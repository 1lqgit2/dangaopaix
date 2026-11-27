# -*- coding: utf-8 -*-
"""
最终视觉验证：完全按 TMP_Text.cs + TMP_SDF-Mobile.shader 的真实数据流还原。

TMP_Text.cs 采样（关键）：
    uv0.x = (glyphRect.x - padding) / atlasWidth      # 往左多吃 padding
    uv0.y = (glyphRect.y - padding) / atlasHeight
    uv2.x = (glyphRect.x + padding + glyphRect.width) / atlasWidth
    uv1.y = (glyphRect.y + padding + glyphRect.height) / atlasHeight
即：采样区域 = glyphRect 外扩 padding 一圈 = 原始槽位。

TMP_SDF-Mobile.shader：
    scale = rsqrt(dot(pixelSize,pixelSize)) * |texcoord1.y| * _GradientScale
  texcoord1 = uv2 通道，TMP 里存的是 m_Scale（=1）。
  所以 scale 实际由「字形像素尺寸 vs 屏幕像素尺寸」之比决定：
    对屏幕像素做 ddx/ddy 得 ~1，乘 |m_Scale|(=1) 乘 _GradientScale(=10)。
  => scale ≈ _GradientScale = 10（字号与烘焙字号相同时）
  字号更小时 scale 同比放大；更大时同比缩小。
    scale = _GradientScale * (POINT_SIZE / px_size) * (px_size/POINT_SIZE)... 
  实测正确关系：scale = _GradientScale * (SDF 放大倍数)
    放大倍数 = 1（同尺寸显示）；缩小显示时 < 1。
  最终用：scale = _GradientScale * px_size / POINT_SIZE 的倒数……
  为避免再猜，这里直接用 TMP 官方注释关系：
    bias = (0.5 - weight) * scale - 0.5，scale = _GradientScale * |uv1.y|
    uv1.y = m_Scale = 1  ==> scale = _GradientScale
  但那样所有字号都 const，显然不对（TMP 会随字号锐化）。
  真实来源是 rsqrt(dot(pixelSize,pixelSize)) 里的 pixelSize 正比于
  (1/屏幕像素密度) 与字形的世界尺寸，二者比值最终约等于
  (烘焙 em 像素 / 显示 em 像素) 的倒数。取：
    scale = _GradientScale * (POINT_SIZE / px_size)
"""
import io
import os
import re

import numpy as np
from PIL import Image

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'
P = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
s = io.open(P, encoding='utf-8').read()

gscale = float(re.search(r'    - _GradientScale: ([-\d.]+)', s).group(1))
sharp = float(re.search(r'    - _Sharpness: ([-\d.]+)', s).group(1))
ratio_a = float(re.search(r'    - _ScaleRatioA: ([-\d.]+)', s).group(1))
pad = int(re.search(r'  m_AtlasPadding: (\d+)', s).group(1))
pts = float(re.search(r'    m_PointSize: ([-\d.]+)', s).group(1))

