"""审计日志查询蓝图（仅管理员）。"""
from functools import wraps

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from ..models import AuditLog

bp_audit = Blueprint("audit", __name__)


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        if get_jwt().get("role") != "admin":
            return jsonify({"code": 403, "msg": "仅管理员可查看"}), 403
        return fn(*args, **kwargs)
    return wrapper


@bp_audit.get("/logs")
@admin_required
def list_logs():
    q = AuditLog.query
    if (action := request.args.get("action")):
        q = q.filter(AuditLog.action.like(f"{action}%"))
    if (username := request.args.get("username")):
        q = q.filter(AuditLog.username.like(f"%{username}%"))
    if (start := request.args.get("start")):
        q = q.filter(AuditLog.created_at >= start)
    if (end := request.args.get("end")):
        q = q.filter(AuditLog.created_at <= end + " 23:59:59")
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("pageSize", 20)), 1), 200)
    q = q.order_by(AuditLog.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "code": 200,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": [it.to_dict() for it in items],
    })
