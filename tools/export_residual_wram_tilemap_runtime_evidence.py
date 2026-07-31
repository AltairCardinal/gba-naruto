#!/usr/bin/env python3
"""Promote the natural selection-grid WRAM tilemap queue/flush capture."""

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
except ModuleNotFoundError:  # Direct ``python tools/...`` execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.extract_tileset import lz77_decompress


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
EMULATOR_SHA256 = "4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72"
EMULATOR_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
INPUT_STATE = Path("artifacts/lz77-palette-runtime-v1/runs/profile-browser-init/hit.ss9")
INPUT_STATE_SHA256 = "ad2d215c2054e694d67fdd40e22c0aff99fe930466126a2823129ab34e33570c"
SOURCE_POINTER = 0x0834928C
LOAD_TARGET = 0x0808AD3A
QUEUE_CONSUMER = 0x0806365C
VRAM_DESTINATION = 0x0600001E
WRAM_SOURCE = 0x02002B48
WIDTH = 15
HEIGHT = 20
ROW_BYTES = WIDTH * 2
VRAM_ROW_STRIDE = 64
EXPECTED_RUN_ID = "selection-post-consumer-zero-20260731"
EXPECTED_RAW_FILES = {
    "audit.json": "audit.json",
    "guard.json": "guard.json",
    "queue_consumer-queue.bin": "queue-at-consumer.bin",
    "final-queue.bin": "final-queue.bin",
    "queue_consumer-vram.bin": "vram-at-consumer.bin",
    "final-vram.bin": "vram-final.bin",
    "hit.ss9": "hit.ss9",
    "final.ss9": "final.ss9",
    "final.png": "final.png",
}
IMPLEMENTATION_PATHS = (
    "tools/mgba_wram_tilemap_probe.lua",
    "tests/test_mgba_wram_tilemap_probe_script.py",
    "tools/extract_tileset.py",
    "tools/export_residual_wram_tilemap_runtime_evidence.py",
    "tools/verify_residual_wram_tilemap_runtime_evidence.py",
    "tests/test_residual_wram_tilemap_runtime_evidence.py",
)
ABI_PAYLOAD = Path(
    "artifacts/residual-wram-tilemap-abi-v1/residual-wram-tilemap-abi.json"
)
OWNERSHIP_PAYLOAD = Path(
    "artifacts/residual-wram-tilemap-resource-ownership-v1/resource-ownership.json"
)
PARENT_RUNTIME_MANIFEST = Path("artifacts/lz77-palette-runtime-v1/manifest.json")
PARENT_RUNTIME_MANIFEST_SHA256 = (
    "d363310303d8b51d0cc6f64014489297071882859c547694b3db91f7c11c52bf"
)
PARENT_RUNTIME_EVIDENCE = Path("artifacts/lz77-palette-runtime-v1/evidence.json")
PARENT_RUNTIME_EVIDENCE_SHA256 = (
    "d73fa7147eb7aa0b6a221cca73182d763c6321c70121067625368705f0b50967"
)
PARENT_RUNTIME_AUDIT = Path(
    "artifacts/lz77-palette-runtime-v1/runs/profile-browser-init/audit.json"
)
PARENT_RUNTIME_AUDIT_SHA256 = (
    "0b3b708a89cf09df1ac1d6a1bc1cbfa6d0abc9c7eddb7bb18641d509e1ab1c90"
)
ABI_MANIFEST = Path("artifacts/residual-wram-tilemap-abi-v1/manifest.json")
ABI_MANIFEST_SHA256 = (
    "59380e804f695ba16f20617e8b012f6edb8463f854041c71ee17da92a34b0ddb"
)
OWNERSHIP_MANIFEST = Path(
    "artifacts/residual-wram-tilemap-resource-ownership-v1/manifest.json"
)
OWNERSHIP_MANIFEST_SHA256 = (
    "57e04df8c14ac9ee0b34a5102e42b1d9761e168343e3671b8e396fe938123ab5"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _rows(vram: bytes) -> bytes:
    if len(vram) != 0x18000:
        raise ValueError("VRAM capture must be exactly 96 KiB")
    start = VRAM_DESTINATION - 0x06000000
    return b"".join(
        vram[start + row * VRAM_ROW_STRIDE : start + row * VRAM_ROW_STRIDE + ROW_BYTES]
        for row in range(HEIGHT)
    )


def _queue_slot(queue: bytes) -> dict[str, Any]:
    if len(queue) != 0x100:
        raise ValueError("queue capture must be exactly 256 bytes")
    status, source, destination, source_stride, row_count = struct.unpack_from(
        "<I2I2H", queue, 0
    )
    return {
        "slot_index": 0,
        "status": status,
        "source": _address(source),
        "destination": _address(destination),
        "source_stride_halfwords": source_stride,
        "row_count": row_count,
    }


def _matching_queue_entry_count(queue: bytes) -> int:
    if len(queue) != 0x100:
        raise ValueError("queue capture must be exactly 256 bytes")
    expected = (3, WRAM_SOURCE, VRAM_DESTINATION, WIDTH, HEIGHT)
    return sum(
        struct.unpack_from("<I2I2H", queue, index * 16) == expected
        for index in range(16)
    )


def _event(audit: dict[str, Any], target: str) -> dict[str, Any]:
    events = [event for event in audit.get("events", []) if event.get("target") == target]
    if not events:
        raise ValueError(f"missing {target} event")
    return events[0]


def _source_artifact(
    root: Path,
    path: Path,
    expected_sha256: str,
    manifest_path: Path,
    expected_manifest_sha256: str,
) -> dict[str, str]:
    if _sha256(root / path) != expected_sha256:
        raise ValueError(f"source artifact payload changed: {path}")
    if _sha256(root / manifest_path) != expected_manifest_sha256:
        raise ValueError(f"source artifact manifest changed: {manifest_path}")
    return {
        "path": path.as_posix(),
        "sha256": expected_sha256,
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": expected_manifest_sha256,
    }


def export_artifact(root: Path, run: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    run = run.resolve()
    output = output.resolve()
    raw = run / "raw"
    if run.name != EXPECTED_RUN_ID:
        raise ValueError("unexpected runtime run ID")
    if output.exists():
        raise FileExistsError(output)

    rom_path = root / "rom/base.gba"
    if _sha256(rom_path) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    if _sha256(root / INPUT_STATE) != INPUT_STATE_SHA256:
        raise ValueError("input checkpoint SHA-256 changed")
    for path, expected in (
        (PARENT_RUNTIME_MANIFEST, PARENT_RUNTIME_MANIFEST_SHA256),
        (PARENT_RUNTIME_EVIDENCE, PARENT_RUNTIME_EVIDENCE_SHA256),
        (PARENT_RUNTIME_AUDIT, PARENT_RUNTIME_AUDIT_SHA256),
    ):
        if _sha256(root / path) != expected:
            raise ValueError(f"parent runtime provenance changed: {path}")
    for path in IMPLEMENTATION_PATHS:
        if not (root / path).is_file():
            raise FileNotFoundError(root / path)

    audit = _read_json(raw / "audit.json")
    guard = _read_json(raw / "guard.json")
    if audit != _read_json(raw / "done.json"):
        raise ValueError("audit and completion marker differ")
    if (
        audit.get("schema") != "mgba-wram-tilemap-probe-v1"
        or audit.get("run_id") != EXPECTED_RUN_ID
        or audit.get("rom_sha256") != ROM_SHA256
        or audit.get("binary_sha256") != EMULATOR_SHA256
        or audit.get("input_state_sha256") != INPUT_STATE_SHA256
        or audit.get("inputs") != []
    ):
        raise ValueError("runtime audit provenance mismatch")
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("peak_tree_rss_mib", 1537) > 1536
    ):
        raise ValueError("resource guard did not accept the run")

    load = _event(audit, "selection_load")
    consumer = _event(audit, "queue_consumer")
    if (
        load.get("address") != _address(LOAD_TARGET)
        or load.get("pc") != _address(LOAD_TARGET + 2)
        or load.get("frame") != 0
        or load.get("r0") != _address(SOURCE_POINTER)
        or load.get("r1") != _address(WRAM_SOURCE)
        or consumer.get("address") != _address(QUEUE_CONSUMER)
        or consumer.get("pc") != _address(QUEUE_CONSUMER + 2)
        or consumer.get("frame") != 2
    ):
        raise ValueError("runtime breakpoint sequence mismatch")

    rom = rom_path.read_bytes()
    tilemap = lz77_decompress(rom, SOURCE_POINTER - 0x08000000)
    if len(tilemap) != WIDTH * HEIGHT * 2:
        raise ValueError("selection tilemap size changed")
    queue = (raw / "queue_consumer-queue.bin").read_bytes()
    final_queue = (raw / "final-queue.bin").read_bytes()
    slot = _queue_slot(queue)
    expected_slot = {
        "slot_index": 0,
        "status": 3,
        "source": _address(WRAM_SOURCE),
        "destination": _address(VRAM_DESTINATION),
        "source_stride_halfwords": WIDTH,
        "row_count": HEIGHT,
    }
    if slot != expected_slot:
        raise ValueError("queue slot contract mismatch")
    final_match_count = _matching_queue_entry_count(final_queue)
    if final_match_count != 0:
        raise ValueError("captured status-3 queue entry remained after consumer")
    pre_rows = _rows((raw / "queue_consumer-vram.bin").read_bytes())
    final_rows = _rows((raw / "final-vram.bin").read_bytes())
    if pre_rows == tilemap or final_rows != tilemap:
        raise ValueError("VRAM flush relationship mismatch")

    output.mkdir(parents=True)
    for source_name, target_name in EXPECTED_RAW_FILES.items():
        source = raw / source_name
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"invalid runtime evidence input: {source_name}")
        shutil.copy2(source, output / target_name)

    payload: dict[str, Any] = {
        "schema": "residual-wram-tilemap-runtime-evidence-v1",
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "emulator": {
            "source_commit": EMULATOR_COMMIT,
            "binary_sha256": EMULATOR_SHA256,
        },
        "probe": {
            "path": "tools/mgba_wram_tilemap_probe.lua",
            "sha256": _sha256(root / "tools/mgba_wram_tilemap_probe.lua"),
            "test": "tests/test_mgba_wram_tilemap_probe_script.py",
            "test_sha256": _sha256(root / "tests/test_mgba_wram_tilemap_probe_script.py"),
        },
        "input_checkpoint": {
            "path": INPUT_STATE.as_posix(),
            "sha256": INPUT_STATE_SHA256,
            "provenance": {
                "manifest_path": PARENT_RUNTIME_MANIFEST.as_posix(),
                "manifest_sha256": PARENT_RUNTIME_MANIFEST_SHA256,
                "evidence_path": PARENT_RUNTIME_EVIDENCE.as_posix(),
                "evidence_sha256": PARENT_RUNTIME_EVIDENCE_SHA256,
                "audit_path": PARENT_RUNTIME_AUDIT.as_posix(),
                "audit_sha256": PARENT_RUNTIME_AUDIT_SHA256,
                "route": "profile-browser-init",
                "target_pc": "0x0808B5EE",
                "hit_frame": 54,
            },
        },
        "source_artifacts": {
            "abi": _source_artifact(
                root,
                ABI_PAYLOAD,
                "07e1f89b5aaff938184d5d31bea4174e995f96d10b8ffbee56bff0f609a27dfc",
                ABI_MANIFEST,
                ABI_MANIFEST_SHA256,
            ),
            "ownership": _source_artifact(
                root,
                OWNERSHIP_PAYLOAD,
                "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7",
                OWNERSHIP_MANIFEST,
                OWNERSHIP_MANIFEST_SHA256,
            ),
        },
        "run": {
            "run_id": EXPECTED_RUN_ID,
            "inputs": [],
            "capture_frames": audit["capture_frames"],
            "final_frame": audit["frame"],
            "total_hits": audit["total_hits"],
            "hit_counts": audit["hit_counts"],
            "audit_sha256": _sha256(output / "audit.json"),
            "guard_sha256": _sha256(output / "guard.json"),
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
        },
        "tilemap": {
            "source_pointer": _address(SOURCE_POINTER),
            "width_entries": WIDTH,
            "height_entries": HEIGHT,
            "decompressed_size": len(tilemap),
            "decompressed_sha256": hashlib.sha256(tilemap).hexdigest(),
            "vram_destination": _address(VRAM_DESTINATION),
            "destination_row_stride_bytes": VRAM_ROW_STRIDE,
        },
        "load_hit": {
            "target": load["address"],
            "pc": load["pc"],
            "lr": load["lr"],
            "frame": load["frame"],
            "cycle": load["cycle"],
            "registers": {name: load[name] for name in ("r0", "r1", "r2", "r3")},
        },
        "queue_flush": {
            "consumer_target": consumer["address"],
            "consumer_pc": consumer["pc"],
            "consumer_lr": consumer["lr"],
            "first_consumer_frame": consumer["frame"],
            "slot": slot,
            "queue_snapshot_sha256": _sha256(output / "queue-at-consumer.bin"),
            "post_consumer_queue_snapshot_sha256": _sha256(
                output / "final-queue.bin"
            ),
            "post_consumer_frame": audit["frame"],
            "captured_entry_count_at_post_consumer": final_match_count,
            "captured_entry_retired_before_post_consumer_capture": (
                final_match_count == 0
            ),
            "preflush_rows_sha256": hashlib.sha256(pre_rows).hexdigest(),
            "final_rows_sha256": hashlib.sha256(final_rows).hexdigest(),
            "preflush_equals_source": pre_rows == tilemap,
            "final_equals_source": final_rows == tilemap,
            "changed_byte_count": sum(a != b for a, b in zip(pre_rows, final_rows)),
        },
        "remaining_direct_queue_sources": ["0x083F1C98", "0x085B67E0"],
        "summary": {
            "direct_queue_tilemap_denominator": 3,
            "runtime_verified_count": 1,
            "remaining_runtime_count": 2,
            "verified_source_pointer": _address(SOURCE_POINTER),
        },
        "scope": {
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
        },
    }
    payload_bytes = _canonical_json(payload)
    (output / "runtime-evidence.json").write_bytes(payload_bytes)
    files = {
        path.relative_to(output).as_posix(): _sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    implementation = {path: _sha256(root / path) for path in IMPLEMENTATION_PATHS}
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": "residual-wram-tilemap-runtime-v1",
        "artifact_schema": "residual-wram-tilemap-runtime-evidence-v1",
        "artifact_status": "accepted",
        "payload_file": "runtime-evidence.json",
        "payload_sha256": files["runtime-evidence.json"],
        "files": files,
        "implementation": implementation,
        "scope": payload["scope"],
        "verifier": {
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
    }
    (output / "manifest.json").write_bytes(_canonical_json(manifest))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    run = args.run if args.run.is_absolute() else root / args.run
    output = args.output if args.output.is_absolute() else root / args.output
    payload = export_artifact(root, run, output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
