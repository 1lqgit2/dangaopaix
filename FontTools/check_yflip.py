# -*- coding: utf-8 -*-
"""检查现有字体资产：glyphRect 的 m_Y 究竟是按「自下而上」还是「自上而下」写的。"""
import io
import os
import re

import numpy as np
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
OUT = os.path.join(PROJ, 'FontTools', 'conv')
os.makedirs(OUT, exist_ok=True)

s = io.open(ASSET, encoding='utf-8').read()

# 纹理文档
tex = {}
for d in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- |\Z)', s, re.S):
    fid, body = d.group(1), d.group(2)
    hx = re.search(r'_typelessdata: ([0-9a-f]+)', body)
    if not hx:
        continue
    w = int(re.search(r'  m_Width: (\d+)', body).group(1))
    h = int(re.search(r'  m_Height: (\d+)', body).group(1))
    tex[fid] = (w, h, hx.group(1))
    print('纹理 &%s %dx%d' % (fid, w, h))

atl_list = re.findall(r'  m_AtlasTextures:\n((?:  - \{fileID: -?\d+\}\n)+)', s)
fids = re.findall(r'fileID: (-?\d+)', atl_list[0])
print('m_AtlasTextures =', fids)

# 字符 -> glyph
i_c = s.index('  m_CharacterTable:')
i_a = s.index('  m_AtlasTextures:')
u2g = {}
for m in re.finditer(r'm_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', s[i_c:i_a]):
    u2g[int(m.group(1))] = int(m.group(2))

gt = s[s.index('  m_GlyphTable:'):i_c]
G = {}
for m in re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S):
    b = m.group(2)
    x = re.search(r'      m_X: (-?\d+)', b)
    y = re.search(r'      m_Y: (-?\d+)', b)
    w = re.search(r'      m_Width: (-?\d+)', b)
    h = re.search(r'      m_Height: (-?\d+)', b)
    ai = re.search(r'    m_AtlasIndex: (\d+)', b)
    if not (x and y and w and h):
        continue
    G[int(m.group(1))] = (int(x.group(1)), int(y.group(1)),
                          int(w.group(1)), int(h.group(1)),
                          int(ai.group(1)) if ai else 0)

for ch in '漫A看':
    u = ord(ch)
    if u not in u2g:
        print('%-3s 不在字符表' % ch)
        continue
    gid = u2g[u]
    if gid not in G:
        print('%-3s gid=%d 无可用 glyphRect' % (ch, gid))
        continue
    x, y, w, h, ai = G[gid]
    print('%-3s gid=%-5d atlas=%d rect=(%d,%d,%d,%d)  右下角 y+h=%d' % (ch, gid, ai, x, y, w, h, y + h))
    fid = fids[ai]
    W, H, hx = tex[fid]
    raw = np.frombuffer(bytes.fromhex(hx), dtype=np.uint8).reshape(H, W)
    td = np.flipud(raw)
    if w <= 0 or h <= 0:
        print('   尺寸为 0，跳过')
        continue
    a = Image.fromarray(td[max(0, H - y - h):H - y, x:x + w])
    a.resize((a.width * 4, a.height * 4), Image.NEAREST).save(
        os.path.join(OUT, '%s_store_yfrombottom.png' % ch))
    b2 = Image.fromarray(td[y:y + h, x:x + w])
    b2.resize((b2.width * 4, b2.height * 4), Image.NEAREST).save(
        os.path.join(OUT, '%s_store_yfromtop.png' % ch))
print('\n已保存到', OUT)
