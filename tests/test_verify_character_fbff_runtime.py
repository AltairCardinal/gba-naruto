import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "verify_character_fbff_runtime.py"
ARTIFACT = ROOT / "artifacts" / "character-fbff-runtime-v1"


class VerifyCharacterFbffRuntimeTests(unittest.TestCase):
    def run_verifier(self, artifact: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(ROOT),
                "--artifact-dir",
                str(artifact),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_accepts_the_committed_runtime_ab_evidence(self):
        completed = self.run_verifier(ARTIFACT)

        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual("character-fbff-runtime-verification-v1", report["schema"])
        self.assertTrue(report["success"])
        self.assertEqual([], report["errors"])
        self.assertEqual("renderer_continues_past_fbff", report["base_outcome"])
        self.assertEqual("renderer_stops_at_ffff", report["control_outcome"])

    def test_rejects_a_tampered_renderer_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            trace = artifact / "base" / "renderer-loop.json"
            payload = json.loads(trace.read_text(encoding="utf-8"))
            payload["hits"][1]["pointer"] = "0x0825A8FC"
            trace.write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )

            completed = self.run_verifier(artifact)

        self.assertNotEqual(0, completed.returncode)
        report = json.loads(completed.stdout)
        self.assertFalse(report["success"])
        self.assertTrue(
            any("base renderer trace" in error for error in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
