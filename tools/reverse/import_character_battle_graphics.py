#!/usr/bin/env python3
"""Build guarded fixed-length patches for character battle graphics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/character-battle-visuals-v1/manifest.json")
CATALOG_SHA256 = "a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c"
SPEC_SCHEMA = "character-battle-graphics-import-v1"
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
) -> tuple[int, int]:
    try:
        pointer = int(pointer_text, 16)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} pointer is invalid") from error
    offset = pointer - ROM_BASE
    if offset < 0 or size <= 0 or offset + size > rom_size:
        raise ValueError(f"{label} span is outside ROM")
    return pointer, offset


def _validate_source_span(
    rom: bytes,
    source: Any,
    label: str,
) -> tuple[int, int]:
    if not isinstance(source, dict):
        raise ValueError(f"{label} provenance is missing")
    size = source.get("size")
    if not isinstance(size, int):
        raise ValueError(f"{label} size is invalid")
    _, offset = _pointer_offset(
        source.get("gba_pointer"),
        size,
        len(rom),
        label,
    )
    raw = rom[offset : offset + size]
    if _sha256(raw) != source.get("sha256"):
        raise ValueError(f"{label} bytes mismatch")
    return offset, offset + size


def _catalog_graphics(
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
        or table.get("row_formula")
        != "(character_id - 1) * 9 + visual_slot"
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
        raise ValueError("character battle visual catalog denominator mismatch")

    graphics_rows: dict[int, dict[str, Any]] = {}
    graphics_spans: list[tuple[int, int, int]] = []
    structure_spans: list[tuple[int, int, str, int]] = []
    populated_rows: set[int] = set()
    total_components = 0
    total_frames = 0
    total_tiles = 0
    for expected_id, resource in enumerate(resources):
        if not isinstance(resource, dict) or resource.get(
            "resource_id"
        ) != expected_id:
            raise ValueError("character battle visual resource identity mismatch")
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
                f"resource {expected_id} graphics provenance mismatch"
            )
        size = graphics.get("size")
        tile_count = graphics.get("tile_count")
        source_file = graphics.get("file")
        if (
            not isinstance(size, int)
            or size <= 0
            or size % 32
            or tile_count != size // 32
            or not isinstance(source_file, str)
        ):
            raise ValueError(f"resource {expected_id} graphics format mismatch")
        pointer, offset = _pointer_offset(
            graphics.get("gba_pointer"),
            size,
            len(rom),
            f"resource {expected_id} graphics",
        )
        raw = rom[offset : offset + size]
        digest = _sha256(raw)
        if digest != graphics.get("sha256"):
            raise ValueError(f"resource {expected_id} graphics bytes mismatch")
        if offset in graphics_rows:
            raise ValueError("character battle graphics pointer alias detected")

        components: list[dict[str, Any]] = []
        for expected_frame_id, frame in enumerate(frames):
            if (
                not isinstance(frame, dict)
                or frame.get("frame_id") != expected_frame_id
                or not isinstance(frame.get("components"), list)
                or not frame["components"]
            ):
                raise ValueError(
                    f"resource {expected_id} frame provenance mismatch"
                )
            components.extend(frame["components"])
        if (
            len(frames) != resource.get("frame_count")
            or len(components) != resource.get("component_count")
        ):
            raise ValueError(
                f"resource {expected_id} frame/component denominator mismatch"
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
                    f"resource {expected_id} component tile range mismatch"
                )
            maximum_tile_end = max(maximum_tile_end, tile_end)
        if maximum_tile_end != tile_count:
            raise ValueError(
                f"resource {expected_id} graphics/component boundary mismatch"
            )
        try:
            first_frame_pointer = int(
                frames[0]["component_list_pointer"],
                16,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"resource {expected_id} first frame pointer is invalid"
            ) from error
        if pointer + size != first_frame_pointer:
            raise ValueError(
                f"resource {expected_id} graphics end boundary mismatch"
            )

        descriptor = resource.get("descriptor")
        if (
            not isinstance(descriptor, dict)
            or descriptor.get("graphics") != f"0x{pointer:08X}"
        ):
            raise ValueError(
                f"resource {expected_id} descriptor provenance mismatch"
            )
        aliases: list[dict[str, Any]] = []
        for row in slot_rows:
            if not isinstance(row, int) or not 0 <= row < TABLE_ENTRY_COUNT:
                raise ValueError(f"resource {expected_id} slot row is invalid")
            slot = slots[row]
            if (
                slot.get("row") != row
                or not slot.get("populated")
                or slot.get("resource_id") != expected_id
            ):
                raise ValueError(
                    f"resource {expected_id} slot-row provenance mismatch"
                )
            descriptor_bytes = table_bytes[
                row * TABLE_ENTRY_SIZE : (row + 1) * TABLE_ENTRY_SIZE
            ]
            if descriptor_bytes != bytes.fromhex(
                slot.get("descriptor_raw_hex", "")
            ):
                raise ValueError(f"slot {row} descriptor bytes mismatch")
            actual_pointer = int.from_bytes(
                descriptor_bytes[
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
                    "resource_id": expected_id,
                    "table_pointer_offset": (
                        TABLE_OFFSET
                        + row * TABLE_ENTRY_SIZE
                        + GRAPHICS_POINTER_DELTA
                    ),
                }
            )
            populated_rows.add(row)

        for key in STRUCTURE_KEYS:
            start, end = _validate_source_span(
                rom,
                resource.get(key),
                f"resource {expected_id} {key}",
            )
            structure_spans.append((start, end, key, expected_id))
        graphics_spans.append((offset, offset + size, expected_id))
        graphics_rows[offset] = {
            "file_offset": offset,
            "graphics_pointer": f"0x{pointer:08X}",
            "graphics_sha256": digest,
            "source_file": source_file,
            "size": size,
            "tile_count": tile_count,
            "maximum_component_tile_end": maximum_tile_end,
            "resource_id": expected_id,
            "slot_rows": slot_rows,
            "logical_aliases": aliases,
            "component_count": len(components),
            "frame_count": len(frames),
        }
        total_components += len(components)
        total_frames += len(frames)
        total_tiles += tile_count

    for expected_row, slot in enumerate(slots):
        if slot.get("row") != expected_row:
            raise ValueError("character battle slot ordering mismatch")
        if slot.get("populated") != (expected_row in populated_rows):
            raise ValueError("character battle populated-slot denominator mismatch")
    ordered_graphics = sorted(graphics_spans)
    if any(
        left_end > right_start
        for (_, left_end, _), (right_start, _, _) in zip(
            ordered_graphics,
            ordered_graphics[1:],
        )
    ):
        raise ValueError("character battle graphics physical slots overlap")
    for graphics_start, graphics_end, resource_id in ordered_graphics:
        for structure_start, structure_end, key, owner_id in structure_spans:
            if (
                graphics_start < structure_end
                and structure_start < graphics_end
            ):
                raise ValueError(
                    "character battle graphics overlaps "
                    f"{key}: resource {resource_id}/{owner_id}"
                )
    if (
        len(graphics_rows) != 250
        or len({row["graphics_sha256"] for row in graphics_rows.values()})
        != 250
        or len(populated_rows) != 342
        or total_components != 2190
        or total_frames != 2004
        or total_tiles != 60430
    ):
        raise ValueError(
            "character battle graphics denominator mismatch: "
            f"{len(graphics_rows)}/250 physical, "
            f"{len(populated_rows)}/342 slots, "
            f"{total_components}/2190 components, "
            f"{total_frames}/2004 frames, {total_tiles}/60430 tiles"
        )
    return graphics_rows


def resolve_character_battle_graphics_patches(
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
        raise ValueError("character battle graphics source catalog path mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("character battle visual catalog hash mismatch")
    catalog = json.loads(catalog_bytes)
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("character battle graphics base ROM hash mismatch")
    graphics_rows = _catalog_graphics(catalog, base)

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("character battle graphics edits must be a list")
    seen: set[int] = set()
    patches: list[dict[str, Any]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("character battle graphics edit must be an object")
        pointer_text = edit.get("graphics_pointer")
        try:
            offset = int(pointer_text, 16) - ROM_BASE
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"unknown character battle graphics: {pointer_text}"
            ) from error
        row = graphics_rows.get(offset)
        if (
            row is None
            or pointer_text != row["graphics_pointer"]
            or edit.get("graphics_sha256") != row["graphics_sha256"]
        ):
            raise ValueError(
                f"unknown character battle graphics: {pointer_text}"
            )
        if offset in seen:
            raise ValueError(
                f"duplicate character battle graphics: {pointer_text}"
            )
        seen.add(offset)
        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError(
                "character battle graphics expected provenance is missing"
            )
        for key, message in (
            ("file_offset", "file-offset provenance"),
            ("size", "size provenance"),
            ("tile_count", "tile-count provenance"),
            ("resource_id", "resource provenance"),
            ("slot_rows", "slot-row provenance"),
        ):
            if expected.get(key) != row[key]:
                raise ValueError(f"character battle graphics {message} mismatch")
        if (
            expected.get("maximum_component_tile_end")
            != row["maximum_component_tile_end"]
        ):
            raise ValueError(
                "character battle graphics component provenance mismatch"
            )
        source_file = edit.get("source_file")
        if not isinstance(source_file, str):
            raise ValueError("character battle graphics source file is missing")
        content = _resolve_path(root, source_file).read_bytes()
        if len(content) != row["size"]:
            raise ValueError(
                "character battle graphics must contain exactly "
                f"{row['size']} bytes"
            )
        if not content or len(content) % 32:
            raise ValueError(
                "character battle graphics must contain complete "
                "32-byte 4bpp tiles"
            )
        before = base[offset : offset + row["size"]]
        if _sha256(before) != row["graphics_sha256"]:
            raise ValueError("character battle graphics immutable bytes mismatch")
        if content == before:
            continue
        edit_id = edit.get("id")
        if not isinstance(edit_id, str) or not edit_id:
            raise ValueError("character battle graphics edit id is missing")
        patches.append(
            {
                "id": f"{edit_id}:graphics@{offset:06X}",
                "type": "bytes",
                "offset": offset,
                "before_hex": before.hex(),
                "after_hex": content.hex(),
                "asset_type": "character_battle_graphics",
                "graphics_pointer": row["graphics_pointer"],
                "graphics_sha256": row["graphics_sha256"],
                "replacement_sha256": _sha256(content),
                "graphics_size": row["size"],
                "tile_count": row["tile_count"],
                "affected_resource_id": row["resource_id"],
                "affected_slot_rows": row["slot_rows"],
                "logical_aliases": row["logical_aliases"],
                "source_file": source_file,
            }
        )
    return sorted(patches, key=lambda item: (item["offset"], item["id"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_character_battle_graphics_patches(args.root, args.spec)
    payload = {"patches": patches}
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
