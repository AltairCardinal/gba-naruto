#!/usr/bin/env python3
"""TDD RED contract for the fixed tick-callback CFG proven-roots v11 packet."""

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
from unittest.mock import patch

import tools.experiment_workspace as experiment_workspace
import tools.export_rom_cfg_proven_roots_v11 as exporter_v11
import tools.verify_rom_cfg_proven_roots_v11 as verifier_v11
from tools.verify_battle_effect_sprite_animations import (
    verify_battle_effect_sprite_animations,
)


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v11"
PAYLOAD_NAME = "rom-cfg-proven-roots-v11.json"
SCHEMA = "rom-cfg-proven-roots-v11"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v11"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "c65ec320a432681600bda916254f3265489829ee2f0b8b885b885b5436d35396"

SOURCE_SLICE = (0x080554, 0x080A46)
SOURCE_SLICE_SHA256 = "22aae5132d081d89b9e9315968c1d3d089131b269ae1f5cfa232d1d6d13b8c8a"
SOURCE_ROOT_VECTOR_SHA256 = "a7713d600741b0dd4c0d7ada7d59086252a9821e33436efced0e23da7c1048b4"
SOURCE_EXTERNAL_VECTOR_SHA256 = "0cb2da1c57effcb48910685b26bcc1331ecf923f34f65b9a0bb27b3be1ccb97b"
SOURCE_BLOCK_VECTOR_SHA256 = "16b4561b090a9a5cfda78923813e32c7c6c3a37fc8c67fdf7a1a63159cab3304"

SOURCE_SPECS = (
    (0x08055C, 0x08065E, 0x08064E, "f0b54f46", "8a1d56a49bd75817476a967ee4e23ecef2beeffa6748599c19bc8e7ed7620257", 118, 18, 250, "7a01382c7739a24b78e164c0eaee5367271a670b8ddfe81aa2e32adca7467855", "6b4b7326c82b01d30f7486b3ac98a158cea94b349296b888bbb71f40541cbaab"),
    (0x080670, 0x080762, 0x08072A, "f0b54746", "3e7ec2098933d96de8dc658d119ed3848ccdd7942f96f2a0d015f1e68e3c759b", 105, 16, 216, "59153c8ce6f6b295552306667c61f79d34ee452a1ef06224f533e37db2d988e1", "45102ed7d9db0d567b80b174209103bb251d4f5242804111de14d31be2f25ff7"),
    (0x080764, 0x080812, 0x0807E8, "f0b584b0", "9a03127c7ccf0b8c4ec43474f7c075704e096f385c54c0b7c78017896afb9ff1", 80, 14, 166, "02a7c6463fc9d948eeb2d221a398392369d5e356215cbc0c042322d774979c49", "d3fb9be1bfa4693ce65065e610f16f02ee1f531d50e3f3d5fc517eaaa6c32348"),
    (0x080814, 0x0808BA, 0x080892, "f0b584b0", "9a03127c7ccf0b8c4ec43474f7c075704e096f385c54c0b7c78017896afb9ff1", 77, 14, 160, "cd5e36e8e49373c003b4f1fdf27624f27904117594c8261c187489fd62454da2", "a91f164f2c83abb0190d00be3253bea1df8542ce09f0d690af68937b97ad14e7"),
    (0x0808C4, 0x080910, 0x080906, "30b584b0", "16d0e16c7269b3ae4e0b97c4aeb7103382fed757c0ee6ad513b0f7ebe3eef78e", 33, 7, 72, "b0d527d91abee77e0289b27ebb646766fc5dd4cb706e4cf6d28a7c0ebebd4d94", "c4a8e1dd07595a3fa9cf237b4c809a9d99a0622eaf1f445baa3cfc4882daedc4"),
    (0x080914, 0x080960, 0x080956, "30b584b0", "16d0e16c7269b3ae4e0b97c4aeb7103382fed757c0ee6ad513b0f7ebe3eef78e", 34, 7, 74, "33aa9c6b234de8d338d15993694ba8ba643fe4ebfa93e2921e12c8f3158cca80", "1e51f1334f8f5eddc8afbede0d56e582d5f320fd8218cbb8a741d18e39a6e547"),
    (0x080964, 0x0809F0, 0x0809E6, "30b584b0", "16d0e16c7269b3ae4e0b97c4aeb7103382fed757c0ee6ad513b0f7ebe3eef78e", 55, 9, 116, "1080c3a19046bc8c83fb1d0a73a5a6668d8a19ae0459eaece05dfb00494ff3dd", "f48d1f3aae17dec106cb35f5f4cc28fc72f792f8d019785b5de5757ece3ad497"),
    (0x0809F4, 0x080A44, 0x080A3A, "30b584b0", "16d0e16c7269b3ae4e0b97c4aeb7103382fed757c0ee6ad513b0f7ebe3eef78e", 35, 7, 76, "672b5be4716ff294b79b1a272f38400e613a69a48f252692a82173619772eadc", "852227b2a297cad00a486e58274b0733c7d4bbc95b491dcf006b4da48eeeb923"),
)

