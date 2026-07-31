from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GenericSpriteBundleRelocationAuditTests(unittest.TestCase):
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

    def test_exporter_starts_in_a_clean_subprocess(self):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "tools/export_generic_sprite_bundle_relocation_audit.py",
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
            ROOT / "tools/verify_generic_sprite_bundle_relocation_audit.py"
        ).read_text()
        self.assertNotIn(
            "from tools.import_generic_sprite_bundle_relocations",
            source,
        )
        self.assertNotIn(
            "from tools.export_generic_sprite_bundle_relocation_audit",
            source,
        )

    def test_full_relocation_and_independent_verification(self):
        from tools.export_generic_sprite_bundle_relocation_audit import (
            export_audit,
        )
        from tools.verify_generic_sprite_bundle_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "generic-sprite"
            payload = export_audit(ROOT, artifact)
            verified = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(43, summary["entry_count"])
        self.assertEqual(45, summary["component_count"])
        self.assertEqual(49, summary["graphics_tile_count"])
        self.assertEqual(97, summary["maximum_safe_graphics_tiles"])
        self.assertEqual(174, summary["source_pointer_reference_count"])
        self.assertEqual(45, summary["allocation_count"])
        self.assertEqual(88, summary["pointer_patch_count"])
        self.assertEqual(43, summary["tile_base_patch_count"])
        self.assertEqual(176, summary["applied_patch_count"])
        self.assertEqual(0xB90000, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0xBA0000)
        self.assertEqual(0xBA0000, summary["region_end"])
        self.assertEqual([], verified["errors"])
        self.assertEqual(43, verified["verified_entries"])
        self.assertEqual(174, verified["verified_source_pointers"])
        self.assertEqual(
            97,
            payload["capability_fixture"]["graphics_tile_count"],
        )
        self.assertEqual(
            46,
            payload["capability_fixture"]["component_count"],
        )
        self.assertEqual(97, verified["verified_fixture_tiles"])
        self.assertEqual(46, verified["verified_fixture_components"])
        self.assertEqual(
            payload["capability_fixture"]["output_rom_sha256"],
            verified["capability_fixture_output_rom_sha256"],
        )
        self.assertEqual(
            payload["output_rom_sha256"],
            verified["rebuilt_output_rom_sha256"],
        )

    def test_resigned_denominator_spec_and_extra_file_are_rejected(self):
        from tools.export_generic_sprite_bundle_relocation_audit import (
            export_audit,
        )
        from tools.verify_generic_sprite_bundle_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "generic-sprite"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            payload["summary"]["entry_count"] -= 1
            self._resign(artifact, payload)
            denominator = verify_audit(ROOT, artifact)

            export_audit(ROOT, artifact)
            spec_path = artifact / "full-relocation-spec.json"
            spec = json.loads(spec_path.read_text())
            spec["entries"][0]["tile_base_offset"] = 1
            spec_path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
            )
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"]["full-relocation-spec.json"] = hashlib.sha256(
                spec_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
            )
            spec_result = verify_audit(ROOT, artifact)

            export_audit(ROOT, artifact)
            (artifact / "unexpected.bin").write_bytes(b"unexpected")
            extra = verify_audit(ROOT, artifact)

        self.assertTrue(denominator["errors"])
        self.assertTrue(spec_result["errors"])
        self.assertTrue(extra["errors"])

    def test_resigned_base_layout_and_catalog_claims_are_rejected(self):
        from tools.export_generic_sprite_bundle_relocation_audit import (
            export_audit,
        )
        from tools.verify_generic_sprite_bundle_relocation_audit import (
            verify_audit,
        )

        results = []
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "generic-sprite"
            for mutate in (
                lambda payload: payload["base_rom"].update({"size": 1}),
                lambda payload: payload["layout"].update(
                    {"target_rom_size": 1}
                ),
                lambda payload: payload["catalogs"]["static"].update(
                    {"sha256": "0" * 64}
                ),
            ):
                export_audit(ROOT, artifact)
                payload = json.loads(
                    (artifact / "relocation-audit.json").read_text()
                )
                mutate(payload)
                self._resign(artifact, payload)
                results.append(verify_audit(ROOT, artifact))

        self.assertTrue(all(result["errors"] for result in results), results)


if __name__ == "__main__":
    unittest.main()
