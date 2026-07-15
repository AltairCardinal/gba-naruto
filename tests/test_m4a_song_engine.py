#!/usr/bin/env python3
import unittest
import json
import hashlib
from pathlib import Path

from tools.m4a_song_engine import M4ASongEngine
from tools.m4a_scheduler import BUFFER_FRAMES
from tools.m4a_pcm import interleave_wav_u8


class M4ASongEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path("rom/base.gba").read_bytes()
        cls.bank = json.loads(Path("sequel/content/audio/bank.json").read_text())
        cls.decoded = json.loads(Path("build/audio-v2/tracks-decoded.json").read_text())

    def engine(self, sound_id: int) -> M4ASongEngine:
        return M4ASongEngine.from_bank(
            self.rom, self.bank, self.decoded, sound_id=sound_id
        )

    def test_real_sfx_runs_player_ticks_before_each_directsound_chunk(self):
        engine = self.engine(101)
        first = engine.advance_soundmain()
        second = engine.advance_soundmain()
        self.assertEqual((first.chunk_index, second.chunk_index), (0, 1))
        self.assertEqual((first.tick_count, second.tick_count), (1, 1))
        self.assertEqual(len(engine.right), BUFFER_FRAMES * 2)
        self.assertFalse(any(first.right) or any(first.left))
        self.assertTrue(any(second.right) or any(second.left))
        self.assertEqual(len(engine.runners[0].allocations), 1)

    def test_tempo_command_updates_the_player_clock_for_later_invocations(self):
        engine = self.engine(1)
        first = engine.advance_soundmain()
        second = engine.advance_soundmain()
        self.assertEqual((first.tick_count, second.tick_count), (1, 1))
        self.assertEqual(engine.clock.tempo_i, 160)
        self.assertEqual(engine.clock.tempo_c, 10)

    def test_real_noise_sfx_retriggers_without_a_gap_then_stops_at_fine(self):
        engine = self.engine(144)
        steps = [engine.advance_soundmain() for _ in range(68)]
        audible = [any(step.right) or any(step.left) for step in steps]
        self.assertEqual(audible, [False] + [True] * 66 + [False])
        self.assertEqual(
            engine.channels.cgb[3].registers,
            {"NR41": 0x00, "NR42": 0x08, "NR43": 0x14, "NR44": 0x80, "NR51": 0x88},
        )
        self.assertEqual(engine.channels.cgb[3].status, 0)
        self.assertTrue(engine.finished)
        self.assertEqual(
            hashlib.sha256(interleave_wav_u8(engine.right, engine.left)).hexdigest(),
            "70eb804979782044634fa3b307cff5fdf84c6a6da04e0b09aa299a5176c2253d",
        )

    def test_bounded_render_stops_a_one_shot_but_not_a_looping_song(self):
        one_shot = self.engine(144)
        self.assertEqual(one_shot.render_until_finished(max_invocations=100), 68)
        self.assertTrue(one_shot.finished)

        looping = self.engine(1)
        self.assertEqual(looping.render_until_finished(max_invocations=16), 16)
        self.assertFalse(looping.finished)

    def test_loop_boundary_waits_until_every_looping_track_executes_goto(self):
        engine = self.engine(15)
        looping_tracks = set(engine.entry["track_ptrs"])
        count, reached = engine.render_until_loop_boundary(
            looping_tracks, max_invocations=500
        )
        self.assertEqual((count, reached), (388, True))
        self.assertTrue(all(
            runner.vm.command_counts["GOTO"] == 1 for runner in engine.runners
        ))

    def test_real_loop_records_ties_that_remain_active_at_goto(self):
        engine = self.engine(7)
        tracks = {track["offset"]: track for track in self.decoded["tracks"]}
        looping_tracks = {
            ptr for ptr in engine.entry["track_ptrs"]
            if any(
                command["name"] == "GOTO"
                for command in tracks[ptr - 0x08000000]["commands"]
            )
        }
        count, reached = engine.render_until_loop_boundary(
            looping_tracks, max_invocations=4000
        )
        self.assertTrue(reached)
        self.assertLess(count, 4000)
        first_crossing_ties = [
            snapshot
            for runner in engine.runners
            for snapshot in runner.goto_tie_snapshots[:1]
        ]
        self.assertEqual(len(first_crossing_ties), len(looping_tracks))
        self.assertGreater(sum(len(snapshot) for snapshot in first_crossing_ties), 0)


if __name__ == "__main__":
    unittest.main()
