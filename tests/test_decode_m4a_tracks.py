#!/usr/bin/env python3
import struct
import unittest

from pathlib import Path

from tools.decode_m4a_tracks import DecodeError, decode_manifest, decode_track


class DecodeM4ATrackTests(unittest.TestCase):
    def test_decodes_control_parameters_notes_and_running_status(self):
        raw = bytes((0xBD, 3, 0xBE, 100, 0xD3, 60, 90, 0, 0x81, 62, 88, 0, 0xB1))
        commands = decode_track(raw, 0x100)
        self.assertEqual([item["name"] for item in commands], ["VOICE", "VOL", "N04", "W01", "N04", "FINE"])
        self.assertEqual(commands[4]["args"], [62, 88, 0])

    def test_decodes_little_endian_control_target(self):
        raw = bytes((0xB3,)) + struct.pack("<I", 0x0853C000) + bytes((0xB4,))
        commands = decode_track(raw, 0x200)
        self.assertEqual(commands[0]["target_offset"], 0x53C000)
        self.assertEqual(commands[1]["name"], "PEND")

    def test_rejects_parameter_without_running_note(self):
        with self.assertRaises(DecodeError):
            decode_track(bytes((60, 90, 0)), 0x300)

    def test_all_extracted_tracks_decode_with_valid_control_targets(self):
        result = decode_manifest(Path("build/audio-v2"))
        self.assertEqual(result["track_count"], 217)
        self.assertEqual(result["tracks_with_fine"], 217)
        self.assertEqual(result["invalid_control_targets"], [])
        self.assertEqual(result["note_count"], 6750)


if __name__ == "__main__":
    unittest.main()
