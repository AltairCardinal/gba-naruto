import json
import inspect
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import tools.generate_butano_battle_runtime_assets as runtime_assets
from tools.generate_butano_battle_runtime_assets import generate
from tools.butano.generate_scenario_41_assets import reconstruct_map


ROOT = Path(__file__).resolve().parents[1]


class GenerateButanoBattleRuntimeAssetsTest(unittest.TestCase):
    def test_generates_all_battle_backgrounds_and_cpp_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            header_path = (
                output
                / "generated_battle_background_content.h"
            )
            catalog_path = (
                output / "battle_background_catalog.json"
            )
            catalog = runtime_assets.generate_all_map_chunks(
                ROOT / "rom" / "base.gba",
                output,
                header_path,
                catalog_path,
            )

            self.assertEqual(catalog["map_count"], 47)
            self.assertEqual(catalog["chunk_count"], 49)
            entries = catalog["entries"]
            self.assertEqual(len(entries), 47)
            self.assertEqual(
                [entry["battle_id"] for entry in entries],
                list(range(47)),
            )
            self.assertEqual(
                entries[0]["active_size"],
                [736, 512],
            )
            self.assertEqual(entries[0]["origins"], [0, 224])
            self.assertEqual(
                entries[11]["active_size"],
                [544, 480],
            )
            self.assertEqual(entries[11]["origins"], [0, 32])
            self.assertEqual(
                entries[41]["active_size"],
                [288, 352],
            )
            self.assertEqual(entries[41]["origins"], [0])
            self.assertEqual(
                entries[11]["source_sha256"],
                reconstruct_map(
                    ROOT / "rom" / "base.gba",
                    11,
                )["source_sha256"],
            )
            self.assertEqual(
                json.loads(
                    catalog_path.read_text(encoding="utf-8")
                ),
                catalog,
            )
            self.assertEqual(
                len(list(output.glob("battle_*_map_chunk_*.bmp"))),
                49,
            )
            self.assertEqual(
                len(list(output.glob("battle_*_map_chunks.json"))),
                47,
            )

            header = header_path.read_text(encoding="utf-8")
            self.assertEqual(
                header.count(
                    '#include "bn_regular_bg_items_battle_'
                ),
                49,
            )
            self.assertIn(
                "std::array<"
                "battle_background_content_entry, 47>",
                header,
            )
            self.assertIn(
                "generated_battle_background_entry(int battle_id)",
                header,
            )
            self.assertIn(
                "&bn::regular_bg_items::"
                "battle_00_map_chunk_1",
                header,
            )
            self.assertIn(
                "&bn::regular_bg_items::"
                "battle_11_map_chunk_1",
                header,
            )
            before_catalog = catalog_path.read_bytes()
            before_header = header_path.read_bytes()
            runtime_assets.generate_all_map_chunks(
                ROOT / "rom" / "base.gba",
                output,
                header_path,
                catalog_path,
            )
            self.assertEqual(
                catalog_path.read_bytes(),
                before_catalog,
            )
            self.assertEqual(
                header_path.read_bytes(),
                before_header,
            )

    def test_generates_overlapping_rom_backed_battle_11_chunks(self):
        self.assertEqual(
            runtime_assets.plan_map_chunk_origins(544),
            [0, 32],
        )
        with self.assertRaises(ValueError):
            runtime_assets.plan_map_chunk_origins(
                544,
                viewport_width=513,
            )

        reconstructed = reconstruct_map(
            ROOT / "rom" / "base.gba",
            11,
        )
        self.assertEqual(
            (reconstructed["width"], reconstructed["height"]),
            (544, 480),
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            manifest_path = output / "battle_11_map_chunks.json"
            manifest = runtime_assets.generate_map_chunks(
                ROOT / "rom" / "base.gba",
                11,
                output,
                "battle_11_map",
                manifest_path,
            )

            self.assertEqual(manifest["active_size"], [544, 480])
            self.assertEqual(manifest["chunk_size"], [512, 512])
            self.assertEqual(manifest["viewport_width"], 240)
            self.assertEqual(manifest["origins"], [0, 32])
            self.assertEqual(
                manifest["source_sha256"],
                reconstructed["source_sha256"],
            )
            self.assertEqual(
                json.loads(
                    manifest_path.read_text(encoding="utf-8")
                ),
                manifest,
            )

            paths = [
                output / "battle_11_map_chunk_0.bmp",
                output / "battle_11_map_chunk_1.bmp",
            ]
            for path in paths:
                self.assertTrue(path.is_file())
            with Image.open(paths[0]) as opened:
                first = opened.copy()
            with Image.open(paths[1]) as opened:
                second = opened.copy()
            self.assertEqual(first.size, (512, 512))
            self.assertEqual(second.size, (512, 512))
            self.assertEqual(first.mode, "P")
            self.assertEqual(second.mode, "P")
            self.assertEqual(
                first.crop((32, 0, 512, 480)).tobytes(),
                second.crop((0, 0, 480, 480)).tobytes(),
            )
            self.assertEqual(
                second.crop((0, 0, 512, 480)).tobytes(),
                bytes(
                    reconstructed["pixels"][
                        y * 544 + 32:
                        y * 544 + 544
                    ][x]
                    for y in range(480)
                    for x in range(512)
                ),
            )
            self.assertTrue(
                not any(
                    second.crop(
                        (0, 480, 512, 512)
                    ).tobytes()
                )
            )

            for index, origin in enumerate([0, 32]):
                metadata = json.loads(
                    (
                        output
                        / f"battle_11_map_chunk_{index}.json"
                    ).read_text(encoding="utf-8")
                )
                self.assertEqual(metadata["type"], "regular_bg")
                self.assertEqual(
                    metadata["compression"],
                    "auto_no_huffman",
                )
                self.assertEqual(metadata["source"], "rom/base.gba:map-row-11")
                self.assertEqual(metadata["map_active_size"], [544, 480])
                self.assertEqual(metadata["chunk_index"], index)
                self.assertEqual(metadata["chunk_count"], 2)
                self.assertEqual(metadata["world_origin"], [origin, 0])

    def test_reconstructs_and_generates_rom_backed_battle_09_map(self):
        self.assertIn(
            "battle_id",
            inspect.signature(reconstruct_map).parameters,
        )
        self.assertTrue(hasattr(runtime_assets, "generate_map"))

        reconstructed = reconstruct_map(ROOT / "rom" / "base.gba", 9)
        self.assertEqual(
            (reconstructed["width"], reconstructed["height"]),
            (512, 512),
        )
        self.assertEqual(
            reconstructed["source_sha256"],
            {
                "tile_gfx": (
                    "f966926f51bf1dd00d6c73d70f9ea7f7"
                    "ef4a54e300633fcc80298d076f0bb66a"
                ),
                "bg_palette": (
                    "bdb15e88f379675f2bb26619ef6899f2"
                    "78df6d5f5abfc4cf583ea1c6ac12bb12"
                ),
                "primary_layout": (
                    "925661754c1db09be6a2a0efdf25ffd8"
                    "d16d0b1c282ccc94cb1106d998746d1b"
                ),
                "metatile_attributes": (
                    "e300befabb9e59dfdce21982e0c95ff4"
                    "debe1170f03132962484705f32325ea5"
                ),
            },
        )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            clean_map = output / "battle_09_clean_map.bmp"
            clean_json = output / "battle_09_clean_map.json"
            runtime_assets.generate_map(
                ROOT / "rom" / "base.gba",
                9,
                clean_map,
                clean_json,
            )

            with Image.open(clean_map) as clean:
                self.assertEqual(clean.size, (512, 512))
                self.assertEqual(clean.mode, "P")
                self.assertEqual(
                    bytes(clean.getdata()),
                    reconstructed["pixels"],
                )
            self.assertEqual(
                json.loads(clean_json.read_text(encoding="utf-8")),
                {
                    "type": "regular_bg",
                    "bpp_mode": "bpp_8",
                    "colors_count": 256,
                    "compression": "auto_no_huffman",
                    "source": "rom/base.gba:map-row-9",
                    "active_size": [512, 512],
                    "collision_source": (
                        "generated_battle_map_content.h:9"
                    ),
                },
            )

    def test_generates_rom_backed_map_and_independent_enemy_sprite(self):
        source = ROOT / "butano-sequel" / "graphics" / "scenario_41_map.bmp"
        reconstructed = reconstruct_map(ROOT / "rom" / "base.gba")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            clean_map = output / "scenario_41_clean_map.bmp"
            enemy = output / "scenario_41_enemy.bmp"
            clean_json = output / "scenario_41_clean_map.json"
            enemy_json = output / "scenario_41_enemy.json"
            generate(source, clean_map, enemy, clean_json, enemy_json)

            with Image.open(clean_map) as clean:
                self.assertEqual(clean.size, (512, 512))
                for y in range(352):
                    for x in range(288):
                        self.assertEqual(
                            clean.getpixel((x, y)),
                            reconstructed["pixels"][y * 288 + x],
                        )
                self.assertEqual(clean.getpixel((96, 128)), 55)
                self.assertEqual(clean.getpixel((511, 511)), 0)
                self.assertTrue(
                    all(
                        clean.getpixel((x, y)) == 0
                        for y in range(512)
                        for x in range(512)
                        if x >= 288 or y >= 352
                    )
                )

            with Image.open(enemy) as sprite:
                self.assertEqual(sprite.size, (32, 32))
                self.assertEqual(sprite.mode, "P")
                self.assertEqual(sprite.getpixel((31, 0)), 0)
                opaque = sum(pixel != 0 for pixel in sprite.getdata())
                self.assertGreater(opaque, 300)
                self.assertLess(opaque, 900)

            self.assertEqual(
                json.loads(clean_json.read_text(encoding="utf-8")),
                {
                    "type": "regular_bg",
                    "bpp_mode": "bpp_8",
                    "colors_count": 256,
                    "compression": "auto_no_huffman",
                    "source": "rom/base.gba:map-row-41",
                    "active_size": [288, 352],
                    "collision_source": "generated_battle_map_content.h:41",
                },
            )
            self.assertEqual(
                json.loads(enemy_json.read_text(encoding="utf-8")),
                {"type": "sprite", "height": 32, "bpp_mode": "bpp_8"},
            )


if __name__ == "__main__":
    unittest.main()
