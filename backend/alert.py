"""报警推送：高危违规实时推到钉钉 / 企业微信群机器人。

配置存在 Setting 表里（系统设置页可在线改，无需重启）：
  alert_enabled   "1"/"0"
  alert_channel   "dingtalk" / "wecom"
  alert_webhook   群机器人 Webhook 地址
  alert_cooldown  两次推送最小间隔秒数（防刷屏），默认 30

群机器人只能发文本/markdown，发不了本地图片，所以推送文字告警（类型/风险/类别/时间）。
"""
import threading
import time

import requests
from flask import current_app

from .models import Setting

# 进程级冷却：上次发送时间戳
_last_sent = 0.0
_lock = threading.Lock()


def get_config() -> dict:
    return {
        "enabled": Setting.get("alert_enabled", "0") == "1",
        "channel": Setting.get("alert_channel", "dingtalk"),
        "webhook": Setting.get("alert_webhook", ""),
        "cooldown": int(Setting.get("alert_cooldown", "30") or 30),
    }


def _send(channel: str, webhook: str, text: str) -> tuple[bool, str]:
    """按渠道格式发送。返回 (ok, msg)。"""
    try:
        if channel == "wecom":
            payload = {"msgtype": "text", "text": {"content": text}}
        else:  # dingtalk
            payload = {"msgtype": "text", "text": {"content": text}}
        r = requests.post(webhook, json=payload, timeout=10)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {r.text[:150]}"
        data = r.json()
        # 钉钉 errcode==0 成功；企业微信 errcode==0 成功
        if data.get("errcode", 0) not in (0, None):
            return False, data.get("errmsg", str(data))
        return True, "ok"
    except Exception as e:
        return False, str(e)


def _send_image_wecom(webhook: str, image_bytes: bytes) -> tuple[bool, str]:
    """企业微信群机器人发图片消息（base64 + md5）。图片需 < 2MB。"""
    import base64
    import hashlib
    payload = {
        "msgtype": "image",
        "image": {
            "base64": base64.b64encode(image_bytes).decode(),
            "md5": hashlib.md5(image_bytes).hexdigest(),
        },
    }
    try:
        r = requests.post(webhook, json=payload, timeout=10)
        data = r.json()
        if r.status_code != 200 or data.get("errcode", 0) not in (0, None):
            return False, data.get("errmsg", r.text[:150])
        return True, "ok"
    except Exception as e:
        return False, str(e)


def send_test(channel: str, webhook: str) -> tuple[bool, str]:
    """系统设置页「测试发送」用，不受开关/冷却限制。"""
    return _send(channel, webhook, "【工地安防】测试消息：报警推送配置成功 ✅")


def notify_high_risk(record):
    """高危记录触发推送（在后台线程里调，不阻塞请求）。带开关与冷却。"""
    global _last_sent
    cfg = get_config()
    if not cfg["enabled"] or not cfg["webhook"]:
        return
    with _lock:
        now = time.time()
        if now - _last_sent < cfg["cooldown"]:
            return
        _last_sent = now

    cls = "、".join(record.cls_list) or "未知"
    when = record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else ""
    text = (
        "⚠️【工地安防·高危预警】\n"
        f"来源：{record.TYPE_ZH.get(record.record_type, record.record_type)}\n"
        f"违规类别：{cls}\n"
        f"风险等级：高危\n"
        f"时间：{when}\n"
        "请相关人员立即前往现场核实处理。"
    )
    ok, msg = _send(cfg["channel"], cfg["webhook"], text)
    if not ok:
        current_app.logger.warning("报警推送失败：%s", msg)

    # 企业微信再附一条违规截图（钉钉机器人不支持发本地图片）
    if cfg["channel"] == "wecom" and record.image_path:
        import os
        path = os.path.join(current_app.config["SNAPSHOT_DIR"], record.image_path)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    img = f.read()
                if len(img) < 2 * 1024 * 1024:
                    iok, imsg = _send_image_wecom(cfg["webhook"], img)
                    if not iok:
                        current_app.logger.warning("报警截图推送失败：%s", imsg)
            except Exception as e:
                current_app.logger.warning("读取报警截图失败：%s", e)


def notify_async(app, record_id):
    """在后台线程触发推送：独立 app 上下文里按 id 重新加载记录，避免脱离会话报错。"""
    def run():
        with app.app_context():
            from .extensions import db
            from .models import DetectionRecord
            rec = db.session.get(DetectionRecord, record_id)
            if rec:
                notify_high_risk(rec)

    threading.Thread(target=run, daemon=True).start()
