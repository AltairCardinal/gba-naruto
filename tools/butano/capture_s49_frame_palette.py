#!/usr/bin/env python3
"""Capture the original's frame and its palette RAM in the same frame.

Why this tool exists
--------------------
The original's move-range screen was the biggest unexplained pixel gap in the
S49 remake.  Two earlier kinds of evidence could not settle it:

* a rendered PNG says what a frame looks like but not which palette entries
  produced it;
* a palette dump says which entries exist, but the archives in this
  repository were captured by a **different mGBA build** than the PNGs they
  were compared against, and the two builds do not share a colour space.

This tool therefore captures, in one run and in one frame, the screenshot,
the palette RAM and the I/O registers.  The result is self-consistent: a
consumer can check that the colours in the PNG really are palette entries,
and can compare two frames of the same run without the colour spaces
drifting.

It also records the mGBA binary hash it used, so a receipt can be tied to
the exact emulator build.

Usage::

    python3 tools/butano/capture_s49_frame_palette.py \
        --state artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-19-A.ss9 \
        --rom rom/base.gba \
        --out-dir artifacts/s49-original-movegrid-frame-v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.butano.capture_s49_advance import guard_command  # noqa: E402

DEFAULT_MGBA = ROOT / "build/macos-mgba/build/qt/mGBA.app/Contents/MacOS/mGBA"
SCRIPT = ROOT / "tools/butano/mgba_frame_palette_sequence.lua"

FRAME_COUNT = 6
PRAM_BYTES = 1024
IO_BYTES = 0x60


class FramePaletteError(RuntimeError):
    """The probe did not produce a complete, self-consistent capture."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(
    state: Path,
    rom: Path,
    out_dir: Path,
    settle_frames: int,
    frame_count: int,
    mgba: Path = DEFAULT_MGBA,
) -> dict[str, object]:
    for path, label in ((state, "savestate"), (rom, "ROM"), (mgba, "mGBA")):
        if not Path(path).is_file():
            raise FramePaletteError(f"missing {label}: {path}")
    if not SCRIPT.is_file():
        raise FramePaletteError(f"missing probe script: {SCRIPT}")

    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FramePaletteError(
            f"{out_dir} is not empty; each run needs its own directory so a "
            f"stale capture can never be read as a fresh one")
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema": "konoha.s49-frame-palette-inputs.v1",
        "input_state": str(state),
        "input_state_sha256": sha256_file(Path(state)),
        "rom": str(rom),
        "rom_sha256": sha256_file(Path(rom)),
        "mgba": str(mgba),
        "mgba_sha256": sha256_file(Path(mgba)),
        "script": str(SCRIPT),
        "script_sha256": sha256_file(Path(SCRIPT)),
        "guard": str(ROOT / "tools/run_guarded.py"),
        "guard_sha256": sha256_file(ROOT / "tools/run_guarded.py"),
        "settle_frames": settle_frames,
        "frame_count": frame_count,
    }
    (out_dir / "inputs.json").write_text(
        json.dumps(inputs, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    done_marker = out_dir / "done.json"
    environment = {
        "MGBA_FRAME_INPUT_STATE": str(Path(state).resolve()),
        "MGBA_FRAME_OUTPUT_DIR": str(out_dir.resolve()),
        "MGBA_FRAME_DONE_MARKER": str(done_marker.resolve()),
        "MGBA_FRAME_SETTLE_FRAMES": str(settle_frames),
        "MGBA_FRAME_COUNT": str(frame_count),
    }
    child = [str(mgba), "--script", str(SCRIPT), str(rom)]
    completed = subprocess.run(
        guard_command(out_dir / "guard.json", done_marker, child),
        env={**os.environ, **environment},
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise FramePaletteError(
            f"guarded probe failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:400]}")
    if not done_marker.is_file():
        raise FramePaletteError("probe never wrote its done marker")

    for index in range(frame_count):
        for name, size in (
            (f"pram-{index:02d}.bin", PRAM_BYTES),
            (f"io-{index:02d}.bin", IO_BYTES),
        ):
            path = out_dir / name
            if not path.is_file():
                raise FramePaletteError(f"probe did not write {name}")
            if path.stat().st_size != size:
                raise FramePaletteError(
                    f"{name} is {path.stat().st_size} bytes, expected {size}")
        if not (out_dir / f"frame-{index:02d}.png").is_file():
            raise FramePaletteError(f"probe did not write frame-{index:02d}.png")
    return inputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--settle-frames", type=int, default=2)
    parser.add_argument("--frame-count", type=int, default=FRAME_COUNT)
    parser.add_argument("--mgba", type=Path, default=DEFAULT_MGBA)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inputs = run(
            state=args.state,
            rom=args.rom,
            out_dir=args.out_dir,
            settle_frames=args.settle_frames,
            frame_count=args.frame_count,
            mgba=args.mgba,
        )
    except FramePaletteError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(inputs, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
