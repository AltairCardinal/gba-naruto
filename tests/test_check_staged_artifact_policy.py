import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import check_staged_artifact_policy as checker


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "check_staged_artifact_policy.py"


class CheckStagedArtifactPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.repo,
            check=True,
        )
        (self.repo / "README.md").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.repo, check=True)

    def tearDown(self):
        self.temporary.cleanup()

    def run_checker(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.repo)],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=False,
        )

    def stage_structured_artifact(self, receipt=None):
        artifact = self.repo / "artifacts" / "new-runtime"
        artifact.mkdir(parents=True)
        payload = b"asset"
        (artifact / "asset.bin").write_bytes(payload)
        manifest = {
            "schema": "git-artifact-promotion-v1",
            "artifact_status": "accepted",
            "files": {"asset.bin": receipt if receipt is not None else {
                "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload),
            }},
            "verifier": {"command": ["verify"], "exit_code": 0},
        }
        (artifact / "manifest.json").write_text(json.dumps(manifest))
        subprocess.run(["git", "add", "artifacts"], cwd=self.repo, check=True)
        return artifact

    def test_accepts_structured_hash_and_size_receipt(self):
        self.stage_structured_artifact()
        completed = self.run_checker()
        self.assertEqual(0, completed.returncode, completed.stdout)

    def test_rejects_staged_size_mismatch(self):
        self.stage_structured_artifact({
            "sha256": hashlib.sha256(b"asset").hexdigest(), "size": 4,
        })
        completed = self.run_checker()
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("size mismatch", completed.stdout)

    def test_rejects_malformed_structured_receipts(self):
        for receipt in (
            {"sha256": hashlib.sha256(b"asset").hexdigest(), "size": True},
            {"sha256": hashlib.sha256(b"asset").hexdigest()},
            {"sha256": hashlib.sha256(b"asset").hexdigest(), "size": 5, "extra": 1},
        ):
            with self.subTest(receipt=receipt):
                artifact = self.repo / "artifacts" / "new-runtime"
                if not artifact.exists():
                    self.stage_structured_artifact(receipt)
                else:
                    path = artifact / "manifest.json"
                    manifest = json.loads(path.read_text())
                    manifest["files"]["asset.bin"] = receipt
                    path.write_text(json.dumps(manifest))
                    subprocess.run(["git", "add", "artifacts"], cwd=self.repo, check=True)
                completed = self.run_checker()
                self.assertNotEqual(0, completed.returncode)
                self.assertIn("malformed file receipt", completed.stdout)

    def test_rejects_corrupt_staged_payload_even_if_worktree_is_restored(self):
        artifact = self.stage_structured_artifact(hashlib.sha256(b"asset").hexdigest())
        payload = artifact / "asset.bin"
        payload.write_bytes(b"wrong")
        subprocess.run(["git", "add", "artifacts"], cwd=self.repo, check=True)
        payload.write_bytes(b"asset")
        completed = self.run_checker()
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("hash mismatch", completed.stdout)

    def test_checks_staged_manifest_even_if_worktree_manifest_is_invalid(self):
        artifact = self.stage_structured_artifact(hashlib.sha256(b"asset").hexdigest())
        (artifact / "manifest.json").write_text("not JSON")
        completed = self.run_checker()
        self.assertEqual(0, completed.returncode, completed.stdout)

    def test_rejects_staged_symlink_even_if_worktree_is_regular(self):
        artifact = self.stage_structured_artifact(hashlib.sha256(b"asset").hexdigest())
        payload = artifact / "asset.bin"
        payload.unlink()
        payload.symlink_to("../../README.md")
        subprocess.run(["git", "add", "artifacts"], cwd=self.repo, check=True)
        payload.unlink()
        payload.write_bytes(b"asset")
        completed = self.run_checker()
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("non-regular staged member", completed.stdout)

    def test_head_advance_during_check_cannot_hide_new_artifact(self):
        artifact = self.repo / "artifacts" / "new-runtime"
        artifact.mkdir(parents=True)
        (artifact / "asset.bin").write_bytes(b"unaccepted")
        subprocess.run(["git", "add", "artifacts"], cwd=self.repo, check=True)
        original = checker._git

        def advance_head_after_diff(root, *args):
            result = original(root, *args)
            if args[0] == "diff":
                tree = original(root, "write-tree").stdout.decode().strip()
                commit = original(root, "commit-tree", tree, "-p", "HEAD",
                                  "-m", "concurrent baseline").stdout.decode().strip()
                self.assertTrue(commit)
                self.assertEqual(0, original(root, "update-ref", "HEAD", commit).returncode)
            return result

        with mock.patch.object(checker, "_git", side_effect=advance_head_after_diff):
            errors = checker.check(self.repo)
        self.assertTrue(any("missing manifest.json" in error for error in errors), errors)

    def test_baseline_blob_or_symlink_does_not_exempt_new_artifact_directory(self):
        for kind in ("blob", "symlink"):
            with self.subTest(kind=kind):
                path = self.repo / "artifacts" / kind
                path.parent.mkdir(exist_ok=True)
                if kind == "blob":
                    path.write_bytes(b"old file")
                else:
                    path.symlink_to("../README.md")
                subprocess.run(["git", "add", "artifacts"], cwd=self.repo, check=True)
                subprocess.run(["git", "commit", "-qm", "baseline non-directory"],
                               cwd=self.repo, check=True)
                path.unlink()
                path.mkdir()
                (path / "asset.bin").write_bytes(b"unaccepted")
                subprocess.run(["git", "add", "artifacts"], cwd=self.repo, check=True)
                completed = self.run_checker()
                self.assertNotEqual(0, completed.returncode)
                self.assertIn(f"artifacts/{kind}: missing manifest.json", completed.stdout)

    def test_rejects_a_new_artifact_without_acceptance_manifest(self):
        artifact = self.repo / "artifacts" / "new-runtime"
        artifact.mkdir(parents=True)
        (artifact / "asset.bin").write_bytes(b"asset")
        subprocess.run(["git", "add", "artifacts"], cwd=self.repo, check=True)

        completed = self.run_checker()

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("manifest.json", completed.stdout)

    def test_accepts_a_hash_locked_promoted_artifact(self):
        artifact = self.repo / "artifacts" / "new-runtime"
        artifact.mkdir(parents=True)
        payload = b"asset"
        (artifact / "asset.bin").write_bytes(payload)
        (artifact / "manifest.json").write_text(
            json.dumps(
                {
                    "schema": "git-artifact-promotion-v1",
                    "artifact_status": "accepted",
                    "files": {
                        "asset.bin": hashlib.sha256(payload).hexdigest()
                    },
                    "verifier": {"command": ["verify"], "exit_code": 0},
                }
            ),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "artifacts"], cwd=self.repo, check=True)

        completed = self.run_checker()

        self.assertEqual(0, completed.returncode, completed.stdout)

    def test_ignores_changes_outside_new_artifact_directories(self):
        (self.repo / "README.md").write_text("updated\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True)

        completed = self.run_checker()

        self.assertEqual(0, completed.returncode, completed.stdout)


if __name__ == "__main__":
    unittest.main()
