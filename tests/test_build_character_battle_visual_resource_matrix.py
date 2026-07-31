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


class BuildCharacterBattleVisualResourceMatrixTests(unittest.TestCase):
    def test_builds_three_single_factor_visual_resource_candidates(self):
        from tools.build_character_battle_visual_resource_matrix import build_matrix

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "matrix"
            manifest = build_matrix(ROOT, output)

            self.assertEqual(
                "character-battle-visual-resource-matrix-build-v1",
                manifest["schema"],
            )
            self.assertEqual(
                {"baseline", "palette", "component", "timeline"},
                set(manifest["variants"]),
            )
            self.assertEqual(
                {
                    "palette": {
                        "bundle_local_offset": 0x2,
                        "before_hex": "84",
                        "after_hex": "85",
                        "palette_index": 1,
                    },
                    "component": {
                        "bundle_local_offset": 0x486C,
                        "before_hex": "f0",
                        "after_hex": "f1",
                        "frame_id": 3,
                        "component_index": 0,
                        "field": "x",
                        "before": -16,
                        "after": -15,
                    },
                    "timeline": {
                        "bundle_local_offset": 0x4A64,
                        "before_hex": "03",
                        "after_hex": "04",
                        "animation_id": 1,
                        "keyframe_index": 0,
                        "field": "frame_id",
                        "before": 3,
                        "after": 4,
                    },
                },
                manifest["edits"],
            )
            self.assertTrue(manifest["isolation"]["shared_patch_topology"])
            self.assertTrue(manifest["isolation"]["single_byte_candidates"])

            variants = manifest["variants"]
            roms = {
                variant: (output / row["rom_path"]).read_bytes()
                for variant, row in variants.items()
            }
            for variant, rom in roms.items():
                self.assertEqual(0x1000000, len(rom))
                self.assertEqual(variants[variant]["rom_sha256"], _sha256(rom))
                self.assertEqual(2, len(variants[variant]["patch_ledger"]))
                self.assertEqual(0x600000, variants[variant]["patch_ledger"][0]["offset"])
                self.assertEqual(0x4B60, variants[variant]["patch_ledger"][0]["size"])
                self.assertEqual(0x596D5C, variants[variant]["patch_ledger"][1]["offset"])

            for variant, expected in {
                "palette": 0x600002,
                "component": 0x60486C,
                "timeline": 0x604A64,
            }.items():
                self.assertEqual(
                    [expected],
                    _changed_offsets(roms["baseline"], roms[variant]),
                )

    def test_rejects_a_non_contract_variant(self):
        from tools.build_character_battle_visual_resource_matrix import build_matrix

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "variant contract"):
                build_matrix(
                    ROOT,
                    Path(temporary) / "matrix",
                    variants=("baseline", "palette"),
                )


if __name__ == "__main__":
    unittest.main()
