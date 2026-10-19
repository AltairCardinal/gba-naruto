#!/usr/bin/env python3
import unittest

from tools.m4a_envelope import EnvelopeState, advance_envelope, mixer_gains


class M4AEnvelopeTests(unittest.TestCase):
    def test_attack_decay_and_sustain_vector(self):
        state = EnvelopeState.new()
        observed = []
        for _ in range(6):
            self.assertTrue(
                advance_envelope(
                    state, attack=64, decay=128, sustain=64, release=0,
                    pseudo_echo_volume=0,
                )
            )
            observed.append((state.phase, state.level))
        self.assertEqual(
            observed,
            [
                ("attack", 64),
                ("attack", 128),
                ("attack", 192),
                ("decay", 255),
                ("decay", 127),
                ("sustain", 64),
            ],
        )

    def test_zero_attack_remains_silent_attack(self):
        state = EnvelopeState.new()
        for _ in range(4):
            self.assertTrue(
                advance_envelope(
                    state, attack=0, decay=255, sustain=255, release=0,
                    pseudo_echo_volume=0,
                )
            )
        self.assertEqual((state.phase, state.level), ("attack", 0))

    def test_release_stops_at_zero_without_inventing_echo(self):
        state = EnvelopeState.release(level=64)
        levels = []
        while advance_envelope(
            state, attack=0, decay=0, sustain=0, release=128,
            pseudo_echo_volume=0,
        ):
            levels.append(state.level)
        self.assertEqual(levels, [32, 16, 8, 4, 2, 1])
        self.assertFalse(state.active)

    def test_pseudo_echo_threshold_and_counter(self):
        state = EnvelopeState.release(level=12, pseudo_echo_length=3)
        outputs = []
        for _ in range(5):
            if advance_envelope(
                state, attack=0, decay=0, sustain=0, release=128,
                pseudo_echo_volume=10,
            ):
                outputs.append((state.phase, state.level, state.echo_remaining))
        self.assertEqual(
            outputs,
            [("echo", 10, 3), ("echo", 10, 2), ("echo", 10, 1)],
        )
        self.assertFalse(state.active)

    def test_release_before_first_mix_is_silent(self):
        state = EnvelopeState.new(released=True)
        self.assertFalse(
            advance_envelope(
                state, attack=255, decay=0, sustain=255, release=255,
                pseudo_echo_volume=0,
            )
        )
        self.assertFalse(state.active)

    def test_master_and_pre_envelope_gain_formula(self):
        self.assertEqual(mixer_gains(128, 128, level=64, master_volume=15), (32, 32))
        self.assertEqual(mixer_gains(128, 128, level=255, master_volume=15), (127, 127))
        self.assertEqual(mixer_gains(128, 128, level=255, master_volume=7), (63, 63))
        self.assertEqual(mixer_gains(255, 255, level=255, master_volume=15), (254, 254))


if __name__ == "__main__":
    unittest.main()
