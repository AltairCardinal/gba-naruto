from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.export_rom_m4a_byte_inventory import build_manifest
from tools.verify_rom_m4a_byte_inventory import verify_manifest


ROOT = Path(__file__).resolve().parents[1]


class RomM4aByteInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.manifest = build_manifest(ROOT)

    def test_exports_fixed_audio_denominators_and_exact_byte_total(self):
        manifest = self.manifest
        self.assertEqual("rom-m4a-byte-inventory-v1", manifest["schema"])
        self.assertEqual(
            {
                "active_sound_id_count": 80,
                "byte_count": 887_018,
                "claim_count": 842,
                "empty_sound_id_count": 79,
                "song_header_count": 80,
                "sound_id_count": 159,
                "tone_record_count": 387,
                "track_reference_count": 217,
                "track_stream_count": 217,
                "voicegroup_count": 23,
                "wave_count": 79,
            },
            manifest["summary"],
        )
        self.assertEqual(
            {
                "m4a_directsound_wave": 79,
                "m4a_empty_sound_id_entry": 79,
                "m4a_song_header": 80,
                "m4a_tone_record": 387,
                "m4a_track_stream": 217,
            },
            manifest["semantic_class_counts"],
        )
        self.assertEqual(
            {
                "m4a_directsound_wave": 850_898,
                "m4a_empty_sound_id_entry": 632,
                "m4a_song_header": 1_508,
                "m4a_tone_record": 4_644,
                "m4a_track_stream": 29_336,
            },
            manifest["semantic_class_bytes"],
        )

    def test_claims_are_disjoint_and_hash_bound_to_rom(self):
        claims = self.manifest["claims"]
        self.assertEqual(842, len(claims))
        previous_end = -1
        for claim in claims:
            start, end = claim["range"]
            self.assertGreaterEqual(start, previous_end)
            self.assertGreater(end, start)
            self.assertEqual(
                claim["bytes_sha256"],
                hashlib.sha256(self.rom[start:end]).hexdigest(),
            )
            previous_end = end

    def test_dense_audio_window_preserves_every_unclassified_gap(self):
        window = self.manifest["dense_audio_window"]
        self.assertEqual([0x466068, 0x53D5F4], window["range"])
        self.assertEqual(881_742, window["classified_bytes"])
        self.assertEqual(318, window["unclaimed_bytes"])
        self.assertEqual(81, len(window["unclaimed_ranges"]))
        self.assertEqual(
            [0x53D578, 0x53D5F4],
            window["unclaimed_ranges"][-1]["range"],
        )

    def test_independent_verifier_accepts_inventory_and_rejects_tamper(self):
        verifier_source = (
            ROOT / "tools/verify_rom_m4a_byte_inventory.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "from tools.export_rom_m4a_byte_inventory", verifier_source
        )
        self.assertNotIn(
            "import tools.export_rom_m4a_byte_inventory", verifier_source
        )

        report = verify_manifest(ROOT, self.manifest)
        self.assertTrue(report["verified"], report["errors"])

        tampered = copy.deepcopy(self.manifest)
        wave = next(
            claim
            for claim in tampered["claims"]
            if claim["semantic_class"] == "m4a_directsound_wave"
        )
        wave["range"][1] -= 1
        report = verify_manifest(ROOT, tampered)
        self.assertFalse(report["verified"])
        self.assertIn("manifest differs from independent parse", report["errors"])

    def test_direct_cli_writes_an_independently_verifiable_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/export_rom_m4a_byte_inventory.py",
                    "--root",
                    ".",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            manifest = json.loads(output.read_text(encoding="utf-8"))
            report = verify_manifest(ROOT, manifest)
            self.assertTrue(report["verified"], report["errors"])


if __name__ == "__main__":
    unittest.main()
