#!/usr/bin/env python3
"""Independently verify the menu/story portrait fixed-slot write-back audit."""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
from typing import Any


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
    "tests/test_vram_safe_fixed_slot_audits.py",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _decompress_lz77(data: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError("invalid GBA LZ77 header")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        if cursor >= len(data):
            raise ValueError("truncated GBA LZ77 flags")
        flags = data[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(data):
                    raise ValueError("truncated GBA LZ77 reference")
                token = int.from_bytes(data[cursor : cursor + 2], "big")
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0x0FFF) + 1
                if distance > len(output):
                    raise ValueError("invalid GBA LZ77 distance")
                for _ in range(length):
                    output.append(output[-distance])
                    if len(output) >= size:
                        break
            else:
                if cursor >= len(data):
                    raise ValueError("truncated GBA LZ77 literal")
                output.append(data[cursor])
                cursor += 1
    return bytes(output)


def _encode_lz77(data: bytes) -> bytes:
    if not data or len(data) >= 1 << 24:
        raise ValueError("invalid GBA LZ77 input length")
    output = bytearray(
        (0x10, len(data) & 0xFF, (len(data) >> 8) & 0xFF, len(data) >> 16)
    )
    positions: dict[bytes, deque[int]] = {}
    cursor = 0
    while cursor < len(data):
        flag_offset = len(output)
        output.append(0)
        flags = 0
        for token_index in range(8):
            if cursor >= len(data):
                break
            best_length = 0
            best_distance = 0
            if cursor + 3 <= len(data):
                candidates = positions.get(data[cursor : cursor + 3], ())
                for previous in reversed(candidates):
                    distance = cursor - previous
                    if distance > 0x1000:
                        break
                    if distance == 1:
                        continue
                    length = 3
                    while (
                        length < 18
                        and cursor + length < len(data)
                        and data[previous + length] == data[cursor + length]
                    ):
                        length += 1
                    if length > best_length:
                        best_length = length
                        best_distance = distance
                    if length == 18:
                        break
            if best_length >= 3:
                flags |= 1 << (7 - token_index)
                token = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend((token >> 8, token & 0xFF))
                advance = best_length
            else:
                output.append(data[cursor])
                advance = 1
            for position in range(cursor, cursor + advance):
                if position + 3 > len(data):
                    continue
                key = data[position : position + 3]
                bucket = positions.setdefault(key, deque())
                bucket.append(position)
                while bucket and position - bucket[0] > 0x1000:
                    bucket.popleft()
            cursor += advance
        output[flag_offset] = flags
    return bytes(output)


def _expected_resource(rom: bytes, source: dict[str, Any]) -> dict[str, Any]:
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
    graphics = _decompress_lz77(rom, graphics_offset)
    if len(graphics) != 6400 or _sha256_bytes(graphics) != source["decompressed_sha256"]:
        raise ValueError(f"resource {resource_id} decompressed provenance mismatch")
    reencoded = _encode_lz77(graphics)
    if _decompress_lz77(reencoded, 0) != graphics:
        raise ValueError(f"resource {resource_id} original round-trip mismatch")
    mutated = bytearray(graphics)
    original_index = mutated[0]
    mutated[0] = (mutated[0] + 1) % 64
    mutated_bytes = bytes(mutated)
    mutation_encoded = _encode_lz77(mutated_bytes)
    mutation_fit = len(mutation_encoded) <= slot_size
    fixed_slot = None
    fixed_slot_decode_verified = False
    if mutation_fit:
        fixed_slot = mutation_encoded + compressed[len(mutation_encoded) :]
        if len(fixed_slot) != slot_size:
            raise ValueError(f"resource {resource_id} fixed-slot size mismatch")
        if _decompress_lz77(fixed_slot, 0) != mutated_bytes:
            raise ValueError(f"resource {resource_id} fixed-slot decode mismatch")
        fixed_slot_decode_verified = True
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
        "single_pixel_mutation_fit": mutation_fit,
        "fixed_slot_patch_sha256": (
            _sha256_bytes(fixed_slot) if fixed_slot is not None else None
        ),
        "fixed_slot_decode_verified": fixed_slot_decode_verified,
        "palette_size": len(palette),
        "palette_fixed_length_writeback": len(palette) == 128,
    }


