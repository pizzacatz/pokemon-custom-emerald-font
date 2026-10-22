"""FontForge outline validation for every built font (self-intersections, open contours,
wrong direction, missing extrema...). usage: scripts/ff.sh scripts/check_geometry.py"""
import sys, os, json
import fontforge
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

FLAGS = {0x1: 'open-contour', 0x2: 'self-intersecting', 0x4: 'wrong-direction', 0x8: 'flipped-refs',
         0x10: 'missing-extrema', 0x20: 'bad-glyph-name', 0x40: 'too-many-points', 0x80: 'too-many-hints',
         0x100: 'bad-bbox', 0x200: 'too-many-points-ttf', 0x400: 'ref-depth', 0x800: 'ref-out-of-bounds',
         0x1000: 'ref-off-by-one', 0x2000: 'distance-too-big', 0x4000: 'non-integral', 0x8000: 'point-too-far',
         0x20000: 'self-intersect-ok?', 0x40000: 'overlapping-hints', 0x80000: 'duplicate-glyph-name',
         0x100000: 'duplicate-unicode', 0x200000: 'overlapping-contours'}
IGNORE = {'missing-extrema', 'too-many-points', 'too-many-hints', 'overlapping-hints', 'non-integral'}

out = {}
for fn in sorted(os.listdir(os.path.join(BUILD, 'fonts'))):
    if not fn.endswith('.ttf'):
        continue
    f = fontforge.open(os.path.join(BUILD, 'fonts', fn))
    problems = {}
    for g in f.glyphs():
        v = g.validate(True)
        names = [n for b, n in FLAGS.items() if v & b and n not in IGNORE]
        if names:
            problems[f'{g.glyphname} U+{g.unicode:04X}' if g.unicode >= 0 else g.glyphname] = names
    out[fn] = problems
    print(fn, 'glyphs:', len(list(f.glyphs())), 'problem glyphs:', len(problems))
    for k, v in list(problems.items())[:40]:
        print('   ', k, v)
with open(os.path.join(BUILD, 'geometry_check.json'), 'w') as fh:
    json.dump(out, fh, indent=1)
