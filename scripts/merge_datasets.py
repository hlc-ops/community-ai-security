"""
智慧社区数据集合并 + 采样脚本 v2

修复 v1 问题:
1. 取消模糊匹配(导致 'no-fire' 错配 fire,'occupied' 错配 trash_item)
2. 增加 PER_DATASET_OVERRIDE,精确指定每个数据集的类名映射
3. 跳过完全无关的数据集(bike.v1i 姿态识别、parking.v1i 车位状态)

运行: D:/Python/Python/python.exe scripts/merge_datasets.py
"""

import os
import re
import sys
import shutil
import random
import zipfile
import yaml
from pathlib import Path
from collections import defaultdict, Counter

# 强制 UTF-8
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ============ 配置 ============

SOURCE_DIR = Path(r"D:\智慧社区数据集汇总")
TEMP_DIR = SOURCE_DIR / "_temp_extract"
OUTPUT_DIR = SOURCE_DIR / "_processed"
FINAL_ZIP = SOURCE_DIR / "community_dataset_v1.zip"

TARGET_CLASSES = [
    "person", "car", "dog", "cat",
    "trash_bag", "trash_item", "electric_bike", "fire",
]
TARGET_TO_ID = {name: idx for idx, name in enumerate(TARGET_CLASSES)}

SAMPLE_LIMITS = {
    "person": 4000,
    "car": 10000,           # V3 大幅提升,吸收 VisDrone 大量车辆样本
    "dog": 2500,
    "cat": 2000,
    "trash_bag": 1889,
    "trash_item": 5500,
    "electric_bike": 8000,  # V3 大幅提升,VisDrone 多目标图主要分配到此池
    "fire": 3500,
}

