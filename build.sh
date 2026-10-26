#!/bin/sh
# Full reproducible rebuild of all nine game fonts (Emerald's five + pokeemerald-expansion's four) and the summary-screen header lettering: extraction -> smoothing -> code points -> fonts -> verification.
# Normal builds all four treatments; the others build Pixel Vector + Rounded Game.
# usage: ./build.sh [variant ...]   (default: all)
set -e
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/pylib${PYTHONPATH:+:$PYTHONPATH}"
VARIANTS=${*:-normal narrow small short small_narrow narrower small_narrower short_narrow short_narrower header badge}
for v in $VARIANTS; do
  echo "=== $v"
  export EMERALD_VARIANT=$v
  case $v in header|badge) python3 scripts/make_lettering.py $v;; esac   # lettering baked into the game's art: a synthesized sheet
  python3 scripts/extract.py
  python3 scripts/smooth.py
  python3 scripts/assign_codepoints.py
  if [ "$v" = normal ]; then TREATMENTS="exact rounded smooth smoothgame"; else TREATMENTS="exact smoothgame"; fi
  for t in $TREATMENTS; do scripts/ff.sh scripts/build_font.py "$t" 2>&1 | grep -E "^built|Error|Traceback|WARNING|retried" || true; done
  if [ "$v" = normal ]; then python3 scripts/make_comparison.py; fi
  python3 scripts/verify.py
  if [ "$v" = badge ]; then python3 scripts/make_badges.py; fi   # smooth badge SVGs + letterless backgrounds
done
unset EMERALD_VARIANT
scripts/ff.sh scripts/check_geometry.py 2>&1 | grep -v "pkg_resources\|UserWarning\|Based on\|License\|BSD\|Version:\|Copyright"
