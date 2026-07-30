from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MenuPortraitRelocationAuditTests(unittest.TestCase):
    def test_independent_codec_dependency_is_hash_bound(self):
        from tools.export_menu_portrait_relocation_audit import (
            IMPLEMENTATION_PATHS as EXPORT_IMPLEMENTATION_PATHS,
        )
        from tools.verify_menu_portrait_relocation_audit import (
            IMPLEMENTATION_PATHS as VERIFY_IMPLEMENTATION_PATHS,
        )

        for dependency in (
            "tools/verify_menu_portrait_writeback_audit.py",
            "tools/gba_image_export.py",
            "tools/extract_tileset.py",
            "tools/export_menu_portraits.py",
        ):
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, EXPORT_IMPLEMENTATION_PATHS)
                self.assertIn(dependency, VERIFY_IMPLEMENTATION_PATHS)

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
        from tools.export_menu_portrait_relocation_audit import export_audit
        from tools.verify_menu_portrait_relocation_audit import verify_audit

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "menu-portraits"
            payload = export_audit(ROOT, artifact)
            verification = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(311, summary["logical_portrait_count"])
        self.assertEqual(74, summary["logical_pair_count"])
        self.assertEqual(140, summary["physical_payload_count"])
        self.assertEqual(622, summary["logical_pointer_count"])
        self.assertEqual(0, summary["unexpected_pointer_count"])
        self.assertEqual(0xA80000, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0xB00000)
        self.assertEqual(0xB00000, summary["region_end"])
        self.assertGreater(summary["remaining_bytes"], 0)
        self.assertEqual([], verification["errors"])
        self.assertEqual(140, verification["verified_payloads"])
        self.assertEqual(622, verification["verified_pointers"])
        self.assertEqual(
            payload["output_rom_sha256"],
            verification["rebuilt_output_rom_sha256"],
        )

    def test_resigned_summary_and_scope_overclaims_are_rejected(self):
        from tools.export_menu_portrait_relocation_audit import export_audit
        from tools.verify_menu_portrait_relocation_audit import verify_audit

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "menu-portraits"
            export_audit(ROOT, artifact)
            payload = json.loads(
                (artifact / "relocation-audit.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["summary"]["logical_pointer_count"] -= 1
            self._resign(artifact, payload)
            summary_verification = verify_audit(ROOT, artifact)

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
            scope_verification = verify_audit(ROOT, artifact)

        self.assertTrue(summary_verification["errors"])
        self.assertTrue(scope_verification["errors"])


if __name__ == "__main__":
    unittest.main()
