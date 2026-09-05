#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_exporter():
    try:
        from tools import export_rom_cfg_proven_roots_v16_consumed_literals as module
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v16 consumed-literals exporter is absent") from error
    return module


class ExportV16ConsumedLiteralsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = load_exporter()
        cls.payload = cls.exporter.build_payload(ROOT)

    def test_exact_binding_and_promotion_denominators(self):
        payload = self.payload
        self.assertEqual(51, len(payload["bindings"]))
        self.assertEqual(51, len(payload["target_words"]))
        self.assertEqual(51, len(payload["promotion"]["claims"]))
        self.assertEqual(204, payload["promotion"]["union_bytes"])
        self.assertEqual(204, sum(b - a for a, b in payload["promotion"]["union_ranges"]))
        self.assertEqual(147160, payload["coverage_baseline"]["unknown_bytes"])
        self.assertEqual(204, payload["coverage_projection"]["promoted_bytes"])
        self.assertEqual(146956, payload["coverage_projection"]["remaining_unknown_bytes"])
        self.assertEqual(147160, 204 + 146956)

    def test_every_binding_has_raw_word_hash_and_owner(self):
        rom = (ROOT / "rom/base.gba").read_bytes()
        offsets = []
        targets = []
        for row in self.payload["bindings"]:
            source = row["source_file_offset"]
            target = row["target_file_offset"]
            halfword = int.from_bytes(rom[source : source + 2], "little")
            self.assertEqual(0x4800, halfword & 0xF800)
            self.assertEqual(((source + 4) & ~3) + (halfword & 255) * 4, target)
            self.assertEqual(rom[source : source + 2].hex(), row["source_raw_hex"])
            self.assertEqual(rom[target : target + 4].hex(), row["word_raw_hex"])
            self.assertEqual(hashlib.sha256(rom[target : target + 4]).hexdigest(), row["word_sha256"])
            self.assertEqual("rom-cfg-proven-roots-v16", row["owner"]["artifact"])
            self.assertLessEqual(row["owner"]["range"][0], source)
            self.assertLess(source + 2, row["owner"]["range"][1] + 1)
            offsets.append(source)
            targets.append(target)
        self.assertEqual(sorted(offsets), offsets)
        self.assertEqual(51, len(set(targets)))
        self.assertTrue(all(target % 4 == 0 for target in targets))

    def test_targets_are_baseline_unknown_and_disjoint_from_v16_code(self):
        code_ranges = self.payload["source_denominator"]["ranges"]
        for word in self.payload["target_words"]:
            target = word["target_file_offset"]
            self.assertEqual("unknown", word["baseline_owner"]["primary_class"])
            self.assertFalse(any(target < end and start < target + 4 for start, end in code_ranges))

    def test_export_is_closed_and_does_not_import_verifier(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "candidate"
            self.exporter.export(ROOT, output)
            self.assertEqual({"manifest.json", self.exporter.PAYLOAD_NAME}, {p.name for p in output.iterdir()})
            manifest = json.loads((output / "manifest.json").read_text())
            payload = output / self.exporter.PAYLOAD_NAME
            self.assertEqual(hashlib.sha256(payload.read_bytes()).hexdigest(), manifest["files"][payload.name]["sha256"])
        tree = ast.parse((ROOT / "tools/export_rom_cfg_proven_roots_v16_consumed_literals.py").read_text())
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
        self.assertFalse(any("verify_rom_cfg_proven_roots_v16_consumed_literals" in name for name in imports))

    def test_rom_mutation_fails_closed(self):
        rom = bytearray((ROOT / "rom/base.gba").read_bytes())
        rom[0x61152] ^= 1
        with self.assertRaisesRegex(ValueError, "ROM identity"):
            self.exporter.build_payload(ROOT, bytes(rom))


if __name__ == "__main__":
    unittest.main()
