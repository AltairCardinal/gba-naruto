#!/usr/bin/env python3
"""Patch explicit memory bytes in an mGBA PNG-container savestate."""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

try:
    from tools.inspect_mgba_savestate import (
        GBA_STATE_SIZE,
        PNG_SIGNATURE,
        _strict_zlib_decompress,
        _validated_png_chunks,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from inspect_mgba_savestate import (
        GBA_STATE_SIZE,
        PNG_SIGNATURE,
        _strict_zlib_decompress,
        _validated_png_chunks,
    )


MEMORY_REGIONS = (
    (0x04000000, 0x00400, 0x00400),
    (0x05000000, 0x00400, 0x00800),
    (0x07000000, 0x00400, 0x00C00),
    (0x06000000, 0x18000, 0x01000),
    (0x03000000, 0x08000, 0x19000),
    (0x02000000, 0x40000, 0x21000),
)


def _state_offset(address: int, size: int) -> int:
    if size <= 0:
        raise ValueError("savestate writes must not be empty")
    for base, length, state_offset in MEMORY_REGIONS:
        relative = address - base
        if 0 <= relative and relative + size <= length:
            return state_offset + relative
    raise ValueError(f"unsupported savestate memory write: 0x{address:08X}+0x{size:X}")


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


def patch_savestate(container: bytes, writes: list[tuple[int, bytes]]) -> bytes:
    spans = sorted((address, address + len(payload)) for address, payload in writes)
    for index, (start, end) in enumerate(spans):
        if index and start < spans[index - 1][1]:
            raise ValueError("savestate memory writes overlap")
        _state_offset(start, end - start)

    chunks = _validated_png_chunks(container)
    payload_indices = [index for index, (tag, _) in enumerate(chunks) if tag == b"gbAs"]
    if len(payload_indices) != 1:
        raise ValueError(
            f"mGBA savestate must contain exactly one gbAs chunk; found {len(payload_indices)}"
        )
    payload_index = payload_indices[0]
    state = bytearray(
        _strict_zlib_decompress(
            chunks[payload_index][1], expected_size=GBA_STATE_SIZE, label="gbAs state"
        )
    )
    for address, payload in writes:
        offset = _state_offset(address, len(payload))
        state[offset : offset + len(payload)] = payload

    chunks[payload_index] = (b"gbAs", zlib.compress(state))
    return PNG_SIGNATURE + b"".join(_png_chunk(tag, payload) for tag, payload in chunks)


def _parse_write(value: str) -> tuple[int, bytes]:
    try:
        address_text, payload_text = value.split(":", 1)
        return int(address_text, 0), bytes.fromhex(payload_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("write must be ADDRESS:HEX_BYTES") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--write", action="append", type=_parse_write, required=True)
    args = parser.parse_args()
    patched = patch_savestate(args.source.read_bytes(), args.write)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patched)
    print(f"wrote {args.output} with {len(args.write)} explicit memory write(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
