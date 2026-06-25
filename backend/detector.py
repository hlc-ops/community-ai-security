"""YOLO + OpenVINO 检测器封装（进程内单例）。

相对旧 app.py 的优化：
  * 模型/字体只加载一次（旧代码每帧都 ImageFont.truetype，浪费）；
  * draw_boxes 复用全局字体；
  * 统一返回结构化结果（标注图 + 中文类别 + 风险标记），便于各接口复用。

下一步可做（本阶段未做）：INT8 量化导出，CPU 上还能再快 2~4 倍。
"""
import base64
import threading

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# === 智慧社区违规检测 8 类(英文 → 中文)===
# YOLO 只负责"识别物体是什么",违规判定由后端业务规则引擎结合 polygon 完成
# 2026-06-21:trash 拆按业务场景分:
#   trash_bag(弃置垃圾袋)→ 大件清运工单(查规划堆放点)
#   trash_item(散落垃圾)→ 实时保洁工单(白色随手袋+瓶罐杂物)
ZH_MAP = {
    "person": "行人",
    "car": "车辆",
    "dog": "狗",
    "cat": "猫",
    "trash_bag": "弃置垃圾袋",
    "trash_item": "散落垃圾",
    "electric_bike": "电瓶车",
    "fire": "明火",
}

# 按风险等级统一配色(BGR,前端 colorFor 同一套):
#   高危=红 / 中危=黄 / 低危=绿
_COLOR_HIGH = (45, 34, 245)     # #f5222d
_COLOR_MID  = (20, 173, 250)    # #faad14
_COLOR_LOW  = (26, 196, 82)     # #52c41a
# 默认配色(实际告警等级由业务规则引擎结合 polygon 决定,这里只是检测画面上色)
COLORS = {
    0: _COLOR_LOW,    # 行人(默认低,在禁区里才升高)
    1: _COLOR_LOW,    # 车辆(默认低,在禁停区才高)
    2: _COLOR_LOW,    # 狗(默认低,在草坪才中)
    3: _COLOR_LOW,    # 猫
    4: _COLOR_MID,    # 垃圾袋(出现即可疑)
    5: _COLOR_MID,    # 散落垃圾
    6: _COLOR_MID,    # 电瓶车(在电梯/楼道才高)
    7: _COLOR_HIGH,   # 明火(任何场景都是高危)
}

# 中文类别 → 默认风险等级(high / mid / low)
# 注意:这是"检测层"的默认值,真实业务等级由 business_rules.py 结合摄像头位置 + polygon 决定
RISK = {
    "行人": "low",
    "车辆": "low",
    "狗": "low",
    "猫": "low",
    "垃圾袋": "mid",
    "散落垃圾": "mid",
    "电瓶车": "mid",
    "明火": "high",
}


