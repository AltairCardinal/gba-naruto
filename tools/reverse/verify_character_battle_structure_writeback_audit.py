#!/usr/bin/env python3
"""Independently verify character battle same-layout structure write-back."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


ARTIFACT_ID = "character-battle-structure-writeback-v1"
PAYLOAD_NAME = "character-battle-structure-writeback.json"
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/character-battle-visuals-v1/manifest.json")
CATALOG_SHA256 = "a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c"
TABLE_OFFSET = 0x596D5C
TABLE_ENTRY_COUNT = 558
TABLE_ENTRY_SIZE = 16
TABLE_SIZE = TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
COMPONENT_SIZE = 20
KEYFRAME_SIZE = 4
NORMAL_TRAILER = bytes.fromhex("ffff0000")
ANOMALOUS_TRAILER = bytes.fromhex("fffb0000")
ANOMALOUS_TRAILER_OFFSET = 0x25A8E4
SUPPORTED_SIZES = {
    (8, 8),
    (16, 16),
    (32, 32),
    (64, 64),
    (16, 8),
    (32, 8),
    (32, 16),
    (64, 32),
    (8, 16),
    (8, 32),
    (16, 32),
    (32, 64),
}
IMPLEMENTATION_PATHS = (
    "tools/import_character_battle_structures.py",
    "tools/export_character_battle_structure_writeback_audit.py",
    "tools/verify_character_battle_structure_writeback_audit.py",
    "tools/build_mod.py",
    "tools/automated_test.py",
    "tests/test_import_character_battle_structures.py",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _source(
    rom: bytes,
    source: Any,
    label: str,
) -> tuple[int, bytes]:
    if not isinstance(source, dict):
        raise ValueError(f"{label} provenance is missing")
    try:
        pointer = int(source.get("gba_pointer"), 16)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} pointer is invalid") from error
    size = source.get("size")
    if not isinstance(size, int) or size <= 0:
        raise ValueError(f"{label} size is invalid")
    offset = pointer - ROM_BASE
    if offset < 0 or offset + size > len(rom):
        raise ValueError(f"{label} span is outside ROM")
    raw = rom[offset : offset + size]
    if _sha256_bytes(raw) != source.get("sha256"):
        raise ValueError(f"{label} bytes mismatch")
    return offset, raw


def _component_values(
    raw: bytes,
    expected: dict[str, Any],
    tile_count: int,
    label: str,
) -> dict[str, Any]:
    if len(raw) != COMPONENT_SIZE:
        raise ValueError(f"{label} record size mismatch")
    (
        tile_offset,
        orientation,
        angle,
        x,
        y,
        width,
        height,
        scale_x,
        scale_y,
        control,
        attribute,
        reserved,
    ) = struct.unpack("<HBBhhHHHHBBH", raw)
    tile_end = tile_offset + (width // 8) * (height // 8)
    if (
        tile_offset >> 10
        or orientation & ~3
        or angle
        or scale_x != 0x100
        or scale_y != 0x100
        or control != 0xFF
        or attribute
        or reserved
        or (width, height) not in SUPPORTED_SIZES
        or tile_end > tile_count
    ):
        raise ValueError(f"{label} semantic bounds mismatch")
    fields = {
        "tile_index_raw": tile_offset,
        "tile_offset": tile_offset,
        "orientation": orientation,
        "horizontal_flip": bool(orientation & 1),
        "vertical_flip": bool(orientation & 2),
        "affine_angle_offset": angle,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "control": control,
        "attribute": attribute,
        "reserved": reserved,
        "tile_end": tile_end,
        "raw_hex": raw.hex(),
        "raw_sha256": _sha256_bytes(raw),
    }
    if any(expected.get(key) != value for key, value in fields.items()):
        raise ValueError(f"{label} catalog fields mismatch")
    return fields


def _encode_component(values: dict[str, Any], orientation: int) -> bytes:
    return struct.pack(
        "<HBBhhHHHHBBH",
        values["tile_offset"],
        orientation,
        0,
        values["x"],
        values["y"],
        values["width"],
        values["height"],
        0x100,
        0x100,
        0xFF,
        0,
        0,
    )


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
    ):
        raise ValueError("character battle table provenance mismatch")
    table_bytes = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    if len(table_bytes) != TABLE_SIZE or _sha256_bytes(
        table_bytes
    ) != table.get("sha256"):
        raise ValueError("character battle table bytes mismatch")
    slots = catalog.get("slots")
    resources = catalog.get("resources")
    if (
        not isinstance(slots, list)
        or len(slots) != TABLE_ENTRY_COUNT
        or not isinstance(resources, list)
        or len(resources) != 250
    ):
        raise ValueError("character battle structure denominator mismatch")

    records = []
    populated_rows: set[int] = set()
    editable_spans: list[tuple[int, int]] = []
    for resource_id, resource in enumerate(resources):
        if not isinstance(resource, dict) or resource.get(
            "resource_id"
        ) != resource_id:
            raise ValueError("character battle resource identity mismatch")
        frames = resource.get("frames")
        animations = resource.get("animations")
        slot_rows = resource.get("slot_rows")
        if (
            not isinstance(frames, list)
            or not frames
            or not isinstance(animations, list)
            or not animations
            or not isinstance(slot_rows, list)
            or not slot_rows
        ):
            raise ValueError(
                f"resource {resource_id} structure provenance mismatch"
            )
        component_offset, component_region = _source(
            rom,
            resource.get("component_region"),
            f"resource {resource_id} component region",
        )
        frame_table_offset, frame_table = _source(
            rom,
            resource.get("frame_pointer_table"),
            f"resource {resource_id} frame table",
        )
        timeline_offset, timeline = _source(
            rom,
            resource.get("timeline_region"),
            f"resource {resource_id} timeline",
        )
        animation_table_offset, animation_table = _source(
            rom,
            resource.get("animation_pointer_table"),
            f"resource {resource_id} animation table",
        )
        if (
            component_offset + len(component_region) != frame_table_offset
            or timeline_offset + len(timeline) != animation_table_offset
            or len(frame_table) != len(frames) * 4
            or len(animation_table) != len(animations) * 4
        ):
            raise ValueError(
                f"resource {resource_id} structure boundary mismatch"
            )
        frame_pointers = struct.unpack(f"<{len(frames)}I", frame_table)
        animation_pointers = struct.unpack(
            f"<{len(animations)}I",
            animation_table,
        )
        component_evidence = []
        anomaly_count = 0
        component_count = 0
        tile_count = resource["graphics"]["tile_count"]
        for frame_id, frame in enumerate(frames):
            if (
                frame.get("frame_id") != frame_id
                or frame.get("component_count")
                != len(frame.get("components", []))
                or not frame.get("components")
            ):
                raise ValueError(
                    f"resource {resource_id} frame identity mismatch"
                )
            pointer = frame_pointers[frame_id]
            if frame.get("component_list_pointer") != f"0x{pointer:08X}":
                raise ValueError(
                    f"resource {resource_id} frame pointer mismatch"
                )
            end = (
                frame_pointers[frame_id + 1]
                if frame_id + 1 < len(frame_pointers)
                else ROM_BASE + frame_table_offset
            )
            size = end - pointer
            if (
                size != len(frame["components"]) * COMPONENT_SIZE + 4
                or frame.get("raw_size") != size
            ):
                raise ValueError(
                    f"resource {resource_id} frame span mismatch"
                )
            offset = pointer - ROM_BASE
            raw = rom[offset : offset + size]
            if _sha256_bytes(raw) != frame.get("raw_sha256"):
                raise ValueError(
                    f"resource {resource_id} frame bytes mismatch"
                )
            trailer = raw[-4:]
            if trailer.hex() != frame.get("frame_trailer_raw_hex"):
                raise ValueError(
                    f"resource {resource_id} trailer catalog mismatch"
                )
            if trailer == ANOMALOUS_TRAILER:
                if offset + size - 4 != ANOMALOUS_TRAILER_OFFSET:
                    raise ValueError("unexpected anomalous trailer")
                anomaly_count += 1
            elif trailer != NORMAL_TRAILER:
                raise ValueError("unknown component trailer")
            for component_index, expected_component in enumerate(
                frame["components"]
            ):
                record_offset = offset + component_index * COMPONENT_SIZE
                source_raw = rom[
                    record_offset : record_offset + COMPONENT_SIZE
                ]
                values = _component_values(
                    source_raw,
                    expected_component,
                    tile_count,
                    (
                        f"resource {resource_id} frame {frame_id} "
                        f"component {component_index}"
                    ),
                )
                roundtrip = _encode_component(
                    values,
                    values["orientation"],
                )
                mutation = _encode_component(
                    values,
                    values["orientation"] ^ 1,
                )
                if roundtrip != source_raw or mutation == source_raw:
                    raise ValueError("component round-trip/mutation mismatch")
                component_evidence.append(
                    {
                        "frame_id": frame_id,
                        "component_index": component_index,
                        "file_offset": record_offset,
                        "source_sha256": _sha256_bytes(source_raw),
                        "roundtrip_sha256": _sha256_bytes(roundtrip),
                        "mutation_sha256": _sha256_bytes(mutation),
                        "source_tile_end": values["tile_end"],
                        "mutation_tile_end": values["tile_end"],
                    }
                )
                editable_spans.append(
                    (record_offset, record_offset + COMPONENT_SIZE)
                )
                component_count += 1

        keyframe_evidence = []
        keyframe_count = 0
        for animation_id, animation in enumerate(animations):
            if (
                animation.get("animation_id") != animation_id
                or animation.get("keyframe_count")
                != len(animation.get("keyframes", []))
                or not animation.get("keyframes")
            ):
                raise ValueError(
                    f"resource {resource_id} animation identity mismatch"
                )
            pointer = animation_pointers[animation_id]
            if animation.get("timeline_pointer") != f"0x{pointer:08X}":
                raise ValueError(
                    f"resource {resource_id} animation pointer mismatch"
                )
            end = (
                animation_pointers[animation_id + 1]
                if animation_id + 1 < len(animation_pointers)
                else ROM_BASE + animation_table_offset
            )
            size = end - pointer
            if (
                size
                != (len(animation["keyframes"]) + 1) * KEYFRAME_SIZE
                or animation.get("raw_size") != size
            ):
                raise ValueError(
                    f"resource {resource_id} animation span mismatch"
                )
            offset = pointer - ROM_BASE
            raw = rom[offset : offset + size]
            if (
                _sha256_bytes(raw) != animation.get("raw_sha256")
                or raw[-4:] != NORMAL_TRAILER
            ):
                raise ValueError(
                    f"resource {resource_id} animation bytes mismatch"
                )
            for keyframe_index, expected_keyframe in enumerate(
                animation["keyframes"]
            ):
                record_offset = offset + keyframe_index * KEYFRAME_SIZE
                source_raw = rom[
                    record_offset : record_offset + KEYFRAME_SIZE
                ]
                frame_id_value, hold_frames = struct.unpack(
                    "<HH",
                    source_raw,
                )
                if (
                    frame_id_value != expected_keyframe.get("frame_id")
                    or hold_frames != expected_keyframe.get("hold_frames")
                    or frame_id_value >= len(frames)
                    or hold_frames == 0
                ):
                    raise ValueError(
                        f"resource {resource_id} keyframe mismatch"
                    )
                roundtrip = struct.pack(
                    "<HH",
                    frame_id_value,
                    hold_frames,
                )
                new_hold = (
                    hold_frames + 1
                    if hold_frames < 0xFFFF
                    else hold_frames - 1
                )
                mutation = struct.pack(
                    "<HH",
                    frame_id_value,
                    new_hold,
                )
                if roundtrip != source_raw or mutation == source_raw:
                    raise ValueError("keyframe round-trip/mutation mismatch")
                keyframe_evidence.append(
                    {
                        "animation_id": animation_id,
                        "keyframe_index": keyframe_index,
                        "file_offset": record_offset,
                        "source_sha256": _sha256_bytes(source_raw),
                        "roundtrip_sha256": _sha256_bytes(roundtrip),
                        "mutation_sha256": _sha256_bytes(mutation),
                        "mutation_frame_id": frame_id_value,
                        "mutation_hold_frames": new_hold,
                    }
                )
                editable_spans.append(
                    (record_offset, record_offset + KEYFRAME_SIZE)
                )
                keyframe_count += 1

        aliases = []
        for slot_row in slot_rows:
            slot = slots[slot_row]
            if (
                slot.get("row") != slot_row
                or not slot.get("populated")
                or slot.get("resource_id") != resource_id
            ):
                raise ValueError(
                    f"resource {resource_id} slot provenance mismatch"
                )
            descriptor = table_bytes[
                slot_row * TABLE_ENTRY_SIZE :
                (slot_row + 1) * TABLE_ENTRY_SIZE
            ]
            if descriptor != bytes.fromhex(
                slot.get("descriptor_raw_hex", "")
            ):
                raise ValueError(f"slot {slot_row} descriptor mismatch")
            aliases.append(
                {
                    "slot_row": slot_row,
                    "character_id": slot["character_id"],
                    "visual_slot": slot["visual_slot"],
                    "resource_id": resource_id,
                }
            )
            populated_rows.add(slot_row)
        records.append(
            {
                "resource_id": resource_id,
                "component_region": {
                    key: resource["component_region"][key]
                    for key in ("gba_pointer", "size", "sha256")
                },
                "frame_pointer_table": {
                    key: resource["frame_pointer_table"][key]
                    for key in ("gba_pointer", "size", "sha256")
                },
                "timeline_region": {
                    key: resource["timeline_region"][key]
                    for key in ("gba_pointer", "size", "sha256")
                },
                "animation_pointer_table": {
                    key: resource["animation_pointer_table"][key]
                    for key in ("gba_pointer", "size", "sha256")
                },
                "frame_count": len(frames),
                "component_count": component_count,
                "animation_count": len(animations),
                "keyframe_count": keyframe_count,
                "tile_count": tile_count,
                "slot_reference_count": len(slot_rows),
                "slot_rows": slot_rows,
                "logical_aliases": aliases,
                "anomalous_trailer_count": anomaly_count,
                "component_roundtrip_count": component_count,
                "component_mutation_count": component_count,
                "component_evidence_sha256": _canonical_sha256(
                    component_evidence
                ),
                "keyframe_roundtrip_count": keyframe_count,
                "keyframe_mutation_count": keyframe_count,
                "keyframe_evidence_sha256": _canonical_sha256(
                    keyframe_evidence
                ),
            }
        )
    for slot_row, slot in enumerate(slots):
        if slot.get("row") != slot_row:
            raise ValueError("character battle slot ordering mismatch")
        if slot.get("populated") != (slot_row in populated_rows):
            raise ValueError("character battle populated denominator mismatch")
    spans = sorted(editable_spans)
    if any(
        left_end > right_start
        for (_, left_end), (right_start, _) in zip(spans, spans[1:])
    ):
        raise ValueError("editable structure spans overlap")
    return records


def _summary(resources: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "resource_count": len(resources),
        "slot_reference_count": sum(
            row["slot_reference_count"] for row in resources
        ),
        "frame_count": sum(row["frame_count"] for row in resources),
        "component_count": sum(
            row["component_count"] for row in resources
        ),
        "animation_count": sum(
            row["animation_count"] for row in resources
        ),
        "keyframe_count": sum(
            row["keyframe_count"] for row in resources
        ),
        "component_roundtrip_count": sum(
            row["component_roundtrip_count"] for row in resources
        ),
        "component_mutation_count": sum(
            row["component_mutation_count"] for row in resources
        ),
        "keyframe_roundtrip_count": sum(
            row["keyframe_roundtrip_count"] for row in resources
        ),
        "keyframe_mutation_count": sum(
            row["keyframe_mutation_count"] for row in resources
        ),
        "anomalous_trailer_count": sum(
            row["anomalous_trailer_count"] for row in resources
        ),
    }
    expected = {
        "resource_count": 250,
        "slot_reference_count": 342,
        "frame_count": 2004,
        "component_count": 2190,
        "animation_count": 784,
        "keyframe_count": 3187,
        "component_roundtrip_count": 2190,
        "component_mutation_count": 2190,
        "keyframe_roundtrip_count": 3187,
        "keyframe_mutation_count": 3187,
        "anomalous_trailer_count": 1,
    }
    if summary != expected:
        raise ValueError(
            f"character battle structure denominator mismatch: {summary}"
        )
    return summary


def _scope() -> dict[str, bool]:
    return {
        "all_resources_audited": True,
        "all_slot_aliases_accounted": True,
        "all_frames_and_components_audited": True,
        "all_animations_and_keyframes_audited": True,
        "pointer_tables_immutable": True,
        "terminators_immutable": True,
        "anomalous_trailer_preserved": True,
        "component_semantic_writeback_complete": True,
        "keyframe_semantic_writeback_complete": True,
        "variable_count_structure_writeback_complete": False,
        "resource_relocation_complete": False,
        "pointer_rewrite_complete": False,
        "runtime_slot_selection_complete": False,
        "runtime_pixel_equivalence": False,
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
        "schema": "character-battle-structure-writeback-audit-v1",
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
        "mutation_models": {
            "component": "toggle horizontal flip bit",
            "keyframe": "increment non-maximum hold by one frame",
            "purpose": (
                "prove every existing semantic slot has a length-preserving "
                "write-back path"
            ),
        },
        "resources": resources,
        "summary": _summary(resources),
        "scope": _scope(),
    }


def verify_character_battle_structure_writeback_audit(
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
    ) != "character-battle-structure-writeback-audit-v1":
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
        "tools/verify_character_battle_structure_writeback_audit.py",
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
            "mutation_models",
            "summary",
            "scope",
        ):
            if payload.get(key) != expected[key]:
                errors.append(f"payload {key} mismatch")
    summary = payload.get("summary", {})
    return {
        "verified": not errors,
        "resources": summary.get("resource_count"),
        "slots": summary.get("slot_reference_count"),
        "components": summary.get("component_count"),
        "keyframes": summary.get("keyframe_count"),
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
    report = verify_character_battle_structure_writeback_audit(
        args.root,
        artifact,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
