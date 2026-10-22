#!/usr/bin/env python3
"""Encode semantic chapter scripts and plan guarded payload+pointer patches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from tools.chapter_script_codec import decode_script, encode_script
except ModuleNotFoundError:
    from chapter_script_codec import decode_script, encode_script


ROM_BASE = 0x08000000
DEFAULT_TABLE_OFFSETS = {
    "primary": 0x60C74,
    "alternate": 0x60D54,
}
FREE_SPACE_START = 0x5F8000
FREE_SPACE_END = 0x600000


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValueError(f"{field} must be an integer") from exc
    raise ValueError(f"{field} must be an integer")


def resolve_chapter_script_patches(
    spec_path: Path,
    *,
    rom: bytes,
    free_space_start: int = FREE_SPACE_START,
    free_space_end: int = FREE_SPACE_END,
    table_offsets: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Validate every script first, then return one atomic build patch plan."""
    tables = DEFAULT_TABLE_OFFSETS if table_offsets is None else table_offsets
    if not 0 <= free_space_start < free_space_end <= len(rom):
        raise ValueError("chapter free-space partition is outside ROM")
    if any(byte != 0xFF for byte in rom[free_space_start:free_space_end]):
        raise ValueError("chapter free-space partition is not entirely 0xFF")

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("version") != 1 or not isinstance(spec.get("scripts"), list):
        raise ValueError("chapter script spec requires version 1 and a scripts list")

    cursor = free_space_start
    seen_targets: set[tuple[str, int]] = set()
    seen_ids: set[str] = set()
    planned: list[dict[str, Any]] = []
    for item in spec["scripts"]:
        if not isinstance(item, dict):
            raise ValueError("chapter script entry must be an object")
        if not item.get("enabled", True):
            continue
        script_id = item.get("id")
        if not isinstance(script_id, str) or not script_id:
            raise ValueError("chapter script id must be a non-empty string")
        if script_id in seen_ids:
            raise ValueError(f"duplicate chapter script id {script_id!r}")
        seen_ids.add(script_id)

        table = item.get("table")
        if table not in tables:
            raise ValueError(f"chapter script {script_id}: unknown table {table!r}")
        scenario_id = _integer(item.get("scenario_id"), "scenario_id")
        if not 1 <= scenario_id < 56:
            raise ValueError(f"chapter script {script_id}: scenario_id must be in 1..55")
        target = (table, scenario_id)
        if target in seen_targets:
            raise ValueError(f"duplicate chapter script target {table}[{scenario_id}]")
        seen_targets.add(target)

        pointer_offset = tables[table] + scenario_id * 4
        if not 0 <= pointer_offset <= len(rom) - 4:
            raise ValueError(f"chapter script {script_id}: pointer slot is outside ROM")
        base_pointer = _integer(item.get("base_script_ptr"), "base_script_ptr")
        actual_pointer = int.from_bytes(rom[pointer_offset:pointer_offset + 4], "little")
        if actual_pointer != base_pointer:
            raise ValueError(
                f"chapter script {script_id}: base pointer mismatch: "
                f"spec 0x{base_pointer:08X}, ROM 0x{actual_pointer:08X}"
            )

        commands = item.get("commands")
        base_range = item.get("base_script_range")
        if isinstance(commands, list) and base_range is None:
            payload = encode_script(commands)
        elif commands is None and isinstance(base_range, dict):
            source_offset = _integer(base_range.get("offset"), "base_script_range.offset")
            source_length = _integer(base_range.get("length"), "base_script_range.length")
            if source_length <= 0 or not 0 <= source_offset <= len(rom) - source_length:
                raise ValueError(f"chapter script {script_id}: base script range is outside ROM")
            if base_pointer != ROM_BASE + source_offset:
                raise ValueError(
                    f"chapter script {script_id}: base range does not begin at base_script_ptr"
                )
            source = rom[source_offset:source_offset + source_length]
            payload = encode_script(decode_script(source))
            if payload != source:
                raise ValueError(f"chapter script {script_id}: semantic round-trip changed bytes")
        else:
            raise ValueError(
                f"chapter script {script_id}: provide exactly one of commands or base_script_range"
            )
        cursor = (cursor + 3) & ~3
        if cursor + len(payload) > free_space_end:
            raise ValueError(
                f"chapter script free space exhausted by {script_id}: "
                f"need {len(payload)} bytes at 0x{cursor:X}"
            )
        planned.append({
            "id": f"chapter.{script_id}.payload",
            "type": "bytes",
            "offset": cursor,
            "before_hex": rom[cursor:cursor + len(payload)].hex(),
            "after_hex": payload.hex(),
            "source_entry": script_id,
            "method": "chapter_script_allocation",
        })
        planned.append({
            "id": f"chapter.{script_id}.redirect",
            "type": "pointer_redirect",
            "pointer_table_offset": pointer_offset,
            "expected_pointer_hex": actual_pointer.to_bytes(4, "little").hex(),
            "new_pointer_hex": (ROM_BASE + cursor).to_bytes(4, "little").hex(),
            "source_entry": script_id,
            "method": "chapter_script_redirect",
        })
        cursor += len(payload)
    return planned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--free-space-start", default=hex(FREE_SPACE_START))
    parser.add_argument("--free-space-end", default=hex(FREE_SPACE_END))
    args = parser.parse_args()
    patches = resolve_chapter_script_patches(
        args.spec,
        rom=args.rom.read_bytes(),
        free_space_start=int(args.free_space_start, 0),
        free_space_end=int(args.free_space_end, 0),
    )
    print(json.dumps({"patches": patches}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
