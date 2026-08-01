import importlib
import unittest


class ControlledBattleEffectCaptureRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = importlib.import_module(
            "tools.run_macos_mgba_controlled_battle_effect_capture"
        )

    def test_payload_requires_spawn_plus_ordered_global_transaction(self):
        expected = {
            "group_id": 3,
            "sequence_id": 3,
            "definition_pointer": 0x083425D8,
            "animation_pointer": 0x083426CC,
        }
        payload = {
            "schema": "mgba-controlled-battle-effect-capture-v1",
            "outcome": "binder-plus-three-phase-captured",
            "group_id": 3,
            "sequence_id": 3,
            "definition_pointer": "0x083425D8",
            "animation_pointer": "0x083426CC",
            "inputs": [],
            "automatic_inputs": [],
            "recovery_inputs": [],
            "scratch_before": 0,
            "scratch_after": 1,
            "phases": [
                {"name": "binder-return", "address": "0x0809E85A", "cycle": "10"},
                {"name": "renderer-post", "address": "0x08063328", "cycle": "20"},
                {"name": "submit-post", "address": "0x08061126", "cycle": "30"},
                {"name": "ack-post", "address": "0x080612AA", "cycle": "40"},
            ],
        }
        self.runner.validate_controlled_payload(payload, expected)
        for mutation in (
            {"scratch_after": 0},
            {"sequence_id": 14},
            {"phases": payload["phases"][:3]},
            {"automatic_inputs": ["A"]},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(
                self.runner.ReplayError
            ):
                self.runner.validate_controlled_payload({**payload, **mutation}, expected)

    def test_cli_error_path_is_defined(self):
        self.assertIs(self.runner.sys.stderr, __import__("sys").stderr)


if __name__ == "__main__":
    unittest.main()
