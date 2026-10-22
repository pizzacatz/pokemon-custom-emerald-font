"""Extract foreground masks, mapping and exact pixel SVG outlines from latin_normal.png.
Outputs: data/mapping.json, data/masks/*.json, data/masks/sheet_fg.png, data/svg_exact/*.svg
"""
import re, os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def parse_charmap(path):
    """Return {glyph_id: {'unicode': cp or None, 'name': str}} for the Latin section."""
    out = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('@'):
                break  # Hiragana/Katakana/other sections follow
            m = re.match(r"^(\S+|'(?:\\.|[^'])+')\s*=\s*([0-9A-F]{2}(?:\s+[0-9A-F]{2})*)\s*$", line)
            if not m:
                continue
            key, codes = m.group(1), m.group(2).split()
            if len(codes) != 1:
                continue  # multi-byte sequences (PKMN, POKEBLOCK, TALL_PLUS) are not single glyphs
            gid = int(codes[0], 16)
            if key.startswith("'"):
                ch = key[1:-1]
                if ch.startswith('\\'):
                    ch = ch[1:]
                assert len(ch) == 1, (line, ch)
                out.setdefault(gid, {'unicode': [], 'name': None})['unicode'].append(ord(ch))
            else:
                out.setdefault(gid, {'unicode': [], 'name': None})['name'] = key
    return out

def parse_widths(path):
    src = open(path).read()
    m = re.search(r'gFontNormalLatinGlyphWidths\[\] = \{(.*?)\};', src, re.S)
    w = [int(x) for x in re.findall(r'\d+', m.group(1))]
    assert len(w) == 512, len(w)
    return w

def cell_mask(px, gid, value):
    r, c = divmod(gid, 16)
    return [[1 if px[c*CELL+x, r*CELL+y] == value else 0 for x in range(CELL)] for y in range(CELL)]

# ---------- exact outline tracing ----------
def trace_mask(mask):
    """Return list of closed contours (lists of (x,y) integer vertices, y down).
    Outer contours are clockwise in y-down coords (== counter-clockwise in y-up font coords),
    holes the opposite. Diagonal-only contacts are split so contours never touch at a vertex."""
    h, w = len(mask), len(mask[0])
    edges = {}  # directed edge (p,q) -> count; edges shared by two pixels cancel
    def add(p, q):
        if (q, p) in edges:
            del edges[(q, p)]
        else:
            edges[(p, q)] = 1
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                # clockwise in y-down screen coords: top, right, bottom, left
                add((x, y), (x+1, y)); add((x+1, y), (x+1, y+1))
                add((x+1, y+1), (x, y+1)); add((x, y+1), (x, y))
    out = {}
    for p, q in edges:
        out.setdefault(p, []).append(q)
    contours = []
    while edges:
        start, cur = next(iter(edges))
        contour = [start]
        prev = start
        edges.pop((start, cur))
        out[start].remove(cur)
        while cur != start:
            contour.append(cur)
            nxts = out[cur]
            if len(nxts) == 1:
                nxt = nxts[0]
            else:
                # vertex touched by diagonal pixels: turn so the contour stays on its own region.
                # incoming direction d; prefer the "right turn" (clockwise) which keeps the
                # already-traced area on the inside and avoids crossing into the other blob.
                d = (cur[0]-prev[0], cur[1]-prev[1])
                right = (-d[1], d[0])  # rotate 90 deg in y-down coords == turn right
                cand = [q for q in nxts if (q[0]-cur[0], q[1]-cur[1]) == right]
                nxt = cand[0] if cand else nxts[0]
            out[cur].remove(nxt)
            edges.pop((cur, nxt))
            prev, cur = cur, nxt
        contours.append(simplify(contour))
    return contours

def simplify(c):
    """Drop collinear (redundant) points on straight runs."""
    n = len(c)
    keep = []
    for i in range(n):
        a, b, d = c[i-1], c[i], c[(i+1) % n]
        if (b[0]-a[0])*(d[1]-b[1]) - (b[1]-a[1])*(d[0]-b[0]) != 0:
            keep.append(b)
    return keep

