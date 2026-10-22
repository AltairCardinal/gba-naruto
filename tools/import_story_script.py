#!/usr/bin/env python3
"""Write-back path for the story script VM root tables.

Four root tables hold one u32 ROM pointer per scene
(``notes/story-script-vm.md`` §1):

    before  0x060C74   pre-battle story script      (scenes 1..55)
    after   0x060D54   post-battle story script     (scenes 1..55)
    logic   0x060E34   in-battle event logic        (scenes 1..46)
    events  0x060EF0   in-battle event table        (scenes 1..46)

The interpreter lives at 0x080977B8; the instruction lengths come from
``tools/decode_story_script.py`` (shared with the decoder so the two can never
drift apart).

**Why this write-back is length-preserving.**  Text instructions (opcodes
0x01 / 0x05 / 0x13 / 0x20) are variable length, so rewriting prose would move
every following instruction and invalidate the absolute branch targets
(``u32`` ROM addresses) inside the script.  This tool therefore only patches
*fixed-width* operands whose meaning is proved
(``notes/story-script-vm.md`` §4), and it patches them **in place**: the native
instruction bytes are copied and only the named operand byte(s) are
overwritten, so the script keeps its exact length and every branch target
stays valid.

Text editing is therefore *not* available yet; see
``notes/evidence/writeback-paths-20261020.md`` for the relocation path that
would be required and the falsifiable test that would prove it.

Usage:
    python tools/import_story_script.py rom/base.gba --table before --scene 1
    python tools/import_story_script.py rom/base.gba --table before --scene 1 \\
        --patch '{"opcode": 8, "occurrence": 0, "field": "portrait", "value": 12}' \\
        --out build/naruto.gba
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.lib.io import write_json  # noqa: E402

import decode_story_script as ds  # noqa: E402  (shared length/branch tables)

BASE = 0x08000000

ROOT_TABLES: dict[str, int] = dict(ds.ROOT_TABLES)
STORY_SCENES = ds.STORY_SCENES
BATTLE_SCENES = ds.BATTLE_SCENES

# Fixed-width operands whose meaning is proved (notes/story-script-vm.md §4).
# opcode -> field -> (offset inside the instruction, size in bytes)
#
# Mirrors `rom-editor/js/storyvm.js::KNOWN_OPERANDS` (the two tables must stay
# item-for-item identical; the editor gate `verify_battle_story_triggers.mjs`
# checks that).  0x32 is deliberately absent: its u32 payload is a *segment
# start address*, not a parameter.
KNOWN_OPERANDS: dict[int, dict[str, tuple[int, int]]] = {
    0x08: {"portrait": (1, 1)},                       # set portrait + speaker name
    0x09: {"flag": (1, 1)},                          # set story flag bit(id)
    0x0A: {"flag": (1, 1)},                          # clear story flag bit(id)
    0x0B: {},                                       # conditional branch (u32 target)
    0x0C: {},                                       # conditional branch (u32 target)
    0x0E: {"portrait_a": (1, 1), "portrait_b": (2, 1)},   # two portraits
    0x0F: {"frames": (1, 1)},                        # wait N frames
    0x11: {"portrait": (1, 1)},                      # clear/set portrait (0xFF = all)
    0x14: {"progress": (1, 2)},                      # story progress (u16)
    0x16: {"scene": (1, 1)},                         # switch to next scene
    0x1A: {"scene": (1, 1), "flag": (2, 1)},         # switch scene + flag
    0x1B: {"track": (1, 1), "mode": (2, 1)},         # play music
    0x1D: {"track": (1, 1), "mode": (2, 1)},         # stop music / switch state
    0x1E: {"map": (1, 1)},                           # load map / background
    0x1F: {"config": (1, 1)},                        # set sub-config id
    0x23: {"member_a": (1, 1), "member_b": (2, 1)},   # set party members
    0x33: {"value": (1, 1)},                         # push event queue value
    # 战场触发的条件指令（0x34..0x39）：定宽 u8 字段。
    # u32 跳转目标一律不给 —— 改它是改控制流，不是改参数。
    0x34: {"comparator": (1, 1), "round_count": (2, 1), "phase_byte": (3, 1)},
    0x35: {"expect": (1, 1), "param_b": (2, 1), "param_c": (3, 1), "param_d": (4, 1)},
    0x36: {"expect": (1, 1), "param_b": (2, 1), "role_id": (3, 1)},
    0x37: {"flag_mode": (1, 1), "battle_flag": (2, 1)},
    0x38: {"flag_mode": (1, 1), "battle_flag": (2, 1)},
    0x39: {"sub_config": (1, 1)},
}

# Variable-length (text) opcodes: a length-preserving write-back cannot edit
# them, so they are rejected explicitly instead of silently corrupting the
# script.
TEXT_OPCODES = {0x01, 0x05, 0x13, 0x20}


class WriteBackError(ValueError):
    """Raised when an author change is not representable in the ROM record."""


# --- scanning ---------------------------------------------------------------

def _text_end(rom: bytes, pos: int) -> int:
    """Offset just after the NUL-terminated text run starting at ``pos``.

    Mirrors ``tools/konoha_font.decode_at``'s scan (0x00 ends the run, 0x01
    and 0x02 are two-byte / three-byte control codes) but without needing the
    font catalogue.
    """
    p = pos
    limit = min(len(rom), pos + 8192)
    while p < limit:
        a = rom[p]
        if a == 0:
            return p + 1
        if a == 1:
            p += 2
            continue
        if a == 2:
            p += 3
            continue
        if 0x80 <= a <= 0x9F:
            p += 2
            continue
        p += 1
    raise WriteBackError(f"unterminated text run at 0x{p:X}")


def instruction_length(rom: bytes, offset: int) -> int:
    """Length of the instruction at ``offset`` (file offset)."""
    op = rom[offset]
    if op in TEXT_OPCODES:
        if op == 0x01:
            return 1 + (_text_end(rom, offset + 1) - (offset + 1))
        if op == 0x05 or op == 0x20:
            return 2 + (_text_end(rom, offset + 2) - (offset + 2))
        # 0x13: first text at +4; a second text follows when +2 is non-zero
        end = _text_end(rom, offset + 4)
        if rom[offset + 2]:
            end = _text_end(rom, end + 1)
        return end - offset
    if op == 0x06:
        return 9
    length = ds.LENGTHS.get(op)
    if length is None:
        raise WriteBackError(f"unknown opcode 0x{op:02X} at 0x{offset + BASE:08X}")
    return length


def _branch_targets(rom: bytes, offset: int, length: int) -> list[int]:
    op = rom[offset]
    targets: list[int] = []
    if op == 0x06:
        targets = [struct.unpack_from("<I", rom, offset + 1)[0],
                   struct.unpack_from("<I", rom, offset + 5)[0]]
    elif op in ds.SINGLE_TARGET:
        targets = [struct.unpack_from("<I", rom, offset + 1)[0]]
    elif op in ds.BRANCH:
        targets = [struct.unpack_from("<I", rom, offset + ds.BRANCH[op])[0]]
    return [t - BASE for t in targets]


def scan_script(rom: bytes, root: int) -> list[dict]:
    """Return every reachable instruction of the script at ``root``.

    The result is ordered by file offset; each item is
    ``{"offset", "op", "length"}``.
    """
    if not 0 <= root < len(rom):
        raise WriteBackError(f"script root 0x{root:X} outside the ROM")
    seen: dict[int, dict] = {}
    stack = [root]
    while stack:
        p = stack.pop()
        if p in seen or not 0 <= p < len(rom):
            continue
        length = instruction_length(rom, p)
        seen[p] = {"offset": p, "op": rom[p], "length": length}
        for target in _branch_targets(rom, p, length):
            if 0 <= target < len(rom):
                stack.append(target)
        if rom[p] not in (0x00, 0x06, 0x07):
            stack.append(p + length)
    return [seen[p] for p in sorted(seen)]


# --- read -------------------------------------------------------------------

def read_root_pointer(rom: bytes, table: str, scene: int) -> int | None:
    """File offset of the script the root table points at (None when empty)."""
    if table not in ROOT_TABLES:
        raise WriteBackError(f"unknown root table {table!r}")
    limit = BATTLE_SCENES if table in ("logic", "events") else STORY_SCENES
    if not 1 <= scene <= limit:
        raise WriteBackError(f"scene {scene} outside 1..{limit} for table {table!r}")
    base = ROOT_TABLES[table]
    pointer = struct.unpack_from("<I", rom, base + scene * 4)[0]
    if pointer == 0:
        return None
    offset = pointer - BASE
    if not 0 <= offset < len(rom):
        raise WriteBackError(f"root pointer 0x{pointer:08X} outside the ROM")
    return offset


def read_story_field(rom: bytes, table: str, scene: int, opcode: int,
                     occurrence: int, field: str) -> dict:
    """Read one known operand of the n-th instruction with ``opcode``."""
    root = read_root_pointer(rom, table, scene)
    if root is None:
        raise WriteBackError(f"{table}[{scene}] has no script")
    instructions = [i for i in scan_script(rom, root) if i["op"] == opcode]
    if not 0 <= occurrence < len(instructions):
        raise WriteBackError(
            f"occurrence {occurrence} out of range ({len(instructions)} found)"
        )
    operands = KNOWN_OPERANDS.get(opcode, {})
    if field not in operands:
        raise WriteBackError(
            f"opcode 0x{opcode:02X} has no known operand {field!r} "
            f"(known: {sorted(operands)})"
        )
    operand_off, size = operands[field]
    at = instructions[occurrence]["offset"] + operand_off
    return {
        "table": table,
        "scene": scene,
        "root": root,
        "opcode": opcode,
        "occurrence": occurrence,
        "field": field,
        "offset": at,
        "value": int.from_bytes(rom[at:at + size], "little"),
    }


# --- write ------------------------------------------------------------------

def patch_story_script(rom: bytearray, table: str, scene: int,
                       patches: list[dict]) -> dict:
    """Apply author patches to one scene script, in place.

    Each patch is ``{"opcode": int, "occurrence": int, "field": str,
    "value": int}``.  The native instruction bytes are copied and only the
    named operand byte(s) are overwritten, so the script length is preserved.
    """
    root = read_root_pointer(rom, table, scene)
    if root is None:
        raise WriteBackError(f"{table}[{scene}] has no script")
    instructions = scan_script(rom, root)
    applied: list[dict] = []
    for patch in patches:
        opcode = int(patch["opcode"])
        occurrence = int(patch.get("occurrence", 0))
        field = patch["field"]
        value = int(patch["value"])
        if opcode in TEXT_OPCODES:
            raise WriteBackError(
                f"opcode 0x{opcode:02X} carries variable-length text; a "
                f"length-preserving write-back cannot edit it (relocation "
                f"required)"
            )
        operands = KNOWN_OPERANDS.get(opcode, {})
        if field not in operands:
            raise WriteBackError(
                f"opcode 0x{opcode:02X} has no known operand {field!r} "
                f"(known: {sorted(operands)})"
            )
        matches = [i for i in instructions if i["op"] == opcode]
        if not 0 <= occurrence < len(matches):
            raise WriteBackError(
                f"occurrence {occurrence} out of range ({len(matches)} found "
                f"for opcode 0x{opcode:02X})"
            )
        instruction = matches[occurrence]
        operand_off, size = operands[field]
        at = instruction["offset"] + operand_off
        if not 0 <= value < (1 << (size * 8)):
            raise WriteBackError(
                f"value {value} does not fit into {size} byte(s) at 0x{at:X}"
            )
        # copy the native instruction, then overwrite only the operand
        native = bytes(rom[instruction["offset"]:instruction["offset"] + instruction["length"]])
        buf = bytearray(native)
        buf[operand_off:operand_off + size] = value.to_bytes(size, "little")
        rom[instruction["offset"]:instruction["offset"] + instruction["length"]] = buf
        applied.append({
            "table": table,
            "scene": scene,
            "opcode": opcode,
            "occurrence": occurrence,
            "field": field,
            "value": value,
            "offset": at,
            "instruction_offset": instruction["offset"],
        })
    return {
        "table": table,
        "scene": scene,
        "root": root,
        "script_length": sum(i["length"] for i in instructions),
        "patches": applied,
    }


# --- CLI --------------------------------------------------------------------

def _as_path(value: str) -> pathlib.Path | None:
    """Path for a CLI argument, or None when it cannot be a path at all."""
    try:
        return pathlib.Path(value)
    except (OSError, ValueError):
        return None


def _load_json_arg(value: str) -> dict:
    """Load a JSON object from an inline argument or from a JSON file."""
    path = _as_path(value)
    if path is not None and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"--patch expects a JSON object or a JSON file path ({exc}); "
            f"received {value!r}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", help="ROM path (a copy is patched, never the original)")
    parser.add_argument("--table", default="before", choices=sorted(ROOT_TABLES))
    parser.add_argument("--scene", type=int, default=1)
    parser.add_argument("--patch", action="append", default=[], dest="patches",
                        help="JSON patch (repeatable)")
    parser.add_argument("--out", help="write the patched ROM copy here")
    parser.add_argument("--json", help="write the read-back report here")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    rom = bytearray(rom_path.read_bytes())

    patches = [_load_json_arg(p) for p in args.patches]
    result = patch_story_script(rom, args.table, args.scene, patches)

    if args.out:
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(bytes(rom))

    readback = []
    for patch in result["patches"]:
        readback.append(read_story_field(
            rom, args.table, args.scene, patch["opcode"],
            patch["occurrence"], patch["field"],
        ))

    report = {"applied": result, "read_back": readback}
    if args.json:
        write_json(args.json, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
