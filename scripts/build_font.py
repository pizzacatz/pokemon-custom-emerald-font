"""Assemble a TTF/SFD with FontForge from one of the outline treatments.

usage: fontforge -lang=py -script build_font.py <exact|rounded|smooth> [--no-ttf]
Run via scripts/ff.sh which picks the system fontforge or the project AppImage.
"""
import sys, os, json, time
import fontforge, psMat
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

TREATMENT = sys.argv[1]
META = {
    'exact':   dict(family='Emerald Pixel Vector', style='Regular', file='EmeraldPixelVector-Regular',
                    tracking=0, lsb=0),
    'rounded': dict(family='Emerald Pixel Soft', style='Regular', file='EmeraldPixelSoft-Regular',
                    tracking=0, lsb=0),
    'smooth':  dict(family='Emerald Rounded', style='Regular', file='EmeraldRounded-Regular',
                    tracking=1, lsb=0.5),   # extra px of advance and half-px shift for smooth text
    'smoothgame': dict(family='Emerald Rounded Game', style='Regular', file='EmeraldRoundedGame-Regular',
                    tracking=0, lsb=0),     # smooth outlines, spacing identical to the game
}[TREATMENT]
if VARIANT != 'normal':
    # e.g. "Emerald Pixel Vector Narrow" / "Emerald Rounded Narrow Game"
    fam = META['family'].split(' ')
    fam.insert(3 if TREATMENT == 'exact' else 2, VINFO['name'])
    META['family'] = ' '.join(fam)
    META['file'] = META['family'].replace(' ', '') + '-' + META['style']
OUTLINES = 'smooth' if TREATMENT.startswith('smooth') else TREATMENT
VERSION = '1.0'

def pt(x, y):
    return (x*PX, (BASELINE_ROW - y)*PX)

def contour_from_svg_d(d):
    """Parse the limited SVG path syntax we emit (M, L, C, Z with absolute coords)."""
    import re
    toks = re.sub(r'([MLCZ])', r' \1 ', d).replace(',', ' ').split()
    contours, cur, i = [], None, 0
    while i < len(toks):
        t = toks[i]
        if t == 'M':
            cur = fontforge.contour(); x, y = float(toks[i+1]), float(toks[i+2]); cur.moveTo(*pt(x, y)); i += 3
        elif t == 'L':
            x, y = float(toks[i+1]), float(toks[i+2]); cur.lineTo(*pt(x, y)); i += 3
        elif t == 'C':
            v = [float(v) for v in toks[i+1:i+7]]
            cur.cubicTo(pt(v[0], v[1]), pt(v[2], v[3]), pt(v[4], v[5])); i += 7
        elif t == 'Z':
            cur.closed = True; contours.append(cur); cur = None; i += 1
        else:
            raise ValueError(t)
    return contours

def exact_layer(gid):
    pts = json.load(open(os.path.join(DATA, 'svg_exact', f'{gid:03d}.json')))
    lay = fontforge.layer()
    for c in pts:
        con = fontforge.contour()
        c = c[::-1]   # tracer emits clockwise in y-down coords; TrueType wants clockwise in y-up
        con.moveTo(*pt(*c[0]))
        for p in c[1:]:
            con.lineTo(*pt(*p))
        con.closed = True
        lay += con
    return lay

def rounded_layer(gid):
    d = json.load(open(os.path.join(DATA, 'svg_rounded', f'{gid:03d}.json')))['d']
    lay = fontforge.layer()
    for c in contour_from_svg_d(d):
        lay += c
    return lay

def circle(cx, cy, r):
    c = fontforge.contour()
    k = 0.5523*r
    x, y = pt(cx, cy); r *= PX; k *= PX
    c.moveTo(x+r, y)   # clockwise (y-up)
    c.cubicTo((x+r, y-k), (x+k, y-r), (x, y-r))
    c.cubicTo((x-k, y-r), (x-r, y-k), (x-r, y))
    c.cubicTo((x-r, y+k), (x-k, y+r), (x, y+r))
    c.cubicTo((x+k, y+r), (x+r, y+k), (x+r, y))
    c.closed = True
    return c

