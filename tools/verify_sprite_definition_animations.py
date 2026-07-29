#!/usr/bin/env python3
"""Independently verify the generic Sprite animation timeline artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAIR_TABLE_OFFSET = 0x53F140
ENTRY_COUNT = 43
ENTRY_SIZE = 8
STATIC_ARTIFACT = Path("artifacts/sprite-definition-assets-v2")
OUTPUT_ARTIFACT = Path("artifacts/sprite-definition-animations-v1")
CODE_SLICES = (
    ("generic_sprite_loader", 0x08080B08, 0x08080B7C,
     "ff28fa10e4606f706a4fd4986126d8a14fe2baf66f1cc2621c5fe6b15d2ff8c2"),
    ("allocator_flags", 0x0806262C, 0x08062632,
     "037cf2c2f1e3e36347c438806e1dad9c525b2b93d1aeb2fb8b2600b8fdf3709d"),
    ("animation_zero_and_pair_install", 0x08062654, 0x08062678,
     "41c3013f14bb788fe58c8e2a4915989209161d3ad69237a78c6649fe53ace385"),
    ("sequence_select", 0x0806298C, 0x080629A0,
     "62718fbb246078256e2c3344773d0ab9a0b2c10aee2fb3890d16e134b331e1ab"),
    ("animation_tick", 0x08063256, 0x0806327A,
     "7b345c6e3bea9594393aa55bebee00bf1750040c02224169f9d44723f0282a64"),
    ("terminal_policy", 0x08063284, 0x080632D8,
     "9cfe00688a2b0e339e870ca2281b5c9c253aeaedffdd6c40130dba6976334020"),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _contact(source: Path, entry_id: int) -> bytes:
    with Image.open(source) as image:
        frame = image.convert("RGBA")
    sheet = Image.new("RGBA", (240, 190), (0, 0, 0, 255))
    sheet.alpha_composite(
        frame,
        ((240 - frame.width) // 2, (160 - frame.height) // 2),
    )
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, 160, 239, 189), fill=(20, 20, 20, 255))
    draw.text(
        (8, 169),
        f"sprite {entry_id:02d}: frame 0, hold 1, stop",
        fill=(255, 255, 255, 255),
    )
    output = BytesIO()
    sheet.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def verify_sprite_definition_animations(
    root: Path,
    artifact_dir: Path = OUTPUT_ARTIFACT,
) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.is_absolute():
        artifact_dir = root / artifact_dir
    errors: list[str] = []
    try:
        manifest_bytes = (artifact_dir / "manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as error:
        return {
            "schema": "sprite-definition-animations-verification-v1",
            "verified_entries": 0,
            "errors": [f"cannot read manifest: {error}"],
        }

    try:
        rom = (root / "rom/base.gba").read_bytes()
        if _sha256(rom) != ROM_SHA256:
            errors.append("base ROM SHA-256 mismatch")
        static_path = root / STATIC_ARTIFACT / "manifest.json"
        static_bytes = static_path.read_bytes()
        static = json.loads(static_bytes)
        static_by_id = {entry["id"]: entry for entry in static["entries"]}
        for name, start, end, expected in CODE_SLICES:
            if _sha256(rom[start - ROM_BASE : end - ROM_BASE]) != expected:
                errors.append(f"{name} code slice SHA-256 mismatch")
    except (OSError, KeyError, json.JSONDecodeError) as error:
        return {
            "schema": "sprite-definition-animations-verification-v1",
            "verified_entries": 0,
            "errors": [*errors, f"cannot read ROM/static source: {error}"],
        }

    if manifest.get("schema") != "sprite-definition-animations-v1":
        errors.append("unexpected manifest schema")
    if manifest.get("rom") != {
        "path": "rom/base.gba",
        "size": len(rom),
        "sha256": _sha256(rom),
    }:
        errors.append("ROM identity mismatch")
    if manifest.get("pair_table") != {
        "file_offset": PAIR_TABLE_OFFSET,
        "gba_address": f"0x{ROM_BASE + PAIR_TABLE_OFFSET:08X}",
        "entry_count": ENTRY_COUNT,
        "entry_size": ENTRY_SIZE,
    }:
        errors.append("pair table contract mismatch")
    if manifest.get("code_slices") != [
        {
            "name": name,
            "start_gba_address": f"0x{start:08X}",
            "end_gba_address_exclusive": f"0x{end:08X}",
            "sha256": digest,
        }
        for name, start, end, digest in CODE_SLICES
    ]:
        errors.append("code slice manifest mismatch")
    if manifest.get("entry_count") != ENTRY_COUNT:
        errors.append("entry count mismatch")
    if manifest.get("sequence_count") != ENTRY_COUNT:
        errors.append("sequence count mismatch")
    if manifest.get("keyframe_count") != ENTRY_COUNT:
        errors.append("keyframe count mismatch")
    if manifest.get("single_frame_sequence_count") != ENTRY_COUNT:
        errors.append("single-frame count mismatch")
    if manifest.get("terminated_sequence_count") != ENTRY_COUNT:
        errors.append("terminated count mismatch")
    if manifest.get("looping_sequence_count") != 0:
        errors.append("looping count mismatch")
    if manifest.get("source_artifact") != {
        "path": str(STATIC_ARTIFACT),
        "manifest_sha256": _sha256(static_bytes),
    }:
        errors.append("source artifact identity mismatch")
    expected_consumer = {
        "sequence_select": "0x0806298C..0x080629A0",
        "animation_tick": "0x08063256..0x0806327A",
        "terminal_policy": "0x08063284..0x080632D8",
        "record_size": 4,
        "record_schema": ["s16 frame_index", "s16 duration_ticks"],
        "terminator_frame_index": -1,
        "generic_task_flags": "0x00000049",
        "generic_terminal_policy": "stop",
    }
    if manifest.get("consumer") != expected_consumer:
        errors.append("consumer contract mismatch")
    if manifest.get("scope") != {
        "all_generic_sprite_entries": True,
        "animation_zero_used_by_natural_loader": True,
        "frame_duration_and_terminator_complete": True,
        "generic_task_terminal_policy_complete": True,
        "scene_specific_overwrite_checked": False,
    }:
        errors.append("scope contract mismatch")

    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != ENTRY_COUNT:
        errors.append("manifest entries mismatch")
        entries = []
    referenced = {"manifest.json"}
    verified = 0
    for entry_id, item in enumerate(entries):
        try:
            pair_offset = PAIR_TABLE_OFFSET + entry_id * ENTRY_SIZE
            definition_pointer, animation_pointer = struct.unpack_from(
                "<II",
                rom,
                pair_offset,
            )
            sequence_pointer = struct.unpack_from(
                "<I",
                rom,
                animation_pointer - ROM_BASE,
            )[0]
            sequence_offset = sequence_pointer - ROM_BASE
            frame_index, duration = struct.unpack_from(
                "<hh",
                rom,
                sequence_offset,
            )
            terminal_frame, terminal_duration = struct.unpack_from(
                "<hh",
                rom,
                sequence_offset + 4,
            )
            raw = rom[sequence_offset : sequence_offset + 8]
            if sequence_pointer != definition_pointer + 4:
                errors.append(f"entry {entry_id} sequence pointer mismatch")
            if (frame_index, duration) != (0, 1):
                errors.append(f"entry {entry_id} keyframe record mismatch")
            if (terminal_frame, terminal_duration) != (-1, 0):
                errors.append(f"entry {entry_id} terminator mismatch")

            timeline_name = item["timeline_json"]
            contact_name = item["contact_sheet_png"]
            if Path(timeline_name).name != timeline_name:
                errors.append(f"entry {entry_id} unsafe timeline path")
            if Path(contact_name).name != contact_name:
                errors.append(f"entry {entry_id} unsafe contact path")
            referenced.update((timeline_name, contact_name))
            timeline_bytes = (artifact_dir / timeline_name).read_bytes()
            contact_bytes = (artifact_dir / contact_name).read_bytes()
            timeline = json.loads(timeline_bytes)
            if item.get("id") != entry_id or timeline.get("id") != entry_id:
                errors.append(f"entry {entry_id} ID mismatch")
            if item.get("animation_table_pointer") != f"0x{animation_pointer:08X}":
                errors.append(f"entry {entry_id} animation pointer mismatch")
            if item.get("sequence_pointer") != f"0x{sequence_pointer:08X}":
                errors.append(f"entry {entry_id} sequence address mismatch")
            if item.get("sequence_sha256") != _sha256(raw):
                errors.append(f"entry {entry_id} sequence hash mismatch")
            if item.get("keyframe_count") != 1:
                errors.append(f"entry {entry_id} keyframe count mismatch")
            if item.get("total_duration_ticks") != 1:
                errors.append(f"entry {entry_id} summary duration mismatch")
            if item.get("terminal_policy") != "stop":
                errors.append(f"entry {entry_id} terminal policy mismatch")
            if timeline.get("schema") != (
                "sprite-definition-animation-entry-v1"
            ):
                errors.append(f"entry {entry_id} timeline schema mismatch")
            if timeline.get("definition_pointer") != (
                f"0x{definition_pointer:08X}"
            ):
                errors.append(f"entry {entry_id} definition pointer mismatch")
            if timeline.get("animation_table_pointer") != (
                f"0x{animation_pointer:08X}"
            ):
                errors.append(
                    f"entry {entry_id} timeline animation pointer mismatch"
                )
            if timeline.get("sequence_pointer") != (
                f"0x{sequence_pointer:08X}"
            ):
                errors.append(
                    f"entry {entry_id} timeline sequence pointer mismatch"
                )
            if timeline.get("sequence_sha256") != _sha256(raw):
                errors.append(
                    f"entry {entry_id} timeline sequence hash mismatch"
                )
            if timeline.get("sequence_raw_hex") != raw.hex():
                errors.append(f"entry {entry_id} raw sequence mismatch")
            if timeline.get("keyframes") != [
                {"frame_index": 0, "duration_ticks": 1}
            ]:
                errors.append(f"entry {entry_id} timeline keyframes mismatch")
            if timeline.get("terminator") != {
                "frame_index": -1,
                "raw_hex": "ffff0000",
                "generic_task_flags": "0x00000049",
                "policy": "stop",
            }:
                errors.append(f"entry {entry_id} timeline terminator mismatch")
            if timeline.get("total_duration_ticks") != 1:
                errors.append(f"entry {entry_id} duration mismatch")
            if _sha256(timeline_bytes) != item.get("timeline_json_sha256"):
                errors.append(f"{timeline_name} hash mismatch")

            source = static_by_id[entry_id]
            if item.get("source_png") != source["asset"]["png"]:
                errors.append(f"entry {entry_id} source PNG mismatch")
            if item.get("source_png_sha256") != source["asset"]["png_sha256"]:
                errors.append(f"entry {entry_id} source PNG hash mismatch")
            expected_contact = _contact(
                root / STATIC_ARTIFACT / source["asset"]["png"],
                entry_id,
            )
            if contact_bytes != expected_contact:
                errors.append(f"{contact_name} independent rebuild mismatch")
            if _sha256(contact_bytes) != item.get("contact_sheet_png_sha256"):
                errors.append(f"{contact_name} hash mismatch")
            verified += 1
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            struct.error,
            json.JSONDecodeError,
        ) as error:
            errors.append(f"entry {entry_id} invalid: {error}")

    try:
        actual_files = {
            path.name for path in artifact_dir.iterdir() if path.is_file()
        }
        if actual_files != referenced:
            errors.append("artifact file set mismatch")
        if manifest.get("artifact_files") != sorted(referenced):
            errors.append("manifest artifact file list mismatch")
        if manifest.get("artifact_file_count") != len(referenced):
            errors.append("manifest artifact file count mismatch")
    except OSError as error:
        errors.append(f"cannot enumerate artifact files: {error}")

    return {
        "schema": "sprite-definition-animations-verification-v1",
        "verified_entries": verified,
        "manifest_sha256": _sha256(manifest_bytes),
        "errors": sorted(set(errors)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact-dir", type=Path, default=OUTPUT_ARTIFACT)
    args = parser.parse_args()
    result = verify_sprite_definition_animations(
        args.root,
        args.artifact_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
