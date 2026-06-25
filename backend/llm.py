"""视觉大模型复核客户端（YOLO 的第二重保险）。

把违规截图 + YOLO 命中的类别交给视觉大模型，让它：
  1) 二次确认是否真的存在该安全隐患（降低 YOLO 误报）；
  2) 用自然语言描述画面；
  3) 给出整改建议。

走 OpenAI 兼容的 chat/completions 接口，通义千问 Qwen-VL 与智谱 GLM-4V 都支持。
未配置 API Key 时返回 ok=False + 友好提示，不抛异常。
"""
import base64
import json
import re

import requests
from flask import current_app


def _preferred_provider_from_db():
    """从 Settings 读偏好的 LLM 服务商配置;无则返回 None。"""
    try:
        from .models import Setting
        pref_id = Setting.get("llm_preferred_id", "")
        if not pref_id:
            return None
        raw = Setting.get("llm_providers", "")
        if not raw:
            return None
        providers = json.loads(raw)
        for p in providers:
            if p.get("id") == pref_id and p.get("api_key"):
                return p
    except Exception:
        return None
    return None


def is_configured() -> bool:
    if _preferred_provider_from_db():
        return True
    return bool(current_app.config.get("LLM_API_KEY"))


def _resolve():
    """优先用 DB 偏好的服务商;否则回落到环境变量。"""
    cfg = current_app.config
    db_pref = _preferred_provider_from_db()
    if db_pref:
        provider = db_pref.get("provider", "qwen")
        defaults = cfg.get("LLM_DEFAULTS", {}).get(provider, {})
        base_url = db_pref.get("base_url") or defaults.get("base_url")
        model = db_pref.get("model") or defaults.get("model")
        return provider, base_url, model, db_pref.get("api_key"), cfg.get("LLM_TIMEOUT", 60)
    # fallback: 环境变量
    provider = cfg.get("LLM_PROVIDER", "qwen")
    defaults = cfg.get("LLM_DEFAULTS", {}).get(provider, {})
    base_url = cfg.get("LLM_BASE_URL") or defaults.get("base_url")
    model = cfg.get("LLM_MODEL") or defaults.get("model")
    return provider, base_url, model, cfg.get("LLM_API_KEY"), cfg.get("LLM_TIMEOUT", 60)


def _image_to_data_url(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64," + base64.b64encode(image_bytes).decode()


def ping() -> tuple:
    """轻量探活:返回 (ok, msg)。Settings 页面的"测试连接"按钮用。"""
    if not is_configured():
        return False, "未配置 API Key"
    provider, base_url, model, api_key, timeout = _resolve()
    text_model = current_app.config.get("LLM_TEXT_MODEL") or _text_model_for(provider)
    try:
        r = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": text_model,
                  "messages": [{"role": "user", "content": "ping"}],
                  "max_tokens": 4, "temperature": 0},
            timeout=min(timeout, 15),
        )
        if r.status_code == 200:
            return True, f"已连通 · 模型 {text_model}"
        return False, f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return False, str(e)[:200]


PROMPT = (
    "你是智慧社区物业管理专家。这是一张社区监控画面,YOLO 检测模型初步识别出: "
    "{classes}。请你结合画面二次研判,并严格以 JSON 返回,键固定为: "
    '{{"confirmed": true/false, "description": "一句话描述画面情况", "advice": "物业处置建议"}}。'
    "confirmed 表示是否确实存在违规(如违停/乱丢垃圾/宠物闯入/电瓶车违规/明火等);"
    "若画面正常或检测有误则为 false。只返回 JSON,不要多余文字。"
)


def _parse_json(text: str) -> dict:
    """从模型输出里抽出 JSON。"""
    if not text:
        return {}
    # 去掉可能的 ```json 包裹
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"description": text.strip()}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"description": text.strip()}


def review(image_bytes: bytes, cls_list: list) -> dict:
    """对一张截图做大模型复核。返回 dict：

    成功： {ok, confirmed, description, advice, model}
    失败/未配置： {ok: False, msg}
    """
    if not is_configured():
        return {"ok": False, "msg": "未配置大模型 API Key，请在后端环境变量 LLM_API_KEY 中填写后重启"}

    provider, base_url, model, api_key, timeout = _resolve()
    classes = "、".join(cls_list) if cls_list else "未提供具体类别"
    data_url = _image_to_data_url(image_bytes)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT.format(classes=classes)},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {"ok": False, "msg": f"大模型接口返回 {resp.status_code}：{resp.text[:200]}"}
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):  # 个别实现返回分段
            content = "".join(seg.get("text", "") for seg in content if isinstance(seg, dict))
        parsed = _parse_json(content)
        return {
            "ok": True,
            "confirmed": bool(parsed.get("confirmed", True)),
            "description": parsed.get("description", "").strip(),
            "advice": parsed.get("advice", "").strip(),
            "model": model,
        }
    except requests.Timeout:
        return {"ok": False, "msg": "大模型接口超时，请稍后重试"}
    except Exception as e:
        return {"ok": False, "msg": f"大模型调用失败：{e}"}


