#!/usr/bin/env python3
"""Export the natural scene-panel closure for all direct WRAM tilemap queues."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
from typing import Any

try:
    from tools.extract_tileset import lz77_decompress
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.extract_tileset import lz77_decompress


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
EMULATOR_SHA256 = "4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72"
EMULATOR_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
PARENT_DIR = Path("artifacts/residual-wram-tilemap-runtime-v1")
PARENT_MANIFEST_SHA256 = "1cde045d1fb0e06028760371514cfe2ac47e1623e1d9605a00489e763a460f5f"
PARENT_EVIDENCE_SHA256 = "cf2ccff3159ac28a4300f94fcf40498c805de8351ba0b180a840648025470e62"
PARENT_STATE_SHA256 = "fbfd4b5aa0ceda8e239ae0d965c05429e1edc64e9bd7dfba9567f968460348ff"
ABI_PATH = Path("artifacts/residual-wram-tilemap-abi-v1/residual-wram-tilemap-abi.json")
ABI_SHA256 = "07e1f89b5aaff938184d5d31bea4174e995f96d10b8ffbee56bff0f609a27dfc"
OWNERSHIP_PATH = Path("artifacts/residual-wram-tilemap-resource-ownership-v1/resource-ownership.json")
OWNERSHIP_SHA256 = "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
BRIDGE_RUN_ID = "scene-panel-v1-parent-b-bridge-20260731"
ZERO_RUN_ID = "scene-panel-v1-parent-direct-sources-zero5-20260731"
SETUP_STATE_SHA256 = "6fed9fe8db43646a5a5a53901a5f0edf1c743ba5e682fd842d3fd19b12776000"
QUEUE_CONSUMER = 0x0806365C
VRAM_BASE = 0x06000000
VRAM_STRIDE = 64
SOURCES = (
    {
        "source_pointer": 0x083F1C98,
        "load_target": 0x0808BBD8,
        "load_name": "scene_panel_upper_load",
        "wram_source": 0x02002B78,
        "vram_destination": 0x0600F810,
        "width": 24,
        "height": 12,
        "slot": 0,
    },
    {
        "source_pointer": 0x085B67E0,
        "load_target": 0x0808BBFC,
        "load_name": "scene_panel_lower_load",
        "wram_source": 0x02002DB8,
        "vram_destination": 0x0600FC4E,
        "width": 23,
        "height": 3,
        "slot": 1,
    },
)
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
COPIES = {
    "bridge-audit.json": ("bridge", "audit.json"),
    "bridge-done.json": ("bridge", "done.json"),
    "bridge-guard.json": ("bridge", "guard.json"),
    "scene-panel-setup.ss9": ("bridge", "scene_panel_setup-hit.ss9"),
    "zero-audit.json": ("zero", "audit.json"),
    "zero-done.json": ("zero", "done.json"),
    "zero-guard.json": ("zero", "guard.json"),
    "queue-at-consumer.bin": ("zero", "queue_consumer-queue.bin"),
    "vram-at-consumer.bin": ("zero", "queue_consumer-vram.bin"),
    "final-queue.bin": ("zero", "final-queue.bin"),
    "vram-final.bin": ("zero", "final-vram.bin"),
    "final.ss9": ("zero", "final.ss9"),
    "final.png": ("zero", "final.png"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _event(audit: dict[str, Any], name: str) -> dict[str, Any]:
    events = [item for item in audit.get("events", []) if item.get("target") == name]
    if not events:
        raise ValueError(f"missing runtime event: {name}")
    return events[0]


def _guard_ok(guard: dict[str, Any]) -> bool:
    return (
        guard.get("reason") == "completed"
        and guard.get("exit_code") == 0
        and guard.get("degraded") is False
        and guard.get("completion_trigger") == "success-marker"
        and isinstance(guard.get("peak_tree_rss_mib"), (int, float))
        and guard["peak_tree_rss_mib"] <= 1536
    )


def _slot(data: bytes, index: int) -> dict[str, Any]:
    if len(data) != 0x100:
        raise ValueError("queue capture must be exactly 256 bytes")
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
        raise ValueError("queue capture must be exactly 256 bytes")
    return sum(
        struct.unpack_from("<I2I2H", data, index * 16) == expected
        for index in range(16)
    )


def _rows(data: bytes, destination: int, width: int, height: int) -> bytes:
    if len(data) != 0x18000:
        raise ValueError("VRAM capture must be exactly 96 KiB")
    start = destination - VRAM_BASE
    row_bytes = width * 2
    return b"".join(
        data[start + row * VRAM_STRIDE : start + row * VRAM_STRIDE + row_bytes]
        for row in range(height)
    )


def _validate_parent(root: Path) -> dict[str, Any]:
    manifest_path = root / PARENT_DIR / "manifest.json"
    evidence_path = root / PARENT_DIR / "runtime-evidence.json"
    state_path = root / PARENT_DIR / "final.ss9"
    if _sha256(manifest_path) != PARENT_MANIFEST_SHA256:
        raise ValueError("parent v1 manifest changed")
    if _sha256(evidence_path) != PARENT_EVIDENCE_SHA256:
        raise ValueError("parent v1 evidence changed")
    if _sha256(state_path) != PARENT_STATE_SHA256:
        raise ValueError("parent v1 final checkpoint changed")
    manifest = _read_json(manifest_path)
    evidence = _read_json(evidence_path)
    if (
        manifest.get("artifact_id") != "residual-wram-tilemap-runtime-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("files", {}).get("final.ss9") != PARENT_STATE_SHA256
        or evidence.get("summary", {}).get("runtime_verified_count") != 1
        or evidence.get("summary", {}).get("verified_source_pointer") != "0x0834928C"
    ):
        raise ValueError("parent v1 semantics changed")
    return {
        "artifact": PARENT_DIR.as_posix(),
        "manifest_sha256": PARENT_MANIFEST_SHA256,
        "evidence_sha256": PARENT_EVIDENCE_SHA256,
        "verified_source_pointer": "0x0834928C",
    }


def export_artifact(
    root: Path, bridge_run: Path, zero_run: Path, output: Path
) -> dict[str, Any]:
    root = root.resolve()
    bridge_run = bridge_run.resolve()
    zero_run = zero_run.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(output)
    if bridge_run.name != BRIDGE_RUN_ID or zero_run.name != ZERO_RUN_ID:
        raise ValueError("unexpected runtime run ID")
    for path in IMPLEMENTATION_PATHS:
        if not (root / path).is_file():
            raise FileNotFoundError(root / path)
    rom_path = root / "rom/base.gba"
    if _sha256(rom_path) != ROM_SHA256:
        raise ValueError("base ROM changed")
    if _sha256(root / ABI_PATH) != ABI_SHA256:
        raise ValueError("tilemap ABI artifact changed")
    if _sha256(root / OWNERSHIP_PATH) != OWNERSHIP_SHA256:
        raise ValueError("tilemap ownership artifact changed")
    parent = _validate_parent(root)

    bridge_raw, zero_raw = bridge_run / "raw", zero_run / "raw"
    bridge_audit = _read_json(bridge_raw / "audit.json")
    bridge_guard = _read_json(bridge_raw / "guard.json")
    zero_audit = _read_json(zero_raw / "audit.json")
    zero_guard = _read_json(zero_raw / "guard.json")
    if bridge_audit != _read_json(bridge_raw / "done.json"):
        raise ValueError("bridge audit and completion marker differ")
    if zero_audit != _read_json(zero_raw / "done.json"):
        raise ValueError("zero-input audit and completion marker differ")
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
    if (
        bridge_audit.get("schema") != "mgba-wram-tilemap-single-input-probe-v1"
        or bridge_audit.get("run_id") != BRIDGE_RUN_ID
        or bridge_audit.get("outcome") != "targets-observed"
        or bridge_audit.get("input_state_sha256") != PARENT_STATE_SHA256
        or bridge_audit.get("rom_sha256") != ROM_SHA256
        or bridge_audit.get("binary_sha256") != EMULATOR_SHA256
        or bridge_audit.get("inputs") != expected_input
        or bridge_audit.get("automatic_inputs") != []
        or bridge_audit.get("recovery_inputs") != []
        or bridge_audit.get("capture_frames") != 80
        or bridge_audit.get("frame") != 80
        or bridge_audit.get("total_hits") != 81
        or bridge_audit.get("hit_counts") != expected_bridge_hits
        or not _guard_ok(bridge_guard)
    ):
        raise ValueError("single-B bridge provenance mismatch")
    setup = _event(bridge_audit, "scene_panel_setup")
    setup_path = bridge_raw / "scene_panel_setup-hit.ss9"
    if (
        setup.get("address") != "0x0808BAB0"
        or setup.get("pc") != "0x0808BAB2"
        or setup.get("lr") != "0x0808F819"
        or setup.get("frame") != 28
        or _sha256(setup_path) != SETUP_STATE_SHA256
    ):
        raise ValueError("scene-panel setup bridge mismatch")

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
    if (
        zero_audit.get("schema") != "mgba-wram-tilemap-probe-v1"
        or zero_audit.get("run_id") != ZERO_RUN_ID
        or zero_audit.get("input_state_sha256") != SETUP_STATE_SHA256
        or zero_audit.get("rom_sha256") != ROM_SHA256
        or zero_audit.get("binary_sha256") != EMULATOR_SHA256
        or zero_audit.get("inputs") != []
        or zero_audit.get("capture_frames") != 5
        or zero_audit.get("frame") != 5
        or zero_audit.get("total_hits") != 5
        or zero_audit.get("hit_counts") != expected_hits
        or not _guard_ok(zero_guard)
    ):
        raise ValueError("zero-input runtime provenance mismatch")

    queue = (zero_raw / "queue_consumer-queue.bin").read_bytes()
    final_queue = (zero_raw / "final-queue.bin").read_bytes()
    pre_vram = (zero_raw / "queue_consumer-vram.bin").read_bytes()
    final_vram = (zero_raw / "final-vram.bin").read_bytes()
    rom = rom_path.read_bytes()
    abi_records = {
        record["source_pointer"]: record
        for record in _read_json(root / ABI_PATH).get("tilemaps", [])
    }
    records = []
    for spec in SOURCES:
        pointer = spec["source_pointer"]
        pointer_text = _address(pointer)
        load = _event(zero_audit, spec["load_name"])
        expected_slot = {
            "slot_index": spec["slot"],
            "status": 3,
            "source": _address(spec["wram_source"]),
            "destination": _address(spec["vram_destination"]),
            "source_stride_halfwords": spec["width"],
            "row_count": spec["height"],
        }
        if (
            load.get("address") != _address(spec["load_target"])
            or load.get("pc") != _address(spec["load_target"] + 2)
            or load.get("frame") != 2
            or load.get("r0") != pointer_text
            or load.get("r1") != _address(spec["wram_source"])
            or _slot(queue, spec["slot"]) != expected_slot
        ):
            raise ValueError(f"runtime load/queue mismatch for {pointer_text}")
        final_slot = _slot(final_queue, spec["slot"])
        if final_slot != {**expected_slot, "status": 2}:
            raise ValueError(f"queue status did not transition 3->2 for {pointer_text}")
        contract = (
            3,
            spec["wram_source"],
            spec["vram_destination"],
            spec["width"],
            spec["height"],
        )
        if _matching_count(queue, contract) != 1:
            raise ValueError(f"duplicate or missing queue contract for {pointer_text}")
        if _matching_count(final_queue, contract) != 0:
            raise ValueError(f"status-3 queue contract remained for {pointer_text}")
        tilemap = lz77_decompress(rom, pointer - 0x08000000)
        if len(tilemap) != spec["width"] * spec["height"] * 2:
            raise ValueError(f"tilemap size mismatch for {pointer_text}")
        pre_rows = _rows(pre_vram, spec["vram_destination"], spec["width"], spec["height"])
        final_rows = _rows(final_vram, spec["vram_destination"], spec["width"], spec["height"])
        if pre_rows == tilemap or final_rows != tilemap:
            raise ValueError(f"VRAM flush mismatch for {pointer_text}")
        abi = abi_records.get(pointer_text, {})
        if (
            abi.get("load_call") != _address(spec["load_target"])
            or abi.get("queue_consumer") != _address(QUEUE_CONSUMER)
            or abi.get("vram_destination") != _address(spec["vram_destination"])
            or abi.get("decompressed_sha256") != hashlib.sha256(tilemap).hexdigest()
        ):
            raise ValueError(f"ABI mismatch for {pointer_text}")
        records.append(
            {
                "source_pointer": pointer_text,
                "width_entries": spec["width"],
                "height_entries": spec["height"],
                "decompressed_size": len(tilemap),
                "decompressed_sha256": hashlib.sha256(tilemap).hexdigest(),
                "load_hit": {
                    "target": load["address"],
                    "pc": load["pc"],
                    "lr": load["lr"],
                    "frame": load["frame"],
                    "registers": {name: load[name] for name in ("r0", "r1", "r2", "r3")},
                },
                "queue_flush": {
                    "slot_at_first_consumer": expected_slot,
                    "status_at_final": final_slot["status"],
                    "preflush_rows_sha256": hashlib.sha256(pre_rows).hexdigest(),
                    "final_rows_sha256": hashlib.sha256(final_rows).hexdigest(),
                    "preflush_equals_source": False,
                    "final_equals_source": True,
                    "changed_byte_count": sum(a != b for a, b in zip(pre_rows, final_rows)),
                },
            }
        )

    output.mkdir(parents=True)
    roots = {"bridge": bridge_raw, "zero": zero_raw}
    for target, (kind, source) in COPIES.items():
        path = roots[kind] / source
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"invalid runtime evidence input: {path}")
        shutil.copy2(path, output / target)

    consumers = [event for event in zero_audit["events"] if event.get("target") == "queue_consumer"]
    expected_consumer_events = [
        {
            "address": "0x0806365C",
            "pc": "0x0806365E",
            "lr": "0x080614C7",
            "frame": frame,
        }
        for frame in (3, 4)
    ]
    actual_consumer_events = [
        {name: event.get(name) for name in ("address", "pc", "lr", "frame")}
        for event in consumers
    ]
    if actual_consumer_events != expected_consumer_events:
        raise ValueError("queue consumer event sequence mismatch")
    payload = {
        "schema": "residual-wram-tilemap-runtime-evidence-v2",
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "emulator": {"source_commit": EMULATOR_COMMIT, "binary_sha256": EMULATOR_SHA256},
        "parent_runtime_v1": parent,
        "source_artifacts": {
            "abi": {"path": ABI_PATH.as_posix(), "sha256": ABI_SHA256},
            "ownership": {"path": OWNERSHIP_PATH.as_posix(), "sha256": OWNERSHIP_SHA256},
        },
        "bridge": {
            "run_id": BRIDGE_RUN_ID,
            "input_checkpoint": {
                "path": (PARENT_DIR / "final.ss9").as_posix(),
                "sha256": PARENT_STATE_SHA256,
            },
            "inputs": expected_input,
            "scene_panel_setup_hit": {
                "target": setup["address"],
                "pc": setup["pc"],
                "lr": setup["lr"],
                "frame": setup["frame"],
            },
            "setup_checkpoint_sha256": SETUP_STATE_SHA256,
            "audit_sha256": _sha256(output / "bridge-audit.json"),
            "guard_sha256": _sha256(output / "bridge-guard.json"),
            "peak_tree_rss_mib": bridge_guard["peak_tree_rss_mib"],
        },
        "zero_run": {
            "run_id": ZERO_RUN_ID,
            "input_checkpoint_sha256": SETUP_STATE_SHA256,
            "inputs": [],
            "capture_frames": 5,
            "queue_consumer_hit_count": 2,
            "first_consumer_frame": consumers[0]["frame"],
            "second_consumer_frame": consumers[1]["frame"],
            "consumer_events": expected_consumer_events,
            "audit_sha256": _sha256(output / "zero-audit.json"),
            "guard_sha256": _sha256(output / "zero-guard.json"),
            "queue_snapshot_sha256": _sha256(output / "queue-at-consumer.bin"),
            "final_queue_snapshot_sha256": _sha256(output / "final-queue.bin"),
            "preflush_vram_sha256": _sha256(output / "vram-at-consumer.bin"),
            "final_vram_sha256": _sha256(output / "vram-final.bin"),
            "peak_tree_rss_mib": zero_guard["peak_tree_rss_mib"],
        },
        "tilemaps": records,
        "summary": {
            "direct_queue_tilemap_denominator": 3,
            "runtime_verified_count": 3,
            "remaining_runtime_count": 0,
            "verified_source_pointers": ["0x0834928C", "0x083F1C98", "0x085B67E0"],
        },
        "scope": {
            "natural_base_rom_reachability_verified": True,
            "single_input_bridge_verified": True,
            "zero_input_checkpoint_continuation_verified": True,
            "all_direct_queue_sources_runtime_verified": True,
            "queue_status_transition_3_to_2_verified": True,
            "final_vram_rows_equal_rom_tilemaps": True,
            "exclusive_writer_causality_verified": False,
            "modified_rom_pixel_equivalence_verified": False,
            "exact_natural_language_identity_verified": False,
        },
    }
    (output / "runtime-evidence.json").write_bytes(_canonical(payload))
    files = {
        path.relative_to(output).as_posix(): _sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": "residual-wram-tilemap-runtime-v2",
        "artifact_schema": "residual-wram-tilemap-runtime-evidence-v2",
        "artifact_status": "accepted",
        "payload_file": "runtime-evidence.json",
        "payload_sha256": files["runtime-evidence.json"],
        "files": files,
        "implementation": {path: _sha256(root / path) for path in IMPLEMENTATION_PATHS},
        "scope": payload["scope"],
        "verifier": {
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
    }
    (output / "manifest.json").write_bytes(_canonical(manifest))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bridge-run", type=Path, required=True)
    parser.add_argument("--zero-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    bridge = args.bridge_run if args.bridge_run.is_absolute() else root / args.bridge_run
    zero = args.zero_run if args.zero_run.is_absolute() else root / args.zero_run
    output = args.output if args.output.is_absolute() else root / args.output
    payload = export_artifact(root, bridge, zero, output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
