"""SSE 事件流：浏览器 EventSource 订阅高危告警等实时事件。

EventSource 不支持自定义请求头，所以 JWT 通过 query 参数 ?token=xxx 传入。
"""
import queue

from flask import Blueprint, Response, request, jsonify, stream_with_context
from flask_jwt_extended import decode_token

from .. import events

bp_events = Blueprint("events", __name__)


@bp_events.get("/stream")
def stream():
    token = request.args.get("token", "")
    try:
        decode_token(token)
    except Exception:
        return jsonify({"code": 401, "msg": "未登录或令牌无效"}), 401

    @stream_with_context
    def gen():
        q = events.subscribe()
        try:
            yield "retry: 5000\n\n"        # 客户端断线 5s 后重连
            yield ": connected\n\n"
            while True:
                try:
                    msg = q.get(timeout=20)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"     # 防代理/防火墙断连
        finally:
            events.unsubscribe(q)

    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
