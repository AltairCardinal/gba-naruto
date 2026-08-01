#!/usr/bin/env python3
"""Bind ninja-tool battlefield objects to their delayed battle-effect actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.thumb_branch import decode_thumb_bl


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
NINJA_TOOL_TABLE = 0x08545BE4
NINJA_TOOL_ENTRY_SIZE = 16
SPECIAL_TOOL_IDS = tuple(range(67, 73))
HANDLER_TABLE = 0x0853E698
SPECIAL_ACTIONS = tuple(range(0xE4, 0xEA))

EVIDENCE_RANGES = {
    "event_action_store": (
        0x080755FA,
        0x08075602,
        "7301adbc80a6e486987c9fb526067ebcc2782875163b1cc96ed46c6013ad4df4",
    ),
    "type_1_object_builder": (
        0x08077514,
        0x08077532,
        "575b1743e7a1467926f7d97c859d3a76c4de7b2deea72bef2a87592ba8c248fa",
    ),
    "object_allocator": (
        0x08081024,
        0x08081084,
        "c2d9429855e9a91fabf5783581a0466a88a63f209dded259c359aef7e5ba73e8",
    ),
    "side_end_controller": (
        0x0807367C,
        0x0807368C,
        "2a0c42d909bf81f19ce2246cc1ce386bc70e97bbcf95ab0842263770d4758622",
    ),
    "expiry_event_builder": (
        0x08081B70,
        0x0808203E,
        "c575f74ad7453e16a348e53fb3dbe352e0f91ea1f181f95a3970b34fb542ff70",
    ),
    "presentation_initializer_call": (
        0x0807ABC8,
        0x0807ABD8,
        "e7256a40f68e7fa059da3cb19d674e72c6c0f49518437f93056d6907beff5d8c",
    ),
    "special_action_threshold": (
        0x0807F4E2,
        0x0807F4F0,
        "f749d481ea36d628ad833f70bb58a565dbef41be35b8b22f41418548a89e04ed",
    ),
    "wide_reset_and_primary_dispatch": (
        0x0807FD0A,
        0x0807FD3E,
        "85af47b24f2632b3b291f9393eb533eb24ff8e3614ef53b6a0565d6a4f0afccf",
    ),
    "native_handler": (
        0x0807F208,
        0x0807F278,
        "56d49600380dd6ecd7830b11fe9fa54851cf9e3b85fa63daec038ff5bed5917a",
    ),
}


def _offset(address: int) -> int:
    return address - ROM_BASE


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _expect_bl(rom: bytes, callsite: int, target: int) -> None:
    actual = decode_thumb_bl(callsite, _u16(rom, callsite), _u16(rom, callsite + 2))
    _expect(actual, target, f"BL at {_hex(callsite)}")


def _validate_code(rom: bytes) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for name, (start, end, expected_hash) in EVIDENCE_RANGES.items():
        raw = rom[_offset(start) : _offset(end)]
        actual_hash = hashlib.sha256(raw).hexdigest()
        _expect(actual_hash, expected_hash, f"{name} SHA-256")
        evidence[name] = {
            "start": _hex(start),
            "end": _hex(end),
            "sha256": actual_hash,
        }

    for callsite, target in (
        (0x0807752C, 0x08081024),
        (0x08073688, 0x08081B70),
        (0x08081CB4, 0x0806D910),
        (0x08081F60, 0x0807AB34),
        (0x0807ABD4, 0x0807F414),
        (0x0807FD14, 0x0807FDCC),
        (0x0807FD3A, 0x0809C114),
    ):
        _expect_bl(rom, callsite, target)

    _expect(_u32(rom, 0x0807FD7C), 0x0000039F, "wide allocator end literal")
    _expect(_u32(rom, 0x0807FD88), HANDLER_TABLE, "primary handler table literal")
    return evidence


def build_battlefield_object_effect_chain_manifest(
    root: Path | str, rom_path: Path | str
) -> dict[str, Any]:
    root = Path(root)
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    _expect(hashlib.sha256(rom).hexdigest(), ROM_SHA256, "ROM SHA-256")
    evidence = _validate_code(rom)

    action_semantics_path = root / "notes/battle-action-template-semantics-bindings-20260723.json"
    action_semantics = json.loads(action_semantics_path.read_text(encoding="utf-8"))
    tool_semantics = {
        row["ninja_tool_id"]: row for row in action_semantics["ninja_tools"]
    }

    mappings = []
    for tool_id, expiry_action in zip(SPECIAL_TOOL_IDS, SPECIAL_ACTIONS, strict=True):
        encoded_action = 0x80 | tool_id
        _expect(encoded_action + 0x21, expiry_action, f"tool {tool_id} expiry action")

        table_offset = _offset(NINJA_TOOL_TABLE) + tool_id * NINJA_TOOL_ENTRY_SIZE
        raw_template = rom[table_offset : table_offset + NINJA_TOOL_ENTRY_SIZE]
        semantics = tool_semantics[tool_id]
        _expect(raw_template.hex(), semantics["source_raw_hex"], f"tool {tool_id} template")
        _expect(raw_template[2] & 0x3F, 0x18, f"tool {tool_id} effect code")
        _expect(semantics["effect"]["handler"], "0x08077514", f"tool {tool_id} resolver")

        handler_offset = _offset(HANDLER_TABLE) + expiry_action * 8
        primary, secondary = struct.unpack_from("<II", rom, handler_offset)
        _expect(primary, 0x0807F209, f"action {expiry_action:02X} primary handler")
        _expect(secondary, 0, f"action {expiry_action:02X} secondary handler")
        mappings.append(
            {
                "ninja_tool_id": tool_id,
                "encoded_action": f"0x{encoded_action:02X}",
                "effect_code": 0x18,
                "effect_flags": raw_template[2] & 0xC0,
                "resolver_handler": "0x08077514",
                "battlefield_object_type": 1,
                "object_encoded_action_offset": 4,
                "expiry_action_delta": 0x21,
                "expiry_action": f"0x{expiry_action:02X}",
                "primary_handler": f"0x{primary:08X}",
                "secondary_handler": None,
            }
        )

    return {
        "schema_version": 1,
        "identity": "ninja_tool_battlefield_object_delayed_effect_chain",
        "rom": str(rom_path),
        "rom_sha256": ROM_SHA256,
        "source_semantics": str(action_semantics_path.relative_to(root)),
        "evidence": evidence,
        "mappings": mappings,
        "chain": {
            "event_action_store": "0x080755FA",
            "type_1_object_builder": "0x08077514",
            "object_allocator_callsite": "0x0807752C",
            "object_allocator": "0x08081024",
            "side_end_caller": "0x08073688",
            "expiry_event_builder": "0x08081B70",
            "object_action_read": "0x08081D74",
            "expiry_action_delta": 0x21,
            "presentation_initializer_callsite": "0x08081F60",
            "presentation_initializer": "0x0807AB34",
            "effect_orchestrator_callsite": "0x0807ABD4",
            "effect_orchestrator": "0x0807F414",
            "special_action_threshold": "action > 0xE3",
            "wide_allocator_reset_callsite": "0x0807FD14",
            "primary_dispatch_load": "0x0807FD28",
            "trampoline_callsite": "0x0807FD3A",
            "native_handler": "0x0807F208",
        },
        "allocator_contract": {
            "start_tile": 0x100,
            "end_tile": 0x39F,
            "palette_bank": 4,
            "palette_count": 14,
        },
        "evidence_level": "static_end_to_end_producer_chain",
        "natural_runtime_observed": False,
        "natural_gameplay_route_closed": False,
        "boundary": (
            "静态证据闭合了忍具 67–72 经 type-1 战场对象到期生成 E4–E9 并分派至原生 "
            "handler 的完整生产链；尚未取得自然装备、选择和到期的运行时命中，因此不计为自然玩法闭环。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battlefield-object-effect-chain-bindings-20260802.json"),
    )
    args = parser.parse_args()
    result = build_battlefield_object_effect_chain_manifest(args.root, args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
