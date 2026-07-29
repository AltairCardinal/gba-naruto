import unittest
from pathlib import Path
import struct

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

    def test_8bpp_obj_ignores_odd_tile_index_bit(self):
        from tools.render_mode0_checkpoint import render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0x2000, 0x0000, 0x0001)
        struct.pack_into("<H", pram, 0x202, 0x001F)
        struct.pack_into("<H", pram, 0x204, 0x03E0)
        vram[0x10000] = 1
        vram[0x10020] = 2

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )
        self.assertEqual(bytes((255, 0, 0)), rendered[:3])

    def test_2d_obj_uses_fixed_32_tile_unit_row_stride(self):
        from tools.render_mode0_checkpoint import render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1000)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0x8000, 0x0000, 0x0000)
        struct.pack_into("<H", pram, 0x202, 0x001F)
        struct.pack_into("<H", pram, 0x204, 0x03E0)
        struct.pack_into("<H", pram, 0x206, 0x7C00)
        vram[0x10000] = 1
        vram[0x10020] = 3
        vram[0x10400] = 2

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )
        self.assertEqual(bytes((255, 0, 0)), rendered[:3])
        row_two = 8 * 240 * 3
        self.assertEqual(bytes((0, 255, 0)), rendered[row_two : row_two + 3])

    def test_semitransparent_obj_forces_alpha_with_backdrop_second_target(self):
        from tools.render_mode0_checkpoint import render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        struct.pack_into("<H", io, 0x50, 0x2000)
        struct.pack_into("<H", io, 0x52, 0x0808)
        struct.pack_into("<H", pram, 0x000, 0x03E0)
        struct.pack_into("<H", pram, 0x202, 0x001F)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0x0400, 0x0000, 0x0000)
        vram[0x10000] = 1

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )
        self.assertEqual(bytes((127, 127, 0)), rendered[:3])

    def test_obj_window_masks_color_without_drawing_its_own_pixels(self):
        from tools.render_mode0_checkpoint import render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x9040)
        struct.pack_into("<H", io, 0x4A, 0x1020)
        struct.pack_into("<H", pram, 0x000, 0x03E0)
        struct.pack_into("<H", pram, 0x202, 0x001F)
        struct.pack_into("<H", pram, 0x204, 0x7C00)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0x0800, 0x0000, 0x0000)
        struct.pack_into("<HHH", oam, 8, 0x0000, 0x0000, 0x0001)
        vram[0x10000] = 2
        vram[0x10020:0x10024] = b"\x11\x11\x11\x11"

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )
        self.assertEqual(bytes((255, 0, 0)), rendered[:3])
        self.assertEqual(bytes((0, 255, 0)), rendered[3:6])

    def test_brighten_and_win0_over_win1_are_explicit_fixtures(self):
        from tools.render_mode0_checkpoint import _window_control, render_mode0

        io = bytearray(0x400)
        pram = bytes(0x400)
        oam = bytearray(0x400)
        vram = bytes(0x18000)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<H", io, 0x50, 0x00A0)
        struct.pack_into("<H", io, 0x54, 0x0008)
        rendered, _ = render_mode0(
            bytes(io), pram, bytes(oam), vram
        )
        self.assertEqual(bytes((127, 127, 127)), rendered[:3])

        struct.pack_into("<H", io, 0x00, 0x6000)
        struct.pack_into("<H", io, 0x40, 0x000A)
        struct.pack_into("<H", io, 0x42, 0x000A)
        struct.pack_into("<H", io, 0x44, 0x000A)
        struct.pack_into("<H", io, 0x46, 0x000A)
        struct.pack_into("<H", io, 0x48, 0x0201)
        struct.pack_into("<H", io, 0x4A, 0x0003)
        self.assertEqual(0x01, _window_control(bytes(io), 0x6000, 5, 5, False))
        self.assertEqual(0x03, _window_control(bytes(io), 0x6000, 15, 5, False))