def dot_contour(d):
    """Circle, square or rounded square dot (pixel coords, r = half size)."""
    x, y, r = d['x'], d['y'], d['r']
    if d['shape'] == 'circle':
        return circle(x, y, r)
    cr = 0.0 if d['shape'] == 'square' else max(0.0, min(d.get('corner', 0.25), r))
    c = fontforge.contour()
    if cr <= 1e-6:
        for px_, py_ in ((x-r, y-r), (x+r, y-r), (x+r, y+r), (x-r, y+r)):
            (c.moveTo if len(c) == 0 else c.lineTo)(*pt(px_, py_))
        c.closed = True; return c
    k = 0.5523*cr
    # clockwise in y-up == counter-clockwise in these y-down pixel coords; start at top edge, left end
    c.moveTo(*pt(x-r+cr, y-r)); c.lineTo(*pt(x+r-cr, y-r))
    c.cubicTo(pt(x+r-cr+k, y-r), pt(x+r, y-r+cr-k), pt(x+r, y-r+cr)); c.lineTo(*pt(x+r, y+r-cr))
    c.cubicTo(pt(x+r, y+r-cr+k), pt(x+r-cr+k, y+r), pt(x+r-cr, y+r)); c.lineTo(*pt(x-r+cr, y+r))
    c.cubicTo(pt(x-r+cr-k, y+r), pt(x-r, y+r-cr+k), pt(x-r, y+r-cr)); c.lineTo(*pt(x-r, y-r+cr))
    c.cubicTo(pt(x-r, y-r+cr-k), pt(x-r+cr-k, y-r), pt(x-r+cr, y-r))
    c.closed = True
    return c

def layer_area(lay):
    """Net area of a layer from its point polygons (control points included: exact enough to compare
    a layer before and after a boolean operation)."""
    tot = 0.0
    for c in lay:
        pts = [(p.x, p.y) for p in c]
        tot += sum(x0*y1 - x1*y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1])) / 2
    return abs(tot)

def clipped_area(poly, box):
    """Area of polygon `poly` inside the rectangle box = (x0, y0, x1, y1) (Sutherland-Hodgman)."""
    x0, y0, x1, y1 = box
    for inside, cross in ((lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1]-a[1])*(x0-a[0])/(b[0]-a[0]))),
                          (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1]-a[1])*(x1-a[0])/(b[0]-a[0]))),
                          (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0]-a[0])*(y0-a[1])/(b[1]-a[1]), y0)),
                          (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0]-a[0])*(y1-a[1])/(b[1]-a[1]), y1))):
        out = []
        for a, b in zip(poly, poly[1:] + poly[:1]):
            if inside(b):
                if not inside(a):
                    out.append(cross(a, b))
                out.append(b)
            elif inside(a):
                out.append(cross(a, b))
        poly = out
        if not poly:
            return 0.0
    return abs(sum(xa*yb - xb*ya for (xa, ya), (xb, yb) in zip(poly, poly[1:] + poly[:1]))) / 2

# FontForge's boolean ops misbehave when a cut edge lies exactly on an outline edge (a clip at x=0 along a
# stem's left side, a clip at the baseline under a box, a terminal trim whose box matches the stroke end):
# whole contours vanish, the cut half-inverts, or it silently does nothing. Each cut is checked and, if
# needed, retried grown outward by a fraction of a font unit, which moves its edges off the outline's
# without leaving slivers; g.round() absorbs the difference.
CUT_GROW = [0, 0.5, 1.0, 1.5, 2.5]

def grow(poly, d):
    """Move every vertex d units away from the polygon's centre along both axes."""
    cx = sum(x for x, _ in poly) / len(poly); cy = sum(y for _, y in poly) / len(poly)
    sg = lambda v: (v > 1e-9) - (v < -1e-9)
    return [(x + d*sg(x - cx), y + d*sg(y - cy)) for x, y in poly]

def _polys(lay):
    """Contours flattened to polygons (cubic and quadratic segments sampled at 8 steps)."""
    out = []
    for c in lay:
        pts = [(p.x, p.y, p.on_curve) for p in c]
        if not pts:
            continue
        k = next((i for i, p in enumerate(pts) if p[2]), 0)
        pts = pts[k:] + pts[:k]
        poly, i, n = [], 0, len(pts)
        while i < n:
            x0, y0, _ = pts[i]; poly.append((x0, y0))
            offs, j = [], i + 1
            while j < i + n and not pts[j % n][2]:
                offs.append(pts[j % n][:2]); j += 1
            end = pts[j % n][:2]
            ctrl = [(x0, y0)] + offs + [end]
            if len(ctrl) in (3, 4):
                for s in range(1, 8):
                    t = s / 8
                    q = ctrl[:]
                    while len(q) > 1:       # de Casteljau
                        q = [((1-t)*a[0] + t*b[0], (1-t)*a[1] + t*b[1]) for a, b in zip(q, q[1:])]
                    poly.append(q[0])
            i = j
        out.append(poly)
    return out

def _inside(polys, x, y):
    """Nonzero winding of (x, y) over contour point polygons (control points included)."""
    w = 0
    for pts in polys:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            if (y0 <= y < y1 or y1 <= y < y0) and x < x0 + (y - y0)*(x1 - x0)/(y1 - y0):
                w += 1 if y1 > y0 else -1
    return w != 0

