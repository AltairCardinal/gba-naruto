#!/usr/bin/env python3
"""Run the chapter (level) route and census the callback dispatch points.

`tools/mgba_probe/callback_census.py` answers "which dispatch point does a
route hit" for the battle / save / sweep routes.  All three of them never
reach the ROM callback tables, because those tables are only read by the
**level mode**: the story VM's chapter hand-off (`1A <scene> 00` -> the
state machine's phase `0x100`) -> `fn 0x08088F10` -> the mission panel ->
the battle entry -> `fn 0x080732B4`.

The route is:

    scene 1, story branch 0
      -> the story VM's `0x0B` condition is patched at 0x08097AC4 so the
         mission dialogue is taken
      -> the "do you know Kato" menu is answered with row 1 (the answer
         channel 0x0200A880 / 0x0200A882 is written at 0x080960BE)
      -> `1A 02 00` fires: state[0x18] = 1, state[0x16] = 2
      -> the state machine's phase `0x30` handler reads state[0x18] at
         0x0808F904 and switches to phase `0x100`
      -> phase `0x100` calls `fn 0x08088F10` (the chapter setup)
      -> the mission panel `fn 0x080884DC` opens its own menu; the answer
         channel is written at 0x080885C0 with row 1 ("start the battle")
      -> the chapter setup's `r4 == 0x20` branch enters the battle

At every dispatch point this tool records the registers **and** a dump of
the table that the dispatch point reads, so the runtime readout can be
matched to the structure fields.

Usage:
    python tools/mgba_probe/chapter_census.py rom/base.gba --json build/chapter-census.json
    python tools/mgba_probe/chapter_census.py rom/base.gba --sites 0x0807FD36,0x08080B12
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
for _p in (REPO, REPO / "tools", REPO / "tools" / "mgba_probe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.mgba_probe.l4_battle_matrix import (  # noqa: E402
    Harness, hit_of, KEY_BITS, PHASE_NEXT_SCENE, SCENE_BYTE, PHASE_WORD,
)
from tools.mgba_probe.callback_census import WATCH as CENSUS_WATCH  # noqa: E402

DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

STATE = 0x020311D4
BRANCH_BYTE = STATE + 0x18
COND_BASE = 0x020314F0
ANSWER_ADDR = 0x0200A880
FINISHED_ADDR = 0x0200A882

# control sites: the three places the route has to be nudged
COND_READ = 0x08097AC4
STORY_ANSWER_SITE = 0x080960BE
MISSION_ANSWER_SITE = 0x080885C0

# the table a dispatch point reads, so the census can dump it
TABLE_BASE = {
    "battle-handlers": 0x0853E698,
    "map-events": 0x0853E698,
    "fonts": 0x0853E596,
    "font-metrics": 0x0853E328,
    "object-types": 0x0853EF30,
    "map-sprites": 0x0853F140,
    "units": 0x0853F298,
    "entity-spawn": 0x0853F310,
    "items": 0x08545BE4,
    "skills": 0x08545BE4,
    "levels": 0x085459C8,
    "battle-encounters": 0x0854229C,
    "ninjutsu-names": 0x08599634,
    "data-table-a": 0x085A143C,
    "data-table-b": 0x085A2034,
    "function-pointers": 0x0853D5F0,
    "resource-pointers": 0x08596F0C,
    "mission-text": 0x08348DAC,
    "tile-assets": 0x085A320C,
    "sprite-frame-descriptors": 0x0853EE98,
    "menu-ui": 0x085A4DEC,
    "sound-id-table": 0x08465B70,
    "story": 0x0859AA5C,
    "story-b": 0x08536BC4,
    "story-c": 0x08538FEC,
    "story-d": 0x0853AB74,
    "story-e": 0x0853C3BC,
    "character-stats": 0x08545068,
    "character-stats-b": 0x08545068,
    "battle-config": 0x085461C4,
    "sprite-animations": 0x08596CCC,
    "sprite-action-table": 0x08596CCC,
    "character-template": 0x0854241C,
    "mechanism-effects": 0x0808136C,
    "text-writeback": 0x08461CE8,
    "sound-id-table": 0x08465B70,
}

CONTROL = {
    COND_READ: "cond-read",
    STORY_ANSWER_SITE: "story-menu-answer",
    MISSION_ANSWER_SITE: "mission-menu-answer",
}

# The decision points the level mode is expected to reach.  They are the
# *same* points the L2 evidence note uses (notes/evidence/
# l2-runtime-evidence-20261021.md §D.3), reached through the level route
# instead of the battle route.  Listing them here keeps the census
# self-describing: the file itself documents what it is looking for.
LEVEL_SITES = {
    0x0806D9D8: "character stats 0x08545068 (decision point)",
    0x0806E1FE: "battle formation 0x085461C4 (decision point)",
    0x0806B770: "sprite action table 0x08596CCC (decision point)",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--scene", type=int, default=1)
    ap.add_argument("--cond", type=int, default=2)
    ap.add_argument("--force-row", type=int, default=1)
    ap.add_argument("--force-mission", type=int, default=1)
    ap.add_argument("--presses", type=int, default=1500)
    ap.add_argument("--keys", default="A")
    ap.add_argument("--sites", default=None,
                    help="comma separated dispatch points to watch instead of "
                         "the default set")
    ap.add_argument("--dump-len", type=int, default=48)
    ap.add_argument("--state", type=pathlib.Path, default=None,
                    help="load this savestate instead of replaying the story; "
                         "it must be a state where the level mode is already "
                         "reached (chapter_route.py --save writes one)")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    names = ["A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN"]
    keys = [KEY_BITS[k.strip().upper()] for k in args.keys.split(",")
            if k.strip().upper() in names] or [KEY_BITS["A"]]

    watch = dict(CENSUS_WATCH)
    if args.sites:
        wanted = {int(s, 0) for s in args.sites.split(",")}
        watch = {a: CENSUS_WATCH.get(a, ("watched", "custom")) for a in sorted(wanted)}
    # the level decision points are always watched: they are the ones this
    # route is for.
    for addr, label in LEVEL_SITES.items():
        watch.setdefault(addr, (label, "level"))
    watch.update({a: ("control", "route") for a in CONTROL})

    harness = Harness(args.exe, pathlib.Path(args.rom))
    report: dict = {
        "scene": args.scene, "cond": args.cond,
        "force_row": args.force_row, "force_mission": args.force_mission,
        "dispatch": {}, "control": [], "phase_trail": [],
    }
    try:
        if args.state is not None:
            harness.send(f"load {args.state}")
            for addr in watch:
                harness.arm(addr)
        else:
            if not harness.boot_to_state_machine():
                print("could not park on the state machine", file=sys.stderr)
                return 2
            for addr in watch:
                harness.arm(addr)
            harness.poke(SCENE_BYTE, args.scene)
            harness.poke(BRANCH_BYTE, 0)
            harness.poke(COND_BASE, args.cond & 0xFF)
            harness.poke16(PHASE_WORD, PHASE_NEXT_SCENE)
            harness.send("next")

        for step in range(args.presses):
            key = keys[step % len(keys)]
            out = harness.send(f"frames 8 {key:#05x}")
            hit = hit_of(out)
            if hit is None:
                out = harness.send("frames 120 0x000")
                hit = hit_of(out)
            if hit is None:
                continue
            regs = harness.probe.registers()
            state = harness.read(STATE, 0x24)

            if hit in CONTROL:
                name = CONTROL[hit]
                if hit == COND_READ:
                    for off in range(8):
                        harness.poke(COND_BASE - 8 + off, 0xFF)
                    harness.poke(COND_BASE, args.cond & 0xFF)
                elif hit == STORY_ANSWER_SITE and args.force_row is not None:
                    harness.poke(ANSWER_ADDR, args.force_row & 0xFF)
                    harness.poke(FINISHED_ADDR, 1)
                elif hit == MISSION_ANSWER_SITE and args.force_mission is not None:
                    harness.poke(ANSWER_ADDR, args.force_mission & 0xFF)
                    harness.poke(FINISHED_ADDR, 1)
                report["control"].append({
                    "site": name, "pc": f"0x{regs.get('pc', 0):08X}",
                    "phase": f"0x{int.from_bytes(state[0x12:0x14], 'little'):04X}",
                })
            else:
                label, structure = watch.get(hit, ("?", "?"))
                base = TABLE_BASE.get(structure)
                dump = ""
                if base:
                    dump = harness.read(base, args.dump_len).hex(" ")
                slot = report["dispatch"].setdefault(structure, [])
                entry = {
                    "at": f"0x{hit:08X}", "label": label,
                    "regs": {k: f"0x{regs.get(k, 0):08X}"
                             for k in ("r0", "r1", "r2", "r3", "r4", "r5",
                                       "r6", "r7", "lr", "pc")},
                    "phase": f"0x{int.from_bytes(state[0x12:0x14], 'little'):04X}",
                    "scene": f"0x{state[0x16]:02X}",
                    "branch": f"0x{state[0x18]:02X}",
                }
                if base:
                    entry["table_base"] = f"0x{base:08X}"
                    entry["table_dump"] = dump
                slot.append(entry)

            phase = int.from_bytes(state[0x12:0x14], "little")
            trail = report["phase_trail"]
            if not trail or trail[-1] != phase:
                trail.append(phase)
            harness.send("next")
            harness.rearm()
    finally:
        harness.close()

    report["dispatch_summary"] = {k: len(v) for k, v in report["dispatch"].items()}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("phase trail:", " -> ".join(f"0x{p:04X}" for p in report["phase_trail"]))
    print("control hits:", len(report["control"]))
    print("dispatch summary:", json.dumps(report["dispatch_summary"],
                                          ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
