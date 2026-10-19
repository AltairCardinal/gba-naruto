import importlib.util
import unittest
from pathlib import Path


class AdvanceProbeTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('advance_probe', Path(__file__).with_name('advance_probe.py'))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.rom = Path('rom/base.gba').read_bytes()
        self.sequence = 0x458578

    def test_freeze_eight_skips_sequence_reads(self):
        report = self.m.probe(self.rom, self.sequence, flags=9, count=255)
        self.assertEqual(report['sequence_reads'], [])
        self.assertEqual(report['slot'], 0)
        self.assertEqual(report['timer'], 0)

    def test_bit_eight_alone_does_not_freeze(self):
        report = self.m.probe(self.rom, self.sequence, flags=0x101, count=1)
        self.assertIn([self.sequence + 2, 2], report['sequence_reads'])
        self.assertEqual(report['flags'] & 1, 0)

    def test_mode_twenty_second_iteration_reads_sentinel_duration(self):
        report = self.m.probe(self.rom, self.sequence, flags=0x21, count=2)
        self.assertIn([self.sequence + 6, 2], report['sequence_reads'])
        self.assertEqual(report['slot'], 0)
        self.assertEqual(report['timer'], 1)

    def test_mode_twenty_one_iteration_does_not_read_suffix(self):
        report = self.m.probe(self.rom, self.sequence, flags=0x21, count=1)
        self.assertNotIn([self.sequence + 6, 2], report['sequence_reads'])
        self.assertEqual(report['timer'], 0)

    def test_mode_thirty_uses_real_group_reset_helper(self):
        report = self.m.probe(self.rom, self.sequence, flags=0x31, count=1)
        self.assertIn(0x62798, report['visited'])
        self.assertEqual((report['group'], report['slot'], report['timer']), (0, 0, 0))
        self.assertEqual(report['flags'] & 4, 0)

    def test_byte_counter_maximum_keeps_mode_twenty_slot_zero(self):
        report = self.m.probe(self.rom, self.sequence, flags=0x21, count=255)
        self.assertEqual((report['slot'], report['timer']), (0, 254))
        self.assertEqual(max(a + n for a, n in report['sequence_reads']), self.sequence + 8)

    def test_non_sentinel_exposes_slot_increment(self):
        mutated = bytearray(self.rom)
        mutated[self.sequence + 4:self.sequence + 6] = b'\0\0'
        report = self.m.probe(bytes(mutated), self.sequence, flags=0x21, count=1)
        self.assertEqual(report['slot'], 1)

    def test_high_timer_wraps_with_u16_store(self):
        report = self.m.probe(self.rom, self.sequence, flags=0x21, count=2, timer=65535)
        self.assertEqual(report['slot'], 0)
        self.assertEqual(report['timer'], 0)

    def test_zero_counter_skips_all_updates(self):
        report = self.m.probe(self.rom, self.sequence, flags=1, count=0)
        self.assertEqual(report['sequence_reads'], [])

    def test_unknown_instruction_fails_closed(self):
        mutated = bytearray(self.rom)
        mutated[0x63244:0x63246] = bytes.fromhex('00df')
        with self.assertRaises(ValueError):
            self.m.probe(bytes(mutated), self.sequence, flags=9, count=1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
