import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


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
