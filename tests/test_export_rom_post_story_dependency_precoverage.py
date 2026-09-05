"""TDD contract for the post-story-dependency immutable coverage baseline."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PostStoryDependencyPrecoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_post_story_dependency_precoverage as exporter

        cls.exporter = exporter

    def test_freezes_exact_authoritative_coverage_without_reconstruction(self) -> None:
        raw, source = self.exporter.build_snapshot(ROOT)
        self.assertEqual(31_378_342, len(raw))
        self.assertEqual(
            "2cc07bc74d24276b994219900ad7419787f9b8832dd62a66bb7839d09df42c01",
            hashlib.sha256(raw).hexdigest(),
        )
        coverage = json.loads(raw)
        self.assertEqual(
            (6_202_729, 88_727, 16_870, 18_641),
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

    def test_export_is_canonical_deterministic_exclusive_and_traversal_safe(self) -> None:
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as directory:
            base = Path(directory)
            output = base / "candidate"
            self.exporter.export_artifact(ROOT, output)
            self.assertEqual(
                {"manifest.json", "rom-byte-coverage.json.gz"},
                {path.name for path in output.iterdir()},
            )
            archive = (output / "rom-byte-coverage.json.gz").read_bytes()
            self.assertEqual(
                hashlib.sha256(
                    (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
                ).hexdigest(),
                hashlib.sha256(gzip.decompress(archive)).hexdigest(),
            )
            manifest_raw = (output / "manifest.json").read_bytes()
            manifest = json.loads(manifest_raw)
            self.assertEqual(
                (json.dumps(
                    manifest, ensure_ascii=False, indent=2, sort_keys=True
                ) + "\n").encode(),
                manifest_raw,
            )
            with self.assertRaises(FileExistsError):
                self.exporter.export_artifact(ROOT, output)
            escaped = base / "escaped"
            with self.assertRaises(ValueError):
                self.exporter.export_artifact(
                    ROOT, base / "unused" / ".." / "escaped" / "artifact")
            self.assertFalse(escaped.exists())


if __name__ == "__main__":
    unittest.main()
