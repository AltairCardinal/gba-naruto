from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "build/experiments/active/scene-source-four-packet-tier2-20260905"


class SceneSourceFourPacketPrecoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools import export_rom_scene_source_four_packet_precoverage as E
        cls.E = E

    def test_replays_exact_immutable_precoverage_identity(self):
        artifact = ROOT / "artifacts/rom-scene-source-four-packet-precoverage-v1"
        self.assertEqual(
            {"manifest.json", "rom-byte-coverage.json.gz"},
            {path.name for path in artifact.iterdir()},
        )
        manifest_raw = (artifact / "manifest.json").read_bytes()
        self.assertEqual(
            "b3aaeca20cb2fb6c9c3345d2bb79cb1c2be2672788993661339e45ad5010220a",
            hashlib.sha256(manifest_raw).hexdigest(),
        )
        manifest = json.loads(manifest_raw)
        self.assertEqual(
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
            manifest_raw,
        )
        archive = (artifact / "rom-byte-coverage.json.gz").read_bytes()
        self.assertEqual(1_722_453, len(archive))
        self.assertEqual(
            "9b1d55e79921dcac25718368cf80419be39f84b8db4c615f429091e7b6e625ff",
            hashlib.sha256(archive).hexdigest(),
        )
        raw = gzip.decompress(archive)
        self.assertEqual(30_889_492, len(raw))
        self.assertEqual(
            "ae7c69330285bd3d668612b057a793f1b98edda5e0df421a8bda6f5e90290024",
            hashlib.sha256(raw).hexdigest(),
        )
        coverage = json.loads(raw)
        self.assertEqual(
            (6_194_116, 97_340, 16_652, 18_332),
            tuple(coverage["summary"][key] for key in (
                "classified_bytes", "unknown_bytes", "claim_count",
                "segment_count",
            )),
        )
        source = manifest["recovery"]["source"]
        self.assertEqual(
            {
                "path": "sequel/rom-byte-coverage.json",
                "sha256": "9bab52d3d4b34490bf0699a2994294c73770bdcdfea1775cbd1d12dc48893fb4",
                "size": 31_201_261,
                "removed_batches": {
                    "rom-fixed-pair-tables-v1": {"bytes": 42, "claim_count": 2},
                    "rom-prebattle-menu-controller-cfg-v1": {"bytes": 1_920, "claim_count": 52},
                    "rom-scene-source-closures-v1": {"bytes": 1_015, "claim_count": 73},
                    "rom-v17-v18-helper-cfg-v1": {"bytes": 1_254, "claim_count": 14},
                },
                "removed_bytes": 4_231,
                "removed_claim_count": 141,
            },
            source,
        )

    def test_historical_builder_fails_closed_after_live_coverage_advances(self):
        with tempfile.TemporaryDirectory(dir=RUN) as raw:
            root = Path(raw)
            (root / "sequel").mkdir()
            (root / "sequel/rom-byte-coverage.json").write_text("{}\n")
            (root / self.E.EXPERIMENT_ROOT).mkdir(parents=True)
            output = root / self.E.OFFICIAL_ARTIFACT
            with self.assertRaisesRegex(
                ValueError, "post-batch coverage identity changed"
            ):
                self.E.export_artifact(root, output)
            self.assertFalse(output.exists())

    def test_exclusive_publish_refuses_an_existing_target(self):
        with tempfile.TemporaryDirectory(dir=RUN) as raw:
            directory = Path(raw)
            source = directory / "source"
            destination = directory / "destination"
            source.mkdir()
            destination.mkdir()
            with self.assertRaises(FileExistsError):
                self.E._publish_exclusive(source, destination)
            self.assertTrue(source.is_dir())
            self.assertTrue(destination.is_dir())


if __name__ == "__main__":
    unittest.main()
