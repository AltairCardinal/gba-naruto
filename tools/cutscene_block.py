#!/usr/bin/env python3
"""Decode the data blocks behind the legacy "cutscene script" pointer table.

What this settles
-----------------
The legacy structure bank calls ``0x53DF70`` a *cutscene script pointer table*
(16 x u32).  The table's only native reader is ``0x08072EDC``; that reader
does **not** feed the story VM.  This tool proves what the reader really does
and what the pointed-at blocks really contain, so the structure can be given a
definite identity instead of an either/or.

Findings (see ``notes/evidence/cutscene-block-format-20261020.md``):

* ``0x53DF70`` is read with an **8-byte stride**: every index selects a *pair*
  of u32 pointers, ``(graphics, palette)``.
* The first pointer of a pair is handed to the BIOS thunk ``0x809C0E8``
  (``svc 0x12`` = ``LZ77UnCompVram``) with destination ``0x06016000``
  (OBJ VRAM); the second pointer is handed to the same thunk with destination
  ``0x05000380`` (palette RAM, slot 28).
* Both blocks are **GBA LZ77** blocks: header byte ``0x10``, then a 24-bit
  little-endian *decompressed* size, then the LZ77 payload
  (``tools/lib/lz77.py`` already implements the codec).
  The graphics blocks decompress to 4096 / 4096 / 4096 / 2048 bytes of 4bpp
  tile pixels; the palette blocks decompress to 32 bytes = 16 x BGR555.
* The story VM script format (``notes/story-script-vm.md``) is a *bytecode*
  stream with an opcode table, text runs and absolute branch targets.  None of
  the blocks can be walked as a VM script, and no block address appears in the
  VM's four root tables.

Usage
-----
    python tools/cutscene_block.py rom/base.gba
    python tools/cutscene_block.py rom/base.gba --json build/cutscene-block.json
    python tools/cutscene_block.py rom/base.gba --disasm 0x08072EDC --count-disasm 400
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys
from collections import deque

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.lib.io import write_json  # noqa: E402
from tools.lib.lz77 import decompress  # noqa: E402

ROM_BASE = 0x08000000

# The legacy structure under investigation.
LEGACY_TABLE = 0x53DF70          # file offset
LEGACY_TABLE_ADDR = 0x0853DF70   # ROM address the native code loads
LEGACY_PAIR_STRIDE = 8           # bytes per index as the native reader walks it
LEGACY_ROM_BASE = 0x0812D000     # the region every legacy pointer lands in

# The story VM's four root tables (notes/story-script-vm.md).
STORY_ROOT_TABLES = (0x060C74, 0x060D54, 0x060E34, 0x060EF0)
STORY_SCENES = 55

LZ77_MAGIC = 0x10


# ---------------------------------------------------------------------------
# capstone plumbing (same discovery order as tools/consumer_locate.py)
# ---------------------------------------------------------------------------
def _candidate_capstone_dirs() -> list[pathlib.Path]:
    import os

    out: list[pathlib.Path] = []
    env = os.environ.get("LIBCAPSTONE_PATH")
    if env:
        out.append(pathlib.Path(env))
    deps = REPO / "build" / "python-deps"
    if deps.exists():
        for dll in deps.rglob("capstone.dll"):
            out.append(dll.parent)
        for dll in deps.rglob("libcapstone.dll"):
            out.append(dll.parent)
    return out


def load_capstone():
    """Import capstone, auto-pointing LIBCAPSTONE_PATH at a local DLL."""
    vendor = REPO / "tools" / "_vendor"
    if str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    try:
        import capstone  # noqa: F401
        return capstone
    except Exception:
        pass
    for cand in _candidate_capstone_dirs():
        if cand and cand.exists():
            import os

            os.environ["LIBCAPSTONE_PATH"] = str(cand)
            try:
                import capstone  # noqa: F401
                return capstone
            except Exception:
                continue
    raise SystemExit(
        "capstone is unavailable: set LIBCAPSTONE_PATH to the folder that "
        "holds capstone.dll (see notes/windows-migration-20261020.md 2.2)"
    )


CS = load_capstone()
MD = CS.Cs(CS.CS_ARCH_ARM, CS.CS_MODE_THUMB)
MD.detail = True


# ---------------------------------------------------------------------------
# small ROM helpers
# ---------------------------------------------------------------------------
def read_u32(rom: bytes, addr: int) -> int:
    """u32 at a ROM address."""
    return struct.unpack_from("<I", rom, addr - ROM_BASE)[0]


def read_u16(rom: bytes, addr: int) -> int:
    return struct.unpack_from("<H", rom, addr - ROM_BASE)[0]


def read_u32_at_file(rom: bytes, offset: int) -> int:
    """u32 at a ROM *file* offset (the story VM root tables live at such offsets)."""
    return struct.unpack_from("<I", rom, offset)[0]


def u24(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16)


# ---------------------------------------------------------------------------
# 1. the pointer table
# ---------------------------------------------------------------------------
def read_pointer_table(rom: bytes, table: int = LEGACY_TABLE,
                       count: int = 16) -> list[int]:
    """The u32 pointers stored at `table` (a ROM address)."""
    out = []
    for i in range(count):
        out.append(read_u32(rom, table + i * 4))
    return out


# ---------------------------------------------------------------------------
# 2. the block format
# ---------------------------------------------------------------------------
def lz77_span(rom: bytes, addr: int) -> tuple[int, int, int]:
    """(decompressed_size, compressed_bytes, decompressed_bytes) of an LZ77 block.

    ``compressed_bytes`` counts the header plus the compressed payload, so the
    caller can tell how much ROM the block occupies.
    """
    off = addr - ROM_BASE
    size = u24(rom, off + 1)
    pos = off + 4
    out = 0
    while out < size:
        flags = rom[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if out >= size:
                break
            if flags & (1 << bit):
                b0 = rom[pos]
                b1 = rom[pos + 1]
                pos += 2
                disp_len = ((b0 >> 4) & 0xF) + 3
                disp = ((b0 & 0xF) << 8) | b1
                if disp + 1 > out:
                    raise ValueError(
                        f"back-reference before the output start at 0x{addr:08X}"
                    )
                out += disp_len
            else:
                pos += 1
                out += 1
    return size, pos - off, size


def decode_block(rom: bytes, addr: int) -> dict:
    """Describe the block at ROM address `addr`.

    A GBA LZ77 block starts with ``0x10`` and a 24-bit decompressed size; this
    ROM's blocks are all of that shape.  Anything else is reported as raw.
    """
    off = addr - ROM_BASE
    magic = rom[off]
    info: dict = {
        "addr": f"0x{addr:08X}",
        "file_offset": f"0x{off:06X}",
        "magic": f"0x{magic:02X}",
        "kind": "raw",
    }
    if magic == LZ77_MAGIC:
        size, span, _ = lz77_span(rom, addr)
        payload = decompress(rom, off)
        info.update({
            "kind": "lz77",
            "decompressed_size": size,
            "compressed_bytes": span,
            "decompressed_head": payload[:32].hex(" "),
        })
        if size == 32:
            info["role"] = "palette (16 x BGR555)"
            info["palette_u16"] = [
                f"0x{struct.unpack_from('<H', payload, i)[0]:04X}"
                for i in range(0, 32, 2)
            ]
        elif size % 32 == 0:
            info["role"] = f"4bpp tile pixels ({size // 32} tiles)"
        else:
            info["role"] = f"unknown payload ({size} bytes)"
    else:
        info["head"] = rom[off:off + 32].hex(" ")
    return info


# ---------------------------------------------------------------------------
# 3. "is this a story VM script?" probe
# ---------------------------------------------------------------------------
def vm_probe(rom: bytes, addr: int, limit: int = 64) -> dict:
    """Try to walk `addr` as a story-VM script.

    Uses the opcode lengths the repository already proved
    (``tools/decode_story_script.py``).  A block only counts as a VM script when
    the walk is *meaningful*: no unknown opcode, more than the two trivial
    instructions, and a real terminator.  The report keeps the raw opcode list
    so the reader can see why a block was rejected.
    """
    import decode_story_script as dss

    out: dict = {"addr": f"0x{addr:08X}", "ops": []}
    pos = addr
    for _ in range(limit):
        if not (ROM_BASE <= pos < ROM_BASE + len(rom)):
            out["ok"] = False
            out["reason"] = "walked past the ROM"
            out["instructions"] = len(out["ops"])
            return out
        op = rom[pos - ROM_BASE]
        if op in dss.TEXT_OPS or op == 19 or op == 6:
            # variable length: the length comes from the data itself
            length = None
        else:
            length = dss.LENGTHS.get(op)
            if length is None:
                out["ok"] = False
                out["reason"] = f"unknown opcode 0x{op:02X}"
                out["opcodes"] = [f"0x{o:02X}" for _, o, _ in out["ops"]]
                out["instructions"] = len(out["ops"])
                return out
        out["ops"].append((f"0x{pos:08X}", op, length))
        if op == 0:
            out["ok"] = True
            out["terminated"] = True
            out["reason"] = "terminated by opcode 0x00 (end)"
            out["opcodes"] = [f"0x{o:02X}" for _, o, _ in out["ops"]]
            out["instructions"] = len(out["ops"])
            out["trivial"] = len(out["ops"]) <= 2
            return out
        if length is None:
            out["ok"] = False
            out["reason"] = f"variable-length opcode 0x{op:02X} (text/branch)"
            out["opcodes"] = [f"0x{o:02X}" for _, o, _ in out["ops"]]
            out["instructions"] = len(out["ops"])
            return out
        pos += length
    out["ok"] = False
    out["reason"] = f"no terminator within {limit} instructions"
    out["opcodes"] = [f"0x{o:02X}" for _, o, _ in out["ops"]]
    out["instructions"] = len(out["ops"])
    return out


def story_root_targets(rom: bytes) -> set[int]:
    """Every script start the story VM's four root tables point at.

    The four root tables are ROM *file* offsets (``tools/decode_story_script.py``
    indexes the ROM buffer with them directly); the pointers they hold are ROM
    addresses.
    """
    targets: set[int] = set()
    for table in STORY_ROOT_TABLES:
        for scene in range(STORY_SCENES):
            ptr = read_u32_at_file(rom, table + scene * 4)
            if ROM_BASE <= ptr < ROM_BASE + len(rom):
                targets.add(ptr)
    return targets


# ---------------------------------------------------------------------------
# 4. a control-flow-following Thumb disassembler
# ---------------------------------------------------------------------------
COND_BRANCHES = {
    "beq", "bne", "bhi", "bls", "bgt", "ble", "bcc", "bcs",
    "bmi", "bpl", "bvs", "bvc",
}

_IMM_RE = re.compile(r"#(-?(?:0x[0-9a-fA-F]+|\d+))")


def _imm(text: str) -> int | None:
    m = _IMM_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1), 0)
    except ValueError:
        return None


def _branch_target(op_str: str) -> int | None:
    try:
        return int(op_str.strip().lstrip("#"), 16)
    except ValueError:
        return None


def disassemble_function(rom: bytes, entry: int,
                         max_insns: int = 2000) -> dict:
    """Disassemble the Thumb function at `entry`, following control flow.

    Literal pools are resolved and *not* decoded as code: every
    ``ldr rX, [pc, #imm]`` contributes its literal address to a skip set, so
    the walk steps over the pool instead of mis-reading it as instructions.
    """
    decoded: dict[int, object] = {}
    literals: dict[int, int] = {}
    calls: list[tuple[int, int]] = []
    # Breadth first: a depth-first walk dives into whatever follows the first
    # branch and runs out of budget before it reaches the code behind a
    # conditional branch (that is how the block at 0x08073072 stayed unseen).
    queue = deque([entry])
    while queue and len(decoded) < max_insns:
        addr = queue.popleft()
        if addr in decoded:
            continue
        if addr in literals:          # we are inside a literal pool
            queue.append(addr + 4)
            continue
        off = addr - ROM_BASE
        if off < 0 or off + 4 > len(rom):
            continue
        ins = next(MD.disasm(rom[off:off + 4], addr), None)
        if ins is None:
            continue
        decoded[addr] = ins
        m, op = ins.mnemonic, ins.op_str

        if m.startswith("ldr") and "[pc" in op:
            imm = _imm(op)
            if imm is not None:
                lit = ((addr + 4) & ~3) + imm
                if ROM_BASE <= lit < ROM_BASE + len(rom) - 3:
                    literals[lit] = read_u32(rom, lit)

        if m in ("bl", "blx"):
            tgt = _branch_target(op)
            if tgt is not None:
                calls.append((addr, tgt))
            queue.append(addr + ins.size)
            continue
        if m == "b" or m == "b.w":
            tgt = _branch_target(op)
            if tgt is not None:
                queue.append(tgt)
            continue
        if m in COND_BRANCHES:
            tgt = _branch_target(op)
            if tgt is not None:
                queue.append(tgt)
            queue.append(addr + ins.size)
            continue
        if m in ("bx", "pop", "mov", "ldr", "ldm", "subs", "cmp") and \
                "pc" in op:
            # control leaves the function (bx pc = ARM switch, pop {..,pc},
            # mov pc, lr = return, ldr pc = jump table)
            if m in ("pop", "mov", "ldr", "ldm", "subs", "cmp"):
                queue.append(addr + ins.size)
            continue
        queue.append(addr + ins.size)

    lines = []
    for addr in sorted(decoded):
        ins = decoded[addr]
        note = ""
        if addr in literals:
            note = f"   ; =0x{literals[addr]:08X}"
        lines.append(
            f"{addr:08X}  {ins.mnemonic:<8} {ins.op_str}".rstrip() + note
        )
    return {
        "entry": f"0x{entry:08X}",
        "instructions": lines,
        "literals": {f"0x{a:08X}": f"0x{v:08X}" for a, v in literals.items()},
        "calls": [f"0x{a:08X} -> 0x{t:08X}" for a, t in calls],
    }


# ---------------------------------------------------------------------------
# 5. the native reader, and what it does with the block
# ---------------------------------------------------------------------------
def reader_evidence(rom: bytes, table: int = LEGACY_TABLE_ADDR) -> dict:
    """Locate the native reader of `table` and describe what it does.

    The facts are extracted mechanically from the instruction stream:

      * the **stride** the reader uses to index the table - the ``lsls``
        that shifts the index register and whose result is added to the
        register holding the table base,
      * the **window** of instructions around the table load, which shows
        where each pointer goes,
      * the **callee** that consumes the pointer, and the BIOS SWI number
        that callee issues (``svc 0x12`` = ``LZ77UnCompVram``).
    """
    from consumer_locate import LiteralIndex, find_function_start

    index = LiteralIndex(rom)
    readers = index.readers_of(table)
    out: dict = {"table": f"0x{table:08X}", "readers": []}
    for reader_addr, mode in readers:
        fn = find_function_start(rom, reader_addr, mode)
        entry = {
            "reader": f"0x{reader_addr:08X}",
            "mode": mode,
            "function": f"0x{fn:08X}" if fn else None,
        }
        if not fn:
            out["readers"].append(entry)
            continue
        func = disassemble_function(rom, fn)
        literals = {int(a, 16): int(v, 16) for a, v in func["literals"].items()}
        insns = {}
        for line in func["instructions"]:
            addr = int(line.split()[0], 16)
            insns[addr] = line

        # --- the register that holds the table base -----------------------
        base_reg = None
        base_load = None
        for addr in sorted(insns):
            parts = insns[addr].split(None, 2)
            if len(parts) < 3 or not parts[1].startswith("ldr"):
                continue
            if "[pc" not in parts[2]:
                continue
            imm = _imm(parts[2])
            if imm is None:
                continue
            lit = ((addr + 4) & ~3) + imm
            if literals.get(lit) == table:
                base_reg = parts[2].split(",")[0].strip()
                base_load = addr
                break
        entry["base_register"] = base_reg
        entry["base_load"] = f"0x{base_load:08X}" if base_load else None

        # every literal-pool load of this function, so a sibling table that
        # the same function reads can be pointed at
        loads = []
        for addr in sorted(insns):
            parts = insns[addr].split(None, 2)
            if len(parts) < 3 or not parts[1].startswith("ldr"):
                continue
            if "[pc" not in parts[2]:
                continue
            imm = _imm(parts[2])
            if imm is None:
                continue
            lit = ((addr + 4) & ~3) + imm
            value = literals.get(lit)
            if value is None:
                continue
            loads.append({"load": f"0x{addr:08X}",
                          "value": f"0x{value:08X}"})
        entry["literal_loads"] = loads

        # --- the stride: lsls of the index, added to the base -------------
        stride = None
        stride_at = None
        if base_reg:
            for addr in sorted(insns):
                parts = insns[addr].split(None, 2)
                if len(parts) < 3 or not parts[1].startswith("lsls"):
                    continue
                ops = [o.strip() for o in parts[2].split(",")]
                if len(ops) < 3:
                    continue
                shift = _imm(ops[2])
                if shift is None:
                    continue
                dst = ops[0]
                # the shifted value must be added to the base register
                for probe in range(addr + 2, addr + 12, 2):
                    line = insns.get(probe)
                    if not line:
                        continue
                    p2 = line.split(None, 2)
                    if len(p2) < 3 or not p2[1].startswith("add"):
                        continue
                    o2 = [o.strip() for o in p2[2].split(",")]
                    if len(o2) >= 2 and o2[1] == dst and o2[2:3] == [base_reg]:
                        stride = 1 << shift
                        stride_at = addr
                        break
                if stride:
                    break
        entry["stride"] = stride
        entry["stride_at"] = f"0x{stride_at:08X}" if stride_at else None

        # --- the instruction window around the table load -----------------
        window = []
        if base_load:
            for addr in sorted(insns):
                if base_load - 2 <= addr <= base_load + 26:
                    window.append(insns[addr])
        entry["window"] = window

        # --- the callee and the BIOS SWI it issues ------------------------
        callees = []
        for addr in sorted(insns):
            parts = insns[addr].split(None, 2)
            if len(parts) < 3 or not parts[1].startswith("bl"):
                continue
            tgt = _branch_target(parts[2])
            if tgt is None:
                continue
            # the callee is a different function: disassemble it on its own
            svc = None
            for probe in range(tgt, tgt + 8, 2):
                blob = rom[probe - ROM_BASE: probe - ROM_BASE + 4]
                callee = next(MD.disasm(blob, probe), None)
                if callee is None:
                    break
                if callee.mnemonic.startswith("svc"):
                    svc = callee.op_str
                    break
                if not callee.mnemonic.startswith("bx"):
                    break
            callees.append({
                "call": f"0x{addr:08X}",
                "target": f"0x{tgt:08X}",
                "svc": svc,
            })
        entry["calls"] = callees
        entry["bios_calls"] = [c for c in callees if c["svc"]]
        out["readers"].append(entry)
    return out


# ---------------------------------------------------------------------------
# 6. the whole analysis
# ---------------------------------------------------------------------------
def _is_vm_script(probe: dict, roots: set[int]) -> bool:
    """A block counts as a VM script only if the walk is meaningful.

    Three conditions, all required:
      * every opcode is known,
      * the script is more than the two trivial instructions
        (opcode + immediate end), i.e. it carries content,
      * the script is reachable from one of the four root tables.
    """
    if not probe.get("ok"):
        return False
    if probe.get("trivial"):
        return False
    addr = int(probe["addr"], 16)
    return addr in roots


def analyze(rom: bytes, table: int = LEGACY_TABLE_ADDR,
             count: int = 16) -> dict:
    """Full report for the legacy table at `table` (a ROM address)."""
    pointers = read_pointer_table(rom, table, count)
    roots = story_root_targets(rom)

    pairs = []
    for i in range(0, count, 2):
        gfx, pal = pointers[i], pointers[i + 1]
        gfx_vm = vm_probe(rom, gfx)
        pal_vm = vm_probe(rom, pal)
        pairs.append({
            "index": i // 2,
            "graphics_ptr": f"0x{gfx:08X}",
            "palette_ptr": f"0x{pal:08X}",
            "graphics": decode_block(rom, gfx),
            "palette": decode_block(rom, pal),
            "graphics_vm_probe": gfx_vm,
            "palette_vm_probe": pal_vm,
            "graphics_is_vm_script": _is_vm_script(gfx_vm, roots),
            "palette_is_vm_script": _is_vm_script(pal_vm, roots),
            "in_story_root_tables": (gfx in roots) or (pal in roots),
        })

    return {
        "table": f"0x{table:08X}",
        "table_file_offset": f"0x{table - ROM_BASE:06X}",
        "pointers": [f"0x{p:08X}" for p in pointers],
        "pairs": pairs,
        "reader": reader_evidence(rom, table),
        "story_root_targets": len(roots),
        "block_is_vm_script": any(
            p["graphics_is_vm_script"] or p["palette_is_vm_script"]
            for p in pairs
        ),
        "block_in_story_root_tables": any(
            p["in_story_root_tables"] for p in pairs
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Decode the blocks behind the legacy 0x53DF70 pointer table."
    )
    ap.add_argument("rom", help="ROM path")
    ap.add_argument("--table", default=f"0x{LEGACY_TABLE_ADDR:08X}",
                    help="table base as a ROM address (default 0x0853DF70)")
    ap.add_argument("--count", type=int, default=8,
                    help="number of u32 pointers to read (default 8 = the "
                         "table's true extent; the next 8 u32 at 0x53DF90 "
                         "belong to a separate table)")
    ap.add_argument("--json", help="write the report as JSON")
    ap.add_argument("--disasm", help="disassemble a Thumb function")
    ap.add_argument("--count-disasm", dest="count_disasm", type=int, default=400,
                    help="instruction budget for --disasm")
    args = ap.parse_args()

    rom = pathlib.Path(args.rom).read_bytes()

    if args.disasm:
        func = disassemble_function(rom, int(args.disasm, 0),
                                    args.count_disasm)
        for line in func["instructions"]:
            print(line)
        print("\n-- literal pool --")
        for addr, value in sorted(func["literals"].items()):
            print(f"  {addr}  {value}")
        print("\n-- calls --")
        for call in func["calls"]:
            print(f"  {call}")
        return 0

    report = analyze(rom, int(args.table, 0), args.count)
    print(f"legacy table {report['table']} ({report['table_file_offset']}), "
          f"{args.count} u32 pointers")
    for r in report["reader"]["readers"]:
        print(f"native reader {r['reader']} in fn {r['function']}, "
              f"stride {r.get('stride')} bytes (at {r.get('stride_at')})")
        print("  -- instruction window --")
        for line in r.get("window", []):
            print(f"    {line}")
        print("  -- BIOS calls made by this function --")
        for call in r.get("bios_calls", []):
            print(f"    {call['call']} -> {call['target']}  svc {call['svc']}")
        sibs = [ld for ld in r.get("literal_loads", [])
                if ld["value"].startswith("0x0853")]
        if sibs:
            print("  -- sibling tables read by the same function --")
            for ld in sibs:
                print(f"    {ld['load']}  -> {ld['value']}")
    for p in report["pairs"]:
        g, c = p["graphics"], p["palette"]
        print(f"  [{p['index']}] gfx {g['addr']} {g['kind']:<5} "
              f"{g.get('decompressed_size', '-')} bytes  {g.get('role', '')}")
        print(f"      pal {c['addr']} {c['kind']:<5} "
              f"{c.get('decompressed_size', '-')} bytes  {c.get('role', '')}")
    print(f"block is a story VM script : {report['block_is_vm_script']}")
    print(f"block is a VM root target  : {report['block_in_story_root_tables']}")

    if args.json:
        write_json(args.json, report)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
