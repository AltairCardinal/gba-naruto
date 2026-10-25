#!/bin/bash
# Y1 unit test ratchet: HEAD baseline vs the working tree.
#
# The failure set may not grow: every test that fails on the HEAD baseline
# has to keep failing, and no new name may appear.
#
# The output directories are unique per run ($$): two ratchets running at the
# same time would overwrite each other's test binaries and turn the result
# into a false red (that happened to the X3 stream, see
# notes/s49-fidelity/X3-boundary-fixes.md).
set -u
REPO=/mnt/d/Github/gba-naruto
BASE=$REPO/build/head-baseline/butano-sequel/game
TREE=/mnt/d/Shell/Github/gba-naruto-butano/butano-sequel/game
OUT=/tmp/y1-ratchet-$$
mkdir -p "$OUT/base" "$OUT/work"
: > "$OUT/base-fails.txt"
: > "$OUT/work-fails.txt"

run_suite() {
  local src=$1
  local out=$2
  local fails=$3
  local pass=0
  local fail=0
  for f in "$src"/tests/test_*.cpp; do
    t=$(basename "$f" .cpp)
    if g++ -std=c++23 -Wall -Wextra -Werror -pedantic \
        -I "$src/include" "$f" -o "$out/$t" 2>"$out/$t.log"; then
      if "$out/$t" >"$out/$t.run" 2>&1; then
        pass=$((pass + 1))
      else
        fail=$((fail + 1))
        echo "$t" >> "$fails"
      fi
    else
      fail=$((fail + 1))
      echo "$t" >> "$fails"
    fi
  done
  echo "pass=$pass fail=$fail"
}

echo "--- HEAD baseline ---"
run_suite "$BASE" "$OUT/base" "$OUT/base-fails.txt"
echo "--- working tree ---"
run_suite "$TREE" "$OUT/work" "$OUT/work-fails.txt"

echo "--- baseline failures ---"
sort "$OUT/base-fails.txt"
echo "--- working tree failures ---"
sort "$OUT/work-fails.txt"
echo "--- new red (working tree failures that are not in the baseline) ---"
comm -13 <(sort -u "$OUT/base-fails.txt") <(sort -u "$OUT/work-fails.txt")
NEW=$(comm -13 <(sort -u "$OUT/base-fails.txt") <(sort -u "$OUT/work-fails.txt") | wc -l)
echo "new red count: $NEW"
rm -rf "$OUT"
if [ "$NEW" -ne 0 ]; then
  exit 1
fi
exit 0
