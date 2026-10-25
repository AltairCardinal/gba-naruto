#!/usr/bin/env python3
"""Bisect helper: move the audio event trace ring buffer between IWRAM/EWRAM.

Stream L.  The verification ROM crashes during the input walk.  The leading
hypothesis is an IWRAM stack collision: the battle runtime scene has stack
frames of ~16 kB, so growing ``.bss`` by 1 kB moves the top of ``.bss`` into
the stack's reachable range, and the crash happens exactly at the deepest call
(a corrupted return address).

This script patches the verification tree's trace header so the ring buffer
lives in EWRAM (``BN_DATA_EWRAM_BSS`` -> the ``.sbss`` section) instead of the
default ``.bss`` section (IWRAM), which keeps ``.bss`` at its original size.

Usage:
    python tools/s49_audio_l/patch_trace_placement.py ewram|iwram
"""
from __future__ import annotations

import pathlib
import sys

TREE = pathlib.Path(
    r"D:\Github\gba-naruto\build\remake-audio-verify\butano-sequel")
HEADER = TREE / "game" / "include" / "konoha" / "battle_audio_event_trace.h"

IWRAM = """inline battle_audio_trace_entry
        battle_audio_trace_buffer[battle_audio_trace_capacity] = {};"""

EWRAM = """inline __attribute__((section(".ewram"))) battle_audio_trace_entry
        battle_audio_trace_buffer[battle_audio_trace_capacity] = {};"""

EWRAM_BSS = """inline __attribute__((section(".sbss"))) battle_audio_trace_entry
        battle_audio_trace_buffer[battle_audio_trace_capacity] = {};"""


def main() -> int:
    placement = sys.argv[1] if len(sys.argv) > 1 else "ewram"
    text = HEADER.read_text(encoding="utf-8")
    if "#include \"bn_hw_common.h\"" in text:
        text = text.replace("#include \"bn_hw_common.h\"\n\n", "", 1)
    if placement == "ewram":
        target = EWRAM
    elif placement == "ewram-bss":
        target = EWRAM_BSS
    elif placement == "iwram":
        target = IWRAM
    else:
        raise SystemExit(f"unknown placement: {placement}")
    for body in (IWRAM, EWRAM, EWRAM_BSS):
        if body in text and body != target:
            text = text.replace(body, target)
    if target not in text:
        raise SystemExit("ERR the trace buffer declaration was not found")
    HEADER.write_text(text, encoding="utf-8", newline="\n")
    print(f"trace buffer placement: {placement}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
