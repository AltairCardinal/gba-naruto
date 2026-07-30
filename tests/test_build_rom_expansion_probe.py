import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_rom_expansion_probe import build_probe


class RomExpansionProbeTests(unittest.TestCase):
    def setUp(self):
        self.base = bytearray([0xFF] * 0x600000)
        struct.pack_into("<I", self.base, 0, 0xEA00002E)
        self.base = bytes(self.base)
        self.layout = {
            "version": 1,
            "base_rom": {
                "sha1": hashlib.sha1(self.base).hexdigest(),
                "size": "0x600000",
            },
            "cartridge_profile": {
                "id": "agb-standard-game-pak-rom",
                "rom_base": "0x08000000",
                "max_rom_size": "0x02000000",
            },
            "target_rom_size": "0x1000000",
            "fill_byte": "0xFF",
            "partitions": [
                {
                    "id": "character-battle-visual-bundles",
                    "owner": "character_battle_visuals",
                    "start": "0x600000",
                    "end": "0x800000",
                    "origin": "expanded_ff",
                    "alignment": 4,
                }
            ],
        }

    def test_probe_executes_and_reads_expanded_rom_before_returning_to_original_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_path = root / "base.gba"
            layout_path = root / "layout.json"
            output_path = root / "probe.gba"
            manifest_path = root / "manifest.json"
            base_path.write_bytes(self.base)
            layout_path.write_text(json.dumps(self.layout), encoding="utf-8")

            manifest = build_probe(
                base_path,
                layout_path,
                output_path,
                manifest_path,
            )
            output = output_path.read_bytes()

        self.assertEqual(0x1000000, len(output))
        self.assertEqual("0x080000C0", manifest["original_entry_target"])
        self.assertEqual("0x08600000", manifest["stub_address"])
        self.assertEqual("0x08600100", manifest["marker_address"])
        self.assertEqual("0x0203FFF0", manifest["scratch_address"])
        self.assertEqual("4D475842", manifest["marker_hex"])
        self.assertEqual("feff17ea", output[:4].hex())
        self.assertEqual(bytes.fromhex("4d475842"), output[0x600100:0x600104])
        self.assertEqual(
            bytes.fromhex(
                "10009fe5"
                "001090e5"
                "0c209fe5"
                "001082e5"
                "08309fe5"
                "13ff2fe1"
                "00016008"
                "f0ff0302"
                "c0000008"
            ),
            output[0x600000:0x600024],
        )
        changed = [
            index
            for index, (before, after) in enumerate(
                zip(
                    self.base + bytes([0xFF] * (len(output) - len(self.base))),
                    output,
                )
            )
            if before != after
        ]
        self.assertTrue(all(index < 4 or 0x600000 <= index < 0x600104 for index in changed))
        self.assertEqual(hashlib.sha256(output).hexdigest(), manifest["output_sha256"])

    def test_rejects_changed_or_non_branch_original_entry(self):
        bad_base = bytearray(self.base)
        struct.pack_into("<I", bad_base, 0, 0xE1A00000)
        bad_base = bytes(bad_base)
        layout = json.loads(json.dumps(self.layout))
        layout["base_rom"]["sha1"] = hashlib.sha1(bad_base).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "base.gba").write_bytes(bad_base)
            (root / "layout.json").write_text(json.dumps(layout), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "entry is not an unconditional ARM branch"):
                build_probe(
                    root / "base.gba",
                    root / "layout.json",
                    root / "probe.gba",
                    root / "manifest.json",
                )


if __name__ == "__main__":
    unittest.main()
