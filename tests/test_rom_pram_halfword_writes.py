#!/usr/bin/env python3
"""The original ROM's direct palette-RAM half-word writes, pinned.

Round 25 located the per-frame write that gives the S49 field unit its
outlined look: the function at ``0x0806A7A0`` rewrites palette entry 15 of
the unit's OBJ palette every frame with a 32-frame triangle wave.  The
finding is now a reproducible inventory instead of a claim:

* the exporter censuses every 32-bit literal that points into PRAM and
  resolves the Thumb ``LDR`` that loads it and the function it belongs to;
* it decodes the known writer and records the instructions around the store,
  so the address expression (``0x0500021E + bank * 32``) and the value
  expression (``(v << 10) | (v << 5)``) can be checked against the bytes;
* the receipt states plainly which instruction forms it covers and which it
  does not.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import export_rom_pram_halfword_writes as exporter  # noqa: E402

ROM = ROOT / "rom/base.gba"
RECEIPT = ROOT / "artifacts/rom-pram-halfword-writes-v1/pram-halfword-writes.json"
KNOWN_FUNCTION = 0x0806A7A0
KNOWN_STORE = 0x0806A7EE


class PramHalfwordInventoryTest(unittest.TestCase):
    def test_the_rom_hash_gate_rejects_a_modified_rom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken.gba"
            shutil.copy(ROM, broken)
            data = bytearray(broken.read_bytes())
            data[0x1000] ^= 0x01
            broken.write_bytes(bytes(data))
            with self.assertRaises(exporter.PramInventoryError):
                exporter.build_inventory(broken)

    def test_the_receipt_is_byte_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = exporter.write_inventory(
                exporter.build_inventory(ROM), Path(directory) / "a"
            )
            second = exporter.write_inventory(
                exporter.build_inventory(ROM), Path(directory) / "b"
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_the_known_outline_write_is_confirmed(self) -> None:
        payload = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertTrue(payload["scope"]["known_site_confirmed"])
        known = payload["known_outline_write"]
        self.assertEqual(known["function"], KNOWN_FUNCTION)
        self.assertEqual(known["store"], KNOWN_STORE)
        store = known["store_instruction"]
        self.assertIsNotNone(store, "the known store instruction was not decoded")
        self.assertEqual(store["address"], KNOWN_STORE)
        self.assertEqual(store["mnemonic"], "strh")

    def test_the_known_literals_resolve_to_their_loads_and_function(self) -> None:
        payload = json.loads(RECEIPT.read_text(encoding="utf-8"))
        by_address = {
            entry["literal_address"]: entry for entry in payload["entries"]
        }
        for literal, reference in ((0x0806A7F4, 0x0806A7E4), (0x0806A808, 0x0806A7FC)):
            entry = by_address[literal]
            self.assertEqual(entry["literal_value"], "0x0500021E")
            self.assertIn(reference, entry["referenced_by"])
            self.assertEqual(entry["function"], KNOWN_FUNCTION)

    def test_the_wave_computation_is_visible_in_the_decoded_window(self) -> None:
        """The triangle wave must be readable in the receipt's own bytes."""
        payload = json.loads(RECEIPT.read_text(encoding="utf-8"))
        window = payload["known_outline_write"]["window"]
        text = " | ".join(
            f"{record['mnemonic']} {record['operands']}" for record in window
        )
        self.assertIn("ands r0, r1", text)
        self.assertIn("lsls r0, r0, #1", text)
        self.assertIn("adds r0, #1", text)
        self.assertIn("strh r1, [r0]", text)

    def test_the_scope_names_what_is_and_is_not_covered(self) -> None:
        payload = json.loads(RECEIPT.read_text(encoding="utf-8"))
        scope = payload["scope"]
        self.assertIn("literal", scope["covers"])
        self.assertIn("does_not_cover", scope)
        self.assertTrue(scope["does_not_cover"].strip())

    def test_the_census_finds_pram_literals(self) -> None:
        payload = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertGreater(payload["counts"]["pram_literal_occurrences"], 0)
        self.assertGreater(payload["counts"]["distinct_pram_literal_values"], 0)
        for entry in payload["entries"]:
            self.assertTrue(
                0x05000000 <= int(entry["literal_value"], 16) <= 0x050003FF
            )


if __name__ == "__main__":
    unittest.main()
