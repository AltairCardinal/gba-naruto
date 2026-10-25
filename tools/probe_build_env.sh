#!/usr/bin/env bash
# Local environment probe for the Butano remake line.
# Run inside WSL:  bash tools/probe_build_env.sh
set -u
echo "=== devkitARM ==="
if [ -f /opt/devkitpro/devkitarm.sh ]; then
  # shellcheck disable=SC1091
  source /opt/devkitpro/devkitarm.sh
  arm-none-eabi-gcc --version 2>&1 | head -1
  echo "DEVKITPRO=${DEVKITPRO:-unset}"
else
  echo "devkitarm.sh NOT FOUND"
fi
echo "=== make / python ==="
make --version 2>&1 | head -1
python3 --version 2>&1
echo "=== mGBA ==="
command -v mgba || echo "mgba NOT on PATH"
command -v mgba-qt || echo "mgba-qt NOT on PATH"
mgba --version 2>&1 | head -3
echo "--- script support (needed by the recording chain) ---"
mgba --help 2>&1 | grep -i -E '\-\-script|\-\-features|loglevel' || echo "(no --script in help)"
echo "=== python modules used by the repo probes ==="
python3 - <<'PY'
for m in ("zlib", "struct", "hashlib", "json", "sqlite3"):
    try:
        __import__(m)
        print(f"  {m}: ok")
    except Exception as exc:  # noqa: BLE001
        print(f"  {m}: MISSING ({exc})")
PY
