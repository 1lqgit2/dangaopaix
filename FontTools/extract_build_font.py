# -*- coding: utf-8 -*-
"""
从构建产物 data.unity3d 中提取 TMP 字体资产与图集纹理，落到磁盘，
用于和工程里的 .asset 对比。
"""
import os
import sys

import UnityPy

BASE = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\FontTools\build_extract'
SRC = os.path.join(BASE, 'data.unity3d')
OUT = os.path.join(BASE, 'font')
os.makedirs(OUT, exist_ok=True)

env = UnityPy.load(SRC)

textures = {}
monos = []
for obj in env.objects:
    try:
        t = obj.type.name
    except Exception:
        continue
    if t == 'Texture2D':
        textures[obj.path_id] = obj
    elif t in ('MonoBehaviour',):
        monos.append(obj)

print('Texture2D %d 个, MonoBehaviour %d 个' % (len(textures), len(monos)))

# 找 2048x2048 的纹理
print('\n=== 2048x2048 纹理 ===')
cands = []
for pid, obj in textures.items():
    try:
        d = obj.read()
        w, h = d.m_Width, d.m_Height
        if w == 2048 and h == 2048:
            cands.append((pid, obj, d))
    except Exception:
        pass
print('候选 %d 个' % len(cands))

for i, (pid, obj, d) in enumerate(cands):
    name = getattr(d, 'm_Name', '?')
    fmt = getattr(d, 'm_TextureFormat', '?')
    print('  [%d] pid=%s name=%r fmt=%s' % (i, pid, name, fmt))
    try:
        img = d.image
        fp = os.path.join(OUT, 'tex_%d_%s.png' % (i, str(pid)))
        img.save(fp)
        print('       ->', fp, img.size, img.mode)
    except Exception as e:
        print('       导出失败:', e)

# 找 TMP_FontAsset（MonoBehaviour，脚本名含 TMP_FontAsset）
print('\n=== 疑似 TMP 字体 MonoBehaviour ===')
for obj in monos:
    try:
        d = obj.read()
        name = getattr(d, 'm_Name', '')
        if 'SDF' in str(name) or 'Fallback' in str(name):
            print('  pid=%s name=%r' % (obj.path_id, name))
            # 尝试 dump 关键字段
            tt = d.read_typetree() if hasattr(d, 'read_typetree') else None
            if tt:
                for k in ('m_FaceInfo', 'm_AtlasTextureIndex', 'm_AtlasWidth',
                          'm_AtlasHeight', 'm_AtlasPadding', 'm_AtlasPopulationMode'):
                    if k in tt:
                        v = tt[k]
                        if isinstance(v, dict):
                            v = {kk: vv for kk, vv in list(v.items())[:4]}
                        print('    %-24s %s' % (k, v))
    except Exception:
        pass
