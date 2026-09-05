#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from tools.export_rom_cfg_proven_roots_v5 import (
    _producer_denominator,
    _root_seeds,
    build_cfg_proven_roots_v5_payload,
    export_rom_cfg_proven_roots_v5,
)
from tools.verify_rom_cfg_proven_roots_v5 import verify_rom_cfg_proven_roots_v5


ROOT = Path(__file__).resolve().parents[1]


class RomCfgProvenRootsV5ProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_full_rom_scan_finds_exact_three_single_producer_roots(self) -> None:
        denominator = _producer_denominator(self.rom)
        self.assertEqual(
            [(0x736DE, 0x6DF88), (0x73702, 0x8A534), (0x73780, 0x8A588)],
            [
                (item["file_offset"], item["target_file_offset"])
                for item in denominator["producers"]
            ],
        )
        self.assertEqual(3, denominator["scan"]["matching_producer_count"])

    def test_producer_denominator_fails_closed_on_each_callsite(self) -> None:
        for offset in (0x736DE, 0x73702, 0x73780):
            with self.subTest(offset=offset):
                tampered = bytearray(self.rom)
                tampered[offset] ^= 1
                with self.assertRaisesRegex(
                    ValueError, "producer denominator changed"
                ):
                    _producer_denominator(bytes(tampered))

    def test_root_seeds_bind_one_producer_each(self) -> None:
        roots = _root_seeds(self.rom)
        self.assertEqual(
            [0x6DF88, 0x8A534, 0x8A588],
            [item["file_offset"] for item in roots],
        )
        self.assertTrue(all(len(item["sources"]) == 1 for item in roots))


class RomCfgProvenRootsV5IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_cfg_proven_roots_v5_payload(ROOT)

    def test_freezes_v4_and_every_prior_cfg_as_opaque_baseline(self) -> None:
        self.assertEqual(
            {
                "battle_controller",
                "proven_roots_v1",
                "proven_roots_v2",
                "proven_roots_v3",
                "proven_roots_v4",
                "v2",
                "v3",
            },
            set(self.payload["frozen_baseline"]),
        )

    def test_builds_nonempty_three_root_delta(self) -> None:
        self.assertEqual("rom-cfg-proven-roots-v5", self.payload["schema"])
        self.assertEqual(3, len(self.payload["roots"]))
        self.assertGreater(
            self.payload["extension"]["summary"]["reachable_instruction_bytes"],
            0,
        )

    def test_freezes_exact_three_root_delta(self) -> None:
        self.assertEqual(
            {
                "decoded_basic_block_count": 124,
                "decoded_instruction_count": 576,
                "frontier_count": 8,
                "frontier_reasons": {"indirect_pc_target": 8},
                "reachable_instruction_bytes": 1_252,
            },
            self.payload["extension"]["summary"],
        )
        self.assertEqual(40, len(self.payload["extension"]["baseline_cross_edges"]))


class RomCfgProvenRootsV5ArtifactTests(unittest.TestCase):
    def _tampered_artifact(self, tmp: str, mutate) -> Path:
        output = Path(tmp).resolve() / "cfg-v5"
        export_rom_cfg_proven_roots_v5(ROOT, output)
        payload_path = output / "rom-cfg-proven-roots-v5.json"
        payload = json.loads(payload_path.read_text()); mutate(payload)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(); payload_path.write_bytes(raw)
        manifest = json.loads((output / "manifest.json").read_text()); manifest["rom"] = payload["rom"]
        manifest["files"]["rom-cfg-proven-roots-v5.json"] = {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
        return output

    def test_rejects_tampered_cross_hash_with_rebuilt_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self._tampered_artifact(tmp, lambda p: p["extension"].__setitem__("cross_edge_denominator_sha256", "0" * 64))
            self.assertFalse(verify_rom_cfg_proven_roots_v5(ROOT, output)["verified"])

    def test_rejects_tampered_scope_with_rebuilt_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self._tampered_artifact(tmp, lambda p: p["scope"].__setitem__("runtime_reachability_complete", True))
            self.assertFalse(verify_rom_cfg_proven_roots_v5(ROOT, output)["verified"])

    def test_exports_only_manifest_and_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve() / "cfg-v5"
            manifest = export_rom_cfg_proven_roots_v5(ROOT, output)
            self.assertEqual(
                {"manifest.json", "rom-cfg-proven-roots-v5.json"},
                {path.name for path in output.iterdir()},
            )
            self.assertEqual("rom-cfg-proven-roots-v5", manifest["artifact_schema"])
            report = verify_rom_cfg_proven_roots_v5(ROOT, output)
            self.assertTrue(report["verified"], report)

    def test_rejects_repository_root_as_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "repository root"):
            export_rom_cfg_proven_roots_v5(ROOT, ROOT)


if __name__ == "__main__":
    unittest.main()
