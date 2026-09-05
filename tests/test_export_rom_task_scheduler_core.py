#!/usr/bin/env python3
"""TDD contract tests for the frozen scheduler-core candidate packet."""

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

from tools import verify_rom_task_scheduler_core as scheduler_verifier


ROOT = Path(__file__).resolve().parents[1]
RUN = (
    ROOT
    / "build/experiments/active/rom-task-scheduler-core-sorted-coverage-compat/"
    "codex-r1-20260827"
)
ARTIFACT = RUN / "final"
EXPORTER = ROOT / "tools/export_rom_task_scheduler_core.py"
VERIFIER = ROOT / "tools/verify_rom_task_scheduler_core.py"
PAYLOAD_NAME = "rom-task-scheduler-core.json"
BUNDLE_NAME = "rom-task-scheduler-core.bin"
MANIFEST_NAME = "manifest.json"


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _run(command: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=check)


class SchedulerCoreContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not RUN.is_dir():
            raise AssertionError("managed experiment run must be initialized before tests")

    def _export(self) -> Path:
        result = _run([sys.executable, str(EXPORTER), "--root", str(ROOT), "--output-dir", str(ARTIFACT)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return RUN

    def _verify(self, artifact: Path = ARTIFACT, *, allow_candidate: bool = False) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(VERIFIER), "--root", str(ROOT), "--artifact-dir", str(artifact)]
        if allow_candidate:
            command.append("--allow-candidate")
        return _run(command)

    def _load(self) -> tuple[dict, dict, bytes]:
        payload = json.loads((ARTIFACT / PAYLOAD_NAME).read_text())
        manifest = json.loads((ARTIFACT / MANIFEST_NAME).read_text())
        return payload, manifest, (ARTIFACT / BUNDLE_NAME).read_bytes()

    def test_reproducible_sorted_post_coverage_normalizes(self) -> None:
        coverage, unknown, claim_map = scheduler_verifier._coverage_state(ROOT)

        self.assertEqual(14_459, coverage["claim_count"])
        self.assertEqual(170_484, sum(unknown))
        self.assertIn("cfg-thumb-0000-061d7c", claim_map)
        self.assertIn("cfg-thumb-0001-061e00", claim_map)

    def _projected_coverage(self, payload: dict) -> dict:
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        rows = payload["promotion_ranges"]
        non_claims = {
            key: value for key, value in payload["scope"].items() if value is False
        }
        payload_sha = _sha((ARTIFACT / PAYLOAD_NAME).read_bytes())
        manifest_sha = _sha((ARTIFACT / MANIFEST_NAME).read_bytes())
        verifier_sha = _sha(VERIFIER.read_bytes())
        projected_claims = []
        for index, row in enumerate(rows):
            projected_claims.append(
                {
                    "id": row["id"],
                    "range": row["range"],
                    "gba_range": [
                        0x08000000 + row["range"][0],
                        0x08000000 + row["range"][1],
                    ],
                    "role": "primary",
                    "primary_class": row["semantic_class"],
                    "claim_kind": (
                        "task_scheduler_core_reachable_instruction_bytes"
                        if row["kind"] == "code"
                        else "task_scheduler_core_consumed_literal_bytes"
                    ),
                    "mode": "thumb" if row["kind"] == "code" else None,
                    "promotion_batch": "rom-task-scheduler-core-v1",
                    "promoted_from_primary_class": "unknown",
                    "baseline_unknown_only": True,
                    "bytes_sha256": row["sha256"],
                    "artifact_range_id": row["id"],
                    "artifact_range_kind": row["kind"],
                    "promotion_union_range_count": 3,
                    "promotion_union_bytes": 308,
                    "promotion_union_range_vector_sha256": (
                        "094ce63366d095869c1826cb58de52d19849049bcb6312ca3f3009fdea31852f"
                    ),
                    "evidence_path": (
                        "artifacts/rom-task-scheduler-core-v1/"
                        "rom-task-scheduler-core.json"
                    ),
                    "evidence_sha256": payload_sha,
                    "evidence_selector": f"/promotion_ranges/{index}",
                    "promotion_manifest_path": (
                        "artifacts/rom-task-scheduler-core-v1/manifest.json"
                    ),
                    "promotion_manifest_sha256": manifest_sha,
                    "independent_verifier_path": (
                        "tools/verify_rom_task_scheduler_core.py"
                    ),
                    "independent_verifier_sha256": verifier_sha,
                    "non_claims": non_claims,
                    "limitations": payload["limitations"],
                }
            )

        projected_segments = []
        endpoints = sorted({value for row in rows for value in row["range"]})
        for segment in coverage["segments"]:
            start, end = segment["range"]
            cuts = [start, *(value for value in endpoints if start < value < end), end]
            for left, right in zip(cuts, cuts[1:]):
                promoted = next(
                    (
                        row
                        for row in rows
                        if row["range"][0] <= left and right <= row["range"][1]
                    ),
                    None,
                )
                if promoted is None:
                    replacement = copy.deepcopy(segment)
                    replacement["range"] = [left, right]
                else:
                    replacement = {
                        "range": [left, right],
                        "primary_class": promoted["semantic_class"],
                        "primary_claim_ids": [promoted["id"]],
                        "secondary_claim_ids": list(
                            segment.get("secondary_claim_ids", [])
                        ),
                    }
                projected_segments.append(replacement)

        projected = copy.deepcopy(coverage)
        projected["claims"] = [
            claim
            for claim in projected["claims"]
            if claim.get("promotion_batch") != "rom-task-scheduler-core-v1"
            and claim.get("claim_kind")
            not in {
                "task_scheduler_core_reachable_instruction_bytes",
                "task_scheduler_core_consumed_literal_bytes",
            }
            and claim.get("id") not in {row["id"] for row in rows}
        ]
        projected["claims"].extend(projected_claims)
        projected["claims"].sort(key=lambda claim: (claim["range"], claim["id"]))
        projected["segments"] = projected_segments
        limitation = "The task scheduler core artifact classifies exactly 264 bounded Thumb instruction bytes and 44 consumed literal bytes; 138 already-owned bytes remain provenance and three two-byte gaps remain unknown. Dynamic callback targets, callback lifecycle, natural runtime reachability, global caller/code/indirect denominators, scheduler business semantics, editing, relocation, and allocatable space remain unclaimed."
        if limitation not in projected["limitations"]:
            projected["limitations"].append(limitation)
        projected["summary"].update(
            {
                "classified_bytes": 6_121_280,
                "unknown_bytes": 170_176,
                "claim_count": 14_466,
                "segment_count": 16_577,
                "cfg_reachable_thumb_code_bytes": 144_178,
                "cfg_promoted_unknown_bytes": 144_210,
                "cfg_primary_claim_count": 3_785,
                "task_scheduler_core_promotion_batch": (
                    "rom-task-scheduler-core-v1"
                ),
                "task_scheduler_core_code_claim_kind": (
                    "task_scheduler_core_reachable_instruction_bytes"
                ),
                "task_scheduler_core_literal_claim_kind": (
                    "task_scheduler_core_consumed_literal_bytes"
                ),
                "task_scheduler_core_code_bytes": 264,
                "task_scheduler_core_code_claim_count": 4,
                "task_scheduler_core_literal_bytes": 44,
                "task_scheduler_core_literal_claim_count": 3,
                "task_scheduler_core_promoted_bytes": 308,
                "task_scheduler_core_promotion_claim_count": 7,
                "task_scheduler_core_gap_bytes": 6,
                "task_scheduler_core_gap_range_count": 3,
                "task_scheduler_core_owned_provenance_bytes": 138,
                "task_scheduler_core_owned_provenance_range_count": 2,
                "task_scheduler_core_union_range_count": 3,
                "task_scheduler_core_union_range_vector_sha256": (
                    "094ce63366d095869c1826cb58de52d19849049bcb6312ca3f3009fdea31852f"
                ),
                "task_scheduler_core_frontier_count": 1,
                "task_scheduler_core_return_count": 12,
            }
        )
        return projected

    def test_export_and_independent_verification(self) -> None:
        self._export()
        result = self._verify()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["verified"])
        payload, manifest, bundle = self._load()
        self.assertEqual(payload["summary"]["code_bytes"], 264)
        self.assertEqual(payload["summary"]["literal_bytes"], 44)
        self.assertEqual(payload["summary"]["promoted_bytes"], 308)
        self.assertEqual(payload["summary"]["unclassified_unknown_bytes"], 6)
        self.assertEqual(payload["summary"]["owned_provenance_bytes"], 138)
        self.assertEqual(manifest["artifact_status"], "accepted")
        self.assertEqual(manifest["files"][BUNDLE_NAME]["sha256"], _sha(bundle))

    def test_payload_mutation_is_rejected(self) -> None:
        self._export()
        path = ARTIFACT / PAYLOAD_NAME
        payload = json.loads(path.read_text())
        payload["summary"]["code_bytes"] += 1
        path.write_bytes(_canonical(payload))
        result = self._verify()
        self.assertNotEqual(result.returncode, 0)

    def test_manifest_and_binary_mutations_are_rejected(self) -> None:
        self._export()
        manifest_path = ARTIFACT / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text())
        manifest["scope"]["natural_runtime_reachable"] = True
        manifest_path.write_bytes(_canonical(manifest))
        self.assertNotEqual(self._verify().returncode, 0)
        self._export()
        binary = ARTIFACT / BUNDLE_NAME
        raw = bytearray(binary.read_bytes())
        raw[0] ^= 1
        binary.write_bytes(raw)
        self.assertNotEqual(self._verify().returncode, 0)

    def test_foreign_file_and_candidate_status_are_rejected(self) -> None:
        self._export()
        (ARTIFACT / "foreign.txt").write_text("foreign\n")
        self.assertNotEqual(self._verify().returncode, 0)
        (ARTIFACT / "foreign.txt").unlink()
        manifest_path = ARTIFACT / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text())
        manifest["artifact_status"] = "candidate"
        manifest_path.write_bytes(_canonical(manifest))
        self.assertNotEqual(self._verify().returncode, 0)
        self.assertNotEqual(self._verify(allow_candidate=True).returncode, 0)

    def test_contract_vectors_and_nonclaims_are_frozen(self) -> None:
        self._export()
        payload, _, _ = self._load()
        self.assertEqual(payload["code_ranges"], [[0x61C58, 0x61C80], [0x61C8C, 0x61D10], [0x61D10, 0x61D62], [0x61D70, 0x61D7A]])
        self.assertEqual(payload["literal_ranges"], [[0x61C80, 0x61C8C], [0x61D64, 0x61D70], [0x61DEC, 0x61E00]])
        self.assertEqual(payload["unclassified_unknown_ranges"], [[0x61D62, 0x61D64], [0x61D7A, 0x61D7C], [0x61DEA, 0x61DEC]])
        self.assertEqual(payload["owned_provenance_ranges"], [[0x61D7C, 0x61DEA], [0x61E00, 0x61E1C]])
        self.assertFalse(payload["scope"]["dynamic_callback_targets_resolved"])
        self.assertFalse(payload["scope"]["natural_runtime_reachable"])
        self.assertFalse(payload["scope"]["global_caller_denominator_complete"])
        self.assertFalse(payload["scope"]["editing_relocation_writeback_safe"])

    def test_raw_rom_mutation_helpers_fail_closed(self) -> None:
        self._export()
        # The verifier exposes an in-memory raw-input contract for mutation tests;
        # no ROM file is ever modified by this suite.
        import tools.verify_rom_task_scheduler_core as verifier

        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        payload = json.loads((ARTIFACT / PAYLOAD_NAME).read_text())
        mutation_offsets = {
            "code": 0x61C58,
            "literal": 0x61C80,
            "gap_first": 0x61D62,
            "gap_second": 0x61D7A,
            "gap_third": 0x61DEA,
            "producer_bl": 0x616C0,
            "table_pointer": 0x53D5F4,
            "wrapper_bl": 0x61C90,
            "ldr_displacement": 0x61C5C,
            "ldr_value": 0x61C80,
            "branch": 0x61C7E,
            "return": 0x61C96,
            "yield_loop": 0x61D78,
            "bx_r1_frontier": 0x9C114,
        }
        for offset in mutation_offsets.values():
            mutated = bytearray(rom)
            mutated[offset] ^= 1
            with self.assertRaises(ValueError):
                verifier.build_expected_payload(ROOT, bytes(mutated), payload=payload)

    def test_coverage_identity_mutation_fails_closed(self) -> None:
        self._export()
        import tools.verify_rom_task_scheduler_core as verifier

        payload, _, _ = self._load()
        mutated = copy.deepcopy(payload)
        mutated["coverage_baseline"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verifier.build_expected_payload(ROOT, (ROOT / "rom/base.gba").read_bytes(), payload=mutated)

    def test_producer_and_verifier_normalize_exact_post_promotion_coverage(self) -> None:
        """Both receipts must remain executable after their 308B promotion."""

        self._export()
        import tools.export_rom_task_scheduler_core as exporter
        import tools.verify_rom_task_scheduler_core as verifier

        payload, _, _ = self._load()
        projected = self._projected_coverage(payload)
        receipt = ARTIFACT.relative_to(ROOT)
        with tempfile.TemporaryDirectory(dir=RUN) as temp:
            path = Path(temp) / "post-promotion-coverage.json"
            path.write_bytes(_canonical(projected))
            relative = path.relative_to(ROOT)
            with mock.patch.object(
                verifier, "COVERAGE_PATH", relative
            ), mock.patch.object(
                verifier,
                "COVERAGE_RECEIPT_ARTIFACT",
                receipt,
                create=True,
            ):
                rebuilt, _ = verifier.build_expected_payload(
                    ROOT,
                    (ROOT / "rom/base.gba").read_bytes(),
                    payload=payload,
                )
            with mock.patch.object(
                exporter, "COVERAGE_PATH", relative
            ), mock.patch.object(
                exporter,
                "COVERAGE_RECEIPT_ARTIFACT",
                receipt,
                create=True,
            ):
                rebuilt_by_producer, _ = exporter.build_payload(ROOT)
        self.assertEqual(payload["coverage_baseline"], rebuilt["coverage_baseline"])
        self.assertEqual(
            payload["coverage_baseline"],
            rebuilt_by_producer["coverage_baseline"],
        )

    def test_post_promotion_coverage_mutations_fail_closed(self) -> None:
        self._export()
        import tools.export_rom_task_scheduler_core as exporter
        import tools.verify_rom_task_scheduler_core as verifier

        payload, _, _ = self._load()
        projected = self._projected_coverage(payload)
        receipt = ARTIFACT.relative_to(ROOT)

        mutations = {}
        non_target = copy.deepcopy(projected)
        segment = next(
            item
            for item in non_target["segments"]
            if item["primary_class"] not in {"unknown", "armv4t_task_scheduler_thumb_code", "thumb_pc_relative_consumed_literal"}
        )
        segment["primary_claim_ids"] = ["injected-non-target-owner"]
        mutations["non-target-segment"] = non_target

        extra_claim_field = copy.deepcopy(projected)
        next(
            claim
            for claim in extra_claim_field["claims"]
            if claim.get("promotion_batch") == "rom-task-scheduler-core-v1"
        )["injected"] = True
        mutations["scheduler-claim-extra-field"] = extra_claim_field

        extra_summary = copy.deepcopy(projected)
        extra_summary["summary"]["injected"] = 1
        mutations["summary-extra-field"] = extra_summary

        duplicate = copy.deepcopy(projected)
        duplicate["claims"].append(
            copy.deepcopy(
                next(
                    claim
                    for claim in duplicate["claims"]
                    if claim.get("promotion_batch")
                    == "rom-task-scheduler-core-v1"
                )
            )
        )
        mutations["duplicate-equality-claim"] = duplicate

        for label, mutated in mutations.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory(dir=RUN) as temp:
                    path = Path(temp) / "mutated-post-promotion-coverage.json"
                    path.write_bytes(_canonical(mutated))
                    relative = path.relative_to(ROOT)
                    with mock.patch.object(
                        verifier, "COVERAGE_PATH", relative
                    ), mock.patch.object(
                        verifier,
                        "COVERAGE_RECEIPT_ARTIFACT",
                        receipt,
                        create=True,
                    ):
                        with self.assertRaises(ValueError):
                            verifier.build_expected_payload(
                                ROOT,
                                (ROOT / "rom/base.gba").read_bytes(),
                                payload=payload,
                            )
                    with mock.patch.object(
                        exporter, "COVERAGE_PATH", relative
                    ), mock.patch.object(
                        exporter,
                        "COVERAGE_RECEIPT_ARTIFACT",
                        receipt,
                        create=True,
                    ):
                        with self.assertRaises(ValueError):
                            exporter.build_payload(ROOT)

    def test_later_nonoverlap_is_accepted_but_scheduler_overlap_fails(self) -> None:
        self._export()
        import tools.export_rom_task_scheduler_core as exporter
        import tools.verify_rom_task_scheduler_core as verifier

        payload, _, _ = self._load()
        projected = self._projected_coverage(payload)
        receipt = ARTIFACT.relative_to(ROOT)

        future = copy.deepcopy(projected)
        target_index, target = next(
            (index, item)
            for index, item in enumerate(future["segments"])
            if item["primary_class"] == "unknown"
            and item["range"][1] - item["range"][0] >= 3
            and not (0x061C58 <= item["range"][0] < 0x061E1C)
        )
        start = target["range"][0] + 1
        future_id = "future-nonoverlap-primary"
        future["claims"].append(
            {
                "id": future_id,
                "range": [start, start + 1],
                "role": "primary",
                "primary_class": "future_test_class",
                "claim_kind": "future_test_bytes",
                "promotion_batch": "future-test-coverage-v1",
            }
        )
        future["claims"].sort(key=lambda claim: (claim["range"], claim["id"]))
        left = copy.deepcopy(target)
        left["range"] = [target["range"][0], start]
        middle = {
            "range": [start, start + 1],
            "primary_class": "future_test_class",
            "primary_claim_ids": [future_id],
            "secondary_claim_ids": list(target.get("secondary_claim_ids", [])),
        }
        right = copy.deepcopy(target)
        right["range"] = [start + 1, target["range"][1]]
        future["segments"][target_index : target_index + 1] = [left, middle, right]
        future["limitations"].append("Future non-overlap test claim only.")
        future["summary"].update(
            {
                "classified_bytes": 6_121_281,
                "unknown_bytes": 170_175,
                "claim_count": 14_467,
                "segment_count": 16_579,
                "future_test_bytes": 1,
            }
        )

        def exercise(document: dict, *, expect_error: bool) -> None:
            with tempfile.TemporaryDirectory(dir=RUN) as temp:
                path = Path(temp) / "later-coverage.json"
                path.write_bytes(_canonical(document))
                relative = path.relative_to(ROOT)
                with mock.patch.object(
                    verifier, "COVERAGE_PATH", relative
                ), mock.patch.object(
                    verifier, "COVERAGE_RECEIPT_ARTIFACT", receipt
                ):
                    if expect_error:
                        with self.assertRaises(ValueError):
                            verifier.build_expected_payload(
                                ROOT,
                                (ROOT / "rom/base.gba").read_bytes(),
                                payload=payload,
                            )
                    else:
                        rebuilt, _ = verifier.build_expected_payload(
                            ROOT,
                            (ROOT / "rom/base.gba").read_bytes(),
                            payload=payload,
                        )
                        self.assertEqual(
                            payload["coverage_baseline"],
                            rebuilt["coverage_baseline"],
                        )
                with mock.patch.object(
                    exporter, "COVERAGE_PATH", relative
                ), mock.patch.object(
                    exporter, "COVERAGE_RECEIPT_ARTIFACT", receipt
                ):
                    if expect_error:
                        with self.assertRaises(ValueError):
                            exporter.build_payload(ROOT)
                    else:
                        rebuilt, _ = exporter.build_payload(ROOT)
                        self.assertEqual(
                            payload["coverage_baseline"],
                            rebuilt["coverage_baseline"],
                        )

        exercise(future, expect_error=False)

        missing_future_batch = copy.deepcopy(future)
        next(
            claim
            for claim in missing_future_batch["claims"]
            if claim.get("id") == future_id
        ).pop("promotion_batch")
        exercise(missing_future_batch, expect_error=True)

        unsorted_future = copy.deepcopy(future)
        future_index = next(
            index
            for index, claim in enumerate(unsorted_future["claims"])
            if claim.get("id") == future_id
        )
        unsorted_future["claims"].append(
            unsorted_future["claims"].pop(future_index)
        )
        self.assertNotEqual(
            unsorted_future["claims"],
            sorted(
                unsorted_future["claims"],
                key=lambda claim: (claim["range"], claim["id"]),
            ),
        )
        exercise(unsorted_future, expect_error=True)

        detached_primary = copy.deepcopy(projected)
        detached_primary["claims"].append(
            {
                "id": "future-detached-primary",
                "range": [start, start + 1],
                "role": "primary",
                "primary_class": "future_detached_class",
                "claim_kind": "future_detached_bytes",
                "promotion_batch": "future-detached-primary-v1",
            }
        )
        detached_primary["claims"].sort(
            key=lambda claim: (claim["range"], claim["id"])
        )
        detached_primary["limitations"].append("Detached future primary test.")
        detached_primary["summary"]["claim_count"] = 14_467
        exercise(detached_primary, expect_error=True)

        detached_secondary = copy.deepcopy(projected)
        detached_secondary["claims"].append(
            {
                "id": "future-detached-secondary",
                "range": [start, start + 1],
                "role": "secondary",
                "claim_kind": "future_detached_provenance",
                "promotion_batch": "future-detached-secondary-v1",
            }
        )
        detached_secondary["claims"].sort(
            key=lambda claim: (claim["range"], claim["id"])
        )
        detached_secondary["limitations"].append("Detached future secondary test.")
        detached_secondary["summary"]["claim_count"] = 14_467
        exercise(detached_secondary, expect_error=True)

        primary_overprojection = copy.deepcopy(future)
        outside_primary_segment = next(
            segment
            for segment in primary_overprojection["segments"]
            if not (
                segment["range"][0] < start + 1
                and start < segment["range"][1]
            )
        )
        outside_primary_segment["primary_claim_ids"] = [future_id]
        exercise(primary_overprojection, expect_error=True)

        primary_cross_role = copy.deepcopy(future)
        matching_primary_segment = next(
            segment
            for segment in primary_cross_role["segments"]
            if segment["range"] == [start, start + 1]
        )
        matching_primary_segment.setdefault("secondary_claim_ids", []).append(
            future_id
        )
        exercise(primary_cross_role, expect_error=True)

        future_secondary = copy.deepcopy(projected)
        secondary_id = "future-nonoverlap-secondary"
        future_secondary["claims"].append(
            {
                "id": secondary_id,
                "range": [start, start + 1],
                "role": "secondary",
                "claim_kind": "future_test_provenance",
                "promotion_batch": "future-test-secondary-v1",
            }
        )
        future_secondary["claims"].sort(
            key=lambda claim: (claim["range"], claim["id"])
        )
        secondary_target_index, secondary_target = next(
            (index, segment)
            for index, segment in enumerate(future_secondary["segments"])
            if segment["range"][0] <= start
            and start + 1 <= segment["range"][1]
        )
        secondary_left = copy.deepcopy(secondary_target)
        secondary_left["range"] = [secondary_target["range"][0], start]
        secondary_middle = copy.deepcopy(secondary_target)
        secondary_middle["range"] = [start, start + 1]
        secondary_middle.setdefault("secondary_claim_ids", []).append(secondary_id)
        secondary_right = copy.deepcopy(secondary_target)
        secondary_right["range"] = [start + 1, secondary_target["range"][1]]
        future_secondary["segments"][
            secondary_target_index : secondary_target_index + 1
        ] = [secondary_left, secondary_middle, secondary_right]
        future_secondary["limitations"].append("Future secondary test claim only.")
        future_secondary["summary"].update(
            {"claim_count": 14_467, "segment_count": 16_579}
        )
        exercise(future_secondary, expect_error=False)

        secondary_overprojection = copy.deepcopy(future_secondary)
        outside_secondary_segment = next(
            segment
            for segment in secondary_overprojection["segments"]
            if not (
                segment["range"][0] < start + 1
                and start < segment["range"][1]
            )
        )
        outside_secondary_segment.setdefault("secondary_claim_ids", []).append(
            secondary_id
        )
        exercise(secondary_overprojection, expect_error=True)

        secondary_cross_role = copy.deepcopy(future_secondary)
        matching_secondary_segment = next(
            segment
            for segment in secondary_cross_role["segments"]
            if segment["range"] == [start, start + 1]
        )
        matching_secondary_segment["primary_claim_ids"] = [secondary_id]
        exercise(secondary_cross_role, expect_error=True)

        ghost_primary = copy.deepcopy(future)
        ghost_primary_segment = next(
            segment
            for segment in ghost_primary["segments"]
            if segment["range"] != [start, start + 1]
            and segment["primary_class"] != "unknown"
        )
        ghost_primary_segment["primary_claim_ids"] = ["ghost-primary-id"]
        exercise(ghost_primary, expect_error=True)

        ghost_secondary = copy.deepcopy(future)
        ghost_secondary_segment = next(
            segment
            for segment in ghost_secondary["segments"]
            if segment["range"] != [start, start + 1]
        )
        ghost_secondary_segment.setdefault("secondary_claim_ids", []).append(
            "ghost-secondary-id"
        )
        exercise(ghost_secondary, expect_error=True)

        baseline_primary = next(
            claim
            for claim in future["claims"]
            if claim.get("role") == "primary"
            and claim.get("id") != future_id
            and claim.get("primary_class") != "unknown"
        )
        baseline_range_escape = copy.deepcopy(future)
        escaped_segment = next(
            segment
            for segment in baseline_range_escape["segments"]
            if not (
                segment["range"][0] < baseline_primary["range"][1]
                and baseline_primary["range"][0] < segment["range"][1]
            )
            and segment["range"] != [start, start + 1]
        )
        escaped_segment["primary_class"] = baseline_primary["primary_class"]
        escaped_segment["primary_claim_ids"] = [baseline_primary["id"]]
        exercise(baseline_range_escape, expect_error=True)

        baseline_cross_role = copy.deepcopy(future)
        baseline_owned_segment = next(
            segment
            for segment in baseline_cross_role["segments"]
            if baseline_primary["id"] in segment.get("primary_claim_ids", [])
        )
        baseline_owned_segment.setdefault("secondary_claim_ids", []).append(
            baseline_primary["id"]
        )
        exercise(baseline_cross_role, expect_error=True)

        first_scheduler_range = payload["promotion_ranges"][0]["range"]
        overlap_primary = copy.deepcopy(projected)
        overlap_primary["claims"].append(
            {
                "id": "future-overlap-primary",
                "range": [first_scheduler_range[0], first_scheduler_range[0] + 1],
                "role": "primary",
                "primary_class": "injected",
                "claim_kind": "future_overlap_bytes",
                "promotion_batch": "future-overlap-primary-v1",
            }
        )
        overlap_primary["claims"].sort(
            key=lambda claim: (claim["range"], claim["id"])
        )
        overlap_primary["limitations"].append("Injected overlap test.")
        overlap_primary["summary"]["claim_count"] = 14_467
        exercise(overlap_primary, expect_error=True)

        overlap_secondary = copy.deepcopy(projected)
        overlap_secondary["claims"].append(
            {
                "id": "future-overlap-secondary",
                "range": [first_scheduler_range[0], first_scheduler_range[0] + 1],
                "role": "secondary",
                "claim_kind": "future_overlap_provenance",
                "promotion_batch": "future-overlap-secondary-v1",
            }
        )
        overlap_secondary["claims"].sort(
            key=lambda claim: (claim["range"], claim["id"])
        )
        overlap_secondary["limitations"].append("Injected overlap test.")
        overlap_secondary["summary"]["claim_count"] = 14_467
        exercise(overlap_secondary, expect_error=True)

    def test_verifier_has_no_exporter_import(self) -> None:
        source = VERIFIER.read_text()
        self.assertNotIn("import tools.export_rom_task_scheduler_core", source)
        self.assertNotIn("from tools.export_rom_task_scheduler_core", source)

    def test_post_coverage_compat_official_receipt_contract_is_frozen(self) -> None:
        import tools.export_rom_task_scheduler_core as exporter
        import tools.verify_rom_task_scheduler_core as verifier

        self.assertEqual(exporter.ARTIFACT_RELATIVE.as_posix(), "artifacts/rom-task-scheduler-core-v1")
        self.assertEqual(verifier.ARTIFACT_RELATIVE.as_posix(), "artifacts/rom-task-scheduler-core-v1")
        expected_candidate = (
            "rom-task-scheduler-core-sorted-coverage-compat/"
            "codex-r1-20260827/final"
        )
        self.assertTrue(
            exporter.CANDIDATE_FINAL_RELATIVE.as_posix().endswith(expected_candidate)
        )
        self.assertTrue(
            verifier.CANDIDATE_FINAL_RELATIVE.as_posix().endswith(expected_candidate)
        )
        self._export()
        _, manifest, _ = self._load()
        self.assertEqual(manifest["producer"]["command"][-1], "artifacts/rom-task-scheduler-core-v1")
        self.assertEqual(manifest["verifier"]["command"][-1], "artifacts/rom-task-scheduler-core-v1")
        self.assertNotIn("build/experiments", json.dumps(manifest["producer"]))
        self.assertNotIn("build/experiments", json.dumps(manifest["verifier"]))

    def test_provenance_claim_snapshots_are_saved(self) -> None:
        self._export()
        payload, _, _ = self._load()
        snapshots = payload["provenance_inputs"]
        self.assertEqual(snapshots["consumer_code_slice"]["id"], "consumer-code-battle_effect_sprite_animations-061624")
        self.assertEqual(snapshots["consumer_code_slice"]["range"], [0x61624, 0x61710])
        self.assertEqual(snapshots["consumer_code_slice"]["primary_class"], "consumer_code_slice")
        self.assertFalse(snapshots["consumer_code_slice"]["instruction_only"])
        self.assertEqual(snapshots["function_pointer_table"]["id"], "bank-function-pointers-000")
        self.assertEqual(snapshots["function_pointer_table"]["range"], [0x53D5F4, 0x53D620])
        self.assertEqual(snapshots["function_pointer_table"]["records"], 11)
        self.assertEqual(snapshots["opaque_targets"]["0x0809C114"]["id"], "cfg-thumb-0775-09c114")
        self.assertEqual(snapshots["opaque_targets"]["0x0809C574"]["id"], "cfg-thumb-0786-09c574")

    def test_entry_proof_is_bounded_to_source_to_boundary(self) -> None:
        self._export()
        payload, _, _ = self._load()
        proof = payload["entry_proof"]
        self.assertEqual(proof["source_call"]["file_offset"], 0x60FE0)
        self.assertEqual(proof["source_call"]["target_offset"], 0x61624)
        self.assertEqual(proof["entry"]["range"], [0x61624, 0x61626])
        self.assertEqual(proof["entry"]["raw_hex"], "30b5")
        self.assertEqual(proof["rebuild"]["range"], [0x61624, 0x616C0])
        self.assertEqual(proof["rebuild"]["stop_offset"], 0x616C0)
        self.assertEqual(proof["rebuild"]["stop_reason"], "reachable_instruction_boundary")
        self.assertEqual(proof["source_to_scheduler"]["target_offset"], 0x61D10)
        self.assertFalse(proof["owner_instruction_only"])

    def test_layered_mutations_report_specific_contract_errors(self) -> None:
        self._export()
        import tools.verify_rom_task_scheduler_core as verifier

        base = (ROOT / "rom/base.gba").read_bytes()
        payload, _, _ = self._load()

        def expect(label: str, offset: int, message: str, *, patchers: dict[str, object] | None = None) -> None:
            mutated = bytearray(base)
            mutated[offset] ^= 1
            patches = {"ROM_SHA256": hashlib.sha256(mutated).hexdigest()}
            if patchers:
                patches.update(patchers)
            with self.subTest(label=label):
                with mock.patch.multiple(verifier, **patches):
                    with self.assertRaisesRegex(ValueError, message):
                        verifier.build_expected_payload(ROOT, bytes(mutated), payload=payload)

        expect("code", 0x61C58, "candidate code range changed")
        expect("gap", 0x61D62, "unclassified range changed")
        expect("producer", 0x616C0, "scheduler entry producer denominator changed")
        expect("BX-r1 frontier", 0x9C114, "BX r1 callback veneer changed")
        expect("registration denominator", 0x06EAC4, "registration wrapper BL denominator changed")
        expect("owned provenance", 0x061D7C, "owned provenance changed")
        expect("boot entry proof", 0x060FE0, "boot entry proof source BL changed")

        mutated = bytearray(base)
        mutated[0x53D5F4] ^= 1
        table_hash = hashlib.sha256(mutated[0x53D5F4:0x53D620]).hexdigest()
        sentinel_hash = hashlib.sha256(mutated[0x53D5F0:0x53D624]).hexdigest()
        with mock.patch.multiple(
            verifier,
            ROM_SHA256=hashlib.sha256(mutated).hexdigest(),
            TABLE_SHA256=table_hash,
            TABLE_SENTINEL_SHA256=sentinel_hash,
        ):
            with self.assertRaisesRegex(ValueError, "wrapper pointer occurrence denominator changed"):
                verifier.build_expected_payload(ROOT, bytes(mutated), payload=payload)

        mutated = bytearray(base)
        mutated[0x061C90] ^= 1
        code_hashes = dict(verifier.CODE_SHA256)
        code_hashes[(0x061C8C, 0x061D10)] = hashlib.sha256(mutated[0x061C8C:0x061D10]).hexdigest()
        with mock.patch.multiple(verifier, ROM_SHA256=hashlib.sha256(mutated).hexdigest(), CODE_SHA256=code_hashes):
            with self.assertRaisesRegex(ValueError, "CFG"):
                verifier.build_expected_payload(ROOT, bytes(mutated), payload=payload)

        mutated = bytearray(base)
        mutated[0x61C5C] ^= 1
        code_hashes = dict(verifier.CODE_SHA256)
        code_hashes[(0x61C58, 0x61C80)] = hashlib.sha256(mutated[0x61C58:0x61C80]).hexdigest()
        with mock.patch.multiple(verifier, ROM_SHA256=hashlib.sha256(mutated).hexdigest(), CODE_SHA256=code_hashes):
            with self.assertRaisesRegex(ValueError, "literal value or binding changed"):
                verifier.build_expected_payload(ROOT, bytes(mutated), payload=payload)

        mutated = bytearray(base)
        mutated[0x61C80] ^= 1
        literal_hashes = dict(verifier.LITERAL_SHA256)
        literal_hashes[(0x61C80, 0x61C8C)] = hashlib.sha256(mutated[0x61C80:0x61C8C]).hexdigest()
        with mock.patch.multiple(verifier, ROM_SHA256=hashlib.sha256(mutated).hexdigest(), LITERAL_SHA256=literal_hashes):
            with self.assertRaisesRegex(ValueError, "literal value or binding changed"):
                verifier.build_expected_payload(ROOT, bytes(mutated), payload=payload)

        for label, offset in (("branch", 0x61C7E), ("return", 0x61C96), ("yield loop", 0x61D78)):
            mutated = bytearray(base)
            mutated[offset] ^= 1
            code_hashes = dict(verifier.CODE_SHA256)
            for start, end in verifier.CODE_RANGES:
                if start <= offset < end:
                    code_hashes[(start, end)] = hashlib.sha256(mutated[start:end]).hexdigest()
                    break
            with self.subTest(label=label), mock.patch.multiple(verifier, ROM_SHA256=hashlib.sha256(mutated).hexdigest(), CODE_SHA256=code_hashes):
                with self.assertRaisesRegex(ValueError, "CFG|instruction denominator|return denominator"):
                    verifier.build_expected_payload(ROOT, bytes(mutated), payload=payload)

    def test_layered_provenance_and_boot_receipt_mutations_fail_closed(self) -> None:
        self._export()
        import tools.verify_rom_task_scheduler_core as verifier

        payload, manifest, _ = self._load()
        mutated_payload = copy.deepcopy(payload)
        mutated_payload["provenance_inputs"]["function_pointer_table"]["records"] = 10
        (ARTIFACT / PAYLOAD_NAME).write_bytes(_canonical(mutated_payload))
        self.assertRegex(self._verify().stdout, "payload provenance_inputs changed")
        self.assertNotEqual(self._verify().returncode, 0)
        self._export()
        mutated_payload = copy.deepcopy(payload)
        mutated_payload["entry_proof"]["entry"]["raw_hex"] = "30b6"
        (ARTIFACT / PAYLOAD_NAME).write_bytes(_canonical(mutated_payload))
        self.assertRegex(self._verify().stdout, "payload entry_proof changed")
        self.assertNotEqual(self._verify().returncode, 0)
        self._export()
        mutated_manifest = copy.deepcopy(manifest)
        mutated_manifest["producer"]["command"][-1] = "build/experiments/active/rom-task-scheduler-core/luna-r2-20260827/final"
        (ARTIFACT / MANIFEST_NAME).write_bytes(_canonical(mutated_manifest))
        result = self._verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("producer receipt changed", result.stdout)


if __name__ == "__main__":
    unittest.main()
