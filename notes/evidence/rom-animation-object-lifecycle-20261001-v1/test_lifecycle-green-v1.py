import importlib.util
import struct
import unittest
from pathlib import Path

HERE = Path(__file__).parent
POOL = 0x03003BB8
OTHER = 0x03003078
SP = 0x03007000
BASE = 0x08000000


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('lifecycle_probe', HERE / 'lifecycle_probe.py')
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.rom = Path('rom/base.gba').read_bytes()

    def test_initializer_clears_exactly_144_flags_words_and_preserves_poison(self):
        before = self.m.state()
        after = self.m.initialize(self.rom, before)
        expected = dict(before)
        addresses = [POOL + 60 * n for n in range(128)] + [OTHER + 180 * n for n in range(16)]
        for address in addresses:
            for byte in range(4): expected[address + byte] = 0
        for address in before:
            if not SP - 64 <= address < SP: self.assertEqual(after['memory'][address], expected[address])
        pool_writes = [w for w in after['writes'] if not SP - 64 <= w['address'] < SP]
        self.assertEqual([(w['address'], w['size'], w['value']) for w in pool_writes], [(a, 4, 0) for a in addresses])
        self.assertEqual(after['registers'][4:12], self.m.registers()[4:12])
        self.assertEqual(after['registers'][13], SP)

    def test_direct_allocator_selects_each_of_128_highest_free_slots(self):
        for free in range(128):
            memory = self.m.state()
            for n in range(128): self.m.put(memory, POOL + 60*n, 4, 3)
            self.m.put(memory, POOL + 60*free, 4, 0xA5000004)
            result = self.m.allocate(self.rom, memory)
            self.assertEqual(result['registers'][0], POOL + 60*free)
            self.assertEqual(result['registers'][4:12], self.m.registers()[4:12])
            self.assertEqual(result['registers'][13], SP)
            written = {w['address'] for w in result['writes'] if POOL <= w['address'] < POOL + 128*60}
            self.assertTrue(written and all(POOL + 60*free <= a < POOL + 60*(free+1) for a in written))

    def test_full_pool_returns_null_without_pool_write_or_129th_read(self):
        memory = self.m.state()
        for n in range(128): self.m.put(memory, POOL + 60*n, 4, 3)
        for alternate in (False, True):
            result = self.m.allocate(self.rom, memory, alternate=alternate)
            self.assertEqual(result['registers'][0], 0)
            self.assertFalse(any(POOL <= w['address'] < POOL + 128*60 for w in result['writes']))
            self.assertEqual({r['address'] for r in result['reads'] if POOL <= r['address'] < POOL + 128*60}, {POOL + 60*n for n in range(128)})

    def test_allocator_overwrites_only_documented_fields_and_truncates_arguments(self):
        memory = self.m.state()
        for n in range(128): self.m.put(memory, POOL + 60*n, 4, 3)
        address = POOL + 127*60
        self.m.put(memory, address, 4, 0)
        result = self.m.allocate(self.rom, memory)
        expected = {0:(4,0x10203041),4:(2,0x3456),6:(2,0x5678),8:(2,0),10:(2,0),12:(2,256),14:(2,256),16:(2,0x789A),18:(1,0xBC),19:(1,0),20:(2,0x1234),22:(2,0),24:(2,0),28:(4,0x08458474),32:(4,0x0845848C),40:(4,0x0808AA51)}
        changed = set()
        for off,(size,value) in expected.items():
            self.assertEqual(self.m.get(result['memory'],address+off,size),value)
            changed.update(range(address+off,address+off+size))
        for a in range(POOL,POOL+128*60):
            if a not in changed: self.assertEqual(result['memory'][a],memory[a])

    def test_alternate_allocator_non_bios_path_binds_table_entry(self):
        memory = self.m.state()
        for n in range(128): self.m.put(memory, POOL + 60*n, 4, 3)
        self.m.put(memory, POOL+127*60, 4, 0)
        result = self.m.allocate(self.rom, memory, alternate=True)
        address = POOL+127*60
        self.assertEqual(result['registers'][0],address)
        self.assertEqual(self.m.get(result['memory'],address+28,4),0x08458474)
        self.assertEqual(self.m.get(result['memory'],address+32,4),0x0845848C)
        self.assertEqual(self.m.get(result['memory'],address+40,4),0x0808AA51)
        self.assertEqual(result['registers'][4:12],self.m.registers()[4:12])

    def test_alternate_bios_path_stops_at_real_call_instead_of_stub(self):
        memory = self.m.state()
        for n in range(128): self.m.put(memory,POOL+60*n,4,3)
        self.m.put(memory,POOL+127*60,4,0)
        with self.assertRaisesRegex(ValueError,'unexpected callee.*9c0dc'):
            self.m.allocate(self.rom,memory,alternate=True,flags=0x400000)

    def test_disable_reserves_slot_until_real_active_filter_clears_bit1(self):
        memory = self.m.state()
        for n in range(128): self.m.put(memory,POOL+60*n,4,3)
        address = POOL+127*60
        self.m.put(memory,address,4,0xA0000001)
        disabled = self.m.disable(self.rom,memory,address)
        self.assertEqual(self.m.get(disabled['memory'],address,4),0xA0000002)
        reserved = self.m.allocate(self.rom,disabled['memory'])
        self.assertEqual(reserved['registers'][0],0)
        filtered = self.m.filter_scan(self.rom,disabled['memory'])
        self.assertEqual(self.m.get(filtered['memory'],address,4),0xA0000000)
        self.assertEqual(self.m.get(filtered['memory'],0x03005BB8,1),127)
        allocated = self.m.allocate(self.rom,filtered['memory'])
        self.assertEqual(allocated['registers'][0],address)

    def test_filter_scans_128_slots_and_rebuilds_exact_active_list(self):
        memory = self.m.state()
        flags = [0xF0000000 | (n%4) for n in range(128)]
        for n,value in enumerate(flags): self.m.put(memory,POOL+60*n,4,value)
        result = self.m.filter_scan(self.rom,memory)
        active = [POOL+60*n for n,value in enumerate(flags) if value&1]
        self.assertEqual(self.m.get(result['memory'],0x03005BB8,1),len(active))
        self.assertEqual([self.m.get(result['memory'],0x030059B8+4*n,4) for n in range(len(active))],active)
        for n,value in enumerate(flags): self.assertEqual(self.m.get(result['memory'],POOL+60*n,4),value if value&1 else value&0xFFFFFFFD)
        for n in range(128):
            for byte in range(4,60): self.assertEqual(result['memory'][POOL+60*n+byte],memory[POOL+60*n+byte])
        self.assertEqual(result['stop'],0x62816)
        self.assertFalse(result['ordinary_return'])

    def test_restore_counter_preserves_all_256_byte_values_when_saved_nonzero(self):
        for saved in range(256):
            result = self.m.restore_counter(self.rom,guard=0x303,saved=saved,counter=173,argument=0)
            self.assertEqual(self.m.get(result['memory'],0x03000075,1),saved or 173)
            self.assertEqual(self.m.get(result['memory'],0x03005E2D,1),0)
            self.assertEqual(result['registers'][0],1)

    def test_restore_guard_and_argument_fallthrough_keep_counter_and_saved(self):
        for argument,count in ((0,59),(1,58),(1,59),(255,255)):
            result = self.m.restore_counter(self.rom,guard=0,saved=254,counter=173,argument=argument,wait=count)
            self.assertEqual(self.m.get(result['memory'],0x03000075,1),173)
            self.assertEqual(self.m.get(result['memory'],0x03005E2D,1),254)
            updated=(count+bool(argument))&255
            self.assertEqual(result['registers'][0],2 if updated>59 else 0)
            self.assertEqual(self.m.get(result['memory'],0x03005E4A,1),updated)

    def test_source_hole_budget_and_unexpected_opcode_fail_closed(self):
        from bounded_thumb import execute
        with self.assertRaisesRegex(ValueError,'source'):
            execute(self.rom,0x62560,set(),self.m.registers(),self.m.state(),set(),budget=20000)
        with self.assertRaisesRegex(ValueError,'budget'):
            execute(self.rom,0x62560,{0x62560},self.m.registers(),self.m.state(),set(),budget=1)
        changed=bytearray(self.rom);changed[0x62560:0x62562]=bytes.fromhex('00df')
        with self.assertRaisesRegex(ValueError,'unsupported'):
            execute(bytes(changed),0x62560,{0x62560},self.m.registers(),self.m.state(),set())


if __name__ == '__main__': unittest.main(verbosity=2)
