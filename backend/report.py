"""报表汇总与 PDF 生成。

用 reportlab 内置中文 CID 字体 STSong-Light，无需外部字体文件，中文不乱码。
"""
import io
import json
from datetime import datetime, timedelta

from sqlalchemy import func

from .extensions import db
from .models import DetectionRecord

RISK_ZH = {"high": "高危", "mid": "中危", "low": "低危"}
TYPE_ZH = {"img": "图片检测", "video": "视频检测", "camera": "实时检测"}


def _parse_date(s: str, default: datetime) -> datetime:
    if not s:
        return default
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return default


def build_summary(start: str = "", end: str = "") -> dict:
    """汇总 [start, end]（含端点，按日）区间内的检测数据。"""
    end_dt = _parse_date(end, datetime.utcnow())
    start_dt = _parse_date(start, end_dt - timedelta(days=6))
    lo = datetime(start_dt.year, start_dt.month, start_dt.day)
    hi = datetime(end_dt.year, end_dt.month, end_dt.day) + timedelta(days=1)

    q = DetectionRecord.query.filter(
        DetectionRecord.created_at >= lo, DetectionRecord.created_at < hi
    )

    total = q.count()
    by_risk = {RISK_ZH[k]: v for k, v in {"high": 0, "mid": 0, "low": 0}.items()}
    for r, cnt in (
        db.session.query(DetectionRecord.risk_level, func.count())
        .filter(DetectionRecord.created_at >= lo, DetectionRecord.created_at < hi)
        .group_by(DetectionRecord.risk_level).all()
    ):
        by_risk[RISK_ZH.get(r, r)] = cnt

    by_type = {}
    for t, cnt in (
        db.session.query(DetectionRecord.record_type, func.count())
        .filter(DetectionRecord.created_at >= lo, DetectionRecord.created_at < hi)
        .group_by(DetectionRecord.record_type).all()
    ):
        by_type[TYPE_ZH.get(t, t)] = cnt

    processed = q.filter(DetectionRecord.status == "processed").count()

    by_class = {}
    for (cls_json,) in q.with_entities(DetectionRecord.cls_list_json).all():
        try:
            for c in json.loads(cls_json or "[]"):
                by_class[c] = by_class.get(c, 0) + 1
        except Exception:
            pass

    return {
        "start": lo.strftime("%Y-%m-%d"),
        "end": (hi - timedelta(days=1)).strftime("%Y-%m-%d"),
        "total": total,
        "processed": processed,
        "pending": total - processed,
        "byRisk": by_risk,
        "byType": by_type,
        "byClass": dict(sorted(by_class.items(), key=lambda x: -x[1])),
    }


def build_pdf(summary: dict) -> bytes:
    import os
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    # 优先嵌入系统中文 TTF（字形打进 PDF，任何阅读器都不乱码），找不到再回退 CID 字体
    FONT = "STSong-Light"
    for ttf in (r"C:/Windows/Fonts/simhei.ttf", r"C:/Windows/Fonts/msyh.ttc"):
        if os.path.exists(ttf):
            try:
                pdfmetrics.registerFont(TTFont("CN", ttf))
                FONT = "CN"
                break
            except Exception:
                continue
    if FONT == "STSong-Light":
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Title"], fontName=FONT, fontSize=20)
    h_style = ParagraphStyle("h", parent=styles["Heading2"], fontName=FONT, fontSize=13)
    body = ParagraphStyle("b", parent=styles["Normal"], fontName=FONT, fontSize=10)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    story = []

    story.append(Paragraph("工地安防违规检测报表", title_style))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"统计周期：{summary['start']} 至 {summary['end']}", body))
    story.append(Paragraph(
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body))
    story.append(Spacer(1, 8 * mm))

    def make_table(header, rows, col_widths=None):
        data = [header] + rows
        t = Table(data, colWidths=col_widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FONT),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a5a2c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return t

    # 总览
    story.append(Paragraph("一、总览", h_style))
    story.append(Spacer(1, 3 * mm))
    story.append(make_table(
        ["指标", "数值"],
        [
            ["检测记录总数", str(summary["total"])],
            ["高危事件", str(summary["byRisk"].get("高危", 0))],
            ["中危事件", str(summary["byRisk"].get("中危", 0))],
            ["低危/正常", str(summary["byRisk"].get("低危", 0))],
            ["已处理", str(summary["processed"])],
            ["未处理", str(summary["pending"])],
        ],
        col_widths=[80 * mm, 40 * mm],
    ))
    story.append(Spacer(1, 8 * mm))

    # 来源分布
    story.append(Paragraph("二、检测来源分布", h_style))
    story.append(Spacer(1, 3 * mm))
    type_rows = [[k, str(v)] for k, v in summary["byType"].items()] or [["（无数据）", "0"]]
    story.append(make_table(["来源", "数量"], type_rows, col_widths=[80 * mm, 40 * mm]))
    story.append(Spacer(1, 8 * mm))

    # 违规类别
    story.append(Paragraph("三、违规类别统计", h_style))
    story.append(Spacer(1, 3 * mm))
    class_rows = [[k, str(v)] for k, v in summary["byClass"].items()] or [["（无数据）", "0"]]
    story.append(make_table(["违规类别", "出现次数"], class_rows, col_widths=[80 * mm, 40 * mm]))

    doc.build(story)
    return buf.getvalue()
