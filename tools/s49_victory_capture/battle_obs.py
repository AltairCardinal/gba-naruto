#!/usr/bin/env python3
"""Frame-exact observation of the original ROM's battle.

Why this module exists
----------------------
Stream M's driver lost the state machine after the second unit's move and
blamed it on "every probe command advances the emulated game by one frame".
Experiment W3-E1 (notes/s49-fidelity/W3-original-truth.md) measured that
this is **false**:

* ``frames`` / ``run`` / ``framedump`` / ``keyseq`` advance the frame,
* ``dump`` / ``shot`` / ``rawshot`` do **not**.

So a register read and a screenshot taken back to back describe the *same*
frame, and the picture can never be stale.  What was wrong in stream M was the
*menu classifier*, not the timing.

The observer therefore does three things:

1. takes the picture with ``rawshot`` (the core's video buffer, lossless and
   much faster than mGBA's PNG writer),
2. reads the game's own state registers,
3. classifies the screen with pixel signatures that were measured on this
   machine (see ``measure_frames.py``).

EWRAM landmarks
---------------
============================  ===========================================
0x0200A8BA                   menu cursor index
0x02026A78 / 79 / 7A         aim / move cursor x / y / active flag
0x02026A8C                   menu level (3 = action, 4 = jutsu)
0x020240C0 + slot*0x1D4      unit record
    +0x0C                     HP
    +0xC1                     acting flag
    +0xC4 / +0xC5             position at the start of the turn
    +0xC7 / +0xC8             live position
    +0xCC                     affiliation (0 = player, 1 = enemy)
============================  ===========================================
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

import probe as probe_module
import s49_state

ADDR_MENU_CURSOR = 0x0200A8BA
ADDR_CURSOR = 0x02026A78
ADDR_MENU_LEVEL = 0x02026A8C

POOL_ADDRESS = s49_state.POOL_ADDRESS
POOL_STRIDE = s49_state.POOL_STRIDE

RAW_WIDTH = 240
RAW_HEIGHT = 160

# palette entries of the original's battle UI (measured on this machine)
DARK = (57, 66, 57)        # menu text
BORDER = (107, 156, 90)    # menu box frame
FILL = (231, 247, 214)     # menu box interior / dialogue box

MENU_REGION = (8, 16, 58, 133)      # the left hand menu box
INFO_PANEL = (170, 20, 240, 130)    # the jutsu list's info panel
# The battle HUD bar sits in rows 135..152 and is on *every* battle screen, so
# a dialogue box has to be measured above it: the original's story box starts
# at row 103 and reaches row 152.
DIALOGUE_REGION = (7, 100, 232, 134)
ERROR_REGION = (40, 45, 200, 100)
CONFIRM_REGION = (86, 30, 154, 72)

BEE_SLOTS = (5, 6, 7, 8, 9)
ALLY_SLOTS = (1, 2, 3, 4)

# the jutsu list of Naruto / Sasuke: 变身术 / 影分身术 / 忍者组合拳 / 十字手里剑
JUTSU_SHURIKEN = 3
# the action menu: 移動 / 术・忍具 / 查克拉 / 休息 / 行動終了
MENU_ITEM_MOVE = 0
MENU_ITEM_JUTSU = 1
MENU_ITEM_END = 4
COMPACT_ITEM_JUTSU = 0
COMPACT_ITEM_END = 1


def count_colour(image, region, colour) -> int:
    box = image.crop(region)
    return sum(1 for pixel in box.get_flattened_data() if pixel == colour)


def signature(image) -> dict:
    """The pixel measurements the classifier is built on."""
    border_rows = sum(1 for y in range(16, 134)
                      if image.getpixel((8, y)) == BORDER)
    # The move phase paints the reachable set in a cyan hatch that no other
    # screen uses (measured: 5231..6649 px in the move phase, 0 everywhere
    # else), so it is the reliable way to tell the move phase apart from the
    # unit selection phase.
    hatch = 0
    path = 0
    for pixel in image.get_flattened_data():
        red, green, blue = pixel
        if red <= 140 and green >= 230 and blue >= 180:
            hatch += 1
        # the orange path / attack range preview (255,143,30) and its shades
        if red >= 240 and 120 <= green <= 175 and blue <= 50:
            path += 1
    return {
        "border_rows": border_rows,
        "menu_dark": count_colour(image, MENU_REGION, DARK),
        "panel_light": count_colour(image, INFO_PANEL, FILL),
        "dialogue_light": count_colour(image, DIALOGUE_REGION, FILL),
        "error_light": count_colour(image, ERROR_REGION, FILL),
        "confirm_light": count_colour(image, CONFIRM_REGION, FILL),
        "hatch": hatch,
        "path": path,
    }


def is_jutsu_list(sig: dict, level: int) -> bool:
    """True for the real jutsu list screen.

    The list has the light info panel and it lives on the **jutsu layer**
    (level 4).  The fire style of Sasuke opens a *different* screen that also
    has a light panel (its target screen with its own confirm box) but on the
    action layer (level 3).
    """
    return sig["panel_light"] > 3000 and level == 4


def classify(image, level: int, cursor_active: bool = False) -> str:
    """Name the screen.

    ``action5``  the five entry action menu
    ``action2``  the compact menu (術·忍具 / 行動終了) after a move
    ``jutsu``    the jutsu list (with its light info panel)
    ``target``   a jutsu's target screen that is not the list (火遁术)
    ``move``     the move phase (the reachable set is painted)
    ``aim``      the aim / target cursor mode (the range preview is painted)
    ``dialogue`` a story or result message box at the bottom
    ``none``     nothing of the above is on screen
    """
    sig = signature(image)
    if is_jutsu_list(sig, level):
        return "jutsu"
    if sig["panel_light"] > 3000:
        return "target"
    if sig["border_rows"] >= 70:
        return "action5"
    if sig["border_rows"] >= 25:
        return "action2"
    if sig["dialogue_light"] > 3000:
        return "dialogue"
    if sig["hatch"] > 1000:
        return "move"
    if sig["path"] > 200:
        return "aim"
    if sig["menu_dark"] >= 800:
        return "jutsu"
    # NOTE: the cursor-active flag alone is **not** the aim mode: the unit
    # selection phase also has an active cursor.  Only the orange range
    # preview tells the two apart.
    return "none"


@dataclass
class Observation:
    image: object
    level: int
    menu_cursor: int
    cursor: tuple
    units: list
    sig: dict
    menu: str
    extra: dict = field(default_factory=dict)

    def unit(self, slot: int):
        for entry in self.units:
            if entry["slot"] == slot:
                return entry
        return None

    def position(self, slot: int):
        entry = self.unit(slot)
        return None if entry is None else (entry["x"], entry["y"])

    def hp(self, slot: int) -> int:
        entry = self.unit(slot)
        return 0 if entry is None else entry["hp"]

    def hp_list(self) -> list:
        return [self.hp(slot) for slot in range(1, 10)]

    def acting_ally(self):
        for entry in self.units:
            if entry["acting"] and entry["side"] == 0:
                return entry
        return None

    def allies(self) -> list:
        return [entry for entry in self.units if entry["side"] == 0]

    def bees(self) -> list:
        return [entry for entry in self.units
                if entry["side"] == 1 and entry["hp"] > 0]


class BattleObserver:
    """Reads the live battle state and the rendered frame of the same frame."""

    def __init__(self, probe: probe_module.Probe, *, raw_path: pathlib.Path | None = None,
                 slots: int = 9) -> None:
        self.probe = probe
        self.raw_path = raw_path or pathlib.Path("frame.raw")
        self.slots = slots
        self.frame_index = 0

    # --------------------------------------------------------------- input
    def press(self, key: str, settle: int = 45, hold: int = 4, release: int = 1) -> None:
        mask = probe_module.key_mask([key])
        self.probe.frames(hold, mask)
        self.probe.frames(release, 0)
        if settle:
            self.probe.frames(settle, 0)

    def run(self, frames: int) -> None:
        if frames:
            self.probe.frames(frames, 0)

    # -------------------------------------------------------------- observe
    def observe(self) -> Observation:
        """The state and the picture of **one** frame.

        The order does not matter for the correctness (no command but
        ``frames`` advances the emulation), but the picture is taken first so
        that the returned image and the returned registers describe the same
        frame.
        """
        from PIL import Image
        self.probe.run(f"rawshot {self.raw_path}")
        raw = self.raw_path.read_bytes()
        image = Image.frombytes("RGBA", (RAW_WIDTH, RAW_HEIGHT),
                                raw).convert("RGB")
        level = self.probe.dump(ADDR_MENU_LEVEL, 1)[0]
        menu_cursor = self.probe.dump(ADDR_MENU_CURSOR, 1)[0]
        cursor = self.probe.dump(ADDR_CURSOR, 3)
        units = []
        for slot in range(1, self.slots + 1):
            base = POOL_ADDRESS + slot * POOL_STRIDE
            # the HP byte sits at record+0x0C, the flags and the coordinates
            # at record+0xC1..record+0xCC -- two small reads, because a large
            # dump makes the mGBA CLI debugger die (measured: 7488 bytes does,
            # 13 bytes does not)
            hp = self.probe.dump(base + 0x0C, 1)[0]
            blob = self.probe.dump(base + 0xC0, 13)
            if not any(blob) and hp == 0:
                continue
            units.append({
                "slot": slot,
                "hp": hp,
                "acting": bool(blob[0xC1 - 0xC0]),
                "start_x": blob[0xC4 - 0xC0],
                "start_y": blob[0xC5 - 0xC0],
                "x": blob[0xC7 - 0xC0],
                "y": blob[0xC8 - 0xC0],
                "side": blob[0xCC - 0xC0],
            })
        sig = signature(image)
        return Observation(image=image, level=level, menu_cursor=menu_cursor,
                           cursor=(cursor[0], cursor[1], cursor[2]),
                           units=units, sig=sig,
                           menu=classify(image, level, bool(cursor[2])))

    # --------------------------------------------------------------- menus
    def move_cursor_to(self, observation: Observation, cell) -> None:
        """Walk the cell cursor to ``cell`` with D-pad presses."""
        cx, cy = observation.cursor[0], observation.cursor[1]
        if cx > cell[0]:
            self.press("Left", settle=8, hold=4)
            cx -= 1
        elif cx < cell[0]:
            self.press("Right", settle=8, hold=4)
            cx += 1
        if cy > cell[1]:
            self.press("Up", settle=8, hold=4)
            cy -= 1
        elif cy < cell[1]:
            self.press("Down", settle=8, hold=4)
            cy += 1
        while cx != cell[0]:
            key = "Left" if cx > cell[0] else "Right"
            self.press(key, settle=8, hold=4)
            cx += -1 if key == "Left" else 1
        while cy != cell[1]:
            key = "Up" if cy > cell[1] else "Down"
            self.press(key, settle=8, hold=4)
            cy += -1 if key == "Up" else 1

    def select_menu_item(self, observation: Observation, index: int,
                         limit: int = 8) -> bool:
        """Put the menu cursor on ``index`` (0 based)."""
        for _ in range(limit):
            current = self.observe().menu_cursor
            if current == index:
                return True
            self.press("Down" if current < index else "Up", settle=10, hold=4)
        return self.observe().menu_cursor == index
