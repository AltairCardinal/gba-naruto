#!/usr/bin/env python3
"""W23-F4: attribute every bee kill to the actor that caused it.

The driver receipt has two streams:

* ``decisions`` -- one ``actor`` entry per turn (who acted, what it planned);
* ``roster_series`` -- one snapshot per turn (the live hit points).

Merging them gives the "who killed what in which turn" table, which is the
only thing that decides the 战闘分 row of the settlement screen.

Usage:
    python tools/s49_w23f4/trace_kills.py --battle build/w23-f4/run/battle.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

NAMES = {1: "naruto", 2: "sasuke", 3: "sakura"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battle", required=True, type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args(argv)

    data = json.loads(args.battle.read_text(encoding="utf-8"))
    decisions = data.get("decisions", [])
    series = data.get("roster_series", [])

    # snapshot[i] = hp of every unit right before turn i (roster_series has one
    # entry per "actor" decision, so they line up one to one).
    snaps = []
    snap_units = []
    for entry in series:
        snaps.append({unit["slot"]: unit["hp"] for unit in entry.get("roster", [])})
        snap_units.append({unit["slot"]: unit for unit in entry.get("roster", [])})

    kills = []
    rows = []
    turn_index = 0
    for decision in decisions:
        if decision.get("do") != "actor":
            continue
        before = snaps[turn_index] if turn_index < len(snaps) else {}
        after = snaps[turn_index + 1] if turn_index + 1 < len(snaps) else {}
        actor = decision.get("character_id")
        plan = decision.get("plan", {})
        target = (plan.get("target") or {}).get("slot")
        chosen = plan.get("chosen_attack") or {}
        # The driver's snapshot drops dead units, so a kill shows up as a slot
        # that disappears from the roster (not as hp == 0).
        # The **last** turn has no following snapshot (the battle ended), so
        # its "after" state comes from the receipt's acceptance block (the
        # final bee hit points); the escort is never a kill.
        acceptance = data.get("acceptance", {})
        bee_hp_end = {int(key): value for key, value in
                      (acceptance.get("bee_hp_end", {}) or {}).items()}
        escort_slot = None
        for unit in (snap_units[0] if snap_units else {}).values():
            if unit.get("char") == 30:
                escort_slot = unit.get("slot")
        dropped = []
        for slot, hp_before in before.items():
            if hp_before <= 0 or slot == escort_slot:
                continue
            if turn_index + 1 < len(snaps):
                hp_after = after.get(slot)
                if hp_after is None or hp_after == 0:
                    dropped.append((slot, hp_before))
            elif slot in bee_hp_end and bee_hp_end[slot] == 0:
                dropped.append((slot, hp_before))
        for slot, hp_before in dropped:
            kills.append({
                "turn": turn_index,
                "frame": decision.get("frame"),
                "actor": actor,
                "actor_name": NAMES.get(actor, actor),
                "slot": slot,
                "hp_before": hp_before,
                "planned_target": target,
            })
        rows.append({
            "turn": turn_index,
            "frame": decision.get("frame"),
            "actor_name": NAMES.get(actor, actor),
            "planned_target": target,
            "attack": f"{chosen.get('source_name') or chosen.get('source')}"
                      f":{chosen.get('action_id')}"
                      f" p{chosen.get('potency')} r{chosen.get('range')}",
            "drops": dropped,
        })
        turn_index += 1

    counts = {1: 0, 2: 0, 3: 0}
    for kill in kills:
        if kill["actor"] in counts:
            counts[kill["actor"]] += 1

    print(f"battle={args.battle}")
    print(f"round={data.get('round')} turns={turn_index} "
          f"kills={len(kills)} distribution={counts} "
          f"battle_score={counts[1]*50}/{counts[2]*50}/{counts[3]*50}")
    print("--- per turn ---")
    for row in rows:
        mark = ("  DROPS " + ",".join(f"slot{s}({h})" for s, h in row["drops"])
                ) if row["drops"] else ""
        print(f"t{row['turn']:>3} f{row['frame']:>6} {row['actor_name']:>7} "
              f"tgt={str(row['planned_target']):>4} {row['attack']:>22}{mark}")
    print("--- kills ---")
    for kill in kills:
        print(f"  t{kill['turn']:>3} f{kill['frame']:>6} "
              f"{kill['actor_name']:>7} killed slot {kill['slot']} "
              f"(hp {kill['hp_before']} -> 0)")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "battle_json": str(args.battle),
            "round": data.get("round"),
            "turns": turn_index,
            "kill_count": len(kills),
            "distribution": counts,
            "battle_score": [counts[1] * 50, counts[2] * 50, counts[3] * 50],
            "rows": rows,
            "kills": kills,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
