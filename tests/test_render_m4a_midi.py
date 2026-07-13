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

    def test_tie_is_sustained_until_matching_eot(self):
        commands = decode_track(bytes.fromhex("cf3c648cce3cb1"), 0x600)
        result = execute_track(
            {"offset": 0x600}, {item["offset"]: item for item in commands}
        )
        notes = [event for event in result["events"] if event["type"] == "note"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["key"], 60)
        self.assertTrue(notes[0]["tied"])
        self.assertEqual(notes[0]["duration"], 12)
        midi = midi_file([result])
        self.assertIn(bytes((0x90, 60, 100)), midi)
        self.assertIn(bytes((0x80, 60, 0)), midi)

    def test_unkeyed_eot_closes_the_running_tie_key(self):
        commands = decode_track(bytes.fromhex("cf40648cceb1"), 0x700)
        result = execute_track(
            {"offset": 0x700}, {item["offset"]: item for item in commands}
        )
        note = next(event for event in result["events"] if event["type"] == "note")
        self.assertEqual(note["key"], 64)
        self.assertEqual(note["duration"], 12)

    def test_note_snapshots_exact_track_pitch_state(self):
        # KEYSH=-2, BEND=-32, BENDR=12, TUNE=+4.
        commands = decode_track(bytes.fromhex("bcfec020c10cc844d33c64b1"), 0x800)
        result = execute_track(
            {"offset": 0x800}, {item["offset"]: item for item in commands}
        )
        note = next(event for event in result["events"] if event["type"] == "note")
        self.assertEqual(note["key"], 60)
        self.assertEqual(note["pitch_key"], 52)
        self.assertEqual(note["pitch_fine"], 16)
        self.assertEqual(
            note["pitch_components"],
            {"key_shift": -2, "bend": -32, "bend_range": 12, "tune": 4},
        )

    def test_mid_note_bend_emits_timed_pitch_state(self):
        # N12 C4, wait 6, bend down one semitone with default range 2.
        commands = decode_track(bytes.fromhex("db3c6486c02086b1"), 0x900)
        result = execute_track(
            {"offset": 0x900}, {item["offset"]: item for item in commands}
        )
        updates = [
            event for event in result["events"] if event["type"] == "pitch_state"
        ]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["tick"], 6)
        self.assertEqual(updates[0]["pitch_key_delta"], -1)
        self.assertEqual(updates[0]["pitch_fine"], 0)

    def test_pitch_lfo_emits_exact_triangle_updates_each_tick(self):
        # LFOS=64, MOD depth=64, MODT defaults to pitch; phase is 64/128/192/0.
        commands = decode_track(bytes.fromhex("c240c440db3c6484b1"), 0xA00)
        result = execute_track(
            {"offset": 0xA00}, {item["offset"]: item for item in commands}
        )
        updates = [
            event
            for event in result["events"]
            if event["type"] == "pitch_state" and event["command"] == "LFO"
        ]
        self.assertEqual(
            [(event["tick"], event["pitch_key_delta"], event["pitch_fine"]) for event in updates],
            [(1, 4, 0), (2, 0, 0), (3, -4, 0), (4, 0, 0)],
        )

    def test_all_sound_ids_render_nonempty_standard_midi(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = render(
                Path("build/audio-v2"), Path("sequel/content/audio/bank.json"), Path(tmp)
            )
            self.assertEqual(result["song_count"], 80)
            self.assertTrue(all(song["duration_ticks"] > 0 for song in result["songs"]))
            self.assertTrue(all(song["event_count"] > 0 for song in result["songs"]))
            self.assertTrue(all((Path(tmp) / song["midi"]).read_bytes().startswith(b"MThd") for song in result["songs"]))
            self.assertEqual(
                result["tie_lifecycle"],
                {"total": 90, "closed_by_eot": 25, "left_open_at_loop_end": 65},
            )
            self.assertEqual(result["total_event_count"], 38530)
            self.assertEqual(result["event_type_counts"]["pitch_state"], 21328)


if __name__ == "__main__":
    unittest.main()
