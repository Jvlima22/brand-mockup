"""Frame configuration + drawing/compositing helpers shared by all scenes."""
import math
from types import SimpleNamespace

import cairo
import numpy as np
from PIL import Image
from scipy import ndimage

# Output formats. `logo_h` = fixed logo height (px) after the reveal; `cons_h` = logo height in the construction scenes.
FORMATS = {
    '9x16': dict(W=1080, H=1920, logo_h=156, cons_h=340),
    '16x9': dict(W=1920, H=1080, logo_h=109, cons_h=238),
    '1x1': dict(W=1080, H=1080, logo_h=120, cons_h=270),
    '4x5': dict(W=1080, H=1350, logo_h=130, cons_h=290),
}

ctx = SimpleNamespace()


def hexc(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def configure(fmt, colors):
    f = FORMATS[fmt]
    ctx.fmt = fmt
    ctx.W, ctx.H = f['W'], f['H']
    ctx.CX, ctx.CY = f['W'] // 2, f['H'] // 2
    ctx.LOGO_H = f['logo_h']
    ctx.CONS_H = f['cons_h']
    ctx.u = ctx.LOGO_H / 156.0          # design unit: all fixed pixel sizes were tuned at logo_h=156
    ctx.col = {k: hexc(v) for k, v in colors.items()}
    ctx._grid = None


def col(name_or_hex):
    if isinstance(name_or_hex, str) and name_or_hex.startswith('#'):
        return hexc(name_or_hex)
    return ctx.col[name_or_hex]


# ---------------------------------------------------------------- raster helpers
def grid():
    if ctx._grid is None:
        y, x = np.mgrid[0:ctx.H, 0:ctx.W].astype(np.float32)
        ctx._grid = (x, y)
    return ctx._grid


def solid(c):
    img = np.empty((ctx.H, ctx.W, 3), np.float32)
    img[:] = c
    return img


def comp(img, alpha, c):
    a = alpha[..., None]
    c = np.asarray(c, np.float32)
    if c.ndim == 1:
        c = c[None, None, :]
    img[:] = img * (1 - a) + c * a
    return img


def put(img, a, c):
    img[:] = img * (1 - a[..., None]) + c * a[..., None]


def radial(cx, cy, r):
    x, y = grid()
    return np.clip(1 - np.hypot(x - cx, y - cy) / r, 0, 1)


def blob(cx, cy, rx, ry):
    x, y = grid()
    return np.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2) * 2)


def soft_shade(img, cx, cy, rx, ry, strength, c=(0, 0, 0)):
    comp(img, blob(cx, cy, rx, ry) * strength, np.array(c, np.float32))


def rel_shade(img, x, y, rx, ry, strength, c):
    """soft_shade with coordinates given in a 1080x1920 design space, mapped to the current frame."""
    W, H = ctx.W, ctx.H
    soft_shade(img, x * W / 1080, y * H / 1920, rx * W / 1080, ry * H / 1920, strength, c)


def noise(sigma=1.0, amp=1.0, seed=0):
    rng = np.random.default_rng(seed)
    n = rng.standard_normal((ctx.H, ctx.W)).astype(np.float32)
    if sigma > 0:
        n = ndimage.gaussian_filter(n, sigma)
    n /= (n.std() + 1e-6)
    return n * amp


def grain(img, amt=0.01, seed=99):
    img += noise(0, amt, seed)[..., None]
    return img


def fabric(base, amp=0.06, seed=1, diag=False, fine=0.7):
    img = solid(base)
    n = noise(fine, amp, seed)
    if diag:
        x, y = grid()
        n = n * 0.6 + amp * 0.8 * np.sin((x + y) * 0.9)
    img += n[..., None]
    return img


def save(img, path):
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def outline(alpha, width=1.5):
    gy, gx = np.gradient(ndimage.gaussian_filter(alpha, 0.6))
    return np.clip(np.hypot(gx, gy) * (2.2 * width), 0, 1)


