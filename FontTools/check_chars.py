# -*- coding: utf-8 -*-
"""检查字符收集：哪些 UI 文本里的字没被收进候选集"""
import io
import os
import re

PROJ = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle'

ESC = {'n': '\n', 't': '\t', 'r': '\r', '0': '\0', '"': '"', "'": "'",
       '\\': '\\', '/': '/'}


def unescape(raw):
    out = []
    i = 0
    while i < len(raw):
        if raw[i] == '\\' and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt == 'u' and i + 5 < len(raw) + 0 and re.match(r'[0-9a-fA-F]{4}', raw[i + 2:i + 6]):
                out.append(chr(int(raw[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append(ESC.get(nxt, nxt))
            i += 2
            continue
        out.append(raw[i])
        i += 1
    return ''.join(out)


used = set()
texts = []
n_up = n_low = 0
for root, dirs, files in os.walk(os.path.join(PROJ, 'Assets')):
    for f in files:
        if not f.endswith(('.prefab', '.unity', '.asset')):
            continue
        p = os.path.join(root, f)
        t = io.open(p, encoding='utf-8', errors='ignore').read()
        for m in re.finditer(r'^(\s*m_[Tt]ext:[ \t]*)(.*)$', t, re.M):
            key, val = m.group(1), m.group(2).strip()
            if not val or val in ('""', "''"):
                continue
            quoted = len(val) >= 2 and val[0] == val[-1] and val[0] in '"\'' 
            if quoted:
                val = unescape(val[1:-1])
            else:
                val = unescape(val)
            if 'm_Text' in key:
                n_up += 1
            else:
                n_low += 1
            texts.append((os.path.relpath(p, PROJ), val))
            for ch in val:
                used.add(ord(ch))

print('m_Text 字段 %d 条, m_text 字段 %d 条' % (n_up, n_low))
print('唯一码位(不含ASCII/标点): %d' % len([u for u in used if u > 0x7f]))
print()
print('=== 含中文的文本样本（前 25 条）===')
cn = [(p, v) for p, v in texts if any(0x4e00 <= ord(c) <= 0x9fff for c in v)]
for p, v in cn[:25]:
    print('  %-52s %r' % (os.path.basename(p), v))
print('\n含中文文本共 %d 条' % len(cn))

print('\n=== 关键 UI 字检查 ===')
test = '看视频领取奖励返回首页开始设置关卡分数金币商店排行暂停继续音效音乐关闭确定取消'
miss = [c for c in test if ord(c) not in used]
print('  缺失:', ''.join(miss) if miss else '无')
