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
        row=p.sort_pool([0x10001]*128,list(range(128)))
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

if __name__=='__main__':unittest.main()
