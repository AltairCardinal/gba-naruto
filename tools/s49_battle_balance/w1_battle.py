#!/usr/bin/env python3
"""W1 (wave 15): play the remake's battle to a **win** and walk the chain.

Why a new driver
----------------
``routeY.json`` was generated offline by ``u2_route_gen.cpp`` against the
controller of wave 11, and the wave 14 black field work moved the script
around, so the route no longer lines up with the ROM step by step.  The
driver therefore plays the battle **closed loop**: the ROM's own telemetry
says which phase it is in, and the driver does what that phase needs until
the battle is decided.

What it does per phase:

===============  =========================================================
phase            what the driver does
===============  =========================================================
script_blocked   taps A until the dialogue advances
unit_selection   puts the cursor on a player unit and confirms it
move_selection   moves the cursor to a free cell and confirms the move
command_selection  confirms the command (the first entry is the attack)
action_selection  asks the ROM which action it accepts and confirms it
target_selection  puts the cursor on a live enemy and confirms it
facing_selection confirms the facing
defense_*        confirms the defense
enemy_turn       waits for the enemies
===============  =========================================================

When the battle is decided the settlement chain is walked with the confirm
button and every page is photographed.
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

import w1_boot  # noqa: E402
import w1_probe as probe_module  # noqa: E402
import x1_telemetry  # noqa: E402
import y1_play  # noqa: E402

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
PHASE_SCRIPT_BLOCKED = y1_play.PHASE_SCRIPT_BLOCKED
PHASE_TURN_BANNER = y1_play.PHASE_TURN_BANNER
PHASE_TARGET_PREVIEW = y1_play.PHASE_TARGET_PREVIEW
PHASE_TARGET_CONFIRMATION = y1_play.PHASE_TARGET_CONFIRMATION
PHASE_END_CONFIRMATION = y1_play.PHASE_END_CONFIRMATION
PHASE_OUTCOME = y1_play.PHASE_OUTCOME
SETTLEMENT_PHASES = y1_play.SETTLEMENT_PHASES


class BattlePlayer(y1_play.Driver):
    """The Y1 driver's helpers plus a closed loop battle."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.steps: list[dict[str, object]] = []

    def note(self, what: str, **extra: object) -> None:
        values = self.state()
        entry = {"do": what, "frame": self.frames,
                 "phase": values["phase"], "round": values["round"]}
        entry.update(extra)
        self.steps.append(entry)

    # ------------------------------------------------------------- helpers
    def player_unit_cell(self) -> tuple[int, int] | None:
        """The cell of the player unit the cursor is on, or the first one."""
        values = self.state()
        count = min(values["unit_count"], 12)
        cursor = (values["cursor_x"], values["cursor_y"])
        fallback = None
        for index in range(count):
            if values[f"unit_active[{index}]"] == 0:
                continue
            if values[f"unit_side[{index}]"] != y1_play.SIDE_PLAYER:
                continue
            if values[f"unit_hp[{index}]"] <= 0:
                continue
            point = (values[f"unit_x[{index}]"], values[f"unit_y[{index}]"])
            if point == cursor:
                return point
            if fallback is None:
                fallback = point
        return fallback

    def select_unit(self) -> bool:
        goal = self.player_unit_cell()
        if goal is not None:
            self.place_cursor(goal)
        self.press("A", 4)
        self.wait(18)
        if self.state()["phase"] != PHASE_UNIT_SELECTION:
            return True
        # The unit under the cursor may not be selectable: cycle the roster
        # and try the next one.
        for _ in range(6):
            self.press("R", 2)
            self.wait(6)
            self.press("A", 4)
            self.wait(18)
            if self.state()["phase"] != PHASE_UNIT_SELECTION:
                return True
        return False

    def move_unit(self) -> bool:
        """Move the unit: the cursor starts on its own cell."""
        values = self.state()
        if values["phase"] != PHASE_MOVE_SELECTION:
            return True
        for key in ("Right", "Down", "Left", "Up", "Right"):
            self.press(key, 2)
            self.wait(8)
            self.press("A", 4)
            self.wait(18)
            values = self.state()
            if values["phase"] != PHASE_MOVE_SELECTION:
                return True
        return False

    def choose_action(self) -> bool:
        return self.action_and_target()

    def choose_target(self) -> bool:
        """Put the cursor on a legal target and confirm it.

        The action's target policy decides which cells are legal and the
        policy is not in the telemetry, so the driver tries every plausible
        cell (the live enemies and the free cells around the acting unit)
        until the ROM accepts one.
        """
        for target in self.candidate_targets(self.state()):
            if not self.place_cursor(target):
                continue
            self.press("A", 4)
            self.wait(18)
            if self.state()["phase"] != PHASE_TARGET_SELECTION:
                return True
        return False

    # --------------------------------------------------------------- battle
    def play_battle(self, max_turns: int = 60) -> bool:
        for turn in range(max_turns):
            values = self.state()
            phase = values["phase"]
            self.steps.append({"do": "phase", "frame": self.frames,
                               "phase": phase, "round": values["round"]})
            if phase in SETTLEMENT_PHASES:
                self.note("battle-decided", turn=turn,
                          outcome=values["condition_outcome"])
                return True
            if phase == PHASE_SCRIPT_BLOCKED:
                self.advance_dialogue()
                continue
            if phase == PHASE_UNIT_SELECTION:
                self.select_unit()
                continue
            if phase == PHASE_MOVE_SELECTION:
                self.move_unit()
                continue
            if phase in (PHASE_COMMAND_SELECTION, PHASE_CHAKRA_SELECTION,
                         PHASE_REST_CONFIRMATION):
                self.press("A", 4)
                self.wait(18)
                continue
            if phase == PHASE_ACTION_SELECTION:
                self.choose_action()
                continue
            if phase == PHASE_COMBINATION_DECISION:
                self.press("A", 4)
                self.wait(18)
                continue
            if phase == PHASE_TARGET_SELECTION:
                self.choose_target()
                continue
            if phase == PHASE_DEFENSE_DECISION:
                # The original's defence decision has two answers; the route
                # picks the second one ("do not defend") and lets the enemy
                # attack.
                self.press("Down", 2)
                self.wait(6)
                self.press("A", 4)
                self.wait(18)
                continue
            if phase in (PHASE_FACING_SELECTION, PHASE_DEFENSE_SELECTION,
                         PHASE_TURN_BANNER,
                         PHASE_TARGET_PREVIEW, PHASE_TARGET_CONFIRMATION,
                         PHASE_END_CONFIRMATION):
                self.press("A", 4)
                self.wait(18)
                continue
            if phase == PHASE_ENEMY_TURN:
                self.wait(30)
                continue
            self.wait(30)
        self.note("battle-timeout")
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--exe", type=pathlib.Path,
                        default=HERE.parents[1] / "build" / "mgba-probe-w1" /
                        "mgba-probe.exe")
    parser.add_argument("--boot", action="store_true")
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    receipt: dict[str, object] = {
        "schema": "konoha.s49-w1-battle-player.v1",
        "rom": str(args.rom),
        "rom_sha256": y1_play.sha256_file(args.rom),
    }
    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        driver = BattlePlayer(probe, x1_telemetry.Telemetry(probe), args.out,
                              verbose=not args.quiet)
        if args.boot:
            boot = w1_boot.Boot(probe, args.out / "boot")
            receipt["boot"] = boot.run()
        else:
            probe.run("frames 120 0x00000000")
            driver.frames = 120
        driver.log(f"telemetry at 0x{driver.telemetry.locate(verbose=True):08X}")
        decided = driver.play_battle(args.max_turns)
        settlement: dict[str, object] = {}
        if decided:
            settlement = driver.play_settlement(90)
        else:
            values = driver.state()
            settlement = {"final_phase": values["phase"],
                          "final_phase_name":
                              x1_telemetry.phase_name(values["phase"]),
                          "outcome": values["condition_outcome"],
                          "round": values["round"], "pages": []}
        values = driver.state()
        receipt.update({
            "battle_decided": decided,
            "outcome": values["condition_outcome"],
            "round": values["round"],
            "frames_run": driver.frames,
            "keys_pressed": driver.keys,
            "errors": driver.errors,
            "settlement": settlement,
            "steps": driver.steps,
        })
        (args.out / "stderr.txt").write_text(
            "\n".join(probe.stderr) + "\n", encoding="utf-8", newline="\n")
    receipt["wall_seconds"] = round(time.time() - started, 1)
    (args.out / "battle.json").write_text(
        json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in receipt.items()
                      if key not in ("steps", "settlement")},
                     ensure_ascii=False, indent=1))
    print("settlement pages:", len(settlement.get("pages", [])),
          "final:", settlement.get("final_phase_name"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
