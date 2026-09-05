"""Contract tests for the independent Cutscene OBJ palette-gap verifier."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
VERIFIER_PATH = ROOT / "tools/verify_rom_cutscene_obj_palette_definition_alignment_gaps.py"

VERIFY_SCHEMA = "rom-cutscene-obj-palette-definition-alignment-gaps-verification-v1"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
RESOURCE_TABLE_SHA256 = "16b13c432f37ba159697cd9d9d6d5d5147adc41c44c8cc0cc44ce7f2935f1401"
SPRITE_TABLE_SHA256 = "1c76f2100b2067e78abd713e312bd845d7c874b030f51ef08f968961862e198a"
COMBINED_TABLE_SHA256 = "1e6d5016b58d0e565c5a40791a7f2684d6129e0a1c4e85e79317af4d2b1a7f62"
RANGE_VECTOR_SHA256 = "374c247199713cc2e172ebff551ae7a5e40df4289437f45cf76c814e84bed5e6"
BOUNDARY_VECTOR_SHA256 = "779dae0d0811b3cde7817d9de9c0c61c35e7d9c54e5d2f9ecfd99eb0a80b211d"
PACKED_BYTES_SHA256 = "af5570f5a1810b7af78caf4bc70a660f0df51e42baf91d4de5b2328de0e83dfc"
COMPRESSED_STREAM_SHA256 = "6bdf4b41b3d1b6240499cb68ceddb82a6e98267709f05d075bc64389956681c2"
DECODED_STREAM_SHA256 = "99d45ddc5929d60c150146f1292cd55f56d89afbff70ffd0f377128fe75352af"
ROOT_ROW_VECTOR_SHA256 = "8a0ab99bbb46e1fa58a0413ffae366bd67a3660e5f947b043228858688899e2d"

RANGES = (
    (0x12DEFA, 0x12DEFC),
    (0x12E442, 0x12E444),
    (0x12E95E, 0x12E960),
    (0x12ED6E, 0x12ED70),
)
PALETTE_OFFSETS = (0x12DEE4, 0x12E42C, 0x12E948, 0x12ED58)
ROOT_TABLE_OFFSET = 0x53DF70
SPRITE_TABLE_OFFSET = 0x53DF90
DEFINITION_TABLE_OFFSETS = (0x12DF2C, 0x12E474, 0x12E990, 0x12EDD0)

ROOT_ROWS = (
    (0x0812D9E4, 0x0812DEE4, 0x0812DF2C, 0x0812DF44),
    (0x0812DF4C, 0x0812E42C, 0x0812E474, 0x0812E48C),
    (0x0812E494, 0x0812E948, 0x0812E990, 0x0812E9A8),
    (0x0812E9B0, 0x0812ED58, 0x0812EDD0, 0x0812EE00),
)
FIRST_DEFINITION_POINTERS = (0x0812DEFC, 0x0812E444, 0x0812E960, 0x0812ED70)
TERMINATOR = bytes.fromhex("ffff0000")
FIRST_RECORDS = (
    bytes.fromhex("00000000e0ffe0ff4000400000010001ff000000ffff0000"),
    bytes.fromhex("00000000e0ffe0ff4000400000010001ff000000ffff0000"),
    bytes.fromhex("00000000e0ffe0ff4000400000010001ff000000ffff0000"),
    bytes.fromhex("00000000f0fff0ff2000200000010001ff000000ffff0000"),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_verifier():
    try:
        return importlib.import_module(
            "tools.verify_rom_cutscene_obj_palette_definition_alignment_gaps"
        )
    except ModuleNotFoundError as error:
        raise AssertionError(
            "target verifier module is absent (the expected RED condition)"
        ) from error


class CutsceneObjPaletteDefinitionAlignmentGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()

    def _verify_bytes(self, raw: bytes, **patches):
        verifier = _load_verifier()
        with mock.patch.object(verifier, "ROM_SHA256", _sha(raw)):
            if patches:
                with mock.patch.multiple(verifier, **patches):
                    return verifier.verify_rom_bytes(raw)
            return verifier.verify_rom_bytes(raw)

    def test_exact_denominator_vectors_hashes_and_ordered_report(self):
        verifier = _load_verifier()
        report = verifier.verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(report["schema"], VERIFY_SCHEMA)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["gap_count"], 4)
        self.assertEqual(report["byte_count"], 8)
        self.assertEqual(report["zero_byte_count"], 8)
        self.assertEqual(report["left_lz_count"], 4)
        self.assertEqual(report["right_definition_count"], 4)
        self.assertEqual(report["ranges"], [list(pair) for pair in RANGES])
        self.assertEqual(report["range_vector_sha256"], RANGE_VECTOR_SHA256)
        self.assertEqual(report["boundary_vector_sha256"], BOUNDARY_VECTOR_SHA256)
        self.assertEqual(report["packed_bytes_sha256"], PACKED_BYTES_SHA256)
        self.assertEqual(report["resource_table_sha256"], RESOURCE_TABLE_SHA256)
        self.assertEqual(report["sprite_table_sha256"], SPRITE_TABLE_SHA256)
        self.assertEqual(report["combined_table_sha256"], COMBINED_TABLE_SHA256)
        self.assertEqual(report["root_row_vector_sha256"], ROOT_ROW_VECTOR_SHA256)
        self.assertEqual(report["compressed_stream_sha256"], COMPRESSED_STREAM_SHA256)
        self.assertEqual(report["decoded_stream_sha256"], DECODED_STREAM_SHA256)
        self.assertTrue(report["all_parser_endpoints_exact"])
        self.assertTrue(report["all_alignment_equations_hold"])
        resources = report["resources"]
        self.assertEqual([row["resource_id"] for row in resources], [0, 1, 2, 3])
        self.assertEqual(
            [row["gap_range"] for row in resources],
            [list(pair) for pair in RANGES],
        )
        self.assertEqual(
            [row["first_definition_pointer"] for row in resources],
            [f"0x{pointer:08X}" for pointer in FIRST_DEFINITION_POINTERS],
        )

    def test_root_tables_slot_zero_lz_endpoints_alignment_gaps_and_terminators(self):
        verifier = _load_verifier()
        report = verifier.verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        for index, row in enumerate(report["resources"]):
            self.assertEqual(row["root"]["resource_row"], list(ROOT_ROWS[index][:2]))
            self.assertEqual(row["root"]["sprite_row"], list(ROOT_ROWS[index][2:]))
            self.assertEqual(row["root"]["first_definition_pointer"], FIRST_DEFINITION_POINTERS[index])
            self.assertEqual(row["palette_pointer"], f"0x{PALETTE_OFFSETS[index] + 0x08000000:08X}")
            self.assertEqual(row["parser_end"], RANGES[index][0])
            self.assertEqual(row["gap_start"], RANGES[index][0])
            self.assertEqual(row["gap_end"], RANGES[index][1])
            self.assertEqual(row["gap_size"], 2)
            self.assertEqual(row["gap_raw_hex"], "0000")
            self.assertEqual(row["first_definition_size"], 24)
            self.assertEqual(row["first_definition_raw_hex"], FIRST_RECORDS[index].hex())
            self.assertEqual(row["first_definition_terminator_hex"], TERMINATOR.hex())
            self.assertTrue(row["first_definition_terminator_exact"])
            self.assertEqual(row["component_stride_bytes"], 20)
            self.assertTrue(row["gap_start_equals_parser_end"])
            self.assertTrue(row["gap_end_equals_aligned_parser_end"])
            self.assertTrue(row["slot_0_equals_aligned_parser_end"])

    def test_cli_success_has_one_deterministic_json_report(self):
        command = [
            sys.executable,
            "-u",
            "tools/verify_rom_cutscene_obj_palette_definition_alignment_gaps.py",
            "--root",
            str(ROOT),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            env={"PYTHONDONTWRITEBYTECODE": "1", **dict(__import__("os").environ)},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(completed.stdout.splitlines()), 1)
        report = json.loads(completed.stdout)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(report, _load_verifier().verify_root(ROOT))

    def test_wrong_missing_out_of_tree_and_symlink_roots_or_rom_fail_closed(self):
        verifier = _load_verifier()
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as raw:
            temp = Path(raw)
            self.assertFalse(verifier.verify_root(temp / "missing")["verified"])
            self.assertFalse(verifier.verify_root(temp)["verified"])

            project = temp / "project"
            (project / "tools").mkdir(parents=True)
            (project / "tests").mkdir()
            (project / "rom").mkdir()
            (project / "rom/base.gba").write_bytes(b"wrong")
            wrong = verifier.verify_root(project)
            self.assertFalse(wrong["verified"])
            self.assertTrue(wrong["errors"])

            symlink_root = temp / "root-link"
            symlink_root.symlink_to(ROOT, target_is_directory=True)
            self.assertFalse(verifier.verify_root(symlink_root)["verified"])

            linked_rom_project = temp / "linked-rom"
            (linked_rom_project / "tools").mkdir(parents=True)
            (linked_rom_project / "tests").mkdir()
            (linked_rom_project / "rom").mkdir()
            (linked_rom_project / "rom/base.gba").symlink_to(ROM_PATH)
            linked = verifier.verify_root(linked_rom_project)
            self.assertFalse(linked["verified"])
            self.assertTrue(any("symlink" in error for error in linked["errors"]))

    def test_gap_bytes_fail_after_resigning_shallow_rom_and_packed_identity(self):
        verifier = _load_verifier()
        data = bytearray(self.rom)
        for start, _ in RANGES:
            data[start] = 1
        packed = b"".join(data[start:end] for start, end in RANGES)
        report = self._verify_bytes(bytes(data), PACKED_BYTES_SHA256=_sha(packed))
        self.assertFalse(report["verified"])
        self.assertTrue(any("zero" in error or "gap" in error for error in report["errors"]))

    def test_lz_header_flags_and_back_reference_fail_in_parser_not_only_rom_hash(self):
        verifier = _load_verifier()
        mutations = {
            "header": lambda data, start: data.__setitem__(start, 0x11),
            "flags": lambda data, start: data.__setitem__(start + 4, 0x80),
            "back-reference": lambda data, start: data.__setitem__(start + 18, 0xFF),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                data = bytearray(self.rom)
                for start in PALETTE_OFFSETS:
                    mutate(data, start)
                stream_sha = _sha(bytes(data[PALETTE_OFFSETS[0] : PALETTE_OFFSETS[0] + 22]))
                report = self._verify_bytes(
                    bytes(data), COMPRESSED_STREAM_SHA256=stream_sha
                )
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any(
                        marker in error
                        for error in report["errors"]
                        for marker in ("LZ", "header", "back-reference", "flags", "compressed")
                    ),
                    report["errors"],
                )

    def test_resource_and_sprite_root_pointer_mutations_fail_after_resigning_table_hashes(self):
        for name, table_offset, patch_name in (
            ("resource", ROOT_TABLE_OFFSET + 4, "RESOURCE_TABLE_SHA256"),
            ("sprite", SPRITE_TABLE_OFFSET, "SPRITE_TABLE_SHA256"),
        ):
            with self.subTest(table=name):
                data = bytearray(self.rom)
                data[table_offset] ^= 4
                resource_sha = _sha(bytes(data[ROOT_TABLE_OFFSET:SPRITE_TABLE_OFFSET]))
                sprite_sha = _sha(bytes(data[SPRITE_TABLE_OFFSET : SPRITE_TABLE_OFFSET + 0x20]))
                patches = {
                    "RESOURCE_TABLE_SHA256": resource_sha,
                    "SPRITE_TABLE_SHA256": sprite_sha,
                    "COMBINED_TABLE_SHA256": _sha(bytes(data[ROOT_TABLE_OFFSET : SPRITE_TABLE_OFFSET + 0x20])),
                }
                report = self._verify_bytes(bytes(data), **patches)
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any("pointer" in error or "root" in error for error in report["errors"]),
                    report["errors"],
                )

    def test_slot_zero_pointer_mutation_hits_alignment_binding(self):
        data = bytearray(self.rom)
        struct.pack_into("<I", data, DEFINITION_TABLE_OFFSETS[0], 0x0812DF00)
        report = self._verify_bytes(bytes(data))
        self.assertFalse(report["verified"])
        self.assertTrue(
            any("slot" in error or "aligned" in error or "definition pointer" in error for error in report["errors"]),
            report["errors"],
        )

    def test_first_definition_terminator_mutation_hits_terminator_semantics(self):
        verifier = _load_verifier()
        data = bytearray(self.rom)
        data[FIRST_DEFINITION_POINTERS[0] - 0x08000000 + 23] ^= 1
        expected_hashes = list(verifier.DEFINITION_RECORD_SHA256)
        expected_hashes[0] = _sha(bytes(data[0x12DEFC : 0x12DF14]))
        report = self._verify_bytes(
            bytes(data), DEFINITION_RECORD_SHA256=tuple(expected_hashes)
        )
        self.assertFalse(report["verified"])
        self.assertTrue(any("terminator" in error for error in report["errors"]), report["errors"])

    def test_denominator_expected_vector_and_non_claim_drift_fail_closed(self):
        verifier = _load_verifier()
        with mock.patch.object(verifier, "RANGE_VECTOR_SHA256", "0" * 64):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(any("range vector" in error for error in report["errors"]))

        bad_rows = list(verifier.EXPECTED_ROOT_ROWS)
        bad_rows[0] = tuple(bad_rows[0][:-1]) + (0x0812DEFC,)
        with mock.patch.object(verifier, "EXPECTED_ROOT_ROWS", tuple(bad_rows)):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(any("pointer" in error for error in report["errors"]))

        bad_claims = dict(verifier.NON_CLAIMS)
        bad_claims["free_space_claimed"] = True
        with mock.patch.object(verifier, "NON_CLAIMS", bad_claims):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(any("non-claim" in error for error in report["errors"]))

    def test_all_non_claims_are_false_in_report_and_each_resource(self):
        report = _load_verifier().verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        expected = {
            "allocatable_space_claimed",
            "free_space_claimed",
            "editing_safety_claimed",
            "writeback_or_relocation_safety_claimed",
            "runtime_consumes_padding_claimed",
            "natural_runtime_reachability_claimed",
            "final_pixel_equivalence_claimed",
            "definition_unknown_field_semantics_claimed",
            "graphics_or_palette_expansion_claimed",
            "all_cutscene_gaps_exhaustive_claimed",
            "generic_lz_alignment_rule_claimed",
            "lz_trailing_bytes_claimed",
            "compiler_authorship_claimed",
        }
        self.assertEqual(set(report["non_claims"]), expected)
        self.assertTrue(all(value is False for value in report["non_claims"].values()))
        for row in report["resources"]:
            self.assertTrue(all(row[name] is False for name in expected))

    def test_static_source_has_no_existing_cutscene_exporter_or_verifier_dependency(self):
        if not VERIFIER_PATH.is_file():
            self.fail("target verifier module is absent (the expected RED condition)")
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        banned = (
            "export_rom_cutscene_obj_source_ranges",
            "verify_rom_cutscene_obj_source_ranges",
            "verify_cutscene_obj_export",
            "export_cutscene_obj_assets",
            "build_payload",
            "_resource_tables",
        )
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = ast.unparse(node)
                self.assertFalse(any(name in imported for name in banned), imported)
        self.assertFalse(any(name in source for name in banned), source)


if __name__ == "__main__":
    unittest.main()
