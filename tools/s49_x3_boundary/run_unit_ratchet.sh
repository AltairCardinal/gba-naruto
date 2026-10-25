#!/bin/bash
# X3 gate: the remake's unit-test failure set must not grow.
#
# The remake tree has 20 unit tests that are already red at HEAD
# (notes/s49-fidelity/Q-unit-test-baseline.md).  The gate is therefore a
# RATCHET: the workspace failure set must be a subset of the HEAD baseline
# failure set.  A new red test => exit 1.  A test that turns green => fine.
#
# Usage (from WSL):
#   bash /mnt/d/Github/gba-naruto/tools/s49_x3_boundary/run_unit_ratchet.sh
set -u

REMAKE=/mnt/d/Shell/Github/gba-naruto-butano/butano-sequel/game
BASE=/mnt/d/Github/gba-naruto/build/head-baseline/butano-sequel/game
# A unique output directory per invocation: two concurrent ratchets would
# otherwise overwrite each other's test binaries mid-run.
OUT=/tmp/x3-unit-ratchet-$$
mkdir -p "$OUT"
trap 'rm -rf "$OUT"' EXIT

# The HEAD baseline snapshot has to exist (git archive HEAD butano-sequel/game).
if [ ! -d "$BASE/tests" ]; then
    echo "ERR missing HEAD baseline: $BASE/tests" >&2
    echo "  extract it with:" >&2
    echo "  git -C /mnt/d/Shell/Github/gba-naruto-butano archive --output=head.tar HEAD butano-sequel/game" >&2
    echo "  tar -xf head.tar -C /mnt/d/Github/gba-naruto/build/head-baseline" >&2
    exit 2
fi

run_suite() {
    local include="$1" testdir="$2" list="$3" label="$4"
    local pass=0 fail=0
    : > "$list"
    for f in "$testdir"/tests/test_*.cpp; do
        t=$(basename "$f" .cpp)
        if g++ -std=c++23 -Wall -Wextra -Werror -pedantic \
                -I "$include" "$f" -o "$OUT/$label-$t" 2>"$OUT/$label-$t.log"; then
            if "$OUT/$label-$t" >"$OUT/$label-$t.run" 2>&1; then
                pass=$((pass + 1))
            else
                echo "$t" >> "$list"
                fail=$((fail + 1))
            fi
        else
            echo "$t" >> "$list"
            fail=$((fail + 1))
        fi
    done
    echo "$label: pass=$pass fail=$fail"
}

run_suite "$BASE/include" "$BASE" "$OUT/base-fails.txt" base
run_suite "$REMAKE/include" "$REMAKE" "$OUT/ws-fails.txt" ws

sort -u "$OUT/base-fails.txt" -o "$OUT/base-fails.txt"
sort -u "$OUT/ws-fails.txt" -o "$OUT/ws-fails.txt"

echo "--- new red tests (must be empty) ---"
NEW=$(comm -13 "$OUT/base-fails.txt" "$OUT/ws-fails.txt")
if [ -n "$NEW" ]; then
    echo "$NEW"
fi
echo "--- fixed tests (informational) ---"
comm -23 "$OUT/base-fails.txt" "$OUT/ws-fails.txt"
echo "--- X3-owned tests ---"
for t in test_battle_roster_cross_side test_battle_roster_scheduler \
         test_battle_campaign_sram_trigger; do
    if grep -qx "$t" "$OUT/ws-fails.txt"; then
        echo "RED  $t"
    else
        echo "GREEN $t"
    fi
done

if [ -n "$NEW" ]; then
    echo "RATCHET: FAIL (new red tests)"
    exit 1
fi
echo "RATCHET: OK (workspace failures are a subset of the HEAD baseline)"
exit 0
