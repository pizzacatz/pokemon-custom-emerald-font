# Emerald Rounded

Pokémon Emerald's dialogue font, rebuilt as installable TrueType fonts. The pixel art of the Latin
"normal" font from the [pret/pokeemerald](https://github.com/pret/pokeemerald) decompilation is
traced two ways: once exactly, pixel for pixel, and once as a smooth reconstruction whose glyphs are
hand-tuned stroke models (polylines, arcs, dots) expanded into outlines by FontForge.

![Smooth alphabet](build/comparisons/smooth_alphabet_72.png)

![Specimen at 32 px](build/specimens/smoothgame_32px.png)

| Font | File | What it is |
|---|---|---|
| **Emerald Pixel Vector** | `build/fonts/EmeraldPixelVector-Regular.ttf` | Faithful, sharp pixel outlines. At 16 px it reproduces the game bitmap exactly. |
| **Emerald Rounded** | `build/fonts/EmeraldRounded-Regular.ttf` | Smooth reconstruction: stepped diagonals become clean lines, bowls become Bézier curves, spacing opened by 1 px for text. |
| **Emerald Rounded Game** | `build/fonts/EmeraldRoundedGame-Regular.ttf` | Same smooth outlines, but advances, side bearings and space width identical to the game. |
| Emerald Pixel Soft (reference) | `build/fonts/EmeraldPixelSoft-Regular.ttf` | Pixel outline with every corner softened. Kept for comparison only. |

Each font also ships as `.otf` and as an editable FontForge `.sfd` next to the TTF. The ready-made
fonts are committed, so you can download them from `build/fonts/` without building anything.

Companion project: [font-compare](https://github.com/pizzacatz/font-compare), a local web app that
overlays the fonts, scores every glyph against the pixel original, and provides the GUI glyph editor
used to tune the smooth fonts.

## Quick install (Linux)

```sh
mkdir -p ~/.local/share/fonts
cp build/fonts/EmeraldPixelVector-Regular.ttf build/fonts/EmeraldRounded-Regular.ttf build/fonts/EmeraldRoundedGame-Regular.ttf ~/.local/share/fonts/
fc-cache -f
```

On Windows or macOS, double-click a TTF and choose Install.

## Source

- Sheet: `https://raw.githubusercontent.com/pret/pokeemerald/refs/heads/master/graphics/fonts/latin_normal.png`
- Mapping/width/render code: `charmap.txt`, `src/fonts.c` (`gFontNormalLatinGlyphWidths`), `src/text.c`
  (`DecompressGlyph_Normal`, `CHAR_EXTRA_SYMBOL`), `include/constants/characters.h`
- Repository: https://github.com/pret/pokeemerald, revision `731ad5bfd6e6f265508d0efcca0ba42f9dcf5881`
  (master, 2026-10-01). Local copies of the files used are in `source/pokeemerald/`.
- Licensing: pokeemerald's own LICENSE file covers the decompiled *code*; the glyph artwork is
  Nintendo / Creatures / GAME FREAK property and no licence for it is asserted here. These fonts are
  a fan conversion for personal use.

## Layout of the project

```
source/pokeemerald/      downloaded source files + REVISION.txt
data/mapping.json        per sheet cell: game id, charmap Unicode, width, ink box, shadow pixels
data/codepoints.json     final code point assignment + glyph names
data/masks/              foreground/shadow masks per glyph (JSON) and sheet_fg.png
data/svg_exact/          exact pixel outlines (SVG + contour JSON)
data/svg_rounded/        treatment 2 outlines
data/svg_smooth/         treatment 3: *.json stroke model, *.centerline.svg, u*.outline.svg (final outlines)
scripts/                 extract.py, smooth.py, assign_codepoints.py, build_font.py (FontForge),
                         render.py, make_comparison.py, verify.py, check_geometry.py, ff.sh
build/fonts/             TTF / OTF / SFD
build/comparisons/       treatment comparisons, source sheet, zooms
build/specimens/         text specimens at 16/24/32/64 px for each font
build/verification.json, build/geometry_check.json
REPORT.md                coverage, design choices, defects, verification results
```

## Setup

Only needed to rebuild or edit the fonts. Linux Mint 22 / Ubuntu 24.04 was used. Python 3.12 with Pillow is the only system requirement;
numpy, fonttools and freetype-py are installed project-locally (the project lives on an exFAT drive,
which cannot hold a venv's symlinks, so `pip --target` is used instead):

```sh
pip3 install --target pylib numpy fonttools freetype-py
```

FontForge (with Python bindings) is required to assemble the fonts. Either:

```sh
sudo apt install fontforge python3-fontforge      # preferred, distro package
```

or, with no sudo, fetch the official AppImage into `tools/` (what this build used; it embeds its own
Python 3.10, so `scripts/build_font.py` runs inside FontForge's interpreter, not the system one):

```sh
scripts/get_fontforge.sh
```

`scripts/ff.sh` picks whichever is available. Inkscape is not required; nothing in the pipeline
depends on it (it is still handy for opening the SVGs in `data/`).

## Rebuild

```sh
./build.sh
```

runs: extract → smooth → assign code points → FontForge builds (4 fonts) → geometry check →
comparison images → specimens and automated checks. Everything is deterministic.

## Using the fonts

Use `Emerald Pixel Vector` at multiples of 16 px (16, 32, 48 …) with hinting/antialiasing off for
pixel-perfect output. `Emerald Rounded` is intended for ordinary antialiased use at any size.

## Code points

- Everything in `charmap.txt` with a single-byte code and a glyph in the sheet maps to its Unicode
  character (A–Z, a–z, 0–9, accented Latin, punctuation, ♂ ♀ × ¥ … “ ” ‘ ’ ▶ etc.).
- Game-only glyphs sit in the Private Use Area at **U+E000 + sheet id** (so the `CHAR_EXTRA_SYMBOL`
  glyph `0xF9 0x05` "Lv" is U+E105, the emoji `0xF9 0xE7` heart is U+E1E7, `CHAR_SPACER` is U+E077).
  Where the symbol has an unambiguous Unicode form it is additionally mapped there:
  arrows ↑↓←→ (U+2190–2193 for 0x79–7C, U+2B05–2B07/2B95 for the 0x100 set), circled digits ①–⑨,
  № (U+2116), ⊂ (U+2282, the charmap's own annotation).
- See `data/codepoints.json` for the full table; `REPORT.md` lists what is missing.

## Hand-editing glyphs (parametric)

The smooth fonts are generated from a *centreline model*: every glyph is a set of strokes (polylines
and arcs through source-pixel coordinates) that FontForge expands to a 1 px wide outline. You edit
that model per glyph in `data/glyph_overrides/<name>.json`; the scripts regenerate the outlines, so
your edits survive every rebuild and stay exact.

Coordinate system (source pixels): x 0..16 left to right, y 0..16 top to bottom. Baseline y = 12,
cap top y = 3, x-height y = 6, descender bottom y = 14, accents from y = 0. Pixel centres are at .5,
so the left stem of H runs from (0.5, 3.5) to (0.5, 11.5). Advance widths come from the game table
and are not changed by overrides.

```jsonc
{
  "char": ["N", "Ñ"],          // character(s) this applies to; accents outside `rows` are still auto-traced
  "rows": [3, 12],             // band of the pixel mask that the override replaces
  "width": 1.0,                // stroke width in px for the glyph (per stroke: "width" on the stroke)
  "joint_radius": 1.0,         // default rounding radius at polyline joints, px
  "strokes": [
    {"points": [[0.5,3.5],[0.5,11.5]]},                     // straight stem
    {"points": [[4.5,3.5],[1.2,6.8,0],[1.2,8.2,0],[4.5,11.5]]}, // 3rd value = that joint's radius, 0 = sharp
    {"points": [[0.5,3.5],[2.5,3.5,0,-0.4142],[4.5,5.5,0]]},   // 4th value = bulge: segment to the next point is a circular arc (tan(angle/4), + = CCW on the page)
    {"points": [[1,9],[4,9],[4,11],[1,11]], "closed": true, "sharp": true},
    {"arc": {"center":[2.5,9], "radius":2, "start":0, "end":180}}, // degrees, CCW as on the page, 0 = right
    {"circle": {"center":[2.5,9], "radius":2}, "width": 1.1}
  ],
  "dots": [[2.5,1.5,0.5], [4.5,1.5,0.5,"square"], [6.5,1.5,0.5,"rounded",0.2]], // x, y, half-size, shape, corner radius
  "dot_shape": "circle",       // default dot shape: circle | square | rounded; "dot_corner" = default corner radius
  "join": "round",             // corner style where a stroke bends: round | miter (sharp) | bevel (flat); also per stroke
  "clip_y": [3, 12]            // keep only this band of rows (and/or "clip_x"); trims round joins flush with cap/baseline
}
```

Cut masks are subtracted one polygon at a time after the strokes are unioned, so masks may overlap each
other and may cross counters (the inside of O, B, etc.) safely; `clip_x` and `clip_y` can be combined.
A stroke entry may carry both `points` and its own `cut`.


A stroke entry `{"cut": [[x,y], ...]}` is a polygon subtracted from the finished outline, for any
trimming the join styles cannot express.

`data/glyph_overrides/_TEMPLATE.json` has every construct with notes; `N.json`, `M.json`, `K.json`,
`W.json`, `multiply.json` are working examples. Stroke ends get square caps (extended by half the
width), joints between strokes are unioned, so you can build a glyph from overlapping pieces.

Edit loop:

```sh
./preview.sh "NKa"        # regenerate model -> rebuild Emerald Rounded Game -> build/preview/
```

`build/preview/strip.png` shows the glyphs in Pixel Vector, in Rounded Game, and enlarged on the
16 px grid with both overlaid (blue = pixel original, pink = your outline, dark = agreement, the
vertical line is the advance). Per-glyph PNGs sit next to it. When happy, run `./build.sh` for all
fonts and `../font-compare/sync-fonts.sh` to refresh the web comparison, whose glyph grid,
loupe and overlay give the same comparison interactively.

The GUI for all of this is the glyph editor in [font-compare](https://github.com/pizzacatz/font-compare)
(`./serve.sh` there, then `/editor.html`): it draws on the pixel grid, edits every field above with
sliders and numbers, saves the JSON here, and rebuilds Emerald Rounded Game with one click.

Free-form edits are also possible in the FontForge GUI (`tools/squashfs-root/AppRun build/fonts/X.sfd`),
but those live only in the `.sfd` and are overwritten by the next `./build.sh`.

## Licence

Everything original here (scripts, override files, generated outlines, font files) is released under
[The Unlicense](LICENSE): public domain, do what you like. The underlying pixel artwork remains the
property of Nintendo / Creatures Inc. / GAME FREAK Inc.; these fonts are a fan conversion and no
licence for the artwork is granted or implied. The pokeemerald files in `source/` are reference
copies from the pret decompilation project.
