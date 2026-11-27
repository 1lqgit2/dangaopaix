# -*- coding: utf-8 -*-
"""
按 TMP_SDF-Mobile.shader 的**真实**公式模拟屏幕上看到的文字。

shader 关键（vertex 里算好，fragment 用）：
    scale = |uv1.y| * _GradientScale * (_Sharpness + 1)
    weight = (_WeightNormal + _FaceDilate) * _ScaleRatioA * 0.5
    bias  = (0.5 - weight) * scale - 0.5
    d     = smoothstep(0, 1, 0.5 - (a - bias) / scale)
    c.a   = saturate(d)

uv1.y 由 TMP_Text 在生成 mesh 时写入：
    uv1.y = 1 / (pointSize / (padding * 2))
         = (padding * 2) / pointSize
  pointSize 是显示时的字号（像素 em），padding 是 m_AtlasPadding。
"""
import io
import os
import re

import numpy as np
from PIL import Image

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'
P = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
s = io.open(P, encoding='utf-8').read()

gs = float(re.search(r'    - _GradientScale: ([-\d.]+)', s).group(1))
sharp = float(re.search(r'    - _Sharpness: ([-\d.]+)', s).group(1))
ratio_a = float(re.search(r'    - _ScaleRatioA: ([-\d.]+)', s).group(1))
wn = float(re.search(r'    - _WeightNormal: ([-\d.]+)', s).group(1))
fd = float(re.search(r'    - _FaceDilate: ([-\d.]+)', s).group(1))
pad = int(re.search(r'  m_AtlasPadding: (\d+)', s).group(1))
ptsize = float(re.search(r'    m_PointSize: ([-\d.]+)', s).group(1))
print('_GradientScale=%.2f _Sharpness=%.2f _ScaleRatioA=%.3f' % (gs, sharp, ratio_a))
print('_WeightNormal=%.2f _FaceDilate=%.2f padding=%d PointSize=%.0f' % (wn, fd, pad, ptsize))

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
    pm = re.search(r'      m_HorizontalAdvance: ([-\d.]+)', b)
    d['adv'] = float(pm.group(1)) if pm else 0
    pm = re.search(r'      m_HorizontalBearingY: ([-\d.]+)', b)
    d['yoff'] = float(pm.group(1)) if pm else 0
    pm = re.search(r'      m_PointSize: ([-\d.]+)', b)
    d['pt'] = float(pm.group(1)) if pm else ptsize
    G[gid] = d


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def render(text, px_size, color=(255, 255, 255), bg=(46, 46, 46)):
    """px_size: 屏幕上 em 的像素高度。返回 RGB 图像。"""
    sc = px_size / float(ptsize)     # 显示 / 烘焙 比例
    # shader 的 uv1.y
    uv1y = (pad * 2.0) / px_size
    scale = uv1y * gs * (sharp + 1.0)
    weight = (wn + fd) * ratio_a * 0.5
    biass = (0.5 - weight) * scale - 0.5
    print('  [%s @%dpx] uv1.y=%.4f scale=%.4f bias=%.4f' % (text, px_size, uv1y, scale, biass))

    advs = [G[chars[ord(c)]]['adv'] * sc if ord(c) in chars and chars[ord(c)] in G
            else px_size * 0.5 for c in text]
    W = int(np.ceil(sum(advs))) + 12
    H = int(np.ceil(px_size * 1.5))
    base = int(H - px_size * 0.28)
    cov = np.zeros((H, W), np.float32)

    x = 4.0
    for c, adv in zip(text, advs):
        gid = chars.get(ord(c))
        if gid is not None and gid in G:
            g = G[gid]
            if g['Width'] >= 2 and g['Height'] >= 2:
                sub = atlas[atl_list[g['atlas']]][g['Y']:g['Y'] + g['Height'],
                                                  g['X']:g['X'] + g['Width']]
                a = sub.astype(np.float32) / 255.0
                d = smoothstep(0.0, 1.0, 0.5 - (a - biass) / scale)
                nw = max(1, int(round(g['Width'] * sc)))
                nh = max(1, int(round(g['Height'] * sc)))
                if (nw, nh) != (g['Width'], g['Height']):
                    d = np.array(Image.fromarray((d * 255).astype(np.uint8), 'L')
                                 .resize((nw, nh), Image.LANCZOS), np.float32) / 255.0
                pxx = int(round(x))
                pyy = int(round(base - g['yoff'] * sc))
                x0, y0 = max(0, pxx), max(0, pyy)
                x1, y1 = min(W, pxx + nw), min(H, pyy + nh)
                if x1 > x0 and y1 > y0:
                    patch = d[y0 - pyy:y1 - pyy, x0 - pxx:x1 - pxx]
                    cov[y0:y1, x0:x1] = np.maximum(cov[y0:y1, x0:x1], patch)
        x += adv

    rgb = np.zeros((H, W, 3), np.float32)
    rgb[:] = np.array(bg, np.float32) / 255.0
    col = np.array(color, np.float32) / 255.0
    rgb = rgb * (1 - cov[..., None]) + col * cov[..., None]
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8), 'RGB')


rows = []
for txt, px in (('看视频领取奖励', 84), ('返回首页', 84), ('开始', 84),
                ('看视频领取奖励', 52), ('返回首页', 40), ('设置', 30)):
    rows.append(render(txt, px))

W = max(r.size[0] for r in rows) + 16
H = sum(r.size[1] for r in rows) + 4 * (len(rows) + 1)
cv = Image.new('RGB', (W, H), (46, 46, 46))
y = 4
for r in rows:
    cv.paste(r, (8, y))
    y += r.size[1] + 4
out = os.path.join(PROJ, 'FontTools', 'shader_sim_preview.png')
cv.save(out)
print('\nshader 真实模拟:', out, cv.size)
