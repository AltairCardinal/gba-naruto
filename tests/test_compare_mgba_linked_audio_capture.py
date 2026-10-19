import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.compare_mgba_linked_audio_capture import compare_linked_capture
from tools.build_controlled_audio_runtime_probe import build_probe
from tools.m4a_song_engine import M4ASongEngine


ROOT = Path(__file__).resolve().parent.parent


class CompareMgbaLinkedAudioCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = json.loads((ROOT / "sequel/content/audio/bank.json").read_text())
        cls.decoded = json.loads((ROOT / "build/audio-v2/tracks-decoded.json").read_text())

    def capture(self):
        engines = [
            M4ASongEngine.from_bank(
                self.rom, self.bank, self.decoded, sound_id=sound_id
            )
            for sound_id in (101, 106)
        ]
        rows = []
        combined = bytearray()
        for invocation in range(2):
            steps = [engine.advance_soundmain() for engine in engines]
            right = bytes(
                sum(step.right[frame] for step in steps) & 0xFF
                for frame in range(264)
            )
            left = bytes(
                sum(step.left[frame] for step in steps) & 0xFF
                for frame in range(264)
            )
            pcm = bytearray()
            for right_sample, left_sample in zip(right, left):
                pcm.extend((right_sample, left_sample))
            combined.extend(pcm)
            players = bytearray(0x110)
            struct.pack_into("<I", players, 0x40 + 0x0C, invocation + 1)
            struct.pack_into("<I", players, 0x80 + 0x0C, invocation + 1)
            channels = bytearray(0x300)
            if invocation == 1:
                channels[0] = channels[0x40] = 2
                struct.pack_into("<I", channels, 0x2C, 0x03006178)
                struct.pack_into("<I", channels, 0x40 + 0x2C, 0x030061C8)
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

    def test_matches_mixed_pcm_player_clocks_and_shared_pool_tracks(self):
        result = compare_linked_capture(
            self.rom, self.bank, self.decoded, self.capture(),
            sound_ids=(101, 106),
            captured_rom=build_probe(self.rom, sound_ids=(101, 106)),
        )

        self.assertTrue(result["all_chunks_match"])
        self.assertTrue(result["all_player_clocks_match"])
        self.assertTrue(result["shared_pool_tracks_observed"])
        self.assertTrue(result["capture_state_hashes_valid"])
        self.assertTrue(result["probe_rom_match"])
        self.assertTrue(result["verification_passed"])

    def test_reports_a_stalled_linked_player_clock(self):
        capture = self.capture()
        players = bytearray.fromhex(capture["captures"][1]["player_state_hex"])
        struct.pack_into("<I", players, 0x80 + 0x0C, 1)
        capture["captures"][1]["player_state_hex"] = players.hex()

        result = compare_linked_capture(
            self.rom, self.bank, self.decoded, capture,
            sound_ids=(101, 106),
            captured_rom=build_probe(self.rom, sound_ids=(101, 106)),
        )

        self.assertFalse(result["all_player_clocks_match"])
        self.assertEqual(result["first_clock_mismatch_invocation"], 1)
        self.assertFalse(result["capture_state_hashes_valid"])

    def test_rejects_invalid_counter_sequence(self):
        capture = self.capture()
        capture["counter_sequence_valid"] = False
        result = compare_linked_capture(
            self.rom, self.bank, self.decoded, capture,
            sound_ids=(101, 106),
            captured_rom=build_probe(self.rom, sound_ids=(101, 106)),
        )
        self.assertFalse(result["verification_passed"])


if __name__ == "__main__":
    unittest.main()
