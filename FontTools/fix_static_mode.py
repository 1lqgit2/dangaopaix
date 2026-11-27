# -*- coding: utf-8 -*-
"""
把字体从 Dynamic 改为 Static，并修正被 Unity 改脏的材质参数。

根因：
  m_AtlasPopulationMode: 1 (Dynamic)
  动态模式下 TMP 不相信预烘焙字形，会：
    - 运行时用 FreeType 从源 TTF 现场光栅化
    - 往图集里继续塞字形，重排 m_UsedGlyphRects / m_FreeGlyphRects
  => 预烘焙字形的 UV 与实际像素错位 -> 屏幕上是横条/百叶窗/错位
WebGL / 抖音小游戏环境（无系统字体、FreeType 行为差异）下尤其明显。

改为 Static(0) 后字形全部来自预烘焙图集，UV 与像素严格对应。
"""
import io
import re
import shutil
import sys

P = sys.argv[1] if len(sys.argv) > 1 else \
    r'C:\Unity\project\Unity2021_蛋糕排序_CakeSort3DColorPuzzle\Assets\AdSDK\Font\DroidSansFallback SDF.asset'

raw = io.open(P, 'rb').read()
s_raw = raw.decode('utf-8')
L0 = len(s_raw)

# 备份
shutil.copy(P, P + '.bak_before_static')

s = s_raw

def sub1(pat, rep, label):
    global s
    new, n = re.subn(pat, rep, s, count=1)
    if n != 1:
        print('  !! %s 替换失败（匹配 %d 次）' % (label, n))
        return False
    s = new
    print('  %-28s -> %s' % (label, rep.strip()))
    return True

print('== 1. 改 Static ==')
sub1(r'  m_AtlasPopulationMode: \d+', '  m_AtlasPopulationMode: 0', 'm_AtlasPopulationMode')

print('== 2. 关掉 build 时保留动态数据 ==')
sub1(r'  m_ClearDynamicDataOnBuild: \d+', '  m_ClearDynamicDataOnBuild: 1', 'm_ClearDynamicDataOnBuild')

print('== 3. 修正材质参数 ==')
gs = float(re.search(r'    - _GradientScale: ([-\d.]+)', s).group(1))
pad = int(re.search(r'  m_AtlasPadding: (\d+)', s).group(1))
pt = float(re.search(r'    m_PointSize: ([-\d.]+)', s).group(1))
aw = float(re.search(r'    - _TextureWidth: ([-\d.]+)', s).group(1))

ratio_a = 2.0 * pad / pt
ratio_c = gs / (aw + gs)
sub1(r'    - _ScaleRatioA: [-\.\d]+', '    - _ScaleRatioA: %.6g' % round(ratio_a, 6), '_ScaleRatioA')
sub1(r'    - _ScaleRatioC: [-\.\d]+', '    - _ScaleRatioC: %.6g' % round(ratio_c, 6), '_ScaleRatioC')

# 这里只改标量字段，不碰图集 hex，所以长度可以有微小的合法变化。
# 关键校验：图集的 hex 数据必须原封不动。
def hexes(txt):
    return [m.group(1) for m in re.finditer(r'  _typelessdata: ([0-9a-f]+)\n', txt)]


h_before = hexes(s_raw)
h_after = hexes(s)
assert len(h_before) == len(h_after), '图集文档数变了：%d -> %d' % (len(h_before), len(h_after))
for i, (a, b) in enumerate(zip(h_before, h_after)):
    assert a == b, '第 %d 个图集 hex 被改动！' % i
print('\n图集 hex 校验：%d 张全部未变 OK' % len(h_after))

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('已写回，长度 %d -> %d（仅标量字段长度变化）' % (L0, len(s)))
print('理论 _ScaleRatioA = 2*%d/%g = %.6f' % (pad, pt, ratio_a))
print('理论 _ScaleRatioC = %g/(%g+%g) = %.6f' % (gs, aw, gs, ratio_c))
