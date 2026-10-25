#!/usr/bin/env python3
"""Prepare an isolated verification tree for stream L's audio verification.

The remake tree is being edited by other flows in parallel (G edits
``battle_runtime_scene.cpp``, H2 edits the palette/visual headers).  Their
in-flight state can crash the ROM, which would block the audio verification.

This script copies the remake tree into ``build/remake-audio-verify`` and
restores every file that stream L does NOT own back to its git HEAD state, so
the verification ROM contains exactly "HEAD + stream L's audio changes".
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

REMAKE = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
DST_ROOT = pathlib.Path(r"D:\Github\gba-naruto\build\remake-audio-verify")
DST = DST_ROOT / "butano-sequel"

# Files stream L owns; they stay as they are in the remake tree.
STREAM_L_FILES = {
    "butano-sequel/game/include/konoha/battle_audio_director.h",
    "butano-sequel/game/include/konoha/battle_audio_runtime.h",
    "butano-sequel/game/include/konoha/battle_audio_event_trace.h",
    "butano-sequel/game/tests/test_battle_audio_director.cpp",
    "butano-sequel/audio/sound_010.s3m",
    "butano-sequel/audio/sound_146.wav",
    "butano-sequel/audio/sound_152.wav",
}


def git(*args: str, binary: bool = False):
    result = subprocess.run(["git", "-C", str(REMAKE), *args],
                            capture_output=True)
    if result.returncode != 0:
        raise SystemExit(
            f"ERR git {' '.join(args)}: {result.stderr.decode('utf-8', 'replace')}")
    if binary:
        return result.stdout
    return result.stdout.decode("utf-8")


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    for name in ("game", "graphics", "audio", "src", "benchmark"):
        source = REMAKE / "butano-sequel" / name
        if source.is_dir():
            target = DST / name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
    shutil.copy2(REMAKE / "butano-sequel" / "Makefile", DST / "Makefile")

    junction = DST_ROOT / "third_party"
    if not junction.exists():
        junction.symlink_to(REMAKE / "third_party", target_is_directory=True)

    status = git("status", "--porcelain", "butano-sequel")
    restored = []
    for line in status.splitlines():
        state, path = line[:2].strip(), line[3:].strip()
        if state == "??":
            if path in STREAM_L_FILES:
                continue
            candidate = REMAKE / path
            if candidate.is_file():
                target = DST_ROOT / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate, target)
            continue
        if path in STREAM_L_FILES:
            continue
        content = git("show", f"HEAD:{path}", binary=True)
        target = DST_ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        restored.append(path)

    print(f"restored {len(restored)} files to HEAD:")
    for path in restored:
        print("   ", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
