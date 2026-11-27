# -*- coding: utf-8 -*-
"""
把指定字形从图集里按 TMP 的真实采样区（glyphRect 外扩 padding）抠出来，
放大保存，并检查它内部是否已经含有"条纹"。
如果图集里的字形块本身就是干净的，那问题一定在运行时/材质。
"""
import io
import os
import re
import sys

import numpy as np
from PIL import Image

P = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\Assets\AdSDK\Font\DroidSansFallback SDF.asset'
OUT = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\FontTools\inspect'
os.makedirs(OUT, exist_ok=True)
s = io.open(P, encoding='utf-8').read()

pad = int(re.search(r'  m_AtlasPadding: (\d+)', s).group(1))

atlas = {}
order = []
for m in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- !u!|\Z)', s, re.S):
    fid, sg = m.group(1), m.group(2)
    w = int(re.search(r'  m_Width: (\d+)', sg).group(1))
    h = int(re.search(r'  m_Height: (\d+)', sg).group(1))
    raw = re.search(r'  _typelessdata: ([0-9a-f]+)\n', sg).group(1)
    atlas[fid] = np.flipud(np.frombuffer(bytes.fromhex(raw), np.uint8).reshape(h, w))
    order.append(fid)

atl_list = re.findall(r'fileID: (\d+)',
                      re.search(r'  m_AtlasTextures:\n((?:  - \{fileID[^\n]*\n)+)', s).group(1)) \
    if re.search(r'  m_AtlasTextures:\n((?:  - \{fileID[^\n]*\n)+)', s) else order
print('m_AtlasTextures:', atl_list)
print('纹理文档顺序  :', order)

i_g = s.index('  m_GlyphTable:')
i_c = s.index('  m_CharacterTable:')
i_a = s.index('  m_AtlasTextures:')
gt, ct = s[i_g:i_c], s[i_c:i_a]
u2g = {int(m.group(1)): int(m.group(2))
       for m in re.finditer(r'  - m_ElementType: \d+\n    m_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', ct)}
B = {int(m.group(1)): m.group(2)
     for m in re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S)}

chars = sys.argv[1] if len(sys.argv) > 1 else '漫操得'
for ch in chars:
    u = ord(ch)
    if u not in u2g or u2g[u] not in B:
        print('「%s」缺失' % ch)
        continue
    b = B[u2g[u]]
    x, y, w, h = map(int, re.search(
        r'    m_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', b).groups())
    ai = int(re.search(r'    m_AtlasIndex: (\d+)', b).group(1))
    tex = atlas[atl_list[ai]]

    # TMP 采样区
    sx0, sy0 = x - pad, y - pad
    sx1, sy1 = x + w + pad, y + h + pad
    sub = tex[max(0, sy0):sy1, max(0, sx0):sx1]

    # 只取本体
    body = tex[y:y + h, x:x + w]

    big = Image.fromarray(sub, 'L').resize((sub.shape[1] * 4, sub.shape[0] * 4), Image.NEAREST)
    big.save(os.path.join(OUT, '%s_%04X_sample.png' % (ch, u)))
    Image.fromarray(body, 'L').resize((w * 4, h * 4), Image.NEAREST).save(
        os.path.join(OUT, '%s_%04X_body.png' % (ch, u)))

    # 条纹检测：统计横向连续同值段长度
    m = body > 128
    runs = []
    for row in m:
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        st = np.where(d == 1)[0]
        en = np.where(d == -1)[0]
        runs.extend((en - st).tolist())
    print('「%s」atlas%d rect=(%d,%d,%d,%d)  采样区(%d,%d)-(%d,%d)  笔画段数%d 中位宽%d'
          % (ch, ai, x, y, w, h, sx0, sy0, sx1, sy1, len(runs), int(np.median(runs)) if runs else 0))

print('\n图集块已保存到', OUT)
