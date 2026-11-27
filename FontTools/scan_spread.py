# -*- coding: utf-8 -*-
"""
在真实字形上扫描 spread 取值，量出「笔画中心能达到的最大 alpha」和边缘过渡宽度。
目标：笔画中心 = 255（纯白），同时边缘过渡带 >= 1.5px（不硬）。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdf_fast import glyph_sdf

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'
TTFP = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback.ttf')
PS = 90
PAD = 12

ft = ImageFont.truetype(TTFP, PS)


def rasterize(ch):
    top, bottom = int(PS * 1.3), int(PS * 0.6)
    left, right = int(PS * 0.35), int(PS * 1.6)
    im = Image.new('L', (left + right, top + bottom), 0)
    ImageDraw.Draw(im).text((left, top), ch, fill=255, font=ft, anchor='ls')
    a = np.array(im)
    ys, xs = np.nonzero(a)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return (a[y0:y1, x0:x1] > 110)


def stroke_widths(mask):
    runs = []
    for row in mask:
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        s = np.where(d == 1)[0]
        e = np.where(d == -1)[0]
        runs.extend((e - s).tolist())
    return np.array(runs)


print('%-6s %8s %8s %8s %8s' % ('spread', 'max_alpha', '中心>=250%', '>=200%', '过渡px'))
for spread in (3.0, 4.0, 5.0, 6.0, 7.0, 9.0, 12.0):
    stats = []
    for ch in '看视频领取奖励返回首页开始设置':
        m = rasterize(ch)
        h, w = m.shape
        canvas = np.zeros((h + PAD * 2, w + PAD * 2), dtype=bool)
        canvas[PAD:PAD + h, PAD:PAD + w] = m
        sdf = glyph_sdf(canvas, PAD, spread)
        core = sdf[m.sum() > 0 and slice(PAD, PAD + h), :][:, PAD:PAD + w] if False else \
            sdf[PAD:PAD + h, PAD:PAD + w]
        # 只在「腐蚀后仍属实体」的像素上看中心值
        solid = m.copy()
        for _ in range(2):
            solid = (solid & np.roll(solid, 1, 0) & np.roll(solid, -1, 0)
                     & np.roll(solid, 1, 1) & np.roll(solid, -1, 1))
        if solid.sum() < 20:
            continue
        stats.append((core[solid].max(), (core[solid] >= 250).mean() * 100,
                      (core >= 200).sum() * 100.0 / core.size))
    a = np.array(stats)
    print('%-6.1f %8.0f %8.1f %8.1f   (±%.1f)'
          % (spread, a[:, 0].mean(), a[:, 1].mean(), a[:, 2].mean(), spread))

print('\n笔画宽度参考（90pt）:')
w = stroke_widths(rasterize('看'))
print('  中位 %d  25%%=%d  75%%=%d  最小 %d'
      % (np.median(w), np.percentile(w, 25), np.percentile(w, 75), w.min()))
print('  笔画半宽 = %.1f px' % (np.median(w) / 2.0))
