# AutoDL 云端训练完整指南

> **目标**:把 `community_dataset_v1.zip` 上传到 AutoDL 4090 显卡,训练 YOLOv8s,产出 `best.pt`
> **预计耗时**:配置 30 分钟 + 训练 3-4 小时 + 下载 5 分钟 = **约 4 小时**
> **预算**:¥15-25(纯训练费用,关机后不扣费)

---

## 📑 完整流程概览

```
1. 注册 AutoDL 账号 + 充值 ¥30
   ↓
2. 创建实例(选 4090 + PyTorch 镜像)
   ↓
3. 启动实例 + 开 JupyterLab
   ↓
4. 上传 community_dataset_v1.zip(517 MB)
   ↓
5. 解压数据集
   ↓
6. 安装 ultralytics
   ↓
7. 跑训练命令(3-4 小时)
   ↓
8. 下载 best.pt 到本地
   ↓
9. ⚠️ 关机省钱(否则继续扣费)
```

---

## Step 1:注册 AutoDL 账号

1. 浏览器打开 **https://www.autodl.com/**
2. 右上角点 **注册/登录**
3. 选 **微信扫码登录**(最快)
4. 完善实名信息(身份证)— 必须做,否则不能买卡
5. 进入控制台

---

## Step 2:充值

1. 控制台左侧菜单 → **费用 → 充值**
2. 充 **¥30**(够训练 2-3 次,够你用)
3. 支付宝/微信都可以

> 💡 不要充太多,先试小额,熟悉后再续。

---

## Step 3:创建实例(关键)

### 3.1 进入算力市场

1. 控制台首页 → 顶部 **算力市场** Tab
2. 看到一堆 GPU 选项

### 3.2 选 GPU

**选 RTX 4090 24GB**(性价比之王):

| 显卡 | 价格 | 适合你吗 |
|------|------|---------|
| **RTX 4090 24GB** ⭐ | ¥2.5/小时 | ✅ 推荐 |
| RTX 3090 24GB | ¥1.8/小时 | ⚠️ 慢 30% |
| A100 40GB | ¥8/小时 | ❌ 浪费,你用不上 40GB |
| RTX 4080 / 4070 | ¥1.5/小时 | ⚠️ 显存可能不够 |

### 3.3 选地区(就近)

界面会列出多个地区,选择:
- 🌟 **任何"空闲多"的地区都行**(看右侧"空闲数量")
- 优先**北京/上海/南京**(网络稳定)
- 避开**香港**(贵且慢)

### 3.4 点 "1 卡可用" → "1 小时" → **租用**

进入实例配置页:

| 选项 | 选什么 |
|------|--------|
| **镜像** | **PyTorch / 2.x 版本 / CUDA 12.x** ⭐ |
| **系统盘** | 默认 30GB 够用(不要选扩展) |
| **数据盘** | 不需要(免费 50GB 系统盘已够) |
| **付费方式** | **按量计费**(用多久付多久) |

> ⚠️ 看清楚镜像版本是 **PyTorch 2.x**(不是 1.x),并且 **CUDA 11.8 或 12.x**

### 3.5 点 "立即创建"

实例创建好后,自动跳到 **控制台 → 我的实例**。

---

## Step 4:启动实例 + 开 JupyterLab

### 4.1 启动

在"我的实例"页,找到刚创建的实例,点 **开机**(右侧按钮)。

等 30 秒,状态变为"运行中"。

### 4.2 打开 JupyterLab

实例右侧有几个按钮:
- **JupyterLab** ⭐(网页版,推荐新手)
- SSH 登录(进阶,需要 SSH 工具)
- 文件传输(传大文件用)

**点 JupyterLab**,会在浏览器新标签打开 Jupyter 界面。

界面左侧是文件管理器,中间是工作区。

---

## Step 5:上传数据集(2 种方式)

### 方式 A:JupyterLab 直接拖拽(< 1GB 用这个)

1. JupyterLab 左侧文件管理器,确认在 `/root/` 目录
2. **直接把本地的 `community_dataset_v1.zip` 拖进左侧文件区**
3. 上传中会显示进度条,你的 517MB 大约 5-10 分钟(看网速)

### 方式 B:AutoDL 自带的文件传输(更快,推荐)

1. 控制台 → 我的实例 → 实例右侧点 **更多 → 文件传输**
2. 在新窗口里点 **上传** → 选 `community_dataset_v1.zip`
3. 通常比拖拽快 2-3 倍

### 方式 C:阿里云 OSS 中转(可选,> 1GB 用)

如果上传慢,可以传到阿里云盘/OSS,然后实例里 wget 下载。**你 517MB 不需要这种方式**。

---

