"""Graphic (non-photo) scenes: construction, grid, lockup, marks, chrome-on-gradient, app icon..."""
import math

import numpy as np
from scipy import ndimage

from . import logo
from .core import (ctx, col, hexc, solid, comp, put, draw, shape, ell_path, rrect, outline, radial,
                   rel_shade, chrome, grid)

LINE = hexc('#74747C')
DARKLINE = hexc('#2A2B30')

_guides = []
_grid_cfg = {}


def set_guides(guides, grid_cfg):
    global _guides, _grid_cfg
    _guides = guides or auto_guides()
    _grid_cfg = grid_cfg or {}


def auto_guides():
    """Fallback construction when the brand gives none: bounding ellipse, inner circle, box and axes."""
    a = logo.aspect()
    return [
        {"shape": "ellipse", "e": [a / 2, 0.5, max(a, 1) * 0.62, max(a, 1) * 0.62]},
        {"shape": "rect", "r": [0, 0, a, 1]},
        {"shape": "ellipse", "e": [a / 2, 0.5, 0.25, 0.25]},
        {"shape": "line", "p": [a / 2, -0.3, a / 2, 1.3]},
        {"shape": "line", "p": [-0.3, 0.5, a + 0.3, 0.5]},
        {"shape": "ellipse", "e": [a / 2, 0.5, a / 2, 0.5], "dashed": True},
    ]


def _ell_px(g, h):
    nx, ny, rx, ry = g['e']
    x, y = logo.to_px(nx, ny, h=h)
    return x, y, rx * h, ry * h


def _stroke_guide(c, g, h, lw):
    dashed = g.get('dashed', False)
    dash = [7 * ctx.u, 6 * ctx.u]
    if g['shape'] == 'ellipse':
        cx, cy, rx, ry = _ell_px(g, h)
        if 'solid_x_max' in g:
            clip_x, _ = logo.to_px(g['solid_x_max'], 0, h=h)
            t0 = math.acos(max(-1, min(1, (clip_x - cx) / rx)))
            for rng, d in (((t0, 2 * math.pi - t0), False), ((-t0, t0), True)):
                c.save(); c.translate(cx, cy); c.scale(rx, ry); c.arc(0, 0, 1, *rng); c.restore()
                c.set_line_width(lw); c.set_dash(dash if d else []); c.stroke()
            return
        ell_path(c, (cx, cy, rx, ry))
    elif g['shape'] == 'rect':
        x, y, w, hh = g['r']
        x0, y0 = logo.to_px(x, y, h=h)
        c.rectangle(x0, y0, w * h, hh * h)
    elif g['shape'] == 'line':
        x0, y0, x1, y1 = g['p']
        c.move_to(*logo.to_px(x0, y0, h=h)); c.line_to(*logo.to_px(x1, y1, h=h))
    c.set_line_width(lw); c.set_dash(dash if dashed else []); c.stroke()


def blank():
    return solid(col('background'))


def construction(level):
    img = solid(col('background'))
    n = len(_guides)
    counts = {1: 1, 2: 2, 3: 3, 4: 3 + math.ceil(max(0, n - 3) / 2), 5: n, 6: n}
    items = _guides[:min(n, counts[level])]
    h = ctx.CONS_H
    comp(img, draw(lambda c: [_stroke_guide(c, g, h, 2.0 * max(ctx.u, 0.8)) for g in items]), LINE)
    if level >= 6:
        comp(img, outline(logo.alpha(h=h), 1.1), DARKLINE)
    return img


def synthesis():
    img = solid(col('background'))
    comp(img, outline(logo.alpha(), 1.1), DARKLINE)
    return img


