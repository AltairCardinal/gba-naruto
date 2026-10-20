#!/usr/bin/env python3
"""The S49 map hint must be the original's small "SELECT詳細", not a font line.

The original draws a 39x10 pixel hint in the top right corner: a narrow
ASCII "SELECT" over 22 pixels and two 8x8 CJK cells, in the ink colour
(247,255,222) with a (57,57,57) outline.  The remake drew the same hint with
the UI font, which is 57x14 pixels wide, uses the full width ASCII and the
characters 人物, and is drawn in plain white.  The font atlases have neither
a narrow ASCII nor the two characters 詳 and 細, so the hint is cut out of
the original's own frame instead.

This gate pins the asset against that frame, pins the runtime to the sprite
instead of a text line, and pins the phases the hint appears in: the original
shows it while the player picks a unit, picks a destination and picks a
target, and hides it behind every menu.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GRAPHICS = ROOT / "butano-sequel/graphics"
PROMPT = GRAPHICS / "battle_ui_select_prompt.bmp"
PROMPT_JSON = GRAPHICS / "battle_ui_select_prompt.json"
ORIGINAL_FRAME = (
    ROOT
    / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-17-A.png"
)
SCENE = ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
UI_MODEL = ROOT / "butano-sequel/game/include/konoha/battle_ui_model.h"

INK = (247, 255, 222)
OUTLINE = (57, 57, 57)
TRANSPARENT = (198, 132, 255)
REGION_ORIGIN = (192, 12)
REGION_SIZE = (48, 16)
PIECE_SIZE = 32
PIECE_COUNT = 2

# The phases the original shows the hint in, and the ones it hides it behind.
SHOWING_PHASES = ("unit_selection", "move_selection", "target_selection")
HIDDEN_PHASES = ("command_selection", "action_selection", "enemy_turn")


class SelectPromptTest(unittest.TestCase):
    def setUp(self):
        if not ORIGINAL_FRAME.is_file():
            self.skipTest("the original walk is unavailable")

    def test_the_asset_is_cut_from_the_original_frame(self):
        if not PROMPT.is_file():
            self.fail(f"{PROMPT} is missing")
        with Image.open(PROMPT) as image:
            self.assertEqual(image.mode, "P")
            self.assertEqual(
                image.size, (PIECE_SIZE, PIECE_SIZE * PIECE_COUNT)
            )
            pixels = image.convert("RGB").load()
        original = Image.open(ORIGINAL_FRAME).convert("RGB").load()
        kept = 0
        for y in range(REGION_SIZE[1]):
            for x in range(REGION_SIZE[0]):
                piece = x // PIECE_SIZE
                colour = pixels[x % PIECE_SIZE, piece * PIECE_SIZE + y]
                source = original[REGION_ORIGIN[0] + x, REGION_ORIGIN[1] + y]
                if colour == TRANSPARENT:
                    self.assertNotEqual(
                        source,
                        INK,
                        f"the prompt ink at ({x},{y}) was cut as transparent",
                    )
                    continue
                kept += 1
                self.assertEqual(
                    colour,
                    source,
                    f"the prompt pixel ({x},{y}) does not match the original",
                )
        self.assertGreater(kept, 0, "the prompt sprite is empty")

    def test_the_sidecar_declares_a_sprite(self):
        self.assertEqual(
            json.loads(PROMPT_JSON.read_text(encoding="utf-8")),
            {"type": "sprite", "height": PIECE_SIZE},
        )

    def test_the_runtime_draws_the_sprite_not_a_text_line(self):
        source = SCENE.read_text(encoding="utf-8")
        self.assertIn(
            "battle_ui_select_prompt",
            source,
            "the runtime does not draw the prompt sprite",
        )
        self.assertNotIn(
            "SELECT人物",
            source,
            "the runtime still draws the hint with the UI font",
        )

    def test_the_hint_appears_only_while_the_player_picks_something(self):
        source = UI_MODEL.read_text(encoding="utf-8")
        for phase in SHOWING_PHASES:
            pattern = (
                r"case battle_scene_phase::" + phase + r":(?:(?!case ).)*?"
                r"show_select_prompt = true"
            )
            self.assertIsNotNone(
                re.search(pattern, source, re.S),
                f"the hint is not shown while the player is in {phase}",
            )
        for phase in HIDDEN_PHASES:
            match = re.search(
                r"case battle_scene_phase::" + phase + r":(.*?)\n    case ",
                source,
                re.S,
            )
            if not match:
                continue
            self.assertNotIn(
                "show_select_prompt = true",
                match.group(1),
                f"the hint is shown in {phase}, where the original hides it",
            )


if __name__ == "__main__":
    unittest.main()
