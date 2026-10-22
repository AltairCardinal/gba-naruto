#!/usr/bin/env python3
"""Build guarded same-layout character battle structure patches."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/character-battle-visuals-v1/manifest.json")
CATALOG_SHA256 = "a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c"
SPEC_SCHEMA = "character-battle-structure-import-v1"
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _pointer_offset(
    pointer_text: Any,
    size: int,
    rom_size: int,
    label: str,
) -> int:
    try:
        pointer = int(pointer_text, 16)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} pointer is invalid") from error
    offset = pointer - ROM_BASE
    if offset < 0 or size < 0 or offset + size > rom_size:
        raise ValueError(f"{label} span is outside ROM")
    return offset


def _validate_source(
    rom: bytes,
    source: Any,
    label: str,
) -> tuple[int, bytes]:
    if not isinstance(source, dict):
        raise ValueError(f"{label} provenance is missing")
    size = source.get("size")
    if not isinstance(size, int) or size <= 0:
        raise ValueError(f"{label} size is invalid")
    offset = _pointer_offset(
        source.get("gba_pointer"),
        size,
        len(rom),
        label,
    )
    raw = rom[offset : offset + size]
    if _sha256(raw) != source.get("sha256"):
        raise ValueError(f"{label} bytes mismatch")
    return offset, raw


def _parse_component(
    raw: bytes,
    expected: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    if len(raw) != COMPONENT_SIZE:
        raise ValueError(f"{label} record size mismatch")
    values = struct.unpack("<HBBhhHHHHBBH", raw)
    (
        tile_index,
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
    ) = values
    if (
        tile_index >> 10
        or orientation & ~3
        or angle
        or scale_x != 0x100
        or scale_y != 0x100
        or control != 0xFF
        or attribute
        or reserved
        or (width, height) not in SUPPORTED_SIZES
    ):
        raise ValueError(f"{label} control fields mismatch")
    parsed = {
        "tile_index_raw": tile_index,
        "tile_offset": tile_index,
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
        "tile_end": tile_index + (width // 8) * (height // 8),
        "raw_hex": raw.hex(),
        "raw_sha256": _sha256(raw),
    }
    for key, value in parsed.items():
        if expected.get(key) != value:
            raise ValueError(f"{label} catalog field {key} mismatch")
    return parsed


def _catalog_structures(
    catalog: dict[str, Any],
    rom: bytes,
) -> dict[int, dict[str, Any]]:
    if catalog.get("schema") != "character-battle-visuals-v1":
        raise ValueError("character battle visual catalog schema mismatch")
    table = catalog.get("table")
    if (
        not isinstance(table, dict)
        or table.get("file_offset") != TABLE_OFFSET
        or table.get("entry_count") != TABLE_ENTRY_COUNT
        or table.get("entry_size") != TABLE_ENTRY_SIZE
    ):
        raise ValueError("character battle visual table provenance mismatch")
    table_bytes = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    if len(table_bytes) != TABLE_SIZE or _sha256(table_bytes) != table.get(
        "sha256"
    ):
        raise ValueError("character battle visual table bytes mismatch")
    slots = catalog.get("slots")
    resources = catalog.get("resources")
    if (
        not isinstance(slots, list)
        or len(slots) != TABLE_ENTRY_COUNT
        or not isinstance(resources, list)
        or len(resources) != 250
    ):
        raise ValueError("character battle structure denominator mismatch")

    rows: dict[int, dict[str, Any]] = {}
    populated_rows: set[int] = set()
    component_spans: list[tuple[int, int]] = []
    keyframe_spans: list[tuple[int, int]] = []
    total_frames = 0
    total_components = 0
    total_animations = 0
    total_keyframes = 0
    anomaly_count = 0
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
            or slot_rows != sorted(set(slot_rows))
        ):
            raise ValueError(
                f"resource {resource_id} structure provenance mismatch"
            )
        component_region_offset, component_region = _validate_source(
            rom,
            resource.get("component_region"),
            f"resource {resource_id} component region",
        )
        frame_table_offset, frame_table = _validate_source(
            rom,
            resource.get("frame_pointer_table"),
            f"resource {resource_id} frame pointer table",
        )
        timeline_offset, timeline_region = _validate_source(
            rom,
            resource.get("timeline_region"),
            f"resource {resource_id} timeline region",
        )
        animation_table_offset, animation_table = _validate_source(
            rom,
            resource.get("animation_pointer_table"),
            f"resource {resource_id} animation pointer table",
        )
        if len(frame_table) != len(frames) * 4:
            raise ValueError(
                f"resource {resource_id} frame table denominator mismatch"
            )
        if len(animation_table) != len(animations) * 4:
            raise ValueError(
                f"resource {resource_id} animation table denominator mismatch"
            )
        frame_pointers = list(
            struct.unpack(f"<{len(frames)}I", frame_table)
        )
        animation_pointers = list(
            struct.unpack(f"<{len(animations)}I", animation_table)
        )
        if (
            component_region_offset + len(component_region)
            != frame_table_offset
            or timeline_offset + len(timeline_region)
            != animation_table_offset
        ):
            raise ValueError(
                f"resource {resource_id} structure region boundary mismatch"
            )

        component_targets: dict[tuple[int, int], dict[str, Any]] = {}
        for frame_id, frame in enumerate(frames):
            if (
                not isinstance(frame, dict)
                or frame.get("frame_id") != frame_id
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
            end_pointer = (
                frame_pointers[frame_id + 1]
                if frame_id + 1 < len(frame_pointers)
                else ROM_BASE + frame_table_offset
            )
            size = end_pointer - pointer
            expected_size = len(frame["components"]) * COMPONENT_SIZE + 4
            if size != expected_size or frame.get("raw_size") != size:
                raise ValueError(
                    f"resource {resource_id} frame span mismatch"
                )
            offset = pointer - ROM_BASE
            raw = rom[offset : offset + size]
            if _sha256(raw) != frame.get("raw_sha256"):
                raise ValueError(
                    f"resource {resource_id} frame bytes mismatch"
                )
            trailer = raw[-4:]
            if trailer.hex() != frame.get("frame_trailer_raw_hex"):
                raise ValueError(
                    f"resource {resource_id} frame trailer mismatch"
                )
            if trailer == ANOMALOUS_TRAILER:
                if offset + size - 4 != ANOMALOUS_TRAILER_OFFSET:
                    raise ValueError("unexpected anomalous component trailer")
                anomaly_count += 1
            elif trailer != NORMAL_TRAILER:
                raise ValueError("unknown component trailer")
            for component_index, expected_component in enumerate(
                frame["components"]
            ):
                component_offset = offset + component_index * COMPONENT_SIZE
                component_raw = rom[
                    component_offset : component_offset + COMPONENT_SIZE
                ]
                parsed = _parse_component(
                    component_raw,
                    expected_component,
                    (
                        f"resource {resource_id} frame {frame_id} "
                        f"component {component_index}"
                    ),
                )
                tile_count = resource["graphics"]["tile_count"]
                if parsed["tile_end"] > tile_count:
                    raise ValueError(
                        f"resource {resource_id} component tile range mismatch"
                    )
                component_targets[(frame_id, component_index)] = {
                    "offset": component_offset,
                    "raw": component_raw,
                    **parsed,
                }
                component_spans.append(
                    (component_offset, component_offset + COMPONENT_SIZE)
                )

        keyframe_targets: dict[tuple[int, int], dict[str, Any]] = {}
        for animation_id, animation in enumerate(animations):
            if (
                not isinstance(animation, dict)
                or animation.get("animation_id") != animation_id
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
            end_pointer = (
                animation_pointers[animation_id + 1]
                if animation_id + 1 < len(animation_pointers)
                else ROM_BASE + animation_table_offset
            )
            size = end_pointer - pointer
            expected_size = (
                len(animation["keyframes"]) + 1
            ) * KEYFRAME_SIZE
            if size != expected_size or animation.get("raw_size") != size:
                raise ValueError(
                    f"resource {resource_id} animation span mismatch"
                )
            offset = pointer - ROM_BASE
            raw = rom[offset : offset + size]
            if _sha256(raw) != animation.get("raw_sha256"):
                raise ValueError(
                    f"resource {resource_id} animation bytes mismatch"
                )
            if raw[-4:] != NORMAL_TRAILER:
                raise ValueError("animation terminator mismatch")
            for keyframe_index, expected_keyframe in enumerate(
                animation["keyframes"]
            ):
                keyframe_offset = offset + keyframe_index * KEYFRAME_SIZE
                keyframe_raw = rom[
                    keyframe_offset : keyframe_offset + KEYFRAME_SIZE
                ]
                frame_id_value, hold_frames = struct.unpack(
                    "<HH",
                    keyframe_raw,
                )
                if (
                    frame_id_value != expected_keyframe.get("frame_id")
                    or hold_frames != expected_keyframe.get("hold_frames")
                    or frame_id_value >= len(frames)
                    or hold_frames == 0
                ):
                    raise ValueError(
                        f"resource {resource_id} keyframe bytes mismatch"
                    )
                keyframe_targets[(animation_id, keyframe_index)] = {
                    "offset": keyframe_offset,
                    "raw": keyframe_raw,
                    "frame_id": frame_id_value,
                    "hold_frames": hold_frames,
                }
                keyframe_spans.append(
                    (keyframe_offset, keyframe_offset + KEYFRAME_SIZE)
                )

        aliases = []
        for slot_row in slot_rows:
            if (
                not isinstance(slot_row, int)
                or not 0 <= slot_row < TABLE_ENTRY_COUNT
            ):
                raise ValueError(
                    f"resource {resource_id} slot row is invalid"
                )
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
                raise ValueError(f"slot {slot_row} descriptor bytes mismatch")
            aliases.append(
                {
                    "slot_row": slot_row,
                    "character_id": slot["character_id"],
                    "visual_slot": slot["visual_slot"],
                    "resource_id": resource_id,
                }
            )
            populated_rows.add(slot_row)
        rows[resource_id] = {
            "resource_id": resource_id,
            "component_region_sha256": resource["component_region"]["sha256"],
            "timeline_region_sha256": resource["timeline_region"]["sha256"],
            "frame_count": len(frames),
            "component_count": len(component_targets),
            "animation_count": len(animations),
            "keyframe_count": len(keyframe_targets),
            "tile_count": resource["graphics"]["tile_count"],
            "slot_rows": slot_rows,
            "logical_aliases": aliases,
            "component_targets": component_targets,
            "keyframe_targets": keyframe_targets,
        }
        total_frames += len(frames)
        total_components += len(component_targets)
        total_animations += len(animations)
        total_keyframes += len(keyframe_targets)

    for slot_row, slot in enumerate(slots):
        if slot.get("row") != slot_row:
            raise ValueError("character battle slot ordering mismatch")
        if slot.get("populated") != (slot_row in populated_rows):
            raise ValueError("character battle populated denominator mismatch")
    all_spans = sorted(component_spans + keyframe_spans)
    if any(
        left_end > right_start
        for (_, left_end), (right_start, _) in zip(
            all_spans,
            all_spans[1:],
        )
    ):
        raise ValueError("character battle editable structure spans overlap")
    if (
        len(rows) != 250
        or len(populated_rows) != 342
        or total_frames != 2004
        or total_components != 2190
        or total_animations != 784
        or total_keyframes != 3187
        or anomaly_count != 1
    ):
        raise ValueError(
            "character battle structure denominator mismatch: "
            f"{len(rows)}/250 resources, {len(populated_rows)}/342 slots, "
            f"{total_frames}/2004 frames, "
            f"{total_components}/2190 components, "
            f"{total_animations}/784 animations, "
            f"{total_keyframes}/3187 keyframes, {anomaly_count}/1 anomaly"
        )
    return rows


def _integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _component_after(
    source: dict[str, Any],
    edit: dict[str, Any],
    tile_count: int,
) -> tuple[bytes, dict[str, Any]]:
    allowed = {
        "frame_id",
        "component_index",
        "tile_offset",
        "horizontal_flip",
        "vertical_flip",
        "x",
        "y",
        "width",
        "height",
    }
    unknown = set(edit) - allowed
    if unknown:
        raise ValueError(f"unsupported component fields: {sorted(unknown)}")
    tile_offset = _integer(
        edit.get("tile_offset", source["tile_offset"]),
        "component tile_offset",
    )
    x = _integer(edit.get("x", source["x"]), "component x")
    y = _integer(edit.get("y", source["y"]), "component y")
    width = _integer(
        edit.get("width", source["width"]),
        "component width",
    )
    height = _integer(
        edit.get("height", source["height"]),
        "component height",
    )
    horizontal = edit.get(
        "horizontal_flip",
        source["horizontal_flip"],
    )
    vertical = edit.get("vertical_flip", source["vertical_flip"])
    if not isinstance(horizontal, bool) or not isinstance(vertical, bool):
        raise ValueError("component flip values must be booleans")
    if not -0x8000 <= x <= 0x7FFF or not -0x8000 <= y <= 0x7FFF:
        raise ValueError("component x/y must fit signed 16-bit")
    if (width, height) not in SUPPORTED_SIZES:
        raise ValueError("component must use a supported OBJ size")
    tile_end = tile_offset + (width // 8) * (height // 8)
    if tile_offset < 0 or tile_offset >= 0x400 or tile_end > tile_count:
        raise ValueError("component tile range exceeds graphics")
    orientation = int(horizontal) | (int(vertical) << 1)
    after = struct.pack(
        "<HBBhhHHHHBBH",
        tile_offset,
        orientation,
        0,
        x,
        y,
        width,
        height,
        0x100,
        0x100,
        0xFF,
        0,
        0,
    )
    return after, {
        "tile_offset": tile_offset,
        "tile_end": tile_end,
        "horizontal_flip": horizontal,
        "vertical_flip": vertical,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
    }


def _keyframe_after(
    source: dict[str, Any],
    edit: dict[str, Any],
    frame_count: int,
) -> tuple[bytes, dict[str, int]]:
    allowed = {
        "animation_id",
        "keyframe_index",
        "frame_id",
        "hold_frames",
    }
    unknown = set(edit) - allowed
    if unknown:
        raise ValueError(f"unsupported keyframe fields: {sorted(unknown)}")
    frame_id = _integer(
        edit.get("frame_id", source["frame_id"]),
        "keyframe frame_id",
    )
    hold_frames = _integer(
        edit.get("hold_frames", source["hold_frames"]),
        "keyframe hold_frames",
    )
    if not 0 <= frame_id < frame_count:
        raise ValueError("keyframe frame_id is outside resource frames")
    if not 1 <= hold_frames <= 0xFFFF:
        raise ValueError("keyframe hold_frames must be nonzero u16")
    return struct.pack("<HH", frame_id, hold_frames), {
        "frame_id": frame_id,
        "hold_frames": hold_frames,
    }


def resolve_character_battle_structure_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
) -> list[dict[str, Any]]:
    root = root.resolve()
    spec_path = _resolve_path(root, str(spec_path))
    spec = _load_json(spec_path)
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"expected schema {SPEC_SCHEMA}")
    if spec.get("source_catalog") != CATALOG_PATH.as_posix():
        raise ValueError("character battle structure source catalog mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("character battle visual catalog hash mismatch")
    catalog = json.loads(catalog_bytes)
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("character battle structure base ROM hash mismatch")
    resources = _catalog_structures(catalog, base)

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("character battle structure edits must be a list")
    seen_resources: set[int] = set()
    patches: list[dict[str, Any]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("character battle structure edit must be an object")
        resource_id = edit.get("resource_id")
        if not isinstance(resource_id, int) or resource_id not in resources:
            raise ValueError(f"unknown character battle resource: {resource_id}")
        if resource_id in seen_resources:
            raise ValueError(
                f"duplicate character battle resource edit: {resource_id}"
            )
        seen_resources.add(resource_id)
        row = resources[resource_id]
        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError("character battle structure provenance is missing")
        for key in (
            "component_region_sha256",
            "timeline_region_sha256",
            "frame_count",
            "component_count",
            "animation_count",
            "keyframe_count",
            "tile_count",
            "slot_rows",
        ):
            if expected.get(key) != row[key]:
                raise ValueError(
                    f"character battle structure provenance mismatch: {key}"
                )
        edit_id = edit.get("id")
        if not isinstance(edit_id, str) or not edit_id:
            raise ValueError("character battle structure edit id is missing")
        component_edits = edit.get("component_edits", [])
        keyframe_edits = edit.get("keyframe_edits", [])
        if not isinstance(component_edits, list) or not isinstance(
            keyframe_edits,
            list,
        ):
            raise ValueError("character battle structure edit lists are invalid")
        seen_components: set[tuple[int, int]] = set()
        for component_edit in component_edits:
            if not isinstance(component_edit, dict):
                raise ValueError("component edit must be an object")
            frame_id = component_edit.get("frame_id")
            component_index = component_edit.get("component_index")
            key = (frame_id, component_index)
            source = row["component_targets"].get(key)
            if source is None:
                raise ValueError(f"unknown component edit target: {key}")
            if key in seen_components:
                raise ValueError(f"duplicate component edit: {key}")
            seen_components.add(key)
            after, semantic = _component_after(
                source,
                component_edit,
                row["tile_count"],
            )
            if after == source["raw"]:
                continue
            patches.append(
                {
                    "id": (
                        f"{edit_id}:component:"
                        f"{frame_id}:{component_index}"
                    ),
                    "type": "bytes",
                    "offset": source["offset"],
                    "before_hex": source["raw"].hex(),
                    "after_hex": after.hex(),
                    "asset_type": "character_battle_structure",
                    "structure_type": "component",
                    "resource_id": resource_id,
                    "frame_id": frame_id,
                    "component_index": component_index,
                    "semantic_after": semantic,
                    "affected_slot_rows": row["slot_rows"],
                    "logical_aliases": row["logical_aliases"],
                }
            )
        seen_keyframes: set[tuple[int, int]] = set()
        for keyframe_edit in keyframe_edits:
            if not isinstance(keyframe_edit, dict):
                raise ValueError("keyframe edit must be an object")
            animation_id = keyframe_edit.get("animation_id")
            keyframe_index = keyframe_edit.get("keyframe_index")
            key = (animation_id, keyframe_index)
            source = row["keyframe_targets"].get(key)
            if source is None:
                raise ValueError(f"unknown keyframe edit target: {key}")
            if key in seen_keyframes:
                raise ValueError(f"duplicate keyframe edit: {key}")
            seen_keyframes.add(key)
            after, semantic = _keyframe_after(
                source,
                keyframe_edit,
                row["frame_count"],
            )
            if after == source["raw"]:
                continue
            patches.append(
                {
                    "id": (
                        f"{edit_id}:keyframe:"
                        f"{animation_id}:{keyframe_index}"
                    ),
                    "type": "bytes",
                    "offset": source["offset"],
                    "before_hex": source["raw"].hex(),
                    "after_hex": after.hex(),
                    "asset_type": "character_battle_structure",
                    "structure_type": "keyframe",
                    "resource_id": resource_id,
                    "animation_id": animation_id,
                    "keyframe_index": keyframe_index,
                    "semantic_after": semantic,
                    "affected_slot_rows": row["slot_rows"],
                    "logical_aliases": row["logical_aliases"],
                }
            )
    return sorted(patches, key=lambda item: (item["offset"], item["id"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_character_battle_structure_patches(
        args.root,
        args.spec,
    )
    payload = {"patches": patches}
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
