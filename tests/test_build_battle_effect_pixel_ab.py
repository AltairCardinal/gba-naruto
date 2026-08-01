from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-11-cross-shuriken.json"


class BattleEffectPixelAbBuilderTests(unittest.TestCase):
    def setUp(self):
        from tools import build_battle_effect_pixel_ab

        self.builder = build_battle_effect_pixel_ab

    def test_group11_profile_builds_same_topology_one_byte_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "pair"
            result = self.builder.build_pair(ROOT, PROFILE, output)

            self.assertEqual(result["schema"], "battle-effect-pixel-ab-build-v1")
            self.assertEqual(result["profile_id"], "group-11-cross-shuriken")
            self.assertEqual(result["binding"]["ninja_tool_id"], 1)
            self.assertEqual(result["binding"]["encoded_action_id"], 129)
            self.assertEqual(result["binding"]["sequence_id"], 13)
            self.assertEqual(result["binding"]["group_id"], 11)
            self.assertEqual(result["edit"]["graphics_byte_offset"], 0x16)
            self.assertEqual(result["edit"]["screen_xy"], [172, 61])
            self.assertTrue(result["same_patch_topology"])
            self.assertTrue(result["same_encoded_size"])

            baseline = (output / result["variants"]["baseline"]["graphics_path"]).read_bytes()
            candidate = (output / result["variants"]["candidate"]["graphics_path"]).read_bytes()
            changed = [
                index
                for index, pair in enumerate(zip(baseline, candidate))
                if pair[0] != pair[1]
            ]
            self.assertEqual(changed, [0x16])
            self.assertEqual((baseline[0x16], candidate[0x16]), (0x21, 0x22))
            self.assertEqual(
                result["variants"]["baseline"]["encoded_graphics_size"],
                488,
            )
            self.assertEqual(
                result["variants"]["candidate"]["encoded_graphics_size"],
                488,
            )
            for variant in ("baseline", "candidate"):
                ledger = result["variants"][variant]["patch_ledger"]
                self.assertEqual(len(ledger), 2)
                self.assertEqual(ledger[0]["kind"], "allocation")
                self.assertEqual(ledger[0]["offset"], 0xB40000)
                self.assertEqual(ledger[1]["kind"], "redirect")
                self.assertEqual(ledger[1]["offset"], 0x599174)

    def test_profile_tampering_fails_closed(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        mutations = (
            {"group_id": 10},
            {"sequence_id": 12},
            {"graphics_byte_offset": 0x17},
            {"before_byte": 0x20},
            {"input_state_sha256": "0" * 64},
            {"input_evidence_sha256": "0" * 64},
            {"graphics_allocation_offset": 0xB41000},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(
                dir=ROOT / "build"
            ) as tmp:
                altered = copy.deepcopy(profile)
                altered.update(mutation)
                path = Path(tmp) / "profile.json"
                path.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.builder.build_pair(ROOT, path, Path(tmp) / "out")

    def test_rejects_nonempty_output_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            output.mkdir()
            marker = output / "keep"
            marker.write_text("user", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty"):
                self.builder.build_pair(ROOT, PROFILE, output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "user")

    def test_rejects_external_profile_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile.json"
            profile.write_bytes(PROFILE.read_bytes())
            output = Path(tmp) / "out"
            with self.assertRaisesRegex(ValueError, "profile.*repository"):
                self.builder.build_pair(ROOT, profile, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
