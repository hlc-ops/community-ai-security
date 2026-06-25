"""Pose 行为识别 · 单张图测试脚本

用法:
    cd D:\\Python\\PyCharm\\PythonProject\\智慧社区Web项目
    D:/Python/Python/python.exe scripts/test_pose_on_image.py 图片路径

示例:
    D:/Python/Python/python.exe scripts/test_pose_on_image.py D:/test/falling.jpg

功能:
    1. 加载 YOLOv8-pose 预训练模型(首次自动下载 ~22MB)
    2. 对图片提取所有人的 17 个关键点
    3. 跑 4 个行为规则(摔倒/翻墙/打架/奔跑)
    4. 保存标注图到同目录 _pose_result.jpg
"""
import sys
import os
import json
from pathlib import Path

# 把项目根加到 sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    if len(sys.argv) < 2:
        print("用法: python test_pose_on_image.py <图片路径>")
        print("示例: python test_pose_on_image.py D:/test/falling.jpg")
        sys.exit(1)

    img_path = sys.argv[1]
    if not os.path.exists(img_path):
        print(f"❌ 图片不存在: {img_path}")
        sys.exit(1)

    print("=" * 60)
    print("Pose 行为识别 · 单张图测试")
    print("=" * 60)
    print(f"\n📷 图片: {img_path}")

    print("\n📥 加载 YOLOv8-pose 模型(首次会下载 ~22MB)...")
    from backend.pose_detector import PoseDetector
    import cv2

    detector = PoseDetector(model_path="yolov8s-pose.pt")
    print("✅ 模型加载完成")

    # 读图
    frame = cv2.imread(img_path)
    if frame is None:
        print(f"❌ 无法读取图片(格式不支持?)")
        sys.exit(1)
    h, w = frame.shape[:2]
    print(f"\n📐 图片尺寸: {w} × {h}")

    # 提取关键点
    print("\n🔍 提取人体关键点...")
    persons = detector.extract(frame, conf=0.4)
    print(f"✅ 检测到 {len(persons)} 个人")

    if not persons:
        print("\n⚠️  未检测到人,请换一张含清晰人体的图")
        sys.exit(0)

    # 列出每个人的关键点情况
    for i, p in enumerate(persons):
        present = sum(1 for kp in p['keypoints'] if kp is not None)
        print(f"   人 #{i + 1}: 置信度 {p['score']:.2f}, "
              f"{present}/17 个关键点可见, "
              f"框=({p['box'][0]}, {p['box'][1]}, {p['box'][2]}, {p['box'][3]})")

    # 跑行为规则
    print("\n🧠 跑行为规则引擎...")
    from backend.behavior_rules import PoseBehaviorAnalyzer
    analyzer = PoseBehaviorAnalyzer()

    # 单帧判定(不走时序去抖,所有规则单独测一次)
    print("\n--- 单帧判定 ---")
    for i, p in enumerate(persons):
        kps = p['keypoints_norm']
        is_fall = analyzer._is_fallen_pose(kps)
        is_climb = analyzer._is_climbing_pose(kps)
        is_run = analyzer._is_running_pose(kps, prev_kps=None)
        print(f"  人 #{i + 1}:")
        print(f"    摔倒姿态:    {'✅ 是' if is_fall else '❌ 否'}")
        print(f"    翻墙姿态:    {'✅ 是' if is_climb else '❌ 否'}")
        print(f"    奔跑姿态:    {'✅ 是' if is_run else '❌ 否(需要上一帧对比)'}")

    if len(persons) >= 2:
        print(f"\n  两两打架判定:")
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                is_fight = analyzer._is_fighting_pair(
                    persons[i]['keypoints_norm'],
                    persons[j]['keypoints_norm'],
                )
                print(f"    人 #{i + 1} <-> 人 #{j + 1}: {'✅ 是' if is_fight else '❌ 否'}")

    # 多帧时序模拟(重复 5 帧)
    print(f"\n--- 时序判定(模拟 5 帧持续场景)---")
    import time
    analyzer2 = PoseBehaviorAnalyzer()
    for frame_idx in range(5):
        events = analyzer2.analyze(persons)
        ts = frame_idx * 0.5
        evt_types = [e['type'] for e in events] or ['无']
        print(f"  帧 {frame_idx + 1} (t={ts}s): {evt_types}")
        time.sleep(0.5)

    # 保存标注图
    print("\n🎨 生成可视化标注...")
    out = frame.copy()
    SKELETON = [
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
        (0, 1), (0, 2), (1, 3), (2, 4),
    ]
    COLORS = [
        (78, 205, 196), (91, 155, 255), (255, 183, 77),
        (255, 84, 112), (167, 139, 250),
    ]
    for i, p in enumerate(persons):
        color = COLORS[i % len(COLORS)]
        x1, y1, x2, y2 = p['box']
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

        # 画关键点
        for kp in p['keypoints']:
            if kp:
                cv2.circle(out, (int(kp['x']), int(kp['y'])), 4, color, -1)

        # 画骨架
        for a, b in SKELETON:
            ka, kb = p['keypoints'][a], p['keypoints'][b]
            if ka and kb:
                cv2.line(out,
                         (int(ka['x']), int(ka['y'])),
                         (int(kb['x']), int(kb['y'])),
                         color, 2)

        # 标记
        kps = p['keypoints_norm']
        labels = []
        if analyzer._is_fallen_pose(kps): labels.append("FALL")
        if analyzer._is_climbing_pose(kps): labels.append("CLIMB")
        if labels:
            label = " + ".join(labels)
            cv2.putText(out, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    out_path = os.path.splitext(img_path)[0] + "_pose_result.jpg"
    cv2.imwrite(out_path, out)
    print(f"✅ 标注图已保存: {out_path}")

    print("\n" + "=" * 60)
    print("测试完成!打开标注图看效果")
    print("=" * 60)


if __name__ == "__main__":
    main()
