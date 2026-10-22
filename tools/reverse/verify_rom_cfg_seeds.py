#!/usr/bin/env python3
"""Independently verify the fixed ARM/Thumb CFG seed denominator."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.verify_similar_table_candidates import INLINE_JUMP_TABLES


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-cfg-seeds-v1"
VERIFY_SCHEMA = "rom-cfg-seeds-verification-v1"
CATALOG_PATH = Path("tools/verify_similar_table_candidates.py")
CATALOG_SHA256 = "04b9bc0b0a2d0ce22e817f590c04851fa70f712136e9c362a12dcd3aea75d86b"
BOOT_MANIFEST_PATH = Path("artifacts/rom-boot-framebuffers-v1/manifest.json")
BOOT_MANIFEST_SHA256 = "ede3fa29106e8b67cc40e37746b5a44b85beddeb2750e660d5955e26d946238d"
CANONICAL_DISPATCH_SPECS = (
    ("battle-status-action", 0x06FF30, 0x06FFE8, "70e8f03efa99fa88b91aa2bbb6963555c617688855d6414d597aa1cf10e7db1d", 0x06FF10, 0x06FF24, "007d04382d2800d9c0e180000349401800688746", "notes/battle-status-stage-policy-bindings-20260723.json", "cc7b85b43c55a9a3af074240052ac2c00b1c18c59dc92b898427a4783e3b1b68", 0),
    ("battle-effect-subtype", 0x076F44, 0x077040, "bb2f646887a005da8a0430da93bf5ea2268aa42ebc0200f92183f26957623958", 0x076F24, 0x076F40, "f1893f20084001380a1c3e2800d98ce3800002494018006887460000", "notes/battle-action-template-semantics-bindings-20260723.json", "43b550b3fce94b3f9a335e69b1f9399f041b3d3d45afdc88770ac86de9170209", 0),
    ("scene-controller", 0x08C2FC, 0x08C350, "5c208504bc18c720d7cbae57394572582a05298ee8485875be52c39d3abb2c39", 0x08C2E8, 0x08C2F8, "142f00d9d6e0b8000149401800688746", "artifacts/scene-visual-transition-timelines-v1/scene-visual-transition-timelines.json", "24ab82165144c34b3e751c7dccb211c9bfb40b4eee5f20b9b3691119043f9e8c", 0),
    ("story-opcode", 0x0977F4, 0x0978DC, "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d", 0x0977D8, 0x0977F0, "3878392800d925e3800003494018006887460000505e0003", "sequel/content/story/bank.json", "3b1467d057b8196e376b0cba6a7abb195940afe7956fa7f482c2470ef5079b17", 0),
    ("m4a-track-command", 0x464534, 0x4645C4, "f18662620047b0851ca5ae6d181ac3810a115870add27bb5119d0612b5f6c6a6", 0x09A234, 0x09A24C, "137801b4500e05d10348824201d3900b00d0002301bc7047", "artifacts/audio/pitch-step-evidence.json", "caf9fc9d4149c07e991c859cf19d75d8086550147284c34452495607347a31b7", 1),
)
EXPECTED_SCOPE = {
    "enumerated_proven_dispatch_root_denominator_complete": True,
    "global_dispatch_source_denominator_complete": False,
    "global_function_entry_denominator_complete": False,
    "independent_source_discovery_performed": False,
    "unbound_pointer_pools_excluded": True,
    "cfg_traversal_performed": False,
}
EXPECTED_EXCLUSIONS = [
    "unbound_thumb_code_pointer_pool",
    "map_sprite_callback_pointer_pair",
    "unclassified_code_handler_pointer_table",
    "untyped_resource_or_data_pointer_tables",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value: object) -> str:
    return _sha(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _safe_file(root: Path, relative: str | Path) -> Path:
    path = root / relative
    resolved = path.resolve(strict=True)
    if resolved != path.absolute() or not resolved.is_file():
        raise ValueError(f"evidence path is missing or uses a symlink: {relative}")
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"evidence path escapes repository: {relative}") from error
    return resolved


def _require_file_sha(root: Path, relative: str | Path, expected: str) -> None:
    if _sha(_safe_file(root, relative).read_bytes()) != expected:
        raise ValueError(f"evidence SHA-256 changed: {relative}")


def _record(
    identifier: str,
    kind: str,
    table_range: tuple[int, int],
    table_sha256: str,
    consumer_range: tuple[int, int],
    consumer_sha256: str,
    evidence_path: str,
    evidence_sha256: str,
    values: list[int],
) -> dict[str, Any]:
    normalized = [value & ~1 for value in values]
    return {
        "id": identifier,
        "kind": kind,
        "table_range": list(table_range),
        "gba_table_range": [
            f"0x{ROM_BASE + table_range[0]:08X}",
            f"0x{ROM_BASE + table_range[1]:08X}",
        ],
        "table_sha256": table_sha256,
        "consumer_range": list(consumer_range),
        "consumer_sha256": consumer_sha256,
        "evidence_path": evidence_path,
        "evidence_sha256": evidence_sha256,
        "slot_count": len(values),
        "unique_target_count": len(set(normalized)),
        "raw_pointer_bit0_values": sorted({value & 1 for value in values}),
        "targets_sha256": _canonical_sha(normalized),
        "targets": [
            {
                "slot_index": index,
                "raw_pointer": f"0x{value:08X}",
                "file_offset": (value & ~1) - ROM_BASE,
                "mode": "thumb",
            }
            for index, value in enumerate(values)
        ],
    }


def rebuild_cfg_seeds(root: Path, rom: bytes) -> dict[str, Any]:
    """Rebuild sources/seeds without importing the exporter."""

    root = Path(root).resolve(strict=True)
    if len(rom) != 6_291_456:
        raise ValueError("base ROM size changed")
    _require_file_sha(root, CATALOG_PATH, CATALOG_SHA256)
    _require_file_sha(root, BOOT_MANIFEST_PATH, BOOT_MANIFEST_SHA256)
    boot = json.loads(_safe_file(root, BOOT_MANIFEST_PATH).read_text(encoding="utf-8"))
    if (
        boot.get("schema") != "rom-boot-framebuffers-v1"
        or boot.get("rom", {}).get("sha256") != ROM_SHA256
        or boot.get("startup_chain", {}).get("irq_install", {}).get("callback")
        != "0x08000104"
        or boot.get("startup_chain", {}).get("thumb_handoff", {}).get("target")
        != "0x08060FAD"
    ):
        raise ValueError("boot CFG seed evidence changed")

    sources = []
    for record in INLINE_JUMP_TABLES:
        (
            candidate_id,
            prefix_start,
            table_start,
            table_end,
            prefix_sha256,
            table_sha256,
            base_literal_offset,
            consumer_start,
            consumer_end,
            consumer_hex,
        ) = record
        identifier = f"inline-{candidate_id:02d}"
        if _sha(rom[prefix_start:table_start]) != prefix_sha256:
            raise ValueError(f"{identifier} prefix bytes changed")
        if _sha(rom[table_start:table_end]) != table_sha256:
            raise ValueError(f"{identifier} table bytes changed")
        if rom[consumer_start:consumer_end].hex() != consumer_hex:
            raise ValueError(f"{identifier} consumer bytes changed")
        if _u32(rom, base_literal_offset) != ROM_BASE + table_start:
            raise ValueError(f"{identifier} table literal changed")
        values = [_u32(rom, offset) for offset in range(table_start, table_end, 4)]
        if any(value & 1 or not ROM_BASE <= value < ROM_BASE + len(rom) for value in values):
            raise ValueError(f"{identifier} target domain changed")
        sources.append(
            _record(
                identifier,
                "inline_thumb_mov_pc_dispatch",
                (table_start, table_end),
                table_sha256,
                (consumer_start, consumer_end),
                _sha(rom[consumer_start:consumer_end]),
                CATALOG_PATH.as_posix(),
                CATALOG_SHA256,
                values,
            )
        )

    for spec in CANONICAL_DISPATCH_SPECS:
        (
            identifier,
            table_start,
            table_end,
            table_sha256,
            consumer_start,
            consumer_end,
            consumer_hex,
            evidence_path,
            evidence_sha256,
            pointer_bit0,
        ) = spec
        _require_file_sha(root, evidence_path, evidence_sha256)
        if _sha(rom[table_start:table_end]) != table_sha256:
            raise ValueError(f"{identifier} table bytes changed")
        if rom[consumer_start:consumer_end].hex() != consumer_hex:
            raise ValueError(f"{identifier} consumer bytes changed")
        values = [_u32(rom, offset) for offset in range(table_start, table_end, 4)]
        if any(
            (value & 1) != pointer_bit0
            or not ROM_BASE <= (value & ~1) < ROM_BASE + len(rom)
            for value in values
        ):
            raise ValueError(f"{identifier} target domain changed")
        sources.append(
            _record(
                identifier,
                "canonical_thumb_dispatch",
                (table_start, table_end),
                table_sha256,
                (consumer_start, consumer_end),
                _sha(rom[consumer_start:consumer_end]),
                evidence_path,
                evidence_sha256,
                values,
            )
        )

    slot_refs: dict[int, list[dict[str, int | str]]] = {}
    flattened_slots = []
    for source in sources:
        for target in source["targets"]:
            offset = target["file_offset"]
            ref = {"source_id": source["id"], "slot_index": target["slot_index"]}
            slot_refs.setdefault(offset, []).append(ref)
            flattened_slots.append(
                {
                    **ref,
                    "raw_pointer": target["raw_pointer"],
                    "file_offset": offset,
                }
            )
    if len(sources) != 23 or len(flattened_slots) != 829 or len(slot_refs) != 261:
        raise ValueError("CFG source/slot/handler denominator changed")

    seeds = []
    for offset, source_id in ((0x000000, "boot-reset-vector"), (0x000104, "boot-irq-callback")):
        seeds.append(
            {
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "mode": "arm",
                "entry_size": 4,
                "entry_sha256": _sha(rom[offset : offset + 4]),
                "sources": [{"source_id": source_id}],
            }
        )
    for offset in sorted(slot_refs):
        if offset & 1:
            raise ValueError("Thumb CFG seed alignment changed")
        seeds.append(
            {
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "mode": "thumb",
                "entry_size": 4,
                "entry_sha256": _sha(rom[offset : offset + 4]),
                "sources": slot_refs[offset],
            }
        )
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    return {
        "sources": sources,
        "seeds": seeds,
        "flattened_slots": flattened_slots,
        "summary": {
            "dispatch_source_count": 23,
            "inline_dispatch_source_count": 18,
            "canonical_dispatch_source_count": 5,
            "raw_dispatch_slot_count": 829,
            "unique_dispatch_handler_count": 261,
            "root_seed_count": 263,
            "arm_root_seed_count": 2,
            "thumb_root_seed_count": 261,
        },
    }


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha((root / "tools/export_rom_cfg_seeds.py").read_bytes()),
        "verifier_sha256": _sha((root / "tools/verify_rom_cfg_seeds.py").read_bytes()),
        "test_sha256": _sha((root / "tests/test_export_rom_cfg_seeds.py").read_bytes()),
    }


def verify_rom_cfg_seeds(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = Path(root).resolve(strict=True)
        artifact_dir = Path(artifact_dir).resolve(strict=True)
        try:
            artifact_dir.relative_to(root)
        except ValueError:
            pass
        if any(path.is_symlink() for path in artifact_dir.iterdir()):
            raise ValueError("CFG seed artifact contains a symlink")
        if {path.name for path in artifact_dir.iterdir() if path.is_file()} != {
            "manifest.json",
            "rom-cfg-seeds.json",
        }:
            raise ValueError("CFG seed artifact file set changed")

        payload_path = artifact_dir / "rom-cfg-seeds.json"
        payload_raw = payload_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
        rom = _safe_file(root, ROM_PATH).read_bytes()
        rebuilt = rebuild_cfg_seeds(root, rom)

        expected_payload = {
            "schema": SCHEMA,
            "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
            "summary": rebuilt["summary"],
            "source_catalog": {"path": CATALOG_PATH.as_posix(), "sha256": CATALOG_SHA256},
            "boot_evidence": {
                "path": BOOT_MANIFEST_PATH.as_posix(),
                "sha256": BOOT_MANIFEST_SHA256,
                "derived_thumb_handoff": "0x08060FAC",
                "derived_thumb_handoff_pointer": "0x08060FAD",
            },
            "dispatch_slot_denominator_sha256": _canonical_sha(rebuilt["flattened_slots"]),
            "seed_denominator_sha256": _canonical_sha(rebuilt["seeds"]),
            "dispatch_sources": rebuilt["sources"],
            "seeds": rebuilt["seeds"],
            "excluded_seed_classes": EXPECTED_EXCLUSIONS,
            "scope": EXPECTED_SCOPE,
        }
        if payload != expected_payload:
            raise ValueError("CFG seed payload differs from independent reconstruction")
        expected_manifest = {
            "artifact_schema": SCHEMA,
            "rom": expected_payload["rom"],
            "summary": rebuilt["summary"],
            "files": {
                "rom-cfg-seeds.json": {
                    "size": len(payload_raw),
                    "sha256": _sha(payload_raw),
                }
            },
            "implementation": _implementation(root),
            "scope": EXPECTED_SCOPE,
        }
        if manifest != expected_manifest:
            raise ValueError("CFG seed manifest differs from independent reconstruction")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, struct.error) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "dispatch_source_count": 23 if not errors else 0,
        "raw_dispatch_slot_count": 829 if not errors else 0,
        "root_seed_count": 263 if not errors else 0,
        "arm_root_seed_count": 2 if not errors else 0,
        "thumb_root_seed_count": 261 if not errors else 0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path("artifacts/rom-cfg-seeds-v1")
    )
    args = parser.parse_args()
    artifact_dir = args.artifact_dir
    if not artifact_dir.is_absolute():
        artifact_dir = args.root / artifact_dir
    report = verify_rom_cfg_seeds(args.root, artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
