#!/usr/bin/env python3
"""The relocation and writeback families must be importable as the engineering
basis for the "customized original ROM" route.

Content-level customization of the original ROM needs more than the right
bytes: the resource has to be relocated, every pointer that referenced it has
to be recomputed, and the result has to still fit.  The reverse work tree
closed that for 22 families; until now all 22 sat at ``doc`` status in the gap
measurement, which means the remake tree mentioned them and consumed none.

This test pins the contract that turns them into an engineering basis:

* a family is imported only when its manifest hash matches the pin, its status
  is ``accepted`` and every file it lists still hashes to what the manifest
  says -- each failure closes the import and names the family;
* the relocation rule set and the audit survive the import, so the region
  binding, the pointer-rewrite count and the capacity numbers are available
  locally;
* the writeback safety gate is derived from the audit's own summary and
  fails when a resource can no longer be written back at its original size,
  when the tightest original slot runs out of room, or when the family was
  measured against a different ROM;
* the import is deterministic, so a third party can re-run it and diff.

The fixture reverse tree is built inside the test.  The last test checks the
pinned table against the real reverse tree and is skipped when that tree is
not present.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.butano.import_rom_relocation_specs import (  # noqa: E402
    EXPECTED_BASE_ROM_SHA256,
    RELOCATION_FAMILIES,
    capacity_gate,
    import_families,
    main,
)
from tools.butano.import_rom_reverse_families import (  # noqa: E402
    EXIT_FAMILY_FILE_MISMATCH,
    EXIT_GATE_FAILED,
    EXIT_HASH_MISMATCH,
    EXIT_INPUT_ERROR,
    EXIT_STATUS_REJECTED,
    FamilyImportError,
    FamilySpec,
    as_specs,
    load_verified_manifest,
    sha256_file,
)

REVERSE_ROOT = Path("/Users/altair/github/gba-naruto-reverse")


@contextlib.contextmanager
def _quiet():
    """Swallow the importer's own output so the test log stays readable."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        yield buffer

FAMILY = "fake-family-writeback-v1"
SPEC_REL = "full-relocation-spec.json"
AUDIT_REL = "relocation-audit.json"


