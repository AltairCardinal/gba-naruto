import re
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class GenerateBattleScenario49SceneryTest(unittest.TestCase):
    def _copy_committed_inputs(self, root):
        for relative in (
            "rom/base.gba",
            "artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9",
        ):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)

    def test_imports_from_committed_checkpoint_without_local_gpu_slices(self):
        from tools.butano.generate_battle_scenario_49_scenery import generate_outputs

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_committed_inputs(root)
            output = root / "output"
            result = generate_outputs(root, output)
            self.assertEqual(
                (output / "battle_scenario_49_chest.bmp").read_bytes(),
                (ROOT / "butano-sequel/graphics/battle_scenario_49_chest.bmp").read_bytes(),
            )
            self.assertEqual(
                result["source_commit"],
                "c16018a282d00f32ec8323877df68918cc478d8d",
            )
            self.assertFalse((root / "references").exists())

    def test_rejects_changed_rom_before_publishing_assets(self):
        from tools.butano.generate_battle_scenario_49_scenery import generate_outputs

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_committed_inputs(root)
            rom = root / "rom/base.gba"
            data = bytearray(rom.read_bytes())
            data[-1] ^= 1
            rom.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "ROM.*hash mismatch"):
                generate_outputs(root, root / "output")
            self.assertFalse((root / "output").exists())

    def test_rejects_changed_checkpoint_before_publishing_assets(self):
        from tools.butano.generate_battle_scenario_49_scenery import generate_outputs

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_committed_inputs(root)
            state = root / "artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9"
            state.write_bytes(state.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "checkpoint.*hash mismatch"):
                generate_outputs(root, root / "output")
            self.assertFalse((root / "output").exists())

    def test_extracts_exact_runtime_chest_sprite_from_original_gpu_evidence(
        self,
    ):
        from tools.butano.generate_battle_scenario_49_scenery import (
            generate_outputs,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = generate_outputs(ROOT, Path(temp_dir))
            chest = Image.open(
                Path(temp_dir) / "battle_scenario_49_chest.bmp"
            )

            self.assertEqual(chest.mode, "P")
            self.assertEqual(chest.size, (32, 32))
            self.assertEqual(chest.getpixel((0, 0)), 0)
            self.assertEqual(
                sum(
                    pixel != 0
                    for pixel in chest.get_flattened_data()
                ),
                582,
            )

            original = Image.open(
                ROOT
                / "artifacts/runtime-checkpoints/"
                "scenario-49-battle-14-entry.ss9"
            ).convert("RGB")
            palette = chest.getpalette()
            for y in range(32):
                for x in range(32):
                    color_index = chest.getpixel((x, y))
                    if color_index:
                        offset = color_index * 3
                        self.assertEqual(
                            tuple(palette[offset : offset + 3]),
                            original.getpixel((176 + x, 40 + y)),
                        )

            self.assertEqual(result["battle_id"], 14)
            self.assertEqual(result["oam_index"], 12)
            self.assertEqual(result["tile_index"], 944)
            self.assertEqual(result["palette_index"], 14)
            self.assertEqual(result["world_center"], [176, -176])

    def test_runtime_uses_live_objects_as_camera_bound_sprites(self):
        source = (ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp").read_text()
        self.assertIn('#include "bn_sprite_items_battle_scenario_49_chest.h"', source)
        self.assertIn("object.type == 3 && object.payload_id == 2", source)
        self.assertIn("world_x(object.position), world_y(object.position) - 8", source)
        self.assertIn("sprite.set_camera(camera)", source)
        self.assertIn("sprite.set_bg_priority(2)", source)
        self.assertIn("sprite.set_z_order(-object.position.y)", source)
        self.assertIn("object_state = controller.object_snapshot()", source)

    def test_destination_corners_reuse_both_committed_obj_tiles(self):
        from tools.butano.generate_battle_scenario_49_scenery import generate_outputs
        from tools.inspect_mgba_savestate import load_gba_state

        state = load_gba_state(ROOT / "artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            report = generate_outputs(ROOT, output)
            with Image.open(output / "battle_scenario_49_destination_cursor.bmp") as sprite:
                self.assertEqual(sprite.size, (64, 128))
                for distance in range(4):
                    tile = state.read_memory(0x06017080 if distance == 3 else 0x06017060, 32)
                    for vertical in range(2):
                        for horizontal in range(2):
                            left = 40 + distance if horizontal else 16 - distance
                            top = 16 + distance if vertical else 8 - distance
                            for y in range(8):
                                for x in range(8):
                                    tx = 7 - x if horizontal else x
                                    ty = 7 - y if vertical else y
                                    packed = tile[ty * 4 + tx // 2]
                                    expected = (packed >> (4 * (tx % 2))) & 15
                                    self.assertEqual(sprite.getpixel((left + x, distance * 32 + top + y)), expected)
                self.assertEqual(sprite.getpixel((32, 16)), 0)
                palette = sprite.getpalette()
                raw = state.read_memory(0x050003E0, 32)
                for index in range(16):
                    rgb5 = int.from_bytes(raw[index * 2:index * 2 + 2], "little")
                    for channel in range(3):
                        value = (rgb5 >> (5 * channel)) & 31
                        self.assertEqual(palette[3 * index + channel], (value << 3) | (value >> 2))
            self.assertEqual(report["destination_cursor"]["tile_addresses"], ["0x06017060", "0x06017080"])


if __name__ == "__main__":
    unittest.main()
