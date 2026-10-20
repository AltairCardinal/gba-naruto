#!/usr/bin/env python3
"""Tests for the sprite frame descriptor table (0x53EE98) extractor.

The table is live (three native readers, 10-byte stride).  The extractor
must therefore *check* rather than merely print: a ROM whose layout does
not match what it assumes has to make it fail loudly.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.frame_descriptors import (
    LITERAL_POOL_ADDRESS,
    TABLE_BASE,
    read_records,
    validate,
)

REPO = Path(__file__).resolve().parents[1]
BASE_ROM = REPO / "rom/base.gba"


class FrameDescriptorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = BASE_ROM.read_bytes()

    def test_table_geometry(self):
        records = read_records(self.rom)
        self.assertEqual(len(records), 15)
        self.assertEqual(records[0]["offset"], TABLE_BASE)
        # the list must be terminated by a record whose field_0 == -1
        self.assertTrue(records[-1]["list_end"])
        self.assertEqual(records[-1]["field_0"], -1)
        # and the records are 10 bytes apart
        for previous, current in zip(records, records[1:]):
            self.assertEqual(current["offset"] - previous["offset"], 10)

    def test_walk_end_flag_is_observed(self):
        records = read_records(self.rom)
        # field_8 != 0 ends a walk, == 0 continues to the next record
        self.assertTrue(any(r["walk_end"] for r in records))
        self.assertTrue(any(not r["walk_end"] for r in records))

    def test_validator_accepts_the_real_rom(self):
        self.assertEqual(validate(self.rom, read_records(self.rom)), [])

    def test_validator_rejects_a_rom_whose_layout_differs(self):
        """A wrong literal-pool value must be reported, not ignored."""
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "base.gba"
            shutil.copyfile(BASE_ROM, copy)
            raw = bytearray(copy.read_bytes())
            pool = LITERAL_POOL_ADDRESS - 0x08000000
            raw[pool:pool + 4] = (0x0853EE99).to_bytes(4, "little")
            problems = validate(bytes(raw), read_records(bytes(raw)))
        self.assertTrue(problems)
        self.assertTrue(any("literal" in p for p in problems))

    def test_validator_rejects_a_broken_terminator(self):
        """Removing the -1 terminator must be caught."""
        raw = bytearray(self.rom)
        # overwrite the terminator record's field_0 with 0
        off = TABLE_BASE + 14 * 10
        raw[off:off + 2] = (0).to_bytes(2, "little")
        problems = validate(bytes(raw), read_records(bytes(raw)))
        self.assertTrue(problems)
        self.assertTrue(any("terminate" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
