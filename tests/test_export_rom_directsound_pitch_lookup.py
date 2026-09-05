#!/usr/bin/env python3
"""TDD contract for the frozen DirectSound pitch lookup packet."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
COVERAGE = ROOT / "sequel/rom-byte-coverage.json"
SCHEMA = "rom-directsound-pitch-lookup-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "5c3c9bcaa90a4d55a2de5ef37effbd9947502aff75f01b73738b90aa704b0d9f"

CONSUMER_RANGE = [0x09A998, 0x09A9F4]
CONSUMER_SHA256 = "d04cce3da22f96b569d80a5fea059633e43b5daec754ffa268bf95ecbbddff40"
LITERAL_RANGE = [0x09A9F4, 0x09A9FC]
LITERAL_SHA256 = "c46d5afc346f36454cfdedf489cfeafc148e4f952887b63f8738339ea6fe1deb"
HELPER_RANGE = [0x099D7C, 0x099D8C]
HELPER_SHA256 = "1addb8be644cbaa9421a91f6cd6d91407907e9c92320f56ae49804b98fc29a81"
SCALE_RANGE = [0x4645C4, 0x464678]
SCALE_SHA256 = "52e19ba195ffad7aa82ac71bf26543d912f3e3a763e40c755ce0e71b674ef9e7"
FREQUENCY_RANGE = [0x464678, 0x4646A8]
FREQUENCY_SHA256 = "6b73747d3fb29635eeda13481d08a06e5371958ee746967aa892fa5390509404"

PROMOTION_RANGES = [
    HELPER_RANGE,
    CONSUMER_RANGE,
    LITERAL_RANGE,
    SCALE_RANGE,
    FREQUENCY_RANGE,
]
PROMOTION_VECTOR_SHA256 = "ac877e8eec80edbdab3d1b6f3991fc8a93dfc497a66c298dc9ee0c29034431bd"
PACKED_SHA256 = "cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850"

PRODUCERS = [
    {
        "file_offset": 0x09A654,
        "raw_hex": "00f0a0f9",
        "bytes_sha256": "3bafe4212ed9d14d56bccd395ff9c325fbe5a4a6f14f0d34b081b0cb74a6ff74",
        "target_file_offset": 0x09A998,
    },
    {
        "file_offset": 0x09A8DC,
        "raw_hex": "00f05cf8",
        "bytes_sha256": "5fc2d693651559bb36bd2b8ea97a263e5b7546576569baeab382e37a6a924eb7",
        "target_file_offset": 0x09A998,
    },
]

FREQUENCIES = [
    0x80000000,
    0x879C7C97,
    0x8FACD61E,
    0x9837F052,
    0xA14517CC,
    0xAADC0848,
    0xB504F334,
    0xBFC886BB,
    0xCB2FF52A,
    0xD744FCCB,
    0xE411F03A,
    0xF1A1BF39,
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _exporter():
    try:
        return importlib.import_module("tools.export_rom_directsound_pitch_lookup")
    except ModuleNotFoundError:
        return None


class DirectSoundPitchLookupExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter = _exporter()

    def _implemented(self):
        self.assertIsNotNone(
            self.exporter,
            "DirectSound pitch lookup exporter implementation is absent",
        )
        return self.exporter

    def test_build_payload_freezes_five_disjoint_semantic_ranges(self) -> None:
        exporter = self._implemented()
        payload, bundle = exporter.build_payload(ROOT)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["rom"]["size"], 0x600000)
        self.assertEqual(payload["rom"]["sha256"], ROM_SHA256)

        promotion = payload["promotion"]
        self.assertEqual(promotion["ranges"], PROMOTION_RANGES)
        self.assertEqual(promotion["range_count"], 5)
        self.assertEqual(promotion["byte_count"], 344)
        self.assertEqual(promotion["range_vector_sha256"], PROMOTION_VECTOR_SHA256)
        self.assertEqual(promotion["packed_bytes_sha256"], PACKED_SHA256)
        self.assertEqual(len(bundle), 344)
        self.assertEqual(_sha(bundle), PACKED_SHA256)
        self.assertEqual(
            bundle,
            b"".join(self.rom[start:end] for start, end in PROMOTION_RANGES),
        )

        by_kind = {item["kind"]: item for item in promotion["semantic_ranges"]}
        self.assertEqual(by_kind["directsound_pitch_consumer_code"]["range"], CONSUMER_RANGE)
        self.assertEqual(by_kind["directsound_pitch_consumer_code"]["sha256"], CONSUMER_SHA256)
        self.assertEqual(by_kind["directsound_pitch_table_literals"]["range"], LITERAL_RANGE)
        self.assertEqual(by_kind["directsound_pitch_table_literals"]["sha256"], LITERAL_SHA256)
        self.assertEqual(by_kind["directsound_pitch_high32_interwork_code"]["range"], HELPER_RANGE)
        self.assertEqual(by_kind["directsound_pitch_high32_interwork_code"]["sha256"], HELPER_SHA256)
        self.assertEqual(by_kind["directsound_pitch_scale_table"]["range"], SCALE_RANGE)
        self.assertEqual(by_kind["directsound_pitch_scale_table"]["sha256"], SCALE_SHA256)
        self.assertEqual(by_kind["directsound_pitch_frequency_table"]["range"], FREQUENCY_RANGE)
        self.assertEqual(by_kind["directsound_pitch_frequency_table"]["sha256"], FREQUENCY_SHA256)

    def test_current_coverage_baseline_keeps_all_promotion_bytes_unknown(self) -> None:
        exporter = self._implemented()
        coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
        expected = {
            "path": "sequel/rom-byte-coverage.json",
            "schema": "rom-byte-coverage-v1",
            "sha256": COVERAGE_SHA256,
            "classified_bytes": 6_121_280,
            "unknown_bytes": 170_176,
            "claim_count": 14_466,
            "segment_count": 16_577,
            "promotion_bytes": 344,
            "unknown_promotion_bytes": 344,
            "primary_overlap_bytes": 0,
            "all_promotion_bytes_unknown": True,
        }
        payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(payload["coverage_baseline"], expected)
        self.assertEqual(exporter.analyze_coverage_baseline(coverage), expected)

        tampered = copy.deepcopy(coverage)
        for segment in tampered["segments"]:
            if segment["range"] == HELPER_RANGE:
                segment["primary_class"] = "already_owned"
                segment["primary_claim_ids"] = ["synthetic-overlap"]
                break
        with self.assertRaisesRegex(ValueError, "unknown|overlap"):
            exporter.analyze_coverage_baseline(tampered)

    def test_target_limited_raw_bl_denominator_is_exact_and_provenance_only(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        denominator = payload["producer_denominator"]
        self.assertEqual(denominator["scan"]["mode"], "thumb")
        self.assertEqual(denominator["scan"]["alignment_bytes"], 2)
        self.assertEqual(denominator["scan"]["range"], [0, 0x600000])
        self.assertEqual(denominator["scan"]["target_file_offset"], 0x09A998)
        self.assertEqual(denominator["scan"]["matching_producer_count"], 2)
        self.assertEqual(denominator["producers"], PRODUCERS)
        self.assertEqual(denominator["thumb_pointer_occurrences"], [])
        self.assertFalse(denominator["producer_source_instruction_membership_proven"])
        self.assertFalse(denominator["producer_bytes_promoted"])
        promoted = {
            offset
            for start, end in payload["promotion"]["ranges"]
            for offset in range(start, end)
        }
        for producer in PRODUCERS:
            self.assertTrue(
                set(range(producer["file_offset"], producer["file_offset"] + 4)).isdisjoint(promoted)
            )

    def test_thumb1_bl_decoder_handles_backward_signed_displacement(self) -> None:
        exporter = self._implemented()
        callsite = 0x100
        target = 0x80
        displacement = target - (callsite + 4)
        encoded = displacement & 0x7FFFFF
        first = 0xF000 | ((encoded >> 12) & 0x07FF)
        second = 0xF800 | ((encoded >> 1) & 0x07FF)
        synthetic = bytearray(0x200)
        synthetic[callsite : callsite + 2] = first.to_bytes(2, "little")
        synthetic[callsite + 2 : callsite + 4] = second.to_bytes(2, "little")

        self.assertEqual(exporter._thumb_bl_target(bytes(synthetic), callsite), target)

    def test_consumer_cfg_literal_bindings_and_stack_return_are_closed(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        consumer = payload["consumer"]
        self.assertEqual(consumer["root_file_offset"], 0x09A998)
        self.assertEqual(consumer["code_range"], CONSUMER_RANGE)
        self.assertEqual(consumer["code_sha256"], CONSUMER_SHA256)
        self.assertEqual(consumer["decoded_instruction_count"], 44)
        self.assertEqual(consumer["decoded_basic_block_count"], 5)
        self.assertEqual(
            consumer["block_ranges"],
            [
                [0x09A998, 0x09A9A6],
                [0x09A9A6, 0x09A9AC],
                [0x09A9AC, 0x09A9E4],
                [0x09A9E4, 0x09A9EE],
                [0x09A9EE, 0x09A9F4],
            ],
        )
        self.assertEqual(
            consumer["external_call_edges"],
            [
                {"source_file_offset": 0x09A9E0, "target_file_offset": 0x099D7C},
                {"source_file_offset": 0x09A9EA, "target_file_offset": 0x099D7C},
            ],
        )
        self.assertEqual(consumer["frontier_count"], 0)
        self.assertEqual(
            consumer["return_proof"],
            {
                "saved_lr_at_entry": True,
                "stack_adjustment_between_entry_and_epilogue": 0,
                "epilogue_range": [0x09A9EE, 0x09A9F4],
                "epilogue_raw_hex": "f0bc02bc0847",
                "restored_lr_register": "r1",
                "return_instruction": "bx r1",
            },
        )
        self.assertEqual(
            payload["literal_bindings"],
            [
                {
                    "load_file_offset": 0x09A9AC,
                    "load_raw_hex": "114b",
                    "literal_range": [0x09A9F4, 0x09A9F8],
                    "pointer": 0x084645C4,
                    "target_range": SCALE_RANGE,
                },
                {
                    "load_file_offset": 0x09A9B2,
                    "load_raw_hex": "114c",
                    "literal_range": [0x09A9F8, 0x09A9FC],
                    "pointer": 0x08464678,
                    "target_range": FREQUENCY_RANGE,
                },
            ],
        )

    def test_interwork_helper_and_exact_integer_formula_are_bound(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        helper = payload["high32_helper"]
        self.assertEqual(helper["range"], HELPER_RANGE)
        self.assertEqual(helper["sha256"], HELPER_SHA256)
        self.assertEqual(helper["thumb_range"], [0x099D7C, 0x099D80])
        self.assertEqual(helper["arm_range"], [0x099D80, 0x099D8C])
        self.assertEqual(helper["decoded_instruction_count"], 5)
        self.assertEqual(helper["decoded_basic_block_count"], 2)
        self.assertEqual(helper["frontier_count"], 0)
        self.assertEqual(helper["state_switch"], "thumb_adr_bx_to_arm")
        self.assertEqual(helper["operation"], "unsigned_multiply_high32")
        self.assertEqual(
            payload["formula"],
            {
                "base_pitch": "freq[descriptor&15]>>(descriptor>>4)",
                "interpolation": "u32(p0+high32(u32(p1-p0),fine<<24))",
                "step": "high32(load_u32(input_r0+4),interpolated)",
            },
        )

    def test_table_domains_fail_closed_and_cover_every_frozen_entry(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        scale = payload["tables"]["scale"]
        self.assertEqual(scale["range"], SCALE_RANGE)
        self.assertEqual(scale["descriptor_count"], 180)
        self.assertEqual(scale["key_index_domain"], [0, 179])
        self.assertEqual(scale["frequency_index_domain"], [0, 11])
        self.assertEqual(scale["shift_domain"], [0, 14])
        self.assertEqual(scale["frequency_index_counts"], {str(i): 15 for i in range(12)})
        self.assertEqual(scale["shift_counts"], {str(i): 12 for i in range(15)})
        frequency = payload["tables"]["frequency"]
        self.assertEqual(frequency["range"], FREQUENCY_RANGE)
        self.assertEqual(frequency["entry_count"], 12)
        self.assertEqual(frequency["entry_size"], 4)
        self.assertEqual(frequency["values_u32"], FREQUENCIES)
        self.assertEqual(
            payload["input_domain"],
            {
                "raw_key_u8": [0, 255],
                "effective_key": [0, 178],
                "clamped_raw_keys": [179, 255],
                "fine_u8": [0, 255],
                "clamped_fine": 255,
                "scale_access_union": [0, 179],
                "frequency_access_union": [0, 11],
            },
        )

        invalid = bytearray(self.rom[SCALE_RANGE[0] : SCALE_RANGE[1]])
        invalid[0] = (invalid[0] & 0xF0) | 0x0C
        with self.assertRaisesRegex(ValueError, "frequency index"):
            exporter.analyze_scale_descriptors(bytes(invalid))

    def test_scope_keeps_callers_runtime_and_editing_unclaimed(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        scope = payload["scope"]
        self.assertTrue(scope["target_limited_raw_bl_denominator_complete"])
        self.assertTrue(scope["consumer_cfg_closed"])
        self.assertTrue(scope["helper_interwork_closed"])
        self.assertTrue(scope["table_index_domain_complete_for_all_u8_inputs"])
        for key in (
            "producer_source_instruction_membership_complete",
            "producer_bytes_promoted",
            "natural_runtime_reachability_complete",
            "global_code_denominator_complete",
            "global_caller_denominator_complete",
            "global_indirect_target_denominator_complete",
            "editing_relocation_writeback_safe",
            "allocatable_free_space_proven",
        ):
            self.assertFalse(scope[key])

    def test_cli_writes_deterministic_candidate_without_touching_canonical(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "candidate"
            exporter.write_artifact(ROOT, output)
            payload = json.loads(
                (output / "rom-directsound-pitch-lookup.json").read_text(encoding="utf-8")
            )
            bundle = (output / "rom-directsound-pitch-lookup.bin").read_bytes()
            expected, expected_bundle = exporter.build_payload(ROOT)
            self.assertEqual(payload, expected)
            self.assertEqual(bundle, expected_bundle)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["coverage_baseline"], expected["coverage_baseline"])

    def test_repository_local_candidate_output_is_allowed(self) -> None:
        exporter = self._implemented()
        active = ROOT / "build/experiments/active"
        with tempfile.TemporaryDirectory(dir=active) as temporary:
            output = Path(temporary) / "candidate"
            exporter.write_artifact(ROOT, output)
            self.assertTrue((output / "manifest.json").is_file())

    def test_foreign_same_named_output_directory_is_not_overwritten(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "candidate"
            output.mkdir()
            (output / "rom-directsound-pitch-lookup.json").write_text("{}\n")
            (output / "rom-directsound-pitch-lookup.bin").write_bytes(b"foreign")
            (output / "manifest.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "foreign|schema"):
                exporter.write_artifact(ROOT, output)
            self.assertEqual(
                (output / "rom-directsound-pitch-lookup.bin").read_bytes(),
                b"foreign",
            )

    def test_output_symlink_component_is_rejected_without_following_target(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.write_artifact(ROOT, linked / "candidate")
            self.assertEqual(list(real.iterdir()), [])

    def test_preexisting_backup_collision_is_preserved_and_rejected(self) -> None:
        exporter = self._implemented()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "candidate"
            exporter.write_artifact(ROOT, output)
            collision = output.with_name(f".{output.name}.old-{os.getpid()}")
            collision.mkdir()
            sentinel = collision / "sentinel.txt"
            sentinel.write_text("owned by someone else\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "backup|collision"):
                exporter.write_artifact(ROOT, output)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "owned by someone else\n")


if __name__ == "__main__":
    unittest.main()
