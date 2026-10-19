import struct
import unittest
from pathlib import Path
from analyze_batch import fixed_graph, derive
from callee_effects import analyze
from frontier import dependencies


def bl(at,target):
    d=(target-at-4)&0x7fffff
    return struct.pack('<HH',0xf000|(d>>12),0xf800|((d>>1)&2047))


class SummaryFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base,cls.offsets,_,_=fixed_graph()
        cls.rows={r['range'][0]:r for r in derive(cls.base,cls.offsets)}

    def case(self,target,register=5):
        raw=bytearray(self.base)
        pieces={0x100:struct.pack('<H',0x2000|(register<<8)),0x102:bl(0x102,target),
                0x106:struct.pack('<H',0x9000|(register<<8)|4),0x108:bl(0x108,0x626b4)}
        for at,b in pieces.items(): raw[at:at+len(b)]=b
        rom=bytes(raw)
        row=self.rows[target]
        prior=row['strict'] if row['strict']['return_identity_proven'] else row['conditional_frame']
        nodes={i['at'] for i in prior['source_instructions']}
        summary=analyze(rom,target,nodes,conditional_frame=prior['conditional'])
        return rom,set(pieces)|nodes,{target:summary}

    def test_verified_leaf_boundary_reaches_constant_producer(self):
        rom,nodes,summaries=self.case(0x6571c)
        r=dependencies(rom,nodes,{0x100},0x108,16,callees=summaries)
        self.assertEqual(r['frontiers'],[{'kind':'constant_producer','at':0x100,'register':5,'value':0}])

    def test_unsaved_register_remains_explicit_callee_boundary(self):
        rom,nodes,summaries=self.case(0x8d580,register=2)
        r=dependencies(rom,nodes,{0x100},0x108,16,callees=summaries)
        self.assertTrue(any(f['kind']=='unproved_callee_register_effect' for f in r['frontiers']))

    def test_forged_frontier_summary_is_rejected(self):
        rom,nodes,summaries=self.case(0x6571c)
        summaries[0x6571c]['caller_stack_facts_preserved']=True
        with self.assertRaises(ValueError):
            dependencies(rom,nodes,{0x100},0x108,16,callees=summaries)


if __name__ == '__main__':
    unittest.main(verbosity=2)
