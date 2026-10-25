#!/usr/bin/env python3
"""Capture cartridge-SRAM images (32 KiB) for the original and the remake.

The instrument is the headless mGBA probe: ``framedump 1 0x0E000000 32768``
reads the cartridge SRAM window through the bus and writes it to a binary
file.  One probe process can do many ``load`` + ``framedump`` pairs, so the
whole sweep of a walk's savestates costs a single emulator start-up.

Capture points
--------------
original
    * ``original-entry``      -- the battle 14 entry savestate
    * ``original-step-NN``    -- every step of the 41 step original walk
                                (40 x A from the battle 14 entry savestate)
remake
    * ``remake-step-NN``      -- every step of the remake boot walk, whose
                                key sequence selects "save" in the preparation
                                scene, starts the battle and then presses A

Nothing is deleted: every run overwrites the same file names, and the step
selection is by index so a stale file from a longer earlier walk is ignored.

Usage::

    python tools/s49_save_boundary/capture_sram.py --original
    python tools/s49_save_boundary/capture_sram.py --remake
    python tools/s49_save_boundary/capture_sram.py --all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_save_common import (  # noqa: E402
    BATTLE14_STATE,
    BATTLE14_STATE_SHA256,
    CHECKPOINT_DIR,
    ORIGINAL_CHECKPOINTS,
    ORIGINAL_ROM,
    ORIGINAL_ROM_SHA256,
    ORIGINAL_SCRIPTS,
    REMAKE_ROM,
    SRAM_BASE,
    SRAM_DIR,
    WORK,
    probe_exe,
    sha256_file,
    write_json,
)

PROBE_CLIENT = HERE.parents[0] / "mgba_probe" / "probe_client.py"

#: The original walk: 40 x A from the battle 14 entry savestate.
ORIGINAL_KEY_SEQUENCE = ",".join(["A"] * 40)
ORIGINAL_ZERO_INPUT_FRAMES = 90
ORIGINAL_SETTLE_FRAMES = 90
ORIGINAL_HOLD_FRAMES = 4

#: The remake walk.  The preparation scene's root menu is
#: ``[party_equipment, inspect_map, start_battle, save]`` and ``Down`` moves
#: one option down, so ``Down x3 + A`` picks "save" -- the only place where
#: the remake writes SRAM before the battle.  The walk saves twice (to watch
#: the two slots alternate and the generation counter advance), then picks
#: "start battle" (root option 2) and presses A inside the battle (to watch
#: the battle itself not touch SRAM).
REMAKE_KEY_SEQUENCE = ",".join(
    ["Down", "Down", "Down", "A"]
    + ["Down", "Down", "Down", "A"]
    + ["Down", "Down", "A", "A"]
    + ["A"] * 4
)
REMAKE_ZERO_INPUT_FRAMES = 600
REMAKE_SETTLE_FRAMES = 90
REMAKE_HOLD_FRAMES = 4


def _run_walk(rom: pathlib.Path, script: pathlib.Path, frames: int,
              out_dir: pathlib.Path, environment: dict[str, str]) -> dict:
    """Record one walk with the remake tree's own Lua probe script."""

    out_dir.mkdir(parents=True, exist_ok=True)
    done_marker = out_dir / "done.json"
    command = [
        sys.executable,
        str(PROBE_CLIENT),
        "--rom", str(rom),
        "--timeout", "900",
        "--cmd", "script %s" % script,
        "--cmd", "frames %d 0x000" % frames,
        "--out", str(out_dir / "result.json"),
    ]
    completed = subprocess.run(
        command, env={**os.environ, **environment},
        text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "walk failed with exit %d: %s"
            % (completed.returncode, completed.stderr.strip()[:600])
        )
    if not done_marker.is_file():
        raise RuntimeError("the walk never wrote %s" % done_marker)
    return json.loads(done_marker.read_text(encoding="utf-8"))


