import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENE = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "battle_preparation_scene.cpp"
)
SCENE_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_preparation_scene.h"
)
MAIN = ROOT / "butano-sequel" / "src" / "main.cpp"


class BattlePreparationOriginalUiTest(unittest.TestCase):
    def test_scene_uses_original_root_labels_and_dynamic_panels(self):
        source = SCENE.read_text(encoding="utf-8")

        for label in (
            "保护木叶丸不被蜜蜂攻击！",
            "保护木叶丸不受",
            '"傀儡人偶" : "蜜蜂"',
            "攻击。",
            "木叶丸擅自到处跑，所以不能攻击。",
            "所有的蜜蜂",
            "都赶走任务就算结束",
            "保护木叶丸不被傀儡人偶攻击！",
            "木叶丸不会攻击，",
            "所以不要让他去接近危险品。",
            "所有的傀儡人偶",
            "都赶走任务就算结束",
            "队伍·装备",
            "查看地图",
            "开始任务",
            "储存",
            "开始任务吗？",
        ):
            with self.subTest(label=label):
                self.assertIn(label, source)
        self.assertNotIn('"都赶走。"', source)

        self.assertNotIn(
            "bn_sprite_items_battle_ui_panel.h",
            source,
        )
        self.assertIn(
            "bn_regular_bg_items_battle_01_map_chunk_0.h",
            source,
        )
        self.assertIn(
            "bn_regular_bg_items_battle_preparation_background.h",
            source,
        )
        self.assertIn(
            "bn_regular_bg_items_"
            "battle_preparation_overview_background.h",
            source,
        )
        self.assertIn(
            "battle_preparation_sprite_font",
            source,
        )
        self.assertNotIn(
            "battle_ui_sprite_font",
            source,
        )
        self.assertNotIn(
            "bn_regular_bg_items_battle_preparation_confirmation_"
            "background.h",
            source,
        )
        self.assertIn(
            "bn_sprite_items_battle_ui_preparation_dialog_panel.h",
            source,
        )
        self.assertIn(
            "bn_sprite_items_battle_ui_preparation_menu_panel.h",
            source,
        )
        self.assertIn(
            "bn_sprite_items_battle_ui_preparation_cursor.h",
            source,
        )
        self.assertIn(
            "bn_sprite_items_battle_ui_confirmation_cursor.h",
            source,
        )
        self.assertIn(
            "render_preparation_menu_panel(",
            source,
        )
        self.assertIn(
            "render_preparation_root_cursor(",
            source,
        )
        cursor_function = source[
            source.index("void add_preparation_root_cursor("):
            source.index("void render_preparation_root_cursor(")
        ]
        self.assertIn(
            "palette_item().create_new_palette()",
            cursor_function,
        )
        for y in (-16, 0, 16, 32):
            with self.subTest(cursor_y=y):
                self.assertRegex(
                    source,
                    rf"add_preparation_root_cursor\(\s*"
                    rf"-44,\s*{y}",
                )
        for x, y, graphics_index in (
            (-32, -24, 0),
            (32, -24, 1),
            (-32, 40, 2),
            (32, 40, 3),
        ):
            with self.subTest(menu_x=x, menu_y=y):
                self.assertRegex(
                    source,
                    rf"add_preparation_menu_slice\(\s*"
                    rf"{x},\s*{y},\s*{graphics_index}",
                )
        for z_order in (50, 40, 30, 20):
            with self.subTest(z_order=z_order):
                self.assertIn(
                    f"set_z_order({z_order})",
                    source,
                )
        self.assertIn(
            "battle_preparation_phase::equipment_root",
            source,
        )
        self.assertIn(
            "battle_preparation_phase::overview",
            source,
        )
        self.assertIn(
            "render_preparation_mission_content(",
            source,
        )
        self.assertIn("campaign.chapter_id", source)
        self.assertIn(
            "battle_preparation_phase::map_preview",
            source,
        )
        self.assertRegex(
            source,
            r"state\.phase\s*==\s*"
            r"battle_preparation_phase::root\s*\|\|\s*"
            r"state\.phase\s*==\s*"
            r"battle_preparation_phase::\s*"
            r"start_confirmation",
        )
        self.assertIn(
            "bn_sprite_palette_items_"
            "battle_ui_preparation_text_palette.h",
            source,
        )
        self.assertIn(
            "bn_sprite_palette_items_"
            "battle_ui_preparation_accent_palette.h",
            source,
        )
        self.assertIn(
            "bn_sprite_palette_items_battle_ui_result_total_palette.h",
            source,
        )
        self.assertRegex(
            source,
            r"bn::sprite_palette_items::\s*"
            r"battle_ui_preparation_accent_palette",
        )
        self.assertRegex(
            source,
            r"bn::sprite_palette_items::\s*"
            r"battle_ui_preparation_text_palette",
        )
        self.assertRegex(
            source,
            r"bn::sprite_palette_items::\s*"
            r"battle_ui_result_total_palette",
        )
        self.assertRegex(
            source,
            r'generator\.generate\(\s*-112,\s*-32,\s*'
            r'"保护木叶丸不受"',
        )
        self.assertRegex(
            source,
            r'generator\.generate\(\s*-112,\s*48,\s*"把"',
        )
        self.assertRegex(
            source,
            r'puppet_mission\s*\?\s*-48\s*:\s*-64',
        )
        self.assertNotIn('"> 队伍·装备"', source)
        self.assertNotRegex(
            source,
            r'generator\.generate\(\s*-48,\s*-16.*?"→"',
        )
        self.assertRegex(
            source,
            r'generator\.generate\(\s*-72,\s*0,\s*"开始任务吗？"',
        )
        for x, graphics_index in (
            (-64, 0),
            (-32, 1),
            (0, 1),
            (32, 1),
            (64, 2),
        ):
            with self.subTest(dialog_x=x):
                self.assertRegex(
                    source,
                    rf"add_preparation_dialog_slice\(\s*"
                    rf"{x},\s*{graphics_index}",
                )
        self.assertIn("sprite.set_z_order(20)", source)
        self.assertIn("set_z_order(30)", source)
        confirmation_block = source[
            source.index(
                "if(state.phase ==\n"
                "            battle_preparation_phase::\n"
                "                    start_confirmation)"
            ):
            source.index(
                "if(state.phase == battle_preparation_phase::equip"
            )
        ]
        self.assertNotIn(
            "render_preparation_menu_panel(",
            confirmation_block,
        )
        self.assertNotIn(
            "render_preparation_root_cursor(",
            confirmation_block,
        )
        self.assertNotIn(
            "render_preparation_root_content(",
            confirmation_block,
        )
        self.assertIn(
            "render_preparation_confirmation_cursor(",
            confirmation_block,
        )
        confirmation_cursor_helper = source[
            source.index(
                "void render_preparation_confirmation_cursor("
            ):
            source.index("void render_preparation_text(")
        ]
        self.assertIn(
            "battle_ui_confirmation_cursor",
            confirmation_cursor_helper,
        )
        self.assertRegex(
            confirmation_cursor_helper,
            r"create_sprite\(\s*44,\s*"
            r"state\.start_confirmation_yes\s*\?\s*0\s*:\s*16",
        )
        self.assertNotRegex(
            confirmation_block,
            r'generator\.generate\([^;]*"→"',
        )
        self.assertNotIn(
            "battle_preparation_confirmation_background"
            ".create_bg",
            source,
        )

    def test_save_root_option_exits_to_verified_sram_save(self):
        header = SCENE_HEADER.read_text(encoding="utf-8")
        scene = SCENE.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")

        self.assertIn("save_requested", header)
        self.assertRegex(
            scene,
            r"battle_preparation_scene_exit::\s*"
            r"save_requested",
        )
        self.assertRegex(
            main,
            r"battle_preparation_scene_exit::\s*"
            r"save_requested",
        )
        self.assertIn(
            "save_battle_campaign_to_sram(",
            main,
        )
        self.assertIn("saved.verified", main)

    def test_postbattle_campaign_entry_shows_overview_before_root_menu(self):
        header = SCENE_HEADER.read_text(encoding="utf-8")
        scene = SCENE.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")

        self.assertIn("bool show_overview", header)
        self.assertIn("bool show_preparation_overview", main)
        self.assertRegex(
            main,
            r"run_battle_preparation_scene\(\s*"
            r"campaign,\s*show_preparation_overview\)",
        )
        self.assertIn(
            "show_preparation_overview = false;",
            main,
        )
        self.assertRegex(
            main,
            r"show_preparation_overview\s*=\s*"
            r"campaign\s*!=\s*campaign_checkpoint",
        )
        overview_block = scene[
            scene.index(
                "state.phase == battle_preparation_phase::overview"
            ):
            scene.index(
                "if(state.phase == battle_preparation_phase::root)"
            )
        ]
        self.assertIn(
            "render_preparation_mission_content(",
            overview_block,
        )
        self.assertNotIn(
            "render_preparation_root_content(",
            overview_block,
        )
        self.assertRegex(
            scene,
            r"(?s)state\.phase\s*==\s*"
            r"battle_preparation_phase::overview.*?"
            r"battle_preparation_overview_background",
        )


if __name__ == "__main__":
    unittest.main()