# 数据集级别的精确映射(zip 文件名(去 .zip)→ {原始类名: 目标类名 或 None=丢弃})
# None 表示这个类要被丢弃,整个数据集 = SKIP 表示完全跳过
PER_DATASET_OVERRIDE = {
    "bike.v11i.yolov8": {
        "bike": "electric_bike",
    },
    "bike.v1i.yolov8": "SKIP",  # 自行车姿态识别(down/stand),不可用

    "Dog Cat.v1i.yolov8": {
        "0": "cat",   # 文件名 cats_XXX 证实 0 = cat
        "1": "dog",
    },

    "fire-detection.v1i.yolov8": {
        "fire": "fire",
        "smoke": "fire",
        "no-fire": None,  # 负样本,丢弃
        "light": None,    # 灯光误检,丢弃
    },

    # 两个 Garbage 数据集 — 真实内容(2026-06-21 经 peek_old_garbage.py 验证)
    # 都是瓶罐 + 散落杂物,**不是塑料袋**,统一映射为 trash_item
    "Garbage Detection.v1i.yolov8": {
        "1": "trash_item", "2": "trash_item", "3": "trash_item",
    },
    "Garbage-Detection.v1i.yolov8": {
        "0": "trash_item", "1": "trash_item", "2": "trash_item",
        "3": "trash_item", "4": "trash_item",
    },

    "parking.v1i.yolov8": "SKIP",  # 车位空满状态,不是车辆检测

    "Person detection.v1i.yolov8": {
        "Persona": "person",
    },

    # === 第一轮补缺(4 个)===
    "car detection.v1i.yolov8": {
        "-": "car",  # class_id 0(占 95% 标注框,实际是车辆,类名只是符号)
    },
    "xemay.v2i.yolov8": {
        "motorcycle": "electric_bike",
    },
    "Motorbikes Detection.v1i.yolov8": {
        "motorbikes": "electric_bike",
    },
    "noash ark.v2i.yolov8": {
        "cat": "cat",
        "dog": "dog",
    },

    # === 第二轮补缺(16 个)— 修复"识别成功率低"问题 ===
    # --- 大巴 / 公交(3 个,全归 car)---
    "bus detection.v3i.yolov8": {
        "0": None,           # background,跳过
        "bus": "car",
    },
    "detection bus.v1i.yolov8": {"Bus": "car"},
    "Bus Detection.v1i.yolov8": {"bus": "car"},

    # --- 卡车(2 个,全归 car)---
    "truck detection.v1i.yolov8": {"truck": "car"},
    "Truck Detection.v3i.yolov8": {"trucks": "car"},

    # --- 三轮车 / mototaxi(4 个,全归 car)---
    "Vehiculos_LSP.v1i.yolov8": {"mototaxi": "car"},
    "tricycle-object-detection.v2-tricycle-object-tracing2.yolov8": {
        "tricycle": "car",
    },
    "Auto Rickshaw Types.v1i.yolov8": {
        "Atul": "car", "Bajaj": "car", "JS Auto": "car", "Lohia": "car",
        "Mahindra": "car", "PIag": "car", "Piaggo": "car", "TVS": "car",
    },
    "threeWheeler_detection.v1i.yolov8": {"threeWheeler": "car"},

    # --- 面包车 / 多类混合场景(1 个)— 多类共存!正是我们要的 ---
    "van.v2i.yolov8": {
        "car": "car", "bus": "car", "truck": "car", "van": "car",
        "motor": "car", "emotor": "car",
        "bike": "electric_bike",
        "person": "person",
        # "trafficcone" 不在 8 类内,自动跳过
    },

    # --- 猫狗专项 ---
    "cat project.v4i.yolov8": {"Cat": "cat"},
    "dog-detect.v1-dog-detect-v1.yolov8": {
        # Roboflow 自动用数据集名当类名,实际只 1 类是狗
        "Dog Detection - v1 2025-01-06 9-56pm": "dog",
    },

    # --- 瓶罐(全归 trash_item)---
    "All plastic bottle.v5-no_augmentation.yolov8": {
        "Plastic-bottle": "trash_item",
    },
    "can.v1i.yolov8": {"metal": "trash_item"},  # metal = 金属易拉罐

    # --- 明火(全归 fire)---
    "fire.v4i.yolov8": {"fire": "fire"},
    "Fire Source Detection.v2i.yolov8": {
        # 6 类火灾源全归 fire
        "Cooking Oil": "fire", "Electrical": "fire", "Gas": "fire",
        "Liquid": "fire", "Metal": "fire", "Solid": "fire",
    },

    # === 第三轮补缺(2026-06-21,7 个)— 补 electric_bike + trash_bag 真实数据 ===
    # --- 电瓶车补强(3 个)---
    "my_school_bike.v1i.yolov8": {
        "bikes": "electric_bike",
        "motorbycle": "electric_bike",   # typo of motorcycle
        "yellowbike": "electric_bike",
    },
    "bicycle.v1i.yolov8": {
        "shared": "electric_bike",        # 共享单车
        "unshared": "electric_bike",      # 私人单车
    },
    "motorcycle models.v2i.yolov8": {     # 高质量(用户认可)
        "motorcycle": "electric_bike",
    },

    # === 第四轮(2026-06-21,V3)— VisDrone 多目标俯拍数据 ===
    # 已通过 convert_visdrone_to_8class.py 预先转换为我们的 8 类 YOLO 格式
    # 8629 张图,457065 标注框(平均每图 53 个目标),解决多目标共存盲区
    "VisDrone_v1.yolov8": {
        "person": "person",
        "car": "car",
        "electric_bike": "electric_bike",
        # dog/cat/trash_bag/trash_item/fire 类 VisDrone 没有,自动跳过
    },

    # --- 塑料袋类(按业务场景拆分)---
    # 黑色大塑料袋 → trash_bag "弃置垃圾袋"(物业判定:是否合规堆放)
    "Garbage.v1i.yolov8": {                 # peek 验证:黑色大塑料垃圾袋特写
        "0": "trash_bag",
    },
    # 白色 / 普通塑料袋 → trash_item "散落垃圾"(随手乱丢小袋,实时保洁)
    "Plastic bag.v1i.yolov8": {"Plastic-bag": "trash_item"},
    "plastic.v1i.yolov8": {
        "Garbage bag": "trash_item",
        "plastic bag": "trash_item",
    },
    "plastic bag.v1i.yolov8 (1)": {
        "plastic-bag": "trash_item",
    },
}

