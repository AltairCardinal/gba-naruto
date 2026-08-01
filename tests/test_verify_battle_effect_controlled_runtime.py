from __future__ import annotations

import copy
import hashlib
import importlib
import inspect
import io
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-controlled-runtime-v1"


class ControlledBattleEffectRuntimeVerifierTests(unittest.TestCase):
    def _resign(self, artifact: Path) -> None:
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative in manifest["files"]:
            manifest["files"][relative] = hashlib.sha256(
                (artifact / relative).read_bytes()
            ).hexdigest()
        for relative in manifest["repository_files"]:
            manifest["repository_files"][relative] = hashlib.sha256(
                (ROOT / relative).read_bytes()
            ).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _coverage(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        return {
            "positive_group_ids": list(verifier.POSITIVE_GROUP_IDS),
            "negative_group_ids": list(verifier.NEGATIVE_GROUP_IDS),
            "controlled_case_count": 13,
            "controlled_transaction_count": 10,
            "controlled_negative_count": 3,
            "existing_observed_group_ids": [1, 2, 5, 11, 14],
            "controlled_or_observed_group_ids": [
                1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17
            ],
            "production_natural_pixel_ab": {"numerator": 4, "denominator": 18},
            "observed_frame_phase": {"numerator": 5, "denominator": 18},
            "tracked_parent_checkpoint_count": 93,
            "uncovered_sequence_group_edges": [{"group_id": 18, "sequence_id": 18}],
            "all_entry_paths_complete": False,
        }

    def test_accepts_exact_coverage_and_rejects_scope_inflation(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        verifier.validate_coverage_contract(self._coverage())

        mutations = (
            ("negative promoted", lambda row: row["positive_group_ids"].append(3)),
            (
                "natural metric changed",
                lambda row: row["production_natural_pixel_ab"].__setitem__("numerator", 14),
            ),
            ("missing sequence edge", lambda row: row.__setitem__("uncovered_sequence_group_edges", [])),
            ("all routes claim", lambda row: row.__setitem__("all_entry_paths_complete", True)),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                coverage = copy.deepcopy(self._coverage())
                mutate(coverage)
                with self.assertRaises(ValueError):
                    verifier.validate_coverage_contract(coverage)

    def test_rejects_unsafe_or_non_regular_tar_members(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        for name, kind in (("../escape.ss9", "file"), ("/absolute.ss9", "file"), ("raw/link.ss9", "link")):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "bad.tar"
                with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
                    info = tarfile.TarInfo(name)
                    info.size = 1
                    if kind == "link":
                        info.type = tarfile.SYMTYPE
                        info.linkname = "raw/target.ss9"
                        info.size = 0
                        archive.addfile(info)
                    else:
                        archive.addfile(info, io.BytesIO(b"x"))
                with self.assertRaises(ValueError):
                    verifier.read_safe_tar(path)

    def test_independent_verifier_accepts_production_artifact(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        source = inspect.getsource(verifier)
        self.assertNotIn("from tools.export_battle_effect_controlled_runtime", source)
        self.assertNotIn("import export_battle_effect_controlled_runtime", source)

        result = verifier.verify_artifact(ARTIFACT)

        self.assertEqual(result["errors"], [])
        self.assertEqual(result["positive_group_ids"], list(verifier.POSITIVE_GROUP_IDS))
        self.assertEqual(result["negative_group_ids"], list(verifier.NEGATIVE_GROUP_IDS))
        self.assertEqual(result["task_oam_binding_count"], 25)
        self.assertEqual(result["task_oam_bound_group_ids"], list(verifier.POSITIVE_GROUP_IDS))
        self.assertFalse(result["all_entry_paths_complete"])

    def test_production_artifact_archives_the_complete_source_batch(self):
        manifest = json.loads((ARTIFACT / "manifest.json").read_text(encoding="utf-8"))
        evidence = json.loads((ARTIFACT / "evidence.json").read_text(encoding="utf-8"))

        self.assertEqual(set(manifest["files"]), {"evidence.json", "raw-batch.tar"})
        self.assertEqual(evidence["archive"]["path"], "raw-batch.tar")
        self.assertEqual(evidence["archive"]["member_count"], 729)

    def test_repository_inventory_locks_probe_and_parent_verifier_dependencies(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        required = {
            "tools/build_save_state_runtime_probe.py",
            "tools/thumb_branch.py",
            "tools/verify_battle_effect_sequence_bindings.py",
            "tools/verify_battle_effect_sprite_animations.py",
            "tools/verify_battle_effect_resource_pairs.py",
        }

        self.assertTrue(required <= set(verifier.REPOSITORY_FILES))

    def test_trusted_parent_catalog_hashes_are_not_resignable_evidence(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        trusted = dict(verifier.TRUSTED_SOURCE_SHA256)
        verifier.validate_trusted_source_hashes(trusted)
        trusted["sequence_catalog"] = "00" * 32

        with self.assertRaisesRegex(ValueError, "trusted source hash mismatch"):
            verifier.validate_trusted_source_hashes(trusted)

    def test_rejects_extra_artifact_files_even_when_manifest_is_unchanged(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            (artifact / "unreviewed.bin").write_bytes(b"unreviewed")

            result = verifier.verify_artifact(artifact)

            self.assertFalse(result["verified"])
            self.assertTrue(
                any("artifact directory inventory mismatch" in error for error in result["errors"]),
                result["errors"],
            )

    def test_rejects_resigned_archived_guard_rss_tampering(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            archive_path = artifact / "raw-batch.tar"
            payloads = verifier.read_safe_tar(archive_path)
            member = "source/group-04-sequence-04/guard-summary.json"
            guard = json.loads(payloads[member].decode("utf-8"))
            guard["peak_tree_rss_mib"] = 99.0
            payloads[member] = json.dumps(guard, separators=(",", ":")).encode()
            archive_path.write_bytes(verifier._canonical_tar(payloads))
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["archive"]["sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            evidence["archive"]["size"] = archive_path.stat().st_size
            evidence["archive"]["members"][member] = {
                "sha256": hashlib.sha256(payloads[member]).hexdigest(),
                "size": len(payloads[member]),
            }
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._resign(artifact)

            result = verifier.verify_artifact(artifact)

            self.assertFalse(result["verified"])
            self.assertTrue(
                any("guard hash mismatch" in error or "RSS" in error for error in result["errors"]),
                result["errors"],
            )

    def test_rejects_resigned_dispatch_ordinal_or_oam_binding_tampering(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        for field, value, message in (
            ("dispatch_ordinal", 0, "dispatcher ordinal mismatch"),
            ("oam_index", 0, "OAM binding mismatch"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                artifact = Path(temporary) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                evidence_path = artifact / "evidence.json"
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
                positive = next(row for row in evidence["cases"] if row["group_id"] == 4)
                if field == "dispatch_ordinal":
                    positive["task_oam"][field] = value
                else:
                    positive["oam_bindings"][0][field] = value
                evidence_path.write_text(
                    json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                self._resign(artifact)

                result = verifier.verify_artifact(artifact)

                self.assertFalse(result["verified"])
                self.assertTrue(any(message in error for error in result["errors"]), result["errors"])

    def test_rejects_resigned_task_metadata_tampering(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_controlled_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            positive = next(
                row for row in evidence["cases"] if row["group_id"] == 4
            )
            positive["phases"][1]["task_flags"] = "0x00000001"
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            for relative in manifest["repository_files"]:
                manifest["repository_files"][relative] = hashlib.sha256(
                    (ROOT / relative).read_bytes()
                ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            result = verifier.verify_artifact(artifact)

            self.assertFalse(result["verified"])
            self.assertTrue(
                any("task metadata mismatch" in error for error in result["errors"]),
                result["errors"],
            )


if __name__ == "__main__":
    unittest.main()
