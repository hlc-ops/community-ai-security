"""系统设置蓝图：报警推送、品牌、告警声音、灵敏度（按需仅管理员）。

  GET  /api/settings/alert            读取报警配置（管理员）
  PUT  /api/settings/alert            保存报警配置
  POST /api/settings/alert/test       测试发送
  GET  /api/settings/brand            读取品牌信息（公开，登录页用）
  PUT  /api/settings/brand            保存品牌（管理员）
  POST /api/settings/brand/logo       上传 logo（管理员）
  GET  /api/settings/alert_sound      读取自定义告警音 URL（登录后）
  POST /api/settings/alert_sound      上传 mp3/wav（管理员）
  DEL  /api/settings/alert_sound      清除自定义音
  GET  /api/settings/class_confs      读取按类别灵敏度（管理员）
  PUT  /api/settings/class_confs      保存按类别灵敏度
"""
import json
import os
import time
import uuid
from functools import wraps

from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt

from ..extensions import db
from ..models import Setting
from .. import alert

bp_settings = Blueprint("settings", __name__)


CLASS_NAMES = ["反光衣", "跌倒", "未戴安全帽", "安全帽", "打电话", "吸烟"]
DEFAULT_CLASS_CONF = 0.5

ALLOWED_LOGO_EXT = {"png", "jpg", "jpeg", "svg", "webp"}
ALLOWED_AUDIO_EXT = {"mp3", "wav", "ogg", "m4a"}


def _uploads_dir() -> str:
    d = os.path.join(current_app.config["DATA_DIR"], "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        if get_jwt().get("role") != "admin":
            return jsonify({"code": 403, "msg": "仅管理员可操作"}), 403
        return fn(*args, **kwargs)
    return wrapper


@bp_settings.get("/alert")
@admin_required
def get_alert():
    cfg = alert.get_config()
    return jsonify({"code": 200, "config": cfg})


@bp_settings.put("/alert")
@admin_required
def put_alert():
    data = request.get_json(silent=True) or {}
    Setting.put("alert_enabled", "1" if data.get("enabled") else "0")
    Setting.put("alert_channel", data.get("channel", "dingtalk"))
    Setting.put("alert_webhook", (data.get("webhook") or "").strip())
    Setting.put("alert_cooldown", int(data.get("cooldown") or 30))
    db.session.commit()
    from .. import audit
    audit.log("setting.alert", "setting", "alert",
              f"enabled={bool(data.get('enabled'))} channel={data.get('channel')}")
    return jsonify({"code": 200, "msg": "已保存", "config": alert.get_config()})


@bp_settings.post("/alert/test")
@admin_required
def test_alert():
    data = request.get_json(silent=True) or {}
    channel = data.get("channel", "dingtalk")
    webhook = (data.get("webhook") or "").strip()
    if not webhook:
        return jsonify({"code": 400, "msg": "请先填写 Webhook 地址"}), 400
    ok, msg = alert.send_test(channel, webhook)
    if ok:
        return jsonify({"code": 200, "msg": "测试消息已发送，请查看群消息"})
    return jsonify({"code": 502, "msg": f"发送失败：{msg}"}), 502


# ======================== 品牌定制 ========================

def _brand_config() -> dict:
    return {
        "name": Setting.get("brand_name", "工地安防预警系统"),
        "subtitle": Setting.get("brand_subtitle", "基于深度学习的智能工地安防违规识别平台"),
        "logoUrl": Setting.get("brand_logo_url", ""),
    }


@bp_settings.get("/brand")
def get_brand():
    """登录页要用，无需鉴权。"""
    return jsonify({"code": 200, "config": _brand_config()})


@bp_settings.put("/brand")
@admin_required
def put_brand():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:64]
    sub = (data.get("subtitle") or "").strip()[:128]
    if name:
        Setting.put("brand_name", name)
    if "subtitle" in data:
        Setting.put("brand_subtitle", sub)
    if "logoUrl" in data:
        Setting.put("brand_logo_url", (data.get("logoUrl") or "").strip())
    db.session.commit()
    from .. import audit
    audit.log("setting.brand", "setting", "brand", f"name={name}")
    return jsonify({"code": 200, "msg": "已保存", "config": _brand_config()})


