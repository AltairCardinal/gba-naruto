import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.compare_mgba_cross_player_cgb_capture import (
    compare_cross_player_cgb_capture,
)
from tools.build_cross_player_cgb_probe import build_probe


ROOT = Path(__file__).resolve().parent.parent


class CompareMgbaCrossPlayerCgbCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = json.loads((ROOT / "sequel/content/audio/bank.json").read_text())
        cls.decoded = json.loads((ROOT / "build/audio-v2/tracks-decoded.json").read_text())

    def capture(self):
        zero_plane = bytes(264).hex()
        zero_pcm = bytes(528)
        rows = []
        for invocation in range(2):
            io = bytearray(0x30)
            io[0x19] = 0x08 if invocation == 0 else 0x18
            if invocation:
                io[0x1C] = 0x14
                io[0x21] = 0x88
            cgb = bytearray(0x100)
            if invocation:
                cgb[0xC0] = 1
                struct.pack_into("<I", cgb, 0xC0 + 0x2C, 0x03006178)
            players = bytearray(0x110)
            struct.pack_into("<I", players, 0x40 + 0x0C, invocation + 1)
            struct.pack_into("<I", players, 0x80 + 0x0C, invocation + 1)
            rows.append({
                "invocation": invocation,
                "cgb_io_hex": io.hex(),
                "cgb_state_hex": cgb.hex(),
                "cgb_state_sha256": hashlib.sha256(cgb).hexdigest(),
                "player_state_hex": players.hex(),
                "player_state_sha256": hashlib.sha256(players).hexdigest(),
                "right_hex": zero_plane,
                "left_hex": zero_plane,
                "pcm_sha256": hashlib.sha256(zero_pcm).hexdigest(),
            })
        return {
            "format": "gba-naruto-mgba-mp2k-capture-v1",
            "sound_id": 144,
            "timed_out": False,
            "counter_sequence_valid": True,
            "captures": rows,
            "combined_pcm_sha256": hashlib.sha256(zero_pcm * len(rows)).hexdigest(),
        }

    def test_matches_both_player_clocks_and_lower_owner_winner(self):
        result = compare_cross_player_cgb_capture(
            self.rom, self.bank, self.decoded, self.capture(),
            source_sound_id=144,
            clone_sound_id=143,
            clone_player_slot=1,
            captured_rom=build_probe(
                self.rom, source_sound_id=144, clone_sound_id=143,
                clone_player_slot=1,
            ),
        )

        self.assertTrue(result["all_visible_registers_match"])
        self.assertTrue(result["all_player_clocks_match"])
        self.assertTrue(result["all_active_owners_match"])
        self.assertTrue(result["competition_observed"])
        self.assertTrue(result["capture_state_hashes_valid"])
        self.assertTrue(result["capture_hashes_valid"])
        self.assertTrue(result["probe_rom_match"])
        self.assertTrue(result["verification_passed"])

    def test_reports_wrong_winning_owner(self):
        capture = self.capture()
        cgb = bytearray.fromhex(capture["captures"][1]["cgb_state_hex"])
        struct.pack_into("<I", cgb, 0xC0 + 0x2C, 0x030061C8)
        capture["captures"][1]["cgb_state_hex"] = cgb.hex()

        result = compare_cross_player_cgb_capture(
            self.rom, self.bank, self.decoded, capture,
            source_sound_id=144,
            clone_sound_id=143,
            clone_player_slot=1,
            captured_rom=build_probe(
                self.rom, source_sound_id=144, clone_sound_id=143,
                clone_player_slot=1,
            ),
        )

        self.assertFalse(result["all_active_owners_match"])
        self.assertEqual(result["first_owner_mismatch_invocation"], 1)
        self.assertFalse(result["capture_state_hashes_valid"])

    def test_rejects_invalid_counter_sequence(self):
        capture = self.capture()
        capture["counter_sequence_valid"] = False
        result = compare_cross_player_cgb_capture(
            self.rom, self.bank, self.decoded, capture,
            source_sound_id=144, clone_sound_id=143, clone_player_slot=1,
            captured_rom=build_probe(
                self.rom, source_sound_id=144, clone_sound_id=143,
                clone_player_slot=1,
            ),
        )
        self.assertFalse(result["verification_passed"])

    def test_lower_source_owner_wins_when_clone_slot_is_higher(self):
        capture = self.capture()
        for invocation, row in enumerate(capture["captures"]):
            players = bytearray.fromhex(row["player_state_hex"])
            struct.pack_into("<I", players, 0x40 + 0x0C, 0)
            struct.pack_into("<I", players, 0xD0 + 0x0C, invocation + 1)
            row["player_state_hex"] = players.hex()
            row["player_state_sha256"] = hashlib.sha256(players).hexdigest()
            if invocation:
                cgb = bytearray.fromhex(row["cgb_state_hex"])
                struct.pack_into("<I", cgb, 0xC0 + 0x2C, 0x030061C8)
                row["cgb_state_hex"] = cgb.hex()
                row["cgb_state_sha256"] = hashlib.sha256(cgb).hexdigest()

        result = compare_cross_player_cgb_capture(
            self.rom, self.bank, self.decoded, capture,
            source_sound_id=144, clone_sound_id=143, clone_player_slot=3,
            captured_rom=build_probe(
                self.rom, source_sound_id=144, clone_sound_id=143,
                clone_player_slot=3,
            ),
        )

        self.assertEqual(result["expected_winning_track_owner"], "0x030061C8")
        self.assertEqual(result["losing_track_owner"], "0x03006218")
        self.assertTrue(result["verification_passed"])


if __name__ == "__main__":
    unittest.main()
