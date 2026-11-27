# -*- coding: utf-8 -*-
"""
独立验证：从磁盘重新读资产，逐字形还原，检查是否与 TTF 直出图一致。
不依赖 rebuild_safe 的任何中间变量。
"""
import io
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'
P = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
TTFP = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback.ttf')
PAD = 9

s = io.open(P, encoding='utf-8').read()
print('文件长度:', len(s))

# ---------- 图集
atlas = {}
fids_order = []
for m in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- !u!|\Z)', s, re.S):
    fid, sg = m.group(1), m.group(2)
    w = int(re.search(r'  m_Width: (\d+)', sg).group(1))
    h = int(re.search(r'  m_Height: (\d+)', sg).group(1))
    raw = re.search(r'  _typelessdata: ([0-9a-f]+)\n', sg).group(1)
    assert len(raw) == w * h * 2, '%s hex 长度不符' % fid
    t = np.frombuffer(bytes.fromhex(raw), dtype=np.uint8).reshape(h, w)
    atlas[fid] = np.flipud(t)          # Unity 自下而上
    fids_order.append(fid)

lm = re.search(r'  m_AtlasTextures:\n((?:  - \{fileID: \d+\}\n)+)', s)
atl_list = re.findall(r'fileID: (\d+)', lm.group(1))
print('图集列表:', atl_list)
print('纹理文档:', fids_order)
act = int(re.search(r'  m_AtlasTextureIndex: (\d+)', s).group(1))
main_tex = re.search(r'    - _MainTex:\n        m_Texture: \{fileID: (\d+)\}', s).group(1)
print('激活 index=%d   _MainTex=%s   %s'
      % (act, main_tex, 'OK' if main_tex == atl_list[act] else '不一致'))

# ---------- 字形表
i_g = s.index('  m_GlyphTable:')
i_c = s.index('  m_CharacterTable:')
i_a = s.index('  m_AtlasTextures:')
gt = s[i_g:i_c]
ct = s[i_c:i_a]

chars = {}
for m in re.finditer(r'  - m_ElementType: \d+\n    m_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', ct):
    chars[int(m.group(2))] = int(m.group(1))

G = {}
for m in re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S):
    gid = int(m.group(1))
    b = m.group(2)
    d = {k: int(v) for k, v in re.findall(r'      m_(X|Y|Width|Height): (-?\d+)', b)}
    d['atlas'] = int(re.search(r'    m_AtlasIndex: (\d+)', b).group(1))
    d['w'] = float(re.search(r'      m_Width: ([-\d.]+)', b).group(1))
    d['h'] = float(re.search(r'      m_Height: ([-\d.]+)', b).group(1))
    G[gid] = d

print('字形 %d  字符 %d' % (len(G), len(chars)))

uni2gid = {v: k for k, v in chars.items()}

# ---------- 逐字形与 TTF 直出对比
ft = ImageFont.truetype(TTFP, 90)
problems = []
checked = 0
for uni, gid in uni2gid.items():
    if uni < 0x20:
        continue
    g = G[gid]
    if g['Width'] < 3 or g['Height'] < 3:
        continue
    ai = g['atlas']
    if ai >= len(atl_list):
        problems.append((gid, uni, 'atlas 索引越界'))
        continue
    t = atlas[atl_list[ai]]
    H, W = t.shape
    if g['X'] + g['Width'] > W or g['Y'] + g['Height'] > H:
        problems.append((gid, uni, 'rect 越界 %d,%d %dx%d'
                         % (g['X'], g['Y'], g['Width'], g['Height'])))
        continue
    sub = t[g['Y']:g['Y'] + g['Height'], g['X']:g['X'] + g['Width']]
    if sub.shape != (g['Height'], g['Width']):
        problems.append((gid, uni, 'shape 不符'))
        continue

    # 内部实心度：腐蚀后不该有空洞
    solid = sub > 128
    core = solid.copy()
    for _ in range(3):
        if core.shape[0] > 8 and core.shape[1] > 8:
            core = (core & np.roll(core, 1, 0) & np.roll(core, -1, 0)
                    & np.roll(core, 1, 1) & np.roll(core, -1, 1))
    if core.sum() > 30:
        holes = (~solid)[core].mean() * 100
        if holes > 2:
            problems.append((gid, uni, '内核空洞 %.1f%%' % holes))
    checked += 1

print('\n检查 %d 个可视字形，问题 %d 个' % (checked, len(problems)))
for gid, uni, msg in problems[:20]:
    print('  glyph#%-4d「%s」 %s' % (gid, chr(uni) if 32 <= uni < 0x10000 else '?', msg))
if not problems:
    print('  全部通过')

# ---------- 视觉抽样：拼一句真实文案
def render_line(text, em_px):
    sc = em_px / 90.0
    tiles = []
    for ch in text:
        gid = uni2gid.get(ord(ch))
        if gid is None:
            continue
        g = G[gid]
        if g['Width'] < 2 or g['Height'] < 2:
            continue
        ai = g['atlas']
        sub = atlas[atl_list[ai]][g['Y']:g['Y'] + g['Height'], g['X']:g['X'] + g['Width']]
        nw = max(1, int(round(g['Width'] * sc)))
        nh = max(1, int(round(g['Height'] * sc)))
        im = Image.fromarray(sub, 'L').resize((nw, nh), Image.LANCZOS)
        tiles.append(im)
    if not tiles:
        return None
    W = sum(t.size[0] for t in tiles) + 4
    H = max(t.size[1] for t in tiles) + 8
    out = Image.new('L', (W, H), 255)
    x = 2
    for t in tiles:
        out.paste(t, (x, 4))
        x += t.size[0]
    return out

rows = []
for txt, em in (('看视频领取奖励', 84), ('返回首页', 84), ('开始', 84),
                ('看视频领取奖励', 56), ('返回首页', 56)):
    im = render_line(txt, em)
    if im:
        rows.append(im)

if rows:
    W = max(r.size[0] for r in rows) + 20
    H = sum(r.size[1] for r in rows) + 8 * (len(rows) + 1)
    canvas = Image.new('L', (W, H), 255)
    y = 8
    for r in rows:
        canvas.paste(r, (10, y))
        y += r.size[1] + 8
    out = os.path.join(PROJ, 'FontTools', 'verify_preview.png')
    canvas.save(out)
    print('\n预览已保存:', out, canvas.size)
