#!/usr/bin/env python3
"""Print the three variants of one battle scenario from the generated table.

The S49 scenario is battle id 14, and the table holds three variants of it.
Which variant a run picks decides whether the bees and 木叶丸 are on the field
at all, so the variants are worth reading directly instead of guessing from a
rendered frame.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEADER = (
    ROOT
    / "butano-sequel/game/include/konoha/generated_battle_scenario_content.h"
)

SLOT = re.compile(
    r"battle_scenario_unit_slot\{\s*(true|false),\s*"
    r"scenario_selector_kind::(\w+),\s*(\d+),\s*"
    r"battle_side::(\w+),\s*"
    r"grid_point\{\s*(\d+),\s*(\d+)\s*\},\s*"
    r"battle_facing::(\w+),\s*(\d+)"
)


def scenario_block(battle_id: int) -> str:
    text = HEADER.read_text(encoding="utf-8")
    parts = text.split("battle_scenario_definition{")[1:]
    for part in parts:
        if int(re.match(r"\s*(\d+)", part).group(1)) == battle_id:
            return part
    raise SystemExit(f"battle id {battle_id} is not in {HEADER}")


def variants(block: str) -> list[list[tuple]]:
    groups = re.split(
        r"std::array<std::array<battle_scenario_unit_slot,\s*12>,\s*3>>\{\{",
        block,
    )
    result = []
    for group in groups[1:4]:
        slots = SLOT.findall(group)
        result.append([slot for slot in slots if slot[0] == "true"])
    return result


def main() -> int:
    battle_id = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    for index, slots in enumerate(variants(scenario_block(battle_id))):
        print(f"--- variant {index}: {len(slots)} enabled units")
        for slot in slots:
            print(
                f"    selector={slot[2]:>3} side={slot[3]:<6} "
                f"pos=({slot[4]},{slot[5]}) facing={slot[6]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
