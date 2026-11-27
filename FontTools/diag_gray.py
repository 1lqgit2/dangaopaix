# -*- coding: utf-8 -*-
"""
诊断 SDF 灰度分布：判断为什么渲染出来偏灰。
检查每字形的 alpha 直方图、笔画宽度、0.5 等值线是否落在笔画中心。
"""
import io
import os
import re

import numpy as np

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'
P = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
s = io.open(P, encoding='utf-8').read()

gs = float(re.search(r'    - _GradientScale: ([-\d.]+)', s).group(1))
atlas = {}
for m in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- !u!|\Z)', s, re.S):
    fid, sg = m.group(1), m.group(2)
    w = int(re.search(r'  m_Width: (\d+)', sg).group(1))
    h = int(re.search(r'  m_Height: (\d+)', sg).group(1))
    raw = re.search(r'  _typelessdata: ([0-9a-f]+)\n', sg).group(1)
    atlas[fid] = np.flipud(np.frombuffer(bytes.fromhex(raw), dtype=np.uint8).reshape(h, w))
atl_list = re.findall(r'fileID: (\d+)',
                      re.search(r'  m_AtlasTextures:\n((?:  - \{fileID: \d+\}\n)+)', s).group(1))

i_g = s.index('  m_GlyphTable:')
i_c = s.index('  m_CharacterTable:')
gt, ct = s[i_g:i_c], s[i_c:s.index('  m_AtlasTextures:')]
chars = {}
for m in re.finditer(r'  - m_ElementType: \d+\n    m_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', ct):
    chars[int(m.group(1))] = int(m.group(2))
G = {}
for m in re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S):
    gid, b = int(m.group(1)), m.group(2)
    d = {k: int(v) for k, v in re.findall(r'      m_(X|Y|Width|Height): (-?\d+)', b)}
    d['atlas'] = int(re.search(r'    m_AtlasIndex: (\d+)', b).group(1))
    G[gid] = d

print('=== 抽样字形 alpha 分布 ===')
print('%-4s %-4s %5s %5s %6s %6s %6s %6s %6s' %
      ('char', 'gid', 'W', 'H', '>=250', '>=200', '>=128', '<64', 'max'))
for ch in '看视频领取奖励返回首页开始设置ABC':
    u = ord(ch)
    if u not in chars:
        continue
    gid = chars[u]
    g = G[gid]
    sub = atlas[atl_list[g['atlas']]][g['Y']:g['Y'] + g['Height'], g['X']:g['X'] + g['Width']]
    n = sub.size
    print('%-4s %-4d %5d %5d %5.0f%% %5.0f%% %5.0f%% %5.0f%% %6d' %
          (ch, gid, g['Width'], g['Height'],
           (sub >= 250).sum() * 100.0 / n, (sub >= 200).sum() * 100.0 / n,
           (sub >= 128).sum() * 100.0 / n, (sub < 64).sum() * 100.0 / n, sub.max()))

# 笔画宽度统计：水平扫描，统计连续 >=128 的段长度
print('\n=== 笔画宽度分布（横向）===')
allrun = []
for ch in '看视频领取奖励返回首页开始设置':
    u = ord(ch)
    if u not in chars:
        continue
    g = G[chars[u]]
    sub = atlas[atl_list[g['atlas']]][g['Y']:g['Y'] + g['Height'], g['X']:g['X'] + g['Width']]
    m = sub >= 128
    for row in m:
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        starts = np.where(d == 1)[0]
        ends = np.where(d == -1)[0]
        allrun.extend((ends - starts).tolist())
allrun = np.array(allrun)
if len(allrun):
    print('  段数 %d  中位数 %d  均值 %.2f  最小 %d  最大 %d'
          % (len(allrun), int(np.median(allrun)), allrun.mean(), allrun.min(), allrun.max()))
    print('  分位: 10%%=%d 25%%=%d 50%%=%d 75%%=%d 90%%=%d'
          % (np.percentile(allrun, 10), np.percentile(allrun, 25),
             np.percentile(allrun, 50), np.percentile(allrun, 75), np.percentile(allrun, 90)))
    print('  spread=%.1f (半宽) -> 笔画半宽需 >= %.1f 才能达到 max alpha'
          % (gs / 2, gs / 2))
    print('  宽度 < %.1f 像素的笔画会"变灰": 占比 %.1f%%'
          % (2 * gs / 2, (allrun < gs).sum() * 100.0 / len(allrun)))

# 全局：整张图集里 alpha 的分布
print('\n=== 图集 0 全局 alpha 直方图（只看非零）===')
a0 = atlas[atl_list[0]]
nz = a0[a0 > 0]
if nz.size:
    for lo, hi in ((1, 63), (64, 127), (128, 191), (192, 249), (250, 255)):
        print('  [%3d-%3d] %6d 个 (%.1f%%)' % (lo, hi, ((nz >= lo) & (nz <= hi)).sum(),
                                             ((nz >= lo) & (nz <= hi)).sum() * 100.0 / nz.size))
