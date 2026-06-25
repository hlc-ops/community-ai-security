"""检测推理蓝图：图片 / 视频帧 / 摄像头帧。

接口（均需登录）返回标注图（base64）+ 中文类别 + 风险标记。是否落库由前端
在合适时机调用 /api/records 决定（沿用原有"前端节流抓拍"逻辑）。
"""
import threading
import time
from collections import defaultdict, deque

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..detector import get_detector, decode_data_url, encode_jpg_data_url, risk_level

bp_detect = Blueprint("detect", __name__)


# ============ 时序投票(视频/摄像头流场景)============
# session_key (用户ID + 来源类型) → deque[最近 N 帧的行为类型集合]
_session_pose_history = defaultdict(lambda: deque(maxlen=5))
_session_last_seen = {}  # session_key → 上次访问时间(用于过期清理)
_session_lock = threading.Lock()


def _temporal_vote_filter(session_key, current_events, window=2):
    """对当前帧行为事件做时序投票:连续 window 帧出现才确认。

    Args:
        session_key: 唯一会话 ID(JWT user + endpoint)
        current_events: 当前帧检测到的 pose events
        window: 至少多少帧连续出现才确认

    Returns:
        confirmed_events: 经过投票确认的事件
    """
    now = time.time()
    types_in_frame = {ev["type"] for ev in current_events}

    with _session_lock:
        _session_pose_history[session_key].append(types_in_frame)
        _session_last_seen[session_key] = now
        history = list(_session_pose_history[session_key])

        # 简单清理:超过 60 秒不活跃的 session 删除
        stale = [k for k, t in _session_last_seen.items() if now - t > 60]
        for k in stale:
            _session_pose_history.pop(k, None)
            _session_last_seen.pop(k, None)

    # 帧数不够时,信任本帧(用户刚开始)
    if len(history) < 2:
        return current_events

    confirmed = []
    for ev in current_events:
        hit_count = sum(1 for h in history if ev["type"] in h)
        if hit_count >= window:
            confirmed.append(ev)
    return confirmed


def _get_session_key(endpoint):
    """生成会话 key(基于 JWT 身份 + 端点 + 来源 IP)"""
    try:
        user = get_jwt_identity() or "anon"
    except Exception:
        user = "anon"
    ip = request.remote_addr or "0.0.0.0"
    return f"{user}@{ip}:{endpoint}"


def _valid_zone(zone):
    """校验归一化矩形 {x1,y1,x2,y2}，非法返回 None。"""
    if not isinstance(zone, dict):
        return None
    try:
        x1, y1, x2, y2 = (float(zone[k]) for k in ("x1", "y1", "x2", "y2"))
    except (KeyError, TypeError, ValueError):
        return None
    x1, x2 = sorted((max(0.0, x1), min(1.0, x2)))
    y1, y2 = sorted((max(0.0, y1), min(1.0, y2)))
    if x2 - x1 < 0.02 or y2 - y1 < 0.02:  # 太小视为无效
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _get_class_confs():
    """从 Setting 读取按类别灵敏度，若未配置返回 None。"""
    from ..models import Setting
    raw = Setting.get("class_confs", "")
    if not raw:
        return None
    try:
        import json
        return json.loads(raw)
    except Exception:
        return None


