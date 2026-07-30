#!/usr/bin/env python3
"""Relocate variable-length character battle visual bundles into expanded ROM."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

try:
    from tools.rom_layout import RomLayout
except ModuleNotFoundError:
    from rom_layout import RomLayout


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/character-battle-visuals-v1/manifest.json")
CATALOG_SHA256 = "a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c"
SPEC_SCHEMA = "character-battle-bundle-import-v1"
TABLE_OFFSET = 0x596D5C
TABLE_ENTRY_COUNT = 558
TABLE_ENTRY_SIZE = 16
TABLE_SIZE = TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
COMPONENT_SIZE = 20
NORMAL_TRAILER = bytes.fromhex("ffff0000")
KEYFRAME_TERMINATOR = bytes.fromhex("ffff0000")
MAX_TILES = 1024
MAX_FRAMES = 128
MAX_ANIMATIONS = 64
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


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _pointer(value: object, label: str) -> int:
    try:
        pointer = int(str(value), 16)
    except ValueError as error:
        raise ValueError(f"{label} pointer is invalid") from error
    return pointer


def _source_bytes(rom: bytes, source: dict[str, Any], label: str) -> bytes:
    size = source.get("size")
    if not isinstance(size, int) or size <= 0:
        raise ValueError(f"{label} size is invalid")
    pointer = _pointer(source.get("gba_pointer"), label)
    offset = pointer - ROM_BASE
    if offset < 0 or offset + size > len(rom):
        raise ValueError(f"{label} is outside base ROM")
    data = rom[offset : offset + size]
    if _sha256(data) != source.get("sha256"):
        raise ValueError(f"{label} base bytes mismatch")
    return data


def _validated_catalog(
    root: Path,
    spec: dict[str, Any],
    rom: bytes,
) -> tuple[dict[str, Any], bytes]:
    if _sha256(rom) != ROM_SHA256 or spec.get("base_rom_sha256") != ROM_SHA256:
        raise ValueError("character battle bundle base ROM mismatch")
    catalog_value = spec.get("catalog")
    if not isinstance(catalog_value, str):
        raise ValueError("character battle bundle catalog path is missing")
    catalog_path = _resolve(root, catalog_value)
    catalog_bytes = catalog_path.read_bytes()
    if (
        _sha256(catalog_bytes) != CATALOG_SHA256
        or spec.get("catalog_sha256") != CATALOG_SHA256
    ):
        raise ValueError("character battle visual catalog SHA-256 mismatch")
    catalog = json.loads(catalog_bytes)
    table = catalog.get("table")
    if (
        catalog.get("schema") != "character-battle-visuals-v1"
        or not isinstance(table, dict)
        or table.get("file_offset") != TABLE_OFFSET
        or table.get("entry_count") != TABLE_ENTRY_COUNT
        or table.get("entry_size") != TABLE_ENTRY_SIZE
    ):
        raise ValueError("character battle visual catalog identity mismatch")
    table_bytes = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    if len(table_bytes) != TABLE_SIZE or _sha256(table_bytes) != table.get(
        "sha256"
    ):
        raise ValueError("character battle descriptor table mismatch")
    resources = catalog.get("resources")
    slots = catalog.get("slots")
    summary = catalog.get("summary")
    if (
        not isinstance(resources, list)
        or len(resources) != 250
        or not isinstance(slots, list)
        or len(slots) != TABLE_ENTRY_COUNT
        or not isinstance(summary, dict)
        or summary.get("resource_count") != 250
        or summary.get("populated_slot_count") != 342
        or summary.get("frame_count") != 2004
        or summary.get("component_count") != 2190
        or summary.get("animation_count") != 784
        or summary.get("keyframe_count") != 3187
    ):
        raise ValueError("character battle visual catalog denominator mismatch")
    return catalog, catalog_bytes


def _validate_resource(
    catalog: dict[str, Any],
    rom: bytes,
    resource_id: int,
) -> dict[str, Any]:
    resources = catalog["resources"]
    if not 0 <= resource_id < len(resources):
        raise ValueError(f"unknown character battle resource: {resource_id}")
    resource = resources[resource_id]
    if resource.get("resource_id") != resource_id:
        raise ValueError(f"resource {resource_id} catalog identity mismatch")
    slot_rows = resource.get("slot_rows")
    if (
        not isinstance(slot_rows, list)
        or not slot_rows
        or slot_rows != sorted(set(slot_rows))
    ):
        raise ValueError(f"resource {resource_id} slot aliases are invalid")
    descriptor = resource.get("descriptor")
    if not isinstance(descriptor, dict):
        raise ValueError(f"resource {resource_id} descriptor is missing")
    expected_descriptor = struct.pack(
        "<4I",
        _pointer(descriptor["frame_pointer_table"], "frame table"),
        _pointer(descriptor["animation_pointer_table"], "animation table"),
        _pointer(descriptor["graphics"], "graphics"),
        _pointer(descriptor["palette"], "palette"),
    )
    for row in slot_rows:
        if not isinstance(row, int) or not 0 <= row < TABLE_ENTRY_COUNT:
            raise ValueError(f"resource {resource_id} slot row is invalid")
        slot = catalog["slots"][row]
        offset = TABLE_OFFSET + row * TABLE_ENTRY_SIZE
        if (
            slot.get("row") != row
            or slot.get("resource_id") != resource_id
            or not slot.get("populated")
            or rom[offset : offset + TABLE_ENTRY_SIZE] != expected_descriptor
        ):
            raise ValueError(
                f"resource {resource_id} slot {row} provenance mismatch"
            )
    for key in (
        "palette",
        "graphics",
        "component_region",
        "frame_pointer_table",
        "timeline_region",
        "animation_pointer_table",
    ):
        source = resource.get(key)
        if not isinstance(source, dict):
            raise ValueError(f"resource {resource_id} {key} source is missing")
        _source_bytes(rom, source, f"resource {resource_id} {key}")
    return resource


def _reference_expectations(
    resource: dict[str, Any],
) -> dict[int, set[int]]:
    targets: dict[int, set[int]] = {}

    def expect(target: int, source_offset: int) -> None:
        targets.setdefault(target, set()).add(source_offset)

    descriptor = resource["descriptor"]
    for row in resource["slot_rows"]:
        row_offset = TABLE_OFFSET + row * TABLE_ENTRY_SIZE
        expect(_pointer(descriptor["frame_pointer_table"], "frame table"), row_offset)
        expect(
            _pointer(descriptor["animation_pointer_table"], "animation table"),
            row_offset + 4,
        )
        expect(_pointer(descriptor["graphics"], "graphics"), row_offset + 8)

    frame_table_offset = (
        _pointer(
            resource["frame_pointer_table"]["gba_pointer"],
            "frame pointer table",
        )
        - ROM_BASE
    )
    for frame_id, frame in enumerate(resource["frames"]):
        expect(
            _pointer(frame["component_list_pointer"], "component list"),
            frame_table_offset + frame_id * 4,
        )

    animation_table_offset = (
        _pointer(
            resource["animation_pointer_table"]["gba_pointer"],
            "animation pointer table",
        )
        - ROM_BASE
    )
    for animation_id, animation in enumerate(resource["animations"]):
        expect(
            _pointer(animation["timeline_pointer"], "timeline"),
            animation_table_offset + animation_id * 4,
        )

    return targets


def _scan_reference_locations(
    rom: bytes,
    target_values: set[int],
) -> dict[int, set[int]]:
    actual: dict[int, set[int]] = {target: set() for target in target_values}
    for offset in range(0, len(rom) - 3, 4):
        value = struct.unpack_from("<I", rom, offset)[0]
        if value in target_values:
            actual[value].add(offset)
    return actual


def _lz77_end(rom: bytes, start: int) -> int | None:
    if start < 0 or start + 4 > len(rom) or rom[start] != 0x10:
        return None
    declared = int.from_bytes(rom[start + 1 : start + 4], "little")
    if declared <= 0:
        return None
    cursor = start + 4
    produced = 0
    try:
        while produced < declared:
            flags = rom[cursor]
            cursor += 1
            for bit in range(7, -1, -1):
                if produced >= declared:
                    break
                if flags & (1 << bit):
                    first = rom[cursor]
                    second = rom[cursor + 1]
                    cursor += 2
                    length = (first >> 4) + 3
                    distance = (((first & 0x0F) << 8) | second) + 1
                    if distance > produced or produced + length > declared:
                        return None
                    produced += length
                else:
                    cursor += 1
                    produced += 1
    except IndexError:
        return None
    return cursor


def _pointed_lz77_spans(rom: bytes) -> list[dict[str, Any]]:
    sources: dict[int, list[int]] = {}
    for offset in range(0, len(rom) - 3, 4):
        pointer = struct.unpack_from("<I", rom, offset)[0]
        target = pointer - ROM_BASE
        if 0 <= target < len(rom) and rom[target] == 0x10:
            sources.setdefault(target, []).append(offset)
    spans = []
    for start, pointer_sources in sorted(sources.items()):
        end = _lz77_end(rom, start)
        if end is not None:
            spans.append(
                {
                    "start": start,
                    "end": end,
                    "pointer_sources": pointer_sources,
                }
            )
    return spans


def _reference_audit(
    resource: dict[str, Any],
    actual: dict[int, set[int]],
    pointed_lz77_spans: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check every aligned exact pointer to relocated semantic targets."""
    targets = _reference_expectations(resource)

    unexpected = []
    compressed_coincidences = []
    missing = []
    for target in sorted(targets):
        for offset in sorted(actual[target] - targets[target]):
            container = next(
                (
                    span
                    for span in pointed_lz77_spans
                    if span["start"] < offset < span["end"]
                ),
                None,
            )
            row = {
                "pointer": f"0x{target:08X}",
                "source_offset": offset,
            }
            if container is None:
                unexpected.append(row)
            else:
                compressed_coincidences.append(
                    {
                        **row,
                        "classification": "pointed_lz77_payload_coincidence",
                        "container_start": container["start"],
                        "container_end": container["end"],
                        "container_pointer_sources": container["pointer_sources"],
                    }
                )
        for offset in sorted(targets[target] - actual[target]):
            missing.append(
                {
                    "pointer": f"0x{target:08X}",
                    "source_offset": offset,
                }
            )
    if missing:
        raise ValueError(f"character battle pointer reference inventory is missing {missing}")
    if unexpected:
        raise ValueError(
            f"character battle resource has unexpected external references: {unexpected}"
        )
    return {
        "target_pointer_count": len(targets),
        "reference_count": sum(len(actual[target]) for target in targets),
        "compressed_payload_coincidences": compressed_coincidences,
        "unexpected_external_references": unexpected,
    }


