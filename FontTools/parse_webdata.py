# -*- coding: utf-8 -*-
"""
解析 UnityWebData1.0 容器，列出内部文件，并提取 data.unity3d。
格式：
  magic "UnityWebData1.0\0"
  u32 headerLength
  然后若干条： u32 offset, u32 size, u32 pathLength, path bytes
"""
import os
import struct

P = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\FontTools\build_data.bin'
OUT = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\FontTools\build_extract'

data = open(P, 'rb').read()
magic = b'UnityWebData1.0\x00'
assert data.startswith(magic)

p = len(magic)
header_len = struct.unpack('<I', data[p:p + 4])[0]
p += 4
print('headerLength = %d (%.1f MB)' % (header_len, header_len / 1048576))

files = []
while p < header_len:
    off, size, plen = struct.unpack('<III', data[p:p + 12])
    p += 12
    path = data[p:p + plen].decode('utf-8', 'replace')
    p += plen
    files.append((path, off, size))

print('内部文件 %d 个:' % len(files))
for path, off, size in files:
    print('  %-34s off=%-10d size=%.2f MB' % (path, off, size / 1048576))

os.makedirs(OUT, exist_ok=True)
for path, off, size in files:
    safe = path.replace('/', '_').replace('\\', '_')
    fp = os.path.join(OUT, safe)
    open(fp, 'wb').write(data[off:off + size])
    print('提取 ->', fp, '%.2f MB' % (size / 1048576))
