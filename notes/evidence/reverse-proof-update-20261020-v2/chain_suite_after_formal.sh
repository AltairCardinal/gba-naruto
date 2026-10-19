#!/bin/bash
# 等 formal v2 结束后，跑修复后的 93 个 proof 测试全量套件。
# 顺序理由：套件里最慢的那条用例会**在进程内再跑一遍覆盖审计器**，
# 与 formal 的 verifier[0] 撞车会把 formal 的墙钟数字污染掉
# （上一轮实测：争用下覆盖段被放大 8.8×）。先拿准 formal 墙钟，再跑套件。
set -u
ROOT="/Users/altair/github/gba-naruto-reverse"
PY="/usr/local/bin/python3"
cd "$ROOT" || exit 1
WAIT_PID="${1:-}"
if [ -n "$WAIT_PID" ]; then
  while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 15; done
  echo "[suite] formal 链已结束 $(date -u +%H:%M:%SZ)，开始 93 测试全量" >&2
fi
START=$(date +%s)
"$PY" -m unittest -v tests.test_audit_reverse_engineering_proof \
  > /tmp/proof-suite9-full.log 2>&1
CODE=$?
END=$(date +%s)
echo "[suite] exit=$CODE  wall=$((END-START))s  $(date -u +%H:%M:%SZ)" >&2
tail -5 /tmp/proof-suite9-full.log >&2
exit $CODE
