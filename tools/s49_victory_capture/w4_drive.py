#!/usr/bin/env python3
"""Step-wise driver for the original S49 battle (stream W4 exploration tool).

The game is deterministic, so a key sequence is a *route*: replaying the same
keys from the same savestate always produces the same battle.  This tool
executes a route one key at a time and, after every step, records

* the live battle state (HP of all nine slots, every unit's live cell, the
  cell cursor, the menu level / menu cursor / action-tail bytes), and
* a PNG of the frame the step ended on,

and it can save a savestate per step, so a later iteration can resume from
any step instead of replaying from the beginning.

That is the method change of stream W4: the previous attempts drove the game
with a closed-loop pixel classifier; this one drives it with an **open loop**
route whose every step is *visible*, and the recording side never has to
guess what screen it is on.

Usage::

    python tools/s49_victory_capture/w4_drive.py \
        --state "<...>/scenario-49-battle-14-turn4-two-kills.ss9" \
        --keys "A:60,A:60,Down:30" --out build/s49-victory-capture/w4/drive1
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


def parse_sequence(spec: str) -> list[tuple[str, int]]:
    """``"A:60,Down"`` -> ``[("A", 60), ("Down", 90)]``."""
    steps: list[tuple[str, int]] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "*" in token:
            name, _, count = token.partition("*")
            steps.extend([(name.strip(), 90)] * int(count))
            continue
        if ":" in token:
            name, _, settle = token.partition(":")
            steps.append((name.strip(), int(settle)))
        else:
            steps.append((token, 90))
    return steps


def dump_record(probe: probe_module.Probe, slot: int) -> str:
    """The full 0x1D4 byte unit record of ``slot``, read in 12 byte chunks.

    The mGBA CLI debugger dies on a large dump (stream M measured 7488 bytes
    to fail, 13 bytes to be safe), so the record is read in small pieces.
    """
    base = s49_state.POOL_ADDRESS + slot * s49_state.POOL_STRIDE
    blob = b""
    for offset in range(0, s49_state.POOL_STRIDE, 12):
        chunk = min(12, s49_state.POOL_STRIDE - offset)
        blob += probe.dump(base + offset, chunk)
    return blob.hex()


def read_state(probe: probe_module.Probe) -> dict:
    """Sample the live battle state (small reads only: <= 13 bytes each)."""
    hp = []
    for slot in range(1, SLOTS + 1):
        base = s49_state.POOL_ADDRESS + slot * s49_state.POOL_STRIDE
        hp.append(probe.dump(base + 0x0C, 1)[0])
    units = []
    for slot in range(1, SLOTS + 1):
        base = s49_state.POOL_ADDRESS + slot * s49_state.POOL_STRIDE
        blob = probe.dump(base + 0xC0, 13)
        status = probe.dump(base + 0xCC, 4)
        if not any(blob) and hp[slot - 1] == 0:
            continue
        units.append({
            "slot": slot,
            "name": s49_state.SLOT_NAMES.get(slot, f"slot-{slot}"),
            "hp": hp[slot - 1],
            "flags": blob[0],
            "acting": bool(blob[1]),
            "cell": [blob[7], blob[8]],
            "side": blob[12],
            "status": list(status),
        })
    cursor = probe.dump(0x02026A78, 3)
    return {
        "units": units,
        "hp": hp,
        "cursor": list(cursor),
        "menu_level": probe.dump(0x02026A8C, 1)[0],
        "menu_cursor": probe.dump(0x0200A8BA, 1)[0],
        "action_tail": list(probe.dump(0x0200A880, 4)),
        "side": probe.dump(0x0202680E, 1)[0],
        "selected_slot": probe.dump(0x02026A41, 1)[0],
    }


def classify_shot(path: pathlib.Path, level: int, cursor_active: bool) -> str:
    """Name the screen from the calibrated pixel signatures (battle_obs)."""
    from PIL import Image
    image = Image.open(path).convert("RGB")
    return battle_obs.classify(image, level, cursor_active)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-victory-capture" / "w4" / "drive")
    parser.add_argument("--keys", default="", help="key sequence, e.g. 'A:60,Down:30'")
    parser.add_argument("--hold", type=int, default=4)
    parser.add_argument("--settle", type=int, default=90)
    parser.add_argument("--save-states", action="store_true",
                        help="save a savestate after every step")
    parser.add_argument("--record-slot", type=int, default=0,
                        help="also dump the full unit record of this slot at "
                             "every step (hex)")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    shots_dir = args.out / "steps"
    shots_dir.mkdir(parents=True, exist_ok=True)
    states_dir = args.out / "states"
    if args.save_states:
        states_dir.mkdir(parents=True, exist_ok=True)

    steps = parse_sequence(args.keys)
    records = []
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        probe.frames(args.settle, 0)
        state = read_state(probe)
        shot0 = shots_dir / "step-000.png"
        probe.shot(shot0)
        records.append({"step": 0, "key": None, "state": state,
                        "screen": classify_shot(shot0, state["menu_level"],
                                                bool(state["cursor"][2])),
                        "unit_record": dump_record(probe, args.record_slot)
                        if args.record_slot else None})
        for index, (key, settle) in enumerate(steps, start=1):
            if key.lower() != "wait":
                mask = probe_module.key_mask([key])
                probe.frames(args.hold, mask)
                probe.frames(1, 0)
            probe.frames(settle, 0)
            state = read_state(probe)
            shot = shots_dir / f"step-{index:03d}-{key}.png"
            probe.shot(shot)
            record = {"step": index, "key": key, "settle": settle,
                      "state": state,
                      "screen": classify_shot(shot, state["menu_level"],
                                              bool(state["cursor"][2])),
                      "unit_record": dump_record(probe, args.record_slot)
                      if args.record_slot else None}
            records.append(record)
            if args.save_states:
                probe.save(states_dir / f"step-{index:03d}.ss9")

    receipt = {
        "schema": "konoha.s49-victory-drive-w4.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "state": str(args.state),
        "state_sha256": sha256_file(args.state),
        "keys": args.keys,
        "hold": args.hold,
        "default_settle": args.settle,
        "steps": records,
    }
    (args.out / "steps.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    for record in records:
        state = record["state"]
        bees = [unit for unit in state["units"]
                if unit["side"] == 1 and unit["hp"] > 0]
        print(f"step {record['step']:3d} key={str(record['key']):6s} "
              f"screen={record.get('screen'):9s} "
              f"level={state['menu_level']} cur={state['cursor']} "
              f"mcur={state['menu_cursor']} hp={state['hp']} "
              f"bees={[(b['slot'], b['hp'], b['cell']) for b in bees]}")
    print(f"written: {args.out / 'steps.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
