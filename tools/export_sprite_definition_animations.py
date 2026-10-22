#!/usr/bin/env python3
"""Export all generic Sprite animation streams as editor timelines."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import tempfile
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
GENERIC_TASK_FLAGS = 0x49
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


def _pointer(value: int) -> str:
    return f"0x{value:08X}"


def _offset(pointer: int, size: int) -> int:
    result = pointer - ROM_BASE
    if not 0 <= result < size:
        raise ValueError(f"pointer {_pointer(pointer)} outside ROM")
    return result


def _parse_sequence(
    rom: bytes,
    pointer: int,
) -> tuple[list[dict[str, int]], dict[str, Any], bytes]:
    cursor = _offset(pointer, len(rom))
    start = cursor
    keyframes: list[dict[str, int]] = []
    while len(keyframes) < 64:
        frame_index, duration = struct.unpack_from("<hh", rom, cursor)
        raw = rom[cursor : cursor + 4]
        if frame_index == -1:
            return (
                keyframes,
                {
                    "frame_index": -1,
                    "raw_hex": raw.hex(),
                    "generic_task_flags": f"0x{GENERIC_TASK_FLAGS:08X}",
                    "policy": (
                        "loop"
                        if GENERIC_TASK_FLAGS & 0x30 == 0x20
                        else "callback"
                        if GENERIC_TASK_FLAGS & 0x30 == 0x30
                        else "stop"
                    ),
                },
                rom[start : cursor + 4],
            )
        if frame_index < 0 or duration <= 0:
            raise ValueError(
                f"invalid animation record at {_pointer(ROM_BASE + cursor)}"
            )
        keyframes.append(
            {
                "frame_index": frame_index,
                "duration_ticks": duration,
            }
        )
        cursor += 4
    raise ValueError(f"animation at {_pointer(pointer)} is unbounded")


def _contact_sheet(source: Path, entry_id: int) -> bytes:
    with Image.open(source) as image:
        frame = image.convert("RGBA")
    sheet = Image.new("RGBA", (240, 190), (0, 0, 0, 255))
    x = (240 - frame.width) // 2
    y = (160 - frame.height) // 2
    sheet.alpha_composite(frame, (x, y))
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


def _build_outputs(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    static_manifest_path = root / STATIC_ARTIFACT / "manifest.json"
    static_bytes = static_manifest_path.read_bytes()
    static = json.loads(static_bytes)
    if static.get("schema") != "sprite-definition-assets-v2":
        raise ValueError("unexpected static Sprite artifact schema")
    static_by_id = {entry["id"]: entry for entry in static["entries"]}
    for name, start, end, expected in CODE_SLICES:
        if _sha256(rom[start - ROM_BASE : end - ROM_BASE]) != expected:
            raise ValueError(f"{name} code slice SHA-256 mismatch")

    files: dict[str, bytes] = {}
    entries: list[dict[str, Any]] = []
    keyframe_count = 0
    for entry_id in range(ENTRY_COUNT):
        pair_offset = PAIR_TABLE_OFFSET + entry_id * ENTRY_SIZE
        definition_pointer, animation_table_pointer = struct.unpack_from(
            "<II",
            rom,
            pair_offset,
        )
        animation_table_offset = _offset(animation_table_pointer, len(rom))
        sequence_pointer = struct.unpack_from(
            "<I",
            rom,
            animation_table_offset,
        )[0]
        keyframes, terminator, raw = _parse_sequence(rom, sequence_pointer)
        if sequence_pointer != definition_pointer + 4:
            raise ValueError(
                f"entry {entry_id} sequence is not definition + 4"
            )
        if not keyframes:
            raise ValueError(f"entry {entry_id} has no visible keyframe")
        if any(frame["frame_index"] != 0 for frame in keyframes):
            raise ValueError(f"entry {entry_id} references unknown frame")

        timeline = {
            "schema": "sprite-definition-animation-entry-v1",
            "id": entry_id,
            "definition_pointer": _pointer(definition_pointer),
            "animation_table_pointer": _pointer(animation_table_pointer),
            "sequence_pointer": _pointer(sequence_pointer),
            "sequence_raw_hex": raw.hex(),
            "sequence_sha256": _sha256(raw),
            "keyframes": keyframes,
            "terminator": terminator,
            "total_duration_ticks": sum(
                frame["duration_ticks"] for frame in keyframes
            ),
        }
        timeline_name = f"sprite-id-{entry_id:02d}-timeline.json"
        timeline_bytes = (
            json.dumps(timeline, ensure_ascii=False, indent=2) + "\n"
        ).encode()
        source = static_by_id[entry_id]
        source_png = source["asset"]["png"]
        contact_name = f"sprite-id-{entry_id:02d}-contact.png"
        contact = _contact_sheet(
            root / STATIC_ARTIFACT / source_png,
            entry_id,
        )
        files[timeline_name] = timeline_bytes
        files[contact_name] = contact
        entries.append(
            {
                "id": entry_id,
                "animation_table_pointer": _pointer(animation_table_pointer),
                "sequence_pointer": _pointer(sequence_pointer),
                "sequence_sha256": _sha256(raw),
                "keyframe_count": len(keyframes),
                "total_duration_ticks": timeline["total_duration_ticks"],
                "terminal_policy": terminator["policy"],
                "timeline_json": timeline_name,
                "timeline_json_sha256": _sha256(timeline_bytes),
                "source_png": source_png,
                "source_png_sha256": source["asset"]["png_sha256"],
                "contact_sheet_png": contact_name,
                "contact_sheet_png_sha256": _sha256(contact),
            }
        )
        keyframe_count += len(keyframes)

    manifest = {
        "schema": "sprite-definition-animations-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": _sha256(rom),
        },
        "source_artifact": {
            "path": str(STATIC_ARTIFACT),
            "manifest_sha256": _sha256(static_bytes),
        },
        "pair_table": {
            "file_offset": PAIR_TABLE_OFFSET,
            "gba_address": _pointer(ROM_BASE + PAIR_TABLE_OFFSET),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
        },
        "consumer": {
            "sequence_select": "0x0806298C..0x080629A0",
            "animation_tick": "0x08063256..0x0806327A",
            "terminal_policy": "0x08063284..0x080632D8",
            "record_size": 4,
            "record_schema": ["s16 frame_index", "s16 duration_ticks"],
            "terminator_frame_index": -1,
            "generic_task_flags": f"0x{GENERIC_TASK_FLAGS:08X}",
            "generic_terminal_policy": "stop",
        },
        "code_slices": [
            {
                "name": name,
                "start_gba_address": _pointer(start),
                "end_gba_address_exclusive": _pointer(end),
                "sha256": digest,
            }
            for name, start, end, digest in CODE_SLICES
        ],
        "entry_count": len(entries),
        "sequence_count": len(entries),
        "keyframe_count": keyframe_count,
        "single_frame_sequence_count": sum(
            entry["keyframe_count"] == 1 for entry in entries
        ),
        "terminated_sequence_count": sum(
            entry["terminal_policy"] == "stop" for entry in entries
        ),
        "looping_sequence_count": sum(
            entry["terminal_policy"] == "loop" for entry in entries
        ),
        "scope": {
            "all_generic_sprite_entries": True,
            "animation_zero_used_by_natural_loader": True,
            "frame_duration_and_terminator_complete": True,
            "generic_task_terminal_policy_complete": True,
            "scene_specific_overwrite_checked": False,
        },
        "artifact_file_count": 1 + len(files),
        "artifact_files": sorted(["manifest.json", *files]),
        "entries": entries,
    }
    files["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    return manifest, files


def export_sprite_definition_animations(
    root: Path,
    output_dir: Path = OUTPUT_ARTIFACT,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    manifest, files = _build_outputs(root)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".sprite-definition-animations-",
        dir=output_dir.parent,
    ) as temporary:
        staging = Path(temporary)
        for name, payload in files.items():
            (staging / name).write_bytes(payload)
        output_dir.mkdir(parents=True, exist_ok=True)
        for path in output_dir.iterdir():
            if path.is_file() and path.name not in files:
                path.unlink()
        for name in sorted(files):
            (staging / name).replace(output_dir / name)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_ARTIFACT)
    args = parser.parse_args()
    manifest = export_sprite_definition_animations(
        args.root,
        args.output_dir,
    )
    print(
        f"Exported {manifest['sequence_count']} generic Sprite animations "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
