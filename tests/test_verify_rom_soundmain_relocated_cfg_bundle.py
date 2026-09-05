from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import verify_rom_soundmain_relocated_cfg as legacy


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/rom-soundmain-relocated-cfg-v1"
WRAPPER_PATH = ROOT / "tools/verify_rom_soundmain_relocated_cfg_bundle.py"
MANIFEST_NAME = "manifest.json"
PAYLOAD_NAME = "rom-soundmain-relocated-cfg.json"
BUNDLE_NAME = "rom-soundmain-relocated-cfg.bin"


def _load_wrapper():
    spec = importlib.util.spec_from_file_location(
        "verify_rom_soundmain_relocated_cfg_bundle", WRAPPER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load SoundMain relocated CFG bundle verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


class SoundMainRelocatedCfgBundleVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wrapper = _load_wrapper()

    def test_report_pins_accepted_bundle_and_avoids_live_coverage(self):
        with mock.patch.object(
            legacy,
            "_coverage_baseline",
            side_effect=AssertionError("bundle verifier must not read live coverage"),
        ) as live_coverage:
            report = self.wrapper.verify_artifact_bundle(ROOT, ARTIFACT)

        self.assertFalse(live_coverage.called)
        self.assertEqual(
            report["schema"],
            "rom-soundmain-relocated-cfg-bundle-verification-v1",
        )
        self.assertTrue(report["verified"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["artifact_schema"], "rom-soundmain-relocated-cfg-v1")
        self.assertEqual(report["artifact_status"], "accepted")
        self.assertTrue(report["artifact_bundle_verified"])
        self.assertTrue(report["legacy_receipt_verified"])
        self.assertTrue(report["candidate_identity_verified"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertEqual(report["promotion_bytes"], 924)
        self.assertEqual(report["promotion_claim_count"], 6)
        self.assertEqual(report["promotion_range_count"], 6)
        self.assertEqual(report["promotion_union_range_count"], 5)
        self.assertEqual(report["deferred_alignment_gap_bytes"], 6)
        self.assertEqual(
            report["promotion_packed_sha256"],
            "2e94dbb5f876de3420d1317db7ad646991b9778e15a3699659d7786d65de8331",
        )
        self.assertEqual(
            report["accepted_manifest_sha256"],
            "e6b9a2cbdb439c520b5c98a422279e44e03866dbf1541810626d28eb57ce0a37",
        )
        self.assertEqual(
            report["candidate_manifest_sha256"],
            "16aedff95afaf1e24f49cd74c01ded1f46433a79b5b708145dfa9a582fd2fa28",
        )
        self.assertEqual(report["summary"]["instruction_count"], 315)
        self.assertEqual(report["summary"]["block_count"], 73)
        self.assertEqual(report["summary"]["promoted_bytes"], 924)

    def test_external_anchor_rejects_synchronized_candidate_receipt_resigning(self):
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="soundmain-wrapper-resign-test-", dir=active
        ) as raw:
            target = Path(raw) / "artifact"
            shutil.copytree(ARTIFACT, target)
            manifest_path = target / MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            candidate = "build/forged-candidate"
            output = target.relative_to(ROOT).as_posix()
            acceptance_command = [
                "python3",
                "tools/verify_rom_soundmain_relocated_cfg.py",
                "--artifact",
                candidate,
                "--accept-to",
                output,
            ]
            manifest["acceptance"]["candidate_artifact"] = candidate
            manifest["acceptance"]["output_artifact"] = output
            manifest["acceptance"]["command"] = acceptance_command
            manifest["producer"]["output_artifact"] = candidate
            manifest["producer"]["command"][-1] = candidate
            manifest["verifier"]["command"] = acceptance_command
            candidate_manifest = dict(manifest)
            candidate_manifest.pop("acceptance")
            candidate_manifest.pop("verifier")
            candidate_manifest["artifact_status"] = "candidate"
            candidate_manifest["verification"] = {
                "status": "pending",
                "report": None,
            }
            manifest["acceptance"]["candidate_identity"]["manifest_sha256"] = (
                hashlib.sha256(_canonical(candidate_manifest)).hexdigest()
            )
            manifest_path.write_bytes(_canonical(manifest))

            with self.assertRaisesRegex(ValueError, "accepted manifest identity changed"):
                self.wrapper.verify_artifact_bundle(ROOT, target)

    def test_rejects_manifest_payload_and_binary_mutations(self):
        mutations = {
            MANIFEST_NAME: lambda raw: _canonical(
                {**json.loads(raw), "approval": {"status": "forged"}}
            ),
            PAYLOAD_NAME: lambda raw: _canonical(
                {
                    **json.loads(raw),
                    "summary": {
                        **json.loads(raw)["summary"],
                        "instruction_count": 316,
                    },
                }
            ),
            BUNDLE_NAME: lambda raw: bytes([raw[0] ^ 1]) + raw[1:],
        }
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="soundmain-wrapper-mutation-test-", dir=active
        ) as raw:
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    target = Path(raw) / name.replace(".", "-")
                    shutil.copytree(ARTIFACT, target)
                    path = target / name
                    path.write_bytes(mutate(path.read_bytes()))
                    with self.assertRaisesRegex(
                        ValueError, "artifact|manifest|payload|binary|identity"
                    ):
                        self.wrapper.verify_artifact_bundle(ROOT, target)

    def test_wrapper_has_no_exporter_or_capstone_import_and_cli_is_stable(self):
        imports: list[str] = []
        for node in ast.walk(ast.parse(WRAPPER_PATH.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(
            any(
                name.endswith("export_rom_soundmain_relocated_cfg")
                or name == "capstone"
                or name.startswith("capstone.")
                for name in imports
            ),
            imports,
        )

        command = [
            sys.executable,
            "-I",
            "-S",
            "tools/verify_rom_soundmain_relocated_cfg_bundle.py",
            "--root",
            ".",
        ]
        first = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, check=False
        )
        second = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))

    def test_stage1_hash_is_checked_before_any_stage1_import_side_effect(self):
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="soundmain-wrapper-preimport-test-", dir=active
        ) as raw:
            clone = Path(raw) / "clone"
            tools = clone / "tools"
            tools.mkdir(parents=True)
            shutil.copy2(WRAPPER_PATH, tools / WRAPPER_PATH.name)
            sentinel = tools / "stage1-imported.txt"
            (tools / "verify_rom_soundmain_relocated_cfg.py").write_text(
                "from pathlib import Path\n"
                "Path(__file__).with_name('stage1-imported.txt').write_text('executed')\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    f"tools/{WRAPPER_PATH.name}",
                    "--root",
                    ".",
                ],
                cwd=clone,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(
                sentinel.exists(),
                "untrusted stage1 code executed before its frozen hash was checked",
            )

    def test_verified_source_bytes_not_matching_unanchored_pyc_are_executed(self):
        active = ROOT / "build/experiments/active"
        active.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="soundmain-wrapper-pyc-test-", dir=active
        ) as raw:
            clone = Path(raw) / "clone"
            tools = clone / "tools"
            tools.mkdir(parents=True)
            shutil.copy2(WRAPPER_PATH, tools / WRAPPER_PATH.name)
            source = tools / "verify_rom_soundmain_relocated_cfg.py"
            trusted = (ROOT / "tools/verify_rom_soundmain_relocated_cfg.py").read_bytes()
            sentinel = tools / "stage1-pyc-executed.txt"
            prefix = (
                b"from pathlib import Path\n"
                b"Path(__file__).with_name('stage1-pyc-executed.txt').write_text('executed')\n#"
            )
            self.assertLess(len(prefix), len(trusted))
            malicious = prefix + b"x" * (len(trusted) - len(prefix))
            source.write_bytes(malicious)
            timestamp = 1_700_000_000
            os.utime(source, (timestamp, timestamp))
            py_compile.compile(
                str(source),
                doraise=True,
                invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP,
            )
            source.write_bytes(trusted)
            os.utime(source, (timestamp, timestamp))

            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    f"tools/{WRAPPER_PATH.name}",
                    "--root",
                    ".",
                ],
                cwd=clone,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(
                sentinel.exists(),
                "unanchored bytecode executed instead of the verified source bytes",
            )


if __name__ == "__main__":
    unittest.main()
