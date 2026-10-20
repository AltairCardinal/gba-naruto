#!/usr/bin/env python3
"""S49's roster must be the original's roster, slot for slot.

S49 is the original's battle 14.  Until now the claim "the remake copies the
original battle" rested on rendered frames: the status bar happens to show the
same numbers, and the same sprites stand on the same tiles.  That is evidence
about *pixels*, not about *data*, and it cannot say whether the nine units are
the same nine units.

This gate closes the claim at the data level, from three independent sides:

* the original's own runtime unit pool, read out of EWRAM while the original
  sat at the battle 14 entry checkpoint
  (``artifacts/s49-original-battle14-roster-v1/``, captured by
  ``tools/butano/capture_s49_battle_roster.py``);
* the remake's ROM-backed formation table
  (``sequel/content/positions/bank.json``, ROM ``0x5461C4``), which is the
  table the remake's scenario header is generated from;
* the remake's stat tables (character templates at ROM ``0x54241C`` and the
  growth table at ROM ``0x545068``), which are what turn a level into an HP
  number.

The original's nine units, read out of the pool, are:

======  ======  =======  =====  =====  =====
slot    unit    grid     level  maxHP  carried EXP
======  ======  =======  =====  =====  =====
1       鸣人     (11,6)   5      138    0
2       佐助     (10,14)  4      104    0
3       小樱     (8,14)   5      110    0
4       木叶丸   (8,7)    3      40     0
5-9     蜜蜂 x5  five positions  5   25     50
======  ======  =======  =====  =====  =====

Every one of those HP numbers is reproduced by the remake's own tables through
the original's growth rule (``max_hp = base + growth * (level - 1) / 100``),
for example 鸣人 ``80 + 1450 * 4 / 100 = 138``.

The party slots are the one place the formation table does *not* carry the
level: the original's campaign owns the party levels, and the remake's
campaign initialises them to 5 / 4 / 5.  The test pins those three numbers
against ``battle_campaign_route.h`` so the verifier's constants cannot drift
away from the runtime.

The failure modes are exercised, not assumed: a mutated pool, a mutated
formation record and a mutated stat table each have to make the verifier
report a problem instead of quietly agreeing.

The measurement comes from ``tools/butano/verify_s49_battle_roster.py``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.butano import verify_s49_battle_roster as verifier  # noqa: E402

REVERSE_ROOT = Path(
    os.environ.get("KONOHA_REVERSE_ROOT", "/Users/altair/github/gba-naruto-reverse")
)

ARTIFACT = ROOT / "artifacts/s49-original-battle14-roster-v1"

# The original's battle 14 roster, read out of the runtime unit pool.
EXPECTED_ROSTER = (
    (1, 1, 11, 6, 5, 138, 0),
    (2, 2, 10, 14, 4, 104, 0),
    (3, 3, 8, 14, 5, 110, 0),
    (4, 30, 8, 7, 3, 40, 0),
    (5, 55, 3, 4, 5, 25, 50),
    (6, 55, 4, 8, 5, 25, 50),
    (7, 55, 3, 11, 5, 25, 50),
    (8, 55, 6, 6, 5, 25, 50),
    (9, 55, 5, 13, 5, 25, 50),
)


def _verify(artifact: Path = ARTIFACT, root: Path = ROOT) -> dict:
    return verifier.verify(artifact, root, None)


class S49BattleRosterTest(unittest.TestCase):
    def test_capture_artifact_is_present_and_self_consistent(self) -> None:
        self.assertTrue(
            (ARTIFACT / "unit_pool.bin").is_file(),
            f"missing capture: {ARTIFACT / 'unit_pool.bin'}")
        capture = json.loads(
            (ARTIFACT / "capture.json").read_text(encoding="utf-8"))
        self.assertEqual(
            capture["unit_pool_sha256"],
            verifier.sha256_file(ARTIFACT / "unit_pool.bin"),
            "the captured pool does not match its own receipt")
        self.assertEqual(capture["unit_pool_size"], verifier.POOL_SIZE)

    def test_original_roster_is_pinned(self) -> None:
        _capture, units = verifier.load_artifact(ARTIFACT)
        observed = tuple(
            (
                unit["slot"],
                unit["character_id"],
                unit["grid_x"],
                unit["grid_y"],
                unit["level"],
                unit["max_hp"],
                unit["carried_experience"],
            )
            for unit in units
        )
        self.assertEqual(observed, EXPECTED_ROSTER)

    def test_remake_formation_table_matches_the_original(self) -> None:
        formation = verifier.load_formation(ROOT)
        self.assertEqual(len(formation), 9)
        for row, expected in zip(formation, EXPECTED_ROSTER):
            slot, character_id, x, y = expected[:4]
            self.assertEqual(row["record_id"] + 1, slot)
            self.assertEqual(int(row["selector"]), character_id)
            self.assertEqual(int(row["x"]), x)
            self.assertEqual(int(row["y"]), y)

    def test_remake_stat_tables_reproduce_every_original_hp(self) -> None:
        base_hp, growth_hp = verifier.load_stat_tables(ROOT)
        for _slot, character_id, _x, _y, level, max_hp, _exp in EXPECTED_ROSTER:
            expected = verifier.grown_max_hp(
                base_hp[character_id], growth_hp[character_id], level)
            self.assertEqual(
                expected,
                max_hp,
                f"character {character_id} at level {level}: remake tables give "
                f"{expected}, the original had {max_hp}")

    def test_party_levels_still_come_from_the_campaign(self) -> None:
        route = (
            ROOT / "butano-sequel/game/include/konoha/battle_campaign_route.h")
        text = route.read_text(encoding="utf-8")
        for character_id, level in verifier.PARTY_LEVELS.items():
            pattern = re.compile(
                r"ensure_battle_campaign_character\(\s*"
                r"campaign,\s*" + str(character_id) + r",\s*"
                r"initialize_defaults \? " + str(level) + r" : 1")
            self.assertRegex(
                text,
                pattern,
                f"character {character_id} default level is no longer {level}")

    def test_reverse_note_and_the_original_memory_agree(self) -> None:
        _capture, units = verifier.load_artifact(ARTIFACT)
        observed = tuple(
            (unit["slot"], unit["character_id"], unit["level"], unit["max_hp"])
            for unit in units
        )
        self.assertEqual(
            observed,
            verifier.NOTE_ROSTER,
            "the reverse side's prose record and the original's own memory "
            "disagree about the battle 14 roster")

    def test_verifier_reports_no_problem(self) -> None:
        result = _verify()
        self.assertEqual(result["problems"], [])

    def test_verifier_cross_checks_the_reverse_tree(self) -> None:
        if not (REVERSE_ROOT / "artifacts").is_dir():
            self.skipTest(f"reverse tree not available at {REVERSE_ROOT}")
        result = verifier.verify(ARTIFACT, ROOT, REVERSE_ROOT)
        self.assertEqual(result["problems"], [])
        self.assertIsNotNone(result["reverse_bindings_cross_check"])

    def test_mutated_pool_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copy)
            pool = bytearray((copy / "unit_pool.bin").read_bytes())
            offset = verifier.POOL_RECORD_SIZE * 1 + verifier.MAX_HP_OFFSET
            pool[offset] = (pool[offset] + 1) % 256
            (copy / "unit_pool.bin").write_bytes(bytes(pool))
            with self.assertRaises(verifier.RosterVerificationError):
                _verify(artifact=copy)

    def test_mutated_formation_record_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "root"
            shutil.copytree(
                ROOT / "sequel/content", copy / "sequel/content",
                ignore=shutil.ignore_patterns("__pycache__"))
            positions_path = copy / "sequel/content/positions/bank.json"
            positions = json.loads(positions_path.read_text(encoding="utf-8"))
            for row in positions["entries"]:
                if row["group_id"] == verifier.BATTLE_ID and \
                        row["variant_id"] == verifier.BATTLE_VARIANT and \
                        row["record_id"] == 4:
                    row["x"] = int(row["x"]) + 1
            positions_path.write_text(
                json.dumps(positions, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            result = verifier.verify(ARTIFACT, copy, None)
            self.assertTrue(
                any("position differs" in problem for problem in result["problems"]),
                result["problems"])

    def test_mutated_stat_table_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "root"
            shutil.copytree(
                ROOT / "sequel/content", copy / "sequel/content",
                ignore=shutil.ignore_patterns("__pycache__"))
            stats_path = copy / "sequel/content/character-stats/bank.json"
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            for row in stats["entries"]:
                if int(row["character_id"]) == 1:
                    row["template_0e_growth"] = int(
                        row["template_0e_growth"]) + 100
            stats_path.write_text(
                json.dumps(stats, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
            result = verifier.verify(ARTIFACT, copy, None)
            self.assertTrue(
                any("max HP differs" in problem for problem in result["problems"]),
                result["problems"])


if __name__ == "__main__":
    unittest.main()
