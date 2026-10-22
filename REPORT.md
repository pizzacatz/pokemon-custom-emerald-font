# Emerald Rounded — build report

Built 2026-10-21 from pret/pokeemerald `731ad5bf` on Linux Mint 22.2 with FontForge 20251009 (AppImage),
Python 3.12, fonttools 4.67, freetype-py 2.5.

## Source findings

- `latin_normal.png` is 256×512, 4-colour indexed, 16 columns × 32 rows of 16×16 cells = 512 glyph ids.
  Sheet position `row*16 + col` is the game character id; the game reads 15 of the 16 rows.
- Palette roles (from `GenerateFontHalfRowLookupTable` / `sFontHalfRowOffsets` in `src/text.c`):
  index 1 = foreground, 2 = shadow (offset +1,+1), 0 and 3 = background (3 marks the glyph's box).
- Game ids → Unicode comes from `charmap.txt` (first section only). It is not ASCII order
  (`'A'` = 0xBB, `'0'` = 0xA1, `'a'` = 0xD5). Multi-byte entries (PKMN, POKEBLOCK, TALL_PLUS) are ignored.
- Ids 0x100–0x1FF are reached in game through the `CHAR_EXTRA_SYMBOL` (0xF9) prefix byte:
  arrows, PLUS, Lv, PP, ID, No, UNDERSCORE, CIRCLE_1–9, round parentheses, CIRCLE_DOT, TRIANGLE,
  BIG_MULT_X (0x100–0x117) and the `EMOJI_*` set (0x1D0–0x1FE) used by Easy Chat / mail.
  `CHAR_SPACER` (0x77) is an empty 3 px glyph. Keypad icons (0xF8) are drawn from a different image
  and are not in this sheet.
- Metrics (pixel rows, 0 = top): cap height rows 3–11 (9 px), x-height rows 6–11 (6 px), baseline
  between rows 11 and 12, descenders to row 13, accents from row 0. Line pitch 16 px.
- Widths: `gFontNormalLatinGlyphWidths` gives the advance per id. For 124 of 141 mapped glyphs the
  width equals ink width + 1, i.e. the advance already contains the shadow column, which is the only
  inter-letter gap in game. Narrow glyphs (i, l, punctuation) start at column 1 with width = ink + 2.
  Letter spacing in game is 0 for Latin text (`letterSpacing` only applies to Japanese).

## Outline generation

- **Exact**: foreground pixels → unit squares → shared edges cancelled → directed edge chains →
  collinear points removed. At diagonal-only contacts the tracer always turns right so the two regions
  stay separate contours. Verified by rasterising with pixel-centre winding tests: 0 mismatches in 227
  glyphs, and again after the TTF round trip (FreeType 16 px mono render vs. source mask: 0 mismatches).
- Common coordinate system: 1 source px = 100 font units, UPM 1600, baseline at y = 0 = pixel row 12,
  ascent 1200, descent 400. No per-glyph cropping or rescaling.
- **Treatment 2 (Emerald Pixel Soft)**: every outline corner replaced by a 0.3 px arc. Reference only.
- **Treatment 3 (Emerald Rounded)**: each glyph modelled as a graph of pixel centres (4-neighbours plus
  diagonal links where no 4-neighbour is shared). Chains are split at ≥ 90° turns (kept as true
  corners), alternating-turn staircases are replaced by straight lines (N, Z, 7, V, K legs…), the
  remaining 45° joints are rounded with Bézier arcs (radius ≤ 1 px), and the centrelines are stroked
  1 px wide with square caps/round joins in FontForge, then overlap-removed and simplified.
  Single pixels become round dots (r 0.5 px), 2×2 blocks become round dots (r 1 px) that connect to
  any tail (comma, quotes, semicolon). N, M, K, W, Ñ and × have 2 px-thick pixel diagonals that the
  centreline model cannot infer, so their skeletons are hand-defined (`OVERRIDES` in `smooth.py`).
  Pictograms with filled areas (arrows, ▶, most emoji) fall back to the softened pixel outline.
- Spacing: pixel font uses the game advance verbatim (space = 3 px). Rounded font shifts outlines
  right by 0.5 px and adds 1 px to every advance (space = 4 px) so smooth text has ~2 px between letters.
- **Emerald Rounded Game** (`smoothgame` target): the smooth outlines with the game advances verbatim
  (no tracking, no half-pixel shift, space = 3 px), so it drops in anywhere the pixel font fits and
  overlays it exactly. Letters sit 1 px apart as in game; use Emerald Rounded for looser text.
- Stroke caps: FontForge's Python stroker ignores the "square" cap, which originally left every open
  stroke half a pixel short at both ends (H stems ran 50..850 units). Caps are now extended explicitly
  in `smooth.py` (clamped to the 16 px cell), so stems span the full 0..900.
- Per-glyph parametric overrides live in `data/glyph_overrides/*.json` (points, per-joint radii, arcs,
  circles, dots, stroke width); see README "Hand-editing glyphs". `./preview.sh` rebuilds and renders
  the edited glyphs over the pixel originals.
- No kerning tables.

## Coverage

- Four fonts built: Emerald Pixel Vector, Emerald Pixel Soft, Emerald Rounded, Emerald Rounded Game.
- 230 glyphs per font (.notdef + 229). 249 cmap entries (some glyphs carry two code points).
- Required set: A–Z, a–z, 0–9, space: complete. Useful set: é and all charmap accented letters,
  ♂ ♀ × ¥ “ ” ‘ ’ ' ! ? . , ; : … · - + = / % ( ) < > & ¿ ¡ º ª ▶: complete.
- **Missing** (not in the source font): `" # $ * @ [ \ ] ^ _ ` { | } ~`. `$` is listed in charmap.txt as
  id 0xFF but that cell is blank in `latin_normal.png`, so U+0024 is deliberately absent rather than
  faked. `_` is absent because the game's "UNDERSCORE" (0x109) is a name-entry blank cursor glyph
  and lives only at U+E109.
- 88 PUA glyphs (U+E000 + id): Lv (×2), PP, ID, No, SUPER_E/ER/RE, PK/MN/POKEBLOCK pieces, box 0x50,
  spacer, arrows, circled digits, emoji. Arrows, circled digits, № and ⊂ also map to Unicode.

## Verification results

- `verify.py`: no missing required/useful/intended code points, no empty mapped glyphs, no zero
  advances, no ink outside the advance box, no vertical overflow (0.1 px tolerance), line height
  = 32 px at 32 px size for all three fonts. Specimen text lines contain no unmapped characters.
- `check_geometry.py` (FontForge validate, TTF): Emerald Rounded 0 problem glyphs, Emerald Rounded Game 0, Emerald Pixel
  Soft 0. Emerald Pixel Vector reports "wrong direction" on 175 glyphs: these are the glyphs whose
  contours touch at a pixel corner (diagonal contacts, accents touching letters), which FontForge's
  nesting test cannot classify. The 16 px bitmap round-trip proves the fills are correct, so this is
  recorded as a false positive, not fixed by altering the exact geometry.
- Visual inspection was done by viewing the rendered PNGs in `build/comparisons/` and
  `build/specimens/` (the model can view images; all specimen images were inspected at least once
  at 32–128 px). Observations: strokes are uniform, bowls are smooth, holes stay open at 16 px,
  baseline and descenders align across fonts.

## Known limitations / remaining defects

- `%` and `&` follow the quirky source shapes; the smooth `%` is odd-looking because the pixel
  original is (a slashed "y"-like form). Left as is.
- The smooth `ß` (source draws it like a β / "R"-ish shape) is faithful but unusual.
- Â Ê Î Ñ Ô Û: the round join at the apex of the circumflex/tilde pokes about 0.2 px above the em
  box (reported by `verify.py` as vertical_overflow). Renderers do not clip outlines, so it is harmless.
- Very short strokes near joints (e.g. the spur of `a`, `t` crossbar ends) can show a slightly
  bulbous square cap at 64 px+. Cosmetic.
- Emoji / arrows / ▶ in the rounded font are only corner-softened pixel art, not reconstructed.
- No kerning; "AVATAR To Wa" shows the expected loose pairs.
- Hinting: none. The pixel font is only pixel-exact at multiples of 16 px with hinting disabled.
- `data/` looks large (`du` ≈ 230 MB) only because the exFAT drive has 128 KB clusters; actual
  content is a few MB.
