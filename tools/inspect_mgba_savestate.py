#!/usr/bin/env python3
"""Inspect CPU, WRAM and cooperative-task state embedded in an mGBA .ss9."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

try:
    from tools.thumb_branch import decode_thumb_bl
except ModuleNotFoundError:
    from thumb_branch import decode_thumb_bl


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
                return self.data[start : start + size]
        raise ValueError(
            f"unsupported or out-of-range savestate memory read: "
            f"0x{address:08X}+0x{size:X}"
        )

    def read_u32(self, address: int) -> int:
        return struct.unpack("<I", self.read_memory(address, 4))[0]


def _gbas_payload(png: bytes) -> bytes:
    chunks = _validated_png_chunks(png)
    payloads = [payload for tag, payload in chunks if tag == b"gbAs"]
    if len(payloads) != 1:
        raise ValueError(
            f"mGBA savestate must contain exactly one gbAs chunk; found {len(payloads)}"
        )
    return payloads[0]


def _validated_png_chunks(png: bytes) -> list[tuple[bytes, bytes]]:
    if not png.startswith(PNG_SIGNATURE):
        raise ValueError("screen image is not a PNG container")
    chunks: list[tuple[bytes, bytes]] = []
    cursor = len(PNG_SIGNATURE)
    saw_iend = False
    while cursor < len(png):
        if cursor + 12 > len(png):
            raise ValueError("truncated PNG chunk header")
        size = struct.unpack_from(">I", png, cursor)[0]
        payload_start = cursor + 8
        payload_end = payload_start + size
        chunk_end = payload_end + 4
        if chunk_end > len(png):
            raise ValueError("truncated PNG chunk payload")
        tag = png[cursor + 4 : cursor + 8]
        payload = png[payload_start:payload_end]
        stored_crc = struct.unpack_from(">I", png, payload_end)[0]
        actual_crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        if stored_crc != actual_crc:
            raise ValueError(f"PNG {tag!r} CRC mismatch")
        chunks.append((tag, payload))
        cursor = chunk_end
        if tag == b"IEND":
            if payload:
                raise ValueError("PNG IEND chunk must be empty")
            saw_iend = True
            if cursor != len(png):
                raise ValueError("PNG contains data after IEND")
            break
    if not saw_iend:
        raise ValueError("PNG has no IEND chunk")
    return chunks


def _strict_zlib_decompress(
    payload: bytes, *, expected_size: int, label: str
) -> bytes:
    decompressor = zlib.decompressobj()
    try:
        data = decompressor.decompress(payload, expected_size + 1)
        if decompressor.unconsumed_tail:
            raise ValueError(f"{label} exceeds its expected decompressed size")
        data += decompressor.flush()
    except zlib.error as error:
        raise ValueError(f"invalid compressed {label}: {error}") from error
    if not decompressor.eof:
        raise ValueError(f"truncated compressed {label}")
    if decompressor.unused_data:
        raise ValueError(f"compressed {label} has trailing unused data")
    if decompressor.unconsumed_tail:
        raise ValueError(f"compressed {label} has an unconsumed tail")
    if len(data) != expected_size:
        raise ValueError(
            f"decompressed {label} is {len(data)} bytes; expected {expected_size}"
        )
    return data


def _paeth_predictor(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def _unfilter_rgb8(scanlines: bytes, *, width: int, height: int) -> bytes:
    bytes_per_pixel = 3
    stride = width * bytes_per_pixel
    pixels = bytearray()
    previous = bytes(stride)
    cursor = 0
    for row_index in range(height):
        filter_type = scanlines[cursor]
        cursor += 1
        if filter_type not in range(5):
            raise ValueError(
                f"PNG row {row_index} has invalid filter type {filter_type}"
            )
        encoded = scanlines[cursor : cursor + stride]
        cursor += stride
        row = bytearray(stride)
        for index, value in enumerate(encoded):
            left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            up = previous[index]
            upper_left = (
                previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            )
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            else:
                predictor = _paeth_predictor(left, up, upper_left)
            row[index] = (value + predictor) & 0xFF
        pixels.extend(row)
        previous = row
    return bytes(pixels)


def png_screen_fingerprint(path: Path | str) -> dict[str, object]:
    """Hash normalized RGB pixels from a strictly validated PNG container."""

    chunks = _validated_png_chunks(Path(path).read_bytes())
    ihdr_chunks = [payload for tag, payload in chunks if tag == b"IHDR"]
    idat_chunks = [payload for tag, payload in chunks if tag == b"IDAT"]
    if len(ihdr_chunks) != 1 or chunks[0][0] != b"IHDR":
        raise ValueError("PNG must contain exactly one leading IHDR chunk")
    if not idat_chunks:
        raise ValueError("PNG has no IDAT chunks")
    ihdr = ihdr_chunks[0]
    if len(ihdr) != 13:
        raise ValueError("PNG IHDR has invalid length")
    width, height, bit_depth, color_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", ihdr)
    )
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive")
    if (bit_depth, color_type, compression, filtering, interlace) != (8, 2, 0, 0, 0):
        raise ValueError("screen fingerprint requires non-interlaced RGB8 PNG")
    expected_size = height * (1 + width * 3)
    scanlines = _strict_zlib_decompress(
        b"".join(idat_chunks),
        expected_size=expected_size,
        label="PNG IDAT scanlines",
    )
    pixels = _unfilter_rgb8(scanlines, width=width, height=height)
    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "ihdr_sha256": hashlib.sha256(ihdr).hexdigest(),
        "rgb_pixels_length": len(pixels),
        "rgb_pixels_sha256": hashlib.sha256(pixels).hexdigest(),
    }


def load_gba_state(path: Path | str) -> GbaState:
    payload = _gbas_payload(Path(path).read_bytes())
    state = _strict_zlib_decompress(
        payload, expected_size=GBA_STATE_SIZE, label="gbAs state"
    )
    version = struct.unpack_from("<I", state, 0)[0]
    if not 0x01000000 <= version <= 0x01000007:
        raise ValueError(f"unsupported GBA savestate version magic 0x{version:08X}")
    return GbaState(state)


def _hex(value: int) -> str:
    return f"0x{value:08X}"


def inspect_savestate(
    path: Path | str,
    *,
    rom_path: Path | str | None = None,
    task_slot: int | None = None,
    unwind_frames: list[tuple[int, int]] | None = None,
    memory_bytes: list[int] | None = None,
) -> dict[str, object]:
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
    report: dict[str, object] = {
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
    if memory_bytes:
        report["memory_bytes"] = {
            _hex(address): state.read_memory(address, 1)[0] for address in memory_bytes
        }
    if unwind_frames is not None:
        if rom_path is None or task_slot is None:
            raise ValueError("explicit unwind requires rom_path and task_slot")
        if not 1 <= task_slot <= TASK_CONTEXT_COUNT:
            raise ValueError(f"task_slot must be between 1 and {TASK_CONTEXT_COUNT}")
        if not unwind_frames:
            raise ValueError("explicit unwind requires at least one frame")
        rom = Path(rom_path).read_bytes()
        task = tasks[task_slot - 1]
        task_sp = int(task["sp"], 16)
        previous_address = task_sp - 1
        frames = []
        for stack_address, expected_target in unwind_frames:
            if stack_address < task_sp or stack_address <= previous_address:
                raise ValueError("explicit unwind stack addresses must increase from task SP")
            raw_return = state.read_u32(stack_address)
            if raw_return & 1 == 0:
                raise ValueError(
                    f"stack return at {_hex(stack_address)} is not a Thumb return"
                )
            callsite = raw_return - 5
            rom_offset = callsite - 0x08000000
            if rom_offset < 0 or rom_offset + 4 > len(rom):
                raise ValueError(
                    f"stack return at {_hex(stack_address)} maps outside ROM"
                )
            first, second = struct.unpack_from("<HH", rom, rom_offset)
            decoded_target = decode_thumb_bl(callsite, first, second)
            if decoded_target != expected_target:
                decoded = "not BL" if decoded_target is None else _hex(decoded_target)
                raise ValueError(
                    f"BL target mismatch at {_hex(callsite)}: "
                    f"decoded {decoded}, expected {_hex(expected_target)}"
                )
            frames.append(
                {
                    "stack_address": _hex(stack_address),
                    "raw_return_word": _hex(raw_return),
                    "resume_pc": _hex(raw_return - 1),
                    "callsite": _hex(callsite),
                    "decoded_target": _hex(decoded_target),
                }
            )
            previous_address = stack_address
        report["active_unwind"] = {
            "task_slot": task_slot,
            "task_sp": task["sp"],
            "selection": "explicit-stack-slots-with-static-thumb-bl-validation",
            "raw_return_words": [frame["raw_return_word"] for frame in frames],
            "frames": frames,
        }
    return report


def _parse_int(value: str) -> int:
    return int(value, 0)


def _parse_unwind_frame(value: str) -> tuple[int, int]:
    try:
        address, target = value.split(":", 1)
        return _parse_int(address), _parse_int(target)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected STACK_ADDRESS:BL_TARGET") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("savestate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--task-slot", type=int)
    parser.add_argument("--unwind-return", type=_parse_unwind_frame, action="append")
    parser.add_argument("--memory-byte", type=_parse_int, action="append")
    args = parser.parse_args()
    rendered = json.dumps(
        inspect_savestate(
            args.savestate,
            rom_path=args.rom,
            task_slot=args.task_slot,
            unwind_frames=args.unwind_return,
            memory_bytes=args.memory_byte,
        ),
        indent=2,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
