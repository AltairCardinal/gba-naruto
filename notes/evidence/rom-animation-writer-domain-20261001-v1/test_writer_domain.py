import importlib.util
import struct
import unittest
from pathlib import Path

HERE=Path(__file__).parent


class WriterDomainTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('writer_domain',HERE/'writer_domain.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def event(self,opcode,registers):
        return self.m.stores(struct.pack('<H',opcode),{0},{0:{'registers':registers}})[0]

    def test_raw_immediate_and_register_address_expressions(self):
        direct=self.event(0x70C8,{0:0x1234,1:0x03000072})
        self.assertEqual((direct['effective_address'],direct['aligned_address'],direct['width'],direct['value']),(0x03000075,0x03000075,1,0x34))
        indexed=self.event(0x5088,{0:0x12345678,1:0x03000070,2:5})
        self.assertEqual((indexed['effective_address'],indexed['aligned_address']),(0x03000075,0x03000074))
        self.assertIn('counter_75',indexed['overlaps'])

    def test_word_halfword_alignment_and_iwram_mirrors(self):
        for opcode,width in [(0x6008,4),(0x8008,2),(0x7008,1)]:
            for address in (0x03000075,0x03008075,0x03FF0075):
                row=self.event(opcode,{0:0xFFFFFFFF,1:address})
                self.assertIn('counter_75',row['overlaps'])
                self.assertEqual(row['iwram_bytes'],list(range(0x75&~(width-1),(0x75&~(width-1))+width)))
                self.assertEqual(row['width'],width)

    def test_all_128_pool_records_and_partial_critical_fields(self):
        for slot in range(128):
            row=self.event(0x7008,{0:0,1:0x03003BB8+60*slot+0x15})
            self.assertEqual(row['pool_fields'],[{'slot':slot,'field':'group_slot_timer','range':[0x14,0x1A]}])
        row=self.event(0x7008,{0:0,1:0x03003BB8+0x2C})
        self.assertEqual(row['pool_fields'],[])
        self.assertFalse(row['may_alias_targets'])

    def test_multiple_stores_keep_every_register_and_unknown_push_alias(self):
        rom=struct.pack('<2H',0xC10D,0xB510)
        states={0:{'registers':{0:11,1:0x03005E28,2:22,3:33}},2:{'registers':{4:44,14:55}}}
        rows=self.m.stores(rom,{0,2},states)
        self.assertEqual([(r['effective_address'],r['value']) for r in rows[:3]],[(0x03005E28,11),(0x03005E2C,22),(0x03005E30,33)])
        self.assertIn('saved_5e2d',rows[1]['overlaps'])
        self.assertEqual([r['register'] for r in rows[3:]],[4,14])
        self.assertTrue(all(r['may_alias_targets'] and r['address_unknown'] for r in rows[3:]))

    def test_unknown_and_not_reached_addresses_remain_possible_writers(self):
        unknown=self.event(0x7008,{0:0})
        self.assertTrue(unknown['may_alias_targets'])
        self.assertTrue(unknown['address_unknown'])
        row=self.m.stores(bytes.fromhex('0870'),{0},{})[0]
        self.assertTrue(row['may_alias_targets'])
        self.assertFalse(row['reachable_in_model'])
        self.assertFalse(row['global_writer_exhaustiveness_proven'])

    def test_dma_register_write_keeps_indirect_memory_effect_obligation(self):
        row=self.event(0x6008,{0:0x03000075,1:0x040000D8})
        self.assertFalse(row['may_alias_targets'])
        self.assertTrue(row['dma_control_or_address_write'])
        self.assertFalse(row['global_writer_exhaustiveness_proven'])

    def test_roots_include_calls_missing_predecessors_and_all_disconnected_cycles(self):
        decoded={0:{'successors':[{'kind':'fallthrough','file_offset':2}]},
                 2:{'successors':[{'kind':'call_target','file_offset':10},{'kind':'fallthrough','file_offset':4}]},
                 4:{'successors':[{'kind':'branch_target','file_offset':4}]},
                 10:{'successors':[]},20:{'successors':[{'kind':'branch_target','file_offset':20}]},
                 30:{'successors':[{'kind':'fallthrough','file_offset':99}]}}
        result=self.m.root_set(decoded,{0})
        self.assertEqual(result['roots'],[0,10,20,30])
        self.assertEqual(result['disconnected_unproven_nodes'],[20])
        with self.assertRaisesRegex(ValueError,'declared root'):
            self.m.root_set(decoded,{99})

    def test_all_raw_single_store_classes_keep_fixed_instruction_denominator(self):
        opcodes=[0x6008,0x7008,0x8008,0x5088,0x5288,0x5488,0x9000]
        rom=struct.pack('<7H',*opcodes)
        rows=self.m.stores(rom,set(range(0,14,2)),{})
        self.assertEqual([r['at'] for r in rows],list(range(0,14,2)))
        self.assertEqual([r['width'] for r in rows],[4,1,2,4,2,1,4])
        self.assertTrue(all(r['may_alias_targets'] for r in rows))

    def test_claim_suffix_is_covered_by_existing_complete_bl_not_new_root(self):
        rom=struct.pack('<3H',0xF000,0xF800,0x7008)
        result=self.m.cover_range(rom,2,6,{0})
        self.assertEqual(result['new_nodes'],[4])
        self.assertFalse(result['range_start_is_instruction'])
        self.assertEqual(result['cross_boundary_existing_nodes'],[0])

    def test_unsupported_uncovered_claim_is_explicit_gap_not_guessed_prefix(self):
        rom=struct.pack('<3H',0xF000,0xF800,0x7008)
        with self.assertRaisesRegex(ValueError,'partition'):
            self.m.cover_range(rom,2,6,set())
        with self.assertRaisesRegex(ValueError,'range'):
            self.m.cover_range(rom,0,7,{0})

    def test_partition_hole_empty_multiple_and_rom_overflow_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'partition'):
            self.m.stores(bytes.fromhex('00f000f8'),{0,2},{})
        with self.assertRaisesRegex(ValueError,'empty'):
            self.m.stores(bytes.fromhex('00c0'),{0},{})
        with self.assertRaisesRegex(ValueError,'bounds'):
            self.m.stores(b'\0',{0},{})


if __name__=='__main__':unittest.main(verbosity=2)