random.seed(42)

# ============ 工具 ============

def extract_all_zips(source_dir, temp_dir):
    temp_dir.mkdir(parents=True, exist_ok=True)
    datasets = []
    for zip_path in sorted(source_dir.glob("*.zip")):
        if zip_path.name == FINAL_ZIP.name:
            continue
        ds_name = zip_path.stem
        ds_dir = temp_dir / ds_name
        if not ds_dir.exists():
            ds_dir.mkdir(parents=True)
            print(f"  解压 {zip_path.name}")
            try:
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(ds_dir)
            except Exception as e:
                print(f"  ❌ 解压失败:{e}")
                continue
        else:
            print(f"  已解压(跳过):{zip_path.name}")
        datasets.append(ds_dir)
    return datasets

def find_data_yaml(ds_dir):
    for p in ds_dir.rglob("data.yaml"):
        return p
    return None

def parse_dataset(ds_dir):
    yaml_path = find_data_yaml(ds_dir)
    if not yaml_path:
        return None, None
    with open(yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    names = cfg.get("names", [])
    if isinstance(names, dict):
        names = [names[i] for i in sorted(names.keys())]
    yaml_root = yaml_path.parent
    splits = {}
    for split in ["train", "valid", "val", "test"]:
        split_imgs = yaml_root / split / "images"
        if split_imgs.is_dir():
            key = "val" if split == "valid" else split
            splits[key] = list(split_imgs.iterdir())
    return names, splits

def process_image(img_path, src_names, override):
    """读取一张图的标签,按 override 映射 class_id"""
    label_path = img_path.parent.parent / "labels" / (img_path.stem + ".txt")
    if not label_path.exists():
        return [], set()
    new_lines = []
    contained = set()
    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                src_id = int(parts[0])
            except ValueError:
                continue
            if src_id >= len(src_names):
                continue
            src_name = str(src_names[src_id])
            if src_name not in override:
                continue
            target = override[src_name]
            if target is None:
                continue
            if target not in TARGET_TO_ID:
                continue
            new_id = TARGET_TO_ID[target]
            new_lines.append(f"{new_id} {' '.join(parts[1:])}")
            contained.add(target)
    return new_lines, contained

# ============ 主流程 ============

def main():
    print("=" * 60)
    print("智慧社区数据集合并 + 采样 v2(精确映射版)")
    print("=" * 60)

    if not SOURCE_DIR.exists():
        print(f"❌ 源目录不存在:{SOURCE_DIR}")
        sys.exit(1)

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    if FINAL_ZIP.exists():
        FINAL_ZIP.unlink()

    print(f"\n📦 [Step 1/6] 解压 zip(已解压则跳过)...")
    datasets = extract_all_zips(SOURCE_DIR, TEMP_DIR)
    print(f"  ✅ 共 {len(datasets)} 个数据集")

    print(f"\n🔍 [Step 2/6] 扫描数据集 + 精确映射...")
    all_candidates = []
    raw_class_counter = Counter()
    skipped_ds = []

    for ds_dir in datasets:
        ds_name = ds_dir.name
        override = PER_DATASET_OVERRIDE.get(ds_name)
        if override == "SKIP":
            print(f"\n  ⏭️  跳过 {ds_name}(配置为 SKIP)")
            skipped_ds.append(ds_name)
            continue
        if override is None:
            print(f"\n  ⚠️  {ds_name} 未配置映射,跳过(请加 PER_DATASET_OVERRIDE)")
            skipped_ds.append(ds_name)
            continue

        print(f"\n  · {ds_name}")
        src_names, splits = parse_dataset(ds_dir)
        if src_names is None:
            print(f"    ⚠️ 无 data.yaml,跳过")
            continue
        print(f"    原始类:{src_names}")
        for raw, target in override.items():
            print(f"      '{raw}' → {target if target else '(丢弃)'}")

        for split_name, imgs in (splits or {}).items():
            for img_path in imgs:
                new_lines, contained = process_image(img_path, src_names, override)
                if not new_lines:
                    continue
                all_candidates.append({
                    "img_path": img_path,
                    "labels": new_lines,
                    "classes": contained,
                    "src_ds": ds_name,
                })
                for c in contained:
                    raw_class_counter[c] += 1

    print(f"\n📊 候选总数:{len(all_candidates)} 张")
    print(f"📊 各类原始分布(图片级):")
    for c in TARGET_CLASSES:
        n = raw_class_counter[c]
        status = "✅" if n > 0 else "❌ 缺数据"
        print(f"    {c:15s}: {n:6d}  {status}")

    print(f"\n🎯 [Step 3/6] 采样到平衡集...")
    class_to_imgs = defaultdict(list)
    for cand in all_candidates:
        if cand["classes"]:
            primary = min(cand["classes"], key=lambda c: raw_class_counter[c])
            class_to_imgs[primary].append(cand)

    sampled = []
    sampled_ids = set()
    for cls in TARGET_CLASSES:
        pool = class_to_imgs.get(cls, [])
        limit = SAMPLE_LIMITS[cls]
        random.shuffle(pool)
        chosen = pool[:limit]
        for c in chosen:
            cid = id(c)
            if cid not in sampled_ids:
                sampled.append(c)
                sampled_ids.add(cid)
        print(f"    {cls:15s}: 候选 {len(pool):5d} → 采样 {len(chosen):4d}")

    print(f"\n📊 最终采样总数:{len(sampled)} 张")
    if len(sampled) == 0:
        print("\n❌ 无可用数据,请检查 PER_DATASET_OVERRIDE 配置")
        sys.exit(1)

    print(f"\n📂 [Step 4/6] 切分 train/val/test (80/10/10)...")
    random.shuffle(sampled)
    n = len(sampled)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)
    splits = {
        "train": sampled[:n_train],
        "val": sampled[n_train:n_train + n_val],
        "test": sampled[n_train + n_val:],
    }
    for k, v in splits.items():
        print(f"    {k:6s}: {len(v)} 张")

    print(f"\n📝 [Step 5/6] 统一命名 + 写出...")
    OUTPUT_DIR.mkdir(parents=True)
    counter = 0
    for split, items in splits.items():
        img_dir = OUTPUT_DIR / "images" / split
        lbl_dir = OUTPUT_DIR / "labels" / split
        img_dir.mkdir(parents=True)
        lbl_dir.mkdir(parents=True)
        for item in items:
            counter += 1
            new_name = f"community_{counter:06d}"
            src_img = item["img_path"]
            ext = src_img.suffix.lower()
            shutil.copy2(src_img, img_dir / f"{new_name}{ext}")
            with open(lbl_dir / f"{new_name}.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(item["labels"]))
    print(f"    ✅ 写入 {counter} 张图")

    data_yaml = {
        "path": ".",
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": len(TARGET_CLASSES),
        "names": TARGET_CLASSES,
    }
    with open(OUTPUT_DIR / "data.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data_yaml, f, sort_keys=False, allow_unicode=True)
    print(f"    ✅ data.yaml 已写")

    print(f"\n📦 [Step 6/6] 打包成最终 zip...")
    with zipfile.ZipFile(FINAL_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for file in files:
                full = Path(root) / file
                arcname = full.relative_to(OUTPUT_DIR)
                zf.write(full, arcname)
    size_mb = FINAL_ZIP.stat().st_size / (1024 * 1024)
    print(f"    ✅ {FINAL_ZIP.name} ({size_mb:.1f} MB)")

    print("\n" + "=" * 60)
    print("🎉 完成!")
    print("=" * 60)
    print(f"\n📦 最终:{FINAL_ZIP}")
    print(f"   {counter} 张图,8 类")
    print(f"   跳过的数据集:{skipped_ds}")


if __name__ == "__main__":
    main()
