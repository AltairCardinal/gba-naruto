from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-boot-thumb-handoff-cfg-v1"
RUN_ROOT = ROOT / "build/experiments/active/boot-thumb-handoff-cfg-v1/sol-r2-20260827"
RUN_FINAL = RUN_ROOT / "final"
EXCLUDED = (0x60FA4, 0x60FAC)
ENVELOPE = (0x60FAC, 0x9C098)


class ExportRomBootThumbHandoffCfgTests(unittest.TestCase):
    _final_generated = False

    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def _payload_bundle(self):
        from tools.export_rom_boot_thumb_handoff_cfg import build_payload

        return build_payload(ROOT)

    def _export(self, directory: str | Path) -> Path:
        from tools.export_rom_boot_thumb_handoff_cfg import export_artifact

        # Generate the authoritative run final once. Mutation cases only copy
        # it into isolated Sol-run directories and never rewrite it.
        if not type(self)._final_generated:
            export_artifact(ROOT, RUN_FINAL)
            type(self)._final_generated = True
        target = Path(directory)
        if target == RUN_FINAL:
            return target
        target.mkdir(parents=True, exist_ok=True)
        if any(target.iterdir()):
            raise AssertionError(f"test artifact destination is not empty: {target}")
        shutil.copytree(RUN_FINAL, target, dirs_exist_ok=True)
        return target

    @staticmethod
    def _intersects(first: list[int] | tuple[int, int], second: list[int] | tuple[int, int]) -> bool:
        return first[0] < second[1] and second[0] < first[1]

    @staticmethod
    def _unknown_mask() -> bytearray:
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8"))
        unknown = bytearray(len((ROOT / "rom/base.gba").read_bytes()))
        for segment in coverage["segments"]:
            if segment["primary_class"] == "unknown":
                start, end = segment["range"]
                unknown[start:end] = b"\1" * (end - start)
        return unknown

    def _assert_recomputed_summary(self, payload: dict) -> None:
        instructions = payload["instructions"]
        edges = payload["edges"]
        literals = payload["literal_bindings"]
        recomputed = {
            "instruction_count": len(instructions),
            "instruction_bytes": sum(item["size"] for item in instructions),
            "block_count": len(payload["blocks"]),
            "internal_edge_count": sum(item["resolution"] == "internal" for item in edges),
            "external_edge_count": sum(item["resolution"] == "opaque_external_entry" for item in edges),
            "external_target_count": len({item["target_offset"] for item in edges if item["resolution"] == "opaque_external_entry"}),
            "literal_ref_count": len(literals),
            "literal_word_count": len({item["literal_offset"] for item in literals}),
            "literal_bytes": len({item["literal_offset"] for item in literals}) * 4,
            "return_count": sum(item["flow_kind"] == "return" for item in instructions),
            "raw_indirect_pc_count": len(payload["raw_indirect_pc_sites"]),
            "frontier_count": len(payload["frontiers"]),
            "budget_exhausted": False,
        }
        self.assertEqual(recomputed, payload["summary"])
        self.assertEqual(recomputed["instruction_count"], 583)
        self.assertEqual(recomputed["instruction_bytes"], 1226)
        self.assertEqual(recomputed["block_count"], 125)
        self.assertEqual(recomputed["internal_edge_count"], 164)
        self.assertEqual(recomputed["external_edge_count"], 14)
        self.assertEqual(recomputed["external_target_count"], 11)
        self.assertEqual(recomputed["literal_ref_count"], 77)
        self.assertEqual(recomputed["literal_word_count"], 74)
        self.assertEqual(recomputed["literal_bytes"], 296)
        self.assertEqual(recomputed["return_count"], 14)
        self.assertEqual(recomputed["raw_indirect_pc_count"], 15)
        self.assertEqual(recomputed["frontier_count"], 2)

    def _assert_exact_promotion(self, payload: dict, bundle: bytes) -> None:
        expected_union = [
            [0x060FAC, 0x061022], [0x061024, 0x061086],
            [0x0610E8, 0x0610FE], [0x061100, 0x06111E], [0x061120, 0x06114A], [0x06114C, 0x061150],
            [0x0615E4, 0x061624], [0x061824, 0x06185E], [0x061860, 0x06188A],
            [0x061F74, 0x061F8A], [0x061F8C, 0x061FA2], [0x0620B4, 0x0620C6], [0x0620C8, 0x0620CC],
            [0x06211C, 0x062276], [0x062278, 0x06231E], [0x062320, 0x062330], [0x0646D0, 0x064700],
            [0x065398, 0x065404], [0x099D8C, 0x099DF6], [0x099DF8, 0x099E10],
            [0x09A1AE, 0x09A1B0], [0x09AAB4, 0x09AABE], [0x09BFFC, 0x09C046],
            [0x09C048, 0x09C086], [0x09C088, 0x09C098],
        ]
        self.assertEqual(expected_union, payload["union_ranges"])
        for ranges in (payload["code_ranges"], payload["literal_ranges"], payload["union_ranges"]):
            self.assertEqual(ranges, sorted(ranges))
            self.assertTrue(all(start < end for start, end in ranges))
            self.assertTrue(all(not self._intersects(ranges[index], ranges[index + 1]) for index in range(len(ranges) - 1)))
        self.assertEqual(27, len(payload["code_ranges"]))
        self.assertEqual(22, len(payload["literal_ranges"]))
        self.assertEqual(25, len(payload["union_ranges"]))
        self.assertEqual(1226, sum(end - start for start, end in payload["code_ranges"]))
        self.assertEqual(296, sum(end - start for start, end in payload["literal_ranges"]))
        self.assertEqual(1522, sum(end - start for start, end in payload["union_ranges"]))
        self.assertEqual("f8df15ea8c3feb1a9c460bd0a2aabd79572806100ed726ada64b360aabb92aa5", hashlib.sha256(json.dumps(expected_union, separators=(",", ":")).encode("utf-8")).hexdigest())
        expected_bundle = b"".join(self.rom[start:end] for start, end in expected_union)
        self.assertEqual(expected_bundle, bundle)
        self.assertEqual("73033e06942ec6604fe036849e40c420728f6f9bd4ae5db6c0fe49ba6eca2f22", hashlib.sha256(expected_bundle).hexdigest())
        unknown = self._unknown_mask()
        self.assertTrue(all(all(unknown[start:end]) for start, end in expected_union))
        self.assertEqual(0, payload["promotion"]["current_known_overlap_bytes"])
        self.assertEqual([0x60FAC, 0x9C098], payload["promotion"]["wide_envelope"])
        self.assertFalse(payload["promotion"]["wide_envelope_is_claim"])
        self.assertFalse(any(self._intersects(item["range"], EXCLUDED) for item in payload["promotion_ranges"]))
        self.assertFalse(any(self._intersects(item["range"], EXCLUDED) for item in payload["coverage_claims"]))
        self.assertFalse(any(item["range"] == list(ENVELOPE) for item in payload["coverage_claims"] + payload["promotion_ranges"]))

    @staticmethod
    def _resign_manifest(artifact: Path, filename: str) -> None:
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw = (artifact / filename).read_bytes()
        record = manifest["files"][filename]
        if isinstance(record, dict):
            record["size"] = len(raw)
            record["sha256"] = hashlib.sha256(raw).hexdigest()
        else:
            manifest["files"][filename] = hashlib.sha256(raw).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_exporter_rebuilds_the_frozen_thumb_handoff_contract(self) -> None:
        payload, bundle = self._payload_bundle()
        self.assertEqual(SCHEMA, payload["schema"])
        self.assertEqual(1_522, len(bundle))
        self._assert_recomputed_summary(payload)
        self.assertEqual(
            {
                "instruction_count": 583,
                "instruction_bytes": 1226,
                "block_count": 125,
                "internal_edge_count": 164,
                "external_edge_count": 14,
                "external_target_count": 11,
                "literal_ref_count": 77,
                "literal_word_count": 74,
                "literal_bytes": 296,
                "return_count": 14,
                "raw_indirect_pc_count": 15,
                "frontier_count": 2,
                "budget_exhausted": False,
            },
            payload["summary"],
        )

    def test_final_artifact_is_independently_verified(self) -> None:
        from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact

        with tempfile.TemporaryDirectory(dir=RUN_FINAL.parent) as directory:
            output = self._export(directory)
            report = verify_artifact(ROOT, output)
            self.assertTrue(report["verified"], report["errors"])

    def test_handoff_and_root_mutations_fail_closed(self) -> None:
        from tools.export_rom_boot_thumb_handoff_cfg import build_payload_from_rom

        for offset, message in (
            (0xE4, "handoff"),
            (0xE8, "handoff"),
            (0xEC, "handoff"),
            (0xF8, "handoff"),
            (0x60FAC, "root"),
        ):
            mutated = bytearray(self.rom)
            mutated[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaisesRegex(ValueError, message):
                build_payload_from_rom(ROOT, bytes(mutated))

    def test_boot_manifest_drift_and_frozen_baseline_drift_fail_closed(self) -> None:
        from tools import export_rom_boot_thumb_handoff_cfg as exporter
        from tools.export_rom_boot_thumb_handoff_cfg import build_payload

        for constant, source_name, message in (
            ("BOOT_MANIFEST_PATH", "boot-manifest.json", "boot manifest"),
            ("COVERAGE_PATH", "coverage.json", "coverage"),
        ):
            with tempfile.TemporaryDirectory(dir=RUN_FINAL.parent) as directory:
                replacement = Path(directory) / source_name
                original = ROOT / getattr(exporter, constant)
                raw = bytearray(original.read_bytes())
                raw[0] ^= 1
                replacement.write_bytes(raw)
                with mock.patch.object(exporter, constant, replacement.relative_to(ROOT)):
                    with self.subTest(source=constant), self.assertRaisesRegex(ValueError, message):
                        build_payload(ROOT)

    def test_excluded_prefix_never_enters_nodes_blocks_literals_or_promotion(self) -> None:
        payload, _ = self._payload_bundle()
        for key in ("instructions", "blocks", "literal_bindings", "promotion_ranges"):
            for item in payload[key]:
                if "range" in item:
                    span = item["range"]
                elif key == "literal_bindings":
                    span = [item["literal_offset"], item["literal_offset"] + 4]
                else:
                    span = [item["file_offset"], item["file_offset"] + item["size"]]
                self.assertFalse(self._intersects(span, EXCLUDED), (key, item))
        for key in ("union_ranges", "code_ranges", "literal_ranges"):
            self.assertFalse(any(self._intersects(span, EXCLUDED) for span in payload[key]), key)

    def test_graph_literals_frontiers_and_exact_return_idiom(self) -> None:
        payload, _ = self._payload_bundle()
        self.assertEqual(77, len(payload["literal_bindings"]))
        self.assertEqual(74, len({item["literal_offset"] for item in payload["literal_bindings"]}))
        iwram = [item for item in payload["literal_bindings"] if item["literal_offset"] == 0x99E00]
        self.assertEqual(1, len(iwram))
        self.assertEqual("0x030077C9", iwram[0]["raw_value"])
        self.assertEqual("0x030077C8", iwram[0]["normalized_value"])
        frontier_offsets = {item["instruction_offset"] for item in payload["frontiers"]}
        self.assertEqual({0x99DF4, 0x9A1AE}, frontier_offsets)
        self.assertEqual(
            {0x6107A, 0x61148, 0x61612, 0x61888, 0x61FA0, 0x620C4, 0x6222E,
             0x62274, 0x6231C, 0x646EA, 0x653F6, 0x99D98, 0x9AABC, 0x9C084},
            {item["file_offset"] for item in payload["instructions"] if item["flow_kind"] == "return"},
        )
        returns = {item["file_offset"] for item in payload["instructions"] if item["flow_kind"] == "return"}
        self.assertIn(0x6107A, returns)
        self.assertNotIn(0x9A1AE, returns)
        self.assertNotIn(0x99DF4, returns)
        self.assertEqual(15, len(payload["raw_indirect_pc_sites"]))

    def test_all_external_owner_bindings_and_new_61624_entry_proof_are_exact(self) -> None:
        payload, bundle = self._payload_bundle()
        expected = {
            0x60FE0: 0x61624,
            0x6101A: 0x64700,
            0x61050: 0x64C68,
            0x6105A: 0x64A48,
            0x61064: 0x65384,
            0x6106C: 0x61D7C,
            0x61082: 0x61086,
            0x61F82: 0x9B0C4,
            0x61F94: 0x9B140,
            0x62250: 0x9C0E0,
            0x62294: 0x9C110,
            0x622E0: 0x9C0E0,
            0x622F8: 0x9C0E0,
            0x646DE: 0x9C0E0,
        }
        self.assertEqual(expected, {item["source_instruction_offset"]: item["target_offset"] for item in payload["external_edges"]})
        proof = payload["entry_proofs"]["0x08061624"]
        self.assertEqual([0x60FE0, 0x60FE4], proof["source_and_fallthrough"])
        self.assertEqual("00f020fb", proof["source_call"]["raw_hex"])
        self.assertEqual(0x61624, proof["source_call"]["target_offset"])
        self.assertEqual(0x60FE4, proof["source_call"]["fallthrough_offset"])
        self.assertEqual("30b5", proof["entry"]["raw_hex"])
        self.assertEqual(
            "0179fa50db01a670ea0d378b606928ed6b7a1f590c3fe52fcfe05a1936a84414",
            proof["entry"]["sha256"],
        )
        self.assertEqual("thumb", proof["entry"]["mode"])
        self.assertFalse(proof["target_scheduled"])
        self.assertEqual([0x61624, 0x61710], proof["owner_range"])
        self.assertEqual("consumer-code-battle_effect_sprite_animations-061624", proof["owner_claim_id"])
        self.assertIn("not instruction-only", proof["owner_limitation"])
        self.assertNotIn(0x61624, {item["file_offset"] for item in payload["instructions"]})
        self.assertNotIn(0x61624, {item["range"][0] for item in payload["blocks"]})
        self.assertNotIn([0x61624, 0x61710], payload["code_ranges"])
        self.assertNotIn([0x61624, 0x61710], payload["union_ranges"])
        self.assertTrue(
            all(not self._intersects(span, [0x61624, 0x61626]) for span in payload["union_ranges"])
        )

    def test_promotion_projection_is_frozen_and_binary_matches_union(self) -> None:
        payload, bundle = self._payload_bundle()
        self._assert_exact_promotion(payload, bundle)
        self.assertEqual(27, payload["promotion"]["code_range_count"])
        self.assertEqual(22, payload["promotion"]["literal_range_count"])
        self.assertEqual(25, payload["promotion"]["union_range_count"])
        self.assertEqual(1_226, payload["promotion"]["code_bytes"])
        self.assertEqual(296, payload["promotion"]["literal_bytes"])
        self.assertEqual(1_522, payload["promotion"]["union_bytes"])
        self.assertEqual(
            "73033e06942ec6604fe036849e40c420728f6f9bd4ae5db6c0fe49ba6eca2f22",
            payload["promotion"]["union_bytes_sha256"],
        )
        self.assertEqual(
            "f8df15ea8c3feb1a9c460bd0a2aabd79572806100ed726ada64b360aabb92aa5",
            payload["promotion"]["union_range_vector_sha256"],
        )
        expected = b"".join(self.rom[start:end] for start, end in payload["union_ranges"])
        self.assertEqual(expected, bundle)

    def test_payload_binary_manifest_receipt_and_command_tampering_fail_even_when_resigned(self) -> None:
        from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact

        with tempfile.TemporaryDirectory(dir=RUN_FINAL.parent) as directory:
            artifact = self._export(directory)
            payload_path = next(path for path in artifact.glob("*.json") if path.name != "manifest.json")
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["summary"]["instruction_count"] += 1
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self._resign_manifest(artifact, payload_path.name)
            self.assertFalse(verify_artifact(ROOT, artifact)["verified"])

            clean_artifact = self._export(Path(directory) / "clean")
            binary_artifact = Path(directory) / "binary-tampered"
            shutil.copytree(clean_artifact, binary_artifact)
            binary_path = next(binary_artifact.glob("*.bin"))
            binary = bytearray(binary_path.read_bytes())
            binary[0] ^= 1
            binary_path.write_bytes(binary)
            self._resign_manifest(binary_artifact, binary_path.name)
            self.assertFalse(verify_artifact(ROOT, binary_artifact)["verified"])

    def test_each_owner_and_receipt_leaf_mutation_fails_closed(self) -> None:
        from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact

        with tempfile.TemporaryDirectory(dir=RUN_FINAL.parent) as directory:
            clean_artifact = self._export(Path(directory) / "clean")
            clean_payload_path = clean_artifact / "rom-boot-thumb-handoff-cfg.json"
            clean_payload = json.loads(clean_payload_path.read_text(encoding="utf-8"))

            def mutate_case(label: str, mutate) -> None:
                case = Path(directory) / label
                shutil.copytree(clean_artifact, case)
                payload_path = case / clean_payload_path.name
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                mutate(payload)
                payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                self._resign_manifest(case, payload_path.name)
                self.assertFalse(verify_artifact(ROOT, case)["verified"], label)

            # Exercise every external owner leaf independently, including all
            # four edges that share 0x09C0E0 and every owner boundary record.
            for index in range(len(clean_payload["external_edges"])):
                mutate_case(f"owner-id-tampered-{index}", lambda payload, i=index: payload["external_edges"][i].__setitem__("owner_claim_id", "wrong-owner"))
                mutate_case(f"owner-range-tampered-{index}", lambda payload, i=index: payload["external_edges"][i].__setitem__("owner_range", [0, 1]))
            for key in clean_payload["existing_entry_claims"]:
                mutate_case(f"claim-range-tampered-{key[2:]}", lambda payload, k=key: payload["existing_entry_claims"][k].__setitem__("owner_range", [0, 1]))
                mutate_case(f"claim-class-tampered-{key[2:]}", lambda payload, k=key: payload["existing_entry_claims"][k].__setitem__("owner_primary_class", "wrong-class"))

            proof_leaves = (
                ("entry_mode", lambda payload: payload["entry_proofs"]["0x08061624"]["entry"].__setitem__("mode", "arm")),
                ("entry_raw", lambda payload: payload["entry_proofs"]["0x08061624"]["entry"].__setitem__("raw_hex", "00b5")),
                ("entry_hash", lambda payload: payload["entry_proofs"]["0x08061624"]["entry"].__setitem__("sha256", "0" * 64)),
                ("source_raw", lambda payload: payload["entry_proofs"]["0x08061624"]["source_call"].__setitem__("raw_hex", "00f021fb")),
                ("source_hash", lambda payload: payload["entry_proofs"]["0x08061624"]["source_call"].__setitem__("sha256", "0" * 64)),
                ("source_target", lambda payload: payload["entry_proofs"]["0x08061624"]["source_call"].__setitem__("target_offset", 0x61626)),
                ("source_fallthrough", lambda payload: payload["entry_proofs"]["0x08061624"]["source_call"].__setitem__("fallthrough_offset", 0x60FE6)),
                ("source_reachability", lambda payload: payload["instructions"].__setitem__(
                    next(i for i, item in enumerate(payload["instructions"]) if item["file_offset"] == 0x60FE0),
                    {**next(item for item in payload["instructions"] if item["file_offset"] == 0x60FE0), "file_offset": 0x60FDE},
                )),
                ("source_and_fallthrough", lambda payload: payload["entry_proofs"]["0x08061624"].__setitem__("source_and_fallthrough", [0x60FE0, 0x60FE6])),
                ("proof_owner_id", lambda payload: payload["entry_proofs"]["0x08061624"].__setitem__("owner_claim_id", "wrong-owner")),
                ("proof_owner_range", lambda payload: payload["entry_proofs"]["0x08061624"].__setitem__("owner_range", [0x61626, 0x61710])),
                ("proof_owner_class", lambda payload: payload["entry_proofs"]["0x08061624"].__setitem__("owner_primary_class", "wrong-class")),
                ("proof_limitation", lambda payload: payload["entry_proofs"]["0x08061624"].__setitem__("owner_limitation", "")),
                ("proof_schedule", lambda payload: payload["entry_proofs"]["0x08061624"].__setitem__("target_scheduled", True)),
                ("proof_resolution", lambda payload: payload["entry_proofs"]["0x08061624"].__setitem__("edge_resolution", "internal")),
            )
            for label, mutate in proof_leaves:
                mutate_case(f"proof-{label}", mutate)

            receipt_artifact = Path(directory) / "receipt-tampered"
            shutil.copytree(clean_artifact, receipt_artifact)
            manifest_path = receipt_artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["verification"]["command"][-1] = "foreign"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(verify_artifact(ROOT, receipt_artifact)["verified"])

    def test_verifier_rebuilds_instruction_edge_block_literal_and_promotion_leaves(self) -> None:
        from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact

        with tempfile.TemporaryDirectory(dir=RUN_FINAL.parent) as directory:
            clean_artifact = self._export(Path(directory) / "clean")
            payload_name = "rom-boot-thumb-handoff-cfg.json"

            def mutate_case(label: str, mutate) -> None:
                case = Path(directory) / label
                shutil.copytree(clean_artifact, case)
                payload_path = case / payload_name
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                mutate(payload)
                payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                self._resign_manifest(case, payload_name)
                self.assertFalse(verify_artifact(ROOT, case)["verified"], label)

            mutations = (
                ("instruction", lambda p: p["instructions"][0].__setitem__("raw_hex", "31b581b0")),
                ("edge", lambda p: p["edges"][0].__setitem__("kind", "fallthrough")),
                ("block", lambda p: p["blocks"][0]["range"].__setitem__(0, p["blocks"][0]["range"][0] + 2)),
                ("literal", lambda p: p["literal_bindings"][0].__setitem__("literal_offset", p["literal_bindings"][0]["literal_offset"] + 4)),
                ("literal_dedup", lambda p: p["literal_bindings"].append(dict(p["literal_bindings"][0]))),
                ("promotion_range", lambda p: p["promotion_ranges"][0]["range"].__setitem__(0, p["promotion_ranges"][0]["range"][0] + 2)),
                ("promotion_union", lambda p: p["union_ranges"].__setitem__(0, [0x60FA4, 0x61022])),
                ("coverage_claim", lambda p: p["coverage_claims"][0].__setitem__("size", p["coverage_claims"][0]["size"] + 1)),
            )
            for label, mutate in mutations:
                mutate_case(label, mutate)

    def test_verifier_uses_the_complete_external_source_target_contract(self) -> None:
        from tools import verify_rom_boot_thumb_handoff_cfg as verifier

        with tempfile.TemporaryDirectory(dir=RUN_ROOT) as directory:
            artifact = self._export(Path(directory) / "clean")
            changed = dict(verifier.EXTERNAL_TARGETS)
            changed[0x622F8] = 0x9C110
            with mock.patch.object(verifier, "EXTERNAL_TARGETS", changed):
                report = verifier.verify_artifact(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(any("external" in error.lower() for error in report["errors"]), report)

    def test_each_manifest_receipt_leaf_mutation_fails_closed(self) -> None:
        from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact

        with tempfile.TemporaryDirectory(dir=RUN_ROOT) as directory:
            clean = self._export(Path(directory) / "clean")

            def mutate_case(label: str, mutate) -> None:
                case = Path(directory) / label
                shutil.copytree(clean, case)
                manifest_path = case / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(manifest)
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                self.assertFalse(verify_artifact(ROOT, case)["verified"], label)

            mutations = (
                ("producer-command", lambda m: m["producer"]["command"].__setitem__(-1, "foreign")),
                ("producer-implementation", lambda m: m["producer"]["implementation"]["exporter"].__setitem__("sha256", "0" * 64)),
                ("verifier-schema", lambda m: m["verifier"].__setitem__("schema", "foreign")),
                ("verifier-command", lambda m: m["verifier"]["command"].__setitem__(-1, "foreign")),
                ("verifier-exit", lambda m: m["verifier"].__setitem__("exit_code", 2)),
                ("verifier-report", lambda m: m["verifier"]["report"].__setitem__("verified", False)),
                ("verifier-sha", lambda m: m["verifier"].__setitem__("verifier_sha256", "0" * 64)),
                ("verification-command", lambda m: m["verification"]["command"].__setitem__(-1, "foreign")),
                ("file-size", lambda m: m["files"]["rom-boot-thumb-handoff-cfg.bin"].__setitem__("size", 0)),
                ("file-sha", lambda m: m["files"]["rom-boot-thumb-handoff-cfg.bin"].__setitem__("sha256", "0" * 64)),
            )
            for label, mutate in mutations:
                mutate_case(label, mutate)

    def test_export_output_safety_and_verifier_source_independence(self) -> None:
        from tools import export_rom_boot_thumb_handoff_cfg as exporter
        from tools.export_rom_boot_thumb_handoff_cfg import export_artifact

        with tempfile.TemporaryDirectory(dir=RUN_FINAL.parent) as directory:
            base = Path(directory)
            foreign = base / "foreign"
            foreign.mkdir()
            (foreign / "keep").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "this run's final"):
                export_artifact(ROOT, foreign)
            isolated_experiment = base / "isolated"
            isolated_final = isolated_experiment / "final"
            isolated_final.mkdir(parents=True)
            (isolated_final / "keep").write_text("keep", encoding="utf-8")
            relative_experiment = isolated_experiment.relative_to(ROOT)
            with mock.patch.object(exporter, "EXPERIMENT_ROOT", relative_experiment):
                with self.assertRaisesRegex(ValueError, "foreign|non-empty"):
                    export_artifact(ROOT, isolated_final)
            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with mock.patch.object(exporter, "EXPERIMENT_ROOT", linked.relative_to(ROOT)):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    export_artifact(ROOT, linked / "final")
        with self.assertRaisesRegex(ValueError, "repository root"):
            export_artifact(ROOT, ROOT)
        with self.assertRaisesRegex(ValueError, "ancestor"):
            export_artifact(ROOT, ROOT.parent)

        source = (ROOT / "tools/verify_rom_boot_thumb_handoff_cfg.py").read_text(encoding="utf-8")
        self.assertNotIn("from tools.export_rom_boot_thumb_handoff_cfg", source)
        self.assertNotIn("import tools.export_rom_boot_thumb_handoff_cfg", source)

    def test_candidate_preflight_failure_preserves_existing_accepted_final(self) -> None:
        from tools import export_rom_boot_thumb_handoff_cfg as exporter

        self._export(RUN_FINAL)
        before = {path.name: path.read_bytes() for path in RUN_FINAL.iterdir()}
        with mock.patch.object(exporter, "_run_verifier", side_effect=ValueError("forced candidate rejection")):
            with self.assertRaisesRegex(ValueError, "forced candidate rejection"):
                exporter.export_artifact(ROOT, RUN_FINAL)
        self.assertEqual(before, {path.name: path.read_bytes() for path in RUN_FINAL.iterdir()})

    def test_public_verifier_rejects_candidate_and_requires_loaded_project_root(self) -> None:
        from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact

        with tempfile.TemporaryDirectory(dir=RUN_ROOT) as directory:
            accepted = self._export(Path(directory) / "accepted")
            candidate = Path(directory) / "candidate"
            shutil.copytree(accepted, candidate)
            manifest_path = candidate / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifact_status"] = "candidate"
            manifest["verifier"]["exit_code"] = None
            manifest["verifier"]["report"] = None
            manifest["verification"] = dict(manifest["verifier"])
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(verify_artifact(ROOT, candidate)["verified"])
            self.assertTrue(verify_artifact(ROOT, candidate, allow_candidate=True)["verified"])
            self.assertFalse(verify_artifact(ROOT.parent, accepted)["verified"])

    def test_noncanonical_payload_and_manifest_json_bytes_fail_closed(self) -> None:
        from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact

        with tempfile.TemporaryDirectory(dir=RUN_ROOT) as directory:
            clean = self._export(Path(directory) / "clean")
            for filename in ("rom-boot-thumb-handoff-cfg.json", "manifest.json"):
                case = Path(directory) / f"noncanonical-{filename}"
                shutil.copytree(clean, case)
                path = case / filename
                value = json.loads(path.read_text(encoding="utf-8"))
                path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                if filename != "manifest.json":
                    self._resign_manifest(case, filename)
                self.assertFalse(verify_artifact(ROOT, case)["verified"], filename)

    def test_verifier_rejects_symlinked_intermediate_artifact_path(self) -> None:
        from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact

        with tempfile.TemporaryDirectory(dir=RUN_ROOT) as directory:
            base = Path(directory)
            clean = self._export(base / "clean")
            linked = base / "linked"
            linked.symlink_to(clean, target_is_directory=True)
            report = verify_artifact(ROOT, linked)
            self.assertFalse(report["verified"])
            self.assertTrue(any("symlink" in error.lower() for error in report["errors"]), report)

    def test_verifier_reads_every_frozen_input_and_rejects_each_drift(self) -> None:
        from tools import verify_rom_boot_thumb_handoff_cfg as verifier

        sources = (
            ("BOOT_MANIFEST_PATH", "boot manifest"),
            ("CFG_SEEDS_PATH", "CFG seeds"),
            ("CFG_V2_MANIFEST_PATH", "CFG v2 manifest"),
            ("CFG_V2_PAYLOAD_PATH", "CFG v2 payload"),
            ("BOOT_INTERWORK_MANIFEST_PATH", "boot interwork manifest"),
            ("BOOT_INTERWORK_PAYLOAD_PATH", "boot interwork payload"),
        )
        with tempfile.TemporaryDirectory(dir=RUN_ROOT) as directory:
            artifact = self._export(Path(directory) / "clean")
            for constant, label in sources:
                original = ROOT / getattr(verifier, constant)
                replacement = Path(directory) / f"drift-{constant.lower()}.json"
                raw = bytearray(original.read_bytes())
                raw[0] ^= 1
                replacement.write_bytes(raw)
                relative = replacement.relative_to(ROOT).as_posix()
                with self.subTest(source=constant), mock.patch.object(verifier, constant, relative):
                    report = verifier.verify_artifact(ROOT, artifact)
                    self.assertFalse(report["verified"])
                    self.assertTrue(any(label.lower() in error.lower() for error in report["errors"]), report)


if __name__ == "__main__":
    unittest.main()
