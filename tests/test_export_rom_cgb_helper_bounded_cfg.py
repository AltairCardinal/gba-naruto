from __future__ import annotations

import hashlib
import gzip
import importlib
import json
from pathlib import Path
import struct
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
EXPERIMENT = ROOT / "build/experiments/active/cgb-helper-contract/codex-r1-20260829"
SCHEMA = "rom-cgb-helper-bounded-cfg-v1"
CONTRACT_SHA256 = "e1f4d0b840d52b19ee996ee7c0ba18c41511f0c96b37f498f77954a24c9105b7"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SIZE = 6291456
COVERAGE_SHA256 = "22f8f88ca0929468289b749cb94b4aaa4c47d7a53fa68fe10cb93c9a01816839"
COVERAGE_SIZE = 23152713
COVERAGE_TOTALS = {
    "claim_count": 14507,
    "classified_bytes": 6124601,
    "segment_count": 16617,
    "unknown_bytes": 166855,
}
PROMOTION_RANGES = [
    {"bytes": 36, "kind": "cgb_helper_bounded_thumb_code", "range": [636220, 636256], "sha256": "ac01b052dd7ab7f97e74b52e671f1e8bdc2c423caeebeee4c5618c905f29bca1"},
    {"bytes": 4, "kind": "cgb_helper_consumed_literal_bytes", "range": [636256, 636260], "sha256": "22f7252bc2b8f2444cb6c59642ab9d902a8cac23e4c27e48623e8513b28ddeee"},
    {"bytes": 4, "kind": "cgb_helper_bounded_thumb_code", "range": [636260, 636264], "sha256": "df358c07b036a56dcc30711ce42e97371d6e3f08f6a1e8027e0beb713f85c56d"},
    {"bytes": 4, "kind": "cgb_helper_consumed_literal_bytes", "range": [636264, 636268], "sha256": "60e226a6318302bbe245079f99e6724c5cd2431c689d5ae9992b08bdcc592a04"},
    {"bytes": 6, "kind": "cgb_helper_bounded_thumb_code", "range": [636268, 636274], "sha256": "30c6c9fcb611330459336092dfdf9059b742dabc6d5f773ae67f501c1caadc3f"},
    {"bytes": 4, "kind": "cgb_helper_consumed_literal_bytes", "range": [636276, 636280], "sha256": "d0455d972504810561aaa6b9cc70d69a9ad49abc84a3df38789afdd8eb9236eb"},
    {"bytes": 14, "kind": "cgb_helper_bounded_thumb_code", "range": [636280, 636294], "sha256": "6531a1df4bcdc95692713b4c346c135e75339afb73d35dd2934ff15e9f606d99"},
    {"bytes": 4, "kind": "cgb_helper_consumed_literal_bytes", "range": [636296, 636300], "sha256": "bd56e77404afec2e1cb1d293f4b56e5188b6e7c5d7aaf39d58dbd1de177f28fd"},
    {"bytes": 104, "kind": "cgb_helper_bounded_thumb_code", "range": [636300, 636404], "sha256": "584762a3caa5fe9d71f2afd7fe58f2e5a8d2ef8efb2c4d68df84a621b84c9b88"},
]
PROMOTED_RANGES = [row["range"] for row in PROMOTION_RANGES]
PROMOTION_RANGE_VECTOR_SHA256 = "ea942377babe2613c9affe8711b6480f6e9e27e60da7aeb483112790de3b85b3"
PROMOTION_PACKED_SHA256 = "87c62bbe5f0e9d25ee5b11398ecdd3ed5b41782d4873871205f71c1122a4c1dc"
ENVELOPE = {"bytes": 184, "range": [636220, 636404], "sha256": "a0f923319eee38584598d41b83ff9dbc06a870c257d6a2411d10d5f1113c25da"}
CODE_RANGES = [[636220, 636256], [636260, 636264], [636268, 636274], [636280, 636294], [636300, 636404]]
LITERAL_RANGES = [[636256, 636260], [636264, 636268], [636276, 636280], [636296, 636300]]
EXCLUDED_RANGES = [[636274, 636276], [636294, 636296]]
EXCLUDED_SHA256 = [
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
]
UPSTREAM = {
    "m4a_initializer_chain": {
        "manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c",
        "payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd",
    }
}
LITERAL_BINDINGS = [
    {"consumer_offset": 636246, "load_raw_hex": "0249", "range": [636256, 636260], "value": 67108963},
    {"consumer_offset": 636260, "load_raw_hex": "0049", "range": [636264, 636268], "value": 67108969},
    {"consumer_offset": 636268, "load_raw_hex": "0149", "range": [636276, 636280], "value": 67108976},
    {"consumer_offset": 636280, "load_raw_hex": "0349", "range": [636296, 636300], "value": 67108985},
]
PRODUCER_FORMS = [
    "thumb_bl",
    "thumb_b",
    "thumb_b_conditional",
    "arm_b",
    "arm_bl",
    "bytewise_u32_entry",
    "bytewise_u32_thumb_pointer",
]
PRODUCER_TARGETS = [
    {
        "target_file_offset": 636220,
        "forms": {
            "thumb_bl": [636882],
            "thumb_b": [],
            "thumb_b_conditional": [],
            "arm_b": [],
            "arm_bl": [],
            "bytewise_u32_entry": [],
            "bytewise_u32_thumb_pointer": [634368],
        },
    },
    {
        "target_file_offset": 636300,
        "forms": {
            "thumb_bl": [636654, 636976],
            "thumb_b": [],
            "thumb_b_conditional": [],
            "arm_b": [],
            "arm_bl": [],
            "bytewise_u32_entry": [],
            "bytewise_u32_thumb_pointer": [],
        },
    },
]
PRODUCER_VECTOR_SHA256 = "536020c92992d0ea9387b79d4ef15f9aa9e09b3f82c100b8c396fe1af98c4ab1"
SCOPE = {
    "allocatable_free_space_proven": False,
    "audio_behavior_proven": False,
    "computed_or_indirect_producer_denominator_complete": False,
    "editing_relocation_writeback_safe": False,
    "global_caller_or_code_denominator_complete": False,
    "global_ram_writer_denominator_complete": False,
    "input_value_domain_complete": False,
    "literal_target_semantics_claimed": False,
    "natural_runtime_reachability": False,
    "target_limited_raw_producer_denominator_complete": True,
}


