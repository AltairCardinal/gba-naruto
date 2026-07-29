import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.experiment_workspace import (
    archive_run,
    complete_run,
    init_run,
    maintenance,
    promote_run,
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class ExperimentWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "artifacts").mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def test_completed_run_is_verified_then_archived_as_one_file(self):
        run = init_run(self.root, "reverse", "fbff-001")
        (run / "trace").mkdir()
        (run / "trace" / "frame-000.bin").write_bytes(b"frame")

        completed = complete_run(self.root, "reverse", "fbff-001")
        archived = archive_run(self.root, "reverse", "fbff-001")

        self.assertEqual("completed", completed["status"])
        self.assertEqual(1, completed["inventory"]["file_count"])
        self.assertFalse(run.exists())
        self.assertTrue(archived["archive_path"].is_file())
        self.assertTrue(archived["sidecar_path"].is_file())
        sidecar = json.loads(
            archived["sidecar_path"].read_text(encoding="utf-8")
        )
        self.assertEqual("experiment-archive-v1", sidecar["schema"])
        self.assertEqual("reverse", sidecar["task"])
        self.assertEqual("fbff-001", sidecar["run_id"])
        self.assertEqual(
            sha256(archived["archive_path"].read_bytes()),
            sidecar["archive_sha256"],
        )
        self.assertTrue(sidecar["verified"])

    def test_promotion_requires_an_accepted_hash_manifest(self):
        run = init_run(self.root, "reverse", "sprite-001")
        final = run / "final"
        final.mkdir()
        payload = b"asset"
        (final / "asset.bin").write_bytes(payload)
        (final / "manifest.json").write_text(
            json.dumps(
                {
                    "schema": "git-artifact-promotion-v1",
                    "artifact_status": "accepted",
                    "files": {"asset.bin": sha256(payload)},
                    "verifier": {"command": ["verify"], "exit_code": 0},
                }
            ),
            encoding="utf-8",
        )

        promoted = promote_run(
            self.root,
            "reverse",
            "sprite-001",
            "sprite-runtime-v1",
        )

        self.assertEqual(
            self.root.resolve() / "artifacts" / "sprite-runtime-v1",
            promoted,
        )
        self.assertEqual(payload, (promoted / "asset.bin").read_bytes())

    def test_promotion_rejects_an_incorrect_hash(self):
        run = init_run(self.root, "reverse", "bad-001")
        final = run / "final"
        final.mkdir()
        (final / "asset.bin").write_bytes(b"asset")
        (final / "manifest.json").write_text(
            json.dumps(
                {
                    "schema": "git-artifact-promotion-v1",
                    "artifact_status": "accepted",
                    "files": {"asset.bin": "0" * 64},
                    "verifier": {"command": ["verify"], "exit_code": 0},
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "hash"):
            promote_run(self.root, "reverse", "bad-001", "bad-runtime-v1")

    def test_maintenance_only_archives_explicitly_completed_runs(self):
        active = init_run(self.root, "reverse", "active-001")
        completed = init_run(self.root, "reverse", "done-001")
        (active / "payload.bin").write_bytes(b"active")
        (completed / "payload.bin").write_bytes(b"done")
        complete_run(self.root, "reverse", "done-001")

        dry_run = maintenance(self.root, apply=False)
        self.assertEqual(["reverse/done-001"], dry_run["archive_candidates"])
        self.assertTrue(active.is_dir())
        self.assertTrue(completed.is_dir())

        applied = maintenance(self.root, apply=True)

        self.assertEqual(["reverse/done-001"], applied["archived"])
        self.assertTrue(active.is_dir())
        self.assertFalse(completed.exists())

    def test_identifiers_cannot_escape_the_workspace(self):
        with self.assertRaisesRegex(ValueError, "identifier"):
            init_run(self.root, "../reverse", "run")
        with self.assertRaisesRegex(ValueError, "identifier"):
            init_run(self.root, "reverse", "../run")


if __name__ == "__main__":
    unittest.main()
