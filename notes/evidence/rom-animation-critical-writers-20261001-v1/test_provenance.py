import struct,unittest
from provenance import audit
from callee_effects import analyze


def bl(at,target):
    d=(target-at-4)&0x7fffff
    return struct.pack('<HH',0xf000|(d>>12),0xf800|((d>>1)&2047))


def fixture(parts):
    raw=bytearray(0x400)
    for at,b in parts.items():raw[at:at+len(b)]=b
    return bytes(raw),set(parts)


class ProvenanceTests(unittest.TestCase):
    def test_derived_address_uses_total_offset_not_store_displacement(self):
        rom,n=fixture({0x100:bytes.fromhex('051c'),0x102:bytes.fromhex('2c35'),0x104:bytes.fromhex('6980'),0x106:bytes.fromhex('7047')})
        r=audit(rom,0x100,n,{0:('object',0)})
        self.assertEqual(r['stores'][0]['address'],['object',0x2e])
        self.assertFalse(r['stores'][0]['critical_field_overlap'])

    def test_retargeted_register_must_not_remain_original_object(self):
        rom,n=fixture({0x100:bytes.fromhex('051c'),0x102:bytes.fromhex('1025'),0x104:bytes.fromhex('a982'),0x106:bytes.fromhex('7047')})
        r=audit(rom,0x100,n,{0:('object',0)})
        self.assertEqual(r['stores'][0]['address'],0x24)
        self.assertFalse(r['stores'][0]['critical_field_overlap'])

    def test_branch_join_loses_disagreeing_object_identity(self):
        rom,n=fixture({0x100:bytes.fromhex('0028'),0x102:bytes.fromhex('01d0'),0x104:bytes.fromhex('011c'),0x106:bytes.fromhex('00e0'),0x108:bytes.fromhex('0021'),0x10a:bytes.fromhex('0883'),0x10c:bytes.fromhex('7047')})
        r=audit(rom,0x100,n,{0:('object',0)})
        self.assertIsNone(r['stores'][0]['address'])
        self.assertTrue(r['stores'][0]['may_alias_pool'])

    def test_opaque_child_destroys_pointer_and_stack_facts(self):
        rom,n=fixture({0x100:bytes.fromhex('051c'),0x102:bytes.fromhex('0095'),0x104:bl(0x104,0x200),0x108:bytes.fromhex('a982'),0x10a:bytes.fromhex('009d'),0x10c:bytes.fromhex('a982'),0x10e:bytes.fromhex('7047')})
        r=audit(rom,0x100,n,{0:('object',0)})
        self.assertTrue(all(s['address'] is None for s in r['stores'][1:]))

    def test_bound_child_preserves_gpr_but_not_caller_memory(self):
        rom,n=fixture({0x100:bytes.fromhex('051c'),0x102:bytes.fromhex('0095'),0x104:bl(0x104,0x200),0x108:bytes.fromhex('a982'),0x10a:bytes.fromhex('009d'),0x10c:bytes.fromhex('a982'),0x10e:bytes.fromhex('7047'),0x200:bytes.fromhex('0120'),0x202:bytes.fromhex('7047')})
        c=analyze(rom,0x200,{0x200,0x202})
        r=audit(rom,0x100,n,{0:('object',0)},callees={0x200:c})
        self.assertEqual(r['stores'][1]['address'],['object',0x14])
        self.assertTrue(r['stores'][1]['critical_field_overlap'])
        self.assertIsNone(r['stores'][2]['address'])
        self.assertFalse(r['caller_memory_preserved'])

    def test_literal_read_is_bound_to_rom_address(self):
        rom,n=fixture({0x100:bytes.fromhex('0149'),0x102:bytes.fromhex('8182'),0x104:bytes.fromhex('7047')})
        raw=bytearray(rom);raw[0x108:0x10c]=struct.pack('<I',0x03000075)
        r=audit(bytes(raw),0x100,n,{0:('object',0)})
        self.assertEqual(r['reads'][0]['address'],0x08000108)
        self.assertFalse(r['reads'][0]['may_alias_pool'])

    def test_load_does_not_guess_pointee_as_original_object(self):
        rom,n=fixture({0x100:bytes.fromhex('0168'),0x102:bytes.fromhex('8a82'),0x104:bytes.fromhex('7047')})
        r=audit(rom,0x100,n,{0:('object',0)})
        self.assertIsNone(r['stores'][0]['address'])
        self.assertTrue(r['stores'][0]['may_alias_pool'])

    def test_partial_overlap_is_critical_even_without_equal_field_start(self):
        rom,n=fixture({0x100:bytes.fromhex('1230'),0x102:bytes.fromhex('0160'),0x104:bytes.fromhex('7047')})
        r=audit(rom,0x100,n,{0:('object',0)})
        self.assertEqual(r['stores'][0]['address'],['object',0x12])
        self.assertTrue(r['stores'][0]['critical_field_overlap'])

    def test_missing_raw_partition_and_budget_fail_closed(self):
        rom,n=fixture({0x100:bytes.fromhex('011c'),0x102:bytes.fromhex('0883'),0x104:bytes.fromhex('7047')})
        with self.assertRaises(ValueError):audit(rom,0x100,n-{0x102},{0:('object',0)})
        with self.assertRaises(ValueError):audit(rom,0x100,n,{0:('object',0)},budget=1)


if __name__=='__main__':unittest.main(verbosity=2)
