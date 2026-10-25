#!/usr/bin/env python3
"""Deterministic driver that plays the original S49 battle 14 to a decision.

The driver plays the *original* ROM (``rom/base.gba``) from the battle-14
entry savestate.  It only ever reads the live game state (EWRAM) and the
rendered screen, so every decision is content-based -- never frame-index
based.

Battle UI facts (all measured on this machine, see notes/s49-fidelity/K-original-victory.md):

* action menu (5 items, vertical, left edge)  移動 / 术・忍具 / 查克拉 / 休息 / 行動結束
* 术・忍具 opens the jutsu list (4 items)       变身术 / 影分身术 / 忍者组合拳 / 十字手里剑
* 十字手里剑: 攻击力 6x3, 距离 3 直, 范围 1, 成功率 90% -- it kills a 25 HP bee in one hit
* the aim cursor is a free cell cursor; the target has to sit within 3 cells
  in a straight line of the acting unit, otherwise the game answers
  「请把对方设置在范围内」 / 「请指明射范围」
* the acting unit may be moved first (移動) and can still use a jutsu afterwards

EWRAM landmarks used by the driver:

======  ==========================================================
0x0200A8BA  menu cursor index (shared by the action and jutsu menus)
0x02026A8C  menu level: 3 = action menu, 4 = jutsu list / aim mode
0x02026A78  aim / move cursor x
0x02026A79  aim / move cursor y
0x02026A7A  cursor-active flag
0x020240C0  unit pool (stride 0x1D4, x=+0xC4, y=+0xC5, acting=+0xC1)
0x020242A0  HP array (stride 0x1D4, one byte per unit slot)
======  ==========================================================

Screen classification uses stable pixel signatures of the menu boxes
(the menus are static text, so the signature is constant):

* action menu (5 items): 631 dark text pixels in the box region
* compact menu (2 items): 304 dark text pixels
* jutsu list:             953 dark text pixels
* everything else:          0
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

import probe as probe_module  # noqa: E402
import s49_state  # noqa: E402

DEFAULT_EXE = pathlib.Path(__file__).resolve().parents[2] / "build" / "mgba-probe" / "mgba-probe.exe"
DEFAULT_ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")

# EWRAM landmarks
ADDR_MENU_CURSOR = 0x0200A8BA
ADDR_MENU_LEVEL = 0x02026A8C
ADDR_CURSOR = 0x02026A78
ADDR_POOL = s49_state.POOL_ADDRESS
ADDR_HP = s49_state.HP_ARRAY_ADDRESS

POOL_SLOTS = 16
HP_SLOTS = 9

DARK = (57, 66, 57)
BORDER = (107, 156, 90)
FILL = (231, 247, 214)
MENU_REGION = (8, 16, 58, 133)

# jutsu list indices (变身术, 影分身术, 忍者组合拳, 十字手里剑)
JUTSU_SHURIKEN = 3
JUTSU_TELEPORT = 0
# action menu indices (移動, 术・忍具, 查克拉, 休息, 行動結束)
MENU_MOVE = 0
MENU_JUTSU = 1

BEE_SLOTS = (5, 6, 7, 8, 9)
ALLY_SLOTS = (1, 2, 3, 4)
SHURIKEN_RANGE = 3


class Battle:
    """A live battle with content-based state inspection."""

    def __init__(self, probe: probe_module.Probe, *, hold: int = 4,
                 release: int = 1, settle: int = 45, shot_dir: pathlib.Path | None = None,
                 screen_path: pathlib.Path | None = None,
                 log: list | None = None) -> None:
        self.probe = probe
        self.hold = hold
        self.release = release
        self.settle = settle
        self.shot_dir = shot_dir
        self.screen_path = screen_path or pathlib.Path("screen.png")
        self.capture_each = False
        self.log_menu = False
        self.dump_address = 0
        self.dump_length = 0
        self.dump_dir: pathlib.Path | None = None
        self.dump_predicate = None
        self.dump_active = False
        self.frame_counter = 0
        self.dump_segments: list = []
        self.log = log if log is not None else []
        self.shot_index = 0
        if shot_dir is not None:
            shot_dir.mkdir(parents=True, exist_ok=True)
        self.screen_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- input
    def press(self, key: str, settle: int | None = None, tag: str = "") -> None:
        mask = probe_module.key_mask([key])
        frames = self.settle if settle is None else settle
        if not self.dump_active and self.dump_predicate is not None:
            if self.dump_predicate():
                self.enable_dump(self.dump_address, self.dump_length,
                                 self.dump_dir)
        if self.dump_active:
            self._dump_segment(self.hold, mask)
            self._dump_segment(self.release, 0)
            self._dump_segment(frames, 0)
        else:
            self.probe.frames(self.hold, mask)
            self.probe.frames(self.release, 0)
            self.probe.frames(frames, 0)
        record = {"event": f"press {key}{(' ' + tag) if tag else ''}"}
        if self.log_menu:
            record["menu"] = self.menu()
            record["level"] = self.menu_level()
            record["mcur"] = self.menu_cursor()
            record["cursor"] = self.cursor()
        self.record(**record)
        if self.capture_each:
            self.capture(f"{key}{('-' + tag) if tag else ''}")

    def enable_dump(self, address: int, length: int, directory: pathlib.Path,
                    predicate=None) -> None:
        """Dump one memory region after every frame from now on.

        With a ``predicate`` the dump only starts once the predicate turns
        true (used for the VRAM pass, which only covers the endgame).
        """
        self.dump_address = address
        self.dump_length = length
        self.dump_dir = directory
        self.dump_predicate = predicate
        if predicate is None:
            directory.mkdir(parents=True, exist_ok=True)
            self.frame_counter = 0
            self.dump_segments = []
            self.dump_active = True

    def _dump_segment(self, frames: int, mask: int) -> None:
        if frames <= 0:
            return
        prefix = self.dump_dir / f"s{self.frame_counter:07d}"
        self.probe.framedump(frames, self.dump_address, self.dump_length, mask,
                             str(prefix))
        self.dump_segments.append({
            "prefix": prefix.name,
            "start_frame": self.frame_counter,
            "frames": frames,
        })
        self.frame_counter += frames

    def record(self, event: str, **extra) -> None:
        # No wall-clock field: the receipt has to stay byte identical between
        # two consecutive runs.
        row = {"event": event}
        row.update(extra)
        self.log.append(row)

    # ------------------------------------------------------------- state
    def hp(self) -> list[int]:
        """The HP of every pool slot.

        The HP bytes sit 0x1D4 apart, so they are read one by one: a single
        dump of the whole array (4212 bytes) makes the mGBA CLI debugger die
        with a broken pipe.
        """
        out = []
        for index in range(HP_SLOTS):
            blob = self.probe.dump(ADDR_HP + index * s49_state.HP_STRIDE, 1)
            out.append(blob[0])
        return out

    def pool(self) -> list[dict]:
        blob = self.probe.dump(ADDR_POOL, s49_state.POOL_STRIDE * POOL_SLOTS)
        units = []
        for slot in range(1, POOL_SLOTS + 1):
            record = blob[slot * s49_state.POOL_STRIDE:(slot + 1) * s49_state.POOL_STRIDE]
            if not any(record):
                continue
            units.append({
                "slot": slot,
                "x": record[0xC4],
                "y": record[0xC5],
                "acting": bool(record[0xC1]),
                "side": record[0xCC],
            })
        return units

    def pool_current(self) -> list[dict]:
        """Units with their **live** position.

        Measured on this machine (stream M): the pool's x/y at +0xC4/+0xC5 is
        the position the unit had when the turn started, the live position is
        at +0xC7/+0xC8.  A confirmed move only rewrites +0xC7/+0xC8, so a
        driver that watches +0xC4/+0xC5 never notices that the unit walked.

        The pool is read in small pieces (12 bytes per slot): a single dump
        of the whole pool (7488 bytes) makes the mGBA CLI debugger die with
        a broken pipe after a few hundred reads.
        """
        units = []
        for slot in range(1, POOL_SLOTS + 1):
            base = ADDR_POOL + slot * s49_state.POOL_STRIDE
            blob = self.probe.dump(base + 0xC1, 12)
            if not any(blob):
                continue
            units.append({
                "slot": slot,
                "x": blob[0xC7 - 0xC1],
                "y": blob[0xC8 - 0xC1],
                "start_x": blob[0xC4 - 0xC1],
                "start_y": blob[0xC5 - 0xC1],
                "acting": bool(blob[0]),
                "side": blob[0xCC - 0xC1],
            })
        return units

    def position(self, slot: int) -> tuple[int, int] | None:
        """The live cell of a pool slot."""
        for entry in self.pool_current():
            if entry["slot"] == slot:
                return entry["x"], entry["y"]
        return None

    def cursor(self) -> tuple[int, int]:
        blob = self.probe.dump(ADDR_CURSOR, 3)
        return blob[0], blob[1]

    def menu_level(self) -> int:
        return self.probe.dump(ADDR_MENU_LEVEL, 1)[0]

    def menu_cursor(self) -> int:
        return self.probe.dump(ADDR_MENU_CURSOR, 1)[0]

    def menu_cursor(self) -> int:
        """Index of the highlighted entry of the open menu (0 based)."""
        return self.probe.dump(ADDR_MENU_CURSOR, 1)[0]

    def select_menu_item(self, index: int, limit: int = 8) -> bool:
        """Move the menu cursor onto ``index`` with D-pad presses."""
        for _ in range(limit):
            current = self.menu_cursor()
            if current == index:
                return True
            if current < index:
                self.press("Down", tag="menu")
            else:
                self.press("Up", tag="menu")
        return self.menu_cursor() == index

    def screen(self) -> "PIL.Image.Image":
        """The rendered frame.

        Two screenshots are taken: a probe command advances the emulated game
        by a frame, so the *second* screenshot is the frame that belongs to
        the current state.  With only one screenshot the classification was
        one frame behind and missed the menus that appear right after a key
        press.
        """
        from PIL import Image
        self.probe.shot(self.screen_path)
        self.probe.shot(self.screen_path)
        return Image.open(self.screen_path).convert("RGB")

    def confirm_dialog(self) -> bool:
        """True when the 「可以嗎？」 yes/no dialog is on screen.

        The yes/no dialog is a narrow light box at (87..152, 31..80); the
        error messages are wide boxes that start at y=71, so the region below
        keeps the two apart.
        """
        image = self.screen()
        region = image.crop((86, 30, 154, 72))
        light = sum(1 for pixel in region.get_flattened_data() if pixel == FILL)
        return light > 500

    def menu(self) -> str:
        """Classify the screen: none / action5 / action2 / jutsu.

        The menu boxes are static text, so their pixel signature is constant:

        =========  =====  =====  =====
        screen      dark   fill  border
        =========  =====  =====  =====
        action5      631   1550      94
        action2      304    548      37
        jutsu     685..953    -        8
        other         0      -       0-4
        =========  =====  =====  =====

        ``border`` counts the rows of the box frame in the column x=8; that
        column is the reliable discriminator, because a dialogue box overlaps
        the text region but never draws a frame there.

        The jutsu list is recognised by the game's own menu level register
        (0x02026A8C == 4) *and* by the light info panel on the right of the
        screen: its text pixel count varies with the highlighted jutsu
        (685..953), which makes a pure pixel threshold unreliable.

        The level register has to be read **before** the screenshot: reading
        memory advances the emulated frame by one, so a screenshot taken
        first would classify the *previous* frame (which is how a jutsu list
        that is already on screen got classified as an 「行動終了」 menu, and
        how the driver kept pressing A inside the jutsu list).
        """
        level = self.menu_level()
        image = self.screen()
        region = image.crop(MENU_REGION)
        dark = sum(1 for pixel in region.get_flattened_data() if pixel == DARK)
        border = sum(1 for y in range(16, 134)
                     if image.getpixel((8, y)) == BORDER)
        if level == 4:
            panel = image.crop((170, 20, 240, 130))
            light = sum(1 for pixel in panel.get_flattened_data() if pixel == FILL)
            if light > 1500:
                return "jutsu"
            # after a jutsu the game keeps the jutsu level (4) for the rest
            # of the action, so the menu box itself has to be measured
            if border >= 70:
                return "action5"
            if border >= 25 and light < 200:
                return "action2"
            return "none"
        if border >= 70:
            return "action5"
        if border >= 25:
            return "action2"
        if dark >= 800:
            return "jutsu"
        return "none"

    # ------------------------------------------------------------ helpers
    def alive_bees(self) -> list[int]:
        hp = self.hp()
        return [slot for slot in BEE_SLOTS if hp[slot - 1] > 0]

    def unit(self, slot: int) -> dict | None:
        for entry in self.pool_current():
            if entry["slot"] == slot:
                return entry
        return None

    def acting_ally(self) -> dict | None:
        """The ally the game is currently waiting for (acting flag at +0xC1)."""
        for entry in self.pool_current():
            if entry["acting"] and entry["side"] == 0:
                return entry
        return None

    def unit_at(self, cell: tuple[int, int]) -> dict | None:
        """The unit standing on the given cell."""
        for entry in self.pool_current():
            if (entry["x"], entry["y"]) == cell:
                return entry
        return None

    def set_cursor(self, x: int, y: int) -> None:
        """Walk the cell cursor to (x, y) with D-pad presses."""
        cx, cy = self.cursor()
        if cx > x:
            for _ in range(cx - x):
                self.press("Left")
        elif cx < x:
            for _ in range(x - cx):
                self.press("Right")
        cx, cy = self.cursor()
        if cy > y:
            for _ in range(cy - y):
                self.press("Up")
        elif cy < y:
            for _ in range(y - cy):
                self.press("Down")

    def capture(self, label: str) -> str | None:
        if self.shot_dir is None:
            return None
        self.shot_index += 1
        path = self.shot_dir / f"{self.frame_counter:07d}-{self.shot_index:05d}-{label}.png"
        self.probe.shot(path)
        return str(path)
