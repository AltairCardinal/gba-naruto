import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "butano-sequel" / "src" / "main.cpp"
RUNTIME_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_runtime_scene.h"
)
RUNTIME_SOURCE = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "battle_runtime_scene.cpp"
)
FIXTURE_SOURCE = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "scenario_43_scene.cpp"
)
ROUTE_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_campaign_route.h"
)


class ButanoBattleCampaignRouteWiringTest(unittest.TestCase):
    def test_acceptance_rom_defaults_to_konohamaru_escort_battle(self):
        route = ROUTE_HEADER.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")

        self.assertRegex(
            route,
            r"battle_campaign_route_initial_scenario\s*=\s*49;",
        )
        self.assertRegex(
            route,
            r"\{\s*49,\s*14,\s*0,\s*50,",
        )
        self.assertIn(
            "battle_campaign_route_accepts_saved_scenario(",
            route,
        )
        self.assertRegex(
            main,
            r"if\(!\s*konoha::battle_campaign_route_"
            r"accepts_saved_scenario\(\s*campaign\.chapter_id\s*\)\)",
        )
        fallback = main.index(
            "if(! konoha::"
            "battle_campaign_route_accepts_saved_scenario("
        )
        prepare = main.index(
            "prepare_battle_campaign_stage(",
            fallback,
        )
        self.assertIn(
            "campaign = campaign_checkpoint;",
            main[fallback:prepare],
        )

    def test_main_uses_campaign_route_instead_of_fixture_chain(self):
        main = MAIN.read_text(encoding="utf-8")

        self.assertIn(
            '#include "konoha/battle_campaign_route.h"',
            main,
        )
        self.assertNotIn("scenario_43_scene.h", main)
        self.assertNotIn("run_scenario_43_scene", main)
        self.assertNotIn("run_battle_41_scene", main)
        self.assertIn("prepare_battle_campaign_stage(", main)
        self.assertIn("run_battle_campaign_stage(", main)
        self.assertIn("advance_battle_campaign_stage(", main)

    def test_main_does_not_override_scenario_49_default_equipment(self):
        main = MAIN.read_text(encoding="utf-8")

        self.assertNotIn(
            "campaign_checkpoint.characters[1].equipped_tools",
            main,
        )
        self.assertNotIn(
            "campaign_checkpoint.inventory.ninja_tools",
            main,
        )
        self.assertNotIn(
            "campaign_checkpoint.inventory.materials",
            main,
        )

    def test_route_advances_before_verified_save(self):
        main = MAIN.read_text(encoding="utf-8")
        advance = main.index("advance_battle_campaign_stage(")
        save = main.index(
            "save_battle_campaign_to_sram(",
            advance,
        )
        self.assertLess(advance, save)
        self.assertRegex(
            main[advance:save],
            r"campaign\s*=\s*campaign_checkpoint",
        )

    def test_visible_adapter_resolves_stage_into_generic_request(self):
        header = RUNTIME_HEADER.read_text(encoding="utf-8")
        source = RUNTIME_SOURCE.read_text(encoding="utf-8")

        self.assertIn(
            "run_battle_campaign_stage(",
            header,
        )
        adapter = re.search(
            r"battle_runtime_scene_exit\s+"
            r"run_battle_campaign_stage\(.*?\n\}",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(adapter)
        body = adapter.group(0)
        self.assertIn("battle_campaign_stage_for(", body)
        self.assertIn("request.battle_id", body)
        self.assertIn("stage->battle_id", body)
        self.assertIn("request.variant", body)
        self.assertIn("stage->variant", body)
        self.assertIn(
            "request.rng_seed = campaign.chapter_id",
            body,
        )
        self.assertNotIn(
            "request.rng_seed = stage->battle_id",
            body,
        )
        self.assertIn("request.campaign = &campaign", body)
        self.assertIn("run_battle_scene(request)", body)

    def test_diagnostic_fixture_file_no_longer_owns_a_sequence(self):
        fixture = FIXTURE_SOURCE.read_text(encoding="utf-8")

        self.assertNotIn("run_battle_09_scene()", fixture)
        self.assertNotIn("run_battle_11_scene()", fixture)
        self.assertNotIn(
            "run_battle_32_arena_fixture_scene()",
            fixture,
        )

    def test_campaign_route_transaction_workspace_reuses_sram_ewram(
        self,
    ):
        route = ROUTE_HEADER.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")

        self.assertIn(
            "struct battle_campaign_route_workspace",
            route,
        )
        self.assertIn(
            "battle_campaign_route_workspace& workspace",
            route,
        )
        self.assertRegex(
            main,
            r"BN_DATA_EWRAM_BSS static unsigned char\s*"
            r"campaign_shared_workspace_storage",
        )
        self.assertIn(
            "campaign_shared_workspace_size",
            main,
        )
        self.assertNotIn(
            "campaign_route_workspace_storage",
            main,
        )
        self.assertNotIn(
            "static\n"
            "            konoha::battle_campaign_sram_workspace\n"
            "                    campaign_sram_workspace",
            main,
        )
        self.assertIn(
            "konoha::battle_campaign_route_workspace&\n"
            "            campaign_route_workspace",
            main,
        )
        self.assertIn(
            "*reinterpret_cast<konoha::\n"
            "                            battle_campaign_route_workspace*>(",
            main,
        )
        self.assertIn(
            "prepare_battle_campaign_stage(\n"
            "                    campaign_checkpoint,\n"
            "                    campaign_route_workspace)",
            main,
        )
        self.assertIn(
            "advance_battle_campaign_stage(\n"
            "                                        campaign,\n"
            "                                        battle_exit,\n"
            "                                        campaign_route_workspace)",
            main,
        )


if __name__ == "__main__":
    unittest.main()
