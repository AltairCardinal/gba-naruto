from __future__ import annotations

import importlib
import hashlib
import inspect
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-frame-phase-v1"
OBSERVED_GROUP_ARTIFACTS = {
    1: (ROOT / "artifacts/battle-effect-frame-phase-group1-v1", 12),
    2: (ROOT / "artifacts/battle-effect-frame-phase-group2-v1", 0),
    5: (ROOT / "artifacts/battle-effect-frame-phase-group5-v1", 2),
    14: (ROOT / "artifacts/battle-effect-frame-phase-group14-v1", 2),
}
NATURAL_DELAYED_PROFILE = (
    ROOT
    / "sequel/content/battle-effect-phase-capture/group-03-natural-tool67-expiry.json"
)
NATURAL_DELAYED_ARTIFACT = (
    ROOT / "artifacts/battle-effect-frame-phase-group3-natural-v1"
)


class BattleEffectFramePhaseVerifierTests(unittest.TestCase):
    def _natural_source_fixture(self, temporary_root):
        profile = json.loads(NATURAL_DELAYED_PROFILE.read_text(encoding="utf-8"))
        catalog = json.loads(
            (
                ROOT
                / "sequel/content/battle-effect-phase-capture/source-provenance-v1.json"
            ).read_text(encoding="utf-8")
        )
        contract = next(
            row
            for row in catalog["profiles"]
            if row["profile_id"] == profile["profile_id"]
        )
        contract = json.loads(json.dumps(contract))
        for relative in (
            profile["input_state"],
            profile["source_runtime_evidence"],
            contract["static_chain"]["path"],
            "notes/battle-action-template-semantics-bindings-20260723.json",
            "rom/base.gba",
        ):
            source = ROOT / relative
            destination = temporary_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return profile, contract

    def test_accepts_natural_delayed_object_checkpoint_provenance(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        profile = json.loads(NATURAL_DELAYED_PROFILE.read_text(encoding="utf-8"))
        catalog = json.loads(
            (
                ROOT
                / "sequel/content/battle-effect-phase-capture/source-provenance-v1.json"
            ).read_text(encoding="utf-8")
        )
        contract = next(
            row
            for row in catalog["profiles"]
            if row["profile_id"] == profile["profile_id"]
        )
        verifier.validate_source_runtime_provenance(
            ROOT,
            profile,
            contract,
            group_id=3,
            input_state_path=profile["input_state"],
            input_state_sha256=profile["input_state_sha256"],
            rom_sha256=profile["source_rom_sha256"],
        )

    def test_accepts_natural_group3_expiry_phase_artifact(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        result = verifier.verify_artifact(NATURAL_DELAYED_ARTIFACT)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["group_id"], 3)
        self.assertEqual(result["pending_sequence"], [0, 1, 0])
        self.assertEqual(result["target_dispatch_ordinals"], [0, 0, 0])
        self.assertTrue(result["ack_shadow_matches_hardware"])

    def test_rejects_natural_delayed_object_contract_tampering(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        profile = json.loads(NATURAL_DELAYED_PROFILE.read_text(encoding="utf-8"))
        catalog = json.loads(
            (
                ROOT
                / "sequel/content/battle-effect-phase-capture/source-provenance-v1.json"
            ).read_text(encoding="utf-8")
        )
        original = next(
            row
            for row in catalog["profiles"]
            if row["profile_id"] == profile["profile_id"]
        )
        cases = (
            ("remaining turns", lambda row: row["delayed_object"].__setitem__("remaining_turns", 1)),
            ("static chain hash", lambda row: row["static_chain"].__setitem__("sha256", "0" * 64)),
        )
        for expected, mutate in cases:
            with self.subTest(expected=expected):
                contract = json.loads(json.dumps(original))
                mutate(contract)
                with self.assertRaisesRegex(ValueError, expected):
                    verifier.validate_source_runtime_provenance(
                        ROOT,
                        profile,
                        contract,
                        group_id=3,
                        input_state_path=profile["input_state"],
                        input_state_sha256=profile["input_state_sha256"],
                        rom_sha256=profile["source_rom_sha256"],
                    )

    def test_rejects_natural_delayed_source_semantic_tampering(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        cases = (
            (
                "natural action submission",
                lambda evidence, contract: evidence["scope"].__setitem__(
                    "natural_action_submission_verified", False
                ),
            ),
            (
                "natural object creation",
                lambda evidence, contract: evidence["scope"].__setitem__(
                    "natural_object_creation_verified", False
                ),
            ),
            (
                "natural expiry handler",
                lambda evidence, contract: evidence["scope"].__setitem__(
                    "natural_expiry_handler_verified", True
                ),
            ),
            (
                "ninja tool",
                lambda evidence, contract: evidence["runtime_binding"].__setitem__(
                    "ninja_tool_id", 68
                ),
            ),
            (
                "base ROM",
                lambda evidence, contract: evidence["provenance"].__setitem__(
                    "base_rom_sha256", "0" * 64
                ),
            ),
        )
        for expected, mutate in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                profile, contract = self._natural_source_fixture(root)
                evidence_path = root / profile["source_runtime_evidence"]
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
                mutate(evidence, contract)
                evidence_path.write_text(
                    json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                evidence_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                profile["source_runtime_evidence_sha256"] = evidence_hash
                contract["source_evidence"]["sha256"] = evidence_hash
                with self.assertRaisesRegex(ValueError, expected):
                    verifier.validate_source_runtime_provenance(
                        root,
                        profile,
                        contract,
                        group_id=3,
                        input_state_path=profile["input_state"],
                        input_state_sha256=profile["input_state_sha256"],
                        rom_sha256=profile["source_rom_sha256"],
                    )

    def test_rejects_natural_delayed_source_with_accepted_parent(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        profile = json.loads(NATURAL_DELAYED_PROFILE.read_text(encoding="utf-8"))
        catalog = json.loads(
            (
                ROOT
                / "sequel/content/battle-effect-phase-capture/source-provenance-v1.json"
            ).read_text(encoding="utf-8")
        )
        contract = json.loads(
            json.dumps(
                next(
                    row
                    for row in catalog["profiles"]
                    if row["profile_id"] == profile["profile_id"]
                )
            )
        )
        contract["accepted_parent"] = {}
        with self.assertRaisesRegex(ValueError, "accepted parent"):
            verifier.validate_source_runtime_provenance(
                ROOT,
                profile,
                contract,
                group_id=3,
                input_state_path=profile["input_state"],
                input_state_sha256=profile["input_state_sha256"],
                rom_sha256=profile["source_rom_sha256"],
            )

    def test_rejects_natural_delayed_source_when_static_chain_verifier_fails(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            profile, contract = self._natural_source_fixture(root)
            chain_path = root / contract["static_chain"]["path"]
            chain = json.loads(chain_path.read_text(encoding="utf-8"))
            chain["allocator_contract"]["end_tile"] -= 1
            chain_path.write_text(
                json.dumps(chain, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            contract["static_chain"]["sha256"] = hashlib.sha256(
                chain_path.read_bytes()
            ).hexdigest()
            with self.assertRaisesRegex(ValueError, "static chain verifier"):
                verifier.validate_source_runtime_provenance(
                    root,
                    profile,
                    contract,
                    group_id=3,
                    input_state_path=profile["input_state"],
                    input_state_sha256=profile["input_state_sha256"],
                    rom_sha256=profile["source_rom_sha256"],
                )

    def test_independent_verifier_accepts_production_artifact(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        source = inspect.getsource(verifier)
        self.assertNotIn("export_battle_effect_frame_phase", source)
        result = verifier.verify_artifact(ARTIFACT)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["group_id"], 11)
        self.assertEqual(result["pending_sequence"], [0, 1, 0])
        self.assertTrue(result["ack_shadow_matches_hardware"])
        self.assertTrue(result["renderer_shadow_differs_from_hardware"])
        self.assertEqual(result["non_state_equivalent_dumps"], ["io.bin"])
        self.assertEqual(
            result["breakpoint_addresses"],
            ["0x08063328", "0x08061126", "0x080612AA"],
        )
        self.assertEqual(result["target_dispatch_ordinals"], [0, 0, 0])

    def test_thumb_breakpoint_pc_and_dispatch_membership_are_independent(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        self.assertEqual(
            verifier.thumb_breakpoint_address(0x0806332A, 0x6000003F),
            0x08063328,
        )
        slots = verifier.decode_active_task_slots(
            b"\x03",
            bytes.fromhex("c8580003045900037c590003") + bytes(0x200 - 12),
        )
        self.assertEqual(slots, [124, 125, 127])
        self.assertEqual(verifier.target_dispatch_ordinal(slots, 124), 0)
        self.assertEqual(verifier.target_dispatch_ordinal(slots, 127), 2)
        with self.assertRaisesRegex(ValueError, "exactly once"):
            verifier.target_dispatch_ordinal([125, 127], 124)
        with self.assertRaisesRegex(ValueError, "aligned"):
            verifier.decode_active_task_slots(
                b"\x01", bytes.fromhex("c9580003") + bytes(0x200 - 4)
            )

    def test_group_identity_is_derived_from_animation_catalog(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        catalog = json.loads(
            (
                ROOT
                / "artifacts/battle-effect-sprite-animations-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            verifier.effect_group_identity(catalog, 14),
            (0x083468D0, 0x08346914),
        )
        with self.assertRaisesRegex(ValueError, "exactly once"):
            verifier.effect_group_identity(catalog, 99)

    def test_rejects_toolchain_profile_hash_tampering(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["toolchain"]["sha256"] = "0" * 64
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verifier.verify_artifact(artifact)
            self.assertIn("toolchain profile hash mismatch", result["errors"])

    def test_rejects_runtime_audit_profile_hash_tampering(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            audit_path = artifact / "runtime-audit.json"
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["profile_sha256"] = "0" * 64
            audit_path.write_text(
                json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["runtime-audit.json"] = hashlib.sha256(
                audit_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verifier.verify_artifact(artifact)
            self.assertIn("runtime audit profile hash mismatch", result["errors"])

    def test_accepts_every_new_observed_group_phase_artifact(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        for group_id, (artifact, ordinal) in OBSERVED_GROUP_ARTIFACTS.items():
            with self.subTest(group_id=group_id):
                result = verifier.verify_artifact(artifact)
                self.assertEqual(result["errors"], [])
                self.assertEqual(result["group_id"], group_id)
                self.assertEqual(
                    result["target_dispatch_ordinals"], [ordinal, ordinal, ordinal]
                )
                self.assertEqual(result["pending_sequence"], [0, 1, 0])
                self.assertTrue(result["ack_shadow_matches_hardware"])

    def test_rejects_unaccepted_source_runtime_evidence_provenance(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_runtime_provenance"]["contract"]["accepted_parent"][
                "manifest_sha256"
            ] = "0" * 64
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verifier.verify_artifact(artifact)
            self.assertIn(
                "source runtime artifact manifest hash mismatch",
                result["errors"],
            )

    def test_rejects_artifact_level_pc_and_dispatcher_tampering(self):
        verifier = importlib.import_module("tools.verify_battle_effect_frame_phase")
        cases = (
            (
                "pc",
                "raw/renderer-post/capture-phase.json",
                lambda phase: phase.__setitem__("address", "0x0806332A"),
                "renderer-post address mismatch",
            ),
            (
                "dispatcher",
                "raw/renderer-post/capture-phase.json",
                lambda phase: phase.__setitem__("task_slot", 0),
                "renderer-post dispatcher membership mismatch",
            ),
        )
        for name, relative, mutate, expected_error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                artifact = Path(tmp) / "artifact"
                shutil.copytree(ARTIFACT, artifact)
                phase_path = artifact / relative
                phase = json.loads(phase_path.read_text(encoding="utf-8"))
                mutate(phase)
                phase_path.write_text(
                    json.dumps(phase, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                manifest_path = artifact / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["files"][relative] = hashlib.sha256(
                    phase_path.read_bytes()
                ).hexdigest()
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                result = verifier.verify_artifact(artifact)
                self.assertTrue(
                    any(expected_error in error for error in result["errors"]),
                    result["errors"],
                )


if __name__ == "__main__":
    unittest.main()
