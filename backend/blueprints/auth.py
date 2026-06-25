"""鉴权蓝图：注册 / 登录 / 当前用户。

前后端分离方案：登录成功返回 JWT access token，前端存起来，后续请求带在
Authorization: Bearer <token> 头里。
"""
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)

from ..extensions import db
from ..models import User
from .. import security

bp_auth = Blueprint("auth", __name__)


@bp_auth.post("/login")
def login():
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"code": 400, "msg": "用户名和密码不能为空"}), 400

    # 限流：先看是否被锁
    locked, remain = security.is_locked(username)
    if locked:
        return jsonify({
            "code": 429,
            "msg": f"登录失败次数过多，账号已锁定，请 {remain // 60 + 1} 分钟后再试",
        }), 429

    user = User.query.filter_by(username=username).first()
    from .. import audit
    if not user or not user.check_password(password):
        triggered, remaining = security.record_failure(username)
        audit.log("login.fail", detail=f"用户名={username}", username=username)
        if triggered:
            return jsonify({
                "code": 429,
                "msg": "连续 5 次失败，账号已锁定 5 分钟",
            }), 429
        return jsonify({
            "code": 401,
            "msg": f"账号或密码错误（剩余 {remaining} 次尝试）",
        }), 401
    if not user.enabled:
        audit.log("login.fail", detail="账号已停用", user_id=user.id, username=user.username)
        return jsonify({"code": 403, "msg": "账号已被停用，请联系管理员"}), 403

    security.record_success(username)
    user.last_login = datetime.utcnow()
    db.session.commit()

    token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role, "username": user.username},
    )
    audit.log("login.success", user_id=user.id, username=user.username)
    return jsonify({"code": 200, "msg": "登录成功", "token": token, "user": user.to_dict()})


@bp_auth.post("/register")
def register():
    """注册操作员账号。管理员账号请用默认 seed 或后续后台管理创建。"""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    real_name = (data.get("realName") or "").strip()

    if len(username) < 3:
        return jsonify({"code": 400, "msg": "用户名至少 3 个字符"}), 400
    ok, msg = security.check_password(password)
    if not ok:
        return jsonify({"code": 400, "msg": msg}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"code": 409, "msg": "用户名已存在"}), 409

    user = User(username=username, real_name=real_name, role="operator")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"code": 200, "msg": "注册成功", "user": user.to_dict()})


@bp_auth.get("/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404
    return jsonify({"code": 200, "user": user.to_dict()})


@bp_auth.put("/password")
@jwt_required()
def change_password():
    data = request.get_json(silent=True) or {}
    old = data.get("oldPassword") or ""
    new = data.get("newPassword") or ""
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or not user.check_password(old):
        return jsonify({"code": 401, "msg": "原密码错误"}), 401
    ok, msg = security.check_password(new)
    if not ok:
        return jsonify({"code": 400, "msg": msg}), 400
    user.set_password(new)
    db.session.commit()
    return jsonify({"code": 200, "msg": "密码已修改"})
