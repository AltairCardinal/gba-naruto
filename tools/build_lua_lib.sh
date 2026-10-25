#!/usr/bin/env bash
# Wrapper so the Lua static library can be built from WSL too.
#
# The real build lives in tools/build_lua_lib.ps1 because the toolchain is
# MSVC (cl.exe / lib.exe).  From WSL, hand the work to the Windows shell:
#
#     bash tools/build_lua_lib.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIN_SCRIPT="$(wslpath -w "$SCRIPT_DIR/build_lua_lib.ps1")"

powershell.exe -ExecutionPolicy Bypass -File "$WIN_SCRIPT"
