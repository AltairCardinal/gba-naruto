import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattlefieldObjectEffectContentGeneratorTest(unittest.TestCase):
    def test_extracts_exact_type_2_expiry_sheet_from_original_rom(self):
        from tools.generate_butano_battlefield_object_effect_content import (
            generate_battlefield_object_effect_content,
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = generate_battlefield_object_effect_content(
                ROOT, output
            )

            self.assertEqual(result["effect_sequence"], 7)
            self.assertEqual(result["sequence_resource_group"], 0x12)
            self.assertEqual(result["graphics_pointer"], "0x083478F4")
            self.assertEqual(result["palette_pointer"], "0x083480C8")
            self.assertEqual(result["frame_width"], 32)
            self.assertEqual(result["frame_height"], 32)
            self.assertEqual(result["frame_count"], 7)
            self.assertEqual(
                result["graphics_decompressed_sha256"],
                "9162bda2e90536bbe5982e94b4d4de9b"
                "18111538b548137ca057701d36b7bc55",
            )
            self.assertEqual(
                result["palette_decompressed_sha256"],
                "d53a7a56bded0b6727002a3fb4ad6945"
                "4dccee15e8f849ad3a16c3b5639244c1",
            )

            bmp = output / "battlefield_object_type_2_expiry.bmp"
            metadata = (
                output / "battlefield_object_type_2_expiry.json"
            )
            self.assertTrue(bmp.is_file())
            self.assertEqual(
                json.loads(metadata.read_text(encoding="utf-8")),
                {
                    "type": "sprite",
                    "height": 32,
                    "source": (
                        "rom/base.gba:sequence-7-resource-group-18"
                    ),
                },
            )


if __name__ == "__main__":
    unittest.main()
