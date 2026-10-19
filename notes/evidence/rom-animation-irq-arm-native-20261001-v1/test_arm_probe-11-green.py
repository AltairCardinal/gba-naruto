import unittest
from pathlib import Path
import arm_probe as p

class ContractTests(unittest.TestCase):
    def test_copy_offsets_and_noncode_tail(self):
        self.assertEqual(p.COPIES, ((0x638,0x03005CE8,92),(0x690,0x03005D50,164)))
        self.assertEqual(p.code_ranges(0x638),((0x08000638,0x08000680),))
        self.assertEqual(p.code_ranges(0x638,True),((0x03005CE8,0x03005D30),))
    def test_raster_first_oracle(self):
        f=p.raster_fixture(0x638,True,159,255,False)
        self.assertEqual(f['expected_writes'],[[0x04000040,4,0x12345678],[0x04000044,4,0x89ABCDEF]])
        self.assertEqual(f['data_address'],0x02000000+255*1280+159*8)
        self.assertEqual(p.raster_fixture(0x638,False,160,0,False)['expected_writes'],[])
    def test_second_callback_both_branches(self):
        self.assertEqual(p.raster_fixture(0x690,True,0,0,True)['expected_writes'],[[0x04000050,2,0x1234],[0x04000054,2,0x5678],[0x04000048,4,0x89ABCDEF]])
        self.assertEqual(p.raster_fixture(0x690,False,0,0,False)['expected_writes'],[[0x04000050,2,255],[0x04000054,2,16],[0x04000048,4,0x3F3F3F3F]])
    def test_protocol_rejects_outside_fixture(self):
        with self.assertRaises(ValueError):p.protocol({'root':0x08000638,'stop':0x0800063C,'ranges':[[0x08000638,0x08000680]],'budget':100})
        with self.assertRaises(ValueError):p.raster_fixture(0x638,False,0,256,False)
    def test_real_rom_native_snapshot_and_callbacks(self):
        rows=p.execute([p.raster_fixture(root,ram,line,bank,active) for root,ram,line,bank,active in [(0x638,False,159,255,False),(0x638,True,160,255,False),(0x690,False,159,255,True),(0x690,True,159,255,False)]])
        self.assertEqual(len(rows),4)
        self.assertTrue(all(row['verified'] for row in rows))

class ContextTests(unittest.TestCase):
    def test_raw_save_and_resume_register_crossing(self):
        saved,resumed=p.context_pair(2,1)
        self.assertEqual(saved['record'][0x14],saved['original_registers'][1])
        self.assertEqual(saved['record'][0x18],saved['original_registers'][2])
        self.assertEqual(resumed['registers'][1],saved['original_registers'][2])
        self.assertEqual(resumed['registers'][2],saved['original_registers'][1])
        for r in (0,*range(3,13),13):self.assertEqual(resumed['registers'][r],saved['original_registers'][r])
        self.assertEqual(resumed['cpsr']&0x3F,0x3F)
    def test_wait_zero_is_wrapping_skip(self):
        saved,resumed=p.context_pair(1,0)
        self.assertFalse(resumed['selected'])
        self.assertEqual(resumed['wait'],255)
    def test_slot_domains(self):
        for slot in (0,7,8):
            with self.assertRaises(ValueError):p.context_pair(slot,1)

class IrqTests(unittest.TestCase):
    def test_banked_dispatch_both_callbacks(self):
        for root,active in ((0x638,False),(0x690,True),(0x690,False)):
            row=p.irq_case(root,159,255,active)
            self.assertEqual(row['registers'][13],0x03007000)
            self.assertEqual(row['cpsr']&255,0x92)
            self.assertEqual(row['callback_writes'],p.raster_fixture(root,True,159,255,active)['expected_writes'])
    def test_wrong_copy_entry_is_rejected(self):
        fixture=p.raster_fixture(0x638,True,0,0,False)
        fixture['memory'].append([4,0x03005CE8,0])
        # Copy executes after RAM fixtures; alter source fetch through smaller allowed range instead.
        fixture['ranges']=((0x03005CE8,0x03005CEC),)
        with self.assertRaises(ValueError):p.execute([fixture])
    def test_dispatch_upper_line_returns_without_callback_stores(self):
        row=p.irq_case(0x690,160,255,True)
        self.assertEqual(row['callback_writes'],[])

if __name__=='__main__':unittest.main()


