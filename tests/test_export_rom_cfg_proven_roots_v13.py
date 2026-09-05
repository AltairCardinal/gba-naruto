#!/usr/bin/env python3
"""Contract tests for the frozen CFG proven-roots v13 exporter."""

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

from tools import experiment_workspace


def _products():
    try:
        import tools.export_rom_cfg_proven_roots_v13 as exporter
        import tools.verify_rom_cfg_proven_roots_v13 as verifier
    except ModuleNotFoundError as error:
        raise AssertionError("v13 product modules are absent") from error
    return exporter, verifier


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v13-red-20260829"
PAYLOAD_NAME = "rom-cfg-proven-roots-v13.json"
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "96fba5e10bbef80eb0326e7dd85d07babdcffb63674a0fecd046c8b9edc427eb"
COVERAGE_EXPECTED = {
    "path": "sequel/rom-byte-coverage.json",
    "sha256": COVERAGE_SHA256,
    "classified_bytes": 6_126_383,
    "unknown_bytes": 165_073,
    "promotion_bytes": 392,
    "known_overlap_bytes": 0,
}

UPSTREAM_EXPECTED = {
    "artifact_schema": "battle-effect-sprite-animations-v1",
    "manifest_path": "artifacts/battle-effect-sprite-animations-v1/manifest.json",
    "manifest_sha256": "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848",
    "verifier_path": "tools/verify_battle_effect_sprite_animations.py",
    "verifier_sha256": "ba22259f41e53398a0f271f806c831b5eaf0052f17784c831d2591c0220f0c6b",
    "consumer_slice_name": "dynamic_obj_vram_dispatch_order",
    "consumer_slice_range": [398_012, 398_564],
    "consumer_slice_sha256": "90568d99bb0ddfba74ce946781049494e117bd2273bd3b69843f7df420506817",
    "coverage_claim_id": "consumer-code-battle_effect_sprite_animations-0612bc",
    "coverage_primary_class": "consumer_code_slice",
    "opaque_stop": {
        "offset": 398_564,
        "coverage_claim_id": "verified-reuse-staged-oam-submit-code-0614e4",
    },
}

SOURCE_RANGE = (398_012, 398_564)
SOURCE_SLICE_SHA256 = "90568d99bb0ddfba74ce946781049494e117bd2273bd3b69843f7df420506817"
SOURCE_REACHABLE_RANGES = [[398_012, 398_156], [398_200, 398_564]]
SOURCE_SUMMARY = {
    "decoded_instruction_count": 237,
    "decoded_basic_block_count": 40,
    "reachable_instruction_bytes": 508,
    "frontier_count": 0,
    "external_call_edge_count": 17,
    "target_producer_edge_count": 1,
    "opaque_boundary_edge_count": 1,
    "instruction_internal_edge_count": 251,
}
SOURCE_HASHES = {
    "packed_instruction_bytes_sha256": "45b2ec5ee53d3583d2e641ae5d1190045a541af0877462e2f509304f592fa158",
    "semantic_instruction_vector_sha256": "bede899464bca87e2fde14ff8492eadf4735538963f3c3b8e5895552aec5e576",
    "block_range_vector_sha256": "fb3c471b6695529759b6d18103ee733a1d0b0a9a97bd9a90f62449fbcb07b4f2",
    "instruction_internal_edge_vector_sha256": "4135e4f261905b1532bf59e598ac65253bf2461e560d03d2930cf4a3ff30d1f3",
    "external_edge_vector_sha256": "f41f0b5d1826f3c8d18a70e2c0959f31052b0a76a7d07b9ba38ffa0de8a3d48d",
}

