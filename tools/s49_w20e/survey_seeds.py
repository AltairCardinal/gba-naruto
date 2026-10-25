#!/usr/bin/env python3
"""E4: survey every distinct battle-experience seed in the whole formation matrix."""

from __future__ import annotations

import collections
import json
import pathlib
import sys

JSON = pathlib.Path(r"D:\Github\gba-naruto\build\w20-e4\enemy-battle-experience.json")


def main() -> int:
    payload = json.loads(JSON.read_text(encoding="utf-8"))
    by_value = collections.defaultdict(list)
    for scenario in payload["scenarios"]:
        for variant in scenario["variants"]:
            for unit in variant["units"]:
                if unit["enabled"] and unit["battle_experience"]:
                    by_value[unit["battle_experience"]].append(
                        (scenario["battle_id"], variant["variant"], unit["record_id"],
                         unit["side"])
                    )
    print("distinct seeds over all 48 groups x 3 variants x 12 records:")
    for value in sorted(by_value):
        hits = by_value[value]
        enemies = [h for h in hits if h[3] == 1]
        print(f"  {value:6d}  count={len(hits):4d}  enemy_count={len(enemies):4d}")
    print()
    print("seeds in [50..70] that are NOT multiples of 5/10:")
    odd = [v for v in sorted(by_value) if v % 5 != 0]
    print(f"  {odd}")
    print()
    print("all battles whose variant-0 enemy seeds could make 59/59/30:")
    for scenario in payload["scenarios"]:
        for variant in scenario["variants"]:
            enemies = [
                u for u in variant["units"]
                if u["enabled"] and u["side"] == 1
            ]
            seeds = [u["battle_experience"] for u in enemies]
            if not seeds:
                continue
            uniq = sorted(set(seeds))
            if len(uniq) == 1:
                continue
            if any(s in (59, 30, 60) for s in uniq):
                print(
                    f"  battle {scenario['battle_id']:2d} v{variant['variant']}: {seeds}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
