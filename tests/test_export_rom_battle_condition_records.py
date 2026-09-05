"""TDD contract tests for the frozen battle condition records packet."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
SCHEMA = "rom-battle-condition-records-v1"
VERIFY_SCHEMA = "rom-battle-condition-records-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
JSON_NAME = "battle-condition-records.json"
BIN_NAME = "battle-condition-records.bin"
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_RANGE = (0x00594758, 0x00596CCC)
TABLE_GBA_RANGE = (0x08594758, 0x08596CCC)
TABLE_SIZE = 9_588
TABLE_SHA256 = "0d6e137011aa4e97c5b5d165f1939b7fb0b33235b9b20fceb1566b485dc35bf4"
PREFIX_RANGE_SHA256 = "1e2e792bf9c4fd75afe20481e55ca3ba7ea0374b88db95e7dad918b52f8bdd2d"
PREFIX_BYTES_SHA256 = "45ca80c7d87e05305a9677c54c552161834f1829c298b0d2078924e0947d950c"
PAYLOAD_RANGE_SHA256 = "240541fbf33b129c71076b7dbbed0fa12c5e4e58cc4d0df91dd406b96e22c958"
PAYLOAD_BYTES_SHA256 = "f429071eb67753a70d01e5ea056a1853646598cda81866adaa82630c13f17f7e"
SLOT_RANGE_SHA256 = "c9156961326d3ea4e7ba99f85c1860c3c6bfe587edbe79cda6fd5a5b541d7f6a"
SLOT_BYTES_SHA256 = "f429071eb67753a70d01e5ea056a1853646598cda81866adaa82630c13f17f7e"
INTERPRETER_RANGE = (0x0777FC, 0x077C1C)
INTERPRETER_SHA256 = "d3d27daffc790de8896f7d2194ae110f8e839e7095c95b2f708dacbe527e152e"
CORE_SLICE_RANGE = (0x07781C, 0x07786A)
CORE_SLICE_SHA256 = "459ff8159f6db352869fc58aaa5862820ecaa5aa4d209cbd8df9e0656d91cc2a"
DISPATCH_RANGE = (0x077878, 0x07789C)
DISPATCH_SHA256 = "3365c0bb46f11c4cb369b1f8c1d1a9f614907f20e3cd7ce9889d389c1d7348f7"
CALLER_RANGE = (0x07305C, 0x0731D0)
CALLER_SHA256 = "6d2208001cebc68f565fd30aaf1a0068549f0cb7c675faedc9c346cec6cc2240"
DISPATCH_TARGETS = [
    0x0807789C,
    0x08077904,
    0x08077924,
    0x08077994,
    0x080779B4,
    0x080779D4,
    0x080779EC,
    0x08077A78,
    0x08077AFC,
]
NON_CLAIMS = {
    "all_battle_ids_naturally_reached_claimed",
    "all_variant_indices_naturally_reached_claimed",
    "all_predicate_slots_naturally_evaluated_claimed",
    "all_condition_consumers_exhausted_claimed",
    "computed_or_ram_consumers_exhausted_claimed",
    "prefix_field_semantics_claimed",
    "prefix_padding_or_reserved_claimed",
    "byte3_field_semantics_claimed",
    "payload_word_business_semantics_claimed",
    "handlers_4_5_naturally_used_claimed",
    "battlefield_object_visible_behavior_names_claimed",
    "all_battle_conditions_semantically_named_claimed",
    "complete_objective_engine_claimed",
    "positions_condition_business_relation_claimed",
    "existing_primary_owner_reclassification_claimed",
    "right_gap_structure_claimed",
    "right_gap_padding_claimed",
    "runtime_trigger_coverage_claimed",
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


def _compact(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence(path: str, value: dict) -> dict[str, str]:
    raw = _canonical(value)
    return {
        "path": path,
        "sha256": _sha(raw),
        "content_base64": base64.b64encode(raw).decode("ascii"),
    }


def _dotted_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _forbidden_dynamic_calls(source: str) -> set[str]:
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    forbidden_modules = {"builtins", "importlib", "os", "runpy", "subprocess"}
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                aliases[alias.asname or root] = alias.name
                if root in forbidden_modules:
                    violations.add(root)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root in forbidden_modules:
                violations.add(root)
            for alias in node.names:
                if alias.name != "*":
                    aliases[alias.asname or alias.name] = (
                        f"{module}.{alias.name}" if module else alias.name
                    )
    forbidden = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "importlib.import_module",
        "os.popen",
        "os.spawnl",
        "os.spawnle",
        "os.spawnlp",
        "os.spawnlpe",
        "os.spawnv",
        "os.spawnve",
        "os.spawnvp",
        "os.spawnvpe",
        "os.system",
        "runpy.run_module",
        "runpy.run_path",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "subprocess.run",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted_call_name(node.func)
        head, separator, tail = name.partition(".")
        if head in aliases:
            name = aliases[head] + (separator + tail if separator else "")
        if name.startswith("builtins."):
            name = name.removeprefix("builtins.")
        if name in forbidden:
            violations.add(name)
    return violations


class ExportRomBattleConditionRecordsTests(unittest.TestCase):
    def _mods(self):
        try:
            from tools import export_rom_battle_condition_records as exporter
            from tools import verify_rom_battle_condition_records as verifier
        except ModuleNotFoundError as error:
            self.fail(f"required product module missing: {error}")
        return exporter, verifier

    def test_exact_denominator_layout_statistics_and_scope(self):
        exporter, _ = self._mods()
        payload = exporter.build_payload(ROOT)
        self.assertEqual(SCHEMA, payload["schema"])
        self.assertEqual(
            {"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256},
            payload["rom"],
        )
        table = payload["table"]
        self.assertEqual(list(TABLE_RANGE), table["file_range"])
        self.assertEqual(list(TABLE_GBA_RANGE), table["gba_range"])
        self.assertEqual(TABLE_SIZE, table["byte_size"])
        self.assertEqual(TABLE_SHA256, table["byte_sha256"])
        self.assertEqual(47, table["battle_count"])
        self.assertEqual(0xCC, table["battle_stride"])
        self.assertEqual(3, table["variants_per_battle"])
        self.assertEqual(0x44, table["variant_stride"])
        self.assertEqual(141, table["variant_count"])
        self.assertEqual(1128, table["predicate_slot_count"])
        self.assertEqual(
            {
                "prefix_ranges_json_sha256": PREFIX_RANGE_SHA256,
                "prefix_bytes_sha256": PREFIX_BYTES_SHA256,
                "predicate_payload_ranges_json_sha256": PAYLOAD_RANGE_SHA256,
                "predicate_payload_bytes_sha256": PAYLOAD_BYTES_SHA256,
                "predicate_slot_ranges_json_sha256": SLOT_RANGE_SHA256,
                "predicate_slot_bytes_sha256": SLOT_BYTES_SHA256,
            },
            table["denominator_hashes"],
        )
        stats = payload["statistics"]
        self.assertEqual(
            {"00000000": 122, "0f000000": 6, "14000000": 3, "0a000000": 2, "ff000000": 8},
            stats["prefix_frequency_map"],
        )
        self.assertEqual(19, stats["prefix_nonzero_byte_count"])
        self.assertEqual(
            {"0": 898, "1": 155, "2": 11, "3": 18, "6": 8, "7": 16, "8": 16, "9": 6},
            stats["condition_type_counts"],
        )
        self.assertEqual(1128, stats["byte3_raw_zero_count"])
        self.assertEqual(230, stats["payload_word_le_raw_nonzero_count"])
        self.assertEqual(219, stats["payload_word_le_raw_nonzero_distinct_count"])
        self.assertEqual(NON_CLAIMS, set(payload["non_claims"]))
        self.assertTrue(all(value is False for value in payload["non_claims"].values()))
        self.assertEqual(payload["non_claims"], payload["scope"]["non_claims"])

    def test_all_variants_and_predicates_are_exact_ordered_raw_rows(self):
        exporter, _ = self._mods()
        payload = exporter.build_payload(ROOT)
        rom = ROM_PATH.read_bytes()
        variants = payload["variants"]
        self.assertEqual(141, len(variants))
        for ordinal, row in enumerate(variants):
            battle_id, variant_index = divmod(ordinal, 3)
            start = TABLE_RANGE[0] + battle_id * 0xCC + variant_index * 0x44
            with self.subTest(battle_id=battle_id, variant=variant_index):
                self.assertEqual(battle_id, row["battle_id"])
                self.assertEqual(variant_index, row["variant_index"])
                self.assertEqual([start, start + 0x44], row["file_range"])
                self.assertEqual([ROM_BASE + start, ROM_BASE + start + 0x44], row["gba_range"])
                self.assertEqual(rom[start : start + 4].hex(), row["prefix_bytes_hex"])
                self.assertEqual(list(rom[start : start + 4]), row["prefix_bytes"])
                for group_name, group_offset in (("win", 0x04), ("lose", 0x24)):
                    group = row[group_name]
                    self.assertEqual([start + group_offset, start + group_offset + 0x20], group["file_range"])
                    self.assertEqual(4, len(group["predicates"]))
                    for slot, predicate in enumerate(group["predicates"]):
                        slot_start = start + group_offset + slot * 8
                        raw = rom[slot_start : slot_start + 8]
                        self.assertEqual(slot, predicate["slot_index"])
                        self.assertEqual([slot_start, slot_start + 8], predicate["file_range"])
                        self.assertEqual(raw.hex(), predicate["raw_hex"])
                        self.assertEqual(raw[0], predicate["condition_type"])
                        self.assertEqual(raw[1], predicate["arg0"])
                        self.assertEqual(raw[2], predicate["arg1"])
                        self.assertEqual(raw[3], predicate["byte3_raw"])
                        self.assertEqual(int.from_bytes(raw[4:], "little"), predicate["payload_word_le_raw"])

    def test_independent_raw_consumer_decoder_matches_and_has_exact_evidence(self):
        exporter, verifier = self._mods()
        rom = ROM_PATH.read_bytes()
        exported = exporter.decode_consumer_contract(rom)
        independent = verifier.independent_consumer_contract(rom)
        self.assertEqual(exported, independent)
        self.assertEqual(list(INTERPRETER_RANGE), exported["interpreter"]["file_range"])
        self.assertEqual(INTERPRETER_SHA256, exported["interpreter"]["sha256"])
        self.assertEqual(list(CORE_SLICE_RANGE), exported["core_selector_slice"]["file_range"])
        self.assertEqual(CORE_SLICE_SHA256, exported["core_selector_slice"]["sha256"])
        self.assertEqual([0x02026804, 0x08594758], exported["literals"]["words_le"])
        self.assertEqual(DISPATCH_TARGETS, exported["dispatch"]["targets"])
        self.assertEqual(DISPATCH_SHA256, exported["dispatch"]["sha256"])
        self.assertEqual(CALLER_SHA256, exported["caller"]["sha256"])
        formula = exported["formula"]
        self.assertEqual(0xCC, formula["battle_stride"])
        self.assertEqual(0x44, formula["variant_stride"])
        self.assertEqual(0x20, formula["group_stride"])
        self.assertEqual(8, formula["predicate_stride"])
        self.assertEqual(4, formula["slots_per_group"])
        self.assertEqual(2, formula["group_count"])
        required = {
            0x07781C: 0x4A13,
            0x07781E: 0x7851,
            0x077820: 0x20CC,
            0x077822: 0x1C0B,
            0x077824: 0x4343,
            0x077826: 0x7891,
            0x077828: 0x0108,
            0x07782A: 0x1840,
            0x07782C: 0x0080,
            0x07782E: 0x4910,
            0x07783C: 0x2700,
            0x077840: 0x0149,
            0x07784C: 0x3004,
            0x077852: 0x00F9,
            0x077856: 0x7828,
            0x077858: 0x3801,
            0x07785A: 0x2808,
        }
        decoded = {item["file_offset"]: item["halfword"] for item in exported["raw_instructions"]}
        for offset, halfword in required.items():
            with self.subTest(offset=hex(offset)):
                self.assertEqual(halfword, decoded[offset])
        self.assertEqual(4, exported["loops"]["slot"]["count"])
        self.assertEqual(2, exported["loops"]["group"]["count"])
        self.assertEqual(0x07784A, exported["loops"]["slot"]["back_edge_file_offset"])
        self.assertEqual(0x07783C, exported["loops"]["group"]["back_edge_file_offset"])

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
            self.assertEqual(
                {p.name: _sha(p.read_bytes()) for p in first.iterdir()},
                {p.name: _sha(p.read_bytes()) for p in second.iterdir()},
            )
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

    def test_independent_verifier_accepts_artifact_and_cli_is_deterministic(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            report_path = Path(temporary) / "report.json"
            exporter.export_artifact(ROOT, output)
            first = verifier.verify_artifact(ROOT, output)
            second = verifier.verify_artifact(ROOT, output)
            self.assertEqual(first, second)
            self.assertTrue(first["verified"], first["errors"])
            self.assertEqual(VERIFY_SCHEMA, first["schema"])
            self.assertEqual([], first["errors"])
            result = subprocess.run(
                [
                    "python3",
                    "tools/verify_rom_battle_condition_records.py",
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    str(output),
                    "--output",
                    str(report_path),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(first, json.loads(result.stdout))
            self.assertEqual(first, _json(report_path))
            self.assertEqual(_canonical(first), report_path.read_bytes())

    def test_verifier_source_forbids_product_and_coverage_dependencies(self):
        source_path = ROOT / "tools/verify_rom_battle_condition_records.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        for imported in imports:
            self.assertNotIn("export_rom_battle_condition_records", imported)
            self.assertNotIn("analyze_battle_condition_interpreter", imported)
            self.assertNotIn("audit_rom_byte_coverage", imported)
            self.assertNotIn("audit_reverse_engineering_proof", imported)
        for forbidden_literal in (
            "analyze_battle_condition_interpreter",
            "audit_rom_byte_coverage",
            "audit_reverse_engineering_proof",
            "sequel/rom-byte-coverage.json",
            "private_builder",
        ):
            self.assertNotIn(forbidden_literal, source)
        self.assertNotIn("subprocess", imports)
        self.assertEqual(set(), _forbidden_dynamic_calls(source))
        dynamic_canaries = {
            "import importlib\nimportlib.import_module('tools.export_rom_battle_condition_records')\n": "importlib.import_module",
            "import importlib as il\nil.import_module('tools.export_rom_battle_condition_records')\n": "importlib.import_module",
            "from importlib import import_module\nimport_module('tools.export_rom_battle_condition_records')\n": "importlib.import_module",
            "import os\nos.system('python3 tools/analyze_battle_condition_interpreter.py')\n": "os.system",
            "import os as operating_system\noperating_system.system('python3 tools/analyze_battle_condition_interpreter.py')\n": "os.system",
            "from os import system\nsystem('python3 tools/analyze_battle_condition_interpreter.py')\n": "os.system",
            "import runpy\nrunpy.run_path('tools/audit_rom_byte_coverage.py')\n": "runpy.run_path",
            "import runpy as rp\nrp.run_path('tools/audit_rom_byte_coverage.py')\n": "runpy.run_path",
            "__import__('tools.audit_reverse_engineering_proof')\n": "__import__",
            "exec(compile('pass', '<x>', 'exec'))\n": "exec",
            "import builtins as b\nb.exec(b.compile('pass', '<x>', 'exec'))\n": "exec",
        }
        for canary, expected in dynamic_canaries.items():
            with self.subTest(dynamic_call=expected):
                self.assertIn(expected, _forbidden_dynamic_calls(canary))

    def test_consumer_mutations_fail_closed_for_exporter_and_verifier(self):
        exporter, verifier = self._mods()
        original = ROM_PATH.read_bytes()
        mutation_offsets = {
            "table byte": TABLE_RANGE[0],
            "battle-stride halfword": 0x077820,
            "variant-stride sequence": 0x077828,
            "variant-stride add": 0x07782A,
            "table-base literal": 0x077870,
            "group-stride halfword": 0x077840,
            "prefix-skip halfword": 0x07784C,
            "predicate-stride halfword": 0x077852,
            "slot-loop bound": 0x077B40,
            "group-loop bound": 0x077B4E,
            "dispatch table word": 0x077878,
        }
        for label, offset in mutation_offsets.items():
            mutated = bytearray(original)
            mutated[offset] ^= 0x01
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    exporter.decode_consumer_contract(bytes(mutated))
                with self.assertRaises(ValueError):
                    verifier.independent_consumer_contract(bytes(mutated))

    def test_payload_binary_implementation_missing_and_manifest_mutations_fail_closed(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            exporter.export_artifact(ROOT, source)
            payload = _json(source / JSON_NAME)

            def fresh(name: str) -> Path:
                target = Path(temporary) / name
                shutil.copytree(source, target)
                return target

            mutated = fresh("json")
            changed = _json(mutated / JSON_NAME)
            changed["variants"][0]["prefix_bytes"][0] ^= 1
            (mutated / JSON_NAME).write_bytes(_canonical(changed))
            self.assertFalse(verifier.verify_artifact(ROOT, mutated)["verified"])

            mutated = fresh("binary")
            raw = bytearray((mutated / BIN_NAME).read_bytes())
            raw[0] ^= 1
            (mutated / BIN_NAME).write_bytes(raw)
            self.assertFalse(verifier.verify_artifact(ROOT, mutated)["verified"])

            mutated = fresh("identity")
            changed = _json(mutated / JSON_NAME)
            changed["implementation"]["exporter"]["sha256"] = "0" * 64
            (mutated / JSON_NAME).write_bytes(_canonical(changed))
            self.assertFalse(verifier.verify_artifact(ROOT, mutated)["verified"])

            mutated = fresh("missing")
            (mutated / JSON_NAME).unlink()
            self.assertFalse(verifier.verify_artifact(ROOT, mutated)["verified"])

            final = Path(temporary) / "final"
            shutil.copytree(source, final)
            run_base = "build/experiments/active/battle-condition-records/codex-test"
            candidate = f"{run_base}/candidate"
            producer_command = [
                "python3",
                "-u",
                "tools/export_rom_battle_condition_records.py",
                "--root",
                ".",
                "--out-dir",
                candidate,
            ]
            verifier_report_path = f"{run_base}/candidate-verify.report.json"
            verifier_command = [
                "python3",
                "-u",
                "tools/verify_rom_battle_condition_records.py",
                "--root",
                ".",
                "--artifact-dir",
                candidate,
                "--output",
                verifier_report_path,
            ]

            def guard(command: list[str]) -> dict:
                return {
                    "reason": "completed",
                    "exit_code": 0,
                    "child_pid": 123,
                    "peak_tree_rss_mib": 1.0,
                    "protection_backend": "posix-process-group",
                    "degraded": False,
                    "command": command,
                    "cwd": str(ROOT.resolve()),
                    "started_at": "2026-08-22T00:00:00Z",
                    "finished_at": "2026-08-22T00:00:01Z",
                }

            candidate_report = verifier.verify_artifact(ROOT, final)
            self.assertTrue(candidate_report["verified"], candidate_report["errors"])
            manifest = {
                "schema": PROMOTION_SCHEMA,
                "artifact_schema": SCHEMA,
                "artifact_status": "accepted",
                "files": {
                    JSON_NAME: _sha((final / JSON_NAME).read_bytes()),
                    BIN_NAME: _sha((final / BIN_NAME).read_bytes()),
                },
                "implementation": payload["implementation"],
                "rom": payload["rom"],
                "scope": payload["scope"],
                "producer": {
                    "command": producer_command,
                    "receipt": _evidence(
                        f"{run_base}/guard-candidate-export.json",
                        guard(producer_command),
                    ),
                },
                "verifier": {
                    "command": verifier_command,
                    "exit_code": 0,
                    "receipt": _evidence(
                        f"{run_base}/guard-candidate-verify.json",
                        guard(verifier_command),
                    ),
                    "report": _evidence(verifier_report_path, candidate_report),
                },
            }
            (final / "manifest.json").write_bytes(_canonical(manifest))
            self.assertTrue(verifier.verify_artifact(ROOT, final)["verified"])

            def rejected(label: str, mutate) -> None:
                changed = json.loads(json.dumps(manifest))
                mutate(changed)
                (final / "manifest.json").write_bytes(_canonical(changed))
                report = verifier.verify_artifact(ROOT, final)
                self.assertFalse(report["verified"], f"{label}: {report}")

            rejected("file hash", lambda value: value["files"].__setitem__(BIN_NAME, "0" * 64))
            rejected("missing implementation", lambda value: value.pop("implementation"))
            rejected(
                "implementation identity",
                lambda value: value["implementation"]["verifier"].__setitem__("sha256", "0" * 64),
            )
            rejected("ROM identity", lambda value: value["rom"].__setitem__("sha256", "0" * 64))
            rejected(
                "nonclaim changed",
                lambda value: value["scope"]["non_claims"].__setitem__(
                    "right_gap_padding_claimed", True
                ),
            )
            rejected("missing producer", lambda value: value.pop("producer"))

            def bad_producer_command(value: dict) -> None:
                command = value["producer"]["command"][:-2]
                value["producer"]["command"] = command
                value["producer"]["receipt"] = _evidence(
                    value["producer"]["receipt"]["path"], guard(command)
                )

            rejected("producer command", bad_producer_command)

            def bad_verifier_command(value: dict) -> None:
                command = value["verifier"]["command"][:5] + value["verifier"]["command"][7:]
                value["verifier"]["command"] = command
                value["verifier"]["receipt"] = _evidence(
                    value["verifier"]["receipt"]["path"], guard(command)
                )

            rejected("verifier command", bad_verifier_command)

            def receipt_exit_one(value: dict) -> None:
                receipt = value["verifier"]["receipt"]
                content = json.loads(base64.b64decode(receipt["content_base64"]))
                content["exit_code"] = 1
                value["verifier"]["receipt"] = _evidence(receipt["path"], content)

            rejected("verifier receipt exit", receipt_exit_one)

            def report_not_verified(value: dict) -> None:
                report_evidence = value["verifier"]["report"]
                content = json.loads(base64.b64decode(report_evidence["content_base64"]))
                content["verified"] = False
                content["errors"] = ["forged"]
                value["verifier"]["report"] = _evidence(report_evidence["path"], content)

            rejected("verifier report", report_not_verified)
            rejected(
                "receipt hash",
                lambda value: value["verifier"]["receipt"].__setitem__("sha256", "0" * 64),
            )
            rejected("unexpected manifest field", lambda value: value.__setitem__("extra", True))

    def test_artifact_members_and_boundaries_are_exact(self):
        exporter, verifier = self._mods()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            exporter.export_artifact(ROOT, output)
            payload = _json(output / JSON_NAME)
            binary = (output / BIN_NAME).read_bytes()
            rom = ROM_PATH.read_bytes()
            self.assertEqual(TABLE_SIZE, len(binary))
            self.assertEqual(rom[TABLE_RANGE[0] : TABLE_RANGE[1]], binary)
            self.assertEqual(TABLE_RANGE[1], payload["table"]["file_range"][1])
            self.assertEqual(TABLE_GBA_RANGE[1], payload["table"]["gba_range"][1])
            self.assertNotIn("left_neighbor", payload)
            self.assertNotIn("right_neighbor", payload)
            self.assertNotIn("coverage", payload)
            encoded = (output / JSON_NAME).read_text(encoding="utf-8")
            self.assertNotIn("0x00594757", encoded)
            self.assertNotIn("0x00596CCC", encoded)
            self.assertEqual({JSON_NAME, BIN_NAME}, {p.name for p in output.iterdir()})
            (output / "foreign").write_text("x", encoding="utf-8")
            report = verifier.verify_artifact(ROOT, output)
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
