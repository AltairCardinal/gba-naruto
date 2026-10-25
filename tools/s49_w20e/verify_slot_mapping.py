#!/usr/bin/env python3
"""E4: verify that the ROM record order matches the committed generated header.

The parent will paste the seeds back into the generator, so the mapping
`record_id -> battle_scenario_unit_slot[12] index` must be exactly right.
This compares (selector, side, x, y) per slot for every scenario/variant.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

JSON = pathlib.Path(r"D:\Github\gba-naruto\build\w20-e4\enemy-battle-experience.json")
HEADER = pathlib.Path(
    r"D:\Github\gba-naruto\build\w20-e4\butano-sequel\game\include\konoha"
    r"\generated_battle_scenario_content.h"
)

SLOT_RE = re.compile(
    r"battle_scenario_unit_slot\{ "
    r"(?P<enabled>true|false), "
    r"scenario_selector_kind::(?P<kind>\w+), "
    r"(?P<selector>\d+), "
    r"battle_side::(?P<side>\w+), "
    r"grid_point\{ (?P<x>\d+), (?P<y>\d+) \}, "
    r"battle_facing::(?P<facing>\w+), "
    r"(?P<experience>\d+), "
    r"battle_scenario_unit_runtime_config"
)


def main() -> int:
    payload = json.loads(JSON.read_text(encoding="utf-8"))
    text = HEADER.read_text(encoding="utf-8")

    # Split the header into per-scenario blocks.
    blocks = re.split(r"battle_scenario_definition\{", text)[1:]
    print(f"header scenario blocks: {len(blocks)}")
    header_slots = []
    for block in blocks:
        head = block.split("std::array<std::array", 1)[0]
        battle_id = int(re.match(r"\s*(\d+),", head).group(1))
        variants = []
        markers = list(
            re.finditer(r"std::array<battle_scenario_unit_slot, 12>\{\{", block)
        )
        for index, marker in enumerate(markers):
            start = marker.end()
            end = (
                markers[index + 1].start()
                if index + 1 < len(markers)
                else len(block)
            )
            body = block[start:end]
            slots = [
                {
                    "enabled": m.group("enabled") == "true",
                    "selector": int(m.group("selector")),
                    "side": 0 if m.group("side") == "player" else 1,
                    "x": int(m.group("x")),
                    "y": int(m.group("y")),
                    "experience": int(m.group("experience")),
                }
                for m in SLOT_RE.finditer(body)
            ]
            variants.append(slots)
        header_slots.append((battle_id, variants))

    total = 0
    mismatched = []
    for battle_id, variants in header_slots:
        scenario = next(
            s for s in payload["scenarios"] if s["battle_id"] == battle_id
        )
        for variant in scenario["variants"]:
            units = variant["units"]
            ref = variants[variant["variant"]]
            if len(ref) != len(units):
                mismatched.append(
                    (battle_id, variant["variant"], "slot count", len(ref), len(units))
                )
                continue
            for unit, h in zip(units, ref):
                total += 1
                if (
                    unit["enabled"] != h["enabled"]
                    or unit["selector"] != h["selector"]
                    or unit["side"] != h["side"]
                    or unit["x"] != h["x"]
                    or unit["y"] != h["y"]
                ):
                    mismatched.append(
                        (
                            battle_id,
                            variant["variant"],
                            unit["record_id"],
                            (unit["selector"], unit["side"], unit["x"], unit["y"]),
                            (h["selector"], h["side"], h["x"], h["y"]),
                        )
                    )
                if unit["battle_experience"] != h["experience"]:
                    mismatched.append(
                        (
                            battle_id,
                            variant["variant"],
                            unit["record_id"],
                            "experience",
                            unit["battle_experience"],
                            h["experience"],
                        )
                    )
    print(f"compared slots: {total}")
    print(f"mismatches: {len(mismatched)}")
    for row in mismatched[:20]:
        print(f"  {row}")
    if mismatched:
        print()
        print("=> the committed header is STALE for the experience field "
              "and/or the geometry")
        stale_exp = [m for m in mismatched if m[2] == "experience"]
        stale_geo = [m for m in mismatched if m[2] != "experience"]
        print(f"   experience-only mismatches: {len(stale_exp)}")
        print(f"   geometry mismatches       : {len(stale_geo)}")
        return 1
    print("=> the committed header already matches the ROM on every field")
    return 0


if __name__ == "__main__":
    sys.exit(main())
