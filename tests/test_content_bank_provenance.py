#!/usr/bin/env python3
"""Every content bank must be able to say where its bytes came from.

``docs/butano-wiring-roadmap.md`` (W3, action 2) asks that the 34 content
banks each answer "which reverse family / which note", so the sink side stops
being a gray zone.  The answer has to be **true**, not merely present, so
these tests pin:

* every bank carries a ``_provenance`` block with the required fields;
* the block's ROM hash is the hash of the ROM in this tree;
* the ROM offset and size agree with the bank's own table fields;
* a named reverse family exists in the reverse work tree's manifest;
* a named note exists on disk;
* a bank with **no** family and **no** note says so explicitly, instead of
  leaving the reader to guess;
* the annotator is idempotent -- running it twice must not change a byte.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "annotate_content_bank_provenance.py"
REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")
CONTENT = ROOT / "sequel" / "content"

REQUIRED_FIELDS = (
    "rom",
    "extractor",
    "reverse_family",
    "reverse_family_candidates",
    "reverse_family_state",
    "reverse_evidence",
    "unattributed_reason",
)


class ContentBankProvenanceTest(unittest.TestCase):
    def _banks(self) -> list[Path]:
        banks = sorted(CONTENT.glob("*/bank.json"))
        if not banks:
            self.skipTest("no content banks in this tree")
        return banks

    def test_every_bank_carries_the_provenance_block(self) -> None:
        for path in self._banks():
            with self.subTest(bank=path.parent.name):
                bank = json.loads(path.read_text(encoding="utf-8"))
                self.assertIn("_provenance", bank)
                block = bank["_provenance"]
                for field in REQUIRED_FIELDS:
                    self.assertIn(field, block)

    def test_the_rom_hash_is_this_trees_rom(self) -> None:
        import hashlib

        rom = ROOT / "rom" / "base.gba"
        digest = hashlib.sha256(rom.read_bytes()).hexdigest()
        for path in self._banks():
            with self.subTest(bank=path.parent.name):
                bank = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(bank["_provenance"]["rom"]["sha256"], digest)

    def test_the_rom_fields_agree_with_the_bank(self) -> None:
        for path in self._banks():
            with self.subTest(bank=path.parent.name):
                bank = json.loads(path.read_text(encoding="utf-8"))
                rom = bank["_provenance"]["rom"]
                if isinstance(bank.get("table_offset"), int):
                    self.assertEqual(rom["offset"], bank["table_offset"])
                if (
                    isinstance(bank.get("entry_count"), int)
                    and isinstance(bank.get("entry_size"), int)
                ):
                    self.assertEqual(
                        rom["size"], bank["entry_count"] * bank["entry_size"]
                    )

    def test_a_named_family_exists_in_the_reverse_tree(self) -> None:
        for path in self._banks():
            with self.subTest(bank=path.parent.name):
                bank = json.loads(path.read_text(encoding="utf-8"))
                family = bank["_provenance"]["reverse_family"]
                if family is None:
                    continue
                manifest = (
                    REVERSE_ROOT / "artifacts" / family / "manifest.json"
                )
                self.assertTrue(manifest.is_file(), family)

    def test_a_named_note_exists_on_disk(self) -> None:
        for path in self._banks():
            with self.subTest(bank=path.parent.name):
                bank = json.loads(path.read_text(encoding="utf-8"))
                for note in bank["_provenance"]["reverse_evidence"]:
                    self.assertTrue((ROOT / note).is_file(), note)

    def test_a_bank_without_a_source_says_so(self) -> None:
        for path in self._banks():
            with self.subTest(bank=path.parent.name):
                bank = json.loads(path.read_text(encoding="utf-8"))
                block = bank["_provenance"]
                if block["reverse_family"] is None and not block["reverse_evidence"]:
                    self.assertTrue(block["unattributed_reason"])

    def test_the_annotator_is_idempotent(self) -> None:
        if not REVERSE_ROOT.is_dir():
            self.skipTest("reverse work tree not present")
        before = {
            path: path.read_bytes() for path in self._banks()
        }
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(ROOT),
                "--reverse-root",
                str(REVERSE_ROOT),
                "--out-dir",
                str(ROOT / "build" / "bank-provenance-check"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for path, payload in before.items():
            with self.subTest(bank=path.parent.name):
                self.assertEqual(path.read_bytes(), payload)

    def test_the_check_mode_accepts_the_current_tree(self) -> None:
        if not REVERSE_ROOT.is_dir():
            self.skipTest("reverse work tree not present")
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(ROOT),
                    "--reverse-root",
                    str(REVERSE_ROOT),
                    "--out-dir",
                    str(Path(tmp) / "out"),
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
