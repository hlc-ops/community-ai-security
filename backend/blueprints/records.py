"""检测记录蓝图：替代前端 localStorage，记录持久化到数据库。

接口（均需登录）：
  POST   /api/records              新增记录（含违规截图，落盘）
  GET    /api/records              分页 + 筛选查询
  GET    /api/records/stats        统计（首页/看板用）
  PATCH  /api/records/<id>         更新状态 / 备注
  DELETE /api/records/<id>         删除单条
  POST   /api/records/batch        批量处理 / 批量删除
"""
import base64
import os
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from ..extensions import db
from ..models import DetectionRecord

bp_records = Blueprint("records", __name__)

VALID_TYPES = {"img", "video", "camera"}
VALID_RISKS = {"high", "mid", "low"}


def _parse_dt(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(value[:26], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _save_snapshot(data_url: str) -> str | None:
    """把 dataURL 截图写到快照目录，返回文件名。"""
    if not data_url or "," not in data_url:
        return None
    try:
        payload = data_url.split(",", 1)[1]
        raw = base64.b64decode(payload)
        fname = f"{datetime.now():%Y%m%d}_{uuid.uuid4().hex[:12]}.jpg"
        with open(os.path.join(current_app.config["SNAPSHOT_DIR"], fname), "wb") as f:
            f.write(raw)
        return fname
    except Exception as e:
        current_app.logger.warning("保存快照失败：%s", e)
        return None


@bp_records.post("")
@jwt_required()
def create_record():
    data = request.get_json(silent=True) or {}
    rtype = data.get("type")
    risk = data.get("risk")
    if rtype not in VALID_TYPES:
        return jsonify({"code": 400, "msg": f"非法类型 {rtype}"}), 400
    if risk not in VALID_RISKS:
        return jsonify({"code": 400, "msg": f"非法风险等级 {risk}"}), 400

    rec = DetectionRecord(
        record_type=rtype,
        risk_level=risk,
        status="pending",
        image_path=_save_snapshot(data.get("image")),
        duration_seconds=float(data.get("durationSeconds") or 0),
        started_at=_parse_dt(data.get("startedAt")) or datetime.utcnow(),
        ended_at=_parse_dt(data.get("endedAt")),
        user_id=int(get_jwt_identity()),
    )
    rec.cls_list = data.get("clsList") or []
    db.session.add(rec)
    db.session.commit()

    # 高/中危事件实时广播到所有订阅前端
    if rec.risk_level in ("high", "mid"):
        from .. import events
        events.publish("alert", rec.to_dict())
    # 高危事件：若启用了 AI 分级 → 走 triage 异步分级（分级完成再按 urgency 决定推送）
    # 未启用 → 维持原行为：直接推送
    if rec.risk_level == "high":
        from .. import triage, alert
        if triage.is_enabled():
            triage.schedule(current_app._get_current_object(), rec.id)
        else:
            alert.notify_async(current_app._get_current_object(), rec.id)

    return jsonify({"code": 200, "msg": "已保存", "record": rec.to_dict()})


@bp_records.get("")
@jwt_required()
def list_records():
    q = DetectionRecord.query
    rtype = request.args.get("type")
    risk = request.args.get("risk")
    status = request.args.get("status")
    keyword = request.args.get("keyword", "").strip()

    if rtype in VALID_TYPES:
        q = q.filter_by(record_type=rtype)
    if risk in VALID_RISKS:
        q = q.filter_by(risk_level=risk)
    if status in {"pending", "processed", "processing", "closed"}:
        q = q.filter_by(status=status)
    if keyword:
        q = q.filter(DetectionRecord.remark.ilike(f"%{keyword}%"))
    # 仅看带视频片段
    if request.args.get("hasClip") in ("1", "true"):
        q = q.filter(DetectionRecord.clip_path.isnot(None))

    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("pageSize", 10)), 1), 100)

    q = q.order_by(DetectionRecord.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return jsonify({
        "code": 200,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": [r.to_dict() for r in items],
    })


@bp_records.get("/stats")
@jwt_required()
def stats():
    """看板统计：总数、未处理数、各类型/各风险/各类别分布。"""
    total = DetectionRecord.query.count()
    pending = DetectionRecord.query.filter_by(status="pending").count()

    by_type = dict(
        db.session.query(DetectionRecord.record_type, func.count())
        .group_by(DetectionRecord.record_type).all()
    )
    by_risk = dict(
        db.session.query(DetectionRecord.risk_level, func.count())
        .group_by(DetectionRecord.risk_level).all()
    )

    # 各违规类别计数（cls_list 存的是 JSON，Python 侧聚合）
    by_class: dict[str, int] = {}
    for (cls_json,) in db.session.query(DetectionRecord.cls_list_json).all():
        try:
            import json
            for c in json.loads(cls_json or "[]"):
                by_class[c] = by_class.get(c, 0) + 1
        except Exception:
            pass

    # 近 7 天趋势（按 UTC 日期），填补无数据的日期为 0
    trend = _recent_trend(days=7)

    return jsonify({
        "code": 200,
        "total": total,
        "pending": pending,
        "byType": by_type,
        "byRisk": by_risk,
        "byClass": by_class,
        "trend": trend,
    })


def _recent_trend(days: int = 7) -> list[dict]:
    """返回近 N 天每日记录总数与高危数：[{date, total, high}]。"""
    from datetime import date, timedelta

    today = date.today()
    start = today - timedelta(days=days - 1)

    day_col = func.date(DetectionRecord.created_at)
    base = db.session.query(day_col, func.count()).filter(
        DetectionRecord.created_at >= start
    ).group_by(day_col)

    total_map = {str(d): c for d, c in base.all()}
    high_map = {
        str(d): c
        for d, c in base.filter(DetectionRecord.risk_level == "high").all()
    }

    result = []
    for i in range(days):
        d = str(start + timedelta(days=i))
        result.append({
            "date": d[5:],  # 只取 MM-DD
            "total": total_map.get(d, 0),
            "high": high_map.get(d, 0),
        })
    return result


@bp_records.patch("/<int:rid>")
@jwt_required()
def update_record(rid):
    rec = db.session.get(DetectionRecord, rid)
    if not rec:
        return jsonify({"code": 404, "msg": "记录不存在"}), 404
    data = request.get_json(silent=True) or {}
    valid_states = {"pending", "processing", "processed", "closed"}
    if "status" in data and data["status"] in valid_states:
        new_st = data["status"]
        # 状态转换时记录时间戳
        if new_st == "processed" and rec.status != "processed":
            rec.processed_at = datetime.utcnow()
        if new_st == "closed" and rec.status != "closed":
            rec.closed_at = datetime.utcnow()
        rec.status = new_st
    if "remark" in data:
        rec.remark = data["remark"]
    if "assigneeId" in data:
        rec.assignee_id = int(data["assigneeId"]) if data["assigneeId"] else None
    db.session.commit()
    return jsonify({"code": 200, "msg": "已更新", "record": rec.to_dict()})


@bp_records.post("/<int:rid>/assign")
@jwt_required()
def assign_record(rid):
    """分配处理人。status=pending → processing。"""
    rec = db.session.get(DetectionRecord, rid)
    if not rec:
        return jsonify({"code": 404, "msg": "记录不存在"}), 404
    aid = (request.get_json(silent=True) or {}).get("assigneeId")
    rec.assignee_id = int(aid) if aid else None
    if rec.status == "pending" and rec.assignee_id:
        rec.status = "processing"
    db.session.commit()
    return jsonify({"code": 200, "msg": "已分配", "record": rec.to_dict()})


@bp_records.post("/escalate_overdue")
@jwt_required()
def escalate_overdue():
    """触发一次"超时未处理告警自动升级"扫描，由前端/定时器调用。
    超过 minutes 分钟仍为 pending 的高危记录标记 escalated。"""
    minutes = int((request.get_json(silent=True) or {}).get("minutes", 30))
    threshold = datetime.utcnow() - timedelta(minutes=minutes)
    q = DetectionRecord.query.filter(
        DetectionRecord.status == "pending",
        DetectionRecord.risk_level == "high",
        DetectionRecord.escalated == False,  # noqa: E712
        DetectionRecord.created_at <= threshold,
    )
    n = 0
    for r in q.all():
        r.escalated = True
        r.escalated_at = datetime.utcnow()
        n += 1
    db.session.commit()
    return jsonify({"code": 200, "msg": "扫描完成", "escalated": n})


@bp_records.delete("/<int:rid>")
@jwt_required()
def delete_record(rid):
    rec = db.session.get(DetectionRecord, rid)
    if not rec:
        return jsonify({"code": 404, "msg": "记录不存在"}), 404
    _remove_snapshot(rec)
    db.session.delete(rec)
    db.session.commit()
    from .. import audit
    audit.log("record.delete", "record", rid)
    return jsonify({"code": 200, "msg": "已删除"})


@bp_records.post("/batch")
@jwt_required()
def batch():
    """批量操作：action=process|delete，ids=[...]。"""
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    ids = data.get("ids") or []
    if not ids:
        return jsonify({"code": 400, "msg": "未选择记录"}), 400

    recs = DetectionRecord.query.filter(DetectionRecord.id.in_(ids)).all()
    if action == "process":
        for r in recs:
            r.status = "processed"
    elif action == "delete":
        for r in recs:
            _remove_snapshot(r)
            db.session.delete(r)
    else:
        return jsonify({"code": 400, "msg": f"未知操作 {action}"}), 400

    db.session.commit()
    from .. import audit
    audit.log("record.batch", "record", "", f"action={action} count={len(recs)}")
    return jsonify({"code": 200, "msg": f"已处理 {len(recs)} 条"})


def _remove_snapshot(rec: DetectionRecord):
    if rec.image_path:
        path = os.path.join(current_app.config["SNAPSHOT_DIR"], rec.image_path)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    if rec.clip_path:
        path = os.path.join(current_app.config["DATA_DIR"], "clips", rec.clip_path)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
