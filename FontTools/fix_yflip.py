# -*- coding: utf-8 -*-
"""
修复决定性根因：m_GlyphRect.m_Y 写反了（写成了「自上而下」，Unity/TMP 要「自下而上」）。

证据（FontTools/conv/）：
  Unity 自烘焙的 LiberationSans SDF：'A' 的 rect=(828,103,57,59)
    -> 在图像里按 H-y-h 裁 -> 干净的字母 A  ✔ 说明 m_Y 是「距底边」
  本项目的 DroidSansFallback SDF：'漫' 的 rect=(555,987,83,82)
    -> 按 H-y-h 裁 -> 碎片；按 y 裁 -> 完整的「漫」

所以图集像素是对的，只是记录下来的 y 方向反了。TMP 按 H-y-h 去采样，
拿到的就是镜像位置的内容 —— 屏幕上表现为横向切片/百叶窗。

本脚本只翻 y，不动任何像素数据。
  H 取该图集实际高度（两张都是 2048）
"""
import io
import os
import re
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')

s = io.open(ASSET, encoding='utf-8').read()
orig_len = len(s)

# ---- 图集高度 ----
heights = {}
for d in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- |\Z)', s, re.S):
    fid, body = d.group(1), d.group(2)
    m = re.search(r'  m_Height: (\d+)', body)
    if m:
        heights[fid] = int(m.group(1))
atl = re.findall(r'  m_AtlasTextures:\n((?:  - \{fileID: -?\d+\}\n)+)', s)
atlas_fids = re.findall(r'fileID: (-?\d+)', atl[0])
H_DEFAULT = heights[atlas_fids[0]]
print('图集高度:', heights, ' 默认 H =', H_DEFAULT)

# ---- 1) 字形表：逐字形翻 y ----
i_g = s.index('  m_GlyphTable:')
i_c = s.index('  m_CharacterTable:')
head, gtable, tail = s[:i_g], s[i_g:i_c], s[i_c:]

blocks = re.split(r'(?=  - m_Index: )', gtable)
out_blocks = []
flipped = 0
for b in blocks:
    mh = re.search(r'    m_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', b)
    if not mh:
        out_blocks.append(b)
        continue
    x, y, w, h = (int(v) for v in mh.groups())
    mai = re.search(r'    m_AtlasIndex: (\d+)', b)
    ai = int(mai.group(1)) if mai else 0
    H = heights.get(atlas_fids[ai], H_DEFAULT) if ai < len(atlas_fids) else H_DEFAULT
    if w == 0 or h == 0:
        out_blocks.append(b)
        continue
    ny = H - y - h
    if ny < 0 or ny + h > H:
        print('  跳过越界字形 gid=%s y=%d h=%d H=%d' % (
            re.search(r'  - m_Index: (\d+)', b).group(1), y, h, H))
        out_blocks.append(b)
        continue
    nb = b[:mh.start()] + (
        '    m_GlyphRect:\n      m_X: %d\n      m_Y: %d\n      m_Width: %d\n      m_Height: %d'
        % (x, ny, w, h)) + b[mh.end():]
    out_blocks.append(nb)
    flipped += 1
gtable_new = ''.join(out_blocks)
print('字形 y 已翻转: %d 个' % flipped)

s = head + gtable_new + tail

# ---- 2) Used / Free 矩形：同样翻 y ----
def flip_rect_block(span, H):
    cnt = [0]

    def rep(m):
        x, y, w, h = (int(v) for v in m.groups())
        if w == 0 or h == 0:
            return m.group(0)
        cnt[0] += 1
        return ('  - m_X: %d\n    m_Y: %d\n    m_Width: %d\n    m_Height: %d'
                % (x, H - y - h, w, h))

    new = re.sub(r'  - m_X: (-?\d+)\n    m_Y: (-?\d+)\n    m_Width: (-?\d+)\n    m_Height: (-?\d+)',
                 rep, span)
    return new, cnt[0]


for key, endkey in (('  m_UsedGlyphRects:', '  m_FreeGlyphRects:'),
                    ('  m_FreeGlyphRects:', '  m_fontInfo:')):
    i0 = s.index(key)
    i1 = s.index(endkey, i0 + 1)
    blk = s[i0:i1]
    nb, n = flip_rect_block(blk, H_DEFAULT)
    print('%s 翻 y: %d 条' % (key.strip(), n))
    s = s[:i0] + nb + s[i1:]

io.open(ASSET, 'w', encoding='utf-8', newline='').write(s)
print('\n已写回 %s' % ASSET)
print('长度 %d -> %d（像素数据未改动）' % (orig_len, len(s)))
