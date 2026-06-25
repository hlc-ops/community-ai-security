# Roboflow Universe 下载清单(照着干)

> **目标**:今天 1-2 小时内下载 3000-5000 张已标注图,**零手工标注**完成 80% 数据准备
> **平台**:https://universe.roboflow.com/(免费,Google 登录)
>
> ⚠️ **架构说明**:本清单只下载 **YOLO 检测模型(8 类物体)** 的数据。
> 行为类业务(摔倒/翻墙/打架/跑步)走 **YOLOv8-pose 预训练模型 + 规则引擎**,
> **不需要在 Roboflow 下数据**,详见 `POSE_LAYER.md`。

---

## 一、YOLO 检测模型 · 8 类汇总

| ID | 类名 | 中文 | 业务用途 | 数据难度 |
|----|------|------|---------|---------|
| 0 | `person` | 行人 | 闯草坪、停留检测、姿态分析输入 | ⭐ 极易 |
| 1 | `car` | 车辆 | 违规停车 | ⭐ 极易 |
| 2 | `dog` | 狗 | 宠物违规 | ⭐⭐ 易 |
| 3 | `cat` | 猫 | 宠物违规 | ⭐⭐ 易 |
| 4 | `trash_bag` | 垃圾袋 | 乱丢垃圾 | ⭐⭐ 易 |
| 5 | `trash_item` | 散落垃圾 | 乱丢垃圾 | ⭐⭐⭐ 中 |
| 6 | `electric_bike` | 电瓶车 | 电梯禁入 + 违停 | ⭐⭐⭐ 中 |
| 7 | `fire` | 明火 | 消防隐患 | ⭐⭐ 易 |

**行为类业务(走 pose 路线,不在这下载)**:摔倒、翻越围栏、打架斗殴、异常奔跑

---

## 二、Roboflow 搜索关键词清单

### 🚗 类别 1:Car / 违停场景

**搜索词**(任选 2-3 个,挑下载数最多的下):
- `illegal parking`
- `vehicle detection`
- `car detection`
- `parking detection`

**目标**:下 500-1000 张

### 👤 类别 0:Person / 行人

**搜索词**:
- `person detection`
- `pedestrian detection`
- `human detection`
- `crowd detection`

**目标**:下 500-800 张(基础类,多多益善,后面 pose 也用得上)

### 🐕 类别 2-3:Dog & Cat / 宠物

**搜索词**:
- `dog cat detection`
- `pet detection`
- `dog detection`
- `cat detection`

**目标**:下 300-500 张

### 🗑️ 类别 4-5:Garbage / 垃圾

**搜索词**:
- `garbage detection`
- `trash detection`
- `litter detection`
- `waste detection`

**目标**:下 500-800 张

### 🛵 类别 6:Electric Bike / 电瓶车

**搜索词**:
- `electric bike detection`
- `e-bike detection`
- `electric scooter`
- `motorcycle detection`(部分把电瓶车归到摩托车)

**目标**:下 300-500 张

### 🔥 类别 7:Fire / 明火

**搜索词**:
- `fire detection`
- `flame detection`
- `fire smoke detection`

**目标**:下 300-500 张

---

## 三、Roboflow 下载操作 SOP

### Step 1:登录
1. https://universe.roboflow.com/
2. 右上角 **Sign In** → Google 账号

### Step 2:搜索 + 筛选
1. 输入关键词
2. **按 Downloads 排序**(右上角 Sort:Downloads ↓)
3. 挑 **Top 3** 下载数最多的

### Step 3:质量确认
进入项目页看 3 指标:
- **Images** ≥ 200
- **Classes** 1-5 个
- **Last Updated** 近 1 年
- **Sample Images** 真实(不是动画/简笔画)

### Step 4:下载
- **Download Dataset** → **Format: YOLOv8** → **不勾** "Show download code" → **Continue → Download Zip**

### Step 5:重命名归档
统一改名:
```
roboflow_parking_01.zip
roboflow_person_01.zip
roboflow_pet_01.zip
roboflow_garbage_01.zip
roboflow_ebike_01.zip
roboflow_fire_01.zip
```

全部放进:
```
D:\Python\PyCharm\PythonProject\智慧社区Web项目\dataset\downloads\
```

---

## 四、下载完成后告诉我

```
✅ illegal parking    — N 个 zip,约 X 张,类别名:car, motorbike
✅ person detection   — N 个 zip,约 X 张,类别名:person
✅ dog cat detection  — N 个 zip,约 X 张,类别名:dog, cat
✅ garbage detection  — N 个 zip,约 X 张,类别名:garbage, plastic
✅ electric bike      — N 个 zip,约 X 张,类别名:e-bike
✅ fire detection     — N 个 zip,约 X 张,类别名:fire, smoke
─────────────────────────────────────────
总计: N 个 zip,约 X 张
```

我拿到清单后,**5 分钟内**给你写自动合并脚本:
- 解压所有 zip
- 类名映射到我们 8 类
- 统一图片命名(`roboflow_000001.jpg`)
- 转 YOLO 格式入 `dataset/images/raw/`

---

## 五、注意事项

### ⚠️ Roboflow 类别名千奇百怪
- `car` 可能叫:`car / vehicle / Car / sedan / auto`
- `dog` 可能叫:`dog / Dog / canine / puppy`

**你不用管**,合并脚本会统一映射。

### ⚠️ License
- 选 **CC BY 4.0** 或 **Public Domain**
- **不要选** "License unspecified" 或付费的

### ⚠️ 数据多样性 > 单一来源
- 同一关键词搜出 5 个数据集,**不要全下**,选 Top 3,场景互补
- 比如 1 个室外、1 个室内、1 个夜景

---

## 六、时间预算

| 任务 | 耗时 |
|------|------|
| 注册 + 熟悉界面 | 10 分钟 |
| 搜索 + 下载 6 大类 | 50-70 分钟 |
| 重命名 + 整理 | 10 分钟 |
| 汇总表发我 | 1 分钟 |
| **我跑合并脚本(自动)** | 5 分钟 |

**总耗时:1.5-2 小时** → 5000 张已标注图就绪。

---

## 七、完成后状态

```
dataset/
├── downloads/                    ← 你的 zip(脚本读完可删)
│   ├── roboflow_parking_01.zip
│   ├── roboflow_garbage_01.zip
│   └── ...
└── images/raw/                   ← 脚本输出
    ├── roboflow_000001.jpg
    └── ...(5000 张图,统一命名)
└── labels/raw/
    └── roboflow_000001.txt       ← YOLO 格式
```

下一步:**训练**(W2,AutoDL 4090 跑 3-4 小时,¥10 左右)。

---

## 开始吧

打开 https://universe.roboflow.com/ → Sign In → 搜 `illegal parking` → 走 SOP。

有问题随时贴截图问。
