"""RTSP/IP 摄像头拉流 + 检测 + MJPEG 推流。

浏览器放不了 RTSP，所以后端用 OpenCV 拉流、逐帧 YOLO 检测、画框后编码成 JPEG，
通过 multipart/x-mixed-replace（MJPEG）推给网页 <img> 显示。

每路摄像头一个 StreamWorker 后台线程；StreamManager 统一管理。命中高/中危时
服务端按间隔抓拍入库并触发报警（复用现有记录与报警逻辑）。
"""
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime

import numpy as np

# 给 FFmpeg 设连接/读取超时，避免坏 RTSP 地址卡死（stimeout 单位微秒，5s）
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000"
)

import cv2

from .detector import get_detector, risk_level


class StreamWorker:
    def __init__(self, app, url, conf=0.5, snap_interval=10, zone=None, schedule=None):
        self.app = app
        self.url = url
        self.conf = conf
        self.snap_interval = snap_interval
        self.zone = zone
        self.schedule = schedule  # dict {enabled, start "HH:MM", end "HH:MM"} or None

        self.alive = False
        self.error = ""
        self.latest_jpeg = None          # 最新原始帧（不带框，bytes，JPEG）
        self.latest_boxes = []           # 最近一次检测的归一化框列表
        self.risk = "low"
        self.cls_list = []
        self.snap_count = 0

        self._stop = threading.Event()
        self._last_snap = 0.0
        self._frame_lock = threading.Lock()
        self._latest_frame = None         # 最新原始帧（np.ndarray，给检测线程取）
        self._det_running = False
        self._last_det_at = 0.0
        # Pose 行为分析器(每个 StreamWorker 一个,维护时序状态)
        self._pose_analyzer = None  # 懒加载
        # ---- 告警视频片段录像 ----
        # 环形缓冲：保留近 5 秒 JPEG 帧（每帧 ~30KB，100 帧 ~3MB）
        self.ring = deque(maxlen=100)     # [(timestamp, jpeg_bytes), ...]
        self._clip_recording = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 降低延迟
        except Exception:
            pass
        if not cap.isOpened():
            self.error = "无法打开视频源，请检查 RTSP 地址 / 网络 / 账号密码"
            self.alive = False
            cap.release()
            return

        self.alive = True
        detector = None
        with self.app.app_context():
            try:
                detector = get_detector()
            except Exception as e:
                self.error = f"模型加载失败：{e}"
                self.alive = False
                cap.release()
                return

            # ===== 主循环：只负责拉流 + 编码原帧 =====
            # 检测在独立线程里跑（节流派发），实现"原视频丝滑播放，框单独更新"
            fail = 0
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    fail += 1
                    if fail > 30:
                        self.error = "视频流中断"
                        break
                    time.sleep(0.05)
                    continue
                fail = 0
                try:
                    ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if ok2:
                        jpeg = buf.tobytes()
                        self.latest_jpeg = jpeg
                        self.ring.append((time.time(), jpeg))
                    # 保存最新帧供检测线程取（拷贝，因为 cap.read 会复用底层 buffer）
                    with self._frame_lock:
                        self._latest_frame = frame.copy()
                    self._maybe_dispatch_detection(detector)
                    self._maybe_heartbeat()
                except Exception:
                    pass

        cap.release()
        self.alive = False

    def _maybe_dispatch_detection(self, detector):
        """节流派发：上一次检测未完成则跳过；时段外不检测。"""
        if not self._in_schedule():
            # 时段外清空状态，避免残留旧告警
            self.cls_list = []
            self.risk = "low"
            self.latest_boxes = []
            return
        if self._det_running:
            return
        now = time.time()
        if now - self._last_det_at < 0.05:  # 最快 ~20fps 检测频率（CPU 实际跑不到）
            return
        self._last_det_at = now
        self._det_running = True
        threading.Thread(target=self._do_detection, args=(detector,), daemon=True).start()

    def _do_detection(self, detector):
        try:
            with self._frame_lock:
                frame = self._latest_frame
            if frame is None:
                return
            # 整个推理 + 抓拍入库 + 视频片段录制都在 app 上下文内
            # （_maybe_snap 用 current_app/db，没上下文会被静默吞掉）
            with self.app.app_context():
                from .blueprints.detect import _get_class_confs
                drawn, cls_list, high, mid, boxes = detector.detect(
                    frame, self.conf, self.zone, _get_class_confs(),
                )
                self.cls_list = cls_list
                self.risk = risk_level(high, mid)
                self.latest_boxes = boxes
                # === Pose 行为分析(可选,失败不影响主检测)===
                pose_events = self._run_pose_analysis(frame)
                self._maybe_snap(drawn, cls_list, high, mid, boxes, pose_events)
        except Exception:
            pass
        finally:
            self._det_running = False

    def _start_clip_recording(self, rec_id):
        """触发：捕获当前 ring（前 5s 帧快照），后台线程再等 5s 录后帧并编码 mp4。"""
        if self._clip_recording:
            return  # 上一个还没录完，丢弃本次（避免重叠）
        # 快照当前环形缓冲：(timestamp, jpeg) 列表
        pre_frames = list(self.ring)
        if not pre_frames:
            return
        self._clip_recording = True
        threading.Thread(
            target=self._record_clip,
            args=(rec_id, pre_frames),
            daemon=True,
        ).start()

    def _record_clip(self, rec_id, pre_frames):
        POST_DURATION_SEC = 5.0
        try:
            trigger_ts = pre_frames[-1][0] if pre_frames else time.time()
            # 等待后帧填充
            time.sleep(POST_DURATION_SEC)
            # 取后帧（trigger 后的帧）
            post_frames = [(t, j) for t, j in list(self.ring) if t > trigger_ts]
            # 合并前+后；按时间排序、去重
            seen = set()
            all_frames = []
            for t, j in pre_frames + post_frames:
                if t in seen:
                    continue
                seen.add(t)
                all_frames.append((t, j))
            all_frames.sort(key=lambda x: x[0])
            if len(all_frames) < 5:
                return  # 帧太少不值得保存

            # 解出第一帧拿尺寸；统一尺寸（不一致的丢弃）
            first = cv2.imdecode(np.frombuffer(all_frames[0][1], np.uint8), cv2.IMREAD_COLOR)
            if first is None:
                return
            h, w = first.shape[:2]

            # 估算播放 fps
            duration = max(0.1, all_frames[-1][0] - all_frames[0][0])
            fps = max(5.0, min(25.0, len(all_frames) / duration))

            with self.app.app_context():
                from flask import current_app
                clip_dir = os.path.join(current_app.config["DATA_DIR"], "clips")
                os.makedirs(clip_dir, exist_ok=True)
                fname = f"{datetime.now():%Y%m%d}_{uuid.uuid4().hex[:12]}.mp4"
                path = os.path.join(clip_dir, fname)

                writer = cv2.VideoWriter(
                    path,
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    fps,
                    (w, h),
                )
                if not writer.isOpened():
                    return
                for t, j in all_frames:
                    frame = cv2.imdecode(np.frombuffer(j, np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None and frame.shape[:2] == (h, w):
                        writer.write(frame)
                writer.release()

                # 更新记录的 clip_path
                from .extensions import db
                from .models import DetectionRecord
                rec = db.session.get(DetectionRecord, rec_id)
                if rec:
                    rec.clip_path = fname
                    db.session.commit()
        except Exception:
            pass
        finally:
            self._clip_recording = False

    def _maybe_heartbeat(self):
        """每 ~5 秒把摄像头的 last_online_at 推到数据库一次，用于健康监控。"""
        cid = getattr(self, "camera_id", None)
        if cid is None:
            return
        now = time.time()
        if now - getattr(self, "_last_hb", 0) < 5:
            return
        self._last_hb = now
        try:
            with self.app.app_context():
                from .extensions import db
                from .models import Camera
                cam = db.session.get(Camera, cid)
                if cam:
                    cam.last_online_at = datetime.utcnow()
                    db.session.commit()
        except Exception:
            pass

    def _in_schedule(self) -> bool:
        """当前时间是否处于检测时段内。未启用时段则恒为 True。"""
        s = self.schedule
        if not s or not s.get("enabled"):
            return True
        try:
            now = datetime.now().strftime("%H:%M")
            start, end = s.get("start", "00:00"), s.get("end", "23:59")
            # 支持跨夜（如 22:00 → 06:00）
            if start <= end:
                return start <= now <= end
            return now >= start or now <= end
        except Exception:
            return True

    def _run_pose_analysis(self, frame_bgr):
        """跑姿态分析,返回行为事件列表。失败返回空列表(不阻断主流程)。"""
        try:
            from . import pose_detector, behavior_rules
            from .models import Setting
            # Setting 开关:默认关闭,管理员开启才跑(避免双模型推理压力)
            if Setting.get("pose_enabled", "0") != "1":
                return []
            if self._pose_analyzer is None:
                self._pose_analyzer = behavior_rules.PoseBehaviorAnalyzer()
            detector = pose_detector.get_pose_detector()
            persons = detector.extract(frame_bgr, conf=0.5)
            if not persons:
                return []
            # 拉摄像头关联的"围栏"polygon 给翻墙判定用
            fence_polys = None
            if self.camera_id:
                from .models import Polygon
                fence_polys = [
                    {"points": p.points}
                    for p in Polygon.query.filter_by(
                        camera_id=self.camera_id, polygon_type="fire_lane", enabled=True
                    ).all()
                ]
            return self._pose_analyzer.analyze(persons, fence_polygons=fence_polys)
        except Exception as e:
            try:
                self.app.logger.warning(f"pose 分析失败: {e}")
            except Exception:
                pass
            return []

    def _maybe_snap(self, drawn, cls_list, high, mid, boxes_norm, pose_events=None):
        """社区版:接入 business_rules 业务规则引擎。

        - 基础检测层只判断 high/mid 是否触发
        - 业务层结合摄像头位置 + polygon 决定具体违规类型
        - 两条路径:
          1. business_rules 命中:用业务等级覆盖 + 记录 violation_type
          2. 仅基础层 high/mid:走原通用流程
        """
        now = time.time()
        if now - self._last_snap < self.snap_interval:
            return

        try:
            from .extensions import db
            from .models import DetectionRecord, Camera, Polygon
            from . import alert, business_rules
            import os
            from flask import current_app

            # 拉取 camera + polygons
            camera = None
            polygons = []
            if self.camera_id:
                camera = db.session.get(Camera, self.camera_id)
                if camera:
                    polygons = list(Polygon.query.filter_by(
                        camera_id=self.camera_id, enabled=True
                    ).all())

            # 业务规则路由
            violations = []
            if camera:
                violations = business_rules.route(camera, boxes_norm, polygons)

            # 接入 Pose 行为事件(如 fall/fence_climbing/fighting/running)
            for ev in (pose_events or []):
                violations.append({
                    "violation_type": {
                        "fall": "fall_detected",
                        "fence_climbing": "fence_climbing",
                        "fighting": "fighting",
                        "running": "abnormal_running",
                    }.get(ev["type"], ev["type"]),
                    "risk_level": ev.get("risk_level", "mid"),
                    "polygon_id": ev.get("polygon_id"),
                    "reason": ev.get("reason", ""),
                    "detection": None,
                })

            # 决策:有业务违规 -> 用业务等级;否则用基础 high/mid
            if violations:
                # 按 high>mid>low 排序,取最严重
                _rank = {"high": 0, "mid": 1, "low": 2}
                violations.sort(key=lambda v: _rank.get(v["risk_level"], 9))
                top = violations[0]
                final_risk = top["risk_level"]
                violation_type = top["violation_type"]
                polygon_id = top["polygon_id"]
                violation_reason = top["reason"]
            else:
                if not (high or mid):
                    return  # 基础检测也无违规,跳过
                final_risk = risk_level(high, mid)
                violation_type = None
                polygon_id = None
                violation_reason = ""

            self._last_snap = now

            # 截图落盘
            ok, buf = cv2.imencode(".jpg", drawn, [cv2.IMWRITE_JPEG_QUALITY, 70])
            fname = None
            if ok:
                fname = f"{datetime.now():%Y%m%d}_{uuid.uuid4().hex[:12]}.jpg"
                with open(os.path.join(current_app.config["SNAPSHOT_DIR"], fname), "wb") as f:
                    f.write(buf.tobytes())

            rec = DetectionRecord(
                record_type="camera",
                risk_level=final_risk,
                status="pending",
                image_path=fname,
                started_at=datetime.utcnow(),
                violation_type=violation_type,
                triggered_polygon_id=polygon_id,
                camera_id=self.camera_id,
                remark=violation_reason,
            )
            rec.cls_list = cls_list
            db.session.add(rec)
            db.session.commit()
            rec_id = rec.id
            self.snap_count += 1

            # 广播给前端实时弹窗
            from . import events as _events
            _events.publish("alert", rec.to_dict())

            if rec.risk_level == "high":
                from . import triage
                if triage.is_enabled():
                    triage.schedule(current_app._get_current_object(), rec_id)
                else:
                    alert.notify_async(current_app._get_current_object(), rec_id)

            # 触发告警视频片段录像(前 5 秒 + 后 5 秒)
            self._start_clip_recording(rec_id)
        except Exception:
            db_rollback()

    def mjpeg(self):
        """MJPEG 生成器：持续吐出最新帧。"""
        boundary = b"--frame"
        while self.alive and not self._stop.is_set():
            if self.latest_jpeg:
                yield (boundary + b"\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n"
                       + self.latest_jpeg + b"\r\n")
            time.sleep(0.05)


def db_rollback():
    try:
        from .extensions import db
        db.session.rollback()
    except Exception:
        pass


class StreamManager:
    def __init__(self):
        self._streams: dict[str, StreamWorker] = {}
        self._by_camera: dict[int, str] = {}    # camera_id → sid
        self._lock = threading.Lock()

    def start(self, app, url, conf=0.5, snap_interval=10, zone=None, camera_id=None, schedule=None) -> str:
        # 每个摄像头同时只允许一路
        if camera_id is not None:
            old = self._by_camera.get(camera_id)
            if old:
                self.stop(old)
        sid = uuid.uuid4().hex
        worker = StreamWorker(app, url, conf, snap_interval, zone, schedule)
        worker.camera_id = camera_id
        with self._lock:
            self._streams[sid] = worker
            if camera_id is not None:
                self._by_camera[camera_id] = sid
        worker.start()
        return sid

    def get(self, sid) -> StreamWorker | None:
        return self._streams.get(sid)

    def get_by_camera(self, camera_id) -> tuple[str, StreamWorker] | None:
        sid = self._by_camera.get(camera_id)
        if sid:
            w = self._streams.get(sid)
            if w:
                return sid, w
        return None

    def stop(self, sid):
        with self._lock:
            w = self._streams.pop(sid, None)
            if w and getattr(w, "camera_id", None) is not None:
                self._by_camera.pop(w.camera_id, None)
        if w:
            w.stop()

    def stop_camera(self, camera_id):
        ws = self.get_by_camera(camera_id)
        if ws:
            self.stop(ws[0])

    def cleanup_dead(self):
        with self._lock:
            dead = [sid for sid, w in self._streams.items() if not w.alive and w.error]
            for sid in dead:
                w = self._streams.pop(sid, None)
                if w and getattr(w, "camera_id", None) is not None:
                    self._by_camera.pop(w.camera_id, None)


manager = StreamManager()
