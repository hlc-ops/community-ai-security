"""COCO val 2017 → 我们的 8 类 YOLO 格式
- 从 COCO 80 类映射到我们的 6 类(person/car/dog/cat/trash_item/electric_bike)
- 输出 YOLO txt 标注
- 只保留含至少 1 个目标类的图(过滤无关图)

运行:
    D:/Python/Python/python.exe scripts/convert_coco_to_8class.py
"""
import json
import os
import shutil
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ============ 配置 ============
COCO_ROOT = Path(r"D:\COCO")
COCO_IMG_DIR = COCO_ROOT / "val2017"
COCO_ANN_FILE = COCO_ROOT / "annotations" / "instances_val2017.json"

OUT_DIR = Path(r"D:\智慧社区数据集汇总\_coco_converted")
OUT_IMG_DIR = OUT_DIR / "images"
OUT_LBL_DIR = OUT_DIR / "labels"
OUT_IMG_DIR.mkdir(parents=True, exist_ok=True)
OUT_LBL_DIR.mkdir(parents=True, exist_ok=True)

# 我们的 8 类(顺序就是 class_id)
TARGET_CLASSES = ["person", "car", "dog", "cat", "trash_bag", "trash_item", "electric_bike", "fire"]
TARGET_TO_ID = {n: i for i, n in enumerate(TARGET_CLASSES)}

# COCO 类名 → 我们的目标类
COCO_TO_TARGET = {
    "person": "person",
    "car": "car",
    "truck": "car",
    "bus": "car",
    "motorcycle": "electric_bike",  # 摩托当电瓶车
    "bicycle": "electric_bike",
    "dog": "dog",
    "cat": "cat",
    # 瓶罐杂物 → 散落垃圾
    "bottle": "trash_item",
    "cup": "trash_item",
    "wine glass": "trash_item",
    # 不映射的(背景上下文):
    # train/airplane/boat/bench/bird/sheep/cow/horse/elephant/bear/zebra/...
    # backpack/umbrella/handbag/tie/suitcase/frisbee/skis/snowboard/...
    # sports ball/kite/baseball bat/skateboard/surfboard/tennis racket/...
    # banana/apple/sandwich/orange/broccoli/carrot/hot dog/pizza/donut/cake/...
    # chair/couch/potted plant/bed/dining table/toilet/tv/laptop/mouse/...
}


def main():
    print("=" * 60)
    print("COCO val 2017 → 8 类 YOLO 格式 转换")
    print("=" * 60)

    if not COCO_ANN_FILE.exists():
        print(f"❌ 标注文件不存在: {COCO_ANN_FILE}")
        print("先下载 COCO 然后解压到 D:/COCO/")
        sys.exit(1)
    if not COCO_IMG_DIR.exists():
        print(f"❌ 图片目录不存在: {COCO_IMG_DIR}")
        sys.exit(1)

    print(f"\n📖 加载 COCO 标注(可能需要 10-30 秒)...")
    with open(COCO_ANN_FILE, "r", encoding="utf-8") as f:
        coco = json.load(f)

    # 建立 image_id → image 信息映射
    img_info = {img["id"]: img for img in coco["images"]}
    print(f"   COCO 图片数: {len(img_info)}")

    # 建立 category_id → category 名映射
    cat_info = {c["id"]: c["name"] for c in coco["categories"]}
    print(f"   COCO 类别数: {len(cat_info)}")

    # 我们关心的 COCO category_id 集合
    target_cat_ids = {cid for cid, name in cat_info.items() if name in COCO_TO_TARGET}
    print(f"   命中我们目标的 COCO 类数: {len(target_cat_ids)}")
    for cid in sorted(target_cat_ids):
        cn = cat_info[cid]
        tn = COCO_TO_TARGET[cn]
        print(f"     [{cid}] {cn} → {tn}")

    # 按 image_id 收集所有 annotation
    print(f"\n📝 处理 {len(coco['annotations'])} 个标注框...")
    img_annotations = {}  # image_id → list of (target_id, bbox_norm)
    for ann in coco["annotations"]:
        if ann["category_id"] not in target_cat_ids:
            continue
        cn = cat_info[ann["category_id"]]
        tn = COCO_TO_TARGET[cn]
        target_id = TARGET_TO_ID[tn]

        img_id = ann["image_id"]
        img = img_info[img_id]
        W, H = img["width"], img["height"]

        # COCO bbox: [x, y, w, h] 像素 → YOLO 格式 [cx, cy, w, h] 归一化
        x, y, w, h = ann["bbox"]
        cx = (x + w / 2) / W
        cy = (y + h / 2) / H
        nw = w / W
        nh = h / H
        # 裁剪到 [0, 1]
        cx, cy, nw, nh = max(0, min(1, cx)), max(0, min(1, cy)), max(0, min(1, nw)), max(0, min(1, nh))

        if nw <= 0 or nh <= 0:
            continue

        if img_id not in img_annotations:
            img_annotations[img_id] = []
        img_annotations[img_id].append((target_id, cx, cy, nw, nh))

    print(f"   含目标类的图片数: {len(img_annotations)}")

    # 写出 YOLO 格式标签 + 复制图片
    print(f"\n💾 写出 YOLO 格式到 {OUT_DIR}...")
    written = 0
    class_count = {n: 0 for n in TARGET_CLASSES}

    for img_id, anns in img_annotations.items():
        img = img_info[img_id]
        src_img = COCO_IMG_DIR / img["file_name"]
        if not src_img.exists():
            continue

        # 新文件名(避免冲突):coco_<image_id>.jpg
        new_name = f"coco_{img_id:012d}"
        dst_img = OUT_IMG_DIR / f"{new_name}.jpg"
        dst_lbl = OUT_LBL_DIR / f"{new_name}.txt"

        # 复制图(不重新编码,直接拷贝)
        shutil.copy2(src_img, dst_img)

        # 写标签
        with open(dst_lbl, "w", encoding="utf-8") as f:
            for tid, cx, cy, w, h in anns:
                f.write(f"{tid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
                class_count[TARGET_CLASSES[tid]] += 1
        written += 1

    print(f"\n✅ 完成!")
    print(f"   输出图片:{written} 张")
    print(f"   输出位置:{OUT_DIR}")
    print(f"\n📊 各类标注框数:")
    for n in TARGET_CLASSES:
        print(f"     {n:15s}: {class_count[n]}")

    # 计算多类共存比例
    multi_class_imgs = 0
    for anns in img_annotations.values():
        if len({a[0] for a in anns}) >= 2:
            multi_class_imgs += 1
    print(f"\n🎯 多类共存图片数(2+ 类同图): {multi_class_imgs} / {written} "
          f"({multi_class_imgs / max(written, 1) * 100:.1f}%)")

    print(f"\n下一步:")
    print(f"  1. 检查 {OUT_DIR} 里的图和标签")
    print(f"  2. 把这个目录里的 images/ 和 labels/ 合并到你的训练 dataset 里")
    print(f"     (或者用 merge 脚本统一处理)")


if __name__ == "__main__":
    main()