@bp_settings.post("/brand/logo")
@admin_required
def upload_logo():
    file = request.files.get("logo")
    if not file:
        return jsonify({"code": 400, "msg": "未上传文件"}), 400
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in ALLOWED_LOGO_EXT:
        return jsonify({"code": 400, "msg": f"仅支持 {', '.join(ALLOWED_LOGO_EXT)}"}), 400
    fname = f"logo_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
    path = os.path.join(_uploads_dir(), fname)
    file.save(path)
    if os.path.getsize(path) > 2 * 1024 * 1024:
        os.remove(path)
        return jsonify({"code": 400, "msg": "Logo 需 < 2MB"}), 400
    url = f"/api/uploads/{fname}"
    Setting.put("brand_logo_url", url)
    db.session.commit()
    return jsonify({"code": 200, "logoUrl": url})


# ======================== 自定义告警声音 ========================

@bp_settings.get("/alert_sound")
@jwt_required()
def get_alert_sound():
    return jsonify({"code": 200, "url": Setting.get("alert_sound_url", "")})


@bp_settings.post("/alert_sound")
@admin_required
def upload_alert_sound():
    file = request.files.get("audio")
    if not file:
        return jsonify({"code": 400, "msg": "未上传文件"}), 400
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in ALLOWED_AUDIO_EXT:
        return jsonify({"code": 400, "msg": f"仅支持 {', '.join(ALLOWED_AUDIO_EXT)}"}), 400
    fname = f"alert_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
    path = os.path.join(_uploads_dir(), fname)
    file.save(path)
    if os.path.getsize(path) > 1 * 1024 * 1024:
        os.remove(path)
        return jsonify({"code": 400, "msg": "音频需 < 1MB"}), 400
    url = f"/api/uploads/{fname}"
    Setting.put("alert_sound_url", url)
    db.session.commit()
    return jsonify({"code": 200, "url": url})


@bp_settings.delete("/alert_sound")
@admin_required
def clear_alert_sound():
    Setting.put("alert_sound_url", "")
    db.session.commit()
    return jsonify({"code": 200, "msg": "已恢复内置蜂鸣声"})


# ======================== 按类别灵敏度 ========================

def _read_class_confs() -> dict:
    raw = Setting.get("class_confs", "")
    if not raw:
        return {n: DEFAULT_CLASS_CONF for n in CLASS_NAMES}
    try:
        d = json.loads(raw)
        return {n: float(d.get(n, DEFAULT_CLASS_CONF)) for n in CLASS_NAMES}
    except Exception:
        return {n: DEFAULT_CLASS_CONF for n in CLASS_NAMES}


@bp_settings.get("/class_confs")
@admin_required
def get_class_confs():
    return jsonify({"code": 200, "config": _read_class_confs()})


# ======================== 数据保留 + 系统健康 ========================

@bp_settings.get("/retention")
@admin_required
def get_retention():
    from .. import maintenance
    return jsonify({"code": 200, "config": maintenance.get_config()})


@bp_settings.put("/retention")
@admin_required
def put_retention():
    from .. import maintenance
    data = (request.get_json(silent=True) or {}).get("config") or {}
    maintenance.save_config(data)
    from .. import audit
    audit.log("setting.retention", "setting", "retention", str(data))
    return jsonify({"code": 200, "msg": "已保存", "config": maintenance.get_config()})


@bp_settings.post("/retention/run")
@admin_required
def run_cleanup_now():
    """立即跑一次清理。"""
    from flask import current_app
    from .. import maintenance
    stats = maintenance.cleanup_once(current_app._get_current_object())
    from .. import audit
    audit.log("setting.retention.run", "setting", "retention", str(stats))
    return jsonify({"code": 200, "msg": "清理完成", "stats": stats})


@bp_settings.get("/triage")
@admin_required
def get_triage():
    """AI 告警分级开关。"""
    return jsonify({"code": 200, "enabled": Setting.get("triage_enabled", "0") == "1"})


@bp_settings.put("/triage")
@admin_required
def put_triage():
    data = request.get_json(silent=True) or {}
    Setting.put("triage_enabled", "1" if data.get("enabled") else "0")
    db.session.commit()
    from .. import audit
    audit.log("setting.triage", "setting", "triage", f"enabled={bool(data.get('enabled'))}")
    return jsonify({"code": 200, "msg": "已保存", "enabled": data.get("enabled")})


@bp_settings.get("/auto_review")
@admin_required
def get_auto_review():
    """自动 LLM 安全复核开关(YOLO 空检测时触发)。"""
    return jsonify({"code": 200, "enabled": Setting.get("auto_review_enabled", "1") == "1"})


