#!/usr/bin/env python3
"""Print the unit slot order of one battle in the remake's scenario table.

Stream U3 (wave 10).  S3 asks for a **per-person** level-up page sequence, so
the order in which the remake's battle-14 puts its player units on the
session decides who ends up in the progression roster (the roster holds
three entries) and therefore who gets a level-up screen.

This tool answers one yes/no question:

    *In which order does battle 14 put its player units into the session?*

Usage::

    python tools/s49_u3_settlement/u3_battle_units.py --battle 14
"""

from __future__ import annotations

import argparse
import pathlib
import re

SCENARIO_HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include"
    r"\konoha\generated_battle_scenario_content.h")


def scenario_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    position = 0
    while True:
        start = text.find("battle_scenario_definition{", position)
        if start < 0:
            break
        depth = 0
        index = start + len("battle_scenario_definition") - 1
        while True:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        blocks.append(text[start:index + 1])
        position = index + 1
    return blocks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battle", type=int, default=14)
    args = parser.parse_args(argv)

    text = SCENARIO_HEADER.read_text(encoding="utf-8")
    blocks = scenario_blocks(text)
    print(f"scenario definitions: {len(blocks)}")

    for index, block in enumerate(blocks):
        head = block[len("battle_scenario_definition{"):]
        head = head[:head.find(",")]
        if head.strip() != str(args.battle):
            continue
        print(f"=== battle {args.battle} = scenario index {index}")
        for slot, match in enumerate(
                re.finditer(r"battle_scenario_unit_slot\{([^}]*)\}", block)):
            fields = " ".join(match.group(1).split())
            if fields.startswith("false"):
                continue
            print(f"  slot {slot:>2}: {fields}")
        return 0

    print(f"battle {args.battle} not found")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
