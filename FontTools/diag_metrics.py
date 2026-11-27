# -*- coding: utf-8 -*-
"""
诊断「竖条切片」症状：检查 m_Metrics 与 m_GlyphRect 的尺寸是否一致、
UV 计算是否合理。
TMP 里每个字形有两套尺寸：
  m_GlyphRect: 图集里的像素矩形 (x, y, width, height)
  m_Metrics:   显示尺寸 (width, height, horizontalBearingX, horizontalBearingY, horizontalAdvance)
如果 m_Metrics.width != m_GlyphRect.width，显示时就会横向拉伸/压缩。
"""
import io
import os
import re

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'
P = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
s = io.open(P, encoding='utf-8').read()

i_g = s.index('  m_GlyphTable:')
i_c = s.index('  m_CharacterTable:')
gt = s[i_g:i_c]
ct = s[i_c:s.index('  m_AtlasTextures:')]

chars = {}
for m in re.finditer(r'  - m_ElementType: \d+\n    m_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', ct):
    chars[int(m.group(1))] = int(m.group(2))

blocks = list(re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S))
print('字形块 %d 个' % len(blocks))

print('\n%-4s %-5s %-18s %-30s %-24s' % ('char', 'gid', 'GlyphRect(x,y,w,h)', 'Metrics(w,h,bx,by,adv)', '判定'))
bad = 0
for ch in '看广告获得奖励返回确认添加金币进入侧边栏':
    u = ord(ch)
    if u not in chars:
        print('%-4s 不在字符表' % ch)
        continue
    gid = chars[u]
    blk = None
    for m in blocks:
        if int(m.group(1)) == gid:
            blk = m.group(2)
            break
    if blk is None:
        print('%-4s gid=%d 无字形块' % (ch, gid))
        continue
    gr = re.search(r'    m_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', blk)
    me = re.search(r'    m_Metrics:\n      m_Width: ([-\d.]+)\n      m_Height: ([-\d.]+)\n      m_HorizontalBearingX: ([-\d.]+)\n      m_HorizontalBearingY: ([-\d.]+)\n      m_HorizontalAdvance: ([-\d.]+)', blk)
    if not gr or not me:
        print('%-4s 结构解析失败' % ch)
        continue
    gx, gy, gw, gh = map(int, gr.groups())
    mw, mh, bx, by, adv = map(float, me.groups())
    ok = 'OK' if abs(mw - gw) < 0.51 and abs(mh - gh) < 0.51 else '!! W/H 不一致'
    if '!!' in ok:
        bad += 1
    print('%-4s %-5d (%4d,%4d,%4d,%4d)%4s(%.1f,%.1f,%.1f,%.1f,%.1f)%s'
          % (ch, gid, gx, gy, gw, gh, ' ', mw, mh, bx, by, adv, ok))

print('\n全量检查...')
badlist = []
for u, gid in chars.items():
    if u < 0x20:
        continue
    blk = None
    for m in blocks:
        if int(m.group(1)) == gid:
            blk = m.group(2)
            break
    if blk is None:
        continue
    gr = re.search(r'    m_GlyphRect:\n      m_X: (-?\d+)\n      m_Y: (-?\d+)\n      m_Width: (-?\d+)\n      m_Height: (-?\d+)', blk)
    me = re.search(r'    m_Metrics:\n      m_Width: ([-\d.]+)\n      m_Height: ([-\d.]+)\n      m_HorizontalBearingX: ([-\d.]+)\n      m_HorizontalBearingY: ([-\d.]+)\n      m_HorizontalAdvance: ([-\d.]+)', blk)
    if not gr or not me:
        badlist.append((u, gid, '结构缺失'))
        continue
    gw, gh = int(gr.group(3)), int(gr.group(4))
    mw, mh = float(me.group(1)), float(me.group(2))
    if abs(mw - gw) > 0.51 or abs(mh - gh) > 0.51:
        badlist.append((u, gid, 'W %.1f vs %d / H %.1f vs %d' % (mw, gw, mh, gh)))

print('尺寸不一致 %d / %d' % (len(badlist), len(chars)))
for u, gid, msg in badlist[:15]:
    print('  U+%04X gid=%d %s' % (u, gid, msg))
