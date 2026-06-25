"""摄像头档案蓝图。

  GET    /api/cameras                列表（含在线状态）
  POST   /api/cameras                新增
  PUT    /api/cameras/<id>           编辑
  DELETE /api/cameras/<id>           删除（会先停流）
  POST   /api/cameras/<id>/start     启动该摄像头的拉流（返回 streamId）
  POST   /api/cameras/<id>/stop      停止该摄像头
"""
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from ..extensions import db
from ..models import Camera
from ..stream import manager
from .. import audit

bp_cameras = Blueprint("cameras", __name__)


def _status(cam: Camera) -> dict:
    from datetime import datetime
    from ..health import OFFLINE_THRESHOLD_SEC

    ws = manager.get_by_camera(cam.id)
    if ws:
        _, w = ws
        d = cam.to_dict(online=w.alive and not w.error, error=w.error or "")
        d["healthState"] = "online" if (w.alive and not w.error) else "error"
        return d
    d = cam.to_dict()
    if not cam.last_online_at:
        d["healthState"] = "never"
    else:
        gap = (datetime.utcnow() - cam.last_online_at).total_seconds()
        d["offlineFor"] = int(gap)
        d["healthState"] = "offline" if gap > OFFLINE_THRESHOLD_SEC else "recent"
    return d


@bp_cameras.get("")
@jwt_required()
def list_cameras():
    cams = Camera.query.order_by(Camera.created_at.asc()).all()
    return jsonify({"code": 200, "items": [_status(c) for c in cams]})


@bp_cameras.post("")
@jwt_required()
def create_camera():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()
    if not name or not url:
        return jsonify({"code": 400, "msg": "名称与地址不能为空"}), 400
    cam = Camera(
        name=name,
        url=url,
        location=(data.get("location") or "").strip(),
        enabled=bool(data.get("enabled", True)),
        conf=float(data.get("conf", 0.5)),
        snap_interval=int(data.get("snapInterval", 10)),
        schedule_enabled=bool(data.get("scheduleEnabled", False)),
        schedule_start=(data.get("scheduleStart") or "07:00")[:5],
        schedule_end=(data.get("scheduleEnd") or "19:00")[:5],
    )
    db.session.add(cam)
    db.session.commit()
    audit.log("camera.create", "camera", cam.id, cam.name)
    return jsonify({"code": 200, "msg": "已创建", "camera": cam.to_dict()})


@bp_cameras.put("/<int:cid>")
@jwt_required()
def update_camera(cid):
    cam = db.session.get(Camera, cid)
    if not cam:
        return jsonify({"code": 404, "msg": "摄像头不存在"}), 404
    data = request.get_json(silent=True) or {}
    for k_in, attr, cast in [
        ("name", "name", lambda v: v.strip()),
        ("url", "url", lambda v: v.strip()),
        ("location", "location", lambda v: v.strip()),
        ("enabled", "enabled", bool),
        ("conf", "conf", float),
        ("snapInterval", "snap_interval", int),
        ("scheduleEnabled", "schedule_enabled", bool),
        ("scheduleStart", "schedule_start", lambda v: (v or "07:00")[:5]),
        ("scheduleEnd", "schedule_end", lambda v: (v or "19:00")[:5]),
    ]:
        if k_in in data:
            setattr(cam, attr, cast(data[k_in]))
    db.session.commit()
    return jsonify({"code": 200, "msg": "已更新", "camera": _status(cam)})


@bp_cameras.delete("/<int:cid>")
@jwt_required()
def delete_camera(cid):
    cam = db.session.get(Camera, cid)
    if not cam:
        return jsonify({"code": 404, "msg": "摄像头不存在"}), 404
    name = cam.name
    manager.stop_camera(cid)
    db.session.delete(cam)
    db.session.commit()
    audit.log("camera.delete", "camera", cid, name)
    return jsonify({"code": 200, "msg": "已删除"})


@bp_cameras.post("/<int:cid>/start")
@jwt_required()
def start_camera(cid):
    cam = db.session.get(Camera, cid)
    if not cam:
        return jsonify({"code": 404, "msg": "摄像头不存在"}), 404
    if not cam.enabled:
        return jsonify({"code": 400, "msg": "该摄像头已停用，请先启用"}), 400
    app = current_app._get_current_object()
    schedule = {
        "enabled": bool(cam.schedule_enabled),
        "start": cam.schedule_start or "00:00",
        "end": cam.schedule_end or "23:59",
    }
    sid = manager.start(app, cam.url, cam.conf, cam.snap_interval,
                        zone=None, camera_id=cam.id, schedule=schedule)
    cam.last_online_at = datetime.utcnow()
    db.session.commit()
    audit.log("camera.start", "camera", cam.id, cam.name)
    return jsonify({"code": 200, "msg": "已开启", "streamId": sid})


@bp_cameras.post("/<int:cid>/stop")
@jwt_required()
def stop_camera(cid):
    cam = db.session.get(Camera, cid)
    if not cam:
        return jsonify({"code": 404, "msg": "摄像头不存在"}), 404
    manager.stop_camera(cid)
    audit.log("camera.stop", "camera", cam.id, cam.name)
    return jsonify({"code": 200, "msg": "已停止"})
