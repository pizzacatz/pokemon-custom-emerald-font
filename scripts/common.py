"""Shared constants and helpers for the Emerald font project.

Emerald has five Latin fonts, and pokeemerald-expansion adds four narrower ones. Which one a script works on is chosen with the environment variable
EMERALD_VARIANT (default "normal"). Normal keeps its data at data/; every other variant has the same
layout under data/<variant>/ (mapping.json, masks/, svg_*/, glyph_overrides/ ...)."""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'source', 'pokeemerald')
EXP_SRC = os.path.join(ROOT, 'source', 'pokeemerald-expansion')   # glyphs the expansion adds in blank cells
BUILD = os.path.join(ROOT, 'build')

# sheet, width table in src/fonts.c, baseline row, game line pitch (FontInfo.maxLetterHeight; Small Narrow's
# and Small Narrower's 8 is too tight for their own descenders, so they use Small's 12), the name fragment used
# in font names, and for the expansion-only fonts the source tree their sheet and widths come from.
VARIANTS = {
    'normal':       dict(sheet='latin_normal.png',       widths='gFontNormalLatinGlyphWidths',      baseline=12, line=16, name=''),
    'narrow':       dict(sheet='latin_narrow.png',       widths='gFontNarrowLatinGlyphWidths',      baseline=12, line=16, name='Narrow'),
    'small':        dict(sheet='latin_small.png',        widths='gFontSmallLatinGlyphWidths',       baseline=11, line=12, name='Small'),
    'short':        dict(sheet='latin_short.png',        widths='gFontShortLatinGlyphWidths',       baseline=11, line=14, name='Short'),
    'small_narrow': dict(sheet='latin_small_narrow.png', widths='gFontSmallNarrowLatinGlyphWidths', baseline=11, line=12, name='Small Narrow'),
    # pokeemerald-expansion only
    'narrower':       dict(sheet='latin_narrower.png',       widths='gFontNarrowerLatinGlyphWidths',      baseline=12, line=16, name='Narrower', expansion=True),
    'small_narrower': dict(sheet='latin_small_narrower.png', widths='gFontSmallNarrowerLatinGlyphWidths', baseline=11, line=12, name='Small Narrower', expansion=True),
    'short_narrow':   dict(sheet='latin_short_narrow.png',   widths='gFontShortNarrowLatinGlyphWidths',   baseline=11, line=14, name='Short Narrow', expansion=True),
    'short_narrower': dict(sheet='latin_short_narrower.png', widths='gFontShortNarrowerLatinGlyphWidths', baseline=11, line=14, name='Short Narrower', expansion=True),
}
VARIANT = os.environ.get('EMERALD_VARIANT', 'normal')
if VARIANT not in VARIANTS:
    raise SystemExit(f'EMERALD_VARIANT={VARIANT!r}: expected one of {", ".join(VARIANTS)}')
VINFO = VARIANTS[VARIANT]

def data_dir(variant):
    return os.path.join(ROOT, 'data') if variant == 'normal' else os.path.join(ROOT, 'data', variant)

DATA = data_dir(VARIANT)
CELL = 16          # sheet cell size in px
GLYPH_H = 15       # rows actually used by the game (row 15 is padding)
BASELINE_ROW = VINFO['baseline']  # pixel row index of the first row *below* the baseline
PX = 100           # font units per source pixel
UPM = 1600         # 16 px cell == 1 em
FG, SHADOW = 1, 2  # palette indices in the font sheets (0 and 3 are background)

def load_json(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)

def save_json(name, obj):
    with open(os.path.join(DATA, name), 'w') as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)

def path_from_contours(contours, scale=1.0, flip_h=None, prec=3):
    """contours: list of lists of (x,y) in pixel coords (y down). Returns SVG path d."""
    parts = []
    for c in contours:
        pts = []
        for x, y in c:
            if flip_h is not None:
                y = flip_h - y
            pts.append((round(x*scale, prec), round(y*scale, prec)))
        parts.append('M' + ' L'.join(f'{x:g} {y:g}' for x, y in pts) + ' Z')
    return ' '.join(parts)
