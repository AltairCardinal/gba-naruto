import json
import unittest
from pathlib import Path

from tools.compare_mgba_cgb_capture import compare_cgb_capture


ROOT = Path(__file__).resolve().parent.parent


class CompareMgbaCgbCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = json.loads((ROOT / "sequel/content/audio/bank.json").read_text())
        cls.decoded = json.loads((ROOT / "build/audio-v2/tracks-decoded.json").read_text())

    def capture(self):
        idle_io = bytearray(0x30)
        idle_io[0x19] = 0x08
        active_io = bytearray(idle_io)
        active_io[0x19] = 0x18
        active_io[0x1C] = 0x14
        active_io[0x21] = 0x88
        idle_state = bytes(0x100)
        active_state = bytearray(0x100)
        active_state[0xC0] = 1
        zero_plane = bytes(264).hex()
        return {
            "format": "gba-naruto-mgba-mp2k-capture-v1",
            "sound_id": 144,
            "timed_out": False,
            "counter_sequence_valid": True,
            "captures": [
                {
                    "invocation": 0,
                    "cgb_io_hex": idle_io.hex(),
                    "cgb_state_hex": idle_state.hex(),
                    "right_hex": zero_plane,
                    "left_hex": zero_plane,
                },
                {
                    "invocation": 1,
                    "cgb_io_hex": active_io.hex(),
                    "cgb_state_hex": bytes(active_state).hex(),
                    "right_hex": zero_plane,
                    "left_hex": zero_plane,
                },
            ],
        }

    def test_matches_visible_noise_register_and_channel_status_timeline(self):
        result = compare_cgb_capture(
            self.rom, self.bank, self.decoded, self.capture()
        )

        self.assertTrue(result["all_visible_registers_match"])
        self.assertTrue(result["all_channel_statuses_match"])
        self.assertTrue(result["direct_fifo_silent"])

    def test_reports_register_mismatch(self):
        capture = self.capture()
        io = bytearray.fromhex(capture["captures"][1]["cgb_io_hex"])
        io[0x19] = 0x28
        capture["captures"][1]["cgb_io_hex"] = io.hex()

        result = compare_cgb_capture(
            self.rom, self.bank, self.decoded, capture
        )

        self.assertFalse(result["all_visible_registers_match"])
        self.assertEqual(result["first_register_mismatch_invocation"], 1)


if __name__ == "__main__":
    unittest.main()
