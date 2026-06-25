"""大模型蓝图。

  GET  /api/llm/status                  查询是否已配置大模型
  POST /api/llm/review                  视觉大模型二次复核
       body: { "recordId": 123 }
  POST /api/llm/work_order              AI 物业工单生成(社区版独有)
       body: { "recordId": 123 }
"""
import os
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from ..extensions import db
from ..models import DetectionRecord, Camera
from .. import llm

bp_llm = Blueprint("llm", __name__)


@bp_llm.get("/status")
@jwt_required()
def status():
    return jsonify({
        "code": 200,
        "configured": llm.is_configured(),
        "provider": current_app.config.get("LLM_PROVIDER"),
    })


@bp_llm.post("/review")
@jwt_required()
def review():
    data = request.get_json(silent=True) or {}
    rid = data.get("recordId")
    rec = db.session.get(DetectionRecord, rid) if rid else None
    if not rec:
        return jsonify({"code": 404, "msg": "记录不存在"}), 404
    if not rec.image_path:
        return jsonify({"code": 400, "msg": "该记录没有截图，无法复核"}), 400

    img_file = os.path.join(current_app.config["SNAPSHOT_DIR"], rec.image_path)
    if not os.path.exists(img_file):
        return jsonify({"code": 400, "msg": "截图文件丢失"}), 400

    with open(img_file, "rb") as f:
        image_bytes = f.read()

    result = llm.review(image_bytes, rec.cls_list)
    if not result.get("ok"):
        return jsonify({"code": 503, "msg": result.get("msg", "大模型复核失败")}), 503

    # 写回记录
    rec.llm_reviewed = True
    rec.llm_confirmed = result.get("confirmed")
    rec.llm_description = result.get("description", "")
    rec.llm_advice = result.get("advice", "")
    db.session.commit()

    return jsonify({"code": 200, "msg": "复核完成", "result": result, "record": rec.to_dict()})


@bp_llm.post("/work_order")
@jwt_required()
def gen_work_order():
    """AI 生成物业工单(社区版独有)。"""
    data = request.get_json(silent=True) or {}
    rid = data.get("recordId")
    rec = db.session.get(DetectionRecord, rid) if rid else None
    if not rec:
        return jsonify({"code": 404, "msg": "记录不存在"}), 404

    # 组装传给 LLM 的上下文
    camera_location = "未指定"
    location_type_zh = "露天监控"
    if rec.camera_id:
        cam = db.session.get(Camera, rec.camera_id)
        if cam:
            camera_location = cam.location or cam.name or "未指定"
            location_type_zh = cam.LOCATION_TYPE_ZH.get(cam.location_type, "露天监控")

    record_data = {
        "violation_zh": DetectionRecord.VIOLATION_ZH.get(rec.violation_type, rec.violation_type or "异常事件"),
        "cls_list": "、".join(rec.cls_list) if rec.cls_list else "未提供",
        "reason": rec.remark or "未填写",
        "camera_location": camera_location,
        "location_type_zh": location_type_zh,
        "occur_time": (rec.created_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M"),
    }

    result = llm.generate_work_order(record_data)
    if not result.get("ok"):
        return jsonify({"code": 503, "msg": result.get("msg", "工单生成失败")}), 503

    # 写回记录
    rec.work_order = {
        "title": result["title"],
        "assigneeRole": result["assignee_role"],
        "priority": result["priority"],
        "summary": result["summary"],
        "actions": result["actions"],
        "expected": result["expected"],
        "timeframe": result["timeframe"],
        "notifyOwner": result["notify_owner"],
    }
    rec.work_order_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"code": 200, "msg": "工单已生成", "workOrder": rec.work_order, "record": rec.to_dict()})