# ==================== 文本摘要（写日报）====================

REPORT_PROMPT = """你是智慧社区物业运营助手。请根据下面这份社区物业{period_zh}数据,写一份**专业、克制、有可执行建议**的社区运行报告。

【数据摘要】
- 时段:{start} 至 {end}
- 总告警:{total} 起(高危 {high} · 中危 {mid} · 低危 {low})
- 处理情况:已处理 {processed} 起,未处理 {pending} 起
- 社区安全指数:{score}/100({grade})
- 高发违规类别(按次数):{top_classes}
- 高发时段:{peak_hours}

【输出要求】
严格以 JSON 返回，键固定为：
{{
  "summary": "1-2 句总体评价",
  "highlights": ["关键发现 1", "关键发现 2", "关键发现 3"],
  "recommendations": ["可执行建议 1", "可执行建议 2", "可执行建议 3"],
  "outlook": "下阶段重点关注事项"
}}

要求：语气专业克制；不要堆砌数字（数字已在数据里）；建议要具体可执行，不要空话套话。只返回 JSON，不要任何额外说明。"""


def summarize_report(data: dict) -> dict:
    """根据汇总数据让 LLM 写一份自然语言报告。

    data 字段：period_zh / start / end / total / high / mid / low /
               processed / pending / score / grade / top_classes / peak_hours
    返回：{ok, summary, highlights, recommendations, outlook} 或 {ok:False, msg}
    """
    if not is_configured():
        return {"ok": False, "msg": "未配置大模型 API Key"}

    provider, base_url, model, api_key, timeout = _resolve()
    text_model = current_app.config.get("LLM_TEXT_MODEL") or _text_model_for(provider)

    prompt = REPORT_PROMPT.format(**data)
    payload = {
        "model": text_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload, headers=headers, timeout=timeout,
        )
        if resp.status_code != 200:
            return {"ok": False, "msg": f"大模型返回 {resp.status_code}：{resp.text[:200]}"}
        content = resp.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(seg.get("text", "") for seg in content if isinstance(seg, dict))
        parsed = _parse_json(content)
        return {
            "ok": True,
            "summary": parsed.get("summary", ""),
            "highlights": parsed.get("highlights", []),
            "recommendations": parsed.get("recommendations", []),
            "outlook": parsed.get("outlook", ""),
            "model": text_model,
        }
    except requests.Timeout:
        return {"ok": False, "msg": "大模型接口超时"}
    except Exception as e:
        return {"ok": False, "msg": f"大模型调用失败：{e}"}


# ==================== 告警紧急度分级 ====================

TRIAGE_PROMPT = (
    "你是社区物业紧急响应分析师。这张小区监控截图里,YOLO 初步检出: {classes}。"
    "请综合考虑:是否消防隐患(明火/电瓶车进电梯)/老人摔倒/儿童危险/邻里冲突,"
    "判断**该告警的紧急程度**。"
    '严格以 JSON 返回:{{"urgency": "immediate|high|normal|low", "reason": "30字内中文原因"}}。'
    "规则:immediate=可能立即造成伤亡或火灾;high=多人违规或重要安保;normal=一般违规;low=远处或轻微。"
    "只返回 JSON。"
)


def triage_alert(image_bytes: bytes, cls_list: list) -> dict:
    """对一张违规截图做紧急度分级。返回 {ok, urgency, reason} 或 {ok:False, msg}。"""
    if not is_configured():
        return {"ok": False, "msg": "未配置大模型"}

    provider, base_url, model, api_key, timeout = _resolve()
    classes = "、".join(cls_list) or "未知"
    data_url = _image_to_data_url(image_bytes)

    payload = {
        "model": model,  # 看图必须用视觉模型
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": TRIAGE_PROMPT.format(classes=classes)},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload, headers=headers, timeout=timeout,
        )
        if resp.status_code != 200:
            return {"ok": False, "msg": f"HTTP {resp.status_code}"}
        content = resp.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(seg.get("text", "") for seg in content if isinstance(seg, dict))
        parsed = _parse_json(content)
        urgency = parsed.get("urgency", "normal")
        if urgency not in ("immediate", "high", "normal", "low"):
            urgency = "normal"
        return {
            "ok": True,
            "urgency": urgency,
            "reason": (parsed.get("reason") or "").strip()[:100],
        }
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ==================== 安全场景兜底复核(YOLO 无检测时触发)====================

SAFETY_REVIEW_PROMPT = (
    "你是社区物业 AI 巡检员。这张小区监控图,YOLO + 姿态检测器**未发现违规**。"
    "请仔细看图,凭你的世界知识判断:**实际上是否真的没有问题?**"
    "重点检查检测器容易漏识的:"
    "1) **姿态行为类**(关键!): 翻越围栏/墙、攀爬、跌倒、打架斗殴、剧烈推搡、可疑攀附;"
    "2) 被遮挡或半身的人/车/动物;"
    "3) 倒地不动的老人/儿童;"
    "4) 小物体如烟头/小垃圾/小动物;"
    "5) 异常聚集/可疑徘徊/盯梢;"
    "6) 远处的明火/烟雾/积水/堆放物。"
    "\\n严格以 JSON 返回:"
    '{"truly_safe": true/false, "found_objects": ["发现的物体/姿态/隐患 1", "..."], '
    '"description": "20-50 字场景描述", "advice": "30 字内物业建议(如真安全可写\\"暂无需处置\\")"}。'
    "只返回 JSON。"
)


