# -*- coding: utf-8 -*-
"""
检查 TMP 采样区（glyphRect 外扩 padding）是否越界、是否压到别的字形。

TMP_Text.cs 实际采样：
    uv0.x = (glyphRect.x - padding) / atlasWidth
    uv2.x = (glyphRect.x + padding + glyphRect.width) / atlasWidth
=> 实际读取的图集区域 = [x-padding, x+width+padding)

若这个区域越过图集边界，或者覆盖到相邻字形 -> 画面出现横条错位。
"""
import io
import os
import re
import sys

P = sys.argv[1] if len(sys.argv) > 1 else \
    r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\Assets\AdSDK\Font\DroidSansFallback SDF.asset'
s = io.open(P, encoding='utf-8').read()

pad = int(re.search(r'  m_AtlasPadding: (\d+)', s).group(1))
AW = int(re.search(r'  m_AtlasWidth: (\d+)', s).group(1))
AH = int(re.search(r'  m_AtlasHeight: (\d+)', s).group(1))
print('m_AtlasPadding=%d  m_AtlasWidth=%d  m_AtlasHeight=%d' % (pad, AW, AH))

i_g = s.index('  m_GlyphTable:')
i_c = s.index('  m_CharacterTable:')
gt, ct = s[i_g:i_c], s[i_c:s.index('  m_AtlasTextures:')]

uni2gid = {}
for m in re.finditer(r'  - m_ElementType: \d+\n    m_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', ct):
    uni2gid[int(m.group(2))] = int(m.group(1))

rects = []
for m in re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S):
    gid, b = int(m.group(1)), m.group(2)
    g = re.search(r'    m_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', b)
    ai = int(re.search(r'    m_AtlasIndex: (\d+)', b).group(1))
    x, y, w, h = map(int, g.groups())
    if w < 2 or h < 2:
        continue
    rects.append((gid, uni2gid.get(gid, -1), ai, x, y, w, h))

print('可视字形 %d' % len(rects))

# 1) 采样区越界
oob = []
for gid, uni, ai, x, y, w, h in rects:
    sx0, sy0 = x - pad, y - pad
    sx1, sy1 = x + w + pad, y + h + pad
    if sx0 < 0 or sy0 < 0 or sx1 > AW or sy1 > AH:
        oob.append((gid, uni, ai, sx0, sy0, sx1, sy1))

print('\n=== 采样区越出图集边界 ===')
print('%d / %d' % (len(oob), len(rects)))
for gid, uni, ai, a, b, c, d in oob[:12]:
    print('  gid=%-4d U+%04X「%s」atlas%d  采样区(%d,%d)-(%d,%d)'
          % (gid, uni, chr(uni) if 32 <= uni < 0x10000 else '?', ai, a, b, c, d))

# 2) 采样区压到相邻字形（同一张图集内，矩形相交）
print('\n=== 采样区压到其他字形 ===')
by_atlas = {}
for r in rects:
    by_atlas.setdefault(r[2], []).append(r)

overlap_count = 0
samples = []
for ai, lst in by_atlas.items():
    # 用扫描线思想：按 x 排序，只比较附近
    sx = sorted(lst, key=lambda r: r[3])
    for i in range(len(sx)):
        gid1, uni1, _, x1, y1, w1, h1 = sx[i]
        s1 = (x1 - pad, y1 - pad, x1 + w1 + pad, y1 + h1 + pad)
        for j in range(i + 1, len(sx)):
            gid2, uni2, _, x2, y2, w2, h2 = sx[j]
            if x2 - pad >= s1[2]:
                break
            r2 = (x2, y2, x2 + w2, y2 + h2)
            if (s1[0] < r2[2] and s1[2] > r2[0] and
                    s1[1] < r2[3] and s1[3] > r2[1]):
                overlap_count += 1
                if len(samples) < 12:
                    samples.append((gid1, uni1, gid2, uni2, ai))

print('%d 对冲突' % overlap_count)
for g1, u1, g2, u2, ai in samples:
    print('  gid=%-4d「%s」 的采样区压到 gid=%-4d「%s」 (atlas%d)'
          % (g1, chr(u1) if 32 <= u1 < 0x10000 else '?',
             g2, chr(u2) if 32 <= u2 < 0x10000 else '?', ai))

# 3) 统计：字形之间最小间隙
if rects:
    print('\n=== 字形矩形之间的最小间隙（不是槽位，是本体）===')
    gaps = []
    for ai, lst in by_atlas.items():
        sx = sorted(lst, key=lambda r: r[3])
        for i in range(len(sx)):
            _, _, _, x1, y1, w1, h1 = sx[i]
            for j in range(i + 1, min(i + 4, len(sx))):
                _, _, _, x2, y2, w2, h2 = sx[j]
                gx = x2 - (x1 + w1)
                if gx >= 0:
                    gaps.append(gx)
    if gaps:
        import statistics
        print('  %d 个左右邻接对，最小 %d，中位 %d' % (len(gaps), min(gaps), statistics.median(gaps)))
        print('  需要 >= 2*padding = %d 才能让采样区互不重叠' % (2 * pad))
