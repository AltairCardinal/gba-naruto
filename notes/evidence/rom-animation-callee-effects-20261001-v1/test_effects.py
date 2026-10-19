import importlib.util
from pathlib import Path
import struct
import unittest


def bl(at, target):
    delta = (target-at-4) & 0x7fffff
    return struct.pack('<HH', 0xf000 | (delta >> 12), 0xf800 | ((delta >> 1) & 2047))


class EffectsTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('callee_effects', Path(__file__).with_name('callee_effects.py'))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.base = Path('rom/base.gba').read_bytes()

    def case(self, pieces, **kw):
        raw = bytearray(self.base)
        for at, value in pieces.items():
            raw[at:at+len(value)] = value
        return self.m.analyze(bytes(raw), min(pieces), set(pieces), **kw)

    def test_leaf_only_changes_low_registers(self):
        result = self.case({0x100: bytes.fromhex('0120'), 0x102: bytes.fromhex('7047')})
        self.assertEqual(result['preserved_registers'], list(range(1, 15)))
        self.assertTrue(result['return_identity_proven'])
        self.assertFalse(result['conditional'])

    def test_saved_frame_restores_register_after_opaque_child(self):
        parts = {0x100: bytes.fromhex('10b5'), 0x102: bl(0x102, 0x6571c),
                 0x106: bytes.fromhex('10bc'), 0x108: bytes.fromhex('01bc'), 0x10a: bytes.fromhex('0047')}
        result = self.case(parts, conditional_frame=True)
        self.assertIn(4, result['preserved_registers'])
        self.assertNotIn(5, result['preserved_registers'])
        self.assertTrue(result['conditional'])
        self.assertEqual(result['child_call_targets'], [0x6571c])

    def test_opaque_child_without_frame_contract_stays_frontier(self):
        result = self.case({0x100: bytes.fromhex('10b5'), 0x102: bl(0x102, 0x6571c),
                            0x106: bytes.fromhex('10bd')})
        self.assertFalse(result['return_identity_proven'])
        self.assertEqual(result['frontiers'][0]['kind'], 'opaque_child_call')

    def test_high_register_save_restore_uses_actual_stack_tokens(self):
        result = self.case({0x100: bytes.fromhex('0046'), 0x102: bytes.fromhex('10b5'),
                            0x104: bytes.fromhex('4c46'), 0x106: bytes.fromhex('10b4'),
                            0x108: bytes.fromhex('0024'), 0x10a: bytes.fromhex('a146'),
                            0x10c: bytes.fromhex('01bc'), 0x10e: bytes.fromhex('8146'),
                            0x110: bytes.fromhex('10bc'), 0x112: bytes.fromhex('01bc'),
                            0x114: bytes.fromhex('0047')})
        self.assertIn(9, result['preserved_registers'])

    def test_one_return_path_clobbers_saved_register(self):
        result = self.case({0x100: bytes.fromhex('0028'), 0x102: bytes.fromhex('01d0'),
                            0x104: bytes.fromhex('0124'), 0x106: bytes.fromhex('7047'),
                            0x108: bytes.fromhex('7047')})
        self.assertNotIn(4, result['preserved_registers'])
        self.assertEqual(result['return_count'], 2)

    def test_unknown_store_can_destroy_saved_return_word(self):
        result = self.case({0x100: bytes.fromhex('10b5'), 0x102: bytes.fromhex('0860'),
                            0x104: bytes.fromhex('10bc'), 0x106: bytes.fromhex('01bc'),
                            0x108: bytes.fromhex('0047')})
        self.assertFalse(result['return_identity_proven'])
        self.assertTrue(any(f['kind']=='unproved_return_identity' for f in result['frontiers']))

    def test_conditional_store_contract_does_not_preserve_caller_memory(self):
        result = self.case({0x100: bytes.fromhex('10b5'), 0x102: bytes.fromhex('0860'),
                            0x104: bytes.fromhex('10bc'), 0x106: bytes.fromhex('01bc'),
                            0x108: bytes.fromhex('0047')}, conditional_frame=True)
        self.assertTrue(result['return_identity_proven'])
        self.assertFalse(result['caller_stack_facts_preserved'])
        self.assertTrue(result['conditional'])

    def test_svc_effects_are_not_invented(self):
        result = self.case({0x100: bytes.fromhex('0bdf'), 0x102: bytes.fromhex('7047')}, conditional_frame=True)
        self.assertFalse(result['return_identity_proven'])
        self.assertEqual(result['frontiers'][0]['kind'], 'external_svc')

    def test_dynamic_sp_write_rejected(self):
        with self.assertRaises(ValueError):
            self.case({0x100: bytes.fromhex('8546'), 0x102: bytes.fromhex('7047')})

    def test_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            self.case({0x100: bl(0x100, 0x6571c), 0x102: bytes.fromhex('7047')})

    def test_budget_exhaustion_is_not_a_valid_contract(self):
        with self.assertRaises(ValueError):
            self.case({0x100: bytes.fromhex('0120'), 0x102: bytes.fromhex('7047')}, budget=1)


    def test_sp_alias_stm_is_not_excused_as_disjoint_store(self):
        result = self.case({0x100: bytes.fromhex('10b5'),0x102: bytes.fromhex('6946'),
                            0x104: bytes.fromhex('01c1'),0x106: bytes.fromhex('10bc'),
                            0x108: bytes.fromhex('01bc'),0x10a: bytes.fromhex('0047')},conditional_frame=True)
        self.assertNotIn(4,result['preserved_registers'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
