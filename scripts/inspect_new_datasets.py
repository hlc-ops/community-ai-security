"""检查新下载的 16 个数据集的真实类名和图片数量"""
import zipfile
import yaml
import os
import sys

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

folder = r"D:\智慧社区数据集汇总"
new_zips = [
    # 车类
    ("bus detection.v3i.yolov8.zip", "car"),
    ("detection bus.v1i.yolov8.zip", "car"),
    ("Bus Detection.v1i.yolov8.zip", "car"),
    ("truck detection.v1i.yolov8.zip", "car"),
    ("Truck Detection.v3i.yolov8.zip", "car"),
    ("Vehiculos_LSP.v1i.yolov8.zip", "car"),
    ("tricycle-object-detection.v2-tricycle-object-tracing2.yolov8.zip", "car"),
    ("Auto Rickshaw Types.v1i.yolov8.zip", "car"),
    ("threeWheeler_detection.v1i.yolov8.zip", "car"),
    ("van.v2i.yolov8.zip", "car"),
    # 猫狗
    ("cat project.v4i.yolov8.zip", "cat"),
    ("dog-detect.v1-dog-detect-v1.yolov8.zip", "dog"),
    # 垃圾(瓶罐 → trash_item)
    ("All plastic bottle.v5-no_augmentation.yolov8.zip", "trash_item"),
    ("can.v1i.yolov8.zip", "trash_item"),
    # 明火
    ("fire.v4i.yolov8.zip", "fire"),
    ("Fire Source Detection.v2i.yolov8.zip", "fire"),
    # === 第三轮(2026-06-21)===
    ("my_school_bike.v1i.yolov8.zip", "electric_bike"),
    ("bicycle.v1i.yolov8.zip", "electric_bike"),
    ("motorcycle models.v2i.yolov8.zip", "electric_bike"),
    ("Plastic bag.v1i.yolov8.zip", "trash_bag"),
    ("plastic.v1i.yolov8.zip", "trash_bag"),
    ("plastic bag.v1i.yolov8 (1).zip", "trash_bag"),
    ("Garbage.v1i.yolov8.zip", "trash_bag"),
]

sep = "=" * 95
print(sep)
print(f"{'数据集':52s} | {'图数':>5s} | {'分到':10s} | 真实类名")
print(sep)

for z, target in new_zips:
    path = os.path.join(folder, z)
    if not os.path.exists(path):
        print(f"{z[:52]:52s} | ❌ 文件缺失")
        continue
    try:
        with zipfile.ZipFile(path) as zf:
            data_yaml = None
            img_count = 0
            for n in zf.namelist():
                if n.endswith("data.yaml") and not data_yaml:
                    data_yaml = zf.read(n).decode("utf-8", errors="replace")
                if "/images/" in n and any(n.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".bmp")):
                    img_count += 1
            if data_yaml:
                cfg = yaml.safe_load(data_yaml)
                names = cfg.get("names", [])
                if isinstance(names, dict):
                    names = [names[i] for i in sorted(names.keys())]
                names_str = str(names)
            else:
                names_str = "(无 data.yaml)"
            print(f"{z[:52]:52s} | {img_count:5d} | → {target:8s} | {names_str}")
    except Exception as e:
        print(f"{z[:52]:52s} | ERROR: {e}")

print(sep)
