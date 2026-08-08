from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from tools.build_map_events_e4_handler_pixel_ab import build_pair


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "sequel/content/map-events/entry-e4-primary-pixel-ab.json"


class BuildMapEventsE4HandlerPixelAbTests(unittest.TestCase):
    def test_builds_an_isolated_safe_handler_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "build"
            manifest = build_pair(ROOT, PROFILE, output)

            self.assertEqual(manifest["schema"], "map-events-e4-handler-pixel-ab-build-v1")
            self.assertEqual(manifest["entry_id"], 0xE4)
            self.assertEqual(manifest["field"], "primary_handler_ptr")
            self.assertEqual(manifest["edit"]["rom_offset"], 0x53EDB8)
            self.assertEqual(
                manifest["edit"]["changed_rom_offsets"],
                [0x53EDB8, 0x53EDB9, 0x53EDBA],
            )
            self.assertEqual(manifest["edit"]["before_pointer"], "0x0807F209")
            self.assertEqual(manifest["edit"]["after_pointer"], "0x0809C149")
            self.assertEqual(manifest["edit"]["after_target_instruction"], "bx lr")
            baseline = output / manifest["variants"]["baseline"]["rom_path"]
            candidate = output / manifest["variants"]["candidate"]["rom_path"]
            self.assertEqual(baseline.stat().st_size, 0x600000)
            self.assertEqual(candidate.stat().st_size, 0x600000)
            self.assertEqual(
                hashlib.sha256(candidate.read_bytes()).hexdigest(),
                manifest["variants"]["candidate"]["rom_sha256"],
            )
            self.assertEqual(candidate.read_bytes()[0x53EDB8 : 0x53EDBC], bytes.fromhex("49c10908"))
            self.assertEqual(manifest["input_mode"], "zero-input-natural-expiry")
            self.assertEqual(manifest["inputs"], [])

    def test_profile_binds_the_existing_natural_e4_chain(self):
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["entry_id"], 0xE4)
        self.assertEqual(profile["encoded_action"], "0xC3")
        self.assertEqual(profile["natural_expiry_action"], "0xE4")
        self.assertEqual(profile["source_chain_manifest"], "notes/battlefield-object-effect-chain-bindings-20260802.json")
        self.assertEqual(profile["source_phase_artifact"], "artifacts/battle-effect-frame-phase-group3-natural-v1")


if __name__ == "__main__":
    unittest.main()
