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
import sqlite3
import struct
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


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


from tools.lib import load_json


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
# Suite: editor DB patch integrity
# ---------------------------------------------------------------------------

# Generator/table pairs are deliberately explicit.  This makes a schema rename
# visible in review and, more importantly, prevents generators from silently
# returning [] after catching sqlite3.OperationalError for a misspelled table.
ROM_TABLE_GENERATORS = {
    "rom_battle_encounters": "generate_battle_encounter_patches",
    "rom_battle_handlers": "generate_battle_handler_patches",
    "rom_character_stats_b": "generate_character_stats_b_patches",
    "rom_cutscene_scripts": "generate_cutscene_script_patches",
    "rom_data_table_a": "generate_data_table_a_patches",
    "rom_data_table_b": "generate_data_table_b_patches",
    "rom_fonts": "generate_font_patches",
    "rom_function_pointers": "generate_function_pointer_patches",
    "rom_map_events": "generate_map_event_patches",
    "rom_map_sprites": "generate_map_sprite_patches",
    "rom_menu_ui": "generate_menu_ui_patches",
    "rom_palettes": "generate_palette_patches",
    "rom_resource_pointers": "generate_resource_pointer_patches",
    "rom_save_state": "generate_save_state_patches",
    "rom_sprite_animations": "generate_sprite_animation_patches",
    "rom_story_b": "generate_story_b_patches",
    "rom_story_c": "generate_story_c_patches",
    "rom_story_d": "generate_story_d_patches",
    "rom_story_e": "generate_story_e_patches",
    "rom_tile_assets": "generate_tile_asset_patches",
}


