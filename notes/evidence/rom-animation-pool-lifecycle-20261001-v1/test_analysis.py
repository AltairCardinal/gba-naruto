import importlib.util
import struct
import unittest
from pathlib import Path


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name('analysis.py')
        spec = importlib.util.spec_from_file_location('animation_analysis', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_flags_and_callback_are_distinct_stack_arguments(self):
        # MOV r2,8; STR r2,[SP+12]; MOV r2,0; STR r2,[SP+16].
        rom = bytes.fromhex('0822039200220492')
        state = self.module.argument_path(rom, 0, 8)
        self.assertEqual(state['stack'], {12: 8, 16: 0})
        self.assertEqual(state['registers'][2], 0)

    def test_unknown_load_clobbers_previous_constant(self):
        state = self.module.argument_path(bytes.fromhex('002209680491'), 0, 6)
        self.assertNotIn(1, state['registers'])
        self.assertNotIn(16, state['stack'])

    def test_call_and_branch_are_not_skipped(self):
        for raw in ('002200e0', '0022fff7ffff'):
            with self.assertRaises(ValueError):
                self.module.argument_path(bytes.fromhex(raw), 0, len(bytes.fromhex(raw)))

    def test_literal_and_shift_reconstruct_base_arguments(self):
        rom = bytes.fromhex('0148082252010000') + struct.pack('<I', 0x08458510)
        state = self.module.argument_path(rom, 0, 6)
        self.assertEqual(state['registers'][0], 0x08458510)
        self.assertEqual(state['registers'][2], 0x100)

    def test_unknown_stack_overwrite_discards_old_value(self):
        state = self.module.argument_path(bytes.fromhex('082203920393'), 0, 6)
        self.assertNotIn(12, state['stack'])

    def test_unbounded_store_does_not_leave_stack_facts(self):
        result = self.module.argument_path(bytes.fromhex('082203920a60'), 0, 6)
        self.assertEqual(result['stack'], {})
        self.assertEqual(result['registers'][2], 8)

    def test_descriptor_reads_only_sentinel_head(self):
        rom = b'\0' * 20 + bytes.fromhex('ffffdead')
        parsed = self.module.descriptor(rom, 0, len(rom))
        self.assertEqual(parsed['entry_ranges'], [[0, 20]])
        self.assertEqual(parsed['sentinel_head_range'], [20, 22])
        self.assertEqual(parsed['consumed_range'], [0, 22])

    def test_missing_descriptor_sentinel_fails_closed(self):
        with self.assertRaises(ValueError):
            self.module.descriptor(b'\0' * 40, 0, 40)

    def test_flags_mask_is_eight_not_bit_eight(self):
        self.assertEqual(self.module.freeze_mask(bytes.fromhex('08200840'), 0), 8)
        with self.assertRaises(ValueError):
            self.module.freeze_mask(bytes.fromhex('01200840'), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
