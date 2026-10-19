#!/bin/bash
# Re-run the formal proof with the guard timeouts the project actually uses.
#
# The guard's idle timeout measures "no complete stdout/stderr line", and
# audit_reverse_engineering_proof.py prints its whole report only once at the
# end, so the idle timer never resets.  The 2026-09-30 receipt that completed
# used wall 9000s / idle 7200s; a 3600s idle budget kills the run at exactly
# 3600s with exit 124 and no report.
set -u
ROOT="/Users/altair/github/gba-naruto-reverse"
RUN_DIR="$ROOT/notes/evidence/reverse-proof-update-20261019-v1"
PY="/usr/local/bin/python3"
export PATH="/Users/altair/github/gba-naruto-reverse/.venv/bin:/usr/local/bin:$PATH"
cd "$ROOT" || exit 1

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
echo "[formal] guard exit: $?"

"$PY" - <<'PYEOF'
import json
report = json.load(open("notes/evidence/reverse-proof-update-20261019-v1/formal-report.json"))
print("complete:", report.get("complete"))
print("blockers:", len(report.get("blockers", [])))
print("verifiers_executed:", len(report.get("verifiers_executed", [])))
gate = report.get("gate_results", {}).get("rom_byte_coverage", {})
audit = gate.get("rom_coverage_audit", {})
print("coverage gate verified:", audit.get("verified"))
print("coverage unknown_bytes:", audit.get("summary", {}).get("unknown_bytes"))
print("contracted_verifier_count:", gate.get("contracted_verifier_count"))
print("banks_complete:", report.get("formal", {}).get("banks_complete"))
PYEOF
echo "[formal] done"