def cut_is_clean(before, after, poly):
    """Sample a 1/4 px grid around the cut: ink inside the cut must be gone, ink outside it must remain.
    Catches an exclude that half-inverts the cut (ink appears in it while a notch vanishes beside it)."""
    xs = [x for x, _ in poly]; ys = [y for _, y in poly]
    bx0, by0, bx1, by1 = before.boundingBox()
    x0, x1 = max(min(xs), bx0) - 100, min(max(xs), bx1) + 100
    y0, y1 = max(min(ys), by0) - 100, min(max(ys), by1) + 100
    pb, pa, pc = _polys(before), _polys(after), [list(poly)]
    bad = 0
    y = y0 + 12.5
    while y < y1:
        x = x0 + 12.5
        while x < x1:
            in_cut = _inside(pc, x, y)
            bad += (in_cut and _inside(pa, x, y)) or (not in_cut and _inside(pb, x, y) and not _inside(pa, x, y))
            x += 25
        y += 25
    return bad <= 3              # a few samples may straddle curves approximated by their control points

def apply_cut(g, poly):
    """g.foreground minus the polygon poly (font units)."""
    if clipped_area(poly, (-1e9, -1e9, 1e9, 1e9)) < 1:
        return                     # degenerate polygon (zero area): FontForge's exclude would wipe the glyph
    shape = g.foreground
    before = layer_area(shape)
    removable = clipped_area(poly, shape.boundingBox())
    for d in CUT_GROW:
        gp = grow(poly, d)
        cut = fontforge.layer()
        c = fontforge.contour(); c.moveTo(*gp[0])
        for x, y in gp[1:]:
            c.lineTo(x, y)
        c.closed = True; cut += c
        cut.removeOverlap(); cut.correctDirection()
        # FontForge's layer.exclude() argument order is the reverse of its docstring: cut.exclude(shape) == shape - cut
        g.foreground = cut.exclude(shape)
        # exclude() hands back contours with scrambled directions (an untouched outer box can come back
        # counter-clockwise). removeOverlap on that merges counters away, so fix directions FIRST.
        g.correctDirection()
        g.removeOverlap()
        g.correctDirection()
        if layer_area(g.foreground) >= before - removable - 0.02*before - 50 and \
                cut_is_clean(shape, g.foreground, gp):
            return
        print(f'cut retried for {g.glyphname}: exclude went wrong with the cut grown by {d} units', file=sys.stderr)
    g.foreground = shape
    print(f'WARNING: cut on {g.glyphname} still wrong after {len(CUT_GROW)} tries; left uncut', file=sys.stderr)

def smooth_glyph(g, gid):
    rec = json.load(open(os.path.join(DATA, 'svg_smooth', f'{gid:03d}.json')))
    if rec['fallback_rounded_outline']:
        g.foreground = rounded_layer(gid)
        return
    # group strokes by width, stroke each group, union
    groups = {}
    for s in rec['strokes']:
        groups.setdefault((s.get('width', rec['stroke_width']), s.get('join', 'round')), []).append(s)
    result = fontforge.layer()
    for (w, join), strokes in groups.items():
        lay = fontforge.layer()
        for s in strokes:
            c = fontforge.contour()
            b = s['beziers']
            c.moveTo(*pt(*b[0][0]))
            for p0, c1, c2, p3 in b:
                c.cubicTo(pt(*c1), pt(*c2), pt(*p3))
            c.closed = bool(s['closed'])
            lay += c
        stroked = lay.stroke('circular', w*PX, 'butt', join)   # caps are pre-extended in smooth.py
        for c in stroked:
            result += c
    for d in rec['dots']:
        result += dot_contour(d)
    g.foreground = result
    g.removeOverlap()
    g.correctDirection()          # outer contours and counters must be consistently oriented before any boolean op
    # Cuts are applied ONE AT A TIME. Putting several polygons in one layer breaks FontForge's exclude when
    # they overlap each other (clip_x + clip_y corners, a cut over a clip band): overlapping cut regions
    # cancel out and the mask inverts; a cut crossing a counter could also fill the counter.
    for poly in rec.get('cuts', []):
        apply_cut(g, [pt(*p) for p in poly])
    g.simplify(1.0, ('mergelines', 'setstarttoextremum'), 0.2)
    g.round()
    g.correctDirection()

