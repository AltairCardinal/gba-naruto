#!/usr/bin/env python3
"""W23-F4: dump the per-turn decision chain of a v1_battle real-battle receipt.

The receipt's ``decisions`` list is the driver's own log: one ``actor`` entry
per turn (with the round, the actor's character id, the chosen plan and the
scored candidates) plus the ``action``/``refused`` entries that show what the
ROM actually did.

This tool turns that log into a compact, comparable table so that a driver
change can be judged by *who killed what in which round* instead of by the
settlement pixels alone.

Usage:
    python tools/s49_w23f4/analyze_decisions.py \
        --battle build/w23-f4/run/battle.json --out build/w23-f4/decision-chain.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

CHARACTER_NAMES = {1: "naruto", 2: "sasuke", 3: "sakura"}


def character_name(character_id) -> str:
    return CHARACTER_NAMES.get(character_id, f"char{character_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battle", required=True, type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path)
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)

    data = json.loads(args.battle.read_text(encoding="utf-8"))
    decisions = data.get("decisions", [])
    roster = data.get("roster_series", [])

    # roster_series: one snapshot per turn; index -> unit hp map
    snapshots = []
    for entry in roster:
        units = entry.get("roster", [])
        snapshots.append({
            "frame": entry.get("frame"),
            "round": entry.get("round"),
            "units": [
                {"slot": unit.get("slot"), "char": unit.get("character_id"),
                 "hp": unit.get("hp"), "at": [unit.get("x"), unit.get("y")],
                 "active": unit.get("active"), "side": unit.get("side")}
                for unit in units],
        })

    turns = []
    refusals = []
    actions = []
    for index, decision in enumerate(decisions):
        kind = decision.get("do")
        if kind == "actor":
            plan = decision.get("plan", {})
            chosen = plan.get("chosen_attack") or {}
            turns.append({
                "index": index,
                "frame": decision.get("frame"),
                "character_id": decision.get("character_id"),
                "character": character_name(decision.get("character_id")),
                "hp": decision.get("hp"),
                "at": decision.get("at"),
                "attack_stat": decision.get("attack"),
                "plan_attack": plan.get("attack"),
                "target_slot": (plan.get("target") or {}).get("slot"),
                "target_hp": (plan.get("target") or {}).get("hp"),
                "cell": plan.get("cell"),
                "gap": plan.get("gap"),
                "path_len": len(plan.get("path") or []) - 1 if plan.get("path") else None,
                "damage": plan.get("damage"),
                "chosen_attack": {
                    "source": chosen.get("source"),
                    "action_id": chosen.get("action_id"),
                    "source_name": chosen.get("source_name"),
                    "range": chosen.get("range"),
                    "potency": chosen.get("potency"),
                    "hits": chosen.get("hits"),
                } if chosen else None,
                "candidate_count": len(decision.get("candidates", [])),
                "candidates": decision.get("candidates", []),
            })
        elif kind in ("action-refused", "refused"):
            refusals.append(decision)
        elif kind in ("action", "action-ok", "damage"):
            actions.append(decision)

    # hp trajectory per player slot: who lost hp to whom is not in the log,
    # but the *bee* hp trajectory is, so we can detect the kill turns.
    hp_series = []
    for snapshot in snapshots:
        hp_series.append({
            "round": snapshot["round"],
            "frame": snapshot["frame"],
            "player": [
                {"slot": unit["slot"], "char": unit["char"], "hp": unit["hp"],
                 "active": unit["active"], "side": unit["side"]}
                for unit in snapshot["units"]],
        })

    result = {
        "label": args.label,
        "battle_json": str(args.battle),
        "rom": data.get("rom"),
        "rom_sha256": data.get("rom_sha256"),
        "entry": data.get("entry"),
        "round": data.get("round"),
        "outcome": data.get("outcome"),
        "errors": data.get("errors"),
        "acceptance": data.get("acceptance"),
        "settlement": data.get("settlement"),
        "turn_count": len(turns),
        "turns": turns,
        "refusals": refusals,
        "actions": actions,
        "raw_decisions": decisions,
        "hp_series": hp_series,
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    else:
        print(text)

    # console summary
    print(f"round={data.get('round')} outcome={data.get('outcome')} "
          f"entry={data.get('entry')} errors={data.get('errors')}")
    print(f"{'idx':>4} {'round':>5} {'actor':>8} {'hp':>4} {'tgt':>4} "
          f"{'tgt_hp':>6} {'dmg':>4} {'atk':>22} {'cell':>10} {'path':>4}")
    for turn in turns:
        attack = turn["chosen_attack"] or {}
        attack_text = (f"{attack.get('source_name') or attack.get('source')}"
                       f":{attack.get('action_id')}"
                       f" p{attack.get('potency')}x{attack.get('hits')}"
                       f" r{attack.get('range')}")
        print(f"{turn['index']:>4} {str(turn['frame']):>5} "
              f"{turn['character']:>8} {str(turn['hp']):>4} "
              f"{str(turn['target_slot']):>4} {str(turn['target_hp']):>6} "
              f"{str(turn['damage']):>4} {attack_text:>22} "
              f"{str(turn['cell']):>10} {str(turn['path_len']):>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
