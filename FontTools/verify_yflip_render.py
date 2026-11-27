# -*- coding: utf-8 -*-
"""
按 TMP 真实采样约定渲染：v 自下而上，采样区 = [y-pad, y+h+pad)。
输出预览图，肉眼确认字形是否正确。
"""
import io
import os
import re
import sys

import numpy as np
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
TEXT = sys.argv[2] if len(sys.argv) > 2 else '看广告获得奖励  返回首页  开始'
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(PROJ, 'FontTools', 'yflip_preview.png')

s = io.open(ASSET, encoding='utf-8').read()

# 纹理
tex = {}
for d in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- |\Z)', s, re.S):
    fid, body = d.group(1), d.group(2)
    hx = re.search(r'_typelessdata: ([0-9a-f]+)', body)
    if not hx:
        continue
    W = int(re.search(r'  m_Width: (\d+)', body).group(1))
    H = int(re.search(r'  m_Height: (\d+)', body).group(1))
    raw = np.frombuffer(bytes.fromhex(hx.group(1)), dtype=np.uint8).reshape(H, W)
    tex[fid] = {0: np.flipud(raw), 1: np.flipud(raw)}   # 索引由下面 atlas 顺序定
atl = re.findall(r'  m_AtlasTextures:\n((?:  - \{fileID: -?\d+\}\n)+)', s)
fids = re.findall(r'fileID: (-?\d+)', atl[0])
ATL = {}
for i, f in enumerate(fids):
    for H, W, arr in [(0, 0, None)]:
        pass
# 重新按 fid 读一遍，映射到 index
for d in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- |\Z)', s, re.S):
    fid, body = d.group(1), d.group(2)
    hx = re.search(r'_typelessdata: ([0-9a-f]+)', body)
    if not hx:
        continue
    W = int(re.search(r'  m_Width: (\d+)', body).group(1))
    H = int(re.search(r'  m_Height: (\d+)', body).group(1))
    raw = np.frombuffer(bytes.fromhex(hx.group(1)), dtype=np.uint8).reshape(H, W)
    td = np.flipud(raw)
    if fid in fids:
        ATL[fids.index(fid)] = (td, H, W)

PAD = int(re.search(r'  m_AtlasPadding: (\d+)', s).group(1))
GS = float(re.search(r'- _GradientScale: ([\d.]+)', s).group(1))
BIAS = (0.5 - 0.0) * GS - 0.5

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
    adv = re.search(r'      m_HorizontalAdvance: ([\d.\-]+)', b)
    bx = re.search(r'      m_HorizontalBearingX: ([\d.\-]+)', b)
    by = re.search(r'      m_HorizontalBearingY: ([\d.\-]+)', b)
    if not (x and y and w and h):
        continue
    G[int(m.group(1))] = dict(
        x=int(x.group(1)), y=int(y.group(1)), w=int(w.group(1)), h=int(h.group(1)),
        ai=int(ai.group(1)) if ai else 0,
        adv=float(adv.group(1)) if adv else 0,
        bx=float(bx.group(1)) if bx else 0,
        by=float(by.group(1)) if by else 0)

print('padding=%d  _GradientScale=%s  bias=%.2f' % (PAD, GS, BIAS))
print('图集: %s' % {k: (v[1], v[2]) for k, v in ATL.items()})


def render(text, px, y0, col, img):
    """px = 目标字号像素高度；按 g['by'] 处理基线"""
    g0 = next((G[u2g[ord(c)]] for c in text if ord(c) in u2g and u2g[ord(c)] in G), None)
    if g0 is None:
        return 0
    # 90pt 烘焙 -> 缩放到 px
    k = px / 90.0
    adv = 0.0
    for c in text:
        u = ord(c)
        if u not in u2g or u2g[u] not in G:
            adv += px * 0.5
            continue
        g = G[u2g[u]]
        src, H, W = ATL.get(g['ai'], (None, 0, 0))
        if src is None or g['w'] <= 0 or g['h'] <= 0:
            adv += g['adv'] * k
            continue
        # m_Y 是「距底边」的高度，转成图像（自上而下）行号要 H - y - h
        td_y = H - g['y'] - g['h']
        yA = td_y - PAD
        yB = td_y + g['h'] + PAD
        xA = g['x'] - PAD
        xB = g['x'] + g['w'] + PAD
        yA, yB = max(0, yA), min(H, yB)
        xA, xB = max(0, xA), min(W, xB)
        patch = src[yA:yB, xA:xB].astype(np.float32) / 255.0
        a = np.clip(patch * GS - BIAS, 0, 1)
        ph, pw = a.shape
        tgt_w = max(1, int(round((xB - xA) * k)))
        tgt_h = max(1, int(round((yB - yA) * k)))
        a_img = Image.fromarray((a * 255).astype(np.uint8)).resize((tgt_w, tgt_h), Image.LANCZOS)
        aa = np.array(a_img).astype(np.float32) / 255.0
        # 位置：字形原点 = 笔位置 + bearingX*k，基线在 y0；顶端 = 基线 - bearingY*k
        left = int(round(col + adv + g['bx'] * k - PAD * k))
        top = int(round(y0 - g['by'] * k - PAD * k))
        hh, ww = aa.shape
        for yy in range(hh):
            ty = top + yy
            if ty < 0 or ty >= img.shape[0]:
                continue
            for xx in range(ww):
                tx = left + xx
                if tx < 0 or tx >= img.shape[1]:
                    continue
                al = aa[yy, xx]
                if al > 0.01:
                    img[ty, tx] = img[ty, tx] * (1 - al) + 255.0 * al
        adv += g['adv'] * k
    return adv


W_img, H_img = 900, 460
img = np.zeros((H_img, W_img), dtype=np.float32)
rows = [(TEXT, 82, 95), (TEXT, 56, 200), ('返回首页 设置 开始', 40, 285), ('获取奖励  3/5  Lv.2', 30, 360)]
for t, px, base in rows:
    render(t, px, base, 20, img)
Image.fromarray(img.astype(np.uint8)).save(OUT)
print('预览已保存:', OUT, Image.open(OUT).size)
