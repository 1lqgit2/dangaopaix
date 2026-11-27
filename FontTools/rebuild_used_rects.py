# -*- coding: utf-8 -*-
"""
重算 m_UsedGlyphRects（按激活图集），并给出 m_FreeGlyphRects。

注意：m_UsedGlyphRects / m_FreeGlyphRects 只描述 **m_AtlasTextureIndex 指向的那一张**
图集。非激活图集的占用信息不在这两个列表里表达。

每个 Used 矩形 = 字形本体外扩 padding（即 TMP 的采样区 = 槽位）。
因为 TMP 就是用 [x-padding, x+width+padding) 去采样的，
所以「已被占用」的区域必须是这个外扩后的范围，否则新字形会被装进
渐变带里，把已有字形的边缘覆盖掉。
"""
import io
import re
import sys

import numpy as np

P = sys.argv[1] if len(sys.argv) > 1 else \
    r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\Assets\AdSDK\Font\DroidSansFallback SDF.asset'
s = io.open(P, encoding='utf-8').read()

pad = int(re.search(r'  m_AtlasPadding: (\d+)', s).group(1))
AW = int(re.search(r'  m_AtlasWidth: (\d+)', s).group(1))
AH = int(re.search(r'  m_AtlasHeight: (\d+)', s).group(1))
ACT = int(re.search(r'  m_AtlasTextureIndex: (\d+)', s).group(1))
print('padding=%d atlas=%dx%d 激活=%d' % (pad, AW, AH, ACT))

i_g = s.index('  m_GlyphTable:')
i_c = s.index('  m_CharacterTable:')
gt = s[i_g:i_c]

used = {0: [], 1: []}
for m in re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S):
    b = m.group(2)
    r = re.search(r'    m_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', b)
    ai = int(re.search(r'    m_AtlasIndex: (\d+)', b).group(1))
    x, y, w, h = map(int, r.groups())
    if w < 2 or h < 2:
        continue
    # 采样区 = 本体外扩 padding
    x0, y0 = x - pad, y - pad
    if x0 < 0 or y0 < 0 or x0 + w + pad * 2 > AW or y0 + h + pad * 2 > AH:
        # 越界时夹紧
        x0 = max(0, min(x0, AW - 1))
        y0 = max(0, min(y0, AH - 1))
    bw = min(w + pad * 2, AW - x0)
    bh = min(h + pad * 2, AH - y0)
    used.setdefault(ai, []).append((x0, y0, bw, bh))

print('占用矩形：atlas0=%d  atlas1=%d' % (len(used[0]), len(used[1])))

cur = sorted(used[ACT])
print('激活图的占用矩形 %d 条' % len(cur))

# 计算最大空闲矩形（直方图法）
occ = np.zeros((AH, AW), dtype=bool)
for (x, y, w, h) in cur:
    occ[y:y + h, x:x + w] = True
print('图集占用率 %.1f%%' % (occ.mean() * 100))

heights = np.zeros(AW, dtype=np.int64)
best = (0, 0, 0, 0, 0)
for yy in range(AH):
    heights = np.where(occ[yy], 0, heights + 1)
    stack = []
    for xx in range(AW + 1):
        c = heights[xx] if xx < AW else 0
        start = xx
        while stack and stack[-1][1] >= c:
            sx, hh = stack.pop()
            area = hh * (xx - sx)
            if area > best[0]:
                best = (area, sx, yy - hh + 1, xx - sx, hh)
            start = sx
        stack.append((start, c))

_, fx, fy, fw, fh = best
print('最大空闲矩形 (%d,%d) %dx%d' % (fx, fy, fw, fh))

# 生成文本：在 Static 模式下，所有已知字形都应登记为已占用，
# 且不再留「空闲」给运行时写入（Static 不会写入新字形，
# 但保留一个合理空闲矩形可避免编辑器告警）。
used_txt = ''.join('  - m_X: %d\n    m_Y: %d\n    m_Width: %d\n    m_Height: %d\n' % r
                   for r in cur)
free_txt = ''

m = re.search(r'  m_UsedGlyphRects:\n((?:  - m_X: [-\d]+\n    m_Y: [-\d]+\n    m_Width: \d+\n    m_Height: \d+\n)*)', s)
if not m:
    print('未找到 m_UsedGlyphRects 块')
    sys.exit(1)
s = s[:m.start(1)] + used_txt + s[m.end(1):]

m = re.search(r'  m_FreeGlyphRects:\n((?:  - m_X: [-\d]+\n    m_Y: [-\d]+\n    m_Width: \d+\n    m_Height: \d+\n)*)', s)
if m:
    s = s[:m.start(1)] + free_txt + s[m.end(1):]
    print('m_FreeGlyphRects 已清空')
else:
    # 已经没有条目，确认字段存在即可
    if '  m_FreeGlyphRects:' in s:
        print('m_FreeGlyphRects 已为空（字段存在）')
    else:
        print('!! 缺少 m_FreeGlyphRects 字段')
        sys.exit(1)

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('已写回：Used %d 条，Free 清空（Static 模式不需要）' % len(cur))
