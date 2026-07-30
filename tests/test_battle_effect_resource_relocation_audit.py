from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleEffectResourceRelocationAuditTests(unittest.TestCase):
    def test_exporter_starts_in_a_clean_subprocess(self):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "tools/export_battle_effect_resource_relocation_audit.py",
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_all_direct_implementation_dependencies_are_hash_bound(self):
        from tools.export_battle_effect_resource_relocation_audit import (
            IMPLEMENTATION_PATHS as EXPORT_PATHS,
        )
        from tools.verify_battle_effect_resource_relocation_audit import (
            IMPLEMENTATION_PATHS as VERIFY_PATHS,
        )

        for dependency in (
            "tools/import_battle_effect_resource_relocations.py",
            "tools/import_battle_effect_resources.py",
            "tools/gba_image_export.py",
            "tools/extract_tileset.py",
            "tools/verify_battle_effect_resource_writeback_audit.py",
            "tools/image_resource_regions.py",
            "tools/rom_layout.py",
            "tools/patch_safety.py",
            "tools/build_mod.py",
        ):
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, EXPORT_PATHS)
                self.assertIn(dependency, VERIFY_PATHS)

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
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_full_relocation_and_independent_verification(self):
        from tools.export_battle_effect_resource_relocation_audit import (
            export_audit,
        )
        from tools.verify_battle_effect_resource_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "battle-effects"
            payload = export_audit(ROOT, artifact)
            verification = verify_audit(ROOT, artifact)

        summary = payload["summary"]
        self.assertEqual(18, summary["group_count"])
        self.assertEqual(34, summary["content_resource_count"])
        self.assertEqual(35, summary["physical_payload_count"])
        self.assertEqual(36, summary["logical_pointer_count"])
        self.assertEqual(0, summary["unexpected_pointer_count"])
        self.assertEqual(0xB40000, summary["allocation_start"])
        self.assertLessEqual(summary["allocation_end"], 0xB50000)
        self.assertEqual(0xB50000, summary["region_end"])
        self.assertGreater(summary["remaining_bytes"], 0)
        self.assertEqual([], verification["errors"])
        self.assertEqual(34, verification["verified_payloads"])
        self.assertEqual(36, verification["verified_pointers"])
        self.assertEqual(
            payload["output_rom_sha256"],
            verification["rebuilt_output_rom_sha256"],
        )

    def test_resigned_overclaims_command_drift_and_extra_file_are_rejected(self):
        from tools.export_battle_effect_resource_relocation_audit import (
            export_audit,
        )
        from tools.verify_battle_effect_resource_relocation_audit import (
            verify_audit,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "battle-effects"
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
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            manifest["scope"] = payload["scope"]
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            scope_verification = verify_audit(ROOT, artifact)

            export_audit(ROOT, artifact)
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            manifest["verifier"]["command"][-1] = "artifacts/wrong"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            command_verification = verify_audit(ROOT, artifact)

            export_audit(ROOT, artifact)
            nested = artifact / "unexpected"
            nested.mkdir()
            (nested / "extra.bin").write_bytes(b"unexpected")
            extra_file_verification = verify_audit(ROOT, artifact)

        self.assertTrue(summary_verification["errors"])
        self.assertTrue(scope_verification["errors"])
        self.assertTrue(command_verification["errors"])
        self.assertTrue(extra_file_verification["errors"])


if __name__ == "__main__":
    unittest.main()
