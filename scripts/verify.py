"""Render specimens from the built TTFs and run automated font checks.
Writes build/specimens/*.png and build/verification.json; prints a summary."""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from render import *
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

LINES = [
    'The quick brown fox jumps over the lazy dog.',
    'Pokémon Emerald',
    'Hamburgefontsiv',
    '0123456789',
    'Il1 O0 rn m',
    'AVATAR To Wa',
    '!?.,;:…·-+=/%()<>&',
    '“quoted” ‘single’ it’s ♂ ♀ × ¥',
    'ÀÁÂÄÇÈÉÊËÌÍÎÏÑÒÓÔÖŒÙÚÛÜ ßàáâäçèéêëìíîïñòóôöœùúûü ¿¡ºª',
    'Extra: ↑↓←→ ①②③④⑤⑥⑦⑧⑨ № ⊂ ' + ''.join(chr(0xE000+g) for g in (0x105,0x106,0x107,0x115,0x116,0x117)),
    'Emoji: ' + ''.join(chr(0xE000+g) for g in range(0x1E4, 0x1FF)),
]

def specimens(report):
    os.makedirs(os.path.join(BUILD, 'specimens'), exist_ok=True)
    for key in FONTS:
        for px in (16, 24, 32, 64):
            rows, missing = [], set()
            for t in LINES:
                im, miss = render_line(t, key, px); rows.append(im); missing |= set(miss)
            stack(rows).save(os.path.join(BUILD, 'specimens', f'{OUT_PREFIX}{key}_{px}px.png'))
            report.setdefault('missing_in_specimen', {})[key] = sorted(f'U+{ord(c):04X}' for c in missing)
    # enlarged glyph comparisons across fonts
    for name, text in [('glyphs_upper', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), ('glyphs_lower', 'abcdefghijklmnopqrstuvwxyz'),
                       ('glyphs_digits_punct', '0123456789!?.,;:“”‘’&%×♂♀')]:
        rows = [label(render_line(text, k, 64)[0], k, 70) for k in FONTS]
        stack(rows).save(os.path.join(BUILD, 'comparisons', f'{OUT_PREFIX}{name}_64.png'))
    # line-height / baseline check: two lines of text stacked using the font's line height
    for key in FONTS:
        face = freetype.Face(font_path(key)); face.set_char_size(32*64)
        lh = face.size.height >> 6
        ims = [render_line(t, key, 32, pad=0)[0] for t in ('Ágjpqy Hxg', 'Ágjpqy Hxg')]
        out = Image.new('RGB', (max(i.width for i in ims), lh*2), (255, 255, 255))
        for i, im in enumerate(ims):
            out.paste(im, (0, i*lh))
        out.save(os.path.join(BUILD, 'specimens', f'{OUT_PREFIX}{key}_linepitch_32px.png'))
        report.setdefault('line_height_px_at_32', {})[key] = lh

