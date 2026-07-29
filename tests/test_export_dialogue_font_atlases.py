#!/usr/bin/env python3
"""Lossless export of both localized base-ROM dialogue glyph branches."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SJIS_TABLE_SHA256 = (
    "6c396ab55b0cbeacb4d2d2d8df55666ab79fcfa426377ef91d03ab7743a7b18d"
)
BYTE_TABLE_SHA256 = (
    "f6d1d6950f29cf0cb2e03e3d365ac5cc8faaafd2336c12c8ab28673602873b90"
)
LOCALIZED_MAPPING_SHA256 = (
    "174dcb43915385fe0eab3e63a0671bc07edfd984c5d31f78c390f617c004a43d"
)
MAPPING_SHA256 = (
    "3a8b8bb998028d93cdbd0905dd929efb96e1d9643720cbd36b817daf31db7e6f"
)


class DialogueFontAtlasExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_dialogue_font_atlases import (
            export_dialogue_font_atlases,
        )

        cls._temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary.name) / "dialogue-font"
        cls.manifest = export_dialogue_font_atlases(ROOT, cls.output_dir)

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_exports_both_lookup_tables_and_every_source_record(self):
        manifest = self.manifest
        self.assertEqual("dialogue-font-atlas-v2", manifest["schema"])
        self.assertEqual(ROM_SHA256, manifest["rom"]["sha256"])
        self.assertEqual(
            {
                "file_offset": 0x53D644,
                "gba_address": "0x0853D644",
                "entry_count": 26,
                "entry_size": 8,
                "sha256": SJIS_TABLE_SHA256,
                "logical_glyph_count": 4410,
                "source_bytes_per_glyph": 32,
            },
            manifest["sjis_table"],
        )
        self.assertEqual(
            {
                "file_offset": 0x53D73C,
                "gba_address": "0x0853D73C",
                "entry_count": 2,
                "entry_size": 8,
                "sha256": BYTE_TABLE_SHA256,
                "logical_glyph_count": 192,
                "source_bytes_per_glyph": 16,
            },
            manifest["byte_table"],
        )
        self.assertEqual(4602, manifest["logical_glyph_count"])
        self.assertEqual(4602, manifest["unique_source_record_count"])
        self.assertEqual(9012, manifest["physical_half_tile_count"])
        self.assertEqual(0, manifest["logical_alias_count"])
        self.assertEqual(12, len(list(self.output_dir.iterdir())))

    def test_source_format_is_2bpp_and_code_expansion_is_exact(self):
        from tools.export_dialogue_font_atlases import (
            expand_2bpp_to_4bpp,
        )

        self.assertEqual(
            bytes.fromhex("98ba"),
            expand_2bpp_to_4bpp(bytes([0b11100100]), palette_group=2),
        )
        self.assertEqual(
            bytes.fromhex("dcfe"),
            expand_2bpp_to_4bpp(bytes([0b11100100]), palette_group=3),
        )
        source = self.manifest["source_format"]
        self.assertEqual(2, source["bits_per_pixel"])
        self.assertEqual(
            "bits 1:0, 3:2, 5:4, 7:6",
            source["pixel_order_within_byte"],
        )
        self.assertEqual(
            {
                "bytes": 32,
                "half_tile_count": 2,
                "half_tile_dimensions": [8, 8],
                "half_tile_order": [0, 1],
                "intrinsic_layout": "none",
            },
            source["sjis_record"],
        )
        self.assertEqual(
            {
                "bytes": 16,
                "tile_count": 1,
                "tile_dimensions": [8, 8],
                "intrinsic_layout": "single-tile",
            },
            source["byte_record"],
        )
        expansion = self.manifest["runtime_expansion"]
        self.assertEqual(
            "output_index = source_2bpp + (((arg1 & 1) + 2) << 2)",
            expansion["formula"],
        )
        self.assertEqual(
            [12, 13, 14, 15],
            expansion["sjis_cache_indices"],
        )
        self.assertEqual(
            [8, 9, 10, 11],
            expansion["byte_cache_indices"],
        )
        self.assertEqual(
            "two ordered 8x8 4bpp tiles; final layout is consumer-defined",
            expansion["sjis_output"],
        )

    def test_runtime_consumers_prove_vertical_sjis_layout(self):
        layouts = {
            item["consumer"]: item
            for item in self.manifest["runtime_layouts"]
        }
        for consumer in ("0x0806626C", "0x0808CE8C", "0x0808CF08"):
            self.assertEqual(
                {
                    "consumer": consumer,
                    "role": "tilemap-layout",
                    "glyph_dimensions": [8, 16],
                    "half_tile_layout": "vertical",
                    "half_tile_order": ["top", "bottom"],
                    "horizontal_advance_tiles": 1,
                },
                {
                    key: layouts[consumer][key]
                    for key in (
                        "consumer",
                        "role",
                        "glyph_dimensions",
                        "half_tile_layout",
                        "half_tile_order",
                        "horizontal_advance_tiles",
                    )
                },
            )
        expansion = self.manifest["runtime_expansion"]
        self.assertEqual("0x08089310", expansion["cache_enclosing_function"])
        self.assertEqual("0x0808942C", expansion["cache_path_anchor"])
        self.assertEqual("0x080894A8", expansion["byte_cache_callsite"])
        self.assertEqual("0x080894DE", expansion["sjis_cache_callsite"])
        self.assertEqual(
            "undetermined",
            expansion["cache_path_final_layout"],
        )
        code_slices = {
            item["name"]: item
            for item in self.manifest["consumer_chain"]["code_slices"]
        }
        self.assertEqual(
            "66b825738fc35608b0a2eeb6641dd1d4a354b8716510e35cdb8d675f69e8fb03",
            code_slices["text_parser_vertical_layout"]["sha256"],
        )
        self.assertEqual(
            "d63541506eba58dc15f19989ef72cdbce3f4ccce748d48a7212fcfb333cb8ba7",
            code_slices["text_consumer_a_vertical_layout"]["sha256"],
        )
        self.assertEqual(
            "c61ec8fb439575c53b0d0a1b46d6fd935501155fe6a46a5a76b5f0e426dfae7a",
            code_slices["text_consumer_b_vertical_layout"]["sha256"],
        )
        self.assertIn("cache_expansion_path", code_slices)

    def test_independent_verifier_decodes_layout_instruction_semantics(self):
        from tools.verify_dialogue_font_atlases import (
            _verify_layout_instructions,
        )

        rom = (ROOT / "rom/base.gba").read_bytes()
        errors = []
        self.assertEqual(3, _verify_layout_instructions(rom, errors))
        self.assertEqual([], errors)

        tampered = bytearray(rom)
        tampered[0x066388] ^= 1
        errors = []
        self.assertEqual(2, _verify_layout_instructions(tampered, errors))
        self.assertTrue(
            any(
                "half 0 to current destination" in error
                for error in errors
            ),
            errors,
        )

    def test_sjis_aux_byte_and_source_boundaries_come_from_rom(self):
        entries = self.manifest["sjis_entries"]
        self.assertEqual(26, len(entries))
        self.assertEqual([0] * 25 + [4], [entry["aux_byte"] for entry in entries])
        self.assertEqual("0x085B4020", entries[25]["source_pointer"])
        self.assertEqual("0x085B6000", entries[25]["source_end_pointer"])
        self.assertEqual(255, entries[25]["range_size"])
        dataset = self.manifest["datasets"]["sjis_full"]
        self.assertEqual(
            "968a628e718e351cb3f97d52b9dfb7a8fce539ada0523f9ea16425470e60a6a3",
            dataset["source_sha256"],
        )
        self.assertEqual(
            "586ef4b2b731f56a358c640297a43c5db634d49dff85cb8736b7877d6cee3338",
            dataset["expanded_4bpp_sha256"],
        )
        self.assertEqual(76, dataset["all_zero_records"])

    def test_byte_branch_uses_16_bytes_and_is_contiguous_with_sjis_data(self):
        entries = self.manifest["byte_entries"]
        self.assertEqual(
            [
                (0x20, 0x60, "0x0809CD54", "0x0809D354"),
                (0xA0, 0x60, "0x0809D354", "0x0809D954"),
            ],
            [
                (
                    entry["lower"],
                    entry["range_size"],
                    entry["source_pointer"],
                    entry["source_end_pointer"],
                )
                for entry in entries
            ],
        )
        storage = self.manifest["storage_relationships"]
        self.assertEqual(0, storage["overlap_bytes"])
        self.assertEqual("0x0809D354", storage["byte_entry_boundary"])
        self.assertEqual("0x0809D954", storage["byte_to_sjis_boundary"])
        dataset = self.manifest["datasets"]["byte_full"]
        self.assertEqual(
            "2e780768db4da9eb3705c6b4db428ed9ed905ef377bcaab72ef2fede5ff8d800",
            dataset["source_sha256"],
        )
        self.assertEqual(
            "78d754494557e6701b315dc784456754376e944c052af619a7eeaf0479fee68f",
            dataset["expanded_4bpp_sha256"],
        )

    def test_chapter_intro_mapping_is_rechecked_against_rom(self):
        source = self.manifest["chapter_intro_mapping"]
        self.assertEqual(MAPPING_SHA256, source["sha256"])
        self.assertEqual(517, source["mapping_count"])
        self.assertEqual(517, source["verified_mapping_count"])
        self.assertEqual([], source["errors"])
        dataset = self.manifest["datasets"]["chapter_intro_used"]
        self.assertEqual(
            "124f204bce726a33d4dd795e6aaf6440c737d7b8a92897b46e14f9330b0bdfea",
            dataset["source_sha256"],
        )
        self.assertEqual(
            "c8d7d5ee1c2e4c59f069b54ca3bd1ced6bb53e326f0669e40d5c32998e06dd58",
            dataset["expanded_4bpp_sha256"],
        )
        self.assertEqual([0, 1, 2, 3], dataset["source_indices_used"])

    def test_historical_group0_examples_are_covered_by_the_sjis_table(self):
        entries = self.manifest["sjis_entries"]
        for sjis, expected_entry in ((0x88CF, 4), (0x8FC2, 11)):
            hits = [
                entry["index"]
                for entry in entries
                if entry["lower"]
                <= sjis
                < entry["lower"] + entry["range_size"]
            ]
            self.assertEqual([expected_entry], hits)

    def test_known_localized_glyphs_are_bound_to_rom_sources(self):
        evidence = self.manifest["localized_mapping_evidence"]
        self.assertEqual(
            "sequel/content/text/sjis-to-tile-mapping.json",
            evidence["path"],
        )
        self.assertEqual(LOCALIZED_MAPPING_SHA256, evidence["sha256"])
        self.assertEqual(19, evidence["semantic_mapping_count"])
        self.assertEqual(1, evidence["unresolved_code_count"])
        self.assertEqual(20, evidence["source_resolved_count"])
        self.assertEqual([], evidence["errors"])
        samples = {
            item["sjis_hex"]: (
                item["display_character"],
                item["semantic_status"],
                item["source_pointer"],
                item["source_sha256"],
            )
            for item in evidence["mappings"]
        }
        self.assertEqual(
            (
                "什",
                "historical_ocr_label",
                "0x080A2754",
                "95628aafdf25dc250aa439cc814e62c4e4cd0dfb5d76440af0d79221883be675",
            ),
            samples["0x88CF"],
        )
        self.assertEqual(
            (
                "么",
                "historical_ocr_label",
                "0x080ACD94",
                "6ca10a1eb18ac95404c686185c6111bd1aac284b97db70110e234532dd4da1af",
            ),
            samples["0x8FC2"],
        )
        self.assertEqual(
            (
                None,
                "unresolved",
                "0x080A6194",
                "359b3ed5aa018173a0f708adb7cb7cbb776bd4823118eec06a76f73212a1dd1e",
            ),
            samples["0x8B62"],
        )
        stream = evidence["group0_stream"]
        self.assertEqual(0x459414, stream["file_offset"])
        self.assertEqual(41, stream["size"])
        self.assertEqual(20, stream["sjis_token_count"])
        self.assertEqual(
            [
                {
                    "relative_offset": 26,
                    "file_offset": 0x45942E,
                    "value": "0x0A",
                }
            ],
            stream["control_bytes"],
        )
        self.assertEqual(
            "dc998ad097f02104c488a3d380a17b37ad02b89cba5491b49ed444d55dab2370",
            stream["sha256"],
        )
        scope = self.manifest["scope"]
        self.assertTrue(scope["localized_base_rom_glyph_sources_exported"])
        self.assertTrue(scope["group0_known_codes_use_sjis_table"])
        self.assertFalse(scope["runtime_replacement_layer_proven"])
        self.assertFalse(scope["full_unicode_naming_complete"])

    def test_group0_control_byte_is_not_mislabeled_as_a_sjis_glyph(self):
        from tools.translate_sjis_to_chinese import (
            load_mapping,
            translate_bytes,
        )

        rom = (ROOT / "rom/base.gba").read_bytes()
        raw = rom[0x459414 : 0x459414 + 41]
        translated, unknowns = translate_bytes(raw, load_mapping())
        self.assertEqual(
            "什么！？……真拿你没办法?\n最后一次哦！！",
            translated,
        )
        self.assertEqual(["8B62"], unknowns)

    def test_sjis_atlas_stacks_ordered_half_tiles_vertically(self):
        dataset = self.manifest["datasets"]["sjis_full"]
        self.assertEqual(8, dataset["item_width"])
        self.assertEqual(16, dataset["item_height"])
        self.assertEqual(
            "vertical-proven-consumer-layout",
            dataset["item_layout"],
        )
        self.assertEqual(3, dataset["expansion_palette_group"])
        self.assertEqual(
            "0x080894DE callsite in 0x08089310 function; arg1=1",
            dataset["expansion_context"],
        )
        glyph = next(
            glyph
            for glyph in self.manifest["sjis_glyphs"]
            if glyph["sjis"] == 0x82A0
        )
        source = (
            self.output_dir / dataset["source_bin"]
        ).read_bytes()
        offset = glyph["logical_index"] * dataset["source_bytes_per_item"]
        record = source[offset : offset + dataset["source_bytes_per_item"]]

        def decode_half(raw):
            return [
                (packed >> shift) & 3
                for packed in raw
                for shift in (0, 2, 4, 6)
            ]

        top = decode_half(record[:16])
        bottom = decode_half(record[16:])
        expected = bytes(top + bottom)

        with Image.open(self.output_dir / dataset["atlas_png"]) as image:
            per_row = dataset["atlas_width"] // dataset["item_width"]
            item_index = glyph["logical_index"]
            x = (item_index % per_row) * dataset["item_width"]
            y = (item_index // per_row) * dataset["item_height"]
            actual = image.crop((x, y, x + 8, y + 16)).tobytes()
        self.assertEqual(expected, actual)

    def test_pngs_visualize_source_indices_without_runtime_color_claims(self):
        palette = self.manifest["visualization_palette"]
        self.assertEqual("diagnostic-source-2bpp-grayscale-v1", palette["id"])
        self.assertFalse(palette["runtime_verified"])
        self.assertIsNone(palette["transparent_index"])
        for dataset in self.manifest["datasets"].values():
            with Image.open(self.output_dir / dataset["atlas_png"]) as image:
                image.load()
                self.assertEqual("P", image.mode)
                self.assertEqual(
                    (dataset["atlas_width"], dataset["atlas_height"]),
                    image.size,
                )
                self.assertNotIn("transparency", image.info)
                self.assertEqual(
                    dataset["source_indices_used"],
                    sorted(set(image.tobytes())),
                )

    def test_independent_verifier_checks_source_expansion_and_pixels(self):
        from tools.verify_dialogue_font_atlases import (
            verify_dialogue_font_atlases,
        )

        verifier_source = (
            ROOT / "tools/verify_dialogue_font_atlases.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools.", verifier_source)
        result = verify_dialogue_font_atlases(ROOT, self.output_dir)
        self.assertEqual(4602, result["verified_logical_glyphs"])
        self.assertEqual(9012, result["verified_half_tiles"])
        self.assertEqual(4, result["verified_atlases"])
        self.assertEqual(3, result["verified_layout_consumers"])
        self.assertEqual([], result["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "manifest"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "manifest.json"
            tampered = json.loads(path.read_text(encoding="utf-8"))
            tampered["sjis_entries"][25]["aux_byte"] = 0
            path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_dialogue_font_atlases(ROOT, tampered_dir)
            self.assertTrue(
                any("sjis_entries[25].aux_byte" in error for error in result["errors"]),
                result["errors"],
            )

        with tempfile.TemporaryDirectory() as temporary:
            tampered_dir = Path(temporary) / "binary"
            shutil.copytree(self.output_dir, tampered_dir)
            path = tampered_dir / "sjis-full-expanded-4bpp.bin"
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
            result = verify_dialogue_font_atlases(ROOT, tampered_dir)
            self.assertTrue(
                any(
                    "sjis-full-expanded-4bpp.bin" in error
                    for error in result["errors"]
                ),
                result["errors"],
            )

    def test_exporter_reuses_png_primitive_and_clis_run_from_root(self):
        source = (
            ROOT / "tools/export_dialogue_font_atlases.py"
        ).read_text(encoding="utf-8")
        self.assertIn("indexed_png_from_bgr555", source)
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "dialogue-font"
            export = subprocess.run(
                [
                    sys.executable,
                    "tools/export_dialogue_font_atlases.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, export.returncode, export.stderr)
            verify = subprocess.run(
                [
                    sys.executable,
                    "tools/verify_dialogue_font_atlases.py",
                    "--root",
                    ".",
                    "--artifact-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, verify.returncode, verify.stderr)
            report = json.loads(verify.stdout)
            self.assertEqual([], report["errors"])


if __name__ == "__main__":
    unittest.main()
