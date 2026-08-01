from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class MapResourceRelocationAuditTests(unittest.TestCase):
    @staticmethod
    def _resign(artifact: Path, payload: dict) -> None:
        payload_path = artifact / "relocation-audit.json"
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        promotion_path = artifact / "manifest.json"
        promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
        promotion["payload_sha256"] = digest
        promotion["files"]["relocation-audit.json"] = digest
        promotion_path.write_text(
            json.dumps(promotion, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_full_relocation_and_independent_verification(self):
        from tools.export_map_resource_relocation_audit import export_audit
        from tools.verify_map_resource_relocation_audit import verify_audit

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "map-relocation"
            payload = export_audit(ROOT, artifact)
            verification = verify_audit(ROOT, artifact)
            cli = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "tools"
                        / "verify_map_resource_relocation_audit.py"
                    ),
                    "--root",
                    str(ROOT),
                    "--artifact",
                    str(artifact),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            promotion = json.loads(
                (artifact / "manifest.json").read_text(encoding="utf-8")
            )

            tampered = json.loads(
                (artifact / "relocation-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            tampered["summary"]["logical_reference_count"] -= 1
            self._resign(artifact, tampered)
            tampered_verification = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(166, summary["content_resource_count"])
        self.assertEqual(217, summary["physical_source_count"])
        self.assertEqual(249, summary["logical_reference_count"])
        self.assertEqual(
            {
                "alternate_layout": 12,
                "bg_palette": 15,
                "collision_grid": 35,
                "metatile_definitions": 35,
                "primary_layout": 35,
                "tile_graphics": 34,
            },
            summary["resource_type_counts"],
        )
        self.assertEqual(0, summary["unexpected_pointer_count"])
        self.assertEqual(0x980000, summary["allocation_start"])
        self.assertEqual(0xA80000, summary["region_end"])
        self.assertEqual(0x9DE03E, summary["allocation_end"])
        self.assertGreater(summary["remaining_bytes"], 0)
        self.assertEqual([], verification["errors"])
        self.assertEqual(166, verification["verified_resources"])
        self.assertEqual(249, verification["verified_pointers"])
        self.assertEqual(
            payload["output_rom_sha256"],
            verification["rebuilt_output_rom_sha256"],
        )
        self.assertEqual(0, cli.returncode, cli.stderr)
        self.assertEqual([], json.loads(cli.stdout)["errors"])
        self.assertEqual("git-artifact-promotion-v1", promotion["schema"])
        self.assertEqual("accepted", promotion["artifact_status"])
        self.assertTrue(tampered_verification["errors"])

    def test_resigned_scope_overclaim_is_rejected(self):
        from tools.export_map_resource_relocation_audit import export_audit
        from tools.verify_map_resource_relocation_audit import verify_audit

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "map-relocation"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["scope"]["not_proved"] = "Everything is proved."
            self._resign(artifact, payload)
            promotion_path = artifact / "manifest.json"
            promotion = json.loads(
                promotion_path.read_text(encoding="utf-8")
            )
            promotion["scope"] = payload["scope"]
            promotion_path.write_text(
                json.dumps(promotion, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            verification = verify_audit(ROOT, artifact)

        self.assertTrue(verification["errors"])

    def test_full_tile_and_map_relocations_share_one_safety_gate(self):
        from tools.build_mod import apply_patch
        from tools.export_map_resource_relocation_audit import (
            export_audit as export_map,
        )
        from tools.export_tile_asset_resource_relocation_audit import (
            export_audit as export_tiles,
        )
        from tools.image_resource_regions import ImageResourceRegions
        from tools.import_map_resource_relocations import (
            resolve_map_resource_relocation_patches,
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
            map_artifact = temp / "maps"
            export_tiles(ROOT, tile_artifact)
            export_map(ROOT, map_artifact)
            tile_patches = resolve_tile_asset_resource_patches(
                ROOT,
                tile_artifact / "full-relocation-spec.json",
                rom=base,
                layout=layout,
                regions=regions,
            )
            map_patches = resolve_map_resource_relocation_patches(
                ROOT,
                map_artifact / "full-relocation-spec.json",
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
                for patch in (*tile_patches, *map_patches)
            ]

        self.assertEqual(1447, len(applied))
        self.assertEqual(
            489,
            sum(row["patch_class"] == "allocation" for row in applied),
        )
        self.assertEqual(
            958,
            sum(row["patch_class"] == "game_effective" for row in applied),
        )
        self.assertEqual(
            {"tile-assets", "map-resources"},
            {
                row["allocation_region"]
                for row in applied
                if row["patch_class"] == "allocation"
            },
        )


if __name__ == "__main__":
    unittest.main()
