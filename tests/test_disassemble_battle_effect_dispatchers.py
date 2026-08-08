from __future__ import annotations

import hashlib
import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/_vendor"))


class BattleEffectDispatcherInventoryTests(unittest.TestCase):
    def test_inventory_records_rom_hash_and_direct_callers(self):
        module = importlib.import_module(
            "tools.disassemble_battle_effect_dispatchers"
        )
        rom_path = ROOT / "rom/base.gba"
        inventory = module.build_dispatcher_inventory(rom_path)

        self.assertEqual(
            inventory["rom_sha256"],
            hashlib.sha256(rom_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            inventory["direct_callers"]["0x0807C93C"],
            [
                "0x0807BA7E",
                "0x0807BF64",
                "0x0807C092",
                "0x0807F150",
                "0x0807F184",
                "0x0807F1D2",
            ],
        )
        self.assertEqual(inventory["direct_callers"]["0x0807B8B8"], [])
        self.assertIn("dynamic", inventory["scope"]["outer_entry_boundary"])


if __name__ == "__main__":
    unittest.main()
