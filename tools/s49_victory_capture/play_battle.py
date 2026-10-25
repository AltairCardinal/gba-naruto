#!/usr/bin/env python3
"""Play the original S49 battle 14 with the probe and capture the frames.

This is the executable version of the route that stream K documents.  It
starts from ``scenario-49-battle-14-entry.ss9`` and drives the original ROM
until the battle is decided, recording PNG frames and a machine readable
receipt for every step.

Battle facts (all measured on this machine, see notes/s49-fidelity/K-original-victory.md):

* the player controls the whole party; the game asks for one ally per turn
  and shows the action menu 移動 / 术・忍具 / 查克拉 / 休息 / 行動結束
* 术・忍具 opens the jutsu list 变身术 / 影分身术 / 忍者组合拳 / 十字手里剑
* 十字手里剑 (6x3 damage, range 3 straight) kills a 25 HP bee in one hit,
  but the cursor has to sit **on** the bee and the bee has to be within three
  cells in the same row or column of the acting unit
* 变身术 (teleport, distance 3, 1 chakra) is how a unit closes the distance
* the game validates every choice: a legal target or destination raises the
  「可以嗎？」 yes/no dialog, an illegal one answers with an error box.  The
  driver uses that dialog as its oracle, so it never has to guess which ally
  is acting or whether a bee is in range

Usage::

    python tools/s49_victory_capture/play_battle.py \
        --out build/s49-victory-capture/run1 \
        --state artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9
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
import probe as probe_module  # noqa: E402
import s49_state  # noqa: E402

_BUILD = pathlib.Path(__file__).resolve().parents[2] / "build"
# A private copy of the probe avoids the LNK1104 clash with the other streams.
DEFAULT_EXE = (_BUILD / "mgba-probe-k" / "mgba-probe.exe")
if not DEFAULT_EXE.exists():
    DEFAULT_EXE = _BUILD / "mgba-probe" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
DEFAULT_STATE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints"
    r"\scenario-49-battle-14-entry.ss9")

MENU_ITEM_MOVE = 0
MENU_ITEM_JUTSU = 1
MENU_ITEM_END = 4

JUTSU_TELEPORT = 0
JUTSU_SHURIKEN = 3


def teleport_candidates(battle: battle_module.Battle,
                        origin: tuple[int, int]) -> list[tuple[int, int]]:
    """Cells to try as a teleport destination, closest to the bees first."""
    hp = battle.hp()
    bees = [battle.unit(slot) for slot in battle_module.BEE_SLOTS
            if hp[slot - 1] > 0 and battle.unit(slot) is not None]
    if not bees:
        return []
    out: list[tuple[int, int]] = []
    for bee in bees:
        dx = bee["x"] - origin[0]
        dy = bee["y"] - origin[1]
        for step in (3, 2, 1):
            if dx != 0:
                out.append((origin[0] + (step if dx > 0 else -step), origin[1]))
            if dy != 0:
                out.append((origin[0], origin[1] + (step if dy > 0 else -step)))
    seen: set[tuple[int, int]] = set()
    unique: list[tuple[int, int]] = []
    for cell in out:
        if cell in seen or cell == origin:
            continue
        if not (0 <= cell[0] <= 15 and 0 <= cell[1] <= 15):
            continue
        seen.add(cell)
        unique.append(cell)
    return unique


def open_jutsu(battle: battle_module.Battle, menu: str) -> bool:
    """Select 术・忍具 in the action menu and open the jutsu list."""
    index = MENU_ITEM_JUTSU if menu == "action5" else 0
    if not battle.select_menu_item(index):
        return False
    battle.press("A", settle=120, tag="open-jutsu")
    return True


def pick_jutsu(battle: battle_module.Battle, index: int) -> bool:
    """Highlight the jutsu with the given index and confirm it."""
    if not battle.select_menu_item(index):
        return False
    battle.press("A", settle=120, tag="pick-jutsu")
    return True


def back_out(battle: battle_module.Battle) -> str:
    """Leave the jutsu list / aim mode and come back to the action menu."""
    for _ in range(4):
        menu = battle.menu()
        if menu in ("action5", "action2"):
            return menu
        battle.press("B", settle=120, tag="back")
    return battle.menu()


def end_action(battle: battle_module.Battle, menu: str) -> None:
    """Pick 行動結束 in the action menu and confirm it."""
    index = MENU_ITEM_END if menu == "action5" else 1
    if not battle.select_menu_item(index):
        battle.press("A", settle=120, tag="pick-end")
        return
    battle.press("A", settle=120, tag="pick-end")
    if battle.confirm_dialog():
        battle.press("A", settle=120, tag="confirm-end")


def reachable_bees(battle: battle_module.Battle,
                   origin: tuple[int, int]) -> list[dict]:
    """Bees the cross shuriken can reach from ``origin``.

    The shuriken shoots three cells in a straight line, so the bee has to be
    in the same row or column and no further than three cells away.
    """
    hp = battle.hp()
    out = []
    for slot in battle_module.BEE_SLOTS:
        if hp[slot - 1] == 0:
            continue
        bee = battle.unit(slot)
        if bee is None:
            continue
        dx = bee["x"] - origin[0]
        dy = bee["y"] - origin[1]
        if dx != 0 and dy != 0:
            continue
        distance = abs(dx) + abs(dy)
        if distance == 0 or distance > battle_module.SHURIKEN_RANGE:
            continue
        out.append(bee)
    return out


def do_attack(battle: battle_module.Battle, menu: str) -> bool:
    """Fire the cross shuriken at a reachable bee.

    The driver does not need to know which ally acts: in the aim mode the
    cell cursor starts on the acting unit, so the unit's cell comes from the
    cursor.  A legal target raises the 「可以嗎？」 dialog; an illegal one
    answers 「请把对方设置在范围内」 and is dismissed with B.
    """
    before = battle.hp()
    if not open_jutsu(battle, menu):
        return False
    if not pick_jutsu(battle, JUTSU_SHURIKEN):
        back_out(battle)
        return False
    origin = battle.cursor()
    targets = reachable_bees(battle, origin)
    battle.record("aim-origin", origin=origin, targets=len(targets))
    for bee in targets:
        battle.set_cursor(bee["x"], bee["y"])
        battle.press("A", settle=150, tag="fire")
        if not battle.confirm_dialog():
            battle.press("B", settle=100, tag="dismiss-error")
            continue
        battle.press("A", settle=150, tag="confirm-fire")
        for _ in range(6):
            battle.press("A", settle=180, tag="resolve")
        after = battle.hp()
        if after != before:
            battle.record("attacked", slot=bee["slot"], hp=after)
            return True
        back_out(battle)
        return False
    battle.record("no-reachable-bee", origin=origin)
    back_out(battle)
    return False


def do_teleport(battle: battle_module.Battle, menu: str,
                position: tuple[int, int]) -> bool:
    """Teleport the acting unit towards the bees.

    In the 变身术 aim mode the cell cursor starts on the acting unit, so the
    driver learns the unit's cell from the cursor instead of guessing it.
    """
    if not open_jutsu(battle, menu):
        return False
    if not pick_jutsu(battle, JUTSU_TELEPORT):
        back_out(battle)
        return False
    origin = battle.cursor()
    for cell in teleport_candidates(battle, origin):
        battle.set_cursor(*cell)
        battle.press("A", settle=120, tag="teleport-dest")
        if not battle.confirm_dialog():
            battle.press("B", settle=100, tag="dismiss-error")
            continue
        battle.press("A", settle=120, tag="teleport-confirm")
        # The teleport animation needs ~400 frames before the unit stands on
        # the destination cell (measured: +210 frames still at the origin).
        battle.probe.frames(600, 0)
        landed = battle.unit_at(cell)
        battle.record("teleported", origin=origin, cell=cell,
                      landed=landed is not None)
        if landed is not None:
            return True
    return False


def move_candidates(battle: battle_module.Battle,
                    origin: tuple[int, int]) -> list[tuple[int, int]]:
    """Cells to try as a move destination, closest to the bees first."""
    hp = battle.hp()
    bees = [battle.unit(slot) for slot in battle_module.BEE_SLOTS
            if hp[slot - 1] > 0 and battle.unit(slot) is not None]
    if not bees:
        return []
    out: list[tuple[int, int]] = []
    for bee in bees:
        dx = bee["x"] - origin[0]
        dy = bee["y"] - origin[1]
        for step in (3, 2, 1):
            if dx != 0:
                out.append((origin[0] + (step if dx > 0 else -step), origin[1]))
            if dy != 0:
                out.append((origin[0], origin[1] + (step if dy > 0 else -step)))
    seen: set[tuple[int, int]] = set()
    unique: list[tuple[int, int]] = []
    for cell in out:
        if cell in seen or cell == origin:
            continue
        if not (0 <= cell[0] <= 15 and 0 <= cell[1] <= 15):
            continue
        seen.add(cell)
        unique.append(cell)
    return unique


def do_move_and_attack(battle: battle_module.Battle, menu: str) -> bool:
    """Walk the unit towards the bees and attack in the same action.

    移動 is the first entry of the action menu and it does **not** end the
    action: after the move the game shows the compact menu (术・忍具 /
    行動結束), so the unit can still use a jutsu.  The move phase is
    forgiving -- an illegal destination only shows an error, the phase stays
    open and another cell can be picked.
    """
    hp_before = battle.hp()
    if not battle.select_menu_item(MENU_ITEM_MOVE):
        return False
    battle.press("A", settle=120, tag="open-move")
    origin = battle.cursor()
    for cell in move_candidates(battle, origin):
        battle.set_cursor(*cell)
        battle.press("A", settle=120, tag="move-dest")
        # A successful move opens the compact menu; an illegal destination
        # keeps the move phase open (the unit does not move).
        if battle.menu() == "action2":
            battle.record("moved", origin=origin, cell=cell)
            break
    menu2 = battle.menu()
    if menu2 not in ("action2", "action5"):
        return False
    if not open_jutsu(battle, menu2):
        return False
    if not pick_jutsu(battle, JUTSU_SHURIKEN):
        back_out(battle)
        return False
    origin2 = battle.cursor()
    targets = reachable_bees(battle, origin2)
    battle.record("aim-origin", origin=origin2, targets=len(targets))
    for bee in targets:
        battle.set_cursor(bee["x"], bee["y"])
        battle.press("A", settle=150, tag="fire")
        # the damage forecast appears first, the yes/no dialog after one more A
        for _ in range(3):
            if battle.confirm_dialog():
                break
            battle.press("A", settle=120, tag="forecast")
        if not battle.confirm_dialog():
            battle.press("B", settle=100, tag="dismiss-error")
            continue
        battle.press("A", settle=150, tag="confirm-fire")
        for _ in range(6):
            battle.press("A", settle=180, tag="resolve")
        if battle.hp() != hp_before:
            battle.record("attacked", slot=bee["slot"], hp=battle.hp())
            return True
        break
    back_out(battle)
    return False


def play(battle: battle_module.Battle, max_turns: int = 200) -> dict:
    """Run the battle until every bee is dead (or the turn budget runs out)."""
    stats = {"turns": 0, "attacks": 0, "hits": 0, "teleports": 0,
             "victory": False, "kills": 0}
    battle.record("start", hp=battle.hp())

    while stats["turns"] < max_turns:
        stats["turns"] += 1
        alive = battle.alive_bees()
        if not alive:
            stats["victory"] = True
            break

        # ---- 1. wait for the action menu of the next ally ---------------
        # The cell cursor rests on the acting unit while the game asks for
        # its move, so the last sample before the menu opens is the actor's
        # cell.  (The acting flag at +0xC1 is only set during that prompt.)
        menu = "none"
        origin = battle.cursor()
        for attempt in range(70):
            menu = battle.menu()
            if menu in ("action5", "action2"):
                break
            origin = battle.cursor()
            # The intro dialogue needs ~21 A presses before the first action
            # menu appears, so B is only used as a last resort.
            if attempt >= 45:
                battle.press("B", settle=90, tag="escape")
            else:
                battle.press("A", settle=60)
        if menu not in ("action5", "action2"):
            battle.record("stuck", menu=menu, origin=origin)
            for _ in range(6):
                battle.press("B", settle=120, tag="escape")
            for _ in range(6):
                battle.press("A", settle=120, tag="escape-a")
            continue
        battle.record("actor", origin=origin)

        # ---- 2. attack a bee, otherwise close the distance ---------------
        # 移動 does not end the action, so the driver walks the unit into
        # range first and then fires the cross shuriken in the same turn.
        hp_before = battle.hp()
        stats["attacks"] += 1
        hit = do_move_and_attack(battle, menu)
        if hit:
            stats["hits"] += 1
        else:
            current = battle.menu()
            if current in ("action5", "action2"):
                if not do_teleport(battle, current, battle.cursor()):
                    current = battle.menu()
                    end_action(battle, current if current in ("action5", "action2")
                               else menu)
        stats["kills"] = len([slot for slot in battle_module.BEE_SLOTS
                               if battle.hp()[slot - 1] == 0])

        # ---- 3. resolve the action --------------------------------------
        for _ in range(14):
            if battle.menu() in ("action5", "action2"):
                break
            battle.press("A", settle=180, tag="resolve")
        battle.record("after-turn", hp=battle.hp())

    battle.record("end", hp=battle.hp(), stats=stats)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--exe", default=str(DEFAULT_EXE))
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--settle", type=int, default=45)
    parser.add_argument("--no-frames", action="store_true",
                        help="do not write PNG frames")
    parser.add_argument("--capture-each", action="store_true",
                        help="write a PNG frame after every key press")
    parser.add_argument("--log-menu", action="store_true",
                        help="record the screen classification with every press")
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = None if args.no_frames else out_dir / "frames"
    log: list = []

    with probe_module.Probe(args.rom, exe=args.exe) as probe:
        probe.load(args.state)
        battle = battle_module.Battle(probe, settle=args.settle,
                                      shot_dir=frames_dir,
                                      screen_path=out_dir / "screen.png",
                                      log=log)
        battle.capture_each = args.capture_each
        battle.log_menu = args.log_menu
        stats = play(battle, max_turns=args.max_turns)
        final_hp = battle.hp()
        final_units = battle.pool()

    receipt = {
        "schema": "konoha.s49-victory-play.v1",
        "rom": str(args.rom),
        "rom_sha256": s49_state.file_sha256(args.rom),
        "start_state": str(args.state),
        "start_state_sha256": s49_state.file_sha256(args.state),
        "stats": stats,
        "final_hp": final_hp,
        "final_units": final_units,
        "log": log,
    }
    (out_dir / "play.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({"stats": stats, "hp": final_hp}, ensure_ascii=False))
    return 0 if stats["victory"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
