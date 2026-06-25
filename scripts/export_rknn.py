"""best.onnx → best.rknn 一键转换(瑞芯微 RK3588 / RK3568 / RK3566 边缘盒子用)

⚠️ 必须在 Linux 上跑(Ubuntu 18.04+ / 20.04 / 22.04),Windows 不支持。

环境准备(只装一次):
    # 用 conda 起一个干净的 py3.10 环境
    conda create -n rknn python=3.10 -y
    conda activate rknn

    # 装 RKNN-Toolkit2(瑞芯微官方,选你的目标芯片对应的 whl)
    pip install rknn-toolkit2 -i https://pypi.tuna.tsinghua.edu.cn/simple

    # 装基础依赖
    pip install numpy opencv-python onnx onnxruntime

用法:
    python scripts/export_rknn.py --target rk3588
    python scripts/export_rknn.py --target rk3568   # RK3568 系列
    python scripts/export_rknn.py --target rk3566   # 入门级

校准数据集:
    脚本会从 dataset/images/val/ 随机抽 100 张作为 INT8 量化校准源
    (跟我们 OpenVINO INT8 用的同一套校准策略)
"""
import argparse
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ONNX_PATH = ROOT / "model" / "best.onnx"
DATASET_DIR = ROOT / "dataset" / "images" / "val"
CALIB_LIST = ROOT / "model" / "rknn_calib_list.txt"
IMGSZ = 640


def build_calib_list(n_samples: int = 100) -> Path:
    """从 dataset/images/val 随机抽 N 张图,生成校准用图片列表。"""
    if not DATASET_DIR.exists():
        print(f"❌ 校准数据集不存在: {DATASET_DIR}")
        print("   把 100 张代表性图片放到这个目录,或改 DATASET_DIR")
        sys.exit(1)
    imgs = sorted([p for p in DATASET_DIR.iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    if len(imgs) < 10:
        print(f"⚠️  校准图片不足 10 张(实有 {len(imgs)} 张),量化精度可能下降")
    sample = random.sample(imgs, min(n_samples, len(imgs)))
    with open(CALIB_LIST, "w", encoding="utf-8") as f:
        for p in sample:
            f.write(str(p.resolve()) + "\n")
    print(f"📝 校准列表: {CALIB_LIST}({len(sample)} 张)")
    return CALIB_LIST


def export_rknn(target: str):
    try:
        from rknn.api import RKNN
    except ImportError:
        print("❌ rknn-toolkit2 未安装")
        print("   先跑: pip install rknn-toolkit2 -i https://pypi.tuna.tsinghua.edu.cn/simple")
        sys.exit(1)

    if not ONNX_PATH.exists():
        print(f"❌ ONNX 不存在: {ONNX_PATH}")
        print("   先在 Windows 跑: yolo export model=model/best.pt format=onnx imgsz=640")
        sys.exit(1)

    calib_path = build_calib_list(100)
    out_path = ROOT / "model" / f"best_{target}.rknn"

    rknn = RKNN(verbose=False)

    print(f"\n🔧 配置 (target={target})...")
    rknn.config(
        mean_values=[[0, 0, 0]],
        std_values=[[255, 255, 255]],
        target_platform=target,
        quantized_dtype="asymmetric_quantized-8",
        quantized_algorithm="normal",
        optimization_level=3,
    )

    print(f"📥 载入 ONNX: {ONNX_PATH.name}")
    ret = rknn.load_onnx(model=str(ONNX_PATH))
    if ret != 0:
        print("❌ load_onnx 失败")
        sys.exit(1)

    print(f"⚙️  构建 + INT8 量化(用 {calib_path.name} 校准,约 1-3 分钟)...")
    ret = rknn.build(do_quantization=True, dataset=str(calib_path))
    if ret != 0:
        print("❌ build 失败")
        sys.exit(1)

    print(f"💾 导出: {out_path}")
    ret = rknn.export_rknn(str(out_path))
    if ret != 0:
        print("❌ export 失败")
        sys.exit(1)

    rknn.release()
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\n✅ 完成!  {out_path} ({size_mb:.1f} MB)")
    print(f"\n📦 部署:把这个 .rknn 文件拷到 RK3588 盒子上,")
    print(f"   用 rknn-toolkit-lite2 (设备端版) 或 rknpu2 C++ SDK 加载推理。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="rk3588",
                    choices=["rk3588", "rk3568", "rk3566", "rk3562", "rv1103", "rv1106"],
                    help="目标芯片(默认 RK3588)")
    args = ap.parse_args()
    export_rknn(args.target)


if __name__ == "__main__":
    main()
