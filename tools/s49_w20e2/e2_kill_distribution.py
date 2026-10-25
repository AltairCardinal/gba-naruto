#!/usr/bin/env python3
"""Derive the remake's **real battle** kill distribution from the probe telemetry.

Why
---
The original's 「戰鬥分」 row is the sum of the *neutralised* enemies' battle
experience.  Whether the remake's real battle reproduces the original's
settlement row therefore depends on **who killed each enemy**.

The driver's receipt (``battle.json``) keeps

* ``decisions``      — one ``actor`` record per player action (actor id, the
                       planned target slot, the planned damage), and
* ``roster_series``  — per-frame snapshots of every unit's hit points.

An enemy disappears from the roster when it is defeated, so the killer is the
last ``actor`` decision before the snapshot in which the enemy vanished.

Usage::

    python tools/s49_w20e2/e2_kill_distribution.py build/w19-d/run-a/battle.json
"""

from __future__ import annotations

import json
import pathlib
import sys


def main() -> int:
    path = pathlib.Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"receipt   : {path}")
    print(f"rom sha256: {data.get('rom_sha256')}")
    print(f"outcome   : {data.get('outcome')}  round: {data.get('round')}")
    print()

    actors = [
        decision for decision in data.get("decisions", [])
        if decision.get("do") == "actor"
    ]
    series = data.get("roster_series", [])
    print(f"actor decisions: {len(actors)}   roster snapshots: {len(series)}")

    kills: dict[int, list[int]] = {}
    previous: dict[int, int] = {}
    for snapshot in series:
        frame = snapshot.get("frame", 0)
        alive = {
            unit["slot"]: unit["hp"]
            for unit in snapshot.get("roster", [])
            if unit.get("side") == 1
        }
        for slot, hp in previous.items():
            if slot not in alive:
                killer = None
                for decision in actors:
                    if decision.get("frame", 0) <= frame:
                        killer = decision.get("character_id")
                    else:
                        break
                kills.setdefault(killer, []).append(slot)
                print(f"  frame {frame:>7}: enemy slot {slot} defeated "
                      f"(last actor = character {killer})")
        previous = alive

    print()
    print("kills per character (derived):")
    for character_id in sorted(kills, key=lambda value: (value is None, value)):
        print(f"  character {character_id}: {len(kills[character_id])} "
              f"(slots {kills[character_id]})")
    print()
    print("=> 「戰鬥分」 per character = 50 x kills "
          "(battle 14 enemies each carry the seed 50)")
    for character_id in sorted(kills, key=lambda value: (value is None, value)):
        print(f"  character {character_id}: {50 * len(kills[character_id])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