def _draw_pose_overlay(img_bgr, persons, events_by_person=None):
    """把 pose 关键点 + 骨架 + 行为标签画到图上(就地修改)。

    设计:
    - 关键点 / 骨架 / 框:用 cv2(快)
    - 行为中文标签:用 PIL + simhei.ttf(cv2.putText 不支持中文)
    """
    import cv2
    import numpy as np

    SKELETON = [
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (5, 11), (6, 12), (11, 12),
        (11, 13), (13, 15), (12, 14), (14, 16),
        (0, 1), (0, 2), (1, 3), (2, 4),
    ]
    COLOR_KP = (164, 205, 78)
    COLOR_SKELETON = (200, 230, 100)
    COLOR_BOX = (164, 205, 78)

    # 第一遍:用 cv2 画关键点 + 骨架 + 框
    for p in persons:
        kps = p.get('keypoints', [])
        x1, y1, x2, y2 = p.get('box', (0, 0, 0, 0))
        cv2.rectangle(img_bgr, (x1, y1), (x2, y2), COLOR_BOX, 1)
        for a, b in SKELETON:
            if a < len(kps) and b < len(kps):
                ka, kb = kps[a], kps[b]
                if ka and kb:
                    cv2.line(
                        img_bgr,
                        (int(ka['x']), int(ka['y'])),
                        (int(kb['x']), int(kb['y'])),
                        COLOR_SKELETON, 2, cv2.LINE_AA,
                    )
        for kp in kps:
            if kp:
                cv2.circle(
                    img_bgr,
                    (int(kp['x']), int(kp['y'])),
                    4, COLOR_KP, -1, cv2.LINE_AA,
                )

    # 第二遍:用 PIL 画中文行为标签
    if events_by_person:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception:
            return img_bgr
        img_pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 22)
        except Exception:
            try:
                font = ImageFont.truetype("simhei.ttf", 22)
            except Exception:
                font = ImageFont.load_default()
        for idx, p in enumerate(persons):
            if idx not in events_by_person:
                continue
            label = events_by_person[idx]
            x1, y1, x2, y2 = p.get('box', (0, 0, 0, 0))
            tx = x1 + 4
            ty = y1 - 28 if y1 > 36 else y1 + 4
            # 黑色描边
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                draw.text((tx + dx, ty + dy), label, font=font, fill=(0, 0, 0))
            # 红色主色(RGB)
            draw.text((tx, ty), label, font=font, fill=(255, 70, 84))
        img_bgr = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    return img_bgr


def _run_pose_on_frame(frame):
    """对单帧跑 pose + 行为规则,返回行为事件列表(失败返空,不阻断主流程)。"""
    try:
        from .. import pose_detector, behavior_rules
        from flask import current_app
        persons = pose_detector.get_pose_detector().extract(frame, conf=0.3)
        current_app.logger.info(f"[POSE] 检测到 {len(persons)} 个人")
        if not persons:
            return [], []
        analyzer = behavior_rules.PoseBehaviorAnalyzer()
        # 关键点完整性过滤:小于 8 个关键点的人不参与行为判定(避免半身误判)
        for i, p in enumerate(persons):
            visible = sum(1 for k in p.get('keypoints_norm', []) if k)
            if visible < 8:
                # 标记跳过,后续不判定行为
                p['_skip_behavior'] = True
        # 打印每个人的关键调试值
        for i, p in enumerate(persons):
            present = sum(1 for k in p['keypoints_norm'] if k)
            kps = p['keypoints_norm']
            ls = behavior_rules.get(kps, 'left_shoulder')
            rs = behavior_rules.get(kps, 'right_shoulder')
            lh = behavior_rules.get(kps, 'left_hip')
            rh = behavior_rules.get(kps, 'right_hip')
            lk = behavior_rules.get(kps, 'left_knee')
            rk = behavior_rules.get(kps, 'right_knee')
            current_app.logger.info(
                f"[POSE] 人{i+1}: 置信={p['score']:.2f} 可见关键点={present}/17 "
                f"肩={'O' if ls and rs else 'X'} 髋={'O' if lh and rh else 'X'} 膝={'O' if lk and rk else 'X'}"
            )
        # ===== 优先级互斥判定:打架 > 摔倒 > 翻墙 =====
        # 一个人在一帧只产生一种行为事件,避免"屁股着地被判翻墙"这类误报

        events = []

        # Step 1: 先扫一遍打架(打架者不再判摔倒/翻墙)
        fighters = set()
        for i in range(len(persons)):
            if persons[i].get('_skip_behavior'):
                continue
            for j in range(i + 1, len(persons)):
                if persons[j].get('_skip_behavior'):
                    continue
                if analyzer._is_fighting_pair(
                    persons[i]['keypoints_norm'],
                    persons[j]['keypoints_norm']
                ):
                    fighters.add(i)
                    fighters.add(j)
                    events.append({
                        "type": "fighting", "typeZh": "打架斗殴",
                        "person_idx": [i, j], "risk_level": "high",
                        "box": persons[i]['box_norm'],
                    })
                    current_app.logger.info(f"[POSE] 人{i+1} 和 人{j+1} 触发打架")

        # Step 2: 摔倒和翻墙互斥判定
        for i, p in enumerate(persons):
            if i in fighters:
                current_app.logger.info(f"[POSE] 人{i+1} 是打架者,跳过摔倒/翻墙判定")
                continue
            if p.get('_skip_behavior'):
                current_app.logger.info(f"[POSE] 人{i+1} 关键点不足 8 个,跳过行为判定")
                continue
            kps = p['keypoints_norm']
            bbox = p['box_norm']

            is_fall = analyzer._is_fallen_pose(kps, person_bbox=bbox)
            fall_reasons = list(getattr(analyzer, '_last_fall_reasons', []))
            is_climb = analyzer._is_climbing_pose(kps, person_bbox=bbox)
            climb_reasons = list(getattr(analyzer, '_last_climb_reasons', []))

            # 互斥:都触发时,取得分高的(指标多的)
            if is_fall and is_climb:
                if len(fall_reasons) >= len(climb_reasons):
                    is_climb = False
                else:
                    is_fall = False

            if is_fall:
                current_app.logger.info(f"[POSE] 人{i+1} 触发摔倒 · 命中: {fall_reasons}")
                events.append({
                    "type": "fall_detected", "typeZh": "跌倒",
                    "person_idx": i, "risk_level": "high",
                    "box": bbox, "reasons": fall_reasons,
                })
            elif is_climb:
                current_app.logger.info(f"[POSE] 人{i+1} 触发翻墙 · 命中: {climb_reasons}")
                events.append({
                    "type": "fence_climbing", "typeZh": "翻越围栏",
                    "person_idx": i, "risk_level": "high",
                    "box": bbox, "reasons": climb_reasons,
                })

        return events, persons
    except Exception:
        return [], []


