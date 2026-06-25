"""后台运维任务：数据保留清理、数据库备份、健康指标采集。

每天凌晨执行一次清理 + 备份；可被前端"立即执行"按钮按需触发。
所有保留天数从 Setting 表读，默认值见 DEFAULTS。
"""
import json
import os
import shutil
import threading
import time
from datetime import datetime, timedelta

from .extensions import db
from .models import DetectionRecord, Setting, AuditLog


DEFAULTS = {
    "retention_records": 90,    # 检测记录（含截图）保留天数
    "retention_clips":   30,    # 视频片段保留天数（mp4 体积大，单独控制）
    "retention_audits":  180,   # 审计日志保留天数
    "retention_backups": 30,    # DB 备份保留天数
}


def get_config() -> dict:
    cfg = {}
    for k, v in DEFAULTS.items():
        raw = Setting.get(k, "")
        try:
            cfg[k] = int(raw) if raw else v
        except ValueError:
            cfg[k] = v
    return cfg


def save_config(cfg: dict):
    for k in DEFAULTS:
        if k in cfg:
            try:
                v = max(1, min(3650, int(cfg[k])))
                Setting.put(k, str(v))
            except (TypeError, ValueError):
                pass
    db.session.commit()


# ===================== 清理 =====================

def cleanup_once(app) -> dict:
    """跑一次清理。返回 {records_deleted, clips_deleted, snaps_deleted, audits_deleted, db_backed_up}"""
    stats = {"records_deleted": 0, "clips_deleted": 0,
             "snaps_deleted": 0, "audits_deleted": 0, "db_backed_up": False}
    with app.app_context():
        cfg = get_config()
        now = datetime.utcnow()

        # 1) 清理超期检测记录（连带截图/视频文件）
        cutoff = now - timedelta(days=cfg["retention_records"])
        snapshot_dir = app.config["SNAPSHOT_DIR"]
        clip_dir = os.path.join(app.config["DATA_DIR"], "clips")
        old_records = DetectionRecord.query.filter(
            DetectionRecord.created_at < cutoff
        ).all()
        for rec in old_records:
            if rec.image_path:
                _safe_unlink(os.path.join(snapshot_dir, rec.image_path))
                stats["snaps_deleted"] += 1
            if rec.clip_path:
                _safe_unlink(os.path.join(clip_dir, rec.clip_path))
                stats["clips_deleted"] += 1
            db.session.delete(rec)
        stats["records_deleted"] = len(old_records)

        # 2) 单独清理仍在保留期内的旧视频片段（mp4 大，更短保留）
        clip_cutoff = now - timedelta(days=cfg["retention_clips"])
        # 找出有 clip 且 created_at 在 clip_cutoff 之前的记录，清掉 clip 文件
        for rec in DetectionRecord.query.filter(
            DetectionRecord.clip_path.isnot(None),
            DetectionRecord.created_at < clip_cutoff,
        ).all():
            _safe_unlink(os.path.join(clip_dir, rec.clip_path))
            rec.clip_path = None
            stats["clips_deleted"] += 1

        # 3) 清理超期审计日志
        audit_cutoff = now - timedelta(days=cfg["retention_audits"])
        deleted = AuditLog.query.filter(AuditLog.created_at < audit_cutoff).delete()
        stats["audits_deleted"] = deleted

        # 4) 孤儿文件清理：snapshots / clips 里没被任何记录引用的
        stats["snaps_deleted"] += _clean_orphans(snapshot_dir,
            {r.image_path for r in DetectionRecord.query.with_entities(DetectionRecord.image_path) if r.image_path})
        stats["clips_deleted"] += _clean_orphans(clip_dir,
            {r.clip_path for r in DetectionRecord.query.with_entities(DetectionRecord.clip_path) if r.clip_path})

        db.session.commit()

        # 5) 数据库备份
        stats["db_backed_up"] = backup_db(app, cfg["retention_backups"])
    return stats


def _safe_unlink(path: str) -> bool:
    try:
        if path and os.path.exists(path):
            os.remove(path)
            return True
    except OSError:
        pass
    return False


def _clean_orphans(dir_path: str, kept: set) -> int:
    """删 dir_path 里不在 kept 集合中的文件。返回删除数量。"""
    if not os.path.isdir(dir_path):
        return 0
    n = 0
    for name in os.listdir(dir_path):
        if name not in kept and not name.startswith("."):
            full = os.path.join(dir_path, name)
            if os.path.isfile(full):
                if _safe_unlink(full):
                    n += 1
    return n


