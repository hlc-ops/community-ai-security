"""智慧社区 Web 后端 —— Flask 应用工厂。

提供 create_app() 统一装配:配置、数据库、JWT、蓝图、静态快照目录、
后台 watcher、日志切割。

业务覆盖:违停、乱丢垃圾、宠物闯入、电瓶车违规(进电梯/楼道)、明火检测,
配合 polygon 配置实现"摄像头 + 区域 + 业务"灵活映射。
"""
import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from .config import Config
from .extensions import db, jwt
from .detector import get_detector


def _setup_logging(app: Flask):
    """日志切割：单文件 5MB，保留 5 份，存 data/logs/server.log。"""
    log_dir = os.path.join(app.config["DATA_DIR"], "logs")
    os.makedirs(log_dir, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = RotatingFileHandler(
        os.path.join(log_dir, "server.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(fmt)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    logging.getLogger("werkzeug").addHandler(handler)


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    # 确保数据/快照目录存在
    os.makedirs(app.config["SNAPSHOT_DIR"], exist_ok=True)
    os.makedirs(os.path.dirname(app.config["SQLITE_PATH"]), exist_ok=True)

    # 扩展
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 蓝图
    from .blueprints.auth import bp_auth
    from .blueprints.records import bp_records
    from .blueprints.detect import bp_detect
    from .blueprints.llm import bp_llm
    from .blueprints.settings import bp_settings
    from .blueprints.users import bp_users
    from .blueprints.reports import bp_reports
    from .blueprints.stream import bp_stream
    from .blueprints.cameras import bp_cameras
    from .blueprints.audit import bp_audit
    from .blueprints.events import bp_events
    from .blueprints.public import bp_public

    app.register_blueprint(bp_auth, url_prefix="/api/auth")
    app.register_blueprint(bp_records, url_prefix="/api/records")
    app.register_blueprint(bp_detect, url_prefix="/api/detect")
    app.register_blueprint(bp_llm, url_prefix="/api/llm")
    app.register_blueprint(bp_settings, url_prefix="/api/settings")
    app.register_blueprint(bp_users, url_prefix="/api/users")
    app.register_blueprint(bp_reports, url_prefix="/api/reports")
    app.register_blueprint(bp_stream, url_prefix="/api/stream")
    app.register_blueprint(bp_cameras, url_prefix="/api/cameras")
    app.register_blueprint(bp_audit, url_prefix="/api/audit")
    app.register_blueprint(bp_events, url_prefix="/api/events")
    app.register_blueprint(bp_public, url_prefix="/api/public")

    # 快照图片访问： /api/snapshots/<filename>
    @app.route("/api/snapshots/<path:filename>")
    def snapshot(filename):
        return send_from_directory(app.config["SNAPSHOT_DIR"], filename)

    # 上传文件访问（品牌 logo、告警声音等）： /api/uploads/<filename>
    @app.route("/api/uploads/<path:filename>")
    def upload(filename):
        upload_dir = os.path.join(app.config["DATA_DIR"], "uploads")
        return send_from_directory(upload_dir, filename)

    # 告警视频片段访问： /api/clips/<filename>
    @app.route("/api/clips/<path:filename>")
    def clip(filename):
        clip_dir = os.path.join(app.config["DATA_DIR"], "clips")
        return send_from_directory(clip_dir, filename)

    @app.route("/api/health")
    def health():
        """轻量健康检查（供监控探活）。详细指标走 /api/settings/health。"""
        from . import stream as _stream
        active = len([s for s in _stream.manager._streams.values()
                      if s.alive and not s.error])
        return jsonify({
            "status": "ok",
            "service": "smart-community-backend",
            "activeStreams": active,
        })

    # ---- 托管打包后的前端（单进程部署）----
    # 仅当 frontend/dist 存在时生效；开发模式用 Vite(5173) 不受影响。
    dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "frontend", "dist")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        # /api 已由蓝图处理；这里只兜前端路由
        if path.startswith("api/"):
            return jsonify({"code": 404, "msg": "接口不存在"}), 404
        if not os.path.isdir(dist_dir):
            return jsonify({"code": 404,
                            "msg": "前端未打包，请先在 frontend 下执行 npm run build"}), 404
        target = os.path.join(dist_dir, path)
        if path and os.path.isfile(target):
            return send_from_directory(dist_dir, path)
        return send_from_directory(dist_dir, "index.html")  # SPA 回退

    # 统一 JWT 错误返回 JSON（前端好处理）
    @jwt.unauthorized_loader
    def _missing_token(reason):
        return jsonify({"code": 401, "msg": "未登录或缺少令牌", "detail": reason}), 401

    @jwt.invalid_token_loader
    def _invalid_token(reason):
        return jsonify({"code": 401, "msg": "令牌无效", "detail": reason}), 401

    @jwt.expired_token_loader
    def _expired_token(header, payload):
        return jsonify({"code": 401, "msg": "登录已过期，请重新登录"}), 401

    # 建表 + 轻量迁移 + 预热模型 + 初始化默认管理员
    with app.app_context():
        db.create_all()
        from .migrate import auto_migrate
        auto_migrate()
        from .seed import ensure_default_admin
        ensure_default_admin()
        if app.config.get("PRELOAD_MODEL", True):
            try:
                get_detector()  # 启动即加载 OpenVINO 模型，避免首帧卡顿
            except Exception as e:  # 模型缺失时不阻断后端启动
                app.logger.warning("模型预加载失败：%s", e)

    # 日志切割
    _setup_logging(app)

    # 摄像头健康监控后台 watcher
    from . import health
    health.start(app)

    # 数据保留 + 数据库备份 后台 watcher
    from . import maintenance
    maintenance.start(app)

    return app
