import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.butano.render_scenario_41_gpu import (
    _background_pixel,
    _object_pixel,
    _rgb,
    render_boundary,
)


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "butano" / "generate_scenario_41_assets.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("scenario_41_assets", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def bmp_contract(path: Path) -> tuple[int, int, int]:
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise AssertionError(f"{path.name} is not a BMP")
    dib_size = struct.unpack_from("<I", data, 14)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    bits_per_pixel = struct.unpack_from("<H", data, 28)[0]
    if dib_size != 40:
        raise AssertionError(f"{path.name} has unexpected DIB size {dib_size}")
    return width, height, bits_per_pixel


class Scenario41AssetsTest(unittest.TestCase):
    def test_combat_layers_preserve_original_alpha_blending(self):
        generator = load_generator()
        reference = ROOT / "artifacts/scenario-41-combat-reference-v1"
        for boundary_name in ("target-select", "attack-confirmation"):
            with self.subTest(boundary=boundary_name):
                boundary = reference / boundary_name
                palette, layers = generator.reconstruct_blended_combat_layers(boundary)
                actual = bytearray()
                for y in range(160):
                    for x in range(240):
                        offset = y * 256 + x
                        bottom, middle, top = (layer[offset] for layer in layers)
                        if top:
                            color = palette[top]
                        elif middle:
                            color = tuple(
                                min(255, (first * 10 + second * 10) // 16)
                                for first, second in zip(
                                    palette[middle], palette[bottom], strict=True
                                )
                            )
                        else:
                            color = palette[bottom]
                        actual.extend(color)
                self.assertEqual(bytes(actual), render_boundary(boundary))

    def test_screen_aligned_reference_layers_recompose_exact_boundaries(self):
        generator = load_generator()
        cases = {
            "turn-1-complete": (
                (((0,), ()), ((), tuple(range(1, 13))), ((3,), (0,))),
            ),
            "victory": (
                (((0,), ()), ((), tuple(range(2, 7))), ((3,), (0, 1))),
            ),
            "postbattle": (
                (((0,), ()), ((3,), (0,))),
            ),
        }
        for boundary_name, (specs,) in cases.items():
            with self.subTest(boundary=boundary_name):
                boundary = ROOT / "artifacts/scenario-41-reference-v1" / boundary_name
                palette, layers = generator.reconstruct_screen_layers(boundary, specs)
                actual = bytearray()
                for y in range(160):
                    for x in range(240):
                        index = 0
                        for layer in layers:
                            candidate = layer[y * 256 + x]
                            if candidate:
                                index = candidate
                        actual.extend(palette[index])
                self.assertEqual(bytes(actual), render_boundary(boundary))

    def test_reconstructs_the_original_36_by_44_tile_map(self):
        generator = load_generator()
        reconstructed = generator.reconstruct_map(ROOT / "rom/base.gba")
        self.assertEqual((reconstructed["width"], reconstructed["height"]), (288, 352))
        self.assertEqual(len(reconstructed["pixels"]), 288 * 352)
        self.assertEqual(len(reconstructed["palette"]), 192)

        boundary = ROOT / "artifacts/scenario-41-reference-v1/player-turn"
        io = (boundary / "io.bin").read_bytes()
        pram = (boundary / "pram.bin").read_bytes()
        vram = (boundary / "vram.bin").read_bytes()
        scroll_x = struct.unpack_from("<H", io, 0x10)[0] & 0x1FF
        scroll_y = struct.unpack_from("<H", io, 0x12)[0] & 0x1FF
        for screen_y in range(128):
            for screen_x in range(240):
                expected = _background_pixel(io, pram, vram, 0, screen_x, screen_y)
                world_x = screen_x + scroll_x
                world_y = screen_y + scroll_y
                palette_index = reconstructed["pixels"][world_y * 288 + world_x]
                if expected is None:
                    self.assertEqual(palette_index, 0)
                else:
                    self.assertEqual(
                        bytes(reconstructed["palette"][palette_index]),
                        _rgb(expected.color),
                    )

    def test_reconstructs_the_original_player_hud_background_layer(self):
        generator = load_generator()
        boundary = ROOT / "artifacts/scenario-41-reference-v1/player-turn"
        reconstructed = generator.reconstruct_reference_bg(boundary, 3)
        self.assertEqual((reconstructed["width"], reconstructed["height"]), (256, 256))
        io = (boundary / "io.bin").read_bytes()
        pram = (boundary / "pram.bin").read_bytes()
        vram = (boundary / "vram.bin").read_bytes()
        for y in range(160):
            for x in range(240):
                expected = _background_pixel(io, pram, vram, 3, x, y)
                palette_index = reconstructed["pixels"][y * 256 + x]
                if expected is None:
                    self.assertEqual(palette_index, 0)
                else:
                    self.assertEqual(
                        bytes(reconstructed["palette"][palette_index]),
                        _rgb(expected.color),
                    )

    def test_reconstructs_original_naruto_cursor_and_move_overlay(self):
        generator = load_generator()
        boundary = ROOT / "artifacts/scenario-41-reference-v1/player-turn"
        io = (boundary / "io.bin").read_bytes()
        pram = (boundary / "pram.bin").read_bytes()
        oam = (boundary / "oam.bin").read_bytes()
        vram = (boundary / "vram.bin").read_bytes()
        dispcnt = struct.unpack_from("<H", io, 0)[0]

        naruto = generator.reconstruct_reference_sprite(
            boundary, (11,), 104, 24, 32, 64
        )
        self.assertEqual((naruto["width"], naruto["height"]), (32, 64))
        for y in range(64):
            for x in range(32):
                expected = _object_pixel(dispcnt, pram, oam, vram, 11, x + 104, y + 24)
                palette_index = naruto["pixels"][y * 32 + x]
                if expected is None:
                    self.assertEqual(palette_index, 0)
                else:
                    self.assertEqual(bytes(naruto["palette"][palette_index]), _rgb(expected.color))

        cursor_indices = tuple(range(3, 11))
        cursor = generator.reconstruct_reference_sprite(
            boundary, cursor_indices, 88, 24, 64, 64
        )
        self.assertEqual((cursor["width"], cursor["height"]), (64, 64))
        self.assertGreater(sum(pixel != 0 for pixel in cursor["pixels"]), 0)

        cursor_shadow = generator.reconstruct_reference_sprite(
            boundary, tuple(range(12, 16)), 88, 25, 64, 64
        )
        self.assertEqual((cursor_shadow["width"], cursor_shadow["height"]), (64, 64))
        self.assertGreater(sum(pixel != 0 for pixel in cursor_shadow["pixels"]), 0)

        select_label = generator.reconstruct_reference_sprite(
            boundary, (0, 1, 2), 184, 0, 64, 32
        )
        self.assertEqual((select_label["width"], select_label["height"]), (64, 32))
        self.assertGreater(sum(pixel != 0 for pixel in select_label["pixels"]), 0)

        overlay = generator.reconstruct_reference_bg(boundary, 2)
        self.assertEqual((overlay["width"], overlay["height"]), (256, 256))

    def test_generator_writes_deterministic_butano_assets(self):
        self.assertTrue(GENERATOR.is_file(), "scenario 41 asset generator is missing")
        generator = load_generator()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_dir = Path(first)
            second_dir = Path(second)
            first_hashes = generator.generate_assets(first_dir)
            second_hashes = generator.generate_assets(second_dir)

            self.assertEqual(first_hashes, second_hashes)
            self.assertEqual(
                set(first_hashes),
                {
                    "scenario_41_map.bmp",
                    "scenario_41_map.json",
                    "scenario_41_move_overlay.bmp",
                    "scenario_41_move_overlay.json",
                    "scenario_41_naruto.bmp",
                    "scenario_41_naruto.json",
                    "scenario_41_cursor.bmp",
                    "scenario_41_cursor.json",
                    "scenario_41_cursor_shadow.bmp",
                    "scenario_41_cursor_shadow.json",
                    "scenario_41_select_label.bmp",
                    "scenario_41_select_label.json",
                    "scenario_41_facing_ui.bmp",
                    "scenario_41_facing_ui.json",
                    "scenario_41_facing_naruto.bmp",
                    "scenario_41_facing_naruto.json",
                    "scenario_41_facing_cursor.bmp",
                    "scenario_41_facing_cursor.json",
                    "scenario_41_facing_cursor_shadow.bmp",
                    "scenario_41_facing_cursor_shadow.json",
                    "scenario_41_technique_ui.bmp",
                    "scenario_41_technique_ui.json",
                    "scenario_41_technique_naruto.bmp",
                    "scenario_41_technique_naruto.json",
                    "scenario_41_technique_cursor.bmp",
                    "scenario_41_technique_cursor.json",
                    "scenario_41_technique_cursor_shadow.bmp",
                    "scenario_41_technique_cursor_shadow.json",
                    "scenario_41_technique_left_marker.bmp",
                    "scenario_41_technique_left_marker.json",
                    "scenario_41_technique_bottom_controls.bmp",
                    "scenario_41_technique_bottom_controls.json",
                    "scenario_41_technique_icons.bmp",
                    "scenario_41_technique_icons.json",
                    "scenario_41_tutorial_bg.bmp",
                    "scenario_41_tutorial_bg.json",
                    "scenario_41_tutorial_portraits.bmp",
                    "scenario_41_tutorial_portraits.json",
                    "scenario_41_tutorial_ui.bmp",
                    "scenario_41_tutorial_ui.json",
                    "scenario_41_victory_bg.bmp",
                    "scenario_41_victory_bg.json",
                    "scenario_41_victory_actor.bmp",
                    "scenario_41_victory_actor.json",
                    "scenario_41_victory_title.bmp",
                    "scenario_41_victory_title.json",
                    "scenario_41_postbattle_bg.bmp",
                    "scenario_41_postbattle_bg.json",
                    "scenario_41_postbattle_ui.bmp",
                    "scenario_41_postbattle_ui.json",
                    "scenario_41_player_hud.bmp",
                    "scenario_41_player_hud.json",
                    "scenario_41_units.bmp",
                    "scenario_41_units.json",
                    *(
                        f"scenario_41_{prefix}_{layer}.{extension}"
                        for prefix in (
                            "result",
                            "level_up_1",
                            "level_up_2",
                            *(f"postbattle_dialogue_{index}" for index in range(1, 12)),
                            "action_menu_0",
                            "action_menu_1",
                            "end_confirmation",
                            "defense_confirmation",
                            "target_select",
                            "attack_confirmation",
                            "combat_dialogue",
                            "combat_popup",
                        )
                        for layer in ("bottom", "middle", "top")
                        for extension in ("bmp", "json")
                    ),
                },
            )
            for name, digest in first_hashes.items():
                self.assertEqual(
                    hashlib.sha256((first_dir / name).read_bytes()).hexdigest(),
                    digest,
                )

            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_map.bmp"), (512, 512, 8)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_units.bmp"), (16, 48, 4)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_player_hud.bmp"), (256, 256, 8)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_move_overlay.bmp"), (256, 256, 8)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_naruto.bmp"), (32, 64, 4)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_cursor.bmp"), (64, 64, 4)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_cursor_shadow.bmp"), (64, 64, 4)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_select_label.bmp"), (64, 32, 4)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_facing_ui.bmp"), (256, 256, 8)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_facing_naruto.bmp"), (32, 64, 4)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_technique_ui.bmp"), (256, 256, 8)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_technique_bottom_controls.bmp"),
                (64, 32, 4),
            )
            for name in (
                "scenario_41_tutorial_bg.bmp",
                "scenario_41_tutorial_portraits.bmp",
                "scenario_41_tutorial_ui.bmp",
                "scenario_41_victory_bg.bmp",
                "scenario_41_victory_actor.bmp",
                "scenario_41_victory_title.bmp",
                "scenario_41_postbattle_bg.bmp",
                "scenario_41_postbattle_ui.bmp",
            ):
                with self.subTest(name=name):
                    self.assertEqual(bmp_contract(first_dir / name), (256, 256, 8))
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_result_top.bmp"), (256, 256, 8)
            )
            self.assertEqual(
                bmp_contract(first_dir / "scenario_41_postbattle_dialogue_11_bottom.bmp"),
                (256, 256, 8),
            )
            self.assertEqual(
                json.loads((first_dir / "scenario_41_map.json").read_text()),
                {"type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256},
            )
            self.assertEqual(
                json.loads((first_dir / "scenario_41_player_hud.json").read_text()),
                {"type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256},
            )
            self.assertEqual(
                json.loads((first_dir / "scenario_41_units.json").read_text()),
                {"type": "sprite", "height": 16},
            )


if __name__ == "__main__":
    unittest.main()