def _load_exporter():
    try:
        return importlib.import_module("tools.export_rom_cgb_helper_bounded_cfg")
    except ModuleNotFoundError:
        return None


def _coverage_fixture() -> dict[str, object]:
    return {
        "schema": "rom-byte-coverage-v1",
        "summary": dict(COVERAGE_TOTALS),
        "segments": [
            {"range": list(interval), "primary_class": "unknown", "primary_claim_ids": []}
            for interval in PROMOTED_RANGES
        ]
        + [
            {"range": list(interval), "primary_class": "unknown", "primary_claim_ids": []}
            for interval in EXCLUDED_RANGES
        ]
        + [
            {
                "range": [634368, 634372],
                "primary_class": "m4a_initializer_chain_consumed_literal_bytes",
                "primary_claim_ids": ["psg-initializer-literals-09adc0"],
            }
        ],
    }


def _canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=False).encode()


def _copy_precoverage(directory: Path) -> Path:
    directory.mkdir(parents=True)
    target = directory / "precoverage"
    shutil.copytree(ROOT / "artifacts/rom-cgb-audio-precoverage-v1", target)
    return target


class CgbHelperExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter = _load_exporter()

    def _implemented(self):
        self.assertIsNotNone(cls := self.exporter, "CGB helper exporter is absent")
        return cls

    def _payload(self, **kwargs):
        return self._implemented().build_payload(ROOT, **kwargs)

    def test_contract_identity_exact_promotion_ranges_and_binary(self) -> None:
        exporter = self._implemented()
        contract_path = EXPERIMENT / "CONTRACT.json"
        contract = json.loads(contract_path.read_text())
        self.assertEqual(hashlib.sha256(contract_path.read_bytes()).hexdigest(), CONTRACT_SHA256)
        payload, bundle = exporter.build_payload(ROOT)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["rom"], {"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256})
        self.assertEqual(payload["envelope"], ENVELOPE)
        promotion = payload["promotion"]
        self.assertEqual(promotion["ranges"], PROMOTION_RANGES)
        self.assertEqual(promotion["claim_count"], contract["promotion"]["claim_count"])
        self.assertEqual(promotion["code_bytes"], 164)
        self.assertEqual(promotion["literal_bytes"], 16)
        self.assertEqual(promotion["total_bytes"], 180)
        self.assertEqual(promotion["range_vector_sha256"], PROMOTION_RANGE_VECTOR_SHA256)
        self.assertEqual(promotion["packed_bytes_sha256"], PROMOTION_PACKED_SHA256)
        self.assertEqual(len(bundle), 180)
        self.assertEqual(hashlib.sha256(bundle).hexdigest(), PROMOTION_PACKED_SHA256)
        self.assertEqual(payload["promotion_ranges"], PROMOTION_RANGES)

    def test_cfg_counts_roots_edges_branches_fallthrough_and_returns(self) -> None:
        exporter = self._implemented()
        contract = json.loads((EXPERIMENT / "CONTRACT.json").read_text())
        payload, _ = exporter.build_payload(ROOT)
        cfg = payload["cfg"]
        for key in (
            "block_count",
            "code_bytes",
            "external_edge_count",
            "frontier_count",
            "instruction_count",
            "internal_edge_count",
            "structured_return_count",
        ):
            self.assertEqual(cfg[key], contract["cfg"][key])
        self.assertEqual(cfg["budget_exhausted"], False)
        self.assertEqual(cfg["code_ranges"], CODE_RANGES)
        self.assertEqual(cfg["return_offsets"], [636292, 636402])
        self.assertEqual(cfg["semantic_instruction_vector_sha256"], "66df11b0f24f38a6aa9aa3b202c5b07b949ff98631ddb3f8c97f46d602d8f5db")
        self.assertEqual(cfg["block_range_vector_sha256"], "421415d1f0c255dc581a1076ec73441ef031ed7fd623ce6d8e224b2e51ab55ce")
        self.assertEqual(cfg["edge_vector_sha256"], "7c080763f41c5afb6556bc4dcdf44ccd884a96ac8b14d8270aa68f77c36a2978")
        self.assertEqual(len(cfg["instructions"]), 82)
        self.assertEqual(len(cfg["blocks"]), 23)
        self.assertEqual(len(cfg["block_edges"]), 29)
        self.assertEqual(cfg["frontiers"], [])
        self.assertEqual(cfg["roots"], contract["cfg"]["roots"])
        instruction_offsets = {row["offset"] for row in cfg["instructions"]}
        self.assertEqual(sum(row["size"] for row in cfg["instructions"]), 164)
        kinds = set()
        for row in cfg["instructions"]:
            for edge in row.get("successors", []):
                kinds.add(edge["kind"])
                target = edge["target_offset"]
                self.assertIn(target, instruction_offsets)
                self.assertFalse(any(start <= target < end for start, end in EXCLUDED_RANGES))
        self.assertIn("branch", kinds)
        self.assertIn("fallthrough", kinds)
        self.assertEqual([(row["offset"], row["register"]) for row in cfg["returns"]], [(636292, "lr"), (636402, "r0")])
        semantic = [[row["offset"], row["size"], row["mnemonic"], row["op_str"]] for row in sorted(cfg["instructions"], key=lambda row: row["offset"])]
        blocks = [row["range"] for row in sorted(cfg["blocks"], key=lambda row: row["range"][0])]
        edges = sorted(
            [[row["source_instruction_offset"], row["target_offset"], row["kind"]] for row in cfg["block_edges"]],
            key=lambda row: (row[0], 0 if row[2] == "branch" else 1),
        )
        self.assertEqual(hashlib.sha256(_canonical(semantic)).hexdigest(), cfg["semantic_instruction_vector_sha256"])
        self.assertEqual(hashlib.sha256(_canonical(blocks)).hexdigest(), cfg["block_range_vector_sha256"])
        self.assertEqual(hashlib.sha256(_canonical(edges)).hexdigest(), cfg["edge_vector_sha256"])
        successor_edges = sorted(
            [[row["offset"], edge["target_offset"], edge["kind"]] for row in cfg["instructions"] for edge in row.get("successors", [])],
            key=lambda row: (row[0], 0 if row[2] == "branch" else 1),
        )
        self.assertEqual(successor_edges, edges)

    def test_literals_use_pc_align_values_and_stay_separate_from_code(self) -> None:
        payload, _ = self._payload()
        projection = payload["literal_projection"]
        self.assertEqual(projection["binding_count"], 4)
        self.assertEqual(projection["bytes"], 16)
        self.assertEqual(projection["word_count"], 4)
        self.assertEqual(projection["ranges"], LITERAL_RANGES)
        self.assertEqual(projection["range_vector_sha256"], "ef5c2b2dbc43d612c4d0c96272f74cf4d2c0322306b359b04780c374ccbf563e")
        self.assertEqual(projection["packed_sha256"], "01d705cc2e13fbb303c3f9b4b889ead90b5082f621806104e9997b35f186b038")
        self.assertEqual(projection["bindings"], LITERAL_BINDINGS)
        for binding in projection["bindings"]:
            raw = bytes.fromhex(binding["load_raw_hex"])
            halfword = struct.unpack("<H", raw)[0]
            pc_base = (binding["consumer_offset"] + 4) & ~3
            literal_offset = pc_base + ((halfword & 0xFF) * 4)
            self.assertEqual(literal_offset, binding["range"][0])
            self.assertNotIn(binding["range"], CODE_RANGES)
        self.assertTrue(set(tuple(row["range"]) for row in projection["bindings"]).isdisjoint(set(tuple(row) for row in CODE_RANGES)))

    def test_initializer_producers_and_excluded_gaps_are_frozen_provenance(self) -> None:
        contract = json.loads((EXPERIMENT / "CONTRACT.json").read_text())
        payload, _ = self._payload()
        self.assertEqual(payload["initializer_binding"], contract["initializer_binding"])
        producer = payload["producer_denominator"]
        self.assertEqual(producer["forms"], PRODUCER_FORMS)
        self.assertEqual(producer["scan_range"], [0, ROM_SIZE])
        self.assertEqual(producer["targets"], PRODUCER_TARGETS)
        self.assertEqual(producer["vector_sha256"], PRODUCER_VECTOR_SHA256)
        excluded = payload["excluded_ranges"]
        self.assertEqual(len(excluded), 2)
        for row, expected_range, expected_sha in zip(excluded, EXCLUDED_RANGES, EXCLUDED_SHA256):
            self.assertEqual(row["range"], expected_range)
            self.assertEqual(row["sha256"], expected_sha)
            self.assertEqual(row["raw_hex"], "0000")
            self.assertFalse(row["promoted"])
            self.assertEqual(row["semantic_class"], "unknown")
            self.assertNotIn(expected_range, [row["range"] for row in PROMOTION_RANGES])

    def test_live_shared_coverage_and_upstream_identity_are_explicit(self) -> None:
        exporter = self._implemented()
        live, _ = exporter.build_payload(ROOT)
        self.assertEqual(live["coverage_baseline"]["path"], "sequel/rom-byte-coverage.json")
        self.assertEqual(live["coverage_baseline"]["sha256"], COVERAGE_SHA256)
        self.assertEqual(live["coverage_baseline"]["size"], COVERAGE_SIZE)
        self.assertEqual(live["coverage_baseline"]["summary"], COVERAGE_TOTALS)
        self.assertEqual(live["upstream_receipts"], UPSTREAM)
        shared = Path("artifacts/rom-cgb-audio-precoverage-v1")
        replay, _ = exporter.build_payload(ROOT, coverage_baseline_artifact=shared)
        self.assertEqual(replay["coverage_baseline_source"]["artifact"], shared.as_posix())
        self.assertEqual(replay["coverage_baseline"]["sha256"], COVERAGE_SHA256)
        self.assertEqual(replay["coverage_baseline"]["summary"], COVERAGE_TOTALS)
        immutable = replay["coverage_baseline"]["immutable_artifact"]
        self.assertEqual(immutable, {
            "path": shared.as_posix(),
            "archive_sha256": "e345bf5a605d796c1e38a4243b4aefbcb7b8229f70bea13ce40ca044d4edf04b",
            "manifest_sha256": "73be947de76ede7948780faba669d74320d2f37d91c95a6bdd99a3c5b02b94c1",
        })
        with mock.patch.object(exporter, "_coverage_from_file", side_effect=AssertionError("live coverage consulted")):
            replay, _ = exporter.build_payload(ROOT, coverage_baseline_artifact=shared)
        self.assertEqual(replay["coverage_baseline_source"]["artifact"], shared.as_posix())

    def test_precoverage_replay_validates_outer_gzip_raw_recovery_and_path(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            for case in ("gzip", "outer", "raw", "recovery"):
                archive = _copy_precoverage(root / case)
                manifest_path = archive / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                if case == "gzip":
                    (archive / "rom-byte-coverage.json.gz").write_bytes(b"not-gzip")
                elif case == "outer":
                    manifest["coverage"]["archive"]["sha256"] = "0" * 64
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                elif case == "raw":
                    manifest["coverage"]["raw"]["sha256"] = "0" * 64
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                else:
                    manifest["recovery"]["kind"] = "mutable-live-file"
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                with self.subTest(case=case), self.assertRaises(ValueError):
                    exporter.build_payload(ROOT, coverage_baseline_artifact=archive.relative_to(ROOT))
            link = root / "precoverage-link"
            link.symlink_to(ROOT / "artifacts/rom-cgb-audio-precoverage-v1", target_is_directory=True)
            with self.assertRaises(ValueError):
                exporter.build_payload(ROOT, coverage_baseline_artifact=link.relative_to(ROOT))

    def test_coverage_nonobject_summary_drift_partial_owner_and_overlap_fail_closed(self) -> None:
        exporter = self._implemented()
        for bad in (None, [], "coverage"):
            with self.subTest(kind=type(bad).__name__), self.assertRaises(ValueError):
                exporter.analyze_coverage_baseline(bad)
        bad = _coverage_fixture()
        bad["summary"]["unknown_bytes"] += 1
        with self.assertRaisesRegex(ValueError, "summary"):
            exporter.analyze_coverage_baseline(bad)
        bad = _coverage_fixture()
        bad["segments"][0] = {"range": [636220, 636240], "primary_class": "unknown", "primary_claim_ids": []}
        bad["segments"].insert(1, {"range": [636240, 636256], "primary_class": "foreign", "primary_claim_ids": ["foreign"]})
        with self.assertRaisesRegex(ValueError, "whole-range|unknown"):
            exporter.analyze_coverage_baseline(bad)
        bad = _coverage_fixture()
        bad["segments"].append({"range": [636220, 636256], "primary_class": "unknown", "primary_claim_ids": []})
        with self.assertRaisesRegex(ValueError, "overlap|duplicate"):
            exporter.analyze_coverage_baseline(bad)
        for target in ([634368, 634370], [636274, 636276]):
            bad = _coverage_fixture()
            for row in bad["segments"]:
                if row["range"] == target or (target == [634368, 634370] and row["range"] == [634368, 634372]):
                    row["range"] = target
                    row["primary_class"] = "foreign"
                    row["primary_claim_ids"] = ["foreign"]
                    break
            with self.subTest(target=target), self.assertRaises(ValueError):
                exporter.analyze_coverage_baseline(bad)

    def test_raw_cfg_mutations_reach_decoder_and_initializer_is_content_bound(self) -> None:
        exporter = self._implemented()
        for offset, raw in ((636230, b"\x00\xe0"), (636292, b"\x00\x47"), (636246, b"\xff\x49")):
            changed = bytearray(self.rom)
            changed[offset : offset + 2] = raw
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                exporter.analyze_cfg_from_rom(bytes(changed))
        for offset in (634224, 634226, 634368):
            changed = bytearray(self.rom)
            changed[offset] ^= 1
            with self.subTest(initializer_offset=offset), mock.patch.object(exporter, "_validate_rom"):
                with self.assertRaises(ValueError):
                    exporter.build_payload_from_rom(ROOT, bytes(changed))

    def test_rom_and_promotion_mutations_fail_before_cfg_analysis(self) -> None:
        exporter = self._implemented()
        for offset in [item for start, end in PROMOTED_RANGES for item in range(start, end)]:
            changed = bytearray(self.rom)
            changed[offset] ^= 1
            with self.subTest(offset=offset), mock.patch.object(exporter, "_validate_rom"), mock.patch.object(exporter, "_validate_upstream_receipts"), mock.patch.object(exporter, "_analyze_cfg", side_effect=AssertionError("CFG scan ran")):
                with self.assertRaisesRegex(ValueError, "promotion range"):
                    exporter.build_payload_from_rom(ROOT, bytes(changed))

    def test_candidate_writer_is_canonical_candidate_only_and_path_safe(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            output = root / "candidate"
            result = exporter.write_candidate(ROOT, output)
            self.assertEqual(result["bundle_sha256"], PROMOTION_PACKED_SHA256)
            self.assertEqual(set(path.name for path in output.iterdir()), {"manifest.json", "rom-cgb-helper-bounded-cfg.json", "rom-cgb-helper-bounded-cfg.bin"})
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["artifact_status"], "candidate")
            self.assertEqual(manifest["files"]["rom-cgb-helper-bounded-cfg.bin"]["sha256"], PROMOTION_PACKED_SHA256)
            payload_path = output / "rom-cgb-helper-bounded-cfg.json"
            payload = json.loads(payload_path.read_text())
            self.assertEqual(payload_path.read_text(), json.dumps(payload, indent=2, sort_keys=True) + "\n")
            manifest_path = output / "manifest.json"
            self.assertEqual(manifest_path.read_text(), json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, output)
            occupied = root / "occupied"
            occupied.mkdir()
            (occupied / "sentinel").write_text("keep")
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, occupied)
            for escaped in (ROOT, ROOT.parent, Path("/tmp/cgb-helper-escape")):
                with self.subTest(escaped=str(escaped)), self.assertRaises(ValueError):
                    exporter.write_candidate(ROOT, escaped)
            link = root / "link"
            link.symlink_to(output, target_is_directory=True)
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, link)
            empty = root / "empty"
            empty.mkdir()
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, empty)
            link_parent = root / "link-parent"
            link_parent.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, link_parent / "new")

    def test_candidate_writer_rejects_parent_swap_without_writing_outside(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp, tempfile.TemporaryDirectory() as outside:
            root = Path(temp)
            parent = root / "publish"
            parent.mkdir()
            real_validate = exporter._validate_output
            def raced(repository, requested):
                result = real_validate(repository, requested)
                parent.rename(root / "publish-original")
                parent.symlink_to(Path(outside), target_is_directory=True)
                return result
            with mock.patch.object(exporter, "_validate_output", side_effect=raced):
                with self.assertRaises(ValueError):
                    exporter.write_candidate(ROOT, parent / "candidate")
            self.assertFalse((Path(outside) / "candidate").exists())

    def test_output_rejects_dotdot_after_resolution_and_replay_is_single_snapshot(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, r"parent|\.\.|escape"):
                exporter.write_candidate(ROOT, root / "nested" / ".." / "candidate")
            with self.assertRaises(ValueError):
                exporter.write_candidate(ROOT, ROOT / "notes" / "cgb-helper-forbidden")
        coverage = _coverage_fixture()
        raw = (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
        source = {"artifact": "artifacts/rom-cgb-audio-precoverage-v1"}
        original_safe_file = exporter._safe_file
        def no_second_archive_read(repository, relative):
            if Path(relative).name == "rom-byte-coverage.json.gz":
                raise AssertionError("validated replay archive was read a second time")
            return original_safe_file(repository, relative)
        with mock.patch.object(exporter, "_coverage_from_artifact", return_value=(coverage, source, raw)), mock.patch.object(exporter, "_safe_file", side_effect=no_second_archive_read):
            payload, _ = exporter.build_payload(ROOT, coverage_baseline_artifact=Path(source["artifact"]))
        self.assertEqual(payload["coverage_baseline"]["sha256"], COVERAGE_SHA256)

    def test_initializer_raw_bits_and_upstream_semantics_are_content_bound(self) -> None:
        exporter = self._implemented()
        semantics = exporter.decode_initializer_semantics(self.rom)
        self.assertEqual(semantics, {
            "load": {"offset": 634224, "rt": "r0", "pc_base": 634228, "literal_offset": 634368, "value": 0x0809B53D},
            "store": {"offset": 634226, "source": "r0", "base": "r4", "width": "word", "field_offset": 0x2C},
        })
        for offset, raw in ((634224, bytes.fromhex("2248")), (634226, bytes.fromhex("e162"))):
            changed = bytearray(self.rom)
            changed[offset : offset + 2] = raw
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "initializer.*semantic|semantic.*initializer"):
                exporter._initializer(bytes(changed), ROOT)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as temp:
            replacement = Path(temp) / "upstream.json"
            payload = json.loads((ROOT / "artifacts/rom-m4a-initializer-chain-v1/rom-m4a-initializer-chain.json").read_text())
            next(row for row in payload["cfg"]["instructions"] if row["offset"] == 634226)["op_str"] = "r1, [r4, #0x2c]"
            replacement.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            receipts = json.loads(json.dumps(exporter.UPSTREAM))
            receipts["m4a_initializer_chain"]["payload_sha256"] = hashlib.sha256(replacement.read_bytes()).hexdigest()
            original = exporter._safe_file
            def redirected(repository, relative):
                if Path(relative) == exporter.UPSTREAM_PATHS["payload"]:
                    return replacement
                return original(repository, relative)
            with mock.patch.object(exporter, "UPSTREAM", receipts), mock.patch.object(exporter, "_safe_file", side_effect=redirected):
                with self.assertRaisesRegex(ValueError, "upstream.*semantic|semantic.*upstream"):
                    exporter._validate_upstream_receipts(ROOT)

    def test_coverage_projection_is_recomputed_and_frozen(self) -> None:
        payload, _ = self._payload()
        self.assertEqual(payload["coverage_projection"], {
            "claim_delta": 9,
            "classified_delta": 180,
            "segment_delta": 11,
            "unknown_delta": -180,
            "post_if_applied_alone": {"claim_count": 14516, "classified_bytes": 6124781, "segment_count": 16628, "unknown_bytes": 166675},
        })

    def test_source_is_raw_cfg_only_and_neutral_scope_is_not_overclaimed(self) -> None:
        exporter = self._implemented()
        source = (ROOT / "tools/export_rom_cgb_helper_bounded_cfg.py").read_text()
        self.assertIn("_raw_flow", source)
        self.assertIn("raw", source.lower())
        self.assertNotIn("CgbSoundStop", source)
        self.assertNotIn("import tools.verify_rom_cgb_helper_bounded_cfg", source)
        self.assertNotIn("from tools import verify_rom_cgb_helper_bounded_cfg", source)
        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(payload["scope"], SCOPE)
        self.assertEqual(payload["roots"][0]["id"], "cgb_helper_09b53c")
        self.assertEqual(payload["roots"][1]["id"], "cgb_helper_09b58c")
        serialized = json.dumps(payload, sort_keys=True)
        self.assertNotIn("CgbSoundStop", serialized)


if __name__ == "__main__":
    unittest.main()
