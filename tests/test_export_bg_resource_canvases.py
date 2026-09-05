import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
TABLE_SHA256 = "57e9b8b6b7c3003615c39539f80934f142efeb1e6674114fbaca98bc629f7da2"
CONSUMER_SHA256 = "1d581ddbdfb89f17de5b5e52fd1b34d9952fcaddf8e4f24f1f86982facf6db27"


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportBgResourceCanvasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_bg_resource_canvases import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_complete_hash_bound_table_and_consumer(self):
        manifest = self.manifest
        self.assertEqual("bg-resource-canvases-v1", manifest["schema"])
        self.assertEqual(TABLE_SHA256, manifest["table"]["sha256"])
        self.assertEqual(14, manifest["table"]["entry_count"])
        self.assertEqual([0, 8], manifest["table"]["empty_entry_ids"])
        self.assertEqual(CONSUMER_SHA256, manifest["consumer"]["sha256"])
        self.assertEqual(
            [0x0807AAA6, 0x0808F522, 0x08091716, 0x080930D6],
            manifest["consumer"]["direct_callers"],
        )
        self.assertEqual(
            {
                "battle_header_formula": (
                    "u8[0x0853D910 + battle_id * 0x20 + 0x1C]"
                ),
                "battle_header_entry_distribution": {
                    "1": 23,
                    "2": 3,
                    "3": 5,
                    "4": 4,
                    "5": 1,
                    "6": 1,
                    "7": 10,
                },
                "special_input_formula": (
                    "input_id > 49: entry_id = input_id - 41"
                ),
                "fixed_entry_calls": {
                    "0x08091716": 9,
                    "0x080930D6": 1,
                },
                "loader_bounds_check": False,
            },
            manifest["consumer"]["entry_selection"],
        )
        self.assertEqual(12, manifest["summary"]["canvas_count"])
        self.assertEqual(7, manifest["summary"]["4bpp_canvas_count"])
        self.assertEqual(5, manifest["summary"]["8bpp_canvas_count"])
        self.assertEqual(11, manifest["summary"]["unique_graphics_count"])
        self.assertEqual(12, manifest["summary"]["unique_palette_count"])
        self.assertEqual(8, manifest["summary"]["unique_tilemap_count"])
        self.assertEqual(
            list(range(1, 8)) + list(range(9, 14)),
            [entry["entry_id"] for entry in manifest["entries"]],
        )

    def test_preserves_source_payloads_and_renders_full_screen_canvases(self):
        for entry in self.manifest["entries"]:
            self.assertEqual(32, entry["tilemap"]["width_tiles"])
            self.assertEqual(10, entry["tilemap"]["height_tiles"])
            self.assertEqual(640, entry["tilemap"]["decompressed_size"])
            self.assertEqual(384, entry["palette"]["decompressed_size"])
            self.assertEqual(
                "8bpp" if entry["mode_flag"] else "4bpp",
                entry["pixel_mode"],
            )
            for key in ("graphics", "palette", "tilemap"):
                source = entry[key]
                path = self.output / source["file"]
                self.assertEqual(
                    source["decompressed_sha256"],
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            with Image.open(self.output / entry["canvas"]["png"]) as image:
                image.load()
                self.assertEqual("P", image.mode)
                self.assertEqual((256, 160), image.size)
                self.assertNotIn("transparency", image.info)
            with Image.open(
                self.output / entry["source_strip"]["png"]
            ) as image:
                image.load()
                self.assertEqual("P", image.mode)
                self.assertEqual((256, 80), image.size)

        first = self.manifest["entries"][0]
        self.assertEqual(1, first["entry_id"])
        self.assertEqual(3072, first["graphics"]["decompressed_size"])
        self.assertEqual(
            "c5463fdae80642349f275722801017ff3e23bdffa88190ca111a3184bafd38c1",
            first["graphics"]["decompressed_sha256"],
        )
        ninth = self.manifest["entries"][7]
        self.assertEqual(9, ninth["entry_id"])
        self.assertEqual(19264, ninth["graphics"]["decompressed_size"])
        self.assertEqual(
            "298f88e6750cac7a61d854afcf0cc9b961d98d5b59bfc5824f294930557192d1",
            ninth["graphics"]["decompressed_sha256"],
        )

    def test_scope_does_not_overclaim_runtime_selection_semantics(self):
        self.assertEqual(
            {
                "all_static_table_entries_exported": True,
                "full_source_space_canvases_rendered": True,
                "4bpp_and_8bpp_modes_verified": True,
                "runtime_entry_selection_complete": False,
                "scrolling_and_layer_composition_complete": False,
                "scene_names_complete": False,
            },
            self.manifest["scope"],
        )

    def test_independent_verifier_accepts_export_and_rejects_tamper(self):
        from tools.verify_bg_resource_canvases import verify_artifact

        source = (
            ROOT / "tools" / "verify_bg_resource_canvases.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertEqual(
            "bg-resource-canvases-verification-v1", report["schema"]
        )
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        self.assertEqual(12, report["canvases"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            path = tampered / self.manifest["entries"][0]["canvas"]["png"]
            raw = bytearray(path.read_bytes())
            raw[-1] ^= 1
            path.write_bytes(raw)
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            path = tampered / "manifest.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["entries"][0]["mode_flag"] = 1
            path.write_text(json.dumps(data), encoding="utf-8")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            path = tampered / self.manifest["entries"][0]["graphics"]["file"]
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "unexpected.bin").write_bytes(b"unexpected")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

        for field, value in (
            (("rom", "file"), "wrong.gba"),
            (("consumer", "graphics_destination"), "0xDEADBEEF"),
            (("entries", 0, "descriptor_gba_address"), "0xDEADBEEF"),
        ):
            with tempfile.TemporaryDirectory() as temporary:
                tampered = Path(temporary) / "artifact"
                shutil.copytree(self.output, tampered)
                manifest_path = tampered / "manifest.json"
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                target = data
                for key in field[:-1]:
                    target = target[key]
                target[field[-1]] = value
                manifest_path.write_text(
                    json.dumps(data),
                    encoding="utf-8",
                )
                report = verify_artifact(ROOT, tampered)
                self.assertFalse(report["verified"], field)
                self.assertTrue(report["errors"], field)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            manifest_path = tampered / "manifest.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            relative = data["entries"][0]["source_strip"]["png"]
            source_path = tampered / relative
            with Image.open(source_path) as image:
                image.load()
                palette = image.getpalette()
                palette[:3] = [255, 0, 255]
                image.putpalette(palette)
                image.save(source_path, format="PNG")
            data["entries"][0]["source_strip"]["png_sha256"] = hashlib.sha256(
                source_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_export_is_deterministic_and_cli_is_repository_relative(self):
        from tools.export_bg_resource_canvases import export_artifact

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            second = export_artifact(ROOT, output)
            self.assertEqual(self.manifest, second)
            self.assertEqual(
                directory_hashes(self.output),
                directory_hashes(output),
            )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_bg_resource_canvases.py",
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
            self.assertIn('"canvases": 12', result.stdout)
            self.assertTrue((output / "manifest.json").is_file())

    def test_output_target_rejects_repository_symlink_and_unrelated_data(self):
        from tools.export_bg_resource_canvases import (
            export_artifact,
            validate_output_target,
        )

        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT)
        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT.parent)

        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            unrelated = parent / "unrelated"
            unrelated.mkdir()
            sentinel = unrelated / "keep.txt"
            sentinel.write_text("user data", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_artifact(ROOT, unrelated)
            self.assertEqual("user data", sentinel.read_text(encoding="utf-8"))

            symlink = parent / "link"
            symlink.symlink_to(unrelated, target_is_directory=True)
            with self.assertRaises(ValueError):
                validate_output_target(ROOT, symlink)


if __name__ == "__main__":
    unittest.main()
