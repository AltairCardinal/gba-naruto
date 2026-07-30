#!/usr/bin/env python3
"""Independently verify scene visual controller composites and provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
UPSTREAM = Path("artifacts/scene-visual-packs-v1")
UPSTREAM_MANIFEST_SHA256 = (
    "4bb40dff9ac2e5641b5e13f46b1dc90bdaa28b9b5615deab7e2a914ae002d5f4"
)
CODE_SLICES = {
    "setup_bg_priority": (
        0x0808BAF4,
        0x0808BAFC,
        "86d9bf38b840eb876dcceee0f40ff838df1f308737cd65330ddf059120d75f9f",
    ),
    "row_loader": (
        0x0808BEE4,
        0x0808BF62,
        "804b19345db90905040aeb7c71e9e5d2464d9ee0fcf821bc6f3fc4ceead08f2a",
    ),
    "main_motion": (
        0x0808C030,
        0x0808C078,
        "ee6f94b5978f5824f37d73b77344cbec1f474c1f6535b8469f90e8e910a95515",
    ),
    "exit_motion": (
        0x0808C07C,
        0x0808C0B4,
        "682d82fc8dcd4cdd78862f4892476dedcc38b192dbe6b44a5eaf5e9e0fd56459",
    ),
    "spawner": (
        0x0808C0B4,
        0x0808C164,
        "3fd57f3a23dd6e1a1c1030f272b0213c596b7c3679069d47c0e7b4b82b5b05d3",
    ),
    "controller": (
        0x0808C214,
        0x0808C4CC,
        "68d80d0b04278938b03702b2d65795d7be94dac3881be06c80884c98912cf8fc",
    ),
    "allocator": (
        0x080626B4,
        0x08062768,
        "bed7ee16174877d036a3999979b69651fabd7ba619d8bbeaef2f41602b6e44eb",
    ),
    "obj_attr2_writer": (
        0x08063108,
        0x08063120,
        "3a8ba305e8ed98f95bda2f6e81361571db10e20f0c2158d99930573e4d24ba83",
    ),
    "interpolation": (
        0x08090AA8,
        0x08090AE6,
        "41eb27f42cf8891465ac7911a4de72eeeb87e7bc6495041b186a83b698d41af2",
    ),
    "caller_mode_toggle": (
        0x0808F866,
        0x0808F872,
        "44c3b8bcbbfbca19b6775555a967860bb740d37b3aa7cee6d11d1056310bbb1f",
    ),
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return value


def _rom_halfword(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    return int.from_bytes(rom[offset : offset + 2], "little")


def _rom_word(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    return int.from_bytes(rom[offset : offset + 4], "little")


def _signed(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def _expect_halfword(rom: bytes, address: int, expected: int) -> None:
    actual = _rom_halfword(rom, address)
    if actual != expected:
        raise ValueError(
            f"controller instruction mismatch at 0x{address:08X}: "
            f"0x{actual:04X} != 0x{expected:04X}"
        )


def _movs_immediate(rom: bytes, address: int, register: int) -> int:
    halfword = _rom_halfword(rom, address)
    if halfword & 0xF800 != 0x2000 or (halfword >> 8) & 7 != register:
        raise ValueError(f"expected MOVS immediate at 0x{address:08X}")
    return halfword & 0xFF


def _cmp_immediate(rom: bytes, address: int, register: int) -> int:
    halfword = _rom_halfword(rom, address)
    if halfword & 0xF800 != 0x2800 or (halfword >> 8) & 7 != register:
        raise ValueError(f"expected CMP immediate at 0x{address:08X}")
    return halfword & 0xFF


def _subs_immediate(rom: bytes, address: int, register: int) -> int:
    halfword = _rom_halfword(rom, address)
    if halfword & 0xF800 != 0x3800 or (halfword >> 8) & 7 != register:
        raise ValueError(f"expected SUBS immediate at 0x{address:08X}")
    return halfword & 0xFF


def _literal_word(rom: bytes, address: int, register: int) -> int:
    halfword = _rom_halfword(rom, address)
    if halfword & 0xF800 != 0x4800 or (halfword >> 8) & 7 != register:
        raise ValueError(f"expected PC-relative LDR at 0x{address:08X}")
    literal = ((address + 4) & ~3) + ((halfword & 0xFF) << 2)
    return _rom_word(rom, literal)


def _interpolate_q12(start: int, end: int, counter: int, shift: int) -> int:
    product = (end - start) * (counter << shift)
    if product < 0:
        product += (1 << 12) - 1
    return start + (product >> 12)


def _derive_controller_model(rom: bytes) -> dict[str, Any]:
    # Main callback: task index selects both the signed initial Y and target Y.
    for address, expected in {
        0x0808C03C: 0x281F,  # cmp counter, 31
        0x0808C040: 0x6B6A,  # ldr task index from +0x34
        0x0808C044: 0x2A00,
        0x0808C04C: 0x2A00,
        0x0808C054: 0x5F2A,  # current task X
        0x0808C06E: 0x80E8,  # write interpolated Y to +6
        0x0808C0EC: 0x46A0,  # loop index -> initial counter
        0x0808C138: 0x6344,  # loop index -> task +0x34
        0x0808C13C: 0x6381,  # initial counter -> task +0x38
        0x0808C466: 0x9200,  # exit Y argument is first stack argument
        0x0808C474: 0x2200,  # exit allocator selector argument
        0x0808C480: 0x6384,  # exit counter starts at zero
        0x0808C08C: 0x2006,
        0x0808C08E: 0x5E23,  # exit callback preserves task Y
        0x0808C0AA: 0x80A0,  # exit callback writes task X
    }.items():
        _expect_halfword(rom, address, expected)

    last_counter = _cmp_immediate(rom, 0x0808C03C, 0)
    if _cmp_immediate(rom, 0x0808C088, 1) != last_counter:
        raise ValueError("main and exit callback counter limits differ")

    main_shift_instruction = _rom_halfword(rom, 0x0808C062)
    exit_shift_instruction = _rom_halfword(rom, 0x0808C098)
    if main_shift_instruction & 0xF800 != 0x0000:
        raise ValueError("unexpected main counter shift instruction")
    if exit_shift_instruction & 0xF800 != 0x0000:
        raise ValueError("unexpected exit counter shift instruction")
    counter_shift = (main_shift_instruction >> 6) & 0x1F
    if ((exit_shift_instruction >> 6) & 0x1F) != counter_shift:
        raise ValueError("main and exit callback counter shifts differ")

    for address, expected in {
        0x08090AC0: 0x4909,
        0x08090AC2: 0x1840,
        0x08090AC4: 0x1300,
        0x08090AD4: 0x4904,
        0x08090AD6: 0x1840,
        0x08090AD8: 0x1300,
    }.items():
        _expect_halfword(rom, address, expected)
    if _literal_word(rom, 0x08090AC0, 1) != 0xFFF:
        raise ValueError("interpolator negative-rounding bias mismatch")
    fraction_bits = (_rom_halfword(rom, 0x08090AC4) >> 6) & 0x1F

    first_y = _signed(_literal_word(rom, 0x0808C048, 1) & 0xFFFF, 16)
    second_y = _movs_immediate(rom, 0x0808C042, 1)
    first_target_y = _movs_immediate(rom, 0x0808C050, 3)
    second_target_y = _movs_immediate(rom, 0x0808C04A, 3)
    mode_one_x = _movs_immediate(rom, 0x0808C0CA, 0)
    mode_zero_x = _movs_immediate(rom, 0x0808C0D2, 0)
    second_x_delta = _subs_immediate(rom, 0x0808C140, 0)
    if _signed(_literal_word(rom, 0x0808C0FE, 2) & 0xFFFF, 16) != first_y:
        raise ValueError("spawner and callback first-task Y differ")
    if _movs_immediate(rom, 0x0808C0F8, 2) != second_y:
        raise ValueError("spawner and callback second-task Y differ")

    exit_initial = [
        _movs_immediate(rom, 0x0808C476, 3),
        _movs_immediate(rom, 0x0808C464, 2),
    ]
    exit_target = [
        _movs_immediate(rom, 0x0808C0A0, 2),
        exit_initial[1],
    ]
    if _movs_immediate(rom, 0x0808C09C, 0) != exit_initial[0]:
        raise ValueError("exit allocator and callback initial X differ")

    mode_one_initial_scroll = _signed(
        _literal_word(rom, 0x0808C374, 5),
        32,
    ) >> 8
    mode_zero_step = _signed(_literal_word(rom, 0x0808C392, 1), 32) >> 8
    _expect_halfword(rom, 0x0808C368, 0x02C5)  # width_tiles << 11
    _expect_halfword(rom, 0x0808C38A, 0x0044)  # width_tiles << 1
    if mode_zero_step != -4:
        raise ValueError("main mode-zero scroll step mismatch")
    exit_scroll = [
        _signed(_literal_word(rom, 0x0808C414, 0), 32) >> 8,
        0,
    ]
    if _signed(_literal_word(rom, 0x0808C418, 0), 32) >> 8 != -240:
        raise ValueError("exit transition initial vertical scroll mismatch")

    return {
        "last_updated_counter": last_counter,
        "counter_shift": counter_shift,
        "fraction_bits": fraction_bits,
        "main_initial_y": [first_y, second_y],
        "main_target_y": [first_target_y, second_target_y],
        "main_initial_x_by_mode": {
            0: [mode_zero_x, mode_zero_x - second_x_delta],
            1: [mode_one_x, mode_one_x - second_x_delta],
        },
        "mode_one_initial_scroll": mode_one_initial_scroll,
        "exit_scroll": exit_scroll,
        "exit_initial": exit_initial,
        "exit_target": exit_target,
    }


def _derive_layering_model(rom: bytes) -> dict[str, Any]:
    if _literal_word(rom, 0x0808BAF4, 1) != 0x04000008:
        raise ValueError("scene setup does not target BG0CNT")
    bg0cnt = _literal_word(rom, 0x0808BAF6, 4) & 0xFFFF
    for address, expected in {
        0x0808BAFA: 0x8008,  # strh BG0CNT value
        0x0808C11E: 0x9203,  # main flags -> allocator stack argument
        0x0808C46E: 0x9203,  # exit flags -> allocator stack argument
        0x080626CA: 0x9D0D,  # allocator reads that flags argument
        0x0806272A: 0x4305,  # active bit is added without losing priority
        0x0806272C: 0x6015,  # flags stored in task word
        0x08063116: 0x20C0,
        0x08063118: 0x4002,
        0x0806311A: 0x0110,
        0x0806311C: 0x4301,
        0x0806311E: 0x80A9,  # attr2 priority write
        0x080626E8: 0x237F,  # allocator starts at OAM/task slot 127
    }.items():
        _expect_halfword(rom, address, expected)
    main_flags = _movs_immediate(rom, 0x0808C11C, 2)
    exit_flags = _movs_immediate(rom, 0x0808C46C, 2)
    return {
        "bg0cnt": f"0x{bg0cnt:04X}",
        "background_priority": bg0cnt & 3,
        "main_obj_flags": f"0x{main_flags:02X}",
        "main_obj_priority": (main_flags & 0xC0) >> 6,
        "exit_obj_flags": f"0x{exit_flags:02X}",
        "exit_obj_priority": (exit_flags & 0xC0) >> 6,
        "equal_priority_rule": "obj_over_bg",
        "obj_tie_rule": "lower_oam_index_in_front",
    }


def _bgr555(value: int) -> tuple[int, int, int]:
    return (
        (value & 31) * 255 // 31,
        ((value >> 5) & 31) * 255 // 31,
        ((value >> 10) & 31) * 255 // 31,
    )


def _background(
    pack: dict[str, Any],
    upstream: Path,
) -> tuple[Image.Image, Image.Image]:
    spec = pack["background"]
    graphics_path = upstream / spec["graphics_file"]
    palette_path = upstream / spec["palette_file"]
    tight_path = upstream / spec["canvas"]["file"]
    if _sha256(graphics_path) != spec["graphics_sha256"]:
        raise ValueError("upstream background graphics hash mismatch")
    if _sha256(palette_path) != spec["palette_sha256"]:
        raise ValueError("upstream background palette hash mismatch")
    if _sha256(tight_path) != spec["canvas"]["sha256"]:
        raise ValueError("upstream background PNG hash mismatch")
    graphics = graphics_path.read_bytes()
    palette = palette_path.read_bytes()
    colors = [
        _bgr555(int.from_bytes(palette[index : index + 2], "little"))
        for index in range(0, len(palette), 2)
    ]
    if len(graphics) < 64 or max(graphics[:64]) >= len(colors):
        raise ValueError("invalid upstream tile zero")
    tile = Image.new("RGB", (8, 8))
    tile.putdata([colors[index] for index in graphics[:64]])
    index_tile = Image.new("L", (8, 8))
    index_tile.putdata(graphics[:64])
    canvas = Image.new("RGB", (512, 256))
    indices = Image.new("L", (512, 256))
    for y in range(0, 256, 8):
        for x in range(0, 512, 8):
            canvas.paste(tile, (x, y))
            indices.paste(index_tile, (x, y))
    tight_source = Image.open(tight_path)
    if tight_source.size != (
        spec["width_tiles"] * 8,
        spec["height_tiles"] * 8,
    ):
        raise ValueError("upstream background PNG dimensions mismatch")
    tight_indices = Image.new("L", tight_source.size)
    tight_indices.frombytes(tight_source.tobytes())
    canvas.paste(tight_source.convert("RGB"), (0, 0))
    indices.paste(tight_indices, (0, 0))
    return canvas, indices


def _viewport(
    canvas: Image.Image,
    indices: Image.Image,
    scroll: tuple[int, int],
) -> tuple[Image.Image, Image.Image]:
    source = canvas.load()
    index_source = indices.load()
    result = Image.new("RGBA", (240, 160))
    result_indices = Image.new("L", (240, 160))
    target = result.load()
    index_target = result_indices.load()
    for y in range(160):
        for x in range(240):
            source_x = (x + scroll[0]) % 512
            source_y = (y + scroll[1]) % 256
            red, green, blue = source[source_x, source_y]
            target[x, y] = (red, green, blue, 255)
            index_target[x, y] = index_source[source_x, source_y]
    return result, result_indices


def _add_objects(
    image: Image.Image,
    pack: dict[str, Any],
    positions: list[list[int]],
    background_indices: Image.Image,
    background_priority: int,
    obj_priority: int,
    upstream: Path,
) -> list[dict[str, Any]]:
    placements = []
    frames = pack["obj"]["frames"]
    for task_index, position in enumerate(positions):
        frame = frames[task_index]
        png = upstream / frame["png"]["file"]
        if _sha256(png) != frame["png"]["sha256"]:
            raise ValueError("upstream OBJ frame hash mismatch")
        bounds = frame["png"]["local_bounds"]
        origin = [
            position[0] + bounds["min_x"],
            position[1] + bounds["min_y"],
        ]
        layer = Image.new("RGBA", image.size)
        layer.alpha_composite(Image.open(png).convert("RGBA"), tuple(origin))
        source_alpha = layer.getchannel("A")
        source_pixel_count = sum(value != 0 for value in source_alpha.tobytes())
        occluded_pixel_count = 0
        if obj_priority > background_priority:
            bg_transparent = background_indices.point(
                lambda value: 255 if value == 0 else 0
            )
            visible_alpha = ImageChops.multiply(source_alpha, bg_transparent)
            visible_pixel_count = sum(
                value != 0 for value in visible_alpha.tobytes()
            )
            occluded_pixel_count = source_pixel_count - visible_pixel_count
            layer.putalpha(visible_alpha)
        image.alpha_composite(layer)
        placements.append(
            {
                "task_index": task_index,
                "frame_id": frame["frame_id"],
                "palette_bank": frame["palette_bank"],
                "task_position": position,
                "local_bounds": bounds,
                "image_origin": origin,
                "source_nontransparent_pixel_count": source_pixel_count,
                "occluded_by_background_pixel_count": occluded_pixel_count,
            }
        )
    return placements


def _expected_records(
    rom: bytes,
    source: dict[str, Any],
    upstream: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    packs = source["packs"]
    controller = _derive_controller_model(rom)
    layering = _derive_layering_model(rom)
    motion_model = {
        "counter_initial_by_task_index": [0, 1],
        "last_updated_counter": controller["last_updated_counter"],
        "fraction_bits": controller["fraction_bits"],
        "counter_step_q12": 1 << controller["counter_shift"],
        "division": "signed_truncate_toward_zero",
    }
    main = []
    modes = []
    for mode, pack_ids, exit_obj_pack_id in (
        (0, range(4), 4),
        (1, range(8), 8),
    ):
        xs = controller["main_initial_x_by_mode"][mode]
        mode_spec = {
            "mode": mode,
            "main_pack_ids": list(pack_ids),
            "main_task_initial_x": xs,
            "main_task_initial_y": controller["main_initial_y"],
            "main_task_target_y": controller["main_target_y"],
            "exit_background_pack_id": 8,
            "exit_obj_pack_id": exit_obj_pack_id,
        }
        modes.append(mode_spec)
        for pack_id in pack_ids:
            pack = packs[pack_id]
            width = pack["background"]["width_tiles"] * 8
            scroll = (
                (0, 0)
                if mode == 0
                else (
                    controller["mode_one_initial_scroll"]
                    + pack["background"]["width_tiles"] * 2 * 4,
                    0,
                )
            )
            count = pack["spawn_count"]
            initial_positions = [
                [xs[index], controller["main_initial_y"][index]]
                for index in range(count)
            ]
            target_positions = [
                [xs[index], controller["main_target_y"][index]]
                for index in range(count)
            ]
            positions = [
                [
                    initial[0],
                    _interpolate_q12(
                        initial[1],
                        target[1],
                        controller["last_updated_counter"],
                        controller["counter_shift"],
                    ),
                ]
                for initial, target in zip(
                    initial_positions,
                    target_positions,
                    strict=True,
                )
            ]
            background, background_indices = _background(pack, upstream)
            image, viewport_indices = _viewport(
                background,
                background_indices,
                scroll,
            )
            placements = _add_objects(
                image,
                pack,
                positions,
                viewport_indices,
                layering["background_priority"],
                layering["main_obj_priority"],
                upstream,
            )
            main.append(
                {
                    "mode": mode,
                    "pack_id": pack_id,
                    "background_width_pixels": width,
                    "background_scroll_pixels": list(scroll),
                    "background_screen_origin": [-scroll[0], -scroll[1]],
                    "task_initial_positions": initial_positions,
                    "task_target_positions": target_positions,
                    "task_positions": positions,
                    "background_priority": layering["background_priority"],
                    "obj_priority": layering["main_obj_priority"],
                    "obj_placements": placements,
                    "file": f"main/mode-{mode}-pack-{pack_id:02d}.png",
                    "width": 240,
                    "height": 160,
                    "png_mode": "RGBA",
                    "pixel_sha256": _sha256_bytes(image.tobytes()),
                    "_image": image,
                }
            )
    exits = []
    for mode, obj_pack_id in ((0, 4), (1, 8)):
        scroll = controller["exit_scroll"]
        background, background_indices = _background(packs[8], upstream)
        image, viewport_indices = _viewport(
            background,
            background_indices,
            tuple(scroll),
        )
        initial_positions = [controller["exit_initial"]]
        target_positions = [controller["exit_target"]]
        positions = [
            [
                _interpolate_q12(
                    initial_positions[0][0],
                    target_positions[0][0],
                    controller["last_updated_counter"],
                    controller["counter_shift"],
                ),
                initial_positions[0][1],
            ]
        ]
        placements = _add_objects(
            image,
            packs[obj_pack_id],
            positions,
            viewport_indices,
            layering["background_priority"],
            layering["exit_obj_priority"],
            upstream,
        )
        exits.append(
            {
                "mode": mode,
                "background_pack_id": 8,
                "obj_pack_id": obj_pack_id,
                "background_width_pixels": 160,
                "background_scroll_pixels": scroll,
                "background_screen_origin": [-scroll[0], -scroll[1]],
                "task_initial_positions": initial_positions,
                "task_target_positions": target_positions,
                "task_positions": positions,
                "background_priority": layering["background_priority"],
                "obj_priority": layering["exit_obj_priority"],
                "obj_placements": placements,
                "file": (
                    f"exit/mode-{mode}-obj-pack-{obj_pack_id:02d}"
                    "-over-pack-08.png"
                ),
                "width": 240,
                "height": 160,
                "png_mode": "RGBA",
                "pixel_sha256": _sha256_bytes(image.tobytes()),
                "_image": image,
            }
        )
    return main, exits, modes, motion_model, layering


def _compare_record(
    actual: dict[str, Any],
    expected: dict[str, Any],
    artifact: Path,
    label: str,
    errors: list[str],
) -> None:
    for field, expected_value in expected.items():
        if field == "_image":
            continue
        if actual.get(field) != expected_value:
            description = (
                "task positions"
                if field == "task_positions"
                else field.replace("_", " ")
            )
            errors.append(f"{label}: {description} mismatch")
    path = artifact / expected["file"]
    try:
        image = Image.open(path).convert("RGBA")
        if image.size != (240, 160):
            errors.append(f"{label}: PNG dimensions mismatch")
        if image.tobytes() != expected["_image"].tobytes():
            errors.append(f"{label}: PNG pixels mismatch")
        if actual.get("sha256") != _sha256(path):
            errors.append(f"{label}: PNG file hash mismatch")
    except OSError as error:
        errors.append(f"{label}: cannot read PNG: {error}")


def verify_scene_visual_composites(
    root: Path,
    artifact: Path,
) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.resolve()
    errors: list[str] = []
    try:
        manifest = _json(artifact / "manifest.json")
        payload = _json(artifact / "scene-visual-composites.json")
        if manifest.get("schema") != "git-artifact-promotion-v1":
            errors.append("promotion manifest schema mismatch")
        if manifest.get("artifact_status") != "accepted":
            errors.append("artifact is not accepted")
        files = manifest.get("files")
        actual_files = {
            path.relative_to(artifact).as_posix(): path
            for path in artifact.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        if not isinstance(files, dict) or set(files) != set(actual_files):
            errors.append("artifact file inventory mismatch")
            files = {}
        for relative, expected_hash in files.items():
            if relative in actual_files and _sha256(actual_files[relative]) != expected_hash:
                errors.append(f"artifact hash mismatch: {relative}")
        payload_hash = _sha256(artifact / "scene-visual-composites.json")
        if manifest.get("payload_sha256") != payload_hash:
            errors.append("payload hash mismatch")

        rom = (root / "rom/base.gba").read_bytes()
        if _sha256_bytes(rom) != ROM_SHA256:
            errors.append("base ROM SHA-256 mismatch")
        for name, (start, end, expected_hash) in CODE_SLICES.items():
            if _sha256_bytes(rom[start - ROM_BASE : end - ROM_BASE]) != expected_hash:
                errors.append(f"{name} code slice mismatch")

        upstream = root / UPSTREAM
        source_manifest_path = upstream / "manifest.json"
        if _sha256(source_manifest_path) != UPSTREAM_MANIFEST_SHA256:
            errors.append("upstream manifest SHA-256 mismatch")
        source = _json(source_manifest_path)
        (
            expected_main,
            expected_exit,
            expected_modes,
            expected_motion,
            expected_layering,
        ) = _expected_records(rom, source, upstream)
        expected_implementation = {
            relative: _sha256(root / relative)
            for relative in (
                "tools/export_scene_visual_composites.py",
                "tools/verify_scene_visual_composites.py",
                "tests/test_export_scene_visual_composites.py",
            )
        }
        if payload.get("implementation") != expected_implementation:
            errors.append("implementation hashes mismatch")

        if payload.get("controller_modes") != expected_modes:
            errors.append("controller mode declarations mismatch")
        if payload.get("motion_model") != expected_motion:
            errors.append("motion model mismatch")
        if payload.get("layering") != expected_layering:
            errors.append("layering model mismatch")
        actual_main = payload.get("main_composites")
        actual_exit = payload.get("exit_composites")
        if not isinstance(actual_main, list) or len(actual_main) != 12:
            errors.append("main composite denominator mismatch")
            actual_main = []
        if not isinstance(actual_exit, list) or len(actual_exit) != 2:
            errors.append("exit composite denominator mismatch")
            actual_exit = []
        for index, expected in enumerate(expected_main):
            if index < len(actual_main):
                _compare_record(
                    actual_main[index],
                    expected,
                    artifact,
                    f"main composite {index}",
                    errors,
                )
        for index, expected in enumerate(expected_exit):
            if index < len(actual_exit):
                _compare_record(
                    actual_exit[index],
                    expected,
                    artifact,
                    f"exit composite {index}",
                    errors,
                )
        if payload.get("summary") != {
            "main_composite_count": 12,
            "exit_composite_count": 2,
            "composite_count": 14,
            "source_pack_count": 9,
            "source_packs_represented": list(range(9)),
        }:
            errors.append("summary mismatch")
        expected_scope = {
            "controller_direct_call_modes_complete": True,
            "stable_pack_row_bg_obj_layouts_complete": True,
            "bg_obj_priority_order_complete": True,
            "all_nine_source_packs_represented": True,
            "transition_intermediate_frames_complete": False,
            "presentation_overlay_composition_complete": False,
            "window_blend_mosaic_runtime_complete": False,
            "runtime_pixel_equivalence": False,
            "natural_language_identity_complete": False,
        }
        if payload.get("scope") != expected_scope:
            errors.append("scope mismatch")
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": "scene-visual-composites-verification-v1",
        "verified": not errors,
        "composite_count": 14 if not errors else 0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/scene-visual-composites-v1"),
    )
    args = parser.parse_args()
    artifact = args.artifact if args.artifact.is_absolute() else args.root / args.artifact
    report = verify_scene_visual_composites(args.root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
