# -*- coding: utf-8 -*-
"""
TMP 中文字体资产完整重建。

目标：把工程实际用到的全部字符（约 640 个，含 517 个汉字）烘焙进图集，
     运行时零动态补字，WebGL 手机环境最稳定。

图集方案：2 张 2048x2048 Alpha8（共 8MB），MaxRects 装箱，利用率 ~87%。

用法：
  python rebuild_font.py --dry     只做装箱验证，不写文件
  python rebuild_font.py           完整重建
"""
import io
import math
import os
import re
import sys

import numpy as np
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdf_fast import glyph_sdf
from packer import maxrects_pack

# 用法: python rebuild_tmp_sdf_atlas.py <项目根目录> <字体资产.asset> <源字体.ttf> [--dry]
_ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(_ARGS) < 3:
    raise SystemExit("用法: python rebuild_tmp_sdf_atlas.py <PROJ> <字体资产.asset> <源字体.ttf> [--dry]")
PROJ = _ARGS[0]
ASSET = _ARGS[1]
TTFP = _ARGS[2]

POINT_SIZE = 90
PADDING = 9
GRADIENT_SCALE = 10
ATLAS_SIZE = 2048
GAP = 6          # 字形之间的额外间隔
NOTDEF_INDEX = 3
NOTDEF_ADV = 23.5625

DRY = '--dry' in sys.argv


