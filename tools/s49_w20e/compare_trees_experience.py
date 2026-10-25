#!/usr/bin/env python3
"""E4: print the battle_experience field of every enabled slot, per tree."""

from __future__ import annotations

import pathlib
import re
import sys

TREES = {
    "shared": pathlib.Path(
        r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
        r"\generated_battle_scenario_content.h"
    ),
    "lane-e4": pathlib.Path(
        r"D:\Github\gba-naruto\build\w20-e4\butano-sequel\game\include\konoha"
        r"\generated_battle_scenario_content.h"
    ),
}

SLOT_RE = re.compile(
    r"battle_scenario_unit_slot\{ "
    r"(?P<enabled>true|false), "
    r"scenario_selector_kind::(?P<kind>\w+), "
    r"(?P<selector>\d+), "
    r"battle_side::(?P<side>\w+), "
    r"grid_point\{ (?P<x>\d+), (?P<y>\d+) \}, "
    r"battle_facing::(?P<facing>\w+), "
    r"(?P<experience>\d+), "
)


def parse(text):
    blocks = re.split(r"battle_scenario_definition\{", text)[1:]
    out = []
    for block in blocks:
        head = block.split("std::array<std::array", 1)[0]
        battle_id = int(re.match(r"\s*(\d+),", head).group(1))
        markers = list(
            re.finditer(r"std::array<battle_scenario_unit_slot, 12>\{\{", block)
        )
        variants = []
        for index, marker in enumerate(markers):
            start = marker.end()
            end = (
                markers[index + 1].start()
                if index + 1 < len(markers)
                else len(block)
            )
            variants.append(list(SLOT_RE.finditer(block[start:end])))
        out.append((battle_id, variants))
    return out


def main() -> int:
    for label, path in TREES.items():
        print("=" * 72)
        print(f"{label}: {path}")
        if not path.is_file():
            print("  MISSING")
            continue
        data = path.read_bytes()
        print(f"  bytes={len(data)}  sha256={__import__('hashlib').sha256(data).hexdigest()}")
        parsed = parse(path.read_text(encoding="utf-8"))
        total = 0
        nonzero = 0
        for battle_id, variants in parsed:
            for v_index, slots in enumerate(variants):
                for slot in slots:
                    total += 1
                    value = int(slot.group("experience"))
                    if value:
                        nonzero += 1
        print(f"  scenarios={len(parsed)} slots={total} nonzero_experience={nonzero}")
        for battle_id in (9, 13, 14, 41, 43):
            entry = next((b, v) for b, v in parsed if b == battle_id)
            for v_index, slots in enumerate(entry[1]):
                enemies = [
                    (s.group("selector"), s.group("experience"))
                    for s in slots
                    if s.group("enabled") == "true"
                    and s.group("side") == "enemy"
                ]
                if enemies:
                    print(
                        f"    battle {battle_id:2d} v{v_index}: "
                        f"enemies(selector,exp)={enemies}"
                    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
