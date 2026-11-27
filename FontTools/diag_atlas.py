# -*- coding: utf-8 -*-
"""
诊断：资产里两个 Texture2D 文档的 hex 数据长度是否与 m_Width*m_Height 匹配，
以及文档边界是否被破坏（导致后面的文档被吃掉）。
"""
import io
import os
import re

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'
P = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
s = io.open(P, encoding='utf-8').read()
print('文件总长:', len(s))

docs = [(m.start(), m.group(1), m.group(2))
        for m in re.finditer(r'--- !u!(\d+) &(-?\d+)', s)]
print('\n=== 文档边界 ===')
for k, (pos, cls, fid) in enumerate(docs):
    end = docs[k + 1][0] if k + 1 < len(docs) else len(s)
    print('  !u!%-4s &%-22s  offset %9d..%-9d  len %9d' % (cls, fid, pos, end, end - pos))

print('\n=== Texture2D 详情 ===')
for m in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- !u!|\Z)', s, re.S):
    fid, sg = m.group(1), m.group(2)
    w = int(re.search(r'  m_Width: (\d+)', sg).group(1))
    h = int(re.search(r'  m_Height: (\d+)', sg).group(1))
    cis = int(re.search(r'  m_CompleteImageSize: (\d+)', sg).group(1))
    mm = re.search(r'  _typelessdata: ([0-9a-f]*)\n', sg)
    hexlen = len(mm.group(1)) if mm else 0
    print('  &%s  %dx%d  CompleteImageSize=%d  expect=%d  hexlen=%d  expect_hex=%d  %s'
          % (fid, w, h, cis, w * h, hexlen, w * h * 2,
             'OK' if hexlen == w * h * 2 else '!! 长度不符'))

print('\n=== hex 数据里是否混入了非 hex 字符 ===')
for m in re.finditer(r'--- !u!28 &(-?\d+)\n(.*?)(?=\n--- !u!|\Z)', s, re.S):
    fid, sg = m.group(1), m.group(2)
    mm = re.search(r'  _typelessdata: ([0-9a-f]*)\n', sg)
    if mm:
        d = mm.group(1)
        bad = sum(1 for c in d if c not in '0123456789abcdef')
        print('  &%s  hexlen=%d  非hex字符=%d' % (fid, len(d), bad))
        # 检查该行之后是否还有内容（说明 hex 提前结束）
        tail = sg[mm.end():mm.end() + 120]
        print('      hex 之后紧跟: %r' % tail[:100])
