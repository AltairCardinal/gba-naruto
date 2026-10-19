import copy
import unittest
from analyze_batch import fixed_graph
from callee_effects import analyze
from closure import noncall_closure


class DispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom,cls.source,_,_=fixed_graph()

    def binder(self):
        import dispatch_contracts
        return dispatch_contracts

    def test_fixed_contract_has_all_ten_slots(self):
        rows=self.binder().bind(self.rom,0x6d964,self.source,{0x6dc72})
        self.assertEqual(len(rows[0x6dc72]['targets']),10)
        self.assertEqual(rows[0x6dc72]['allowed_indices'],list(range(10)))

    def test_forged_target_vector_rejected(self):
        rows=self.binder().bind(self.rom,0x6d964,self.source,{0x6dc72})
        rows[0x6dc72]['targets'][0]['file_offset']+=2
        with self.assertRaises(ValueError):self.binder().validate(self.rom,0x6d964,self.source,rows)

    def test_entry_at_terminal_cannot_inherit_guard(self):
        with self.assertRaises(ValueError):self.binder().bind(self.rom,0x6dc72,self.source,{0x6dc72})

    def test_guard_rom_mutation_rejected(self):
        raw=bytearray(self.rom);raw[0x6dc64]^=1
        with self.assertRaises(ValueError):self.binder().bind(bytes(raw),0x6d964,self.source,{0x6dc72})

    def test_real_closed_callee_requires_dispatch_edges(self):
        rows=self.binder().bind(self.rom,0x6d964,self.source,{0x6dc72})
        graph=noncall_closure(self.rom,0x6d964,self.source,dispatches=rows)
        nodes=set(graph['nodes'])
        ordinary=analyze(self.rom,0x6d964,nodes,conditional_frame=True)
        self.assertFalse(ordinary['return_identity_proven'])
        bound=analyze(self.rom,0x6d964,nodes,conditional_frame=True,dispatches=rows)
        self.assertTrue(bound['return_identity_proven'])
        self.assertIn(5,bound['preserved_registers'])
        self.assertTrue(all(t['file_offset'] in nodes for t in rows[0x6dc72]['targets']))


    def test_independent_replay_cached_only_with_pinned_inputs(self):
        from unittest import mock
        module=self.binder()
        module._cached_dispatch=None
        original=module._resolve_thumb_indexed_dispatches_independently
        with mock.patch.object(module,'_resolve_thumb_indexed_dispatches_independently',wraps=original) as replay:
            module.bind(self.rom,0x6d964,self.source,{0x6dc72})
            module.bind(self.rom,0x6d964,self.source,{0x6dc72})
            self.assertEqual(replay.call_count,1)

    def test_cached_replay_still_rejects_live_input_drift(self):
        from unittest import mock
        from pathlib import Path
        module=self.binder();module.bind(self.rom,0x6d964,self.source,{0x6dc72})
        original=Path.read_bytes
        def altered(path):
            raw=original(path)
            if str(path)=='tools/verify_rom_cfg_inventory_v3.py':return raw+b' '
            return raw
        with mock.patch.object(Path,'read_bytes',altered):
            with self.assertRaises(ValueError):module.bind(self.rom,0x6d964,self.source,{0x6dc72})

if __name__ == '__main__':unittest.main(verbosity=2)
