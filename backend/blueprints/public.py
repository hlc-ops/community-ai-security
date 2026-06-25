"""居民端公开 API(无需登录,适合 H5 / 微信扫码访问)。

所有数据脱敏处理:
- 只显示事件类型 + 时间 + 处理状态,不显示截图/视频
- 不返回业主信息、车牌、人脸
- 摄像头列表只返回名称/位置/在线状态,不返回 RTSP

  GET  /api/public/overview                小区总览(安全指数、统计)
  GET  /api/public/parking                 车位实时余量
  GET  /api/public/events?limit=20         近期事件列表(脱敏)
  POST /api/public/feedback                业主反馈(简单留言)
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import DetectionRecord, Camera, Polygon, ParkingSlotStatus, Setting

bp_public = Blueprint("public", __name__)


@bp_public.get("/overview")
def overview():
    """小区运行总览(脱敏)。"""
    # 今日时间窗
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 今日告警
    today_records = DetectionRecord.query.filter(
        DetectionRecord.created_at >= today_start
    ).all()
    today_high = sum(1 for r in today_records if r.risk_level == "high")
    today_processed = sum(1 for r in today_records if r.status == "processed")

    # 摄像头健康
    from .. import stream as _stream
    cameras = Camera.query.filter_by(enabled=True).all()
    online_count = 0
    for cam in cameras:
        s = _stream.manager._streams.get(cam.id) if hasattr(_stream, "manager") else None
        if s and s.alive and not s.error:
            online_count += 1
        elif cam.last_online_at and (now - cam.last_online_at) < timedelta(minutes=2):
            online_count += 1
    total_cameras = len(cameras)

    # 车位汇总
    parking_polygons = Polygon.query.filter_by(
        polygon_type="parking_slot", enabled=True
    ).count()
    occupied = ParkingSlotStatus.query.filter_by(occupied=True).count()
    parking_available = max(0, parking_polygons - occupied)

    # 安全指数(简化版:高危减分)
    score = max(60, 100 - today_high * 5)
    if score >= 95:
        grade, grade_color = "优秀", "#16b3a8"
    elif score >= 85:
        grade, grade_color = "良好", "#3b82f6"
    elif score >= 70:
        grade, grade_color = "注意", "#f59e0b"
    else:
        grade, grade_color = "警示", "#ef4444"

    # 品牌信息(给业主端展示小区名)
    community_name = Setting.get("brand_name", "智慧社区")

    return jsonify({
        "code": 200,
        "data": {
            "communityName": community_name,
            "score": score,
            "grade": grade,
            "gradeColor": grade_color,
            "today": {
                "total": len(today_records),
                "high": today_high,
                "processed": today_processed,
                "pending": len(today_records) - today_processed,
            },
            "cameras": {"online": online_count, "total": total_cameras},
            "parking": {
                "total": parking_polygons,
                "occupied": occupied,
                "available": parking_available,
            },
            "updatedAt": now.isoformat() + "Z",
        },
    })


@bp_public.get("/parking")
def parking_status():
    """车位实时状态(给业主小程序/扫码看)。"""
    slots = []
    parking_polygons = Polygon.query.filter_by(
        polygon_type="parking_slot", enabled=True
    ).all()
    status_map = {
        s.polygon_id: s
        for s in ParkingSlotStatus.query.all()
    }
    for p in parking_polygons:
        st = status_map.get(p.id)
        slots.append({
            "id": p.id,
            "name": p.name or f"车位 {p.id}",
            "type": "parking_slot",
            "occupied": bool(st and st.occupied),
            "since": (st.occupied_since.isoformat() + "Z") if (st and st.occupied_since) else None,
        })
    charging_polygons = Polygon.query.filter_by(
        polygon_type="charging_slot", enabled=True
    ).all()
    for p in charging_polygons:
        st = status_map.get(p.id)
        slots.append({
            "id": p.id,
            "name": p.name or f"充电位 {p.id}",
            "type": "charging_slot",
            "occupied": bool(st and st.occupied),
            "since": (st.occupied_since.isoformat() + "Z") if (st and st.occupied_since) else None,
        })

    total = len(slots)
    occupied = sum(1 for s in slots if s["occupied"])
    return jsonify({
        "code": 200,
        "data": {
            "slots": slots,
            "total": total,
            "occupied": occupied,
            "available": total - occupied,
            "usagePercent": round((occupied / total * 100) if total else 0, 1),
            "updatedAt": datetime.utcnow().isoformat() + "Z",
        },
    })


@bp_public.get("/events")
def events():
    """近期事件列表(脱敏:只返回类型/时间/处理状态)。"""
    try:
        limit = max(1, min(50, int(request.args.get("limit", 20))))
    except Exception:
        limit = 20

    records = (
        DetectionRecord.query
        .order_by(DetectionRecord.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for r in records:
        items.append({
            "id": r.id,
            "type": r.violation_type or "general",
            "typeZh": DetectionRecord.VIOLATION_ZH.get(r.violation_type, "异常事件") if r.violation_type else "异常事件",
            "risk": r.risk_level,
            "riskZh": DetectionRecord.RISK_ZH.get(r.risk_level, r.risk_level),
            "status": r.status,
            "statusZh": DetectionRecord.STATUS_ZH.get(r.status, r.status),
            "createdAt": r.created_at.isoformat() + "Z" if r.created_at else None,
        })

    return jsonify({"code": 200, "data": items})


@bp_public.post("/feedback")
def feedback():
    """业主反馈(简化版:存到设置表的 JSON 数组里)。"""
    import json as _json
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:32]
    content = (data.get("content") or "").strip()[:500]
    contact = (data.get("contact") or "").strip()[:64]
    if not content:
        return jsonify({"code": 400, "msg": "反馈内容不能为空"}), 400

    existing = Setting.get("public_feedback", "[]")
    try:
        arr = _json.loads(existing)
        if not isinstance(arr, list):
            arr = []
    except Exception:
        arr = []
    arr.append({
        "name": name or "匿名业主",
        "contact": contact,
        "content": content,
        "at": datetime.utcnow().isoformat() + "Z",
    })
    # 限制最多保留 200 条
    arr = arr[-200:]
    Setting.put("public_feedback", _json.dumps(arr, ensure_ascii=False))
    db.session.commit()

    return jsonify({"code": 200, "msg": "已收到您的反馈,物业将尽快处理"})
