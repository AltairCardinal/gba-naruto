from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest

from tools.export_map_events_e4_handler_pixel_ab import export_artifact
from tools.verify_map_events_e4_handler_pixel_ab import verify_artifact


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/map-events-e4-handler-pixel-ab-v1"


class MapEventsE4HandlerPixelAbArtifactTests(unittest.TestCase):
    def _extract(self, destination: Path) -> Path:
        source = destination / "source"
        source.mkdir()
        with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
            archive.extractall(source, filter="data")
        return source

    def test_manifest_satisfies_promotion_policy(self):
        manifest = json.loads((ARTIFACT / "manifest.json").read_text())
        self.assertEqual(manifest["schema"], "git-artifact-promotion-v1")
        self.assertEqual(manifest["artifact_status"], "accepted")
        self.assertEqual(manifest["verifier"]["exit_code"], 0)

    def test_verifies_committed_artifact(self):
        result = verify_artifact(ROOT, ARTIFACT)
        self.assertTrue(result["verified"])
        self.assertEqual(result["entry_id"], 0xE4)
        self.assertEqual(result["changed_pixel_count"], 37436)

    def test_verifier_cli_runs_from_repository_root(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/verify_map_events_e4_handler_pixel_ab.py"),
                "--root",
                ".",
                "--artifact",
                str(ARTIFACT.relative_to(ROOT)),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_export_is_deterministic_from_raw_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = self._extract(temporary)
            output = temporary / "artifact"
            export_artifact(ROOT, source, output)
            for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar"):
                self.assertEqual(
                    hashlib.sha256((output / name).read_bytes()).hexdigest(),
                    hashlib.sha256((ARTIFACT / name).read_bytes()).hexdigest(),
                )

    def test_rejects_resigned_variant_rom_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = self._extract(temporary)
            build_path = source / "build/build-manifest.json"
            build = json.loads(build_path.read_text())
            build["variants"]["candidate"]["rom_sha256"] = "0" * 64
            build_path.write_text(json.dumps(build, indent=2, sort_keys=True) + "\n")
            audit_path = source / "runs/candidate/output/audit.json"
            audit = json.loads(audit_path.read_text())
            audit["rom_sha256"] = "0" * 64
            audit_path.write_text(json.dumps(audit, separators=(",", ":")))
            with self.assertRaisesRegex(ValueError, "ROM reconstruction mismatch"):
                export_artifact(ROOT, source, temporary / "forged")

    def test_rejects_resigned_runtime_tool_or_script_path(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = self._extract(temporary)
            audit_path = source / "runs/baseline/output/audit.json"
            audit = json.loads(audit_path.read_text())
            audit["script_sha256"] = "0" * 64
            audit_path.write_text(json.dumps(audit, separators=(",", ":")))
            with self.assertRaisesRegex(ValueError, "runtime tool hash mismatch"):
                export_artifact(ROOT, source, temporary / "forged-hash")

            second = temporary / "second"
            second.mkdir()
            source = self._extract(second)
            guard_path = source / "runs/baseline/guard-summary.json"
            guard = json.loads(guard_path.read_text())
            guard["command"][2] = "/tmp/mgba_map_events_e4_trace.lua"
            guard_path.write_text(json.dumps(guard, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "guard mismatch"):
                export_artifact(ROOT, source, temporary / "forged-path")

    def test_rejects_resigned_handler_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = self._extract(temporary)
            audit_path = source / "runs/baseline/output/audit.json"
            audit = json.loads(audit_path.read_text())
            audit["native_handler_seen"] = False
            audit["events"] = [
                event for event in audit["events"] if event["name"] != "native-group3-handler"
            ]
            audit_path.write_text(json.dumps(audit, separators=(",", ":")))
            with self.assertRaisesRegex(ValueError, "runtime chain mismatch"):
                export_artifact(ROOT, source, temporary / "forged")


if __name__ == "__main__":
    unittest.main()
