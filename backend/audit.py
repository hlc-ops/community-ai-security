"""审计日志助手：在请求上下文里一行记录关键操作。"""
from flask import request

from .extensions import db
from .models import AuditLog


def log(action: str,
        target_type: str = "",
        target_id="",
        detail: str = "",
        user_id=None,
        username: str = ""):
    """记录一条审计日志。失败不抛异常，避免影响主流程。"""
    try:
        # 从 JWT 上下文取当前用户（若未传入）
        if user_id is None or not username:
            try:
                from flask_jwt_extended import get_jwt_identity, get_jwt
                if user_id is None:
                    uid = get_jwt_identity()
                    if uid is not None:
                        user_id = int(uid)
                if not username:
                    username = get_jwt().get("username", "")
            except Exception:
                pass
        ip = ""
        try:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
        except Exception:
            pass
        db.session.add(AuditLog(
            user_id=user_id,
            username=username or "",
            action=action,
            target_type=target_type or "",
            target_id=str(target_id) if target_id is not None else "",
            ip=ip,
            detail=detail or "",
        ))
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
