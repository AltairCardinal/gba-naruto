"""TDD contract tests for the frozen u8-indexed u8-triplet lookup candidate."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ROOT = ROOT / "build/experiments/active/rom-u8-indexed-u8-triplet-lookup"
ROM_PATH = ROOT / "rom/base.gba"
SCHEMA = "rom-u8-indexed-u8-triplet-lookup-v1"
VERIFY_SCHEMA = "rom-u8-indexed-u8-triplet-lookup-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
JSON_NAME = "rom-u8-indexed-u8-triplet-lookup.json"
BIN_NAME = "rom-u8-indexed-u8-triplet-lookup.bin"
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_RANGE = [0x53DFB0, 0x53DFBF]
TABLE_GBA_RANGE = ["0x0853DFB0", "0x0853DFBF"]
TABLE_SHA256 = "d9f09635484acda7178a3c3661cacb5857338798c5dd87058fe5c7d8a17c3ef3"
TABLE_RAW_HEX = "09080a09050b0c0c0d10101110ff12"
RECORDS = ["09080a", "09050b", "0c0c0d", "101011", "10ff12"]
POINTER_RANGE = [0x75C0C, 0x75C10]
POINTER_GBA_RANGE = ["0x08075C0C", "0x08075C10"]
POINTER_RAW_HEX = "b0df5308"
POINTER_VALUE = 0x0853DFB0
POINTER_SHA256 = "94ed1b299bbef8b78e0b6e7e6afab5cec9dada3516e48cf04e104ccdd689262e"
POINTER_OCCURRENCES = [0x75C0C]
POINTER_OCCURRENCE_VECTOR_SHA256 = "ce055d1c77a9bf59940c7f367a1c66973425d7a2c7c95782150fc261f9af159a"
ENVELOPE_RANGE = [0x75BD2, 0x75D10]
ENVELOPE_SHA256 = "00ad2e10053d53e5d4f96d28fc2f327a4bf6d143ad44718ff84195d246263d6b"
CODE_RANGES = [
    [0x75BD2, 0x75BFE],
    [0x75C10, 0x75C5E],
    [0x75C68, 0x75C98],
    [0x75CA4, 0x75CB6],
    [0x75CBC, 0x75D10],
]
CODE_SIZE = 272
CODE_SHA256 = "203f476edad477eb359e84d625ca079f2a7aba161e5f2a2266c83cc31f3e6529"
BLOCK_COUNT = 28
INSTRUCTION_COUNT = 134
FRONTIER_COUNT = 0
BLOCK_VECTOR_SHA256 = "91225206f466857eae0f8e6d6718b1c7020dcd824344793cf2e8ba79944afe5d"
POOL_RANGES = [
    [0x75BFE, 0x75C10],
    [0x75C5E, 0x75C68],
    [0x75C98, 0x75CA4],
    [0x75CB6, 0x75CBC],
]
RIGHT_UNKNOWN_RANGE = [0x53DFBF, 0x53E000]
RIGHT_UNKNOWN_SHA256 = "3649f772a191366cf911ca8eb6b9e28e902a79e4a19607a5ac340cd64d818849"
COVERAGE_SHA256 = "5432e12ff0aa9bd2722f7e18e169ac0d82d67f6a1afd4601a8d0011e502eba89"
COVERAGE_SIZE = 23_020_449
PROMOTION_RANGES = [[0x75C0C, 0x75C10], [0x53DFB0, 0x53DFBF]]
PROMOTION_RANGE_VECTOR_SHA256 = "99af22b0af2f42931bb29c3cbe187ff8836b1f651504eea40a45eb5be108d87f"
PROMOTION_PACKED_SHA256 = "4439669abd06a2c350f23e705c750821694c15e2f92a083bc00c89ab7506dcc6"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _temporary_experiment_dir():
    EXPERIMENT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=EXPERIMENT_ROOT)


def _load_modules():
    try:
        exporter = importlib.import_module("tools.export_rom_u8_indexed_u8_triplet_lookup")
        verifier = importlib.import_module("tools.verify_rom_u8_indexed_u8_triplet_lookup")
    except ModuleNotFoundError:
        return None, None
    return exporter, verifier


class ExportRomU8IndexedU8TripletLookupTests(unittest.TestCase):
    def _implemented(self):
        exporter, verifier = _load_modules()
        self.assertIsNotNone(
            exporter,
            "u8-indexed u8-triplet lookup exporter implementation is absent",
        )
        self.assertIsNotNone(
            verifier,
            "u8-indexed u8-triplet lookup verifier implementation is absent",
        )
        return exporter, verifier

    def test_red_contract_requires_missing_exporter_and_verifier_implementation(self):
        """The first RED must fail for the intended reason: no product modules yet."""
        exporter, verifier = _load_modules()
        self.assertIsNotNone(exporter, "RED: exporter module is not implemented")
        self.assertIsNotNone(verifier, "RED: verifier module is not implemented")

    def test_exact_table_pointer_and_consumer_contract(self):
        exporter, _ = self._implemented()
        payload, bundle = exporter.build_payload(ROOT)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(
            payload["rom"],
            {"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256},
        )
        table = payload["table"]
        self.assertEqual(table["file_range"], TABLE_RANGE)
        self.assertEqual(table["gba_range"], TABLE_GBA_RANGE)
        self.assertEqual(table["byte_size"], 15)
        self.assertEqual(table["byte_sha256"], TABLE_SHA256)
        self.assertEqual(table["raw_hex"], TABLE_RAW_HEX)
        self.assertEqual([row["raw_hex"] for row in table["records"]], RECORDS)
        self.assertEqual(table["record_count"], 5)
        self.assertEqual(table["record_size"], 3)
        self.assertEqual(table["index_domain"], [0, 4])
        self.assertEqual(table["field_offsets"], [0, 1, 2])
        self.assertEqual(table["right_unknown_range"], RIGHT_UNKNOWN_RANGE)
        self.assertEqual(table["right_unknown_sha256"], RIGHT_UNKNOWN_SHA256)
        pointer = payload["pointer_binding"]
        self.assertEqual(pointer["literal_file_range"], POINTER_RANGE)
        self.assertEqual(pointer["literal_gba_range"], POINTER_GBA_RANGE)
        self.assertEqual(pointer["raw_hex"], POINTER_RAW_HEX)
        self.assertEqual(pointer["value"], POINTER_VALUE)
        self.assertEqual(pointer["sha256"], POINTER_SHA256)
        self.assertEqual(pointer["full_rom_occurrences"], POINTER_OCCURRENCES)
        self.assertEqual(pointer["occurrence_count"], 1)
        self.assertEqual(pointer["occurrence_vector_sha256"], POINTER_OCCURRENCE_VECTOR_SHA256)
        consumer = payload["consumer"]
        self.assertEqual(consumer["root_file_offset"], 0x75BD2)
        self.assertEqual(consumer["envelope"]["file_range"], ENVELOPE_RANGE)
        self.assertEqual(consumer["envelope"]["sha256"], ENVELOPE_SHA256)
        self.assertEqual([item["file_range"] for item in consumer["code_ranges"]], CODE_RANGES)
        self.assertEqual(consumer["code_byte_size"], CODE_SIZE)
        self.assertEqual(consumer["code_sha256"], CODE_SHA256)
        self.assertEqual(consumer["block_count"], BLOCK_COUNT)
        self.assertEqual(consumer["instruction_count"], INSTRUCTION_COUNT)
        self.assertEqual(consumer["frontier_count"], FRONTIER_COUNT)
        self.assertEqual(consumer["block_vector_sha256"], BLOCK_VECTOR_SHA256)
        self.assertEqual(consumer["excluded_pool_ranges"], POOL_RANGES)
        self.assertEqual(bundle, bytes.fromhex(POINTER_RAW_HEX + TABLE_RAW_HEX))

    def test_exact_index_formula_and_semantic_bindings(self):
        exporter, _ = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        formula = payload["index_formula"]
        self.assertEqual(formula["index_register"], "r5")
        self.assertEqual(formula["initial_value"], 0)
        self.assertEqual(formula["expression"], "2*i+i")
        self.assertEqual(formula["stride_bytes"], 3)
        self.assertEqual(formula["index_domain"], [0, 4])
        self.assertEqual(formula["field_offsets"], [0, 1, 2])
        self.assertEqual(formula["field_width"], "u8")
        self.assertEqual(formula["increment_u8_truncation"], [0x75D02, 0x75D04, 0x75D06])
        self.assertEqual(formula["bound_compare"], {"file_offset": 0x75D08, "immediate": 4})
        self.assertEqual(formula["back_edge"], [0x75D0C, 0x75BDA])
        self.assertEqual(formula["literal_load"], {"file_offset": 0x75BD4, "halfword": 0x4C0D, "literal_file_offset": 0x75C0C})
        self.assertEqual(formula["wildcard_field1_value"], 0xFF)
        self.assertEqual(formula["wildcard_range"], {"lower_exclusive": 0x80, "upper_inclusive": 0x91})
        self.assertEqual(payload["external_calls"], [[0x75C58, 0x6D85C], [0x75C70, 0x6D910]])
        self.assertEqual(payload["structured_return_target"], 0x75D12)
        self.assertEqual(payload["scope"]["natural_runtime_reachability_complete"], False)
        self.assertEqual(payload["scope"]["business_field_semantics_complete"], False)

    def test_only_current_unknown_pointer_and_table_are_promoted(self):
        exporter, verifier = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        promotion = payload["promotion"]
        self.assertEqual(promotion["ranges"], PROMOTION_RANGES)
        self.assertEqual(promotion["byte_size"], 19)
        self.assertEqual(promotion["range_vector_sha256"], PROMOTION_RANGE_VECTOR_SHA256)
        self.assertEqual(promotion["packed_sha256"], PROMOTION_PACKED_SHA256)
        self.assertEqual(
            [claim["claim_kind"] for claim in promotion["claims"]],
            [
                "fixed_consumer_triplet_pointer_literal_bytes",
                "fixed_consumer_triplet_record_bytes",
            ],
        )
        self.assertNotIn([0x53DFBF, 0x53E000], promotion["ranges"])
        self.assertTrue(all(pool not in promotion["ranges"] for pool in POOL_RANGES))
        self.assertEqual(payload["coverage_projection"]["baseline"]["sha256"], COVERAGE_SHA256)
        self.assertEqual(payload["coverage_projection"]["baseline"]["size"], COVERAGE_SIZE)
        self.assertEqual(payload["coverage_projection"]["expected_delta"], {"classified": 19, "unknown": -19, "claims": 2, "segments": 2})
        rebuilt, rebuilt_bundle = verifier.rebuild_payload(ROOT)
        self.assertEqual(rebuilt, payload)
        self.assertEqual(rebuilt_bundle, bytes.fromhex(POINTER_RAW_HEX + TABLE_RAW_HEX))

    def test_export_artifact_is_candidate_only_and_canonical(self):
        exporter, verifier = self._implemented()
        with _temporary_experiment_dir() as raw:
            output = Path(raw) / "candidate"
            result = exporter.export_artifact(ROOT, output)
            self.assertEqual(result["schema"], SCHEMA)
            self.assertEqual({p.name for p in output.iterdir()}, {"manifest.json", JSON_NAME, BIN_NAME})
            manifest_raw = (output / "manifest.json").read_bytes()
            manifest = json.loads(manifest_raw)
            self.assertEqual(manifest_raw, _canonical(manifest))
            self.assertEqual(manifest["schema"], PROMOTION_SCHEMA)
            self.assertEqual(manifest["artifact_schema"], SCHEMA)
            self.assertEqual(manifest["artifact_status"], "candidate")
            self.assertNotIn("verifier", manifest)
            self.assertNotIn("verification", manifest)
            self.assertTrue(verifier.verify_artifact(ROOT, output)["verified"])

    def test_rom_table_pointer_and_semantic_mutations_fail_closed(self):
        exporter, verifier = self._implemented()
        original = ROM_PATH.read_bytes()
        mutations = {
            "table-byte": 0x53DFB0,
            "table-row-order": 0x53DFB0,
            "pointer-value": 0x75C0C,
            "ldr": 0x75BD4,
            "stride": 0x75BDC,
            "field-load": 0x75BE2,
            "wildcard": 0x75BF0,
            "u8-truncation": 0x75D04,
            "bound": 0x75D08,
            "back-edge": 0x75D0C,
        }
        for label, offset in mutations.items():
            with self.subTest(label=label):
                mutated = bytearray(original)
                if label == "table-row-order":
                    mutated[0x53DFB0:0x53DFB3], mutated[0x53DFB3:0x53DFB6] = (
                        mutated[0x53DFB3:0x53DFB6],
                        mutated[0x53DFB0:0x53DFB3],
                    )
                else:
                    mutated[offset] ^= 1
                changed = bytes(mutated)
                for implementation in (exporter, verifier):
                    with self.subTest(implementation=implementation.__name__):
                        with self.assertRaises(ValueError):
                            implementation.rebuild_from_rom(ROOT, changed)

    def test_all_three_field_loads_and_return_external_edges_are_pinned(self):
        exporter, verifier = self._implemented()
        original = ROM_PATH.read_bytes()
        offsets = [0x075BE2, 0x075BEE, 0x075C24, 0x075D0E, 0x075C58, 0x075C70]
        for offset in offsets:
            with self.subTest(offset=hex(offset)):
                changed = bytearray(original)
                changed[offset] ^= 1
                for implementation in (exporter, verifier):
                    with self.subTest(implementation=implementation.__name__):
                        with self.assertRaises(ValueError):
                            implementation.rebuild_from_rom(ROOT, bytes(changed))

    def test_semantic_mutation_fails_after_range_hashes_are_resigned(self):
        exporter, verifier = self._implemented()
        original = ROM_PATH.read_bytes()
        offsets = [
            0x075BE2,
            0x075BEE,
            0x075C24,
            0x075BDC,
            0x075BDE,
            0x075D02,
            0x075D04,
            0x075D06,
            0x075D08,
            0x075D0A,
            0x075D0C,
            0x075C58,
            0x075C70,
            0x075D0E,
        ]
        for offset in offsets:
            changed_bytes = bytearray(original)
            changed_bytes[offset] ^= 1
            changed = bytes(changed_bytes)
            for implementation in (exporter, verifier):
                with self.subTest(offset=hex(offset), implementation=implementation.__name__):
                    changed_range_hashes = [
                        _sha(changed[start:end])
                        for start, end in implementation.CODE_RANGES
                    ]
                    changed_range_hex = [
                        changed[start:end].hex()
                        for start, end in implementation.CODE_RANGES
                    ]
                    changed_code = b"".join(
                        changed[start:end]
                        for start, end in implementation.CODE_RANGES
                    )
                    changed_vector = implementation._instruction_vector(changed)
                    coverage = {
                        "path": "sequel/rom-byte-coverage.json",
                        "schema": "rom-byte-coverage-v1",
                        "size": 0,
                        "sha256": "resigned",
                        "current_unknown_only": True,
                        "existing_cfg_owner_reused": True,
                        "expected_delta": {
                            "classified": 19,
                            "unknown": -19,
                            "claims": 2,
                            "segments": 2,
                        },
                    }
                    with (
                        mock.patch.object(implementation, "ROM_SHA256", _sha(changed)),
                        mock.patch.object(
                            implementation,
                            "CODE_RANGE_SHA256",
                            changed_range_hashes,
                        ),
                        mock.patch.object(
                            implementation,
                            "CODE_RANGE_HEX",
                            changed_range_hex,
                        ),
                        mock.patch.object(
                            implementation,
                            "CODE_SHA256",
                            _sha(changed_code),
                        ),
                        mock.patch.object(
                            implementation,
                            "CONSUMER_ENVELOPE_SHA256",
                            _sha(changed[0x075BD2:0x075D10]),
                        ),
                        mock.patch.object(
                            implementation,
                            "SEMANTIC_VECTOR_SHA256",
                            _sha(implementation._compact(changed_vector)),
                        ),
                        mock.patch.object(
                            implementation,
                            "_coverage_contract",
                            return_value=coverage,
                        ),
                    ):
                        with self.assertRaises(ValueError):
                            implementation.rebuild_from_rom(ROOT, changed)

    def test_resigned_pointer_target_must_still_bind_exact_table_start(self):
        exporter, verifier = self._implemented()
        original = ROM_PATH.read_bytes()
        changed_bytes = bytearray(original)
        changed_pointer = (POINTER_VALUE + 3).to_bytes(4, "little")
        changed_bytes[POINTER_RANGE[0] : POINTER_RANGE[1]] = changed_pointer
        changed = bytes(changed_bytes)
        occurrences = [
            offset
            for offset in range(len(changed) - 3)
            if changed[offset : offset + 4] == changed_pointer
        ]
        packed = changed_pointer + changed[TABLE_RANGE[0] : TABLE_RANGE[1]]
        for implementation in (exporter, verifier):
            with self.subTest(implementation=implementation.__name__):
                with (
                    mock.patch.object(implementation, "ROM_SHA256", _sha(changed)),
                    mock.patch.object(implementation, "POINTER_RAW", changed_pointer),
                    mock.patch.object(implementation, "POINTER_VALUE", POINTER_VALUE + 3),
                    mock.patch.object(implementation, "POINTER_SHA256", _sha(changed_pointer)),
                    mock.patch.object(implementation, "POINTER_OCCURRENCES", occurrences),
                    mock.patch.object(
                        implementation,
                        "POINTER_OCCURRENCE_VECTOR_SHA256",
                        _sha(implementation._compact(occurrences)),
                    ),
                    mock.patch.object(
                        implementation,
                        "PROMOTION_PACKED_SHA256",
                        _sha(packed),
                    ),
                    mock.patch.object(
                        implementation,
                        "CONSUMER_ENVELOPE_SHA256",
                        _sha(changed[0x075BD2:0x075D10]),
                    ),
                    mock.patch.object(
                        implementation,
                        "_coverage_contract",
                        return_value={
                            "path": "sequel/rom-byte-coverage.json",
                            "schema": "rom-byte-coverage-v1",
                            "size": 0,
                            "sha256": "resigned",
                            "current_unknown_only": True,
                            "existing_cfg_owner_reused": True,
                            "expected_delta": {
                                "classified": 19,
                                "unknown": -19,
                                "claims": 2,
                                "segments": 2,
                            },
                        },
                    ),
                ):
                    with self.assertRaisesRegex(ValueError, "table|pointer|literal"):
                        implementation.rebuild_from_rom(ROOT, changed)

    def test_pointer_duplicate_and_moved_occurrences_fail_after_rom_resign(self):
        exporter, verifier = self._implemented()
        original = ROM_PATH.read_bytes()
        def duplicate(value: bytes) -> bytes:
            changed = bytearray(value)
            changed[0x100:0x104] = bytes.fromhex(POINTER_RAW_HEX)
            return bytes(changed)

        def moved(value: bytes) -> bytes:
            changed = bytearray(value)
            changed[POINTER_RANGE[0] : POINTER_RANGE[1]] = b"\x00\x00\x00\x00"
            changed[0x100:0x104] = bytes.fromhex(POINTER_RAW_HEX)
            return bytes(changed)

        for label, mutate in (("duplicate", duplicate), ("moved", moved)):
            with self.subTest(label=label):
                changed = mutate(original)
                for implementation in (exporter, verifier):
                    with self.subTest(implementation=implementation.__name__):
                        with mock.patch.object(implementation, "ROM_SHA256", _sha(changed)):
                            with self.assertRaises(ValueError):
                                implementation.rebuild_from_rom(ROOT, changed)

    def test_output_path_rejects_nonempty_and_unsafe_candidate_paths(self):
        exporter, _ = self._implemented()
        with _temporary_experiment_dir() as raw:
            nonempty = Path(raw) / "nonempty"
            nonempty.mkdir()
            (nonempty / "keep").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                exporter.export_artifact(ROOT, nonempty)
        with self.assertRaises(ValueError):
            exporter.export_artifact(ROOT, ROOT / "build/experiments/active/not-the-triplet")

    def test_output_path_rejects_an_existing_empty_directory_explicitly(self):
        exporter, _ = self._implemented()
        with _temporary_experiment_dir() as raw:
            empty = Path(raw) / "empty"
            empty.mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"):
                exporter.export_artifact(ROOT, empty)

    def test_coverage_summary_fields_are_not_interchangeable_after_resign(self):
        exporter, verifier = self._implemented()
        coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8"))
        changed = copy.deepcopy(coverage)
        summary = changed["summary"]
        summary["classified_bytes"], summary["unknown_bytes"] = (
            summary["unknown_bytes"],
            summary["classified_bytes"],
        )
        raw = _canonical(changed)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "sequel/rom-byte-coverage.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(raw)
            for implementation in (exporter, verifier):
                with self.subTest(implementation=implementation.__name__):
                    with (
                        mock.patch.object(implementation, "COVERAGE_SHA256", _sha(raw)),
                        mock.patch.object(implementation, "COVERAGE_SIZE", len(raw)),
                    ):
                        with self.assertRaisesRegex(ValueError, "summary|baseline"):
                            implementation._coverage_contract(root.resolve())

    def test_verifier_has_no_exporter_import_or_process_escape(self):
        source = (ROOT / "tools/verify_rom_u8_indexed_u8_triplet_lookup.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertNotIn("importlib", imports)
        self.assertNotIn("tools.export_rom_u8_indexed_u8_triplet_lookup", imported_modules)
        for function_name in ("rebuild_payload", "verify_artifact"):
            node = next(
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
            )
            self.assertNotIn(
                "subprocess",
                ast.get_source_segment(source, node) or "",
            )