def _component(component: object, tile_count: int, label: str) -> bytes:
    if not isinstance(component, dict):
        raise ValueError(f"{label} must be an object")
    fields = {}
    for key in ("tile_offset", "orientation", "x", "y", "width", "height"):
        value = component.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{label} {key} is invalid")
        fields[key] = value
    tile_offset = fields["tile_offset"]
    orientation = fields["orientation"]
    x = fields["x"]
    y = fields["y"]
    width = fields["width"]
    height = fields["height"]
    if not 0 <= tile_offset < MAX_TILES:
        raise ValueError(f"{label} tile offset is outside 10-bit range")
    if not 0 <= orientation <= 3:
        raise ValueError(f"{label} orientation is invalid")
    if not -0x8000 <= x <= 0x7FFF or not -0x8000 <= y <= 0x7FFF:
        raise ValueError(f"{label} coordinate is outside s16")
    if (width, height) not in SUPPORTED_SIZES:
        raise ValueError(f"{label} OBJ size is unsupported")
    tile_end = tile_offset + (width // 8) * (height // 8)
    if tile_end > tile_count:
        raise ValueError(
            f"{label} tile range {tile_offset}..{tile_end} "
            f"exceeds graphics tile count {tile_count}"
        )
    return struct.pack(
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


def _frames(
    authored: object,
    tile_count: int,
) -> tuple[list[bytes], int]:
    if not isinstance(authored, list) or not authored:
        raise ValueError("character battle bundle must have at least one frame")
    if len(authored) > MAX_FRAMES:
        raise ValueError(f"character battle bundle exceeds {MAX_FRAMES} frames")
    frames = []
    component_count = 0
    for frame_id, frame in enumerate(authored):
        if not isinstance(frame, dict) or not isinstance(
            frame.get("components"), list
        ):
            raise ValueError(f"frame {frame_id} components are invalid")
        components = [
            _component(
                component,
                tile_count,
                f"frame {frame_id} component {component_index}",
            )
            for component_index, component in enumerate(frame["components"])
        ]
        component_count += len(components)
        frames.append(b"".join(components) + NORMAL_TRAILER)
    return frames, component_count


def _animations(
    authored: object,
    frame_count: int,
) -> tuple[list[bytes], int]:
    if not isinstance(authored, list) or not authored:
        raise ValueError("character battle bundle must have at least one animation")
    if len(authored) > MAX_ANIMATIONS:
        raise ValueError(
            f"character battle bundle exceeds {MAX_ANIMATIONS} animations"
        )
    animations = []
    keyframe_count = 0
    for animation_id, animation in enumerate(authored):
        if not isinstance(animation, dict) or not isinstance(
            animation.get("keyframes"), list
        ) or not animation["keyframes"]:
            raise ValueError(f"animation {animation_id} keyframes are invalid")
        encoded = bytearray()
        for keyframe_index, keyframe in enumerate(animation["keyframes"]):
            if not isinstance(keyframe, dict):
                raise ValueError(
                    f"animation {animation_id} keyframe {keyframe_index} is invalid"
                )
            frame_id = keyframe.get("frame_id")
            hold_frames = keyframe.get("hold_frames")
            if (
                not isinstance(frame_id, int)
                or isinstance(frame_id, bool)
                or not 0 <= frame_id < frame_count
            ):
                raise ValueError(
                    f"animation {animation_id} keyframe {keyframe_index} "
                    "frame ID is out of range"
                )
            if (
                not isinstance(hold_frames, int)
                or isinstance(hold_frames, bool)
                or not 1 <= hold_frames <= 0xFFFF
            ):
                raise ValueError(
                    f"animation {animation_id} keyframe {keyframe_index} "
                    "hold is invalid"
                )
            encoded.extend(struct.pack("<HH", frame_id, hold_frames))
            keyframe_count += 1
        encoded.extend(KEYFRAME_TERMINATOR)
        animations.append(bytes(encoded))
    return animations, keyframe_count


def _catalog_frames(resource: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "components": [
                {
                    key: component[key]
                    for key in (
                        "tile_offset",
                        "orientation",
                        "x",
                        "y",
                        "width",
                        "height",
                    )
                }
                for component in frame["components"]
            ]
        }
        for frame in resource["frames"]
    ]


def _catalog_animations(resource: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "keyframes": [
                {
                    "frame_id": keyframe["frame_id"],
                    "hold_frames": keyframe["hold_frames"],
                }
                for keyframe in animation["keyframes"]
            ]
        }
        for animation in resource["animations"]
    ]


