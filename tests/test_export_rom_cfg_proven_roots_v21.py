"""TDD contract tests for the overlap-aware CFG proven-roots v21 packet."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class CfgProvenRootsV21Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_cfg_proven_roots_v21 as exporter
        from tools import verify_rom_cfg_proven_roots_v21 as verifier

        cls.exporter = exporter
        cls.verifier = verifier
        cls.C = exporter.C
        cls.rom = (ROOT / cls.C.ROM_PATH).read_bytes()

    def test_frozen_root_envelope_and_schema(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual("rom-cfg-proven-roots-v21", payload["schema"])
        self.assertEqual(0x063400, payload["root"]["file_offset"])
        self.assertEqual([0x063400, 0x063494], payload["root"]["envelope"])
        self.assertEqual(self.C.ENVELOPE_SHA256, payload["root"]["envelope_sha256"])

    def test_exact_raw_cfg_denominator(self) -> None:
        denominator = self.exporter.build_payload(ROOT)["target_local_denominator"]
        self.assertEqual((70, 17, 144, 2, 1), tuple(denominator[key] for key in (
            "instruction_count", "basic_block_count", "code_bytes",
            "opaque_call_count", "frontier_count")))
        self.assertEqual(self.C.CODE_RANGES, tuple(map(tuple, denominator["code_ranges"])))
        self.assertEqual(self.C.BLOCK_RANGES, tuple(map(tuple, denominator["blocks"])))
        self.assertEqual(self.C.OPAQUE_CALLS, tuple(
            (row["source"], row["target"]) for row in denominator["opaque_calls"]))

    def test_complete_direct_producer_denominator(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        denominator = payload["producer_denominator"]
        self.assertEqual(2, denominator["match_count"])
        self.assertEqual([0x06108A, 0x06131C],
                         [row["file_offset"] for row in denominator["matches"]])
        self.assertEqual([0x06108A],
                         [row["file_offset"] for row in payload["accepted_producers"]])
        rejected = payload["rejected_producers"]
        self.assertEqual([0x06131C], [row["file_offset"] for row in rejected])
        self.assertFalse(rejected[0]["instruction_only"])
        self.assertEqual("coverage_owner_not_instruction_only",
                         rejected[0]["rejection_reason"])

    def test_cross_owner_bl_is_fully_decoded_but_only_unknown_bytes_promote(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        split = payload["cross_owner_instruction"]
        self.assertEqual([0x06347C, 0x063480], split["instruction_range"])
        self.assertEqual("38f04afe", split["raw_hex"])
        self.assertEqual([0x06345E, 0x06347E], split["existing_owner_range"])
        self.assertEqual([0x06347E, 0x063480], split["promoted_suffix_range"])
        self.assertEqual(
            "consumer-code-battle_effect_sequence_bindings-06345e",
            split["existing_owner_claim_id"],
        )
        promotion = payload["promotion"]
        self.assertEqual(self.C.UNKNOWN_CODE_RANGES,
                         tuple(map(tuple, promotion["code_ranges"])))
        self.assertNotIn([0x06345E, 0x06347E], promotion["union_ranges"])

    def test_literal_and_return_candidate_remain_fail_closed(self) -> None:
        denominator = self.exporter.build_payload(ROOT)["target_local_denominator"]
        self.assertEqual([[0x063490, 0x063494]], denominator["literal_ranges"])
        self.assertEqual(2, denominator["literal_reference_count"])
        self.assertEqual(1, denominator["unique_literal_word_count"])
        self.assertEqual(
            [{"source": 0x06348E, "reason": "indirect_pc_target"}],
            denominator["frontiers"],
        )
        candidate = denominator["return_candidate"]
        self.assertFalse(candidate["opaque_callee_stack_effects_proven"])
        self.assertFalse(candidate["structured_return_proven"])
        self.assertEqual(0, denominator["structured_return_count"])

    def test_exact_current_unknown_projection(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        promotion = payload["promotion"]
        self.assertEqual((112, 4, 116, 3, 32), tuple(promotion[key] for key in (
            "code_bytes", "literal_bytes", "promotion_bytes", "claim_count",
            "existing_owner_code_provenance_bytes")))
        self.assertEqual(88_611, payload["coverage_projection"]["remaining_unknown_bytes"])
        self.assertEqual(6_202_845, payload["coverage_projection"]["classified_bytes"])

    def test_representative_raw_mutations_fail_closed(self) -> None:
        for offset, message in (
            (0x06108A, "producer"),
            (0x06131C, "producer"),
            (0x063400, "closure|envelope"),
            (0x06347E, "closure|envelope"),
            (0x06348E, "closure|return"),
            (0x063490, "closure|literal|envelope"),
        ):
            changed = bytearray(self.rom)
            changed[offset] ^= 1
            with self.subTest(offset=hex(offset)), self.assertRaisesRegex(ValueError, message):
                self.exporter._build_from_rom(ROOT, bytes(changed), verify_rom_identity=False)

    def test_export_roundtrip_and_independent_verifier(self) -> None:
        experiment = ROOT / self.C.EXPERIMENT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            first = self.verifier.verify_artifact(ROOT, output)
            second = self.verifier.verify_artifact(ROOT, output)
            self.assertEqual(first, second)
            self.assertTrue(first["verified"], first)
            self.assertEqual(116, first["promotion_bytes"])
            manifest = json.loads((output / self.C.MANIFEST_NAME).read_text())
            self.assertEqual("accepted", manifest["artifact_status"])
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, output)

    def test_published_candidate_requires_explicit_staging_verification(self) -> None:
        experiment = ROOT / self.C.EXPERIMENT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as directory:
            output = Path(directory) / "published"
            self.exporter.export_artifact(ROOT, output)
            manifest_path = output / self.C.MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text())
            manifest["artifact_status"] = "candidate"
            manifest["verifier"].pop("report")
            manifest["verifier"]["exit_code"] = None
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            # Model an interrupted publication: a final directory is present,
            # but the accepted receipt was never written.
            report = self.verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"], report)
            self.assertFalse(report["contract_ok"], report)
            self.assertTrue(any("candidate" in error for error in report["errors"]))
            # Naming the already published directory as its own intended target
            # must not turn ordinary verification into a staging acceptance.
            report = self.verifier.verify_artifact(
                ROOT, output, intended_artifact=output)
            self.assertFalse(report["verified"], report)
            with mock.patch("sys.argv", [
                    "verify_rom_cfg_proven_roots_v21.py", "--root", str(ROOT),
                    "--artifact", str(output)]), mock.patch("builtins.print"):
                self.assertEqual(1, self.verifier.main())

    def test_verifier_rebuilds_exact_payload_and_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v21.py").read_text()
        imports = [node for node in ast.walk(ast.parse(source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_cfg_proven_roots_v21" in ast.unparse(node)
                             for node in imports))
        experiment = ROOT / self.C.EXPERIMENT_ROOT
        mutations = (
            lambda payload, manifest: payload["promotion"].__setitem__("promotion_bytes", 118),
            lambda payload, manifest: payload.pop("cross_owner_instruction"),
            lambda payload, manifest: payload["scope"].__setitem__(
                "natural_runtime_reachability", True),
            lambda payload, manifest: manifest["implementation"]["verifier"].__setitem__(
                "sha256", "0" * 64),
        )
        with tempfile.TemporaryDirectory(dir=experiment) as directory:
            for index, mutate in enumerate(mutations):
                with self.subTest(index=index):
                    output = Path(directory) / f"candidate-{index}"
                    self.exporter.export_artifact(ROOT, output)
                    payload_path = output / self.C.PAYLOAD_NAME
                    manifest_path = output / self.C.MANIFEST_NAME
                    payload = json.loads(payload_path.read_text())
                    manifest = json.loads(manifest_path.read_text())
                    mutate(payload, manifest)
                    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
                    payload_path.write_bytes(raw)
                    manifest["files"][self.C.PAYLOAD_NAME] = {
                        "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                    self.assertFalse(self.verifier.verify_artifact(ROOT, output)["verified"])

    def test_output_and_artifact_path_safety(self) -> None:
        experiment = ROOT / self.C.EXPERIMENT_ROOT
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory(
                dir=experiment) as directory:
            base = Path(directory)
            link = base / "escape"
            link.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, link / "candidate")
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(ROOT, base / ".." / "escape")
            output = base / "candidate"
            self.exporter.export_artifact(ROOT, output)
            (output / "extra").write_text("forbidden")
            self.assertFalse(self.verifier.verify_artifact(ROOT, output)["verified"])

    def test_publish_rejects_staging_name_swap_after_candidate_verification(self) -> None:
        experiment = ROOT / self.C.EXPERIMENT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as directory:
            output = Path(directory) / "candidate"
            original_publish = self.exporter._publish_exclusive_at

            def swap_then_publish(parent_fd, source_name, destination_name):
                os.rename(source_name, "held-verified-stage",
                          src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                os.mkdir(source_name, dir_fd=parent_fd)
                return original_publish(parent_fd, source_name, destination_name)

            with mock.patch.object(self.exporter, "_publish_exclusive_at",
                                   side_effect=swap_then_publish):
                with self.assertRaisesRegex(ValueError, "published artifact identity"):
                    self.exporter.export_artifact(ROOT, output)
            self.assertFalse(output.exists())

    def test_member_reader_rejects_name_replacement_during_read(self) -> None:
        experiment = ROOT / self.C.EXPERIMENT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as directory:
            base = Path(directory)
            (base / "member").write_bytes(b"original")
            directory_fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
            original_read = os.read
            replaced = False

            def read_then_replace(file_fd, count):
                nonlocal replaced
                raw = original_read(file_fd, count)
                if raw and not replaced:
                    replaced = True
                    replacement = base / "replacement"
                    replacement.write_bytes(b"changed!")
                    os.replace(replacement, base / "member")
                return raw

            try:
                with mock.patch.object(self.verifier.os, "read",
                                       side_effect=read_then_replace):
                    with self.assertRaisesRegex(ValueError, "member changed"):
                        self.verifier._read_regular_at(directory_fd, "member")
            finally:
                os.close(directory_fd)

    def test_verifier_rejects_member_changes_after_initial_reads(self) -> None:
        experiment = ROOT / self.C.EXPERIMENT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as directory:
            for name in (self.C.PAYLOAD_NAME, self.C.MANIFEST_NAME, "extra"):
                with self.subTest(member=name):
                    output = Path(directory) / name
                    self.exporter.export_artifact(ROOT, output)
                    original_read = self.verifier._read_regular_at
                    replaced = False

                    def read_then_replace(directory_fd, member):
                        nonlocal replaced
                        raw = original_read(directory_fd, member)
                        if member == self.C.MANIFEST_NAME and not replaced:
                            replaced = True
                            replacement = output / "replacement"
                            replacement.write_bytes(b"{}\n")
                            os.replace(replacement, output / name)
                        return raw

                    with mock.patch.object(self.verifier, "_read_regular_at",
                                           side_effect=read_then_replace):
                        report = self.verifier.verify_artifact(ROOT, output)
                    self.assertFalse(report["verified"], report)

    def test_export_rejects_member_replacement_after_final_verification(self) -> None:
        experiment = ROOT / self.C.EXPERIMENT_ROOT
        with tempfile.TemporaryDirectory(dir=experiment) as directory:
            output = Path(directory) / "published"
            original_verify = self.verifier.verify_artifact

            def verify_then_replace(root, artifact, **kwargs):
                report = original_verify(root, artifact, **kwargs)
                if report.get("artifact_status") == "accepted":
                    replacement = Path(artifact) / "replacement"
                    replacement.write_bytes(b"{}\n")
                    os.replace(replacement, Path(artifact) / self.C.PAYLOAD_NAME)
                return report

            with mock.patch.object(self.verifier, "verify_artifact",
                                   side_effect=verify_then_replace):
                with self.assertRaisesRegex(ValueError, "member"):
                    self.exporter.export_artifact(ROOT, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
