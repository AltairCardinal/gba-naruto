#!/usr/bin/env python3
"""W20-E2: regression lock for the formation ``battle_experience`` seeds.

Why this exists
---------------
The battle-14 enemy seeds (``50`` each) are what makes the settlement screen's
「戰鬥分」row non-zero.  They live in the *generated* header
``generated_battle_scenario_content.h``; if that artifact is ever regenerated
from a stale data source, the seeds silently fall back to ``0`` and the
settlement screen loses two number rows **without any test failing**.

This checker therefore asserts the seeds in the artifact itself, against the
values the reverse line extracted from the ROM (E4's
``build/w20-e4/enemy-battle-experience.json``) and the reverse line's
``sequel/content/positions/bank.json``.

Usage::

    python tools/s49_w20e2/check_scenario_seeds.py [--header <path>]

Exit code 0 = every expected seed is present; 1 = a seed is missing or wrong.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

DEFAULT_HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
    r"\generated_battle_scenario_content.h"
)
BANK = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\sequel\content\positions\bank.json"
)
E4_JSON = pathlib.Path(
    r"D:\Github\gba-naruto\build\w20-e4\enemy-battle-experience.json"
)

SCENARIO_HEAD = re.compile(
    r"battle_scenario_definition\{\s*\n\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)U,"
)
INNER_ARRAY = "std::array<battle_scenario_unit_slot, 12>{{"
SLOT_RE = re.compile(
    r"battle_scenario_unit_slot\{\s*"
    r"(true|false),\s*scenario_selector_kind::(\w+),\s*(\d+),\s*"
    r"battle_side::(\w+),\s*grid_point\{\s*(\d+),\s*(\d+)\s*\},\s*"
    r"battle_facing::(\w+),\s*(\d+),"
)


def load_header_slots(path: pathlib.Path) -> dict[tuple[int, int, int], int]:
    text = path.read_text(encoding="utf-8")
    out: dict[tuple[int, int, int], int] = {}
    for head in SCENARIO_HEAD.finditer(text):
        battle_id = int(head.group(1))
        region = text[head.end():]
        starts: list[int] = []
        cursor = 0
        for _ in range(3):
            index = region.find(INNER_ARRAY, cursor)
            if index < 0:
                break
            starts.append(index)
            cursor = index + len(INNER_ARRAY)
        for variant_index, start in enumerate(starts):
            end = (
                starts[variant_index + 1]
                if variant_index + 1 < len(starts)
                else region.find("\n        }}", start)
            )
            for record_index, slot in enumerate(SLOT_RE.finditer(region[start:end])):
                out[(battle_id, variant_index, record_index)] = int(slot.group(8))
    return out


def expected_seeds() -> dict[tuple[int, int, int], int]:
    """The seeds the reverse line read out of the ROM formation table.

    E4's document nests the records as
    ``scenarios[].variants[].units[]`` (each unit carries ``record_id`` and
    ``battle_experience`` plus the ROM offset it was read from).
    """
    if E4_JSON.is_file():
        document = json.loads(E4_JSON.read_text(encoding="utf-8"))
        seeds: dict[tuple[int, int, int], int] = {}
        for scenario in document.get("scenarios") or []:
            battle_id = scenario.get("battle_id", scenario.get("group_id"))
            for variant in scenario.get("variants") or []:
                variant_id = variant.get("variant", variant.get("variant_id"))
                for unit in variant.get("units") or []:
                    record = unit.get("record_id", unit.get("record"))
                    seeds[(battle_id, variant_id, record)] = unit["battle_experience"]
        if seeds:
            return seeds
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    return {
        (row["group_id"], row["variant_id"], row["record_id"]): row["battle_experience"]
        for row in bank["entries"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--header", type=pathlib.Path, default=DEFAULT_HEADER)
    args = parser.parse_args()

    header_slots = load_header_slots(args.header)
    expected = expected_seeds()

    failures: list[str] = []
    checked = 0
    for key, want in sorted(expected.items()):
        if not want:
            continue
        got = header_slots.get(key)
        checked += 1
        if got != want:
            failures.append(f"battle {key[0]:2d} v{key[1]} rec{key[2]:2d}: "
                            f"header={got} expected={want}")

    print(f"header : {args.header}")
    print(f"non-zero seeds expected: {checked}")
    print(f"mismatches            : {len(failures)}")
    for line in failures[:30]:
        print("  ", line)

    # The two scenarios the fidelity work actually depends on.
    for battle_id, variant, records, want in (
        (14, 0, (4, 5, 6, 7, 8), 50),
        (14, 2, (4, 5, 6, 7, 8), 75),
        (41, 0, (1,), 50),
    ):
        for record in records:
            got = header_slots.get((battle_id, variant, record))
            status = "ok" if got == want else "FAIL"
            print(f"  {status:4s} battle {battle_id} v{variant} rec{record}: "
                  f"{got} (want {want})")
            if got != want:
                failures.append(f"pinned battle {battle_id} v{variant} rec{record}")

    if failures:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
