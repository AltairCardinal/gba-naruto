import gzip
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FastAuditFourPacketReplayTests(unittest.TestCase):
    def test_cli_runs_under_formal_proof_isolation_flags(self):
        completed = subprocess.run(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_fast_audit_four_packet_coverage.py",
                "--root",
                ".",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["verified"])

    def test_replays_all_four_frozen_verifiers_after_canonical_coverage_advances(self):
        from tools.verify_rom_fast_audit_four_packet_coverage import verify

        report = verify(ROOT)
        self.assertTrue(report["verified"], report)
        self.assertEqual([], report["errors"])
        self.assertEqual(4, report["packet_count"])
        self.assertEqual(7_140, report["promotion_bytes"])
        self.assertEqual(116, report["promotion_claim_count"])
        self.assertEqual(
            "064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa",
            report["baseline_coverage_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
            ).hexdigest(),
            report["canonical_coverage_sha256"],
        )
        self.assertEqual(
            {
                "rom-event-handler-cfg-v1",
                "rom-sprite-component-source-v1",
                "rom-cfg-proven-roots-v16",
                "rom-cfg-proven-roots-v16-consumed-literals-v1",
            },
            set(report["packets"]),
        )
        self.assertTrue(all(row["verified"] for row in report["packets"].values()))

    def test_frozen_baseline_archive_is_exact_and_tamper_evident(self):
        archive = ROOT / "artifacts/rom-fast-audit-four-packet-baseline-v1/rom-byte-coverage.json.gz"
        raw = gzip.decompress(archive.read_bytes())
        self.assertEqual(
            "064370aa0eca861d99d96e4ee15be4b50c569bea86c67a279d4084517e543baa",
            hashlib.sha256(raw).hexdigest(),
        )
        baseline = json.loads(raw)
        self.assertEqual(6_144_296, baseline["summary"]["classified_bytes"])
        self.assertEqual(147_160, baseline["summary"]["unknown_bytes"])


if __name__ == "__main__":
    unittest.main()
