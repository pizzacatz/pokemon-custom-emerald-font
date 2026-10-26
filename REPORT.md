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

## Other game fonts (Narrow, Small, Short, Small Narrow)

Added 2026-10-25. Sheets `latin_narrow.png`, `latin_small.png`, `latin_short.png`, `latin_small_narrow.png`
and their width tables from the same pokeemerald revision; same character map, code points and PUA
layout as Normal. Each builds as Emerald Pixel Vector <Name> (exact) and Emerald Rounded <Name> Game.

| Font | Baseline row | Line pitch | Cap / x-height | Overrides: identical, transfer, fuzzy, traced, hand |
|---|---|---|---|---|
| Narrow | 12 | 16 px | 9 / 6 px | 23, 43, 4, 8, 6 |
| Short | 11 | 14 px | 8 / 5 px | 0, 60, 1, 13, 10 |
| Small | 11 | 12 px | 7 / 5 px | 0, 55, 4, 12, 13 |
| Small Narrow | 11 | 12 px (the game's 8 is too tight for its descenders) | 7 / 5 px | 68 (from Small), 0, 4, 12, 0 |

Source quirks, kept as in the game:
- Glyphs up to 8 px wide only draw the left half of their 16×16 cell (`DecompressGlyph_*`); the Narrow
  sheet has stray pixels in the unused right half of cell 0xCD ("S"), so extraction ignores that half.
- Small Narrow's width table gives `=` a width of 0 and makes `:` `;` `×` narrower than their ink, so
  they overlap the next character exactly as in the game (reported by `verify.py` as ink outside the
  advance in both Small Narrow fonts).

Verification: the exact fonts round-trip to the game bitmaps at 16 px with zero mismatches; no
missing or empty glyphs; every ported model covers every pixel of its glyph (no "missing" pixels
in `port_report.json`), with scores in the same range as the hand-tuned Normal models (median about
2.1–2.4; the largest are `&` at 7.4 in Narrow and Short, the same as Normal's, and Small's `“` at 6.0). The FontForge validator finds nothing in any
Rounded font (the "wrong direction" notes on `3` and U+E054 went with the skia-pathops change below).
Remaining: the 0.2 px cap overshoots of accents, `Ç` `ç` `Q` in Small, as with Normal's circumflexes.

## Glyphs from pokeemerald-expansion

Added 2026-10-25 for Showdown Advance, which draws text from pokeemerald-expansion's sheets. Compared
cell by cell with pokeemerald, the expansion's five sheets add ink only in blank cells: 0x38 V_D_ARROW
and 0x118 CIRCLE_HOLLOW in all five, and 0xF7 EMOJI_DIZZYEGG in Small. Every other glyph and width is
identical. `extract.py` takes exactly those cells (bitmap, width, charmap name) from
`source/pokeemerald-expansion/`, so the existing glyphs are unchanged. CIRCLE_HOLLOW also maps to ○ U+25CB.

## pokeemerald-expansion's extra fonts (Narrower, Small Narrower, Short Narrow, Short Narrower)

Added 2026-10-25. Sheets and width tables from pokeemerald-expansion (`source/pokeemerald-expansion/`),
character map and code points as for the other fonts. Each is ported from the font it narrows.

| Font | Baseline row | Line pitch | Overrides: identical, transfer, fuzzy, traced, hand | Median score |
|---|---|---|---|---|
| Narrower | 12 | 16 px | 13, 44, 11, 14, 2 | 2.02 |
| Small Narrower | 11 | 12 px (the game's 8 is too tight for its descenders) | 9, 53, 7, 13, 2 | 2.09 |
| Short Narrow | 11 | 14 px | 32, 34, 5, 13, 0 | 2.28 |
| Short Narrower | 11 | 14 px | 25, 37, 7, 14, 1 | 1.99 |

Hand-fitted: Narrower `/` `×`, Small Narrower `/` `Z`, Short Narrower `V`. Verification as for the others:
the exact fonts round-trip pixel for pixel; no missing or empty glyphs; no model misses a pixel. Game-data
quirks kept: Small Narrower gives `=` width 0 like Small Narrow; Short Narrower's arrows are wider than
their advance.

While doing this, dot sizes in transfers were fixed: a dot over a deleted row or column now shrinks with
it (never below one pixel). This corrected the quote marks of Small and Small Narrow, whose dots were a
row too tall, and slightly reduced their i/j dots.

## Cut masks and FontForge's boolean bug

FontForge's boolean operations misbehave where edges coincide, which clip boxes, terminal trims and
strokes meeting end to end do by design: they can drop whole contours, half-invert a cut, silently do
nothing, or fill the space between stems. A first fix checked every cut and retried it grown by a
fraction of a font unit. That fixed the trim at the left terminal of Normal `J`, which had never been
applied, and refreshed Emerald Rounded's stale `¥`.

That check missed Narrow `M` (its clip lines lie on its stems, and its right stem is two strokes
meeting end to end): the union went wrong before any cut ran, filling the M between its stems and
leaving its top unclipped. The same bug had filled the top of the M in the Short fonts' U+E054. Since
then, FontForge only strokes the centrelines; the union and the cuts are done with skia-pathops (Skia's
path booleans, as used by fontmake), which handles coincident edges. Every other glyph of the ten
Rounded fonts renders exactly as before. Points that rounding to whole font units puts on top of
each other are removed, so the FontForge validator reports nothing for any Rounded font.

## Mitred joints in the other fonts

The eight fonts other than Normal draw their sharp joints (joint radius 0) with miter joins instead of
round ones, so a sharp corner keeps its point; Normal's hand-made models are unchanged, and bevels stay
bevels. A miter longer than 4 stroke widths (SVG's default limit: joints sharper than about 29°, or a
stroke doubling back on itself) is cut square, which stops spikes on `N`, `3`, `&`, `j` and `y`. Newly
ported glyphs get miter joins too. About 45 glyphs per font change, by a fraction of a pixel at each corner.

## Pictograms

The symbols the game shows next to text are modelled in all nine Rounded Game fonts instead of being
softened pixel art or plain traces:

- Lv (E034) has its own model, a copy of Lv2's (E105), which draws the same pixels in seven of the
  fonts; Small Narrower and Short Narrower draw Lv differently and have their own ports.
- PLUS (E104), the POKéBLOCK pieces (E055, E056; PK and MN were already modelled), and the move
  menu's effectiveness marks: CIRCLE_DOT (E115) and CIRCLE_HOLLOW (E118, also U+25CB) as circles,
  TRIANGLE (E116) with rounded corners, BIG_MULT_X (E117) clipped flat like `X`. Small, Small Narrow
  and Small Narrower draw smaller marks (a 6-pixel ring with a solid centre) and have their own models.
- The arrows are solid, so they are polygons rather than strokes (the new `fill` entry):
  E100-E103, the text arrows ↑ ↓ ← → (E079-E07C), the up-down arrow (E038) and ▶ (U+25B6), fitted to
  each font's own pixels by `scripts/fit_fills.py`. The 45-degree slopes run through the pixel centres.

- The circled digits ①–⑨ (E10A–E112) are true circles around the digit (`scripts/fit_circles.py`), not the
  octagon a trace through the pixel ring gives. The header and badge fonts reuse Normal's, since their
  pixel ring is a row short.

No advance or code point changed.

## Lettering from the game's art

The summary screen's section headers and the type badges are lettering drawn into the graphics, not
text. Both are now fonts (Header and Badge, see the README) built by the normal pipeline from sheets
synthesized from the art: every letter the art shows is taken from it (one consistent shape per letter
in both sets), the rest of A–Z is derived or drawn in the same style. Header: 19 letters from the art,
G H J K Q U W Z from Short with a repeated middle row removed (row 9, or 7 for K and Z, 5 for Q); its
M N R G X are hand-modelled. Badge: 21 letters and `?` from the badges, J Q V X Z drawn; its M N V W X
are hand-modelled (M and W are stems with a bar, X is two brackets). Every header word and every badge
was rendered over the art's pixels to check positions.

## Sharp mitred joints by default

Sharp joints drawn with miter joins are now the default everywhere: a model that names no joint radius
gets sharp joints (radius 0, was 1 px of rounding), one that names no join gets miter (was round), the
automatic trace keeps its joints sharp instead of rounding them, new glyphs in the glyph editor start
that way, and the rasteriser that scores models draws each stroke's own join. Every existing model names
its join and radius, so only automatically traced glyphs change. The Y of the fonts other than Normal and
Short now has sharp joints where its arms meet the stem.

Glyphs without a model (accented letters, Œ, ß, ¿, ª, º, ç and some pictograms) are now drawn by the
same convention trace that ports models between fonts (`port_overrides.trace`): straight strokes through
pixel centres, a 67.5-degree arc wherever a stroke turns through a single diagonal pixel step, and sharp
joints. The older plain trace is kept for a glyph only where the convention trace misses a pixel or
scores more than 1 worse (brackets built from two-pixel steps, solid blocks).

## Known limitations / remaining defects

- `%` and `&` follow the quirky source shapes; the smooth `%` is odd-looking because the pixel
  original is (a slashed "y"-like form). Left as is.
- The smooth `ß` (source draws it like a β / "R"-ish shape) is faithful but unusual.
- Â Ê Î Ñ Ô Û: the round join at the apex of the circumflex/tilde pokes about 0.2 px above the em
  box (reported by `verify.py` as vertical_overflow). Renderers do not clip outlines, so it is harmless.
- Very short strokes near joints (e.g. the spur of `a`, `t` crossbar ends) can show a slightly
  bulbous square cap at 64 px+. Cosmetic.
- The emoji (E1D0 onward) and the extended underscore (E009) are still corner-softened pixel art; every
  symbol the game shows beside text is modelled (see "Pictograms").
- No kerning; "AVATAR To Wa" shows the expected loose pairs.
- Hinting: none. The pixel font is only pixel-exact at multiples of 16 px with hinting disabled.
- `data/` looks large (`du` ≈ 230 MB) only because the exFAT drive has 128 KB clusters; actual
  content is a few MB.
