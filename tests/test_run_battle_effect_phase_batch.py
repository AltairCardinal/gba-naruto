from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "sequel/content/battle-effect-phase-capture/observed-groups-batch-v1.json"


class BattleEffectPhaseBatchRunnerTests(unittest.TestCase):
    def test_production_spec_covers_the_four_missing_observed_groups(self):
        runner = importlib.import_module("tools.run_battle_effect_phase_batch")
        spec = runner.load_batch_spec(SPEC)
        self.assertEqual([row["group_id"] for row in spec["cases"]], [1, 2, 5, 14])
        self.assertEqual(len({row["profile_sha256"] for row in spec["cases"]}), 4)
        for row in spec["cases"]:
            self.assertEqual(
                runner.sha256_file(ROOT / row["profile"]),
                row["profile_sha256"],
            )

    def test_rom_overrides_are_unique_and_group_scoped(self):
        runner = importlib.import_module("tools.run_battle_effect_phase_batch")
        self.assertEqual(
            runner.parse_rom_overrides(["1=/tmp/one.gba", "14=/tmp/fourteen.gba"]),
            {1: Path("/tmp/one.gba"), 14: Path("/tmp/fourteen.gba")},
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            runner.parse_rom_overrides(["1=/tmp/a.gba", "1=/tmp/b.gba"])
        with self.assertRaisesRegex(ValueError, "GROUP=PATH"):
            runner.parse_rom_overrides(["bad"])

    def test_builds_one_guarded_single_case_command(self):
        runner = importlib.import_module("tools.run_battle_effect_phase_batch")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = runner.build_case_command(
                python="python3",
                binary=Path("/Applications/mGBA"),
                toolchain_profile=Path("profile.json"),
                binary_sha256="a" * 64,
                rom=Path("group.gba"),
                rom_sha256="b" * 64,
                profile=Path("group.json"),
                profile_sha256="c" * 64,
                case_root=root / "group-01",
                wall_timeout_s=40.0,
                idle_timeout_s=20.0,
            )
        self.assertEqual(command[0], "python3")
        self.assertIn("tools/run_macos_mgba_battle_effect_phase_capture.py", command[1])
        self.assertEqual(command[command.index("--expected-rom-sha256") + 1], "b" * 64)
        self.assertEqual(command[command.index("--output-dir") + 1], str(root / "group-01/output"))
        self.assertEqual(command[command.index("--guard-summary") + 1], str(root / "group-01/guard-summary.json"))

    def test_rejects_profile_paths_outside_the_repository(self):
        runner = importlib.import_module("tools.run_battle_effect_phase_batch")
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        spec["cases"][0]["profile"] = str(
            (ROOT / spec["cases"][0]["profile"]).resolve()
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "absolute-profile.json"
            path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "repository-relative"):
                runner.load_batch_spec(path)

    def test_rejects_parent_traversal_profile_paths(self):
        runner = importlib.import_module("tools.run_battle_effect_phase_batch")
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        spec["cases"][0]["profile"] = "../outside-profile.json"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "parent-profile.json"
            path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "repository-relative"):
                runner.load_batch_spec(path)

    def test_rejects_profile_symlinks_that_escape_the_repository(self):
        runner = importlib.import_module("tools.run_battle_effect_phase_batch")
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory(
            dir=ROOT
        ) as inside:
            outside_profile = Path(outside) / "outside-profile.json"
            outside_profile.write_text("{}\n", encoding="utf-8")
            link = Path(inside) / "profile.json"
            os.symlink(outside_profile, link)
            spec["cases"][0]["profile"] = link.relative_to(ROOT).as_posix()
            path = Path(outside) / "symlink-profile.json"
            path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "stay inside"):
                runner.load_batch_spec(path)


if __name__ == "__main__":
    unittest.main()
