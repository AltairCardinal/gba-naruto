#!/usr/bin/env python3
"""Y1 (wave 13): the adaptive closed-loop battle driver for the remake ROM.

Why an adaptive driver
----------------------
``x1_play.py`` replays U2's **offline** route step by step.  The route was
computed by ``u2_route_gen.cpp`` with the *same* controller the ROM runs, so
the phase sequence lines up -- but the route hard-codes *which* action is
picked (``Down`` x N, then ``A``).  On the ROM the highlighted action can be
unusable (the battle scene reports ``action_selection_error`` for it), the
press is rejected with an "insufficient chakra" message and the driver walks
into the wrong phase.

So this driver keeps the route for the decisions that the offline generator
computed (in particular **where the unit walks**), but it decides the two
choices that depend on the *live* battle state itself:

* ``action_selection`` -- walk the action list and pick the first entry whose
  ``selected_action_error`` is zero (the ROM's own verdict);
* ``target_selection`` -- put the cursor on a live enemy (the ROM's own
  ``unit_x`` / ``unit_y`` / ``unit_hp`` / ``unit_side`` telemetry).

The settlement chain is walked with the confirm button and every page is
photographed, so the capture is a **real runtime frame** of the product code.

Usage::

    python tools/s49_battle_balance/y1_play.py \\
        --rom build/y1/rom-current.gba \\
        --route build/s49-battle-balance/u2/routeY.json \\
        --out build/y1/run-current
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402

KEYS = dict(w1_boot.KEYS)

PHASE_PREPARATION = 0
PHASE_UNIT_SELECTION = 1
PHASE_MOVE_SELECTION = 2
PHASE_COMMAND_SELECTION = 3
PHASE_CHAKRA_SELECTION = 4
PHASE_REST_CONFIRMATION = 5
PHASE_ACTION_SELECTION = 6
PHASE_COMBINATION_DECISION = 7
PHASE_TARGET_SELECTION = 8
PHASE_FACING_SELECTION = 9
PHASE_DEFENSE_DECISION = 10
PHASE_DEFENSE_SELECTION = 11
PHASE_ENEMY_TURN = 12
PHASE_OUTCOME = 13
PHASE_RESULT = 14
PHASE_LEVEL_UP = 15
PHASE_COMPLETE = 16
PHASE_ERROR = 17
PHASE_SCRIPT_BLOCKED = 18
PHASE_TRAINING = 19
PHASE_TARGET_CONFIRMATION = 20
PHASE_END_CONFIRMATION = 21
PHASE_TARGET_PREVIEW = 22
PHASE_TURN_BANNER = 23
PHASE_POST_BATTLE_DIALOGUE = 24
PHASE_TASK_MENU = 25

SETTLEMENT_PHASES = (
    PHASE_OUTCOME, PHASE_RESULT, PHASE_LEVEL_UP, PHASE_TRAINING,
    PHASE_POST_BATTLE_DIALOGUE, PHASE_TASK_MENU)

# The order the player's own turn walks through.  A route step that waits for
# a phase the ROM has already walked past is not a failure: the route was
# generated offline and the ROM may skip a step (for example the combination
# decision, which only happens for a special combination).
TURN_FLOW_ORDER = (
    PHASE_UNIT_SELECTION, PHASE_MOVE_SELECTION, PHASE_COMMAND_SELECTION,
    PHASE_CHAKRA_SELECTION, PHASE_REST_CONFIRMATION, PHASE_ACTION_SELECTION,
    PHASE_COMBINATION_DECISION, PHASE_TARGET_SELECTION,
    PHASE_FACING_SELECTION, PHASE_DEFENSE_DECISION,
    PHASE_DEFENSE_SELECTION, PHASE_ENEMY_TURN)

SIDE_PLAYER = 0
SIDE_ENEMY = 1


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Driver:
    """Drives the remake ROM's battle with the ROM's own telemetry as oracle."""

    def __init__(self, probe: probe_module.Probe,
                 telemetry: x1_telemetry.Telemetry,
                 out: pathlib.Path,
                 verbose: bool = True,
                 prefer_action_index: int | None = None) -> None:
        self.probe = probe
        self.telemetry = telemetry
        self.out = out
        self.shots = out / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.frames = 0
        self.keys = 0
        self.trace: list[dict[str, object]] = []
        self.captures: list[dict[str, object]] = []
        self.errors: list[str] = []
        self.notes: list[str] = []
        self.shot_index = 0
        self.prefer_action_index = prefer_action_index

    # ------------------------------------------------------------- plumbing
    def log(self, text: str) -> None:
        if self.verbose:
            print(text, flush=True)

    def state(self) -> dict[str, int]:
        return self.telemetry.read()

    def wait(self, frames: int) -> None:
        if frames > 0:
            self.probe.run(f"frames {frames} 0x00000000")
            self.frames += frames

    def release_gap(self, frames: int = 1) -> None:
        """Render ``frames`` frames with **no** button held down.

        The battle scene latches a confirmation until it has seen the button
        released: ``battle_runtime_scene.cpp`` clears
        ``script_confirmation_latched`` only on a frame where A is **not**
        held, and the generic input path uses ``bn::keypad::a_pressed()``,
        which is an edge and needs a released frame to re-arm.

        The probe's ``frames <count> <mask>`` command releases the keys
        **after** the last frame it renders, so two presses in a row leave
        the scene without a single released frame in between and the second
        press is swallowed.  One released frame is enough, so the driver
        renders one before every press.
        """
        if frames > 0:
            self.probe.run(f"frames {frames} 0x00000000")
            self.frames += frames

    def press(self, key: str, hold: int = 4, settle: int = 0) -> None:
        if key not in KEYS:
            raise KeyError(key)
        self.release_gap(1)
        self.probe.run(f"frames {hold} 0x{KEYS[key]:08X}")
        self.frames += hold
        self.keys += 1
        if settle:
            self.wait(settle)

    def press_until(self, key: str, predicate, max_frames: int = 900,
                    poll: int = 4) -> bool:
        """Tap the key until the ROM accepts it.

        The key is **tapped** (pressed for a few frames, then released for a
        few), not held down.  A continuous hold confirms exactly one dialogue
        line and is then swallowed by the scene's latch (see
        ``release_gap``), so a hold stalls on the second line.
        """
        if key not in KEYS:
            raise KeyError(key)
        mask = KEYS[key]
        accepted = False
        deadline = self.frames + max_frames
        while self.frames < deadline:
            self.probe.run("frames 1 0x00000000")
            self.probe.run(f"frames 4 0x{mask:08X}")
            self.probe.run("frames 2 0x00000000")
            self.frames += 7
            if predicate(self.state()):
                accepted = True
                break
        self.keys += 1
        return accepted

    def shot(self, tag: str) -> pathlib.Path:
        self.shot_index += 1
        path = self.shots / f"shot-{self.shot_index:03d}-{tag}.png"
        self.probe.run(f"shot {path}")
        return path

    def wait_idle(self, timeout: int = 6000, poll: int = 8) -> bool:
        deadline = self.frames + timeout
        while self.frames < deadline:
            values = self.state()
            if (values["presentation_busy"] == 0 and
                    values["map_movement_active"] == 0):
                return True
            self.wait(poll)
        return False

    def wait_phase(self, want: int, timeout: int = 4000,
                   poll: int = 8, require_idle: bool = True
                   ) -> dict[str, int] | None:
        deadline = self.frames + timeout
        while self.frames < deadline:
            values = self.state()
            if (values["phase"] == want and
                    (not require_idle or
                     (values["presentation_busy"] == 0 and
                      values["map_movement_active"] == 0))):
                return values
            self.wait(poll)
        return None

    # --------------------------------------------------- adaptive decisions
    def live_enemies(self, values: dict[str, int]) -> list[tuple[int, int]]:
        points: list[tuple[int, int]] = []
        count = min(values["unit_count"], 12)
        for index in range(count):
            if values[f"unit_active[{index}]"] == 0:
                continue
            if values[f"unit_side[{index}]"] != SIDE_ENEMY:
                continue
            if values[f"unit_hp[{index}]"] <= 0:
                continue
            points.append((values[f"unit_x[{index}]"],
                           values[f"unit_y[{index}]"]))
        return points

    def select_usable_action(self) -> dict[str, int] | None:
        """Walk the action list and stop on the first entry the ROM accepts.

        The whole list is scanned (and logged) so that the receipt records
        which entries the ROM itself rejects.
        """
        values = self.state()
        count = max(1, values["action_count"])
        seen: list[dict[str, int]] = []
        chosen_index: int | None = None
        for step in range(count):
            values = self.state()
            entry = {
                "index": values["action_index"],
                "action_id": values["selected_action_id"],
                "kind": values["selected_action_kind"],
                "error": values["selected_action_error"],
            }
            seen.append(entry)
            self.log(f"    action[{entry['index']}] id={entry['action_id']} "
                     f"kind={entry['kind']} error={entry['error']}")
            if entry["error"] == 0 and chosen_index is None:
                chosen_index = entry["index"]
            if step + 1 < count:
                self.press("Down", 2)
                self.wait(10)
        if chosen_index is None:
            self.trace.append({"do": "action-scan", "entries": seen,
                               "chosen": None})
            return None
        # The scan walked the whole list; walk back to the chosen entry.
        values = self.state()
        steps = (chosen_index - values["action_index"]) % count
        for _ in range(steps):
            self.press("Down", 2)
            self.wait(10)
        values = self.state()
        self.trace.append({"do": "action-scan", "entries": seen,
                           "chosen": chosen_index,
                           "chosen_id": values["selected_action_id"]})
        return values

    def select_target(self) -> tuple[int, int] | None:
        """Put the cursor on a live enemy (the ROM's own unit telemetry)."""
        values = self.state()
        enemies = self.live_enemies(values)
        if not enemies:
            return None
        cursor = (values["cursor_x"], values["cursor_y"])
        goal = min(enemies, key=lambda point: (abs(point[0] - cursor[0]) +
                                                abs(point[1] - cursor[1])))
        self.log(f"    target: cursor {cursor} -> {goal} "
                 f"(enemies {enemies})")
        for _ in range(64):
            values = self.state()
            cursor = (values["cursor_x"], values["cursor_y"])
            if cursor == goal:
                break
            dx = goal[0] - cursor[0]
            dy = goal[1] - cursor[1]
            order = []
            if dx > 0:
                order.append("Right")
            elif dx < 0:
                order.append("Left")
            if dy > 0:
                order.append("Down")
            elif dy < 0:
                order.append("Up")
            if not order:
                break
            moved = False
            for key in order:
                self.press(key, 2)
                self.wait(6)
                after = self.state()
                if (after["cursor_x"], after["cursor_y"]) != cursor:
                    moved = True
                    break
            if not moved:
                break
        self.trace.append({"do": "target-select", "goal": list(goal)})
        return goal

    def select_action_index(self, wanted: int) -> dict[str, int]:
        """Put the action cursor on ``wanted`` (the list wraps around)."""
        values = self.state()
        count = max(1, values["action_count"])
        for _ in range(count):
            values = self.state()
            if values["action_index"] == wanted:
                break
            self.press("Down", 2)
            self.wait(10)
        return self.state()

    def place_cursor(self, goal: tuple[int, int]) -> bool:
        """Walk the target cursor onto ``goal`` (x first, then y)."""
        for _ in range(64):
            values = self.state()
            cursor = (values["cursor_x"], values["cursor_y"])
            if cursor == goal:
                return True
            dx = goal[0] - cursor[0]
            dy = goal[1] - cursor[1]
            order = []
            if dx > 0:
                order.append("Right")
            elif dx < 0:
                order.append("Left")
            if dy > 0:
                order.append("Down")
            elif dy < 0:
                order.append("Up")
            if not order:
                return False
            moved = False
            for key in order:
                self.press(key, 2)
                self.wait(6)
                after = self.state()
                if (after["cursor_x"], after["cursor_y"]) != cursor:
                    moved = True
                    break
            if not moved:
                return False
        return False

    def actor_cell(self, values: dict[str, int]) -> tuple[int, int]:
        """The acting unit's cell.

        The telemetry's ``selected_unit_x`` / ``selected_unit_y`` are zero while
        the controller is in the target selection (the controller reports "no
        selected unit" there), so the acting unit is found as the **player
        unit closest to the cursor** -- the cursor starts on the unit's own
        cell when the target selection opens.
        """
        cursor = (values["cursor_x"], values["cursor_y"])
        best: tuple[int, int] | None = None
        best_distance = 1 << 30
        count = min(values["unit_count"], 12)
        for index in range(count):
            if values[f"unit_active[{index}]"] == 0:
                continue
            if values[f"unit_side[{index}]"] != SIDE_PLAYER:
                continue
            point = (values[f"unit_x[{index}]"], values[f"unit_y[{index}]"])
            distance = abs(point[0] - cursor[0]) + abs(point[1] - cursor[1])
            if distance < best_distance:
                best_distance = distance
                best = point
        if best is None:
            return cursor
        return best

    def candidate_targets(self, values: dict[str, int]) -> list[tuple[int, int]]:
        """The cells worth trying as a target.

        The action's target policy decides which cells are legal and the
        policy is not in the telemetry, so the driver tries **all** plausible
        cells: the enemies (for ``opponent_unit``) and the empty cells around
        the acting unit (for ``empty_tile``).
        """
        candidates: list[tuple[int, int]] = []
        actor = self.actor_cell(values)
        for point in self.live_enemies(values):
            if point not in candidates:
                candidates.append(point)
        for radius in (1, 2, 3):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    point = (actor[0] + dx, actor[1] + dy)
                    if point not in candidates:
                        candidates.append(point)
        return candidates

    def action_and_target(self, prefer_index: int | None = None) -> bool:
        """Pick an action and a target the ROM itself accepts.

        The action's target policy (``opponent_unit`` / ``empty_tile``) decides
        which cells are legal, and the policy is not in the telemetry, so the
        driver simply *asks the ROM*: it walks the action list, confirms the
        action, and then tries the cells that could be legal targets until
        the confirmation is accepted.
        """
        values = self.state()
        count = max(1, values["action_count"])
        order = list(range(count))
        if prefer_index is not None and prefer_index in order:
            order.remove(prefer_index)
            order.insert(0, prefer_index)
        for action_index in order:
            self.log(f"    trying action[{action_index}]")
            self.select_action_index(action_index)
            values = self.state()
            action_id = values["selected_action_id"]
            # Confirm the action.  A self-targeting action goes straight on.
            self.press("A", 4)
            self.wait(40)
            values = self.state()
            if values["phase"] != PHASE_ACTION_SELECTION:
                self.log(f"    action[{action_index}] id={action_id} confirmed "
                         f"-> phase {x1_telemetry.phase_name(values['phase'])}")
                self.trace.append({
                    "do": "action-and-target",
                    "action_index": action_index, "action_id": action_id,
                    "target": None,
                    "phase": values["phase"],
                })
                return True
            # The action was refused (the ROM stays in the action list).
            self.trace.append({
                "do": "action-refused", "action_index": action_index,
                "action_id": action_id,
                "control_error": values["last_control_error"],
                "player_error": values["last_player_error"],
            })
            continue
        self.log("    no action was accepted")
        return False

    # ---------------------------------------------------------- the battle
    def play_route(self, route: dict[str, object],
                   max_steps: int = 0, route_loops: int = 6) -> bool:
        steps = route["steps"]
        if max_steps:
            steps = steps[:max_steps]
        index = 0
        loop = 0
        while index < len(steps) or loop < route_loops:
            if index >= len(steps):
                # The route is shorter than the battle: the battle of the
                # original takes more turns than the offline route covers.
                # Start the route again, so the driver keeps playing the
                # battle until it is decided.
                values = self.state()
                if values["phase"] in SETTLEMENT_PHASES:
                    return True
                loop += 1
                index = 0
                self.log(f"  the route ran out (round {values['round']}, "
                         f"phase {x1_telemetry.phase_name(values['phase'])}), "
                         f"starting it again ({loop}/{route_loops})")
                self.trace.append({
                    "do": "route-loop", "loop": loop, "round": values["round"],
                    "phase": values["phase"], "frame": self.frames,
                })
                continue
            step = steps[index]
            key = step["key"]
            want = int(step.get("phase", -1))
            if key == "":
                if want < 0:
                    self.wait_idle(timeout=6000)
                else:
                    deadline = self.frames + 1500
                    while self.frames < deadline:
                        if self.state()["phase"] != want:
                            break
                        self.wait(8)
                index += 1
                continue

            adaptive = want in (PHASE_ACTION_SELECTION, PHASE_TARGET_SELECTION)
            if adaptive:
                values = self.wait_phase(want, timeout=600,
                                         require_idle=False)
                if values is None:
                    now = self.state()
                    if now["phase"] in SETTLEMENT_PHASES:
                        return True
                    if now["phase"] > want:
                        # The previous adaptive step already handled it.
                        index += 1
                        continue
                    self.errors.append(
                        f"step {index} ({key}, phase {want}): the ROM never "
                        f"reached phase {want}; it is in "
                        f"{x1_telemetry.phase_name(now['phase'])} "
                        f"(round {now['round']})")
                    return False
            else:
                values = (self.wait_phase(want) if want >= 0
                          else self.state())
                if want >= 0 and values is None:
                    now = self.state()
                    if (want in TURN_FLOW_ORDER and
                            now["phase"] in TURN_FLOW_ORDER and
                            TURN_FLOW_ORDER.index(now["phase"]) >
                            TURN_FLOW_ORDER.index(want)):
                        # The ROM has already walked past the phase this
                        # route step waits for, so the step is stale: skip it
                        # instead of stopping the run.
                        self.log(f"  step {index}: the ROM is already past "
                                 f"phase {want} (it is in "
                                 f"{x1_telemetry.phase_name(now['phase'])}), "
                                 f"the route step is stale")
                        self.trace.append({
                            "step": index, "do": "stale-route-step",
                            "want_phase": want, "phase": now["phase"],
                            "round": now["round"], "frame": self.frames,
                        })
                        index += 1
                        continue
                    if (want == PHASE_SCRIPT_BLOCKED and
                            now["phase"] in TURN_FLOW_ORDER):
                        # The route waits for a dialogue that the ROM did
                        # not run (the script of the round it is in was
                        # already played): the step is stale as well.
                        self.log(f"  step {index}: the ROM did not run the "
                                 f"dialogue of this round (it is in "
                                 f"{x1_telemetry.phase_name(now['phase'])}), "
                                 f"the route step is stale")
                        self.trace.append({
                            "step": index, "do": "stale-dialogue-step",
                            "want_phase": want, "phase": now["phase"],
                            "round": now["round"], "frame": self.frames,
                        })
                        index += 1
                        continue
                    if (want in TURN_FLOW_ORDER and
                            now["phase"] == PHASE_SCRIPT_BLOCKED):
                        # The ROM runs a dialogue where the route does not
                        # expect one (the black field transition of the
                        # wave 14 moves the script around): play the
                        # dialogue out and carry on with the route.
                        self.log(f"  step {index}: the ROM is in a dialogue "
                                 f"where the route expects "
                                 f"{x1_telemetry.phase_name(want)}, "
                                 f"playing the dialogue out")
                        if self.advance_dialogue():
                            self.trace.append({
                                "step": index, "do": "played-dialogue",
                                "want_phase": want,
                                "phase": self.state()["phase"],
                                "round": now["round"], "frame": self.frames,
                            })
                            index += 1
                            continue
                    self.notes.append(
                        f"step {index} ({key}, phase {want}): the ROM was in "
                        f"{x1_telemetry.phase_name(now['phase'])} "
                        f"(round {now['round']}); the key was pressed anyway")
                    self.log(f"  step {index}: the ROM is in "
                             f"{x1_telemetry.phase_name(now['phase'])}, not "
                             f"in {x1_telemetry.phase_name(want)}; pressing "
                             f"{key} anyway")

            # ---------------------------------------------------- adaptive
            if want in (PHASE_ACTION_SELECTION, PHASE_TARGET_SELECTION):
                # The driver owns these two phases: the action's target
                # policy decides which cells are legal, and the policy is
                # not in the telemetry, so the driver asks the ROM directly.
                values = self.wait_phase(want, timeout=600,
                                         require_idle=False)
                if values is None:
                    now = self.state()
                    if now["phase"] in SETTLEMENT_PHASES:
                        return True
                    if now["phase"] > want:
                        # The previous adaptive step already handled it.
                        index += 1
                        continue
                    self.errors.append(
                        f"step {index} ({key}, phase {want}): the ROM never "
                        f"reached phase {want}; it is in "
                        f"{x1_telemetry.phase_name(now['phase'])} "
                        f"(round {now['round']})")
                    return False
                if want == PHASE_ACTION_SELECTION:
                    self.log(f"  step {index}: adaptive action selection")
                    if not self.action_and_target(self.prefer_action_index):
                        self.errors.append(
                            f"step {index}: no action/target pair was "
                            f"accepted")
                        return False
                    index += 1
                    continue
                # A target selection the driver did not start: put the cursor
                # on the nearest live enemy and confirm it.
                self.log(f"  step {index}: adaptive target selection")
                for target in self.candidate_targets(values):
                    if not self.place_cursor(target):
                        continue
                    self.press("A", 4)
                    self.wait(40)
                    after = self.state()
                    if after["phase"] != PHASE_TARGET_SELECTION:
                        self.log(f"    target {target} accepted -> "
                                 f"{x1_telemetry.phase_name(after['phase'])}")
                        self.trace.append({
                            "step": index, "do": "adaptive-target-confirm",
                            "target": list(target),
                            "phase": after["phase"],
                        })
                        index += 1
                        break
                else:
                    after = self.state()
                    self.errors.append(
                        f"step {index}: the ROM refused every target "
                        f"(control_error={after['last_control_error']}, "
                        f"player_error={after['last_player_error']})")
                    return False
                continue

            if want == PHASE_SCRIPT_BLOCKED:
                # The dialogue swallows a press that arrives while the
                # typewriter is still running, and the product code latches
                # the confirmation until the button is released -- so the
                # driver releases the button between the attempts.
                before = self.script_fingerprint(self.state())
                accepted = False
                for attempt in range(4):
                    accepted = self.press_until(
                        key,
                        lambda v: (v["phase"] != PHASE_SCRIPT_BLOCKED or
                                   self.script_fingerprint(v) != before),
                        max_frames=2400)
                    if accepted:
                        break
                    self.probe.run("keyoff")
                    self.wait(60)
                    before = self.script_fingerprint(self.state())
                if not accepted:
                    # The script may be in a ``wait_frames`` block, which the
                    # ROM advances on its own -- so wait for it.
                    deadline = self.frames + 6000
                    while self.frames < deadline:
                        values = self.state()
                        if (values["phase"] != PHASE_SCRIPT_BLOCKED or
                                self.script_fingerprint(values) != before):
                            accepted = True
                            break
                        self.wait(16)
                if not accepted:
                    values = self.state()
                    self.trace.append({
                        "step": index, "do": "script-stuck",
                        "script_phase": values["script_phase"],
                        "script_command_index": values["script_command_index"],
                        "script_text_address": values["script_text_address"],
                        "script_selector": values["script_selector"],
                        "script_message_window_visible":
                            values["script_message_window_visible"],
                        "presentation_busy": values["presentation_busy"],
                    })
                    self.log(f"  step {index}: script stuck: "
                             f"script_phase={values['script_phase']} "
                             f"command_index={values['script_command_index']} "
                             f"text={values['script_text_address']:#x}")
                    self.shot(f"script-stuck-{index:03d}")
                    self.errors.append(
                        f"step {index} ({key}, phase {want}): the dialogue "
                        f"never advanced")
                    return False
            else:
                self.press(key, int(step.get("hold", 4)))
            self.wait(min(int(step.get("settle", 60)), 300))
            values = self.state()
            self.trace.append({
                "step": index, "key": key, "want_phase": want,
                "phase": values["phase"], "round": values["round"],
                "action_index": values["action_index"],
                "action_id": values["selected_action_id"],
                "action_error": values["selected_action_error"],
                "cursor": (values["cursor_x"], values["cursor_y"]),
                "outcome": values["condition_outcome"],
                "frame": self.frames,
            })
            if values["phase"] in SETTLEMENT_PHASES:
                self.log(f"  step {index}: reached settlement phase "
                         f"{x1_telemetry.phase_name(values['phase'])}")
                return True
            index += 1
        return False

    @staticmethod
    def script_fingerprint(values: dict[str, int]) -> tuple[int, ...]:
        return (values["script_phase"], values["script_command_index"],
                values["script_text_address"], values["script_selector"],
                values["script_portrait_0_id"], values["script_portrait_1_id"])

    def advance_dialogue(self, max_taps: int = 16) -> bool:
        """Tap A until the ROM leaves the script dialogue.

        The dialogue swallows a press that arrives while the typewriter is
        still running, and the scene latches the confirmation until the
        button is released, so the taps have to be released between them.
        """
        for _ in range(max_taps):
            if self.state()["phase"] != PHASE_SCRIPT_BLOCKED:
                return True
            before = self.script_fingerprint(self.state())
            self.press_until(
                "A",
                lambda v: (v["phase"] != PHASE_SCRIPT_BLOCKED or
                           self.script_fingerprint(v) != before),
                max_frames=1200)
            self.wait(30)
        return self.state()["phase"] != PHASE_SCRIPT_BLOCKED

    # -------------------------------------------------- the settlement chain
    def play_settlement(self, settle_frames: int = 90,
                        max_pages: int = 40) -> dict[str, object]:
        result: dict[str, object] = {"pages": [], "final_phase": None}
        for _ in range(max_pages):
            values = self.state()
            phase = values["phase"]
            if phase not in SETTLEMENT_PHASES:
                result["final_phase"] = phase
                break
            self.wait(settle_frames)
            values = self.state()
            phase = values["phase"]
            if phase not in SETTLEMENT_PHASES:
                result["final_phase"] = phase
                break
            page = values["training_detail_page"]
            path = self.shot(f"{x1_telemetry.phase_name(phase)}-p{page}")
            entry = {
                "file": path.name,
                "phase": phase,
                "phase_name": x1_telemetry.phase_name(phase),
                "settlement_page": page,
                "round": values["round"],
                "outcome": values["condition_outcome"],
                "result_participant_count": values["result_participant_count"],
                "sha256": sha256_file(path),
            }
            self.captures.append(entry)
            result["pages"].append(entry)
            self.log(f"  settlement page: {entry['phase_name']} "
                     f"page={page} -> {path.name}")
            self.press("A", 4)
            self.wait(settle_frames)
        values = self.state()
        result["final_phase"] = values["phase"]
        result["final_phase_name"] = x1_telemetry.phase_name(values["phase"])
        result["outcome"] = values["condition_outcome"]
        result["round"] = values["round"]
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--route", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-y1" /
                        "mgba-probe.exe")
    parser.add_argument("--boot", action="store_true")
    parser.add_argument("--state", type=pathlib.Path, default=None)
    parser.add_argument("--settle-frames", type=int, default=90)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--prefer-action-index", type=int, default=None,
                        help="try this action index first (the offline route's "
                             "own choice)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    route = json.loads(args.route.read_text(encoding="utf-8"))
    started = time.time()
    receipt: dict[str, object] = {
        "schema": "konoha.s49-y1-closed-loop-play.v1",
        "rom": str(args.rom),
        "rom_sha256": sha256_file(args.rom),
        "route": str(args.route),
        "route_sha256": sha256_file(args.route),
        "out": str(args.out),
    }
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        driver = Driver(probe, x1_telemetry.Telemetry(probe), args.out,
                        verbose=not args.quiet,
                        prefer_action_index=args.prefer_action_index)
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
        reached = driver.play_route(route, args.max_steps)
        settlement: dict[str, object] = {}
        if reached:
            settlement = driver.play_settlement(args.settle_frames)
        else:
            values = driver.state()
            settlement = {"final_phase": values["phase"],
                         "final_phase_name": x1_telemetry.phase_name(values["phase"]),
                         "outcome": values["condition_outcome"],
                         "round": values["round"], "pages": []}
        receipt.update({
            "reached_settlement": reached,
            "frames_run": driver.frames,
            "keys_pressed": driver.keys,
            "errors": driver.errors,
            "settlement": settlement,
            "captures": driver.captures,
        })
        stderr = probe.stderr
        (args.out / "stderr.txt").write_text("\n".join(stderr) + "\n",
                                              encoding="utf-8", newline="\n")
        receipt["stderr_tail"] = stderr[-40:]
        (args.out / "trace.json").write_text(
            json.dumps(driver.trace, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")
    receipt["wall_seconds"] = round(time.time() - started, 1)
    (args.out / "play.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in receipt.items()
                      if key not in ("trace", "captures")},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
