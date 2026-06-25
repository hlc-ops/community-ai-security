# 第 1 周每日任务表

> **总目标**:完成立项、配置环境、动手下载第一批 1500 张图,验证整个标注流程跑通

---

## Day 1 (今天)· 立项 + 环境 · 4 小时

### 上午(2h)
- [x] 项目目录骨架已搭好(✅ 我已经帮你做了)
- [x] 类别定义 `docs/CLASSES.md` 阅读 + 理解(必读)
- [x] 数据集收集指南 `docs/DATASET_COLLECTION.md` 阅读
- [x] 标注指南 `docs/ANNOTATION_GUIDE.md` 阅读
- [ ] 注册以下账号(免费):
  - [ ] Roboflow Universe(找现成数据集)
  - [ ] AutoDL(国内算力,后续训练用)
  - [ ] HuggingFace(可选,放数据集)

### 下午(2h)
- [ ] 安装 Label Studio:
  ```powershell
  D:/Python/Python/python.exe -m pip install label-studio
  D:/Python/Python/python.exe -m label_studio
  ```
- [ ] 按 `docs/ANNOTATION_GUIDE.md` 第三章创建项目,配置 7 类标签
- [ ] 找 10 张测试图(随便),手工标完跑通流程(导出 YOLO 格式验证)
- [ ] 安装 ffmpeg(后面爬视频要用):https://ffmpeg.org/download.html
- [ ] 安装 yt-dlp:`pip install yt-dlp`

**完成标志**:Label Studio 跑起来 + 标注 10 张 + 成功导出 YOLO 格式

---

## Day 2 · COCO 数据集 · 5 小时

### 任务
- [ ] 下载 **COCO 2017 val 集**(约 1GB,1000+ 张 person/car/dog/cat)
  - 注意:用 `val2017`,不是 `train2017`(后者 18GB 太大)
  - 直接下载链接:http://images.cocodataset.org/zips/val2017.zip
- [ ] 用脚本筛选目标类(我后面给你)
- [ ] 转换 COCO json 标注 → YOLO txt 格式
- [ ] 把图片和标签放入 `dataset/images/raw/` 和对应 labels

### 目标产出
- **800 张已标注图**(person 500 + car 150 + dog 80 + cat 70)
- 命名规范:`coco_000001.jpg`, `coco_000002.jpg` ...

**完成标志**:`dataset/images/raw/coco_*.jpg` 至少 800 个,对应 labels 已就位

---

## Day 3 · Open Images 数据集 · 5 小时

### 任务
- [ ] 安装 FiftyOne:`D:/Python/Python/python.exe -m pip install fiftyone`
- [ ] 用 FiftyOne 从 Open Images V7 筛选目标:
  - `Plastic bag` → 标为 `trash_bag`
  - `Bottle`, `Tin can` → 标为 `trash_item`
  - 也可补充 `Dog`, `Cat` 数据
- [ ] 转 YOLO 格式
- [ ] 入库 `dataset/images/raw/oi_*.jpg`

### 目标产出
- **600 张已标注图**(trash_bag 300 + trash_item 200 + 其他补充 100)

**完成标志**:trash 类样本充足,累计 1400+ 张

---

## Day 4 · UA-DETRAC 车辆 + TACO 垃圾 · 5 小时

### 任务
- [ ] 下载 UA-DETRAC 训练集(选 1000 帧)
  - 中国实景车辆数据集,适配国内场景
- [ ] 下载 TACO 街景垃圾数据集(1500 张全要)
- [ ] 类别映射 + YOLO 格式转换

### 目标产出
- **700 张**:car 400 + trash 类 300
- 命名 `detrac_*.jpg`, `taco_*.jpg`

**完成标志**:累计 2500 张,4 类(person/car/trash_bag/trash_item)已经足够

---

## Day 5 · B 站 + Bing 爬取(真实场景)· 5 小时

### 任务
- [ ] 用 yt-dlp 下载 20 个 B 站监控视频:
  - 关键词:"小区监控""高空抛物""宠物闯入""翻墙"
- [ ] 用 ffmpeg 抽帧(每秒 1 帧):
  ```bash
  ffmpeg -i input.mp4 -vf fps=1 frame_%04d.jpg
  ```
- [ ] 装 Chrome 扩展 **Fatkun**,从 Bing 图片下 500+ 张
  - 关键词:"fence climbing CCTV""dog on lawn""garbage on street"
- [ ] 手工筛掉低质量图(模糊、水印、卡通),留 60% 即可

### 目标产出
- **1000 张未标注真实场景图**

**完成标志**:`dataset/images/raw/bili_*.jpg` 和 `bing_*.jpg` 累计 1000+ 张

---

## Day 6-7(周末)· 自家小区拍摄 · 6 小时

### 任务
- [ ] 选 3-5 个角度拍 30-60 分钟视频:
  - 单元门口、车库口、绿地边、围栏旁
- [ ] 让家人朋友配合摆拍稀有场景:
  - 假装"走草坪"
  - 假装"丢垃圾"(用空袋子)
  - 摆出"摔倒"姿势(保护好自己)
  - 假装"翻矮栏杆"(注意安全!选低矮装饰栏杆)
- [ ] 抽帧 + 筛选

### 目标产出
- **500 张自采图**,文件名 `selfshot_*.jpg`

**完成标志**:`dataset/images/raw/` 总数达到 4000 张

---

## Day 8-9 · AIGC 合成 + Roboflow Universe · 6 小时

### Day 8(AIGC)
- [ ] 即梦 AI 生成翻越围栏场景 100 张
- [ ] 即梦 AI 生成高空抛物场景 100 张
- [ ] 即梦 AI 生成夜间宠物闯入 100 张
- [ ] 筛掉不真实的,留 60-70% 即可

### Day 9(Roboflow)
- [ ] 注册 Roboflow Universe(免费)
- [ ] 搜索 `garbage detection`, `community surveillance` 等
- [ ] 下载 2-3 个公开数据集(注意 License 是 CC BY 4.0)
- [ ] 合并到主数据集

### 目标产出
- **500 张稀有场景图**,累计 4500+ 张

---

## Day 10 · 整理 + 重命名 + 入 raw 池 · 3 小时

### 任务
- [ ] 检查 `dataset/images/raw/` 总数(目标 5000+)
- [ ] 用脚本统一重命名为 `community_000001.jpg`(连续编号)
- [ ] 写 `dataset/COLLECTION_LOG.md`,记录每个文件的来源
- [ ] 备份原始来源(`raw_backup.zip`)

### 目标产出
- **5000 张统一命名的图**,等待标注

**完成标志**:`dataset/images/raw/` 下 5000+ 张图,文件名规范

---

## 完成 W1 后的状态

- ✅ Label Studio 已配置好
- ✅ 5000 张原始图就位
- ✅ 来源记录完整
- ✅ 已有约 2500 张是从公开数据集来的(已带标注)
- ⏳ 剩下 2500 张需要 W2 手工标注

W1 估计总耗时:**35-45 小时**(全职 1 周 / 兼职 2 周)

---

## 我能帮你做的(下一步告诉我)

我可以随时给你写:
1. **COCO 筛选脚本**(Day 2 用)
2. **Open Images FiftyOne 脚本**(Day 3 用)
3. **B 站视频批量抽帧脚本**(Day 5 用)
4. **统一重命名脚本**(Day 10 用)
5. **半自动预标注脚本**(标到 1000 张后用)

**今天先按 Day 1 做**(装 Label Studio + 跑通流程),做完告诉我,我们按节奏推进。