def _source_frames(
    resource: dict[str, Any],
    rom: bytes,
) -> tuple[list[bytes], int]:
    region = _source_bytes(
        rom,
        resource["component_region"],
        f"resource {resource['resource_id']} component region",
    )
    frames = []
    cursor = 0
    component_count = 0
    for frame in resource["frames"]:
        size = frame.get("raw_size")
        if not isinstance(size, int) or size < 4 or (size - 4) % COMPONENT_SIZE:
            raise ValueError("catalog frame raw size is invalid")
        raw = region[cursor : cursor + size]
        if len(raw) != size or _sha256(raw) != frame.get("raw_sha256"):
            raise ValueError("catalog frame raw bytes mismatch")
        frames.append(raw)
        component_count += (size - 4) // COMPONENT_SIZE
        cursor += size
    if cursor != len(region) or component_count != resource["component_count"]:
        raise ValueError("catalog component region denominator mismatch")
    return frames, component_count


def _source_animations(
    resource: dict[str, Any],
    rom: bytes,
) -> tuple[list[bytes], int]:
    region = _source_bytes(
        rom,
        resource["timeline_region"],
        f"resource {resource['resource_id']} timeline region",
    )
    animations = []
    cursor = 0
    keyframe_count = 0
    for animation in resource["animations"]:
        size = animation.get("raw_size")
        if not isinstance(size, int) or size < 8 or size % 4:
            raise ValueError("catalog animation raw size is invalid")
        raw = region[cursor : cursor + size]
        if len(raw) != size or _sha256(raw) != animation.get("raw_sha256"):
            raise ValueError("catalog animation raw bytes mismatch")
        animations.append(raw)
        keyframe_count += size // 4 - 1
        cursor += size
    if cursor != len(region) or keyframe_count != resource["keyframe_count"]:
        raise ValueError("catalog timeline region denominator mismatch")
    return animations, keyframe_count


