#!/usr/bin/env python3
"""Stream L: one command that reproduces the whole S49 audio-event comparison.

    python tools/s49_audio_l/run_all.py --out build/s49-audio-l

Steps
-----
1. capture_remake_trace  -- drive the remake ROM with the stream J input walk
                            and dump the IWRAM audio-event ring buffer every
                            frame (the instrument stream J was missing).
2. capture_remake_audio  -- record the remake ROM's own audio output and check
                            that the Maxmod mixer keeps running (the remake tree
                            documents a mixer freeze caused by repeated sound
                            effect submission).
3. compare_runtime_events -- pair the original side (stream J's evidence) with
                            the remake's runtime cue sequence and write the
                            per-event difference table.

With ``--repeat 2`` the whole pipeline runs twice into two directories and the
byte identity of every artifact is reported, which is stream J's acceptance
criterion.

Usage:
    python tools/s49_audio_l/run_all.py --out build/s49-audio-l --repeat 2
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

ARTIFACTS = ("remake_trace.json", "remake_audio_analysis.json",
             "event_diff.json", "event_diff.md")


def run(script: str, *args: str) -> None:
    command = [sys.executable, str(HERE / script), *args]
    print(f"\n=== {script} {' '.join(args)}")
    result = subprocess.run(command, cwd=str(REPO))
    if result.returncode != 0:
        raise SystemExit(f"ERR {script} failed with {result.returncode}")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pipeline(out_dir: pathlib.Path, rom: pathlib.Path, elf: pathlib.Path,
             original_dir: pathlib.Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    run("capture_remake_trace.py", "--out", str(out_dir),
        "--rom", str(rom), "--elf", str(elf))
    run("capture_remake_audio.py", "--out", str(out_dir), "--rom", str(rom))
    run("compare_runtime_events.py", "--out", str(out_dir),
        "--original", str(original_dir),
        "--trace", str(out_dir / "remake_trace.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPO / "build" / "s49-audio-l"))
    parser.add_argument("--rom", default=None)
    parser.add_argument("--elf", default=None)
    parser.add_argument("--original", default=str(REPO / "build" / "s49-audio"))
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    remake_root = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
    rom = pathlib.Path(args.rom) if args.rom else remake_root / "butano-sequel.gba"
    elf = pathlib.Path(args.elf) if args.elf else remake_root / "butano-sequel.elf"
    out_dir = pathlib.Path(args.out)

    if args.repeat < 2:
        pipeline(out_dir, rom, elf, pathlib.Path(args.original))
        return 0

    digests: list[dict[str, str]] = []
    for index in range(args.repeat):
        run_dir = out_dir if index == 0 else out_dir / f"repeat{index}"
        pipeline(run_dir, rom, elf, pathlib.Path(args.original))
        digests.append({name: sha256(run_dir / name) for name in ARTIFACTS
                        if (run_dir / name).is_file()})

    print("\n=== determinism (two independent runs, byte identical) ===")
    identical = True
    for name in ARTIFACTS:
        values = {digest.get(name) for digest in digests}
        same = len(values) == 1
        identical = identical and same
        print(f"  {name:32s} {'IDENTICAL' if same else 'DIFFERENT'} "
              f"{sorted(v for v in values if v)}")
    print(f"determinism (run twice byte-identical) = {identical}")
    return 0 if identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
