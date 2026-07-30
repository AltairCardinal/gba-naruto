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


class TileAssetResourceRelocationAuditTests(unittest.TestCase):
    @staticmethod
    def _resign_payload(artifact: Path, payload: dict) -> None:
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

    def test_all_resources_fit_and_independent_verifier_rebuilds_output(self):
        from tools.export_tile_asset_resource_relocation_audit import (
            export_audit,
        )
        from tools.verify_tile_asset_resource_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "tile-assets"
            payload = export_audit(ROOT, artifact)
            verification = verify_audit(ROOT, artifact)
            cli_verification = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "tools"
                        / "verify_tile_asset_resource_relocation_audit.py"
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
            promotion_path = artifact / "manifest.json"
            payload_path = artifact / "relocation-audit.json"
            spec_path = artifact / "full-relocation-spec.json"
            promotion = json.loads(promotion_path.read_text(encoding="utf-8"))

            tampered = json.loads(payload_path.read_text(encoding="utf-8"))
            tampered["summary"]["logical_pointer_count"] -= 1
            payload_path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            promotion["payload_sha256"] = digest
            promotion["files"]["relocation-audit.json"] = digest
            promotion_path.write_text(
                json.dumps(promotion, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tampered_verification = verify_audit(ROOT, artifact)

            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["edits"][0]["target_pointer_offsets"] = [
                spec["edits"][0]["expected_pointer_offsets"][0]
            ]
            spec_path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            payload["authoring_spec"]["sha256"] = hashlib.sha256(
                spec_path.read_bytes()
            ).hexdigest()
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            promotion["files"]["full-relocation-spec.json"] = hashlib.sha256(
                spec_path.read_bytes()
            ).hexdigest()
            digest = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            promotion["payload_sha256"] = digest
            promotion["files"]["relocation-audit.json"] = digest
            promotion_path.write_text(
                json.dumps(promotion, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            semantic_tampered_verification = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(323, summary["resource_count"])
        self.assertEqual(709, summary["logical_pointer_count"])
        self.assertEqual(
            {"graphics": 107, "tilemap": 108, "palette": 108},
            summary["resource_type_counts"],
        )
        self.assertEqual(236, summary["complete_layer_count"])
        self.assertEqual(1, summary["partial_layer_count"])
        self.assertEqual(0x800000, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0x980000)
        self.assertEqual(0x980000, summary["region_end"])
        self.assertGreater(summary["remaining_bytes"], 0)
        self.assertEqual(0, summary["unexpected_pointer_count"])
        self.assertEqual("git-artifact-promotion-v1", promotion["schema"])
        self.assertEqual("accepted", promotion["artifact_status"])
        self.assertEqual([], verification["errors"])
        self.assertEqual(0, cli_verification.returncode, cli_verification.stderr)
        self.assertEqual(
            [],
            json.loads(cli_verification.stdout)["errors"],
        )
        self.assertEqual(323, verification["verified_resources"])
        self.assertEqual(709, verification["verified_pointers"])
        self.assertEqual(
            payload["output_rom_sha256"],
            verification["rebuilt_output_rom_sha256"],
        )
        self.assertTrue(tampered_verification["errors"])
        self.assertTrue(semantic_tampered_verification["errors"])

    def test_resigned_scope_overclaim_is_rejected(self):
        from tools.export_tile_asset_resource_relocation_audit import (
            export_audit,
        )
        from tools.verify_tile_asset_resource_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "tile-assets"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["scope"]["not_proved"] = "Everything is proved."
            self._resign_payload(artifact, payload)
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

    def test_verifier_rejects_missing_implementation_hash_and_invalid_layout(self):
        from tools.export_tile_asset_resource_relocation_audit import (
            export_audit,
        )
        from tools.verify_tile_asset_resource_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            clean = temp / "clean"
            export_audit(ROOT, clean)

            missing_hash = temp / "missing-hash"
            shutil.copytree(clean, missing_hash)
            payload = json.loads(
                (missing_hash / "relocation-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["implementation"].pop("tools/build_mod.py")
            self._resign_payload(missing_hash, payload)
            missing_hash_verification = verify_audit(ROOT, missing_hash)

            invalid_layout = temp / "invalid-layout"
            shutil.copytree(clean, invalid_layout)
            root = temp / "root"
            for relative in (
                "rom/base.gba",
                "sequel/rom-layout.json",
                "sequel/image-resource-regions.json",
                "artifacts/tile-assets-bg-v2/manifest.json",
                "tools/image_resource_regions.py",
                "tools/import_tile_asset_resources.py",
                "tools/rom_layout.py",
                "tools/patch_safety.py",
                "tools/build_mod.py",
            ):
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            layout_path = root / "sequel/rom-layout.json"
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
            next(
                row
                for row in layout["partitions"]
                if row["id"] == "sequel-audio-text-config"
            )["start"] = "0xB00000"
            layout_path.write_text(
                json.dumps(layout, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            payload = json.loads(
                (invalid_layout / "relocation-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["layout"]["sha256"] = hashlib.sha256(
                layout_path.read_bytes()
            ).hexdigest()
            self._resign_payload(invalid_layout, payload)
            invalid_layout_verification = verify_audit(root, invalid_layout)

        self.assertTrue(missing_hash_verification["errors"])
        self.assertTrue(invalid_layout_verification["errors"])


if __name__ == "__main__":
    unittest.main()
