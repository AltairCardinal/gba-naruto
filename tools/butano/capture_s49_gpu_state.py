#!/usr/bin/env python3
"""Dump the GBA's palette RAM, VRAM, OAM and I/O registers from one savestate.

Every question in this project of the form "which palette bank produced this
colour" needs palette RAM, and the recorded S49 walks only kept rendered PNGs.
A rendered frame is the *result* of a palette, not the palette: when the
original draws an inactive unit in grey and the remake draws it in colour, the
only way to tell "the ROM writes a modified bank at runtime" from "the ROM owns
a second, greyscale tile set" is to read PRAM itself.

The earlier GPU dumps that answered such questions lived under `artifacts/` and
were removed by a host cleanup, so the probe is rebuilt here as a first-class,
reproducible tool rather than an ad-hoc script:

* the savestate, ROM, mGBA binary and Lua script are all hashed into
  `inputs.json` before the run, so a claim can be re-checked against the exact
  inputs that produced it;
* the run fails closed when mGBA exits non-zero, when the done marker is absent,
  or when any dumped file is missing or the wrong size;
* `palette_entries()` turns the PRAM blob into the GBA's 256 banks of 16 BGR555
  entries, which is the form every consumer in this repo already reads.
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
SCRIPT = ROOT / "tools/butano/mgba_gpu_state_dump.lua"

PRAM_BYTES = 1024
VRAM_BYTES = 96 * 1024
OAM_BYTES = 1024
IO_BYTES = 1024

EXPECTED_SIZES = {
    "pram.bin": PRAM_BYTES,
    "vram.bin": VRAM_BYTES,
    "oam.bin": OAM_BYTES,
    "io.bin": IO_BYTES,
}


class GpuStateError(RuntimeError):
    """The probe did not produce a complete, self-consistent dump."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gba555(value: int) -> tuple[int, int, int]:
    """Convert one BGR555 entry to 8-bit RGB, matching the repo's other readers."""

    red = value & 0x1F
    green = (value >> 5) & 0x1F
    blue = (value >> 10) & 0x1F
    return (
        (red << 3) | (red >> 2),
        (green << 3) | (green >> 2),
        (blue << 3) | (blue >> 2),
    )


def palette_entries(pram: bytes) -> list[list[tuple[int, int, int]]]:
    """Return PRAM as 256 palette banks of 16 RGB triples.

    PRAM is 1 KiB: the first 0x200 bytes are background palette RAM and the rest
    is OBJ palette RAM, each 32 bytes per bank.
    """

    if len(pram) != PRAM_BYTES:
        raise GpuStateError(f"pram.bin is {len(pram)} bytes, expected {PRAM_BYTES}")
    banks = []
    for offset in range(0, len(pram), 32):
        words = [
            int.from_bytes(pram[offset + 2 * i:offset + 2 * i + 2], "little")
            for i in range(16)
        ]
        banks.append([_gba555(word) for word in words])
    return banks


def _resolve_inputs(state: Path, rom: Path, mgba: Path) -> dict[str, object]:
    for path, label in ((state, "savestate"), (rom, "ROM"), (mgba, "mGBA")):
        if not Path(path).is_file():
            raise GpuStateError(f"missing {label}: {path}")
    if not SCRIPT.is_file():
        raise GpuStateError(f"missing probe script: {SCRIPT}")
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema": "konoha.mgba-gpu-state-inputs.v1",
        "input_state": str(state),
        "input_state_sha256": sha256_file(state),
        "rom": str(rom),
        "rom_sha256": sha256_file(rom),
        "mgba": str(mgba),
        "mgba_sha256": sha256_file(mgba),
        "script": str(SCRIPT),
        "script_sha256": sha256_file(SCRIPT),
        "guard": str(ROOT / "tools/run_guarded.py"),
        "guard_sha256": sha256_file(ROOT / "tools/run_guarded.py"),
        "expected_sizes": EXPECTED_SIZES,
    }


def _verify(out_dir: Path) -> dict[str, object]:
    for name, size in EXPECTED_SIZES.items():
        path = out_dir / name
        if not path.is_file():
            raise GpuStateError(f"probe did not write {name}")
        actual = path.stat().st_size
        if actual != size:
            raise GpuStateError(f"{name} is {actual} bytes, expected {size}")
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.is_file():
        raise GpuStateError("probe did not write manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    banks_path = out_dir / "oam-palette-banks.json"
    if not banks_path.is_file():
        raise GpuStateError("probe did not write oam-palette-banks.json")
    pram = (out_dir / "pram.bin").read_bytes()
    return {
        "out_dir": str(out_dir),
        "captured_frame": manifest["captured_frame"],
        "manifest": manifest,
        "oam_palette_banks": json.loads(banks_path.read_text(encoding="utf-8")),
        "pram_sha256": hashlib.sha256(pram).hexdigest(),
        "palette_banks": 32,
    }


def run(
    state: Path,
    rom: Path,
    out_dir: Path,
    settle_frames: int,
    mgba: Path = DEFAULT_MGBA,
    run_probe: bool = True,
) -> dict[str, object]:
    inputs = _resolve_inputs(Path(state), Path(rom), Path(mgba))
    if not run_probe:
        return {"inputs": inputs}

    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise GpuStateError(
            f"{out_dir} is not empty; each run needs its own directory so a "
            f"stale dump can never be read as a fresh one"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "inputs.json").write_text(
        json.dumps(inputs, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    done_marker = out_dir / "done.json"
    environment = {
        "MGBA_GPU_STATE_INPUT_STATE": str(Path(state).resolve()),
        "MGBA_GPU_STATE_OUTPUT_DIR": str(out_dir.resolve()),
        "MGBA_GPU_STATE_DONE_MARKER": str(done_marker.resolve()),
        "MGBA_GPU_STATE_SETTLE_FRAMES": str(settle_frames),
        "MGBA_GPU_STATE_DUMP": ",".join(sorted(EXPECTED_SIZES)),
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
        raise GpuStateError(
            f"guarded probe failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:400]}"
        )
    if not done_marker.is_file():
        raise GpuStateError("probe never wrote its done marker")
    return {"inputs": inputs, **_verify(out_dir)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--settle-frames", type=int, default=2)
    parser.add_argument("--mgba", type=Path, default=DEFAULT_MGBA)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve and print the input contract without running mGBA",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(
            args.state,
            args.rom,
            args.out_dir,
            args.settle_frames,
            args.mgba,
            run_probe=not args.dry_run,
        )
    except GpuStateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    printable = {
        key: value
        for key, value in result.items()
        if key not in ("manifest", "oam_palette_banks")
    }
    print(json.dumps(printable, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
