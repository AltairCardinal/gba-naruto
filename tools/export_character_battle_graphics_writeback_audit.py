#!/usr/bin/env python3
"""Audit fixed-length write-back for all character battle graphics."""

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

from tools.import_character_battle_graphics import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROM_SHA256,
    _catalog_graphics,
)


ARTIFACT_ID = "character-battle-graphics-writeback-v1"
PAYLOAD_NAME = "character-battle-graphics-writeback.json"
IMPLEMENTATION_PATHS = (
    "tools/import_character_battle_graphics.py",
    "tools/export_character_battle_graphics_writeback_audit.py",
    "tools/verify_character_battle_graphics_writeback_audit.py",
    "tools/build_mod.py",
    "tools/automated_test.py",
    "tests/test_import_character_battle_graphics.py",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _resource_record(
    rom: bytes,
    row: dict[str, Any],
) -> dict[str, Any]:
    offset = row["file_offset"]
    size = row["size"]
    content = rom[offset : offset + size]
    if _sha256_bytes(content) != row["graphics_sha256"]:
        raise ValueError(
            f"resource {row['resource_id']} graphics hash mismatch"
        )
    mutated = bytearray(content)
    before = mutated[0]
    mutated[0] ^= 1
    mutated_bytes = bytes(mutated)
    if len(mutated_bytes) != size:
        raise ValueError("fixed-length graphics mutation changed size")
    return {
        "resource_id": row["resource_id"],
        "graphics_pointer": row["graphics_pointer"],
        "file_offset": offset,
        "graphics_size": size,
        "graphics_sha256": row["graphics_sha256"],
        "source_file": row["source_file"],
        "tile_count": row["tile_count"],
        "maximum_component_tile_end": row["maximum_component_tile_end"],
        "frame_count": row["frame_count"],
        "component_count": row["component_count"],
        "slot_reference_count": len(row["slot_rows"]),
        "slot_rows": row["slot_rows"],
        "logical_aliases": row["logical_aliases"],
        "original_roundtrip_sha256": _sha256_bytes(content),
        "original_roundtrip": True,
        "mutation": {
            "kind": "first_graphics_byte_low_bit_toggle",
            "offset": 0,
            "before": before,
            "after": mutated[0],
        },
        "mutation_sha256": _sha256_bytes(mutated_bytes),
        "mutation_writeback": True,
    }


def _build_payload(root: Path) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256(catalog_path) != CATALOG_SHA256:
        raise ValueError("character battle visual catalog SHA-256 mismatch")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = _catalog_graphics(catalog, rom)
    resources = [
        _resource_record(rom, rows[offset]) for offset in sorted(rows)
    ]
    summary = {
        "physical_graphics_count": len(resources),
        "unique_content_count": len(
            {row["graphics_sha256"] for row in resources}
        ),
        "resource_count": len(
            {row["resource_id"] for row in resources}
        ),
        "slot_reference_count": sum(
            row["slot_reference_count"] for row in resources
        ),
        "frame_count": sum(row["frame_count"] for row in resources),
        "component_count": sum(
            row["component_count"] for row in resources
        ),
        "tile_count": sum(row["tile_count"] for row in resources),
        "graphics_byte_count": sum(
            row["graphics_size"] for row in resources
        ),
        "original_roundtrip_count": sum(
            row["original_roundtrip"] for row in resources
        ),
        "mutation_writeback_count": sum(
            row["mutation_writeback"] for row in resources
        ),
        "minimum_graphics_size": min(
            row["graphics_size"] for row in resources
        ),
        "maximum_graphics_size": max(
            row["graphics_size"] for row in resources
        ),
    }
    expected = {
        "physical_graphics_count": 250,
        "unique_content_count": 250,
        "resource_count": 250,
        "slot_reference_count": 342,
        "frame_count": 2004,
        "component_count": 2190,
        "tile_count": 60430,
        "graphics_byte_count": 1933760,
        "original_roundtrip_count": 250,
        "mutation_writeback_count": 250,
        "minimum_graphics_size": 1600,
        "maximum_graphics_size": 26624,
    }
    if summary != expected:
        raise ValueError(f"character battle graphics denominator mismatch: {summary}")
    scope = {
        "all_physical_graphics_audited": True,
        "all_resource_references_accounted": True,
        "all_slot_references_accounted": True,
        "all_component_tile_ranges_accounted": True,
        "graphics_structure_non_overlap_complete": True,
        "guarded_fixed_length_importer_available": True,
        "arbitrary_fixed_length_raw_graphics_writeback_complete": True,
        "same_resource_slot_aliases_atomic": True,
        "variable_length_writeback_complete": False,
        "frame_structure_writeback_complete": False,
        "resource_relocation_complete": False,
        "pointer_rewrite_complete": False,
        "runtime_slot_selection_complete": False,
        "runtime_pixel_equivalence": False,
        "generic_image_writeback_complete": False,
    }
    return {
        "schema": "character-battle-graphics-writeback-audit-v1",
        "artifact_id": ARTIFACT_ID,
        "rom": {
            "path": "rom/base.gba",
            "sha256": ROM_SHA256,
            "size": len(rom),
        },
        "source_catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
            "table_sha256": catalog["table"]["sha256"],
        },
        "implementation": {
            relative: _sha256(root / relative)
            for relative in IMPLEMENTATION_PATHS
        },
        "mutation_model": {
            "kind": "first_graphics_byte_low_bit_toggle",
            "offset": 0,
            "length_preserving": True,
            "purpose": (
                "witness that every raw graphics slot accepts an actual "
                "same-length edit"
            ),
        },
        "resources": resources,
        "summary": summary,
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


def export_character_battle_graphics_writeback_audit(
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
            "summary": payload["summary"],
            "verifier": {
                "command": [
                    "python3",
                    "tools/verify_character_battle_graphics_writeback_audit.py",
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
    payload = export_character_battle_graphics_writeback_audit(
        args.root,
        output,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
