"""报表蓝图。

  GET  /api/reports/summary?start=YYYY-MM-DD&end=YYYY-MM-DD   汇总 JSON
  GET  /api/reports/pdf?start=&end=                            下载 PDF 报表
  GET  /api/reports/safety_score?period=day|week              工地安全指数
  GET  /api/reports/heatmap?type=hour|camera                  违规热力图矩阵
  POST /api/reports/ai_summary                                AI 生成自然语言报告
"""
import io
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from ..extensions import db
from ..models import DetectionRecord, Camera
from .. import report

bp_reports = Blueprint("reports", __name__)


@bp_reports.get("/summary")
@jwt_required()
def summary():
    data = report.build_summary(request.args.get("start", ""), request.args.get("end", ""))
    return jsonify({"code": 200, "summary": data})


@bp_reports.get("/pdf")
@jwt_required()
def pdf():
    data = report.build_summary(request.args.get("start", ""), request.args.get("end", ""))
    pdf_bytes = report.build_pdf(data)
    filename = f"工地安防报表_{data['start']}_{data['end']}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


# ======================== 安全指数 ========================

def _score_for_range(start: datetime, end: datetime) -> dict:
    """根据某个时间段算 0~100 的安全分。"""
    q = DetectionRecord.query.filter(
        DetectionRecord.created_at >= start,
        DetectionRecord.created_at < end,
    )
    counts = {}
    for r, n in (
        db.session.query(DetectionRecord.risk_level, func.count())
        .filter(DetectionRecord.created_at >= start,
                DetectionRecord.created_at < end)
        .group_by(DetectionRecord.risk_level).all()
    ):
        counts[r] = n
    high = counts.get("high", 0)
    mid = counts.get("mid", 0)
    low = counts.get("low", 0)
    total = q.count()
    processed = q.filter(DetectionRecord.status.in_(["processed", "closed"])).count()
    pending = total - processed

    # 算分逻辑（基础 100）
    score = 100.0
    score -= min(40, high * 8)     # 高危每条 -8，最多 -40
    score -= min(20, mid * 3)      # 中危每条 -3，最多 -20
    score -= min(15, pending * 2)  # 未处理每条 -2，最多 -15
    if total > 0:
        score += (processed / total) * 5  # 处理率奖励 0~+5
    score = max(0, min(100, round(score, 1)))

    if score >= 95:
        grade, gradeColor = "优秀", "success"
    elif score >= 85:
        grade, gradeColor = "良好", ""
    elif score >= 70:
        grade, gradeColor = "警告", "warning"
    else:
        grade, gradeColor = "危险", "danger"

    return {
        "score": score,
        "grade": grade,
        "gradeColor": gradeColor,
        "components": {
            "high": high, "mid": mid, "low": low,
            "total": total, "processed": processed, "pending": pending,
        },
    }


@bp_reports.get("/safety_score")
@jwt_required()
def safety_score():
    period = request.args.get("period", "day")
    now = datetime.utcnow()
    if period == "week":
        end = now
        start = now - timedelta(days=7)
        trend_days = 8
    else:
        end = datetime(now.year, now.month, now.day) + timedelta(days=1)
        start = datetime(now.year, now.month, now.day)
        trend_days = 8
    current = _score_for_range(start, end)

    # 7 天趋势（按天）
    trend = []
    today_d = datetime(now.year, now.month, now.day)
    for i in range(trend_days - 1, -1, -1):
        d = today_d - timedelta(days=i)
        s = _score_for_range(d, d + timedelta(days=1))
        trend.append({"date": d.strftime("%m-%d"), "score": s["score"], "grade": s["grade"]})

    return jsonify({
        "code": 200,
        "period": period,
        **current,
        "trend": trend,
    })


# ======================== 违规热力图 ========================

CLASS_NAMES = ["反光衣", "跌倒", "未戴安全帽", "安全帽", "打电话", "吸烟"]


