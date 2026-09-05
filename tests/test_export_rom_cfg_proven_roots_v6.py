#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from tools.export_rom_cfg_proven_roots_v6 import (
    _producer_denominator,
    build_cfg_proven_roots_v6_payload,
    export_rom_cfg_proven_roots_v6,
)
from tools.verify_rom_cfg_proven_roots_v6 import verify_rom_cfg_proven_roots_v6

ROOT = Path(__file__).resolve().parents[1]


class RomCfgProvenRootsV6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_finds_exact_six_producers_for_five_roots(self):
        report = _producer_denominator(self.rom)
        self.assertEqual(
            [
                (0x8F474, 0x8ECD0),
                (0x8F47A, 0x8E118),
                (0x8F644, 0x8A0F0),
                (0x8F872, 0x87940),
                (0x8F9C0, 0x8A0F0),
                (0x8FA1C, 0x86FEC),
            ],
            [
                (item["file_offset"], item["target_file_offset"])
                for item in report["producers"]
            ],
        )

    def test_freezes_exact_union_delta_and_frontiers(self):
        payload = build_cfg_proven_roots_v6_payload(ROOT)
        self.assertEqual(5, len(payload["roots"]))
        self.assertEqual(
            {
                "decoded_basic_block_count": 2_305,
                "decoded_instruction_count": 12_564,
                "frontier_count": 85,
                "frontier_reasons": {"indirect_pc_target": 85},
                "reachable_instruction_bytes": 27_224,
            },
            payload["extension"]["summary"],
        )
        self.assertEqual(916, len(payload["extension"]["baseline_cross_edges"]))

    def test_exports_and_independently_verifies(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = Path(tmp) / "cfg-v6"
            export_rom_cfg_proven_roots_v6(ROOT, output)
            report = verify_rom_cfg_proven_roots_v6(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(12_564, report["decoded_instruction_count"])
            self.assertEqual(85, report["frontier_count"])

    def _tampered_artifact(self, tmp: str, mutate) -> Path:
        output = Path(tmp) / "cfg-v6"
        export_rom_cfg_proven_roots_v6(ROOT, output)
        payload_path = output / "rom-cfg-proven-roots-v6.json"
        payload = json.loads(payload_path.read_text())
        mutate(payload)
        raw = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode()
        payload_path.write_bytes(raw)
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["rom-cfg-proven-roots-v6.json"] = {
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        )
        return output

    def test_rejects_tampered_cross_hash_after_manifest_rebuild(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = self._tampered_artifact(
                tmp,
                lambda payload: payload["extension"].__setitem__(
                    "cross_edge_denominator_sha256", "0" * 64
                ),
            )
            self.assertFalse(verify_rom_cfg_proven_roots_v6(ROOT, output)["verified"])

    def test_rejects_tampered_scope_after_manifest_rebuild(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = self._tampered_artifact(
                tmp,
                lambda payload: payload["scope"].__setitem__(
                    "runtime_reachability_complete", True
                ),
            )
            self.assertFalse(verify_rom_cfg_proven_roots_v6(ROOT, output)["verified"])

    def test_rejects_tampered_v5_baseline_after_manifest_rebuild(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = self._tampered_artifact(
                tmp,
                lambda payload: payload["frozen_baseline"][
                    "proven_roots_v5"
                ].__setitem__("payload_sha256", "0" * 64),
            )
            self.assertFalse(verify_rom_cfg_proven_roots_v6(ROOT, output)["verified"])

    def test_rejects_repository_root_as_output(self):
        with self.assertRaisesRegex(ValueError, "repository root"):
            export_rom_cfg_proven_roots_v6(ROOT, ROOT)

    def test_rejects_foreign_non_empty_output_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            output = Path(tmp) / "cfg-v6"
            output.mkdir()
            (output / "foreign.txt").write_text("do not replace")
            with self.assertRaisesRegex(ValueError, "foreign non-empty directory"):
                export_rom_cfg_proven_roots_v6(ROOT, output)

    def test_rejects_symlink_output_component(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as tmp:
            base = Path(tmp)
            real = base / "real"
            real.mkdir()
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                export_rom_cfg_proven_roots_v6(ROOT, linked / "cfg-v6")


if __name__ == "__main__":
    unittest.main()
