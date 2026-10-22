#!/usr/bin/env python3
"""Audit fixed-slot write-back capacity for every fullscreen BG resource."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77, read_lz77_record
from tools.import_bg_resources import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROM_SHA256,
    _catalog_resources,
)


ARTIFACT_ID = "bg-resource-writeback-v1"
PAYLOAD_NAME = "bg-resource-writeback.json"
IMPLEMENTATION_PATHS = (
    "tools/gba_image_export.py",
    "tools/import_bg_resources.py",
    "tools/export_bg_resource_writeback_audit.py",
    "tools/verify_bg_resource_writeback_audit.py",
    "tools/build_mod.py",
    "tools/automated_test.py",
    "tests/test_import_bg_resources.py",
    "tests/test_vram_safe_fixed_slot_audits.py",
)
MUTATION_OFFSETS = {"graphics": 0, "palette": 2, "tilemap": 0}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _mutate(role: str, content: bytes) -> tuple[bytes, dict[str, Any]]:
    mutated = bytearray(content)
    offset = MUTATION_OFFSETS[role]
    before = mutated[offset]
    mutated[offset] ^= 1
    return bytes(mutated), {
        "kind": "first_editable_unit_low_bit_toggle",
        "resource_type": role,
        "offset": offset,
        "before": before,
        "after": mutated[offset],
    }


def _resource_record(
    rom: bytes,
    row: dict[str, Any],
) -> dict[str, Any]:
    role = row["resource_type"]
    digest = row["resource_sha256"]
    content = lz77_decompress(rom, row["physical_offsets"][0])
    if _sha256_bytes(content) != digest:
        raise ValueError(f"{role}/{digest} decompressed hash mismatch")
    original_encoded = encode_gba_lz77(content)
    if lz77_decompress(original_encoded, 0) != content:
        raise ValueError(f"{role}/{digest} original round-trip mismatch")
    mutated, mutation = _mutate(role, content)
    mutation_encoded = encode_gba_lz77(mutated)
    if lz77_decompress(mutation_encoded, 0) != mutated:
        raise ValueError(f"{role}/{digest} mutation round-trip mismatch")

    slots = []
    for offset in row["physical_offsets"]:
        source = read_lz77_record(rom, offset)
        if lz77_decompress(rom, offset) != content:
            raise ValueError(f"{role}/{digest} physical alias mismatch")
        slots.append(
            {
                "file_offset": offset,
                "gba_address": f"0x{0x08000000 + offset:08X}",
                "slot_size": len(source),
                "source_compressed_sha256": _sha256_bytes(source),
                "original_reencoded_size": len(original_encoded),
                "original_slot_margin": len(source) - len(original_encoded),
                "original_roundtrip_fit": len(original_encoded) <= len(source),
                "mutation_encoded_size": len(mutation_encoded),
                "mutation_slot_margin": len(source) - len(mutation_encoded),
                "mutation_fit": len(mutation_encoded) <= len(source),
            }
        )
    return {
        "resource_type": role,
        "resource_sha256": digest,
        "decompressed_size": len(content),
        "source_files": row["source_files"],
        "logical_alias_count": len(row["logical_aliases"]),
        "logical_aliases": row["logical_aliases"],
        "physical_slot_count": len(slots),
        "physical_slots": slots,
        "original_reencoded_sha256": _sha256_bytes(original_encoded),
        "original_fit_all_aliases": all(
            slot["original_roundtrip_fit"] for slot in slots
        ),
        "mutation": mutation,
        "mutation_decompressed_sha256": _sha256_bytes(mutated),
        "mutation_encoded_sha256": _sha256_bytes(mutation_encoded),
        "mutation_fit_all_aliases": all(
            slot["mutation_fit"] for slot in slots
        ),
    }


def _build_payload(root: Path) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256(catalog_path) != CATALOG_SHA256:
        raise ValueError("BG resource catalog SHA-256 mismatch")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    grouped, _ = _catalog_resources(catalog, rom)
    resources = [_resource_record(rom, grouped[key]) for key in sorted(grouped)]
    physical_slots = sum(row["physical_slot_count"] for row in resources)
    logical_references = sum(row["logical_alias_count"] for row in resources)
    original_content_fit = sum(
        row["original_fit_all_aliases"] for row in resources
    )
    original_slot_fit = sum(
        slot["original_roundtrip_fit"]
        for row in resources
        for slot in row["physical_slots"]
    )
    mutation_content_fit = sum(
        row["mutation_fit_all_aliases"] for row in resources
    )
    mutation_slot_fit = sum(
        slot["mutation_fit"]
        for row in resources
        for slot in row["physical_slots"]
    )
    mutation_logical_fit = sum(
        row["logical_alias_count"]
        for row in resources
        if row["mutation_fit_all_aliases"]
    )
    if (
        len(resources),
        physical_slots,
        logical_references,
        original_content_fit,
        original_slot_fit,
        mutation_content_fit,
        mutation_slot_fit,
        mutation_logical_fit,
    ) != (31, 36, 36, 31, 36, 10, 10, 10):
        raise ValueError("BG write-back denominator mismatch")

    scope = {
        "all_content_resources_audited": True,
        "all_physical_slots_audited": True,
        "all_logical_references_accounted": True,
        "original_roundtrip_capacity_complete": True,
        "guarded_in_place_importer_available": True,
        "atomic_all_alias_capacity_gate": True,
        "explicit_physical_slot_targeting_available": True,
        "linked_resource_validation_complete": True,
        "deterministic_first_unit_mutation_audited": True,
        "vram_safe_encoding_audited": True,
        "arbitrary_edit_capacity_complete": False,
        "resource_relocation_complete": False,
        "pointer_rewrite_complete": False,
        "runtime_pixel_equivalence": False,
        "canvas_png_writeback_complete": False,
        "runtime_entry_selection_complete": False,
    }
    return {
        "schema": "bg-resource-writeback-audit-v1",
        "artifact_id": ARTIFACT_ID,
        "rom": {
            "path": "rom/base.gba",
            "sha256": ROM_SHA256,
            "size": len(rom),
        },
        "source_catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
            "content_resource_count": 31,
            "physical_slot_count": 36,
            "logical_reference_count": 36,
        },
        "implementation": {
            relative: _sha256(root / relative)
            for relative in IMPLEMENTATION_PATHS
        },
        "mutation_model": {
            "kind": "first_editable_unit_low_bit_toggle",
            "graphics_byte_offset": MUTATION_OFFSETS["graphics"],
            "palette_byte_offset": MUTATION_OFFSETS["palette"],
            "tilemap_byte_offset": MUTATION_OFFSETS["tilemap"],
            "purpose": "bounded capacity witness only; overflow remains fail-closed",
        },
        "resources": resources,
        "summary": {
            "content_resource_count": len(resources),
            "physical_slot_count": physical_slots,
            "logical_reference_count": logical_references,
            "original_roundtrip_fit_content_count": original_content_fit,
            "original_roundtrip_fit_slot_count": original_slot_fit,
            "mutation_fit_all_alias_content_count": mutation_content_fit,
            "mutation_overflow_content_count": len(resources) - mutation_content_fit,
            "mutation_fit_slot_count": mutation_slot_fit,
            "mutation_overflow_slot_count": physical_slots - mutation_slot_fit,
            "mutation_fit_logical_reference_count": mutation_logical_fit,
            "mutation_overflow_logical_reference_count": (
                logical_references - mutation_logical_fit
            ),
            "minimum_original_slot_margin": min(
                slot["original_slot_margin"]
                for row in resources
                for slot in row["physical_slots"]
            ),
            "minimum_mutation_slot_margin": min(
                slot["mutation_slot_margin"]
                for row in resources
                for slot in row["physical_slots"]
            ),
        },
        "scope": scope,
    }


def _prepare_output(output: Path) -> None:
    if not output.exists():
        return
    try:
        manifest = json.loads(
            (output / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"refusing to replace foreign output: {error}") from error
    if manifest.get("artifact_id") != ARTIFACT_ID:
        raise ValueError("refusing to replace foreign output directory")
    shutil.rmtree(output)


def export_bg_resource_writeback_audit(
    root: Path,
    output: Path,
) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=output.parent,
        prefix=f".{ARTIFACT_ID}-",
    ) as directory:
        temporary = Path(directory) / ARTIFACT_ID
        temporary.mkdir()
        payload = _build_payload(root)
        payload_path = temporary / PAYLOAD_NAME
        payload_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        files = {PAYLOAD_NAME: _sha256(payload_path)}
        manifest = {
            "schema": "git-artifact-promotion-v1",
            "artifact_id": ARTIFACT_ID,
            "artifact_schema": payload["schema"],
            "artifact_status": "accepted",
            "payload_file": PAYLOAD_NAME,
            "payload_sha256": files[PAYLOAD_NAME],
            "files": files,
            "scope": payload["scope"],
            "verifier": {
                "command": [
                    "python3",
                    "tools/verify_bg_resource_writeback_audit.py",
                    "--root",
                    ".",
                    "--artifact",
                    f"artifacts/{ARTIFACT_ID}",
                ],
                "exit_code": 0,
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _prepare_output(output)
        temporary.rename(output)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else args.root / args.output
    payload = export_bg_resource_writeback_audit(args.root, output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
