import json
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VerifyBattleEffectRuntimeOamTaskBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_battle_effect_runtime_oam_task_bindings import export_bindings

        cls.temporary = tempfile.TemporaryDirectory()
        cls.bindings_path = Path(cls.temporary.name) / "bindings.json"
        export_bindings(ROOT, cls.bindings_path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_independently_reconstructs_task_and_oam_bindings(self):
        from tools.verify_battle_effect_runtime_oam_task_bindings import verify_bindings

        report = verify_bindings(ROOT, self.bindings_path)

        self.assertEqual(
            {
                "verified": True,
                "errors": [],
                "tracked_checkpoints": 93,
                "supplemental_states": 5,
                "recognized_effect_tasks": 12,
                "accepted_bindings": 3,
                "observed_group_ids": [1, 2, 5, 11, 14],
            },
            report,
        )

    def test_verifier_does_not_import_exporter(self):
        source = (
            ROOT / "tools/verify_battle_effect_runtime_oam_task_bindings.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("export_battle_effect_runtime_oam_task_bindings", source)

    def test_rejects_runtime_offset_tampering(self):
        from tools.verify_battle_effect_runtime_oam_task_bindings import verify_bindings

        value = json.loads(self.bindings_path.read_text(encoding="utf-8"))
        checkpoint = next(
            item for item in value["tracked_checkpoints"] if item["accepted_bindings"]
        )
        checkpoint["runtime_offset_table"]["entries"][0]["y_q8_8"] = 0
        tampered = Path(self.temporary.name) / "tampered-offset.json"
        tampered.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )

        report = verify_bindings(ROOT, tampered)

        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

    def test_rejects_task_group_identity_tampering(self):
        from tools.verify_battle_effect_runtime_oam_task_bindings import verify_bindings

        value = json.loads(self.bindings_path.read_text(encoding="utf-8"))
        checkpoint = next(
            item for item in value["tracked_checkpoints"] if item["accepted_bindings"]
        )
        checkpoint["accepted_bindings"][0]["task"]["group_id"] = 2
        tampered = Path(self.temporary.name) / "tampered-group.json"
        tampered.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )

        report = verify_bindings(ROOT, tampered)

        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

    def test_rejects_nonaccepted_parent_promotion(self):
        from tools.verify_battle_effect_runtime_oam_task_bindings import (
            _validate_provenance,
        )

        parent_path = ROOT / "artifacts/battle-effect-runtime-oam-bindings-v1/bindings.json"
        manifest_path = ROOT / "artifacts/battle-effect-runtime-oam-bindings-v1/manifest.json"
        source_path = ROOT / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
        parent_raw = parent_path.read_bytes()
        source_raw = source_path.read_bytes()
        parent = json.loads(parent_raw)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = json.loads(source_raw)
        manifest["artifact_status"] = "candidate"

        with self.assertRaisesRegex(ValueError, "accepted"):
            _validate_provenance(
                parent,
                manifest,
                source,
                hashlib.sha256(parent_raw).hexdigest(),
                hashlib.sha256(source_raw).hexdigest(),
            )

    def test_rejects_parent_source_provenance_or_scope_tampering(self):
        from tools.verify_battle_effect_runtime_oam_task_bindings import (
            _validate_provenance,
        )

        parent_path = ROOT / "artifacts/battle-effect-runtime-oam-bindings-v1/bindings.json"
        manifest_path = ROOT / "artifacts/battle-effect-runtime-oam-bindings-v1/manifest.json"
        source_path = ROOT / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
        parent_raw = parent_path.read_bytes()
        source_raw = source_path.read_bytes()
        parent = json.loads(parent_raw)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = json.loads(source_raw)

        bad_parent = copy.deepcopy(parent)
        bad_parent["source_artifact"]["manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source provenance"):
            _validate_provenance(
                bad_parent,
                manifest,
                source,
                hashlib.sha256(parent_raw).hexdigest(),
                hashlib.sha256(source_raw).hexdigest(),
            )

        bad_source = copy.deepcopy(source)
        bad_source["scope"]["component_lists_complete"] = False
        with self.assertRaisesRegex(ValueError, "source scope"):
            _validate_provenance(
                parent,
                manifest,
                bad_source,
                hashlib.sha256(parent_raw).hexdigest(),
                hashlib.sha256(source_raw).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
