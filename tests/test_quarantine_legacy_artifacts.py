import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.quarantine_legacy_artifacts import apply_quarantine, plan_quarantine


class QuarantineLegacyArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Tests"],
            cwd=self.root,
            check=True,
        )

        tracked = self.root / "artifacts" / "tracked" / "manifest.json"
        tracked.parent.mkdir(parents=True)
        tracked.write_text("{}\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.root, check=True)

        (self.root / "artifacts" / "tracked" / "scratch.bin").write_bytes(b"scratch")
        legacy = self.root / "artifacts" / "legacy-run"
        legacy.mkdir(parents=True)
        (legacy / "one.bin").write_bytes(b"one")
        (legacy / "nested").mkdir()
        (legacy / "nested" / "two.bin").write_bytes(b"two")

    def tearDown(self):
        self.temporary.cleanup()

    def test_plan_only_selects_fully_untracked_artifact_roots(self):
        plan = plan_quarantine(self.root)

        self.assertEqual(plan["directories"], ["artifacts/legacy-run"])
        self.assertEqual(plan["file_count"], 2)
        self.assertEqual(plan["byte_count"], 6)

    def test_apply_writes_marked_info_exclude_and_audit(self):
        audit = self.root / "build" / "quarantine.json"
        result = apply_quarantine(self.root, audit_path=audit)

        exclude = Path(
            subprocess.run(
                ["git", "rev-parse", "--git-path", "info/exclude"],
                cwd=self.root,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()
        )
        if not exclude.is_absolute():
            exclude = self.root / exclude
        text = exclude.read_text(encoding="utf-8")
        self.assertIn("/artifacts/legacy-run/", text)
        self.assertNotIn("/artifacts/tracked/", text)
        self.assertEqual(result["directories"], ["artifacts/legacy-run"])
        self.assertEqual(json.loads(audit.read_text(encoding="utf-8"))["file_count"], 2)

        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", "artifacts"],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
        self.assertNotIn("legacy-run", untracked)
        self.assertIn("tracked/scratch.bin", untracked)

    def test_reapply_replaces_own_section_without_duplicates(self):
        audit = self.root / "build" / "quarantine.json"
        apply_quarantine(self.root, audit_path=audit)
        apply_quarantine(self.root, audit_path=audit)

        exclude_path = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        exclude = Path(exclude_path)
        if not exclude.is_absolute():
            exclude = self.root / exclude
        text = exclude.read_text(encoding="utf-8")
        self.assertEqual(text.count("/artifacts/legacy-run/"), 1)


if __name__ == "__main__":
    unittest.main()
