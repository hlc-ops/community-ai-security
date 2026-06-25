# 智慧社区 · 物业违规检测系统

> 基于 **YOLOv8 检测 + YOLOv8-pose 姿态分析 + LLM 兜底复核 + 业务规则引擎** 的智慧物业安全平台,覆盖违停、乱丢垃圾、宠物闯入、电瓶车违规、明火、翻越围栏、跌倒等社区高频违规场景。

![Status](https://img.shields.io/badge/Status-v0.3%20Ready-success)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask)
![Vue](https://img.shields.io/badge/Vue-3.4-4FC08D?logo=vue.js&logoColor=white)
![YOLO](https://img.shields.io/badge/YOLO-v8-00FFFF)
![OpenVINO](https://img.shields.io/badge/OpenVINO-INT8-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 项目定位

面向**物业 + 社区**场景的 AI 视频安防系统,商业目标:替代物业人工巡检,自动发现违停、乱丢垃圾、宠物闯入、明火、电瓶车进电梯等违规并联动工单 + 居民端通知。

### 与工地安防项目的差异点

| 维度 | 工地项目 | 智慧社区项目(本项目) |
|------|---------|---------------------|
| 业务侧 | 安全监管(强合规) | 物业服务 + 居民体验 |
| 检测对象 | 工人行为 | **行人 + 车辆 + 动物 + 物体**(8 类)|
| 技术亮点 | YOLO + LLM 双保险 | **YOLO + 姿态分析 + LLM 自动复核 + 8 类检测** |
| 终端形态 | 后端 + PC 工作站 | 后端 + PC 大屏 + **居民 H5 扫码端** |

---

## V3 模型(2026-06-21 训练)

| 指标 | 数值 |
|---|---|
| 模型 | YOLOv8s · 11.1M 参数 |
| 训练集 | **36,459 张图**(29167 train / 3645 val / 3647 test)|
| 类别数 | 8(person / car / dog / cat / trash_bag / trash_item / electric_bike / fire)|
| 数据源 | Roboflow 38 个数据集 + **VisDrone2019**(无人机俯拍多目标街景)|
| 增强策略 | Mosaic 1.0 + Copy-Paste 0.3 + MixUp 0.15 + HSV |
| 训练耗时 | 5.27 h(RTX 4090,100 epoch)|
| mAP@0.5 | **0.772**(在含 30% 高难 VisDrone 俯拍小目标的 val 集上)|
| mAP@0.5:0.95 | 0.563 |
| 部署格式 | OpenVINO **INT8**(11 MB)+ FP32(43 MB)备份 |

---

## 8 类检测覆盖 7 大业务违规

| 业务违规 | 检测方式 | 涉及类 |
|---------|---------|--------|
| **违规停车** | 检测 car + 消防通道 polygon 电子围栏 | car |
| **乱丢垃圾** | 检测 trash_bag/trash_item + 区域分布 | trash_bag, trash_item |
| **宠物闯入草坪** | 检测 dog/cat + 草坪 polygon | dog, cat |
| **电瓶车进电梯/楼道** | 检测 electric_bike + 室内 polygon | electric_bike |
| **明火预警(消防)** | 检测 fire,任意检出即告警 | fire |
| **跌倒检测** | YOLOv8-pose 17 关键点 + 水平度规则 | person + pose |
| **翻越围栏** | YOLOv8-pose + 高度/姿态匹配围栏 polygon | person + pose |

---

## 三层"AI 检测安全网"

```
┌────────────────────────────────────────────────────────┐
│ L1  YOLO 实时检测(主用,INT8,CPU 15-30ms/帧)        │
│     ▼ 如检出 → 走业务规则引擎判定违规                  │
│ L2  YOLOv8-pose 姿态规则(摔倒 / 翻墙等行为)          │
│     ▼ 如 L1 未检出 但场景未必安全(空检场景)         │
│ L3  LLM 自动安全复核(Qwen-VL 兜底,频率限制 5 min/3 次)│
│     ▼ "这真的是安全场景吗?"  防止 YOLO 漏识         │
│ →   多模型互补 + 频率经济模型,避免 LLM Token 浪费     │
└────────────────────────────────────────────────────────┘
```

---

## 系统组成

### 后端(Flask 3 + SQLite + OpenVINO)

12 个 API 蓝图,覆盖完整业务闭环:

| 蓝图 | 路由前缀 | 职责 |
|------|---------|------|
| auth | `/api/auth` | JWT 登录、注册、权限 |
| detect | `/api/detect` | 图像/视频/RTSP 检测 + LLM 兜底 |
| records | `/api/records` | 违规记录 CRUD + 截图 |
| events | `/api/events` | 实时事件流(SSE)|
| cameras | `/api/cameras` | 摄像头管理 + polygon 配置 |
| stream | `/api/stream` | 视频流接入(MJPEG / HLS)|
| llm | `/api/llm` | 工单文案 + 物业建议 |
| settings | `/api/settings` | 系统参数 + LLM 复核开关 |
| reports | `/api/reports` | 统计报表 + 趋势分析 |
| audit | `/api/audit` | 操作审计日志 |
| users | `/api/users` | 用户管理(管理员)|
| public | `/api/public` | **居民端公开 API**(免登录扫码用)|

### 前端(Vue 3 + Vite + Pinia + Element Plus + ECharts)

15 个页面,覆盖物业 PC 端 + 居民 H5:

```
管理大屏       Cockpit / Dashboard / Reports
检测入口       ImageDetect / VideoDetect / CameraDetect / RtspDetect
管理后台       Cameras / RecordList / AuditLog / UserManage / Settings
回放/审计      VideoReplay
居民端 H5      H5Community(扫码即用,4 个公开 API)
```

---

## 快速启动

### 环境要求

- Python 3.10+(项目实测 3.13.5)
- Node.js 20+
- Windows / Linux(开发环境 Win11,部署支持 Linux 边缘工控机)
- (可选)NVIDIA GPU — 推理用 OpenVINO INT8,CPU 即可

### 后端

```powershell
# 1. 装依赖(项目固定用 D:/Python/Python/python.exe,避免代理问题)
D:\Python\Python\python.exe -m pip install -r requirements.txt

# 2. 启动(默认 http://localhost:5000)
D:\Python\Python\python.exe run.py
```

模型加载顺序(`backend/config.py`):
1. `model/best_openvino_model/` — INT8 主用(11 MB,CPU 推理)
2. `model/best_openvino_model_fp32/` — FP32 备份
3. `model/best.pt` — PyTorch 原始

### 前端

```bash
cd frontend
npm install
npm run dev   # 默认 http://localhost:5173
```

### 默认管理员

启动时自动创建:用户名 `hlc`,密码可通过环境变量 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 自定义。

---

## 项目结构

```
智慧社区Web项目/
├── backend/
│   ├── blueprints/          # 12 个 API 蓝图
│   ├── config.py            # MODEL_PATH 自动路由 INT8/FP32/PT
│   ├── detector.py          # YOLO 检测器封装
│   ├── pose_detector.py     # YOLOv8-pose 姿态分析
│   ├── llm.py               # LLM 工单 + 安全自动复核
│   ├── models.py            # SQLAlchemy 数据模型
│   └── rules/               # 业务规则引擎(8 类 → 7 违规)
├── frontend/
│   └── src/
│       ├── views/           # 15 个页面
│       ├── components/      # PolygonEditor / ParkingMap 等
│       └── stores/          # Pinia 状态管理
├── model/
│   ├── best_openvino_model/       # V3 INT8(主用)
│   ├── best_openvino_model_fp32/  # V3 FP32 备份
│   ├── best.pt                    # V3 PyTorch 原始
│   ├── best_v2_backup.pt          # V2 回滚备份
│   └── best_v1_backup.pt          # V1 回滚备份
├── scripts/                 # 训练 / 数据合并 / 转换 / 回归脚本
│   ├── merge_datasets.py    # 38 数据集 → V3 平衡集
│   ├── convert_visdrone_to_8class.py  # VisDrone → 8 类
│   ├── regression_test_v3.py
│   └── ...
├── data/                    # 运行时数据(截图 / 日志 / SQLite)
├── docs/                    # 类别定义、标注规范、AutoDL 训练指南
└── README.md
```

---

## 模型训练流程

V3 完整训练 pipeline 见 [`docs/AUTODL_RETRAIN_V2.md`](docs/AUTODL_RETRAIN_V2.md)(可复用):

```
1. 数据收集     Roboflow 38 数据集 + VisDrone2019-DET (val/train/test-dev)
2. 类映射验证   scripts/peek_old_garbage.py + inspect_new_datasets.py
3. VisDrone 转换 scripts/convert_visdrone_to_8class.py
4. 数据集打包   scripts/package_visdrone_for_merge.py
5. 合并 + 采样   scripts/merge_datasets.py
6. AutoDL 训练   RTX 4090 / yolov8s.pt / 100 epoch / mosaic+copy_paste+mixup
7. 下载 + 部署   解压 → 替换 best.pt → 导 OpenVINO INT8 → 回归测试
```

---

## 文档

- [类别定义与标注规范](docs/CLASSES.md)
- [数据集收集指南](docs/DATASET_COLLECTION.md)
- [AutoDL 训练手册](docs/AUTODL_TRAINING_GUIDE.md)
- [AutoDL 重训手册(V2/V3 复用)](docs/AUTODL_RETRAIN_V2.md)
- [Pose 行为层规则](docs/POSE_LAYER.md)

---

## 演进路线

- [x] 立项 + 8 类业务设计(7 类社区违规)
- [x] 数据集收集(38 个 Roboflow + VisDrone)
- [x] V1 训练 24,632 张,mAP@0.5 = 0.901
- [x] V2 训练 19,396 张,mAP@0.5 = 0.910(4 个 bug 修复)
- [x] **V3 训练 36,459 张(VisDrone 多目标融入),mAP@0.5 = 0.772**
- [x] 后端 12 蓝图 + 业务规则引擎
- [x] 前端 15 页面 + 居民端 H5
- [x] LLM 集成(Qwen-Plus 工单文案)
- [x] **LLM 自动安全复核(YOLO 空检 → LLM 兜底,频率限制 5min/3 次)**
- [x] OpenVINO INT8 部署(11 MB,CPU 推理)
- [ ] 演示视频
- [ ] GitHub 公开发布

---

## License

MIT License