def _write_json(path: Path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return sha256_file(path)


def build_reverse_tree(
    root: Path,
    *,
    family: str = FAMILY,
    status: str = "accepted",
    summary: dict | None = None,
    base_rom_sha256: str = EXPECTED_BASE_ROM_SHA256,
) -> tuple[Path, FamilySpec]:
    """Build a synthetic reverse tree holding one relocation/writeback family."""
    family_dir = root / "artifacts" / family
    family_dir.mkdir(parents=True, exist_ok=True)

    spec = {
        "schema": f"{family}-relocation-v1",
        "base_rom_sha256": base_rom_sha256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region": "fake-region",
        "region_owner": "fake_owner",
        "region_registry": "sequel/image-resource-regions.json",
        "region_registry_sha256": "a" * 64,
        "source_catalog": "artifacts/fake-catalog-v1/manifest.json",
        "source_catalog_sha256": "b" * 64,
        "edits": [
            {"id": "resource-0", "expected_header_pointer_offsets": [1, 2]},
            {"id": "resource-1", "expected_header_pointer_offsets": [3]},
        ],
    }
    spec_path = family_dir / SPEC_REL
    spec_digest = _write_json(spec_path, spec)

    audit = {
        "schema": f"{family}-relocation-audit-v1",
        "base_rom": {"path": "rom/base.gba", "sha256": base_rom_sha256},
        "summary": summary if summary is not None else {
            "content_resource_count": 2,
            "logical_reference_count": 3,
            "physical_slot_count": 3,
            "minimum_original_slot_margin": 0,
            "minimum_mutation_slot_margin": -1,
            "mutation_overflow_slot_count": 1,
            "mutation_overflow_content_count": 1,
            "original_roundtrip_fit_content_count": 2,
            "original_roundtrip_fit_slot_count": 3,
            "unexpected_pointer_count": 0,
            "allocation_count": 2,
            "pointer_patch_count": 3,
        },
        "scope": {
            "proved": "every content resource round-trips at its original size",
            "guarded_in_place_importer_available": True,
        },
        "output_rom_sha256": "c" * 64,
    }
    audit_path = family_dir / AUDIT_REL
    audit_digest = _write_json(audit_path, audit)

    manifest = {
        "schema": "fake-promotion-v1",
        "artifact_id": family,
        "artifact_schema": f"{family}-relocation-audit-v1",
        "artifact_status": status,
        "base_rom_sha256": base_rom_sha256,
        "payload_file": AUDIT_REL,
        "files": {SPEC_REL: spec_digest, AUDIT_REL: audit_digest},
        "scope": {
            "proved": "the relocation covers every audited resource",
            "not_proved": "runtime pixel equivalence",
        },
        "verifier": {
            "command": ["python3", "tools/verify_fake.py", "--artifact",
                        f"artifacts/{family}"],
            "exit_code": 0,
        },
    }
    manifest_path = family_dir / "manifest.json"
    manifest_digest = _write_json(manifest_path, manifest)
    return root, FamilySpec(family=family, manifest_sha256=manifest_digest)


class RelocationImportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="relocation-import-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.reverse_root = self.tmp / "reverse"
        self.out_dir = self.tmp / "out"

    def _specs(self, spec: FamilySpec) -> tuple[FamilySpec, ...]:
        return (spec,)

    # -- success ---------------------------------------------------------
    def test_import_writes_the_rules_the_audit_and_a_receipt(self) -> None:
        reverse_root, spec = build_reverse_tree(self.reverse_root)
        index = import_families(reverse_root, self.out_dir, self._specs(spec))

        self.assertEqual(index["family_count"], 1)
        self.assertTrue(index["all_capacity_gates_hold"])
        receipt = index["families"][0]
        self.assertEqual(receipt["family"], FAMILY)
        self.assertEqual(receipt["kind"], "writeback")
        self.assertEqual(receipt["manifest_sha256"], spec.manifest_sha256)
        self.assertTrue(receipt["verifier"]["command"])

        self.assertTrue((self.out_dir / FAMILY / SPEC_REL).is_file())
        self.assertTrue((self.out_dir / FAMILY / AUDIT_REL).is_file())
        self.assertTrue((self.out_dir / FAMILY / "import.json").is_file())
        self.assertTrue((self.out_dir / "relocation-specs.json").is_file())

        # The rule set survived: region binding and pointer-rewrite count.
        self.assertEqual(receipt["rule_set"]["region"], "fake-region")
        self.assertEqual(receipt["rule_set"]["region_owner"], "fake_owner")
        self.assertEqual(receipt["rule_set"]["edit_count"], 2)
        self.assertEqual(receipt["rule_set"]["region_registry_sha256"], "a" * 64)

        # The audit survived, with the capacity numbers.
        self.assertEqual(receipt["audit"]["summary"]["pointer_patch_count"], 3)
        self.assertTrue(receipt["capacity_gate"]["holds"])
        self.assertEqual(
            receipt["capacity_gate"]["guarded_importer_flags"],
            ["guarded_in_place_importer_available"])

    def test_import_is_deterministic(self) -> None:
        reverse_root, spec = build_reverse_tree(self.reverse_root)
        first = self.tmp / "first"
        second = self.tmp / "second"
        import_families(reverse_root, first, self._specs(spec))
        import_families(reverse_root, second, self._specs(spec))

        first_files = sorted(
            path.relative_to(first).as_posix() for path in first.rglob("*")
            if path.is_file())
        second_files = sorted(
            path.relative_to(second).as_posix() for path in second.rglob("*")
            if path.is_file())
        self.assertEqual(first_files, second_files)
        for relative in first_files:
            self.assertEqual(
                sha256_file(first / relative), sha256_file(second / relative),
                f"{relative} differs between two runs of the same import")

    # -- fail closed -----------------------------------------------------
    def test_missing_manifest_fails_closed_and_names_the_family(self) -> None:
        spec = FamilySpec(family="absent-family-relocation-v1",
                          manifest_sha256="0" * 64)
        with self.assertRaises(FamilyImportError) as caught:
            import_families(self.reverse_root, self.out_dir, self._specs(spec))
        self.assertEqual(caught.exception.family, "absent-family-relocation-v1")
        self.assertEqual(caught.exception.exit_code, EXIT_INPUT_ERROR)
        self.assertIn("absent-family-relocation-v1", str(caught.exception))

    def test_manifest_hash_mismatch_fails_closed(self) -> None:
        reverse_root, spec = build_reverse_tree(self.reverse_root)
        manifest_path = reverse_root / "artifacts" / FAMILY / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["scope"]["proved"] = "tampered"
        _write_json(manifest_path, manifest)
        with self.assertRaises(FamilyImportError) as caught:
            import_families(reverse_root, self.out_dir, self._specs(spec))
        self.assertEqual(caught.exception.family, FAMILY)
        self.assertEqual(caught.exception.exit_code, EXIT_HASH_MISMATCH)

    def test_family_file_hash_mismatch_fails_closed(self) -> None:
        reverse_root, spec = build_reverse_tree(self.reverse_root)
        audit = reverse_root / "artifacts" / FAMILY / AUDIT_REL
        audit.write_text('{"schema": "tampered"}\n', encoding="utf-8")
        with self.assertRaises(FamilyImportError) as caught:
            import_families(reverse_root, self.out_dir, self._specs(spec))
        self.assertEqual(caught.exception.family, FAMILY)
        self.assertEqual(caught.exception.exit_code, EXIT_FAMILY_FILE_MISMATCH)
        self.assertIn(AUDIT_REL, str(caught.exception))

    def test_unaccepted_status_fails_closed(self) -> None:
        for status in ("candidate", "disproved", "superseded"):
            with self.subTest(status=status):
                reverse_root, spec = build_reverse_tree(
                    self.reverse_root, status=status)
                with self.assertRaises(FamilyImportError) as caught:
                    import_families(reverse_root, self.out_dir, self._specs(spec))
                self.assertEqual(caught.exception.family, FAMILY)
                self.assertEqual(caught.exception.exit_code, EXIT_STATUS_REJECTED)
                self.assertIn(status, str(caught.exception))

    # -- the capacity gate -----------------------------------------------
    def test_capacity_gate_rejects_a_broken_roundtrip(self) -> None:
        gate = capacity_gate(
            {"content_resource_count": 4, "original_roundtrip_fit_content_count": 3},
            {})
        self.assertFalse(gate["holds"])
        self.assertTrue(any("original_roundtrip_fit_content_count" in problem
                            for problem in gate["problems"]))

    def test_capacity_gate_rejects_a_negative_original_slot_margin(self) -> None:
        gate = capacity_gate({"minimum_original_slot_margin": -1}, {})
        self.assertFalse(gate["holds"])

    def test_capacity_gate_rejects_an_unaccounted_pointer(self) -> None:
        gate = capacity_gate({"unexpected_pointer_count": 2}, {})
        self.assertFalse(gate["holds"])

    def test_import_fails_the_gate_for_a_foreign_rom(self) -> None:
        reverse_root, spec = build_reverse_tree(
            self.reverse_root, base_rom_sha256="d" * 64)
        index = import_families(reverse_root, self.out_dir, self._specs(spec))
        self.assertFalse(index["all_capacity_gates_hold"])
        receipt = index["families"][0]
        self.assertFalse(receipt["base_rom_matches_project"])
        self.assertFalse(receipt["capacity_gate"]["holds"])

    # -- CLI -------------------------------------------------------------
    def test_cli_exits_non_zero_when_the_manifest_is_missing(self) -> None:
        with _quiet():
            code = main([
                "import",
                "--reverse-root", str(self.reverse_root),
                "--out-dir", str(self.out_dir),
            ])
        self.assertNotEqual(code, 0)
        self.assertEqual(code, EXIT_INPUT_ERROR)

    # -- the pinned table ------------------------------------------------
    def test_pinned_table_matches_the_reverse_tree(self) -> None:
        if not REVERSE_ROOT.is_dir():
            self.skipTest(f"reverse work tree not present: {REVERSE_ROOT}")
        specs = as_specs(RELOCATION_FAMILIES)
        self.assertEqual(len(specs), 22)
        for spec in specs:
            with self.subTest(family=spec.family):
                _path, manifest = load_verified_manifest(REVERSE_ROOT, spec)
                self.assertEqual(manifest["artifact_status"], "accepted")


if __name__ == "__main__":
    unittest.main()