class Detector:
    def __init__(self, model_path: str, imgsz: int = 416):
        # 延迟导入 ultralytics，避免无模型环境下 import backend 即报错
        from ultralytics import YOLO

        self.imgsz = imgsz
        self.model = YOLO(model_path, task="detect")
        raw_names = self.model.names
        self.class_names_zh = [
            ZH_MAP.get(raw_names[i], raw_names[i]) for i in range(len(raw_names))
        ]
        # 字体加载一次，全局复用
        try:
            self.font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 20)
        except Exception:
            self.font = ImageFont.load_default()
        # 推理串行化：OpenVINO 模型实例非线程安全，加锁保护
        self._lock = threading.Lock()

    def _draw_boxes(self, img_bgr, boxes, zone=None):
        img_pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        h, w = img_bgr.shape[:2]
        # 先画检测区域框（电子围栏）
        if zone:
            zx1, zy1, zx2, zy2 = (
                int(zone["x1"] * w), int(zone["y1"] * h),
                int(zone["x2"] * w), int(zone["y2"] * h),
            )
            draw.rectangle([(zx1, zy1), (zx2, zy2)], outline=(255, 215, 0), width=2)
            draw.text((zx1 + 4, zy1 + 2), "检测区域", font=self.font, fill=(255, 215, 0))
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            cls_name = self.class_names_zh[cls_id]
            label = f"{cls_name} {conf:.2f}"
            color_bgr = COLORS.get(cls_id, (0, 255, 0))
            color_rgb = (color_bgr[2], color_bgr[1], color_bgr[0])
            draw.rectangle([(x1, y1), (x2, y2)], outline=color_rgb, width=3)
            tx, ty = x1, y1 - 24
            if ty < 0:
                ty = y1 + 2
            for ox, oy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                draw.text((tx + ox, ty + oy), label, font=self.font, fill=(0, 0, 0))
            draw.text((tx, ty), label, font=self.font, fill=color_rgb)
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    @staticmethod
    def _in_zone(box, w, h, zone):
        """框中心是否落在归一化矩形 zone 内。"""
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
        return zone["x1"] <= cx <= zone["x2"] and zone["y1"] <= cy <= zone["y2"]

    def detect(self, frame_bgr, conf: float = 0.5, zone=None, class_confs=None):
        """对一帧 BGR 图做检测，返回 (标注图BGR, 中文类别列表, high, mid, boxes_norm)。

        zone 为归一化矩形 {x1,y1,x2,y2}（0~1）时，只保留中心落在区域内的目标。
        class_confs 为按中文类别名映射的置信度下限 {"未戴安全帽":0.6,...}；为 None 时
        所有类别共用 conf 参数。后端用最低阈值跑推理，再按类别做精细过滤。
        """
        # 用最低阈值跑一次推理，后面再按类别精细过滤
        run_conf = conf
        if class_confs:
            run_conf = min(min(class_confs.values()), conf)
        with self._lock:
            res = self.model.predict(
                frame_bgr, conf=run_conf, verbose=False, imgsz=self.imgsz,
                # 调优 NMS:让密集同类目标(多个垃圾袋)都保留
                # iou 是 NMS 阈值,越高越宽松(越不容易抑制)
                iou=0.7,         # 保持 YOLO 默认,对中等重叠的同类目标友好
                max_det=500,     # 默认 300,放大到 500,允许更多检测结果
                agnostic_nms=False,  # 类别相关 NMS:不同类别(袋子和瓶子)不互相抑制
            )[0]
        boxes = list(res.boxes) if res.boxes is not None else []
        if zone:
            h, w = frame_bgr.shape[:2]
            boxes = [b for b in boxes if self._in_zone(b, w, h, zone)]
        if class_confs:
            kept = []
            for b in boxes:
                name = self.class_names_zh[int(b.cls[0])]
                thr = class_confs.get(name, conf)
                if float(b.conf[0]) >= thr:
                    kept.append(b)
            boxes = kept
        # 归一化坐标列表（供前端 canvas 叠层画框，画面用原视频流，丝滑）
        h, w = frame_bgr.shape[:2]
        boxes_norm = []
        for b in boxes:
            x1, y1, x2, y2 = b.xyxy[0].cpu().numpy().tolist()
            cid = int(b.cls[0])
            boxes_norm.append({
                "x1": round(x1 / w, 4),
                "y1": round(y1 / h, 4),
                "x2": round(x2 / w, 4),
                "y2": round(y2 / h, 4),
                "cls": cid,
                "conf": round(float(b.conf[0]), 3),
                "name": self.class_names_zh[cid],
            })
        drawn = self._draw_boxes(frame_bgr, boxes, zone) if (boxes or zone) else frame_bgr
        cls_list = [self.class_names_zh[int(b.cls[0])] for b in boxes]
        high = any(RISK.get(c) == "high" for c in cls_list)
        mid = any(RISK.get(c) == "mid" for c in cls_list)
        return drawn, cls_list, high, mid, boxes_norm


# ---- 单例管理 ----
_detector = None
_detector_lock = threading.Lock()


def get_detector() -> Detector:
    """获取全局检测器（首次调用时加载模型）。"""
    global _detector
    if _detector is None:
        with _detector_lock:
            if _detector is None:
                from flask import current_app

                _detector = Detector(
                    current_app.config["MODEL_PATH"],
                    current_app.config["MODEL_IMGSZ"],
                )
    return _detector


# ---- 编解码工具 ----
def decode_data_url(data_url: str):
    """'data:image/jpeg;base64,xxxx' → BGR ndarray。"""
    payload = data_url.split(",", 1)[1] if "," in data_url else data_url
    img_bytes = base64.b64decode(payload)
    arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def encode_jpg_data_url(img_bgr, quality: int = 70) -> str:
    """BGR ndarray → 'data:image/jpeg;base64,...'。"""
    _, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()


def risk_level(high: bool, mid: bool) -> str:
    return "high" if high else ("mid" if mid else "low")
