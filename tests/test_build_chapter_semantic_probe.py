#!/usr/bin/env python3
"""TDD contract for a codec-authored primary chapter runtime probe."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_chapter_semantic_probe import (
    DISPATCH_HOOK,
    DISPATCH_STUB_OFFSET,
    DISPATCH_STUB_SIZE,
    PRIMARY_SCENARIO_39_POINTER,
    SCRIPT_ADDRESS,
    SCRIPT_OFFSET,
    SCRIPT_REGION_SIZE,
    SELECTOR_CAPTURE_HOOK,
    SELECTOR_STUB_OFFSET,
    SELECTOR_STUB_SIZE,
    _dispatch_stub,
    _selector_stub,
    build_probe,
)


ROOT = Path(__file__).resolve().parents[1]
ROM_BASE = 0x08000000


class ChapterSemanticProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_places_codec_script_and_redirects_only_primary_scenario_39(self):
        patched = build_probe(self.base)
        self.assertEqual(
            patched[PRIMARY_SCENARIO_39_POINTER:PRIMARY_SCENARIO_39_POINTER + 4],
            SCRIPT_ADDRESS.to_bytes(4, "little"),
        )
        self.assertEqual(patched[SCRIPT_OFFSET:SCRIPT_OFFSET + 4], bytes.fromhex("1a280200"))
        self.assertEqual(
            patched[SCRIPT_OFFSET + 4:SCRIPT_OFFSET + SCRIPT_REGION_SIZE],
            bytes(SCRIPT_REGION_SIZE - 4),
        )

    def test_changes_only_pointer_hooks_stubs_and_script_region(self):
        patched = build_probe(self.base)
        changed = {i for i, pair in enumerate(zip(self.base, patched)) if pair[0] != pair[1]}
        allowed = (
            set(range(PRIMARY_SCENARIO_39_POINTER, PRIMARY_SCENARIO_39_POINTER + 4))
            | set(range(SELECTOR_CAPTURE_HOOK - ROM_BASE, SELECTOR_CAPTURE_HOOK - ROM_BASE + 4))
            | set(range(DISPATCH_HOOK - ROM_BASE, DISPATCH_HOOK - ROM_BASE + 4))
            | set(range(SELECTOR_STUB_OFFSET, SELECTOR_STUB_OFFSET + SELECTOR_STUB_SIZE))
            | set(range(DISPATCH_STUB_OFFSET, DISPATCH_STUB_OFFSET + DISPATCH_STUB_SIZE))
            | set(range(SCRIPT_OFFSET, SCRIPT_OFFSET + SCRIPT_REGION_SIZE))
        )
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)
        # Unlike the alternate-table probe, the primary/alternate selector branch is untouched.
        self.assertEqual(patched[0x8F5A4:0x8F5A6], self.base[0x8F5A4:0x8F5A6])

    def test_accepts_only_codec_supported_commands(self):
        patched = build_probe(self.base, commands=[
            {"name": "set_battle", "battle_id": 41, "mode": 0},
            {"name": "end"},
        ])
        self.assertEqual(patched[SCRIPT_OFFSET:SCRIPT_OFFSET + 4], bytes.fromhex("1a290000"))
        with self.assertRaisesRegex(ValueError, "unsupported command"):
            build_probe(self.base, commands=[{"name": "dialogue"}, {"name": "end"}])

    def test_trace_stubs_filter_later_scenarios_and_unrelated_scripts(self):
        selector = _selector_stub()
        dispatch = _dispatch_stub()
        self.assertIn(bytes.fromhex("272c07d1"), selector)  # cmp r4,#39; bne skip
        self.assertIn(SCRIPT_ADDRESS.to_bytes(4, "little"), dispatch)
        self.assertIn(bytes.fromhex("7a1a032a0ed8"), dispatch)  # cursor-base <= 3


if __name__ == "__main__":
    unittest.main()
