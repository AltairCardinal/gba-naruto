#!/usr/bin/env python3
"""Record the original ROM and the remake on one input contract and diff them.

Both sides are captured with the same key, hold length, frame count and input
anchor, so a full-screen same-index pixel comparison is meaningful. Every run
gets its own directory and an inputs manifest that pins ROM, savestate, script
and emulator hashes; nothing overwrites earlier evidence.
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
from typing import Mapping, Sequence

from tools.butano.compare_frame_sequences import compare_sequences

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MGBA = ROOT / "build/macos-mgba/build/qt/mGBA.app/Contents/MacOS/mGBA"
RECORD_SCRIPT = ROOT / "tools/butano/mgba_original_input_frame_sequence.lua"
GUARD = ROOT / "tools/run_guarded.py"


class CaptureError(RuntimeError):
    """A side of the pair was not recorded exactly as requested."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_environment(
    output_dir: Path,
    done_marker: Path,
    state: Path,
    rom: Path,
    key: str,
    hold_frames: int,
    frame_count: int,
    pre_input_frames: int,
) -> dict[str, str]:
    return {
        "MGBA_ORIGINAL_INPUT_SEQUENCE_INPUT_STATE": str(state),
        "MGBA_ORIGINAL_INPUT_SEQUENCE_INPUT_STATE_SHA256": sha256_file(state),
        "MGBA_ORIGINAL_INPUT_SEQUENCE_OUTPUT_DIR": str(output_dir),
        "MGBA_ORIGINAL_INPUT_SEQUENCE_DONE_MARKER": str(done_marker),
        "MGBA_ORIGINAL_INPUT_SEQUENCE_KEY": key,
        "MGBA_ORIGINAL_INPUT_SEQUENCE_HOLD_FRAMES": str(hold_frames),
        "MGBA_ORIGINAL_INPUT_SEQUENCE_FRAME_COUNT": str(frame_count),
        "MGBA_ORIGINAL_INPUT_SEQUENCE_RECORD_ALL": "1",
        "MGBA_ORIGINAL_INPUT_SEQUENCE_PRE_INPUT_FRAMES": str(pre_input_frames),
    }


def guard_command(
    summary: Path,
    success_marker: Path,
    child: Sequence[str],
) -> list[str]:
    return [
        sys.executable, str(GUARD),
        "--summary", str(summary),
        "--success-marker", str(success_marker),
        "--wall-timeout-s", "600",
        "--idle-timeout-s", "60",
        "--min-available-mib", "1024",
        "--", *child,
    ]


def save_state_hash(rom: Path) -> str | None:
    """Hash the cartridge SRAM sidecar, which GBA savestates do not restore.

    mGBA loads ``<rom-stem>.sav`` next to the ROM, and a savestate only covers
    the console, not the cartridge memory.  Two runs that share a savestate can
    still diverge if the sidecar differs, so it belongs in the input contract.
    """
    sidecar = rom.with_suffix(".sav")
    return sha256_file(sidecar) if sidecar.is_file() else None


def record_side(
    label: str,
    out_dir: Path,
    rom: Path,
    state: Path,
    mgba: Path,
    key: str,
    hold_frames: int,
    frame_count: int,
    pre_input_frames: int,
) -> dict[str, object]:
    if out_dir.exists():
        raise CaptureError(f"capture directory already exists: {out_dir}")
    out_dir.mkdir(parents=True)
    done_marker = out_dir / "done.json"
    environment = record_environment(
        out_dir, done_marker, state, rom, key, hold_frames, frame_count,
        pre_input_frames)
    child = [
        str(mgba), "--script", str(RECORD_SCRIPT), str(rom),
    ]
    completed = subprocess.run(
        guard_command(out_dir / "guard.json", done_marker, child),
        env={**os.environ, **environment},
        text=True, capture_output=True, check=False,
    )
    audit_path = out_dir / "audit.json"
    if not audit_path.is_file():
        raise CaptureError(
            f"{label} capture produced no audit: {completed.stderr.strip()[:400]}")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    expected = out_dir / f"frame-{frame_count - 1:03d}.png"
    if not expected.is_file():
        raise CaptureError(f"{label} capture is missing its last frame")
    return {
        "label": label,
        "dir": str(out_dir),
        "rom": str(rom),
        "rom_sha256": sha256_file(rom),
        "state": str(state),
        "state_sha256": sha256_file(state),
        "save_sha256": save_state_hash(Path(rom)),
        "audit": audit,
        "audit_sha256": sha256_file(audit_path),
        "frames": frame_count,
    }


def record_pair(
    out_dir: Path,
    original_rom: Path,
    original_state: Path,
    remake_rom: Path,
    remake_state: Path,
    key: str = "None",
    hold_frames: int = 6,
    frame_count: int = 96,
    pre_input_frames: int = 0,
    mgba: Path = DEFAULT_MGBA,
) -> dict[str, object]:
    """Record both sides, then compare them frame by frame at the same index."""
    if out_dir.exists():
        raise CaptureError(f"pair directory already exists: {out_dir}")
    out_dir.mkdir(parents=True)
    for path in (original_rom, original_state, remake_rom, remake_state, mgba,
                 RECORD_SCRIPT, GUARD):
        if not Path(path).is_file():
            raise CaptureError(f"missing pinned input: {path}")

    inputs = {
        "schema": "konoha.s49-pair-inputs.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mgba": str(mgba),
        "mgba_sha256": sha256_file(Path(mgba)),
        "record_script": str(RECORD_SCRIPT),
        "record_script_sha256": sha256_file(RECORD_SCRIPT),
        "key": key,
        "hold_frames": hold_frames,
        "frame_count": frame_count,
        "pre_input_frames": pre_input_frames,
    }
    sides = {}
    for label, rom, state in (
        ("original", original_rom, original_state),
        ("remake", remake_rom, remake_state),
    ):
        sides[label] = record_side(
            label, out_dir / label, Path(rom), Path(state), Path(mgba),
            key, hold_frames, frame_count, pre_input_frames)
        inputs[f"{label}_rom_sha256"] = sides[label]["rom_sha256"]
        inputs[f"{label}_state_sha256"] = sides[label]["state_sha256"]
        inputs[f"{label}_save_sha256"] = sides[label]["save_sha256"]
    (out_dir / "inputs.json").write_text(
        json.dumps(inputs, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    comparison = compare_sequences(out_dir / "original", out_dir / "remake")
    report_path = out_dir / "comparison.json"
    report_path.write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "out_dir": str(out_dir),
        "inputs": inputs,
        "sides": sides,
        "comparison": {
            "status": comparison["status"],
            "compared_frames": comparison["compared_frames"],
            "different_frames": comparison["different_frames"],
            "different_pixels": comparison["different_pixels"],
            "report": str(report_path),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--original-rom", type=Path, required=True)
    parser.add_argument("--original-state", type=Path, required=True)
    parser.add_argument("--remake-rom", type=Path, required=True)
    parser.add_argument("--remake-state", type=Path, required=True)
    parser.add_argument("--key", default="None")
    parser.add_argument("--hold-frames", type=int, default=6)
    parser.add_argument("--frame-count", type=int, default=96)
    parser.add_argument("--pre-input-frames", type=int, default=0)
    parser.add_argument("--mgba", type=Path, default=DEFAULT_MGBA)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = record_pair(
            args.out_dir, args.original_rom, args.original_state,
            args.remake_rom, args.remake_state, args.key, args.hold_frames,
            args.frame_count, args.pre_input_frames, args.mgba)
    except (CaptureError, ValueError, OSError) as error:
        print(f"capture_s49_pair: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result["comparison"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
