"""TDD contract tests for the frozen battle sound selector packet."""

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
SCHEMA = "rom-battle-sound-selector-v1"
VERIFY_SCHEMA = "rom-battle-sound-selector-verification-v1"
JSON_NAME = "battle-sound-selector.json"
BIN_NAME = "battle-sound-selector.bin"
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_RANGE = (0x53E496, 0x53E596)
TABLE_SHA256 = "2f77582ae5eea1711b079fc8ce67d36e95ec68bf0e2bd0a3d5780eb3d9819b5d"
DENOMINATOR_SHA256 = "fc3c1c03d918f173b304633d84fcbd8ead4448f5185d30d687c2ef352a3fcd62"
POINTER_WORD = 0x0853E496
POINTER_RAW = "96e45308"
POINTER_GBA_ADDRESSES = [
    0x0807BC64,
    0x0807BDF8,
    0x0807C078,
    0x0807C33C,
    0x0807CCA4,
]
POINTER_VECTOR_SHA256 = "0aacec92ffcc42108b7fe437ff83872b3702697ab9662b51e86dffc73623392d"
CONSUMER_ROWS = [
    {
        "window": (0x07BB70, 0x07BB88),
        "base": 0x07BB70,
        "base_halfword": 0x493C,
        "literal": 0x07BC64,
        "index": 0x07BB7E,
        "table": 0x07BB82,
        "call": 0x07BB84,
        "bl_second": 0xF972,
        "window_sha256": "894597c8cc38880ab91ed219991c5d137b73d2e1c271d8c0e943e34bbd2a8c46",
    },
    {
        "window": (0x07BD50, 0x07BD68),
        "base": 0x07BD50,
        "base_halfword": 0x4929,
        "literal": 0x07BDF8,
        "index": 0x07BD5E,
        "table": 0x07BD62,
        "call": 0x07BD64,
        "bl_second": 0xF882,
        "window_sha256": "1ae576f2d74d8c58e4762db95c12658c41aaa537caec94471099ed4bd89aaa89",
    },
    {
        "window": (0x07C046, 0x07C05E),
        "base": 0x07C046,
        "base_halfword": 0x490C,
        "literal": 0x07C078,
        "index": 0x07C054,
        "table": 0x07C058,
        "call": 0x07C05A,
        "bl_second": 0xFF07,
        "window_sha256": "6c8a2264999769ed720357212d246cdc76e38cfd84f869cd6de300142fa424c4",
    },
    {
        "window": (0x07C1C6, 0x07C1E6),
        "base": 0x07C1C6,
        "base_halfword": 0x4B5D,
        "literal": 0x07C33C,
        "index": 0x07C1DC,
        "table": 0x07C1E0,
        "call": 0x07C1E2,
        "bl_second": 0xFE43,
        "window_sha256": "501fc5c21279690eeecd2b8da076ba6c5b416d6a924cd706bec2f36d09ad18eb",
    },
    {
        "window": (0x07CC88, 0x07CC9C),
        "base": 0x07CC88,
        "base_halfword": 0x4906,
        "literal": 0x07CCA4,
        "index": 0x07CC92,
        "table": 0x07CC96,
        "call": 0x07CC98,
        "bl_second": 0xF8E8,
        "window_sha256": "9c6ff38335c7aaf8a8b0152fc1b88ddeab0f928876c34303d945b46d823d63e4",
    },
]
NON_CLAIMS = {
    "all_indices_naturally_reached_claimed",
    "all_direct_paths_naturally_reached_claimed",
    "all_selector_consumers_exhausted_claimed",
    "computed_or_ram_consumers_exhausted_claimed",
    "zero_value_business_semantics_claimed",
    "nonzero_value_business_semantics_claimed",
    "index_to_gameplay_semantics_claimed",
    "play_routine_full_behavior_claimed",
    "sound_playback_success_claimed",
    "left_neighbor_structure_claimed",
    "right_neighbor_business_relation_claimed",
    "all_battle_audio_exhausted_claimed",
    "editing_safety_claimed",
    "writeback_safety_claimed",
    "relocation_safety_claimed",
    "free_space_claimed",
    "allocatable_space_claimed",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_artifact(source: Path, temporary: str) -> Path:
    target = Path(temporary) / "artifact"
    shutil.copytree(source, target)
    return target


class ExportRomBattleSoundSelectorTests(unittest.TestCase):
    def _mods(self):
        try:
            from tools import export_rom_battle_sound_selector as exporter
            from tools import verify_rom_battle_sound_selector as verifier
        except ModuleNotFoundError as error:
            self.fail(f"required product module missing: {error}")
        return exporter, verifier

    def _temporary_artifact(self):
        exporter, _ = self._mods()
        temporary = tempfile.TemporaryDirectory()
        output = Path(temporary.name) / "artifact"
        exporter.export_artifact(ROOT, output)
        return temporary, output

    def test_exact_selector_denominator_entries_and_statistics(self):
        exporter, _ = self._mods()
        payload = exporter.build_payload(ROOT)
        self.assertEqual(SCHEMA, payload["schema"])
        self.assertEqual(
            {
                "path": "rom/base.gba",
                "size": ROM_SIZE,
                "sha256": ROM_SHA256,
            },
            payload["rom"],
        )
        selector = payload["selector"]
        self.assertEqual(TABLE_RANGE, tuple(selector["range"]))
        self.assertEqual(
            [ROM_BASE + TABLE_RANGE[0], ROM_BASE + TABLE_RANGE[1]],
            selector["gba_range"],
        )
        self.assertEqual(256, selector["entry_count"])
        self.assertEqual(1, selector["entry_size"])
        self.assertEqual(TABLE_SHA256, selector["byte_sha256"])
        self.assertEqual(DENOMINATOR_SHA256, selector["denominator_sha256"])
        self.assertEqual(
            {
                "zero": 158,
                "nonzero": 98,
                "distinct": 18,
                "minimum": 0,
                "maximum": 0x90,
            },
            selector["counts"],
        )
        self.assertEqual(
            {
                "00": 158,
                "78": 3,
                "79": 5,
                "7A": 7,
                "7B": 3,
                "7C": 4,
                "7D": 43,
                "82": 3,
                "83": 6,
                "85": 1,
                "88": 1,
                "89": 2,
                "8A": 4,
                "8C": 9,
                "8D": 2,
                "8E": 1,
                "8F": 3,
                "90": 1,
            },
            selector["frequency_map"],
        )
        entries = payload["entries"]
        self.assertEqual(256, len(entries))
        rom = ROM_PATH.read_bytes()
        for index, row in enumerate(entries):
            with self.subTest(index=index):
                self.assertEqual(index, row["index"])
                self.assertEqual(TABLE_RANGE[0] + index, row["file_offset"])
                self.assertEqual(ROM_BASE + TABLE_RANGE[0] + index, row["gba_address"])
                self.assertEqual(rom[TABLE_RANGE[0] + index], row["value"])

    def test_literal_xrefs_and_consumer_paths_are_independently_decoded(self):
        exporter, verifier = self._mods()
        rom = ROM_PATH.read_bytes()
        exported = exporter.decode_consumer_contract(rom)
        independent = verifier.independent_consumer_contract(rom)
        self.assertEqual(exported, independent)
        self.assertEqual(5, len(exported["literal_xrefs"]))
        self.assertEqual(5, len(exported["consumer_paths"]))
        self.assertEqual(POINTER_GBA_ADDRESSES, exported["literal_addresses"])
        self.assertEqual(POINTER_VECTOR_SHA256, exported["literal_vector_sha256"])
        for expected, xref, path in zip(CONSUMER_ROWS, exported["literal_xrefs"], exported["consumer_paths"]):
            base_gba = ROM_BASE + expected["base"]
            literal_gba = ROM_BASE + expected["literal"]
            self.assertEqual(POINTER_WORD, xref["literal_word"])
            self.assertEqual(POINTER_RAW, xref["raw_word_hex"])
            self.assertEqual(base_gba, xref["base_load_address"])
            self.assertEqual(expected["base_halfword"], xref["base_load_halfword"])
            self.assertEqual(literal_gba, xref["resolved_literal_address"])
            self.assertEqual(base_gba, path["base_load_address"])
            self.assertEqual(literal_gba, path["literal_address"])
            self.assertEqual(
                ROM_BASE + expected["index"], path["final_index_load_address"]
            )
            self.assertEqual(
                ROM_BASE + expected["table"], path["table_load_address"]
            )
            self.assertEqual(1, path["final_index_load_width"])
            self.assertEqual(1, path["table_load_width"])
            self.assertEqual(ROM_BASE + expected["call"], path["play_callsite"])
            self.assertEqual(0x08061E6C, path["decoded_play_target"])
            self.assertEqual(list(expected["window"]), path["window"]["range"])
            self.assertEqual(expected["window_sha256"], path["window"]["sha256"])
            self.assertEqual(ROM_BASE + expected["window"][0], path["window"]["gba_range"][0])

    def test_right_boundary_and_non_claims_are_exact(self):
        exporter, _ = self._mods()
        payload = exporter.build_payload(ROOT)
        boundary = payload["right_boundary"]
        self.assertEqual(
            {
                "table_end_exclusive": TABLE_RANGE[1],
                "table_end_gba_address": ROM_BASE + TABLE_RANGE[1],
                "no_overlap": True,
                "no_gap_claimed": True,
                "next_byte": {
                    "file_offset": TABLE_RANGE[1],
                    "gba_address": ROM_BASE + TABLE_RANGE[1],
                    "class": "battle_effect_runtime_state_sequence_table",
                    "claim": "verified-reuse-battle-effect-runtime-state-sequences-53e596",
                },
            },
            boundary,
        )
        self.assertEqual(NON_CLAIMS, set(payload["non_claims"]))
        self.assertTrue(all(value is False for value in payload["non_claims"].values()))
        self.assertEqual(NON_CLAIMS, set(payload["scope"]["non_claims"]))
        self.assertTrue(all(value is False for value in payload["scope"]["non_claims"].values()))

    def test_export_is_deterministic_exactly_two_files_and_safe(self):
        exporter, _ = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            exporter.export_artifact(ROOT, first)
            exporter.export_artifact(ROOT, second)
            expected = {JSON_NAME, BIN_NAME}
            self.assertEqual(expected, {p.name for p in first.iterdir()})
            self.assertEqual(expected, {p.name for p in second.iterdir()})
            first_hashes = {p.name: _sha(p.read_bytes()) for p in first.iterdir()}
            second_hashes = {p.name: _sha(p.read_bytes()) for p in second.iterdir()}
            self.assertEqual(first_hashes, second_hashes)
            foreign = root / "foreign"
            foreign.mkdir()
            (foreign / "keep").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "foreign|non-empty"):
                exporter.export_artifact(ROOT, foreign)
            linked_target = root / "linked-target"
            linked_target.mkdir()
            linked = root / "linked"
            linked.symlink_to(linked_target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                exporter.export_artifact(ROOT, linked / "artifact")
        with self.assertRaisesRegex(ValueError, "repository root"):
            exporter.export_artifact(ROOT, ROOT)
        with self.assertRaisesRegex(ValueError, "ancestor"):
            exporter.export_artifact(ROOT, ROOT.parent)

    def test_independent_verifier_accepts_candidate_and_cli_is_deterministic(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            exporter.export_artifact(ROOT, output)
            first = verifier.verify_artifact(ROOT, output)
            second = verifier.verify_artifact(ROOT, output)
            self.assertEqual(first, second)
            self.assertTrue(first["verified"], first["errors"])
            self.assertEqual(VERIFY_SCHEMA, first["schema"])
            self.assertEqual([], first["errors"])
            command = [
                "python3",
                "tools/verify_rom_battle_sound_selector.py",
                "--root",
                str(ROOT),
                "--artifact-dir",
                str(output),
            ]
            result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(first, json.loads(result.stdout))

    def test_verifier_source_forbids_exporter_and_coverage_builders(self):
        source = (ROOT / "tools/verify_rom_battle_sound_selector.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        for imported in imports:
            self.assertNotIn("export_rom_battle_sound_selector", imported)
            self.assertNotIn("audit_rom_byte_coverage", imported)
            self.assertNotIn("audit_reverse_engineering_proof", imported)
        self.assertNotIn("sequel/rom-byte-coverage.json", source)
        self.assertNotIn("private_builder", source)
        self.assertNotIn("subprocess", imports)

    def test_consumer_and_literal_mutations_fail_closed(self):
        exporter, verifier = self._mods()
        original = ROM_PATH.read_bytes()
        mutation_cases = [
            ("table byte", TABLE_RANGE[0], "table"),
            ("literal word", CONSUMER_ROWS[0]["literal"], "literal"),
            ("base-load halfword", CONSUMER_ROWS[0]["base"], "literal"),
            ("final index LDRB", CONSUMER_ROWS[0]["index"], "index"),
            ("table LDRB", CONSUMER_ROWS[0]["table"], "table"),
            ("BL halfword", CONSUMER_ROWS[0]["call"], "play"),
        ]
        for label, offset, _ in mutation_cases:
            mutated = bytearray(original)
            mutated[offset] ^= 0x01
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    exporter.decode_consumer_contract(bytes(mutated))
                with self.assertRaises(ValueError):
                    verifier.independent_consumer_contract(bytes(mutated))

    def test_payload_binary_json_and_manifest_mutations_fail_closed(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            exporter.export_artifact(ROOT, source)
            payload = _json(source / JSON_NAME)
            manifest = {
                "schema": "git-artifact-promotion-v1",
                "artifact_schema": SCHEMA,
                "artifact_status": "accepted",
                "files": {
                    JSON_NAME: _sha((source / JSON_NAME).read_bytes()),
                    BIN_NAME: _sha((source / BIN_NAME).read_bytes()),
                },
                "verifier": {
                    "command": ["python3", "tools/verify_rom_battle_sound_selector.py"],
                    "exit_code": 0,
                },
            }

            fresh_index = [0]

            def fresh() -> Path:
                target = Path(temporary) / f"copy-{fresh_index[0]}"
                fresh_index[0] += 1
                shutil.copytree(source, target)
                return target

            mutated = fresh()
            changed = _json(mutated / JSON_NAME)
            changed["entries"][0]["value"] ^= 1
            (mutated / JSON_NAME).write_bytes(_canonical(changed))
            self.assertFalse(verifier.verify_artifact(ROOT, mutated)["verified"])

            mutated = fresh()
            raw = bytearray((mutated / BIN_NAME).read_bytes())
            raw[0] ^= 1
            (mutated / BIN_NAME).write_bytes(raw)
            self.assertFalse(verifier.verify_artifact(ROOT, mutated)["verified"])

            mutated = fresh()
            changed = _json(mutated / JSON_NAME)
            changed["implementation"]["exporter"]["sha256"] = "0" * 64
            (mutated / JSON_NAME).write_bytes(_canonical(changed))
            self.assertFalse(verifier.verify_artifact(ROOT, mutated)["verified"])

            mutated = fresh()
            (mutated / JSON_NAME).unlink()
            self.assertFalse(verifier.verify_artifact(ROOT, mutated)["verified"])

            final = Path(temporary) / "final"
            shutil.copytree(source, final)
            (final / "manifest.json").write_bytes(_canonical(manifest))
            self.assertTrue(verifier.verify_artifact(ROOT, final)["verified"])
            tampered = _json(final / "manifest.json")
            tampered["files"][BIN_NAME] = "0" * 64
            (final / "manifest.json").write_bytes(_canonical(tampered))
            self.assertFalse(verifier.verify_artifact(ROOT, final)["verified"])

    def test_verifier_rejects_missing_or_foreign_artifact_members(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            exporter.export_artifact(ROOT, output)
            (output / "foreign").write_text("x", encoding="utf-8")
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])
            (output / "foreign").unlink()
            (output / BIN_NAME).unlink()
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_payload_does_not_include_left_neighbor_consumer_or_right_neighbor(self):
        exporter, _ = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            exporter.export_artifact(ROOT, output)
            payload = _json(output / JSON_NAME)
            encoded = (output / JSON_NAME).read_text(encoding="utf-8")
            self.assertNotIn("left_neighbor", payload)
            self.assertNotIn("consumer_code", payload)
            self.assertNotIn("right_neighbor_bytes", payload)
            self.assertNotIn("0x53E495", encoded)
            self.assertNotIn("0x53E596", encoded)
            self.assertEqual(TABLE_RANGE[1] - TABLE_RANGE[0], (output / BIN_NAME).stat().st_size)


if __name__ == "__main__":
    unittest.main()
