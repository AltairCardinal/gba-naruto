import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INITIALIZER_SHA256 = (
    "213423e70948ef3dbd91ed7854efb5c52fd7543f4b73b4a4a2219ffd89ce66f7"
)
DIRECT_CALLERS = [
    0x080691F8,
    0x08073752,
    0x08074E96,
    0x0807953C,
    0x0807AB68,
    0x08081328,
    0x08086204,
    0x0808692C,
    0x08086A94,
    0x08086B4C,
    0x0808702C,
    0x080875C0,
    0x08087CD6,
    0x0808819C,
    0x08088F92,
    0x0808A120,
    0x0808B5B2,
    0x0808BAE2,
    0x0808C506,
    0x0808CBA0,
    0x0808F26A,
    0x0808F582,
    0x08091512,
]


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExportInitializerResourcePackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_initializer_resource_pack import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.artifact = export_artifact(ROOT, cls.output)
        cls.manifest = json.loads(
            (cls.output / "manifest.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exports_hash_bound_initializer_and_four_lossless_resources(self):
        artifact = self.artifact
        self.assertEqual(
            "initializer-resource-pack-v1",
            artifact["schema"],
        )
        self.assertEqual(ROM_SHA256, artifact["rom"]["sha256"])
        self.assertEqual(
            {
                "gba_start": "0x08065404",
                "gba_end_exclusive": "0x08065554",
                "size": 336,
                "sha256": INITIALIZER_SHA256,
                "direct_callers": DIRECT_CALLERS,
                "evidence_type": "static_code",
            },
            artifact["initializer"],
        )

        expected = {
            "bg_graphics": {
                "gba_pointer": "0x0809C614",
                "file_offset": 0x09C614,
                "literal_gba_address": "0x0806557C",
                "load_call_gba_address": "0x080654A0",
                "loader_target_gba_address": "0x0809C0E8",
                "compressed_size": 604,
                "compressed_sha256": (
                    "65ec75afff379ad740b3e0e4d73b5c9b6d51289c1dbb0ea80264a93a09166103"
                ),
                "decompressed_size": 2048,
                "decompressed_sha256": (
                    "d2338ea2e8d155029010b4dfac8f72e01e73a74e9ccccc8998f62ec0ba81909e"
                ),
                "tile_count": 64,
                "unique_tile_content_count": 29,
            },
            "bg_palette": {
                "gba_pointer": "0x0809C870",
                "file_offset": 0x09C870,
                "literal_gba_address": "0x08065580",
                "load_call_gba_address": "0x080654B8",
                "loader_target_gba_address": "0x0808830C",
                "compressed_size": 64,
                "compressed_sha256": (
                    "4c657dea384298a2607427dddbf49e58dc0b70579617e7b64f56497e33eb2f49"
                ),
                "decompressed_size": 64,
                "decompressed_sha256": (
                    "f20fc5a725aba48ad552db95ec211c78b1bef25732c8978324a6bf72e64d72e5"
                ),
                "color_count": 32,
            },
            "obj_graphics": {
                "gba_pointer": "0x085B64E0",
                "file_offset": 0x5B64E0,
                "literal_gba_address": "0x08065588",
                "load_call_gba_address": "0x080654C6",
                "loader_target_gba_address": "0x0809C0E8",
                "compressed_size": 753,
                "compressed_sha256": (
                    "9ad033484a1970f11f0ed37df58c894f7a093505ecb6b12ff364a787e4cb539b"
                ),
                "decompressed_size": 1536,
                "decompressed_sha256": (
                    "be06481834463afa0226757f897601ef07291106257bc716ef42bf4572df1848"
                ),
                "tile_count": 48,
                "unique_tile_content_count": 43,
            },
            "obj_palette": {
                "gba_pointer": "0x0809CBC4",
                "file_offset": 0x09CBC4,
                "literal_gba_address": "0x08065590",
                "load_call_gba_address": "0x080654D6",
                "loader_target_gba_address": "0x0808830C",
                "compressed_size": 40,
                "compressed_sha256": (
                    "cf94ad002a6878cb393843f9a6dcbe63ef05fbe514f0280f85c42ac8a25af7e1"
                ),
                "decompressed_size": 32,
                "decompressed_sha256": (
                    "dc72a37cfa3893bc9979d1801b80c9e356b04990751d4bf525e2879fa6e52393"
                ),
                "color_count": 16,
            },
        }
        self.assertEqual(set(expected), set(artifact["resources"]))
        for key, fields in expected.items():
            actual = artifact["resources"][key]
            for field, value in fields.items():
                self.assertEqual(value, actual[field], (key, field))
            for field in ("compressed_file", "file"):
                path = self.output / actual[field]
                self.assertTrue(path.is_file(), path)
            self.assertEqual(
                actual["compressed_sha256"],
                hashlib.sha256(
                    (self.output / actual["compressed_file"]).read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                actual["decompressed_sha256"],
                hashlib.sha256(
                    (self.output / actual["file"]).read_bytes()
                ).hexdigest(),
            )

    def test_binds_each_resource_to_the_exact_loader_route_and_destination(self):
        routes = self.artifact["loader_routes"]
        self.assertEqual(
            {
                "wrapper_gba_address": "0x0809C0E8",
                "bios_service": "LZ77UnCompVram",
                "source_register": "r0",
                "destination_register": "r1",
                "destination_formula": (
                    "0x06000000 + bg_charblock * 0x4000 + bg_tile_base * 32"
                ),
                "destination_pointer_global": "0x0201BD54",
                "evidence_type": "static_code",
            },
            routes["bg_graphics"],
        )
        self.assertEqual(
            {
                "helper_gba_address": "0x0808830C",
                "bios_decompress": "LZ77UnCompWram",
                "bios_copy": "CpuSet",
                "scratch_address": "0x02002880",
                "destination_formula": (
                    "0x05000000 + bg_palette_slot * 32"
                ),
                "evidence_type": "static_code",
            },
            routes["bg_palette"],
        )
        self.assertEqual(
            {
                "wrapper_gba_address": "0x0809C0E8",
                "bios_service": "LZ77UnCompVram",
                "destination_formula": (
                    "0x06010000 + obj_tile_slot * 32"
                ),
                "destination_slot_global": "0x0201BD5E",
                "evidence_type": "static_code",
            },
            routes["obj_graphics"],
        )
        self.assertEqual(
            {
                "helper_gba_address": "0x0808830C",
                "bios_decompress": "LZ77UnCompWram",
                "bios_copy": "CpuSet",
                "scratch_address": "0x02002880",
                "destination_formula": (
                    "0x05000200 + obj_palette_slot * 32"
                ),
                "destination_slot_global": "0x0201BD60",
                "evidence_type": "static_code",
            },
            routes["obj_palette"],
        )

    def test_parent_provenance_is_pinned_to_accepted_payloads_and_manifests(self):
        self.assertEqual(
            {
                "parent_layer_provenance_sha256": (
                    "4ba73a257695af886e939dd2dd2aff506a4fc4d0f952401f36f9dc408cc48578"
                ),
                "parent_layer_provenance_manifest_sha256": (
                    "6a24b443bea94177c8a017a1099cfb343b4d61bed765f6a4d7400cf738a16704"
                ),
                "font_tile_provenance_sha256": (
                    "4787d0049a7d7b92e106b7eb560e0893271dcf979739031f06ad16f5714d6d5a"
                ),
                "font_tile_provenance_manifest_sha256": (
                    "ad74f08c107a5326dc75c003614fcaff6fe1b0218087da80781d3d2316780375"
                ),
            },
            {
                key: self.artifact["runtime_binding"]["source"][key]
                for key in (
                    "parent_layer_provenance_sha256",
                    "parent_layer_provenance_manifest_sha256",
                    "font_tile_provenance_sha256",
                    "font_tile_provenance_manifest_sha256",
                )
            },
        )

    def test_renders_complete_bg_and_obj_source_atlases(self):
        expected = {
            "bg_graphics": ((128, 32), 64),
            "obj_graphics": ((96, 32), 48),
        }
        for key, (size, tile_count) in expected.items():
            resource = self.artifact["resources"][key]
            with Image.open(self.output / resource["atlas_png"]) as image:
                image.load()
                self.assertEqual("P", image.mode)
                self.assertEqual(size, image.size)
                self.assertNotIn("transparency", image.info)
            self.assertEqual(tile_count, resource["tile_count"])
            self.assertEqual(
                resource["atlas_sha256"],
                hashlib.sha256(
                    (self.output / resource["atlas_png"]).read_bytes()
                ).hexdigest(),
            )

    def test_classifies_the_complete_nonfont_denominator_without_promoting_layers(self):
        summary = self.artifact["runtime_binding"]["summary"]
        self.assertEqual(
            {
                "parent_layer_count": 61,
                "nonfont_cell_count": 59611,
                "exact_initializer_bg_content_cell_count": 5225,
                "exact_initializer_bg_content_distinct_hash_count": 23,
                "aliased_initializer_content_cell_count": 53488,
                "aliased_zero_cell_count": 48815,
                "aliased_common_fill_cell_count": 4673,
                "unmatched_nonfont_cell_count": 898,
                "unmatched_nonfont_distinct_hash_count": 39,
                "layers_with_exact_initializer_bg_content": 58,
                "layers_without_exact_initializer_bg_content_count": 3,
            },
            {
                key: summary[key]
                for key in (
                    "parent_layer_count",
                    "nonfont_cell_count",
                    "exact_initializer_bg_content_cell_count",
                    "exact_initializer_bg_content_distinct_hash_count",
                    "aliased_initializer_content_cell_count",
                    "aliased_zero_cell_count",
                    "aliased_common_fill_cell_count",
                    "unmatched_nonfont_cell_count",
                    "unmatched_nonfont_distinct_hash_count",
                    "layers_with_exact_initializer_bg_content",
                    "layers_without_exact_initializer_bg_content_count",
                )
            },
        )
        self.assertEqual(
            [
                {
                    "checkpoint": "alternate-character-overview.ss9",
                    "bg_index": 0,
                },
                {
                    "checkpoint": "scenario-41-pre-controller-after-a.ss9",
                    "bg_index": 3,
                },
                {
                    "checkpoint": "scenario-41-victory.ss9",
                    "bg_index": 3,
                },
            ],
            summary["layers_without_exact_initializer_bg_content"],
        )

        layers = self.artifact["runtime_binding"]["layers"]
        self.assertEqual(61, len(layers))
        for layer in layers:
            self.assertEqual(
                "unidentified_runtime_payload",
                layer["parent_classification"],
            )
            self.assertEqual(64, len(layer["parent_layer_sha256"]))
            self.assertEqual(
                layer["nonfont_cell_count"],
                layer["exact_initializer_bg_content_cell_count"]
                + layer["aliased_initializer_content_cell_count"]
                + layer["unmatched_nonfont_cell_count"],
            )
            for forbidden in (
                "classification",
                "source",
                "whole_bg_source",
                "exact_sources",
                "partial_sources",
            ):
                self.assertNotIn(forbidden, layer)

    def test_fixed_delta_and_palette_are_component_evidence_only(self):
        summary = self.artifact["runtime_binding"]["summary"]
        self.assertEqual(448, summary["common_runtime_tile_delta"])
        self.assertEqual(5106, summary["fixed_delta_cell_count"])
        self.assertEqual(119, summary["non_fixed_delta_cell_count"])
        self.assertEqual(
            28,
            summary["layers_with_all_exact_content_at_common_delta"],
        )
        self.assertEqual(58, summary["layers_with_exact_bg_palette_bank"])
        self.assertEqual(
            {
                "source_palette_bank": 0,
                "runtime_palette_bank": 14,
                "sha256": (
                    "6b8d0c736a2f8ba4f6954f7a1f1e7b18458c3b34bf216beb21b9f03f5ff8bfb9"
                ),
            },
            summary["common_palette_binding"],
        )

        bindings = [
            binding
            for layer in self.artifact["runtime_binding"]["layers"]
            for binding in layer["exact_initializer_bg_contents"]
        ]
        self.assertEqual(23, len({item["runtime_tile_sha256"] for item in bindings}))
        for binding in bindings:
            self.assertEqual(
                "exact_initializer_bg_graphics_content",
                binding["classification"],
            )
            self.assertTrue(binding["source_tile_indices"])
            self.assertEqual(
                len(binding["source_tile_indices"]),
                binding["source_tile_candidate_count"],
            )
            self.assertTrue(binding["linear_cell_ranges"])

    def test_aliases_remain_explicit_and_never_sign_unique_source_identity(self):
        groups = self.artifact["runtime_binding"]["alias_content_groups"]
        self.assertEqual(2, len(groups))
        zero = next(item for item in groups if item["alias_kind"] == "all_zero")
        fill = next(
            item for item in groups if item["alias_kind"] == "common_fill"
        )
        self.assertEqual(48815, zero["runtime_cell_count"])
        self.assertEqual([0] + list(range(34, 64)), zero["source_tile_indices"])
        self.assertEqual(4673, fill["runtime_cell_count"])
        self.assertEqual([1, 10], fill["source_tile_indices"])
        for item in groups:
            self.assertEqual(
                "aliased_initializer_bg_graphics_content",
                item["classification"],
            )
            self.assertFalse(item["unique_source_identity"])

    def test_scope_keeps_unproved_runtime_and_whole_screen_claims_false(self):
        self.assertEqual(
            {
                "four_initializer_resources_losslessly_exported": True,
                "initializer_literal_and_loader_routes_code_verified": True,
                "tracked_parent_nonfont_cells_fully_classified": True,
                "exact_initializer_bg_tile_content_components_bound": True,
                "aliased_zero_and_fill_content_retained": True,
                "whole_bg_source_identity_complete": False,
                "runtime_writer_identity_per_checkpoint_complete": False,
                "obj_runtime_instance_binding_complete": False,
                "all_game_visual_states_complete": False,
                "natural_language_resource_identity_complete": False,
                "remaining_nonfont_content_sources_complete": False,
            },
            self.artifact["scope"],
        )

    def test_independent_verifier_accepts_and_rejects_source_and_semantic_tamper(self):
        from tools.verify_initializer_resource_pack import verify_artifact

        source = (
            ROOT / "tools" / "verify_initializer_resource_pack.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)

        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        self.assertEqual(4, report["resource_count"])
        self.assertEqual(61, report["runtime_layer_count"])
        self.assertEqual(59611, report["nonfont_cell_count"])

        tamper_cases = [
            ("binary", "bg-graphics.bin"),
            ("png", "obj-graphics-atlas.png"),
            ("payload", "initializer-resource-pack.json"),
            ("extra", "unexpected.bin"),
            ("manifest", "manifest.json"),
        ]
        for kind, relative in tamper_cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                tampered = Path(temporary) / "artifact"
                shutil.copytree(self.output, tampered)
                path = tampered / relative
                if kind in {"binary", "png"}:
                    raw = bytearray(path.read_bytes())
                    raw[-1] ^= 1
                    path.write_bytes(raw)
                elif kind == "payload":
                    data = json.loads(path.read_text(encoding="utf-8"))
                    data["runtime_binding"]["layers"][0][
                        "parent_classification"
                    ] = "exact_static_source"
                    path.write_text(json.dumps(data), encoding="utf-8")
                elif kind == "manifest":
                    data = json.loads(path.read_text(encoding="utf-8"))
                    data["artifact_status"] = "unverified"
                    path.write_text(json.dumps(data), encoding="utf-8")
                else:
                    path.write_bytes(b"unexpected")
                report = verify_artifact(ROOT, tampered)
                self.assertFalse(report["verified"], kind)
                self.assertTrue(report["errors"], kind)

        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "artifact"
            shutil.copytree(self.output, tampered)
            path = tampered / "bg-graphics.bin"
            path.unlink()
            path.symlink_to(self.output / "bg-graphics.bin")
            report = verify_artifact(ROOT, tampered)
            self.assertFalse(report["verified"])
            self.assertIn("symbolic", " ".join(report["errors"]))

    def test_independent_lz77_rejects_a_back_reference_overrun(self):
        from tools.verify_initializer_resource_pack import _lz77

        malformed = bytes((0x10, 0x02, 0x00, 0x00, 0x40, 0x41, 0x00, 0x00))
        with self.assertRaisesRegex(ValueError, "exceeds declared size"):
            _lz77(malformed, 0)

    def test_output_replacement_is_safe_and_cli_is_reproducible(self):
        from tools.export_initializer_resource_pack import export_artifact

        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            foreign = temporary / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not this artifact"):
                export_artifact(ROOT, foreign)
            self.assertEqual(
                "keep",
                (foreign / "keep.txt").read_text(encoding="utf-8"),
            )

            first = temporary / "first"
            second = temporary / "second"
            command = [
                sys.executable,
                str(ROOT / "tools/export_initializer_resource_pack.py"),
                "--root",
                str(ROOT),
            ]
            subprocess.run(
                command + ["--output-dir", str(first)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                command + ["--output-dir", str(second)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(directory_hashes(first), directory_hashes(second))

            verification = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "tools/verify_initializer_resource_pack.py"
                    ),
                    "--root",
                    str(ROOT),
                    "--artifact-dir",
                    str(first),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(json.loads(verification.stdout)["verified"])


if __name__ == "__main__":
    unittest.main()
