import hashlib
import json
import unittest
from pathlib import Path

from tools.compare_mgba_audio_capture import compare_capture
from tools.build_controlled_audio_runtime_probe import build_probe
from tools.m4a_song_engine import M4ASongEngine


ROOT = Path(__file__).resolve().parent.parent


class CompareMgbaAudioCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = json.loads((ROOT / "sequel/content/audio/bank.json").read_text())
        cls.decoded = json.loads((ROOT / "build/audio-v2/tracks-decoded.json").read_text())

    def capture_for_first_sound101_invocation(self):
        engine = M4ASongEngine.from_bank(
            self.rom, self.bank, self.decoded, sound_id=101
        )
        step = engine.advance_soundmain()
        right = bytes(sample & 0xFF for sample in step.right)
        left = bytes(sample & 0xFF for sample in step.left)
        pcm = bytearray()
        for right_sample, left_sample in zip(right, left):
            pcm.extend((right_sample, left_sample))
        return {
            "format": "gba-naruto-mgba-mp2k-capture-v1",
            "sound_id": 101,
            "timed_out": False,
            "counter_sequence_valid": True,
            "captures": [{
                "invocation": 0,
                "right_hex": right.hex(),
                "left_hex": left.hex(),
                "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
            }],
            "combined_pcm_sha256": hashlib.sha256(pcm).hexdigest(),
        }

    def test_accepts_byte_exact_real_engine_chunk(self):
        probe_rom = build_probe(self.rom, sound_ids=(101,))
        result = compare_capture(
            self.rom, self.bank, self.decoded,
            self.capture_for_first_sound101_invocation(),
            captured_rom=probe_rom,
            dispatch_sequence=(101,),
        )

        self.assertTrue(result["all_chunks_match"])
        self.assertTrue(result["combined_pcm_match"])
        self.assertEqual(result["matched_chunk_count"], 1)
        self.assertTrue(result["probe_rom_match"])
        self.assertTrue(result["verification_passed"])

    def test_recomputes_capture_hash_and_reports_corruption(self):
        capture = self.capture_for_first_sound101_invocation()
        capture["captures"][0]["right_hex"] = "01" + capture["captures"][0]["right_hex"][2:]

        result = compare_capture(
            self.rom, self.bank, self.decoded, capture,
            captured_rom=build_probe(self.rom, sound_ids=(101,)),
            dispatch_sequence=(101,),
        )

        self.assertFalse(result["all_chunks_match"])
        self.assertEqual(result["first_mismatch_invocation"], 0)
        self.assertFalse(result["capture_hashes_valid"])

    def test_binds_controlled_dispatch_sequence_to_probe_rom(self):
        capture = self.capture_for_first_sound101_invocation()
        probe_rom = build_probe(self.rom, sound_ids=(102, 101))

        result = compare_capture(
            self.rom, self.bank, self.decoded, capture,
            captured_rom=probe_rom,
            dispatch_sequence=(102, 101),
        )

        self.assertEqual(result["dispatch_sequence"], [102, 101])
        self.assertEqual(result["final_sound_id"], 101)
        self.assertTrue(result["probe_rom_match"])

        wrong = compare_capture(
            self.rom, self.bank, self.decoded, capture,
            captured_rom=build_probe(self.rom, sound_ids=(101,)),
            dispatch_sequence=(102, 101),
        )
        self.assertFalse(wrong["probe_rom_match"])
        self.assertFalse(wrong["verification_passed"])

    def test_rejects_invalid_counter_sequence(self):
        capture = self.capture_for_first_sound101_invocation()
        capture["counter_sequence_valid"] = False
        result = compare_capture(
            self.rom, self.bank, self.decoded, capture,
            captured_rom=build_probe(self.rom, sound_ids=(101,)),
            dispatch_sequence=(101,),
        )
        self.assertFalse(result["verification_passed"])


if __name__ == "__main__":
    unittest.main()
