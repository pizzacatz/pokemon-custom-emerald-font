Files from rh-hideout/pokeemerald-expansion (revision in REVISION.txt): the five Latin font sheets,
src/fonts.c (width tables) and charmap.txt. The fonts are built from pokeemerald (../pokeemerald);
these only supply glyphs the expansion adds in cells that are blank in pokeemerald's sheets
(0x38 V_D_ARROW, 0x118 CIRCLE_HOLLOW, 0x119 STAR and 0x11A TRIANGLE_UPSIDE_DOWN, and 0xF7 EMOJI_DIZZYEGG
in the Small font). STAR (4x) and TRIANGLE_UPSIDE_DOWN (1/4x) are the Pokemon Champions effectiveness marks
added in d94ee27453. The status pills are unchanged since 68a5890c.
graphics/interface/status_icons.png and graphics/battle_interface/status.png are the status-condition
pills, the source of the Status lettering font (scripts/make_lettering.py status).
