import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportBattleVisualCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_visual_catalog import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.manifest = export_artifact(ROOT, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_binds_all_visual_descriptors_to_same_index_messages(self):
        manifest = self.manifest
        self.assertEqual("battle-visual-catalog-v1", manifest["schema"])
        self.assertEqual(79, len(manifest["entries"]))
        self.assertEqual(
            list(range(79)),
            [entry["descriptor_id"] for entry in manifest["entries"]],
        )
        self.assertEqual(
            list(range(1, 80)),
            [entry["consumer_id"] for entry in manifest["entries"]],
        )
        self.assertEqual(
            list(range(79)),
            [entry["message"]["message_id"] for entry in manifest["entries"]],
        )
        self.assertEqual(
            "state.message_id = u8(input_id - 1); "
            "descriptor = 0x085A320C + state.message_id * 0x44; "
            "message = u32[0x085A2B08 + state.message_id * 4]",
            manifest["selection_chain"]["formula"],
        )

    def test_preserves_every_complete_layer_and_glyph_binding(self):
        entries = self.manifest["entries"]
        self.assertEqual(236, sum(len(entry["layers"]) for entry in entries))
        self.assertEqual(
            284,
            sum(len(entry["message"]["glyphs"]) for entry in entries),
        )
        self.assertEqual(
            10,
            sum(
                slot["skipped"]
                for entry in entries
                for slot in entry["message"]["binding_slots"]
            ),
        )
        self.assertEqual(
            [13, 31, 32, 46],
            [
                entry["descriptor_id"]
                for entry in entries
                if entry["descriptor_status"] == "sentinel"
            ],
        )
        for entry in entries:
            self.assertTrue((self.output / entry["preview"]["file"]).is_file())
            for layer in entry["layers"]:
                self.assertTrue(layer["source_file"].startswith(
                    "artifacts/tile-assets-bg-v2/"
                ))
                self.assertEqual(64, len(layer["sha256"]))
            for glyph in entry["message"]["glyphs"]:
                self.assertTrue(glyph["source_file"].startswith(
                    "artifacts/battle-presentation-glyphs-v1/"
                ))
                self.assertEqual(64, len(glyph["sha256"]))

    def test_scope_does_not_overclaim_dynamic_composition(self):
        self.assertEqual(
            {
                "all_descriptor_message_bindings_complete": True,
                "all_complete_static_layers_cataloged": True,
                "all_message_glyph_bindings_cataloged": True,
                "editor_preview_sheets_complete": True,
                "runtime_tick_timeline_complete": False,
                "screen_space_composition_complete": False,
                "message_character_decoding_complete": False,
                "natural_language_names_complete": False,
            },
            self.manifest["scope"],
        )

    def test_independent_verifier_accepts_export_and_rejects_tamper(self):
        from tools.verify_battle_visual_catalog import verify_artifact

        source = (
            ROOT / "tools" / "verify_battle_visual_catalog.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("export_battle_visual_catalog", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(79, report["entry_count"])
        self.assertEqual(236, report["layer_count"])
        self.assertEqual(284, report["glyph_binding_count"])
        self.assertEqual(10, report["skipped_binding_count"])

        for relative in (
            "manifest.json",
            self.manifest["entries"][0]["preview"]["file"],
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

    def test_independent_verifier_rejects_semantic_manifest_tampering(self):
        from tools.verify_battle_visual_catalog import verify_artifact

        mutations = {
            "source hash": lambda data: data["source_artifacts"]["tile_assets"].update(
                sha256="0" * 64
            ),
            "consumer slice": lambda data: data["selection_chain"]["code_slices"][
                0
            ].update(sha256="0" * 64),
            "index proof": lambda data: data["selection_chain"].update(
                same_zero_based_index_verified=False
            ),
            "message raw": lambda data: data["entries"][0]["message"].update(
                raw_hex="00"
            ),
            "binding raw": lambda data: data["entries"][0]["message"].update(
                binding_raw_hex="00"
            ),
            "preview claim": lambda data: data["entries"][0]["preview"].update(
                is_runtime_composite=True
            ),
            "scope": lambda data: data["scope"].update(
                runtime_tick_timeline_complete=True
            ),
            "sentinels": lambda data: data["summary"].update(
                sentinel_descriptor_ids=[]
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                tampered = Path(temporary) / "artifact"
                shutil.copytree(self.output, tampered)
                manifest_path = tampered / "manifest.json"
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(data)
                manifest_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                report = verify_artifact(ROOT, tampered)
                self.assertFalse(report["verified"], name)
                self.assertTrue(report["errors"], name)

    def test_export_is_deterministic_and_cli_is_repository_relative(self):
        from tools.export_battle_visual_catalog import export_artifact

        committed = ROOT / "artifacts/battle-visual-catalog-v1"
        self.assertEqual(
            directory_hashes(self.output),
            directory_hashes(committed),
        )

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
                    "tools/export_battle_visual_catalog.py",
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
            self.assertIn('"entry_count": 79', result.stdout)
            self.assertTrue((output / "manifest.json").is_file())

    def test_output_target_rejects_repository_and_unrelated_data(self):
        from tools.export_battle_visual_catalog import (
            export_artifact,
            validate_output_target,
        )

        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT)
        with self.assertRaises(ValueError):
            validate_output_target(ROOT, ROOT.parent)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            output.mkdir()
            (output / "unrelated.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_artifact(ROOT, output)
            self.assertEqual(
                "keep",
                (output / "unrelated.txt").read_text(encoding="utf-8"),
            )

    def test_failed_publish_restores_previous_complete_artifact(self):
        import tools.export_battle_visual_catalog as exporter

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            exporter.export_artifact(ROOT, output)
            before = directory_hashes(output)
            real_replace = exporter.os.replace
            calls = 0

            def fail_publish_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected publish failure")
                return real_replace(source, destination)

            with mock.patch.object(
                exporter.os,
                "replace",
                side_effect=fail_publish_replace,
            ):
                with self.assertRaises(OSError):
                    exporter.export_artifact(ROOT, output)
            self.assertEqual(before, directory_hashes(output))


if __name__ == "__main__":
    unittest.main()
