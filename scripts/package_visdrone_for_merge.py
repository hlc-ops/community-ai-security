"""把 _visdrone_converted/ 打包成符合 merge 脚本结构的 YOLO 数据集 zip

打包成 VisDrone_v1.yolov8.zip,包含:
- data.yaml(类名 = 我们的 8 类)
- train/images/*.jpg(全部图)
- train/labels/*.txt(全部 YOLO 标注)

(merge_datasets.py 会在末尾自动 80/10/10 切分,所以这里全放 train/)
"""
import os
import sys
import zipfile
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SRC_IMG = Path(r"D:\智慧社区数据集汇总\_visdrone_converted\images")
SRC_LBL = Path(r"D:\智慧社区数据集汇总\_visdrone_converted\labels")
OUT_ZIP = Path(r"D:\智慧社区数据集汇总\VisDrone_v1.yolov8.zip")

DATA_YAML = """train: train/images
val: val/images
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
"""


def main():
    if not SRC_IMG.exists():
        print(f"❌ 源目录不存在:{SRC_IMG}")
        print("   请先跑 convert_visdrone_to_8class.py")
        sys.exit(1)

    imgs = sorted(SRC_IMG.glob("*.jpg"))
    lbls = sorted(SRC_LBL.glob("*.txt"))
    print(f"📂 源:{len(imgs)} 张图,{len(lbls)} 个标注")

    if len(imgs) == 0:
        print("❌ 没有图片,先跑转换脚本")
        sys.exit(1)

    print(f"📦 打包成 {OUT_ZIP.name}(约 1.6 GB,需要 3-5 分钟)...")

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_STORED) as zf:
        # data.yaml
        zf.writestr("VisDrone_v1.yolov8/data.yaml", DATA_YAML)

        # train/images/
        for i, img in enumerate(imgs, 1):
            arc = f"VisDrone_v1.yolov8/train/images/{img.name}"
            zf.write(img, arc)
            if i % 500 == 0:
                print(f"   {i}/{len(imgs)} 张图已写入")

        # train/labels/
        for i, lbl in enumerate(lbls, 1):
            arc = f"VisDrone_v1.yolov8/train/labels/{lbl.name}"
            zf.write(lbl, arc)
            if i % 500 == 0:
                print(f"   {i}/{len(lbls)} 个标注已写入")

    size_mb = OUT_ZIP.stat().st_size / 1024 / 1024
    print(f"\n✅ 完成!{OUT_ZIP}")
    print(f"   大小:{size_mb:.1f} MB")
    print(f"\n💡 下一步:")
    print(f"   1. 更新 merge_datasets.py 加入 VisDrone_v1.yolov8 的映射")
    print(f"   2. 重跑 merge,生成 V3 数据集")


if __name__ == "__main__":
    main()
