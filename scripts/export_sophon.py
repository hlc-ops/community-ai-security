"""best.onnx → best.bmodel 一键转换(算能 SOPHON BM1684 / BM1684X 边缘盒子用)

⚠️ 必须在 Linux 上跑,Windows 不支持。

环境准备(只装一次):
    # Docker 是算能官方推荐(免装一堆系统依赖)
    docker pull sophgo/tpuc_dev:latest
    docker run -it -v /path/to/project:/workspace sophgo/tpuc_dev:latest

    # 容器内激活环境
    source /workspace/tpu-mlir_xxx/envsetup.sh

用法:
    python scripts/export_sophon.py --target bm1684x

说明:
    本脚本只是把"标准转换流程"打包成易复制的命令。
    真实转换走 SOPHON 官方 TPU-MLIR 工具链。
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ONNX_PATH = ROOT / "model" / "best.onnx"
CALIB_DIR = ROOT / "dataset" / "images" / "val"
IMGSZ = 640


CMDS_TEMPLATE = """
# === 1. ONNX → MLIR(中间表示)===
model_transform.py \\
    --model_name community_yolov8s \\
    --model_def {onnx} \\
    --input_shapes [[1,3,{sz},{sz}]] \\
    --mean 0,0,0 \\
    --scale 0.00392156862745,0.00392156862745,0.00392156862745 \\
    --keep_aspect_ratio \\
    --pixel_format rgb \\
    --output_names "output0" \\
    --test_input dataset/images/val/$(ls dataset/images/val/ | head -1) \\
    --test_result community_yolov8s_top_outputs.npz \\
    --mlir community_yolov8s.mlir

# === 2. 生成 INT8 校准表(用 100 张图)===
run_calibration.py community_yolov8s.mlir \\
    --dataset {calib} \\
    --input_num 100 \\
    -o community_yolov8s_cali_table

# === 3. MLIR → BModel(INT8 量化)===
model_deploy.py \\
    --mlir community_yolov8s.mlir \\
    --quantize INT8 \\
    --calibration_table community_yolov8s_cali_table \\
    --chip {target} \\
    --test_input community_yolov8s_in_f32.npz \\
    --test_reference community_yolov8s_top_outputs.npz \\
    --tolerance 0.85,0.45 \\
    --model best_{target}.bmodel

echo "✅ 完成 → best_{target}.bmodel"
echo "📦 拷到 BM1684/BM1684X 盒子上用 sail Python / C++ SDK 加载"
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="bm1684x", choices=["bm1684", "bm1684x", "bm1688"])
    args = ap.parse_args()

    if not ONNX_PATH.exists():
        print(f"❌ {ONNX_PATH} 不存在,先在 Windows 跑 yolo export 出 ONNX")
        sys.exit(1)
    if not CALIB_DIR.exists():
        print(f"❌ {CALIB_DIR} 不存在,放 100 张校准图")
        sys.exit(1)

    cmds = CMDS_TEMPLATE.format(
        onnx=str(ONNX_PATH).replace("\\", "/"),
        calib=str(CALIB_DIR).replace("\\", "/"),
        sz=IMGSZ,
        target=args.target,
    )
    script_path = ROOT / f"_sophon_{args.target}.sh"
    script_path.write_text(cmds, encoding="utf-8")
    print(f"📝 命令脚本已生成: {script_path}")
    print("\n下一步:")
    print(f"  1. 进 TPU-MLIR 的 Docker 容器")
    print(f"  2. cd /workspace && source tpu-mlir_xxx/envsetup.sh")
    print(f"  3. bash {script_path.name}")
    print(f"\n或者直接复制粘贴下面的命令:\n")
    print(cmds)


if __name__ == "__main__":
    main()
