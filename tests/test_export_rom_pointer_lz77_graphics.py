import hashlib
import json
import shutil
import struct
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PALETTES = {
    "0x08348BE4": 32,
    "0x0834941C": 32,
    "0x083496B0": 32,
    "0x083F0AF0": 32,
    "0x083F2794": 32,
    "0x083F2CB0": 32,
    "0x08405FF0": 256,
    "0x08457EA8": 32,
    "0x0845830C": 32,
    "0x084638D4": 32,
    "0x084638F4": 32,
    "0x08463FFC": 32,
}
UNRESOLVED = {
    "0x0812D2F0",
    "0x083496F8",
}


def directory_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def png_header(path: Path) -> tuple[int, int, int, int]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    length = struct.unpack_from(">I", raw, 8)[0]
    if raw[12:16] != b"IHDR" or length != 13:
        raise AssertionError(f"missing PNG IHDR: {path}")
    width, height, bit_depth, color_type = struct.unpack_from(
        ">IIBB", raw, 16
    )
    return width, height, bit_depth, color_type


class ExportRomPointerLz77GraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.export_rom_pointer_lz77_graphics import export_artifact

        cls.temporary = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temporary.name) / "artifact"
        cls.catalog = export_artifact(ROOT, cls.output)
        cls.manifest = json.loads(
            (cls.output / "manifest.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_closes_the_finite_new_graphics_preview_denominator(self):
        self.assertEqual("rom-pointer-lz77-graphics-v1", self.catalog["schema"])
        self.assertEqual(
            {
                "graphics_record_count": 20,
                "raw_palette_bound_count": 12,
                "runtime_oam_palette_bound_count": 2,
                "lz77_palette_bound_count": 4,
                "source_palette_bound_count": 18,
                "unresolved_palette_count": 2,
                "source_palette_preview_count": 33,
                "index_only_preview_count": 2,
                "preview_file_count": 35,
                "raw_palette_source_count": 12,
                "raw_palette_bundle_size": 608,
                "runtime_checkpoint_count": 91,
            },
            self.catalog["summary"],
        )
        self.assertEqual(20, len(self.catalog["graphics"]))
        self.assertEqual(
            {
                "window_bytes": 32,
                "sources": (
                    "all literal_load_users of the 20 source-inventory "
                    "graphics records"
                ),
                "accepted_operations": [
                    "r0 ROM LZ77 source -> LZ77UnCompVram -> PRAM, size 32",
                    (
                        "r0 ROM raw source -> CpuSet/CpuFastSet -> PRAM, "
                        "exact unit count"
                    ),
                ],
                "runtime_oam_rule": (
                    "scan every tracked .ss9 in lexical order; require the full "
                    "graphics payload at its statically proven OBJ VRAM "
                    "destination, an active hardware OAM object whose 4bpp tile "
                    "range intersects it, one consistent attr2 palette bank, and "
                    "one unique exact 32-byte ROM palette source"
                ),
                "runtime_conflict_policy": (
                    "different selected palette bytes or non-unique ROM source "
                    "leave the record unresolved"
                ),
                "unknown_instruction_policy": "invalidate r0-r3 (fail closed)",
                "call_policy": (
                    "record actual arguments at BL, then invalidate r0-r3"
                ),
                "unresolved_rule": (
                    "no accepted static palette operation and no accepted "
                    "runtime OAM binding"
                ),
            },
            self.catalog["selection_rule"],
        )
        self.assertEqual(
            UNRESOLVED,
            {
                entry["graphics_address"]
                for entry in self.catalog["graphics"]
                if entry["palette_binding"]["kind"] == "unresolved"
            },
        )

    def test_binds_shared_battle_obj_palette_from_natural_oam(self):
        entries = {
            entry["graphics_address"]: entry
            for entry in self.catalog["graphics"]
        }
        self.assertNotIn("0x08349368", entries)
        expected = {
            "0x0812C8B0": {
                "destination": "0x06016FE0",
                "tile_start": 895,
                "tile_end": 899,
                "oam_observation_count": 8,
            },
            "0x0812D134": {
                "destination": "0x06017060",
                "tile_start": 899,
                "tile_end": 901,
                "oam_observation_count": 4,
            },
        }
        for address, runtime_expected in expected.items():
            binding = entries[address]["palette_binding"]
            self.assertEqual("runtime_oam_raw_rom", binding["kind"])
            self.assertEqual(["0x08457EA8"], binding["source_addresses"])
            evidence = binding["operation_evidence"]
            self.assertEqual(1, len(evidence))
            observation = evidence[0]
            self.assertEqual(
                "artifacts/runtime-checkpoints/actionable-move-grid.ss9",
                observation["checkpoint_path"],
            )
            self.assertEqual(
                "0x050003E0", observation["palette_address"]
            )
            self.assertEqual(15, observation["palette_bank"])
            for key, value in runtime_expected.items():
                self.assertEqual(value, observation[key])
            self.assertEqual(
                observation["palette_sha256"],
                next(
                    item["sha256"]
                    for item in self.catalog["raw_palette_sources"]
                    if item["gba_address"] == "0x08457EA8"
                ),
            )

    def test_runtime_binding_fails_closed_on_palette_ambiguity(self):
        from tools.export_rom_pointer_lz77_graphics import (
            _discover_runtime_oam_binding,
        )

        graphics = bytes([0x55] * 32)
        palette_a = bytes(range(32))
        palette_b = bytes(range(32, 64))
        record = {
            "classification": {
                "destination_addresses": ["0x06010000"],
            }
        }

        class FakeState:
            version_magic = 0x01000007

            def __init__(self, palette, banks=(15,)):
                self.palette = palette
                self.banks = banks

            def read_memory(self, address, size):
                if address == 0x04000000:
                    return struct.pack("<H", 0x40) + bytes(size - 2)
                if address == 0x06010000:
                    return graphics[:size]
                if address == 0x07000000:
                    oam = bytearray(0x400)
                    for index, bank in enumerate(self.banks):
                        struct.pack_into(
                            "<HHH", oam, index * 8, 0, 0, bank << 12
                        )
                    for index in range(len(self.banks), 128):
                        struct.pack_into(
                            "<HHH", oam, index * 8, 0x0200, 0, 0
                        )
                    return bytes(oam)
                if address == 0x050003E0:
                    return self.palette[:size]
                raise AssertionError(f"unexpected memory read: {address:#x}")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.ss9"
            second = root / "second.ss9"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            rom = b"prefix" + palette_a + b"suffix"

            with mock.patch(
                "tools.export_rom_pointer_lz77_graphics.load_gba_state",
                return_value=FakeState(palette_a, banks=(15, 14)),
            ):
                self.assertIsNone(
                    _discover_runtime_oam_binding(
                        root, rom, record, graphics, [first]
                    )
                )

            states = {
                first: FakeState(palette_a),
                second: FakeState(palette_b),
            }
            with mock.patch(
                "tools.export_rom_pointer_lz77_graphics.load_gba_state",
                side_effect=lambda path: states[path],
            ):
                self.assertIsNone(
                    _discover_runtime_oam_binding(
                        root, rom + palette_b, record, graphics, [first, second]
                    )
                )

            with mock.patch(
                "tools.export_rom_pointer_lz77_graphics.load_gba_state",
                return_value=FakeState(palette_a),
            ):
                self.assertIsNone(
                    _discover_runtime_oam_binding(
                        root,
                        palette_a + b"gap" + palette_a,
                        record,
                        graphics,
                        [first],
                    )
                )

    def test_packs_every_static_raw_palette_losslessly(self):
        bundle = (self.output / "raw-palettes.bgr555.bin").read_bytes()
        self.assertEqual(608, len(bundle))
        self.assertEqual(RAW_PALETTES, {
            item["gba_address"]: item["size"]
            for item in self.catalog["raw_palette_sources"]
        })
        rom = (ROOT / "rom/base.gba").read_bytes()
        cursor = 0
        for item in self.catalog["raw_palette_sources"]:
            self.assertEqual(cursor, item["bundle_offset"])
            source = int(item["gba_address"], 16) - 0x08000000
            expected = rom[source : source + item["size"]]
            actual = bundle[cursor : cursor + item["size"]]
            self.assertEqual(expected, actual)
            self.assertEqual(item["sha256"], hashlib.sha256(actual).hexdigest())
            self.assertTrue(item["copy_evidence"])
            cursor += item["size"]
        self.assertEqual(len(bundle), cursor)

    def test_preserves_direct_shared_and_multi_bank_palette_evidence(self):
        entries = {
            entry["graphics_address"]: entry
            for entry in self.catalog["graphics"]
        }
        self.assertEqual(
            ["0x0834941C"],
            entries["0x08348F00"]["palette_binding"]["source_addresses"],
        )
        self.assertEqual(
            ["0x083F0AC8"],
            entries["0x083F00C8"]["palette_binding"]["source_addresses"],
        )
        self.assertEqual(
            ["0x08405FF0"],
            entries["0x08405EA4"]["palette_binding"]["source_addresses"],
        )
        self.assertEqual(
            8, len(entries["0x08405EA4"]["previews"])
        )
        self.assertEqual(
            ["0x084638D4", "0x084638F4"],
            entries["0x08463688"]["palette_binding"]["source_addresses"],
        )
        self.assertEqual(
            ["0x08463FFC"],
            entries["0x085B6000"]["palette_binding"]["source_addresses"],
        )
        self.assertEqual(
            ["0x083F0AF0"],
            entries["0x085B6880"]["palette_binding"]["source_addresses"],
        )

    def test_palette_discovery_tracks_actual_r0_across_calls(self):
        from tools.export_rom_pointer_lz77_graphics import (
            discover_palette_operations,
        )

        rom = (ROOT / "rom/base.gba").read_bytes()
        operations = discover_palette_operations(rom, 0x0808B5D4)
        raw_sources = {
            operation["source_address"]
            for operation in operations
            if operation["kind"] == "raw_rom"
        }
        self.assertEqual({"0x0834941C"}, raw_sources)
        self.assertNotIn("0x08348F00", raw_sources)

        without_palette_load = bytearray(rom)
        struct.pack_into("<H", without_palette_load, 0x08B5DC, 0x46C0)
        operations = discover_palette_operations(
            bytes(without_palette_load), 0x0808B5D4
        )
        self.assertEqual(
            set(),
            {
                operation["source_address"]
                for operation in operations
                if operation["kind"] == "raw_rom"
            },
        )

    def test_exporter_and_verifier_do_not_embed_binding_conclusion_tables(self):
        for relative in (
            "tools/export_rom_pointer_lz77_graphics.py",
            "tools/verify_rom_pointer_lz77_graphics.py",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("RAW_BINDINGS", source)
            self.assertNotIn("LZ77_BINDINGS", source)
            self.assertNotIn("UNRESOLVED =", source)

    def test_outputs_deterministic_indexed_candidate_atlases(self):
        previews = [
            preview
            for entry in self.catalog["graphics"]
            for preview in entry["previews"]
        ]
        self.assertEqual(35, len(previews))
        self.assertEqual(35, len({preview["file"] for preview in previews}))
        for preview in previews:
            path = self.output / preview["file"]
            self.assertEqual(
                preview["png_sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
            )
            width, height, bit_depth, color_type = png_header(path)
            self.assertEqual((width, height), (
                preview["width"], preview["height"]
            ))
            self.assertEqual((8, 3), (bit_depth, color_type))
            self.assertIn(
                preview["palette_origin"],
                {
                    "raw_rom",
                    "runtime_oam_raw_rom",
                    "lz77_rom",
                    "synthetic_index_only",
                },
            )

    def test_scope_keeps_candidate_previews_separate_from_final_images(self):
        self.assertEqual(
            {
                "new_pointer_reachable_graphics_records_cataloged": True,
                "source_palette_bound_subset_previewed": True,
                "unresolved_palette_records_index_previewed": True,
                "all_previews_are_final_visible_images": False,
                "tilemap_or_oam_composition_complete": False,
                "all_raw_graphics_complete": False,
                "all_game_visual_states_complete": False,
                "generic_image_writeback_complete": False,
            },
            self.catalog["scope"],
        )

    def test_independent_verifier_accepts_and_rejects_tamper(self):
        from tools.verify_rom_pointer_lz77_graphics import verify_artifact

        source = (
            ROOT / "tools/verify_rom_pointer_lz77_graphics.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from tools", source)
        self.assertNotIn("import tools", source)
        report = verify_artifact(ROOT, self.output)
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual([], report["errors"])
        self.assertEqual(20, report["graphics_record_count"])
        self.assertEqual(35, report["preview_file_count"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            preview = next(tampered.glob("previews/*.png"))
            raw = bytearray(preview.read_bytes())
            raw[-1] ^= 1
            preview.write_bytes(raw)
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"])
            self.assertTrue(rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            catalog_path = tampered / "graphics-catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            bound = next(
                entry
                for entry in catalog["graphics"]
                if entry["palette_binding"]["kind"] == "raw_rom"
            )
            bound["palette_binding"]["source_addresses"][0] = "0x08348F00"
            catalog_path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["graphics-catalog.json"] = hashlib.sha256(
                catalog_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"], rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            catalog_path = tampered / "graphics-catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            bound = next(
                entry
                for entry in catalog["graphics"]
                if entry["palette_binding"]["kind"]
                == "runtime_oam_raw_rom"
            )
            bound["palette_binding"]["operation_evidence"][0][
                "palette_bank"
            ] = 14
            catalog_path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["graphics-catalog.json"] = hashlib.sha256(
                catalog_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"], rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            bundle_path = tampered / "raw-palettes.bgr555.bin"
            bundle = bytearray(bundle_path.read_bytes())
            bundle[0] ^= 1
            bundle_path.write_bytes(bundle)
            manifest_path = tampered / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["raw-palettes.bgr555.bin"] = hashlib.sha256(
                bundle_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"], rejected["errors"])

        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "artifact"
            shutil.copytree(self.output, tampered)
            (tampered / "unexpected.txt").write_text("foreign")
            rejected = verify_artifact(ROOT, tampered)
            self.assertFalse(rejected["verified"], rejected["errors"])

    def test_export_is_deterministic_and_refuses_foreign_output(self):
        from tools.export_rom_pointer_lz77_graphics import export_artifact

        with tempfile.TemporaryDirectory() as tmp:
            repeated = Path(tmp) / "artifact"
            export_artifact(ROOT, repeated)
            self.assertEqual(directory_hashes(self.output), directory_hashes(repeated))

            foreign = Path(tmp) / "foreign"
            foreign.mkdir()
            (foreign / "keep.txt").write_text("owned by someone else")
            with self.assertRaises(ValueError):
                export_artifact(ROOT, foreign)
            self.assertEqual(
                "owned by someone else", (foreign / "keep.txt").read_text()
            )


if __name__ == "__main__":
    unittest.main()
