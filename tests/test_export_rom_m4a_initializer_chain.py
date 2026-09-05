from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
BASELINE_ARTIFACT = Path(
    "artifacts/rom-m4a-initializer-chain-precoverage-v1"
)
SCHEMA = "rom-m4a-initializer-chain-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
RANGES = [
    [0x09AA3C, 0x09AA90],
    [0x09AA90, 0x09AAB4],
    [0x09ACF8, 0x09ADC0],
    [0x09ADC0, 0x09AE10],
    [0x09B17C, 0x09B1E6],
    [0x09B1E8, 0x09B1F4],
]
RANGE_SHA256 = [
    "c782ff96fc49708def45c12c5ba3c4170449390bf0ea4aa389561e09f359013b",
    "7f208987daf90cface78da36557a0773839b56b2bf1fe174358f1a56cfebbc6f",
    "b2c254e31eb7da12ddfd1a22a1fecb176659d1cc344e70cb8cad311230c84c9a",
    "5b0dd3fbbfc9f8c964f9c0f806548ccd9b72059ee6b67188c9432ac2342652b0",
    "b89251f7ae5e7e69702a82f4777b07d2a5ed1747b3aa8cfb8ea90bbfe0c7c733",
    "93fd80ddfc01693c7d0a9011380fb8fc6fe9c830809470f90cdacb2979bf0c46",
]
PACKED_SHA256 = "f5c0a94ac06bf6750edc038e0db95fc5d4e96c321129e57a11abd461aa678ea7"
RANGE_VECTOR_SHA256 = "8bcba07694e7375d59dddeb3cb12eeb4903e61147c91723482d61d06a47dbd72"
GAP = [0x09B1E6, 0x09B1E8]
COVERAGE_SHA256 = "31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563"
COVERAGE_TOTALS = {
    "classified_bytes": 6_123_419,
    "unknown_bytes": 168_037,
    "claim_count": 14_493,
    "segment_count": 16_600,
}
FROZEN_COVERAGE_RECEIPT = {
    "path": "sequel/rom-byte-coverage.json",
    "schema": "rom-byte-coverage-v1",
    "sha256": COVERAGE_SHA256,
    "summary": COVERAGE_TOTALS,
    "promotion_bytes": 518,
    "unknown_promotion_bytes": 518,
    "primary_overlap_bytes": 0,
    "all_promotion_bytes_unknown": True,
    "target_segments": [
        {
            "range": interval,
            "primary_class": "unknown",
            "primary_claim_ids": [],
        }
        for interval in RANGES
    ],
}
UPSTREAM_RECEIPTS = {
    "soundmain": {
        "manifest_sha256": "e6b9a2cbdb439c520b5c98a422279e44e03866dbf1541810626d28eb57ce0a37",
        "payload_sha256": "63543ece1982ced20eb0818faf3b6f1848e72ba6dcdb68105fa8b2e3e07e477a",
        "verifier_sha256": "321d5ca5b7d6f887a21ec93c1bb06640f6e1397248273068bb5a13d3d7167d82",
    },
    "psg": {
        "manifest_sha256": "4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f",
        "payload_sha256": "d2631b1a65a2e9fa0114dbd76a4e2c89853e3b2f402a491fdbc466e79dacd733",
        "verifier_sha256": "c87ab33b067a35a0105e21967dc0caad5fe91368942f34baf91218d69258f616",
    },
    "mplaymain": {
        "manifest_sha256": "43399803451c393722522c9d2a363736541c34c37dd03d3cb2c1e292ed0b8f5d",
        "payload_sha256": "31bc026a8c83b3bf4af06746de2990a658bb86954a5aae31c45d63d68cf44f78",
        "verifier_sha256": "c064fc6a576a518cbd825630babc40d1c2dab2d369846078c3950b68748a2c2a",
    },
}


def _load_exporter():
    try:
        return importlib.import_module("tools.export_rom_m4a_initializer_chain")
    except ModuleNotFoundError:
        return None


