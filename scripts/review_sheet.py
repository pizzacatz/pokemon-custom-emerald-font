"""Contact sheet of every hand-modelled glyph of one font, for reviewing ported overrides.

usage: python3 scripts/review_sheet.py <variant> [chars] [--all]
Writes build/comparisons/<variant>_overrides_review.png. Each cell shows the game pixels (blue), the
model's ink as the rasteriser sees it (pink, dark where both agree), the centrelines (black) and the
port method + score from port_report.json: = identical, T transfer, F fuzzy transfer, R traced, H hand.
Without --all only glyphs that were not carried over exactly are shown."""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image, ImageDraw
import numpy as np
from port_overrides import overrides_of, chars_of, gid_for, mask_of, model_score
from common import data_dir, BUILD
import smooth, raster

Z = 22   # screen px per source px
args = [a for a in sys.argv[1:] if not a.startswith('--')]
variant = args[0]; only = args[1] if len(args) > 1 else None
rep_p = os.path.join(data_dir(variant), 'port_report.json')
rep = json.load(open(rep_p)) if os.path.exists(rep_p) else {}
cells = []
for name, spec in overrides_of(variant).items():
    ch = chars_of(spec)[0]
    r = rep.get(name, {'method': 'hand'})
    if only and ch not in only:
        continue
    if not only and '--all' not in sys.argv and r['method'] in ('identical', 'transfer', 'hand'):
        continue
    gid = gid_for(variant, ch); m = mask_of(variant, gid)
    smooth.JSON_OVERRIDES = {ch: spec}
    st, dots, cuts = smooth.smooth_glyph(m, ch)
    cl = [dict(s, beziers=list(s['beziers'])) for s in st]          # centrelines before cap extension
    smooth.extend_caps(st)
    cov = raster.coverage(st, dots, cuts, spec.get('width', 1.0))
    sc = raster.score(cov, m)
    W = 10
    im = Image.new('RGB', (W*Z, 16*Z + 16), (255, 255, 255)); px = im.load()
    for y in range(16*Z):
        for x in range(W*Z):
            sx, sy = x // Z, y // Z
            a = m[sy][sx]; c = cov[sy][sx]
            lo, hi = ((160, 205, 240), (95, 80, 150)) if a else ((255, 255, 255), (240, 120, 160))
            px[x, y] = tuple(int(lo[i] + (hi[i] - lo[i])*c) for i in range(3))
    d = ImageDraw.Draw(im)
    for i in range(W+1):
        d.line([(i*Z, 0), (i*Z, 16*Z)], fill=(225, 225, 225))
    for i in range(17):
        d.line([(0, i*Z), (W*Z, i*Z)], fill=(225, 225, 225))
    for s in cl:
        for p0, c1, c2, p3 in s['beziers']:
            pts = [tuple((1-t)**3*np.array(p0) + 3*(1-t)**2*t*np.array(c1) + 3*(1-t)*t**2*np.array(c2) + t**3*np.array(p3))
                   for t in np.linspace(0, 1, 9)]
            d.line([(x*Z, y*Z) for x, y in pts], fill=(20, 20, 20), width=1)
    for poly in cuts:
        d.polygon([(x*Z, y*Z) for x, y in poly], outline=(220, 40, 40))
    tag = {'identical': '=', 'transfer': 'T', 'fuzzy': 'F', 'traced': 'R', 'hand': 'H'}.get(r['method'], '?')
    d.text((4, 16*Z + 3), f"{ch} {tag} {sc['err']:.1f} m{sc['missing']} x{sc['extra']}", fill=(0, 0, 0))
    cells.append(im)
if not cells:
    print('nothing to review'); sys.exit()
cols = 8
rows = (len(cells) + cols - 1) // cols
sheet = Image.new('RGB', (cols*(cells[0].width + 6), rows*(cells[0].height + 6)), (240, 240, 240))
for i, c in enumerate(cells):
    sheet.paste(c, ((i % cols)*(c.width + 6), (i // cols)*(c.height + 6)))
os.makedirs(os.path.join(BUILD, 'comparisons'), exist_ok=True)
out = os.path.join(BUILD, 'comparisons', f'{variant}_overrides_review.png')
sheet.save(out); print('wrote', out, len(cells), 'glyphs')