def rasterize(contours, w, h):
    """Nonzero-winding point-in-polygon at pixel centres -> mask. Exact for axis-aligned integer polys."""
    m = [[0]*w for _ in range(h)]
    for y in range(h):
        py = y + 0.5
        for x in range(w):
            px_ = x + 0.5
            wn = 0
            for c in contours:
                n = len(c)
                for i in range(n):
                    (x0, y0), (x1, y1) = c[i], c[(i+1) % n]
                    if y0 <= py < y1 or y1 <= py < y0:
                        t = (py - y0) / (y1 - y0)
                        xi = x0 + t*(x1 - x0)
                        if xi > px_:
                            wn += 1 if y1 > y0 else -1
            m[y][x] = 1 if wn != 0 else 0
    return m

def svg_for(contours, w=CELL, h=CELL):
    d = path_from_contours(contours)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w*10}" height="{h*10}">\n'
            f'<path d="{d}" fill="#000" fill-rule="nonzero"/>\n</svg>\n')

def main():
    im = Image.open(os.path.join(SRC, 'graphics/fonts/latin_normal.png'))
    assert im.size == (256, 512) and im.mode == 'P', (im.size, im.mode)
    px = im.load()
    widths = parse_widths(os.path.join(SRC, 'src/fonts.c'))
    cmap = parse_charmap(os.path.join(SRC, 'charmap.txt'))
    os.makedirs(os.path.join(DATA, 'masks'), exist_ok=True)
    os.makedirs(os.path.join(DATA, 'svg_exact'), exist_ok=True)
    sheet = Image.new('L', (256, 512), 255)
    mapping = {}
    mismatches = []
    for gid in range(512):
        fg = cell_mask(px, gid, FG)
        sh = cell_mask(px, gid, SHADOW)
        ink = sum(map(sum, fg))
        ink_cols = [x for x in range(CELL) if any(fg[y][x] for y in range(CELL))]
        ink_rows = [y for y in range(CELL) if fg[y][x] for x in range(CELL) if fg[y][x]] if False else [y for y in range(CELL) if any(fg[y])]
        contours = trace_mask(fg) if ink else []
        if ink:
            r = rasterize(contours, CELL, CELL)
            if r != fg:
                mismatches.append(gid)
        for y in range(CELL):
            for x in range(CELL):
                if fg[y][x]:
                    sheet.putpixel(((gid % 16)*16 + x, (gid//16)*16 + y), 0)
        info = cmap.get(gid, {'unicode': [], 'name': None})
        entry = {
            'id': gid, 'unicode': info['unicode'], 'name': info['name'],
            'width': widths[gid], 'ink': ink,
            'ink_xmin': min(ink_cols) if ink_cols else None,
            'ink_xmax': max(ink_cols)+1 if ink_cols else None,
            'ink_ymin': min(ink_rows) if ink_rows else None,
            'ink_ymax': max(ink_rows)+1 if ink_rows else None,
            'shadow_px': sum(map(sum, sh)),
            'contours': len(contours),
        }
        mapping[str(gid)] = entry
        if ink or info['unicode'] or info['name']:
            with open(os.path.join(DATA, 'masks', f'{gid:03d}.json'), 'w') as f:
                json.dump({'id': gid, 'fg': fg, 'shadow': sh}, f)
            with open(os.path.join(DATA, 'svg_exact', f'{gid:03d}.svg'), 'w') as f:
                f.write(svg_for(contours))
            with open(os.path.join(DATA, 'svg_exact', f'{gid:03d}.json'), 'w') as f:
                json.dump(contours, f)
    sheet.save(os.path.join(DATA, 'masks', 'sheet_fg.png'))
    save_json('mapping.json', mapping)
    print('glyphs with ink:', sum(1 for e in mapping.values() if e['ink']))
    print('mapped to unicode:', sum(1 for e in mapping.values() if e['unicode']))
    print('raster mismatches:', mismatches)
    # metrics summary
    def rows(ch):
        gid = next(int(k) for k, e in mapping.items() if ord(ch) in e['unicode'])
        e = mapping[str(gid)]; return gid, e['ink_ymin'], e['ink_ymax']
    for ch in 'HxgpAbé':
        print(ch, rows(ch))
    unmapped_ink = [(k, e['name']) for k, e in mapping.items() if e['ink'] and not e['unicode']]
    print('ink but no unicode:', unmapped_ink)

if __name__ == '__main__':
    main()
