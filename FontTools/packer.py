# -*- coding: utf-8 -*-
"""可靠的 2D 装箱：MaxRects 最佳短边匹配（BSSF），工业级利用率。"""


def maxrects_pack(items, aw, ah, gap=0):
    """
    items: [(w, h, key)]  尺寸需已包含 gap
    返回 (placed, unplaced)，placed = [(x, y, key)]
    """
    # 空闲矩形列表：(x, y, w, h)
    free = [(0, 0, aw, ah)]
    placed = []
    unplaced = []

    # 面积大的先放
    order = sorted(items, key=lambda t: (-t[0] * t[1], -t[1]))

    for (w, h, key) in order:
        best = None
        best_score = None
        for (fx, fy, fw, fh) in free:
            if w > fw or h > fh:
                continue
            left = fw - w
            right = fh - h
            short = min(left, right)
            long_ = max(left, right)
            score = (short, long_)
            if best_score is None or score < best_score:
                best_score = score
                best = (fx, fy, fw, fh)
        if best is None:
            unplaced.append(key)
            continue

        fx, fy, fw, fh = best
        x, y = fx, fy
        placed.append((x, y, key))

        # 切分空闲矩形
        new_free = []
        for (rx, ry, rw, rh) in free:
            if x >= rx + rw or x + w <= rx or y >= ry + rh or y + h <= ry:
                new_free.append((rx, ry, rw, rh))
                continue
            if y > ry:
                new_free.append((rx, ry, rw, y - ry))
            if y + h < ry + rh:
                new_free.append((rx, y + h, rw, ry + rh - (y + h)))
            if x > rx:
                new_free.append((rx, ry, x - rx, rh))
            if x + w < rx + rw:
                new_free.append((x + w, ry, rx + rw - (x + w), rh))
        # 剪除被包含的碎片
        pruned = []
        for i, a in enumerate(new_free):
            if a[2] <= 0 or a[3] <= 0:
                continue
            dup = False
            for j, b in enumerate(new_free):
                if i == j:
                    continue
                if b[2] <= 0 or b[3] <= 0:
                    continue
                if (a[0] >= b[0] and a[1] >= b[1] and
                        a[0] + a[2] <= b[0] + b[2] and a[1] + a[3] <= b[1] + b[3]):
                    if a != b or i > j:
                        dup = True
                        break
            if not dup:
                pruned.append(a)
        free = pruned

    return placed, unplaced
