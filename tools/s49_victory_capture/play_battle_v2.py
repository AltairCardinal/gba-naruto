#!/usr/bin/env python3
"""Play the original S49 battle 14 (Konohamaru vs the bees) to a decision.

This is stream M's driver.  It supersedes ``play_battle.py`` (stream K),
which could not move its second unit because it guessed landing cells from
coordinates and because it watched the wrong position field.

Facts this driver relies on (all measured on this machine, see
notes/s49-fidelity/M-original-victory-truth.md):

* the **live** unit position is the pool's x/y at **+0xC7/+0xC8**; +0xC4/+0xC5
  keeps the position the unit had when the turn started
* the **move range is a Manhattan radius of 3** around the acting unit; the
  cell cursor is clamped to it and an out-of-range cell answers with the
  game's own error box
* 十字手里剑 hits a target in the same row or column within 3 cells;
  the aim cursor starts on the acting unit
* the player controls all four allies, the five bees are AI
* the game answers an illegal choice with a wide error box and the
  「可以嗎？」 dialog is a narrow light box -- the two are told apart by pixel
  signature, so the driver never has to guess

Usage::

    python tools/s49_victory_capture/play_battle_v2.py \
        --out build/s49-victory-capture/run-v2
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

import battle as battle_module  # noqa: E402
import overlay as overlay_module  # noqa: E402
import probe as probe_module  # noqa: E402
import s49_state  # noqa: E402

_BUILD = pathlib.Path(__file__).resolve().parents[2] / "build"
DEFAULT_EXE = _BUILD / "mgba-probe-m" / "mgba-probe.exe"
if not DEFAULT_EXE.exists():
    DEFAULT_EXE = _BUILD / "mgba-probe" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")

MENU_ITEM_MOVE = 0
MENU_ITEM_JUTSU = 1
MENU_ITEM_CHAKRA = 2
MENU_ITEM_REST = 3
MENU_ITEM_END = 4

JUTSU_SHURIKEN = 3

MOVE_RANGE = 3          # Manhattan radius
SHURIKEN_RANGE = 3      # straight line range
BEE_SLOTS = (5, 6, 7, 8, 9)

FILL = (231, 247, 214)


def has_bottom_box(image) -> bool:
    """The story / result message box at the bottom of the screen."""
    region = image.crop((7, 128, 232, 158))
    light = sum(1 for pixel in region.get_flattened_data() if pixel == FILL)
    return light > 500


def error_box_visible(image) -> bool:
    """The game's own rejection notice.

    Measured on this machine: the rejection box paints the light colour
    (231,247,214) over the message area (x 40..200, y 45..100) with 2033
    pixels, while the 「可以嗎？」 dialog uses the same area but also covers
    the narrow confirm region (x 86..154, y 30..72) with >500 pixels, and
    the story dialogue box sits at the bottom of the screen (y >= 135).
    """
    region = image.crop((40, 45, 200, 100))
    light = sum(1 for pixel in region.get_flattened_data() if pixel == FILL)
    confirm = image.crop((86, 30, 154, 72))
    confirm_light = sum(1 for pixel in confirm.get_flattened_data() if pixel == FILL)
    return 1000 < light < 3000 and confirm_light < 500


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def aligned(origin: tuple[int, int], target: tuple[int, int]) -> bool:
    """True when the shuriken can reach the target (same row or column)."""
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    if dx != 0 and dy != 0:
        return False
    distance = abs(dx) + abs(dy)
    return 1 <= distance <= SHURIKEN_RANGE


def shot_candidates(unit: tuple[int, int],
                    bee: tuple[int, int]) -> list[tuple[int, int]]:
    """Cells the unit could stand on to shoot ``bee`` with the shuriken."""
    out = []
    for offset in range(-SHURIKEN_RANGE, SHURIKEN_RANGE + 1):
        if offset == 0:
            continue
        out.append((bee[0] + offset, bee[1]))
        out.append((bee[0], bee[1] + offset))
    return out


class Driver:
    def __init__(self, battle: battle_module.Battle, log: list,
                 debug_shots: pathlib.Path | None = None,
                 checkpoint: pathlib.Path | None = None) -> None:
        self.battle = battle
        self.log = log
        self.debug_shots = debug_shots
        self.advance_index = 0
        self.wait_index = 0
        self.jutsu_index = 0
        self.resolve_index = 0
        self.checkpoint = checkpoint
        self.actions_done = 0

    def save_checkpoint(self) -> None:
        """Write the battle state so a crashed probe can be replaced."""
        if self.checkpoint is None:
            return
        try:
            self.battle.probe.save(self.checkpoint)
        except Exception:
            pass

    # ------------------------------------------------------------ helpers
    def record(self, event: str, **extra) -> None:
        row = {"event": event}
        row.update(extra)
        self.log.append(row)

    def resolve_until_menu(self, limit: int = 20) -> str:
        """Advance the game until the action menu is back.

        Pressing A blindly is dangerous: in the action menu A selects
        「移動」, which opens the move phase, and one more A confirms a move.
        So the loop watches the screen and stops as soon as the menu is up.
        """
        for _ in range(limit):
            menu = self.battle.menu()
            if self.debug_shots is not None:
                self.debug_shots.mkdir(parents=True, exist_ok=True)
                self.battle.probe.shot(
                    self.debug_shots / f"resolve-{self.resolve_index:03d}.png")
            self.resolve_index += 1
            self.record("resolve", menu=menu, level=self.battle.menu_level())
            if menu in ("action5", "action2"):
                return menu
            if not self.alive_bees():
                # the battle is decided -- stop pressing A so the victory
                # performance is not skipped
                return "victory"
            if error_box_visible(self.battle.screen()):
                self.battle.press("B", settle=140, tag="dismiss")
                continue
            if menu == "jutsu":
                self.battle.press("B", settle=140, tag="leave-jutsu")
                continue
            if has_bottom_box(self.battle.screen()):
                # a result / story message: A advances it
                self.battle.press("A", settle=160, tag="resolve")
                continue
            # no menu and no message: the game sits in a sub mode (aim or
            # target selection).  Those live on the jutsu level (4) and B
            # walks out of them; everything else is a dialogue.
            if self.battle.menu_level() == 4:
                self.battle.press("B", settle=140, tag="back-out")
            else:
                self.battle.press("A", settle=160, tag="resolve")
            continue
        return self.battle.menu()

    def wait_for_menu(self, limit: int = 20, step: int = 90,
                      nudge_after: int = 8) -> str:
        """Wait for the game to finish an animation and show the menu again.

        The walk animation after a move takes a few hundred frames and may be
        followed by a prompt, so the loop presses A; if that lands on the
        compact menu it opens the jutsu list, which the caller understands.
        """
        pressed = 0
        for index in range(limit):
            menu = self.battle.menu()
            if self.debug_shots is not None:
                self.debug_shots.mkdir(parents=True, exist_ok=True)
                self.battle.probe.shot(
                    self.debug_shots / f"wait-{self.wait_index:03d}.png")
            self.wait_index += 1
            self.record("wait", index=index, menu=menu)
            if menu in ("action5", "action2", "jutsu"):
                return menu
            if error_box_visible(self.battle.screen()):
                self.battle.press("B", settle=140, tag="dismiss")
                continue
            if index >= nudge_after and pressed < 3:
                self.battle.press("A", settle=step, tag="wait")
                pressed += 1
            else:
                self.battle.probe.frames(step, 0)
        return self.battle.menu()

    def alive_bees(self) -> list[dict]:
        hp = self.battle.hp()
        out = []
        for slot in BEE_SLOTS:
            if hp[slot - 1] <= 0:
                continue
            position = self.battle.position(slot)
            if position is None:
                continue
            out.append({"slot": slot, "x": position[0], "y": position[1],
                        "hp": hp[slot - 1]})
        return out

    def allies(self) -> list[dict]:
        return [u for u in self.battle.pool_current() if u["side"] == 0]

    # ------------------------------------------------------------- menus
    def open_jutsu(self, menu: str) -> bool:
        """Make sure the jutsu list is on screen.

        The transition into the list takes a moment, so the screen is checked
        again instead of trusting a single press.
        """
        for attempt in range(12):
            current = self.battle.menu()
            level = self.battle.menu_level()
            self.record("jutsu-probe", current=current, level=level)
            if current == "jutsu":
                return True
            if current == "action5":
                if not self.battle.select_menu_item(MENU_ITEM_JUTSU):
                    return False
                self.battle.press("A", settle=140, tag="open-jutsu")
                continue
            if current == "action2":
                # the compact menu (術·忍具 / 行動終了): its first entry is
                # 「術·忍具」, so A opens the jutsu list.  (B would cancel the
                # move and put the unit back on its old cell.)
                self.battle.press("A", settle=140, tag="open-jutsu")
                continue
            if attempt >= 4:
                # a message box (the move quote) waits for an A press
                self.battle.press("A", settle=140, tag="nudge")
                continue
            if level == 3:
                # the game is still busy (walk animation, message box): one A
                # press advances it, and the game buffers the press until the
                # compact menu is up -- which opens the jutsu list.
                self.battle.press("A", settle=140, tag="nudge")
                continue
            self.battle.probe.frames(60, 0)
        return self.battle.menu() == "jutsu"

    def end_action(self, menu: str) -> None:
        index = MENU_ITEM_END if menu == "action5" else 1
        if not self.battle.select_menu_item(index):
            self.battle.press("A", settle=140, tag="pick-end")
        else:
            self.battle.press("A", settle=140, tag="pick-end")
        for _ in range(8):
            if self.battle.confirm_dialog():
                self.battle.press("A", settle=140, tag="confirm-end")
                return
            if self.battle.menu() in ("action5", "action2"):
                return          # the action is over already
            self.battle.probe.frames(60, 0)

    # -------------------------------------------------------------- move
    def move_candidates(self, unit: tuple[int, int],
                        bees: list[dict]) -> list[tuple[int, int]]:
        """Cells that would put the unit into shuriken range of a bee.

        Ordered by: the bee with the lowest HP first (finish wounded bees),
        then by the distance to that bee, then by the move cost.
        """
        occupied = {(u["x"], u["y"]) for u in self.battle.pool_current()}
        scored = []
        for bee in bees:
            for cell in shot_candidates(unit, (bee["x"], bee["y"])):
                cost = manhattan(unit, cell)
                if cost > MOVE_RANGE or cost == 0:
                    continue
                if cell in occupied:
                    continue
                if not (0 <= cell[0] <= 15 and 0 <= cell[1] <= 15):
                    continue
                scored.append((bee["hp"], manhattan(cell, (bee["x"], bee["y"])),
                               cost, cell))
        scored.sort()
        out: list[tuple[int, int]] = []
        for _hp, _dist, _cost, cell in scored:
            if cell not in out:
                out.append(cell)
        return out

    def do_move(self, menu: str, unit_slot: int,
                bees: list[dict]) -> tuple[int, int] | None:
        """Move the acting unit towards a bee.

        Every candidate is tried with the game's own oracle: an out-of-range
        or unwalkable cell answers with the error box and the move phase
        stays open, so the driver can simply try the next candidate.
        """
        if menu != "action5":
            return None
        if not self.battle.select_menu_item(MENU_ITEM_MOVE):
            return None
        self.battle.press("A", settle=140, tag="open-move")
        origin = self.battle.position(unit_slot)
        if origin is None:
            return None
        candidates = self.move_candidates(origin, bees)
        self.record("move-plan", origin=list(origin),
                    candidates=[list(c) for c in candidates])
        for cell in candidates:
            if self.battle.cursor() != cell:
                self.battle.set_cursor(*cell)
            actual = tuple(self.battle.cursor())
            self.battle.press("A", settle=140, tag="move-dest")
            after = self.battle.position(unit_slot)
            moved = after is not None and after != origin
            self.record("move-try", cell=list(cell), cursor=list(actual),
                        moved=moved, to=list(after) if after else None)
            if moved:
                return after
            image = self.battle.screen()
            if error_box_visible(image):
                self.battle.press("B", settle=140, tag="dismiss")
                continue
            if self.battle.menu() in ("action2", "action5"):
                self.record("move-phase-ended", cell=list(cell))
                return None
        return None

    # ------------------------------------------------------------ attack
    def do_shuriken(self, menu: str) -> dict | None:
        """Fire the cross shuriken at the best target in range."""
        bees = self.alive_bees()
        if not bees:
            return None
        if not self.open_jutsu(menu):
            self.record("jutsu-not-open", menu=self.battle.menu())
            return None
        if not self.battle.select_menu_item(JUTSU_SHURIKEN):
            return None
        self.battle.press("A", settle=160, tag="pick-shuriken")
        origin = self.battle.cursor()
        targets = [bee for bee in bees
                   if aligned(origin, (bee["x"], bee["y"]))]
        targets.sort(key=lambda bee: bee["hp"])
        self.record("aim", origin=list(origin),
                    targets=[[t["slot"], t["x"], t["y"], t["hp"]] for t in targets])
        for bee in targets:
            self.battle.set_cursor(bee["x"], bee["y"])
            before = self.battle.hp()
            self.battle.press("A", settle=160, tag="fire")
            dialog = False
            for _ in range(4):
                if self.battle.confirm_dialog():
                    dialog = True
                    break
                self.battle.press("A", settle=140, tag="forecast")
            if dialog:
                self.battle.press("A", settle=160, tag="confirm-fire")
            elif self.battle.hp() == before:
                # nothing happened: the target was refused.  Only then is it
                # safe to dismiss the message -- pressing B after a *successful*
                # shot cancels the attack and drops the game back into the
                # aim mode.
                if error_box_visible(self.battle.screen()):
                    self.battle.press("B", settle=140, tag="dismiss-error")
                continue
            self.resolve_until_menu()
            after = self.battle.hp()
            if after != before:
                self.record("attacked", slot=bee["slot"], hp=after)
                return {"slot": bee["slot"], "hp": after[bee["slot"] - 1]}
            self.record("shot-missed", slot=bee["slot"])
            return None
        self.record("no-target")
        return None

    # --------------------------------------------------------------- act
    def act(self) -> None:
        """One ally's whole action.

        The action always ends with 「行動終了」 unless the game has already
        handed the turn to the next unit (the acting flag in the unit pool
        tells the two apart).
        """
        menu = self.battle.menu()
        if menu not in ("action5", "action2"):
            return
        unit = self.battle.acting_ally()
        if unit is None:
            for entry in self.allies():
                if entry["acting"]:
                    unit = entry
                    break
        if unit is None:
            unit = {"slot": 1, "x": 0, "y": 0}
        slot = unit["slot"]
        position = self.battle.position(slot) or (unit["x"], unit["y"])
        bees = self.alive_bees()
        self.record("acting", slot=slot, position=list(position),
                    menu=menu, bees=len(bees))

        # already in range?  shoot from where we stand.
        if any(aligned(position, (bee["x"], bee["y"])) for bee in bees):
            if self.do_shuriken(menu):
                menu = self.resolve_until_menu()
            else:
                menu = self.battle.menu()

        # otherwise step towards a bee and shoot from there.
        if menu in ("action2", "action5"):
            moved = self.do_move(menu, slot, bees)
            if moved is not None:
                menu = self.wait_for_menu()
            if menu in ("action2", "action5"):
                if self.do_shuriken(menu):
                    menu = self.resolve_until_menu()
                else:
                    menu = self.battle.menu()

        # end the action, unless the game already moved on to the next unit
        acting = self.battle.acting_ally()
        still_mine = acting is None or acting["slot"] == slot
        menu = self.battle.menu()
        if menu in ("action2", "action5") and still_mine:
            self.end_action(menu)
            self.resolve_until_menu()
        self.record("action-done", slot=slot, menu=self.battle.menu())
        self.actions_done += 1
        self.save_checkpoint()

    # -------------------------------------------------------------- play
    def play(self, max_turns: int = 40) -> dict:
        stats = {"turns": 0, "actions": 0, "hits": 0, "victory": False}
        self.record("start", hp=self.battle.hp())
        idle = 0
        while stats["turns"] < max_turns:
            bees = self.alive_bees()
            if not bees:
                stats["victory"] = True
                self.record("victory", hp=self.battle.hp())
                break
            menu = self.battle.menu()
            if menu in ("action5", "action2"):
                stats["turns"] += 1
                stats["actions"] += 1
                before = self.battle.hp()
                self.act()
                if self.battle.hp() != before:
                    stats["hits"] += 1
                continue
            # not the player's turn: advance the dialogue / enemy phase
            idle += 1
            if self.debug_shots is not None and self.advance_index < 40:
                self.debug_shots.mkdir(parents=True, exist_ok=True)
                self.battle.probe.shot(
                    self.debug_shots / f"advance-{self.advance_index:03d}.png")
            self.advance_index += 1
            if idle > 400:
                self.record("stuck", menu=menu)
                break
            if error_box_visible(self.battle.screen()):
                self.battle.press("B", settle=140, tag="dismiss-error")
                continue
            if menu == "jutsu":
                # a stray A press can open the jutsu list; leave it again
                self.battle.press("B", settle=140, tag="leave-jutsu")
                continue
            if has_bottom_box(self.battle.screen()):
                self.battle.press("A", settle=90, tag="advance")
                continue
            if self.battle.menu_level() == 4:
                self.battle.press("B", settle=140, tag="back-out")
                continue
            self.battle.press("A", settle=90, tag="advance")
        self.record("end", hp=self.battle.hp(), stats=stats)
        return stats


def capture_endgame(battle: battle_module.Battle, out_dir: pathlib.Path,
                    frames: int = 900, every: int = 6) -> list[str]:
    """Grab the victory performance and the settlement screen."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    index = 0
    while index < frames:
        step = min(every, frames - index)
        battle.probe.frames(step, 0)
        path = out_dir / f"end-{index:05d}.png"
        battle.probe.shot(path)
        paths.append(str(path))
        index += step
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--settle", type=int, default=45)
    parser.add_argument("--endgame-frames", type=int, default=900)
    parser.add_argument("--endgame-every", type=int, default=6)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--restarts", type=int, default=8,
                        help="how often the probe may be restarted after a crash")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    log: list = []

    # The probe process dies from time to time (a non deterministic crash in
    # the mGBA CLI).  A checkpoint of the battle is written after every
    # finished action so the run can be continued from there.
    checkpoint = out_dir.parent / (out_dir.name + "-checkpoint.ss9")
    state = pathlib.Path(args.state)
    stats = {"turns": 0, "actions": 0, "hits": 0, "victory": False}
    final_hp: list[int] = []
    final_units: list[dict] = []
    endgame: list[str] = []
    error = None

    for attempt in range(args.restarts + 1):
        try:
            with probe_module.Probe(args.rom, exe=args.exe) as probe:
                probe.load(state)
                battle = battle_module.Battle(probe, settle=args.settle,
                                              screen_path=out_dir / "screen.png")
                driver = Driver(battle, log,
                                debug_shots=(out_dir / "debug") if args.debug else None,
                                checkpoint=checkpoint)
                stats = driver.play(max_turns=args.max_turns)
                final_hp = battle.hp()
                final_units = battle.pool_current()
                endgame = []
                if stats["victory"]:
                    endgame = capture_endgame(battle, out_dir / "endgame",
                                              frames=args.endgame_frames,
                                              every=args.endgame_every)
                    final_hp = battle.hp()
                    final_units = battle.pool_current()
            error = None
            break
        except Exception as failure:      # keep the log even when the probe dies
            error = f"{type(failure).__name__}: {failure}"
            log.append({"event": "error", "attempt": attempt, "message": error})
            print(f"!! attempt {attempt} failed: {error}", file=sys.stderr)
            if not checkpoint.is_file():
                break
            state = checkpoint
            print(f"   restarting the probe from {checkpoint}", file=sys.stderr)

    receipt = {
        "schema": "konoha.s49-victory-play-v2.v1",
        "rom": args.rom,
        "rom_sha256": s49_state.file_sha256(args.rom),
        "start_state": args.state,
        "start_state_sha256": s49_state.file_sha256(args.state),
        "stats": stats,
        "final_hp": final_hp,
        "final_units": final_units,
        "endgame_frames": [pathlib.Path(p).name for p in endgame],
        "log": log,
    }
    (out_dir / "play.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({"stats": stats, "hp": final_hp}, ensure_ascii=False))
    return 0 if stats["victory"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
