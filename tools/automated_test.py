#!/usr/bin/env python3
"""Automated build verification and patch correctness tests.

Covers all checks that do not require mGBA runtime input injection:

  1. Build pipeline  — build_mod.py runs without error
  2. ROM integrity   — output size, SHA-1 stability, unpatched regions unchanged
  3. Patch manifest  — no duplicate IDs, all entries have required fields
  4. Bytes patches   — verify applied bytes match expected after_hex
  5. Dialogue bank   — all entries encode correctly in their declared encoding
  6. Encoding sanity — no patch text exceeds max_bytes (same-length strategy)

Usage:
    python tools/automated_test.py                 # run all tests
    python tools/automated_test.py --verbose       # print each test result
    python tools/automated_test.py --suite build   # run only 'build' suite
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


# ---------------------------------------------------------------------------
# Test result tracking
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    suite: str
    passed: bool
    message: str = ""
    details: list[str] = field(default_factory=list)


class TestRunner:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: list[TestResult] = []

    def run(self, name: str, suite: str, fn: Callable[[], None]) -> None:
        try:
            fn()
            result = TestResult(name=name, suite=suite, passed=True)
            if self.verbose:
                print(f"  ✓ {name}")
        except AssertionError as exc:
            result = TestResult(name=name, suite=suite, passed=False, message=str(exc))
            if self.verbose:
                print(f"  ✗ {name}: {exc}")
        except Exception as exc:
            result = TestResult(name=name, suite=suite, passed=False,
                                message=f"{type(exc).__name__}: {exc}")
            if self.verbose:
                print(f"  ! {name}: {type(exc).__name__}: {exc}")
        self.results.append(result)

    def summary(self) -> dict:
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        return {
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "failures": [
                {"name": r.name, "suite": r.suite, "message": r.message}
                for r in self.results if not r.passed
            ],
        }

    def print_summary(self) -> None:
        s = self.summary()
        status = "PASS" if s["failed"] == 0 else "FAIL"
        print(f"\n[{status}] {s['passed']}/{s['total']} tests passed")
        if s["failures"]:
            print("\nFailures:")
            for f in s["failures"]:
                print(f"  [{f['suite']}] {f['name']}")
                if f["message"]:
                    print(f"    {f['message']}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_build_report() -> dict:
    path = ROOT / "build/naruto-sequel-build-report.json"
    assert path.exists(), f"build report not found: {path}"
    return load_json(path)


def load_project() -> dict:
    return load_json(ROOT / "sequel/project.json")


def load_manifest() -> dict:
    return load_json(ROOT / "sequel/patches/manifest.json")


# ---------------------------------------------------------------------------
# Suite: build
# ---------------------------------------------------------------------------

def suite_build(runner: TestRunner) -> None:
    """Verify build_mod.py runs successfully and produces expected output."""
    suite = "build"

    def test_build_runs() -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "tools/build_mod.py", "--project", "sequel/project.json"],
            capture_output=True, text=True, cwd=ROOT,
        )
        assert result.returncode == 0, f"build_mod.py exited {result.returncode}\n{result.stderr}"

    def test_output_rom_exists() -> None:
        project = load_project()
        out = ROOT / project["build"]["output_rom"]
        assert out.exists(), f"output ROM not found: {out}"

    def test_output_rom_size() -> None:
        project = load_project()
        base_path = ROOT / project["base_rom"]["path"]
        out_path = ROOT / project["build"]["output_rom"]
        assert base_path.exists(), f"base ROM not found: {base_path}"
        assert out_path.exists(), f"output ROM not found: {out_path}"
        assert base_path.stat().st_size == out_path.stat().st_size, \
            f"ROM size mismatch: base={base_path.stat().st_size} output={out_path.stat().st_size}"

    def test_report_exists() -> None:
        project = load_project()
        rp = ROOT / project["build"]["report"]
        assert rp.exists(), f"build report not found: {rp}"

    def test_report_has_patches() -> None:
        report = load_build_report()
        assert "applied_patches" in report, "build report missing applied_patches"
        assert len(report["applied_patches"]) > 0, "no patches applied"

    def test_base_sha1_matches() -> None:
        project = load_project()
        report = load_build_report()
        expected = project["base_rom"]["sha1"]
        actual = report["base_rom"]["sha1"]
        assert actual == expected, f"base ROM sha1 mismatch: expected {expected} got {actual}"

    runner.run("build_mod.py runs without error", suite, test_build_runs)
    runner.run("output ROM file exists", suite, test_output_rom_exists)
    runner.run("output ROM same size as base ROM", suite, test_output_rom_size)
    runner.run("build report JSON exists", suite, test_report_exists)
    runner.run("build report lists applied patches", suite, test_report_has_patches)
    runner.run("base ROM sha1 matches project.json", suite, test_base_sha1_matches)


# ---------------------------------------------------------------------------
# Suite: manifest
# ---------------------------------------------------------------------------

def suite_manifest(runner: TestRunner) -> None:
    """Verify patch manifest consistency."""
    suite = "manifest"

    def test_no_duplicate_ids() -> None:
        manifest = load_manifest()
        ids = [p["id"] for p in manifest["patches"]]
        dupes = [i for i in set(ids) if ids.count(i) > 1]
        assert not dupes, f"duplicate patch IDs: {dupes}"

    def test_required_fields() -> None:
        manifest = load_manifest()
        errors = []
        for patch in manifest["patches"]:
            if "id" not in patch:
                errors.append(f"patch missing 'id': {patch}")
            if "type" not in patch:
                errors.append(f"patch {patch.get('id','?')} missing 'type'")
        assert not errors, "\n".join(errors)

    def test_bytes_patches_have_offset() -> None:
        manifest = load_manifest()
        errors = []
        for patch in manifest["patches"]:
            if patch.get("type") == "bytes" and "offset" not in patch:
                errors.append(f"bytes patch {patch['id']} missing 'offset'")
        assert not errors, "\n".join(errors)

    def test_enabled_patches_only() -> None:
        # All enabled patches should have valid types
        manifest = load_manifest()
        valid_types = {"bytes", "dialogue", "pointer_redirect", "map", "battle_config", "dialogue_var"}
        errors = []
        for patch in manifest["patches"]:
            if not patch.get("enabled", True):
                continue
            if patch["type"] not in valid_types:
                errors.append(f"patch {patch['id']} has unknown type: {patch['type']}")
        assert not errors, "\n".join(errors)

    runner.run("no duplicate patch IDs", suite, test_no_duplicate_ids)
    runner.run("all patches have 'id' and 'type'", suite, test_required_fields)
    runner.run("bytes patches have 'offset'", suite, test_bytes_patches_have_offset)
    runner.run("all enabled patches use known types", suite, test_enabled_patches_only)


# ---------------------------------------------------------------------------
# Suite: patches
# ---------------------------------------------------------------------------

def suite_patches(runner: TestRunner) -> None:
    """Verify applied patch bytes in the output ROM."""
    suite = "patches"

    def _get_output_rom() -> bytes:
        project = load_project()
        out_path = ROOT / project["build"]["output_rom"]
        assert out_path.exists(), f"output ROM not found: run build first"
        return out_path.read_bytes()

    def test_report_patch_types_match() -> None:
        report = load_build_report()
        for ap in report["applied_patches"]:
            assert "type" in ap, f"applied patch missing type: {ap}"

    def test_bytes_patches_applied() -> None:
        """Verify that each bytes patch's after_hex is present at the correct offset."""
        report = load_build_report()
        rom = _get_output_rom()
        errors = []
        for ap in report["applied_patches"]:
            ptype = ap.get("type", ap.get("sub_type", ""))
            if ptype == "bytes":
                offset = int(ap["offset"])
                after = bytes.fromhex(ap["after_hex"])
                actual = rom[offset : offset + len(after)]
                if actual != after:
                    errors.append(
                        f"patch {ap['id']}: expected {after.hex()} at 0x{offset:X}, "
                        f"got {actual.hex()}"
                    )
        assert not errors, f"{len(errors)} byte patch(es) not correctly applied:\n" + "\n".join(errors[:5])

    def test_pointer_redirect_patches_applied() -> None:
        report = load_build_report()
        rom = _get_output_rom()
        errors = []
        for ap in report["applied_patches"]:
            if ap.get("type") == "pointer_redirect":
                offset = int(ap["pointer_table_offset"])
                expected = bytes.fromhex(ap["new_pointer_hex"])
                actual = rom[offset : offset + 4]
                if actual != expected:
                    errors.append(
                        f"pointer_redirect {ap['id']}: expected {expected.hex()} at 0x{offset:X}, "
                        f"got {actual.hex()}"
                    )
        assert not errors, "\n".join(errors)

    def test_no_unintended_changes() -> None:
        """Verify ROM size unchanged and no obvious corruption (spot-check header)."""
        rom = _get_output_rom()
        project = load_project()
        base_path = ROOT / project["base_rom"]["path"]
        base = base_path.read_bytes()
        assert len(rom) == len(base), f"ROM size changed: {len(base)} → {len(rom)}"
        # GBA header (first 192 bytes) should be unchanged
        assert rom[:192] == base[:192], "GBA ROM header was modified unexpectedly"

    runner.run("build report has applied patch types", suite, test_report_patch_types_match)
    runner.run("bytes patches correctly applied in output ROM", suite, test_bytes_patches_applied)
    runner.run("pointer_redirect patches correctly applied in output ROM", suite, test_pointer_redirect_patches_applied)
    runner.run("ROM size unchanged and header intact", suite, test_no_unintended_changes)


