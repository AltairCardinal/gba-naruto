#!/usr/bin/env python3
"""Closed-loop driver that plays the original S49 battle 14 to a decision.

Stream W4 (fifth attempt).  What is different from the four earlier attempts
(K -> M -> W3 -> X3):

* **The recording side is frame exact.**  The Lua frame callback writes every
  frame of the run, so the victory / settlement frames cannot be stale.
* **The state side is decoded, not guessed.**  The unit record layout of the
  original ROM was measured this stream (one 4212 byte pool dump, parsed
  offline)::

      +0x00  character id (0 = the slot is empty / the unit is defeated)
      +0x01  忍具   ninja tools left
      +0x07  current chakra          +0x08  maximum chakra
      +0x0C  current HP               +0x0E  maximum HP
      +0xC1  acting flag              +0xC4/+0xC5  cell at turn start
      +0xC7/+0xC8  live cell          +0xCC  affiliation (0 player, 1 enemy)

  The previous streams treated the HP array as the source of truth and were
  wrong in two ways that killed them: a defeated enemy **keeps its last HP**
  (so "HP > 0" does not mean alive) and the array **lags the attack
  animation** (so a hit is invisible for a few hundred frames).
* **Victory is read, not recognised.**  ``0x02026807`` is the battle result
  byte (0 = unsettled, 1 = victory, 2 = escort failure) -- the reverse
  engineering line's ``analyze_battle_objective_transitions.py``.
* **Pixels only name the message boxes** (forecast / confirm / error), whose
  signatures stream W3 calibrated.

Usage::

    python tools/s49_victory_capture/w4_play.py \
        --state "<...>/scenario-49-battle-14-turn4-two-kills.ss9" \
        --out build/s49-victory-capture/w4/play
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import os  # noqa: E402

import battle_obs  # noqa: E402
import probe as probe_module  # noqa: E402
import s49_state  # noqa: E402

REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe-w4" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-turn4-two-kills.ss9")
MAP_TRUTH = REPO / "tools" / "s49_orig_map" / "battle-14-map-truth.json"
LUA_SCRIPT = HERE / "capture_victory_frames.lua"

ADDR_RESULT = 0x02026807          # 0 = unsettled, 1 = victory, 2 = failure
ADDR_CURSOR = 0x02026A78
ADDR_MENU_LEVEL = 0x02026A8C
ADDR_MENU_CURSOR = 0x0200A8BA
SLOTS = 9
MOVE_RANGE = 3

# per character attack table, read off the original's own jutsu list screens
# (stream W3 for the lists, stream W4 for the 消耗查克拉 / 攻撃力 / 距離 /
# 範囲 / 成功率 panels):
#
#   slot 1 漩涡鸣人  变身术 / 影分身术 / 忍者组合拳 / 十字手里剑
#           十字手里剑  27 伤害, 距离 3 直, 忍具 1
#           忍者组合拳  10 伤害, 距离 1,     消耗体力 0
#   slot 2 宁智波佐助  火遁术 / 影分身术 / 忍者组合拳
#           火遁术      15 伤害, 距离 2 直, 消耗查克拉 2
#   slot 3 春野樱     影分身术 / 分身术 / 忍者组合拳
#           忍者组合拳  10 伤害, 距离 1,     消耗体力 0
ATTACKS = {
    1: [{"index": 3, "range": 3, "chakra": 0, "damage": 27, "name": "十字手里剑"},
        {"index": 2, "range": 1, "chakra": 0, "damage": 10, "name": "忍者组合拳"}],
    2: [{"index": 0, "range": 2, "chakra": 2, "damage": 15, "name": "火遁术"},
        {"index": 2, "range": 1, "chakra": 0, "damage": 10, "name": "忍者组合拳"}],
    3: [{"index": 2, "range": 1, "chakra": 0, "damage": 10, "name": "忍者组合拳"}],
}

MENU_MOVE = 0
MENU_JUTSU = 1
MENU_REST = 3
MENU_END = 4


def load_walkable() -> set:
    document = json.loads(MAP_TRUTH.read_text(encoding="utf-8"))
    cells = set()
    for index, value in enumerate(document["collision_grid"]):
        if value in (0, 3):
            cells.add((index % 15, index // 15))
    return cells


def manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class Player:
    def __init__(self, probe: probe_module.Probe, out_dir: pathlib.Path,
                 walkable: set, verbose: bool = False,
                 endgame_frames: int = 1800,
                 record_victory_only: bool = False,
                 lua_script: pathlib.Path | None = None,
                 endgame_presses: int = 24,
                 endgame_settle: int = 240) -> None:
        self.probe = probe
        self.out_dir = out_dir
        self.walkable = walkable
        self.verbose = verbose
        self.raw_path = out_dir / "frame.raw"
        self.shot_index = 0
        self.log: list[dict] = []
        self.actions = 0
        self.hits = 0
        self.acted: set[int] = set()
        self.no_tool: set[int] = set()      # jutsu indices already used up
        self.enemy_cells: dict = {}         # to detect a new player phase
        self.blocked_cells: set = set()      # cells the cursor cannot reach
        self.endgame_frames = endgame_frames
        self.record_victory_only = record_victory_only
        self.lua_script = lua_script or LUA_SCRIPT
        self.endgame_presses = endgame_presses
        self.endgame_settle = endgame_settle
        self.current_slot = 0

    # ------------------------------------------------------------- helpers
    def record(self, event: str, **extra) -> None:
        row = {"event": event}
        row.update(extra)
        self.log.append(row)
        if self.verbose:
            print(f"    {event}: {json.dumps(extra, ensure_ascii=False)}", flush=True)

    def press(self, key: str, settle: int = 60, hold: int = 4) -> None:
        mask = probe_module.key_mask([key])
        self.probe.frames(hold, mask)
        self.probe.frames(1, 0)
        self.probe.frames(settle, 0)
        self.record("key", k=key)

    def run(self, frames: int) -> None:
        if frames:
            self.probe.frames(frames, 0)

    # ------------------------------------------------------------- observe
    def observe(self) -> dict:
        from PIL import Image
        self.probe.run(f"rawshot {self.raw_path}")
        raw = self.raw_path.read_bytes()
        image = Image.frombytes("RGBA", (battle_obs.RAW_WIDTH, battle_obs.RAW_HEIGHT),
                                raw).convert("RGB")
        level = self.probe.dump(ADDR_MENU_LEVEL, 1)[0]
        menu_cursor = self.probe.dump(ADDR_MENU_CURSOR, 1)[0]
        cursor = self.probe.dump(ADDR_CURSOR, 3)
        result = self.probe.dump(ADDR_RESULT, 1)[0]
        units = []
        for slot in range(1, SLOTS + 1):
            base = s49_state.POOL_ADDRESS + slot * s49_state.POOL_STRIDE
            head = self.probe.dump(base + 0x00, 12)
            vitals = self.probe.dump(base + 0x0C, 4)
            blob = self.probe.dump(base + 0xC0, 13)
            units.append({
                "slot": slot,
                "name": s49_state.SLOT_NAMES.get(slot, f"slot-{slot}"),
                "char_id": head[0],
                "tools": head[1],
                "chakra": head[7],
                "chakra_max": head[8],
                "hp": vitals[0],
                "hp_max": vitals[2],
                "cell": [blob[7], blob[8]],
                "acting": bool(blob[1]),
                "side": blob[12],
            })
        sig = battle_obs.signature(image)
        return {"image": image, "sig": sig, "screen": self.classify(sig),
                "level": level, "menu_cursor": menu_cursor,
                "cursor": list(cursor), "result": result, "units": units}

    @staticmethod
    def classify(sig: dict) -> str:
        """Name the screen (stream W3's calibrated signatures, in this order)."""
        # The order matters.  The jutsu list paints a description box that
        # overlaps the error region (W3 measured err=5676 for the list
        # itself), so the list has to be recognised before the error box.
        # Measured on this ROM: action5 border=94/dark=631, action2
        # border=42/dark=304, jutsu list border=8/dark=723..953 and the
        # light info panel=4874..5170.
        if sig["border_rows"] >= 70:
            return "action5"
        if sig["border_rows"] >= 25:
            return "action2"
        if sig["panel_light"] > 3000 and sig["menu_dark"] >= 500:
            return "jutsu"
        if sig["menu_dark"] >= 500:
            return "jutsu"
        if sig["confirm_light"] > 1000:
            return "confirm"
        if sig["error_light"] > 1000:
            return "error"
        if sig["dialogue_light"] > 1000:
            return "message"
        if sig["hatch"] > 1000:
            return "move"
        if sig["path"] > 200:
            return "aim"
        if sig["panel_light"] > 3000:
            return "info"
        return "none"

    # -------------------------------------------------------------- helpers
    def live_enemies(self, obs) -> list:
        """Enemies that are still in the battle.

        ``char_id == 0`` marks a defeated unit (its HP stays at the last
        value), so the character id -- not the HP -- decides liveness.
        """
        return [unit for unit in obs["units"]
                if unit["side"] == 1 and unit["char_id"] != 0 and unit["hp"] > 0]

    def live_allies(self, obs) -> list:
        return [unit for unit in obs["units"]
                if unit["side"] == 0 and unit["char_id"] != 0 and unit["hp"] > 0]

    def acting_ally(self, obs):
        """The ally the game is currently waiting for.

        The acting flag is ``unit+0xC1``.  A defeated *enemy* can still carry
        it, so only the player side counts.
        """
        for unit in obs["units"]:
            if unit["side"] == 0 and unit["acting"] and unit["char_id"] != 0:
                return unit
        return None

    def in_line(self, origin, target, reach) -> bool:
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        if dx != 0 and dy != 0:
            return False
        return 1 <= abs(dx) + abs(dy) <= reach

    def reachable(self, origin, occupied) -> list:
        cells = []
        for dx in range(-MOVE_RANGE, MOVE_RANGE + 1):
            for dy in range(-MOVE_RANGE, MOVE_RANGE + 1):
                if abs(dx) + abs(dy) > MOVE_RANGE or (dx == 0 and dy == 0):
                    continue
                cell = (origin[0] + dx, origin[1] + dy)
                if cell not in self.walkable or cell in occupied:
                    continue
                cells.append(cell)
        cells.sort(key=lambda cell: (manhattan(origin, cell), cell[1], cell[0]))
        return cells

    def path_to(self, origin, target, blocked=frozenset()):
        """A walkable path from ``origin`` to ``target`` (BFS on the grid).

        The cursor cannot cross a blocked cell: battle 14 has a river row at
        y=10, so a straight walk from (8,11) to (8,8) jams on (8,10) and the
        game answers 「請在移動範圍內選擇」.  The path has to go around.
        """
        from collections import deque
        origin = (origin[0], origin[1])
        target = (target[0], target[1])
        if origin == target:
            return [origin]
        if target not in self.walkable:
            return None
        seen = {origin: None}
        queue = deque([origin])
        while queue:
            cell = queue.popleft()
            for nxt in ((cell[0] + 1, cell[1]), (cell[0] - 1, cell[1]),
                        (cell[0], cell[1] + 1), (cell[0], cell[1] - 1)):
                if nxt in seen or nxt not in self.walkable or nxt in blocked:
                    continue
                seen[nxt] = cell
                if nxt == target:
                    path = [target]
                    while seen[path[-1]] is not None:
                        path.append(seen[path[-1]])
                    return list(reversed(path))
                queue.append(nxt)
        return None

    def walk_cursor(self, obs, cell, limit: int = 60,
                    block_occupied: bool = False) -> bool:
        """Walk the cell cursor to `cell`.

        The cursor is clamped by the game (the move phase clamps it to the
        reachable set), so the position is re-read after every press instead
        of being counted locally -- a counted walk silently diverges and the
        game answers 「請在移動範圍內選擇」.
        """
        cell = (cell[0], cell[1])
        obs = self.observe()
        origin = (obs["cursor"][0], obs["cursor"][1])
        # The move phase refuses to land on an occupied cell, but the aim
        # cursor has to be able to stand **on** the enemy it targets.
        blocked = set()
        if block_occupied:
            blocked = {(entry["cell"][0], entry["cell"][1])
                       for entry in obs["units"] if entry["char_id"] != 0}
        path = self.path_to(origin, cell, blocked)
        if path is None:
            self.record("no-path", origin=list(origin), want=list(cell))
            return False
        for step in path[1:]:
            for _ in range(limit):
                obs = self.observe()
                cx, cy = obs["cursor"][0], obs["cursor"][1]
                if (cx, cy) == step:
                    break
                key = ("Right" if cx < step[0] else "Left") if cx != step[0] else (
                    "Down" if cy < step[1] else "Up")
                self.press(key, settle=12)
            else:
                self.record("cursor-unreachable", want=list(step))
                return False
        obs = self.observe()
        ok = (obs["cursor"][0], obs["cursor"][1]) == cell
        if not ok:
            self.record("cursor-unreachable", want=list(cell),
                        at=list(obs["cursor"][:2]))
        return ok

    def aim_to(self, obs, cell, limit: int = 24) -> bool:
        """Walk the aim cursor onto ``cell``.

        In the aim mode the cursor only travels along the shot line (the
        range preview), so it is walked directly instead of over a path.
        """
        cell = (cell[0], cell[1])
        for _ in range(limit):
            obs = self.observe()
            cx, cy = obs["cursor"][0], obs["cursor"][1]
            if (cx, cy) == cell:
                return True
            if cx != cell[0]:
                key = "Right" if cx < cell[0] else "Left"
            elif cy != cell[1]:
                key = "Down" if cy < cell[1] else "Up"
            else:
                return True
            self.press(key, settle=12)
        self.record("aim-unreachable", want=list(cell),
                    at=list(self.observe()["cursor"][:2]))
        return False

    def pick_menu(self, obs, index) -> None:
        """Put the cursor on ``index`` of the **jutsu list**.

        The jutsu list cursor register (0x0200A8BA) is 0 based and tracks the
        highlight exactly (measured: Down x3 -> 0,1,2,3 on Naruto's four entry
        list).
        """
        for _ in range(8):
            current = obs["menu_cursor"]
            if current == index:
                return
            self.press("Down" if current < index else "Up", settle=12)
            obs = self.observe()

    def menu_top(self, obs) -> None:
        """Put the menu highlight on the first entry.

        The action menu does **not** use the jutsu list cursor register: with
        the highlight on 「移動」 the register still reads 1, so a counted walk
        lands on the wrong entry (measured this stream).  The highlight also
        *persists* between openings, so the entry has to be addressed
        relative to the top of the list.  Pressing Up as many times as the
        menu has entries always lands on the first entry, whether the menu
        wraps or clamps.
        """
        entries = 5 if obs["screen"] == "action5" else 2
        for _ in range(entries):
            self.press("Up", settle=12)

    def action(self, obs, offsets, want, budget: int = 900):
        """Use an entry of the action menu (0 = the first entry)."""
        for offset in offsets:
            obs = self.observe()
            if obs["screen"] not in ("action5", "action2"):
                return obs
            self.menu_top(obs)
            for _ in range(offset):
                self.press("Down", settle=12)
            self.press("A")
            obs = self.wait_for(
                lambda o: o["screen"] in ("move", "jutsu", "action5", "action2",
                                           "message", "confirm", "error", "none"),
                budget=budget)
            if obs["screen"] in want:
                return obs
            self.press("B")
        return self.observe()

    def shot(self, label: str) -> None:
        self.shot_index += 1
        path = self.out_dir / "shots" / f"{self.shot_index:04d}-{label}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.probe.shot(path)

    def wait_for(self, predicate, budget: int = 2400, step: int = 30):
        waited = 0
        while waited < budget:
            obs = self.observe()
            if predicate(obs):
                return obs
            self.run(step)
            waited += step
        return self.observe()

    # ----------------------------------------------------------------- move
    def do_move(self, obs, cell) -> bool:
        if obs["screen"] != "action5":
            return False
        obs = self.action(obs, (0, 1, 2, 3, 4), ("move",))
        if obs["screen"] != "move":
            self.record("move-not-open", screen=obs["screen"])
            return False
        if not self.walk_cursor(obs, cell, block_occupied=True):
            self.record("move-cursor-failed", cell=list(cell))
            self.press("B")
            return False
        self.press("A")
        obs = self.wait_for(
            lambda o: o["screen"] in ("action5", "action2", "none", "error"),
            budget=1800)
        if obs["screen"] == "error":
            # the game refused the landing cell: 「請在移動範圍內選擇」
            self.record("move-refused", cell=list(cell), sig=obs["sig"])
            self.press("B")
            return False
        return True

    # --------------------------------------------------------------- attack
    def open_jutsu(self, obs, index) -> bool:
        """Open the jutsu list and put the cursor on ``index``."""
        if obs["screen"] == "action5":
            obs = self.action(obs, (1, 0, 2, 3, 4), ("jutsu",))
            if obs["screen"] != "jutsu":
                self.record("jutsu-not-open", screen=obs["screen"],
                            sig=obs["sig"], level=obs["level"])
                self.shot("jutsu-not-open")
                return False
        elif obs["screen"] == "action2":
            self.menu_top(obs)
            self.press("A")
        obs = self.wait_for(lambda o: o["screen"] in ("jutsu", "info", "error"),
                             budget=900)
        if obs["screen"] != "jutsu":
            self.record("jutsu-not-open", screen=obs["screen"],
                        sig=obs["sig"], level=obs["level"],
                        menu_cursor=obs["menu_cursor"])
            self.shot("jutsu-not-open")
            return False
        self.run(40)                     # the list animates in
        self.pick_menu(obs, index)
        obs = self.observe()
        if obs["menu_cursor"] != index:
            self.record("jutsu-index-missing", index=index,
                        cursor=obs["menu_cursor"])
            # the entry is gone from the list (十字手里剑 can only be used
            # once per battle) -> do not try it again in this battle
            self.no_tool.add((self.current_slot, index))
            self.press("B")
            return False
        self.press("A")
        obs = self.wait_for(lambda o: o["screen"] in ("aim", "info", "error"),
                             budget=900)
        if obs["screen"] == "info":
            self.press("A")
            obs = self.wait_for(lambda o: o["screen"] in ("aim", "error"),
                                 budget=900)
        if obs["screen"] == "error":
            self.record("jutsu-refused", sig=obs["sig"])
            self.press("B")
            return False
        return True

    def try_attack(self, obs, unit, attack, target_cell, target_slot) -> bool:
        if not self.open_jutsu(obs, attack["index"]):
            return False
        obs = self.observe()
        if not self.aim_to(obs, target_cell):
            self.record("aim-cursor-failed", cell=list(target_cell))
            self.press("B")
            return False
        obs = self.observe()
        self.press("A")
        obs = self.wait_for(
            lambda o: o["screen"] in ("message", "confirm", "error"), budget=900)
        if obs["screen"] == "error":
            self.record("target-rejected", cell=list(target_cell))
            self.press("B")
            return False
        self.shot("forecast")
        self.record("target-accepted", cell=list(target_cell),
                    attack=attack["name"])
        # forecast -> 可以嗎? -> resolution
        for _ in range(8):
            obs = self.observe()
            if obs["screen"] in ("message", "confirm"):
                self.press("A")
                continue
            if obs["screen"] == "error":
                self.press("B")
                continue
            break
        # the HP array lags the attack animation: wait for it to move
        for _ in range(30):
            obs = self.observe()
            live = {unit["slot"]: unit for unit in obs["units"]}
            if live.get(target_slot, {}).get("hp", 0) <= 0:
                break
            self.run(30)
        self.hits += 1
        return True

    def end_action(self, obs) -> None:
        if obs["screen"] == "action5":
            self.action(obs, (4, 3, 2, 1, 0), ("none", "message", "confirm"))
        else:
            self.menu_top(obs)
            self.press("Down", settle=12)
            self.press("A")
        for _ in range(6):
            obs = self.observe()
            if obs["screen"] in ("action5", "action2", "none"):
                return
            if obs["screen"] in ("message", "confirm"):
                self.press("A")
                continue
            if obs["screen"] == "error":
                self.press("B")
                continue
            return

    def rest(self, obs) -> None:
        if obs["screen"] != "action5":
            return
        self.action(obs, (3, 2, 4, 1, 0), ("none", "message", "confirm"))
        for _ in range(6):
            obs = self.observe()
            if obs["screen"] in ("action5", "action2", "none"):
                return
            if obs["screen"] in ("message", "confirm"):
                self.press("A")
                continue
            if obs["screen"] == "error":
                self.press("B")
                continue
            return

    # ----------------------------------------------------------------- act
    def act(self, obs) -> None:
        unit = self.acting_ally(obs)
        if unit is None:
            for entry in obs["units"]:
                if (entry["side"] == 0 and entry["hp"] > 0
                        and entry["char_id"] != 0
                        and entry["slot"] not in self.acted):
                    unit = entry
                    break
        if unit is None:
            return
        # A new player phase starts after the enemy phase, and the enemies
        # only move between phases -- their cells are therefore the phase
        # clock (there is no readable turn counter).
        cells = {entry["slot"]: tuple(entry["cell"])
                 for entry in self.live_enemies(obs)}
        moved = [slot for slot, cell in self.enemy_cells.items()
                 if slot in cells and cells[slot] != cell]
        if moved:
            # the enemies only move between player phases
            self.acted = set()
            self.record("new-player-phase", moved=moved)
        self.enemy_cells = cells
        if unit["slot"] in self.acted:
            return
        self.acted.add(unit["slot"])
        self.current_slot = unit["slot"]
        self.actions += 1
        options = [attack for attack in ATTACKS.get(unit["slot"], [])
                   if (unit["slot"], attack["index"]) not in self.no_tool]
        self.record("acting", slot=unit["slot"], cell=unit["cell"],
                    hp=unit["hp"], chakra=unit["chakra"],
                    tools=unit["tools"], screen=obs["screen"])
        if not options:
            obs = self.observe()
            if obs["screen"] in ("action5", "action2"):
                self.end_action(obs)
            return
        origin = tuple(unit["cell"])
        occupied = {(entry["cell"][0], entry["cell"][1]) for entry in obs["units"]
                    if entry["char_id"] != 0}
        enemies = self.live_enemies(obs)
        candidates = []
        for attack in options:
            if attack["chakra"] > unit["chakra"]:
                continue
            for cell in [origin] + self.reachable(origin, occupied):
                for enemy in enemies:
                    if not self.in_line(cell, tuple(enemy["cell"]), attack["range"]):
                        continue
                    kills = attack["damage"] >= enemy["hp"]
                    score = (0 if kills else 1, -min(attack["damage"], enemy["hp"]),
                             manhattan(origin, cell), enemy["slot"])
                    candidates.append((score, attack, cell, enemy))
        candidates.sort(key=lambda item: item[0])
        # A unit whose only strong attack costs chakra has to bank chakra
        # first (measured: Sasuke starts battle 14 with 0 chakra, the fire
        # costs 2 and the punch only does 10).
        can_kill = any(item[0][0] == 0 for item in candidates)
        self.record("candidates", n=len(candidates),
                    enemies=[[e["slot"], e["cell"], e["hp"]] for e in enemies],
                    options=[a["name"] for a in options],
                    chakra=unit["chakra"], origin=list(origin))
        for _, attack, cell, enemy in candidates:
            if (unit["slot"], attack["index"]) in self.no_tool:
                continue
            if attack["chakra"] > unit["chakra"]:
                continue
            if cell in self.blocked_cells:
                continue
            if cell != origin:
                self.record("plan-move", to=list(cell),
                            target=list(enemy["cell"]))
                if not self.do_move(obs, cell):
                    self.blocked_cells.add(cell)
                    continue
                obs = self.observe()
            if self.try_attack(obs, unit, attack, tuple(enemy["cell"]),
                               enemy["slot"]):
                return
            obs = self.observe()
            if obs["screen"] not in ("action5", "action2"):
                return
        # nothing worked: rest when the attack needs chakra we do not have
        obs = self.observe()
        need = min((attack["chakra"] for attack in options), default=0)
        if obs["screen"] in ("action5", "action2"):
            if unit["chakra"] < need:
                self.rest(obs)
            else:
                self.end_action(obs)

    # ---------------------------------------------------------------- play
    def play(self, max_turns: int = 40) -> dict:
        stats = {"turns": 0, "actions": 0, "hits": 0, "victory": False}
        idle = 0
        while stats["turns"] < max_turns:
            obs = self.observe()
            if obs["result"] == 1:
                stats["victory"] = True
                self.record("victory")
                if self.record_victory_only:
                    self.probe.run(f"script {self.lua_script}")
                # The 「勝利」 screen does **not** advance on its own: it waits
                # for an A press (measured: 18000 recorded frames stayed on
                # the victory screen).  The settlement screen comes after
                # that press.
                self.run(self.endgame_frames)
                for _ in range(self.endgame_presses):
                    self.press("A", settle=self.endgame_settle)
                    self.run(self.endgame_settle)
                break
            if obs["result"] == 2:
                self.record("defeat")
                break
            before = [unit["hp"] for unit in obs["units"]]
            screen = obs["screen"]
            if screen in ("action5", "action2"):
                acting = [unit for unit in obs["units"]
                          if unit["side"] == 0 and unit["acting"]]
                if acting and acting[0]["slot"] in self.acted:
                    # the same unit acts again -> a new player phase
                    self.acted = set()
                    self.record("new-player-phase")
                stats["turns"] += 1
                self.act(obs)
                after = [unit["hp"] for unit in self.observe()["units"]]
                if after != before:
                    stats["hits"] += 1
                idle = 0
                continue
            if screen in ("message", "confirm"):
                self.press("A", settle=90)
                idle = 0
                continue
            if screen == "error":
                self.press("B", settle=90)
                idle = 0
                continue
            if screen in ("jutsu", "info", "aim", "move"):
                self.press("B", settle=90)
                idle = 0
                continue
            idle += 1
            target = self.acting_ally(obs)
            if target is None:
                for entry in obs["units"]:
                    if (entry["side"] == 0 and entry["hp"] > 0
                            and entry["char_id"] != 0
                            and entry["slot"] not in self.acted):
                        target = entry
                        break
            if target is not None:
                self.walk_cursor(obs, (target["cell"][0], target["cell"][1]))
            self.press("A", settle=90)
            self.record("select-unit", idle=idle)
            if idle > 40:
                self.record("stuck", screen=screen)
                break
        stats["actions"] = self.actions
        stats["hits"] = self.hits
        return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    parser.add_argument("--exe", type=pathlib.Path, default=DEFAULT_EXE)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-victory-capture" / "w4" / "play")
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--endgame-frames", type=int, default=1800,
                        help="frames to keep recording after the victory")
    parser.add_argument("--no-frames", action="store_true",
                        help="do not record the frames (debug runs)")
    parser.add_argument("--endgame-presses", type=int, default=24,
                        help="how many A presses after the victory (the "
                             "victory screen waits for input)")
    parser.add_argument("--endgame-settle", type=int, default=240)
    parser.add_argument("--record-victory-only", action="store_true",
                        help="start the frame recorder only when the victory "
                             "is detected (much faster: the battle frames are "
                             "not written)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    walkable = load_walkable()
    stats = {"turns": 0, "actions": 0, "hits": 0, "victory": False}
    error = None
    player = None
    frames: list = []
    frames_dir = args.out / "frames"
    environment = {
        "MGBA_W4_OUTPUT_DIR": str(frames_dir),
        "MGBA_W4_KEY_SEQUENCE": "",
        "MGBA_W4_ZERO_FRAMES": "0",
        "MGBA_W4_HOLD_FRAMES": "4",
        "MGBA_W4_SETTLE_FRAMES": "90",
        "MGBA_W4_CAPTURE": "all",
        "MGBA_W4_INPUT_STATE": "",
        "MGBA_W4_STATE_FILE": str(args.out / "state.csv"),
    }
    # the Lua script runs inside the probe process and reads its
    # configuration from the process environment, so the environment has to
    # be set **before** the probe is started.
    previous = {name: os.environ.get(name) for name in environment}
    if not args.no_frames:
        frames_dir.mkdir(parents=True, exist_ok=True)
        os.environ.update(environment)
    try:
        with probe_module.Probe(args.rom, exe=args.exe) as probe:
            probe.load(args.state)
            probe.frames(30, 0)
            if not args.no_frames and not args.record_victory_only:
                probe.run(f"script {LUA_SCRIPT}")
            player = Player(probe, args.out, walkable, verbose=args.verbose,
                            endgame_frames=args.endgame_frames,
                            record_victory_only=args.record_victory_only,
                            lua_script=LUA_SCRIPT,
                            endgame_presses=args.endgame_presses,
                            endgame_settle=args.endgame_settle)
            stats = player.play(max_turns=args.max_turns)
    except Exception as failure:
        error = f"{type(failure).__name__}: {failure}"
        print(f"!! {error}", file=sys.stderr)
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    receipt = {
        "schema": "konoha.s49-victory-play-w4.v1",
        "rom": str(args.rom),
        "rom_sha256": s49_state.file_sha256(args.rom),
        "state": str(args.state),
        "state_sha256": s49_state.file_sha256(args.state),
        "stats": stats,
        "error": error,
        "frames_captured": len(frames),
        "frames_manifest": str(args.out / "frames.sha256") if frames else None,
        "log": player.log if player else [],
    }
    frames = sorted((args.out / "frames").glob("frame-*.png"))
    if frames:
        lines = []
        for path in frames:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.name}")
        (args.out / "frames.sha256").write_text("\n".join(lines) + "\n",
                                                encoding="utf-8", newline="\n")
    (args.out / "play.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({"stats": stats, "error": error}, ensure_ascii=False))
    return 0 if stats["victory"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
