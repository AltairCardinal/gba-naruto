from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
BASELINE_ARTIFACT = Path(
    "artifacts/rom-m4a-initializer-chain-precoverage-v1"
)
EXPORTER_NAME = "tools.export_rom_m4a_initializer_chain"
VERIFIER_NAME = "tools.verify_rom_m4a_initializer_chain"


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _load(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


class M4aInitializerChainVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter = _load(EXPORTER_NAME)
        cls.verifier = _load(VERIFIER_NAME)

    def _implemented(self):
        self.assertIsNotNone(self.verifier, "m4a initializer-chain verifier is absent")
        self.assertIsNotNone(self.exporter, "m4a initializer-chain exporter is absent")
        return self.exporter, self.verifier

    @staticmethod
    def _frozen_receipt(verifier):
        return {
            "path": verifier.COVERAGE_PATH.as_posix(),
            "schema": "rom-byte-coverage-v1",
            "sha256": verifier.COVERAGE_SHA256,
            "summary": dict(verifier.COVERAGE_SUMMARY),
            "promotion_bytes": 518,
            "unknown_promotion_bytes": 518,
            "primary_overlap_bytes": 0,
            "all_promotion_bytes_unknown": True,
            "target_segments": [
                {
                    "range": list(interval),
                    "primary_class": "unknown",
                    "primary_claim_ids": [],
                }
                for interval in verifier.PROMOTION_RANGES
            ],
        }

    def _frozen_exporter_coverage(self, exporter, verifier):
        return mock.patch.object(
            exporter,
            "_coverage_baseline",
            side_effect=lambda _root: json.loads(
                json.dumps(self._frozen_receipt(verifier))
            ),
        )

    def _frozen_verifier_coverage(self, verifier):
        return mock.patch.object(
            verifier,
            "_load_coverage",
            side_effect=lambda _root: json.loads(
                json.dumps(self._frozen_receipt(verifier))
            ),
        )

    def _independent_with_refreshed_raw_receipts(self, verifier, changed: bytes):
        range_hashes = [
            hashlib.sha256(changed[start:end]).hexdigest()
            for start, end in verifier.PROMOTION_RANGES
        ]
        packed = b"".join(changed[start:end] for start, end in verifier.PROMOTION_RANGES)
        with (
            mock.patch.object(verifier, "ROM_SHA256", hashlib.sha256(changed).hexdigest()),
            mock.patch.object(verifier, "PROMOTION_RANGE_SHA256", range_hashes),
            mock.patch.object(verifier, "PACKED_SHA256", hashlib.sha256(packed).hexdigest()),
            self._frozen_verifier_coverage(verifier),
        ):
            return verifier.independent_rebuild(ROOT, changed)

    def test_verifier_is_independent_and_rebuilds_raw_cfg(self) -> None:
        exporter, verifier = self._implemented()
        source = (ROOT / "tools/verify_rom_m4a_initializer_chain.py").read_text(encoding="utf-8")
        self.assertNotIn("import tools.export_rom_m4a_initializer_chain", source)
        self.assertNotIn("from tools.export_rom_m4a_initializer_chain", source)
        with (
            self._frozen_verifier_coverage(verifier),
            self._frozen_exporter_coverage(exporter, verifier),
        ):
            rebuilt = verifier.independent_rebuild(ROOT, self.rom)
            payload, bundle = exporter.build_payload(ROOT)
        self.assertEqual(rebuilt["summary"], payload["summary"])
        self.assertEqual(rebuilt["bundle_sha256"], hashlib.sha256(bundle).hexdigest())
        self.assertEqual(rebuilt["producer_denominator"], payload["producer_denominator"])
        self.assertEqual(rebuilt["literal_bindings"], payload["literal_bindings"])
        self.assertTrue(rebuilt["contract_ok"])

    def test_candidate_requires_opt_in_and_verifies_from_candidate_bytes(self) -> None:
        exporter, verifier = self._implemented()
        with (
            tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as raw,
            self._frozen_exporter_coverage(exporter, verifier),
            self._frozen_verifier_coverage(verifier),
        ):
            candidate = Path(raw) / "candidate"
            exporter.write_candidate(ROOT, candidate)
            with self.assertRaisesRegex(ValueError, "opt-in"):
                verifier.verify_artifact(ROOT, candidate)
            report = verifier.verify_artifact(ROOT, candidate, allow_candidate=True)
            self.assertTrue(report["verified"])
            self.assertTrue(report["contract_ok"])
            self.assertEqual(report["summary"]["promoted_bytes"], 518)
            with self.assertRaisesRegex(TypeError, "_use_frozen_coverage"):
                verifier.verify_artifact(
                    ROOT,
                    candidate,
                    allow_candidate=True,
                    _use_frozen_coverage=True,
                )

    def test_explicit_precoverage_cli_is_replayable_and_default_stays_closed(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as raw:
            candidate = Path(raw) / "candidate"
            accepted = Path(raw) / "accepted"
            candidate_relative = candidate.relative_to(ROOT).as_posix()
            accepted_relative = accepted.relative_to(ROOT).as_posix()
            baseline_relative = BASELINE_ARTIFACT.as_posix()

            export_command = [
                "python3",
                "tools/export_rom_m4a_initializer_chain.py",
                "--coverage-baseline-artifact",
                baseline_relative,
                "--output",
                candidate_relative,
            ]
            exported = subprocess.run(
                export_command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, exported.returncode, exported.stderr + exported.stdout)

            default_verify = subprocess.run(
                [
                    "python3",
                    "tools/verify_rom_m4a_initializer_chain.py",
                    candidate_relative,
                    "--allow-candidate",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, default_verify.returncode)
            self.assertIn("coverage baseline identity", default_verify.stdout)

            verify_command = [
                "python3",
                "tools/verify_rom_m4a_initializer_chain.py",
                candidate_relative,
                "--allow-candidate",
                "--coverage-baseline-artifact",
                baseline_relative,
            ]
            verified = subprocess.run(
                verify_command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, verified.returncode, verified.stderr + verified.stdout)

            accept_command = [
                "python3",
                "tools/verify_rom_m4a_initializer_chain.py",
                candidate_relative,
                "--coverage-baseline-artifact",
                baseline_relative,
                "--accept-to",
                accepted_relative,
            ]
            accepted_run = subprocess.run(
                accept_command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                0,
                accepted_run.returncode,
                accepted_run.stderr + accepted_run.stdout,
            )
            accepted_verify = subprocess.run(
                [
                    "python3",
                    "tools/verify_rom_m4a_initializer_chain.py",
                    accepted_relative,
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                0,
                accepted_verify.returncode,
                accepted_verify.stderr + accepted_verify.stdout,
            )

            manifest = json.loads(
                (accepted / exporter.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(
                [
                    "python3",
                    "tools/export_rom_m4a_initializer_chain.py",
                    "--coverage-baseline-artifact",
                    baseline_relative,
                    "--output",
                    (accepted / "candidate").relative_to(ROOT).as_posix(),
                ],
                manifest["producer"]["command"],
            )
            self.assertEqual(accept_command, manifest["acceptance"]["command"])
            self.assertEqual(
                baseline_relative,
                manifest["coverage_baseline_source"]["artifact"],
            )

    def test_absolute_baseline_acceptance_normalizes_receipts(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as raw:
            candidate = Path(raw) / "candidate"
            accepted = Path(raw) / "accepted"
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=BASELINE_ARTIFACT,
            )
            report = verifier.accept_candidate(
                ROOT,
                candidate,
                accepted,
                coverage_baseline_artifact=ROOT / BASELINE_ARTIFACT,
            )
            self.assertEqual("accepted", report["artifact_status"])
            manifest = json.loads(
                (accepted / exporter.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            for receipt in (
                manifest["producer"]["command"],
                manifest["acceptance"]["command"],
            ):
                self.assertIn(BASELINE_ARTIFACT.as_posix(), receipt)
                self.assertNotIn(str(ROOT / BASELINE_ARTIFACT), receipt)

    def test_failed_final_acceptance_check_leaves_no_target(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as raw:
            candidate = Path(raw) / "candidate"
            accepted = Path(raw) / "accepted"
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=BASELINE_ARTIFACT,
            )
            candidate_report = verifier.verify_artifact(
                ROOT,
                candidate,
                allow_candidate=True,
                coverage_baseline_artifact=BASELINE_ARTIFACT,
            )
            with mock.patch.object(
                verifier,
                "verify_artifact",
                side_effect=[
                    candidate_report,
                    ValueError("forced final acceptance verification failure"),
                ],
            ):
                with self.assertRaisesRegex(ValueError, "forced final"):
                    verifier.accept_candidate(
                        ROOT,
                        candidate,
                        accepted,
                        coverage_baseline_artifact=BASELINE_ARTIFACT,
                    )
            self.assertFalse(
                accepted.exists(),
                "failed acceptance must not leave a published target",
            )

    def test_precoverage_artifact_outer_receipts_and_symlinks_fail_closed(self) -> None:
        _, verifier = self._implemented()
        source = ROOT / BASELINE_ARTIFACT
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as raw:
            fixture_root = Path(raw)
            fixture = fixture_root / BASELINE_ARTIFACT
            fixture.parent.mkdir(parents=True)
            shutil.copytree(source, fixture)

            archive = fixture / verifier.PRE_COVERAGE_ARCHIVE_NAME
            changed = bytearray(archive.read_bytes())
            changed[0] ^= 1
            archive.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "archive identity"):
                verifier._load_coverage_from_artifact(
                    fixture_root, BASELINE_ARTIFACT
                )

            shutil.rmtree(fixture)
            shutil.copytree(source, fixture)
            manifest = fixture / verifier.PRE_COVERAGE_MANIFEST_NAME
            manifest.write_bytes(manifest.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "manifest identity"):
                verifier._load_coverage_from_artifact(
                    fixture_root, BASELINE_ARTIFACT
                )

            shutil.rmtree(fixture)
            shutil.copytree(source, fixture)
            archive = fixture / verifier.PRE_COVERAGE_ARCHIVE_NAME
            archive.unlink()
            archive.symlink_to(source / verifier.PRE_COVERAGE_ARCHIVE_NAME)
            with self.assertRaisesRegex(ValueError, "symlink"):
                verifier._load_coverage_from_artifact(
                    fixture_root, BASELINE_ARTIFACT
                )

            with self.assertRaisesRegex(ValueError, "identity|escapes"):
                verifier._load_coverage_from_artifact(
                    fixture_root, Path("../outside-baseline")
                )

    def test_candidate_cannot_self_promote_and_independent_acceptance_verifies(self) -> None:
        exporter, verifier = self._implemented()
        with (
            tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as raw,
            self._frozen_exporter_coverage(exporter, verifier),
            self._frozen_verifier_coverage(verifier),
        ):
            candidate = Path(raw) / "candidate"
            accepted = Path(raw) / "accepted"
            exporter.write_candidate(ROOT, candidate)

            manifest_path = candidate / exporter.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifact_status"] = "accepted"
            manifest_path.write_bytes(_canonical(manifest))
            with self.assertRaisesRegex(ValueError, "acceptance|accepted|manifest"):
                verifier.verify_artifact(ROOT, candidate)

            shutil.rmtree(candidate)
            exporter.write_candidate(ROOT, candidate)
            manifest_path = candidate / exporter.MANIFEST_NAME
            candidate_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            missing_candidate = (Path(raw) / "missing-candidate").relative_to(ROOT).as_posix()
            output_artifact = candidate.relative_to(ROOT).as_posix()
            candidate_manifest["producer"] = {
                "kind": "artifact-candidate-construction",
                "output_artifact": missing_candidate,
                "command": [
                    "python3", "tools/export_rom_m4a_initializer_chain.py",
                    "--output", missing_candidate,
                ],
            }
            acceptance_command = [
                "python3", "tools/verify_rom_m4a_initializer_chain.py",
                missing_candidate, "--accept-to", output_artifact,
            ]
            candidate_identity = {
                "artifact_status": "candidate",
                "manifest_sha256": hashlib.sha256(_canonical(candidate_manifest)).hexdigest(),
                "payload_sha256": candidate_manifest["files"][exporter.PAYLOAD_NAME]["sha256"],
                "bundle_sha256": candidate_manifest["files"][exporter.BUNDLE_NAME]["sha256"],
            }
            forged = dict(candidate_manifest)
            forged["artifact_status"] = "accepted"
            forged["acceptance"] = {
                "kind": "independent-candidate-acceptance",
                "candidate_artifact": missing_candidate,
                "output_artifact": output_artifact,
                "command": acceptance_command,
                "candidate_identity": candidate_identity,
            }
            forged["verifier"] = {
                "path": "tools/verify_rom_m4a_initializer_chain.py",
                "sha256": hashlib.sha256((ROOT / "tools/verify_rom_m4a_initializer_chain.py").read_bytes()).hexdigest(),
                "command": acceptance_command,
            }
            forged["verification"] = {
                "status": "verified",
                "contract_ok": True,
                "schema": verifier.VERIFY_SCHEMA,
                "summary": candidate_manifest["summary"],
            }
            manifest_path.write_bytes(_canonical(forged))
            with self.assertRaisesRegex((OSError, ValueError), "candidate|artifact|exist"):
                verifier.verify_artifact(ROOT, candidate)

            shutil.rmtree(candidate)
            exporter.write_candidate(ROOT, candidate)
            report = verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertEqual(report["artifact_status"], "accepted")
            self.assertTrue(report["contract_ok"])
            self.assertEqual(verifier.verify_artifact(ROOT, accepted)["artifact_status"], "accepted")
            accepted_manifest = json.loads((accepted / exporter.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(accepted_manifest["acceptance"]["kind"], "independent-candidate-acceptance")
            self.assertEqual(accepted_manifest["acceptance"]["candidate_identity"]["artifact_status"], "candidate")
            self.assertEqual(
                accepted_manifest["acceptance"]["candidate_artifact"],
                (accepted / "candidate").relative_to(ROOT).as_posix(),
            )
            self.assertTrue((accepted / "candidate" / exporter.MANIFEST_NAME).is_file())
            shutil.rmtree(candidate)
            self.assertEqual(
                verifier.verify_artifact(ROOT, accepted)["artifact_status"],
                "accepted",
                "accepted artifact must remain verifiable without ignored build/ evidence",
            )
            with mock.patch.object(
                verifier,
                "_load_coverage",
                side_effect=AssertionError(
                    "accepted artifact must not consult the mutable live coverage"
                ),
            ):
                self.assertEqual(
                    verifier.verify_artifact(ROOT, accepted)["artifact_status"],
                    "accepted",
                    "accepted artifact must remain verifiable after coverage advances",
                )

    def test_artifact_json_must_be_canonical_even_with_refreshed_receipt(self) -> None:
        exporter, verifier = self._implemented()
        with (
            tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as raw,
            self._frozen_exporter_coverage(exporter, verifier),
            self._frozen_verifier_coverage(verifier),
        ):
            candidate = Path(raw) / "candidate"
            exporter.write_candidate(ROOT, candidate)
            payload_path = candidate / exporter.PAYLOAD_NAME
            manifest_path = candidate / exporter.MANIFEST_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            changed = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            payload_path.write_bytes(changed)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][exporter.PAYLOAD_NAME] = {
                "size": len(changed),
                "sha256": hashlib.sha256(changed).hexdigest(),
            }
            manifest_path.write_bytes(_canonical(manifest))
            with self.assertRaisesRegex(ValueError, "canonical"):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)

    def test_payload_and_bundle_mutations_fail_even_with_refreshed_manifest_receipts(self) -> None:
        exporter, verifier = self._implemented()
        with (
            tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as raw,
            self._frozen_exporter_coverage(exporter, verifier),
            self._frozen_verifier_coverage(verifier),
        ):
            candidate = Path(raw) / "candidate"
            exporter.write_candidate(ROOT, candidate)
            payload_path = candidate / exporter.PAYLOAD_NAME
            manifest_path = candidate / exporter.MANIFEST_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["summary"]["instruction_count"] += 1
            changed = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
            payload_path.write_bytes(changed)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][exporter.PAYLOAD_NAME] = {"size": len(changed), "sha256": hashlib.sha256(changed).hexdigest()}
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)

            shutil.rmtree(candidate)
            exporter.write_candidate(ROOT, candidate)
            bundle_path = candidate / exporter.BUNDLE_NAME
            bundle = bytearray(bundle_path.read_bytes())
            bundle[0] ^= 1
            bundle_path.write_bytes(bundle)
            manifest = json.loads((candidate / exporter.MANIFEST_NAME).read_text(encoding="utf-8"))
            manifest["files"][exporter.BUNDLE_NAME] = {"size": len(bundle), "sha256": hashlib.sha256(bundle).hexdigest()}
            (candidate / exporter.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "raw-ROM|bundle|packed"):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)

    def test_raw_mutation_vectors_and_foreign_file_fail_closed(self) -> None:
        exporter, verifier = self._implemented()
        mutations = {
            0x09AA3C: b"\x00",
            0x09AA90: b"\x00",
            0x09ACF8: b"\x00",
            0x09ADC0: b"\x00",
            0x09B17C: b"\x00",
            0x09B1E8: b"\x00",
            0x09B1E6: b"\x01",
        }
        for offset, changed_byte in mutations.items():
            changed = bytearray(self.rom)
            changed[offset] ^= 1
            with self.subTest(offset=offset):
                changed = bytes(changed)
                with (
                    mock.patch.object(
                        verifier,
                        "ROM_SHA256",
                        hashlib.sha256(changed).hexdigest(),
                    ),
                    self._frozen_verifier_coverage(verifier),
                ):
                    with self.assertRaises(ValueError):
                        verifier.independent_rebuild(ROOT, changed)
        for offset, raw in (
            (0x09AA8E, b"\x00\x00"),  # structured return / stack epilogue
            (0x09AA68, b"\x00\xe0"),  # branch changes the frozen CFG
        ):
            changed = bytearray(self.rom)
            changed[offset : offset + len(raw)] = raw
            changed = bytes(changed)
            with self.subTest(structural_offset=offset):
                with self.assertRaises(ValueError):
                    self._independent_with_refreshed_raw_receipts(verifier, changed)

        changed = bytearray(self.rom)
        changed[0x09AA3E:0x09AA40] = b"\xff\x48"
        changed = bytes(changed)
        escaped_expectations = list(verifier.LITERAL_EXPECTATIONS)
        escaped_expectations[0] = (
            0x09AA3E, 0x09AE3C,
            int.from_bytes(changed[0x09AE3C:0x09AE40], "little"),
        )
        with mock.patch.object(verifier, "LITERAL_EXPECTATIONS", escaped_expectations):
            with self.assertRaisesRegex(ValueError, "escapes frozen pool"):
                self._independent_with_refreshed_raw_receipts(verifier, changed)

        changed = bytearray(self.rom)
        changed[0x09AA46:0x09AA48] = b"\x12\x49"
        changed = bytes(changed)
        hole_expectations = list(verifier.LITERAL_EXPECTATIONS)
        hole_expectations[1] = (
            0x09AA46, 0x09AA90,
            int.from_bytes(changed[0x09AA90:0x09AA94], "little"),
        )
        with mock.patch.object(verifier, "LITERAL_EXPECTATIONS", hole_expectations):
            with self.assertRaisesRegex(ValueError, "literal pool hole"):
                self._independent_with_refreshed_raw_receipts(verifier, changed)
        with (
            tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as raw,
            self._frozen_exporter_coverage(exporter, verifier),
            self._frozen_verifier_coverage(verifier),
        ):
            candidate = Path(raw) / "candidate"
            exporter.write_candidate(ROOT, candidate)
            (candidate / "foreign.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "file set"):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)


if __name__ == "__main__":
    unittest.main()