def grid_scene():
    img = solid(col('background'))
    h = ctx.CONS_H
    a = logo.alpha(h=h)
    comp(img, a, hexc('#E3E4E9'))
    g = _grid_cfg
    ell = [x for x in _guides if x['shape'] == 'ellipse']
    hl = [logo.to_px(0, ny, h=h)[1] for ny in g.get('h_lines', [0.24, 0.76])]
    solid_x = [logo.to_px(nx, 0, h=h)[0] for nx in g.get('solid_x', [logo.aspect() / 2 - 0.02, logo.aspect() / 2 + 0.03])]
    dashed_x = [logo.to_px(nx, 0, h=h)[0] for nx in g.get('dashed_x', [0.0, logo.aspect()])]
    cross_idx = g.get('cross', list(range(min(3, len(ell)))))
    node_idx = g.get('nodes_from', list(range(min(2, len(ell)))))
    W, H = ctx.W, ctx.H
    k = 9 * ctx.u

    def f(c):
        c.set_line_width(1.5)
        for y in hl:
            c.move_to(0, y); c.line_to(W, y)
        for x in solid_x:
            c.move_to(x, 0); c.line_to(x, H)
        c.stroke()
        c.set_dash([7, 6])
        for x in dashed_x:
            c.move_to(x, 0); c.line_to(x, H)
        c.stroke(); c.set_dash([])
        for e in ell[:4]:
            ell_path(c, _ell_px(e, h)); c.stroke()
        for i in cross_idx:
            if i < len(ell):
                ex, ey = _ell_px(ell[i], h)[:2]
                c.move_to(ex - k, ey); c.line_to(ex + k, ey); c.move_to(ex, ey - k); c.line_to(ex, ey + k)
        c.stroke()
    comp(img, draw(f), LINE)
    comp(img, outline(a, 1.2), DARKLINE)
    nodes = []
    for i in node_idx:
        if i >= len(ell):
            continue
        ex, ey, rx, ry = _ell_px(ell[i], h)
        for y in hl:
            q = 1 - ((y - ey) / ry) ** 2
            if q > 0:
                d = math.sqrt(q) * rx
                nodes += [(ex - d, y), (ex + d, y)]
    r = 7 * ctx.u

    def gn(c):
        for (x, y) in nodes:
            c.arc(x, y, r, 0, 2 * math.pi); c.new_sub_path()
    comp(img, draw(lambda c: (gn(c), c.fill())), col('background'))
    comp(img, draw(lambda c: (gn(c), c.set_line_width(1.6), c.stroke())), DARKLINE)
    x0, _ = logo.to_px(0.2, 0, h=h)
    arc = draw(lambda c: (c.arc(x0, ctx.CY + 0.15 * h, 0.135 * h, math.pi / 2, math.pi), c.set_line_width(3.5 * ctx.u), c.stroke()))
    comp(img, arc, DARKLINE)
    return img


def value_map():
    img = solid(col('background'))
    h = ctx.LOGO_H
    a = logo.alpha()
    comp(img, outline(a, 1.1), DARKLINE)
    CX, CY = ctx.CX, ctx.CY
    half_w = h * logo.aspect() / 2
    u = ctx.u

    def f(c):
        c.set_line_width(1.4); c.set_dash([5, 6])
        c.move_to(CX, CY - 260 * u); c.line_to(CX, CY - h / 2 - 18 * u)
        c.move_to(CX, CY + h / 2 + 18 * u); c.line_to(CX, CY + 235 * u)
        c.move_to(CX - half_w - 20 * u, CY); c.line_to(CX - half_w - 85 * u, CY)
        c.move_to(CX + half_w + 20 * u, CY); c.line_to(CX + half_w + 85 * u, CY)
        for sx in (-1, 1):
            for sy in (-1, 1):
                c.move_to(CX + sx * 70 * u, CY + sy * 55 * u); c.line_to(CX + sx * 125 * u, CY + sy * 105 * u)
        c.stroke()
    comp(img, draw(f), LINE)
    return img


def lockup():
    img = solid(col('background'))
    lc = col('lockup_lines')
    CX, CY, W, H = ctx.CX, ctx.CY, ctx.W, ctx.H
    vertical = H >= W
    s = min(W, H) / 1080

    def P(a, b):  # a along the short axis, b along the long axis
        return (CX + a, CY + b) if vertical else (CX + b, CY + a)

    def f(c):
        c.set_line_width(1.3)
        for i in range(14):
            o = i * 9 * s
            for sx in (-1, 1):
                for sy in (-1, 1):
                    c.move_to(*P(sx * (30 * s + o * 0.3), sy * (1000 * s + o)))
                    c.curve_to(*P(sx * (80 * s + o), sy * 560 * s), *P(sx * (380 * s + o), sy * 160 * s),
                               *P(sx * (620 * s + o), sy * (60 * s - o * 0.4)))
            for sx in (-1, 1):
                L = (max(W, H) / 2 + 20)
                c.move_to(*P(sx * (40 * s + o * 0.5), -L))
                c.curve_to(*P(sx * (180 * s + o), -300 * s), *P(sx * (180 * s + o), 300 * s), *P(sx * (40 * s + o * 0.5), L))
        c.stroke()
    lines = ndimage.gaussian_filter(draw(f), 1.2)
    fade = np.clip(1 - radial(CX, CY, 1300 * s) * 0.2, 0, 1)
    comp(img, np.clip(lines * 1.2, 0, 1) * 0.7 * fade, lc)
    a = logo.alpha()
    comp(img, ndimage.gaussian_filter(a, 5 * ctx.u) * 0.35, col('dark'))
    comp(img, ndimage.gaussian_filter(a, 1.0), col('dark'))
    return img


