#!/usr/bin/env python3
"""Play the original S49 battle 14 (Konohamaru vs the bees) to a decision.

This is stream W3's driver.  It supersedes ``play_battle_v2.py`` (stream M),
which lost its state machine after the second unit's move.

What changed and why
--------------------
* **The frame lag was never real.**  Experiment W3-E1 measured that only
  ``frames``/``run``/``framedump``/``keyseq`` advance the emulated game;
  ``dump``/``shot``/``rawshot`` do not.  A register read and a screenshot
  taken back to back therefore describe the *same* frame.  The driver reads
  the picture with ``rawshot`` (lossless and fast) and the registers right
  after it.
* **The classifier was the real bug.**  Stream M's menu classifier could not
  tell the compact menu from the jutsu list.  Every threshold used here was
  measured on this machine with ``calibrate_menus.py``:

  ==================  =====  ======  =====  =====  =====  =====
  screen              level  border  dark   panel  dlg    err/cfm
  ==================  =====  ======  =====  =====  =====  =====
  action5 (5 items)   3      94     631    0      74     371/0
  action2 (2 items)   3      42     304    0      0      138/0
  jutsu list          4      8      953    5170   3476   5676/1211
  aim / move cursor   3/4    0..2   0      0      0      0/0
  forecast box        4      2      0      246    2207   0/0
  「可以嗎？」        4      2      0      246    2207   2145/2283
  ==================  =====  ======  =====  =====  =====  =====

* **Every key press is logged**, so the whole run can be replayed frame
  exactly (that is how the black field phases were measured).

Usage::

    python tools/s49_victory_capture/play_battle_v3.py \
        --out build/s49-victory-capture/v3run
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import battle_obs  # noqa: E402
import probe as probe_module  # noqa: E402
import s49_state  # noqa: E402

REPO = HERE.parents[1]
DEFAULT_EXE = REPO / "build" / "mgba-probe-w3" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")
MAP_TRUTH = REPO / "tools" / "s49_orig_map" / "battle-14-map-truth.json"

MOVE_RANGE = 3           # Manhattan radius (measured, stream M)
SHURIKEN_RANGE = 3       # straight line range
BEE_SLOTS = (5, 6, 7, 8, 9)
GRID_W = 15
GRID_H = 19

# The jutsu lists are **character specific**.  The entries below were read
# off the original's own jutsu list screen (the crops are kept in
# build/s49-victory-capture/v3run13/debug/):
#
#   slot 1 漩涡鸣人  查克拉 138 忍具 5
#          变身术 / 影分身术 / 忍者组合拳 / **十字手里剑** (6x3, 距离 3 直, 90%)
#   slot 2 宁智波佐助 查克拉 104 忍具 4
#          **火遁术** (15x1, 距离 2 直, 95%) / 影分身术 / 忍者组合拳
#   slot 3 春野樱    查克拉 110 忍具 3
#          影分身术 / 分身术 / 忍者组合拳   (no ranged attack)
#
# ``index`` is the position of the attack in that character's list and
# ``range`` the 距離 the list itself shows.
ATTACKS = {
    1: {"index": 3, "range": 3, "name": "十字手里剑"},
    2: {"index": 0, "range": 2, "name": "火遁术"},
}


def load_walkable() -> set:
    """The walkable battle cells of map 14 (read only, from stream M)."""
    document = json.loads(MAP_TRUTH.read_text(encoding="utf-8"))
    grid = document["collision_grid"]
    cells = set()
    for index, value in enumerate(grid):
        if value in (0, 3):          # plain and ground_patch are walkable
            cells.add((index % GRID_W, index // GRID_W))
    return cells


def manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def aligned(origin, target) -> bool:
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    if dx != 0 and dy != 0:
        return False
    distance = abs(dx) + abs(dy)
    return 1 <= distance <= SHURIKEN_RANGE


class Driver:
    """The battle driver."""

    def __init__(self, observer: battle_obs.BattleObserver, log: list,
                 walkable: set, *, debug_dir: pathlib.Path | None = None,
                 verbose: bool = False,
                 log_path: pathlib.Path | None = None) -> None:
        self.observer = observer
        self.log = log
        self.walkable = walkable
        self.debug_dir = debug_dir
        self.verbose = verbose
        self.log_path = log_path
        self.key_log: list[dict] = []
        self.shots = 0
        self.switches = 0
        self.cancels = 0
        self.acted_slots: set[int] = set()

    # ------------------------------------------------------------- logging
    def record(self, event: str, **extra) -> None:
        row = {"event": event}
        row.update(extra)
        self.log.append(row)
        if self.log_path is not None:
            # the run can stall; the log has to be readable while it runs
            with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        if self.verbose:
            print(f"    {event}: " + json.dumps(extra, ensure_ascii=False),
                  file=sys.stderr, flush=True)

    def press(self, key: str, settle: int = 60, hold: int = 4,
              release: int = 1, tag: str = "") -> None:
        self.observer.press(key, settle=settle, hold=hold, release=release)
        self.key_log.append({"key": key, "settle": settle, "hold": hold,
                             "release": release, "tag": tag})
        self.record("key", k=key, settle=settle, tag=tag)

    def run(self, frames: int) -> None:
        self.observer.run(frames)

    def observe(self) -> battle_obs.Observation:
        return self.observer.observe()

    def shot(self, label: str) -> str | None:
        if self.debug_dir is None:
            return None
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.shots += 1
        path = self.debug_dir / f"{self.shots:04d}-{label}.png"
        self.observer.probe.shot(path)
        return str(path)

    def crop(self, label: str, region, suffix: str) -> str | None:
        """Save a region of the current frame (used to read the jutsu names)."""
        if self.debug_dir is None:
            return None
        from PIL import Image
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.shots += 1
        path = self.debug_dir / f"{self.shots:04d}-{label}-{suffix}.png"
        observation = self.observe()
        nearest = getattr(Image, "Resampling", Image).NEAREST
        size = ((region[2] - region[0]) * 3, (region[3] - region[1]) * 3)
        observation.image.crop(region).resize(size, nearest).save(path)
        return str(path)

    # -------------------------------------------------------------- helpers
    def error_box(self, observation) -> bool:
        sig = observation.sig
        return 1000 < sig["error_light"] < 3000 and sig["confirm_light"] < 500

    def confirm_dialog(self, observation) -> bool:
        return observation.sig["confirm_light"] > 1000

    def forecast(self, observation) -> bool:
        sig = observation.sig
        return 1000 < sig["dialogue_light"] < 3000 and sig["error_light"] < 1000

    def waits_for_a(self, observation) -> bool:
        """True when the screen is a box that an A press advances.

        The rule is deliberately conservative, because a blind A press on a
        *jutsu list* picks the highlighted jutsu (stream W3's first runs lost
        the action that way).  So:

        * a screen with a light info panel is never A pressed (that is the
          jutsu UI, and the fire style's target screen),
        * an open menu is never A pressed,
        * the game's own error box wants a B, not an A.
        """
        sig = observation.sig
        if sig["panel_light"] > 3000:
            return False
        if observation.menu in ("action5", "action2", "move"):
            return False
        if self.error_box(observation):
            return False
        if sig["confirm_light"] > 1000:
            return True
        if sig["dialogue_light"] > 1000:
            return True
        return False

    def wait_for(self, predicate, budget: int = 1200, step: int = 30,
                 press_a_on_dialogue: bool = True):
        """Run frames until ``predicate(observation)`` holds."""
        waited = 0
        previous = None
        while waited < budget:
            observation = self.observe()
            if predicate(observation):
                return observation
            signature = json.dumps(observation.sig, sort_keys=True)
            stable = signature == previous
            previous = signature
            if press_a_on_dialogue and stable and self.waits_for_a(observation):
                self.press("A", settle=90, tag="wait-dialogue")
                waited += 90
                continue
            self.run(step)
            waited += step
        return self.observe()

    def wait_menu(self, budget: int = 1200):
        return self.wait_for(
            lambda observation: observation.menu in ("action5", "action2", "jutsu"),
            budget=budget)

    def wait_state(self, name: str, budget: int = 600):
        """Wait for one named screen (the game animates the menus in)."""
        return self.wait_for(lambda observation: observation.menu == name,
                              budget=budget)

    # --------------------------------------------------------------- battle
    def acting_unit(self, observation):
        unit = observation.acting_ally()
        if unit is not None:
            return unit
        for entry in observation.allies():
            if entry["hp"] > 0:
                return entry
        return None

    def plan(self, observation, unit, attack_range):
        """Pick the target bee and the cell to shoot it from.

        Returns ``(bee, cell, needs_move)``.  ``bee`` is ``None`` when no bee
        can be reached at all.  When no bee is in attack range the unit still
        has to walk towards the closest one, so ``needs_move`` can be true
        with ``bee`` set to the nearest bee.
        """
        origin = (unit["x"], unit["y"])
        occupied = {(entry["x"], entry["y"]) for entry in observation.units
                    if entry["hp"] > 0}
        bees = sorted(observation.bees(), key=lambda entry: (entry["hp"], entry["slot"]))
        best = None
        for bee in bees:
            target = (bee["x"], bee["y"])
            # shoot from where the unit stands
            if self.in_range(origin, target, attack_range):
                score = (0, manhattan(origin, target), bee["hp"], bee["slot"])
                if best is None or score < best[0]:
                    best = (score, bee, origin)
                continue
            # shoot from a cell that is within the move range
            for candidate in self.reachable(origin, occupied):
                if self.in_range(candidate, target, attack_range):
                    score = (1, manhattan(candidate, target),
                             manhattan(origin, candidate), bee["hp"], bee["slot"])
                    if best is None or score < best[0]:
                        best = (score, bee, candidate)
                    break
        if best is None:
            # nothing is in range: walk towards the closest bee.  A cell
            # only counts as an approach when the attack can be launched from
            # it, so the walk does not end one step short of the target.
            for bee in bees:
                target = (bee["x"], bee["y"])
                for candidate in self.reachable(origin, occupied):
                    usable = 0 if self.in_range(candidate, target, attack_range) else 1
                    straight = 0 if (candidate[0] == target[0]
                                     or candidate[1] == target[1]) else 1
                    score = (2, usable, straight, manhattan(candidate, target),
                             manhattan(origin, candidate), bee["hp"], bee["slot"])
                    if best is None or score < best[0]:
                        best = (score, bee, candidate)
        if best is None:
            return None, None, False
        return best[1], best[2], best[0][0] in (1, 2)

    @staticmethod
    def in_range(origin, target, attack_range) -> bool:
        """True when ``target`` is on a straight line within ``attack_range``."""
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        if dx != 0 and dy != 0:
            return False
        distance = abs(dx) + abs(dy)
        return 1 <= distance <= attack_range

    def reachable(self, origin, occupied):
        """The cells the unit may walk to (Manhattan radius 3, walkable)."""
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

    # ----------------------------------------------------------------- move
    def do_move(self, observation, unit, cell) -> bool:
        """移動 -> walk the cursor -> confirm.  True when the unit moved."""
        if observation.menu != "action5":
            return False
        self.observer.select_menu_item(observation, battle_obs.MENU_ITEM_MOVE)
        self.press("A", settle=60, tag="open-move")
        observation = self.observe()
        if observation.menu not in ("move", "aim", "none"):
            # the move phase did not open
            self.record("move-not-open", menu=observation.menu,
                        level=observation.level)
            return False
        self.observer.move_cursor_to(observation, cell)
        observation = self.observe()
        self.record("move-target", want=list(cell),
                    cursor=list(observation.cursor[:2]))
        self.press("A", settle=60, tag="move-confirm")
        after = self.wait_for(
            lambda obs: obs.menu in ("action2", "action5", "dialogue"),
            budget=1200)
        position = after.position(unit["slot"])
        moved = position is not None and position != (unit["x"], unit["y"])
        self.record("move-result", moved=moved,
                    to=list(position) if position else None,
                    menu=after.menu, sig=after.sig, level=after.level)
        return moved

    # ---------------------------------------------------------------- shoot
    def open_jutsu(self, observation) -> bool:
        """Open the jutsu list from the action menu or the compact menu.

        Every transition waits for the expected screen: the game animates the
        menus in, so the frame right after the A press can show *no* menu at
        all (stream M lost its state machine exactly there).

        The jutsu UI is recognised by its light info panel; the *level*
        register is not a reliable discriminator (the same list reads level 4
        in one turn and level 3 in the next), so both the list and the fire
        style's target screen count as "the jutsu UI is open".
        """
        for _ in range(8):
            observation = self.observe()
            if observation.menu in ("jutsu", "target"):
                return True
            if observation.menu == "action5":
                self.observer.select_menu_item(observation, battle_obs.MENU_ITEM_JUTSU)
                self.press("A", settle=60, tag="open-jutsu")
                self.wait_for(lambda obs: obs.menu in ("jutsu", "target"),
                              budget=600, press_a_on_dialogue=False)
                continue
            if observation.menu == "action2":
                # the compact menu's first entry is 「術·忍具」
                self.press("A", settle=60, tag="open-jutsu-compact")
                self.wait_for(lambda obs: obs.menu in ("jutsu", "target"),
                              budget=600, press_a_on_dialogue=False)
                continue
            if observation.menu == "dialogue":
                self.press("A", settle=90, tag="dialogue")
                continue
            self.record("jutsu-state", menu=observation.menu,
                        level=observation.level, sig=observation.sig)
            self.shot("jutsu-fail")
            return False
        return self.observe().menu in ("jutsu", "target")

    def panel_hash(self, observation) -> str:
        """Hash of the jutsu list's info panel (the jutsu identity)."""
        import hashlib
        panel = observation.image.crop(battle_obs.INFO_PANEL)
        return hashlib.sha256(panel.tobytes()).hexdigest()[:16]

    def do_attack(self, observation, unit, bee, attack) -> bool:
        """Fire the character's attack at ``bee``.  True when the HP dropped."""
        if not self.open_jutsu(observation):
            self.record("jutsu-not-open", menu=self.observe().menu)
            return False
        index = attack["index"]
        self.crop("jutsu-list", (0, 0, 240, 160), f"slot{unit['slot']}")
        if not self.observer.select_menu_item(self.observe(), index):
            self.record("jutsu-index-missing", slot=unit["slot"], index=index)
            self.leave_jutsu()
            return False
        self.press("A", settle=60, tag="pick-jutsu")
        self.shot("aim-mode")
        # 火遁术 opens a confirm box before its target screen, so the driver
        # has to walk the screen until the target cursor is really there
        for _ in range(8):
            observation = self.observe()
            sig = observation.sig
            if observation.menu == "aim":
                break
            if observation.menu in ("jutsu", "target"):
                # the entry is already highlighted: A picks it (the fire
                # style asks one more question before its target screen)
                self.press("A", settle=60, tag="pick-jutsu-again")
                continue
            if sig["confirm_light"] > 1000 or 1000 < sig["dialogue_light"] < 3000:
                self.press("A", settle=60, tag="confirm-jutsu")
                continue
            self.run(30)
        observation = self.observe()
        self.record("aim", menu=observation.menu, level=observation.level,
                    cursor=list(observation.cursor[:2]),
                    target=[bee["x"], bee["y"]], index=index,
                    sig=observation.sig)
        self.observer.move_cursor_to(observation, (bee["x"], bee["y"]))
        observation = self.observe()
        self.record("aim-cursor", cursor=list(observation.cursor[:2]),
                    want=[bee["x"], bee["y"]])
        before = observation.hp(bee["slot"])
        self.press("A", settle=60, tag="fire")
        # the forecast, the 「可以嗎？」 dialog and the resolution.  During the
        # attack animation the driver must **not** press A: the press would
        # be consumed by the action menu that comes back and would open the
        # move phase (stream W3's earlier runs lost the action that way).
        for _ in range(16):
            observation = self.observe()
            if self.confirm_dialog(observation):
                self.press("A", settle=60, tag="confirm")
                continue
            if self.forecast(observation):
                self.press("A", settle=60, tag="forecast")
                continue
            if self.error_box(observation):
                self.record("shot-refused", box=observation.sig)
                self.press("B", settle=60, tag="dismiss")
                continue
            after = observation.hp(bee["slot"])
            if after != before:
                self.record("attacked", slot=bee["slot"], hp=after,
                            before=before)
                self.shot("after-shot")
                return True
            if observation.menu in ("action5", "action2", "jutsu", "target"):
                break
            self.run(30)
        after = self.observe().hp(bee["slot"])
        self.record("shot-missed", slot=bee["slot"], hp=after, before=before)
        return after != before

    def leave_jutsu(self) -> None:
        """Back out of the jutsu UI until the action menu is back."""
        for _ in range(5):
            observation = self.observe()
            if observation.menu in ("jutsu", "target"):
                self.press("B", settle=60, tag="leave-jutsu")
                continue
            if observation.menu == "aim":
                self.press("B", settle=60, tag="leave-aim")
                continue
            return

    def unit_at_cursor(self, observation):
        """The unit the cell cursor is standing on."""
        cell = (observation.cursor[0], observation.cursor[1])
        for entry in observation.units:
            if (entry["x"], entry["y"]) == cell:
                return entry
        return None

    def idle_ally(self, observation):
        """An ally that has not acted yet this player phase."""
        for entry in observation.units:
            if entry["side"] != 0 or entry["hp"] <= 0:
                continue
            if entry["slot"] in self.acted_slots:
                continue
            return entry
        return None

    # ----------------------------------------------------------------- act
    def end_action(self, observation) -> None:
        """行動終了 -> confirm."""
        index = battle_obs.MENU_ITEM_END if observation.menu == "action5" else 1
        self.observer.select_menu_item(observation, index)
        self.press("A", settle=60, tag="pick-end")
        for _ in range(6):
            observation = self.observe()
            if self.confirm_dialog(observation):
                self.press("A", settle=60, tag="confirm-end")
                self.wait_menu(budget=600)
                return
            if observation.menu in ("action5", "action2"):
                return
            self.press("A", settle=90, tag="advance-end")

    def act(self, observation) -> None:
        unit = self.acting_unit(observation)
        if unit is None:
            return
        bees = observation.bees()
        if unit["slot"] in self.acted_slots:
            # the same unit acts again -> a new player phase started
            self.acted_slots = set()
        self.acted_slots.add(unit["slot"])
        self.record("acting", slot=unit["slot"], position=[unit["x"], unit["y"]],
                    menu=observation.menu, bees=len(bees),
                    bee_cells=[[bee["x"], bee["y"], bee["hp"], bee["slot"]]
                               for bee in bees])
        if not bees:
            return
        attack = ATTACKS.get(unit["slot"])
        if attack is None:
            self.record("no-attack", slot=unit["slot"])
            observation = self.observe()
            if observation.menu in ("action5", "action2"):
                self.end_action(observation)
            self.record("action-done", slot=unit["slot"],
                        menu=self.observe().menu)
            return
        bee, cell, needs_move = self.plan(observation, unit, attack["range"])
        if bee is None:
            self.record("no-target", slot=unit["slot"])
            observation = self.observe()
            if observation.menu in ("action5", "action2"):
                self.end_action(observation)
            self.record("action-done", slot=unit["slot"],
                        menu=self.observe().menu)
            return
        if needs_move and observation.menu == "action5":
            moved = self.do_move(observation, unit, cell)
            observation = self.observe()
            self.record("post-move", menu=observation.menu,
                        level=observation.level, sig=observation.sig)
            if moved:
                self.shot("after-move")
            # the planner has to work with the unit's **new** cell, otherwise
            # it keeps asking for another move (stream W3's first runs never
            # attacked because of this)
            position = observation.position(unit["slot"])
            if position is not None:
                unit = dict(unit)
                unit["x"], unit["y"] = position
                self.record("unit-moved", slot=unit["slot"], to=list(position))
        # attack as long as the action menu is up and a target is in range
        for _ in range(6):
            observation = self.observe()
            if observation.menu not in ("action5", "action2"):
                # after an attack the unit's action is over: the game goes
                # back to the unit selection phase, not to a menu
                observation = self.wait_menu(budget=300)
            if observation.menu not in ("action5", "action2"):
                break
            bee, cell, needs_move = self.plan(observation, unit, attack["range"])
            if bee is None or needs_move:
                break
            if not self.do_attack(observation, unit, bee, attack):
                break
        observation = self.wait_menu(budget=1200)
        if observation.menu in ("action5", "action2"):
            self.end_action(observation)
        self.record("action-done", slot=unit["slot"], menu=self.observe().menu)

    # ---------------------------------------------------------------- play
    def play(self, max_turns: int = 40) -> dict:
        stats = {"turns": 0, "actions": 0, "hits": 0, "victory": False}
        self.record("start", hp=[unit["hp"] for unit in self.observe().units])
        idle = 0
        while stats["turns"] < max_turns:
            observation = self.observe()
            if not observation.bees():
                stats["victory"] = True
                self.record("victory")
                break
            if observation.menu in ("action5", "action2"):
                stats["turns"] += 1
                stats["actions"] += 1
                before = observation.hp_list()
                self.act(observation)
                if self.observe().hp_list() != before:
                    stats["hits"] += 1
                idle = 0
                continue
            if observation.menu == "jutsu":
                self.leave_jutsu()
                continue
            if observation.menu in ("target", "aim"):
                # a jutsu UI or an aim mode that the driver did not open:
                # B walks out of it
                self.press("B", settle=90, tag="back-out")
                self.record("back-out", menu=observation.menu)
                idle = 0
                continue
            if observation.menu == "dialogue":
                self.press("A", settle=90, tag="dialogue")
                self.record("dialogue", level=observation.level)
                idle = 0
                continue
            if self.confirm_dialog(observation):
                self.press("A", settle=90, tag="confirm")
                self.record("confirm", level=observation.level)
                idle = 0
                continue
            if self.error_box(observation):
                cursor_unit = self.unit_at_cursor(observation)
                if cursor_unit is not None and cursor_unit["slot"] in self.acted_slots:
                    # the unit under the cursor already acted: walk the cursor
                    # to an ally that has not acted yet and select it
                    target = self.idle_ally(observation)
                    if target is not None:
                        self.observer.move_cursor_to(observation,
                                                     (target["x"], target["y"]))
                        observation = self.observe()
                        self.record("switch-unit", to=[target["x"], target["y"]],
                                    slot=target["slot"])
                        self.press("A", settle=90, tag="select-unit")
                        idle = 0
                        continue
                self.press("B", settle=90, tag="dismiss")
                self.record("error-box", level=observation.level)
                idle = 0
                continue
            if observation.menu == "move":
                # the move phase of an action the driver did not start.
                # B cancels it; when B does not get through, A confirms the
                # move where the cursor is (the unit stays where it is).
                self.cancels += 1
                if self.cancels > 3:
                    self.press("A", settle=90, tag="confirm-move")
                    self.cancels = 0
                else:
                    self.press("B", settle=90, tag="cancel-move")
                self.record("cancel-move", level=observation.level,
                            cancels=self.cancels)
                idle = 0
                continue
            # the unit selection phase: put the cursor on an ally that has
            # not acted yet and select it
            idle += 1
            cursor_unit = self.unit_at_cursor(observation)
            if cursor_unit is not None and cursor_unit["slot"] in self.acted_slots:
                target = self.idle_ally(observation)
                if target is not None:
                    self.observer.move_cursor_to(observation,
                                                 (target["x"], target["y"]))
                    observation = self.observe()
                    self.record("switch-unit", to=[target["x"], target["y"]],
                                slot=target["slot"])
            self.press("A", settle=90, tag="select-unit")
            self.record("select-unit", level=observation.level, idle=idle,
                        cursor=list(observation.cursor[:2]))
            if idle > 60:
                self.record("stuck", menu=observation.menu)
                break
        self.record("end", stats=stats)
        return stats


def capture_endgame(observer: battle_obs.BattleObserver, out_dir: pathlib.Path,
                     frames: int = 900) -> list[str]:
    """Grab the victory performance and the settlement screen, frame by frame."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(frames):
        observer.probe.frames(1, 0)
        path = out_dir / f"end-{index:05d}.png"
        observer.probe.shot(path)
        paths.append(str(path))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--endgame-frames", type=int, default=900)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--verbose", action="store_true",
                        help="print every decision to stderr while the run goes on")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    log: list = []
    stats = {"turns": 0, "actions": 0, "hits": 0, "victory": False}
    final_hp: list = []
    final_units: list = []
    endgame: list[str] = []
    key_log: list = []
    error = None
    walkable = load_walkable()

    for attempt in range(4):
        try:
            with probe_module.Probe(args.rom, exe=args.exe) as probe:
                probe.load(args.state)
                observer = battle_obs.BattleObserver(probe,
                                                     raw_path=out_dir / "frame.raw")
                driver = Driver(observer, log, walkable,
                                debug_dir=(out_dir / "debug") if args.debug else None,
                                verbose=args.verbose,
                                log_path=out_dir / "progress.jsonl")
                stats = driver.play(max_turns=args.max_turns)
                final_hp = observer.observe().hp_list()
                final_units = observer.observe().units
                key_log = driver.key_log
                if stats["victory"]:
                    endgame = capture_endgame(observer, out_dir / "endgame",
                                              frames=args.endgame_frames)
            error = None
            break
        except Exception as failure:      # keep the log even when the probe dies
            error = f"{type(failure).__name__}: {failure}"
            log.append({"event": "error", "attempt": attempt, "message": error})
            print(f"!! attempt {attempt} failed: {error}", file=sys.stderr)
            break

    receipt = {
        "schema": "konoha.s49-victory-play-v3.v1",
        "rom": args.rom,
        "rom_sha256": s49_state.file_sha256(args.rom),
        "start_state": args.state,
        "start_state_sha256": s49_state.file_sha256(args.state),
        "stats": stats,
        "final_hp": final_hp,
        "final_units": final_units,
        "endgame_frames": [pathlib.Path(path).name for path in endgame],
        "key_log": key_log,
        "error": error,
        "log": log,
    }
    (out_dir / "play.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({"stats": stats, "hp": final_hp, "error": error},
                     ensure_ascii=False))
    return 0 if stats["victory"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
