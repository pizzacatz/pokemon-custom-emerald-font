"""Make ported and traced glyph models symmetric, and give Small Narrower its hand-drawn arc style.

usage: python3 scripts/tidy_arcs.py [variant ...]   (default: all fonts but Normal)
Leaves alone Normal (hand-made throughout), models marked "hand" in port_report.json (hand-modelled, or
saved from the glyph editor) and "fitted" ones (fit_circles.py, fit_fills.py).

centre: the flat top or bottom of a bowl, between two corner arcs, is centred between the arcs' far ends,
  running between the centres of the end pixels of its row's ink run (a 1-pixel run gets a 0.5 px flat
  around its centre). Porting leaves some off by half a pixel (Narrower's O ran 1.0..1.5 over column 1).
  A flat whose pixels are themselves off centre (a J's tail) is left as it is.
inset (Small Narrower, after its hand-edited letters): every corner arc from a stem to the next column
  (0.5 to 1 px across, as ported or traced) is made 0.75 px across, its horizontal end 0.25 px short of
  the pixel centre; where two arcs met at a point (the top of a 3 px bowl), a 0.5 px flat now joins them.
  smooth.py does the same to Small Narrower's traced glyphs.
"""
import os, sys, json, copy
sys.path.insert(0, os.path.dirname(__file__))
from common import VARIANTS, data_dir

ARC = 0.3033
INSET = {'small_narrower': 0.75}    # fonts drawn with inset arcs: how far across a corner arc reaches

def _bulge(p):
    return p[3] if len(p) > 3 and p[3] is not None else 0

def _is_arc(p, q):
    """A corner arc over one diagonal pixel step (0.5 to 1 px each way), from p to q."""
    dx, dy = abs(q[0] - p[0]), abs(q[1] - p[1])
    return abs(abs(_bulge(p)) - ARC) < 1e-3 and 0.49 < dx < 1.01 and 0.49 < dy < 1.01

def inset_points(P, closed, d):
    """P with every one-step arc's horizontal end d across from its vertical end (see the docstring)."""
    dup = not closed and len(P) > 2 and P[0][:2] == P[-1][:2]
    Q = [list(p) for p in (P[:-1] if dup else P)]
    n = len(Q); loop = closed or dup
    want_in, want_out = [None]*n, [None]*n           # x wanted by the arc ending / starting at each point
    for i in range(n if loop else n - 1):
        p, q = Q[i], Q[(i + 1) % n]
        if not _is_arc(p, q):
            continue
        dx, dy = q[0] - p[0], q[1] - p[1]
        if dx * dy * _bulge(p) < 0:                  # the arc leaves p horizontally
            want_out[i] = q[0] - d * (1 if dx > 0 else -1)
        else:                                        # it arrives at q horizontally
            want_in[(i + 1) % n] = p[0] + d * (1 if dx > 0 else -1)
    out = []
    for i, p in enumerate(Q):
        a, b = want_in[i], want_out[i]
        if a is not None and b is not None and abs(a - b) > 1e-9:
            # two arcs met at this point: a flat between them, straight (no bulge) from a to b
            out.append([a, p[1]] + ([p[2], 0] if len(p) > 2 else [None, 0]))
            out.append([b] + p[1:])
        else:
            x = a if a is not None else b
            out.append(([x] + p[1:]) if x is not None else p)
    if dup:
        out.append(list(out[0][:2]) + ([out[0][2]] if len(out[0]) > 2 else []))
    return out

def _start_mid_side(Q):
    """The closed loop Q started halfway along its longest straight side: a loop's start joint is mitred
    from the closing segment, which goes wrong against an arc that is not a 45 degree step."""
    n = len(Q)
    straight = [i for i in range(n) if abs(_bulge(Q[i])) < 1e-3]
    if not straight:
        return Q
    L = lambda i: abs(Q[(i + 1) % n][0] - Q[i][0]) + abs(Q[(i + 1) % n][1] - Q[i][1])
    i = max(straight, key=L)
    p, q = Q[i], Q[(i + 1) % n]
    mid = [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2] + ([p[2], 0] if len(p) > 2 else [])
    return [mid] + Q[i + 1:] + Q[:i + 1]

