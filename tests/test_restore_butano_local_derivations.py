#!/usr/bin/env python3
"""The local artifact copies must be restored *and* provably identical.

``docs/butano-wiring-roadmap.md`` (W1) closes a line that was broken in the
work tree rather than in the design: 26 reverse families are named by the
remake's build chain, but the local copy of ``artifacts/<family>/`` was gone
after the 2026-10-19 cleanup.  The producers were still there, so the fix was
to re-run them -- and to check the bytes.

These tests pin down the parts that make that check mean something:

* the candidate set comes from the **wiring receipt**, not from a hand-kept
  list, so the milestone's denominator is the same one the gate reads;
* a producer is found even when the family name only hides behind a module
  constant (``REPO_ROOT / "artifacts" / SCHEMA``);
* a producer that claims the **same schema** but writes different bytes is a
  divergence, and it is reported -- never papered over by copying the reverse
  tree's file;
* a producer that writes a **different schema** is a version bump, which may
  fall back to an import, and the receipt has to say so;
* the provenance record survives a second run, so the mode does not decay into
  "already identical";
* the independent verifier re-decides every claim from the trees, and a
  tampered local copy is rejected.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESTORE = ROOT / "tools" / "restore_butano_local_derivations.py"
VERIFY = ROOT / "tools" / "verify_butano_local_derivations.py"

sys.path.insert(0, str(ROOT))

from tools.restore_butano_local_derivations import (  # noqa: E402
    candidate_families,
    producer_output_family,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ProducerDiscoveryTest(unittest.TestCase):
    """The producer has to be found, not guessed."""

    def test_the_output_family_is_resolved_through_a_module_constant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "export_x.py"
            _write(
                script,
                "from pathlib import Path\n"
                "REPO_ROOT = Path(__file__).resolve().parents[1]\n"
                'SCHEMA = "rom-example-v1"\n'
                "def main():\n"
                '    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "artifacts" / SCHEMA)\n',
            )
            self.assertEqual(producer_output_family(script), "rom-example-v1")

    def test_a_plain_literal_output_directory_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "export_y.py"
            _write(
                script,
                "from pathlib import Path\n"
                'def main():\n'
                '    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/rom-other-v1"))\n',
            )
            self.assertEqual(producer_output_family(script), "rom-other-v1")

    def test_the_real_producers_of_the_restored_families_are_discoverable(self) -> None:
        """The families this milestone restored must have a findable producer.

        A producer that cannot be found would silently turn into an import,
        and the receipt would quietly stop saying "re-derived".
        """
        for script, family in (
            ("tools/export_scene_visual_packs.py", "scene-visual-packs-v1"),
            ("tools/export_bg_resource_canvases.py", "bg-resource-canvases-v1"),
            ("tools/export_bg_scene_selection.py", "bg-scene-selection-v1"),
            ("tools/export_tile_asset_bg_layers.py", "tile-assets-bg-v2"),
        ):
            self.assertEqual(producer_output_family(ROOT / script), family, script)


class CandidateSetTest(unittest.TestCase):
    def test_the_candidate_set_is_read_from_the_wiring_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wiring.json"
            _write(
                path,
                json.dumps(
                    {
                        "source_rows": [
                            {"id": "rom-a-v1", "state": "local-derivation-missing"},
                            {"id": "rom-b-v1", "state": "on-shelf"},
                            {"id": "rom-c-v1", "state": "local-derivation-missing"},
                        ]
                    }
                ),
            )
            self.assertEqual(
                candidate_families(path), ["rom-a-v1", "rom-c-v1"]
            )


class RestoreBehaviourTest(unittest.TestCase):
    """A synthetic tree: one producer, one reverse twin, one verdict."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.reverse = self.root / "reverse"
        self.family = "rom-demo-v1"
        (self.reverse / "artifacts" / self.family).mkdir(parents=True)
        (self.reverse / "artifacts" / self.family / "manifest.json").write_text(
            json.dumps({"schema": "rom-demo-v1"}) + "\n", encoding="utf-8"
        )
        (self.reverse / "artifacts" / self.family / "payload.bin").write_bytes(b"\x01\x02")
        self.wiring = self.root / "artifacts" / "butano-wiring-coverage-v1" / "wiring.json"
        _write(
            self.wiring,
            json.dumps(
                {
                    "source_rows": [
                        {"id": self.family, "state": "local-derivation-missing"}
                    ]
                }
            ),
        )

    def _producer(self, body: str) -> None:
        """A producer the discovery can actually find.

        It has to look like the real ones: an ``--output-dir`` argument whose
        default names the family under ``artifacts/``.
        """
        _write(
            self.root / "tools" / "export_rom_demo.py",
            "import argparse\n"
            "import json\n"
            "from pathlib import Path\n"
            'SCHEMA = "rom-demo-v1"\n'
            "def main():\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--root', type=Path, default=Path('.'))\n"
            "    parser.add_argument('--output-dir', type=Path, default=Path('artifacts') / SCHEMA)\n"
            "    args = parser.parse_args()\n"
            "    out = args.output_dir\n"
            "    out.mkdir(parents=True, exist_ok=True)\n"
            + body
            + "\nif __name__ == '__main__':\n    main()\n",
        )

    def _run(self) -> tuple[int, dict]:
        out_dir = self.root / "artifacts" / "butano-local-derivations-v1"
        proc = subprocess.run(
            [
                sys.executable,
                str(RESTORE),
                "--root",
                str(self.root),
                "--reverse-root",
                str(self.reverse),
                "--wiring",
                str(self.wiring),
                "--out-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
        )
        payload = json.loads((out_dir / "local.json").read_text(encoding="utf-8"))
        return proc.returncode, payload

    def test_a_producer_that_reproduces_the_bytes_is_a_re_derivation(self) -> None:
        self._producer(
            '    (out / "manifest.json").write_text(json.dumps({"schema": "rom-demo-v1"}) + "\\n", encoding="utf-8")\n'
            '    (out / "payload.bin").write_bytes(b"\\x01\\x02")'
        )
        code, payload = self._run()
        self.assertEqual(code, 0, payload)
        row = payload["rows"][0]
        self.assertEqual(row["mode"], "rederived")
        self.assertTrue(row["identical"])
        self.assertTrue((self.root / "artifacts" / self.family / "payload.bin").is_file())

    def test_the_same_schema_with_different_bytes_is_a_divergence(self) -> None:
        """The roadmap forbids papering over a divergence.

        A producer that claims the same schema but writes different bytes is
        a decoder disagreement.  The tool must report it and must NOT copy
        the reverse tree's file over it.
        """
        self._producer(
            '    (out / "manifest.json").write_text(json.dumps({"schema": "rom-demo-v1"}) + "\\n", encoding="utf-8")\n'
            '    (out / "payload.bin").write_bytes(b"\\x09\\x09")'
        )
        code, payload = self._run()
        self.assertNotEqual(code, 0)
        row = payload["rows"][0]
        self.assertEqual(row["mode"], "diverged")
        self.assertFalse(row["identical"])
        local = self.root / "artifacts" / self.family
        self.assertFalse(local.is_dir(), "a diverged family must not be copied in")

    def test_a_different_schema_may_fall_back_to_an_import(self) -> None:
        """A version bump is not a divergence -- but it must be named."""
        self._producer(
            '    (out / "manifest.json").write_text(json.dumps({"schema": "rom-demo-v2"}) + "\n", encoding="utf-8")\n'
            '    (out / "payload.bin").write_bytes(b"\\x01\\x02")'
        )
        code, payload = self._run()
        self.assertEqual(code, 0, payload)
        row = payload["rows"][0]
        self.assertEqual(row["mode"], "imported")
        self.assertIn("schema", row["reason"])
        self.assertTrue(row["identical"])

    def test_the_provenance_record_survives_a_second_run(self) -> None:
        self._producer(
            '    (out / "manifest.json").write_text(json.dumps({"schema": "rom-demo-v1"}) + "\\n", encoding="utf-8")\n'
            '    (out / "payload.bin").write_bytes(b"\\x01\\x02")'
        )
        code, first = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(first["rows"][0]["mode"], "rederived")
        code, second = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(
            second["rows"][0]["mode"],
            "rederived",
            "a second run must not downgrade the recorded mode",
        )

    def test_a_missing_wiring_receipt_fails_closed(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(RESTORE),
                "--root",
                str(self.root),
                "--reverse-root",
                str(self.reverse),
                "--wiring",
                str(self.root / "missing.json"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)


class IndependentVerifierTest(unittest.TestCase):
    """The verifier must not import the tool it checks."""

    def test_the_verifier_does_not_import_the_restore_tool(self) -> None:
        tree = ast.parse(VERIFY.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse(
            [name for name in imported if "restore_butano_local_derivations" in name],
            "the verifier must re-decide the claims with its own code",
        )

    def test_the_verifier_rejects_a_tampered_local_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reverse = root / "reverse"
            (reverse / "artifacts" / "rom-t-v1").mkdir(parents=True)
            (reverse / "artifacts" / "rom-t-v1" / "payload.bin").write_bytes(b"good")
            (root / "artifacts" / "rom-t-v1").mkdir(parents=True)
            (root / "artifacts" / "rom-t-v1" / "payload.bin").write_bytes(b"good")
            receipt = root / "local.json"
            wiring = (
                root
                / "artifacts"
                / "butano-wiring-coverage-v1"
                / "wiring.json"
            )
            _write(
                wiring,
                json.dumps({"source_rows": [{"id": "rom-t-v1", "state": "local-rederived-identical"}]}),
            )
            _write(
                receipt,
                json.dumps(
                    {
                        "rows": [
                            {
                                "family": "rom-t-v1",
                                "mode": "imported",
                                "producer": None,
                                "local_manifest_sha": None,
                                "reverse_manifest_sha": None,
                                "identical": True,
                            }
                        ],
                        "summary": {
                            "rederived": 0,
                            "imported": 1,
                            "already_identical": 0,
                            "diverged": 0,
                            "unavailable": 0,
                            "error": 0,
                        },
                    }
                ),
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY),
                    "--root",
                    str(root),
                    "--reverse-root",
                    str(reverse),
                    "--receipt",
                    str(receipt),
                    "--wiring",
                    str(wiring),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            (root / "artifacts" / "rom-t-v1" / "payload.bin").write_bytes(b"tampered")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY),
                    "--root",
                    str(root),
                    "--reverse-root",
                    str(reverse),
                    "--receipt",
                    str(receipt),
                    "--wiring",
                    str(wiring),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("differs", proc.stderr)


class RestoredTreeTest(unittest.TestCase):
    """The milestone's own gate, checked against the real tree."""

    def test_every_restored_family_is_byte_identical_to_the_reverse_tree(self) -> None:
        receipt_path = (
            ROOT / "artifacts" / "butano-local-derivations-v1" / "local.json"
        )
        if not receipt_path.is_file():
            self.skipTest("no local-derivation receipt in this tree")
        proc = subprocess.run(
            [
                sys.executable,
                str(VERIFY),
                "--root",
                str(ROOT),
                "--reverse-root",
                "/Users/altair/github/gba-naruto-reverse",
                "--receipt",
                str(receipt_path),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_the_wiring_gate_reports_no_missing_local_derivation(self) -> None:
        wiring_path = (
            ROOT / "artifacts" / "butano-wiring-coverage-v1" / "wiring.json"
        )
        if not wiring_path.is_file():
            self.skipTest("no wiring receipt in this tree")
        payload = json.loads(wiring_path.read_text(encoding="utf-8"))
        missing = [
            row
            for row in payload["source_rows"]
            if row.get("state") == "local-derivation-missing"
        ]
        self.assertEqual(missing, [], "W1's gate is local-derivation-missing == 0")


if __name__ == "__main__":
    unittest.main()
