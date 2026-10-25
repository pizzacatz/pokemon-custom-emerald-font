#!/bin/sh
# Re-run the smoothing on the override files, rebuild Emerald Rounded Game, render previews.
# For another game font set EMERALD_VARIANT (narrow, small, short, small_narrow): EMERALD_VARIANT=small ./preview.sh "a"
# Exits non-zero (and prints the error) if any override file is broken or the build fails.
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/pylib${PYTHONPATH:+:$PYTHONPATH}"
python3 scripts/smooth.py > build/smooth.log 2> build/smooth.err
rc=$?
head -1 build/smooth.log
grep -v '^Internal Error' build/smooth.err | grep -i 'error\|broken\|Traceback' | head -20
[ $rc -ne 0 ] && echo "smooth.py FAILED (exit $rc) -- fix the override above, the old shape was kept" && exit $rc
python3 scripts/preview_glyph.py "$@" 2>&1 | grep -v '^Internal Error'
