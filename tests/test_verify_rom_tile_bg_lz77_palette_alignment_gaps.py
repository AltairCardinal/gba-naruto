#!/usr/bin/env python3
"""Contract tests for the tile-BG LZ77-to-palette gap verifier."""

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
VERIFIER_PATH = ROOT / "tools/verify_rom_tile_bg_lz77_palette_alignment_gaps.py"

POINTER_MANIFEST = ROOT / "artifacts/rom-pointer-lz77-inventory-v1/manifest.json"
POINTER_PAYLOAD = ROOT / "artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json"
TILE_MANIFEST = ROOT / "artifacts/tile-assets-bg-v2/manifest.json"
EXPORTER_SOURCE = ROOT / "tools/verify_tile_asset_bg_export.py"

VERIFY_SCHEMA = "rom-tile-bg-lz77-palette-alignment-gaps-verification-v1"
PROMOTION_BATCH = "rom-tile-bg-lz77-palette-alignment-gaps-v1"
PRIMARY_CLASS = "tile_bg_lz77_palette_alignment_bytes"
CLAIM_KIND = "tile_bg_lz77_palette_alignment_gap_bytes"

ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
POINTER_MANIFEST_SHA256 = "d4afca9d19c3b764ce40f460d9c73d7c19f908bf25c197d4b082bd6bc5c4bb33"
POINTER_PAYLOAD_SHA256 = "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"
TILE_MANIFEST_SHA256 = "1df63cf6cf49079115e997c6f0f33c57578e517dbe22dc16c15f64c4d218a749"
EXPORTER_SOURCE_SHA256 = "4273c6d0cada4e7d018a805e5c96fca9654c19aabeff9a1a7b26e5aa8380d57c"

EXPECTED_RANGE_VECTOR_SHA256 = "684c4ad2fa1256261de50ed01f8a781bde09b7514f4cab0c5ec5dec9a0b472e2"
EXPECTED_BOUNDARY_VECTOR_SHA256 = "b96f496cb68ed87905d62c39a148f67b2fef4e10bfa9e2b6b004f2d1644fe448"
EXPECTED_PACKED_BYTES_SHA256 = "2aa1fd6b1e4d7e4352751c0a8b7acb6fd9aa3a3a4c994f52b0a214c6f346277d"
ZERO_HASHES = {
    1: "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d",
    2: "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    3: "709e80c88487a2411e1ee4dfb9f22a861492d20c4765150c0c794abd70f8147c",
}