## Step 6:打开终端 + 解压数据

### 6.1 在 JupyterLab 里开终端

- 顶部菜单 **File → New → Terminal**
- 或者左下角 "+" 号 → **Terminal**

弹出一个黑色命令行窗口。

### 6.2 解压数据集

在终端粘贴运行:

```bash
cd /root
ls -lh community_dataset_v1.zip      # 确认文件存在
mkdir -p dataset
unzip -q community_dataset_v1.zip -d dataset/
ls dataset/                          # 看是否有 images/ labels/ data.yaml
```

应该看到:
```
data.yaml
images/
labels/
```

### 6.3 看一眼 data.yaml(确认没问题)

```bash
cat dataset/data.yaml
```

应该看到:
```yaml
path: .
train: images/train
val: images/val
test: images/test
nc: 8
names:
- person
- car
- dog
- cat
- trash_bag
- trash_item
- electric_bike
- fire
```

---

## Step 7:安装 ultralytics + 训练

### 7.1 安装

```bash
pip install ultralytics -i https://pypi.tuna.tsinghua.edu.cn/simple
```

国内源,几秒装好。

### 7.2 跑训练!

```bash
cd /root/dataset
yolo detect train \
    data=data.yaml \
    model=yolov8s.pt \
    epochs=100 \
    imgsz=640 \
    batch=32 \
    name=community_v1 \
    device=0
```

**参数解释**(背下来面试可能问):

| 参数 | 含义 | 为什么这么设 |
|------|------|------------|
| `data=data.yaml` | 数据配置 | 我们生成的 8 类配置 |
| `model=yolov8s.pt` | 用 small 版本预训练 | 平衡精度速度 |
| `epochs=100` | 训 100 轮 | 通常 50-100 收敛 |
| `imgsz=640` | 输入 640×640 | YOLOv8 标准 |
| `batch=32` | 一批 32 张 | 4090 24GB 显存能扛 |
| `name=community_v1` | 输出文件夹名 | 方便管理 |
| `device=0` | 用第 0 块 GPU | 单卡 |

### 7.3 开始训练!

回车后会看到:
- 自动下载 `yolov8s.pt` 预训练权重(几十秒)
- 开始训练,每轮 1-2 分钟
- 控制台滚动输出 loss + mAP

**预计时间**:
- 100 epochs × 每轮约 2 分钟 = **3.5 小时**
- 中途**可以关浏览器**,训练在云端继续跑(用 nohup 更稳,见进阶)

### 7.4 进阶:后台运行(关浏览器也不停)

```bash
cd /root/dataset
nohup yolo detect train \
    data=data.yaml model=yolov8s.pt epochs=100 imgsz=640 batch=32 \
    name=community_v1 device=0 \
    > /root/train.log 2>&1 &

echo "训练已后台运行,PID: $!"
```

**看进度**:
```bash
tail -f /root/train.log    # 实时滚动看日志
# 按 Ctrl+C 退出(只是退出 tail,训练不停)
```

---

## Step 8:监控训练(可选,中间看进度)

### 8.1 看实时日志

```bash
tail -f /root/train.log
```

### 8.2 看每轮指标

训练过程会输出表格,关注这几列:
```
Epoch  |  box_loss  |  cls_loss  |  mAP@0.5  |  mAP@0.5:0.95
  10   |    1.245   |    1.872   |   0.521   |    0.312
  50   |    0.832   |    0.911   |   0.756   |    0.487
  100  |    0.523   |    0.612   |   0.823   |    0.564
```

**判断好坏**:
- mAP@0.5 > 0.7 → 可接受
- mAP@0.5 > 0.8 → 优秀
- mAP@0.5 < 0.5 → 数据有问题或训练不收敛

### 8.3 看 GPU 占用

新开一个终端跑:
```bash
nvidia-smi
```

应该看到 GPU 利用率 > 80%,显存 18-20GB 占用。

---

## Step 9:训练完成,下载结果

### 9.1 训完位置

训练完成后,关键文件在:
```
/root/dataset/runs/detect/community_v1/
├── weights/
│   ├── best.pt          ⭐ 这个是你要的!最优模型
│   └── last.pt          (最后一轮的,一般不用)
├── results.csv          ⭐ 训练曲线数据
├── results.png          ⭐ 训练曲线图
├── confusion_matrix.png ⭐ 混淆矩阵(看哪类容易误判)
├── val_batch0_labels.jpg  (验证集标注示例)
└── val_batch0_pred.jpg    (模型预测示例)
```

### 9.2 打包下载

```bash
cd /root/dataset/runs/detect
tar czf community_v1_result.tar.gz community_v1/
ls -lh community_v1_result.tar.gz
```

