"""Synthesize the sheets and width tables of two pieces of lettering baked into Emerald's graphics.

usage: python3 scripts/make_lettering.py header|badge      (run after the Short font is extracted)

header: the summary screen's section headers.
The summary screen's headers (PROFILE, ABILITY, TRAINER MEMO, ITEM, RIBBON, STATS, EXP., MOVES,
DESCRIPTION, STATE, EFFECT) are baked into graphics/summary_screen/tiles.png in a 5x7 capital alphabet
with a 6 px advance. It is Short's capitals with one middle row fewer, except M N S X, which are redrawn.
Writes source/derived/latin_header.png (a sheet laid out like the game's, palette index 1 = ink) and
source/derived/latin_header_widths.json, which extract.py reads for the "header" font:
- every cell starts as Short's with its 7th ink row of the capital band (row 9) removed, so digits,
  punctuation and accented letters exist too;
- the 19 letters and the period that the art shows replace their cells, and G H J K Q U W Z are Short's
  with the repeated row removed that keeps each letter's shape (row 9, or 7 for K and Z, 5 for Q);
- a few symbols are drawn in the header's style; lowercase cells carry the capitals, so either case works.

badge: the condensed capitals of the type badges (graphics/types/*.png: NORMAL, FIRE, ... and the contest
badges COOL, BEAUTY, ...), white (palette index 15) with a shadow (14), 7 rows tall at rows 4..10 of the
32x16 badge. Letters are 4 px wide (I T Y 3), one pixel apart, so a glyph's advance is its width + 1.
The badges show 21 letters and "?"; J Q V X Z are drawn here in the same style. Every other cell is the
header font's, and lowercase cells again carry the capitals.
"""
import os, sys, json
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, EXP_SRC, data_dir, CELL

TILES = os.path.join(EXP_SRC, 'graphics/summary_screen/tiles.png')
OUT = os.path.join(ROOT, 'source', 'derived')
INK = 2                   # palette index of the white letters in tiles.png (6 is their shadow)
TOP = 4                   # the capital band of the header font is rows 4..10, baseline row 11 like Short
WORDS = [('PROFILE', 2, 64), ('ITEM', 74, 64), ('ABILITY', 2, 72), ('RIBBON', 74, 72), ('STATS', 74, 80),
         ('STATE', 2, 88), ('EXP.', 74, 88), ('MOVES', 2, 96), ('EFFECT', 82, 96), ('DESCRIPTION', 2, 104),
         ('TRAINER', 2, 112)]
DROP = {'K': 7, 'Z': 7, 'Q': 5}   # Short row removed for these (default 9)
SYMBOLS = {   # 7 rows of the capital band, drawn in the header's style
    '!': ['#', '#', '#', '#', '#', '.', '#'],
    '?': ['.###.', '#...#', '....#', '...#.', '..#..', '.....', '..#..'],
    '-': ['.....', '.....', '.....', '#####', '.....', '.....', '.....'],
    ':': ['..', '##', '##', '..', '..', '##', '##'],
    '/': ['....#', '...#.', '...#.', '..#..', '.#...', '.#...', '#....'],
    "'": ['#', '#', '.', '.', '.', '.', '.'],
}
WIDTHS = {' ': 3, '.': 3, '!': 2, ':': 3, "'": 2, '-': 6, '?': 6, '/': 6}

BADGES = {'normal': 'NORMAL', 'fight': 'FIGHT', 'flying': 'FLYING', 'poison': 'POISON', 'ground': 'GROUND',
          'rock': 'ROCK', 'bug': 'BUG', 'ghost': 'GHOST', 'steel': 'STEEL', 'mystery': '???', 'fire': 'FIRE',
          'water': 'WATER', 'grass': 'GRASS', 'electric': 'ELECTR', 'psychic': 'PSYCHC', 'ice': 'ICE',
          'dragon': 'DRAGON', 'dark': 'DARK', 'fairy': 'FAIRY', 'stellar': 'STELLR', 'none': '???',
          'contest_cool': 'COOL', 'contest_beauty': 'BEAUTY', 'contest_cute': 'CUTE', 'contest_smart': 'SMART',
          'contest_tough': 'TOUGH'}
BADGE_INK, BADGE_SHADOW = 15, 14
BADGE_EXTRA = {   # letters no badge shows, drawn in the badge style
    'J': ['...#', '...#', '...#', '...#', '...#', '#..#', '.##.'],
    'Q': ['.##.', '#..#', '#..#', '#..#', '#..#', '#.#.', '.#.#'],
    'V': ['#..#', '#..#', '#..#', '#..#', '#..#', '.##.', '.##.'],
    'X': ['#..#', '#..#', '.##.', '.##.', '.##.', '#..#', '#..#'],
    'Z': ['####', '...#', '..#.', '..#.', '.#..', '#...', '####'],
}