def _select_steps(walk_dir: pathlib.Path, keys: list[str]) -> list[pathlib.Path]:
    """The ``step-NN-<key>.ss9`` files of this walk, by exact name.

    The Lua script names the file of step ``N`` after the key of step ``N``,
    so the expected names are known exactly.  Selecting by exact name (not by
    glob) keeps a stale file from an earlier, differently-keyed walk out of
    the sweep.
    """

    selected: list[pathlib.Path] = []
    for index, key in enumerate(keys, start=1):
        state = walk_dir / ("step-%02d-%s.ss9" % (index, key))
        if not state.is_file():
            raise RuntimeError("the walk did not write %s" % state)
        selected.append(state)
    return selected


def _walk_dir(tag: str, keys: list[str]) -> pathlib.Path:
    """A per-sequence walk directory, so two key sequences never collide."""

    digest = hashlib.sha256(",".join(keys).encode("utf-8")).hexdigest()[:8]
    return WORK / ("%s-walk-%s" % (tag, digest))


def _sram_sweep(rom: pathlib.Path, checkpoints: list[tuple[str, pathlib.Path]],
                tag: str, sram_dir: pathlib.Path) -> dict:
    """Read SRAM at every checkpoint with a single probe process."""

    sram_dir.mkdir(parents=True, exist_ok=True)
    sweep_dir = WORK / "sweep" / tag
    sweep_dir.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    for name, state in checkpoints:
        commands.append("load %s" % state)
        commands.append("framedump 1 0x%08X 32768 0x000 %s"
                        % (SRAM_BASE, (sweep_dir / name).as_posix()))
    out_json = sweep_dir / "sweep.json"
    command = [
        sys.executable,
        str(PROBE_CLIENT),
        "--rom", str(rom),
        "--exe", str(probe_exe()),
        "--timeout", "1800",
    ]
    for item in commands:
        command += ["--cmd", item]
    command += ["--out", str(out_json)]
    completed = subprocess.run(
        command, text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "sram sweep failed with exit %d: %s"
            % (completed.returncode, completed.stderr.strip()[:600])
        )
    document = json.loads(out_json.read_text(encoding="utf-8"))
    errors = [
        step["output"][0]
        for step in document["steps"]
        if step["status"] != "ok"
    ]
    if errors:
        raise RuntimeError("sram sweep reported errors: %s" % errors[:4])

    images = {}
    for name, state in checkpoints:
        produced = sweep_dir / ("%s-0000.bin" % name)
        if not produced.is_file():
            raise RuntimeError("the sweep did not write %s" % produced)
        target = sram_dir / ("%s.sav" % name)
        shutil.copyfile(produced, target)
        images[name] = {
            "savestate": str(state),
            "savestate_sha256": sha256_file(state),
            "sram_path": str(target),
            "sram_sha256": sha256_file(target),
            "sram_size": target.stat().st_size,
        }
    return images


def capture_original() -> dict:
    """The original's SRAM at battle entry and across the whole battle walk."""

    if sha256_file(ORIGINAL_ROM) != ORIGINAL_ROM_SHA256:
        raise RuntimeError("the original ROM hash moved")
    if sha256_file(BATTLE14_STATE) != BATTLE14_STATE_SHA256:
        raise RuntimeError("the battle 14 savestate hash moved")

    walk_dir = _walk_dir("original", ORIGINAL_KEY_SEQUENCE.split(","))
    sram_dir = SRAM_DIR / walk_dir.name
    audit = _run_walk(
        ORIGINAL_ROM,
        ORIGINAL_SCRIPTS / "mgba_original_s49_ui_boundaries.lua",
        6000,
        walk_dir,
        {
            "MGBA_ORIGINAL_S49_INPUT_STATE": str(BATTLE14_STATE),
            "MGBA_ORIGINAL_S49_INPUT_STATE_SHA256": BATTLE14_STATE_SHA256,
            "MGBA_ORIGINAL_S49_OUTPUT_DIR": str(walk_dir),
            "MGBA_ORIGINAL_S49_DONE_MARKER": str(walk_dir / "done.json"),
            "MGBA_ORIGINAL_S49_KEY_SEQUENCE": ORIGINAL_KEY_SEQUENCE,
            "MGBA_ORIGINAL_S49_ZERO_INPUT_FRAMES": str(
                ORIGINAL_ZERO_INPUT_FRAMES),
            "MGBA_ORIGINAL_S49_SETTLE_FRAMES": str(ORIGINAL_SETTLE_FRAMES),
            "MGBA_ORIGINAL_S49_HOLD_FRAMES": str(ORIGINAL_HOLD_FRAMES),
        },
    )
    steps = _select_steps(walk_dir, ORIGINAL_KEY_SEQUENCE.split(","))
    checkpoints: list[tuple[str, pathlib.Path]] = []
    for name, filename, expected in ORIGINAL_CHECKPOINTS:
        state = CHECKPOINT_DIR / filename
        if not state.is_file():
            raise RuntimeError("missing original checkpoint %s" % state)
        actual = sha256_file(state)
        if actual != expected:
            raise RuntimeError(
                "original checkpoint %s hashes to %s, expected %s"
                % (filename, actual, expected)
            )
        checkpoints.append((name, state))
    for state in steps:
        checkpoints.append(("original-" + state.stem, state))
    images = _sram_sweep(ORIGINAL_ROM, checkpoints, "original", sram_dir)
    return {
        "rom": str(ORIGINAL_ROM),
        "rom_sha256": ORIGINAL_ROM_SHA256,
        "walk_dir": str(walk_dir),
        "walk_audit": audit,
        "step_count": len(steps),
        "checkpoint_count": len(checkpoints),
        "images": images,
    }


