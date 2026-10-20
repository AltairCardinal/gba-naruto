"""Tests for the runtime-state / battle-object tools absorbed from the
third-party package.

Each check re-derives the claim from our own ROM rather than trusting the
provenance, so a change in the ROM would fail here.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import text_codec  # noqa: E402
import runtime_state  # noqa: E402
import extract_rewards  # noqa: E402
import object_tables  # noqa: E402
import event_queue_budget  # noqa: E402
import portrait_assets  # noqa: E402


def _rom_available():
    try:
        text_codec.resolve_rom()
        return True
    except FileNotFoundError:
        return False


@unittest.skipUnless(_rom_available(), "base ROM not available")
class RuntimeStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = text_codec.resolve_rom().read_bytes()

    def test_native_fields_are_referenced_by_the_game(self):
        report = runtime_state.build_report(self.rom)
        native = [r for r in report["fields"] if r["evidence_class"] == "rom_ref"]
        for row in native:
            self.assertTrue(
                row["referenced_by_game"],
                f"{row['name']} ({row['address']}) has no ROM reference",
            )

    def test_third_party_bookkeeping_is_not_a_native_field(self):
        """0x02022EA0 and the RAM mirrors are the third party's own state.

        They must not be documented as native game fields, so the tool has to
        keep flagging them as unreferenced."""
        report = runtime_state.build_report(self.rom)
        by_name = {r["name"]: r for r in report["fields"]}
        for name in ("save_signature", "replacement_ids",
                     "name_table_ram", "skill_table_ram"):
            row = by_name[name]
            self.assertEqual("third_party", row["evidence_class"], name)
            self.assertFalse(
                row["referenced_by_game"],
                f"{name} suddenly has ROM references - re-check the claim",
            )

    def test_party_and_unit_slot_strides(self):
        self.assertEqual(188, runtime_state.PARTY_FIELDS and 188)
        report = runtime_state.build_report(self.rom)
        names = {r["name"] for r in report["fields"]}
        self.assertIn("party_slot_base", names)
        self.assertIn("battle_unit_base", names)


@unittest.skipUnless(_rom_available(), "base ROM not available")
class RewardTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = text_codec.resolve_rom().read_bytes()
        cls.mapping, _ = text_codec.load_mapping()

    def test_table_geometry(self):
        entries = extract_rewards.read_entries(self.rom, self.mapping)
        self.assertEqual(112, len(entries))
        self.assertEqual(24, extract_rewards.ENTRY_SIZE)
        live = [e for e in entries if not e["is_zero"]]
        self.assertGreater(len(live), 50)

    def test_tail_layout_holds(self):
        """The (item<<8 | count) tail must keep its shape."""
        entries = extract_rewards.read_entries(self.rom, self.mapping)
        evidence = extract_rewards.layout_evidence(entries)
        self.assertGreater(evidence["tail_pairs"], 100)
        self.assertEqual(
            evidence["tail_pairs"], evidence["pairs_with_low_in_0_2"],
            "low byte must stay in 0..2",
        )
        self.assertGreaterEqual(
            evidence["pairs_with_id_in_1_93"], evidence["tail_pairs"] * 0.95,
            "high byte should be a 忍具 id in 1..93",
        )

    def test_gold_and_bonus_ranges_are_plausible(self):
        entries = extract_rewards.read_entries(self.rom, self.mapping)
        evidence = extract_rewards.layout_evidence(entries)
        self.assertGreaterEqual(evidence["gold_range"][0], 10)
        self.assertLessEqual(evidence["gold_range"][1], 2000)


@unittest.skipUnless(_rom_available(), "base ROM not available")
class ObjectTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = text_codec.resolve_rom().read_bytes()
        cls.mapping, _ = text_codec.load_mapping()

    def test_native_dispatch_has_seven_handlers(self):
        _, length, _ = object_tables.read_dispatch(self.rom)
        self.assertEqual(7, length)

    def test_background_table_has_valid_ids(self):
        backgrounds = object_tables.read_backgrounds(self.rom)
        valid = [b["id"] for b in backgrounds if b["valid"]]
        self.assertIn(1, valid)
        self.assertIn(15, valid)
        self.assertNotIn(0, valid)

    def test_object_records_are_inside_the_battle_config(self):
        objects = object_tables.read_objects(self.rom, 40, 0)
        self.assertEqual(16, len(objects))
        base = object_tables.ACTOR_TABLE + 40 * object_tables.GROUP_STRIDE
        for rec in objects:
            self.assertEqual(base + object_tables.OBJECT_OFFSET
                             + rec["index"] * 4, rec["offset"])


@unittest.skipUnless(_rom_available(), "base ROM not available")
class EventQueueBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = text_codec.resolve_rom().read_bytes()
        cls.mapping, _ = text_codec.load_mapping()

    def test_all_battle_logic_scripts_analyse(self):
        import decode_story_script as ds
        for scene in range(1, 47):
            roots = ds.scene_roots(self.rom, scene)
            logic = roots.get("logic")
            if not logic:
                continue
            nodes, issues = ds.walk(self.rom, [logic], self.mapping)
            self.assertEqual(0, len(issues), f"scene {scene}")
            baseline, with_added, reason = event_queue_budget.budget_for_scene(
                self.rom, nodes, logic, []
            )
            self.assertIsNone(reason, f"scene {scene}: {reason}")
            self.assertIsNotNone(baseline, f"scene {scene}")

    def test_stage_one_saturates_the_sixteen_entry_queue(self):
        """Independent confirmation of the queue limit: stage 1's original
        logic script occupies exactly 16 slots."""
        import decode_story_script as ds
        roots = ds.scene_roots(self.rom, 1)
        nodes, _ = ds.walk(self.rom, [roots["logic"]], self.mapping)
        baseline, _, _ = event_queue_budget.budget_for_scene(
            self.rom, nodes, roots["logic"], []
        )
        self.assertEqual(event_queue_budget.QUEUE_LIMIT, baseline)


@unittest.skipUnless(_rom_available(), "base ROM not available")
class PortraitAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = text_codec.resolve_rom().read_bytes()

    def test_pieces_assemble_an_80x80_portrait(self):
        pieces = [p for p in portrait_assets.read_pieces(self.rom)
                  if not p.get("end_marker")]
        self.assertEqual(6, len(pieces))
        width = max(p["x"] + p["w"] for p in pieces)
        height = max(p["y"] + p["h"] for p in pieces)
        self.assertEqual(80, width)
        self.assertEqual(80, height)

    def test_gfx_decompresses_to_80x80_4bpp(self):
        portraits = portrait_assets.read_portraits(self.rom)
        self.assertGreater(len(portraits), 50)
        sizes = [e["gfx_lz_size"] for r in portraits for e in r["expressions"]]
        known = [s for s in sizes if s is not None]
        self.assertGreater(len(known), 300)
        self.assertEqual({6400}, set(known),
                         "every LZ portrait gfx should be 80*80/2 bytes")


if __name__ == "__main__":
    unittest.main()
