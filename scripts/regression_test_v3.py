"""V3 部署后的回归测试:
- doubao1/    : 7 张图(V2 已通过),V3 应保持识别正确
- doubaotupian/: 4 张图(V2 失败 — 多车/多人只识别一个),V3 应能识别全部

直接调本地 INT8 模型,不走 Flask,跑完输出 per-image 表格 + 标注图。
"""
import os
import sys
from pathlib import Path
from collections import Counter

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from ultralytics import YOLO
import cv2

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "model" / "best_openvino_model"
OUT_DIR = ROOT / f"_v3_regression_out_conf{int(float(os.environ.get('RT_CONF', '0.25'))*100):02d}"
OUT_DIR.mkdir(exist_ok=True)

CLASS_ZH = {
    0: "行人", 1: "车辆", 2: "狗", 3: "猫",
    4: "弃置垃圾袋", 5: "散落垃圾", 6: "电瓶车", 7: "明火",
}

TEST_SETS = {
    "doubao1 (V2 已通过的 7 张图)": Path("D:/doubao1"),
    "doubaotupian (V2 失败的多目标街景)": Path("D:/doubaotupian"),
}

CONF = float(os.environ.get("RT_CONF", "0.25"))
IOU = float(os.environ.get("RT_IOU", "0.45"))


def run_set(model, label, img_dir):
    print(f"\n{'=' * 70}")
    print(f"📂 {label}")
    print(f"   路径: {img_dir}")
    print('=' * 70)

    if not img_dir.exists():
        print("  ❌ 路径不存在,跳过")
        return

    imgs = sorted([p for p in img_dir.iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    if not imgs:
        print("  ❌ 无图,跳过")
        return

    for i, img_path in enumerate(imgs, 1):
        results = model.predict(
            source=str(img_path),
            imgsz=640, conf=CONF, iou=IOU,
            verbose=False, save=False,
        )
        r = results[0]
        boxes = r.boxes
        n = len(boxes) if boxes is not None else 0

        cls_counts = Counter()
        if n > 0:
            for c in boxes.cls.cpu().numpy().astype(int):
                cls_counts[CLASS_ZH.get(c, f"cls_{c}")] += 1

        # 把标注图保存
        save_name = f"{i:02d}_{img_path.stem[:20]}.jpg"
        save_path = OUT_DIR / save_name
        annotated = r.plot()
        cv2.imwrite(str(save_path), annotated)

        cls_str = ", ".join(f"{k} ×{v}" for k, v in cls_counts.items()) if cls_counts else "(空)"
        print(f"\n  图 {i}: {img_path.name[:50]}")
        print(f"    检测框数: {n}")
        print(f"    类别: {cls_str}")
        print(f"    标注图: {save_path.name}")


def main():
    print(f"加载 V3 INT8 模型: {MODEL}")
    if not MODEL.exists():
        print(f"❌ 模型不存在,确认是否已导出")
        sys.exit(1)
    model = YOLO(str(MODEL), task="detect")
    print("✅ 模型加载成功")

    for label, img_dir in TEST_SETS.items():
        run_set(model, label, img_dir)

    print(f"\n{'=' * 70}")
    print(f"🎉 回归测试完成,标注图保存在: {OUT_DIR}")
    print('=' * 70)


if __name__ == "__main__":
    main()
