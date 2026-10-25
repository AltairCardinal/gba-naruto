#!/bin/bash
# Y1: rebuild the remake ROM and capture every compiler warning.
# Usage: y1_build.sh [logfile]
set -u
cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel || exit 2
source /opt/devkitpro/devkitarm.sh || exit 2
export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano
LOG=${1:-/mnt/d/Github/gba-naruto/build/y1-build.log}
make -j4 >"$LOG" 2>&1
rc=$?
echo "make exit=$rc  log=$LOG"
echo "---- stack-usage warnings ----"
grep -n 'stack-usage' "$LOG" | head -40
echo "---- warning count ----"
grep -c 'warning:' "$LOG"
exit $rc