class M4aInitializerChainExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter = _load_exporter()

    def _implemented(self):
        self.assertIsNotNone(self.exporter, "m4a initializer-chain exporter is absent")
        return self.exporter

    @staticmethod
    def _frozen_coverage(exporter):
        return mock.patch.object(
            exporter,
            "_coverage_baseline",
            side_effect=lambda _root: json.loads(
                json.dumps(FROZEN_COVERAGE_RECEIPT)
            ),
        )

    def _mutated_payload(self, mutations: dict[int, bytes]):
        exporter = self._implemented()
        changed = bytearray(self.rom)
        for offset, raw in mutations.items():
            changed[offset : offset + len(raw)] = raw
        changed = bytes(changed)
        with (
            mock.patch.object(
                exporter, "ROM_SHA256", hashlib.sha256(changed).hexdigest()
            ),
            self._frozen_coverage(exporter),
        ):
            return exporter.build_payload_from_rom(ROOT, changed)

    def test_build_payload_freezes_six_ranges_and_expected_totals(self) -> None:
        exporter = self._implemented()
        with self._frozen_coverage(exporter):
            payload, bundle = exporter.build_payload(ROOT)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["rom"], {
            "path": "rom/base.gba", "size": 0x600000, "sha256": ROM_SHA256,
        })
        self.assertEqual(payload["promotion"]["ranges"], RANGES)
        self.assertEqual(payload["promotion"]["range_count"], 6)
        self.assertEqual(payload["promotion"]["byte_count"], 518)
        self.assertEqual(payload["promotion"]["range_sha256"], RANGE_SHA256)
        self.assertEqual(payload["promotion"]["packed_bytes_sha256"], PACKED_SHA256)
        self.assertEqual(payload["promotion"]["range_vector_sha256"], RANGE_VECTOR_SHA256)
        self.assertEqual(
            payload["coverage_projection"],
            {
                "pre": COVERAGE_TOTALS,
                "post": {
                    "classified_bytes": 6_123_937,
                    "unknown_bytes": 167_519,
                    "claim_count": 14_499,
                    "segment_count": 16_608,
                },
                "classified_delta": 518,
                "unknown_delta": -518,
                "claim_delta": 6,
                "segment_delta": 8,
            },
        )
        self.assertEqual(len(bundle), 518)
        self.assertEqual(hashlib.sha256(bundle).hexdigest(), PACKED_SHA256)
        self.assertEqual(payload["summary"]["instruction_count"], 188)
        self.assertEqual(payload["summary"]["instruction_bytes"], 390)
        self.assertEqual(payload["summary"]["block_count"], 25)
        self.assertEqual(payload["summary"]["internal_edge_count"], 31)
        self.assertEqual(payload["summary"]["direct_call_count"], 7)
        self.assertEqual(payload["summary"]["literal_ref_count"], 33)
        self.assertEqual(payload["summary"]["literal_word_count"], 32)
        self.assertEqual(payload["summary"]["literal_bytes"], 128)
        self.assertEqual(payload["summary"]["frontier_count"], 0)
        self.assertEqual(payload["summary"]["promoted_bytes"], 518)
        self.assertEqual(payload["unclassified_unknown_ranges"], [GAP])

    def test_manifest_contract_has_semantic_vectors_and_explicit_nonclaims(self) -> None:
        exporter = self._implemented()
        with self._frozen_coverage(exporter):
            payload, _ = exporter.build_payload(ROOT)
        self.assertEqual(
            [(row["id"], row["kind"], row["range"], row["sha256"], row["mode"])
             for row in payload["promotion_ranges"]],
            [
                ("m4a-sound-init-code-09aa3c", "bounded_thumb_code", RANGES[0], RANGE_SHA256[0], "thumb"),
                ("m4a-sound-init-literals-09aa90", "consumed_literals", RANGES[1], RANGE_SHA256[1], None),
                ("psg-initializer-code-09acf8", "bounded_thumb_code", RANGES[2], RANGE_SHA256[2], "thumb"),
                ("psg-initializer-literals-09adc0", "consumed_literals", RANGES[3], RANGE_SHA256[3], None),
                ("mplay-open-code-09b17c", "bounded_thumb_code", RANGES[4], RANGE_SHA256[4], "thumb"),
                ("mplay-open-literals-09b1e8", "consumed_literals", RANGES[5], RANGE_SHA256[5], None),
            ],
        )
        self.assertEqual(len(payload["cfg"]["instructions"]), 188)
        self.assertEqual(len(payload["cfg"]["blocks"]), 25)
        self.assertEqual(len(payload["cfg"]["block_edges"]), 31)
        self.assertEqual(len(payload["literal_bindings"]), 33)
        producer = payload["producer_denominator"]
        self.assertEqual(producer["all_non_thumb_bl_forms_empty"], True)
        self.assertEqual(producer["thumb_bl"], [0x061E28, 0x09AA56, 0x09AA76])
        for root in ("0x09AA3C", "0x09ACF8", "0x09B17C"):
            self.assertEqual(producer["root_forms"][root]["thumb_bl"], {
                "0x09AA3C": [0x061E28],
                "0x09ACF8": [0x09AA56],
                "0x09B17C": [0x09AA76],
            }[root])
            for form in ("thumb_b", "thumb_b_conditional", "arm_b", "arm_bl",
                         "bytewise_u32_entry", "bytewise_u32_thumb_pointer"):
                self.assertEqual(producer["root_forms"][root][form], [])
        self.assertFalse(payload["producer_denominator"]["producer_source_instruction_membership_proven"])
        self.assertFalse(payload["producer_denominator"]["producer_bytes_promoted"])
        self.assertEqual(payload["coverage_baseline"]["sha256"], COVERAGE_SHA256)
        self.assertEqual(payload["coverage_baseline"]["summary"], COVERAGE_TOTALS)
        self.assertEqual(payload["coverage_baseline"]["promotion_bytes"], 518)
        self.assertEqual(payload["coverage_baseline"]["primary_overlap_bytes"], 0)
        self.assertEqual(payload["upstream_receipts"], UPSTREAM_RECEIPTS)
        self.assertEqual(payload["gap_exclusion"], {
            "ranges": [GAP], "bytes": 2, "sha256": "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
            "promotion_excluded": True, "semantic_label": "unknown",
        })
        for key in ("source_instruction_membership_complete", "dynamic_callback_values_proven",
                    "natural_runtime_reachability_complete", "global_caller_denominator_complete",
                    "editing_relocation_writeback_safe", "allocatable_free_space_proven"):
            self.assertFalse(payload["scope"][key])

        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as raw:
            candidate = Path(raw) / "candidate"
            with self._frozen_coverage(exporter):
                exporter.write_candidate(ROOT, candidate)
            manifest = json.loads((candidate / exporter.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(
                set(manifest),
                {
                    "schema", "artifact_schema", "artifact_status", "rom",
                    "coverage_baseline", "coverage_projection", "upstream_receipts",
                    "promotion", "promotion_ranges", "semantic_contract",
                    "producer_denominator", "gap_exclusion", "scope", "limitations",
                    "files", "implementation", "producer", "verification", "summary",
                },
            )
            self.assertEqual(manifest["promotion_ranges"], payload["promotion_ranges"])
            self.assertEqual(manifest["producer_denominator"], payload["producer_denominator"])
            self.assertEqual(
                manifest["semantic_contract"],
                {
                    "semantic_instruction_vector_sha256": payload["cfg"]["semantic_instruction_vector_sha256"],
                    "edge_vector_sha256": payload["cfg"]["edge_vector_sha256"],
                    "literal_binding_vector_sha256": payload["literal_binding_vector_sha256"],
                    "producer_form_vector_sha256": payload["producer_denominator"]["producer_form_vector_sha256"],
                    "range_vector_sha256": RANGE_VECTOR_SHA256,
                    "packed_bytes_sha256": PACKED_SHA256,
                },
            )

    def test_each_range_byte_mutation_and_gap_mutation_fail_closed(self) -> None:
        for start, end in RANGES + [GAP]:
            with self.subTest(range=(start, end)):
                raw = bytearray(self.rom[start : start + 1])
                raw[0] ^= 1
                with self.assertRaises(ValueError):
                    self._mutated_payload({start: bytes(raw)})

    def test_duplicate_producer_and_raw_cfg_literal_escapes_fail_closed(self) -> None:
        exporter = self._implemented()
        # Thumb BL encoding for an additional call to each frozen root at 0x100.
        def bl_at(offset: int, target: int) -> bytes:
            displacement = target - (offset + 4)
            encoded = displacement & 0x7FFFFF
            return ((0xF000 | ((encoded >> 12) & 0x7FF)).to_bytes(2, "little") +
                    (0xF800 | ((encoded >> 1) & 0x7FF)).to_bytes(2, "little"))

        with self.assertRaisesRegex(ValueError, "producer"):
            self._mutated_payload({0x100: bl_at(0x100, 0x09AA3C)})
        for offset, raw in ((0x09AA68, b"\x00\xe0"), (0x09AA3E, b"\xff\x48"), (0x09ACFE, b"\xff\x48")):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self._mutated_payload({offset: raw})

    def test_upstream_receipt_coverage_owner_and_nonempty_output_are_guarded(self) -> None:
        exporter = self._implemented()
        with mock.patch.object(exporter, "UPSTREAM_RECEIPTS", {"soundmain": {"manifest_sha256": "0"}}):
            with self.assertRaisesRegex(ValueError, "upstream"):
                exporter.build_payload(ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments/active") as raw:
            output = Path(raw) / "nonempty"
            output.mkdir()
            (output / "keep").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty"):
                exporter.write_candidate(ROOT, output)

    def test_live_post_coverage_cannot_be_reused_as_candidate_baseline(self) -> None:
        exporter = self._implemented()
        with self.assertRaisesRegex(ValueError, "coverage baseline identity"):
            exporter.build_payload(ROOT)

    def test_explicit_precoverage_artifact_builds_an_honest_candidate(self) -> None:
        exporter = self._implemented()
        payload, _ = exporter.build_payload(
            ROOT,
            coverage_baseline_artifact=BASELINE_ARTIFACT,
        )
        source = payload["coverage_baseline_source"]
        self.assertEqual("immutable-gzip-artifact", source["kind"])
        self.assertEqual(BASELINE_ARTIFACT.as_posix(), source["artifact"])
        self.assertEqual(COVERAGE_SHA256, source["raw_sha256"])
        self.assertEqual(23_097_532, source["raw_size"])

        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as raw:
            candidate = Path(raw) / "candidate"
            exporter.write_candidate(
                ROOT,
                candidate,
                coverage_baseline_artifact=BASELINE_ARTIFACT,
            )
            manifest = json.loads(
                (candidate / exporter.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(source, manifest["coverage_baseline_source"])
            self.assertEqual(
                [
                    "python3",
                    "tools/export_rom_m4a_initializer_chain.py",
                    "--coverage-baseline-artifact",
                    BASELINE_ARTIFACT.as_posix(),
                    "--output",
                    candidate.relative_to(ROOT).as_posix(),
                ],
                manifest["producer"]["command"],
            )

    def test_partial_primary_owner_inside_promotion_range_fails_closed(self) -> None:
        exporter = self._implemented()
        coverage = {
            "schema": "rom-byte-coverage-v1",
            "summary": dict(COVERAGE_TOTALS),
            "segments": [
                {
                    "range": list(interval),
                    "primary_class": "unknown",
                    "primary_claim_ids": [],
                }
                for interval in RANGES
            ],
        }
        start, end = RANGES[0]
        coverage["segments"][0:1] = [
            {
                "range": [start, start + 1],
                "primary_class": "foreign_primary",
                "primary_claim_ids": ["foreign-claim"],
            },
            {
                "range": [start + 1, end],
                "primary_class": "unknown",
                "primary_claim_ids": [],
            },
        ]
        with self.assertRaisesRegex(
            ValueError, "promotion ranges are not whole-range unknown"
        ):
            exporter.analyze_coverage_baseline(coverage)


if __name__ == "__main__":
    unittest.main()