PRODUCERS = {
    0x08064E: ("e2f7b7fe", "e9569ef5f484cb3614fec0f1004df2d54775972c8fbd4c96c095ceb33bf016a5", "accepted_fixed_tick_callback_closure"),
    0x08072A: ("e2f749fe", "4c6c3403d646884caa3097d9e9732b6ac98135bf81ed7d1ea35c43996764ffd7", "accepted_fixed_tick_callback_closure"),
    0x0807E8: ("e2f7eafd", "b8df4590b05b8b4e137fb92ac8dd2578f67247c2add3ad7ae1b4412bf369c3e2", "accepted_fixed_tick_callback_closure"),
    0x080892: ("e2f795fd", "166e76fd67e3b9189f019203d188872184c09009ce26d4c65c2efd22085daa72", "accepted_fixed_tick_callback_closure"),
    0x080906: ("e2f75bfd", "be6392d8ccb6312b98222178231f8035d0a5c87578e426b75409411bd5c8cce3", "accepted_fixed_tick_callback_closure"),
    0x080956: ("e2f733fd", "48f6cd4792b0a94eb736207a3649d8ec2581b56048fbc65de382d95bb9c7859b", "accepted_fixed_tick_callback_closure"),
    0x0809E6: ("e2f7ebfc", "259386b428280f08c3c5c92ab6ad1bdf63d31bfd82a6ae37ea6431574347e4e9", "accepted_fixed_tick_callback_closure"),
    0x080A3A: ("e2f7c1fc", "ce0b0e41d69429b983a88bdafe6972e6c025537cf6df7b636f71a8074c4a49dd", "accepted_fixed_tick_callback_closure"),
    0x080D7C: ("e2f720fb", "81e18c23989b5a1c06a9d1f8a732628bc30726c1c7e76a814ec02d6fbca7c054", "excluded_unproven_source"),
}
PRODUCER_DENOMINATOR_SHA256 = "c6bf31a08f115718087652e182d97efd33807202785548b5100bda0e8e2d8851"

TARGET = (0x0633C0, 0x0633FE)
TARGET_SHA256 = "bce5dad093cbcf2447728c50288b94fb47140fe452f6846f83b7224220dfb5cd"
TARGET_ROOT_SHA256 = "df4b34ae82a0188510cc4ac861082202afc6dda014c718f38abd68912aebdf96"
TARGET_BLOCK_SHA256 = "4cdafc34a251971c6edec8d98dbf812042ccaab70e1ec3ee663976301a5a86c6"
TARGET_BLOCKS = [[0x0633C0, 0x0633D0], [0x0633D0, 0x0633DE], [0x0633DE, 0x0633E8], [0x0633E8, 0x0633EE], [0x0633EE, 0x0633F8], [0x0633F8, 0x0633FE]]
RETURN_PREFIX = "01bc0047"
RETURN_SHA256 = "15a0c45072c4f43ac42d0c62cb597469cb73ae8294c056a31dc8415af2bc0d3c"

