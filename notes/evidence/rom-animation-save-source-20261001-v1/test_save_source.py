"""Raw-source partitions, callback binding, save/restore and freeze domains."""
import struct
import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from save_source import closure, raw_closure, binding, save, postbattle

ROM = (Path.cwd() / 'rom/base.gba').read_bytes()


class SaveSourceTests(unittest.TestCase):
    def test_direct_cfg_follows_branches_skips_calls_and_does_not_decode_literals(self):
        rom = struct.pack('<HHHHHH', 0x4801, 0xE002, 0x1234, 0x5678, 0x9ABC, 0x4770) + bytes(4)
        graph = closure(rom, 0, 12)
        self.assertEqual(graph['nodes'], [0, 2, 10])
        self.assertEqual(graph['literal_words'], [8])
        self.assertEqual(raw_closure(rom, 0, 12), graph['nodes'])

    def test_bounded_cfg_rejects_branch_escape_and_truncated_bl(self):
        with self.assertRaisesRegex(ValueError, 'escape'):
            closure(struct.pack('<HH', 0xE002, 0x4770), 0, 4)
        with self.assertRaises(ValueError):
            closure(struct.pack('<HH', 0xF000, 0xF800), 0, 2)

    def test_raw_oracle_follows_negative_conditional_backedge_and_call_fallthrough(self):
        rom = struct.pack('<HHHHH', 0x2000, 0xD1FD, 0xF000, 0xF802, 0x4770)
        graph = closure(rom, 0, 10)
        self.assertEqual(graph['nodes'], [0, 2, 4, 8])
        self.assertEqual(raw_closure(rom, 0, 10), graph['nodes'])
        self.assertEqual(graph['calls'], [{'at': 4, 'target': 12}])

    def test_callback_registration_binds_slot5_real_record_and_dispatch_pointer(self):
        result = binding(ROM)
        self.assertEqual(result['callback'], 0x0808584D)
        self.assertEqual(result['slot'], 5)
        self.assertEqual(result['callback_address'], 0x03000CF8)
        self.assertEqual(result['record_entry'], 0x08061CBD)
        self.assertEqual(result['argument'], 0)
        self.assertFalse(result['natural_execution_proven'])

    def test_callback_binding_rejects_pointer_and_registrar_mutations(self):
        for offset in (0x85A14, 0x61DC0):
            changed = bytearray(ROM)
            changed[offset] ^= 1
            with self.assertRaises(ValueError):
                binding(bytes(changed))

    def test_all_counter_values_save_exact_byte_and_set_one(self):
        for counter in range(256):
            trace = save(ROM, counter=counter, saved=0, guard=0, wait=0)
            self.assertEqual(trace['counter'], 1)
            self.assertEqual(trace['saved'], counter)
            self.assertEqual(trace['stop'], 0x85988)
            self.assertEqual(trace['callee_targets'], [0x64A48, 0x857E4])
            self.assertFalse(trace['context_resume_proven'])

    def test_existing_saved_blocks_new_save_and_valid_restore_clears_saved(self):
        for saved in (1, 0x80, 255):
            trace = save(ROM, counter=173, saved=saved, guard=0, wait=0)
            self.assertEqual((trace['counter'], trace['saved']), (173, saved))
            restored = save(ROM, counter=1, saved=saved, guard=0x303, wait=0)
            self.assertEqual((restored['counter'], restored['saved']), (saved, 0))
        zero = save(ROM, counter=1, saved=0, guard=0x303, wait=0)
        self.assertEqual((zero['counter'], zero['saved']), (1, 0))

    def test_timeout_freezes_only_active_128_objects_and_cleans_four_task_records(self):
        trace = save(ROM, counter=173, saved=201, guard=0, wait=59)
        self.assertEqual(trace['stop'], 0x858E4)
        self.assertEqual(trace['callee_targets'], [0x64A48, 0x857E4, *([0x61E00]*4), 0x857B8])
        self.assertEqual((trace['counter'], trace['saved']), (173, 0))
        self.assertEqual(len(trace['pool_flags']), 128)
        for slot, row in enumerate(trace['pool_flags']):
            self.assertEqual(row['after'], row['before'] | 8 if row['before'] & 1 else row['before'])
        self.assertEqual(trace['task_marker_stores'], 8)

    def test_busy_status_and_context_switch_are_fail_closed(self):
        trace = save(ROM, counter=173, saved=201, guard=0, wait=0, busy=1)
        self.assertEqual((trace['counter'], trace['saved']), (173, 201))
        self.assertEqual(trace['callee_targets'], [0x64A48])
        with self.assertRaisesRegex(ValueError, 'unexpected callee'):
            save(ROM, counter=173, saved=0, guard=0, wait=0, allow_stop=False)

    def test_freeze_all_active_all_inactive_and_high_flags_keep_128_slot_domain(self):
        for words in ([0xFFFFFFFF]*128, [0xFFFFFFFE]*128, [1 if n==127 else 0 for n in range(128)]):
            trace = save(ROM, counter=173, saved=201, guard=0, wait=59, flag_words=words)
            stores = [w for w in trace['writes'] if 0x03003BB8 <= w['address'] < 0x030059B8]
            self.assertEqual([w['address'] for w in stores], [0x03003BB8+60*n for n,v in enumerate(words) if v&1])
            self.assertEqual([r['after'] for r in trace['pool_flags']], [v|8 if v&1 else v for v in words])
        with self.assertRaises(ValueError):
            save(ROM, counter=0, saved=0, guard=0, wait=59, flag_words=[1]*129)

    def test_save_then_restore_roundtrip_retains_nonzero_but_zero_is_marker(self):
        for value in range(256):
            stored = save(ROM, counter=value, saved=0, guard=0, wait=0)
            restored = save(ROM, counter=stored['counter'], saved=stored['saved'], guard=0x303, wait=0)
            self.assertEqual(restored['counter'], value if value else 1)
            self.assertEqual(restored['saved'], 0)

    def test_postbattle_counter_store_stops_before_external_controller(self):
        trace = postbattle(ROM, counter=173)
        self.assertEqual(trace['counter'], 1)
        self.assertEqual(trace['stop'], 0x68DEC)
        self.assertFalse(trace['producer_entry_proven'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
