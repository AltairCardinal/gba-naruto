#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: tools/trace_dialogue_callers.sh ROM.gba [walk.lua]" >&2
  exit 2
fi

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
ROM_PATH=$1
WALK_SCRIPT=${2:-"$ROOT/tools/mgba_newgame_walk.lua"}
MGBA_BIN=${MGBA_BIN:-/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA}
LOG_PATH=${NARUTO_LLDB_TRACE_LOG:-"$ROOT/notes/lldb-dialogue-callers.log"}
MGBA_STDOUT_LOG=${NARUTO_LLDB_MGBA_LOG:-"$ROOT/notes/lldb-dialogue-callers-mgba.log"}
LLDB_LOG=${NARUTO_LLDB_SESSION_LOG:-"$ROOT/notes/lldb-dialogue-callers-session.log"}

pkill -f "$MGBA_BIN" >/dev/null 2>&1 || true
rm -f "$LOG_PATH" "$LOG_PATH.done" "$MGBA_STDOUT_LOG" "$LLDB_LOG"

env QT_QPA_PLATFORM=offscreen \
  "$MGBA_BIN" \
  -C mute=1 \
  -C volume=0 \
  -g \
  --script "$WALK_SCRIPT" \
  "$ROM_PATH" >"$MGBA_STDOUT_LOG" 2>&1 &
MGBA_PID=$!

cleanup() {
  kill "$MGBA_PID" >/dev/null 2>&1 || true
  wait "$MGBA_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

READY=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if lldb -b -o "target create $MGBA_BIN" -o "gdb-remote localhost:2345" -o "quit" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "failed to connect to mGBA GDB stub on localhost:2345" >&2
  exit 1
fi

LLDB_CMDS=$(mktemp)
cat >"$LLDB_CMDS" <<EOF
target create $MGBA_BIN
command script import $ROOT/tools/lldb_trace_dialogue_callers.py
script lldb_trace_dialogue_callers.reset("$LOG_PATH")
gdb-remote localhost:2345
breakpoint set --address 0x08077D0E
breakpoint command add -s python 1 -F lldb_trace_dialogue_callers.log_and_continue
breakpoint set --address 0x08089B36
breakpoint command add -s python 2 -F lldb_trace_dialogue_callers.log_and_continue
breakpoint set --address 0x0809159C
breakpoint command add -s python 3 -F lldb_trace_dialogue_callers.log_and_continue
breakpoint set --address 0x08093842
breakpoint command add -s python 4 -F lldb_trace_dialogue_callers.log_and_continue
breakpoint set --address 0x0809678A
breakpoint command add -s python 5 -F lldb_trace_dialogue_callers.log_and_continue
breakpoint set --address 0x080968A0
breakpoint command add -s python 6 -F lldb_trace_dialogue_callers.log_and_continue
breakpoint set --address 0x0809698E
breakpoint command add -s python 7 -F lldb_trace_dialogue_callers.log_and_continue
continue
script lldb_trace_dialogue_callers.finish_marker("lldb_complete")
quit
EOF

lldb -b -s "$LLDB_CMDS" >"$LLDB_LOG" 2>&1 || true
rm -f "$LLDB_CMDS"