def font_checks(report):
    cps = load_json('codepoints.json')
    required = [*range(0x41, 0x5B), *range(0x61, 0x7B), *range(0x30, 0x3A), 0x20]
    useful = [ord(c) for c in 'é♂♀×“”‘’!?.,;:-+=/%()<>&…·¥']
    for key, fn in FONTS.items():
        tt = TTFont(font_path(key))
        cmap = tt.getBestCmap()
        gs = tt.getGlyphSet()
        r = {'num_glyphs': len(tt.getGlyphOrder()), 'cmap_entries': len(cmap)}
        r['missing_required'] = [f'U+{c:04X}' for c in required if c not in cmap]
        r['missing_useful'] = [f'U+{c:04X}' for c in useful if c not in cmap]
        # every codepoint we intended must be present
        intended = {cp for v in cps.values() for cp in v['codepoints']}
        r['missing_intended'] = [f'U+{c:04X}' for c in sorted(intended) if c not in cmap]
        # vertical metrics
        hhea, os2, head = tt['hhea'], tt['OS/2'], tt['head']
        r['upm'] = head.unitsPerEm
        r['metrics'] = dict(hhea=(hhea.ascent, hhea.descent, hhea.lineGap), typo=(os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap),
                            win=(os2.usWinAscent, os2.usWinDescent), capH=os2.sCapHeight, xH=os2.sxHeight)
        # outline sanity: empty mapped glyphs other than space/spacer, glyphs exceeding the ascent/descent box, zero advance
        empty, clipped, zero_adv, bounds_bad = [], [], [], []
        hmtx = tt['hmtx']
        for cp, gn in cmap.items():
            bp = BoundsPen(gs); gs[gn].draw(bp)
            adv, lsb = hmtx[gn]
            if adv <= 0:
                zero_adv.append(f'U+{cp:04X}')
            if bp.bounds is None:
                if cp not in (0x20, 0xE077, 0xE000 + 0x109):
                    empty.append(f'U+{cp:04X}')
                continue
            x0, y0, x1, y1 = bp.bounds
            if y1 > hhea.ascent + 10 or y0 < hhea.descent - 10:   # 0.1 px tolerance
                clipped.append(f'U+{cp:04X}')
            if x1 > adv + 0.75*PX or x0 < -0.75*PX:
                bounds_bad.append((f'U+{cp:04X}', round(x0), round(x1), adv))
        r.update(empty_mapped_glyphs=empty, vertical_overflow=clipped, zero_advance=zero_adv, ink_outside_advance=bounds_bad)
        report['fonts'][key] = r

def bitmap_roundtrip(report):
    """Render every mapped glyph of the exact font at 16 px (1 source px == 1 output px), monochrome,
    unhinted, and compare with the source foreground mask (rows counted from the cell top, baseline at
    BASELINE_ROW). This is the definitive check that the exact
    outlines (including hole directions) survived the TTF round trip."""
    cps = load_json('codepoints.json'); mp = load_json('mapping.json')
    face = freetype.Face(font_path('exact')); face.set_char_size(16*64)
    bad = []
    for gid_s, rec in cps.items():
        e = mp[gid_s]
        if not e['ink']:
            continue
        cp = rec['codepoints'][0]
        face.load_char(cp, freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_TARGET_MONO)
        face.glyph.render(freetype.FT_RENDER_MODE_MONO)
        bm = face.glyph.bitmap
        got = [[0]*16 for _ in range(16)]
        top = BASELINE_ROW - face.glyph.bitmap_top; left = face.glyph.bitmap_left
        for y in range(bm.rows):
            for x in range(bm.width):
                if (bm.buffer[y*bm.pitch + x//8] >> (7 - x % 8)) & 1:
                    yy, xx = top + y, left + x
                    if 0 <= yy < 16 and 0 <= xx < 16:
                        got[yy][xx] = 1
                    else:
                        got = None; break
            if got is None:
                break
        want = json.load(open(os.path.join(DATA, 'masks', f'{int(gid_s):03d}.json')))['fg']
        if got != want:
            bad.append(f'U+{cp:04X}')
    report['exact_bitmap_roundtrip_mismatches'] = bad
    print('exact font 16px bitmap round-trip mismatches:', bad)

def main():
    report = {'fonts': {}}
    font_checks(report)
    bitmap_roundtrip(report)
    specimens(report)
    with open(os.path.join(BUILD, f'{OUT_PREFIX}verification.json'), 'w') as f:
        json.dump(report, f, indent=1)
    for k, r in report['fonts'].items():
        print(k, {x: r[x] for x in ('num_glyphs', 'cmap_entries', 'missing_required', 'missing_useful', 'missing_intended',
                                     'empty_mapped_glyphs', 'vertical_overflow', 'zero_advance')})
        print('   ink outside advance:', r['ink_outside_advance'][:12], '... total', len(r['ink_outside_advance']))
    print('missing in specimen text:', report['missing_in_specimen'])
    print('line height @32px:', report['line_height_px_at_32'])

if __name__ == '__main__':
    main()
