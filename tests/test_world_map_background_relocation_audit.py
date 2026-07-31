from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorldMapBackgroundRelocationAuditTests(unittest.TestCase):
    @staticmethod
    def _resign(artifact: Path, payload: dict) -> None:
        payload_path = artifact / "relocation-audit.json"
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["payload_sha256"] = digest
        manifest["files"]["relocation-audit.json"] = digest
        manifest["summary"] = payload["summary"]
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_exporter_starts_in_a_clean_subprocess(self):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "tools/export_world_map_background_relocation_audit.py",
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_verifier_is_independent_of_importer_and_exporter(self):
        source = (
            ROOT / "tools/verify_world_map_background_relocation_audit.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.import_world_map_background_relocations",
            source,
        )
        self.assertNotIn(
            "from tools.export_world_map_background_relocation_audit",
            source,
        )

    def test_full_relocation_and_independent_verification(self):
        from tools.export_world_map_background_relocation_audit import (
            export_audit,
        )
        from tools.verify_world_map_background_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "world-map"
            payload = export_audit(ROOT, artifact)
            verification = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(3, summary["page_count"])
        self.assertEqual(7, summary["content_resource_count"])
        self.assertEqual(9, summary["physical_payload_count"])
        self.assertEqual(9, summary["logical_pointer_count"])
        self.assertEqual(0, summary["unexpected_pointer_count"])
        self.assertEqual(0xB71000, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0xB90000)
        self.assertEqual(0xB90000, summary["region_end"])
        self.assertGreater(summary["remaining_bytes"], 0)
        self.assertEqual([], verification["errors"])
        self.assertEqual(7, verification["verified_payloads"])
        self.assertEqual(9, verification["verified_pointers"])
        self.assertEqual(
            payload["output_rom_sha256"],
            verification["rebuilt_output_rom_sha256"],
        )

    def test_resigned_denominator_spec_and_extra_file_are_rejected(self):
        from tools.export_world_map_background_relocation_audit import (
            export_audit,
        )
        from tools.verify_world_map_background_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "world-map"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["summary"]["logical_pointer_count"] -= 1
            self._resign(artifact, payload)
            denominator = verify_audit(ROOT, artifact)

            export_audit(ROOT, artifact)
            spec_path = artifact / "full-relocation-spec.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["edits"][0]["expected"]["pointer_offsets"][0] += 4
            spec_path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["full-relocation-spec.json"] = hashlib.sha256(
                spec_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            spec_result = verify_audit(ROOT, artifact)

            export_audit(ROOT, artifact)
            (artifact / "unexpected.bin").write_bytes(b"unexpected")
            extra = verify_audit(ROOT, artifact)

        self.assertTrue(denominator["errors"])
        self.assertTrue(spec_result["errors"])
        self.assertTrue(extra["errors"])

    def test_committed_artifact_matches_fresh_export(self):
        from tools.export_world_map_background_relocation_audit import (
            export_audit,
        )

        committed = ROOT / "artifacts/world-map-background-relocation-v1"
        with tempfile.TemporaryDirectory() as temp_dir:
            fresh = Path(temp_dir) / "artifact"
            export_audit(ROOT, fresh)
            expected = {
                path.relative_to(fresh).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in fresh.rglob("*")
                if path.is_file()
            }
        actual = {
            path.relative_to(committed).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in committed.rglob("*")
            if path.is_file()
        }
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