def safety_review(image_bytes: bytes) -> dict:
    """YOLO 无检测时,让 LLM 用世界知识"巡检"画面,补 YOLO 盲区。

    返回:
      成功:{ok, truly_safe, found_objects, description, advice, model}
      失败:{ok:False, msg}
    """
    if not is_configured():
        return {"ok": False, "msg": "未配置大模型 API Key"}

    provider, base_url, model, api_key, timeout = _resolve()
    data_url = _image_to_data_url(image_bytes)

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": SAFETY_REVIEW_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload, headers=headers, timeout=timeout,
        )
        if resp.status_code != 200:
            return {"ok": False, "msg": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        content = resp.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(seg.get("text", "") for seg in content if isinstance(seg, dict))
        parsed = _parse_json(content)
        return {
            "ok": True,
            "truly_safe": bool(parsed.get("truly_safe", True)),
            "found_objects": parsed.get("found_objects", [])[:10],
            "description": (parsed.get("description") or "").strip()[:150],
            "advice": (parsed.get("advice") or "").strip()[:100],
            "model": model,
        }
    except requests.Timeout:
        return {"ok": False, "msg": "大模型超时"}
    except Exception as e:
        return {"ok": False, "msg": f"大模型调用失败: {e}"}


def _text_model_for(provider: str) -> str:
    """各厂商的纯文本模型默认值(写日报时用,比视觉模型便宜)。"""
    return {
        "qwen": "qwen-plus",
        "zhipu": "glm-4-flash",
    }.get(provider, "qwen-plus")


# ==================== AI 物业工单生成 ====================

WORK_ORDER_PROMPT = """你是智慧社区物业调度助手。一起社区违规事件已发生,请基于以下信息生成一份**可执行的物业工单**。

【事件信息】
- 业务类型:{violation_zh}
- 检测对象:{cls_list}
- 触发原因:{reason}
- 摄像头位置:{camera_location}
- 安装类型:{location_type_zh}
- 发生时间:{occur_time}

【输出要求】
严格返回 JSON,字段固定:
{{
  "title": "工单标题(不超过 20 字,如'1 号楼电梯电瓶车告警')",
  "assignee_role": "执行人角色(从这些里选:安保员/保洁员/物业经理/维修工/园林工)",
  "priority": "优先级(immediate/high/normal/low)",
  "summary": "1-2 句情况说明(给执行人快速理解)",
  "actions": ["执行步骤 1", "执行步骤 2", "执行步骤 3"],
  "expected": "处置后的期望结果(可验证)",
  "timeframe": "完成时限(如'15 分钟内''当日 18:00 前')",
  "notify_owner": true/false
}}

要求:
- title 要简洁、有定位信息
- actions 必须可操作、有顺序(进入现场 → 沟通/取证 → 处置 → 复核)
- timeframe 与 priority 匹配(immediate≤15分钟、high≤1小时、normal≤4小时、low≤当日)
- notify_owner:涉及业主家车辆/财产/家人安全才为 true
- 只返回 JSON,不要任何额外文字"""


def generate_work_order(record_data: dict) -> dict:
    """根据违规记录生成可执行物业工单。

    record_data 字段:
      violation_zh / cls_list / reason / camera_location / location_type_zh / occur_time

    返回:{ok, title, assignee_role, priority, summary, actions, expected, timeframe, notify_owner}
        或 {ok:False, msg}
    """
    if not is_configured():
        return {"ok": False, "msg": "未配置大模型 API Key"}

    provider, base_url, model, api_key, timeout = _resolve()
    text_model = current_app.config.get("LLM_TEXT_MODEL") or _text_model_for(provider)

    prompt = WORK_ORDER_PROMPT.format(**record_data)
    payload = {
        "model": text_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload, headers=headers, timeout=timeout,
        )
        if resp.status_code != 200:
            return {"ok": False, "msg": f"大模型返回 {resp.status_code}: {resp.text[:200]}"}
        content = resp.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(seg.get("text", "") for seg in content if isinstance(seg, dict))
        parsed = _parse_json(content)
        return {
            "ok": True,
            "title": parsed.get("title", "")[:50],
            "assignee_role": parsed.get("assignee_role", "物业经理"),
            "priority": parsed.get("priority", "normal"),
            "summary": parsed.get("summary", ""),
            "actions": parsed.get("actions", []),
            "expected": parsed.get("expected", ""),
            "timeframe": parsed.get("timeframe", ""),
            "notify_owner": bool(parsed.get("notify_owner", False)),
            "model": text_model,
        }
    except requests.Timeout:
        return {"ok": False, "msg": "大模型接口超时"}
    except Exception as e:
        return {"ok": False, "msg": f"大模型调用失败: {e}"}
