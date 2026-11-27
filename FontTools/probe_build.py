# -*- coding: utf-8 -*-
"""
从构建产物（解压后的 Unity serialized 数据）里找字体资产，检查它是哪一版。
Unity WebGL 数据是 LZ4/自定义序列化，无法直接当 YAML 读，
这里用特征串定位：
  - "_GradientScale" 附近是否有 _TextureWidth
  - 找 m_AtlasPadding 的二进制形态
  - 找 2048x2048 的图集原始像素（Alpha8 = 4,194,304 字节块）
更实用：直接搜 TMP 字体资产里的 FaceInfo 字符串 "Droid Sans Fallback"
以及图集尺寸字段。
"""
import os
import struct

P = r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\FontTools\build_data.bin'
data = open(P, 'rb').read()
print('数据长度 %.1f MB' % (len(data) / 1048576))

# 1) 找字体名
for name in (b'Droid Sans Fallback', b'DroidSansFallback'):
    idx = data.find(name)
    print('%-24s -> %s' % (name.decode(), idx))

# 2) 找图集尺寸：Alpha8 2048x2048 = 4194304 字节
TARGET = 4194304
hits = []
i = 0
while True:
    i = data.find(struct.pack('<I', TARGET), i)
    if i < 0:
        break
    hits.append(i)
    i += 1
    if len(hits) > 40:
        break
print('\n可能的 4MB 纹理块标记: %d 处' % len(hits))

# 3) 统计大块全零/低熵区（Alpha8 图集特征是大量 0 和 128 附近的字节）
print('\n=== 估算图集数据规模 ===')
window = 4194304
best = []
step = 2 * 1024 * 1024
for i in range(0, len(data) - window, step):
    chunk = data[i:i + window]
    z = chunk.count(b'\x00')
    if z > window * 0.5:
        best.append((i, z / window))
print('高零占比区块 %d 个' % len(best))
for i, r in best[:8]:
    print('  offset=%d (%.1f MB)  零占比 %.1f%%' % (i, i / 1048576, r * 100))
