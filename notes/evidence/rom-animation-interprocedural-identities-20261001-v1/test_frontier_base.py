import importlib.util
import struct
import unittest
from pathlib import Path


def bl(at, target):
    delta = (target - at - 4) & 0x7FFFFF
    return struct.pack('<HH', 0xF000 | (delta >> 12), 0xF800 | ((delta >> 1) & 2047))


class FrontierTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('frontier', Path(__file__).with_name('frontier.py'))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.base = Path('rom/base.gba').read_bytes()

    def run_case(self, parts, site, *, budget=1000):
        rom = bytearray(self.base)
        for at, raw in parts.items():
            rom[at:at + len(raw)] = raw
        return self.m.dependencies(bytes(rom), set(parts), {min(parts)}, site, 16, budget=budget)

    def test_constant_stack_argument_finds_its_producer(self):
        result = self.run_case({0x100: bytes.fromhex('0024'), 0x102: bytes.fromhex('0494'),
                                0x104: bl(0x104, 0x626B4)}, 0x104)
        self.assertEqual(result['frontiers'], [{'kind': 'constant_producer', 'at': 0x100, 'register': 4, 'value': 0}])

    def test_unknown_callee_is_an_explicit_register_boundary(self):
        result = self.run_case({0x100: bytes.fromhex('0024'), 0x102: bl(0x102, 0x655B4),
                                0x106: bytes.fromhex('0494'), 0x108: bl(0x108, 0x626B4)}, 0x108)
        self.assertEqual(result['frontiers'][0]['kind'], 'unproved_callee_register_effect')
        self.assertEqual(result['frontiers'][0]['target'], 0x655B4)

    def test_allocator_does_not_preserve_stack_memory_origin(self):
        result = self.run_case({0x100: bytes.fromhex('0024'), 0x102: bytes.fromhex('1294'),
                                0x104: bl(0x104, 0x626B4), 0x108: bytes.fromhex('129c'),
                                0x10A: bytes.fromhex('0494'), 0x10C: bl(0x10C, 0x626B4)}, 0x10C)
        self.assertEqual(result['frontiers'][0]['kind'], 'unproved_callee_stack_effect')
        self.assertEqual(result['frontiers'][0]['target'], 0x626B4)

    def test_budget_exhaustion_does_not_fake_an_empty_frontier(self):
        with self.assertRaises(ValueError):
            self.run_case({0x100: bytes.fromhex('0024'), 0x102: bytes.fromhex('0494'),
                           0x104: bl(0x104, 0x626B4)}, 0x104, budget=1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
