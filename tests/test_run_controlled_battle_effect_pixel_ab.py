from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    ROOT
    / "sequel/content/battle-effect-controlled-pixel-ab/"
    "group-18-sequence-07-direct-spawn.json"
)
GROUP3_PROFILE = (
    ROOT
    / "sequel/content/battle-effect-controlled-pixel-ab/"
    "group-03-sequence-03-side-0-direct-spawn.json"
)


class ControlledBattleEffectPixelAbRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = importlib.import_module(
            "tools.run_controlled_battle_effect_pixel_ab"
        )
        self.builder = importlib.import_module(
            "tools.build_controlled_battle_effect_pixel_ab"
        )

    def test_prepares_two_zero_input_profiles_from_the_composed_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_root = output / "build"
            build = self.builder.build_pair(ROOT, PROFILE, build_root)
            prepared = [
                self.runner.prepare_variant(
                    output / "runs", build_root=build_root, build=build, variant=variant
                )
                for variant in ("baseline", "candidate")
            ]

            for variant, row in zip(("baseline", "candidate"), prepared, strict=True):
                profile = json.loads(row["profile"].read_text(encoding="utf-8"))
                self.assertEqual(profile["schema"], "battle-effect-phase-capture-profile-v1")
                self.assertEqual(profile["execution_mode"], "controlled-direct-spawn-pixel-ab")
                self.assertEqual(profile["input_mode"], "zero-input-active-state")
                self.assertEqual(profile["variant"], variant)
                self.assertFalse(profile["natural_gameplay_route"])
                self.assertEqual(profile["source_rom_sha256"], row["rom_sha256"])
                self.assertEqual(
                    profile["source_build_manifest"], "build/build-manifest.json"
                )
                self.assertEqual(row["group_id"], 18)
                self.assertEqual(row["sequence_id"], 7)

    def test_rejects_unknown_variant_before_creating_a_run_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_root = output / "build"
            build = self.builder.build_pair(ROOT, PROFILE, build_root)
            run_root = output / "runs"
            with self.assertRaisesRegex(ValueError, "variant"):
                self.runner.prepare_variant(
                    run_root, build_root=build_root, build=build, variant="other"
                )
            self.assertFalse(run_root.exists())

    def test_script_entrypoint_can_load_repository_modules(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/run_controlled_battle_effect_pixel_ab.py"),
                "--help",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_rejects_toolchain_profile_outside_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "profile.json"
            profile.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inside repository"):
                self.runner._repository_relative_file(profile, "toolchain profile")

    def test_prepares_group3_alias_split_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_root = output / "build"
            build = self.builder.build_pair(ROOT, GROUP3_PROFILE, build_root)
            row = self.runner.prepare_variant(
                output / "runs",
                build_root=build_root,
                build=build,
                variant="baseline",
            )
            profile = json.loads(row["profile"].read_text(encoding="utf-8"))
            self.assertEqual(profile["group_id"], 3)
            self.assertEqual(profile["sequence_id"], 3)
            self.assertEqual(profile["side"], 0)
            self.assertEqual(profile["allocator_reset"]["tile_start"], "0x0100")
            self.assertEqual(profile["allocator_reset"]["tile_end"], "0x039F")
            self.assertEqual(profile["allocator_reset"]["palette_start"], 4)
            self.assertEqual(profile["pixel_contract"]["screen_xy"], [129, 51])


if __name__ == "__main__":
    unittest.main()
