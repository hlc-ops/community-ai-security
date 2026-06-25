"""摄像头健康监控后台 watcher。

每 30 秒巡检一次：
- 若摄像头有 stream 在跑（manager 中存在）且 alive=True：说明在线，跳过
- 若 stream 不存在或不 alive，但 last_online_at 在最近 OFFLINE_THRESHOLD 内：
  说明刚掉线，发一次"离线告警"（SSE 广播 + 报警推送）；同一摄像头同次离线不重复告警
- 若 last_online_at 超过 OFFLINE_THRESHOLD 很久：维持"离线"状态，不再告警

只对 enabled=True 的摄像头巡检。
"""
import threading
import time
from datetime import datetime, timedelta

OFFLINE_THRESHOLD_SEC = 90      # 心跳停止超过 90 秒视为离线
LOOP_INTERVAL_SEC = 30

# 已告警过的摄像头集合，避免重复打扰；上线时清除
_alerted: set[int] = set()
_lock = threading.Lock()
_thread = None
_stop = threading.Event()


def _check_once(app):
    from .extensions import db
    from .models import Camera
    from .stream import manager
    from . import events, alert

    with app.app_context():
        now = datetime.utcnow()
        threshold = now - timedelta(seconds=OFFLINE_THRESHOLD_SEC)
        cams = Camera.query.filter_by(enabled=True).all()
        for cam in cams:
            ws = manager.get_by_camera(cam.id)
            online = bool(ws and ws[1].alive and not ws[1].error)
            if online:
                # 在线：清掉告警标记（恢复连接也是一种正面事件）
                with _lock:
                    if cam.id in _alerted:
                        _alerted.discard(cam.id)
                        try:
                            events.publish("camera_online", {
                                "id": cam.id, "name": cam.name, "location": cam.location or "",
                                "time": now.isoformat() + "Z",
                            })
                        except Exception:
                            pass
                continue

            # 不在线：是否需要告警？
            last = cam.last_online_at
            # 只对"曾经在线、但最近停止心跳"的摄像头发告警
            if not last:
                continue  # 从未上线（用户从未点开始），不算"掉线"
            if last < threshold:
                # 心跳停了 > 阈值，确认离线
                with _lock:
                    if cam.id in _alerted:
                        continue
                    _alerted.add(cam.id)
                # SSE 广播 + 报警推送
                try:
                    events.publish("camera_offline", {
                        "id": cam.id, "name": cam.name, "location": cam.location or "",
                        "lastOnline": last.isoformat() + "Z",
                        "time": now.isoformat() + "Z",
                    })
                except Exception:
                    pass
                try:
                    cfg = alert.get_config()
                    if cfg.get("enabled") and cfg.get("webhook"):
                        text = (
                            "📡【摄像头离线告警】\n"
                            f"摄像头：{cam.name}\n"
                            f"位置：{cam.location or '未设置'}\n"
                            f"最后心跳：{last.strftime('%Y-%m-%d %H:%M:%S')} (UTC)\n"
                            "请检查网络/电源/RTSP 凭据。"
                        )
                        # 直接调底层 _send；不走冷却（运维告警优先）
                        alert._send(cfg["channel"], cfg["webhook"], text)
                except Exception:
                    pass


def _loop(app):
    while not _stop.is_set():
        try:
            _check_once(app)
        except Exception:
            pass
        _stop.wait(LOOP_INTERVAL_SEC)


def start(app):
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(app,), daemon=True, name="health-watcher")
    _thread.start()


def stop():
    _stop.set()
