#!/usr/bin/env python3
"""Attribute the bees' deaths to their killers in a v1 real-battle receipt.

Why this tool exists
--------------------
W22-D5 has to answer one question with numbers: **after the normal attack is
opened for battle 14 v0, who kills the five bees?**

``v1_battle.py``'s receipt (``battle.json``) carries two streams:

* ``roster_series`` -- a per-turn snapshot of every unit's ``slot``,
  ``character_id``, ``hp`` and position, and
* ``decisions`` -- the driver's own log, including ``target-accepted``
  entries that name the enemy ``slot`` it just aimed at.

Neither stream says "this bee died to that attacker" on its own, so this tool
joins them: for every enemy slot it finds the round in which its ``hp``
reaches 0 and attributes the kill to the driver decision that targeted that
slot most recently before the death.

The tool also reports the **direct-attack usage** of every character: the
``action-list`` decisions carry the ROM's own ``source``/``action_id`` of the
entry the cursor rested on, so a direct attack (source kind ``direct_attack``)
is visible there.

Usage
-----
    python tools/s49_w22d5/analyze_kills.py --battle build/w22-d5/run/battle.json
    python tools/s49_w22d5/analyze_kills.py --battle a.json --battle b.json \
        --label A --label B --out build/w22-d5/kill-compare.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

SOURCE_ACTIVE = 0
SOURCE_NINJA_TOOL = 1
SOURCE_DIRECT_ATTACK = 2

BEE_CHARACTER_ID = 55
NARUTO = 1
SASUKE = 2
SAKURA = 3
SEED_PER_KILL = 50


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def enemy_slots(data: dict) -> list[int]:
    """The enemy slots of the first roster snapshot."""
    roster = data["roster_series"][0]["roster"]
    return [unit["slot"] for unit in roster if unit["side"] == 1]


def kill_events(data: dict) -> list[dict]:
    """One record per enemy slot: the round it died in and its killer.

    A dead unit **leaves** the roster, so "died" means "present in the last
    snapshot that still lists it and absent from the next one".  The very
    last kill can happen after the final roster snapshot, so the end state is
    taken from the receipt's own ``acceptance.bee_hp_end``.
    """
    slots = enemy_slots(data)
    end_hp = (data.get("acceptance") or {}).get("bee_hp_end") or {}
    # hp timeline per slot: (round, hp, frame, present)
    timeline: dict[int, list[tuple[int, int, int, bool]]] = {slot: [] for slot in slots}
    for entry in data["roster_series"]:
        round_no = entry["round"]
        present = {unit["slot"]: unit["hp"] for unit in entry["roster"]}
        for slot in slots:
            timeline[slot].append(
                (round_no, present.get(slot, 0), entry["frame"], slot in present))
    # the frame the battle was decided on (the last kill may land there)
    decided = next((d for d in reversed(data["decisions"])
                    if d.get("do") == "battle-decided"), None)
    decided_frame = decided.get("frame", 0) if decided else 0
    # decisions that aimed at an enemy
    aimed: list[dict] = [d for d in data["decisions"] if d.get("do") == "target-accepted"]
    events = []
    for slot in slots:
        series = timeline[slot]
        death = None
        for r, hp, f, present in series:
            if not present:
                death = (r, hp, f)
                break
        prev_alive = None
        for r, hp, f, present in series:
            if present:
                prev_alive = (r, hp, f)
        final_hp = end_hp.get(str(slot))
        died = (final_hp == 0) if final_hp is not None else death is not None
        death_frame = death[2] if death else (decided_frame if died else None)
        death_round = death[0] if death else (
            series[-1][0] if series and died else None)
        killer = None
        if died and death_frame is not None:
            hits = [d for d in aimed
                    if d.get("enemy") == slot and d.get("frame", 0) <= death_frame]
            if hits:
                killer = hits[-1]
        events.append({
            "slot": slot,
            "died": died,
            "death_round": death_round,
            "hp_before_death": prev_alive[1] if prev_alive else None,
            "final_hp": final_hp,
            "killer_character_id": killer.get("character_id") if killer else None,
            "killer_frame": killer.get("frame") if killer else None,
        })
    return events


def character_of_decision(data: dict, frame: int) -> int | None:
    """The actor that was planning at ``frame`` (last 'actor' decision before)."""
    actor = None
    for decision in data["decisions"]:
        if decision.get("do") == "actor" and decision.get("frame", 0) <= frame:
            actor = decision["character_id"]
    return actor


def behaviour_fingerprint(data: dict) -> str:
    """A hash of everything that decides the battle's outcome.

    Two runs with the same fingerprint played the **same battle**: the same
    actors, the same rounds, the same accepted attacks, the same dead bees.
    """
    parts = []
    for decision in data["decisions"]:
        if decision.get("do") in ("actor", "action-list", "target-accepted",
                                  "battle-decided"):
            parts.append(json.dumps(
                {k: decision.get(k) for k in
                 ("do", "frame", "character_id", "want", "chosen", "enemy",
                  "cell", "outcome", "round")},
                ensure_ascii=False, sort_keys=True))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def attribute(data: dict) -> dict:
    """Kill distribution + direct-attack usage + the settlement rows."""
    events = kill_events(data)
    distribution: dict[str, int] = {}
    for event in events:
        if not event["died"]:
            continue
        killer = event["killer_character_id"]
        if killer is None:
            killer = character_of_decision(data, event["killer_frame"] or 0)
        key = str(killer)
        distribution[key] = distribution.get(key, 0) + 1
    # direct attack usage
    direct = []
    for decision in data["decisions"]:
        if decision.get("do") != "action-list":
            continue
        chosen = decision.get("chosen") or {}
        if chosen.get("source") == SOURCE_DIRECT_ATTACK:
            direct.append({
                "frame": decision.get("frame"),
                "want": decision.get("want"),
                "chosen": chosen,
                "damage": decision.get("damage"),
            })
    # who used which action at all
    usage: dict[str, int] = {}
    for decision in data["decisions"]:
        if decision.get("do") != "action-list":
            continue
        want = decision.get("want") or {}
        source = want.get("source")
        actor = character_of_decision(data, decision.get("frame", 0))
        key = "char{}/src{}".format(actor, source)
        usage[key] = usage.get(key, 0) + 1
    rows = {}
    for character, name in ((NARUTO, "naruto"), (SASUKE, "sasuke"), (SAKURA, "sakura")):
        kills = distribution.get(str(character), 0)
        rows[name] = {"character_id": character, "kills": kills,
                      "battle_experience": kills * SEED_PER_KILL}
    return {
        "rom_sha256": data.get("rom_sha256"),
        "round": data.get("round"),
        "outcome": data.get("outcome"),
        "frames_run": data.get("frames_run"),
        "behaviour_fingerprint": behaviour_fingerprint(data),
        "kill_events": events,
        "kill_distribution": distribution,
        "battle_experience": {name: rows[name]["battle_experience"]
                              for name in rows},
        "battle_experience_vector": [rows["naruto"]["battle_experience"],
                                     rows["sasuke"]["battle_experience"],
                                     rows["sakura"]["battle_experience"]],
        "kills_vector": [rows["naruto"]["kills"], rows["sasuke"]["kills"],
                         rows["sakura"]["kills"]],
        "direct_attack_uses": direct,
        "action_usage": usage,
        "action_refused_count": sum(1 for d in data["decisions"]
                                    if d.get("do") == "action-refused"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--battle", type=pathlib.Path, action="append", required=True)
    parser.add_argument("--label", action="append", default=None)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()
    labels = args.label or [p.parent.name + "/" + p.stem for p in args.battle]
    result = {}
    for path, label in zip(args.battle, labels):
        result[label] = attribute(load(path))
        print("=== {} ===".format(label))
        print(json.dumps(result[label], ensure_ascii=False, indent=1))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=1)
        print("[analyze_kills] wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
