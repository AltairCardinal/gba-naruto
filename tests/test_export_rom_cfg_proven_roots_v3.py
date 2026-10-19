#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

from tools.export_rom_cfg_proven_roots_v3 import (
    _producer_denominator,
    _root_seeds,
    build_cfg_proven_roots_v3_payload,
    export_rom_cfg_proven_roots_v3,
)
from tools.verify_rom_cfg_proven_roots_v3 import (
    verify_rom_cfg_proven_roots_v3,
)


ROOT = Path(__file__).resolve().parents[1]


class RomCfgProvenRootsV3ProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_full_rom_scan_finds_exact_two_producers_for_070df8(self) -> None:
        denominator = _producer_denominator(self.rom)
        self.assertEqual(
            [(0x74192, 0x70DF8), (0x74836, 0x70DF8)],
            [
                (item["file_offset"], item["target_file_offset"])
                for item in denominator["producers"]
            ],
        )
        self.assertEqual(2, denominator["scan"]["matching_producer_count"])

    def test_producer_denominator_fails_closed_on_each_callsite(self) -> None:
        for offset in (0x74192, 0x74836):
            with self.subTest(offset=offset):
                tampered = bytearray(self.rom)
                tampered[offset] ^= 1
                with self.assertRaisesRegex(
                    ValueError, "producer denominator changed"
                ):
                    _producer_denominator(bytes(tampered))

    def test_root_seed_is_bound_to_both_producers(self) -> None:
        roots = _root_seeds(self.rom)
        self.assertEqual([0x70DF8], [item["file_offset"] for item in roots])
        self.assertEqual(
            ["target_confirmation", "technique_menu"],
            [source["producer_id"] for source in roots[0]["sources"]],
        )


class RomCfgProvenRootsV3IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_cfg_proven_roots_v3_payload(ROOT)

    def test_freezes_every_prior_cfg_artifact_as_opaque_baseline(self) -> None:
        self.assertEqual(
            {
                "battle_controller",
                "proven_roots_v1",
                "proven_roots_v2",
                "v2",
                "v3",
            },
            set(self.payload["frozen_baseline"]),
        )

    def test_builds_nonempty_one_root_delta_without_baseline_overlap(self) -> None:
        self.assertEqual("rom-cfg-proven-roots-v3", self.payload["schema"])
        self.assertEqual(1, len(self.payload["roots"]))
        summary = self.payload["extension"]["summary"]
        self.assertGreater(summary["decoded_instruction_count"], 0)
        self.assertGreater(summary["decoded_basic_block_count"], 0)
        self.assertGreater(summary["reachable_instruction_bytes"], 0)
        self.assertFalse(self.payload["scope"]["runtime_reachability_complete"])

    def test_freezes_exact_closed_denominator(self) -> None:
        self.assertEqual(
            {
                "decoded_basic_block_count": 8,
                "decoded_instruction_count": 52,
                "frontier_count": 0,
                "frontier_reasons": {},
                "reachable_instruction_bytes": 110,
            },
            self.payload["extension"]["summary"],
        )
        self.assertEqual(5, len(self.payload["extension"]["baseline_cross_edges"]))


class RomCfgProvenRootsV3ArtifactTests(unittest.TestCase):
    def _tampered_artifact(self, tmp: str, mutate) -> Path:
        output = Path(tmp).resolve() / "cfg-v3"
        export_rom_cfg_proven_roots_v3(ROOT, output)
        payload_path = output / "rom-cfg-proven-roots-v3.json"
        payload = json.loads(payload_path.read_text())
        mutate(payload)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload_path.write_bytes(raw)
        manifest = json.loads((output / "manifest.json").read_text())
        manifest["rom"] = payload["rom"]
        manifest["files"]["rom-cfg-proven-roots-v3.json"] = {
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
            self.assertFalse(verify_rom_cfg_proven_roots_v3(ROOT, output)["verified"])

    def test_rejects_tampered_scope_with_rebuilt_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self._tampered_artifact(
                tmp,
                lambda payload: payload["scope"].__setitem__(
                    "runtime_reachability_complete", True
                ),
            )
            self.assertFalse(verify_rom_cfg_proven_roots_v3(ROOT, output)["verified"])

    def test_verifier_cli_accepts_repository_artifact(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "tools/verify_rom_cfg_proven_roots_v3.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v3",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_exports_only_manifest_and_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve() / "cfg-v3"
            manifest = export_rom_cfg_proven_roots_v3(ROOT, output)
            self.assertEqual(
                {"manifest.json", "rom-cfg-proven-roots-v3.json"},
                {path.name for path in output.iterdir()},
            )
            self.assertEqual("rom-cfg-proven-roots-v3", manifest["artifact_schema"])
            report = verify_rom_cfg_proven_roots_v3(ROOT, output)
            self.assertEqual(True, report.get("verified"), report)
            self.assertEqual([], report.get("errors"), report)
            self.assertEqual(52, report.get("decoded_instruction_count"))
            self.assertEqual(8, report.get("decoded_basic_block_count"))
            self.assertEqual(110, report.get("reachable_instruction_bytes"))
            self.assertEqual(0, report.get("frontier_count"))
            self.assertEqual(5, report.get("baseline_cross_edge_count"))

    def test_independent_verifier_does_not_import_v3_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v3.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("export_rom_cfg_proven_roots_v3", source)

    def test_rejects_repository_root_as_output(self) -> None:
        with self.assertRaisesRegex(ValueError, "repository root"):
            export_rom_cfg_proven_roots_v3(ROOT, ROOT)


if __name__ == "__main__":
    unittest.main()