def badge_runs(name):
    """The badge's lettering: [(x of the letter's first column, [7 rows of 0/1])] in reading order."""
    px = Image.open(os.path.join(EXP_SRC, 'graphics/types', name + '.png')).load()
    cols = [x for x in range(32) if any(px[x, y] == BADGE_INK for y in range(16))]
    runs = []
    for x in cols:
        if runs and x == runs[-1][-1] + 1:
            runs[-1].append(x)
        else:
            runs.append([x])
    return [(r[0], [[1 if px[x, y] == BADGE_INK else 0 for x in r] for y in range(TOP, TOP + 7)]) for r in runs]

def badge_letters():
    out = {}
    for name, text in BADGES.items():
        runs = badge_runs(name)
        assert len(runs) == len(text), (name, len(runs))
        for ch, (_, g) in zip(text, runs):
            assert out.get(ch, g) == g, f'badge {ch} drawn two ways'
            out[ch] = g
    return out

def art_letters():
    px = Image.open(TILES).load()
    out = {}
    for word, x0, y0 in WORDS:
        for i, ch in enumerate(word):
            g = [[1 if px[x0 + 6*i + c, y0 + r] == INK else 0 for c in range(5)] for r in range(7)]
            assert out.get(ch, g) == g, f'{ch} drawn two ways'
            out[ch] = g
    return out

def header_cells():
    sd = data_dir('short')
    smap = json.load(open(os.path.join(sd, 'mapping.json')))
    gid_of = {cp: int(k) for k, e in smap.items() for cp in e['unicode']}
    def short_mask(gid):
        p = os.path.join(sd, 'masks', f'{gid:03d}.json')
        return json.load(open(p))['fg'] if os.path.exists(p) else [[0]*CELL for _ in range(CELL)]
    def drop(m, row):
        """Remove `row`, moving the rows above it down one (the baseline and descenders stay put)."""
        return [[0]*CELL] + m[:row] + m[row+1:]
    cells, widths = {}, {}
    for k, e in smap.items():
        gid = int(k)
        cells[gid] = drop(short_mask(gid), 9)
        widths[gid] = e['width']
    def put(ch, rows, width=None):
        m = [[0]*CELL for _ in range(CELL)]
        for r, line in enumerate(rows):
            for c, v in enumerate(line):
                m[TOP + r][c] = 1 if v in (1, '#') else 0
        for cp in (ord(ch),) + ((ord(ch.lower()),) if ch.isalpha() else ()):
            if cp in gid_of:
                cells[gid_of[cp]] = m
                widths[gid_of[cp]] = width or 6
    art = art_letters()
    for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        if ch in art:
            put(ch, art[ch])
        else:
            m = drop(short_mask(gid_of[ord(ch)]), DROP.get(ch, 9))
            put(ch, [r[:6] for r in m[TOP:TOP + 7]])    # Q's tail reaches into the sixth column
    put('.', art['.'][:7], WIDTHS['.'])
    for ch, rows in SYMBOLS.items():
        put(ch, rows, WIDTHS[ch])
    widths[gid_of[ord(' ')]] = WIDTHS[' ']
    print('header: art letters', ''.join(sorted(art)), '| derived', ''.join(c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if c not in art))
    return cells, widths, put, gid_of

def badge_cells():
    cells, widths, put, gid_of = header_cells()
    art = badge_letters()
    for ch, g in list(art.items()) + list(BADGE_EXTRA.items()):
        put(ch, g, len(g[0]) + 1)
    widths[gid_of[ord(' ')]] = 3
    print('badge: art letters', ''.join(sorted(art)), '| drawn', ''.join(BADGE_EXTRA))
    return cells, widths

def write_sheet(name, cells, widths):
    # 16 x 32 cells of 16 px, palette index 1 = ink, 0 = background
    im = Image.new('P', (256, 512), 0)
    im.putpalette([255, 255, 255, 0, 0, 0, 160, 160, 160, 255, 255, 255] + [0, 0, 0]*252)
    px = im.load()
    for gid, m in cells.items():
        r, c = divmod(gid, 16)
        for y in range(CELL):
            for x in range(CELL):
                if m[y][x]:
                    px[c*CELL + x, r*CELL + y] = 1
    os.makedirs(OUT, exist_ok=True)
    im.save(os.path.join(OUT, f'latin_{name}.png'))
    json.dump([widths.get(g, 0) for g in range(512)], open(os.path.join(OUT, f'latin_{name}_widths.json'), 'w'))

def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'header'
    if which == 'header':
        cells, widths, _, _ = header_cells()
    else:
        cells, widths = badge_cells()
    write_sheet(which, cells, widths)

if __name__ == '__main__':
    main()
