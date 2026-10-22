"""Shared constants and helpers for the Emerald font project."""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'source', 'pokeemerald')
DATA = os.path.join(ROOT, 'data')
BUILD = os.path.join(ROOT, 'build')
CELL = 16          # sheet cell size in px
GLYPH_H = 15       # rows actually used by the game (row 15 is padding)
BASELINE_ROW = 12  # pixel row index of the first row *below* the baseline
PX = 100           # font units per source pixel
UPM = 1600         # 16 px cell == 1 em
FG, SHADOW = 1, 2  # palette indices in latin_normal.png (0 and 3 are background)

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
