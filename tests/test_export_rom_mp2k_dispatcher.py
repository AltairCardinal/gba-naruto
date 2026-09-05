from __future__ import annotations

import gzip
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
EXPERIMENT = ROOT / "build/experiments/active/mp2k-dispatcher-contract/codex-r1-20260829"
SCHEMA = "rom-mp2k-dispatcher-v1"
CONTRACT_SHA256 = "936f4fd2200a4ac6cbdc5641880f46585ed5722493cd6a4912632042058e154d"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "3926d1cd6e09c8b45b85cb33d0b2f77d83578ec71c17d61fa1282d863f220735"
COVERAGE_TOTALS = {
    "claim_count": 14503,
    "classified_bytes": 6124499,
    "segment_count": 16614,
    "unknown_bytes": 166957,
}
RANGES = [[638132, 638178], [638244, 638256], [638404, 638444], [638460, 638464]]
RANGE_SHA256 = [
    "d3a8d0298a139e1b02c709d08116eb3c55a835ccf69f6fc9a3957791632cc59b",
    "7d71c074f708e1abd395793f711907297dc09527cf3a9e050ce645540ba76911",
    "45103e5203193bee6f39a1533b917175c16d361b9e72bdbcdb04ec83b93eec4c",
    "48f5b6c8f55b1a8bac36a2ce2871ffc9e6e1068d808aade8c70a9afc40e2a4b0",
]
PACKED_SHA256 = "83f220623fff3f5effb8bf6cd21b7e7ce8d543ab660d7fa721b8632bd26b3bd5"
RANGE_VECTOR_SHA256 = "f7621079a8d84ce92aeebf1855856f30c0d8e551aed692531139bd6dccb39171"
TABLE_TARGETS = [
    638256,
    638260,
    638268,
    638276,
    638286,
    638300,
    638314,
    638322,
    638330,
    638338,
    638346,
    638354,
    638362,
    638376,
    638390,
    638404,
    638418,
    638432,
]
UPSTREAM = {
    "cfg_inventory_v2": {
        "manifest_sha256": "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753",
        "payload_sha256": "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd",
    },
    "m4a_initializer_chain": {
        "manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c",
        "payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd",
    },
    "similar_table_adjudications": {
        "path": "sequel/similar-table-adjudications-v1.json",
        "sha256": "c19ab7ee1e7b79eb6e3bc2888114336237e86a4c976bd8ee812fc251d70357d0",
    },
    "similar_table_verifier": {
        "path": "tools/verify_similar_table_candidates.py",
        "sha256": "04b9bc0b0a2d0ce22e817f590c04851fa70f712136e9c362a12dcd3aea75d86b",
    },
}
EXCLUDED = [
    [638178, 638180],
    [638458, 638460],
]
EXCLUDED_SHA256 = [
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
]


def _load_exporter():
    try:
        return importlib.import_module("tools.export_rom_mp2k_dispatcher")
    except ModuleNotFoundError:
        return None


def _coverage_fixture() -> dict[str, object]:
    return {
        "schema": "rom-byte-coverage-v1",
        "summary": dict(COVERAGE_TOTALS),
        "segments": [
            {"range": list(interval), "primary_class": "unknown", "primary_claim_ids": []}
            for interval in RANGES
        ] + [
            {"range": [634304, 634384], "primary_class": "m4a_initializer_chain_consumed_literal_bytes", "primary_claim_ids": ["psg-initializer-literals-09adc0"]},
            {"range": [638180, 638184], "primary_class": "thumb_dispatch_literal_pool", "primary_claim_ids": ["similar-table-candidate-027-range-050"]},
            {"range": [638184, 638244], "primary_class": "thumb_pc_relative_jump_table", "primary_claim_ids": ["similar-table-candidate-027-range-051"]},
            {"range": [638256, 638404], "primary_class": "armv4t_cfg_reachable_thumb_code", "primary_claim_ids": ["cfg-thumb-0770-09bd30"]},
            {"range": [638444, 638458], "primary_class": "armv4t_cfg_reachable_thumb_code", "primary_claim_ids": ["cfg-thumb-0771-09bdec"]},
            {"range": [638464, 638476], "primary_class": "armv4t_cfg_reachable_thumb_code", "primary_claim_ids": ["cfg-thumb-0772-09be00"]},
        ],
    }


