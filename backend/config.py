"""后端配置。

开发期默认用 SQLite，零配置即可跑。上线切 PostgreSQL/MySQL 时只需改
SQLALCHEMY_DATABASE_URI（或设环境变量 DATABASE_URL）。
"""
import os
from datetime import timedelta

# 项目根目录（backend 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 自动加载项目根目录下的 .env（存放 API Key 等敏感配置，不提交到代码库）
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))
except Exception:
    pass


class Config:
    # ---- 安全 ----
    # 生产环境务必通过环境变量覆盖，不要用默认值
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)

    # ---- 数据库 ----
    DATA_DIR = os.path.join(BASE_DIR, "data")
    SQLITE_PATH = os.path.join(DATA_DIR, "app.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{SQLITE_PATH}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- 文件 ----
    SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")  # 违规截图落盘目录
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB 上传上限

    # ---- 模型 ----
    # 优先级:OpenVINO INT8 > FP32 备份 > PyTorch 原始
    # 命名对齐工地项目:
    #   best_openvino_model/      → INT8 主用(CPU 推理快、体积小)
    #   best_openvino_model_fp32/ → FP32 备份(精度对比/回退用)
    #   best.pt                   → PyTorch 原始权重
    _ov_int8 = os.path.join(BASE_DIR, "model", "best_openvino_model")
    _ov_fp32 = os.path.join(BASE_DIR, "model", "best_openvino_model_fp32")
    _pt = os.path.join(BASE_DIR, "model", "best.pt")
    if os.path.exists(_ov_int8):
        MODEL_PATH = _ov_int8
    elif os.path.exists(_ov_fp32):
        MODEL_PATH = _ov_fp32
    else:
        MODEL_PATH = _pt
    MODEL_IMGSZ = 640  # 社区检测用 640(训练时是 640)
    PRELOAD_MODEL = True  # 启动即加载模型

    # ---- 默认管理员（首次启动自动创建）----
    DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "hlc")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")

    # ---- 视觉大模型（YOLO 二次复核 + 整改建议）----
    # provider: qwen（通义千问，默认）/ zhipu（智谱 GLM-4V）。二者均为 OpenAI 兼容接口。
    # 只需填 LLM_API_KEY 即可启用；想换厂商改 LLM_PROVIDER 即可。
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "qwen")
    LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("DASHSCOPE_API_KEY", "")
    # 留空则按 provider 取下方默认值
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "")
    LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))

    # 各厂商默认 base_url / 视觉模型
    LLM_DEFAULTS = {
        "qwen": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-vl-plus",
        },
        "zhipu": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4v-plus",
        },
    }
