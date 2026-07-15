#!/usr/bin/env python3
import struct
import unittest
from pathlib import Path

from tools.extract_audio_cue_calls import encode_thumb_bl, scan_calls
from tools.thumb_branch import encode_thumb_bl as shared_encode_thumb_bl


class AudioCueCallExtractionTests(unittest.TestCase):
    def test_public_encoder_is_shared(self):
        self.assertIs(encode_thumb_bl, shared_encode_thumb_bl)

    def test_thumb_bl_round_trip_and_immediate_sound_id(self):
        base = 0x08000000
        target = 0x08000100
        callsite = base + 2
        rom = bytearray(0x200)
        struct.pack_into("<H", rom, 0, 0x2076)  # movs r0, #118
        rom[2:6] = encode_thumb_bl(callsite, target)

        calls = scan_calls(bytes(rom), target=target, rom_base=base)

        self.assertEqual(calls, [{
            "callsite": callsite,
            "callsite_hex": "0x08000002",
            "source": "immediate",
            "sound_id": 118,
        }])

    def test_register_source_is_not_guessed(self):
        base = 0x08000000
        target = 0x08000100
        callsite = base + 2
        rom = bytearray(0x200)
        struct.pack_into("<H", rom, 0, 0x1C20)  # adds r0, r4, #0
        rom[2:6] = encode_thumb_bl(callsite, target)

        self.assertEqual(
            scan_calls(bytes(rom), target=target, rom_base=base)[0],
            {
                "callsite": callsite,
                "callsite_hex": "0x08000002",
                "source": "dynamic",
                "sound_id": None,
            },
        )

    def test_real_rom_call_inventory_is_stable(self):
        calls = scan_calls(
            Path("rom/base.gba").read_bytes(), target=0x08061E6C
        )
        immediate = [call for call in calls if call["source"] == "immediate"]
        dynamic = [call for call in calls if call["source"] == "dynamic"]

        self.assertEqual((len(calls), len(immediate), len(dynamic)), (290, 278, 12))
        self.assertEqual(len({call["sound_id"] for call in immediate}), 38)
        self.assertEqual(
            [call["callsite"] for call in dynamic],
            [
                0x08061F58, 0x0807BB84, 0x0807BD64, 0x0807C05A,
                0x0807C1E2, 0x0807CC98, 0x08081528, 0x08088294,
                0x0809715C, 0x08098944, 0x08099628, 0x08099806,
            ],
        )


if __name__ == "__main__":
    unittest.main()
