import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.build_motion_effect_parameter_pixel_ab import build_pair


ROOT = Path(__file__).resolve().parents[1]
PROFILE = (
    ROOT
    / "sequel/content/motion-effect-parameter-pixel-ab/"
    "group-03-record-00-y-offset.json"
)
TABLE_OFFSET = 0x53EE98
PATCH_OFFSET = TABLE_OFFSET + 4


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class BuildMotionEffectParameterPixelAbTests(unittest.TestCase):
    def test_builds_probe_free_single_byte_pair_from_the_natural_group3_route(self):
        base = (ROOT / "rom/base.gba").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "pair"
            manifest = build_pair(ROOT, PROFILE, output)

            baseline = (output / manifest["variants"]["baseline"]["rom_path"]).read_bytes()
            candidate = (output / manifest["variants"]["candidate"]["rom_path"]).read_bytes()
            changed = [
                index
                for index, values in enumerate(zip(baseline, candidate, strict=True))
                if values[0] != values[1]
            ]

            self.assertEqual(manifest["schema"], "motion-effect-parameter-pixel-ab-build-v1")
            self.assertEqual(manifest["group_id"], 3)
            self.assertEqual(manifest["sequence_id"], 3)
            self.assertEqual(manifest["record_id"], 0)
            self.assertEqual(manifest["field"], "y_offset")
            self.assertEqual(manifest["consumer_entry"], "0x08080764")
            self.assertEqual(manifest["child_spawn_function"], "0x08080218")
            self.assertEqual(manifest["input_mode"], "zero-input-active-state")
            self.assertEqual(manifest["inputs"], [])
            self.assertEqual(baseline, base)
            self.assertEqual(changed, [PATCH_OFFSET])
            self.assertEqual((baseline[PATCH_OFFSET], candidate[PATCH_OFFSET]), (0, 32))
            self.assertEqual(manifest["edit"]["rom_offset"], PATCH_OFFSET)
            self.assertEqual(manifest["edit"]["before_bytes"], "0000")
            self.assertEqual(manifest["edit"]["after_bytes"], "2000")
            self.assertEqual(manifest["variants"]["baseline"]["rom_sha256"], sha256(base))
            self.assertEqual(manifest["variants"]["candidate"]["rom_sha256"], sha256(candidate))

    def test_rejects_a_profile_that_does_not_target_record_zero(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        profile["record_id"] = 1
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad_profile = root / "profile.json"
            bad_profile.write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "record 0"):
                build_pair(ROOT, bad_profile, root / "pair")

    def test_rejects_a_profile_that_uses_the_old_group13_route(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        profile["group_id"] = 13
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad_profile = root / "profile.json"
            bad_profile.write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "natural group-3"):
                build_pair(ROOT, bad_profile, root / "pair")


if __name__ == "__main__":
    unittest.main()
