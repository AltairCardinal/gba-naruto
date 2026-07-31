from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CutsceneObjBundleRelocationAuditTests(unittest.TestCase):
    @staticmethod
    def _resign(artifact: Path, payload: dict) -> None:
        payload_path = artifact / "relocation-audit.json"
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        )
        digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["payload_sha256"] = digest
        manifest["files"]["relocation-audit.json"] = digest
        manifest["summary"] = payload["summary"]
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )

    @staticmethod
    def _resign_spec(artifact: Path, payload: dict, spec: dict) -> None:
        spec_path = artifact / "full-relocation-spec.json"
        spec_path.write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
        )
        digest = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        payload["authoring_spec"]["sha256"] = digest
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["full-relocation-spec.json"] = digest
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )
        CutsceneObjBundleRelocationAuditTests._resign(artifact, payload)

    def test_exporter_starts_in_a_clean_subprocess(self):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "tools/export_cutscene_obj_bundle_relocation_audit.py",
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_verifier_does_not_import_importer_or_exporter(self):
        source = (
            ROOT / "tools/verify_cutscene_obj_bundle_relocation_audit.py"
        ).read_text()
        self.assertNotIn(
            "from tools.import_cutscene_obj_bundle_relocations",
            source,
        )
        self.assertNotIn(
            "from tools.export_cutscene_obj_bundle_relocation_audit",
            source,
        )

    def test_full_relocation_and_independent_verification(self):
        from tools.export_cutscene_obj_bundle_relocation_audit import (
            export_audit,
        )
        from tools.verify_cutscene_obj_bundle_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "cutscene-obj"
            payload = export_audit(ROOT, artifact)
            verified = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(4, summary["resource_count"])
        self.assertEqual(10, summary["frame_count"])
        self.assertEqual(10, summary["component_count"])
        self.assertEqual(10, summary["animation_count"])
        self.assertEqual(10, summary["keyframe_count"])
        self.assertEqual(256, summary["maximum_safe_graphics_tiles"])
        self.assertEqual(36, summary["source_pointer_reference_count"])
        self.assertEqual(12, summary["allocation_count"])
        self.assertEqual(16, summary["pointer_patch_count"])
        self.assertEqual(28, summary["applied_patch_count"])
        self.assertEqual(0xBA0000, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0xBB0000)
        self.assertEqual(0xBB0000, summary["region_end"])
        self.assertEqual([], verified["errors"])
        self.assertEqual(4, verified["verified_resources"])
        self.assertEqual(36, verified["verified_source_pointers"])
        fixture = payload["capability_fixture"]
        self.assertEqual(256, fixture["graphics_tile_count"])
        self.assertEqual(11, fixture["component_count"])
        self.assertEqual(11, fixture["keyframe_count"])
        self.assertEqual(256, verified["verified_fixture_tiles"])
        self.assertEqual(11, verified["verified_fixture_components"])
        self.assertEqual(11, verified["verified_fixture_keyframes"])
        self.assertEqual(
            fixture["output_rom_sha256"],
            verified["capability_fixture_output_rom_sha256"],
        )
        self.assertEqual(
            payload["output_rom_sha256"],
            verified["rebuilt_output_rom_sha256"],
        )

    def test_resigned_denominator_spec_metadata_and_extra_file_are_rejected(self):
        from tools.export_cutscene_obj_bundle_relocation_audit import (
            export_audit,
        )
        from tools.verify_cutscene_obj_bundle_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "cutscene-obj"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            payload["summary"]["source_pointer_reference_count"] = 35
            self._resign(artifact, payload)
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "cutscene-obj"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            spec = json.loads(
                (artifact / "full-relocation-spec.json").read_text()
            )
            spec["resources"][0]["animations"][0]["keyframes"][0][
                "duration_ticks"
            ] = 2
            self._resign_spec(artifact, payload, spec)
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        for section, key in (
            ("base_rom", "sha256"),
            ("layout", "sha256"),
            ("region_registry", "sha256"),
            ("catalog", "sha256"),
        ):
            with tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "cutscene-obj"
                export_audit(ROOT, artifact)
                payload = json.loads(
                    (artifact / "relocation-audit.json").read_text()
                )
                payload[section][key] = "0" * 64
                self._resign(artifact, payload)
                self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "cutscene-obj"
            export_audit(ROOT, artifact)
            (artifact / "extra.bin").write_bytes(b"unexpected")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])


if __name__ == "__main__":
    unittest.main()
