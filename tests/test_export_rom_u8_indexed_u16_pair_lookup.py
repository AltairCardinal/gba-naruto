#!/usr/bin/env python3
"""TDD contract for the fixed u8-indexed, two-u16 lookup overlay."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom/base.gba"
SCHEMA = "rom-u8-indexed-u16-pair-lookup-v1"
VERIFY_SCHEMA = "rom-u8-indexed-u16-pair-lookup-verification-v1"
LOGICAL_START = 0x59F560
LOGICAL_END = 0x59F960
PRIMARY_START = 0x59F560
PRIMARY_END = 0x59F5F0
OVERLAP_START = 0x59F5F0
OVERLAP_END = 0x59F960
EXPECTED_LOGICAL_SHA256 = "adaa3da39ee951908263186ab1587a95f827b3041b4a59055da9fb54eb7cdf53"
EXPECTED_PRIMARY_SHA256 = "36799e6ed48b1bb9dfb3b6ed607e114ef6477174ce57f57ad352b8cab0441f60"
EXPECTED_OVERLAP_SHA256 = "8e709ff34aa30c2d5f1639513fee9cfabd54e88e726112f5d49e3253549306f1"
EXPECTED_BASE_LITERAL = 0x0859F560
EXPECTED_BASE_LITERAL_RAW = "60f55908"
EXPECTED_BASE_LITERAL_ADDRESSES = [0x08078094, 0x080898D8, 0x08093C6C]
EXPECTED_CONSUMER_CALLERS = {
    0x08077C90: [0x080795D4, 0x08086B90],
    0x0808983C: [0x08089464, 0x08089920],
    0x08093818: [0x08095E68],
}
EXPECTED_CELL_29 = {
    "raw_hex": "00008eb9",
    "sha256": "90a3a6705c52c282ca775cd1eb304e5f1beba470df7f764bbb19824ecefb2141",
}
EXPECTED_CELL_62 = {
    "raw_hex": "05000000",
    "sha256": "2594b6a92ebfb1c3312deb7d01c015fb95e9fbe9bd7bc6b527af07813ec7b910",
}
EXPECTED_COVERAGE_SHA256 = "4ea0496a0754d0391ae4f48e16f941d9a2241c9cc730bdf38799abde85181cbd"
EXPECTED_OWNER_MANIFEST_SHA256 = "094dbb593b2b8e09849ea795f4a09155598936cd3a1bc0b36e2eda6a413cf789"
EXPECTED_OWNER_PAYLOAD_SHA256 = "adc03bd5e29e956c208698fedc733e305ea87e519e17dfa405ff813939149430"
EXPECTED_OWNER_VERIFIER_SHA256 = "510835b5d104f0009df09e3c8200beaefcb4f01836c40db7d3b1c11b475052d1"
ROM_BASE = 0x08000000


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _encode_thumb_bl(gba: int, target: int) -> bytes:
    delta = target - (gba + 4)
    if delta % 2 or not -(1 << 24) <= delta <= (1 << 24) - 2:
        raise ValueError("Thumb BL test target is out of range")
    encoded = delta & ((1 << 25) - 1)
    sign = (encoded >> 24) & 1
    i1 = ((encoded >> 23) & 1) ^ sign ^ 1
    i2 = ((encoded >> 22) & 1) ^ sign ^ 1
    first = 0xF000 | (sign << 10) | ((encoded >> 12) & 0x03FF)
    second = 0xF800 | (i1 << 13) | (i2 << 11) | ((encoded >> 1) & 0x07FF)
    return first.to_bytes(2, "little") + second.to_bytes(2, "little")


def _decode_thumb_bl(raw: bytes, gba: int) -> int:
    first = int.from_bytes(raw[:2], "little")
    second = int.from_bytes(raw[2:4], "little")
    sign = (first >> 10) & 1
    i1 = ((second >> 13) & 1) ^ 1 ^ sign
    i2 = ((second >> 11) & 1) ^ 1 ^ sign
    immediate = (sign << 24) | (i1 << 23) | (i2 << 22) | ((first & 0x03FF) << 12) | ((second & 0x07FF) << 1)
    if sign:
        immediate -= 1 << 25
    return gba + 4 + immediate


def _load_modules():
    """Import lazily so the RED phase fails as an explicit missing implementation."""
    try:
        exporter = importlib.import_module("tools.export_rom_u8_indexed_u16_pair_lookup")
        verifier = importlib.import_module("tools.verify_rom_u8_indexed_u16_pair_lookup")
    except ModuleNotFoundError:
        return None, None
    return exporter, verifier


def _copy_file(root: Path, relative: str) -> None:
    source = ROOT / relative
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_minimal_root(root: Path, *, include_artifact: bool = False) -> None:
    for relative in (
        "rom/base.gba",
        "sequel/rom-byte-coverage.json",
        "artifacts/rom-selector-direct-source-records-v1/manifest.json",
        "artifacts/rom-selector-direct-source-records-v1/rom-selector-direct-source-records.json",
        "artifacts/rom-selector-direct-source-records-v1/rom-selector-direct-source-records.bin",
        "tools/export_rom_selector_direct_source_records.py",
        "tools/verify_rom_selector_direct_source_records.py",
        "tests/test_export_rom_selector_direct_source_records.py",
        "tools/export_rom_u8_indexed_u16_pair_lookup.py",
        "tools/verify_rom_u8_indexed_u16_pair_lookup.py",
        "tests/test_export_rom_u8_indexed_u16_pair_lookup.py",
    ):
        _copy_file(root, relative)
    if include_artifact:
        artifact = ROOT / "artifacts/rom-u8-indexed-u16-pair-lookup-v1"
        target = root / "artifacts/rom-u8-indexed-u16-pair-lookup-v1"
        shutil.copytree(artifact, target)


class U8IndexedU16PairLookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM.read_bytes()
        cls.exporter, cls.verifier = _load_modules()

    def _implemented(self):
        self.assertIsNotNone(
            self.exporter,
            "u8-indexed u16-pair lookup exporter implementation is absent",
        )
        self.assertIsNotNone(
            self.verifier,
            "u8-indexed u16-pair lookup verifier implementation is absent",
        )
        return self.exporter, self.verifier

    def test_exporter_and_independent_verifier_rebuild_exact_contract(self) -> None:
        exporter, verifier = self._implemented()
        exported, bundle = exporter.build_payload(ROOT)
        rebuilt, rebuilt_bundle = verifier.rebuild_payload(ROOT)
        self.assertEqual(exported, rebuilt)
        self.assertEqual(bundle, rebuilt_bundle)
        self.assertEqual(exported["schema"], SCHEMA)
        self.assertEqual(exported["logical_view"]["range"], [LOGICAL_START, LOGICAL_END])
        self.assertEqual(exported["logical_view"]["cell_count"], 256)
        self.assertEqual(exported["logical_view"]["cell_size"], 4)
        self.assertEqual(exported["logical_view"]["size"], 1024)
        self.assertEqual(exported["logical_view"]["sha256"], EXPECTED_LOGICAL_SHA256)
        self.assertEqual(exported["coverage_projection"]["current_unknown"]["range"], [PRIMARY_START, PRIMARY_END])
        self.assertEqual(exported["coverage_projection"]["current_unknown"]["cell_count"], 36)
        self.assertEqual(exported["coverage_projection"]["current_unknown"]["size"], 144)
        self.assertEqual(exported["coverage_projection"]["current_unknown"]["sha256"], EXPECTED_PRIMARY_SHA256)
        overlap = exported["coverage_projection"]["existing_owner_overlap"]
        self.assertEqual(overlap["range"], [OVERLAP_START, OVERLAP_END])
        self.assertEqual(overlap["cell_count"], 220)
        self.assertEqual(overlap["size"], 880)
        self.assertEqual(overlap["sha256"], EXPECTED_OVERLAP_SHA256)
        self.assertEqual(overlap["owner_source_ids"], list(range(44)))
        self.assertEqual(exported["base_literal"]["value"], EXPECTED_BASE_LITERAL)
        self.assertEqual(exported["base_literal"]["raw_hex"], EXPECTED_BASE_LITERAL_RAW)
        self.assertEqual(exported["base_literal"]["occurrences"], EXPECTED_BASE_LITERAL_ADDRESSES)
        self.assertEqual(
            [item["function_entry"] for item in exported["consumers"]],
            list(EXPECTED_CONSUMER_CALLERS),
        )
        self.assertFalse(exported["scope"]["allocatable"])
        self.assertTrue(all(value is False for value in exported["non_claims"].values()))

    def test_cells_are_contiguous_and_each_pair_is_little_endian(self) -> None:
        exporter, _ = self._implemented()
        payload, bundle = exporter.build_payload(ROOT)
        cells = payload["logical_view"]["cells"]
        self.assertEqual(len(cells), 256)
        self.assertEqual(len(bundle), 1024)
        self.assertEqual(bundle, self.rom[LOGICAL_START:LOGICAL_END])
        for index, cell in enumerate(cells):
            start = LOGICAL_START + index * 4
            raw = self.rom[start : start + 4]
            self.assertEqual(cell["index"], index)
            self.assertEqual(cell["range"], [start, start + 4])
            self.assertEqual(cell["raw_hex"], raw.hex())
            self.assertEqual(cell["raw_sha256"], _sha(raw))
            self.assertEqual(cell["multiplier_u16"], int.from_bytes(raw[:2], "little"))
            self.assertEqual(cell["addend_u16"], int.from_bytes(raw[2:], "little"))
            self.assertEqual(cell["formula"], "multiplier_u16*(count-1)+addend_u16")
        self.assertEqual(cells[29]["raw_hex"], EXPECTED_CELL_29["raw_hex"])
        self.assertEqual(cells[29]["raw_sha256"], EXPECTED_CELL_29["sha256"])
        self.assertEqual(cells[62]["raw_hex"], EXPECTED_CELL_62["raw_hex"])
        self.assertEqual(cells[62]["raw_sha256"], EXPECTED_CELL_62["sha256"])

    def test_three_raw_consumers_rebuild_index_loads_formula_and_callers(self) -> None:
        exporter, _ = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        consumers = {item["function_entry"]: item for item in payload["consumers"]}
        first = consumers[0x08077C90]
        self.assertEqual(first["base_literal_load"]["gba_address"], 0x08077F34)
        self.assertEqual(first["base_literal_load"]["raw_hex"], "5749")
        self.assertEqual(first["index_argument"]["width"], "u8")
        self.assertEqual(first["index_argument"]["source"], "third_argument")
        self.assertFalse(first["index_guard_before_load"])
        self.assertEqual(first["direct_bl_callers"], EXPECTED_CONSUMER_CALLERS[0x08077C90])
        second = consumers[0x0808983C]
        self.assertEqual(second["base_literal_load"]["gba_address"], 0x08089868)
        self.assertEqual(second["base_literal_load"]["raw_hex"], "1b48")
        self.assertEqual(second["index_argument"]["width"], "u8")
        self.assertEqual(second["index_argument"]["source"], "first_argument")
        self.assertEqual(second["count_guard"], {"immediate": 0x31, "relation": "count<=0x31"})
        self.assertFalse(second["index_guard_before_load"])
        self.assertEqual(second["direct_bl_callers"], EXPECTED_CONSUMER_CALLERS[0x0808983C])
        self.assertEqual(second["branch_domain"], {"inclusive_ranges": [[0, 21]], "singleton_values": [29, 62]})
        self.assertTrue(second["all_branch_classes_reach_load"])
        self.assertEqual(second["branch_load_callsite"], 0x08089920)
        third = consumers[0x08093818]
        self.assertEqual(third["base_literal_load"]["gba_address"], 0x08093A26)
        self.assertEqual(third["base_literal_load"]["raw_hex"], "914a")
        self.assertEqual(third["index_argument"]["width"], "u8")
        self.assertEqual(third["index_argument"]["source"], "dynamic_object_first_byte")
        self.assertEqual(third["post_load_cmp"]["immediate"], 3)
        self.assertEqual(third["post_load_cmp"]["position"], "after_load")
        self.assertEqual(third["direct_bl_callers"], EXPECTED_CONSUMER_CALLERS[0x08093818])
        for item in consumers.values():
            self.assertEqual(item["formula"], "u16(multiplier_u16*(count-1)+addend_u16)")
            self.assertEqual(item["arithmetic_expression"], "multiplier_u16*(count-1)+addend_u16")
            self.assertEqual(item["index_scale_bytes"], 4)
            self.assertEqual(item["enclosing_function_thumb_pointer_literals"], [])
        self.assertEqual(
            payload["base_literal"]["enclosing_function_thumb_entry_occurrences"],
            [
                {"entry": 0x08077C91, "entry_hex": "0x08077C91", "occurrences": []},
                {"entry": 0x0808983D, "entry_hex": "0x0808983D", "occurrences": []},
                {"entry": 0x08093819, "entry_hex": "0x08093819", "occurrences": []},
            ],
        )

    def test_u16_result_and_final_truncation_are_bound_for_all_consumers(self) -> None:
        exporter, verifier = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        expected = {
            0x08077C90: {
                "code_end": 0x08077F50,
                "truncation_gba": [0x08077F4C, 0x08077F4E],
                "truncation_halfwords": [0x0400, 0x0C05],
            },
            0x0808983C: {
                "code_end": 0x08089884,
                "truncation_gba": [0x08089880, 0x08089882],
                "truncation_halfwords": [0x0400, 0x0C01],
            },
            0x08093818: {
                "code_end": 0x08093A46,
                "truncation_gba": [0x08093A42, 0x08093A44],
                "truncation_halfwords": [0x0400, 0x0C05],
            },
        }
        for item in payload["consumers"]:
            contract = expected[item["function_entry"]]
            self.assertEqual(item["code_window"]["gba_range"], [f"0x{item['function_entry']:08X}", f"0x{contract['code_end']:08X}"])
            self.assertEqual(item["result"], {"width": "u16", "truncation_gba": contract["truncation_gba"], "truncation_halfwords": contract["truncation_halfwords"]})
            self.assertEqual(item["formula"], "u16(multiplier_u16*(count-1)+addend_u16)")
            self.assertEqual(item["arithmetic_expression"], "multiplier_u16*(count-1)+addend_u16")
        rebuilt, _ = verifier.rebuild_payload(ROOT)
        self.assertEqual(rebuilt, payload)

    def test_u16_formula_handles_count_zero_and_arithmetic_overflow(self) -> None:
        exporter, _ = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        cells = payload["logical_view"]["cells"]

        def evaluate(cell: dict, count: int) -> int:
            return (cell["multiplier_u16"] * (count - 1) + cell["addend_u16"]) & 0xFFFF

        self.assertEqual(evaluate(cells[62], 0), 0xFFFB)
        self.assertEqual(evaluate(cells[62], 0x10001), 0)
        self.assertEqual(evaluate(cells[29], 0), cells[29]["addend_u16"])
        for consumer in payload["consumers"]:
            self.assertEqual(consumer["result"]["width"], "u16")

    def test_final_u16_truncation_mutations_fail_closed(self) -> None:
        exporter, verifier = self._implemented()
        addresses = (0x08077F4C, 0x08089880, 0x08093A42)
        for address in addresses:
            with self.subTest(address=hex(address)):
                with tempfile.TemporaryDirectory() as raw:
                    root = Path(raw)
                    _copy_minimal_root(root)
                    tampered = bytearray((root / "rom/base.gba").read_bytes())
                    tampered[address - 0x08000000] ^= 1
                    tampered_bytes = bytes(tampered)
                    (root / "rom/base.gba").write_bytes(tampered_bytes)
                    tampered_sha = _sha(tampered_bytes)
                    for implementation in (exporter, verifier):
                        with self.subTest(implementation=implementation.__name__):
                            with mock.patch.object(implementation, "ROM_SHA256", tampered_sha):
                                with self.assertRaisesRegex(ValueError, "consumer|truncation|u16|code"):
                                    implementation.rebuild_from_rom(root, tampered_bytes)

    def test_existing_selector_primary_owners_are_bound_without_reclassification(self) -> None:
        exporter, verifier = self._implemented()
        payload, _ = exporter.build_payload(ROOT)
        overlap = payload["coverage_projection"]["existing_owner_overlap"]
        self.assertEqual(overlap["owner_artifact_manifest"], "artifacts/rom-selector-direct-source-records-v1/manifest.json")
        self.assertEqual(overlap["owner_manifest_sha256"], EXPECTED_OWNER_MANIFEST_SHA256)
        self.assertEqual(overlap["owner_payload_sha256"], EXPECTED_OWNER_PAYLOAD_SHA256)
        self.assertEqual(overlap["owner_verifier_sha256"], EXPECTED_OWNER_VERIFIER_SHA256)
        self.assertEqual(overlap["owner_primary_class"], "selector_direct_source_record")
        self.assertEqual(overlap["owner_claim_kind"], "selector_direct_source_record_bytes")
        self.assertEqual(overlap["owner_source_ids"], list(range(44)))
        self.assertEqual(payload["scope"]["revokes_existing_selector_owners"], False)
        self.assertEqual(payload["scope"]["reclassifies_existing_owner_overlap"], False)
        rebuilt, _ = verifier.rebuild_payload(ROOT)
        self.assertEqual(rebuilt["coverage_projection"], payload["coverage_projection"])

    def test_export_artifact_writes_canonical_manifest_and_verifier_evidence(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "artifact"
            result = exporter.export_artifact(ROOT, output)
            self.assertEqual(result["schema"], SCHEMA)
            self.assertEqual(
                set(path.name for path in output.iterdir()),
                {"manifest.json", "rom-u8-indexed-u16-pair-lookup.json", "rom-u8-indexed-u16-pair-lookup.bin"},
            )
            manifest = _json(output / "manifest.json")
            self.assertEqual(manifest["schema"], "git-artifact-promotion-v1")
            self.assertEqual(manifest["artifact_status"], "accepted")
            self.assertEqual(
                manifest["verifier"]["command"],
                [
                    "python3",
                    "tools/verify_rom_u8_indexed_u16_pair_lookup.py",
                    "--root",
                    ".",
                    "--artifact-dir",
                    str(output.absolute().resolve()),
                ],
            )
            self.assertEqual(manifest["files"]["rom-u8-indexed-u16-pair-lookup.bin"], _sha((output / "rom-u8-indexed-u16-pair-lookup.bin").read_bytes()))
            self.assertEqual(manifest["files"]["rom-u8-indexed-u16-pair-lookup.json"], _sha((output / "rom-u8-indexed-u16-pair-lookup.json").read_bytes()))
            report = verifier.verify_artifact(ROOT, output)
            self.assertTrue(report["verified"])
            self.assertEqual(report["schema"], VERIFY_SCHEMA)

    def test_export_artifact_allows_repo_relative_target(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _copy_minimal_root(root)
            output = root / "artifacts/rom-u8-indexed-u16-pair-lookup-v1"
            result = exporter.export_artifact(root, output)
            self.assertEqual(result["schema"], SCHEMA)
            self.assertTrue(verifier.verify_artifact(root, output)["verified"])

    def test_relative_output_is_resolved_against_validated_root(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw_root, tempfile.TemporaryDirectory() as raw_cwd:
            root = Path(raw_root)
            _copy_minimal_root(root)
            relative = Path("artifacts/relative-u8-pair")
            previous = Path.cwd()
            os.chdir(raw_cwd)
            try:
                exporter.export_artifact(root, relative)
            finally:
                os.chdir(previous)
            self.assertTrue((root / relative / "manifest.json").is_file())
            self.assertFalse((Path(raw_cwd) / relative).exists())
            manifest = _json(root / relative / "manifest.json")
            self.assertEqual(
                manifest["verifier"]["command"],
                ["python3", "tools/verify_rom_u8_indexed_u16_pair_lookup.py", "--root", ".", "--artifact-dir", relative.as_posix()],
            )
            self.assertNotIn(str(root), manifest["verifier"]["command"])
            self.assertTrue(verifier.verify_artifact(root, root / relative)["verified"])

    def test_output_path_rejects_nonempty_leaf_and_parent_symlink(self) -> None:
        exporter, _ = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            nonempty = base / "nonempty"
            nonempty.mkdir()
            (nonempty / "keep").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-empty"):
                exporter.export_artifact(ROOT, nonempty)

            real_leaf = base / "real-leaf"
            real_leaf.mkdir()
            leaf = base / "leaf-link"
            leaf.symlink_to(real_leaf, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.export_artifact(ROOT, leaf)

            real_parent = base / "real-parent"
            real_parent.mkdir()
            parent = base / "parent-link"
            parent.symlink_to(real_parent, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.export_artifact(ROOT, parent / "artifact")

    def test_export_artifact_requires_independent_verifier_success(self) -> None:
        exporter, _ = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "artifact"
            failed = mock.Mock(returncode=7, stdout="", stderr="forced verifier failure")
            with mock.patch.object(exporter.subprocess, "run", return_value=failed) as run:
                with self.assertRaisesRegex(RuntimeError, "independent verifier failed"):
                    exporter.export_artifact(ROOT, output)
            run.assert_called_once()
            self.assertFalse(output.exists())

    def test_candidate_manifest_rejects_preset_verifier_receipts(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "artifact"
            exporter.export_artifact(ROOT, output)
            manifest_path = output / "manifest.json"
            manifest = _json(manifest_path)
            manifest["artifact_status"] = "candidate"
            manifest["verifier"] = {"command": ["fake"], "exit_code": 0, "report": {"verified": True}}
            manifest["verification"] = {"verified": True}
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])

    def test_accepted_manifest_verifier_command_exit_and_report_are_exact(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "artifact"
            exporter.export_artifact(ROOT, output)
            manifest_path = output / "manifest.json"
            original = _json(manifest_path)
            for mutation in ("command", "exit", "report"):
                with self.subTest(mutation=mutation):
                    manifest = json.loads(json.dumps(original))
                    if mutation == "command":
                        manifest["verifier"]["command"] = ["python3", "wrong-verifier"]
                    elif mutation == "exit":
                        manifest["verifier"]["exit_code"] = 1
                    else:
                        manifest["verifier"]["report"]["verified"] = False
                    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                    report = verifier.verify_artifact(ROOT, output)
                    self.assertFalse(report["verified"])
            manifest_path.write_text(json.dumps(original, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_logical_bytes_mutation_fails_closed(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _copy_minimal_root(root)
            tampered = bytearray((root / "rom/base.gba").read_bytes())
            tampered[LOGICAL_START] ^= 1
            (root / "rom/base.gba").write_bytes(tampered)
            tampered_sha = _sha(bytes(tampered))
            for implementation in (exporter, verifier):
                with self.subTest(implementation=implementation.__name__):
                    with mock.patch.object(implementation, "ROM_SHA256", tampered_sha):
                        with self.assertRaisesRegex(ValueError, "logical|lookup|table"):
                            implementation.rebuild_from_rom(root, bytes(tampered))

    def test_base_literal_mutation_fails_closed(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _copy_minimal_root(root)
            tampered = bytearray((root / "rom/base.gba").read_bytes())
            tampered[0x080898D8 - 0x08000000] ^= 1
            (root / "rom/base.gba").write_bytes(tampered)
            tampered_sha = _sha(bytes(tampered))
            for implementation in (exporter, verifier):
                with self.subTest(implementation=implementation.__name__):
                    with mock.patch.object(implementation, "ROM_SHA256", tampered_sha):
                        with self.assertRaisesRegex(ValueError, "literal|base"):
                            implementation.rebuild_from_rom(root, bytes(tampered))

    def test_consumer_index_formula_mutation_fails_closed(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _copy_minimal_root(root)
            tampered = bytearray((root / "rom/base.gba").read_bytes())
            tampered[0x0808986A - 0x08000000] ^= 1
            (root / "rom/base.gba").write_bytes(tampered)
            tampered_sha = _sha(bytes(tampered))
            for implementation in (exporter, verifier):
                with self.subTest(implementation=implementation.__name__):
                    with mock.patch.object(implementation, "ROM_SHA256", tampered_sha):
                        with self.assertRaisesRegex(ValueError, "formula|index|consumer"):
                            implementation.rebuild_from_rom(root, bytes(tampered))

    def test_special_29_62_branch_mutation_fails_closed(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _copy_minimal_root(root)
            tampered = bytearray((root / "rom/base.gba").read_bytes())
            tampered[0x080898F2 - 0x08000000] ^= 1
            (root / "rom/base.gba").write_bytes(tampered)
            tampered_sha = _sha(bytes(tampered))
            for implementation in (exporter, verifier):
                with self.subTest(implementation=implementation.__name__):
                    with mock.patch.object(implementation, "ROM_SHA256", tampered_sha):
                        with self.assertRaisesRegex(ValueError, "branch|domain|29|62|consumer"):
                            implementation.rebuild_from_rom(root, bytes(tampered))

    def test_coverage_projection_mutation_fails_closed(self) -> None:
        exporter, verifier = self._implemented()
        payload, bundle = exporter.build_payload(ROOT)
        payload["coverage_projection"]["current_unknown"]["size"] += 4
        with self.assertRaisesRegex(ValueError, "coverage|projection|unknown"):
            verifier.verify_payload(ROOT, payload, bundle)

    def test_existing_owner_overlap_mutation_fails_closed(self) -> None:
        exporter, verifier = self._implemented()
        payload, bundle = exporter.build_payload(ROOT)
        payload["coverage_projection"]["existing_owner_overlap"]["owner_source_ids"][-1] = 44
        with self.assertRaisesRegex(ValueError, "owner|overlap|selector"):
            verifier.verify_payload(ROOT, payload, bundle)

    def test_verifier_does_not_require_future_canonical_coverage_file(self) -> None:
        exporter, verifier = self._implemented()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _copy_minimal_root(root)
            artifact = root / "artifact"
            exporter.export_artifact(root, artifact)
            (root / "sequel/rom-byte-coverage.json").unlink()
            report = verifier.verify_artifact(root, artifact)
            self.assertTrue(report["verified"])

    def test_verifier_source_is_independent_of_exporter(self) -> None:
        _, verifier = self._implemented()
        source = Path(verifier.__file__).read_text(encoding="utf-8")
        self.assertNotIn("export_rom_u8_indexed_u16_pair_lookup", source)
        self.assertNotIn("from tools import export", source)

    def test_literal_caller_and_thumb_entry_denominator_additions_fail_closed(self) -> None:
        exporter, verifier = self._implemented()
        caller_source = 0x080795D4 - 0x08000000
        new_caller_gba = ROM_BASE + 0x300
        new_caller_raw = _encode_thumb_bl(new_caller_gba, 0x08077C90)
        self.assertEqual(_decode_thumb_bl(new_caller_raw, new_caller_gba), 0x08077C90)
        mutations = {
            "literal": lambda rom: rom.__setitem__(slice(0x100, 0x104), bytes.fromhex("60f55908")),
            "caller": lambda rom: rom.__setitem__(slice(0x300, 0x304), new_caller_raw),
            "thumb-entry": lambda rom: rom.__setitem__(slice(0x400, 0x404), (0x08077C91).to_bytes(4, "little")),
            "existing-caller-encoding": lambda rom: rom.__setitem__(caller_source, (rom[caller_source] ^ 1)),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                with tempfile.TemporaryDirectory() as raw:
                    root = Path(raw)
                    _copy_minimal_root(root)
                    tampered = bytearray((root / "rom/base.gba").read_bytes())
                    mutate(tampered)
                    if name == "caller":
                        self.assertEqual(_decode_thumb_bl(bytes(tampered[0x300:0x304]), new_caller_gba), 0x08077C90)
                    tampered_bytes = bytes(tampered)
                    (root / "rom/base.gba").write_bytes(tampered_bytes)
                    tampered_sha = _sha(tampered_bytes)
                    for implementation in (exporter, verifier):
                        with self.subTest(implementation=implementation.__name__):
                            with mock.patch.object(implementation, "ROM_SHA256", tampered_sha):
                                with self.assertRaisesRegex(ValueError, "literal|base|caller|denominator|Thumb|entry|pointer"):
                                    implementation.rebuild_from_rom(root, tampered_bytes)


if __name__ == "__main__":
    unittest.main()
