import importlib.util
import unittest
from pathlib import Path

HERE=Path(__file__).parent


class CoupledWriterTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('coupled_probe',HERE/'coupled_probe.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.rom=Path('rom/base.gba').read_bytes()

    def test_boot_dma_configuration_and_zero_fill_ranges(self):
        report=self.m.boot_dma(self.rom)
        self.assertEqual([(r['destination'],r['count_words'],r['range'],r['source_word']) for r in report['transfers']],[(0x02000000,65536,[0x02000000,0x02040000],0),(0x03000000,7872,[0x03000000,0x03007B00],0)])
        self.assertTrue(report['counter_saved_and_pool_inside_iwram_zero_range'])
        self.assertFalse(report['natural_runtime_proven'])
        self.assertEqual(report['transfers'][0]['masked_control'],0x8500)

    def test_boot_nonzero_source_and_unsupported_dma_mode_are_rejected(self):
        changed=bytearray(self.rom);changed[0x60FB8:0x60FBA]=bytes.fromhex('0125')
        with self.assertRaisesRegex(ValueError,'zero source'):
            self.m.boot_dma(bytes(changed))
        changed=bytearray(self.rom);changed[0x61034:0x61038]=(0x87001EC0).to_bytes(4,'little')
        with self.assertRaisesRegex(ValueError,'DMA mode'):
            self.m.boot_dma(bytes(changed))

    def test_vector_register_all_u8_slots_and_high_byte_truncation(self):
        for slot in range(256):
            report=self.m.vector(self.rom,slot|0x12340000,value=0x12345678)
            writes=[w for w in report['writes'] if 0x03000000<=w['address']<0x03000400]
            self.assertEqual(writes,[{'at':0x624F8,'address':0x03000000+4*slot,'size':4,'value':0x12345678}])
            self.assertEqual(report['counter'],0x56 if slot==29 else 0xA5)
            self.assertEqual(report['registers'][13],0x03007000)

    def test_vector_default_restoration_can_alias_counter_if_slot_is_29(self):
        for slot in range(256):
            report=self.m.vector(self.rom,slot,remove=True)
            writes=[w for w in report['writes'] if 0x03000000<=w['address']<0x03000400]
            self.assertEqual(writes,[{'at':0x6251C,'address':0x03000000+4*slot,'size':4,'value':0x08061535}])
            self.assertEqual(report['counter'],0x15 if slot==29 else 0xA5)
        for slot in (0,1,2):
            report=self.m.vector(self.rom,slot,remove=True,default_vector=True)
            self.assertEqual(report['counter'],0xA5)
            self.assertEqual(report['irq_enable'],0xFFFD)
            self.assertEqual(report['display_status'],0xFFEF)

    def test_saved_byte_initializer_clears_saved_without_changing_counter(self):
        report=self.m.clear_saved(self.rom)
        self.assertEqual(report['saved'],0)
        self.assertEqual(report['counter'],0xA5)
        self.assertEqual(len(report['writes']),5)


if __name__=='__main__':unittest.main(verbosity=2)
