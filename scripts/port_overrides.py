"""Port the hand-tuned glyph overrides of one font to another game font (Narrow, Small, Short, Small Narrow).

usage: python3 scripts/port_overrides.py <variant> [--force | --replace] [chars]
       --force re-ports glyphs that already have a file, except those marked "hand" (hand-modelled, or saved
       from the glyph editor); --replace re-ports those too (the editor's "Re-port from Normal" button).
       Sources are Normal plus the already-ported fonts listed in SOURCES.

Every override of a source font is carried over to the target font in one of three ways:

  transfer  The target bitmap is the source bitmap with whole pixel columns/rows deleted or doubled
            (Narrow "O" is Normal "O" minus its middle column). The source model is remapped with a
            piecewise-linear map that keeps every other pixel's centre and edges, so the strokes, the
            67.5 degree corner arcs, the cuts and clips all survive unchanged.
  fuzzy     The closest such mapping still differs by a few pixels; the remapped model is used if it
            scores better than a fresh trace.
  traced    A fresh model in the same convention: straight strokes through pixel centres, a 67.5 degree
            arc (bulge 0.3033) wherever a stroke turns through a single diagonal pixel step, sharp joints,
            separate strokes at right-angle corners. See trace().

Files are written to <data>/glyph_overrides/ (existing files are kept unless --force, and glyphs marked
"hand" in the report are always kept), with a "_ported"
note saying where each came from, and <data>/port_report.json lists method and score per glyph.
Score = sum over the 16x16 cell of |ink coverage - pixel| (raster.py); the hand-tuned Normal glyphs
have a median of about 2.5.
"""
import os, sys, json, math, itertools, copy
sys.path.insert(0, os.path.dirname(__file__))
from common import *
import smooth, raster

ARC = 0.3033          # tan(67.5deg / 4): the bulge of every hand-drawn corner arc
SOURCES = {'narrow': ['normal'], 'short': ['normal'], 'small': ['normal', 'narrow'],
           'small_narrow': ['small', 'narrow', 'normal'],
           # pokeemerald-expansion's fonts, ported from the font each one narrows (port them in this order)
           'narrower': ['narrow', 'normal'], 'short_narrow': ['short', 'narrow', 'normal'],
           'short_narrower': ['short_narrow', 'short', 'narrower', 'narrow', 'normal'],
           'small_narrower': ['small_narrow', 'small', 'narrower', 'narrow', 'normal']}
PREFER_TRANSFER = 1.0  # a fuzzy transfer wins unless a fresh trace scores this much better

def overrides_of(variant):
    d = os.path.join(data_dir(variant), 'glyph_overrides')
    out = {}
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.json') and not fn.startswith('_'):
                spec = json.load(open(os.path.join(d, fn), encoding='utf-8'))
                out[fn[:-5]] = spec
    return out

def chars_of(spec):
    return [spec['char']] if isinstance(spec['char'], str) else list(spec['char'])

def gid_for(variant, ch):
    cps = json.load(open(os.path.join(data_dir(variant), 'codepoints.json')))
    mp = json.load(open(os.path.join(data_dir(variant), 'mapping.json')))
    cp = ord(ch)
    return next((int(k) for k, e in mp.items() if cp in e['unicode']), None) or \
           next((int(k) for k, v in cps.items() if cp in v['codepoints']), None)

def mask_of(variant, gid):
    return json.load(open(os.path.join(data_dir(variant), 'masks', f'{gid:03d}.json')))['fg']

def ink_box(m):
    ys = [y for y in range(16) if any(m[y])]
    xs = [x for x in range(16) if any(m[y][x] for y in range(16))]
    return (ys[0], ys[-1]+1, xs[0], xs[-1]+1) if ys else None

