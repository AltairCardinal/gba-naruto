#!/usr/bin/env python3
from __future__ import annotations

import struct
import unittest
from pathlib import Path

from tools.build_alternate_chapter_runtime_probe import (
    DISPATCH_HOOK,
    DISPATCH_STUB_OFFSET,
    DISPATCH_STUB_SIZE,
    SELECTOR_CAPTURE_HOOK,
    SELECTOR_STUB_OFFSET,
    SELECTOR_STUB_SIZE,
)
from tools.build_battle_start_runtime_probe import (
    DEPLOY_CALL,
    DEPLOY_STUB,
    DEPLOY_STUB_OFFSET,
    DEPLOY_STUB_SIZE,
    LINEUP_CALL,
    LINEUP_EXIT_HOOK,
    LINEUP_EXIT_SCRATCH,
    LINEUP_EXIT_STUB,
    LINEUP_EXIT_STUB_OFFSET,
    LINEUP_EXIT_STUB_SIZE,
    LINEUP_STUB,
    LINEUP_STUB_OFFSET,
    LINEUP_STUB_SIZE,
    MENU_CALL,
    MENU_STUB,
    MENU_STUB_OFFSET,
    MENU_STUB_SIZE,
    SCRATCH,
    START_CALL,
    START_STUB,
    START_STUB_OFFSET,
    START_STUB_SIZE,
    build_probe,
)
from tools.build_save_state_runtime_probe import encode_thumb_bl


ROOT = Path(__file__).resolve().parents[1]
ROM_BASE = 0x08000000


class BattleStartRuntimeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = (ROOT / "rom/base.gba").read_bytes()

    def test_layers_natural_chapter_and_start_flow_hooks_only(self):
        output = build_probe(self.base)
        changed = {
            index
            for index, pair in enumerate(zip(self.base, output))
            if pair[0] != pair[1]
        }
        allowed = set(range(SELECTOR_CAPTURE_HOOK - ROM_BASE, SELECTOR_CAPTURE_HOOK - ROM_BASE + 4))
        allowed.update(range(DISPATCH_HOOK - ROM_BASE, DISPATCH_HOOK - ROM_BASE + 4))
        allowed.update(range(SELECTOR_STUB_OFFSET, SELECTOR_STUB_OFFSET + SELECTOR_STUB_SIZE))
        allowed.update(range(DISPATCH_STUB_OFFSET, DISPATCH_STUB_OFFSET + DISPATCH_STUB_SIZE))
        allowed.update(range(MENU_CALL - ROM_BASE, MENU_CALL - ROM_BASE + 4))
        allowed.update(range(START_CALL - ROM_BASE, START_CALL - ROM_BASE + 4))
        allowed.update(range(MENU_STUB_OFFSET, MENU_STUB_OFFSET + MENU_STUB_SIZE))
        allowed.update(range(START_STUB_OFFSET, START_STUB_OFFSET + START_STUB_SIZE))
        allowed.update(range(LINEUP_CALL - ROM_BASE, LINEUP_CALL - ROM_BASE + 4))
        allowed.update(range(DEPLOY_CALL - ROM_BASE, DEPLOY_CALL - ROM_BASE + 4))
        allowed.update(range(LINEUP_STUB_OFFSET, LINEUP_STUB_OFFSET + LINEUP_STUB_SIZE))
        allowed.update(range(LINEUP_EXIT_HOOK - ROM_BASE, LINEUP_EXIT_HOOK - ROM_BASE + 4))
        allowed.update(range(LINEUP_EXIT_STUB_OFFSET, LINEUP_EXIT_STUB_OFFSET + LINEUP_EXIT_STUB_SIZE))
        allowed.update(range(DEPLOY_STUB_OFFSET, DEPLOY_STUB_OFFSET + DEPLOY_STUB_SIZE))
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)

    def test_patches_both_calls_to_dedicated_wrappers(self):
        output = build_probe(self.base)
        self.assertEqual(
            output[MENU_CALL - ROM_BASE:MENU_CALL - ROM_BASE + 4],
            encode_thumb_bl(MENU_CALL, MENU_STUB),
        )
        self.assertEqual(
            output[START_CALL - ROM_BASE:START_CALL - ROM_BASE + 4],
            encode_thumb_bl(START_CALL, START_STUB),
        )
        self.assertEqual(
            output[LINEUP_CALL - ROM_BASE:LINEUP_CALL - ROM_BASE + 4],
            encode_thumb_bl(LINEUP_CALL, LINEUP_STUB),
        )
        self.assertEqual(
            output[DEPLOY_CALL - ROM_BASE:DEPLOY_CALL - ROM_BASE + 4],
            encode_thumb_bl(DEPLOY_CALL, DEPLOY_STUB),
        )
        self.assertEqual(
            output[LINEUP_EXIT_HOOK - ROM_BASE:LINEUP_EXIT_HOOK - ROM_BASE + 4],
            encode_thumb_bl(LINEUP_EXIT_HOOK, LINEUP_EXIT_STUB),
        )

    def test_wrappers_embed_scratch_address(self):
        output = build_probe(self.base)
        scratch = struct.pack("<I", SCRATCH)
        menu = output[MENU_STUB_OFFSET:MENU_STUB_OFFSET + MENU_STUB_SIZE]
        start = output[START_STUB_OFFSET:START_STUB_OFFSET + START_STUB_SIZE]
        self.assertIn(scratch, menu)
        self.assertIn(scratch, start)

    def test_lineup_exit_uses_a_dedicated_counter_region(self):
        output = build_probe(self.base)
        exit_stub = output[
            LINEUP_EXIT_STUB_OFFSET:LINEUP_EXIT_STUB_OFFSET + LINEUP_EXIT_STUB_SIZE
        ]
        self.assertEqual(LINEUP_EXIT_SCRATCH, SCRATCH + 0x40)
        self.assertIn(struct.pack("<I", LINEUP_EXIT_SCRATCH), exit_stub)
        self.assertNotIn(struct.pack("<I", SCRATCH), exit_stub)

    def test_rejects_mismatched_menu_call(self):
        modified = bytearray(self.base)
        modified[MENU_CALL - ROM_BASE] ^= 1
        with self.assertRaisesRegex(ValueError, "menu call"):
            build_probe(bytes(modified))


if __name__ == "__main__":
    unittest.main()