会生成一个几十 MB 的压缩包,方便下载。

### 9.3 下载到本地

**方式 A(推荐)**:JupyterLab 文件管理器,右键文件 → **Download**

**方式 B**:控制台的文件传输工具

下载到本地后,**至少保留**:
- `weights/best.pt`(模型权重,**最重要**)
- `results.png`(简历素材)
- `confusion_matrix.png`(简历素材)

---

## Step 10:⚠️ 关机省钱!!

**这一步千万别忘**,不关机会持续扣费(¥2.5/小时 × 24 = ¥60/天烧着)。

1. 控制台 → 我的实例
2. 找到你的实例 → 点 **关机**
3. 状态变为"已关机",**不再扣费**(但数据保留)

> 💡 关机后系统盘数据保留 15 天,后续训练 V2 可以直接开机继续用。

---

## 训练完成后的工作流

### 11. 把 best.pt 接入项目

```
本地路径:
D:\Python\PyCharm\PythonProject\智慧社区Web项目\model\best.pt
```

把下载的 `best.pt` 放到这里,后端代码后续会从这里加载模型。

### 12. (可选)导出 OpenVINO INT8

工地项目用了 INT8 量化,**社区项目可以同样做**:

```bash
cd /root/dataset
yolo export model=runs/detect/community_v1/weights/best.pt format=openvino int8=True data=data.yaml
```

会生成 `best_openvino_model/` 目录,**推理速度提升 3-5 倍**,适合工控机部署。

---

## ❓ 常见问题速查

### Q1:训练报 `CUDA out of memory`
**原因**:batch 太大,显存爆了
**解决**:把 `batch=32` 改成 `batch=16` 或 `batch=8`

### Q2:训练几轮后 loss 是 NaN
**原因**:学习率太大 / 数据有问题
**解决**:加 `lr0=0.001`(初始学习率减半)

### Q3:训练超慢,一轮 5 分钟+
**原因**:可能在用 CPU 而不是 GPU
**解决**:检查 `device=0` 是否生效,跑 `nvidia-smi` 看 GPU 利用率

### Q4:中途断网,JupyterLab 断了
**情况**:**训练没停**(如果你用了 nohup)
**解决**:重连后跑 `tail -f /root/train.log` 看进度

### Q5:训完 mAP 只有 0.4 怎么办
**原因**:
- 数据不平衡(cat 太少导致拉低整体)
- epochs 不够
- 类别太相似(trash_bag vs trash_item 难分)

**解决**:
- 看 `confusion_matrix.png` 找问题类
- 增加该类数据
- 或继续训 50 轮:
  ```bash
  yolo detect train data=data.yaml \
      model=runs/detect/community_v1/weights/last.pt \
      epochs=50 resume=True
  ```

### Q6:JupyterLab 上传超慢
**解决**:用 AutoDL 自带的 "文件传输" 功能,通常快 2-3 倍

### Q7:实例创建后开不了机
**情况**:库存被抢光
**解决**:换地区或换显卡,或者隔几分钟再试

---

## 💰 费用总览

| 项目 | 估算 |
|------|------|
| RTX 4090 × 4 小时训练 | ¥10 |
| 试错 / 调参再训 1-2 次 | ¥10-20 |
| 系统盘 30GB(免费) | ¥0 |
| **总计** | **¥20-30** |

**关机后**:不扣费,数据保留 15 天。

---

## 📊 训练成功的标准

跑完后,看 `results.png`,如果:

- ✅ **loss 曲线平滑下降**(没有大幅波动)
- ✅ **mAP@0.5 最终 > 0.7**
- ✅ **混淆矩阵**主对角线明亮(各类预测准确)

**通过 → 进入后端开发阶段**(复用工地项目代码)。

---

## 📋 准备好的检查清单

开始训练前,在本地确认:

- [ ] `D:\智慧社区数据集汇总\community_dataset_v1.zip` 存在(517 MB)
- [ ] AutoDL 账号已注册,实名认证完成
- [ ] 充值 ≥ ¥30
- [ ] 知道 RTX 4090 在哪选(算力市场页)
- [ ] 知道选 PyTorch 2.x 镜像
- [ ] 关机的位置在哪(训完别忘关)

全部 ✅ 后,**开干**。

---

## 🎯 完成后下一步

训练好的 `best.pt` 放到 `model/` 目录后,**下一阶段是复用工地项目代码搭建社区版后端**(任务 #119)。

那时我会帮你:
- 从工地项目复制 Flask 骨架
- 改业务规则(违停 polygon、宠物闯入等)
- 加车位空满统计(方案 C)
- 集成 LLM 工单生成

**祝训练顺利!** 🚀
