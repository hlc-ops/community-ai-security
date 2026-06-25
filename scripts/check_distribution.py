"""统计最终数据集每类的图片数和标注框数"""
import os
import sys
from collections import Counter

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

NAMES = ['person', 'car', 'dog', 'cat', 'trash_bag', 'trash_item', 'electric_bike', 'fire']
ZH = ['行人', '车辆', '狗', '猫', '弃置垃圾袋', '散落垃圾', '电瓶车', '明火']
base = r'D:\智慧社区数据集汇总\_processed\labels'

total_boxes = Counter()
total_imgs = Counter()

for split in ['train', 'val', 'test']:
    split_dir = os.path.join(base, split)
    if not os.path.exists(split_dir):
        continue
    for fn in os.listdir(split_dir):
        if not fn.endswith('.txt'):
            continue
        cls_in_img = set()
        with open(os.path.join(split_dir, fn), 'r') as f:
            for line in f:
                parts = line.split()
                if parts:
                    try:
                        cid = int(parts[0])
                        total_boxes[cid] += 1
                        cls_in_img.add(cid)
                    except ValueError:
                        pass
        for cid in cls_in_img:
            total_imgs[cid] += 1

print('=' * 70)
print(f'{"类别":18s} | {"图片数":>10s} | {"标注框数":>10s}')
print('=' * 70)
total_b = 0
for cid in range(8):
    bi = total_imgs[cid]
    bb = total_boxes[cid]
    total_b += bb
    label = f"{NAMES[cid]}({ZH[cid]})"
    print(f'{label:18s} | {bi:10d} | {bb:10d}')
print('=' * 70)
print(f'{"总标注框":18s} | {"":>10s} | {total_b:10d}')
