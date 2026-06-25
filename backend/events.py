"""进程内 SSE 事件总线：高危告警实时推送给所有已订阅的浏览器。

简单的发布-订阅：每个 SSE 连接持有一个队列，publish 会广播到所有订阅者。
仅适用于单进程开发/小规模部署；多进程要换 Redis Pub/Sub。
"""
import json
import queue
import threading

_subs: list[queue.Queue] = []
_lock = threading.Lock()


def subscribe() -> queue.Queue:
    q = queue.Queue(maxsize=100)
    with _lock:
        _subs.append(q)
    return q


def unsubscribe(q: queue.Queue):
    with _lock:
        try:
            _subs.remove(q)
        except ValueError:
            pass


def publish(event_type: str, data) -> None:
    msg = json.dumps({"type": event_type, "data": data}, ensure_ascii=False, default=str)
    with _lock:
        for q in list(_subs):
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass  # 慢消费者丢弃，避免阻塞生产端
