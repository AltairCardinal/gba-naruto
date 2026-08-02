from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    ROOT
    / "sequel/content/battle-effect-natural-pixel-ab/"
    "group-03-tool67-expiry.json"
)


class NaturalDelayedBattleEffectPixelAbRunnerTests(unittest.TestCase):
    def test_prepares_two_zero_input_natural_profiles(self):
        builder = importlib.import_module(
            "tools.build_natural_delayed_battle_effect_pixel_ab"
        )
        runner = importlib.import_module(
            "tools.run_natural_delayed_battle_effect_pixel_ab"
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_root = output / "build"
            build = builder.build_pair(ROOT, PROFILE, build_root)
            rows = [
                runner.prepare_variant(
                    output / "runs",
                    build_root=build_root,
                    build=build,
                    variant=variant,
                )
                for variant in ("baseline", "candidate")
            ]

            for variant, row in zip(("baseline", "candidate"), rows, strict=True):
                profile = json.loads(row["profile"].read_text(encoding="utf-8"))
                self.assertEqual(
                    profile["schema"], "battle-effect-phase-capture-profile-v1"
                )
                self.assertEqual(
                    profile["execution_mode"],
                    "natural-delayed-object-pixel-ab",
                )
                self.assertTrue(profile["natural_gameplay_route"])
                self.assertEqual(profile["input_mode"], "zero-input-active-state")
                self.assertEqual(profile["inputs"], [])
                self.assertEqual(profile["variant"], variant)
                self.assertEqual(profile["group_id"], 3)
                self.assertEqual(profile["sequence_id"], 3)
                self.assertEqual(profile["source_rom_sha256"], row["rom_sha256"])
                self.assertEqual(
                    profile["source_natural_phase_artifact"],
                    "artifacts/battle-effect-frame-phase-group3-natural-v1",
                )
                self.assertNotIn("allocator_reset", profile)
                self.assertNotIn("spawn", profile)


if __name__ == "__main__":
    unittest.main()
