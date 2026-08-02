import unittest
from pathlib import Path
import struct

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class RenderMode0CheckpointTests(unittest.TestCase):
    def test_affine_runtime_goldens_reconstruct_bound_object_pixels(self):
        from tools.inspect_mgba_savestate import load_gba_state
        from tools.render_mode0_checkpoint import _object_coverage, _rgb8

        cases = (
            (
                "raw/state-0154.ss9",
                2,
                "runtime-object-02.png",
            ),
            (
                "mirror-raw/mirrored.ss9",
                5,
                "runtime-object-mirrored.png",
            ),
        )
        root = ROOT / "artifacts/battle-effect-affine-runtime-v1"
        for relative, object_index, reference_name in cases:
            with self.subTest(path=relative):
                state = load_gba_state(root / relative)
                io = state.read_memory(0x04000000, 0x400)
                pram = state.read_memory(0x05000000, 0x400)
                vram = state.read_memory(0x06000000, 0x18000)
                hardware_oam = state.read_memory(0x07000000, 0x400)
                isolated_oam = bytearray(hardware_oam)
                for index in range(128):
                    struct.pack_into("<H", isolated_oam, index * 8, 0x0200)
                start = object_index * 8
                isolated_oam[start : start + 6] = hardware_oam[
                    start : start + 6
                ]

                candidates, _, stats = _object_coverage(
                    struct.unpack_from("<H", io, 0)[0],
                    struct.unpack_from("<H", io, 0x4C)[0],
                    pram,
                    bytes(isolated_oam),
                    vram,
                )
                attr0, attr1 = struct.unpack_from(
                    "<HH", hardware_oam, start
                )
                origin_x, origin_y = attr1 & 0x1FF, attr0 & 0xFF
                rgba = bytearray()
                for local_y in range(32):
                    for local_x in range(32):
                        pixels = candidates[
                            (origin_y + local_y) * 240
                            + origin_x
                            + local_x
                        ]
                        if pixels:
                            self.assertEqual(1, len(pixels))
                            rgba.extend((*_rgb8(pixels[0].color), 255))
                        else:
                            rgba.extend((0, 0, 0, 0))
                with Image.open(root / reference_name) as reference:
                    self.assertEqual(
                        reference.convert("RGBA").tobytes(),
                        bytes(rgba),
                    )
                self.assertEqual(1, stats["affine"])

    def test_inventory_and_exact_embedded_png_goldens_cover_all_checkpoints(self):
        from tools.render_mode0_checkpoint import audit_checkpoint_corpus

        report = audit_checkpoint_corpus(ROOT / "artifacts/runtime-checkpoints")
        self.assertEqual(101, report["checkpoint_count"])
        self.assertEqual(101, report["mode0_checkpoint_count"])
        self.assertEqual(1368, report["active_oam_count"])
        self.assertEqual(0, report["affine_oam_count"])
        self.assertEqual(0, report["semitransparent_oam_count"])
        self.assertEqual(0, report["obj_window_oam_count"])
        self.assertEqual(5, report["win0_checkpoint_count"])
        self.assertEqual({1: 62, 3: 39}, report["blend_effect_counts"])
        self.assertEqual(98, report["exact_rgb_checkpoint_count"])
        self.assertEqual(
            [
                {
                    "path": "alternate-character-submenu.ss9",
                    "differing_bytes": 157,
                    "differing_pixels": 53,
                },
                {
                    "path": "scenario-47-fire-action16-confirmation.ss9",
                    "differing_bytes": 36,
                    "differing_pixels": 18,
                },
                {
                    "path": "skill-list-pre-controller.ss9",
                    "differing_bytes": 88,
                    "differing_pixels": 30,
                }
            ],
            report["mismatches"],
        )

    def test_only_mismatches_are_asynchronous_ui_state_in_embedded_pngs(self):
        from tools.inspect_mgba_savestate import load_gba_state
        from tools.render_mode0_checkpoint import render_mode0

        cases = (
            ("alternate-character-submenu.ss9", 0x3F4, 0x3FA, 0x3F4),
            ("skill-list-pre-controller.ss9", 0x3FA, 0x3F8, 0x3FA),
        )
        for filename, serialized_tile, screenshot_tile, shadow_tile in cases:
            with self.subTest(filename=filename):
                path = ROOT / "artifacts/runtime-checkpoints" / filename
                state = load_gba_state(path)
                hardware_oam = bytearray(
                    state.read_memory(0x07000000, 0x400)
                )
                shadow_oam = state.read_memory(0x0300027C, 0x400)
                serialized_attr2 = int.from_bytes(
                    hardware_oam[4:6], "little"
                )
                shadow_attr2 = int.from_bytes(shadow_oam[4:6], "little")
                self.assertEqual(serialized_tile, serialized_attr2 & 0x3FF)
                self.assertEqual(shadow_tile, shadow_attr2 & 0x3FF)
                self.assertEqual(
                    [4] if serialized_tile != shadow_tile else [],
                    [
                        index
                        for index, (hardware, shadow) in enumerate(
                            zip(hardware_oam, shadow_oam)
                        )
                        if hardware != shadow
                    ],
                )

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

        path = (
            ROOT
            / "artifacts/runtime-checkpoints"
            / "scenario-47-fire-action16-confirmation.ss9"
        )
        state = load_gba_state(path)
        pram = bytearray(state.read_memory(0x05000000, 0x400))
        self.assertEqual(0x4620, int.from_bytes(pram[0x23E:0x240], "little"))
        serialized, _ = render_mode0(
            state.read_memory(0x04000000, 0x400),
            bytes(pram),
            state.read_memory(0x07000000, 0x400),
            state.read_memory(0x06000000, 0x18000),
        )
        pram[0x23E:0x240] = (0x4E60).to_bytes(2, "little")
        previous_palette, _ = render_mode0(
            state.read_memory(0x04000000, 0x400),
            bytes(pram),
            state.read_memory(0x07000000, 0x400),
            state.read_memory(0x06000000, 0x18000),
        )
        with Image.open(path) as screenshot:
            actual = screenshot.convert("RGB").tobytes()
        palette_pixels = [
            offset
            for offset in range(0, len(actual), 3)
            if serialized[offset : offset + 3]
            != previous_palette[offset : offset + 3]
        ]
        self.assertEqual(20, len(palette_pixels))
        self.assertEqual(
            18,
            sum(
                actual[offset : offset + 3]
                == previous_palette[offset : offset + 3]
                for offset in palette_pixels
            ),
        )
        self.assertEqual(
            2,
            sum(
                actual[offset : offset + 3]
                == serialized[offset : offset + 3]
                for offset in palette_pixels
            ),
        )
        self.assertTrue(
            all(
                actual[offset : offset + 3]
                in {
                    serialized[offset : offset + 3],
                    previous_palette[offset : offset + 3],
                }
                for offset in palette_pixels
            )
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

    def test_mgba_mosaic_sampling_rules_are_source_pinned(self):
        from tools.verify_mgba_renderer_source import (
            MGBA_COMMIT,
            SOURCES,
            verify_sources,
        )

        self.assertEqual(
            "1d65391d3531f9338300f306c4e1d76c258ce657",
            MGBA_COMMIT,
        )
        self.assertEqual(
            {
                "src/gba/renderers/software-mode0.c":
                    "1e4104200fa1c068ff4ff17c24d8f99f9e1aed112d75e5088773e1bb6a318783",
                "src/gba/renderers/software-obj.c":
                    "b737ba2372054156fd987f95ed9350e3370f469cb38b40367657c70c02667fe9",
                "src/gba/renderers/software-private.h":
                    "7bd0201cbd81aa74186121c91bf830ff3e33591a241f5ac5dd66d4842fe7b3aa",
                "src/gba/renderers/video-software.c":
                    "39a03b64a3fe9ab384a17de7d92d215298e9f5b64415f7c550d33779c2bbaf70",
            },
            {entry["path"]: entry["sha256"] for entry in SOURCES},
        )
        missing = verify_sources({})
        self.assertFalse(missing["verified"])
        self.assertEqual(4, len(missing["sources"]))
        self.assertFalse(missing["mosaic_fragments_verified"])

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

    def test_affine_double_size_expands_bounds_without_scaling_source(self):
        from tools.render_mode0_checkpoint import render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        for offset, value in zip((6, 14, 22, 30), (256, 0, 0, 256)):
            struct.pack_into("<h", oam, offset, value)
        struct.pack_into("<HHH", oam, 4 * 8, 0x0300, 0x0000, 0x0000)
        struct.pack_into("<H", pram, 0x202, 0x001F)
        vram[0x10000 : 0x10020] = bytes((0x11,)) * 0x20

        rendered, stats = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )

        def pixel(x: int, y: int) -> bytes:
            start = (y * 240 + x) * 3
            return rendered[start : start + 3]

        self.assertEqual(bytes((0, 0, 0)), pixel(3, 3))
        self.assertEqual(bytes((255, 0, 0)), pixel(4, 4))
        self.assertEqual(bytes((255, 0, 0)), pixel(11, 11))
        self.assertEqual(bytes((0, 0, 0)), pixel(12, 12))
        self.assertEqual(1, stats["affine"])

    def test_bg_mosaic_is_screen_anchored_before_scroll(self):
        from tools.render_mode0_checkpoint import _rgb8, render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x0100)
        struct.pack_into("<H", io, 0x08, 0x04C0)
        struct.pack_into("<H", io, 0x10, 1)
        struct.pack_into("<H", io, 0x12, 2)
        struct.pack_into("<H", io, 0x4C, 0x0023)
        for index in range(1, 65):
            struct.pack_into("<H", pram, index * 2, index)
        vram[:64] = bytes(range(1, 65))

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )

        def pixel(x: int, y: int) -> bytes:
            start = (y * 240 + x) * 3
            return rendered[start : start + 3]

        first = _rgb8(18)
        next_block = _rgb8(46)
        self.assertEqual(first, pixel(0, 0))
        self.assertEqual(first, pixel(3, 2))
        self.assertEqual(next_block, pixel(4, 3))
        self.assertNotEqual(_rgb8(1), pixel(0, 0))

    def test_bg_mosaic_reuses_4bpp_flipped_palette_sample_across_tile_edge(self):
        from tools.render_mode0_checkpoint import _rgb8, render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x0100)
        struct.pack_into("<H", io, 0x08, 0x0140)
        struct.pack_into("<H", io, 0x4C, 0x0005)
        struct.pack_into("<H", vram, 0x800, 0x1400)
        struct.pack_into("<H", vram, 0x802, 0x2001)
        vram[0:4] = bytes((0x21, 0x43, 0x65, 0x87))
        vram[32:36] = bytes((0xA9, 0xCB, 0xED, 0x1F))
        for index in range(1, 48):
            struct.pack_into("<H", pram, index * 2, index)

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )

        def pixel(x: int, y: int) -> bytes:
            start = (y * 240 + x) * 3
            return rendered[start : start + 3]

        self.assertEqual(_rgb8(18), pixel(6, 0))
        self.assertEqual(pixel(6, 0), pixel(11, 0))
        self.assertEqual(_rgb8(45), pixel(12, 0))

    def test_normal_obj_mosaic_is_screen_anchored_not_object_anchored(self):
        from tools.render_mode0_checkpoint import render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        struct.pack_into("<H", io, 0x4C, 0x2300)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0x1005, 0x0003, 0x0000)
        for index in range(1, 16):
            struct.pack_into(
                "<H", pram, 0x200 + index * 2, index * 0x421
            )
        for y in range(8):
            for x in range(0, 8, 2):
                low = (y * 8 + x) % 15 + 1
                high = (y * 8 + x + 1) % 15 + 1
                vram[0x10000 + y * 4 + x // 2] = low | high << 4

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )

        def pixel(x: int, y: int) -> bytes:
            start = (y * 240 + x) * 3
            return rendered[start : start + 3]

        self.assertNotEqual(pixel(3, 5), pixel(4, 6))
        self.assertEqual(pixel(4, 6), pixel(7, 7))

    def test_normal_obj_mosaic_clamps_screen_anchor_before_flips(self):
        from tools.render_mode0_checkpoint import _rgb8, render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        struct.pack_into("<H", io, 0x4C, 0x2300)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0x1005, 0x3003, 0x0000)
        for index in range(1, 16):
            struct.pack_into(
                "<H", pram, 0x200 + index * 2, index * 0x421
            )
        for y in range(8):
            for x in range(0, 8, 2):
                low = (y * 8 + x) % 15 + 1
                high = (y * 8 + x + 1) % 15 + 1
                vram[0x10000 + y * 4 + x // 2] = low | high << 4

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )

        def pixel(x: int, y: int) -> bytes:
            start = (y * 240 + x) * 3
            return rendered[start : start + 3]

        self.assertEqual(_rgb8(4 * 0x421), pixel(3, 5))
        self.assertEqual(_rgb8(10 * 0x421), pixel(4, 6))
        self.assertEqual(pixel(4, 6), pixel(7, 7))

    def test_affine_obj_mosaic_samples_screen_block_before_matrix(self):
        from tools.render_mode0_checkpoint import _rgb8, render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        struct.pack_into("<H", io, 0x4C, 0x2300)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        for offset, value in zip((6, 14, 22, 30), (0, 256, -256, 0)):
            struct.pack_into("<h", oam, offset, value)
        struct.pack_into("<HHH", oam, 4 * 8, 0x1105, 0x0003, 0x0000)
        for index in range(1, 16):
            struct.pack_into(
                "<H", pram, 0x200 + index * 2, index * 0x421
            )
        for y in range(8):
            for x in range(0, 8, 2):
                low = (y * 8 + x) % 15 + 1
                high = (y * 8 + x + 1) % 15 + 1
                vram[0x10000 + y * 4 + x // 2] = low | high << 4

        rendered, stats = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )

        def pixel(x: int, y: int) -> bytes:
            start = (y * 240 + x) * 3
            return rendered[start : start + 3]

        self.assertEqual(_rgb8(13 * 0x421), pixel(4, 6))
        self.assertEqual(pixel(4, 6), pixel(7, 7))
        self.assertEqual(1, stats["affine"])

    def test_affine_obj_mosaic_leading_partial_block_matches_mgba_accumulator(self):
        from tools.render_mode0_checkpoint import _rgb8, render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        struct.pack_into("<H", io, 0x4C, 0x2300)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        for offset, value in zip((6, 14, 22, 30), (128, 0, 0, 256)):
            struct.pack_into("<h", oam, offset, value)
        struct.pack_into("<HHH", oam, 4 * 8, 0x1105, 0x0003, 0x0000)
        for index in range(1, 16):
            struct.pack_into(
                "<H", pram, 0x200 + index * 2, index * 0x421
            )
        for y in range(8):
            for x in range(0, 8, 2):
                low = (y * 8 + x) % 15 + 1
                high = (y * 8 + x + 1) % 15 + 1
                vram[0x10000 + y * 4 + x // 2] = low | high << 4

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )

        def pixel(x: int, y: int) -> bytes:
            start = (y * 240 + x) * 3
            return rendered[start : start + 3]

        self.assertEqual(_rgb8(2 * 0x421), pixel(3, 5))
        self.assertEqual(_rgb8(3 * 0x421), pixel(4, 5))
        self.assertEqual(pixel(4, 5), pixel(7, 5))

    def test_affine_double_size_mosaic_uses_expanded_output_geometry(self):
        from tools.render_mode0_checkpoint import _rgb8, render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        struct.pack_into("<H", io, 0x4C, 0x2300)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        for offset, value in zip((6, 14, 22, 30), (256, 0, 0, 256)):
            struct.pack_into("<h", oam, offset, value)
        struct.pack_into("<HHH", oam, 4 * 8, 0x1305, 0x0003, 0x0000)
        for index in range(1, 16):
            struct.pack_into(
                "<H", pram, 0x200 + index * 2, index * 0x421
            )
        for y in range(8):
            for x in range(0, 8, 2):
                low = (y * 8 + x) % 15 + 1
                high = (y * 8 + x + 1) % 15 + 1
                vram[0x10000 + y * 4 + x // 2] = low | high << 4

        rendered, stats = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )

        def pixel(x: int, y: int) -> bytes:
            start = (y * 240 + x) * 3
            return rendered[start : start + 3]

        self.assertEqual(bytes((0, 0, 0)), pixel(4, 9))
        self.assertEqual(_rgb8(2 * 0x421), pixel(8, 9))
        self.assertEqual(pixel(8, 9), pixel(11, 11))
        self.assertEqual(1, stats["affine"])

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

    def test_overlapping_obj_keeps_only_top_sprite_before_alpha_blend(self):
        from tools.render_mode0_checkpoint import render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        struct.pack_into("<H", io, 0x50, 0x3000)
        struct.pack_into("<H", io, 0x52, 0x0808)
        struct.pack_into("<H", pram, 0x000, 0x03E0)
        struct.pack_into("<H", pram, 0x202, 0x001F)
        struct.pack_into("<H", pram, 0x204, 0x7C00)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0x0400, 0x0000, 0x0000)
        struct.pack_into("<HHH", oam, 8, 0x0400, 0x0000, 0x0001)
        vram[0x10000] = 1
        vram[0x10020] = 2

        rendered, _ = render_mode0(
            bytes(io), bytes(pram), bytes(oam), bytes(vram)
        )

        self.assertEqual(bytes((127, 127, 0)), rendered[:3])

    def test_obj_priority_beats_oam_order_before_alpha_blend(self):
        from tools.render_mode0_checkpoint import render_mode0

        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        struct.pack_into("<H", io, 0x00, 0x1040)
        struct.pack_into("<H", io, 0x50, 0x3000)
        struct.pack_into("<H", io, 0x52, 0x0808)
        struct.pack_into("<H", pram, 0x000, 0x03E0)
        struct.pack_into("<H", pram, 0x202, 0x001F)
        struct.pack_into("<H", pram, 0x204, 0x7C00)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0x0400, 0x0000, 0x0401)
        struct.pack_into("<HHH", oam, 8, 0x0400, 0x0000, 0x0000)
        vram[0x10000] = 1
        vram[0x10020] = 2

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
