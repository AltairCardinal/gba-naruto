import unittest
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIRECTORY = (
    ROOT
    / "artifacts/original-s49-postlevel-sequence-20260730-347"
)
REFERENCE_FRAMES = tuple(
    REFERENCE_DIRECTORY / f"step-{step:02d}-A.png"
    for step in range(1, 7)
)


class ButanoBattleTrainingOriginalUiTest(unittest.TestCase):
    def test_training_layers_recompose_all_six_original_pages(self):
        from tools.butano.generate_battle_ui_assets import (
            _training_panel_pixels,
            _training_text_pixels,
            recompose_training_frame,
        )

        self.assertEqual(len(_training_panel_pixels()), 256 * 256)
        for page, reference_path in enumerate(REFERENCE_FRAMES):
            with self.subTest(page=page):
                self.assertEqual(
                    len(_training_text_pixels(page)),
                    256 * 256,
                )
                expected = Image.open(reference_path).convert("RGB")
                actual = recompose_training_frame(page)
                self.assertIsNone(
                    ImageChops.difference(expected, actual).getbbox()
                )

    def test_runtime_projects_training_page_as_original_bg_layers(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        controller = (
            ROOT
            / "butano-sequel/game/include/konoha/battle_scene_controller.h"
        ).read_text(encoding="utf-8")
        telemetry_header = (
            ROOT
            / "butano-sequel/game/include/konoha/battle_runtime_scene.h"
        ).read_text(encoding="utf-8")

        for token in (
            "battle_ui_training_panel",
            "battle_ui_training_text_0",
            "battle_ui_training_text_1",
            "battle_ui_training_text_2",
            "battle_ui_training_text_3",
            "battle_ui_training_text_4",
            "battle_ui_training_text_5",
            "_add_training_ui(state)",
            "state.training_detail_page",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        for token in (
            "training_detail_page",
            "_advance_training_summary()",
        ):
            with self.subTest(token=token):
                self.assertIn(token, controller)
        self.assertIn(
            "std::uint32_t training_detail_page",
            telemetry_header,
        )
        self.assertIn(
            "output.training_detail_page",
            source,
        )


if __name__ == "__main__":
    unittest.main()
