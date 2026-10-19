#!/bin/bash
# 等待独立审计跑完（它持有 heavy.lock），然后自动开 formal v2。
# 为什么要等：formal 走 tools/run_guarded.py 的 build/resource-guard/heavy.lock，
# 锁被占时会直接 exit 75（lock busy）拒绝，不会排队。
set -u
ROOT="/Users/altair/github/gba-naruto-reverse"
WAIT_PID="${1:-}"
cd "$ROOT" || exit 1
if [ -n "$WAIT_PID" ]; then
  while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 10; done
  echo "[chain] 独立审计 (pid $WAIT_PID) 已结束，等 5 s 让锁释放" >&2
  sleep 5
fi
echo "[chain] 启动 formal v2 $(date -u +%H:%M:%SZ)" >&2
bash notes/evidence/reverse-proof-update-20261020-v2/run_formal_parallel.sh
echo "[chain] formal v2 结束，退出码 $? $(date -u +%H:%M:%SZ)" >&2
