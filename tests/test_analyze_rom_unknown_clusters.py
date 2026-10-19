import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AnalyzeRomUnknownClustersTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        rom_path = root / "base.gba"
        coverage_path = root / "coverage.json"
        rom_path.write_bytes(bytes([9, 9, 0, 1, 0, 1, 8, 8, 7, 7, 0, 1, 0, 1, 6, 6]))
        coverage_path.write_text(
            json.dumps(
                {
                    "schema": "rom-byte-coverage-v1",
                    "summary": {
                        "rom_bytes": 16,
                        "classified_bytes": 8,
                        "unknown_bytes": 8,
                    },
                    "segments": [
                        {"range": [0, 2], "primary_class": "left_owner"},
                        {"range": [2, 6], "primary_class": "unknown"},
                        {"range": [6, 8], "primary_class": "right_owner"},
                        {"range": [8, 10], "primary_class": "left_owner"},
                        {"range": [10, 14], "primary_class": "unknown"},
                        {"range": [14, 16], "primary_class": "right_owner"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return rom_path, coverage_path

    def test_cli_groups_unknown_ranges_without_making_semantic_claims(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rom_path, coverage_path = self._fixture(Path(td))
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/analyze_rom_unknown_clusters.py"),
                    "--rom",
                    str(rom_path),
                    "--coverage",
                    str(coverage_path),
                    "--top",
                    "10",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)

        self.assertEqual("rom-unknown-cluster-analysis-v1", report["schema"])
        self.assertEqual(
            {"rom_bytes": 16, "unknown_bytes": 8, "unknown_range_count": 2},
            report["summary"],
        )
        self.assertEqual(
            {
                "left_primary_class": "left_owner",
                "right_primary_class": "right_owner",
                "range_count": 2,
                "total_bytes": 8,
                "max_range_bytes": 4,
            },
            report["adjacency_families"][0],
        )
        self.assertEqual(2, report["length_buckets"]["4-15"]["range_count"])
        self.assertEqual(8, report["length_buckets"]["4-15"]["total_bytes"])
        self.assertEqual([2, 6], report["largest_ranges"][0]["range"])
        self.assertEqual(2, report["largest_ranges"][0]["distinct_byte_count"])
        self.assertNotIn("semantic_class", report["largest_ranges"][0])
        self.assertEqual(
            "Candidate ranking only; adjacency and byte patterns are not semantic evidence.",
            report["scope"],
        )

    def test_cli_fails_closed_when_coverage_summary_does_not_match_segments(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rom_path, coverage_path = self._fixture(Path(td))
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            coverage["summary"]["unknown_bytes"] = 7
            coverage_path.write_text(json.dumps(coverage), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/analyze_rom_unknown_clusters.py"),
                    "--rom",
                    str(rom_path),
                    "--coverage",
                    str(coverage_path),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("unknown byte total does not match coverage summary", result.stderr)


if __name__ == "__main__":
    unittest.main()
