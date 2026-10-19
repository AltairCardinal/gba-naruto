import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OBSERVER = ROOT / "tools" / "butano" / "mgba_manual_battle_observer.lua"
LAUNCHER = ROOT / "tools" / "butano" / "start_manual_battle_observer.sh"
LATEST = ROOT / "artifacts" / "manual-battle-observer-latest.txt"


class ManualBattleObserverScriptTest(unittest.TestCase):
    def test_observer_records_manual_input_and_stall_state_without_driving_game(self):
        self.assertTrue(OBSERVER.is_file())
        source = OBSERVER.read_text(encoding="utf-8")

        for token in (
            "MGBA_MANUAL_BATTLE_OBSERVER_OUTPUT_DIR",
            "MGBA_MANUAL_BATTLE_OBSERVER_BATTLE_TELEMETRY_ADDRESS",
            "MGBA_MANUAL_BATTLE_OBSERVER_CAMPAIGN_TELEMETRY_ADDRESS",
            "MGBA_MANUAL_BATTLE_OBSERVER_ASSERT_ADDRESS",
            "manual-battle-trace.jsonl",
            "observer-ready.json",
            "emu:getKeys()",
            "emu:readRegister",
            "emu:setBreakpoint",
            '"assert-hit"',
            "presentation_combat_stage",
            "presentation_combat_stage_frame",
            "presentation_combat_stage = u32(364)",
            "presentation_combat_stage_frame = u32(368)",
            "selected_character_id",
            "selected_action_id",
            "last_resolved_action_id",
            "cursor_unit_id",
            "render_stage",
            "focus_armed",
            "stall_threshold_frames",
            "stall-snapshot-",
            "emu:saveStateFile",
            "emu:screenshot",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

        for forbidden in (
            "emu:addKey",
            "emu:clearKey",
            "emu:setKeys",
            "emu:write8",
            "emu:write16",
            "emu:write32",
            "emu:loadState",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_launcher_uses_guard_and_current_elf_symbols(self):
        self.assertTrue(LAUNCHER.is_file())
        source = LAUNCHER.read_text(encoding="utf-8")

        for token in (
            "tools/run_guarded.py",
            "build/resource-guard/heavy.lock",
            "konoha_battle_runtime_telemetry",
            "konoha_battle_campaign_runtime_telemetry",
            "_ZN3_bn6assert4showEPKcS2_S2_iRKN2bn12istring_baseE",
            "mgba_manual_battle_observer.lua",
            "butano-sequel/butano-sequel.gba",
            "konoha-battle-manual-observer.gba",
            "konoha-battle-manual-observer.sav",
            "manual-battle-observer-latest.txt",
            "MGBA_MANUAL_BATTLE_OBSERVER_OUTPUT_DIR",
            "MGBA_MANUAL_BATTLE_OBSERVER_BATTLE_TELEMETRY_ADDRESS",
            "MGBA_MANUAL_BATTLE_OBSERVER_CAMPAIGN_TELEMETRY_ADDRESS",
            "MGBA_MANUAL_BATTLE_OBSERVER_ASSERT_ADDRESS",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertNotIn(
            "konoha-battle-acceptance-clean.gba",
            source,
        )

    def test_launcher_check_mode_is_portable_and_does_not_start_a_run(self):
        source = LAUNCHER.read_text(encoding="utf-8")
        self.assertTrue(source.startswith("#!/bin/sh\n"))
        self.assertNotIn("${0:A:h}", source)
        self.assertIn("--check", source)

        pointer_before = (
            LATEST.read_bytes() if LATEST.is_file() else None
        )
        for command in (
            [str(LAUNCHER), "--check"],
            ["/bin/sh", str(LAUNCHER), "--check"],
        ):
            with self.subTest(command=command):
                completed = subprocess.run(
                    command,
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertIn("启动器检查通过", completed.stdout)
                self.assertIn("战斗遥测地址", completed.stdout)
                self.assertIn("Butano 断言地址", completed.stdout)

        pointer_after = (
            LATEST.read_bytes() if LATEST.is_file() else None
        )
        self.assertEqual(pointer_after, pointer_before)


if __name__ == "__main__":
    unittest.main()
