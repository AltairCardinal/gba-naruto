#!/usr/bin/env python3
"""Export the natural 40x10 to 32x10 WRAM crop runtime closure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
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
RUN_ID = "scene-panel-crop-consumer-wram-zero5-20260731"
PARENT_DIR = Path("artifacts/residual-wram-tilemap-runtime-v2")
PARENT_MANIFEST_SHA256 = "73eb055798b1c93a59d9fc6c9bab16525933d2ea9ccfab066fe4b70b6d65d1f7"
PARENT_EVIDENCE_SHA256 = "38698c15b03141659fe83359106454bc2157befce2bdcfd3cd4881f6f1cec617"
SETUP_STATE_SHA256 = "6fed9fe8db43646a5a5a53901a5f0edf1c743ba5e682fd842d3fd19b12776000"
ABI_PATH = Path("artifacts/residual-wram-visual-metadata-abi-v2/residual-wram-visual-metadata-abi.json")
ABI_SHA256 = "4cee47ab097986d50ed0d3b3017fc4fd429037405ee247876022dfd08beac260"
OWNERSHIP_PATH = Path("artifacts/residual-wram-tilemap-resource-ownership-v1/resource-ownership.json")
OWNERSHIP_SHA256 = "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
SOURCE = 0x083F2108
WRAM = 0x02002880
DESTINATION = 0x06001100
SOURCE_WIDTH = 40
SUBMITTED_WIDTH = 32
HEIGHT = 10
IMPLEMENTATION_PATHS = (
    "tools/mgba_wram_crop_tilemap_probe.lua",
    "tests/test_mgba_wram_crop_tilemap_probe_script.py",
    "tools/extract_tileset.py",
    "tools/export_residual_wram_crop_tilemap_runtime_evidence.py",
    "tools/verify_residual_wram_crop_tilemap_runtime_evidence.py",
    "tests/test_residual_wram_crop_tilemap_runtime_evidence.py",
)
COPIES = {
    "audit.json": "audit.json",
    "done.json": "done.json",
    "guard.json": "guard.json",
    "crop-load.ss9": "crop_load-hit.ss9",
    "crop-consumer.ss9": "crop_consumer-hit.ss9",
    "vram-at-consumer.bin": "crop_consumer-vram.bin",
    "wram-at-consumer.bin": "crop_consumer-wram.bin",
    "vram-final.bin": "final-vram.bin",
    "final.ss9": "final.ss9",
    "final.png": "final.png",
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
        raise ValueError(f"{path} is not a JSON object")
    return value


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _event(audit: dict[str, Any], name: str) -> dict[str, Any]:
    events = [event for event in audit.get("events", []) if event.get("target") == name]
    if not events:
        raise ValueError(f"missing event: {name}")
    return events[0]


def _event_record(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "target": event["address"],
        "pc": event["pc"],
        "lr": event["lr"],
        "frame": event["frame"],
        "cycle": event["cycle"],
        "registers": {name: event[name] for name in ("r0", "r1", "r2", "r3")},
    }


def export_artifact(root: Path, run: Path, output: Path) -> dict[str, Any]:
    root, run, output = root.resolve(), run.resolve(), output.resolve()
    if run.name != RUN_ID:
        raise ValueError("unexpected runtime run ID")
    if output.exists():
        raise FileExistsError(output)
    for relative in IMPLEMENTATION_PATHS:
        if not (root / relative).is_file():
            raise FileNotFoundError(root / relative)
    rom_path = root / "rom/base.gba"
    if _sha256(rom_path) != ROM_SHA256:
        raise ValueError("base ROM changed")
    parent_manifest = root / PARENT_DIR / "manifest.json"
    parent_evidence = root / PARENT_DIR / "runtime-evidence.json"
    parent_state = root / PARENT_DIR / "scene-panel-setup.ss9"
    if (
        _sha256(parent_manifest) != PARENT_MANIFEST_SHA256
        or _sha256(parent_evidence) != PARENT_EVIDENCE_SHA256
        or _sha256(parent_state) != SETUP_STATE_SHA256
    ):
        raise ValueError("parent runtime v2 changed")
    parent = _read_json(parent_manifest)
    if (
        parent.get("artifact_id") != "residual-wram-tilemap-runtime-v2"
        or parent.get("artifact_status") != "accepted"
        or parent.get("files", {}).get("scene-panel-setup.ss9") != SETUP_STATE_SHA256
    ):
        raise ValueError("parent runtime v2 semantics changed")
    if _sha256(root / ABI_PATH) != ABI_SHA256:
        raise ValueError("derived tilemap ABI changed")
    if _sha256(root / OWNERSHIP_PATH) != OWNERSHIP_SHA256:
        raise ValueError("tilemap ownership changed")

    raw = run / "raw"
    audit = _read_json(raw / "audit.json")
    guard = _read_json(raw / "guard.json")
    if audit != _read_json(raw / "done.json"):
        raise ValueError("audit and completion marker differ")
    if (
        audit.get("schema") != "mgba-wram-crop-tilemap-probe-v1"
        or audit.get("run_id") != RUN_ID
        or audit.get("outcome") != "targets-observed"
        or audit.get("input_state_sha256") != SETUP_STATE_SHA256
        or audit.get("rom_sha256") != ROM_SHA256
        or audit.get("binary_sha256") != EMULATOR_SHA256
        or audit.get("inputs") != []
        or audit.get("capture_frames") != 5
        or audit.get("frame") != 5
        or audit.get("total_hits") != 4
        or audit.get("hit_counts") != {"crop_load": 1, "crop_consumer": 3}
    ):
        raise ValueError("runtime audit mismatch")
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("peak_tree_rss_mib", 1537) > 1536
    ):
        raise ValueError("resource guard rejected runtime")
    load = _event(audit, "crop_load")
    consumer = _event(audit, "crop_consumer")
    if (
        load.get("address") != "0x0808BC2E"
        or load.get("pc") != "0x0808BC30"
        or load.get("lr") != "0x0808BC2B"
        or load.get("frame") != 3
        or load.get("r0") != "0x083F2108"
        or load.get("r1") != "0x02002880"
        or consumer.get("address") != "0x0808B79C"
        or consumer.get("pc") != "0x0808B79E"
        or consumer.get("lr") != "0x0808BC3B"
        or consumer.get("frame") != 3
    ):
        raise ValueError("load/consumer runtime sequence mismatch")

    rom = rom_path.read_bytes()
    decoded = lz77_decompress(rom, SOURCE - 0x08000000)
    consumer_wram = (raw / "crop_consumer-wram.bin").read_bytes()
    if consumer_wram != decoded:
        raise ValueError("consumer WRAM does not match ROM source")
    expected = b"".join(
        decoded[row * SOURCE_WIDTH * 2 : row * SOURCE_WIDTH * 2 + SUBMITTED_WIDTH * 2]
        for row in range(HEIGHT)
    )
    pre_vram = (raw / "crop_consumer-vram.bin").read_bytes()
    final_vram = (raw / "final-vram.bin").read_bytes()
    if len(pre_vram) != 0x18000 or len(final_vram) != 0x18000:
        raise ValueError("VRAM capture size mismatch")
    start = DESTINATION - 0x06000000
    pre = pre_vram[start : start + len(expected)]
    final = final_vram[start : start + len(expected)]
    if pre == expected or final != expected:
        raise ValueError("crop VRAM relationship mismatch")
    abi = next(
        record
        for record in _read_json(root / ABI_PATH).get("tilemap_sources", [])
        if record.get("source_pointer") == "0x083F2108"
    )
    if (
        abi.get("classification") != "direct_cpu_crop_tilemap"
        or abi.get("load_call") != "0x0808BC2E"
        or abi.get("submit_consumer") != "0x0808B79C"
        or abi.get("vram_destination") != "0x06001100"
        or abi.get("decompressed_sha256") != hashlib.sha256(decoded).hexdigest()
    ):
        raise ValueError("derived tilemap ABI mismatch")

    output.mkdir(parents=True)
    for target, source in COPIES.items():
        path = raw / source
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"invalid runtime input: {source}")
        shutil.copy2(path, output / target)
    payload = {
        "schema": "residual-wram-crop-tilemap-runtime-evidence-v1",
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "emulator": {"source_commit": EMULATOR_COMMIT, "binary_sha256": EMULATOR_SHA256},
        "parent_runtime": {
            "artifact": PARENT_DIR.as_posix(),
            "manifest_sha256": PARENT_MANIFEST_SHA256,
            "evidence_sha256": PARENT_EVIDENCE_SHA256,
            "checkpoint": "scene-panel-setup.ss9",
            "checkpoint_sha256": SETUP_STATE_SHA256,
        },
        "source_artifacts": {
            "abi": {"path": ABI_PATH.as_posix(), "sha256": ABI_SHA256},
            "ownership": {"path": OWNERSHIP_PATH.as_posix(), "sha256": OWNERSHIP_SHA256},
        },
        "run": {
            "run_id": RUN_ID,
            "inputs": [],
            "capture_frames": 5,
            "audit_sha256": _sha256(output / "audit.json"),
            "guard_sha256": _sha256(output / "guard.json"),
            "consumer_vram_sha256": _sha256(output / "vram-at-consumer.bin"),
            "consumer_wram_sha256": _sha256(output / "wram-at-consumer.bin"),
            "final_vram_sha256": _sha256(output / "vram-final.bin"),
            "load_checkpoint_sha256": _sha256(output / "crop-load.ss9"),
            "consumer_checkpoint_sha256": _sha256(output / "crop-consumer.ss9"),
            "final_checkpoint_sha256": _sha256(output / "final.ss9"),
            "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
        },
        "load_hit": _event_record(load),
        "consumer_hit": _event_record(consumer),
        "crop_flush": {
            "source_pointer": "0x083F2108",
            "wram_source": "0x02002880",
            "vram_destination": "0x06001100",
            "source_width_entries": SOURCE_WIDTH,
            "submitted_width_entries": SUBMITTED_WIDTH,
            "height_entries": HEIGHT,
            "discarded_right_entries_per_row": SOURCE_WIDTH - SUBMITTED_WIDTH,
            "source_decompressed_size": len(decoded),
            "source_decompressed_sha256": hashlib.sha256(decoded).hexdigest(),
            "expected_crop_size": len(expected),
            "expected_crop_sha256": hashlib.sha256(expected).hexdigest(),
            "consumer_entry_sha256": hashlib.sha256(pre).hexdigest(),
            "final_sha256": hashlib.sha256(final).hexdigest(),
            "consumer_entry_equals_expected": False,
            "consumer_wram_sha256": hashlib.sha256(consumer_wram).hexdigest(),
            "consumer_wram_equals_source": True,
            "final_equals_expected": True,
            "changed_byte_count": sum(a != b for a, b in zip(pre, final)),
        },
        "summary": {
            "derived_tilemap_denominator": 4,
            "runtime_verified_count": 1,
            "remaining_runtime_count": 3,
            "verified_source_pointer": "0x083F2108",
            "remaining_source_pointers": ["0x084634B8", "0x0846356C", "0x084635D8"],
        },
        "scope": {
            "natural_base_rom_reachability_verified": True,
            "zero_input_checkpoint_continuation_verified": True,
            "crop_consumer_entry_verified": True,
            "final_vram_crop_equals_rom_source_verified": True,
            "exclusive_writer_causality_verified": False,
            "modified_rom_pixel_equivalence_verified": False,
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
        "artifact_id": "residual-wram-crop-tilemap-runtime-v1",
        "artifact_schema": payload["schema"],
        "artifact_status": "accepted",
        "payload_file": "runtime-evidence.json",
        "payload_sha256": files["runtime-evidence.json"],
        "files": files,
        "implementation": {path: _sha256(root / path) for path in IMPLEMENTATION_PATHS},
        "scope": payload["scope"],
        "verifier": {
            "command": [
                "python3",
                "tools/verify_residual_wram_crop_tilemap_runtime_evidence.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/residual-wram-crop-tilemap-runtime-v1",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_bytes(_canonical(manifest))
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
