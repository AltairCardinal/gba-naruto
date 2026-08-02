from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


class RebuildBattleEffectPixelAbArtifactsTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        artifact = root / "artifacts/pixel"
        (artifact / "raw").mkdir(parents=True)
        (artifact / "raw/capture.bin").write_bytes(b"raw")
        (artifact / "runtime-evidence.json").write_text("{}\n", encoding="utf-8")
        (artifact / "baseline.png").write_bytes(b"baseline")
        profile = root / "profiles/group.json"
        profile.parent.mkdir(parents=True)
        profile.write_text("{}\n", encoding="utf-8")
        (artifact / "manifest.json").write_text(
            json.dumps({"profile": "profiles/group.json"}) + "\n",
            encoding="utf-8",
        )
        return artifact

    def test_refresh_replaces_only_manifest_after_verification(self):
        from tools.rebuild_battle_effect_pixel_ab_artifacts import refresh_artifact

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            artifact = self._fixture(root)

            def exporter(repo, profile, raw, target):
                self.assertEqual(repo, root)
                self.assertEqual(profile, root / "profiles/group.json")
                shutil.copytree(artifact, target)
                (target / "manifest.json").write_text(
                    '{"refreshed": true}\n', encoding="utf-8"
                )

            refresh_artifact(
                root,
                artifact,
                exporter=exporter,
                verifier=lambda repo, target: {"errors": [], "verified": True},
            )
            self.assertEqual(
                json.loads((artifact / "manifest.json").read_text()),
                {"refreshed": True},
            )
            self.assertEqual((artifact / "raw/capture.bin").read_bytes(), b"raw")

    def test_refresh_restores_manifest_when_verification_fails(self):
        from tools.rebuild_battle_effect_pixel_ab_artifacts import refresh_artifact

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            artifact = self._fixture(root)
            original = (artifact / "manifest.json").read_bytes()

            def exporter(repo, profile, raw, target):
                shutil.copytree(artifact, target)
                (target / "manifest.json").write_text(
                    '{"refreshed": true}\n', encoding="utf-8"
                )

            with self.assertRaisesRegex(ValueError, "verification failed"):
                refresh_artifact(
                    root,
                    artifact,
                    exporter=exporter,
                    verifier=lambda repo, target: {
                        "errors": ["rejected"],
                        "verified": False,
                    },
                )
            self.assertEqual((artifact / "manifest.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
