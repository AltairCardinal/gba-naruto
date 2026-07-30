import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from patch_safety import PatchSafetyGate
from rom_layout import RomLayout


class RomLayoutTests(unittest.TestCase):
    def setUp(self):
        self.base = bytes([0x11] * 16 + [0xFF] * 16)
        self.layout_payload = {
            "version": 1,
            "base_rom": {
                "sha1": hashlib.sha1(self.base).hexdigest(),
                "size": len(self.base),
            },
            "cartridge_profile": {
                "id": "agb-standard-game-pak-rom",
                "rom_base": "0x08000000",
                "max_rom_size": "0x02000000",
            },
            "target_rom_size": "0x40",
            "fill_byte": "0xFF",
            "partitions": [
                {
                    "id": "legacy-tail",
                    "owner": "legacy",
                    "start": "0x10",
                    "end": "0x20",
                    "origin": "base_ff",
                    "alignment": 4,
                },
                {
                    "id": "visual-relocation",
                    "owner": "character_visuals",
                    "start": "0x20",
                    "end": "0x40",
                    "origin": "expanded_ff",
                    "alignment": 4,
                },
            ],
        }

    def _layout(self, payload=None):
        return RomLayout.from_dict(payload or self.layout_payload, self.base)

    def test_validates_base_provenance_and_extends_with_declared_fill(self):
        layout = self._layout()
        self.assertEqual(0x40, layout.target_rom_size)
        self.assertEqual(
            self.base + bytes([0xFF] * 32),
            layout.expanded_base(),
        )

    def test_rejects_overlapping_partitions(self):
        payload = json.loads(json.dumps(self.layout_payload))
        payload["partitions"][1]["start"] = "0x1C"
        with self.assertRaisesRegex(ValueError, "overlap"):
            self._layout(payload)

    def test_rejects_base_ff_partition_with_non_ff_bytes(self):
        payload = json.loads(json.dumps(self.layout_payload))
        payload["partitions"][0]["start"] = "0x0C"
        with self.assertRaisesRegex(ValueError, "is not filled with 0xFF"):
            self._layout(payload)

    def test_rejects_unaligned_or_non_power_of_two_expansion(self):
        payload = json.loads(json.dumps(self.layout_payload))
        payload["target_rom_size"] = "0x3C"
        with self.assertRaisesRegex(ValueError, "power of two"):
            self._layout(payload)

    def test_rejects_target_larger_than_cartridge_profile(self):
        payload = json.loads(json.dumps(self.layout_payload))
        payload["target_rom_size"] = "0x04000000"
        with self.assertRaisesRegex(ValueError, "exceeds cartridge profile"):
            self._layout(payload)

    def test_allocation_requires_matching_partition_owner_and_virtual_precondition(self):
        layout = self._layout()
        gate = PatchSafetyGate(self.base, layout=layout)
        patch = {
            "id": "bundle",
            "type": "bytes",
            "offset": 0x20,
            "before_hex": "ffffffff",
            "after_hex": "01020304",
            "allocation": {
                "partition": "visual-relocation",
                "owner": "character_visuals",
            },
        }
        result = gate.register(patch, patch_class="allocation")
        self.assertEqual("visual-relocation", result["allocation_partition"])
        self.assertEqual("character_visuals", result["allocation_owner"])

        wrong_owner = {
            **patch,
            "id": "wrong-owner",
            "offset": 0x24,
            "allocation": {
                "partition": "visual-relocation",
                "owner": "other",
            },
        }
        with self.assertRaisesRegex(ValueError, "owner"):
            gate.register(wrong_owner, patch_class="allocation")

    def test_expansion_does_not_relax_normal_game_effective_bounds(self):
        layout = self._layout()
        gate = PatchSafetyGate(self.base, layout=layout)
        with self.assertRaisesRegex(ValueError, "allocation"):
            gate.register(
                {
                    "id": "undeclared-expanded-write",
                    "offset": 0x20,
                    "before_hex": "ffff",
                    "after_hex": "0102",
                },
                patch_class="game_effective",
            )

    def test_allocation_rejects_wrong_virtual_before_bytes(self):
        layout = self._layout()
        gate = PatchSafetyGate(self.base, layout=layout)
        with self.assertRaisesRegex(ValueError, "base-ROM mismatch"):
            gate.register(
                {
                    "id": "bad-before",
                    "offset": 0x20,
                    "before_hex": "0000",
                    "after_hex": "0102",
                    "allocation": {
                        "partition": "visual-relocation",
                        "owner": "character_visuals",
                    },
                },
                patch_class="allocation",
            )

    def test_audit_writes_require_the_declared_base_ff_partition(self):
        layout = self._layout()
        gate = PatchSafetyGate(self.base, layout=layout)
        patch = {
            "id": "audit-row",
            "offset": 0x10,
            "after_hex": "01020304",
            "allocation": {
                "partition": "legacy-tail",
                "owner": "legacy",
            },
        }
        result = gate.register(patch, patch_class="audit")
        self.assertEqual("legacy-tail", result["allocation_partition"])
        self.assertEqual("legacy", result["allocation_owner"])

        with self.assertRaisesRegex(ValueError, "allocation declaration"):
            gate.register(
                {
                    "id": "undeclared-audit",
                    "offset": 0,
                    "after_hex": "01",
                },
                patch_class="audit",
            )

        with self.assertRaisesRegex(ValueError, "outside partition"):
            gate.register(
                {
                    **patch,
                    "id": "misdirected-audit",
                    "offset": 0,
                },
                patch_class="audit",
            )

    def test_existing_allocator_must_match_registered_partition_exactly(self):
        layout = self._layout()
        partition = layout.require_exact_partition(
            "legacy-tail",
            "legacy",
            0x10,
            0x20,
        )
        self.assertEqual("legacy-tail", partition.id)
        with self.assertRaisesRegex(ValueError, "must exactly match"):
            layout.require_exact_partition(
                "legacy-tail",
                "legacy",
                0x10,
                0x1C,
            )

    def test_manifest_allocator_declarations_are_bound_to_layout_registry(self):
        from tools.build_mod import validate_layout_allocators

        layout = self._layout()
        manifest = {
            "patches": [
                {
                    "id": "legacy-allocator",
                    "type": "dialogue_var",
                    "free_space_start": "0x10",
                    "free_space_end": "0x20",
                }
            ]
        }
        bindings = validate_layout_allocators(
            manifest,
            layout,
            allocator_bindings={
                "dialogue_var": ("legacy-tail", "legacy"),
            },
        )
        self.assertEqual(
            [
                {
                    "patch_id": "legacy-allocator",
                    "patch_type": "dialogue_var",
                    "partition": "legacy-tail",
                    "owner": "legacy",
                    "start": 0x10,
                    "end": 0x20,
                }
            ],
            bindings,
        )
        manifest["patches"][0]["free_space_end"] = "0x1C"
        with self.assertRaisesRegex(ValueError, "must exactly match"):
            validate_layout_allocators(
                manifest,
                layout,
                allocator_bindings={
                    "dialogue_var": ("legacy-tail", "legacy"),
                },
            )