# ===================== 数据库备份 =====================

def backup_db(app, keep_days: int) -> bool:
    """复制 sqlite 文件到 data/backups/app_YYYYMMDD.db；清理超期备份。"""
    src = app.config["SQLITE_PATH"]
    if not os.path.exists(src):
        return False
    backup_dir = os.path.join(app.config["DATA_DIR"], "backups")
    os.makedirs(backup_dir, exist_ok=True)
    fname = f"app_{datetime.now():%Y%m%d}.db"
    dst = os.path.join(backup_dir, fname)
    try:
        shutil.copy2(src, dst)
    except OSError:
        return False
    # 清理超期备份
    cutoff = time.time() - keep_days * 86400
    for f in os.listdir(backup_dir):
        full = os.path.join(backup_dir, f)
        if os.path.isfile(full) and os.path.getmtime(full) < cutoff:
            _safe_unlink(full)
    return True


# ===================== 健康指标 =====================

def health_metrics(app) -> dict:
    """采集系统健康指标：磁盘/内存/数据大小/活跃流。"""
    import shutil as sh
    metrics = {}
    data_dir = app.config["DATA_DIR"]
    try:
        usage = sh.disk_usage(data_dir)
        metrics["diskTotalGB"] = round(usage.total / 1e9, 2)
        metrics["diskUsedGB"] = round(usage.used / 1e9, 2)
        metrics["diskFreeGB"] = round(usage.free / 1e9, 2)
        metrics["diskPercent"] = round(usage.used / usage.total * 100, 1)
    except Exception:
        pass
    try:
        sqlite_path = app.config["SQLITE_PATH"]
        if os.path.exists(sqlite_path):
            metrics["dbSizeMB"] = round(os.path.getsize(sqlite_path) / 1e6, 2)
    except Exception:
        pass
    try:
        metrics["snapshotsMB"] = _dir_size_mb(app.config["SNAPSHOT_DIR"])
        metrics["clipsMB"] = _dir_size_mb(os.path.join(data_dir, "clips"))
        metrics["uploadsMB"] = _dir_size_mb(os.path.join(data_dir, "uploads"))
        metrics["backupsMB"] = _dir_size_mb(os.path.join(data_dir, "backups"))
    except Exception:
        pass
    try:
        # 进程内存（如果有 psutil）
        try:
            import psutil
            p = psutil.Process()
            metrics["memoryMB"] = round(p.memory_info().rss / 1e6, 1)
            metrics["cpuPercent"] = p.cpu_percent(interval=None)
        except ImportError:
            pass
    except Exception:
        pass
    # 活跃流
    try:
        from .stream import manager
        metrics["activeStreams"] = len([
            s for s in manager._streams.values() if s.alive and not s.error
        ])
        metrics["totalStreams"] = len(manager._streams)
    except Exception:
        pass
    # 数据库统计
    with app.app_context():
        try:
            from .models import DetectionRecord, AuditLog, Camera, User
            metrics["counts"] = {
                "records": DetectionRecord.query.count(),
                "audits": AuditLog.query.count(),
                "cameras": Camera.query.count(),
                "users": User.query.count(),
            }
        except Exception:
            metrics["counts"] = {}
    return metrics


def _dir_size_mb(path: str) -> float:
    if not os.path.isdir(path):
        return 0.0
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return round(total / 1e6, 2)


# ===================== 后台调度 =====================

_thread = None
_stop = threading.Event()


def _loop(app):
    """每小时检查一次：若上次清理距今 ≥ 24 小时，跑一次。"""
    last_run_key = "maintenance_last_run"
    while not _stop.is_set():
        try:
            with app.app_context():
                last_raw = Setting.get(last_run_key, "")
                try:
                    last = datetime.fromisoformat(last_raw) if last_raw else None
                except ValueError:
                    last = None
                now = datetime.utcnow()
                if not last or (now - last) >= timedelta(hours=24):
                    stats = cleanup_once(app)
                    Setting.put(last_run_key, now.isoformat())
                    db.session.commit()
                    app.logger.info("[maintenance] cleanup done: %s", stats)
        except Exception as e:
            try:
                app.logger.warning("[maintenance] failed: %s", e)
            except Exception:
                pass
        _stop.wait(3600)  # 1 小时一查


def start(app):
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(app,), daemon=True,
                               name="maintenance")
    _thread.start()


def stop():
    _stop.set()
