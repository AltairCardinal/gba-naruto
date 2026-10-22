#!/usr/bin/env python3
"""Independently verify a battlefield-object delayed-effect chain manifest."""

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
TOOL_TABLE_OFFSET = 0x545BE4
TOOL_ENTRY_SIZE = 16
EFFECT_DISPATCH_OFFSET = 0x076F44
HANDLER_TABLE_OFFSET = 0x53E698
RANGES = {
    "event_action_store": (0x755FA, 0x75602, "7301adbc80a6e486987c9fb526067ebcc2782875163b1cc96ed46c6013ad4df4"),
    "type_1_object_builder": (0x77514, 0x77532, "575b1743e7a1467926f7d97c859d3a76c4de7b2deea72bef2a87592ba8c248fa"),
    "object_allocator": (0x81024, 0x81084, "c2d9429855e9a91fabf5783581a0466a88a63f209dded259c359aef7e5ba73e8"),
    "side_end_controller": (0x7367C, 0x7368C, "2a0c42d909bf81f19ce2246cc1ce386bc70e97bbcf95ab0842263770d4758622"),
    "expiry_event_builder": (0x81B70, 0x8203E, "c575f74ad7453e16a348e53fb3dbe352e0f91ea1f181f95a3970b34fb542ff70"),
    "presentation_initializer_call": (0x7ABC8, 0x7ABD8, "e7256a40f68e7fa059da3cb19d674e72c6c0f49518437f93056d6907beff5d8c"),
    "special_action_threshold": (0x7F4E2, 0x7F4F0, "f749d481ea36d628ad833f70bb58a565dbef41be35b8b22f41418548a89e04ed"),
    "wide_reset_and_primary_dispatch": (0x7FD0A, 0x7FD3E, "85af47b24f2632b3b291f9393eb533eb24ff8e3614ef53b6a0565d6a4f0afccf"),
    "native_handler": (0x7F208, 0x7F278, "56d49600380dd6ecd7830b11fe9fa54851cf9e3b85fa63daec038ff5bed5917a"),
}
BOUNDARY = (
    "静态证据闭合了忍具 67–72 经 type-1 战场对象到期生成 E4–E9 并分派至原生 "
    "handler 的完整生产链；尚未取得自然装备、选择和到期的运行时命中，因此不计为自然玩法闭环。"
)


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, address - ROM_BASE)[0]


def _decoded_bl(rom: bytes, callsite: int) -> int:
    return decode_thumb_bl(callsite, _u16(rom, callsite), _u16(rom, callsite + 2))


def verify_manifest(
    root: Path | str, rom_path: Path | str, manifest_path: Path | str
) -> dict[str, Any]:
    root = Path(root)
    rom_path = Path(rom_path)
    rom = Path(rom_path).read_bytes()
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    errors: list[str] = []

    def check(actual: Any, expected: Any, label: str) -> None:
        if actual != expected:
            errors.append(f"{label}: expected {expected!r}, got {actual!r}")

    check(hashlib.sha256(rom).hexdigest(), ROM_SHA256, "rom_sha256")
    check(manifest.get("schema_version"), 1, "schema_version")
    check(
        manifest.get("identity"),
        "ninja_tool_battlefield_object_delayed_effect_chain",
        "identity",
    )
    check(manifest.get("rom_sha256"), ROM_SHA256, "manifest rom_sha256")
    check(manifest.get("rom"), str(rom_path), "rom")
    check(
        manifest.get("source_semantics"),
        "notes/battle-action-template-semantics-bindings-20260723.json",
        "source_semantics",
    )
    check(
        (root / "notes/battle-action-template-semantics-bindings-20260723.json").is_file(),
        True,
        "source_semantics file",
    )
    check(manifest.get("boundary"), BOUNDARY, "boundary")
    check(manifest.get("evidence_level"), "static_end_to_end_producer_chain", "evidence_level")
    check(manifest.get("natural_runtime_observed"), False, "natural_runtime_observed")
    check(manifest.get("natural_gameplay_route_closed"), False, "natural_gameplay_route_closed")
    check(
        manifest.get("chain"),
        {
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
        "chain",
    )

    evidence = manifest.get("evidence", {})
    for name, (start, end, expected_hash) in RANGES.items():
        actual_hash = hashlib.sha256(rom[start:end]).hexdigest()
        check(actual_hash, expected_hash, f"ROM {name} sha256")
        expected_row = {
            "start": f"0x{ROM_BASE + start:08X}",
            "end": f"0x{ROM_BASE + end:08X}",
            "sha256": expected_hash,
        }
        check(evidence.get(name), expected_row, f"evidence.{name}")

    for callsite, target in (
        (0x0807752C, 0x08081024),
        (0x08073688, 0x08081B70),
        (0x08081CB4, 0x0806D910),
        (0x08081F60, 0x0807AB34),
        (0x0807ABD4, 0x0807F414),
        (0x0807FD14, 0x0807FDCC),
        (0x0807FD3A, 0x0809C114),
    ):
        check(_decoded_bl(rom, callsite), target, f"BL 0x{callsite:08X}")

    effect_handler = struct.unpack_from("<I", rom, EFFECT_DISPATCH_OFFSET + (0x18 - 1) * 4)[0]
    check(effect_handler, 0x08077514, "effect 0x18 resolver handler")

    mappings = manifest.get("mappings")
    if not isinstance(mappings, list):
        errors.append("mappings: expected list")
        mappings = []
    check(len(mappings), 6, "mappings length")
    for index, tool_id in enumerate(range(67, 73)):
        if index >= len(mappings):
            break
        row = mappings[index]
        encoded = 0x80 | tool_id
        expiry = encoded + 0x21
        template_offset = TOOL_TABLE_OFFSET + tool_id * TOOL_ENTRY_SIZE
        template = rom[template_offset : template_offset + TOOL_ENTRY_SIZE]
        primary, secondary = struct.unpack_from(
            "<II", rom, HANDLER_TABLE_OFFSET + expiry * 8
        )
        expected = {
            "ninja_tool_id": tool_id,
            "encoded_action": f"0x{encoded:02X}",
            "effect_code": template[2] & 0x3F,
            "effect_flags": template[2] & 0xC0,
            "resolver_handler": f"0x{effect_handler:08X}",
            "battlefield_object_type": 1,
            "object_encoded_action_offset": 4,
            "expiry_action_delta": 0x21,
            "expiry_action": f"0x{expiry:02X}",
            "primary_handler": f"0x{primary:08X}",
            "secondary_handler": None if secondary == 0 else f"0x{secondary:08X}",
        }
        for field, expected_value in expected.items():
            check(row.get(field), expected_value, f"mappings[{index}].{field}")
        check(template[2] & 0x3F, 0x18, f"tool {tool_id} effect_code")
        check(primary, 0x0807F209, f"action {expiry:02X} primary handler")
        check(secondary, 0, f"action {expiry:02X} secondary handler")

    check(
        manifest.get("allocator_contract"),
        {"start_tile": 0x100, "end_tile": 0x39F, "palette_bank": 4, "palette_count": 14},
        "allocator_contract",
    )
    return {"verified": not errors, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    args = parser.parse_args()
    result = verify_manifest(args.root, args.rom, args.manifest)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
