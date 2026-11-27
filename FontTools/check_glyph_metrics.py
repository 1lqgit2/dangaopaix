# -*- coding: utf-8 -*-
"""
交叉验证 TMP 字体资产的字形度量与源 TTF 是否一致。

用法:
  python check_glyph_metrics.py <字体资产.asset> <源字体.ttf>

校验项:
  1. 每个字形的 m_HorizontalAdvance vs TTF hmtx（排版间距）
  2. m_FaceInfo 的 AscentLine/DescentLine/LineHeight vs TTF hhea（行高基线）
"""
import io
import re
import sys

from fontTools.ttLib import TTFont

if len(sys.argv) < 3:
    raise SystemExit('用法: python check_glyph_metrics.py <字体资产.asset> <源字体.ttf>')

P = sys.argv[1]
TTFP = sys.argv[2]

s = io.open(P, encoding='utf-8').read()
tt = TTFont(TTFP)
cmap = tt.getBestCmap()
hmtx = tt['hmtx']
hhea = tt['hhea']
upem = tt['head'].unitsPerEm

fi_block = s[s.index('  m_FaceInfo:'):s.index('  m_GlyphTable:')]
POINT = float(re.search(r'm_PointSize: ([-\d.]+)', fi_block).group(1))
scale = POINT / upem
print('PointSize=%.1f  unitsPerEm=%d  scale=%.6f' % (POINT, upem, scale))

char2glyph = {}
for m in re.finditer(r'  - m_ElementType: 1\n    m_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', s):
    char2glyph[int(m.group(1))] = int(m.group(2))

glyph = {}
pat = re.compile(
    r'  - m_Index: (\d+)\n    m_Metrics:\n'
    r'      m_Width: ([-\d.]+)\n      m_Height: ([-\d.]+)\n'
    r'      m_HorizontalBearingX: ([-\d.]+)\n      m_HorizontalBearingY: ([-\d.]+)\n'
    r'      m_HorizontalAdvance: ([-\d.]+)\n')
for m in pat.finditer(s):
    glyph[int(m.group(1))] = dict(
        w=float(m.group(2)), h=float(m.group(3)),
        bx=float(m.group(4)), by=float(m.group(5)), adv=float(m.group(6)))

print('资产 Glyph=%d  Character=%d' % (len(glyph), len(char2glyph)))

total = 0
bad = []
for u, gi in char2glyph.items():
    if u not in cmap or gi not in glyph:
        continue
    expect = hmtx[cmap[u]][0] * scale
    got = glyph[gi]['adv']
    total += 1
    if abs(expect - got) > 0.03:
        bad.append((chr(u), expect, got))

print('\n[1] advance 全量比对: %d 个字，不匹配 %d 个' % (total, len(bad)))
for ch, e, g in bad[:10]:
    print('    %s 期望 %.4f 实际 %.4f' % (ch, e, g))

fi = {}
for k in ['m_AscentLine', 'm_DescentLine', 'm_LineHeight']:
    m = re.search(k + r': ([-\d.]+)', fi_block)
    if m:
        fi[k] = float(m.group(1))

checks = [
    ('AscentLine', fi.get('m_AscentLine'), hhea.ascent * scale),
    ('DescentLine', fi.get('m_DescentLine'), hhea.descent * scale),
    ('LineHeight', fi.get('m_LineHeight'),
     (hhea.ascent - hhea.descent + hhea.lineGap) * scale),
]
print('\n[2] FaceInfo 比对:')
for name, a, b in checks:
    if a is None:
        print('    %-14s 资产无此值' % name)
        continue
    diff = abs(a - b)
    print('    %-14s 资产=%9.4f  TTF=%9.4f  差=%.4f  %s'
          % (name, a, b, diff, 'OK' if diff < 1.5 else '偏差较大'))

print('\n结论:', '通过' if not bad else '存在 %d 处 advance 偏差' % len(bad))
