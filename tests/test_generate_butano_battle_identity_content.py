import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PINGFANG = Path("/System/Library/Fonts/PingFang.ttc")


class GenerateButanoBattleIdentityContentTest(unittest.TestCase):
    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_facing_instruction_uses_every_original_full_height_glyph(self):
        from tools.generate_butano_battle_identity_content import (
            ASCII_GLYPH_COUNT,
            ORIGINAL_UI_BACKGROUND_COLOR,
            ORIGINAL_UI_FOREGROUND_INDEX,
            ORIGINAL_UI_MIDTONE_COLORS,
            ORIGINAL_UI_MIDTONE_INDEX,
            ORIGINAL_UI_SHADOW_COLORS,
            ORIGINAL_UI_SHADOW_INDEX,
            SCENARIO_41_ORIGINAL_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            generate_ui_font_bitmap,
            load_identity_content,
        )

        phrase = "请选择人物面对的方向"
        source_suffix = (
            "original/"
            "scenario-41-reference-v1__first-movedone-facing.png"
        )
        bitmap = generate_ui_font_bitmap(ROOT, PINGFANG)
        characters = load_identity_content(ROOT)["utf8_characters"]

        for index, character in enumerate(phrase):
            with self.subTest(character=character):
                source_path, left, top = (
                    SCENARIO_41_ORIGINAL_GLYPH_SOURCES[character]
                )
                self.assertTrue(source_path.endswith(source_suffix))
                self.assertEqual((left, top), (8 + index * 8, 136))
                with Image.open(ROOT / source_path) as source:
                    expected = [
                        0
                        if color == ORIGINAL_UI_BACKGROUND_COLOR
                        else ORIGINAL_UI_SHADOW_INDEX
                        if color in ORIGINAL_UI_SHADOW_COLORS
                        else ORIGINAL_UI_MIDTONE_INDEX
                        if color in ORIGINAL_UI_MIDTONE_COLORS
                        else ORIGINAL_UI_FOREGROUND_INDEX
                        for color in source.convert("RGB").crop(
                            (left, top, left + 8, top + 16)
                        ).get_flattened_data()
                    ]
                glyph_index = (
                    ASCII_GLYPH_COUNT + characters.index(character)
                )
                actual = list(
                    bitmap.crop(
                        (
                            0,
                            glyph_index * UI_GLYPH_HEIGHT,
                            8,
                            (glyph_index + 1) * UI_GLYPH_HEIGHT,
                        )
                    ).get_flattened_data()
                )
                self.assertEqual(actual, expected)

    def test_ui_ascii_digit_widths_match_original_eight_pixel_tile_grid(self):
        from tools.generate_butano_battle_identity_content import (
            _load_ui_ascii_widths,
        )

        widths = _load_ui_ascii_widths(ROOT)
        self.assertEqual(
            [widths[ord(character) - 32] for character in "0123456789"],
            [8] * 10,
        )

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_duel_status_font_uses_compact_original_digits_and_slash(self):
        from tools.generate_butano_battle_identity_content import (
            ASCII_GLYPH_COUNT,
            DUEL_STATUS_ASCII_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            generate_duel_status_font_header,
            generate_duel_status_font_bitmap,
        )

        bitmap = generate_duel_status_font_bitmap(ROOT, PINGFANG)
        header = generate_duel_status_font_header(ROOT)
        self.assertEqual(
            bitmap.size,
            (8, ASCII_GLYPH_COUNT * UI_GLYPH_HEIGHT),
        )
        self.assertNotIn("utf8_characters", header)
        self.assertNotIn("character_widths", header)
        self.assertEqual(
            set(DUEL_STATUS_ASCII_GLYPH_SOURCES),
            set("0123456789/"),
        )
        for character, (source_path, left, top) in (
            DUEL_STATUS_ASCII_GLYPH_SOURCES.items()
        ):
            with self.subTest(character=character):
                self.assertTrue(source_path.startswith("artifacts/"))
                glyph_index = ord(character) - ord("!")
                glyph = bitmap.crop(
                    (
                        0,
                        glyph_index * UI_GLYPH_HEIGHT,
                        8,
                        (glyph_index + 1) * UI_GLYPH_HEIGHT,
                    )
                )
                self.assertIsNotNone(glyph.getbbox())
                self.assertEqual(
                    set(glyph.crop((0, 8, 8, 16)).get_flattened_data()),
                    {0},
                )
                self.assertGreaterEqual(left, 0)
                self.assertGreaterEqual(top, 0)

    def test_hud_glyph_sources_start_below_the_frame_border(self):
        from tools.generate_butano_battle_identity_content import (
            SCENARIO_41_ORIGINAL_GLYPH_SOURCES,
        )

        for character in "漩涡鸣人本体待机力":
            with self.subTest(character=character):
                self.assertEqual(
                    SCENARIO_41_ORIGINAL_GLYPH_SOURCES[character][2],
                    136,
                )

    def test_target_status_uses_a_dedicated_full_height_glyph_role(self):
        from tools.generate_butano_battle_identity_content import (
            PREPARATION_BASE_GLYPH_SOURCES,
            PREPARATION_ORIGINAL_GLYPH_SOURCES,
            TARGET_STATUS_ASCII_GLYPH_SOURCES,
        )

        for character in "蜜蜂待机体力查克拉伤害成功率攻防快":
            with self.subTest(character=character):
                source_spec = (
                    PREPARATION_BASE_GLYPH_SOURCES.get(character) or
                    PREPARATION_ORIGINAL_GLYPH_SOURCES.get(character)
                )
                self.assertIsNotNone(source_spec)
                source, _, top = source_spec
                self.assertTrue(source.startswith("artifacts/"))
                self.assertGreaterEqual(top, 0)
        self.assertEqual(
            set(TARGET_STATUS_ASCII_GLYPH_SOURCES),
            set("0124569%"),
        )

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_action_menu_uses_full_height_original_glyph_role(self):
        from tools.generate_butano_battle_identity_content import (
            ACTION_MENU_ASCII_GLYPH_SOURCES,
            ACTION_MENU_ORIGINAL_GLYPH_SOURCES,
            ASCII_GLYPH_COUNT,
            ORIGINAL_UI_BACKGROUND_COLOR,
            ORIGINAL_UI_FOREGROUND_INDEX,
            ORIGINAL_UI_MIDTONE_COLORS,
            ORIGINAL_UI_MIDTONE_INDEX,
            ORIGINAL_UI_SHADOW_COLORS,
            ORIGINAL_UI_SHADOW_INDEX,
            UI_GLYPH_HEIGHT,
            generate_action_menu_font_bitmap,
            load_identity_content,
        )

        bitmap = generate_action_menu_font_bitmap(ROOT, PINGFANG)
        characters = load_identity_content(ROOT)["utf8_characters"]
        for character in "瞬身术影分组合拳十字手里剑用查克拉的力量进行间移动攻击指令返回蜂刺":
            with self.subTest(character=character):
                source_path, left, top = (
                    ACTION_MENU_ORIGINAL_GLYPH_SOURCES[character]
                )
                self.assertTrue(
                    source_path.endswith(
                        (
                            "turn4-skill-menu/frame.png",
                            "original-s49-real-enemy-turn-20260730-188/"
                            "frame-400.png",
                        )
                    )
                )
                original = Image.open(
                    ROOT / source_path
                ).convert("RGB")
                expected = [
                    0
                    if color == ORIGINAL_UI_BACKGROUND_COLOR
                    else ORIGINAL_UI_SHADOW_INDEX
                    if color in ORIGINAL_UI_SHADOW_COLORS
                    else ORIGINAL_UI_MIDTONE_INDEX
                    if color in ORIGINAL_UI_MIDTONE_COLORS
                    else ORIGINAL_UI_FOREGROUND_INDEX
                    for color in original.crop(
                        (left, top, left + 8, top + 16)
                    ).get_flattened_data()
                ]
                glyph_index = (
                    ASCII_GLYPH_COUNT + characters.index(character)
                )
                actual = list(
                    bitmap.crop(
                        (
                            0,
                            glyph_index * UI_GLYPH_HEIGHT,
                            8,
                            (glyph_index + 1) * UI_GLYPH_HEIGHT,
                        )
                    ).get_flattened_data()
                )
                self.assertEqual(actual, expected)
                self.assertTrue(any(actual[8 * 8 :]))
                if character == "攻":
                    self.assertIn(
                        ORIGINAL_UI_SHADOW_INDEX,
                        actual,
                    )
        for character in "漩涡鸣人消耗查克拉攻击力距离范围成功率":
            with self.subTest(detail_character=character):
                source_path, _, _ = (
                    ACTION_MENU_ORIGINAL_GLYPH_SOURCES[character]
                )
                self.assertTrue(
                    source_path.endswith(
                        (
                            "turn4-skill-menu/frame.png",
                            "first-turn-technique-menu.png",
                        )
                    )
                )
        self.assertEqual(
            set(ACTION_MENU_ASCII_GLYPH_SOURCES),
            set("01389X%"),
        )
        for character, (source_path, _, _) in (
            ACTION_MENU_ASCII_GLYPH_SOURCES.items()
        ):
            with self.subTest(ascii_character=character):
                self.assertTrue(
                    source_path.endswith(
                        (
                            "turn4-skill-menu/frame.png",
                            "first-turn-technique-menu.png",
                        )
                    )
                )
                glyph_index = ord(character) - ord("!")
                actual = list(
                    bitmap.crop(
                        (
                            0,
                            glyph_index * UI_GLYPH_HEIGHT,
                            8,
                            (glyph_index + 1) * UI_GLYPH_HEIGHT,
                        )
                    ).get_flattened_data()
                )
                self.assertTrue(any(actual[8 * 8 :]), character)

    def test_loads_complete_ordered_identity_catalogs(self):
        from tools.generate_butano_battle_identity_content import (
            load_identity_content,
        )

        content = load_identity_content(ROOT)
        self.assertEqual(len(content["units"]), 63)
        self.assertEqual(len(content["actions"]), 87)
        self.assertEqual(len(content["tools"]), 94)
        self.assertEqual(
            [entry["id"] for entry in content["units"]],
            list(range(63)),
        )
        self.assertEqual(
            [entry["id"] for entry in content["actions"]],
            list(range(87)),
        )
        self.assertEqual(
            [entry["id"] for entry in content["tools"]],
            list(range(94)),
        )
        self.assertEqual(
            content["units"][1],
            {
                "id": 1,
                "display_name": "漩涡鸣人",
                "dialogue_name": "鸣人",
                "dialogue_label_frame": 0,
                "exact": True,
            },
        )
        self.assertEqual(
            content["units"][2]["display_name"],
            "宇智波佐助",
        )
        self.assertEqual(
            content["units"][3]["display_name"],
            "春野樱",
        )
        self.assertEqual(
            [
                content["actions"][action_id]["display_name"]
                for action_id in (1, 2, 5, 7, 16, 86)
            ],
            [
                "分身术",
                "瞬身术",
                "忍者组合拳",
                "影分身术",
                "火遁术",
                "蜂刺",
            ],
        )
        self.assertTrue(content["actions"][86]["exact"])
        self.assertEqual(
            [
                content["tools"][tool_id]["display_name"]
                for tool_id in (1, 2, 17, 73, 93)
            ],
            [
                "十字手里剑",
                "八方手里剑",
                "风魔手里剑",
                "兵粮丸",
                "超万能丸",
            ],
        )
        self.assertEqual(
            len(content["utf8_characters"]),
            len(set(content["utf8_characters"])),
        )
        self.assertTrue(
            all(
                character in content["utf8_characters"]
                for entry in (
                    content["units"] +
                    content["actions"] +
                    content["tools"]
                )
                for character in entry["display_name"]
                if not 32 <= ord(character) <= 126
            )
        )
        self.assertTrue(
            all(
                character in content["utf8_characters"]
                for character in (
                    "开始任务是否可以援助木叶丸吧"
                    "队伍·装备查看地图储存角色"
                    "忍具卸下强化返回预览确定"
                    "！？？→攻击练习。用「」组合拳"
                    "不能使用忍术和忍具脱离为胜战斗败"
                    "移动查克拉休息行动结束"
                    "保护被蜜蜂受擅自到处跑所有赶走"
                    "傀儡人偶不会所以接近敌打倒同时"
                )
            )
        )
        self.assertEqual(
            sum(not entry["exact"] for entry in content["units"]),
            8,
        )
        self.assertEqual(
            sum(not entry["exact"] for entry in content["actions"]),
            8,
        )

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_generates_deterministic_header_and_complete_font(self):
        from tools.generate_butano_battle_identity_content import (
            generate_outputs,
            load_identity_content,
        )

        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first = Path(first_directory)
                second = Path(second_directory)
                first_outputs = generate_outputs(
                    ROOT,
                    first,
                    font_path=PINGFANG,
                )
                second_outputs = generate_outputs(
                    ROOT,
                    second,
                    font_path=PINGFANG,
                )
                self.assertEqual(
                    set(first_outputs),
                    {
                        "content_header",
                        "font_header",
                        "font_bitmap",
                        "font_metadata",
                        "ui_font_header",
                        "ui_font_bitmap",
                        "ui_font_metadata",
                        "result_font_header",
                        "result_font_bitmap",
                        "result_font_metadata",
                        "result_compact_font_header",
                        "result_compact_font_bitmap",
                        "result_compact_font_metadata",
                        "action_menu_font_header",
                        "action_menu_font_bitmap",
                        "action_menu_font_metadata",
                        "preparation_font_header",
                        "preparation_font_bitmap",
                        "preparation_font_metadata",
                        "target_status_font_header",
                        "target_status_font_bitmap",
                        "target_status_font_metadata",
                        "target_metrics_font_header",
                        "target_metrics_font_bitmap",
                        "target_metrics_font_metadata",
                        "duel_status_font_header",
                        "duel_status_font_bitmap",
                        "duel_status_font_metadata",
                    },
                )
                for key in first_outputs:
                    self.assertEqual(
                        first_outputs[key].read_bytes(),
                        second_outputs[key].read_bytes(),
                        key,
                    )

                content_header = first_outputs[
                    "content_header"
                ].read_text(encoding="utf-8")
                font_header = first_outputs["font_header"].read_text(
                    encoding="utf-8"
                )
                self.assertIn(
                    "std::array<battle_identity_record, 63>",
                    content_header,
                )
                self.assertIn(
                    "std::array<battle_identity_record, 87>",
                    content_header,
                )
                self.assertIn(
                    "std::array<battle_identity_record, 94>",
                    content_header,
                )
                self.assertIn(
                    "battle_ninja_tool_identity(std::size_t tool_id)",
                    content_header,
                )
                self.assertIn(
                    "battle_unit_dialogue_name(std::size_t character_id)",
                    content_header,
                )
                self.assertRegex(
                    content_header,
                    r"battle_unit_dialogue_label_graphics_index\(\s*"
                    r"std::size_t character_id\)",
                )
                for dialogue_name in ("鸣人", "佐助", "小樱"):
                    self.assertIn(
                        f'    "{dialogue_name}",',
                        content_header,
                    )
                self.assertIn('battle_identity_record{ "漩涡鸣人", true }',
                              content_header)
                self.assertIn('battle_identity_record{ "火遁术", true }',
                              content_header)
                self.assertIn('battle_identity_record{ "十字手里剑", true }',
                              content_header)
                self.assertIn('battle_identity_record{ "超万能丸", false }',
                              content_header)
                self.assertIn(
                    "battle_identity_font_utf8_characters_map",
                    font_header,
                )
                self.assertIn(
                    "bn::sprite_items::battle_identity_font",
                    font_header,
                )
                ui_font_header = first_outputs[
                    "ui_font_header"
                ].read_text(encoding="utf-8")
                self.assertIn(
                    "battle_ui_sprite_font",
                    ui_font_header,
                )
                self.assertIn(
                    "bn::sprite_items::battle_ui_font",
                    ui_font_header,
                )
                action_menu_font_header = first_outputs[
                    "action_menu_font_header"
                ].read_text(encoding="utf-8")
                self.assertIn(
                    "battle_action_menu_sprite_font",
                    action_menu_font_header,
                )
                self.assertIn(
                    "bn::sprite_items::battle_action_menu_font",
                    action_menu_font_header,
                )
                preparation_font_header = first_outputs[
                    "preparation_font_header"
                ].read_text(encoding="utf-8")
                self.assertIn(
                    "battle_preparation_sprite_font",
                    preparation_font_header,
                )
                self.assertIn(
                    "bn::sprite_items::battle_preparation_font",
                    preparation_font_header,
                )
                target_status_font_header = first_outputs[
                    "target_status_font_header"
                ].read_text(encoding="utf-8")
                self.assertIn(
                    "battle_target_status_sprite_font",
                    target_status_font_header,
                )
                self.assertIn(
                    "bn::sprite_items::battle_target_status_font",
                    target_status_font_header,
                )
                target_metrics_font_header = first_outputs[
                    "target_metrics_font_header"
                ].read_text(encoding="utf-8")
                self.assertIn(
                    "battle_target_metrics_sprite_font",
                    target_metrics_font_header,
                )
                self.assertIn(
                    "bn::sprite_items::battle_target_metrics_font",
                    target_metrics_font_header,
                )
                duel_status_font_header = first_outputs[
                    "duel_status_font_header"
                ].read_text(encoding="utf-8")
                self.assertIn(
                    "battle_duel_status_sprite_font",
                    duel_status_font_header,
                )
                self.assertIn(
                    "bn::sprite_items::battle_duel_status_font",
                    duel_status_font_header,
                )
                for original_ui_character in (
                    "请选择物面防御避系经验值分计"
                ):
                    self.assertIn(
                        f'"{original_ui_character}"',
                        ui_font_header,
                    )
                widths_source = re.search(
                    r"battle_identity_font_character_widths\[\] = \{"
                    r"(?P<body>.*?)\n\};",
                    font_header,
                    flags=re.DOTALL,
                )
                self.assertIsNotNone(widths_source)
                self.assertEqual(
                    len(
                        re.findall(
                            r"\b\d+\b",
                            widths_source.group("body"),
                        )
                    ),
                    1 + 94 + len(
                        load_identity_content(ROOT)["utf8_characters"]
                    ),
                )

                with Image.open(
                    first_outputs["font_bitmap"]
                ) as font_bitmap:
                    utf8_count = len(
                        load_identity_content(ROOT)["utf8_characters"]
                    )
                    self.assertEqual(
                        font_bitmap.size,
                        (16, (94 + utf8_count) * 16),
                    )
                    self.assertEqual(font_bitmap.mode, "P")
                    self.assertEqual(
                        sorted(
                            set(
                                font_bitmap.get_flattened_data()
                            )
                        ),
                        [0, 12, 14],
                    )
                    # The full-width space is intentionally blank, but every
                    # other generated UTF-8 glyph must contain foreground.
                    for glyph_index in range(
                        94, 94 + utf8_count
                    ):
                        glyph = font_bitmap.crop(
                            (
                                0,
                                glyph_index * 16,
                                16,
                                (glyph_index + 1) * 16,
                            )
                        )
                        if not glyph.getbbox():
                            character_index = glyph_index - 94
                            character = load_identity_content(ROOT)[
                                "utf8_characters"
                            ][character_index]
                            self.assertEqual(character, "\u3000")

                with Image.open(
                    first_outputs["ui_font_bitmap"]
                ) as ui_font_bitmap:
                    utf8_count = len(
                        load_identity_content(ROOT)["utf8_characters"]
                    )
                    self.assertEqual(
                        ui_font_bitmap.size,
                        (8, (94 + utf8_count) * 16),
                    )
                    characters = load_identity_content(ROOT)[
                        "utf8_characters"
                    ]
                    # Characters without an original UI sample still use
                    # the original battle UI's 8px visible cell inside the
                    # legal 8x16 OBJ tile, rather than a 14px story glyph.
                    fallback_index = characters.index("小")
                    fallback = ui_font_bitmap.crop(
                        (
                            0,
                            (94 + fallback_index) * 16,
                            8,
                            (95 + fallback_index) * 16,
                        )
                    )
                    self.assertIsNotNone(fallback.getbbox())
                    self.assertEqual(
                        set(
                            fallback.crop((0, 8, 8, 16))
                            .get_flattened_data()
                        ),
                        {0},
                    )

                    # Result statistics are laid out on an 8px baseline in
                    # the original. Their source sample must not capture the
                    # following row into the legal 8x16 sprite cell.
                    for character in (
                        "任", "务", "战", "斗",
                        "回", "合", "分", "计",
                    ):
                        compact_index = characters.index(character)
                        compact = ui_font_bitmap.crop(
                            (
                                0,
                                (94 + compact_index) * 16,
                                8,
                                (95 + compact_index) * 16,
                            )
                        )
                        self.assertEqual(
                            set(
                                compact.crop((0, 8, 8, 16))
                                .get_flattened_data()
                            ),
                            {0},
                            character,
                        )

                with Image.open(
                    first_outputs["preparation_font_bitmap"]
                ) as preparation_font_bitmap:
                    characters = load_identity_content(ROOT)[
                        "utf8_characters"
                    ]
                    character_index = characters.index("保")
                    glyph = preparation_font_bitmap.crop(
                        (
                            0,
                            (94 + character_index) * 16,
                            8,
                            (95 + character_index) * 16,
                        )
                    )
                    self.assertIsNotNone(glyph.getbbox())
                    occupied_rows = [
                        y
                        for y in range(16)
                        if set(
                            glyph.crop((0, y, 8, y + 1))
                            .get_flattened_data()
                        ) != {0}
                    ]
                    self.assertGreaterEqual(
                        max(occupied_rows) - min(occupied_rows),
                        10,
                    )

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_ui_font_reuses_original_scenario_41_glyph_elements(self):
        from tools.generate_butano_battle_identity_content import (
            ASCII_GLYPH_COUNT,
            SCENARIO_41_ORIGINAL_COMPACT_UI_GLYPHS,
            UI_GLYPH_HEIGHT,
            generate_ui_font_bitmap,
            load_identity_content,
        )

        menu = Image.open(
            ROOT
            / "artifacts/scenario-41-prebattle-reference-v1"
            / "screens/menu-0.png"
        ).convert("RGB")
        attack = Image.open(
            ROOT
            / "artifacts/scenario-41-screenshot-comparison-20260729-01"
            / "original"
            / "scenario-41-combat-reference-v1__attack-confirmation.png"
        ).convert("RGB")
        result = Image.open(
            ROOT
            / "artifacts/scenario-41-screenshot-comparison-20260729-01"
            / "original"
            / "scenario-41-extended-reference-v1__result.png"
        ).convert("RGB")
        status = Image.open(
            ROOT
            / "artifacts/runtime-checkpoints"
            / "scenario-49-battle-14-entry.ss9"
        ).convert("RGB")
        action_menu = Image.open(
            ROOT
            / "artifacts/scenario-41-screenshot-comparison-20260729-01"
            / "original"
            / "scenario-41-reference-v1__first-turn-technique-menu.png"
        ).convert("RGB")
        command_menu = Image.open(
            ROOT
            / "artifacts/scenario-49-battle-14-original-ui-boundaries-v1"
            / "turn4-command-menu"
            / "frame.png"
        ).convert("RGB")
        source_locations = {
            "援": (menu, 88, 8),
            "助": (menu, 96, 8),
            "队": (menu, 80, 56),
            "伍": (menu, 88, 56),
            "·": (menu, 96, 56),
            "装": (menu, 104, 56),
            "备": (menu, 112, 56),
            "查": (status, 136, 144),
            "看": (menu, 88, 72),
            "开": (menu, 80, 88),
            "始": (menu, 88, 88),
            "任": (result, 8, 112),
            "务": (result, 16, 112),
            "储": (menu, 80, 104),
            "存": (menu, 88, 104),
            "可": (attack, 88, 32),
            "以": (attack, 96, 32),
            "！": (menu, 136, 8),
            "？": (
                Image.open(
                    ROOT
                    / "artifacts/scenario-41-prebattle-reference-v1"
                    / "screens/confirmation-yes.png"
                ).convert("RGB"),
                88,
                72,
            ),
            "→": (
                Image.open(
                    ROOT
                    / "artifacts/scenario-41-prebattle-reference-v1"
                    / "screens/confirmation-yes.png"
                ).convert("RGB"),
                160,
                72,
            ),
            "攻": (action_menu, 160, 24),
            "击": (action_menu, 168, 24),
            "练": (menu, 24, 40),
            "习": (menu, 32, 40),
            "。": (menu, 40, 40),
            "用": (menu, 8, 56),
            "「": (menu, 16, 56),
            "忍": (command_menu, 32, 48),
            "者": (menu, 32, 56),
            "组": (menu, 40, 56),
            "合": (result, 8, 136),
            "拳": (menu, 56, 56),
            "」": (menu, 64, 56),
            "不": (menu, 8, 72),
            "能": (status, 136, 136),
            "使": (menu, 24, 72),
            "术": (command_menu, 16, 48),
            "和": (menu, 56, 72),
            "具": (command_menu, 40, 48),
            "・": (command_menu, 24, 48),
            "行": (command_menu, 16, 64),
            "动": (command_menu, 24, 64),
            "结": (command_menu, 32, 64),
            "束": (command_menu, 40, 64),
            "脱": (menu, 40, 104),
            "离": (action_menu, 168, 40),
            "为": (menu, 56, 104),
            "胜": (menu, 64, 104),
            "战": (result, 8, 120),
            "斗": (result, 16, 120),
            "回": (result, 8, 128),
        }
        characters = load_identity_content(ROOT)["utf8_characters"]
        bitmap = generate_ui_font_bitmap(ROOT, PINGFANG)

        def expected_mask(
            source: Image.Image,
            left: int,
            top: int,
            compact: bool,
        ) -> list[int]:
            height = 8 if compact else 16
            colors = list(
                source.crop(
                    (left, top, left + 8, top + height)
                ).get_flattened_data()
            )
            result = [
                0
                if color == (231, 247, 214)
                else 5
                if color in (
                    (173, 181, 156),
                    (189, 173, 222),
                )
                else 15
                if color in (
                    (115, 123, 107),
                    (148, 99, 239),
                )
                else 2
                for color in colors
            ]
            result.extend([0] * (8 * (16 - height)))
            return result

        for character, (
            source,
            left,
            top,
        ) in source_locations.items():
            with self.subTest(character=character):
                index = characters.index(character)
                glyph_top = (
                    ASCII_GLYPH_COUNT + index
                ) * UI_GLYPH_HEIGHT
                actual = list(
                    bitmap.crop(
                        (
                            0,
                            glyph_top,
                            8,
                            glyph_top + UI_GLYPH_HEIGHT,
                        )
                    ).get_flattened_data()
                )
                self.assertEqual(
                    actual,
                    expected_mask(
                        source,
                        left,
                        top,
                        character in
                        SCENARIO_41_ORIGINAL_COMPACT_UI_GLYPHS,
                    ),
                )

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_ui_font_uses_exact_status_labels_and_all_original_digits(self):
        from tools.generate_butano_battle_identity_content import (
            ASCII_GLYPH_COUNT,
            ORIGINAL_UI_ASCII_GLYPH_SOURCES,
            SCENARIO_41_ORIGINAL_COMPACT_UI_GLYPHS,
            SCENARIO_41_ORIGINAL_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            generate_ui_font_bitmap,
            load_identity_content,
        )

        entry_path = (
            "artifacts/runtime-checkpoints/"
            "scenario-49-battle-14-entry.ss9"
        )
        expected_labels = {
            "能": (entry_path, 136, 136),
            "力": (entry_path, 144, 136),
            "查": (entry_path, 136, 144),
            "克": (entry_path, 144, 144),
            "拉": (entry_path, 152, 144),
        }
        for character, source in expected_labels.items():
            with self.subTest(character=character):
                self.assertEqual(
                    SCENARIO_41_ORIGINAL_GLYPH_SOURCES[character],
                    source,
                )
                self.assertIn(
                    character,
                    SCENARIO_41_ORIGINAL_COMPACT_UI_GLYPHS,
                )

        self.assertEqual(
            set(ORIGINAL_UI_ASCII_GLYPH_SOURCES),
            set("0123456789"),
        )
        bitmap = generate_ui_font_bitmap(ROOT, PINGFANG)

        def expected_mask(source_path, left, top):
            with Image.open(ROOT / source_path) as source:
                colors = source.convert("RGB").crop(
                    (left, top, left + 8, top + 8)
                )
            pixels = [
                0
                if color == (231, 247, 214)
                else 5
                if color == (173, 181, 156)
                else 15
                if color == (115, 123, 107)
                else 2
                for color in colors.get_flattened_data()
            ]
            return pixels + [0] * 64

        characters = load_identity_content(ROOT)[
            "utf8_characters"
        ]
        for character, source in expected_labels.items():
            index = characters.index(character)
            top = (
                ASCII_GLYPH_COUNT + index
            ) * UI_GLYPH_HEIGHT
            self.assertEqual(
                list(
                    bitmap.crop(
                        (0, top, 8, top + UI_GLYPH_HEIGHT)
                    ).get_flattened_data()
                ),
                expected_mask(*source),
                character,
            )
        for character, source in (
            ORIGINAL_UI_ASCII_GLYPH_SOURCES.items()
        ):
            top = (
                ord(character) - ord("!")
            ) * UI_GLYPH_HEIGHT
            self.assertEqual(
                list(
                    bitmap.crop(
                        (0, top, 8, top + UI_GLYPH_HEIGHT)
                    ).get_flattened_data()
                ),
                expected_mask(*source),
                character,
            )

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_ui_font_uses_exact_compact_action_stat_labels(self):
        from tools.generate_butano_battle_identity_content import (
            ASCII_GLYPH_COUNT,
            SCENARIO_41_ORIGINAL_COMPACT_UI_GLYPHS,
            SCENARIO_41_ORIGINAL_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            generate_ui_font_bitmap,
            load_identity_content,
        )

        source_path = (
            "artifacts/scenario-41-screenshot-comparison-20260729-01/"
            "original/scenario-41-reference-v1__"
            "first-turn-technique-menu.png"
        )
        expected = {
            "消": (source_path, 160, 8),
            "耗": (source_path, 168, 8),
            "攻": (source_path, 160, 24),
            "击": (source_path, 168, 24),
            "距": (source_path, 160, 40),
            "离": (source_path, 168, 40),
            "范": (source_path, 160, 56),
            "围": (source_path, 168, 56),
            "成": (source_path, 160, 88),
            "功": (source_path, 168, 88),
            "率": (source_path, 176, 88),
        }
        bitmap = generate_ui_font_bitmap(ROOT, PINGFANG)
        characters = load_identity_content(ROOT)[
            "utf8_characters"
        ]
        for character, source in expected.items():
            with self.subTest(character=character):
                self.assertEqual(
                    SCENARIO_41_ORIGINAL_GLYPH_SOURCES[character],
                    source,
                )
                self.assertIn(
                    character,
                    SCENARIO_41_ORIGINAL_COMPACT_UI_GLYPHS,
                )
                with Image.open(ROOT / source[0]) as image:
                    colors = image.convert("RGB").crop(
                        (
                            source[1],
                            source[2],
                            source[1] + 8,
                            source[2] + 8,
                        )
                    )
                expected_pixels = [
                    0
                    if color == (231, 247, 214)
                    else 5
                    if color == (173, 181, 156)
                    else 15
                    if color == (115, 123, 107)
                    else 2
                    for color in colors.get_flattened_data()
                ] + [0] * 64
                index = characters.index(character)
                top = (
                    ASCII_GLYPH_COUNT + index
                ) * UI_GLYPH_HEIGHT
                self.assertEqual(
                    list(
                        bitmap.crop(
                            (0, top, 8, top + UI_GLYPH_HEIGHT)
                        ).get_flattened_data()
                    ),
                    expected_pixels,
                    )

    def test_ui_font_covers_dynamic_ninja_tool_quantity_label(self):
        from tools.generate_butano_battle_identity_content import (
            load_identity_content,
        )

        characters = load_identity_content(ROOT)[
            "utf8_characters"
        ]
        for character in (
            "忍具数量"
            "用查克拉的力量进行瞬间移动分身"
        ):
            with self.subTest(character=character):
                self.assertIn(character, characters)

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_preparation_font_keeps_full_height_sources_separate_from_compact_ui(self):
        from tools.generate_butano_battle_identity_content import (
            ASCII_GLYPH_COUNT,
            PREPARATION_BASE_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            generate_preparation_font_bitmap,
            load_identity_content,
                    )

        menu_source = (
            "artifacts/scenario-41-prebattle-reference-v1/"
            "screens/menu-0.png"
        )
        expected = {
            "查": (menu_source, 80, 72),
            "攻": (menu_source, 8, 40),
            "击": (menu_source, 16, 40),
            "离": (menu_source, 48, 104),
        }
        self.assertEqual(
            {
                character:
                PREPARATION_BASE_GLYPH_SOURCES[character]
                for character in expected
            },
            expected,
        )

        bitmap = generate_preparation_font_bitmap(ROOT, PINGFANG)
        characters = load_identity_content(ROOT)["utf8_characters"]
        for character, (source_path, left, top) in expected.items():
            with self.subTest(character=character):
                with Image.open(ROOT / source_path) as source:
                    colors = source.convert("RGB").crop(
                        (left, top, left + 8, top + 16)
                    )
                expected_pixels = [
                    0
                    if color == (231, 247, 214)
                    else 15
                    if color in (
                        (115, 123, 107),
                        (148, 99, 239),
                    )
                    else 5
                    if color in (
                        (173, 181, 156),
                        (189, 173, 222),
                    )
                    else 2
                    for color in colors.get_flattened_data()
                ]
                index = characters.index(character)
                glyph_top = (
                    ASCII_GLYPH_COUNT + index
                ) * UI_GLYPH_HEIGHT
                self.assertEqual(
                    list(
                        bitmap.crop(
                            (
                                0,
                                glyph_top,
                                8,
                                glyph_top + UI_GLYPH_HEIGHT,
                            )
                        ).get_flattened_data()
                    ),
                    expected_pixels,
                )

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_preparation_font_extracts_visible_bee_mission_glyphs_from_scenario_49(self):
        from tools.generate_butano_battle_identity_content import (
            ASCII_GLYPH_COUNT,
            ORIGINAL_UI_BACKGROUND_COLOR,
            ORIGINAL_UI_FOREGROUND_INDEX,
            ORIGINAL_UI_MIDTONE_COLORS,
            ORIGINAL_UI_MIDTONE_INDEX,
            ORIGINAL_UI_SHADOW_COLORS,
            ORIGINAL_UI_SHADOW_INDEX,
            PREPARATION_ORIGINAL_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            UI_GLYPH_WIDTH,
            generate_preparation_font_bitmap,
            load_identity_content,
        )

        source_path = (
            "artifacts/original-s49-task-menu-sequence-20260730-106/"
            "frame-00.png"
        )
        expected_sources = {
            **{
                character: (source_path, 8 + index * 8, 56)
                for index, character in enumerate(
                    "木叶丸擅自到处跑"
                )
                if index >= 3
            },
            **{
                character: (source_path, 8 + index * 8, 72)
                for index, character in enumerate(
                    "蜜蜂可以通过行动"
                )
                if index >= 4
            },
        }
        bitmap = generate_preparation_font_bitmap(ROOT, PINGFANG)
        characters = load_identity_content(ROOT)["utf8_characters"]
        with Image.open(ROOT / source_path) as source_image:
            source = source_image.convert("RGB")
            for character, source_spec in expected_sources.items():
                with self.subTest(character=character):
                    self.assertEqual(
                        PREPARATION_ORIGINAL_GLYPH_SOURCES[character],
                        source_spec,
                    )
                    _, left, top = source_spec
                    expected_pixels = [
                        0
                        if color == ORIGINAL_UI_BACKGROUND_COLOR
                        else ORIGINAL_UI_MIDTONE_INDEX
                        if color in ORIGINAL_UI_MIDTONE_COLORS
                        else ORIGINAL_UI_SHADOW_INDEX
                        if color in ORIGINAL_UI_SHADOW_COLORS
                        else ORIGINAL_UI_FOREGROUND_INDEX
                        for color in source.crop(
                            (
                                left,
                                top,
                                left + UI_GLYPH_WIDTH,
                                top + UI_GLYPH_HEIGHT,
                            )
                        ).get_flattened_data()
                    ]
                    index = characters.index(character)
                    glyph_top = (
                        ASCII_GLYPH_COUNT + index
                    ) * UI_GLYPH_HEIGHT
                    actual_pixels = list(
                        bitmap.crop(
                            (
                                0,
                                glyph_top,
                                UI_GLYPH_WIDTH,
                                glyph_top + UI_GLYPH_HEIGHT,
                            )
                        ).get_flattened_data()
                    )
                    self.assertEqual(actual_pixels, expected_pixels)

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_target_status_font_uses_its_own_exact_glyph_role(self):
        from tools.generate_butano_battle_identity_content import (
            ASCII_GLYPH_COUNT,
            ORIGINAL_UI_BACKGROUND_COLOR,
            ORIGINAL_UI_FOREGROUND_INDEX,
            ORIGINAL_UI_MIDTONE_COLORS,
            ORIGINAL_UI_MIDTONE_INDEX,
            ORIGINAL_UI_SHADOW_COLORS,
            ORIGINAL_UI_SHADOW_INDEX,
            TARGET_STATUS_ASCII_GLYPH_SOURCES,
            TARGET_STATUS_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            generate_target_status_font_bitmap,
            load_identity_content,
        )

        bitmap = generate_target_status_font_bitmap(ROOT, PINGFANG)
        characters = load_identity_content(ROOT)["utf8_characters"]

        def expected_pixels(source_path, left, top):
            with Image.open(ROOT / source_path) as source:
                colors = source.convert("RGB").crop(
                    (left, top, left + 8, top + UI_GLYPH_HEIGHT)
                )
            return [
                0
                if color == ORIGINAL_UI_BACKGROUND_COLOR
                else ORIGINAL_UI_SHADOW_INDEX
                if color == (231, 173, 140)
                else ORIGINAL_UI_MIDTONE_INDEX
                if color in ORIGINAL_UI_MIDTONE_COLORS
                else ORIGINAL_UI_SHADOW_INDEX
                if color in ORIGINAL_UI_SHADOW_COLORS
                else ORIGINAL_UI_FOREGROUND_INDEX
                for color in colors.get_flattened_data()
            ]

        for character, source_spec in TARGET_STATUS_GLYPH_SOURCES.items():
            with self.subTest(character=character):
                glyph_top = (
                    ASCII_GLYPH_COUNT + characters.index(character)
                ) * UI_GLYPH_HEIGHT
                self.assertEqual(
                    list(
                        bitmap.crop(
                            (0, glyph_top, 8, glyph_top + UI_GLYPH_HEIGHT)
                        ).get_flattened_data()
                    ),
                    expected_pixels(*source_spec),
                )

        for character, source_spec in (
            TARGET_STATUS_ASCII_GLYPH_SOURCES.items()
        ):
            with self.subTest(character=character):
                glyph_top = (
                    ord(character) - ord("!")
                ) * UI_GLYPH_HEIGHT
                self.assertEqual(
                    list(
                        bitmap.crop(
                            (0, glyph_top, 8, glyph_top + UI_GLYPH_HEIGHT)
                        ).get_flattened_data()
                    ),
                    expected_pixels(*source_spec),
                )

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_target_metrics_font_keeps_full_height_bottom_row_digits(self):
        from tools.generate_butano_battle_identity_content import (
            ORIGINAL_UI_BACKGROUND_COLOR,
            ORIGINAL_UI_FOREGROUND_INDEX,
            ORIGINAL_UI_MIDTONE_COLORS,
            ORIGINAL_UI_MIDTONE_INDEX,
            ORIGINAL_UI_SHADOW_COLORS,
            ORIGINAL_UI_SHADOW_INDEX,
            TARGET_METRICS_ASCII_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            generate_target_metrics_font_bitmap,
        )

        source_path, left, top = (
            TARGET_METRICS_ASCII_GLYPH_SOURCES["2"]
        )
        self.assertEqual((left, top), (216, 136))
        with Image.open(ROOT / source_path) as source:
            colors = source.convert("RGB").crop(
                (left, top, left + 8, top + UI_GLYPH_HEIGHT)
            )
        expected = [
            0
            if color == ORIGINAL_UI_BACKGROUND_COLOR
            else ORIGINAL_UI_MIDTONE_INDEX
            if color in ORIGINAL_UI_MIDTONE_COLORS
            else ORIGINAL_UI_SHADOW_INDEX
            if color in ORIGINAL_UI_SHADOW_COLORS
            else ORIGINAL_UI_FOREGROUND_INDEX
            for color in colors.get_flattened_data()
        ]
        bitmap = generate_target_metrics_font_bitmap(ROOT, PINGFANG)
        glyph_top = (ord("2") - ord("!")) * UI_GLYPH_HEIGHT
        self.assertEqual(
            list(
                bitmap.crop(
                    (0, glyph_top, 8, glyph_top + UI_GLYPH_HEIGHT)
                ).get_flattened_data()
            ),
            expected,
        )

    @unittest.skipUnless(PINGFANG.exists(), "PingFang SC is required")
    def test_checked_in_outputs_match_generator(self):
        from tools.generate_butano_battle_identity_content import (
            generate_outputs,
        )

        with tempfile.TemporaryDirectory() as directory:
            outputs = generate_outputs(
                ROOT,
                Path(directory),
                font_path=PINGFANG,
            )
            checked_in = {
                "content_header": (
                    ROOT
                    / "butano-sequel/game/include/konoha"
                    / "generated_battle_identity_content.h"
                ),
                "font_header": (
                    ROOT
                    / "butano-sequel/game/include/konoha"
                    / "battle_identity_sprite_font.h"
                ),
                "font_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_identity_font.bmp"
                ),
                "font_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_identity_font.json"
                ),
                "ui_font_header": (
                    ROOT
                    / "butano-sequel/game/include/konoha"
                    / "battle_ui_sprite_font.h"
                ),
                "ui_font_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_font.bmp"
                ),
                "ui_font_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_ui_font.json"
                ),
                "result_font_header": (
                    ROOT
                    / "butano-sequel/game/include/konoha"
                    / "battle_result_sprite_font.h"
                ),
                "result_font_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_result_font.bmp"
                ),
                "result_font_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_result_font.json"
                ),
                "result_compact_font_header": (
                    ROOT
                    / "butano-sequel/game/include/konoha"
                    / "battle_result_compact_sprite_font.h"
                ),
                "result_compact_font_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_result_compact_font.bmp"
                ),
                "result_compact_font_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_result_compact_font.json"
                ),
                "action_menu_font_header": (
                    ROOT
                    / "butano-sequel/game/include/konoha"
                    / "battle_action_menu_sprite_font.h"
                ),
                "action_menu_font_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_action_menu_font.bmp"
                ),
                "action_menu_font_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_action_menu_font.json"
                ),
                "preparation_font_header": (
                    ROOT
                    / "butano-sequel/game/include/konoha"
                    / "battle_preparation_sprite_font.h"
                ),
                "preparation_font_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_preparation_font.bmp"
                ),
                "preparation_font_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_preparation_font.json"
                ),
                "target_status_font_header": (
                    ROOT
                    / "butano-sequel/game/include/konoha"
                    / "battle_target_status_sprite_font.h"
                ),
                "target_status_font_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_target_status_font.bmp"
                ),
                "target_status_font_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_target_status_font.json"
                ),
                "target_metrics_font_header": (
                    ROOT
                    / "butano-sequel/game/include/konoha"
                    / "battle_target_metrics_sprite_font.h"
                ),
                "target_metrics_font_bitmap": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_target_metrics_font.bmp"
                ),
                "target_metrics_font_metadata": (
                    ROOT
                    / "butano-sequel/graphics"
                    / "battle_target_metrics_font.json"
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
