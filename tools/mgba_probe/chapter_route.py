#!/usr/bin/env python3
"""Try to reach the chapter (level) mode, where the callback tables live.

The story VM opcode ``0x1A <scene> <flag>`` sets ``state[0x16] = scene`` and
``state[0x18] = flag + 1``.  ``flag == 0`` makes ``state[0x18] == 1``, and
that is the marker the state machine uses to run the **chapter init**
(``fn 0x0808F618``) -> ``fn 0x08068DE4`` (sets IWRAM ``0x03000075 = 1``)
-> ``fn 0x080732B4``, the 7.5 KB function that contains the whole event-id
switch -- and, at the end of the chain, the readers of ``0x0853E698``,
``0x0853E596``, ``0x08545BE4``, ``0x0853F140`` and ``0x0853F298``.

Scenes whose script uses ``0x1A <scene> 0``:

    scene  1 -> chapter scene  2      scene 50 -> chapter scene 31
    scene  3 -> chapter scene 51      scene 51 -> chapter scenes 5, 50
    scene 52 -> chapter scene 24      scene 53 -> chapter scene 50

Usage:
    python tools/mgba_probe/chapter_route.py rom/base.gba --scene 1 --keys A,A,A,DOWN,A
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

DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"

WATCH = {
    0x08097AC4: "SANITY op 0x0B condition read (r0 = id)",
    0x08097ACA: "SANITY op 0x0B condition value (r0 = value)",
    0x08097C6C: "VM opcode 0x1A (next-scene)",
    0x0808F654: "scene runner / chapter dispatch",
    0x0808F618: "chapter init",
    0x08068DE4: "chapter init wrapper (0x03000075 = 1)",
    0x080732B4: "chapter / battle control",
    0x08074190: "event case 0x4080 (items reader)",
    0x0807443C: "event case 0x6000 (entity spawn)",
    0x08080E30: "object-type spawn",
    0x08080B08: "object descriptor reader",
    0x08080B12: "reader of 0x0853F140",
    0x08080B2C: "reader of 0x0853F298",
    0x08070DF8: "items/skills reader",
    0x080851F8: "items/skills reader B",
    0x0800B7FF: "SCENE 1 menu (Kato / do not know)",
    0x0800BFBC: "SCENE 1 chapter handoff node (1A 02 00)",
    0x0800BBF4: "SCENE 1 jump target of the 'know Kato' choice",
    0x080978DC: "VM opcode 0x01 (dialogue)",
    0x08097992: "VM opcode 0x05 (menu)",
    0x08097958: "VM opcode 0x04",
    0x08095F1C: "menu UI: about to read the chosen item",
    0x08095F76: "menu builder: cursor reset (patch it here)",
    0x08095FBA: "menu builder: cursor index written",
    0x0809602C: "menu poll: key state read",
    0x080960BE: "menu UI: about to load the finished flag",
    0x08096088: "menu UI: A accepted (writes the answer)",
    0x08096090: "menu UI: writes the answer row",
    0x080979D6: "VM opcode 0x06 (branch on the menu answer)",
    0x0808F8DC: "state machine: phase 0x30 (run a scene script)",
    0x0808F904: "state machine: reads state[0x18]",
    0x0808F91E: "state machine: state[0x18]==1 -> phase 0x100",
    0x0808F928: "state machine: phase 0x100 -> chapter setup",
    0x08088F10: "chapter setup (fn)",
    0x0808F92E: "state machine: phase 0x110 -> full battle entry",
    0x0808F952: "state machine: calls fn 0x080732B4",
    0x080732B4: "battle / event switch",
    0x08068DE4: "chapter mode flag 0x03000075 = 1",
    0x08075184: "pre-battle",
    0x0808A490: "battle running flag",
    # --- the mission panel (fn 0x080884DC) -------------------------------
    0x080884DC: "mission panel (fn)",
    0x0808857C: "mission panel: waits for A",
    0x080885BA: "mission panel: opens its menu",
    0x080885C0: "mission panel: loads the finished flag",
    0x08088622: "mission panel: wait loop",
    0x08088F9A: "chapter setup: asks the mission panel",
    0x08088FF2: "chapter setup: r4 == 0x10",
    0x08089008: "chapter setup: r4 == 0x20 -> battle entry",
    0x0807509C: "LEVEL MODE battle setup (the callback tables live here)",
    0x0808F5CA: "story dispatcher: story_config[0] (0x020311ED)",
    0x08075184: "pre-battle",
    # --- the mission panel's table readers -------------------------------
    0x08088500: "mission index table 0x08348DAC",
    0x0808850C: "mission title table 0x0859AA5C",
    0x0808851C: "mission description table 0x0859D214",
    0x0808852E: "mission hint table 0x0859E920",
}

# the table each of those readers dereferences, so the probe can dump it
MISSION_TABLES = {
    0x08088500: 0x08348DAC,
    0x0808850C: 0x0859AA5C,
    0x0808851C: 0x0859D214,
    0x0808852E: 0x0859E920,
}

# Chatty sites: the VM fetches every opcode, so watching them makes the game
# advance one instruction per hit.  Only enable them for tracing.
TRACE = {
    0x080977D8: "VM opcode fetch",
    0x080970A0: "flag reader",
    0x080970AA: "flag byte read",
    0x080970AE: "flag step",
    0x080970B2: "flag step",
    0x080970B6: "flag step",
    0x0808F544: "story dispatcher",
    0x080977B8: "story VM entry",
    0x08009F2E: "scene 1 BEFORE root entry",
    0x0800B158: "scene 1 mission dialogue",
}

STATE = 0x020311D4
BRANCH_BYTE = STATE + 0x18      # 0x020311EC -- the story_branch marker
# `fn 0x080970A0(id)` reads the story **condition bitfield** at WRAM
# 0x020314F0: condition id n lives in bit (n & 7) >> 1 of byte (n >> 3).
# So condition 1 == bit 0 of byte 0x020314F0.
COND_BASE = 0x020314F0
# The menu UI (`fn 0x08095F58`) stores the player's choice in the object at
# 0x0200A894; the choice itself is the u32 at +4, i.e. 0x0200A898.
CHOICE_ADDR = 0x0200A898
# The menu builder `fn 0x08095F58` keeps the cursor row in the message-box
# object at 0x03005E50, offset +0x14 (reset to 0 on creation, moved by the
# cursor keys).  Writing it right after the reset makes the menu answer with
# the second row.
MSGOBJ = 0x03005E50
CURSOR_ADDR = MSGOBJ + 0x14
MENU_RESET_SITE = 0x08095F76
# The menu builder stores the *cursor index* (u32) at 0x0200A890, written by
# `fn 0x080626B4` right after the rows are built.  Overwriting it there makes
# the menu answer with the row we want.
CURSOR_INDEX_ADDR = 0x0200A890
CURSOR_INDEX_SITE = 0x08095FBA
# The menu's key state is a u16 at 0x0200A884 (a copy of KEYINPUT).  The
# cursor-move logic polls it, so writing the DOWN bit there emulates a real
# cursor move.
KEYSTATE_ADDR = 0x0200A884
KEYSTATE_SITE = 0x0809602C
KEY_DOWN = 0x0080

# --- the choice menu's answer channel -------------------------------------
# `fn 0x08095F58` (the menu UI) writes the answer itself:
#   0x0809608A  0x0200A882 = 1          "the menu is finished"
#   0x08096090  0x0200A880 = <row>      the selected row
# and the VM opcode 0x06 (`0x080979D6`) reads 0x0200A880 back and computes
# the branch target as `cursor + 4*row + 1`.
#
# Scene 1's script has the opcode at 0x0800B855, so the answer table is
#   0x0800B856 -> 0x0800B899   (row 0: "do not know Kato")
#   0x0800B85A -> 0x0800B849   (row 1: "know Kato"  -> the chapter hand-off)
# Writing row 1 is therefore the same thing the A button would do, and it is
# the only way in while the key update is not running inside the modal menu
# loop (see notes/evidence/menu-answer-channel-20261021.md).
ANSWER_ADDR = 0x0200A880
FINISHED_ADDR = 0x0200A882
ANSWER_LOAD_SITE = 0x080960BE     # the `ldrb` of the finished flag is next

# --- the mission panel's own menu ------------------------------------------
# `fn 0x080884DC` (the mission panel) shows the mission and then opens a
# *second* menu -- built by a different UI, but it uses the same answer
# channel:
#   0x080885C0: r5 = 0x0200A882
#   0x080885C2: ldrb r0,[r5]        ; finished flag
#   0x080885C8: r4 = 0x0200A880
#   0x080885CA: ldrb r1,[r4]        ; the answer
#   0x080885CC: mov  r8, r1         ; returned to the caller
# The caller `fn 0x08088F10` maps the answer: 0 -> keep waiting, 1 -> fight,
# 2 -> cancel, 3 -> other.  So answer 1 is "start the battle".
MISSION_ANSWER_SITE = 0x080885C0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--scene", type=int, default=1)
    ap.add_argument("--keys", default="A,A,A,DOWN,A",
                    help="comma separated key names, cycled")
    ap.add_argument("--presses", type=int, default=24)
    ap.add_argument("--branch", type=int, default=0,
                    help="value to write to state[0x18] before dispatching; "
                         "0 selects the BEFORE root (the one that contains the "
                         "chapter handoff), non-zero the AFTER root")
    ap.add_argument("--cond", type=lambda x: int(x, 0), default=0,
                    help="bitmask to write into the condition byte at "
                         "0x020314F0 (bit 0 = condition 1, bit 2 = "
                         "condition 2, ...)")
    ap.add_argument("--cond-addr", type=lambda x: int(x, 0), default=0x08009F2E,
                    help="the VM cursor at which the condition bits are "
                         "written (the scene's `0x0B` branch node); the game "
                         "clears the condition array on scene start, so the "
                         "bits have to be set at the last moment")
    ap.add_argument("--cond-span", type=int, default=8,
                    help="how many bytes around COND_BASE to fill with 0xFF "
                         "when patching (the exact base is being verified)")
    ap.add_argument("--cond-fill", type=lambda x: int(x, 0), default=0,
                    help="fill this many bytes with 0xFF starting at "
                         "COND_BASE (used to locate the flag array "
                         "empirically)")
    ap.add_argument("--cond-fill-start", type=lambda x: int(x, 0), default=0,
                    help="start address for --cond-fill")
    ap.add_argument("--trace", action="store_true",
                    help="also watch the chatty VM trace sites")
    ap.add_argument("--choice", type=int, default=None,
                    help="menu choice index to force (written to "
                         "0x0200A898 just before the menu UI reads it)")
    ap.add_argument("--force-row", type=int, default=None,
                    help="answer the choice menu with this row: the answer "
                         "channel 0x0200A880 is set to the row and the "
                         "finished flag 0x0200A882 to 1 at the moment the "
                         "menu asks for it (the same writes the A button "
                         "makes at 0x0809608A/0x08096090)")
    ap.add_argument("--force-mission", type=int, default=None,
                    help="answer the mission panel's menu with this row "
                         "(1 = 'start the battle'); the same answer channel "
                         "0x0200A880 / 0x0200A882 is written at the moment "
                         "the panel asks for it (0x080885C0)")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    ap.add_argument("--save", type=pathlib.Path, default=None,
                    help="write a savestate here once the level mode is "
                         "reached (so a later dispatch census can load it "
                         "instead of replaying the whole story)")
    ap.add_argument("--lean", action="store_true",
                    help="drop the two very chatty watch sites (the dialogue "
                         "handler and the menu text reader); they cost one "
                         "emulator frame each and are not needed to find the "
                         "route")
    args = ap.parse_args(argv)

    names = ["A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN"]
    keys = [KEY_BITS[k.strip().upper()] for k in args.keys.split(",")
            if k.strip().upper() in names]

    harness = Harness(args.exe, pathlib.Path(args.rom))
    report: dict = {"scene": args.scene, "keys": args.keys, "hits": []}
    watch = dict(WATCH)
    if args.lean:
        for drop in (0x08095F1C, 0x080978DC):
            watch.pop(drop, None)
    try:
        if not harness.boot_to_state_machine():
            print("could not park on the state machine", file=sys.stderr)
            return 2
        for addr in list(watch) + (list(TRACE) if args.trace else []):
            harness.arm(addr)
        harness.poke(SCENE_BYTE, args.scene)
        # The story dispatcher picks the BEFORE root (which contains the
        # `1A <scene> 0` chapter handoff) only when state[0x18] == 0.
        harness.poke(BRANCH_BYTE, args.branch & 0xFF)
        if args.cond:
            # set the story condition bits the scene's branch opcodes test
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
            if args.choice is not None and hit == KEYSTATE_SITE \
                    and not report.get("key_injected"):
                # inject one DOWN press into the menu's key state so the
                # cursor really moves to the second row.
                harness.poke(KEYSTATE_ADDR, KEY_DOWN & 0xFF)
                report["key_injected"] = True
                report.setdefault("key_injected_at", []).append(
                    f"0x{regs.get('r6', 0):08X}")
            if args.choice is not None and hit == CURSOR_INDEX_SITE:
                harness.poke(CURSOR_INDEX_ADDR, args.choice & 0xFF)
                report.setdefault("cursor_index_patched", []).append(
                    f"0x{regs.get('r6', 0):08X}")
            if args.choice is not None and hit == MENU_RESET_SITE:
                # the menu builder has just reset the cursor row to 0 --
                # overwrite it so the menu answers with the second row.
                harness.poke(CURSOR_ADDR, args.choice & 0xFF)
                report.setdefault("cursor_patched", []).append(
                    f"0x{regs.get('r6', 0):08X}")
            if args.choice is not None and hit == 0x08095F1C:
                # the menu UI is about to read the chosen item from
                # 0x0200A898 and jump to that branch -- overwrite it so the
                # second option is taken.
                harness.poke(CHOICE_ADDR, args.choice & 0xFF)
                report.setdefault("choice_patched", []).append(
                    f"0x{regs.get('r7', 0):08X}")
            if hit in MISSION_TABLES:
                base = MISSION_TABLES[hit]
                report.setdefault("mission_tables", []).append({
                    "site": f"0x{hit:08X}",
                    "table_base": f"0x{base:08X}",
                    "r0": f"0x{regs.get('r0', 0):08X}",
                    "r4": f"0x{regs.get('r4', 0):08X}",
                    "dump": harness.read(base, 48).hex(" "),
                })
            if args.force_row is not None and hit == ANSWER_LOAD_SITE:
                # the menu UI is about to test the "finished" flag -- answer
                # for it exactly the way the A button would.
                harness.poke(ANSWER_ADDR, args.force_row & 0xFF)
                harness.poke(FINISHED_ADDR, 1)
                report.setdefault("forced_answers", []).append(
                    f"row={args.force_row}")
            if args.force_mission is not None and hit == MISSION_ANSWER_SITE:
                # the mission panel is about to read the finished flag and
                # the answer -- give it the "start the battle" answer.
                harness.poke(ANSWER_ADDR, args.force_mission & 0xFF)
                harness.poke(FINISHED_ADDR, 1)
                report.setdefault("forced_mission", []).append(
                    f"row={args.force_mission}")
            if args.cond and hit == 0x08097AC4:
                # the `0x0B` handler is about to read the condition value --
                # write it right now: the `0x50` event-entry opcode that ran
                # just before cleared the whole condition array.
                if args.cond_fill:
                    start = args.cond_fill_start or (COND_BASE - args.cond_fill // 2)
                    for off in range(args.cond_fill):
                        harness.poke(start + off, 0xFF)
                        if off % 64 == 63:
                            harness.send("status")   # keep the pipe drained
                for off in range(args.cond_span):
                    harness.poke(COND_BASE - args.cond_span + off, 0xFF)
                harness.poke(COND_BASE, args.cond & 0xFF)
                report.setdefault("cond_patched", []).append(
                    f"op0x0B@{regs.get('r7', 0):08X}")
                report.setdefault("cond_bytes", []).append(
                    harness.read(COND_BASE - 4, 10).hex(" "))
            if args.cond and hit == 0x080977D8:
                cursor = regs.get("r7", 0)
                if cursor == args.cond_addr:
                    harness.poke(COND_BASE, args.cond & 0xFF)
                    report.setdefault("cond_patched", []).append(
                        f"0x{cursor:08X}")
            if hit == 0x08097ACA:
                report.setdefault("cond_readback", []).append(
                    harness.read(COND_BASE - 4, 10).hex(" "))
            state = harness.read(STATE, 0x24)
            script = ""
            if hit == 0x080977B8:
                script = f"0x{regs.get('r0', 0):08X}"
            report["hits"].append({
                "at": f"0x{hit:08X}",
                "label": WATCH.get(hit, "?"),
                "script": script,
                "opcode": (f"0x{regs.get('r0', 0) & 0xFF:02X}"
                           if hit == 0x080977D8 else ""),
                "cond_value": (f"{regs.get('r0', 0) >> 16}"
                               if hit == 0x08097ACA else ""),
                "cond_id": (f"{regs.get('r0', 0)}"
                            if hit == 0x08097AC6 else ""),
                "flag_addr": (f"0x{regs.get('r0', 0):08X}"
                              if hit == 0x080970AA else ""),
                "r0r1r2": (f"r0=0x{regs.get('r0', 0):08X} "
                            f"r1=0x{regs.get('r1', 0):08X} "
                            f"r2=0x{regs.get('r2', 0):08X}"
                            if 0x080970AC <= hit <= 0x080970B8 else ""),
                "cursor7": (f"0x{regs.get('r7', 0):08X}"
                            if hit in (0x08097AC4, 0x08097AC6) else ""),
                "cursor": (f"0x{regs.get('r7', 0):08X}"
                           if hit in (0x080977D8, 0x080978DC) else ""),
                "pc": f"0x{regs.get('pc', 0):08X}",
                "scene_byte": f"0x{state[0x16]:02X}" if state else None,
                "branch_byte": f"0x{state[0x18]:02X}" if state else None,
                "phase": f"0x{int.from_bytes(state[0x12:0x14], 'little'):04X}"
                         if state else None,
                # story_config[0] (0x020311ED) and story_branch (0x020311EC)
                "story_config0": f"0x{state[0x19]:02X}" if state else None,
                "story_branch": f"0x{state[0x18]:02X}" if state else None,
            })
            print(json.dumps(report["hits"][-1], ensure_ascii=False))
            phase = int.from_bytes(state[0x12:0x14], "little")
            if args.save is not None and not report.get("saved") \
                    and hit in (0x08075184, 0x0807509C):
                args.save.parent.mkdir(parents=True, exist_ok=True)
                harness.send(f"save {args.save}")
                report["saved"] = str(args.save)
                print(f"saved savestate to {args.save} (before the level "
                      f"battle setup)")
            report.setdefault("phases", []).append(f"0x{phase:04X}")
            harness.send("next")
            harness.rearm()
    finally:
        harness.close()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    fired = sorted({h["at"] for h in report["hits"]})
    print("fired:", ", ".join(fired) if fired else "(none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