def _detect_dataurl(image_data_url: str, conf: float, quality: int = 70, zone=None, run_pose=True,
                    temporal_session=None, temporal_window=2):
    frame = decode_data_url(image_data_url)
    if frame is None:
        raise ValueError("图像解码失败")
    drawn, cls_list, high, mid, boxes = get_detector().detect(frame, conf, zone, _get_class_confs())
    pose_events, persons = ([], []) if not run_pose else _run_pose_on_frame(frame)
    # 时序投票:连续 window 帧出现才确认行为(减少瞬时误报)
    if temporal_session and pose_events:
        pose_events = _temporal_vote_filter(temporal_session, pose_events, window=temporal_window)
    # 把 pose 关键点 + 骨架 + 行为标签画到结果图上
    if persons:
        events_by_person = {}
        for ev in pose_events:
            idx = ev.get("person_idx")
            if isinstance(idx, int):
                events_by_person[idx] = ev["typeZh"]
            elif isinstance(idx, list):
                for k in idx:
                    events_by_person[k] = ev["typeZh"]
        drawn = _draw_pose_overlay(drawn, persons, events_by_person)
    # 行为事件升级风险
    if pose_events:
        high = True
        for ev in pose_events:
            if ev["typeZh"] not in cls_list:
                cls_list.append(ev["typeZh"])
    return {
        "code": 200,
        "img": encode_jpg_data_url(drawn, quality),
        "high_risk": high,
        "mid_risk": mid,
        "risk": risk_level(high, mid),
        "cls_list": cls_list,
        "boxes": boxes,
        "poseEvents": pose_events,
    }


# ============ 自动 LLM 安全复核 频率限制 ============
_auto_review_history = defaultdict(lambda: deque(maxlen=10))
_auto_review_lock = threading.Lock()
_AUTO_REVIEW_MAX_PER_5MIN = 3


def _can_auto_review(session_key):
    """5 分钟内同一会话最多 3 次,通过返回 True"""
    now = time.time()
    with _auto_review_lock:
        history = _auto_review_history[session_key]
        while history and now - history[0] > 300:
            history.popleft()
        if len(history) >= _AUTO_REVIEW_MAX_PER_5MIN:
            return False
        history.append(now)
        return True


