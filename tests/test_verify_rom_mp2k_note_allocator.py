from __future__ import annotations

import ast
import gzip
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
EXPERIMENT = ROOT / "build/experiments/active/mp2k-note-allocator-contract-20260829"
RANGES = [[0x09A6D8, 0x09A708], [0x09A708, 0x09A8FE], [0x09A900, 0x09A908], [0x09AF24, 0x09AF28]]
PACKED_SHA256 = "3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c"
UNION_VECTOR_SHA256 = "bd9139f26305fea7813e7daf944d6a6e131861b31c3c98065b5e7d13bf65c88b"
PROJECTED_TOTALS = {"classified_bytes": 6_124_499, "unknown_bytes": 166_957, "claim_count": 14_503, "segment_count": 16_614}


def _load(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


def _archive_fixture(directory: Path) -> Path:
    directory.mkdir()
    coverage_raw = (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
    archive_raw = gzip.compress(coverage_raw, mtime=0)
    (directory / "rom-byte-coverage.json.gz").write_bytes(archive_raw)
    manifest = {
        "schema": "rom-byte-coverage-prepromotion-baseline-v1",
        "artifact_status": "accepted",
        "coverage": {
            "raw": {
                "canonical_json": True,
                "schema": "rom-byte-coverage-v1",
                "sha256": hashlib.sha256(coverage_raw).hexdigest(),
                "size": len(coverage_raw),
                "summary": {"classified_bytes": 6_123_937, "unknown_bytes": 167_519, "claim_count": 14_499, "segment_count": 16_608},
            },
            "archive": {
                "compression": "gzip",
                "file": "rom-byte-coverage.json.gz",
                "sha256": hashlib.sha256(archive_raw).hexdigest(),
                "size": len(archive_raw),
            },
        },
        "recovery": {"kind": "frozen-prepromotion-baseline"},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return directory


class Mp2kNoteAllocatorVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter = _load("tools.export_rom_mp2k_note_allocator")
        cls.verifier = _load("tools.verify_rom_mp2k_note_allocator")

    def _implemented(self):
        self.assertIsNotNone(self.exporter, "MP2K note allocator exporter is absent")
        self.assertIsNotNone(self.verifier, "MP2K note allocator verifier is absent")
        return self.exporter, self.verifier

    def _candidate(self, directory: Path):
        exporter, _ = self._implemented()
        target = directory / "candidate"
        exporter.write_candidate(ROOT, target)
        return target

    def test_independent_rebuild_matches_contract_and_source_is_standalone(self) -> None:
        exporter, verifier = self._implemented()
        evidence = verifier.independent_rebuild(ROOT, (ROOT / "rom/base.gba").read_bytes())
        self.assertTrue(evidence["verified"])
        self.assertTrue(evidence["contract_ok"])
        self.assertEqual(evidence["schema"], "rom-mp2k-note-allocator-verification-v1")
        self.assertEqual(evidence["summary"]["instruction_count"], 269)
        self.assertEqual(evidence["summary"]["instruction_bytes"], 550)
        self.assertEqual(evidence["summary"]["block_count"], 66)
        self.assertEqual(evidence["summary"]["internal_edge_count"], 99)
        self.assertEqual(evidence["summary"]["frontier_count"], 0)
        self.assertEqual(evidence["bundle_sha256"], PACKED_SHA256)
        self.assertEqual(evidence["payload"]["promotion"]["range_vector_sha256"], UNION_VECTOR_SHA256)
        self.assertEqual(evidence["payload"]["coverage_projection"]["post"], PROJECTED_TOTALS)
        self.assertEqual(evidence["producer_denominator"]["producer_roles"][0], {
            "target_offset": 0x09A6D8,
            "form": "thumb_bl",
            "source_offset": 0x09A60C,
            "role": "preowned_provenance",
            "owner_claim_id": "mplaymain-code-00-09a42c",
            "promoted": False,
        })
        self.assertEqual(evidence["payload"]["entry_pointer"]["writer"]["owner_range"], [0x09AE3C, 0x09AEF4])
        self.assertEqual(evidence["payload"]["entry_pointer"]["writer"]["owner_claim_id"], "bank-sappy-engine-000")
        source = (ROOT / "tools/verify_rom_mp2k_note_allocator.py").read_text()
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(any("capstone" in name.lower() for name in imported))
        self.assertFalse(any("export_rom_mp2k_note_allocator" in name for name in imported))
        self.assertIn("raw Thumb", source)
        self.assertIn("coverage_claims", source)
        self.assertIn("table_offset", source)
        self.assertIn("entry_size", source)

    def test_candidate_is_independently_accepted_once_and_report_is_complete(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            candidate = self._candidate(Path(raw))
            report = verifier.verify_artifact(ROOT, candidate, allow_candidate=True)
            self.assertTrue(report["verified"])
            self.assertTrue(report["contract_ok"])
            self.assertEqual(report["artifact_status"], "candidate")
            self.assertEqual(report["bundle_sha256"], PACKED_SHA256)
            self.assertEqual(report["summary"]["promoted_bytes"], 562)
            self.assertEqual(report["summary"]["external_edge_count"], 5)
            self.assertFalse(report["scope"]["natural_runtime_reachability"])
            self.assertFalse(report["scope"]["global_ram_writer_denominator_complete"])
            self.assertEqual(report["limitations"], json.loads((candidate / "rom-mp2k-note-allocator.json").read_text())["limitations"])

    def test_candidate_cannot_self_promote_and_accepted_artifact_is_portable(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            raw_dir = Path(raw)
            archive = _archive_fixture(raw_dir / "precoverage")
            archive_relative = archive.relative_to(ROOT)
            candidate = raw_dir / "candidate"
            accepted = raw_dir / "accepted"
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=archive_relative,
            )

            manifest_path = candidate / exporter.MANIFEST_NAME
            forged = json.loads(manifest_path.read_text())
            forged["artifact_status"] = "accepted"
            manifest_path.write_text(json.dumps(forged, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "acceptance|accepted|candidate|manifest"):
                verifier.verify_artifact(ROOT, candidate)

            shutil.rmtree(candidate)
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=archive_relative,
            )
            report = verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertEqual(report["artifact_status"], "accepted")
            self.assertTrue(report["verified"])
            self.assertTrue(report["contract_ok"])
            manifest = json.loads((accepted / exporter.MANIFEST_NAME).read_text())
            self.assertEqual(manifest["acceptance"]["kind"], "independent-candidate-acceptance")
            self.assertEqual(
                manifest["acceptance"]["candidate_artifact"],
                (accepted / "candidate").relative_to(ROOT).as_posix(),
            )
            self.assertEqual(
                manifest["coverage_baseline_source"]["artifact"],
                archive_relative.as_posix(),
            )
            self.assertTrue((accepted / "candidate" / exporter.MANIFEST_NAME).is_file())

            shutil.rmtree(candidate)
            with mock.patch.object(
                verifier,
                "_coverage_from_file",
                side_effect=AssertionError("accepted artifact consulted live coverage"),
            ):
                self.assertEqual(
                    verifier.verify_artifact(ROOT, accepted)["artifact_status"],
                    "accepted",
                )
            with self.assertRaisesRegex(ValueError, "accepted artifact|external coverage"):
                verifier.verify_artifact(
                    ROOT,
                    accepted,
                    coverage_baseline_artifact=archive_relative,
                )

            missing_embedded = raw_dir / "accepted-missing-embedded"
            shutil.copytree(accepted, missing_embedded)
            shutil.rmtree(missing_embedded / "candidate")
            with self.assertRaisesRegex(ValueError, "embedded candidate|candidate"):
                verifier.verify_artifact(ROOT, missing_embedded)

    def test_acceptance_cli_records_normalized_receipts(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            raw_dir = Path(raw)
            archive = _archive_fixture(raw_dir / "precoverage")
            archive_relative = archive.relative_to(ROOT)
            candidate = raw_dir / "candidate"
            accepted = raw_dir / "accepted"
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=archive_relative,
            )
            candidate_relative = candidate.relative_to(ROOT).as_posix()
            accepted_relative = accepted.relative_to(ROOT).as_posix()
            command = [
                "python3",
                "tools/verify_rom_mp2k_note_allocator.py",
                candidate_relative,
                "--accept-to",
                accepted_relative,
            ]
            completed = subprocess.run(
                command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr + completed.stdout)
            self.assertEqual(
                "accepted",
                verifier.verify_artifact(ROOT, accepted)["artifact_status"],
            )
            manifest = json.loads((accepted / exporter.MANIFEST_NAME).read_text())
            self.assertEqual(command, manifest["acceptance"]["command"])
            self.assertNotIn(str(ROOT), json.dumps(manifest["acceptance"]))

            rejected = subprocess.run(
                command + ["--allow-candidate"],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, rejected.returncode)
            rejected_override = subprocess.run(
                command + ["--coverage-baseline-artifact", archive_relative.as_posix()],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, rejected_override.returncode)
            self.assertIn("embedded coverage baseline source", rejected_override.stdout)

    def test_failed_final_acceptance_check_leaves_no_target(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            raw_dir = Path(raw)
            archive = _archive_fixture(raw_dir / "precoverage")
            candidate = raw_dir / "candidate"
            accepted = raw_dir / "accepted"
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=archive.relative_to(ROOT),
            )
            candidate_report = verifier.verify_artifact(
                ROOT,
                candidate,
                allow_candidate=True,
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
                    verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertFalse(accepted.exists())

    def test_accepted_source_identity_is_rebuilt_from_embedded_candidate(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            raw_dir = Path(raw)
            archive = _archive_fixture(raw_dir / "precoverage")
            candidate = raw_dir / "candidate"
            accepted = raw_dir / "accepted"
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=archive.relative_to(ROOT),
            )
            verifier.accept_candidate(ROOT, candidate, accepted)
            manifest_path = accepted / exporter.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text())
            manifest["acceptance"]["source_candidate_identity"]["manifest_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "source candidate identity|acceptance receipt"):
                verifier.verify_artifact(ROOT, accepted)

    def test_acceptance_rejects_parent_symlink_swap_before_publish(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw, tempfile.TemporaryDirectory() as outside_raw:
            raw_dir = Path(raw)
            outside = Path(outside_raw)
            archive = _archive_fixture(raw_dir / "precoverage")
            candidate = raw_dir / "candidate"
            publish_parent = raw_dir / "publish-parent"
            publish_parent.mkdir()
            accepted = publish_parent / "accepted"
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=archive.relative_to(ROOT),
            )
            candidate_report = verifier.verify_artifact(ROOT, candidate, allow_candidate=True)
            real_validate_output = verifier._validate_output

            def raced_validate_output(root, output):
                target = real_validate_output(root, output)
                publish_parent.rename(raw_dir / "publish-parent-original")
                publish_parent.symlink_to(outside, target_is_directory=True)
                return target

            def bypass_final_verification(root, artifact, **kwargs):
                if kwargs.get("allow_candidate"):
                    return candidate_report
                return {**candidate_report, "artifact_status": "accepted"}

            with mock.patch.object(verifier, "_validate_output", side_effect=raced_validate_output), mock.patch.object(verifier, "verify_artifact", side_effect=bypass_final_verification):
                with self.assertRaisesRegex(ValueError, "symlink|anchor|output"):
                    verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertFalse((outside / "accepted").exists())

    def test_acceptance_cleanup_preserves_concurrent_replacement(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            raw_dir = Path(raw)
            archive = _archive_fixture(raw_dir / "precoverage")
            candidate = raw_dir / "candidate"
            accepted = raw_dir / "accepted"
            moved = raw_dir / "published-moved-by-racer"
            sentinel = accepted / "sentinel.txt"
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=archive.relative_to(ROOT),
            )
            candidate_report = verifier.verify_artifact(ROOT, candidate, allow_candidate=True)

            def raced_final_verification(root, artifact, **kwargs):
                if kwargs.get("allow_candidate"):
                    return candidate_report
                accepted.rename(moved)
                accepted.mkdir()
                sentinel.write_text("unrelated replacement\n")
                raise ValueError("forced final acceptance verification failure")

            with mock.patch.object(verifier, "verify_artifact", side_effect=raced_final_verification):
                with self.assertRaisesRegex(ValueError, "forced final"):
                    verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertEqual("unrelated replacement\n", sentinel.read_text())

    def test_archive_baseline_conflict_and_corruption_fail_closed(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            raw_dir = Path(raw)
            archive_a = _archive_fixture(raw_dir / "precoverage-a")
            archive_b = _archive_fixture(raw_dir / "precoverage-b")
            relative_a = archive_a.relative_to(ROOT)
            relative_b = archive_b.relative_to(ROOT)
            evidence = verifier.independent_rebuild(ROOT, (ROOT / "rom/base.gba").read_bytes(), coverage_baseline_artifact=relative_a)
            self.assertEqual(evidence["payload"]["coverage_baseline_source"]["artifact"], relative_a.as_posix())

            bad_gzip = raw_dir / "bad-gzip"
            shutil.copytree(archive_a, bad_gzip)
            bad_bytes = b"definitely-not-gzip"
            (bad_gzip / "rom-byte-coverage.json.gz").write_bytes(bad_bytes)
            bad_manifest = json.loads((bad_gzip / "manifest.json").read_text())
            bad_manifest["coverage"]["archive"]["size"] = len(bad_bytes)
            bad_manifest["coverage"]["archive"]["sha256"] = hashlib.sha256(bad_bytes).hexdigest()
            (bad_gzip / "manifest.json").write_text(json.dumps(bad_manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaises(ValueError):
                verifier.independent_rebuild(ROOT, (ROOT / "rom/base.gba").read_bytes(), coverage_baseline_artifact=bad_gzip.relative_to(ROOT))

            bad_manifest_dir = raw_dir / "bad-manifest"
            shutil.copytree(archive_a, bad_manifest_dir)
            (bad_manifest_dir / "manifest.json").write_text("{}\n")
            with self.assertRaises(ValueError):
                verifier.independent_rebuild(ROOT, (ROOT / "rom/base.gba").read_bytes(), coverage_baseline_artifact=bad_manifest_dir.relative_to(ROOT))

            absolute_link = raw_dir / "verifier-archive-link"
            absolute_link.symlink_to(archive_a, target_is_directory=True)
            with self.assertRaises(ValueError):
                verifier.independent_rebuild(ROOT, (ROOT / "rom/base.gba").read_bytes(), coverage_baseline_artifact=absolute_link)
            absolute_parent_link = raw_dir / "verifier-parent-link"
            absolute_parent_link.symlink_to(raw_dir, target_is_directory=True)
            with self.assertRaises(ValueError):
                verifier.independent_rebuild(ROOT, (ROOT / "rom/base.gba").read_bytes(), coverage_baseline_artifact=absolute_parent_link / archive_a.name)

            candidate = raw_dir / "candidate"
            exporter.write_candidate(ROOT, candidate, coverage_baseline_artifact=relative_a)
            with self.assertRaises(ValueError):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True, coverage_baseline_artifact=relative_b)

    def test_upstream_mplay_owner_membership_is_parsed_and_fail_closed(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            replacement = Path(raw) / "mplaymain-snapshot.json"
            payload = json.loads((ROOT / "artifacts/rom-mplaymain-scheduler-v1/rom-mplaymain-scheduler.json").read_text())
            payload["coverage_claims"][0]["range"] = [0x09A42C, 0x09A60C]
            replacement.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            receipts = json.loads(json.dumps(verifier.UPSTREAM_RECEIPTS))
            receipts["mplaymain"]["payload_sha256"] = hashlib.sha256(replacement.read_bytes()).hexdigest()
            expected_receipts = json.loads(json.dumps(receipts))
            original_safe_file = verifier._safe_file

            def redirected_safe_file(root, relative):
                if Path(relative) == verifier.UPSTREAM_PATHS["mplaymain"]["payload"]:
                    return replacement
                return original_safe_file(root, relative)

            with mock.patch.object(verifier, "UPSTREAM_RECEIPTS", receipts), mock.patch.object(verifier, "EXPECTED_UPSTREAM_RECEIPTS", expected_receipts), mock.patch.object(verifier, "_safe_file", side_effect=redirected_safe_file):
                with self.assertRaisesRegex(ValueError, "MPlayMain producer ownership"):
                    verifier.independent_rebuild(ROOT, (ROOT / "rom/base.gba").read_bytes())

    def test_upstream_sappy_owner_range_is_parsed_and_fail_closed(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            replacement = Path(raw) / "sappy-bank.json"
            bank = json.loads((ROOT / "sequel/content/sappy-engine/bank.json").read_text())
            bank["table_offset"] += 2
            bank["table_offset_hex"] = f"0x{bank['table_offset']:06X}"
            replacement.write_text(json.dumps(bank, indent=2, sort_keys=True) + "\n")
            receipts = json.loads(json.dumps(verifier.UPSTREAM_RECEIPTS))
            receipts["sappy_bank_sha256"] = hashlib.sha256(replacement.read_bytes()).hexdigest()
            expected_receipts = json.loads(json.dumps(receipts))
            original_safe_file = verifier._safe_file

            def redirected_safe_file(root, relative):
                if Path(relative) == verifier.SAPPY_BANK_PATH:
                    return replacement
                return original_safe_file(root, relative)

            with mock.patch.object(verifier, "UPSTREAM_RECEIPTS", receipts), mock.patch.object(verifier, "EXPECTED_UPSTREAM_RECEIPTS", expected_receipts), mock.patch.object(verifier, "SAPPY_BANK_SHA256", receipts["sappy_bank_sha256"]), mock.patch.object(verifier, "_safe_file", side_effect=redirected_safe_file):
                with self.assertRaisesRegex(ValueError, "sappy bank ownership"):
                    verifier.independent_rebuild(ROOT, (ROOT / "rom/base.gba").read_bytes())

    def test_artifact_range_bundle_vector_schema_and_manifest_mutations_fail(self) -> None:
        _, verifier = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            source = self._candidate(Path(raw))
            for name, mutate in (
                ("rom-mp2k-note-allocator.bin", lambda data: data.__setitem__(0, data[0] ^ 1)),
                ("rom-mp2k-note-allocator.json", lambda data: data.__setitem__("promotion", {**data["promotion"], "range_vector_sha256": "0" * 64})),
                ("manifest.json", lambda data: data.__setitem__("artifact_schema", "forged")),
            ):
                target = Path(raw) / (name.replace(".", "-") + "-mutated")
                shutil.copytree(source, target)
                path = target / name
                if path.suffix == ".bin":
                    blob = bytearray(path.read_bytes())
                    mutate(blob)
                    path.write_bytes(blob)
                else:
                    obj = json.loads(path.read_text())
                    mutate(obj)
                    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
                with self.subTest(name=name), self.assertRaises(ValueError):
                    verifier.verify_artifact(ROOT, target, allow_candidate=True)

    def test_special_epilogue_and_pointer_mutations_fail_closed_independently(self) -> None:
        _, verifier = self._implemented()
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        for offset in (0x09A8EE, 0x09A8F0, 0x09A8F2, 0x09A8F4, 0x09A8F6, 0x09A8F8, 0x09A8FA, 0x09A8FC):
            changed = bytearray(rom)
            changed[offset] ^= 1
            with self.subTest(offset=offset), mock.patch.object(verifier, "ROM_SHA256", hashlib.sha256(changed).hexdigest()), self.assertRaises(ValueError):
                verifier.independent_rebuild(ROOT, bytes(changed))
        changed = bytearray(rom)
        changed[0x09AF24] ^= 1
        with mock.patch.object(verifier, "ROM_SHA256", hashlib.sha256(changed).hexdigest()), self.assertRaises(ValueError):
            verifier.independent_rebuild(ROOT, bytes(changed))

    def test_all_562_promotion_bytes_fail_fast_before_cfg_rebuild(self) -> None:
        _, verifier = self._implemented()
        original = (ROOT / "rom/base.gba").read_bytes()
        for start, end in RANGES:
            for offset in range(start, end):
                changed = bytearray(original)
                changed[offset] ^= 1
                with self.subTest(offset=offset), mock.patch.object(verifier, "_validate_rom"), mock.patch.object(verifier, "_rebuild_cfg", side_effect=AssertionError("expensive CFG rebuild ran")):
                    with self.assertRaisesRegex(ValueError, "promotion range"):
                        verifier.independent_rebuild(ROOT, bytes(changed))

    def test_writer_consumer_domain_and_producer_semantic_mutations_fail_closed(self) -> None:
        _, verifier = self._implemented()
        original = (ROOT / "rom/base.gba").read_bytes()
        for offset in (0x09A60C, 0x09AA50, 0x09AE40, 0x09AEC8, 0x09AECA, 0x09A460, 0x09A4EA, 0x09A4F0, 0x09A4FE, 0x09A502, 0x09A504, 0x09A508, 0x09A50E):
            changed = bytearray(original)
            changed[offset] ^= 1
            with self.subTest(offset=offset), mock.patch.object(verifier, "ROM_SHA256", hashlib.sha256(changed).hexdigest()), self.assertRaises(ValueError):
                verifier.independent_rebuild(ROOT, bytes(changed))

    def test_nonclaims_and_excluded_neighbors_are_explicitly_false(self) -> None:
        _, verifier = self._implemented()
        report = verifier.independent_rebuild(ROOT, (ROOT / "rom/base.gba").read_bytes())
        payload = report["payload"]
        expected = {
            "natural_runtime_reachability": False,
            "global_code_producer_denominator_complete": False,
            "global_caller_denominator_complete": False,
            "global_indirect_producer_denominator_complete": False,
            "global_computed_producer_denominator_complete": False,
            "global_ram_writer_denominator_complete": False,
            "literal_target_semantics_claimed": False,
            "audio_behavior_proven": False,
            "editing_relocation_writeback_safe": False,
            "allocatable_free_space_proven": False,
        }
        for key, value in expected.items():
            self.assertIs(payload["scope"].get(key), value, key)
        self.assertEqual([row["range"] for row in payload["excluded_ranges"]], [[0x09A6D2, 0x09A6D8], [0x09A8FE, 0x09A900], [0x09AEF4, 0x09AF24], [0x09AF28, 0x09AF34]])
        self.assertTrue(all(row["promoted"] is False for row in payload["excluded_ranges"]))


if __name__ == "__main__":
    unittest.main()
