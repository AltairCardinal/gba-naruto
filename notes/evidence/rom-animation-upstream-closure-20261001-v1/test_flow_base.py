import importlib.util
import struct
import unittest
from pathlib import Path


def encode_bl(at, target):
    delta = (target - at - 4) & 0x7FFFFF
    return struct.pack('<HH', 0xF000 | (delta >> 12), 0xF800 | ((delta >> 1) & 2047))


class FlowTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('animation_flow', Path(__file__).with_name('flow.py'))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.base = Path('rom/base.gba').read_bytes()

    def fixture(self, parts):
        rom = bytearray(self.base)
        for at, raw in parts.items():
            rom[at:at + len(raw)] = raw
        return bytes(rom), set(parts)

    def test_branch_narrows_unknown_stack_load_to_zero(self):
        parts = {0x100: bytes.fromhex('129b'), 0x102: bytes.fromhex('002b'),
                 0x104: bytes.fromhex('05d1'), 0x106: bytes.fromhex('2024'),
                 0x108: bytes.fromhex('0394'), 0x10A: bytes.fromhex('0493'),
                 0x10C: encode_bl(0x10C, 0x626B4), 0x112: bytes.fromhex('7047')}
        rom, nodes = self.fixture(parts)
        result = self.m.run_flow(rom, nodes, {0x100})
        self.assertEqual(result['states'][0x10C]['stack'][16], 0)
        self.assertEqual(result['states'][0x10C]['stack'][12], 32)

    def test_join_does_not_select_one_successful_predecessor(self):
        # Unknown compare selects r4=8 or r4=32 before one call.
        parts = {0x100: bytes.fromhex('002b'), 0x102: bytes.fromhex('01d0'),
                 0x104: bytes.fromhex('0824'), 0x106: bytes.fromhex('00e0'),
                 0x108: bytes.fromhex('2024'), 0x10A: bytes.fromhex('0394'),
                 0x10C: encode_bl(0x10C, 0x626B4)}
        rom, nodes = self.fixture(parts)
        state = self.m.run_flow(rom, nodes, {0x100})['states'][0x10C]
        self.assertNotIn(12, state['stack'])

    def test_extra_root_removes_unproven_dominance(self):
        rom, nodes = self.fixture({0x100: bytes.fromhex('0824'), 0x102: bytes.fromhex('0394'),
                                   0x104: encode_bl(0x104, 0x626B4)})
        state = self.m.run_flow(rom, nodes, {0x100, 0x102})['states'][0x104]
        self.assertNotIn(12, state['stack'])

    def test_unknown_callee_does_not_preserve_high_register_constants(self):
        rom, nodes = self.fixture({0x100: bytes.fromhex('2024'), 0x102: encode_bl(0x102, 0x655B4),
                                   0x106: bytes.fromhex('0394'), 0x108: encode_bl(0x108, 0x626B4)})
        state = self.m.run_flow(rom, nodes, {0x100})['states'][0x108]
        self.assertNotIn(12, state['stack'])

    def test_allocator_preservation_requires_explicit_raw_contract(self):
        rom, nodes = self.fixture({0x100: bytes.fromhex('2024'), 0x102: encode_bl(0x102, 0x626B4),
                                   0x106: bytes.fromhex('0394'), 0x108: encode_bl(0x108, 0x626B4)})
        plain = self.m.run_flow(rom, nodes, {0x100})['states'][0x108]
        self.assertNotIn(12, plain['stack'])
        contract = self.m.allocator_contract(rom)
        state = self.m.run_flow(rom, nodes, {0x100}, allocator=contract)['states'][0x108]
        self.assertEqual(state['stack'][12], 32)
        self.assertTrue(state['conditional_allocator_preservation'])

    def test_allocator_call_discards_stack_facts_even_with_register_contract(self):
        rom, nodes = self.fixture({0x100: bytes.fromhex('0023'), 0x102: bytes.fromhex('0493'),
                                   0x104: encode_bl(0x104, 0x626B4), 0x108: bytes.fromhex('049b'),
                                   0x10A: bytes.fromhex('0493'), 0x10C: encode_bl(0x10C, 0x626B4)})
        contract = self.m.allocator_contract(rom)
        state = self.m.run_flow(rom, nodes, {0x100}, allocator=contract)['states'][0x10C]
        self.assertNotIn(16, state['stack'])

    def test_changed_allocator_restore_is_not_accepted(self):
        changed = bytearray(self.base)
        changed[0x6277A:0x6277C] = bytes.fromhex('9946')
        with self.assertRaises(ValueError):
            self.m.allocator_contract(bytes(changed))

    def test_unknown_store_invalidates_loaded_stack_origin(self):
        rom, nodes = self.fixture({0x100: bytes.fromhex('129b'), 0x102: bytes.fromhex('0a60'),
                                   0x104: bytes.fromhex('002b'), 0x106: bytes.fromhex('02d1'),
                                   0x108: bytes.fromhex('129a'), 0x10A: bytes.fromhex('0492'),
                                   0x10C: encode_bl(0x10C, 0x626B4)})
        state = self.m.run_flow(rom, nodes, {0x100})['states'][0x10C]
        self.assertNotIn(16, state['stack'])

    def test_budget_failure_is_explicit(self):
        rom, nodes = self.fixture({0x100: bytes.fromhex('0824'), 0x102: bytes.fromhex('0394')})
        with self.assertRaises(ValueError):
            self.m.run_flow(rom, nodes, {0x100}, budget=1)

    def test_changed_flags_do_not_reuse_old_compare_predicate(self):
        rom, nodes = self.fixture({0x100: bytes.fromhex('129b'), 0x102: bytes.fromhex('002b'),
                                   0x104: bytes.fromhex('0120'), 0x106: bytes.fromhex('02d1'),
                                   0x108: bytes.fromhex('0493'), 0x10A: encode_bl(0x10A, 0x626B4)})
        result = self.m.run_flow(rom, nodes, {0x100})
        self.assertNotIn(16, result['states'][0x10A]['stack'])

    def test_forged_allocator_contract_is_rejected(self):
        rom, nodes = self.fixture({0x100: encode_bl(0x100, 0x626B4)})
        contract = self.m.allocator_contract(rom)
        contract['caller_stack_facts_preserved'] = True
        with self.assertRaises(ValueError):
            self.m.run_flow(rom, nodes, {0x100}, allocator=contract)

    def test_bl_suffix_cannot_be_independent_source_instruction(self):
        rom, nodes = self.fixture({0x100: encode_bl(0x100, 0x626B4)})
        with self.assertRaises(ValueError):
            self.m.run_flow(rom, nodes | {0x102}, {0x100})


    def test_changed_compared_register_does_not_narrow_new_value(self):
        rom, nodes = self.fixture({0x100: bytes.fromhex('129b'), 0x102: bytes.fromhex('002b'),
                                   0x104: bytes.fromhex('0346'), 0x106: bytes.fromhex('02d1'),
                                   0x108: bytes.fromhex('0493'), 0x10A: encode_bl(0x10A, 0x626B4)})
        state = self.m.run_flow(rom, nodes, {0x100})['states'][0x10A]
        self.assertNotIn(16, state['stack'])

    def test_stack_reload_overwriting_compared_register_does_not_narrow(self):
        rom, nodes = self.fixture({0x100: bytes.fromhex('129b'), 0x102: bytes.fromhex('002b'),
                                   0x104: bytes.fromhex('139b'), 0x106: bytes.fromhex('02d1'),
                                   0x108: bytes.fromhex('0493'), 0x10A: encode_bl(0x10A, 0x626B4)})
        state = self.m.run_flow(rom, nodes, {0x100})['states'][0x10A]
        self.assertNotIn(16, state['stack'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
