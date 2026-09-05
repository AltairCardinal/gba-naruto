"""TDD contract for the frozen positions auxiliary dispatch artifact."""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
SCHEMA = "rom-positions-aux-dispatch-v1"
PAYLOAD_NAME = "rom-positions-aux-dispatch.json"
ARTIFACT = ROOT / "artifacts" / SCHEMA
ROM_BASE = 0x08000000
BASE = 0x5461C4
GROUP_COUNT = 48
GROUP_STRIDE = 0x1AAC
VARIANT_COUNT = 3
VARIANT_STRIDE = 0x08E4
CANDIDATE_OFFSET = 0x08A4
CANDIDATE_END_OFFSET = 0x08E4
TABLE_COUNT = 144
BYTES_PER_TABLE = 0x40
CELL_COUNT = 16
CELL_STRIDE = 4
TOTAL_CELLS = 2304
TOTAL_BYTES = 9216
EXPECTED_RANGE_HASH = "47d995f09d6aaafcc4f4b4f88e3fbe81c2c4e0ea48ff10048674f1dbf6847d68"
EXPECTED_PACKED_HASH = "ce2ce373f1699899739903532424f59e89184afa8cd37a527f0adc4ecc8c2c57"
EXPECTED_VECTOR_HASH = "29bee47cef98715a027f5df0ce76c03c03d11dcbd7a84b225e50524e6215d8cb"
EXPECTED_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
EXPECTED_BANK_SHA256 = "1e9d2822e486c6e79c9ad4f1545915fa378505dd1b58e840f939fd1032fd55e9"
EXPECTED_FUNCTION_SHA256 = "bd30b1fd844bd3258666af5dfd739ef42401a1cfcabe680cd09055a6ec4785fd"
EXPECTED_JUMP_TARGETS = [
    0x0806E884,
    0x0806E884,
    0x0806E898,
    0x0806E8C8,
    0x0806E8E4,
    0x0806E8F8,
    0x0806E90C,
]
NON_CLAIMS = {
    "runtime_group_bound_claimed",
    "runtime_variant_bound_claimed",
    "all_variants_naturally_reachable_claimed",
    "all_cells_naturally_reached_claimed",
    "all_tags_naturally_reached_claimed",
    "tag_business_semantics_claimed",
    "byte1_common_semantics_claimed",
    "byte2_common_semantics_claimed",
    "byte3_common_semantics_claimed",
    "byte3_padding_claimed",
    "byte3_reserved_claimed",
    "byte3_globally_unused_claimed",
    "free_space_claimed",
    "allocatable_space_claimed",
    "editing_safety_claimed",
    "writeback_or_relocation_safety_claimed",
    "abi_stability_claimed",
    "next_variant_headers_claimed",
    "final_post_candidate_gap_claimed",
    "existing_position_record_extension_claimed",
    "exhaustive_positions_aux_consumers_claimed",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ranges() -> list[list[int]]:
    return [
        [
            BASE + group * GROUP_STRIDE + variant * VARIANT_STRIDE + CANDIDATE_OFFSET,
            BASE + group * GROUP_STRIDE + variant * VARIANT_STRIDE + CANDIDATE_END_OFFSET,
        ]
        for group in range(GROUP_COUNT)
        for variant in range(VARIANT_COUNT)
    ]


class ExportRomPositionsAuxDispatchTests(unittest.TestCase):
    def _mods(self):
        try:
            from tools import export_rom_positions_aux_dispatch as exporter
            from tools import verify_rom_positions_aux_dispatch as verifier
        except ModuleNotFoundError as error:
            self.fail(f"required product module missing: {error}")
        return exporter, verifier

    def _temporary_artifact(self):
        exporter, _ = self._mods()
        temporary = tempfile.TemporaryDirectory()
        output = Path(temporary.name) / SCHEMA
        exporter.export_artifact(ROOT, output)
        return temporary, output

    def test_exact_denominator_hashes_and_content_counts(self):
        exporter, _ = self._mods()
        payload = exporter.build_payload(ROOT)
        self.assertEqual(SCHEMA, payload["schema"])
        self.assertEqual(
            {
                "table_count": TABLE_COUNT,
                "cell_count": TOTAL_CELLS,
                "byte_count": TOTAL_BYTES,
                "nonzero_byte_count": 699,
                "nonzero_table_count": 71,
                "bytes_per_table": BYTES_PER_TABLE,
                "cells_per_table": CELL_COUNT,
                "cell_stride": CELL_STRIDE,
            },
            payload["summary"],
        )
        self.assertEqual([0x546A68, 0x546AA8], payload["tables"][0]["range"])
        self.assertEqual([0x5961C4, 0x596204], payload["tables"][-1]["range"])
        self.assertEqual(_ranges(), payload["range_denominator"])
        self.assertEqual(EXPECTED_RANGE_HASH, payload["range_list_sha256"])
        self.assertEqual(EXPECTED_PACKED_HASH, payload["packed_range_bytes_sha256"])
        self.assertEqual(EXPECTED_VECTOR_HASH, payload["per_range_sha256_vector_sha256"])
        self.assertEqual(144, len(payload["per_range_sha256_vector"]))
        self.assertEqual(699, payload["byte_counts"]["nonzero_bytes"])
        self.assertEqual(71, payload["byte_counts"]["nonzero_tables"])

    def test_owner_boundaries_and_final_gap_are_exact(self):
        exporter, _ = self._mods()
        tables = exporter.build_payload(ROOT)["tables"]
        self.assertEqual(144, len(tables))
        self.assertEqual(
            {
                "id": "bank-positions-000",
                "range": [BASE + 4, BASE + CANDIDATE_OFFSET],
            },
            tables[0]["left_owner"],
        )
        self.assertEqual(
            {
                "id": "bank-positions-001",
                "range": [BASE + VARIANT_STRIDE + 4, BASE + VARIANT_STRIDE + CANDIDATE_OFFSET],
            },
            tables[0]["right_positions_owner"],
        )
        self.assertEqual([0x546AA8, 0x546AAC], tables[0]["next_header_range"])
        self.assertFalse(tables[0]["right_owner_adjacent"])
        for ordinal, row in enumerate(tables[:-1]):
            candidate_end = row["range"][1]
            self.assertEqual([candidate_end, candidate_end + 4], row["next_header_range"])
            self.assertEqual(f"bank-positions-{ordinal + 1:03d}", row["right_positions_owner"]["id"])
            self.assertEqual(candidate_end + 4, row["right_positions_owner"]["range"][0])
            self.assertEqual(CANDIDATE_OFFSET - 4, row["left_owner"]["range"][1] - row["base"] - 4)
            self.assertFalse(row["right_owner_adjacent"])
        last = tables[-1]
        self.assertIsNone(last["next_header_range"])
        self.assertIsNone(last["right_positions_owner"])
        self.assertFalse(last["right_owner_adjacent"])
        self.assertEqual(
            {
                "range": [0x596204, 0x596D5C],
                "size": 0xB58,
                "next_owner": {
                    "id": "character-battle-visual-descriptor_table-596d5c",
                    "range": [0x596D5C, 0x59903C],
                },
            },
            last["final_post_candidate_boundary"],
        )

    def test_exact_consumer_literals_jump_table_and_instruction_semantics(self):
        exporter, verifier = self._mods()
        rom = ROM_PATH.read_bytes()
        semantics = exporter.decode_consumer_contract(rom)
        independent = verifier.independent_consumer_contract(rom)
        self.assertEqual(semantics, independent)
        self.assertEqual(EXPECTED_FUNCTION_SHA256, semantics["function"]["sha256"])
        self.assertEqual(
            {
                "group_source": 0x02026804 + 1,
                "variant_source": 0x02026804 + 2,
                "base": 0x085461C4,
                "group_stride": GROUP_STRIDE,
                "variant_stride": VARIANT_STRIDE,
                "cell_stride": CELL_STRIDE,
                "candidate_offset": CANDIDATE_OFFSET,
                "scan_count": CELL_COUNT,
                "formula": "r4 = base + group*group_stride + variant*variant_stride + index*cell_stride + candidate_offset",
            },
            semantics["address_equation"],
        )
        self.assertEqual(EXPECTED_JUMP_TARGETS, semantics["dispatch"]["jump_targets"])
        self.assertEqual(0x0806E868, semantics["dispatch"]["jump_table_address"])
        self.assertEqual(list(range(1, 8)), semantics["dispatch"]["accepted_selector_values"])
        self.assertEqual([0x06E886, 0x06E898, 0x06E8AA, 0x06E8C8, 0x06E8D8, 0x06E8E6, 0x06E8FA, 0x06E90E, 0x06E926], semantics["read_footprint"]["byte1"]["instruction_offsets"])
        self.assertEqual([0x06E88A, 0x06E8DC, 0x06E8EA, 0x06E8FE, 0x06E916, 0x06E92A, 0x06E938], semantics["read_footprint"]["byte2"]["instruction_offsets"])
        self.assertEqual([0x06E88C, 0x06E8DE, 0x06E8EC, 0x06E900, 0x06E918, 0x06E92C, 0x06E93A], semantics["read_footprint"]["byte3"]["instruction_offsets"])

    def test_cells_preserve_raw_handler_operands_without_shared_meaning(self):
        exporter, _ = self._mods()
        payload = exporter.build_payload(ROOT)
        table = payload["tables"][0]
        self.assertEqual(16, len(table["cells"]))
        for index, cell in enumerate(table["cells"]):
            self.assertEqual(index, cell["index"])
            self.assertEqual(4, cell["range"][1] - cell["range"][0])
            raw = bytes.fromhex(cell["raw_hex"])
            self.assertEqual(4, len(raw))
            self.assertEqual(raw[0], cell["byte0_dispatch_selector"])
            self.assertEqual(raw[1], cell["byte1_raw_handler_operand"])
            self.assertEqual(raw[2], cell["byte2_raw_handler_operand"])
            self.assertEqual(raw[3], cell["byte3_raw_handler_operand"])
        self.assertEqual(
            {"byte0_dispatch_selector", "byte1_raw_handler_operand", "byte2_raw_handler_operand", "byte3_raw_handler_operand"},
            set(payload["scope"]["read_footprint"]),
        )
        self.assertEqual(NON_CLAIMS, set(payload["non_claims"]))
        self.assertTrue(all(value is False for value in payload["non_claims"].values()))

    def test_deterministic_export_and_safe_output_validation(self):
        exporter, _ = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            exporter.export_artifact(ROOT, first)
            exporter.export_artifact(ROOT, second)
            first_hashes = {
                p.relative_to(first): _sha(p.read_bytes())
                for p in first.rglob("*")
                if p.is_file()
            }
            second_hashes = {
                p.relative_to(second): _sha(p.read_bytes())
                for p in second.rglob("*")
                if p.is_file()
            }
            self.assertEqual(first_hashes, second_hashes)
            foreign = root / "foreign"
            foreign.mkdir()
            (foreign / "keep").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign"):
                exporter.export_artifact(ROOT, foreign)
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.export_artifact(ROOT, linked / "artifact")
        with self.assertRaisesRegex(ValueError, "repository root"):
            exporter.export_artifact(ROOT, ROOT)
        with self.assertRaisesRegex(ValueError, "ancestor"):
            exporter.export_artifact(ROOT, ROOT.parent)

    def test_independent_verifier_rebuilds_canonical_and_cli_is_deterministic(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            exporter.export_artifact(ROOT, output)
            first = verifier.verify_artifact(ROOT, output)
            second = verifier.verify_artifact(ROOT, output)
            self.assertEqual(first, second)
            self.assertTrue(first["verified"], first["errors"])
            self.assertEqual("rom-positions-aux-dispatch-verification-v1", first["schema"])
            self.assertEqual([], first["errors"])
            command = [
                "python3",
                "tools/verify_rom_positions_aux_dispatch.py",
                "--root",
                str(ROOT),
                "--artifact-dir",
                str(output),
            ]
            first_cli = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
            second_cli = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertEqual(first_cli.stdout, second_cli.stdout)
            self.assertTrue(json.loads(first_cli.stdout)["verified"])
        source = (ROOT / "tools/verify_rom_positions_aux_dispatch.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        imported = "\n".join(ast.unparse(node) for node in imports)
        self.assertNotIn("export_rom_positions_aux_dispatch", imported)
        self.assertNotIn("extract_positions", source)

    def test_failures_cover_missing_foreign_and_symlink_inputs(self):
        _, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = verifier.verify_artifact(root, root / "missing")
            self.assertFalse(missing["verified"])
            self.assertTrue(missing["errors"])
            outside = root / "outside"
            outside.mkdir()
            linked = root / "linked"
            linked.symlink_to(outside, target_is_directory=True)
            report = verifier.verify_artifact(ROOT, linked)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "artifact"
            path.mkdir()
            (path / "manifest.json").write_text("{}\n", encoding="utf-8")
            (path / "extra").write_text("x", encoding="utf-8")
            report = verifier.verify_artifact(ROOT, path)
            self.assertFalse(report["verified"])
            self.assertTrue(any("artifact" in error or "file" in error or "schema" in error for error in report["errors"]))

    def test_payload_manifest_and_cell_mutations_are_rejected(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / SCHEMA
            exporter.export_artifact(ROOT, artifact)
            payload_path = artifact / PAYLOAD_NAME
            manifest_path = artifact / "manifest.json"
            original_payload = _json(payload_path)
            original_manifest = _json(manifest_path)

            def rewrite(value):
                payload_path.write_text(
                    json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

            def restore_payload():
                rewrite(original_payload)

            def assert_rejected(value):
                rewrite(value)
                self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])
                restore_payload()

            mutated = json.loads(json.dumps(original_payload))
            mutated["tables"][0]["range"][0] += 1
            assert_rejected(mutated)

            mutated = json.loads(json.dumps(original_payload))
            mutated["tables"][0]["cells"][0]["raw_hex"] = "ff000000"
            assert_rejected(mutated)

            mutated = json.loads(json.dumps(original_payload))
            mutated["non_claims"]["byte3_common_semantics_claimed"] = True
            assert_rejected(mutated)

            for mutation in (
                lambda value: value["tables"].pop(),
                lambda value: value["tables"].append(json.loads(json.dumps(value["tables"][-1]))),
                lambda value: value["tables"].reverse(),
                lambda value: value["tables"][0]["cells"].pop(),
                lambda value: value["tables"][0]["cells"].append(json.loads(json.dumps(value["tables"][0]["cells"][-1]))),
                lambda value: value["tables"][0]["cells"].reverse(),
                lambda value: value["tables"][0]["left_owner"]["range"].__setitem__(0, BASE + 5),
                lambda value: value["tables"][0].__setitem__("sha256", "0" * 64),
            ):
                mutated = json.loads(json.dumps(original_payload))
                mutation(mutated)
                assert_rejected(mutated)

            mutated = json.loads(json.dumps(original_payload))
            mutated["range_list_sha256"] = "0" * 64
            assert_rejected(mutated)

            manifest = json.loads(json.dumps(original_manifest))
            del manifest["files"][PAYLOAD_NAME]
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])
            manifest_path.write_text(json.dumps(original_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifest = json.loads(json.dumps(original_manifest))
            manifest["files"][PAYLOAD_NAME] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

    def test_deep_consumer_mutations_are_rejected_by_both_decoders(self):
        exporter, verifier = self._mods()
        rom = bytearray(ROM_PATH.read_bytes())
        mutation_offsets = [
            0x06E818,
            0x06E820,
            0x06E822,
            0x06E846,
            0x06E840,
            0x06E848,
            0x06E86C,
            0x06E886,
            0x06E88A,
            0x06E88C,
        ]
        for offset in mutation_offsets:
            mutated = bytearray(rom)
            mutated[offset] ^= 0x01
            with self.subTest(offset=hex(offset)):
                with self.assertRaises(ValueError):
                    exporter.decode_consumer_contract(bytes(mutated))
                with self.assertRaises(ValueError):
                    verifier.independent_consumer_contract(bytes(mutated))

    def test_semantic_decoder_error_matrix_closes_every_frozen_mutation(self):
        exporter, verifier = self._mods()
        original = ROM_PATH.read_bytes()
        literal_loads = [
            (0x06E816, r"(?i)wram context literal"),
            (0x06E81A, r"(?i)group stride literal"),
            (0x06E822, r"(?i)variant stride literal"),
            (0x06E826, r"(?i)positions base literal"),
            (0x06E82E, r"(?i)candidate offset literal"),
            (0x06E848, r"(?i)jump[- ]table literal"),
        ]
        literal_words = [
            (0x06E850, r"(?i)wram context literal"),
            (0x06E854, r"(?i)group stride literal"),
            (0x06E858, r"(?i)variant stride literal"),
            (0x06E85C, r"(?i)positions base literal"),
            (0x06E860, r"(?i)candidate offset literal"),
            (0x06E864, r"(?i)jump[- ]table literal"),
        ]
        instruction_cases = [
            (0x06E818, r"(?i)group byte load"),
            (0x06E820, r"(?i)variant byte load"),
            (0x06E81C, r"(?i)group move"),
            (0x06E81E, r"(?i)group multiply"),
            (0x06E824, r"(?i)variant multiply"),
            (0x06E828, r"(?i)variant addition"),
            (0x06E82A, r"(?i)group addition"),
            (0x06E82C, r"(?i)(index base addition|index base)"),
            (0x06E830, r"(?i)candidate addition"),
            (0x06E832, r"(?i)cell address formation"),
            (0x06E846, r"(?i)(index scale|index times four)"),
            (0x06E836, r"(?i)(first byte-zero load|byte-zero load)"),
            (0x06E83A, r"(?i)dispatch byte-zero load"),
            (0x06E83C, r"(?i)selector decrement"),
            (0x06E840, r"(?i)selector bound"),
            (0x06E842, r"(?i)(unsigned (selector )?branch|selector branch)"),
            (0x06E844, r"(?i)(default (selector )?branch|selector branch)"),
            (0x06E84A, r"(?i)dispatch table addition"),
            (0x06E84C, r"(?i)dispatch table (load|load)"),
            (0x06E84E, r"(?i)dispatch indirect jump"),
            (0x06E814, r"(?i)index (initialization|initialization)"),
            (0x06E944, r"(?i)loop (index )?increment"),
            (0x06E946, r"(?i)loop .*truncation left"),
            (0x06E948, r"(?i)loop .*truncation right"),
            (0x06E94A, r"(?i)loop bound"),
            (0x06E94C, r"(?i)loop stop branch"),
            (0x06E94E, r"(?i)loop back branch"),
        ]
        handler_cases = (
            [(offset, r"(?i)handler byte 1") for offset in (0x06E886, 0x06E898, 0x06E8AA, 0x06E8C8, 0x06E8D8, 0x06E8E6, 0x06E8FA, 0x06E90E, 0x06E926)]
            + [(offset, r"(?i)handler byte 2") for offset in (0x06E88A, 0x06E8DC, 0x06E8EA, 0x06E8FE, 0x06E916, 0x06E92A, 0x06E938)]
            + [(offset, r"(?i)handler byte 3") for offset in (0x06E88C, 0x06E8DE, 0x06E8EC, 0x06E900, 0x06E918, 0x06E92C, 0x06E93A)]
        )
        jump_payload_cases = [
            (0x06E868 + index * 4, r"(?i)jump table") for index in range(7)
        ]

        def assert_category(offset, pattern):
            mutated = bytearray(original)
            mutated[offset] ^= 0x01
            for decoder in (exporter.decode_consumer_contract, verifier.independent_consumer_contract):
                with self.subTest(offset=hex(offset), pattern=pattern, decoder=decoder.__module__):
                    with self.assertRaisesRegex(ValueError, pattern):
                        decoder(bytes(mutated))

        for offset, pattern in literal_loads + literal_words + instruction_cases + list(handler_cases) + jump_payload_cases:
            assert_category(offset, pattern)

    def test_full_rom_size_synthetic_slice_decodes_then_mutation_fails_semantically(self):
        exporter, verifier = self._mods()
        original = ROM_PATH.read_bytes()
        synthetic = bytearray(b"\xA5" * len(original))
        synthetic[0x06E810:0x06E958] = original[0x06E810:0x06E958]
        exporter_result = exporter.decode_consumer_contract(bytes(synthetic))
        verifier_result = verifier.independent_consumer_contract(bytes(synthetic))
        self.assertEqual(exporter_result, verifier_result)
        mutated = bytearray(synthetic)
        mutated[0x06E83C] ^= 0x01
        for decoder in (exporter.decode_consumer_contract, verifier.independent_consumer_contract):
            with self.assertRaisesRegex(ValueError, r"(?i)selector decrement"):
                decoder(bytes(mutated))

    def test_verifier_forbids_borrowed_builders_and_coverage_auditors(self):
        source = (ROOT / "tools/verify_rom_positions_aux_dispatch.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_text = (
            "export_rom_positions_aux_dispatch",
            "extract_positions",
            "audit_rom_byte_coverage",
            "audit_reverse_engineering_proof",
            "coverage_auditor",
        )
        private_builder_names = {
            "_derive",
            "_table_rows",
            "_decode_consumer_semantics",
            "_byte_distributions",
            "_implementation",
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = ast.unparse(node)
                self.assertFalse(any(name in imported for name in forbidden_text))
            if isinstance(node, ast.Call):
                called = ast.unparse(node.func)
                self.assertNotIn("export_rom_positions_aux_dispatch", called)
                callee_name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else called
                self.assertNotIn(callee_name, private_builder_names)
        for token in forbidden_text[1:]:
            self.assertNotIn(token, source)

    def test_physically_deleted_payload_and_manifest_fail_then_restore(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / SCHEMA
            exporter.export_artifact(ROOT, artifact)
            payload_path = artifact / PAYLOAD_NAME
            manifest_path = artifact / "manifest.json"
            payload_bytes = payload_path.read_bytes()
            manifest_bytes = manifest_path.read_bytes()
            payload_path.unlink()
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])
            payload_path.write_bytes(payload_bytes)
            self.assertTrue(verifier.verify_artifact(ROOT, artifact)["verified"])
            manifest_path.unlink()
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])
            manifest_path.write_bytes(manifest_bytes)
            restored = verifier.verify_artifact(ROOT, artifact)
            self.assertTrue(restored["verified"], restored["errors"])


if __name__ == "__main__":
    unittest.main()
