#!/usr/bin/env python3
"""Sweep the story state machine's phases and see which tables each one reads.

The state machine (`fn 0x0808F73C`, loop head 0x0808F752) dispatches on
`state[0x12]` (the u16 phase).  Each phase handler is a thin wrapper around
one subsystem, and *several* of the structures that still have open gaps are
read from exactly such a handler -- the dialogue pointer table
(0x08461CE8) turned out to be read by the phase `0x0210` handler and by
nothing else, which is why no story route ever hit it.

This tool therefore pokes one phase at a time, presses A so the state
machine dispatches it, and reports which watch sites fired.  The phase list
is derived from the dispatcher itself:

    0x0000 -> 0x0808F80E   0x0010 -> 0x0808F814   0x0018 -> 0x0808F872
    0x0020 -> 0x0808F892   0x0030 -> 0x0808F8DC   0x0100 -> 0x0808F928
    0x0110 -> 0x0808F92E   0x0118 -> 0x0808F94A   0x0120 -> 0x0808F9C0
    0x0200 -> 0x0808F9E2   0x0210 -> 0x0808F9EC   0x0300 -> 0x0808FA04
    0x0700 -> 0x0808FA26   0x1000 -> 0x0808FA0A   0x1100 -> 0x0808FA1C
    0x8000 -> 0x0808FA2C

Usage:
    python tools/mgba_probe/phase_sweep.py rom/base.gba --json build/phase-sweep.json
    python tools/mgba_probe/phase_sweep.py rom/base.gba --phases 0x300,0x210
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
    Harness, hit_of, KEY_BITS, PHASE_WORD,
)
from tools.mgba_probe.runtime_probe import parse_status  # noqa: E402

STATE = 0x020311D4
SCENE_BYTE = STATE + 0x16

DEFAULT_PHASES = [0x0000, 0x0010, 0x0018, 0x0020, 0x0030, 0x0100, 0x0110,
                  0x0118, 0x0120, 0x0200, 0x0210, 0x0300, 0x0700, 0x1000,
                  0x1100, 0x8000]

# site -> (label, structure, table base)
#
# Every entry is a *decision point*: the instruction right after the
# `ldr rX,[pc,#imm]` that loads the table base, so the base (and often the
# index) is already in a register.
WATCH: dict[int, tuple[str, str, int]] = {
    0x080917B0: ("dialogue pointer table", "text-writeback", 0x08461CE4),
    0x0808A6BC: ("data table A", "data-table-a", 0x085A143C),
    0x08087D02: ("battle encounter table", "battle-encounters", 0x0854229C),
    0x0806D91C: ("items / skills table", "items", 0x08545BE4),
    0x08078EFA: ("items / skills table", "items", 0x08545BE4),
    0x08078F0A: ("items / skills table", "items", 0x08545BE4),
    0x0808FC2A: ("items / skills table", "items", 0x08545BE4),
    0x0808FF7A: ("items / skills table", "items", 0x08545BE4),
    0x08095396: ("items / skills table", "items", 0x08545BE4),
    0x080953A6: ("items / skills table", "items", 0x08545BE4),
    0x0806F506: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x080796E6: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x08079706: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x08081644: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x08081700: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x0808E9FA: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x0808EA64: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x08090288: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x08090352: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x0809734E: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x080973E8: ("ninjutsu names table", "ninjutsu-names", 0x08599634),
    0x0807B222: ("resource pointers table", "resource-pointers", 0x08596F0C),
    0x0807F0FE: ("font width table", "fonts", 0x0853E596),
    0x080806BC: ("sprite frame descriptors", "sprite-frame-descriptors",
                 0x0853EE98),
    0x08080780: ("sprite frame descriptors", "sprite-frame-descriptors",
                 0x0853EE98),
    0x08080830: ("sprite frame descriptors", "sprite-frame-descriptors",
                 0x0853EE98),
    0x08081352: ("mechanism effects", "mechanism-effects", 0x0808136C),
    0x080893F2: ("reward table", "reward-table", 0x0859EAE0),
    0x08089EA4: ("reward table", "reward-table", 0x0859EAE0),
    0x08089F02: ("reward table", "reward-table", 0x0859EAE0),
    0x08089F82: ("reward table", "reward-table", 0x0859EAE0),
    0x080985DA: ("data table B", "data-table-b", 0x085A2034),
    0x08099D28: ("data table B", "data-table-b", 0x085A2034),
    0x08061DD6: ("function pointer table", "function-pointers", 0x0853D5F0),
    0x0809AACC: ("sound id table", "sound-id-table", 0x08465B70),
    0x0809B242: ("m4a SongHeader", "story", 0x08536368),
    0x08087334: ("mission text", "mission-text", 0x08348DAC),
    # The story dispatcher writes story_config[0] (0x020311ED) and then
    # clears story_branch (0x020311EC) one instruction later, so the only
    # place a non-zero value can be observed is between the two.
    0x0808F5CA: ("story_config[0]", "runtime-state", 0x020311ED),
    # The battle entry reads state[0x19] into r0 and copies it to ctrl[2].
    0x0808F93E: ("story_config[0] read", "runtime-state", 0x020311ED),
    # The cutscene block loader's table load.
    0x08072F0E: ("cutscene block table", "cutscene-scripts", 0x0853DF70),
    # The chapter menu (phase 0x0120 -> 0x0808F9C0 -> fn 0x0808A0F0 ->
    # fn 0x08089310) plays sound id 14 once the mission list runs past its
    # ninth entry; the m4a engine then reads the song header of that id.
    0x080894FC: ("sound id 14 jingle (mission list end)", "story-e", 0),
    0x0809AAD6: ("m4a song header (play by sound id)", "story-e", 0),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path,
                    default=REPO / "build" / "mgba-probe" / "mgba-probe.exe")
    ap.add_argument("--phases", default=None,
                    help="comma separated phase list (default: all of them)")
    ap.add_argument("--presses", type=int, default=24)
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    phases = ([int(p, 0) for p in args.phases.split(",")]
              if args.phases else list(DEFAULT_PHASES))

    report: dict = {"phases": {}}
    for phase in phases:
        harness = Harness(args.exe, pathlib.Path(args.rom))
        entry: dict = {"fired": [], "hits": []}
        try:
            if not harness.boot_to_state_machine():
                print("could not park on the state machine", file=sys.stderr)
                return 2
            for addr in WATCH:
                harness.arm(addr)
            harness.poke16(PHASE_WORD, phase)
            harness.send("next")
            for _ in range(args.presses):
                # The register dump has to be taken *immediately* after the
                # `frames` call that produced the hit: issuing a second
                # `frames` moves the debugger to the next stop, and the dump
                # would then belong to that later stop instead of this one.
                stops: list[tuple[int, dict, int]] = []
                for cmd in (f"frames 8 {KEY_BITS['A']:#05x}",
                            "frames 120 0x000"):
                    out = harness.send(cmd)
                    h = hit_of(out)
                    if h is None:
                        continue
                    raw = harness.probe.send("status")
                    regs = parse_status(raw)
                    # mGBA prints r13/r14/r15 -- there is no "pc:" line, so
                    # the program counter is r15.
                    stops.append((h, regs, regs.get("r15", 0)))
                    harness.send("next")
                    harness.rearm()
                for h, regs, pc in stops:
                    # a genuine hit has |pc - addr| <= 4 (a 16- or 32-bit
                    # Thumb instruction); anything else is a dump taken at a
                    # different stop and must not be filed under this
                    # address -- see notes/evidence/
                    # callback-dispatch-runtime-20261021.md §2.5.2.
                    genuine = abs(pc - h) <= 4
                    label, structure, base = WATCH.get(
                        h, (f"0x{h:08X}", "?", 0))
                    rec = {"at": f"0x{h:08X}", "label": label,
                           "structure": structure,
                           "genuine": genuine,
                           "pc": f"0x{pc:08X}",
                           "r0": f"0x{regs.get('r0', 0):08X}",
                           "r1": f"0x{regs.get('r1', 0):08X}",
                           "r2": f"0x{regs.get('r2', 0):08X}",
                           "r3": f"0x{regs.get('r3', 0):08X}",
                           "r4": f"0x{regs.get('r4', 0):08X}",
                           "r5": f"0x{regs.get('r5', 0):08X}",
                           "r6": f"0x{regs.get('r6', 0):08X}",
                           "r7": f"0x{regs.get('r7', 0):08X}",
                           "r13": f"0x{regs.get('r13', 0):08X}",
                           "r14": f"0x{regs.get('r14', 0):08X}"}
                    if base:
                        rec["table_base"] = f"0x{base:08X}"
                        rec["table_dump"] = harness.read(base, 32).hex(" ")
                    entry["hits"].append(rec)
                    if genuine and f"0x{h:08X}" not in entry["fired"]:
                        entry["fired"].append(f"0x{h:08X}")
        finally:
            harness.close()
        report["phases"][f"0x{phase:04X}"] = entry
        genuine_hits = [r for r in entry["hits"] if r["genuine"]]
        structs = sorted({r["structure"] for r in genuine_hits})
        print(f"phase 0x{phase:04X}: {len(genuine_hits)} genuine hit(s) "
              f"of {len(entry['hits'])}  structures={structs}")
    if args.json:
        from tools.lib.io import write_json
        write_json(args.json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
