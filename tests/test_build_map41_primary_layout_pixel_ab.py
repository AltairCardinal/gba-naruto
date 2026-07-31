from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from tools.extract_tileset import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]
ROM_BASE = 0x08000000
TARGET_HEADER_POINTER_OFFSET = 0x53DE3C
OTHER_ALIAS_POINTER_OFFSETS = [
    0x53DDFC,
    0x53DE1C,
    0x53DE5C,
    0x53DE7C,
    0x53DE9C,
    0x53DEBC,
]


class BuildMap41PrimaryLayoutPixelAbTests(unittest.TestCase):
    def test_builds_isolated_map41_alias_split_rom_pair(self):
        from tools.build_map41_primary_layout_pixel_ab import build_ab_roms

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            manifest = build_ab_roms(ROOT, output)

            baseline = (output / "baseline.gba").read_bytes()
            candidate = (output / "candidate.gba").read_bytes()
            base = (ROOT / "rom/base.gba").read_bytes()
            self.assertEqual(0x1000000, len(baseline))
            self.assertEqual(len(baseline), len(candidate))
            self.assertNotEqual(baseline, candidate)

            edit = manifest["edit"]
            self.assertEqual(41, edit["map_id"])
            self.assertEqual("primary_layout", edit["resource_type"])
            self.assertEqual("0x0811DCC0", edit["map41_source_pointer"])
            self.assertEqual("0x0053DE3C", edit["target_header_pointer_offset"])
            self.assertEqual([1, 6], [edit["coarse_x"], edit["coarse_y"]])
            self.assertEqual(0xDC, edit["decoded_byte_offset"])
            self.assertEqual("0x00350022", edit["before_word"])
            self.assertEqual("0x00220035", edit["after_word"])
            self.assertEqual([0xDC, 0xDE], edit["decoded_differing_byte_offsets"])

            runtime_pointer = int(manifest["runtime_source_pointer"], 16)
            self.assertEqual(0x08980000, runtime_pointer)
            for rom in (baseline, candidate):
                self.assertEqual(
                    runtime_pointer,
                    struct.unpack_from("<I", rom, TARGET_HEADER_POINTER_OFFSET)[0],
                )
            for offset in OTHER_ALIAS_POINTER_OFFSETS:
                expected = base[offset : offset + 4]
                self.assertEqual(expected, baseline[offset : offset + 4])
                self.assertEqual(expected, candidate[offset : offset + 4])

            baseline_raw = lz77_decompress(
                baseline, runtime_pointer - ROM_BASE
            )
            candidate_raw = lz77_decompress(
                candidate, runtime_pointer - ROM_BASE
            )
            self.assertEqual(792, len(baseline_raw))
            self.assertEqual(792, len(candidate_raw))
            self.assertEqual(0x00350022, struct.unpack_from("<I", baseline_raw, 0xDC)[0])
            self.assertEqual(0x00220035, struct.unpack_from("<I", candidate_raw, 0xDC)[0])
            self.assertEqual(
                [0xDC, 0xDE],
                [
                    index
                    for index, pair in enumerate(zip(baseline_raw, candidate_raw))
                    if pair[0] != pair[1]
                ],
            )

            self.assertEqual(
                hashlib.sha256(baseline).hexdigest(),
                manifest["roms"]["baseline"]["sha256"],
            )
            self.assertEqual(
                hashlib.sha256(candidate).hexdigest(),
                manifest["roms"]["candidate"]["sha256"],
            )
            for variant, expected in (
                ("baseline", baseline),
                ("candidate", candidate),
            ):
                reconstructed = bytearray(
                    base + b"\xFF" * (0x1000000 - len(base))
                )
                ledger = manifest["patch_ledgers"][variant]
                self.assertEqual(2, len(ledger))
                self.assertEqual(
                    ["allocation", "pointer_redirect"],
                    [entry["kind"] for entry in ledger],
                )
                for entry in ledger:
                    offset = entry["offset"]
                    before = bytes.fromhex(entry["before_hex"])
                    after = bytes.fromhex(entry["after_hex"])
                    self.assertEqual(
                        before,
                        reconstructed[offset : offset + len(before)],
                    )
                    reconstructed[offset : offset + len(after)] = after
                self.assertEqual(expected, bytes(reconstructed))

            self.assertEqual(
                OTHER_ALIAS_POINTER_OFFSETS,
                manifest["alias_split"]["preserved_header_pointer_offsets"],
            )
            self.assertTrue(manifest["isolation"]["same_runtime_source_pointer"])
            self.assertTrue(manifest["isolation"]["only_map41_header_redirected"])
            self.assertEqual(2, manifest["isolation"]["decoded_source_diff_count"])

    def test_rejects_nonempty_output_and_out_of_contract_edit(self):
        from tools.build_map41_primary_layout_pixel_ab import build_ab_roms

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "owned-by-another-run.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output directory must be empty"):
                build_ab_roms(ROOT, output)

        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "fixed A/B contract"):
                build_ab_roms(
                    ROOT,
                    Path(temporary),
                    coarse_x=0,
                    coarse_y=0,
                    replacement_word=0,
                )


if __name__ == "__main__":
    unittest.main()
