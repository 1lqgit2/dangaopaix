# -*- coding: utf-8 -*-
"""字体资产完整性最终校验。"""
import io
import re

import numpy as np

# 用法: python check_font_asset.py <字体资产.asset>
import sys
P = sys.argv[1] if len(sys.argv) > 1 else input("字体资产路径: ").strip('"')
SIZE = 2048  # 若图集不是 2048，改这里

s = io.open(P, encoding='utf-8').read()

# 抓全部字形块
pat = re.compile(
    r'm_GlyphRect:\n      m_X: (\d+)\n      m_Y: (\d+)\n'
    r'      m_Width: (\d+)\n      m_Height: (\d+)\n'
    r'    m_Scale: [-\d.]+\n    m_AtlasIndex: (\d+)')
blocks = pat.findall(s)
print('抓到字形块:', len(blocks))

rects = [tuple(int(v) for v in b) for b in blocks]
nonempty = [r for r in rects if r[2] > 0 and r[3] > 0]
print('非空字形:', len(nonempty), ' 空字形:', len(rects) - len(nonempty))

allok = True
for a in (0, 1):
    rs = [(x, y, w, h) for (x, y, w, h, ai) in nonempty if ai == a]
    if not rs:
        print('图集%d: 空' % a)
        continue
    xs = [r[0] for r in rs]
    xe = [r[0] + r[2] for r in rs]
    ys = [r[1] for r in rs]
    ye = [r[1] + r[3] for r in rs]
    occ = np.zeros((SIZE, SIZE), np.int8)
    for x, y, w, h in rs:
        occ[y:y + h, x:x + w] += 1
    over = [r for r in rs if r[0] + r[2] > SIZE or r[1] + r[3] > SIZE]
    print('图集%d: %d 个   x[%d,%d] y[%d,%d]   最大重叠=%d  重叠像素=%d  越界=%d'
          % (a, len(rs), min(xs), max(xe), min(ys), max(ye),
             occ.max(), int((occ > 1).sum()), len(over)))
    if occ.max() > 1 or over:
        allok = False

# 每张图集的实际占用与矩形的一致性
fids = re.findall(r'fileID: (\d+)', re.search(r'm_AtlasTextures:\n((?:  - \{fileID: \d+\}\n)+)', s).group(1))
for ai, fid in enumerate(fids):
    st = s.index('&%s\nTexture2D:' % fid)
    en = s.find('\n--- ', st)
    en = len(s) if en < 0 else en
    seg = s[st:en]
    raw = bytes.fromhex(re.search(r'_typelessdata: ([0-9a-f]+)', seg).group(1))
    # 资产里存的是 Unity 纹理字节序（自下而上）；GlyphRect.y 与之同向，
    # 需先 flipud 得到「自上而下」视图，才能与 PIL/numpy 的 y 索引一致
    img = np.flipud(np.frombuffer(raw, dtype=np.uint8).reshape(SIZE, SIZE))
    pix_mask = img > 128
    rect_mask = np.zeros((SIZE, SIZE), bool)
    for (x, y, w, h, a2) in nonempty:
        if a2 == ai:
            rect_mask[y:y + h, x:x + w] = True
    inside = int((pix_mask & rect_mask).sum())
    outside = int((pix_mask & ~rect_mask).sum())
    total_pix = int(pix_mask.sum())
    print('图集%d(%s): 实心像素=%d, 其中在矩形内=%d, 落在矩形外=%d (%.1f%%)'
          % (ai, fid[-6:], total_pix, inside, outside,
             outside / max(1, total_pix) * 100))
    if outside > total_pix * 0.02:
        print('  警告：矩形外像素过多，可能存在错位')
        allok = False

print()
print('最终校验:', '通过' if allok else '存在问题')
