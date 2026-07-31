import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ResidualWramDerivedTilemapRelocationAuditTests(unittest.TestCase):
    def test_exporter_starts_in_clean_subprocess(self):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "tools/export_residual_wram_derived_tilemap_relocation_audit.py",
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_verifier_is_independent(self):
        source = (
            ROOT
            / "tools/verify_residual_wram_derived_tilemap_relocation_audit.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.import_residual_wram_derived_tilemap_relocations",
            source,
        )
        self.assertNotIn(
            "import tools.import_residual_wram_derived_tilemap_relocations",
            source,
        )
        self.assertNotIn(
            "from tools.export_residual_wram_derived_tilemap_relocation_audit",
            source,
        )

    def test_full_batch_export_and_independent_verification(self):
        from tools.export_residual_wram_derived_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_wram_derived_tilemap_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            payload = export_audit(ROOT, artifact)
            report = verify_audit(ROOT, artifact)
        self.assertEqual(
            {
                "source_count": 4,
                "source_pointer_reference_count": 4,
                "decoded_size": 1664,
                "entry_count": 832,
                "allocation_count": 4,
                "pointer_patch_count": 4,
                "applied_patch_count": 8,
                "allocation_start": 0xBC1400,
                "allocation_end": 0xBC165B,
                "region_end": 0xBC1C00,
                "stored_payload_bytes": 597,
                "allocation_span": 603,
                "remaining_bytes": 1445,
                "literal_lz77_worst_case_bytes_with_alignment": 1888,
            },
            payload["summary"],
        )
        self.assertEqual([], report["errors"])
        self.assertEqual(4, report["verified_sources"])
        self.assertEqual(4, payload["capability_fixture"]["changed_entries"])
        self.assertEqual(
            payload["output_rom_sha256"],
            report["rebuilt_output_rom_sha256"],
        )

    def test_promoted_artifact_passes_and_rehashed_tamper_fails(self):
        from tools.verify_residual_wram_derived_tilemap_relocation_audit import (
            verify_audit,
        )

        promoted = (
            ROOT / "artifacts/residual-wram-derived-tilemap-relocation-v1"
        )
        report = verify_audit(ROOT, promoted)
        self.assertEqual([], report["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(promoted, artifact)
            payload_path = artifact / "relocation-audit.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["summary"]["entry_count"] = 831
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][payload_path.name] = digest
            manifest["payload_sha256"] = digest
            manifest["summary"] = payload["summary"]
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])


if __name__ == "__main__":
    unittest.main()
