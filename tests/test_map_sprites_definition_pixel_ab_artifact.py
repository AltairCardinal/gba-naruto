from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

from PIL import Image

from tools.export_map_sprites_definition_pixel_ab import export_artifact
from tools.verify_map_sprites_definition_pixel_ab import verify_artifact


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/map-sprites-definition-id1-pixel-ab-v1"


class MapSpritesDefinitionPixelAbArtifactTests(unittest.TestCase):
    def test_manifest_satisfies_promotion_policy(self):
        manifest = json.loads((ARTIFACT / "manifest.json").read_text())
        self.assertEqual(manifest["schema"], "git-artifact-promotion-v1")
        self.assertEqual(
            manifest["artifact_schema"],
            "map-sprites-definition-pixel-ab-artifact-v1",
        )
        self.assertEqual(manifest["artifact_status"], "accepted")
        self.assertEqual(manifest["verifier"]["exit_code"], 0)

    def test_verifies_committed_artifact(self):
        result = verify_artifact(ROOT, ARTIFACT)
        self.assertTrue(result["verified"])
        self.assertEqual(result["entry_id"], 1)
        self.assertEqual(result["changed_pixel_count"], 213)

    def test_verifier_cli_runs_from_repository_root(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/verify_map_sprites_definition_pixel_ab.py"),
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
            source = temporary / "source"
            source.mkdir()
            with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
                archive.extractall(source, filter="data")
            output = temporary / "artifact"
            export_artifact(ROOT, source, output)
            for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar"):
                self.assertEqual(
                    hashlib.sha256((output / name).read_bytes()).hexdigest(),
                    hashlib.sha256((ARTIFACT / name).read_bytes()).hexdigest(),
                )

    def test_rejects_resigned_runtime_png_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "source"
            source.mkdir()
            with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
                archive.extractall(source, filter="data")
            candidate_path = source / "runs/candidate/output/final.png"
            with Image.open(candidate_path) as original:
                candidate = original.convert("RGB")
            before = candidate.getpixel((0, 0))
            candidate.putpixel((0, 0), ((before[0] + 1) % 256, before[1], before[2]))
            candidate.save(candidate_path, optimize=False)
            with self.assertRaisesRegex(ValueError, "savestate screenshot mismatch"):
                export_artifact(ROOT, source, temporary / "forged")

    def test_rejects_a_stale_or_resigned_source_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "source"
            source.mkdir()
            with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
                archive.extractall(source, filter="data")
            build_path = source / "build/build-manifest.json"
            build = json.loads(build_path.read_text())
            build["source_bank_sha256"] = "0" * 64
            build_path.write_text(json.dumps(build, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "source contract mismatch"):
                export_artifact(ROOT, source, temporary / "forged")

    def test_rejects_resigned_variant_rom_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "source"
            source.mkdir()
            with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
                archive.extractall(source, filter="data")
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

    def test_rejects_resigned_runtime_tool_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "source"
            source.mkdir()
            with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
                archive.extractall(source, filter="data")
            audit_path = source / "runs/baseline/output/audit.json"
            audit = json.loads(audit_path.read_text())
            audit["script_sha256"] = "0" * 64
            audit["binary_sha256"] = "0" * 64
            audit_path.write_text(json.dumps(audit, separators=(",", ":")))
            with self.assertRaisesRegex(ValueError, "runtime tool hash mismatch"):
                export_artifact(ROOT, source, temporary / "forged")

    def test_rejects_same_named_script_from_another_path(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "source"
            source.mkdir()
            with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
                archive.extractall(source, filter="data")
            guard_path = source / "runs/baseline/guard-summary.json"
            guard = json.loads(guard_path.read_text())
            guard["command"][2] = "/tmp/mgba_map_sprites_trace.lua"
            guard_path.write_text(json.dumps(guard, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "guard mismatch"):
                export_artifact(ROOT, source, temporary / "forged")


if __name__ == "__main__":
    unittest.main()
