import json
import tempfile
import unittest
from pathlib import Path

from tools.butano.export_scenario_41_attack_animation import export_attack_animation


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "build" / "scenario-41-attack-trace-20260722-01"


class Scenario41AttackAnimationTest(unittest.TestCase):
    def test_exports_hash_bound_264_frame_timeline_with_deduplicated_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "animation"
            manifest = export_attack_animation(TRACE, output)
            self.assertEqual(manifest["timeline_frames"], 264)
            self.assertEqual(manifest["unique_frames"], 173)
            self.assertEqual(
                manifest["timeline_sha256"],
                "f10ddd3cf9a6088bc574cf41c069c4c7e701a1d1dd2c49aa4ce98c3dd560e931",
            )
            self.assertEqual(len(manifest["timeline"]), 264)
            self.assertEqual(
                json.loads((output / "manifest.json").read_text(encoding="utf-8")),
                manifest,
            )
            for filename in set(manifest["timeline"]):
                self.assertTrue((output / "frames" / filename).is_file())


if __name__ == "__main__":
    unittest.main()
