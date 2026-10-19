import importlib
import unittest

from tests.thumb_observer_machine import execute_stub


try:
    observer = importlib.import_module("tools.published_call_observer")
except ModuleNotFoundError:
    observer = None


@unittest.skipIf(observer is None, "shared published-call observer is not implemented")
class PublishedCallObserverTests(unittest.TestCase):
    def setUp(self):
        self.player = observer.ObserverSite(
            name="player-control",
            hook=0x08073946,
            original=0x0806F718,
            stub=0x0809E800,
            scratch=0x0203F080,
            magic=int.from_bytes(b"PCO1", "little"),
            event_code=1,
        )
        self.current = observer.ObserverSite(
            name="current-unit",
            hook=0x080739D8,
            original=0x08069DB8,
            stub=0x0809E880,
            scratch=0x0203F060,
            magic=int.from_bytes(b"PCU1", "little"),
            event_code=2,
        )
        self.event_counter = 0x0203F040

    def test_layouts_do_not_overlap(self):
        self.assertIsNone(
            observer.assert_non_overlapping_sites(
                [self.player, self.current], self.event_counter, 4, 96
            )
        )

    def test_overlapping_record_or_stub_is_rejected(self):
        duplicate_record = observer.ObserverSite(
            **{**self.current.__dict__, "scratch": self.player.scratch}
        )
        with self.assertRaisesRegex(ValueError, "overlap"):
            observer.assert_non_overlapping_sites(
                [self.player, duplicate_record], self.event_counter, 4, 96
            )
        duplicate_stub = observer.ObserverSite(
            **{**self.current.__dict__, "stub": self.player.stub + 32}
        )
        with self.assertRaisesRegex(ValueError, "overlap"):
            observer.assert_non_overlapping_sites(
                [self.player, duplicate_stub], self.event_counter, 4, 96
            )

    def test_published_record_contains_fresh_shared_sequence(self):
        initial = {"r0": 9, "r1": 0x12340000, "r2": 0x56780001, "r3": 0x33, "r4": 0x44}
        state = execute_stub(
            observer.build_observer_stub(self.player, self.event_counter, 96),
            registers=initial,
            memory={self.event_counter: 6},
        )

        self.assertEqual(state.read_u32(self.player.scratch + 4), 1)
        self.assertEqual(state.read_u32(self.player.scratch + 8), 9)
        self.assertEqual(state.read_u16(self.player.scratch + 12), 0)
        self.assertEqual(state.read_u16(self.player.scratch + 14), 1)
        self.assertEqual(state.read_u32(self.player.scratch + 16), 7)
        self.assertEqual(state.read_u32(self.player.scratch + 20), self.player.event_code)
        self.assertEqual(state.read_u32(self.player.scratch), self.player.magic)
        self.assertEqual(state.read_u32(self.event_counter), 7)

        scratch_writes = [write for write in state.writes if self.player.scratch <= write[0] < self.player.scratch + 24]
        self.assertEqual(scratch_writes[0], (self.player.scratch, 4, 0))
        self.assertEqual(scratch_writes[-1], (self.player.scratch, 4, self.player.magic))

    def test_second_valid_hit_increments_existing_hit_count(self):
        stub = observer.build_observer_stub(self.player, self.event_counter, 96)
        first = execute_stub(stub, memory={self.event_counter: 10})
        second = execute_stub(stub, memory_bytes=first.memory)

        self.assertEqual(second.read_u32(self.player.scratch + 4), 2)
        self.assertEqual(second.read_u32(self.event_counter), 12)
        self.assertEqual(second.read_u32(self.player.scratch + 16), 12)
        scratch_writes = [
            write
            for write in second.writes
            if self.player.scratch <= write[0] < self.player.scratch + 24
        ]
        self.assertEqual(scratch_writes[0], (self.player.scratch, 4, 0))
        self.assertEqual(scratch_writes[-1], (self.player.scratch, 4, self.player.magic))

    def test_hit_count_and_shared_sequence_wrap_to_zero(self):
        memory = {
            self.event_counter: 0xFFFFFFFF,
            self.player.scratch: self.player.magic,
            self.player.scratch + 4: 0xFFFFFFFF,
        }
        state = execute_stub(
            observer.build_observer_stub(self.player, self.event_counter, 96),
            memory=memory,
        )

        self.assertEqual(state.read_u32(self.player.scratch + 4), 0)
        self.assertEqual(state.read_u32(self.event_counter), 0)
        self.assertEqual(state.read_u32(self.player.scratch + 16), 0)
        self.assertEqual(state.read_u32(self.player.scratch), self.player.magic)

    def test_stub_restores_r0_through_r4_sp_and_lr_then_tail_branches(self):
        initial = {
            "r0": 0x10,
            "r1": 0x21,
            "r2": 0x32,
            "r3": 0x43,
            "r4": 0x54,
            "sp": 0x03007E00,
            "lr": 0x0807394B,
        }
        for site in (self.player, self.current):
            with self.subTest(site=site.name):
                state = execute_stub(
                    observer.build_observer_stub(site, self.event_counter, 96),
                    registers=initial,
                    memory={self.event_counter: 10},
                )
                for register in ("r0", "r1", "r2", "r3", "r4", "sp", "lr"):
                    self.assertEqual(state.registers[register], initial[register])
                self.assertEqual(state.branch_target, site.original | 1)

    def test_stub_must_fit_reserved_cave(self):
        with self.assertRaisesRegex(ValueError, "stub_size"):
            observer.build_observer_stub(self.player, self.event_counter, 80)


class PublishedCallObserverAvailabilityTests(unittest.TestCase):
    def test_shared_module_is_available(self):
        self.assertIsNotNone(observer, "tools.published_call_observer must exist")


if __name__ == "__main__":
    unittest.main()
