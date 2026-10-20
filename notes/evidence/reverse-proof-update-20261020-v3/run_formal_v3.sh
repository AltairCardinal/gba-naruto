#!/bin/bash
# Formal proof, third round (2026-10-20): after the Tier-2 threshold exception
# promoted three packages (3,361 B) and the auditor gained their claim
# projections.
#
# Interpreter contract (inherited from the 2026-10-20 v2 correction and kept
# unchanged here):
#   * MUST use the system interpreter /usr/local/bin/python3 (3.14.3);
#   * MUST NOT put .venv/bin first on PATH.
#   tools/audit_reverse_engineering_proof.py replaces the spec's "python3" with
#   sys.executable, so the child verifiers run under the *auditor's*
#   interpreter.  Under .venv the sprite-loader-tail verifier's purelib
#   workaround silently dies (the venv's own purelib is empty) and the run
#   gains a 176th blocker.  That is environment drift, not a semantic failure.
#
# Why a new directory:
#   v1 holds the 3,905 s authoritative receipt, v2 holds the 175-blocker
#   receipt.  This round writes to v3 so neither baseline is overwritten.
set -u
ROOT="/Users/altair/github/gba-naruto-reverse"
RUN_DIR="$ROOT/notes/evidence/reverse-proof-update-20261020-v3"
PY="/usr/local/bin/python3"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
cd "$ROOT" || exit 1
mkdir -p "$RUN_DIR"
START=$(date +%s)
"$PY" tools/run_guarded.py \
  --summary "$RUN_DIR/formal-guard.json" \
  --lock-file build/resource-guard/heavy.lock \
  --cwd . --wall-timeout-s 9000 --idle-timeout-s 7200 \
  -- \
  "$PY" tools/audit_reverse_engineering_proof.py \
     --root . --execute-verifiers --allow-incomplete \
     --verifier-jobs 4 \
     --output "$RUN_DIR/formal-report.json" \
  > "$RUN_DIR/formal-stdout.json" 2> "$RUN_DIR/formal-stderr.log"
CODE=$?
END=$(date +%s)
echo "[formal-v3] guard exit: $CODE  wall: $((END-START))s" | tee "$RUN_DIR/formal-run.log"
"$PY" - <<'PYEOF' | tee -a "$RUN_DIR/formal-run.log"
import json
report = json.load(open("notes/evidence/reverse-proof-update-20261020-v3/formal-report.json"))
print("complete:", report.get("complete"))
print("blockers:", len(report.get("blockers", [])))
print("verifiers_executed:", len(report.get("verifiers_executed", [])))
print("failed_verifiers:", [
    v.get("label") for v in report.get("verifiers_executed", [])
    if not v.get("contract_ok")
])
print("trust_anchor:", json.dumps(report.get("trust_anchor"), ensure_ascii=False))
summary = (
    report.get("gate_results", {})
    .get("rom_byte_coverage", {})
    .get("rom_coverage_audit", {})
    .get("summary", {})
)
print("coverage summary:", json.dumps({
    k: summary.get(k) for k in (
        "unknown_bytes", "classified_bytes", "claim_count", "segment_count"
    )
}, ensure_ascii=False))
PYEOF
exit "$CODE"
