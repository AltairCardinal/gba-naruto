#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from tools.render_m4a_pcm_bank import render_bank


class RenderM4APcmBankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path("rom/base.gba").read_bytes()
        cls.bank = json.loads(Path("sequel/content/audio/bank.json").read_text())
        cls.decoded = json.loads(Path("build/audio-v2/tracks-decoded.json").read_text())

    def test_all_active_sound_ids_emit_deterministic_bounded_wav_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = render_bank(
                self.rom,
                self.bank,
                self.decoded,
                output,
                loop_invocations=2,
                max_one_shot_invocations=10,
            )
            self.assertEqual(manifest["song_count"], 80)
            self.assertEqual(manifest["looping_song_count"], 18)
            self.assertEqual(len(manifest["songs"]), 80)
            self.assertEqual(len(list(output.glob("sound_*.wav"))), 80)
            noise = next(row for row in manifest["songs"] if row["sound_id"] == 144)
            self.assertEqual(noise["render_invocations"], 10)
            self.assertFalse(noise["finished"])
            self.assertEqual(noise["cgb_allocations"], 2)
            self.assertGreater(noise["pcm_nonzero_frames"], 0)
            self.assertEqual((output / noise["wav"]).read_bytes()[:4], b"RIFF")

    def test_committed_full_render_evidence_covers_every_completion_policy(self):
        evidence = json.loads(
            Path("artifacts/audio/full-song-render-evidence.json").read_text()
        )
        self.assertEqual(
            (
                evidence["song_count"],
                evidence["looping_song_count"],
                evidence["naturally_finished_song_count"],
                evidence["loop_boundary_song_count"],
                evidence["silent_song_count"],
            ),
            (80, 18, 62, 18, 0),
        )
        self.assertEqual(evidence["totals"]["goto_commands"], 138)
        self.assertEqual(evidence["totals"]["cgb_allocations"], 11)
        self.assertEqual(evidence["totals"]["first_goto_active_ties"], 21)
        noise = next(row for row in evidence["songs"] if row["sound_id"] == 144)
        self.assertEqual(
            noise["pcm_sha256"],
            "70eb804979782044634fa3b307cff5fdf84c6a6da04e0b09aa299a5176c2253d",
        )


if __name__ == "__main__":
    unittest.main()
