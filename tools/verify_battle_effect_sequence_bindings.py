#!/usr/bin/env python3
"""Independently verify battle-effect action and sequence bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
RUNTIME_TABLE_OFFSET = 0x53E596
RUNTIME_STATE_COUNT = 256
RUNTIME_TABLE_SHA256 = (
    "4c1ad8b8ac883eb301132c83258ba1e1216b2e131c9ce9866d0de62956d5a01b"
)
ACTIVE_ACTION_COUNT = 87
ACTIVE_ACTION_SLICE_SHA256 = (
    "373b8c02a0e768f15843be31a3f1282346986fd9bb52584be5649e3f01696b22"
)
ACTIVE_TEMPLATE_TABLE_OFFSET = 0x545458
ACTIVE_TEMPLATE_ENTRY_SIZE = 16
ACTIVE_TEMPLATE_TABLE_SHA256 = (
    "d36979d06334807da33a348174de6de4bb834bca762bbb3d23deb2472a2aa966"
)
NINJA_TOOL_ENCODING_FLAG = 0x80
NINJA_TOOL_COUNT = 94
NINJA_TOOL_SELECTOR_SLICE_SHA256 = (
    "7b329765f680d1638a5899bfa67b3501e8c32cda6399a83b38ef88b35c21cfb4"
)
NINJA_TOOL_TEMPLATE_TABLE_OFFSET = 0x545BE4
NINJA_TOOL_TEMPLATE_ENTRY_SIZE = 16
NINJA_TOOL_TEMPLATE_TABLE_SHA256 = (
    "e586bbeeb364a14639e5062491c26c163905cb4c5501985bbafb5ed0ba3cd0fd"
)
DESCRIPTOR_TABLE_OFFSET = 0x53EF30
DESCRIPTOR_COUNT = 22
DESCRIPTOR_SIZE = 24
DESCRIPTOR_TABLE_SHA256 = (
    "04d83157859089ee13c559a35bb6ab2f8814c71db59ee3f6616b917011428b9f"
)
NEXT_STRUCTURE_OFFSET = DESCRIPTOR_TABLE_OFFSET + DESCRIPTOR_COUNT * DESCRIPTOR_SIZE
NEXT_STRUCTURE_PREFIX_SHA256 = (
    "465e1087beab46a404e38f94e2cbf7aea84fd86ad2893d2d6ddb4868da5c1315"
)
SELECTOR_ADDRESS = 0x0807FE2C
CODE_SLICES = (
    (
        "active_action_template_dispatch",
        0x07556E,
        "0x0807556E",
        "0x08075582",
        "54a578a9b34ed7599cf499793ecf240d1040436e8abe1f98e1f338dc0c5682bf",
    ),
    (
        "encoded_action_template_dispatch",
        0x075560,
        "0x08075560",
        "0x080755A4",
        "0cc88d94dd8c4d32225499714fa9951bf3946aacbabbb9fcb31348f4b887d15a",
    ),
    (
        "active_action_template_index",
        0x06D85C,
        "0x0806D85C",
        "0x0806D88C",
        "575e9d12424b0931655902433e723cc36d363644c554158c5a27d75e5e07303d",
    ),
    (
        "ninja_tool_template_index",
        0x06D910,
        "0x0806D910",
        "0x0806D95E",
        "032c35e2fa3295e906a741e1f58a5351417686fd17826d7849af7c1959138268",
    ),
    (
        "action_id_event_store",
        0x0755FA,
        "0x080755FA",
        "0x08075602",
        "7301adbc80a6e486987c9fb526067ebcc2782875163b1cc96ed46c6013ad4df4",
    ),
    (
        "event_action_to_runtime_state_a",
        0x07A0CA,
        "0x0807A0CA",
        "0x0807A0D4",
        "37c8adc6729c4c0a2f346be4aed1d67d2b2c9d94805bcff54937cd979c65e641",
    ),
    (
        "event_action_to_runtime_state_b",
        0x07A222,
        "0x0807A222",
        "0x0807A22C",
        "37c8adc6729c4c0a2f346be4aed1d67d2b2c9d94805bcff54937cd979c65e641",
    ),
    (
        "action_sequence_lookup_and_bind",
        0x07F0FC,
        "0x0807F0FC",
        "0x0807F110",
        "7b16c1004bdbf81a55ecdcfc523166059ec2a94c81161063d695e1ca59f6cc56",
    ),
    (
        "effect_sequence_binder",
        0x07C5E8,
        "0x0807C5E8",
        "0x0807C626",
        "f2bd6b80277ce5c8e33876196cb5cac25cd99036604595065ef1843af89253ee",
    ),
    (
        "effect_sequence_selector",
        0x07FE2C,
        "0x0807FE2C",
        "0x080800A4",
        "690232cbbed4b7f9d19602e91feca3299191cccb8369a10d3235b2d415751c94",
    ),
    (
        "effect_object_spawn",
        0x0800A4,
        "0x080800A4",
        "0x08080108",
        "61b4063b4920296f1a530bd6a42e7177f892d566195c7b14674865ef7f5c7d36",
    ),
    (
        "effect_callback_store",
        0x0633AE,
        "0x080633AE",
        "0x080633B8",
        "e52bcd357644b98d6f687a4af67b55f07bc50937d9a92f4cd7902daa48d7ac14",
    ),
    (
        "effect_callback_dispatch",
        0x06345E,
        "0x0806345E",
        "0x0806347E",
        "73245b505e3790cfbb01a3117a3519c7be689f9190fb11b8fafb71025beb51c1",
    ),
    (
        "next_structure_independent_consumer",
        0x080B08,
        "0x08080B08",
        "0x08080B58",
        "65623aec9844490260f9775f22471477e5fad7807f4cc958987c4f43c40a26e7",
    ),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _decode_thumb_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _selector_callsites(rom: bytes) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        address = ROM_BASE + offset
        if _decode_thumb_bl(address, first, second) != SELECTOR_ADDRESS:
            continue
        previous = struct.unpack_from("<H", rom, offset - 2)[0]
        sequence_id = previous & 0xFF if previous & 0xFF00 == 0x2000 else None
        calls.append(
            {
                "file_offset": offset,
                "gba_address": _address(address),
                "previous_halfword_hex": f"{previous:04x}",
                "sequence_id": sequence_id,
                "source": (
                    "immediate_movs_r0"
                    if sequence_id is not None
                    else "r0_argument_from_effect_sequence_binder"
                ),
            }
        )
    return calls


def _expected_manifest(rom: bytes) -> dict[str, Any]:
    runtime_table = rom[
        RUNTIME_TABLE_OFFSET : RUNTIME_TABLE_OFFSET + RUNTIME_STATE_COUNT
    ]
    active_action_slice = runtime_table[:ACTIVE_ACTION_COUNT]
    active_template_size = ACTIVE_ACTION_COUNT * ACTIVE_TEMPLATE_ENTRY_SIZE
    active_template_table = rom[
        ACTIVE_TEMPLATE_TABLE_OFFSET :
        ACTIVE_TEMPLATE_TABLE_OFFSET + active_template_size
    ]
    ninja_tool_slice = runtime_table[
        NINJA_TOOL_ENCODING_FLAG : NINJA_TOOL_ENCODING_FLAG + NINJA_TOOL_COUNT
    ]
    ninja_tool_template_size = (
        NINJA_TOOL_COUNT * NINJA_TOOL_TEMPLATE_ENTRY_SIZE
    )
    ninja_tool_template_table = rom[
        NINJA_TOOL_TEMPLATE_TABLE_OFFSET :
        NINJA_TOOL_TEMPLATE_TABLE_OFFSET + ninja_tool_template_size
    ]
    descriptor_size = DESCRIPTOR_COUNT * DESCRIPTOR_SIZE
    descriptors = rom[
        DESCRIPTOR_TABLE_OFFSET : DESCRIPTOR_TABLE_OFFSET + descriptor_size
    ]
    next_prefix = rom[NEXT_STRUCTURE_OFFSET : NEXT_STRUCTURE_OFFSET + DESCRIPTOR_SIZE]
    if _sha256(runtime_table) != RUNTIME_TABLE_SHA256:
        raise ValueError("runtime-state-to-sequence table SHA-256 mismatch")
    if _sha256(active_action_slice) != ACTIVE_ACTION_SLICE_SHA256:
        raise ValueError("active-action sequence slice SHA-256 mismatch")
    if _sha256(active_template_table) != ACTIVE_TEMPLATE_TABLE_SHA256:
        raise ValueError("active-action template table SHA-256 mismatch")
    if _sha256(ninja_tool_slice) != NINJA_TOOL_SELECTOR_SLICE_SHA256:
        raise ValueError("ninja-tool sequence slice SHA-256 mismatch")
    if (
        _sha256(ninja_tool_template_table)
        != NINJA_TOOL_TEMPLATE_TABLE_SHA256
    ):
        raise ValueError("ninja-tool template table SHA-256 mismatch")
    if _sha256(descriptors) != DESCRIPTOR_TABLE_SHA256:
        raise ValueError("sequence descriptor table SHA-256 mismatch")
    if _sha256(next_prefix) != NEXT_STRUCTURE_PREFIX_SHA256:
        raise ValueError("sequence descriptor boundary mismatch")

    runtime_values_by_sequence: dict[int, list[int]] = defaultdict(list)
    runtime_state_bindings: list[dict[str, Any]] = []
    for runtime_state_value, sequence_id in enumerate(runtime_table):
        if sequence_id >= DESCRIPTOR_COUNT:
            raise ValueError(
                f"runtime state {runtime_state_value} sequence is out of range"
            )
        runtime_values_by_sequence[sequence_id].append(runtime_state_value)
        runtime_state_bindings.append(
            {
                "runtime_state_value": runtime_state_value,
                "table_entry_file_offset": (
                    RUNTIME_TABLE_OFFSET + runtime_state_value
                ),
                "table_entry_gba_address": _address(
                    ROM_BASE + RUNTIME_TABLE_OFFSET + runtime_state_value
                ),
                "sequence_id": sequence_id,
                "sequence_descriptor_gba_address": _address(
                    ROM_BASE
                    + DESCRIPTOR_TABLE_OFFSET
                    + sequence_id * DESCRIPTOR_SIZE
                ),
            }
        )

    action_ids_by_sequence: dict[int, list[int]] = defaultdict(list)
    active_action_bindings: list[dict[str, Any]] = []
    for action_id, sequence_id in enumerate(active_action_slice):
        template_start = action_id * ACTIVE_TEMPLATE_ENTRY_SIZE
        template = active_template_table[
            template_start : template_start + ACTIVE_TEMPLATE_ENTRY_SIZE
        ]
        action_ids_by_sequence[sequence_id].append(action_id)
        active_action_bindings.append(
            {
                "action_id": action_id,
                "table_entry_file_offset": RUNTIME_TABLE_OFFSET + action_id,
                "table_entry_gba_address": _address(
                    ROM_BASE + RUNTIME_TABLE_OFFSET + action_id
                ),
                "sequence_id": sequence_id,
                "template_raw_hex": template.hex(),
                "display_animation_family": template[1],
                "effect_code": template[2] & 0x3F,
                "sequence_descriptor_gba_address": _address(
                    ROM_BASE
                    + DESCRIPTOR_TABLE_OFFSET
                    + sequence_id * DESCRIPTOR_SIZE
                ),
            }
        )

    ninja_tool_ids_by_sequence: dict[int, list[int]] = defaultdict(list)
    ninja_tool_bindings: list[dict[str, Any]] = []
    for ninja_tool_id, sequence_id in enumerate(ninja_tool_slice):
        encoded_action_id = NINJA_TOOL_ENCODING_FLAG | ninja_tool_id
        template_start = ninja_tool_id * NINJA_TOOL_TEMPLATE_ENTRY_SIZE
        template = ninja_tool_template_table[
            template_start : template_start + NINJA_TOOL_TEMPLATE_ENTRY_SIZE
        ]
        ninja_tool_ids_by_sequence[sequence_id].append(ninja_tool_id)
        ninja_tool_bindings.append(
            {
                "ninja_tool_id": ninja_tool_id,
                "encoded_action_id": encoded_action_id,
                "table_entry_file_offset": (
                    RUNTIME_TABLE_OFFSET + encoded_action_id
                ),
                "table_entry_gba_address": _address(
                    ROM_BASE + RUNTIME_TABLE_OFFSET + encoded_action_id
                ),
                "sequence_id": sequence_id,
                "template_raw_hex": template.hex(),
                "display_animation_family": template[0],
                "effect_code": template[2] & 0x3F,
                "sequence_descriptor_gba_address": _address(
                    ROM_BASE
                    + DESCRIPTOR_TABLE_OFFSET
                    + sequence_id * DESCRIPTOR_SIZE
                ),
            }
        )

    sequences: list[dict[str, Any]] = []
    for sequence_id in range(DESCRIPTOR_COUNT):
        start = sequence_id * DESCRIPTOR_SIZE
        raw = descriptors[start : start + DESCRIPTOR_SIZE]
        values = struct.unpack("<6I", raw)
        group_ids = list(values[:4])
        if any(group_id > 18 for group_id in group_ids):
            raise ValueError(f"sequence {sequence_id} resource group is invalid")
        sequences.append(
            {
                "sequence_id": sequence_id,
                "table_entry_file_offset": DESCRIPTOR_TABLE_OFFSET + start,
                "table_entry_gba_address": _address(
                    ROM_BASE + DESCRIPTOR_TABLE_OFFSET + start
                ),
                "raw_hex": raw.hex(),
                "resource_group_ids": group_ids,
                "nonzero_resource_group_ids": [
                    group_id for group_id in group_ids if group_id
                ],
                "resource_pair_artifacts": [
                    (
                        "artifacts/battle-effect-resource-pairs-v1/"
                        f"group-{group_id:02d}-atlas.png"
                    )
                    for group_id in group_ids
                    if group_id
                ],
                "init_once_callback_thumb": _address(values[4]),
                "init_once_callback_address": _address(
                    values[4] - 1 if values[4] else 0
                ),
                "tick_callback_thumb": _address(values[5]),
                "tick_callback_address": _address(
                    values[5] - 1 if values[5] else 0
                ),
                "runtime_state_values": runtime_values_by_sequence.get(
                    sequence_id, []
                ),
                "active_action_ids": action_ids_by_sequence.get(sequence_id, []),
                "ninja_tool_ids": ninja_tool_ids_by_sequence.get(
                    sequence_id, []
                ),
            }
        )

    calls = _selector_callsites(rom)
    if len(calls) != 67:
        raise ValueError("unexpected selector callsite count")
    constant_ids = [
        item["sequence_id"] for item in calls if item["sequence_id"] is not None
    ]
    if len(constant_ids) != 66 or max(constant_ids) != 21:
        raise ValueError("selector callsites do not prove the descriptor boundary")
    code_slices = []
    for name, start, gba_start, gba_end, digest in CODE_SLICES:
        end = int(gba_end, 16) - ROM_BASE
        if _sha256(rom[start:end]) != digest:
            raise ValueError(f"{name} SHA-256 mismatch")
        code_slices.append(
            {
                "name": name,
                "file_offset": start,
                "gba_start": gba_start,
                "gba_end": gba_end,
                "sha256": digest,
            }
        )

    return {
        "schema": "battle-effect-sequence-bindings-v1",
        "rom": {
            "path": "rom/base.gba",
            "sha256": _sha256(rom),
        },
        "runtime_state_sequence_table": {
            "file_offset": RUNTIME_TABLE_OFFSET,
            "gba_address": _address(ROM_BASE + RUNTIME_TABLE_OFFSET),
            "entry_count": RUNTIME_STATE_COUNT,
            "entry_size": 1,
            "sha256": _sha256(runtime_table),
        },
        "active_action_slice": {
            "start_index": 0,
            "entry_count": ACTIVE_ACTION_COUNT,
            "sha256": _sha256(active_action_slice),
        },
        "active_action_template_table": {
            "file_offset": ACTIVE_TEMPLATE_TABLE_OFFSET,
            "gba_address": _address(ROM_BASE + ACTIVE_TEMPLATE_TABLE_OFFSET),
            "entry_count": ACTIVE_ACTION_COUNT,
            "entry_size": ACTIVE_TEMPLATE_ENTRY_SIZE,
            "sha256": _sha256(active_template_table),
        },
        "ninja_tool_selector_slice": {
            "start_index": NINJA_TOOL_ENCODING_FLAG,
            "entry_count": NINJA_TOOL_COUNT,
            "sha256": _sha256(ninja_tool_slice),
        },
        "ninja_tool_template_table": {
            "file_offset": NINJA_TOOL_TEMPLATE_TABLE_OFFSET,
            "gba_address": _address(
                ROM_BASE + NINJA_TOOL_TEMPLATE_TABLE_OFFSET
            ),
            "entry_count": NINJA_TOOL_COUNT,
            "entry_size": NINJA_TOOL_TEMPLATE_ENTRY_SIZE,
            "sha256": _sha256(ninja_tool_template_table),
        },
        "active_action_join_evidence": {
            "active_action_template_table": "0x08545458",
            "event_action_id_field": "+0x0C",
            "runtime_state_action_id_field": "+0x770",
            "selector_is_parallel_id_table": True,
            "sequence_derived_from_template_fields": False,
        },
        "ninja_tool_join_evidence": {
            "encoded_action_high_bit": "0x80",
            "ninja_tool_id_mask": "0x7F",
            "ninja_tool_template_table": "0x08545BE4",
            "event_preserves_encoded_action_id_at": "+0x0C",
            "runtime_state_action_id_field": "+0x770",
            "selector_is_parallel_encoded_action_id_table": True,
        },
        "sequence_descriptor_table": {
            "file_offset": DESCRIPTOR_TABLE_OFFSET,
            "gba_address": _address(ROM_BASE + DESCRIPTOR_TABLE_OFFSET),
            "entry_count": DESCRIPTOR_COUNT,
            "entry_size": DESCRIPTOR_SIZE,
            "sha256": _sha256(descriptors),
            "next_structure_gba_address": _address(
                ROM_BASE + NEXT_STRUCTURE_OFFSET
            ),
        },
        "runtime_state_bindings": runtime_state_bindings,
        "active_action_bindings": active_action_bindings,
        "ninja_tool_bindings": ninja_tool_bindings,
        "sequences": sequences,
        "selector_callsites": calls,
        "consumer_code_slices": code_slices,
        "boundary_evidence": {
            "next_structure_prefix_size": DESCRIPTOR_SIZE,
            "next_structure_prefix_sha256": _sha256(next_prefix),
            "constant_selector_call_count": 66,
            "dynamic_selector_call_count": 1,
            "maximum_constant_sequence_id": max(constant_ids),
        },
        "scope": {
            "runtime_state_to_sequence_mapping_complete": True,
            "active_action_slice_join_complete": True,
            "active_action_to_sequence_mapping_complete": True,
            "ninja_tool_slice_join_complete": True,
            "ninja_tool_to_sequence_mapping_complete": True,
            "sequence_to_resource_group_mapping_complete": True,
            "callback_pointer_identity_complete": True,
            "callback_scheduler_role_complete": True,
            "callback_internal_animation_semantics_complete": False,
            "oam_composition_complete": False,
            "frame_hold_timing_complete": False,
            "audio_binding_complete": False,
        },
    }


def _compare(expected: Any, actual: Any, path: str, errors: list[str]) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            errors.append(f"{path}: expected object")
            return
        for key in expected:
            if key not in actual:
                errors.append(f"{path}.{key}: missing")
            else:
                _compare(expected[key], actual[key], f"{path}.{key}", errors)
        for key in actual.keys() - expected.keys():
            errors.append(f"{path}.{key}: unexpected")
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            errors.append(f"{path}: expected list")
            return
        if len(expected) != len(actual):
            errors.append(f"{path}: length {len(actual)} != {len(expected)}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            _compare(left, right, f"{path}[{index}]", errors)
    elif expected != actual:
        errors.append(f"{path}: {actual!r} != {expected!r}")


def verify_battle_effect_sequence_bindings(
    root: Path | str,
    artifact_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    artifact_dir = Path(artifact_dir)
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        return {
            "verified_runtime_state_bindings": 0,
            "verified_active_action_bindings": 0,
            "verified_ninja_tool_bindings": 0,
            "verified_sequences": 0,
            "errors": ["rom.sha256: unexpected base ROM"],
        }
    errors: list[str] = []
    try:
        expected = _expected_manifest(rom)
    except ValueError as error:
        return {
            "verified_runtime_state_bindings": 0,
            "verified_active_action_bindings": 0,
            "verified_ninja_tool_bindings": 0,
            "verified_sequences": 0,
            "errors": [str(error)],
        }
    path = artifact_dir / "manifest.json"
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "verified_runtime_state_bindings": 0,
            "verified_active_action_bindings": 0,
            "verified_ninja_tool_bindings": 0,
            "verified_sequences": 0,
            "errors": [f"manifest.json: {error}"],
        }
    _compare(expected, actual, "manifest", errors)
    return {
        "verified_runtime_state_bindings": (
            0 if errors else RUNTIME_STATE_COUNT
        ),
        "verified_active_action_bindings": (
            0 if errors else ACTIVE_ACTION_COUNT
        ),
        "verified_ninja_tool_bindings": (
            0 if errors else NINJA_TOOL_COUNT
        ),
        "verified_sequences": 0 if errors else DESCRIPTOR_COUNT,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/battle-effect-sequence-bindings-v1"),
    )
    args = parser.parse_args()
    result = verify_battle_effect_sequence_bindings(args.root, args.artifact_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
