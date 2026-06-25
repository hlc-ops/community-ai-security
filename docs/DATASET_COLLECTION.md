# 数据集收集指南 · 5000 张图从哪来

> **目标**:每类 700+ 张,共 5000 张高质量训练图
> **预算**:¥0(全部免费来源)
> **时间**:W1-W2 两周(全职 ~30 小时 / 兼职 ~50 小时)

---

## 一、来源分配(预期数量)

| 来源 | 占比 | 张数 | 优劣势 |
|------|------|------|--------|
| **公开数据集**(已标注) | 50% | 2500 | ✅ 高质量已标 ❌ 场景不够"小区" |
| **网络爬取**(B 站截图+图库) | 25% | 1250 | ✅ 真实场景 ❌ 要重新标 |
| **自采**(小区实拍/亲戚家) | 15% | 750 | ✅ 最贴合落地 ❌ 数量有限 |
| **AIGC 合成**(稀有场景) | 10% | 500 | ✅ 补稀有类 ❌ 真实度受限 |

---

## 二、公开数据集(直接下载,大头)

### 1. COCO(必下,通用基础)

- **网址**:https://cocodataset.org/
- **下载**:COCO 2017 val(约 5GB,1000 张筛选用,免标注)
- **能用什么类**:
  - `person` → 几万张
  - `car` → 几千张
  - `dog`, `cat` → 各几百张
  - `bottle`, `cup` → 当 `trash_item`(部分场景)
- **怎么筛**:用脚本只下载含目标类别的图,见下方 `scripts/`

### 2. Open Images V7(超大,补充用)

- **网址**:https://storage.googleapis.com/openimages/web/index.html
- **优势**:包含 600 类,有 `Plastic bag`、`Trash`、`Cat`、`Dog` 等小类
- **下载工具**:`pip install fiftyone`,用 FiftyOne 按类别筛
- **能用什么类**:
  - `Plastic bag` → 标为 `trash_bag`
  - `Skateboard`, `Tin can`, `Bottle` → 标为 `trash_item`
  - 全部 7 类都有覆盖

### 3. UA-DETRAC(车辆检测专项)

- **网址**:https://detrac-db.rit.albany.edu/
- **优势**:中国实景车辆数据集,140000 帧
- **下载**:训练集约 5GB
- **能用什么类**:`car` → 几千张

### 4. URFD / Le2i Fall Detection(摔倒)

- **URFD**:http://fenix.univ.rzeszow.pl/~mkepski/ds/uf.html
- **Le2i**:https://imvia.u-bourgogne.fr/en/database/fall-detection-dataset-2.html
- **优势**:专门拍的摔倒场景视频
- **用法**:抽帧 + 标 `person`(姿态训练 pose 模型时再用)

### 5. TACO(垃圾检测)

- **网址**:http://tacodataset.org/
- **优势**:1500 张街景垃圾图,40 类细分
- **能用什么类**:全部映射到 `trash_bag` 或 `trash_item`

### 6. Roboflow Universe(找现成的)

- **网址**:https://universe.roboflow.com/
- **搜索关键词**:
  - `community surveillance`
  - `garbage detection`
  - `illegal parking`
  - `fence climbing`
- **优势**:很多大学生项目数据集已标注,**可以直接合并用**(注意 License,大多 CC BY 4.0)

---

## 三、网络爬取(补真实场景)

### 1. B 站监控视频抽帧

- 搜索关键词:
  - "小区监控 抓贼"
  - "物业监控 录像"
  - "高空抛物 监控"
  - "宠物 闯入"
  - "电动车 起火"(意外但场景类似)
- **工具**:`you-get` 或 `yt-dlp` 下载视频
  ```bash
  pip install yt-dlp
  yt-dlp "https://www.bilibili.com/video/BVxxxxxx"
  ```
- **抽帧**:用 ffmpeg 每秒抽 1 帧
  ```bash
  ffmpeg -i input.mp4 -vf fps=1 frame_%04d.jpg
  ```
- **预期产出**:每个视频 30-100 张可用图,**找 20 个视频就有 1000+ 张**

### 2. 图库搜索(批量下载)

- **必应图片** + **Google 图片**:中文+英文双关键词覆盖更广
  - "fence climbing security camera"
  - "翻越围墙 监控"
  - "dog on lawn surveillance"
  - "garbage on street CCTV"