def _expected_payload(root: Path) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256(catalog_path) != CATALOG_SHA256:
        raise ValueError("menu portrait catalog SHA-256 mismatch")
    catalog = _json(catalog_path)
    if (
        catalog.get("schema") != "menu-portrait-export-v1"
        or catalog.get("unique_resource_count") != 74
        or len(catalog.get("unique_resources", [])) != 74
        or catalog.get("portrait_count") != 311
    ):
        raise ValueError("menu portrait catalog denominator mismatch")
    resources = [
        _expected_resource(rom, source)
        for source in catalog["unique_resources"]
    ]
    if [row["resource_id"] for row in resources] != list(range(74)):
        raise ValueError("menu portrait resource IDs are not canonical 0..73")
    mutation_fit = sum(row["single_pixel_mutation_fit"] for row in resources)
    if mutation_fit != 37:
        raise ValueError("menu portrait safe fixed-slot denominator mismatch")
    scope = {
        "all_unique_resources_audited": True,
        "all_logical_portrait_aliases_accounted": True,
        "original_roundtrip_capacity_complete": True,
        "single_pixel_mutation_capacity_complete": mutation_fit == len(resources),
        "vram_safe_encoding_audited": True,
        "fixed_slot_overflow_reported": True,
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
            "original_roundtrip_fit_count": sum(
                row["original_roundtrip_fit"] for row in resources
            ),
            "single_pixel_mutation_fit_count": sum(
                row["single_pixel_mutation_fit"] for row in resources
            ),
            "palette_fixed_length_writeback_count": sum(
                row["palette_fixed_length_writeback"] for row in resources
            ),
            "minimum_original_slot_margin": min(
                row["original_slot_margin"] for row in resources
            ),
            "minimum_mutation_slot_margin": min(
                row["single_pixel_mutation_slot_margin"] for row in resources
            ),
        },
        "scope": scope,
    }


def verify_menu_portrait_writeback_audit(
    root: Path,
    artifact: Path,
) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.resolve()
    errors: list[str] = []
    resource_count = 0
    try:
        manifest = _json(artifact / "manifest.json")
        payload_path = artifact / PAYLOAD_NAME
        payload = _json(payload_path)
        if manifest.get("schema") != "git-artifact-promotion-v1":
            errors.append("promotion manifest schema mismatch")
        if manifest.get("artifact_id") != ARTIFACT_ID:
            errors.append("artifact ID mismatch")
        if manifest.get("artifact_status") != "accepted":
            errors.append("artifact is not accepted")
        actual_files = {
            path.relative_to(artifact).as_posix(): path
            for path in artifact.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != set(actual_files):
            errors.append("artifact file inventory mismatch")
            files = {}
        for relative, expected_hash in files.items():
            if relative in actual_files and _sha256(actual_files[relative]) != expected_hash:
                errors.append(f"artifact hash mismatch: {relative}")
        payload_hash = _sha256(payload_path)
        if manifest.get("payload_sha256") != payload_hash:
            errors.append("payload hash mismatch")
        expected = _expected_payload(root)
        resource_count = len(expected["resources"])
        if payload.get("resources") != expected["resources"]:
            errors.append("resource records mismatch")
        for key in (
            "schema",
            "artifact_id",
            "rom",
            "source_catalog",
            "implementation",
            "mutation_model",
            "summary",
            "scope",
        ):
            if payload.get(key) != expected[key]:
                errors.append(f"{key.replace('_', ' ')} mismatch")
        if manifest.get("scope") != expected["scope"]:
            errors.append("promotion scope mismatch")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": "menu-portrait-writeback-verification-v1",
        "verified": not errors,
        "resource_count": resource_count,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    artifact = (
        args.artifact
        if args.artifact.is_absolute()
        else args.root / args.artifact
    )
    report = verify_menu_portrait_writeback_audit(args.root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
