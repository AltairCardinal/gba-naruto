import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "tools" / "butano" / "summarize_manual_battle_observer.py"
)


class SummarizeManualBattleObserverTest(unittest.TestCase):
    def test_summary_reports_focus_presentation_stages_and_stall(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            records = [
                {
                    "observer_frame": 100,
                    "kind": "sasuke-taijutsu-focus-armed",
                    "phase": 8,
                    "selected_character_id": 2,
                    "selected_action_id": 5,
                    "last_resolved_action_id": 255,
                    "presentation_busy": 0,
                    "presentation_combat_stage": 8,
                    "last_control_error": 0,
                    "last_player_error": 0,
                    "pc": "0x08001000",
                },
                {
                    "observer_frame": 110,
                    "kind": "presentation-start",
                    "phase": 9,
                    "selected_character_id": 2,
                    "selected_action_id": 5,
                    "last_resolved_action_id": 5,
                    "presentation_busy": 1,
                    "presentation_combat_stage": 0,
                    "last_control_error": 0,
                    "last_player_error": 0,
                    "pc": "0x08002000",
                },
                {
                    "observer_frame": 300,
                    "kind": "presentation-stage",
                    "phase": 9,
                    "selected_character_id": 2,
                    "selected_action_id": 5,
                    "last_resolved_action_id": 5,
                    "presentation_busy": 1,
                    "presentation_combat_stage": 7,
                    "last_control_error": 0,
                    "last_player_error": 0,
                    "pc": "0x08003000",
                },
                {
                    "observer_frame": 500,
                    "kind": "stall",
                    "phase": 9,
                    "selected_character_id": 2,
                    "selected_action_id": 5,
                    "last_resolved_action_id": 5,
                    "presentation_busy": 0,
                    "presentation_combat_stage": 8,
                    "last_control_error": 0,
                    "last_player_error": 0,
                    "pc": "0x08004000",
                },
                {
                    "observer_frame": 501,
                    "kind": "assert-hit",
                    "pc": "0x08035640",
                    "lr": "0x08012345",
                    "sp": "0x03007F00",
                    "r0": "0x08090000",
                },
            ]
            trace = run_dir / "manual-battle-trace.jsonl"
            trace.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--run-dir",
                    str(run_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(completed.stdout)

        self.assertEqual(summary["record_count"], 5)
        self.assertTrue(summary["focus_armed"])
        self.assertTrue(summary["presentation_started"])
        self.assertEqual(summary["combat_stages"], [0, 7])
        self.assertEqual(summary["maximum_combat_stage"], 7)
        self.assertEqual(summary["stall_count"], 1)
        self.assertEqual(summary["assert_hit_count"], 1)
        self.assertEqual(
            summary["last_assert"]["pc"],
            "0x08035640",
        )
        self.assertEqual(summary["last_state"]["phase"], 9)
        self.assertEqual(summary["last_state"]["pc"], "0x08004000")


if __name__ == "__main__":
    unittest.main()
