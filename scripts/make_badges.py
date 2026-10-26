"""Smooth type and contest badges: graphics/types/*.png with their lettering set in Emerald Rounded Badge Game.

usage: python3 scripts/make_badges.py      (after the badge font is built)
Writes build/badges/:
  <name>.svg        the whole 32x16 badge: the pixel background as exact squares (crisp at any scale) and
                    the lettering as smooth outlines at the art's own letter positions, with the art's
                    shadow (the letter repeated one pixel right, down, and right-and-down, behind it)
  <name>_blank.png  the 32x16 background with the lettering painted out in each row's body colour
  badges.json       per badge: text, letter positions (x of each letter's left edge, baseline y 11),
                    ink and shadow colours, for setting the text with the font over the blank badge
"""
import os, sys, json
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from common import BUILD, EXP_SRC, PX
from make_lettering import BADGES, BADGE_INK, BADGE_SHADOW, badge_runs
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

BASELINE = 11
FONT = os.path.join(BUILD, 'fonts', 'EmeraldRoundedBadgeGame-Regular.ttf')
OUT = os.path.join(BUILD, 'badges')

def hexc(rgb):
    return '#%02x%02x%02x' % tuple(rgb)

def main():
    font = TTFont(FONT)
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    def outline(ch, x):
        """SVG path of one letter with its left edge at pixel x and its baseline at BASELINE (y down)."""
        pen = SVGPathPen(gs)
        gs[cmap[ord(ch)]].draw(TransformPen(pen, (1/PX, 0, 0, -1/PX, x, BASELINE)))
        return pen.getCommands()
    os.makedirs(OUT, exist_ok=True)
    layout = {}
    for name, text in BADGES.items():
        im = Image.open(os.path.join(EXP_SRC, 'graphics/types', name + '.png'))
        pal = im.getpalette(); px = im.load(); W, H = im.size
        col = lambda i: pal[3*i:3*i + 3]
        # letterless background: each lettering pixel takes the commonest other colour of its row
        blank = im.copy(); bp = blank.load(); fill = 0
        for y in range(H):
            body = [px[x, y] for x in range(W) if px[x, y] not in (0, BADGE_INK, BADGE_SHADOW)]
            fill = max(set(body), key=body.count) if body else fill     # a row that is all lettering: the row above's
            for x in range(W):
                if px[x, y] in (BADGE_INK, BADGE_SHADOW):
                    bp[x, y] = fill
        blank.save(os.path.join(OUT, name + '_blank.png'), transparency=0)   # index 0 is transparent on the GBA
        # background squares, merged into runs along each row; index 0 is transparent on the GBA
        rects = []
        for y in range(H):
            x = 0
            while x < W:
                i = bp[x, y]; x1 = x
                while x1 < W and bp[x1, y] == i:
                    x1 += 1
                if i != 0:
                    rects.append(f'<rect x="{x}" y="{y}" width="{x1 - x}" height="1" fill="{hexc(col(i))}"/>')
                x = x1
        letters = [(ch, x) for ch, (x, _) in zip(text, badge_runs(name))]
        ink = ''.join(outline(ch, x) for ch, x in letters)
        ink_c, sh_c = hexc(col(BADGE_INK)), hexc(col(BADGE_SHADOW))
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W*8}" height="{H*8}">\n'
               f'<g shape-rendering="crispEdges">\n' + '\n'.join(rects) + '\n</g>\n'
               f'<g fill="{sh_c}">' + ''.join(f'<path transform="translate({dx} {dy})" d="{ink}"/>' for dx, dy in ((1, 0), (0, 1), (1, 1))) + '</g>\n'
               f'<path fill="{ink_c}" d="{ink}"/>\n</svg>\n')
        open(os.path.join(OUT, name + '.svg'), 'w').write(svg)
        layout[name] = {'text': text, 'size': [W, H], 'baseline': BASELINE,
                        'letters': [{'char': ch, 'x': x} for ch, x in letters],
                        'ink': ink_c, 'shadow': sh_c, 'shadow_offsets': [[1, 0], [0, 1], [1, 1]],
                        'svg': name + '.svg', 'blank': name + '_blank.png'}
    json.dump({'font': os.path.basename(FONT), 'units_per_pixel': PX, 'badges': layout},
              open(os.path.join(OUT, 'badges.json'), 'w'), indent=1)
    print('badges:', len(layout), '->', OUT)

if __name__ == '__main__':
    main()
