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
import tempfile
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


# The build suite builds into an isolated directory so a test run never
# overwrites the committed build artifact.  The committed ROM/report were
# produced with sequel/editor.db present; rebuilding without that DB drops
# every editor-db-derived patch, which would silently degrade a tracked file.
BUILD_OUTPUT_DIR = "build/automated-test-build"


def build_output_paths() -> tuple[Path, Path]:
    """(output ROM path, build report path) of the isolated test build."""
    project = load_project()
    out_dir = ROOT / BUILD_OUTPUT_DIR
    return (
        out_dir / "naruto-sequel-dev.gba",
        out_dir / "naruto-sequel-build-report.json",
    )


def load_build_report() -> dict:
    path = build_output_paths()[1]
    if not path.exists():
        path = ROOT / "build/naruto-sequel-build-report.json"
    assert path.exists(), f"build report not found: {path}"
    return load_json(path)


def ensure_isolated_build() -> Path:
    """Build into the isolated directory if it has not been done yet.

    The committed report under build/ may be stale (it was produced with a
    full editor DB, which is not part of the repository), so the process
    checks must read a report produced by *this* run.
    """
    import os
    import subprocess

    _, report = build_output_paths()
    if not report.exists():
        env = {
            **os.environ,
            "BUILD_OUTPUT_DIR": BUILD_OUTPUT_DIR,
            # the child prints UTF-8 Chinese; a GBK console would fail to decode
            "PYTHONIOENCODING": "utf-8",
        }
        result = subprocess.run(
            [sys.executable, "tools/build_mod.py", "--project", "sequel/project.json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=ROOT, env=env,
        )
        assert result.returncode == 0, (
            f"build_mod.py exited {result.returncode}\n{result.stderr}")
    return report


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
        import os
        import subprocess
        env = {
            **os.environ,
            "BUILD_OUTPUT_DIR": BUILD_OUTPUT_DIR,
            "PYTHONIOENCODING": "utf-8",
        }
        result = subprocess.run(
            [sys.executable, "tools/build_mod.py", "--project", "sequel/project.json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=ROOT, env=env,
        )
        assert result.returncode == 0, f"build_mod.py exited {result.returncode}\n{result.stderr}"

    def test_output_rom_exists() -> None:
        out, _ = build_output_paths()
        assert out.exists(), f"output ROM not found: {out}"

    def test_output_rom_size() -> None:
        project = load_project()
        base_path = ROOT / project["base_rom"]["path"]
        out_path, _ = build_output_paths()
        assert base_path.exists(), f"base ROM not found: {base_path}"
        assert out_path.exists(), f"output ROM not found: {out_path}"
        assert base_path.stat().st_size == out_path.stat().st_size, \
            f"ROM size mismatch: base={base_path.stat().st_size} output={out_path.stat().st_size}"

    def test_report_exists() -> None:
        _, rp = build_output_paths()
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

# Generators whose table identity was **falsified** by the registry
# (``tools/table_registry.py::CONFLICTS``).  Their base address is a window
# inside a table the ROM really reads, so the generator must refuse to write
# instead of emitting byte patches.  The refusal record is the contract; a
# silent byte patch here would corrupt live data.
FALSIFIED_ALIAS_GENERATORS = {
    "rom_palettes": "generate_palette_patches",
    "rom_resource_pointers": "generate_resource_pointer_patches",
}

# Schema of the synthetic editor database used by
# ``test_populated_rom_tables_have_generator_output``.  ``sequel/editor.db``
# is gitignored, so the real database is not available in a clean checkout;
# the synthetic one reproduces the contract each generator depends on: the
# table name, the column names, the row count and the ``_rom_offset`` values.
#   (table, [(column, kind)], base, count, stride)
# kind: "thumb" -> odd ROM pointer, "data" -> even ROM pointer,
#       "raw"   -> any ROM pointer, "byte" -> 0..255, "word" -> 0..65535
SYNTHETIC_ROM_TABLES: tuple[tuple[str, list[tuple[str, str]], int, int, int], ...] = (
    ("rom_battle_encounters", [("entry", "raw")], 0x542384, 38, 4),
    ("rom_battle_handlers", [("handler_ptr", "thumb")], 0x53E6D8, 14, 4),
    ("rom_character_stats_b", [("hp", "word"), ("padding1", "byte"),
                               ("padding2", "byte"), ("padding3", "byte"),
                               ("max_value", "word"), ("char_type", "byte"),
                               ("attack", "word"), ("defense", "word")],
     0x545200, 18, 16),
    ("rom_cutscene_scripts", [("gfx_ptr", "data"), ("palette_ptr", "data")],
     0x53DF70, 4, 8),
    ("rom_data_table_a", [("data_ptr", "data")], 0x5A14A4, 20, 4),
    ("rom_data_table_b", [("data_ptr", "data")], 0x5A2120, 20, 4),
    ("rom_fonts", [("char_width", "byte")], 0x53E5B4, 256, 1),
    ("rom_function_pointers", [("func_ptr", "thumb")], 0x53D5F4, 11, 4),
    ("rom_map_events", [("handler_ptr", "thumb")], 0x53EB08, 47, 4),
    ("rom_map_sprites", [("sprite_ptr", "data")], 0x53F140, 86, 4),
    ("rom_menu_ui", [("ui_ptr", "data")], 0x5A5774, 20, 4),
    ("rom_palettes", [("palette_ptr", "data")], 0x53F138, 88, 4),
    ("rom_resource_pointers", [("resource_ptr", "data")], 0x596F0C, 20, 4),
    ("rom_save_state", [("ewram_buffer", "word"), ("sram_offset_field", "word")],
     0x53D848, 10, 8),
    ("rom_sprite_animations", [("frames_ptr", "data"), ("animations_ptr", "data"),
                               ("gfx_ptr", "data"), ("palette_ptr", "data")],
     0x596CCC, 576, 16),
    ("rom_story_b", [("chapter_ptr", "rom")], 0x536BC8, 11, 4),
    ("rom_story_c", [("chapter_ptr", "rom")], 0x538FF0, 11, 4),
    ("rom_story_d", [("chapter_ptr", "rom")], 0x53AB78, 11, 4),
    ("rom_story_e", [("chapter_ptr", "rom")], 0x53C3C0, 9, 4),
    ("rom_tile_assets", [("tile_ptr", "data")], 0x5A3218, 6, 4),
)


def build_synthetic_editor_db(path: Path) -> None:
    """Create a populated editor database with the real table contract."""
    conn = sqlite3.connect(str(path))
    for table, columns, base, count, stride in SYNTHETIC_ROM_TABLES:
        ddl = ", ".join(f'"{name}" INTEGER' for name, _ in columns)
        conn.execute(
            f'CREATE TABLE "{table}" (_idx INTEGER PRIMARY KEY, '
            f'_rom_offset INTEGER NOT NULL, {ddl})'
        )
        for index in range(count):
            values = []
            for position, (_, kind) in enumerate(columns):
                if kind == "thumb":
                    values.append(0x08001235 + index * 4)
                elif kind == "data":
                    values.append(0x0812F000 + index * 4 + position * 16)
                elif kind == "raw":
                    values.append(0x0812F000 + index * 4)
                elif kind == "rom":
                    values.append(0x0812F400 + index * 4)
                elif kind == "byte":
                    values.append(8 + position)
                else:                       # word
                    values.append(100 + index)
            conn.execute(
                f'INSERT INTO "{table}" VALUES (?, ?, '
                + ", ".join("?" for _ in columns) + ")",
                (index, base + index * stride, *values),
            )
    conn.commit()
    conn.close()


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
        errors = []
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            try:
                existing = {
                    row[0] for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
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
                    if table in FALSIFIED_ALIAS_GENERATORS:
                        # A falsified identity must refuse, never write.
                        if byte_patches:
                            errors.append(
                                f"{generator_name}: wrote {len(byte_patches)} byte "
                                f"patch(es) for the falsified table {table}"
                            )
                        continue
                    if not byte_patches:
                        errors.append(
                            f"{generator_name}: returned no byte patches for "
                            f"{table} ({row_count} rows); check the queried table name"
                        )
            finally:
                conn.close()
        else:
            # sequel/editor.db is gitignored, so on a clean checkout the real
            # database does not exist.  A synthetic one with the same contract
            # keeps the check meaningful everywhere.
            with tempfile.TemporaryDirectory() as tmp:
                synthetic = Path(tmp) / "editor.db"
                build_synthetic_editor_db(synthetic)
                for table, generator_name in ROM_TABLE_GENERATORS.items():
                    generator = getattr(build_db_patches, generator_name)
                    patches = generator(synthetic)
                    byte_patches = [p for p in patches if p.get("type") == "bytes"]
                    if table in FALSIFIED_ALIAS_GENERATORS:
                        if byte_patches:
                            errors.append(
                                f"{generator_name}: wrote {len(byte_patches)} byte "
                                f"patch(es) for the falsified table {table}"
                            )
                        elif not patches:
                            errors.append(
                                f"{generator_name}: returned nothing at all for the "
                                f"falsified table {table}; it must refuse explicitly"
                            )
                        continue
                    if not byte_patches:
                        errors.append(
                            f"{generator_name}: returned no byte patches for "
                            f"{table}; check the queried table name"
                        )
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
        """Every bank entry must declare an encoding the codec supports, and
        the text the ROM actually stores must re-encode to the exact original
        bytes.  The second half is what catches a wrong encoding: a bank that
        claims cp932 for font-coded bytes round-trips by accident, but a bank
        whose text cannot be re-encoded at all cannot."""
        from tools import text_codec

        bank_path = ROOT / "sequel/content/text/dialogue-bank.json"
        if not bank_path.exists():
            return
        bank = load_json(bank_path)
        mapping = None
        errors = []
        for entry in bank["entries"]:
            enc = entry.get("encoding", text_codec.FONT_ENCODING)
            text = entry.get("expected_text", "")
            try:
                if enc == text_codec.FONT_ENCODING:
                    if mapping is None:
                        mapping, _ = text_codec.load_mapping()
                    text_codec.encode(text, enc, mapping)
                else:
                    text.encode(enc)
            except (UnicodeEncodeError, LookupError, KeyError, FileNotFoundError) as e:
                errors.append(f"entry {entry['id']}: {e}")
        assert not errors, "\n".join(errors)

    def test_dialogue_bank_matches_rom() -> None:
        """The bank's expected_hex must still be the ROM's bytes, and the ROM's
        own text must re-encode to exactly those bytes."""
        from tools import text_codec

        bank_path = ROOT / "sequel/content/text/dialogue-bank.json"
        if not bank_path.exists():
            return
        try:
            rom_path = text_codec.resolve_rom()
        except FileNotFoundError:
            return
        rom = rom_path.read_bytes()
        mapping, _ = text_codec.load_mapping(rom_path)
        bank = load_json(bank_path)
        errors = []
        for entry in bank["entries"]:
            offset = int(entry["offset"])
            max_bytes = int(entry["max_bytes"])
            actual = rom[offset:offset + max_bytes]
            if entry.get("expected_hex", "").lower() != actual.hex():
                errors.append(
                    f"entry {entry['id']}: expected_hex does not match ROM at "
                    f"0x{offset:X} (rom has {actual.hex()})"
                )
                continue
            if entry.get("encoding") != text_codec.FONT_ENCODING:
                continue
            text, _ = text_codec.decode_bounded(rom, offset, max_bytes, mapping)
            try:
                encoded = text_codec.encode(text, text_codec.FONT_ENCODING, mapping)
            except KeyError as e:
                errors.append(f"entry {entry['id']}: ROM text not encodable: {e}")
                continue
            if encoded != actual[:len(encoded)]:
                errors.append(
                    f"entry {entry['id']}: re-encoded ROM text does not match "
                    f"the ROM bytes"
                )
        assert not errors, "\n".join(errors)

    def test_dialogue_patches_fit() -> None:
        """All same-length patches must fit within max_bytes."""
        from tools import text_codec

        content_path = ROOT / "sequel/content/text/dialogue-patches.json"
        bank_path = ROOT / "sequel/content/text/dialogue-bank.json"
        if not content_path.exists() or not bank_path.exists():
            return
        bank = load_json(bank_path)
        content = load_json(content_path)
        bank_map = {e["id"]: e for e in bank["entries"]}
        mapping = None
        errors = []
        for entry in content.get("entries", []):
            eid = entry["id"]
            if eid not in bank_map:
                continue
            be = bank_map[eid]
            enc = be.get("encoding", text_codec.FONT_ENCODING)
            max_bytes = int(be.get("max_bytes", 0))
            table_off = int(be.get("table_offset", 0))
            if table_off:
                continue  # variable-length ok, will redirect
            try:
                if enc == text_codec.FONT_ENCODING:
                    if mapping is None:
                        mapping, _ = text_codec.load_mapping()
                    encoded = text_codec.encode(entry["text"], enc, mapping)
                else:
                    encoded = entry["text"].encode(enc)
                if len(encoded) > max_bytes:
                    errors.append(
                        f"{eid}: encoded {len(encoded)} bytes > max_bytes {max_bytes} "
                        f"(no table_offset for redirect)"
                    )
            except (UnicodeEncodeError, LookupError, KeyError, FileNotFoundError) as e:
                errors.append(f"{eid}: encoding error: {e}")
        assert not errors, "\n".join(errors)

    def test_dialogue_patches_render() -> None:
        """What the build writes must read back as the authored text.

        This is the check the original cp932 pipeline could not pass: the
        bytes landed, but the game drew something else."""
        from tools import text_codec

        content_path = ROOT / "sequel/content/text/dialogue-patches.json"
        bank_path = ROOT / "sequel/content/text/dialogue-bank.json"
        if not content_path.exists() or not bank_path.exists():
            return
        try:
            rom_path = text_codec.resolve_rom()
        except FileNotFoundError:
            return
        mapping, _ = text_codec.load_mapping(rom_path)
        bank = load_json(bank_path)
        bank_map = {e["id"]: e for e in bank["entries"]}
        content = load_json(content_path)
        errors = []
        for entry in content.get("entries", []):
            eid = entry["id"]
            be = bank_map.get(eid)
            if be is None or be.get("encoding") != text_codec.FONT_ENCODING:
                continue
            max_bytes = int(be.get("max_bytes", 0))
            try:
                encoded = text_codec.encode(entry["text"], text_codec.FONT_ENCODING, mapping)
            except KeyError as e:
                errors.append(f"{eid}: not encodable: {e}")
                continue
            if len(encoded) > max_bytes:
                continue  # handled by the fit test
            rendered = text_codec.decode(encoded, mapping)
            if rendered != entry["text"]:
                errors.append(
                    f"{eid}: renders as {rendered!r}, authored {entry['text']!r}"
                )
        assert not errors, "\n".join(errors)

    runner.run("dialogue bank JSON loads", suite, test_dialogue_bank_loads)
    runner.run("all bank entries encode in declared encoding", suite, test_dialogue_bank_encoding)
    runner.run("dialogue bank matches the ROM byte for byte", suite, test_dialogue_bank_matches_rom)
    runner.run("all same-length patches fit within max_bytes", suite, test_dialogue_patches_fit)
    runner.run("patched dialogue renders as the authored text", suite, test_dialogue_patches_render)


# ---------------------------------------------------------------------------
# Suite: process  (M1-M4, absorbed from the third-party package)
# ---------------------------------------------------------------------------

def suite_process(runner: TestRunner) -> None:
    """The process improvements we adopted from the third-party package.

      M1  synthetic fixture round-trip: a table's format is proven by
          writing known content and reading it back - no emulator needed
      M2  the build may only change bytes inside declared patch ranges
      M3  the build report must carry the change radius
      M4  table base addresses come from the registry, not content files
    """
    suite = "process"

    def test_synthetic_fixtures_roundtrip() -> None:
        import synthetic_fixture
        from tools import text_codec

        try:
            rom_path = text_codec.resolve_rom()
        except FileNotFoundError:
            return
        mapping, _ = text_codec.load_mapping(rom_path)
        import tempfile
        errors = []
        with tempfile.TemporaryDirectory() as tmp:
            for name in sorted(synthetic_fixture.FIXTURES):
                result = synthetic_fixture.run_fixture(
                    name, rom_path, mapping, Path(tmp))
                for check in result["checks"]:
                    if not check["pass"]:
                        errors.append(
                            f"{name} / {check['check']}: "
                            f"expected {check['expected']!r}, "
                            f"got {check['actual']!r}")
        assert not errors, "\n".join(errors)

    def test_table_bases_match_the_registry() -> None:
        import table_registry

        report = table_registry.verify_table_bases()
        strict = [r for r in report["rows"]
                  if not r["match"] and r["authoritative_verified"]]
        assert not strict, "\n".join(
            f"{r['bank']}: declares {r['declared_hex']}, "
            f"authoritative {r['authoritative_hex']}" for r in strict)

    def test_build_changes_nothing_undeclared() -> None:
        ensure_isolated_build()
        report = load_build_report()
        radius = report.get("change_radius")
        assert radius is not None, "build report has no change_radius section"
        assert radius.get("undeclared_change_count", 0) == 0, (
            "the build changed bytes outside every declared patch range:\n"
            + json.dumps(radius.get("undeclared_changes", []),
                         ensure_ascii=False, indent=2))

    def test_build_report_has_a_change_radius() -> None:
        ensure_isolated_build()
        report = load_build_report()
        radius = report.get("change_radius")
        assert radius is not None, "build report has no change_radius section"
        for key in ("changed_bytes", "changed_range_count",
                    "declared_range_count", "undeclared_change_count"):
            assert key in radius, f"change_radius is missing {key}"

    runner.run("synthetic fixtures read back what was written",
               suite, test_synthetic_fixtures_roundtrip)
    runner.run("content table bases match the authoritative registry",
               suite, test_table_bases_match_the_registry)
    runner.run("build changes nothing outside declared patch ranges",
               suite, test_build_changes_nothing_undeclared)
    runner.run("build report carries the change radius",
               suite, test_build_report_has_a_change_radius)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SUITES = {
    "build":    suite_build,
    "manifest": suite_manifest,
    "patches":  suite_patches,
    "db_integrity": suite_db_integrity,
    "encoding": suite_encoding,
    "process":  suite_process,
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
