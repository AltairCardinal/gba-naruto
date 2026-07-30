#!/usr/bin/env python3
"""Independently verify the character battle palette write-back audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ARTIFACT_ID = "character-battle-palette-writeback-v1"
PAYLOAD_NAME = "character-battle-palette-writeback.json"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/character-battle-visuals-v1/manifest.json")
CATALOG_SHA256 = "a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c"
TABLE_OFFSET = 0x596D5C
TABLE_ENTRY_COUNT = 558
TABLE_ENTRY_SIZE = 16
TABLE_SIZE = TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
IMPLEMENTATION_PATHS = (
    "tools/import_character_battle_palettes.py",
    "tools/export_character_battle_palette_writeback_audit.py",
    "tools/verify_character_battle_palette_writeback_audit.py",
    "tools/build_mod.py",
    "tools/automated_test.py",
    "tests/test_import_character_battle_palettes.py",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _expected_records(
    rom: bytes,
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    table = catalog["table"]
    table_bytes = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    if (
        catalog.get("schema") != "character-battle-visuals-v1"
        or table.get("file_offset") != TABLE_OFFSET
        or table.get("entry_count") != TABLE_ENTRY_COUNT
        or table.get("entry_size") != TABLE_ENTRY_SIZE
        or _sha256_bytes(table_bytes) != table.get("sha256")
    ):
        raise ValueError("catalog table provenance mismatch")
    slots = catalog["slots"]
    resources = catalog["resources"]
    if len(slots) != 558 or len(resources) != 250:
        raise ValueError("catalog denominator mismatch")

    grouped: dict[int, dict[str, Any]] = {}
    populated: set[int] = set()
    for resource_id, resource in enumerate(resources):
        if resource.get("resource_id") != resource_id:
            raise ValueError("resource ordering mismatch")
        palette = resource["palette"]
        pointer = int(palette["gba_pointer"], 16)
        offset = pointer - 0x08000000
        raw = rom[offset : offset + 32]
        if (
            len(raw) != 32
            or palette.get("size") != 32
            or palette.get("color_count") != 16
            or _sha256_bytes(raw) != palette.get("sha256")
        ):
            raise ValueError("palette bytes mismatch")
        aliases = []
        for row in resource["slot_rows"]:
            slot = slots[row]
            descriptor = table_bytes[
                row * TABLE_ENTRY_SIZE : (row + 1) * TABLE_ENTRY_SIZE
            ]
            if (
                slot.get("row") != row
                or not slot.get("populated")
                or slot.get("resource_id") != resource_id
                or descriptor.hex() != slot.get("descriptor_raw_hex")
                or int.from_bytes(descriptor[12:16], "little") != pointer
            ):
                raise ValueError("slot/palette provenance mismatch")
            aliases.append(
                {
                    "slot_row": row,
                    "character_id": slot["character_id"],
                    "visual_slot": slot["visual_slot"],
                    "resource_id": resource_id,
                    "table_pointer_offset": TABLE_OFFSET + row * 16 + 12,
                }
            )
            populated.add(row)
        target = grouped.setdefault(
            offset,
            {
                "file_offset": offset,
                "gba_pointer": f"0x{pointer:08X}",
                "size": 32,
                "color_count": 16,
                "sha256": _sha256_bytes(raw),
                "source_files": set(),
                "resource_ids": [],
                "slot_rows": [],
                "logical_aliases": [],
            },
        )
        if target["sha256"] != _sha256_bytes(raw):
            raise ValueError("physical palette identity conflict")
        target["source_files"].add(palette["file"])
        target["resource_ids"].append(resource_id)
        target["slot_rows"].extend(resource["slot_rows"])
        target["logical_aliases"].extend(aliases)

    if len(populated) != 342:
        raise ValueError("populated slot denominator mismatch")
    spans = sorted((offset, offset + 32) for offset in grouped)
    if any(
        left_end > right_start
        for (_, left_end), (right_start, _) in zip(spans, spans[1:])
    ):
        raise ValueError("physical palette overlap")

    records = []
    for offset, row in sorted(grouped.items()):
        raw = rom[offset : offset + 32]
        mutated = bytearray(raw)
        mutated[2] ^= 1
        row["source_files"] = sorted(row["source_files"])
        row["resource_ids"] = sorted(row["resource_ids"])
        row["slot_rows"] = sorted(row["slot_rows"])
        row["logical_aliases"] = sorted(
            row["logical_aliases"],
            key=lambda item: (item["slot_row"], item["resource_id"]),
        )
        row["resource_reference_count"] = len(row["resource_ids"])
        row["slot_reference_count"] = len(row["slot_rows"])
        row["mutation"] = {
            "kind": "first_nontransparent_color_low_bit_toggle",
            "byte_offset": 2,
            "before": raw[2],
            "after": mutated[2],
            "sha256": _sha256_bytes(bytes(mutated)),
            "fixed_length_writeback": True,
        }
        records.append(row)
    if (
        len(records) != 48
        or len({row["sha256"] for row in records}) != 40
        or sum(row["resource_reference_count"] for row in records) != 250
        or sum(row["slot_reference_count"] for row in records) != 342
    ):
        raise ValueError("palette denominator mismatch")
    return records


def verify_character_battle_palette_writeback_audit(
    root: Path,
    artifact: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = root.resolve()
        artifact = artifact.resolve()
        if artifact.is_symlink():
            raise ValueError("artifact must not be a symbolic link")
        rom = (root / "rom/base.gba").read_bytes()
        if _sha256_bytes(rom) != ROM_SHA256:
            raise ValueError("base ROM SHA-256 mismatch")
        catalog_path = root / CATALOG_PATH
        if _sha256(catalog_path) != CATALOG_SHA256:
            raise ValueError("catalog SHA-256 mismatch")
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        records = _expected_records(rom, catalog)

        manifest_path = artifact / "manifest.json"
        payload_path = artifact / PAYLOAD_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_id") != ARTIFACT_ID
            or manifest.get("artifact_schema")
            != "character-battle-palette-writeback-audit-v1"
            or manifest.get("artifact_status") != "accepted"
        ):
            raise ValueError("artifact identity mismatch")
        if manifest.get("payload_file") != PAYLOAD_NAME:
            raise ValueError("payload filename mismatch")
        payload_digest = _sha256(payload_path)
        if (
            manifest.get("payload_sha256") != payload_digest
            or manifest.get("files") != {PAYLOAD_NAME: payload_digest}
        ):
            raise ValueError("payload hash mismatch")
        if set(path.name for path in artifact.iterdir()) != {
            "manifest.json",
            PAYLOAD_NAME,
        }:
            raise ValueError("artifact file set mismatch")
        if payload.get("palettes") != records:
            raise ValueError("palette records mismatch")

        summary = {
            "physical_palette_count": 48,
            "unique_content_count": 40,
            "resource_reference_count": 250,
            "slot_reference_count": 342,
            "original_roundtrip_count": 48,
            "mutation_writeback_count": 48,
        }
        scope = {
            "all_physical_palettes_audited": True,
            "all_resource_references_accounted": True,
            "all_slot_references_accounted": True,
            "guarded_fixed_length_importer_available": True,
            "arbitrary_fixed_length_palette_writeback_complete": True,
            "same_pointer_aliases_atomic": True,
            "equal_content_distinct_pointers_independent": True,
            "graphics_writeback_complete": False,
            "frame_structure_writeback_complete": False,
            "resource_relocation_complete": False,
            "pointer_rewrite_complete": False,
            "runtime_pixel_equivalence": False,
            "generic_image_writeback_complete": False,
        }
        expected_payload = {
            "schema": "character-battle-palette-writeback-audit-v1",
            "artifact_id": ARTIFACT_ID,
            "rom": {
                "path": "rom/base.gba",
                "sha256": ROM_SHA256,
                "size": len(rom),
            },
            "source_catalog": {
                "path": CATALOG_PATH.as_posix(),
                "sha256": CATALOG_SHA256,
            },
            "implementation": {
                relative: _sha256(root / relative)
                for relative in IMPLEMENTATION_PATHS
            },
            "palettes": records,
            "summary": summary,
            "scope": scope,
        }
        if payload != expected_payload:
            raise ValueError("payload semantics mismatch")
        if manifest.get("summary") != summary or manifest.get("scope") != scope:
            raise ValueError("manifest promotion mismatch")
        if manifest.get("verifier") != {
            "command": [
                "python3",
                "tools/verify_character_battle_palette_writeback_audit.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/character-battle-palette-writeback-v1",
            ],
            "exit_code": 0,
        }:
            raise ValueError("verifier evidence mismatch")
    except Exception as error:
        errors.append(str(error))
    return {
        "schema": "character-battle-palette-writeback-verification-v1",
        "verified": not errors,
        "palettes": 48 if not errors else 0,
        "resources": 250 if not errors else 0,
        "slots": 342 if not errors else 0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_character_battle_palette_writeback_audit(
        args.root,
        args.artifact,
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
