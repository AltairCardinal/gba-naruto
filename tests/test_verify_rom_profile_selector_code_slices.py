"""Independent-verifier tests for the profile-selector code-slice packet."""

from __future__ import annotations

import json
import copy
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools import verify_rom_profile_selector_code_slices as verifier


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-profile-selector-code-slices-v1"
PAYLOAD_NAME = "rom-profile-selector-code-slices.json"


POST_PROMOTIONS = (
    (0x08B19E, 0x08B1B6, "profile-pointer-selector", SCHEMA),
    (0x08D1A4, 0x08D230, "profile-line-wrapper", SCHEMA),
    (0x08F594, 0x08F5D4, "chapter-root-table-selector", "rom-chapter-selector-code-slice-v1"),
    (0x080B58, 0x080B7C, "generic-sprite-loader-terminal-tail", "rom-sprite-loader-tail-v1"),
    (0x07A34C, 0x07AA8C, "battle-status-bar-generator-caller", "rom-battle-status-bar-caller-slice-v1"),
)


def _post_coverage() -> bytes:
    return (ROOT / "sequel/rom-byte-coverage.json").read_bytes()


class VerifyRomProfileSelectorCodeSlicesTests(unittest.TestCase):
    def test_cli_verifier_rebuilds_without_importing_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_profile_selector_code_slices.py").read_text()
        self.assertNotIn("from tools.export_rom_profile_selector_code_slices", source)
        self.assertNotIn("import tools.export_rom_profile_selector_code_slices", source)
        report = verifier.verify_artifact(ROOT, ROOT / "artifacts" / SCHEMA)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(report["range_count"], 2)
        self.assertEqual(report["bytes"], 164)

    def test_isolated_cli_contract_runs_without_repository_python_path(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "-I",
                "-S",
                "tools/verify_rom_profile_selector_code_slices.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-profile-selector-code-slices-v1",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)["verified"])

    def test_missing_contract_inputs_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "rom").mkdir(parents=True)
            (root / "rom/base.gba").write_bytes((ROOT / "rom/base.gba").read_bytes())
            report = verifier.verify_artifact(root, root / "artifact")
            self.assertFalse(report["verified"])
            self.assertTrue(report["errors"])

    def test_manifest_payload_and_packed_bytes_mutations_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / SCHEMA
            shutil.copytree(ROOT / "artifacts" / SCHEMA, artifact)
            payload_path = artifact / PAYLOAD_NAME
            payload = json.loads(payload_path.read_text())
            payload["packed_bytes"] = "00" * 164
            payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            self.assertFalse(verifier.verify_artifact(ROOT, artifact)["verified"])

            shutil.copytree(ROOT / "artifacts" / SCHEMA, artifact.parent / "manifest-tamper")
            manifest_path = artifact.parent / "manifest-tamper" / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["source"]["coverage"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            self.assertFalse(
                verifier.verify_artifact(ROOT, artifact.parent / "manifest-tamper")["verified"]
            )

    def test_post_promotion_fixture_and_mutations_are_fail_closed(self) -> None:
        post_raw = _post_coverage()
        post = json.loads(post_raw)
        payload, _packed = verifier.rebuild_payload(
            ROOT,
            coverage=post_raw,
        )
        self.assertEqual(payload["coverage"]["sha256"], verifier.COVERAGE_SHA256)
        report = verifier.verify_artifact(
            ROOT,
            ROOT / "artifacts" / SCHEMA,
            coverage=post_raw,
        )
        self.assertTrue(report["verified"], report["errors"])

        wrong_summary = copy.deepcopy(post)
        wrong_summary["summary"]["unknown_bytes"] -= 1
        wrong_owner = copy.deepcopy(post)
        owned = next(item for item in wrong_owner["segments"] if item["range"] == [0x08B19E, 0x08B1B6])
        owned["primary_class"] = "arm_code"
        secondary_overlap = copy.deepcopy(post)
        owned = next(item for item in secondary_overlap["segments"] if item["range"] == [0x08B19E, 0x08B1B6])
        owned["secondary_claim_ids"] = ["forged-secondary"]
        partial = copy.deepcopy(post)
        owned = next(item for item in partial["segments"] if item["range"] == [0x08B19E, 0x08B1B6])
        owned["range"] = [0x08B19E, 0x08B1B5]
        for mutation in (wrong_summary, wrong_owner, secondary_overlap, partial):
            raw = (json.dumps(mutation, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    verifier.rebuild_payload(ROOT, coverage=raw)

    def test_packet_verifiers_accept_later_additive_coverage(self) -> None:
        from tools import verify_rom_battle_status_bar_caller_slice as battle
        from tools import verify_rom_chapter_selector_code_slice as chapter
        from tools import verify_rom_sprite_loader_tail as sprite

        later = json.loads(_post_coverage())
        index, original = next(
            (index, segment)
            for index, segment in enumerate(later["segments"])
            if segment["primary_class"] == "unknown"
            and segment["range"][1] - segment["range"][0] > 1
        )
        start, end = original["range"]
        owned = copy.deepcopy(original)
        owned["range"] = [start, start + 1]
        owned["primary_class"] = "synthetic_later_packet"
        owned["primary_claim_ids"] = ["synthetic-later-packet"]
        owned["secondary_claim_ids"] = []
        owned.pop("unknown_reason", None)
        remainder = copy.deepcopy(original)
        remainder["range"] = [start + 1, end]
        later["segments"][index : index + 1] = [owned, remainder]
        later["claims"].append(
            {
                "id": "synthetic-later-packet",
                "range": [start, start + 1],
                "role": "primary",
                "primary_class": "synthetic_later_packet",
                "claim_kind": "synthetic_later_packet",
            }
        )
        later["summary"]["classified_bytes"] += 1
        later["summary"]["unknown_bytes"] -= 1
        later["summary"]["claim_count"] += 1
        later["summary"]["segment_count"] += 1
        raw = (
            json.dumps(later, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        for module, schema in (
            (verifier, SCHEMA),
            (chapter, "rom-chapter-selector-code-slice-v1"),
            (sprite, "rom-sprite-loader-tail-v1"),
            (battle, "rom-battle-status-bar-caller-slice-v1"),
        ):
            with self.subTest(schema=schema):
                report = module.verify_artifact(
                    ROOT, ROOT / "artifacts" / schema, coverage=raw
                )
                self.assertTrue(report["verified"], report["errors"])


if __name__ == "__main__":
    unittest.main()
