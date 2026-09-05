"""Independent-verifier contract tests for the sprite-loader tail packet."""

from __future__ import annotations

import hashlib
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-sprite-loader-tail-v1"
PAYLOAD_NAME = "rom-sprite-loader-tail.json"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


POST_PROMOTIONS = (
    (0x08B19E, 0x08B1B6, "profile-pointer-selector", "rom-profile-selector-code-slices-v1"),
    (0x08D1A4, 0x08D230, "profile-line-wrapper", "rom-profile-selector-code-slices-v1"),
    (0x08F594, 0x08F5D4, "chapter-root-table-selector", "rom-chapter-selector-code-slice-v1"),
    (0x080B58, 0x080B7C, "generic-sprite-loader-terminal-tail", SCHEMA),
    (0x07A34C, 0x07AA8C, "battle-status-bar-generator-caller", "rom-battle-status-bar-caller-slice-v1"),
)


def _post_coverage() -> bytes:
    return (ROOT / "sequel/rom-byte-coverage.json").read_bytes()


class VerifyRomSpriteLoaderTailTests(unittest.TestCase):
    def test_isolated_cli_regression_is_present_and_passes(self) -> None:
        verifier_path = ROOT / "tools/verify_rom_sprite_loader_tail.py"
        self.assertTrue(verifier_path.is_file())
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                str(verifier_path),
                "--root",
                str(ROOT),
                "--artifact-dir",
                str(ROOT / "artifacts" / SCHEMA),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(report["range_count"], 1)
        self.assertEqual(report["bytes"], 36)

    def test_missing_artifact_and_source_contract_fail_closed(self) -> None:
        from tools import verify_rom_sprite_loader_tail as verifier

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            report = verifier.verify_artifact(root, root / "artifact")
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_rehashed_payload_and_manifest_mutations_are_rejected(self) -> None:
        from tools import verify_rom_sprite_loader_tail as verifier

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary).resolve() / SCHEMA
            shutil.copytree(ROOT / "artifacts" / SCHEMA, artifact)
            payload_path = artifact / PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["packed_bytes"] = "00" * 36
            payload_path.write_bytes(_canonical(payload))
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][PAYLOAD_NAME] = _sha(payload_path.read_bytes())
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

            manifest_tamper = artifact.parent / "manifest-tamper"
            shutil.copytree(ROOT / "artifacts" / SCHEMA, manifest_tamper)
            tampered_manifest_path = manifest_tamper / "manifest.json"
            tampered_manifest = json.loads(tampered_manifest_path.read_text())
            tampered_manifest["coverage"]["sha256"] = "0" * 64
            tampered_manifest_path.write_bytes(_canonical(tampered_manifest))
            self.assertFalse(verifier.verify_artifact(ROOT, manifest_tamper)["verified"])

    def test_range_and_coverage_identity_mutations_are_rejected(self) -> None:
        from tools import verify_rom_sprite_loader_tail as verifier

        payload, packed = verifier.rebuild_payload(ROOT)
        mutated_payload = json.loads(json.dumps(payload))
        mutated_payload["range"]["range"][0] += 1
        with self.assertRaises(ValueError):
            verifier.verify_rebuilt_payload(ROOT, mutated_payload, packed)

        coverage = bytearray((ROOT / "sequel/rom-byte-coverage.json").read_bytes())
        coverage[100] ^= 1
        with self.assertRaises(ValueError):
            verifier.rebuild_payload(ROOT, coverage=bytes(coverage))

    def test_post_promotion_fixture_and_mutations_are_fail_closed(self) -> None:
        from tools import verify_rom_sprite_loader_tail as verifier

        post_raw = _post_coverage()
        post = json.loads(post_raw)
        payload, _packed = verifier.rebuild_payload(ROOT, coverage=post_raw)
        self.assertEqual(payload["coverage"]["sha256"], verifier.COVERAGE_SHA256)
        report = verifier.verify_artifact(ROOT, ROOT / "artifacts" / SCHEMA, coverage=post_raw)
        self.assertTrue(report["verified"], report["errors"])
        mutations = []
        wrong_summary = copy.deepcopy(post)
        wrong_summary["summary"]["segment_count"] -= 1
        mutations.append(wrong_summary)
        wrong_owner = copy.deepcopy(post)
        owned = next(item for item in wrong_owner["segments"] if item["range"] == [0x080B58, 0x080B7C])
        owned["primary_claim_ids"] = ["chapter-root-table-selector"]
        mutations.append(wrong_owner)
        secondary_overlap = copy.deepcopy(post)
        owned = next(item for item in secondary_overlap["segments"] if item["range"] == [0x080B58, 0x080B7C])
        owned["secondary_claim_ids"] = ["forged-secondary"]
        mutations.append(secondary_overlap)
        partial = copy.deepcopy(post)
        owned = next(item for item in partial["segments"] if item["range"] == [0x080B58, 0x080B7C])
        owned["range"] = [0x080B58, 0x080B7B]
        mutations.append(partial)
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    verifier.rebuild_payload(ROOT, coverage=_canonical(mutation))


if __name__ == "__main__":
    unittest.main()