TARGET_ROOT = 414_200
TARGET_ROOT_RAW = "f0b54746"
TARGET_ROOT_SHA256 = "3e7ec2098933d96de8dc658d119ed3848ccdd7942f96f2a0d015f1e68e3c759b"
TARGET_ENVELOPE = (414_200, 414_596)
TARGET_ENVELOPE_SHA256 = "838fd74b07984a3a692f3fb66e72f1b4d6d7c7c5ad791934c3827ca7e968b10e"
TARGET_CODE_RANGES = [
    [414_200, 414_268],
    [414_284, 414_430],
    [414_472, 414_570],
]
TARGET_LITERAL_RANGES = [
    [414_268, 414_284],
    [414_432, 414_472],
    [414_572, 414_596],
]
TARGET_PROMOTION_RANGES = [
    [414_200, 414_268],
    [414_268, 414_284],
    [414_284, 414_430],
    [414_432, 414_472],
    [414_472, 414_570],
    [414_572, 414_596],
]
TARGET_BLOCKS = [
    [414_200, 414_220], [414_220, 414_222], [414_222, 414_236], [414_236, 414_242],
    [414_242, 414_250], [414_250, 414_264], [414_264, 414_268], [414_284, 414_288],
    [414_288, 414_300], [414_300, 414_304], [414_304, 414_306], [414_306, 414_316],
    [414_316, 414_324], [414_324, 414_344], [414_344, 414_362], [414_362, 414_368],
    [414_368, 414_382], [414_382, 414_390], [414_390, 414_430], [414_472, 414_512],
    [414_512, 414_522], [414_522, 414_536], [414_536, 414_556], [414_556, 414_560],
    [414_560, 414_570],
]
TARGET_BLOCK_RANGE_SHA256 = "fae253e64395d30da0ed5988fdaa2f553dd4ac0216de710d543b03e8b57b200e"
TARGET_CODE_RANGE_SHA256 = "1eb89efbb94cb9f1a7ecbcfad992dfeb3ff49c84f918d52b715a87f25fcd89f4"
TARGET_LITERAL_RANGE_SHA256 = "f34a55f4703f8b17f969d13aa02fd9aa1b1d1264a52ca8267dbd688ee6658f88"
TARGET_PROMOTION_RANGE_SHA256 = "09f8682f0e4bab0db4108820c4034abf45e345e05f9e7bd9c4111cc2054114c0"
TARGET_INSTRUCTION_INTERNAL_SHA256 = "27ae4a890679ccafeb65a38f512757c35faf18fe4dd8540581c073468b4eb1d4"
TARGET_BLOCK_INTERNAL_SHA256 = "d71a01f074ed0b403748e311425936768ec5df8ae4971b614e66766c7c685681"
TARGET_EXTERNAL_SHA256 = "6d9235d9594d1a1124aaef710d1d29f4b2c8edc4f0f56699bc6c0d10561983aa"
TARGET_FRONTIER_SHA256 = "76d3c99e0143cccffef136d057794fe0863bb4e775b880b7d632515547b992b8"
TARGET_SEMANTIC_SHA256 = "4fe44f3fb076b347b7d641a02a01cd9978880414253ad0664f6c7a870bab449f"
TARGET_LITERAL_BINDING_SHA256 = "4eac0d84e979e591c789d522c21df22d06a8274817d0ca9943c45ea6a2f7ee84"
TARGET_PACKED_CODE_SHA256 = "c0fd79364221d43e831d33b5266bad1bc2fefe9249c10313ce06d812bd712bcb"
TARGET_PACKED_LITERAL_SHA256 = "3ad57b1bb869ecd47546e6f220201414fc68c0727742cee023e8feb640e59546"
TARGET_PACKED_PROMOTION_SHA256 = "d7449f4feb51fa169d011c0692d2009090633aa8cf7968064bd36063be491e40"
TARGET_HOLES = [
    {
        "range": [414_430, 414_432],
        "raw_hex": "0000",
        "sha256": "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    },
    {
        "range": [414_570, 414_572],
        "raw_hex": "0000",
        "sha256": "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    },
]
HOLE_RANGES = [row["range"] for row in TARGET_HOLES]
FRONTIERS = [[414_568, "indirect_pc_target"]]

SCOPE_EXPECTED = {
    "source_worklist_bounded_to_accepted_slice": True,
    "source_producer_edge_rebuilt_from_raw_rom": True,
    "target_worklist_bounded_to_frozen_envelope": True,
    "target_producer_denominator_complete_for_fixed_target": True,
    "literal_bindings_rebuilt_from_raw_rom": True,
    "single_indirect_pc_frontier_is_explicit_and_unresolved": True,
    "two_holes_excluded_from_promotion": True,
    "promotion_window_complete_except_explicit_holes": True,
    "current_known_overlap_bytes": 0,
    "structured_return_proven": False,
    "runtime_reachability_complete": False,
    "global_code_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "callee_semantics_proven": False,
    "literal_business_meaning_proven": False,
    "hole_semantics_proven": False,
    "editing_relocation_safe": False,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _offset(value: object) -> int:
    if isinstance(value, dict):
        return int(value.get("file_offset", value.get("offset")))
    return int(value)


def _raw_hex(value: object) -> str:
    if isinstance(value, dict):
        return str(value["entry_raw_hex"])
    return str(value)


def _entry_sha(value: object) -> str:
    if isinstance(value, dict):
        return str(value["entry_sha256"])
    return str(value)


class CfgProvenRootsV13ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = cls.exporter.build_cfg_proven_roots_v13_payload(ROOT)

    def _export(self, parent: Path) -> Path:
        output = parent / "candidate"
        self.exporter.export_rom_cfg_proven_roots_v13(ROOT, output)
        return output

    def test_frozen_rom_coverage_upstream_source_and_scope_contract(self) -> None:
        self.assertEqual(ROM_SIZE, self.exporter.ROM_SIZE)
        self.assertEqual(ROM_SHA256, self.exporter.ROM_SHA256)
        self.assertEqual("rom-cfg-proven-roots-v13", self.payload["schema"])
        self.assertEqual(
            {"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256},
            self.payload["rom"],
        )

        coverage = self.payload["coverage_baseline"]
        for key, value in COVERAGE_EXPECTED.items():
            self.assertEqual(value, coverage[key], key)

        upstream = self.payload["upstream"]
        for key, value in UPSTREAM_EXPECTED.items():
            self.assertEqual(value, upstream[key], key)

        source = self.payload["source"]
        self.assertEqual(list(SOURCE_RANGE), source["range"])
        self.assertEqual(SOURCE_SLICE_SHA256, source["slice_sha256"])
        self.assertEqual(398_012, _offset(source["root"]))
        self.assertEqual(398_544, source["accepted_producer_file_offset"])
        self.assertEqual(SOURCE_REACHABLE_RANGES, source["reachable_ranges"])
        self.assertEqual([], source["frontiers"])
        for key, value in SOURCE_HASHES.items():
            self.assertEqual(value, source[key], key)
        for key, value in SOURCE_SUMMARY.items():
            self.assertEqual(value, source["summary"][key], key)
        self.assertEqual(
            {
                "source_file_offset": 398_560,
                "target_file_offset": 398_564,
                "edge_kind": "opaque_boundary",
                "reason": "accepted_owner_beginning",
            },
            source["opaque_boundary"],
        )

        scope = self.payload["scope"]
        for key, value in SCOPE_EXPECTED.items():
            self.assertEqual(value, scope[key], key)

    def test_target_code_literals_promotion_holes_blocks_and_frontier(self) -> None:
        target = self.payload["target"]
        self.assertEqual(TARGET_ROOT, _offset(target["root"]))
        self.assertEqual(TARGET_ROOT_RAW, target.get("root_raw_hex", _raw_hex(target["root"])))
        self.assertEqual(TARGET_ROOT_SHA256, target.get("root_sha256", _entry_sha(target["root"])))
        self.assertEqual(list(TARGET_ENVELOPE), target["envelope"])
        self.assertEqual(396, target["envelope_bytes"])
        self.assertEqual(TARGET_ENVELOPE_SHA256, target["envelope_sha256"])
        self.assertEqual(TARGET_CODE_RANGES, target["code_ranges"])
        self.assertEqual(TARGET_LITERAL_RANGES, target["literal_ranges"])
        self.assertEqual(TARGET_PROMOTION_RANGES, target["promotion_ranges"])
        self.assertEqual(TARGET_BLOCKS, target["block_ranges"])
        self.assertEqual(TARGET_BLOCK_RANGE_SHA256, target["block_range_vector_sha256"])
        self.assertEqual(TARGET_CODE_RANGE_SHA256, target["code_range_vector_sha256"])
        self.assertEqual(TARGET_LITERAL_RANGE_SHA256, target["literal_range_vector_sha256"])
        self.assertEqual(TARGET_PROMOTION_RANGE_SHA256, target["promotion_range_vector_sha256"])
        self.assertEqual(TARGET_INSTRUCTION_INTERNAL_SHA256, target["instruction_internal_edge_vector_sha256"])
        self.assertEqual(TARGET_BLOCK_INTERNAL_SHA256, target["block_internal_edge_vector_sha256"])
        self.assertEqual(TARGET_EXTERNAL_SHA256, target["external_edge_vector_sha256"])
        self.assertEqual(TARGET_FRONTIER_SHA256, target["frontier_vector_sha256"])
        self.assertEqual(TARGET_SEMANTIC_SHA256, target["semantic_instruction_vector_sha256"])
        self.assertEqual(TARGET_LITERAL_BINDING_SHA256, target["literal_binding_vector_sha256"])
        self.assertEqual(TARGET_PACKED_CODE_SHA256, target["packed_code_sha256"])
        self.assertEqual(TARGET_PACKED_LITERAL_SHA256, target["packed_literals_sha256"])
        self.assertEqual(TARGET_PACKED_PROMOTION_SHA256, target["packed_promotion_sha256"])
        self.assertEqual(TARGET_HOLES, target["holes"])
        self.assertEqual(FRONTIERS, target["frontiers"])
        self.assertNotIn("structured_return", target)

        summary = target["summary"]
        self.assertEqual(
            {
                "decoded_instruction_count": 153,
                "decoded_basic_block_count": 25,
                "reachable_instruction_bytes": 312,
                "frontier_count": 1,
                "instruction_internal_edge_count": 164,
                "block_internal_edge_count": 36,
                "external_call_edge_count": 3,
                "literal_reference_count": 21,
                "unique_literal_word_count": 20,
                "literal_bytes": 80,
                "promotion_range_count": 6,
                "promotion_bytes": 392,
                "hole_bytes": 4,
            },
            summary,
        )
        for hole in HOLE_RANGES:
            self.assertNotIn(hole, target["promotion_ranges"])
            self.assertFalse(any(start <= hole[0] and hole[1] <= end for start, end in target["code_ranges"]))
            self.assertFalse(any(start <= hole[0] and hole[1] <= end for start, end in target["literal_ranges"]))
        self.assertEqual(1, len(target["frontiers"]))
        self.assertEqual(414_568, target["frontiers"][0][0])
        self.assertEqual("indirect_pc_target", target["frontiers"][0][1])

    def test_producer_denominator_and_literals_are_rebuilt_from_raw_rom(self) -> None:
        denominator = self.exporter._producer_denominator(self.rom)
        self.assertEqual([0, ROM_SIZE], denominator["scan"]["range"])
        self.assertEqual(2, denominator["scan"]["alignment_bytes"])
        self.assertEqual("thumb", denominator["scan"]["mode"])
        self.assertEqual(1, denominator["scan"]["matching_producer_count"])
        self.assertEqual([TARGET_ROOT], denominator["scan"]["target_file_offsets"])
        self.assertEqual([398_544], [
            row if isinstance(row, int) else row["file_offset"]
            for row in denominator["thumb_bl"]
        ])
        for key in ("thumb_b", "thumb_bcond", "arm_b_bl", "aligned_arm_pointers", "thumb_pointers"):
            self.assertEqual([], denominator[key], key)
        self.assertEqual([[398_544, TARGET_ROOT, "thumb_bl"]], denominator["vector"])
        self.assertEqual("4c0df27279aa18befd77dbc2c4a4a2997dce603548c2d97879d517aa857d681f", denominator["vector_sha256"])
        self.assertEqual("03f092fe", denominator.get("producer_raw_hex", denominator["thumb_bl"][0]["raw_hex"]))
        self.assertEqual("d9bd4f7a9eef6b4224a1d630a698ccec615fc19dd002c390d3c46b047a84ba4b", denominator.get("producer_sha256", denominator["thumb_bl"][0]["bytes_sha256"]))

        projection = self.exporter._target_worklist(self.rom)["literal_projection"]
        self.assertEqual(21, projection["literal_reference_count"])
        self.assertEqual(20, projection["unique_literal_word_count"])
        self.assertEqual(80, projection["bytes"])
        self.assertEqual(TARGET_LITERAL_BINDING_SHA256, projection["binding_vector_sha256"])

    def test_promotion_contract_and_atomic_artifact_manifest(self) -> None:
        promotion = self.payload["promotion"]
        self.assertEqual("cfg-proven-roots-v13", promotion["batch"])
        self.assertEqual(TARGET_PROMOTION_RANGES, promotion["ranges"])
        self.assertEqual(6, promotion["promotion_range_count"])
        self.assertEqual(392, promotion["promotion_bytes"])
        self.assertEqual(312, promotion["promotion_code_bytes"])
        self.assertEqual(80, promotion["promotion_literal_bytes"])
        self.assertEqual(4, promotion["hole_bytes"])
        self.assertEqual(4, promotion["unclassified_hole_bytes"])
        self.assertEqual(TARGET_PACKED_PROMOTION_SHA256, promotion["packed_sha256"])
        self.assertEqual(TARGET_PROMOTION_RANGE_SHA256, promotion["range_vector_sha256"])

        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = self._export(Path(raw))
            manifest = json.loads((output / "manifest.json").read_text())
            payload_raw = (output / PAYLOAD_NAME).read_bytes()
            self.assertEqual("git-artifact-promotion-v1", manifest["schema"])
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(
                {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
                manifest["files"],
            )
            self.assertEqual(manifest, experiment_workspace._validate_promotion_manifest(output))
            report = self.verifier.verify_rom_cfg_proven_roots_v13(ROOT, output)
            self.assertTrue(report["verified"])
            self.assertEqual(report, manifest["verifier"]["report"])

    def test_failed_verification_does_not_leave_partial_artifact(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            with mock.patch.object(
                self.exporter,
                "_run_isolated_verifier",
                side_effect=ValueError("forced independent verifier failure"),
            ), self.assertRaisesRegex(ValueError, "forced independent verifier failure"):
                self.exporter.export_rom_cfg_proven_roots_v13(ROOT, output)
            self.assertFalse(output.exists())

    def test_failed_accepted_postflight_restores_prior_artifact_without_debris(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            output = self._export(parent)
            before = {
                path.relative_to(output).as_posix(): path.read_bytes()
                for path in output.rglob("*")
                if path.is_file()
            }
            with mock.patch.object(
                self.exporter,
                "_run_isolated_verifier",
                side_effect=[
                    dict(self.exporter.EXPECTED_REPORT),
                    ValueError("forced accepted postflight failure"),
                ],
            ), self.assertRaisesRegex(
                ValueError, "forced accepted postflight failure"
            ):
                self.exporter.export_rom_cfg_proven_roots_v13(ROOT, output)
            after = {
                path.relative_to(output).as_posix(): path.read_bytes()
                for path in output.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertEqual([output], list(parent.iterdir()))

    def test_output_symlink_foreign_and_verifier_independence(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            linked_target = parent / "real"
            linked_target.mkdir()
            linked = parent / "linked"
            linked.symlink_to(linked_target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.exporter.export_rom_cfg_proven_roots_v13(ROOT, linked / "candidate")
            foreign = parent / "foreign"
            foreign.mkdir()
            (foreign / "foreign.txt").write_text("do not replace")
            with self.assertRaisesRegex(ValueError, "foreign"):
                self.exporter.export_rom_cfg_proven_roots_v13(ROOT, foreign)

        verifier_source = (ROOT / "tools/verify_rom_cfg_proven_roots_v13.py").read_text()
        tree = ast.parse(verifier_source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("export_rom_cfg_proven_roots_v13" in name for name in imports))

    def test_cli_requires_isolated_runtime(self) -> None:
        script = ROOT / "tools/export_rom_cfg_proven_roots_v13.py"
        ordinary = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, ordinary.returncode)
        self.assertIn("requires Python -I -S", ordinary.stdout + ordinary.stderr)
        isolated = subprocess.run(
            [sys.executable, "-I", "-S", str(script), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, isolated.returncode, isolated.stdout + isolated.stderr)

    def test_raw_rom_mutations_fail_during_independent_rebuild(self) -> None:
        for offset, helper in (
            (398_544, self.exporter._producer_denominator),
            (414_200, self.exporter._target_worklist),
            (414_430, self.exporter._target_worklist),
            (414_568, self.exporter._target_worklist),
            (414_572, self.exporter._target_worklist),
        ):
            mutated = bytearray(self.rom)
            mutated[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaises(ValueError):
                helper(bytes(mutated))

    def test_source_and_target_digest_contracts_are_recomputed(self) -> None:
        for product in (self.exporter, self.verifier):
            with self.subTest(product=product.__name__), mock.patch.object(
                product,
                "SOURCE_OPAQUE_BOUNDARY_SHA256",
                "0" * 64,
            ), self.assertRaisesRegex(ValueError, "source opaque boundary vector changed"):
                product._source_worklist(self.rom)


if __name__ == "__main__":
    unittest.main()