# ---------------------------------------------------------------- transfer
def index_maps(m, n):
    """All ways to turn m source rows into n target rows by deleting or doubling whole rows.
    Yields tuples s where target row j shows source row s[j]."""
    if m >= n:
        for dele in itertools.combinations(range(m), m-n):
            yield tuple(i for i in range(m) if i not in dele)
    else:
        for dup in itertools.combinations_with_replacement(range(m), n-m):
            yield tuple(i for i in range(m) for _ in range(1 + dup.count(i)))

def axis_knots(smap, s0, t0, m):
    """Piecewise-linear knots (source coord -> target coord) for one axis of an ink box of m source pixels.
    Kept source pixels map their two edges and centre onto the target pixel(s) showing them; a deleted pixel
    collapses onto the edge between its neighbours (or onto the box edge at either end); a doubled one
    stretches over both target pixels."""
    byrc = {}
    for j, s in enumerate(smap):
        byrc.setdefault(s, []).append(j)
    k = []
    if smap[0] > 0:
        k.append((s0, t0))
    for s, js in sorted(byrc.items()):
        a, b = t0 + min(js), t0 + max(js) + 1
        k += [(s0+s, a), (s0+s+0.5, (a+b)/2), (s0+s+1, b)]
    if smap[-1] < m-1:
        k.append((s0+m, t0+len(smap)))
    return k

def interp(knots, v):
    xs = [a for a, _ in knots]; ys = [b for _, b in knots]
    if v <= xs[0]:
        return ys[0] + (v - xs[0])
    if v >= xs[-1]:
        return ys[-1] + (v - xs[-1])
    for i in range(len(xs)-1):
        if xs[i] <= v <= xs[i+1]:
            if xs[i+1] - xs[i] < 1e-12:
                return ys[i+1]
            t = (v - xs[i]) / (xs[i+1] - xs[i])
            return ys[i] + t*(ys[i+1] - ys[i])

def spec_points(spec):
    """Every (x, y) the model is drawn through, for counting how much of it a mapping squashes."""
    for st in spec.get('strokes', []):
        for p in st.get('points', []):
            yield p[0], p[1]
        if 'arc' in st:
            yield tuple(st['arc']['center'])
        if 'circle' in st:
            yield tuple(st['circle']['center'])
    for d in spec.get('dots', []):
        d = smooth.norm_dot(d)
        yield d['x'], d['y']

def squash_penalty(spec, knots_x, knots_y):
    """Number of model points that land inside a deleted or doubled pixel (where the map is not a plain shift)."""
    def off(knots, v):
        for (a0, b0), (a1, b1) in zip(knots, knots[1:]):
            if a0 <= v <= a1 and a1 > a0 and abs((b1-b0)/(a1-a0) - 1) > 1e-6:
                return True
        return False
    return sum(off(knots_x, x) or off(knots_y, y) for x, y in spec_points(spec))

def best_mapping(S, T, spec):
    """Search row and column maps from source mask S to target mask T. Returns
    (mismatched pixels, squash penalty, edits, knots_x, knots_y) of the best one, or None."""
    bs, bt = ink_box(S), ink_box(T)
    if not bs or not bt:
        return None
    best = None
    rows = list(index_maps(bs[1]-bs[0], bt[1]-bt[0]))
    cols = list(index_maps(bs[3]-bs[2], bt[3]-bt[2]))
    if len(rows)*len(cols) > 20000:
        return None
    for rm in rows:
        src_rows = [S[bs[0]+r] for r in rm]
        for cm in cols:
            mis = sum(T[bt[0]+j][bt[2]+i] != src_rows[j][bs[2]+c] for j in range(len(rm)) for i, c in enumerate(cm))
            mis += sum(T[y][x] for y in range(16) for x in range(16)
                       if not (bt[0] <= y < bt[1] and bt[2] <= x < bt[3]))
            if best and mis > best[0]:
                continue
            kx, ky = axis_knots(cm, bs[2], bt[2], bs[3]-bs[2]), axis_knots(rm, bs[0], bt[0], bs[1]-bs[0])
            pen = squash_penalty(spec, kx, ky)
            edits = abs((bs[3]-bs[2]) - len(cm)) + abs((bs[1]-bs[0]) - len(rm))
            key = (mis, pen, edits)
            if best is None or key < best[:3]:
                best = (mis, pen, edits, kx, ky)
    return best

