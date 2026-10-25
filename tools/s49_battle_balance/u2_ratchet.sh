#!/bin/bash
# U2: HEAD baseline unit tests + workspace unit tests, with the failure
# names compared name by name (the "ratchet").
set -u
echo "=== HEAD baseline ==="
bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh \
  > /tmp/u2-baseline.txt 2>&1
echo "baseline exit=$?"
tail -40 /tmp/u2-baseline.txt
echo
echo "=== workspace ==="
bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh \
  > /tmp/u2-workspace.txt 2>&1
echo "workspace exit=$?"
tail -40 /tmp/u2-workspace.txt
echo
echo "=== ratchet: failures only in the workspace ==="
grep -oE 'FAIL\((run|compile)\) [a-z0-9_]+' /tmp/u2-baseline.txt \
  | awk '{print $2}' | sort -u > /tmp/u2-baseline-fails.txt
grep -oE 'FAIL\((run|compile)\) [a-z0-9_]+' /tmp/u2-workspace.txt \
  | awk '{print $2}' | sort -u > /tmp/u2-workspace-fails.txt
echo "baseline failures: $(wc -l < /tmp/u2-baseline-fails.txt)"
echo "workspace failures: $(wc -l < /tmp/u2-workspace-fails.txt)"
echo "--- new failures (must be empty) ---"
comm -13 /tmp/u2-baseline-fails.txt /tmp/u2-workspace-fails.txt
echo "--- fixed failures (informational) ---"
comm -23 /tmp/u2-baseline-fails.txt /tmp/u2-workspace-fails.txt
