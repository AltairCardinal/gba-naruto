import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.compare_mgba_retrigger_capture import compare_retrigger_capture
from tools.build_delayed_audio_retrigger_probe import build_probe
from tools.m4a_song_engine import M4ASongEngine


ROOT = Path(__file__).resolve().parent.parent


class CompareMgbaRetriggerCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = json.loads((ROOT / "sequel/content/audio/bank.json").read_text())
        cls.decoded = json.loads((ROOT / "build/audio-v2/tracks-decoded.json").read_text())

    def capture(self):
        first = M4ASongEngine.from_bank(
            self.rom, self.bank, self.decoded, sound_id=101
        )
        replacement = None
        rows = []
        combined = bytearray()
        for invocation in range(4):
            if invocation < 2:
                step = first.advance_soundmain()
                clock = invocation + 1
            else:
                if replacement is None:
                    replacement = M4ASongEngine.from_bank(
                        self.rom, self.bank, self.decoded, sound_id=102
                    )
                step = replacement.advance_soundmain()
                clock = invocation - 1
            right = bytes(sample & 0xFF for sample in step.right)
            left = bytes(sample & 0xFF for sample in step.left)
            pcm = bytearray()
            for right_sample, left_sample in zip(right, left):
                pcm.extend((right_sample, left_sample))
            combined.extend(pcm)
            players = bytearray(0x110)
            struct.pack_into("<I", players, 0x40 + 0x0C, clock)
            channels = bytearray(0x300)
            if invocation in (1, 3):
                channels[0] = 2
            rows.append({
                "invocation": invocation,
                "right_hex": right.hex(),
                "left_hex": left.hex(),
                "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
                "player_state_hex": players.hex(),
                "player_state_sha256": hashlib.sha256(players).hexdigest(),
                "direct_channels_hex": channels.hex(),
                "direct_channels_sha256": hashlib.sha256(channels).hexdigest(),
            })
        return {
            "format": "gba-naruto-mgba-mp2k-capture-v1",
            "timed_out": False,
            "counter_sequence_valid": True,
            "captures": rows,
            "combined_pcm_sha256": hashlib.sha256(combined).hexdigest(),
        }

    def test_matches_active_same_slot_hard_replacement(self):
        result = compare_retrigger_capture(
            self.rom, self.bank, self.decoded, self.capture(),
            first_sound_id=101,
            replacement_sound_id=102,
            switch_after_invocations=2,
            captured_rom=build_probe(
                self.rom, first_sound_id=101, replacement_sound_id=102,
                switch_after_invocations=2,
            ),
        )

        self.assertTrue(result["all_chunks_match"])
        self.assertTrue(result["all_player_clocks_match"])
        self.assertTrue(result["old_pool_empty_at_switch"])
        self.assertTrue(result["capture_state_hashes_valid"])
        self.assertTrue(result["probe_rom_match"])
        self.assertTrue(result["verification_passed"])

    def test_reports_missing_player_clock_reset(self):
        capture = self.capture()
        players = bytearray.fromhex(capture["captures"][2]["player_state_hex"])
        struct.pack_into("<I", players, 0x40 + 0x0C, 3)
        capture["captures"][2]["player_state_hex"] = players.hex()

        result = compare_retrigger_capture(
            self.rom, self.bank, self.decoded, capture,
            first_sound_id=101,
            replacement_sound_id=102,
            switch_after_invocations=2,
            captured_rom=build_probe(
                self.rom, first_sound_id=101, replacement_sound_id=102,
                switch_after_invocations=2,
            ),
        )

        self.assertFalse(result["all_player_clocks_match"])
        self.assertEqual(result["first_clock_mismatch_invocation"], 2)
        self.assertFalse(result["capture_state_hashes_valid"])

    def test_rejects_invalid_counter_sequence(self):
        capture = self.capture()
        capture["counter_sequence_valid"] = False
        result = compare_retrigger_capture(
            self.rom, self.bank, self.decoded, capture,
            first_sound_id=101, replacement_sound_id=102,
            switch_after_invocations=2,
            captured_rom=build_probe(
                self.rom, first_sound_id=101, replacement_sound_id=102,
                switch_after_invocations=2,
            ),
        )
        self.assertFalse(result["verification_passed"])


if __name__ == "__main__":
    unittest.main()
