from __future__ import annotations

import hashlib
import importlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group15-natural-runtime-v1"


class Group15NaturalRuntimeVerifierTests(unittest.TestCase):
    def setUp(self):
        self.verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_natural_runtime"
        )

    def test_independent_verifier_accepts_production_artifact(self):
        result = self.verifier.verify_artifact(ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])
        self.assertEqual(result["action_id"], 64)
        self.assertEqual(result["sequence_id"], 17)
        self.assertEqual(result["group_id"], 15)
        self.assertEqual(result["phase_pending"], [0, 1, 0])

    def test_manifest_records_the_successful_independent_verifier(self):
        manifest = json.loads((ARTIFACT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest.get("verifier"),
            {
                "command": [
                    "python3",
                    "tools/verify_battle_effect_group15_natural_runtime.py",
                    "--artifact",
                    "artifacts/battle-effect-group15-natural-runtime-v1",
                ],
                "exit_code": 0,
            },
        )

    def test_rejects_resigned_action_scope_inflation(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["execution"]["action_id"] = 65
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = self.verifier.verify_artifact(artifact)
            self.assertFalse(result["verified"])
            self.assertTrue(any("action identity" in error for error in result["errors"]))

    def test_archive_member_denominator_is_fixed(self):
        payloads = self.verifier.read_safe_tar(ARTIFACT / "raw-runtime.tar")
        self.assertEqual(len(payloads), 48)
        self.assertEqual(set(payloads), self.verifier.EXPECTED_ARCHIVE_MEMBERS)

    def test_rejects_oversized_legal_archive_member_before_reading_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "oversized.tar"
            size = self.verifier.MAX_JSON_MEMBER_BYTES + 1
            with tarfile.open(archive_path, "w") as archive:
                info = tarfile.TarInfo("source/branch-audit.json")
                info.size = size
                archive.addfile(info, io.BytesIO(b"x" * size))
            with self.assertRaisesRegex(ValueError, "size limit"):
                self.verifier.read_safe_tar(archive_path)

    def test_rejects_unexpected_zero_byte_member_before_payload_collection(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "unexpected.tar"
            with tarfile.open(archive_path, "w") as archive:
                info = tarfile.TarInfo("source/unexpected-zero.bin")
                info.size = 0
                archive.addfile(info, io.BytesIO())
            with self.assertRaisesRegex(ValueError, "unexpected archive member"):
                self.verifier.read_safe_tar(archive_path)

    def test_repository_dependency_denominator_covers_runtime_guard_chain(self):
        required = {
            "tools/run_macos_mgba_group15_natural_branch_trace.py",
            "tools/run_macos_mgba_replay.py",
            "tools/run_macos_mgba_input_sequence.py",
            "tools/run_macos_mgba_single_input.py",
            "tools/macos_mgba_runtime_residue.py",
            "tools/run_guarded.py",
            "tools/mgba_runtime_safety.py",
            "tools/project_resource_guard.py",
            "tools/thumb_branch.py",
            "tools/build_save_state_runtime_probe.py",
            "tests/test_run_macos_mgba_group15_natural_branch_trace.py",
        }
        self.assertTrue(required.issubset(set(self.verifier.EXPECTED_REPOSITORY_FILES)))

    def test_rejects_resigned_stable_generation_dependency_hash(self):
        manifest = json.loads((ARTIFACT / "manifest.json").read_text(encoding="utf-8"))
        manifest["repository_files"][
            "tools/build_chapter_battle_route_probe.py"
        ] = "0" * 64

        with self.assertRaisesRegex(ValueError, "dependency hash mismatch"):
            self.verifier._verify_repository(manifest)

    def test_rejects_resigned_evolved_generation_dependency_hash(self):
        manifest = json.loads((ARTIFACT / "manifest.json").read_text(encoding="utf-8"))
        manifest["repository_files"][
            "tools/run_macos_mgba_input_sequence.py"
        ] = "0" * 64

        with self.assertRaisesRegex(ValueError, "historical dependency hash mismatch"):
            self.verifier._verify_repository(manifest)


if __name__ == "__main__":
    unittest.main()
