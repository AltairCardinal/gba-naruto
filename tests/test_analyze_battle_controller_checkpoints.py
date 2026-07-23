import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_controller_checkpoints import (
    analyze_checkpoint,
    build_checkpoint_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom" / "base.gba"
STATES = ROOT / "notes" / "battle-controller-states-20260723.json"
CHECKPOINTS = ROOT / "artifacts" / "runtime-checkpoints"


class BattleControllerCheckpointAnalysisTest(unittest.TestCase):
    def test_binds_direct_controller_resume_to_state_interval(self):
        result = analyze_checkpoint(
            ROM,
            STATES,
            CHECKPOINTS / "scenario-41-controller-entry.ss9",
        )

        self.assertEqual(result["controller_state"], 0x0000)
        self.assertEqual(result["controller_state_hex"], "0x0000")
        self.assertEqual(result["binding_kind"], "direct_controller_resume")
        self.assertEqual(result["resume_pc"], "0x08073616")
        self.assertEqual(result["controller_frame"]["entry"], "0x080735CA")
        self.assertEqual(
            result["controller_caller"]["decoded_target"], "0x080732B4"
        )

    def test_binds_nested_checkpoint_only_with_validated_controller_ancestor(self):
        cases = {
            "scenario-41-player-turn.ss9": (0x3110, "0x08073C88", "0x0806F718"),
            "scenario-41-first-turn-technique-menu.ss9": (
                0x9200,
                "0x08074836",
                "0x08070DF8",
            ),
            "scenario-41-first-movedone-facing.ss9": (
                0x9000,
                None,
                None,
            ),
            "scenario-41-turn-1-complete.ss9": (
                0x1220,
                "0x08073780",
                "0x0808A588",
            ),
            "scenario-41-victory.ss9": (0x8000, "0x0807444E", "0x0807305C"),
        }

        for filename, (state, callsite, target) in cases.items():
            with self.subTest(filename=filename):
                result = analyze_checkpoint(ROM, STATES, CHECKPOINTS / filename)
                self.assertEqual(result["controller_state"], state)
                self.assertIn(
                    result["binding_kind"],
                    {"direct_controller_resume", "validated_controller_ancestor"},
                )
                if callsite:
                    self.assertEqual(result["controller_frame"]["callsite"], callsite)
                    self.assertEqual(
                        result["controller_frame"]["decoded_target"], target
                    )
                    self.assertLess(
                        int(result["controller_frame"]["stack_address"], 16),
                        int(result["controller_caller"]["stack_address"], 16),
                    )

    def test_rejects_observation_with_wrong_checkpoint_hash(self):
        observations = {
            "schema_version": 1,
            "observations": [
                {
                    "checkpoint": "artifacts/runtime-checkpoints/scenario-41-player-turn.ss9",
                    "sha256": "00" * 32,
                    "visible_phase": "player_move_selection",
                    "expected_controller_state": "0x3110",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observations.json"
            path.write_text(json.dumps(observations), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                build_checkpoint_manifest(ROOT, ROM, STATES, path)

    def test_builds_hash_bound_visible_phase_manifest(self):
        observations = (
            ROOT
            / "notes"
            / "battle-controller-checkpoint-observations-20260723.json"
        )
        result = build_checkpoint_manifest(ROOT, ROM, STATES, observations)

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["checkpoint_count"], 18)
        by_phase = {item["visible_phase"]: item for item in result["checkpoints"]}
        self.assertEqual(by_phase["player_move_selection"]["controller_state_hex"], "0x3110")
        self.assertEqual(by_phase["action_menu_initial"]["controller_state_hex"], "0x3000")
        self.assertEqual(by_phase["technique_menu"]["controller_state_hex"], "0x9200")
        self.assertEqual(by_phase["facing_selection"]["controller_state_hex"], "0x9000")
        self.assertEqual(by_phase["defense_confirmation"]["controller_state_hex"], "0x9100")
        self.assertEqual(by_phase["victory_presentation"]["controller_state_hex"], "0x8000")
        self.assertEqual(by_phase["scenario_45_enemy_planning"]["controller_state_hex"], "0x7000")
        self.assertEqual(by_phase["scenario_45_enemy_planning"]["current_side"], 1)
        self.assertEqual(by_phase["scenario_45_enemy_planning"]["current_unit_pointer"], "0x00000000")
        self.assertEqual(by_phase["scenario_45_enemy_resolution"]["controller_state_hex"], "0x8000")
        self.assertEqual(by_phase["scenario_45_enemy_resolution"]["current_unit"]["character_id"], 7)
        self.assertEqual(by_phase["scenario_45_enemy_resolution"]["current_unit"]["affiliation"], 1)
        self.assertEqual(by_phase["scenario_50_enemy_planning"]["controller_state_hex"], "0x7000")
        self.assertEqual(by_phase["scenario_50_enemy_resolution"]["controller_state_hex"], "0x8000")
        self.assertEqual(by_phase["scenario_50_enemy_resolution"]["current_unit"]["character_id"], 35)
        self.assertEqual(by_phase["scenario_50_enemy_resolution"]["current_unit"]["affiliation"], 1)

    def test_cli_generates_manifest_when_invoked_as_a_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bindings.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "analyze_battle_controller_checkpoints.py"),
                    "--root",
                    str(ROOT),
                    "--rom",
                    str(ROM),
                    "--states",
                    str(STATES),
                    "--observations",
                    str(
                        ROOT
                        / "notes"
                        / "battle-controller-checkpoint-observations-20260723.json"
                    ),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["checkpoint_count"], 18)


if __name__ == "__main__":
    unittest.main()
