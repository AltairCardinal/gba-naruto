import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.analyze_original_action_components import (
    analyze_lz77_transfers,
    load_trace,
)


def _literal_lz77(payload: bytes) -> bytes:
    encoded = bytearray((0x10,))
    encoded.extend(len(payload).to_bytes(3, "little"))
    for start in range(0, len(payload), 8):
        encoded.append(0)
        encoded.extend(payload[start : start + 8])
    return bytes(encoded)


class OriginalActionComponentAnalyzerTest(unittest.TestCase):
    def test_cli_runs_directly_from_repository_root(self):
        payload = bytes(range(8))
        encoded = _literal_lz77(payload)
        rom = bytearray(0x100)
        rom[0x20 : 0x20 + len(encoded)] = encoded
        records = [
            {
                "frame": 1,
                "cycle": "1",
                "target": "lz77_vram",
                "r0": "0x08000020",
                "r1": "0x06000000",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            rom_path = temp / "test.gba"
            trace_path = temp / "trace.jsonl"
            rom_path.write_bytes(rom)
            trace_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            trace_sha256 = hashlib.sha256(
                trace_path.read_bytes()
            ).hexdigest()

            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[1]
                        / "tools"
                        / "analyze_original_action_components.py"
                    ),
                    str(rom_path),
                    str(trace_path),
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(
            "original-action-components-v1",
            json.loads(completed.stdout)["schema"],
        )
        self.assertEqual(
            trace_sha256,
            json.loads(completed.stdout)["trace_sha256"],
        )

    def test_load_trace_rejects_non_object_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            trace = Path(temp_dir) / "trace.jsonl"
            trace.write_text('{"frame":1}\n[]\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "JSON object"):
                load_trace(trace)

    def test_analysis_links_rom_components_to_phase_and_gpu_destination(self):
        background = bytes(range(32))
        actor = bytes(reversed(range(32)))
        rom = bytearray(0x200)
        rom[0x40 : 0x40 + len(_literal_lz77(background))] = _literal_lz77(
            background
        )
        rom[0x90 : 0x90 + len(_literal_lz77(actor))] = _literal_lz77(actor)

        records = [
            {
                "frame": 50,
                "cycle": "100",
                "target": "effect_resource_builder",
            },
            {
                "frame": 51,
                "cycle": "110",
                "target": "lz77_vram",
                "r0": "0x08000040",
                "r1": "0x06004000",
            },
            {
                "frame": 145,
                "cycle": "200",
                "target": "hit_presentation",
            },
            {
                "frame": 145,
                "cycle": "210",
                "target": "lz77_vram",
                "r0": "0x08000090",
                "r1": "0x06012400",
            },
            {
                "frame": 146,
                "cycle": "220",
                "target": "lz77_vram",
                "r0": "0x02000000",
                "r1": "0x06013000",
            },
        ]
        vram = bytearray(0x18000)
        vram[0x4000 : 0x4020] = background
        vram[0x12400 : 0x12420] = actor

        result = analyze_lz77_transfers(
            bytes(rom),
            records,
            memory_dumps={"vram": bytes(vram)},
        )

        self.assertEqual(2, len(result["components"]))
        first, second = result["components"]
        self.assertEqual("0x08000040", first["source_address"])
        self.assertEqual("vram", first["destination_domain"])
        self.assertEqual("bg_tiles", first["component_kind"])
        self.assertEqual("0x00004000", first["destination_offset"])
        self.assertEqual(32, first["decompressed_size"])
        self.assertEqual(
            hashlib.sha256(background).hexdigest(),
            first["decompressed_sha256"],
        )
        self.assertTrue(first["destination_matches_dump"])
        self.assertEqual(
            "effect_resource_builder",
            first["phase_anchor"]["target"],
        )
        self.assertEqual("hit_presentation", second["phase_anchor"]["target"])
        self.assertTrue(second["destination_matches_dump"])

    def test_analysis_reports_out_of_range_destination_without_guessing(self):
        payload = bytes(range(8))
        rom = bytearray(0x100)
        encoded = _literal_lz77(payload)
        rom[0x20 : 0x20 + len(encoded)] = encoded

        result = analyze_lz77_transfers(
            bytes(rom),
            [
                {
                    "frame": 1,
                    "cycle": "1",
                    "target": "lz77_vram",
                    "r0": "0x08000020",
                    "r1": "0x07000000",
                }
            ],
            memory_dumps={"vram": bytes(0x18000)},
        )

        self.assertEqual([], result["components"])
        self.assertEqual(1, result["ignored_non_gpu_transfer_count"])

    def test_32_by_20_byte_screen_map_is_classified_as_tilemap(self):
        payload = bytes(index % 96 for index in range(32 * 20))
        encoded = _literal_lz77(payload)
        rom = bytearray(0x400)
        rom[0x20 : 0x20 + len(encoded)] = encoded

        result = analyze_lz77_transfers(
            bytes(rom),
            [
                {
                    "frame": 1,
                    "cycle": "1",
                    "target": "lz77_vram",
                    "r0": "0x08000020",
                    "r1": "0x06000000",
                }
            ],
        )

        self.assertEqual(
            "bg_tilemap",
            result["components"][0]["component_kind"],
        )


if __name__ == "__main__":
    unittest.main()