- **下载工具**:Chrome 扩展 **Fatkun 批量下载图片**(免费)
- **筛选**:下载 500 张大概能用 200 张,**剔除低分辨率、水印、卡通图**

### 3. 公开监控站点(慎用,合规)

- 不要直接接公开摄像头(可能侵犯隐私)
- 替代方案:**Earthcam.com** 等公开旅游摄像头有少量小区/街道画面

---

## 四、自采(最贴合落地)

### 你能拍什么(完全合法)

1. **自己家小区**:在自家阳台/单元门口拍 30-60 分钟监控角度的视频
2. **亲戚朋友家**:征得同意后拍他们小区
3. **公共场所**:学校、公园(不含人脸特写)
4. **可以摆拍**:让朋友/家人配合摆出"走草坪""丢垃圾""摔倒"等动作

### 拍摄要求

- 分辨率:1080p 起,最好 4K(可以下采样)
- 角度:**俯视 + 监控视角**,不是平视
- 光照:**白天 + 黄昏 + 夜间**全覆盖(每个场景各 1/3)
- 多样性:阴天、晴天、雨天(让模型不挑天气)

### 自采数量目标

- 每类 100 张 = 700 张
- 一周内能搞定

---

## 五、AIGC 合成(补稀有场景)

### 用什么工具

- **即梦 AI**(字节,免费):https://jimeng.jianying.com/
- **腾讯混元图片**(免费)
- **Stable Diffusion**(本地,需 GPU):用 SDXL + ControlNet
- **OpenAI DALL-E 3**(付费,质量最好)

### 适合用 AIGC 合成的场景

- ✅ **翻越围栏**:网络上真实图少,AIGC 能可控生成
- ✅ **高空抛物**:危险场景,几乎拍不到
- ✅ **夜间宠物闯入**:稀有
- ❌ **不要合成 `trash_item`**:AIGC 画的垃圾不真实

### Prompt 模板

```
监控摄像头视角,小区夜晚,一个穿黑衣服的人正在翻越铁栅栏,
背景是居民楼,真实摄像头风格,16:9 比例,1080p,真实感
```

每张图调 prompt 微调,生成 50-100 张稀有场景。

---

## 六、收集进度跟踪

把收集进度记在 `dataset/COLLECTION_LOG.md`:

```markdown
# 收集进度

| 来源 | 日期 | 类别 | 张数 | 累计 |
|------|------|------|------|------|
| COCO val | 06-18 | person/car/dog/cat | 800 | 800 |
| Open Images | 06-19 | trash_bag/trash_item | 600 | 1400 |
| B 站 BV1xx | 06-20 | person/fence_climb | 80 | 1480 |
| 自家小区 | 06-21 | car/person | 120 | 1600 |
| ...
```

---

## 七、下载脚本(我帮你写的)

`scripts/download_coco.py` 和 `scripts/download_openimages.py` 在仓库里,**今天先不跑**,等明天看完本指南再用。

---

## 八、收集顺序建议(节奏感)

| 天 | 任务 | 累计 |
|----|------|------|
| Day 1 | 下载 COCO val + 筛选脚本 → 出 1000 张 | 1000 |
| Day 2 | Open Images 用 FiftyOne 筛 trash 类 → 出 800 张 | 1800 |
| Day 3 | UA-DETRAC 车辆 + TACO 垃圾 → 出 700 张 | 2500 |
| Day 4-5 | B 站 + 图库爬取(2 天) | 3500 |
| Day 6-7 | 自家小区拍摄(周末) | 4250 |
| Day 8-9 | AIGC 合成稀有场景 | 4750 |
| Day 10 | Roboflow Universe 找补 | 5000 |

**完成标志**:`dataset/images/raw/` 下有 5000+ 张图,文件名规范(`source_序号.jpg`),可以开始标注了。

---

## 九、注意事项

1. **隐私**:别拍人脸特写,标注时遇到可识别人脸的图,**优先选远景或马赛克处理**
2. **版权**:公开数据集都是 CC 协议,放心用;爬虫下来的图**只用于训练,不传播**
3. **质量 > 数量**:模糊、太小、构图差的图扔掉,**4000 张高质量好于 5000 张垃圾**
4. **多样性 > 单一**:同一场景拍 500 张,不如 10 个不同场景各 50 张
