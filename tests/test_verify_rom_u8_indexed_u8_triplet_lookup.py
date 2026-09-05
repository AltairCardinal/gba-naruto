"""Independent verifier and artifact fail-closed tests for the triplet candidate."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = ROOT / "build/experiments/active/rom-u8-indexed-u8-triplet-lookup"
JSON_NAME = "rom-u8-indexed-u8-triplet-lookup.json"
BIN_NAME = "rom-u8-indexed-u8-triplet-lookup.bin"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _temporary_experiment_dir():
    EXPERIMENT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=EXPERIMENT_ROOT)


class VerifyRomU8IndexedU8TripletLookupTests(unittest.TestCase):
    def _mods(self):
        try:
            from tools import export_rom_u8_indexed_u8_triplet_lookup as exporter
            from tools import verify_rom_u8_indexed_u8_triplet_lookup as verifier
        except ModuleNotFoundError as error:
            self.fail(f"required triplet product module missing: {error}")
        return exporter, verifier

    def test_red_verifier_module_is_required(self):
        """The verifier-side RED is explicit before implementation exists."""
        try:
            from tools import verify_rom_u8_indexed_u8_triplet_lookup as verifier
        except ModuleNotFoundError:
            self.fail("RED: verifier module is not implemented")
        self.assertTrue(hasattr(verifier, "verify_artifact"))

    def test_independent_rebuild_matches_exporter(self):
        exporter, verifier = self._mods()
        expected, bundle = exporter.build_payload(ROOT)
        rebuilt, rebuilt_bundle = verifier.rebuild_payload(ROOT)
        self.assertEqual(rebuilt, expected)
        self.assertEqual(rebuilt_bundle, bundle)
        self.assertNotIn("export_rom_u8_indexed_u8_triplet_lookup", verifier.__dict__)

    def test_artifact_mutations_fail_closed(self):
        exporter, verifier = self._mods()
        with _temporary_experiment_dir() as raw:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            self.assertTrue(verifier.verify_artifact(ROOT, artifact)["verified"])

            payload_path = artifact / JSON_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["promotion"]["byte_size"] = 20
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = verifier.verify_artifact(ROOT, artifact)
            self.assertFalse(report["verified"])

    def test_extra_member_and_noncanonical_manifest_fail_closed(self):
        exporter, verifier = self._mods()
        with _temporary_experiment_dir() as raw:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            (artifact / "extra.json").write_text("{}\n", encoding="utf-8")
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

        with _temporary_experiment_dir() as raw:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            (artifact / BIN_NAME).unlink()
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

        with _temporary_experiment_dir() as raw:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            target = artifact / "target.bin"
            target.write_bytes((artifact / BIN_NAME).read_bytes())
            (artifact / BIN_NAME).unlink()
            (artifact / BIN_NAME).symlink_to(target)
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

        with _temporary_experiment_dir() as raw:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
            (artifact / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_wrong_baseline_and_pool_or_right_gap_promotion_fail_closed(self):
        exporter, verifier = self._mods()
        with _temporary_experiment_dir() as raw:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
            manifest["coverage_baseline"]["sha256"] = "0" * 64
            (artifact / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

        with _temporary_experiment_dir() as raw:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            payload_path = artifact / JSON_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["promotion"]["ranges"] = [[0x75BFE, 0x75C10], [0x53DFBF, 0x53E000]]
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_report_receipt_and_command_drift_fail_closed(self):
        exporter, verifier = self._mods()
        with _temporary_experiment_dir() as raw:
            run = Path(raw)
            artifact = run / "candidate"
            report_path = run / "verify.report.json"
            exporter.export_artifact(ROOT, artifact)
            report = verifier.verify_artifact(ROOT, artifact)
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertTrue(verifier.main(["--root", str(ROOT), "--artifact-dir", str(artifact), "--report", str(report_path)]) == 0)
            report["promotion_bytes"] = 20
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertNotEqual(verifier.main(["--root", str(ROOT), "--artifact-dir", str(artifact), "--report", str(report_path)]), 0)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["reproduction_command"][-1] = "wrong"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_isolated_cli_and_manifest_reproduction_command_are_exact(self):
        exporter, _ = self._mods()
        with _temporary_experiment_dir() as raw, tempfile.TemporaryDirectory() as foreign:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["reproduction_command"][:4],
                [
                    "python3",
                    "-I",
                    "-S",
                    "tools/verify_rom_u8_indexed_u8_triplet_lookup.py",
                ],
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    str(ROOT / "tools/verify_rom_u8_indexed_u8_triplet_lookup.py"),
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    str(artifact),
                ],
                cwd=foreign,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_acceptance_receipt_is_exact_and_fails_closed(self):
        exporter, verifier = self._mods()
        with _temporary_experiment_dir() as raw:
            run = Path(raw)
            candidate = run / "candidate"
            accepted = run / "accepted"
            exporter.export_artifact(ROOT, candidate)
            real_run = subprocess.run
            with mock.patch.object(verifier.subprocess, "run", wraps=real_run) as isolated:
                report = verifier.accept_candidate(ROOT, candidate, accepted)
            isolated.assert_called_once()
            command = isolated.call_args.args[0]
            self.assertEqual(
                command[:4],
                [
                    "python3",
                    "-I",
                    "-S",
                    "tools/verify_rom_u8_indexed_u8_triplet_lookup.py",
                ],
            )
            self.assertEqual(Path(isolated.call_args.kwargs["cwd"]), ROOT)
            self.assertTrue(report["verified"])
            self.assertEqual(report["artifact_status"], "accepted")
            manifest_path = accepted / "manifest.json"
            original = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(original["artifact_status"], "accepted")
            self.assertEqual(original["verification"], original["verifier"])
            self.assertEqual(original["verification"]["exit_code"], 0)
            self.assertEqual(original["verification"]["report"], report)
            self.assertEqual(
                original["verification"]["command"][:4],
                [
                    "python3",
                    "-I",
                    "-S",
                    "tools/verify_rom_u8_indexed_u8_triplet_lookup.py",
                ],
            )
            for field in ("command", "exit_code", "report"):
                with self.subTest(field=field):
                    changed = json.loads(json.dumps(original))
                    if field == "command":
                        changed["verification"][field][-1] = "wrong"
                    elif field == "exit_code":
                        changed["verification"][field] = 1
                    else:
                        changed["verification"][field]["promotion_bytes"] = 20
                    manifest_path.write_text(
                        json.dumps(changed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    self.assertFalse(verifier.verify_artifact(ROOT, accepted)["verified"])
            manifest_path.write_text(
                json.dumps(original, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def test_failed_isolated_acceptance_leaves_no_target(self):
        exporter, verifier = self._mods()
        with _temporary_experiment_dir() as raw:
            run = Path(raw)
            candidate = run / "candidate"
            accepted = run / "accepted"
            exporter.export_artifact(ROOT, candidate)
            failed = mock.Mock(returncode=7, stdout="", stderr="forced verifier failure")
            with mock.patch.object(verifier.subprocess, "run", return_value=failed):
                with self.assertRaisesRegex(ValueError, "isolated|verifier|accept"):
                    verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertFalse(accepted.exists())

    def test_report_output_cannot_overwrite_an_artifact_member(self):
        exporter, verifier = self._mods()
        with _temporary_experiment_dir() as raw:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            manifest_path = artifact / "manifest.json"
            before = manifest_path.read_bytes()
            result = verifier.main(
                [
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    str(artifact),
                    "--output",
                    str(manifest_path),
                ]
            )
            self.assertNotEqual(result, 0)
            self.assertEqual(manifest_path.read_bytes(), before)

    def test_acceptance_report_cannot_overwrite_source_candidate(self):
        exporter, verifier = self._mods()
        with _temporary_experiment_dir() as raw:
            run = Path(raw)
            candidate = run / "candidate"
            accepted = run / "accepted"
            exporter.export_artifact(ROOT, candidate)
            manifest_path = candidate / "manifest.json"
            before = manifest_path.read_bytes()
            result = verifier.main(
                [
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    str(candidate),
                    "--accept-to",
                    str(accepted),
                    "--output",
                    str(manifest_path),
                ]
            )
            self.assertNotEqual(result, 0)
            self.assertEqual(manifest_path.read_bytes(), before)
            self.assertFalse(accepted.exists())

    def test_accepted_artifact_verifies_exact_pre_and_post_coverage_states(self):
        exporter, verifier = self._mods()
        from tools import audit_rom_byte_coverage as coverage_auditor

        with _temporary_experiment_dir() as raw:
            run = Path(raw)
            candidate = run / "candidate"
            accepted = run / "accepted"
            exporter.export_artifact(ROOT, candidate)
            verifier.accept_candidate(ROOT, candidate, accepted)
            payload = json.loads((accepted / JSON_NAME).read_text(encoding="utf-8"))
            manifest_raw = (accepted / "manifest.json").read_bytes()
            manifest = json.loads(manifest_raw)
            expected_claims = verifier.expected_coverage_claims(
                payload,
                manifest,
                manifest_sha256=_sha(manifest_raw),
            )
            self.assertEqual(
                [
                    "fixed-consumer-triplet-pointer-literal",
                    "fixed-consumer-triplet-records",
                ],
                [claim["id"] for claim in expected_claims],
            )
            self.assertEqual(
                [[0x075C0C, 0x075C10], [0x53DFB0, 0x53DFBF]],
                [claim["range"] for claim in expected_claims],
            )
            baseline = json.loads(
                (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
            )
            post = copy.deepcopy(baseline)
            post["claims"].extend(copy.deepcopy(expected_claims))
            post["claims"].sort(key=lambda claim: (claim["range"], claim["id"]))
            post["segments"] = coverage_auditor.atomize_claims(
                6_291_456,
                post["claims"],
            )
            post["summary"].update(
                {
                    "classified_bytes": 6_121_869,
                    "unknown_bytes": 169_587,
                    "claim_count": 14_478,
                    "segment_count": 16_591,
                    "u8_indexed_u8_triplet_lookup_promotion_batch": verifier.SCHEMA,
                    "u8_indexed_u8_triplet_lookup_bytes": 19,
                    "u8_indexed_u8_triplet_lookup_claim_count": 2,
                    "u8_indexed_u8_triplet_lookup_range_vector_sha256": verifier.PROMOTION_RANGE_VECTOR_SHA256,
                    "u8_indexed_u8_triplet_lookup_packed_bytes_sha256": verifier.PROMOTION_PACKED_SHA256,
                    "u8_indexed_u8_triplet_lookup_class_bytes": {
                        "fixed_consumer_triplet_pointer_literal": 4,
                        "fixed_consumer_triplet_table": 15,
                    },
                    "u8_indexed_u8_triplet_lookup_class_claim_counts": {
                        "fixed_consumer_triplet_pointer_literal": 1,
                        "fixed_consumer_triplet_table": 1,
                    },
                    "u8_indexed_u8_triplet_lookup_pointer_occurrence_count": 1,
                    "u8_indexed_u8_triplet_lookup_table_record_count": 5,
                    "u8_indexed_u8_triplet_lookup_index_domain": [0, 4],
                    "u8_indexed_u8_triplet_lookup_consumer_instruction_provenance_count": 134,
                    "u8_indexed_u8_triplet_lookup_consumer_block_provenance_count": 28,
                }
            )
            post["limitations"].append(verifier.COVERAGE_LIMITATION)
            self.assertEqual(16_591, len(post["segments"]))
            self.assertEqual(
                "66800eb89254d07e1eeba23d7b14ecc763bfcd888f13072560d777400759b31d",
                _sha(verifier._canonical(post["segments"])),
            )
            self.assertEqual(
                "3aaa7f345d1b49a9db140c55e7dfdc3aecc6a54a1ed346bbed5af9ab84135018",
                _sha(verifier._canonical(post["summary"])),
            )
            self.assertEqual(
                "768236648c3f6eb45677715fb62eda7cec6b5c3bedec79a76e1767dc1950f656",
                _sha(verifier._canonical(post["limitations"])),
            )
            pre_result = verifier.analyze_live_coverage(
                baseline,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )
            post_result = verifier.analyze_live_coverage(
                post,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )
            self.assertEqual(pre_result, post_result)
            with mock.patch.object(
                verifier,
                "_read_live_coverage",
                return_value=(verifier._canonical(post), post),
            ):
                report = verifier.verify_artifact(ROOT, accepted)
            self.assertTrue(report["verified"])
            self.assertEqual("accepted", report["artifact_status"])

            drifted = copy.deepcopy(post)
            for claim in drifted["claims"]:
                if claim.get("id") == expected_claims[0]["id"]:
                    claim["claim_kind"] = "forged"
                    break
            with self.assertRaisesRegex(ValueError, "coverage|claim|post"):
                verifier.analyze_live_coverage(
                    drifted,
                    artifact_status="accepted",
                    expected_claims=expected_claims,
                )

    def test_unsafe_artifact_path_is_rejected(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as raw:
            outside = Path(raw) / "candidate"
            with self.assertRaises(ValueError):
                exporter.export_artifact(ROOT, outside)
            self.assertFalse(verifier.verify_artifact(ROOT, outside)["verified"])

    def test_report_symlink_parent_is_rejected(self):
        exporter, verifier = self._mods()
        with _temporary_experiment_dir() as raw:
            run = Path(raw)
            link = run / "link"
            link.symlink_to(Path("/tmp"), target_is_directory=True)
            with self.assertRaises(ValueError):
                verifier._safe_report_path(ROOT, link / "report.json")

        with _temporary_experiment_dir() as raw:
            artifact = Path(raw) / "candidate"
            exporter.export_artifact(ROOT, artifact)
            payload_path = artifact / JSON_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["promotion"]["ranges"].append([0x53DFBF, 0x53E000])
            payload_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])
