# -*- coding: utf-8 -*-
"""
逐字形精确 SDF。字形位图很小（约 92x92），Felzenszwalb EDT 在这个尺寸上很快。
"""
import numpy as np


def edt1d(f):
    """Felzenszwalb 一维平方距离变换。"""
    n = len(f)
    d = np.empty(n, dtype=np.float64)
    v = np.zeros(n, dtype=np.int64)
    z = np.empty(n + 1, dtype=np.float64)
    k = 0
    v[0] = 0
    z[0] = -1e20
    z[1] = 1e20
    for q in range(1, n):
        denom = 2.0 * q - 2.0 * v[k]
        s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / denom
        while s <= z[k] and k > 0:
            k -= 1
            denom = 2.0 * q - 2.0 * v[k]
            s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / denom
        k += 1
        v[k] = q
        z[k] = s
        z[k + 1] = 1e20
    k = 0
    for q in range(n):
        while z[k + 1] < q:
            k += 1
        d[q] = (q - v[k]) ** 2 + f[v[k]]
    return d


def edt2d_sq(binary):
    """
    精确二维欧氏距离变换。
    binary: bool，True 为种子。
    返回每个像素到最近 True 的「平方距离」。
    """
    INF = 1e12
    h, w = binary.shape
    f = np.where(binary, 0.0, INF)
    g = np.empty_like(f)
    for x in range(w):
        g[:, x] = edt1d(f[:, x])
    out = np.empty_like(f)
    for y in range(h):
        out[y, :] = edt1d(g[y, :])
    return out


def glyph_sdf(mask, padding, spread):
    """
    mask: bool 数组，True = 字形实体内部
    padding: 每边留白像素
    spread: SDF 半宽，通常等于 m_AtlasPadding

    返回 uint8，TMP 约定：alpha = 0.5 + signedDist/(2*spread)*255
      - 实体内部：alpha > 128
      - 边界处：  alpha = 128
      - 外部远处：alpha = 0
    """
    h, w = mask.shape
    if not mask.any():
        return np.zeros((h, w), dtype=np.uint8)

    # 到最近「实体」的距离（实体内部为 0）
    dist_to_fg = np.sqrt(edt2d_sq(mask))
    # 到最近「背景」的距离（背景上为 0）
    dist_to_bg = np.sqrt(edt2d_sq(~mask))

    # 有符号距离：内部为正，外部为负
    sd = np.where(mask, dist_to_bg, -dist_to_fg)

    alpha = 0.5 + sd / (2.0 * spread)
    return (np.clip(alpha, 0.0, 1.0) * 255.0).round().astype(np.uint8)
