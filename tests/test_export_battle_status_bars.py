import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class ExportBattleStatusBarsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_status_bars import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.payload = export_artifact(ROOT, cls.output)
        cls.manifest = json.loads(
            (cls.output / "manifest.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_binds_generator_literals_and_all_four_direct_calls(self):
        self.assertEqual("battle-status-bars-v1", self.payload["schema"])
        self.assertEqual(
            {
                "gba_start": "0x08068370",
                "gba_end_exclusive": "0x08068642",
                "size": 722,
                "sha256": (
                    "13ef2ceedfe889bee6b7a6666d268246f43daa3fe5ad0be83a37f275e4ff4b20"
                ),
            },
            self.payload["generator"]["code"],
        )
        self.assertEqual(
            [
                "0x0806F0D6",
                "0x0806F0EC",
                "0x0807A83C",
                "0x0807A8A6",
            ],
            self.payload["generator"]["direct_calls"],
        )
        self.assertEqual(
            {
                "graphics_base_pointer": "0x0201BD48",
                "screenblock_pointer": "0x0201BD50",
                "template_base_pointer": "0x0201BD54",
                "work_tiles": "0x0201BD84",
            },
            self.payload["generator"]["runtime_globals"],
        )

    def test_exports_complete_two_style_thirty_nine_level_family(self):
        generated = self.payload["generated"]
        self.assertEqual(2, generated["style_count"])
        self.assertEqual(39, generated["fill_level_count"])
        self.assertEqual(5, generated["tiles_per_bar"])
        self.assertEqual(160, generated["bytes_per_bar"])
        self.assertEqual(12480, generated["family"]["size"])
        self.assertEqual(320, generated["templates"]["size"])
        self.assertEqual(32, generated["palette"]["size"])
        self.assertEqual(
            "canonical-indexed-png-stored-deflate-v1",
            generated["contact_sheet"]["encoder"],
        )

        for key in ("family", "templates", "palette", "contact_sheet"):
            item = generated[key]
            data = (self.output / item["file"]).read_bytes()
            self.assertEqual(item["size"], len(data))
            self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())

        with Image.open(self.output / generated["contact_sheet"]["file"]) as image:
            image.load()
            self.assertEqual("P", image.mode)
            self.assertEqual((80, 312), image.size)
            self.assertEqual(0, image.info.get("transparency"))

    def test_exactly_closes_all_parent_battle_bg3_unknown_content(self):
        runtime = self.payload["runtime_binding"]
        self.assertEqual(30, runtime["checkpoint_count"])
        self.assertEqual(60, runtime["bar_count"])
        self.assertEqual(300, runtime["full_bar_tile_count"])
        self.assertEqual(181, runtime["parent_unknown_record_count"])
        self.assertEqual(181, runtime["parent_unknown_cell_count"])
        self.assertEqual(22, runtime["parent_unknown_distinct_hash_count"])
        self.assertEqual(181, runtime["exact_generated_unknown_cell_count"])
        self.assertEqual(22, runtime["exact_generated_unknown_distinct_hash_count"])
        self.assertEqual(0, runtime["unmatched_unknown_cell_count"])
        self.assertTrue(all(len(bar["fill_level_matches"]) == 1 for bar in runtime["bars"]))
        self.assertEqual(
            {0, 1},
            {bar["style"] for bar in runtime["bars"]},
        )

    def test_reduces_visible_resource_denominator_to_zero(self):
        resolution = self.payload["parent_visible_resource_resolution"]
        self.assertEqual(
            {
                "global_visible_resource_unmatched_cell_count": 181,
                "global_visible_resource_unmatched_distinct_hash_count": 22,
            },
            resolution["baseline"],
        )
        self.assertEqual(
            {
                "cell_count": 181,
                "distinct_hash_count": 22,
                "classification": "generated_battle_status_bar_content",
            },
            resolution["resolved"],
        )
        self.assertEqual(
            {
                "global_visible_resource_unmatched_cell_count": 0,
                "global_visible_resource_unmatched_distinct_hash_count": 0,
            },
            resolution["remaining"],
        )

    def test_scope_does_not_promote_tracked_bars_to_all_visual_states(self):
        self.assertEqual(
            {
                "generator_algorithm_code_verified": True,
                "source_templates_losslessly_exported": True,
                "all_fill_levels_losslessly_generated": True,
                "tracked_battle_bg3_unknown_content_fully_resolved": True,
                "tracked_visible_resource_denominator_complete": True,
                "all_game_visual_states_complete": False,
                "all_generator_callers_runtime_bound": False,
                "bar_input_field_semantics_complete": False,
                "generic_image_writeback_complete": False,
            },
            self.payload["scope"],
        )

    def test_independent_verifier_accepts_and_rejects_tamper(self):
        from tools.verify_battle_status_bars import verify_artifact

        source = (ROOT / "tools" / "verify_battle_status_bars.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        self.assertEqual(181, report["exact_generated_unknown_cell_count"])

        for relative in (
            "source-templates.4bpp.bin",
            "generated-family.4bpp.bin",
            "runtime-palette-bank13.bgr555.bin",
            "battle-status-bars.png",
            "battle-status-bars.json",
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
            payload_path = tampered / "battle-status-bars.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["generator"]["formula"]["fill_level"] = "forged formula"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["battle-status-bars.json"] = hashlib.sha256(
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
            payload_path = tampered / "battle-status-bars.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["generator"]["copy_route"]["hardware_screenblock"] = "0x06000000"
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["battle-status-bars.json"] = hashlib.sha256(
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
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source"]["generator_gba_address"] = "0x08000000"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

    def test_promotion_manifest_hashes_only_declared_files(self):
        self.assertEqual("git-artifact-promotion-v1", self.manifest["schema"])
        self.assertEqual("battle-status-bars-v1", self.manifest["artifact_schema"])
        self.assertEqual("accepted", self.manifest["artifact_status"])
        self.assertEqual(
            {
                "source-templates.4bpp.bin",
                "generated-family.4bpp.bin",
                "runtime-palette-bank13.bgr555.bin",
                "battle-status-bars.png",
                "battle-status-bars.json",
            },
            set(self.manifest["files"]),
        )
        for relative, expected in self.manifest["files"].items():
            self.assertEqual(
                expected,
                hashlib.sha256((self.output / relative).read_bytes()).hexdigest(),
            )

    def test_output_target_rejects_repository_symlink_and_unrelated_data(self):
        from tools.export_battle_status_bars import export_artifact, validate_output_target

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

            forged = parent / "forged"
            forged.mkdir()
            forged_sentinel = forged / "keep.txt"
            forged_sentinel.write_text("user data", encoding="utf-8")
            (forged / "manifest.json").write_text(
                json.dumps(
                    {
                        "artifact_schema": "battle-status-bars-v1",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                export_artifact(ROOT, forged)
            self.assertEqual(
                "user data", forged_sentinel.read_text(encoding="utf-8")
            )

            symlink = parent / "link"
            symlink.symlink_to(self.output, target_is_directory=True)
            with self.assertRaises(ValueError):
                validate_output_target(ROOT, symlink)
