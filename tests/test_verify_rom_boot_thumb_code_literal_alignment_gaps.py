#!/usr/bin/env python3
"""Contract tests for the independent boot Thumb alignment-gap verifier."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
VERIFIER_PATH = ROOT / "tools/verify_rom_boot_thumb_code_literal_alignment_gaps.py"
CONTRACT = (
    ROOT
    / "build/experiments/active/boot-thumb-code-literal-alignment-gap-preflight-20260830/CONTRACT.json"
)
SOURCE_DIR = ROOT / "artifacts/rom-boot-thumb-handoff-cfg-v1"
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
SOURCE_PAYLOAD = SOURCE_DIR / "rom-boot-thumb-handoff-cfg.json"
SOURCE_IMPLEMENTATION = (
    ROOT / "tools/export_rom_boot_thumb_handoff_cfg.py",
    ROOT / "tools/verify_rom_boot_thumb_handoff_cfg.py",
    ROOT / "tests/test_export_rom_boot_thumb_handoff_cfg.py",
)

VERIFY_SCHEMA = "rom-boot-thumb-code-literal-alignment-gaps-verification-v1"
EXPECTED_CONTRACT_SHA256 = (
    "2298b1f03236d77eb14e0970612c54cbfa2ba10f92ba595fc1cb6426a61f338b"
)
EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74"
)
EXPECTED_SOURCE_PAYLOAD_SHA256 = (
    "a35b581e44b276399874a2fc393f22f3c548c6b99e053f504587bdd92fbad295"
)
EXPECTED_RANGE_VECTOR_SHA256 = (
    "dec4177a9818ff7b3349a7c678f8e4a223f4a6e8ac254e2cd81bb4cf1362ce58"
)
EXPECTED_BOUNDARY_VECTOR_SHA256 = (
    "2c1e60388f8fd7ef11118e7a61ac93fa7816aa6012e7f6e3478a45d4d080b54f"
)
EXPECTED_PACKED_BYTES_SHA256 = (
    "9d908ecfb6b256def8b49a7c504e6c889c4b0e41fe6ce3e01863dd7b61a20aa0"
)

GAP_RANGES = (
    (397346, 397348),
    (397566, 397568),
    (397598, 397600),
    (397642, 397644),
    (399454, 399456),
    (401290, 401292),
    (401606, 401608),
    (402038, 402040),
    (402206, 402208),
    (630262, 630264),
    (639046, 639048),
    (639110, 639112),
)
TERMINAL_OFFSETS = (
    397344,
    397564,
    397596,
    397640,
    399452,
    401288,
    401604,
    402036,
    402204,
    630260,
    639044,
    639108,
)
RETURN_TERMINALS = (397640, 401604, 402036, 402204, 639108)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _load_verifier():
    try:
        return importlib.import_module(
            "tools.verify_rom_boot_thumb_code_literal_alignment_gaps"
        )
    except ModuleNotFoundError as error:
        raise AssertionError("target verifier is absent (the expected RED condition)") from error


class BootThumbCodeLiteralAlignmentGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()
        cls.source_payload = json.loads(SOURCE_PAYLOAD.read_text(encoding="utf-8"))
        cls.source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))

    @staticmethod
    def _copy_project(project: Path) -> None:
        (project / "rom").mkdir(parents=True)
        shutil.copy2(ROM_PATH, project / "rom/base.gba")
        shutil.copytree(SOURCE_DIR, project / SOURCE_DIR.relative_to(ROOT))
        for source in SOURCE_IMPLEMENTATION:
            destination = project / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_bytes(_canonical(value))

    def _resign_source(self, project: Path, payload: dict, *, manifest_patch=None) -> None:
        payload_path = project / SOURCE_PAYLOAD.relative_to(ROOT)
        manifest_path = project / SOURCE_MANIFEST.relative_to(ROOT)
        self._write_json(payload_path, payload)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload_receipt = manifest["files"][payload_path.name]
        payload_receipt["sha256"] = _sha(payload_path.read_bytes())
        payload_receipt["size"] = payload_path.stat().st_size
        if manifest_patch is not None:
            manifest_patch(manifest)
        self._write_json(manifest_path, manifest)

    def _verify_resigned_source(self, project: Path, payload: dict, *, manifest_patch=None, rom=None):
        self._resign_source(project, payload, manifest_patch=manifest_patch)
        manifest_path = project / SOURCE_MANIFEST.relative_to(ROOT)
        payload_path = project / SOURCE_PAYLOAD.relative_to(ROOT)
        verifier = _load_verifier()
        patches = {
            "SOURCE_MANIFEST_SHA256": _sha(manifest_path.read_bytes()),
            "SOURCE_PAYLOAD_SHA256": _sha(payload_path.read_bytes()),
        }
        if rom is not None:
            patches["ROM_SHA256"] = _sha(rom)
        with mock.patch.multiple(verifier, **patches):
            return verifier.verify_root(project)

    def test_default_cli_accepts_frozen_repository_without_preflight_inputs(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-I", "-S", str(VERIFIER_PATH), "--root", str(ROOT)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(1, len(completed.stdout.splitlines()))
        report = json.loads(completed.stdout)
        self.assertTrue(report["verified"], report.get("errors"))
        self.assertEqual(VERIFY_SCHEMA, report["schema"])
        self.assertEqual(EXPECTED_ROM_SHA256, report["rom"]["sha256"])
        self.assertEqual(EXPECTED_SOURCE_MANIFEST_SHA256, report["source"]["manifest"]["sha256"])
        self.assertEqual(EXPECTED_SOURCE_PAYLOAD_SHA256, report["source"]["payload"]["sha256"])
        self.assertEqual(EXPECTED_CONTRACT_SHA256, report["contract_sha256"])

    def test_optional_contract_is_only_an_extra_consistency_check(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                str(VERIFIER_PATH),
                "--root",
                str(ROOT),
                "--contract",
                str(CONTRACT.relative_to(ROOT)),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(EXPECTED_CONTRACT_SHA256, report["contract_sha256"])

    def test_report_recomputes_denominators_rows_and_terminal_flow_counts(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        summary = report["summary"]
        self.assertEqual(12, summary["gap_count"])
        self.assertEqual(24, summary["gap_bytes"])
        self.assertEqual(27, summary["code_range_count"])
        self.assertEqual(1226, summary["code_bytes"])
        self.assertEqual(22, summary["consumed_literal_range_count"])
        self.assertEqual(296, summary["consumed_literal_bytes"])
        self.assertEqual(77, summary["literal_binding_count"])
        self.assertEqual(EXPECTED_RANGE_VECTOR_SHA256, summary["range_vector_sha256"])
        self.assertEqual(EXPECTED_BOUNDARY_VECTOR_SHA256, summary["boundary_vector_sha256"])
        self.assertEqual(EXPECTED_PACKED_BYTES_SHA256, summary["packed_bytes_sha256"])
        self.assertEqual(
            {"indirect_branch": 1, "return": 5, "unconditional_branch": 6},
            summary["flow_counts"],
        )
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        for key in (
            "gap_count",
            "gap_bytes",
            "size_counts",
            "flow_counts",
            "range_vector_sha256",
            "boundary_vector_sha256",
            "packed_bytes_sha256",
            "all_bytes_zero",
            "alignment_formula",
        ):
            self.assertEqual(contract["candidate"][key], report["candidate"][key])
        for frozen, actual in zip(contract["candidate"]["rows"], report["candidate"]["rows"]):
            for key in ("id", "range", "size", "sha256", "raw_hex", "alignment", "terminal"):
                self.assertEqual(frozen[key], actual[key])
        self.assertEqual(contract["source_denominator"], report["source_denominator"])
        self.assertEqual("boot_thumb_code_literal_alignment_bytes", report["primary_class"])
        self.assertEqual("boot_thumb_code_literal_alignment_gap_bytes", report["claim_kind"])
        self.assertEqual(list(GAP_RANGES), [tuple(row["range"]) for row in report["gaps"]])
        self.assertEqual(RETURN_TERMINALS, tuple(
            row["terminal"]["offset"]
            for row in report["gaps"]
            if row["terminal"]["flow_kind"] == "return"
        ))

    def test_source_identity_and_shallow_resign_fail_closed(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            project = Path(raw) / "project"
            self._copy_project(project)
            payload = copy.deepcopy(self.source_payload)
            payload["summary"]["instruction_bytes"] += 1
            self._resign_source(project, payload)
            report = verifier.verify_root(project)
            self.assertFalse(report["verified"])
            self.assertTrue(any("identity" in error for error in report["errors"]), report)

    def test_source_manifest_scope_and_implementation_receipts_are_bound(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            project = Path(raw) / "project"
            self._copy_project(project)
            manifest_path = project / SOURCE_MANIFEST.relative_to(ROOT)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["scope"]["envelope_gaps_classified"] = True
            self._write_json(manifest_path, manifest)
            report = verifier.verify_root(project)
            self.assertFalse(report["verified"])
            self.assertTrue(any("identity" in error or "scope" in error for error in report["errors"]), report)

    def test_rom_identity_mutation_fails_without_touching_real_rom(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            project = Path(raw) / "project"
            self._copy_project(project)
            rom = bytearray((project / "rom/base.gba").read_bytes())
            rom[0x100] ^= 1
            (project / "rom/base.gba").write_bytes(rom)
            report = verifier.verify_root(project)
            self.assertFalse(report["verified"])
            self.assertTrue(any("ROM" in error or "rom" in error for error in report["errors"]), report)
        self.assertEqual(EXPECTED_ROM_SHA256, _sha(self.rom))

    def test_code_literal_denominator_order_and_range_mutations_fail_after_complete_resign(self) -> None:
        verifier = _load_verifier()
        mutations = (
            ("code-order", lambda p: p["code_ranges"].reverse()),
            ("code-range", lambda p: p["code_ranges"][0].__setitem__(0, p["code_ranges"][0][0] + 2)),
            ("literal-order", lambda p: p["literal_ranges"].reverse()),
            ("literal-range", lambda p: p["literal_ranges"][0].__setitem__(1, p["literal_ranges"][0][1] - 2)),
            ("binding-order", lambda p: p["literal_bindings"].reverse()),
            ("binding-denominator", lambda p: p["literal_bindings"].pop()),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label), tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
                project = Path(raw) / "project"
                self._copy_project(project)
                payload = copy.deepcopy(self.source_payload)
                mutate(payload)
                report = self._verify_resigned_source(project, payload)
                self.assertFalse(report["verified"], report)
                self.assertTrue(report["errors"], label)

    def test_every_gap_byte_mutation_is_rejected(self) -> None:
        verifier = _load_verifier()
        for offset in (offset for start, end in GAP_RANGES for offset in range(start, end)):
            with self.subTest(offset=offset), tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
                project = Path(raw) / "project"
                self._copy_project(project)
                rom_path = project / "rom/base.gba"
                rom = bytearray(rom_path.read_bytes())
                rom[offset] ^= 1
                rom_path.write_bytes(rom)
                with mock.patch.object(verifier, "ROM_SHA256", _sha(bytes(rom))):
                    report = verifier.verify_root(project)
                self.assertFalse(report["verified"], report)
                self.assertTrue(any("gap" in error or "zero" in error for error in report["errors"]), report)

    def test_every_terminal_instruction_mutation_is_rejected(self) -> None:
        verifier = _load_verifier()
        for offset in TERMINAL_OFFSETS:
            with self.subTest(offset=offset), tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
                project = Path(raw) / "project"
                self._copy_project(project)
                rom_path = project / "rom/base.gba"
                rom = bytearray(rom_path.read_bytes())
                rom[offset] ^= 1
                rom_path.write_bytes(rom)
                with mock.patch.object(verifier, "ROM_SHA256", _sha(bytes(rom))):
                    report = verifier.verify_root(project)
                self.assertFalse(report["verified"], report)
                self.assertTrue(any("terminal" in error or "branch" in error or "return" in error for error in report["errors"]), report)

    def test_branch_target_and_no_fallthrough_semantics_fail_closed(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            project = Path(raw) / "project"
            self._copy_project(project)
            rom_path = project / "rom/base.gba"
            rom = bytearray(rom_path.read_bytes())
            # B #0 targets the first byte after the code, i.e. the gap.
            rom[397344:397346] = bytes.fromhex("00e0")
            rom_path.write_bytes(rom)
            with mock.patch.object(verifier, "ROM_SHA256", _sha(bytes(rom))):
                report = verifier.verify_root(project)
            self.assertFalse(report["verified"])
            self.assertTrue(any("gap" in error or "branch" in error or "terminal" in error for error in report["errors"]), report)

        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            project = Path(raw) / "project"
            self._copy_project(project)
            payload = copy.deepcopy(self.source_payload)
            item = next(item for item in payload["instructions"] if item["file_offset"] == 397344)
            item["successors"].append({"file_offset": 397346, "kind": "fallthrough", "mode": "thumb"})
            report = self._verify_resigned_source(project, payload)
            self.assertFalse(report["verified"], report)
            self.assertTrue(any("fallthrough" in error or "terminal" in error for error in report["errors"]), report)

    def test_return_idiom_is_exact_and_requires_unique_previous_fallthrough(self) -> None:
        verifier = _load_verifier()
        cases = (
            ("pop-multi", lambda rom, previous: rom.__setitem__(slice(previous, previous + 2), (0xBC03).to_bytes(2, "little"))),
            ("pop-pc", lambda rom, previous: rom.__setitem__(slice(previous, previous + 2), (0xBD01).to_bytes(2, "little"))),
            ("pop-bx-mismatch", lambda rom, previous: rom.__setitem__(slice(previous, previous + 2), (0xBC02).to_bytes(2, "little"))),
            ("pop-missing", lambda rom, previous: rom.__setitem__(slice(previous, previous + 2), (0x2000).to_bytes(2, "little"))),
            ("pop-nonadjacent", lambda rom, previous: rom.__setitem__(slice(previous, previous + 2), (0x4770).to_bytes(2, "little"))),
        )
        for label, mutate in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
                project = Path(raw) / "project"
                self._copy_project(project)
                rom_path = project / "rom/base.gba"
                rom = bytearray(rom_path.read_bytes())
                terminal = 397640
                mutate(rom, terminal - 2)
                rom_path.write_bytes(rom)
                with mock.patch.object(verifier, "ROM_SHA256", _sha(bytes(rom))):
                    report = verifier.verify_root(project)
                self.assertFalse(report["verified"], report)
                self.assertTrue(report["errors"], report)

        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            project = Path(raw) / "project"
            self._copy_project(project)
            payload = copy.deepcopy(self.source_payload)
            predecessor = next(item for item in payload["instructions"] if item["file_offset"] == 397638)
            predecessor["successors"].append({"file_offset": 397640, "kind": "branch_target", "mode": "thumb"})
            report = self._verify_resigned_source(project, payload)
            self.assertFalse(report["verified"], report)
            self.assertTrue(any("incoming" in error or "return" in error for error in report["errors"]), report)

    def test_invalid_pop_predecessors_decode_as_indirect_and_fail_frozen_flow_count(self) -> None:
        verifier = _load_verifier()
        cases = (
            ("pop-multi", 0xBC03),
            ("pop-pc", 0xBD01),
            ("pop-bx-mismatch", 0xBC02),
            ("pop-missing", 0x2000),
            ("pop-nonadjacent", 0x4770),
        )
        terminal_offset = 397640
        predecessor_offset = terminal_offset - 2
        for label, raw_word in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
                project = Path(raw) / "project"
                self._copy_project(project)
                rom = bytearray((project / "rom/base.gba").read_bytes())
                raw_bytes = raw_word.to_bytes(2, "little")
                rom[predecessor_offset:terminal_offset] = raw_bytes
                (project / "rom/base.gba").write_bytes(rom)
                payload = copy.deepcopy(self.source_payload)
                predecessor = next(item for item in payload["instructions"] if item["file_offset"] == predecessor_offset)
                predecessor["raw_hex"] = raw_bytes.hex()
                predecessor["bytes_sha256"] = _sha(raw_bytes)
                code_claim = next(
                    item
                    for item in payload["coverage_claims"]
                    if item["range"][0] <= predecessor_offset < item["range"][1]
                )
                code_start, code_end = code_claim["range"]
                code_claim["sha256"] = _sha(bytes(rom[code_start:code_end]))
                terminal = next(item for item in payload["instructions"] if item["file_offset"] == terminal_offset)
                terminal["flow_kind"] = "indirect_branch"
                report = self._verify_resigned_source(project, payload, rom=bytes(rom))
                self.assertFalse(report["verified"], report)
                self.assertTrue(any("frozen candidate" in error for error in report["errors"]), report)

                manifest = json.loads((project / SOURCE_MANIFEST.relative_to(ROOT)).read_text(encoding="utf-8"))
                payload_raw = (project / SOURCE_PAYLOAD.relative_to(ROOT)).read_bytes()
                payload_on_disk = json.loads(payload_raw.decode("utf-8"))
                with mock.patch.multiple(
                    verifier,
                    SOURCE_MANIFEST_SHA256=_sha((project / SOURCE_MANIFEST.relative_to(ROOT)).read_bytes()),
                    SOURCE_PAYLOAD_SHA256=_sha(payload_raw),
                    ROM_SHA256=_sha(bytes(rom)),
                ):
                    code, literal, instructions, _source_claims = verifier._validate_source(
                        bytes(rom), manifest, payload_on_disk, payload_raw
                    )
                    terminal_result = verifier._decode_terminal(bytes(rom), terminal_offset, 397642, 397644, instructions)
                self.assertEqual("indirect_branch", terminal_result["flow_kind"], report)

    def test_indirect_99df4_pseudo_pop_r3_never_becomes_return(self) -> None:
        verifier = _load_verifier()
        terminal_offset = 630260
        predecessor_offset = terminal_offset - 2
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            project = Path(raw) / "project"
            self._copy_project(project)
            rom = bytearray((project / "rom/base.gba").read_bytes())
            pop_r3 = (0xBC08).to_bytes(2, "little")
            rom[predecessor_offset:terminal_offset] = pop_r3
            (project / "rom/base.gba").write_bytes(rom)
            payload = copy.deepcopy(self.source_payload)
            predecessor = next(
                item
                for item in payload["instructions"]
                if item["file_offset"] == predecessor_offset
            )
            predecessor["raw_hex"] = pop_r3.hex()
            predecessor["bytes_sha256"] = _sha(pop_r3)
            predecessor["flow_kind"] = "linear"
            predecessor["successors"] = [
                {
                    "file_offset": terminal_offset,
                    "kind": "fallthrough",
                    "mode": "thumb",
                }
            ]
            code_claim = next(
                item
                for item in payload["coverage_claims"]
                if item["range"][0] <= predecessor_offset < item["range"][1]
            )
            code_start, code_end = code_claim["range"]
            code_claim["sha256"] = _sha(bytes(rom[code_start:code_end]))
            self._resign_source(project, payload)
            manifest_path = project / SOURCE_MANIFEST.relative_to(ROOT)
            payload_path = project / SOURCE_PAYLOAD.relative_to(ROOT)
            payload_raw = payload_path.read_bytes()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload_on_disk = json.loads(payload_raw.decode("utf-8"))
            with mock.patch.multiple(
                verifier,
                SOURCE_MANIFEST_SHA256=_sha(manifest_path.read_bytes()),
                SOURCE_PAYLOAD_SHA256=_sha(payload_raw),
                ROM_SHA256=_sha(bytes(rom)),
            ):
                _code, _literal, instructions, _source_claims = (
                    verifier._validate_source(
                        bytes(rom), manifest, payload_on_disk, payload_raw
                    )
                )
                terminal = verifier._decode_terminal(
                    bytes(rom), terminal_offset, 630262, 630264, instructions
                )
            self.assertEqual("indirect_branch", terminal["flow_kind"])

    def test_symlink_and_path_escape_inputs_fail_closed(self) -> None:
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            temp = Path(raw)
            root_link = temp / "root-link"
            root_link.symlink_to(ROOT, target_is_directory=True)
            self.assertFalse(verifier.verify_root(root_link)["verified"])

            parent_link = temp / "parent-link"
            parent_link.symlink_to(temp, target_is_directory=True)
            self.assertFalse(verifier.verify_root(parent_link / "project")["verified"])

            project = temp / "project"
            self._copy_project(project)
            source_link = project / SOURCE_DIR.relative_to(ROOT)
            real_source = temp / "real-source"
            shutil.copytree(SOURCE_DIR, real_source)
            shutil.rmtree(source_link)
            source_link.symlink_to(real_source, target_is_directory=True)
            report = verifier.verify_root(project)
            self.assertFalse(report["verified"])
            self.assertTrue(any("symlink" in error for error in report["errors"]), report)

            project = temp / "binary-link-project"
            self._copy_project(project)
            binary_path = project / SOURCE_DIR.relative_to(ROOT) / "rom-boot-thumb-handoff-cfg.bin"
            binary_path.unlink()
            binary_path.symlink_to(SOURCE_DIR / "rom-boot-thumb-handoff-cfg.bin")
            report = verifier.verify_root(project)
            self.assertFalse(report["verified"])
            self.assertTrue(any("symlink" in error for error in report["errors"]), report)

            project = temp / "rom-link-project"
            self._copy_project(project)
            rom_path = project / "rom/base.gba"
            rom_path.unlink()
            rom_path.symlink_to(ROM_PATH)
            report = verifier.verify_root(project)
            self.assertFalse(report["verified"])
            self.assertTrue(any("symlink" in error for error in report["errors"]), report)

    def test_report_historical_boundary_and_nonclaims_are_explicit(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertFalse(report["source_artifact_historical_envelope_gaps_classified"])
        self.assertFalse(report["source_wide_envelope_is_claim"])
        self.assertTrue(report["new_packet_additive"])
        expected = {
            "original_artifact_envelope_gaps_classified",
            "complete_boot_runtime",
            "natural_execution_reachability",
            "global_code_or_literal_denominator",
            "indirect_target_resolution",
            "padding",
            "reserved_space",
            "free_or_allocatable_space",
            "editing_or_relocation_safety",
        }
        self.assertEqual(expected, set(report["non_claims"]))
        self.assertTrue(all(value is False for value in report["non_claims"].values()))

    def test_standalone_rows_do_not_pretend_to_verify_live_coverage_owners(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        for row in report["gaps"]:
            for side in (row["left"], row["right"]):
                self.assertNotIn("current_primary_claim_ids", side)
                self.assertNotIn("current_primary_class", side)
                self.assertIn("source_artifact_claim_id", side)
                self.assertIn("source_artifact_semantic_class", side)

    def test_public_verifier_does_not_import_source_exporter_or_use_preflight_coverage(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8") if VERIFIER_PATH.exists() else ""
        if not source:
            self.fail("target verifier is absent (the expected RED condition)")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = ast.unparse(node)
                self.assertNotIn("export_rom_boot_thumb_handoff_cfg", imported)
                self.assertNotIn("verify_rom_boot_thumb_handoff_cfg", imported)
        self.assertNotIn("build/experiments/active/boot-thumb-code-literal-alignment-gap-preflight", source)
        self.assertNotIn("sequel/rom-byte-coverage.json", source)


if __name__ == "__main__":
    unittest.main()
