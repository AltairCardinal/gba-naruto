#!/bin/sh
set -eu

if [ "$#" -lt 2 ]; then
  echo "usage: tools/run_headless_mgba.sh SCRIPT.lua ROM.gba [mGBA args...]" >&2
  exit 2
fi

SCRIPT_PATH=$1
ROM_PATH=$2
shift 2

MGBA_BIN=${MGBA_BIN:-/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA}

if [ ! -x "$MGBA_BIN" ]; then
  echo "mGBA binary not found: $MGBA_BIN" >&2
  exit 1
fi

exec env QT_QPA_PLATFORM=offscreen "$MGBA_BIN" \
  -C mute=1 \
  -C volume=0 \
  --script "$SCRIPT_PATH" \
  "$@" \
  "$ROM_PATH"
