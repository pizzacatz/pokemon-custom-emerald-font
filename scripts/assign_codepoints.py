"""Assign final code points and glyph names.

Base: charmap.txt single-byte Latin mappings (from extract.py).
Extra symbols (CHAR_EXTRA_SYMBOL 0xF9 prefix -> sheet ids 0x100..0x1FF) and other inked glyphs
with no Unicode equivalent go to the Private Use Area at U+E000 + sheet id, so nothing is
silently merged with an unrelated Unicode character. A few extra symbols have an unambiguous
Unicode form (arrows, circled digits, numero sign) and additionally get that code point.
Output: data/codepoints.json  {gid: {'codepoints': [...], 'name': glyphname, 'source': ...}}
"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *

PUA_BASE = 0xE000

def extra_names(charmap_path):
    """Names of the 0xF9-prefixed extra symbols: {gid: NAME}."""
    names = {}
    for line in open(charmap_path, encoding='utf-8'):
        m = re.match(r'^(\w+)\s*=\s*F9 ([0-9A-F]{2})', line)
        if m:
            names[0x100 + int(m.group(2), 16)] = m.group(1)
    return names

# unambiguous Unicode equivalents for named symbols (kept conservative)
UNICODE_FOR_NAME = {
    'UP_ARROW': 0x2191, 'DOWN_ARROW': 0x2193, 'LEFT_ARROW': 0x2190, 'RIGHT_ARROW': 0x2192,
    'UP_ARROW_2': 0x2B06, 'DOWN_ARROW_2': 0x2B07, 'LEFT_ARROW_2': 0x2B05, 'RIGHT_ARROW_2': 0x2B95,
    'NO': 0x2116,                       # numero sign
    'CIRCLE_1': 0x2460, 'CIRCLE_2': 0x2461, 'CIRCLE_3': 0x2462, 'CIRCLE_4': 0x2463, 'CIRCLE_5': 0x2464,
    'CIRCLE_6': 0x2465, 'CIRCLE_7': 0x2466, 'CIRCLE_8': 0x2467, 'CIRCLE_9': 0x2468,
    'EMOJI_UNION': 0x2282,              # annotated as ⊂ in charmap.txt itself
    'CIRCLE_HOLLOW': 0x25CB,            # white circle (pokeemerald-expansion glyph)
    'UNK_SPACER': None, 'SPACER': None,
}

def main():
    mp = load_json('mapping.json')
    ext = extra_names(os.path.join(EXP_SRC, 'charmap.txt'))
    ext.update(extra_names(os.path.join(SRC, 'charmap.txt')))   # pokeemerald's names win; the expansion adds e.g. CIRCLE_HOLLOW
    out = {}
    for gid in range(512):
        e = mp[str(gid)]
        name = e['name'] or ext.get(gid)
        if gid == 0x77:
            name = 'SPACER'
        if gid == 0x50:
            name = 'BOX_0x50'
        if not (e['ink'] or e['unicode'] or name):
            continue
        if gid == 0x00:
            out[str(gid)] = {'codepoints': [0x20], 'name': 'space', 'source': 'charmap'}
            continue
        if gid == 0xFF:   # '$' maps here in charmap.txt but no Latin sheet has a glyph at 0xFF
            continue
        cps = list(e['unicode'])
        src = 'charmap' if cps else 'pua'
        if not cps:
            cps = [PUA_BASE + gid]
            u = UNICODE_FOR_NAME.get(name)
            if u:
                cps.append(u); src = 'pua+unicode-equivalent'
        # prefix so names like PLUS/UNDERSCORE never collide with standard AGL names of real characters
        gname = ('ext.' + name.lower()) if (name and src != 'charmap') else None
        out[str(gid)] = {'codepoints': cps, 'name': gname, 'source': src}
    save_json('codepoints.json', out)
    n_pua = sum(1 for v in out.values() if v['source'] != 'charmap')
    print('glyphs:', len(out), ' charmap-mapped:', len(out)-n_pua, ' PUA:', n_pua)

if __name__ == '__main__':
    main()