UPSTREAM = {
    "artifact_schema": "battle-effect-sprite-animations-v1",
    "manifest_path": "artifacts/battle-effect-sprite-animations-v1/manifest.json",
    "manifest_sha256": "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848",
    "verifier_path": "tools/verify_battle_effect_sprite_animations.py",
    "verifier_sha256": "ba22259f41e53398a0f271f806c831b5eaf0052f17784c831d2591c0220f0c6b",
    "verification_schema": "battle-effect-sprite-animations-verification-v1",
    "consumer_slice_name": "all_effect_descriptor_callbacks",
    "consumer_slice_range": list(SOURCE_SLICE),
    "consumer_slice_sha256": SOURCE_SLICE_SHA256,
    "playback_plan_count": 22,
    "non_null_tick_slot_count": 21,
    "unique_tick_root_count": 8,
}

EXPECTED_REPORT = {
    "schema": VERIFY_SCHEMA,
    "verified": True,
    "errors": [],
    "control_flow_oracle": "armv4t-raw-encoding",
    "raw_target_producer_count": 9,
    "accepted_target_producer_count": 8,
    "excluded_unproven_source_count": 1,
    "source_root_count": 8,
    "source_decoded_instruction_count": 537,
    "source_decoded_basic_block_count": 92,
    "source_reachable_instruction_bytes": 1130,
    "source_frontier_count": 0,
    "source_external_call_edge_count": 28,
    "independently_rebuilt_instruction_count": 30,
    "decoded_basic_block_count": 6,
    "reachable_instruction_bytes": 62,
    "frontier_count": 0,
    "external_call_edge_count": 1,
}


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def canonical_sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


