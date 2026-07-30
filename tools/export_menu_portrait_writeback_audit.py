#!/usr/bin/env python3
"""Audit fixed-slot write-back capacity for all menu/story portrait resources."""

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
from tools.import_menu_portraits import encode_gba_lz77


ARTIFACT_ID = "menu-portrait-writeback-v1"
PAYLOAD_NAME = "menu-portrait-writeback.json"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/menu-portraits-v1/manifest.json")
CATALOG_SHA256 = "cd54c20d774a2aa69c7a41db396ca344157320882602b03a00ccd83851a791b3"
IMPLEMENTATION_PATHS = (
    "tools/import_menu_portraits.py",
    "tools/export_menu_portrait_writeback_audit.py",
    "tools/verify_menu_portrait_writeback_audit.py",
    "tools/build_mod.py",
    "tests/test_import_menu_portraits.py",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _inputs(root: Path) -> tuple[bytes, dict[str, Any]]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256(catalog_path) != CATALOG_SHA256:
        raise ValueError("menu portrait catalog SHA-256 mismatch")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if (
        catalog.get("schema") != "menu-portrait-export-v1"
        or catalog.get("unique_resource_count") != 74
        or len(catalog.get("unique_resources", [])) != 74
        or catalog.get("portrait_count") != 311
    ):
        raise ValueError("menu portrait catalog denominator mismatch")
    return rom, catalog


def _resource_record(rom: bytes, source: dict[str, Any]) -> dict[str, Any]:
    resource_id = int(source["resource_id"])
    graphics_offset = int(source["gfx_file_offset"])
    palette_offset = int(source["palette_file_offset"])
    slot_size = int(source["compressed_size"])
    compressed = rom[graphics_offset : graphics_offset + slot_size]
    palette = rom[palette_offset : palette_offset + 128]
    if _sha256_bytes(compressed) != source["compressed_sha256"]:
        raise ValueError(f"resource {resource_id} compressed hash mismatch")
    if _sha256_bytes(palette) != source["palette_sha256"]:
        raise ValueError(f"resource {resource_id} palette hash mismatch")

    graphics = lz77_decompress(rom, graphics_offset)
    if len(graphics) != 6400 or _sha256_bytes(graphics) != source["decompressed_sha256"]:
        raise ValueError(f"resource {resource_id} decompressed provenance mismatch")
    reencoded = encode_gba_lz77(graphics)
    if lz77_decompress(reencoded, 0) != graphics:
        raise ValueError(f"resource {resource_id} original round-trip mismatch")

    mutated = bytearray(graphics)
    original_index = mutated[0]
    mutated[0] = (mutated[0] + 1) % 64
    mutated_bytes = bytes(mutated)
    mutation_encoded = encode_gba_lz77(mutated_bytes)
    if lz77_decompress(mutation_encoded, 0) != mutated_bytes:
        raise ValueError(f"resource {resource_id} mutation round-trip mismatch")
    fixed_slot = mutation_encoded + compressed[len(mutation_encoded) :]
    if len(fixed_slot) != slot_size:
        raise ValueError(f"resource {resource_id} mutation exceeds fixed slot")
    if lz77_decompress(fixed_slot, 0) != mutated_bytes:
        raise ValueError(f"resource {resource_id} fixed-slot decode mismatch")

    return {
        "resource_id": resource_id,
        "gfx_pointer": source["gfx_pointer"],
        "palette_pointer": source["palette_pointer"],
        "gfx_file_offset": graphics_offset,
        "palette_file_offset": palette_offset,
        "logical_alias_count": int(source["reuse_count"]),
        "slot_size": slot_size,
        "source_compressed_sha256": source["compressed_sha256"],
        "source_decompressed_sha256": source["decompressed_sha256"],
        "source_palette_sha256": source["palette_sha256"],
        "original_reencoded_size": len(reencoded),
        "original_reencoded_sha256": _sha256_bytes(reencoded),
        "original_slot_margin": slot_size - len(reencoded),
        "original_roundtrip_fit": len(reencoded) <= slot_size,
        "mutation_stream_offset": 0,
        "mutation_before_index": original_index,
        "mutation_after_index": mutated[0],
        "single_pixel_mutation_encoded_size": len(mutation_encoded),
        "single_pixel_mutation_encoded_sha256": _sha256_bytes(mutation_encoded),
        "single_pixel_mutation_decompressed_sha256": _sha256_bytes(mutated_bytes),
        "single_pixel_mutation_slot_margin": slot_size - len(mutation_encoded),
        "single_pixel_mutation_fit": len(mutation_encoded) <= slot_size,
        "fixed_slot_patch_sha256": _sha256_bytes(fixed_slot),
        "fixed_slot_decode_verified": True,
        "palette_size": len(palette),
        "palette_fixed_length_writeback": len(palette) == 128,
    }


def _build_payload(root: Path) -> dict[str, Any]:
    rom, catalog = _inputs(root)
    resources = [
        _resource_record(rom, source)
        for source in catalog["unique_resources"]
    ]
    if [row["resource_id"] for row in resources] != list(range(74)):
        raise ValueError("menu portrait resource IDs are not canonical 0..73")
    original_fit = sum(row["original_roundtrip_fit"] for row in resources)
    mutation_fit = sum(row["single_pixel_mutation_fit"] for row in resources)
    palette_fit = sum(row["palette_fixed_length_writeback"] for row in resources)
    if (original_fit, mutation_fit, palette_fit) != (74, 74, 74):
        raise ValueError("menu portrait fixed-slot denominator is incomplete")

    scope = {
        "all_unique_resources_audited": True,
        "all_logical_portrait_aliases_accounted": True,
        "original_roundtrip_capacity_complete": True,
        "single_pixel_mutation_capacity_complete": True,
        "fixed_length_palette_writeback_complete": True,
        "guarded_in_place_importer_available": True,
        "arbitrary_png_slot_fit_complete": False,
        "resource_relocation_complete": False,
        "pointer_rewrite_complete": False,
        "runtime_pixel_equivalence": False,
        "generic_image_writeback_complete": False,
    }
    return {
        "schema": "menu-portrait-writeback-audit-v1",
        "artifact_id": ARTIFACT_ID,
        "rom": {
            "path": "rom/base.gba",
            "sha256": ROM_SHA256,
            "size": len(rom),
        },
        "source_catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
            "logical_portrait_count": 311,
            "unique_resource_count": 74,
        },
        "implementation": {
            relative: _sha256(root / relative)
            for relative in IMPLEMENTATION_PATHS
        },
        "mutation_model": {
            "kind": "single_index_change",
            "decompressed_stream_offset": 0,
            "after": "(before + 1) modulo 64",
            "purpose": (
                "bounded capacity witness only; it does not prove arbitrary PNGs fit"
            ),
        },
        "resources": resources,
        "summary": {
            "resource_count": len(resources),
            "logical_portrait_count": sum(
                row["logical_alias_count"] for row in resources
            ),
            "original_roundtrip_fit_count": original_fit,
            "single_pixel_mutation_fit_count": mutation_fit,
            "palette_fixed_length_writeback_count": palette_fit,
            "minimum_original_slot_margin": min(
                row["original_slot_margin"] for row in resources
            ),
            "minimum_mutation_slot_margin": min(
                row["single_pixel_mutation_slot_margin"] for row in resources
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


def export_menu_portrait_writeback_audit(
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
                    "tools/verify_menu_portrait_writeback_audit.py",
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
    payload = export_menu_portrait_writeback_audit(args.root, output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