# ---------------------------------------------------------------- 字形轮廓
class LayerPen(BasePen):
    def __init__(self, glyphSet):
        super().__init__(glyphSet)
        self.contours, self.cur = [], []

    def _moveTo(self, p):
        if self.cur:
            self.contours.append(self.cur)
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, 9):
            t = i / 8.0
            mt = 1 - t
            self.cur.append((
                mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, 9):
            t = i / 8.0
            mt = 1 - t
            self.cur.append((
                mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
                mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        if self.cur:
            self.contours.append(self.cur)
            self.cur = []

    def _endPath(self):
        self._closePath()


# ---------------------------------------------------------------- 字符集
def collect_chars():
    used = set()
    for root, dirs, files in os.walk(os.path.join(PROJ, 'Assets')):
        for f in files:
            if not f.endswith(('.prefab', '.unity', '.asset', '.cs')):
                continue
            p = os.path.join(root, f)
            try:
                t = io.open(p, encoding='utf-8', errors='ignore').read()
            except Exception:
                continue
            if f.endswith('.cs'):
                srcs = re.findall(r'"([^"\\\n]*)"', t)
            else:
                srcs = [m.group(1) for m in re.finditer(r'm_text:\s*(.*)$', t, re.M)]
            for raw in srcs:
                raw = raw.strip()
                if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in '\'"':
                    raw = raw[1:-1]
                for ch in raw:
                    if ch != '\n':
                        used.add(ord(ch))
    for c in range(32, 127):
        used.add(c)
    for ch in '，。！？；：、（）《》「」【】—…·%+-/×÷':
        used.add(ord(ch))
    return sorted(used)


def fmt(v):
    r = round(float(v), 4)
    if abs(r - int(r)) < 1e-9:
        return str(int(r))
    return ('%.4f' % r).rstrip('0').rstrip('.')


# ---------------------------------------------------------------- 主流程
def main():
    print('读取 TTF ...', flush=True)
    tt = TTFont(TTFP)
    gs = tt.getGlyphSet()
    cmap = tt.getBestCmap()
    upem = tt['head'].unitsPerEm
    hmtx = tt['hmtx']
    scale = POINT_SIZE / upem
    print('  unitsPerEm=%d  scale=%.5f  cmap=%d' % (upem, scale, len(cmap)), flush=True)

    chars = collect_chars()
    n_cjk = len([c for c in chars if 0x4E00 <= c <= 0x9FFF])
    print('待烘焙字符 %d 个（汉字 %d 个）' % (len(chars), n_cjk), flush=True)

    # ---- 逐字形生成 SDF
    glyphs = []
    miss = []
    for i, uni in enumerate(chars):
        if uni not in cmap:
            miss.append(uni)
            continue
        gname = cmap[uni]
        pen = LayerPen(gs)
        try:
            gs[gname].draw(pen)
        except Exception:
            miss.append(uni)
            continue
        adv = hmtx[gname][0] * scale
        if not pen.contours:
            glyphs.append(dict(uni=uni, adv=adv, w=0.0, h=0.0, bx=0.0, by=0.0,
                               alpha=None, gw=0, gh=0))
            continue
        xs = [p[0] for c in pen.contours for p in c]
        ys = [p[1] for c in pen.contours for p in c]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)

        # ---- 用 PIL 内建 FreeType 光栅化（正确处理复合轮廓 / 内孔）
        # 切忌用 ImageDraw.polygon 逐轮廓填充：PIL 的 polygon 不支持
        # nonzero/evenodd 环绕规则，每个轮廓独立实心填充，会让「回」「日」
        # 这类带内孔的字被填实，多部件汉字被割裂成碎片 —— 渲染成斑驳点阵。
        ft_font = ImageFont.truetype(TTFP, POINT_SIZE)
        top = int(POINT_SIZE * 1.25)
        bottom = int(POINT_SIZE * 0.55)
        left = int(POINT_SIZE * 0.35)
        right = int(POINT_SIZE * 1.6)
        tmp = Image.new('L', (left + right, top + bottom), 0)
        ImageDraw.Draw(tmp).text((left, top), chr(uni), fill=255,
                                 font=ft_font, anchor='ls')   # ls = 左基线
        tarr = np.array(tmp)
        nzy, nzx = np.nonzero(tarr)
        if len(nzx) == 0:
            glyphs.append(dict(uni=uni, adv=adv, w=0.0, h=0.0, bx=0.0, by=0.0,
                               alpha=None, gw=0, gh=0))
            continue
        cx0, cx1 = int(nzx.min()), int(nzx.max()) + 1
        cy0, cy1 = int(nzy.min()), int(nzy.max()) + 1
        bmp = Image.new('L', (cx1 - cx0 + PADDING * 2, cy1 - cy0 + PADDING * 2), 0)
        bmp.paste(Image.fromarray(tarr[cy0:cy1, cx0:cx1], 'L'), (PADDING, PADDING))
        gw, gh = bmp.size
        mask = np.array(bmp) > 127
        if not mask.any():
            glyphs.append(dict(uni=uni, adv=adv, w=0.0, h=0.0, bx=0.0, by=0.0,
                               alpha=None, gw=0, gh=0))
            continue
        alpha = glyph_sdf(mask, PADDING, GRADIENT_SCALE / 2.0)
        # 度量：以 FreeType bbox 为准（像素，相对 baseline 左端）
        glyphs.append(dict(uni=uni, adv=adv,
                           w=float(cx1 - cx0), h=float(cy1 - cy0),
                           bx=float(cx0 - left), by=float(top - cy0),
                           alpha=alpha, gw=gw, gh=gh))
        if (i + 1) % 100 == 0:
            print('  已生成 %d/%d' % (i + 1, len(chars)), flush=True)

    print('生成字形 %d 个，TTF 缺失 %d 个: %s'
          % (len(glyphs), len(miss), ''.join(chr(c) for c in miss)), flush=True)

    # ---- 装箱
    drawable = [g for g in glyphs if g['alpha'] is not None]
    items = [(g['gw'] + GAP, g['gh'] + GAP, k) for k, g in enumerate(drawable)]
    placed, unplaced = maxrects_pack(items, ATLAS_SIZE, ATLAS_SIZE)
    print('图集 0: 装入 %d / %d' % (len(placed), len(drawable)), flush=True)

    placed_all = [(0, x, y, k) for (x, y, k) in placed]
    if unplaced:
        rest_items = [(drawable[k]['gw'] + GAP, drawable[k]['gh'] + GAP, k) for k in unplaced]
        placed2, unplaced2 = maxrects_pack(rest_items, ATLAS_SIZE, ATLAS_SIZE)
        print('图集 1: 装入 %d / %d' % (len(placed2), len(unplaced)), flush=True)
        placed_all += [(1, x, y, k) for (x, y, k) in placed2]
        if unplaced2:
            bad = ''.join(chr(drawable[k]['uni']) for k in unplaced2)
            print('错误：仍有 %d 个放不下: %s' % (len(unplaced2), bad[:80]), flush=True)
            sys.exit(2)
    else:
        placed2 = []

    n_atlas = 2 if placed2 else 1
    print('使用图集张数:', n_atlas, flush=True)

    # 统计利用率
    used_area = sum(drawable[k]['gw'] * drawable[k]['gh'] for (_, _, _, k) in placed_all)
    print('面积利用率 %.1f%%' % (used_area / (ATLAS_SIZE * ATLAS_SIZE * n_atlas) * 100), flush=True)

    if DRY:
        return

    # ---- 渲染图集
    atlases = [Image.new('L', (ATLAS_SIZE, ATLAS_SIZE), 0) for _ in range(n_atlas)]
    slot = {}
    for (ai, x, y, k) in placed_all:
        g = drawable[k]
        atlases[ai].paste(Image.fromarray(g['alpha'], 'L'), (x, y))
        slot[g['uni']] = (ai, x, y, g['gw'], g['gh'])

    for ai in range(n_atlas):
        atlases[ai].save(os.path.join(PROJ, 'Temp/atlas%d_new.png' % ai))
    print('预览已保存 Temp/atlas0_new.png ...', flush=True)

    # ---- 读取资产
    s = io.open(ASSET, encoding='utf-8').read()

    # 图集纹理 fileID 列表
    m = re.search(r'  m_AtlasTextures:\n((?:  - \{fileID: \d+\}\n)+)', s)
    assert m, 'm_AtlasTextures 未找到'
    old_fids = re.findall(r'fileID: (\d+)', m.group(1))
    print('原图集 fileID:', old_fids, flush=True)

    # 找到全部 Texture2D 文档
    tex_docs = {}
    for mm in re.finditer(r'--- !u!28 &(\d+)\nTexture2D:', s):
        fid = mm.group(1)
        st = s.rindex('--- !u!', 0, mm.end())
        nxt = s.find('\n--- !u!', st + 10)
        en = len(s) if nxt < 0 else nxt
        tex_docs[fid] = (st, en)
    print('找到 Texture2D 文档:', list(tex_docs.keys()), flush=True)

    # 确定可用 fid（复用旧的，不够就造新的）
    import random
    random.seed(20261126)
    fids = list(old_fids)
    while len(fids) < n_atlas:
        newfid = str(random.randrange(10 ** 18, 10 ** 19))
        fids.append(newfid)
        # 复制第一个纹理文档作为模板
        tmpl_st, tmpl_en = tex_docs[old_fids[0]]
        tmpl = s[tmpl_st:tmpl_en]
        tmpl = re.sub(r'&%s' % old_fids[0], '&%s' % newfid, tmpl, count=1)
        tmpl = re.sub(r'm_Name: .*', 'm_Name: DroidSansFallback SDF Atlas %d' % (len(fids) - 1), tmpl, count=1)
        s = s + '\n' + tmpl
        tex_docs = {}
        for mm in re.finditer(r'--- !u!28 &(\d+)\nTexture2D:', s):
            st = s.rindex('--- !u!', 0, mm.end())
            nxt = s.find('\n--- !u!', st + 10)
            en = len(s) if nxt < 0 else nxt
            tex_docs[mm.group(1)] = (st, en)
        print('  新建纹理文档 &%s' % newfid, flush=True)

    # 重新扫一遍文档位置（因为新建文档可能追加过）
    def rescan(src):
        docs = {}
        for mm in re.finditer(r'--- !u!28 &(\d+)\nTexture2D:', src):
            st = src.rindex('--- !u!', 0, mm.end())
            nxt = src.find('\n--- !u!', st + 10)
            en = len(src) if nxt < 0 else nxt
            docs[mm.group(1)] = (st, en)
        return docs

    tex_docs = rescan(s)

    # 对每个纹理段做「整段替换」：改尺寸 + 换像素数据，一次性完成
    repl = []
    for ai in range(n_atlas):
        fid = fids[ai]
        st, en = tex_docs[fid]
        seg = s[st:en]
        mm = re.search(r'_typelessdata: ([0-9a-f]+)', seg)
        assert mm, '纹理 %s 无 _typelessdata' % fid
        new_hex = np.flipud(np.array(atlases[ai])).tobytes().hex()
        body = seg[:mm.start(1)] + new_hex + seg[mm.end(1):]
        body = re.sub(r'(\n  m_Width: )\d+', r'\g<1>%d' % ATLAS_SIZE, body, count=1)
        body = re.sub(r'(\n  m_Height: )\d+', r'\g<1>%d' % ATLAS_SIZE, body, count=1)
        body = re.sub(r'm_Name: .*', 'm_Name: DroidSansFallback SDF Atlas %d' % ai, body, count=1)
        repl.append((st, en, body))

    # 按起始位置降序替换，避免偏移失效
    for (st, en, body) in sorted(repl, key=lambda t: -t[0]):
        s = s[:st] + body + s[en:]
    print('纹理像素与尺寸已写入', flush=True)

    # ---- 更新 m_AtlasTextures 列表 / Index / 尺寸（注意字段前有 2 空格缩进）
    lst = '  m_AtlasTextures:\n' + ''.join('  - {fileID: %s}\n' % f for f in fids[:n_atlas])
    s, n1 = re.subn(r'  m_AtlasTextures:\n(?:  - \{fileID: \d+\}\n)+', lst, s, count=1)
    s, n2 = re.subn(r'  m_AtlasTextureIndex: \d+', '  m_AtlasTextureIndex: %d' % (n_atlas - 1), s, count=1)
    s, n3 = re.subn(r'  m_AtlasWidth: \d+', '  m_AtlasWidth: %d' % ATLAS_SIZE, s, count=1)
    s, n4 = re.subn(r'  m_AtlasHeight: \d+', '  m_AtlasHeight: %d' % ATLAS_SIZE, s, count=1)
    print('字段更新: AtlasTextures=%d AtlasTextureIndex=%d Width=%d Height=%d'
          % (n1, n2, n3, n4), flush=True)
    assert n1 == 1 and n2 == 1 and n3 == 1 and n4 == 1, '图集相关字段替换失败'
    # ---- 重排 GlyphTable / CharacterTable
    glyphs.sort(key=lambda g: g['uni'])
    entries = [dict(idx=NOTDEF_INDEX, w=0.0, h=0.0, bx=0.0, by=0.0, adv=NOTDEF_ADV,
                    x=0, y=0, gw=0, gh=0, atlas=0)]
    chars_tbl = [(0xFFFD, NOTDEF_INDEX)]
    next_idx = NOTDEF_INDEX + 1

    for g in glyphs:
        uni = g['uni']
        if g['alpha'] is None:
            entries.append(dict(idx=next_idx, w=0.0, h=0.0, bx=0.0, by=0.0, adv=g['adv'],
                                x=0, y=0, gw=0, gh=0, atlas=0))
        else:
            ai, x, y, gw, gh = slot[uni]
            entries.append(dict(idx=next_idx, w=g['w'], h=g['h'], bx=g['bx'], by=g['by'],
                                adv=g['adv'], x=x, y=y, gw=gw, gh=gh, atlas=ai))
        chars_tbl.append((uni, next_idx))
        next_idx += 1

    assert next_idx < 65535, '字形数超限'
    print('字形条目 %d，字符条目 %d' % (len(entries), len(chars_tbl)), flush=True)

    gt = ''
    for g in entries:
        gt += (
            '  - m_Index: %d\n    m_Metrics:\n'
            '      m_Width: %s\n      m_Height: %s\n'
            '      m_HorizontalBearingX: %s\n      m_HorizontalBearingY: %s\n'
            '      m_HorizontalAdvance: %s\n    m_GlyphRect:\n'
            '      m_X: %d\n      m_Y: %d\n      m_Width: %d\n      m_Height: %d\n'
            '    m_Scale: 1\n    m_AtlasIndex: %d\n    m_ClassDefinitionType: 0\n'
        ) % (g['idx'], fmt(g['w']), fmt(g['h']), fmt(g['bx']), fmt(g['by']), fmt(g['adv']),
             g['x'], g['y'], g['gw'], g['gh'], g['atlas'])

    ct = ''
    for (uni, gidx) in chars_tbl:
        ct += '  - m_ElementType: 1\n    m_Unicode: %d\n    m_GlyphIndex: %d\n    m_Scale: 1\n' % (uni, gidx)

    # 替换 GlyphTable：从 "  m_GlyphTable:" 到 "  m_CharacterTable:" 之前
    i_g = s.index('  m_GlyphTable:\n')
    i_c = s.index('  m_CharacterTable:\n')
    s = s[:i_g] + '  m_GlyphTable:\n' + gt + s[i_c:]
    # 替换 CharacterTable：从 "  m_CharacterTable:" 到 "  m_AtlasTextures:" 之前
    i_c = s.index('  m_CharacterTable:\n')
    i_a = s.index('  m_AtlasTextures:\n')
    s = s[:i_c] + '  m_CharacterTable:\n' + ct + s[i_a:]

    # ---- 重建 Used / Free（针对当前激活图集）
    cur_ai = n_atlas - 1
    used = [(e['x'], e['y'], e['gw'], e['gh']) for e in entries
            if e['atlas'] == cur_ai and e['gw'] > 0]
    used = sorted(set(used), key=lambda r: (r[1], r[0]))

    occ = np.zeros((ATLAS_SIZE, ATLAS_SIZE), dtype=bool)
    for x, y, w, h in used:
        occ[y:y + h, x:x + w] = True

    free = []
    yy = 0
    while yy < ATLAS_SIZE:
        row = ~occ[yy]
        if not row.any():
            yy += 1
            continue
        xx = 0
        while xx < ATLAS_SIZE:
            if not row[xx]:
                xx += 1
                continue
            x0 = xx
            while xx < ATLAS_SIZE and row[xx]:
                xx += 1
            w = xx - x0
            y1 = yy
            while y1 + 1 < ATLAS_SIZE and not occ[y1 + 1, x0:x0 + w].any():
                y1 += 1
            h = y1 - yy + 1
            if w >= 110 and h >= 110:
                free.append((x0, yy, w, h))
                occ[yy:y1 + 1, x0:x0 + w] = True
        yy += 1

    used_txt = '  m_UsedGlyphRects:\n' + ''.join(
        '  - m_X: %d\n    m_Y: %d\n    m_Width: %d\n    m_Height: %d\n' % r for r in used)
    free_txt = '  m_FreeGlyphRects:\n' + ''.join(
        '  - m_X: %d\n    m_Y: %d\n    m_Width: %d\n    m_Height: %d\n' % r
        for r in sorted(free, key=lambda r: (r[1], r[0])))

    s, nr = re.subn(r'  m_UsedGlyphRects:\n(?:  - m_X: -?\d+\n    m_Y: -?\d+\n'
                    r'    m_Width: -?\d+\n    m_Height: -?\d+\n)*'
                    r'  m_FreeGlyphRects:\n(?:  - m_X: -?\d+\n    m_Y: -?\d+\n'
                    r'    m_Width: -?\d+\n    m_Height: -?\d+\n)*',
                    used_txt + free_txt, s, count=1)
    print('Used/Free 替换:', nr, flush=True)
    assert nr == 1, 'Used/Free 段替换失败'

    # ---- 写盘
    io.open(ASSET, 'w', encoding='utf-8', newline='\n').write(s)
    free_area = sum(r[2] * r[3] for r in free)
    print('\n完成！', flush=True)
    print('  字形 %d，字符 %d' % (len(entries), len(chars_tbl)), flush=True)
    print('  图集 %d 张 %dx%d，当前激活 index=%d' % (n_atlas, ATLAS_SIZE, ATLAS_SIZE, cur_ai), flush=True)
    print('  Used %d 条，Free %d 条（剩余 %.1f%% 可动态补字）'
          % (len(used), len(free), free_area / ATLAS_SIZE / ATLAS_SIZE * 100), flush=True)


if __name__ == '__main__':
    main()