EXPECTED_BOUNDARIES = (
    (3452872, 3453477, 3453480, 3453512),
    (3457484, 3458071, 3458072, 3458104),
    (3461164, 3461659, 3461660, 3461692),
    (3464908, 3465386, 3465388, 3465420),
    (3472960, 3473502, 3473504, 3473536),
    (3481268, 3481802, 3481804, 3481836),
    (3485096, 3485605, 3485608, 3485640),
    (3488544, 3489075, 3489076, 3489108),
    (3495304, 3495799, 3495800, 3495832),
    (3502960, 3503486, 3503488, 3503520),
    (3506776, 3507346, 3507348, 3507380),
    (3511964, 3512547, 3512548, 3512580),
    (3516328, 3516889, 3516892, 3516924),
    (3521016, 3521645, 3521648, 3521680),
    (3524704, 3525174, 3525176, 3525208),
    (3529404, 3529967, 3529968, 3530000),
    (3532356, 3532789, 3532792, 3532824),
    (3538932, 3539458, 3539460, 3539492),
    (3541556, 3541979, 3541980, 3542012),
    (3545380, 3545954, 3545956, 3545988),
    (3549324, 3549837, 3549840, 3549872),
    (3552780, 3553249, 3553252, 3553284),
    (3557472, 3558087, 3558088, 3558120),
    (3561152, 3561633, 3561636, 3561668),
    (3569484, 3570015, 3570016, 3570144),
    (3578160, 3578774, 3578776, 3578904),
    (3583916, 3584443, 3584444, 3584476),
    (3598564, 3599241, 3599244, 3599372),
    (3605764, 3606470, 3606472, 3606504),
    (3611784, 3612203, 3612204, 3612332),
    (3631628, 3632194, 3632196, 3632324),
    (3638888, 3639329, 3639332, 3639460),
    (3646116, 3646749, 3646752, 3646880),
    (3649088, 3649429, 3649432, 3649464),
    (3653700, 3653986, 3653988, 3654116),
    (3659280, 3659725, 3659728, 3659760),
    (3662744, 3663119, 3663120, 3663152),
    (3668244, 3668609, 3668612, 3668740),
    (3682096, 3682521, 3682524, 3682652),
    (3693212, 3693538, 3693540, 3693668),
    (3708352, 3708823, 3708824, 3708952),
    (3715264, 3715755, 3715756, 3715884),
    (3724628, 3725098, 3725100, 3725228),
    (3734132, 3734621, 3734624, 3734752),
    (3740064, 3740519, 3740520, 3740648),
    (3768036, 3768635, 3768636, 3768764),
    (3775316, 3775802, 3775804, 3775932),
    (3783820, 3784367, 3784368, 3784496),
    (3788856, 3789227, 3789228, 3789356),
    (3804656, 3805105, 3805108, 3805236),
    (3808624, 3808941, 3808944, 3809072),
    (3813040, 3813375, 3813376, 3813504),
    (3818180, 3818562, 3818564, 3818692),
    (3823532, 3823917, 3823920, 3824048),
    (3828268, 3828634, 3828636, 3828764),
    (3832964, 3833387, 3833388, 3833516),
    (3838028, 3838467, 3838468, 3838596),
    (3845244, 3845715, 3845716, 3845844),
    (3854576, 3855155, 3855156, 3855284),
    (3862376, 3862891, 3862892, 3863020),
    (3872208, 3872841, 3872844, 3872972),
    (3881028, 3881633, 3881636, 3881764),
    (3889460, 3890067, 3890068, 3890196),
    (3898848, 3899447, 3899448, 3899576),
    (3909280, 3909941, 3909944, 3910072),
    (3919272, 3919599, 3919600, 3919728),
    (3924724, 3925101, 3925104, 3925232),
    (3933448, 3934030, 3934032, 3934160),
    (3941132, 3941663, 3941664, 3941792),
    (3954556, 3955235, 3955236, 3955364),
    (3972860, 3973306, 3973308, 3973436),
    (3976012, 3976215, 3976216, 3976344),
    (3982712, 3983337, 3983340, 3983372),
    (3987228, 3987494, 3987496, 3987624),
    (3993280, 3993838, 3993840, 3993872),
    (3998648, 3999010, 3999012, 3999140),
    (4006368, 4006922, 4006924, 4007052),
    (4011784, 4012134, 4012136, 4012264),
    (4022928, 4023245, 4023248, 4023376),
    (4041100, 4041713, 4041716, 4041844),
    (4052244, 4052819, 4052820, 4052948),
    (4058060, 4058413, 4058416, 4058544),
    (4063424, 4063773, 4063776, 4063904),
    (4069216, 4069678, 4069680, 4069808),
)

