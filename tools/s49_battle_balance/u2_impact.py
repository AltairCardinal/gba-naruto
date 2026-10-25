#!/usr/bin/env python3
"""U2 (wave 10): impact assessment for the S49 battle-14 balance.

Answers one question: *which* battles share the numbers that battle 14
touches, so a decision to change them can be priced before it is made.

The script is read-only: it parses the remake's generated scenario table and
reports, per battle id, which characters are used and at which level.

Usage::

    python tools/s49_battle_balance/u2_impact.py
"""

from __future__ import annotations

import pathlib
import re
import sys
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parents[2]
HEADER = (
    pathlib.Path(r"D:\Shell\Github\gba-naruto-butano")
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "generated_battle_scenario_content.h"
)

SLOT = re.compile(
    r"battle_scenario_unit_slot\{ "
    r"(true|false), "
    r"scenario_selector_kind::(\w+), "
    r"(\d+), "
    r"battle_side::(\w+), "
    r"grid_point\{ (\d+), (\d+) \}, "
    r"battle_facing::(\w+), "
    r"(\d+), "
    r"battle_scenario_unit_runtime_config\{ (true|false), (\d+), (\d+),"
)


def parse() -> list[dict]:
    text = HEADER.read_text(encoding="utf-8")
    battles: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        head = re.match(r"\s*battle_scenario_definition\{", line)
        if head:
            current = {"battle_id": None, "width": None, "height": None,
                       "slots": []}
            battles.append(current)
            continue
        if current is None:
            continue
        head = re.match(r"\s*(\d+), (\d+), (\d+),", line)
        if head and current["battle_id"] is None:
            current["battle_id"] = int(head.group(1))
            current["width"] = int(head.group(2))
            current["height"] = int(head.group(3))
            continue
        slot = SLOT.search(line)
        if slot:
            current["slots"].append(
                {
                    "enabled": slot.group(1) == "true",
                    "selector_kind": slot.group(2),
                    "selector": int(slot.group(3)),
                    "side": slot.group(4),
                    "level": int(slot.group(10)),
                    "ai": int(slot.group(11)),
                }
            )
    return battles


def main() -> int:
    if not HEADER.exists():
        print(f"missing {HEADER}", file=sys.stderr)
        return 2
    battles = parse()
    usage: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for battle in battles:
        seen: set[int] = set()
        for slot in battle["slots"]:
            if not slot["enabled"]:
                continue
            if slot["selector_kind"] != "fixed_character":
                continue
            character = slot["selector"]
            if character in seen:
                continue
            seen.add(character)
            usage[character].append((battle["battle_id"], slot["level"]))

    print(f"parsed {len(battles)} battle definitions")
    print()
    print("character  battles                                   levels")
    print("-" * 78)
    for character in sorted(usage):
        entries = usage[character]
        ids = ",".join(str(battle) for battle, _ in entries)
        levels = ",".join(str(level) for _, level in entries)
        print(
            f"{character:9d}  {len(entries):2d}  {ids:<40s} {levels}")
    print()
    for character in (1, 2, 3, 30, 55):
        entries = usage.get(character, [])
        print(
            f"battle-14's character {character}: "
            f"{len(entries)} of {len(battles)} battles use it")
    print()
    print("battle ids that use ALL of 1, 2, 3, 30, 55:")
    for battle in battles:
        characters = {
            slot["selector"]
            for slot in battle["slots"]
            if slot["enabled"]
            and slot["selector_kind"] == "fixed_character"
        }
        if {1, 2, 3, 30, 55} <= characters:
            print(f"  battle {battle['battle_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
