import unittest
from pathlib import Path

from tools.extract_audio_resource_sets import ACTIVE_IDS, MASTER_OFFSET, SOUND_ID_COUNT, extract

ROOT = Path(__file__).resolve().parent.parent


class AudioResourceSetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = extract(cls.rom)

    def test_active_ids_and_master_bytes_are_lossless(self):
        self.assertEqual([e["sound_id"] for e in self.bank["entries"]], list(ACTIVE_IDS))
        for entry in self.bank["entries"]:
            off = MASTER_OFFSET + entry["sound_id"] * 8
            self.assertEqual(entry["raw_hex"], self.rom[off:off + 8].hex())

    def test_every_descriptor_has_sequence_and_track_pointers(self):
        for entry in self.bank["entries"]:
            self.assertEqual(len(entry["track_ptrs"]), entry["track_count"])
            self.assertTrue(0x08000000 <= entry["sequence_ptr"] < 0x08600000)
            self.assertTrue(all(0x08000000 <= p < 0x08600000 for p in entry["track_ptrs"]))

    def test_runtime_observed_id_118_resolves_to_captured_descriptor(self):
        entry = next(e for e in self.bank["entries"] if e["sound_id"] == 118)
        self.assertEqual(entry["descriptor_ptr"], 0x0853D06C)
        self.assertEqual(entry["player_index"], 2)
        self.assertEqual(self.bank["sound_id_domain"], [0, SOUND_ID_COUNT - 1])
        self.assertEqual(self.bank["verification"], "runtime_verified")


if __name__ == "__main__":
    unittest.main()
