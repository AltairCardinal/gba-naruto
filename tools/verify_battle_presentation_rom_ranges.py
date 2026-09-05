#!/usr/bin/env python3
"""Verify only the battle-presentation ROM ranges promoted to byte coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ARTIFACT_SCHEMA = "battle-presentation-glyphs-v1"
VERIFY_SCHEMA = "battle-presentation-rom-range-verification-v1"
EXPECTED_SUMMARY = {
    "message_count": 79,
    "glyph_count": 172,
    "unique_glyph_count": 171,
    "bound_glyph_count": 138,
    "unbound_glyph_count": 34,
    "empty_binding_count": 4,
}
TABLES = {
    "messages": (0x5A2B08, 0x5A2C44, 79, 4, "source/message-pointer-table.bin"),
    "glyphs": (0x5A2C44, 0x5A2EF4, 172, 4, "source/glyph-pointer-table.bin"),
    "bindings": (0x5A2EF4, 0x5A320A, 79, 10, "source/message-glyph-binding-table.bin"),
}
CODE_SLICES = {
    "glyph_preloader": (0x09812C, 0x09819C, "4827abc170644bda91140d48a597cd641df061faae15e40d6a83e4b9a29d74ed"),
    "message_measure": (0x0981AC, 0x09822A, "05a03ba78a859cb91cabfb865d3c58c80601054f43def714318c2124df7a9f03"),
    "glyph_display_consumer": (0x098EDC, 0x098FBA, "6af0b1e7ecb858590d4dc422e1b5833f661602ff6137a65518a09aff874a32bc"),
    "message_renderer": (0x098290, 0x098418, "8d599b9b21b70c455b0acb85a916806697f916b0271b8a42a7c8013ed1196804"),
    "message_selector": (0x099564, 0x099582, "835b54df161608218062de4ad9743101456988d29af8fd5c0de165d0b7ebaa47"),
    "presentation_initializer": (0x0983B8, 0x098624, "7a7598a7edfef279bf745897ba5ea0f94e5361e2db84acee7a84a23f06a61422"),
    "sprite_palette_attr2_writer": (0x063108, 0x063120, "3a8ba305e8ed98f95bda2f6e81361571db10e20f0c2158d99930573e4d24ba83"),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_file(artifact: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("artifact source path is invalid")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"artifact source path escapes: {relative}")
    candidate = artifact / path
    resolved = candidate.resolve(strict=True)
    resolved.relative_to(artifact)
    if resolved != candidate.absolute() or not resolved.is_file():
        raise ValueError(f"artifact source uses a symlink: {relative}")
    return resolved


def _verify_tables(
    manifest: dict[str, Any], artifact: Path, rom: bytes
) -> dict[str, bytes]:
    claimed = manifest.get("tables")
    if not isinstance(claimed, dict) or set(claimed) != set(TABLES):
        raise ValueError("battle-presentation table set changed")
    result: dict[str, bytes] = {}
    for name, (start, end, count, size, relative) in TABLES.items():
        table = claimed.get(name)
        raw = rom[start:end]
        if (
            not isinstance(table, dict)
            or table.get("file_offset") != start
            or table.get("gba_address") != f"0x{ROM_BASE + start:08X}"
            or table.get("gba_end") != f"0x{ROM_BASE + end:08X}"
            or table.get("entry_count") != count
            or table.get("entry_size") != size
            or table.get("sha256") != _sha(raw)
            or table.get("raw_file") != relative
            or len(raw) != count * size
            or _safe_file(artifact, relative).read_bytes() != raw
        ):
            raise ValueError(f"battle-presentation {name} table differs from ROM")
        result[name] = raw
    return result


def _verify_messages(
    manifest: dict[str, Any], artifact: Path, rom: bytes, tables: dict[str, bytes]
) -> tuple[int, int]:
    messages = manifest.get("messages")
    if not isinstance(messages, list) or len(messages) != 79:
        raise ValueError("battle-presentation message denominator changed")
    pointers = struct.unpack("<79I", tables["messages"])
    binding_table = tables["bindings"]
    previous_end = -1
    total = 0
    for message_id, (pointer, message) in enumerate(
        zip(pointers, messages, strict=True)
    ):
        if not isinstance(message, dict) or message.get("message_id") != message_id:
            raise ValueError("battle-presentation message IDs changed")
        start = pointer - ROM_BASE
        if message.get("pointer") != f"0x{pointer:08X}" or message.get("file_offset") != start:
            raise ValueError(f"message {message_id} pointer-table binding changed")
        try:
            end = rom.index(b"\0", start, TABLES["messages"][0]) + 1
        except ValueError as error:
            raise ValueError(f"message {message_id} has no NUL terminator") from error
        raw = rom[start:end]
        if start < previous_end or not 0 <= start < end <= TABLES["messages"][0]:
            raise ValueError("battle-presentation message ranges overlap")
        if (
            message.get("raw_size") != len(raw)
            or message.get("raw_sha256") != _sha(raw)
            or message.get("raw_hex") != raw.hex()
            or _safe_file(artifact, message.get("raw_file")).read_bytes() != raw
        ):
            raise ValueError(f"message {message_id} bytes differ from ROM")

        binding = message.get("binding")
        binding_start = message_id * 10
        binding_raw = binding_table[binding_start : binding_start + 10]
        glyph_count = binding_raw[0]
        glyph_ids = list(binding_raw[1 : 1 + glyph_count])
        if (
            not isinstance(binding, dict)
            or glyph_count > 9
            or binding.get("file_offset") != TABLES["bindings"][0] + binding_start
            or binding.get("gba_address")
            != f"0x{ROM_BASE + TABLES['bindings'][0] + binding_start:08X}"
            or binding.get("raw_size") != 10
            or binding.get("raw_hex") != binding_raw.hex()
            or binding.get("glyph_count") != glyph_count
            or binding.get("glyph_ids") != glyph_ids
        ):
            raise ValueError(f"message {message_id} glyph binding changed")
        previous_end = end
        total += len(raw)
    if total != 1_148:
        raise ValueError("battle-presentation message byte denominator changed")
    return len(messages), total


def _verify_glyph_pointer_domain(tables: dict[str, bytes], rom: bytes) -> None:
    pointers = struct.unpack("<172I", tables["glyphs"])
    if len(set(pointers)) != 172:
        raise ValueError("battle-presentation glyph pointer uniqueness changed")
    for pointer in pointers:
        offset = pointer - ROM_BASE
        if not 0 <= offset < len(rom) or rom[offset] != 0x10:
            raise ValueError("battle-presentation glyph pointer domain changed")


def _verify_consumer(manifest: dict[str, Any], rom: bytes) -> None:
    consumer = manifest.get("consumer")
    if not isinstance(consumer, dict):
        raise ValueError("battle-presentation consumer evidence is missing")
    slices = consumer.get("code_slices")
    if not isinstance(slices, list) or len(slices) != len(CODE_SLICES):
        raise ValueError("battle-presentation consumer slice denominator changed")
    by_name = {
        item.get("name"): item for item in slices if isinstance(item, dict)
    }
    if set(by_name) != set(CODE_SLICES):
        raise ValueError("battle-presentation consumer slice set changed")
    for name, (start, end, expected_hash) in CODE_SLICES.items():
        item = by_name[name]
        if (
            item.get("file_offset") != start
            or item.get("gba_start") != f"0x{ROM_BASE + start:08X}"
            or item.get("gba_end") != f"0x{ROM_BASE + end:08X}"
            or item.get("sha256") != expected_hash
            or _sha(rom[start:end]) != expected_hash
        ):
            raise ValueError(f"battle-presentation consumer slice changed: {name}")
    for literal, value in (
        (0x0981A4, 0x085A2EF4),
        (0x0981A8, 0x085A2C44),
        (0x09861C, 0x083E4AF0),
        (0x098620, 0x05000200),
        (0x098FC4, 0x085A2EF4),
        (0x0995E0, 0x085A2B08),
    ):
        if struct.unpack_from("<I", rom, literal)[0] != value:
            raise ValueError(f"battle-presentation literal changed at 0x{literal:X}")


def _verify_palette(
    manifest: dict[str, Any], artifact: Path, rom: bytes
) -> int:
    palette = manifest.get("runtime_palette")
    start, size = 0x3E4AF0, 32
    raw = rom[start : start + size]
    if (
        not isinstance(palette, dict)
        or palette.get("file_offset") != start
        or palette.get("gba_address") != "0x083E4AF0"
        or palette.get("size") != size
        or palette.get("color_count") != 16
        or palette.get("format") != "BGR555"
        or palette.get("sha256") != _sha(raw)
        or palette.get("palette_bank") != 13
        or palette.get("obj_palette_destination") != "0x050003A0"
        or _safe_file(artifact, palette.get("raw_file")).read_bytes() != raw
    ):
        raise ValueError("battle-presentation runtime palette differs from ROM")
    return size


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    message_count = message_bytes = table_bytes = palette_bytes = 0
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact).resolve(strict=True)
        if not artifact.is_dir() or artifact.is_symlink():
            raise ValueError("artifact is not a safe directory")
        rom = (root / "rom/base.gba").read_bytes()
        if _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM SHA-256 changed")
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        if (
            manifest.get("schema") != ARTIFACT_SCHEMA
            or manifest.get("rom")
            != {"file": "rom/base.gba", "sha256": ROM_SHA256}
            or manifest.get("summary") != EXPECTED_SUMMARY
        ):
            raise ValueError("battle-presentation manifest identity changed")
        tables = _verify_tables(manifest, artifact, rom)
        message_count, message_bytes = _verify_messages(
            manifest, artifact, rom, tables
        )
        _verify_glyph_pointer_domain(tables, rom)
        _verify_consumer(manifest, rom)
        palette_bytes = _verify_palette(manifest, artifact, rom)
        table_bytes = sum(len(raw) for raw in tables.values())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "message_count": message_count,
        "message_bytes": message_bytes,
        "table_bytes": table_bytes,
        "palette_bytes": palette_bytes,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/battle-presentation-glyphs-v1"),
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
