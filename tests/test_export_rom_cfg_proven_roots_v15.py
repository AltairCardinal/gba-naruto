#!/usr/bin/env python3
"""TDD contract tests for the frozen CFG proven-roots v15 exporter."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v15-implementation-20260830"
CONTRACT = json.loads(
    (ROOT / "build/experiments/active/cfg-proven-roots-v15-preflight-20260830/CONTRACT.json")
    .read_text(encoding="utf-8")
)
PREFLIGHT = json.loads(
    (ROOT / "build/experiments/active/cfg-proven-roots-v15-preflight-20260830/preflight-r1.json")
    .read_text(encoding="utf-8")
)


def _products():
    try:
        from tools import export_rom_cfg_proven_roots_v15 as exporter
        from tools import verify_rom_cfg_proven_roots_v15 as verifier
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v15 product modules are absent") from error
    return exporter, verifier


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


class CfgProvenRootsV15ProductPresenceTests(unittest.TestCase):
    def test_exporter_and_independent_verifier_are_present(self) -> None:
        exporter, verifier = _products()
        self.assertTrue(callable(exporter.export_rom_cfg_proven_roots_v15))
        self.assertTrue(callable(exporter.build_cfg_proven_roots_v15_payload))
        self.assertTrue(callable(verifier.verify_rom_cfg_proven_roots_v15))


class CfgProvenRootsV15ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_payload_has_exact_acceptance_and_negative_evidence(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v15_payload(ROOT)
        self.assertEqual("rom-cfg-proven-roots-v15", payload["schema"])
        self.assertEqual(
            [0x09A3E0, 0x0611F4, 0x0618FC, 0x08B6F0],
            [row["root"] for row in payload["targets"]],
        )
        self.assertEqual([0x09C0F4], [row["root"] for row in payload["rejected_targets"]])
        self.assertEqual(4, payload["promotion"]["accepted_root_count"])
        self.assertEqual(1, payload["promotion"]["rejected_root_count"])
        self.assertEqual(398, payload["promotion"]["code_bytes"])
        self.assertEqual(52, payload["promotion"]["literal_only_bytes"])
        self.assertEqual(450, payload["promotion"]["promotion_bytes"])
        self.assertEqual(386, payload["promotion"]["preserved_unknown_hole_bytes"])
        self.assertEqual(CONTRACT["artifact"]["promotion"]["union_ranges"], payload["promotion"]["union_ranges"])
        self.assertEqual(CONTRACT["artifact"]["promotion"]["packed_sha256"], payload["promotion"]["packed_sha256"])
        self.assertEqual(CONTRACT["artifact"]["promotion"]["union_range_vector_sha256"], payload["promotion"]["union_range_vector_sha256"])
        rejected_start, rejected_end = CONTRACT["rejected_targets"][0]["envelope"]
        for family in ("semantic_ranges", "union_ranges"):
            for start, end in payload["promotion"][family]:
                self.assertTrue(end <= rejected_start or rejected_end <= start, (family, start, end))
        self.assertEqual(
            {
                "decoded_instruction_count": 197,
                "decoded_basic_block_count": 31,
                "reachable_instruction_bytes": 398,
                "literal_only_bytes": 52,
                "frontier_count": 3,
                "external_call_edge_count": 2,
            },
            payload["promotion"]["summary"],
        )

    def test_target_vectors_and_exact_envelopes_are_frozen(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v15_payload(ROOT)
        accepted = {row["root"]: row for row in payload["targets"]}
        frozen = {row["root"]: row for row in PREFLIGHT["accepted_targets"]}
        self.assertEqual(set(frozen), set(accepted))
        for root, expected in frozen.items():
            actual = accepted[root]
            for field in (
                "envelope",
                "code_ranges",
                "promotion_ranges",
                "block_ranges",
                "frontiers",
                "holes",
            ):
                self.assertEqual(expected[field], actual[field], (hex(root), field))
            self.assertEqual(
                expected["literal_projection"]["literal_only_ranges"],
                actual["literal_projection"]["literal_only_ranges"],
                (hex(root), "literal_only_ranges"),
            )
            self.assertEqual(expected["semantic_instruction_vector_sha256"], actual["semantic_instruction_vector_sha256"])
            self.assertEqual(expected["instruction_internal_edge_vector_sha256"], actual["instruction_internal_edge_vector_sha256"])
            self.assertEqual(expected["block_internal_edge_vector_sha256"], actual["block_internal_edge_vector_sha256"])
            self.assertEqual(expected["promotion_bytes"], actual["promotion_bytes"])
            self.assertEqual(expected["frontiers"], actual["frontiers"])
        rejected = payload["rejected_targets"][0]
        self.assertEqual([0x09C0F4, 0x09C110], rejected["envelope"])
        self.assertEqual(["literal_code_overlap", "unbound_raw_thumb_bl_match"], rejected["reasons"])
        self.assertEqual([0x0610C6], rejected["unbound_raw_thumb_bl_matches"])
        self.assertEqual([[0x09C108, 0x09C110]], rejected["literal_code_overlap_ranges"])

    def test_full_rom_producer_denominators_and_upstream_membership_are_exact(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v15_payload(ROOT)
        expected_vectors = {
            0x09A3E0: [[0x0612C8, 0x09A3E0, "thumb_bl"]],
            0x0611F4: [[0x06144A, 0x0611F4, "thumb_bl"]],
            0x0618FC: [[0x061456, 0x0618FC, "thumb_bl"]],
            0x08B6F0: [[0x08BBAA, 0x08B6F0, "thumb_bl"]],
        }
        for target in payload["targets"]:
            root = target["root"]
            denominator = target["producer_denominator"]
            self.assertEqual(expected_vectors[root], denominator["vector"])
            self.assertEqual([row[0] for row in expected_vectors[root]], [row["file_offset"] for row in target["producer_membership"]])
            for row in target["producer_membership"]:
                if row["kind"] == "v12-accepted-source-node":
                    self.assertTrue(row["artifact_node"]["accepted"])
                    self.assertEqual("bl", row["artifact_node"]["mnemonic"])
                else:
                    self.assertEqual("v8-accepted-source-worklist-offset", row["kind"])
                    self.assertEqual("/source/worklist/accepted_instruction_offsets/114", row["source_pointer"])
                    self.assertEqual([572156, 572372], row["coverage_owner_range"])
        expected_upstream = CONTRACT["inputs"]["upstream"]
        self.assertEqual(expected_upstream["v8_manifest_sha256"], payload["upstream"]["v8"]["manifest_sha256"])
        self.assertEqual(expected_upstream["v8_payload_sha256"], payload["upstream"]["v8"]["payload_sha256"])
        self.assertEqual(expected_upstream["v12_manifest_sha256"], payload["upstream"]["v12"]["manifest_sha256"])
        self.assertEqual(expected_upstream["v12_payload_sha256"], payload["upstream"]["v12"]["payload_sha256"])
        self.assertEqual(expected_upstream["v13_decoder_anchor_manifest_sha256"], payload["upstream"]["v13"]["manifest_sha256"])
        self.assertEqual(expected_upstream["v13_decoder_anchor_payload_sha256"], payload["upstream"]["v13"]["payload_sha256"])

    def test_external_literal_is_provenance_only_and_scope_is_fail_closed(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v15_payload(ROOT)
        target = next(row for row in payload["targets"] if row["root"] == 0x09A3E0)
        literals = target["literal_projection"]
        self.assertEqual([[0x09A424, 0x09A42C]], literals["literal_only_ranges"])
        self.assertEqual([[0x09A68C, 0x09A694]], literals["known_external_ranges"])
        self.assertEqual(8, literals["known_external_bytes"])
        self.assertEqual(8, target["literal_only_bytes"])
        self.assertNotIn([0x09A68C, 0x09A694], target["promotion_ranges"])
        self.assertEqual(CONTRACT["scope"]["nonclaims"], payload["scope"]["nonclaims"])
        self.assertFalse(payload["scope"]["runtime_reachability_complete"])
        self.assertFalse(payload["scope"]["global_code_denominator_complete"])
        self.assertFalse(payload["scope"]["global_indirect_target_denominator_complete"])

    def test_runtime_never_reads_forbidden_preflight_or_live_coverage_inputs(self) -> None:
        source_paths = [
            ROOT / "tools/rom_cfg_proven_roots_v15_contract.py",
            ROOT / "tools/export_rom_cfg_proven_roots_v15.py",
            ROOT / "tools/verify_rom_cfg_proven_roots_v15.py",
            ROOT / "tools/verify_rom_cfg_proven_roots_v15_bundle.py",
        ]
        forbidden = (
            "CONTRACT.json",
            "preflight-r1.json",
            "independent-preflight.py",
            "sequel/rom-byte-coverage.json",
        )
        for path in source_paths:
            source = path.read_text(encoding="utf-8")
            for needle in forbidden:
                self.assertNotIn(needle, source, (path.name, needle))

        original = self.exporter._safe_file

        def guarded(root: Path, path: Path) -> Path:
            relative = Path(path).as_posix()
            self.assertNotIn(relative, {
                "sequel/rom-byte-coverage.json",
                "build/experiments/active/cfg-proven-roots-v15-preflight-20260830/CONTRACT.json",
                "build/experiments/active/cfg-proven-roots-v15-preflight-20260830/preflight-r1.json",
            })
            return original(root, path)

        with mock.patch.object(self.exporter, "_safe_file", side_effect=guarded):
            self.exporter.build_cfg_proven_roots_v15_payload(ROOT)

    def test_raw_rom_mutations_fail_during_independent_rebuild(self) -> None:
        checks = [
            (0x0612C8, lambda rom: self.exporter._producer_denominator(rom, 0x09A3E0)),
            (0x06144A, lambda rom: self.exporter._producer_denominator(rom, 0x0611F4)),
            (0x061456, lambda rom: self.exporter._producer_denominator(rom, 0x0618FC)),
            (0x08BBAA, lambda rom: self.exporter._producer_denominator(rom, 0x08B6F0)),
            (0x09A3E0, lambda rom: self.exporter._target_worklist(rom, 0)),
            (0x09A42A, lambda rom: self.exporter._target_worklist(rom, 0)),
            (0x0611F4, lambda rom: self.exporter._target_worklist(rom, 1)),
            (0x0618FC, lambda rom: self.exporter._target_worklist(rom, 2)),
            (0x08B6F0, lambda rom: self.exporter._target_worklist(rom, 3)),
        ]
        for offset, helper in checks:
            mutated = bytearray(self.rom)
            mutated[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaises(ValueError):
                helper(bytes(mutated))

    def test_upstream_mutation_fails_closed(self) -> None:
        upstream = ROOT / "artifacts/rom-cfg-proven-roots-v12/rom-cfg-proven-roots-v12.json"
        original = self.exporter._safe_file
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            mutated = Path(raw) / upstream.name
            data = bytearray(upstream.read_bytes())
            data[0] ^= 1
            mutated.write_bytes(data)

            def substitute(root: Path, path: Path) -> Path:
                if Path(path).as_posix() == upstream.relative_to(ROOT).as_posix():
                    return mutated
                return original(root, path)

            with mock.patch.object(self.exporter, "_safe_file", side_effect=substitute):
                with self.assertRaisesRegex(ValueError, "upstream|identity"):
                    self.exporter.build_cfg_proven_roots_v15_payload(ROOT)

    def test_export_is_atomic_and_requires_independent_verifier(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            output = parent / "candidate"
            manifest = self.exporter.export_rom_cfg_proven_roots_v15(ROOT, output)
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual({"manifest.json", "rom-cfg-proven-roots-v15.json"}, {path.name for path in output.iterdir()})
            self.assertEqual(self.verifier.EXPECTED_REPORT, self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, output))
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with mock.patch.object(
                self.exporter,
                "_run_isolated_verifier",
                side_effect=ValueError("forced verifier failure"),
            ), self.assertRaisesRegex(ValueError, "forced verifier failure"):
                self.exporter.export_rom_cfg_proven_roots_v15(ROOT, output)
            self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})

    def test_export_target_stays_in_candidate_or_official_scope(self) -> None:
        path = ROOT / "build/experiments/foreign-v15-candidate"
        with self.assertRaisesRegex(ValueError, "experiment|official|scope"):
            self.exporter.export_rom_cfg_proven_roots_v15(ROOT, path)

    def test_payload_path_binding_for_candidate_and_official_is_pure(self) -> None:
        candidate = EXPERIMENT / "path-binding-candidate"
        candidate_payload = self.exporter.build_cfg_proven_roots_v15_payload(
            ROOT, artifact_dir=candidate
        )
        self.assertEqual(
            candidate.relative_to(ROOT).as_posix(),
            candidate_payload["artifact_relative_path"],
        )

        official = ROOT / "artifacts/rom-cfg-proven-roots-v15"
        self.assertFalse(official.exists())
        official_payload = self.exporter.build_cfg_proven_roots_v15_payload(
            ROOT, artifact_dir=official
        )
        self.assertEqual(
            official.relative_to(ROOT).as_posix(),
            official_payload["artifact_relative_path"],
        )
        self.assertFalse(official.exists())

    def test_verifier_is_independent_and_clis_require_isolated_runtime(self) -> None:
        exporter_path = ROOT / "tools/export_rom_cfg_proven_roots_v15.py"
        verifier_path = ROOT / "tools/verify_rom_cfg_proven_roots_v15.py"
        for source_path, forbidden in (
            (exporter_path, "verify_rom_cfg_proven_roots_v15"),
            (verifier_path, "export_rom_cfg_proven_roots_v15"),
        ):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            self.assertFalse(any(forbidden in name for name in imports), source_path.name)
        for script in (
            ROOT / "tools/export_rom_cfg_proven_roots_v15.py",
            verifier_path,
        ):
            ordinary = subprocess.run(
                [sys.executable, str(script), "--help"], cwd=ROOT, capture_output=True, text=True
            )
            self.assertNotEqual(0, ordinary.returncode)
            self.assertIn("requires Python -I -S", ordinary.stdout + ordinary.stderr)
            isolated = subprocess.run(
                [sys.executable, "-I", "-S", str(script), "--help"],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(0, isolated.returncode, isolated.stdout + isolated.stderr)


if __name__ == "__main__":
    unittest.main()
