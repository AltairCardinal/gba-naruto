import importlib.util
from pathlib import Path
import struct
import unittest


class ClosureTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('closure',Path(__file__).with_name('closure.py'))
        self.m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.base=Path('rom/base.gba').read_bytes()

    def test_noncall_closure_follows_fallthrough_but_not_child(self):
        raw=bytearray(self.base)
        d=(0x200-0x104)&0x7fffff
        raw[0x100:0x104]=struct.pack('<HH',0xf000|(d>>12),0xf800|((d>>1)&2047))
        raw[0x104:0x106]=bytes.fromhex('7047')
        result=self.m.noncall_closure(bytes(raw),0x100,{0x100,0x104,0x200})
        self.assertEqual(result['nodes'],[0x100,0x104])
        self.assertEqual(result['child_targets'],[0x200])

    def test_missing_root_does_not_invent_source_membership(self):
        result=self.m.noncall_closure(self.base,0x100,set())
        self.assertEqual(result['nodes'],[])
        self.assertEqual(result['frontiers'][0]['kind'],'missing_source_root')

    def test_loop_is_finite_without_inventing_exit(self):
        raw=bytearray(self.base);raw[0x100:0x102]=bytes.fromhex('fee7')
        result=self.m.noncall_closure(bytes(raw),0x100,{0x100})
        self.assertEqual(result['nodes'],[0x100])
        self.assertEqual(result['return_nodes'],[])

    def test_graph_budget_failure_is_explicit(self):
        raw=bytearray(self.base);raw[0x100:0x104]=bytes.fromhex('01207047')
        with self.assertRaises(ValueError):
            self.m.noncall_closure(bytes(raw),0x100,{0x100,0x102},budget=1)

    def test_shared_targets_are_analyzed_once_until_fixed_frontier(self):
        counts={}
        def inspect(registry):
            if 1 not in registry:return [{'kind':'unproved_callee_register_effect','target':1}]*2
            if 2 not in registry:return [{'kind':'unproved_callee_register_effect','target':2}]
            return [{'kind':'constant_producer','value':0}]
        def prove(target):
            counts[target]=counts.get(target,0)+1
            return {'accepted':True,'summary':target}
        result=self.m.discover(inspect,prove,{})
        self.assertEqual(counts,{1:1,2:1})
        self.assertEqual(result['registry'],{1:1,2:2})
        self.assertEqual(result['round_count'],3)

    def test_rejected_target_is_cached_and_not_promoted(self):
        counts=[]
        def prove(target):counts.append(target);return {'accepted':False,'reason':'svc'}
        result=self.m.discover(lambda _: [{'kind':'unproved_callee_register_effect','target':1}],prove,{})
        self.assertEqual(counts,[1]);self.assertEqual(result['registry'],{})

    def test_discovery_budget_never_returns_partial_success(self):
        with self.assertRaises(ValueError):
            self.m.discover(lambda r:[{'kind':'unproved_callee_register_effect','target':len(r)+1}],
                            lambda t:{'accepted':True,'summary':t},{},max_targets=1)


    def test_bx_pc_is_mode_boundary_and_mov_pc_lr_is_return(self):
        raw=bytearray(self.base);raw[0x100:0x102]=bytes.fromhex('7847')
        r=self.m.noncall_closure(bytes(raw),0x100,{0x100})
        self.assertEqual(r['frontiers'][0]['kind'],'mode_switch')
        raw[0x100:0x102]=bytes.fromhex('f746')
        r=self.m.noncall_closure(bytes(raw),0x100,{0x100})
        self.assertEqual(r['return_nodes'],[0x100])

if __name__ == '__main__':unittest.main(verbosity=2)
