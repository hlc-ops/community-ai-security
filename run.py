"""智慧社区后端启动入口。

    python run.py

默认监听 0.0.0.0:5050,提供 /api/* 接口(前后端分离,前端为独立 Vue 工程)。
为避开工地项目的 5000 端口,这里用 5050。
"""
from backend import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