def main():
    cps = load_json('codepoints.json')
    mp = load_json('mapping.json')
    f = fontforge.font()
    f.em = UPM
    f.familyname = META['family']; f.fontname = META['file']; f.fullname = f"{META['family']} {META['style']}"
    f.weight = 'Regular'; f.version = VERSION
    f.copyright = (f'Outlines derived from the Latin "{VARIANT.replace("_", " ")}" bitmap font of Pokémon Emerald as decompiled by '
                   'the pret/pokeemerald project. Original artwork © Nintendo / Creatures / GAME FREAK; '
                   'no licence for the artwork is asserted here. Conversion scripts: Emerald Rounded project.')
    f.appendSFNTName('English (US)', 'Family', META['family'])
    f.appendSFNTName('English (US)', 'SubFamily', META['style'])
    f.appendSFNTName('English (US)', 'UniqueID', f"{META['file']} {VERSION}")
    f.appendSFNTName('English (US)', 'Fullname', f.fullname)
    f.appendSFNTName('English (US)', 'Version', f'Version {VERSION}')
    f.appendSFNTName('English (US)', 'PostScriptName', META['file'])
    # vertical metrics: 1 em == the 16 px cell, so 16 px text reproduces the game pixels 1:1. The line height is the
    # game's line pitch for this font (16 px for Normal), split at the baseline row (12 px from the top for Normal).
    asc, desc = BASELINE_ROW*PX, (VINFO['line'] - BASELINE_ROW)*PX
    f.ascent = asc; f.descent = UPM - asc
    f.hhea_ascent = asc; f.hhea_descent = -desc; f.hhea_linegap = 0
    f.os2_typoascent = asc; f.os2_typodescent = -desc; f.os2_typolinegap = 0
    f.os2_winascent = asc; f.os2_windescent = desc
    f.os2_use_typo_metrics = True
    def top_of(ch):
        return next((e['ink_ymin'] for e in mp.values() if ord(ch) in e['unicode'] and e['ink']), None)
    f.os2_capheight = (BASELINE_ROW - top_of('H'))*PX; f.os2_xheight = (BASELINE_ROW - top_of('x'))*PX
    f.hhea_ascent_add = f.hhea_descent_add = f.os2_typoascent_add = f.os2_typodescent_add = 0
    f.os2_winascent_add = f.os2_windescent_add = 0
    f.encoding = 'UnicodeFull'
    # .notdef: hollow box
    g = f.createChar(-1, '.notdef'); g.width = 6*PX
    lay = fontforge.layer()
    for (x0, y0, x1, y1) in [(0, 3, 5, 12), (1, 4, 4, 11)]:
        c = fontforge.contour(); c.moveTo(*pt(x0, y0)); c.lineTo(*pt(x1, y0)); c.lineTo(*pt(x1, y1)); c.lineTo(*pt(x0, y1)); c.closed = True; lay += c
    g.foreground = lay; g.correctDirection()
    tracking, lsb = META['tracking'], META['lsb']
    for gid_s, rec in cps.items():
        gid = int(gid_s); e = mp[gid_s]
        cp = rec['codepoints'][0]
        g = f.createChar(cp, rec['name']) if rec['name'] else f.createChar(cp)
        for extra in rec['codepoints'][1:]:
            g.altuni = tuple((g.altuni or ())) + ((extra, -1, 0),)
        if e['ink']:
            if OUTLINES == 'exact':
                g.foreground = exact_layer(gid)
            elif OUTLINES == 'rounded':
                g.foreground = rounded_layer(gid)
            else:
                if os.environ.get('FF_DEBUG'): print('GLYPH', gid, chr(cp), flush=True); sys.stdout.flush()
                smooth_glyph(g, gid)
            g.correctDirection()
            if lsb:
                g.transform(psMat.translate(lsb*PX, 0))
        # advance: in-game width already includes the 1 px shadow column (acts as the right side bearing)
        # (the space too: 3 px in every table except Short Narrower's, which gives it 1)
        g.width = (e['width'] + tracking)*PX
    f.selection.all()
    f.addExtrema() if OUTLINES != 'exact' else None
    os.makedirs(os.path.join(BUILD, 'fonts'), exist_ok=True)
    sfd = os.path.join(BUILD, 'fonts', META['file'] + '.sfd')
    f.save(sfd)
    if '--no-ttf' not in sys.argv:
        f.generate(os.path.join(BUILD, 'fonts', META['file'] + '.ttf'), flags=('opentype',))
        f.generate(os.path.join(BUILD, 'fonts', META['file'] + '.otf'), flags=('opentype',))
    # per-glyph SVG export of the final outlines (smooth treatment: stroked result)
    if TREATMENT == 'smooth':
        outdir = os.path.join(DATA, 'svg_smooth')
        for g in f.glyphs():
            if g.unicode >= 0 and not g.foreground.isEmpty():
                g.export(os.path.join(outdir, f"u{g.unicode:04X}.outline.svg"))
    print('built', META['file'], 'glyphs:', len(list(f.glyphs())))

if __name__ == '__main__':
    main()
