# -*- coding: utf-8 -*-
"""在所有构建产物文件里找 2048 纹理与 TMP 字体。"""
import glob
import os

import UnityPy

BASE = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\FontTools\build_extract'
OUT = os.path.join(BASE, 'font')
os.makedirs(OUT, exist_ok=True)

for fp in sorted(glob.glob(os.path.join(BASE, '*'))):
    if os.path.isdir(fp):
        continue
    name = os.path.basename(fp)
    try:
        env = UnityPy.load(fp)
    except Exception as e:
        print('%-42s 无法加载: %s' % (name, e))
        continue
    n_tex = n_mono = 0
    big = []
    for obj in env.objects:
        try:
            t = obj.type.name
        except Exception:
            continue
        if t == 'Texture2D':
            n_tex += 1
            try:
                d = obj.read()
                if d.m_Width >= 1024 and d.m_Height >= 1024:
                    big.append((obj.path_id, d.m_Width, d.m_Height, getattr(d, 'm_Name', '?'),
                                getattr(d, 'm_TextureFormat', '?')))
            except Exception:
                pass
        elif t == 'MonoBehaviour':
            n_mono += 1
    print('%-42s Texture2D=%-4d Mono=%-5d 大纹理=%d' % (name, n_tex, n_mono, len(big)))
    for pid, w, h, nm, fmt in big[:10]:
        print('     %dx%d name=%r fmt=%s pid=%s' % (w, h, nm, fmt, pid))