@bp_detect.post("/image")
@jwt_required()
def detect_image():
    """multipart 上传图片检测(YOLO + Pose + 空检测时自动 LLM 复核)。"""
    try:
        import cv2
        import numpy as np
        import json as _json
        from ..models import Setting
        from .. import llm

        img_file = request.files["image"]
        raw_image_bytes = img_file.read()
        conf = float(request.form.get("conf", 0.5))
        zone = _valid_zone(_json.loads(request.form.get("zone", "null") or "null"))
        nparr = np.frombuffer(raw_image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"code": 400, "msg": "图片无效"}), 400
        drawn, cls_list, high, mid, boxes = get_detector().detect(img, conf, zone, _get_class_confs())
        # Pose 行为分析(摔倒/翻墙/打架)
        pose_events, persons = _run_pose_on_frame(img)
        # 把 pose 关键点 + 骨架 + 行为标签画到结果图上
        if persons:
            events_by_person = {}
            for ev in pose_events:
                idx = ev.get("person_idx")
                if isinstance(idx, int):
                    events_by_person[idx] = ev["typeZh"]
                elif isinstance(idx, list):
                    for k in idx:
                        events_by_person[k] = ev["typeZh"]
            drawn = _draw_pose_overlay(drawn, persons, events_by_person)
        if pose_events:
            high = True
            for ev in pose_events:
                if ev["typeZh"] not in cls_list:
                    cls_list.append(ev["typeZh"])

        # === 自动 LLM 安全复核 ===
        # 触发条件: 综合风险判定为"安全"(无 high/mid)
        # 含括: ① YOLO + Pose 全无识别 ② 仅识别到 person 但 pose 未识别行为(治翻墙漏识)
        safety_review_result = None
        auto_review_enabled = Setting.get("auto_review_enabled", "1") == "1"
        is_safe = not high and not mid
        if is_safe and auto_review_enabled and llm.is_configured():
            session_key = _get_session_key("image_safety_review")
            if _can_auto_review(session_key):
                from flask import current_app
                current_app.logger.info(f"[AUTO_REVIEW] 触发安全复核 session={session_key}")
                safety_review_result = llm.safety_review(raw_image_bytes)
                if safety_review_result.get("ok"):
                    # 把 LLM 发现的目标也加入 cls_list
                    for obj in safety_review_result.get("found_objects", []):
                        if obj and obj not in cls_list:
                            cls_list.append(f"[LLM] {obj}")
                    # LLM 判定"不真安全" → 升级风险
                    if not safety_review_result.get("truly_safe"):
                        mid = True
        return jsonify({
            "code": 200,
            "img": encode_jpg_data_url(drawn, 70),
            "high_risk": high,
            "mid_risk": mid,
            "risk": risk_level(high, mid),
            "cls_list": cls_list,
            "boxes": boxes,
            "poseEvents": pose_events,
            "safetyReview": safety_review_result,
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500


@bp_detect.post("/frame")
@jwt_required()
def detect_frame():
    """摄像头实时帧(base64 dataURL)+ 时序投票。"""
    try:
        data = request.get_json() or {}
        conf = float(data.get("conf", 0.5))
        zone = _valid_zone(data.get("zone"))
        session = _get_session_key("camera_frame")
        return jsonify(_detect_dataurl(
            data["image"], conf, quality=60, zone=zone,
            temporal_session=session, temporal_window=2,
        ))
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500


@bp_detect.post("/video_frame")
@jwt_required()
def detect_video_frame():
    """视频逐帧(base64 dataURL)+ 时序投票。"""
    try:
        data = request.get_json() or {}
        conf = float(data.get("conf", 0.5))
        zone = _valid_zone(data.get("zone"))
        session = _get_session_key("video_frame")
        return jsonify(_detect_dataurl(
            data["image"], conf, quality=60, zone=zone,
            temporal_session=session, temporal_window=2,
        ))
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500
