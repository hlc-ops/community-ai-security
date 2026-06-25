# Pose 行为分析层 · 设计文档

> **核心思想**:用预训练 YOLOv8-pose 提取人体关键点,后端规则引擎判断姿态语义,无需训练单独的"行为分类模型"。

---

## 一、整体架构

```
摄像头帧
   │
   ├──→ YOLOv8 检测模型(自训 8 类)──→ 物体类违规(违停/垃圾/宠物等)
   │
   └──→ YOLOv8-pose 模型(预训练)─┐
                                  │
                                  ▼
                          17 个人体关键点坐标
                                  │
                                  ▼
                          后端规则引擎(Python)
                                  │
                ┌─────────┬───────┴───────┬──────────┐
                ▼         ▼               ▼          ▼
              摔倒       翻墙            打架       跑步
            (水平规则)  (高度+姿态)    (多人交互)  (位移规则)
```

---

## 二、YOLOv8-pose 输出的 17 个关键点

按 COCO Keypoints 标准,顺序固定:

| ID | 关键点 | 中文 | 业务相关 |
|----|--------|------|---------|
| 0 | nose | 鼻子 | 头部位置 |
| 1 | left_eye | 左眼 | 头朝向 |
| 2 | right_eye | 右眼 | 头朝向 |
| 3 | left_ear | 左耳 | 头朝向 |
| 4 | right_ear | 右耳 | 头朝向 |
| 5 | left_shoulder | 左肩 | ⭐ 摔倒/翻墙关键 |
| 6 | right_shoulder | 右肩 | ⭐ 摔倒/翻墙关键 |
| 7 | left_elbow | 左肘 | 打架关键 |
| 8 | right_elbow | 右肘 | 打架关键 |
| 9 | left_wrist | 左手腕 | 翻墙/打架 |
| 10 | right_wrist | 右手腕 | 翻墙/打架 |
| 11 | left_hip | 左髋 | ⭐ 摔倒关键 |
| 12 | right_hip | 右髋 | ⭐ 摔倒关键 |
| 13 | left_knee | 左膝 | ⭐ 摔倒/翻墙 |
| 14 | right_knee | 右膝 | ⭐ 摔倒/翻墙 |
| 15 | left_ankle | 左脚踝 | 跑步 |
| 16 | right_ankle | 右脚踝 | 跑步 |

每个点输出 `(x, y, confidence)`,confidence < 0.3 视为不可见。

---

## 三、4 类行为的判断规则

### 3.1 摔倒检测 🚨

**核心规则**:肩-髋-膝**三点连线接近水平**

```python
def is_fallen(keypoints) -> bool:
    # 取躯干 3 个关键点的 y 坐标(图像 y 越大越靠下)
    shoulder_y = avg(kp[5].y, kp[6].y)
    hip_y      = avg(kp[11].y, kp[12].y)
    knee_y     = avg(kp[13].y, kp[14].y)
    
    # 三点 y 差值小 = 身体水平
    height_range = max(shoulder_y, hip_y, knee_y) - min(shoulder_y, hip_y, knee_y)
    body_height  = abs(shoulder_y - knee_y) or 1  # 防 0
    
    # 水平度 = 高度范围 / 体高,< 0.3 视为接近水平
    flatness = height_range / body_height
    
    return flatness < 0.3
```

**辅助规则**(降低误报):
- 头部低于髋部(头朝下)
- 持续 2 秒以上(避免蹲下、捡东西误报)
- 与历史姿态对比(突然倒下 vs 慢慢蹲下)

### 3.2 翻越围栏 🚨

**核心规则**:**人体位置 + 抬腿姿势**

```python
def is_climbing_fence(keypoints, fence_polygon) -> bool:
    # 1. 人体中心点在围栏区域上方
    center = midpoint(kp[11], kp[12])  # 髋部
    if not above(center, fence_polygon):
        return False
    
    # 2. 一条腿抬高(膝盖高于髋部)
    one_knee_above_hip = (
        kp[13].y < kp[11].y or  # 左膝高于左髋
        kp[14].y < kp[12].y     # 右膝高于右髋
    )
    
    # 3. 双手举高(手腕高于肩)
    hands_up = (
        kp[9].y < kp[5].y and
        kp[10].y < kp[6].y
    )
    
    return one_knee_above_hip and hands_up
```

**注意**:需要管理员预先在前端**配置围栏 polygon**(像工地项目里的电子围栏)。

### 3.3 打架斗殴 🥊

**核心规则**:**两人靠近 + 手臂动作**

