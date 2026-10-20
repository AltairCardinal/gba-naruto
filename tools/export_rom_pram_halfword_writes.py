#!/usr/bin/env python3
"""Inventory the original ROM's half-word writes into palette RAM.

The S49 field unit's outline colour is rewritten every frame: the pixels
that change on each frame transition are exactly the pixels holding one
palette index, and the on-screen colour cycles as ``(0, g, g)`` with
``g = 1, 3, …, 31`` on a 32-frame triangle wave.  That write has to be a
direct ``STRH`` into PRAM, because the reverse tree's copy-queue inventory
(``notes/rom-gpu-copy-queue-inventory-20260730.md``) shows all 14 copy-queue
callers moving whole blocks of 416/352/128/32 bytes and never two bytes.

This exporter turns that claim into a pinned, reproducible inventory:

* it censuses every 32-bit literal in the ROM whose value points into PRAM
  (``0x05000000..0x050003FF``) and finds, for each one, the Thumb
  ``LDR Rt, [PC, #imm]`` that loads it (that encoding is decoded from the
  instruction word directly, so no full-ROM disassembly is needed);
* it attributes each literal to the enclosing function (the nearest
  preceding ``PUSH {…, lr}``);
* it decodes the **known** per-frame outline-colour writer at ``0x0806A7A0``
  (the store is at ``0x0806A7EE``) and records the instructions around it,
  so the address expression ``0x0500021E + bank*32`` and the value expression
  ``(v << 10) | (v << 5)`` are checkable against the bytes.

Scope, stated honestly: the census covers PRAM addresses that reach the
code **through a literal pool**, which is how this game writes them.  A
register-computed PRAM address built without a literal would be missed; the
receipt says so in its ``scope`` block.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Sequence

ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_BASE = 0x08000000
PRAM_START = 0x05000000
PRAM_END = 0x050003FF
PRAM_PALETTE_START = 0x05000000
PRAM_PALETTE_END = 0x050003FF

#: The known per-frame outline-colour writer and its store.
KNOWN_FUNCTION = 0x0806A7A0
KNOWN_STORE = 0x0806A7EE
#: The literal pool entries that hold the palette address of entry 15.
KNOWN_LITERAL_ADDRESSES = (0x0806A7F4, 0x0806A808)
#: How far back to look for the instruction that loads a literal.
LITERAL_LOOKBACK = 512


class PramInventoryError(RuntimeError):
    """The inventory cannot be produced as declared."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_rom(path: Path) -> bytes:
    data = Path(path).read_bytes()
    digest = sha256_bytes(data)
    if digest != ROM_SHA256:
        raise PramInventoryError(
            f"ROM sha256 {digest} does not match the expected {ROM_SHA256}"
        )
    return data


def pram_literals(rom: bytes) -> list[tuple[int, int]]:
    """Every file offset whose 32-bit little-endian value points into PRAM."""
    found: list[tuple[int, int]] = []
    for offset in range(0, len(rom) - 3):
        value = int.from_bytes(rom[offset:offset + 4], "little")
        if PRAM_START <= value <= PRAM_END:
            found.append((offset, value))
    return found


def thumb_literal_targets(rom: bytes, literal_offset: int) -> list[int]:
    """Addresses of Thumb ``LDR Rt, [PC, #imm]`` instructions that load it.

    The encoding is ``0x4800 | (imm8 << 8) | (rt << 8)``-style: the word's
    bits 15..11 are ``01001`` and bits 10..8 hold the register, bits 7..0 the
    immediate.  The target is ``((pc + 4) & ~3) + imm8 * 4`` where ``pc`` is
    the instruction's own address.
    """
    hits: list[int] = []
    start = max(0, literal_offset - LITERAL_LOOKBACK)
    start &= ~1
    for offset in range(start, literal_offset, 2):
        word = struct.unpack_from("<H", rom, offset)[0]
        if (word & 0xF800) != 0x4800:
            continue
        address = ROM_BASE + offset
        # Thumb LDR (literal): 01001 Rt(3) imm8(8) -- the immediate lives in
        # the low byte and is scaled by four.
        immediate = word & 0xFF
        target = ((address + 4) & ~3) + immediate * 4
        if target == ROM_BASE + literal_offset:
            hits.append(address)
    return hits


