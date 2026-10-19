import unittest
import full_renderer as p

class FullRendererTests(unittest.TestCase):
    def test_actual_callback_sort_body_and_full_return(self):
        row=p.frame(sequence_table=0x458558,descriptor_table=0x45854C,group=0,flags=0x20,count=1)
        self.assertEqual(row['registers'][13],p.native.SP)
        for pc in (0x62924,0x8AA50,0x627B0,0x62A16,0x631F6,0x63336):
            self.assertIn(p.native.BASE+pc,row['visited'])
        self.assertEqual(row['slot'],0)
        self.assertEqual(row['timer'],0)
    def test_loop_mode_reads_sequence_sentinel_duration(self):
        row=p.frame(sequence_table=0x458558,descriptor_table=0x45854C,group=0,flags=0x20,count=2)
        self.assertIn([0x458556,2],row['sequence_reads'])
        self.assertEqual(row['slot'],0)
        self.assertEqual(row['timer'],1)
    def test_preflight_rejects_sequence_sentinel_slot(self):
        with self.assertRaises(ValueError):
            p.frame(sequence_table=0x458558,descriptor_table=0x45854C,group=0,flags=0x20,count=1,slot=1)

if __name__=='__main__':unittest.main()
