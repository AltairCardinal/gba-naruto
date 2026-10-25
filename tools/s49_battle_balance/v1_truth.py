#!/usr/bin/env python3
"""V1 (wave 16): the truth the closed-loop battle driver needs.

The driver plays the **remake** ROM, so it needs two facts that only exist in
the remake's generated content headers:

* the **battle 14 map** -- which cells the movement may enter
  (``generated_battle_map_content.h``);
* the **action catalogue** -- every action's range, potency, hit count and
  target policy (``generated_battle_action_content.h``).

Both headers are **read only**: this script never writes to the remake tree.
It turns them into a small JSON snapshot (``build/v1/battle-truth.json``) that
the driver reads, so the driver does not depend on the remake tree at runtime.

Why the map model is "plain cells only"
---------------------------------------
``battle_map_cell::fully_blocked()`` is ``terrain_class() == 15`` (the wall), so
the *remake* may step on a river (class 1), a ground patch (class 3) and a rock
(class 7) as well.  The driver's model uses the **plain** cells (class 0) only,
which is what the original allows (the reverse line's map truth marks the
classes 0 and 3 as walkable) and what U2's validated route generator used
(``u2_route_gen.cpp``: ``player_can_enter()`` -> ``terrain_class() == 0``).
A cell the driver picks is therefore always accepted by the ROM's own
pathfinder: the model is a strict subset of the ROM's rule.

Usage::

    python tools/s49_battle_balance/v1_truth.py --out build/v1/battle-truth.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

REMAKE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha")
MAP_HEADER = REMAKE / "generated_battle_map_content.h"
ACTION_HEADER = REMAKE / "generated_battle_action_content.h"

BATTLE_ID = 14

# Bumped whenever the snapshot's content changes, so ``load`` rebuilds a
# stale snapshot even when the remake's headers did not move.
BUILDER = 2

# The remake's S49 battle-14 roster, as U2 measured it with the **product
# code** (the offline controller running the real battle scene):
# ``build/s49-battle-balance/u2/dump.txt`` (U2's V1/V2 of
# ``notes/s49-fidelity/U2-battle-balance.md``).  The driver needs the
# *defence* of a target to estimate the damage of an attack -- the telemetry
# only carries the stats of the unit under the cursor.
ROSTER = {
    "1": {"character": "Naruto", "hp": 138, "attack": 18, "defense": 17,
          "agility": 12, "move_range": 3,
          "actions": ["active:2", "active:7", "active:5",
                      "tool:1", "tool:11", "tool:37"]},
    "2": {"character": "Sasuke", "hp": 104, "attack": 15, "defense": 11,
          "agility": 15, "move_range": 3,
          "actions": ["active:2", "active:16", "active:5"]},
    "3": {"character": "Sakura", "hp": 110, "attack": 11, "defense": 11,
          "agility": 14, "move_range": 3,
          "actions": ["active:1", "active:2", "active:5"]},
    "30": {"character": "Konohamaru", "hp": 40, "attack": 8, "defense": 8,
           "agility": 8, "move_range": 2, "actions": []},
    "55": {"character": "bee", "hp": 25, "attack": 14, "defense": 6,
           "agility": 24, "move_range": 3, "actions": []},
}

TARGET_POLICY = {
    "self_or_implicit_actor": 0,
    "friendly_unit_policy_1": 1,
    "opponent_unit": 2,
    "occupied_unit": 3,
    "empty_tile": 4,
    "friendly_unit_policy_5": 5,
}

ACTION_DEFINITION = re.compile(
    r"action_definition\{\s*(?P<id>\d+),\s*"
    r"cost_policy\{ action_cost_kind::(?P<cost_kind>\w+),\s*"
    r"(?P<cost>\d+),\s*(?P<tool>\d+)\s*\},\s*"
    r"presentation_binding\{\s*(?P<binding>\d+)\s*\},\s*"
    r"effect_descriptor\{\s*(?P<code>\d+),\s*(?P<flags>\d+),\s*"
    r"(?P<potency>\d+),\s*(?P<hits>\d+),\s*(?P<rate>\d+),\s*"
    r"(?P<duration>\d+)\s*\},\s*"
    r"target_policy\{ target_policy_kind::(?P<target>\w+),\s*"
    r"(?P<target_flags>\d+)\s*\},\s*"
    r"range_shape\{\s*(?P<distance_flags>\d+),\s*"
    r"(?P<area_flags>\d+)\s*\},\s*"
    r"upgrade_rule\{\s*(?P<upgrade_type>\d+),\s*(?P<upgrade_growth>\d+)\s*\}\s*,\s*"
    r"battle_action_source_kind::(?P<source>\w+)\s*\}")

MAP_DEFINITION = re.compile(
    r"battle_map_definition\{\s*(?P<id>\d+),\s*(?P<width>\d+),\s*"
    r"(?P<height>\d+),\s*(?P<offset>\d+),\s*(?P<count>\d+)\s*\}")


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_map(header: pathlib.Path, battle_id: int) -> dict:
    text = header.read_text(encoding="utf-8", errors="replace")
    definitions = [match.groupdict() for match in
                   MAP_DEFINITION.finditer(text)]
    definition = next(item for item in definitions
                      if int(item["id"]) == battle_id)
    start = text.index("battle_map_cells = {{")
    cells = [int(value, 16) for value in
             re.findall(r"battle_map_cell\{\s*0x([0-9A-Fa-f]+)\s*\}",
                        text[start:])]
    offset = int(definition["offset"])
    count = int(definition["count"])
    classes = [value & 0xF for value in cells[offset:offset + count]]
    return {
        "battle_id": battle_id,
        "width": int(definition["width"]),
        "height": int(definition["height"]),
        "cell_offset": offset,
        "cell_count": count,
        "classes": classes,
        "plain_cells": sum(1 for value in classes if value == 0),
        "wall_cells": sum(1 for value in classes if value == 15),
    }


def parse_actions(header: pathlib.Path) -> dict:
    text = header.read_text(encoding="utf-8", errors="replace")
    tables: dict[str, list[dict]] = {}
    for name in ("active_action_definitions", "ninja_tool_action_definitions"):
        start = text.index(f"{name} = {{")
        end = text.index("}};", start)
        tables[name] = [
            {
                "id": int(match.group("id")),
                "source": match.group("source"),
                "cost_kind": match.group("cost_kind"),
                "cost": int(match.group("cost")),
                "tool_slot": int(match.group("tool")),
                "effect_code": int(match.group("code")),
                "potency": int(match.group("potency")),
                "hits": int(match.group("hits")),
                "rate": int(match.group("rate")),
                "target_kind": TARGET_POLICY[match.group("target")],
                "range": int(match.group("distance_flags")) & 0x1F,
                "distance_flags": int(match.group("distance_flags")),
            }
            for match in ACTION_DEFINITION.finditer(text[start:end])
        ]
    return {
        "active": {str(item["id"]): item for item in tables[
            "active_action_definitions"]},
        "ninja_tool": {str(item["id"]): item for item in tables[
            "ninja_tool_action_definitions"]},
    }


def build(out: pathlib.Path) -> dict:
    document = {
        "schema": "konoha.s49-v1-battle-truth.v1",
        "builder": BUILDER,
        "sources": {
            "map_header": str(MAP_HEADER),
            "map_header_sha256": sha256_file(MAP_HEADER),
            "action_header": str(ACTION_HEADER),
            "action_header_sha256": sha256_file(ACTION_HEADER),
        },
        "map": parse_map(MAP_HEADER, BATTLE_ID),
        "actions": parse_actions(ACTION_HEADER),
        "roster": ROSTER,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
    return document


def load(path: pathlib.Path) -> dict:
    """Load the snapshot, rebuilding it when the remake's headers moved."""
    if path.exists():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            document = None
        if document:
            sources = document.get("sources", {})
            if (document.get("builder") == BUILDER and
                    sources.get("map_header_sha256") == sha256_file(MAP_HEADER) and
                    sources.get("action_header_sha256") ==
                    sha256_file(ACTION_HEADER)):
                return document
    return build(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "v1" / "battle-truth.json")
    args = parser.parse_args(argv)
    document = build(args.out)
    print(json.dumps({
        "out": str(args.out),
        "map": {key: value for key, value in document["map"].items()
                if key != "classes"},
        "active_actions": len(document["actions"]["active"]),
        "ninja_tool_actions": len(document["actions"]["ninja_tool"]),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