EXPECTED_LONG_GAPS = ((1302573, 1302640), (3448401, 3448436))
EXPECTED_HETEROGENEOUS_GAPS = (
    (3443681, 3443684),
    (3445786, 3445788),
    (3446445, 3446448),
    (4136542, 4136544),
    (4218861, 4218864),
    (4554406, 4554408),
    (4602066, 4602068),
)
NON_CLAIMS = (
    "padding",
    "reserved_space",
    "free_space",
    "allocatable_space",
    "natural_runtime_reachability",
    "global_unreachability",
    "fixed_consumer_exhaustiveness",
    "final_pixel_equivalence",
    "editing_safety",
    "relocation_safety",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _compact_sha(value: object) -> str:
    return _sha(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _load_verifier():
    try:
        return importlib.import_module(
            "tools.verify_rom_tile_bg_lz77_palette_alignment_gaps"
        )
    except ModuleNotFoundError as error:
        raise AssertionError(
            "target verifier module is absent (the expected RED condition)"
        ) from error


def _expected_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for left_start, left_end, palette_start, palette_end in EXPECTED_BOUNDARIES:
        size = palette_start - left_end
        left = [left_start, left_end]
        right = [palette_start, palette_end]
        gap = [left_end, palette_start]
        rows.append(
            {
                "alignment_unit_bytes": 4,
                "bytes_sha256": ZERO_HASHES[size],
                "gfx_stream_range": left,
                "id": f"tile-bg-lz77-palette-gap-{left_start:06x}",
                "left": left,
                "left_id": f"lz77-{left_start:06x}",
                "left_primary_class": "lz77_resource",
                "palette_range": right,
                "range": gap,
                "raw_hex": "00" * size,
                "right": right,
                "right_claim_kind": "tile_bg_palette_source_range",
                "right_id": f"tile-bg-palette-{palette_start:06x}",
                "right_primary_class": "palette_bgr555",
                "size": size,
            }
        )
    return rows


class TileBgLz77PaletteAlignmentGapVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()
        cls.pointer_manifest = POINTER_MANIFEST.read_bytes()
        cls.pointer_payload = POINTER_PAYLOAD.read_bytes()
        cls.tile_manifest = TILE_MANIFEST.read_bytes()
        cls.exporter_source = EXPORTER_SOURCE.read_bytes()

    def _verify_inputs(self, *, rom: bytes | None = None, **overrides):
        verifier = _load_verifier()
        values = {
            "rom": self.rom if rom is None else rom,
            "pointer_manifest": self.pointer_manifest,
            "pointer_payload": self.pointer_payload,
            "tile_manifest": self.tile_manifest,
            "exporter_source": self.exporter_source,
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
        verifier = _load_verifier()
        values = {
            "rom": self.rom if rom is None else rom,
            "pointer_manifest": self.pointer_manifest,
            "pointer_payload": self.pointer_payload,
            "tile_manifest": self.tile_manifest,
            "exporter_source": self.exporter_source,
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
        report = _load_verifier().verify_root(ROOT)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(VERIFY_SCHEMA, report["schema"])
        self.assertEqual([], report["errors"])
        self.assertEqual(PROMOTION_BATCH, report["promotion_batch"])
        self.assertEqual(PRIMARY_CLASS, report["primary_class"])
        self.assertEqual(CLAIM_KIND, report["claim_kind"])
        self.assertEqual(84, report["gap_count"])
        self.assertEqual(165, report["gap_bytes"])
        self.assertEqual({"1": 31, "2": 25, "3": 28}, report["size_counts"])
        self.assertEqual(EXPECTED_RANGE_VECTOR_SHA256, report["range_vector_sha256"])
        self.assertEqual(EXPECTED_BOUNDARY_VECTOR_SHA256, report["boundary_vector_sha256"])
        self.assertEqual(EXPECTED_PACKED_BYTES_SHA256, report["packed_bytes_sha256"])
        self.assertEqual(896, report["aligned_pointer_reachable_lz77_count"])
        self.assertEqual(79, report["tile_descriptor_count"])
        self.assertEqual(236, report["tile_palette_entry_count"])
        self.assertEqual(108, report["tile_raw_palette_range_count"])
        self.assertEqual(107, report["tile_merged_palette_claim_count"])
        self.assertEqual(9984, report["tile_merged_palette_bytes"])
        self.assertEqual(_expected_rows(), report["rows"])
        self.assertEqual(list(NON_CLAIMS), report["non_claims"])
        self.assertTrue(report["all_zero"])
        self.assertTrue(report["right_end_align4"])
        self.assertEqual(
            list(EXPECTED_LONG_GAPS),
            [tuple(item["range"]) for item in report["excluded_long_gaps"]],
        )
        self.assertEqual(
            list(EXPECTED_HETEROGENEOUS_GAPS),
            [tuple(item["range"]) for item in report["excluded_heterogeneous_gaps"]],
        )

    def test_report_vectors_are_recomputed_from_explicit_rows(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        ranges = [row["range"] for row in report["rows"]]
        boundaries = [
            {
                key: row[key]
                for key in ("range", "left", "right", "left_id", "right_id")
            }
            for row in report["rows"]
        ]
        self.assertEqual(EXPECTED_RANGE_VECTOR_SHA256, _compact_sha(ranges))
        self.assertEqual(EXPECTED_BOUNDARY_VECTOR_SHA256, _compact_sha(boundaries))
        self.assertEqual(165, sum(end - start for start, end in ranges))
        packed = bytes.fromhex("".join(row["raw_hex"] for row in report["rows"]))
        self.assertEqual(165, len(packed))
        self.assertEqual(EXPECTED_PACKED_BYTES_SHA256, _sha(packed))
        self.assertTrue(all(row["left_primary_class"] == "lz77_resource" for row in report["rows"]))
        self.assertTrue(
            all(
                row["right_primary_class"] == "palette_bgr555"
                for row in report["rows"]
            )
        )
        self.assertTrue(
            all(
                row["right_claim_kind"] == "tile_bg_palette_source_range"
                for row in report["rows"]
            )
        )

    def test_right_end_alignment_uses_gap_end_not_palette_end(self) -> None:
        verifier = _load_verifier()
        self.assertTrue(
            verifier._right_end_align4(
                [{"range": [1, 4], "right": [4, 5]}]
            )
        )
        self.assertFalse(
            verifier._right_end_align4(
                [{"range": [1, 3], "right": [3, 4]}]
            )
        )

    def test_every_individual_gap_byte_mutation_fails_closed(self) -> None:
        self.assertEqual(165, sum(palette_start - left_end for _, left_end, palette_start, _ in EXPECTED_BOUNDARIES))
        expected_rows = _expected_rows()
        for index, row in enumerate(expected_rows):
            start, end = row["range"]
            for offset in range(start, end):
                with self.subTest(row=index, offset=offset):
                    mutated = bytearray(self.rom)
                    mutated[offset] ^= 0x01
                    report = self._verify_semantics(
                        rom=bytes(mutated), bypass_identity_labels={"ROM"}
                    )
                    self.assertFalse(report["verified"])
                    self.assertEqual(
                        [f"{row['id']} alignment bytes changed"],
                        report["errors"],
                    )

    def test_gap_mutation_reaches_zero_byte_guard_after_identity_acceptance(self) -> None:
        row = _expected_rows()[0]
        start, _ = row["range"]
        mutated = bytearray(self.rom)
        mutated[start] ^= 0x01
        report = self._verify_semantics(
            rom=bytes(mutated), bypass_identity_labels={"ROM"}
        )
        self.assertEqual([f"{row['id']} alignment bytes changed"], report["errors"])

    def test_rom_identity_parser_endpoint_and_palette_mutations_fail_closed(self) -> None:
        for index in range(0, len(EXPECTED_BOUNDARIES), 7):
            left_start, _, _, _ = EXPECTED_BOUNDARIES[index]
            with self.subTest(parser_index=index):
                mutated = bytearray(self.rom)
                mutated[left_start + 1] ^= 0x01
                report = self._verify_semantics(
                    rom=bytes(mutated), bypass_identity_labels={"ROM"}
                )
                self.assertFalse(report["verified"])
                self.assertTrue(report["errors"])
                self.assertFalse(
                    any("identity changed" in error for error in report["errors"]),
                    report,
                )
        for index in range(0, len(EXPECTED_BOUNDARIES), 7):
            _, _, palette_start, _ = EXPECTED_BOUNDARIES[index]
            with self.subTest(palette_index=index):
                mutated = bytearray(self.rom)
                mutated[palette_start] ^= 0x01
                report = self._verify_semantics(
                    rom=bytes(mutated), bypass_identity_labels={"ROM"}
                )
                self.assertFalse(report["verified"])
                self.assertTrue(
                    any("tile palette bytes changed" in error for error in report["errors"]),
                    report,
                )
        mutated = bytearray(self.rom)
        mutated[0] ^= 0x01
        report = self._verify_inputs(rom=bytes(mutated))
        self.assertFalse(report["verified"])
        self.assertTrue(any("ROM" in error or "rom" in error for error in report["errors"]))

    def test_all_input_identity_drifts_fail_closed(self) -> None:
        sources = {
            "pointer_manifest": self.pointer_manifest,
            "pointer_payload": self.pointer_payload,
            "tile_manifest": self.tile_manifest,
            "exporter_source": self.exporter_source,
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

    def test_upstream_semantic_denominator_mutations_fail_closed(self) -> None:
        pointer = json.loads(self.pointer_payload.decode("utf-8"))
        pointer["summary"]["aligned_pointer_reachable_record_count"] = 895
        report = self._verify_semantics(
            pointer_payload=_canonical(pointer),
            bypass_identity_labels={"pointer inventory payload"},
        )
        self.assertEqual(["pointer inventory denominator summary changed"], report["errors"])

        tile = json.loads(self.tile_manifest.decode("utf-8"))
        tile["descriptor_count"] = 78
        report = self._verify_semantics(
            tile_manifest=_canonical(tile),
            bypass_identity_labels={"tile asset manifest"},
        )
        self.assertTrue(any("tile manifest denominator changed" in error for error in report["errors"]), report)

        tile = json.loads(self.tile_manifest.decode("utf-8"))
        tile["descriptors"].pop()
        report = self._verify_semantics(
            tile_manifest=_canonical(tile),
            bypass_identity_labels={"tile asset manifest"},
        )
        self.assertEqual(["tile descriptor list changed"], report["errors"])

        tile = json.loads(self.tile_manifest.decode("utf-8"))
        tile["descriptors"][1]["raw_words"][0] = "0x00000001"
        report = self._verify_semantics(
            tile_manifest=_canonical(tile),
            bypass_identity_labels={"tile asset manifest"},
        )
        self.assertEqual(["descriptor 1 raw words differ from ROM"], report["errors"])

    def test_tile_palette_entry_and_raw_range_denominators_are_rebuilt(self) -> None:
        tile = json.loads(self.tile_manifest.decode("utf-8"))
        tile["complete_layer_count"] = 235
        report = self._verify_semantics(
            tile_manifest=_canonical(tile),
            bypass_identity_labels={"tile asset manifest"},
        )
        self.assertTrue(any("tile manifest denominator changed" in error for error in report["errors"]), report)

        tile = json.loads(self.tile_manifest.decode("utf-8"))
        tile["unique_palette_count"] = 106
        report = self._verify_semantics(
            tile_manifest=_canonical(tile),
            bypass_identity_labels={"tile asset manifest"},
        )
        self.assertTrue(any("tile manifest denominator changed" in error for error in report["errors"]), report)

        mutated = bytearray(self.rom)
        mutated[0x5A320C] ^= 0x01
        report = self._verify_semantics(
            rom=bytes(mutated), bypass_identity_labels={"ROM"}
        )
        self.assertFalse(report["verified"])
        self.assertTrue(any("tile descriptor table" in error for error in report["errors"]), report)

    def test_frozen_row_count_hash_adjacency_and_alignment_drift_fail_closed(self) -> None:
        verifier = _load_verifier()
        with mock.patch.object(verifier, "EXPECTED_RANGE_VECTOR_SHA256", "0" * 64):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

        with mock.patch.object(verifier, "EXPECTED_BOUNDARY_VECTOR_SHA256", "0" * 64):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

        with mock.patch.object(verifier, "EXPECTED_PACKED_BYTES_SHA256", "0" * 64):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

        wrong = list(verifier.EXPECTED_BOUNDARIES)
        left_start, left_end, palette_start, palette_end = wrong[0]
        wrong[0] = (left_start, left_end, palette_start + 1, palette_end)
        with mock.patch.object(verifier, "EXPECTED_BOUNDARIES", tuple(wrong)):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

        with mock.patch.object(verifier, "ALIGNMENT_UNIT_BYTES", 2):
            report = verifier.verify_root(ROOT)
        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

    def test_nonclaims_and_excluded_long_and_heterogeneous_gaps_are_explicit(self) -> None:
        report = _load_verifier().verify_root(ROOT)
        self.assertEqual(list(NON_CLAIMS), report["non_claims"])
        reported_ranges = {tuple(row["range"]) for row in report["rows"]}
        for interval in EXPECTED_LONG_GAPS + EXPECTED_HETEROGENEOUS_GAPS:
            self.assertNotIn(interval, reported_ranges)
        self.assertTrue(all(item["contains_nonzero"] for item in report["excluded_long_gaps"]))
        self.assertEqual(2, len(report["excluded_long_gaps"]))
        self.assertEqual(7, len(report["excluded_heterogeneous_gaps"]))

    def test_cli_success_failure_and_real_root_symlink_safety(self) -> None:
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
            Path("artifacts/tile-assets-bg-v2/manifest.json"),
            Path("tools/verify_tile_asset_bg_export.py"),
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

    def test_verifier_is_standalone_and_does_not_read_exporter_or_live_coverage(self) -> None:
        _load_verifier()
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("rom-byte-coverage.json", source)
        tree = ast.parse(source)
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
