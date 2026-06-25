"""姿态行为分析引擎。

输入:pose_detector.extract() 返回的人体关键点列表
输出:行为违规事件列表

4 个行为规则:
  - 摔倒(fall):肩-髋-膝水平度判定
  - 翻越围栏(fence_climb):人体位置 + 抬腿 + 举高
  - 打架斗殴(fighting):两人靠近 + 手腕进入对方躯干
  - 异常奔跑(running):配合 stream 时序,这里只判定姿态特征

设计原则:
  1. 规则化判定,可解释,易调优
  2. 单帧 + 多帧时序结合(单例 PoseBehaviorAnalyzer 维护历史)
  3. 阈值经过常识标定,实际部署需根据真实摄像头微调
"""
import time
from collections import deque

from .pose_detector import get, midpoint, distance


class PoseBehaviorAnalyzer:
    """姿态行为分析器(每个摄像头独立实例,维护时序状态)。

    使用方法:
        analyzer = PoseBehaviorAnalyzer()
        # 每帧调用:
        events = analyzer.analyze(persons, fence_polygons=None)
        for e in events:
            print(e)  # {"type": "fall", "person_idx": 0, "reason": "..."}
    """

    HISTORY_MAXLEN = 60         # 缓存最近 60 帧(~6 秒,10fps 检测)
    # 阈值已根据真实场景放宽(单图判定更易触发,代价是误报增加)
    FALL_FLATNESS_THR = 0.55    # 肩-髋-膝高度差/体长 < 此值 = 接近水平
    FALL_DURATION_SEC = 1.5     # 视频流持续多久确认摔倒
    FIGHT_DIST_RATIO = 2.0      # 两人距离 / 肩宽 < 此 = 靠近
    FIGHT_DURATION_SEC = 1.5    # 打架需持续才算
    RUN_SPEED_NORM_THR = 0.015  # 归一化髋部位移速度阈值(每帧)
    RUN_FOOT_DIFF_THR = 0.06    # 双脚高度差 / 体高 > 此 = 跑步姿势

    def __init__(self):
        # 全部历史(timestamp, persons_list)
        self.history = deque(maxlen=self.HISTORY_MAXLEN)
        # 每个候选事件的持续计时:{event_key: started_at_ts}
        self._fall_starts = {}     # {person_idx: start_ts}
        self._fight_starts = {}    # {(i, j): start_ts}
        self._reported = set()     # 已经报过的事件 key,避免重复推送

    # ============ 单帧判定 ============

    def _is_fallen_pose(self, kps, person_bbox=None) -> bool:
        """单帧:是否摔倒姿态。

        指标计分法:不只看"水平躯干"一个 pattern,把摔倒拆成 5 个独立指标:
          1. 三点接近水平(flatness 低)
          2. 头部低于髋部(趴姿/面朝下)
          3. bbox 扁(宽 > 高,横躺/侧躺)
          4. 头与肩持平(站立时头高于肩)
          5. 髋低于膝盖一定比例(跪坐倒地)
        任意 ≥ 2 个指标触发 = 摔倒。
        """
        ls, rs = get(kps, "left_shoulder"), get(kps, "right_shoulder")
        lh, rh = get(kps, "left_hip"), get(kps, "right_hip")
        lk, rk = get(kps, "left_knee"), get(kps, "right_knee")
        nose = get(kps, "nose")

        # 关键点缺失太多不判定
        present = sum(1 for p in [ls, rs, lh, rh] if p)
        if present < 2:
            return False

        shoulder = midpoint(ls, rs) if (ls and rs) else (ls or rs)
        hip = midpoint(lh, rh) if (lh and rh) else (lh or rh)
        knee = midpoint(lk, rk) if (lk and rk) else (lk or rk)

        if not (shoulder and hip):
            return False

        score = 0
        reasons = []

        # 指标 1:三点接近水平
        if knee:
            ys = [shoulder["y"], hip["y"], knee["y"]]
            height_range = max(ys) - min(ys)
            body_length = distance(shoulder, knee) or 0.01
            flatness = height_range / body_length
            if flatness < self.FALL_FLATNESS_THR:
                score += 1
                reasons.append("水平躯干")

        # 指标 2:头低于髋(趴姿/面朝下/前倾)
        if nose and hip:
            if nose["y"] > hip["y"] - 0.05:
                score += 1
                reasons.append("头低于髋")

        # 指标 3:bbox 扁(宽 > 高,横躺/侧躺)
        if person_bbox:
            x1, y1, x2, y2 = person_bbox
            box_w = x2 - x1
            box_h = y2 - y1
            if box_h > 0 and box_w / box_h > 1.1:
                score += 1
                reasons.append("bbox 宽大于高")

        # 指标 4:头与肩持平(摔倒时头通常不会显著高于肩)
        if nose:
            if shoulder["y"] - nose["y"] < 0.04:  # 头几乎与肩同高
                score += 1
                reasons.append("头与肩持平")

        # 指标 5:髋低于膝(跪坐倒地)
        if knee and hip:
            if hip["y"] > knee["y"] + 0.03:
                score += 1
                reasons.append("髋低于膝")

        # 任意 2 个指标 = 摔倒
        self._last_fall_reasons = reasons
        return score >= 2

    def _is_climbing_pose(self, kps, fence_polygons=None, person_bbox=None) -> bool:
        """单帧:是否翻墙姿态。

        指标计分法,覆盖 5 种典型翻墙姿势:
          1. 抬腿(膝高于髋)— 跨栏/翻越
          2. 举手(手腕高于肩)— 抓栏杆/向上攀爬
          3. 双手紧靠(< 0.15 体宽)— 双手抓栏杆
          4. 一腿明显高于另一腿(差 > 0.15)— 跨栏一腿过去
          5. 上身前倾(头超出髋部前方)— 弯腰攀爬
          6. 双膝弯曲(膝盖明显高于脚踝中位)— 蹲式攀爬
        任意 ≥ 2 个指标 = 翻墙。
        """
        ls, rs = get(kps, "left_shoulder"), get(kps, "right_shoulder")
        lw, rw = get(kps, "left_wrist"), get(kps, "right_wrist")
        lh, rh = get(kps, "left_hip"), get(kps, "right_hip")
        lk, rk = get(kps, "left_knee"), get(kps, "right_knee")
        la, ra = get(kps, "left_ankle"), get(kps, "right_ankle")
        nose = get(kps, "nose")

        # 至少要有肩和髋
        if not ((ls or rs) and (lh or rh)):
            return False

        shoulder = midpoint(ls, rs) if (ls and rs) else (ls or rs)
        hip = midpoint(lh, rh) if (lh and rh) else (lh or rh)
        if not (shoulder and hip):
            return False

        body_width = distance(ls, rs) if (ls and rs) else 0.1

        # ===== 前置过滤:髋部太接近 bbox 底部 = 坐姿/屁股着地 =====
        if person_bbox:
            x1, y1, x2, y2 = person_bbox
            box_h = y2 - y1
            if box_h > 0 and (hip["y"] - y1) / box_h > 0.82:
                self._last_climb_reasons = ["髋部太接近 bbox 底部(坐姿)"]
                return False

        # ===== 核心指标(必须至少 1 个,否则不可能是翻墙)=====
        core_score = 0
        aux_score = 0
        reasons = []

        # 核心 1:真正的抬腿翻越 = 膝显著高于髋(差>0.10) AND 同侧踝跟着抬高(踝-膝差<0.20)
        # 屁股着地的人也满足"膝高于髋",但脚平放 → 踝远低于膝(差>0.25),这条排除坐姿
        leg_lifted = False
        if lk and lh and la:
            knee_above_hip = lk["y"] < lh["y"] - 0.10
            ankle_follows = (la["y"] - lk["y"]) < 0.20
            if knee_above_hip and ankle_follows:
                leg_lifted = True
        if rk and rh and ra:
            knee_above_hip = rk["y"] < rh["y"] - 0.10
            ankle_follows = (ra["y"] - rk["y"]) < 0.20
            if knee_above_hip and ankle_follows:
                leg_lifted = True
        if leg_lifted:
            core_score += 1
            reasons.append("抬腿+脚抬(核心)")

        # 核心 2:举手 — 任一手腕显著高于肩(向上抓握)
        hands_up = False
        if lw and ls and lw["y"] < ls["y"] - 0.05:
            hands_up = True
        if rw and rs and rw["y"] < rs["y"] - 0.05:
            hands_up = True
        if hands_up:
            core_score += 1
            reasons.append("举手(核心)")

        # ===== 一票否决:没有任何垂直方向极端动作 → 不可能翻墙 =====
        if core_score == 0:
            self._last_climb_reasons = ["缺少抬腿/举手"]
            return False

        # ===== 辅助指标(支持核心,不能单独触发)=====

        # 辅助 1:双手紧靠(< 0.4 倍体宽)= 抓栏杆
        if lw and rw:
            hand_dist = distance(lw, rw)
            if 0 < hand_dist < body_width * 0.4:
                aux_score += 1
                reasons.append("双手紧靠")

        # 辅助 2:一腿明显高于另一腿(差 > 0.2)= 跨栏一腿过去
        if lk and rk:
            if abs(lk["y"] - rk["y"]) > 0.2:
                aux_score += 1
                reasons.append("两腿高度差大")

        # 辅助 3:上身前倾(头部 x 显著偏离髋部 x)= 弯腰
        if nose and hip:
            if abs(nose["x"] - hip["x"]) > body_width * 1.0:
                aux_score += 1
                reasons.append("上身前倾")

        # 辅助 4:双膝弯曲 + 上身在腰部以上(蹲爬,但要排除坐姿)
        # 拳击姿势/坐姿/屈膝都是双膝弯曲,所以这条要严格:
        # 必须膝盖比脚踝高 0.08 以上,且躯干长(肩高于髋显著)
        if lk and la and rk and ra and shoulder and hip:
            knee_y = (lk["y"] + rk["y"]) / 2
            ankle_y = (la["y"] + ra["y"]) / 2
            torso_height = hip["y"] - shoulder["y"]
            if ankle_y - knee_y > 0.08 and torso_height > 0.15:
                aux_score += 1
                reasons.append("攀爬式弯膝")

        # ===== 最终决策:核心 ≥ 1 且 总分 ≥ 2 =====
        total = core_score + aux_score
        self._last_climb_reasons = reasons
        if total < 2:
            return False

        # 如果有围栏 polygon,人体髋部应该在围栏上方
        if fence_polygons:
            hip_y = hip["y"]
            hip_x = hip["x"]
            for poly in fence_polygons:
                pts = poly.get("points") if isinstance(poly, dict) else poly
                if not pts:
                    continue
                ys = [p[1] for p in pts]
                xs = [p[0] for p in pts]
                if min(xs) <= hip_x <= max(xs) and hip_y < (min(ys) + max(ys)) / 2:
                    return True
            return False

        return True

    def _is_fighting_pair(self, kps_a, kps_b) -> bool:
        """单帧:两人是否打架姿态。

        新版本(更鲁棒):
          - 主要信号:任一人的手腕落入对方躯干(扩张 30%)
          - 辅助信号:两人足够靠近(距离 < 3 倍肩宽)
          - 任何一个手腕真的"打过去"了 → 触发
        """
        las, ras = get(kps_a, "left_shoulder"), get(kps_a, "right_shoulder")
        lah, rah = get(kps_a, "left_hip"), get(kps_a, "right_hip")
        lbs, rbs = get(kps_b, "left_shoulder"), get(kps_b, "right_shoulder")
        lbh, rbh = get(kps_b, "left_hip"), get(kps_b, "right_hip")
        law, raw = get(kps_a, "left_wrist"), get(kps_a, "right_wrist")
        lbw, rbw = get(kps_b, "left_wrist"), get(kps_b, "right_wrist")

        if not (las and ras and lbs and rbs):
            return False

        # 1. 距离 / 肩宽(放宽到 3 倍,挥拳时身体保持一定距离)
        center_a = midpoint(las, ras)
        center_b = midpoint(lbs, rbs)
        dist = distance(center_a, center_b)
        sw_a = distance(las, ras)
        sw_b = distance(lbs, rbs)
        avg_sw = (sw_a + sw_b) / 2 or 1
        if dist > avg_sw * 3.0:  # 太远不是打架
            return False

        # 2. 计算躯干 bbox(向外扩张 30%,容忍手腕略超躯干)
        def torso_bbox(ls, rs, lh, rh, expand=0.3):
            xs = [p["x"] for p in [ls, rs, lh, rh] if p]
            ys = [p["y"] for p in [ls, rs, lh, rh] if p]
            if not xs or not ys:
                return None
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            w = x2 - x1
            h = y2 - y1
            return (x1 - w * expand, y1 - h * expand,
                    x2 + w * expand, y2 + h * expand)

        def in_bbox(p, bbox):
            if not p or not bbox:
                return False
            x1, y1, x2, y2 = bbox
            return x1 <= p["x"] <= x2 and y1 <= p["y"] <= y2

        a_torso = torso_bbox(las, ras, lah, rah)
        b_torso = torso_bbox(lbs, rbs, lbh, rbh)

        # 任一手腕落在对方扩张躯干内
        intrude = (
            in_bbox(law, b_torso) or in_bbox(raw, b_torso) or
            in_bbox(lbw, a_torso) or in_bbox(rbw, a_torso)
        )
        return intrude

    def _is_running_pose(self, kps, prev_kps=None, frames_passed=1) -> bool:
        """单帧 + 上一帧:是否奔跑。

        条件:
          - 髋部位移速度大
          - 双脚高度差大(交替离地)
        """
        lh, rh = get(kps, "left_hip"), get(kps, "right_hip")
        la, ra = get(kps, "left_ankle"), get(kps, "right_ankle")
        ls = get(kps, "left_shoulder")
        if not (lh and rh and la and ra):
            return False

        # 1. 双脚高度差 / 体高
        foot_diff = abs(la["y"] - ra["y"])
        if ls:
            body_height = abs(ls["y"] - max(la["y"], ra["y"])) or 1
            if foot_diff / body_height < self.RUN_FOOT_DIFF_THR:
                return False

        # 2. 髋部位移速度(需要上一帧)
        if prev_kps:
            prev_lh = get(prev_kps, "left_hip")
            prev_rh = get(prev_kps, "right_hip")
            if prev_lh and prev_rh:
                prev_hip = midpoint(prev_lh, prev_rh)
                curr_hip = midpoint(lh, rh)
                speed_per_frame = distance(prev_hip, curr_hip) / max(1, frames_passed)
                if speed_per_frame < self.RUN_SPEED_NORM_THR:
                    return False
                return True

        return False

    # ============ 多帧时序判定 ============

    def analyze(self, persons, fence_polygons=None) -> list:
        """主入口:输入当前帧的所有人,输出本帧产生的行为事件。

        Args:
            persons: pose_detector.extract() 输出的归一化关键点列表
                     每个 person 用 keypoints_norm 字段
            fence_polygons: [{points: [[x,y],...]},...] 围栏区域

        Returns:
            events: [{type, person_idx, reason, polygon_id}, ...]
        """
        now = time.time()
        # 取归一化关键点
        person_kps = [p.get("keypoints_norm", []) for p in persons]
        self.history.append((now, person_kps))

        events = []

        # === 摔倒判定(单帧 + 持续时间)===
        currently_fallen = set()
        for i, kps in enumerate(person_kps):
            if self._is_fallen_pose(kps):
                currently_fallen.add(i)
                if i not in self._fall_starts:
                    self._fall_starts[i] = now
                elif now - self._fall_starts[i] >= self.FALL_DURATION_SEC:
                    key = f"fall_{i}_{int(self._fall_starts[i])}"
                    if key not in self._reported:
                        events.append({
                            "type": "fall",
                            "person_idx": i,
                            "reason": "人体姿态接近水平且持续超过 1.5 秒,疑似摔倒",
                            "risk_level": "high",
                            "polygon_id": None,
                        })
                        self._reported.add(key)
        # 清理不再摔倒的人计时
        for i in list(self._fall_starts.keys()):
            if i not in currently_fallen:
                self._fall_starts.pop(i, None)

        # === 翻墙判定(单帧即触发)===
        for i, kps in enumerate(person_kps):
            if self._is_climbing_pose(kps, fence_polygons):
                key = f"climb_{i}_{int(now)}"
                if key not in self._reported:
                    events.append({
                        "type": "fence_climbing",
                        "person_idx": i,
                        "reason": "检测到抬腿 + 双手举高姿态,疑似翻越围栏",
                        "risk_level": "high",
                        "polygon_id": None,
                    })
                    self._reported.add(key)

        # === 打架判定(两两 + 持续时间)===
        currently_fighting = set()
        for i in range(len(person_kps)):
            for j in range(i + 1, len(person_kps)):
                if self._is_fighting_pair(person_kps[i], person_kps[j]):
                    pair = (i, j)
                    currently_fighting.add(pair)
                    if pair not in self._fight_starts:
                        self._fight_starts[pair] = now
                    elif now - self._fight_starts[pair] >= self.FIGHT_DURATION_SEC:
                        key = f"fight_{i}_{j}_{int(self._fight_starts[pair])}"
                        if key not in self._reported:
                            events.append({
                                "type": "fighting",
                                "person_idx": [i, j],
                                "reason": "两人持续靠近且手腕进入对方躯干区域,疑似打架斗殴",
                                "risk_level": "high",
                                "polygon_id": None,
                            })
                            self._reported.add(key)
        for pair in list(self._fight_starts.keys()):
            if pair not in currently_fighting:
                self._fight_starts.pop(pair, None)

        # === 奔跑判定(对比上一帧)===
        if len(self.history) >= 2:
            prev_ts, prev_persons = self.history[-2]
            for i, kps in enumerate(person_kps):
                prev_kps = prev_persons[i] if i < len(prev_persons) else None
                if self._is_running_pose(kps, prev_kps, frames_passed=1):
                    key = f"run_{i}_{int(now)}"
                    if key not in self._reported:
                        events.append({
                            "type": "running",
                            "person_idx": i,
                            "reason": "髋部位移异常 + 双脚交替明显,疑似异常奔跑",
                            "risk_level": "mid",
                            "polygon_id": None,
                        })
                        self._reported.add(key)

        # 清理过期 reported(每 60 秒)
        if len(self._reported) > 200:
            self._reported.clear()

        return events


# ============ 行为类型 → 业务违规映射 ============
# 用于把 PoseBehaviorAnalyzer 的输出整合到 DetectionRecord 的 violation_type

BEHAVIOR_TO_VIOLATION = {
    "fall":           "fall_detected",
    "fence_climbing": "fence_climbing",
    "fighting":       "fighting",
    "running":        "abnormal_running",
}

# 用于 to_dict 的中文标签(同步加入 DetectionRecord.VIOLATION_ZH)
BEHAVIOR_VIOLATION_ZH = {
    "fall_detected":    "跌倒告警",
    "fence_climbing":   "翻越围栏",
    "fighting":         "打架斗殴",
    "abnormal_running": "异常奔跑",
}
