#!/usr/bin/env python3
"""Contract tests for the menu portrait LZ77-to-palette short-gap verifier."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "rom/base.gba"
VERIFIER_PATH = ROOT / "tools/verify_rom_menu_portrait_lz77_palette_alignment_gaps.py"

VERIFY_SCHEMA = "rom-menu-portrait-lz77-palette-alignment-gaps-verification-v1"
PROMOTION_BATCH = "rom-menu-portrait-lz77-palette-alignment-gaps-v1"
PRIMARY_CLASS = "menu_portrait_lz77_palette_alignment_bytes"
CLAIM_KIND = "menu_portrait_lz77_palette_alignment_gap_bytes"

POINTER_MANIFEST = ROOT / "artifacts/rom-pointer-lz77-inventory-v1/manifest.json"
POINTER_PAYLOAD = ROOT / "artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json"
MENU_MANIFEST = ROOT / "artifacts/rom-menu-portrait-palette-inventory-v1/manifest.json"
MENU_PAYLOAD = ROOT / "artifacts/rom-menu-portrait-palette-inventory-v1/rom-menu-portrait-palette-inventory.json"

ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
POINTER_MANIFEST_SHA256 = "d4afca9d19c3b764ce40f460d9c73d7c19f908bf25c197d4b082bd6bc5c4bb33"
POINTER_PAYLOAD_SHA256 = "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"
MENU_MANIFEST_SHA256 = "8a8675c2724131a6caa9b956825d74280fa26fe99447470b3cc3810688e6f88b"
MENU_PAYLOAD_SHA256 = "ac263fc071b6c6ad4b94b649df38560c180f2b2fd350212cc3875055146d908d"

EXPECTED_RANGE_VECTOR_SHA256 = "e88d3a42d6e3144919668ade6db9f9caa21e8aab1502d8b3d9c84a148875bbf7"
EXPECTED_BOUNDARY_VECTOR_SHA256 = "13ab975a67b42528abeef6075ff1f71b9440a7e53806f4f07f345d2e30900ddb"
EXPECTED_PACKED_BYTES_SHA256 = "f23391587f1c9fc48eabd1e95f4caf16f585ef09941b7bc24f023d228e81ccd5"
ZERO_HASHES = {
    1: "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d",
    2: "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    3: "709e80c88487a2411e1ee4dfb9f22a861492d20c4765150c0c794abd70f8147c",
}

EXPECTED_RANGES = (
    (4233410, 4233412),
    (4236963, 4236964),
    (4240629, 4240632),
    (4244062, 4244064),
    (4251263, 4251264),
    (4257177, 4257180),
    (4260505, 4260508),
    (4263773, 4263776),
    (4267091, 4267092),
    (4270467, 4270468),
    (4273973, 4273976),
    (4285367, 4285368),
    (4288887, 4288888),
    (4291506, 4291508),
    (4295174, 4295176),
    (4298437, 4298440),
    (4301659, 4301660),
    (4305365, 4305368),
    (4308873, 4308876),
    (4312293, 4312296),
    (4315393, 4315396),
    (4321202, 4321204),
    (4330091, 4330092),
    (4333031, 4333032),
    (4336969, 4336972),
    (4344091, 4344092),
    (4350414, 4350416),
    (4353713, 4353716),
    (4357009, 4357012),
    (4360097, 4360100),
    (4365801, 4365804),
    (4368866, 4368868),
    (4371699, 4371700),
    (4378290, 4378292),
    (4382119, 4382120),
    (4384767, 4384768),
    (4390465, 4390468),
    (4398274, 4398276),
    (4412021, 4412024),
    (4415989, 4415992),
    (4419657, 4419660),
    (4423211, 4423212),
    (4426593, 4426596),
    (4429877, 4429880),
    (4433122, 4433124),
    (4436215, 4436216),
    (4439982, 4439984),
    (4443362, 4443364),
    (4449485, 4449488),
    (4452170, 4452172),
    (4455414, 4455416),
    (4461347, 4461348),
)
EXPECTED_RESOURCE_IDS = (
    0,
    1,
    2,
    3,
    73,
    6,
    7,
    8,
    9,
    10,
    11,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    25,
    28,
    29,
    30,
    32,
    34,
    35,
    36,
    37,
    39,
    40,
    41,
    43,
    44,
    45,
    47,
    49,
    53,
    54,
    55,
    56,
    57,
    58,
    59,
    60,
    61,
    62,
    64,
    65,
    66,
    72,
)
EXPECTED_GFX_STREAM_STARTS = (
    4230104,
    4233540,
    4237092,
    4240760,
    4247976,
    4254296,
    4257308,
    4260636,
    4263904,
    4267220,
    4270596,
    4281876,
    4285496,
    4289016,
    4291636,
    4295304,
    4298568,
    4301788,
    4305496,
    4309004,
    4312424,
    4318412,
    4327044,
    4330220,
    4333160,
    4340264,
    4347128,
    4350544,
    4353844,
    4357140,
    4362852,
    4365932,
    4368996,
    4375140,
    4378420,
    4382248,
    4387592,
    4394372,
    4408984,
    4412152,
    4416120,
    4419788,
    4423340,
    4426724,
    4430008,
    4433252,
    4436344,
    4440112,
    4446648,
    4449616,
    4452300,
    4458424,
)

NON_CLAIM_KEYS = (
    "padding_intent_claimed",
    "reserved_space_claimed",
    "free_space_claimed",
    "allocatable_space_claimed",
    "runtime_consumption_claimed",
    "natural_runtime_reachability_claimed",
    "generic_lz77_alignment_rule_claimed",
    "all_menu_gaps_exhaustive_claimed",
    "graphics_or_palette_semantics_expanded",
    "editing_safety_claimed",
    "writeback_or_relocation_safety_claimed",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _compact_sha(value: object) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode())


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _load_verifier():
    try:
        return importlib.import_module(
            "tools.verify_rom_menu_portrait_lz77_palette_alignment_gaps"
        )
    except ModuleNotFoundError as error:
        raise AssertionError(
            "target verifier module is absent (the expected RED condition)"
        ) from error


def _expected_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for resource_id, gfx_start, (start, end) in zip(
        EXPECTED_RESOURCE_IDS, EXPECTED_GFX_STREAM_STARTS, EXPECTED_RANGES
    ):
        size = end - start
        rows.append(
            {
                "alignment_unit_bytes": 4,
                "bytes_sha256": ZERO_HASHES[size],
                "gfx_stream_range": [gfx_start, start],
                "id": f"menu-portrait-lz77-palette-gap-{resource_id:02d}-{start:06x}",
                "left_primary_class": "lz77_resource",
                "palette_range": [end, end + 128],
                "range": [start, end],
                "raw_hex": "00" * size,
                "resource_id": resource_id,
                "right_primary_class": "menu_portrait_palette_bgr555",
                "size": size,
            }
        )
    return rows


class MenuPortraitLz77PaletteAlignmentGapVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()
        cls.pointer_manifest = POINTER_MANIFEST.read_bytes()
        cls.pointer_payload = POINTER_PAYLOAD.read_bytes()
        cls.menu_manifest = MENU_MANIFEST.read_bytes()
        cls.menu_payload = MENU_PAYLOAD.read_bytes()

    def _verify_inputs(self, *, rom: bytes | None = None, **overrides):
        verifier = _load_verifier()
        values = {
            "rom": self.rom if rom is None else rom,
            "pointer_manifest": self.pointer_manifest,
            "pointer_payload": self.pointer_payload,
            "menu_manifest": self.menu_manifest,
            "menu_payload": self.menu_payload,
        }
        values.update(overrides)
        return verifier.verify_inputs(**values)

    def _verify_semantics(
        self,
        *,
        bypass_identity_labels: set[str],
        rom: bytes | None = None,
        **overrides,
    ):
        """Bypass only named outer hashes so mutations reach semantic guards."""

        verifier = _load_verifier()
        values = {
            "rom": self.rom if rom is None else rom,
            "pointer_manifest": self.pointer_manifest,
            "pointer_payload": self.pointer_payload,
            "menu_manifest": self.menu_manifest,
            "menu_payload": self.menu_payload,
        }
        values.update(overrides)
        original_check = verifier._check_identity

        def selective_check(raw: bytes, expected: str, label: str) -> None:
            if label not in bypass_identity_labels:
                original_check(raw, expected, label)

        with mock.patch.object(
            verifier, "_check_identity", side_effect=selective_check
        ):
            return verifier.verify_inputs(**values)

    def test_exact_frozen_report_totals_hashes_rows_and_nonclaims(self) -> None:
        verifier = _load_verifier()
        report = verifier.verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(VERIFY_SCHEMA, report["schema"])
        self.assertEqual([], report["errors"])
        self.assertEqual(PROMOTION_BATCH, report["promotion_batch"])
        self.assertEqual(PRIMARY_CLASS, report["primary_class"])
        self.assertEqual(CLAIM_KIND, report["claim_kind"])
        self.assertEqual(52, report["gap_count"])
        self.assertEqual(110, report["gap_bytes"])
        self.assertEqual({"1": 16, "2": 14, "3": 22}, report["size_counts"])
        self.assertEqual(list(EXPECTED_RESOURCE_IDS), report["resource_ids"])
        self.assertEqual(EXPECTED_RANGE_VECTOR_SHA256, report["range_vector_sha256"])
        self.assertEqual(EXPECTED_BOUNDARY_VECTOR_SHA256, report["boundary_vector_sha256"])
        self.assertEqual(EXPECTED_PACKED_BYTES_SHA256, report["packed_bytes_sha256"])
        self.assertEqual(896, report["aligned_pointer_reachable_lz77_count"])
        self.assertEqual(74, report["menu_resource_count"])
        self.assertEqual(70, report["physical_palette_count"])
        self.assertEqual(_expected_rows(), report["rows"])
        self.assertEqual({key: False for key in NON_CLAIM_KEYS}, report["non_claims"])
        self.assertTrue(report["limitations"])
        joined = " ".join(report["limitations"]).lower()
        for marker in (
            "padding",
            "reserved",
            "free",
            "allocatable",
            "runtime",
            "natural",
            "generic",
            "exhaustive",
            "editing",
            "relocation",
        ):
            self.assertIn(marker, joined)

    def test_report_vectors_are_recomputed_from_explicit_rows(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        ranges = [row["range"] for row in report["rows"]]
        self.assertEqual([list(pair) for pair in EXPECTED_RANGES], ranges)
        self.assertEqual(EXPECTED_RANGE_VECTOR_SHA256, _compact_sha(ranges))
        self.assertEqual(EXPECTED_BOUNDARY_VECTOR_SHA256, _compact_sha(report["rows"]))
        self.assertEqual(110, sum(end - start for start, end in EXPECTED_RANGES))
        self.assertEqual(110, len(bytes.fromhex("".join(row["raw_hex"] for row in report["rows"]))))
        self.assertEqual(EXPECTED_PACKED_BYTES_SHA256, _sha(bytes.fromhex("".join(row["raw_hex"] for row in report["rows"]))))
        self.assertTrue(all(row["left_primary_class"] == "lz77_resource" for row in report["rows"]))
        self.assertTrue(all(row["right_primary_class"] == "menu_portrait_palette_bgr555" for row in report["rows"]))

    def test_every_individual_gap_byte_mutation_fails_closed(self) -> None:
        self.assertEqual(110, sum(end - start for start, end in EXPECTED_RANGES))
        for range_index, (start, end) in enumerate(EXPECTED_RANGES):
            for offset in range(start, end):
                with self.subTest(range_index=range_index, offset=offset):
                    mutated = bytearray(self.rom)
                    mutated[offset] ^= 0x01
                    report = self._verify_semantics(
                        rom=bytes(mutated), bypass_identity_labels={"ROM"}
                    )
                    self.assertFalse(report["verified"])
                    self.assertEqual(
                        [
                            f"resource {EXPECTED_RESOURCE_IDS[range_index]} "
                            "alignment bytes changed"
                        ],
                        report["errors"],
                    )

    def test_gap_mutation_reaches_zero_byte_guard_after_identity_acceptance(self) -> None:
        start, _ = EXPECTED_RANGES[0]
        mutated = bytearray(self.rom)
        mutated[start] ^= 0x01
        report = self._verify_semantics(
            rom=bytes(mutated), bypass_identity_labels={"ROM"}
        )
        self.assertEqual(["resource 0 alignment bytes changed"], report["errors"])

    def test_rom_identity_parser_endpoint_and_adjacency_mutations_fail_closed(self) -> None:
        sample_indexes = range(0, len(EXPECTED_RANGES), 5)
        for index in sample_indexes:
            with self.subTest(parser_resource_id=EXPECTED_RESOURCE_IDS[index]):
                mutated = bytearray(self.rom)
                mutated[EXPECTED_GFX_STREAM_STARTS[index] + 1] ^= 0x01
                report = self._verify_semantics(
                    rom=bytes(mutated), bypass_identity_labels={"ROM"}
                )
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])
                self.assertFalse(
                    any("identity changed" in error for error in report["errors"]),
                    report,
                )
        for index in sample_indexes:
            with self.subTest(palette_resource_id=EXPECTED_RESOURCE_IDS[index]):
                _, palette_start = EXPECTED_RANGES[index]
                mutated = bytearray(self.rom)
                mutated[palette_start] ^= 0x01
                report = self._verify_semantics(
                    rom=bytes(mutated), bypass_identity_labels={"ROM"}
                )
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any("physical palette bytes changed" in error for error in report["errors"]),
                    report,
                )
        mutated = bytearray(self.rom)
        mutated[0] ^= 0x01
        report = self._verify_inputs(rom=bytes(mutated))
        self.assertFalse(report["verified"])
        self.assertTrue(any("ROM" in error or "rom" in error for error in report["errors"]))

    def test_upstream_identity_and_semantic_denominator_mutations_fail_closed(self) -> None:
        sources = {
            "pointer_manifest": self.pointer_manifest,
            "pointer_payload": self.pointer_payload,
            "menu_manifest": self.menu_manifest,
            "menu_payload": self.menu_payload,
        }
        for name, raw in sources.items():
            with self.subTest(source=name):
                mutated = bytearray(raw)
                mutated[-1] ^= 0x01
                values = dict(sources)
                values[name] = bytes(mutated)
                report = self._verify_inputs(**values)
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])

        menu = json.loads(self.menu_payload.decode())
        menu["resource_provenance"].pop()
        report = self._verify_semantics(
            menu_payload=_canonical(menu),
            bypass_identity_labels={"menu inventory payload"},
        )
        self.assertEqual(["menu resource denominator changed"], report["errors"])

        menu = json.loads(self.menu_payload.decode())
        menu["physical_palettes"].pop()
        report = self._verify_semantics(
            menu_payload=_canonical(menu),
            bypass_identity_labels={"menu inventory payload"},
        )
        self.assertEqual(["physical palette denominator changed"], report["errors"])

        menu = json.loads(self.menu_payload.decode())
        menu["resource_provenance"][0]["resource_id"] = 73
        report = self._verify_semantics(
            menu_payload=_canonical(menu),
            bypass_identity_labels={"menu inventory payload"},
        )
        self.assertEqual(["menu resource ID denominator changed"], report["errors"])

        menu = json.loads(self.menu_payload.decode())
        menu["resource_provenance"][0]["palette_file_offset"] += 1
        menu["resource_provenance"][0]["palette_pointer"] = "0x084098C5"
        report = self._verify_semantics(
            menu_payload=_canonical(menu),
            bypass_identity_labels={"menu inventory payload"},
        )
        self.assertTrue(
            any("menu resource 0 binding changed" in error for error in report["errors"]),
            report,
        )

    def test_range_vector_and_packed_hash_drift_fail_closed(self) -> None:
        verifier = _load_verifier()
        with mock.patch.object(
            verifier,
            "EXPECTED_RANGE_VECTOR_SHA256",
            "0" * 64,
        ):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

        with mock.patch.object(verifier, "EXPECTED_PACKED_BYTES_SHA256", "0" * 64):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

    def test_cli_success_failure_and_real_symlink_safety(self) -> None:
        _load_verifier()
        completed = subprocess.run(
            [sys.executable, str(VERIFIER_PATH), "--root", str(ROOT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        success = json.loads(completed.stdout)
        self.assertTrue(success["verified"])
        self.assertEqual([], success["errors"])

        with tempfile.TemporaryDirectory() as raw:
            outside = Path(raw)
            linked_root = outside / "root-link"
            linked_root.symlink_to(ROOT, target_is_directory=True)
            rejected = subprocess.run(
                [sys.executable, str(VERIFIER_PATH), "--root", str(linked_root)],
                cwd=outside,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, rejected.returncode)
            failure = json.loads(rejected.stdout)
            self.assertFalse(failure["verified"])
            self.assertTrue(failure["errors"])

    def test_real_symlinked_bound_inputs_are_rejected(self) -> None:
        _load_verifier()
        bound = (
            Path("rom/base.gba"),
            Path("artifacts/rom-pointer-lz77-inventory-v1/manifest.json"),
            Path("artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json"),
            Path("artifacts/rom-menu-portrait-palette-inventory-v1/manifest.json"),
            Path("artifacts/rom-menu-portrait-palette-inventory-v1/rom-menu-portrait-palette-inventory.json"),
        )
        for relative in bound:
            with self.subTest(relative=relative):
                with tempfile.TemporaryDirectory() as raw:
                    copied_root = Path(raw)
                    target = copied_root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(ROOT / relative)
                    for other in bound:
                        if other == relative:
                            continue
                        destination = copied_root / other
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(ROOT / other, destination)
                    report = _load_verifier().verify_root(copied_root)
                    self.assertFalse(report["verified"])
                    self.assertTrue(report["errors"])

    def test_verifier_is_standalone_standard_library_only(self) -> None:
        _load_verifier()
        tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        self.assertTrue(imports)
        for imported in imports:
            self.assertIn(imported.split(".", 1)[0], sys.stdlib_module_names)
        self.assertTrue(
            {"tools", "tests", "build", "sequel"}.isdisjoint(
                imported.split(".", 1)[0] for imported in imports
            )
        )


if __name__ == "__main__":
    unittest.main()
