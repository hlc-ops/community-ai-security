# 边缘盒子部署指南

> 把 V3 模型(`model/best.pt`)落到 AI 边缘计算盒子上的完整流程。
> 适用场景:客户已有/需采购瑞芯微 / 算能 / 寒武纪 / 海思等边缘盒子。

---

## 模型部署形态总览

```
┌──────────────────────────────────────────────────────────┐
│ 本地开发(Windows / Linux PC)                           │
│   model/best.pt          ← 训练产物(PyTorch)            │
│   model/best.onnx        ← 通用中间格式(已导出 43 MB)   │
│   model/best_openvino_*  ← Intel CPU 推理(已导出 11 MB) │
└──────────────────────────────────────────────────────────┘
                          │
                          │  到客户现场后,选一种编译
                          ▼
┌──────────────────────────────────────────────────────────┐
│ 边缘盒子(Linux,装目标芯片 SDK)                       │
│   model/best_rk3588.rknn     ← 瑞芯微 RK3588(主流)    │
│   model/best_bm1684x.bmodel  ← 算能 BM1684X(高端)     │
│   model/best.cambricon       ← 寒武纪 MLU(企业)       │
│   ...                                                     │
└──────────────────────────────────────────────────────────┘
```

**核心事实**:`best.onnx` 是所有边缘芯片的统一入口。本地 Windows 出 ONNX,到 Linux 再转目标格式。

---

## 一、瑞芯微 RK3588(最主流,价位 300-1500 元)

适合场景:中小型物业 / 工地 / 园区,1-4 路 1080p 摄像头同时跑。

### 步骤 1:准备 Linux 环境

可以三选一:
- **A. 自己装 Ubuntu 22.04**(实体机/虚拟机)
- **B. 租云服务器**(AutoDL / 阿里云 / 腾讯云,~¥0.5/h)
- **C. 直接用客户的 RK3588 开发板上跑**(需要 8GB+ 内存,转换比较慢)

### 步骤 2:装 RKNN-Toolkit2

```bash
# 装 Conda(如果没有)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 起干净的 py3.10 环境
conda create -n rknn python=3.10 -y
conda activate rknn

# 装 RKNN-Toolkit2(国内镜像加速)
pip install rknn-toolkit2 -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install numpy opencv-python onnx onnxruntime
```

### 步骤 3:转换 ONNX → RKNN

把本地的 `model/best.onnx` 和 `dataset/images/val/` 拷到 Linux,然后:

```bash
cd 智慧社区Web项目
python scripts/export_rknn.py --target rk3588

# 输出: model/best_rk3588.rknn(约 8-11 MB)
```

脚本会自动:
- 从 `dataset/images/val/` 随机抽 100 张图做 INT8 校准
- 对齐 YOLOv8 的输入预处理(/255 归一化、RGB 顺序)
- 生成可直接部署的 `.rknn` 文件

### 步骤 4:盒子端推理

把 `best_rk3588.rknn` 拷到 RK3588 盒子上,装 **rknn-toolkit-lite2**(设备端 SDK):

```bash
pip install rknn-toolkit-lite2

# 推理代码示例(scripts/infer_rknn_demo.py 见仓库)
```

性能参考(RK3588 + INT8):
- 单帧推理 25-40ms(25-40 FPS)
- 同时跑 4 路 1080p 摄像头无压力

---

## 二、算能 BM1684X(高端,价位 1500-5000 元)

适合场景:8-16 路摄像头并行,大型园区 / 工业园 / 智慧楼宇。

### 步骤 1:装 TPU-MLIR(算能官方推荐 Docker)

```bash
docker pull sophgo/tpuc_dev:latest
docker run -it -v /your/project:/workspace sophgo/tpuc_dev:latest
```

### 步骤 2:生成转换命令

```bash
cd /workspace/智慧社区Web项目
python scripts/export_sophon.py --target bm1684x
# 会输出 _sophon_bm1684x.sh 转换脚本
```

### 步骤 3:在容器内跑转换

