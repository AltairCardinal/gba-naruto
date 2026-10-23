#!/usr/bin/env python3
"""The graphic assets must be grouped by the generator that produced them.

``docs/butano-wiring-roadmap.md`` (W3, action 2, third part) asks for a
sidecar per generator instead of a declaration per file.  The grouping has to
be *measured*, and every asset that cannot be measured has to stay visible
instead of being guessed into a group.

These tests pin:

* every group has a sidecar, and the sidecar lists the assets it owns;
* every asset in a sidecar really exists in the graphics directory;
* every attribution records **which rule** decided it;
* an asset no rule explains is in the receipt's open list, not in a group;
* the receipt is reproducible (the same tree gives the same grouping).
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "annotate_graphic_asset_provenance.py"
RECEIPT = ROOT / "artifacts" / "butano-graphic-asset-provenance-v1" / "provenance.json"
GRAPHICS = ROOT / "butano-sequel" / "graphics"

RULES = {"literal", "pattern", "prefix", "constant"}


class GraphicAssetProvenanceTest(unittest.TestCase):
    def _payload(self) -> dict:
        if not RECEIPT.is_file():
            self.skipTest("no graphic asset provenance receipt in this tree")
        return json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_every_group_has_a_sidecar_that_lists_its_assets(self) -> None:
        payload = self._payload()
        self.assertGreater(len(payload["groups"]), 0)
        for group in payload["groups"]:
            with self.subTest(generator=group["generator"]):
                sidecar_path = ROOT / group["sidecar"]
                self.assertTrue(sidecar_path.is_file(), group["sidecar"])
                sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
                self.assertEqual(sidecar["generator"], group["generator"])
                self.assertEqual(len(sidecar["assets"]), group["asset_count"])
                self.assertGreater(group["asset_count"], 0)

    def test_every_attributed_asset_exists(self) -> None:
        payload = self._payload()
        for group in payload["groups"]:
            sidecar = json.loads(
                (ROOT / group["sidecar"]).read_text(encoding="utf-8")
            )
            for asset in sidecar["assets"]:
                with self.subTest(asset=asset):
                    self.assertTrue((GRAPHICS / asset).is_file(), asset)

    def test_every_attribution_records_its_rule(self) -> None:
        payload = self._payload()
        for group in payload["groups"]:
            sidecar = json.loads(
                (ROOT / group["sidecar"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                sorted(sidecar["attribution_rules"]),
                sorted(sidecar["assets"]),
            )
            for asset, rule in sidecar["attribution_rules"].items():
                with self.subTest(asset=asset):
                    self.assertIn(rule, RULES)

    def test_the_open_list_holds_every_unattributed_asset(self) -> None:
        payload = self._payload()
        owned: set[str] = set()
        for group in payload["groups"]:
            sidecar = json.loads(
                (ROOT / group["sidecar"]).read_text(encoding="utf-8")
            )
            owned |= set(sidecar["assets"])
        open_assets = {
            item["asset"] for item in payload["unattributed"]
        } | {item["asset"] for item in payload["ambiguous"]}
        every = {
            path.name
            for path in GRAPHICS.iterdir()
            if path.is_file() and not path.name.startswith(".")
        }
        self.assertEqual(owned | open_assets, every)
        self.assertFalse(owned & open_assets)

    def test_the_grouping_is_reproducible(self) -> None:
        with __import__("tempfile").TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(ROOT),
                    "--out-dir",
                    str(out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            fresh = json.loads(
                (out / "provenance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                fresh["summary"], self._payload()["summary"]
            )


if __name__ == "__main__":
    unittest.main()


class GraphicReverseSourceTest(unittest.TestCase):
    """A generator that consumes a reverse result must say so.

    The generators already declare it with the tree's own contract
    (``provenance_block(sources=((family, manifest sha256),))``), so the
    sidecar reads that declaration instead of grepping the source.  The
    generators that declare nothing are listed as a gap, not silently
    credited with an empty provenance.
    """

    def _payload(self) -> dict:
        if not RECEIPT.is_file():
            self.skipTest("no graphic asset provenance receipt in this tree")
        return json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_the_sidecar_records_the_declared_families(self) -> None:
        payload = self._payload()
        for group in payload["groups"]:
            with self.subTest(generator=group["generator"]):
                sidecar = json.loads(
                    (ROOT / group["sidecar"]).read_text(encoding="utf-8")
                )
                self.assertIsInstance(sidecar["declared_families"], list)
                for entry in sidecar["declared_families"]:
                    self.assertIn("family", entry)
                    self.assertEqual(len(entry["manifest_sha256"]), 64)

    def test_a_declared_family_is_a_real_family(self) -> None:
        index = ROOT / "artifacts" / "reverse-results-index-v1" / "index.json"
        if not index.is_file():
            self.skipTest("no reverse results index in this tree")
        known = {
            entry["id"]
            for entry in json.loads(index.read_text(encoding="utf-8"))["entries"]
            if entry.get("kind") == "artifact"
        }
        payload = self._payload()
        for group in payload["groups"]:
            for entry in group["declared_families"]:
                with self.subTest(family=entry["family"]):
                    self.assertIn(entry["family"], known)

    def test_the_declaration_gap_is_the_complement_of_the_declarations(self) -> None:
        payload = self._payload()
        declared = {
            group["generator"]
            for group in payload["groups"]
            if group["declared_families"]
        }
        self.assertEqual(set(payload["declaration_gap"]) | declared, {
            group["generator"] for group in payload["groups"]
        })
        self.assertFalse(set(payload["declaration_gap"]) & declared)
