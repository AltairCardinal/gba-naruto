"""Contract tests for the SoundMain relocated align4-gap verifier."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
ARTIFACT_DIR = ROOT / "artifacts/rom-soundmain-relocated-cfg-v1"
VERIFIER_PATH = ROOT / "tools/verify_rom_soundmain_relocated_alignment_gaps.py"

VERIFY_SCHEMA = "rom-soundmain-relocated-alignment-gaps-verification-v1"
PROMOTION_BATCH = "rom-soundmain-relocated-alignment-gaps-v1"
PRIMARY_CLASS = "soundmain_relocated_artifact_bound_4byte_alignment_bytes"
CLAIM_KIND = "soundmain_relocated_alignment_gap_bytes"
RANGES = (
    (0x099E1A, 0x099E1C),
    (0x099EC2, 0x099EC4),
    (0x099FA6, 0x099FA8),
)
IDS = (
    "soundmain-thumb-to-arm-099e1a",
    "soundmain-branch-to-literal-099ec2",
    "soundmain-thumb-to-arm-099fa6",
)
RIGHT_KINDS = ("arm_block", "consumed_literal_range", "arm_block")
RANGE_VECTOR_SHA256 = (
    "80e7409ef3fd737361faa6a08ae8e2efbedd9891c31e4f4b98392a3ad91da3af"
)
BOUNDARY_VECTOR_SHA256 = (
    "2f21e70062013bff5f99a9191920f3a6b4ee8996fd1adb0d8cfe577f7d450dd4"
)
CLAIM_DENOMINATOR_SHA256 = (
    "ed6703a2245ca526dc40809dafbaa65328faec20f5aa493ab735ab70128cbd6c"
)
SOURCE_FILE_VECTOR_SHA256 = (
    "94d5aa4caa9f45d802f4cecde10d1f08ee4c5650a0c4f24bf40707f2ca1888a2"
)
PACKED_BYTES_SHA256 = (
    "b0f66adc83641586656866813fd9dd0b8ebb63796075661ba45d1aa8089e1d44"
)
ZERO_PAIR_SHA256 = (
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
)
TERMINALS = (
    ([0x099E18, 0x099E1A], "0847", "mode_switch", "bx", "r1", 0x099E1C),
    (
        [0x099EC0, 0x099EC2],
        "6be1",
        "unconditional_branch",
        "b",
        "#0x3007b52",
        0x09A19A,
    ),
    ([0x099FA4, 0x099FA6], "0047", "mode_switch", "bx", "r0", 0x099FA8),
)
RIGHT_RANGES = (
    [0x099E1C, 0x099E2C],
    [0x099EC4, 0x099EC8],
    [0x099FA8, 0x099FC8],
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_verifier():
    try:
        return importlib.import_module(
            "tools.verify_rom_soundmain_relocated_alignment_gaps"
        )
    except ModuleNotFoundError as error:
        raise AssertionError(
            "target verifier module is absent (the expected RED condition)"
        ) from error


class SoundMainRelocatedAlignmentGapVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()
        cls.manifest = json.loads(
            (ARTIFACT_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        cls.payload = json.loads(
            (ARTIFACT_DIR / "rom-soundmain-relocated-cfg.json").read_text(
                encoding="utf-8"
            )
        )
        cls.binary = (
            ARTIFACT_DIR / "rom-soundmain-relocated-cfg.bin"
        ).read_bytes()
        wrapper = importlib.import_module(
            "tools.verify_rom_soundmain_relocated_cfg_bundle"
        )
        cls.bundle_report = wrapper.verify_artifact_bundle(
            ROOT, Path("artifacts/rom-soundmain-relocated-cfg-v1")
        )

    def _verify_inputs(self, rom: bytes, **overrides):
        values = {
            "manifest": self.manifest,
            "payload": self.payload,
            "binary": self.binary,
            "bundle_report": self.bundle_report,
        }
        values.update(overrides)
        return _load_verifier().verify_inputs(rom, **values)

    def test_exact_denominator_order_and_frozen_source_identity(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(VERIFY_SCHEMA, report["schema"])
        self.assertEqual([], report["errors"])
        self.assertEqual(PROMOTION_BATCH, report["promotion_batch"])
        self.assertEqual(PRIMARY_CLASS, report["primary_class"])
        self.assertEqual(CLAIM_KIND, report["claim_kind"])
        self.assertEqual(3, report["gap_count"])
        self.assertEqual(6, report["byte_count"])
        self.assertEqual(6, report["zero_byte_count"])
        self.assertEqual([list(pair) for pair in RANGES], report["ranges"])
        self.assertEqual(RANGE_VECTOR_SHA256, report["range_vector_sha256"])
        self.assertEqual(
            BOUNDARY_VECTOR_SHA256, report["boundary_vector_sha256"]
        )
        self.assertEqual(
            CLAIM_DENOMINATOR_SHA256, report["claim_denominator_sha256"]
        )
        self.assertEqual(
            SOURCE_FILE_VECTOR_SHA256, report["source_file_vector_sha256"]
        )
        self.assertEqual(PACKED_BYTES_SHA256, report["packed_bytes_sha256"])
        self.assertEqual(1, report["source_artifact_count"])
        self.assertTrue(report["source_bundle_verified"])
        self.assertTrue(report["all_alignment_equations_hold"])
        self.assertTrue(report["all_boundaries_exact"])
        self.assertEqual(IDS, tuple(row["id"] for row in report["gaps"]))
        self.assertEqual(
            RIGHT_KINDS, tuple(row["right_kind"] for row in report["gaps"])
        )
        sources = report["source_files"]
        self.assertEqual(
            "e6b9a2cbdb439c520b5c98a422279e44e03866dbf1541810626d28eb57ce0a37",
            sources["manifest.json"]["sha256"],
        )
        self.assertEqual(
            "63543ece1982ced20eb0818faf3b6f1848e72ba6dcdb68105fa8b2e3e07e477a",
            sources["rom-soundmain-relocated-cfg.json"]["sha256"],
        )
        self.assertEqual(
            "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331",
            sources["rom-soundmain-relocated-cfg.bin"]["sha256"],
        )

    def test_each_gap_binds_terminal_align4_and_exact_right_structure(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        for index, row in enumerate(report["gaps"]):
            start, end = RANGES[index]
            terminal_range, raw_hex, flow_kind, mnemonic, op_str, target = (
                TERMINALS[index]
            )
            self.assertEqual([start, end], row["gap_range"])
            self.assertEqual("0000", row["gap_raw_hex"])
            self.assertEqual(ZERO_PAIR_SHA256, row["gap_sha256"])
            self.assertEqual(2, row["gap_size"])
            self.assertEqual(terminal_range, row["left_terminal"]["range"])
            self.assertEqual(raw_hex, row["left_terminal"]["raw_hex"])
            self.assertEqual(flow_kind, row["left_terminal"]["flow_kind"])
            self.assertEqual(mnemonic, row["left_terminal"]["mnemonic"])
            self.assertEqual(op_str, row["left_terminal"]["op_str"])
            self.assertEqual(target, row["left_terminal"]["target_offset"])
            self.assertEqual(RIGHT_RANGES[index], row["right_range"])
            self.assertEqual(start, row["left_owner_range"][1])
            self.assertEqual(end, row["right_range"][0])
            self.assertEqual(end, (start + 3) & ~3)
            self.assertTrue(row["gap_start_equals_left_owner_end"])
            self.assertTrue(row["gap_end_equals_align4_left_end"])
            self.assertTrue(row["right_start_equals_gap_end"])
            self.assertEqual(self.rom[start:end].hex(), row["gap_raw_hex"])

    def test_rom_gap_terminal_and_right_mutations_fail_after_rom_resign(self) -> None:
        verifier = _load_verifier()
        offsets = (
            0x099E1A,
            0x099EC2,
            0x099FA6,
            0x099E18,
            0x099EC0,
            0x099FA4,
            0x099E1C,
            0x099EC4,
            0x099FA8,
        )
        for offset in offsets:
            with self.subTest(offset=hex(offset)):
                mutated = bytearray(self.rom)
                mutated[offset] ^= 1
                with mock.patch.object(verifier, "ROM_SHA256", _sha(bytes(mutated))):
                    report = self._verify_inputs(bytes(mutated))
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])

    def test_payload_semantic_mutations_and_shallow_resigns_fail_closed(self) -> None:
        mutations = []
        extra = copy.deepcopy(self.payload)
        extra["injected"] = True
        mutations.append(extra)
        reversed_gaps = copy.deepcopy(self.payload)
        reversed_gaps["cfg"]["alignment_gap_ranges"].reverse()
        mutations.append(reversed_gaps)
        duplicate_block = copy.deepcopy(self.payload)
        duplicate_block["cfg"]["blocks"].append(
            copy.deepcopy(duplicate_block["cfg"]["blocks"][0])
        )
        mutations.append(duplicate_block)
        changed_terminal = copy.deepcopy(self.payload)
        block = next(
            row
            for row in changed_terminal["cfg"]["blocks"]
            if row["id"] == "block-thumb-099e16"
        )
        block["terminator"]["op_str"] = "r0"
        mutations.append(changed_terminal)
        changed_promotion = copy.deepcopy(self.payload)
        changed_promotion["promotion"]["deferred_alignment_gap_ranges"].reverse()
        mutations.append(changed_promotion)

        for index, payload in enumerate(mutations):
            with self.subTest(index=index):
                report = self._verify_inputs(self.rom, payload=payload)
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])

    def test_manifest_binary_and_bundle_receipt_drift_fail_closed(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["artifact_status"] = "candidate"
        self.assertFalse(
            self._verify_inputs(self.rom, manifest=manifest)["verified"]
        )

        binary = bytearray(self.binary)
        binary[0] ^= 1
        self.assertFalse(
            self._verify_inputs(self.rom, binary=bytes(binary))["verified"]
        )

        for key in (
            "verified",
            "artifact_bundle_verified",
            "legacy_receipt_verified",
            "candidate_identity_verified",
        ):
            with self.subTest(key=key):
                receipt = copy.deepcopy(self.bundle_report)
                receipt[key] = False
                report = self._verify_inputs(self.rom, bundle_report=receipt)
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])

    def test_stale_bundle_receipt_cannot_cover_nested_payload_drift(self) -> None:
        mutations = []

        missing_literal_binding = copy.deepcopy(self.payload)
        missing_literal_binding["cfg"]["literal_bindings"] = []
        mutations.append(missing_literal_binding)

        changed_right_arm_block = copy.deepcopy(self.payload)
        block = next(
            row
            for row in changed_right_arm_block["cfg"]["blocks"]
            if row["id"] == "block-arm-099e1c"
        )
        block["instruction_count"] = 99
        mutations.append(changed_right_arm_block)

        for index, payload in enumerate(mutations):
            with self.subTest(index=index):
                report = self._verify_inputs(
                    self.rom,
                    payload=payload,
                    bundle_report=self.bundle_report,
                )
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])

    def test_bundle_wrapper_executes_frozen_bytes_without_reopening_path(self) -> None:
        verifier = _load_verifier()
        frozen_source = b"raise AssertionError('subprocess mock should intercept')\n"
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(self.bundle_report).encode("utf-8"),
            stderr=b"",
        )
        with mock.patch.object(verifier.subprocess, "run", return_value=completed) as run:
            report = verifier._run_bundle_verifier(
                ROOT,
                frozen_source,
                VERIFIER_PATH,
            )

        self.assertEqual(self.bundle_report, report)
        command = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertEqual([sys.executable, "-I", "-S", "-c"], command[:4])
        self.assertIn("sys.stdin.buffer.read()", command[4])
        self.assertEqual(frozen_source, kwargs["input"])
        self.assertNotIn("text", kwargs)
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["check"])

    def test_nonclaims_are_explicit_false_and_semantic_packet_is_unchanged(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        self.assertTrue(report["limitations"])
        self.assertTrue(report["non_claims"])
        self.assertTrue(all(value is False for value in report["non_claims"].values()))
        self.assertFalse(report["semantic_packet_modified"])
        joined = " ".join(report["limitations"]).lower()
        for marker in (
            "padding",
            "nop",
            "instruction",
            "reserved",
            "free",
            "allocatable",
            "natural runtime",
            "compiler",
            "editing",
            "relocation",
            "exhaustive",
        ):
            self.assertIn(marker, joined)

    def test_cli_path_safety_and_source_independence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            outside = Path(raw)
            completed = subprocess.run(
                [sys.executable, str(VERIFIER_PATH), "--root", str(ROOT)],
                cwd=outside,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["verified"])

            linked = outside / "root-link"
            linked.symlink_to(ROOT, target_is_directory=True)
            rejected = subprocess.run(
                [sys.executable, str(VERIFIER_PATH), "--root", str(linked)],
                cwd=outside,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, rejected.returncode)
            self.assertFalse(json.loads(rejected.stdout)["verified"])

            traversal = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER_PATH),
                    "--root",
                    str(ROOT / ".."),
                ],
                cwd=outside,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, traversal.returncode)
            self.assertFalse(json.loads(traversal.stdout)["verified"])

        tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("tools.audit_rom_byte_coverage", imported)
        self.assertNotIn("tools.verify_rom_soundmain_relocated_cfg", imported)


if __name__ == "__main__":
    unittest.main()
