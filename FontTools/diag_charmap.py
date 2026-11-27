# -*- coding: utf-8 -*-
"""导出指定字形的图集块，并列出字符表里 该 gid 附近 的映射，用于判断是否错位。"""
import io
import os
import re
import sys

import numpy as np
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
OUT = os.path.join(PROJ, 'FontTools', 'conv')
os.makedirs(OUT, exist_ok=True)

CHARS = sys.argv[1] if len(sys.argv) > 1 else '看广得'

s = io.open(ASSET, encoding='utf-8').read()
fids = re.findall(r'fileID: (-?\d+)',
                  re.findall(r'  m_AtlasTextures:\n((?:  - \{fileID: -?\d+\}\n)+)', s)[0])

arrs = {}
for d in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- |\Z)', s, re.S):
    fid, body = d.group(1), d.group(2)
    hx = re.search(r'_typelessdata: ([0-9a-f]+)', body)
    if not hx:
        continue
    W = int(re.search(r'  m_Width: (\d+)', body).group(1))
    H = int(re.search(r'  m_Height: (\d+)', body).group(1))
    arrs[fid] = np.flipud(np.frombuffer(bytes.fromhex(hx.group(1)), dtype=np.uint8).reshape(H, W))

i_c = s.index('  m_CharacterTable:')
i_a = s.index('  m_AtlasTextures:')
ct = s[i_c:i_a]
u2g = {}
g2u = {}
for m in re.finditer(r'm_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', ct):
    u, g = int(m.group(1)), int(m.group(2))
    u2g[u] = g
    g2u.setdefault(g, u)

gt = s[s.index('  m_GlyphTable:'):i_c]
G = {}
for m in re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S):
    gid = int(m.group(1))
    b = m.group(2)
    gr = re.search(r'    m_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', b)
    ai = re.search(r'    m_AtlasIndex: (\d+)', b)
    if gr:
        G[gid] = (int(gr.group(1)), int(gr.group(2)), int(gr.group(3)), int(gr.group(4)),
                  int(ai.group(1)) if ai else 0)

print('字符 %d  字形 %d' % (len(u2g), len(G)))
for ch in CHARS:
    u = ord(ch)
    if u not in u2g:
        print('%s 不在字符表' % ch)
        continue
    gid = u2g[u]
    if gid not in G:
        print('%s gid=%d 无 rect' % (ch, gid))
        continue
    x, y, w, h, ai = G[gid]
    img = arrs[fids[ai]]
    print('%s U+%04X gid=%-5d atlas=%d rect=(%d,%d,%d,%d)' % (ch, u, gid, ai, x, y, w, h))
    Image.fromarray(img[y:y + h, x:x + w]).resize((w * 4, h * 4), Image.NEAREST).save(
        os.path.join(OUT, 'X_%s_u%04X_gid%d.png' % (ch, u, gid)))
print('已保存到', OUT)