@bp_settings.put("/auto_review")
@admin_required
def put_auto_review():
    data = request.get_json(silent=True) or {}
    Setting.put("auto_review_enabled", "1" if data.get("enabled") else "0")
    db.session.commit()
    from .. import audit
    audit.log("setting.auto_review", "setting", "auto_review", f"enabled={bool(data.get('enabled'))}")
    return jsonify({"code": 200, "msg": "已保存", "enabled": data.get("enabled")})


# ======================== LLM 服务商管理(多供应商 + 偏好)========================

def _read_llm_providers() -> list:
    raw = Setting.get("llm_providers", "")
    if not raw:
        return []
    try:
        arr = json.loads(raw)
        return arr if isinstance(arr, list) else []
    except Exception:
        return []


def _mask_key(k: str) -> str:
    if not k:
        return ""
    if len(k) <= 8:
        return "***"
    return k[:4] + "*" * 6 + k[-4:]


def _public_providers(providers: list) -> list:
    """返回时 api_key 做 mask,前端只能看到关键末尾。"""
    return [
        {
            "id": p.get("id"),
            "name": p.get("name") or "",
            "provider": p.get("provider") or "qwen",
            "base_url": p.get("base_url") or "",
            "model": p.get("model") or "",
            "api_key_masked": _mask_key(p.get("api_key", "")),
            "has_key": bool(p.get("api_key")),
        }
        for p in providers
    ]


@bp_settings.get("/llm_providers")
@admin_required
def list_llm_providers():
    providers = _read_llm_providers()
    return jsonify({
        "code": 200,
        "providers": _public_providers(providers),
        "preferred_id": Setting.get("llm_preferred_id", ""),
        "supported": [
            {"provider": "qwen", "label": "通义千问 Qwen-VL",
             "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
             "default_model": "qwen-vl-plus"},
            {"provider": "zhipu", "label": "智谱 GLM-4V",
             "base_url": "https://open.bigmodel.cn/api/paas/v4",
             "default_model": "glm-4v-plus"},
            {"provider": "openai", "label": "OpenAI / 兼容接口",
             "base_url": "https://api.openai.com/v1",
             "default_model": "gpt-4o-mini"},
            {"provider": "doubao", "label": "豆包 Vision",
             "base_url": "https://ark.cn-beijing.volces.com/api/v3",
             "default_model": "doubao-1.5-vision-pro-32k"},
        ],
    })


@bp_settings.post("/llm_providers")
@admin_required
def create_llm_provider():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:64]
    provider = (data.get("provider") or "qwen").strip()[:32]
    base_url = (data.get("base_url") or "").strip()[:256]
    model = (data.get("model") or "").strip()[:64]
    api_key = (data.get("api_key") or "").strip()[:256]
    if not name:
        return jsonify({"code": 400, "msg": "请填写显示名称"}), 400
    if not api_key:
        return jsonify({"code": 400, "msg": "请填写 API Key"}), 400
    providers = _read_llm_providers()
    new_id = uuid.uuid4().hex[:12]
    providers.append({
        "id": new_id, "name": name, "provider": provider,
        "base_url": base_url, "model": model, "api_key": api_key,
    })
    Setting.put("llm_providers", json.dumps(providers, ensure_ascii=False))
    # 如果还没设过偏好,自动把第一个设为主用
    if not Setting.get("llm_preferred_id", ""):
        Setting.put("llm_preferred_id", new_id)
    db.session.commit()
    from .. import audit
    audit.log("setting.llm_provider.create", "setting", "llm_provider",
              f"name={name} provider={provider}")
    return jsonify({"code": 200, "msg": "已添加", "id": new_id})


@bp_settings.put("/llm_providers/<pid>")
@admin_required
def update_llm_provider(pid):
    data = request.get_json(silent=True) or {}
    providers = _read_llm_providers()
    target = next((p for p in providers if p.get("id") == pid), None)
    if not target:
        return jsonify({"code": 404, "msg": "服务商不存在"}), 404
    if "name" in data:
        target["name"] = (data.get("name") or "").strip()[:64] or target["name"]
    if "provider" in data:
        target["provider"] = (data.get("provider") or "qwen").strip()[:32]
    if "base_url" in data:
        target["base_url"] = (data.get("base_url") or "").strip()[:256]
    if "model" in data:
        target["model"] = (data.get("model") or "").strip()[:64]
    # api_key 仅在传了非空值时才覆盖,空串保留原值
    new_key = (data.get("api_key") or "").strip()
    if new_key:
        target["api_key"] = new_key[:256]
    Setting.put("llm_providers", json.dumps(providers, ensure_ascii=False))
    db.session.commit()
    from .. import audit
    audit.log("setting.llm_provider.update", "setting", "llm_provider", f"id={pid}")
    return jsonify({"code": 200, "msg": "已保存"})


