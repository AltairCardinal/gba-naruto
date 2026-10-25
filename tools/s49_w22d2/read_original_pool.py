#!/usr/bin/env python3
"""Read the ORIGINAL game's battle unit pool out of a ``.ss9`` savestate.

Wave 22 / D2 needs one fact from the original ROM: **who made the two kills
that already happened when the settlement truth was captured?**  The truth was
captured from ``scenario-49-battle-14-turn4-two-kills.ss9``; the original's
battle state lives in EWRAM and can be read without an emulator.

Field layout (reverse-engineering line, read-only, re-stated here):

    unit pool  0x020240C0 + slot * 0x1D4   (slot 1..9)

    +0x00  character id (0 = the slot is dead)
    +0x0C  current HP (also mirrored in the HP array)
    +0xC1  "this unit is acting / selected" flag
    +0xC4  map x
    +0xC5  map y
    +0xCE  carried experience (a dead unit's carried experience is moved to
           its killer)

    control  0x02026804 .. 0x0202680B (8 bytes)  -- battle id in byte 0
    round    0x0202680C                      -- current round

Character ids: 1 = Naruto, 2 = Sasuke, 3 = Sakura, 30 = Konohamaru
(the escort), 55 = a bee (the backup troops).

Usage::

    python tools/s49_w22d2/read_original_pool.py --state <a.ss9>
    python tools/s49_w22d2/read_original_pool.py --state <a.ss9> --json out.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_w20e"))

from ss9_wram import file_sha256, load_state  # noqa: E402

POOL_ADDRESS = 0x020240C0
POOL_STRIDE = 0x1D4
HP_ARRAY_ADDRESS = 0x020242A0
BATTLE_CONTROL = 0x02026804
BATTLE_ROUND = 0x0202680C

CHARACTER_NAMES = {
    0: "(dead)",
    1: "Naruto",
    2: "Sasuke",
    3: "Sakura",
    30: "Konohamaru(escort)",
    55: "Bee",
}


def decode(state, slots: int) -> list[dict]:
    rows = []
    for slot in range(1, slots + 1):
        base = POOL_ADDRESS + slot * POOL_STRIDE
        record = state.read_memory(base, POOL_STRIDE)
        if not any(record):
            continue
        hp_base = HP_ARRAY_ADDRESS + (slot - 1) * POOL_STRIDE
        character_id = record[0]
        rows.append({
            "slot": slot,
            "address": f"0x{base:08X}",
            "character_id": character_id,
            "character": CHARACTER_NAMES.get(character_id, f"id{character_id}"),
            "hp_pool_0x0C": record[0x0C],
            "hp_array": state.read_memory(hp_base, 1)[0],
            "acting_flag_0xC1": record[0xC1],
            "x_0xC4": record[0xC4],
            "y_0xC5": record[0xC5],
            "carried_exp_0xCE_u16": state.read_memory(base + 0xCE, 2)[0]
            | (state.read_memory(base + 0xCE, 2)[1] << 8),
            "carried_exp_0xCE_u32": int.from_bytes(
                state.read_memory(base + 0xCE, 4), "little"),
            "bytes_0xCE_0xD6": record[0xCE:0xD6].hex(),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", required=True)
    parser.add_argument("--slots", type=int, default=9)
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    state = load_state(args.state)
    control = state.read_memory(BATTLE_CONTROL, 8)
    document = {
        "state": args.state,
        "state_sha256": file_sha256(args.state),
        "battle_control_0x02026804": control.hex(),
        "battle_id": control[0],
        "round_0x0202680C": state.read_memory(BATTLE_ROUND, 1)[0],
        "slots": decode(state, args.slots),
    }
    print(json.dumps(document, ensure_ascii=False, indent=1))
    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