def _bundle(
    start: int,
    *,
    graphics: bytes,
    palette: bytes,
    frames: list[bytes],
    animations: list[bytes],
) -> tuple[bytes, dict[str, int]]:
    palette_offset = start
    graphics_offset = palette_offset + len(palette)
    component_offset = graphics_offset + len(graphics)
    component_region = b"".join(frames)
    frame_table_offset = component_offset + len(component_region)
    timeline_offset = frame_table_offset + len(frames) * 4
    timeline_region = b"".join(animations)
    animation_table_offset = timeline_offset + len(timeline_region)

    frame_pointers = []
    cursor = component_offset
    for frame in frames:
        frame_pointers.append(ROM_BASE + cursor)
        cursor += len(frame)
    animation_pointers = []
    cursor = timeline_offset
    for animation in animations:
        animation_pointers.append(ROM_BASE + cursor)
        cursor += len(animation)

    frame_table = struct.pack(f"<{len(frame_pointers)}I", *frame_pointers)
    animation_table = struct.pack(
        f"<{len(animation_pointers)}I",
        *animation_pointers,
    )
    payload = (
        palette
        + graphics
        + component_region
        + frame_table
        + timeline_region
        + animation_table
    )
    pointers = {
        "palette": ROM_BASE + palette_offset,
        "graphics": ROM_BASE + graphics_offset,
        "component_region": ROM_BASE + component_offset,
        "frame_pointer_table": ROM_BASE + frame_table_offset,
        "timeline_region": ROM_BASE + timeline_offset,
        "animation_pointer_table": ROM_BASE + animation_table_offset,
    }
    return payload, pointers


