"""Photographic mockups driven by library/mockups.json.

Each entry describes a photo (brand-independent): where the logo goes (`anchor`, source px),
how tall the logo is on the object (`ls`, source px), optional per-format overrides, clean-up
operations (`erase`) and the `material` used to apply the logo.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from . import logo
from .core import (ctx, col, hexc, put, noise, chrome, bevel, shadow, lum, outline, grid,
                   rounded_rect_alpha)

_img_cache = {}
LIB_DIR = Path('.')


def load(fn):
    if fn not in _img_cache:
        _img_cache[fn] = np.asarray(Image.open(LIB_DIR / fn).convert('RGB'), np.float32) / 255
    return _img_cache[fn]


# ---------------------------------------------------------------- geometry
def frame(src, anchor, ls, rot=0.0, pad='nearest', pad_blur=30):
    """Resample `src` so that `anchor` lands on the frame centre and `ls` source px become LOGO_H."""
    s = ctx.LOGO_H / ls
    x, y = grid()
    u, v = (x - ctx.CX) / s, (y - ctx.CY) / s
    th = math.radians(rot)
    sx = anchor[0] + u * math.cos(th) - v * math.sin(th)
    sy = anchor[1] + u * math.sin(th) + v * math.cos(th)
    h, w = src.shape[:2]
    base = src
    if s < 0.6:
        f = max(1, int(0.6 / s))
        base = ndimage.uniform_filter(src, size=(f, f, 1))
    out = np.stack([ndimage.map_coordinates(base[..., c], [sy, sx], order=3, mode=pad) for c in range(3)], -1)
    inside = (sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1)
    if pad_blur and not inside.all():
        blurred = ndimage.gaussian_filter(out, (pad_blur, pad_blur, 0))
        dist = ndimage.distance_transform_edt(~inside)
        k = np.clip(dist / 40, 0, 1)[..., None]
        out = out * (1 - k) + blurred * k
    return np.clip(out, 0, 1).astype(np.float32), s, (sx, sy)


# ---------------------------------------------------------------- clean-up ops (source space)
def _region(src, op):
    hh, ww = src.shape[:2]
    y, x = np.mgrid[0:hh, 0:ww]
    if op['type'] == 'ellipse':
        cx, cy, rx, ry = op['e']
        return (((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2) < 1
    x0, y0, x1, y1 = op['r']
    return (x > x0) & (x < x1) & (y > y0) & (y < y1)


def erase(src, ops):
    src = src.copy()
    for op in ops or []:
        m = _region(src, op)
        method = op.get('method', 'fill')
        if method == 'patch':  # copy texture from an offset (dy, dx)
            dy, dx = op.get('offset', [500, 0])
            patch = np.roll(src, (dy, dx), axis=(0, 1))
            k = ndimage.gaussian_filter(m.astype(np.float32), op.get('feather', 8))[..., None]
            src = src * (1 - k) + patch * k
        elif method == 'fill_dark_marks':  # remove dark text/marks on a light surface
            L = lum(src)
            txt = ndimage.binary_dilation(m & (L < op.get('threshold', 0.82)), iterations=op.get('grow', 14)) & m
            white = np.median(src[m & ~txt], axis=0)
            fill = white[None, None, :] + np.random.default_rng(3).normal(0, 0.012, src.shape).astype(np.float32)
            k = ndimage.gaussian_filter(txt.astype(np.float32), 3)[..., None]
            src = src * (1 - k) + fill * k
        else:  # 'fill': median colour of a ring around the region + grain
            ring = ndimage.binary_dilation(m, iterations=12) & ~m
            c = np.median(src[ring], axis=0)
            fill = c[None, None, :] + np.random.default_rng(4).normal(0, 0.01, src.shape).astype(np.float32)
            k = ndimage.gaussian_filter(m.astype(np.float32), op.get('feather', 3))[..., None]
            src = src * (1 - k) + fill * k
    return src


# ---------------------------------------------------------------- material helpers (frame space)
def ink(img, a, c, texture=1.0, opacity=0.96):
    L = lum(img)
    region = ndimage.grey_dilation(a, size=(25, 25)) > 0.1
    ref = np.median(L[region]) if region.any() else L.mean()
    shade = np.clip(1 + texture * (L - ref) / max(ref, 0.12), 0.55, 1.35)[..., None]
    inked = np.clip(np.asarray(c, np.float32)[None, None, :] * shade, 0, 1)
    k = (a * opacity)[..., None]
    return img * (1 - k) + inked * k


def emboss_light(img, a, depth=4.0, amount=0.35, light=(-1, -1.3)):
    h = ndimage.gaussian_filter(a, 1.6) * depth
    gy, gx = np.gradient(h)
    return np.clip(img * (1 + amount * (-(gx * light[0] + gy * light[1])))[..., None], 0, 1)


def soft_shadow(img, a, dx=3, dy=5, blur=4, strength=0.3):
    sh = ndimage.shift(ndimage.gaussian_filter(a, blur), (dy, dx), order=1)
    return img * (1 - strength * sh[..., None])


def _c(p, key='color', default='primary'):
    v = p.get(key, default)
    if v == 'white':
        return np.array([0.94, 0.95, 0.97], np.float32)
    return col(v)


def m_ink(img, a, p, **_):
    return ink(img, a, _c(p), texture=p.get('texture', 0.9), opacity=p.get('opacity', 0.96))


def m_embroidery(img, a, p, **_):
    out = ink(img, a, _c(p, default='dark'), texture=0.6)
    out = emboss_light(out, a, depth=5, amount=0.5)
    out += (noise(0.6, 0.02, 5) * a)[..., None]
    return np.clip(soft_shadow(out, a, 2, 3, 2, 0.25), 0, 1)


def m_screenprint(img, a, p, **_):
    out = ink(img, a, _c(p, default='white'), texture=p.get('texture', 0.5), opacity=0.93)
    return np.clip(out + (noise(0.8, 0.025, 7) * a)[..., None], 0, 1)


def m_foil(img, a, p, **_):
    deb = emboss_light(img, a, depth=6, amount=-0.55)
    foil = chrome(a, dark=p.get('dark', 0.4), bright=p.get('bright', 1.0))
    k = (a * 0.92)[..., None]
    return np.clip(deb * (1 - k) + foil * k, 0, 1)


def m_seal(img, a, p, **_):
    x, y = grid()
    r = 0.95 * ctx.LOGO_H
    seal = np.clip(r - np.hypot(x - ctx.CX, y - ctx.CY), 0, 1).astype(np.float32)
    img = soft_shadow(img, seal, 3, 6, 6, 0.4)
    put(img, seal, bevel(seal, _c(p), depth=10, spec=0.3))
    return np.clip(ink(img, a, np.array([0.97, 0.98, 1.0]), texture=0.2), 0, 1)


def m_patch(img, a, p, **_):
    u = ctx.u
    x, y = grid()
    hw, hh, r = 150 * u, 130 * u, 26 * u
    patch = rounded_rect_alpha(ctx.CX, ctx.CY, hw, hh, r)
    img = soft_shadow(img, patch, 4, 8, 7, 0.45)
    base = _c(p, default='dark')
    weave = base + noise(0.7, 0.03, 31)[..., None] + (0.02 * np.sin(x * 1.3) * np.sin(y * 1.3))[..., None]
    put(img, patch, bevel(patch, base * 1.25, depth=5, spec=0.08) * 0.6 + weave * 0.4)
    inner = rounded_rect_alpha(ctx.CX, ctx.CY, hw - 14 * u, hh - 14 * u, max(r - 14 * u, 2))
    edge = ndimage.gaussian_filter(inner, 0.5) - ndimage.grey_erosion(inner, size=(3, 3))
    stitch = np.clip(edge * 3, 0, 1) * (np.sin((x + y) * 0.35) > 0) * patch
    img = img * (1 - 0.7 * stitch[..., None]) + 0.7 * stitch[..., None] * np.array([0.75, 0.8, 0.9])
    out = ink(img, a, np.array([0.95, 0.96, 0.98]), texture=0.3)
    out = emboss_light(out, a, depth=4, amount=0.4)
    return np.clip(out + (noise(0.6, 0.02, 32) * a)[..., None], 0, 1)


def m_glass(img, a, p, **_):
    fro = np.clip(ndimage.gaussian_filter(img, (4, 4, 0)) * 0.72 + 0.34, 0, 1)
    k = (a * 0.95)[..., None]
    return np.clip(img * (1 - k) + fro * k, 0, 1)


def m_neon(img, a, p, **_):
    img = img * p.get('darken', 0.7)
    tube = ndimage.gaussian_filter(np.clip(outline(a, 1.5), 0, 1), 0.6)
    c = np.clip(col('light') * 0.6 + col('primary') * 0.4 + 0.1, 0, 1)
    for sg, g in ((3, 0.8), (12, 0.45), (45, 0.35)):
        b = ndimage.gaussian_filter(tube, sg * max(ctx.u, 0.7)); b /= b.max() + 1e-6
        img = img + (b * g)[..., None] * c[None, None]
    img = img * (1 - tube[..., None]) + np.array([0.9, 0.96, 1.0]) * tube[..., None]
    return np.clip(img, 0, 1)


def _screen_fill(mask_y0, mask_y1, a):
    x, y = grid()
    t = np.clip((y - mask_y0) / max(1, mask_y1 - mask_y0), 0, 1)[..., None]
    scr = col('dark') * (1 - t) + np.clip(col('dark') * 0.4 + col('primary') * 0.6, 0, 1) * 0.75 * t
    scr = scr * (1 - a[..., None]) + np.ones(3) * a[..., None]
    return scr


def m_screen_phone(img, a, p, sxy=None, **_):
    sx, sy = sxy
    L = lum(img); sat = img.max(-1) - img.min(-1)
    x0, x1, y0, y1, rr = p['rect']
    notch_y = p.get('notch_y', y0 + 250)
    ddx = np.maximum(np.maximum(x0 + rr - sx, sx - (x1 - rr)), 0)
    ddy = np.maximum(np.maximum(y0 + rr - sy, sy - (y1 - rr)), 0)
    inside = (sx > x0) & (sx < x1) & (sy > y0) & (sy < y1) & (np.hypot(ddx, ddy) < rr)
    skin = (sat > 0.10) | (L < 0.30) | ((L < 0.5) & (sy < notch_y))
    skin = ndimage.binary_opening(skin, iterations=2)
    m = inside & ~skin
    near = ndimage.binary_dilation(m, iterations=30)
    m = m | (near & (L > 0.72) & (sat < 0.14))
    lab, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m = np.isin(lab, 1 + np.where(sizes > 2000)[0])
    mf = ndimage.gaussian_filter(m.astype(np.float32), 1.2)
    ys = np.where(m.any(1))[0]
    scr = _screen_fill(ys.min(), ys.max(), a)
    xg, yg = grid()
    scr = scr + 0.25 * np.exp(-(((xg - 0.65 * ctx.W) / (300 * ctx.u)) ** 2 + ((yg - 0.26 * ctx.H) / (300 * ctx.u)) ** 2))[..., None] * col('primary')
    refl = (L - np.median(L[m])) [..., None] * 0.35 if m.any() else 0
    return img * (1 - mf[..., None]) + np.clip(scr + refl, 0, 1) * mf[..., None]


def m_screen_color(img, a, p, **_):
    """Screen found by colour range (uniform grey/white display), seeded at the frame centre."""
    L = lum(img); sat = img.max(-1) - img.min(-1)
    lo, hi = p.get('lum_range', [0.6, 0.85])
    cond = (L > lo) & (L < hi) & (sat < p.get('max_sat', 0.05))
    lab, _ = ndimage.label(cond)
    l = lab[ctx.CY, ctx.CX]
    m = ndimage.binary_fill_holes(ndimage.binary_closing(lab == l, iterations=2)) if l else cond
    ys = np.where(m.any(1))[0]
    mf = ndimage.gaussian_filter(m.astype(np.float32), 0.8)
    return img * (1 - mf[..., None]) + _screen_fill(ys.min(), ys.max(), a) * mf[..., None]


def m_screen_watch(img, a, p, s=1.0, **_):
    hw, hh, r = [v * s for v in p['screen']]
    m = rounded_rect_alpha(ctx.CX, ctx.CY, hw, hh, r)
    x, y = grid()
    rad = 1.12 * ctx.LOGO_H
    ring = np.clip(0.038 * ctx.LOGO_H - np.abs(np.hypot(x - ctx.CX, y - ctx.CY) - rad), 0, 1)
    ang = (np.arctan2(y - ctx.CY, x - ctx.CX) + np.pi / 2) % (2 * np.pi)
    scr = np.zeros_like(img) + 0.01
    scr = scr * (1 - ring[..., None]) + np.clip(col('dark') * 1.4, 0, 1) * ring[..., None]
    arc = ring * (ang < 5.6)
    scr = scr * (1 - arc[..., None]) + col('primary') * arc[..., None]
    scr = scr * (1 - a[..., None]) + col('light') * a[..., None]
    refl = (0.07 * np.clip(1 - np.abs((x - ctx.CX) + (y - ctx.CY) * 0.8 + 120 * ctx.u) / (160 * ctx.u), 0, 1))[..., None]
    return np.clip(img * (1 - m[..., None]) + (scr + refl) * m[..., None], 0, 1)


MATERIALS = dict(ink=m_ink, embroidery=m_embroidery, screenprint=m_screenprint, foil=m_foil, seal=m_seal,
                 patch=m_patch, glass=m_glass, neon=m_neon, screen_phone=m_screen_phone,
                 screen_color=m_screen_color, screen_watch=m_screen_watch)


def render(entry):
    fmt = entry.get(ctx.fmt, {})
    anchor = fmt.get('anchor', entry['anchor'])
    ls = fmt.get('ls', entry['ls'])
    src = erase(load(entry['file']), entry.get('erase'))
    img, s, sxy = frame(src, anchor, ls, rot=entry.get('rot', 0.0))
    a = logo.alpha()
    mat = entry.get('material', {'type': 'ink'})
    return MATERIALS[mat['type']](img, a, mat, s=s, sxy=sxy)