def thumb_push_lr(rom: bytes, address: int, limit: int = 4096) -> int | None:
    """The nearest preceding Thumb ``PUSH {…, lr}`` at or before ``address``.

    The candidate is verified with the disassembler, because a literal pool
    word can decode as a PUSH by accident.
    """
    offset = (address - ROM_BASE) & ~1
    floor = max(0, offset - limit)
    candidates = []
    for position in range(offset, floor - 1, -2):
        word = struct.unpack_from("<H", rom, position)[0]
        if (word & 0xFF00) == 0xB500 and (word & 0x0100):
            candidates.append(position)
            break
    if not candidates:
        return None
    position = candidates[0]
    try:
        records = decode_window(rom, ROM_BASE + position, length=4)
    except Exception:  # pragma: no cover - defensive
        return None
    if not records:
        return None
    record = records[0]
    if record["mnemonic"] != "push" or "lr" not in record["operands"]:
        return None
    return ROM_BASE + position


def _capstone():
    try:
        import capstone  # type: ignore
    except ImportError:  # pragma: no cover - vendored fallback
        import sys

        root = str(Path(__file__).resolve().parents[1])
        if root not in sys.path:
            sys.path.insert(0, root)
        from tools._vendor import capstone  # type: ignore
    return capstone


def decode_window(rom: bytes, address: int, length: int = 96) -> list[dict[str, Any]]:
    """Disassemble a Thumb window into a list of records."""
    capstone = _capstone()
    offset = (address - ROM_BASE) & ~1
    code = rom[offset:offset + length]
    engine = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    engine.detail = False
    records = []
    for instruction in engine.disasm(code, address):
        records.append(
            {
                "address": instruction.address,
                "bytes": instruction.bytes.hex(),
                "mnemonic": instruction.mnemonic,
                "operands": instruction.op_str,
            }
        )
    return records


def build_inventory(rom_path: Path) -> dict[str, Any]:
    rom = load_rom(rom_path)
    literals = pram_literals(rom)

    entries: list[dict[str, Any]] = []
    for offset, value in literals:
        address = ROM_BASE + offset
        references = thumb_literal_targets(rom, offset)
        entries.append(
            {
                "literal_address": address,
                "literal_value": f"0x{value:08X}",
                "pram_offset": value - PRAM_PALETTE_START,
                "referenced_by": references,
                "function": (
                    thumb_push_lr(rom, references[0]) if references else None
                ),
            }
        )

    known_entries = [
        entry
        for entry in entries
        if entry["literal_address"] in KNOWN_LITERAL_ADDRESSES
    ]
    known_window = decode_window(rom, KNOWN_FUNCTION, length=192)
    store = next(
        (
            record
            for record in known_window
            if record["address"] == KNOWN_STORE
        ),
        None,
    )

    return {
        "schema": "konoha.rom-pram-halfword-writes.v1",
        "rom": {
            "path": str(rom_path),
            "sha256": ROM_SHA256,
            "bytes": len(rom),
        },
        "counts": {
            "pram_literal_occurrences": len(entries),
            "distinct_pram_literal_values": len(
                {entry["literal_value"] for entry in entries}
            ),
            "literals_with_a_thumb_reference": sum(
                1 for entry in entries if entry["referenced_by"]
            ),
        },
        "known_outline_write": {
            "function": KNOWN_FUNCTION,
            "store": KNOWN_STORE,
            "literal_pool_entries": list(KNOWN_LITERAL_ADDRESSES),
            "store_instruction": store,
            "window": known_window,
            "address_expression": "0x0500021E + bank * 32",
            "value_expression": "(v << 10) | (v << 5)",
            "wave": "v = (global & 0xF) * 2 + 1  ->  1,3,5,...,31 over 32 frames",
        },
        "entries": entries,
        "scope": {
            "covers": (
                "PRAM addresses that reach the code through a 32-bit literal "
                "pool, which is how this game writes them; for each such "
                "literal the referencing Thumb LDR and the enclosing function"
            ),
            "does_not_cover": (
                "a register-computed PRAM address built without any literal; "
                "writes through the GPU copy queue (those are whole-block "
                "copies and are inventoried separately in the reverse tree)"
            ),
            "known_site_confirmed": bool(known_entries) and store is not None,
        },
    }


def write_inventory(payload: dict[str, Any], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "pram-halfword-writes.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        type=Path,
        default=Path("rom/base.gba"),
        help="the original ROM (its sha256 is verified)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/rom-pram-halfword-writes-v1"),
    )
    args = parser.parse_args(argv)
    try:
        payload = build_inventory(args.rom)
    except (PramInventoryError, OSError) as error:
        print(f"export_rom_pram_halfword_writes: {error}")
        return 2
    path = write_inventory(payload, args.out_dir)
    print(
        json.dumps(
            {
                "out": str(path),
                "literal_occurrences": payload["counts"]["pram_literal_occurrences"],
                "distinct_values": payload["counts"]["distinct_pram_literal_values"],
                "known_site_confirmed": payload["scope"]["known_site_confirmed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