def _reparse_bundle(
    payload: bytes,
    start: int,
    pointers: dict[str, int],
    *,
    tile_count: int,
    frame_count: int,
    component_count: int,
    animation_count: int,
    keyframe_count: int,
    expected_frame_trailers: list[bytes],
) -> None:
    base_pointer = ROM_BASE + start

    def local(pointer: int) -> int:
        offset = pointer - base_pointer
        if not 0 <= offset <= len(payload):
            raise ValueError("relocated pointer is outside bundle")
        return offset

    graphics_start = local(pointers["graphics"])
    component_start = local(pointers["component_region"])
    frame_table_start = local(pointers["frame_pointer_table"])
    timeline_start = local(pointers["timeline_region"])
    animation_table_start = local(pointers["animation_pointer_table"])
    if not (
        local(pointers["palette"]) == 0
        and graphics_start == 32
        and component_start - graphics_start == tile_count * 32
        and frame_table_start > component_start
        and timeline_start - frame_table_start == frame_count * 4
        and animation_table_start > timeline_start
        and len(payload) - animation_table_start == animation_count * 4
    ):
        raise ValueError("relocated bundle region layout mismatch")

    frame_pointers = struct.unpack_from(
        f"<{frame_count}I",
        payload,
        frame_table_start,
    )
    if (
        not frame_pointers
        or tuple(sorted(frame_pointers)) != frame_pointers
        or len(set(frame_pointers)) != frame_count
        or frame_pointers[0] != pointers["component_region"]
    ):
        raise ValueError("relocated frame pointers are invalid")
    parsed_components = 0
    for index, pointer in enumerate(frame_pointers):
        left = local(pointer)
        right = (
            local(frame_pointers[index + 1])
            if index + 1 < frame_count
            else frame_table_start
        )
        span = payload[left:right]
        if (
            len(span) < 4
            or span[-4:] != expected_frame_trailers[index]
            or (len(span) - 4) % 20
        ):
            raise ValueError("relocated frame record is invalid")
        parsed_components += (len(span) - 4) // 20
    if parsed_components != component_count:
        raise ValueError("relocated component denominator mismatch")

    animation_pointers = struct.unpack_from(
        f"<{animation_count}I",
        payload,
        animation_table_start,
    )
    if (
        not animation_pointers
        or tuple(sorted(animation_pointers)) != animation_pointers
        or len(set(animation_pointers)) != animation_count
        or animation_pointers[0] != pointers["timeline_region"]
    ):
        raise ValueError("relocated animation pointers are invalid")
    parsed_keyframes = 0
    for index, pointer in enumerate(animation_pointers):
        left = local(pointer)
        right = (
            local(animation_pointers[index + 1])
            if index + 1 < animation_count
            else animation_table_start
        )
        span = payload[left:right]
        if len(span) < 8 or span[-4:] != KEYFRAME_TERMINATOR or len(span) % 4:
            raise ValueError("relocated animation record is invalid")
        for offset in range(0, len(span) - 4, 4):
            frame_id, hold = struct.unpack_from("<HH", span, offset)
            if frame_id >= frame_count or hold == 0:
                raise ValueError("relocated keyframe is invalid")
            parsed_keyframes += 1
    if parsed_keyframes != keyframe_count:
        raise ValueError("relocated keyframe denominator mismatch")


