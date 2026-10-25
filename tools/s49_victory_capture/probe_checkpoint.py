#!/usr/bin/env python3
"""Inspect an original-ROM battle checkpoint in the live probe.

Why this tool exists
--------------------
Stream W4 (fifth attempt) does **not** replay the whole battle.  The reverse
engineering line already played battle 14 to its end on the *same* base ROM
(``rom/base.gba``, sha256 ``1198ece7...``) and left checkpoints behind:

* ``scenario-49-battle-14-entry.ss9``            sha256 a3628723...
* ``scenario-49-battle-14-turn4-two-kills.ss9``  sha256 e8b2a5ee...
* ``scenario-49-battle-14-postbattle-task-menu.ss9`` sha256 8dfca229...

The last one proves the battle *is* winnable on this ROM, so the missing
puzzle is not "can it be won" but "what is on the screen when it ends".

The offline reader (``s49_state.py``) can parse those savestates without an
emulator, but the HP array keeps the **last known** HP of a defeated unit, so
it cannot answer "who is still alive".  This tool asks the running game:
it loads the checkpoint, takes the rendered frame (the HUD bar shows every
unit's HP) and reads the live state registers.

Reads stay small (<= 13 bytes per command): the mGBA CLI debugger dies with
a broken pipe on a 7488 byte dump (stream M, hypothesis M14).

Usage::

    python tools/s49_victory_capture/probe_checkpoint.py \
        --state "<...>/scenario-49-battle-14-turn4-two-kills.ss9" \
        --out build/s49-victory-capture/w4/turn4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import battle_obs  # noqa: E402
import probe as probe_module  # noqa: E402
import s49_state  # noqa: E402

REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe-w4" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-turn4-two-kills.ss9")

SLOTS = 9


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-victory-capture" / "w4" / "probe")
    parser.add_argument("--settle", type=int, default=30,
                        help="frames to run after loading (let the UI settle)")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    raw_path = args.out / "frame.raw"
    shot_path = args.out / "screen.png"

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        if args.settle:
            probe.frames(args.settle, 0)
        probe.run(f"rawshot {raw_path}")
        probe.shot(shot_path)

        level = probe.dump(battle_obs.ADDR_MENU_LEVEL, 1)[0]
        menu_cursor = probe.dump(battle_obs.ADDR_MENU_CURSOR, 1)[0]
        cursor = probe.dump(battle_obs.ADDR_CURSOR, 3)

        units = []
        for slot in range(1, SLOTS + 1):
            base = s49_state.POOL_ADDRESS + slot * s49_state.POOL_STRIDE
            hp = probe.dump(base + 0x0C, 1)[0]
            blob = probe.dump(base + 0xC0, 13)
            units.append({
                "slot": slot,
                "name": s49_state.SLOT_NAMES.get(slot, f"slot-{slot}"),
                "hp": hp,
                "flag_c1": blob[0xC1 - 0xC0],
                "start_xy": [blob[0xC4 - 0xC0], blob[0xC5 - 0xC0]],
                "live_xy": [blob[0xC7 - 0xC0], blob[0xC8 - 0xC0]],
                "side": blob[0xCC - 0xC0],
                # the 12 bytes around +0xC0 .. +0xCC that are not decoded yet
                "raw_c0_cc": blob.hex(),
            })

        # a wide slice of the *control* block: the battle controller keeps more
        # state next to the cursor than the menu level register
        control = probe.dump(0x02026A70, 32).hex()

    document = {
        "schema": "konoha.s49-victory-checkpoint-probe.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "state": str(args.state),
        "state_sha256": sha256_file(args.state),
        "settle": args.settle,
        "menu_level": level,
        "menu_cursor": menu_cursor,
        "cursor": list(cursor),
        "units": units,
        "control_block_02026A70_32B": control,
        "screen": str(shot_path),
    }
    out_json = args.out / "checkpoint.json"
    out_json.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(json.dumps(document, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
