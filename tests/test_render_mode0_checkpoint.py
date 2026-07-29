import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class RenderMode0CheckpointTests(unittest.TestCase):
    def test_inventory_and_exact_embedded_png_goldens_cover_all_checkpoints(self):
        from tools.render_mode0_checkpoint import audit_checkpoint_corpus

        report = audit_checkpoint_corpus(ROOT / "artifacts/runtime-checkpoints")
        self.assertEqual(91, report["checkpoint_count"])
        self.assertEqual(91, report["mode0_checkpoint_count"])
        self.assertEqual(1211, report["active_oam_count"])
        self.assertEqual(0, report["affine_oam_count"])
        self.assertEqual(0, report["semitransparent_oam_count"])
        self.assertEqual(0, report["obj_window_oam_count"])
        self.assertEqual(5, report["win0_checkpoint_count"])
        self.assertEqual({1: 53, 3: 38}, report["blend_effect_counts"])
        self.assertEqual(89, report["exact_rgb_checkpoint_count"])
        self.assertEqual(
            [
                {
                    "path": "alternate-character-submenu.ss9",
                    "differing_bytes": 157,
                    "differing_pixels": 53,
                },
                {
                    "path": "skill-list-pre-controller.ss9",
                    "differing_bytes": 88,
                    "differing_pixels": 30,
                }
            ],
            report["mismatches"],
        )

    def test_only_mismatches_are_asynchronous_cursor_tiles_in_embedded_pngs(self):
        from tools.inspect_mgba_savestate import load_gba_state
        from tools.render_mode0_checkpoint import render_mode0

        cases = (
            ("alternate-character-submenu.ss9", 0x3F4, 0x3FA),
            ("skill-list-pre-controller.ss9", 0x3FA, 0x3F8),
        )
        for filename, serialized_tile, screenshot_tile in cases:
            with self.subTest(filename=filename):
                path = ROOT / "artifacts/runtime-checkpoints" / filename
                state = load_gba_state(path)
                hardware_oam = bytearray(
                    state.read_memory(0x07000000, 0x400)
                )
                shadow_oam = state.read_memory(0x0300027C, 0x400)
                self.assertEqual(hardware_oam, shadow_oam)
                serialized_attr2 = int.from_bytes(
                    hardware_oam[4:6], "little"
                )
                self.assertEqual(serialized_tile, serialized_attr2 & 0x3FF)

                hardware_oam[4:6] = (
                    (serialized_attr2 & 0xFC00) | screenshot_tile
                ).to_bytes(2, "little")
                rendered, _ = render_mode0(
                    state.read_memory(0x04000000, 0x400),
                    state.read_memory(0x05000000, 0x400),
                    bytes(hardware_oam),
                    state.read_memory(0x06000000, 0x18000),
                )
                with Image.open(path) as screenshot:
                    self.assertEqual(
                        screenshot.convert("RGB").tobytes(),
                        rendered,
                    )

    def test_five_bit_alpha_brighten_and_darken_formulas(self):
        from tools.render_mode0_checkpoint import (
            blend_alpha_bgr555,
            brighten_bgr555,
            darken_bgr555,
        )

        self.assertEqual(0x01EF, blend_alpha_bgr555(0x001F, 0x03E0, 8, 8))
        self.assertEqual(0x3DEF, brighten_bgr555(0x0000, 8))
        self.assertEqual(0x4210, darken_bgr555(0x7FFF, 8))
        self.assertEqual(0x7FFF, brighten_bgr555(0x7FFF, 16))
        self.assertEqual(0x0000, darken_bgr555(0x7FFF, 16))

    def test_mgba_packed_mcolor_darken_rounding_is_source_pinned(self):
        from tools.render_mode0_checkpoint import _darken_rgb8
        from tools.verify_mgba_renderer_source import (
            MGBA_COMMIT,
            SOURCE_PATH,
            SOURCE_SHA256,
            SOURCE_URL,
        )

        self.assertEqual(
            "1d65391d3531f9338300f306c4e1d76c258ce657",
            MGBA_COMMIT,
        )
        self.assertEqual("src/gba/renderers/software-private.h", SOURCE_PATH)
        self.assertEqual(
            "7bd0201cbd81aa74186121c91bf830ff3e33591a241f5ac5dd66d4842fe7b3aa",
            SOURCE_SHA256,
        )
        self.assertIn(MGBA_COMMIT, SOURCE_URL)
        self.assertEqual(bytes((145, 154, 133)), _darken_rgb8(0x6BDC, 6))
        generic_subtract = bytes(
            value - (value * 6 >> 4) for value in (231, 247, 214)
        )
        self.assertEqual(bytes((145, 155, 134)), generic_subtract)

    def test_window_coordinate_wrap_and_empty_range(self):
        from tools.render_mode0_checkpoint import in_window_range

        self.assertTrue(in_window_range(220, 200, 40))
        self.assertTrue(in_window_range(20, 200, 40))
        self.assertFalse(in_window_range(100, 200, 40))
        self.assertTrue(in_window_range(20, 10, 40))
        self.assertFalse(in_window_range(50, 10, 40))
        self.assertFalse(in_window_range(10, 10, 10))
