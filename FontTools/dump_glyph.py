# -*- coding: utf-8 -*-
"""打印指定字符的完整字形块，用于对比正常字与坏字。"""
import io
import re
import sys

P = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\Assets\AdSDK\Font\DroidSansFallback SDF.asset'
s = io.open(P, encoding='utf-8').read()
i_g = s.index('  m_GlyphTable:')
i_c = s.index('  m_CharacterTable:')
i_a = s.index('  m_AtlasTextures:')
gt, ct = s[i_g:i_c], s[i_c:i_a]

u2g = {int(m.group(1)): int(m.group(2))
       for m in re.finditer(r'  - m_ElementType: \d+\n    m_Unicode: (\d+)\n    m_GlyphIndex: (\d+)', ct)}
B = {int(m.group(1)): m.group(2)
     for m in re.finditer(r'  - m_Index: (\d+)\n(.*?)(?=\n  - m_Index: |\Z)', gt, re.S)}

targets = sys.argv[1] if len(sys.argv) > 1 else '漫操得'
for ch in targets:
    u = ord(ch)
    if u not in u2g:
        print('「%s」不在字符表' % ch)
        continue
    gid = u2g[u]
    print('=' * 60)
    print('「%s」 U+%04X  gid=%d' % (ch, u, gid))
    if gid not in B:
        print('  没有对应字形块！')
        continue
    print(B[gid].rstrip())
