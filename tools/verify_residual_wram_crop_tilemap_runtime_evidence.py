#!/usr/bin/env python3
"""Independently verify the natural WRAM crop-tilemap runtime artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
EMULATOR_SHA256 = "4856a8f95a32d0d2d97e0141a4dbe33c162abf27295a8f85ed8fb3c17a42ea72"
EMULATOR_COMMIT = "c16c3ff55585e71bee83c95539c2ecde15d728c8"
RUN_ID = "scene-panel-crop-consumer-wram-zero5-20260731"
PARENT_DIR = "artifacts/residual-wram-tilemap-runtime-v2"
PARENT_MANIFEST_SHA256 = "73eb055798b1c93a59d9fc6c9bab16525933d2ea9ccfab066fe4b70b6d65d1f7"
PARENT_EVIDENCE_SHA256 = "38698c15b03141659fe83359106454bc2157befce2bdcfd3cd4881f6f1cec617"
SETUP_STATE_SHA256 = "6fed9fe8db43646a5a5a53901a5f0edf1c743ba5e682fd842d3fd19b12776000"
ABI_PATH = "artifacts/residual-wram-visual-metadata-abi-v2/residual-wram-visual-metadata-abi.json"
ABI_SHA256 = "4cee47ab097986d50ed0d3b3017fc4fd429037405ee247876022dfd08beac260"
OWNERSHIP_PATH = "artifacts/residual-wram-tilemap-resource-ownership-v1/resource-ownership.json"
OWNERSHIP_SHA256 = "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
EXPECTED_FILES = {
    "audit.json",
    "done.json",
    "guard.json",
    "crop-load.ss9",
    "crop-consumer.ss9",
    "vram-at-consumer.bin",
    "wram-at-consumer.bin",
    "vram-final.bin",
    "final.ss9",
    "final.png",
    "runtime-evidence.json",
}
IMPLEMENTATION_PATHS = (
    "tools/mgba_wram_crop_tilemap_probe.lua",
    "tests/test_mgba_wram_crop_tilemap_probe_script.py",
    "tools/extract_tileset.py",
    "tools/export_residual_wram_crop_tilemap_runtime_evidence.py",
    "tools/verify_residual_wram_crop_tilemap_runtime_evidence.py",
    "tests/test_residual_wram_crop_tilemap_runtime_evidence.py",
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
                distance = (token & 0xFFF) + 1
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


def _event(audit: dict[str, Any], name: str) -> dict[str, Any]:
    events = [event for event in audit.get("events", []) if event.get("target") == name]
    return events[0] if events else {}


def _record(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "target": event.get("address"),
        "pc": event.get("pc"),
        "lr": event.get("lr"),
        "frame": event.get("frame"),
        "cycle": event.get("cycle"),
        "registers": {name: event.get(name) for name in ("r0", "r1", "r2", "r3")},
    }


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
            for path in paths
            if path.is_file() and path.name != "manifest.json"
        }
        if set(actual) != EXPECTED_FILES:
            errors.append("artifact file inventory mismatch")
        manifest = _read_json(artifact_dir / "manifest.json")
        payload = _read_json(artifact_dir / "runtime-evidence.json")
        for field, expected in (
            ("schema", "git-artifact-promotion-v1"),
            ("artifact_id", "residual-wram-crop-tilemap-runtime-v1"),
            ("artifact_schema", "residual-wram-crop-tilemap-runtime-evidence-v1"),
            ("artifact_status", "accepted"),
            ("payload_file", "runtime-evidence.json"),
        ):
            _expect(errors, manifest.get(field), expected, f"manifest {field} mismatch")
        inventory = manifest.get("files", {})
        if not isinstance(inventory, dict) or set(inventory) != EXPECTED_FILES:
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
        _expect(
            errors,
            manifest.get("verifier"),
            {
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
            "manifest verifier declaration mismatch",
        )

        parent_dir = root / PARENT_DIR
        _expect(errors, _sha256(parent_dir / "manifest.json"), PARENT_MANIFEST_SHA256, "parent manifest mismatch")
        _expect(errors, _sha256(parent_dir / "runtime-evidence.json"), PARENT_EVIDENCE_SHA256, "parent evidence mismatch")
        _expect(errors, _sha256(parent_dir / "scene-panel-setup.ss9"), SETUP_STATE_SHA256, "parent checkpoint mismatch")
        parent_manifest = _read_json(parent_dir / "manifest.json")
        _expect(errors, parent_manifest.get("artifact_id"), "residual-wram-tilemap-runtime-v2", "parent artifact ID mismatch")
        _expect(errors, parent_manifest.get("artifact_status"), "accepted", "parent status mismatch")
        expected_parent = {
            "artifact": PARENT_DIR,
            "manifest_sha256": PARENT_MANIFEST_SHA256,
            "evidence_sha256": PARENT_EVIDENCE_SHA256,
            "checkpoint": "scene-panel-setup.ss9",
            "checkpoint_sha256": SETUP_STATE_SHA256,
        }
        _expect(errors, payload.get("parent_runtime"), expected_parent, "parent payload mismatch")

        rom_path = root / "rom/base.gba"
        _expect(errors, _sha256(rom_path), ROM_SHA256, "base ROM mismatch")
        _expect(errors, _sha256(root / ABI_PATH), ABI_SHA256, "ABI hash mismatch")
        _expect(errors, _sha256(root / OWNERSHIP_PATH), OWNERSHIP_SHA256, "ownership hash mismatch")
        _expect(errors, payload.get("rom"), {"path": "rom/base.gba", "sha256": ROM_SHA256}, "ROM payload mismatch")
        _expect(errors, payload.get("emulator"), {"source_commit": EMULATOR_COMMIT, "binary_sha256": EMULATOR_SHA256}, "emulator payload mismatch")
        _expect(
            errors,
            payload.get("source_artifacts"),
            {
                "abi": {"path": ABI_PATH, "sha256": ABI_SHA256},
                "ownership": {"path": OWNERSHIP_PATH, "sha256": OWNERSHIP_SHA256},
            },
            "source artifacts mismatch",
        )

        audit = _read_json(artifact_dir / "audit.json")
        _expect(errors, audit, _read_json(artifact_dir / "done.json"), "audit and done differ")
        for field, expected in (
            ("schema", "mgba-wram-crop-tilemap-probe-v1"),
            ("run_id", RUN_ID),
            ("outcome", "targets-observed"),
            ("input_state_sha256", SETUP_STATE_SHA256),
            ("rom_sha256", ROM_SHA256),
            ("binary_sha256", EMULATOR_SHA256),
            ("inputs", []),
            ("capture_frames", 5),
            ("frame", 5),
            ("total_hits", 4),
            ("hit_counts", {"crop_load": 1, "crop_consumer": 3}),
        ):
            _expect(errors, audit.get(field), expected, f"audit {field} mismatch")
        guard = _read_json(artifact_dir / "guard.json")
        for field, expected in (
            ("reason", "completed"),
            ("exit_code", 0),
            ("degraded", False),
            ("completion_trigger", "success-marker"),
        ):
            _expect(errors, guard.get(field), expected, f"guard {field} mismatch")
        peak = guard.get("peak_tree_rss_mib")
        if not isinstance(peak, (int, float)) or peak > 1536:
            errors.append("guard peak RSS mismatch")
        run = payload.get("run", {})
        for field, expected in (
            ("run_id", RUN_ID),
            ("inputs", []),
            ("capture_frames", 5),
            ("audit_sha256", _sha256(artifact_dir / "audit.json")),
            ("guard_sha256", _sha256(artifact_dir / "guard.json")),
            ("consumer_vram_sha256", _sha256(artifact_dir / "vram-at-consumer.bin")),
            ("consumer_wram_sha256", _sha256(artifact_dir / "wram-at-consumer.bin")),
            ("final_vram_sha256", _sha256(artifact_dir / "vram-final.bin")),
            ("load_checkpoint_sha256", _sha256(artifact_dir / "crop-load.ss9")),
            ("consumer_checkpoint_sha256", _sha256(artifact_dir / "crop-consumer.ss9")),
            ("final_checkpoint_sha256", _sha256(artifact_dir / "final.ss9")),
            ("peak_tree_rss_mib", peak),
        ):
            _expect(errors, run.get(field), expected, f"run {field} mismatch")

        load = _event(audit, "crop_load")
        consumer = _event(audit, "crop_consumer")
        for field, expected in (
            ("address", "0x0808BC2E"),
            ("pc", "0x0808BC30"),
            ("lr", "0x0808BC2B"),
            ("frame", 3),
            ("r0", "0x083F2108"),
            ("r1", "0x02002880"),
        ):
            _expect(errors, load.get(field), expected, f"load {field} mismatch")
        for field, expected in (
            ("address", "0x0808B79C"),
            ("pc", "0x0808B79E"),
            ("lr", "0x0808BC3B"),
            ("frame", 3),
        ):
            _expect(errors, consumer.get(field), expected, f"consumer {field} mismatch")
        _expect(errors, payload.get("load_hit"), _record(load), "load payload mismatch")
        _expect(errors, payload.get("consumer_hit"), _record(consumer), "consumer payload mismatch")

        rom = rom_path.read_bytes()
        decoded = _decode_lz77(rom, 0x083F2108 - 0x08000000)
        consumer_wram = (artifact_dir / "wram-at-consumer.bin").read_bytes()
        if consumer_wram != decoded:
            errors.append("consumer WRAM does not match ROM source")
        expected = b"".join(decoded[row * 80 : row * 80 + 64] for row in range(10))
        pre_vram = (artifact_dir / "vram-at-consumer.bin").read_bytes()
        final_vram = (artifact_dir / "vram-final.bin").read_bytes()
        if len(pre_vram) != 0x18000 or len(final_vram) != 0x18000:
            errors.append("VRAM capture size mismatch")
        pre = pre_vram[0x1100:0x1380]
        final = final_vram[0x1100:0x1380]
        if pre == expected:
            errors.append("consumer VRAM already equals expected crop")
        if final != expected:
            errors.append("final VRAM crop does not match ROM source")
        changed = sum(a != b for a, b in zip(pre, final))
        crop = {
            "source_pointer": "0x083F2108",
            "wram_source": "0x02002880",
            "vram_destination": "0x06001100",
            "source_width_entries": 40,
            "submitted_width_entries": 32,
            "height_entries": 10,
            "discarded_right_entries_per_row": 8,
            "source_decompressed_size": len(decoded),
            "source_decompressed_sha256": hashlib.sha256(decoded).hexdigest(),
            "expected_crop_size": len(expected),
            "expected_crop_sha256": hashlib.sha256(expected).hexdigest(),
            "consumer_entry_sha256": hashlib.sha256(pre).hexdigest(),
            "final_sha256": hashlib.sha256(final).hexdigest(),
            "consumer_entry_equals_expected": pre == expected,
            "consumer_wram_sha256": hashlib.sha256(consumer_wram).hexdigest(),
            "consumer_wram_equals_source": consumer_wram == decoded,
            "final_equals_expected": final == expected,
            "changed_byte_count": changed,
        }
        _expect(errors, payload.get("crop_flush"), crop, "crop payload mismatch")
        _expect(errors, changed, 640, "crop changed-byte count mismatch")
        abi = next(
            record
            for record in _read_json(root / ABI_PATH).get("tilemap_sources", [])
            if record.get("source_pointer") == "0x083F2108"
        )
        for field, expected_value in (
            ("classification", "direct_cpu_crop_tilemap"),
            ("load_call", "0x0808BC2E"),
            ("submit_consumer", "0x0808B79C"),
            ("vram_destination", "0x06001100"),
            ("decompressed_sha256", hashlib.sha256(decoded).hexdigest()),
        ):
            _expect(errors, abi.get(field), expected_value, f"ABI {field} mismatch")

        summary = {
            "derived_tilemap_denominator": 4,
            "runtime_verified_count": 1,
            "remaining_runtime_count": 3,
            "verified_source_pointer": "0x083F2108",
            "remaining_source_pointers": ["0x084634B8", "0x0846356C", "0x084635D8"],
        }
        scope = {
            "natural_base_rom_reachability_verified": True,
            "zero_input_checkpoint_continuation_verified": True,
            "crop_consumer_entry_verified": True,
            "final_vram_crop_equals_rom_source_verified": True,
            "exclusive_writer_causality_verified": False,
            "modified_rom_pixel_equivalence_verified": False,
        }
        _expect(errors, payload.get("summary"), summary, "summary mismatch")
        _expect(errors, payload.get("scope"), scope, "scope mismatch")
        _expect(errors, manifest.get("scope"), scope, "manifest scope mismatch")
        if not (artifact_dir / "final.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append("final screenshot is not PNG")
        for name in ("crop-load.ss9", "crop-consumer.ss9", "final.ss9"):
            if (artifact_dir / name).stat().st_size < 1024:
                errors.append(f"savestate too small: {name}")
    except (KeyError, OSError, ValueError, json.JSONDecodeError, StopIteration) as error:
        errors.append(str(error))
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    return {
        "schema": "residual-wram-crop-tilemap-runtime-verification-v1",
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
        default=Path("artifacts/residual-wram-crop-tilemap-runtime-v1"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    artifact = args.artifact if args.artifact.is_absolute() else root / args.artifact
    report = verify_artifact(root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
