# 标注指南 · Label Studio 上手

> **目标**:5000 张图,每张平均 1-2 分钟,**总耗时约 100-150 小时**(W2-W3 两周)
> **工具**:Label Studio(免费、本地、开源)

---

## 一、Label Studio 是什么

- 最流行的开源数据标注工具,支持图像、文本、音频、视频
- **本地部署,数据不上传**,适合敏感数据
- 输出 YOLO/COCO/Pascal VOC 等主流格式

## 二、安装 Label Studio(5 分钟)

### 方式 1:pip 安装(推荐)

```powershell
# 用项目同一个 Python 环境
D:/Python/Python/python.exe -m pip install label-studio
```

启动:
```powershell
D:/Python/Python/python.exe -m label_studio
```

浏览器自动打开 http://localhost:8080,首次进入注册一个本地账号(随便填,不会上传)。

### 方式 2:Docker(可选)

```powershell
docker run -it -p 8080:8080 -v "${PWD}/data:/label-studio/data" heartexlabs/label-studio:latest
```

---

## 三、创建项目

1. 登录后点 **"Create"** → 创建新项目
2. 项目名:`智慧社区违规检测`
3. **Data Import**:暂时跳过,后面批量导入
4. **Labeling Setup** → 选 **"Object Detection with Bounding Boxes"**
5. 进入配置页,**清空默认 labels**,贴入下面的配置:

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>
  <RectangleLabels name="label" toName="image">
    <Label value="person" background="#FF6B6B"/>
    <Label value="car" background="#4ECDC4"/>
    <Label value="dog" background="#FFD93D"/>
    <Label value="cat" background="#A8E6CF"/>
    <Label value="trash_bag" background="#C9B1FF"/>
    <Label value="trash_item" background="#FF9F40"/>
    <Label value="small_object" background="#95E1D3"/>
  </RectangleLabels>
</View>
```

6. 保存

## 四、导入图片(两种方式)

### 方式 1:Web 上传(适合 < 100 张)

直接拖拽到 Label Studio 的 Import 区

### 方式 2:本地路径同步(适合 5000 张)

1. **设置环境变量**(允许 Label Studio 读本地路径):
   ```powershell
   $env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"
   $env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = "D:\Python\PyCharm\PythonProject\智慧社区Web项目\dataset\images\raw"
   D:/Python/Python/python.exe -m label_studio
   ```

2. **项目 Settings → Cloud Storage → Add Source Storage**:
   - Storage Type: `Local files`
   - Absolute local path: `D:\Python\PyCharm\PythonProject\智慧社区Web项目\dataset\images\raw`
   - **勾选** "Treat every bucket object as a source file"
   - Save → Sync Storage

3. 几分钟后所有图就出现在任务列表里

---

## 五、标注操作(熟练后 1 张 < 1 分钟)

### 快捷键(必须背熟,**3 倍提速**)

| 按键 | 功能 |
|------|------|
| `1-7` | 切换类别(对应 7 个标签) |
| `空格` | 缩放图片到合适大小 |
| `Ctrl + 滚轮` | 缩放图片 |
| `Ctrl + Z` | 撤销 |
| `Ctrl + S` 或 `Shift + 回车` | 提交并下一张 |
| `Delete` | 删除选中的框 |
| `Tab` | 切换框 |

### 标注流程

1. 看图,识别**所有目标**
2. 按数字键 **选类别**(比如按 `1` 选 person)
3. 鼠标**拖拽**画框,贴紧目标边缘
4. 重复 2-3 步,直到所有目标都标完
5. **Ctrl + S** 提交,自动跳下一张

### 效率提示

- 屏幕分辨率开高(1440p / 2K 最舒服)
- 显示器越大越好(看小目标省力)
- 鼠标灵敏度调高
- 听轻音乐或纪录片(不要看视频)
- **每 30 张休息 2 分钟,看远处**(护眼,防腰背痛)

---

## 六、导出 YOLO 格式

1. 标完一批(比如 500 张)
2. 项目主页 → **Export** → 选 **YOLO**
3. 下载 zip 文件
4. 解压后结构:
   ```
   ├── classes.txt        # 类别列表
   ├── images/
   │   ├── img_001.jpg
   │   └── ...
   └── labels/
       ├── img_001.txt    # YOLO 格式 (cls cx cy w h)
       └── ...
   ```

5. 用 `scripts/split_dataset.py`(等我后面给你)把数据按 80/10/10 分成 train/val/test

---

## 七、标注质量自检

每标 100 张回头抽查 10 张:
- [ ] 框是否紧贴目标?
- [ ] 类别是否对?
- [ ] 是否漏标?
- [ ] 是否多标(把不该标的标了)?

**质检方法**:Label Studio 有"Review Mode",可以让另一个账号或自己第二次检查。

---

## 八、效率优化:半自动标注(进阶,可选)

标到 1000 张时,可以**用半成品模型预标注**,人工只做修正:

1. 用已有 1000 张训练一个**初版 YOLO 模型**(yolov8n,20 分钟)
2. 用模型给剩下 4000 张生成预标注 JSON
3. 导入 Label Studio,人工修正
4. **效率提升 2-3 倍**,从 1 张/分钟 到 3 张/分钟

具体脚本 `scripts/pre_annotate.py` 等你标到 1000 张时我给你写。

---

## 九、常见问题

### Q1:Label Studio 启动报错 "Port 8080 in use"
```powershell
D:/Python/Python/python.exe -m label_studio --port 8090
```

### Q2:图片显示不出来(空白)
检查 `LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED` 是否为 `true`,**必须在启动前设置**,且路径要用反斜杠 `\`。

### Q3:标完导出找不到 YOLO 选项
项目 Settings → Labeling Interface → 确认选的是 "Object Detection",不是 "Polygons"。

### Q4:数据丢了怎么办
Label Studio 数据存在 `~\.local\share\label-studio` 或 `%APPDATA%\label-studio`,**定期备份这个目录**。

---

## 十、节奏控制

| 阶段 | 目标 | 实际节奏 |
|------|------|----------|
| Day 1-2 | 安装 + 配置 + 标 100 张找手感 | 5-8 小时 |
| Day 3-7 | 每天 500 张,共 2500 张 | 5 小时/天 |
| Day 8-10 | 训初版模型 → 半自动标 + 修正 2500 张 | 4 小时/天 |
| Day 11 | 质量复查 + 导出 + 分 train/val/test | 3 小时 |

**总耗时约 50-70 小时**,合理安排可在 **10-14 天**完成。
