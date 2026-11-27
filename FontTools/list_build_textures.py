# -*- coding: utf-8 -*-
"""列出 data.unity3d 里所有纹理按尺寸排序，并检查是否有 Alpha8 大块。"""
import os

import UnityPy

SRC = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\FontTools\build_extract\data.unity3d'
env = UnityPy.load(SRC)

rows = []
for obj in env.objects:
    try:
        if obj.type.name != 'Texture2D':
            continue
    except Exception:
        continue
    try:
        d = obj.read()
        rows.append((d.m_Width * d.m_Height, d.m_Width, d.m_Height,
                     getattr(d, 'm_TextureFormat', '?'),
                     str(getattr(d, 'm_Name', '?')), obj.path_id))
    except Exception:
        pass

rows.sort(reverse=True)
print('纹理总数 %d' % len(rows))
print('%-11s %-7s %-6s %-8s %s' % ('面积', 'WxH', 'fmt', 'pid', 'name'))
for area, w, h, fmt, nm, pid in rows[:25]:
    print('%-11d %-7s %-6s %-8s %s' % (area, '%dx%d' % (w, h), fmt, pid, nm[:30]))

# 统计 format 分布
from collections import Counter
c = Counter(r[3] for r in rows)
print('\n纹理格式分布:', dict(c))
