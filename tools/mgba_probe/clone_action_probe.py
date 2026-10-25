#!/usr/bin/env python3
"""Read the *battle action list* that every unit carries.

What this tool proves
---------------------
A battle unit (WRAM ``0x020240C0`` + slot*0x1D4) carries two parallel
16-entry tables of 8-byte records:

    unit+0x0D4 + i*8   the *source* table: byte 0 = action id (& 0x3F),
                       bytes 1..7 = the action's parameters
    unit+0x154 + i*8   the *live* table: the records that have been armed
                       for this fight (byte 0 = action id, 0 = empty slot)

``fn 0x0806C40C`` dispatches the live table through the 60-case switch whose
table base is ``0x0806C478``; the case index is ``(action_id & 0x3F) - 4``,
so only action ids 4..63 have a dedicated implementation and everything else
falls through to the default at ``0x0806D1A2``.

``fn 0x0806C160(unit, slot)`` looks a slot id up in the source table, and the
battle setup installs five slot ids per character: 0x0E(14), 0x0F(15),
0x15(21), 0x3D(61), 0x3E(62).

The shadow clone ("影分身术", ninjutsu id 7 in the name table 0x0859937C) is
one of those five slots, so this dumper answers directly: *which action ids
does this character own, and what are their parameter bytes?*

Usage
-----
    python tools/mgba_probe/clone_action_probe.py rom/base.gba --group 21 --sub 0
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import Harness as Probe, KEY_BITS  # noqa: E402
import re  # noqa: E402

HIT_RE = re.compile(r"(?:Hit breakpoint|Hit watchpoint)\s+#?(\d+)\s+at\s+(0x[0-9a-fA-F]+)")

STORY_STATE = 0x020311D4
SCENE_BYTE = STORY_STATE + 0x16
SUBCFG_BYTE = STORY_STATE + 0x19
PHASE_WORD = STORY_STATE + 0x12
MAPID_BYTE = STORY_STATE + 0x17
PHASE_BATTLE = 0x0110

STATE_LOOP = 0x0808F752
PHASE_110 = 0x0808F92E
BATTLE_WRAPPER = 0x080732B4

UNIT_ARRAY = 0x020240C0
UNIT_STRIDE = 0x1D4
UNIT_SLOTS = 12

ACTION_LIST = 0x154      # live action table
ACTION_SOURCE = 0x0D4    # source action table (id + parameters)
ACTION_ENTRIES = 16
ACTION_RECORD = 8

# the five ninjutsu slots the battle setup installs, and the action ids the
# dispatch switch implements (case index = id - 4)
SLOT_IDS = (0x0E, 0x0F, 0x15, 0x3D, 0x3E)
IMPLEMENTED_IDS = (4, 5, 13, 14, 15, 17, 18, 21, 22, 25, 27, 30, 31, 32, 33,
                   34, 35, 36, 37, 61, 62, 63)


def hit_of(lines) -> int | None:
    for line in lines:
        m = HIT_RE.search(line)
        if m:
            return int(m.group(2), 16)
    return None


class Driver(Probe):
    def start_battle(self, group: int, sub: int, battle_frames: int = 40) -> int | None:
        if not self.boot_to_state_machine():
            return None
        self.arm(PHASE_110)
        self.arm(BATTLE_WRAPPER)
        self.poke(SCENE_BYTE, group)
        self.poke(SUBCFG_BYTE, sub)
        self.poke16(PHASE_WORD, PHASE_BATTLE)
        for _ in range(12):
            out = self.send("cont 900")
            hit = hit_of(out)
            if hit is None:
                out = self.send("frames 8 0x001") + self.send("frames 120 0x000")
                hit = hit_of(out)
            if hit is None:
                break
            self.send("next")
            self.rearm()
            if hit == BATTLE_WRAPPER:
                break
        self.disarm_all()
        for _ in range(battle_frames):
            self.send("frames 8 0x001")
            self.send("frames 120 0x000")
            raw = self.read(MAPID_BYTE, 1)
            if raw and raw[0] == group:
                break
        return group

    def dump_units(self) -> list[dict]:
        out = []
        for slot in range(UNIT_SLOTS):
            base = UNIT_ARRAY + slot * UNIT_STRIDE
            head = self.read(base, 2)
            if len(head) < 2 or head[0] == 0:
                continue
            src = self.read(base + ACTION_SOURCE, ACTION_ENTRIES * ACTION_RECORD)
            live = self.read(base + ACTION_LIST, ACTION_ENTRIES * ACTION_RECORD)
            out.append({
                "slot": slot,
                "char_id": head[0],
                "side": head[1],
                "source": [src[i:i + ACTION_RECORD].hex()
                           for i in range(0, len(src), ACTION_RECORD)] if src else [],
                "live": [live[i:i + ACTION_RECORD].hex()
                         for i in range(0, len(live), ACTION_RECORD)] if live else [],
            })
        return out

    def press(self, mask: int, frames: int = 8, settle: int = 120) -> None:
        self.send(f"frames {frames} {mask:#05x}")
        self.send(f"frames {settle} 0x000")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", type=pathlib.Path, nargs="?", default=REPO / "rom" / "base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--group", type=int, default=21)
    ap.add_argument("--sub", type=int, default=0)
    ap.add_argument("--battle-frames", type=int, default=40)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    if not args.exe.exists():
        print(f"ERR {args.exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    probe = Driver(args.exe, args.rom, timeout=1800)
    report: dict = {"group": args.group, "sub": args.sub, "phases": []}
    try:
        got = probe.start_battle(args.group, args.sub, args.battle_frames)
        report["battle_reached"] = got is not None
        report["phases"].append({"phase": "after-intro", "units": probe.dump_units()})
        # let the fight run and try every button, dumping after each round
        for mask in (0x001, 0x002, 0x008, 0x004, 0x100, 0x200):
            for _ in range(6):
                probe.press(mask)
            report["phases"].append(
                {"phase": f"after-press-{mask:#05x}", "units": probe.dump_units()})
    finally:
        probe.close()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for ph in report["phases"]:
        print("=" * 78)
        print(f"PHASE {ph['phase']}")
        print("=" * 78)
        for u in ph["units"]:
            src = [(i, r) for i, r in enumerate(u["source"]) if r[:2] != "00"]
            live = [(i, r) for i, r in enumerate(u["live"]) if r[:2] != "00"]
            if not src and not live:
                continue
            print(f"  slot {u['slot']:2d}  char_id {u['char_id']:3d}  side {u['side']}")
            for i, r in src:
                aid = int(r[:2], 16)
                print(f"      src [{i:2d}] id {aid & 0x3F:2d}  raw {r}"
                      + ("   <- implemented" if (aid & 0x3F) in IMPLEMENTED_IDS else ""))
            for i, r in live:
                aid = int(r[:2], 16)
                print(f"      live[{i:2d}] id {aid & 0x3F:2d}  raw {r}")
    print()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
