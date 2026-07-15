#!/usr/bin/env python3
"""Inspect CPU, WRAM and cooperative-task state embedded in an mGBA .ss9."""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GBA_STATE_SIZE = 0x61000
TASK_CONTEXT_BASE = 0x03000A88
TASK_CONTEXT_SIZE = 0x4C
TASK_CONTEXT_COUNT = 8


@dataclass(frozen=True)
class GbaState:
    data: bytes

    @property
    def version_magic(self) -> int:
        return struct.unpack_from("<I", self.data, 0)[0]

    @property
    def registers(self) -> tuple[int, ...]:
        return struct.unpack_from("<16I", self.data, 0x20)

    @property
    def cpsr(self) -> int:
        return struct.unpack_from("<I", self.data, 0x60)[0]

    def read_memory(self, address: int, size: int) -> bytes:
        if size < 0:
            raise ValueError("memory read size must be non-negative")
        regions = (
            (0x02000000, 0x40000, 0x21000),
            (0x03000000, 0x08000, 0x19000),
        )
        for base, length, state_offset in regions:
            relative = address - base
            if 0 <= relative and relative + size <= length:
                start = state_offset + relative
                return self.data[start : start + size]
        raise ValueError(
            f"unsupported or out-of-range savestate memory read: "
            f"0x{address:08X}+0x{size:X}"
        )

    def read_u32(self, address: int) -> int:
        return struct.unpack("<I", self.read_memory(address, 4))[0]


def _gbas_payload(png: bytes) -> bytes:
    if not png.startswith(PNG_SIGNATURE):
        raise ValueError("mGBA savestate is not a PNG container")
    cursor = len(PNG_SIGNATURE)
    while cursor + 12 <= len(png):
        size = struct.unpack_from(">I", png, cursor)[0]
        payload_start = cursor + 8
        payload_end = payload_start + size
        chunk_end = payload_end + 4
        if chunk_end > len(png):
            raise ValueError("truncated PNG chunk in mGBA savestate")
        tag = png[cursor + 4 : cursor + 8]
        if tag == b"gbAs":
            return png[payload_start:payload_end]
        cursor = chunk_end
    raise ValueError("mGBA savestate has no gbAs chunk")


def load_gba_state(path: Path | str) -> GbaState:
    payload = _gbas_payload(Path(path).read_bytes())
    try:
        state = zlib.decompress(payload)
    except zlib.error as error:
        raise ValueError(f"invalid compressed gbAs chunk: {error}") from error
    if len(state) != GBA_STATE_SIZE:
        raise ValueError(
            f"decompressed gbAs state is {len(state)} bytes; expected {GBA_STATE_SIZE}"
        )
    version = struct.unpack_from("<I", state, 0)[0]
    if not 0x01000000 <= version <= 0x01000007:
        raise ValueError(f"unsupported GBA savestate version magic 0x{version:08X}")
    return GbaState(state)


def _hex(value: int) -> str:
    return f"0x{value:08X}"


def inspect_savestate(path: Path | str) -> dict[str, object]:
    state = load_gba_state(path)
    registers = state.registers
    tasks = []
    for index in range(TASK_CONTEXT_COUNT):
        address = TASK_CONTEXT_BASE + index * TASK_CONTEXT_SIZE
        raw = state.read_memory(address, TASK_CONTEXT_SIZE)
        task_type = raw[0]
        lr = struct.unpack_from("<I", raw, 8)[0]
        tasks.append(
            {
                "slot": index + 1,
                "type": task_type,
                "delay": raw[1],
                "sp": _hex(struct.unpack_from("<I", raw, 4)[0]),
                "lr": _hex(lr),
                "resume_pc": _hex((lr - 1) & 0xFFFFFFFF if lr & 1 else lr),
            }
        )
    return {
        "schema_version": 1,
        "savestate": str(path),
        "version_magic": _hex(state.version_magic),
        "cpu": {
            "registers": {f"r{index}": _hex(value) for index, value in enumerate(registers)},
            "saved_pc": _hex(registers[15]),
            "current_thumb_pc": _hex((registers[15] - 4) & 0xFFFFFFFF),
            "cpsr": _hex(state.cpsr),
            "thumb": bool(state.cpsr & 0x20),
        },
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("savestate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(inspect_savestate(args.savestate), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
