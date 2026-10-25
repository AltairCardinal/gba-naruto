#!/bin/bash
# Compile and run every unit test in a directory, and report the *names* of the
# ones that fail.
#
#   run_unit_tests.sh <tests-dir> <include-dir> <out-tsv>
#
# The flags are the ones the project's other runners use
# (`build/w1-run-all-tests.sh`, `build/h2-run-tests.sh`):
#
#   g++ -std=c++23 -Wall -Wextra -Werror -pedantic -I <include-dir>
#
# Output is a TSV with one line per test:
#
#   <name>\tpass|fail\t<phase>\t<detail>
#
# The phase is "compile" when the test did not build and "run" when it built
# but the binary returned non-zero.  The name of every failing test is what the
# pipeline's ratchet gate compares against the HEAD baseline.
#
# Exit code is 0 when every test passed and 1 when at least one failed.  The
# caller must not treat a non-zero exit as "the pipeline broke": the ratchet
# gate decides, by comparing the failing *set* against the baseline.
set -u

TESTS_DIR="$1"
INCLUDE_DIR="$2"
OUT_TSV="$3"

if [ ! -d "$TESTS_DIR" ]; then
    echo "ERR tests dir not found: $TESTS_DIR" >&2
    exit 2
fi
if [ ! -d "$INCLUDE_DIR" ]; then
    echo "ERR include dir not found: $INCLUDE_DIR" >&2
    exit 2
fi

OUT_DIR="$(dirname "$OUT_TSV")"
mkdir -p "$OUT_DIR"
: > "$OUT_TSV"

WORK="$(mktemp -d /tmp/s49-unit-tests-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

status=0
pass=0
fail=0
for f in "$TESTS_DIR"/test_*.cpp; do
    [ -e "$f" ] || continue
    t="$(basename "$f" .cpp)"
    if g++ -std=c++23 -Wall -Wextra -Werror -pedantic \
        -I "$INCLUDE_DIR" "$f" -o "$WORK/$t" 2>"$WORK/$t.log"; then
        if "$WORK/$t" >"$WORK/$t.run" 2>&1; then
            printf '%s\tpass\trun\t\n' "$t" >> "$OUT_TSV"
            pass=$((pass + 1))
        else
            detail="$(grep -m1 -o 'Assertion.*failed' "$WORK/$t.run" || tail -1 "$WORK/$t.run")"
            detail="$(printf '%s' "$detail" | tr '\t\n' '  ' | cut -c1-160)"
            printf '%s\tfail\trun\t%s\n' "$t" "$detail" >> "$OUT_TSV"
            fail=$((fail + 1))
            status=1
        fi
    else
        detail="$(grep -m1 'error:' "$WORK/$t.log" | tr '\t\n' '  ' | cut -c1-160)"
        printf '%s\tfail\tcompile\t%s\n' "$t" "$detail" >> "$OUT_TSV"
        fail=$((fail + 1))
        status=1
    fi
done

echo "unit-tests: total=$((pass + fail)) pass=$pass fail=$fail status=$status"
echo "wrote $OUT_TSV"
exit $status
