#!/usr/bin/env python3
"""The pixel-A/B families must be importable as local acceptance baselines.

The reverse work tree holds 32 closed pixel-A/B families; until now every one
of them sat at ``doc`` status in the gap measurement, which means the remake
tree mentioned them in prose and consumed none of them.  This test pins the
contract that turns them into a usable acceptance baseline:

* a family is imported only when its manifest hash matches the pin, its status
  is ``accepted`` and every file it lists still hashes to what the manifest
  says -- each failure closes the import and names the family;
* the import is deterministic, so a third party can re-run it and diff;
* the imported baseline frame is a real 1:1 acceptance gate: an identical
  frame passes, a different frame fails and reports the differing pixels.

The fixture reverse tree is built inside the test, so the failure modes are
exercised without depending on another work tree.  The last test checks the
pinned table against the real reverse tree and is skipped when that tree is
not present.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.butano.import_rom_pixel_ab_baselines import (  # noqa: E402
    check_rom_anchor,
    PIXEL_AB_FAMILIES,
    compare_against_import,
    compare_frames,
    import_families,
    main,
)
from tools.butano.import_rom_reverse_families import (  # noqa: E402
    EXIT_BASELINE_MISSING,
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

FAMILY = "fake-family-pixel-ab-v1"
BASELINE_REL = "raw/baseline/frame90.png"
CANDIDATE_REL = "raw/candidate/frame90.png"
EVIDENCE_REL = "runtime-evidence.json"


def _frame(pixel: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (240, 160), pixel)
    image.putpixel((12, 34), (255, 0, 0))
    return image


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
    baseline_pixel: tuple[int, int, int] = (0, 0, 0),
    candidate_pixel: tuple[int, int, int] = (0, 0, 0),
) -> tuple[Path, FamilySpec]:
    """Build a synthetic reverse tree holding one pixel-A/B family."""
    family_dir = root / "artifacts" / family
    family_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = family_dir / BASELINE_REL
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    _frame(baseline_pixel).save(baseline_path)
    candidate_path = family_dir / CANDIDATE_REL
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    _frame(candidate_pixel).save(candidate_path)

    evidence = {
        "schema": "fake-pixel-ab-runtime-v1",
        "verified": True,
        "input": {
            "path": "artifacts/runtime-checkpoints/scenario-41-battle-entry.ss9",
            "sha256": "0" * 64,
        },
        "runtime": {
            "pixels": {
                "baseline_rgb_sha256": "a" * 64,
                "candidate_rgb_sha256": "b" * 64,
                "bbox": [12, 34, 13, 35],
                "changes": [{"x": 12, "y": 34}],
                "count": 1,
            }
        },
    }
    evidence_path = family_dir / EVIDENCE_REL
    evidence_digest = _write_json(evidence_path, evidence)

    files = {
        BASELINE_REL: sha256_file(baseline_path),
        CANDIDATE_REL: sha256_file(candidate_path),
        EVIDENCE_REL: evidence_digest,
    }
    manifest = {
        "schema": "fake-promotion-v1",
        "artifact_id": family,
        "artifact_schema": "fake-pixel-ab-runtime-v1",
        "artifact_status": status,
        "base_rom_sha256": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
        "payload_file": EVIDENCE_REL,
        "files": files,
        "scope": {
            "proved": "one edited byte changes exactly one pixel",
            "not_proved": "physical GBA output",
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


class PixelAbImportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(
            __import__("tempfile").mkdtemp(prefix="pixel-ab-import-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.reverse_root = self.tmp / "reverse"
        self.out_dir = self.tmp / "out"

    def _specs(self, spec: FamilySpec) -> tuple[FamilySpec, ...]:
        return (spec,)

    # -- success ---------------------------------------------------------
    def test_import_writes_baseline_evidence_and_receipt(self) -> None:
        reverse_root, spec = build_reverse_tree(self.reverse_root)
        index = import_families(reverse_root, self.out_dir, self._specs(spec),
                                root=self.tmp)

        self.assertEqual(index["family_count"], 1)
        receipt = index["families"][0]
        self.assertEqual(receipt["family"], FAMILY)
        self.assertEqual(receipt["artifact_status"], "accepted")
        self.assertEqual(receipt["manifest_sha256"], spec.manifest_sha256)
        self.assertTrue(receipt["verifier"]["command"])
        self.assertIn("not_proved", receipt["scope"])

        self.assertTrue((self.out_dir / FAMILY / "baseline" / "frame90.png").is_file())
        self.assertTrue((self.out_dir / FAMILY / "evidence.json").is_file())
        self.assertTrue((self.out_dir / FAMILY / "import.json").is_file())
        self.assertTrue((self.out_dir / "baselines.json").is_file())

        # The imported baseline is byte-identical to the reverse-side frame.
        self.assertEqual(
            sha256_file(self.out_dir / FAMILY / "baseline" / "frame90.png"),
            sha256_file(reverse_root / "artifacts" / FAMILY / BASELINE_REL),
        )

        # The recorded pixel expectation survived the import.
        self.assertEqual(receipt["expectation"]["changed_pixel_count"], 1)
        self.assertEqual(receipt["expectation"]["bbox"], [12, 34, 13, 35])

    def test_import_is_deterministic(self) -> None:
        reverse_root, spec = build_reverse_tree(self.reverse_root)
        first = self.tmp / "first"
        second = self.tmp / "second"
        import_families(reverse_root, first, self._specs(spec), root=self.tmp)
        import_families(reverse_root, second, self._specs(spec), root=self.tmp)

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

    def test_reimport_leaves_foreign_files_alone(self) -> None:
        reverse_root, spec = build_reverse_tree(self.reverse_root)
        import_families(reverse_root, self.out_dir, self._specs(spec), root=self.tmp)
        stale = self.out_dir / FAMILY / "baseline" / "stale.png"
        stale.write_bytes(b"stale")
        import_families(reverse_root, self.out_dir, self._specs(spec), root=self.tmp)
        self.assertTrue(stale.is_file())  # foreign files are never removed

    # -- fail closed -----------------------------------------------------
    def test_missing_manifest_fails_closed_and_names_the_family(self) -> None:
        spec = FamilySpec(family="absent-family-pixel-ab-v1", manifest_sha256="0" * 64)
        with self.assertRaises(FamilyImportError) as caught:
            import_families(self.reverse_root, self.out_dir, self._specs(spec))
        self.assertEqual(caught.exception.family, "absent-family-pixel-ab-v1")
        self.assertEqual(caught.exception.exit_code, EXIT_INPUT_ERROR)
        self.assertIn("absent-family-pixel-ab-v1", str(caught.exception))

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
        self.assertIn("manifest sha256 mismatch", str(caught.exception))

    def test_family_file_hash_mismatch_fails_closed(self) -> None:
        reverse_root, spec = build_reverse_tree(self.reverse_root)
        baseline = reverse_root / "artifacts" / FAMILY / BASELINE_REL
        baseline.write_bytes(b"not the frame the manifest describes")
        with self.assertRaises(FamilyImportError) as caught:
            import_families(reverse_root, self.out_dir, self._specs(spec))
        self.assertEqual(caught.exception.family, FAMILY)
        self.assertEqual(caught.exception.exit_code, EXIT_FAMILY_FILE_MISMATCH)
        self.assertIn(BASELINE_REL, str(caught.exception))

    def test_a_tampered_rom_anchor_is_rejected(self) -> None:
        """The content-equivalence acceptance has to bite.

        A pair that was produced by editing this ROM at this place must stop
        being accepted the moment the ROM at that place changes.
        """
        rom = bytearray((ROOT / "rom" / "base.gba").read_bytes())
        anchor = {"kind": "byte", "offsets": [5528266], "baseline_value": 1}
        self.assertEqual(check_rom_anchor(bytes(rom), anchor), [])
        rom[5528266] = 2
        problems = check_rom_anchor(bytes(rom), anchor)
        self.assertTrue(problems)
        self.assertIn("5528266", problems[0])

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

    def test_family_without_a_baseline_frame_fails_closed(self) -> None:
        reverse_root = self.reverse_root
        family_dir = reverse_root / "artifacts" / FAMILY
        family_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = family_dir / EVIDENCE_REL
        digest = _write_json(evidence_path, {"schema": "x", "verified": True})
        manifest_path = family_dir / "manifest.json"
        manifest_digest = _write_json(manifest_path, {
            "artifact_id": FAMILY,
            "artifact_status": "accepted",
            "payload_file": EVIDENCE_REL,
            "files": {EVIDENCE_REL: digest},
        })
        with self.assertRaises(FamilyImportError) as caught:
            import_families(reverse_root, self.out_dir,
                            (FamilySpec(family=FAMILY,
                                        manifest_sha256=manifest_digest),))
        self.assertEqual(caught.exception.exit_code, EXIT_BASELINE_MISSING)

    # -- comparison entry point -----------------------------------------
    def test_compare_reports_a_difference_and_fails(self) -> None:
        reverse_root, spec = build_reverse_tree(
            self.reverse_root, baseline_pixel=(0, 0, 0), candidate_pixel=(9, 9, 9))
        import_families(reverse_root, self.out_dir, self._specs(spec), root=self.tmp)
        candidate = self.tmp / "candidate.png"
        _frame((9, 9, 9)).save(candidate)
        result = compare_against_import(self.out_dir, FAMILY, candidate)
        self.assertFalse(result["identical"])
        self.assertGreater(result["different_pixels"], 0)
        self.assertIsNotNone(result["difference_bbox"])

    def test_compare_accepts_an_identical_frame(self) -> None:
        reverse_root, spec = build_reverse_tree(
            self.reverse_root, baseline_pixel=(4, 5, 6))
        import_families(reverse_root, self.out_dir, self._specs(spec), root=self.tmp)
        candidate = self.tmp / "candidate.png"
        _frame((4, 5, 6)).save(candidate)
        result = compare_against_import(self.out_dir, FAMILY, candidate)
        self.assertTrue(result["identical"])
        self.assertEqual(result["different_pixels"], 0)

    def test_compare_of_an_unknown_family_fails_closed(self) -> None:
        reverse_root, spec = build_reverse_tree(self.reverse_root)
        import_families(reverse_root, self.out_dir, self._specs(spec), root=self.tmp)
        candidate = self.tmp / "candidate.png"
        _frame((0, 0, 0)).save(candidate)
        with self.assertRaises(FamilyImportError) as caught:
            compare_against_import(self.out_dir, "not-imported-pixel-ab-v1", candidate)
        self.assertEqual(caught.exception.family, "not-imported-pixel-ab-v1")

    # -- CLI -------------------------------------------------------------
    def test_cli_exits_non_zero_when_the_manifest_is_missing(self) -> None:
        with _quiet():
            code = main([
                "import",
                "--reverse-root", str(self.reverse_root),
                "--out-dir", str(self.out_dir),
                "--root", str(self.tmp),
            ])
        self.assertNotEqual(code, 0)
        self.assertEqual(code, EXIT_INPUT_ERROR)

    def test_cli_compare_exits_non_zero_on_a_difference(self) -> None:
        reverse_root, spec = build_reverse_tree(
            self.reverse_root, baseline_pixel=(0, 0, 0))
        import_families(reverse_root, self.out_dir, self._specs(spec), root=self.tmp)
        candidate = self.tmp / "candidate.png"
        _frame((1, 1, 1)).save(candidate)
        with _quiet():
            code = main([
                "compare",
                "--out-dir", str(self.out_dir),
                "--family", FAMILY,
                "--candidate", str(candidate),
            ])
        self.assertEqual(code, EXIT_GATE_FAILED)

    # -- the pinned table ------------------------------------------------
    def test_pinned_table_matches_the_reverse_tree(self) -> None:
        if not REVERSE_ROOT.is_dir():
            self.skipTest(f"reverse work tree not present: {REVERSE_ROOT}")
        specs = as_specs(PIXEL_AB_FAMILIES)
        self.assertEqual(len(specs), 35)
        for spec in specs:
            with self.subTest(family=spec.family):
                _path, manifest = load_verified_manifest(REVERSE_ROOT, spec)
                self.assertEqual(manifest["artifact_status"], "accepted")

    def test_imported_baselines_reproduce_the_recorded_pixel_expectation(self) -> None:
        """The imported baseline is the frame the reverse side measured.

        For every family, the imported baseline compared against the reverse
        side's edited frame must differ in exactly the number of pixels the
        reverse side recorded.  A baseline that is off by one pixel, or a
        comparison rule that undercounts, would break this.
        """
        if not REVERSE_ROOT.is_dir():
            self.skipTest(f"reverse work tree not present: {REVERSE_ROOT}")
        specs = as_specs(PIXEL_AB_FAMILIES)
        index = import_families(REVERSE_ROOT, self.out_dir, specs, root=self.tmp)
        checked = 0
        for entry in index["families"]:
            family = entry["family"]
            manifest = json.loads(
                (REVERSE_ROOT / "artifacts" / family / "manifest.json")
                .read_text(encoding="utf-8"))
            candidates = [
                relative for relative in manifest["files"]
                if relative.lower().endswith(".png") and "candidate" in relative.lower()
            ]
            if not candidates:
                continue
            with self.subTest(family=family):
                expectation = entry["expectation"]
                count = expectation.get("changed_pixel_count")
                if count is None:
                    # Not every A/B pair is a pixel pair.  Some edit a ROM
                    # data byte or a code halfword, and then the frames are
                    # evidence of the edit rather than its measurement.  The
                    # acceptance is content equivalence: the recorded offset
                    # must still hold the recorded baseline value in *this*
                    # tree's base ROM, which anchors the pair to the ROM the
                    # remake builds from.
                    anchor = expectation.get("rom_anchor")
                    self.assertIsNotNone(
                        anchor,
                        f"{family}: no pixel expectation and no ROM anchor, so "
                        f"the pair has no acceptance at all")
                    rom = (ROOT / "rom" / "base.gba").read_bytes()
                    problems = check_rom_anchor(rom, anchor)
                    self.assertEqual(
                        problems, [],
                        f"{family}: the base ROM does not hold the recorded "
                        f"baseline value at the recorded offset")
                    checked += 1
                    continue
                baseline = self.out_dir / entry["baseline_images"][0]["path"]
                result = compare_frames(
                    baseline, REVERSE_ROOT / "artifacts" / family / candidates[0])
                self.assertEqual(
                    result["different_pixels"],
                    count,
                    f"{family}: the imported baseline does not reproduce the "
                    f"recorded pixel difference")
                checked += 1
        self.assertEqual(checked, len(specs))


if __name__ == "__main__":
    unittest.main()
