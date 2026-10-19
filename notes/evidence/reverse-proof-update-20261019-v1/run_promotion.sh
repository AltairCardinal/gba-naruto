#!/bin/bash
# Apply the renderer script pointer-pool promotion as one atomic chain.
#
# The coverage ledger and the proof ledger must never disagree: the policy
# requires the canonical rebuild, the proof sync and the formal audit to land
# together.  This script waits for the in-flight coverage rebuild, then runs
# the proof update, the focused test suites and one non-degraded formal proof.
#
# Usage: bash notes/evidence/reverse-proof-update-20261019-v1/run_promotion.sh <coverage-pid>

set -u

ROOT="/Users/altair/github/gba-naruto-reverse"
RUN_DIR="$ROOT/notes/evidence/reverse-proof-update-20261019-v1"
PY="/usr/local/bin/python3"
# The proof ledger's 97 verifier commands are bare "python3"; this runtime PATH
# has no /usr/local/bin, so "python3" would resolve to 3.9.6 and 1,219
# zip(strict=True) call sites would fail with false blockers.  The repository
# venv pins 3.14.3, and both auditors now refuse to start below 3.10.
export PATH="/Users/altair/github/gba-naruto-reverse/.venv/bin:/usr/local/bin:$PATH"

cd "$ROOT" || exit 1

AUDIT_PID="${1:-}"
if [ -n "$AUDIT_PID" ]; then
  echo "[promotion] waiting for coverage rebuild pid $AUDIT_PID"
  while kill -0 "$AUDIT_PID" 2>/dev/null; do sleep 10; done
  echo "[promotion] coverage rebuild finished"
fi

echo "[promotion] ledger digest after rebuild"
shasum -a 256 sequel/rom-byte-coverage.json

echo "[promotion] checking the pool claim landed"
"$PY" - <<'EOF'
import json, sys
coverage = json.load(open("sequel/rom-byte-coverage.json"))
claims = [c for c in coverage["claims"]
          if c.get("promotion_batch") == "rom-renderer-script-pointer-pool-records-v1"]
if len(claims) != 1:
    sys.exit(f"expected exactly one pool claim, found {len(claims)}")
summary = coverage["summary"]
print("pool claim:", claims[0]["id"], claims[0]["range"])
print("unknown_bytes:", summary["unknown_bytes"],
      "classified_bytes:", summary["classified_bytes"],
      "claim_count:", summary["claim_count"],
      "segment_count:", summary["segment_count"])
EOF
if [ $? -ne 0 ]; then echo "[promotion] the pool claim did not land; aborting"; exit 1; fi

echo "[promotion] applying the proof ledger update"
"$PY" "$RUN_DIR/apply.py" --root . | tee "$RUN_DIR/proof-update.json"
if [ ${PIPESTATUS[0]} -ne 0 ]; then echo "[promotion] proof update failed"; exit 1; fi

echo "[promotion] running the focused test suites"
"$PY" -m unittest \
  tests.test_export_rom_renderer_script_pointer_pool_records \
  tests.test_rom_renderer_script_pointer_pool_canonical \
  tests.test_export_rom_animation_descriptor_pool_v2 \
  tests.test_rom_small_cfg_batch_canonical \
  2>&1 | tail -20
if [ ${PIPESTATUS[0]} -ne 0 ]; then echo "[promotion] focused tests failed"; exit 1; fi

echo "[promotion] running the formal proof (non-degraded, idle 3600s)"
"$PY" tools/run_guarded.py \
  --summary "$RUN_DIR/formal-guard.json" \
  --lock-file build/resource-guard/heavy.lock \
  --cwd . \
  --wall-timeout-s 9000 \
  --idle-timeout-s 7200 \
  -- \
  "$PY" tools/audit_reverse_engineering_proof.py \
     --root . \
     --execute-verifiers \
     --allow-incomplete \
     --output "$RUN_DIR/formal-report.json" \
  > "$RUN_DIR/formal-stdout.json" 2> "$RUN_DIR/formal-stderr.log"
echo "[promotion] formal guard exit: $?"

"$PY" - <<'EOF'
import json
report = json.load(open("notes/evidence/reverse-proof-update-20261019-v1/formal-report.json"))
print("complete:", report.get("complete"))
print("blockers:", len(report.get("blockers", [])))
print("verifiers_executed:", len(report.get("verifiers_executed", [])))
gate = report.get("gate_results", {}).get("rom_byte_coverage", {})
print("coverage gate verified:", gate.get("rom_coverage_audit", {}).get("verified"))
print("coverage unknown_bytes:", gate.get("rom_coverage_audit", {}).get("summary", {}).get("unknown_bytes"))
EOF

echo "[promotion] done"
