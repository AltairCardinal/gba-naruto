#!/usr/bin/env python3
"""Read WRAM out of an mGBA ``.ss9`` savestate without an emulator.

Why this tool exists
--------------------
Wave 20 / stream E4 has to answer "where do the original settlement numbers
live?" for the remake line (stream E2).  The reverse-engineering line keeps the
*original* ROM checkpoints (``artifacts/runtime-checkpoints/*.ss9``) but those are
read-only and there is no tool there that dumps a WRAM window.

The savestate container is a PNG whose ``gbAs`` chunk holds a zlib stream that
inflates to exactly ``0x61000`` bytes.  Region layout (mGBA 0.10.x, version
magic ``0x0100000B``):

    0x04000000 I/O    0x400 bytes  @ state offset 0x00400
    0x05000000 palette 0x800 bytes @ state offset 0x00800
    0x07000000 VRAM   0xC00 bytes  @ state offset 0x00C00
    0x06000000 OAM    0x18000      @ state offset 0x01000
    0x03000000 IWRAM  0x8000       @ state offset 0x19000
    0x02000000 EWRAM  0x40000      @ state offset 0x21000

Battle unit pool facts (reverse-engineering line, re-stated here):

    unit pool  0x020240C0, stride 0x1D4
    HP array   0x020242A0, stride 0x1D4, one byte per slot
    control    0x02026804 .. 0x0202680B (8 bytes)

Usage::

    python tools/s49_w20e/ss9_wram.py dump  --state <a.ss9> --out <a.bin>
    python tools/s49_w20e/ss9_wram.py find  --state <a.ss9> --value 150 --width 2
    python tools/s49_w20e/ss9_wram.py pool  --state <a.ss9> --slots 21
    python tools/s49_w20e/ss9_wram.py diff  --state <a.ss9> --state <b.ss9> \
        --values 100,50,0,150
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GBA_STATE_SIZE = 0x61000
GBA_SAVESTATE_MAGIC = 0x01000000
GBA_SAVESTATE_MAX_VERSION = 0x0000000B

REGIONS = (
    (0x04000000, 0x00400, 0x00400, "io"),
    (0x05000000, 0x00800, 0x00800, "palette"),
    (0x07000000, 0x00C00, 0x00C00, "vram"),
    (0x06000000, 0x18000, 0x01000, "oam"),
    (0x03000000, 0x08000, 0x19000, "iwram"),
    (0x02000000, 0x40000, 0x21000, "ewram"),
)

POOL_ADDRESS = 0x020240C0
POOL_STRIDE = 0x1D4
HP_ARRAY_ADDRESS = 0x020242A0
BATTLE_CONTROL = 0x02026804


class StateError(RuntimeError):
    """The savestate did not yield a trustworthy memory image."""


def file_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    path: str

    @property
    def version_magic(self) -> int:
        return struct.unpack_from("<I", self.data, 0)[0]

    def read_memory(self, address: int, size: int) -> bytes:
        if size < 0:
            raise ValueError("memory read size must be non-negative")
        for base, length, state_offset, _name in REGIONS:
            relative = address - base
            if 0 <= relative and relative + size <= length:
                start = state_offset + relative
                return self.data[start:start + size]
        raise ValueError(
            f"unsupported or out-of-range savestate read: 0x{address:08X}+0x{size:X}")

    def read_u16(self, address: int) -> int:
        return struct.unpack("<H", self.read_memory(address, 2))[0]

    def read_u32(self, address: int) -> int:
        return struct.unpack("<I", self.read_memory(address, 4))[0]


def load_state(path: Path | str) -> GbaState:
    container = Path(path).read_bytes()
    payloads = [payload for tag, payload in _png_chunks(container) if tag == b"gbAs"]
    if len(payloads) != 1:
        raise StateError(f"expected exactly one gbAs chunk, found {len(payloads)}")
    decompressor = zlib.decompressobj()
    try:
        data = decompressor.decompress(payloads[0], GBA_STATE_SIZE + 1)
        data += decompressor.flush()
    except zlib.error as error:
        raise StateError(f"invalid compressed savestate: {error}") from error
    if len(data) != GBA_STATE_SIZE:
        raise StateError(
            f"savestate inflated to {len(data)} bytes, expected {GBA_STATE_SIZE}")
    state = GbaState(data, str(path))
    magic = state.version_magic
    if not (GBA_SAVESTATE_MAGIC <= magic <= GBA_SAVESTATE_MAGIC + GBA_SAVESTATE_MAX_VERSION):
        raise StateError(f"unsupported savestate magic 0x{magic:08X}")
    return state


def _region_of(address: int) -> str:
    for base, length, _offset, name in REGIONS:
        if base <= address < base + length:
            return name
    return "?"


def cmd_dump(args: argparse.Namespace) -> int:
    state = load_state(args.state)
    if args.ewram:
        payload = state.read_memory(0x02000000, 0x40000)
        out = Path(args.out) if args.out else Path(args.state).with_suffix(".ewram.bin")
        out.write_bytes(payload)
        print(json.dumps({
            "state": str(args.state),
            "state_sha256": file_sha256(args.state),
            "region": "ewram",
            "base": "0x02000000",
            "length": len(payload),
            "out": str(out),
        }, indent=2))
        return 0
    address = int(args.address, 0)
    size = int(args.size, 0)
    payload = state.read_memory(address, size)
    out = Path(args.out) if args.out else None
    if out:
        out.write_bytes(payload)
    print(json.dumps({
        "state": str(args.state),
        "region": _region_of(address),
        "base": f"0x{address:08X}",
        "length": len(payload),
        "out": str(out) if out else None,
    }, indent=2))
    return 0


def _scan(state: GbaState, value: int, width: int, base: int, length: int) -> list[int]:
    blob = state.read_memory(base, length)
    fmt = {1: "<B", 2: "<H", 4: "<I"}[width]
    hits: list[int] = []
    for offset in range(0, length - width + 1):
        if struct.unpack_from(fmt, blob, offset)[0] == value:
            hits.append(base + offset)
    return hits


def cmd_find(args: argparse.Namespace) -> int:
    state = load_state(args.state)
    base = int(args.base, 0)
    length = int(args.length, 0)
    report = []
    for value in args.value:
        hits = _scan(state, value, args.width, base, length)
        report.append({
            "value": value,
            "width": args.width,
            "count": len(hits),
            "addresses": [f"0x{address:08X}" for address in hits[:args.limit]],
            "truncated": len(hits) > args.limit,
        })
    print(json.dumps({
        "state": str(args.state),
        "state_sha256": file_sha256(args.state),
        "base": f"0x{base:08X}",
        "length": length,
        "results": report,
    }, indent=2))
    return 0


def cmd_pool(args: argparse.Namespace) -> int:
    state = load_state(args.state)
    slots = []
    for slot in range(1, args.slots + 1):
        base = POOL_ADDRESS + slot * POOL_STRIDE
        record = state.read_memory(base, POOL_STRIDE)
        if not any(record):
            continue
        hp_base = HP_ARRAY_ADDRESS + (slot - 1) * POOL_STRIDE
        slots.append({
            "slot": slot,
            "address": f"0x{base:08X}",
            "character_id": record[0],
            "hp": state.read_memory(hp_base, 1)[0],
            "flags_c0_c8": record[0xC0:0xC9].hex(),
            "affiliation": record[0xCC],
            "nonzero_offsets": [
                f"0x{offset:03X}" for offset, byte in enumerate(record) if byte
            ],
            "record_head_hex": record[:0x40].hex(),
        })
    print(json.dumps({
        "state": str(args.state),
        "state_sha256": file_sha256(args.state),
        "pool_base": f"0x{POOL_ADDRESS:08X}",
        "pool_stride": f"0x{POOL_STRIDE:X}",
        "hp_array_base": f"0x{HP_ARRAY_ADDRESS:08X}",
        "battle_control": state.read_memory(BATTLE_CONTROL, 8).hex(),
        "slots": slots,
    }, indent=2))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    left = load_state(args.state)
    right = load_state(args.other)
    base = int(args.base, 0)
    length = int(args.length, 0)
    left_blob = left.read_memory(base, length)
    right_blob = right.read_memory(base, length)
    wanted = set(args.value)
    hits = []
    for offset in range(0, length - 3):
        left_u16 = struct.unpack_from("<H", left_blob, offset)[0]
        right_u16 = struct.unpack_from("<H", right_blob, offset)[0]
        if left_u16 not in wanted:
            continue
        if left_u16 == right_u16:
            continue
        hits.append({
            "address": f"0x{base + offset:08X}",
            "left_u16": left_u16,
            "right_u16": right_u16,
            "left_u32": struct.unpack_from("<I", left_blob, offset)[0],
            "right_u32": struct.unpack_from("<I", right_blob, offset)[0],
            "left_bytes": left_blob[offset:offset + 8].hex(),
            "right_bytes": right_blob[offset:offset + 8].hex(),
        })
    print(json.dumps({
        "left": str(args.state),
        "left_sha256": file_sha256(args.state),
        "right": str(args.other),
        "right_sha256": file_sha256(args.other),
        "base": f"0x{base:08X}",
        "length": length,
        "values": sorted(wanted),
        "hits": hits[:args.limit],
        "hit_count": len(hits),
    }, indent=2))
    return 0


def cmd_screen(args: argparse.Namespace) -> int:
    """Extract the screen image that mGBA embeds in the savestate PNG."""
    import struct as _struct

    container = Path(args.state).read_bytes()
    chunks = _png_chunks(container)
    ihdr = next(payload for tag, payload in chunks if tag == b"IHDR")
    width, height, bit_depth, color_type, _c, _f, interlace = _struct.unpack(
        ">IIBBBBB", ihdr)
    if (bit_depth, color_type, interlace) != (8, 2, 0):
        raise StateError(
            f"unexpected screen PNG format: depth={bit_depth} color={color_type} "
            f"interlace={interlace}")
    idat = b"".join(payload for tag, payload in chunks if tag == b"IDAT")
    raw = zlib.decompress(idat)
    stride = width * 3
    expected = height * (1 + stride)
    if len(raw) != expected:
        raise StateError(f"screen PNG payload is {len(raw)} bytes, expected {expected}")
    out = Path(args.out) if args.out else Path(args.state).with_suffix(".screen.png")
    out.write_bytes(container)
    print(json.dumps({
        "state": str(args.state),
        "state_sha256": file_sha256(args.state),
        "width": width,
        "height": height,
        "out": str(out),
        "note": "the savestate PNG already carries the emulator frame; copied verbatim",
    }, indent=2))
    return 0


def cmd_io(args: argparse.Namespace) -> int:
    """Read the GBA I/O registers (display + BG scroll) out of a savestate."""
    state = load_state(args.state)
    registers = {
        0x04000000: "DISPCNT",
        0x04000004: "DISPSTAT",
        0x04000010: "BG0HOFS",
        0x04000012: "BG0VOFS",
        0x04000014: "BG1HOFS",
        0x04000016: "BG1VOFS",
        0x04000018: "BG2HOFS",
        0x0400001A: "BG2VOFS",
        0x0400001C: "BG3HOFS",
        0x0400001E: "BG3VOFS",
        0x04000040: "WINH",
        0x04000042: "WINV",
    }
    values = {}
    for address, name in registers.items():
        try:
            raw = state.read_memory(address, 2)
        except ValueError:
            continue
        values[name] = {
            "address": f"0x{address:08X}",
            "u16": int.from_bytes(raw, "little"),
            "hex": f"0x{int.from_bytes(raw, 'little'):04X}",
        }
    print(json.dumps({
        "state": str(args.state),
        "state_sha256": file_sha256(args.state),
        "registers": values,
    }, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    dump = sub.add_parser("dump", help="dump a WRAM window to a .bin file")
    dump.add_argument("--state", required=True)
    dump.add_argument("--address", default="0x02000000")
    dump.add_argument("--size", default="0x40000")
    dump.add_argument("--ewram", action="store_true")
    dump.add_argument("--out")
    dump.set_defaults(func=cmd_dump)

    find = sub.add_parser("find", help="find u8/u16/u32 values inside a WRAM window")
    find.add_argument("--state", required=True)
    find.add_argument("--value", type=int, action="append", required=True)
    find.add_argument("--width", type=int, default=2, choices=(1, 2, 4))
    find.add_argument("--base", default="0x02000000")
    find.add_argument("--length", default="0x40000")
    find.add_argument("--limit", type=int, default=200)
    find.set_defaults(func=cmd_find)

    pool = sub.add_parser("pool", help="decode the original battle unit pool")
    pool.add_argument("--state", required=True)
    pool.add_argument("--slots", type=int, default=21)
    pool.set_defaults(func=cmd_pool)

    diff = sub.add_parser("diff", help="addresses holding a value in A but not in B")
    diff.add_argument("--state", required=True)
    diff.add_argument("--other", required=True)
    diff.add_argument("--value", type=int, action="append", required=True)
    diff.add_argument("--base", default="0x02000000")
    diff.add_argument("--length", default="0x40000")
    diff.add_argument("--limit", type=int, default=400)
    diff.set_defaults(func=cmd_diff)

    screen = sub.add_parser("screen", help="copy the savestate's embedded screen PNG")
    screen.add_argument("--state", required=True)
    screen.add_argument("--out")
    screen.set_defaults(func=cmd_screen)

    io_cmd = sub.add_parser("io", help="read display + BG scroll registers")
    io_cmd.add_argument("--state", required=True)
    io_cmd.set_defaults(func=cmd_io)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
