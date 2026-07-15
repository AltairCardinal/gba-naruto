#!/usr/bin/env python3
import unittest

from tools.m4a_scheduler import (
    BUFFER_FRAMES,
    PCM_RING_CHUNKS,
    MPlayClock,
    PcmRing,
    SoundMainClock,
    advance_gate,
    tempo_increment,
)


class M4ASchedulerTests(unittest.TestCase):
    def test_tempo_opcode_and_threshold_accumulator(self):
        self.assertEqual(tempo_increment(75), 150)
        self.assertEqual(tempo_increment(60), 120)
        self.assertEqual(tempo_increment(75, tempo_u=128), 75)

        clock = MPlayClock(tempo_i=75)
        self.assertEqual([clock.advance() for _ in range(4)], [0, 1, 0, 1])
        self.assertEqual(clock.tempo_c, 0)

        clock = MPlayClock(tempo_i=225)
        self.assertEqual([clock.advance() for _ in range(2)], [1, 2])
        self.assertEqual(clock.tempo_c, 0)

    def test_all_player_ticks_precede_one_cgb_and_direct_mix(self):
        scheduler = SoundMainClock([
            MPlayClock(tempo_i=300),
            MPlayClock(tempo_i=150),
        ])
        events = []
        step = scheduler.advance(
            on_tick=lambda player, tick: events.append(("tick", player, tick)),
            on_cgb=lambda: events.append(("cgb",)),
            on_direct=lambda chunk, frames: events.append(("direct", chunk, frames)),
        )
        # MPlayMain recursively visits next players first. Player 0's two ticks
        # have no mixer invocation between them.
        self.assertEqual(events, [
            ("tick", 1, 0),
            ("tick", 0, 0),
            ("tick", 0, 1),
            ("cgb",),
            ("direct", 0, BUFFER_FRAMES),
        ])
        self.assertEqual(step.tick_counts, (2, 1))

    def test_gate_one_note_can_release_before_first_multi_tick_mix(self):
        # Tick 1's gate scan runs before the note exists. Tick 2 then sees the
        # newly-created gate=1 and releases it before the single mix callback.
        gate = 1
        gate, released = advance_gate(gate)
        self.assertEqual((gate, released), (0, True))

    def test_dma_chunk_sequence_is_six_by_264_ring(self):
        scheduler = SoundMainClock([])
        self.assertEqual(
            [scheduler.advance().chunk_index for _ in range(8)],
            [0, 1, 2, 3, 4, 5, 0, 1],
        )
        self.assertEqual(PCM_RING_CHUNKS * BUFFER_FRAMES, 1584)

    def test_reverb_seed_uses_current_and_next_old_ring_chunks(self):
        ring = PcmRing()
        ring.right[0] = 10
        ring.left[0] = 20
        ring.right[BUFFER_FRAMES] = 30
        ring.left[BUFFER_FRAMES] = 40
        seeded_right, seeded_left = ring.seed_chunk(0, reverb=128)
        self.assertEqual((seeded_right[0], seeded_left[0]), (25, 25))

        last = (PCM_RING_CHUNKS - 1) * BUFFER_FRAMES
        ring.right[last] = -1
        ring.left[last] = -1
        ring.right[0] = -1
        ring.left[0] = -1
        seeded_right, seeded_left = ring.seed_chunk(5, reverb=128)
        self.assertEqual((seeded_right[0], seeded_left[0]), (0, 0))


if __name__ == "__main__":
    unittest.main()
