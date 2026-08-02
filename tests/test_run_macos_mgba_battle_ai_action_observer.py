from __future__ import annotations

import importlib
import unittest


class BattleAiActionObserverRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = importlib.import_module(
            "tools.run_macos_mgba_battle_ai_action_observer"
        )

    def valid_payload(self) -> dict[str, object]:
        return {
            "schema": "battle-ai-action-observer-v4",
            "run_id": "0123456789abcdef0123456789abcdef",
            "frame": 1087,
            "capture_frame_limit": 1800,
            "rom_sha256": "a" * 64,
            "input_state_sha256": "b" * 64,
            "script_sha256": "c" * 64,
            "inputs": [
                {"key": "A", "down_frame": 60, "up_frame": 68, "hold_frames": 8},
                {"key": "A", "down_frame": 420, "up_frame": 428, "hold_frames": 8},
            ],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "skipped_action_ids": [0],
            "events": [
                {
                    "address": "0x0807A22C",
                    "cycle": "4569400000",
                    "runtime_pointer": "0x02026CB8",
                    "action_address": "0x02027428",
                    "action_id": 0,
                    "candidate_pointer": "0x02030E90",
                    "source_action_address": "0x02030E9C",
                    "source_action_id": 0,
                    "r5": "0x0202680C",
                },
                {
                    "address": "0x0807A22C",
                    "cycle": "4569400752",
                    "runtime_pointer": "0x02026CB8",
                    "action_address": "0x02027428",
                    "action_id": 61,
                    "candidate_pointer": "0x02030E90",
                    "source_action_address": "0x02030E9C",
                    "source_action_id": 61,
                    "r5": "0x0202680C",
                },
            ],
            "selection": {
                "address": "0x0807A22C",
                "cycle": "4569400752",
                "runtime_pointer": "0x02026CB8",
                "action_address": "0x02027428",
                "action_id": 61,
                "candidate_pointer": "0x02030E90",
                "source_action_address": "0x02030E9C",
                "source_action_id": 61,
                "r5": "0x0202680C",
            },
        }

    def test_accepts_a_fresh_action61_runtime_copy(self):
        payload = self.valid_payload()
        selection = self.runner.validate_observer_payload(
            payload,
            run_id=str(payload["run_id"]),
            rom_sha256="a" * 64,
            input_state_sha256="b" * 64,
            script_sha256="c" * 64,
            skipped_action_ids=[0],
            expected_inputs=payload["inputs"],
        )
        self.assertEqual(selection["action_id"], 61)

    def test_rejects_stale_pointer_or_hidden_input(self):
        payload = self.valid_payload()
        payload["selection"] = dict(payload["selection"], runtime_pointer="0x020240C0")
        with self.assertRaisesRegex(self.runner.ReplayError, "runtime pointer"):
            self.runner.validate_observer_payload(
                payload,
                run_id=str(payload["run_id"]),
                rom_sha256="a" * 64,
                input_state_sha256="b" * 64,
                script_sha256="c" * 64,
                skipped_action_ids=[0],
                expected_inputs=payload["inputs"],
            )
        payload = self.valid_payload()
        payload["automatic_inputs"] = [{"key": "A"}]
        with self.assertRaisesRegex(self.runner.ReplayError, "implicit inputs"):
            self.runner.validate_observer_payload(
                payload,
                run_id=str(payload["run_id"]),
                rom_sha256="a" * 64,
                input_state_sha256="b" * 64,
                script_sha256="c" * 64,
                skipped_action_ids=[0],
                expected_inputs=payload["inputs"],
            )
        payload = self.valid_payload()
        payload["selection"] = dict(payload["selection"], source_action_id=5)
        payload["events"][-1] = dict(payload["events"][-1], source_action_id=5)
        with self.assertRaisesRegex(self.runner.ReplayError, "source action"):
            self.runner.validate_observer_payload(
                payload,
                run_id=str(payload["run_id"]),
                rom_sha256="a" * 64,
                input_state_sha256="b" * 64,
                script_sha256="c" * 64,
                skipped_action_ids=[0],
                expected_inputs=payload["inputs"],
            )

    def test_rejects_missing_selection_at_the_frame_limit(self):
        payload = self.valid_payload()
        payload["frame"] = 1800
        payload["selection"] = None
        with self.assertRaisesRegex(self.runner.ReplayError, "no AI action selection"):
            self.runner.validate_observer_payload(
                payload,
                run_id=str(payload["run_id"]),
                rom_sha256="a" * 64,
                input_state_sha256="b" * 64,
                script_sha256="c" * 64,
                skipped_action_ids=[0],
                expected_inputs=payload["inputs"],
            )

    def test_rejects_an_unskipped_event_before_the_selection(self):
        payload = self.valid_payload()
        payload["events"][0]["action_id"] = 5
        payload["events"][0]["source_action_id"] = 5
        with self.assertRaisesRegex(self.runner.ReplayError, "unskipped action"):
            self.runner.validate_observer_payload(
                payload,
                run_id=str(payload["run_id"]),
                rom_sha256="a" * 64,
                input_state_sha256="b" * 64,
                script_sha256="c" * 64,
                skipped_action_ids=[0],
                expected_inputs=payload["inputs"],
            )

    def test_parser_uses_the_fixed_script_and_current_profile(self):
        destinations = {action.dest for action in self.runner.build_parser()._actions}
        self.assertIn("toolchain_profile", destinations)
        self.assertIn("skip_action_id", destinations)
        self.assertIn("input_event", destinations)
        self.assertNotIn("script", destinations)
        self.assertNotIn("build_manifest", destinations)

    def test_input_events_are_explicit_and_non_overlapping(self):
        events = self.runner.parse_observer_input_events(
            ["A:60:68", "A:420:428"]
        )
        self.assertEqual(events, self.valid_payload()["inputs"])
        with self.assertRaisesRegex(self.runner.ReplayError, "overlap"):
            self.runner.parse_observer_input_events(["A:60:68", "B:67:70"])


if __name__ == "__main__":
    unittest.main()
