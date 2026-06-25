"""Flask 扩展单例。在工厂里 init_app 绑定到具体 app，避免循环导入。"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
jwt = JWTManager()
