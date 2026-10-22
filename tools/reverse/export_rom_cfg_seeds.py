#!/usr/bin/env python3
"""Export hash-bound ARM/Thumb CFG roots from proven dispatch consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import uuid
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.verify_similar_table_candidates import INLINE_JUMP_TABLES


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-cfg-seeds-v1"
CATALOG_PATH = Path("tools/verify_similar_table_candidates.py")
CATALOG_SHA256 = "04b9bc0b0a2d0ce22e817f590c04851fa70f712136e9c362a12dcd3aea75d86b"
BOOT_MANIFEST_PATH = Path("artifacts/rom-boot-framebuffers-v1/manifest.json")
BOOT_MANIFEST_SHA256 = "ede3fa29106e8b67cc40e37746b5a44b85beddeb2750e660d5955e26d946238d"
CANONICAL_DISPATCH_SPECS = (
    {
        "id": "battle-status-action",
        "range": (0x06FF30, 0x06FFE8),
        "table_sha256": "70e8f03efa99fa88b91aa2bbb6963555c617688855d6414d597aa1cf10e7db1d",
        "consumer_range": (0x06FF10, 0x06FF24),
        "consumer_hex": "007d04382d2800d9c0e180000349401800688746",
        "evidence_path": "notes/battle-status-stage-policy-bindings-20260723.json",
        "evidence_sha256": "cc7b85b43c55a9a3af074240052ac2c00b1c18c59dc92b898427a4783e3b1b68",
        "pointer_bit0": 0,
    },
    {
        "id": "battle-effect-subtype",
        "range": (0x076F44, 0x077040),
        "table_sha256": "bb2f646887a005da8a0430da93bf5ea2268aa42ebc0200f92183f26957623958",
        "consumer_range": (0x076F24, 0x076F40),
        "consumer_hex": "f1893f20084001380a1c3e2800d98ce3800002494018006887460000",
        "evidence_path": "notes/battle-action-template-semantics-bindings-20260723.json",
        "evidence_sha256": "43b550b3fce94b3f9a335e69b1f9399f041b3d3d45afdc88770ac86de9170209",
        "pointer_bit0": 0,
    },
    {
        "id": "scene-controller",
        "range": (0x08C2FC, 0x08C350),
        "table_sha256": "5c208504bc18c720d7cbae57394572582a05298ee8485875be52c39d3abb2c39",
        "consumer_range": (0x08C2E8, 0x08C2F8),
        "consumer_hex": "142f00d9d6e0b8000149401800688746",
        "evidence_path": "artifacts/scene-visual-transition-timelines-v1/scene-visual-transition-timelines.json",
        "evidence_sha256": "24ab82165144c34b3e751c7dccb211c9bfb40b4eee5f20b9b3691119043f9e8c",
        "pointer_bit0": 0,
    },
    {
        "id": "story-opcode",
        "range": (0x0977F4, 0x0978DC),
        "table_sha256": "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d",
        "consumer_range": (0x0977D8, 0x0977F0),
        "consumer_hex": "3878392800d925e3800003494018006887460000505e0003",
        "evidence_path": "sequel/content/story/bank.json",
        "evidence_sha256": "3b1467d057b8196e376b0cba6a7abb195940afe7956fa7f482c2470ef5079b17",
        "pointer_bit0": 0,
    },
    {
        "id": "m4a-track-command",
        "range": (0x464534, 0x4645C4),
        "table_sha256": "f18662620047b0851ca5ae6d181ac3810a115870add27bb5119d0612b5f6c6a6",
        "consumer_range": (0x09A234, 0x09A24C),
        "consumer_hex": "137801b4500e05d10348824201d3900b00d0002301bc7047",
        "evidence_path": "artifacts/audio/pitch-step-evidence.json",
        "evidence_sha256": "caf9fc9d4149c07e991c859cf19d75d8086550147284c34452495607347a31b7",
        "pointer_bit0": 1,
    },
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _canonical_sha(value: object) -> str:
    return _sha(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


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
    path = _safe_file(root, relative)
    if _sha(path.read_bytes()) != expected:
        raise ValueError(f"evidence SHA-256 changed: {relative}")


def _source_record(
    *,
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


def build_cfg_seed_payload(root: Path, rom: bytes | None = None) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != 6_291_456 or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    _require_file_sha(root, CATALOG_PATH, CATALOG_SHA256)
    _require_file_sha(root, BOOT_MANIFEST_PATH, BOOT_MANIFEST_SHA256)
    boot = json.loads(_safe_file(root, BOOT_MANIFEST_PATH).read_text(encoding="utf-8"))
    if (
        boot.get("schema") != "rom-boot-framebuffers-v1"
        or boot.get("rom", {}).get("sha256") != ROM_SHA256
        or boot.get("startup_chain", {}).get("reset_vector", {}).get("target")
        != "0x080000C0"
        or boot.get("startup_chain", {}).get("irq_install", {}).get("callback")
        != "0x08000104"
        or boot.get("startup_chain", {}).get("thumb_handoff", {}).get("target")
        != "0x08060FAD"
    ):
        raise ValueError("boot CFG seed evidence changed")

    sources: list[dict[str, Any]] = []
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
            _source_record(
                identifier=identifier,
                kind="inline_thumb_mov_pc_dispatch",
                table_range=(table_start, table_end),
                table_sha256=table_sha256,
                consumer_range=(consumer_start, consumer_end),
                consumer_sha256=_sha(rom[consumer_start:consumer_end]),
                evidence_path=CATALOG_PATH.as_posix(),
                evidence_sha256=CATALOG_SHA256,
                values=values,
            )
        )

    for spec in CANONICAL_DISPATCH_SPECS:
        identifier = spec["id"]
        table_start, table_end = spec["range"]
        consumer_start, consumer_end = spec["consumer_range"]
        _require_file_sha(root, spec["evidence_path"], spec["evidence_sha256"])
        if _sha(rom[table_start:table_end]) != spec["table_sha256"]:
            raise ValueError(f"{identifier} table bytes changed")
        if rom[consumer_start:consumer_end].hex() != spec["consumer_hex"]:
            raise ValueError(f"{identifier} consumer bytes changed")
        values = [_u32(rom, offset) for offset in range(table_start, table_end, 4)]
        if any(
            (value & 1) != spec["pointer_bit0"]
            or not ROM_BASE <= (value & ~1) < ROM_BASE + len(rom)
            for value in values
        ):
            raise ValueError(f"{identifier} target domain changed")
        sources.append(
            _source_record(
                identifier=identifier,
                kind="canonical_thumb_dispatch",
                table_range=(table_start, table_end),
                table_sha256=spec["table_sha256"],
                consumer_range=(consumer_start, consumer_end),
                consumer_sha256=_sha(rom[consumer_start:consumer_end]),
                evidence_path=spec["evidence_path"],
                evidence_sha256=spec["evidence_sha256"],
                values=values,
            )
        )

    if len(sources) != 23:
        raise ValueError("CFG dispatch-source denominator changed")
    slot_refs: dict[int, list[dict[str, Any]]] = {}
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
    if len(flattened_slots) != 829 or len(slot_refs) != 261:
        raise ValueError("CFG dispatch-slot/handler denominator changed")

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
    if len(seeds) != 263:
        raise ValueError("CFG root-seed denominator changed")

    summary = {
        "dispatch_source_count": 23,
        "inline_dispatch_source_count": 18,
        "canonical_dispatch_source_count": 5,
        "raw_dispatch_slot_count": 829,
        "unique_dispatch_handler_count": 261,
        "root_seed_count": 263,
        "arm_root_seed_count": 2,
        "thumb_root_seed_count": 261,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "summary": summary,
        "source_catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
        },
        "boot_evidence": {
            "path": BOOT_MANIFEST_PATH.as_posix(),
            "sha256": BOOT_MANIFEST_SHA256,
            "derived_thumb_handoff": "0x08060FAC",
            "derived_thumb_handoff_pointer": "0x08060FAD",
        },
        "dispatch_slot_denominator_sha256": _canonical_sha(flattened_slots),
        "seed_denominator_sha256": _canonical_sha(seeds),
        "dispatch_sources": sources,
        "seeds": seeds,
        "excluded_seed_classes": [
            "unbound_thumb_code_pointer_pool",
            "map_sprite_callback_pointer_pair",
            "unclassified_code_handler_pointer_table",
            "untyped_resource_or_data_pointer_tables",
        ],
        "scope": {
            "enumerated_proven_dispatch_root_denominator_complete": True,
            "global_dispatch_source_denominator_complete": False,
            "global_function_entry_denominator_complete": False,
            "independent_source_discovery_performed": False,
            "unbound_pointer_pools_excluded": True,
            "cfg_traversal_performed": False,
        },
    }


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha((root / "tools/export_rom_cfg_seeds.py").read_bytes()),
        "verifier_sha256": _sha((root / "tools/verify_rom_cfg_seeds.py").read_bytes()),
        "test_sha256": _sha((root / "tests/test_export_rom_cfg_seeds.py").read_bytes()),
    }


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    if requested.is_symlink():
        raise ValueError("CFG seed output directory must not be a symlink")
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("CFG seed output cannot be repository root or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("CFG seed output is not a directory")
    members = list(target.iterdir())
    if not members:
        return target
    expected = {"manifest.json", "rom-cfg-seeds.json"}
    if (
        any(member.is_symlink() or not member.is_file() for member in members)
        or {member.name for member in members} != expected
    ):
        raise ValueError("existing directory is not a replaceable CFG seed artifact")
    try:
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        payload = target / "rom-cfg-seeds.json"
        record = manifest["files"][payload.name]
    except (OSError, KeyError, json.JSONDecodeError, TypeError) as error:
        raise ValueError("existing directory is not a replaceable CFG seed artifact") from error
    if (
        manifest.get("artifact_schema") != SCHEMA
        or set(manifest.get("files", {})) != {payload.name}
        or record.get("size") != payload.stat().st_size
        or record.get("sha256") != _sha(payload.read_bytes())
    ):
        raise ValueError("existing directory is not a replaceable CFG seed artifact")
    return target


def _replace_output_dir(output_dir: Path, temporary: Path) -> None:
    backup: Path | None = None
    try:
        if output_dir.exists():
            backup = output_dir.with_name(
                f".{output_dir.name}.backup-{uuid.uuid4().hex}"
            )
            os.replace(output_dir, backup)
        os.replace(temporary, output_dir)
    except Exception:
        if backup is not None and backup.exists() and not output_dir.exists():
            os.replace(backup, output_dir)
        raise
    else:
        if backup is not None:
            shutil.rmtree(backup)


def export_rom_cfg_seeds(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output_dir = _validate_output_dir(root, output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    payload = build_cfg_seed_payload(root)
    temporary = Path(tempfile.mkdtemp(prefix=".rom-cfg-seeds-", dir=output_dir.parent))
    try:
        payload_path = temporary / "rom-cfg-seeds.json"
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "artifact_schema": SCHEMA,
            "rom": payload["rom"],
            "summary": payload["summary"],
            "files": {
                "rom-cfg-seeds.json": {
                    "size": payload_path.stat().st_size,
                    "sha256": _sha(payload_path.read_bytes()),
                }
            },
            "implementation": _implementation(root),
            "scope": payload["scope"],
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _replace_output_dir(output_dir, temporary)
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/rom-cfg-seeds-v1")
    )
    args = parser.parse_args()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = args.root / output_dir
    manifest = export_rom_cfg_seeds(args.root, output_dir)
    print(json.dumps(manifest["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
