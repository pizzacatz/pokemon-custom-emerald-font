"""Model solid pixel shapes (the arrows) as filled polygons fitted to their pixels.

usage: python3 scripts/fit_fills.py [variant ...]   (default: all nine fonts)
Each row of the glyph is one run of pixels. Down each side, a one-pixel step from row to row becomes a
straight edge through the pixel centres (the 45-degree slopes of the arrow heads); an unchanged edge stays
vertical; a jump of two or more pixels stays a horizontal step at the row boundary. Where a slope runs past
the glyph's ink box it is cut off at the box. The result is written as a glyph override of one "fill"
polygon, editable in the glyph editor like any other; ported fonts record it as method "fitted", which
port_overrides.py leaves alone."""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import VARIANTS, data_dir

# the big arrows, the text arrows (↑ ↓ ← →, sharing their cells with E079-E07C), the up-down arrow and ▶
SYMBOLS = {0xE100: 'UP_ARROW', 0xE101: 'DOWN_ARROW', 0xE102: 'LEFT_ARROW', 0xE103: 'RIGHT_ARROW',
           0xE079: 'UP_ARROW', 0xE07A: 'DOWN_ARROW', 0xE07B: 'LEFT_ARROW', 0xE07C: 'RIGHT_ARROW',
           0xE038: 'V_D_ARROW', 0x25B6: 'PLAY'}

def runs(mask):
    """{row: (x0, x1)} for the one run of ink in each row (x1 exclusive)."""
    out = {}
    for y, r in enumerate(mask):
        xs = [x for x, c in enumerate(r) if c]
        if xs:
            if xs[-1] - xs[0] + 1 != len(xs):
                raise ValueError(f'row {y} has more than one run of pixels')
            out[y] = (xs[0], xs[-1] + 1)
    return out

def side(rows, xs, lo, hi):
    """Points (top to bottom) of one side of the shape. xs[i] is that side's pixel edge in rows[i]."""
    pts = []
    def clampseg(x0, y0, x1, y1):
        # the line from (x0, y0) to (x1, y1) cut off at the ink box: a slope that runs out of it turns vertical
        if lo <= x1 <= hi:
            return [(x1, y1)]
        b = lo if x1 < lo else hi
        yb = y0 + (y1 - y0) * (b - x0) / (x1 - x0)
        return [(b, yb), (b, y1)]
    n = len(rows)
    for i, (y, x) in enumerate(zip(rows, xs)):
        dprev = x - xs[i-1] if i and rows[i-1] == y - 1 else None
        dnext = xs[i+1] - x if i + 1 < n and rows[i+1] == y + 1 else None
        if dprev is None or abs(dprev) >= 2:
            # this row starts a run: begin at its top edge, continuing the slope up to it if there is one
            if dnext is not None and abs(dnext) == 1:
                pts += clampseg(x, y + 0.5, x - dnext * 0.5, y)[::-1]
            else:
                pts.append((x, y))
        if (dprev is not None and abs(dprev) == 1) or (dnext is not None and abs(dnext) == 1):
            pts.append((x, y + 0.5))
        if dnext is None or abs(dnext) >= 2:
            # this row ends a run: finish at its bottom edge, continuing the slope down to it if there is one
            if dprev is not None and abs(dprev) == 1:
                pts += clampseg(x, y + 0.5, x + dprev * 0.5, y + 1)
            else:
                pts.append((x, y + 1))
    return pts

def fit(mask):
    r = runs(mask)
    rows = sorted(r)
    lo = min(a for a, _ in r.values()); hi = max(b for _, b in r.values())
    left = side(rows, [r[y][0] for y in rows], lo, hi)
    right = side(rows, [r[y][1] for y in rows], lo, hi)
    poly = left + right[::-1]
    out = []
    for p in poly:
        p = (round(p[0], 4), round(p[1], 4))
        if not out or p != out[-1]:
            out.append(p)
    if out[0] == out[-1]:
        out.pop()
    # drop points in the middle of a straight edge
    i = 0
    while i < len(out) and len(out) > 3:
        a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
        if abs((b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])) < 1e-9:
            out.pop(i)
        else:
            i += 1
    return [[int(x) if x == int(x) else x, int(y) if y == int(y) else y] for x, y in out]

def main():
    for v in sys.argv[1:] or list(VARIANTS):
        d = data_dir(v)
        mp = json.load(open(os.path.join(d, 'mapping.json'))); cps = json.load(open(os.path.join(d, 'codepoints.json')))
        rp = os.path.join(d, 'port_report.json')
        rep = json.load(open(rp)) if v != 'normal' and os.path.exists(rp) else None
        for cp in SYMBOLS:
            gid = next((k for k, e in mp.items() if cp in e['unicode']), None) or \
                  next((k for k, e in cps.items() if cp in e['codepoints']), None)
            if gid is None:
                continue
            mask = json.load(open(os.path.join(d, 'masks', f'{int(gid):03d}.json')))['fg']
            if not any(map(any, mask)):
                continue
            aliases = [cp] + [c for c in (mp.get(gid, {}).get('unicode', []) + cps.get(gid, {}).get('codepoints', [])) if c != cp]
            name = f'u{cp:04X}'
            spec = {'char': [chr(c) for c in dict.fromkeys(aliases)] if len(set(aliases)) > 1 else chr(cp), 'rows': [0, 16], 'width': 1, 'joint_radius': 1,
                    'strokes': [{'fill': fit(mask)}], 'dots': [], 'join': 'miter',
                    '_ported': 'filled polygon fitted to the pixels by fit_fills.py'}
            with open(os.path.join(d, 'glyph_overrides', name + '.json'), 'w', encoding='utf-8') as f:
                json.dump(spec, f, indent=1, ensure_ascii=False)
            if rep is not None:
                rep[name] = {'char': spec['char'], 'method': 'fitted', 'from': None, 'note': 'fit_fills.py'}
        if rep is not None:
            json.dump(rep, open(rp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print(v, 'fitted:', ''.join(chr(c) if c < 0xE000 else f'[{c:X}]' for c in SYMBOLS))

if __name__ == '__main__':
    main()
