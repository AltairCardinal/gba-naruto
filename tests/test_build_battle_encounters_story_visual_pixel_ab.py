from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.inspect_mgba_savestate import load_gba_state


ROOT = Path(__file__).resolve().parents[1]


class BuildBattleEncountersStoryVisualPixelAbTests(unittest.TestCase):
    def test_builds_cursor_fixture_and_isolated_story_gfx_pointer_pair(self):
        from tools.build_battle_encounters_story_visual_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "build"
            manifest = build_pair(ROOT, output)

            self.assertEqual(
                "battle-encounters-story-visual-pixel-ab-build-v1",
                manifest["schema"],
            )
            fixture = output / manifest["input_state"]
            self.assertEqual(0x08049E63, load_gba_state(fixture).read_u32(0x030011F0))
            self.assertEqual(
                hashlib.sha256(fixture.read_bytes()).hexdigest(),
                manifest["input_state_sha256"],
            )
            self.assertEqual(
                [0x54229C, 0x54229D, 0x54229E],
                manifest["edit"]["changed_rom_offsets"],
            )
            baseline = (output / manifest["variants"]["baseline"]["rom_path"]).read_bytes()
            candidate = (output / manifest["variants"]["candidate"]["rom_path"]).read_bytes()
            self.assertEqual(0x600000, len(baseline))
            self.assertEqual(0x600000, len(candidate))
            self.assertEqual(
                [0x54229C, 0x54229D, 0x54229E],
                [
                    index
                    for index, pair in enumerate(zip(baseline, candidate, strict=True))
                    if pair[0] != pair[1]
                ],
            )

    def test_manifest_binds_static_scenario_53_command_and_parent_checkpoint(self):
        from tools.build_battle_encounters_story_visual_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "build"
            manifest = build_pair(ROOT, output)
            built_fixture = (output / manifest["input_state"]).read_bytes()
        self.assertEqual(
            {
                "address": "0x08049E63",
                "raw_hex": "146801",
                "opcode": "0x14",
                "state_value": "0x0168",
                "roots": [
                    {"table": "alternate", "scenario_id": 53},
                    {"table": "primary", "scenario_id": 53},
                ],
            },
            manifest["controlled_entry"]["scenario_command"],
        )
        parent = ROOT / manifest["controlled_entry"]["parent_checkpoint"]
        self.assertEqual(
            hashlib.sha256(parent.read_bytes()).hexdigest(),
            manifest["controlled_entry"]["parent_checkpoint_sha256"],
        )
        self.assertEqual(
            "script-cursor-only",
            manifest["controlled_entry"]["fixture_edit_kind"],
        )
        canonical = ROOT / manifest["controlled_entry"]["canonical_checkpoint"]
        self.assertTrue(canonical.is_file())
        self.assertEqual(
            hashlib.sha256(canonical.read_bytes()).hexdigest(),
            manifest["controlled_entry"]["canonical_checkpoint_sha256"],
        )
        self.assertEqual(
            canonical.read_bytes(),
            built_fixture,
        )

    def test_rejects_nonempty_output(self):
        from tools.build_battle_encounters_story_visual_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "build"
            output.mkdir()
            (output / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "absent or empty"):
                build_pair(ROOT, output)


if __name__ == "__main__":
    unittest.main()
