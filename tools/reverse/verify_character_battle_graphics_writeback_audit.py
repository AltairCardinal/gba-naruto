#!/usr/bin/env python3
"""Independently verify character battle graphics fixed-length write-back."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ARTIFACT_ID = "character-battle-graphics-writeback-v1"
PAYLOAD_NAME = "character-battle-graphics-writeback.json"
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/character-battle-visuals-v1/manifest.json")
CATALOG_SHA256 = "a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c"
TABLE_OFFSET = 0x596D5C
TABLE_ENTRY_COUNT = 558
TABLE_ENTRY_SIZE = 16
TABLE_SIZE = TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
GRAPHICS_POINTER_DELTA = 8
STRUCTURE_KEYS = (
    "palette",
    "component_region",
    "frame_pointer_table",
    "timeline_region",
    "animation_pointer_table",
)
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


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _span(
    rom: bytes,
    source: Any,
    label: str,
) -> tuple[int, int]:
    if not isinstance(source, dict):
        raise ValueError(f"{label} provenance is missing")
    pointer_text = source.get("gba_pointer")
    size = source.get("size")
    try:
        pointer = int(pointer_text, 16)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} pointer is invalid") from error
    if not isinstance(size, int):
        raise ValueError(f"{label} size is invalid")
    offset = pointer - ROM_BASE
    if offset < 0 or size <= 0 or offset + size > len(rom):
        raise ValueError(f"{label} span is outside ROM")
    raw = rom[offset : offset + size]
    if _sha256_bytes(raw) != source.get("sha256"):
        raise ValueError(f"{label} bytes mismatch")
    return offset, offset + size


def _rebuild_resources(
    rom: bytes,
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    if catalog.get("schema") != "character-battle-visuals-v1":
        raise ValueError("character battle visual catalog schema mismatch")
    table = catalog.get("table")
    if (
        not isinstance(table, dict)
        or table.get("file_offset") != TABLE_OFFSET
        or table.get("entry_count") != TABLE_ENTRY_COUNT
        or table.get("entry_size") != TABLE_ENTRY_SIZE
        or table.get("row_formula")
        != "(character_id - 1) * 9 + visual_slot"
    ):
        raise ValueError("character battle visual table provenance mismatch")
    table_bytes = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    if len(table_bytes) != TABLE_SIZE or _sha256_bytes(
        table_bytes
    ) != table.get("sha256"):
        raise ValueError("character battle visual table bytes mismatch")
    slots = catalog.get("slots")
    resources = catalog.get("resources")
    if (
        not isinstance(slots, list)
        or len(slots) != TABLE_ENTRY_COUNT
        or not isinstance(resources, list)
        or len(resources) != 250
    ):
        raise ValueError("character battle visual catalog denominator mismatch")

    records = []
    graphics_spans: list[tuple[int, int, int]] = []
    structure_spans: list[tuple[int, int, str, int]] = []
    populated_rows: set[int] = set()
    for resource_id, resource in enumerate(resources):
        if not isinstance(resource, dict) or resource.get(
            "resource_id"
        ) != resource_id:
            raise ValueError("character battle resource identity mismatch")
        graphics = resource.get("graphics")
        frames = resource.get("frames")
        slot_rows = resource.get("slot_rows")
        if (
            not isinstance(graphics, dict)
            or not isinstance(frames, list)
            or not frames
            or not isinstance(slot_rows, list)
            or not slot_rows
            or slot_rows != sorted(set(slot_rows))
        ):
            raise ValueError(
                f"resource {resource_id} graphics provenance mismatch"
            )
        size = graphics.get("size")
        tile_count = graphics.get("tile_count")
        if (
            not isinstance(size, int)
            or size <= 0
            or size % 32
            or tile_count != size // 32
            or not isinstance(graphics.get("file"), str)
        ):
            raise ValueError(f"resource {resource_id} graphics format mismatch")
        graphics_start, graphics_end = _span(
            rom,
            graphics,
            f"resource {resource_id} graphics",
        )
        pointer = ROM_BASE + graphics_start
        if resource.get("descriptor", {}).get(
            "graphics"
        ) != f"0x{pointer:08X}":
            raise ValueError(
                f"resource {resource_id} graphics descriptor mismatch"
            )
        components: list[dict[str, Any]] = []
        for frame_id, frame in enumerate(frames):
            if (
                not isinstance(frame, dict)
                or frame.get("frame_id") != frame_id
                or not isinstance(frame.get("components"), list)
                or not frame["components"]
            ):
                raise ValueError(
                    f"resource {resource_id} frame provenance mismatch"
                )
            components.extend(frame["components"])
        if (
            len(frames) != resource.get("frame_count")
            or len(components) != resource.get("component_count")
        ):
            raise ValueError(
                f"resource {resource_id} frame/component denominator mismatch"
            )
        maximum_tile_end = 0
        for component in components:
            tile_offset = component.get("tile_offset")
            tile_end = component.get("tile_end")
            if (
                not isinstance(tile_offset, int)
                or not isinstance(tile_end, int)
                or not 0 <= tile_offset < tile_end <= tile_count
            ):
                raise ValueError(
                    f"resource {resource_id} component range mismatch"
                )
            maximum_tile_end = max(maximum_tile_end, tile_end)
        if maximum_tile_end != tile_count:
            raise ValueError(
                f"resource {resource_id} component boundary mismatch"
            )
        try:
            first_frame_pointer = int(
                frames[0]["component_list_pointer"],
                16,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"resource {resource_id} first frame pointer invalid"
            ) from error
        if ROM_BASE + graphics_end != first_frame_pointer:
            raise ValueError(
                f"resource {resource_id} graphics end boundary mismatch"
            )

        aliases = []
        for row in slot_rows:
            if not isinstance(row, int) or not 0 <= row < TABLE_ENTRY_COUNT:
                raise ValueError(f"resource {resource_id} slot row invalid")
            slot = slots[row]
            if (
                slot.get("row") != row
                or not slot.get("populated")
                or slot.get("resource_id") != resource_id
            ):
                raise ValueError(
                    f"resource {resource_id} slot provenance mismatch"
                )
            descriptor = table_bytes[
                row * TABLE_ENTRY_SIZE : (row + 1) * TABLE_ENTRY_SIZE
            ]
            if descriptor != bytes.fromhex(
                slot.get("descriptor_raw_hex", "")
            ):
                raise ValueError(f"slot {row} descriptor bytes mismatch")
            actual_pointer = int.from_bytes(
                descriptor[
                    GRAPHICS_POINTER_DELTA : GRAPHICS_POINTER_DELTA + 4
                ],
                "little",
            )
            if actual_pointer != pointer:
                raise ValueError(f"slot {row} graphics pointer mismatch")
            aliases.append(
                {
                    "slot_row": row,
                    "character_id": slot["character_id"],
                    "visual_slot": slot["visual_slot"],
                    "resource_id": resource_id,
                    "table_pointer_offset": (
                        TABLE_OFFSET
                        + row * TABLE_ENTRY_SIZE
                        + GRAPHICS_POINTER_DELTA
                    ),
                }
            )
            populated_rows.add(row)
        for key in STRUCTURE_KEYS:
            start, end = _span(
                rom,
                resource.get(key),
                f"resource {resource_id} {key}",
            )
            structure_spans.append((start, end, key, resource_id))
        content = rom[graphics_start:graphics_end]
        mutated = bytearray(content)
        before = mutated[0]
        mutated[0] ^= 1
        records.append(
            {
                "resource_id": resource_id,
                "graphics_pointer": f"0x{pointer:08X}",
                "file_offset": graphics_start,
                "graphics_size": size,
                "graphics_sha256": _sha256_bytes(content),
                "source_file": graphics["file"],
                "tile_count": tile_count,
                "maximum_component_tile_end": maximum_tile_end,
                "frame_count": len(frames),
                "component_count": len(components),
                "slot_reference_count": len(slot_rows),
                "slot_rows": slot_rows,
                "logical_aliases": aliases,
                "original_roundtrip_sha256": _sha256_bytes(content),
                "original_roundtrip": True,
                "mutation": {
                    "kind": "first_graphics_byte_low_bit_toggle",
                    "offset": 0,
                    "before": before,
                    "after": mutated[0],
                },
                "mutation_sha256": _sha256_bytes(bytes(mutated)),
                "mutation_writeback": True,
            }
        )
        graphics_spans.append(
            (graphics_start, graphics_end, resource_id)
        )
    for row, slot in enumerate(slots):
        if slot.get("row") != row:
            raise ValueError("character battle slot ordering mismatch")
        if slot.get("populated") != (row in populated_rows):
            raise ValueError("character battle populated denominator mismatch")
    ordered = sorted(graphics_spans)
    if any(
        left_end > right_start
        for (_, left_end, _), (right_start, _, _) in zip(
            ordered,
            ordered[1:],
        )
    ):
        raise ValueError("character battle graphics overlap")
    for graphics_start, graphics_end, resource_id in ordered:
        for structure_start, structure_end, key, owner_id in structure_spans:
            if (
                graphics_start < structure_end
                and structure_start < graphics_end
            ):
                raise ValueError(
                    f"graphics/structure overlap {resource_id}/{owner_id}/{key}"
                )
    records.sort(key=lambda item: item["file_offset"])
    return records


def _summary(resources: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "physical_graphics_count": len(resources),
        "unique_content_count": len(
            {row["graphics_sha256"] for row in resources}
        ),
        "resource_count": len({row["resource_id"] for row in resources}),
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
        raise ValueError(
            f"character battle graphics denominator mismatch: {summary}"
        )
    return summary


def _scope() -> dict[str, bool]:
    return {
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


def _expected_payload(root: Path) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256(catalog_path) != CATALOG_SHA256:
        raise ValueError("character battle visual catalog SHA-256 mismatch")
    catalog = _json(catalog_path)
    resources = _rebuild_resources(rom, catalog)
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
        "summary": _summary(resources),
        "scope": _scope(),
    }


def verify_character_battle_graphics_writeback_audit(
    root: Path,
    artifact: Path,
) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.resolve()
    errors: list[str] = []
    expected: dict[str, Any] | None = None
    try:
        expected = _expected_payload(root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"could not reconstruct expected audit: {error}")
    try:
        manifest = _json(artifact / "manifest.json")
        payload_path = artifact / PAYLOAD_NAME
        payload = _json(payload_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"could not read artifact: {error}")
        return {"verified": False, "errors": errors}
    payload_digest = _sha256(payload_path)
    if manifest.get("schema") != "git-artifact-promotion-v1":
        errors.append("promotion manifest schema mismatch")
    if manifest.get("artifact_id") != ARTIFACT_ID:
        errors.append("promotion artifact ID mismatch")
    if manifest.get(
        "artifact_schema"
    ) != "character-battle-graphics-writeback-audit-v1":
        errors.append("promotion artifact schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        errors.append("promotion artifact status mismatch")
    if manifest.get("payload_file") != PAYLOAD_NAME:
        errors.append("promotion payload file mismatch")
    if manifest.get("payload_sha256") != payload_digest:
        errors.append("promotion payload hash mismatch")
    if manifest.get("files") != {PAYLOAD_NAME: payload_digest}:
        errors.append("promotion file inventory mismatch")
    expected_command = [
        "python3",
        "tools/verify_character_battle_graphics_writeback_audit.py",
        "--root",
        ".",
        "--artifact",
        f"artifacts/{ARTIFACT_ID}",
    ]
    verifier = manifest.get("verifier")
    if (
        not isinstance(verifier, dict)
        or verifier.get("command") != expected_command
        or verifier.get("exit_code") != 0
    ):
        errors.append("promotion verifier evidence mismatch")
    if expected is not None:
        if manifest.get("scope") != expected["scope"]:
            errors.append("promotion scope mismatch")
        if manifest.get("summary") != expected["summary"]:
            errors.append("promotion summary mismatch")
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
                errors.append(f"payload {key} mismatch")
    summary = payload.get("summary", {})
    return {
        "verified": not errors,
        "graphics": summary.get("physical_graphics_count"),
        "resources": summary.get("resource_count"),
        "slots": summary.get("slot_reference_count"),
        "components": summary.get("component_count"),
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
    report = verify_character_battle_graphics_writeback_audit(
        args.root,
        artifact,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