def flats(P, closed):
    """(i, j, a, b): points i..j lie on one row, an arc arrives at i from a and leaves j for b, a and b on
    the same side of the row (a bowl's top or bottom) and on either side of the flat."""
    n = len(P)
    loop = closed or (n > 2 and P[0][:2] == P[-1][:2])
    if loop and P[0][:2] == P[-1][:2]:
        n -= 1
    for i in (range(n) if loop else range(1, n - 1)):
        a = P[(i - 1) % n]
        if abs(abs(_bulge(a)) - ARC) > 1e-3:
            continue
        j = i
        while (loop or j + 1 < n - 1) and j - i < n and P[(j + 1) % n][1] == P[i][1] and abs(_bulge(P[j % n])) < 1e-3:
            j += 1
        pj = P[j % n]
        if abs(abs(_bulge(pj)) - ARC) > 1e-3 or not (loop or j + 1 < n):
            continue
        b = P[(j + 1) % n]
        y = P[i][1]
        if (a[1] - y) * (b[1] - y) <= 0 or (y % 1) != 0.5:
            continue
        lo, hi = sorted([a[0], b[0]])
        if lo < min(P[i][0], pj[0]) and max(P[i][0], pj[0]) < hi:
            yield i, j % n, a, b

def centre_flats(spec, mask):
    """Centre each bowl's flat (see the docstring). Returns the number of flats moved."""
    moved = 0
    for st in spec['strokes']:
        P = st.get('points')
        if not P:
            continue
        for i, j, a, b in list(flats(P, st.get('closed', False))):
            if i == j:
                continue                              # arcs meeting at a point: nothing to slide
            f0, f1 = P[i][0], P[j][0]
            want = (a[0] + b[0]) / 2
            if abs((f0 + f1) / 2 - want) < 0.05:
                continue
            row = mask[int(P[i][1])]
            c = int((f0 + f1) / 2)
            if not row[c]:
                continue
            l, r = c, c
            while l > 0 and row[l - 1]: l -= 1
            while r < len(row) - 1 and row[r + 1]: r += 1
            lo, hi = (l + 0.5, r + 0.5) if r > l else (l + 0.25, l + 0.75)
            if abs((lo + hi) / 2 - want) > 0.05:
                continue                              # the pixels themselves are off centre
            x0, x1 = (lo, hi) if f0 < f1 else (hi, lo)
            P[i][0], P[j][0] = x0, x1
            if P[0][:2] == P[-1][:2] and not st.get('closed'):
                P[-1][0] = P[0][0]
            moved += 1
    return moved

def inset_spec(spec, d):
    for st in spec['strokes']:
        if st.get('points'):
            st['points'] = inset_points(st['points'], st.get('closed', False), d)
    return spec

def main():
    from port_overrides import gid_for, mask_of, model_score
    for v in sys.argv[1:] or [v for v in VARIANTS if v != 'normal']:
        d = data_dir(v); od = os.path.join(d, 'glyph_overrides')
        rep = json.load(open(os.path.join(d, 'port_report.json')))
        done = []
        for fn in sorted(os.listdir(od)):
            if not fn.endswith('.json') or fn.startswith('_'):
                continue
            name = fn[:-5]
            if rep.get(name, {}).get('method') in ('hand', 'fitted'):
                continue
            spec = json.load(open(os.path.join(od, fn), encoding='utf-8'))
            ch = spec['char'] if isinstance(spec['char'], str) else spec['char'][0]
            if ch == '&':
                continue                              # its crossing is a sharp point, not a bowl
            gid = gid_for(v, ch)
            if gid is None:
                continue
            mask = mask_of(v, gid)
            new = copy.deepcopy(spec)
            n = centre_flats(new, mask)
            if v in INSET:
                inset_spec(new, INSET[v])
            for st, old in zip(new['strokes'], spec['strokes']):
                if st.get('closed') and st.get('points') and st['points'] != old.get('points'):
                    st['points'] = _start_mid_side(st['points'])
            if new['strokes'] == spec['strokes']:
                continue
            before, after = model_score(spec, mask, ch), model_score(new, mask, ch)
            if after['missing'] > before['missing']:
                print(f'  {v} {ch}: skipped, would miss {after["missing"]} px')
                continue
            new['_ported'] = spec.get('_ported', '') + '; tidied by tidy_arcs.py'
            with open(os.path.join(od, fn), 'w', encoding='utf-8') as f:
                json.dump(new, f, indent=1, ensure_ascii=False)
            if name in rep:
                rep[name].update(after)
            done.append(ch + (f'({n})' if n else ''))
        json.dump(rep, open(os.path.join(d, 'port_report.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print(v, 'tidied:', ' '.join(done) or '-')

if __name__ == '__main__':
    main()
