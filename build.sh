#!/bin/sh
# Full reproducible rebuild: extraction -> smoothing -> code points -> fonts -> verification.
set -e
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/pylib${PYTHONPATH:+:$PYTHONPATH}"
python3 scripts/extract.py
python3 scripts/smooth.py
python3 scripts/assign_codepoints.py
for t in exact rounded smooth smoothgame; do scripts/ff.sh scripts/build_font.py "$t" 2>&1 | grep -E "^built|Error|Traceback" || true; done
scripts/ff.sh scripts/check_geometry.py 2>&1 | grep -v "pkg_resources\|UserWarning\|Based on\|License\|BSD\|Version:\|Copyright"
python3 scripts/make_comparison.py
python3 scripts/verify.py
