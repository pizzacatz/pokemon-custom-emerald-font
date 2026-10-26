"""Let accented letters use their base letter's model.

usage: python3 scripts/share_base_models.py [variant ...]   (default: all fonts)
An accented letter without a model of its own (À, ç, Ñ, ...) is added to the "char" list of its base
letter's model when the letter part of its pixels is exactly the base letter's: every row the base letter
uses is identical. The model's "rows" are narrowed to those rows, so the accent outside them is traced on
its own (smooth.py), and the model's cuts and clips don't touch it. An accent touching the letter (Small's
ì, whose accent ends where i's dot is) keeps the letter traced. A model whose "rows" are already set
keeps them, provided the base letter has no ink outside them. Run it again after re-porting a font.
"""
import os, sys, json, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
from common import VARIANTS, data_dir

def main():
    for v in sys.argv[1:] or list(VARIANTS):
        d = data_dir(v)
        od = os.path.join(d, 'glyph_overrides')
        mp = json.load(open(os.path.join(d, 'mapping.json')))
        cps = json.load(open(os.path.join(d, 'codepoints.json')))
        gid_of = {}
        for k, e in mp.items():
            for c in e['unicode'] + cps.get(k, {}).get('codepoints', []):
                gid_of.setdefault(chr(c), int(k))
        mask = lambda ch: json.load(open(os.path.join(d, 'masks', f'{gid_of[ch]:03d}.json')))['fg']
        files, model_of = {}, {}
        for fn in sorted(os.listdir(od)):
            if fn.endswith('.json') and not fn.startswith('_'):
                spec = json.load(open(os.path.join(od, fn), encoding='utf-8'))
                files[fn] = spec
                for ch in ([spec['char']] if isinstance(spec['char'], str) else spec['char']):
                    model_of[ch] = fn
        added, changed = [], set()
        for ch, gid in sorted(gid_of.items()):
            if ch in model_of or not mp[str(gid)]['ink']:
                continue
            nfd = unicodedata.normalize('NFD', ch)
            base = nfd[0]
            if len(nfd) < 2 or base not in model_of or base not in gid_of:
                continue
            fn = model_of[base]; spec = files[fn]
            bm, am = mask(base), mask(ch)
            ink_rows = [y for y, r in enumerate(bm) if any(r)]
            rows = spec.get('rows', [0, 16])
            band = [ink_rows[0], ink_rows[-1] + 1] if rows == [0, 16] else rows
            if any(any(bm[y]) for y in range(16) if not band[0] <= y < band[1]):
                continue                                  # the model's rows don't hold the whole base letter
            if any(am[y] != bm[y] for y in range(*band)):
                continue                                  # the letter part differs (squashed, shifted)
            accent = [(x, y) for y in range(16) if not band[0] <= y < band[1] for x in range(16) if am[y][x]]
            if not accent or any(bm[y + dy][x + dx] for x, y in accent for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                                 if band[0] <= y + dy < band[1] and 0 <= x + dx < 16):
                continue                                  # no accent, or one touching the letter (ì in Small)
            spec['rows'] = band
            chars = [spec['char']] if isinstance(spec['char'], str) else list(spec['char'])
            spec['char'] = chars + [ch]
            model_of[ch] = fn; changed.add(fn); added.append(ch)
        for fn in changed:
            with open(os.path.join(od, fn), 'w', encoding='utf-8') as f:
                json.dump(files[fn], f, indent=1, ensure_ascii=False)
        print(v, 'shares base models:', ''.join(added))

if __name__ == '__main__':
    main()