@bp_reports.get("/heatmap")
@jwt_required()
def heatmap():
    """type=hour 返回 24×6 (小时×类别) ; type=camera 返回 摄像头×类别。"""
    import json as _json
    htype = request.args.get("type", "hour")
    days = int(request.args.get("days", 30))
    since = datetime.utcnow() - timedelta(days=days)

    if htype == "camera":
        cams = Camera.query.all()
        cam_names = [c.name for c in cams]
        # 简化：没有 record→camera 的外键，按 record.record_type 与 camera 名匹配是不靠谱的
        # 这里按 records 的 cls_list × camera 数量近似：暂用 类别 × 来源类型 (img/video/camera)
        # 真正按摄像头维度需要在 records 加 camera_id，留作未来
        # 改为：类别 × 来源类型矩阵
        TYPES = ["img", "video", "camera"]
        TYPES_ZH = ["图片", "视频", "实时"]
        matrix = [[0] * len(CLASS_NAMES) for _ in TYPES]
        rows = db.session.query(
            DetectionRecord.record_type, DetectionRecord.cls_list_json
        ).filter(DetectionRecord.created_at >= since).all()
        for rec_type, raw in rows:
            try:
                cls_list = _json.loads(raw or "[]")
            except Exception:
                continue
            if rec_type not in TYPES:
                continue
            ti = TYPES.index(rec_type)
            for c in cls_list:
                if c in CLASS_NAMES:
                    matrix[ti][CLASS_NAMES.index(c)] += 1
        return jsonify({
            "code": 200,
            "type": htype,
            "xLabels": CLASS_NAMES,
            "yLabels": TYPES_ZH,
            "data": [[x, y, matrix[y][x]] for y in range(len(TYPES)) for x in range(len(CLASS_NAMES))],
        })

    # hour x class
    matrix = [[0] * len(CLASS_NAMES) for _ in range(24)]
    rows = db.session.query(
        DetectionRecord.created_at, DetectionRecord.cls_list_json
    ).filter(DetectionRecord.created_at >= since).all()
    for ts, raw in rows:
        try:
            cls_list = _json.loads(raw or "[]")
        except Exception:
            continue
        # 转北京时间小时（UTC+8）
        local_hour = (ts.hour + 8) % 24 if ts else 0
        for c in cls_list:
            if c in CLASS_NAMES:
                matrix[local_hour][CLASS_NAMES.index(c)] += 1

    return jsonify({
        "code": 200,
        "type": htype,
        "xLabels": CLASS_NAMES,
        "yLabels": [f"{h:02d}:00" for h in range(24)],
        "data": [[x, y, matrix[y][x]] for y in range(24) for x in range(len(CLASS_NAMES))],
    })


# ======================== AI 智能日报 ========================

@bp_reports.post("/ai_summary")
@jwt_required()
def ai_summary():
    """LLM 根据时段数据生成自然语言报告。"""
    import json as _json
    from collections import Counter
    from .. import llm

    body = request.get_json(silent=True) or {}
    period = body.get("period", "day")  # day | week
    now = datetime.utcnow()
    if period == "week":
        end_dt = now
        start_dt = now - timedelta(days=7)
        period_zh = "近 7 天"
    else:
        start_dt = datetime(now.year, now.month, now.day)
        end_dt = start_dt + timedelta(days=1)
        period_zh = "今日"

    q = DetectionRecord.query.filter(
        DetectionRecord.created_at >= start_dt,
        DetectionRecord.created_at < end_dt,
    )
    total = q.count()
    if total == 0:
        return jsonify({
            "code": 200,
            "period": period,
            "data": {
                "summary": f"{period_zh}内未检出任何违规事件，现场整体安全。",
                "highlights": ["无违规告警"],
                "recommendations": ["继续保持当前管控强度", "巡查保持频度"],
                "outlook": "无重点关注事项",
            },
            "raw_stats": {"total": 0},
            "generated": False,
        })

    # 风险分级
    risk_counts = dict(
        db.session.query(DetectionRecord.risk_level, func.count())
        .filter(DetectionRecord.created_at >= start_dt,
                DetectionRecord.created_at < end_dt)
        .group_by(DetectionRecord.risk_level).all()
    )
    high = risk_counts.get("high", 0)
    mid = risk_counts.get("mid", 0)
    low = risk_counts.get("low", 0)
    processed = q.filter(DetectionRecord.status.in_(["processed", "closed"])).count()
    pending = total - processed

    # 高发类别
    cls_counter = Counter()
    for (raw,) in db.session.query(DetectionRecord.cls_list_json).filter(
        DetectionRecord.created_at >= start_dt,
        DetectionRecord.created_at < end_dt,
    ).all():
        try:
            for c in _json.loads(raw or "[]"):
                cls_counter[c] += 1
        except Exception:
            pass
    top_classes = "、".join([f"{c}({n})" for c, n in cls_counter.most_common(5)]) or "—"

    # 高发时段（按北京时间小时聚合）
    hour_counter = Counter()
    for (ts,) in db.session.query(DetectionRecord.created_at).filter(
        DetectionRecord.created_at >= start_dt,
        DetectionRecord.created_at < end_dt,
    ).all():
        local_h = (ts.hour + 8) % 24  # UTC+8
        hour_counter[local_h] += 1
    peak_hours = "、".join([f"{h:02d}:00({n})" for h, n in hour_counter.most_common(3)]) or "—"

    # 安全指数（重用之前的算法）
    score_data = _score_for_range(start_dt, end_dt)

    data = {
        "period_zh": period_zh,
        "start": start_dt.strftime("%Y-%m-%d %H:%M"),
        "end": end_dt.strftime("%Y-%m-%d %H:%M"),
        "total": total, "high": high, "mid": mid, "low": low,
        "processed": processed, "pending": pending,
        "score": score_data["score"], "grade": score_data["grade"],
        "top_classes": top_classes, "peak_hours": peak_hours,
    }

    res = llm.summarize_report(data)
    if not res.get("ok"):
        return jsonify({"code": 503, "msg": res.get("msg", "AI 报告生成失败")}), 503

    return jsonify({
        "code": 200,
        "period": period,
        "data": {
            "summary": res["summary"],
            "highlights": res["highlights"],
            "recommendations": res["recommendations"],
            "outlook": res["outlook"],
        },
        "raw_stats": data,
        "generated": True,
        "model": res.get("model"),
    })
