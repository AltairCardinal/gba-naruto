#!/usr/bin/env python3
"""V1 (wave 16): play the remake's S49 battle 14 to a **real** victory.

Why this driver exists
----------------------
W1's closed-loop driver (``w1_battle.py``) walks the whole turn chain but
never gets past the **target selection**: it tries cell after cell until the
round limit (716 618 frames) and the battle is never decided, so the
``outcome=1`` of the settlement chain still had to be poked into the
controller.

So the driver takes its decisions from the **original's** strategy
(``tools/s49_victory_capture/w4_play.py``) and from the remake's own
validated route generator (``tools/s49_battle_balance/u2_route_gen.cpp``):

* **the original's target rule** (``w4_play.py::act``) ranks the candidates
  by *one shot kill first*, then by the damage it deals, then by the least
  movement, and finally by the enemy's slot;
* **the remake's attack cell** (``u2_route_gen.cpp::find_attack_cell``) is the
  reachable cell from which the target is **closest** -- the cell the actor
  has to stand on for the shot to be legal;
* **the remake's fallback** (``u2_route_gen.cpp`` R4) is to *close the
  distance* to the nearest enemy when no enemy is in reach, instead of
  guarding the escort;
* **the defence decision** is answered with *no* (U2's R3), because every
  defence entry of the remake reports
  ``defense_preparation_error::unsupported_category``.

The rules the ROM itself applies (read from the remake's source, not guessed):

* a target is legal when the cell holds an **active unit of the other side**
  (``battle_action_system.h::_validate_target``) and the Manhattan distance
  from the actor's cell is within the action's range
  (``_preview``: ``distance > action.range.maximum_distance()``);
* the movement accepts a cell when a path of cost <= the unit's move range
  exists over the map cells that are not walls
  (``battle_player_action_flow.h::preview_move``);
* the command list is ordered ``move, ability, direct_attack,
  replenish_chakra, rest, end_action``
  (``battle_command_browser.h``).

Everything the driver decides is read from the ROM's own telemetry, so the
run is a **real battle**: the ``outcome=1`` of the settlement chain is
produced by the product code, not poked into it.

Usage::

    python tools/s49_battle_balance/v1_battle.py \\
        --rom build/v1/rom-pinned.gba --out build/v1/run-a --boot
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
# W22-D5: this copy lives outside tools/s49_battle_balance, so the sibling
# modules (w1_boot, w1_probe, x1_telemetry, y1_play, v1_truth) have to be
# found explicitly.
BALANCE = HERE.parent / "s49_battle_balance"
if str(BALANCE) not in sys.path:
    sys.path.insert(0, str(BALANCE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402
import y1_play  # noqa: E402
import v1_truth  # noqa: E402

PHASE_UNIT_SELECTION = y1_play.PHASE_UNIT_SELECTION
PHASE_MOVE_SELECTION = y1_play.PHASE_MOVE_SELECTION
PHASE_COMMAND_SELECTION = y1_play.PHASE_COMMAND_SELECTION
PHASE_CHAKRA_SELECTION = y1_play.PHASE_CHAKRA_SELECTION
PHASE_REST_CONFIRMATION = y1_play.PHASE_REST_CONFIRMATION
PHASE_ACTION_SELECTION = y1_play.PHASE_ACTION_SELECTION
PHASE_COMBINATION_DECISION = y1_play.PHASE_COMBINATION_DECISION
PHASE_TARGET_SELECTION = y1_play.PHASE_TARGET_SELECTION
PHASE_FACING_SELECTION = y1_play.PHASE_FACING_SELECTION
PHASE_DEFENSE_DECISION = y1_play.PHASE_DEFENSE_DECISION
PHASE_DEFENSE_SELECTION = y1_play.PHASE_DEFENSE_SELECTION
PHASE_ENEMY_TURN = y1_play.PHASE_ENEMY_TURN
PHASE_OUTCOME = y1_play.PHASE_OUTCOME
PHASE_TARGET_CONFIRMATION = y1_play.PHASE_TARGET_CONFIRMATION
PHASE_END_CONFIRMATION = y1_play.PHASE_END_CONFIRMATION
PHASE_TARGET_PREVIEW = y1_play.PHASE_TARGET_PREVIEW
PHASE_TURN_BANNER = y1_play.PHASE_TURN_BANNER
PHASE_SCRIPT_BLOCKED = y1_play.PHASE_SCRIPT_BLOCKED
SETTLEMENT_PHASES = y1_play.SETTLEMENT_PHASES

SIDE_PLAYER = y1_play.SIDE_PLAYER
SIDE_ENEMY = y1_play.SIDE_ENEMY

CONTROL_PLAYER = 0            # battle_control::player
COMMAND_MOVE = 0              # battle_command_type
COMMAND_ABILITY = 1
COMMAND_DIRECT_ATTACK = 2
COMMAND_REPLENISH = 3
COMMAND_REST = 4
COMMAND_END = 5

TARGET_SELF = 0               # target_policy_kind
TARGET_OPPONENT = 2
TARGET_EMPTY = 4

SOURCE_ACTIVE_ACTION = 0      # battle_action_source_kind
SOURCE_NINJA_TOOL = 1
SOURCE_DIRECT_ATTACK = 2

# W22-D5: the normal attack ("忍者组合拳") is a command of its own, not an
# entry of the character's action list.  These numbers are the product's own
# (``game/include/konoha/battle_direct_attack.h``):
#   direct_attack_definition
#     range_shape{ 1, 1 }              -> maximum_distance() = 1 (adjacent)
#     effect_descriptor{ 0x01, 0, 10, 1, 98, 0 } -> potency 10, 1 hit, 98 %
#     target_policy{ opponent_unit }   -> an enemy unit
DIRECT_ATTACK_OPTION = {
    "index": 99,
    "source": SOURCE_DIRECT_ATTACK,
    "source_name": "direct_attack",
    "action_id": 0xFE,
    "cost_kind": "none",
    "cost": 0,
    "range": 1,
    "potency": 10,
    "hits": 1,
    "rate": 98,
}

ESCORT_CHARACTER = 30         # the escorted Konohamaru (char 30, 40 HP)
MOVE_RANGE = 3                # the original's Manhattan radius (U2's dump)


def integer_sqrt(value: int) -> int:
    root = 0
    while (root + 1) * (root + 1) <= value:
        root += 1
    return root


def preview_damage(power: int, hits: int, attack: int, defense: int) -> int:
    """The original ROM's damage formula.

    ``raw = power * attack / 10``, ``factor = 100 - 5 * isqrt(defense)``,
    ``per hit = raw * factor / 100``, ``preview = per hit * hits``
    (the reverse line's ``notes/battle-damage-hit-bindings-20260723.json``,
    the same formula ``u2_route_gen.cpp`` uses).
    """
    raw = power * attack // 10
    factor = max(0, 100 - 5 * integer_sqrt(defense))
    return (raw * factor // 100) * hits


def acceptance(series: list[dict], final: dict[str, int], outcome: int,
               decided: bool, poke_commands: int) -> dict:
    """The evidence that a run is a **real** victory.

    * the battle must have been **decided** by the product code and the
      outcome must be ``1`` (victory);
    * a bee's hit points must have gone **down** -- the player's attack
      really landed;
    * the escort must still be alive;
    * the driver must not have poked a single byte into the ROM.
    """
    bees_start: dict[int, int] = {}
    escort_start = None
    for sample in series:
        for unit in sample["roster"]:
            if unit["side"] == SIDE_ENEMY:
                bees_start.setdefault(unit["slot"], unit["hp"])
            elif unit["character_id"] == ESCORT_CHARACTER:
                escort_start = (unit["hp"] if escort_start is None
                                else escort_start)
    bees_end: dict[int, int] = {}
    escort_end = 0
    for index in range(min(final.get("unit_count", 0), 12)):
        character = final[f"unit_character_ids[{index}]"]
        hp = final[f"unit_hp[{index}]"]
        if character == 55:
            bees_end[index] = hp
        elif character == ESCORT_CHARACTER:
            escort_end = hp
    drops = {slot: bees_start[slot] - bees_end.get(slot, 0)
             for slot in sorted(bees_start)}
    return {
        "outcome": outcome,
        "battle_decided": decided,
        "outcome_is_victory": outcome == 1,
        "bee_hp_start": bees_start,
        "bee_hp_end": bees_end,
        "bee_hp_drop": {slot: value for slot, value in drops.items()
                        if value > 0},
        "bee_hp_dropped": any(value > 0 for value in drops.values()),
        "escort_hp_start": escort_start,
        "escort_hp_end": escort_end,
        "escort_alive": escort_end > 0,
        "poke_commands": poke_commands,
        "from_real_battle": bool(decided and outcome == 1 and
                                  poke_commands == 0),
    }


class Battle(y1_play.Driver):
    """The closed-loop battle driver with the original's target strategy."""

    def __init__(self, probe: probe_module.Probe,
                 telemetry: x1_telemetry.Telemetry,
                 out: pathlib.Path,
                 verbose: bool = True,
                 truth: dict | None = None,
                 allow_tools: bool = True,
                 passive: bool = False) -> None:
        super().__init__(probe, telemetry, out, verbose=verbose)
        self.truth = truth if truth is not None else v1_truth.load(
            pathlib.Path(HERE.parents[1] / "build" / "v1" / "battle-truth.json"))
        self.map = self.truth["map"]
        self.width = int(self.map["width"])
        self.height = int(self.map["height"])
        self.classes = list(self.map["classes"])
        self.actions = self.truth["actions"]
        self.roster = self.truth.get("roster", {})
        self.allow_tools = allow_tools
        self.passive = passive
        self.plan: dict | None = None
        self.expect = "ability"
        self.refused: set[tuple[int, int]] = set()
        # W22-D5: an attack the ROM refuses **every** time must not be
        # re-chosen by the plan on the next turn, otherwise the unit spends
        # every turn on an attack that cannot land (Naruto's ninja tool is
        # consumed after one use, so it is refused from the second turn on
        # and his normal attack -- active action 5, range 1 -- never gets
        # its turn).
        self.persistent_refused: set[tuple[int, int]] = set()
        self.decisions: list[dict] = []
        self.roster_series: list[dict] = []
        self.last_scene_frame = -1
        self.stalled = 0

    # ------------------------------------------------------------- geometry
    def plain(self, x: int, y: int) -> bool:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return self.classes[y * self.width + x] == 0

    @staticmethod
    def distance(first: tuple[int, int], second: tuple[int, int]) -> int:
        return abs(first[0] - second[0]) + abs(first[1] - second[1])

    def reachable(self, origin: tuple[int, int],
                  occupied: set[tuple[int, int]],
                  budget: int = MOVE_RANGE
                  ) -> tuple[dict, dict]:
        """BFS over the plain, unoccupied cells within ``budget`` steps."""
        costs: dict[tuple[int, int], int] = {origin: 0}
        parents: dict[tuple[int, int], tuple[int, int] | None] = {origin: None}
        queue: list[tuple[int, int]] = [origin]
        while queue:
            point = queue.pop(0)
            cost = costs[point]
            if cost >= budget:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (point[0] + dx, point[1] + dy)
                if nxt in costs:
                    continue
                if not self.plain(*nxt) or nxt in occupied:
                    continue
                costs[nxt] = cost + 1
                parents[nxt] = point
                queue.append(nxt)
        return costs, parents

    @staticmethod
    def path_to(parents: dict, cell: tuple[int, int]) -> list[tuple[int, int]]:
        path = [cell]
        while parents.get(path[-1]) is not None:
            path.append(parents[path[-1]])
        path.reverse()
        return path

    def find_attack_cell(self, origin: tuple[int, int],
                         occupied: set[tuple[int, int]],
                         enemy: tuple[int, int], reach: int = 3):
        """The cell from which an attack of range ``reach`` can hit ``enemy``.

        The original (``w4_play.py::act``) scores the cells by the movement
        they cost and tries the origin first, so a cell that is **already**
        in range is always preferred over a cell closer to the enemy.  The
        remake's rule for the range is the Manhattan distance
        (``battle_action_system.h::_preview``).
        """
        gap = self.distance(origin, enemy)
        if 1 <= gap <= reach:
            return origin, gap, [origin]
        costs, parents = self.reachable(origin, occupied)
        best = None
        best_cost = None
        best_distance = None
        for cell, cost in costs.items():
            distance = self.distance(cell, enemy)
            if distance < 1 or distance > reach:
                continue
            if (best is None or (cost, distance) < (best_cost, best_distance)):
                best, best_cost, best_distance = cell, cost, distance
        if best is None:
            return None
        return best, best_distance, self.path_to(parents, best)

    def find_step_toward(self, origin: tuple[int, int],
                         occupied: set[tuple[int, int]],
                         enemy: tuple[int, int]):
        """The reachable cell that gets the actor closest to the enemy."""
        costs, parents = self.reachable(origin, occupied)
        best = None
        best_distance = None
        best_cost = None
        for cell, cost in costs.items():
            gap = self.distance(cell, enemy)
            if best is None or gap < best_distance or (
                    gap == best_distance and cost < best_cost):
                best, best_distance, best_cost = cell, gap, cost
        if best is None:
            return None
        return best, best_distance, self.path_to(parents, best)

    # ---------------------------------------------------------------- state
    def units(self, values: dict[str, int]) -> list[dict]:
        count = min(values["unit_count"], 12)
        return [{
            "slot": index,
            "character_id": values[f"unit_character_ids[{index}]"],
            "active": values[f"unit_active[{index}]"],
            "x": values[f"unit_x[{index}]"],
            "y": values[f"unit_y[{index}]"],
            "hp": values[f"unit_hp[{index}]"],
            "chakra": values[f"unit_chakra[{index}]"],
            "side": values[f"unit_side[{index}]"],
            "control": values[f"unit_control[{index}]"],
        } for index in range(count)]

    def enemies(self, values: dict[str, int]) -> list[dict]:
        return [unit for unit in self.units(values)
                if unit["side"] == SIDE_ENEMY and unit["active"] and
                unit["hp"] > 0]

    def escort(self, values: dict[str, int]) -> dict | None:
        for unit in self.units(values):
            if (unit["side"] == SIDE_PLAYER and unit["active"] and
                    unit["hp"] > 0 and
                    unit["character_id"] == ESCORT_CHARACTER):
                return unit
        return None

    def actor_stats(self, character_id: int) -> dict:
        return self.roster.get(str(character_id), {})

    def roster_snapshot(self, values: dict[str, int]) -> list[dict]:
        """The live roster: the escort and every bee, with their hit points."""
        snapshot = []
        for unit in self.units(values):
            if not unit["active"] or unit["hp"] <= 0:
                continue
            if unit["side"] == SIDE_PLAYER and unit["character_id"] != \
                    ESCORT_CHARACTER:
                continue
            snapshot.append({"slot": unit["slot"],
                             "character_id": unit["character_id"],
                             "hp": unit["hp"],
                             "at": [unit["x"], unit["y"]],
                             "side": unit["side"]})
        return snapshot

    # ------------------------------------------------------------- plumbing
    def settle(self, steps: int = 120, step: int = 30) -> bool:
        """Wait until the scene is idle again.

        A press that arrives while the presentation is still running is
        swallowed by the product code, so every press has to be followed by
        a wait for the scene to go idle.  The wait is a **fixed** number of
        frames (never "poll until"), so two runs of the driver press the same
        keys on the same frames.
        """
        for _ in range(steps):
            values = self.state()
            if (values["presentation_busy"] == 0 and
                    values["map_movement_active"] == 0):
                return True
            self.wait(step)
        return False

    def confirm(self, wanted: tuple[int, ...], tries: int = 4,
                settle_frames: int = 30) -> bool:
        """Press A until the ROM reaches one of the ``wanted`` phases."""
        for _ in range(tries):
            self.press("A", 4)
            self.wait(settle_frames)
            self.settle()
            values = self.state()
            if values["phase"] in wanted:
                return True
        return False

    # -------------------------------------------------------------- planning
    def make_plan(self, values: dict[str, int], actor: dict) -> dict:
        """Plan the unit's turn: the target, the cell to stand on, the order.

        The ranking is the original's (``w4_play.py::act``):

        1. a target this unit can **kill** with one attack comes first;
        2. then the target that deals the most damage;
        3. then the cell that costs the least movement;
        4. then the enemy's slot.

        The **attack** is part of the candidate: the original scores every
        (attack, cell, enemy) triple, and the attack's own range decides
        which cell the unit has to stand on.  Scoring the attacks on their
        own is what makes the ninja tool usable at all -- the tool reaches
        three cells, so the unit may attack from where it stands, while
        忍者组合拳 (range 1) forces the unit to walk next to the bee.
        """
        origin = (actor["x"], actor["y"])
        enemies = self.enemies(values)
        escort = self.escort(values)
        occupied = {(unit["x"], unit["y"]) for unit in self.units(values)
                    if unit["active"] and (unit["x"], unit["y"]) != origin}
        attack = values["cursor_unit_attack"] or self.actor_stats(
            actor["character_id"]).get("attack", 0)
        chakra = actor.get("chakra", 0)
        candidates = []
        for enemy in enemies:
            defense = self.actor_stats(enemy["character_id"]).get("defense", 0)
            for option in self.attack_options(values, actor):
                if (option["cost_kind"] == "current_chakra" and
                        option["cost"] > chakra):
                    continue
                found = self.find_attack_cell(
                    origin, occupied, (enemy["x"], enemy["y"]), option["range"])
                if found is None:
                    continue
                cell, gap, path = found
                damage = preview_damage(option["potency"], option["hits"],
                                        attack, defense)
                escort_gap = self.distance(
                    (escort["x"], escort["y"]), (enemy["x"], enemy["y"])
                ) if escort else 0
                score = (0 if damage >= enemy["hp"] else 1,
                         -min(damage, enemy["hp"]),
                         len(path) - 1,
                         escort_gap,
                         enemy["slot"],
                         option["index"])
                candidates.append({"enemy": enemy, "cell": cell, "gap": gap,
                                   "path": path, "score": score,
                                   "damage": damage, "attack": option})
        candidates.sort(key=lambda item: item["score"])
        if not candidates:
            # No bee is in reach: close the distance to the nearest one
            # (U2's R4) instead of guarding the escort.
            nearest = None
            nearest_gap = None
            for enemy in enemies:
                gap = self.distance(origin, (enemy["x"], enemy["y"]))
                if nearest is None or gap < nearest_gap:
                    nearest, nearest_gap = enemy, gap
            if nearest is None:
                return {"attack": False, "reason": "no enemy",
                        "character_id": actor["character_id"]}
            step = self.find_step_toward(origin, occupied,
                                         (nearest["x"], nearest["y"]))
            if step is None:
                return {"attack": False, "reason": "no reachable cell",
                        "character_id": actor["character_id"]}
            cell, gap, path = step
            return {"attack": False, "reason": "no target in reach",
                    "cell": cell, "path": path, "target": nearest,
                    "gap": gap}
        best = candidates[0]
        return {"attack": True, "candidates": candidates,
                "attack_stat": attack,
                "character_id": actor["character_id"],
                "target": best["enemy"],
                "cell": best["cell"],
                "gap": best["gap"],
                "path": best["path"],
                "chosen_attack": best["attack"],
                "damage": best["damage"]}

    def attack_options(self, values: dict[str, int],
                       actor: dict) -> list[dict]:
        """The attacks the actor could use, read from the action catalogue.

        The live action list is only known in the action selection phase; this
        is the *static* per-character list (U2's measured dump) used for the
        ranking.
        """
        options = []
        for entry in self.character_attacks(actor["character_id"]):
            if (entry["source"], entry["action_id"]) in self.refused:
                continue
            if (entry["source"], entry["action_id"]) in self.persistent_refused:
                continue
            options.append(entry)
        return options

    def character_attacks(self, character_id: int) -> list[dict]:
        """The character's own attacks, from the truth catalogue.

        The **live** action list is read in the action selection phase; this
        static list (U2's measured dump) is what the driver uses to estimate
        the damage of an attack **before** it moves, when it ranks the
        targets.  The entries are normalised: ``index`` is the position in
        the character's action list (the live list has the same order),
        ``source`` is the ROM's ``battle_action_source_kind``.

        W22-D5: the catalogue has **no** ``direct_attack`` entry, so the
        driver never chose the normal attack and the battle never reached
        the original's "Naruto's normal attack" route.  The normal attack is
        a **command** of its own (``battle_command_type::direct_attack``),
        not an entry of the action list, so it is appended here from the
        product's own definition (``battle_direct_attack.h``:
        ``direct_attack_definition`` -- range 1, potency 10, one hit,
        98 % hit rate, target = opponent unit).
        """
        keys = self.actor_stats(character_id).get("actions", [])
        result = []
        for index, key in enumerate(keys):
            source, _, identifier = key.partition(":")
            if source != "active" and not self.allow_tools:
                continue
            table = (self.actions["active"] if source == "active"
                     else self.actions["ninja_tool"])
            entry = table.get(identifier)
            if entry is None or entry["target_kind"] != TARGET_OPPONENT:
                continue
            result.append({
                "index": index,
                "source": (SOURCE_ACTIVE_ACTION if source == "active"
                           else SOURCE_NINJA_TOOL),
                "source_name": source,
                "action_id": int(identifier),
                "cost_kind": entry["cost_kind"],
                "cost": entry["cost"],
                "range": entry["range"],
                "potency": entry["potency"],
                "hits": entry["hits"],
                "rate": entry["rate"],
            })
        result.append(dict(DIRECT_ATTACK_OPTION))
        return result

    def reach(self, actor: dict) -> int:
        """The longest range the actor's usable attacks reach."""
        ranges = [entry["range"] for entry in
                  self.character_attacks(actor["character_id"])]
        return max(ranges) if ranges else 1

    # -------------------------------------------------------------- the turn
    def select_actor(self) -> None:
        """Pick the unit that acts and plan its turn."""
        values = self.state()
        self.roster_series.append({
            "frame": self.frames, "round": values["round"],
            "roster": self.roster_snapshot(values)})
        actor = self.actor_under_cursor(values)
        if actor is None:
            for _ in range(8):
                self.press("Right", 2)
                self.wait(8)
                values = self.state()
                actor = self.actor_under_cursor(values)
                if actor is not None:
                    break
        if actor is None:
            self.decisions.append({"do": "no-actor", "frame": self.frames})
            self.confirm((PHASE_COMMAND_SELECTION, PHASE_MOVE_SELECTION))
            return
        self.plan = self.make_plan(values, actor)
        self.expect = "move"
        self.refused = set()
        self.decisions.append({
            "do": "actor", "frame": self.frames,
            "character_id": actor["character_id"], "hp": actor["hp"],
            "at": [actor["x"], actor["y"]],
            "attack": values["cursor_unit_attack"],
            "roster": self.roster_snapshot(values),
            "plan": {key: value for key, value in self.plan.items()
                     if key != "candidates"},
            "candidates": [
                {"enemy": item["enemy"]["slot"], "hp": item["enemy"]["hp"],
                 "at": [item["enemy"]["x"], item["enemy"]["y"]],
                 "cell": list(item["cell"]), "gap": item["gap"],
                 "damage": item["damage"]}
                for item in self.plan.get("candidates", [])],
        })
        self.log(f"  actor char={actor['character_id']} at "
                 f"({actor['x']},{actor['y']}) hp={actor['hp']} "
                 f"plan={self.plan.get('cell')} gap={self.plan.get('gap')}")
        self.confirm((PHASE_COMMAND_SELECTION, PHASE_MOVE_SELECTION))

    def actor_under_cursor(self, values: dict[str, int]) -> dict | None:
        cursor = (values["cursor_x"], values["cursor_y"])
        for unit in self.units(values):
            if (unit["side"] == SIDE_PLAYER and unit["active"] and
                    unit["hp"] > 0 and unit["control"] == CONTROL_PLAYER and
                    (unit["x"], unit["y"]) == cursor):
                return unit
        return None

    def do_move(self) -> None:
        """Walk the actor to the cell the plan chose and confirm the move."""
        values = self.state()
        plan = self.plan or {}
        path = plan.get("path") or []
        origin = (values["cursor_x"], values["cursor_y"])
        if path:
            for step in path[1:]:
                self.step_cursor(step)
        self.press("A", 4)
        self.wait(30)
        self.settle()
        after = self.state()
        if after["phase"] == PHASE_MOVE_SELECTION:
            # The ROM refused the landing cell: walk back to the origin and
            # confirm the move there (the origin is always legal).
            self.decisions.append({"do": "move-refused",
                                   "frame": self.frames,
                                   "cursor": [after["cursor_x"],
                                              after["cursor_y"]],
                                   "control_error": after["last_control_error"],
                                   "player_error": after["last_player_error"]})
            self.step_cursor(origin)
            self.press("A", 4)
            self.wait(30)
            self.settle()
        self.expect = "ability"

    def step_cursor(self, step: tuple[int, int]) -> bool:
        """Move the cursor one cell at a time onto ``step``."""
        for _ in range(6):
            values = self.state()
            cursor = (values["cursor_x"], values["cursor_y"])
            if cursor == step:
                return True
            if cursor[0] != step[0]:
                key = "Right" if cursor[0] < step[0] else "Left"
            elif cursor[1] != step[1]:
                key = "Down" if cursor[1] < step[1] else "Up"
            else:
                return True
            self.press(key, 2)
            self.wait(8)
        return False

    def do_command(self) -> None:
        """Pick the command the turn needs.

        The remake's command list is ordered ``move, ability, direct_attack,
        replenish_chakra, rest, end_action`` (``battle_command_browser.h``),
        and the turn walks it like this::

            unit_selection -> command_selection(move) -> move_selection
                           -> command_selection(ability) -> action_selection

        so the driver has to know **which** command list it is looking at:
        ``self.expect`` says whether the move, the attack or the end of the
        turn is wanted.
        """
        wanted = {"move": COMMAND_MOVE, "ability": COMMAND_ABILITY}.get(
            self.expect, COMMAND_END)
        # W22-D5: the normal attack is a command of its own
        # (``battle_command_type::direct_attack``).  When the plan picked it,
        # the driver has to walk the command cursor to that entry; the
        # product then goes straight to the target selection (the direct
        # attack is a one-entry action list).
        plan = self.plan or {}
        chosen = plan.get("chosen_attack") or {}
        if chosen.get("source") == SOURCE_DIRECT_ATTACK:
            wanted = COMMAND_DIRECT_ATTACK
        for _ in range(7):
            values = self.state()
            if values["selected_command"] == wanted:
                break
            self.press("Down", 2)
            self.wait(8)
        values = self.state()
        if values["selected_command"] != wanted:
            if wanted == COMMAND_MOVE:
                # The unit cannot move: attack from where it stands.
                wanted = COMMAND_ABILITY
                for _ in range(7):
                    values = self.state()
                    if values["selected_command"] == wanted:
                        break
                    self.press("Down", 2)
                    self.wait(8)
                values = self.state()
            elif wanted == COMMAND_DIRECT_ATTACK:
                # The mission does not offer the normal attack: fall back to
                # the ability command and let the plan's action list decide.
                self.decisions.append({"do": "direct-attack-command-missing",
                                       "frame": self.frames,
                                       "selected": values["selected_command"]})
                wanted = COMMAND_ABILITY
                for _ in range(7):
                    values = self.state()
                    if values["selected_command"] == wanted:
                        break
                    self.press("Down", 2)
                    self.wait(8)
                values = self.state()
            if values["selected_command"] != wanted:
                self.decisions.append({"do": "command-missing",
                                       "frame": self.frames,
                                       "wanted": wanted,
                                       "selected": values["selected_command"]})
        self.press("A", 4)
        self.wait(30)
        self.settle()

    def action_index_stuck(self) -> bool:
        """Is the battle scene still reacting to the keys?

        The action cursor moves when the scene accepts the input.  When the
        attack's combat presentation starts and never ends, the scene keeps
        rendering but swallows every key -- the action cursor stops moving
        (defect D4).
        """
        values = self.state()
        before = values["action_index"]
        self.press("Down", 2)
        self.wait(12)
        after = self.state()["action_index"]
        return after == before

    def action_entry(self, values: dict[str, int]) -> dict:
        """The action the cursor rests on, read off the ROM's telemetry."""
        return {"index": values["action_index"],
                "action_id": values["selected_action_id"],
                "source": values["selected_action_kind"],
                "target_kind": values["selected_action_target_kind"],
                "error": values["selected_action_error"]}

    def walk_to_action(self, want: dict, count: int) -> dict | None:
        """Put the action cursor on the wanted entry and read it back.

        The wanted entry is addressed by its **index** in the character's
        action list -- the live list has the same order as the catalogue --
        so the cursor never rests on an entry the driver does not want (the
        ninja tool's hover starts a combat presentation).
        """
        values = self.state()
        steps = (want["index"] - values["action_index"]) % count
        for _ in range(steps):
            self.press("Down", 2)
            self.wait(8)
        values = self.state()
        entry = self.action_entry(values)
        if (entry["source"] == want["source"] and
                entry["action_id"] == want["action_id"]):
            return entry
        # The live list is not in the catalogue's order: scan it.
        for _ in range(count):
            self.press("Down", 2)
            self.wait(8)
            values = self.state()
            entry = self.action_entry(values)
            if (entry["source"] == want["source"] and
                    entry["action_id"] == want["action_id"]):
                return entry
        return None

    def do_action(self) -> None:
        """Confirm the planned attack.

        The action list is the ROM's own (``action_count``,
        ``selected_action_id``, ``selected_action_target_kind``,
        ``selected_action_error``), so the driver does not have to guess what
        a character can do -- it asks the ROM and reads the catalogue for the
        range and the damage of the entry it picked.

        The plan's attack is addressed by index, so the cursor only ever
        rests on the entry the driver means to use.  When the ROM refuses the
        attack (an error code, or the phase does not leave the action
        selection) the turn is given up and the next turn re-plans.
        """
        if self.passive:
            # The ``--passive`` mode never attacks: it measures what the
            # battle does when the player's attacks cannot land (defect D4).
            self.press("B", 4)
            self.wait(24)
            self.settle()
            self.expect = "end"
            return
        plan = self.plan or {}
        want = plan.get("chosen_attack")
        values = self.state()
        count = max(1, values["action_count"])
        if want is None:
            # No attack reaches the target from here: give the turn up.
            self.log("    no attack reaches the target")
            self.decisions.append({"do": "no-attack", "frame": self.frames,
                                   "gap": plan.get("gap"),
                                   "reason": plan.get("reason", "no plan")})
            self.press("B", 4)
            self.wait(24)
            self.settle()
            self.expect = "end"
            return
        entry = self.walk_to_action(want, count)
        self.decisions.append({
            "do": "action-list", "frame": self.frames,
            "want": {"index": want["index"], "source": want["source"],
                     "action_id": want["action_id"], "range": want["range"],
                     "potency": want["potency"], "hits": want["hits"],
                     "rate": want["rate"]},
            "gap": plan.get("gap"),
            "chosen": entry,
            "damage": plan.get("damage", 0),
        })
        if (entry is None or entry["target_kind"] != TARGET_OPPONENT or
                entry["error"] != 0):
            # The ROM refuses this attack: do not try it again this turn.
            self.refused.add((want["source"], want["action_id"]))
            # W22-D5: learn it for good -- the plan must not pick it again.
            self.persistent_refused.add((want["source"], want["action_id"]))
            self.decisions.append({
                "do": "action-refused", "frame": self.frames,
                "action_id": want["action_id"],
                "control_error": values["last_control_error"],
                "player_error": values["last_player_error"]})
            self.press("B", 4)
            self.wait(24)
            self.settle()
            self.expect = "end"
            return
        self.press("A", 4)
        self.wait(30)
        self.settle()
        after = self.state()
        if after["phase"] == PHASE_ACTION_SELECTION:
            # The ROM did not leave the action selection: the attack's
            # combat presentation swallowed the input (defect D4).
            self.refused.add((want["source"], want["action_id"]))
            # W22-D5: learn it for good -- the plan must not pick it again.
            self.persistent_refused.add((want["source"], want["action_id"]))
            self.decisions.append({
                "do": "action-refused", "frame": self.frames,
                "action_id": want["action_id"],
                "control_error": after["last_control_error"],
                "player_error": after["last_player_error"]})
            self.press("B", 4)
            self.wait(24)
            self.settle()
            self.expect = "end"
            return
        if after["phase"] == PHASE_COMBINATION_DECISION:
            self.press("A", 4)
            self.wait(30)
            self.settle()
        self.expect = "end"

    def action_definition(self, entry: dict) -> dict | None:
        table = (self.actions["active"] if entry["source"] == SOURCE_ACTIVE_ACTION
                 else self.actions["ninja_tool"])
        return table.get(str(entry["action_id"]))

    def do_target(self) -> None:
        """Put the cursor on the target and confirm it."""
        candidates = []
        plan = self.plan or {}
        for item in plan.get("candidates", []):
            candidates.append(item)
        if not candidates and plan.get("target") is not None:
            candidates = [{"enemy": plan["target"]}]
        values = self.state()
        if not candidates:
            self.decisions.append({"do": "no-target", "frame": self.frames})
            self.press("B", 4)
            self.wait(24)
            self.settle()
            self.expect = "end"
            return
        for item in candidates:
            enemy = item["enemy"] if isinstance(item, dict) and "enemy" in item \
                else item
            cell = (enemy["x"], enemy["y"])
            if not self.place_cursor(cell):
                continue
            self.press("A", 4)
            accepted = False
            for _ in range(8):
                self.wait(30)
                self.settle()
                after = self.state()
                if after["phase"] != PHASE_TARGET_SELECTION:
                    accepted = True
                    break
            if accepted:
                self.decisions.append({
                    "do": "target-accepted", "frame": self.frames,
                    "enemy": enemy["slot"], "cell": list(cell),
                    "phase": after["phase"]})
                self.expect = "end"
                return
            self.decisions.append({
                "do": "target-refused", "frame": self.frames,
                "enemy": enemy["slot"], "cell": list(cell),
                "control_error": after["last_control_error"],
                "player_error": after["last_player_error"]})
            self.press("B", 4)
            self.wait(24)
            self.settle()
        # Every target was refused: give the turn up.
        self.press("B", 4)
        self.wait(24)
        self.settle()
        self.expect = "end"

    def do_defense_decision(self) -> None:
        """Answer the defence question with *no* (U2's R3).

        The remake's defence entries all report
        ``defense_preparation_error::unsupported_category``, so the only
        legal answer is to take the hit without a defence action.
        """
        self.press("Down", 2)
        self.wait(8)
        self.press("A", 4)
        self.wait(30)
        self.settle()
        if self.state()["phase"] == PHASE_DEFENSE_DECISION:
            self.press("A", 4)
            self.wait(30)
            self.settle()

    # ----------------------------------------------------------- settlement
    def enter_chain_by_poke(self) -> dict:
        """Enter the settlement chain by poking the controller.

        ⚠️ **This is a tool validation mode only.**  The controller's phase
        and outcome bytes are poked, so the chain that follows is **not** a
        real victory -- the receipt says so and the acceptance block stays
        false.  It exists so the settlement walker and the per-screen
        comparison can be proven on a ROM whose battle cannot be won yet
        (defect D4).
        """
        import z1_settlement_chain

        current = self.state()["phase"]
        address = z1_settlement_chain.locate_phase_byte(
            self.probe, self.telemetry, current)
        outcome_address = address + 0x228
        self.probe.run(f"poke {address} {z1_settlement_chain.PHASE_OUTCOME}")
        self.probe.run(f"poke {outcome_address} "
                       f"{z1_settlement_chain.OUTCOME_WIN}")
        self.wait(8)
        values = self.state()
        return {"phase_address": address, "outcome_address": outcome_address,
                "phase_after_poke": values["phase"],
                "outcome_after_poke": values["condition_outcome"]}

    def wait_stable(self, probe_shot: pathlib.Path, tries: int = 12,
                    gap: int = 20) -> str:
        """Wait until the rendered frame stops changing.

        The chain's first screen is drawn behind the battle-to-settlement
        black field, so a fixed wait photographs the fade instead of the
        screen.  Two identical frames in a row mean the picture has settled.
        """
        previous = ""
        for _ in range(tries):
            self.probe.run(f"shot {probe_shot}")
            current = y1_play.sha256_file(probe_shot)
            if current == previous:
                return current
            previous = current
            self.wait(gap)
        return previous

    def play_settlement_chain(self, settle_frames: int = 90,
                              max_pages: int = 48) -> dict:
        """Walk the settlement chain with the **buttons only**.

        The chain's pages are told apart by the sha256 of the rendered
        frame, not by the phase: the training stage shows six pages under one
        phase.  A page is written only when the picture changed, so the
        capture holds exactly one frame per screen -- which is what the
        per-screen comparison needs.

        When a button leaves the picture unchanged, the next button of the
        list is tried: the chain's last training page swallows A.

        ⚠️ **Nothing is poked here.**  The chain is walked the way a player
        walks it, so every frame of the capture is the product's own.
        """
        keys = ["A", "B", "Right", "Down", "Left", "Up"]
        probe_shot = self.out / "chain-probe.png"
        result: dict[str, object] = {"pages": [], "presses": 0,
                                     "final_phase": None, "poked": False}
        previous_sha: str | None = None
        key_index = 0
        for index in range(max_pages):
            values = self.state()
            phase = values["phase"]
            if phase not in SETTLEMENT_PHASES:
                result["final_phase"] = phase
                result["final_phase_name"] = x1_telemetry.phase_name(phase)
                break
            self.wait(settle_frames)
            values = self.state()
            phase = values["phase"]
            if phase not in SETTLEMENT_PHASES:
                result["final_phase"] = phase
                result["final_phase_name"] = x1_telemetry.phase_name(phase)
                break
            sha = self.wait_stable(probe_shot)
            if sha != previous_sha:
                name = x1_telemetry.phase_name(phase)
                path = self.shots / f"page-{index:03d}-{name}.png"
                path.write_bytes(probe_shot.read_bytes())
                entry = {
                    "index": index,
                    "file": path.name,
                    "phase": phase,
                    "phase_name": name,
                    "training_detail_page": values["training_detail_page"],
                    "outcome": values["condition_outcome"],
                    "round": values["round"],
                    "result_participant_count":
                        values["result_participant_count"],
                    "result_total_experience":
                        values["result_total_experience"],
                    "sha256": sha,
                }
                self.captures.append(entry)
                result["pages"].append(entry)
                previous_sha = sha
                key_index = 0
            else:
                key_index += 1
                if key_index >= len(keys):
                    result["stuck_at"] = index
                    result["stuck_phase"] = phase
                    break
            self.wait_idle()
            self.press(keys[key_index])
            result["presses"] = int(result["presses"]) + 1
            if result["pages"] and result["pages"][-1].get("index") == index:
                result["pages"][-1]["advanced_by"] = keys[key_index]
        values = self.state()
        result["final_phase"] = values["phase"]
        result["final_phase_name"] = x1_telemetry.phase_name(values["phase"])
        result["outcome"] = values["condition_outcome"]
        result["round"] = values["round"]
        result["frames_run"] = self.frames
        return result

    # ------------------------------------------------------------ the battle
    def play_battle(self, max_turns: int = 60,
                    max_frames: int = 600000) -> bool:
        for turn in range(max_turns):
            values = self.state()
            phase = values["phase"]
            if phase in SETTLEMENT_PHASES:
                self.decisions.append({"do": "battle-decided", "turn": turn,
                                       "frame": self.frames,
                                       "outcome": values["condition_outcome"],
                                       "round": values["round"]})
                return True
            if self.frames > max_frames:
                self.decisions.append({"do": "frame-budget-exhausted",
                                       "frame": self.frames})
                return False
            # The remake freezes (the scene stops advancing) when a ninja tool
            # is confirmed while an enemy is inside the tool's range; the
            # driver notices it instead of spinning until the frame budget.
            if values["scene_frame"] != self.last_scene_frame:
                self.last_scene_frame = values["scene_frame"]
                self.stalled = 0
            else:
                self.stalled += 1
                if self.stalled >= 6:
                    self.decisions.append({
                        "do": "rom-frozen", "frame": self.frames,
                        "phase": phase, "scene_frame": values["scene_frame"]})
                    # The frozen screen is the evidence: what the product
                    # shows when the battle stops is worth keeping.
                    try:
                        shot = self.shot(f"rom-frozen-phase{phase}")
                        self.decisions[-1]["shot"] = shot.name
                    except Exception as error:  # pragma: no cover
                        self.decisions[-1]["shot_error"] = str(error)
                    return False
            if phase == PHASE_ACTION_SELECTION and not self.passive:
                if self.action_index_stuck():
                    self.decisions.append({
                        "do": "scene-input-dead", "frame": self.frames,
                        "phase": phase,
                        "action_index": values["action_index"],
                        "scene_frame": values["scene_frame"],
                        "note": "the action list no longer reacts to the "
                                "keys: the combat presentation of the "
                                "attack never ends (defect D4)"})
                    return False
            self.decisions.append({
                "do": "phase", "frame": self.frames, "phase": phase,
                "name": x1_telemetry.phase_name(phase),
                "round": values["round"], "busy": values["presentation_busy"],
                "command": values["selected_command"],
                "action_index": values["action_index"],
                "cursor": [values["cursor_x"], values["cursor_y"]],
                "outcome": values["condition_outcome"],
            })
            if phase == PHASE_SCRIPT_BLOCKED:
                self.advance_dialogue()
                continue
            if phase == PHASE_TURN_BANNER:
                self.press("A", 4)
                self.wait(30)
                self.settle()
                continue
            if phase == PHASE_UNIT_SELECTION:
                self.select_actor()
                continue
            if phase == PHASE_MOVE_SELECTION:
                self.do_move()
                continue
            if phase == PHASE_COMMAND_SELECTION:
                self.do_command()
                continue
            if phase == PHASE_ACTION_SELECTION:
                self.do_action()
                continue
            if phase == PHASE_TARGET_SELECTION:
                self.do_target()
                continue
            if phase == PHASE_COMBINATION_DECISION:
                self.press("A", 4)
                self.wait(30)
                self.settle()
                continue
            if phase == PHASE_DEFENSE_DECISION:
                self.do_defense_decision()
                continue
            if phase in (PHASE_TARGET_PREVIEW, PHASE_TARGET_CONFIRMATION,
                         PHASE_FACING_SELECTION, PHASE_END_CONFIRMATION,
                         PHASE_CHAKRA_SELECTION, PHASE_REST_CONFIRMATION,
                         PHASE_DEFENSE_SELECTION):
                self.press("A", 4)
                self.wait(30)
                self.settle()
                continue
            if phase == PHASE_ENEMY_TURN:
                self.wait(30)
                continue
            self.wait(30)
        self.decisions.append({"do": "turn-budget-exhausted",
                               "frame": self.frames})
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-v1" /
                        "mgba-probe.exe")
    parser.add_argument("--truth", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "v1" /
                        "battle-truth.json")
    parser.add_argument("--boot", action="store_true")
    parser.add_argument("--state", type=pathlib.Path, default=None)
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--settle-frames", type=int, default=90)
    parser.add_argument("--no-tools", action="store_true",
                        help="do not use the ninja tools: the remake hangs "
                             "when a tool is confirmed while an enemy is "
                             "inside its range (defect D4)")
    parser.add_argument("--use-tools", action="store_true",
                        help="use the ninja tools (the original's rule: "
                             "十字手里剑 reaches three cells).  Only safe "
                             "once defect D4 is fixed -- the tool's combat "
                             "presentation must end")
    parser.add_argument("--passive", action="store_true",
                        help="never attack: measures what the battle does "
                             "when the player's attacks cannot land (D4)")
    parser.add_argument("--poke-settlement", action="store_true",
                        help="TOOL VALIDATION only: enter the settlement "
                             "chain by poking the controller's phase and "
                             "outcome, then walk it with the buttons.  The "
                             "receipt says so and the acceptance block "
                             "stays false -- this is NOT a real victory")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    truth = v1_truth.load(args.truth)
    started = time.time()
    receipt: dict[str, object] = {
        "schema": "konoha.s49-v1-real-battle.v1",
        "rom": str(args.rom),
        "rom_sha256": y1_play.sha256_file(args.rom),
        "truth": str(args.truth),
        "truth_sha256": y1_play.sha256_file(args.truth),
        "entry": {
            "method": "real battle: the closed-loop driver plays the battle "
                      "with the buttons only, and the outcome is the product "
                      "code's own decision",
            "poke": False,
            "use_tools": bool(args.use_tools and not args.no_tools),
        },
    }
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        driver = Battle(probe, x1_telemetry.Telemetry(probe), args.out,
                        verbose=not args.quiet, truth=truth,
                        allow_tools=bool(args.use_tools and
                                         not args.no_tools),
                        passive=args.passive)
        if args.state:
            probe.load(args.state)
            driver.frames = 0
        elif args.boot:
            boot = w1_boot.Boot(probe, args.out / "boot")
            receipt["boot"] = boot.run()
        else:
            probe.run("frames 120 0x00000000")
            driver.frames = 120
        driver.log(f"telemetry at 0x{driver.telemetry.locate(verbose=True):08X}")
        decided = False
        settlement: dict[str, object] = {}
        if args.poke_settlement:
            # TOOL VALIDATION ONLY: the chain is entered by poking the
            # controller, so this run is **not** a real victory.
            receipt["entry"] = {
                "method": "TOOL VALIDATION: the settlement chain was entered "
                          "by poking the controller's phase and outcome; this "
                          "is NOT a real victory",
                "poke": True,
                "use_tools": False,
            }
            receipt["poke_entry"] = driver.enter_chain_by_poke()
            settlement = driver.play_settlement_chain(args.settle_frames,
                                                      max_pages=48)
        else:
            decided = driver.play_battle(args.max_turns)
            if decided:
                settlement = driver.play_settlement_chain(args.settle_frames,
                                                          max_pages=48)
            else:
                values = driver.state()
                settlement = {"final_phase": values["phase"],
                              "final_phase_name":
                                  x1_telemetry.phase_name(values["phase"]),
                              "outcome": values["condition_outcome"],
                              "round": values["round"], "pages": []}
        values = driver.state()
        poke_commands = sum(1 for command in probe.commands
                            if command.split(" ", 1)[0] == "poke")
        receipt["entry"]["poke_commands"] = poke_commands
        receipt["entry"]["probe_commands"] = len(probe.commands)
        receipt.update({
            "battle_decided": decided,
            "outcome": values["condition_outcome"],
            "round": values["round"],
            "frames_run": driver.frames,
            "keys_pressed": driver.keys,
            "errors": driver.errors,
            "settlement": settlement,
            "roster_series": driver.roster_series,
            "acceptance": acceptance(driver.roster_series, values,
                                     values["condition_outcome"], decided,
                                     poke_commands),
            "decisions": driver.decisions,
            "captures": driver.captures,
        })
        (args.out / "stderr.txt").write_text(
            "\n".join(probe.stderr) + "\n", encoding="utf-8", newline="\n")
    receipt["wall_seconds"] = round(time.time() - started, 1)
    (args.out / "battle.json").write_text(
        json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in receipt.items()
                      if key not in ("decisions", "settlement", "captures",
                                     "roster_series")},
                     ensure_ascii=False, indent=1))
    print("settlement pages:", len(settlement.get("pages", [])),
          "final:", settlement.get("final_phase_name"))
    return 0 if decided else 1


if __name__ == "__main__":
    raise SystemExit(main())