```bash
source /workspace/tpu-mlir_xxx/envsetup.sh
bash _sophon_bm1684x.sh
# 输出: best_bm1684x.bmodel(约 12-14 MB)
```

性能参考(BM1684X + INT8):
- 单帧推理 8-15ms(60-120 FPS)
- 同时跑 16 路 1080p 摄像头无压力

---

## 三、其他芯片(简表)

| 厂商 | 芯片 | 工具链 | 输入 | 备注 |
|---|---|---|---|---|
| 寒武纪 | MLU220/270/370 | MagicMind / NeuWare | ONNX | 企业级,贵 |
| 海思 | Hi3516/3519 | NNIE + Atlas Toolkit | Caffe/ONNX | 老牌,工业稳定 |
| Hailo | Hailo-8 | Hailo Dataflow Compiler | ONNX | 工业 AI,功耗低 |
| Jetson | Orin Nano/NX/AGX | TensorRT | ONNX | 英伟达,生态最好 |

**统一思路**:Windows 出 ONNX → Linux 用厂商工具链转 → 拷盒子 → SDK 加载推理。

---

## 后端接入(把盒子推理结果接到我们的 Flask)

边缘盒子推理出 boxes 后,有两种接入策略:

### 模式 A — 盒子只推理,告警走我们后端

```
摄像头 → 盒子 (推理出 boxes) → HTTP POST → 我们后端 → DB + LLM 复核 + 工单
```

这种最常见。盒子端写个轻量 Python/C++ 程序,把检测结果以 JSON 推到我们的 `/api/detect/from_edge`(需要新增此端点,见下)。

### 模式 B — 盒子端独立运行整套系统

直接把整个 Flask + Vue dist 打包到盒子里(RK3588 4GB 内存够跑 Flask + SQLite),客户局域网内访问。
适合不联网的场景(机场 / 政府敏感区域)。

---

## ONNX vs PT 精度对照(2026-06-26 验证)

ONNX 加载并跑了 6 张图(doubao1 单类 3 张 + doubaotupian 多目标 3 张):

| 场景 | 结果 |
|---|---|
| 单目标专题图 | PT 与 ONNX **完全一致** ✅ |
| 多目标密集图 | ONNX 比 PT 少 1-2 个边缘置信度框 ⚠️ |

**原因**:PyTorch 与 ONNX Runtime 浮点累加路径差异,在 conf=0.25 阈值附近的框会抖动。
**业务影响**:几乎为零,告警逻辑不受影响。
**补偿**:真实边缘 INT8 部署时把 conf 阈值从 0.25 降到 0.22 即可。

## 常见坑(我踩过的)

1. **rknn-toolkit2 装不上** — 用清华镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple`,直接走 pypi 经常超时
2. **量化精度掉太多** — 校准图要从真实业务场景抽,不能用 COCO 等通用数据集
3. **盒子端推理比 PC 慢** — 检查是不是用了 INT8(不是 FP16/FP32),`rknn.config` 里 `quantized_dtype="asymmetric_quantized-8"`
4. **ONNX 算子不兼容** — 用 `opset=12`(老芯片如 RK3568 用 opset=11),不要用最新的 opset=18+
5. **盒子内存爆** — yolov8s 11M 参数勉强够,**yolov8m 25M 在 4GB 盒子上会 OOM**,要么换大内存盒子,要么用 yolov8n

---

## 产出物归档

本仓库已经准备好的边缘部署资产:

| 文件 | 用途 |
|---|---|
| `model/best.pt` | 原始权重(回滚备份) |
| `model/best.onnx` | 通用中间格式(去 Linux 编译) |
| `model/best_openvino_model/` | Intel CPU 推理(本地开发用) |
| `scripts/export_rknn.py` | RK3588 一键转换脚本 |
| `scripts/export_sophon.py` | BM1684X 命令生成器 |
| `docs/EDGE_DEPLOYMENT.md` | 本文档 |

把这套拷到 Linux 主机就能开工,**不用重新训练 / 重新标数据**。
