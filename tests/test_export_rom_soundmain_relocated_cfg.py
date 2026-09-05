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
EXPORTER_PATH = ROOT / "tools/export_rom_soundmain_relocated_cfg.py"
VERIFIER_PATH = ROOT / "tools/verify_rom_soundmain_relocated_cfg.py"


def _load_exporter():
    spec = importlib.util.spec_from_file_location(
        "export_rom_soundmain_relocated_cfg", EXPORTER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load SoundMain relocated CFG exporter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_rom_soundmain_relocated_cfg_for_artifact_test", VERIFIER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load SoundMain relocated CFG verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SoundMainRelocatedCopyPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = _load_exporter()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def _build_mutated(self, offset: int, size: int = 2):
        changed = bytearray(self.rom)
        changed[offset] ^= 1
        changed = bytes(changed)
        with mock.patch.object(
            self.exporter,
            "ROM_SHA256",
            hashlib.sha256(changed).hexdigest(),
        ):
            return self.exporter.build_preflight_from_rom(ROOT, changed)

    def test_live_rom_freezes_cpuset_copy_and_reuses_full_direct_call_denominator(self):
        report = self.exporter.build_preflight_from_rom(ROOT, self.rom)

        self.assertEqual(report["schema"], "rom-soundmain-relocated-cfg-preflight-v1")
        self.assertEqual(report["rom"], {
            "path": "rom/base.gba",
            "size": 0x600000,
            "sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
        })

        operation = report["copy_operation"]
        self.assertEqual(operation["initializer_code_range"], [0x09AA3C, 0x09AA90])
        self.assertEqual(operation["initializer_literal_range"], [0x09AA90, 0x09AAB4])
        self.assertEqual(operation["source_pointer"], "0x08099E11")
        self.assertEqual(operation["source_range"], [0x099E10, 0x09A210])
        self.assertEqual(operation["destination_range"], [0x030077C8, 0x03007BC8])
        self.assertEqual(operation["control"], "0x04000100")
        self.assertEqual(operation["unit_bytes"], 4)
        self.assertEqual(operation["unit_count"], 0x100)
        self.assertEqual(operation["copy_bytes"], 0x400)
        self.assertFalse(operation["fixed_source"])
        self.assertEqual(operation["callsite_offset"], 0x09AA4A)
        self.assertEqual(operation["bios_wrapper_range"], [0x09C0E0, 0x09C0E4])
        self.assertEqual(operation["bios_swi"], "0x0B")
        self.assertEqual(
            operation["copy_window_sha256"],
            "7b4fef2cb8e0e87ce8e8aaf244970f121851095a6d6260a423eda20791d5b238",
        )

        source = report["source"]
        self.assertEqual(source["rom_envelope"], [0x099E10, 0x09A1AE])
        self.assertEqual(source["runtime_envelope"], [0x030077C8, 0x03007B66])
        self.assertEqual(source["gba_to_runtime_delta"], -0x05092648)
        self.assertEqual(source["envelope_bytes"], 926)
        self.assertEqual(
            source["envelope_sha256"],
            "1099dd6414c3f8a052a9e0e19c7ef9497661c4c15b4e8d1dd056f791bb115df8",
        )
        self.assertEqual(source["copied_but_outside_envelope_range"], [0x09A1AE, 0x09A210])
        self.assertEqual(source["copied_but_outside_envelope_bytes"], 98)

        denominator = report["producer_denominator"]
        self.assertEqual(denominator["cpuset_target"], "0x0809C0E0")
        self.assertEqual(denominator["cpuset_call_count"], 126)
        self.assertEqual(denominator["cpufastset_target"], "0x0809C0DC")
        self.assertEqual(denominator["cpufastset_call_count"], 20)
        self.assertEqual(denominator["direct_call_count"], 146)
        self.assertEqual(denominator["soundmain_copy_callsites"], [0x09AA4A])
        self.assertEqual(denominator["initializer_direct_bl_producers"], [0x061E28])
        self.assertTrue(denominator["matches_direct_cpuset_artifact"])
        self.assertTrue(denominator["target_limited_direct_bl_denominator_complete"])
        self.assertFalse(denominator["computed_or_indirect_producer_denominator_complete"])
        self.assertEqual(denominator["initializer_forms"], {
            "thumb_bl": [0x061E28],
            "thumb_b": [],
            "thumb_b_conditional": [],
            "arm_b": [],
            "arm_bl": [],
            "bytewise_u32_entry": [],
            "bytewise_u32_thumb_pointer": [],
        })
        self.assertEqual(denominator["cpuset_forms"]["thumb_bl"],
                         denominator["cpuset_callsites"])
        for kind in (
            "thumb_b", "thumb_b_conditional", "arm_b", "arm_bl",
            "bytewise_u32_entry", "bytewise_u32_thumb_pointer",
        ):
            self.assertEqual(denominator["cpuset_forms"][kind], [], kind)

    def test_copy_consumer_and_denominators_fail_closed_on_raw_mutation(self):
        cases = (
            (0x09AA90, "SoundMain source literal changed"),
            (0x09AA94, "SoundMain destination literal changed"),
            (0x09AA98, "SoundMain control literal changed"),
            (0x09AA4A, "CpuSet callsite changed"),
            (0x09C0E0, "CpuSet wrapper changed"),
            (0x061E28, "m4aSoundInit direct-BL producer denominator changed"),
            (0x061190, "direct CpuSet denominator changed"),
        )
        for offset, message in cases:
            with self.subTest(offset=f"0x{offset:06X}"), self.assertRaisesRegex(
                ValueError, message
            ):
                self._build_mutated(offset)


class SoundMainRelocatedCfgPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = _load_exporter()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def _analyze_mutated(self, offset: int):
        changed = bytearray(self.rom)
        changed[offset] ^= 1
        return self.exporter.analyze_relocated_cfg(bytes(changed))

    def test_runtime_mapped_mixed_isa_worklist_freezes_all_denominators(self):
        cfg = self.exporter.analyze_relocated_cfg(self.rom)

        self.assertEqual(cfg["root"], {
            "source_offset": 0x099E10,
            "gba_address": "0x08099E10",
            "runtime_address": "0x030077C8",
            "mode": "thumb",
        })
        self.assertEqual(cfg["runtime_mapping"], {
            "source_range": [0x099E10, 0x09A1AE],
            "runtime_range": [0x030077C8, 0x03007B66],
            "formula": "runtime=0x030077C8+(source_offset-0x099E10)",
        })
        self.assertEqual(cfg["code_ranges"], [
            [0x099E10, 0x099E1A],
            [0x099E1C, 0x099EC2],
            [0x099EC8, 0x099FA6],
            [0x099FA8, 0x09A1AE],
        ])
        self.assertEqual(cfg["literal_ranges"], [
            [0x099EC4, 0x099EC8],
            [0x09A1B0, 0x09A1B4],
        ])
        self.assertEqual(cfg["alignment_gap_ranges"], [
            [0x099E1A, 0x099E1C],
            [0x099EC2, 0x099EC4],
            [0x099FA6, 0x099FA8],
        ])
        self.assertEqual(cfg["owned_provenance_ranges"], [[0x09A1AE, 0x09A1B0]])

        self.assertEqual(
            [
                (
                    item["producer_offset"], item["producer_mode"],
                    item["target_offset"], item["target_mode"],
                )
                for item in cfg["mode_switches"]
            ],
            [
                (0x099E18, "thumb", 0x099E1C, "arm"),
                (0x099E6C, "arm", 0x099E9E, "thumb"),
                (0x099FA4, "thumb", 0x099FA8, "arm"),
                (0x09A18C, "arm", 0x09A190, "thumb"),
            ],
        )
        self.assertEqual(
            [
                (
                    item["instruction_offset"], item["instruction_mode"],
                    item["literal_offset"], item["value"],
                )
                for item in cfg["literal_bindings"]
            ],
            [
                (0x099EB2, "thumb", 0x099EC4, "0x04000006"),
                (0x09A19C, "thumb", 0x09A1B0, "0x68736D53"),
            ],
        )
        self.assertEqual(cfg["external_edges"], [{
            "source_instruction_offset": 0x09A1AC,
            "source_mode": "thumb",
            "kind": "fallthrough",
            "target_offset": 0x09A1AE,
            "target_mode": "thumb",
            "resolution": "opaque_existing_soundmain_return_veneer",
            "owner_claim_id": "boot-thumb-handoff-code-22-09a1ae",
        }])
        self.assertEqual(cfg["summary"], {
            "instruction_count": 315,
            "instruction_bytes": 916,
            "thumb_instruction_count": 172,
            "thumb_instruction_bytes": 344,
            "arm_instruction_count": 143,
            "arm_instruction_bytes": 572,
            "code_bytes": 916,
            "block_count": 73,
            "internal_block_edge_count": 112,
            "external_block_edge_count": 1,
            "mode_switch_count": 4,
            "literal_ref_count": 2,
            "literal_word_count": 2,
            "literal_bytes": 8,
            "alignment_gap_count": 3,
            "alignment_gap_bytes": 6,
            "owned_return_veneer_count": 1,
            "owned_provenance_bytes": 2,
            "internal_return_count": 0,
            "opaque_return_count": 1,
            "unresolved_frontier_count": 0,
        })
        self.assertEqual(
            cfg["identities"],
            {
                "code_packed_sha256": "e9a33c0d5d90a69fd9c6906523dc48043eb59c31ddf7d47403409dbde18604d2",
                "code_range_vector_sha256": "17a5eb6c86a18b7aae3c5537a184d4ee355f244eae5a96b7c5d60ee6f1f5a95f",
                "literal_packed_sha256": "73532471c9748faea0e2abc00e4c17dde622220884d2521f4e58cf3fab9be7e0",
                "literal_range_vector_sha256": "ce75959fb7681a95b5a4bbf9371bdaf97d18afa44168107fc33d957c18d6bb71",
                "gap_packed_sha256": "b0f66adc83641586656866813fd9dd0b8ebb63796075661ba45d1aa8089e1d44",
                "gap_range_vector_sha256": "80e7409ef3fd737361faa6a08ae8e2efbedd9891c31e4f4b98392a3ad91da3af",
                "instruction_vector_sha256": "7f18b67eb2b9d93eb09d01c73e31cd89ca639464c888aa5e7b01ecc5d404fc88",
                "instruction_edge_vector_sha256": "0a14df5c71dac205501ed6daa636cb4d414e5c55acd8c3eb319ab5e9cdf6b6fc",
            },
        )

    def test_semantic_packet_promotes_924_bytes_and_defers_three_gaps(self):
        report = self.exporter.build_preflight_from_rom(ROOT, self.rom)
        promotion = report["promotion"]

        self.assertEqual(promotion["code_ranges"], report["cfg"]["code_ranges"])
        self.assertEqual(promotion["literal_ranges"], report["cfg"]["literal_ranges"])
        self.assertEqual(promotion["semantic_union_ranges"], [
            [0x099E10, 0x099E1A],
            [0x099E1C, 0x099EC2],
            [0x099EC4, 0x099FA6],
            [0x099FA8, 0x09A1AE],
            [0x09A1B0, 0x09A1B4],
        ])
        self.assertEqual(promotion["semantic_bytes"], 924)
        self.assertEqual(promotion["semantic_claim_count"], 6)
        self.assertEqual(
            promotion["semantic_packed_sha256"],
            "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331",
        )
        self.assertEqual(
            promotion["semantic_union_range_vector_sha256"],
            "edd9da8aad815cf4aea5ca9c02360c3903d523588f0a7a6d7a1fa214e57d8a94",
        )
        self.assertEqual(promotion["deferred_alignment_gap_ranges"],
                         report["cfg"]["alignment_gap_ranges"])
        self.assertEqual(promotion["deferred_alignment_gap_bytes"], 6)
        self.assertTrue(promotion["alignment_gap_requires_accepted_immutable_artifact"])
        self.assertEqual(promotion["projected_totals"], {
            "classified_bytes": 6_123_413,
            "unknown_bytes": 168_043,
            "claim_count": 14_490,
            "segment_count": 16_600,
        })
        self.assertEqual(promotion["post_gap_projected_totals"], {
            "classified_bytes": 6_123_419,
            "unknown_bytes": 168_037,
            "claim_count": 14_493,
            "segment_count": 16_600,
        })

        baseline = report["coverage_baseline"]
        self.assertEqual(
            baseline["sha256"],
            "2b93df18a7815cb966dad707dfa2ad606049911ae1772a341b57cf2347b58e3b",
        )
        self.assertEqual(baseline["summary"], {
            "classified_bytes": 6_122_489,
            "unknown_bytes": 168_967,
            "claim_count": 14_484,
            "segment_count": 16_593,
        })
        self.assertEqual(baseline["target_segments"], [
            {"range": [0x099E10, 0x09A1AE], "primary_class": "unknown"},
            {
                "range": [0x09A1AE, 0x09A1B0],
                "claim_id": "boot-thumb-handoff-code-22-09a1ae",
            },
            {"range": [0x09A1B0, 0x09A1B4], "primary_class": "unknown"},
        ])

    def test_modes_literals_gaps_and_preowned_return_fail_closed(self):
        cases = (
            (0x099E16, "mode-switch producer changed"),
            (0x099E18, "mode-switch producer changed"),
            (0x099E68, "mode-switch producer changed"),
            (0x099E6C, "mode-switch producer changed"),
            (0x099FA2, "mode-switch producer changed"),
            (0x099FA4, "mode-switch producer changed"),
            (0x09A188, "mode-switch producer changed"),
            (0x09A18C, "mode-switch producer changed"),
            (0x099EC4, "literal binding changed"),
            (0x09A1B0, "literal binding changed"),
            (0x099E1A, "alignment gap changed"),
            (0x099EC2, "alignment gap changed"),
            (0x099FA6, "alignment gap changed"),
            (0x09A1AE, "preowned SoundMain return veneer changed"),
        )
        for offset, message in cases:
            with self.subTest(offset=f"0x{offset:06X}"), self.assertRaisesRegex(
                ValueError, message
            ):
                self._analyze_mutated(offset)


class SoundMainRelocatedCfgArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = _load_exporter()

    def test_final_payload_packs_only_six_semantic_ranges(self):
        payload, bundle = self.exporter.build_payload(ROOT)

        self.assertEqual(payload["schema"], "rom-soundmain-relocated-cfg-v1")
        self.assertEqual(len(bundle), 924)
        self.assertEqual(
            hashlib.sha256(bundle).hexdigest(),
            "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331",
        )
        self.assertEqual(
            [row["range"] for row in payload["promotion_ranges"]],
            [
                [0x099E10, 0x099E1A],
                [0x099E1C, 0x099EC2],
                [0x099EC4, 0x099EC8],
                [0x099EC8, 0x099FA6],
                [0x099FA8, 0x09A1AE],
                [0x09A1B0, 0x09A1B4],
            ],
        )
        self.assertEqual(len(payload["coverage_claims"]), 6)
        self.assertEqual(payload["packed_layout"], payload["packed_binary"]["layout"])
        self.assertEqual(payload["packed_binary"], {
            "file": "rom-soundmain-relocated-cfg.bin",
            "size": 924,
            "sha256": hashlib.sha256(bundle).hexdigest(),
            "layout": payload["packed_layout"],
        })
        promoted = {tuple(row["range"]) for row in payload["promotion_ranges"]}
        self.assertTrue(
            promoted.isdisjoint({
                (0x099E1A, 0x099E1C),
                (0x099EC2, 0x099EC4),
                (0x099FA6, 0x099FA8),
            })
        )
        self.assertEqual(payload["summary"]["promoted_bytes"], 924)
        self.assertEqual(payload["summary"]["deferred_alignment_gap_bytes"], 6)

    def test_candidate_verification_and_acceptance_are_fail_closed(self):
        verifier = _load_verifier()
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="soundmain-relocated-artifact-test-", dir=active
        ) as raw:
            workspace = Path(raw)
            candidate = workspace / "candidate"
            accepted = workspace / "accepted"
            self.exporter.write_candidate(ROOT, candidate)
            candidate_relative = candidate.relative_to(ROOT).as_posix()
            candidate_manifest = json.loads(
                (candidate / self.exporter.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(candidate_manifest["producer"], {
                "kind": "artifact-candidate-construction",
                "output_artifact": candidate_relative,
                "command": [
                    "python3",
                    "tools/export_rom_soundmain_relocated_cfg.py",
                    "--output",
                    candidate_relative,
                ],
            })

            with self.assertRaisesRegex(
                ValueError, "candidate artifact requires explicit opt-in"
            ):
                verifier.verify_artifact(ROOT, candidate)
            report = verifier.verify_artifact(ROOT, candidate, allow_candidate=True)
            self.assertTrue(report["verified"])
            self.assertTrue(report["contract_ok"])
            self.assertEqual(report["artifact_status"], "candidate")
            self.assertEqual(report["summary"]["promoted_bytes"], 924)

            receipt = verifier.accept_candidate(ROOT, candidate, accepted)
            self.assertEqual(receipt["artifact_status"], "accepted")
            accepted_report = verifier.verify_artifact(ROOT, accepted)
            self.assertTrue(accepted_report["verified"])
            self.assertTrue(accepted_report["contract_ok"])
            accepted_relative = accepted.relative_to(ROOT).as_posix()
            accepted_manifest = json.loads(
                (accepted / self.exporter.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            acceptance_command = [
                "python3",
                "tools/verify_rom_soundmain_relocated_cfg.py",
                "--artifact",
                candidate_relative,
                "--accept-to",
                accepted_relative,
            ]
            self.assertEqual(accepted_manifest["acceptance"], {
                "kind": "independent-candidate-acceptance",
                "candidate_artifact": candidate_relative,
                "output_artifact": accepted_relative,
                "command": acceptance_command,
                "candidate_identity": {
                    "artifact_status": "candidate",
                    "manifest_sha256": hashlib.sha256(
                        (candidate / self.exporter.MANIFEST_NAME).read_bytes()
                    ).hexdigest(),
                    "payload_sha256": hashlib.sha256(
                        (candidate / self.exporter.PAYLOAD_NAME).read_bytes()
                    ).hexdigest(),
                    "bundle_sha256": hashlib.sha256(
                        (candidate / self.exporter.BUNDLE_NAME).read_bytes()
                    ).hexdigest(),
                },
            })
            self.assertEqual(
                accepted_manifest["verifier"]["command"], acceptance_command
            )

            moved = workspace / "moved"
            shutil.copytree(accepted, moved)
            with self.assertRaisesRegex(ValueError, "output artifact path changed"):
                verifier.verify_artifact(ROOT, moved)

            forged = workspace / "forged"
            shutil.copytree(accepted, forged)
            forged_manifest_path = forged / self.exporter.MANIFEST_NAME
            forged_manifest = json.loads(
                forged_manifest_path.read_text(encoding="utf-8")
            )
            forged_candidate = "build/forged-candidate"
            forged_output = forged.relative_to(ROOT).as_posix()
            forged_command = [
                "python3",
                "tools/verify_rom_soundmain_relocated_cfg.py",
                "--artifact",
                forged_candidate,
                "--accept-to",
                forged_output,
            ]
            forged_manifest["acceptance"]["candidate_artifact"] = forged_candidate
            forged_manifest["acceptance"]["output_artifact"] = forged_output
            forged_manifest["acceptance"]["command"] = forged_command
            forged_manifest["producer"]["output_artifact"] = forged_candidate
            forged_manifest["producer"]["command"][-1] = forged_candidate
            forged_manifest["verifier"]["command"] = forged_command
            forged_manifest_path.write_text(
                json.dumps(
                    forged_manifest, indent=2, sort_keys=True, ensure_ascii=False
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "candidate artifact identity changed"):
                verifier.verify_artifact(ROOT, forged)

    def test_payload_and_binary_mutation_fail_even_with_fresh_file_receipts(self):
        verifier = _load_verifier()
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="soundmain-relocated-mutation-test-", dir=active
        ) as raw:
            workspace = Path(raw)
            candidate = workspace / "candidate"
            self.exporter.write_candidate(ROOT, candidate)

            payload_path = candidate / self.exporter.PAYLOAD_NAME
            manifest_path = candidate / self.exporter.MANIFEST_NAME
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["summary"]["instruction_count"] += 1
            changed = (
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            ).encode("utf-8")
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
            with self.assertRaisesRegex(ValueError, "payload|summary"):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)

            shutil.rmtree(candidate)
            self.exporter.write_candidate(ROOT, candidate)
            bundle_path = candidate / self.exporter.BUNDLE_NAME
            bundle = bytearray(bundle_path.read_bytes())
            bundle[-1] ^= 1
            bundle_path.write_bytes(bundle)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][self.exporter.BUNDLE_NAME] = {
                "size": len(bundle),
                "sha256": hashlib.sha256(bundle).hexdigest(),
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError, "packed binary differs from raw-ROM reconstruction"
            ):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)

    def test_output_and_artifact_file_sets_reject_symlinks_and_foreign_files(self):
        verifier = _load_verifier()
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="soundmain-relocated-safety-test-", dir=active
        ) as raw:
            workspace = Path(raw)
            nonempty = workspace / "nonempty"
            nonempty.mkdir()
            (nonempty / "keep.txt").write_text("user data", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output directory must be empty"):
                self.exporter.write_candidate(ROOT, nonempty)
            self.assertEqual(
                (nonempty / "keep.txt").read_text(encoding="utf-8"), "user data"
            )

            outside = workspace / "outside"
            outside.mkdir()
            link = workspace / "link"
            os.symlink(outside, link)
            with self.assertRaisesRegex(ValueError, "symlink"):
                self.exporter.write_candidate(ROOT, link / "candidate")

            candidate = workspace / "candidate"
            self.exporter.write_candidate(ROOT, candidate)

            manifest_path = candidate / self.exporter.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["approval"] = {"status": "forged"}
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "manifest schema changed"):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)
            manifest.pop("approval")
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            (candidate / "foreign.txt").write_text(
                "not part of packet", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "artifact file set changed"):
                verifier.verify_artifact(ROOT, candidate, allow_candidate=True)


if __name__ == "__main__":
    unittest.main()