class Mp2kDispatcherExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter = _load_exporter()

    def _implemented(self):
        self.assertIsNotNone(self.exporter, "MP2K dispatcher exporter is absent")
        return self.exporter

    def _payload(self, **kwargs):
        return self._implemented().build_payload(ROOT, **kwargs)

    def test_contract_identity_and_promotion_vector(self) -> None:
        contract = json.loads((EXPERIMENT / "CONTRACT.json").read_text())
        self.assertEqual(hashlib.sha256((EXPERIMENT / "CONTRACT.json").read_bytes()).hexdigest(), CONTRACT_SHA256)
        payload, bundle = self._payload()
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["rom"], {"path": "rom/base.gba", "size": 6291456, "sha256": ROM_SHA256})
        self.assertEqual(payload["coverage_baseline"]["sha256"], COVERAGE_SHA256)
        self.assertEqual(payload["coverage_baseline"]["size"], json.loads((EXPERIMENT / "CONTRACT.json").read_text())["coverage_baseline"]["size"])
        self.assertEqual(payload["coverage_baseline"]["summary"], COVERAGE_TOTALS)
        self.assertEqual(payload["upstream_receipts"], UPSTREAM)
        promotion = payload["promotion"]
        self.assertEqual(promotion["ranges"], RANGES)
        self.assertEqual(promotion["range_sha256"], RANGE_SHA256)
        self.assertEqual(promotion["range_count"], 4)
        self.assertEqual(promotion["byte_count"], 102)
        self.assertEqual(promotion["claim_count"], contract["promotion"]["claim_count"])
        self.assertEqual(promotion["total_bytes"], contract["promotion"]["total_bytes"])
        self.assertEqual(promotion["union_ranges"], RANGES)
        self.assertEqual(promotion["range_vector_sha256"], RANGE_VECTOR_SHA256)
        self.assertEqual(promotion["packed_bytes_sha256"], PACKED_SHA256)
        self.assertEqual(hashlib.sha256(bundle).hexdigest(), PACKED_SHA256)
        self.assertEqual([
            {key: row[key] for key in ("range", "bytes", "sha256")}
            for row in payload["promotion_ranges"]
        ], [
            {"range": interval, "bytes": end - start, "sha256": digest}
            for interval, digest in zip(RANGES, RANGE_SHA256)
            for start, end in [interval]
        ])
        self.assertEqual(len(payload["coverage_claims"]), 4)
        self.assertEqual(payload["coverage_projection"]["post"], {
            "claim_count": 14507,
            "classified_bytes": 6124601,
            "segment_count": 16617,
            "unknown_bytes": 166855,
        })
        self.assertEqual(contract["promotion"]["total_bytes"], 102)

    def test_dispatcher_semantics_and_table_provenance(self) -> None:
        contract = json.loads((EXPERIMENT / "CONTRACT.json").read_text())
        payload, _ = self._payload()
        dispatcher = payload["dispatcher"]
        self.assertEqual(dispatcher["accepted_index_domain"], [0, 17])
        self.assertEqual(dispatcher["accepted_value_count"], 18)
        self.assertEqual(dispatcher["root_offset"], 638132)
        self.assertEqual(dispatcher["cmp"], {"offset": 638162, "raw_hex": "112d", "immediate": 17})
        self.assertEqual(dispatcher["domain_branch"], {"kind": "unsigned_bls", "offset": 638164, "raw_hex": "00d9", "target_offset": 638168})
        self.assertEqual(dispatcher["default_branch"], {"offset": 638166, "raw_hex": "96e0", "target_offset": 638470})
        self.assertEqual(dispatcher["terminal"], {"kind": "resolved_mov_pc_r0", "offset": 638176, "raw_hex": "8746"})
        self.assertEqual(dispatcher["base_literal"], contract["dispatcher"]["base_literal"])
        table = dispatcher["table"]
        self.assertEqual(table["entry_count"], 18)
        self.assertEqual(table["range"], [638184, 638256])
        self.assertEqual(table["sha256"], "38127546630d56bd867a46b250c397775b52721bdc84b6daecf0326d38ab141d")
        self.assertEqual(table["targets"], TABLE_TARGETS)
        self.assertEqual([row["source_offset"] for row in payload["producer_denominator"]["producer_roles"] if row["form"] == "bytewise_u32_entry"], list(range(638184, 638256, 4)))
        self.assertEqual(payload["provenance"]["candidate_027"], {
            "candidate_range": [638180, 638244],
            "partitions": [[638180, 638184], [638184, 638244]],
            "relation": "crosses_canonical_table_boundary",
            "status": "rejected",
        })

    def test_initializer_binding_distinguishes_load_and_writer(self) -> None:
        contract = json.loads((EXPERIMENT / "CONTRACT.json").read_text())
        payload, _ = self._payload()
        binding = payload["initializer_binding"]
        self.assertEqual(binding["destination_address"], 50361664)
        self.assertEqual(binding["entry_pointer"], 134855861)
        self.assertEqual(binding["entry_pointer_occurrences"], [634328])
        self.assertEqual(binding["field_offset"], 32)
        self.assertEqual(binding["load_instruction"], {"offset": 634176, "raw_hex": "2548"})
        self.assertEqual(binding["store_instruction"], {"offset": 634178, "raw_hex": "0862"})
        self.assertEqual(binding["structure_base_literal"], {"consumer_offset": 634174, "range": [634324, 634328], "value": 50361632})
        self.assertEqual(binding["entry_pointer_root_offset"], contract["initializer_binding"]["entry_pointer_root_offset"])

    def test_cfg_has_frozen_independent_denominators(self) -> None:
        contract = json.loads((EXPERIMENT / "CONTRACT.json").read_text())
        payload, _ = self._payload()
        cfg = payload["cfg"]
        for key, value in contract["cfg"].items():
            if key in {"code_ranges", "external_edges", "return_offsets"}:
                self.assertEqual(cfg[key], value)
                continue
            self.assertIn(key, cfg["summary"])
            self.assertEqual(cfg["summary"][key], value)
        for key, value in {
            "instruction_count": 129,
            "code_bytes": 260,
            "block_count": 36,
            "internal_edge_count": 65,
            "external_edge_count": 1,
            "resolved_dispatch_edge_count": 18,
            "total_graph_edge_count": 66,
            "structured_return_count": 1,
            "frontier_count": 0,
            "unresolved_frontier_count": 0,
            "budget_exhausted": False,
        }.items():
            self.assertEqual(cfg["summary"][key], value)
        self.assertEqual(len(cfg["instructions"]), 129)
        self.assertEqual(len(cfg["blocks"]), 36)
        self.assertEqual(len(cfg["block_edges"]), 66)
        self.assertEqual(len(cfg["calls"]), 1)
        self.assertEqual(cfg["calls"][0]["source_instruction_offset"], 638452)
        self.assertEqual(cfg["calls"][0]["target_offset"], 639256)
        self.assertEqual(cfg["calls"][0]["resolution"], "opaque_thumb_bl")
        self.assertEqual(cfg["returns"][0]["offset"], 638474)
        self.assertEqual(cfg["frontiers"], [])
        self.assertEqual([
            {key: row[key] for key in ("file_offset", "code_range")}
            for row in cfg["roots"]
        ], [
            {"file_offset": 638132, "code_range": [638132, 638178]},
            {"file_offset": 638256, "code_range": [638256, 638458]},
        ])

    def test_literals_and_excluded_gaps_are_explicit(self) -> None:
        payload, _ = self._payload()
        self.assertEqual(payload["literal_bindings"], [{
            "instruction_offset": 638170,
            "raw": 0x4902,
            "literal_offset": 638180,
            "value": 134855912,
            "raw_hex": "e8bc0908",
        }])
        self.assertEqual(payload["consumed_literals"], [{
            "consumer_offset": 638444,
            "range": [638460, 638464],
            "value": 50361636,
            "raw_hex": "24750003",
        }])
        self.assertEqual([
            {key: row[key] for key in ("range", "sha256", "promoted", "semantic_class")}
            for row in payload["excluded_ranges"]
        ], [
            {"range": interval, "sha256": digest, "promoted": False, "semantic_class": "unknown"}
            for interval, digest in zip(EXCLUDED, EXCLUDED_SHA256)
        ])

    def test_coverage_contract_rejects_non_object_summary_drift_and_partial_owner(self) -> None:
        exporter = self._implemented()
        for bad in (None, [], "coverage"):
            with self.subTest(type=type(bad).__name__), self.assertRaises(ValueError):
                exporter.analyze_coverage_baseline(bad)
        bad = _coverage_fixture()
        bad["summary"]["unknown_bytes"] += 1
        with self.assertRaisesRegex(ValueError, "summary"):
            exporter.analyze_coverage_baseline(bad)
        bad = _coverage_fixture()
        bad["segments"][0] = {"range": [638132, 638150], "primary_class": "unknown", "primary_claim_ids": []}
        bad["segments"].insert(1, {"range": [638150, 638178], "primary_class": "foreign", "primary_claim_ids": ["foreign"]})
        with self.assertRaisesRegex(ValueError, "whole-range|unknown"):
            exporter.analyze_coverage_baseline(bad)
        bad = _coverage_fixture()
        bad["segments"].append({"range": [638244, 638256], "primary_class": "unknown", "primary_claim_ids": []})
        with self.assertRaisesRegex(ValueError, "overlap|duplicate"):
            exporter.analyze_coverage_baseline(bad)

    def test_rom_and_promotion_mutations_fail_closed_before_expensive_analysis(self) -> None:
        exporter = self._implemented()
        for offset in [item for start, end in RANGES for item in range(start, end)]:
            changed = bytearray(self.rom)
            changed[offset] ^= 1
            with self.subTest(offset=offset), mock.patch.object(exporter, "_validate_rom"), mock.patch.object(exporter, "_validate_upstream_receipts"), mock.patch.object(exporter, "_analyze_cfg", side_effect=AssertionError("CFG scan ran")):
                with self.assertRaisesRegex(ValueError, "promotion range"):
                    exporter.build_payload_from_rom(ROOT, bytes(changed))

    def test_unique_pointer_and_writer_roles_fail_closed(self) -> None:
        exporter = self._implemented()
        for offset in (634176, 634178, 634324, 634328):
            changed = bytearray(self.rom)
            changed[offset] ^= 1
            with self.subTest(offset=offset), mock.patch.object(exporter, "ROM_SHA256", hashlib.sha256(changed).hexdigest()):
                with self.assertRaises(ValueError):
                    exporter.build_payload_from_rom(ROOT, bytes(changed))
        duplicate = bytearray(self.rom)
        duplicate[634332:634336] = duplicate[634328:634332]
        with mock.patch.object(exporter, "ROM_SHA256", hashlib.sha256(duplicate).hexdigest()):
            with self.assertRaisesRegex(ValueError, "occurrence|unique|pointer|producer"):
                exporter.build_payload_from_rom(ROOT, bytes(duplicate))

    def test_raw_target_producer_scan_rejects_injected_direct_and_pointer_forms(self) -> None:
        exporter = self._implemented()
        source = 638000
        root = 638132
        handler = 638256
        delta = root - (source + 4)
        variants = {
            "thumb_b": struct.pack("<H", 0xE000 | ((delta >> 1) & 0x07FF)),
            "thumb_b_conditional": struct.pack("<H", 0xD000 | ((delta >> 1) & 0x00FF)),
            "thumb_bl": struct.pack("<HH", 0xF000 | ((delta >> 12) & 0x07FF), 0xF800 | ((delta >> 1) & 0x07FF)),
            "arm_b": struct.pack("<I", 0xEA000000 | (((root - (source + 8)) >> 2) & 0x00FFFFFF)),
            "arm_bl": struct.pack("<I", 0xEB000000 | (((root - (source + 8)) >> 2) & 0x00FFFFFF)),
            "bytewise_u32_entry": struct.pack("<I", 0x08000000 + handler),
            "bytewise_u32_thumb_pointer": struct.pack("<I", 0x08000000 + root + 1),
        }
        for name, raw in variants.items():
            changed = bytearray(self.rom)
            changed[source:source + len(raw)] = raw
            with self.subTest(form=name), mock.patch.object(exporter, "ROM_SHA256", hashlib.sha256(changed).hexdigest()):
                with self.assertRaisesRegex(ValueError, "producer.*denominator|denominator.*producer"):
                    exporter.build_payload_from_rom(ROOT, bytes(changed))

    def test_candidate_writer_uses_only_new_empty_output(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            output = Path(temp) / "candidate"
            result = exporter.write_candidate(ROOT, output)
            self.assertEqual(result["bundle_sha256"], PACKED_SHA256)
            self.assertEqual(set(path.name for path in output.iterdir()), {"manifest.json", "rom-mp2k-dispatcher.json", "rom-mp2k-dispatcher.bin"})
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["artifact_status"], "candidate")
            self.assertEqual(manifest["files"]["rom-mp2k-dispatcher.bin"]["sha256"], PACKED_SHA256)
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, output)
            (Path(temp) / "existing").mkdir()
            (Path(temp) / "existing" / "sentinel").write_text("keep")
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, Path(temp) / "existing")
            link = Path(temp) / "link"
            link.symlink_to(output, target_is_directory=True)
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, link)

    def test_candidate_writer_rejects_preexisting_empty_output_and_parent_swap(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp, tempfile.TemporaryDirectory() as outside_raw:
            root = Path(temp)
            empty = root / "empty"
            empty.mkdir()
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, empty)
            self.assertTrue(empty.is_dir())

            parent = root / "publish-parent"
            parent.mkdir()
            output = parent / "candidate"
            real_validate = exporter._validate_output

            def raced_validate(repository, requested):
                target = real_validate(repository, requested)
                parent.rename(root / "publish-parent-original")
                parent.symlink_to(Path(outside_raw), target_is_directory=True)
                return target

            with mock.patch.object(exporter, "_validate_output", side_effect=raced_validate):
                with self.assertRaisesRegex(ValueError, "symlink|identity|anchor|output"):
                    exporter.write_candidate(ROOT, output)
            self.assertFalse((Path(outside_raw) / "candidate").exists())

    def test_candidate_writer_rejects_real_parent_identity_swap_and_preserves_replacement(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            parent = root / "publish-parent"
            parent.mkdir()
            output = parent / "candidate"
            real_validate = exporter._validate_output

            def replaced_parent_validate(repository, requested):
                validated = real_validate(repository, requested)
                parent.rename(root / "publish-parent-original")
                parent.mkdir()
                return validated

            with mock.patch.object(exporter, "_validate_output", side_effect=replaced_parent_validate):
                with self.assertRaisesRegex(ValueError, "identity|changed|output"):
                    exporter.write_candidate(ROOT, output)
            self.assertFalse(output.exists())

            parent.rmdir()
            (root / "publish-parent-original").rename(parent)
            replacement: list[Path] = []

            def replace_owned_directory(_directory_fd, _name, _raw):
                owned = next(path for path in parent.iterdir() if path.name == "candidate" or path.name.startswith(".candidate."))
                owned.rename(parent / f"{owned.name}.owned")
                owned.mkdir()
                (owned / "sentinel").write_text("keep")
                replacement.append(owned)
                raise OSError("injected write failure")

            with mock.patch.object(exporter, "_write_file_at", side_effect=replace_owned_directory):
                with self.assertRaisesRegex(OSError, "injected"):
                    exporter.write_candidate(ROOT, output)
            self.assertEqual(len(replacement), 1)
            self.assertEqual((replacement[0] / "sentinel").read_text(), "keep")

    def test_candidate_writer_cleans_owned_directory_when_open_fails(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            output = Path(temp) / "candidate"
            real_open = exporter.os.open

            def fail_target_open(path, flags, mode=0o777, *, dir_fd=None):
                if path == output.name and dir_fd is not None:
                    raise OSError("injected directory open failure")
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(exporter.os, "open", side_effect=fail_target_open):
                with self.assertRaisesRegex(OSError, "injected"):
                    exporter.write_candidate(ROOT, output)
            self.assertFalse(output.exists())

    def test_optional_precoverage_replay_is_identity_checked(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            archive = Path(temp) / "precoverage"
            archive.mkdir()
            raw = (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
            compressed = gzip.compress(raw, mtime=0)
            (archive / "rom-byte-coverage.json.gz").write_bytes(compressed)
            (archive / "manifest.json").write_text(json.dumps({
                "schema": "rom-byte-coverage-prepromotion-baseline-v1",
                "artifact_status": "accepted",
                "coverage": {
                    "raw": {"canonical_json": True, "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256, "size": len(raw), "summary": COVERAGE_TOTALS},
                    "archive": {"compression": "gzip", "file": "rom-byte-coverage.json.gz", "sha256": hashlib.sha256(compressed).hexdigest(), "size": len(compressed)},
                },
                "recovery": {"kind": "direct-frozen-prepromotion-snapshot"},
            }, indent=2, sort_keys=True) + "\n")
            relative = archive.relative_to(ROOT)
            payload, _ = exporter.build_payload(ROOT, coverage_baseline_artifact=relative)
            self.assertEqual(payload["coverage_baseline_source"]["artifact"], relative.as_posix())
            bad = Path(temp) / "bad"
            bad.mkdir()
            (bad / "rom-byte-coverage.json.gz").write_bytes(compressed[:-1])
            (bad / "manifest.json").write_text("{}\n")
            with self.assertRaises(ValueError):
                exporter.build_payload(ROOT, coverage_baseline_artifact=bad.relative_to(ROOT))

            wrong_recovery = Path(temp) / "wrong-recovery"
            shutil.copytree(archive, wrong_recovery)
            manifest = json.loads((wrong_recovery / "manifest.json").read_text())
            manifest["recovery"]["kind"] = "mutable-live-file"
            (wrong_recovery / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "recovery"):
                exporter.build_payload(ROOT, coverage_baseline_artifact=wrong_recovery.relative_to(ROOT))

    def test_source_uses_raw_control_flow_and_not_verifier(self) -> None:
        self._implemented()
        source = (ROOT / "tools/export_rom_mp2k_dispatcher.py").read_text()
        self.assertIn("_raw_flow", source)
        self.assertIn("raw", source.lower())
        self.assertNotIn("import tools.verify_rom_mp2k_dispatcher", source)
        self.assertNotIn("from tools import verify_rom_mp2k_dispatcher", source)


if __name__ == "__main__":
    unittest.main()
