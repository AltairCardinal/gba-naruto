#!/usr/bin/env python3
import unittest
import json
import struct
from collections import Counter
from pathlib import Path

from tools.m4a_channels import (
    Channel,
    TrackChannels,
    cgb_can_allocate,
    clear_chain,
    direct_channel_index,
    effective_priority,
    link_head,
    release_first_key,
)


ACTIVE = 0x03
RELEASED = 0x43


class M4AChannelTests(unittest.TestCase):
    def test_priority_clamps_player_plus_track(self):
        self.assertEqual(effective_priority(250, 10), 255)
        self.assertEqual(effective_priority(0, 0), 0)

    def test_rom_mode_and_song_priorities_define_actual_allocator_scope(self):
        rom = Path("rom/base.gba").read_bytes()
        self.assertEqual(struct.unpack_from("<I", rom, 0x9AAA4)[0], 0x0095FA00)
        bank = json.loads(Path("sequel/content/audio/bank.json").read_text())
        self.assertEqual(
            Counter(entry["priority"] for entry in bank["entries"]),
            Counter({255: 58, 0: 18, 10: 4}),
        )

    def test_direct_first_free_stops_scan(self):
        channels = [
            Channel(status=ACTIVE, priority=40, track_ptr=0x100),
            Channel(),
            Channel(),
        ]
        self.assertEqual(direct_channel_index(channels, 50, 0x300), 1)

    def test_direct_active_and_release_selection(self):
        active = [
            Channel(status=ACTIVE, priority=60, track_ptr=0x100),
            Channel(status=ACTIVE, priority=40, track_ptr=0x100),
            Channel(status=ACTIVE, priority=40, track_ptr=0x200),
        ]
        self.assertEqual(direct_channel_index(active, 50, 0x300), 2)

        active.append(Channel(status=RELEASED, priority=255, track_ptr=0x010))
        self.assertEqual(direct_channel_index(active, 50, 0x300), 3)

        releases = [
            Channel(status=RELEASED, priority=20, track_ptr=0x100),
            Channel(status=RELEASED, priority=20, track_ptr=0x300),
            Channel(status=RELEASED, priority=10, track_ptr=0x050),
        ]
        self.assertEqual(direct_channel_index(releases, 50, 0x100), 2)

    def test_direct_equal_priority_requires_strictly_higher_old_track(self):
        self.assertEqual(
            direct_channel_index(
                [Channel(status=ACTIVE, priority=50, track_ptr=0x200)],
                50, 0x100,
            ),
            0,
        )
        for old_track in (0x100, 0x080):
            self.assertIsNone(direct_channel_index(
                [Channel(status=ACTIVE, priority=50, track_ptr=old_track)],
                50, 0x100,
            ))

    def test_cgb_equal_priority_allows_same_track_retrigger(self):
        self.assertTrue(cgb_can_allocate(
            Channel(status=ACTIVE, priority=50, track_ptr=0x100), 50, 0x100
        ))
        self.assertFalse(cgb_can_allocate(
            Channel(status=ACTIVE, priority=50, track_ptr=0x080), 50, 0x100
        ))
        self.assertTrue(cgb_can_allocate(
            Channel(status=ACTIVE, priority=49, track_ptr=0x080), 50, 0x100
        ))
        self.assertFalse(cgb_can_allocate(
            Channel(status=ACTIVE, priority=51, track_ptr=0x200), 50, 0x100
        ))
        self.assertTrue(cgb_can_allocate(Channel(status=RELEASED), 0, 0x100))

    def test_newest_first_chain_and_same_key_eot(self):
        channels = [
            Channel(status=ACTIVE, midi_key=60),
            Channel(status=ACTIVE, midi_key=60),
        ]
        track = TrackChannels(track_ptr=0x100)
        link_head(channels, track, 0)
        link_head(channels, track, 1)
        self.assertEqual((track.head, channels[1].next, channels[0].prev), (1, 0, 1))
        self.assertEqual(release_first_key(channels, track, 60), 1)
        self.assertEqual(channels[1].status & 0x40, 0x40)
        self.assertEqual(channels[0].status & 0x40, 0)
        clear_chain(channels, track, 1)
        self.assertEqual((track.head, channels[0].prev, channels[1].track_ptr), (0, None, 0))


if __name__ == "__main__":
    unittest.main()
