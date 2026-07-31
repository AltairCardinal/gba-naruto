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


class ResidualWramTilemapRelocationAuditTests(unittest.TestCase):
    @staticmethod
    def _resign_payload(artifact: Path, payload: dict) -> None:
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
    def _resign_file(artifact: Path, name: str) -> None:
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][name] = hashlib.sha256(
            (artifact / name).read_bytes()
        ).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )

    def test_exporter_starts_in_a_clean_subprocess(self):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "tools/export_residual_wram_tilemap_relocation_audit.py",
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_verifier_does_not_import_production_importer_or_exporter(self):
        source = (
            ROOT
            / "tools/verify_residual_wram_tilemap_relocation_audit.py"
        ).read_text()
        self.assertNotIn(
            "from tools.import_residual_wram_tilemap_relocations",
            source,
        )
        self.assertNotIn(
            "from tools.export_residual_wram_tilemap_relocation_audit",
            source,
        )

    def test_full_batch_relocation_and_independent_verification(self):
        from tools.export_residual_wram_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_wram_tilemap_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemaps"
            payload = export_audit(ROOT, artifact)
            spec = json.loads(
                (artifact / "full-relocation-spec.json").read_text()
            )
            verified = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(3, summary["source_count"])
        self.assertEqual(3, summary["source_pointer_reference_count"])
        self.assertEqual(1314, summary["decoded_size"])
        self.assertEqual(657, summary["entry_count"])
        self.assertEqual(3, summary["allocation_count"])
        self.assertEqual(3, summary["pointer_patch_count"])
        self.assertEqual(6, summary["applied_patch_count"])
        self.assertEqual(0xBC0C00, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0xBC1400)
        self.assertEqual(0xBC1400, summary["region_end"])
        self.assertEqual(3, payload["capability_fixture"]["changed_entries"])
        self.assertEqual(
            {
                "path": (
                    "artifacts/residual-wram-tilemap-resource-ownership-v1/"
                    "resource-ownership.json"
                ),
                "sha256": (
                    "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be"
                    "83a37aa90b5ced7"
                ),
                "verified_source_count": 3,
            },
            payload["resource_ownership"],
        )
        self.assertEqual(
            payload["resource_ownership"]["path"],
            spec["resource_ownership_artifact"],
        )
        self.assertEqual(
            payload["resource_ownership"]["sha256"],
            spec["resource_ownership_sha256"],
        )
        self.assertNotIn("ownership", payload["scope"]["not_proved"])
        self.assertEqual([], verified["errors"])
        self.assertEqual(3, verified["verified_sources"])
        self.assertEqual(3, verified["verified_source_pointers"])
        self.assertEqual(
            payload["output_rom_sha256"],
            verified["rebuilt_output_rom_sha256"],
        )

    def test_promoted_artifact_passes_independent_verifier(self):
        from tools.verify_residual_wram_tilemap_relocation_audit import (
            verify_audit,
        )

        report = verify_audit(
            ROOT,
            ROOT / "artifacts/residual-wram-tilemap-relocation-v1",
        )
        self.assertEqual([], report["errors"])
        self.assertEqual(3, report["verified_sources"])

    def test_manifest_requires_implementation_hashes(self):
        from tools.export_residual_wram_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_wram_tilemap_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemaps"
            payload = export_audit(ROOT, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(
                payload["implementation"],
                manifest["implementation"],
            )
            del manifest["implementation"]
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
            )
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

    def test_resigned_payload_spec_tilemap_and_extra_files_are_rejected(self):
        from tools.export_residual_wram_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_wram_tilemap_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemaps"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            payload["summary"]["entry_count"] = 656
            self._resign_payload(artifact, payload)
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemaps"
            export_audit(ROOT, artifact)
            spec_path = artifact / "full-relocation-spec.json"
            spec = json.loads(spec_path.read_text())
            spec["resources"][0]["source_pointer"] = "0x08349290"
            spec_path.write_text(json.dumps(spec, indent=2) + "\n")
            self._resign_file(artifact, "full-relocation-spec.json")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemaps"
            export_audit(ROOT, artifact)
            tilemap = artifact / "tilemap-0834928c.bin"
            raw = bytearray(tilemap.read_bytes())
            raw[0] ^= 1
            tilemap.write_bytes(raw)
            self._resign_file(artifact, tilemap.name)
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemaps"
            export_audit(ROOT, artifact)
            (artifact / "extra.bin").write_bytes(b"unexpected")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

    def test_resigned_region_overlap_and_implementation_drift_are_rejected(self):
        from tools.export_residual_wram_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_wram_tilemap_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemaps"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            payload["region_registry"]["start"] = 0xBC0BFC
            self._resign_payload(artifact, payload)
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemaps"
            export_audit(ROOT, artifact)
            shadow = Path(temporary) / "shadow"
            shutil.copytree(ROOT / "tools", shadow / "tools")
            for relative in (
                Path("rom/base.gba"),
                Path("sequel/rom-layout.json"),
                Path("sequel/image-resource-regions.json"),
                Path(
                    "artifacts/residual-wram-tilemap-abi-v1/"
                    "residual-wram-tilemap-abi.json"
                ),
            ):
                destination = shadow / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(ROOT / relative)
            importer = (
                shadow / "tools/import_residual_wram_tilemap_relocations.py"
            )
            importer.write_text(importer.read_text() + "\n# drift\n")
            self.assertTrue(verify_audit(shadow, artifact)["errors"])


if __name__ == "__main__":
    unittest.main()
