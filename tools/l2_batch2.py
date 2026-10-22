#!/usr/bin/env python3
"""Batch-2 helper: enumerate and disassemble the native readers of a table.

Why this tool exists
--------------------
`tools/l2_runtime_capture.py` needs three hand-picked facts per structure:

  1. the **reader** -- the instruction that loads the table base,
  2. the **decision point** -- the instruction after it where the base, the
     index and the field value are all in registers,
  3. the **stride** -- how the index is scaled into the table.

Batch 2 adds twelve structures.  Picking those three facts by eye over a
whole-ROM disassembly is slow and error prone, so this helper prints, for
every native reader of a table, the enclosing function and the instruction
window around the reader.  Nothing here is trusted automatically: the tool
only *prints*; the choices are still made by reading the code, and every
address that ends up in `l2_runtime_capture.py` is re-verified at run time
by the static checks there (the reader must be in the `LiteralIndex` reader
set) and by the negative control.

Usage:
    python tools/l2_batch2.py --list
    python tools/l2_batch2.py battle_handler_table --window 14
    python tools/l2_batch2.py --all --window 14 --json build/l2-batch2-readers.json

Diagnostics (what the emulator actually reaches):

    python tools/l2_batch2.py --battle-diag --battle-groups 40 --watch 0x08098822
    python tools/l2_batch2.py --sweep-diag --sweep-scenes 1-20 --watch 0x0807F942
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

from consumer_locate import (LiteralIndex, decode_function,       # noqa: E402
                             disassemble, find_function_start)
from table_registry import TABLES                                # noqa: E402

ROM_BASE = 0x08000000

NOTE = REPO / "notes" / "evidence" / "l2-runtime-evidence-20261021.md"


def append_note(text: str, path: pathlib.Path = NOTE) -> pathlib.Path:
    """Append to a note with LF line endings (see tools/lib/io.py)."""
    from tools.lib.io import write_text
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    write_text(path, existing + text)
    return path


# The twelve structures of L2 batch 2, in the order of the task table.
BATCH2 = [
    ("battle-handlers", "battle_handler_table"),
    ("fonts", "font_width_table"),
    ("data-table-a", "data_pointer_table_a"),
    ("data-table-b", "data_pointer_table_b"),
    ("function-pointers", "function_pointer_table"),
    ("tile-assets", "tile_asset_records"),
    ("sprite-frame-descriptors", "sprite_frame_descriptors"),
    ("battle-encounters", "battle_encounter_records"),
    ("ninjutsu-names", "ninjutsu_names"),
    ("reward-table", "reward_table"),
    ("cutscene-scripts", "legacy_cutscene_scripts"),
    ("sprite-action-table", "sprite_action_table"),
]


def window(rom: bytes, reader: int, mode: str, span: int) -> list[str]:
    """The instructions around `reader`, with the literal pool filtered out."""
    fn_start = find_function_start(rom, reader, mode)
    insns = []
    if fn_start is not None:
        insns = decode_function(rom, fn_start, mode)
    index = next((i for i, insn in enumerate(insns) if insn.address == reader),
                 None)
    if index is None:
        # ARM code in this ROM does not always start with an `stmfd ... lr`
        # prologue, so fall back to a straight linear disassembly around the
        # reader.  The literal pool is a *data* word there, but the window is
        # short enough that the reader is still readable.
        insns = disassemble(rom, (reader - 0x60) & ~3, 0x60, "arm")
        index = next((i for i, insn in enumerate(insns) if insn.address == reader),
                     None)
        if index is None:
            return [f"    (reader 0x{reader:08X} not disassembled)"]
    lines = []
    for insn in insns[max(0, index - span):index + span + 1]:
        marker = ">>" if insn.address == reader else "  "
        lines.append(f"  {marker} {insn.address:08X}  {insn.mnemonic:8s} "
                     f"{insn.op_str}")
    return lines


def readers_of(index: LiteralIndex, name: str) -> list[tuple[int, str]]:
    """(reader address, mode) for every native reader of the table base."""
    offset, _verified, _note = TABLES[name]
    base = offset + ROM_BASE
    modes: dict[int, str] = {}
    for addr, mode in index.readers_of(base):
        modes.setdefault(addr, mode)
    return sorted(modes.items())


def battle_diag(groups: str, subs: str, presses: int, states: pathlib.Path,
                exe: pathlib.Path, rom_path: pathlib.Path,
                watch: list[int] | None = None,
                keys: str = "A") -> None:
    """Report whether the battle route actually reaches a battle.

    For every (group, sub) it forces the battle with the three memory writes
    the state machine expects, then reports which of the battle's own
    milestones were hit and what the unit array looks like.
    """
    import l2_runtime_capture as L

    probe = L.Probe(exe, rom_path, timeout=3600)
    key_cycle = [L._key_mask(k) for k in keys.split(",") if k] or [L.KEY_A]
    try:
        state = states / "battle.ss9"
        probe.send(f"load {state}")
        milestones = {
            "phase_110": 0x0808F92E,
            "wrapper": 0x080732B4,
            "entry": 0x0808A588,
            "map_load": 0x0808F588,
            "vm": L.VM_ENTRY,
        }
        for item in watch or []:
            milestones[f"w{item:08X}"] = item
        ids: dict[str, int] = {}
        for group in L.parse_scene_list(groups):
            for sub in L.parse_scene_list(subs):
                probe.send(f"load {state}")
                seen = set()
                for name, ident in ids.items():
                    if ident:
                        probe.send(f"delete {ident}")
                ids = {}
                for name, addr in milestones.items():
                    ident = L.arm(probe, addr)
                    if ident:
                        ids[name] = ident
                probe.send(f"poke 0x{L.SCENE_BYTE:08X} {group}")
                probe.send(f"poke 0x{L.SUBCFG_BYTE:08X} {sub}")
                probe.send(f"poke16 0x{L.PHASE_WORD:08X} {L.PHASE_BATTLE}")
                for step in range(presses):
                    mask = key_cycle[step % len(key_cycle)]
                    out = probe.send(f"frames {L.PRESS_FRAMES} {mask:#05x}")
                    found = L.hits_in(out)
                    if not found:
                        out = probe.send(f"frames {L.SETTLE_FRAMES} 0x000")
                        found = L.hits_in(out)
                    for _ident, addr in found:
                        for name, target in milestones.items():
                            if addr == target:
                                seen.add(name)
                        probe.send("next")
                units = 0
                for slot in range(12):
                    raw = probe.read_bytes(0x020240C0 + slot * 0x1D4, 1)
                    if raw and raw[0]:
                        units += 1
                mapid = probe.read_bytes(0x020311EB, 1)
                print(f"group={group:3d} sub={sub}  seen={sorted(seen)}  "
                      f"units={units}  mapid={mapid.hex() if mapid else '??'}")
    finally:
        probe.close()


def sweep_diag(scenes: str, presses: int, states: pathlib.Path,
               exe: pathlib.Path, rom_path: pathlib.Path,
               watch: list[int] | None = None, keys: str = "A") -> None:
    """Watch addresses while the story sweep plays every scene."""
    import l2_runtime_capture as L

    probe = L.Probe(exe, rom_path, timeout=3600)
    key_cycle = [L._key_mask(k) for k in keys.split(",") if k] or [L.KEY_A]
    try:
        state = states / "sweep.ss9"
        milestones = {"vm": L.VM_ENTRY, "next": L.NEXT_SCENE}
        for item in watch or []:
            milestones[f"w{item:08X}"] = item
        ids: dict[str, int] = {}
        for scene in L.parse_scene_list(scenes):
            probe.send(f"load {state}")
            seen = set()
            for name, ident in ids.items():
                if ident:
                    probe.send(f"delete {ident}")
            ids = {}
            for name, addr in milestones.items():
                ident = L.arm(probe, addr)
                if ident:
                    ids[name] = ident
            probe.send(f"poke 0x{L.SCENE_BYTE:08X} {scene}")
            probe.send("next")
            for step in range(presses):
                mask = key_cycle[step % len(key_cycle)]
                out = probe.send(f"frames {L.PRESS_FRAMES} {mask:#05x}")
                found = L.hits_in(out)
                if not found:
                    out = probe.send(f"frames {L.SETTLE_FRAMES} 0x000")
                    found = L.hits_in(out)
                for _ident, addr in found:
                    for name, target in milestones.items():
                        if addr == target:
                            seen.add(name)
                    probe.send("next")
            scene_byte = probe.read_bytes(L.SCENE_BYTE, 1)
            print(f"scene={scene:3d}  seen={sorted(seen)}  "
                  f"scene_byte={scene_byte.hex() if scene_byte else '??'}")
    finally:
        probe.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table", nargs="?", default=None,
                    help="registry entry name (or the batch-2 structure key)")
    ap.add_argument("--all", action="store_true", help="every batch-2 table")
    ap.add_argument("--list", action="store_true", help="list the batch-2 tables")
    ap.add_argument("--window", type=int, default=10,
                    help="instructions shown on each side of the reader")
    ap.add_argument("--rom", type=pathlib.Path, default=REPO / "rom" / "base.gba")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    ap.add_argument("--battle-diag", action="store_true",
                    help="report whether the battle route reaches a battle")
    ap.add_argument("--battle-groups", default="40")
    ap.add_argument("--battle-subs", default="0")
    ap.add_argument("--battle-presses", type=int, default=12)
    ap.add_argument("--watch", nargs="*", default=[],
                    help="extra addresses to watch during the battle diagnostic")
    ap.add_argument("--keys", default="A",
                    help="key cycle the battle diagnostic uses")
    ap.add_argument("--sweep-diag", action="store_true",
                    help="watch addresses while the story sweep plays")
    ap.add_argument("--sweep-scenes", default="1-55")
    ap.add_argument("--sweep-presses", type=int, default=16)
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.sweep_diag:
        import l2_runtime_capture as L
        sweep_diag(args.sweep_scenes, args.sweep_presses, L.STATE_DIR,
                   L.DEFAULT_EXE, args.rom,
                   [int(a, 16) for a in args.watch], args.keys)
        return 0

    if args.battle_diag:
        import l2_runtime_capture as L
        battle_diag(args.battle_groups, args.battle_subs, args.battle_presses,
                    L.STATE_DIR, L.DEFAULT_EXE, args.rom,
                    [int(a, 16) for a in args.watch], args.keys)
        return 0

    if args.list:
        for key, name in BATCH2:
            offset, verified, note = TABLES[name]
            print(f"{key:26s} {name:28s} base=0x{offset + ROM_BASE:08X} "
                  f"verified={verified}")
        return 0

    if args.all:
        wanted = list(BATCH2)
    elif args.table:
        matched = [n for n in BATCH2 if n[0] == args.table]
        if not matched and args.table in TABLES:
            matched = [(args.table, args.table)]
        if not matched:
            print(f"ERR unknown table {args.table!r}", file=sys.stderr)
            return 2
        wanted = matched
    else:
        ap.print_help()
        return 2

    rom = args.rom.read_bytes()
    index = LiteralIndex(rom)
    report: dict = {}
    for key, name in wanted:
        offset, verified, note = TABLES[name]
        base = offset + ROM_BASE
        print(f"== {key}  ({name})  base=0x{base:08X}  verified={verified}")
        print(f"   note: {note}")
        entries = []
        for addr, mode in readers_of(index, name):
            print(f"   reader 0x{addr:08X} [{mode}]")
            fn_start = find_function_start(rom, addr, mode)
            print(f"     fn start 0x{(fn_start or 0):08X}")
            for line in window(rom, addr, mode, args.window):
                print(line)
            entries.append({"reader": f"0x{addr:08X}", "mode": mode,
                            "function": f"0x{(fn_start or 0):08X}"})
        report[key] = {"registry": name, "base": f"0x{base:08X}",
                       "verified": verified, "readers": entries}
        print()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
