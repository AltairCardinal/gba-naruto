#!/usr/bin/env python3
"""Independently verify the complete direct-WRAM tilemap runtime artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
EMULATOR_SHA256 = "4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72"
EMULATOR_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
PARENT_DIR = "artifacts/residual-wram-tilemap-runtime-v1"
PARENT_MANIFEST_SHA256 = "1cde045d1fb0e06028760371514cfe2ac47e1623e1d9605a00489e763a460f5f"
PARENT_EVIDENCE_SHA256 = "cf2ccff3159ac28a4300f94fcf40498c805de8351ba0b180a840648025470e62"
PARENT_STATE_SHA256 = "fbfd4b5aa0ceda8e239ae0d965c05429e1edc64e9bd7dfba9567f968460348ff"
ABI_PATH = "artifacts/residual-wram-tilemap-abi-v1/residual-wram-tilemap-abi.json"
ABI_SHA256 = "07e1f89b5aaff938184d5d31bea4174e995f96d10b8ffbee56bff0f609a27dfc"
OWNERSHIP_PATH = "artifacts/residual-wram-tilemap-resource-ownership-v1/resource-ownership.json"
OWNERSHIP_SHA256 = "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
BRIDGE_RUN_ID = "scene-panel-v1-parent-b-bridge-20260731"
ZERO_RUN_ID = "scene-panel-v1-parent-direct-sources-zero5-20260731"
SETUP_STATE_SHA256 = "6fed9fe8db43646a5a5a53901a5f0edf1c743ba5e682fd842d3fd19b12776000"
EXPECTED_FILES = {
    "bridge-audit.json",
    "bridge-done.json",
    "bridge-guard.json",
    "scene-panel-setup.ss9",
    "zero-audit.json",
    "zero-done.json",
    "zero-guard.json",
    "queue-at-consumer.bin",
    "vram-at-consumer.bin",
    "final-queue.bin",
    "vram-final.bin",
    "final.ss9",
    "final.png",
    "runtime-evidence.json",
}
IMPLEMENTATION_PATHS = (
    "tools/mgba_wram_tilemap_probe.lua",
    "tests/test_mgba_wram_tilemap_probe_script.py",
    "tools/mgba_wram_tilemap_single_input_probe.lua",
    "tests/test_mgba_wram_tilemap_single_input_probe_script.py",
    "tools/extract_tileset.py",
    "tools/export_residual_wram_tilemap_runtime_v2.py",
    "tools/verify_residual_wram_tilemap_runtime_v2.py",
    "tests/test_residual_wram_tilemap_runtime_v2.py",
)
SPECS = (
    {
        "pointer": 0x083F1C98,
        "load_name": "scene_panel_upper_load",
        "load_target": 0x0808BBD8,
        "wram": 0x02002B78,
        "vram": 0x0600F810,
        "width": 24,
        "height": 12,
        "slot": 0,
        "changed": 473,
    },
    {
        "pointer": 0x085B67E0,
        "load_name": "scene_panel_lower_load",
        "load_target": 0x0808BBFC,
        "wram": 0x02002DB8,
        "vram": 0x0600FC4E,
        "width": 23,
        "height": 3,
        "slot": 1,
        "changed": 134,
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _expect(errors: list[str], actual: object, expected: object, message: str) -> None:
    if actual != expected:
        errors.append(message)


def _decode_lz77(data: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError("invalid LZ77 header")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    if size <= 0:
        raise ValueError("invalid LZ77 output size")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        if cursor >= len(data):
            raise ValueError("truncated LZ77 flags")
        flags = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(data):
                    raise ValueError("truncated LZ77 token")
                token = (data[cursor] << 8) | data[cursor + 1]
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0x0FFF) + 1
                if distance > len(output):
                    raise ValueError("invalid LZ77 distance")
                for _ in range(length):
                    if len(output) >= size:
                        break
                    output.append(output[-distance])
            else:
                if cursor >= len(data):
                    raise ValueError("truncated LZ77 literal")
                output.append(data[cursor])
                cursor += 1
    return bytes(output)


def _slot(data: bytes, index: int) -> dict[str, Any]:
    if len(data) != 0x100:
        raise ValueError("queue capture is not 256 bytes")
    status, source, destination, width, height = struct.unpack_from(
        "<I2I2H", data, index * 16
    )
    return {
        "slot_index": index,
        "status": status,
        "source": _address(source),
        "destination": _address(destination),
        "source_stride_halfwords": width,
        "row_count": height,
    }


def _matching_count(data: bytes, expected: tuple[int, int, int, int, int]) -> int:
    if len(data) != 0x100:
        raise ValueError("queue capture is not 256 bytes")
    return sum(
        struct.unpack_from("<I2I2H", data, index * 16) == expected
        for index in range(16)
    )


def _rows(data: bytes, destination: int, width: int, height: int) -> bytes:
    if len(data) != 0x18000:
        raise ValueError("VRAM capture is not 96 KiB")
    start = destination - 0x06000000
    return b"".join(
        data[start + row * 64 : start + row * 64 + width * 2]
        for row in range(height)
    )


def _event(audit: dict[str, Any], name: str) -> dict[str, Any]:
    events = [event for event in audit.get("events", []) if event.get("target") == name]
    return events[0] if events else {}


def _verify_guard(errors: list[str], guard: dict[str, Any], label: str) -> None:
    for field, expected in (
        ("reason", "completed"),
        ("exit_code", 0),
        ("degraded", False),
        ("completion_trigger", "success-marker"),
    ):
        _expect(errors, guard.get(field), expected, f"{label} guard {field} mismatch")
    peak = guard.get("peak_tree_rss_mib")
    if not isinstance(peak, (int, float)) or peak > 1536:
        errors.append(f"{label} guard peak RSS mismatch")


def _verify_parent(root: Path, payload: dict[str, Any], errors: list[str]) -> None:
    parent_dir = root / PARENT_DIR
    manifest_path = parent_dir / "manifest.json"
    evidence_path = parent_dir / "runtime-evidence.json"
    state_path = parent_dir / "final.ss9"
    _expect(errors, _sha256(manifest_path), PARENT_MANIFEST_SHA256, "parent v1 manifest SHA-256 mismatch")
    _expect(errors, _sha256(evidence_path), PARENT_EVIDENCE_SHA256, "parent v1 evidence SHA-256 mismatch")
    _expect(errors, _sha256(state_path), PARENT_STATE_SHA256, "parent v1 checkpoint SHA-256 mismatch")
    manifest = _read_json(manifest_path)
    evidence = _read_json(evidence_path)
    _expect(errors, manifest.get("artifact_id"), "residual-wram-tilemap-runtime-v1", "parent v1 artifact ID mismatch")
    _expect(errors, manifest.get("artifact_status"), "accepted", "parent v1 status mismatch")
    _expect(errors, manifest.get("files", {}).get("final.ss9"), PARENT_STATE_SHA256, "parent v1 state inventory mismatch")
    actual_parent_files = {
        path.relative_to(parent_dir).as_posix(): path
        for path in parent_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    inventory = manifest.get("files", {})
    if not isinstance(inventory, dict) or set(inventory) != set(actual_parent_files):
        errors.append("parent v1 file inventory mismatch")
    else:
        for relative, path in actual_parent_files.items():
            _expect(errors, inventory.get(relative), _sha256(path), f"parent v1 file hash mismatch: {relative}")
    _expect(errors, evidence.get("summary", {}).get("runtime_verified_count"), 1, "parent v1 verified count mismatch")
    _expect(errors, evidence.get("summary", {}).get("verified_source_pointer"), "0x0834928C", "parent v1 source mismatch")
    _expect(
        errors,
        payload.get("parent_runtime_v1"),
        {
            "artifact": PARENT_DIR,
            "manifest_sha256": PARENT_MANIFEST_SHA256,
            "evidence_sha256": PARENT_EVIDENCE_SHA256,
            "verified_source_pointer": "0x0834928C",
        },
        "parent v1 declaration mismatch",
    )


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    artifact_dir = artifact_dir.resolve()
    errors: list[str] = []
    payload: dict[str, Any] = {}
    try:
        paths = list(artifact_dir.rglob("*"))
        if any(path.is_symlink() for path in paths):
            errors.append("artifact contains a symbolic link")
        actual_files = {
            path.relative_to(artifact_dir).as_posix(): path
            for path in paths
            if path.is_file() and path.name != "manifest.json"
        }
        if set(actual_files) != EXPECTED_FILES:
            errors.append("artifact file inventory mismatch")
        manifest = _read_json(artifact_dir / "manifest.json")
        payload = _read_json(artifact_dir / "runtime-evidence.json")
        for field, expected in (
            ("schema", "git-artifact-promotion-v1"),
            ("artifact_id", "residual-wram-tilemap-runtime-v2"),
            ("artifact_schema", "residual-wram-tilemap-runtime-evidence-v2"),
            ("artifact_status", "accepted"),
            ("payload_file", "runtime-evidence.json"),
        ):
            _expect(errors, manifest.get(field), expected, f"manifest {field} mismatch")
        inventory = manifest.get("files")
        if not isinstance(inventory, dict) or set(inventory) != EXPECTED_FILES:
            errors.append("manifest file inventory mismatch")
            inventory = {}
        for relative, path in actual_files.items():
            _expect(errors, inventory.get(relative), _sha256(path), f"artifact hash mismatch: {relative}")
        payload_hash = _sha256(artifact_dir / "runtime-evidence.json")
        _expect(errors, manifest.get("payload_sha256"), payload_hash, "payload SHA-256 mismatch")
        implementation = manifest.get("implementation")
        if not isinstance(implementation, dict) or set(implementation) != set(IMPLEMENTATION_PATHS):
            errors.append("implementation inventory mismatch")
            implementation = {}
        for relative in IMPLEMENTATION_PATHS:
            _expect(errors, implementation.get(relative), _sha256(root / relative), f"implementation hash mismatch: {relative}")
        _expect(
            errors,
            manifest.get("verifier"),
            {
                "command": [
                    "python3",
                    "tools/verify_residual_wram_tilemap_runtime_v2.py",
                    "--root",
                    ".",
                    "--artifact",
                    "artifacts/residual-wram-tilemap-runtime-v2",
                ],
                "exit_code": 0,
            },
            "manifest verifier declaration mismatch",
        )
        _expect(errors, payload.get("schema"), "residual-wram-tilemap-runtime-evidence-v2", "payload schema mismatch")
        _expect(errors, payload.get("rom"), {"path": "rom/base.gba", "sha256": ROM_SHA256}, "ROM declaration mismatch")
        _expect(errors, payload.get("emulator"), {"source_commit": EMULATOR_COMMIT, "binary_sha256": EMULATOR_SHA256}, "emulator declaration mismatch")
        _verify_parent(root, payload, errors)

        rom_path = root / "rom/base.gba"
        _expect(errors, _sha256(rom_path), ROM_SHA256, "base ROM SHA-256 mismatch")
        _expect(errors, _sha256(root / ABI_PATH), ABI_SHA256, "ABI payload SHA-256 mismatch")
        _expect(errors, _sha256(root / OWNERSHIP_PATH), OWNERSHIP_SHA256, "ownership payload SHA-256 mismatch")
        _expect(
            errors,
            payload.get("source_artifacts"),
            {
                "abi": {"path": ABI_PATH, "sha256": ABI_SHA256},
                "ownership": {"path": OWNERSHIP_PATH, "sha256": OWNERSHIP_SHA256},
            },
            "source artifact declaration mismatch",
        )
        abi_records = {
            record["source_pointer"]: record
            for record in _read_json(root / ABI_PATH).get("tilemaps", [])
        }
        if set(abi_records) != {"0x0834928C", "0x083F1C98", "0x085B67E0"}:
            errors.append("direct queue source denominator mismatch")

        bridge_audit = _read_json(artifact_dir / "bridge-audit.json")
        _expect(errors, bridge_audit, _read_json(artifact_dir / "bridge-done.json"), "bridge audit and completion marker differ")
        bridge_guard = _read_json(artifact_dir / "bridge-guard.json")
        expected_input = [{"key": "B", "down_frame": 18, "up_frame": 20, "hold_frames": 2}]
        expected_bridge_hits = {
            "text_bg_loop_link": 0,
            "text_bg_setup": 0,
            "selection_load": 0,
            "scene_panel_setup": 1,
            "scene_panel_upper_load": 1,
            "scene_panel_lower_load": 1,
            "scene_panel_crop_load": 1,
            "scene_panel_result": 0,
            "choice_screen_entry": 0,
            "choice_action_dispatch": 0,
            "choice_animation_spawn_call": 0,
            "choice_animation_task_factory": 0,
            "choice_phase_a_load": 0,
            "choice_phase_a_submit": 0,
            "choice_phase_b_initial_load": 0,
            "choice_phase_b_second_load": 0,
            "choice_phase_b_submit": 0,
            "queue_consumer": 77,
        }
        for field, expected in (
            ("schema", "mgba-wram-tilemap-single-input-probe-v1"),
            ("run_id", BRIDGE_RUN_ID),
            ("outcome", "targets-observed"),
            ("rom_sha256", ROM_SHA256),
            ("binary_sha256", EMULATOR_SHA256),
            ("input_state_sha256", PARENT_STATE_SHA256),
            ("inputs", expected_input),
            ("automatic_inputs", []),
            ("recovery_inputs", []),
            ("capture_frames", 80),
            ("frame", 80),
            ("total_hits", 81),
            ("hit_counts", expected_bridge_hits),
        ):
            _expect(errors, bridge_audit.get(field), expected, f"bridge audit {field} mismatch")
        _verify_guard(errors, bridge_guard, "bridge")
        setup = _event(bridge_audit, "scene_panel_setup")
        for field, expected in (
            ("address", "0x0808BAB0"),
            ("pc", "0x0808BAB2"),
            ("lr", "0x0808F819"),
            ("frame", 28),
        ):
            _expect(errors, setup.get(field), expected, f"bridge setup {field} mismatch")
        setup_hash = _sha256(artifact_dir / "scene-panel-setup.ss9")
        _expect(errors, setup_hash, SETUP_STATE_SHA256, "bridge setup checkpoint hash mismatch")
        bridge = payload.get("bridge", {})
        _expect(errors, bridge.get("run_id"), BRIDGE_RUN_ID, "bridge run ID mismatch")
        _expect(errors, bridge.get("input_checkpoint"), {"path": f"{PARENT_DIR}/final.ss9", "sha256": PARENT_STATE_SHA256}, "bridge input checkpoint mismatch")
        _expect(errors, bridge.get("inputs"), expected_input, "bridge input declaration mismatch")
        _expect(errors, bridge.get("scene_panel_setup_hit"), {"target": "0x0808BAB0", "pc": "0x0808BAB2", "lr": "0x0808F819", "frame": 28}, "bridge setup hit declaration mismatch")
        _expect(errors, bridge.get("setup_checkpoint_sha256"), setup_hash, "bridge setup payload hash mismatch")
        _expect(errors, bridge.get("audit_sha256"), _sha256(artifact_dir / "bridge-audit.json"), "bridge audit hash binding mismatch")
        _expect(errors, bridge.get("guard_sha256"), _sha256(artifact_dir / "bridge-guard.json"), "bridge guard hash binding mismatch")
        _expect(errors, bridge.get("peak_tree_rss_mib"), bridge_guard.get("peak_tree_rss_mib"), "bridge RSS binding mismatch")

        zero_audit = _read_json(artifact_dir / "zero-audit.json")
        _expect(errors, zero_audit, _read_json(artifact_dir / "zero-done.json"), "zero audit and completion marker differ")
        zero_guard = _read_json(artifact_dir / "zero-guard.json")
        expected_hits = {
            "text_bg_loop_link": 0,
            "text_bg_setup": 0,
            "selection_load": 0,
            "scene_panel_setup": 0,
            "scene_panel_upper_load": 1,
            "scene_panel_lower_load": 1,
            "scene_panel_crop_load": 1,
            "choice_phase_a_load": 0,
            "choice_phase_a_submit": 0,
            "choice_phase_b_initial_load": 0,
            "choice_phase_b_second_load": 0,
            "choice_phase_b_submit": 0,
            "queue_consumer": 2,
        }
        for field, expected in (
            ("schema", "mgba-wram-tilemap-probe-v1"),
            ("run_id", ZERO_RUN_ID),
            ("rom_sha256", ROM_SHA256),
            ("binary_sha256", EMULATOR_SHA256),
            ("input_state_sha256", SETUP_STATE_SHA256),
            ("inputs", []),
            ("capture_frames", 5),
            ("frame", 5),
            ("total_hits", 5),
            ("hit_counts", expected_hits),
        ):
            _expect(errors, zero_audit.get(field), expected, f"zero audit {field} mismatch")
        _verify_guard(errors, zero_guard, "zero")
        consumers = [event for event in zero_audit.get("events", []) if event.get("target") == "queue_consumer"]
        if len(consumers) != 2:
            errors.append("queue consumer event count mismatch")
            consumers = [{}, {}]
        else:
            for index, (event, frame) in enumerate(zip(consumers, (3, 4))):
                for field, expected in (
                    ("address", "0x0806365C"),
                    ("pc", "0x0806365E"),
                    ("lr", "0x080614C7"),
                    ("frame", frame),
                ):
                    _expect(
                        errors,
                        event.get(field),
                        expected,
                        f"queue consumer {field} mismatch: event {index}",
                    )
        expected_consumer_events = [
            {
                "address": "0x0806365C",
                "pc": "0x0806365E",
                "lr": "0x080614C7",
                "frame": frame,
            }
            for frame in (3, 4)
        ]
        zero = payload.get("zero_run", {})
        for field, expected in (
            ("run_id", ZERO_RUN_ID),
            ("input_checkpoint_sha256", setup_hash),
            ("inputs", []),
            ("capture_frames", 5),
            ("queue_consumer_hit_count", 2),
            ("first_consumer_frame", 3),
            ("second_consumer_frame", 4),
            ("consumer_events", expected_consumer_events),
            ("audit_sha256", _sha256(artifact_dir / "zero-audit.json")),
            ("guard_sha256", _sha256(artifact_dir / "zero-guard.json")),
            ("queue_snapshot_sha256", _sha256(artifact_dir / "queue-at-consumer.bin")),
            ("final_queue_snapshot_sha256", _sha256(artifact_dir / "final-queue.bin")),
            ("preflush_vram_sha256", _sha256(artifact_dir / "vram-at-consumer.bin")),
            ("final_vram_sha256", _sha256(artifact_dir / "vram-final.bin")),
            ("peak_tree_rss_mib", zero_guard.get("peak_tree_rss_mib")),
        ):
            _expect(errors, zero.get(field), expected, f"zero run {field} mismatch")

        queue = (artifact_dir / "queue-at-consumer.bin").read_bytes()
        final_queue = (artifact_dir / "final-queue.bin").read_bytes()
        pre_vram = (artifact_dir / "vram-at-consumer.bin").read_bytes()
        final_vram = (artifact_dir / "vram-final.bin").read_bytes()
        rom = rom_path.read_bytes()
        records = {
            record.get("source_pointer"): record
            for record in payload.get("tilemaps", [])
            if isinstance(record, dict)
        }
        if set(records) != {"0x083F1C98", "0x085B67E0"}:
            errors.append("v2 tilemap record set mismatch")
        occupied: list[set[int]] = []
        for spec in SPECS:
            pointer_text = _address(spec["pointer"])
            record = records.get(pointer_text, {})
            tilemap = _decode_lz77(rom, spec["pointer"] - 0x08000000)
            expected_slot = {
                "slot_index": spec["slot"],
                "status": 3,
                "source": _address(spec["wram"]),
                "destination": _address(spec["vram"]),
                "source_stride_halfwords": spec["width"],
                "row_count": spec["height"],
            }
            actual_slot = _slot(queue, spec["slot"])
            _expect(errors, actual_slot, expected_slot, f"raw queue slot mismatch: {pointer_text}")
            contract = (3, spec["wram"], spec["vram"], spec["width"], spec["height"])
            _expect(errors, _matching_count(queue, contract), 1, f"status-3 queue contract count mismatch: {pointer_text}")
            final_slot = _slot(final_queue, spec["slot"])
            _expect(errors, final_slot, {**expected_slot, "status": 2}, f"final queue slot mismatch: {pointer_text}")
            _expect(errors, _matching_count(final_queue, contract), 0, f"status-3 queue contract remained: {pointer_text}")
            pre_rows = _rows(pre_vram, spec["vram"], spec["width"], spec["height"])
            final_rows = _rows(final_vram, spec["vram"], spec["width"], spec["height"])
            if pre_rows == tilemap:
                errors.append(f"consumer snapshot already contains ROM tilemap: {pointer_text}")
            if final_rows != tilemap:
                errors.append(f"final VRAM rows do not match ROM tilemap: {pointer_text}")
            changed = sum(a != b for a, b in zip(pre_rows, final_rows))
            _expect(errors, changed, spec["changed"], f"changed-byte count mismatch: {pointer_text}")
            load = _event(zero_audit, spec["load_name"])
            for field, expected in (
                ("address", _address(spec["load_target"])),
                ("pc", _address(spec["load_target"] + 2)),
                ("frame", 2),
                ("r0", pointer_text),
                ("r1", _address(spec["wram"])),
            ):
                _expect(errors, load.get(field), expected, f"runtime load {field} mismatch: {pointer_text}")
            abi = abi_records.get(pointer_text, {})
            for field, expected in (
                ("load_call", _address(spec["load_target"])),
                ("queue_consumer", "0x0806365C"),
                ("vram_destination", _address(spec["vram"])),
                ("decompressed_sha256", hashlib.sha256(tilemap).hexdigest()),
            ):
                _expect(errors, abi.get(field), expected, f"ABI {field} mismatch: {pointer_text}")
            expected_record = {
                "source_pointer": pointer_text,
                "width_entries": spec["width"],
                "height_entries": spec["height"],
                "decompressed_size": len(tilemap),
                "decompressed_sha256": hashlib.sha256(tilemap).hexdigest(),
                "load_hit": {
                    "target": load.get("address"),
                    "pc": load.get("pc"),
                    "lr": load.get("lr"),
                    "frame": load.get("frame"),
                    "registers": {name: load.get(name) for name in ("r0", "r1", "r2", "r3")},
                },
                "queue_flush": {
                    "slot_at_first_consumer": expected_slot,
                    "status_at_final": final_slot["status"],
                    "preflush_rows_sha256": hashlib.sha256(pre_rows).hexdigest(),
                    "final_rows_sha256": hashlib.sha256(final_rows).hexdigest(),
                    "preflush_equals_source": pre_rows == tilemap,
                    "final_equals_source": final_rows == tilemap,
                    "changed_byte_count": changed,
                },
            }
            _expect(errors, record, expected_record, f"tilemap payload mismatch: {pointer_text}")
            addresses = {
                spec["vram"] + row * 64 + column
                for row in range(spec["height"])
                for column in range(spec["width"] * 2)
            }
            occupied.append(addresses)
        if len(occupied) == 2 and occupied[0] & occupied[1]:
            errors.append("tilemap VRAM row regions overlap")

        expected_summary = {
            "direct_queue_tilemap_denominator": 3,
            "runtime_verified_count": 3,
            "remaining_runtime_count": 0,
            "verified_source_pointers": ["0x0834928C", "0x083F1C98", "0x085B67E0"],
        }
        expected_scope = {
            "natural_base_rom_reachability_verified": True,
            "single_input_bridge_verified": True,
            "zero_input_checkpoint_continuation_verified": True,
            "all_direct_queue_sources_runtime_verified": True,
            "queue_status_transition_3_to_2_verified": True,
            "final_vram_rows_equal_rom_tilemaps": True,
            "exclusive_writer_causality_verified": False,
            "modified_rom_pixel_equivalence_verified": False,
            "exact_natural_language_identity_verified": False,
        }
        _expect(errors, payload.get("summary"), expected_summary, "runtime summary mismatch")
        _expect(errors, payload.get("scope"), expected_scope, "scope mismatch")
        _expect(errors, manifest.get("scope"), expected_scope, "manifest scope mismatch")
        if not (artifact_dir / "final.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append("final screenshot is not PNG")
        for name in ("scene-panel-setup.ss9", "final.ss9"):
            if (artifact_dir / name).stat().st_size < 1024:
                errors.append(f"savestate is unexpectedly small: {name}")
    except (KeyError, OSError, ValueError, json.JSONDecodeError, struct.error) as error:
        errors.append(str(error))
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    return {
        "schema": "residual-wram-tilemap-runtime-verification-v2",
        "verified": not errors,
        "runtime_verified_count": summary.get("runtime_verified_count", 0),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/residual-wram-tilemap-runtime-v2"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    artifact = args.artifact if args.artifact.is_absolute() else root / args.artifact
    report = verify_artifact(root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