# ---------------------------------------------------------------- vector helpers (cairo -> alpha)
def _canvas():
    s = cairo.ImageSurface(cairo.FORMAT_A8, ctx.W, ctx.H)
    return s, cairo.Context(s)


def _to_alpha(surf):
    surf.flush()
    a = np.frombuffer(surf.get_data(), np.uint8).reshape(ctx.H, surf.get_stride())[:, :ctx.W]
    return a.astype(np.float32) / 255


def draw(fn):
    s, c = _canvas()
    c.set_source_rgba(0, 0, 0, 1)
    fn(c)
    return _to_alpha(s)


def shape(fn):
    return draw(lambda c: (fn(c), c.fill()))


def ell_path(c, e):
    cx, cy, rx, ry = e
    c.save(); c.translate(cx, cy); c.scale(rx, ry); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()


def rrect(c, x, y, w, h, r):
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    c.close_path()


def rounded_rect_alpha(cx, cy, hw, hh, r):
    x, y = grid()
    dx = np.maximum(np.abs(x - cx) - (hw - r), 0)
    dy = np.maximum(np.abs(y - cy) - (hh - r), 0)
    return np.clip(r - np.hypot(dx, dy), 0, 1).astype(np.float32)


# ---------------------------------------------------------------- materials
def chrome(alpha, tint_top=None, tint_bot=None, dark=0.06, bright=1.0, cy=None, h=None):
    """Chrome look: bright sky above a sharp horizon, dark ground below, thin edge highlights."""
    cy = ctx.CY if cy is None else cy
    h = ctx.LOGO_H if h is None else h
    m = alpha > 0.5
    d = ndimage.distance_transform_edt(m).astype(np.float32)
    x, y = grid()
    t = (y - (cy - h / 2)) / h + (x - ctx.CX) / (900 * ctx.u)
    hz = 0.52
    sky = 0.95 - 0.5 * np.clip(t / hz, 0, 1) ** 1.5
    ground = 0.06 + 0.55 * np.clip((t - hz) / (1 - hz), 0, 1) ** 1.3
    tone = ndimage.gaussian_filter(np.where(t < hz, sky, ground), 1.0)
    edge = np.exp(-d / (1.3 * max(ctx.u, 0.7)))
    rim = np.exp(-((d - 4.0 * ctx.u) / 1.6) ** 2)
    tone = np.clip(tone * (1 - 0.45 * rim) + 0.8 * edge, 0, 1)
    c = dark + (bright - dark) * tone[..., None] * np.ones(3, np.float32)
    if tint_top is not None:
        k = (np.clip(1 - t / hz, 0, 1) * (1 - edge))[..., None] * 0.6
        c = c * (1 - k) + np.asarray(tint_top) * k * tone[..., None] * 1.2
    if tint_bot is not None:
        k = (np.clip((t - hz) / (1 - hz), 0, 1) * (1 - edge))[..., None] * 0.7
        c = c * (1 - k) + np.asarray(tint_bot) * k
    return np.clip(c, 0, 1)


def bevel(alpha, base, light=(-1, -1.3), depth=6.0, spec=0.6):
    h = ndimage.gaussian_filter(alpha, 2.2) * depth
    gy, gx = np.gradient(h)
    n = np.stack([-gx, -gy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array([light[0], light[1], 1.4], np.float32); L /= np.linalg.norm(L)
    diff = np.clip((n * L).sum(-1), 0, 1)
    c = np.asarray(base)[None, None, :] * (0.55 + 0.6 * diff[..., None])
    c += spec * (diff ** 18)[..., None]
    return np.clip(c, 0, 1)


def shadow(img, alpha, dx=6, dy=10, blur=8, strength=0.35):
    sh = ndimage.shift(ndimage.gaussian_filter(alpha, blur), (dy, dx), order=1)
    img *= (1 - strength * sh[..., None])
    return img


def lum(img):
    return img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
