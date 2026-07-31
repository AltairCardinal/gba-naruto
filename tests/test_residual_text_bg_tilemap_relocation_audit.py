from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ResidualTextBgTilemapRelocationAuditTests(unittest.TestCase):
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
                "tools/export_residual_text_bg_tilemap_relocation_audit.py",
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
            / "tools/verify_residual_text_bg_tilemap_relocation_audit.py"
        ).read_text()
        self.assertNotIn(
            "from tools.import_residual_text_bg_tilemap_relocations",
            source,
        )
        self.assertNotIn(
            "from tools.export_residual_text_bg_tilemap_relocation_audit",
            source,
        )

    def test_full_relocation_and_independent_verification(self):
        from tools.export_residual_text_bg_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_text_bg_tilemap_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemap"
            payload = export_audit(ROOT, artifact)
            spec = json.loads(
                (artifact / "full-relocation-spec.json").read_text()
            )
            verified = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(1, summary["source_count"])
        self.assertEqual(1, summary["source_pointer_reference_count"])
        self.assertEqual(1280, summary["decoded_size"])
        self.assertEqual(640, summary["entry_count"])
        self.assertEqual(1, summary["allocation_count"])
        self.assertEqual(1, summary["pointer_patch_count"])
        self.assertEqual(2, summary["applied_patch_count"])
        self.assertEqual(0xBC0400, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0xBC0C00)
        self.assertEqual(0xBC0C00, summary["region_end"])
        self.assertEqual(1, payload["capability_fixture"]["changed_entries"])
        self.assertEqual(
            {
                "path": (
                    "artifacts/"
                    "residual-text-bg-tilemap-resource-ownership-v1/"
                    "resource-ownership.json"
                ),
                "sha256": (
                    "95c4baf0febd70151d68c08d276bb694daa1f544035466f"
                    "9b078f73e538d8741"
                ),
                "verified_source_count": 1,
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
        self.assertEqual([], verified["errors"])
        self.assertEqual(1, verified["verified_sources"])
        self.assertEqual(1, verified["verified_source_pointers"])
        self.assertEqual(
            payload["output_rom_sha256"],
            verified["rebuilt_output_rom_sha256"],
        )

    def test_manifest_requires_implementation_hashes(self):
        from tools.export_residual_text_bg_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_text_bg_tilemap_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemap"
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

    def test_resigned_summary_spec_tilemap_and_extra_files_are_rejected(self):
        from tools.export_residual_text_bg_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_text_bg_tilemap_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemap"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            payload["summary"]["entry_count"] = 639
            self._resign_payload(artifact, payload)
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemap"
            export_audit(ROOT, artifact)
            spec_path = artifact / "full-relocation-spec.json"
            spec = json.loads(spec_path.read_text())
            spec["source_pointer"] = "0x0834936C"
            spec_path.write_text(json.dumps(spec, indent=2) + "\n")
            self._resign_file(artifact, "full-relocation-spec.json")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemap"
            export_audit(ROOT, artifact)
            path = artifact / "tilemap.bin"
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
            self._resign_file(artifact, "tilemap.bin")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemap"
            export_audit(ROOT, artifact)
            (artifact / "extra.bin").write_bytes(b"unexpected")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

    def test_nested_files_and_symlinks_are_rejected(self):
        from tools.export_residual_text_bg_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_text_bg_tilemap_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemap"
            export_audit(ROOT, artifact)
            nested = artifact / "build/experiments"
            nested.mkdir(parents=True)
            (nested / "leak.bin").write_bytes(b"unexpected")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "tilemap"
            export_audit(ROOT, artifact)
            (artifact / "linked.bin").symlink_to(artifact / "tilemap.bin")
            self.assertTrue(verify_audit(ROOT, artifact)["errors"])

    def test_resigned_overlapping_global_region_registry_is_rejected(self):
        from tools.export_residual_text_bg_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_text_bg_tilemap_relocation_audit import (
            IMPLEMENTATION_PATHS,
            INVENTORY_PATH,
            LAYOUT_PATH,
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            artifact = temporary_path / "tilemap"
            export_audit(ROOT, artifact)
            shadow_root = temporary_path / "shadow"
            for relative in (
                Path("rom/base.gba"),
                LAYOUT_PATH,
                INVENTORY_PATH,
                *(Path(value) for value in IMPLEMENTATION_PATHS),
            ):
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
            future["start"] = "0xBC0BFC"
            registry_path = shadow_root / "sequel/image-resource-regions.json"
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(json.dumps(registry, indent=2) + "\n")
            registry_hash = hashlib.sha256(
                registry_path.read_bytes()
            ).hexdigest()

            spec_path = artifact / "full-relocation-spec.json"
            spec = json.loads(spec_path.read_text())
            spec["region_registry_sha256"] = registry_hash
            spec_path.write_text(json.dumps(spec, indent=2) + "\n")
            spec_hash = hashlib.sha256(spec_path.read_bytes()).hexdigest()

            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            payload["region_registry"]["sha256"] = registry_hash
            payload["authoring_spec"]["sha256"] = spec_hash
            self._resign_payload(artifact, payload)
            self._resign_file(artifact, "full-relocation-spec.json")

            self.assertTrue(verify_audit(shadow_root, artifact)["errors"])

    def test_resigned_overlapping_global_rom_layout_is_rejected(self):
        from tools.export_residual_text_bg_tilemap_relocation_audit import (
            export_audit,
        )
        from tools.verify_residual_text_bg_tilemap_relocation_audit import (
            IMPLEMENTATION_PATHS,
            INVENTORY_PATH,
            LAYOUT_PATH,
            REGISTRY_PATH,
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            artifact = temporary_path / "tilemap"
            export_audit(ROOT, artifact)
            shadow_root = temporary_path / "shadow"
            for relative in (
                Path("rom/base.gba"),
                INVENTORY_PATH,
                REGISTRY_PATH,
                *(Path(value) for value in IMPLEMENTATION_PATHS),
            ):
                destination = shadow_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(ROOT / relative)

            layout = json.loads((ROOT / LAYOUT_PATH).read_text())
            parent = next(
                row
                for row in layout["partitions"]
                if row["id"] == "sequel-image-assets"
            )
            parent["alignment"] = 2
            layout["partitions"].append(
                {
                    "id": "resigned-overlap",
                    "owner": "attacker",
                    "origin": "expanded_ff",
                    "start": "0x800000",
                    "end": "0x801000",
                    "alignment": 4,
                }
            )
            layout_path = shadow_root / LAYOUT_PATH
            layout_path.parent.mkdir(parents=True, exist_ok=True)
            layout_path.write_text(json.dumps(layout, indent=2) + "\n")
            layout_hash = hashlib.sha256(layout_path.read_bytes()).hexdigest()

            payload = json.loads(
                (artifact / "relocation-audit.json").read_text()
            )
            payload["layout"]["sha256"] = layout_hash
            self._resign_payload(artifact, payload)

            self.assertTrue(verify_audit(shadow_root, artifact)["errors"])


if __name__ == "__main__":
    unittest.main()
