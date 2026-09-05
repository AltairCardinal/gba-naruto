"""TDD contract for the immutable story-callback precoverage baseline."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StoryCallbackDependencyPrecoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_story_callback_dependency_precoverage as exporter

        cls.exporter = exporter

    def test_freezes_exact_current_coverage_without_reconstruction(self) -> None:
        raw, source = self.exporter.build_snapshot(ROOT)
        self.assertEqual(31_201_261, len(raw))
        self.assertEqual(
            "b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82",
            hashlib.sha256(raw).hexdigest(),
        )
        coverage = json.loads(raw)
        self.assertEqual(
            (6_198_347, 93_109, 16_793, 18_552),
            tuple(coverage["summary"][key] for key in (
                "classified_bytes", "unknown_bytes", "claim_count", "segment_count",
            )),
        )
        self.assertEqual(
            {
                "path": "sequel/rom-byte-coverage.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
            },
            source,
        )

    def test_export_is_canonical_deterministic_and_exclusive(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "build/experiments") as directory:
            output = Path(directory) / "candidate"
            self.exporter.export_artifact(ROOT, output)
            self.assertEqual(
                {"manifest.json", "rom-byte-coverage.json.gz"},
                {path.name for path in output.iterdir()},
            )
            archive = (output / "rom-byte-coverage.json.gz").read_bytes()
            self.assertEqual(
                hashlib.sha256((ROOT / "sequel/rom-byte-coverage.json").read_bytes()).hexdigest(),
                hashlib.sha256(gzip.decompress(archive)).hexdigest(),
            )
            manifest_raw = (output / "manifest.json").read_bytes()
            manifest = json.loads(manifest_raw)
            self.assertEqual(
                (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
                manifest_raw,
            )
            self.assertEqual(
                "rom-byte-coverage-prepromotion-baseline-v1",
                manifest["schema"],
            )
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, output)


if __name__ == "__main__":
    unittest.main()