def remap_spec(spec, kx, ky):
    fx = lambda v: round(interp(kx, v), 4)
    fy = lambda v: round(interp(ky, v), 4)
    out = copy.deepcopy(spec)
    def area(poly):
        return abs(sum(a[0]*b[1] - b[0]*a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2
    for st in out.get('strokes', []):
        if 'points' in st:
            st['points'] = [[fx(p[0]), fy(p[1])] + list(p[2:]) for p in st['points']]
        if 'cut' in st:
            st['cut'] = [[fx(p[0]), fy(p[1])] for p in st['cut']]
            if area(st['cut']) < 0.01:          # squashed flat by a deleted row/column: nothing left to cut
                del st['cut']
        if 'arc' in st:
            st['arc']['center'] = [fx(st['arc']['center'][0]), fy(st['arc']['center'][1])]
        if 'circle' in st:
            st['circle']['center'] = [fx(st['circle']['center'][0]), fy(st['circle']['center'][1])]
    out['strokes'] = [st for st in out.get('strokes', []) if st]
    dots = []
    for d in out.get('dots', []):
        # map the dot's box, not just its centre: a dot over a deleted column or row shrinks with it
        n = smooth.norm_dot(d, out.get('dot_shape', 'circle'), out.get('dot_corner', 0.25))
        x0, x1 = fx(n['x'] - n['r']), fx(n['x'] + n['r'])
        y0, y1 = fy(n['y'] - n['r']), fy(n['y'] + n['r'])
        r = round(max(min(n['r'], 0.5), min(x1 - x0, y1 - y0) / 2), 4)   # never below one pixel
        x, y = round((x0 + x1) / 2, 4), round((y0 + y1) / 2, 4)
        x, y, r = [int(v) if v == int(v) else v for v in (x, y, r)]
        d = dict(d, x=x, y=y, r=r) if isinstance(d, dict) else [x, y, r] + list(d[3:])
        dots.append(d)
    out['dots'] = dots
    if out.get('clip_x'):
        out['clip_x'] = [fx(v) for v in out['clip_x']]
    if out.get('clip_y'):
        out['clip_y'] = [fy(v) for v in out['clip_y']]
    if out.get('rows'):
        r0, r1 = out['rows']
        out['rows'] = [max(0, min(16, round(interp(ky, r0)))), max(0, min(16, round(interp(ky, r1))))]
        if out['rows'] == [0, 16] or spec['rows'] == [0, 16]:
            out['rows'] = [0, 16]
    return out

# ---------------------------------------------------------------- convention tracer
def run_len(pix, p, d):
    n = 1
    for s in (1, -1):
        q = (p[0] + s*d[0], p[1] + s*d[1])
        while q in pix:
            n += 1; q = (q[0] + s*d[0], q[1] + s*d[1])
    return n

def build_graph(mask):
    """Pixel graph like smooth.build_graph, but two-pixel-thick parts made of parallel strokes (Narrow "m":
    a stem right next to a stem) are split into their strokes instead of being merged into a blob."""
    pix = {(x, y) for y in range(16) for x in range(16) if mask[y][x]}
    adj = {p: set() for p in pix}
    def in_block(p, q, perp):
        return any((p[0]+s*perp[0], p[1]+s*perp[1]) in pix and (q[0]+s*perp[0], q[1]+s*perp[1]) in pix for s in (1, -1))
    for (x, y) in pix:
        for d, perp in (((1, 0), (0, 1)), ((0, 1), (1, 0))):
            q = (x+d[0], y+d[1])
            if q not in pix:
                continue
            # a rung between two parallel runs of >= 3 px: not part of either stroke
            if in_block((x, y), q, perp) and run_len(pix, (x, y), perp) >= 3 and run_len(pix, q, perp) >= 3:
                continue
            adj[(x, y)].add(q); adj[q].add((x, y))
    for (x, y) in pix:
        for dx, dy in ((1, 1), (-1, 1)):
            q = (x+dx, y+dy)
            if q in pix and (x+dx, y) not in pix and (x, y+dy) not in pix:
                adj[(x, y)].add(q); adj[q].add((x, y))
    return pix, adj

def unit_diag(a, b):
    return abs(b[0]-a[0]) == 1 and abs(b[1]-a[1]) == 1

def axis(a, b):
    return a[0] == b[0] or a[1] == b[1]

def cross(u, v):
    return u[0]*v[1] - u[1]*v[0]

def sgn(v):
    return (v > 0) - (v < 0)

def split_runs(chain, closed):
    """Split at turns of 90 degrees or more, except the apex of two single diagonal steps (the top of an
    arch like Narrow "m"), which becomes a pair of corner arcs."""
    n = len(chain)
    def corner(i):
        a, b, c = chain[i-1], chain[i], chain[(i+1) % n]
        d1, d2 = (b[0]-a[0], b[1]-a[1]), (c[0]-b[0], c[1]-b[1])
        if d1[0]*d2[0] + d1[1]*d2[1] > 0:
            return False
        return not (unit_diag(a, b) and unit_diag(b, c))
    if closed:
        cs = [i for i in range(n) if corner(i)]
        if not cs:
            return [(chain, True)]
        runs = []
        for k in range(len(cs)):
            i, j = cs[k], cs[(k+1) % len(cs)]
            run, t = [chain[i]], i
            while t != j:
                t = (t+1) % n; run.append(chain[t])
            runs.append((run, False))
        return runs
    runs, cur = [], [chain[0]]
    for i in range(1, n-1):
        cur.append(chain[i])
        if corner(i):
            runs.append((cur, False)); cur = [chain[i]]
    cur.append(chain[-1]); runs.append((cur, False))
    return runs

def end_cut(p, s):
    """Cut box beyond the pixel edge p in direction s: trims the square cap of a half-pixel terminal stub
    so the stroke ends flush with the pixel, as on the hand-made C, S, J."""
    (x, y), (sx, sy) = p, s
    px_, py_ = -sy, sx
    a, b = (x + px_*0.6, y + py_*0.6), (x - px_*0.6, y - py_*0.6)
    return [[a[0], a[1]], [b[0], b[1]], [b[0] + sx, b[1] + sy], [a[0] + sx, a[1] + sy]]

def convention_points(pts, closed, pix=frozenset(), terminals=frozenset()):
    """Pixel-index polyline -> (override points [x, y, radius, bulge] at pixel centres, cut boxes).
    pix: the glyph's ink pixels; terminals: pixels where a stroke really ends (not a junction). Only a
    terminal ending in a corner arc gets a half-pixel stub, trimmed when the pixel beyond it is blank."""
    pts = smooth.straighten_zigzags(pts, closed) if not closed else smooth.merge_collinear(pts, True)
    n = len(pts)
    segs = n if closed else n-1
    seg = lambda i: (pts[i % n], pts[(i+1) % n])
    vec = lambda i: (seg(i)[1][0]-seg(i)[0][0], seg(i)[1][1]-seg(i)[0][1])
    bulge = {}
    stub_start = stub_end = None
    for i in range(segs):
        a, b = seg(i)
        if not unit_diag(a, b):
            continue
        prv = i-1 if (closed or i > 0) else None
        nxt = i+1 if (closed or i < segs-1) else None
        turns = []
        ok = True
        for j, first in ((prv, True), (nxt, False)):
            if j is None:
                continue
            u, v = (vec(j), vec(i)) if first else (vec(i), vec(j))
            pa, pb = seg(j)
            if not (axis(pa, pb) or unit_diag(pa, pb)):
                ok = False
            turns.append(sgn(cross(u, v)))
        if not ok or not turns or 0 in turns or len(set(turns)) > 1:
            continue
        if not any(axis(*seg(j)) for j in (prv, nxt) if j is not None):
            continue
        bulge[i] = -ARC * turns[0]          # y-down: a positive cross product turns clockwise on the page
        d = vec(i)
        if prv is None and nxt is not None and axis(*seg(nxt)) and pts[0] in terminals:
            u = vec(nxt)                    # stub before the arc, along the axis the arc leaves
            stub_start = (d[0] if u[0] == 0 else 0, d[1] if u[1] == 0 else 0)
        if nxt is None and prv is not None and axis(*seg(prv)) and pts[-1] in terminals:
            u = vec(prv)
            stub_end = (d[0] if u[0] == 0 else 0, d[1] if u[1] == 0 else 0)
    out = []
    for i, (x, y) in enumerate(pts):
        p = [x+0.5, y+0.5, 0]
        if i in bulge:
            p = [x+0.5, y+0.5, None, bulge[i]]
        out.append(p)
    cuts = []
    if stub_start:
        x, y = pts[0]
        out.insert(0, [out[0][0] - stub_start[0]*0.5, out[0][1] - stub_start[1]*0.5, 0])
        if (x - stub_start[0], y - stub_start[1]) not in pix:
            cuts.append(end_cut(out[0][:2], (-stub_start[0], -stub_start[1])))
    if stub_end:
        x, y = pts[-1]
        out.append([out[-1][0] + stub_end[0]*0.5, out[-1][1] + stub_end[1]*0.5, 0])
        if (x + stub_end[0], y + stub_end[1]) not in pix:
            cuts.append(end_cut(out[-1][:2], stub_end))
    return out, cuts

def trace(mask, ch):
    pix, adj = build_graph(mask)
    allpix = frozenset(pix)
    dots, strokes = [], []
    # isolated 2x2 blocks (periods, colons) become square dots, single pixels round ones
    for (x, y) in sorted(pix):
        blk = {(x, y), (x+1, y), (x, y+1), (x+1, y+1)}
        if blk <= pix and all(adj[p] <= blk for p in blk):
            dots.append({'x': x+1, 'y': y+1, 'r': 1, 'shape': 'square'})
            pix -= blk
            for p in blk:
                adj.pop(p)
    chains, singles = smooth.chains_from_graph(set(adj), adj)
    terminals = frozenset(p for p in adj if len(adj[p]) == 1)
    for x, y in singles:
        dots.append({'x': x+0.5, 'y': y+0.5, 'r': 0.5})
    for chain, closed in chains:
        for run, rclosed in split_runs(chain, closed):
            pts, cuts = convention_points(run, rclosed, allpix, terminals)
            if len(pts) >= 2:
                strokes.append({'points': pts, **({'closed': True} if rclosed else {})})
                strokes += [{'cut': c} for c in cuts]
    return {'char': ch, 'rows': [0, 16], 'width': 1, 'joint_radius': 1, 'strokes': strokes, 'dots': dots,
            'join': 'miter', 'dot_shape': 'circle', 'dot_corner': 0.25}

# ---------------------------------------------------------------- scoring + main
def model_score(spec, mask, ch):
    saved = smooth.JSON_OVERRIDES
    smooth.JSON_OVERRIDES = {ch: spec}
    try:
        st, dots, cuts = smooth.smooth_glyph(mask, ch)
    finally:
        smooth.JSON_OVERRIDES = saved
    smooth.extend_caps(st)
    return raster.score(raster.coverage(st, dots, cuts, spec.get('width', 1.0)), mask)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    variant = args[0]; only = args[1] if len(args) > 1 else None
    replace = '--replace' in sys.argv
    force = '--force' in sys.argv or replace
    tdir = os.path.join(data_dir(variant), 'glyph_overrides'); os.makedirs(tdir, exist_ok=True)
    rpath = os.path.join(data_dir(variant), 'port_report.json')
    report = json.load(open(rpath)) if os.path.exists(rpath) else {}
    existing = overrides_of(variant)
    # source models: Normal's own overrides, and those of already-ported fonts that are exact transfers or
    # were hand-edited after porting (method "hand" in their report)
    sources = []
    for sv in SOURCES[variant]:
        rep = {} if sv == 'normal' else json.load(open(os.path.join(data_dir(sv), 'port_report.json')))
        for name, spec in overrides_of(sv).items():
            if sv == 'normal' or rep.get(name, {}).get('method') in ('identical', 'transfer', 'hand'):
                sources.append((sv, name, spec))
    # the set of overridden glyphs is Normal's: every font gets the same glyphs hand-modelled
    for name, nspec in overrides_of('normal').items():
        chs = chars_of(nspec)
        if only and not set(chs) & set(only):
            continue
        if name in existing and (not force or (report.get(name, {}).get('method') == 'hand' and not replace)):
            continue                      # --force re-ports, but only --replace replaces a hand-modelled glyph
        ch = chs[0]
        gid = gid_for(variant, ch)
        if gid is None:
            continue
        T = mask_of(variant, gid)
        cands = []
        for sv, sname, sspec in sources:
            if sname != name:
                continue
            S = mask_of(sv, gid_for(sv, ch))
            if S == T:
                sc = model_score(sspec, T, ch)
                cands.append(((0, 0, 0), 'identical', sv, copy.deepcopy(sspec), sc, ''))
                continue
            bm = best_mapping(S, T, sspec)
            if not bm:
                continue
            mis, pen, edits, kx, ky = bm
            spec = remap_spec(sspec, kx, ky)
            sc = model_score(spec, T, ch)
            cands.append(((mis, pen, edits), 'transfer' if mis == 0 else 'fuzzy', sv, spec, sc,
                          f'{edits} row/column edits' + (f', {mis} px differ' if mis else '')))
        exact = sorted([c for c in cands if c[1] in ('identical', 'transfer')], key=lambda c: (c[0], c[4]['err']))
        if exact:
            choice = exact[0]
        else:
            tr = trace(T, ch); tr['char'] = nspec['char']
            tsc = model_score(tr, T, ch)
            fuzzy = sorted([c for c in cands if c[1] == 'fuzzy'], key=lambda c: (c[4]['missing'], c[4]['err']))
            choice = (None, 'traced', None, tr, tsc, '')
            if fuzzy:
                f = fuzzy[0]
                if (f[4]['missing'], f[4]['err']) <= (tsc['missing'], tsc['err'] + PREFER_TRANSFER):
                    choice = f
        _, method, sv, spec, sc, note = choice
        spec['char'] = nspec['char']
        # the ported fonts' sharp joints are mitred, not rounded like most of Normal's (bevels are kept)
        if spec.get('join', 'round') == 'round':
            spec['join'] = 'miter'
        for st in spec['strokes']:
            if st.get('join') == 'round':
                st['join'] = 'miter'
        spec['_ported'] = f'{method} from {sv}' + (f' ({note})' if note else '') if sv else \
                          'traced from the pixels in the 67.5 degree corner-arc convention'
        with open(os.path.join(tdir, name + '.json'), 'w', encoding='utf-8') as f:
            json.dump(spec, f, indent=1, ensure_ascii=False)
        report[name] = {'char': nspec['char'], 'method': method, 'from': sv, 'note': note, **sc}
    json.dump(report, open(rpath, 'w'), indent=1, ensure_ascii=False)
    from collections import Counter
    print(variant, dict(Counter(v['method'] for v in report.values())))
    review = sorted((v['err'], n) for n, v in report.items() if v['method'] not in ('identical', 'transfer', 'hand'))
    print('to review:', ' '.join(f"{report[n]['char'] if isinstance(report[n]['char'], str) else report[n]['char'][0]}:{report[n]['method'][0]}{e:g}" for e, n in review))

if __name__ == '__main__':
    main()