class BuildExpansionIntegrationTests(unittest.TestCase):
    def test_build_expands_only_from_explicit_layout_and_reports_provenance(self):
        from tools import build_mod

        base = bytes([0xA5] * 16 + [0xFF] * 16)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for relative in ("rom", "sequel/patches", "sequel"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            (root / "rom/base.gba").write_bytes(base)
            layout = {
                "version": 1,
                "base_rom": {
                    "sha1": hashlib.sha1(base).hexdigest(),
                    "size": len(base),
                },
                "cartridge_profile": {
                    "id": "agb-standard-game-pak-rom",
                    "rom_base": "0x08000000",
                    "max_rom_size": "0x02000000",
                },
                "target_rom_size": "0x40",
                "fill_byte": "0xFF",
                "partitions": [
                    {
                        "id": "visual-relocation",
                        "owner": "character_visuals",
                        "start": "0x20",
                        "end": "0x40",
                        "origin": "expanded_ff",
                        "alignment": 4,
                    }
                ],
            }
            (root / "sequel/rom-layout.json").write_text(
                json.dumps(layout),
                encoding="utf-8",
            )
            (root / "sequel/patches/manifest.json").write_text(
                json.dumps({"version": 1, "patches": []}),
                encoding="utf-8",
            )
            project = {
                "project_id": "expansion-test",
                "base_rom": {
                    "path": "rom/base.gba",
                    "sha1": hashlib.sha1(base).hexdigest(),
                },
                "rom_layout": "sequel/rom-layout.json",
                "patch_manifest": "sequel/patches/manifest.json",
                "build": {
                    "output_rom": "build/output.gba",
                    "report": "build/report.json",
                },
            }
            project_path = root / "sequel/project.json"
            project_path.write_text(json.dumps(project), encoding="utf-8")

            with mock.patch.object(build_mod, "ROOT", root):
                report = build_mod.build(project_path)

            output = (root / "build/output.gba").read_bytes()
            self.assertEqual(base + bytes([0xFF] * 32), output)
            self.assertEqual(0x40, report["output_rom"]["size"])
            self.assertEqual(0x20, report["rom_layout"]["base_rom_size"])
            self.assertEqual(0x40, report["rom_layout"]["target_rom_size"])
            self.assertEqual(
                "agb-standard-game-pak-rom",
                report["rom_layout"]["cartridge_profile"],
            )

    def test_generic_apply_patch_uses_allocation_class_for_expanded_subpatch(self):
        from tools import build_mod

        base = bytes([0xFF] * 32)
        layout = RomLayout.from_dict(
            {
                "version": 1,
                "base_rom": {
                    "sha1": hashlib.sha1(base).hexdigest(),
                    "size": len(base),
                },
                "cartridge_profile": {
                    "id": "agb-standard-game-pak-rom",
                    "rom_base": "0x08000000",
                    "max_rom_size": "0x02000000",
                },
                "target_rom_size": "0x40",
                "fill_byte": "0xFF",
                "partitions": [
                    {
                        "id": "visual-relocation",
                        "owner": "character_visuals",
                        "start": "0x20",
                        "end": "0x40",
                        "origin": "expanded_ff",
                        "alignment": 4,
                    }
                ],
            },
            base,
        )
        data = bytearray(layout.expanded_base())
        gate = PatchSafetyGate(base, layout=layout)
        result = build_mod.apply_patch(
            data,
            {
                "id": "expanded-subpatch",
                "type": "bytes",
                "offset": 0x20,
                "before_hex": "ffffffff",
                "after_hex": "01020304",
                "allocation": {
                    "partition": "visual-relocation",
                    "owner": "character_visuals",
                },
            },
            gate=gate,
        )
        self.assertEqual("allocation", result["patch_class"])
        self.assertEqual(bytes.fromhex("01020304"), data[0x20:0x24])


if __name__ == "__main__":
    unittest.main()
