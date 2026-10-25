#!/usr/bin/env python3
"""E4: compact per-battle / per-variant view of the formation seeds."""

from __future__ import annotations

import json
import pathlib
import sys

JSON = pathlib.Path(r"D:\Github\gba-naruto\build\w20-e4\enemy-battle-experience.json")


def main() -> int:
    payload = json.loads(JSON.read_text(encoding="utf-8"))
    wanted = set(int(a) for a in sys.argv[1:]) if len(sys.argv) > 1 else None
    header = "battle | variant | players | enemies | enemy seeds | sum"
    print(header)
    print("-" * len(header))
    for scenario in payload["scenarios"]:
        battle = scenario["battle_id"]
        if wanted is not None and battle not in wanted:
            continue
        for variant in scenario["variants"]:
            units = variant["units"]
            players = [u for u in units if u["enabled"] and u["side"] == 0]
            enemies = [u for u in units if u["enabled"] and u["side"] == 1]
            seeds = [u["battle_experience"] for u in enemies]
            print(
                f"{battle:6d} | {variant['variant']:7d} | {len(players):7d} | "
                f"{len(enemies):7d} | {str(seeds):40s} | {sum(seeds):4d}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
