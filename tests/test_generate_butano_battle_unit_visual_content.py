import hashlib
import json
import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def bmp_contract(path: Path) -> tuple[int, int, int]:
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise AssertionError(f"{path.name} is not a BMP")
    return (
        *struct.unpack_from("<ii", data, 18),
        struct.unpack_from("<H", data, 28)[0],
    )


class GenerateButanoBattleUnitVisualContentTest(unittest.TestCase):
    def test_decodes_all_character_visual_slots_and_idle_frames(self):
        from tools.generate_butano_battle_unit_visual_content import (
            load_battle_unit_visuals,
        )

        catalog = load_battle_unit_visuals(ROOT / "rom" / "base.gba")

        self.assertEqual(catalog["unit_count"], 62)
        self.assertEqual(catalog["slots_per_unit"], 9)
        self.assertEqual(catalog["row_count"], 558)
        self.assertEqual(catalog["valid_slot_count"], 342)
        self.assertEqual(catalog["empty_slot_count"], 216)
        self.assertEqual(catalog["component_asset_count"], 534)
        self.assertEqual(catalog["schema_version"], 2)
        self.assertEqual(
            [entry["character_id"] for entry in catalog["entries"]],
            list(range(1, 63)),
        )
        self.assertTrue(all(entry["idle"]["valid"] for entry in catalog["entries"]))
        self.assertEqual(
            catalog["slot_semantics"],
            [
                "field_idle_and_movement",
                "cast_facing_right",
                "throw_facing_right",
                "melee_facing_right",
                "hit_facing_right",
                "cast_facing_left",
                "throw_facing_left",
                "melee_facing_left",
                "hit_facing_left",
            ],
        )

        naruto_slot_0 = catalog["entries"][0]["visuals"][0]
        self.assertEqual(naruto_slot_0["frame_count"], 20)
        self.assertEqual(naruto_slot_0["animation_count"], 12)
        self.assertEqual(naruto_slot_0["component_track_count"], 1)
        self.assertEqual(len(naruto_slot_0["component_assets"]), 2)
        self.assertEqual(
            naruto_slot_0["component_assets"][0]["canvas_size"],
            [32, 64],
        )
        self.assertEqual(
            naruto_slot_0["component_assets"][1]["canvas_size"],
            [64, 64],
        )
        self.assertEqual(
            naruto_slot_0["frames"][0]["component_poses"][0][
                "asset_index"
            ],
            0,
        )
        self.assertNotEqual(
            naruto_slot_0["frames"][16]["component_poses"][0][
                "asset_index"
            ],
            naruto_slot_0["frames"][0]["component_poses"][0][
                "asset_index"
            ],
        )
        self.assertEqual(
            naruto_slot_0["animations"][0]["steps"],
            [
                {"frame_index": 0, "duration": 8},
                {"frame_index": 1, "duration": 8},
                {"frame_index": 2, "duration": 8},
                {"frame_index": 1, "duration": 8},
            ],
        )
        self.assertEqual(
            naruto_slot_0["animations"][4]["steps"],
            [
                {"frame_index": 1, "duration": 2},
                {"frame_index": 2, "duration": 4},
                {"frame_index": 12, "duration": 4},
                {"frame_index": 13, "duration": 2},
            ],
        )
        self.assertEqual(
            catalog["entries"][0]["visuals"][3]["animations"][0][
                "total_duration"
            ],
            34,
        )

        composite_idle = catalog["entries"][38]["idle"]
        self.assertEqual(composite_idle["component_count"], 3)
        self.assertEqual(composite_idle["bounds"], [-24, -56, 16, 8])
        self.assertEqual(composite_idle["size"], [40, 64])
        self.assertEqual(composite_idle["canvas_size"], [64, 64])
        self.assertEqual(composite_idle["center_offset"], [8, -24])

        mirrored_frame = catalog["entries"][38]["visuals"][0]["frames"][3]
        self.assertEqual(mirrored_frame["component_count"], 5)
        self.assertTrue(
            all(
                component["horizontal_flip"]
                for component in mirrored_frame["components"]
            )
        )

        expected = {
            1: (
                [32, 64],
                [0, -24],
                "afd089ccaf2855ea2e5f79088051e8bb"
                "09b2d2e4a420ad0c49be37fc605c81ee",
            ),
            2: (
                [32, 64],
                [0, -24],
                "5af82f6494aedbef3d81d5e2a76374a4"
                "dac1ee69656ccff62aed914730efd9c6",
            ),
            42: (
                [64, 64],
                [8, -24],
                "b1401cd9095a08ab27595216372d9dff"
                "b6d4b2109ac3a2e22a52206cbaca30ec",
            ),
            62: (
                [32, 64],
                [0, -24],
                "5eb65ff9aa902f3ac1f025d6dbe5d99d"
                "0b2ad593d37369b7cbd4de39f9c10e20",
            ),
        }
        for character_id, (
            size,
            center_offset,
            pixel_sha256,
        ) in expected.items():
            with self.subTest(character_id=character_id):
                idle = catalog["entries"][character_id - 1]["idle"]
                self.assertEqual(idle["size"], size)
                self.assertEqual(idle["center_offset"], center_offset)
                self.assertEqual(idle["pixel_sha256"], pixel_sha256)

    def test_generates_deterministic_butano_assets_and_cpp_catalog(self):
        from tools.generate_butano_battle_unit_visual_content import generate

        with (
            tempfile.TemporaryDirectory() as first_temporary,
            tempfile.TemporaryDirectory() as second_temporary,
        ):
            first = Path(first_temporary)
            second = Path(second_temporary)
            stale_bmp = first / "battle_unit_99_slot_0_part_0.bmp"
            stale_json = first / "battle_unit_99_slot_0_part_0.json"
            stale_bmp.write_bytes(b"stale")
            stale_json.write_text("stale", encoding="utf-8")
            first_catalog = generate(
                ROOT / "rom" / "base.gba",
                first,
                first / "generated_battle_unit_visual_content.h",
                first / "battle_unit_visual_catalog.json",
            )
            second_catalog = generate(
                ROOT / "rom" / "base.gba",
                second,
                second / "generated_battle_unit_visual_content.h",
                second / "battle_unit_visual_catalog.json",
            )

            self.assertFalse(stale_bmp.exists())
            self.assertFalse(stale_json.exists())
            self.assertEqual(first_catalog, second_catalog)
            self.assertEqual(
                json.loads(
                    (first / "battle_unit_visual_catalog.json").read_text(
                        encoding="utf-8"
                    )
                ),
                first_catalog,
            )
            self.assertEqual(len(list(first.glob("battle_unit_*_idle.bmp"))), 62)
            self.assertEqual(len(list(first.glob("battle_unit_*_idle.json"))), 62)
            self.assertEqual(
                len(list(first.glob("battle_unit_*_slot_*_part_*.bmp"))),
                first_catalog["component_asset_count"],
            )
            self.assertEqual(
                len(list(first.glob("battle_unit_*_slot_*_part_*.json"))),
                first_catalog["component_asset_count"],
            )
            self.assertEqual(
                bmp_contract(first / "battle_unit_01_idle.bmp"),
                (32, 64, 4),
            )
            self.assertEqual(
                bmp_contract(first / "battle_unit_42_idle.bmp"),
                (64, 64, 4),
            )
            self.assertEqual(
                bmp_contract(first / "battle_unit_55_idle.bmp"),
                (32, 64, 4),
            )
            self.assertEqual(
                bmp_contract(
                    first
                    / "battle_unit_01_slot_0_part_0_shape_32x64.bmp"
                ),
                (32, 1024, 4),
            )
            with Image.open(
                first
                / "battle_unit_30_slot_0_part_0_shape_32x64.bmp"
            ) as unit_palette:
                palette = unit_palette.getpalette()
                self.assertEqual(
                    tuple(palette[15 * 3:15 * 3 + 3]),
                    (0, 8, 8),
                )
            component_metadata = json.loads(
                (
                    first
                    / "battle_unit_01_slot_0_part_0_shape_32x64.json"
                ).read_text(encoding="utf-8")
            )
            self.assertNotIn("compression", component_metadata)

            first_files = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in first.iterdir()
            }
            second_files = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in second.iterdir()
            }
            self.assertEqual(first_files, second_files)

            header = (
                first / "generated_battle_unit_visual_content.h"
            ).read_text(encoding="utf-8")
            self.assertEqual(
                header.count('#include "bn_sprite_items_battle_unit_'),
                62 + first_catalog["component_asset_count"],
            )
            self.assertEqual(header.count("case "), 404)
            self.assertIn("battle_unit_idle_visual", header)
            self.assertIn("battle_unit_visual_slot", header)
            self.assertIn("battle_unit_visual_slot_for", header)
            self.assertIn("battle_unit_visual_timeline_step", header)
            self.assertIn("component_track_count", header)
            self.assertIn("center_offset_x", header)
            self.assertIn("center_offset_y", header)
            self.assertIn(
                "battle_unit_visual_max_assets",
                header,
            )

    def test_cli_runs_from_repository_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/generate_butano_battle_unit_visual_content.py",
                    "--graphics",
                    str(output),
                    "--header",
                    str(output / "generated.h"),
                    "--catalog",
                    str(output / "catalog.json"),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                "generated 62 battle unit idle sprites",
                result.stdout,
            )


if __name__ == "__main__":
    unittest.main()
