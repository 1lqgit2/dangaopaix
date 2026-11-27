# -*- coding: utf-8 -*-
"""
量化 spread 的边缘过渡宽度与"灰度厚度"，并用 TMP 公式出预览图。
过渡宽度 = 横穿笔画边缘时，alpha 从 15% 升到 85% 所需像素数。
视觉最优：过渡宽度 1.2 ~ 2.0 px（足够柔，又不糊）。
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
TXT = '看视频领取奖励返回首页'

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


def build(ch, spread):
    m = rasterize(ch)
    h, w = m.shape
    c = np.zeros((h + PAD * 2, w + PAD * 2), dtype=bool)
    c[PAD:PAD + h, PAD:PAD + w] = m
    sdf = glyph_sdf(c, PAD, spread).astype(np.float32) / 255.0
    return sdf, m


print('%-6s %10s %10s' % ('spread', '过渡宽(px)', '中位笔画宽'))
best = None
for spread in (2.5, 3.0, 3.5, 4.0, 5.0):
    tw = []
    for ch in TXT:
        sdf, m = build(ch, spread)
        for row in sdf:
            d = np.diff(np.concatenate([[0], (row > 0.15).astype(np.int8), [0]]))
            st = np.where(d == 1)[0]
            en = np.where(d == -1)[0]
            for s, e in zip(st, en):
                seg = row[max(0, s - 3):e + 3]
                if (seg >= 0.85).any():
                    tw.append(((seg >= 0.15) & (seg <= 0.85)).sum())
    if tw:
        print('%-6.1f %10.2f' % (spread, np.mean(tw)))
    else:
        print('%-6.1f %10s' % (spread, '无过渡(全灰)'))

# 出对比预览
SPREAD = 3.0
rows = []
for txt in (TXT, '返回首页开始'):
    imgs = []
    for ch in txt:
        sdf, m = build(ch, SPREAD)
        h, w = sdf.shape
        a = (np.clip(sdf, 0, 1) * 255).astype(np.uint8)
        # 深色底合成
        rgb = np.zeros((h, w, 3), np.uint8)
        rgb[:] = 46
        cov = sdf[..., None]
        rgb = (rgb * (1 - cov) + 255 * cov).astype(np.uint8)
        imgs.append(rgb)
    W = sum(i.shape[1] for i in imgs)
    H = max(i.shape[0] for i in imgs)
    line = np.zeros((H, W, 3), np.uint8)
    line[:] = 46
    x = 0
    for i in imgs:
        line[:i.shape[0], x:x + i.shape[1]] = i
        x += i.shape[1]
    rows.append(line)

W = max(r.shape[1] for r in rows)
H = sum(r.shape[0] for r in rows)
out = np.zeros((H, W, 3), np.uint8)
out[:] = 46
y = 0
for r in rows:
    out[y:y + r.shape[0], :r.shape[1]] = r
    y += r.shape[0]
p = os.path.join(PROJ, 'FontTools', 'spread3_preview.png')
Image.fromarray(out).save(p)
print('\n预览:', p, out.shape)
