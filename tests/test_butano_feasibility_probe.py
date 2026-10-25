#!/usr/bin/env python3
"""Tests for the 1:1 fidelity feasibility probes.

The roadmap's risk list is only worth something if it can be re-checked.
These tests pin the findings that the roadmap's cost model rests on:

* F1 -- the original's 38 states exist as a generated shape layer, the
  runtime still runs the remake's own 26-value enum;
* F2 -- the remake's action dispatch is a different id set from the
  original's 60, and its slot layout is not the original's 5+tables;
* F5 -- Butano 21.7.1 cannot place a regular BG on bg0, and rejects 4bpp
  palettes;
* F8 -- no ledger entry is missing.

If any of these change, the roadmap's numbers change with them, and the
tests say so instead of the document quietly going stale.
"""

from __future__ import annotations

import unittest

from tools.butano_feasibility_probe import (
    ORIGINAL_ACTION_IDS,
    ORIGINAL_NINJUTSU_SLOTS,
    probe_f1_state_machine,
    probe_f2_action_system,
    probe_f5_butano_substrate,
    probe_f8_ledger,
)


class FeasibilityProbeTests(unittest.TestCase):
    def test_f1_shape_exists_but_runtime_is_still_the_remake_enum(self):
        data = probe_f1_state_machine()
        if not data.get("ok"):
            self.skipTest(f"probe unavailable: {data.get('why')}")
        self.assertEqual(38, data["original_states"])
        self.assertEqual(12, data["unknown_states"])
        self.assertEqual(17, data["original_only_states"])
        self.assertEqual("battle_scene_phase", data["runtime_enum"])
        self.assertEqual(26, data["runtime_enum_values"])
        self.assertFalse(data["implemented_flag"])

    def test_f2_action_ids_differ_from_the_originals_sixty(self):
        data = probe_f2_action_system()
        if not data.get("ok"):
            self.skipTest(f"probe unavailable: {data.get('why')}")
        self.assertLess(len(data["remake_ids"]), len(ORIGINAL_ACTION_IDS))
        self.assertTrue(data["missing_ids"], "the shape gap must be measured")
        self.assertIn(61, data["ninjutsu_slots_missing"])
        self.assertIn(62, data["ninjutsu_slots_missing"])
        # the remake's slot layout is not the original's 5 ninjutsu slots
        self.assertNotEqual(
            {"primary_slots": 5, "secondary_slots": 0}, data["remake_slot_counts"])

    def test_f5_butano_has_three_additive_gaps_not_an_unsuitable_engine(self):
        data = probe_f5_butano_substrate()
        if not data.get("ok"):
            self.skipTest(f"probe unavailable: {data.get('why')}")
        # three regular BG layers fit (bg3, bg2, bg1) even though bg0 does not
        self.assertFalse(data["can_reach_bg0"])
        self.assertEqual(3, data["regular_bgs_available"])
        # the 4bpp mode exists and the hardware layer takes a per-BG bpp ...
        self.assertTrue(data["bpp4_mode_exists"])
        self.assertTrue(data["per_bg_bpp_in_hw_layer"])
        # ... but only the palette-bitmap painting path rejects 4bpp
        self.assertTrue(data["bpp4_palette_bitmap_rejected"])
        # per-frame single-colour palette writes are available
        self.assertTrue(data["per_color_palette_write"])
        # the BG index only matters for register-level identity
        self.assertIn("pixel-identical", data["register_level_only"])

    def test_f8_no_ledger_entry_is_missing(self):
        data = probe_f8_ledger()
        if not data.get("ok"):
            self.skipTest(f"probe unavailable: {data.get('why')}")
        self.assertEqual(0, data["missing"])
        self.assertEqual(36, data["entries"])


if __name__ == "__main__":
    unittest.main()
