#!/usr/bin/env python3
"""Independently verify the natural selection-grid WRAM tilemap flush artifact."""

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
INPUT_STATE = "artifacts/lz77-palette-runtime-v1/runs/profile-browser-init/hit.ss9"
INPUT_STATE_SHA256 = "ad2d215c2054e694d67fdd40e22c0aff99fe930466126a2823129ab34e33570c"
ABI_PAYLOAD = "artifacts/residual-wram-tilemap-abi-v1/residual-wram-tilemap-abi.json"
ABI_PAYLOAD_SHA256 = "07e1f89b5aaff938184d5d31bea4174e995f96d10b8ffbee56bff0f609a27dfc"
ABI_MANIFEST = "artifacts/residual-wram-tilemap-abi-v1/manifest.json"
ABI_MANIFEST_SHA256 = "59380e804f695ba16f20617e8b012f6edb8463f854041c71ee17da92a34b0ddb"
OWNERSHIP_PAYLOAD = (
    "artifacts/residual-wram-tilemap-resource-ownership-v1/resource-ownership.json"
)
OWNERSHIP_PAYLOAD_SHA256 = "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
OWNERSHIP_MANIFEST = (
    "artifacts/residual-wram-tilemap-resource-ownership-v1/manifest.json"
)
OWNERSHIP_MANIFEST_SHA256 = "57e04df8c14ac9ee0b34a5102e42b1d9761e168343e3671b8e396fe938123ab5"
PARENT_RUNTIME_DIR = "artifacts/lz77-palette-runtime-v1"
PARENT_RUNTIME_MANIFEST = f"{PARENT_RUNTIME_DIR}/manifest.json"
PARENT_RUNTIME_MANIFEST_SHA256 = "d363310303d8b51d0cc6f64014489297071882859c547694b3db91f7c11c52bf"
PARENT_RUNTIME_EVIDENCE = f"{PARENT_RUNTIME_DIR}/evidence.json"
PARENT_RUNTIME_EVIDENCE_SHA256 = "d73fa7147eb7aa0b6a221cca73182d763c6321c70121067625368705f0b50967"
PARENT_RUNTIME_AUDIT = f"{PARENT_RUNTIME_DIR}/runs/profile-browser-init/audit.json"
PARENT_RUNTIME_AUDIT_SHA256 = "0b3b708a89cf09df1ac1d6a1bc1cbfa6d0abc9c7eddb7bb18641d509e1ab1c90"
SOURCE_POINTER = 0x0834928C
LOAD_TARGET = 0x0808AD3A
QUEUE_CONSUMER = 0x0806365C
WRAM_SOURCE = 0x02002B48
VRAM_DESTINATION = 0x0600001E
WIDTH = 15
HEIGHT = 20
ROW_BYTES = 30
VRAM_ROW_STRIDE = 64
RUN_ID = "selection-post-consumer-zero-20260731"
EXPECTED_FILES = {
    "audit.json",
    "final.png",
    "final-queue.bin",
    "final.ss9",
    "guard.json",
    "hit.ss9",
    "queue-at-consumer.bin",
    "runtime-evidence.json",
    "vram-at-consumer.bin",
    "vram-final.bin",
}
IMPLEMENTATION_PATHS = (
    "tools/mgba_wram_tilemap_probe.lua",
    "tests/test_mgba_wram_tilemap_probe_script.py",
    "tools/extract_tileset.py",
    "tools/export_residual_wram_tilemap_runtime_evidence.py",
    "tools/verify_residual_wram_tilemap_runtime_evidence.py",
    "tests/test_residual_wram_tilemap_runtime_evidence.py",
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
            raise ValueError("truncated LZ77 flag byte")
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


def _vram_rows(data: bytes) -> bytes:
    if len(data) != 0x18000:
        raise ValueError("VRAM capture is not 96 KiB")
    start = VRAM_DESTINATION - 0x06000000
    return b"".join(
        data[start + row * VRAM_ROW_STRIDE : start + row * VRAM_ROW_STRIDE + ROW_BYTES]
        for row in range(HEIGHT)
    )


def _queue_slot(data: bytes) -> dict[str, Any]:
    if len(data) != 0x100:
        raise ValueError("queue capture is not 256 bytes")
    status, source, destination, source_stride, row_count = struct.unpack_from(
        "<I2I2H", data, 0
    )
    return {
        "slot_index": 0,
        "status": status,
        "source": _address(source),
        "destination": _address(destination),
        "source_stride_halfwords": source_stride,
        "row_count": row_count,
    }


def _matching_queue_entry_count(data: bytes) -> int:
    if len(data) != 0x100:
        raise ValueError("queue capture is not 256 bytes")
    expected = (3, WRAM_SOURCE, VRAM_DESTINATION, WIDTH, HEIGHT)
    return sum(
        struct.unpack_from("<I2I2H", data, index * 16) == expected
        for index in range(16)
    )


def _expect_equal(errors: list[str], actual: object, expected: object, message: str) -> None:
    if actual != expected:
        errors.append(message)


def _verify_parent_manifest(
    root: Path,
    relative: str,
    expected_sha256: str,
    artifact_id: str,
    payload_name: str,
    payload_sha256: str,
    errors: list[str],
    label: str,
) -> dict[str, Any]:
    path = root / relative
    if _sha256(path) != expected_sha256:
        errors.append(f"{label} manifest SHA-256 mismatch")
    manifest = _read_json(path)
    _expect_equal(errors, manifest.get("schema"), "git-artifact-promotion-v1", f"{label} manifest schema mismatch")
    _expect_equal(errors, manifest.get("artifact_id"), artifact_id, f"{label} artifact ID mismatch")
    _expect_equal(errors, manifest.get("artifact_status"), "accepted", f"{label} artifact is not accepted")
    _expect_equal(errors, manifest.get("payload_file"), payload_name, f"{label} payload file mismatch")
    _expect_equal(errors, manifest.get("payload_sha256"), payload_sha256, f"{label} payload SHA-256 mismatch")
    artifact_dir = path.parent
    paths = list(artifact_dir.rglob("*"))
    if any(candidate.is_symlink() for candidate in paths):
        errors.append(f"{label} artifact contains a symbolic link")
    actual = {
        candidate.relative_to(artifact_dir).as_posix(): candidate
        for candidate in paths
        if candidate.is_file() and candidate.name != "manifest.json"
    }
    inventory = manifest.get("files")
    if not isinstance(inventory, dict) or set(inventory) != set(actual):
        errors.append(f"{label} manifest file inventory mismatch")
        inventory = {}
    for name, candidate in actual.items():
        if inventory.get(name) != _sha256(candidate):
            errors.append(f"{label} file hash mismatch: {name}")
    return manifest


def _verify_parent_artifacts(root: Path, errors: list[str]) -> None:
    _verify_parent_manifest(
        root,
        PARENT_RUNTIME_MANIFEST,
        PARENT_RUNTIME_MANIFEST_SHA256,
        "lz77-palette-runtime-v1",
        "evidence.json",
        PARENT_RUNTIME_EVIDENCE_SHA256,
        errors,
        "parent runtime",
    )
    evidence_path = root / PARENT_RUNTIME_EVIDENCE
    if _sha256(evidence_path) != PARENT_RUNTIME_EVIDENCE_SHA256:
        errors.append("parent runtime evidence SHA-256 mismatch")
    evidence = _read_json(evidence_path)
    _expect_equal(errors, evidence.get("schema"), "lz77-palette-runtime-evidence-v1", "parent runtime evidence schema mismatch")
    entries = [
        entry
        for entry in evidence.get("entries", [])
        if entry.get("route") == "profile-browser-init"
    ]
    if len(entries) != 1:
        errors.append("parent runtime profile route mismatch")
    else:
        entry = entries[0]
        for field, expected in (
            ("graphics_address", "0x083496F8"),
            ("target_pc", "0x0808B5EE"),
            ("hit_frame", 54),
            ("audit", "runs/profile-browser-init/audit.json"),
            ("audit_sha256", PARENT_RUNTIME_AUDIT_SHA256),
        ):
            _expect_equal(errors, entry.get(field), expected, f"parent runtime entry {field} mismatch")
    audit_path = root / PARENT_RUNTIME_AUDIT
    if _sha256(audit_path) != PARENT_RUNTIME_AUDIT_SHA256:
        errors.append("parent runtime audit SHA-256 mismatch")
    audit = _read_json(audit_path)
    expected_inputs = [
        {"key": "Down", "down_frame": 2, "up_frame": 4, "hold_frames": 2},
        {"key": "Down", "down_frame": 18, "up_frame": 20, "hold_frames": 2},
        {"key": "A", "down_frame": 34, "up_frame": 36, "hold_frames": 2},
        {"key": "A", "down_frame": 50, "up_frame": 52, "hold_frames": 2},
    ]
    for field, expected in (
        ("schema", "mgba-lz77-palette-probe-v1"),
        ("route", "profile-browser-init"),
        ("outcome", "oam-not-observed"),
        ("rom_sha256", ROM_SHA256),
        ("binary_sha256", EMULATOR_SHA256),
        ("target_pc", "0x0808B5EE"),
        ("hit_frame", 54),
        ("hit_pc", "0x0808B5F0"),
        ("inputs", expected_inputs),
    ):
        _expect_equal(errors, audit.get(field), expected, f"parent runtime audit {field} mismatch")
    runtime_manifest = _read_json(root / PARENT_RUNTIME_MANIFEST)
    _expect_equal(
        errors,
        runtime_manifest.get("files", {}).get("runs/profile-browser-init/hit.ss9"),
        INPUT_STATE_SHA256,
        "parent runtime hit checkpoint hash mismatch",
    )

    _verify_parent_manifest(
        root,
        ABI_MANIFEST,
        ABI_MANIFEST_SHA256,
        "residual-wram-tilemap-abi-v1",
        "residual-wram-tilemap-abi.json",
        ABI_PAYLOAD_SHA256,
        errors,
        "ABI parent",
    )
    _verify_parent_manifest(
        root,
        OWNERSHIP_MANIFEST,
        OWNERSHIP_MANIFEST_SHA256,
        "residual-wram-tilemap-resource-ownership-v1",
        "resource-ownership.json",
        OWNERSHIP_PAYLOAD_SHA256,
        errors,
        "ownership parent",
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
        _expect_equal(errors, manifest.get("schema"), "git-artifact-promotion-v1", "manifest schema mismatch")
        _expect_equal(errors, manifest.get("artifact_id"), "residual-wram-tilemap-runtime-v1", "artifact ID mismatch")
        _expect_equal(errors, manifest.get("artifact_schema"), "residual-wram-tilemap-runtime-evidence-v1", "artifact schema mismatch")
        _expect_equal(errors, manifest.get("artifact_status"), "accepted", "artifact status mismatch")
        _expect_equal(errors, manifest.get("payload_file"), "runtime-evidence.json", "payload file mismatch")
        file_hashes = manifest.get("files")
        if not isinstance(file_hashes, dict) or set(file_hashes) != EXPECTED_FILES:
            errors.append("manifest file inventory mismatch")
            file_hashes = {}
        for relative, path in actual_files.items():
            if file_hashes.get(relative) != _sha256(path):
                errors.append(f"artifact hash mismatch: {relative}")
        payload_hash = _sha256(artifact_dir / "runtime-evidence.json")
        if manifest.get("payload_sha256") != payload_hash:
            errors.append("payload SHA-256 mismatch")

        implementation = manifest.get("implementation")
        if not isinstance(implementation, dict) or set(implementation) != set(IMPLEMENTATION_PATHS):
            errors.append("implementation inventory mismatch")
            implementation = {}
        for relative in IMPLEMENTATION_PATHS:
            if implementation.get(relative) != _sha256(root / relative):
                errors.append(f"implementation hash mismatch: {relative}")
        _expect_equal(
            errors,
            manifest.get("verifier"),
            {
                "command": [
                    "python3",
                    "tools/verify_residual_wram_tilemap_runtime_evidence.py",
                    "--root",
                    ".",
                    "--artifact",
                    "artifacts/residual-wram-tilemap-runtime-v1",
                ],
                "exit_code": 0,
            },
            "manifest verifier declaration mismatch",
        )

        _expect_equal(errors, payload.get("schema"), "residual-wram-tilemap-runtime-evidence-v1", "payload schema mismatch")
        _expect_equal(errors, payload.get("rom"), {"path": "rom/base.gba", "sha256": ROM_SHA256}, "ROM provenance mismatch")
        _expect_equal(
            errors,
            payload.get("emulator"),
            {"source_commit": EMULATOR_COMMIT, "binary_sha256": EMULATOR_SHA256},
            "emulator provenance mismatch",
        )
        _expect_equal(
            errors,
            payload.get("probe"),
            {
                "path": "tools/mgba_wram_tilemap_probe.lua",
                "sha256": _sha256(root / "tools/mgba_wram_tilemap_probe.lua"),
                "test": "tests/test_mgba_wram_tilemap_probe_script.py",
                "test_sha256": _sha256(
                    root / "tests/test_mgba_wram_tilemap_probe_script.py"
                ),
            },
            "probe declaration mismatch",
        )
        checkpoint = payload.get("input_checkpoint", {})
        _expect_equal(errors, checkpoint.get("path"), INPUT_STATE, "checkpoint path mismatch")
        _expect_equal(errors, checkpoint.get("sha256"), INPUT_STATE_SHA256, "checkpoint SHA-256 mismatch")
        _expect_equal(
            errors,
            checkpoint.get("provenance"),
            {
                "manifest_path": PARENT_RUNTIME_MANIFEST,
                "manifest_sha256": PARENT_RUNTIME_MANIFEST_SHA256,
                "evidence_path": PARENT_RUNTIME_EVIDENCE,
                "evidence_sha256": PARENT_RUNTIME_EVIDENCE_SHA256,
                "audit_path": PARENT_RUNTIME_AUDIT,
                "audit_sha256": PARENT_RUNTIME_AUDIT_SHA256,
                "route": "profile-browser-init",
                "target_pc": "0x0808B5EE",
                "hit_frame": 54,
            },
            "checkpoint parent provenance mismatch",
        )
        _verify_parent_artifacts(root, errors)
        if _sha256(root / INPUT_STATE) != INPUT_STATE_SHA256:
            errors.append("tracked input checkpoint changed")

        rom_path = root / "rom/base.gba"
        if _sha256(rom_path) != ROM_SHA256:
            errors.append("base ROM SHA-256 mismatch")
        tilemap = _decode_lz77(rom_path.read_bytes(), SOURCE_POINTER - 0x08000000)
        if len(tilemap) != WIDTH * HEIGHT * 2:
            errors.append("ROM tilemap size mismatch")

        source_artifacts = payload.get("source_artifacts", {})
        for key, expected_path, expected_hash, manifest_path, manifest_hash in (
            ("abi", ABI_PAYLOAD, ABI_PAYLOAD_SHA256, ABI_MANIFEST, ABI_MANIFEST_SHA256),
            (
                "ownership",
                OWNERSHIP_PAYLOAD,
                OWNERSHIP_PAYLOAD_SHA256,
                OWNERSHIP_MANIFEST,
                OWNERSHIP_MANIFEST_SHA256,
            ),
        ):
            record = source_artifacts.get(key, {})
            _expect_equal(errors, record.get("path"), expected_path, f"{key} artifact path mismatch")
            actual_hash = _sha256(root / expected_path)
            _expect_equal(errors, actual_hash, expected_hash, f"{key} parent payload changed")
            _expect_equal(errors, record.get("sha256"), expected_hash, f"{key} artifact SHA-256 mismatch")
            _expect_equal(errors, record.get("manifest_path"), manifest_path, f"{key} manifest path mismatch")
            _expect_equal(errors, record.get("manifest_sha256"), manifest_hash, f"{key} manifest SHA-256 mismatch")

        abi = _read_json(root / ABI_PAYLOAD)
        abi_records = {
            record["source_pointer"]: record for record in abi.get("tilemaps", [])
        }
        if set(abi_records) != {"0x0834928C", "0x083F1C98", "0x085B67E0"}:
            errors.append("direct queue source denominator mismatch")
        abi_record = abi_records.get("0x0834928C", {})
        for field, expected in (
            ("load_call", "0x0808AD3A"),
            ("queue_consumer", "0x0806365C"),
            ("vram_destination", "0x0600001E"),
            ("decompressed_size", 600),
            ("decompressed_sha256", hashlib.sha256(tilemap).hexdigest()),
        ):
            _expect_equal(errors, abi_record.get(field), expected, f"ABI {field} mismatch")
        ownership = _read_json(root / OWNERSHIP_PAYLOAD)
        owners = {
            record["tilemap_source_pointer"]: record
            for record in ownership.get("ownership_records", [])
        }
        owner = owners.get("0x0834928C", {})
        for field, expected in (
            ("scene_identity", "selection_grid_overlay"),
            ("setup_function", "0x0808B58C"),
            ("vram_destination", "0x0600001E"),
            ("tilemap_abi_sha256", hashlib.sha256(tilemap).hexdigest()),
        ):
            _expect_equal(errors, owner.get(field), expected, f"ownership {field} mismatch")

        run = payload.get("run", {})
        expected_hits = {
            "text_bg_loop_link": 0,
            "text_bg_setup": 0,
            "selection_load": 1,
            "scene_panel_setup": 0,
            "scene_panel_upper_load": 0,
            "scene_panel_lower_load": 0,
            "scene_panel_crop_load": 0,
            "choice_phase_a_load": 0,
            "choice_phase_a_submit": 0,
            "choice_phase_b_initial_load": 0,
            "choice_phase_b_second_load": 0,
            "choice_phase_b_submit": 0,
            "queue_consumer": 77,
        }
        _expect_equal(errors, run.get("run_id"), RUN_ID, "run ID mismatch")
        _expect_equal(errors, run.get("inputs"), [], "runtime input set is not empty")
        expected_hits["queue_consumer"] = 1
        _expect_equal(errors, run.get("capture_frames"), 3, "capture duration mismatch")
        _expect_equal(errors, run.get("final_frame"), 3, "final frame mismatch")
        _expect_equal(errors, run.get("total_hits"), 2, "total hit count mismatch")
        _expect_equal(errors, run.get("hit_counts"), expected_hits, "target hit counts mismatch")

        audit_path = artifact_dir / "audit.json"
        guard_path = artifact_dir / "guard.json"
        _expect_equal(errors, run.get("audit_sha256"), _sha256(audit_path), "audit hash binding mismatch")
        _expect_equal(errors, run.get("guard_sha256"), _sha256(guard_path), "guard hash binding mismatch")
        audit = _read_json(audit_path)
        for field, expected in (
            ("schema", "mgba-wram-tilemap-probe-v1"),
            ("run_id", RUN_ID),
            ("outcome", "targets-observed"),
            ("rom_sha256", ROM_SHA256),
            ("binary_sha256", EMULATOR_SHA256),
            ("input_state_sha256", INPUT_STATE_SHA256),
            ("inputs", []),
            ("capture_frames", 3),
            ("frame", 3),
            ("total_hits", 2),
            ("hit_counts", expected_hits),
        ):
            _expect_equal(errors, audit.get(field), expected, f"audit {field} mismatch")
        guard = _read_json(guard_path)
        for field, expected in (
            ("reason", "completed"),
            ("exit_code", 0),
            ("degraded", False),
            ("completion_trigger", "success-marker"),
        ):
            _expect_equal(errors, guard.get(field), expected, f"guard {field} mismatch")
        peak = guard.get("peak_tree_rss_mib")
        if not isinstance(peak, (int, float)) or peak > 1536:
            errors.append("guard peak RSS exceeds accepted bound")
        _expect_equal(errors, run.get("peak_tree_rss_mib"), peak, "guard peak RSS binding mismatch")

        events = audit.get("events", [])
        load_events = [event for event in events if event.get("target") == "selection_load"]
        consumer_events = [event for event in events if event.get("target") == "queue_consumer"]
        if not load_events or not consumer_events:
            errors.append("required runtime events are missing")
            load_event = consumer_event = {}
        else:
            load_event, consumer_event = load_events[0], consumer_events[0]
        expected_load = {
            "target": "0x0808AD3A",
            "pc": "0x0808AD3C",
            "lr": "0x0808AD31",
            "frame": 0,
            "cycle": "866596474",
            "registers": {
                "r0": "0x0834928C",
                "r1": "0x02002B48",
                "r2": "0x000002C8",
                "r3": "0x00000170",
            },
        }
        _expect_equal(errors, payload.get("load_hit"), expected_load, "load hit semantic mismatch")
        for field, expected in (
            ("address", "0x0808AD3A"),
            ("pc", "0x0808AD3C"),
            ("lr", "0x0808AD31"),
            ("frame", 0),
            ("r0", "0x0834928C"),
            ("r1", "0x02002B48"),
            ("r2", "0x000002C8"),
            ("r3", "0x00000170"),
        ):
            _expect_equal(errors, load_event.get(field), expected, f"audit load {field} mismatch")

        queue_path = artifact_dir / "queue-at-consumer.bin"
        slot = _queue_slot(queue_path.read_bytes())
        expected_slot = {
            "slot_index": 0,
            "status": 3,
            "source": "0x02002B48",
            "destination": "0x0600001E",
            "source_stride_halfwords": 15,
            "row_count": 20,
        }
        flush = payload.get("queue_flush", {})
        _expect_equal(errors, flush.get("slot"), expected_slot, "queue destination mismatch")
        _expect_equal(errors, slot, expected_slot, "raw queue slot mismatch")
        _expect_equal(errors, flush.get("consumer_target"), "0x0806365C", "consumer target mismatch")
        _expect_equal(errors, flush.get("consumer_pc"), "0x0806365E", "consumer PC mismatch")
        _expect_equal(errors, flush.get("consumer_lr"), "0x080614C7", "consumer LR mismatch")
        _expect_equal(errors, flush.get("first_consumer_frame"), 2, "first consumer frame mismatch")
        for field, expected in (
            ("address", "0x0806365C"),
            ("pc", "0x0806365E"),
            ("lr", "0x080614C7"),
            ("frame", 2),
        ):
            _expect_equal(errors, consumer_event.get(field), expected, f"audit consumer {field} mismatch")
        _expect_equal(errors, flush.get("queue_snapshot_sha256"), _sha256(queue_path), "queue snapshot hash binding mismatch")
        final_queue_path = artifact_dir / "final-queue.bin"
        final_queue_match_count = _matching_queue_entry_count(
            final_queue_path.read_bytes()
        )
        _expect_equal(
            errors,
            flush.get("post_consumer_queue_snapshot_sha256"),
            _sha256(final_queue_path),
            "post-consumer queue snapshot hash binding mismatch",
        )
        _expect_equal(errors, flush.get("post_consumer_frame"), 3, "post-consumer frame mismatch")
        _expect_equal(
            errors,
            flush.get("captured_entry_count_at_post_consumer"),
            final_queue_match_count,
            "post-consumer captured entry count mismatch",
        )
        _expect_equal(errors, final_queue_match_count, 0, "captured status-3 entry remained after consumer")
        _expect_equal(
            errors,
            flush.get("captured_entry_retired_before_post_consumer_capture"),
            True,
            "captured entry retirement declaration mismatch",
        )

        pre_rows = _vram_rows((artifact_dir / "vram-at-consumer.bin").read_bytes())
        final_rows = _vram_rows((artifact_dir / "vram-final.bin").read_bytes())
        if pre_rows == tilemap:
            errors.append("consumer snapshot already contains ROM tilemap")
        if final_rows != tilemap:
            errors.append("final VRAM rows do not match ROM tilemap")
        changed = sum(a != b for a, b in zip(pre_rows, final_rows))
        _expect_equal(errors, flush.get("preflush_rows_sha256"), hashlib.sha256(pre_rows).hexdigest(), "preflush rows hash mismatch")
        _expect_equal(errors, flush.get("final_rows_sha256"), hashlib.sha256(final_rows).hexdigest(), "final rows hash mismatch")
        _expect_equal(errors, flush.get("preflush_equals_source"), False, "preflush equality declaration mismatch")
        _expect_equal(errors, flush.get("final_equals_source"), True, "final equality declaration mismatch")
        _expect_equal(errors, flush.get("changed_byte_count"), changed, "changed byte count mismatch")
        _expect_equal(errors, changed, 600, "unexpected changed-byte denominator")

        tilemap_record = payload.get("tilemap", {})
        for field, expected in (
            ("source_pointer", "0x0834928C"),
            ("width_entries", 15),
            ("height_entries", 20),
            ("decompressed_size", 600),
            ("decompressed_sha256", hashlib.sha256(tilemap).hexdigest()),
            ("vram_destination", "0x0600001E"),
            ("destination_row_stride_bytes", 64),
        ):
            _expect_equal(errors, tilemap_record.get(field), expected, f"tilemap {field} mismatch")
        _expect_equal(errors, payload.get("remaining_direct_queue_sources"), ["0x083F1C98", "0x085B67E0"], "remaining source set mismatch")
        _expect_equal(
            errors,
            payload.get("summary"),
            {
                "direct_queue_tilemap_denominator": 3,
                "runtime_verified_count": 1,
                "remaining_runtime_count": 2,
                "verified_source_pointer": "0x0834928C",
            },
            "runtime summary mismatch",
        )
        expected_scope = {
            "natural_base_rom_reachability_verified": True,
            "zero_input_checkpoint_continuation_verified": True,
            "queue_slot_status3_verified": True,
            "natural_queue_consumer_flush_verified": True,
            "post_consumer_queue_retirement_verified": True,
            "final_vram_rows_equal_rom_tilemap": True,
            "exclusive_writer_causality_verified": False,
            "other_two_direct_queue_sources_runtime_verified": False,
            "modified_rom_pixel_equivalence_verified": False,
            "exact_natural_language_identity_verified": False,
        }
        _expect_equal(errors, payload.get("scope"), expected_scope, "scope declaration mismatch")
        _expect_equal(errors, manifest.get("scope"), expected_scope, "manifest scope mismatch")
        if not (artifact_dir / "final.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append("final screenshot is not PNG")
        for name in ("hit.ss9", "final.ss9"):
            if (artifact_dir / name).stat().st_size < 1024:
                errors.append(f"savestate is unexpectedly small: {name}")
    except (KeyError, OSError, ValueError, json.JSONDecodeError, struct.error) as error:
        errors.append(str(error))

    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    return {
        "schema": "residual-wram-tilemap-runtime-verification-v1",
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
        default=Path("artifacts/residual-wram-tilemap-runtime-v1"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    artifact = args.artifact if args.artifact.is_absolute() else root / args.artifact
    report = verify_artifact(root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
