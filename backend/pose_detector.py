"""YOLOv8-pose 人体关键点检测封装。

使用 Ultralytics 预训练的 yolov8s-pose 模型(COCO Keypoints,17 个关键点),
首次调用自动下载权重,无需额外训练。

关键点索引(COCO 标准):
    0  nose
    1  left_eye      2  right_eye
    3  left_ear      4  right_ear
    5  left_shoulder 6  right_shoulder    ← 摔倒/翻墙关键
    7  left_elbow    8  right_elbow       ← 打架关键
    9  left_wrist    10 right_wrist       ← 翻墙/打架
    11 left_hip      12 right_hip         ← 摔倒关键
    13 left_knee     14 right_knee        ← 摔倒/翻墙
    15 left_ankle    16 right_ankle       ← 跑步

每个点输出 (x, y, confidence)。conf < 0.3 视为不可见(置为 None)。
"""
import threading


class PoseDetector:
    """单例 pose 检测器,延迟初始化。"""

    def __init__(self, model_path: str = "yolov8s-pose.pt", imgsz: int = 640):
        from ultralytics import YOLO
        self.imgsz = imgsz
        # 首次会自动从 ultralytics 仓库下载到 ~/.cache/torch/hub/(几秒到几分钟)
        self.model = YOLO(model_path, task="pose")
        self._lock = threading.Lock()

    def extract(self, frame_bgr, conf: float = 0.5) -> list:
        """对一帧 BGR 图提取所有人体关键点。

        返回: [
            {
                "box": (x1, y1, x2, y2),         # 人体框,像素坐标
                "box_norm": (x1, y1, x2, y2),    # 归一化坐标
                "score": 0.92,                    # 人体置信度
                "keypoints": [                   # 17 个关键点
                    {"x": 320, "y": 100, "conf": 0.95},  # 0 nose
                    ...
                ],
                "keypoints_norm": [...],          # 归一化版本
            },
            ...
        ]
        """
        with self._lock:
            results = self.model.predict(
                frame_bgr, conf=conf, verbose=False, imgsz=self.imgsz
            )
        if not results:
            return []

        res = results[0]
        if res.keypoints is None or res.boxes is None:
            return []

        h, w = frame_bgr.shape[:2]
        persons = []
        boxes_xy = res.boxes.xyxy.cpu().numpy()
        scores = res.boxes.conf.cpu().numpy()
        kps_data = res.keypoints.data.cpu().numpy()  # shape (n, 17, 3) - x, y, conf

        for i in range(len(boxes_xy)):
            x1, y1, x2, y2 = boxes_xy[i].tolist()
            person_kps = []
            person_kps_norm = []
            for j in range(17):
                kx, ky, kc = float(kps_data[i, j, 0]), float(kps_data[i, j, 1]), float(kps_data[i, j, 2])
                if kc < 0.3:
                    person_kps.append(None)
                    person_kps_norm.append(None)
                else:
                    person_kps.append({"x": kx, "y": ky, "conf": round(kc, 3)})
                    person_kps_norm.append({
                        "x": round(kx / w, 4),
                        "y": round(ky / h, 4),
                        "conf": round(kc, 3),
                    })
            persons.append({
                "box": (int(x1), int(y1), int(x2), int(y2)),
                "box_norm": (
                    round(x1 / w, 4), round(y1 / h, 4),
                    round(x2 / w, 4), round(y2 / h, 4),
                ),
                "score": round(float(scores[i]), 3),
                "keypoints": person_kps,
                "keypoints_norm": person_kps_norm,
            })
        return persons


# ============ 单例管理 ============
_pose = None
_pose_lock = threading.Lock()


def get_pose_detector() -> PoseDetector:
    """获取全局 pose 检测器(首次调用懒加载)。"""
    global _pose
    if _pose is None:
        with _pose_lock:
            if _pose is None:
                _pose = PoseDetector()
    return _pose


# ============ 关键点访问辅助 ============

KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

KP_IDX = {name: i for i, name in enumerate(KP_NAMES)}


def get(kps, name):
    """安全获取关键点,失败返 None"""
    idx = KP_IDX.get(name)
    if idx is None or idx >= len(kps):
        return None
    return kps[idx]


def midpoint(p1, p2):
    """两点中点(任一为 None 则返回 None)"""
    if not p1 or not p2:
        return None
    return {"x": (p1["x"] + p2["x"]) / 2, "y": (p1["y"] + p2["y"]) / 2}


def distance(p1, p2):
    """欧氏距离(任一为 None 则返回 inf)"""
    if not p1 or not p2:
        return float("inf")
    return ((p1["x"] - p2["x"]) ** 2 + (p1["y"] - p2["y"]) ** 2) ** 0.5
