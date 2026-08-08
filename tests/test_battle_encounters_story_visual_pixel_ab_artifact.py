from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-encounters-story-visual-pixel-ab-v1"


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _resign_evidence(artifact: Path, mutate) -> None:
    evidence_path = artifact / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    mutate(evidence)
    _write_json(evidence_path, evidence)
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["evidence.json"] = hashlib.sha256(
        evidence_path.read_bytes()
    ).hexdigest()
    for relative in (
        "tests/test_battle_encounters_story_visual_pixel_ab_artifact.py",
        "tools/verify_battle_encounters_story_visual_pixel_ab.py",
    ):
        manifest["implementation"][relative] = hashlib.sha256(
            (ROOT / relative).read_bytes()
        ).hexdigest()
    _write_json(manifest_path, manifest)


def _resign_launch_identity(artifact: Path, mutate) -> None:
    raw_path = artifact / "raw.tar"
    temporary = artifact / "raw-updated.tar"
    with tarfile.open(raw_path, "r") as source, tarfile.open(
        temporary, "w", format=tarfile.USTAR_FORMAT
    ) as output:
        for member in source.getmembers():
            stream = source.extractfile(member)
            if stream is None:
                raise AssertionError(f"raw member is not a file: {member.name}")
            payload = stream.read()
            if member.name == "launch-identity.json":
                identity = json.loads(payload)
                mutate(identity)
                payload = (
                    json.dumps(
                        identity, ensure_ascii=False, indent=2, sort_keys=True
                    )
                    + "\n"
                ).encode("utf-8")
                member.size = len(payload)
            output.addfile(member, io.BytesIO(payload))
    temporary.replace(raw_path)
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["raw.tar"] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    for relative in (
        "tests/test_battle_encounters_story_visual_pixel_ab_artifact.py",
        "tools/verify_battle_encounters_story_visual_pixel_ab.py",
    ):
        manifest["implementation"][relative] = hashlib.sha256(
            (ROOT / relative).read_bytes()
        ).hexdigest()
    _write_json(manifest_path, manifest)


class BattleEncountersStoryVisualPixelAbArtifactTests(unittest.TestCase):
    def test_committed_artifact_verifies(self):
        from tools.verify_battle_encounters_story_visual_pixel_ab import verify_artifact

        result = verify_artifact(ROOT, ARTIFACT)
        self.assertTrue(result["verified"])
        self.assertEqual(1603, result["changed_pixel_count"])
        manifest = json.loads((ARTIFACT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [
                "python3",
                "tools/verify_battle_encounters_story_visual_pixel_ab.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/battle-encounters-story-visual-pixel-ab-v1",
            ],
            manifest["verifier"]["command"],
        )

    def test_rejects_resigned_runtime_identity_claim(self):
        from tools.verify_battle_encounters_story_visual_pixel_ab import verify_artifact

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            _resign_evidence(
                artifact,
                lambda value: value["emulator"].__setitem__(
                    "source_commit", "0000000000000000000000000000000000000000"
                ),
            )
            with self.assertRaisesRegex(ValueError, "emulator identity"):
                verify_artifact(ROOT, artifact)

    def test_rejects_resigned_pointer_claim(self):
        from tools.verify_battle_encounters_story_visual_pixel_ab import verify_artifact

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            _resign_evidence(
                artifact,
                lambda value: value["edit"].__setitem__(
                    "after_pointer", "0x08130F50"
                ),
            )
            with self.assertRaisesRegex(ValueError, "edit contract"):
                verify_artifact(ROOT, artifact)

    def test_rejects_resigned_boundary_expansion(self):
        from tools.verify_battle_encounters_story_visual_pixel_ab import verify_artifact

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            _resign_evidence(
                artifact,
                lambda value: value["boundary"].__setitem__(
                    "natural_scenario_53_navigation", True
                ),
            )
            with self.assertRaisesRegex(ValueError, "evidence mismatch"):
                verify_artifact(ROOT, artifact)

    def test_artifact_emulator_identity_is_path_portable(self):
        evidence = json.loads((ARTIFACT / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "source_commit",
                "binary_sha256",
                "launch_identity",
                "script_path",
                "script_sha256",
            },
            set(evidence["emulator"]),
        )
        self.assertEqual(
            "tools/mgba_battle_encounters_story_visual_trace.lua",
            evidence["emulator"]["script_path"],
        )

    def test_raw_launch_identity_binds_runtime_binary_and_guards(self):
        with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
            member = archive.extractfile("launch-identity.json")
            self.assertIsNotNone(member)
            identity = json.loads(member.read())
        self.assertEqual("battle-encounters-launch-identity-v1", identity["schema"])
        self.assertEqual(
            "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b",
            identity["binary"]["sha256"],
        )
        self.assertEqual({"baseline", "candidate"}, set(identity["guards"]))
        for guard in identity["guards"].values():
            self.assertEqual(64, len(guard["guard_sha256"]))
            self.assertEqual(64, len(guard["binary_command_path_sha256"]))

    def test_rejects_resigned_raw_launch_identity(self):
        from tools.verify_battle_encounters_story_visual_pixel_ab import verify_artifact

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            _resign_launch_identity(
                artifact,
                lambda value: value["binary"].__setitem__("sha256", "0" * 64),
            )
            with self.assertRaisesRegex(ValueError, "launch identity mismatch"):
                verify_artifact(ROOT, artifact)

    def test_rejects_missing_implementation_binding(self):
        from tools.verify_battle_encounters_story_visual_pixel_ab import verify_artifact

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            relative = "tests/test_battle_encounters_story_visual_pixel_ab_artifact.py"
            manifest["implementation"][relative] = hashlib.sha256(
                (ROOT / relative).read_bytes()
            ).hexdigest()
            manifest["implementation"].pop(
                "tools/verify_battle_encounters_story_visual_pixel_ab.py"
            )
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "implementation file set"):
                verify_artifact(ROOT, artifact)


if __name__ == "__main__":
    unittest.main()
