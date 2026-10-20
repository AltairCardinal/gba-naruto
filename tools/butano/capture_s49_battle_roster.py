#!/usr/bin/env python3
"""Dump the original game's battle unit pool from one savestate.

The S49 remake claims to copy the original battle (original battle id 14) unit
for unit: the same nine slots, the same characters, the same grid coordinates,
the same levels and the same HP.  The only original-side evidence so far was a
rendered PNG or a prose note, and neither can be compared field by field
against the remake's data tables.

The original keeps its live units in one contiguous pool:

======================  ==========================================
pool base               ``0x020240C0``
record stride           ``0x1D4``, 13 records (slot 0..12)
record ``+0x00``        character id (``0`` marks an empty slot)
record ``+0x0C``        current HP
record ``+0x0E``        max HP
record ``+0xC4``        grid X
record ``+0xC5``        grid Y
======================  ==========================================

This tool only *captures* the raw pool.  Interpreting it is the job of
``tools/butano/verify_s49_battle_roster.py``, which is written independently
and cross-checks the capture against a second original-side source (the
reverse tree's signed unit bindings) and against the remake's own tables.

The probe is fail-closed:

* every input (savestate, ROM, mGBA binary, Lua script, guard) is hashed into
  ``inputs.json`` before the run;
* the run goes through ``tools/run_guarded.py`` like every other mGBA run in
  this repository;
* a missing, short or oversized dump is an error, never a partial success.

Usage::

    python3 tools/butano/capture_s49_battle_roster.py \
        --state artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9 \
        --rom rom/base.gba \
        --out-dir artifacts/s49-original-battle14-roster-v1
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
SCRIPT = ROOT / "tools/butano/mgba_battle_roster_dump.lua"

POOL_BASE = 0x020240C0
POOL_RECORD_SIZE = 0x1D4
POOL_RECORD_COUNT = 13
POOL_SIZE = POOL_RECORD_SIZE * POOL_RECORD_COUNT

EXPECTED_SIZES = {"unit_pool.bin": POOL_SIZE}


class RosterCaptureError(RuntimeError):
    """The probe did not produce a complete, self-consistent dump."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_inputs(state: Path, rom: Path, mgba: Path) -> dict[str, object]:
    for path, label in ((state, "savestate"), (rom, "ROM"), (mgba, "mGBA")):
        if not Path(path).is_file():
            raise RosterCaptureError(f"missing {label}: {path}")
    if not SCRIPT.is_file():
        raise RosterCaptureError(f"missing probe script: {SCRIPT}")
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema": "konoha.mgba-battle-roster-inputs.v1",
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
        "pool_base_hex": f"0x{POOL_BASE:08X}",
        "pool_record_size": POOL_RECORD_SIZE,
        "pool_record_count": POOL_RECORD_COUNT,
        "expected_sizes": EXPECTED_SIZES,
    }


def verify(out_dir: Path) -> dict[str, object]:
    for name, size in EXPECTED_SIZES.items():
        path = out_dir / name
        if not path.is_file():
            raise RosterCaptureError(f"probe did not write {name}")
        actual = path.stat().st_size
        if actual != size:
            raise RosterCaptureError(f"{name} is {actual} bytes, expected {size}")
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RosterCaptureError("probe did not write manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pool = (out_dir / "unit_pool.bin").read_bytes()
    pool_hash = hashlib.sha256(pool).hexdigest()
    (out_dir / "capture.json").write_text(
        json.dumps(
            {
                "schema": "konoha.mgba-battle-roster-capture.v1",
                "unit_pool_sha256": pool_hash,
                "unit_pool_size": len(pool),
                "pool_base_hex": f"0x{POOL_BASE:08X}",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "out_dir": str(out_dir),
        "captured_frame": manifest["captured_frame"],
        "manifest": manifest,
        "unit_pool_sha256": pool_hash,
        "unit_pool_size": len(pool),
    }


def run(
    state: Path,
    rom: Path,
    out_dir: Path,
    settle_frames: int,
    mgba: Path = DEFAULT_MGBA,
    run_probe: bool = True,
) -> dict[str, object]:
    inputs = resolve_inputs(Path(state), Path(rom), Path(mgba))
    if not run_probe:
        return {"inputs": inputs}

    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise RosterCaptureError(
            f"{out_dir} is not empty; each run needs its own directory so a "
            f"stale dump can never be read as a fresh one"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "inputs.json").write_text(
        json.dumps(inputs, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    done_marker = out_dir / "done.json"
    environment = {
        "MGBA_ROSTER_INPUT_STATE": str(Path(state).resolve()),
        "MGBA_ROSTER_OUTPUT_DIR": str(out_dir.resolve()),
        "MGBA_ROSTER_DONE_MARKER": str(done_marker.resolve()),
        "MGBA_ROSTER_SETTLE_FRAMES": str(settle_frames),
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
        raise RosterCaptureError(
            f"guarded probe failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:400]}"
        )
    if not done_marker.is_file():
        raise RosterCaptureError("probe never wrote its done marker")
    return {"inputs": inputs, **verify(out_dir)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--settle-frames", type=int, default=2)
    parser.add_argument("--mgba", type=Path, default=DEFAULT_MGBA)
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="only resolve and print the input hashes",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(
            state=args.state,
            rom=args.rom,
            out_dir=args.out_dir,
            settle_frames=args.settle_frames,
            mgba=args.mgba,
            run_probe=not args.no_probe,
        )
    except RosterCaptureError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
