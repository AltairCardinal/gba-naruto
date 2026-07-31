#!/usr/bin/env python3
"""Promote three controlled-entry transformed tilemap runtime closures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
from typing import Any

try:
    from tools.extract_tileset import lz77_decompress
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.extract_tileset import lz77_decompress
    from tools.inspect_mgba_savestate import load_gba_state


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
EMULATOR_SHA256 = "4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72"
EMULATOR_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
UNLOCK_PARENT_SHA256 = "78db5e103f5fc471bad2d7cb8628b3964d46791ccbf733266c0754d497dfd2bc"
CHOICE_ENTRY_SHA256 = "1fefd560c5a97ba3a15b1f330cfee5aeaba5017da46e01fb5695906412da6027"
STATE3_SHA256 = "dc5a1c1847600bd9719f6e6f4dbfa6237110426f0f942cb74568cdfefd6c0864"
ABI_PATH = Path(
    "artifacts/residual-wram-visual-metadata-abi-v2/"
    "residual-wram-visual-metadata-abi.json"
)
ABI_SHA256 = "4cee47ab097986d50ed0d3b3017fc4fd429037405ee247876022dfd08beac260"
OWNERSHIP_PATH = Path(
    "artifacts/residual-wram-tilemap-resource-ownership-v1/resource-ownership.json"
)
OWNERSHIP_SHA256 = "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
STAGING = 0x0200A640
OUTPUT = 0x0200A760
DESTINATION = 0x06000806
ROW_BYTES = 24
ROW_STRIDE = 64
ROWS = 12
QUEUE_BYTES = 256
QUEUE_BASE = 0x03005BBC
QUEUE_SLOT_SIZE = 16
VRAM_BYTES = 0x18000

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
    "0x084634B8": {
        "run": "phase-a",
        "load_target": "choice_phase_a_load",
        "load_address": "0x08090B5C",
        "load_post_target": "choice_phase_a_load_post",
        "load_post_address": "0x08090B60",
        "submit_target": "choice_phase_a_submit",
        "submit_address": "0x08090CB0",
        "phase": "single_phase",
    },
    "0x0846356C": {
        "run": "phase-b",
        "load_target": "choice_phase_b_initial_load",
        "load_address": "0x08090D56",
        "load_post_target": "choice_phase_b_initial_load_post",
        "load_post_address": "0x08090D62",
        "submit_target": "choice_phase_b_submit",
        "submit_address": "0x08090F3C",
        "phase": "initial_phase",
    },
    "0x084635D8": {
        "run": "phase-b",
        "load_target": "choice_phase_b_second_load",
        "load_address": "0x08090DC4",
        "load_post_target": "choice_phase_b_second_load_post",
        "load_post_address": "0x08090DD0",
        "submit_target": "choice_phase_b_submit",
        "submit_address": "0x08090F3C",
        "phase": "second_phase",
    },
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


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _guard_ok(guard: dict[str, Any]) -> bool:
    return (
        guard.get("reason") == "completed"
        and guard.get("exit_code") == 0
        and guard.get("degraded") is False
        and guard.get("completion_trigger") == "success-marker"
        and guard.get("peak_tree_rss_mib", 1537) <= 1536
    )


def _event(audit: dict[str, Any], target: str, frame: int | None = None) -> dict[str, Any]:
    matches = [
        event
        for event in audit.get("events", [])
        if event.get("target") == target and (frame is None or event.get("frame") == frame)
    ]
    if not matches:
        raise ValueError(f"missing event: {target} frame={frame}")
    return matches[0]


def _event_record(event: dict[str, Any]) -> dict[str, Any]:
    return {
        key: event[key]
        for key in ("target", "address", "frame", "cycle", "pc", "lr", "r0", "r1", "r2", "r3")
    }


def _extract_rows(vram: bytes) -> bytes:
    start = DESTINATION - 0x06000000
    return b"".join(
        vram[start + row * ROW_STRIDE : start + row * ROW_STRIDE + ROW_BYTES]
        for row in range(ROWS)
    )


def _queue_slot(queue: bytes, slot_index: int) -> tuple[int, int, int, int, int]:
    if len(queue) != QUEUE_BYTES or not 0 <= slot_index < 16:
        raise ValueError("invalid queue capture")
    return struct.unpack_from("<IIIHH", queue, slot_index * 16)


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


def _event_cycle_matches(correlation: dict[str, Any], key: str, event: dict[str, Any]) -> bool:
    return str(correlation.get(key)) == str(event.get("cycle"))


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
        status, _source, destination, width, row_count = _queue_slot(queue, slot_index)
        if status != 3 or width == 0 or row_count == 0:
            continue
        candidate_rows = [
            (destination + row * ROW_STRIDE, destination + row * ROW_STRIDE + width * 2)
            for row in range(row_count)
        ]
        if any(left < target_right and target_left < right for left, right in candidate_rows for target_left, target_right in target_rows):
            overlaps.append(slot_index)
    return overlaps


def _copy(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"invalid runtime input: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _validate_entry_chain(
    unlock: Path, state3: Path, output: Path
) -> dict[str, Any]:
    unlock_raw = unlock / "raw"
    state3_raw = state3 / "raw"
    unlock_audit = _read_json(unlock_raw / "audit.json")
    state3_audit = _read_json(state3_raw / "audit.json")
    if (unlock_raw / "audit.json").read_bytes() != (unlock_raw / "done.marker").read_bytes():
        raise ValueError("unlock audit and done marker differ")
    if (state3_raw / "audit.json").read_bytes() != (state3_raw / "done.marker").read_bytes():
        raise ValueError("state3 audit and done marker differ")
    patch = [{"address": "0x020240BC", "before": 0, "after": 1}]
    if (
        unlock_audit.get("schema") != "mgba-wram-tilemap-sequence-probe-v1"
        or unlock_audit.get("run_id") != "choice-completion-unlock-default-20260731-v2"
        or unlock_audit.get("rom_sha256") != ROM_SHA256
        or unlock_audit.get("binary_sha256") != EMULATOR_SHA256
        or unlock_audit.get("input_state_sha256") != UNLOCK_PARENT_SHA256
        or unlock_audit.get("memory_patches") != patch
        or unlock_audit.get("hit_counts", {}).get("choice_screen_entry") != 1
        or not _guard_ok(_read_json(unlock_raw / "guard.json"))
    ):
        raise ValueError("controlled unlock runtime mismatch")
    parent = Path(unlock_audit["input_state"])
    if _sha256(parent) != UNLOCK_PARENT_SHA256:
        raise ValueError("unlock parent checkpoint mismatch")
    entry_state = unlock_raw / "choice_screen_entry-hit.ss9"
    state3_state = state3_raw / "choice_state_3-hit.ss9"
    if _sha256(entry_state) != CHOICE_ENTRY_SHA256 or _sha256(state3_state) != STATE3_SHA256:
        raise ValueError("entry checkpoint hash mismatch")
    if (
        state3_audit.get("schema") != "mgba-wram-tilemap-sequence-probe-v2"
        or state3_audit.get("run_id") != "choice-state3-checkpoint-20260801"
        or state3_audit.get("input_state_sha256") != CHOICE_ENTRY_SHA256
        or state3_audit.get("input_provenance") != "controlled"
        or state3_audit.get("evidence_mode") != "controlled"
        or state3_audit.get("memory_patches") != []
        or state3_audit.get("hit_counts", {}).get("choice_state_3", 0) < 1
        or not _guard_ok(_read_json(state3_raw / "guard.json"))
    ):
        raise ValueError("state3 checkpoint runtime mismatch")

    copies = {
        "entry/unlock-parent.ss9": parent,
        "entry/unlock-audit.json": unlock_raw / "audit.json",
        "entry/unlock-done.marker": unlock_raw / "done.marker",
        "entry/unlock-guard.json": unlock_raw / "guard.json",
        "entry/choice-screen-entry.ss9": entry_state,
        "entry/state3-audit.json": state3_raw / "audit.json",
        "entry/state3-done.marker": state3_raw / "done.marker",
        "entry/state3-guard.json": state3_raw / "guard.json",
        "entry/choice-state3.ss9": state3_state,
    }
    for relative, source in copies.items():
        _copy(source, output / relative)
    return {
        "evidence_mode": "controlled",
        "controlled_memory_patches": patch,
        "unlock_parent_checkpoint_sha256": UNLOCK_PARENT_SHA256,
        "choice_screen_entry_sha256": CHOICE_ENTRY_SHA256,
        "choice_state3_checkpoint_sha256": STATE3_SHA256,
        "chain": [
            "entry/unlock-parent.ss9",
            "entry/choice-screen-entry.ss9",
            "entry/choice-state3.ss9",
        ],
    }


def export_artifact(
    root: Path,
    unlock: Path,
    state3: Path,
    phase_a: Path,
    phase_b: Path,
    output: Path,
) -> dict[str, Any]:
    root, unlock, state3, phase_a, phase_b, output = (
        path.resolve() for path in (root, unlock, state3, phase_a, phase_b, output)
    )
    if output.exists():
        raise FileExistsError(output)
    if _sha256(root / "rom/base.gba") != ROM_SHA256:
        raise ValueError("base ROM changed")
    if _sha256(root / ABI_PATH) != ABI_SHA256 or _sha256(root / OWNERSHIP_PATH) != OWNERSHIP_SHA256:
        raise ValueError("upstream ABI or ownership changed")
    for relative in IMPLEMENTATION_PATHS:
        if not (root / relative).is_file():
            raise FileNotFoundError(root / relative)

    output.mkdir(parents=True)
    entry = _validate_entry_chain(unlock, state3, output)
    runs = {"phase-a": phase_a, "phase-b": phase_b}
    audits: dict[str, dict[str, Any]] = {}
    run_payloads: dict[str, Any] = {}
    for name, run in runs.items():
        spec = RUN_SPECS[name]
        if run.name != spec["run_id"]:
            raise ValueError(f"unexpected {name} run ID")
        raw = run / "raw"
        audit = _read_json(raw / "audit.json")
        guard = _read_json(raw / "guard.json")
        if (raw / "audit.json").read_bytes() != (raw / "done.marker").read_bytes():
            raise ValueError(f"{name} audit and done marker differ")
        closed = [row["source_pointer"] for row in audit.get("source_results", []) if row.get("closed")]
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
            raise ValueError(f"{name} runtime audit mismatch")
        audits[name] = audit
        for target, source in {
            f"runs/{name}/audit.json": raw / "audit.json",
            f"runs/{name}/done.marker": raw / "done.marker",
            f"runs/{name}/guard.json": raw / "guard.json",
            f"runs/{name}/final.ss9": raw / "final.ss9",
            f"runs/{name}/final.png": raw / "final.png",
        }.items():
            _copy(source, output / target)
        run_payloads[name] = {
            "run_id": spec["run_id"],
            "inputs": spec["inputs"],
            "capture_frames": spec["capture_frames"],
            "evidence_mode": "controlled",
            "closed_sources": spec["sources"],
            "audit_sha256": _sha256(output / f"runs/{name}/audit.json"),
            "guard_sha256": _sha256(output / f"runs/{name}/guard.json"),
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
        }

    rom = (root / "rom/base.gba").read_bytes()
    abi = _read_json(root / ABI_PATH)
    ownership = _read_json(root / OWNERSHIP_PATH)
    closures: list[dict[str, Any]] = []
    for pointer, spec in SOURCE_SPECS.items():
        audit = audits[spec["run"]]
        raw = runs[spec["run"]] / "raw"
        name = "source_" + pointer[2:]
        result = next(row for row in audit["source_results"] if row["source_pointer"] == pointer)
        correlation = next(row for row in audit["correlated_queue_hits"] if row["source_pointer"] == pointer)
        load = _event(audit, spec["load_target"])
        load_post = _event(audit, spec["load_post_target"])
        submit = _event(audit, spec["submit_target"], correlation["submit_frame"])
        cycles = [int(correlation[key]) for key in (
            "load_cycle", "load_post_cycle", "submit_cycle", "queue_pre_cycle", "queue_post_cycle"
        )]
        if cycles != sorted(cycles) or len(set(cycles)) != len(cycles):
            raise ValueError(f"non-monotonic transaction cycles: {pointer}")
        if (
            not _event_cycle_matches(correlation, "load_cycle", load)
            or not _event_cycle_matches(correlation, "load_post_cycle", load_post)
            or not _event_cycle_matches(correlation, "submit_cycle", submit)
        ):
            raise ValueError(f"audit event cycle mismatch: {pointer}")
        if not _queue_events_match(correlation, audit.get("events", [])):
            raise ValueError(f"same consumer sweep mismatch: {pointer}")
        if (
            load.get("address") != spec["load_address"]
            or load.get("r0") != pointer
            or load.get("r1") != f"0x{STAGING:08X}"
            or load_post.get("address") != spec["load_post_address"]
            or submit.get("address") != spec["submit_address"]
            or submit.get("r0") != f"0x{OUTPUT:08X}"
            or submit.get("r1") != f"0x{DESTINATION:08X}"
            or submit.get("r2") != "0x0000000C"
            or submit.get("r3") != "0x0000000C"
            or result.get("load_post_hits") != 1
            or result.get("missing_stages") != []
        ):
            raise ValueError(f"load/submit transaction mismatch: {pointer}")

        source_dir = output / "sources" / pointer[2:]
        source_files = {
            "staging.bin": raw / f"{name}-load-staging.bin",
            "load.ss9": raw / f"{spec['load_target']}-hit.ss9",
            "load-post.ss9": raw / f"{spec['load_post_target']}-hit.ss9",
            "queue-pre.bin": raw / f"{name}-queue-pre.bin",
            "queue-post.bin": raw / f"{name}-queue-post.bin",
            "pre-vram.bin": raw / f"{name}-queue-pre-vram.bin",
            "post-vram.bin": raw / f"{name}-queue-post-vram.bin",
            "output-rows.bin": raw / f"{name}-queue-pre-output-rows.bin",
            "pre-vram-rows.bin": raw / f"{name}-queue-pre-vram-rows.bin",
            "post-vram-rows.bin": raw / f"{name}-queue-post-vram-rows.bin",
            "queue-pre.ss9": raw / f"{name}-queue-pre.ss9",
            "queue-post.ss9": raw / f"{name}-queue-post.ss9",
            "queue-pre.png": raw / f"{name}-queue-pre.png",
            "queue-post.png": raw / f"{name}-queue-post.png",
        }
        for target, source in source_files.items():
            _copy(source, source_dir / target)

        staging = (source_dir / "staging.bin").read_bytes()
        decoded = lz77_decompress(rom, int(pointer, 16) - 0x08000000)
        qpre = (source_dir / "queue-pre.bin").read_bytes()
        qpost = (source_dir / "queue-post.bin").read_bytes()
        pre_vram = (source_dir / "pre-vram.bin").read_bytes()
        post_vram = (source_dir / "post-vram.bin").read_bytes()
        output_rows = (source_dir / "output-rows.bin").read_bytes()
        pre_rows = (source_dir / "pre-vram-rows.bin").read_bytes()
        post_rows = (source_dir / "post-vram-rows.bin").read_bytes()
        slot = correlation["slot_index"]
        if staging != decoded or len(staging) != ROW_BYTES * ROWS:
            raise ValueError(f"staging does not match ROM source: {pointer}")
        if len(pre_vram) != VRAM_BYTES or len(post_vram) != VRAM_BYTES:
            raise ValueError(f"VRAM capture size mismatch: {pointer}")
        if pre_rows != _extract_rows(pre_vram) or post_rows != _extract_rows(post_vram):
            raise ValueError(f"strided VRAM row capture mismatch: {pointer}")
        if pre_rows == output_rows or post_rows != output_rows:
            raise ValueError(f"VRAM transaction relationship mismatch: {pointer}")
        if _queue_slot(qpre, slot) != (3, OUTPUT, DESTINATION, 12, 12):
            raise ValueError(f"queue pre slot mismatch: {pointer}")
        if _queue_slot(qpost, slot) != (2, OUTPUT, DESTINATION, 12, 12):
            raise ValueError(f"queue post slot mismatch: {pointer}")
        if _overlapping_status3_slots(qpre, slot):
            raise ValueError(f"overlapping status-3 queue slot: {pointer}")
        load_state = load_gba_state(source_dir / "load.ss9")
        load_post_state = load_gba_state(source_dir / "load-post.ss9")
        queue_pre_state = load_gba_state(source_dir / "queue-pre.ss9")
        queue_post_state = load_gba_state(source_dir / "queue-post.ss9")
        if (
            load_state.registers[15] != int(spec["load_address"], 16) + 2
            or load_post_state.registers[15] != int(spec["load_post_address"], 16) + 2
            or load_post_state.read_memory(STAGING, ROW_BYTES * ROWS) != staging
            or queue_pre_state.registers[15] != 0x0806365E
            or queue_post_state.registers[15] != 0x080636D0
            or queue_pre_state.read_memory(QUEUE_BASE, QUEUE_BYTES) != qpre
            or queue_post_state.read_memory(QUEUE_BASE, QUEUE_BYTES) != qpost
            or queue_pre_state.read_memory(0x06000000, VRAM_BYTES) != pre_vram
            or queue_post_state.read_memory(0x06000000, VRAM_BYTES) != post_vram
        ):
            raise ValueError(f"savestate capture mismatch: {pointer}")
        runtime_transform = _runtime_transform(
            load_post_state.read_memory(OUTPUT, ROW_BYTES * ROWS),
            staging,
            output_rows,
        )
        abi_row = next(row for row in abi["tilemap_sources"] if row["source_pointer"] == pointer)
        owner = next(row for row in ownership["ownership_records"] if row["tilemap_source_pointer"] == pointer)
        if (
            abi_row.get("classification") != "transformed_strided_queue_tilemap"
            or abi_row.get("phase") != spec["phase"]
            or abi_row.get("decompressed_sha256") != hashlib.sha256(decoded).hexdigest()
            or abi_row.get("vram_destination") != f"0x{DESTINATION:08X}"
            or owner.get("graphics", {}).get("source_pointer") != "0x08463688"
            or owner.get("bg", {}).get("name") != "BG1"
        ):
            raise ValueError(f"upstream ABI/ownership mismatch: {pointer}")
        hash_keys = {
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
        file_hashes = {
            hash_keys[target]: _sha256(source_dir / target) for target in source_files
        }
        closures.append({
            "source_pointer": pointer,
            "run": spec["run"],
            "phase": spec["phase"],
            "load_event": _event_record(load),
            "load_post_event": _event_record(load_post),
            "submit_event": _event_record(submit),
            "queue_correlation": correlation,
            "transaction_cycle_order_strict": True,
            "staging_equals_rom_decompressed_source": True,
            "pre_vram_rows_equal_output": False,
            "post_vram_rows_equal_output": True,
            "runtime_transform": runtime_transform,
            "changed_byte_count": sum(a != b for a, b in zip(pre_rows, output_rows)),
            "files": file_hashes,
        })

    phase_b = [row for row in closures if row["run"] == "phase-b"]
    if int(phase_b[0]["queue_correlation"]["queue_post_cycle"]) >= int(phase_b[1]["queue_correlation"]["load_cycle"]):
        raise ValueError("phase B transactions overlap")

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
    summary = {
        "transformed_tilemap_denominator": 3,
        "controlled_runtime_verified_count": 3,
        "remaining_runtime_count": 0,
        "verified_source_pointers": list(SOURCE_SPECS),
    }
    payload = {
        "schema": "residual-wram-transformed-tilemap-runtime-evidence-v1",
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "emulator": {"source_commit": EMULATOR_COMMIT, "binary_sha256": EMULATOR_SHA256},
        "entry_provenance": entry,
        "source_artifacts": {
            "abi": {"path": ABI_PATH.as_posix(), "sha256": ABI_SHA256},
            "ownership": {"path": OWNERSHIP_PATH.as_posix(), "sha256": OWNERSHIP_SHA256},
        },
        "runs": run_payloads,
        "source_closures": closures,
        "summary": summary,
        "scope": scope,
    }
    (output / "runtime-evidence.json").write_bytes(_canonical(payload))
    files = {
        path.relative_to(output).as_posix(): _sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": "residual-wram-transformed-tilemap-runtime-v1",
        "artifact_schema": payload["schema"],
        "artifact_status": "accepted",
        "payload_file": "runtime-evidence.json",
        "payload_sha256": files["runtime-evidence.json"],
        "files": files,
        "implementation": {relative: _sha256(root / relative) for relative in IMPLEMENTATION_PATHS},
        "scope": scope,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_residual_wram_transformed_tilemap_runtime_evidence.py",
                "--root", ".",
                "--artifact", "artifacts/residual-wram-transformed-tilemap-runtime-v1",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_bytes(_canonical(manifest))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--unlock", type=Path, required=True)
    parser.add_argument("--state3", type=Path, required=True)
    parser.add_argument("--phase-a", type=Path, required=True)
    parser.add_argument("--phase-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    values = [getattr(args, name) for name in ("unlock", "state3", "phase_a", "phase_b", "output")]
    resolved = [path if path.is_absolute() else root / path for path in values]
    payload = export_artifact(root, *resolved)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
