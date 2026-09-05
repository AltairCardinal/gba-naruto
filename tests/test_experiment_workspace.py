import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import tools.experiment_workspace as experiment_workspace

from tools.experiment_workspace import (
    archive_run,
    complete_run,
    init_run,
    maintenance,
    promote_run,
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(payload: dict) -> str:
    return json.dumps(
        payload, indent=2, ensure_ascii=False, sort_keys=True
    ) + "\n"


class ExperimentWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        (self.root / "artifacts").mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def _accepted_final(self, run: Path, payload: bytes = b"asset") -> Path:
        final = run / "final"
        final.mkdir(parents=True)
        (final / "asset.bin").write_bytes(payload)
        (final / "manifest.json").write_text(
            canonical_json(
                {
                    "schema": "git-artifact-promotion-v1",
                    "artifact_status": "accepted",
                    "files": {"asset.bin": sha256(payload)},
                    "verifier": {"command": ["verify"], "exit_code": 0},
                }
            ),
            encoding="utf-8",
        )
        return final

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
        payload = b"asset"
        self._accepted_final(run, payload)

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

    def test_promotion_accepts_structured_file_receipts(self):
        run = init_run(self.root, "reverse", "structured-001")
        final = run / "final"
        final.mkdir()
        payload = b"structured asset"
        (final / "asset.bin").write_bytes(payload)
        (final / "manifest.json").write_text(
            canonical_json(
                {
                    "schema": "git-artifact-promotion-v1",
                    "artifact_status": "accepted",
                    "files": {
                        "asset.bin": {
                            "sha256": sha256(payload),
                            "size": len(payload),
                        }
                    },
                    "verifier": {"command": ["verify"], "exit_code": 0},
                }
            ),
            encoding="utf-8",
        )

        promoted = promote_run(
            self.root,
            "reverse",
            "structured-001",
            "structured-runtime-v1",
        )

        self.assertEqual(payload, (promoted / "asset.bin").read_bytes())

    def test_promotion_rejects_structured_receipt_size_or_hash_mismatch(self):
        payload = b"structured asset"
        cases = {
            "size": {"sha256": sha256(payload), "size": len(payload) + 1},
            "hash": {"sha256": "0" * 64, "size": len(payload)},
        }
        for mismatch, receipt in cases.items():
            with self.subTest(mismatch=mismatch):
                run_id = f"structured-bad-{mismatch}-001"
                run = init_run(self.root, "reverse", run_id)
                final = run / "final"
                final.mkdir()
                (final / "asset.bin").write_bytes(payload)
                (final / "manifest.json").write_text(
                    canonical_json(
                        {
                            "schema": "git-artifact-promotion-v1",
                            "artifact_status": "accepted",
                            "files": {"asset.bin": receipt},
                            "verifier": {
                                "command": ["verify"],
                                "exit_code": 0,
                            },
                        }
                    ),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(ValueError, mismatch):
                    promote_run(
                        self.root,
                        "reverse",
                        run_id,
                        f"structured-bad-{mismatch}-runtime-v1",
                    )

    def test_promotion_rejects_an_incorrect_hash(self):
        run = init_run(self.root, "reverse", "bad-001")
        final = run / "final"
        final.mkdir()
        (final / "asset.bin").write_bytes(b"asset")
        (final / "manifest.json").write_text(
            canonical_json(
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

    def test_promotion_rejects_noncanonical_manifest(self):
        run = init_run(self.root, "reverse", "noncanonical-001")
        final = self._accepted_final(run)
        manifest_path = final / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_path.write_text(
            json.dumps(manifest, separators=(",", ":")), encoding="utf-8"
        )

        with self.assertRaisesRegex(ValueError, "canonical"):
            promote_run(
                self.root,
                "reverse",
                "noncanonical-001",
                "noncanonical-runtime-v1",
            )

    def test_promotion_rejects_final_member_and_ancestor_symlinks(self):
        real_final = self.root / "real-final"
        self._accepted_final(real_final.parent / "real-run")
        real_final = real_final.parent / "real-run" / "final"
        linked_final = self.root / "linked-final"
        linked_final.symlink_to(real_final, target_is_directory=True)
        with self.subTest(kind="final"):
            with self.assertRaisesRegex(ValueError, "symlink"):
                experiment_workspace._validate_promotion_manifest(linked_final)

        member_final = self.root / "member-final"
        member_final.mkdir()
        external_asset = self.root / "external-asset.bin"
        external_asset.write_bytes(b"asset")
        (member_final / "asset.bin").symlink_to(external_asset)
        (member_final / "manifest.json").write_text(
            canonical_json(
                {
                    "schema": "git-artifact-promotion-v1",
                    "artifact_status": "accepted",
                    "files": {"asset.bin": sha256(b"asset")},
                    "verifier": {"command": ["verify"], "exit_code": 0},
                }
            ),
            encoding="utf-8",
        )
        with self.subTest(kind="member"):
            with self.assertRaisesRegex(ValueError, "symlink"):
                experiment_workspace._validate_promotion_manifest(member_final)

        manifest_final = self.root / "manifest-final"
        manifest_final.mkdir()
        (manifest_final / "asset.bin").write_bytes(b"asset")
        external_manifest = self.root / "external-manifest.json"
        external_manifest.write_text(
            canonical_json(
                {
                    "schema": "git-artifact-promotion-v1",
                    "artifact_status": "accepted",
                    "files": {"asset.bin": sha256(b"asset")},
                    "verifier": {"command": ["verify"], "exit_code": 0},
                }
            ),
            encoding="utf-8",
        )
        (manifest_final / "manifest.json").symlink_to(external_manifest)
        with self.subTest(kind="manifest"):
            with self.assertRaisesRegex(ValueError, "symlink"):
                experiment_workspace._validate_promotion_manifest(manifest_final)

        empty_link_final = self.root / "empty-link-final"
        empty_link_final.mkdir()
        external_empty = self.root / "external-empty"
        external_empty.mkdir()
        (empty_link_final / "linked-empty").symlink_to(
            external_empty, target_is_directory=True
        )
        (empty_link_final / "manifest.json").write_text(
            canonical_json(
                {
                    "schema": "git-artifact-promotion-v1",
                    "artifact_status": "accepted",
                    "files": {},
                    "verifier": {"command": ["verify"], "exit_code": 0},
                }
            ),
            encoding="utf-8",
        )
        with self.subTest(kind="empty-member-directory"):
            with self.assertRaisesRegex(ValueError, "symlink"):
                experiment_workspace._validate_promotion_manifest(empty_link_final)

        real_parent = self.root / "real-parent"
        real_parent.mkdir()
        self._accepted_final(real_parent / "run")
        linked_parent = self.root / "linked-parent"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        with self.subTest(kind="ancestor"):
            with self.assertRaisesRegex(ValueError, "symlink"):
                experiment_workspace._validate_promotion_manifest(
                    linked_parent / "run" / "final"
                )

    def test_promotion_rejects_symlinked_artifacts_target_root(self):
        run = init_run(self.root, "reverse", "target-symlink-001")
        self._accepted_final(run)
        artifacts = self.root / "artifacts"
        artifacts.rmdir()
        external = self.root / "external-artifacts"
        external.mkdir()
        artifacts.symlink_to(external, target_is_directory=True)

        with mock.patch.object(
            experiment_workspace.shutil,
            "copytree",
            wraps=experiment_workspace.shutil.copytree,
        ) as copytree:
            with self.assertRaisesRegex(ValueError, "symlink"):
                promote_run(
                    self.root,
                    "reverse",
                    "target-symlink-001",
                    "target-symlink-runtime-v1",
                )
            copytree.assert_not_called()

        self.assertEqual([], list(external.iterdir()))

    def test_promotion_rolls_back_target_and_run_state_when_completion_fails(self):
        run = init_run(self.root, "reverse", "rollback-complete-001")
        self._accepted_final(run)
        metadata_path = run / ".experiment.json"
        inventory_path = run / ".inventory.json"
        original_metadata = metadata_path.read_bytes()
        original_complete = experiment_workspace.complete_run

        def complete_then_fail(*args, **kwargs):
            original_complete(*args, **kwargs)
            raise RuntimeError("completion failed after mutation")

        with mock.patch.object(
            experiment_workspace,
            "complete_run",
            side_effect=complete_then_fail,
        ):
            with self.assertRaisesRegex(RuntimeError, "completion failed"):
                promote_run(
                    self.root,
                    "reverse",
                    "rollback-complete-001",
                    "rollback-complete-runtime-v1",
                )

        self.assertFalse(
            (self.root / "artifacts/rollback-complete-runtime-v1").exists()
        )
        self.assertEqual(original_metadata, metadata_path.read_bytes())
        self.assertFalse(inventory_path.exists())

    def test_promotion_rolls_back_when_final_metadata_write_fails(self):
        run = init_run(self.root, "reverse", "rollback-metadata-001")
        self._accepted_final(run)
        metadata_path = run / ".experiment.json"
        inventory_path = run / ".inventory.json"
        original_metadata = metadata_path.read_bytes()
        original_write = experiment_workspace._write_json

        def fail_promoted_metadata(path, value):
            if path == metadata_path and "promoted_to" in value:
                raise RuntimeError("promoted metadata write failed")
            return original_write(path, value)

        with mock.patch.object(
            experiment_workspace,
            "_write_json",
            side_effect=fail_promoted_metadata,
        ):
            with self.assertRaisesRegex(RuntimeError, "metadata write failed"):
                promote_run(
                    self.root,
                    "reverse",
                    "rollback-metadata-001",
                    "rollback-metadata-runtime-v1",
                )

        self.assertFalse(
            (self.root / "artifacts/rollback-metadata-runtime-v1").exists()
        )
        self.assertEqual(original_metadata, metadata_path.read_bytes())
        self.assertFalse(inventory_path.exists())

    def test_atomic_json_write_removes_temporary_file_when_replace_fails(self):
        target = self.root / "state.json"
        target.write_bytes(b"original\n")

        with mock.patch.object(
            experiment_workspace.os,
            "replace",
            side_effect=OSError("replace failed"),
        ):
            with self.assertRaisesRegex(OSError, "replace failed"):
                experiment_workspace._write_json(target, {"state": "new"})

        self.assertEqual(b"original\n", target.read_bytes())
        self.assertEqual([], list(self.root.glob(".state.json.*.tmp")))

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
