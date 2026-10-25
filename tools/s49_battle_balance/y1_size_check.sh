#!/bin/bash
# Y1: measure sizeof/offsets of battle_scene_presentation_event for
#   (a) the HEAD snapshot of the remake tree  (build/y1-size/head/konoha/...)
#   (b) the current working tree
# and diff them. A size-neutral fix means the two dumps are identical.
set -u
REPO=/mnt/d/Shell/Github/gba-naruto-butano
WS=/mnt/d/Github/gba-naruto
OUT=$WS/build/y1-size
PROBE=$WS/tools/s49_battle_balance/y1_size_probe.cpp

rm -rf "$OUT/bin"
mkdir -p "$OUT/bin"

if [ ! -f "$OUT/head/konoha/battle_scene_presentation_event.h" ]; then
  echo "MISSING $OUT/head/konoha/battle_scene_presentation_event.h"
  echo "Run tools/s49_battle_balance/y1_dump_head.sh first (Windows git)."
  exit 2
fi

# (a) HEAD snapshot of the header.  The Windows-side git cannot be used from
# WSL (the remake tree is a Windows worktree), so the HEAD header is dumped
# by the caller into build/y1-size/head/konoha/.  build/head-baseline/ is
# verified byte-identical to `git show HEAD:...` by tools/s49_battle_balance/
# y1_dump_head.sh.
BASE=/mnt/d/Github/gba-naruto/build/head-baseline/butano-sequel/game
HEAD_INC="-I $OUT/head -I $REPO/butano-sequel/game/include"

g++ -std=c++23 -Wall -Wextra -pedantic -I "$OUT/head" $HEAD_INC \
    "$PROBE" -o "$OUT/bin/probe_head" 2>"$OUT/head.log"
rc_head=$?
g++ -std=c++23 -Wall -Wextra -pedantic -DY1_HAS_SETTLEMENT \
    -I "$REPO/butano-sequel/game/include" \
    "$PROBE" -o "$OUT/bin/probe_cur" 2>"$OUT/cur.log"
rc_cur=$?

if [ $rc_head -ne 0 ]; then
  echo "HEAD probe compile FAILED"; tail -20 "$OUT/head.log"; exit 2
fi
if [ $rc_cur -ne 0 ]; then
  echo "WORKTREE probe compile FAILED"; tail -20 "$OUT/cur.log"; exit 2
fi

"$OUT/bin/probe_head" > "$OUT/head.txt"
"$OUT/bin/probe_cur"  > "$OUT/cur.txt"

echo "==== HEAD ===="
head -3 "$OUT/head.txt"
echo "==== WORKTREE ===="
head -3 "$OUT/cur.txt"
echo "==== diff (member offsets) ===="
if diff -u "$OUT/head.txt" "$OUT/cur.txt"; then
  echo "IDENTICAL: sizeof + every member offset match HEAD byte-for-byte"
else
  echo "DIFFERENT (see diff above)"
fi
