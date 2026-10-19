import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from extract_graphics_resource_sets import extract
from revoke_false_story_banks import build_tombstone


class AudioResourceSetsCompatibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = extract((ROOT / "rom/base.gba").read_bytes())

    def test_master_descriptors_have_counted_track_pointer_lists(self):
        self.assertEqual(len(self.result["entries"]), 80)
        first = self.result["entries"][0]
        self.assertEqual(first["descriptor_offset"], 0x536368)
        self.assertEqual(first["track_count"], 8)
        self.assertEqual(first["voicegroup_ptr"], 0x0846480C)
        self.assertEqual(len(first["track_ptrs"]), 8)

    def test_high_descriptor_bytes_are_not_misread_as_pointer_count(self):
        special = next(e for e in self.result["entries"] if e["sound_id"] == 51)
        self.assertEqual(special["track_count"], 7)
        self.assertEqual(special["priority"], 10)
        self.assertEqual(special["player_index"], 3)

    def test_false_story_slice_starts_after_real_header(self):
        descriptor = next(e for e in self.result["entries"] if e["sound_id"] == 8)
        tombstone = build_tombstone("story-c", descriptor)
        self.assertEqual(tombstone["table_offset"], 0x538FF0)
        self.assertEqual(tombstone["actual_container"]["descriptor_offset"], 0x538FEC)
        self.assertEqual(tombstone["verification"], "disproved")
        self.assertEqual(tombstone["entries"], [])

    def test_revoker_never_targets_live_chapter_banks(self):
        from revoke_false_story_banks import MAPPING
        self.assertNotIn("story", MAPPING)
        self.assertNotIn("story-b", MAPPING)


if __name__ == "__main__":
    unittest.main()
