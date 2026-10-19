import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_FRAMES = {
    (1, 0): (
        ROOT
        / "artifacts/original-s49-result-advance-20260730-326"
        / "step-01-A.png"
    ),
    (1, 1): (
        ROOT
        / "artifacts/original-s49-levelup-advance-20260730-345"
        / "step-01-A.png"
    ),
    (2, 0): (
        ROOT
        / "artifacts/original-s49-levelup-sequence-20260730-346"
        / "step-01-A.png"
    ),
    (2, 1): (
        ROOT
        / "artifacts/original-s49-levelup-sequence-20260730-346"
        / "step-02-A.png"
    ),
    (3, 0): (
        ROOT
        / "artifacts/original-s49-levelup-sequence-20260730-346"
        / "step-03-A.png"
    ),
    (3, 1): (
        ROOT
        / "artifacts/original-s49-levelup-sequence-20260730-346"
        / "step-04-A.png"
    ),
}


class ButanoBattleLevelUpOriginalUiTest(unittest.TestCase):
    def test_level_up_assets_recompose_all_six_original_pages(self):
        from tools.butano.generate_battle_ui_assets import (
            _level_up_panel_pixels,
            _level_up_portrait_component_pixels,
            _level_up_title_pixels,
            _level_up_value_pixels,
            recompose_level_up_frame,
        )

        self.assertEqual(len(_level_up_panel_pixels()), 256 * 256)
        self.assertEqual(len(_level_up_title_pixels(1, 0)), 128 * 16)
        self.assertEqual(len(_level_up_value_pixels(14)), 32 * 16)
        for character_id in (1, 2, 3):
            for component_index, dimensions in enumerate(
                ((64, 64), (16, 32), (16, 32),
                 (32, 16), (32, 16), (16, 16))
            ):
                with self.subTest(
                    character_id=character_id,
                    component_index=component_index,
                ):
                    pixels = _level_up_portrait_component_pixels(
                        character_id, component_index
                    )
                    self.assertEqual(
                        len(pixels), dimensions[0] * dimensions[1]
                    )
                    self.assertGreater(sum(pixel != 0 for pixel in pixels), 0)

        for key, reference_path in REFERENCE_FRAMES.items():
            with self.subTest(character_id=key[0], detail_page=key[1]):
                expected = Image.open(reference_path).convert("RGB")
                actual = recompose_level_up_frame(*key)
                self.assertIsNone(
                    ImageChops.difference(expected, actual).getbbox()
                )

    def test_runtime_uses_original_level_up_layers_and_snapshot_page(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        controller = (
            ROOT
            / "butano-sequel/game/include/konoha/battle_scene_controller.h"
        ).read_text(encoding="utf-8")

        for token in (
            "battle_ui_level_up_panel",
            "battle_ui_level_up_title",
            "battle_ui_level_up_value",
            "battle_ui_level_up_portrait_64x64",
            "battle_ui_level_up_portrait_16x32",
            "battle_ui_level_up_portrait_32x16",
            "battle_ui_level_up_portrait_16x16",
            "battle_ui_level_up_eye",
            "_add_level_up_ui(state, result)",
            "state.level_up_detail_page",
            "result.participants[state.result_participant_index]",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        for token in (
            "level_up_detail_page",
            "_advance_level_up()",
            "participant.after.level >",
            "participant.before.level",
        ):
            with self.subTest(token=token):
                self.assertIn(token, controller)

    def test_level_up_obj_layers_share_one_8bpp_palette(self):
        from tools.butano.generate_battle_ui_assets import (
            generate_outputs,
        )

        names = (
            "title",
            "value",
            "portrait_64x64",
            "portrait_16x32",
            "portrait_32x16",
            "portrait_16x16",
            "eye",
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate_outputs(output)
            palettes = []
            for name in names:
                metadata = json.loads(
                    (
                        output
                        / f"battle_ui_level_up_{name}.json"
                    ).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    metadata.get("bpp_mode"), "bpp_8"
                )
                self.assertEqual(
                    metadata.get("colors_count"), 256
                )
                palettes.append(
                    Image.open(
                        output
                        / f"battle_ui_level_up_{name}.bmp"
                    ).getpalette()
                )
            self.assertTrue(
                all(palette == palettes[0] for palette in palettes)
            )


if __name__ == "__main__":
    unittest.main()
