#!/usr/bin/env python3
"""One-command capture of the original S49 battle 14, up to the result screen.

The command replays the battle from the battle-14 entry savestate with the
probe and writes

* ``frames/``       -- one PNG per key press (the frame sequence)
* ``ewram/``        -- the battle state block after every frame
* ``vram/``         -- the whole VRAM after every frame of the endgame
* ``capture.json``  -- the receipt: the route, the frame index, the hashes

The VRAM and the I/O registers are never read in the same run: reading VCOUNT
perturbs the emulation, so the VRAM gets its own run.

Usage::

    python tools/s49_victory_capture/capture_victory.py --out build/s49-victory-capture/capture
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import battle as battle_module  # noqa: E402
import play_battle  # noqa: E402
import probe as probe_module  # noqa: E402
import s49_state  # noqa: E402

_BUILD = pathlib.Path(__file__).resolve().parents[2] / "build"
# A private copy of the probe avoids the LNK1104 clash with the other streams.
DEFAULT_EXE = (_BUILD / "mgba-probe-k" / "mgba-probe.exe")
if not DEFAULT_EXE.exists():
    DEFAULT_EXE = _BUILD / "mgba-probe" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")

VRAM_BASE = 0x06000000
VRAM_LENGTH = 0x18000
EWRAM_BASE = s49_state.POOL_ADDRESS - 0xC0      # the unit pool block
EWRAM_LENGTH = 0x1300


def run_pass(rom: str, state: str, exe: str, out_dir: pathlib.Path,
             dump_kind: str, max_turns: int) -> dict:
    """Play the battle once and capture the frames / dumps."""
    frames_dir = out_dir / "frames"
    dump_dir = out_dir / dump_kind
    log: list = []
    with probe_module.Probe(rom, exe=exe) as probe:
        probe.load(state)
        battle = battle_module.Battle(probe, settle=45, shot_dir=frames_dir,
                                      screen_path=out_dir / "screen.png",
                                      log=log)
        battle.capture_each = True          # one PNG per key press
        if dump_kind == "ewram":
            battle.enable_dump(EWRAM_BASE, EWRAM_LENGTH, dump_dir)
        else:
            # The VRAM pass only covers the endgame: one 96 KiB frame is a
            # lot of disk, and the settlement screen is what matters.
            battle.dump_address = VRAM_BASE
            battle.dump_length = VRAM_LENGTH
            battle.dump_dir = dump_dir
            battle.dump_predicate = lambda: len(battle.alive_bees()) <= 1
        stats = play_battle.play(battle, max_turns=max_turns)
        final_hp = battle.hp()
        final_units = battle.pool()
        segments = list(battle.dump_segments)
    return {
        "stats": stats,
        "final_hp": final_hp,
        "final_units": final_units,
        "log": log,
        "dump_segments": segments,
    }


def manifest(directory: pathlib.Path) -> list[dict]:
    rows = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            rows.append({
                "path": str(path.relative_to(directory)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": s49_state.file_sha256(path),
            })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--skip-vram", action="store_true",
                        help="do not run the second (VRAM) pass")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    ewram = run_pass(args.rom, args.state, args.exe, out_dir, "ewram",
                     args.max_turns)
    vram = None
    if not args.skip_vram:
        vram = run_pass(args.rom, args.state, args.exe, out_dir, "vram",
                        args.max_turns)

    # The receipt carries no wall-clock fields on purpose: two consecutive
    # runs must be byte identical, so the runtime is reported separately.
    receipt = {
        "schema": "konoha.s49-victory-capture.v1",
        "rom": args.rom,
        "rom_sha256": s49_state.file_sha256(args.rom),
        "start_state": args.state,
        "start_state_sha256": s49_state.file_sha256(args.state),
        "ewram_pass": ewram,
        "vram_pass": vram,
        "manifest": manifest(out_dir),
    }
    (out_dir / "capture.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    (out_dir / "runtime.json").write_text(
        json.dumps({"seconds": round(time.time() - started, 1)},
                   indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "ewram_stats": ewram["stats"],
        "vram_stats": vram["stats"] if vram else None,
        "files": len(receipt["manifest"]),
    }, ensure_ascii=False))
    victory = ewram["stats"]["victory"]
    return 0 if victory else 1


if __name__ == "__main__":
    raise SystemExit(main())
