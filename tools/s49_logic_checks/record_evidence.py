#!/usr/bin/env python3
"""Record the local evidence the S49 logic checks need.

Four recordings, all with the headless mGBA probe
(``build/mgba-probe/mgba-probe.exe``) and the remake tree's own Lua probe
scripts, so the capture semantics are the ones the project already trusts:

======================  =============================================  ========
recording               script                                        frames
======================  =============================================  ========
``original-walk``       ``mgba_original_s49_ui_boundaries.lua``      25 steps
``remake-walk``         ``mgba_boot_input_sequence.lua``              35 steps
``original-idle-sweep`` ``mgba_original_input_frame_sequence.lua``    200 frames
``roster-pool``         ``mgba_battle_roster_dump.lua``               1 dump
======================  =============================================  ========

The recipes are the macOS ones, read out of the surviving receipts
(``walk-original-a24/inputs.json`` and friends):

* the original walk starts from the battle 14 entry savestate, waits 90
  frames, then presses ``A`` 24 times (4 frames held, 90 frames settled),
* the remake walk starts from power-on with ``Down,Down,A x 32``,
* the idle sweep is 1800 frames of zero input from the battle 14 entry
  savestate (only the first 192 are needed by the check; 200 are recorded),
* the roster dump reads the original's EWRAM unit pool at the same
  savestate.

Usage::

    python tools/s49_logic_checks/record_evidence.py            # everything
    python tools/s49_logic_checks/record_evidence.py --only original-walk
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_logic_common import (  # noqa: E402
    BATTLE14_STATE,
    BATTLE14_STATE_SHA256,
    EVIDENCE_ROOT,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    FIELD_FRAME,
    IDLE_SWEEP,
    LONG_WALK,
    ORIGINAL_ROM,
    ORIGINAL_ROM_SHA256,
    ORIGINAL_WALK,
    PALETTE_PROBE,
    RECEIPTS,
    REMAKE_ROOT,
    REMAKE_WALK,
    ROSTER_POOL,
    STEP23_FRAMES,
    sha256_file,
)

PROBE = Path(__file__).resolve().parents[2] / "build" / "mgba-probe" / "mgba-probe.exe"
PROBE_CLIENT = (
    Path(__file__).resolve().parents[1] / "mgba_probe" / "probe_client.py"
)
REAL_BIOS = Path(__file__).resolve().parents[2] / "recomp" / "bios" / "gba_bios.bin"

SCRIPTS = REMAKE_ROOT / "tools" / "butano"

#: The remake ROM this stream measures.
REMAKE_ROM = REMAKE_ROOT / "butano-sequel" / "butano-sequel.gba"

ORIGINAL_KEY_SEQUENCE = ",".join(["A"] * 24)
#: The remake needs more presses than the macOS walk used: the local mGBA
#: build boots later (the real BIOS shows the boot animation), and the
#: enemy's turn -- the frames that carry the red 結束 -- comes after the
#: player's whole action.
REMAKE_KEY_SEQUENCE = ",".join(["Down", "Down"] + ["A"] * 60)


class RecordError(RuntimeError):
    """A recording did not complete."""


def _run_probe(
    rom: Path,
    script: Path,
    frames: int,
    out_dir: Path,
    environment: dict[str, str],
    bios: Path | None = None,
) -> dict:
    """Run one probe recording and return the probe's JSON document."""

    out_dir.mkdir(parents=True, exist_ok=True)
    done_marker = out_dir / "done.json"
    command = [
        sys.executable,
        str(PROBE_CLIENT),
        "--rom", str(rom),
    ]
    if bios is not None:
        command += ["--bios", str(bios)]
    command += [
        "--timeout", "900",
        "--cmd", f"script {script}",
        "--cmd", f"frames {frames} 0x000",
        "--out", str(out_dir / "result.json"),
    ]
    child_environment = {**os.environ, **environment}
    completed = subprocess.run(
        command,
        env=child_environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RecordError(
            f"probe failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()[:600]}"
        )
    if not done_marker.is_file():
        raise RecordError(f"the probe never wrote {done_marker}")
    return json.loads((out_dir / "result.json").read_text(encoding="utf-8"))


def _require_hash(path: Path, expected: str, label: str) -> None:
    if not Path(path).is_file():
        raise RecordError(f"missing {label}: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise RecordError(
            f"{label} hashes to {actual}, expected {expected}: {path}"
        )


def record_original_walk() -> dict:
    """The original's 25 step walk from the battle 14 entry savestate."""

    _require_hash(BATTLE14_STATE, BATTLE14_STATE_SHA256, "the battle 14 savestate")
    _require_hash(ORIGINAL_ROM, ORIGINAL_ROM_SHA256, "the original ROM")
    if ORIGINAL_WALK.exists():
        shutil.rmtree(ORIGINAL_WALK)
    environment = {
        "MGBA_ORIGINAL_S49_INPUT_STATE": str(BATTLE14_STATE),
        "MGBA_ORIGINAL_S49_INPUT_STATE_SHA256": BATTLE14_STATE_SHA256,
        "MGBA_ORIGINAL_S49_OUTPUT_DIR": str(ORIGINAL_WALK),
        "MGBA_ORIGINAL_S49_DONE_MARKER": str(ORIGINAL_WALK / "done.json"),
        "MGBA_ORIGINAL_S49_KEY_SEQUENCE": ORIGINAL_KEY_SEQUENCE,
        "MGBA_ORIGINAL_S49_ZERO_INPUT_FRAMES": "90",
        "MGBA_ORIGINAL_S49_SETTLE_FRAMES": "90",
        "MGBA_ORIGINAL_S49_HOLD_FRAMES": "4",
    }
    _run_probe(
        ORIGINAL_ROM,
        SCRIPTS / "mgba_original_s49_ui_boundaries.lua",
        4000,
        ORIGINAL_WALK,
        environment,
    )
    frames = sorted(ORIGINAL_WALK.glob("step-*.png"))
    if len(frames) != 25:
        raise RecordError(
            f"the original walk recorded {len(frames)} frames, expected 25"
        )
    return {"recording": "original-walk", "frames": len(frames)}


def record_remake_walk() -> dict:
    """The remake's 35 step walk from power-on."""

    if REMAKE_WALK.exists():
        shutil.rmtree(REMAKE_WALK)
    environment = {
        "MGBA_BOOT_SEQUENCE_OUTPUT_DIR": str(REMAKE_WALK),
        "MGBA_BOOT_SEQUENCE_DONE_MARKER": str(REMAKE_WALK / "done.json"),
        "MGBA_BOOT_SEQUENCE_ROM_SHA256": sha256_file(REMAKE_ROM),
        "MGBA_BOOT_SEQUENCE_KEY_SEQUENCE": REMAKE_KEY_SEQUENCE,
        "MGBA_BOOT_SEQUENCE_ZERO_INPUT_FRAMES": "900",
        "MGBA_BOOT_SEQUENCE_SETTLE_FRAMES": "90",
        "MGBA_BOOT_SEQUENCE_HOLD_FRAMES": "4",
    }
    _run_probe(
        REMAKE_ROM,
        SCRIPTS / "mgba_boot_input_sequence.lua",
        5000,
        REMAKE_WALK,
        environment,
        bios=REAL_BIOS if REAL_BIOS.is_file() else None,
    )
    frames = sorted(REMAKE_WALK.glob("step-*.png"))
    if len(frames) != 63:
        raise RecordError(
            f"the remake walk recorded {len(frames)} frames, expected 63"
        )
    return {
        "recording": "remake-walk",
        "frames": len(frames),
        "rom_sha256": sha256_file(REMAKE_ROM),
        "real_bios": REAL_BIOS.is_file(),
    }


def record_idle_sweep() -> dict:
    """The original's zero input sweep, for the idle cadence measurement."""

    _require_hash(BATTLE14_STATE, BATTLE14_STATE_SHA256, "the battle 14 savestate")
    if IDLE_SWEEP.exists():
        shutil.rmtree(IDLE_SWEEP)
    environment = {
        "MGBA_ORIGINAL_INPUT_SEQUENCE_INPUT_STATE": str(BATTLE14_STATE),
        "MGBA_ORIGINAL_INPUT_SEQUENCE_INPUT_STATE_SHA256": BATTLE14_STATE_SHA256,
        "MGBA_ORIGINAL_INPUT_SEQUENCE_OUTPUT_DIR": str(IDLE_SWEEP),
        "MGBA_ORIGINAL_INPUT_SEQUENCE_DONE_MARKER": str(IDLE_SWEEP / "done.json"),
        "MGBA_ORIGINAL_INPUT_SEQUENCE_KEY": "None",
        "MGBA_ORIGINAL_INPUT_SEQUENCE_HOLD_FRAMES": "6",
        "MGBA_ORIGINAL_INPUT_SEQUENCE_FRAME_COUNT": "200",
        "MGBA_ORIGINAL_INPUT_SEQUENCE_RECORD_ALL": "1",
    }
    _run_probe(
        ORIGINAL_ROM,
        SCRIPTS / "mgba_original_input_frame_sequence.lua",
        400,
        IDLE_SWEEP,
        environment,
    )
    frames = sorted(IDLE_SWEEP.glob("frame-*.png"))
    if len(frames) < 192:
        raise RecordError(
            f"the idle sweep recorded {len(frames)} frames, 192 are needed"
        )
    return {"recording": "original-idle-sweep", "frames": len(frames)}


def record_roster_pool() -> dict:
    """The original's EWRAM battle unit pool at the battle 14 savestate."""

    _require_hash(BATTLE14_STATE, BATTLE14_STATE_SHA256, "the battle 14 savestate")
    if ROSTER_POOL.exists():
        shutil.rmtree(ROSTER_POOL)
    environment = {
        "MGBA_ROSTER_INPUT_STATE": str(BATTLE14_STATE),
        "MGBA_ROSTER_OUTPUT_DIR": str(ROSTER_POOL),
        "MGBA_ROSTER_DONE_MARKER": str(ROSTER_POOL / "done.json"),
        "MGBA_ROSTER_SETTLE_FRAMES": "2",
    }
    _run_probe(
        ORIGINAL_ROM,
        SCRIPTS / "mgba_battle_roster_dump.lua",
        120,
        ROSTER_POOL,
        environment,
    )
    pool = ROSTER_POOL / "unit_pool.bin"
    if not pool.is_file():
        raise RecordError(f"the probe did not write {pool}")
    if pool.stat().st_size != 0x1D4 * 13:
        raise RecordError(
            f"the dumped pool is {pool.stat().st_size} bytes, expected "
            f"{0x1D4 * 13}"
        )
    return {
        "recording": "roster-pool",
        "bytes": pool.stat().st_size,
        "sha256": sha256_file(pool),
    }


def record_field_frame() -> dict:
    """The original's frame + palette sequence, used as the pixel oracle.

    The macOS capture ``artifacts/s49-original-field-frame-v1/`` took six
    frames (plus a palette / video / sprite / IO dump each) from the savestate
    of the original walk's step 17.  It is the only surviving artifact that
    holds **original pixels and raw memory** side by side, so it is the
    oracle that decides whether a local recording is the same recording.
    """

    state = ORIGINAL_WALK / "step-17-A.ss9"
    if not state.is_file():
        raise RecordError(
            f"missing the original walk step 17 savestate: {state}; record "
            "the original walk first"
        )
    if FIELD_FRAME.exists():
        shutil.rmtree(FIELD_FRAME)
    environment = {
        "MGBA_FRAME_INPUT_STATE": str(state),
        "MGBA_FRAME_OUTPUT_DIR": str(FIELD_FRAME),
        "MGBA_FRAME_DONE_MARKER": str(FIELD_FRAME / "done.json"),
        "MGBA_FRAME_SETTLE_FRAMES": "2",
        "MGBA_FRAME_COUNT": "6",
    }
    _run_probe(
        ORIGINAL_ROM,
        SCRIPTS / "mgba_frame_palette_sequence.lua",
        300,
        FIELD_FRAME,
        environment,
    )
    frames = sorted(FIELD_FRAME.glob("frame-*.png"))
    if len(frames) != 6:
        raise RecordError(
            f"the field frame capture wrote {len(frames)} frames, expected 6"
        )
    return {"recording": "field-frame", "frames": len(frames)}


def record_long_walk() -> dict:
    """A longer traversal of the original battle, 40 A presses.

    The macOS walk pressed ``A`` 24 times and reached the move range screen
    at its step 19.  On this machine the same 24 presses stop one screen
    earlier (the command menu), because the local mGBA build and the macOS
    one walk the UI at a slightly different pace.  The move range screen --
    the screen the move-grid rule lives on -- is therefore only reachable
    with more presses, so this recording walks 40 of them.
    """

    _require_hash(BATTLE14_STATE, BATTLE14_STATE_SHA256, "the battle 14 savestate")
    if LONG_WALK.exists():
        shutil.rmtree(LONG_WALK)
    environment = {
        "MGBA_ORIGINAL_S49_INPUT_STATE": str(BATTLE14_STATE),
        "MGBA_ORIGINAL_S49_INPUT_STATE_SHA256": BATTLE14_STATE_SHA256,
        "MGBA_ORIGINAL_S49_OUTPUT_DIR": str(LONG_WALK),
        "MGBA_ORIGINAL_S49_DONE_MARKER": str(LONG_WALK / "done.json"),
        "MGBA_ORIGINAL_S49_KEY_SEQUENCE": ",".join(["A"] * 40),
        "MGBA_ORIGINAL_S49_ZERO_INPUT_FRAMES": "90",
        "MGBA_ORIGINAL_S49_SETTLE_FRAMES": "90",
        "MGBA_ORIGINAL_S49_HOLD_FRAMES": "4",
    }
    _run_probe(
        ORIGINAL_ROM,
        SCRIPTS / "mgba_original_s49_ui_boundaries.lua",
        6000,
        LONG_WALK,
        environment,
    )
    frames = sorted(LONG_WALK.glob("step-*.png"))
    if len(frames) != 41:
        raise RecordError(
            f"the long walk recorded {len(frames)} frames, expected 41"
        )
    return {"recording": "original-walk-long", "frames": len(frames)}


def record_step23_frames() -> dict:
    """The unit selection screen's animation phases, taken from step 23.

    The macOS oracle ``artifacts/s49-original-field-frame-v1/`` holds six
    consecutive frames of the original's unit selection screen together with
    their palette / video / sprite / IO dumps.  The local walk reaches that
    screen at its step 23, so the same six-frame capture is taken from the
    local step 23 savestate with the very same script.
    """

    state = LONG_WALK / "step-23-A.ss9"
    if not state.is_file():
        raise RecordError(
            f"missing the long walk step 23 savestate: {state}; record the "
            "long walk first"
        )
    if STEP23_FRAMES.exists():
        shutil.rmtree(STEP23_FRAMES)
    environment = {
        "MGBA_FRAME_INPUT_STATE": str(state),
        "MGBA_FRAME_OUTPUT_DIR": str(STEP23_FRAMES),
        "MGBA_FRAME_DONE_MARKER": str(STEP23_FRAMES / "done.json"),
        "MGBA_FRAME_SETTLE_FRAMES": "2",
        "MGBA_FRAME_COUNT": "32",
    }
    _run_probe(
        ORIGINAL_ROM,
        SCRIPTS / "mgba_frame_palette_sequence.lua",
        400,
        STEP23_FRAMES,
        environment,
    )
    frames = sorted(STEP23_FRAMES.glob("frame-*.png"))
    if len(frames) != 32:
        raise RecordError(
            f"the step 23 capture wrote {len(frames)} frames, expected 32"
        )
    return {"recording": "field-frame-step23", "frames": len(frames)}


def record_palette_probe() -> dict:
    """Twelve frames of the original with their palette RAM dumps.

    The idle cadence needs a yardstick: how often does the game rewrite the
    palette in one emulated frame?  The palette dump answers that without
    any rendering in the way.
    """

    _require_hash(BATTLE14_STATE, BATTLE14_STATE_SHA256, "the battle 14 savestate")
    if PALETTE_PROBE.exists():
        shutil.rmtree(PALETTE_PROBE)
    environment = {
        "MGBA_FRAME_INPUT_STATE": str(BATTLE14_STATE),
        "MGBA_FRAME_OUTPUT_DIR": str(PALETTE_PROBE),
        "MGBA_FRAME_DONE_MARKER": str(PALETTE_PROBE / "done.json"),
        "MGBA_FRAME_SETTLE_FRAMES": "2",
        "MGBA_FRAME_COUNT": "12",
    }
    _run_probe(
        ORIGINAL_ROM,
        SCRIPTS / "mgba_frame_palette_sequence.lua",
        200,
        PALETTE_PROBE,
        environment,
    )
    frames = sorted(PALETTE_PROBE.glob("frame-*.png"))
    if len(frames) != 12:
        raise RecordError(
            f"the palette probe wrote {len(frames)} frames, expected 12"
        )
    return {"recording": "palette-probe", "frames": len(frames)}


RECORDINGS = {
    "original-walk": record_original_walk,
    "remake-walk": record_remake_walk,
    "original-idle-sweep": record_idle_sweep,
    "roster-pool": record_roster_pool,
    "field-frame": record_field_frame,
    "original-walk-long": record_long_walk,
    "field-frame-step23": record_step23_frames,
    "palette-probe": record_palette_probe,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only", action="append", choices=sorted(RECORDINGS), default=None,
        help="record only this recording (may be repeated)",
    )
    args = parser.parse_args(argv)

    for required in (PROBE, PROBE_CLIENT):
        if not Path(required).is_file():
            print(f"error: missing {required}", file=sys.stderr)
            return EXIT_INPUT_ERROR

    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    RECEIPTS.mkdir(parents=True, exist_ok=True)

    selected = args.only or list(RECORDINGS)
    results = []
    for name in selected:
        try:
            results.append(RECORDINGS[name]())
        except RecordError as error:
            print(f"error: {name}: {error}", file=sys.stderr)
            return EXIT_INPUT_ERROR
        print(f"recorded {name}: {results[-1]}")
    (RECEIPTS / "record_evidence.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
