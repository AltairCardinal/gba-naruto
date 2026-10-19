#!/bin/bash
# Formal proof with the parallel verifier replay.
#
# 解释器契约（2026-10-20 修正）
# ----------------------------
# 本脚本必须用 **系统解释器** `/usr/local/bin/python3`（3.14.3），并且**不得**
# 把 `.venv/bin` 放在 PATH 最前面。原因：
#
#   `tools/verify_rom_sprite_loader_tail.py::_load_source_verifier()` 里有���
#   一段刻意的兼容 workaround：
#
#       purelib = sysconfig.get_path("purelib")
#       if purelib and purelib not in sys.path:
#           sys.path.append(purelib)
#
#   验证器命令一律带 `-I -S`（隔离模式 + 跳过 site），因此 Pillow 本来不可见，
#   靠这段手动补 purelib 才能 import `PIL`。
#
#   `sysconfig.get_path("purelib")` 取决于**正在运行的那个解释器**：
#     - `/usr/local/bin/python3` → `/usr/local/lib/python3.14/site-packages`（有 Pillow）
#     - `.venv/bin/python`        → `<repo>/.venv/lib/python3.14/site-packages`（**空的**）
#
#   用 venv 解释器跑 formal 时，spec 里的 `python3` 会被解析成 venv 的那个，
#   workaround 静默失效 → `ModuleNotFoundError: No module named 'PIL'`
#   → `verify_rom_sprite_loader_tail.py` exit 1
#   → 多出第 176 个 blocker。**这不是语义失败，是环境漂移。**
#
# 因此：只有 9-30 基线那一轮的**完全相同**解释器解析下，
# 墙钟对比（2,383 s 基线）才成立。
set -u
ROOT="/Users/altair/github/gba-naruto-reverse"
RUN_DIR="$ROOT/notes/evidence/reverse-proof-update-20261019-v1"
PY="/usr/local/bin/python3"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
cd "$ROOT" || exit 1
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
echo "[formal-parallel] guard exit: $CODE  wall: $((END-START))s" | tee "$RUN_DIR/formal-parallel-run.log"
"$PY" - <<'PYEOF' | tee -a "$RUN_DIR/formal-parallel-run.log"
import json
report = json.load(open("notes/evidence/reverse-proof-update-20261019-v1/formal-parallel-report.json"))
print("complete:", report.get("complete"))
print("blockers:", len(report.get("blockers", [])))
print("verifiers_executed:", len(report.get("verifiers_executed", [])))
print("failed_verifiers:", [
    v.get("command", [None])[1] for v in report.get("verifiers_executed", []) if not v.get("contract_ok")
])
gate = report.get("gate_results", {}).get("rom_byte_coverage", {})
print("coverage verified:", gate.get("rom_coverage_audit", {}).get("verified"))
print("unknown_bytes:", gate.get("rom_coverage_audit", {}).get("summary", {}).get("unknown_bytes"))
print("banks_complete:", report.get("banks_complete"))
PYEOF
echo "[formal-parallel] done" | tee -a "$RUN_DIR/formal-parallel-run.log"
