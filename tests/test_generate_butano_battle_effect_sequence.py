import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.butano.generate_battle_effect_sequence import (
    ACTION_05_DUST_SPEC,
    ACTION_16_FIRE_HIT_SPEC,
    NINJA_TOOL_BOMB_PROJECTILE_SPEC,
    NINJA_TOOL_BOMB_SMOKE_SPEC,
    generate,
    generate_sequence,
)


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom" / "base.gba"
TRACE = (
    ROOT
    / "build"
    / "original-action-presentation-trace-20260726-08"
)
TRACE_DUST = (
    ROOT
    / "build"
    / "original-action-presentation-trace-20260726-42-dust"
)
TRACE_FIRE = (
    ROOT
    / "build"
    / "original-fire-presentation-trace-20260726-99"
)
TRACE_BOMB = (
    ROOT
    / "build"
    / "battle-presentation-original-probes-20260727-15"
    / "tool49-component-trace"
)


class ButanoBattleEffectSequenceGeneratorTest(unittest.TestCase):
    def test_generates_bomb_projectile_and_semitransparent_smoke(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            graphics = root / "graphics"

            projectile = generate_sequence(
                ROM,
                TRACE_BOMB,
                graphics,
                root / "generated_battle_ninja_tool_bomb_projectile_content.h",
                root / "bomb-projectile.json",
                NINJA_TOOL_BOMB_PROJECTILE_SPEC,
            )
            self.assertEqual(4, len(projectile["assets"]))
            self.assertEqual(7, projectile["sequence"]["frame_count"])
            self.assertEqual(4, projectile["sequence"]["keyframe_count"])
            self.assertEqual(7, projectile["sequence"]["duration"])
            self.assertEqual(
                "20ba57e9b2eead364b30e256ec03aa1ec28b068849c47bba98972f44e68a0617",
                projectile["source_resources"]["tiles"]["sha256"],
            )

            smoke = generate_sequence(
                ROM,
                TRACE_BOMB,
                graphics,
                root / "generated_battle_ninja_tool_bomb_smoke_content.h",
                root / "bomb-smoke.json",
                NINJA_TOOL_BOMB_SMOKE_SPEC,
            )
            self.assertEqual(25, len(smoke["assets"]))
            self.assertEqual(111, smoke["sequence"]["frame_count"])
            self.assertEqual(70, smoke["sequence"]["keyframe_count"])
            self.assertEqual(111, smoke["sequence"]["duration"])
            self.assertEqual(14, smoke["sequence"]["maximum_components"])
            self.assertEqual(
                "eb9589427babaaa4d746b365cf1ea3083a5accd5cc408d53ac9c83131fb82475",
                smoke["source_resources"]["tiles"]["sha256"],
            )
            self.assertEqual(
                "70c511e326da6ce384f358d0dfe798d71dd44f181f6bcaa693e77aa456f5422e",
                smoke["source_resources"]["palette"]["sha256"],
            )
            smoke_header = (
                root
                / "generated_battle_ninja_tool_bomb_smoke_content.h"
            ).read_text(encoding="utf-8")
            self.assertIn(
                "battle_effect_component{ "
                "160, 80, 0, false, false, 2, true }",
                smoke_header,
            )
            manifest_text = (
                root / "bomb-smoke.json"
            ).read_text(encoding="utf-8")
            self.assertNotIn(".png", manifest_text.lower())
            self.assertNotIn("screenshot", manifest_text.lower())

    def test_generates_component_assets_and_typed_sequence_from_rom(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            graphics = root / "graphics"
            header = root / "generated_battle_action_05_effect_content.h"
            manifest = root / "action-05-hit-sequence.json"

            result = generate(
                ROM,
                TRACE,
                graphics,
                header,
                manifest,
            )

            self.assertEqual(14, len(result["assets"]))
            self.assertEqual(16, result["sequence"]["frame_count"])
            self.assertEqual(11, result["sequence"]["keyframe_count"])
            self.assertEqual(16, result["sequence"]["duration"])
            self.assertEqual(8, result["sequence"]["maximum_components"])
            self.assertEqual(
                "6628fdc3365f8d6f16b134797be5f9a1c7cb48662ffeeea634ace058c659bb32",
                result["source_resources"]["tiles"]["sha256"],
            )
            self.assertEqual(
                "c00b7ea1d6748f60c387c12d2083da584a65a7e654e61a95bdfe25d1a803dc61",
                result["source_resources"]["palette"]["sha256"],
            )

            bmps = sorted(graphics.glob("battle_action_05_hit_*.bmp"))
            metadata = sorted(
                graphics.glob("battle_action_05_hit_*.json")
            )
            self.assertEqual(14, len(bmps))
            self.assertEqual(14, len(metadata))
            with Image.open(
                graphics / "battle_action_05_hit_t000_32x32.bmp"
            ) as image:
                self.assertEqual((32, 32), image.size)
                self.assertEqual("P", image.mode)
            with Image.open(
                graphics / "battle_action_05_hit_t032_8x16.bmp"
            ) as image:
                self.assertEqual((8, 16), image.size)

            header_text = header.read_text(encoding="utf-8")
            normalized_header = " ".join(header_text.split())
            self.assertIn(
                "inline constexpr battle_effect_sequence "
                "battle_action_05_hit_sequence",
                normalized_header,
            )
            self.assertIn(
                "battle_effect_component{ 160, 48, 0, false, false, 2 }",
                header_text,
            )
            items_header = (
                root / "generated_battle_action_05_effect_items.h"
            )
            self.assertTrue(items_header.is_file())
            items_text = items_header.read_text(encoding="utf-8")
            self.assertEqual(
                14,
                items_text.count(
                    "&bn::sprite_items::battle_action_05_hit_"
                ),
            )
            manifest_text = manifest.read_text(encoding="utf-8")
            self.assertIn(
                '"schema": "butano-original-oam-effect-sequence-v1"',
                manifest_text,
            )
            self.assertNotIn(".png", manifest_text.lower())
            self.assertNotIn("screenshot", manifest_text.lower())

    def test_generates_compact_dust_sequence_with_original_frame_holds(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            graphics = root / "graphics"
            header = (
                root
                / "generated_battle_action_05_dust_effect_content.h"
            )
            manifest = root / "action-05-dust-sequence.json"

            result = generate_sequence(
                ROM,
                TRACE_DUST,
                graphics,
                header,
                manifest,
                ACTION_05_DUST_SPEC,
            )

            self.assertEqual(8, len(result["assets"]))
            self.assertEqual(59, result["sequence"]["frame_count"])
            self.assertEqual(26, result["sequence"]["keyframe_count"])
            self.assertEqual(59, result["sequence"]["duration"])
            self.assertEqual(3, result["sequence"]["maximum_components"])
            self.assertEqual(
                "d2bdbe77b17e8ab4031f0a100851dffbbe5a8acf3a8b245ce1b6349d758221d3",
                result["source_resources"]["tiles"]["sha256"],
            )
            self.assertEqual(
                "baf6d16005215ced81fbddd5597f08cbc12441e468e737be9a3fb9a89ac04b67",
                result["source_resources"]["palette"]["sha256"],
            )
            self.assertEqual(
                8,
                len(
                    list(
                        graphics.glob(
                            "battle_action_05_dust_*.bmp"
                        )
                    )
                ),
            )
            normalized_header = " ".join(
                header.read_text(encoding="utf-8").split()
            )
            self.assertIn(
                "battle_action_05_dust_sequence",
                normalized_header,
            )
            self.assertIn(
                "battle_effect_frame{ {{",
                normalized_header,
            )
            self.assertIn(
                "}}, 3, 10 }",
                normalized_header,
            )
            items_header = (
                root
                / "generated_battle_action_05_dust_effect_items.h"
            )
            self.assertTrue(items_header.is_file())
            self.assertEqual(
                8,
                items_header.read_text(encoding="utf-8").count(
                    "&bn::sprite_items::battle_action_05_dust_"
                ),
            )

    def test_generates_action_16_fire_hit_from_original_components(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            graphics = root / "graphics"
            header = (
                root
                / "generated_battle_action_16_fire_effect_content.h"
            )
            manifest = root / "action-16-fire-hit-sequence.json"

            result = generate_sequence(
                ROM,
                TRACE_FIRE,
                graphics,
                header,
                manifest,
                ACTION_16_FIRE_HIT_SPEC,
            )

            self.assertEqual(10, len(result["assets"]))
            self.assertEqual(30, result["sequence"]["frame_count"])
            self.assertEqual(12, result["sequence"]["keyframe_count"])
            self.assertEqual(30, result["sequence"]["duration"])
            self.assertEqual(4, result["sequence"]["maximum_components"])
            self.assertEqual(
                "878505bd0d11d88fb0c72d9feeee8c4604625985cf9e496a3becb21a5165e867",
                result["source_resources"]["tiles"]["sha256"],
            )
            self.assertEqual(
                "2a4e16536349b52f028284eacbaa3e6047b02047b6e77af7d26914320b514d29",
                result["source_resources"]["palette"]["sha256"],
            )
            self.assertEqual(
                10,
                len(
                    list(
                        graphics.glob(
                            "battle_action_16_fire_hit_*.bmp"
                        )
                    )
                ),
            )
            normalized_header = " ".join(
                header.read_text(encoding="utf-8").split()
            )
            self.assertIn(
                "battle_action_16_fire_hit_sequence",
                normalized_header,
            )
            self.assertIn(
                "battle_effect_component{ 160, 48, 0, false, false, 2 }",
                header.read_text(encoding="utf-8"),
            )
            items_header = (
                root
                / "generated_battle_action_16_fire_effect_items.h"
            )
            self.assertTrue(items_header.is_file())
            self.assertEqual(
                10,
                items_header.read_text(encoding="utf-8").count(
                    "&bn::sprite_items::battle_action_16_fire_hit_"
                ),
            )
            manifest_text = manifest.read_text(encoding="utf-8")
            self.assertNotIn(".png", manifest_text.lower())
            self.assertNotIn("screenshot", manifest_text.lower())


if __name__ == "__main__":
    unittest.main()
