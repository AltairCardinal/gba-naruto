from __future__ import annotations

import gzip
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
EXPERIMENT = ROOT / "build/experiments/active/mp2k-note-allocator-contract-20260829"
SCHEMA = "rom-mp2k-note-allocator-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "ab315087593f23bfbcc96c66ac99b8bfd002e5c29cd462088dda343139f9ac27"
COVERAGE_TOTALS = {"classified_bytes": 6_123_937, "unknown_bytes": 167_519, "claim_count": 14_499, "segment_count": 16_608}
PROJECTED_TOTALS = {"classified_bytes": 6_124_499, "unknown_bytes": 166_957, "claim_count": 14_503, "segment_count": 16_614}
RANGES = [[0x09A6D8, 0x09A708], [0x09A708, 0x09A8FE], [0x09A900, 0x09A908], [0x09AF24, 0x09AF28]]
FROZEN_COVERAGE = {"path": "sequel/rom-byte-coverage.json", "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256, "summary": COVERAGE_TOTALS, "promotion_bytes": 562, "unknown_promotion_bytes": 562, "primary_overlap_bytes": 0, "all_promotion_bytes_unknown": True, "target_segments": [{"range": list(interval), "primary_class": "unknown", "primary_claim_ids": []} for interval in RANGES]}
RANGE_SHA256 = [
    "04988bf8e911a12b477d9aafa24342b68e83960a06796e555869cc67b24bd4d2",
    "4c78dfb62e2d92b0b0ed96c8d05e86d3d2867a1bb2a76c82818a672f380eee2e",
    "aea41d042f130b46329f8b5a5fdb976816ec280b367dc424f28bc624072867c1",
    "ee8951cbf1e4a1f69fce481a4537a84678e2615bc7e3f175ff69a97044ab7016",
]
PACKED_SHA256 = "3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c"
UNION_RANGES = [[0x09A6D8, 0x09A8FE], [0x09A900, 0x09A908], [0x09AF24, 0x09AF28]]
UNION_VECTOR_SHA256 = "bd9139f26305fea7813e7daf944d6a6e131861b31c3c98065b5e7d13bf65c88b"
EXCLUDED_RANGES = [[0x09A6D2, 0x09A6D8], [0x09A8FE, 0x09A900], [0x09AEF4, 0x09AF24], [0x09AF28, 0x09AF34]]
EXCLUDED_SHA256 = [
    "83391c178e79facc3d1c0dd948f1d4e3fc46d08591ae8929948a5e028b724daa",
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    "e3f15479ef984fff85b6ec764159375c16eeecf938f7671851aaf38d2a2211ae",
    "56573725cd7c0ffc2159a0d40123cef9750f00c2f444a04492a4b32117cf4bc7",
]
UPSTREAM_RECEIPTS = {
    "mplaymain": {
        "manifest_sha256": "43399803451c393722522c9d2a363736541c34c37dd03d3cb2c1e292ed0b8f5d",
        "payload_sha256": "31bc026a8c83b3bf4af06746de2990a658bb86954a5aae31c45d63d68cf44f78",
        "exporter_sha256": "366c4e41db80c797bd01f36477a67243ac08f4d20d71e596c1332f273deed18d",
        "verifier_sha256": "c064fc6a576a518cbd825630babc40d1c2dab2d369846078c3950b68748a2c2a",
        "test_sha256": "e3804e5833b0d4249b286da8e1428397c02e8b04bd205e20c96e8ab1920b540c",
    },
    "initializer": {
        "manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c",
        "payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd",
        "exporter_sha256": "4e0b8743247d9098a9d72667f4b2499abee1c71c45cd5a704feaa54f17a4ced9",
        "verifier_sha256": "5cd9ccf232ebb10c69e89962e9861add7675dfb935c6e6a293b16049fd6cec31",
        "test_sha256": "b6ed2f247641c74bb1631e4bfb0e449d48ec1be03a7af08c4eecabcc8c297326",
    },
    "sappy_bank_sha256": "d71d8aff52746a61d59139d6ca4ccf3a9dd354b84ef90159276ca541cf82eb40",
    "sappy_runtime_manifest_sha256": "62b97082417cc7d049b62bbb0bacfc92271e9924f674b13d6d5ee0fd8864fde8",
}
FIRST_BLOCKS = [[0x09A6D8, 0x09A6EE], [0x09A6EE, 0x09A6F0], [0x09A6F0, 0x09A702], [0x09A702, 0x09A704], [0x09A704, 0x09A708]]
SECOND_BLOCKS = [
    [0x09A708, 0x09A730], [0x09A730, 0x09A73A], [0x09A73A, 0x09A744], [0x09A744, 0x09A74C],
    [0x09A74C, 0x09A74E], [0x09A74E, 0x09A75E], [0x09A75E, 0x09A766], [0x09A766, 0x09A76E],
    [0x09A76E, 0x09A770], [0x09A770, 0x09A786], [0x09A786, 0x09A788], [0x09A788, 0x09A78E],
    [0x09A78E, 0x09A796], [0x09A796, 0x09A79C], [0x09A79C, 0x09A7A0], [0x09A7A0, 0x09A7A4],
    [0x09A7A4, 0x09A7B2], [0x09A7B2, 0x09A7B4], [0x09A7B4, 0x09A7C2], [0x09A7C2, 0x09A7CA],
    [0x09A7CA, 0x09A7CC], [0x09A7CC, 0x09A7DA], [0x09A7DA, 0x09A7E0], [0x09A7E0, 0x09A7E8],
    [0x09A7E8, 0x09A7EA], [0x09A7EA, 0x09A7EC], [0x09A7EC, 0x09A7F2], [0x09A7F2, 0x09A7F4],
    [0x09A7F4, 0x09A802], [0x09A802, 0x09A80A], [0x09A80A, 0x09A810], [0x09A810, 0x09A814],
    [0x09A814, 0x09A81C], [0x09A81C, 0x09A820], [0x09A820, 0x09A826], [0x09A826, 0x09A82C],
    [0x09A82C, 0x09A82E], [0x09A82E, 0x09A834], [0x09A834, 0x09A838], [0x09A838, 0x09A83A],
    [0x09A83A, 0x09A83C], [0x09A83C, 0x09A842], [0x09A842, 0x09A848], [0x09A848, 0x09A84E],
    [0x09A84E, 0x09A85A], [0x09A85A, 0x09A85C], [0x09A85C, 0x09A868], [0x09A868, 0x09A86E],
    [0x09A86E, 0x09A876], [0x09A876, 0x09A89C], [0x09A89C, 0x09A8A6], [0x09A8A6, 0x09A8A8],
    [0x09A8A8, 0x09A8AE], [0x09A8AE, 0x09A8BC], [0x09A8BC, 0x09A8C2], [0x09A8C2, 0x09A8C4],
    [0x09A8C4, 0x09A8D4], [0x09A8D4, 0x09A8D6], [0x09A8D6, 0x09A8E0], [0x09A8E0, 0x09A8EE],
    [0x09A8EE, 0x09A8FE],
]


def _load_exporter():
    try:
        return importlib.import_module("tools.export_rom_mp2k_note_allocator")
    except ModuleNotFoundError:
        return None


class Mp2kNoteAllocatorExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter = _load_exporter()

    def _implemented(self):
        self.assertIsNotNone(self.exporter, "MP2K note allocator exporter is absent")
        return self.exporter

    def _payload(self, **kwargs):
        return self._implemented().build_payload(ROOT, **kwargs)

    def test_immutable_identities_and_four_ranges(self) -> None:
        payload, bundle = self._payload()
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["rom"], {"path": "rom/base.gba", "size": 0x600000, "sha256": ROM_SHA256})
        self.assertEqual(payload["coverage_baseline"]["sha256"], COVERAGE_SHA256)
        self.assertEqual(payload["coverage_baseline"]["summary"], COVERAGE_TOTALS)
        self.assertEqual(payload["upstream_receipts"], UPSTREAM_RECEIPTS)
        self.assertEqual(payload["promotion"]["ranges"], RANGES)
        self.assertEqual(payload["promotion"]["range_sha256"], RANGE_SHA256)
        self.assertEqual(payload["promotion"]["range_count"], 4)
        self.assertEqual(payload["promotion"]["byte_count"], 562)
        self.assertEqual(payload["promotion"]["union_ranges"], UNION_RANGES)
        self.assertEqual(payload["promotion"]["range_vector_sha256"], UNION_VECTOR_SHA256)
        self.assertEqual(payload["promotion"]["packed_bytes_sha256"], PACKED_SHA256)
        self.assertEqual(hashlib.sha256(bundle).hexdigest(), PACKED_SHA256)
        self.assertEqual(payload["coverage_projection"]["post"], PROJECTED_TOTALS)
        self.assertEqual(len(payload["coverage_claims"]), 4)
        self.assertEqual(
            [claim["id"] for claim in payload["coverage_claims"]],
            ["mp2k-channel-gain-code-09a6d8", "mp2k-note-allocator-code-09a708", "mp2k-note-allocator-literals-09a900", "mp2k-note-entry-pointer-09af24"],
        )

    def test_producers_cfg_literals_pointer_and_nonclaims(self) -> None:
        payload, _ = self._payload()
        producer = payload["producer_denominator"]
        self.assertEqual(producer["root_forms"], {
            "0x09A6D8": {"thumb_bl": [0x09A60C, 0x09A898], "thumb_b": [], "thumb_b_conditional": [], "arm_b": [], "arm_bl": [], "bytewise_u32_entry": [], "bytewise_u32_thumb_pointer": []},
            "0x09A708": {"thumb_bl": [], "thumb_b": [], "thumb_b_conditional": [], "arm_b": [], "arm_bl": [], "bytewise_u32_entry": [], "bytewise_u32_thumb_pointer": [0x09AF24]},
        })
        self.assertEqual(producer["producer_roles"], [
            {"target_offset": 0x09A6D8, "form": "thumb_bl", "source_offset": 0x09A60C, "role": "preowned_provenance", "owner_claim_id": "mplaymain-code-00-09a42c", "promoted": False},
            {"target_offset": 0x09A6D8, "form": "thumb_bl", "source_offset": 0x09A898, "role": "included_root_call_edge", "owner_claim_id": None, "promoted": True},
            {"target_offset": 0x09A708, "form": "bytewise_u32_thumb_pointer", "source_offset": 0x09AF24, "role": "promoted_entry_pointer", "owner_claim_id": None, "promoted": True},
        ])
        self.assertTrue(producer["target_limited_raw_producer_denominator_complete"])
        self.assertTrue(producer["all_producer_source_membership_proven"])
        self.assertFalse(producer["all_producer_bytes_promoted"])
        self.assertEqual(producer["producer_source_membership_by_role"], {
            "preowned_provenance": True,
            "included_root_call_edge": True,
            "promoted_entry_pointer": True,
        })
        self.assertFalse(producer["global_producer_denominator_complete"])
        self.assertEqual(payload["literal_bindings"], [
            {"instruction_offset": 0x09A71A, "raw": 0x4979, "literal_offset": 0x09A900, "value": 0x03007FF0, "raw_hex": "f07f0003"},
            {"instruction_offset": 0x09A720, "raw": 0x4978, "literal_offset": 0x09A904, "value": 0x084647A8, "raw_hex": "a8474608"},
        ])
        pointer = payload["entry_pointer"]
        self.assertEqual(pointer["raw_hex"], "09a70908")
        self.assertEqual(pointer["occurrences"], [0x09AF24])
        self.assertEqual(pointer["writer"]["owner_claim_id"], "bank-sappy-engine-000")
        self.assertEqual(pointer["writer"]["owner_range"], [0x09AE3C, 0x09AEF4])
        self.assertEqual(pointer["writer"]["sappy_bank_sha256"], UPSTREAM_RECEIPTS["sappy_bank_sha256"])
        self.assertEqual(pointer["writer"]["runtime_manifest_sha256"], UPSTREAM_RECEIPTS["sappy_runtime_manifest_sha256"])
        self.assertEqual(pointer["consumer"]["command_source"], "u8")
        self.assertEqual(pointer["consumer"]["accepted_argument_domain"], [0, 48])
        self.assertEqual(pointer["consumer"]["accepted_value_count"], 49)
        self.assertFalse(pointer["global_ram_writer_denominator_complete"])
        self.assertEqual([
            {key: row[key] for key in ("range", "sha256", "promoted", "semantic_class")}
            for row in payload["excluded_ranges"]
        ], [
            {"range": interval, "sha256": digest, "promoted": False, "semantic_class": "unknown"}
            for interval, digest in zip(EXCLUDED_RANGES, EXCLUDED_SHA256)
        ])
        self.assertTrue(all(value is False for value in payload["scope"].values()))
        limits = " ".join(payload["limitations"])
        for term in ("natural runtime reachability", "global RAM writer", "audio behavior", "editing", "writeback", "relocation", "allocatable/free-space"):
            self.assertIn(term, limits)

    def test_cfg_has_exact_blocks_edges_calls_returns_and_epilogue(self) -> None:
        payload, _ = self._payload()
        cfg = payload["cfg"]
        self.assertEqual(cfg["summary"], {
            "instruction_count": 269, "instruction_bytes": 550, "code_bytes": 550,
            "block_count": 66, "ordinary_internal_edge_count": 98, "internal_edge_count": 99,
            "external_edge_count": 5, "direct_call_count": 6, "included_root_call_edge_count": 1,
            "opaque_external_call_count": 5, "structured_return_count": 2,
            "frontier_count": 0, "unresolved_frontier_count": 0, "budget_exhausted": False,
        })
        roots = {root["file_offset"]: root for root in cfg["roots"]}
        self.assertEqual(roots[0x09A6D8]["block_ranges"], FIRST_BLOCKS)
        self.assertEqual(roots[0x09A708]["block_ranges"], SECOND_BLOCKS)
        self.assertEqual(
            [(row["source_instruction_offset"], row["target_offset"], row["resolution"]) for row in cfg["calls"]],
            [(0x09A84A, 0x09AE14, "opaque_external_call"), (0x09A86A, 0x09A948, "opaque_external_call"), (0x09A872, 0x09B3E0, "opaque_external_call"), (0x09A898, 0x09A6D8, "included_root"), (0x09A8D0, 0x09A684, "opaque_existing_veneer"), (0x09A8DC, 0x09A998, "opaque_external_call")],
        )
        self.assertEqual([row["offset"] for row in cfg["returns"]], [0x09A706, 0x09A8FC])
        self.assertEqual(cfg["stack_epilogue"], {
            "range": [0x09A8EE, 0x09A8FE],
            "steps": [[0x09A8EE, "add sp,#0x18"], [0x09A8F0, "pop {r0, r1, r2, r3, r4, r5, r6, r7}"], [0x09A8F2, "mov r8, r0"], [0x09A8F4, "mov sb, r1"], [0x09A8F6, "mov sl, r2"], [0x09A8F8, "mov fp, r3"], [0x09A8FA, "pop {r0}"], [0x09A8FC, "bx r0"]],
            "return_offset": 0x09A8FC,
            "exact": True,
        })
        self.assertEqual(cfg["frontiers"], [])

    def test_mutations_partial_owners_and_excluded_neighbors_fail_closed(self) -> None:
        exporter = self._implemented()
        for start, end in RANGES:
            for offset in range(start, end):
                changed = bytearray(self.rom)
                changed[offset] ^= 1
                with self.subTest(offset=offset), mock.patch.object(exporter, "_validate_rom"), mock.patch.object(exporter, "_validate_upstream_receipts"), mock.patch.object(exporter, "_coverage_baseline", return_value=FROZEN_COVERAGE), mock.patch.object(exporter, "_analyze_cfg", side_effect=AssertionError("expensive scan ran")):
                    with self.assertRaisesRegex(ValueError, "promotion range"):
                        exporter.build_payload_from_rom(ROOT, bytes(changed))
        coverage = {"schema": "rom-byte-coverage-v1", "summary": dict(COVERAGE_TOTALS), "segments": [{"range": list(interval), "primary_class": "unknown", "primary_claim_ids": []} for interval in RANGES]}
        coverage["segments"][0:1] = [{"range": [RANGES[0][0], RANGES[0][0] + 2], "primary_class": "foreign", "primary_claim_ids": ["foreign"]}, {"range": [RANGES[0][0] + 2, RANGES[0][1]], "primary_class": "unknown", "primary_claim_ids": []}]
        with self.assertRaisesRegex(ValueError, "whole-range unknown"):
            exporter.analyze_coverage_baseline(coverage)
        for offset in (0x09A6D4, 0x09A8FE, 0x09AEF4, 0x09AF28):
            changed = bytearray(self.rom)
            changed[offset] ^= 1
            with self.subTest(neighbor=offset), mock.patch.object(exporter, "ROM_SHA256", hashlib.sha256(changed).hexdigest()):
                with self.assertRaises(ValueError):
                    exporter.build_payload_from_rom(ROOT, bytes(changed))

    def test_optional_archived_precoverage_and_manifest(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            archive_dir = Path(raw) / "precoverage"
            archive_dir.mkdir()
            coverage_raw = (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
            archive_raw = gzip.compress(coverage_raw, mtime=0)
            (archive_dir / "rom-byte-coverage.json.gz").write_bytes(archive_raw)
            archive_manifest = {
                "schema": "rom-byte-coverage-prepromotion-baseline-v1",
                "artifact_status": "accepted",
                "coverage": {
                    "raw": {"canonical_json": True, "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256, "size": len(coverage_raw), "summary": COVERAGE_TOTALS},
                    "archive": {"compression": "gzip", "file": "rom-byte-coverage.json.gz", "sha256": hashlib.sha256(archive_raw).hexdigest(), "size": len(archive_raw)},
                },
                "recovery": {"kind": "frozen-prepromotion-baseline"},
            }
            (archive_dir / "manifest.json").write_text(json.dumps(archive_manifest, indent=2, sort_keys=True) + "\n")
            payload, _ = exporter.build_payload(ROOT, coverage_baseline_artifact=archive_dir.relative_to(ROOT))
            self.assertEqual(payload["coverage_baseline"]["summary"], COVERAGE_TOTALS)
            self.assertEqual(payload["coverage_baseline_source"]["raw_size"], len(coverage_raw))
            self.assertEqual(payload["coverage_baseline_source"]["archive_size"], len(archive_raw))
            output = Path(raw) / "candidate"
            exporter.write_candidate(ROOT, output, coverage_baseline_artifact=archive_dir.relative_to(ROOT))
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["artifact_status"], "candidate")
            self.assertEqual(manifest["files"]["rom-mp2k-note-allocator.bin"]["sha256"], PACKED_SHA256)
            self.assertEqual(manifest["coverage_baseline_source"]["artifact"], archive_dir.relative_to(ROOT).as_posix())
            bad = Path(raw) / "bad"
            bad.mkdir()
            (bad / "rom-byte-coverage.json.gz").write_bytes(archive_raw[:-1])
            (bad / "manifest.json").write_text("{}")
            with self.assertRaises(ValueError):
                exporter.build_payload(ROOT, coverage_baseline_artifact=bad.relative_to(ROOT))
            link = Path(raw) / "archive-link"
            link.symlink_to(archive_dir, target_is_directory=True)
            with self.assertRaises(ValueError):
                exporter.build_payload(ROOT, coverage_baseline_artifact=link.relative_to(ROOT))
            absolute_link = Path(raw) / "absolute-archive-link"
            absolute_link.symlink_to(archive_dir, target_is_directory=True)
            with self.assertRaises(ValueError):
                exporter.build_payload(ROOT, coverage_baseline_artifact=absolute_link)
            absolute_parent_link = Path(raw) / "absolute-parent-link"
            absolute_parent_link.symlink_to(archive_dir.parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                exporter.build_payload(ROOT, coverage_baseline_artifact=absolute_parent_link / archive_dir.name)

    def test_consumer_fixed_cell_domain_and_veneer_mutations_fail_closed(self) -> None:
        exporter = self._implemented()
        for offset in (0x09A462, 0x09A68C, 0x09A500, 0x09A684):
            changed = bytearray(self.rom)
            changed[offset] ^= 1
            with self.subTest(offset=offset), mock.patch.object(exporter, "ROM_SHA256", hashlib.sha256(changed).hexdigest()):
                with self.assertRaises(ValueError):
                    exporter.build_payload_from_rom(ROOT, bytes(changed))

    def test_range_vector_schema_and_epilogue_mutations_fail_closed(self) -> None:
        exporter = self._implemented()
        with mock.patch.object(exporter, "PROMOTION_RANGES", [[0x09A6D9, 0x09A708], *RANGES[1:]]):
            with self.assertRaises(ValueError):
                self._payload()
        with mock.patch.object(exporter, "PROMOTION_RANGE_SHA256", ["0" * 64, *RANGE_SHA256[1:]]):
            with self.assertRaises(ValueError):
                self._payload()
        with mock.patch.object(exporter, "PROMOTION_UNION_RANGES", [[0x09A6D8, 0x09A8FD], *UNION_RANGES[1:]]):
            with self.assertRaises(ValueError):
                self._payload()
        changed = bytearray(self.rom)
        changed[0x09A8F0] ^= 1
        with mock.patch.object(exporter, "ROM_SHA256", hashlib.sha256(changed).hexdigest()):
            with self.assertRaises(ValueError):
                exporter.build_payload_from_rom(ROOT, bytes(changed))

    def test_exporter_source_has_vendored_capstone_and_raw_crosscheck(self) -> None:
        source = (ROOT / "tools/export_rom_mp2k_note_allocator.py").read_text()
        self.assertIn("tools/_vendor", source)
        self.assertIn("capstone", source.lower())
        self.assertIn("_raw_flow", source)
        self.assertIn("raw/capstone", source)


if __name__ == "__main__":
    unittest.main()
