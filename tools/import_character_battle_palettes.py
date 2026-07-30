#!/usr/bin/env python3
"""Build guarded fixed-length patches for character battle palettes."""

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
SPEC_SCHEMA = "character-battle-palette-import-v1"
TABLE_OFFSET = 0x596D5C
TABLE_ENTRY_COUNT = 558
TABLE_ENTRY_SIZE = 16
TABLE_SIZE = TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
PALETTE_POINTER_DELTA = 12
PALETTE_SIZE = 32


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


def _catalog_palettes(
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
    if len(table_bytes) != TABLE_SIZE or _sha256(table_bytes) != table.get("sha256"):
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

    grouped: dict[int, dict[str, Any]] = {}
    populated_rows: set[int] = set()
    resource_reference_count = 0
    for expected_id, resource in enumerate(resources):
        if resource.get("resource_id") != expected_id:
            raise ValueError("character battle visual resource identity mismatch")
        palette = resource.get("palette")
        slot_rows = resource.get("slot_rows")
        if (
            not isinstance(palette, dict)
            or palette.get("size") != PALETTE_SIZE
            or palette.get("color_count") != 16
            or not isinstance(slot_rows, list)
            or not slot_rows
            or slot_rows != sorted(set(slot_rows))
        ):
            raise ValueError(f"resource {expected_id} palette provenance mismatch")
        pointer_text = palette.get("gba_pointer")
        try:
            pointer = int(pointer_text, 16)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"resource {expected_id} palette pointer is invalid"
            ) from error
        offset = pointer - ROM_BASE
        if offset < 0 or offset + PALETTE_SIZE > len(rom):
            raise ValueError(f"resource {expected_id} palette is outside ROM")
        raw = rom[offset : offset + PALETTE_SIZE]
        digest = _sha256(raw)
        if digest != palette.get("sha256"):
            raise ValueError(f"resource {expected_id} palette bytes mismatch")

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
            descriptor = table_bytes[
                row * TABLE_ENTRY_SIZE : (row + 1) * TABLE_ENTRY_SIZE
            ]
            catalog_descriptor = bytes.fromhex(slot.get("descriptor_raw_hex", ""))
            if descriptor != catalog_descriptor:
                raise ValueError(f"slot {row} descriptor bytes mismatch")
            actual_pointer = int.from_bytes(
                descriptor[
                    PALETTE_POINTER_DELTA : PALETTE_POINTER_DELTA + 4
                ],
                "little",
            )
            if actual_pointer != pointer:
                raise ValueError(f"slot {row} palette pointer mismatch")
            aliases.append(
                {
                    "slot_row": row,
                    "character_id": slot["character_id"],
                    "visual_slot": slot["visual_slot"],
                    "resource_id": expected_id,
                    "table_pointer_offset": (
                        TABLE_OFFSET
                        + row * TABLE_ENTRY_SIZE
                        + PALETTE_POINTER_DELTA
                    ),
                }
            )
            populated_rows.add(row)

        row = grouped.setdefault(
            offset,
            {
                "file_offset": offset,
                "palette_pointer": f"0x{pointer:08X}",
                "palette_sha256": digest,
                "source_files": set(),
                "resource_ids": [],
                "slot_rows": [],
                "logical_aliases": [],
            },
        )
        if (
            row["palette_pointer"] != f"0x{pointer:08X}"
            or row["palette_sha256"] != digest
        ):
            raise ValueError("conflicting character battle palette identity")
        source_file = palette.get("file")
        if not isinstance(source_file, str):
            raise ValueError(f"resource {expected_id} palette file is invalid")
        row["source_files"].add(source_file)
        row["resource_ids"].append(expected_id)
        row["slot_rows"].extend(slot_rows)
        row["logical_aliases"].extend(aliases)
        resource_reference_count += 1

    for expected_row, slot in enumerate(slots):
        if slot.get("row") != expected_row:
            raise ValueError("character battle slot ordering mismatch")
        if slot.get("populated") != (expected_row in populated_rows):
            raise ValueError("character battle populated-slot denominator mismatch")

    spans = sorted((offset, offset + PALETTE_SIZE) for offset in grouped)
    if any(
        left_end > right_start
        for (_, left_end), (right_start, _) in zip(spans, spans[1:])
    ):
        raise ValueError("character battle palette physical slots overlap")
    if (
        len(grouped) != 48
        or resource_reference_count != 250
        or len(populated_rows) != 342
        or len({row["palette_sha256"] for row in grouped.values()}) != 40
    ):
        raise ValueError(
            "character battle palette denominator mismatch: "
            f"{len(grouped)}/48 physical, "
            f"{resource_reference_count}/250 resources, "
            f"{len(populated_rows)}/342 slots"
        )

    for row in grouped.values():
        row["source_files"] = sorted(row["source_files"])
        row["resource_ids"] = sorted(row["resource_ids"])
        row["slot_rows"] = sorted(row["slot_rows"])
        row["logical_aliases"] = sorted(
            row["logical_aliases"],
            key=lambda item: (item["slot_row"], item["resource_id"]),
        )
    return grouped


def resolve_character_battle_palette_patches(
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
        raise ValueError("character battle palette source catalog path mismatch")

    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("character battle visual catalog hash mismatch")
    catalog = json.loads(catalog_bytes)
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("character battle palette base ROM hash mismatch")
    palettes = _catalog_palettes(catalog, base)

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("character battle palette edits must be a list")
    seen: set[int] = set()
    patches: list[dict[str, Any]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("character battle palette edit must be an object")
        pointer_text = edit.get("palette_pointer")
        try:
            offset = int(pointer_text, 16) - ROM_BASE
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"unknown character battle palette: {pointer_text}"
            ) from error
        row = palettes.get(offset)
        if (
            row is None
            or pointer_text != row["palette_pointer"]
            or edit.get("palette_sha256") != row["palette_sha256"]
        ):
            raise ValueError(f"unknown character battle palette: {pointer_text}")
        if offset in seen:
            raise ValueError(
                f"duplicate character battle palette: {pointer_text}"
            )
        seen.add(offset)

        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError("character battle palette expected provenance is missing")
        if expected.get("file_offset") != offset:
            raise ValueError("character battle palette file-offset provenance mismatch")
        if expected.get("resource_ids") != row["resource_ids"]:
            raise ValueError("character battle palette resource provenance mismatch")
        if expected.get("slot_rows") != row["slot_rows"]:
            raise ValueError("character battle palette slot-row provenance mismatch")
        source_file = edit.get("source_file")
        if not isinstance(source_file, str):
            raise ValueError("character battle palette source file is missing")
        content = _resolve_path(root, source_file).read_bytes()
        if len(content) != PALETTE_SIZE:
            raise ValueError("character battle palette must be exactly 32 bytes")
        before = base[offset : offset + PALETTE_SIZE]
        if _sha256(before) != row["palette_sha256"]:
            raise ValueError("character battle palette immutable bytes mismatch")
        if content == before:
            continue
        edit_id = edit.get("id")
        if not isinstance(edit_id, str) or not edit_id:
            raise ValueError("character battle palette edit id is missing")
        patches.append(
            {
                "id": f"{edit_id}:palette@{offset:06X}",
                "type": "bytes",
                "offset": offset,
                "before_hex": before.hex(),
                "after_hex": content.hex(),
                "asset_type": "character_battle_palette",
                "palette_pointer": row["palette_pointer"],
                "palette_sha256": row["palette_sha256"],
                "replacement_sha256": _sha256(content),
                "affected_resource_ids": row["resource_ids"],
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
    patches = resolve_character_battle_palette_patches(args.root, args.spec)
    payload = {"patches": patches}
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
