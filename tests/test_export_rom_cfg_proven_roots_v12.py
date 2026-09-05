#!/usr/bin/env python3
"""Contract tests for the frozen CFG proven-roots v12 exporter."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import experiment_workspace
def _products():
    try:
        import tools.export_rom_cfg_proven_roots_v12 as exporter
        import tools.verify_rom_cfg_proven_roots_v12 as verifier
    except ModuleNotFoundError as error:
        raise AssertionError("v12 product modules are absent") from error
    return exporter, verifier


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v12-20260829"
PAYLOAD_NAME = "rom-cfg-proven-roots-v12.json"
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "05215215595f0614f0461fa7502703ca62ccaa07159ddb27810f9903a31ef6d6"
SOURCE_RANGE = (398012, 398564)
SOURCE_SLICE_SHA256 = "90568d99bb0ddfba74ce946781049494e117bd2273bd3b69843f7df420506817"
TARGET_ENVELOPE = (410744, 411248)
TARGET_ENVELOPE_SHA256 = "0ea20a2118080d5a6255aad2e336d95a112937005a61a498f66bf6c120b8957b"
TARGET_ROOT_SHA256 = "a33efa7811bffe160f9df32f0892ac99fc8b5458585f096fd2b2359c1a9ac110"
TARGET_BLOCKS = [
    [410744, 410784], [410784, 410788], [410788, 410796], [410796, 410818],
    [410840, 410844], [410844, 410846], [410846, 410850], [410850, 410852],
    [410852, 410856], [410856, 410860], [410860, 410870], [410870, 410874],
    [410874, 410890], [410904, 410908], [410908, 410912], [410912, 410916],
    [410916, 410928], [410928, 410930], [410930, 410968], [410996, 411000],
    [411000, 411004], [411004, 411016], [411016, 411032], [411032, 411042],
    [411042, 411046], [411046, 411060], [411060, 411074], [411074, 411100],
    [411100, 411124], [411124, 411128], [411128, 411136], [411136, 411144],
    [411144, 411148], [411148, 411174], [411174, 411180],
]
TARGET_BLOCK_RANGE_SHA256 = "722fee7509dc5c3da7da974e3dd9854ef7dcef7390372307e141bab5b52a7419"
HOLES = [[410818, 410820], [410890, 410892]]
LITERAL_RANGES = [[410820, 410840], [410892, 410904], [410968, 410996], [411180, 411248]]
PROMOTION_BYTES = 500


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class CfgProvenRootsV12ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = cls.exporter.build_cfg_proven_roots_v12_payload(ROOT)

    def _export(self, parent: Path) -> Path:
        output = parent / "candidate"
        self.exporter.export_rom_cfg_proven_roots_v12(ROOT, output)
        return output

    def test_frozen_rom_source_and_target_contract(self) -> None:
        self.assertEqual(ROM_SIZE, self.exporter.ROM_SIZE)
        self.assertEqual(ROM_SHA256, self.exporter.ROM_SHA256)
        self.assertEqual("rom-cfg-proven-roots-v12", self.payload["schema"])
        self.assertEqual(
            {"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256},
            self.payload["rom"],
        )
        source = self.payload["source"]
        self.assertEqual(list(SOURCE_RANGE), source["range"])
        self.assertEqual(SOURCE_SLICE_SHA256, source["slice_sha256"])
        self.assertEqual("4bcf92e722093ef3fce0130a28d7708afc5572859e9cdfb671d47a17d4559624", source["reachable_range_vector_sha256"])
        self.assertEqual("45b2ec5ee53d3583d2e641ae5d1190045a541af0877462e2f509304f592fa158", source["packed_instruction_bytes_sha256"])
        self.assertEqual("bede899464bca87e2fde14ff8492eadf4735538963f3c3b8e5895552aec5e576", source["semantic_instruction_vector_sha256"])
        self.assertEqual("fb3c471b6695529759b6d18103ee733a1d0b0a9a97bd9a90f62449fbcb07b4f2", source["block_range_vector_sha256"])
        self.assertEqual("4135e4f261905b1532bf59e598ac65253bf2461e560d03d2930cf4a3ff30d1f3", source["internal_edge_vector_sha256"])
        self.assertEqual("79112a1b6ca9a9a02b82283f66ea8ddea7108d3ce200e83d05732d531e03fa8e", source["external_call_vector_sha256"])
        self.assertEqual("2e2cb02cca25a50a6f0dff30daaae54f9d15f4ffbd40875a0f14f6503d73d734", source["opaque_boundary_vector_sha256"])
        self.assertEqual(
            {"root_count": 1, "decoded_instruction_count": 237,
             "decoded_basic_block_count": 40, "reachable_instruction_bytes": 508,
             "frontier_count": 0, "external_call_edge_count": 17,
             "target_producer_edge_count": 1, "opaque_boundary_edge_count": 1},
            source["summary"],
        )
        self.assertEqual(398358, source["accepted_producer_file_offset"])
        self.assertEqual(398564, source["opaque_stop"]["file_offset"])
        target = self.payload["target"]
        self.assertEqual(list(TARGET_ENVELOPE), target["envelope"])
        self.assertEqual(TARGET_ENVELOPE_SHA256, target["envelope_sha256"])
        self.assertEqual(TARGET_ROOT_SHA256, target["root"]["entry_sha256"])
        self.assertEqual(
            [[410744, 410818], [410840, 410890], [410904, 410968], [410996, 411180]],
            target["code_ranges"],
        )
        self.assertEqual(TARGET_BLOCKS, target["block_ranges"])
        self.assertEqual(TARGET_BLOCK_RANGE_SHA256, target["block_range_sha256"])
        self.assertEqual("74f6d97e64d21ea8ff896f1a647ae7effc8a0d90ea0ae55215ff0bf5fa4ba5ce", target["code_range_vector_sha256"])
        self.assertEqual("9dcc966d9f59ca424241e80638e31910bee375f38e73700cca15e9a25b8ab81c", target["literal_range_vector_sha256"])
        self.assertEqual("b2b985dee623ffe0c5e3139112d2021bffd3ea0dbd32f8ad90c9fe91b14928cd", target["promotion_range_vector_sha256"])
        self.assertEqual("339d10d1fd6e3016be13b2734479b27717bf55ac0b8e4cb4b23a0c14783ae076", target["internal_edge_vector_sha256"])
        self.assertEqual("8149f4918dd3a0548e3cfbd49803c76a71f0948e42dcc17205cfb835c68f8d62", target["external_call_vector_sha256"])
        self.assertEqual("ce073ae1c13d87e06d2d0d47ce8630662de14584d421e842c5ba85a63de35044", target["semantic_instruction_vector_sha256"])
        self.assertEqual("5ddad79a99fabe64eb491d42b4f2ec33731e069b7dae00295f5e6b7232338f73", target["literal_binding_vector_sha256"])
        self.assertEqual("654c2b08bfcf87b16b9c3f211511f1646be306952bca9d220780d9bf374b1a84", target["packed_code_sha256"])
        self.assertEqual("7e32235d7f70003fe683de30952b77ebe65b67b95766d44041c65b556de00d10", target["packed_literals_sha256"])
        self.assertEqual("a8043f37679964db642c2d743812d5aab93a7193016d3ffd14d805b9105cf8e8", target["packed_promotion_sha256"])
        self.assertEqual(HOLES, target["holes"])
        self.assertEqual(LITERAL_RANGES, target["literal_ranges"])
        self.assertEqual(
            {"decoded_instruction_count": 182, "decoded_basic_block_count": 35,
             "reachable_instruction_bytes": 372, "frontier_count": 0,
             "internal_edge_count": 51, "external_call_count": 4,
             "literal_reference_count": 35, "unique_literal_word_count": 32,
             "literal_bytes": 128, "promotion_range_count": 8,
             "promotion_bytes": 500, "hole_bytes": 4},
            target["summary"],
        )

    def test_producer_and_literal_denominators_are_raw_rebuilt(self) -> None:
        denominator = self.exporter._producer_denominator(self.rom)
        self.assertEqual([0, ROM_SIZE], denominator["scan"]["range"])
        self.assertEqual(1, denominator["scan"]["matching_producer_count"])
        self.assertEqual([398358], [row["file_offset"] for row in denominator["producers"]])
        self.assertEqual("03f02ff8", denominator["producers"][0]["raw_hex"])
        self.assertEqual(410744, denominator["producers"][0]["target_file_offset"])
        target = self.exporter._target_worklist(self.rom)
        self.assertEqual(35, target["literal_projection"]["literal_reference_count"])
        self.assertEqual(32, target["literal_projection"]["unique_literal_word_count"])
        self.assertEqual(128, target["literal_projection"]["bytes"])
        self.assertNotIn(HOLES[0], target["promotion_ranges"])
        self.assertNotIn(HOLES[1], target["promotion_ranges"])

    def test_coverage_snapshot_and_atomic_artifact_manifest(self) -> None:
        self.assertEqual(
            {"path": "sequel/rom-byte-coverage.json", "sha256": COVERAGE_SHA256,
             "classified_bytes": 6125883, "unknown_bytes": 165573,
             "promotion_bytes": PROMOTION_BYTES, "known_overlap_bytes": 0},
            self.payload["coverage_baseline"],
        )
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = self._export(Path(raw))
            manifest = json.loads((output / "manifest.json").read_text())
            payload_raw = (output / PAYLOAD_NAME).read_bytes()
            self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual({PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}}, manifest["files"])
            self.assertEqual(manifest, experiment_workspace._validate_promotion_manifest(output))
            self.assertEqual(self.verifier.EXPECTED_REPORT, manifest["verifier"]["report"])
            self.assertEqual(self.verifier.EXPECTED_REPORT, self.verifier.verify_rom_cfg_proven_roots_v12(ROOT, output))

    def test_output_symlink_foreign_and_verifier_independence(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            linked_target = parent / "real"
            linked_target.mkdir()
            linked = parent / "linked"
            linked.symlink_to(linked_target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.exporter.export_rom_cfg_proven_roots_v12(ROOT, linked / "candidate")
            foreign = parent / "foreign"
            foreign.mkdir()
            (foreign / "foreign.txt").write_text("do not replace")
            with self.assertRaisesRegex(ValueError, "foreign"):
                self.exporter.export_rom_cfg_proven_roots_v12(ROOT, foreign)
        tree = ast.parse((ROOT / "tools/verify_rom_cfg_proven_roots_v12.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("export_rom_cfg_proven_roots_v12" in name for name in imports))

    def test_cli_requires_isolated_runtime(self) -> None:
        script = ROOT / "tools/export_rom_cfg_proven_roots_v12.py"
        ordinary = subprocess.run([sys.executable, str(script), "--help"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(0, ordinary.returncode)
        self.assertIn("requires Python -I -S", ordinary.stdout + ordinary.stderr)
        isolated = subprocess.run([sys.executable, "-I", "-S", str(script), "--help"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, isolated.returncode, isolated.stdout + isolated.stderr)

    def test_raw_rom_mutations_fail_during_independent_rebuild(self) -> None:
        for offset, helper in (
            (398358, self.exporter._producer_denominator),
            (410744, self.exporter._target_worklist),
            (411178, self.exporter._target_worklist),
        ):
            mutated = bytearray(self.rom)
            mutated[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaises(ValueError):
                helper(bytes(mutated))

    def test_source_boundary_digest_is_recomputed_from_rebuilt_vector(self) -> None:
        for product in (self.exporter, self.verifier):
            with self.subTest(product=product.__name__), mock.patch.object(
                product,
                "SOURCE_OPAQUE_BOUNDARY_SHA256",
                "0" * 64,
            ), self.assertRaisesRegex(ValueError, "source opaque boundary vector changed"):
                product._source_worklist(self.rom)


if __name__ == "__main__":
    unittest.main()
