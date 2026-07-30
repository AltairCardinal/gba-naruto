from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class StoryVisualResourceRelocationAuditTests(unittest.TestCase):
    def test_export_and_independent_verifier_close_full_denominator(self):
        from tools.export_story_visual_resource_relocation_audit import (
            IMPLEMENTATION_PATHS,
            export_audit,
        )
        from tools.verify_story_visual_resource_relocation_audit import (
            verify_audit,
        )

        self.assertIn(
            "tools/import_story_visual_resource_relocations.py",
            IMPLEMENTATION_PATHS,
        )
        self.assertIn(
            "tools/verify_story_visual_resource_relocation_audit.py",
            IMPLEMENTATION_PATHS,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "artifact"
            payload = export_audit(ROOT, artifact)
            report = verify_audit(ROOT, artifact)

        self.assertEqual([], report["errors"])
        self.assertEqual(49, report["verified_payloads"])
        self.assertEqual(72, report["verified_pointers"])
        self.assertEqual(
            {
                "layer_count": 24,
                "content_resource_count": 49,
                "physical_payload_count": 72,
                "logical_pointer_count": 72,
                "unexpected_pointer_count": 0,
                "allocation_count": 49,
                "pointer_patch_count": 72,
                "allocation_start": 0xB50000,
                "allocation_end": payload["summary"]["allocation_end"],
                "region_end": 0xB71000,
                "stored_payload_bytes": payload["summary"][
                    "stored_payload_bytes"
                ],
                "allocation_span": payload["summary"]["allocation_span"],
                "remaining_bytes": payload["summary"]["remaining_bytes"],
                "applied_patch_count": 121,
            },
            payload["summary"],
        )
        self.assertLessEqual(payload["summary"]["allocation_end"], 0xB71000)
        self.assertEqual(49, len(payload["resources"]))
        self.assertEqual(
            {"graphics": 24, "palette": 1, "tilemap": 24},
            {
                role: sum(
                    row["resource_type"] == role
                    for row in payload["resources"]
                )
                for role in ("graphics", "palette", "tilemap")
            },
        )

    def test_verifier_rejects_payload_tampering(self):
        from tools.export_story_visual_resource_relocation_audit import (
            export_audit,
        )
        from tools.verify_story_visual_resource_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "artifact"
            export_audit(ROOT, artifact)
            payload_path = artifact / "relocation-audit.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["summary"]["logical_pointer_count"] = 71
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            manifest["payload_sha256"] = digest
            manifest["files"]["relocation-audit.json"] = digest
            manifest["summary"] = payload["summary"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            report = verify_audit(ROOT, artifact)

        self.assertTrue(report["errors"])

    def test_verifier_rejects_current_catalog_hash_mismatch(self):
        from tools import verify_story_visual_resource_relocation_audit as verifier
        from tools.export_story_visual_resource_relocation_audit import (
            export_audit,
        )

        catalog = (
            ROOT / "artifacts/story-visual-layers-v1/manifest.json"
        ).resolve()
        read_bytes = Path.read_bytes

        def tampered_catalog(path):
            if path.resolve() == catalog:
                return b"tampered story visual catalog"
            return read_bytes(path)

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "artifact"
            export_audit(ROOT, artifact)
            with mock.patch.object(
                Path,
                "read_bytes",
                autospec=True,
                side_effect=tampered_catalog,
            ):
                report = verifier.verify_audit(ROOT, artifact)

        self.assertTrue(report["errors"])

    def test_exporter_starts_in_isolated_python_without_pythonpath(self):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "tools/export_story_visual_resource_relocation_audit.py",
                "--help",
            ],
            cwd=ROOT,
            env={},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_full_story_and_linked_tile_assets_share_one_safety_gate(self):
        from tools.build_mod import apply_patch
        from tools.export_story_visual_resource_relocation_audit import (
            export_audit as export_story,
        )
        from tools.export_tile_asset_resource_relocation_audit import (
            export_audit as export_tiles,
        )
        from tools.image_resource_regions import ImageResourceRegions
        from tools.import_story_visual_resource_relocations import (
            resolve_story_visual_resource_relocation_patches,
        )
        from tools.import_tile_asset_resources import (
            resolve_tile_asset_resource_patches,
        )
        from tools.patch_safety import PatchSafetyGate
        from tools.rom_layout import RomLayout

        base = (ROOT / "rom/base.gba").read_bytes()
        layout = RomLayout.from_path(ROOT / "sequel/rom-layout.json", base)
        regions = ImageResourceRegions.from_path(
            ROOT / "sequel/image-resource-regions.json",
            layout,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            tile_artifact = temp / "tiles"
            story_artifact = temp / "story"
            export_tiles(ROOT, tile_artifact)
            export_story(ROOT, story_artifact)
            tile_patches = resolve_tile_asset_resource_patches(
                ROOT,
                tile_artifact / "full-relocation-spec.json",
                rom=base,
                layout=layout,
                regions=regions,
            )
            story_patches = resolve_story_visual_resource_relocation_patches(
                ROOT,
                story_artifact / "full-relocation-spec.json",
                rom=base,
                layout=layout,
                regions=regions,
            )
            output = bytearray(layout.expanded_base())
            gate = PatchSafetyGate(
                base,
                layout=layout,
                image_regions=regions,
            )
            applied = [
                apply_patch(output, patch, gate=gate)
                for patch in (*tile_patches, *story_patches)
            ]

        self.assertEqual(1153, len(applied))
        self.assertEqual(
            {"tile-assets", "story-visual-layers"},
            {
                row["allocation_region"]
                for row in applied
                if row["patch_class"] == "allocation"
            },
        )
        for layer_id in range(24):
            config_id = int.from_bytes(
                output[
                    0x54229C + layer_id * 0x10 + 0x0C :
                    0x54229C + layer_id * 0x10 + 0x10
                ],
                "little",
            )
            self.assertLess(config_id, 79)
            descriptor = 0x5A320C + config_id * 0x44
            self.assertNotEqual(
                base[descriptor : descriptor + 0x44],
                output[descriptor : descriptor + 0x44],
            )


if __name__ == "__main__":
    unittest.main()
