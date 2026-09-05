from __future__ import annotations

import hashlib
import ast
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-battle-condition-result-text-v1"
JSON_NAME = "battle-condition-result-text.json"
BIN_NAME = "battle-condition-result-text.bin"
EXPECTED_SUMMARY = {
    "condition_slot_count": 1128,
    "empty_slot_count": 898,
    "active_slot_count": 230,
    "distinct_target_count": 219,
    "record_count": 219,
    "record_bytes": 3961,
    "inter_record_gap_bytes_unclaimed": 2782,
    "parse_failure_count": 0,
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class BattleConditionResultTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_battle_condition_result_text import export_artifact

        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / SCHEMA
        cls.payload = export_artifact(ROOT, cls.out)
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_complete_raw_denominator_and_exact_records(self):
        self.assertEqual(EXPECTED_SUMMARY, self.payload["summary"])
        self.assertEqual(
            {"0": 898, "1": 155, "2": 11, "3": 18, "6": 8, "7": 16, "8": 16, "9": 6},
            self.payload["condition_denominator"]["type_counts"],
        )
        self.assertEqual(
            "7d81f7ec06a8969969305002afc307da90b7f3787f8f958fc5799c72ed844fe4",
            self.payload["records_range_vector_sha256"],
        )
        records = self.payload["records"]
        self.assertEqual([0x7F1D, 0x7F2E], records[0]["range"])
        self.assertEqual([0x9963, 0x9974], records[-1]["range"])
        self.assertTrue(all(a["range"][1] <= b["range"][0] for a, b in zip(records, records[1:])))
        packed = (self.out / BIN_NAME).read_bytes()
        self.assertEqual(3961, len(packed))
        self.assertEqual("9826a706b7c4e840117c5ff1a3a6c9d06057cac9188c66f2bd523592cf533d91", hashlib.sha256(packed).hexdigest())
        self.assertEqual(packed, b"".join(self.rom[a:b] for a, b in (r["range"] for r in records)))
        claims = self.payload["promotion"]["claims"]
        self.assertEqual((219, 3961), (len(claims), self.payload["promotion"]["promotion_bytes"]))
        self.assertEqual(
            [record["range"] for record in records],
            [claim["range"] for claim in claims],
        )
        self.assertEqual(
            {"battle_condition_result_renderer_text"},
            {claim["primary_class"] for claim in claims},
        )

    def test_consumer_and_handler_field_contract(self):
        evidence = self.payload["consumer_evidence"]
        self.assertEqual(
            {"1": [1], "2": [], "3": [1, 2], "4": [], "5": [1, 2], "6": [1], "7": [1], "8": [1], "9": [1]},
            evidence["handler_row_byte_reads"],
        )
        self.assertEqual([0x77B70, 0x77B7E], evidence["common_payload_loads"]["win"]["range"])
        self.assertEqual([0x77B90, 0x77BA0], evidence["common_payload_loads"]["lose"]["range"])
        self.assertEqual("3fe6370ac0e3a76325d5907b2e113a403f21712bb4299af26cb970336938dc89", evidence["result_renderer"]["sha256"])
        self.assertEqual("5fcd96135c0633225308088ddfc51ca18ef151d1f317a55c70a3a7adb65044b1", evidence["bridge"]["sha256"])
        self.assertEqual("0x080667A0", evidence["result_renderer"]["renderer_call_target"])
        self.assertEqual("0x0806626C", evidence["bridge"]["parser_target"])

    def test_scope_excludes_aliases_gaps_script_and_safety_claims(self):
        scope = self.payload["scope"]
        for key in (
            "inter_record_gaps_claimed", "tail_9974_9980_claimed", "script_9980_9986_claimed",
            "tail_9986_9f2e_claimed", "positions_group47_independent_provenance_claimed",
            "natural_reachability_claimed", "unicode_decoding_claimed", "editing_safety_claimed",
        ):
            self.assertIs(scope[key], False)
        self.assertIn("physical alias", " ".join(self.payload["limitations"]))

    def test_independent_verifier_and_tamper_fail_closed(self):
        from tools.verify_rom_battle_condition_result_text import verify_artifact

        source = (ROOT / "tools/verify_rom_battle_condition_result_text.py").read_text()
        imports = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertFalse(any(name.endswith("export_rom_battle_condition_result_text") for name in imports))
        report = verify_artifact(ROOT, self.out)
        self.assertTrue(report["verified"], report["errors"])
        with tempfile.TemporaryDirectory() as td:
            def fresh(name: str) -> Path:
                dst = Path(td) / name
                shutil.copytree(self.out, dst)
                return dst
            for name, mutate in (
                ("binary", lambda p: (p / BIN_NAME).write_bytes(bytes([((p / BIN_NAME).read_bytes()[0] ^ 1)]) + (p / BIN_NAME).read_bytes()[1:])),
                ("payload", lambda p: (p / JSON_NAME).write_bytes(canonical({**json.loads((p / JSON_NAME).read_text()), "summary": {**EXPECTED_SUMMARY, "record_bytes": 3960}}))),
                ("manifest", lambda p: (p / "manifest.json").write_text("{}\n")),
                ("foreign", lambda p: (p / "foreign").write_text("x")),
            ):
                dst = fresh(name); mutate(dst)
                self.assertFalse(verify_artifact(ROOT, dst)["verified"], name)

    def test_raw_rom_mutations_and_safe_publication(self):
        import tools.export_rom_battle_condition_result_text as exporter
        import tools.verify_rom_battle_condition_result_text as verifier

        raw = bytearray(self.rom)
        for offset in (0x594828, 0x59482C, 0x77B70, 0x777E4, 0x667B8, 0x6626C, 0x53D644, 0x7F1D):
            changed = bytearray(raw); changed[offset] ^= 1
            with self.subTest(offset=hex(offset)):
                with self.assertRaises(ValueError): exporter.build_payload(ROOT, bytes(changed))
                with self.assertRaises(ValueError): verifier.rebuild_expected(ROOT, bytes(changed))
        unrelated = bytearray(raw)
        unrelated[0x300000] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            exporter.build_payload(ROOT, bytes(unrelated))
        with tempfile.TemporaryDirectory() as td:
            foreign = Path(td) / "foreign"; foreign.mkdir(); (foreign / "keep").write_text("x")
            with self.assertRaisesRegex(ValueError, "non-empty|foreign"): exporter.export_artifact(ROOT, foreign)
            link = Path(td) / "link"; link.symlink_to(Path(td), target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"): exporter.export_artifact(ROOT, link / "x")
        with self.assertRaisesRegex(ValueError, "repository root"): exporter.export_artifact(ROOT, ROOT)

    def test_exclusive_publish_does_not_replace_an_empty_destination(self):
        import tools.export_rom_battle_condition_result_text as exporter

        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            source = parent / "source"
            destination = parent / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "payload").write_text("new")
            with self.assertRaises(FileExistsError):
                exporter._publish_exclusive(source, destination)
            self.assertTrue(destination.is_dir())
            self.assertFalse((destination / "payload").exists())
            self.assertTrue((source / "payload").exists())


if __name__ == "__main__":
    unittest.main()
