#!/usr/bin/env python3
"""Build a controlled story-opcode fixture and one story visual pointer A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.export_bg_scene_selection import _chapter_roots, _bytes, _decode_node
from tools.inspect_mgba_savestate import load_gba_state
from tools.patch_mgba_savestate_memory import patch_savestate


SCHEMA = "battle-encounters-story-visual-pixel-ab-build-v1"
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PARENT_CHECKPOINT = Path(
    "artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-8.ss9"
)
PARENT_CHECKPOINT_SHA256 = (
    "62adcd52b577f73ca1ffd6d2d4ec3b9fafa2a2b130ac644a6834e2a56a50d4d8"
)
CANONICAL_CHECKPOINT = Path(
    "artifacts/runtime-checkpoints/scenario-53-story-slideshow-command-controlled.ss9"
)
CANONICAL_CHECKPOINT_SHA256 = (
    "65cd8b010f9c21a6d5bc93fe8ed1b84fada025136936f6a42f0d540d0f7ab0a9"
)
CURSOR_ADDRESS = 0x030011F0
PARENT_CURSOR = 0x08031F31
CONTROLLED_CURSOR = 0x08049E63
TABLE_OFFSET = 0x54229C
RECORD_SIZE = 0x10
RECORD_COUNT = 24
RECORD_ID = 0
FIELD_OFFSET = 0
BEFORE_POINTER = 0x0812FF50
AFTER_POINTER = 0x081303E8


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _scenario_command(rom: bytes) -> dict[str, Any]:
    references: set[tuple[str, int]] = set()
    for table, scenario_id, root in _chapter_roots(rom):
        pending = [root]
        visited: set[int] = set()
        while pending:
            address = pending.pop()
            if address in visited:
                continue
            visited.add(address)
            opcode, edges, length = _decode_node(rom, address)
            if address == CONTROLLED_CURSOR:
                if opcode != 0x14 or length != 3:
                    raise ValueError("scenario 53 story command decode mismatch")
                references.add((table, scenario_id))
            pending.extend(edge for edge in edges if edge not in visited)
    raw = _bytes(rom, CONTROLLED_CURSOR, 3)
    if raw != bytes.fromhex("14 68 01") or references != {
        ("primary", 53),
        ("alternate", 53),
    }:
        raise ValueError("scenario 53 story command identity mismatch")
    return {
        "address": f"0x{CONTROLLED_CURSOR:08X}",
        "raw_hex": raw.hex(),
        "opcode": "0x14",
        "state_value": "0x0168",
        "roots": [
            {"table": table, "scenario_id": scenario_id}
            for table, scenario_id in sorted(references)
        ],
    }


def build_pair(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("battle-encounters output must be absent or empty")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != BASE_ROM_SHA256:
        raise ValueError("battle-encounters base ROM mismatch")
    command = _scenario_command(base)

    bank = json.loads(
        (root / "sequel/content/battle-encounters/bank.json").read_text(
            encoding="utf-8"
        )
    )
    entries = bank.get("entries")
    if (
        bank.get("table_offset") != TABLE_OFFSET
        or bank.get("entry_size") != RECORD_SIZE
        or bank.get("entry_count") != RECORD_COUNT
        or not isinstance(entries, list)
        or len(entries) != RECORD_COUNT
        or entries[0].get("gfx_lz_ptr") != BEFORE_POINTER
        or entries[1].get("gfx_lz_ptr") != AFTER_POINTER
    ):
        raise ValueError("battle-encounters descriptor bank mismatch")

    parent_path = root / PARENT_CHECKPOINT
    parent = parent_path.read_bytes()
    if _sha256(parent) != PARENT_CHECKPOINT_SHA256:
        raise ValueError("battle-encounters parent checkpoint mismatch")
    if load_gba_state(parent_path).read_u32(CURSOR_ADDRESS) != PARENT_CURSOR:
        raise ValueError("battle-encounters parent cursor mismatch")
    fixture = patch_savestate(
        parent,
        [(CURSOR_ADDRESS, struct.pack("<I", CONTROLLED_CURSOR))],
    )
    canonical = (root / CANONICAL_CHECKPOINT).read_bytes()
    if _sha256(canonical) != CANONICAL_CHECKPOINT_SHA256 or canonical != fixture:
        raise ValueError("battle-encounters canonical checkpoint mismatch")

    patch_offset = TABLE_OFFSET + RECORD_ID * RECORD_SIZE + FIELD_OFFSET
    before = struct.pack("<I", BEFORE_POINTER)
    after = struct.pack("<I", AFTER_POINTER)
    if base[patch_offset : patch_offset + 4] != before:
        raise ValueError("battle-encounters source pointer mismatch")
    candidate_buffer = bytearray(base)
    candidate_buffer[patch_offset : patch_offset + 4] = after
    candidate = bytes(candidate_buffer)
    changed_offsets = [
        index
        for index, pair in enumerate(zip(base, candidate, strict=True))
        if pair[0] != pair[1]
    ]
    if changed_offsets != [patch_offset, patch_offset + 1, patch_offset + 2]:
        raise ValueError("battle-encounters pointer edit isolation mismatch")

    output.mkdir(parents=True, exist_ok=True)
    input_dir = output / "input"
    input_dir.mkdir()
    fixture_path = input_dir / "controlled-story-opcode.ss9"
    fixture_path.write_bytes(fixture)
    if load_gba_state(fixture_path).read_u32(CURSOR_ADDRESS) != CONTROLLED_CURSOR:
        raise ValueError("battle-encounters controlled fixture cursor mismatch")

    variants: dict[str, dict[str, object]] = {}
    for name, rom in (("baseline", base), ("candidate", candidate)):
        variant_dir = output / name
        variant_dir.mkdir()
        rom_path = variant_dir / f"{name}.gba"
        rom_path.write_bytes(rom)
        variants[name] = {
            "rom_path": rom_path.relative_to(output).as_posix(),
            "rom_sha256": _sha256(rom),
            "rom_size": len(rom),
        }

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "source_rom": "rom/base.gba",
        "source_rom_sha256": BASE_ROM_SHA256,
        "source_bank": "sequel/content/battle-encounters/bank.json",
        "source_bank_sha256": _sha256(
            (root / "sequel/content/battle-encounters/bank.json").read_bytes()
        ),
        "input_state": fixture_path.relative_to(output).as_posix(),
        "input_state_sha256": _sha256(fixture),
        "input_mode": "single-a-controlled-script-cursor",
        "inputs": [
            {"key": "A", "down_frame": 2, "up_frame": 10, "hold_frames": 8}
        ],
        "capture_boundary": "first descriptor overlay after eighth VBlank",
        "controlled_entry": {
            "parent_checkpoint": PARENT_CHECKPOINT.as_posix(),
            "parent_checkpoint_sha256": PARENT_CHECKPOINT_SHA256,
            "parent_cursor": f"0x{PARENT_CURSOR:08X}",
            "canonical_checkpoint": CANONICAL_CHECKPOINT.as_posix(),
            "canonical_checkpoint_sha256": CANONICAL_CHECKPOINT_SHA256,
            "fixture_cursor": f"0x{CONTROLLED_CURSOR:08X}",
            "cursor_address": f"0x{CURSOR_ADDRESS:08X}",
            "fixture_edit_kind": "script-cursor-only",
            "scenario_command": command,
        },
        "edit": {
            "record_id": RECORD_ID,
            "field": "gfx_lz_ptr",
            "rom_offset": patch_offset,
            "rom_address": f"0x{0x08000000 + patch_offset:08X}",
            "before_pointer": f"0x{BEFORE_POINTER:08X}",
            "after_pointer": f"0x{AFTER_POINTER:08X}",
            "before_bytes": before.hex(),
            "after_bytes": after.hex(),
            "changed_rom_offsets": changed_offsets,
        },
        "variants": variants,
        "boundary": {
            "runtime_consumer_and_pixel_causality": True,
            "natural_scenario_53_navigation": False,
            "all_24_records_runtime_covered": False,
            "physical_gba_verified": False,
        },
    }
    _write_json(output / "build-manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = build_pair(args.root, args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
