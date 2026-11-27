# -*- coding: utf-8 -*-
"""
TMP 中文字体资产重建（安全版）。

与之前版本的关键区别：
  1. 只用「等长原地替换」：hex 数据长度固定（4096*4096*2），替换后文件总长必须不变
  2. 每个替换都做前后断言，任何一项失败立刻退出，绝不写文件
  3. 图集按行写入前就确认 shape 与 m_Width/m_Height 一致
  4. img2array 使用 flipud，与 Unity 自下而上的存储约定一致

用法：
  python FontTools/rebuild_safe.py --dry
  python FontTools/rebuild_safe.py
"""
import io
import os
import re
import sys

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from packer import maxrects_pack
from sdf_fast import glyph_sdf

PROJ = os.path.dirname(HERE)
ASSET = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback SDF.asset')
TTFP = os.path.join(PROJ, 'Assets/AdSDK/Font/DroidSansFallback.ttf')

POINT_SIZE = 90
# ——— SDF 参数（第四轮定稿）———
# 前几轮反复改 spread 都是在治标：真正的根因是 m_Metrics 与 m_GlyphRect
# 尺寸不一致（差 2*PADDING），TMP 把含留白的整块压进更小的四边形，
# 才出现"竖条切片 / 横向压扁"。度量修好后 spread 回到标准比例即可：
#   _GradientScale = 2 * spread，留白 >= spread
#   gs=10 / spread=5 / padding=10  → TMP 默认手感，边缘柔和且不糊
PADDING = 10
GRADIENT_SCALE = 10                # = 2 * spread
SPREAD = GRADIENT_SCALE / 2.0      # = 5.0
ATLAS = 2048
GAP = 6
NOTDEF_INDEX = 3

DRY = '--dry' in sys.argv


# ---------------------------------------------------------------- 字符收集
def _unescape_yaml(raw):
    """还原 Unity YAML 字符串里的转义：\\uXXXX / \\n / \\t / \\\\ 等。"""
    def rep(m):
        tok = m.group(1)
        if tok[0] == 'u':
            return chr(int(tok[1:], 16))
        return {'n': '\n', 't': '\t', 'r': '\r', '0': '\0',
                '"': '"', "'": "'", '\\': '\\', '/': '/'}.get(tok, tok)
    return re.sub(r'\\(u[0-9a-fA-F]{4}|.)', rep, raw)


def collect_chars():
    used = set()
    stats = {'m_text': 0, 'm_Text': 0, 'cs': 0}
    for root, dirs, files in os.walk(os.path.join(PROJ, 'Assets')):
        for f in files:
            if not f.endswith(('.prefab', '.unity', '.asset', '.cs')):
                continue
            p = os.path.join(root, f)
            try:
                t = io.open(p, encoding='utf-8', errors='ignore').read()
            except Exception:
                continue
            srcs = []
            if f.endswith('.cs'):
                # 只取明显的字符串字面量
                for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"', t):
                    srcs.append(_unescape_yaml(m.group(1)))
                stats['cs'] += len(srcs)
            else:
                # 关键修复：字段名是 m_Text / m_text 两种大小写都要抓；
                # 值可能是 "..." 带引号且含 \uXXXX 转义，也可能是不带引号的裸文本
                for m in re.finditer(r'^(\s*m_[Tt]ext:\s*)(.*)$', t, re.M):
                    val = m.group(2).strip()
                    if not val or val in ('""', "''"):
                        continue
                    if len(val) >= 2 and val[0] == val[-1] and val[0] in '"\'':
                        val = val[1:-1]
                        val = _unescape_yaml(val)
                    srcs.append(val)
                    stats['m_Text' if 'm_Text' in m.group(1) else 'm_text'] += 1
            for raw in srcs:
                for ch in raw:
                    if ch not in ('\n', '\r', '\t'):
                        used.add(ord(ch))
    for c in range(32, 127):
        used.add(c)
    for ch in '，。！？；：、（）《》「」【】—…·%+-/×÷':
        used.add(ord(ch))
    print('  收集：m_Text=%d 条  m_text=%d 条  cs字符串=%d 条  共 %d 个唯一码位'
          % (stats['m_Text'], stats['m_text'], stats['cs'], len(used)))
    return sorted(used)


