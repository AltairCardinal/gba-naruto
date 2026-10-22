#!/usr/bin/env python3
"""Export all active-action and battle-effect sequence bindings from the ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from tools.thumb_branch import find_thumb_branches
except ModuleNotFoundError:
    from thumb_branch import find_thumb_branches


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
    {
        "name": "active_action_template_dispatch",
        "file_offset": 0x07556E,
        "gba_start": "0x0807556E",
        "gba_end": "0x08075582",
        "sha256": "54a578a9b34ed7599cf499793ecf240d1040436e8abe1f98e1f338dc0c5682bf",
    },
    {
        "name": "encoded_action_template_dispatch",
        "file_offset": 0x075560,
        "gba_start": "0x08075560",
        "gba_end": "0x080755A4",
        "sha256": "0cc88d94dd8c4d32225499714fa9951bf3946aacbabbb9fcb31348f4b887d15a",
    },
    {
        "name": "active_action_template_index",
        "file_offset": 0x06D85C,
        "gba_start": "0x0806D85C",
        "gba_end": "0x0806D88C",
        "sha256": "575e9d12424b0931655902433e723cc36d363644c554158c5a27d75e5e07303d",
    },
    {
        "name": "ninja_tool_template_index",
        "file_offset": 0x06D910,
        "gba_start": "0x0806D910",
        "gba_end": "0x0806D95E",
        "sha256": "032c35e2fa3295e906a741e1f58a5351417686fd17826d7849af7c1959138268",
    },
    {
        "name": "action_id_event_store",
        "file_offset": 0x0755FA,
        "gba_start": "0x080755FA",
        "gba_end": "0x08075602",
        "sha256": "7301adbc80a6e486987c9fb526067ebcc2782875163b1cc96ed46c6013ad4df4",
    },
    {
        "name": "event_action_to_runtime_state_a",
        "file_offset": 0x07A0CA,
        "gba_start": "0x0807A0CA",
        "gba_end": "0x0807A0D4",
        "sha256": "37c8adc6729c4c0a2f346be4aed1d67d2b2c9d94805bcff54937cd979c65e641",
    },
    {
        "name": "event_action_to_runtime_state_b",
        "file_offset": 0x07A222,
        "gba_start": "0x0807A222",
        "gba_end": "0x0807A22C",
        "sha256": "37c8adc6729c4c0a2f346be4aed1d67d2b2c9d94805bcff54937cd979c65e641",
    },
    {
        "name": "action_sequence_lookup_and_bind",
        "file_offset": 0x07F0FC,
        "gba_start": "0x0807F0FC",
        "gba_end": "0x0807F110",
        "sha256": "7b16c1004bdbf81a55ecdcfc523166059ec2a94c81161063d695e1ca59f6cc56",
    },
    {
        "name": "effect_sequence_binder",
        "file_offset": 0x07C5E8,
        "gba_start": "0x0807C5E8",
        "gba_end": "0x0807C626",
        "sha256": "f2bd6b80277ce5c8e33876196cb5cac25cd99036604595065ef1843af89253ee",
    },
    {
        "name": "effect_sequence_selector",
        "file_offset": 0x07FE2C,
        "gba_start": "0x0807FE2C",
        "gba_end": "0x080800A4",
        "sha256": "690232cbbed4b7f9d19602e91feca3299191cccb8369a10d3235b2d415751c94",
    },
    {
        "name": "effect_object_spawn",
        "file_offset": 0x0800A4,
        "gba_start": "0x080800A4",
        "gba_end": "0x08080108",
        "sha256": "61b4063b4920296f1a530bd6a42e7177f892d566195c7b14674865ef7f5c7d36",
    },
    {
        "name": "effect_callback_store",
        "file_offset": 0x0633AE,
        "gba_start": "0x080633AE",
        "gba_end": "0x080633B8",
        "sha256": "e52bcd357644b98d6f687a4af67b55f07bc50937d9a92f4cd7902daa48d7ac14",
    },
    {
        "name": "effect_callback_dispatch",
        "file_offset": 0x06345E,
        "gba_start": "0x0806345E",
        "gba_end": "0x0806347E",
        "sha256": "73245b505e3790cfbb01a3117a3519c7be689f9190fb11b8fafb71025beb51c1",
    },
    {
        "name": "next_structure_independent_consumer",
        "file_offset": 0x080B08,
        "gba_start": "0x08080B08",
        "gba_end": "0x08080B58",
        "sha256": "65623aec9844490260f9775f22471477e5fad7807f4cc958987c4f43c40a26e7",
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _code_slices(rom: bytes) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for expected in CODE_SLICES:
        item = dict(expected)
        start = int(item["file_offset"])
        end = int(str(item["gba_end"]), 16) - ROM_BASE
        actual = _sha256(rom[start:end])
        if actual != item["sha256"]:
            raise ValueError(
                f"{item['name']} SHA-256 mismatch: "
                f"expected {item['sha256']}, got {actual}"
            )
        result.append(item)
    return result


def _selector_callsites(rom: bytes) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for branch in find_thumb_branches(
        rom,
        SELECTOR_ADDRESS,
        rom_base=ROM_BASE,
    ):
        offset = branch.address - ROM_BASE
        previous = struct.unpack_from("<H", rom, offset - 2)[0]
        sequence_id = previous & 0xFF if previous & 0xFF00 == 0x2000 else None
        calls.append(
            {
                "file_offset": offset,
                "gba_address": _address(branch.address),
                "previous_halfword_hex": f"{previous:04x}",
                "sequence_id": sequence_id,
                "source": (
                    "immediate_movs_r0"
                    if sequence_id is not None
                    else "r0_argument_from_effect_sequence_binder"
                ),
            }
        )
    if len(calls) != 67:
        raise ValueError(f"expected 67 direct selector calls, got {len(calls)}")
    constant_ids = [
        item["sequence_id"] for item in calls if item["sequence_id"] is not None
    ]
    if len(constant_ids) != 66 or max(constant_ids) != DESCRIPTOR_COUNT - 1:
        raise ValueError("selector callsite coverage does not prove sequence 21")
    dynamic = [item for item in calls if item["sequence_id"] is None]
    if [item["gba_address"] for item in dynamic] != ["0x0807C602"]:
        raise ValueError("unexpected dynamic selector callsite")
    return calls


def export_battle_effect_sequence_bindings(
    root: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    output_dir = Path(output_dir)
    rom = (root / "rom/base.gba").read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: expected {ROM_SHA256}, got {rom_sha256}"
        )

    runtime_table = rom[
        RUNTIME_TABLE_OFFSET : RUNTIME_TABLE_OFFSET + RUNTIME_STATE_COUNT
    ]
    if len(runtime_table) != RUNTIME_STATE_COUNT:
        raise ValueError("runtime-state-to-sequence table is truncated")
    if _sha256(runtime_table) != RUNTIME_TABLE_SHA256:
        raise ValueError("runtime-state-to-sequence table SHA-256 mismatch")
    active_action_slice = runtime_table[:ACTIVE_ACTION_COUNT]
    if _sha256(active_action_slice) != ACTIVE_ACTION_SLICE_SHA256:
        raise ValueError("active-action sequence slice SHA-256 mismatch")
    active_template_size = ACTIVE_ACTION_COUNT * ACTIVE_TEMPLATE_ENTRY_SIZE
    active_template_table = rom[
        ACTIVE_TEMPLATE_TABLE_OFFSET :
        ACTIVE_TEMPLATE_TABLE_OFFSET + active_template_size
    ]
    if _sha256(active_template_table) != ACTIVE_TEMPLATE_TABLE_SHA256:
        raise ValueError("active-action template table SHA-256 mismatch")
    ninja_tool_slice = runtime_table[
        NINJA_TOOL_ENCODING_FLAG : NINJA_TOOL_ENCODING_FLAG + NINJA_TOOL_COUNT
    ]
    if _sha256(ninja_tool_slice) != NINJA_TOOL_SELECTOR_SLICE_SHA256:
        raise ValueError("ninja-tool sequence slice SHA-256 mismatch")
    ninja_tool_template_size = (
        NINJA_TOOL_COUNT * NINJA_TOOL_TEMPLATE_ENTRY_SIZE
    )
    ninja_tool_template_table = rom[
        NINJA_TOOL_TEMPLATE_TABLE_OFFSET :
        NINJA_TOOL_TEMPLATE_TABLE_OFFSET + ninja_tool_template_size
    ]
    if (
        _sha256(ninja_tool_template_table)
        != NINJA_TOOL_TEMPLATE_TABLE_SHA256
    ):
        raise ValueError("ninja-tool template table SHA-256 mismatch")

    descriptor_size = DESCRIPTOR_COUNT * DESCRIPTOR_SIZE
    descriptors = rom[
        DESCRIPTOR_TABLE_OFFSET : DESCRIPTOR_TABLE_OFFSET + descriptor_size
    ]
    if len(descriptors) != descriptor_size:
        raise ValueError("sequence descriptor table is truncated")
    if _sha256(descriptors) != DESCRIPTOR_TABLE_SHA256:
        raise ValueError("sequence descriptor table SHA-256 mismatch")
    if descriptors[:DESCRIPTOR_SIZE] != b"\0" * DESCRIPTOR_SIZE:
        raise ValueError("sequence zero descriptor is not the null sentinel")
    next_prefix = rom[NEXT_STRUCTURE_OFFSET : NEXT_STRUCTURE_OFFSET + DESCRIPTOR_SIZE]
    if _sha256(next_prefix) != NEXT_STRUCTURE_PREFIX_SHA256:
        raise ValueError("sequence descriptor boundary does not match the ROM")

    runtime_values_by_sequence: dict[int, list[int]] = defaultdict(list)
    runtime_state_bindings: list[dict[str, Any]] = []
    for runtime_state_value, sequence_id in enumerate(runtime_table):
        if sequence_id >= DESCRIPTOR_COUNT:
            raise ValueError(
                f"runtime state {runtime_state_value} sequence {sequence_id} "
                "is outside the table"
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
        resource_group_ids = list(values[:4])
        if any(group_id > 18 for group_id in resource_group_ids):
            raise ValueError(f"sequence {sequence_id} has an invalid resource group")
        if sequence_id:
            if not resource_group_ids[0]:
                raise ValueError(f"sequence {sequence_id} has no primary resource")
            for pointer in values[4:]:
                if not (
                    pointer & 1
                    and ROM_BASE <= pointer - 1 < ROM_BASE + len(rom)
                ):
                    raise ValueError(
                        f"sequence {sequence_id} callback {_address(pointer)} "
                        "is not a ROM Thumb pointer"
                    )
        sequences.append(
            {
                "sequence_id": sequence_id,
                "table_entry_file_offset": DESCRIPTOR_TABLE_OFFSET + start,
                "table_entry_gba_address": _address(
                    ROM_BASE + DESCRIPTOR_TABLE_OFFSET + start
                ),
                "raw_hex": raw.hex(),
                "resource_group_ids": resource_group_ids,
                "nonzero_resource_group_ids": [
                    group_id for group_id in resource_group_ids if group_id
                ],
                "resource_pair_artifacts": [
                    (
                        "artifacts/battle-effect-resource-pairs-v1/"
                        f"group-{group_id:02d}-atlas.png"
                    )
                    for group_id in resource_group_ids
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
    manifest: dict[str, Any] = {
        "schema": "battle-effect-sequence-bindings-v1",
        "rom": {
            "path": "rom/base.gba",
            "sha256": rom_sha256,
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
        "consumer_code_slices": _code_slices(rom),
        "boundary_evidence": {
            "next_structure_prefix_size": DESCRIPTOR_SIZE,
            "next_structure_prefix_sha256": _sha256(next_prefix),
            "constant_selector_call_count": 66,
            "dynamic_selector_call_count": 1,
            "maximum_constant_sequence_id": max(
                item["sequence_id"]
                for item in calls
                if item["sequence_id"] is not None
            ),
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
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/battle-effect-sequence-bindings-v1"),
    )
    args = parser.parse_args()
    manifest = export_battle_effect_sequence_bindings(args.root, args.output_dir)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "runtime_state_bindings": len(
                    manifest["runtime_state_bindings"]
                ),
                "active_action_bindings": len(
                    manifest["active_action_bindings"]
                ),
                "ninja_tool_bindings": len(
                    manifest["ninja_tool_bindings"]
                ),
                "sequences": len(manifest["sequences"]),
                "errors": [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
