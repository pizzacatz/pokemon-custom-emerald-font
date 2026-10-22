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
                    tracking=0, lsb=0, space=3),
    'rounded': dict(family='Emerald Pixel Soft', style='Regular', file='EmeraldPixelSoft-Regular',
                    tracking=0, lsb=0, space=3),
    'smooth':  dict(family='Emerald Rounded', style='Regular', file='EmeraldRounded-Regular',
                    tracking=1, lsb=0.5, space=4),   # extra px of advance and half-px shift for smooth text
    'smoothgame': dict(family='Emerald Rounded Game', style='Regular', file='EmeraldRoundedGame-Regular',
                    tracking=0, lsb=0, space=3),     # smooth outlines, spacing identical to the game
}[TREATMENT]
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
        cut = fontforge.layer()
        c = fontforge.contour(); c.moveTo(*pt(*poly[0]))
        for p in poly[1:]:
            c.lineTo(*pt(*p))
        c.closed = True; cut += c
        cut.removeOverlap(); cut.correctDirection()
        # FontForge's layer.exclude() argument order is the reverse of its docstring: cut.exclude(shape) == shape - cut
        g.foreground = cut.exclude(g.foreground)
        # exclude() hands back contours with scrambled directions (an untouched outer box can come back
        # counter-clockwise). removeOverlap on that merges counters away, so fix directions FIRST.
        g.correctDirection()
        g.removeOverlap()
        g.correctDirection()
    g.simplify(1.0, ('mergelines', 'setstarttoextremum'), 0.2)
    g.round()
    g.correctDirection()

def main():
    cps = load_json('codepoints.json')
    mp = load_json('mapping.json')
    f = fontforge.font()
    f.em = UPM; f.ascent = 12*PX; f.descent = 4*PX
    f.familyname = META['family']; f.fontname = META['file']; f.fullname = f"{META['family']} {META['style']}"
    f.weight = 'Regular'; f.version = VERSION
    f.copyright = ('Outlines derived from the Latin "normal" bitmap font of Pokémon Emerald as decompiled by '
                   'the pret/pokeemerald project. Original artwork © Nintendo / Creatures / GAME FREAK; '
                   'no licence for the artwork is asserted here. Conversion scripts: Emerald Rounded project.')
    f.appendSFNTName('English (US)', 'Family', META['family'])
    f.appendSFNTName('English (US)', 'SubFamily', META['style'])
    f.appendSFNTName('English (US)', 'UniqueID', f"{META['file']} {VERSION}")
    f.appendSFNTName('English (US)', 'Fullname', f.fullname)
    f.appendSFNTName('English (US)', 'Version', f'Version {VERSION}')
    f.appendSFNTName('English (US)', 'PostScriptName', META['file'])
    # vertical metrics: 16 px line == 1 em, baseline 12 px from top (matches the game's 16 px line pitch)
    f.hhea_ascent = 12*PX; f.hhea_descent = -4*PX; f.hhea_linegap = 0
    f.os2_typoascent = 12*PX; f.os2_typodescent = -4*PX; f.os2_typolinegap = 0
    f.os2_winascent = 12*PX; f.os2_windescent = 4*PX
    f.os2_use_typo_metrics = True
    f.os2_capheight = 9*PX; f.os2_xheight = 6*PX
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
        if gid == 0 or rec['name'] == 'space':
            g.width = META['space']*PX
        else:
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
