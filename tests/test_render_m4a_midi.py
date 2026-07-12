#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from tools.decode_m4a_tracks import decode_track
from tools.render_m4a_midi import execute_track, midi_file, render


class RenderM4AMidiTests(unittest.TestCase):
    def test_executes_pattern_and_stops_on_second_loop_entry(self):
        # Main: note, pattern call, wait, backward loop, FINE. Pattern: note/PEND.
        raw = bytes.fromhex("d33c640081b31101000881b200010008b1d3406400b4")
        commands = decode_track(raw, 0x100)
        command_map = {item["offset"]: item for item in commands}
        result = execute_track({"offset": 0x100}, command_map)
        self.assertEqual(result["stop_reason"], "one_loop")
        self.assertEqual([event["key"] for event in result["events"] if event["type"] == "note"], [60, 64])

    def test_midi_has_standard_header_and_track_chunk(self):
        data = midi_file([{"events": [{"tick": 0, "type": "note", "key": 60, "velocity": 100, "duration": 12}]}])
        self.assertEqual(data[:4], b"MThd")
        self.assertIn(b"MTrk", data)

    def test_pend_without_pattern_stack_falls_through(self):
        commands = decode_track(bytes((0xB4, 0x81, 0xB1)), 0x500)
        result = execute_track({"offset": 0x500}, {item["offset"]: item for item in commands})
        self.assertEqual(result["stop_reason"], "fine")
        self.assertEqual(result["duration_ticks"], 1)

    def test_all_sound_ids_render_nonempty_standard_midi(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = render(
                Path("build/audio-v2"), Path("sequel/content/audio/bank.json"), Path(tmp)
            )
            self.assertEqual(result["song_count"], 80)
            self.assertTrue(all(song["duration_ticks"] > 0 for song in result["songs"]))
            self.assertTrue(all(song["event_count"] > 0 for song in result["songs"]))
            self.assertTrue(all((Path(tmp) / song["midi"]).read_bytes().startswith(b"MThd") for song in result["songs"]))


if __name__ == "__main__":
    unittest.main()
