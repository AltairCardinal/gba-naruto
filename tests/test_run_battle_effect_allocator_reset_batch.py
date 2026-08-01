import importlib
import json
import tempfile
import unittest
from pathlib import Path


class BattleEffectAllocatorResetBatchTests(unittest.TestCase):
    def test_prepares_both_sides_as_a_single_variable_pair(self):
        runner = importlib.import_module(
            "tools.run_battle_effect_allocator_reset_batch"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            side0 = runner.prepare_case(root, side=0)
            side1 = runner.prepare_case(root, side=1)

            profile0 = json.loads(side0["profile"].read_text(encoding="utf-8"))
            profile1 = json.loads(side1["profile"].read_text(encoding="utf-8"))
            self.assertEqual(profile0["side"], 0)
            self.assertEqual(profile1["side"], 1)
            self.assertEqual(profile0["sequence_id"], profile1["sequence_id"])
            self.assertEqual(profile0["group_id"], profile1["group_id"])
            self.assertNotEqual(side0["rom_sha256"], side1["rom_sha256"])
            self.assertEqual(
                set(profile0) ^ set(profile1),
                set(),
            )

    def test_command_routes_each_case_through_the_guarded_capture_runner(self):
        runner = importlib.import_module(
            "tools.run_battle_effect_allocator_reset_batch"
        )
        with tempfile.TemporaryDirectory() as temporary:
            case = runner.prepare_case(Path(temporary), side=1)
            command = runner.build_case_command(
                binary=Path("/tmp/mGBA"),
                binary_sha256="ab" * 32,
                toolchain_profile=Path("/tmp/profile.json"),
                case=case,
                wall_timeout_s=60,
                idle_timeout_s=25,
            )

            self.assertEqual(command[1], str(runner.SINGLE_RUNNER))
            self.assertIn(str(case["guard_summary"]), command)
            self.assertIn(str(case["profile"]), command)


if __name__ == "__main__":
    unittest.main()
