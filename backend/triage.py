"""告警智能分级 —— 后台线程调用 LLM 看图、给紧急度，再决定是否真推送。

启用门控：Setting('triage_enabled') = '1' 才跑。默认关（避免初始 LLM 费用失控）。

流程：
  1. records.create / stream._maybe_snap 创建高危记录后，调 schedule()
  2. 后台线程读截图 → 调 llm.triage_alert
  3. 写回 record.urgency / urgency_reason / urgency_at
  4. 广播一次 record_updated 事件（前端可刷新该行）
  5. 仅当 urgency in (immediate, high) 且 alert.enabled 时才推送钉钉/企微
"""
import os
import threading
from datetime import datetime

from .models import Setting


def is_enabled() -> bool:
    return Setting.get("triage_enabled", "0") == "1"


def schedule(app, record_id: int):
    """后台线程异步分级。失败静默。"""
    if not is_enabled():
        return
    threading.Thread(
        target=_run,
        args=(app, record_id),
        daemon=True,
        name=f"triage-{record_id}",
    ).start()


def _run(app, record_id: int):
    try:
        with app.app_context():
            from .extensions import db
            from .models import DetectionRecord
            from . import llm, alert, events as _events
            from flask import current_app

            rec = db.session.get(DetectionRecord, record_id)
            if not rec or not rec.image_path:
                return
            img_file = os.path.join(current_app.config["SNAPSHOT_DIR"], rec.image_path)
            if not os.path.exists(img_file):
                return

            with open(img_file, "rb") as f:
                img_bytes = f.read()

            result = llm.triage_alert(img_bytes, rec.cls_list)
            if not result.get("ok"):
                return

            rec.urgency = result["urgency"]
            rec.urgency_reason = result["reason"]
            rec.urgency_at = datetime.utcnow()
            db.session.commit()

            # 广播给前端：让记录页面刷新该条
            try:
                _events.publish("record_updated", {
                    "id": rec.id,
                    "urgency": rec.urgency,
                    "urgencyZh": DetectionRecord.URGENCY_ZH.get(rec.urgency, ""),
                    "urgencyReason": rec.urgency_reason,
                })
            except Exception:
                pass

            # 仅在 immediate/high 时触发推送
            if rec.urgency in ("immediate", "high") and rec.risk_level == "high":
                alert.notify_async(current_app._get_current_object(), rec.id)
    except Exception:
        pass
