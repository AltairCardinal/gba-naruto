#!/bin/bash
# Formal proof with the parallel verifier replay — 第二轮（pin 刷新后）。
#
# 为什么不复用 20261019-v1 那个目录
# -------------------------------
# v1 目录里存着 **3,905 s 那轮的权威收据**（formal-parallel-report.json、
# formal-parallel-guard.json、formal-parallel-run.log 等），那是本轮
# 「解释器解析契约修正后」的唯一证据。formal 是**同名覆盖**写的，
# 直接复用会把基线冲掉且无法回溯。所以另起目录，v1 只读保留。
#
# 解释器契约（2026-10-20 修正，v2 沿用）
# ------------------------------------
# 必须用 **系统解释器** `/usr/local/bin/python3`（3.14.3），且**不得**把
# `.venv/bin` 放在 PATH 最前面。`tools/verify_rom_sprite_loader_tail.py` 里
# 有一段刻意的兼容 workaround（`sysconfig.get_path("purelib")` 手动补 sys.path），
# 而验证器命令一律带 `-I -S`（跳过 site），Pillow 本来不可见，全靠这段补路径。
# `sysconfig.get_path("purelib")` 取决于**正在运行的那个解释器**：
#   - `/usr/local/bin/python3` → `/usr/local/lib/python3.14/site-packages`（有 Pillow）
#   - `.venv/bin/python`        → `<repo>/.venv/lib/python3.14/site-packages`（**空的**）
# 用 venv 解释器跑，workaround 静默失效 → `ModuleNotFoundError: No module named 'PIL'`
# → `verify_rom_sprite_loader_tail.py` exit 1 → 多出第 176 个 blocker。
# **那不是语义失败，是环境漂移。**
set -u
ROOT="/Users/altair/github/gba-naruto-reverse"
RUN_DIR="$ROOT/notes/evidence/reverse-proof-update-20261020-v2"
PY="/usr/local/bin/python3"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
cd "$ROOT" || exit 1
mkdir -p "$RUN_DIR"
START=$(date +%s)
"$PY" tools/run_guarded.py \
  --summary "$RUN_DIR/formal-parallel-guard.json" \
  --lock-file build/resource-guard/heavy.lock \
  --cwd . --wall-timeout-s 9000 --idle-timeout-s 7200 \
  -- \
  "$PY" tools/audit_reverse_engineering_proof.py \
     --root . --execute-verifiers --allow-incomplete \
     --verifier-jobs 4 \
     --output "$RUN_DIR/formal-parallel-report.json" \
  > "$RUN_DIR/formal-parallel-stdout.json" 2> "$RUN_DIR/formal-parallel-stderr.log"
CODE=$?
END=$(date +%s)
echo "[formal-parallel-v2] guard exit: $CODE  wall: $((END-START))s" | tee "$RUN_DIR/formal-parallel-run.log"
"$PY" - <<'PYEOF' | tee -a "$RUN_DIR/formal-parallel-run.log"
import json
report = json.load(open("notes/evidence/reverse-proof-update-20261020-v2/formal-parallel-report.json"))
print("complete:", report.get("complete"))
print("blockers:", len(report.get("blockers", [])))
print("verifiers_executed:", len(report.get("verifiers_executed", [])))
print("failed_verifiers:", [
    v.get("command", [None])[1] for v in report.get("verifiers_executed", []) if not v.get("contract_ok")
])
gate = report.get("gate_results", {}).get("rom_byte_coverage", {})
print("coverage verified:", gate.get("rom_coverage_audit", {}).get("verified"))
print("coverage errors:", gate.get("rom_coverage_audit", {}).get("errors"))
summary = gate.get("rom_coverage_audit", {}).get("summary", {})
print("unknown_bytes:", summary.get("unknown_bytes"), "claims:", summary.get("claim_count"))
PYEOF
exit $CODE