@bp_settings.delete("/llm_providers/<pid>")
@admin_required
def delete_llm_provider(pid):
    providers = _read_llm_providers()
    new_list = [p for p in providers if p.get("id") != pid]
    if len(new_list) == len(providers):
        return jsonify({"code": 404, "msg": "服务商不存在"}), 404
    Setting.put("llm_providers", json.dumps(new_list, ensure_ascii=False))
    # 如果删的就是当前主用,清掉偏好
    if Setting.get("llm_preferred_id", "") == pid:
        Setting.put("llm_preferred_id", new_list[0]["id"] if new_list else "")
    db.session.commit()
    from .. import audit
    audit.log("setting.llm_provider.delete", "setting", "llm_provider", f"id={pid}")
    return jsonify({"code": 200, "msg": "已删除"})


@bp_settings.put("/llm_preferred")
@admin_required
def put_llm_preferred():
    data = request.get_json(silent=True) or {}
    pid = (data.get("id") or "").strip()
    providers = _read_llm_providers()
    if pid and not any(p.get("id") == pid for p in providers):
        return jsonify({"code": 404, "msg": "服务商不存在"}), 404
    Setting.put("llm_preferred_id", pid)
    db.session.commit()
    from .. import audit
    audit.log("setting.llm_preferred", "setting", "llm_preferred", f"id={pid}")
    return jsonify({"code": 200, "msg": "已设为主用"})


@bp_settings.post("/llm_providers/<pid>/test")
@admin_required
def test_llm_provider(pid):
    """跑一次轻量调用验证 key/url/model 是否可用。"""
    providers = _read_llm_providers()
    p = next((x for x in providers if x.get("id") == pid), None)
    if not p:
        return jsonify({"code": 404, "msg": "服务商不存在"}), 404
    # 临时把这家设成主用做一次最小请求
    old_pref = Setting.get("llm_preferred_id", "")
    try:
        Setting.put("llm_preferred_id", pid)
        db.session.commit()
        from .. import llm as _llm
        ok, msg = _llm.ping()
        return jsonify({"code": 200 if ok else 502, "ok": ok, "msg": msg})
    finally:
        Setting.put("llm_preferred_id", old_pref)
        db.session.commit()


@bp_settings.get("/pose")
@admin_required
def get_pose():
    """Pose 行为分析开关(摔倒/翻墙/打架/奔跑)。"""
    return jsonify({"code": 200, "enabled": Setting.get("pose_enabled", "0") == "1"})


@bp_settings.put("/pose")
@admin_required
def put_pose():
    data = request.get_json(silent=True) or {}
    Setting.put("pose_enabled", "1" if data.get("enabled") else "0")
    db.session.commit()
    from .. import audit
    audit.log("setting.pose", "setting", "pose", f"enabled={bool(data.get('enabled'))}")
    return jsonify({"code": 200, "msg": "已保存", "enabled": data.get("enabled")})


@bp_settings.get("/health")
@admin_required
def health_detail():
    from flask import current_app
    from .. import maintenance
    return jsonify({"code": 200, "metrics": maintenance.health_metrics(
        current_app._get_current_object())})


@bp_settings.put("/class_confs")
@admin_required
def put_class_confs():
    data = (request.get_json(silent=True) or {}).get("config") or {}
    cleaned = {}
    for n in CLASS_NAMES:
        v = data.get(n, DEFAULT_CLASS_CONF)
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = DEFAULT_CLASS_CONF
        cleaned[n] = max(0.05, min(0.95, v))
    Setting.put("class_confs", json.dumps(cleaned, ensure_ascii=False))
    db.session.commit()
    from .. import audit
    audit.log("setting.class_confs", "setting", "class_confs", "")
    return jsonify({"code": 200, "msg": "已保存", "config": cleaned})
