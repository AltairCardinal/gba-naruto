from pathlib import Path
import hashlib
import json
import shutil
import tarfile
import tempfile
import unittest

from PIL import Image

from tools.export_tile_asset_descriptor_pixel_ab import _write_raw_tar, export_artifact
from tools.verify_tile_asset_descriptor_pixel_ab import _pixel_facts, verify_artifact


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/tile-asset-descriptor2-pixel-ab-v1"


class TileAssetDescriptorPixelAbArtifactTests(unittest.TestCase):
    def test_manifest_satisfies_promotion_policy(self):
        manifest = json.loads((ARTIFACT / "manifest.json").read_text())
        self.assertEqual(manifest["schema"], "git-artifact-promotion-v1")
        self.assertEqual(manifest["artifact_schema"], "tile-asset-descriptor-pixel-ab-artifact-v1")
        self.assertEqual(manifest["artifact_status"], "accepted")
        self.assertEqual(manifest["verifier"]["exit_code"], 0)

    def test_verifies_committed_artifact(self):
        result = verify_artifact(ROOT, ARTIFACT)
        self.assertTrue(result["verified"])
        self.assertEqual(result["descriptor_id"], 2)
        self.assertEqual(result["changed_pixel_count"], 38400)

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

    def test_rejects_resigned_pixel_count_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "evidence.json"
            evidence = json.loads(evidence_path.read_text())
            evidence["pixels"]["changed_pixel_count"] = 1
            evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(ValueError, "pixel difference"):
                verify_artifact(ROOT, copied)

    def test_rejects_resigned_runtime_png_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "source"
            source.mkdir()
            with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
                archive.extractall(source, filter="data")
            candidate_path = source / "runs/candidate/final.png"
            with Image.open(candidate_path) as original:
                candidate = original.convert("RGB")
            with Image.open(source / "runs/baseline/final.png") as original:
                baseline_pixel = original.convert("RGB").getpixel((0, 0))
            before = candidate.getpixel((0, 0))
            replacement = ((before[0] + 1) % 256, before[1], before[2])
            if replacement == baseline_pixel:
                replacement = (before[0], (before[1] + 1) % 256, before[2])
            candidate.putpixel((0, 0), replacement)
            candidate.save(candidate_path, optimize=False)

            with self.assertRaisesRegex(ValueError, "savestate screenshot mismatch"):
                export_artifact(ROOT, source, temporary / "forged")

    def test_verifier_rejects_resigned_runtime_png_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            forged = temporary / "artifact"
            shutil.copytree(ARTIFACT, forged)
            source = temporary / "source"
            source.mkdir()
            with tarfile.open(forged / "raw.tar", "r") as archive:
                archive.extractall(source, filter="data")
            candidate_path = source / "runs/candidate/final.png"
            with Image.open(candidate_path) as original:
                candidate = original.convert("RGB")
            with Image.open(source / "runs/baseline/final.png") as original:
                baseline_pixel = original.convert("RGB").getpixel((0, 0))
            before = candidate.getpixel((0, 0))
            replacement = ((before[0] + 1) % 256, before[1], before[2])
            if replacement == baseline_pixel:
                replacement = (before[0], (before[1] + 1) % 256, before[2])
            candidate.putpixel((0, 0), replacement)
            candidate.save(candidate_path, optimize=False)
            shutil.copyfile(candidate_path, forged / "candidate.png")

            evidence_path = forged / "evidence.json"
            evidence = json.loads(evidence_path.read_text())
            evidence["runs"]["candidate"]["png_sha256"] = hashlib.sha256(
                candidate_path.read_bytes()
            ).hexdigest()
            evidence["pixels"] = _pixel_facts(
                source / "runs/baseline/final.png", candidate_path
            )
            evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
            _write_raw_tar(source, forged / "raw.tar")

            manifest_path = forged / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            for name in manifest["implementation"]:
                manifest["implementation"][name] = hashlib.sha256(
                    (ROOT / name).read_bytes()
                ).hexdigest()
            for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar"):
                manifest["files"][name] = hashlib.sha256((forged / name).read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

            with self.assertRaisesRegex(ValueError, "savestate screenshot mismatch"):
                verify_artifact(ROOT, forged)


if __name__ == "__main__":
    unittest.main()
