# -*- coding: utf-8 -*-
"""最终结构校验：glyphRect / Used 是否越界、y 是否已自下而上、关键字段一览。"""
import io
import os
import re

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
s = io.open(ASSET, encoding='utf-8').read()

gt = s[s.index('  m_GlyphTable:'):s.index('  m_CharacterTable:')]
tot = bad = 0
for m in re.finditer(r'm_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', gt):
    x, y, w, h = (int(v) for v in m.groups())
    if w == 0 or h == 0:
        continue
    tot += 1
    if x < 0 or y < 0 or x + w > 2048 or y + h > 2048:
        bad += 1
        if bad <= 5:
            print('  越界: (%d,%d,%d,%d)' % (x, y, w, h))
print('glyphRect 可视字形 %d，越界 %d' % (tot, bad))

mb = re.search(r'  m_UsedGlyphRects:\n(.*?)  m_FreeGlyphRects:', s, re.S)
used = re.findall(r'  - m_X: (-?\d+)\n    m_Y: (-?\d+)\n    m_Width: (\d+)\n    m_Height: (\d+)', mb.group(1))
ubad = 0
for x, y, w, h in used:
    x, y, w, h = int(x), int(y), int(w), int(h)
    if x < 0 or y < 0 or x + w > 2048 or y + h > 2048:
        ubad += 1
print('Used 矩形 %d 条，越界 %d' % (len(used), ubad))

print()
for k, pat in (('m_AtlasPopulationMode', r'm_AtlasPopulationMode: (\d+)'),
               ('m_ClearDynamicDataOnBuild', r'm_ClearDynamicDataOnBuild: (\d+)'),
               ('m_AtlasTextureIndex', r'm_AtlasTextureIndex: (\d+)'),
               ('m_AtlasPadding', r'm_AtlasPadding: (\d+)'),
               ('_GradientScale', r'- _GradientScale: ([\d.]+)'),
               ('_ScaleRatioA', r'- _ScaleRatioA: ([\d.]+)'),
               ('_ScaleRatioC', r'- _ScaleRatioC: ([\d.]+)'),
               ('_TextureWidth', r'- _TextureWidth: ([\d.]+)')):
    m = re.search(pat, s)
    print('%-26s %s' % (k, m.group(1) if m else '?'))
print('%-26s %d' % ('字形数', len(re.findall(r'  - m_Index: ', gt))))
print('%-26s %d' % ('字符数', len(re.findall(r'  - m_ElementType:', s[s.index('  m_CharacterTable:'):s.index('  m_AtlasTextures:')]))))
print('%-26s %d 字节' % ('文件大小', os.path.getsize(ASSET)))
