# -*- coding: utf-8 -*-
"""
在真实 shader 公式下扫描 GRADIENT_SCALE，评估不同显示字号下的清晰度。
评估指标：
  - 小字号的笔画是否糊成一块（覆盖率过低）
  - 是否出现"整块发白"（bias 过大）
  - 笔画边缘是否锐利（覆盖率标准差）
"""
import io
import os
import re

import numpy as np
from PIL import Image

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'
P = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
s = io.open(P, encoding='utf-8').read()

ratio_a = float(re.search(r'    - _ScaleRatioA: ([-\d.]+)', s).group(1))
pad = int(re.search(r'  m_AtlasPadding: (\d+)', s).group(1))
ptsize = float(re.search(r'    m_PointSize: ([-\d.]+)', s).group(1))

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


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def coverage_of(ch, px_size, gscale, pad_used=None):
    pd = pad_used if pad_used is not None else pad
    g = G[chars[ord(ch)]]
    sub = atlas[atl_list[g['atlas']]][g['Y']:g['Y'] + g['Height'],
                                      g['X']:g['X'] + g['Width']]
    a = sub.astype(np.float32) / 255.0
    uv1y = (pd * 2.0) / px_size
    scale = uv1y * gscale
    weight = 0.0 * ratio_a * 0.5
    biass = (0.5 - weight) * scale - 0.5
    d = smoothstep(0.0, 1.0, 0.5 - (a - biass) / scale)
    sc = px_size / ptsize
    nw = max(1, int(round(g['Width'] * sc)))
    nh = max(1, int(round(g['Height'] * sc)))
    if (nw, nh) != (g['Width'], g['Height']):
        d = np.array(Image.fromarray((d * 255).astype(np.uint8), 'L')
                     .resize((nw, nh), Image.LANCZOS), np.float32) / 255.0
    return d


print('评估（覆盖率=字墨占比，理想 0.30~0.45；全白=面积占比，应接近0）')
print('大小 / GRADIENT_SCALE:')
hdr = '%-8s' % 'px'
for gsc in (4, 6, 8, 10, 12, 16, 18):
    hdr += '%14s' % ('gs=%d' % gsc)
print(hdr)

for px in (30, 40, 52, 64, 84, 120):
    line = '%-8d' % px
    for gsc in (4, 6, 8, 10, 12, 16, 18):
        covs, whites = [], []
        for ch in '看视频领取奖励返回首页开始设置':
            d = coverage_of(ch, px, gsc)
            covs.append((d > 0.5).mean())
            whites.append((d > 0.98).mean())
        line += '%14s' % ('%.2f/%.2f' % (np.mean(covs), np.mean(whites)))
    print(line)
print('\n（格式：字墨覆盖率 / 全白占比）')