def fmt(v):
    r = round(float(v), 4)
    if abs(r - int(r)) < 1e-9:
        return str(int(r))
    return ('%.4f' % r).rstrip('0').rstrip('.')


# ---------------------------------------------------------------- 字形光栅化
def rasterize(ch, ft_font):
    """
    用 PIL 内建 FreeType 渲染。
    返回 (mask(bool), bx, by, cw, chh) 或 None。
    anchor='ls' -> 左基线对齐。
    """
    ps = POINT_SIZE
    top = int(ps * 1.3)
    bottom = int(ps * 0.6)
    left = int(ps * 0.35)
    right = int(ps * 1.6)
    W, H = left + right, top + bottom
    im = Image.new('L', (W, H), 0)
    ImageDraw.Draw(im).text((left, top), ch, fill=255, font=ft_font, anchor='ls')
    a = np.array(im)
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    crop = a[y0:y1, x0:x1]
    mask = crop > 110
    if not mask.any():
        return None
    return mask, (x0 - left), (top - y0), (x1 - x0), (y1 - y0)


# ---------------------------------------------------------------- 主流程
def main():
    print('读取 TTF ...', flush=True)
    tt = TTFont(TTFP)
    gs = tt.getGlyphSet()
    cmap = tt.getBestCmap()
    upem = tt['head'].unitsPerEm
    hmtx = tt['hmtx']
    scale = POINT_SIZE / upem
    print('  upem=%d scale=%.5f' % (upem, scale), flush=True)

    ft_font = ImageFont.truetype(TTFP, POINT_SIZE)

    chars = collect_chars()
    n_cjk = len([c for c in chars if 0x4E00 <= c <= 0x9FFF])
    print('字符 %d（汉字 %d）' % (len(chars), n_cjk), flush=True)

    # ---- 逐字形
    glyphs = []
    miss = []
    for i, uni in enumerate(chars):
        ch = chr(uni)
        if uni not in cmap:
            miss.append(uni)
            continue
        gname = cmap[uni]
        adv = hmtx[gname][0] * scale
        r = rasterize(ch, ft_font)
        if r is None:
            # 空格等无墨字形
            glyphs.append(dict(uni=uni, adv=adv, w=0.0, h=0.0, bx=0.0, by=0.0,
                               alpha=None, gw=0, gh=0))
            continue
        core, bx, by, cw, chh = r
        gw, gh = cw + PADDING * 2, chh + PADDING * 2
        bmp = Image.new('L', (gw, gh), 0)
        bmp.paste(Image.fromarray((core * 255).astype(np.uint8), 'L'), (PADDING, PADDING))
        mask = np.array(bmp) > 127
        alpha = glyph_sdf(mask, PADDING, SPREAD)
        assert alpha.shape == (gh, gw), 'alpha shape 不符'
        glyphs.append(dict(uni=uni, adv=adv, w=float(cw), h=float(chh),
                           bx=float(bx), by=float(by), alpha=alpha, gw=gw, gh=gh))
        if (i + 1) % 150 == 0:
            print('  %d/%d' % (i + 1, len(chars)), flush=True)

    print('字形 %d，TTF 缺失 %d: %s'
          % (len(glyphs), len(miss), ''.join(chr(c) for c in miss)), flush=True)

    # ---- 装箱
    drawable = [g for g in glyphs if g['alpha'] is not None]
    items = [(g['gw'] + GAP, g['gh'] + GAP, k) for k, g in enumerate(drawable)]
    p0, up0 = maxrects_pack(items, ATLAS, ATLAS)
    print('图集0: %d/%d' % (len(p0), len(drawable)), flush=True)
    placed = [(0, x, y, k) for (x, y, k) in p0]
    n_atlas = 1
    if up0:
        rest = [(drawable[k]['gw'] + GAP, drawable[k]['gh'] + GAP, k) for k in up0]
        p1, up1 = maxrects_pack(rest, ATLAS, ATLAS)
        print('图集1: %d/%d' % (len(p1), len(up0)), flush=True)
        placed += [(1, x, y, k) for (x, y, k) in p1]
        n_atlas = 2
        if up1:
            print('错误：%d 个仍放不下' % len(up1), flush=True)
            sys.exit(2)

    used_area = sum(drawable[k]['gw'] * drawable[k]['gh'] for (_, _, _, k) in placed)
    print('利用率 %.1f%%' % (used_area / (ATLAS * ATLAS * n_atlas) * 100), flush=True)

    # ---- 渲染图集（保存槽位）
    atl = [np.zeros((ATLAS, ATLAS), dtype=np.uint8) for _ in range(n_atlas)]
    slot = {}
    for (ai, x, y, k) in placed:
        g = drawable[k]
        a = g['alpha']
        atl[ai][y:y + g['gh'], x:x + g['gw']] = a
        slot[g['uni']] = (ai, x, y, g['gw'], g['gh'])

    if DRY:
        print('\n[DRY] 不写文件')
        for ai in range(n_atlas):
            Image.fromarray(atl[ai]).resize((620, 620), Image.LANCZOS).save(
                os.path.join(HERE, 'dry_atlas%d.png' % ai))
        print('预览已保存 FontTools/dry_atlas*.png')
        return

    # ---- 读资产
    raw = io.open(ASSET, 'rb').read()
    s = raw.decode('utf-8')
    L0 = len(s)
    print('\n资产长度 %d' % L0, flush=True)

    # 定位两个 Texture2D 文档的 hex 数据区间
    tex = []
    for m in re.finditer(r'--- !u!28 &(-?\d+)\n', s):
        fid = m.group(1)
        nxt = s.find('\n--- !u!', m.end())
        en = len(s) if nxt < 0 else nxt
        seg = s[m.start():en]
        hm = re.search(r'  _typelessdata: ([0-9a-f]+)\n', seg)
        assert hm, '纹理 %s 无 _typelessdata' % fid
        w = int(re.search(r'  m_Width: (\d+)', seg).group(1))
        h = int(re.search(r'  m_Height: (\d+)', seg).group(1))
        tex.append(dict(fid=fid, seg_start=m.start(), seg_end=en,
                        hex_start=m.start() + hm.start(1),
                        hex_end=m.start() + hm.end(1),
                        hexlen=len(hm.group(1)), w=w, h=h))
    print('纹理文档 %d 个' % len(tex))
    for t in tex:
        print('  &%s %dx%d hexlen=%d expect=%d'
              % (t['fid'], t['w'], t['h'], t['hexlen'], t['w'] * t['h'] * 2))

    # 图集列表顺序
    lm = re.search(r'  m_AtlasTextures:\n((?:  - \{fileID: \d+\}\n)+)', s)
    assert lm, 'm_AtlasTextures 未找到'
    atlas_fids = re.findall(r'fileID: (\d+)', lm.group(1))
    print('m_AtlasTextures:', atlas_fids)
    assert len(atlas_fids) == len(tex) == n_atlas, \
        '图集数不匹配: 列表 %d / 文档 %d / 需要 %d' % (len(atlas_fids), len(tex), n_atlas)

    tex_by_fid = {t['fid']: t for t in tex}

    # ---- 等长替换 hex
    edits = []
    for ai in range(n_atlas):
        t = tex_by_fid[atlas_fids[ai]]
        arr = np.flipud(atl[ai])          # Unity 自下而上存储
        hx = arr.tobytes().hex()
        assert len(hx) == t['hexlen'], \
            'hex 长度 %d != 原 %d' % (len(hx), t['hexlen'])
        edits.append((t['hex_start'], t['hex_end'], hx))

    for st, en, hx in sorted(edits, key=lambda e: -e[0]):
        s = s[:st] + hx + s[en:]

    assert len(s) == L0, '替换后长度变化 %d -> %d' % (L0, len(s))

    # ---- 重写 GlyphTable / CharacterTable（这两段长度会变，放最后做）
    glyphs.sort(key=lambda g: g['uni'])
    entries = [dict(idx=NOTDEF_INDEX, w=0.0, h=0.0, bx=0.0, by=0.0, adv=23.5625,
                    x=0, y=0, gw=0, gh=0, atlas=0)]
    chars_tbl = [(0xFFFD, NOTDEF_INDEX)]
    nxt_idx = NOTDEF_INDEX + 1
    for g in glyphs:
        if g['alpha'] is None:
            entries.append(dict(idx=nxt_idx, w=0.0, h=0.0, bx=0.0, by=0.0, adv=g['adv'],
                                x=0, y=0, gw=0, gh=0, atlas=0))
        else:
            ai, x, y, gw, gh = slot[g['uni']]
            # ——— 关键修复（第四轮，已按 TMP 源码核实）———
            # TMP_Text.cs 里：
            #   uv0.x = (glyphRect.x - padding) / atlasWidth
            # 说明 TMP 会**主动**从 glyphRect 往外扩 padding 去采样 SDF 渐变带。
            # 因此 m_GlyphRect 必须只圈住「字形本体」，留白放在它外侧；
            # m_Metrics 也用本体尺寸，二者严格一致。
            # 之前把整块（含留白）都塞进 GlyphRect，TMP 又外扩一圈，
            # 采样区越界 + 四边形比例失真 -> 竖条切片 / 横向压扁。
            entries.append(dict(idx=nxt_idx, w=float(g['w']), h=float(g['h']),
                                bx=g['bx'], by=g['by'],
                                adv=g['adv'], x=x + PADDING, y=y + PADDING,
                                gw=int(round(g['w'])), gh=int(round(g['h'])), atlas=ai))
        chars_tbl.append((g['uni'], nxt_idx))
        nxt_idx += 1

    gt = ''
    for g in entries:
        # ——— 关键（第八坑）———
        # m_GlyphRect.m_Y 必须是「字形底边距图集底边的高度」，即自下而上。
        # 装箱用的是图像坐标（自上而下），所以这里必须 ATLAS - y - gh。
        # 写反了不会报错，只会让 TMP 去镜像位置采样，屏幕上表现为
        # 横向切片 / 百叶窗 / 乱码，而且所有自查脚本都会"自洽通过"。
        gy = ATLAS - g['y'] - g['gh'] if g['gh'] else 0
        gt += ('  - m_Index: %d\n    m_Metrics:\n'
               '      m_Width: %s\n      m_Height: %s\n'
               '      m_HorizontalBearingX: %s\n      m_HorizontalBearingY: %s\n'
               '      m_HorizontalAdvance: %s\n    m_GlyphRect:\n'
               '      m_X: %d\n      m_Y: %d\n      m_Width: %d\n      m_Height: %d\n'
               '    m_Scale: 1\n    m_AtlasIndex: %d\n    m_ClassDefinitionType: 0\n'
               ) % (g['idx'], fmt(g['w']), fmt(g['h']), fmt(g['bx']), fmt(g['by']),
                    fmt(g['adv']), g['x'], gy, g['gw'], g['gh'], g['atlas'])

    ct = ''
    for (uni, gidx) in chars_tbl:
        ct += ('  - m_ElementType: 1\n    m_Unicode: %d\n    m_GlyphIndex: %d\n    m_Scale: 1\n'
               % (uni, gidx))

    i_g = s.index('  m_GlyphTable:\n')
    i_c = s.index('  m_CharacterTable:\n')
    i_a = s.index('  m_AtlasTextures:\n')
    new_s = s[:i_g] + '  m_GlyphTable:\n' + gt + '  m_CharacterTable:\n' + ct + s[i_a:]

    # ---- Used / Free（针对激活图集）
    # 注意：占用区域必须按「槽位（含留白）」记，否则装箱信息失真；
    # 但 TMP 的 m_UsedGlyphRects 语义是「已被占用的图集区域」，
    # 这里保持槽位矩形（含留白），与 glyphRect（本体）分开表达是正确的。
    ACT = 0
    used_by_atlas = {}
    for (ai, x, y, k) in placed:
        used_by_atlas.setdefault(ai, []).append((x, y, drawable[k]['gw'], drawable[k]['gh']))
    cur = sorted(used_by_atlas.get(ACT, []))
    # 同样必须自下而上
    used_txt = ''.join('  - m_X: %d\n    m_Y: %d\n    m_Width: %d\n    m_Height: %d\n'
                       % (x, ATLAS - y - h, w, h) for (x, y, w, h) in cur)

    # 计算该图集最大空闲矩形
    occ = np.zeros((ATLAS, ATLAS), dtype=bool)
    for (x, y, w, h) in cur:
        occ[y:y + h, x:x + w] = True
    heights = np.zeros(ATLAS, dtype=int)
    best = (0, 0, 0, 0, 0)
    for yy in range(ATLAS):
        heights = np.where(occ[yy], 0, heights + 1)
        stack = []
        for xx in range(ATLAS + 1):
            c = heights[xx] if xx < ATLAS else 0
            start = xx
            while stack and stack[-1][1] >= c:
                sx, hh = stack.pop()
                if hh * (xx - sx) > best[0]:
                    best = (hh * (xx - sx), sx, yy - hh + 1, xx - sx, hh)
                start = sx
            stack.append((start, c))
    _, fx, fy, fw, fh = best
    print('激活图集 %d：Used %d 条，最大空闲 (%d,%d) %dx%d'
          % (ACT, len(cur), fx, fy, fw, fh))
    free_txt = ('  - m_X: %d\n    m_Y: %d\n    m_Width: %d\n    m_Height: %d\n'
                % (fx, ATLAS - fy - fh, fw, fh)) if fw >= 60 and fh >= 60 else ''

    m = re.search(r'  m_UsedGlyphRects:\n((?:  - m_X: -?\d+\n(?:    [^\n]*\n)*)*)', new_s)
    assert m
    new_s = new_s[:m.start(1)] + used_txt + new_s[m.end(1):]

    m = re.search(r'  m_FreeGlyphRects:\n((?:  - m_X: -?\d+\n(?:    [^\n]*\n)*)*)', new_s)
    assert m
    new_s = new_s[:m.start(1)] + free_txt + new_s[m.end(1):]

    # ---- 标量字段
    reps = [
        (r'  m_AtlasWidth: \d+', '  m_AtlasWidth: %d' % ATLAS),
        (r'  m_AtlasHeight: \d+', '  m_AtlasHeight: %d' % ATLAS),
        (r'  m_AtlasTextureIndex: \d+', '  m_AtlasTextureIndex: %d' % ACT),
        (r'  m_AtlasPadding: \d+', '  m_AtlasPadding: %d' % PADDING),
        (r'  m_AtlasPopulationMode: \d+', '  m_AtlasPopulationMode: 1'),
        (r'  m_IsMultiAtlasTexturesEnabled: \d+',
         '  m_IsMultiAtlasTexturesEnabled: %d' % (1 if n_atlas > 1 else 0)),
    ]
    for pat, rep in reps:
        new_s, n = re.subn(pat, rep, new_s, count=1)
        assert n == 1, '字段替换失败: %s' % pat

    # 材质参数（只改内嵌材质段）
    st = new_s.index('--- !u!21 &-1362382178054292002')
    en = new_s.index('--- !u!114 &11400000')
    mat = new_s[st:en]
    for key, val in (('_GradientScale', '%g' % GRADIENT_SCALE),
                     ('_TextureWidth', str(ATLAS)),
                     ('_TextureHeight', str(ATLAS)),
                     ('_ScaleRatioC', '%.6g' % round(GRADIENT_SCALE / (ATLAS + GRADIENT_SCALE), 6))):
        mat, n = re.subn(r'(    - ' + re.escape(key) + r': )[-\d.]+',
                         lambda mm: mm.group(1) + val, mat, count=1)
        assert n == 1, '材质字段 %s 未找到' % key
    # _MainTex 指向激活图集
    mat, n = re.subn(r'(    - _MainTex:\n        m_Texture: \{fileID: )\d+(\})',
                     lambda mm: mm.group(1) + atlas_fids[ACT] + mm.group(2), mat, count=1)
    assert n == 1
    new_s = new_s[:st] + mat + new_s[en:]

    # ---- 写文件
    io.open(ASSET, 'w', encoding='utf-8', newline='\n').write(new_s)
    print('\n完成！%d -> %d 字节' % (L0, len(new_s)))
    print('  字形 %d / 字符 %d' % (len(entries), len(chars_tbl)))
    print('  图集 %d 张 %dx%d，激活 index=%d' % (n_atlas, ATLAS, ATLAS, ACT))


if __name__ == '__main__':
    main()
