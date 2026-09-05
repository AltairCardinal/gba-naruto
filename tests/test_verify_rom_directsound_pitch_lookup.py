#!/usr/bin/env python3
"""Independent-verifier contract for the frozen DirectSound pitch packet."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools import export_rom_directsound_pitch_lookup as exporter


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
COVERAGE = ROOT / "sequel/rom-byte-coverage.json"
VERIFIER_PATH = ROOT / "tools/verify_rom_directsound_pitch_lookup.py"
VERIFY_SCHEMA = "rom-directsound-pitch-lookup-verification-v1"
PAYLOAD_NAME = "rom-directsound-pitch-lookup.json"
BUNDLE_NAME = "rom-directsound-pitch-lookup.bin"
MANIFEST_NAME = "manifest.json"
DIRECTSOUND_COVERAGE_LIMITATION = (
    "The DirectSound pitch lookup artifact classifies exactly 344 frozen bytes: "
    "a 16-byte mixed Thumb/ARM high32 helper, a 92-byte bounded Thumb consumer, "
    "eight consumed pointer-literal bytes, 180 u8 scale descriptors, and twelve "
    "little-endian u32 frequencies. Its proof is limited to the target-bounded "
    "two-producer raw Thumb BL denominator, closed consumer CFG and structured "
    "return, helper interwork, literal bindings, and exhaustive u8 table-index "
    "domains; producer bytes and source-instruction membership, natural runtime "
    "reachability, global code/caller/indirect or computed/RAM consumer "
    "denominators, playback behavior, editing, writeback, relocation, and "
    "allocatable space remain unclaimed."
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _verifier():
    try:
        return importlib.import_module("tools.verify_rom_directsound_pitch_lookup")
    except ModuleNotFoundError:
        return None


class DirectSoundPitchLookupVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.verifier = _verifier()
        cls.temporary = tempfile.TemporaryDirectory()
        cls.candidate = Path(cls.temporary.name) / "candidate"
        exporter.write_artifact(ROOT, cls.candidate)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _implemented(self):
        self.assertIsNotNone(
            self.verifier,
            "independent DirectSound pitch verifier implementation is absent",
        )
        return self.verifier

    def _copy_candidate(self, name: str) -> Path:
        target = Path(self.temporary.name) / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.candidate, target)
        return target

    @staticmethod
    def _project_post_coverage(
        coverage: dict, expected_claims: list[dict]
    ) -> dict:
        projected = copy.deepcopy(coverage)
        projected["claims"].extend(copy.deepcopy(expected_claims))
        projected["claims"].sort(key=lambda claim: (claim["range"], claim["id"]))
        endpoints = sorted(
            {value for claim in expected_claims for value in claim["range"]}
        )
        segments = []
        for segment in projected["segments"]:
            start, end = segment["range"]
            cuts = [start, *(value for value in endpoints if start < value < end), end]
            for left, right in zip(cuts, cuts[1:]):
                owner = next(
                    (
                        claim
                        for claim in expected_claims
                        if claim["range"][0] <= left and right <= claim["range"][1]
                    ),
                    None,
                )
                replacement = copy.deepcopy(segment)
                replacement["range"] = [left, right]
                if owner is not None:
                    replacement["primary_class"] = owner["primary_class"]
                    replacement["primary_claim_ids"] = [owner["id"]]
                    replacement.pop("unknown_reason", None)
                segments.append(replacement)
        projected["segments"] = segments
        projected["summary"]["classified_bytes"] += 344
        projected["summary"]["unknown_bytes"] -= 344
        projected["summary"]["claim_count"] += 5
        projected["summary"]["segment_count"] = len(segments)
        projected["summary"].update(
            {
                "directsound_pitch_lookup_promotion_batch": (
                    "rom-directsound-pitch-lookup-v1"
                ),
                "directsound_pitch_lookup_bytes": 344,
                "directsound_pitch_lookup_claim_count": 5,
                "directsound_pitch_lookup_range_vector_sha256": (
                    "ac877e8eec80edbdab3d1b6f3991fc8a93dfc497a66c298dc9ee0c29034431bd"
                ),
                "directsound_pitch_lookup_packed_bytes_sha256": (
                    "cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850"
                ),
                "directsound_pitch_lookup_class_bytes": {
                    "armv4t_directsound_pitch_high32_interwork_code": 16,
                    "armv4t_directsound_pitch_consumer_thumb_code": 92,
                    "directsound_pitch_table_pointer_literals": 8,
                    "directsound_pitch_scale_descriptor_table": 180,
                    "directsound_pitch_frequency_u32_table": 48,
                },
                "directsound_pitch_lookup_class_claim_counts": {
                    "armv4t_directsound_pitch_high32_interwork_code": 1,
                    "armv4t_directsound_pitch_consumer_thumb_code": 1,
                    "directsound_pitch_table_pointer_literals": 1,
                    "directsound_pitch_scale_descriptor_table": 1,
                    "directsound_pitch_frequency_u32_table": 1,
                },
                "directsound_pitch_lookup_producer_count": 2,
                "directsound_pitch_lookup_consumer_instruction_count": 44,
                "directsound_pitch_lookup_consumer_block_count": 5,
                "directsound_pitch_lookup_consumer_frontier_count": 0,
                "directsound_pitch_lookup_helper_instruction_count": 5,
                "directsound_pitch_lookup_helper_block_count": 2,
                "directsound_pitch_lookup_helper_frontier_count": 0,
                "directsound_pitch_lookup_scale_descriptor_count": 180,
                "directsound_pitch_lookup_frequency_entry_count": 12,
                "directsound_pitch_lookup_frequency_index_domain": [0, 11],
                "directsound_pitch_lookup_shift_domain": [0, 14],
            }
        )
        projected["limitations"].append(DIRECTSOUND_COVERAGE_LIMITATION)
        return projected

    def test_independent_rebuild_matches_exporter_without_importing_it(self) -> None:
        verifier = self._implemented()
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertFalse(
            any(name.endswith("export_rom_directsound_pitch_lookup") for name in imported),
            imported,
        )

        expected_payload, expected_bundle = exporter.build_payload(ROOT)
        rebuilt_payload, rebuilt_bundle = verifier.rebuild_payload(ROOT)
        self.assertEqual(rebuilt_payload, expected_payload)
        self.assertEqual(rebuilt_bundle, expected_bundle)

    def test_raw_consumer_producer_literal_and_helper_contracts_are_closed(self) -> None:
        verifier = self._implemented()
        consumer = verifier.independent_consumer_contract(self.rom)
        self.assertEqual(consumer["decoded_instruction_count"], 44)
        self.assertEqual(consumer["decoded_basic_block_count"], 5)
        self.assertEqual(consumer["frontier_count"], 0)
        self.assertEqual(
            consumer["block_ranges"],
            [
                [0x09A998, 0x09A9A6],
                [0x09A9A6, 0x09A9AC],
                [0x09A9AC, 0x09A9E4],
                [0x09A9E4, 0x09A9EE],
                [0x09A9EE, 0x09A9F4],
            ],
        )
        self.assertEqual(
            consumer["external_call_edges"],
            [
                {"source_file_offset": 0x09A9E0, "target_file_offset": 0x099D7C},
                {"source_file_offset": 0x09A9EA, "target_file_offset": 0x099D7C},
            ],
        )
        self.assertEqual(
            verifier.independent_producer_denominator(self.rom)["scan"][
                "matching_producer_count"
            ],
            2,
        )
        self.assertEqual(len(verifier.independent_literal_bindings(self.rom)), 2)
        helper = verifier.independent_helper_contract(self.rom)
        self.assertEqual(helper["decoded_instruction_count"], 5)
        self.assertEqual(helper["decoded_basic_block_count"], 2)
        self.assertEqual(helper["frontier_count"], 0)
        self.assertEqual(helper["operation"], "unsigned_multiply_high32")

    def test_semantic_mutations_fail_after_slice_hashes_are_resigned(self) -> None:
        verifier = self._implemented()
        for offset in (0x09A998, 0x09A9A4, 0x09A9E0, 0x09A9F2):
            with self.subTest(consumer_offset=hex(offset)):
                mutated = bytearray(self.rom)
                mutated[offset] ^= 1
                digest = _sha(bytes(mutated[0x09A998:0x09A9F4]))
                with self.assertRaisesRegex(ValueError, "consumer|CFG|return|semantic"):
                    verifier.independent_consumer_contract(
                        bytes(mutated), expected_sha256=digest
                    )

        mutated = bytearray(self.rom)
        mutated[0x09A9F4] ^= 1
        with self.assertRaisesRegex(ValueError, "literal|pointer"):
            verifier.independent_literal_bindings(bytes(mutated))

        mutated = bytearray(self.rom)
        mutated[0x099D80] ^= 1
        digest = _sha(bytes(mutated[0x099D7C:0x099D8C]))
        with self.assertRaisesRegex(ValueError, "helper|interwork|UMULL"):
            verifier.independent_helper_contract(bytes(mutated), expected_sha256=digest)

        mutated = bytearray(self.rom)
        mutated[0x09A654] ^= 1
        with self.assertRaisesRegex(ValueError, "producer|denominator"):
            verifier.independent_producer_denominator(bytes(mutated))

    def test_table_domains_are_exhaustive_and_fail_closed(self) -> None:
        verifier = self._implemented()
        scale_raw = self.rom[0x4645C4:0x464678]
        scale = verifier.analyze_scale_descriptors(scale_raw)
        self.assertEqual(scale["descriptor_count"], 180)
        self.assertEqual(scale["frequency_index_domain"], [0, 11])
        self.assertEqual(scale["shift_domain"], [0, 14])
        self.assertEqual(scale["frequency_index_counts"], {str(i): 15 for i in range(12)})
        self.assertEqual(scale["shift_counts"], {str(i): 12 for i in range(15)})

        invalid_frequency = bytearray(scale_raw)
        invalid_frequency[0] = (invalid_frequency[0] & 0xF0) | 0x0C
        with self.assertRaisesRegex(ValueError, "frequency index"):
            verifier.analyze_scale_descriptors(bytes(invalid_frequency))
        invalid_shift = bytearray(scale_raw)
        invalid_shift[0] = 0xF0 | (invalid_shift[0] & 0x0F)
        with self.assertRaisesRegex(ValueError, "shift"):
            verifier.analyze_scale_descriptors(bytes(invalid_shift))

        frequency_raw = bytearray(self.rom[0x464678:0x4646A8])
        frequency_raw[0] ^= 1
        with self.assertRaisesRegex(ValueError, "frequency table"):
            verifier.analyze_frequency_table(bytes(frequency_raw))

    def test_coverage_overlap_is_rejected_independently(self) -> None:
        verifier = self._implemented()
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        baseline = verifier.analyze_coverage_baseline(coverage)
        self.assertEqual(baseline["unknown_promotion_bytes"], 344)
        self.assertEqual(baseline["primary_overlap_bytes"], 0)

        tampered = copy.deepcopy(coverage)
        for segment in tampered["segments"]:
            if segment["range"] == [0x099D7C, 0x099D8C]:
                segment["primary_class"] = "synthetic_known"
                segment["primary_claim_ids"] = ["synthetic-overlap"]
                break
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            verifier.analyze_coverage_baseline(tampered)

    def test_candidate_and_resigned_mutations_are_verified_fail_closed(self) -> None:
        verifier = self._implemented()
        report = verifier.verify_artifact(ROOT, self.candidate)
        self.assertEqual(report["schema"], VERIFY_SCHEMA)
        self.assertTrue(report["verified"])
        self.assertEqual(report["artifact_status"], "candidate")
        self.assertEqual(report["promotion_bytes"], 344)
        self.assertEqual(report["consumer_instruction_count"], 44)

        payload_mutation = self._copy_candidate("payload-mutation")
        payload_path = payload_mutation / PAYLOAD_NAME
        manifest_path = payload_mutation / MANIFEST_NAME
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["scope"]["natural_runtime_reachability_complete"] = True
        payload_raw = _canonical(payload)
        payload_path.write_bytes(payload_raw)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][PAYLOAD_NAME] = {
            "size": len(payload_raw),
            "sha256": _sha(payload_raw),
        }
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ValueError, "payload|reconstruction|scope"):
            verifier.verify_artifact(ROOT, payload_mutation)

        binary_mutation = self._copy_candidate("binary-mutation")
        bundle_path = binary_mutation / BUNDLE_NAME
        manifest_path = binary_mutation / MANIFEST_NAME
        bundle = bytearray(bundle_path.read_bytes())
        bundle[0] ^= 1
        bundle_path.write_bytes(bundle)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][BUNDLE_NAME] = {
            "size": len(bundle),
            "sha256": _sha(bytes(bundle)),
        }
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ValueError, "binary|bundle|ROM"):
            verifier.verify_artifact(ROOT, binary_mutation)

        foreign = self._copy_candidate("foreign-file")
        (foreign / "foreign.txt").write_text("not part of the packet\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "foreign"):
            verifier.verify_artifact(ROOT, foreign)

    def test_candidate_status_flip_cannot_forge_acceptance(self) -> None:
        verifier = self._implemented()
        forged = self._copy_candidate("forged-accepted")
        manifest_path = forged / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifact_status"] = "accepted"
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ValueError, "accepted|candidate|receipt"):
            verifier.verify_artifact(ROOT, forged)

    def test_acceptance_adds_exact_receipt_and_is_reproducible(self) -> None:
        verifier = self._implemented()
        accepted = Path(self.temporary.name) / "accepted"
        verifier.accept_candidate(ROOT, self.candidate, accepted)
        report = verifier.verify_artifact(ROOT, accepted)
        self.assertTrue(report["verified"])
        self.assertEqual(report["artifact_status"], "accepted")
        manifest_path = accepted / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["artifact_status"], "accepted")
        self.assertEqual(manifest["verification"]["exit_code"], 0)
        self.assertEqual(manifest["verification"]["report"], report)
        self.assertEqual(manifest["verifier"], manifest["verification"])
        self.assertEqual(manifest["coverage_projection"]["claim_count"], 5)
        self.assertEqual(manifest["coverage_projection"]["byte_count"], 344)
        self.assertEqual(len(manifest["coverage_projection"]["claims"]), 5)

        second = Path(self.temporary.name) / "accepted-second"
        verifier.accept_candidate(ROOT, self.candidate, second)
        for name in (PAYLOAD_NAME, BUNDLE_NAME, MANIFEST_NAME):
            self.assertEqual((accepted / name).read_bytes(), (second / name).read_bytes())

        broken = Path(self.temporary.name) / "accepted-broken"
        shutil.copytree(accepted, broken)
        broken_manifest_path = broken / MANIFEST_NAME
        broken_manifest = json.loads(broken_manifest_path.read_text(encoding="utf-8"))
        broken_manifest["verification"]["exit_code"] = 1
        broken_manifest_path.write_bytes(_canonical(broken_manifest))
        with self.assertRaisesRegex(ValueError, "receipt|manifest|verification"):
            verifier.verify_artifact(ROOT, broken)

    def test_accepted_live_coverage_supports_only_exact_pre_or_post_state(self) -> None:
        verifier = self._implemented()
        accepted = Path(self.temporary.name) / "accepted-for-coverage"
        verifier.accept_candidate(ROOT, self.candidate, accepted)
        payload = json.loads((accepted / PAYLOAD_NAME).read_text(encoding="utf-8"))
        manifest_raw = (accepted / MANIFEST_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        expected_claims = verifier.expected_coverage_claims(
            payload,
            manifest,
            manifest_sha256=_sha(manifest_raw),
        )
        self.assertEqual(5, len(expected_claims))
        self.assertEqual(344, sum(c["range"][1] - c["range"][0] for c in expected_claims))
        self.assertEqual(
            [
                [0x099D7C, 0x099D8C],
                [0x09A998, 0x09A9F4],
                [0x09A9F4, 0x09A9FC],
                [0x4645C4, 0x464678],
                [0x464678, 0x4646A8],
            ],
            [claim["range"] for claim in expected_claims],
        )

        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        pre = verifier.analyze_live_coverage(
            coverage,
            artifact_status="accepted",
            expected_claims=expected_claims,
        )
        post_coverage = self._project_post_coverage(coverage, expected_claims)
        self.assertEqual(
            "4727ba4f1f390bd174d25a31522f6474a7e318d8924a09c62a9a92535bf5e6e0",
            _sha(_canonical(post_coverage["segments"])),
        )
        for segment in post_coverage["segments"]:
            if segment.get("primary_claim_ids") and segment[
                "primary_claim_ids"
            ][0] in {claim["id"] for claim in expected_claims}:
                self.assertNotIn("unknown_reason", segment)
        post = verifier.analyze_live_coverage(
            post_coverage,
            artifact_status="accepted",
            expected_claims=expected_claims,
        )
        self.assertEqual(pre, post)
        self.assertEqual(
            pre,
            {
                "coverage_contract_verified": True,
                "promotion_bytes": 344,
                "promotion_claim_count": 5,
            },
        )

        wrong_owner = copy.deepcopy(post_coverage)
        wrong_owner["segments"] = copy.deepcopy(post_coverage["segments"])
        for segment in wrong_owner["segments"]:
            if segment["range"] == [0x099D7C, 0x099D8C]:
                segment["primary_claim_ids"] = ["wrong-owner"]
                break
        with self.assertRaisesRegex(ValueError, "coverage|owner|claim"):
            verifier.analyze_live_coverage(
                wrong_owner,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        wrong_claim = copy.deepcopy(post_coverage)
        for claim in wrong_claim["claims"]:
            if claim.get("id") == expected_claims[0]["id"]:
                claim["claim_kind"] = "wrong-kind"
                break
        with self.assertRaisesRegex(ValueError, "coverage|owner|claim"):
            verifier.analyze_live_coverage(
                wrong_claim,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        for position in (0, len(post_coverage["claims"])):
            with self.subTest(duplicate_position=position):
                duplicate = copy.deepcopy(post_coverage)
                conflicting = copy.deepcopy(expected_claims[0])
                conflicting["claim_kind"] = "conflicting-duplicate"
                duplicate["claims"].insert(position, conflicting)
                duplicate["summary"]["claim_count"] += 1
                with self.assertRaisesRegex(ValueError, "duplicate|unique|claim"):
                    verifier.analyze_live_coverage(
                        duplicate,
                        artifact_status="accepted",
                        expected_claims=expected_claims,
                    )

        stale_summary = copy.deepcopy(post_coverage)
        stale_summary["summary"].update(
            {
                "classified_bytes": 6_121_280,
                "unknown_bytes": 170_176,
                "claim_count": 14_466,
                "segment_count": 16_577,
            }
        )
        with self.assertRaisesRegex(ValueError, "summary|count|classified|unknown"):
            verifier.analyze_live_coverage(
                stale_summary,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        partial = copy.deepcopy(post_coverage)
        for segment in partial["segments"]:
            if segment["range"] == [0x099D7C, 0x099D8C]:
                segment["primary_class"] = "unknown"
                segment["primary_claim_ids"] = []
                break
        partial["summary"]["classified_bytes"] -= 16
        partial["summary"]["unknown_bytes"] += 16
        with self.assertRaisesRegex(ValueError, "partial|coverage"):
            verifier.analyze_live_coverage(
                partial,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

    def test_pre_and_post_reject_non_directsound_coverage_drift(self) -> None:
        verifier = self._implemented()
        accepted = Path(self.temporary.name) / "accepted-for-global-coverage"
        verifier.accept_candidate(ROOT, self.candidate, accepted)
        payload = json.loads((accepted / PAYLOAD_NAME).read_text(encoding="utf-8"))
        manifest_raw = (accepted / MANIFEST_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        expected_claims = verifier.expected_coverage_claims(
            payload,
            manifest,
            manifest_sha256=_sha(manifest_raw),
        )
        baseline = json.loads(COVERAGE.read_text(encoding="utf-8"))

        drifted_pre = copy.deepcopy(baseline)
        drifted_pre["claims"][0]["limitations"] = ["forged non-target evidence"]
        with self.assertRaisesRegex(ValueError, "coverage|baseline|claim|identity"):
            verifier.analyze_live_coverage(
                drifted_pre,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        post = self._project_post_coverage(baseline, expected_claims)
        drifted_claim = copy.deepcopy(post)
        drifted_claim["claims"][0]["limitations"] = ["forged non-target evidence"]
        with self.assertRaisesRegex(ValueError, "coverage|post|claim|identity"):
            verifier.analyze_live_coverage(
                drifted_claim,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        drifted_segment = copy.deepcopy(post)
        drifted_segment["segments"][0]["forged_metadata"] = True
        with self.assertRaisesRegex(ValueError, "coverage|post|segment|identity"):
            verifier.analyze_live_coverage(
                drifted_segment,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        drifted_summary = copy.deepcopy(post)
        drifted_summary["summary"]["cfg_root_count"] = -1
        with self.assertRaisesRegex(ValueError, "coverage|post|summary|identity"):
            verifier.analyze_live_coverage(
                drifted_summary,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

        drifted_limitation = copy.deepcopy(post)
        drifted_limitation["limitations"].append("forged limitation")
        with self.assertRaisesRegex(ValueError, "coverage|post|limitation|identity"):
            verifier.analyze_live_coverage(
                drifted_limitation,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )

    def test_relative_artifact_is_root_anchored_and_symlink_ancestor_is_rejected(self) -> None:
        verifier = self._implemented()
        active = ROOT / "build/experiments/active"
        with tempfile.TemporaryDirectory(dir=active) as repository_temporary:
            candidate = Path(repository_temporary) / "candidate"
            exporter.write_artifact(ROOT, candidate)
            relative = candidate.relative_to(ROOT)
            with tempfile.TemporaryDirectory() as foreign_cwd:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(VERIFIER_PATH),
                        "--root",
                        str(ROOT),
                        "--artifact-dir",
                        str(relative),
                    ],
                    cwd=foreign_cwd,
                    text=True,
                    capture_output=True,
                )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            real = base / "real"
            real.mkdir()
            shutil.copytree(self.candidate, real / "candidate")
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                verifier.verify_artifact(ROOT, linked / "candidate")


if __name__ == "__main__":
    unittest.main()
