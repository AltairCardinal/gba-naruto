#!/usr/bin/env python3
"""Force the battle wrapper's entity-spawn branch by patching one ctrl byte.

`fn 0x080732B4` (the battle wrapper -- it *does* run in every battle) contains
the object-type spawn, but only behind a gate:

    0x08074400  adds  r0, #0xcd
    0x08074402  ldrb  r0, [r0]        ; r0 = ctrl[0xCD]   (ctrl base 0x02026804)
    0x08074404  cmp   r0, #0xff
    0x08074406  beq   #0x0807443c     ; -> bl fn 0x080722A8 -> fn 0x08080E30
                                       ;    (object-type spawn -> fn 0x08080B08
                                       ;     which reads 0x0853F140 / 0x0853F298)

This tool stops right *before* that `ldrb`, writes 0xFF into that byte so the
game's own compare succeeds, and then watches the spawn chain.  Everything that
follows is the game's native code; the only thing this tool does is choose
which branch the game takes.

Usage:
    python tools/mgba_probe/spawn_forcer.py rom/base.gba --groups 0
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
for _p in (REPO, REPO / "tools", REPO / "tools" / "mgba_probe"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from navigate import Probe as _BaseProbe            # noqa: E402
from runtime_probe import parse_status              # noqa: E402

STORY_STATE = 0x020311D4
SCENE_BYTE = STORY_STATE + 0x16
SUBCFG_BYTE = STORY_STATE + 0x19
PHASE_WORD = STORY_STATE + 0x12
PHASE_BATTLE = 0x0110
DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
STATE_DIR = REPO / "build" / "l2-states"

BATTLE_CTRL = 0x02026804
# `fn 0x08064A48` is the "has the battle finished?" predicate: it returns 1
# (finished) iff this IWRAM byte is ZERO.  The battle wrapper waits on it in
# a loop, so the code *after* the wait -- the entity spawn, the item/skills
# readers -- is never reached while the byte is non-zero.
BATTLE_ACTIVE_BYTE = 0x03005D44
# `fn 0x0808A534` is the story-VM entry: it clears `state[0x1B]`, runs the VM
# and then returns 1 **iff `state[0x1B]` is non-zero** (i.e. the VM asked for
# a battle).  Clearing it right after the read makes the wrapper fall into
# the event dispatcher instead of starting the battle, and the event chain
# 0x1210 -> 0x8000 -> 0x6000 ends at the entity-spawn gate.
STORY_CONFIG2 = 0x020311EF
VM_RESULT_SITE = 0x0808A56C
# The event-id switch selects the case that dispatches event 0x4080 (which
# reads the item/skill table and then dispatches 0x6000, the entity spawn)
# only when this byte equals 1.
MODE_BYTE = 0x0200A880
GATE_BYTE = BATTLE_CTRL + 0xCD          # ctrl[0xCD]
GATE_SITE = 0x08074402                  # 'ldrb r0,[r0]' -- patch just before it
GATE_CMP = 0x08074404                   # 'cmp r0,#0xff'
SPAWN_CALL = 0x0807443C                 # 'bl fn 0x080722A8'
ENTITY_SPAWN = 0x08080E30               # object-type spawn entry
ENTITY_SPAWN_TBL = 0x08080E44           # 'ldr r1,[pc]' -> 0x0853F310
DESCRIPTOR_FN = 0x08080B08              # reads 0x0853F140 / 0x0853F298
DESCRIPTOR_TBL = 0x08080B12             # 'ldr r5,[pc]' -> 0x0853F140
REMAP_TBL = 0x08080B2C                  # 'ldr r1,[pc]' -> 0x0853F298
REMAP_DECISION = 0x08080B3C
OBJ_TYPE_TBL = 0x08080E44

PRESS_FRAMES = 8
SETTLE_FRAMES = 120
KEYS = (0x001, 0x002, 0x008, 0x040, 0x080, 0x020, 0x010)

HIT_RE = re.compile(r"(?:Hit breakpoint|Hit watchpoint)\s+#?(\d+)\s+at\s+(0x[0-9a-fA-F]+)")


class Probe(_BaseProbe):
    def registers(self) -> dict:
        raw = parse_status(self.send("status"))
        out = {f"r{i}": raw.get(f"r{i}", 0) for i in range(13)}
        out["sp"] = raw.get("r13", 0)
        out["lr"] = raw.get("r14", 0)
        out["pc"] = raw.get("r15", 0)
        return out


def arm(probe: Probe, address: int) -> int | None:
    for line in probe.send(f"b {address:#x}"):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def hits_in(output: list[str]) -> list[tuple[int, int]]:
    out = []
    for line in output:
        m = HIT_RE.search(line)
        if m:
            out.append((int(m.group(1)), int(m.group(2), 16)))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--state-dir", type=pathlib.Path, default=STATE_DIR)
    ap.add_argument("--groups", default="0,1,2,3,4,5,6,7,8,9")
    ap.add_argument("--presses", type=int, default=30)
    ap.add_argument("--gate-value", type=lambda x: int(x, 0), default=0xFF)
    ap.add_argument("--no-force", action="store_true",
                    help="only report, do not patch the gate byte")
    ap.add_argument("--clear-battle-flag", action="store_true",
                    help="also clear the 'battle still running' byte at "
                         "0x03005D44 so the wrapper's wait loop exits")
    ap.add_argument("--ctrl0", type=int, default=None,
                    help="force ctrl[0] (0x02026804) to this value; "
                         "ctrl[0] != 0 makes the wrapper take the branch that "
                         "reaches the item/skill readers and the entity spawn")
    ap.add_argument("--sites", default=None,
                    help="comma separated address list to watch instead of "
                         "the default checkpoint set")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    groups = []
    for part in args.groups.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            groups.extend(range(int(lo), int(hi) + 1))
        else:
            groups.append(int(part))

    sites = [GATE_SITE, GATE_CMP, SPAWN_CALL, ENTITY_SPAWN, ENTITY_SPAWN_TBL,
             DESCRIPTOR_FN, DESCRIPTOR_TBL, REMAP_TBL, REMAP_DECISION]
    # checkpoints inside the battle wrapper, to see how far the flow gets
    sites += [0x080732B4, 0x080736DC, 0x08073780, 0x08073786, 0x080737B8,
              0x080737C8, 0x080737D0, 0x08073812, 0x08073938, 0x08074200,
              0x08074300, 0x08074908, 0x08074918,
              # the wait loop inside fn 0x0807504E: 'bl fn 0x08064A48'
              0x08075076, 0x08075080,
              # the item/skill readers the battle wrapper calls
              0x0807425A, 0x0807434E, 0x08074192, 0x08074836,
              # the story VM result read that decides "battle or event chain"
              VM_RESULT_SITE, 0x0808A572, 0x0808A580]
    if args.sites:
        wanted = {int(s, 0) for s in args.sites.split(",")}
        sites = [s for s in sites if s in wanted] or sorted(wanted)
    probe = Probe(args.exe, args.rom, timeout=1800)
    report: dict = {"groups": [], "gate_byte": f"0x{GATE_BYTE:08X}"}
    try:
        state = args.state_dir / "battle.ss9"
        for group in groups:
            probe.send(f"load {state}")
            armed: dict[int, int] = {}
            for addr in sites:
                ident = arm(probe, addr)
                if ident is not None:
                    armed[ident] = addr
            probe.send(f"poke 0x{SCENE_BYTE:08X} {group}")
            probe.send(f"poke 0x{SUBCFG_BYTE:08X} 0")
            probe.send(f"poke16 0x{PHASE_WORD:08X} {PHASE_BATTLE}")
            if not args.no_force:
                # pre-set both gates: ctrl[0] == 0 keeps the wrapper on the
                # "start the battle" path, ctrl[0xCD] == 0xFF is the value the
                # spawn branch tests for.
                probe.send(f"poke 0x{BATTLE_CTRL:08X} 0")
                probe.send(f"poke 0x{GATE_BYTE:08X} {args.gate_value}")
                # the mode byte that makes the event switch pick the
                # 0x4080 case (items reader + the 0x6000 spawn dispatch)
                probe.send(f"poke 0x{MODE_BYTE:08X} 1")
            entry: dict = {"group": group, "fired": [], "hits": [],
                           "forced": False, "gate_before": None}
            for step in range(args.presses):
                key = KEYS[step % len(KEYS)]
                if args.clear_battle_flag:
                    probe.send(f"poke 0x{BATTLE_ACTIVE_BYTE:08X} 0")
                if args.ctrl0 is not None:
                    probe.send(f"poke 0x{BATTLE_CTRL:08X} {args.ctrl0 & 0xFF}")
                if not args.no_force:
                    probe.send(f"poke 0x{MODE_BYTE:08X} 1")
                    probe.send(f"poke 0x{GATE_BYTE:08X} {args.gate_value}")
                out = probe.send(f"frames {PRESS_FRAMES} {key:#05x}")
                found = hits_in(out)
                if not found:
                    out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
                    found = hits_in(out)
                for ident, addr in found:
                    if ident not in armed:
                        continue
                    regs = probe.registers()
                    entry["fired"].append(f"0x{addr:08X}")
                    if addr == GATE_SITE:
                        raw = probe.read_bytes(GATE_BYTE, 1)
                        entry["gate_before"] = raw[0] if raw else None
                        if not args.no_force:
                            probe.send(f"poke 0x{GATE_BYTE:08X} {args.gate_value}")
                            entry["forced"] = True
                    if addr in (0x08075076, 0x08073726, 0x0807371E) \
                            and args.clear_battle_flag:
                        # we are inside the "has the battle finished?" wait
                        # loop -- clear the flag so the loop exits and the
                        # wrapper continues into the post-battle code.
                        probe.send(f"poke 0x{BATTLE_ACTIVE_BYTE:08X} 0")
                        entry["forced"] = True
                    if addr == VM_RESULT_SITE and args.ctrl0 is not None:
                        # the story VM has just run: clear the flag it set so
                        # the wrapper takes the event-chain branch.
                        probe.send(f"poke 0x{STORY_CONFIG2:08X} 0")
                        entry["forced"] = True
                    if addr in (DESCRIPTOR_TBL, REMAP_TBL, REMAP_DECISION,
                                ENTITY_SPAWN_TBL, DESCRIPTOR_FN, ENTITY_SPAWN):
                        entry["hits"].append({
                            "at": f"0x{addr:08X}",
                            "regs": {k: f"0x{v:08X}" for k, v in regs.items()},
                        })
                    probe.send("next")
            report["groups"].append(entry)
            print(f"group {group:3d}: gate_before={entry['gate_before']} "
                  f"forced={entry['forced']} fired={entry['fired']}")
            sys.stdout.flush()
    finally:
        probe.close()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
