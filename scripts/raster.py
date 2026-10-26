"""Quick numpy rasteriser for the smooth stroke models, used to score a glyph model against its pixel mask
without a FontForge build. Strokes get butt ends (smooth.extend_caps already adds the square caps) and
their join (miter by default, cut to a bevel past 4 stroke widths as in build_font.py; bevel; round); dots
and cut masks as in build_font.py. Accurate to a few hundredths of a pixel, which is
plenty for ranking candidate models and for review sheets.

coverage(strokes, dots, cuts) -> 16x16 float array (0..1 ink coverage per source pixel)
score(cov, mask) -> dict(err=sum |cov - mask|, missing=#ink pixels under half covered, extra=#blank pixels over half covered)
"""
import numpy as np

SS = 8                                   # subsamples per pixel per axis
_g = (np.arange(16*SS) + 0.5) / SS
GX, GY = np.meshgrid(_g, _g)             # sample positions in pixel coords, y down

def _bez_points(b, n=8):
    (p0, c1, c2, p3) = [np.array(p, float) for p in b]
    t = np.linspace(0, 1, n+1)[:, None]
    return (1-t)**3*p0 + 3*(1-t)**2*t*c1 + 3*(1-t)*t**2*c2 + t**3*p3

def _stroke_mask(s, default_w=1.0):
    if 'fill' in s:
        return _poly_mask(s['fill'])
    w = s.get('width', default_w); h2 = (w/2)**2
    pts = [_bez_points(b) for b in s['beziers']]
    if not pts:
        return np.zeros(GX.shape, bool)
    P = np.vstack([pts[0]] + [p[1:] for p in pts[1:]])
    out = np.zeros(GX.shape, bool)
    for (ax, ay), (bx, by) in zip(P[:-1], P[1:]):
        dx, dy = bx-ax, by-ay; L2 = dx*dx + dy*dy
        if L2 < 1e-12:
            continue
        t = ((GX-ax)*dx + (GY-ay)*dy) / L2
        d2 = (GX-ax-t*dx)**2 + (GY-ay-t*dy)**2
        out |= (t >= 0) & (t <= 1) & (d2 <= h2)
    n = len(P)
    idx = range(n) if s['closed'] else range(1, n-1)
    join = s.get('join', 'miter')
    for i in idx:
        x, y = P[i]
        if join == 'round':
            out |= (GX-x)**2 + (GY-y)**2 <= h2
            continue
        a, b = P[i-1], P[(i+1) % n]
        u, v = np.array([x, y]) - a, b - np.array([x, y])
        lu, lv = np.hypot(*u), np.hypot(*v)
        if lu < 1e-9 or lv < 1e-9:
            continue
        u, v = u/lu, v/lv
        cross = u[0]*v[1] - u[1]*v[0]
        if abs(cross) < 1e-6:
            continue                      # straight on: nothing to fill
        side = -1 if cross > 0 else 1     # the outer side of the turn
        h = w/2
        n1 = side*np.array([-u[1], u[0]]); n2 = side*np.array([-v[1], v[0]])
        p1, p2 = (x + n1[0]*h, y + n1[1]*h), (x + n2[0]*h, y + n2[1]*h)
        poly = [(x, y), p1, p2]
        if join == 'miter':
            m = n1 + n2; c = np.dot(m/np.hypot(*m), n1)          # cos of half the turn
            if c > 1e-6 and 1/c <= 4:                            # within the miter limit
                tip = (x + m[0]/np.hypot(*m)*h/c, y + m[1]/np.hypot(*m)*h/c)
                poly = [(x, y), p1, tip, p2]
        out |= _poly_mask(poly)
    return out

def _poly_mask(poly):
    inside = np.zeros(GX.shape, bool)
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i][:2], poly[(i+1) % n][:2]
        if y0 == y1:
            continue
        cond = (GY >= min(y0, y1)) & (GY < max(y0, y1))
        xi = x0 + (GY-y0)*(x1-x0)/(y1-y0)
        inside ^= cond & (GX < xi)
    return inside

def coverage(strokes, dots, cuts, default_w=1.0):
    ink = np.zeros(GX.shape, bool)
    for s in strokes:
        ink |= _stroke_mask(s, default_w)
    for d in dots:
        if d['shape'] == 'circle':
            ink |= (GX-d['x'])**2 + (GY-d['y'])**2 <= d['r']**2
        else:
            ink |= (abs(GX-d['x']) <= d['r']) & (abs(GY-d['y']) <= d['r'])
    for poly in cuts:
        ink &= ~_poly_mask(poly)
    return ink.reshape(16, SS, 16, SS).mean(axis=(1, 3))

def score(cov, mask):
    m = np.array(mask, float)
    return {'err': round(float(abs(cov-m).sum()), 3),
            'missing': int(((m == 1) & (cov < 0.5)).sum()),
            'extra': int(((m == 0) & (cov > 0.5)).sum())}