class RomCfgProvenRootsV11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.payload = exporter_v11.build_cfg_proven_roots_v11_payload(ROOT)

    def _export(self, temporary: str | Path) -> Path:
        output = Path(temporary) / "candidate"
        exporter_v11.export_rom_cfg_proven_roots_v11(ROOT, output)
        return output

    def test_rom_upstream_and_tick_roots_are_frozen(self) -> None:
        self.assertEqual(ROM_SIZE, exporter_v11.ROM_SIZE)
        self.assertEqual(ROM_SHA256, exporter_v11.ROM_SHA256)
        self.assertEqual(SCHEMA, self.payload["schema"])
        self.assertEqual({"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256}, self.payload["rom"])
        report = verify_battle_effect_sprite_animations(ROOT, ROOT / "artifacts/battle-effect-sprite-animations-v1")
        self.assertTrue(report["verified"], report)
        self.assertEqual(UPSTREAM["verification_schema"], report["schema"])
        self.assertEqual([], report["errors"])
        self.assertEqual(UPSTREAM, self.payload["upstream"])
        manifest = json.loads((ROOT / UPSTREAM["manifest_path"]).read_text())
        tick = [int(item["tick_callback_thumb"], 16) for item in manifest["sequence_playback_plans"]]
        roots = sorted({value - 0x08000000 & ~1 for value in tick if value})
        self.assertEqual([spec[0] for spec in SOURCE_SPECS], roots)

    def test_full_rom_denominator_keeps_ninth_raw_match_explicitly_excluded(self) -> None:
        denominator = exporter_v11._producer_denominator(self.rom)
        self.assertEqual("thumb", denominator["scan"]["mode"])
        self.assertEqual(2, denominator["scan"]["alignment_bytes"])
        self.assertEqual([0, ROM_SIZE], denominator["scan"]["range"])
        self.assertEqual(9, denominator["scan"]["matching_producer_count"])
        self.assertEqual([0x0633C0], denominator["scan"]["target_file_offsets"])
        independent_matches = []
        for offset in range(0, len(self.rom) - 3, 2):
            first = int.from_bytes(self.rom[offset : offset + 2], "little")
            second = int.from_bytes(self.rom[offset + 2 : offset + 4], "little")
            if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
                continue
            displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
            if displacement & 0x400000:
                displacement -= 0x800000
            if offset + 4 + displacement == TARGET[0]:
                independent_matches.append(offset)
        self.assertEqual(list(PRODUCERS), independent_matches)
        records = {item["file_offset"]: item for item in denominator["producers"]}
        self.assertEqual(set(PRODUCERS), set(records))
        for offset, (raw, digest, status) in PRODUCERS.items():
            self.assertEqual(raw, records[offset]["raw_hex"])
            self.assertEqual(digest, records[offset]["bytes_sha256"])
            self.assertEqual(status, records[offset]["status"])
            self.assertEqual(0x0633C0, records[offset]["target_file_offset"])
        excluded = records[0x080D7C]
        self.assertEqual("excluded_unproven_source", excluded["status"])
        self.assertNotIn("instruction", excluded)
        self.assertEqual(8, sum(item["status"].startswith("accepted_") for item in records.values()))
        self.assertEqual(PRODUCER_DENOMINATOR_SHA256, denominator["denominator_sha256"])
        self.assertEqual(denominator["denominator_sha256"], canonical_sha(denominator["producers"]))
        tampered = bytearray(self.rom)
        tampered[0x080D7C] ^= 1
        with self.assertRaisesRegex(ValueError, "denominator|producer|changed"):
            exporter_v11._producer_denominator(bytes(tampered))

    def test_eight_source_closures_are_frozen_and_each_accepts_one_producer(self) -> None:
        source = exporter_v11._source_worklists(self.rom)
        self.assertEqual(list(SOURCE_SLICE), source["range"])
        self.assertEqual(SOURCE_SLICE_SHA256, source["slice_sha256"])
        self.assertEqual(SOURCE_ROOT_VECTOR_SHA256, source["root_vector_sha256"])
        self.assertEqual(SOURCE_EXTERNAL_VECTOR_SHA256, source["external_vector_sha256"])
        self.assertEqual(SOURCE_BLOCK_VECTOR_SHA256, source["block_range_vector_sha256"])
        summary = source["summary"]
        self.assertEqual((8, 537, 92, 1130, 0, 28), (summary["root_count"], summary["decoded_instruction_count"], summary["decoded_basic_block_count"], summary["reachable_instruction_bytes"], summary["frontier_count"], summary["external_call_edge_count"]))
        closures = {item["root"]["file_offset"]: item for item in source["closures"]}
        all_external = []
        all_block_ranges = []
        for root, return_bx, producer, raw, entry_sha, insn, blocks, size, block_sha, external_sha in SOURCE_SPECS:
            closure = closures[root]
            self.assertEqual(raw, closure["root"]["entry_raw_hex"])
            self.assertEqual(entry_sha, closure["root"]["entry_sha256"])
            self.assertEqual(producer, closure["accepted_producer_file_offset"])
            self.assertEqual(return_bx, closure["return"]["bx_file_offset"])
            self.assertEqual((insn, blocks, size, 0), (closure["summary"]["decoded_instruction_count"], closure["summary"]["decoded_basic_block_count"], closure["summary"]["reachable_instruction_bytes"], closure["summary"]["frontier_count"]))
            self.assertEqual(block_sha, closure["block_range_sha256"])
            self.assertEqual(external_sha, closure["external_vector_sha256"])
            accepted = [edge for edge in closure["external_edges"] if edge["reason"] == "target_producer"]
            self.assertEqual([producer], [edge["source_file_offset"] for edge in accepted])
            self.assertEqual([TARGET[0]], [edge["target_file_offset"] for edge in accepted])
            self.assertEqual(["thumb"], [edge["target_mode"] for edge in accepted])
            self.assertEqual(["call_target"], [edge["edge_kind"] for edge in accepted])
            all_external.extend(closure["external_edges"])
            all_block_ranges.extend(block["range"] for block in closure["blocks"])
        self.assertNotIn(0x080D7C, [edge["source_file_offset"] for edge in all_external])
        canonical_external = [
            {key: value for key, value in edge.items() if key != "source_file_offset"}
            for edge in all_external
        ]
        self.assertEqual(SOURCE_ROOT_VECTOR_SHA256, canonical_sha(list(closures)))
        self.assertEqual(SOURCE_EXTERNAL_VECTOR_SHA256, canonical_sha(canonical_external))
        self.assertEqual(SOURCE_BLOCK_VECTOR_SHA256, canonical_sha(all_block_ranges))

    def test_target_exact_closure_and_opaque_baseline_call_are_frozen(self) -> None:
        target = exporter_v11._target_worklist(self.rom)
        self.assertEqual(list(TARGET), target["envelope"])
        self.assertEqual(TARGET_SHA256, target["envelope_sha256"])
        self.assertEqual("30b5051c", target["root"]["entry_raw_hex"])
        self.assertEqual(TARGET_ROOT_SHA256, target["root"]["entry_sha256"])
        self.assertEqual(TARGET_BLOCKS, target["code_ranges"])
        self.assertEqual(TARGET_BLOCK_SHA256, target["block_range_sha256"])
        self.assertEqual((30, 6, 62, 0, 1), (target["summary"]["decoded_instruction_count"], target["summary"]["decoded_basic_block_count"], target["summary"]["reachable_instruction_bytes"], target["summary"]["frontier_count"], target["summary"]["external_call_edge_count"]))
        self.assertEqual([{"source_file_offset": 0x0633EA, "target_file_offset": 0x062788, "reason": "opaque_baseline_callee"}], [{key: edge[key] for key in ("source_file_offset", "target_file_offset", "reason")} for edge in target["external_edges"]])
        self.assertEqual(0x0633FC, target["return"]["bx_file_offset"])
        self.assertEqual(RETURN_PREFIX, target["return"]["prefix_hex"])
        self.assertEqual(RETURN_SHA256, target["return"]["prefix_sha256"])
        for offset in (0x0633C0, 0x0633EA, 0x0633FA):
            tampered = bytearray(self.rom)
            tampered[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "target|return|changed"):
                exporter_v11._target_worklist(bytes(tampered))

    def test_coverage_baseline_promotes_only_62_unknown_target_bytes(self) -> None:
        baseline = self.payload["coverage_baseline"]
        self.assertEqual("sequel/rom-byte-coverage.json", baseline["path"])
        self.assertEqual(COVERAGE_SHA256, baseline["sha256"])
        self.assertEqual(list(TARGET), baseline["promotion_envelope"])
        self.assertEqual(62, baseline["current_unknown_bytes"])
        self.assertEqual(0, baseline["current_known_overlap_bytes"])
        self.assertEqual(62, baseline["promotion_bytes"])
        self.assertEqual(62, baseline["promotion_code_bytes"])
        self.assertEqual(0, baseline["promotion_literal_bytes"])
        self.assertEqual(62, self.payload["promotion"]["promotion_bytes"])
        self.assertEqual(list(TARGET), self.payload["promotion"]["envelope"])
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            temp_root = Path(temporary)
            coverage_path = temp_root / "sequel/rom-byte-coverage.json"
            coverage_path.parent.mkdir(parents=True)
            coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
            for segment in coverage["segments"]:
                start, end = segment["range"]
                if start <= TARGET[0] and TARGET[1] <= end:
                    segment["primary_class"] = "synthetic_known"
            raw = canonical_json(coverage)
            coverage_path.write_bytes(raw)
            with patch.object(exporter_v11, "COVERAGE_SHA256", hashlib.sha256(raw).hexdigest()):
                with self.assertRaisesRegex(ValueError, "known|overlap"):
                    exporter_v11._coverage_baseline(temp_root, [list(TARGET)])

    def test_payload_manifest_standard_promotion_and_self_hashes(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = self._export(temporary)
            payload_raw = (output / PAYLOAD_NAME).read_bytes()
            payload = json.loads(payload_raw)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual({"schema", "rom", "upstream", "producer_denominator", "source", "target", "promotion", "coverage_baseline", "implementation", "scope"}, set(payload))
            self.assertEqual(PROMOTION_SCHEMA, manifest["schema"])
            self.assertEqual(SCHEMA, manifest["artifact_schema"])
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual({PAYLOAD_NAME: hashlib.sha256(payload_raw).hexdigest()}, manifest["files"])
            self.assertEqual(manifest, experiment_workspace._validate_promotion_manifest(output))
            self.assertEqual(EXPECTED_REPORT, manifest["verifier"]["report"])
            self.assertEqual(EXPECTED_REPORT, verifier_v11.verify_rom_cfg_proven_roots_v11(ROOT, output))
            implementation = exporter_v11._implementation(ROOT)
            self.assertEqual(implementation, verifier_v11._implementation(ROOT))
            self.assertEqual(implementation, payload["implementation"])
            for label in ("exporter", "verifier", "test"):
                relative = Path(implementation["paths"][label])
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), implementation[f"{label}_sha256"])
            for receipt, flag in ((manifest["producer"], "--output-dir"), (manifest["verifier"], "--artifact-dir")):
                self.assertEqual(["python3", "-I", "-S"], receipt["command"][:3])
                self.assertIn(flag, receipt["command"])
                self.assertEqual(output.relative_to(ROOT).as_posix(), receipt["command"][-1])

    def test_promoted_copy_verifies_and_tamper_or_extra_file_fails_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            output = self._export(temporary)
            with tempfile.TemporaryDirectory(dir=ROOT / "artifacts", prefix=".cfg-v11-promotion-copy-") as parent:
                promoted = Path(parent) / "rom-cfg-proven-roots-v11"
                shutil.copytree(output, promoted)
                self.assertEqual(EXPECTED_REPORT, verifier_v11.verify_rom_cfg_proven_roots_v11(ROOT, promoted))
            payload_path = output / PAYLOAD_NAME
            manifest_path = output / "manifest.json"
            original_payload = payload_path.read_bytes()
            original_manifest = manifest_path.read_bytes()
            payload = json.loads(original_payload)
            payload["producer_denominator"]["producers"][-1]["status"] = "accepted_fixed_tick_callback_closure"
            raw = canonical_json(payload)
            payload_path.write_bytes(raw)
            manifest = json.loads(original_manifest)
            manifest["files"][PAYLOAD_NAME] = hashlib.sha256(raw).hexdigest()
            manifest_path.write_bytes(canonical_json(manifest))
            self.assertFalse(verifier_v11.verify_rom_cfg_proven_roots_v11(ROOT, output)["verified"])
            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            payload = json.loads(original_payload)
            payload["promotion"]["promotion_bytes"] = 63
            raw = canonical_json(payload)
            payload_path.write_bytes(raw)
            manifest = json.loads(original_manifest)
            manifest["files"][PAYLOAD_NAME] = hashlib.sha256(raw).hexdigest()
            manifest_path.write_bytes(canonical_json(manifest))
            self.assertFalse(verifier_v11.verify_rom_cfg_proven_roots_v11(ROOT, output)["verified"])
            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            (output / "extra.bin").write_bytes(b"foreign")
            self.assertFalse(verifier_v11.verify_rom_cfg_proven_roots_v11(ROOT, output)["verified"])

    def test_failed_accepted_postflight_restores_existing_verified_output(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            base = Path(temporary)
            output = self._export(base)
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            with patch.object(
                exporter_v11,
                "_run_isolated_verifier",
                side_effect=[EXPECTED_REPORT, ValueError("synthetic accepted postflight")],
            ):
                with self.assertRaisesRegex(ValueError, "accepted postflight"):
                    exporter_v11.export_rom_cfg_proven_roots_v11(ROOT, output)
            after = {path.name: path.read_bytes() for path in output.iterdir()}
            self.assertEqual(before, after)
            leftovers = [
                path.name for path in base.iterdir()
                if path.name.startswith(".candidate.old-")
                or path.name.startswith(".candidate.failed-")
            ]
            self.assertEqual([], leftovers)

    def test_verifier_is_independent_and_output_is_experiment_only(self) -> None:
        verifier_source = Path(verifier_v11.__file__).read_text(encoding="utf-8")
        tree = ast.parse(verifier_source)
        forbidden = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                forbidden.extend(alias.name for alias in node.names if alias.name.startswith("tools.export_rom_cfg") or alias.name.startswith("tools.verify_rom_cfg_proven_roots_v"))
            elif isinstance(node, ast.ImportFrom) and node.module and (node.module.startswith("tools.export_rom_cfg") or node.module.startswith("tools.verify_rom_cfg_proven_roots_v")):
                forbidden.append(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                    forbidden.append("dynamic __import__")
                if isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                    forbidden.append("dynamic import_module")
        self.assertEqual([], forbidden)
        self.assertNotIn("import subprocess", verifier_source)
        for bad in (ROOT / "artifacts/rom-cfg-proven-roots-v11", ROOT / "build/not-an-experiment-v11", ROOT):
            with self.subTest(path=bad), self.assertRaisesRegex(ValueError, "experiment|canonical|artifact|root|ancestor"):
                exporter_v11.export_rom_cfg_proven_roots_v11(ROOT, bad)
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temporary:
            base = Path(temporary)
            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter_v11.export_rom_cfg_proven_roots_v11(ROOT, linked / "candidate")
            foreign = base / "foreign"
            foreign.mkdir()
            (foreign / "foreign.txt").write_text("do not replace")
            with self.assertRaisesRegex(ValueError, "foreign non-empty"):
                exporter_v11.export_rom_cfg_proven_roots_v11(ROOT, foreign)

    def test_cli_requires_isolated_no_site_runtime(self) -> None:
        for module in (exporter_v11, verifier_v11):
            script = Path(module.__file__)
            ordinary = subprocess.run([sys.executable, str(script), "--help"], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(0, ordinary.returncode)
            self.assertIn("requires Python -I -S", ordinary.stdout + ordinary.stderr)
            isolated = subprocess.run([sys.executable, "-I", "-S", str(script), "--help"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(0, isolated.returncode, isolated.stdout + isolated.stderr)

    def test_scope_is_fail_closed_and_publishes_nonclaims(self) -> None:
        scope = self.payload["scope"]
        required = {
            "natural_execution_reachability",
            "global_code_denominator",
            "global_caller_denominator",
            "global_indirect_target_denominator",
            "excluded_0x080d7c_instruction_status",
            "adjacent_target_bytes",
            "external_callee_semantics",
            "function_abi_or_business_meaning",
            "edit_relocation_or_free_space",
        }
        self.assertTrue(required <= set(scope["nonclaims"]))
        self.assertFalse(scope["runtime_reachability_complete"])
        self.assertFalse(scope["global_code_denominator_complete"])
        self.assertFalse(scope["global_caller_denominator_complete"])
        self.assertFalse(scope["excluded_unproven_source_instruction_proven"])
        self.assertTrue(scope["target_limited_raw_producer_denominator_complete"])
        self.assertTrue(scope["fixed_tick_callback_source_closures_complete"])
        self.assertTrue(scope["target_closure_complete"])


if __name__ == "__main__":
    unittest.main()
