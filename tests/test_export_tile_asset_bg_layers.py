#!/usr/bin/env python3
"""Full ROM-backed export of the 79 tile-assets BG descriptors."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_SHA256 = "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"


def _encode_4bpp_tile(pixels: list[int]) -> bytes:
    return bytes(
        pixels[index] | (pixels[index + 1] << 4)
        for index in range(0, len(pixels), 2)
    )


class TileAssetBgLayerExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_tile_asset_bg_layers import (
            export_tile_asset_bg_layers,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "tile-assets-bg"
        cls.manifest = export_tile_asset_bg_layers(ROOT, cls.output_dir)

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def _descriptor(self, index: int) -> dict:
        return self.manifest["descriptors"][index]

    def _layer(self, index: int, name: str) -> dict:
        return next(
            layer
            for layer in self._descriptor(index)["layers"]
            if layer["name"] == name
        )

    def test_renderer_preserves_relative_tiles_and_both_flip_axes(self):
        from tools.export_tile_asset_bg_layers import (
            render_4bpp_tilemap_indices,
        )

        first = [0] * 64
        second = [(y * 8 + x) % 15 + 1 for y in range(8) for x in range(8)]
        graphics = _encode_4bpp_tile(first) + _encode_4bpp_tile(second)
        tilemap = struct.pack(
            "<4H",
            1,
            1 | 1 << 10,
            1 | 1 << 11,
            1 | 3 << 10,
        )
        pixels = render_4bpp_tilemap_indices(
            graphics,
            tilemap,
            width_tiles=2,
            height_tiles=2,
        )

        def source(x: int, y: int) -> int:
            return second[y * 8 + x]

        def pixel(x: int, y: int) -> int:
            return pixels[y * 16 + x]

        self.assertEqual(16 * 16, len(pixels))
        self.assertEqual(source(0, 0), pixel(0, 0))
        self.assertEqual(source(7, 0), pixel(8, 0))
        self.assertEqual(source(0, 7), pixel(0, 8))
        self.assertEqual(source(7, 7), pixel(8, 8))

    def test_exports_complete_table_with_exact_static_boundaries(self):
        manifest = self.manifest
        self.assertEqual("tile-assets-bg-export-v1", manifest["schema"])
        self.assertEqual(ROM_SHA256, manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x5A320C,
                "gba_address": "0x085A320C",
                "entry_count": 79,
                "entry_size": 0x44,
                "sha256": TABLE_SHA256,
                "verification": "code_verified",
            },
            manifest["source_table"],
        )
        self.assertEqual(79, manifest["descriptor_count"])
        self.assertEqual([13, 31, 32, 46], manifest["sentinel_descriptor_ids"])
        self.assertEqual(
            {"A": 75, "B": 75, "C": 75, "D": 11},
            manifest["complete_layer_counts"],
        )
        self.assertEqual(236, manifest["complete_layer_count"])
        self.assertEqual(1, manifest["partial_layer_count"])
        self.assertEqual(107, manifest["unique_graphics_count"])
        self.assertEqual(108, manifest["unique_tilemap_count"])
        self.assertEqual(107, manifest["unique_palette_count"])
        self.assertEqual(108, manifest["unique_atlas_count"])
        self.assertEqual(108, manifest["unique_complete_layer_count"])
        self.assertEqual(79, len(manifest["descriptors"]))
        self.assertEqual(108, len(manifest["atlases"]))
        self.assertEqual(345, len(list(self.output_dir.iterdir())))

    def test_descriptor_zero_records_complete_layers_and_known_partial_d(self):
        descriptor = self._descriptor(0)
        self.assertEqual("partial", descriptor["status"])
        self.assertEqual(1, descriptor["consumer_id"])
        self.assertEqual(0x5A320C, descriptor["descriptor_file_offset"])

        layer_a = self._layer(0, "A")
        self.assertEqual("complete", layer_a["status"])
        self.assertEqual(
            {
                "x_tiles": 0,
                "y_tiles": 0,
                "width_tiles": 30,
                "height_tiles": 14,
                "screen_stride_tiles": 32,
                "source": "consumer_fixed",
            },
            layer_a["definition"],
        )
        self.assertEqual(
            {"kind": "consumer_argument"},
            layer_a["tile_base"],
        )
        self.assertEqual(
            {"kind": "consumer_argument"},
            layer_a["palette_bank"],
        )
        self.assertEqual("0x08349EB4", layer_a["gfx_pointer"])
        self.assertEqual(7424, layer_a["gfx"]["decompressed_size"])
        self.assertEqual(
            "818233e568deb74d1437b21fcd26320c0a880e44852e07239fb63a1032d76924",
            layer_a["gfx"]["decompressed_sha256"],
        )
        self.assertEqual("0x0834AFC8", layer_a["tilemap_pointer"])
        self.assertEqual(840, layer_a["tilemap"]["decompressed_size"])
        self.assertEqual(
            "2f8e5353117fa9ce6fc51092843e682208a0e61e1ba0ec57939cacee088880d0",
            layer_a["tilemap"]["decompressed_sha256"],
        )
        self.assertEqual("0x0834B228", layer_a["palette_pointer"])
        self.assertEqual(
            "47ee4252027a1ec3034bf58e23982e2442591e42dc1759aa016405308c937c11",
            layer_a["palette"]["sha256"],
        )
        self.assertEqual((1, 231), (
            layer_a["tile_index_min"],
            layer_a["tile_index_max"],
        ))
        self.assertEqual((2, 3), (
            layer_a["horizontal_flip_count"],
            layer_a["vertical_flip_count"],
        ))

        layer_c = self._layer(0, "C")
        self.assertEqual(
            {
                "x_tiles": 16,
                "y_tiles": 4,
                "width_tiles": 16,
                "height_tiles": 10,
                "screen_stride_tiles": 64,
                "source": "descriptor_packed_bytes",
            },
            layer_c["definition"],
        )
        self.assertEqual(
            {
                "kind": "runtime_state",
                "expression": "state[0x16] >> 1",
            },
            layer_c["tile_base"],
        )
        self.assertEqual(14464, layer_c["gfx"]["decompressed_size"])
        self.assertEqual(320, layer_c["tilemap"]["decompressed_size"])

        layer_d = self._layer(0, "D")
        self.assertEqual("partial", layer_d["status"])
        self.assertEqual(["gfx", "palette"], layer_d["missing_components"])
        self.assertIsNone(layer_d["gfx_pointer"])
        self.assertEqual("0x0836774C", layer_d["tilemap_pointer"])
        self.assertIsNone(layer_d["palette_pointer"])
        self.assertEqual(
            "64b0c22a42e5e9c0029854762d9e28127748bc74522fe0e6ef00565fc7bf3d24",
            layer_d["tilemap"]["decompressed_sha256"],
        )
        self.assertNotIn("layer_png", layer_d)

    def test_sentinels_and_complete_d_are_not_conflated(self):
        for index in (13, 31, 32, 46):
            descriptor = self._descriptor(index)
            self.assertEqual("sentinel", descriptor["status"])
            self.assertEqual([], descriptor["layers"])
            self.assertEqual(
                ["0x00000000"] * 17,
                descriptor["raw_words"],
            )

        layer_d = self._layer(2, "D")
        self.assertEqual("complete", layer_d["status"])
        self.assertEqual("0x08369C18", layer_d["gfx_pointer"])
        self.assertEqual(
            "67b0142b5b9fceab9acbbcb35af136db6424c892730bda9b28061665973c020b",
            layer_d["gfx"]["decompressed_sha256"],
        )
        self.assertEqual(
            "a789b7c10faedaf114789b0a6252b04c2d6ca752987c45f7b0347027eeae4964",
            layer_d["tilemap"]["decompressed_sha256"],
        )
        self.assertEqual(
            "b82b0d1f5467ca1398170caa70e956b1a1c5efbedb4242c8d9325f5fd46177a3",
            layer_d["palette"]["sha256"],
        )

    def test_d_tile_base_is_bound_to_its_distinct_consumer_semantics(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        self.assertEqual(
            "688ae98a40180004000c8146",
            rom[0x992FA:0x99306].hex(),
        )
        self.assertEqual(
            {
                "kind": "runtime_state",
                "expression": "u16(state[0x12] + state[0x16])",
                "consumer_gba_address": "0x080992FA",
            },
            self._layer(2, "D")["tile_base"],
        )

    def test_every_bank_word_and_output_hash_is_rom_bound(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        bank = json.loads(
            (ROOT / "sequel/content/tile-assets/bank.json").read_text(
                encoding="utf-8"
            )
        )
        for index, descriptor in enumerate(self.manifest["descriptors"]):
            words = struct.unpack_from("<17I", rom, 0x5A320C + index * 0x44)
            self.assertEqual(
                [f"0x{word:08X}" for word in words],
                descriptor["raw_words"],
            )
            self.assertEqual(
                [bank["entries"][index][f"word_{word:02d}"] for word in range(17)],
                list(words),
            )
            for layer in descriptor["layers"]:
                if layer["status"] != "complete":
                    continue
                for key in ("layer_png", "atlas_png"):
                    path = self.output_dir / layer[key]
                    self.assertEqual(
                        layer[f"{key}_sha256"],
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )

    def test_outputs_are_indexed_transparent_native_layers_and_full_atlases(self):
        layer_a = self._layer(0, "A")
        with Image.open(self.output_dir / layer_a["layer_png"]) as image:
            image.load()
            self.assertEqual("P", image.mode)
            self.assertEqual((240, 112), image.size)
            self.assertEqual(0, image.info["transparency"])

        with Image.open(self.output_dir / layer_a["atlas_png"]) as image:
            image.load()
            self.assertEqual("P", image.mode)
            self.assertEqual((256, 64), image.size)
            self.assertEqual(0, image.info["transparency"])

        layer_c = self._layer(0, "C")
        with Image.open(self.output_dir / layer_c["layer_png"]) as image:
            self.assertEqual((128, 80), image.size)

    def test_independent_verifier_recomputes_all_layers_and_atlases(self):
        from tools.verify_tile_asset_bg_export import (
            verify_tile_asset_bg_export,
        )

        result = verify_tile_asset_bg_export(
            ROOT,
            self.output_dir,
        )
        self.assertEqual(
            "tile-assets-bg-verification-v1",
            result["schema"],
        )
        self.assertEqual(79, result["verified_descriptors"])
        self.assertEqual(236, result["verified_complete_layers"])
        self.assertEqual(108, result["verified_atlases"])
        self.assertEqual([], result["errors"])

    def test_independent_verifier_rejects_semantic_manifest_tampering(self):
        from tools.verify_tile_asset_bg_export import (
            verify_tile_asset_bg_export,
        )

        manifest_path = self.output_dir / "manifest.json"
        original = manifest_path.read_bytes()
        tampered = json.loads(original)
        tampered["source_table"]["entry_size"] = 0x40
        tampered["complete_layer_count"] = 235
        tampered["atlases"][0]["atlas_id"] = 999
        tampered["descriptors"][3]["descriptor_gba_address"] = "0xDEADBEEF"
        tampered["descriptors"][2]["layers"][3]["tile_base"] = {
            "kind": "constant",
            "value": 0,
        }
        tampered["descriptors"][4]["layers"][0]["definition"][
            "width_tiles"
        ] += 1
        tampered["descriptors"][5]["layers"][1]["palette_bank"] = {
            "kind": "constant",
            "value": 0,
        }
        tampered["descriptors"][6]["layers"][0][
            "gfx_pointer"
        ] = "0xDEADBEEF"
        tampered["descriptors"][7]["layers"][1][
            "tilemap_pointer"
        ] = "0xDEADBEEF"
        tampered["descriptors"][8]["layers"][2][
            "palette_pointer"
        ] = "0xDEADBEEF"
        tampered["descriptors"][9]["descriptor_file_offset"] += 4
        tampered["descriptors"][10]["layers"][0]["gfx"][
            "compressed_size"
        ] += 1
        tampered["descriptors"][11]["layers"][0]["tilemap"][
            "compressed_sha256"
        ] = "0" * 64
        tampered["descriptors"][12]["layers"][0]["gfx"][
            "decompressed_size"
        ] += 1
        try:
            manifest_path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_tile_asset_bg_export(ROOT, self.output_dir)
        finally:
            manifest_path.write_bytes(original)

        joined = "\n".join(result["errors"])
        self.assertIn("source table metadata mismatch", joined)
        self.assertIn("complete layer count mismatch", joined)
        self.assertIn("atlas 0 metadata mismatch", joined)
        self.assertIn("descriptor GBA address mismatch", joined)
        self.assertIn("layer D tile-base semantics mismatch", joined)
        self.assertIn("layer A definition mismatch", joined)
        self.assertIn("layer B palette-bank semantics mismatch", joined)
        self.assertIn("layer A gfx_pointer mismatch", joined)
        self.assertIn("layer B tilemap_pointer mismatch", joined)
        self.assertIn("layer C palette_pointer mismatch", joined)
        self.assertIn("descriptor file offset mismatch", joined)
        self.assertIn("compressed component size mismatch", joined)
        self.assertIn("compressed component hash mismatch", joined)
        self.assertIn("decompressed component size mismatch", joined)

    def test_cli_and_committed_artifacts_repeat_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            cli_output = Path(directory) / "cli"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/export_tile_asset_bg_layers.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(cli_output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("236 complete BG layers", completed.stdout)

            expected_names = {
                path.name
                for path in self.output_dir.iterdir()
                if path.is_file()
            }
            self.assertEqual(
                expected_names,
                {path.name for path in cli_output.iterdir() if path.is_file()},
            )
            for name in expected_names:
                self.assertEqual(
                    (self.output_dir / name).read_bytes(),
                    (cli_output / name).read_bytes(),
                )

            committed = ROOT / "artifacts/tile-assets-bg-v1"
            self.assertEqual(
                expected_names,
                {path.name for path in committed.iterdir() if path.is_file()},
            )
            for name in expected_names:
                self.assertEqual(
                    (self.output_dir / name).read_bytes(),
                    (committed / name).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
