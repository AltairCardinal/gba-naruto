import importlib
import json
import tempfile
import unittest
from pathlib import Path


class BattleEffectDirectSpawnBatchTests(unittest.TestCase):
    def test_prepares_both_group3_sides_and_both_group18_sequences(self):
        runner = importlib.import_module(
            "tools.run_battle_effect_direct_spawn_batch"
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)

            cases = [runner.prepare_case(output, case=case) for case in runner.CASES]

            self.assertEqual(
                [(row["group_id"], row["sequence_id"], row["side"]) for row in cases],
                [(3, 3, 0), (3, 3, 1), (18, 7, None), (18, 18, None)],
            )
            for direct_case, row in zip(runner.CASES, cases, strict=True):
                profile = json.loads(row["profile"].read_text(encoding="utf-8"))
                self.assertEqual(profile["input_mode"], "zero-input-active-state")
                self.assertEqual(profile["execution_mode"], "controlled-direct-spawn")
                self.assertEqual(profile["source_rom_sha256"], row["rom_sha256"])
                self.assertEqual(profile["allocator_reset"]["function"], "0x0807FDCC")
                self.assertEqual(
                    profile["allocator_reset"]["tile_start"],
                    f"0x{direct_case.allocator_tile_start:04X}",
                )
                self.assertEqual(
                    profile["allocator_reset"]["tile_end"],
                    f"0x{direct_case.allocator_tile_end:04X}",
                )
                self.assertEqual(profile["spawn"]["side"], direct_case.side)
                self.assertEqual(profile["spawn"]["x"], direct_case.spawn_x)
                self.assertEqual(profile["spawn"]["y"], direct_case.spawn_y)
                self.assertEqual(row["side"], direct_case.side)

    def test_selects_independent_cases_without_running_the_whole_batch(self):
        runner = importlib.import_module(
            "tools.run_battle_effect_direct_spawn_batch"
        )

        selected = runner.select_cases([
            "group-18-sequence-18-direct-spawn",
            "group-03-sequence-03-side-1-direct-spawn",
        ])
        self.assertEqual(
            [case.case_id for case in selected],
            [
                "group-18-sequence-18-direct-spawn",
                "group-03-sequence-03-side-1-direct-spawn",
            ],
        )
        self.assertEqual(runner.select_cases(None), list(runner.CASES))
        with self.assertRaises(ValueError):
            runner.select_cases(["group-99-sequence-99-direct-spawn"])

    def test_commands_use_the_existing_guarded_three_phase_runner(self):
        runner = importlib.import_module(
            "tools.run_battle_effect_direct_spawn_batch"
        )
        with tempfile.TemporaryDirectory() as temporary:
            case = runner.prepare_case(Path(temporary), case=runner.CASES[0])

            command = runner.build_case_command(
                binary=Path("/tmp/mGBA"),
                binary_sha256="a" * 64,
                toolchain_profile=Path("/tmp/profile.json"),
                case=case,
                wall_timeout_s=60,
                idle_timeout_s=25,
            )

            self.assertIn(str(runner.SINGLE_RUNNER), command)
            self.assertIn("--guard-summary", command)
            self.assertIn(str(case["profile"]), command)


if __name__ == "__main__":
    unittest.main()
