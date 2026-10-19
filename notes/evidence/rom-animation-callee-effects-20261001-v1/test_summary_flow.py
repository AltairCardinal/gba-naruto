import copy
import struct
from pathlib import Path
import unittest
from analyze_batch import fixed_graph, derive
from flow import run_flow


def bl(at, target):
    delta = (target-at-4) & 0x7fffff
    return struct.pack('<HH',0xf000 | (delta >> 12),0xf800 | ((delta >> 1) & 2047))


class SummaryFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.source, _, _ = fixed_graph()
        cls.rows = derive(cls.base, cls.source)
        cls.summaries = {row['range'][0]: row['strict'] if row['strict']['return_identity_proven']
                         else row['conditional_frame'] for row in cls.rows}

    def fixture(self, target):
        raw = bytearray(self.base)
        pieces = {0x100: bytes.fromhex('0025'), 0x102: bl(0x102,target),
                  0x106: bytes.fromhex('0495'),0x108: bl(0x108,0x626b4)}
        for at,b in pieces.items():
            raw[at:at+len(b)] = b
        return bytes(raw), set(pieces) | self.source

    def rebound(self, raw, target):
        from callee_effects import analyze
        prior = self.summaries[target]
        nodes = {i['at'] for i in prior['source_instructions']}
        return {target: analyze(raw,target,nodes,conditional_frame=prior['conditional'])}

    def test_leaf_preservation_requires_real_summary(self):
        raw,nodes = self.fixture(0x6571c)
        plain = run_flow(raw,nodes,{0x100})['states'][0x108]
        self.assertNotIn(16,plain['stack'])
        state = run_flow(raw,nodes,{0x100},callees=self.rebound(raw,0x6571c))['states'][0x108]
        self.assertEqual(state['stack'][16],0)
        self.assertFalse(state['conditional_callee_preservation'])

    def test_saved_frame_summary_carries_explicit_condition(self):
        raw,nodes = self.fixture(0x66758)
        state = run_flow(raw,nodes,{0x100},callees=self.rebound(raw,0x66758))['states'][0x108]
        self.assertEqual(state['stack'][16],0)
        self.assertTrue(state['conditional_callee_preservation'])

    def test_forged_preserved_register_is_rejected(self):
        raw,nodes = self.fixture(0x8d580)
        summaries = self.rebound(raw,0x8d580)
        summaries[0x8d580]['preserved_registers'].append(9)
        with self.assertRaises(ValueError):
            run_flow(raw,nodes,{0x100},callees=summaries)

    def test_summary_cannot_preserve_caller_stack(self):
        raw,nodes = self.fixture(0x6571c)
        summaries = self.rebound(raw,0x6571c)
        summaries[0x6571c]['caller_stack_facts_preserved'] = True
        with self.assertRaises(ValueError):
            run_flow(raw,nodes,{0x100},callees=summaries)

    def test_summary_must_be_bound_to_current_rom_and_source(self):
        raw,nodes = self.fixture(0x6571c)
        with self.assertRaises(ValueError):
            run_flow(raw,nodes,{0x100},callees={0x6571c:self.summaries[0x6571c]})
        bound = self.rebound(raw,0x6571c)
        with self.assertRaises(ValueError):
            run_flow(raw,nodes-{0x6571e},{0x100},callees=bound)


if __name__ == '__main__':
    unittest.main(verbosity=2)
