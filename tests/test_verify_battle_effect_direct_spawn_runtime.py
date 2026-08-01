import hashlib
import importlib
import inspect
import json
import copy
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "artifacts/battle-effect-direct-spawn-runtime-v1"


class BattleEffectDirectSpawnRuntimeVerifierTests(unittest.TestCase):
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

    def _replace_raw_member(
        self, verifier, artifact: Path, member: str, document: dict
    ) -> None:
        archive_path = artifact / "raw-batch.tar"
        payloads = verifier.read_safe_tar(archive_path)
        payloads[member] = (
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        archive_path.write_bytes(verifier._canonical_tar(payloads))
        evidence_path = artifact / "evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["archive"] = {
            "path": "raw-batch.tar",
            "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            "size": archive_path.stat().st_size,
            "member_count": len(payloads),
            "members": {
                name: {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                for name, raw in payloads.items()
            },
        }
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._resign(artifact)

    def test_independent_verifier_accepts_production_artifact(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_direct_spawn_runtime"
        )
        source = inspect.getsource(verifier)
        self.assertNotIn("import export_battle_effect_direct_spawn_runtime", source)
        self.assertNotIn("from tools.export_battle_effect_direct_spawn_runtime", source)

        result = verifier.verify_artifact(ARTIFACT)

        self.assertEqual(result["errors"], [])
        self.assertEqual(result["direct_case_count"], 4)
        self.assertEqual(result["controlled_or_observed_groups"], 18)
        self.assertEqual(result["narrow_group3_selector"], 0xFF)
        self.assertEqual(result["wide_group3_selectors"], [0, 0])
        self.assertFalse(result["group3_mirror_branch_proven"])

    def test_rejects_resigned_scope_inflation(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_direct_spawn_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["coverage"]["production_natural_pixel_ab"] = {
                "numerator": 18,
                "denominator": 18,
            }
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._resign(artifact)

            result = verifier.verify_artifact(artifact)

            self.assertFalse(result["verified"])
            self.assertTrue(any("coverage boundary" in row for row in result["errors"]))

    def test_18_of_18_union_is_bound_to_verified_parent_artifacts(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_direct_spawn_runtime"
        )

        self.assertEqual(
            verifier.SOURCE_PATHS["parent_controlled_manifest"],
            "artifacts/battle-effect-controlled-runtime-v1/manifest.json",
        )
        self.assertEqual(
            verifier.SOURCE_PATHS["parent_group15_manifest"],
            "artifacts/battle-effect-group15-allocator-side-runtime-v1/manifest.json",
        )
        self.assertIn(
            "tools/verify_battle_effect_controlled_runtime.py",
            verifier.REPOSITORY_FILES,
        )
        self.assertIn(
            "tools/verify_battle_effect_group15_allocator_side_runtime.py",
            verifier.REPOSITORY_FILES,
        )

    def test_runtime_runner_dependency_closure_is_manifested(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_direct_spawn_runtime"
        )

        for relative in (
            "tools/run_macos_mgba_input_sequence.py",
            "tools/run_macos_mgba_replay.py",
            "tools/run_macos_mgba_single_input.py",
        ):
            with self.subTest(relative=relative):
                self.assertIn(relative, verifier.REPOSITORY_FILES)

    def test_rejects_resigned_archived_runtime_provenance_tampering(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_direct_spawn_runtime"
        )
        payloads = verifier.read_safe_tar(ARTIFACT / "raw-batch.tar")
        evidence = json.loads((ARTIFACT / "evidence.json").read_text(encoding="utf-8"))
        animations = json.loads(
            (ROOT / verifier.ANIMATION_CATALOG).read_text(encoding="utf-8")
        )
        resources = json.loads(
            (ROOT / verifier.RESOURCE_CATALOG).read_text(encoding="utf-8")
        )
        case = verifier.CASE_ROWS[0]
        case_id = case["case_id"]
        prefix = f"source/{case_id}"

        mutations = (
            (f"{prefix}/batch-audit.json", ("input_state_sha256",), "0" * 64),
            (
                f"{prefix}/output/audit.json",
                ("toolchain", "source_commit"),
                "0" * 40,
            ),
        )
        for member, keys, replacement in mutations:
            with self.subTest(member=member, keys=keys):
                tampered = dict(payloads)
                document = json.loads(tampered[member].decode("utf-8"))
                cursor = document
                for key in keys[:-1]:
                    cursor = cursor[key]
                cursor[keys[-1]] = replacement
                tampered[member] = (
                    json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n"
                ).encode("utf-8")
                recorded = copy.deepcopy(evidence["cases"][0])
                if member.endswith("/output/audit.json"):
                    recorded["audit_sha256"] = hashlib.sha256(
                        tampered[member]
                    ).hexdigest()

                with tempfile.TemporaryDirectory() as temporary:
                    with self.assertRaisesRegex(
                        ValueError, "runtime audit provenance mismatch"
                    ):
                        verifier._verify_case(
                            tampered,
                            recorded,
                            case,
                            {row["group_id"]: row for row in animations["groups"]}[
                                case["group_id"]
                            ],
                            {row["group_id"]: row for row in resources["entries"]}[
                                case["group_id"]
                            ],
                            Path(temporary),
                        )

    def test_rejects_resigned_narrow_negative_provenance_tampering(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_direct_spawn_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            member = "source/narrow-window-negative/output/audit.json"
            payloads = verifier.read_safe_tar(artifact / "raw-batch.tar")
            audit = json.loads(payloads[member].decode("utf-8"))
            audit["input_state_sha256"] = "0" * 64
            self._replace_raw_member(verifier, artifact, member, audit)

            result = verifier.verify_artifact(artifact)

            self.assertFalse(result["verified"])
            self.assertTrue(
                any("narrow-window negative" in row for row in result["errors"])
            )

    def test_rejects_resigned_negative_completed_run_ledger_tampering(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_direct_spawn_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            member = "source/narrow-window-negative/run-inventory.json"
            payloads = verifier.read_safe_tar(artifact / "raw-batch.tar")
            inventory = json.loads(payloads[member].decode("utf-8"))
            original = (
                "output/group-03-sequence-03-direct-spawn/staged.gba"
            )
            inventory["files"][original]["sha256"] = "0" * 64
            self._replace_raw_member(verifier, artifact, member, inventory)

            result = verifier.verify_artifact(artifact)

            self.assertFalse(result["verified"])
            self.assertTrue(
                any("negative run ledger" in row for row in result["errors"])
            )


if __name__ == "__main__":
    unittest.main()
