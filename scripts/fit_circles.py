"""Model the circled digits (1)-(9) as a true circle around a traced digit.

usage: python3 scripts/fit_circles.py [variant ...]   (default: all fonts)
The pixel ring is about 9 px across (7 in the Small fonts) and a pixel taller or shorter than it is wide,
which a trace through the pixel centres turns into an octagon. Here the ring becomes one "circle" stroke
centred on the ring's ink box, its radius splitting the difference between the box's width and height
(the stroke is 1 px wide, so the outer diameter is (width + height) / 2). The ring's pixels are those all
nine glyphs share, away from the middle; the rest is the digit, traced in the usual convention
(port_overrides.trace); where the trace misses a pixel (the 10-row fonts' 2 and 3) a model drawn here
is used instead. The header and badge fonts' rings are a row short of a circle around their digits, so
they take Normal's models, whose ring starts on the same row. The result is written as a glyph override, editable in the glyph editor;
ported fonts record it as method "fitted", which port_overrides.py leaves alone."""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(__file__))
from common import VARIANTS, data_dir
from port_overrides import trace, model_score

DIGITS = range(0xE10A, 0xE113)    # CHAR_CIRCLED_1..9, also mapped to U+2460..2468
DRAWN = {   # digits the trace gets wrong in the 10-row ring (Normal, Narrow, Short and their narrower fonts),
            # placed for Normal's ring (centre y 7); moved with the ring in the other fonts
    0xE10B: [[3.5, 5.5, 0], [3.5, 4.5, 0], [5.5, 4.5, 0], [5.5, 6.5, 0], [3.5, 8.5, 0], [3.5, 9.5, 0], [5.5, 9.5, 0]],
    0xE10C: [[3.5, 4.5, 0], [5.5, 4.5, 0], [5.5, 5.5, 0], [4.5, 6.5, 0], [5.5, 7.5, 0], [5.5, 9.5, 0], [3.5, 9.5, 0],
             [3.5, 8.5, 0]],
}
BORROW = {'header': 'normal', 'badge': 'normal'}

def fit(mask, shared):
    ys = [y for y, r in enumerate(mask) if any(r)]
    xs = [x for r in mask for x, c in enumerate(r) if c]
    x0, x1, y0, y1 = min(xs), max(xs) + 1, ys[0], ys[-1] + 1
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = ((x1 - x0) + (y1 - y0)) / 4 - 0.5          # centreline radius of a 1 px stroke
    # the ring: pixels every circled digit has, except the few near the middle the digits happen to share
    ring = lambda x, y: shared[y][x] and math.hypot(x + 0.5 - cx, y + 0.5 - cy) > r - 1
    inner = [[0 if ring(x, y) else c for x, c in enumerate(row)] for y, row in enumerate(mask)]
    return {'center': [cx, cy], 'radius': r}, inner

def main():
    for v in sys.argv[1:] or list(VARIANTS):
        d = data_dir(v)
        mp = json.load(open(os.path.join(d, 'mapping.json'))); cps = json.load(open(os.path.join(d, 'codepoints.json')))
        rp = os.path.join(d, 'port_report.json')
        rep = json.load(open(rp)) if v != 'normal' and os.path.exists(rp) else None
        gids = {cp: next((k for k, e in cps.items() if cp in e['codepoints']), None) for cp in DIGITS}
        masks = {cp: json.load(open(os.path.join(d, 'masks', f'{int(g):03d}.json')))['fg'] for cp, g in gids.items() if g}
        masks = {cp: m for cp, m in masks.items() if any(map(any, m))}
        if not masks:
            continue
        shared = [[all(m[y][x] for m in masks.values()) for x in range(len(row))] for y, row in enumerate(next(iter(masks.values())))]
        done = []
        for cp, mask in masks.items():
            gid = gids[cp]
            aliases = list(dict.fromkeys([cp] + mp.get(gid, {}).get('unicode', []) + cps[gid]['codepoints']))
            chars = [chr(c) for c in aliases]
            name = f'u{cp:04X}'
            if v in BORROW:
                spec = json.load(open(os.path.join(data_dir(BORROW[v]), 'glyph_overrides', name + '.json'), encoding='utf-8'))
                spec['_ported'] = f'{BORROW[v]}\'s circled digit (fit_circles.py)'
            else:
                circle, inner = fit(mask, shared)
                digit = trace(inner, chars[0])
                spec = {'char': chars if len(chars) > 1 else chars[0], 'rows': [0, 16], 'width': 1, 'joint_radius': 0,
                        'strokes': [{'circle': circle}] + digit['strokes'], 'dots': digit['dots'], 'join': 'miter',
                        'dot_shape': 'circle', 'dot_corner': 0.25,
                        '_ported': 'circle and traced digit fitted to the pixels by fit_circles.py'}
                if cp in DRAWN:
                    dy = circle['center'][1] - 7
                    drawn = dict(spec, strokes=[{'circle': circle}, {'points': [[x, y + dy, j] for x, y, j in DRAWN[cp]]}], dots=[])
                    if model_score(drawn, mask, chars[0])['missing'] < model_score(spec, mask, chars[0])['missing']:
                        spec = drawn
            with open(os.path.join(d, 'glyph_overrides', name + '.json'), 'w', encoding='utf-8') as f:
                json.dump(spec, f, indent=1, ensure_ascii=False)
            if rep is not None:
                rep[name] = {'char': spec['char'], 'method': 'fitted', 'from': None, 'note': 'fit_circles.py'}
            done.append(name)
        if rep is not None:
            json.dump(rep, open(rp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print(v, 'circled digits:', len(done))

if __name__ == '__main__':
    main()