def capture_remake() -> dict:
    """The remake's SRAM across boot, the preparation-scene save and battle."""

    rom_sha = sha256_file(REMAKE_ROM)
    walk_dir = _walk_dir("remake", REMAKE_KEY_SEQUENCE.split(","))
    sram_dir = SRAM_DIR / walk_dir.name
    audit = _run_walk(
        REMAKE_ROM,
        ORIGINAL_SCRIPTS / "mgba_boot_input_sequence.lua",
        5000,
        walk_dir,
        {
            "MGBA_BOOT_SEQUENCE_OUTPUT_DIR": str(walk_dir),
            "MGBA_BOOT_SEQUENCE_DONE_MARKER": str(walk_dir / "done.json"),
            "MGBA_BOOT_SEQUENCE_ROM_SHA256": rom_sha,
            "MGBA_BOOT_SEQUENCE_KEY_SEQUENCE": REMAKE_KEY_SEQUENCE,
            "MGBA_BOOT_SEQUENCE_ZERO_INPUT_FRAMES": str(
                REMAKE_ZERO_INPUT_FRAMES),
            "MGBA_BOOT_SEQUENCE_SETTLE_FRAMES": str(REMAKE_SETTLE_FRAMES),
            "MGBA_BOOT_SEQUENCE_HOLD_FRAMES": str(REMAKE_HOLD_FRAMES),
        },
    )
    steps = _select_steps(walk_dir, REMAKE_KEY_SEQUENCE.split(","))
    checkpoints = [("remake-" + state.stem, state) for state in steps]
    images = _sram_sweep(REMAKE_ROM, checkpoints, "remake", sram_dir)
    return {
        "rom": str(REMAKE_ROM),
        "rom_sha256": rom_sha,
        "walk_dir": str(walk_dir),
        "walk_audit": audit,
        "key_sequence": REMAKE_KEY_SEQUENCE,
        "step_count": len(steps),
        "checkpoint_count": len(checkpoints),
        "images": images,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", action="store_true")
    parser.add_argument("--remake", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    do_original = args.original or args.all
    do_remake = args.remake or args.all
    if not (do_original or do_remake):
        parser.error("nothing to do: pass --original / --remake / --all")

    receipts = {}
    receipt_path = WORK / "receipts" / "capture_sram.json"
    if receipt_path.is_file():
        receipts = json.loads(receipt_path.read_text(encoding="utf-8"))
    if do_original:
        receipts["original"] = capture_original()
        print("original: %d SRAM checkpoints"
              % receipts["original"]["checkpoint_count"])
    if do_remake:
        receipts["remake"] = capture_remake()
        print("remake: %d SRAM checkpoints"
              % receipts["remake"]["checkpoint_count"])
    write_json(receipt_path, receipts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
