"""Logo from SVG: rasterised once at high resolution, then placed at any centre/height as an alpha mask."""
import io

import cairosvg
import numpy as np
from PIL import Image
from scipy import ndimage

from .core import ctx

_master = None      # cropped high-res alpha (float32), bbox of the drawn content
_aspect = 1.0
_cache = {}
MASTER_H = 2400


def load(svg_path):
    global _master, _aspect
    png = cairosvg.svg2png(url=str(svg_path), output_height=MASTER_H)
    a = np.asarray(Image.open(io.BytesIO(png)).convert('RGBA'))[..., 3].astype(np.float32) / 255
    ys, xs = np.where(a > 0.02)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    _master = a
    _aspect = a.shape[1] / a.shape[0]
    _cache.clear()


def aspect():
    return _aspect


def alpha(cx=None, cy=None, h=None):
    """Alpha mask (frame-sized) with the logo's bbox centred on (cx, cy) and height h px."""
    cx = ctx.CX if cx is None else cx
    cy = ctx.CY if cy is None else cy
    h = ctx.LOGO_H if h is None else h
    key = (ctx.W, ctx.H, round(cx, 2), round(cy, 2), round(h, 2))
    if key in _cache:
        return _cache[key]
    w = h * _aspect
    # resample master into the frame with an affine map (sub-pixel exact placement)
    sy = _master.shape[0] / h
    sx = _master.shape[1] / w
    src = _master
    if sy > 1.5:  # prefilter to avoid aliasing when shrinking
        src = ndimage.gaussian_filter(_master, sigma=0.45 * sy)
    out = ndimage.affine_transform(
        src, np.array([sy, sx]),
        offset=(-(cy - h / 2) * sy, -(cx - w / 2) * sx),
        output_shape=(ctx.H, ctx.W), order=1, mode='constant', cval=0.0)
    out = np.clip(out, 0, 1).astype(np.float32)
    _cache[key] = out
    return out


def to_px(nx, ny, cx=None, cy=None, h=None):
    """Map logo-normalised coords (origin = bbox top-left, unit = bbox height) to frame pixels."""
    cx = ctx.CX if cx is None else cx
    cy = ctx.CY if cy is None else cy
    h = ctx.LOGO_H if h is None else h
    return cx - h * _aspect / 2 + nx * h, cy - h / 2 + ny * h
