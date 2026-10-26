"""Generate the two non-exact treatments from the pixel masks.

Treatment 2 (data/svg_rounded): exact outline with every corner softened by a small arc.
Treatment 3 (data/svg_smooth): reconstructed centerline strokes. Each glyph is modelled as a
graph of pixel centres; chains are split at true corners (>= 90 deg turns), stepped diagonals
are replaced by straight lines, remaining joints are kept sharp (mitred when stroked), and the result
is written as centreline paths (stroked to outlines in build_font.py) plus round dots. A joint is rounded
only where a model asks for it (a joint radius above 0, or join "round").
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(__file__))
from common import *

STROKE_W = 1.0        # px, stroke width of the smooth font
DOT_R = 0.5           # px, radius of isolated single-pixel dots (keeps row-0 diaeresis inside the ascent)
JOINT_R = 0.0         # px, default cut-back of a joint (0 = sharp; a model may round a joint with a radius)
SHORT = 1.5           # px, segments up to this length may be absorbed into a straightened zigzag
K = 0.5523            # cubic approximation of a quarter circle

# ---------------- treatment 2: rounded corners on the exact outline ----------------
def round_corners(contours, r=0.3):
    paths = []
    for c in contours:
        n = len(c)
        segs = []
        for i in range(n):
            a, b, d = c[i-1], c[i], c[(i+1) % n]
            la = math.hypot(b[0]-a[0], b[1]-a[1]); lb = math.hypot(d[0]-b[0], d[1]-b[1])
            rr = min(r, la/2, lb/2)
            p = (b[0] + (a[0]-b[0])/la*rr, b[1] + (a[1]-b[1])/la*rr)
            q = (b[0] + (d[0]-b[0])/lb*rr, b[1] + (d[1]-b[1])/lb*rr)
            segs.append((p, b, q))
        d = ''
        for i, (p, b, q) in enumerate(segs):
            if i == 0:
                d += f'M{p[0]:g} {p[1]:g} '
            else:
                d += f'L{p[0]:g} {p[1]:g} '
            c1 = (p[0] + (b[0]-p[0])*K, p[1] + (b[1]-p[1])*K)
            c2 = (q[0] + (b[0]-q[0])*K, q[1] + (b[1]-q[1])*K)
            d += f'C{c1[0]:g} {c1[1]:g} {c2[0]:g} {c2[1]:g} {q[0]:g} {q[1]:g} '
        d += 'Z'
        paths.append(d)
    return ' '.join(paths)

# ---------------- treatment 3: centreline reconstruction ----------------
def build_graph(mask):
    h, w = len(mask), len(mask[0])
    nodes = {(x, y) for y in range(h) for x in range(w) if mask[y][x]}
    adj = {n: set() for n in nodes}
    for (x, y) in nodes:
        for dx, dy in ((1, 0), (0, 1)):
            q = (x+dx, y+dy)
            if q in nodes:
                adj[(x, y)].add(q); adj[q].add((x, y))
    for (x, y) in nodes:
        for dx, dy in ((1, 1), (-1, 1)):
            q = (x+dx, y+dy)
            if q in nodes:
                # diagonal link only when the two pixels do not already share a 4-neighbour
                if (x+dx, y) in nodes or (x, y+dy) in nodes:
                    continue
                adj[(x, y)].add(q); adj[q].add((x, y))
    return nodes, adj

def has_block(mask):
    h, w = len(mask), len(mask[0])
    return any(mask[y][x] and mask[y][x+1] and mask[y+1][x] and mask[y+1][x+1]
               for y in range(h-1) for x in range(w-1))

def chains_from_graph(nodes, adj):
    """Split the graph into open chains (between nodes of degree != 2) and closed cycles."""
    used = set()
    chains = []
    ends = [n for n in nodes if len(adj[n]) != 2]
    for s in sorted(ends):
        for nb in sorted(adj[s]):
            e = (s, nb) if s < nb else (nb, s)
            if e in used:
                continue
            chain = [s, nb]; used.add(e)
            prev, cur = s, nb
            while len(adj[cur]) == 2 and cur not in ends:
                nxt = next(q for q in adj[cur] if q != prev)
                e = (cur, nxt) if cur < nxt else (nxt, cur)
                if e in used:
                    break
                used.add(e); chain.append(nxt); prev, cur = cur, nxt
            chains.append((chain, False))
    # remaining cycles
    for s in sorted(nodes):
        if len(adj[s]) != 2:
            continue
        for nb in sorted(adj[s]):
            e = (s, nb) if s < nb else (nb, s)
            if e in used:
                continue
            chain = [s]; prev, cur = s, nb; used.add(e)
            while cur != s:
                chain.append(cur)
                nxt = next(q for q in adj[cur] if q != prev)
                e = (cur, nxt) if cur < nxt else (nxt, cur)
                used.add(e); prev, cur = cur, nxt
            chains.append((chain, True))
    dots = [n for n in nodes if not adj[n]]
    return chains, dots

def direction(a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    l = math.hypot(dx, dy)
    return (dx/l, dy/l)

def is_corner(a, b, c):
    da, db = direction(a, b), direction(b, c)
    return da[0]*db[0] + da[1]*db[1] <= 1e-9   # 90 degrees or sharper

def split_at_corners(chain, closed):
    """Return list of runs (point lists); each run is free of >=90 degree turns."""
    n = len(chain)
    if closed:
        corners = [i for i in range(n) if is_corner(chain[i-1], chain[i], chain[(i+1) % n])]
        if not corners:
            return [(chain, True)]
        runs = []
        for k in range(len(corners)):
            i, j = corners[k], corners[(k+1) % len(corners)]
            run = [chain[i]]
            t = i
            while t != j:
                t = (t+1) % n; run.append(chain[t])
            runs.append((run, False))
        return runs
    runs, cur = [], [chain[0]]
    for i in range(1, n-1):
        cur.append(chain[i])
        if is_corner(chain[i-1], chain[i], chain[i+1]):
            runs.append((cur, False)); cur = [chain[i]]
    cur.append(chain[-1]); runs.append((cur, False))
    return runs

def merge_collinear(pts, closed):
    n = len(pts)
    if n < 3:
        return pts
    out = []
    rng = range(n) if closed else range(1, n-1)
    for i in rng:
        a, b, c = pts[i-1], pts[i], pts[(i+1) % n]
        if (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0]) == 0:
            continue
        out.append(b)
    if not closed:
        out = [pts[0]] + out + [pts[-1]]
    return out

def turn_sign(a, b, c):
    return (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])

def straighten_zigzags(pts, closed):
    """Replace alternating-turn sequences of short segments with straight lines."""
    pts = merge_collinear(pts, closed)
    n = len(pts)
    if n < 3:
        return pts
    def seglen(i, j): return math.hypot(pts[j][0]-pts[i][0], pts[j][1]-pts[i][1])
    if closed:
        signs = [math.copysign(1, turn_sign(pts[i-1], pts[i], pts[(i+1) % n])) for i in range(n)]
        # closed shapes rarely zigzag; only handle open runs explicitly
        return pts
    signs = {i: math.copysign(1, turn_sign(pts[i-1], pts[i], pts[i+1])) for i in range(1, n-1)}
    keep = [True]*n
    i = 1
    while i < n-1:
        j = i
        while j+1 < n-1 and signs[j+1] == -signs[j]:
            j += 1
        if j > i:   # alternating window of joints i..j
            s = i-1 if seglen(i-1, i) <= SHORT + 1e-9 else i
            e = j+1 if seglen(j, j+1) <= SHORT + 1e-9 else j
            # if the border segment is long we keep the joint but drop the interior joints
            for t in range(s+1, e):
                keep[t] = False
            # the straightened span is from s to e; interior nodes removed
        i = j+1
    return [p for p, k in zip(pts, keep) if k]

def bulge_arc(a, b, bulge):
    """Circular arc from a to b (pixel coords, y down) with DXF-style bulge = tan(theta/4).
    Positive bulge bends counter-clockwise as seen on the page. Returns cubic Bezier segments."""
    theta = 4 * math.atan(bulge)                  # signed included angle
    d = math.hypot(b[0]-a[0], b[1]-a[1])
    if d < 1e-9 or abs(theta) < 1e-9:
        return None
    # work in y-up page coordinates
    ax, ay, bx, by = a[0], -a[1], b[0], -b[1]
    mx, my = (ax+bx)/2, (ay+by)/2
    ux, uy = (bx-ax)/d, (by-ay)/d
    h = d / (2 * math.tan(theta/2))               # signed distance from chord midpoint to centre (left of chord)
    cx, cy = mx - uy*h, my + ux*h
    r = d / (2 * abs(math.sin(theta/2)))
    a0 = math.degrees(math.atan2(ay-cy, ax-cx))
    a1 = a0 + math.degrees(theta)
    return arc_beziers(cx, -cy, r, a0, a1)

def rounded_path(pts, closed, default_r=None):
    """Build cubic Bezier segments for a polyline whose joints get rounded.
    Each point is (x, y), (x, y, r) or (x, y, r, bulge): r is that joint's cut-back radius in px
    (0 = sharp corner); bulge (DXF style, tan(theta/4)) makes the segment to the NEXT point a circular
    arc. Joints at either end of an arc segment are not rounded."""
    # drop zero-length segments: repeated consecutive points, and a closing point that repeats the first
    dd = []
    for p in pts:
        if not dd or abs(p[0]-dd[-1][0]) > 1e-9 or abs(p[1]-dd[-1][1]) > 1e-9:
            dd.append(p)
    if closed and len(dd) > 1 and abs(dd[0][0]-dd[-1][0]) < 1e-9 and abs(dd[0][1]-dd[-1][1]) < 1e-9:
        if len(dd[-1]) > 3 and dd[-1][3] and not (len(dd[0]) > 3 and dd[0][3]):
            dd[0] = dd[-1]          # keep a bulge stored on the duplicated closing point
        dd.pop()
    pts = dd
    radii = [p[2] if len(p) > 2 and p[2] is not None else (JOINT_R if default_r is None else default_r) for p in pts]
    bulges = [p[3] if len(p) > 3 and p[3] else 0.0 for p in pts]
    n0 = len(pts)
    for i, bz in enumerate(bulges):
        if bz:
            radii[i] = 0.0; radii[(i+1) % n0] = 0.0
    pts = [(p[0], p[1]) for p in pts]
    n = len(pts)
    if n == 1:
        return []
    segs = []   # list of (p0, c1, c2, p3)
    def cut(i):
        a, b, c = pts[i-1], pts[i], pts[(i+1) % n]
        la = math.hypot(b[0]-a[0], b[1]-a[1]); lb = math.hypot(c[0]-b[0], c[1]-b[1])
        if la < 1e-9 or lb < 1e-9:
            return b, b
        rr = min(radii[i], la/2, lb/2)
        p = (b[0] + (a[0]-b[0])/la*rr, b[1] + (a[1]-b[1])/la*rr)
        q = (b[0] + (c[0]-b[0])/lb*rr, b[1] + (c[1]-b[1])/lb*rr)
        return p, q
    joints = range(n) if closed else range(1, n-1)
    cuts = {i: cut(i) for i in joints}
    def line(a, b):
        return (a, (a[0]+(b[0]-a[0])/3, a[1]+(b[1]-a[1])/3), (a[0]+(b[0]-a[0])*2/3, a[1]+(b[1]-a[1])*2/3), b)
    def arc(p, v, q):
        return (p, (p[0]+(v[0]-p[0])*K, p[1]+(v[1]-p[1])*K), (q[0]+(v[0]-q[0])*K, q[1]+(v[1]-q[1])*K), q)
    order = list(range(n)) if closed else list(range(n))
    start = cuts[0][1] if closed else pts[0]
    cur = start
    rng = list(range(1, n+1)) if closed else list(range(1, n))
    def seg_to(target, from_idx):
        """straight line or bulge arc from cur to target, depending on the vertex we leave."""
        bz = bulges[from_idx % n]
        if bz:
            arcs = bulge_arc(cur, target, bz)
            if arcs:
                segs.extend(arcs); return
        segs.append(line(cur, target))
    for i in rng:
        idx = i % n
        if idx in cuts:
            p, q = cuts[idx]
            if math.hypot(p[0]-cur[0], p[1]-cur[1]) > 1e-9:
                seg_to(p, idx-1)
            if radii[idx] > 1e-9:
                segs.append(arc(p, pts[idx], q))
            cur = q
        else:
            seg_to(pts[idx], idx-1); cur = pts[idx]
    return segs

# Hand-built centrelines for letters whose pixel diagonals are 2 px thick. Coordinates are
# pixel centres (x, y). 'rows' is the band of the mask replaced by the override; everything
# outside it (accents) is still traced automatically.
BIG_DOT_R = 1.0
OVERRIDES_LEGACY_UNUSED = {
    'N': {'rows': (3, 12), 'polylines': [
        [(0.5, 3.5), (0.5, 11.5)], [(4.5, 3.5), (4.5, 11.5)],
        [(0.5, 3.5), (4.5, 11.5)]], 'width': 1.0},
    'M': {'rows': (3, 12), 'polylines': [
        [(0.5, 3.5), (0.5, 11.5)], [(4.5, 3.5), (4.5, 11.5)],
        [(0.5, 3.5), (2.5, 7.5), (4.5, 3.5)]], 'width': 1.0, 'sharp': True},
    'K': {'rows': (3, 12), 'polylines': [
        [(0.5, 3.5), (0.5, 11.5)],
        [(4.5, 3.5), (1.2, 6.8), (1.2, 8.2), (4.5, 11.5)]], 'width': 1.0, 'sharp': True},
    'W': {'rows': (3, 12), 'polylines': [
        [(0.5, 3.5), (0.5, 11.5)], [(4.5, 3.5), (4.5, 11.5)],
        [(0.5, 11.5), (1.5, 9.5), (2.5, 7.5), (3.5, 9.5), (4.5, 11.5)]], 'width': 1.0, 'sharp': True},
    '\u00d7': {'rows': (6, 12), 'polylines': [
        [(0.5, 6.5), (5.5, 11.5)], [(5.5, 6.5), (0.5, 11.5)]], 'width': 1.0},
}
OVERRIDES = {}  # built-ins now live in data/glyph_overrides/*.json

OVERRIDE_DIR = os.path.join(DATA, 'glyph_overrides')

def arc_beziers(cx, cy, r, a0, a1, steps=None):
    """Circular arc as cubic Beziers. Angles in degrees, measured counter-clockwise as seen on the
    page (0 = right, 90 = up); pixel coords are y-down so the sign is flipped internally."""
    sweep = a1 - a0
    n = steps or max(1, int(math.ceil(abs(sweep) / 90.0)))
    out = []
    for i in range(n):
        t0 = math.radians(a0 + sweep * i / n); t1 = math.radians(a0 + sweep * (i+1) / n)
        k = 4/3 * math.tan((t1 - t0) / 4)
        p0 = (cx + r*math.cos(t0), cy - r*math.sin(t0)); p3 = (cx + r*math.cos(t1), cy - r*math.sin(t1))
        c1 = (p0[0] - k*r*math.sin(t0), p0[1] - k*r*math.cos(t0))
        c2 = (p3[0] + k*r*math.sin(t1), p3[1] + k*r*math.cos(t1))
        out.append((p0, c1, c2, p3))
    return out

def load_overrides():
    """data/glyph_overrides/*.json -> {char: spec}. See README 'Hand-editing glyphs' for the format."""
    ov = {}
    if not os.path.isdir(OVERRIDE_DIR):
        return ov
    for fn in sorted(os.listdir(OVERRIDE_DIR)):
        if fn.endswith('.json'):
            spec = json.load(open(os.path.join(OVERRIDE_DIR, fn)))
            for ch in ([spec['char']] if isinstance(spec['char'], str) else spec['char']):
                ov[ch] = spec
    return ov

def override_strokes(spec):
    """Turn a JSON override spec into stroke records."""
    out = []
    w = spec.get('width', STROKE_W)
    rdef = spec.get('joint_radius', JOINT_R)
    jdef = spec.get('join', 'miter')
    for st in spec['strokes']:
        if 'cut' in st and not any(k in st for k in ('points', 'arc', 'circle')):
            continue   # pure cut-mask entries are collected separately (a stroke may also carry its own cut)
        if 'fill' in st:
            # a solid polygon (the arrows' heads and shafts), drawn as is: no stroke width, no caps
            P = [tuple(p[:2]) for p in st['fill']]
            if len(P) >= 3:
                out.append({'closed': True, 'fill': [list(p) for p in P], 'width': 0,
                            'beziers': [(a, a, b, b) for a, b in zip(P, P[1:] + P[:1])]})
            continue
        sw = st.get('width', w); sj = st.get('join', jdef)
        if 'arc' in st:
            a = st['arc']
            segs = arc_beziers(a['center'][0], a['center'][1], a['radius'], a['start'], a['end'])
            out.append({'closed': False, 'beziers': segs, 'width': sw, 'join': sj}); continue
        if 'circle' in st:
            c = st['circle']
            segs = arc_beziers(c['center'][0], c['center'][1], c['radius'], 0, 360, 4)
            out.append({'closed': True, 'beziers': segs, 'width': sw, 'join': sj}); continue
        pts = [tuple(p) for p in st['points']]
        r = 0.0 if st.get('sharp') else st.get('joint_radius', rdef)
        if st.get('sharp'):
            pts = [(p[0], p[1], 0.0) + tuple(p[3:]) for p in pts]
        segs = rounded_path(pts, bool(st.get('closed')), r)
        if segs:
            out.append({'closed': bool(st.get('closed')), 'beziers': segs, 'width': sw, 'join': sj})
    return out

def override_cuts(spec):
    """Polygons (pixel coords) subtracted from the finished outline."""
    cuts = [st['cut'] for st in spec['strokes'] if 'cut' in st and len(st['cut']) >= 3] + list(spec.get('cuts', []))
    # convenience clips: keep only the band y in [y0, y1) / x in [x0, x1); everything outside is cut away
    if spec.get('clip_y'):
        y0, y1 = spec['clip_y']; cuts += [[[-2, -2], [18, -2], [18, y0], [-2, y0]], [[-2, y1], [18, y1], [18, 18], [-2, 18]]]
    if spec.get('clip_x'):
        x0, x1 = spec['clip_x']; cuts += [[[-2, -2], [x0, -2], [x0, 18], [-2, 18]], [[x1, -2], [18, -2], [18, 18], [x1, 18]]]
    return cuts

def norm_dot(d, shape='circle', corner=0.25):
    """Dot spec -> {x, y, r, shape, corner}. Accepts [x,y], [x,y,r], [x,y,r,shape], [x,y,r,shape,corner] or a dict.
    r is the half-size (circle radius / half the square side); corner is the rounded-square corner radius in px."""
    if isinstance(d, dict):
        return {'x': d['x'], 'y': d['y'], 'r': d.get('r', DOT_R), 'shape': d.get('shape', shape), 'corner': d.get('corner', corner)}
    return {'x': d[0], 'y': d[1], 'r': d[2] if len(d) > 2 else DOT_R, 'shape': d[3] if len(d) > 3 else shape, 'corner': d[4] if len(d) > 4 else corner}

def find_blocks(mask):
    """Return list of (cx, cy) centres of 2x2 filled blocks (pixel-corner coords) and the pixel set."""
    h, w = len(mask), len(mask[0])
    blocks, pix = [], set()
    for y in range(h-1):
        for x in range(w-1):
            if mask[y][x] and mask[y][x+1] and mask[y+1][x] and mask[y+1][x+1]:
                blocks.append((x+1.0, y+1.0)); pix |= {(x, y), (x+1, y), (x, y+1), (x+1, y+1)}
    return blocks, pix

def is_punct_blocks(mask):
    """True when every 2x2 block is isolated enough to be drawn as a dot (punctuation)."""
    blocks, pix = find_blocks(mask)
    return len(blocks) <= 2 and len(pix) == 4*len(blocks)

def line_strokes(polylines, sharp=False):
    out = []
    for pl in polylines:
        if sharp:
            for a, b in zip(pl, pl[1:]):
                out.append({'closed': False, 'beziers': rounded_path([a, b], False)})
        else:
            out.append({'closed': False, 'beziers': rounded_path(pl, False)})
    return out

def smooth_glyph(mask, char=None):
    mask = [row[:] for row in mask]
    strokes, big_dots = [], []
    cuts = []
    jov = JSON_OVERRIDES.get(char)
    ov = OVERRIDES.get(char)
    if jov:
        rows = jov.get('rows', [0, 16])
        for y in range(rows[0], rows[1]):
            mask[y] = [0]*len(mask[y])
        strokes.extend(override_strokes(jov)); cuts.extend(override_cuts(jov))
        for d in jov.get('dots', []):
            big_dots.append(norm_dot(d, jov.get('dot_shape', 'circle'), jov.get('dot_corner', 0.25)))
    elif ov:
        for y in range(ov['rows'][0], ov['rows'][1]):
            mask[y] = [0]*len(mask[y])
        for s in line_strokes(ov['polylines'], ov.get('sharp', False)):
            s['width'] = ov['width']; strokes.append(s)
    blocks, bpix = find_blocks(mask)
    for (x, y) in bpix:
        mask[y][x] = 0
    nodes, adj = build_graph(mask)
    # link pixels that touched a block to a virtual node at the block centre
    for cx, cy in blocks:
        v = (cx-0.5, cy-0.5)   # expressed in pixel-index coords so +0.5 later gives the centre
        adj[v] = set(); nodes.add(v)
        for (x, y) in list(nodes):
            if (x, y) == v or (x, y) not in adj:
                continue
            if abs(x-(cx-0.5)) <= 1.5 and abs(y-(cy-0.5)) <= 1.5 and isinstance(x, int):
                adj[v].add((x, y)); adj[(x, y)].add(v)
        big_dots.append((cx, cy))
    chains, dots = chains_from_graph(nodes, adj)
    for chain, closed in chains:
        for run, rclosed in split_at_corners(chain, closed):
            pts = straighten_zigzags(run, rclosed)
            pts = [(x+0.5, y+0.5) for x, y in pts]
            segs = rounded_path(pts, rclosed)
            if segs:
                strokes.append({'closed': rclosed, 'beziers': segs})
    dots = [norm_dot((x+0.5, y+0.5, DOT_R)) for x, y in dots if isinstance(x, int)] + \
           [t if isinstance(t, dict) else norm_dot((t[0], t[1], BIG_DOT_R) if len(t) == 2 else t) for t in big_dots]
    return strokes, dots, cuts

def strokes_to_svg_d(strokes):
    out = []
    for s in strokes:
        b = s['beziers']
        d = f"M{b[0][0][0]:.3f} {b[0][0][1]:.3f} "
        for p0, c1, c2, p3 in b:
            d += f"C{c1[0]:.3f} {c1[1]:.3f} {c2[0]:.3f} {c2[1]:.3f} {p3[0]:.3f} {p3[1]:.3f} "
        if s['closed']:
            d += 'Z'
        out.append(d)
    return ' '.join(out)

def clamp_ext(p, v):
    """Scale the cap extension so the end point stays inside the 16x16 source cell."""
    t = 1.0
    for i in range(2):
        if v[i] > 1e-9: t = min(t, (16 - p[i]) / v[i])
        elif v[i] < -1e-9: t = min(t, (0 - p[i]) / v[i])
    return (v[0]*max(t, 0), v[1]*max(t, 0))

def extend_caps(strokes):
    """Square caps done explicitly: push the two ends of every open stroke out by half the stroke
    width along their tangents, so a stem drawn from pixel centre 3.5 to 11.5 covers rows 3..11 fully.
    (FontForge's stroker only offers butt/round caps through the Python API.)"""
    for s in strokes:
        if s['closed'] or not s['beziers']:
            continue
        h = s.get('width', STROKE_W) / 2
        p0, c1, c2, p3 = s['beziers'][0]
        d = (c1[0]-p0[0], c1[1]-p0[1]) if (c1 != p0) else (p3[0]-p0[0], p3[1]-p0[1])
        l = math.hypot(*d) or 1; v = clamp_ext(p0, (-d[0]/l*h, -d[1]/l*h))
        s['beziers'][0] = ((p0[0]+v[0], p0[1]+v[1]), (c1[0]+v[0], c1[1]+v[1]), c2, p3)
        p0, c1, c2, p3 = s['beziers'][-1]
        d = (p3[0]-c2[0], p3[1]-c2[1]) if (c2 != p3) else (p3[0]-p0[0], p3[1]-p0[1])
        l = math.hypot(*d) or 1; v = clamp_ext(p3, (d[0]/l*h, d[1]/l*h))
        s['beziers'][-1] = (p0, c1, (c2[0]+v[0], c2[1]+v[1]), (p3[0]+v[0], p3[1]+v[1]))
    return strokes

JSON_OVERRIDES = {}
CODEPOINTS = {}

def main():
    global JSON_OVERRIDES
    JSON_OVERRIDES = load_overrides()
    print('glyph overrides loaded:', ''.join(sorted(JSON_OVERRIDES)))
    mp = load_json('mapping.json')
    os.makedirs(os.path.join(DATA, 'svg_rounded'), exist_ok=True)
    os.makedirs(os.path.join(DATA, 'svg_smooth'), exist_ok=True)
    fallback = []
    bad_overrides = []
    global CODEPOINTS
    cpf = os.path.join(DATA, 'codepoints.json')
    CODEPOINTS = json.load(open(cpf)) if os.path.exists(cpf) else {}
    for gid in range(512):
        e = mp[str(gid)]
        if not e['ink']:
            continue
        m = json.load(open(os.path.join(DATA, 'masks', f'{gid:03d}.json')))
        contours = json.load(open(os.path.join(DATA, 'svg_exact', f'{gid:03d}.json')))
        d2 = round_corners(contours)
        with open(os.path.join(DATA, 'svg_rounded', f'{gid:03d}.svg'), 'w') as f:
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="160" height="160">\n<path d="{d2}" fill="#000"/>\n</svg>\n')
        with open(os.path.join(DATA, 'svg_rounded', f'{gid:03d}.json'), 'w') as f:
            json.dump({'d': d2}, f)
        # a cell may carry several code points (e.g. U+2019 and U+0027 share one glyph);
        # use whichever alias has an override, else the primary one
        aliases = [chr(u) for u in e['unicode']] + [chr(u) for u in CODEPOINTS.get(str(gid), {}).get('codepoints', []) if chr(u) not in [chr(v) for v in e['unicode']]]
        ch = next((a for a in aliases if a in JSON_OVERRIDES or a in OVERRIDES), aliases[0] if aliases else None)
        fb = has_block(m['fg']) and ch not in OVERRIDES and ch not in JSON_OVERRIDES and not is_punct_blocks(m['fg'])
        try:
            strokes, dots, cuts = smooth_glyph(m['fg'], ch)
        except Exception as ex:
            import traceback
            print(f"ERROR in override for {ch!r} (glyph {gid}): {ex} -- using automatic trace instead", file=sys.stderr)
            traceback.print_exc()
            bad_overrides.append(ch)
            strokes, dots, cuts = smooth_glyph(m['fg'], None)
        extend_caps(strokes)
        if fb:
            fallback.append(gid)
        rec = {'id': gid, 'fallback_rounded_outline': fb, 'stroke_width': STROKE_W, 'dot_r': DOT_R,
               'strokes': strokes, 'dots': dots, 'cuts': cuts}
        with open(os.path.join(DATA, 'svg_smooth', f'{gid:03d}.json'), 'w') as f:
            json.dump(rec, f)
        d3 = strokes_to_svg_d(strokes)
        dots_svg = ''.join(f'<circle cx="{d["x"]}" cy="{d["y"]}" r="{d["r"]}" fill="#000"/>' if d['shape'] == 'circle' else
                           f'<rect x="{d["x"]-d["r"]}" y="{d["y"]-d["r"]}" width="{2*d["r"]}" height="{2*d["r"]}" rx="{0 if d["shape"] == "square" else min(d["corner"], d["r"])}" fill="#000"/>' for d in dots)
        with open(os.path.join(DATA, 'svg_smooth', f'{gid:03d}.centerline.svg'), 'w') as f:
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="160" height="160">\n'
                    f'<path d="{d3}" fill="none" stroke="#000" stroke-width="{STROKE_W}" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="4"/>{dots_svg}\n</svg>\n')
    print('glyphs using rounded-outline fallback (contain 2x2 blocks):',
          [(g, ''.join(chr(u) for u in mp[str(g)]['unicode']) or mp[str(g)]['name']) for g in fallback])
    if bad_overrides:
        print('BROKEN OVERRIDES (automatic trace used instead):', ''.join(bad_overrides), file=sys.stderr)
        sys.exit(2)

if __name__ == '__main__':
    main()
