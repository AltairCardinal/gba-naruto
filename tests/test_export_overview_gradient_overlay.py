import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class ExportOverviewGradientOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_overview_gradient_overlay import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)
        cls.manifest = json.loads(
            (cls.output / "manifest.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_binds_generator_caller_and_live_controller(self):
        self.assertEqual("overview-gradient-overlay-v1", self.payload["schema"])
        self.assertEqual(
            {
                "gba_start": "0x0808D934",
                "gba_end_exclusive": "0x0808DA80",
                "size": 332,
                "sha256": (
                    "d5c6e7269c416817aae299d3d987c27abda6c1bde1a1edea0932329ce7179e96"
                ),
            },
            self.payload["generator"]["code"],
        )
        self.assertEqual("0x0808DAB8", self.payload["caller"]["generator_call"])
        self.assertEqual("0x0808DABC", self.payload["caller"]["bg0cnt_write"])
        self.assertEqual("0x0808DCFC", self.payload["controller"]["caller_call"])
        self.assertEqual(
            "0x0808DF1A",
            self.payload["runtime_binding"]["active_task"]["resume_pc"],
        )

    def test_reconstructs_exact_generated_tiles_palette_and_map(self):
        generated = self.payload["generated"]
        expected = {
            "tiles": (
                "generated-tiles.4bpp.bin",
                352,
                "9c54d11cc0b46d60728f59611b2181241626bfaad61c479536a14dbf0e54a2e4",
            ),
            "palette": (
                "generated-palette.bgr555.bin",
                32,
                "19b43b15fd2dcc824f03e524fad7a77d990ecb7b79eb3fa876ac862a53b7c7a5",
            ),
            "tilemap": (
                "generated-tilemap-30x20.bin",
                1200,
                "9d3188d3ef983613085b4808e19063e4bb1b4be955aa6e67041ae07a73a0d523",
            ),
        }
        for key, (relative, size, sha256) in expected.items():
            item = generated[key]
            self.assertEqual(relative, item["file"])
            self.assertEqual(size, item["size"])
            self.assertEqual(sha256, item["sha256"])
            data = (self.output / relative).read_bytes()
            self.assertEqual(size, len(data))
            self.assertEqual(sha256, hashlib.sha256(data).hexdigest())

        self.assertEqual(11, generated["tiles"]["tile_count"])
        self.assertEqual(16, generated["palette"]["color_count"])
        self.assertEqual([30, 20], generated["tilemap"]["dimensions"])
        self.assertEqual(
            {
                "blank_tile": 0x0100,
                "gradient_rows": [
                    {"row": row, "tile": 0xD101 + row - 4}
                    for row in range(4, 14)
                ],
                "palette_bank": 13,
            },
            generated["tilemap"]["layout"],
        )

    def test_records_the_exact_generator_formulas_and_destinations(self):
        formulas = self.payload["generator"]["formulas"]
        self.assertEqual("floor(y * 15 / 80) + 1", formulas["pixel_index"])
        self.assertEqual(
            "pixel_index repeated across all 8 pixels of scanline y",
            formulas["tile_scanline"],
        )
        self.assertEqual(
            "0 if index == 0 else 20 - index",
            formulas["palette_component"],
        )
        self.assertEqual(
            "component | component << 5 | component << 10",
            formulas["palette_bgr555"],
        )
        destinations = self.payload["generator"]["destinations"]
        self.assertEqual("0x02002AB0", destinations["work_tiles"])
        self.assertEqual("0x02002C10", destinations["work_palette"])
        self.assertEqual("0x02002C30", destinations["work_tilemap"])
        self.assertEqual("0x06002000", destinations["vram_tiles"])
        self.assertEqual("0x050001A0", destinations["pram_palette"])
        self.assertEqual("0x06000000", destinations["vram_tilemap"])

    def test_checkpoint_exactly_matches_work_buffers_and_hardware_destinations(self):
        runtime = self.payload["runtime_binding"]
        self.assertEqual(
            "artifacts/runtime-checkpoints/alternate-character-overview.ss9",
            runtime["checkpoint"],
        )
        self.assertEqual(
            "209bf3c7321fedc93a6c957fb2c7b46f0d48aa56ea5c4bb3858fce93d0a336f6",
            runtime["checkpoint_sha256"],
        )
        self.assertEqual("0x0002", runtime["bg0cnt"])
        self.assertEqual(
            {
                "work_tiles": True,
                "work_palette": True,
                "work_tilemap": True,
                "vram_tiles": True,
                "pram_palette": True,
                "vram_tilemap_visible_30x20": True,
            },
            runtime["exact_matches"],
        )
        self.assertEqual(
            "checkpoint_writer_proven",
            runtime["identity_status"],
        )
        self.assertEqual(600, runtime["tilemap_exact_cell_count"])
        self.assertEqual(600, runtime["tilemap_cell_count"])

    def test_resolves_parent_initializer_unknown_denominator(self):
        resolution = self.payload["parent_unmatched_resolution"]
        self.assertEqual(
            {
                "artifact": (
                    "artifacts/initializer-resource-pack-v1/"
                    "initializer-resource-pack.json"
                ),
                "artifact_sha256": (
                    "c096e70c033f804548446272c47d43bfefa72eed173841e152c630c5436efba8"
                ),
                "manifest": (
                    "artifacts/initializer-resource-pack-v1/manifest.json"
                ),
                "manifest_sha256": (
                    "8fc7c3ea449b480c5065a97e70d0f6c5c0fa30a0dc3f942931f6be86264337a4"
                ),
            },
            resolution["parent"],
        )
        self.assertEqual(
            {
                "global_unmatched_cell_count": 898,
                "global_unmatched_distinct_hash_count": 39,
                "target_layer_unmatched_cell_count": 717,
                "target_layer_unmatched_distinct_hash_count": 17,
            },
            resolution["baseline"],
        )
        self.assertEqual(
            {
                "cell_count": 300,
                "distinct_hash_count": 10,
                "runtime_tile_ids": list(range(257, 267)),
            },
            {
                key: resolution["resolved"][key]
                for key in ("cell_count", "distinct_hash_count", "runtime_tile_ids")
            },
        )
        self.assertEqual(
            {
                "global_unmatched_cell_count": 598,
                "global_unmatched_distinct_hash_count": 29,
                "target_layer_unmatched_cell_count": 417,
                "target_layer_unmatched_distinct_hash_count": 7,
            },
            resolution["remaining"],
        )
        visible = resolution["visible_resource_domain"]
        self.assertEqual([32, 32], visible["screenblock_dimensions"])
        self.assertEqual([30, 20], visible["visible_dimensions"])
        self.assertEqual(600, visible["generated_visible_cell_count"])
        self.assertEqual(0, visible["unresolved_inside_visible_cell_count"])
        self.assertEqual(
            {
                "classification": "outside_visible_tilemap_padding",
                "cell_count": 417,
                "distinct_hash_count": 7,
                "right_padding_cell_count": 57,
                "bottom_padding_cell_count": 384,
                "right_bottom_overlap_cell_count": 24,
            },
            {
                key: visible["excluded_padding"][key]
                for key in (
                    "classification",
                    "cell_count",
                    "distinct_hash_count",
                    "right_padding_cell_count",
                    "bottom_padding_cell_count",
                    "right_bottom_overlap_cell_count",
                )
            },
        )
        for record in visible["excluded_padding"]["parent_records"]:
            for start, end in record["linear_cell_ranges"]:
                for linear in range(start, end):
                    self.assertTrue(linear % 32 >= 30 or linear // 32 >= 20)
        self.assertEqual(
            {
                "global_visible_resource_unmatched_cell_count": 181,
                "global_visible_resource_unmatched_distinct_hash_count": 22,
                "target_layer_visible_resource_unmatched_cell_count": 0,
                "target_layer_visible_resource_unmatched_distinct_hash_count": 0,
            },
            visible["effective_remaining"],
        )

    def test_preview_is_complete_indexed_240x160_overlay(self):
        preview = self.payload["generated"]["preview"]
        path = self.output / preview["file"]
        with Image.open(path) as image:
            image.load()
            self.assertEqual("P", image.mode)
            self.assertEqual((240, 160), image.size)
            self.assertEqual(0, image.info.get("transparency"))
        self.assertEqual(
            preview["sha256"],
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )

    def test_scope_does_not_promote_one_overlay_to_all_visual_states(self):
        self.assertEqual(
            {
                "generator_algorithm_code_verified": True,
                "generated_tiles_palette_tilemap_losslessly_exported": True,
                "overview_checkpoint_work_buffers_exact": True,
                "overview_checkpoint_hardware_destinations_exact": True,
                "overview_checkpoint_writer_identity_complete": True,
                "overview_checkpoint_visible_bg0_resource_domain_complete": True,
                "parent_unknown_padding_excluded_from_visible_resource_denominator": True,
                "whole_overview_screen_source_identity_complete": False,
                "all_callers_runtime_bound": False,
                "all_game_visual_states_complete": False,
                "generic_image_writeback_complete": False,
            },
            self.payload["scope"],
        )

    def test_independent_verifier_accepts_and_rejects_tamper(self):
        from tools.verify_overview_gradient_overlay import verify_artifact

        source = (
            ROOT / "tools" / "verify_overview_gradient_overlay.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        self.assertEqual(600, report["tilemap_exact_cell_count"])

        for relative in (
            "generated-tiles.4bpp.bin",
            "generated-palette.bgr555.bin",
            "generated-tilemap-30x20.bin",
            "overview-gradient-overlay.json",
            "overview-gradient-overlay.png",
            "manifest.json",
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                tampered = Path(tmp) / "artifact"
                shutil.copytree(self.output, tampered)
                path = tampered / relative
                raw = bytearray(path.read_bytes())
                raw[-1] ^= 1
                path.write_bytes(raw)
                rejected = verify_artifact(ROOT, tampered)
                self.assertFalse(rejected["verified"], relative)
                self.assertTrue(rejected["errors"], relative)

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "overview-gradient-overlay.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["generator"]["formulas"]["pixel_index"] = "unverified formula"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["overview-gradient-overlay.json"] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            payload_path = tampered / "overview-gradient-overlay.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["runtime_binding"]["checkpoint"] = "forged-checkpoint.ss9"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["overview-gradient-overlay.json"] = hashlib.sha256(
                payload_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            linked = Path(tmp) / "artifact-link"
            linked.symlink_to(self.output, target_is_directory=True)
            rejected = verify_artifact(ROOT, linked)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "extra.txt").write_text("unexpected", encoding="utf-8")
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

    def test_promotion_manifest_hashes_only_declared_files(self):
        self.assertEqual("git-artifact-promotion-v1", self.manifest["schema"])
        self.assertEqual(
            "overview-gradient-overlay-v1",
            self.manifest["artifact_schema"],
        )
        self.assertEqual("accepted", self.manifest["artifact_status"])
        self.assertEqual(
            {
                "generated-palette.bgr555.bin",
                "generated-tilemap-30x20.bin",
                "generated-tiles.4bpp.bin",
                "overview-gradient-overlay.json",
                "overview-gradient-overlay.png",
            },
            set(self.manifest["files"]),
        )
        for relative, expected in self.manifest["files"].items():
            self.assertEqual(
                expected,
                hashlib.sha256((self.output / relative).read_bytes()).hexdigest(),
            )

    def test_output_target_rejects_repository_symlink_and_unrelated_data(self):
        from tools.export_overview_gradient_overlay import (
            export_artifact,
            validate_output_target,
        )

        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT)
        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT.parent)

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            unrelated = parent / "unrelated"
            unrelated.mkdir()
            sentinel = unrelated / "keep.txt"
            sentinel.write_text("user data", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_artifact(ROOT, unrelated)
            self.assertEqual("user data", sentinel.read_text(encoding="utf-8"))

            symlink = parent / "link"
            symlink.symlink_to(self.output, target_is_directory=True)
            with self.assertRaises(ValueError):
                validate_output_target(ROOT, symlink)
