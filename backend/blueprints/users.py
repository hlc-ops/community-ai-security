"""用户管理蓝图（仅管理员）。

  GET    /api/users            用户列表
  POST   /api/users            新增用户
  PUT    /api/users/<id>       改角色 / 真实姓名
  PUT    /api/users/<id>/password   重置密码
  PUT    /api/users/<id>/status     启用/停用
  DELETE /api/users/<id>       删除用户

约束：管理员不能停用/删除自己；不能删除最后一个管理员。
"""
from functools import wraps

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity

from ..extensions import db
from ..models import User
from .. import audit, security

bp_users = Blueprint("users", __name__)


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        if get_jwt().get("role") != "admin":
            return jsonify({"code": 403, "msg": "仅管理员可操作"}), 403
        return fn(*args, **kwargs)
    return wrapper


def _current_uid():
    return int(get_jwt_identity())


@bp_users.get("")
@admin_required
def list_users():
    users = User.query.order_by(User.created_at.asc()).all()
    return jsonify({"code": 200, "items": [u.to_dict() for u in users]})


@bp_users.post("")
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role", "operator")
    real_name = (data.get("realName") or "").strip()

    if len(username) < 3:
        return jsonify({"code": 400, "msg": "用户名至少 3 个字符"}), 400
    ok, msg = security.check_password(password)
    if not ok:
        return jsonify({"code": 400, "msg": msg}), 400
    if role not in ("admin", "operator"):
        return jsonify({"code": 400, "msg": "非法角色"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"code": 409, "msg": "用户名已存在"}), 409

    user = User(username=username, real_name=real_name, role=role, enabled=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    audit.log("user.create", "user", user.id, f"{username}/{role}")
    return jsonify({"code": 200, "msg": "已创建", "user": user.to_dict()})


@bp_users.put("/<int:uid>")
@admin_required
def update_user(uid):
    user = db.session.get(User, uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404
    data = request.get_json(silent=True) or {}
    if "realName" in data:
        user.real_name = (data["realName"] or "").strip()
    if "role" in data and data["role"] in ("admin", "operator"):
        # 不能把最后一个管理员降级
        if user.role == "admin" and data["role"] != "admin" and _admin_count() <= 1:
            return jsonify({"code": 400, "msg": "至少保留一个管理员"}), 400
        user.role = data["role"]
    db.session.commit()
    return jsonify({"code": 200, "msg": "已更新", "user": user.to_dict()})


@bp_users.put("/<int:uid>/password")
@admin_required
def reset_password(uid):
    user = db.session.get(User, uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404
    pwd = (request.get_json(silent=True) or {}).get("password") or ""
    ok, msg = security.check_password(pwd)
    if not ok:
        return jsonify({"code": 400, "msg": msg}), 400
    user.set_password(pwd)
    db.session.commit()
    audit.log("user.reset_password", "user", uid, user.username)
    return jsonify({"code": 200, "msg": "密码已重置"})


@bp_users.put("/<int:uid>/status")
@admin_required
def set_status(uid):
    user = db.session.get(User, uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    if not enabled and uid == _current_uid():
        return jsonify({"code": 400, "msg": "不能停用自己"}), 400
    if not enabled and user.role == "admin" and _enabled_admin_count() <= 1:
        return jsonify({"code": 400, "msg": "至少保留一个启用的管理员"}), 400
    user.enabled = enabled
    db.session.commit()
    audit.log("user.set_status", "user", uid, f"{user.username}={'启用' if enabled else '停用'}")
    return jsonify({"code": 200, "msg": "已启用" if enabled else "已停用", "user": user.to_dict()})


@bp_users.delete("/<int:uid>")
@admin_required
def delete_user(uid):
    user = db.session.get(User, uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404
    if uid == _current_uid():
        return jsonify({"code": 400, "msg": "不能删除自己"}), 400
    if user.role == "admin" and _admin_count() <= 1:
        return jsonify({"code": 400, "msg": "至少保留一个管理员"}), 400
    uname = user.username
    db.session.delete(user)
    db.session.commit()
    audit.log("user.delete", "user", uid, uname)
    return jsonify({"code": 200, "msg": "已删除"})


def _admin_count():
    return User.query.filter_by(role="admin").count()


def _enabled_admin_count():
    return User.query.filter_by(role="admin", enabled=True).count()
