from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.rebuild_battle_effect_frame_phase_artifacts import refresh_artifact


class RebuildBattleEffectFramePhaseArtifactsTests(unittest.TestCase):
    def test_cli_can_run_directly(self):
        result = subprocess.run(
            [
                sys.executable,
                str(
                    Path(__file__).resolve().parents[1]
                    / "tools/rebuild_battle_effect_frame_phase_artifacts.py"
                ),
                "--help",
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def _fixture(self, root: Path) -> Path:
        artifact = root / "artifacts/phase"
        (artifact / "raw/renderer-post").mkdir(parents=True)
        (artifact / "raw/renderer-post/capture.bin").write_bytes(b"raw")
        (artifact / "runtime-audit.json").write_text(
            json.dumps({"profile": str(root / "profiles/group.json")}) + "\n",
            encoding="utf-8",
        )
        (artifact / "guard-summary.json").write_text(
            json.dumps({"cwd": str(root)}) + "\n", encoding="utf-8"
        )
        profile = root / "profiles/group.json"
        profile.parent.mkdir(parents=True)
        profile.write_text("{}\n", encoding="utf-8")
        (artifact / "manifest.json").write_text(
            json.dumps({"profile": {"path": "profiles/group.json"}}) + "\n",
            encoding="utf-8",
        )
        return artifact

    def test_refresh_replaces_only_manifest_after_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            artifact = self._fixture(root)

            def exporter(source, guard, profile, target):
                self.assertEqual(
                    json.loads((source / "audit.json").read_text())["profile"],
                    str(root / "profiles/group.json"),
                )
                self.assertEqual(profile, root / "profiles/group.json")
                shutil.copytree(artifact, target)
                (target / "runtime-audit.json").write_text(
                    '{"profile": "profiles/group.json"}\n', encoding="utf-8"
                )
                (target / "guard-summary.json").write_text(
                    '{"cwd": "."}\n', encoding="utf-8"
                )
                (target / "manifest.json").write_text(
                    json.dumps(
                        {
                            "refreshed": True,
                            "verifier": {
                                "command": [
                                    "python3",
                                    "tools/verify_battle_effect_frame_phase.py",
                                    "--artifact",
                                    target.relative_to(root).as_posix(),
                                ]
                            },
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

            refresh_artifact(
                root,
                artifact,
                exporter=exporter,
                verifier=lambda target: {"errors": []},
            )
            refreshed = json.loads((artifact / "manifest.json").read_text())
            self.assertTrue(refreshed["refreshed"])
            self.assertEqual(
                refreshed["verifier"]["command"][-1],
                "artifacts/phase",
            )
            self.assertEqual(
                (artifact / "raw/renderer-post/capture.bin").read_bytes(), b"raw"
            )
            self.assertEqual(
                json.loads((artifact / "runtime-audit.json").read_text()),
                {"profile": "profiles/group.json"},
            )
            self.assertEqual(
                json.loads((artifact / "guard-summary.json").read_text()),
                {"cwd": "."},
            )

    def test_refresh_restores_manifest_when_verification_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            artifact = self._fixture(root)
            original = (artifact / "manifest.json").read_bytes()
            original_audit = (artifact / "runtime-audit.json").read_bytes()
            original_guard = (artifact / "guard-summary.json").read_bytes()

            def exporter(source, guard, profile, target):
                shutil.copytree(artifact, target)
                (target / "runtime-audit.json").write_text(
                    '{"profile": "profiles/group.json"}\n', encoding="utf-8"
                )
                (target / "guard-summary.json").write_text(
                    '{"cwd": "."}\n', encoding="utf-8"
                )
                (target / "manifest.json").write_text(
                    json.dumps(
                        {
                            "refreshed": True,
                            "verifier": {
                                "command": [
                                    "python3",
                                    "tools/verify_battle_effect_frame_phase.py",
                                    "--artifact",
                                    target.relative_to(root).as_posix(),
                                ]
                            },
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ValueError, "verification failed"):
                refresh_artifact(
                    root,
                    artifact,
                    exporter=exporter,
                    verifier=lambda target: {"errors": ["rejected"]},
                )
            self.assertEqual((artifact / "manifest.json").read_bytes(), original)
            self.assertEqual(
                (artifact / "runtime-audit.json").read_bytes(), original_audit
            )
            self.assertEqual(
                (artifact / "guard-summary.json").read_bytes(), original_guard
            )


if __name__ == "__main__":
    unittest.main()
