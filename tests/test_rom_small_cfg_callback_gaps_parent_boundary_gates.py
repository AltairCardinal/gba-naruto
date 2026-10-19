"""Independent boundary counterexamples omitted by the initial pure helper."""
import unittest
from tools import rom_small_cfg_callback_gaps_producer as producer
from tests.test_rom_small_cfg_callback_gaps_producer import _align4_fixture, _put_halfword


class BoundaryGates(unittest.TestCase):
    def test_branch_to_claimed_gap_or_literal_is_not_a_proven_boundary(self):
        for instruction in (0xE7FF, 0xE000):
            with self.subTest(instruction=hex(instruction)):
                rom, code, literals, bindings = _align4_fixture(instruction)
                with self.assertRaisesRegex(ValueError, 'branch.*(gap|literal|boundary)'):
                    producer.derive_boundaries(rom, code, literals, bindings)

    def test_entire_supplied_literal_domain_has_actual_word_consumers(self):
        rom, code, _, bindings = _align4_fixture(0xE006)
        with self.assertRaisesRegex(ValueError, 'literal.*(word|cover|binding)'):
            producer.derive_boundaries(rom, code, [[12, 20]], bindings)


if __name__ == '__main__':
    unittest.main()
