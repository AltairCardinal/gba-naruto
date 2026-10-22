#!/usr/bin/env python3
"""Watch the battle round counter while a real battle is played.

`0x0202680C` (the battle control block's byte 8) is compared against the
round limit in `ctrl[6]` by the type-2 victory rule (``0x08077914``..
``0x0807791A``), so it is the engine's **round counter**.  This tool enters
a real battle with the three-write route and presses a long key plan
through the battle UI, recording the control block after every press so
the round advance can be seen (or not seen) directly.

Usage:
    python tools/closure_round_probe.py --battle 9:0 --json build/rounds.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, KEY_BITS, PHASE_BATTLE, SCENE_BYTE, SUBCFG_BYTE, PHASE_WORD,
    MAPID_BYTE, UNIT_ARRAY, UNIT_STRIDE, UNIT_SLOTS,
)

BATTLE_CTRL = 0x02026804
UNIT_HP_SCAN = 0x40          # bytes of every unit slot to fingerprint


def read_unit_fingerprint(harness: Harness) -> list[str]:
    out = []
    for slot in range(UNIT_SLOTS):
        raw = harness.read(UNIT_ARRAY + slot * UNIT_STRIDE, UNIT_HP_SCAN)
        if raw and any(raw):
            out.append(f"{slot}:{raw.hex()}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--battle", default="9:0")
    ap.add_argument("--rounds", type=int, default=40)
    ap.add_argument("--plan", default="A,UP,A,DOWN,A,LEFT,A,RIGHT,A,B,A")
    ap.add_argument("--settle", type=int, default=60)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    group, _, sub = args.battle.partition(":")
    harness = Harness(args.exe, pathlib.Path(args.rom))
    keys = [k.strip() for k in args.plan.split(",") if k.strip()]
    log: list[dict] = []
    try:
        if not harness.boot_to_state_machine():
            print("could not park on the state machine loop head", file=sys.stderr)
            return 1
        harness.poke(SCENE_BYTE, int(group))
        harness.poke(SUBCFG_BYTE, int(sub))
        harness.poke16(PHASE_WORD, PHASE_BATTLE)
        # let the battle intro play out
        for _ in range(30):
            harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
            harness.send("frames 120 0x000")
            raw = harness.read(MAPID_BYTE, 1)
            if raw and raw[0] == int(group):
                break
        harness.send(f"frames 8 {KEY_BITS['A']:#05x}")
        harness.send("frames 120 0x000")

        for index in range(args.rounds):
            key = keys[index % len(keys)]
            harness.send(f"frames 8 {KEY_BITS[key]:#05x}")
            harness.send(f"frames {args.settle} 0x000")
            ctrl = harness.read(BATTLE_CTRL, 0x18)
            if not ctrl:
                break
            entry = {
                "press": index,
                "key": key,
                "ctrl": ctrl.hex(),
                "round_limit": ctrl[6] if len(ctrl) > 6 else None,
                "round_counter": ctrl[8] if len(ctrl) > 8 else None,
                "units": read_unit_fingerprint(harness),
            }
            log.append(entry)
            print(f"press {index:3} key={key:<5} ctrl={ctrl.hex()} "
                  f"limit={entry['round_limit']} counter={entry['round_counter']} "
                  f"units={len(entry['units'])}")
    finally:
        harness.close()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
    counters = sorted({e["round_counter"] for e in log})
    print("distinct round counter values:", counters)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
