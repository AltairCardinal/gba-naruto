import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleStatusConsumerInventoryTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_status_consumers import build_status_consumer_manifest

        return build_status_consumer_manifest(ROOT / "rom/base.gba")

    def test_all_direct_lookup_and_upsert_references_are_hash_bound(self):
        result = self._manifest()
        self.assertEqual(result["lookup_reference_count"], 96)
        self.assertEqual(
            result["lookup_reference_address_sha256"],
            "8c8c19f160a99a33b65ca11ac8107278a593ef33914288b8e484a34d65d1c6d3",
        )
        self.assertEqual(result["upsert_reference_count"], 21)
        self.assertEqual(
            result["upsert_reference_address_sha256"],
            "691c1fe5f9c4559872e01cdd86cd6b2fb5a750258549aad8e8fd04d1886e4fcc",
        )

    def test_immediate_lookup_code_inventory_is_complete_without_naming_effects(self):
        result = self._manifest()
        self.assertEqual(result["immediate_lookup_count"], 95)
        self.assertEqual(result["dynamic_lookup_callsites"], ["0x0806C2C6"])
        self.assertEqual(
            result["immediate_lookup_code_usage"],
            {
                "0x04": 1,
                "0x05": 2,
                "0x09": 1,
                "0x0A": 1,
                "0x0D": 4,
                "0x0E": 12,
                "0x0F": 10,
                "0x10": 1,
                "0x11": 7,
                "0x12": 1,
                "0x13": 10,
                "0x15": 9,
                "0x16": 1,
                "0x19": 1,
                "0x1B": 1,
                "0x1E": 1,
                "0x1F": 1,
                "0x20": 1,
                "0x21": 1,
                "0x22": 1,
                "0x23": 1,
                "0x24": 1,
                "0x3D": 8,
                "0x3E": 9,
                "0x3F": 9,
            },
        )
        self.assertEqual(result["unique_immediate_lookup_codes"], 25)

    def test_existing_reaction_codes_are_a_subset_not_the_status_model(self):
        result = self._manifest()
        self.assertEqual(
            result["known_reaction_lookup_codes"],
            ["0x04", "0x09", "0x0A", "0x10", "0x16", "0x19"],
        )
        self.assertEqual(
            result["known_blocker_lookup_codes"],
            ["0x0F", "0x11", "0x15", "0x3D", "0x3E", "0x3F"],
        )
        self.assertEqual(result["unclassified_immediate_lookup_codes"], 13)


if __name__ == "__main__":
    unittest.main()
