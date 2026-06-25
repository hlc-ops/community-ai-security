"""首次启动初始化默认管理员账号。"""
from flask import current_app

from .extensions import db
from .models import User


def ensure_default_admin():
    username = current_app.config["DEFAULT_ADMIN_USERNAME"]
    if User.query.filter_by(username=username).first():
        return
    admin = User(username=username, real_name="系统管理员", role="admin")
    admin.set_password(current_app.config["DEFAULT_ADMIN_PASSWORD"])
    db.session.add(admin)
    db.session.commit()
    current_app.logger.info("已创建默认管理员账号：%s", username)
