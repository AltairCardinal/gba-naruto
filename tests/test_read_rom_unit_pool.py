#!/usr/bin/env python3
"""The unit-pool reader must agree with the recorded S49 ground truth."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.butano.read_rom_unit_pool import (
    OFFSET_ACTING,
    OFFSET_AFFILIATION,
    OFFSET_X,
    OFFSET_Y,
    POOL_ADDRESS,
    POOL_STRIDE,
    build_parser,
    load_state,
    read_action_order,
    read_pool,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1]
ENTRY_STATE = (
    ROOT / "artifacts/s49-fidelity-20261019-v1/original-entry-advance/step-00-base.ss9"
)
BEE_STATE = (
    ROOT / "artifacts/s49-fidelity-20261019-v1/original-bcycle/step-04-A.ss9"
)
# Measured from the original ROM's EWRAM pool; also matches
# sequel/content/positions/bank.json group 14 variant 0.
EXPECTED_PLAYER = [(11, 6), (10, 14), (8, 14), (8, 7)]
EXPECTED_ENEMY = [(3, 4), (4, 8), (3, 11), (6, 6), (5, 13)]


class UnitPoolContractTest(unittest.TestCase):
    def test_offsets_match_the_reverse_engineering_notes(self):
        self.assertEqual(POOL_ADDRESS, 0x020240C0)
        self.assertEqual(POOL_STRIDE, 0x1D4)
        self.assertEqual((OFFSET_X, OFFSET_Y), (0xC4, 0xC5))
        self.assertEqual(OFFSET_AFFILIATION, 0xCC)
        self.assertEqual(OFFSET_ACTING, 0xC1)

    def test_summary_counts_side_groups_and_reports_the_acting_unit(self):
        units = [
            {"side": "player", "slot": 1, "x": 11, "y": 6, "acting": False},
            {"side": "enemy", "slot": 2, "x": 3, "y": 4, "acting": True},
            {"side": "enemy", "slot": 3, "x": 4, "y": 8, "acting": False},
        ]
        self.assertEqual(
            summarize(units),
            {
                "unit_count": 3,
                "by_side": {"player": 1, "enemy": 2},
                "acting": [{"slot": 2, "side": "enemy", "x": 3, "y": 4}],
            })

    def test_empty_pool_is_reported_as_empty_not_guessed(self):
        class FakeState:
            def read_memory(self, address, size):
                return bytes(size)

        self.assertEqual(read_pool(FakeState()), [])


@unittest.skipUnless(ENTRY_STATE.is_file(), "S49 entry savestate is not recorded")
class UnitPoolGroundTruthTest(unittest.TestCase):
    def test_original_s49_roster_is_four_players_and_five_enemies(self):
        for state in (ENTRY_STATE, BEE_STATE):
            if not state.is_file():
                self.skipTest(f"{state.name} is not recorded")
            with self.subTest(savestate=state.name):
                units = read_pool(load_state(state))
                players = [
                    (unit["x"], unit["y"]) for unit in units
                    if unit["side"] == "player"
                ]
                enemies = [
                    (unit["x"], unit["y"]) for unit in units
                    if unit["side"] == "enemy"
                ]
                self.assertEqual(players, EXPECTED_PLAYER)
                self.assertEqual(enemies, EXPECTED_ENEMY)

    def test_acting_marker_walks_from_player_units_onto_enemy_bees(self):
        """A/B advances the acting unit through players *and* enemies."""
        expected = {
            "00": (1, "player"), "01": (2, "player"), "02": (3, "player"),
            "03": (4, "player"), "04": (5, "enemy"), "05": (6, "enemy"),
            "06": (7, "enemy"),
        }
        base = ROOT / "artifacts/s49-fidelity-20261019-v1/original-bcycle"
        for tag, (slot, side) in expected.items():
            suffix = "-base" if tag == "00" else ("-B" if int(tag) >= 5 else "-A")
            path = base / f"step-{tag}{suffix}.ss9"
            if not path.is_file():
                self.skipTest(f"{path.name} is not recorded")
            with self.subTest(step=tag):
                acting = summarize(read_pool(load_state(path)))["acting"]
                self.assertEqual(len(acting), 1)
                self.assertEqual((acting[0]["slot"], acting[0]["side"]), (slot, side))

    def test_cli_writes_a_machine_readable_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pool.json"
            run = subprocess.run(
                [sys.executable, "-m", "tools.butano.read_rom_unit_pool",
                 str(ENTRY_STATE), "--output", str(output)],
                cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["unit_count"], 9)
            self.assertEqual(
                payload["by_side"], {"player": 4, "enemy": 5})
            self.assertEqual(
                payload["acting"],
                [{"slot": 1, "side": "player", "x": 11, "y": 6}],
                "the entry state acts with Naruto, a player-side unit")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(ENTRY_STATE.is_file(), "S49 entry savestate is not recorded")
class ActionOrderTableTest(unittest.TestCase):
    def test_thirteen_pointers_to_uniform_sixty_byte_records(self):
        rows = read_action_order(load_state(ENTRY_STATE))
        records = [row for row in rows if row.get("index") is not None]
        meta = rows[-1]
        self.assertEqual(len(records), 13)
        self.assertEqual(meta["count"], 13)
        self.assertTrue(meta["records_are_uniform_stride"])
        ordered = [record["address"] for record in records]
        self.assertNotEqual(
            ordered, sorted(ordered),
            "the pointer array is in action order, not address order")
        ascending = sorted(ordered)
        self.assertEqual(ascending[0], 0x030056AC)
        self.assertEqual(
            [ascending[i + 1] - ascending[i] for i in range(12)],
            [0x3C] * 12)

    def test_reader_does_not_claim_semantics_for_the_tag_bytes(self):
        record = read_action_order(load_state(ENTRY_STATE))[0]
        self.assertEqual(record["tag_a"], 0x13)
        self.assertEqual(record["tag_b"], 0x00)
        for forbidden in ("side", "unit", "acting", "done"):
            self.assertNotIn(forbidden, record)