def suite_db_integrity(runner: TestRunner) -> None:
    """Guard the boundary between game-effective and audit-only DB writes."""
    suite = "db_integrity"

    def test_audit_patches_never_reported_real() -> None:
        report = load_build_report()
        errors = []
        for patch in report.get("applied_patches", []):
            if patch.get("patch_source") != "db_real":
                continue
            offset = int(patch.get("offset", -1))
            description = str(patch.get("description", "")).lower()
            if offset >= 0x5E0000 or "audit trail" in description:
                errors.append(
                    f"{patch.get('id', '?')}: db_real points to audit-only data "
                    f"at 0x{offset:X} ({patch.get('db_table', '?')})"
                )
        assert not errors, (
            "audit-only patches must use patch_source=db_audit, never db_real:\n"
            + "\n".join(errors[:20])
        )

    def test_populated_rom_tables_have_generator_output() -> None:
        from tools import build_db_patches

        db_path = ROOT / "sequel/editor.db"
        if not db_path.exists():
            # editor.db is intentionally ignored; clean checkouts verify the
            # wrappers through unit tests instead of a local mutable database.
            return
        conn = sqlite3.connect(str(db_path))
        try:
            existing = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            errors = []
            for table, generator_name in ROM_TABLE_GENERATORS.items():
                if table not in existing:
                    continue
                row_count = int(
                    conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                )
                if row_count == 0:
                    continue
                generator = getattr(build_db_patches, generator_name)
                patches = generator(db_path)
                byte_patches = [p for p in patches if p.get("type") == "bytes"]
                if not byte_patches:
                    errors.append(
                        f"{generator_name}: returned no byte patches for "
                        f"{table} ({row_count} rows); check the queried table name"
                    )
        finally:
            conn.close()
        assert not errors, "generator silent no-op(s):\n" + "\n".join(errors)

    def test_report_db_statistics_match_rows() -> None:
        report = load_build_report()
        stats = report.get("patch_statistics")
        assert isinstance(stats, dict), "build report missing patch_statistics"

        class_counts = report.get("patch_class_counts")
        assert isinstance(class_counts, dict), "build report missing patch_class_counts"

        actual_real = sum(
            p.get("patch_source") == "db_real"
            for p in report.get("applied_patches", [])
        )
        actual_audit = sum(
            p.get("patch_source") == "db_audit"
            for p in report.get("applied_patches", [])
        )
        assert stats.get("db_real") == actual_real, (
            f"patch_statistics.db_real={stats.get('db_real')!r}, "
            f"but applied_patches contains {actual_real} db_real rows"
        )
        assert stats.get("db_audit") == actual_audit, (
            f"patch_statistics.db_audit={stats.get('db_audit')!r}, "
            f"but applied_patches contains {actual_audit} db_audit rows"
        )
        actual_effective = sum(
            p.get("patch_class") == "game_effective"
            for p in report.get("applied_patches", [])
        )
        actual_class_audit = sum(
            p.get("patch_class") == "audit"
            for p in report.get("applied_patches", [])
        )
        assert class_counts.get("game_effective") == actual_effective, (
            f"patch_class_counts.game_effective="
            f"{class_counts.get('game_effective')!r}, but applied_patches contains "
            f"{actual_effective} game_effective rows"
        )
        assert class_counts.get("audit") == actual_class_audit, (
            f"patch_class_counts.audit={class_counts.get('audit')!r}, "
            f"but applied_patches contains {actual_class_audit} audit rows"
        )

        bad_source_classes = [
            p.get("id", "?") for p in report.get("applied_patches", [])
            if (p.get("patch_source") == "db_real"
                and p.get("patch_class") != "game_effective")
            or (p.get("patch_source") == "db_audit"
                and p.get("patch_class") != "audit")
        ]
        assert not bad_source_classes, (
            "DB patch source/class disagreement: " + ", ".join(bad_source_classes[:20])
        )

    def test_db_real_report_bytes_match_base_and_output() -> None:
        """The report must be evidence about both immutable input and final output."""
        report = load_build_report()
        project = load_project()
        base = (ROOT / project["base_rom"]["path"]).read_bytes()
        output = (ROOT / project["build"]["output_rom"]).read_bytes()
        errors = []
        for patch in report.get("applied_patches", []):
            if patch.get("patch_source") != "db_real" or patch.get("type") != "bytes":
                continue
            patch_id = patch.get("id", "?")
            offset = int(patch.get("offset", -1))
            try:
                before = bytes.fromhex(patch["before_hex"])
                after = bytes.fromhex(patch["after_hex"])
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"{patch_id}: malformed byte evidence: {exc}")
                continue
            if offset < 0 or offset + len(after) > len(output):
                errors.append(f"{patch_id}: invalid output offset 0x{offset:X}")
                continue
            if len(before) != len(after):
                errors.append(
                    f"{patch_id}: before/after lengths differ "
                    f"({len(before)} != {len(after)})"
                )
                continue
            if base[offset : offset + len(before)] != before:
                errors.append(
                    f"{patch_id}: before_hex does not match immutable base at 0x{offset:X}"
                )
            if output[offset : offset + len(after)] != after:
                errors.append(
                    f"{patch_id}: after_hex does not match final ROM at 0x{offset:X}"
                )
        assert not errors, "DB real byte-fidelity failure(s):\n" + "\n".join(errors[:20])

    def test_safety_gate_rejects_wrong_offset_and_polluted_precondition() -> None:
        """Regression probes for two historical ways to manufacture false proof."""
        from tools.patch_safety import PatchSafetyGate

        base = bytes.fromhex("10203040")
        cases = [
            # Correct precondition bytes, deliberately attached to the wrong offset.
            {"id": "wrong_offset", "offset": 1, "before_hex": "10", "after_hex": "aa"},
            # before_hex copied from an already-patched/development buffer, not base.
            {"id": "polluted_buffer", "offset": 2, "before_hex": "99", "after_hex": "bb"},
        ]
        accepted = []
        for patch in cases:
            try:
                PatchSafetyGate(base).register(patch, patch_class="game_effective")
            except ValueError:
                continue
            accepted.append(patch["id"])
        assert not accepted, (
            "safety gate accepted invalid byte evidence: " + ", ".join(accepted)
        )

    runner.run("audit-only patches are never labelled db_real", suite,
               test_audit_patches_never_reported_real)
    runner.run("populated rom_* tables cannot silently generate no patches", suite,
               test_populated_rom_tables_have_generator_output)
    runner.run("build report DB statistics match applied patch rows", suite,
               test_report_db_statistics_match_rows)
    runner.run("db_real report bytes match immutable base and final ROM", suite,
               test_db_real_report_bytes_match_base_and_output)
    runner.run("safety gate rejects wrong offsets and polluted preconditions", suite,
               test_safety_gate_rejects_wrong_offset_and_polluted_precondition)


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
    "db_integrity": suite_db_integrity,
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
