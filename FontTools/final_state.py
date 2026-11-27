# -*- coding: utf-8 -*-
"""最终状态检查。"""
import io
import re

P = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\Assets\AdSDK\Font\DroidSansFallback SDF.asset'
s = io.open(P, encoding='utf-8').read()


def g(p, d='?'):
    m = re.search(p, s)
    return m.group(1) if m else d


i_g = s.index('  m_GlyphTable:')
i_c = s.index('  m_CharacterTable:')
i_a = s.index('  m_AtlasTextures:')

rows = [
    ('m_AtlasPopulationMode', g(r'm_AtlasPopulationMode: (\d+)'), '0 = Static'),
    ('m_ClearDynamicDataOnBuild', g(r'm_ClearDynamicDataOnBuild: (\d+)'), '1'),
    ('m_AtlasTextureIndex', g(r'm_AtlasTextureIndex: (\d+)'), '0'),
    ('m_AtlasWidth', g(r'  m_AtlasWidth: (\d+)'), '2048'),
    ('m_AtlasHeight', g(r'  m_AtlasHeight: (\d+)'), '2048'),
    ('m_AtlasPadding', g(r'm_AtlasPadding: (\d+)'), '10'),
    ('_GradientScale', g(r'- _GradientScale: ([\d.]+)'), '10'),
    ('_ScaleRatioA', g(r'- _ScaleRatioA: ([\d.]+)'), '0.222222'),
    ('_ScaleRatioC', g(r'- _ScaleRatioC: ([\d.]+)'), '0.004859'),
    ('_TextureWidth', g(r'- _TextureWidth: ([\d.]+)'), '2048'),
    ('_TextureHeight', g(r'- _TextureHeight: ([\d.]+)'), '2048'),
]
print('%-28s %-12s %s' % ('字段', '当前值', '期望'))
for k, v, e in rows:
    flag = '' if v == e else '   <-- 不符'
    print('%-28s %-12s %s%s' % (k, v, e, flag))

m = re.search(r'  m_UsedGlyphRects:\n((?:  - m_X:[^\n]*\n(?:    [^\n]*\n)*)*)', s)
nu = len(re.findall(r'  - m_X:', m.group(1))) if m else 0
m2 = re.search(r'  m_FreeGlyphRects:\n((?:  - m_X:[^\n]*\n(?:    [^\n]*\n)*)*)', s)
nf = len(re.findall(r'  - m_X:', m2.group(1))) if m2 else 0
print('%-28s %-12d %s' % ('m_UsedGlyphRects', nu, '365'))

ng = len(re.findall(r'  - m_Index: \d+\n', s[i_g:i_c]))
nc = len(re.findall(r'  - m_ElementType:', s[i_c:i_a]))
print('%-28s %-12d' % ('字形数', ng))
print('%-28s %-12d' % ('字符数', nc))
print()
print('文件大小:', len(s.encode('utf-8')), '字节')
