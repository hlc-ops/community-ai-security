"""轻量自动迁移（仅 SQLite，开发期用）。

SQLAlchemy 的 create_all 不会给已存在的表补新列。这里在启动时检查
detection_records 表，缺哪列就 ALTER TABLE 补哪列，避免改模型后旧库报错。
正式上线建议改用 Alembic 做正式迁移。
"""
from sqlalchemy import text, inspect

from .extensions import db

# 表名 → {列名: 建表 SQL 片段}
_COLUMNS = {
    "detection_records": {
        "llm_reviewed": "BOOLEAN DEFAULT 0",
        "llm_confirmed": "BOOLEAN",
        "llm_description": "TEXT DEFAULT ''",
        "llm_advice": "TEXT DEFAULT ''",
        "assignee_id": "INTEGER",
        "escalated": "BOOLEAN DEFAULT 0",
        "escalated_at": "DATETIME",
        "processed_at": "DATETIME",
        "closed_at": "DATETIME",
        "clip_path": "VARCHAR(255)",
        "urgency": "VARCHAR(16)",
        "urgency_reason": "VARCHAR(255) DEFAULT ''",
        "urgency_at": "DATETIME",
        # 社区版扩展
        "violation_type": "VARCHAR(32)",
        "triggered_polygon_id": "INTEGER",
        "camera_id": "INTEGER",
        "work_order_json": "TEXT",
        "work_order_at": "DATETIME",
    },
    "users": {
        "enabled": "BOOLEAN DEFAULT 1",
    },
    "cameras": {
        "schedule_enabled": "BOOLEAN DEFAULT 0",
        "schedule_start": "VARCHAR(5) DEFAULT '07:00'",
        "schedule_end": "VARCHAR(5) DEFAULT '19:00'",
        # 社区版扩展
        "location_type": "VARCHAR(32) DEFAULT 'outdoor'",
    },
}


def auto_migrate():
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    with db.engine.begin() as conn:
        for table, cols in _COLUMNS.items():
            if table not in tables:
                continue  # 还没建表，create_all 会带上新列
            existing = {c["name"] for c in insp.get_columns(table)}
            for col, ddl in cols.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
