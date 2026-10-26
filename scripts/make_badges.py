"""Smooth type and contest badges, and status pills: the game's art with its lettering set in the Badge or
Status font.

usage: python3 scripts/make_badges.py [badge|status]      (after that font is built; default badge)
badge: graphics/types/*.png in Emerald Rounded Badge Game.
status: the status-condition pills in Emerald Rounded Status Game, from both sheets the game has:
  status_<name>         graphics/interface/status_icons.png, 32x8 (party menu, summary): psn par slp frz brn
                        pkrs fnt frb
  battle_status_<name>  graphics/battle_interface/status.png, 24x8 (battle healthbox): psn par slp frz brn frb
  The pills' letters are white with no shadow, baseline y 7.
Writes build/badges/:
  <name>.svg        the whole 32x16 badge: the pixel background as exact squares (crisp at any scale) and
                    the lettering as smooth outlines at the art's own letter positions, with the art's
                    shadow (the letter repeated one pixel right, down, and right-and-down, behind it)
  <name>_blank.png  the 32x16 background with the lettering painted out in each row's body colour
  badges.json       per badge: text, letter positions (x of each letter's left edge, baseline y 11),
                    ink and shadow colours, for setting the text with the font over the blank badge
  status.json       the same for the status pills ("shadow" null, "font" per pill)
"""
import os, sys, json
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from common import BUILD, EXP_SRC, PX
from make_lettering import BADGES, BADGE_INK, BADGE_SHADOW, badge_runs, STATUS, STATUS_INK, STATUS_ICONS, status_runs
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

OUT = os.path.join(BUILD, 'badges')
HEALTHBOX = os.path.join(EXP_SRC, 'graphics/battle_interface/status.png')
HEALTHBOX_ROWS = ['PSN', 'PAR', 'SLP', 'FRZ', 'BRN', 'FRB']

def badge_items():
    """(name, text, image, [(x, mask rows)] of the lettering, ink index, shadow index or None, baseline)"""
    for name, text in BADGES.items():
        im = Image.open(os.path.join(EXP_SRC, 'graphics/types', name + '.png'))
        yield name, text, im, badge_runs(name), BADGE_INK, BADGE_SHADOW, 11

def status_items():
    for prefix, path, rows in (('status_', STATUS_ICONS, STATUS), ('battle_status_', HEALTHBOX, HEALTHBOX_ROWS)):
        sheet = Image.open(path)
        for row, text in enumerate(rows):
            im = sheet.crop((0, 8*row, sheet.size[0], 8*row + 8))
            im.putpalette(sheet.getpalette())
            runs = status_runs(path, row)
            if text == 'PkRS':          # P and k touch: one run, cut after P's 4 columns
                (x, g), rest = runs[0], runs[1:]
                runs = [(x, [r[:4] for r in g]), (x + 4, [r[4:] for r in g])] + rest
            yield prefix + text.lower(), text, im, runs, STATUS_INK, None, 7

def hexc(rgb):
    return '#%02x%02x%02x' % tuple(rgb)

def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'badge'
    FONT = os.path.join(BUILD, 'fonts', f'EmeraldRounded{which.title()}Game-Regular.ttf')
    font = TTFont(FONT)
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    def outline(ch, x, baseline):
        """SVG path of one letter with its left edge at pixel x and its baseline at y `baseline` (y down)."""
        pen = SVGPathPen(gs)
        gs[cmap[ord(ch)]].draw(TransformPen(pen, (1/PX, 0, 0, -1/PX, x, baseline)))
        return pen.getCommands()
    os.makedirs(OUT, exist_ok=True)
    layout = {}
    for name, text, im, runs, INK, SHADOW, baseline in (badge_items() if which == 'badge' else status_items()):
        pal = im.getpalette(); px = im.load(); W, H = im.size
        col = lambda i: pal[3*i:3*i + 3]
        # letterless background: each lettering pixel takes the commonest other colour of its row
        # (only the letters' columns: the healthbox pill's white rim is the ink's colour too)
        lettering = {(x0 + c, y) for x0, g in runs for c in range(len(g[0])) for y in range(H) if px[x0 + c, y] == INK}
        blank = im.copy(); bp = blank.load(); fill = 0
        for y in range(H):
            body = [px[x, y] for x in range(W) if px[x, y] not in (0, INK, SHADOW)]
            fill = max(set(body), key=body.count) if body else fill     # a row that is all lettering: the row above's
            for x in range(W):
                if (x, y) in lettering or (SHADOW is not None and px[x, y] == SHADOW):
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
        assert len(runs) == len(text), (name, len(runs))
        letters = [(ch, x) for ch, (x, _) in zip(text, runs)]
        ink = ''.join(outline(ch, x, baseline) for ch, x in letters)
        ink_c = hexc(col(INK)); sh_c = hexc(col(SHADOW)) if SHADOW is not None else None
        shadow = (f'<g fill="{sh_c}">' + ''.join(f'<path transform="translate({dx} {dy})" d="{ink}"/>' for dx, dy in ((1, 0), (0, 1), (1, 1)))
                  + '</g>\n') if sh_c else ''
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W*8}" height="{H*8}">\n'
               f'<g shape-rendering="crispEdges">\n' + '\n'.join(rects) + '\n</g>\n'
               + shadow + f'<path fill="{ink_c}" d="{ink}"/>\n</svg>\n')
        open(os.path.join(OUT, name + '.svg'), 'w').write(svg)
        layout[name] = {'text': text, 'size': [W, H], 'baseline': baseline,
                        'letters': [{'char': ch, 'x': x} for ch, x in letters],
                        'ink': ink_c, 'shadow': sh_c, 'shadow_offsets': [[1, 0], [0, 1], [1, 1]] if sh_c else [],
                        'svg': name + '.svg', 'blank': name + '_blank.png'}
        if which == 'status':
            layout[name]['font'] = os.path.basename(FONT)
    json.dump({'font': os.path.basename(FONT), 'units_per_pixel': PX, 'badges': layout},
              open(os.path.join(OUT, 'badges.json' if which == 'badge' else 'status.json'), 'w'), indent=1)
    print(which, 'pills:' if which == 'status' else 'badges:', len(layout), '->', OUT)

if __name__ == '__main__':
    main()
