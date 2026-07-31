from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DirectImagePaletteRelocationAuditTests(unittest.TestCase):
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
                "tools/export_direct_image_palette_relocation_audit.py",
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
            ROOT / "tools/verify_direct_image_palette_relocation_audit.py"
        ).read_text()
        self.assertNotIn(
            "from tools.import_direct_image_palette_relocations",
            source,
        )
        self.assertNotIn(
            "from tools.export_direct_image_palette_relocation_audit",
            source,
        )

    def test_full_relocation_and_independent_verification(self):
        from tools.export_direct_image_palette_relocation_audit import (
            export_audit,
        )
        from tools.verify_direct_image_palette_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "direct-image-palettes"
            payload = export_audit(ROOT, artifact)
            verified = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(18, summary["logical_source_count"])
        self.assertEqual(17, summary["physical_resource_count"])
        self.assertEqual(29, summary["source_pointer_reference_count"])
        self.assertEqual(17, summary["allocation_count"])
        self.assertEqual(29, summary["pointer_patch_count"])
        self.assertEqual(46, summary["applied_patch_count"])
        self.assertEqual(0xBC0000, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0xBC0400)
        self.assertEqual(0xBC0400, summary["region_end"])
        self.assertEqual(17, payload["capability_fixture"]["changed_resources"])
        self.assertEqual(18, payload["capability_fixture"]["changed_logical_sources"])
        self.assertEqual([], verified["errors"])
        self.assertEqual(17, verified["verified_physical_resources"])
        self.assertEqual(18, verified["verified_logical_sources"])
        self.assertEqual(29, verified["verified_source_pointers"])
        self.assertEqual(
            payload["output_rom_sha256"],
            verified["rebuilt_output_rom_sha256"],
        )
        self.assertEqual(
            payload["capability_fixture"]["output_rom_sha256"],
            verified["capability_fixture_output_rom_sha256"],
        )

    def test_resigned_denominator_spec_raw_and_extra_files_are_rejected(self):
        from tools.export_direct_image_palette_relocation_audit import (
            export_audit,
        )
        from tools.verify_direct_image_palette_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "direct-image-palettes"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            payload["summary"]["source_pointer_reference_count"] = 28
            self._resign_payload(artifact, payload)
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "direct-image-palettes"
            export_audit(ROOT, artifact)
            spec_path = artifact / "full-relocation-spec.json"
            spec = json.loads(spec_path.read_text())
            spec["resources"].pop()
            spec_path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
            )
            self._resign_file(artifact, "full-relocation-spec.json")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "direct-image-palettes"
            export_audit(ROOT, artifact)
            raw_name = sorted(
                name
                for name in json.loads(
                    (artifact / "manifest.json").read_text()
                )["files"]
                if name.endswith(".bgr555.bin")
            )[0]
            raw_path = artifact / raw_name
            raw = bytearray(raw_path.read_bytes())
            raw[0] ^= 0xFF
            raw_path.write_bytes(raw)
            self._resign_file(artifact, raw_name)
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "direct-image-palettes"
            export_audit(ROOT, artifact)
            (artifact / "extra.bin").write_bytes(b"unexpected")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

    def test_resigned_overlapping_global_region_registry_is_rejected(self):
        from tools.export_direct_image_palette_relocation_audit import (
            export_audit,
        )
        from tools.verify_direct_image_palette_relocation_audit import (
            DIRECT_INVENTORY_PATH,
            GRAPHICS_CATALOG_PATH,
            IMPLEMENTATION_PATHS,
            LAYOUT_PATH,
            LZ_INVENTORY_PATH,
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            artifact = temporary_path / "direct-image-palettes"
            export_audit(ROOT, artifact)
            shadow_root = temporary_path / "shadow-root"
            required_paths = (
                Path("rom/base.gba"),
                LAYOUT_PATH,
                LZ_INVENTORY_PATH,
                GRAPHICS_CATALOG_PATH,
                DIRECT_INVENTORY_PATH,
                *(Path(value) for value in IMPLEMENTATION_PATHS),
            )
            for relative in required_paths:
                destination = shadow_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(ROOT / relative)

            registry = json.loads(
                (ROOT / "sequel/image-resource-regions.json").read_text()
            )
            future = next(
                row
                for row in registry["regions"]
                if row["id"] == "future-image-resources"
            )
            future["start"] = "0xBC0300"
            registry_path = shadow_root / "sequel/image-resource-regions.json"
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2) + "\n"
            )
            registry_sha256 = hashlib.sha256(
                registry_path.read_bytes()
            ).hexdigest()

            spec_path = artifact / "full-relocation-spec.json"
            spec = json.loads(spec_path.read_text())
            spec["region_registry_sha256"] = registry_sha256
            spec_path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
            )
            spec_sha256 = hashlib.sha256(spec_path.read_bytes()).hexdigest()

            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            payload["region_registry"]["sha256"] = registry_sha256
            payload["authoring_spec"]["sha256"] = spec_sha256
            self._resign_payload(artifact, payload)
            self._resign_file(artifact, "full-relocation-spec.json")

            self.assertTrue(verify_audit(shadow_root, artifact)["errors"])


if __name__ == "__main__":
    unittest.main()
