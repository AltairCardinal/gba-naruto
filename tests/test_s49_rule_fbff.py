#!/usr/bin/env python3
"""``0xFBFF`` is a corrupt terminator, not a new format.

The original ROM carries exactly one corrupted component terminator.  At
``0x0825A8E4`` -- the trailer of character 26, visual slot 2, frame 2 --
the bytes read ``0xFBFF`` where every other frame reads ``0xFFFF``.  The
signed value of ``0xFBFF`` is -1025, and the common renderer only accepts
-1 as the end of a component list, so it does **not** stop there: it steps
on by one 20 byte component at a time and reads the data behind the frame
as if it were more components.

The reverse side closed this with a one byte A/B on the ROM, and this gate
keeps the conclusion tied to the bytes:

* the corrupt trailer is at ``0x0825A8E4`` in the ROM under study, and its
  signed value is -1025;
* the renderer's two instruction windows hash to the values the signed
  manifest records;
* patching the high byte of the trailer (``0x0825A8E5``: ``0xFB`` ->
  ``0xFF``) produces the control ROM with the signed hash;
* the base runtime trace reads four pointers one component apart, starting
  at the corrupt trailer, while the control trace reads ``0xFFFF`` (-1) at
  the same address and stops.

The remake reads the same ROM table.  Its generated catalog carries the
corrupt trailer value through, but it does not record the defect, so the
corruption is swallowed silently.  That is the conformance test, and it is
an ``expectedFailure`` until the generator records the defect the way the
reverse side's exporter does.

The measurements come from ``tools/butano/measure_s49_rule_fbff.py``.

The reverse-side note this rule was carried by is
``notes/character-battle-visuals-export-20260729.md`` (the export of the
visual matrix, the ``FBFF`` closure and the ``renderer_terminator`` flag).
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.butano import measure_s49_rule_fbff as measurement  # noqa: E402

REVERSE_ROOT = Path(
    os.environ.get(
        "KONOHA_REVERSE_ROOT", measurement.DEFAULT_REVERSE_ROOT
    )
)


def _measure():
    return measurement.measure(ROOT, REVERSE_ROOT)


class FbffRomEvidence(unittest.TestCase):
    """The ROM side, verified from the local ROM."""

    def test_the_rom_under_study_is_the_pinned_one(self):
        payload = _measure()
        self.assertEqual(payload["rom"]["rom_sha256"], measurement.ROM_SHA256)

    def test_the_corrupt_trailer_is_in_the_rom(self):
        payload = _measure()
        rom = payload["rom"]
        self.assertEqual(rom["trailer_gba_address"], "0x0825A8E4")
        self.assertEqual(rom["trailer_bytes"], "fffb0000")
        self.assertEqual(
            rom["trailer_signed_value"],
            -1025,
            "the corrupt trailer's signed value changed",
        )
        self.assertNotEqual(
            rom["trailer_signed_value"],
            -1,
            "the corrupt trailer is now a legal terminator; the renderer "
            "overrun conclusion no longer holds",
        )

    def test_the_renderer_windows_hash_to_the_signed_values(self):
        payload = _measure()
        windows = payload["rom"]["renderer_windows"]
        self.assertEqual(len(windows), 2)
        for window, (_start, _end, expected) in zip(
            windows, measurement.RENDERER_WINDOWS
        ):
            with self.subTest(window=window["start"]):
                self.assertEqual(window["sha256"], expected)

    def test_the_one_byte_repair_produces_the_signed_control_rom(self):
        payload = _measure()
        rom = payload["rom"]
        self.assertEqual(rom["repair"]["before"], 0xFB)
        self.assertEqual(rom["repair"]["after"], 0xFF)
        self.assertEqual(rom["repair"]["changed_byte_count"], 1)
        self.assertEqual(
            rom["control_rom_sha256"],
            rom["control_rom_sha256_expected"],
        )
        self.assertEqual(
            rom["control_rom_sha256"],
            measurement.CONTROL_ROM_SHA256,
        )


class FbffRuntimeOverrun(unittest.TestCase):
    """The runtime side, read from the signed reverse side traces."""

    def setUp(self):
        payload = _measure()
        reverse = payload["reverse_tree"]
        if not reverse.get("available"):
            self.skipTest(reverse.get("reason", "the reverse tree is absent"))
        self.reverse = reverse

    def test_the_manifest_calls_it_a_renderer_overrun(self):
        conclusion = self.reverse["conclusion"]
        self.assertEqual(self.reverse["schema"], "character-fbff-runtime-v1")
        self.assertEqual(
            conclusion["runtime_semantics"],
            "not_a_terminator_renderer_overrun",
        )
        self.assertEqual(conclusion["raw_trailer_address"], "0x0825A8E4")
        self.assertEqual(conclusion["raw_trailer"], "0xFBFF")
        self.assertEqual(
            self.reverse["base_rom_sha256"],
            measurement.ROM_SHA256,
        )

    def test_the_base_run_reads_past_the_frame_boundary(self):
        hits = self.reverse["traces"]["base"]["hits"]
        self.assertEqual(len(hits), 4)
        self.assertEqual(hits[0]["pointer"], "0x0825A8E4")
        self.assertEqual(hits[0]["raw_u16"], "0xFBFF")
        self.assertEqual(hits[0]["signed_value"], -1025)
        pointers = [int(hit["pointer"], 16) for hit in hits]
        steps = {
            pointers[index + 1] - pointers[index] for index in range(3)
        }
        self.assertEqual(
            steps,
            {20},
            "the renderer no longer steps one 20 byte component at a time "
            "past the corrupt trailer",
        )

    def test_the_control_run_stops_at_the_repaired_trailer(self):
        hits = self.reverse["traces"]["control"]["hits"]
        self.assertTrue(hits)
        for hit in hits:
            with self.subTest(pointer=hit["pointer"]):
                self.assertEqual(hit["pointer"], "0x0825A8E4")
                self.assertEqual(hit["raw_u16"], "0xFFFF")
                self.assertEqual(hit["signed_value"], -1)


class FbffRemakeConformance(unittest.TestCase):
    """The remake reads the same table and has to record the defect."""

    def test_the_generated_catalog_records_the_corrupt_trailer(self):
        """The generator now records the defect instead of swallowing it.

        The generator reads the same ROM table and carries the corrupt
        trailer value (0xFBFF) through; it now also stores the raw trailer
        bytes and says that the renderer does not accept them.

        The one byte repair is deliberately **not** applied: the original
        does not stop at the corrupt trailer, it keeps reading components
        behind the frame, and that overrun is part of what the original
        draws.  Repairing the remake would make it differ from the original
        on exactly the frame the defect is in.
        """

        payload = _measure()
        catalog = payload["catalog"]
        self.assertTrue(
            catalog["records_the_defect"],
            "the generated catalog does not record the corrupt terminator",
        )

    def test_the_recorded_trailer_is_the_corrupt_one(self):
        """The raw trailer is kept, so the defect stays auditable.

        The record keeps the raw bytes ``fffb0000`` and says that the
        renderer does not accept the trailer, so a reader can tell a
        repaired frame from a frame that was always legal.
        """

        payload = _measure()
        catalog = payload["catalog"]
        self.assertEqual(
            catalog["recorded_fields"].get("frame_trailer_raw_hex"),
            "fffb0000",
        )
        self.assertIs(
            catalog["recorded_fields"].get("renderer_terminator"),
            False,
            "the record does not say that the renderer does not accept the "
            "trailer",
        )


class EveryExpectedFailureSaysWhatIsMissing(unittest.TestCase):
    """A known gap has to be written down, not just encoded as red."""

    def test_each_expected_failure_documents_the_missing_piece(self):
        gaps = FbffRemakeConformance
        expected = [
            name
            for name in dir(gaps)
            if name.startswith("test_")
            and getattr(getattr(gaps, name), "__unittest_expecting_failure__", False)
        ]
        self.assertEqual(
            expected,
            [],
            "the 0xFBFF defect is recorded in the generated catalog, so this "
            "file has no expected failure left; the remaining work is the "
            "runtime overrun, which the ledger tracks",
        )


if __name__ == "__main__":
    unittest.main()
