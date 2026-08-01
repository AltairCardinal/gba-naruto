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


ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "artifacts/battle-effect-group15-allocator-side-runtime-v1"


class Group15AllocatorSideRuntimeVerifierTests(unittest.TestCase):
    def _write_tar(self, path: Path, payloads: dict[str, bytes]) -> None:
        with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
            for name, payload in sorted(payloads.items()):
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                info.mode = 0o644
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(payload))

    def _resign(self, artifact: Path, root: Path = ROOT) -> None:
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative in manifest["files"]:
            manifest["files"][relative] = hashlib.sha256(
                (artifact / relative).read_bytes()
            ).hexdigest()
        for relative in manifest["repository_files"]:
            manifest["repository_files"][relative] = hashlib.sha256(
                (root / relative).read_bytes()
            ).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_independent_verifier_accepts_production_artifact(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        source = inspect.getsource(verifier)
        self.assertNotIn("import export_battle_effect_group15", source)
        self.assertNotIn("from tools.export_battle_effect_group15", source)

        result = verifier.verify_artifact(ARTIFACT)

        self.assertEqual(result["errors"], [])
        self.assertEqual(result["selector_valid_sides"], [0, 1])
        self.assertEqual(result["target_task_sides"], [1])
        self.assertEqual(result["target_task_slot"], 108)
        self.assertEqual(result["visible_target_oam_binding_count"], 0)

    def test_independent_probe_reconstruction_locks_the_recorded_rom_hashes(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        base = (ROOT / "rom/base.gba").read_bytes()
        side0 = verifier.build_expected_probe(base, side=0)
        side1 = verifier.build_expected_probe(base, side=1)
        differences = [
            index
            for index, pair in enumerate(zip(side0, side1, strict=True))
            if pair[0] != pair[1]
        ]

        self.assertEqual(differences, [verifier.SIDE_OPCODE_OFFSET])
        evidence = json.loads((ARTIFACT / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [row["rom_sha256"] for row in evidence["cases"]],
            [hashlib.sha256(side0).hexdigest(), hashlib.sha256(side1).hexdigest()],
        )

    def test_independent_no_reset_probe_reconstruction_locks_parent_baseline(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        base = (ROOT / "rom/base.gba").read_bytes()

        probe = verifier.build_expected_no_reset_probe(base)

        self.assertEqual(
            hashlib.sha256(probe).hexdigest(), verifier.PARENT_GROUP15_PROBE_SHA256
        )

    def test_archive_and_single_variable_contract_are_exact(self):
        manifest = json.loads((ARTIFACT / "manifest.json").read_text(encoding="utf-8"))
        evidence = json.loads((ARTIFACT / "evidence.json").read_text(encoding="utf-8"))

        self.assertEqual(set(manifest["files"]), {"evidence.json", "raw-batch.tar"})
        self.assertEqual(evidence["archive"]["member_count"], 113)
        self.assertEqual(evidence["side_ab"]["rom_byte_difference_count"], 1)
        self.assertEqual(evidence["side_ab"]["difference_address"], "0x0809E852")

    def test_resource_payloads_and_guard_chain_are_hash_locked(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        self.assertTrue({
            "group15_graphics", "group15_palette", "toolchain_profile",
            "capture_script",
        } <= set(verifier.TRUSTED_SOURCE_SHA256))
        self.assertTrue({
            "tools/run_macos_mgba_battle_effect_phase_capture.py",
            "tools/macos_mgba_runtime_residue.py",
            "tools/run_guarded.py",
            "tools/mgba_runtime_safety.py",
            "tools/project_resource_guard.py",
        } <= set(verifier.REPOSITORY_FILES))

    def test_rejects_resigned_resource_identity_record(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["sources"]["group15_graphics"]["sha256"] = "0" * 64
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._resign(artifact)

            result = verifier.verify_artifact(artifact)

            self.assertFalse(result["verified"])
            self.assertTrue(any("source record mismatch" in error for error in result["errors"]))

    def test_rejects_replaced_resource_even_when_catalog_and_artifact_are_resigned(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        original_root = verifier.ROOT
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            for relative in set(verifier.SOURCE_PATHS.values()) | set(
                verifier.REPOSITORY_FILES
            ):
                source = ROOT / relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            parent_relative = Path(verifier.PARENT_CONTROLLED_ROOT)
            shutil.copytree(
                ROOT / parent_relative,
                root / parent_relative,
                dirs_exist_ok=True,
            )
            artifact = root / "candidate"
            shutil.copytree(ARTIFACT, artifact)
            graphics_path = root / verifier.SOURCE_PATHS["group15_graphics"]
            graphics_path.write_bytes(graphics_path.read_bytes() + b"tampered")
            graphics_hash = hashlib.sha256(graphics_path.read_bytes()).hexdigest()
            catalog_path = root / verifier.SOURCE_PATHS["resource_catalog"]
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            group = next(row for row in catalog["entries"] if row["group_id"] == 15)
            group["graphics"]["decompressed_sha256"] = graphics_hash
            catalog_path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            for name in ("group15_graphics", "resource_catalog"):
                source_path = root / verifier.SOURCE_PATHS[name]
                evidence["sources"][name] = {
                    "path": verifier.SOURCE_PATHS[name],
                    "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    "size": source_path.stat().st_size,
                }
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._resign(artifact, root)
            verifier.ROOT = root
            try:
                result = verifier.verify_artifact(artifact)
            finally:
                verifier.ROOT = original_root

            self.assertFalse(result["verified"])
            self.assertTrue(any("trusted source hash" in error for error in result["errors"]))

    def test_rejects_resigned_allocator_baseline_inflation(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["allocator_reset_ab"]["no_reset_selector_results"] = [0, 0, 0, 0]
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._resign(artifact)

            result = verifier.verify_artifact(artifact)

            self.assertFalse(result["verified"])
            self.assertTrue(any("allocator reset A/B" in error for error in result["errors"]))

    def test_rejects_resigned_runtime_binary_provenance(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            archive_path = artifact / "raw-batch.tar"
            payloads = verifier.read_safe_tar(archive_path)
            case_id = "group-15-sequence-17-reset-side-0"
            audit_member = f"source/{case_id}/output/audit.json"
            audit = json.loads(payloads[audit_member].decode("utf-8"))
            audit["binary_sha256"] = "0" * 64
            payloads[audit_member] = (
                json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            audit_hash = hashlib.sha256(payloads[audit_member]).hexdigest()
            batch_member = "source/batch-audit.json"
            batch = json.loads(payloads[batch_member].decode("utf-8"))
            batch["cases"][0]["audit_sha256"] = audit_hash
            payloads[batch_member] = (
                json.dumps(batch, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            self._write_tar(archive_path, payloads)
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["cases"][0]["audit_sha256"] = audit_hash
            evidence["archive"]["sha256"] = hashlib.sha256(
                archive_path.read_bytes()
            ).hexdigest()
            evidence["archive"]["size"] = archive_path.stat().st_size
            for member in (audit_member, batch_member):
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
            self.assertTrue(any("runtime audit provenance" in error for error in result["errors"]))

    def test_rejects_resigned_task_scope_inflation(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["coverage"]["visible_target_oam_binding_count"] = 1
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._resign(artifact)

            result = verifier.verify_artifact(artifact)

            self.assertFalse(result["verified"])
            self.assertTrue(any("visible target OAM" in error for error in result["errors"]))

    def test_rejects_resigned_raw_output_that_disagrees_with_runtime_audit(self):
        verifier = importlib.import_module(
            "tools.verify_battle_effect_group15_allocator_side_runtime"
        )
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            archive_path = artifact / "raw-batch.tar"
            payloads = verifier.read_safe_tar(archive_path)
            member = (
                "source/group-15-sequence-17-reset-side-0/"
                "output/renderer-post/capture.png"
            )
            payloads[member] += b"tampered"
            self._write_tar(archive_path, payloads)
            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["archive"]["sha256"] = hashlib.sha256(
                archive_path.read_bytes()
            ).hexdigest()
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
            self.assertTrue(any("runtime audit file hash" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
