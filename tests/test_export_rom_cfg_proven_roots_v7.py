#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

from tools.export_rom_cfg_proven_roots_v7 import (
    _dispatcher_denominator,
    build_cfg_proven_roots_v7_payload,
    export_rom_cfg_proven_roots_v7,
)
from tools.verify_rom_cfg_proven_roots_v7 import verify_rom_cfg_proven_roots_v7


ROOT = Path(__file__).resolve().parents[1]


class RomCfgProvenRootsV7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_binds_two_fixed_dispatcher_denominators(self):
        report = _dispatcher_denominator(self.rom)
        self.assertEqual([7, 38], [item["entry_count"] for item in report])
        self.assertEqual(
            [0x6E84E, 0x92850],
            [item["terminal_file_offset"] for item in report],
        )
        self.assertEqual(21, len({target for item in report for target in item["target_vector"]}))

    def test_dispatcher_denominator_fails_closed_on_proof_and_table_bytes(self):
        for offset in (0x6E83A, 0x6E868, 0x9283A, 0x92864):
            with self.subTest(offset=offset):
                tampered = bytearray(self.rom)
                tampered[offset] ^= 1
                with self.assertRaises(ValueError):
                    _dispatcher_denominator(bytes(tampered))

    def test_freezes_exact_closed_delta(self):
        payload = build_cfg_proven_roots_v7_payload(ROOT)
        self.assertEqual(8, len(payload["roots"]))
        self.assertEqual(
            {
                "decoded_basic_block_count": 38,
                "decoded_instruction_count": 155,
                "frontier_count": 1,
                "frontier_reasons": {"indirect_pc_target": 1},
                "reachable_instruction_bytes": 332,
            },
            payload["extension"]["summary"],
        )
        self.assertEqual(17, len(payload["extension"]["baseline_cross_edges"]))

    def _tampered_artifact(self, tmp: str, mutate) -> Path:
        output = Path(tmp) / "cfg-v7"
        export_rom_cfg_proven_roots_v7(ROOT, output)
        payload_path = output / "rom-cfg-proven-roots-v7.json"
        payload = json.loads(payload_path.read_text())
        mutate(payload)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload_path.write_bytes(raw)
        manifest = json.loads((output / "manifest.json").read_text())
        manifest["files"][payload_path.name] = {
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        )
        return output

    def test_exports_and_independently_verifies(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = Path(tmp) / "cfg-v7"
            export_rom_cfg_proven_roots_v7(ROOT, output)
            report = verify_rom_cfg_proven_roots_v7(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(155, report["decoded_instruction_count"])
            self.assertEqual(1, report["frontier_count"])

    def test_exporter_cli_runs_from_repository_root(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            completed = subprocess.run(
                [sys.executable, "tools/export_rom_cfg_proven_roots_v7.py", "--root", ".", "--output-dir", str(Path(tmp) / "cfg-v7")],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)

    def test_rejects_tampered_dispatcher_after_manifest_rebuild(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = self._tampered_artifact(
                tmp,
                lambda payload: payload["dispatcher_denominator"][0].update(
                    {"index_max": 7}
                ),
            )
            self.assertFalse(verify_rom_cfg_proven_roots_v7(ROOT, output)["verified"])

    def test_rejects_tampered_cross_hash_after_manifest_rebuild(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = self._tampered_artifact(
                tmp,
                lambda payload: payload["extension"].update(
                    {"cross_edge_denominator_sha256": "0" * 64}
                ),
            )
            self.assertFalse(verify_rom_cfg_proven_roots_v7(ROOT, output)["verified"])

    def test_verifier_does_not_import_exporter(self):
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v7.py").read_text()
        self.assertNotIn("export_rom_cfg_proven_roots_v7", source)

    def test_rejects_repository_root_as_output(self):
        with self.assertRaisesRegex(ValueError, "repository root"):
            export_rom_cfg_proven_roots_v7(ROOT, ROOT)


if __name__ == "__main__":
    unittest.main()
