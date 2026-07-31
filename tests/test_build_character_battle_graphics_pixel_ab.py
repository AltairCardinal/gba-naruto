from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _changed_offsets(left: bytes, right: bytes) -> list[int]:
    return [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]


class BuildCharacterBattleGraphicsPixelAbTests(unittest.TestCase):
    def test_builds_topology_identical_relocated_resource_zero_roms(self):
        from tools.build_character_battle_graphics_pixel_ab import build_pixel_ab_roms

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pixel-ab"
            manifest = build_pixel_ab_roms(ROOT, output)

            self.assertEqual(
                "character-battle-graphics-pixel-ab-build-v1",
                manifest["schema"],
            )
            self.assertEqual(0, manifest["resource"]["resource_id"])
            self.assertEqual([0], manifest["resource"]["slot_rows"])
            self.assertEqual("0x0813E090", manifest["resource"]["source_graphics"])
            self.assertEqual(
                {
                    "graphics_byte_offset": 0xD26,
                    "before_hex": "12",
                    "after_hex": "42",
                    "source_pixel": [13, 17],
                    "expected_screen_pixel": [117, 25],
                    "before_palette_index": 1,
                    "after_palette_index": 4,
                },
                manifest["edit"],
            )
            self.assertEqual(
                "artifacts/runtime-checkpoints/scenario-41-start-row.ss9",
                manifest["runtime_contract"]["input_checkpoint"],
            )
            self.assertEqual(80, manifest["runtime_contract"]["capture_frame"])
            self.assertTrue(manifest["isolation"]["shared_patch_topology"])
            self.assertTrue(manifest["isolation"]["single_graphics_byte_difference"])

            base = (ROOT / "rom/base.gba").read_bytes()
            variants = manifest["variants"]
            baseline = (output / variants["baseline"]["rom_path"]).read_bytes()
            candidate = (output / variants["candidate"]["rom_path"]).read_bytes()
            self.assertEqual(0x1000000, len(baseline))
            self.assertEqual(len(baseline), len(candidate))
            self.assertEqual(variants["baseline"]["rom_sha256"], _sha256(baseline))
            self.assertEqual(variants["candidate"]["rom_sha256"], _sha256(candidate))

            baseline_ledger = variants["baseline"]["patch_ledger"]
            candidate_ledger = variants["candidate"]["patch_ledger"]
            self.assertEqual(2, len(baseline_ledger))
            self.assertEqual(
                [
                    (row["kind"], row["offset"], row["size"], row["resource_id"])
                    for row in baseline_ledger
                ],
                [
                    (row["kind"], row["offset"], row["size"], row["resource_id"])
                    for row in candidate_ledger
                ],
            )
            allocation = baseline_ledger[0]
            self.assertEqual("allocation", allocation["kind"])
            self.assertEqual(0x600000, allocation["offset"])
            self.assertEqual("0x08600020", allocation["new_pointers"]["graphics"])
            descriptor = baseline_ledger[1]
            self.assertEqual("descriptor", descriptor["kind"])
            self.assertEqual(0x596D5C, descriptor["offset"])
            self.assertEqual(base[0x596D5C + 16 : 0x596D5C + 32], baseline[0x596D5C + 16 : 0x596D5C + 32])

            graphics_offset = int(allocation["new_pointers"]["graphics"], 16) - 0x08000000
            self.assertEqual(0x12, baseline[graphics_offset + 0xD26])
            self.assertEqual(0x42, candidate[graphics_offset + 0xD26])
            self.assertEqual(
                [graphics_offset + 0xD26],
                _changed_offsets(baseline, candidate),
            )

    def test_rejects_a_non_contract_pixel_edit(self):
        from tools.build_character_battle_graphics_pixel_ab import build_pixel_ab_roms

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "fixed pixel contract"):
                build_pixel_ab_roms(
                    ROOT,
                    Path(temporary) / "pixel-ab",
                    after=0x52,
                )


if __name__ == "__main__":
    unittest.main()