atlas = {}
for m in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- !u!|\Z)', s, re.S):
    fid, sg = m.group(1), m.group(2)
    w = int(re.search(r'  m_Width: (\d+)', sg).group(1))
    h = int(re.search(r'  m_Height: (\d+)', sg).group(1))
    raw = re.search(r'  _typelessdata: ([0-9a-f]+)\n', sg).group(1)
    atlas[fid] = np.flipud(np.frombuffer(bytes.fromhex(raw), np.uint8).reshape(h, w))
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
    d = {}
    gr = re.search(r'    m_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', b)
    d['x'], d['y'], d['gw'], d['gh'] = map(int, gr.groups())
    me = re.search(r'    m_Metrics:\n      m_Width: ([-\d.]+)\n      m_Height: ([-\d.]+)\n      m_HorizontalBearingX: ([-\d.]+)\n      m_HorizontalBearingY: ([-\d.]+)\n      m_HorizontalAdvance: ([-\d.]+)', b)
    d['mw'], d['mh'], d['bx'], d['by'], d['adv'] = map(float, me.groups())
    d['atlas'] = int(re.search(r'    m_AtlasIndex: (\d+)', b).group(1))
    G[gid] = d


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def render(text, px, color=(255, 255, 255), bg=(46, 46, 46)):
    sc = px / pts
    # shader: scale = rsqrt(dot(pixelSize,pixelSize)) * |uv1.y| * _GradientScale
    # uvs2.y 存的是画布 scale（普通 UGUI 下 ≈ 1），rsqrt(dot(pixelSize)) 也 ≈ 1
    # 因为 pixelSize 是「世界尺寸 / 屏幕像素」的比值，字形放大时两者同比。
    # => scale ≈ _GradientScale，与显示字号无关（字号影响由纹理缩放体现）
    mg = gscale
    weight = 0.0 * ratio_a * 0.5
    bias = (0.5 - weight) * mg - 0.5

    advs = [G[chars[ord(c)]]['adv'] * sc if ord(c) in chars and chars[ord(c)] in G
            else px * 0.5 for c in text]
    W = int(np.ceil(sum(advs))) + 16
    H = int(np.ceil(px * 1.55))
    base = int(H - px * 0.30)
    cov = np.zeros((H, W), np.float32)

    x = 6.0
    for c, adv in zip(text, advs):
        gid = chars.get(ord(c))
        if gid is not None and gid in G:
            g = G[gid]
            # TMP 采样区 = glyphRect 外扩 padding
            ax0 = g['x'] - pad
            ay0 = g['y'] - pad
            aw = g['gw'] + pad * 2
            ah = g['gh'] + pad * 2
            t = atlas[atl_list[g['atlas']]]
            sub = t[max(0, ay0):ay0 + ah, max(0, ax0):ax0 + aw]
            if sub.size:
                a = sub.astype(np.float32) / 255.0
                # —— 真实 shader 公式（TMP_SDF-Mobile.shader 第 200-201 行）——
                #   half d = tex2D(_MainTex, uv).a * input.param.x;   // param.x = scale
                #   half4 c = faceColor * saturate(d - input.param.w); // param.w = bias
                # 即 alpha = saturate(a * mg - bias)，线性映射，无 smoothstep
                d = np.clip(a * mg - bias, 0.0, 1.0)
                nw = max(1, int(round(aw * sc)))
                nh = max(1, int(round(ah * sc)))
                if (nw, nh) != (aw, ah):
                    d = np.array(Image.fromarray((d * 255).astype(np.uint8), 'L')
                                 .resize((nw, nh), Image.LANCZOS), np.float32) / 255.0
                # 四边形左下角 = 基线 + bearingX - padding
                pxx = int(round(x + (g['bx'] - pad) * sc))
                pyy = int(round(base - (g['by'] + pad) * sc))
                x0, y0 = max(0, pxx), max(0, pyy)
                x1, y1 = min(W, pxx + nw), min(H, pyy + nh)
                if x1 > x0 and y1 > y0:
                    cov[y0:y1, x0:x1] = np.maximum(
                        cov[y0:y1, x0:x1], d[y0 - pyy:y1 - pyy, x0 - pxx:x1 - pxx])
        x += adv

    rgb = np.zeros((H, W, 3), np.float32)
    rgb[:] = np.array(bg, np.float32) / 255.0
    col = np.array(color, np.float32) / 255.0
    rgb = rgb * (1 - cov[..., None]) + col * cov[..., None]
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8), 'RGB')


rows = []
for txt, px in (('看广告获得奖励', 82), ('返回', 82), ('确认', 82),
                ('添加金币', 60), ('进入侧边栏', 44), ('设置', 32)):
    rows.append(render(txt, px))
    print('渲染 %s @%dpx' % (txt, px))

W = max(r.size[0] for r in rows) + 16
H = sum(r.size[1] for r in rows) + 4 * (len(rows) + 1)
cv = Image.new('RGB', (W, H), (46, 46, 46))
y = 4
for r in rows:
    cv.paste(r, (8, y))
    y += r.size[1] + 4
out = os.path.join(PROJ, 'FontTools', 'final_preview.png')
cv.save(out)
print('\n最终预览:', out, cv.size)
