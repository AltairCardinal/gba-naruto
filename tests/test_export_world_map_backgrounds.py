import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportWorldMapBackgroundsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_world_map_backgrounds import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_binds_exact_tables_and_consumers(self):
        manifest = self.manifest
        self.assertEqual("world-map-backgrounds-v1", manifest["schema"])
        self.assertEqual(
            "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
            manifest["rom"]["sha256"],
        )
        self.assertEqual(
            {
                "backgrounds": {
                    "gba_address": "0x085A8014",
                    "entry_count": 3,
                    "entry_size": 12,
                    "sha256": (
                        "9ccd6d722b87a8bf910fb45072ad682d89b9cf3432979b"
                        "163f57283902396f35"
                    ),
                },
                "labels": {
                    "gba_address": "0x085A8038",
                    "entry_count": 3,
                    "entry_size": 16,
                    "sha256": (
                        "67b4a34289072f9a89b7f79721df851e6f23409d1c23dc"
                        "4f90ae7f5d6130d052"
                    ),
                },
            },
            manifest["source_tables"],
        )
        self.assertEqual(
            {
                "background_loader": (
                    "e66468161801a8d10f070d8d505efdfd39b966fdcd96c60f"
                    "c1b6c384c7cecd12"
                ),
                "selection_and_load_calls": (
                    "256b740d579cbf6f61a29c2504f7f4eb414dd9e7fbd1e219"
                    "55ba520d1cf19b2c"
                ),
                "packed_tilemap_copier": (
                    "844be072d9572bd9a657357e745977ed9435c647d0ec0e811"
                    "f66c953c84a1bd6"
                ),
                "text_wrapper": (
                    "2a90d5fc068dec5c806ec3c973772d726efdaa3a48ac6d2f"
                    "c64a805f3c40c5ef"
                ),
                "background_loader_literal_pool": (
                    "5fad3d9b96d7d52dd1f3f06892e1184a46209023f887ab25"
                    "bc352f289322e19f"
                ),
                "selection_literal_pool": (
                    "5c1f9eb562810b706dcf6ca68342e8fe10e7a4e9b57dcff8"
                    "1f885245884acc2f"
                ),
            },
            {
                key: value["sha256"]
                for key, value in manifest["consumer_evidence"].items()
            },
        )

    def test_exports_all_backgrounds_and_deduplicates_shared_map(self):
        pages = self.manifest["pages"]
        self.assertEqual([0, 1, 2], [page["page_id"] for page in pages])
        self.assertEqual(
            ["0x084414E4", "0x084497BC", "0x0845087C"],
            [page["background"]["graphics_pointer"] for page in pages],
        )
        self.assertEqual(
            ["0x084413A4", "0x0844967C", "0x0845073C"],
            [page["background"]["palette_pointer"] for page in pages],
        )
        self.assertEqual(1, self.manifest["summary"]["unique_tilemap_count"])
        self.assertEqual(
            {"shared/tilemap-30x20.bin"},
            {page["background"]["tilemap_file"] for page in pages},
        )
        for page in pages:
            background = page["background"]
            self.assertEqual(8, background["bits_per_pixel"])
            self.assertEqual(512, background["tile_count"])
            self.assertEqual([30, 20], background["dimensions_tiles"])
            self.assertEqual([240, 160], background["canvas"]["dimensions"])
            self.assertEqual(160, background["palette_color_count"])
            self.assertEqual(159, background["maximum_pixel_index"])
            self.assertTrue(background["all_tiles_referenced"])
            self.assertEqual([], background["missing_tile_indices"])
            self.assertEqual(0, background["horizontal_flip_entry_count"])
            self.assertEqual(0, background["vertical_flip_entry_count"])
            self.assertEqual([0], background["palette_bank_values"])
            self.assertFalse(background["palette_index_zero_used"])
            self.assertTrue((self.output / background["canvas"]["file"]).is_file())

    def test_binds_four_code_labels_to_existing_font_asset(self):
        expected = [
            ["0x92BB", "0x99DE", "0x9BD6", "0x90EC"],
            ["0x8140", "0x89A5", "0x9BD6", "0x8D99"],
            ["0x8140", "0x965E", "0x9BD6", "0x954B"],
        ]
        self.assertEqual(
            expected,
            [[glyph["code"] for glyph in page["label"]["glyphs"]] for page in self.manifest["pages"]],
        )
        for page in self.manifest["pages"]:
            label = page["label"]
            self.assertEqual(4, label["glyph_count"])
            self.assertEqual([64, 8], label["preview"]["dimensions"])
            self.assertEqual(
                "artifacts/dialogue-font-v2/manifest.json",
                label["font_dependency"]["manifest"],
            )
            self.assertTrue(label["font_dependency"]["all_glyphs_covered"])
            self.assertTrue((self.output / label["record_file"]).is_file())
            self.assertTrue((self.output / label["preview"]["file"]).is_file())

    def test_records_static_scope_without_overclaiming_runtime_composite(self):
        self.assertEqual(
            {
                "all_background_rows_exported": True,
                "all_label_rows_exported": True,
                "native_background_canvases_complete": True,
                "label_token_to_glyph_binding_complete": True,
                "label_font_graphics_already_covered": True,
                "runtime_label_palette_complete": False,
                "runtime_label_screen_position_complete": False,
                "selection_cursor_complete": False,
                "final_screen_composition_complete": False,
                "natural_language_label_names_complete": False,
            },
            self.manifest["scope"],
        )

    def test_independent_verifier_accepts_export_and_rejects_tamper(self):
        from tools.verify_world_map_backgrounds import verify_artifact

        source = (
            ROOT / "tools" / "verify_world_map_backgrounds.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(3, report["page_count"])

        for relative in (
            "manifest.json",
            "shared/tilemap-30x20.bin",
            self.manifest["pages"][0]["background"]["canvas"]["file"],
            self.manifest["pages"][0]["label"]["preview"]["file"],
        ):
            with tempfile.TemporaryDirectory() as temporary:
                tampered = Path(temporary) / "artifact"
                shutil.copytree(self.output, tampered)
                path = tampered / relative
                raw = bytearray(path.read_bytes())
                raw[-1] ^= 1
                path.write_bytes(raw)
                report = verify_artifact(ROOT, tampered)
                self.assertFalse(report["verified"], relative)
                self.assertTrue(report["errors"], relative)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "unexpected.bin").write_bytes(b"not part of the artifact")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertIn("unexpected file: unexpected.bin", report["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "page-00/label-record.bin").unlink()
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertIn(
                "missing file: page-00/label-record.bin",
                report["errors"],
            )

    def test_verifier_rejects_wrong_font_dependency_identity(self):
        from tools.verify_world_map_backgrounds import verify_artifact

        for field, value in (
            ("schema", "tampered-schema"),
            ("rom", {"sha256": "0" * 64}),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "root"
                (root / "rom").mkdir(parents=True)
                (root / "artifacts/dialogue-font-v2").mkdir(parents=True)
                shutil.copy2(ROOT / "rom/base.gba", root / "rom/base.gba")
                dependency = json.loads(
                    (
                        ROOT / "artifacts/dialogue-font-v2/manifest.json"
                    ).read_text(encoding="utf-8")
                )
                dependency[field] = value
                (
                    root / "artifacts/dialogue-font-v2/manifest.json"
                ).write_text(
                    json.dumps(dependency, ensure_ascii=False),
                    encoding="utf-8",
                )
                report = verify_artifact(root, self.output)
                self.assertFalse(report["verified"], field)
                self.assertTrue(report["errors"], field)

    def test_export_is_deterministic_and_output_target_is_safe(self):
        from tools.export_world_map_backgrounds import (
            export_artifact,
            validate_output_target,
        )

        committed = ROOT / "artifacts/world-map-backgrounds-v1"
        self.assertEqual(directory_hashes(self.output), directory_hashes(committed))

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            second = export_artifact(ROOT, output)
            self.assertEqual(self.manifest, second)
            self.assertEqual(directory_hashes(self.output), directory_hashes(output))

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_world_map_backgrounds.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('"page_count": 3', result.stdout)

        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            unrelated = Path(temporary) / "unrelated"
            unrelated.mkdir()
            sentinel = unrelated / "keep.txt"
            sentinel.write_text("user data", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_artifact(ROOT, unrelated)
            self.assertEqual("user data", sentinel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
