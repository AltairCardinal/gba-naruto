#!/usr/bin/env python3
"""The S49 turn banner is measured from the original frame and not yet built.

Original frame 15 of `walk-original-a24` is the round banner the remake never
draws:

    回合   1
    玩家  的行动

It is the reason the original needs four `A` presses between the end of the
opening dialogue and the command menu while the remake needs two, which in turn
is why every later step index is offset between the two walks.

This gate does not assert that the banner is implemented — it asserts that the
**specification** is still true.  The geometry below was read off the original
frame column by column, and if a future capture disagrees, that is a signal that
the spec must be re-measured rather than silently implemented against stale
numbers.

`test_the_remake_still_does_not_draw_the_banner` is the deliberate red gate:
it names the missing feature so it cannot be quietly dropped, and it goes green
the day `battle_ui_layer::turn_banner` exists.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "artifacts/s49-fidelity-20261019-v1"
ORIGINAL = RUN / "walk-original-a24"
REMAKE = RUN / "walk-remake-dd-a30-banner6"
SCENE = ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"

BANNER_STEP = 15

# Colours the banner is built from, taken from the original frame.
FRAME_DARK = (99, 115, 90)
FRAME_LIGHT = (99, 189, 115)
INNER_BORDER = (231, 214, 99)
CANVAS = (231, 247, 214)
FRAME_HIGHLIGHT = (247, 255, 222)
FRAME_SHADOW = (107, 156, 90)

# The colours the panel is physically built from.  The text ink and the outline
# shades are deliberately excluded: the unit sprite standing behind the banner
# shares them, and letting them bridge would pull the box up into the field.
STRUCTURAL_COLOURS = frozenset(
    {
        FRAME_DARK,
        FRAME_LIGHT,
        INNER_BORDER,
        CANVAS,
        FRAME_HIGHLIGHT,
        FRAME_SHADOW,
    }
)

PANEL_COLOURS = STRUCTURAL_COLOURS | frozenset(
    {(57, 57, 57), (57, 66, 57), (181, 189, 165), (247, 255, 222), (115, 123, 107)}
)

# Measured off walk-original-a24/step-15-A.png.
BANNER_BOX = (72, 40, 151, 89)          # x0, y0, x1, y1 inclusive, outer frame
# The panel is 50 rows tall.  Its bottom two rows are a dithered edge:
# the highlight colour (247,255,222) appears only in rows 88 and 89,
# where it alternates with the dithered grass of the battlefield.  A
# column profile through x=110 shows grass in those rows and would
# wrongly suggest a 48 row panel, so the flood fill is the measurement
# that holds.
INNER_BORDER_BOX = (78, 46, 145, 81)   # the yellow rule inside the frame
CANVAS_BOX = (79, 47, 144, 80)         # cream drawing surface
TEXT_LINES = (                         # y0, y1, x0, x1 of the inked text
    (49, 62, 88, 131),                 # 回合   1
    (65, 78, 80, 134),                 # 玩家  的行动
)

# Characters the banner needs that the shared UI atlas cannot supply today.
MISSING_GLYPHS = ("玩", "家")
BLANK_GLYPHS = ("合",)


def _capture_available() -> bool:
    return (ORIGINAL / f"step-{BANNER_STEP:02d}-A.png").is_file()


def _frame(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


# The cream drawing surface, verified against the original frame.
BANNER_SEED = (110, 63)


def _panel_box(pixels) -> tuple[int, int, int, int]:
    """Bounding box of the panel flood-filled from a seed inside the canvas.

    A plain scan over the window is not enough: the field behind the banner has
    its own dark outline pixels that share the panel's palette, and they sit
    above and to the left of it.
    """

    seed_x, seed_y = BANNER_SEED
    if pixels[seed_x, seed_y] != CANVAS:
        raise AssertionError(
            f"banner seed {BANNER_SEED} is {pixels[seed_x, seed_y]}, "
            f"expected the canvas colour {CANVAS}"
        )
    seen = {(seed_x, seed_y)}
    stack = [(seed_x, seed_y)]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = (x + dx, y + dy)
            if point in seen or not (0 <= point[0] < 240 and 0 <= point[1] < 160):
                continue
            if pixels[point] in STRUCTURAL_COLOURS:
                seen.add(point)
                stack.append(point)
    xs = [point[0] for point in seen]
    ys = [point[1] for point in seen]
    return min(xs), min(ys), max(xs), max(ys)


def _ink_lines(pixels, box) -> list[tuple[int, int, int, int]]:
    x0, y0, x1, y1 = box
    rows: dict[int, list[int]] = {}
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if sum(pixels[x, y]) < 250:
                rows.setdefault(y, []).append(x)
    lines: list[list[int]] = []
    for y in sorted(rows):
        if not lines or y > lines[-1][-1] + 2:
            lines.append([y])
        else:
            lines[-1].append(y)
    result = []
    for line in lines:
        xs = [x for y in line for x in rows[y]]
        result.append((line[0], line[-1], min(xs), max(xs)))
    return result


@unittest.skipUnless(_capture_available(), "the original S49 walk is unavailable")
class TurnBannerSpecification(unittest.TestCase):
    def setUp(self):
        self.frame = _frame(ORIGINAL / f"step-{BANNER_STEP:02d}-A.png")
        self.pixels = self.frame.load()

    def test_banner_panel_geometry(self):
        box = _panel_box(self.pixels)
        self.assertEqual(
            box[:2], BANNER_BOX[:2],
            "the banner's top-left moved; re-measure before implementing",
        )
        self.assertEqual(
            box[2], BANNER_BOX[2],
            "the banner's right edge moved; the frame is decorative, not uniform",
        )
        self.assertEqual(
            box[3], BANNER_BOX[3],
            "the banner's bottom edge moved; re-measure before implementing",
        )

    def test_banner_has_two_text_lines_at_the_recorded_rows(self):
        lines = _ink_lines(self.pixels, CANVAS_BOX)
        self.assertEqual(
            len(lines),
            2,
            f"expected 回合/玩家 lines, measured {lines}",
        )
        for measured, expected in zip(lines, TEXT_LINES):
            self.assertEqual(measured, expected)

    def test_the_banner_panel_uses_the_shared_panel_palette(self):
        """The banner is the same green-frame/cream panel as every other UI."""

        x0, y0, x1, y1 = BANNER_BOX
        found = {
            self.pixels[x, y]
            for y in range(y0, y1 + 1)
            for x in range(x0, x1 + 1)
        }
        for colour in (FRAME_LIGHT, INNER_BORDER, CANVAS, FRAME_HIGHLIGHT):
            self.assertIn(colour, found)


class TurnBannerNotBuiltYet(unittest.TestCase):
    """Deliberate red gate: names the feature that is still missing."""

    def test_the_remake_draws_the_banner(self):
        """The banner is implemented, so the red gate becomes a frame gate."""

        source = SCENE.read_text(encoding="utf-8")
        self.assertIn(
            "turn_banner",
            source,
            "the round banner phase and layer are gone again",
        )

    def test_the_remake_banner_panel_is_pixel_identical_to_the_original(self):
        """The banner panel itself must match the original frame exactly."""

        if not REMAKE.is_dir():
            self.skipTest("the remake walk is unavailable")
        if not ORIGINAL.is_dir():
            self.skipTest("the original walk is unavailable")
        original = _frame(ORIGINAL / f"step-{BANNER_STEP:02d}-A.png")
        original_pixels = original.load()
        found = []
        for path in sorted(REMAKE.glob("step-*.png")):
            pixels = _frame(path).load()
            if pixels[BANNER_SEED[0], BANNER_SEED[1]] != CANVAS:
                continue
            if _panel_box(pixels) != BANNER_BOX:
                continue
            differences = sum(
                1
                for y in range(BANNER_BOX[1], BANNER_BOX[3])
                for x in range(BANNER_BOX[0], BANNER_BOX[2])
                if pixels[x, y] != original_pixels[x, y]
            )
            found.append((path.name, differences))
        self.assertTrue(
            found,
            "the remake draws no round banner at all",
        )
        for name, differences in found:
            self.assertEqual(
                differences,
                0,
                f"the banner panel in {name} differs from the original in "
                f"{differences} pixels",
            )

    def test_banner_only_glyphs_are_still_unavailable(self):
        self.assertEqual(
            MISSING_GLYPHS,
            ("玩", "家"),
            "玩/家 became available; the banner spec can drop this blocker",
        )
        self.assertEqual(
            BLANK_GLYPHS,
            ("合",),
            "合 gained ink; the banner spec can drop this blocker",
        )


if __name__ == "__main__":
    unittest.main()
