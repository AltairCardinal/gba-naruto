import unittest
import object_native as p

class NativeLifecycleTests(unittest.TestCase):
    def test_allocator_preserves_stale_context(self):
        row=p.allocate(free=127,context=0xA1234567)
        self.assertEqual(row['handle'],p.POOL+60*127)
        self.assertEqual(row['fields'][0x2C],0xA1234567)
        self.assertEqual([row['fields'][off] for off in (0x14,0x16,0x18)],[0,0,0])
    def test_full_allocator_returns_null(self):
        self.assertEqual(p.allocate(free=None)['handle'],0)
    def test_lookup_missing_is_index_ten(self):
        for n in (0,9,None):
            row=p.lookup([n if n is not None else 255]*10,42) if n is None else p.lookup([42 if i==n else 255 for i in range(10)],42)
            self.assertEqual(row['index'],10 if n is None else n)
    def test_sort_full_return_and_mode_keys(self):
        row=p.sort_pool([0x40001]*128,list(range(128)))
        self.assertEqual(row['order'],list(reversed(range(128))))
        self.assertEqual(row['registers'][13],p.SP)
    def test_callback_initialization_uses_real_bios(self):
        row=p.callback(context=0,manager_slot=3,pending=0)
        self.assertEqual(row['own_fields'][0x2C],16)
        self.assertEqual(row['own_fields'][0x2E],3)
        self.assertEqual(row['own_fields'][0x30],1)
        self.assertIn(0x0809C0E0,row['visited'])
    def test_stale_context_skips_bios_init(self):
        row=p.callback(context=7,manager_slot=0,pending=0)
        self.assertNotIn(0x0809C0E0,row['visited'])
        self.assertEqual(row['own_fields'][0x2C],7)
    def test_selection_reads_before_freeze(self):
        row=p.select_and_advance(group=0,slot=0,flags=8,count=1,timer=9)
        self.assertEqual(row['timer'],9)
        self.assertTrue(row['lookup_before_freeze'])
    def test_timer_wrap_and_negative_duration(self):
        row=p.select_and_advance(group=0,slot=0,flags=0,count=1,timer=65535)
        self.assertEqual(row['timer'],0)
    def test_native_source_budget_rejects_execution_escape(self):
        with self.assertRaises(ValueError):p.select_and_advance(group=65535,slot=65535,flags=0,count=1,timer=0)

class NativeJointTests(unittest.TestCase):
    def test_persistent_allocate_dispatch_release_and_reuse(self):
        rows=p.lifecycle_chain(context=0)
        self.assertEqual(len(rows),5)
        self.assertEqual(rows[0]['registers'][0],p.POOL+127*60)
        self.assertIn(0x0808AA50,rows[1]['visited'])
        self.assertEqual(p.values(rows[1])[(p.POOL+127*60+0x2C,2)],16)
        self.assertEqual(p.values(rows[3])[(0x03005BB8,1)],127)
        self.assertEqual(p.values(rows[3])[(p.POOL+127*60,4)],0x20)
        self.assertEqual(rows[4]['registers'][0],p.POOL+127*60)
        self.assertEqual(p.values(rows[4])[(p.POOL+127*60+0x2C,2)],16)
    def test_callback_tail_preserves_critical_indices(self):
        row=p.callback_tail(meta2=2,meta3=3,meta12=1)
        self.assertEqual(row['tile10'],[0,0x384+12,0x398+8])
        self.assertEqual(row['critical_unchanged'],True)
    def test_null_tail_handle_remains_invalid(self):
        with self.assertRaises(ValueError):p.callback_tail(meta2=1,meta3=1,meta12=1,handles=[0,0,0])
    def test_descriptor_sentinel_suffix_is_not_read(self):
        rows=p.descriptor_heads(sequence=0x458550,descriptor_table=0x45854C)
        self.assertEqual(rows['heads'],[0x458520,0x458534,0x458548])
        self.assertEqual(rows['sentinel'],0x458548)
        self.assertNotIn(0x45854A,rows['read_bytes'])
    def test_sequence_sentinel_is_rejected_for_descriptor_binding(self):
        with self.assertRaises(ValueError):p.descriptor_heads(sequence=0x458554,descriptor_table=0x45854C)
    def test_lookup_certificate_rejects_changed_bound(self):
        cert=p.lookup_certificate(p.ROM)
        self.assertEqual(cert['return_indices'],list(range(11)))
        broken=bytearray(p.ROM);broken[0x655D2:0x655D4]=bytes.fromhex('0a2a')
        with self.assertRaises(ValueError):p.lookup_certificate(bytes(broken))

if __name__=='__main__':unittest.main()

