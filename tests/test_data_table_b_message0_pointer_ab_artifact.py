#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.export_data_table_b_message0_pointer_ab import export_artifact
from tools.verify_data_table_b_message0_pointer_ab import (
    extract_raw,
    validate_state_png_pair,
    verify_artifact,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/data-table-b-message0-pointer-pixel-ab-v1"


class DataTableBMessage0PointerAbArtifactTests(unittest.TestCase):
    def test_manifest_uses_git_artifact_promotion_schema(self):
        manifest = json.loads(
            (ARTIFACT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["schema"], "git-artifact-promotion-v1")
        self.assertEqual(manifest["artifact_status"], "accepted")
        self.assertEqual(
            manifest["artifact_schema"],
            "data-table-b-message0-pointer-pixel-ab-artifact-v1",
        )
        self.assertEqual(manifest["verifier"]["exit_code"], 0)
        self.assertIsInstance(manifest["verifier"]["command"], list)

    def test_tracked_artifact_verifies(self):
        result = verify_artifact(ROOT, ARTIFACT)
        self.assertEqual(result["message_id"], 0)
        self.assertEqual(result["different_pixel_count"], 928)

    def test_raw_archive_reexports_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            raw = temp / "raw"
            raw.mkdir()
            extract_raw(ARTIFACT / "raw.tar", raw)
            rebuilt = temp / "rebuilt"
            export_artifact(ROOT, raw, rebuilt)
            expected = {
                path.relative_to(ARTIFACT): path.read_bytes()
                for path in ARTIFACT.rglob("*")
                if path.is_file()
            }
            actual = {
                path.relative_to(rebuilt): path.read_bytes()
                for path in rebuilt.rglob("*")
                if path.is_file()
            }
            self.assertEqual(actual, expected)

    def test_rejects_evidence_tampering_after_manifest_rehash(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["runtime_effect"]["different_pixel_count"] = 0
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "evidence"):
                verify_artifact(ROOT, copied)

    def test_rejects_duplicate_raw_members(self):
        with tempfile.TemporaryDirectory() as directory:
            duplicate = Path(directory) / "duplicate.tar"
            with tarfile.open(ARTIFACT / "raw.tar", "r") as source:
                members = source.getmembers()
                payloads = [(member, source.extractfile(member).read()) for member in members]
            with tarfile.open(duplicate, "w") as output:
                import io

                for member, payload in payloads:
                    output.addfile(member, io.BytesIO(payload))
                member, payload = payloads[0]
                output.addfile(member, io.BytesIO(payload))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                extract_raw(duplicate, Path(directory) / "raw")

    def test_rejects_state_png_screen_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "raw"
            raw.mkdir()
            extract_raw(ARTIFACT / "raw.tar", raw)
            with self.assertRaisesRegex(ValueError, "embedded screen"):
                validate_state_png_pair(
                    raw / "baseline/output.ss9",
                    raw / "candidate/output.png",
                    "test",
                )


if __name__ == "__main__":
    unittest.main()
