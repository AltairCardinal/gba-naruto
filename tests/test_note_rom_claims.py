#!/usr/bin/env python3
"""The open notes' ROM claims must stay true of the base ROM.

``docs/butano-wiring-roadmap.md`` (W5) wants the notes that already state a
verifiable conclusion about the original turned into gates.  332 of them cite
ROM addresses; those addresses are part of what the notes claim, so the bytes
there can be pinned against the base ROM.

This gate is **byte-level**, and the limit is stated in the receipt too: it
proves the bytes a note points at have not moved, not that the note's reading
of them still holds.  Semantic gates are per note and are the next step.

The tests pin:

* every pinnable claim still matches the base ROM;
* the base ROM's hash is the one the snapshot was taken against;
* addresses outside the cartridge window are **listed, not pinned** -- they
  live in EWRAM/PRAM/IO, which the base ROM does not contain;
* the snapshot is reproducible.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "snapshot_note_rom_claims.py"
CLAIMS = ROOT / "artifacts" / "butano-note-rom-claims-v1" / "claims.json"


class NoteRomClaimTest(unittest.TestCase):
    def _payload(self) -> dict:
        if not CLAIMS.is_file():
            self.skipTest("no note ROM claim snapshot in this tree")
        return json.loads(CLAIMS.read_text(encoding="utf-8"))

    def test_every_pinned_claim_still_matches_the_base_rom(self) -> None:
        payload = self._payload()
        rom = (ROOT / "rom" / "base.gba").read_bytes()
        broken: list[str] = []
        for claim in payload["claims"]:
            offset = claim["offset"]
            actual = rom[offset : offset + payload["pin_bytes"]].hex()
            if actual != claim["bytes"]:
                broken.append(
                    f"{claim['note']} {claim['address']}: "
                    f"expected {claim['bytes']}, ROM has {actual}"
                )
        self.assertEqual(broken, [], "\n".join(broken[:10]))

    def test_the_snapshot_was_taken_against_this_rom(self) -> None:
        import hashlib

        payload = self._payload()
        digest = hashlib.sha256((ROOT / "rom" / "base.gba").read_bytes()).hexdigest()
        self.assertEqual(payload["rom_sha256"], digest)

    def test_no_claim_is_pinned_outside_the_cartridge_window(self) -> None:
        payload = self._payload()
        for claim in payload["claims"]:
            with self.subTest(claim=claim["address"]):
                address = int(claim["address"], 16)
                self.assertGreaterEqual(address, payload["rom_base"])
                self.assertLess(address, payload["rom_base"] + 0x2000000)

    def test_addresses_outside_the_cartridge_are_listed_not_pinned(self) -> None:
        payload = self._payload()
        pinned = {claim["address"] for claim in payload["claims"]}
        for item in payload["not_pinnable"]:
            with self.subTest(address=item["address"]):
                self.assertNotIn(item["address"], pinned)
                self.assertTrue(item["reason"])

    def test_the_snapshot_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "claims.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(ROOT),
                    "--out-dir",
                    str(Path(tmp) / "out"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            fresh = json.loads(
                (Path(tmp) / "out" / "claims.json").read_text(encoding="utf-8")
            )
            self.assertEqual(fresh["summary"], self._payload()["summary"])
            self.assertEqual(
                [(c["note"], c["address"], c["bytes"]) for c in fresh["claims"]],
                [(c["note"], c["address"], c["bytes"]) for c in self._payload()["claims"]],
            )


if __name__ == "__main__":
    unittest.main()
