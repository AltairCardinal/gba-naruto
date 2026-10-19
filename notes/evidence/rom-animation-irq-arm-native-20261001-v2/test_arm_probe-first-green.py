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

if __name__=='__main__':unittest.main()
