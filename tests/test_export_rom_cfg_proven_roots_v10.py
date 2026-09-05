#!/usr/bin/env python3
"""TDD RED contract for the selector-menu CFG proven-roots v10 packet."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import tools.export_rom_cfg_proven_roots_v10 as exporter_v10
import tools.experiment_workspace as experiment_workspace
import tools.verify_rom_cfg_proven_roots_v10 as verifier_v10
from tools.verify_rom_selector_text_bindings import verify_artifact as verify_selector


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v10/luna-red-r1-20260823"
PAYLOAD_NAME = "rom-cfg-proven-roots-v10.json"
SCHEMA = "rom-cfg-proven-roots-v10"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v10"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_RANGE = (0x08B2C8, 0x08B580)
TARGET_ENVELOPE = (0x08B278, 0x08B2C8)
SOURCE_SLICE_SHA256 = "fe12c74a937dae0e60f0ba1e566788cd4dc842596d168632c9c45809f88dd07e"
SOURCE_ROOT_SHA256 = "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
SOURCE_PRODUCER_SHA256 = "8bb61927c644fe29c71e934d8e119ec88a0e85273bc4c75ab66c7dc70aadf2f4"
TARGET_ROOT_SHA256 = "3e46e3c4aedc598659e8b54f9ca4d75ca6b3463a987e1230f775c064f8d0cdc6"
TARGET_PRODUCER_SHA256 = {
    0x08B428: "caf18015a8293721c3793fead7a0e280298b190f450999515742eb065e08cdd1",
    0x08B4F8: "6667248043fe28776675c44a4433980294a1fd0365fcf064b08ef4080cd0fcbd",
}
SOURCE_EXTERNAL_VECTOR_SHA256 = "60bfe46619672256529ff046ffe8231259911e49303be42b80eac5175885cb0f"
SOURCE_BLOCK_RANGE_SHA256 = "1f3ed3239ae466d2b6f0461ba45ae446b17790ae518d8b119895d14267914346"
TARGET_BLOCK_RANGE_SHA256 = "4da59c1e58dd71ce16462a5e6a33ff62003fbc4c43aa570b56fea7900b05aed7"
LITERAL_RANGE_SHA256 = "a7ec3a41a610f7fad5af7f702db7684430e1cc86aa850d89000129426e3c4506"
PACKED_LITERAL_SHA256 = "da9566975c6272f3ec6be2401beabfa49089f1b951e7a60a0c63611d0b7b985d"
ENVELOPE_SHA256 = "bac5ad25e409197b0594658159d14f2993dfabb2a20b842ffa9fd8bddfe70890"
COVERAGE_SHA256 = "dd2a64883da6a5b561336a70d90ceb97a6ca7eb282b3bd09b0f3ec2d9ed0d156"
RETURN_PREFIX = "01bc0047"
RETURN_SHA256 = "15a0c45072c4f43ac42d0c62cb597469cb73ae8294c056a31dc8415af2bc0d3c"

UPSTREAM = {
    "artifact_schema": "rom-selector-text-bindings-v1",
    "payload_path": "artifacts/rom-selector-text-bindings-v1/selector-text-bindings.json",
    "payload_sha256": "8737d04de14949cbbbb9215c892a7776476c4230eb1e2b0c2abbbbe4440ce2eb",
    "manifest_path": "artifacts/rom-selector-text-bindings-v1/manifest.json",
    "manifest_sha256": "05cd987a60990ca6b2d3ee187eae963fd6ac8728ef9b42b92d6b37b5dc4bc031",
    "verifier_path": "tools/verify_rom_selector_text_bindings.py",
    "verifier_sha256": "a68a0d1e036be241bbac84538d5a082c7e76e2c6331ffa1d12cd384dc79e2f18",
    "verification_schema": "rom-selector-text-bindings-verification-v1",
    "menu_selector_range": [0x08B2C8, 0x08B580],
}

EXPECTED_REPORT = {
    "schema": VERIFY_SCHEMA,
    "verified": True,
    "errors": [],
    "control_flow_oracle": "armv4t-raw-encoding",
    "source_decoded_instruction_count": 264,
    "source_decoded_basic_block_count": 35,
    "source_reachable_instruction_bytes": 580,
    "source_frontier_count": 0,
    "source_external_call_edge_count": 26,
    "independently_rebuilt_instruction_count": 36,
    "decoded_basic_block_count": 7,
    "reachable_instruction_bytes": 72,
    "frontier_count": 0,
}


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def canonical_sha(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class RomCfgProvenRootsV10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = exporter_v10.build_cfg_proven_roots_v10_payload(ROOT)

    def _export(self, temporary: str | Path) -> Path:
        output = Path(temporary) / "candidate"
        exporter_v10.export_rom_cfg_proven_roots_v10(ROOT, output)
        return output

    def test_rom_identity_schema_and_upstream_report_are_frozen(self) -> None:
        self.assertEqual(ROM_SIZE, exporter_v10.ROM_SIZE)
        self.assertEqual(ROM_SHA256, exporter_v10.ROM_SHA256)
        self.assertEqual(SCHEMA, self.payload["schema"])
        self.assertEqual(
            {"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256},
            self.payload["rom"],
        )
        report = verify_selector(ROOT, ROOT / "artifacts/rom-selector-text-bindings-v1")
        self.assertEqual("rom-selector-text-bindings-verification-v1", report["schema"])
        self.assertTrue(report["verified"])
        self.assertEqual([], report["errors"])
        upstream_payload = json.loads(
            (ROOT / UPSTREAM["payload_path"]).read_text(encoding="utf-8")
        )
        menu = upstream_payload["consumer_evidence"]["direct_producer"]["menu_selector"]
        self.assertEqual(UPSTREAM["menu_selector_range"], menu["range"])
        self.assertEqual(SOURCE_SLICE_SHA256, menu["sha256"])
        self.assertEqual(UPSTREAM, self.payload["upstream"])

    def test_full_rom_denominator_has_one_source_and_two_target_producers(self) -> None:
        result = exporter_v10._producer_denominator(self.rom)
        self.assertEqual(3, result["scan"]["matching_producer_count"])
        producers = {
            (item["file_offset"], item["target_file_offset"]): item
            for item in result["producers"]
        }
        self.assertEqual(
            {(0x08B640, 0x08B2C8), (0x08B428, 0x08B278), (0x08B4F8, 0x08B278)},
            set(producers),
        )
        self.assertEqual(SOURCE_PRODUCER_SHA256, producers[(0x08B640, 0x08B2C8)]["bytes_sha256"])
        for offset, digest in TARGET_PRODUCER_SHA256.items():
            self.assertEqual(digest, producers[(offset, 0x08B278)]["bytes_sha256"])
        self.assertEqual(SOURCE_ROOT_SHA256, self.payload["source"]["root"]["entry_sha256"])
        self.assertEqual(TARGET_ROOT_SHA256, self.payload["target"]["root"]["entry_sha256"])

    def test_source_worklist_is_bounded_and_accepts_both_target_producers(self) -> None:
        source = exporter_v10._source_worklist(self.rom)
        self.assertEqual(list(SOURCE_RANGE), source["range"])
        self.assertEqual(696, source["size"])
        self.assertEqual(SOURCE_SLICE_SHA256, source["slice_sha256"])
        self.assertEqual(264, source["summary"]["decoded_instruction_count"])
        self.assertEqual(35, source["summary"]["decoded_basic_block_count"])
        self.assertEqual(580, source["summary"]["reachable_instruction_bytes"])
        self.assertEqual(0, source["summary"]["frontier_count"])
        self.assertEqual(26, source["summary"]["external_call_edge_count"])
        self.assertEqual(
            {"opaque_external": 24, "target_producer": 2},
            source["summary"]["external_call_edge_reasons"],
        )
        self.assertEqual(SOURCE_EXTERNAL_VECTOR_SHA256, source["external_vector_sha256"])
        self.assertEqual(
            canonical_sha(source["external_edges"]),
            source["external_vector_sha256"],
        )
        self.assertEqual(SOURCE_BLOCK_RANGE_SHA256, source["block_range_sha256"])
        self.assertEqual(
            [[0x08B2C8, 0x08B446], [0x08B4B0, 0x08B4D0], [0x08B4D4, 0x08B57A]],
            source["merged_ranges"],
        )
        node_offsets = {node["file_offset"] for node in source["nodes"]}
        self.assertTrue({0x08B428, 0x08B4F8} <= node_offsets)
        self.assertEqual(0, source["frontier_count"])

    def test_target_worklist_and_exact_80_byte_envelope(self) -> None:
        target = exporter_v10._target_worklist(self.rom)
        self.assertEqual(list(TARGET_ENVELOPE), target["envelope"])
        self.assertEqual(36, target["summary"]["decoded_instruction_count"])
        self.assertEqual(7, target["summary"]["decoded_basic_block_count"])
        self.assertEqual(72, target["summary"]["reachable_instruction_bytes"])
        self.assertEqual(0, target["summary"]["frontier_count"])
        self.assertEqual(0, target["summary"]["external_call_edge_count"])
        self.assertEqual(TARGET_BLOCK_RANGE_SHA256, target["block_range_sha256"])
        self.assertEqual(
            [[0x08B278, 0x08B2B0], [0x08B2B4, 0x08B2C4]],
            target["code_ranges"],
        )
        self.assertEqual(ENVELOPE_SHA256, target["envelope_sha256"])
        self.assertEqual(80, target["envelope_size"])
        self.assertNotEqual(76, target["envelope_size"])

    def test_return_idiom_is_normalized_and_tamper_fails_closed(self) -> None:
        for record in (self.payload["source"]["return"], self.payload["target"]["return"]):
            self.assertEqual("bx", record["kind"])
            self.assertEqual(RETURN_PREFIX, record["prefix_hex"])
            self.assertEqual(RETURN_SHA256, record["prefix_sha256"])
        cases = ((0x08B576, exporter_v10._source_worklist), (0x08B2C0, exporter_v10._target_worklist))
        for offset, worklist in cases:
            with self.subTest(offset=offset):
                tampered = bytearray(self.rom)
                tampered[offset] ^= 1
                with self.assertRaisesRegex(ValueError, "return|idiom|changed"):
                    worklist(bytes(tampered))

    def test_two_ldr_formulas_and_independent_literals_are_frozen(self) -> None:
        target = exporter_v10._target_worklist(self.rom)
        records = {item["ldr_file_offset"]: item for item in target["literals"]}
        self.assertEqual({0x08B294, 0x08B2B8}, set(records))
        expected = {
            0x08B294: ("064a", [0x08B2B0, 0x08B2B4]),
            0x08B2B8: ("024a", [0x08B2C4, 0x08B2C8]),
        }
        for ldr, (raw, bounds) in expected.items():
            item = records[ldr]
            self.assertEqual(raw, item["ldr_raw_hex"])
            self.assertEqual(bounds, item["literal_range"])
            halfword = int.from_bytes(bytes.fromhex(raw), "little")
            self.assertEqual(((ldr + 4) & ~3) + (halfword & 0xFF) * 4, bounds[0])
            self.assertEqual("fffffdff", item["literal_raw_hex"])
            self.assertEqual(4_294_836_223, item["value_u32"])
            self.assertEqual("a1346ac820ab23b88199fa83fdf291b1da35759d6138899533af1fe1d5cd3043", item["bytes_sha256"])
        self.assertEqual(LITERAL_RANGE_SHA256, target["literal_range_sha256"])
        self.assertEqual(PACKED_LITERAL_SHA256, target["packed_literals_sha256"])
        for offset in (0x08B294, 0x08B2B0, 0x08B2B8, 0x08B2C4):
            tampered = bytearray(self.rom)
            tampered[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "literal|LDR|changed"):
                exporter_v10._target_worklist(bytes(tampered))

    def test_coverage_prebaseline_is_hash_bound_all_80_unknown_and_rejects_known_overlap(self) -> None:
        baseline = self.payload["coverage_baseline"]
        self.assertEqual("sequel/rom-byte-coverage.json", baseline["path"])
        self.assertEqual(COVERAGE_SHA256, baseline["sha256"])
        self.assertEqual(list(TARGET_ENVELOPE), baseline["promotion_envelope"])
        self.assertEqual(80, baseline["current_unknown_bytes"])
        self.assertEqual(0, baseline["current_known_overlap_bytes"])
        self.assertEqual(80, baseline["promotion_bytes"])
        self.assertEqual(72, baseline["promotion_code_bytes"])
        self.assertEqual(8, baseline["promotion_literal_bytes"])
        self.assertEqual(80, baseline["unknown_bytes"])
        self.assertNotEqual(76, baseline["unknown_bytes"])
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            temp_root = Path(temporary)
            coverage_path = temp_root / "sequel/rom-byte-coverage.json"
            coverage_path.parent.mkdir(parents=True)
            coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
            for segment in coverage["segments"]:
                start, end = segment["range"]
                if start <= TARGET_ENVELOPE[0] and TARGET_ENVELOPE[1] <= end:
                    segment["primary_class"] = "known_cfg"
            raw = canonical_json(coverage)
            coverage_path.write_bytes(raw)
            with patch.object(exporter_v10, "COVERAGE_SHA256", hashlib.sha256(raw).hexdigest()):
                with self.assertRaisesRegex(ValueError, "known|overlap"):
                    exporter_v10._coverage_baseline(temp_root, [list(TARGET_ENVELOPE)])

    def test_payload_manifest_and_implementation_hashes_are_exact_and_self_bound(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = self._export(temporary)
            payload_raw = (output / PAYLOAD_NAME).read_bytes()
            payload = json.loads(payload_raw)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(
                {
                    "schema", "rom", "upstream", "source", "target",
                    "promotion", "coverage_baseline", "implementation", "scope",
                },
                set(payload),
            )
            self.assertEqual(SCHEMA, manifest["artifact_schema"])
            self.assertEqual(
                {
                    "schema", "artifact_schema", "artifact_status", "rom", "upstream",
                    "source", "target", "promotion", "coverage_baseline", "files",
                    "producer", "verifier", "implementation", "scope",
                },
                set(manifest),
            )
            self.assertEqual(PROMOTION_SCHEMA, manifest["schema"])
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(
                {PAYLOAD_NAME: hashlib.sha256(payload_raw).hexdigest()},
                manifest["files"],
            )
            self.assertEqual(payload["implementation"], manifest["implementation"])
            implementation = exporter_v10._implementation(ROOT)
            self.assertEqual(implementation, verifier_v10._implementation(ROOT))
            self.assertEqual(implementation, payload["implementation"])
            for label in ("exporter", "verifier", "test"):
                relative = Path(implementation["paths"][label])
                self.assertEqual(
                    hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                    implementation[f"{label}_sha256"],
                )

    def test_exported_manifest_is_standard_promotable_and_receipt_bound(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = self._export(temporary)
            manifest = json.loads((output / "manifest.json").read_text())
            report = verifier_v10.verify_rom_cfg_proven_roots_v10(ROOT, output)
            self.assertEqual(EXPECTED_REPORT, report)
            self.assertEqual(
                manifest,
                experiment_workspace._validate_promotion_manifest(output),
            )
            self.assertEqual(EXPECTED_REPORT, manifest["verifier"]["report"])
            self.assertEqual(0, manifest["verifier"]["exit_code"])
            self.assertEqual(VERIFY_SCHEMA, manifest["verifier"]["schema"])
            self.assertEqual(
                hashlib.sha256(Path(verifier_v10.__file__).read_bytes()).hexdigest(),
                manifest["verifier"]["verifier_sha256"],
            )
            for receipt, flag in ((manifest["producer"], "--output-dir"), (manifest["verifier"], "--artifact-dir")):
                command = receipt["command"]
                self.assertEqual(["python3", "-I", "-S"], command[:3])
                self.assertIn(flag, command)
                self.assertEqual(output.relative_to(ROOT).as_posix(), command[-1])

    def test_accepted_artifact_still_verifies_after_standard_promotion_copy(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = self._export(temporary)
            with tempfile.TemporaryDirectory(
                dir=ROOT / "artifacts",
                prefix=".cfg-v10-promotion-copy-",
            ) as artifact_parent:
                promoted = Path(artifact_parent) / "rom-cfg-proven-roots-v10"
                shutil.copytree(output, promoted)
                self.assertEqual(
                    EXPECTED_REPORT,
                    verifier_v10.verify_rom_cfg_proven_roots_v10(ROOT, promoted),
                )

    def test_failed_accepted_postflight_restores_existing_verified_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = self._export(temporary)
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with patch.object(
                exporter_v10,
                "_run_isolated_verifier",
                side_effect=[EXPECTED_REPORT, ValueError("synthetic accepted postflight")],
                create=True,
            ):
                with self.assertRaisesRegex(ValueError, "accepted postflight"):
                    exporter_v10.export_rom_cfg_proven_roots_v10(ROOT, output)
            after = {path.name: path.read_bytes() for path in output.iterdir()}
            self.assertEqual(before, after)

    def test_independent_verifier_rebuilds_and_rejects_tamper_or_extra_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = self._export(temporary)
            report = verifier_v10.verify_rom_cfg_proven_roots_v10(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(VERIFY_SCHEMA, report["schema"])
            self.assertEqual(264, report["source_decoded_instruction_count"])
            self.assertEqual(35, report["source_decoded_basic_block_count"])
            self.assertEqual(580, report["source_reachable_instruction_bytes"])
            self.assertEqual(0, report["source_frontier_count"])
            self.assertEqual(26, report["source_external_call_edge_count"])
            self.assertEqual(36, report["independently_rebuilt_instruction_count"])
            self.assertEqual(7, report["decoded_basic_block_count"])
            self.assertEqual(72, report["reachable_instruction_bytes"])
            self.assertEqual(0, report["frontier_count"])
            payload_path = output / PAYLOAD_NAME
            manifest_path = output / "manifest.json"
            original_payload_raw = payload_path.read_bytes()
            original_manifest_raw = manifest_path.read_bytes()
            payload = json.loads(original_payload_raw)
            payload["promotion"]["current_known_overlap_bytes"] = 1
            raw = canonical_json(payload)
            payload_path.write_bytes(raw)
            manifest = json.loads(original_manifest_raw)
            manifest["files"][PAYLOAD_NAME] = {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            manifest_path.write_bytes(canonical_json(manifest))
            self.assertFalse(verifier_v10.verify_rom_cfg_proven_roots_v10(ROOT, output)["verified"])
            payload_path.write_bytes(original_payload_raw)
            manifest_path.write_bytes(original_manifest_raw)
            (output / "extra.bin").write_bytes(b"foreign")
            self.assertFalse(verifier_v10.verify_rom_cfg_proven_roots_v10(ROOT, output)["verified"])

    def test_verifier_does_not_import_any_exporter_cfg_implementation(self) -> None:
        source = Path(verifier_v10.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                forbidden.extend(
                    alias for alias in node.names
                    if alias.name.startswith("tools.export_rom_cfg")
                )
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("tools.export_rom_cfg")
            ):
                forbidden.append(node)
        self.assertEqual([], forbidden)

    def test_output_isolated_to_experiment_rejects_canonical_artifact_and_symlink(self) -> None:
        with self.assertRaisesRegex(ValueError, "experiment|canonical|artifact"):
            exporter_v10.export_rom_cfg_proven_roots_v10(ROOT, ROOT / "artifacts/rom-cfg-proven-roots-v10")
        with self.assertRaisesRegex(ValueError, "experiment"):
            exporter_v10.export_rom_cfg_proven_roots_v10(
                ROOT, ROOT / "build/cfg-proven-roots-v10-not-an-experiment"
            )
        with self.assertRaisesRegex(ValueError, "repository root|ancestor|experiment"):
            exporter_v10.export_rom_cfg_proven_roots_v10(ROOT, ROOT)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            base = Path(temporary)
            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter_v10.export_rom_cfg_proven_roots_v10(ROOT, linked / "candidate")
            foreign = base / "foreign"
            foreign.mkdir()
            (foreign / "foreign.txt").write_text("do not replace")
            with self.assertRaisesRegex(ValueError, "foreign non-empty"):
                exporter_v10.export_rom_cfg_proven_roots_v10(ROOT, foreign)

    def test_existing_invalid_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = self._export(temporary)
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            payload = json.loads((output / PAYLOAD_NAME).read_text())
            payload["scope"]["runtime_reachability_complete"] = True
            (output / PAYLOAD_NAME).write_bytes(canonical_json(payload))
            with self.assertRaises(ValueError):
                exporter_v10.export_rom_cfg_proven_roots_v10(ROOT, output)
            after = {path.name: path.read_bytes() for path in output.iterdir()}
            self.assertNotEqual(before, after)
            self.assertEqual(before["manifest.json"], after["manifest.json"])

    def test_cli_requires_isolated_no_site_runtime(self) -> None:
        for module in (exporter_v10, verifier_v10):
            script = Path(module.__file__)
            with self.subTest(script=script.name, isolated=False):
                result = subprocess.run([sys.executable, str(script), "--help"], cwd=ROOT, capture_output=True, text=True)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("requires Python -I -S", result.stdout + result.stderr)
            with self.subTest(script=script.name, isolated=True):
                result = subprocess.run([sys.executable, "-I", "-S", str(script), "--help"], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_scope_publishes_nonclaims_without_overclaiming(self) -> None:
        nonclaims = set(self.payload["scope"]["nonclaims"])
        for claim in (
            "natural_execution_reachability",
            "global_code_denominator",
            "global_caller_denominator",
            "global_indirect_target_denominator",
            "source_window_all_instructions",
            "literal_editability",
            "adjacent_region_code_or_free_space",
        ):
            self.assertIn(claim, nonclaims)
        self.assertFalse(self.payload["scope"]["runtime_reachability_complete"])
        self.assertFalse(self.payload["scope"]["global_code_denominator_complete"])
        self.assertFalse(self.payload["scope"]["literal_editability_proven"])


if __name__ == "__main__":
    unittest.main()
