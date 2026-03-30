#!/bin/sh
set -eu

if [ "$#" -lt 2 ]; then
  echo "usage: tools/run_headless_mgba.sh SCRIPT.lua ROM.gba [mGBA args...]" >&2
  exit 2
fi

SCRIPT_PATH=$1
ROM_PATH=$2
shift 2

MGBA_BIN=${MGBA_BIN:-/usr/games/mgba-qt}

if [ ! -x "$MGBA_BIN" ]; then
  # Fallback: try mgba-sdl
  MGBA_BIN=${MGBA_BIN:-/usr/games/mgba}
fi

if [ ! -x "$MGBA_BIN" ]; then
  echo "mGBA binary not found: $MGBA_BIN" >&2
  exit 1
fi

# Check if this binary supports --script
if ! "$MGBA_BIN" --help 2>&1 | grep -q -- '--script'; then
  echo "WARNING: $MGBA_BIN does not support --script (scripting disabled at build time)" >&2
  echo "Use tools/mgba-headless-snapshot.py for headless debugging on this system" >&2
fi

# Determine display strategy
if echo "$MGBA_BIN" | grep -q 'mgba-qt'; then
  # Qt version needs virtual display
  export QT_QPA_PLATFORM=offscreen
fi
export SDL_VIDEODRIVER=dummy
export SDL_AUDIODRIVER=dummy

exec "$MGBA_BIN" \
  -C mute=1 \
  -C volume=0 \
  --script "$SCRIPT_PATH" \
  "$@" \
  "$ROM_PATH"