def mark_on(bg, fg):
    img = solid(col(bg))
    comp(img, logo.alpha(), col(fg))
    return img


def silver():
    img = solid(hexc('#C8C7CB'))
    rel_shade(img, 950, 150, 700, 700, 0.9, (1, 1, 1))
    rel_shade(img, 60, 1850, 600, 500, 0.8, (1, 1, 1))
    rel_shade(img, 1050, 1800, 500, 650, 0.75, hexc('#5E5760'))
    rel_shade(img, 60, 300, 350, 600, 0.35, hexc('#9A999C'))
    a = logo.alpha()
    put(img, a, chrome(a, dark=0.05, bright=1.0))
    comp(img, outline(a, 0.9), hexc('#111114'))
    return img


def black_glow():
    img = solid(hexc('#020203'))
    rel_shade(img, -60, -60, 900, 900, 0.95, hexc('#E9EEF2'))
    rel_shade(img, 1150, 1950, 700, 900, 0.7, hexc('#8FA3AE'))
    rel_shade(img, 300, 820, 90, 90, 0.35, col('primary'))
    rel_shade(img, 690, 1180, 70, 70, 0.3, col('primary') * 0.6)
    a = logo.alpha()
    put(img, a, chrome(a, tint_top=col('light'), tint_bot=col('primary'), dark=0.08))
    return img


def color_gradient():
    img = solid(hexc('#020203'))
    rel_shade(img, -100, -150, 1000, 1100, 0.95, col('glow_a'))
    rel_shade(img, 1200, 2100, 1100, 1100, 0.95, col('glow_b'))
    a = logo.alpha()
    put(img, a, chrome(a, dark=0.12, bright=0.95))
    return img


def poster():
    img = solid(col('dark'))
    a = logo.alpha()
    comp(img, ndimage.gaussian_filter(a, 14 * ctx.u) * 0.35, col('light'))
    comp(img, ndimage.gaussian_filter(a, 4 * ctx.u) * 0.5, np.clip(col('light') * 0.3 + 0.7, 0, 1))
    comp(img, a, hexc('#FFFFFF'))
    return img


def app_icons():
    img = solid(col('background'))
    u, CX, CY = ctx.u, ctx.CX, ctx.CY
    comp(img, shape(lambda c: rrect(c, CX - 240 * u, CY - 225 * u, 1100 * u, 450 * u, 150 * u)), hexc('#ECEDF0'))
    comp(img, shape(lambda c: rrect(c, CX - 160 * u, CY - 160 * u, 320 * u, 320 * u, 72 * u)), col('dark'))
    comp(img, logo.alpha(), col('light'))
    comp(img, shape(lambda c: rrect(c, CX + 200 * u, CY - 130 * u, 260 * u, 260 * u, 58 * u)), np.clip(col('light') * 0.25 + 0.75, 0, 1))
    comp(img, draw(lambda c: (c.arc(CX + 330 * u, CY, 62 * u, 0, 6.3), c.set_line_width(14 * u), c.stroke())), hexc('#FFFFFF'))
    comp(img, shape(lambda c: c.arc(CX + 330 * u, CY, 22 * u, 0, 6.3)), hexc('#FFFFFF'))
    return img


SCENES = {
    'blank': blank,
    'c1': lambda: construction(1), 'c2': lambda: construction(2), 'c3': lambda: construction(3),
    'c4': lambda: construction(4), 'c5': lambda: construction(5), 'c6': lambda: construction(6),
    'synth': synthesis, 'grid': grid_scene, 'map': value_map, 'lockup': lockup,
    'mark_dark_on_light': lambda: mark_on('background', 'dark'),
    'mark_white_on_black': lambda: mark_on('black', 'white'),
    'mark_primary': lambda: mark_on('background', 'primary'),
    'silver': silver, 'blackglow': black_glow, 'color': color_gradient, 'poster': poster, 'app': app_icons,
}
GRAIN = {'silver', 'blackglow', 'color'}
