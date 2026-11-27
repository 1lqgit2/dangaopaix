# -*- coding: utf-8 -*-
"""
按 TMP 的真实 shader 公式渲染，模拟屏幕上看到的文字效果。

TMP Mobile/Distance Field 核心（alpha 通道）：
    d   = (a/255 - 0.5) * _GradientScale          # 还原到字形空间的距离
    aa  = fwidth(d) * 0.25 * _ScaleRatioA         # 抗锯齿宽度
    c   = 0.5 + (d - 0.5*(_GradientScale - _GradientBias)) / aa  ...
实际 TMP 里简化后最关键的两步：
    c = clamp( (a/255 - 0.5) * _GradientScale / spread + 0.5 - _Sharpness, 0, 1 )
再乘 text color，走 sRGB 输出。
"""
import io
import os
import re

import numpy as np
from PIL import Image

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'
P = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')

s = io.open(P, encoding='utf-8').read()

# ---------- 材质参数
gs = float(re.search(r'    - _GradientScale: ([-\d.]+)', s).group(1))
sharp = float(re.search(r'    - _Sharpness: ([-\d.]+)', s).group(1))
ratio_a = float(re.search(r'    - _ScaleRatioA: ([-\d.]+)', s).group(1))
ratio_c = float(re.search(r'    - _ScaleRatioC: ([-\d.]+)', s).group(1))
tw = float(re.search(r'    - _TextureWidth: ([-\d.]+)', s).group(1))
th = float(re.search(r'    - _TextureHeight: ([-\d.]+)', s).group(1))
print('_GradientScale=%.4f  _Sharpness=%.4f' % (gs, sharp))
print('_ScaleRatioA=%.6f  _ScaleRatioC=%.6f' % (ratio_a, ratio_c))
print('_TextureWidth=%.0f  _TextureHeight=%.0f' % (tw, th))

fw = float(re.search(r'  m_AtlasWidth: (\d+)', s).group(1))
fh = float(re.search(r'  m_AtlasHeight: (\d+)', s).group(1))
pad = int(re.search(r'  m_AtlasPadding: (\d+)', s).group(1))
print('m_AtlasWidth=%.0f  m_AtlasHeight=%.0f  m_AtlasPadding=%d' % (fw, fh, pad))
print('  -> 材质尺寸与图集%s' % ('一致 OK' if (tw == fw and th == fh) else '不一致 !!'))

# spread 必须 = _GradientScale/2
SPREAD = gs / 2.0
print('烘焙 spread 应为 %.2f，留白 %d %s' % (SPREAD, pad,
      'OK(留白>=半宽)' if pad >= SPREAD else '不足 !!'))

# ---------- 读图集
atlas = {}
for m in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- !u!|\Z)', s, re.S):
    fid, sg = m.group(1), m.group(2)
    w = int(re.search(r'  m_Width: (\d+)', sg).group(1))
    h = int(re.search(r'  m_Height: (\d+)', sg).group(1))
    raw = re.search(r'  _typelessdata: ([0-9a-f]+)\n', sg).group(1)
    atlas[fid] = np.flipud(np.frombuffer(bytes.fromhex(raw), dtype=np.uint8).reshape(h, w))

lm = re.search(r'  m_AtlasTextures:\n((?:  - \{fileID: \d+\}\n)+)', s)
atl_list = re.findall(r'fileID: (\d+)', lm.group(1))

# ---------- 字形
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
    d['adv'] = float(re.search(r'      m_HorizontalAdvance: ([-\d.]+)', b).group(1))
    d['yoff'] = float(re.search(r'      m_HorizontalBearingY: ([-\d.]+)', b).group(1))
    G[gid] = d


def sdf_to_alpha(sub):
    """TMP 的 SDF -> 屏幕覆盖率，值域 0..1"""
    a = sub.astype(np.float32) / 255.0
    # 还原有符号距离
    d = (a - 0.5) * gs
    # 归一化到 [-0.5, 0.5] 后加 sharpness
    c = (d / gs) * (gs / SPREAD) * 0.5 + 0.5 - sharp
    # 抗锯齿：真实 TMP 在屏幕上按像素导数做 smoothstep，这里按 1px 的带宽近似
    return np.clip(c, 0.0, 1.0)


def render_line(text, em_px, color=(255, 255, 255), bg=(46, 46, 46)):
    """按真实字体度量排版，而不是简单拼接"""
    sc = em_px / 90.0 * (90.0 / 90.0)   # 字形是 90pt 烘焙的
    # 先算总宽（advance 单位与烘焙一致，本身已是像素@90pt）
    advs = []
    for ch in text:
        gid = chars.get(ord(ch))
        if gid is None or gid not in G:
            advs.append(em_px * 0.5)
        else:
            advs.append(G[gid]['adv'] * sc)
    W = int(np.ceil(sum(advs))) + 8
    H = int(np.ceil(em_px * 1.4)) + 8
    base_y = H - int(np.ceil(em_px * 0.25))     # 基线位置

    cov = np.zeros((H, W), dtype=np.float32)
    x = 4.0
    for ch, adv in zip(text, advs):
        gid = chars.get(ord(ch))
        if gid is not None and gid in G:
            g = G[gid]
            if g['Width'] >= 2 and g['Height'] >= 2:
                sub = atlas[atl_list[g['atlas']]][g['Y']:g['Y'] + g['Height'],
                                                  g['X']:g['X'] + g['Width']]
                a = sdf_to_alpha(sub)
                # 缩放到显示尺寸
                nw = max(1, int(round(g['Width'] * sc)))
                nh = max(1, int(round(g['Height'] * sc)))
                if (nw, nh) != (g['Width'], g['Height']):
                    a = np.array(Image.fromarray((a * 255).astype(np.uint8), 'L')
                                 .resize((nw, nh), Image.LANCZOS), dtype=np.float32) / 255.0
                # 用 bearingY 定位：字形顶边在基线之上 yoff
                px = int(round(x))
                py = int(round(base_y - g['yoff'] * sc))
                x0, y0 = max(0, px), max(0, py)
                x1 = min(W, px + nw)
                y1 = min(H, py + nh)
                if x1 > x0 and y1 > y0:
                    patch = a[y0 - py:y1 - py, x0 - px:x1 - px]
                    cov[y0:y1, x0:x1] = np.maximum(cov[y0:y1, x0:x1], patch)
        x += adv

    out = np.zeros((H, W, 3), dtype=np.float32)
    out[:] = np.array(bg, dtype=np.float32) / 255.0
    col = np.array(color, dtype=np.float32) / 255.0
    out = out * (1 - cov[..., None]) + col * cov[..., None]
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), 'RGB')


rows = []
for txt, em in (('看视频领取奖励', 90), ('返回首页', 90), ('开始', 90),
                ('看视频领取奖励', 60), ('返回首页', 48), ('设置', 36)):
    rows.append(render_line(txt, em))

W = max(r.size[0] for r in rows) + 16
H = sum(r.size[1] for r in rows) + 6 * (len(rows) + 1)
canvas = Image.new('RGB', (W, H), (46, 46, 46))
y = 6
for r in rows:
    canvas.paste(r, (8, y))
    y += r.size[1] + 6
out = os.path.join(PROJ, 'FontTools', 'tmp_render_preview.png')
canvas.save(out)
print('\nTMP 模拟渲染: ', out, canvas.size)
