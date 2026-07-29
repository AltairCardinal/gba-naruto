#!/usr/bin/env python3
"""Build the one-byte FFFF control ROM for the character FBFF renderer probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

try:
    from tools.patch_mgba_savestate_memory import patch_savestate
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from patch_mgba_savestate_memory import patch_savestate


BASE_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
SOURCE_STATE_SHA256 = (
    "60028c26e1a529c9542b1e9644dcd35d341cfcfe593cde1b3359c1e2817e3c93"
)
PATCH_OFFSET = 0x25A8E5
EXPECTED_BEFORE = 0xFB
CONTROL_AFTER = 0xFF
TASK_ADDRESS = 0x03005940
SOURCE_TASK = bytes.fromhex(
    "813600c0b00040000000000000010001d80107000100020000009900"
    "4022340834233408ac852b081d040808106c0202000000000000000000000000"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_control_rom(base: bytes) -> tuple[bytes, dict[str, object]]:
    base_sha256 = _sha256(base)
    if base_sha256 != BASE_ROM_SHA256:
        raise ValueError(
            f"base ROM SHA-256 is {base_sha256}; expected {BASE_ROM_SHA256}"
        )
    if base[PATCH_OFFSET] != EXPECTED_BEFORE:
        raise ValueError(
            f"base ROM byte at 0x{PATCH_OFFSET:08X} is "
            f"0x{base[PATCH_OFFSET]:02X}; expected 0x{EXPECTED_BEFORE:02X}"
        )

    control = bytearray(base)
    control[PATCH_OFFSET] = CONTROL_AFTER
    control_bytes = bytes(control)
    report: dict[str, object] = {
        "schema": "character-fbff-control-rom-v1",
        "base_rom_sha256": base_sha256,
        "control_rom_sha256": _sha256(control_bytes),
        "patch": {
            "file_offset": f"0x{PATCH_OFFSET:08X}",
            "gba_address": f"0x{0x08000000 + PATCH_OFFSET:08X}",
            "before": f"0x{EXPECTED_BEFORE:02X}",
            "after": f"0x{CONTROL_AFTER:02X}",
            "meaning": "change the anomalous FBFF trailer to the renderer FFFF terminator",
        },
        "changed_byte_count": 1,
    }
    return control_bytes, report


def build_probe_state(source: bytes) -> tuple[bytes, dict[str, object]]:
    source_sha256 = _sha256(source)
    if source_sha256 != SOURCE_STATE_SHA256:
        raise ValueError(
            f"source state SHA-256 is {source_sha256}; "
            f"expected {SOURCE_STATE_SHA256}"
        )

    task = bytearray(SOURCE_TASK)
    struct.pack_into("<I", task, 0x00, 0xC0003601)
    struct.pack_into("<hh", task, 0x04, 120, 80)
    struct.pack_into("<hh", task, 0x08, 0, 0)
    struct.pack_into("<HH", task, 0x0C, 0x0100, 0x0100)
    struct.pack_into("<HBB", task, 0x10, 0x0300, 0x0E, 0)
    struct.pack_into("<HHHH", task, 0x14, 0, 2, 0, 0)
    struct.pack_into(
        "<IIII",
        task,
        0x1C,
        0x0825A918,
        0x0825A948,
        0x08258CA0,
        0,
    )
    patched = patch_savestate(source, [(TASK_ADDRESS, bytes(task))])
    report: dict[str, object] = {
        "schema": "character-fbff-probe-state-v1",
        "probe_state": {
            "source_state_sha256": source_sha256,
            "patched_state_sha256": _sha256(patched),
            "task_address": f"0x{TASK_ADDRESS:08X}",
            "task_size": len(task),
            "write_count": 1,
            "task_before_hex": SOURCE_TASK.hex(),
            "task_after_hex": bytes(task).hex(),
            "animation_id": 0,
            "keyframe_index": 2,
            "timer": 0,
            "frame_pointer_table": "0x0825A918",
            "animation_pointer_table": "0x0825A948",
            "graphics_pointer": "0x08258CA0",
            "callback": "0x00000000",
        },
    }
    return patched, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    parser.add_argument("output_rom", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--source-state", type=Path)
    parser.add_argument("--output-state", type=Path)
    args = parser.parse_args()
    if (args.source_state is None) != (args.output_state is None):
        parser.error("--source-state and --output-state must be provided together")

    control, report = build_control_rom(args.base_rom.read_bytes())
    if args.source_state is not None:
        patched_state, state_report = build_probe_state(args.source_state.read_bytes())
        args.output_state.parent.mkdir(parents=True, exist_ok=True)
        args.output_state.write_bytes(patched_state)
        report.update(state_report)
    args.output_rom.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output_rom.write_bytes(control)
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
