#!/bin/sh
# Full reproducible rebuild of all five game fonts: extraction -> smoothing -> code points -> fonts -> verification.
# Normal builds all four treatments; Narrow, Small, Short and Small Narrow build Pixel Vector + Rounded Game.
# usage: ./build.sh [variant ...]   (default: all)
set -e
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/pylib${PYTHONPATH:+:$PYTHONPATH}"
VARIANTS=${*:-normal narrow small short small_narrow}
for v in $VARIANTS; do
  echo "=== $v"
  export EMERALD_VARIANT=$v
  python3 scripts/extract.py
  python3 scripts/smooth.py
  python3 scripts/assign_codepoints.py
  if [ "$v" = normal ]; then TREATMENTS="exact rounded smooth smoothgame"; else TREATMENTS="exact smoothgame"; fi
  for t in $TREATMENTS; do scripts/ff.sh scripts/build_font.py "$t" 2>&1 | grep -E "^built|Error|Traceback|WARNING|retried" || true; done
  if [ "$v" = normal ]; then python3 scripts/make_comparison.py; fi
  python3 scripts/verify.py
done
unset EMERALD_VARIANT
scripts/ff.sh scripts/check_geometry.py 2>&1 | grep -v "pkg_resources\|UserWarning\|Based on\|License\|BSD\|Version:\|Copyright"
