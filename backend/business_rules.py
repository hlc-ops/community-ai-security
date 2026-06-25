"""社区版业务规则引擎。

YOLO 只负责"识别物体",这里把"物体 + 摄像头位置 + polygon"映射成具体业务违规。

输入:
  - camera: Camera 对象(含 location_type)
  - detections: 检测结果列表 [{"name":..., "x1,y1,x2,y2":..., "conf":...}]
  - polygons: 该摄像头的所有 polygon 列表

输出:
  - violations: 业务违规事件列表
    每条 {
      "violation_type": "illegal_parking",
      "risk_level": "high",
      "polygon_id": 5,
      "detection": {...原始检测...},
      "reason": "车辆停在消防通道上"
    }

设计原则:
  1. 每个 polygon 只属于一种类型,不会冲突
  2. 同一辆车跨区:按 IoU 重叠面积 + 告警优先级判定
  3. 短暂经过不告警:配合 dwell_threshold 时间维度去抖(由调用方维护历史)
"""
from typing import Optional


# ============ 几何工具 ============

def _point_in_polygon(point, polygon_points) -> bool:
    """归一化坐标:点是否在多边形内(射线法)。"""
    if not polygon_points or len(polygon_points) < 3:
        return False
    x, y = point
    n = len(polygon_points)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon_points[i]
        xj, yj = polygon_points[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _box_polygon_overlap_ratio(box, polygon_points) -> float:
    """估算检测框中心 + 4 角与 polygon 的重叠程度(0~1)。

    简化算法:中心 + 4 角 5 个采样点,数有几个在 polygon 内,返回比例。
    实际生产可用 Shapely 算精确 IoU,这里足够工程使用。
    """
    if not polygon_points or len(polygon_points) < 3:
        return 0.0
    x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    samples = [(cx, cy), (x1, y1), (x2, y1), (x1, y2), (x2, y2)]
    hits = sum(1 for p in samples if _point_in_polygon(p, polygon_points))
    return hits / len(samples)


# ============ 业务规则路由 ============

def route(camera, detections: list, polygons: list) -> list:
    """主路由函数:决定每个检测命中哪个业务违规。

    Args:
        camera: Camera ORM 对象
        detections: 检测结果列表(归一化坐标)
        polygons: 该摄像头的 Polygon ORM 对象列表(enabled=True)

    Returns:
        violations: 业务违规事件列表
    """
    location = camera.location_type or "outdoor"
    violations = []

    for det in detections:
        cls_name = det.get("name", "")

        # 明火:无论装在哪里,出现即立即告警
        if cls_name == "明火":
            violations.append({
                "violation_type": "fire_alert",
                "risk_level": "high",
                "polygon_id": None,
                "detection": det,
                "reason": "检测到明火,可能存在火灾隐患",
            })
            continue

        # 电瓶车 + 电梯/单元门口:无 polygon 也立即告警
        if cls_name == "电瓶车":
            if location == "elevator":
                violations.append({
                    "violation_type": "ebike_in_elevator",
                    "risk_level": "high",
                    "polygon_id": None,
                    "detection": det,
                    "reason": "电瓶车进入电梯轿厢(消防安全)",
                })
                continue
            if location == "building_entrance":
                violations.append({
                    "violation_type": "ebike_in_entrance",
                    "risk_level": "high",
                    "polygon_id": None,
                    "detection": det,
                    "reason": "电瓶车进入单元门口/楼道",
                })
                continue

        # 其余类需要结合 polygon 判断
        v = _check_polygons(det, cls_name, polygons, location)
        if v:
            violations.append(v)

    return violations


def _check_polygons(det, cls_name, polygons, location) -> Optional[dict]:
    """按 polygon 类型 + 类别名 决定违规类型。"""
    box = det
    # 找出所有重叠的 polygon,按"告警优先级"判定
    matches = []
    for p in polygons:
        if not p.enabled:
            continue
        ratio = _box_polygon_overlap_ratio(box, p.points)
        if ratio < 0.2:
            continue
        matches.append((p, ratio))

    if not matches:
        return None

    # 优先级:消防通道 > 禁停 > 充电桩位 > 绿地 > 车位 > 通道
    PRIORITY = {
        "fire_lane": 0,
        "no_parking": 1,
        "charging_slot": 2,
        "lawn": 3,
        "elevator_zone": 4,
        "parking_slot": 5,
        "passage": 99,
    }
    matches.sort(key=lambda x: PRIORITY.get(x[0].polygon_type, 50))
    top_polygon, ratio = matches[0]
    ptype = top_polygon.polygon_type

    # === 消防通道 ===
    if ptype == "fire_lane":
        if cls_name == "车辆":
            return {
                "violation_type": "fire_lane_blocked",
                "risk_level": "high",
                "polygon_id": top_polygon.id,
                "detection": det,
                "reason": f"车辆停在消防通道[{top_polygon.name}]",
            }
        if cls_name == "电瓶车":
            return {
                "violation_type": "fire_lane_blocked",
                "risk_level": "high",
                "polygon_id": top_polygon.id,
                "detection": det,
                "reason": f"电瓶车停在消防通道[{top_polygon.name}]",
            }

    # === 禁停区 ===
    if ptype == "no_parking":
        if cls_name == "车辆":
            return {
                "violation_type": "illegal_parking",
                "risk_level": "mid",
                "polygon_id": top_polygon.id,
                "detection": det,
                "reason": f"车辆停在禁停区[{top_polygon.name}]",
            }
        if cls_name == "电瓶车":
            return {
                "violation_type": "ebike_illegal_park",
                "risk_level": "mid",
                "polygon_id": top_polygon.id,
                "detection": det,
                "reason": f"电瓶车停在禁停区[{top_polygon.name}]",
            }

    # === 充电桩车位 ===
    if ptype == "charging_slot":
        if cls_name == "车辆":  # 燃油车占电桩位
            return {
                "violation_type": "charging_slot_misuse",
                "risk_level": "mid",
                "polygon_id": top_polygon.id,
                "detection": det,
                "reason": f"燃油车占用充电车位[{top_polygon.name}]",
            }

    # === 绿地草坪 ===
    if ptype == "lawn":
        if cls_name in ("狗", "猫"):
            return {
                "violation_type": "pet_intrusion",
                "risk_level": "low",
                "polygon_id": top_polygon.id,
                "detection": det,
                "reason": f"宠物进入绿地[{top_polygon.name}]",
            }
        if cls_name == "行人":
            return {
                "violation_type": "human_intrusion",
                "risk_level": "low",
                "polygon_id": top_polygon.id,
                "detection": det,
                "reason": f"人员进入绿地[{top_polygon.name}]",
            }

    # === 合法车位 ===
    # 这里不告警,仅供 parking_stats 模块统计车位占用
    # 但 car 在 charging_slot 但不是电动车也算违规(上面 charging_slot 已处理)

    # === 通道 / 默认 ===
    # passage 类型只是地图分区,不产生违规
    return None


# ============ 乱丢垃圾的时序判定 ============

class LitterDetector:
    """乱丢垃圾需要时序判定:
       - 当前帧有 trash_bag/trash_item 出现
       - 30 秒内同位置(±100px)曾出现 person
       => 触发"乱丢垃圾"告警

    每个摄像头独立维护一个实例。
    """

    def __init__(self, time_window_sec=30, distance_threshold_norm=0.1):
        self.time_window = time_window_sec
        self.dist_thr = distance_threshold_norm
        # 每个摄像头独立的历史:list of (timestamp, person_center)
        self.person_history = []  # [(ts, (x, y)), ...]
        # 已告警的垃圾位置(避免重复告警)
        self.alerted_trash = set()  # set of "round_x_round_y" 字符串

    def check(self, detections: list, now_ts: float) -> list:
        """返回触发"乱丢垃圾"的违规事件列表。"""
        # 清理过期的人员历史
        self.person_history = [
            (ts, p) for ts, p in self.person_history if now_ts - ts < self.time_window
        ]

        violations = []
        for det in detections:
            cls = det.get("name", "")
            if cls == "行人":
                cx = (det["x1"] + det["x2"]) / 2
                cy = (det["y1"] + det["y2"]) / 2
                self.person_history.append((now_ts, (cx, cy)))
                continue

            if cls in ("弃置垃圾袋", "散落垃圾"):
                tcx = (det["x1"] + det["x2"]) / 2
                tcy = (det["y1"] + det["y2"]) / 2
                # 去重 key(0.05 精度)
                trash_key = f"{round(tcx, 2)}_{round(tcy, 2)}"
                if trash_key in self.alerted_trash:
                    continue
                # 查 30 秒内附近是否有人
                for _, (px, py) in self.person_history:
                    if abs(px - tcx) < self.dist_thr and abs(py - tcy) < self.dist_thr:
                        violations.append({
                            "violation_type": "litter",
                            "risk_level": "mid",
                            "polygon_id": None,
                            "detection": det,
                            "reason": f"检测到{cls},30 秒内同位置曾出现行人",
                        })
                        self.alerted_trash.add(trash_key)
                        break
        return violations