def resolve_character_battle_bundle_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes,
    layout: RomLayout,
) -> list[dict[str, Any]]:
    spec = _load_json(spec_path)
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("character battle bundle spec schema mismatch")
    catalog, catalog_bytes = _validated_catalog(root, spec, rom)
    partition_id = spec.get("partition")
    owner = spec.get("owner")
    if not isinstance(partition_id, str) or not isinstance(owner, str):
        raise ValueError("character battle bundle allocation identity is missing")
    partition = next(
        (
            row
            for row in layout.partitions
            if row.id == partition_id and row.owner == owner
        ),
        None,
    )
    if partition is None:
        raise ValueError("character battle bundle partition/owner mismatch")

    edits = spec.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ValueError("character battle bundle spec has no edits")
    seen_resources: set[int] = set()
    prepared: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    all_reference_targets: set[int] = set()
    for edit_index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            raise ValueError(f"bundle edit {edit_index} must be an object")
        edit_id = edit.get("id")
        resource_id = edit.get("resource_id")
        if not isinstance(edit_id, str) or not edit_id:
            raise ValueError(f"bundle edit {edit_index} has no id")
        if not isinstance(resource_id, int) or isinstance(resource_id, bool):
            raise ValueError(f"bundle edit {edit_id} resource ID is invalid")
        if resource_id in seen_resources:
            raise ValueError(f"duplicate character battle resource edit: {resource_id}")
        seen_resources.add(resource_id)
        resource = _validate_resource(catalog, rom, resource_id)
        if (
            edit.get("expected_descriptor") != resource["descriptor"]
            or edit.get("expected_slot_rows") != resource["slot_rows"]
        ):
            raise ValueError(f"bundle edit {edit_id} target provenance mismatch")
        all_reference_targets.update(_reference_expectations(resource))
        prepared.append((resource_id, resource, edit))
    reference_locations = _scan_reference_locations(
        rom,
        all_reference_targets,
    )
    pointed_lz77_spans = _pointed_lz77_spans(rom)

    cursor = partition.start
    patches: list[dict[str, Any]] = []
    for resource_id, resource, edit in prepared:
        edit_id = edit["id"]
        reference_audit = _reference_audit(
            resource,
            reference_locations,
            pointed_lz77_spans,
        )

        graphics_file = edit.get("graphics_file")
        graphics_sha256 = edit.get("graphics_sha256")
        if not isinstance(graphics_file, str) or not isinstance(
            graphics_sha256, str
        ):
            raise ValueError(f"bundle edit {edit_id} graphics source is missing")
        graphics_path = _resolve(root, graphics_file)
        graphics = graphics_path.read_bytes()
        if _sha256(graphics) != graphics_sha256:
            raise ValueError(f"bundle edit {edit_id} graphics SHA-256 mismatch")
        if not graphics or len(graphics) % 32 or len(graphics) // 32 > MAX_TILES:
            raise ValueError(
                f"bundle edit {edit_id} graphics must contain 1..{MAX_TILES} "
                "complete 4bpp tiles"
            )
        tile_count = len(graphics) // 32

        palette_file = edit.get("palette_file")
        if palette_file is None:
            palette = _source_bytes(
                rom,
                resource["palette"],
                f"resource {resource_id} palette",
            )
            palette_source = resource["palette"]["file"]
        else:
            if not isinstance(palette_file, str) or not isinstance(
                edit.get("palette_sha256"), str
            ):
                raise ValueError(f"bundle edit {edit_id} palette source is invalid")
            palette_path = _resolve(root, palette_file)
            palette = palette_path.read_bytes()
            if _sha256(palette) != edit["palette_sha256"]:
                raise ValueError(f"bundle edit {edit_id} palette SHA-256 mismatch")
            palette_source = palette_file
        if len(palette) != 32:
            raise ValueError(f"bundle edit {edit_id} palette must be 32 bytes")

        authored_frames = edit.get("frames")
        if authored_frames is None:
            frames, component_count = _source_frames(resource, rom)
        else:
            frames, component_count = _frames(authored_frames, tile_count)
        authored_animations = edit.get("animations")
        if authored_animations is None:
            animations, keyframe_count = _source_animations(resource, rom)
        else:
            animations, keyframe_count = _animations(
                authored_animations,
                len(frames),
            )
        payload, pointers = _bundle(
            cursor,
            graphics=graphics,
            palette=palette,
            frames=frames,
            animations=animations,
        )
        end = cursor + len(payload)
        if end > partition.end:
            raise ValueError(
                f"character battle bundle partition capacity exceeded: "
                f"resource {resource_id} needs 0x{cursor:X}..0x{end:X}, "
                f"partition ends at 0x{partition.end:X}"
            )
        layout.allocation_partition(
            partition_id,
            owner,
            cursor,
            end,
        )
        _reparse_bundle(
            payload,
            cursor,
            pointers,
            tile_count=tile_count,
            frame_count=len(frames),
            component_count=component_count,
            animation_count=len(animations),
            keyframe_count=keyframe_count,
            expected_frame_trailers=[frame[-4:] for frame in frames],
        )
        pointer_text = {
            key: f"0x{value:08X}"
            for key, value in pointers.items()
        }
        bundle_patch = {
            "id": f"{edit_id}.bundle",
            "type": "bytes",
            "asset_type": "character_battle_bundle",
            "offset": cursor,
            "before_hex": bytes([layout.fill_byte] * len(payload)).hex(),
            "after_hex": payload.hex(),
            "allocation": {
                "partition": partition_id,
                "owner": owner,
            },
            "resource_id": resource_id,
            "affected_slot_rows": resource["slot_rows"],
            "logical_aliases": [
                {
                    "row": row,
                    "character_id": catalog["slots"][row]["character_id"],
                    "visual_slot": catalog["slots"][row]["visual_slot"],
                    "semantic": catalog["slots"][row]["semantic"],
                }
                for row in resource["slot_rows"]
            ],
            "old_descriptor": resource["descriptor"],
            "new_pointers": pointer_text,
            "bundle_size": len(payload),
            "graphics_size": len(graphics),
            "tile_count": tile_count,
            "frame_count": len(frames),
            "component_count": component_count,
            "animation_count": len(animations),
            "keyframe_count": keyframe_count,
            "graphics_file": graphics_file,
            "graphics_sha256": graphics_sha256,
            "palette_file": palette_source,
            "palette_sha256": _sha256(palette),
            "catalog_sha256": _sha256(catalog_bytes),
            **reference_audit,
        }
        patches.append(bundle_patch)

        descriptor_bytes = struct.pack(
            "<4I",
            pointers["frame_pointer_table"],
            pointers["animation_pointer_table"],
            pointers["graphics"],
            pointers["palette"],
        )
        for row in resource["slot_rows"]:
            offset = TABLE_OFFSET + row * TABLE_ENTRY_SIZE
            patches.append(
                {
                    "id": f"{edit_id}.descriptor-row-{row}",
                    "type": "bytes",
                    "asset_type": "character_battle_bundle_descriptor",
                    "offset": offset,
                    "before_hex": rom[offset : offset + TABLE_ENTRY_SIZE].hex(),
                    "after_hex": descriptor_bytes.hex(),
                    "resource_id": resource_id,
                    "slot_row": row,
                    "affected_slot_rows": resource["slot_rows"],
                    "new_pointers": pointer_text,
                }
            )
        cursor = end
    return patches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan variable-length character battle bundle relocation."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--layout",
        type=Path,
        default=Path("sequel/rom-layout.json"),
    )
    args = parser.parse_args()
    rom_path = args.rom if args.rom.is_absolute() else args.root / args.rom
    layout_path = (
        args.layout if args.layout.is_absolute() else args.root / args.layout
    )
    spec_path = args.spec if args.spec.is_absolute() else args.root / args.spec
    rom = rom_path.read_bytes()
    patches = resolve_character_battle_bundle_patches(
        args.root,
        spec_path,
        rom=rom,
        layout=RomLayout.from_path(layout_path, rom),
    )
    print(json.dumps(patches, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