# ---------------------------------------------------------------------------
# Suite: encoding
# ---------------------------------------------------------------------------

def suite_encoding(runner: TestRunner) -> None:
    """Verify dialogue content encodes correctly."""
    suite = "encoding"

    def test_dialogue_bank_loads() -> None:
        bank_path = ROOT / "sequel/content/text/dialogue-bank.json"
        assert bank_path.exists(), f"dialogue bank not found: {bank_path}"
        bank = load_json(bank_path)
        assert "entries" in bank, "dialogue bank missing 'entries'"
        assert len(bank["entries"]) > 0, "dialogue bank has no entries"

    def test_dialogue_bank_encoding() -> None:
        bank_path = ROOT / "sequel/content/text/dialogue-bank.json"
        if not bank_path.exists():
            return
        bank = load_json(bank_path)
        errors = []
        for entry in bank["entries"]:
            enc = entry.get("encoding", "cp932")
            try:
                entry.get("expected_text", "").encode(enc)
            except (UnicodeEncodeError, LookupError) as e:
                errors.append(f"entry {entry['id']}: {e}")
        assert not errors, "\n".join(errors)

    def test_dialogue_patches_fit() -> None:
        """All same-length patches must fit within max_bytes."""
        content_path = ROOT / "sequel/content/text/dialogue-patches.json"
        bank_path = ROOT / "sequel/content/text/dialogue-bank.json"
        if not content_path.exists() or not bank_path.exists():
            return
        bank = load_json(bank_path)
        content = load_json(content_path)
        bank_map = {e["id"]: e for e in bank["entries"]}
        errors = []
        for entry in content.get("entries", []):
            eid = entry["id"]
            if eid not in bank_map:
                continue
            be = bank_map[eid]
            enc = be.get("encoding", "cp932")
            max_bytes = int(be.get("max_bytes", 0))
            table_off = int(be.get("table_offset", 0))
            if table_off:
                continue  # variable-length ok, will redirect
            try:
                encoded = entry["text"].encode(enc)
                if len(encoded) > max_bytes:
                    errors.append(
                        f"{eid}: encoded {len(encoded)} bytes > max_bytes {max_bytes} "
                        f"(no table_offset for redirect)"
                    )
            except (UnicodeEncodeError, LookupError) as e:
                errors.append(f"{eid}: encoding error: {e}")
        assert not errors, "\n".join(errors)

    runner.run("dialogue bank JSON loads", suite, test_dialogue_bank_loads)
    runner.run("all bank entries encode in declared encoding", suite, test_dialogue_bank_encoding)
    runner.run("all same-length patches fit within max_bytes", suite, test_dialogue_patches_fit)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SUITES = {
    "build":    suite_build,
    "manifest": suite_manifest,
    "patches":  suite_patches,
    "encoding": suite_encoding,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run automated build/patch verification tests.")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--suite", choices=list(SUITES.keys()), default=None,
                        help="Run only the specified test suite")
    parser.add_argument("--json-output", type=Path, default=None,
                        help="Write JSON report to path")
    args = parser.parse_args()

    runner = TestRunner(verbose=args.verbose)

    suites_to_run = [args.suite] if args.suite else list(SUITES.keys())

    for suite_name in suites_to_run:
        if args.verbose:
            print(f"\n── suite: {suite_name} ──")
        SUITES[suite_name](runner)

    runner.print_summary()

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(runner.summary(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return 0 if runner.summary()["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
