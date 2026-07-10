import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from patch_safety import PatchSafetyGate, with_base_precondition


class PatchSafetyGateTests(unittest.TestCase):
    def setUp(self):
        self.base = bytes(range(32))

    def test_precondition_is_read_from_base_not_mutated_buffer(self):
        mutated = bytearray(self.base)
        mutated[4:6] = b"\xaa\xbb"
        patch = with_base_precondition(self.base, {"offset": 4, "after_hex": "0102"})
        self.assertEqual("0405", patch["before_hex"])
        self.assertNotEqual(bytes(mutated[4:6]).hex(), patch["before_hex"])

    def test_rejects_undeclared_conflicting_overlap(self):
        gate = PatchSafetyGate(self.base)
        gate.register(
            {"id": "a", "offset": 4, "before_hex": "0405", "after_hex": "aabb"},
            patch_class="game_effective",
        )
        with self.assertRaisesRegex(ValueError, "conflicting patch overlap"):
            gate.register(
                {"id": "b", "offset": 5, "before_hex": "05", "after_hex": "cc"},
                patch_class="game_effective",
            )

    def test_explicit_merge_cannot_hide_different_bytes(self):
        gate = PatchSafetyGate(self.base)
        gate.register(
            {"id": "a", "offset": 4, "before_hex": "0405", "after_hex": "aabb", "merge_group": "table-row"},
            patch_class="game_effective",
        )
        with self.assertRaisesRegex(ValueError, "merge_group=.*still conflicts"):
            gate.register(
                {"id": "b", "offset": 5, "before_hex": "05", "after_hex": "cc", "merge_group": "table-row"},
                patch_class="game_effective",
            )

    def test_allows_identical_duplicate_without_pre_deduplication(self):
        gate = PatchSafetyGate(self.base)
        patch = {"id": "a", "offset": 4, "before_hex": "0405", "after_hex": "aabb"}
        first = gate.register(patch, patch_class="game_effective")
        second = gate.register({**patch, "id": "b"}, patch_class="game_effective")
        self.assertEqual("unique", first["overlap_disposition"])
        self.assertEqual("idempotent_duplicate", second["overlap_disposition"])
        self.assertEqual(["a"], second["duplicate_of"])

    def test_audit_is_classified_and_still_cannot_collide_with_game_data(self):
        gate = PatchSafetyGate(self.base)
        gate.register(
            {"id": "game", "offset": 8, "before_hex": "0809", "after_hex": "ffee"},
            patch_class="game_effective",
        )
        with self.assertRaisesRegex(ValueError, "game_effective.*audit"):
            gate.register(
                {"id": "audit", "offset": 9, "after_hex": "00"},
                patch_class="audit",
            )

    def test_rejects_out_of_bounds(self):
        gate = PatchSafetyGate(self.base)
        with self.assertRaisesRegex(ValueError, "outside ROM"):
            gate.register(
                {"id": "bad", "offset": 31, "before_hex": "1f", "after_hex": "aabb"},
                patch_class="game_effective",
            )


if __name__ == "__main__":
    unittest.main()
