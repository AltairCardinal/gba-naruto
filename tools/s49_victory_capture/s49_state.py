#!/usr/bin/env python3
"""Read the original ROM's live battle state out of an mGBA ``.ss9`` savestate.

This is a self-contained re-implementation of the reader that lives in the
remake line (``tools/butano/read_rom_unit_pool.py``); stream K must not depend
on the remake tree at runtime, so the handful of offsets that matter are
re-stated here and cross-checked against the known battle-14 entry values
(Naruto 138 / Sasuke 104 / Sakura 110 / Konohamaru 40 / five bees 25).

Layout facts (reverse-engineering line, unchanged here):

* unit pool   ``0x020240C0``, stride ``0x1D4``
  ``+0xC1`` acting flag, ``+0xC4`` x, ``+0xC5`` y, ``+0xCC`` affiliation
  (0 = player side, 1 = enemy side)
* HP array    ``0x020242A0``, stride ``0x1D4``, one byte per unit slot

The savestate container is a PNG whose ``gbAs`` chunk holds a zlib stream that
inflates to exactly ``0x61000`` bytes.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GBA_STATE_SIZE = 0x61000
GBA_SAVESTATE_MAGIC = 0x01000000
GBA_SAVESTATE_MAX_VERSION = 0x0000000B

POOL_ADDRESS = 0x020240C0
POOL_STRIDE = 0x1D4
OFFSET_ACTING = 0xC1
OFFSET_X = 0xC4
OFFSET_Y = 0xC5
OFFSET_BACKUP_X = 0xC7
OFFSET_BACKUP_Y = 0xC8
OFFSET_AFFILIATION = 0xCC

HP_ARRAY_ADDRESS = 0x020242A0
HP_STRIDE = 0x1D4

SIDE_NAMES = {0: "player", 1: "enemy"}

# Named pool slots as they appear in the battle-14 roster (C-logic-state.md).
# The pool index is 1-based: index 0 is an empty record, index 1 is Naruto.
SLOT_NAMES = {
    1: "naruto",
    2: "sasuke",
    3: "sakura",
    4: "konohamaru",
    5: "bee-1",
    6: "bee-2",
    7: "bee-3",
    8: "bee-4",
    9: "bee-5",
}
BEE_SLOTS = (5, 6, 7, 8, 9)
ALLY_SLOTS = (1, 2, 3, 4)


class StateError(RuntimeError):
    """The savestate did not yield a trustworthy battle state."""


def _png_chunks(container: bytes) -> list[tuple[bytes, bytes]]:
    if not container.startswith(PNG_SIGNATURE):
        raise StateError("savestate is not a PNG container")
    chunks: list[tuple[bytes, bytes]] = []
    cursor = len(PNG_SIGNATURE)
    while cursor + 12 <= len(container):
        size = struct.unpack_from(">I", container, cursor)[0]
        tag = container[cursor + 4:cursor + 8]
        payload_start = cursor + 8
        payload_end = payload_start + size
        if payload_end + 4 > len(container):
            raise StateError("truncated PNG chunk")
        chunks.append((tag, container[payload_start:payload_end]))
        cursor = payload_end + 4
        if tag == b"IEND":
            break
    return chunks


@dataclass(frozen=True)
class GbaState:
    data: bytes

    @property
    def version_magic(self) -> int:
        return struct.unpack_from("<I", self.data, 0)[0]

    def read_memory(self, address: int, size: int) -> bytes:
        if size < 0:
            raise ValueError("memory read size must be non-negative")
        regions = (
            (0x04000000, 0x00400, 0x00400),
            (0x05000000, 0x00400, 0x00800),
            (0x07000000, 0x00400, 0x00C00),
            (0x06000000, 0x18000, 0x01000),
            (0x03000000, 0x08000, 0x19000),
            (0x02000000, 0x40000, 0x21000),
        )
        for base, length, state_offset in regions:
            relative = address - base
            if 0 <= relative and relative + size <= length:
                start = state_offset + relative
                return self.data[start:start + size]
        raise ValueError(
            f"unsupported savestate read: 0x{address:08X}+0x{size:X}")


def load_state(path: Path | str) -> GbaState:
    container = Path(path).read_bytes()
    payloads = [payload for tag, payload in _png_chunks(container)
                if tag == b"gbAs"]
    if len(payloads) != 1:
        raise StateError(
            f"expected exactly one gbAs chunk, found {len(payloads)}")
    decompressor = zlib.decompressobj()
    try:
        data = decompressor.decompress(payloads[0], GBA_STATE_SIZE + 1)
        data += decompressor.flush()
    except zlib.error as error:
        raise StateError(f"invalid compressed savestate: {error}") from error
    if len(data) != GBA_STATE_SIZE:
        raise StateError(
            f"savestate inflated to {len(data)} bytes, expected {GBA_STATE_SIZE}")
    state = GbaState(data)
    magic = state.version_magic
    if not (GBA_SAVESTATE_MAGIC <= magic
            <= GBA_SAVESTATE_MAGIC + GBA_SAVESTATE_MAX_VERSION):
        raise StateError(f"unsupported savestate magic 0x{magic:08X}")
    return state


def read_pool(state: GbaState, slots: int = 16) -> list[dict[str, object]]:
    """Return every populated pool slot, skipping all-zero records."""
    return parse_pool(state.read_memory(POOL_ADDRESS, POOL_STRIDE * slots),
                      POOL_ADDRESS, slots)


def parse_pool(memory: bytes, base_address: int = POOL_ADDRESS,
               slots: int = 16) -> list[dict[str, object]]:
    """Parse a unit pool out of a raw memory blob.

    ``memory`` holds the bytes starting at ``base_address``; the blob must
    therefore start exactly at the pool base for the slot offsets to line up.
    """
    units: list[dict[str, object]] = []
    for slot in range(slots):
        start = slot * POOL_STRIDE
        record = memory[start:start + POOL_STRIDE]
        if len(record) < POOL_STRIDE or not any(record):
            continue
        affiliation = record[OFFSET_AFFILIATION]
        units.append({
            "slot": slot,
            "name": SLOT_NAMES.get(slot, f"slot-{slot}"),
            "acting": bool(record[OFFSET_ACTING]),
            "address": POOL_ADDRESS + slot * POOL_STRIDE,
            "x": record[OFFSET_X],
            "y": record[OFFSET_Y],
            "backup_x": record[OFFSET_BACKUP_X],
            "backup_y": record[OFFSET_BACKUP_Y],
            "affiliation": affiliation,
            "side": SIDE_NAMES.get(affiliation, f"unknown-{affiliation}"),
        })
    return units


def read_hp(state: GbaState, count: int = 9) -> dict[int, int]:
    """Current HP per pool slot (pool index is 1-based, matching the roster)."""
    return parse_hp(state.read_memory(HP_ARRAY_ADDRESS, HP_STRIDE * count))


def parse_hp(memory: bytes, count: int = 9) -> dict[int, int]:
    """Parse the HP array out of a raw memory blob starting at the array base."""
    hp: dict[int, int] = {}
    for slot in range(1, count + 1):
        index = (slot - 1) * HP_STRIDE
        if index >= len(memory):
            break
        hp[slot] = memory[index]
    return hp


def summarize(state: GbaState) -> dict[str, object]:
    units = read_pool(state)
    hp = read_hp(state)
    return summarize_parts(units, hp)


def summarize_parts(units: list[dict[str, object]],
                    hp: dict[int, int]) -> dict[str, object]:
    for unit in units:
        unit["hp"] = hp.get(int(unit["slot"]))
    return {
        "units": units,
        "hp": hp,
        "acting": [int(u["slot"]) for u in units if u["acting"]],
        "bees_alive": [slot for slot in BEE_SLOTS if hp.get(slot, 0) > 0],
        "bees_dead": [slot for slot in BEE_SLOTS if hp.get(slot, 0) == 0],
        "allies": [slot for slot in ALLY_SLOTS if hp.get(slot, 0) > 0],
    }


def summarize_memory(memory: bytes, base_address: int = POOL_ADDRESS,
                     slots: int = 16) -> dict[str, object]:
    """Summarize a raw memory blob that starts at ``base_address``."""
    units = parse_pool(memory, base_address, slots)
    hp_offset = HP_ARRAY_ADDRESS - base_address
    hp = parse_hp(memory[hp_offset:]) if hp_offset >= 0 else {}
    return summarize_parts(units, hp)


def file_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("savestate")
    args = parser.parse_args(argv)
    state = load_state(args.savestate)
    print(json.dumps(summarize(state), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
