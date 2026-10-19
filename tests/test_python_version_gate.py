"""The audit toolchain must refuse to run on an unsupported interpreter.

The repository uses ``zip(..., strict=True)`` in more than a thousand places,
which needs Python 3.10+.  On Python 3.9 the coverage audit fails with
"zip() takes no keyword arguments" and the formal proof would then report
that as missing evidence instead of an environment problem, producing false
blockers.
"""

import unittest

from tools import audit_reverse_engineering_proof as proof_auditor
from tools import audit_rom_byte_coverage as coverage_auditor


class PythonVersionGateTests(unittest.TestCase):
    def test_gate_rejects_an_unsupported_interpreter(self):
        with self.assertRaises(RuntimeError) as caught:
            coverage_auditor._require_supported_python((3, 9))
        message = str(caught.exception)
        self.assertIn("3.10", message)
        self.assertIn("zip(strict=True)", message)

    def test_gate_accepts_a_supported_interpreter(self):
        coverage_auditor._require_supported_python((3, 10))
        coverage_auditor._require_supported_python((3, 14))

    def test_gate_defaults_to_the_running_interpreter(self):
        import sys

        coverage_auditor._require_supported_python()
        self.assertGreaterEqual(
            (sys.version_info.major, sys.version_info.minor),
            coverage_auditor.MINIMUM_PYTHON,
        )

    def test_both_auditors_expose_the_same_gate(self):
        self.assertEqual(
            proof_auditor.MINIMUM_PYTHON, coverage_auditor.MINIMUM_PYTHON
        )

    def test_coverage_audit_refuses_before_building(self):
        import collections
        import unittest.mock as mock

        fake_version = collections.namedtuple(
            "version_info", "major minor micro releaselevel serial"
        )
        # The gate must fire before the 57-minute coverage rebuild, so the
        # rebuild is replaced by a sentinel that would fail the test loudly.
        with mock.patch.object(
            coverage_auditor.sys, "version_info", fake_version(3, 9, 0, "final", 0)
        ), mock.patch.object(
            coverage_auditor,
            "build_manifest",
            side_effect=AssertionError("the rebuild must not start"),
        ):
            with self.assertRaises(RuntimeError):
                coverage_auditor.audit_manifest(
                    coverage_auditor.Path("."), {"schema": "rom-byte-coverage-audit-v1"}
                )


if __name__ == "__main__":
    unittest.main()
