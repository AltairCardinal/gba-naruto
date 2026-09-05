#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from tools.export_rom_cfg_proven_roots_v4 import (
    _producer_denominator,
    _root_seeds,
    build_cfg_proven_roots_v4_payload,
    export_rom_cfg_proven_roots_v4,
)
from tools.verify_rom_cfg_proven_roots_v4 import verify_rom_cfg_proven_roots_v4


ROOT = Path(__file__).resolve().parents[1]


class RomCfgProvenRootsV4ProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_full_rom_scan_finds_exact_four_producers_for_07305c(self) -> None:
        denominator = _producer_denominator(self.rom)
        self.assertEqual(
            [
                (0x73696, 0x7305C),
                (0x736C4, 0x7305C),
                (0x7444E, 0x7305C),
                (0x749CE, 0x7305C),
            ],
            [
                (item["file_offset"], item["target_file_offset"])
                for item in denominator["producers"]
            ],
        )
        self.assertEqual(4, denominator["scan"]["matching_producer_count"])

    def test_producer_denominator_fails_closed_on_each_callsite(self) -> None:
        for offset in (0x73696, 0x736C4, 0x7444E, 0x749CE):
            with self.subTest(offset=offset):
                tampered = bytearray(self.rom)
                tampered[offset] ^= 1
                with self.assertRaisesRegex(
                    ValueError, "producer denominator changed"
                ):
                    _producer_denominator(bytes(tampered))

    def test_root_seed_is_bound_to_all_four_producers(self) -> None:
        roots = _root_seeds(self.rom)
        self.assertEqual([0x7305C], [item["file_offset"] for item in roots])
        self.assertEqual(4, len(roots[0]["sources"]))


class RomCfgProvenRootsV4IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_cfg_proven_roots_v4_payload(ROOT)

    def test_freezes_every_prior_cfg_artifact_as_opaque_baseline(self) -> None:
        self.assertEqual(
            {
                "battle_controller",
                "proven_roots_v1",
                "proven_roots_v2",
                "proven_roots_v3",
                "v2",
                "v3",
            },
            set(self.payload["frozen_baseline"]),
        )

    def test_builds_nonempty_one_root_delta_without_baseline_overlap(self) -> None:
        self.assertEqual("rom-cfg-proven-roots-v4", self.payload["schema"])
        self.assertEqual(1, len(self.payload["roots"]))
        summary = self.payload["extension"]["summary"]
        self.assertGreater(summary["decoded_instruction_count"], 0)
        self.assertGreater(summary["decoded_basic_block_count"], 0)
        self.assertGreater(summary["reachable_instruction_bytes"], 0)
        self.assertFalse(self.payload["scope"]["runtime_reachability_complete"])

    def test_freezes_exact_delta_denominator(self) -> None:
        self.assertEqual(
            {
                "decoded_basic_block_count": 118,
                "decoded_instruction_count": 486,
                "frontier_count": 6,
                "frontier_reasons": {"indirect_pc_target": 6},
                "reachable_instruction_bytes": 1_044,
            },
            self.payload["extension"]["summary"],
        )
        self.assertEqual(29, len(self.payload["extension"]["baseline_cross_edges"]))


class RomCfgProvenRootsV4ArtifactTests(unittest.TestCase):
    def _tampered_artifact(self, tmp: str, mutate) -> Path:
        output = Path(tmp).resolve() / "cfg-v4"
        export_rom_cfg_proven_roots_v4(ROOT, output)
        payload_path = output / "rom-cfg-proven-roots-v4.json"
        payload = json.loads(payload_path.read_text())
        mutate(payload)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload_path.write_bytes(raw)
        manifest = json.loads((output / "manifest.json").read_text())
        manifest["rom"] = payload["rom"]
        manifest["files"]["rom-cfg-proven-roots-v4.json"] = {
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        )
        return output

    def test_rejects_tampered_cross_denominator_with_rebuilt_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self._tampered_artifact(
                tmp,
                lambda payload: payload["extension"].__setitem__(
                    "cross_edge_denominator_sha256", "0" * 64
                ),
            )
            self.assertFalse(verify_rom_cfg_proven_roots_v4(ROOT, output)["verified"])

    def test_rejects_tampered_frozen_baseline_with_rebuilt_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self._tampered_artifact(
                tmp,
                lambda payload: payload["frozen_baseline"]["v2"].__setitem__(
                    "schema", "tampered"
                ),
            )
            self.assertFalse(verify_rom_cfg_proven_roots_v4(ROOT, output)["verified"])

    def test_exports_only_manifest_and_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve() / "cfg-v4"
            manifest = export_rom_cfg_proven_roots_v4(ROOT, output)
            self.assertEqual(
                {"manifest.json", "rom-cfg-proven-roots-v4.json"},
                {path.name for path in output.iterdir()},
            )
            self.assertEqual("rom-cfg-proven-roots-v4", manifest["artifact_schema"])
            report = verify_rom_cfg_proven_roots_v4(ROOT, output)
            self.assertTrue(report["verified"], report)
            self.assertEqual(486, report["decoded_instruction_count"])
            self.assertEqual(118, report["decoded_basic_block_count"])
            self.assertEqual(1_044, report["reachable_instruction_bytes"])
            self.assertEqual(6, report["frontier_count"])
            self.assertEqual(29, report["baseline_cross_edge_count"])

    def test_independent_verifier_does_not_import_v4_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v4.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("export_rom_cfg_proven_roots_v4", source)

    def test_rejects_repository_root_as_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "repository root"):
            export_rom_cfg_proven_roots_v4(ROOT, ROOT)


if __name__ == "__main__":
    unittest.main()
