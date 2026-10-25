"""Rebuild Emerald Rounded Game (or the EMERALD_VARIANT version of it) and render the given characters over
the matching Emerald Pixel Vector.

usage:  ./preview.sh "NMK"            (characters to preview; default: the overridden ones)
        ./preview.sh --no-build "a"   (skip rebuild, just render)
Output: build/preview/<char>.png per glyph (big, with pixel grid, both fonts overlaid) and
        build/preview/strip.png (all requested glyphs side by side in both fonts + the overlay).
Blue = Pixel Vector, pink = Rounded Game, dark = both agree."""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from render import *
from PIL import Image, ImageDraw

PXSIZE = 24           # screen pixels per source pixel in the big view
chars = [a for a in sys.argv[1:] if not a.startswith('--')]
text = ''.join(chars) if chars else None
if '--no-build' not in sys.argv:
    subprocess.run([os.path.join(ROOT, 'scripts', 'ff.sh'), os.path.join(ROOT, 'scripts', 'build_font.py'), 'smoothgame'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
if text is None:
    ov = sorted({c for fn in os.listdir(os.path.join(DATA, 'glyph_overrides')) if fn.endswith('.json')
                 for spec in [json.load(open(os.path.join(DATA, 'glyph_overrides', fn)))]
                 for c in ([spec['char']] if isinstance(spec['char'], str) else spec['char']) if len(c) == 1})
    text = ''.join(ov)
out = os.path.join(BUILD, 'preview', '' if VARIANT == 'normal' else VARIANT); os.makedirs(out, exist_ok=True)

def glyph_img(ch, key, px):
    """Render one glyph at px size, unhinted, return an 'L' alpha image aligned to the 16x16 cell."""
    face = freetype.Face(font_path(key)); face.set_char_size(px*64)
    face.load_char(ord(ch), freetype.FT_LOAD_NO_HINTING); face.glyph.render(freetype.FT_RENDER_MODE_NORMAL)
    bm = face.glyph.bitmap
    cell = Image.new('L', (px, px), 0)
    top = round(px*BASELINE_ROW/16) - face.glyph.bitmap_top; left = face.glyph.bitmap_left
    g = Image.frombytes('L', (bm.width, bm.rows), bytes(bm.buffer)) if bm.width else None
    if g is not None:
        cell.paste(g, (left, top))
    return cell, (face.glyph.advance.x >> 6)

COL = {'exact': (11, 142, 196), 'smoothgame': (210, 56, 111)}
strip = []
for ch in text:
    S = 16*PXSIZE
    im = Image.new('RGB', (S, S), (255, 255, 255)); d = ImageDraw.Draw(im)
    for i in range(17):
        c = (200, 200, 200) if i not in (3, 6, BASELINE_ROW) else (120, 120, 120)
        d.line([(i*PXSIZE, 0), (i*PXSIZE, S)], fill=(225, 225, 225)); d.line([(0, i*PXSIZE), (S, i*PXSIZE)], fill=c)
    for key in ('exact', 'smoothgame'):
        a, adv = glyph_img(ch, key, S)
        layer = Image.new('RGB', (S, S), COL[key])
        # multiply blend
        base = im.copy(); im = Image.composite(Image.blend(base, layer, 0.0), base, Image.new('L', (S, S), 0))
        px_ = im.load(); ap = a.load(); lc = COL[key]
        for y in range(S):
            for x in range(S):
                v = ap[x, y]
                if v:
                    o = px_[x, y]; t = v/255
                    px_[x, y] = tuple(int(o[i] * ((lc[i]/255)*t + (1-t))) for i in range(3))
        d = ImageDraw.Draw(im); d.line([(adv, 0), (adv, S)], fill=lc, width=2)
    d.text((4, 4), f'{ch}  U+{ord(ch):04X}', fill=(60, 60, 60))
    im.save(os.path.join(out, f'u{ord(ch):04X}.png')); strip.append(im)
# strip: both fonts as text + overlay cells
rows = [label(render_line(text, 'exact', 64)[0], 'Pixel Vector', 110), label(render_line(text, 'smoothgame', 64)[0], 'Rounded Game', 110)]
cells = Image.new('RGB', (sum(i.width for i in strip) + 8*(len(strip)-1), strip[0].height), (255, 255, 255)); x = 0
for i in strip:
    cells.paste(i, (x, 0)); x += i.width + 8
rows.append(cells)
stack(rows, gap=12).save(os.path.join(out, 'strip.png'))
print('wrote', os.path.join(out, 'strip.png'), 'and', ' '.join(f'u{ord(c):04X}.png' for c in text))
