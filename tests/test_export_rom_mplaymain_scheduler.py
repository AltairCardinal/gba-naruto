from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPORTER_PATH = ROOT / "tools/export_rom_mplaymain_scheduler.py"
VERIFIER_PATH = ROOT / "tools/verify_rom_mplaymain_scheduler.py"


def _load_exporter():
    spec = importlib.util.spec_from_file_location("export_rom_mplaymain_scheduler", EXPORTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load MPlayMain scheduler exporter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_rom_mplaymain_scheduler", VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load MPlayMain scheduler verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MPlayMainSchedulerExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = _load_exporter()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def _build_mutated(self, mutations: dict[int, bytes]):
        changed = bytearray(self.rom)
        for offset, raw in mutations.items():
            changed[offset : offset + len(raw)] = raw
        changed = bytes(changed)
        with mock.patch.object(
            self.exporter,
            "ROM_SHA256",
            hashlib.sha256(changed).hexdigest(),
        ):
            return self.exporter.build_payload_from_rom(ROOT, changed)

    def test_live_rom_rebuilds_the_frozen_612_byte_packet(self):
        payload, bundle = self.exporter.build_payload_from_rom(ROOT, self.rom)

        self.assertEqual(payload["schema"], "rom-mplaymain-scheduler-v1")
        self.assertEqual(payload["roots"], [{
            "mode": "thumb",
            "file_offset": 0x09A42C,
            "gba_address": "0x0809A42C",
            "thumb_pointer": "0x0809A42D",
        }])
        self.assertEqual(payload["code_ranges"], [[0x09A42C, 0x09A684]])
        self.assertEqual(payload["literal_ranges"], [[0x09A688, 0x09A694]])
        self.assertEqual(payload["owned_provenance_ranges"], [[0x09A684, 0x09A686]])
        self.assertEqual(payload["unclassified_unknown_ranges"], [[0x09A686, 0x09A688]])
        self.assertEqual(payload["promotion"]["union_ranges"], [
            [0x09A42C, 0x09A684],
            [0x09A688, 0x09A694],
        ])
        self.assertEqual(payload["promotion"]["union_range_vector_sha256"],
                         "a8e11002ba5439c3d758e03faa1850a686e749cbe3230496f871329283300b4d")
        self.assertEqual(len(bundle), 612)
        self.assertEqual(hashlib.sha256(bundle).hexdigest(),
                         "8ca6a2f02cd27d46b9d0e9dbae2491672f23702ee2230eb73fc460759ef14955")

        self.assertEqual(payload["summary"], {
            "instruction_count": 289,
            "instruction_bytes": 600,
            "code_bytes": 600,
            "block_count": 81,
            "internal_edge_count": 117,
            "external_edge_count": 12,
            "external_target_count": 7,
            "literal_ref_count": 4,
            "literal_word_count": 3,
            "literal_bytes": 12,
            "frontier_count": 1,
            "return_count": 1,
            "raw_indirect_pc_count": 0,
            "owned_indirect_veneer_count": 1,
            "promoted_bytes": 612,
            "owned_provenance_bytes": 2,
            "unclassified_unknown_bytes": 2,
            "budget_exhausted": False,
        })

    def test_entry_proof_binds_unique_pointer_writer_consumer_and_thunks(self):
        payload, _ = self.exporter.build_payload_from_rom(ROOT, self.rom)
        proof = payload["entry_proof"]

        denominator = proof["pointer_denominator"]
        self.assertEqual(denominator["pointer_value"], "0x0809A42D")
        self.assertEqual(denominator["bytewise_u32_occurrences"], [0x09B1F0])
        self.assertEqual(denominator["aligned_thumb_bl_producers"], [])
        self.assertFalse(denominator["global_ram_or_computed_producer_denominator_complete"])

        writer = proof["callback_writer"]
        self.assertEqual(writer["sound_info_global_cell"], "0x03007FF0")
        self.assertEqual(writer["writer_window"], [0x09B1C4, 0x09B1DA])
        self.assertEqual(writer["callback_slot_expression"], "(*u32[0x03007FF0])+0x20")
        self.assertEqual(writer["argument_slot_expression"], "(*u32[0x03007FF0])+0x24")
        self.assertFalse(writer["runtime_value_proven"])

        consumer = proof["callback_consumer"]
        self.assertEqual(consumer["callback_window"], [0x099DC0, 0x099DCC])
        self.assertEqual(consumer["indirect_thunk_range"], [0x09A1AE, 0x09A1B0])
        self.assertEqual(consumer["indirect_thunk_operation"], "bx r3")
        self.assertEqual(consumer["owner_claim_id"], "boot-thumb-handoff-code-22-09a1ae")

        recursive = proof["recursive_chain"]
        self.assertEqual(recursive["window"], [0x09A43C, 0x09A448])
        self.assertEqual(recursive["owned_veneer_range"], [0x09A684, 0x09A686])
        self.assertEqual(recursive["owner_claim_id"], "cfg-thumb-0752-09a684")
        self.assertEqual(recursive["incoming_sites"], [
            [0x09A444, "call_target"],
            [0x09A50E, "call_target"],
            [0x09A52A, "call_target"],
            [0x09A63E, "call_target"],
            [0x09A682, "fallthrough"],
        ])

    def test_cfg_and_literal_denominators_are_exact(self):
        payload, _ = self.exporter.build_payload_from_rom(ROOT, self.rom)

        external = [
            (item["source_instruction_offset"], item["kind"], item["target_offset"])
            for item in payload["external_edges"]
        ]
        self.assertEqual(external, [
            (0x09A444, "call_target", 0x09A684),
            (0x09A468, "call_target", 0x09B318),
            (0x09A4B8, "call_target", 0x09AE14),
            (0x09A4CC, "call_target", 0x09AE28),
            (0x09A50E, "call_target", 0x09A684),
            (0x09A52A, "call_target", 0x09A684),
            (0x09A5E4, "call_target", 0x09B3E0),
            (0x09A5F8, "call_target", 0x09AE14),
            (0x09A60C, "call_target", 0x09A6D8),
            (0x09A63E, "call_target", 0x09A684),
            (0x09A654, "call_target", 0x09A998),
            (0x09A682, "fallthrough", 0x09A684),
        ])
        literals = [
            (item["instruction_offset"], item["literal_offset"], item["value"])
            for item in payload["literal_bindings"]
        ]
        self.assertEqual(literals, [
            (0x09A536, 0x09A688, "0x084647A8"),
            (0x09A460, 0x09A68C, "0x03007FF0"),
            (0x09A42C, 0x09A690, "0x68736D53"),
            (0x09A674, 0x09A690, "0x68736D53"),
        ])
        self.assertEqual(payload["frontiers"], [{
            "reason": "opaque_indirect_r3_veneer",
            "veneer_range": [0x09A684, 0x09A686],
            "veneer_operation": "bx r3",
            "target_resolution": "computed_or_dynamic_unresolved",
            "incoming_sites": [0x09A444, 0x09A50E, 0x09A52A, 0x09A63E, 0x09A682],
        }])

    def test_old_414_byte_envelope_is_rejected_as_not_closed(self):
        with self.assertRaisesRegex(ValueError, "escaped candidate code"):
            self.exporter.analyze_code_range(self.rom, 0x09A42C, 0x09A5CA)

    def test_pointer_literal_and_duplicate_occurrence_mutations_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "MPlayMain pointer literal changed"):
            self._build_mutated({0x09B1F0: b"\x2f\xa4\x09\x08"})
        with self.assertRaisesRegex(ValueError, "MPlayMain pointer occurrence denominator changed"):
            self._build_mutated({0x000100: bytes.fromhex("2da40908")})

    def test_writer_consumer_and_recursive_thunk_mutations_fail_closed(self):
        cases = {
            0x09B1D6: "callback writer pointer load changed",
            0x09B1D8: "callback writer store changed",
            0x099DC0: "callback consumer load changed",
            0x099DC8: "callback consumer thunk call changed",
            0x09A1AE: "SoundMain indirect thunk changed",
            0x09A43C: "recursive callback load changed",
            0x09A444: "recursive callback veneer call changed",
            0x09A684: "owned recursive veneer changed",
        }
        for offset, message in cases.items():
            with self.subTest(offset=f"0x{offset:06X}"), self.assertRaisesRegex(ValueError, message):
                raw = bytearray(self.rom[offset : offset + (4 if offset in {0x099DC8, 0x09A444} else 2)])
                raw[0] ^= 1
                self._build_mutated({offset: bytes(raw)})

    def test_tail_branch_literal_and_unknown_gap_are_frozen(self):
        for offset, message in (
            (0x09A5CA, "candidate code range changed"),
            (0x09A688, "candidate literal range changed"),
            (0x09A686, "unclassified current-unknown range changed"),
        ):
            with self.subTest(offset=f"0x{offset:06X}"), self.assertRaisesRegex(ValueError, message):
                raw = bytearray(self.rom[offset : offset + 2])
                raw[0] ^= 1
                self._build_mutated({offset: bytes(raw)})

    def test_baseline_projection_uses_current_authority_without_reowning_veneer(self):
        payload, _ = self.exporter.build_payload_from_rom(ROOT, self.rom)
        baseline = payload["coverage_baseline"]
        self.assertEqual(baseline["sha256"],
                         "17aa05ec2919606ac4728106daf08b3d06a033ccd3c723dc17fd7ad1bdec9ad0")
        self.assertEqual(baseline["summary"], {
            "classified_bytes": 6_121_877,
            "unknown_bytes": 169_579,
            "claim_count": 14_482,
            "segment_count": 16_591,
        })
        self.assertEqual(baseline["target_segments"], [
            {"range": [0x09A3DC, 0x09A684], "primary_class": "unknown"},
            {"range": [0x09A684, 0x09A686], "claim_id": "cfg-thumb-0752-09a684"},
            {"range": [0x09A686, 0x09A694], "primary_class": "unknown"},
        ])
        self.assertEqual(payload["promotion"]["projected_totals"], {
            "classified_bytes": 6_122_489,
            "unknown_bytes": 168_967,
            "claim_count": 14_484,
            "segment_count": 16_593,
        })
        self.assertNotIn([0x09A684, 0x09A686], [item["range"] for item in payload["promotion_ranges"]])

    def test_independent_verifier_rebuilds_raw_rom_without_importing_exporter(self):
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import tools.export_rom_mplaymain_scheduler", source)
        self.assertNotIn("from tools.export_rom_mplaymain_scheduler", source)
        verifier = _load_verifier()

        rebuilt = verifier.independent_rebuild(ROOT, self.rom)
        payload, bundle = self.exporter.build_payload_from_rom(ROOT, self.rom)
        self.assertEqual(rebuilt["summary"], payload["summary"])
        self.assertEqual(rebuilt["external_edges"], [
            [item["source_instruction_offset"], item["kind"], item["target_offset"]]
            for item in payload["external_edges"]
        ])
        self.assertEqual(rebuilt["literal_bindings"], [
            [item["instruction_offset"], item["literal_offset"], item["value"]]
            for item in payload["literal_bindings"]
        ])
        self.assertEqual(rebuilt["bundle_sha256"], hashlib.sha256(bundle).hexdigest())
        self.assertTrue(rebuilt["entry_contract_ok"])

    def test_candidate_verification_and_acceptance_are_fail_closed(self):
        verifier = _load_verifier()
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mplaymain-artifact-test-", dir=active) as raw:
            workspace = Path(raw)
            candidate = workspace / "candidate"
            accepted = workspace / "accepted"
            self.exporter.write_candidate(ROOT, candidate)

            with self.assertRaisesRegex(ValueError, "candidate artifact requires explicit opt-in"):
                verifier.verify_artifact(ROOT, candidate)
            report = verifier.verify_artifact(ROOT, candidate, allow_candidate=True)
            self.assertTrue(report["verified"])
            self.assertTrue(report["contract_ok"])
            self.assertEqual(report["summary"], self.exporter.EXPECTED_SUMMARY)

            receipt = verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertEqual(receipt["artifact_status"], "accepted")
            accepted_report = verifier.verify_artifact(ROOT, accepted)
            self.assertTrue(accepted_report["verified"])
            self.assertTrue(accepted_report["contract_ok"])

    def test_verifier_rejects_payload_and_binary_mutation_even_with_fresh_file_receipt(self):
        verifier = _load_verifier()
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mplaymain-mutation-test-", dir=active) as raw:
            workspace = Path(raw)
            candidate = workspace / "candidate"
            self.exporter.write_candidate(ROOT, candidate)

            payload_path = candidate / self.exporter.PAYLOAD_NAME
            manifest_path = candidate / self.exporter.MANIFEST_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["summary"]["instruction_count"] += 1
            changed = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
            payload_path.write_bytes(changed)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][self.exporter.PAYLOAD_NAME] = {
                "size": len(changed),
                "sha256": hashlib.sha256(changed).hexdigest(),
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "payload summary changed"):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)

            shutil.rmtree(candidate)
            self.exporter.write_candidate(ROOT, candidate)
            bundle_path = candidate / self.exporter.BUNDLE_NAME
            bundle = bytearray(bundle_path.read_bytes())
            bundle[-1] ^= 1
            bundle_path.write_bytes(bundle)
            manifest = json.loads((candidate / self.exporter.MANIFEST_NAME).read_text(encoding="utf-8"))
            manifest["files"][self.exporter.BUNDLE_NAME] = {
                "size": len(bundle),
                "sha256": hashlib.sha256(bundle).hexdigest(),
            }
            (candidate / self.exporter.MANIFEST_NAME).write_text(
                json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "packed binary differs from raw-ROM reconstruction"):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)

    def test_output_and_artifact_file_sets_reject_symlinks_nonempty_and_foreign_files(self):
        verifier = _load_verifier()
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mplaymain-safety-test-", dir=active) as raw:
            workspace = Path(raw)
            nonempty = workspace / "nonempty"
            nonempty.mkdir()
            (nonempty / "keep.txt").write_text("user data", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output directory must be empty"):
                self.exporter.write_candidate(ROOT, nonempty)
            self.assertEqual((nonempty / "keep.txt").read_text(encoding="utf-8"), "user data")

            outside = workspace / "outside"
            outside.mkdir()
            link = workspace / "link"
            os.symlink(outside, link)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.exporter.write_candidate(ROOT, link / "candidate")

            candidate = workspace / "candidate"
            self.exporter.write_candidate(ROOT, candidate)
            (candidate / "foreign.txt").write_text("not part of packet", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact file set changed"):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)


if __name__ == "__main__":
    unittest.main()
