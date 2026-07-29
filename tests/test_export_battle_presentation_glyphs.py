import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MESSAGE_TABLE_SHA256 = (
    "a58fee3bd11fd9db198f4c93faace06c268a1243870ce755aaf060f6b7acc877"
)
GLYPH_TABLE_SHA256 = (
    "1061b97ae8ec9006c2a4c7f235ec795df3d7e8a40cc6f2117e5e89d7e79e3770"
)
BINDING_TABLE_SHA256 = (
    "8b5557e99d159b2b3ea1701bc0a15d0f2acc95f766003ec706263fc62a3719e8"
)


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportBattlePresentationGlyphsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_presentation_glyphs import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_consumer_defined_tables_and_provenance(self):
        manifest = self.manifest
        self.assertEqual("battle-presentation-glyphs-v1", manifest["schema"])
        self.assertEqual(
            {
                "file_offset": 0x5A2B08,
                "gba_address": "0x085A2B08",
                "gba_end": "0x085A2C44",
                "entry_count": 79,
                "entry_size": 4,
                "sha256": MESSAGE_TABLE_SHA256,
                "raw_file": "source/message-pointer-table.bin",
            },
            manifest["tables"]["messages"],
        )
        self.assertEqual(
            {
                "file_offset": 0x5A2C44,
                "gba_address": "0x085A2C44",
                "gba_end": "0x085A2EF4",
                "entry_count": 172,
                "entry_size": 4,
                "sha256": GLYPH_TABLE_SHA256,
                "raw_file": "source/glyph-pointer-table.bin",
            },
            manifest["tables"]["glyphs"],
        )
        self.assertEqual(
            {
                "file_offset": 0x5A2EF4,
                "gba_address": "0x085A2EF4",
                "gba_end": "0x085A320A",
                "entry_count": 79,
                "entry_size": 10,
                "sha256": BINDING_TABLE_SHA256,
                "raw_file": "source/message-glyph-binding-table.bin",
            },
            manifest["tables"]["bindings"],
        )
        self.assertEqual(
            {
                "message_selector_literal": "0x080995E0",
                "message_selector_formula": (
                    "message_ptr = u32[0x085A2B08 + u8(message_id) * 4]"
                ),
                "glyph_table_literal": "0x080981A8",
                "binding_table_literals": [
                    "0x080981A4",
                    "0x08098FC4",
                ],
                "binding_formula": (
                    "binding = 0x085A2EF4 + u8(message_id) * 10"
                ),
                "glyph_formula": (
                    "glyph_stream = u32[0x085A2C44 + glyph_id * 4]"
                ),
                "display_formula": (
                    "glyph_id = binding[1 + display_slot]"
                ),
                "glyph_destination_stride": 512,
                "skip_glyph_id": 255,
                "bounds_check": False,
            },
            manifest["consumer"]["selection"],
        )
        self.assertEqual(
            {
                "glyph_preloader": (
                    "4827abc170644bda91140d48a597cd641df061faae15e40d6a83e4b9a29d74ed"
                ),
                "glyph_display_consumer": (
                    "6af0b1e7ecb858590d4dc422e1b5833f661602ff6137a65518a09aff874a32bc"
                ),
                "message_measure": (
                    "05a03ba78a859cb91cabfb865d3c58c80601054f43def714318c2124df7a9f03"
                ),
                "message_renderer": (
                    "8d599b9b21b70c455b0acb85a916806697f916b0271b8a42a7c8013ed1196804"
                ),
                "message_selector": (
                    "835b54df161608218062de4ad9743101456988d29af8fd5c0de165d0b7ebaa47"
                ),
            },
            {
                item["name"]: item["sha256"]
                for item in manifest["consumer"]["code_slices"]
            },
        )

    def test_exports_all_messages_bindings_and_glyph_images(self):
        manifest = self.manifest
        self.assertEqual(79, len(manifest["messages"]))
        self.assertEqual(172, len(manifest["glyphs"]))
        self.assertEqual(
            {
                "message_count": 79,
                "glyph_count": 172,
                "unique_glyph_count": 171,
                "bound_glyph_count": 138,
                "unbound_glyph_count": 34,
                "empty_binding_count": 4,
            },
            manifest["summary"],
        )
        for message_id, message in enumerate(manifest["messages"]):
            self.assertEqual(message_id, message["message_id"])
            raw = (self.output / message["raw_file"]).read_bytes()
            self.assertTrue(raw.endswith(b"\0"))
            self.assertEqual(message["raw_size"], len(raw))
            self.assertEqual(
                message["raw_sha256"], hashlib.sha256(raw).hexdigest()
            )
            self.assertEqual(
                message["binding"]["raw_size"], 10
            )
            binding = bytes.fromhex(message["binding"]["raw_hex"])
            self.assertEqual(10, len(binding))
            self.assertEqual(message["binding"]["glyph_count"], binding[0])
            self.assertLessEqual(binding[0], 8)
            self.assertTrue(
                all(glyph_id == 255 or 0 <= glyph_id < 172
                    for glyph_id in message["binding"]["glyph_ids"])
            )

        for glyph_id, glyph in enumerate(manifest["glyphs"]):
            self.assertEqual(glyph_id, glyph["glyph_id"])
            compressed = (self.output / glyph["compressed_file"]).read_bytes()
            graphics = (self.output / glyph["graphics_file"]).read_bytes()
            self.assertEqual(glyph["compressed_sha256"],
                             hashlib.sha256(compressed).hexdigest())
            self.assertEqual(glyph["graphics_sha256"],
                             hashlib.sha256(graphics).hexdigest())
            self.assertEqual(512, len(graphics))
            self.assertEqual(16, glyph["tile_count"])
            self.assertEqual("4bpp", glyph["pixel_mode"])
            with Image.open(self.output / glyph["png_file"]) as image:
                image.load()
                self.assertEqual("P", image.mode)
                self.assertEqual((32, 32), image.size)
                self.assertEqual(
                    glyph["raster_sha256"],
                    hashlib.sha256(image.tobytes()).hexdigest(),
                )

        with Image.open(self.output / manifest["atlas"]["png_file"]) as image:
            image.load()
            self.assertEqual("P", image.mode)
            self.assertEqual((512, 352), image.size)

    def test_scope_does_not_claim_text_decoding_or_runtime_palette(self):
        self.assertEqual(
            {
                "all_static_messages_exported": True,
                "all_static_glyphs_exported": True,
                "all_static_bindings_exported": True,
                "glyph_geometry_static_verified": True,
                "message_character_decoding_complete": False,
                "runtime_palette_binding_complete": False,
                "message_names_complete": False,
            },
            self.manifest["scope"],
        )

    def test_independent_verifier_accepts_export_and_rejects_tamper(self):
        from tools.verify_battle_presentation_glyphs import verify_artifact

        source = (
            ROOT / "tools" / "verify_battle_presentation_glyphs.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        self.assertEqual(79, report["messages"])
        self.assertEqual(172, report["glyphs"])

        targets = (
            self.manifest["messages"][0]["raw_file"],
            self.manifest["glyphs"][0]["graphics_file"],
            self.manifest["glyphs"][0]["png_file"],
        )
        for relative in targets:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                tampered = Path(tmp) / "artifact"
                shutil.copytree(self.output, tampered)
                path = tampered / relative
                raw = bytearray(path.read_bytes())
                raw[-1] ^= 1
                path.write_bytes(raw)
                report = verify_artifact(ROOT, tampered)
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            manifest_path = tampered / "manifest.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["consumer"]["selection"]["glyph_destination_stride"] = 256
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "unexpected.bin").write_bytes(b"unexpected")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_export_is_deterministic_and_cli_is_repository_relative(self):
        from tools.export_battle_presentation_glyphs import export_artifact

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "artifact"
            second = export_artifact(ROOT, output)
            self.assertEqual(self.manifest, second)
            self.assertEqual(directory_hashes(self.output), directory_hashes(output))

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "artifact"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/export_battle_presentation_glyphs.py",
                    "--root",
                    ".",
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(directory_hashes(self.output), directory_hashes(output))

    def test_failed_publish_restores_the_previous_complete_artifact(self):
        from tools import export_battle_presentation_glyphs as exporter

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "artifact"
            output.mkdir()
            sentinel = output / "previous-complete-artifact.txt"
            sentinel.write_text("keep me", encoding="utf-8")
            real_replace = exporter.os.replace

            def fail_new_publish(source, destination):
                source = Path(source)
                destination = Path(destination)
                if (
                    destination.resolve() == output.resolve()
                    and source.name.startswith(".artifact.")
                ):
                    raise OSError("injected publish failure")
                return real_replace(source, destination)

            with patch.object(exporter.os, "replace", side_effect=fail_new_publish):
                with self.assertRaisesRegex(OSError, "injected publish failure"):
                    exporter.export_artifact(ROOT, output)

            self.assertEqual("keep me", sentinel.read_text(encoding="utf-8"))
            self.assertEqual(
                ["artifact"],
                sorted(path.name for path in output.parent.iterdir()),
            )


if __name__ == "__main__":
    unittest.main()
