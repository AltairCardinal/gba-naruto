#!/usr/bin/env python3
"""Extract ROM-backed battle rewards and character EXP thresholds."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


SCENARIO_REWARD_MAP_FILE = 0x348DAC
SCENARIO_REWARD_MAP_COUNT = 48
REWARD_TABLE_FILE = 0x59EAE0
REWARD_RECORD_SIZE = 0x18
REWARD_RECORD_COUNT = 112
EXPERIENCE_THRESHOLD_TABLE_FILE = 0x59F560
EXPERIENCE_THRESHOLD_RECORD_SIZE = 4
EXPERIENCE_THRESHOLD_COUNT = 63


def extract_battle_result_content(rom: bytes) -> dict[str, Any]:
    """Extract the exact tables consumed by the original result flow."""
    last_end = (
        EXPERIENCE_THRESHOLD_TABLE_FILE
        + EXPERIENCE_THRESHOLD_RECORD_SIZE * EXPERIENCE_THRESHOLD_COUNT
    )
    if len(rom) < last_end:
        raise ValueError(
            f"ROM too small for battle-result tables: "
            f"need 0x{last_end:X}, got 0x{len(rom):X}"
        )

    rewards: list[dict[str, Any]] = []
    for record_id in range(REWARD_RECORD_COUNT):
        offset = REWARD_TABLE_FILE + record_id * REWARD_RECORD_SIZE
        raw = rom[offset:offset + REWARD_RECORD_SIZE]
        rewards.append(
            {
                "record_id": record_id,
                "rom_offset": offset,
                "rom_offset_hex": f"0x{offset:06X}",
                "mission_experience": int.from_bytes(raw[0:2], "little"),
                "round_bonus_experience": int.from_bytes(
                    raw[2:4], "little"
                ),
                "round_limit": int.from_bytes(raw[4:6], "little"),
                "postbattle_words": [
                    int.from_bytes(raw[index:index + 2], "little")
                    for index in range(6, REWARD_RECORD_SIZE, 2)
                ],
                "raw_hex": raw.hex(),
            }
        )

    thresholds: list[dict[str, Any]] = []
    for character_id in range(EXPERIENCE_THRESHOLD_COUNT):
        offset = (
            EXPERIENCE_THRESHOLD_TABLE_FILE
            + character_id * EXPERIENCE_THRESHOLD_RECORD_SIZE
        )
        raw = rom[offset:offset + EXPERIENCE_THRESHOLD_RECORD_SIZE]
        thresholds.append(
            {
                "character_id": character_id,
                "rom_offset": offset,
                "rom_offset_hex": f"0x{offset:06X}",
                "per_level_increment": int.from_bytes(raw[0:2], "little"),
                "base_threshold": int.from_bytes(raw[2:4], "little"),
                "raw_hex": raw.hex(),
            }
        )

    mapping = list(
        rom[
            SCENARIO_REWARD_MAP_FILE:
            SCENARIO_REWARD_MAP_FILE + SCENARIO_REWARD_MAP_COUNT
        ]
    )
    return {
        "version": 1,
        "description": (
            "ROM-backed battle reward records, scenario-to-reward mapping, "
            "and per-character level thresholds."
        ),
        "verification": "static_and_runtime_verified",
        "evidence": [
            "build/test-results/battle-result-engine-89310-20260725-297.txt",
            "build/test-results/result-level-preview-8983c-20260725-304.txt",
            "build/test-results/result-level-settle-898e0-20260725-306.txt",
        ],
        "scenario_reward_map": {
            "table_offset": SCENARIO_REWARD_MAP_FILE,
            "table_offset_hex": f"0x{SCENARIO_REWARD_MAP_FILE:06X}",
            "entry_count": SCENARIO_REWARD_MAP_COUNT,
        },
        "scenario_reward_record_indices": mapping,
        "reward_table": {
            "table_offset": REWARD_TABLE_FILE,
            "table_offset_hex": f"0x{REWARD_TABLE_FILE:06X}",
            "entry_count": REWARD_RECORD_COUNT,
            "entry_size": REWARD_RECORD_SIZE,
        },
        "reward_records": rewards,
        "experience_threshold_table": {
            "table_offset": EXPERIENCE_THRESHOLD_TABLE_FILE,
            "table_offset_hex": f"0x{EXPERIENCE_THRESHOLD_TABLE_FILE:06X}",
            "entry_count": EXPERIENCE_THRESHOLD_COUNT,
            "entry_size": EXPERIENCE_THRESHOLD_RECORD_SIZE,
        },
        "experience_thresholds": thresholds,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--bank", type=Path)
    args = parser.parse_args()
    bank = extract_battle_result_content(args.rom.read_bytes())
    if args.bank:
        write_json_atomic(args.bank, bank)
        print(
            f"wrote {len(bank['reward_records'])} reward records and "
            f"{len(bank['experience_thresholds'])} thresholds to {args.bank}"
        )
    else:
        json.dump(bank, __import__("sys").stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