```python
def is_fighting(person_a_kp, person_b_kp) -> bool:
    # 1. 两人距离 < 1.5 倍肩宽
    dist = distance(
        midpoint(person_a_kp[5], person_a_kp[6]),
        midpoint(person_b_kp[5], person_b_kp[6])
    )
    shoulder_width = distance(person_a_kp[5], person_a_kp[6])
    if dist > shoulder_width * 1.5:
        return False
    
    # 2. 至少一人手腕进入对方躯干区域
    a_torso = polygon(person_a_kp[5], person_a_kp[6], person_a_kp[11], person_a_kp[12])
    b_torso = polygon(person_b_kp[5], person_b_kp[6], person_b_kp[11], person_b_kp[12])
    
    return (
        in_polygon(person_b_kp[9], a_torso) or  # B 的左手伸进 A 躯干
        in_polygon(person_b_kp[10], a_torso) or # B 的右手
        in_polygon(person_a_kp[9], b_torso) or
        in_polygon(person_a_kp[10], b_torso)
    )
```

**辅助规则**:
- 持续 3 秒以上(避免握手/拥抱误报)
- 关键点运动剧烈(短时间内大幅位移)

### 3.4 异常奔跑(可选)

**核心规则**:**位移速度异常 + 跑步姿势**

```python
def is_running(current_kp, history_kps) -> bool:
    # 1. 髋部位移速度
    current_hip = midpoint(current_kp[11], current_kp[12])
    past_hip = midpoint(history_kps[-5][11], history_kps[-5][12])  # 5 帧前
    speed_px_per_frame = distance(current_hip, past_hip) / 5
    
    # 2. 跑步姿势:双脚交替离地高度差大
    foot_height_diff = abs(current_kp[15].y - current_kp[16].y)
    body_height = abs(current_kp[0].y - midpoint(current_kp[15], current_kp[16]).y)
    
    return speed_px_per_frame > 20 and foot_height_diff > body_height * 0.15
```

**业务用途**:深夜异常奔跑(逃跑、追逐)→ 安保告警

---

## 四、技术实现路径(W4-W5 实现)

### Step 1:接通 pose 模型(0.5 天)

```python
# backend/pose_detector.py
from ultralytics import YOLO

class PoseDetector:
    def __init__(self):
        self.model = YOLO("yolov8s-pose.pt")  # 自动下载
    
    def extract(self, image):
        """输入图,返回 [每个人的 17 个关键点]"""
        results = self.model.predict(image, verbose=False)
        return results[0].keypoints.xy.cpu().numpy()  # shape: (n_persons, 17, 2)
```

### Step 2:规则引擎(2-3 天)

```python
# backend/behavior_rules.py
class BehaviorAnalyzer:
    def __init__(self):
        self.history = deque(maxlen=30)  # 缓存最近 30 帧
    
    def analyze(self, all_persons_kp):
        events = []
        for person_kp in all_persons_kp:
            if self._is_fallen(person_kp):
                events.append({"type": "fall", "kp": person_kp})
            if self._is_climbing(person_kp):
                events.append({"type": "climb", "kp": person_kp})
            # ...
        
        # 多人交互
        if len(all_persons_kp) >= 2:
            for i in range(len(all_persons_kp)):
                for j in range(i+1, len(all_persons_kp)):
                    if self._is_fighting(all_persons_kp[i], all_persons_kp[j]):
                        events.append({"type": "fight", "kps": [...]})
        
        self.history.append(all_persons_kp)
        return events
```

### Step 3:接到主链路(0.5 天)

```python
# backend/stream.py
detection_results = yolo_detector.detect(frame)    # 物体类
pose_results = pose_detector.extract(frame)        # 关键点
behavior_events = behavior_analyzer.analyze(pose_results)  # 行为类

# 合并告警
all_violations = merge(detection_results, behavior_events)
```

---

## 五、数据需求总结

| 模型 | 数据需求 | 标注成本 |
|------|---------|---------|
| **YOLOv8 检测 8 类** | 5000 张物体图(person/car/dog/cat/trash/bike/fire) | 走 Roboflow,**零标注** |
| **YOLOv8-pose** | **不需要训练**,用预训练 | ✅ 零成本 |
| **规则引擎** | 不需要数据,写代码 | ✅ 零成本 |
| **(可选)pose fine-tune** | 200-500 张监控视角人体图 | 后期可选 |

---

## 六、面试时怎么讲(加分点)

> "我做了**分层检测架构**:
> - **第一层**:自训 YOLOv8 检测 8 类物体(人/车/动物/垃圾/电瓶车/明火),负责'看得见'的违规
> - **第二层**:预训练 YOLOv8-pose 提取人体关键点,**零训练成本**接入
> - **第三层**:Python 规则引擎用关键点判断行为语义(摔倒/翻墙/打架/异常奔跑)
> 
> **这种分层让模型最少、扩展最广**——新增'打架'我只要写一段规则代码,不用重训模型;新增'宠物追逐'我也只需加规则。比直接训一堆专用类的方案灵活 10 倍。"

---

## 七、可优化方向(V2)

- **行为分类网络**:用 SlowFast / ST-GCN 等时序模型替代规则,精度更高
- **pose fine-tune**:用监控视角数据微调 pose 模型
- **小样本扩展**:用 CLIP / BLIP-2 做 zero-shot 行为识别
- **多模态融合**:pose + 物体 + 时序联合训练

这些都不必现在做,**留作简历"未来工作"栏的谈资**。
