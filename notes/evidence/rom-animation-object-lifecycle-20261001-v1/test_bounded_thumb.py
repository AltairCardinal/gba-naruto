"""Independent arithmetic predicates and memory/control boundary oracles."""
import struct
import unittest
from bounded_thumb import execute


class BoundedThumbTests(unittest.TestCase):
    def test_add_sub_compare_all_14_conditions_against_integer_oracle(self):
        pairs = [(0, 0), (0, 1), (1, 0), (0x7FFFFFFF, 1), (0x80000000, 1),
                 (0xFFFFFFFF, 1), (0x80000000, 0x80000000), (0x7FFFFFFF, 0xFFFFFFFF)]
        as_signed = lambda x: x if x < 0x80000000 else x - 0x100000000
        for opcode, subtract in ((0x1840, False), (0x1A40, True), (0x4288, True)):
            for a, b in pairs:
                full = a - b if subtract else a + b
                value = full & 0xFFFFFFFF
                signed_full = as_signed(a) - as_signed(b) if subtract else as_signed(a) + as_signed(b)
                z, n = value == 0, bool(value >> 31)
                c = a >= b if subtract else full > 0xFFFFFFFF
                v = not -0x80000000 <= signed_full <= 0x7FFFFFFF
                oracle = [z, not z, c, not c, n, not n, v, not v,
                          c and not z, not c or z, n == v, n != v,
                          not z and n == v, z or n != v]
                for condition, expected in enumerate(oracle):
                    rom = struct.pack('<5H', opcode, 0xD001 | condition << 8, 0x2200, 0xE000, 0x2201)
                    registers = [0] * 16
                    registers[0], registers[1] = a, b
                    result = execute(rom, 0, {0, 2, 4, 6, 8}, registers, {}, set(), stops=(10,), return_address=0x08000101)
                    self.assertEqual(result['registers'][2], int(expected), (hex(opcode), a, b, condition))

    def test_shift_zero_and_32_preserve_or_update_carry_correctly(self):
        # CMP establishes C=1, then shift r0,r0 and BCS selects the result.
        for opcode, value, expected in ((0,0,True),(0x0800,0x80000000,True),
                                         (0x0800,1,False),(0x1000,0x80000000,True),
                                         (0x1000,1,False),(0x0040,0x80000000,True)):
            rom=struct.pack('<6H',0x4289,opcode,0xD201,0x2200,0xE000,0x2201)
            registers=[0]*16;registers[0]=value
            result=execute(rom,0,{0,2,4,6,8,10},registers,{},set(),stops=(12,),return_address=0x08000101)
            self.assertEqual(result['registers'][2],int(expected))

    def test_return_sentinel_cannot_overlap_source_or_root(self):
        with self.assertRaisesRegex(ValueError,'return sentinel'):
            execute(bytes.fromhex('00df'),0,{0},[0]*16,{},set())

    def test_memory_alignment_whitelist_and_interwork_fail_closed(self):
        registers=[0]*16;registers[1]=0x03000001
        with self.assertRaisesRegex(ValueError,'unaligned'):
            execute(bytes.fromhex('0860'),0,{0},registers,{0x03000001+n:0 for n in range(4)},set(),return_address=0x08000101)
        with self.assertRaisesRegex(ValueError,'unapproved ROM'):
            execute(bytes.fromhex('0048000000000000'),0,{0},registers,{},set(),return_address=0x08000101)
        with self.assertRaisesRegex(ValueError,'ARM interwork'):
            execute(bytes.fromhex('0847'),0,{0},[0]*16,{},set(),return_address=0x08000101)


if __name__ == '__main__': unittest.main(verbosity=2)
