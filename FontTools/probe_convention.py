# -*- coding: utf-8 -*-
"""
判定 TMP 的 m_GlyphRect.m_Y 到底是「自下而上」还是「自上而下」。

做法：拿 Unity 自己烘焙的 LiberationSans SDF 当基准（它一定是对的），
对同一个字形用两种约定各裁一次，看哪一张是真正的字母。
"""
import io
import os
import re
import sys

import numpy as np
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, 'FontTools', 'conv')


def load(path):
    s = io.open(path, encoding='utf-8').read()

    def one(pat, d=None):
        m = re.search(pat, s, re.S)
        return m.group(1) if m else d

    W = int(one(r'  m_Width: (\d+)\n  m_Height: \d+\n  m_CompleteImageSize'))
    H = int(one(r'  m_Width: \d+\n  m_Height: (\d+)\n  m_CompleteImageSize'))
    hexdata = one(r'  _typelessdata: ([0-9a-f]+)')
    pad = int(one(r'  m_AtlasPadding: (\d+)', '0'))
    raw = bytes.fromhex(hexdata)
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(H, W)   # row0 = 底部
    img_bottomup = arr                                        # 直接是 v 从小到大
    img_topdown = np.flipud(arr)                              # 翻成图像习惯

    i_g = s.index('  m_GlyphTable:')
    i_c = s.index('  m_CharacterTable:')
    gt, ct = s[i_g:i_c], s[i_c:s.index('  m_AtlasTextures:')]

    u2g = {}
    for m in re.finditer(r'  - m_ElementType: \d+\n    m_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', ct):
        u2g[int(m.group(1))] = int(m.group(2))

    G = {}
    for m in re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S):
        gid = int(m.group(1))
        b = m.group(2)
        r = re.search(r'    m_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', b)
        if r:
            G[gid] = tuple(int(v) for v in r.groups())
    return W, H, pad, img_bottomup, img_topdown, u2g, G


def crop_save(img, x, y, w, h, path, zoom=6):
    if w <= 0 or h <= 0:
        return False, None
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(img.shape[1], x + w), min(img.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return False, None
    sub = img[y0:y1, x0:x1]
    Image.fromarray(sub).resize(((x1 - x0) * zoom, (y1 - y0) * zoom), Image.NEAREST).save(path)
    return True, sub


def main(asset, chars):
    os.makedirs(OUT, exist_ok=True)
    W, H, pad, bu, td, u2g, G = load(asset)
    print('资产 %s  %dx%d  padding=%d' % (os.path.basename(asset), W, H, pad))
    print('%-4s %-6s %-22s %s' % ('字', 'gid', 'glyphRect(x,y,w,h)', '判定'))
    for ch in chars:
        u = ord(ch)
        if u not in u2g:
            print('%-4s 不在字符表' % ch)
            continue
        gid = u2g[u]
        if gid not in G:
            print('%-4s gid=%d 无 glyphRect' % (ch, gid))
            continue
        x, y, w, h = G[gid]
        # 约定1：y 自下而上 -> 图像里的顶边 = H - y - h
        ok1, s1 = crop_save(bu, x, H - y - h, w, h, os.path.join(OUT, '%s_bottomup.png' % ch))
        # 约定2：y 自上而下 -> 图像里直接就是 y
        ok2, s2 = crop_save(td, x, y, w, h, os.path.join(OUT, '%s_topdown.png' % ch))
        d1 = s1.mean() if s1 is not None else -1
        d2 = s2.mean() if s2 is not None else -1
        print('%-4s %-6d %-22s 自下而上mean=%.1f  自上而下mean=%.1f' % (ch, gid, (x, y, w, h), d1, d2))
    print('\n看图判断：%s 目录下 <字>_bottomup.png / <字>_topdown.png' % OUT)


if __name__ == '__main__':
    a = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        PROJ, 'Assets/TextMesh Pro/Resources/Fonts & Materials/LiberationSans SDF.asset')
    cs = sys.argv[2] if len(sys.argv) > 2 else 'AgB'
    main(a, cs)
