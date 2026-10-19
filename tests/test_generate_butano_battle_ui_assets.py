import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class GenerateButanoBattleUiAssetsTest(unittest.TestCase):
    def test_generates_reusable_panel_and_dynamic_bar_assets(self):
        from tools.butano.generate_battle_ui_assets import generate_outputs

        with tempfile.TemporaryDirectory() as directory:
            output_directory = Path(directory)
            stale_dialogue_assets = (
                "battle_ui_dialogue_upper_forest_wide.bmp",
                "battle_ui_dialogue_upper_forest_wide.json",
                "battle_ui_dialogue_upper_forest_narrow.bmp",
                "battle_ui_dialogue_upper_forest_narrow.json",
                "battle_ui_dialogue_upper_grass_wide.bmp",
                "battle_ui_dialogue_upper_grass_wide.json",
                "battle_ui_dialogue_upper_grass_tail.bmp",
                "battle_ui_dialogue_upper_grass_tail.json",
            )
            for name in stale_dialogue_assets:
                (output_directory / name).write_bytes(b"stale")

            outputs = generate_outputs(output_directory)
            for name in stale_dialogue_assets:
                with self.subTest(stale=name):
                    self.assertFalse(
                        (output_directory / name).exists()
                    )
            self.assertEqual(
                set(outputs),
                {
                    "panel_bitmap",
                    "panel_metadata",
                    "status_panel_bitmap",
                    "status_panel_metadata",
                    "status_end_bitmap",
                    "status_end_metadata",
                    "bar_bitmap",
                    "bar_metadata",
                    "range_tiles_bitmap",
                    "range_tiles_metadata",
                    "range_palette_bitmap",
                    "range_palette_metadata",
                    "preparation_background_bitmap",
                    "preparation_background_metadata",
                    "preparation_overview_background_bitmap",
                    "preparation_overview_background_metadata",
                    "preparation_confirmation_background_bitmap",
                    "preparation_confirmation_background_metadata",
                    "dialog_panel_bitmap",
                    "dialog_panel_metadata",
                    "large_dialog_panel_bitmap",
                    "large_dialog_panel_metadata",
                    "message_panel_bitmap",
                    "message_panel_metadata",
                    "message_black_bar_bitmap",
                    "message_black_bar_metadata",
                    "dialogue_background_bitmap",
                    "dialogue_background_metadata",
                    "dialogue_text_palette_bitmap",
                    "dialogue_text_palette_metadata",
                    "dialogue_speaker_palette_bitmap",
                    "dialogue_speaker_palette_metadata",
                    "dialogue_speaker_label_bitmap",
                    "dialogue_speaker_label_metadata",
                    "text_accent_palette_bitmap",
                    "text_accent_palette_metadata",
                    "text_warning_palette_bitmap",
                    "text_warning_palette_metadata",
                    "preparation_text_palette_bitmap",
                    "preparation_text_palette_metadata",
                    "preparation_accent_palette_bitmap",
                    "preparation_accent_palette_metadata",
                    "preparation_menu_panel_bitmap",
                    "preparation_menu_panel_metadata",
                    "preparation_cursor_bitmap",
                    "preparation_cursor_metadata",
                    "command_cursor_bitmap",
                    "command_cursor_metadata",
                    "confirmation_cursor_bitmap",
                    "confirmation_cursor_metadata",
                    "map_hint_palette_bitmap",
                    "map_hint_palette_metadata",
                    "result_background_bitmap",
                    "result_background_metadata",
                    "result_panel_bitmap",
                    "result_panel_metadata",
                    "result_naruto_bitmap",
                    "result_naruto_metadata",
                    "result_sasuke_bitmap",
                    "result_sasuke_metadata",
                    "result_sakura_bitmap",
                    "result_sakura_metadata",
                    "result_total_palette_bitmap",
                    "result_total_palette_metadata",
                    "level_up_panel_bitmap",
                    "level_up_panel_metadata",
                    "level_up_title_bitmap",
                    "level_up_title_metadata",
                    "level_up_value_bitmap",
                    "level_up_value_metadata",
                    "level_up_portrait_64x64_bitmap",
                    "level_up_portrait_64x64_metadata",
                    "level_up_portrait_16x32_bitmap",
                    "level_up_portrait_16x32_metadata",
                    "level_up_portrait_32x16_bitmap",
                    "level_up_portrait_32x16_metadata",
                    "level_up_portrait_16x16_bitmap",
                    "level_up_portrait_16x16_metadata",
                    "level_up_eye_bitmap",
                    "level_up_eye_metadata",
                    "training_panel_bitmap",
                    "training_panel_metadata",
                    "training_text_0_bitmap",
                    "training_text_0_metadata",
                    "training_text_1_bitmap",
                    "training_text_1_metadata",
                    "training_text_2_bitmap",
                    "training_text_2_metadata",
                    "training_text_3_bitmap",
                    "training_text_3_metadata",
                    "training_text_4_bitmap",
                    "training_text_4_metadata",
                    "training_text_5_bitmap",
                    "training_text_5_metadata",
                    "preparation_dialog_panel_bitmap",
                    "preparation_dialog_panel_metadata",
                    "action_background_bitmap",
                    "action_background_metadata",
                    "action_icon_bitmap",
                    "action_icon_metadata",
                    "action_cursor_bitmap",
                    "action_cursor_metadata",
                    "action_start_hint_bitmap",
                    "action_start_hint_metadata",
                    "action_back_hint_bitmap",
                    "action_back_hint_metadata",
                    "action_actor_stats_bitmap",
                    "action_actor_stats_metadata",
                },
            )
            source = (
                ROOT
                / "artifacts"
                / "original-s49-selector1-page1-gpu-20260730-115"
            )
            io = (source / "io.bin").read_bytes()
            pram = (source / "pram.bin").read_bytes()
            vram = (source / "vram.bin").read_bytes()
            control = struct.unpack_from("<H", io, 0x08)[0]
            self.assertEqual(control & (1 << 7), 0)
            character_base = ((control >> 2) & 3) * 0x4000
            screen_base = ((control >> 8) & 31) * 0x800
            horizontal = struct.unpack_from("<H", io, 0x10)[0] & 511
            vertical = struct.unpack_from("<H", io, 0x12)[0] & 511
            original_palette = []
            for offset in range(0, 512, 2):
                value = int.from_bytes(
                    pram[offset:offset + 2], "little"
                )
                original_palette.append(
                    tuple(
                        (channel << 3) | (channel >> 2)
                        for channel in (
                            value & 31,
                            (value >> 5) & 31,
                            (value >> 10) & 31,
                        )
                    )
                )
            expected_frame = Image.new("RGB", (240, 160))
            for screen_y in range(160):
                for screen_x in range(240):
                    x = (screen_x + horizontal) & 255
                    y = (screen_y + vertical) & 255
                    entry = struct.unpack_from(
                        "<H",
                        vram,
                        screen_base
                        + ((y // 8) * 32 + x // 8) * 2,
                    )[0]
                    local_x = x & 7
                    local_y = y & 7
                    if entry & (1 << 10):
                        local_x = 7 - local_x
                    if entry & (1 << 11):
                        local_y = 7 - local_y
                    packed = vram[
                        character_base
                        + (entry & 0x3FF) * 32
                        + local_y * 4
                        + local_x // 2
                    ]
                    color = (
                        packed >> 4
                        if local_x & 1
                        else packed & 0x0F
                    )
                    palette_index = (
                        0
                        if color == 0
                        else ((entry >> 12) & 15) * 16
                        + color
                    )
                    expected_frame.putpixel(
                        (screen_x, screen_y),
                        original_palette[palette_index],
                    )
            with Image.open(
                outputs["dialogue_background_bitmap"]
            ) as dialogue_background:
                self.assertEqual(dialogue_background.mode, "P")
                self.assertEqual(dialogue_background.size, (256, 256))
                self.assertEqual(
                    dialogue_background.crop(
                        (8, 48, 248, 208)
                    ).convert("RGB").tobytes(),
                    expected_frame.tobytes(),
                )
            self.assertEqual(
                json.loads(
                    outputs["dialogue_background_metadata"].read_text(
                        encoding="utf-8"
                    )
                ),
                {
                    "type": "regular_bg",
                    "bpp_mode": "bpp_8",
                    "colors_count": 256,
                    "compression": "auto_no_huffman",
                    "active_size": [240, 160],
                    "source": (
                        "original-s49-selector1-page1-gpu-"
                        "20260730-115"
                    ),
                },
            )
            with Image.open(outputs["panel_bitmap"]) as panel:
                self.assertEqual(panel.mode, "P")
                self.assertEqual(panel.size, (64, 32 * 7))
                self.assertLessEqual(
                    len(set(panel.get_flattened_data())),
                    16,
                )
                # The original HUD uses a seven-pixel woven frame above and
                # below its 18-pixel state area.
                self.assertEqual(panel.getpixel((0, 0)), 4)
                self.assertEqual(panel.getpixel((32, 1)), 3)
                self.assertEqual(
                    [panel.getpixel((x, 2)) for x in range(8)],
                    [4, 4, 4, 12, 12, 12, 3, 3],
                )
                self.assertEqual(panel.getpixel((32, 6)), 6)
                self.assertEqual(panel.getpixel((32, 25)), 6)
                self.assertEqual(panel.getpixel((32, 31)), 4)
                self.assertNotEqual(panel.getpixel((32, 16)), 0)
                fill = panel.crop((0, 32 * 4, 64, 32 * 5))
                self.assertNotIn(
                    0, set(fill.get_flattened_data())
                )
                self.assertNotIn(
                    2, set(fill.get_flattened_data())
                )
                self.assertEqual(fill.getpixel((0, 0)), 1)
                menu_top = panel.crop((0, 64, 64, 96))
                self.assertEqual(
                    set(
                        menu_top.crop((0, 0, 8, 32))
                        .get_flattened_data()
                    ),
                    {0},
                )
                self.assertNotEqual(menu_top.getpixel((8, 16)), 0)
                self.assertNotEqual(menu_top.getpixel((55, 16)), 0)
                self.assertEqual(
                    set(
                        menu_top.crop((56, 0, 64, 32))
                        .get_flattened_data()
                    ),
                    {0},
                )

                short_top = panel.crop((0, 160, 64, 192))
                short_bottom = panel.crop((0, 192, 64, 224))
                self.assertEqual(
                    set(
                        short_top.crop((0, 0, 64, 8))
                        .get_flattened_data()
                    ),
                    {0},
                )
                self.assertNotEqual(short_top.getpixel((32, 8)), 0)
                self.assertNotEqual(short_bottom.getpixel((32, 23)), 0)
                self.assertEqual(
                    set(
                        short_bottom.crop((0, 24, 64, 32))
                        .get_flattened_data()
                    ),
                    {0},
                )
            with Image.open(outputs["bar_bitmap"]) as bar:
                self.assertEqual(bar.mode, "P")
                # GBA OBJ has no legal 64x8 shape.  Keep the original
                # eight-pixel-tall bar centered in a legal 64x32 frame.
                self.assertEqual(bar.size, (64, 32 * 4))
                self.assertEqual(bar.getpixel((0, 0)), 0)
                self.assertEqual(
                    set(
                        bar.crop((0, 0, 64, 12))
                        .get_flattened_data()
                    ),
                    {0},
                )
                self.assertEqual(bar.getpixel((15, 16)), 0)
                self.assertNotEqual(bar.getpixel((16, 16)), 0)
                self.assertNotEqual(bar.getpixel((55, 16)), 0)
                self.assertEqual(bar.getpixel((56, 16)), 0)
                self.assertEqual(
                    set(
                        bar.crop((0, 20, 64, 32))
                        .get_flattened_data()
                    ),
                    {0},
                )
                # Frame 1 is chakra and frame 2 is HP.  Both preserve the
                # source HUD's asymmetric gold rim and three-step fill
                # gradient instead of drawing a flat debug rectangle.
                chakra_top = 32 + 12
                self.assertEqual(
                    [bar.getpixel((x, chakra_top)) for x in (16, 17, 18, 55)],
                    [10, 15, 6, 15],
                )
                self.assertEqual(
                    bar.getpixel((18, chakra_top + 1)),
                    8,
                )
                self.assertEqual(
                    bar.getpixel((18, chakra_top + 2)),
                    9,
                )
                self.assertEqual(
                    bar.getpixel((18, chakra_top + 3)),
                    13,
                )
                hp_top = 64 + 12
                self.assertEqual(
                    [bar.getpixel((x, hp_top)) for x in (16, 17, 18, 55)],
                    [10, 15, 6, 15],
                )
                self.assertEqual(
                    bar.getpixel((18, hp_top + 1)),
                    14,
                )
                self.assertEqual(
                    bar.getpixel((18, hp_top + 2)),
                    11,
                )
                self.assertEqual(
                    bar.getpixel((18, hp_top + 3)),
                    7,
                )
                # Frame 3 is the original target-preview empty chakra
                # interior.  It is dark green, not the neutral status-HUD
                # track used by the compact panel.
                target_empty_top = 96 + 12
                self.assertEqual(
                    bar.getpixel((18, target_empty_top + 1)),
                    3,
                )
                for y in range(
                    target_empty_top + 2,
                    target_empty_top + 6,
                ):
                    self.assertEqual(bar.getpixel((17, y)), 4)
                    self.assertEqual(bar.getpixel((54, y)), 4)
                palette = bar.getpalette()
                self.assertEqual(
                    tuple(palette[3 * 3:3 * 3 + 3]),
                    (0, 82, 0),
                )
                self.assertEqual(
                    tuple(palette[4 * 3:4 * 3 + 3]),
                    (66, 41, 0),
                )
            with Image.open(
                outputs["dialog_panel_bitmap"]
            ) as dialog:
                self.assertEqual(dialog.mode, "P")
                self.assertEqual(dialog.size, (32, 64 * 3))
                self.assertEqual(dialog.getpixel((0, 0)), 0)
                # The outer slices reserve eight transparent pixels.  Three
                # 32x64 OBJ slices therefore expose the original 80x64
                # confirmation box at x=80..159 without spending more OAM.
                self.assertEqual(dialog.getpixel((7, 32)), 0)
                self.assertNotEqual(dialog.getpixel((8, 32)), 0)
                self.assertNotEqual(dialog.getpixel((16, 64 + 32)), 0)
                self.assertNotEqual(dialog.getpixel((23, 128 + 32)), 0)
                self.assertEqual(dialog.getpixel((24, 128 + 32)), 0)
                self.assertEqual(
                    hashlib.sha256(
                        bytes(dialog.get_flattened_data())
                    ).hexdigest(),
                    "84c3885eb65f327fe5d2c824f84c30e4"
                    "9bdc4d177769b50dae220bcd5b49e2d3",
                )
            with Image.open(
                outputs["large_dialog_panel_bitmap"]
            ) as large_dialog:
                self.assertEqual(large_dialog.mode, "P")
                self.assertEqual(large_dialog.size, (64, 64 * 4))
                # Four legal 64x64 OBJ frames compose the original
                # x=64..175, y=24..103 defense confirmation window.
                top_left = large_dialog.crop((0, 0, 64, 64))
                self.assertEqual(
                    set(
                        top_left.crop((0, 0, 4, 64))
                        .get_flattened_data()
                    ),
                    {0},
                )
            with Image.open(
                outputs["message_panel_bitmap"]
            ) as message_panel:
                self.assertEqual(message_panel.mode, "P")
                self.assertEqual(message_panel.size, (64, 64 * 4))
                # Four state-free 60px slices reproduce the signed original
                # BG window at x=0..239, y=96..159.  Speaker, body text and
                # the continue icon remain independent runtime sprites.
                source = Image.open(
                    ROOT
                    / "artifacts"
                    / "original-s49-selector1-page1-gpu-20260730-115"
                    / "frame.png"
                ).convert("RGB")
                expected = source.crop((0, 96, 240, 160))
                expected.paste(
                    (231, 247, 214),
                    (8, 7, 232, 57),
                )
                reconstructed = Image.new("RGB", (240, 64))
                rgb_panel = message_panel.convert("RGB")
                for frame_index in range(4):
                    frame = rgb_panel.crop(
                        (
                            0,
                            frame_index * 64,
                            64,
                            (frame_index + 1) * 64,
                        )
                    )
                    reconstructed.paste(
                        frame.crop((2, 0, 62, 64)),
                        (frame_index * 60, 0),
                    )
                self.assertEqual(
                    reconstructed.tobytes(),
                    expected.tobytes(),
                )
            with Image.open(
                outputs["message_black_bar_bitmap"]
            ) as message_black_bar:
                self.assertEqual(message_black_bar.mode, "P")
                self.assertEqual(message_black_bar.size, (64, 32))
                self.assertEqual(
                    set(
                        message_black_bar.crop((0, 0, 64, 12))
                        .get_flattened_data()
                    ),
                    {0},
                )
                self.assertEqual(
                    set(
                        message_black_bar.crop((2, 12, 62, 20))
                        .get_flattened_data()
                    ),
                    {15},
                )
                self.assertEqual(
                    set(
                        message_black_bar.crop((0, 20, 64, 32))
                        .get_flattened_data()
                    ),
                    {0},
                )
            with Image.open(
                outputs["dialogue_text_palette_bitmap"]
            ) as dialogue_text_palette:
                palette = dialogue_text_palette.getpalette()
                self.assertEqual(
                    tuple(palette[15 * 3:15 * 3 + 3]),
                    (57, 66, 57),
                )
                self.assertEqual(
                    tuple(palette[5 * 3:5 * 3 + 3]),
                    (173, 181, 156),
                )
                self.assertEqual(
                    tuple(palette[10 * 3:10 * 3 + 3]),
                    (115, 123, 107),
                )
            with Image.open(
                outputs["dialogue_speaker_palette_bitmap"]
            ) as dialogue_speaker_palette:
                palette = dialogue_speaker_palette.getpalette()
                self.assertEqual(
                    tuple(palette[14 * 3:14 * 3 + 3]),
                    (115, 33, 255),
                )
                self.assertEqual(
                    tuple(palette[6 * 3:6 * 3 + 3]),
                    (189, 173, 222),
                )
            with Image.open(
                outputs["dialogue_speaker_label_bitmap"]
            ) as dialogue_speaker_label:
                self.assertEqual(
                    dialogue_speaker_label.size,
                    (32, 16 * 2),
                )
                sources = (
                    ROOT
                    / "artifacts"
                    / "original-s49-facing-sequence-tail-20260730-114"
                    / "step-08-A.png",
                    ROOT
                    / "artifacts"
                    / "original-s49-selector1-page1-gpu-20260730-115"
                    / "frame.png",
                )
                rgb_labels = dialogue_speaker_label.convert("RGB")
                for frame_index, source_path in enumerate(sources):
                    expected = Image.open(source_path).convert("RGB").crop(
                        (16, 104, 48, 120)
                    )
                    actual = rgb_labels.crop(
                        (
                            0,
                            frame_index * 16,
                            32,
                            (frame_index + 1) * 16,
                        )
                    )
                    for y in range(16):
                        for x in range(32):
                            if expected.getpixel((x, y)) == (
                                231,
                                247,
                                214,
                            ):
                                self.assertEqual(
                                    actual.getpixel((x, y)),
                                    (0, 0, 0),
                                )
                            else:
                                self.assertEqual(
                                    actual.getpixel((x, y)),
                                    expected.getpixel((x, y)),
                                )
                self.assertNotEqual(top_left.getpixel((5, 0)), 0)
                self.assertNotEqual(top_left.getpixel((59, 39)), 0)
                self.assertEqual(
                    set(
                        top_left.crop((0, 40, 64, 64))
                        .get_flattened_data()
                    ),
                    {0},
                )
                bottom_right = large_dialog.crop(
                    (0, 64 * 3, 64, 64 * 4)
                )
                self.assertNotEqual(
                    bottom_right.getpixel((4, 0)),
                    0,
                )
                self.assertNotEqual(
                    bottom_right.getpixel((58, 39)),
                    0,
                )
                self.assertEqual(
                    set(
                        bottom_right.crop((0, 40, 64, 64))
                        .get_flattened_data()
                    ),
                    {0},
                )
            with Image.open(
                outputs["text_accent_palette_bitmap"]
            ) as accent:
                palette = accent.getpalette()
                self.assertEqual(
                    tuple(palette[2 * 3:2 * 3 + 3]),
                    (115, 33, 255),
                )
                self.assertEqual(
                    tuple(palette[5 * 3:5 * 3 + 3]),
                    (189, 173, 222),
                )
            with Image.open(
                outputs["map_hint_palette_bitmap"]
            ) as map_hint:
                palette = map_hint.getpalette()
                for index in (2, 14):
                    self.assertEqual(
                        tuple(
                            palette[index * 3:index * 3 + 3]
                        ),
                        (255, 255, 255),
                    )
                for index in (5, 12):
                    self.assertEqual(
                        tuple(
                            palette[index * 3:index * 3 + 3]
                        ),
                        (33, 33, 33),
                    )
            with Image.open(
                outputs["result_background_bitmap"]
            ) as result_background:
                self.assertEqual(result_background.mode, "P")
                self.assertEqual(
                    result_background.size,
                    (256, 256),
                )
                # BG0 is the exact source gradient and stays transparent
                # where the original BG3 header/footer panels cover it.
                viewport = result_background.crop((8, 48, 248, 208))
                self.assertIn(0, set(viewport.get_flattened_data()))
                for x in (8, 68, 128, 188, 247):
                    self.assertNotEqual(
                        result_background.getpixel((x, 80)),
                        result_background.getpixel((x, 128)),
                    )
            with Image.open(
                outputs["result_panel_bitmap"]
            ) as result_panel:
                self.assertEqual(result_panel.mode, "P")
                self.assertEqual(result_panel.size, (256, 256))
                self.assertEqual(
                    result_panel.getpixel((128, 128)),
                    0,
                )
                self.assertNotEqual(
                    result_panel.getpixel((8, 48)),
                    result_panel.getpixel((40, 64)),
                )
            self.assertEqual(
                outputs["result_background_metadata"].read_text(
                    encoding="utf-8"
                ),
                '{\n  "type": "regular_bg"\n}\n',
            )
            self.assertEqual(
                outputs["result_panel_metadata"].read_text(
                    encoding="utf-8"
                ),
                '{\n  "type": "regular_bg"\n}\n',
            )
            with Image.open(
                outputs["result_total_palette_bitmap"]
            ) as result_total:
                palette = result_total.getpalette()
                for index in (2, 14):
                    self.assertEqual(
                        tuple(
                            palette[index * 3:index * 3 + 3]
                        ),
                        (231, 24, 0),
                    )
            with Image.open(
                outputs["preparation_text_palette_bitmap"]
            ) as preparation_text:
                palette = preparation_text.getpalette()
                self.assertEqual(
                    tuple(palette[15 * 3:15 * 3 + 3]),
                    (115, 123, 107),
                )
            with Image.open(
                outputs["preparation_accent_palette_bitmap"]
            ) as preparation_accent:
                palette = preparation_accent.getpalette()
                self.assertEqual(
                    tuple(palette[15 * 3:15 * 3 + 3]),
                    (148, 99, 239),
                )
            with Image.open(
                outputs["preparation_dialog_panel_bitmap"]
            ) as preparation_dialog:
                self.assertEqual(
                    preparation_dialog.size,
                    (32, 64 * 3),
                )
                # A 48px-high frame is centered inside a legal 32x64 OBJ.
                self.assertEqual(
                    set(
                        preparation_dialog.crop((0, 0, 32, 8))
                        .get_flattened_data()
                    ),
                    {0},
                )
                self.assertNotEqual(
                    preparation_dialog.getpixel((16, 8)),
                    0,
                )
                self.assertNotEqual(
                    preparation_dialog.getpixel(
                        (16, 64 + 32)
                    ),
                    0,
                )
            with Image.open(
                outputs["range_tiles_bitmap"]
            ) as overlay:
                self.assertEqual(overlay.mode, "P")
                self.assertEqual(overlay.size, (8, 8 * 4))
                self.assertEqual(
                    set(
                        overlay.crop((0, 0, 8, 8))
                        .get_flattened_data()
                    ),
                    {0},
                )
                self.assertNotEqual(
                    set(
                        overlay.crop((0, 8, 8, 16))
                        .get_flattened_data()
                    ),
                    {0},
                )
            with Image.open(
                outputs["preparation_background_bitmap"]
            ) as preparation:
                self.assertEqual(preparation.mode, "P")
                self.assertEqual(preparation.size, (256, 256))
                # The centered 240x160 viewport has a title frame, main
                # frame and independent menu frame extracted as state-free
                # border elements from the original scenario 49 evidence.
                self.assertEqual(preparation.getpixel((8, 48)), 4)
                self.assertEqual(
                    [
                        preparation.getpixel((8 + x, 50))
                        for x in range(8)
                    ],
                    [4, 3, 12, 12, 4, 12, 4, 3],
                )
                self.assertEqual(preparation.getpixel((80, 96)), 4)
                self.assertEqual(
                    [
                        preparation.getpixel((80 + x, 98))
                        for x in range(8)
                    ],
                    [4, 3, 12, 12, 4, 12, 4, 3],
                )
                self.assertEqual(preparation.getpixel((128, 128)), 1)
                self.assertEqual(preparation.getpixel((216, 88)), 1)
            with Image.open(
                outputs["preparation_overview_background_bitmap"]
            ) as overview:
                self.assertEqual(overview.mode, "P")
                self.assertEqual(overview.size, (256, 256))
                self.assertEqual(overview.getpixel((8, 48)), 4)
                self.assertEqual(
                    [
                        overview.getpixel((8 + x, 50))
                        for x in range(8)
                    ],
                    [4, 3, 12, 12, 4, 12, 4, 3],
                )
                self.assertEqual(overview.getpixel((80, 96)), 1)
                self.assertEqual(overview.getpixel((128, 128)), 1)
            with Image.open(
                outputs["preparation_menu_panel_bitmap"]
            ) as preparation_menu:
                self.assertEqual(preparation_menu.mode, "P")
                self.assertEqual(preparation_menu.size, (64, 64 * 4))
                self.assertEqual(preparation_menu.getpixel((0, 0)), 0)
                self.assertEqual(preparation_menu.getpixel((16, 24)), 4)
                self.assertEqual(preparation_menu.getpixel((32, 40)), 1)
                self.assertEqual(
                    preparation_menu.getpixel((47, 64 * 3 + 39)),
                    4,
                )
                self.assertEqual(
                    set(
                        preparation_menu.crop(
                            (48, 64 * 3, 64, 64 * 4)
                        ).get_flattened_data()
                    ),
                    {0},
                )
            with Image.open(
                outputs["preparation_cursor_bitmap"]
            ) as preparation_cursor:
                self.assertEqual(preparation_cursor.mode, "P")
                self.assertEqual(preparation_cursor.size, (8, 8))
                self.assertEqual(
                    sum(
                        pixel != 0
                        for pixel in
                        preparation_cursor.get_flattened_data()
                    ),
                    42,
                )
                self.assertEqual(
                    hashlib.sha256(
                        bytes(
                            preparation_cursor
                            .get_flattened_data()
                        )
                    ).hexdigest(),
                    "aadfb4745063cc8022323dc34f7f0a6f"
                    "11646919883f7678c43537b53bb2508b",
                )
                palette = preparation_cursor.getpalette()
                for index, expected_color in enumerate(
                    (
                        (0, 0, 0),
                        (181, 189, 165),
                        (247, 255, 222),
                        (115, 123, 107),
                        (57, 57, 57),
                    )
                ):
                    self.assertEqual(
                        tuple(
                            palette[index * 3:index * 3 + 3]
                        ),
                        expected_color,
                    )

            with Image.open(
                outputs["command_cursor_bitmap"]
            ) as command_cursor:
                self.assertEqual(command_cursor.mode, "P")
                self.assertEqual(command_cursor.size, (8, 16))
                self.assertEqual(
                    sum(
                        pixel != 0
                        for pixel in command_cursor.get_flattened_data()
                    ),
                    61,
                )
                self.assertEqual(
                    hashlib.sha256(
                        bytes(command_cursor.get_flattened_data())
                    ).hexdigest(),
                    "b86c16d878c7fd180e217142d488a293"
                    "b25afc62e116f9d86d153a775d50fcc6",
                )
                palette = command_cursor.getpalette()
                for index, expected_color in enumerate(
                    (
                        (0, 0, 0),
                        (247, 255, 222),
                        (181, 189, 165),
                        (115, 123, 107),
                        (57, 57, 57),
                    )
                ):
                    self.assertEqual(
                        tuple(palette[index * 3:index * 3 + 3]),
                        expected_color,
                    )
            with Image.open(
                outputs["confirmation_cursor_bitmap"]
            ) as confirmation_cursor:
                self.assertEqual(confirmation_cursor.mode, "P")
                self.assertEqual(
                    confirmation_cursor.size,
                    (8, 16),
                )
                self.assertEqual(
                    sum(
                        pixel != 0
                        for pixel in confirmation_cursor
                        .get_flattened_data()
                    ),
                    42,
                )
                self.assertEqual(
                    hashlib.sha256(
                        bytes(
                            confirmation_cursor
                            .get_flattened_data()
                        )
                    ).hexdigest(),
                    "6b636a6f0d174bf8e27ca6c88c7cfaf1"
                    "1f8aaf43cf075e9c9f16c21df8560777",
                )
                palette = confirmation_cursor.getpalette()
                for index, expected_color in enumerate(
                    (
                        (0, 0, 0),
                        (247, 255, 222),
                        (181, 189, 165),
                        (115, 123, 107),
                        (57, 57, 57),
                    )
                ):
                    self.assertEqual(
                        tuple(
                            palette[index * 3:index * 3 + 3]
                        ),
                        expected_color,
                    )
            with Image.open(
                outputs["action_background_bitmap"]
            ) as action_background:
                self.assertEqual(
                    action_background.size,
                    (64, 64 * 6),
                )
                # Six reusable 64x64 OBJ frames compose the 4x3 screen grid:
                # one common frame and one right-side separator frame per
                # row.  Keeping the unique frame count at six avoids both a
                # second BG palette and exhausting OBJ tile VRAM.
                self.assertEqual(
                    action_background.getpixel((32, 4)),
                    1,
                )
                self.assertEqual(
                    action_background.getpixel((24, 64)),
                    2,
                )
                self.assertEqual(
                    action_background.getpixel((32, 64 * 2 + 48)),
                    2,
                )
                self.assertEqual(
                    set(
                        action_background.crop(
                            (0, 64 * 4 + 32, 64, 64 * 5)
                        ).get_flattened_data()
                    ),
                    {0},
                )
            with Image.open(
                outputs[
                    "preparation_confirmation_background_bitmap"
                ]
            ) as confirmation:
                self.assertEqual(confirmation.size, (256, 256))
                # Visible modal bounds are x=40..199, y=64..111.
                self.assertEqual(confirmation.getpixel((48, 112)), 2)
                self.assertEqual(confirmation.getpixel((207, 159)), 2)
                self.assertEqual(confirmation.getpixel((128, 136)), 1)

    def test_status_panel_is_a_state_free_exact_shell_from_original_bg3(self):
        from tools.butano.generate_battle_ui_assets import generate_outputs

        evidence = (
            ROOT
            / "references"
            / "battle-scenario-49-ui"
        )
        tile_bytes = (
            evidence / "hud-shell-bg-tiles.bin"
        ).read_bytes()
        palette_bytes = (
            evidence / "hud-shell-bg-palette.bin"
        ).read_bytes()

        def decode_tile(tile_index):
            encoded = tile_bytes[
                tile_index * 32:(tile_index + 1) * 32
            ]
            pixels = []
            for packed in encoded:
                pixels.extend((packed & 0x0F, packed >> 4))
            return pixels

        tile_roles = (
            (1,) + (5,) * 28 + (2,),
            (7,) + (0,) * 28 + (8,),
            (7,) + (0,) * 28 + (8,),
            (3,) + (6,) * 28 + (4,),
        )
        expected = Image.new("P", (256, 32))
        for tile_y, row in enumerate(tile_roles):
            for tile_x, tile_index in enumerate(row):
                tile = Image.new("P", (8, 8))
                tile.putdata(decode_tile(tile_index))
                expected.paste(tile, (tile_x * 8, tile_y * 8))

        with tempfile.TemporaryDirectory() as directory:
            outputs = generate_outputs(Path(directory))
            with Image.open(
                outputs["status_panel_bitmap"]
            ) as panel:
                self.assertEqual(panel.mode, "P")
                self.assertEqual(panel.size, (64, 32 * 4))
                reconstructed = Image.new("P", (256, 32))
                for frame in range(4):
                    reconstructed.paste(
                        panel.crop(
                            (
                                0,
                                frame * 32,
                                64,
                                (frame + 1) * 32,
                            )
                        ),
                        (frame * 64, 0),
                    )
                self.assertEqual(
                    list(
                        reconstructed
                        .crop((0, 0, 240, 32))
                        .get_flattened_data()
                    ),
                    list(
                        expected
                        .crop((0, 0, 240, 32))
                        .get_flattened_data()
                    ),
                )
                palette = panel.getpalette()
                expected_palette = []
                for index in range(16):
                    color = int.from_bytes(
                        palette_bytes[index * 2:index * 2 + 2],
                        "little",
                    )
                    expected_palette.extend(
                        (
                            ((color & 31) << 3)
                            | ((color & 31) >> 2),
                            (((color >> 5) & 31) << 3)
                            | (((color >> 5) & 31) >> 2),
                            (((color >> 10) & 31) << 3)
                            | (((color >> 10) & 31) >> 2),
                        )
                    )
                self.assertEqual(
                    palette[:16 * 3],
                    expected_palette,
                )
            self.assertEqual(
                outputs["status_panel_metadata"].read_text(
                    encoding="utf-8"
                ),
                (
                    '{\n'
                    '  "type": "sprite",\n'
                    '  "height": 32\n'
                    '}\n'
                ),
            )

    def test_status_end_is_exact_dynamic_phase_glyph_without_panel_pixels(self):
        from tools.butano.generate_battle_ui_assets import generate_outputs

        source = Image.open(
            ROOT
            / "artifacts"
            / "runtime-checkpoints"
            / "scenario-49-battle-14-entry.ss9"
        ).convert("RGB").crop((104, 136, 120, 152))
        expected_colors = {
            (231, 247, 214): 0,
            (231, 24, 0): 2,
            (231, 173, 140): 5,
        }
        with tempfile.TemporaryDirectory() as directory:
            outputs = generate_outputs(Path(directory))
            with Image.open(outputs["status_end_bitmap"]) as glyph:
                self.assertEqual(glyph.mode, "P")
                self.assertEqual(glyph.size, (16, 16))
                self.assertEqual(
                    list(glyph.get_flattened_data()),
                    [
                        expected_colors[color]
                        for color in source.get_flattened_data()
                    ],
                )
            self.assertEqual(
                outputs["status_end_metadata"].read_text(
                    encoding="utf-8"
                ),
                (
                    '{\n'
                    '  "type": "sprite",\n'
                    '  "height": 16\n'
                    '}\n'
                ),
            )

    def test_warning_text_palette_matches_original_red_hud_label(self):
        from tools.butano.generate_battle_ui_assets import (
            PALETTE,
            TEXT_ACCENT_PALETTE,
            TEXT_WARNING_PALETTE,
            generate_outputs,
        )

        self.assertEqual(PALETTE[15], (115, 123, 107))
        self.assertEqual(
            TEXT_ACCENT_PALETTE[15],
            (148, 99, 239),
        )
        self.assertEqual(TEXT_WARNING_PALETTE[2], (231, 24, 0))
        self.assertEqual(TEXT_WARNING_PALETTE[5], (231, 173, 140))
        with tempfile.TemporaryDirectory() as directory:
            outputs = generate_outputs(Path(directory))
            self.assertTrue(
                outputs["text_warning_palette_bitmap"].is_file()
            )
            self.assertTrue(
                outputs["text_warning_palette_metadata"].is_file()
            )

    def test_action_icons_are_exact_state_free_original_menu_glyphs(self):
        from tools.butano.generate_battle_ui_assets import (
            ACTION_ICON_FRAME_COUNT,
            ACTION_ICON_SIZE,
            ACTION_MENU_SOURCE,
            _action_icon_pixels,
            generate_outputs,
        )

        self.assertEqual(
            ACTION_MENU_SOURCE,
            ROOT
            / "artifacts"
            / "scenario-49-battle-14-original-ui-boundaries-v1"
            / "turn4-action-a-01"
            / "step-01-A.ss9",
        )
        pixels = _action_icon_pixels()
        self.assertEqual(
            len(pixels),
            ACTION_ICON_SIZE
            * ACTION_ICON_SIZE
            * ACTION_ICON_FRAME_COUNT,
        )
        self.assertEqual(
            hashlib.sha256(bytes(pixels)).hexdigest(),
            "20be299264112376444b451d1a2324e9"
            "ded290ebd38ec76b18c72440fae35457",
        )
        for frame_index in range(ACTION_ICON_FRAME_COUNT):
            frame_start = (
                frame_index * ACTION_ICON_SIZE * ACTION_ICON_SIZE
            )
            frame = pixels[
                frame_start:
                frame_start + ACTION_ICON_SIZE * ACTION_ICON_SIZE
            ]
            self.assertEqual(
                sum(pixel != 0 for pixel in frame),
                224,
            )

        with tempfile.TemporaryDirectory() as directory:
            outputs = generate_outputs(Path(directory))
            with Image.open(outputs["action_icon_bitmap"]) as icons:
                self.assertEqual(icons.mode, "P")
                self.assertEqual(
                    icons.size,
                    (
                        ACTION_ICON_SIZE,
                        ACTION_ICON_SIZE
                        * ACTION_ICON_FRAME_COUNT,
                    ),
                )
            self.assertEqual(
                outputs["action_icon_metadata"].read_text(
                    encoding="utf-8"
                ),
                (
                    '{\n'
                    '  "type": "sprite",\n'
                    '  "height": 16\n'
                    '}\n'
                ),
            )

    def test_action_controls_are_exact_independent_original_objs(self):
        from tools.butano.generate_battle_ui_assets import (
            ACTION_ACTOR_STATS_HEIGHT,
            ACTION_ACTOR_STATS_WIDTH,
            ACTION_BACK_HINT_HEIGHT,
            ACTION_BACK_HINT_WIDTH,
            ACTION_CURSOR_HEIGHT,
            ACTION_CURSOR_WIDTH,
            ACTION_START_HINT_HEIGHT,
            ACTION_START_HINT_WIDTH,
            _action_back_hint_pixels,
            _action_actor_stats_pixels,
            _action_cursor_pixels,
            _action_start_hint_pixels,
            generate_outputs,
        )

        expected = (
            (
                "action_cursor_bitmap",
                "action_cursor_metadata",
                _action_cursor_pixels(),
                (ACTION_CURSOR_WIDTH, ACTION_CURSOR_HEIGHT),
                "11a717b18f659e7b5e08a1a2c5b0b1a5"
                "f011b99e5b933577e056c32779b04c4e",
            ),
            (
                "action_start_hint_bitmap",
                "action_start_hint_metadata",
                _action_start_hint_pixels(),
                (ACTION_START_HINT_WIDTH, ACTION_START_HINT_HEIGHT),
                "1b8ca4a2daa6087368f54cac89cd814ec"
                "320668de2b8abe3688be729d08b0a04",
            ),
            (
                "action_back_hint_bitmap",
                "action_back_hint_metadata",
                _action_back_hint_pixels(),
                (ACTION_BACK_HINT_WIDTH, ACTION_BACK_HINT_HEIGHT),
                "2941fa33c202c9d303ccde8747b50eea"
                "7c862b0cd4a271efb14292538debf20d",
            ),
            (
                "action_actor_stats_bitmap",
                "action_actor_stats_metadata",
                _action_actor_stats_pixels(),
                (
                    ACTION_ACTOR_STATS_WIDTH,
                    ACTION_ACTOR_STATS_HEIGHT,
                ),
                "56fe4c1ad9a790b6a92287c3bb885dc1"
                "5c1dfedf1993d8d12726c6ffd40a9aed",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            outputs = generate_outputs(Path(directory))
            for (
                bitmap_key,
                metadata_key,
                pixels,
                size,
                digest,
            ) in expected:
                with self.subTest(bitmap=bitmap_key):
                    self.assertEqual(
                        hashlib.sha256(bytes(pixels)).hexdigest(),
                        digest,
                    )
                    with Image.open(outputs[bitmap_key]) as image:
                        self.assertEqual(image.mode, "P")
                        self.assertEqual(image.size, size)
                        self.assertEqual(
                            list(image.get_flattened_data()),
                            pixels,
                        )
                    self.assertEqual(
                        outputs[metadata_key].read_text(
                            encoding="utf-8"
                        ),
                        (
                            '{\n'
                            '  "type": "sprite",\n'
                            '  "height": 16\n'
                            '}\n'
                        ),
                    )

    def test_preparation_dialog_shell_matches_original_scenario_49(self):
        from tools.butano.generate_battle_ui_assets import generate_outputs

        with tempfile.TemporaryDirectory() as directory:
            outputs = generate_outputs(Path(directory))
            original_confirmation = Image.open(
                ROOT
                / "artifacts"
                / "original-s49-task-start-20260730-107"
                / "step-03-A.png"
            ).convert("RGB")
            preparation_dialog = Image.open(
                outputs["preparation_dialog_panel_bitmap"]
            )
            dialog_palette = preparation_dialog.getpalette()
            slices = (
                (0, 40),
                (1, 72),
                (1, 104),
                (1, 136),
                (2, 168),
            )
            for frame_index, screen_left in slices:
                for source_y in range(8, 56):
                    screen_y = 56 + source_y
                    for source_x in range(32):
                        screen_x = screen_left + source_x
                        if (
                            48 <= screen_x < 96
                            and 72 <= screen_y < 88
                        ) or (
                            160 <= screen_x < 176
                            and 72 <= screen_y < 104
                        ):
                            continue
                        palette_index = preparation_dialog.getpixel(
                            (
                                source_x,
                                frame_index * 64 + source_y,
                            )
                        )
                        if palette_index == 0:
                            continue
                        actual = tuple(
                            dialog_palette[
                                palette_index * 3:
                                palette_index * 3 + 3
                            ]
                        )
                        self.assertEqual(
                            actual,
                            original_confirmation.getpixel(
                                (screen_x, screen_y)
                            ),
                            (screen_x, screen_y),
                        )

    def test_checked_in_assets_match_generator(self):
        from tools.butano.generate_battle_ui_assets import generate_outputs

        with tempfile.TemporaryDirectory() as directory:
            outputs = generate_outputs(Path(directory))
            checked_in = {
                "panel_bitmap": (
                    ROOT / "butano-sequel/graphics/battle_ui_panel.bmp"
                ),
                "panel_metadata": (
                    ROOT / "butano-sequel/graphics/battle_ui_panel.json"
                ),
                "bar_bitmap": (
                    ROOT / "butano-sequel/graphics/battle_ui_bar.bmp"
                ),
                "bar_metadata": (
                    ROOT / "butano-sequel/graphics/battle_ui_bar.json"
                ),
                "range_tiles_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_range_overlay_tiles.bmp"
                ),
                "range_tiles_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_range_overlay_tiles.json"
                ),
                "range_palette_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_range_overlay_palette.bmp"
                ),
                "range_palette_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_range_overlay_palette.json"
                ),
                "preparation_background_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_preparation_background.bmp"
                ),
                "preparation_background_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_preparation_background.json"
                ),
                "preparation_overview_background_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_preparation_overview_background.bmp"
                ),
                "preparation_overview_background_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_preparation_overview_background.json"
                ),
                "preparation_confirmation_background_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_preparation_confirmation_background.bmp"
                ),
                "preparation_confirmation_background_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_preparation_confirmation_background.json"
                ),
                "dialog_panel_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_dialog_panel.bmp"
                ),
                "dialog_panel_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_dialog_panel.json"
                ),
                "large_dialog_panel_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_large_dialog_panel.bmp"
                ),
                "large_dialog_panel_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_large_dialog_panel.json"
                ),
                "message_panel_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_message_panel.bmp"
                ),
                "message_panel_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_message_panel.json"
                ),
                "text_accent_palette_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_text_accent_palette.bmp"
                ),
                "text_accent_palette_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_text_accent_palette.json"
                ),
                "preparation_text_palette_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_text_palette.bmp"
                ),
                "preparation_text_palette_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_text_palette.json"
                ),
                "preparation_accent_palette_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_accent_palette.bmp"
                ),
                "preparation_accent_palette_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_accent_palette.json"
                ),
                "preparation_menu_panel_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_menu_panel.bmp"
                ),
                "preparation_menu_panel_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_menu_panel.json"
                ),
                "preparation_cursor_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_cursor.bmp"
                ),
                "preparation_cursor_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_cursor.json"
                ),
                "command_cursor_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_command_cursor.bmp"
                ),
                "command_cursor_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_command_cursor.json"
                ),
                "confirmation_cursor_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_confirmation_cursor.bmp"
                ),
                "confirmation_cursor_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_confirmation_cursor.json"
                ),
                "map_hint_palette_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_map_hint_palette.bmp"
                ),
                "map_hint_palette_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_map_hint_palette.json"
                ),
                "preparation_dialog_panel_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_dialog_panel.bmp"
                ),
                "preparation_dialog_panel_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_preparation_dialog_panel.json"
                ),
                "action_background_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_background.bmp"
                ),
                "action_background_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_background.json"
                ),
                "action_icon_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_icon.bmp"
                ),
                "action_icon_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_icon.json"
                ),
                "action_cursor_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_cursor.bmp"
                ),
                "action_cursor_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_cursor.json"
                ),
                "action_start_hint_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_start_hint.bmp"
                ),
                "action_start_hint_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_start_hint.json"
                ),
                "action_back_hint_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_back_hint.bmp"
                ),
                "action_back_hint_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_back_hint.json"
                ),
                "action_actor_stats_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_actor_stats.bmp"
                ),
                "action_actor_stats_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_action_actor_stats.json"
                ),
                "result_background_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_background.bmp"
                ),
                "result_background_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_background.json"
                ),
                "result_panel_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_panel.bmp"
                ),
                "result_panel_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_panel.json"
                ),
                "result_naruto_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_naruto.bmp"
                ),
                "result_naruto_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_naruto.json"
                ),
                "result_sasuke_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_sasuke.bmp"
                ),
                "result_sasuke_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_sasuke.json"
                ),
                "result_sakura_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_sakura.bmp"
                ),
                "result_sakura_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_sakura.json"
                ),
                "result_total_palette_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_total_palette.bmp"
                ),
                "result_total_palette_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_result_total_palette.json"
                ),
            }
            for key, expected in checked_in.items():
                self.assertEqual(
                    expected.read_bytes(),
                    outputs[key].read_bytes(),
                    key,
                )


if __name__ == "__main__":
    unittest.main()
