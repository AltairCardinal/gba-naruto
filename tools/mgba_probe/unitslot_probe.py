#!/usr/bin/env python3
"""Read (and optionally force) the battle unit slot field that gates the
callback-table dispatch.

`fn 0x0806DF88` (called unconditionally from the battle wrapper `fn 0x080732B4`
at `0x080736DE`) walks the 12 battle unit slots.  For every occupied slot it
only calls `fn 0x0806DE18` -- the function that eventually reaches the
`0x0853E698` handler table -- when

    unit[0x0C] <= 9        (a u16 compare at 0x0806DFE6)
    unit[0xBE] == 0        (a u8 compare at 0x0806DFE0)
    unit[0xC0] & 1 == side (a u32 compare at 0x0806DFC0)

This tool stops right before that loop, dumps the fields, and can rewrite
`unit[0x0C]` so the game's own code takes the branch.

Usage:
    python tools/mgba_probe/unitslot_probe.py rom/base.gba --groups 0
    python tools/mgba_probe/unitslot_probe.py rom/base.gba --groups 0 --force
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

UNIT_ARRAY = 0x020240C0
UNIT_STRIDE = 0x1D4
UNIT_SLOTS = 12
CTRL_SIDE = 0x0202680E       # ctrl[10] -- the side byte the gate compares against

GATE_SITE = 0x080736DC        # 'ldrb r0,[r4,#2]' right before fn 0x0806DF88
UNIT_SLOT_SITE = 0x0806DFAE   # 'ldrb r0,[r4]' -- the per-slot gate check
UNIT_DISPATCH = 0x0806DF1E    # 'bl fn 0x0807AB34' inside fn 0x0806DE18
HANDLER_FN = 0x0807F414       # the handler-table dispatcher
HANDLER_DECISION = 0x0807F942
MAP_EVENTS = 0x0807AA8C

# the ROM callback tables and the instructions that read them
CALLBACK_SITES = {
    0x0807F108: "fonts 0x0853E596",
    0x0807EEA8: "glyph metrics 0x0853E328",
    0x0807FD36: "handler table 0x0853E698",
    0x0807FE62: "object types 0x0853EF30",
    0x0807FE80: "entity descriptors 0x0859911C",
    0x08080B12: "object descriptors 0x0853F140",
    0x08080B32: "unit slot remap 0x0853F298",
    0x08080E44: "spawn jump table 0x0853F310",
    0x080806BC: "sprite frame descriptors 0x0853EE98",
    0x0806DDD6: "character perks 0x085459C8",
    # 2026-10-22: the still-open structures' readers.
    0x0807F93C: "handler index byte read (0x0853E698 entry select)",
    0x0806D91A: "items / skills 0x08545BE4",
    0x0807B220: "resource pointers 0x08596F0C",
    0x08081350: "mechanism effects 0x0808136C",
    0x080806BA: "sprite frame descriptors 0x0853EE98 (reader)",
    0x0808077E: "sprite frame descriptors 0x0853EE98 (reader B)",
    0x0808082E: "sprite frame descriptors 0x0853EE98 (reader C)",
    0x08073688: "story battle: calls the level-object processor",
    0x08081CB4: "level-object processor: calls the items reader",
    # 2026-10-22: the resource pointer table's reader.  `fn 0x0807F064`
    # (the fonts reader, entry 159's B slot) calls `fn 0x0807C5E8`
    # (0x0807F0D6 / 0x0807F10C), which calls `fn 0x0807B8B8`, which calls
    # `fn 0x0807AE04(0, 7, 0x10)` -- and case 7 is the one that reads
    # the table 0x08596F0C at 0x0807B220.
    0x0807C5E8: "fn 0x0807C5E8 (calls fn 0x0807B8B8)",
    0x0807C3D6: "fn 0x0807B8B8: calls the resource reader (arg1 = 7)",
    0x0807B220: "RESOURCE reader fn 0x0807AE04 (table 0x08596F0C)",
    0x0807B8D4: "fn 0x0807B8B8: loads the scene byte",
}

# the level object list (32 records of 16 bytes)
OBJ_LIST = 0x02026604
OBJ_STRIDE = 16

# the table each dispatch point reads, so the census can dump it
CALLBACK_TABLE = {
    0x0807F108: 0x0853E596,
    0x0807EEA8: 0x0853E328,
    0x0807FD36: 0x0853E698,
    0x0807FE62: 0x0853EF30,
    0x0807FE80: 0x0859911C,
    0x08080B12: 0x0853F140,
    0x08080B32: 0x0853F298,
    0x08080E44: 0x0853F310,
    0x080806BC: 0x0853EE98,
    0x0806DDD6: 0x085459C8,
    0x0806D91A: 0x08545BE4,
    0x0807B220: 0x08596F0C,
    0x08081350: 0x0808136C,
    0x080806BA: 0x0853EE98,
    0x0808077E: 0x0853EE98,
    0x0808082E: 0x0853EE98,
    0x0807B220: 0x08596F0C,
}

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


def dump_units(probe: Probe) -> list[dict]:
    raw = probe.read_bytes(UNIT_ARRAY, UNIT_SLOTS * UNIT_STRIDE)
    out = []
    for i in range(UNIT_SLOTS):
        base = i * UNIT_STRIDE
        if len(raw) < base + 0xC2:
            break
        slot = raw[base]
        out.append({
            "slot": i,
            "occupied": bool(slot),
            "u8_00": slot,
            "u16_0c": struct.unpack_from("<H", raw, base + 0x0C)[0],
            "u16_0e": struct.unpack_from("<H", raw, base + 0x0E)[0],
            "u8_be": raw[base + 0xBE],
            "u32_c0": struct.unpack_from("<I", raw, base + 0xC0)[0],
            "u8_c4": raw[base + 0xC4],
            "u8_c5": raw[base + 0xC5],
        })
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--state-dir", type=pathlib.Path, default=STATE_DIR)
    ap.add_argument("--groups", default="0")
    ap.add_argument("--presses", type=int, default=14)
    ap.add_argument("--intro", type=int, default=40,
                    help="how many press/release rounds to let the battle "
                         "intro play out (all breakpoints off) before the "
                         "watch sites are armed again")
    ap.add_argument("--force", action="store_true",
                    help="rewrite unit[0x0C] to 0 so the game's own code "
                         "takes the dispatch branch")
    ap.add_argument("--force-value", type=int, default=0)
    ap.add_argument("--force-dispatch", action="store_true",
                    help="open the callback-dispatch gate the way the game "
                         "would: put a character id into the unit slot, give "
                         "it the one character-perk entry whose class byte is "
                         "0x1D (index 24 of 0x085459C8), and clear the side "
                         "byte ctrl[10] so that `unit[0xC0] & 1` matches "
                         "it.  The gate is structurally dead in a natural "
                         "battle, so this is the only way to make the ROM "
                         "callback tables execute their own reader code.")
    ap.add_argument("--force-id", type=int, default=1)
    ap.add_argument("--perk-index", type=int, default=24,
                    help="index into 0x085459C8 whose class byte is 0x1D")
    ap.add_argument("--force-occupy", type=int, default=None,
                    help="(legacy) put this character id into the unit slot "
                         "the gate is inspecting")
    ap.add_argument("--watch-callbacks", action="store_true",
                    help="also break on every known callback-table dispatch "
                         "point and record the table bytes it reads")
    ap.add_argument("--index-byte", type=int, default=None,
                    help="force the handler-table index byte (read at "
                         "0x0807F93C) to this value; entry N selects "
                         "(handler_A, handler_B) at 0x0853E698 + N*8 -- "
                         "entry 159's B slot is fn 0x0807F064, the reader of "
                         "the glyph width table 0x0853E596")
    ap.add_argument("--index-sweep", type=int, default=None,
                    help="cycle the handler-table index byte through "
                         "0..N-1 (one battle run exercises every entry)")
    ap.add_argument("--write-type1-object", action="store_true",
                    help="write a synthetic type-1 level object right before "
                         "the level-object processor runs, so the items "
                         "reader fn 0x0806D910 is reached")
    ap.add_argument("--item-id", type=int, default=1,
                    help="the item id stored in the synthetic object's +4")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    groups = []
    for part in args.groups.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            groups.extend(range(int(lo), int(hi) + 1))
        else:
            groups.append(int(part))

    probe = Probe(args.exe, args.rom, timeout=1800)
    report: dict = {"groups": []}
    watch_list = [GATE_SITE, UNIT_SLOT_SITE, UNIT_DISPATCH, HANDLER_FN,
                  HANDLER_DECISION, MAP_EVENTS]
    if args.watch_callbacks:
        watch_list += list(CALLBACK_SITES)
    try:
        armed = {i for i in (arm(probe, a) for a in watch_list) if i is not None}
        state = args.state_dir / "battle.ss9"
        for group in groups:
            index_turn = 0
            probe.send(f"load {state}")
            for ident in list(armed):
                probe.send(f"delete {ident}")
            armed = {i for i in (arm(probe, a) for a in watch_list)
                     if i is not None}
            probe.send(f"poke 0x{SCENE_BYTE:08X} {group}")
            probe.send(f"poke 0x{SUBCFG_BYTE:08X} 0")
            probe.send(f"poke16 0x{PHASE_WORD:08X} {PHASE_BATTLE}")

            # --- let the battle intro play out ---------------------------
            # Breakpoints abort the frame they hit, so leaving them armed
            # during the intro starves the game: the intro never advances
            # and fn 0x0808A588 never instantiates the units.  The L4
            # battle matrix uses the same recipe -- all breakpoints off,
            # then the press-edge recipe (press 8 frames, release 120).
            for ident in list(armed):
                probe.send(f"delete {ident}")
            armed = set()
            for _ in range(args.intro):
                probe.send(f"frames 8 0x001")
                probe.send(f"frames 120 0x000")
                if any(dump_units(probe)):
                    break
            for ident in (arm(probe, a) for a in watch_list):
                if ident is not None:
                    armed.add(ident)
            entry: dict = {"group": group, "units": None, "fired": [],
                           "forced": False, "gate_readings": [],
                           "callback_hits": [], "intro_units":
                           [u["u8_00"] for u in dump_units(probe)]}
            for step in range(args.presses):
                key = KEYS[step % len(KEYS)]
                out = probe.send(f"frames {PRESS_FRAMES} {key:#05x}")
                found = hits_in(out)
                # The release is *not* a fallback: the game only reacts to a
                # press edge, so the key has to go up again between presses.
                # Releasing only when no breakpoint fired (the old behaviour)
                # meant the key stayed down forever, the battle intro never
                # advanced and the unit slots stayed empty -- which is what
                # made the callback dispatch look unreachable.
                out = probe.send(f"frames {SETTLE_FRAMES} 0x000")
                found = found + hits_in(out)
                for ident, addr in found:
                    if ident not in armed:
                        continue
                    entry["fired"].append(f"0x{addr:08X}")
                    if addr in CALLBACK_SITES:
                        regs = probe.registers()
                        hit = {
                            "at": f"0x{addr:08X}",
                            "what": CALLBACK_SITES[addr],
                            "r0": f"0x{regs.get('r0', 0):08X}",
                            "r1": f"0x{regs.get('r1', 0):08X}",
                            "r2": f"0x{regs.get('r2', 0):08X}",
                            "r3": f"0x{regs.get('r3', 0):08X}",
                            "r4": f"0x{regs.get('r4', 0):08X}",
                            "r5": f"0x{regs.get('r5', 0):08X}",
                            "r6": f"0x{regs.get('r6', 0):08X}",
                            "r7": f"0x{regs.get('r7', 0):08X}",
                        }
                        base = CALLBACK_TABLE.get(addr)
                        if base:
                            hit["table_base"] = f"0x{base:08X}"
                            hit["table_dump"] = probe.read_bytes(
                                base, 48).hex(" ")
                        entry["callback_hits"].append(hit)
                    if addr == GATE_SITE and args.force_dispatch:
                        # The gate is `fn 0x0806DF88`, called with the side
                        # byte ctrl[10] (0x0202680E).  It only dispatches
                        # when, for one slot:
                        #   unit[0]        != 0
                        #   unit[0xC0] & 1 == ctrl[10]
                        #   unit[0xBE]     == 0
                        #   unit[0x0C]     <= 9
                        # and `fn 0x0806DDA4` resolves the unit's perk
                        # (unit[0x50] / unit[0x51]) against 0x085459C8,
                        # whose class byte must be 0x1D.  Exactly one entry
                        # has that class: index 24.
                        # ctrl[10] is toggled by the game every frame
                        # (0x080736B8) and reads 0x0E / 0x0F during a
                        # battle, so `unit[0xC0] & 1` can never match it.
                        # Writing ctrl[10] = 0 here (before the `ldrb` that
                        # loads it) makes the comparison the game performs
                        # succeed.
                        for slot in range(1, UNIT_SLOTS):
                            base = UNIT_ARRAY + slot * UNIT_STRIDE
                            probe.send(f"poke 0x{base:08X} {args.force_id & 0xFF}")
                            probe.send(f"poke 0x{base + 0x50:08X} "
                                       f"{args.perk_index & 0xFF}")
                            probe.send(f"poke 0x{base + 0x51:08X} 1")
                            probe.send(f"poke 0x{base + 0xBE:08X} 0")
                            probe.send(f"poke16 0x{base + 0x0C:08X} 0")
                            probe.send(f"poke16 0x{base + 0xC0:08X} 0")
                        probe.send(f"poke 0x{CTRL_SIDE:08X} 0")
                        entry.setdefault("dispatch_forced", []).append(
                            f"perk_index={args.perk_index} id={args.force_id}")
                    if addr == UNIT_SLOT_SITE and args.force_occupy is not None:
                        # The gate checks `unit[0] != 0` right after this
                        # `ldrb`, so writing the slot here is seen by the
                        # game itself.  `sl` (r10) carries the side the
                        # battle passes in, and the gate also compares
                        # `unit[0xC0] & 1` against it.
                        regs = probe.registers()
                        side = regs.get("r10", 0) & 1
                        base = UNIT_ARRAY
                        probe.send(f"poke 0x{base:08X} {args.force_occupy & 0xFF}")
                        probe.send(f"poke16 0x{base + 0x0C:08X} 0")
                        probe.send(f"poke 0x{base + 0xBE:08X} 0")
                        probe.send(f"poke16 0x{base + 0xC0:08X} {side}")
                        entry.setdefault("occupied_writes", []).append(
                            f"slot0 id={args.force_occupy} side={side}")
                    if addr == 0x0807F93C:
                        # `ldrb r0,[r0]` -- r0 already holds the address of
                        # the index byte (base + 0x770).  The byte itself is
                        # read here, and the dispatch that follows uses it to
                        # select the 8-byte entry in the table 0x0853E698.
                        regs = probe.registers()
                        where = regs.get("r0", 0)
                        raw = probe.read_bytes(where, 1)
                        entry.setdefault("index_byte_reads", []).append(
                            f"addr=0x{where:08X} value="
                            f"0x{raw[0]:02X}" if raw else "value=?")
                        want = args.index_byte
                        if args.index_sweep:
                            # cycle through every entry of the table inside
                            # a single battle: the dispatch reads the byte
                            # again every frame.
                            want = (args.index_sweep + index_turn) % 256
                            index_turn += 1
                        if want is not None:
                            # Writing it here is seen by the dispatch that
                            # follows, so the game itself selects the entry
                            # we want.
                            probe.send(f"poke 0x{where:08X} {want & 0xFF}")
                            entry.setdefault("index_byte_writes", []).append(
                                f"addr=0x{where:08X} value={want & 0xFF}")
                    if addr == 0x0807B8D4 and args.index_byte is not None:
                        # `fn 0x0807B8B8` skips its whole body when the byte
                        # it reads is > 0xE3:
                        #
                        #   0x0807B8D4: ldrb r0, [r0]
                        #   0x0807B8D6: cmp  r0, #0xE3
                        #   0x0807B8D8: bhi  0x0807B8E4
                        #
                        # the breakpoint fires before the load, so r0 holds
                        # the byte's address: clamping it here is seen by
                        # the next instruction.
                        where = regs.get("r0", 0)
                        raw = probe.read_bytes(where, 1)
                        if raw and raw[0] > 0xE3:
                            probe.send(f"poke 0x{where:08X} 0xE3")
                            entry.setdefault("scene_byte_writes", []).append(
                                f"0x{where:08X}: 0x{raw[0]:02X} -> 0xE3")
                            print(f"    [scene byte 0x{where:08X}: "
                                  f"0x{raw[0]:02X} -> 0xE3]")
                    if addr == 0x08073688 and args.write_type1_object:
                        # `bl fn 0x08081B70` is about to run.  That function
                        # walks the level object list and dispatches on the
                        # type byte; a **type 1** record drives it into the
                        # branch that calls the reader `fn 0x0806D910`.
                        #
                        #   0x08081C36: ldrh r0, [r1, #6]
                        #   0x08081C38: subs r0, #1
                        #   0x08081C44: cmp  r0, #0   -> only if it was 1
                        #
                        # so the record needs +6 == 1; +4 is the item id the
                        # reader indexes with (`id & 0x7F`).
                        base = OBJ_LIST + 1 * OBJ_STRIDE
                        probe.send(f"poke 0x{base:08X} 0x01")
                        probe.send(f"poke 0x{base + 1:08X} 0x00")
                        probe.send(f"poke 0x{base + 2:08X} 0x00")
                        probe.send(f"poke 0x{base + 4:08X} "
                                   f"{args.item_id & 0xFF}")
                        probe.send(f"poke 0x{base + 5:08X} 0x00")
                        probe.send(f"poke16 0x{base + 6:08X} 0x0001")
                        probe.send(f"poke16 0x{base + 8:08X} 0x0000")
                        probe.send(f"poke16 0x{base + 10:08X} 0x0000")
                        probe.send(f"poke16 0x{base + 12:08X} 0x0000")
                        entry.setdefault("type1_objects", []).append(
                            f"0x{base:08X} id={args.item_id}")
                        print(f"    [wrote a type-1 object at 0x{base:08X}, "
                              f"id={args.item_id}]")
                    if addr == GATE_SITE:
                        units = dump_units(probe)
                        occupied = [u for u in units if u["occupied"]]
                        # `fn 0x0806DF88` is called once per battle frame, so
                        # the slot state has to be watched over time: the
                        # dispatch only opens once a slot is really filled.
                        entry["gate_readings"].append({
                            "step": step,
                            "occupied": len(occupied),
                            "slots": [{"slot": u["slot"], "id": u["u8_00"],
                                       "0x0C": u["u16_0c"],
                                       "0xBE": u["u8_be"],
                                       "0xC0": u["u32_c0"]}
                                      for u in occupied],
                        })
                        if entry["units"] is None:
                            entry["units"] = units
                        if args.force:
                            for u in units:
                                if u["occupied"]:
                                    addr_w = UNIT_ARRAY + u["slot"] * UNIT_STRIDE + 0x0C
                                    probe.send(f"poke16 0x{addr_w:08X} "
                                               f"{args.force_value}")
                            entry["forced"] = True
                    probe.send("next")
            report["groups"].append(entry)
    finally:
        probe.close()

    for g in report["groups"]:
        print(f"group {g['group']}: fired={sorted(set(g['fired']))}")
        for w in g.get("occupied_writes", []):
            print(f"   occupied write: {w}")
        for h in g.get("callback_hits", []):
            print(f"   CALLBACK {h['at']} {h['what']} "
                  f"r0={h['r0']} r1={h['r1']} r2={h['r2']} r3={h['r3']}")
        for r in g.get("gate_readings", []):
            print(f"   gate step {r['step']:3d}: {r['occupied']} occupied "
                  f"{r['slots']}")
        for u in g["units"] or []:
            if u["occupied"]:
                print(f"   slot {u['slot']:2d} 0x00={u['u8_00']:#04x} "
                      f"0x0C={u['u16_0c']} 0x0E={u['u16_0e']} "
                      f"0xBE={u['u8_be']:#04x} 0xC0={u['u32_c0']:#010x} "
                      f"(side={u['u32_c0'] & 1})")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
