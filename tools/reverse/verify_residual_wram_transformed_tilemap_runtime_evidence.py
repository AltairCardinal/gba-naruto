#!/usr/bin/env python3
"""Independently verify the controlled transformed-tilemap runtime artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any
import zlib


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
EMULATOR_SHA256 = "4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72"
EMULATOR_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
UNLOCK_PARENT_SHA256 = "78db5e103f5fc471bad2d7cb8628b3964d46791ccbf733266c0754d497dfd2bc"
CHOICE_ENTRY_SHA256 = "1fefd560c5a97ba3a15b1f330cfee5aeaba5017da46e01fb5695906412da6027"
STATE3_SHA256 = "dc5a1c1847600bd9719f6e6f4dbfa6237110426f0f942cb74568cdfefd6c0864"
ABI_PATH = "artifacts/residual-wram-visual-metadata-abi-v2/residual-wram-visual-metadata-abi.json"
ABI_SHA256 = "4cee47ab097986d50ed0d3b3017fc4fd429037405ee247876022dfd08beac260"
OWNERSHIP_PATH = "artifacts/residual-wram-tilemap-resource-ownership-v1/resource-ownership.json"
OWNERSHIP_SHA256 = "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
STAGING = 0x0200A640
OUTPUT = 0x0200A760
DESTINATION = 0x06000806
ROW_BYTES = 24
ROW_STRIDE = 64
ROWS = 12
VRAM_BYTES = 0x18000
QUEUE_BASE = 0x03005BBC
QUEUE_SLOT_SIZE = 16
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GBA_STATE_SIZE = 0x61000

RUN_SPECS = {
    "phase-a": {
        "run_id": "choice-state3-phase-a-closure-v6-20260801",
        "capture_frames": 240,
        "inputs": [
            {"key": "A", "down_frame": 18, "up_frame": 20, "hold_frames": 2},
            {"key": "A", "down_frame": 100, "up_frame": 102, "hold_frames": 2},
        ],
        "sources": ["0x084634B8"],
    },
    "phase-b": {
        "run_id": "choice-state3-phase-b-closure-v6-20260801",
        "capture_frames": 280,
        "inputs": [
            {"key": "Down", "down_frame": 18, "up_frame": 20, "hold_frames": 2},
            {"key": "A", "down_frame": 60, "up_frame": 62, "hold_frames": 2},
            {"key": "A", "down_frame": 140, "up_frame": 142, "hold_frames": 2},
        ],
        "sources": ["0x0846356C", "0x084635D8"],
    },
}
SOURCE_SPECS = {
    "0x084634B8": ("phase-a", "single_phase", "choice_phase_a_load", "0x08090B5C", "choice_phase_a_load_post", "0x08090B60", "choice_phase_a_submit", "0x08090CB0"),
    "0x0846356C": ("phase-b", "initial_phase", "choice_phase_b_initial_load", "0x08090D56", "choice_phase_b_initial_load_post", "0x08090D62", "choice_phase_b_submit", "0x08090F3C"),
    "0x084635D8": ("phase-b", "second_phase", "choice_phase_b_second_load", "0x08090DC4", "choice_phase_b_second_load_post", "0x08090DD0", "choice_phase_b_submit", "0x08090F3C"),
}
SOURCE_FILES = {
    "staging.bin": "staging_sha256",
    "load.ss9": "load_checkpoint_sha256",
    "load-post.ss9": "load_post_checkpoint_sha256",
    "queue-pre.bin": "queue_pre_sha256",
    "queue-post.bin": "queue_post_sha256",
    "pre-vram.bin": "pre_vram_sha256",
    "post-vram.bin": "post_vram_sha256",
    "output-rows.bin": "output_rows_sha256",
    "pre-vram-rows.bin": "pre_vram_rows_sha256",
    "post-vram-rows.bin": "post_vram_rows_sha256",
    "queue-pre.ss9": "queue_pre_checkpoint_sha256",
    "queue-post.ss9": "queue_post_checkpoint_sha256",
    "queue-pre.png": "queue_pre_png_sha256",
    "queue-post.png": "queue_post_png_sha256",
}
IMPLEMENTATION_PATHS = (
    "tools/mgba_wram_tilemap_sequence_probe.lua",
    "tests/test_mgba_wram_tilemap_sequence_probe_script.py",
    "tools/export_residual_wram_transformed_tilemap_runtime_evidence.py",
    "tools/verify_residual_wram_transformed_tilemap_runtime_evidence.py",
    "tests/test_residual_wram_transformed_tilemap_runtime_evidence.py",
    "tools/inspect_mgba_savestate.py",
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


def _expect(errors: list[str], actual: object, expected: object, message: str) -> None:
    if actual != expected:
        errors.append(message)


def _decode_lz77(data: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError("invalid LZ77 header")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        flags = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
                token = (data[cursor] << 8) | data[cursor + 1]
                cursor += 2
                length, distance = (token >> 12) + 3, (token & 0xFFF) + 1
                if distance > len(output):
                    raise ValueError("invalid LZ77 distance")
                for _ in range(length):
                    if len(output) >= size:
                        break
                    output.append(output[-distance])
            else:
                output.append(data[cursor])
                cursor += 1
    return bytes(output)


def _event(audit: dict[str, Any], target: str, frame: int | None = None) -> dict[str, Any]:
    rows = [
        event for event in audit.get("events", [])
        if event.get("target") == target and (frame is None or event.get("frame") == frame)
    ]
    return rows[0] if rows else {}


def _event_record(event: dict[str, Any]) -> dict[str, Any]:
    return {
        key: event.get(key)
        for key in ("target", "address", "frame", "cycle", "pc", "lr", "r0", "r1", "r2", "r3")
    }


def _guard_ok(guard: dict[str, Any]) -> bool:
    return (
        guard.get("reason") == "completed"
        and guard.get("exit_code") == 0
        and guard.get("degraded") is False
        and guard.get("completion_trigger") == "success-marker"
        and guard.get("peak_tree_rss_mib", 1537) <= 1536
    )


def _rows(vram: bytes) -> bytes:
    start = DESTINATION - 0x06000000
    return b"".join(
        vram[start + row * ROW_STRIDE : start + row * ROW_STRIDE + ROW_BYTES]
        for row in range(ROWS)
    )


def _slot(queue: bytes, index: int) -> tuple[int, int, int, int, int]:
    if len(queue) != 256 or not 0 <= index < 16:
        raise ValueError("invalid queue capture")
    return struct.unpack_from("<IIIHH", queue, index * 16)


def _ss9_state(path: Path) -> bytes:
    png = path.read_bytes()
    if not png.startswith(PNG_SIGNATURE):
        raise ValueError("savestate is not a PNG container")
    cursor = len(PNG_SIGNATURE)
    state_chunks: list[bytes] = []
    saw_iend = False
    while cursor < len(png):
        if cursor + 12 > len(png):
            raise ValueError("truncated savestate PNG chunk")
        size = struct.unpack_from(">I", png, cursor)[0]
        tag = png[cursor + 4 : cursor + 8]
        start, end = cursor + 8, cursor + 8 + size
        if end + 4 > len(png):
            raise ValueError("truncated savestate PNG payload")
        payload = png[start:end]
        stored_crc = struct.unpack_from(">I", png, end)[0]
        if zlib.crc32(tag + payload) & 0xFFFFFFFF != stored_crc:
            raise ValueError("savestate PNG CRC mismatch")
        if tag == b"gbAs":
            state_chunks.append(payload)
        cursor = end + 4
        if tag == b"IEND":
            if payload or cursor != len(png):
                raise ValueError("invalid savestate PNG IEND")
            saw_iend = True
            break
    if not saw_iend or len(state_chunks) != 1:
        raise ValueError("savestate must contain one gbAs chunk")
    decoder = zlib.decompressobj()
    state = decoder.decompress(state_chunks[0], GBA_STATE_SIZE + 1)
    if decoder.unconsumed_tail:
        raise ValueError("savestate payload exceeds expected size")
    state += decoder.flush()
    if not decoder.eof or decoder.unused_data or len(state) != GBA_STATE_SIZE:
        raise ValueError("invalid compressed savestate payload")
    version = struct.unpack_from("<I", state, 0)[0]
    if not 0x01000000 <= version <= 0x0100000B:
        raise ValueError("unsupported savestate version")
    return state


def _state_memory(state: bytes, address: int, size: int) -> bytes:
    regions = (
        (0x04000000, 0x00400, 0x00400),
        (0x05000000, 0x00400, 0x00800),
        (0x07000000, 0x00400, 0x00C00),
        (0x06000000, 0x18000, 0x01000),
        (0x03000000, 0x08000, 0x19000),
        (0x02000000, 0x40000, 0x21000),
    )
    for base, length, offset in regions:
        relative = address - base
        if 0 <= relative and relative + size <= length:
            return state[offset + relative : offset + relative + size]
    raise ValueError("savestate memory read outside mapped region")


def _state_pc(state: bytes) -> int:
    return struct.unpack_from("<I", state, 0x20 + 15 * 4)[0]


def _runtime_transform(before: bytes, staging: bytes, output: bytes) -> dict[str, Any]:
    if not all(len(blob) == ROW_BYTES * ROWS for blob in (before, staging, output)):
        raise ValueError("invalid transformed tilemap buffer size")
    before_entries = list(struct.unpack("<144H", before))
    staging_entries = struct.unpack("<144H", staging)
    output_entries = tuple(struct.unpack("<144H", output))
    candidates: list[tuple[int, int, int]] = []
    for origin_y in range(-2, ROWS):
        for origin_x in range(-2, 12):
            expected = before_entries.copy()
            written = 0
            for offset_y in range(3):
                for offset_x in range(3):
                    x, y = origin_x + offset_x, origin_y + offset_y
                    if 0 <= x < 12 and 0 <= y < ROWS:
                        index = y * 12 + x
                        expected[index] = (staging_entries[index] + 0x02BC) & 0xFFFF
                        written += 1
            if written and tuple(expected) == output_entries:
                candidates.append((origin_x, origin_y, written))
    if len(candidates) != 1:
        raise ValueError(f"runtime transform mismatch: candidates={candidates}")
    origin_x, origin_y, written = candidates[0]
    return {
        "contract": "preserve_load_post_output_then_update_clipped_3x3_with_entry_plus_0x02BC",
        "origin_x": origin_x,
        "origin_y": origin_y,
        "written_entry_count": written,
        "load_post_output_sha256": hashlib.sha256(before).hexdigest(),
        "verified_against_load_post_savestate": True,
    }


def _queue_events_match(
    correlation: dict[str, Any], audit_events: list[dict[str, Any]]
) -> bool:
    pre = correlation.get("queue_pre_event", {})
    post = correlation.get("queue_post_event", {})
    slot = correlation.get("slot_index")
    if not isinstance(pre, dict) or not isinstance(post, dict) or not isinstance(slot, int):
        return False
    slot_address = f"0x{QUEUE_BASE + slot * QUEUE_SLOT_SIZE:08X}"
    return (
        pre.get("target") == "queue_consumer"
        and pre.get("address") == "0x0806365C"
        and pre.get("pc") == "0x0806365E"
        and pre.get("frame") == correlation.get("queue_pre_frame")
        and pre.get("frame") == post.get("frame")
        and str(pre.get("cycle")) == str(correlation.get("queue_pre_cycle"))
        and post.get("target") == "queue_consumer_post"
        and post.get("address") == "0x080636CE"
        and post.get("pc") == "0x080636D0"
        and post.get("frame") == correlation.get("queue_post_frame")
        and str(post.get("cycle")) == str(correlation.get("queue_post_cycle"))
        and post.get("lr") == "0x080636B5"
        and post.get("r2") == slot_address
        and post.get("r4") == slot_address
        and post.get("r7") == f"0x{slot + 1:08X}"
        and sum(event == pre for event in audit_events) == 1
        and sum(event == post for event in audit_events) == 1
    )


def _overlapping_status3_slots(queue: bytes, selected: int) -> list[int]:
    target_rows = [
        (DESTINATION + row * ROW_STRIDE, DESTINATION + row * ROW_STRIDE + ROW_BYTES)
        for row in range(ROWS)
    ]
    overlaps: list[int] = []
    for slot_index in range(16):
        if slot_index == selected:
            continue
        status, _source, destination, width, row_count = _slot(queue, slot_index)
        if status != 3 or width == 0 or row_count == 0:
            continue
        candidate_rows = [
            (destination + row * ROW_STRIDE, destination + row * ROW_STRIDE + width * 2)
            for row in range(row_count)
        ]
        if any(
            left < target_right and target_left < right
            for left, right in candidate_rows
            for target_left, target_right in target_rows
        ):
            overlaps.append(slot_index)
    return overlaps


def _expected_files() -> set[str]:
    result = {
        "entry/unlock-parent.ss9", "entry/unlock-audit.json", "entry/unlock-done.marker",
        "entry/unlock-guard.json", "entry/choice-screen-entry.ss9", "entry/state3-audit.json",
        "entry/state3-done.marker", "entry/state3-guard.json", "entry/choice-state3.ss9",
        "runtime-evidence.json",
    }
    for run in RUN_SPECS:
        result.update({f"runs/{run}/{name}" for name in ("audit.json", "done.marker", "guard.json", "final.ss9", "final.png")})
    for pointer in SOURCE_SPECS:
        result.update({f"sources/{pointer[2:]}/{name}" for name in SOURCE_FILES})
    return result


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    root, artifact_dir = root.resolve(), artifact_dir.resolve()
    errors: list[str] = []
    payload: dict[str, Any] = {}
    try:
        paths = list(artifact_dir.rglob("*"))
        if any(path.is_symlink() for path in paths):
            errors.append("artifact contains a symbolic link")
        actual = {
            path.relative_to(artifact_dir).as_posix(): path
            for path in paths if path.is_file() and path.name != "manifest.json"
        }
        expected_files = _expected_files()
        if set(actual) != expected_files:
            errors.append("artifact file inventory mismatch")
        manifest = _read_json(artifact_dir / "manifest.json")
        payload = _read_json(artifact_dir / "runtime-evidence.json")
        for field, expected in (
            ("schema", "git-artifact-promotion-v1"),
            ("artifact_id", "residual-wram-transformed-tilemap-runtime-v1"),
            ("artifact_schema", "residual-wram-transformed-tilemap-runtime-evidence-v1"),
            ("artifact_status", "accepted"),
            ("payload_file", "runtime-evidence.json"),
        ):
            _expect(errors, manifest.get(field), expected, f"manifest {field} mismatch")
        inventory = manifest.get("files", {})
        if not isinstance(inventory, dict) or set(inventory) != expected_files:
            errors.append("manifest file inventory mismatch")
            inventory = {}
        for relative, path in actual.items():
            _expect(errors, inventory.get(relative), _sha256(path), f"artifact hash mismatch: {relative}")
        _expect(errors, manifest.get("payload_sha256"), _sha256(artifact_dir / "runtime-evidence.json"), "payload hash mismatch")
        implementation = manifest.get("implementation", {})
        if not isinstance(implementation, dict) or set(implementation) != set(IMPLEMENTATION_PATHS):
            errors.append("implementation inventory mismatch")
            implementation = {}
        for relative in IMPLEMENTATION_PATHS:
            _expect(errors, implementation.get(relative), _sha256(root / relative), f"implementation hash mismatch: {relative}")
        _expect(errors, _sha256(root / "rom/base.gba"), ROM_SHA256, "base ROM mismatch")
        _expect(errors, _sha256(root / ABI_PATH), ABI_SHA256, "ABI artifact mismatch")
        _expect(errors, _sha256(root / OWNERSHIP_PATH), OWNERSHIP_SHA256, "ownership artifact mismatch")

        patch = [{"address": "0x020240BC", "before": 0, "after": 1}]
        unlock_audit = _read_json(artifact_dir / "entry/unlock-audit.json")
        state3_audit = _read_json(artifact_dir / "entry/state3-audit.json")
        _expect(errors, (artifact_dir / "entry/unlock-audit.json").read_bytes(), (artifact_dir / "entry/unlock-done.marker").read_bytes(), "unlock done marker mismatch")
        _expect(errors, (artifact_dir / "entry/state3-audit.json").read_bytes(), (artifact_dir / "entry/state3-done.marker").read_bytes(), "state3 done marker mismatch")
        _expect(errors, _sha256(artifact_dir / "entry/unlock-parent.ss9"), UNLOCK_PARENT_SHA256, "unlock parent checkpoint mismatch")
        _expect(errors, _sha256(artifact_dir / "entry/choice-screen-entry.ss9"), CHOICE_ENTRY_SHA256, "choice entry checkpoint mismatch")
        _expect(errors, _sha256(artifact_dir / "entry/choice-state3.ss9"), STATE3_SHA256, "state3 checkpoint mismatch")
        if (
            unlock_audit.get("schema") != "mgba-wram-tilemap-sequence-probe-v1"
            or unlock_audit.get("run_id") != "choice-completion-unlock-default-20260731-v2"
            or unlock_audit.get("input_state_sha256") != UNLOCK_PARENT_SHA256
            or unlock_audit.get("memory_patches") != patch
            or unlock_audit.get("rom_sha256") != ROM_SHA256
            or unlock_audit.get("binary_sha256") != EMULATOR_SHA256
            or unlock_audit.get("hit_counts", {}).get("choice_screen_entry") != 1
            or not _guard_ok(_read_json(artifact_dir / "entry/unlock-guard.json"))
        ):
            errors.append("controlled unlock runtime mismatch")
        if (
            state3_audit.get("schema") != "mgba-wram-tilemap-sequence-probe-v2"
            or state3_audit.get("run_id") != "choice-state3-checkpoint-20260801"
            or state3_audit.get("input_state_sha256") != CHOICE_ENTRY_SHA256
            or state3_audit.get("input_provenance") != "controlled"
            or state3_audit.get("evidence_mode") != "controlled"
            or state3_audit.get("memory_patches") != []
            or state3_audit.get("hit_counts", {}).get("choice_state_3", 0) < 1
            or not _guard_ok(_read_json(artifact_dir / "entry/state3-guard.json"))
        ):
            errors.append("state3 runtime mismatch")
        entry = {
            "evidence_mode": "controlled",
            "controlled_memory_patches": patch,
            "unlock_parent_checkpoint_sha256": UNLOCK_PARENT_SHA256,
            "choice_screen_entry_sha256": CHOICE_ENTRY_SHA256,
            "choice_state3_checkpoint_sha256": STATE3_SHA256,
            "chain": ["entry/unlock-parent.ss9", "entry/choice-screen-entry.ss9", "entry/choice-state3.ss9"],
        }
        _expect(errors, payload.get("entry_provenance"), entry, "entry provenance mismatch")

        audits: dict[str, dict[str, Any]] = {}
        for run, spec in RUN_SPECS.items():
            audit_path = artifact_dir / f"runs/{run}/audit.json"
            audit = _read_json(audit_path)
            guard = _read_json(artifact_dir / f"runs/{run}/guard.json")
            audits[run] = audit
            _expect(errors, audit_path.read_bytes(), (artifact_dir / f"runs/{run}/done.marker").read_bytes(), f"{run} done marker mismatch")
            closed = [row.get("source_pointer") for row in audit.get("source_results", []) if row.get("closed")]
            if (
                audit.get("schema") != "mgba-wram-tilemap-sequence-probe-v2"
                or audit.get("run_id") != spec["run_id"]
                or audit.get("outcome") != "incomplete"
                or audit.get("input_state_sha256") != STATE3_SHA256
                or audit.get("input_provenance") != "controlled"
                or audit.get("evidence_mode") != "controlled"
                or audit.get("memory_patches") != []
                or audit.get("rom_sha256") != ROM_SHA256
                or audit.get("binary_sha256") != EMULATOR_SHA256
                or audit.get("capture_frames") != spec["capture_frames"]
                or audit.get("inputs") != spec["inputs"]
                or closed != spec["sources"]
                or audit.get("closed_source_count") != len(spec["sources"])
                or not _guard_ok(guard)
            ):
                errors.append(f"{run} runtime mismatch")
            run_payload = {
                "run_id": spec["run_id"], "inputs": spec["inputs"],
                "capture_frames": spec["capture_frames"], "evidence_mode": "controlled",
                "closed_sources": spec["sources"], "audit_sha256": _sha256(audit_path),
                "guard_sha256": _sha256(artifact_dir / f"runs/{run}/guard.json"),
                "peak_tree_rss_mib": guard.get("peak_tree_rss_mib"),
            }
            _expect(errors, payload.get("runs", {}).get(run), run_payload, f"{run} payload mismatch")
            if not (artifact_dir / f"runs/{run}/final.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                errors.append(f"{run} final screenshot is not PNG")

        rom = (root / "rom/base.gba").read_bytes()
        abi = _read_json(root / ABI_PATH)
        ownership = _read_json(root / OWNERSHIP_PATH)
        payload_rows = payload.get("source_closures", [])
        by_source = {row.get("source_pointer"): row for row in payload_rows if isinstance(row, dict)}
        if set(by_source) != set(SOURCE_SPECS) or len(payload_rows) != 3:
            errors.append("source closure inventory mismatch")
        computed: dict[str, dict[str, Any]] = {}
        for pointer, spec in SOURCE_SPECS.items():
            run, phase, load_target, load_address, post_target, post_address, submit_target, submit_address = spec
            audit = audits[run]
            result = next((row for row in audit.get("source_results", []) if row.get("source_pointer") == pointer), {})
            correlation = next((row for row in audit.get("correlated_queue_hits", []) if row.get("source_pointer") == pointer), {})
            load = _event(audit, load_target)
            load_post = _event(audit, post_target)
            submit = _event(audit, submit_target, correlation.get("submit_frame"))
            row = by_source.get(pointer, {})
            _expect(errors, row.get("queue_correlation"), correlation, f"queue correlation mismatch: {pointer}")
            cycles = []
            for key in ("load_cycle", "load_post_cycle", "submit_cycle", "queue_pre_cycle", "queue_post_cycle"):
                try:
                    cycles.append(int(correlation[key]))
                except (KeyError, TypeError, ValueError):
                    errors.append(f"invalid transaction cycle: {pointer}/{key}")
            if len(cycles) != 5 or cycles != sorted(cycles) or len(set(cycles)) != 5:
                errors.append(f"transaction cycle order mismatch: {pointer}")
            if (
                str(correlation.get("load_cycle")) != str(load.get("cycle"))
                or str(correlation.get("load_post_cycle")) != str(load_post.get("cycle"))
                or str(correlation.get("submit_cycle")) != str(submit.get("cycle"))
            ):
                errors.append(f"audit event cycle mismatch: {pointer}")
            if not _queue_events_match(correlation, audit.get("events", [])):
                errors.append(f"same consumer sweep mismatch: {pointer}")
            if (
                result.get("closed") is not True or result.get("load_post_hits") != 1
                or result.get("missing_stages") != []
                or load.get("address") != load_address or load.get("r0") != pointer
                or load.get("r1") != f"0x{STAGING:08X}"
                or load_post.get("address") != post_address
                or submit.get("address") != submit_address
                or submit.get("r0") != f"0x{OUTPUT:08X}"
                or submit.get("r1") != f"0x{DESTINATION:08X}"
                or submit.get("r2") != "0x0000000C" or submit.get("r3") != "0x0000000C"
            ):
                errors.append(f"load/submit transaction mismatch: {pointer}")
            source_dir = artifact_dir / "sources" / pointer[2:]
            file_hashes = {hash_key: _sha256(source_dir / name) for name, hash_key in SOURCE_FILES.items()}
            _expect(errors, row.get("files"), file_hashes, f"source file hashes mismatch: {pointer}")
            decoded = _decode_lz77(rom, int(pointer, 16) - 0x08000000)
            staging = (source_dir / "staging.bin").read_bytes()
            if staging != decoded or len(staging) != ROW_BYTES * ROWS:
                errors.append(f"staging does not match ROM source: {pointer}")
            qpre = (source_dir / "queue-pre.bin").read_bytes()
            qpost = (source_dir / "queue-post.bin").read_bytes()
            slot = correlation.get("slot_index", -1)
            if _slot(qpre, slot) != (3, OUTPUT, DESTINATION, 12, 12):
                errors.append(f"queue pre slot mismatch: {pointer}")
            if _slot(qpost, slot) != (2, OUTPUT, DESTINATION, 12, 12):
                errors.append(f"queue post slot mismatch: {pointer}")
            if _overlapping_status3_slots(qpre, slot):
                errors.append(f"overlapping status-3 queue slot: {pointer}")
            pre_vram = (source_dir / "pre-vram.bin").read_bytes()
            post_vram = (source_dir / "post-vram.bin").read_bytes()
            if len(pre_vram) != VRAM_BYTES or len(post_vram) != VRAM_BYTES:
                errors.append(f"VRAM capture size mismatch: {pointer}")
            output_rows = (source_dir / "output-rows.bin").read_bytes()
            pre_rows = (source_dir / "pre-vram-rows.bin").read_bytes()
            post_rows = (source_dir / "post-vram-rows.bin").read_bytes()
            load_state = _ss9_state(source_dir / "load.ss9")
            load_post_state = _ss9_state(source_dir / "load-post.ss9")
            queue_pre_state = _ss9_state(source_dir / "queue-pre.ss9")
            queue_post_state = _ss9_state(source_dir / "queue-post.ss9")
            runtime_transform = _runtime_transform(
                _state_memory(load_post_state, OUTPUT, ROW_BYTES * ROWS),
                staging,
                output_rows,
            )
            if pre_rows != _rows(pre_vram) or post_rows != _rows(post_vram):
                errors.append(f"strided VRAM row capture mismatch: {pointer}")
            if pre_rows == output_rows:
                errors.append(f"pre VRAM already matches transformed output: {pointer}")
            if post_rows != output_rows:
                errors.append(f"post VRAM rows do not match transformed output: {pointer}")
            if (
                _state_pc(load_state) != int(load_address, 16) + 2
                or _state_pc(load_post_state) != int(post_address, 16) + 2
                or _state_memory(load_post_state, STAGING, ROW_BYTES * ROWS) != staging
                or _state_pc(queue_pre_state) != 0x0806365E
                or _state_pc(queue_post_state) != 0x080636D0
                or _state_memory(queue_pre_state, QUEUE_BASE, 256) != qpre
                or _state_memory(queue_post_state, QUEUE_BASE, 256) != qpost
                or _state_memory(queue_pre_state, 0x06000000, VRAM_BYTES) != pre_vram
                or _state_memory(queue_post_state, 0x06000000, VRAM_BYTES) != post_vram
            ):
                errors.append(f"savestate capture mismatch: {pointer}")
            abi_row = next(row for row in abi.get("tilemap_sources", []) if row.get("source_pointer") == pointer)
            owner = next(row for row in ownership.get("ownership_records", []) if row.get("tilemap_source_pointer") == pointer)
            if (
                abi_row.get("classification") != "transformed_strided_queue_tilemap"
                or abi_row.get("phase") != phase
                or abi_row.get("decompressed_sha256") != hashlib.sha256(decoded).hexdigest()
                or abi_row.get("vram_destination") != f"0x{DESTINATION:08X}"
                or owner.get("graphics", {}).get("source_pointer") != "0x08463688"
                or owner.get("bg", {}).get("name") != "BG1"
            ):
                errors.append(f"upstream ABI/ownership mismatch: {pointer}")
            expected_row = {
                "source_pointer": pointer, "run": run, "phase": phase,
                "load_event": _event_record(load), "load_post_event": _event_record(load_post),
                "submit_event": _event_record(submit), "queue_correlation": correlation,
                "transaction_cycle_order_strict": True,
                "staging_equals_rom_decompressed_source": True,
                "pre_vram_rows_equal_output": False,
                "post_vram_rows_equal_output": True,
                "runtime_transform": runtime_transform,
                "changed_byte_count": sum(a != b for a, b in zip(pre_rows, output_rows)),
                "files": file_hashes,
            }
            computed[pointer] = expected_row
            _expect(errors, row, expected_row, f"source closure mismatch: {pointer}")
            for name in ("load.ss9", "load-post.ss9", "queue-pre.ss9", "queue-post.ss9"):
                if (source_dir / name).stat().st_size < 1024:
                    errors.append(f"savestate too small: {pointer}/{name}")
            for name in ("queue-pre.png", "queue-post.png"):
                if not (source_dir / name).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                    errors.append(f"invalid PNG: {pointer}/{name}")

        if set(computed) == set(SOURCE_SPECS):
            if int(computed["0x0846356C"]["queue_correlation"]["queue_post_cycle"]) >= int(computed["0x084635D8"]["queue_correlation"]["load_cycle"]):
                errors.append("phase B transactions overlap")
        summary = {
            "transformed_tilemap_denominator": 3,
            "controlled_runtime_verified_count": 3,
            "remaining_runtime_count": 0,
            "verified_source_pointers": list(SOURCE_SPECS),
        }
        scope = {
            "natural_entry_reachability_verified": False,
            "controlled_entry_base_rom_runtime_verified": True,
            "all_three_transformed_sources_runtime_verified": True,
            "staging_source_identity_verified": True,
            "queue_status_3_to_2_verified": True,
            "strided_post_vram_equals_transformed_output_verified": True,
            "modified_rom_pixel_equivalence_verified": False,
            "final_screen_timing_equivalence_verified": False,
        }
        _expect(errors, payload.get("summary"), summary, "summary mismatch")
        _expect(errors, payload.get("scope"), scope, "scope mismatch")
        _expect(errors, manifest.get("scope"), scope, "manifest scope mismatch")
        _expect(errors, payload.get("rom"), {"path": "rom/base.gba", "sha256": ROM_SHA256}, "ROM payload mismatch")
        _expect(errors, payload.get("emulator"), {"source_commit": EMULATOR_COMMIT, "binary_sha256": EMULATOR_SHA256}, "emulator payload mismatch")
        _expect(errors, payload.get("source_artifacts"), {
            "abi": {"path": ABI_PATH, "sha256": ABI_SHA256},
            "ownership": {"path": OWNERSHIP_PATH, "sha256": OWNERSHIP_SHA256},
        }, "source artifact payload mismatch")
        _expect(errors, manifest.get("verifier"), {
            "command": ["python3", "tools/verify_residual_wram_transformed_tilemap_runtime_evidence.py", "--root", ".", "--artifact", "artifacts/residual-wram-transformed-tilemap-runtime-v1"],
            "exit_code": 0,
        }, "manifest verifier declaration mismatch")
    except (KeyError, OSError, ValueError, json.JSONDecodeError, StopIteration, struct.error) as error:
        errors.append(str(error))
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    return {
        "schema": "residual-wram-transformed-tilemap-runtime-verification-v1",
        "verified": not errors,
        "controlled_runtime_verified_count": summary.get("controlled_runtime_verified_count", 0),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact", type=Path, default=Path("artifacts/residual-wram-transformed-tilemap-runtime-v1"))
    args = parser.parse_args()
    root = args.root.resolve()
    artifact = args.artifact if args.artifact.is_absolute() else root / args.artifact
    report = verify_artifact(root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
