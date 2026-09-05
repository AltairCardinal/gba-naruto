#!/usr/bin/env python3
"""TDD contract tests for the battle-controller direct-BL CFG v9 packet."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import call, patch

import tools.export_rom_cfg_proven_roots_v9 as exporter_v9
import tools.verify_rom_cfg_proven_roots_v9 as verifier_v9

from tools.export_rom_cfg_proven_roots_v9 import (
    EXPECTED_PRODUCERS,
    PROMOTION_RANGES,
    RETURN_EXIT_PREFIXES,
    _controller_source_provenance,
    _producer_denominator,
    _root_seeds,
    _validate_return_exit,
    build_cfg_proven_roots_v9_payload,
    export_rom_cfg_proven_roots_v9,
)
from tools.experiment_workspace import _validate_promotion_manifest
from tools.verify_rom_cfg_proven_roots_v9 import verify_rom_cfg_proven_roots_v9


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v9/codex-r4-20260821"
PAYLOAD_NAME = "rom-cfg-proven-roots-v9.json"
REAL_EXPORTER_COVERAGE_CONTRACT = exporter_v9._coverage_contract


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


class RomCfgProvenRootsV9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def setUp(self) -> None:
        # The exporter must validate the exact pre-v9 coverage during the real
        # candidate transaction.  Unit tests remain reproducible after that
        # coverage advances by injecting the same compact frozen receipt that
        # the independent verifier rebuilds from the 62 CFG blocks.
        self.coverage_contract = patch.object(
            exporter_v9,
            "_coverage_contract",
            side_effect=lambda _root, ranges: (
                verifier_v9._frozen_coverage_contract(ranges)
            ),
        )
        self.coverage_contract.start()
        self.addCleanup(self.coverage_contract.stop)

    def test_full_rom_direct_bl_denominator_has_all_eleven_producers(self) -> None:
        result = _producer_denominator(self.rom)
        self.assertEqual(11, result["scan"]["matching_producer_count"])
        self.assertEqual(11, len(result["producers"]))
        self.assertEqual(
            [(item[1], item[4]) for item in EXPECTED_PRODUCERS],
            [
                (item["file_offset"], item["target_file_offset"])
                for item in result["producers"]
            ],
        )

    def test_controller_provenance_splits_nine_sources_and_two_excluded(self) -> None:
        result = _controller_source_provenance(ROOT, self.rom)
        self.assertEqual(9, result["controller_source_count"])
        self.assertEqual(2, result["excluded_source_count"])
        self.assertEqual(
            {"provenance_excluded"},
            {
                item["provenance"]
                for item in result["producers"]
                if item["provenance"] == "provenance_excluded"
            },
        )
        self.assertEqual(
            {0x0736A4, 0x07445C},
            {
                item["file_offset"]
                for item in result["producers"]
                if item["provenance"] == "provenance_excluded"
            },
        )

    def test_eight_roots_and_source_bindings_are_exact(self) -> None:
        producers = _producer_denominator(self.rom)
        provenance = _controller_source_provenance(ROOT, self.rom)
        roots = _root_seeds(self.rom, producers, provenance)
        self.assertEqual(
            [
                0x06C010,
                0x06C308,
                0x06C40C,
                0x06D46C,
                0x070DD8,
                0x073000,
                0x075350,
                0x0753F8,
            ],
            [item["file_offset"] for item in roots],
        )
        self.assertEqual(
            {"producer_073d92", "producer_07416c"},
            {item["producer_id"] for item in roots[0]["sources"]},
        )

    def test_return_idiom_is_explicit_and_fails_closed_on_tamper(self) -> None:
        exits = []
        for offset, prefix in RETURN_EXIT_PREFIXES.items():
            exits.append(_validate_return_exit(self.rom, offset, prefix))
        self.assertEqual(7, len(exits))
        self.assertEqual({"r0", "r1"}, {item["register"] for item in exits})
        tampered = bytearray(self.rom)
        tampered[0x06C09A] ^= 1
        with self.assertRaisesRegex(ValueError, "return exit"):
            _validate_return_exit(bytes(tampered), 0x06C09C, "01bc0047")

    def test_exact_union_summary_crosses_and_zero_known_overlap(self) -> None:
        with patch.object(
            exporter_v9,
            "_baseline_verification_reports",
            return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
        ):
            payload = build_cfg_proven_roots_v9_payload(ROOT)
        self.assertEqual("rom-cfg-proven-roots-v9", payload["schema"])
        self.assertEqual(
            {
                "decoded_basic_block_count": 62,
                "decoded_instruction_count": 299,
                "frontier_count": 0,
                "frontier_reasons": {},
                "reachable_instruction_bytes": 628,
            },
            payload["extension"]["summary"],
        )
        self.assertEqual(16, len(payload["extension"]["baseline_cross_edges"]))
        self.assertEqual(0, payload["scope"]["current_known_overlap_bytes"])
        self.assertEqual(7, payload["scope"]["opaque_return_exit_count"])
        self.assertEqual([], payload["extension"]["frontiers"])
        self.assertEqual(
            {"call_target": 15, "fallthrough": 1},
            {
                kind: sum(
                    1
                    for edge in payload["extension"]["baseline_cross_edges"]
                    if edge["source"]["edge_kind"] == kind
                )
                for kind in ("call_target", "fallthrough")
            },
        )
        self.assertEqual(
            [list(item) for item in PROMOTION_RANGES],
            payload["scope"]["promotion_ranges"],
        )

    def test_coverage_baseline_is_hash_bound_and_all_extension_bytes_are_unknown(self) -> None:
        with patch.object(
            exporter_v9,
            "_baseline_verification_reports",
            return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
        ):
            payload = build_cfg_proven_roots_v9_payload(ROOT)
        self.assertEqual(
            {
                "path": "sequel/rom-byte-coverage.json",
                "sha256": "2ff9bc857e182c4bfeeaa572929569801549765ef1d3566cf10c17334125b9d1",
                "summary": {
                    "classified_bytes": 6_105_778,
                    "unknown_bytes": 185_678,
                    "claim_count": 13_929,
                    "segment_count": 16_171,
                },
                "promotion_block_count": 62,
                "promotion_instruction_bytes": 628,
                "promotion_block_ranges": [
                    block["range"] for block in payload["extension"]["blocks"]
                ],
                "promotion_block_range_denominator_sha256": (
                    "058f90da96cf556a2b406fbea2952435bbd64c302654657c4981841587fd7aeb"
                ),
                "current_unknown_bytes": 628,
                "current_known_overlap_bytes": 0,
            },
            payload["coverage_baseline"],
        )

    def test_coverage_loader_rechecks_same_process_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            temp_root = Path(temporary)
            coverage_path = temp_root / "sequel/rom-byte-coverage.json"
            coverage_path.parent.mkdir(parents=True)
            coverage = json.loads(
                (ROOT / exporter_v9.COVERAGE_PATH).read_text(encoding="utf-8")
            )
            promoted_class = (
                "armv4t_cfg_proven_roots_v9_reachable_thumb_code"
            )
            promoted_bytes = 0
            for segment in coverage["segments"]:
                if segment["primary_class"] == promoted_class:
                    promoted_bytes += segment["range"][1] - segment["range"][0]
                    segment["primary_class"] = "unknown"
            self.assertEqual(628, promoted_bytes)
            coverage["summary"]["classified_bytes"] -= promoted_bytes
            coverage["summary"]["unknown_bytes"] += promoted_bytes
            raw = json.dumps(
                coverage, sort_keys=True, separators=(",", ":")
            ).encode()
            coverage_path.write_bytes(raw)
            block_ranges = [
                tuple(block["range"])
                for block in json.loads(
                    (
                        ROOT
                        / "artifacts/rom-cfg-proven-roots-v9"
                        / PAYLOAD_NAME
                    ).read_text(encoding="utf-8")
                )["extension"]["blocks"]
            ]
            with patch.object(
                exporter_v9,
                "COVERAGE_SHA256",
                hashlib.sha256(raw).hexdigest(),
            ), patch.object(
                exporter_v9,
                "EXPECTED_COVERAGE_SUMMARY",
                {
                    key: coverage["summary"][key]
                    for key in exporter_v9.EXPECTED_COVERAGE_SUMMARY
                },
            ):
                first = REAL_EXPORTER_COVERAGE_CONTRACT(temp_root, block_ranges)
            self.assertEqual(628, first["current_unknown_bytes"])
            tampered = bytearray(coverage_path.read_bytes())
            tampered[-2] ^= 1
            coverage_path.write_bytes(bytes(tampered))
            with self.assertRaisesRegex(ValueError, "coverage identity"):
                REAL_EXPORTER_COVERAGE_CONTRACT(temp_root, block_ranges)

    def test_coverage_loader_rejects_a_current_known_extension_byte(self) -> None:
        module = exporter_v9
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            temp_root = Path(temporary)
            coverage_path = temp_root / module.COVERAGE_PATH
            coverage_path.parent.mkdir(parents=True)
            coverage = json.loads(
                (ROOT / module.COVERAGE_PATH).read_text(encoding="utf-8")
            )
            segment = next(
                item
                for item in coverage["segments"]
                if item["range"][0] <= 0x06C010 < item["range"][1]
            )
            segment["primary_class"] = "synthetic_current_known"
            raw = json.dumps(
                coverage, sort_keys=True, separators=(",", ":")
            ).encode()
            coverage_path.write_bytes(raw)
            expected_summary = {
                key: coverage["summary"][key]
                for key in module.EXPECTED_COVERAGE_SUMMARY
            }
            with patch.object(
                module, "COVERAGE_SHA256", hashlib.sha256(raw).hexdigest()
            ), patch.object(
                module, "EXPECTED_COVERAGE_SUMMARY", expected_summary
            ):
                with self.assertRaisesRegex(ValueError, "current known"):
                    REAL_EXPORTER_COVERAGE_CONTRACT(
                        temp_root,
                        [
                            tuple(block["range"])
                            for block in json.loads(
                                (
                                    ROOT
                                    / "artifacts/rom-cfg-proven-roots-v9"
                                    / PAYLOAD_NAME
                                ).read_text(encoding="utf-8")
                            )["extension"]["blocks"]
                        ],
                    )

    def test_verifier_replays_frozen_coverage_receipt_without_live_coverage(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "artifacts/rom-cfg-proven-roots-v9"
                / PAYLOAD_NAME
            ).read_text(encoding="utf-8")
        )
        block_ranges = [
            tuple(block["range"])
            for block in payload["extension"]["blocks"]
        ]
        with patch.object(
            verifier_v9,
            "_safe_file",
            side_effect=AssertionError("verifier read live coverage"),
        ):
            frozen = verifier_v9._frozen_coverage_contract(block_ranges)
        self.assertEqual(
            {
                **payload["coverage_baseline"],
                "promotion_block_ranges": [list(item) for item in block_ranges],
                "promotion_block_range_denominator_sha256": (
                    "058f90da96cf556a2b406fbea2952435bbd64c302654657c4981841587fd7aeb"
                ),
            },
            frozen,
        )

    def test_verifier_frozen_coverage_receipt_rejects_denominator_drift(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "artifacts/rom-cfg-proven-roots-v9"
                / PAYLOAD_NAME
            ).read_text(encoding="utf-8")
        )
        block_ranges = [
            tuple(block["range"])
            for block in payload["extension"]["blocks"]
        ]
        with self.assertRaisesRegex(ValueError, "promotion denominator"):
            verifier_v9._frozen_coverage_contract(block_ranges[:-1])

    def test_committed_artifact_verifies_after_live_coverage_advances(self) -> None:
        artifact = ROOT / "artifacts/rom-cfg-proven-roots-v9"
        with patch.object(
            verifier_v9,
            "_baseline_verification_reports",
            return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
        ):
            report = verify_rom_cfg_proven_roots_v9(ROOT, artifact)
        self.assertTrue(report["verified"], report)

    def test_baseline_entry_middle_and_straddle_fail_closed(self) -> None:
        baseline = {"synthetic": {("thumb", 0x06C010 + 2): {"size": 2}}}
        _nodes, _rejected, _incoming, crosses = exporter_v9._traverse_bounded_roots(
            self.rom,
            [{"mode": "thumb", "file_offset": 0x06C010}],
            baseline,
        )
        self.assertEqual(0x06C010 + 2, crosses[0][3][1])
        baseline = {"synthetic": {("thumb", 0x06C010 + 4): {"size": 2}}}
        decoded = {
            "accepted": True,
            "size": 2,
            "flow_kind": "linear",
            "successors": [
                {"mode": "thumb", "file_offset": 0x06C010 + 5, "kind": "branch_target"}
            ],
            "frontiers": [],
        }
        with patch.object(exporter_v9, "_decode_one", return_value=decoded):
            with self.assertRaisesRegex(ValueError, "baseline middle"):
                exporter_v9._traverse_bounded_roots(
                    self.rom,
                    [{"mode": "thumb", "file_offset": 0x06C010}],
                    baseline,
                )

    def test_export_and_independent_verifier_report(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = Path(temporary) / "final"
            export_rom_cfg_proven_roots_v9(ROOT, output)
            payload = json.loads((output / PAYLOAD_NAME).read_text(encoding="utf-8"))
            self.assertEqual(
                {item[0] for item in exporter_v9.BASELINE_SPECS},
                set(payload["frozen_baseline"]["verification_chain"]["reports"]),
            )
            report = verify_rom_cfg_proven_roots_v9(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(299, report["independently_rebuilt_instruction_count"])
            self.assertEqual(62, report["decoded_basic_block_count"])
            self.assertEqual(628, report["reachable_instruction_bytes"])
            self.assertEqual(16, report["baseline_cross_edge_count"])

    def test_exported_manifest_is_an_accepted_promotion_receipt(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = Path(temporary) / "final"
            with patch.object(
                exporter_v9,
                "_baseline_verification_reports",
                return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                verifier_v9,
                "_baseline_verification_reports",
                return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                exporter_v9,
                "_run_isolated_verifier",
                return_value=exporter_v9.EXPECTED_VERIFIER_REPORT,
            ) as isolated_verifier:
                export_rom_cfg_proven_roots_v9(ROOT, output)
                report = verify_rom_cfg_proven_roots_v9(ROOT, output)
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            payload_raw = (output / PAYLOAD_NAME).read_bytes()
            self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
            self.assertEqual("rom-cfg-proven-roots-v9", manifest["artifact_schema"])
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(
                {PAYLOAD_NAME: hashlib.sha256(payload_raw).hexdigest()},
                manifest["files"],
            )
            self.assertEqual(0, manifest["verifier"]["exit_code"])
            self.assertEqual(report, manifest["verifier"]["report"])
            self.assertEqual(2, isolated_verifier.call_count)
            self.assertEqual(
                [
                    call(ROOT, manifest["verifier"]["command"]),
                    call(ROOT, manifest["verifier"]["command"]),
                ],
                isolated_verifier.call_args_list,
            )
            self.assertEqual(manifest, _validate_promotion_manifest(output))

    def test_verifier_failure_rolls_back_new_and_existing_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = Path(temporary) / "final"
            baseline_patches = (
                patch.object(
                    exporter_v9,
                    "_baseline_verification_reports",
                    return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
                ),
                patch.object(
                    verifier_v9,
                    "_baseline_verification_reports",
                    return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
                ),
            )
            with baseline_patches[0], baseline_patches[1], patch.object(
                exporter_v9,
                "_run_isolated_verifier",
                side_effect=ValueError("candidate verifier failure"),
            ):
                with self.assertRaisesRegex(ValueError, "candidate verifier failure"):
                    export_rom_cfg_proven_roots_v9(ROOT, output)
            self.assertFalse(output.exists())

            with patch.object(
                exporter_v9,
                "_baseline_verification_reports",
                return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                verifier_v9,
                "_baseline_verification_reports",
                return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                exporter_v9,
                "_run_isolated_verifier",
                return_value=exporter_v9.EXPECTED_VERIFIER_REPORT,
            ):
                export_rom_cfg_proven_roots_v9(ROOT, output)
            original = {
                item.name: item.read_bytes() for item in output.iterdir()
            }

            with patch.object(
                exporter_v9,
                "_baseline_verification_reports",
                return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                verifier_v9,
                "_baseline_verification_reports",
                return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                exporter_v9,
                "_run_isolated_verifier",
                side_effect=[
                    exporter_v9.EXPECTED_VERIFIER_REPORT,
                    ValueError("accepted verifier failure"),
                ],
            ):
                with self.assertRaisesRegex(ValueError, "accepted verifier failure"):
                    export_rom_cfg_proven_roots_v9(ROOT, output)
            self.assertEqual(
                original,
                {item.name: item.read_bytes() for item in output.iterdir()},
            )
            self.assertEqual([], list(output.parent.glob(f".{output.name}.old-*")))

    def test_verifier_rejects_noncanonical_payload_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = Path(temporary) / "final"
            with patch.object(
                exporter_v9,
                "_baseline_verification_reports",
                return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                exporter_v9,
                "_run_isolated_verifier",
                return_value=exporter_v9.EXPECTED_VERIFIER_REPORT,
            ):
                export_rom_cfg_proven_roots_v9(ROOT, output)
            payload_path = output / PAYLOAD_NAME
            manifest_path = output / "manifest.json"
            canonical_payload = payload_path.read_bytes()
            canonical_manifest = manifest_path.read_bytes()
            payload = json.loads(canonical_payload)
            manifest = json.loads(canonical_manifest)

            noncanonical_payload = json.dumps(payload, indent=2).encode()
            payload_path.write_bytes(noncanonical_payload)
            manifest["files"][PAYLOAD_NAME] = hashlib.sha256(
                noncanonical_payload
            ).hexdigest()
            manifest_path.write_bytes(canonical_json(manifest))
            with patch.object(
                verifier_v9,
                "_baseline_verification_reports",
                return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
            ):
                self.assertFalse(
                    verify_rom_cfg_proven_roots_v9(ROOT, output)["verified"]
                )

            payload_path.write_bytes(canonical_payload)
            manifest_path.write_bytes(b"\n" + canonical_manifest)
            with patch.object(
                verifier_v9,
                "_baseline_verification_reports",
                return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
            ):
                self.assertFalse(
                    verify_rom_cfg_proven_roots_v9(ROOT, output)["verified"]
                )

    def test_candidate_and_accepted_verifier_receipts_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = Path(temporary) / "final"
            with patch.object(
                exporter_v9,
                "_baseline_verification_reports",
                return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                verifier_v9,
                "_baseline_verification_reports",
                return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                exporter_v9,
                "_run_isolated_verifier",
                return_value=exporter_v9.EXPECTED_VERIFIER_REPORT,
            ):
                export_rom_cfg_proven_roots_v9(ROOT, output)
                manifest_path = output / "manifest.json"
                accepted = json.loads(manifest_path.read_text(encoding="utf-8"))

                candidate = copy.deepcopy(accepted)
                candidate["artifact_status"] = "candidate"
                candidate["verifier"]["exit_code"] = None
                candidate["verifier"]["report"] = None
                manifest_path.write_bytes(canonical_json(candidate))
                self.assertTrue(
                    verify_rom_cfg_proven_roots_v9(ROOT, output)["verified"]
                )

                invalid_receipts = []
                bad_exit = copy.deepcopy(accepted)
                bad_exit["verifier"]["exit_code"] = 1
                invalid_receipts.append(bad_exit)
                bad_report = copy.deepcopy(accepted)
                bad_report["verifier"]["report"]["reachable_instruction_bytes"] += 1
                invalid_receipts.append(bad_report)
                bad_command = copy.deepcopy(accepted)
                bad_command["verifier"]["command"][3] = "tools/not-the-v9-verifier.py"
                invalid_receipts.append(bad_command)
                for invalid in invalid_receipts:
                    with self.subTest(verifier=invalid["verifier"]):
                        manifest_path.write_bytes(canonical_json(invalid))
                        self.assertFalse(
                            verify_rom_cfg_proven_roots_v9(ROOT, output)["verified"]
                        )

    def test_verifier_rejects_payload_tamper_after_manifest_rehash(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = Path(temporary) / "final"
            with patch.object(
                exporter_v9,
                "_baseline_verification_reports",
                return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                exporter_v9,
                "_run_isolated_verifier",
                return_value=exporter_v9.EXPECTED_VERIFIER_REPORT,
            ):
                export_rom_cfg_proven_roots_v9(ROOT, output)
            payload_path = output / PAYLOAD_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["scope"]["current_known_overlap_bytes"] = 1
            raw = canonical_json(payload)
            payload_path.write_bytes(raw)
            manifest_path = output / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][PAYLOAD_NAME] = hashlib.sha256(raw).hexdigest()
            manifest_path.write_bytes(canonical_json(manifest))
            with patch.object(
                verifier_v9,
                "_baseline_verification_reports",
                return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
            ):
                self.assertFalse(
                    verify_rom_cfg_proven_roots_v9(ROOT, output)["verified"]
                )

    def test_verifier_rejects_frozen_coverage_tamper_after_rehash(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = Path(temporary) / "final"
            with patch.object(
                exporter_v9,
                "_baseline_verification_reports",
                return_value=exporter_v9.EXPECTED_BASELINE_REPORTS,
            ), patch.object(
                exporter_v9,
                "_run_isolated_verifier",
                return_value=exporter_v9.EXPECTED_VERIFIER_REPORT,
            ):
                export_rom_cfg_proven_roots_v9(ROOT, output)
            payload_path = output / PAYLOAD_NAME
            manifest_path = output / "manifest.json"
            original_payload = json.loads(
                payload_path.read_text(encoding="utf-8")
            )
            original_manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )

            def mutate_sha(payload: dict) -> None:
                payload["coverage_baseline"]["sha256"] = "0" * 64

            def mutate_summary(payload: dict) -> None:
                payload["coverage_baseline"]["summary"]["unknown_bytes"] += 1

            def mutate_ranges(payload: dict) -> None:
                payload["coverage_baseline"]["promotion_block_ranges"].pop()

            def mutate_denominator(payload: dict) -> None:
                payload["coverage_baseline"][
                    "promotion_block_range_denominator_sha256"
                ] = "0" * 64

            def mutate_extension_and_range(payload: dict) -> None:
                payload["extension"]["blocks"][0]["range"][1] += 2
                payload["coverage_baseline"]["promotion_block_ranges"][0][1] += 2

            for mutate in (
                mutate_sha,
                mutate_summary,
                mutate_ranges,
                mutate_denominator,
                mutate_extension_and_range,
            ):
                with self.subTest(mutate=mutate.__name__):
                    payload = copy.deepcopy(original_payload)
                    manifest = copy.deepcopy(original_manifest)
                    mutate(payload)
                    raw = canonical_json(payload)
                    payload_path.write_bytes(raw)
                    manifest["files"][PAYLOAD_NAME] = hashlib.sha256(
                        raw
                    ).hexdigest()
                    manifest_path.write_bytes(canonical_json(manifest))
                    with patch.object(
                        verifier_v9,
                        "_baseline_verification_reports",
                        return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
                    ):
                        self.assertFalse(
                            verify_rom_cfg_proven_roots_v9(ROOT, output)[
                                "verified"
                            ]
                        )

    def test_output_rejects_symlink_and_foreign_directory(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            base = Path(temporary)
            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                export_rom_cfg_proven_roots_v9(ROOT, linked / "final")
            foreign = base / "foreign"
            foreign.mkdir()
            (foreign / "foreign.txt").write_text("do not replace", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign non-empty"):
                export_rom_cfg_proven_roots_v9(ROOT, foreign)

    def test_output_is_restricted_to_cfg_v9_experiment_subtree(self) -> None:
        with self.assertRaisesRegex(ValueError, "experiment subtree"):
            exporter_v9._validate_output_dir(
                ROOT,
                ROOT.parent / "cfg-v9-outside-repository-must-not-be-created",
            )
        with self.assertRaisesRegex(ValueError, "experiment subtree"):
            exporter_v9._validate_output_dir(
                ROOT,
                ROOT / "build/cfg-v9-repository-but-not-experiment",
            )

    def test_runtime_dependency_denominator_includes_transitive_seed_verifiers(self) -> None:
        expected = {
            Path("tools/verify_rom_cfg_seeds.py"),
            Path("tools/verify_similar_table_candidates.py"),
        }
        self.assertTrue(expected <= set(exporter_v9.RUNTIME_DEPENDENCY_PATHS))
        self.assertTrue(expected <= set(verifier_v9.RUNTIME_DEPENDENCY_PATHS))

    def test_runtime_dependency_identity_reloads_transitive_seed_verifier(self) -> None:
        for module in (exporter_v9, verifier_v9):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
                    temp_root = Path(temporary)
                    paths = set(module.RUNTIME_DEPENDENCY_PATHS) | {
                        Path("tools/export_rom_cfg_proven_roots_v9.py"),
                        Path("tools/verify_rom_cfg_proven_roots_v9.py"),
                        Path("tests/test_export_rom_cfg_proven_roots_v9.py"),
                    }
                    for relative in paths:
                        target = temp_root / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(ROOT / relative, target)
                    first = module._implementation(temp_root)
                    self.assertIn(
                        "tools/verify_rom_cfg_seeds.py",
                        first["runtime_dependency_sha256"],
                    )
                    dependency = temp_root / "tools/verify_rom_cfg_seeds.py"
                    dependency.write_bytes(dependency.read_bytes() + b"\n")
                    with self.assertRaisesRegex(
                        ValueError, "loaded implementation differs from passed root"
                    ):
                        module._implementation(temp_root)

    def test_baseline_verification_chain_covers_every_frozen_artifact(self) -> None:
        for module in (exporter_v9, verifier_v9):
            with self.subTest(module=module.__name__):
                labels = [item[0] for item in module.BASELINE_SPECS]
                with patch.object(
                    module,
                    "_invoke_baseline_verifier",
                    side_effect=lambda root, label: module.EXPECTED_BASELINE_REPORTS[label],
                ) as invoke:
                    reports = module._baseline_verification_reports(ROOT)
                self.assertEqual(set(labels), set(reports))
                self.assertEqual(len(labels), invoke.call_count)
                self.assertTrue(all(report["verified"] for report in reports.values()))

    def test_verifier_does_not_depend_on_v9_exporter(self) -> None:
        source = inspect.getsource(verifier_v9)
        tree = ast.parse(source)
        forbidden_module = "tools.export_rom_cfg_proven_roots_v9"
        forbidden_imports = []
        module_aliases = set()
        symbol_aliases = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == forbidden_module or alias.name.startswith(
                        f"{forbidden_module}."
                    ):
                        forbidden_imports.append(node)
                        module_aliases.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module == forbidden_module:
                forbidden_imports.append(node)
                symbol_aliases.update(
                    alias.asname or alias.name for alias in node.names
                )
        self.assertEqual([], forbidden_imports)
        forbidden_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if isinstance(function, ast.Name) and function.id in symbol_aliases:
                forbidden_calls.append(node)
            elif (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id in module_aliases
            ):
                forbidden_calls.append(node)
        self.assertEqual([], forbidden_calls)

    def test_exporter_reloads_temp_root_controller_dependency_after_first_success(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            temp_root = Path(temporary)
            (temp_root / "rom").mkdir()
            shutil.copy2(ROOT / "rom/base.gba", temp_root / "rom/base.gba")
            source_dir = temp_root / exporter_v9.CONTROLLER_ARTIFACT
            source_dir.mkdir(parents=True)
            for name in (exporter_v9.CONTROLLER_PAYLOAD.name, "manifest.json"):
                shutil.copy2(ROOT / exporter_v9.CONTROLLER_ARTIFACT / name, source_dir / name)
            with patch(
                "tools.verify_rom_battle_controller_cfg.verify_rom_battle_controller_cfg",
                return_value=exporter_v9.EXPECTED_CONTROLLER_REPORT,
            ):
                first = exporter_v9._controller_source_provenance(temp_root, self.rom)
                self.assertEqual(9, first["controller_source_count"])
                manifest = source_dir / "manifest.json"
                raw = bytearray(manifest.read_bytes())
                raw[-2] ^= 1
                manifest.write_bytes(bytes(raw))
                with self.assertRaisesRegex(ValueError, "manifest identity"):
                    exporter_v9._controller_source_provenance(temp_root, self.rom)

    def test_verifier_reloads_temp_root_baseline_dependency_after_first_success(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            temp_root = Path(temporary)
            (temp_root / "rom").mkdir()
            shutil.copy2(ROOT / "rom/base.gba", temp_root / "rom/base.gba")
            for _label, relative, _payload_sha, _manifest_sha, _schema, verifier_path in verifier_v9.BASELINE_SPECS:
                for source in (relative, relative.parent / "manifest.json", verifier_path):
                    target = temp_root / source
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(ROOT / source, target)
            with patch.object(
                verifier_v9,
                "_baseline_verification_reports",
                return_value=verifier_v9.EXPECTED_BASELINE_REPORTS,
            ):
                first = verifier_v9._baseline_contract(temp_root, self.rom)
                self.assertIn("proven_roots_v8", first[2])
                manifest = temp_root / verifier_v9.BASELINE_SPECS[-1][1].parent / "manifest.json"
                raw = bytearray(manifest.read_bytes())
                raw[-2] ^= 1
                manifest.write_bytes(bytes(raw))
                with self.assertRaisesRegex(ValueError, "manifest identity"):
                    verifier_v9._baseline_contract(temp_root, self.rom)


if __name__ == "__main__":
    unittest.main()
