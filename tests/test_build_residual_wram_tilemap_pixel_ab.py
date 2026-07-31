from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from tools.extract_tileset import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]


class BuildResidualWramTilemapPixelAbTests(unittest.TestCase):
    def test_builds_isolated_relocated_rom_pair_and_pixel_oracle(self):
        from tools.build_residual_wram_tilemap_pixel_ab import build_ab_roms

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            manifest = build_ab_roms(ROOT, output)

            baseline = (output / "baseline.gba").read_bytes()
            candidate = (output / "candidate.gba").read_bytes()
            self.assertEqual(0x1000000, len(baseline))
            self.assertEqual(len(baseline), len(candidate))
            self.assertNotEqual(baseline, candidate)

            edit = manifest["edit"]
            self.assertEqual("0x084635D8", edit["source_pointer"])
            self.assertEqual([8, 8], [edit["row"], edit["column"]])
            self.assertEqual("0xD80C", edit["before_entry"])
            self.assertEqual("0xD80B", edit["after_entry"])
            self.assertEqual("0xDAC8", edit["effective_before_entry"])
            self.assertEqual("0xDAC7", edit["effective_after_entry"])
            self.assertEqual("0x06000A16", edit["vram_entry_address"])

            runtime_pointer = int(manifest["runtime_source_pointer"], 16)
            self.assertEqual(0x08BC15AC, runtime_pointer)
            pointer_offset = 0x090DE8
            self.assertEqual(
                runtime_pointer,
                struct.unpack_from("<I", baseline, pointer_offset)[0],
            )
            self.assertEqual(
                runtime_pointer,
                struct.unpack_from("<I", candidate, pointer_offset)[0],
            )

            baseline_raw = lz77_decompress(
                baseline, runtime_pointer - 0x08000000
            )
            candidate_raw = lz77_decompress(
                candidate, runtime_pointer - 0x08000000
            )
            self.assertEqual(288, len(baseline_raw))
            self.assertEqual(288, len(candidate_raw))
            differing = [
                index
                for index, pair in enumerate(zip(baseline_raw, candidate_raw))
                if pair[0] != pair[1]
            ]
            self.assertEqual([2 * (8 * 12 + 8)], differing)

            oracle = manifest["pixel_oracle"]
            self.assertEqual([88, 64, 95, 71], oracle["screen_bbox"])
            self.assertEqual(50, oracle["source_tile_differing_pixel_count"])
            self.assertEqual(50, len(oracle["expected_screen_pixels"]))
            self.assertEqual(
                hashlib.sha256(baseline).hexdigest(),
                manifest["roms"]["baseline"]["sha256"],
            )
            self.assertEqual(
                hashlib.sha256(candidate).hexdigest(),
                manifest["roms"]["candidate"]["sha256"],
            )
            base = (ROOT / "rom/base.gba").read_bytes()
            for variant, expected in (
                ("baseline", baseline),
                ("candidate", candidate),
            ):
                reconstructed = bytearray(base + b"\xFF" * (0x1000000 - len(base)))
                ledger = manifest["patch_ledgers"][variant]
                self.assertEqual(8, len(ledger))
                for patch in ledger:
                    offset = patch["offset"]
                    before = bytes.fromhex(patch["before_hex"])
                    after = bytes.fromhex(patch["after_hex"])
                    self.assertEqual(before, reconstructed[offset : offset + len(before)])
                    reconstructed[offset : offset + len(after)] = after
                self.assertEqual(expected, bytes(reconstructed))

    def test_rejects_out_of_contract_edit(self):
        from tools.build_residual_wram_tilemap_pixel_ab import build_ab_roms

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "fixed A/B contract"):
                build_ab_roms(
                    ROOT,
                    Path(temporary),
                    row=0,
                    column=0,
                    replacement_entry=0xD001,
                )


if __name__ == "__main__":
    unittest.main()
