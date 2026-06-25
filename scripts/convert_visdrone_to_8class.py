"""VisDrone → 我们的 8 类 YOLO 格式转换

VisDrone 标注格式(每行,逗号分隔):
  bbox_left,bbox_top,bbox_width,bbox_height,score,object_category,truncation,occlusion

object_category:
  0: ignored regions
  1: pedestrian
  2: people
  3: bicycle
  4: car
  5: van
  6: truck
  7: tricycle
  8: awning-tricycle
  9: bus
  10: motor
  11: others

映射到我们 8 类(person/car/dog/cat/trash_bag/trash_item/electric_bike/fire):
  1, 2  → person
  3, 10 → electric_bike(自行车 + 摩托)
  4-9   → car(轿车/面包/卡车/三轮/带篷三轮/大巴)
  0, 11 → 跳过(无效/其他)

运行:
    D:/Python/Python/python.exe scripts/convert_visdrone_to_8class.py [zip_path_or_dir]
"""
import os
import sys
import shutil
import zipfile
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ============ 配置 ============
DEFAULT_ZIPS = [
    r"D:\智慧社区数据集汇总\VisDrone2019-DET-val.zip",
    r"D:\智慧社区数据集汇总\VisDrone2019-DET-train.zip",
    r"D:\智慧社区数据集汇总\VisDrone2019-DET-test-dev.zip",
]

OUT_DIR = Path(r"D:\智慧社区数据集汇总\_visdrone_converted")
OUT_IMG_DIR = OUT_DIR / "images"
OUT_LBL_DIR = OUT_DIR / "labels"
OUT_IMG_DIR.mkdir(parents=True, exist_ok=True)
OUT_LBL_DIR.mkdir(parents=True, exist_ok=True)

# 我们的 8 类
TARGET_CLASSES = ["person", "car", "dog", "cat", "trash_bag", "trash_item", "electric_bike", "fire"]
TARGET_TO_ID = {n: i for i, n in enumerate(TARGET_CLASSES)}

# VisDrone category_id → 我们的目标类
VISDRONE_TO_TARGET = {
    1: "person",          # pedestrian
    2: "person",          # people
    3: "electric_bike",   # bicycle
    4: "car",             # car
    5: "car",             # van
    6: "car",             # truck
    7: "car",             # tricycle
    8: "car",             # awning-tricycle
    9: "car",             # bus
    10: "electric_bike",  # motor
    # 0: ignored, 11: others 跳过
}


def convert_one_zip(zip_path: Path):
    """处理一个 VisDrone zip 文件"""
    if not zip_path.exists():
        print(f"⏭️  {zip_path.name} 不存在,跳过")
        return 0, 0, {n: 0 for n in TARGET_CLASSES}

    print(f"\n📦 处理 {zip_path.name}({zip_path.stat().st_size / 1024 / 1024:.1f} MB)...")

    # 用 PIL 读图获取尺寸(也可以用 cv2)
    try:
        from PIL import Image
    except ImportError:
        print("❌ 需要 PIL/Pillow")
        sys.exit(1)

    import io

    img_written = 0
    box_count = 0
    class_count = {n: 0 for n in TARGET_CLASSES}
    skipped_score = 0

    # 解压前,先把 zip 中所有图和 ann 编入索引
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        img_files = {os.path.splitext(os.path.basename(n))[0]: n
                     for n in names if n.lower().endswith(('.jpg', '.jpeg', '.png'))}
        ann_files = {os.path.splitext(os.path.basename(n))[0]: n
                     for n in names if 'annotations' in n and n.lower().endswith('.txt')}

        print(f"   zip 含图:{len(img_files)},含标注:{len(ann_files)}")

        # 取 zip 名作为前缀(避免不同 zip 同名冲突)
        prefix = zip_path.stem  # VisDrone2019-DET-val

        for stem, img_path in img_files.items():
            if stem not in ann_files:
                continue
            ann_text = zf.read(ann_files[stem]).decode('utf-8', errors='replace')

            # 解析图片尺寸(用 PIL 读 zip 中的字节流)
            img_bytes = zf.read(img_path)
            try:
                im = Image.open(io.BytesIO(img_bytes))
                W, H = im.size
            except Exception:
                continue

            # 转换标注
            new_lines = []
            for line in ann_text.strip().splitlines():
                parts = line.strip().split(',')
                if len(parts) < 6:
                    continue
                try:
                    x = int(parts[0])
                    y = int(parts[1])
                    w = int(parts[2])
                    h = int(parts[3])
                    score = int(parts[4])
                    cat = int(parts[5])
                except ValueError:
                    continue
                # score=0 表示无效(忽略区)
                if score == 0:
                    skipped_score += 1
                    continue
                # 类映射
                if cat not in VISDRONE_TO_TARGET:
                    continue
                target_name = VISDRONE_TO_TARGET[cat]
                target_id = TARGET_TO_ID[target_name]
                # YOLO 归一化
                if w <= 0 or h <= 0:
                    continue
                cx = (x + w / 2) / W
                cy = (y + h / 2) / H
                nw = w / W
                nh = h / H
                cx, cy = max(0, min(1, cx)), max(0, min(1, cy))
                nw, nh = max(0, min(1, nw)), max(0, min(1, nh))
                if nw <= 0 or nh <= 0:
                    continue
                new_lines.append(f"{target_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
                class_count[target_name] += 1
                box_count += 1

            if not new_lines:
                continue  # 这张图无目标类标注,跳过

            # 输出文件名(zip 前缀 + 原 stem)
            out_name = f"{prefix}_{stem}"
            out_img = OUT_IMG_DIR / f"{out_name}.jpg"
            out_lbl = OUT_LBL_DIR / f"{out_name}.txt"

            with open(out_img, 'wb') as f:
                f.write(img_bytes)
            with open(out_lbl, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
            img_written += 1

    print(f"   ✅ 写入 {img_written} 张图({box_count} 个标注框)")
    print(f"   跳过(score=0): {skipped_score} 个")
    return img_written, box_count, class_count


def main():
    # 支持命令行传 zip 路径
    if len(sys.argv) > 1:
        zips = [Path(p) for p in sys.argv[1:]]
    else:
        zips = [Path(p) for p in DEFAULT_ZIPS]

    print("=" * 70)
    print("VisDrone → 8 类 YOLO 格式转换")
    print("=" * 70)

    total_imgs = 0
    total_boxes = 0
    total_class = {n: 0 for n in TARGET_CLASSES}

    for z in zips:
        if not z.exists():
            print(f"\n⏭️  {z.name} 不存在,跳过")
            continue
        imgs, boxes, cls = convert_one_zip(z)
        total_imgs += imgs
        total_boxes += boxes
        for k, v in cls.items():
            total_class[k] += v

    print(f"\n{'=' * 70}")
    print(f"🎉 转换完成!")
    print(f"{'=' * 70}")
    print(f"   输出位置:{OUT_DIR}")
    print(f"   总图片:{total_imgs} 张")
    print(f"   总标注框:{total_boxes} 个")
    print(f"   平均每图框数:{total_boxes / max(total_imgs, 1):.1f} (越高 = 多类共存越多)")
    print(f"\n📊 各类标注框数:")
    for n in TARGET_CLASSES:
        if total_class[n] > 0:
            print(f"     {n:15s}: {total_class[n]}")

    print(f"\n💡 下一步:")
    print(f"   1. 检查 {OUT_DIR} 里的图和 labels")
    print(f"   2. 用 merge 脚本把这些合并到主训练集")


if __name__ == "__main__":
    main()
