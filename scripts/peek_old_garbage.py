"""窥视旧 Garbage-Detection.v1i 数据集的真实内容
- 看标注分布(哪个 class_id 最多)
- 解压几张代表性图给用户看
"""
import zipfile
import yaml
import os
import sys
from collections import Counter

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ZIP = r"D:\智慧社区数据集汇总\Garbage-Detection.v1i.yolov8.zip"
SAMPLE_DIR = r"D:\智慧社区数据集汇总\_peek_garbage_samples"
os.makedirs(SAMPLE_DIR, exist_ok=True)

with zipfile.ZipFile(ZIP) as zf:
    # 找 data.yaml
    for n in zf.namelist():
        if n.endswith("data.yaml"):
            cfg = yaml.safe_load(zf.read(n).decode("utf-8", errors="replace"))
            break
    names = cfg.get("names", [])
    if isinstance(names, dict):
        names = [names[i] for i in sorted(names.keys())]
    print(f"data.yaml 类名: {names}")
    print(f"数据集名: {cfg.get('roboflow', {}).get('project', 'unknown')}")

    # 统计每个 class_id 的标注框数量
    class_counter = Counter()
    label_files = [n for n in zf.namelist() if "/labels/" in n and n.endswith(".txt")]
    print(f"标注文件总数: {len(label_files)}")
    for n in label_files[:5000]:  # 采样 5000 个标注文件
        try:
            content = zf.read(n).decode("utf-8")
            for line in content.strip().splitlines():
                parts = line.split()
                if parts:
                    class_counter[parts[0]] += 1
        except Exception:
            pass
    print(f"\n标注框分布(每个 class_id 的实例数):")
    for cid, count in sorted(class_counter.items(), key=lambda x: -x[1]):
        idx = int(cid)
        cn = names[idx] if idx < len(names) else "?"
        print(f"  class {cid} ({cn}): {count} 个标注框")

    # 解压每个类的代表性图片(各取 3 张)
    print(f"\n解压代表性图片到: {SAMPLE_DIR}")
    image_files = [n for n in zf.namelist() if "/images/" in n and any(n.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png"))]
    samples_per_class = {cid: [] for cid in class_counter.keys()}

    for img_path in image_files[:500]:
        # 同名 label 文件
        label_path = img_path.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
        if label_path not in zf.namelist():
            continue
        try:
            content = zf.read(label_path).decode("utf-8")
            cids_in_img = set()
            for line in content.strip().splitlines():
                parts = line.split()
                if parts:
                    cids_in_img.add(parts[0])
            # 这张图代表哪些 class
            for cid in cids_in_img:
                if len(samples_per_class[cid]) < 3:
                    out_name = f"class{cid}_sample{len(samples_per_class[cid]) + 1}.jpg"
                    with open(os.path.join(SAMPLE_DIR, out_name), "wb") as f:
                        f.write(zf.read(img_path))
                    samples_per_class[cid].append(out_name)
        except Exception:
            pass

    for cid, files in samples_per_class.items():
        if files:
            print(f"  class {cid}: {files}")

print(f"\n✅ 完成。打开 {SAMPLE_DIR} 看每个 class 实际长什么样")
