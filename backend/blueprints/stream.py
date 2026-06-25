"""网络摄像头（RTSP/IP）流蓝图。

  POST /api/stream/start          body {url, conf, snapInterval} → {streamId}
  GET  /api/stream/mjpeg/<sid>    MJPEG 实时画面（供 <img> 直接显示）
  GET  /api/stream/status/<sid>   状态轮询（风险/类别/存活/错误）
  POST /api/stream/stop           body {streamId}

注意：MJPEG 接口无法通过 <img> 带 JWT 头，故用不可猜测的 streamId 作为访问凭据；
start/status/stop 仍需登录。
"""
from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required

from ..stream import manager

bp_stream = Blueprint("stream", __name__)


@bp_stream.post("/start")
@jwt_required()
def start():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"code": 400, "msg": "请填写摄像头地址（rtsp:// 或 http://）"}), 400
    conf = float(data.get("conf", 0.5))
    snap = int(data.get("snapInterval", 10))
    from .detect import _valid_zone
    zone = _valid_zone(data.get("zone"))
    app = current_app._get_current_object()
    sid = manager.start(app, url, conf, snap, zone)
    return jsonify({"code": 200, "streamId": sid})


@bp_stream.get("/mjpeg/<sid>")
def mjpeg(sid):
    worker = manager.get(sid)
    if not worker:
        return jsonify({"code": 404, "msg": "流不存在或已停止"}), 404
    return Response(
        worker.mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@bp_stream.get("/status/<sid>")
@jwt_required()
def status(sid):
    worker = manager.get(sid)
    if not worker:
        return jsonify({"code": 404, "msg": "流不存在"}), 404
    return jsonify({
        "code": 200,
        "alive": worker.alive,
        "error": worker.error,
        "risk": worker.risk,
        "clsList": worker.cls_list,
        "boxes": worker.latest_boxes,
        "snapCount": worker.snap_count,
    })


@bp_stream.post("/stop")
@jwt_required()
def stop():
    sid = (request.get_json(silent=True) or {}).get("streamId")
    if sid:
        manager.stop(sid)
    return jsonify({"code": 200, "msg": "已停止"})
