#!/usr/bin/env python3
"""Measure the story-VM choice menu and prove how a menu answer is read.

Why this tool exists
--------------------
The story VM's choice menu is built by ``fn 0x08095F58``.  Static reading of
that function (verified instruction by instruction) gives:

    0x08095F72/74   obj[0x16] = 0, obj[0x14] = 0      (current row, anchor row)
    0x08095FBA      0x0200A890 = <row pointer>          (u32)
    0x08095FBE      0x0200A882 = 0                     ("menu finished" flag)
    0x0809602C      r1 = u16 @ 0x0200A884               (cached key state)
    0x0809602E      r5 = 0x40  -> UP    (move row up)
    0x0809604C      r5 = 0x80  -> DOWN  (move row down)
    0x08096078      r4 = 0x01  -> **A**, read from 0x0300000E (new press)
    0x0809608A      0x0200A882 = 1                      (menu finished)
    0x08096090      **0x0200A880 = current row**        (the ANSWER)
    0x080960C2      if 0x0200A882 != 0 -> leave the loop, bl 0x08062788

and the VM opcode ``0x06`` (``0x080979D6``) reads **0x0200A880** as the
selected index and computes the branch target as ``cursor + 4*index + 1``.

So the answer channel is ``0x0200A880`` -- *not* ``0x0200A898`` (a text-box
slot) and not ``0x0200A890`` (a row pointer).

Why the earlier attempts failed
-------------------------------
``0x0300000E`` is the game's **new-press** mask.  It is written by exactly
one function, ``fn 0x080615E4``, which is called from the main loop
(``0x08061082``).  The menu UI is a *modal internal loop* -- it does not
return to the main loop while the menu is up -- so the question is whether
the key update still runs inside the menu loop.  This tool measures it:
it reads ``0x0300000E`` at the menu poll and reports whether it moves.

If it does not move, the menu can be answered by writing the answer channel
directly (``0x0200A880`` = row, ``0x0200A882`` = 1) at the moment the menu
asks for it -- which is what ``--force-row`` does.

Usage
-----
    python tools/mgba_probe/menu_probe.py rom/base.gba --scene 1 --branch 0 \
        --cond 2 --presses 400
    python tools/mgba_probe/menu_probe.py rom/base.gba --force-row 1 \
        --json build/menu-force.json
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

STATE = 0x020311D4
BRANCH_BYTE = STATE + 0x18
COND_BASE = 0x020314F0

# --- the menu UI, instruction by instruction -------------------------------
MENU_UI = 0x08095F58
ROW_RESET = 0x08095F72          # obj[0x16] = 0  (current row)
ANCHOR_RESET = 0x08095F74       # obj[0x14] = 0  (anchor row)
POLL = 0x0809602C               # read the cached key state
UP_TEST = 0x0809602E            # 0x40
DOWN_TEST = 0x0809604C          # 0x80
A_TEST = 0x08096078             # 0x01, read from 0x0300000E
A_TAKEN = 0x08096088            # 0x0200A882 = 1
ANSWER_WRITE = 0x08096090       # 0x0200A880 = current row
DONE_CHECK = 0x080960C2         # "menu finished?" test
LOOP_HEAD = 0x080960C6          # b back to 0x08095FC4

# --- the answer channel ----------------------------------------------------
ANSWER_ADDR = 0x0200A880        # the selected row
FINISHED_ADDR = 0x0200A882      # "menu finished" flag
KEYSTATE_ADDR = 0x0200A884      # cached key state (u16)
ROW_PTR_ADDR = 0x0200A890       # u32 pointer to the row struct
NEW_PRESS = 0x0300000E          # new press mask (u16)
HELD = 0x0300000C               # currently held mask (u16)

# --- the VM ----------------------------------------------------------------
OP_1A = 0x08097C6C              # VM opcode 0x1A (next scene / chapter hand-off)
OP_06 = 0x080979D6              # VM opcode 0x06 (branch on the menu answer)
OP_05 = 0x08097992              # VM opcode 0x05 (build the menu)
COND_READ = 0x08097AC4          # VM opcode 0x0B reads the condition bitfield

# --- the scene 1 script ----------------------------------------------------
SCENE1_MENU = 0x0800B7FF        # the "do you know Kato" choice
SCENE1_HANDOFF = 0x0800BFBC     # `1A 02 00` -- the chapter hand-off


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    ap.add_argument("--scene", type=int, default=1)
    ap.add_argument("--branch", type=int, default=0)
    ap.add_argument("--cond", type=int, default=0,
                    help="condition bitmask written into 0x020314F0")
    ap.add_argument("--presses", type=int, default=200)
    ap.add_argument("--keys", default="A",
                    help="comma separated key names, cycled")
    ap.add_argument("--force-row", type=int, default=None,
                    help="when the menu asks whether it is finished, write "
                         "this row into 0x0200A880 and set 0x0200A882 = 1")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    names = ["A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN"]
    keys = [KEY_BITS[k.strip().upper()] for k in args.keys.split(",")
            if k.strip().upper() in names]
    if not keys:
        keys = [KEY_BITS["A"]]

    watch = [POLL, A_TEST, A_TAKEN, DONE_CHECK, OP_1A, OP_06, OP_05,
             SCENE1_MENU, SCENE1_HANDOFF, 0x080615E4]
    if args.cond:
        watch.append(COND_READ)

    harness = Harness(args.exe, pathlib.Path(args.rom))
    report: dict = {
        "scene": args.scene, "branch": args.branch, "cond": args.cond,
        "force_row": args.force_row, "hits": [], "new_press_seen": [],
    }
    counts: dict[str, int] = {}
    try:
        if not harness.boot_to_state_machine():
            print("could not park on the state machine", file=sys.stderr)
            return 2
        for addr in watch:
            harness.arm(addr)
        harness.poke(SCENE_BYTE, args.scene)
        harness.poke(BRANCH_BYTE, args.branch & 0xFF)
        if args.cond:
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
            newp = int.from_bytes(harness.read(NEW_PRESS, 2), "little")
            held = int.from_bytes(harness.read(HELD, 2), "little")
            answer = harness.read(ANSWER_ADDR, 4)
            finished = answer[2]
            row = answer[0]
            name = {POLL: "menu-poll", A_TEST: "A-test", A_TAKEN: "A-taken",
                    DONE_CHECK: "done-check", OP_1A: "op-0x1A",
                    OP_06: "op-0x06", OP_05: "op-0x05",
                    SCENE1_MENU: "scene1-menu",
                    SCENE1_HANDOFF: "scene1-handoff",
                    COND_READ: "cond-read",
                    0x080615E4: "key-update"}.get(hit, f"0x{hit:08X}")
            counts[name] = counts.get(name, 0) + 1

            if args.cond and hit == COND_READ:
                # the `0x0B` handler is about to read the condition byte; the
                # game cleared the whole condition array when the scene
                # started, so the bit has to be written right now.
                for off in range(8):
                    harness.poke(COND_BASE - 8 + off, 0xFF)
                harness.poke(COND_BASE, args.cond & 0xFF)
                report.setdefault("cond_patched", []).append(
                    f"0x{regs.get('r7', 0):08X}")

            if hit == POLL:
                # the menu object pointer is r6 at this point
                obj = regs.get("r6", 0)
                cur = harness.read(obj + 0x16, 1)[0] if obj else None
                anchor = harness.read(obj + 0x14, 1)[0] if obj else None
                report["hits"].append({
                    "site": name, "obj": f"0x{obj:08X}",
                    "row": cur, "anchor": anchor,
                    "new_press": f"0x{newp:04X}", "held": f"0x{held:04X}",
                    "answer": f"0x{answer[0]:02X}",
                    "finished": finished,
                })
                if newp & 1:
                    report["new_press_seen"].append(f"0x{newp:04X}")
            else:
                report["hits"].append({
                    "site": name, "new_press": f"0x{newp:04X}",
                    "held": f"0x{held:04X}",
                    "answer": f"0x{answer[0]:02X}", "finished": finished,
                    "r0": f"0x{regs.get('r0', 0):08X}",
                })

            if args.force_row is not None and hit == DONE_CHECK:
                # the menu is asking "am I finished?" -- answer for it
                harness.poke(ANSWER_ADDR, args.force_row & 0xFF)
                harness.poke(FINISHED_ADDR, 1)
                report.setdefault("forced", []).append(
                    f"row={args.force_row} at done-check")
            harness.send("next")
            harness.rearm()
    finally:
        harness.close()

    report["counts"] = counts
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("counts:", json.dumps(counts, ensure_ascii=False))
    polls = [h for h in report["hits"] if h["site"] == "menu-poll"]
    if polls:
        seen = {h["new_press"] for h in polls}
        print("new_press values seen at the menu poll:",
              ", ".join(sorted(seen)))
        print("last 6 polls:", json.dumps(polls[-6:], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
