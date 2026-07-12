#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_relocated_chapter_runtime_probe import build_relocated_probe


ROOT = Path(__file__).resolve().parents[1]


class RelocatedChapterRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()
        cls.spec = ROOT / "sequel/content/story-b/scenario-39-relocation.json"

    def test_layers_production_payload_and_pointer_on_existing_trace_probe(self):
        patched = build_relocated_probe(self.base, self.spec)
        self.assertEqual(
            int.from_bytes(patched[0x60DF0:0x60DF4], "little"),
            0x085F8000,
        )
        self.assertEqual(patched[0x5F8000:0x5F81AE], self.base[0x31281:0x3142F])
        self.assertNotEqual(patched[0x8F5A4:0x8F5A6], self.base[0x8F5A4:0x8F5A6])
        self.assertNotEqual(patched[0x977D8:0x977DC], self.base[0x977D8:0x977DC])


if __name__ == "__main__":
    unittest.main()
