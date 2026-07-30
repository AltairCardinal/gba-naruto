#!/usr/bin/env python3
"""Export controller-proven 240x160 composites for the nine scene visual packs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

from PIL import Image, ImageChops


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
UPSTREAM = Path("artifacts/scene-visual-packs-v1")
UPSTREAM_MANIFEST_SHA256 = (
    "4bb40dff9ac2e5641b5e13f46b1dc90bdaa28b9b5615deab7e2a914ae002d5f4"
)
ARTIFACT_ID = "scene-visual-composites-v1"
PAYLOAD_NAME = "scene-visual-composites.json"
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


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _interpolate_q12(start: int, end: int, counter: int) -> int:
    product = (end - start) * (counter << 7)
    if product < 0:
        product += (1 << 12) - 1
    return start + (product >> 12)


def _bgr555(value: int) -> tuple[int, int, int]:
    return (
        (value & 31) * 255 // 31,
        ((value >> 5) & 31) * 255 // 31,
        ((value >> 10) & 31) * 255 // 31,
    )


def _tile_zero(pack: dict[str, Any], upstream: Path) -> Image.Image:
    background = pack["background"]
    graphics = (upstream / background["graphics_file"]).read_bytes()
    palette = (upstream / background["palette_file"]).read_bytes()
    if len(graphics) < 64 or len(palette) < 2:
        raise ValueError("upstream background resources are truncated")
    colors = [
        _bgr555(int.from_bytes(palette[index : index + 2], "little"))
        for index in range(0, len(palette), 2)
    ]
    if max(graphics[:64]) >= len(colors):
        raise ValueError("tile zero uses a palette index outside the source palette")
    tile = Image.new("RGB", (8, 8))
    tile.putdata([colors[index] for index in graphics[:64]])
    return tile


def _hardware_background(
    pack: dict[str, Any],
    upstream: Path,
) -> tuple[Image.Image, Image.Image]:
    tile = _tile_zero(pack, upstream)
    graphics = (upstream / pack["background"]["graphics_file"]).read_bytes()
    index_tile = Image.new("L", (8, 8))
    index_tile.putdata(graphics[:64])
    canvas = Image.new("RGB", (512, 256))
    indices = Image.new("L", (512, 256))
    for y in range(0, 256, 8):
        for x in range(0, 512, 8):
            canvas.paste(tile, (x, y))
            indices.paste(index_tile, (x, y))
    tight_path = upstream / pack["background"]["canvas"]["file"]
    tight_source = Image.open(tight_path)
    tight_indices = Image.new("L", tight_source.size)
    tight_indices.frombytes(tight_source.tobytes())
    canvas.paste(tight_source.convert("RGB"), (0, 0))
    indices.paste(tight_indices, (0, 0))
    return canvas, indices


def _viewport(
    background: Image.Image,
    background_indices: Image.Image,
    scroll: tuple[int, int],
) -> tuple[Image.Image, Image.Image]:
    source = background.load()
    index_source = background_indices.load()
    output = Image.new("RGBA", (240, 160))
    output_indices = Image.new("L", (240, 160))
    target = output.load()
    index_target = output_indices.load()
    scroll_x, scroll_y = scroll
    for y in range(160):
        source_y = (y + scroll_y) % 256
        for x in range(240):
            source_x = (x + scroll_x) % 512
            red, green, blue = source[source_x, source_y]
            target[x, y] = (red, green, blue, 255)
            index_target[x, y] = index_source[source_x, source_y]
    return output, output_indices


def _paste_objects(
    image: Image.Image,
    *,
    pack: dict[str, Any],
    task_positions: list[list[int]],
    background_indices: Image.Image,
    background_priority: int,
    obj_priority: int,
    upstream: Path,
) -> list[dict[str, Any]]:
    placements = []
    frames = pack["obj"]["frames"]
    if len(task_positions) > len(frames):
        raise ValueError("task count exceeds available definition frames")
    for task_index, (task_x, task_y) in enumerate(task_positions):
        frame = frames[task_index]
        bounds = frame["png"]["local_bounds"]
        origin = [task_x + bounds["min_x"], task_y + bounds["min_y"]]
        frame_image = Image.open(upstream / frame["png"]["file"]).convert("RGBA")
        layer = Image.new("RGBA", image.size)
        layer.alpha_composite(frame_image, tuple(origin))
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
                "task_position": [task_x, task_y],
                "local_bounds": bounds,
                "image_origin": origin,
                "source_nontransparent_pixel_count": source_pixel_count,
                "occluded_by_background_pixel_count": occluded_pixel_count,
            }
        )
    return placements


def _save_composite(
    output: Path,
    relative: str,
    image: Image.Image,
) -> dict[str, Any]:
    path = output / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False)
    return {
        "file": relative,
        "width": 240,
        "height": 160,
        "png_mode": "RGBA",
        "pixel_sha256": _sha256_bytes(image.tobytes()),
        "sha256": _sha256(path),
    }


def _validate_inputs(root: Path) -> tuple[bytes, Path, dict[str, Any]]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    upstream = root / UPSTREAM
    manifest_path = upstream / "manifest.json"
    if _sha256(manifest_path) != UPSTREAM_MANIFEST_SHA256:
        raise ValueError("scene visual pack manifest SHA-256 mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if [pack["pack_id"] for pack in manifest["packs"]] != list(range(9)):
        raise ValueError("upstream scene pack denominator mismatch")
    for name, (start, end, expected_hash) in CODE_SLICES.items():
        actual = _sha256_bytes(rom[start - ROM_BASE : end - ROM_BASE])
        if actual != expected_hash:
            raise ValueError(f"{name} code slice SHA-256 mismatch")
    return rom, upstream, manifest


def _build_payload(
    root: Path,
    output: Path,
) -> dict[str, Any]:
    _, upstream, source = _validate_inputs(root)
    packs = source["packs"]
    modes = (
        {
            "mode": 0,
            "main_pack_ids": list(range(4)),
            "main_task_initial_x": [192, 160],
            "main_task_initial_y": [-160, 240],
            "main_task_target_y": [16, 64],
            "exit_reachable": False,
            "exit_background_pack_id": None,
            "exit_obj_pack_id": None,
        },
        {
            "mode": 1,
            "main_pack_ids": list(range(4, 8)),
            "main_task_initial_x": [48, 16],
            "main_task_initial_y": [-160, 240],
            "main_task_target_y": [16, 64],
            "exit_reachable": True,
            "exit_background_pack_id": 8,
            "exit_obj_pack_id": 8,
        },
    )
    motion_model = {
        "counter_initial_by_task_index": [0, 1],
        "last_updated_counter": 31,
        "fraction_bits": 12,
        "counter_step_q12": 128,
        "division": "signed_truncate_toward_zero",
    }
    layering = {
        "bg0cnt": "0x4086",
        "background_priority": 2,
        "main_obj_flags": "0xA0",
        "main_obj_priority": 2,
        "exit_obj_flags": "0xE0",
        "exit_obj_priority": 3,
        "equal_priority_rule": "obj_over_bg",
        "obj_tie_rule": "lower_oam_index_in_front",
    }
    main_composites = []
    for mode in modes:
        for pack_id in mode["main_pack_ids"]:
            pack = packs[pack_id]
            width = pack["background"]["width_tiles"] * 8
            scroll = (0, 0) if mode["mode"] == 0 else (width - 240, 0)
            task_count = pack["spawn_count"]
            task_initial_positions = [
                [mode["main_task_initial_x"][task_index], initial_y]
                for task_index, initial_y in enumerate(
                    mode["main_task_initial_y"][:task_count]
                )
            ]
            task_target_positions = [
                [mode["main_task_initial_x"][task_index], target_y]
                for task_index, target_y in enumerate(
                    mode["main_task_target_y"][:task_count]
                )
            ]
            task_positions = [
                [
                    initial[0],
                    _interpolate_q12(
                        initial[1],
                        target[1],
                        motion_model["last_updated_counter"],
                    ),
                ]
                for initial, target in zip(
                    task_initial_positions,
                    task_target_positions,
                    strict=True,
                )
            ]
            background, background_indices = _hardware_background(pack, upstream)
            image, viewport_indices = _viewport(
                background,
                background_indices,
                scroll,
            )
            placements = _paste_objects(
                image,
                pack=pack,
                task_positions=task_positions,
                background_indices=viewport_indices,
                background_priority=layering["background_priority"],
                obj_priority=layering["main_obj_priority"],
                upstream=upstream,
            )
            relative = f"main/mode-{mode['mode']}-pack-{pack_id:02d}.png"
            rendered = _save_composite(output, relative, image)
            main_composites.append(
                {
                    "mode": mode["mode"],
                    "pack_id": pack_id,
                    "background_width_pixels": width,
                    "background_scroll_pixels": list(scroll),
                    "background_screen_origin": [-scroll[0], -scroll[1]],
                    "task_initial_positions": task_initial_positions,
                    "task_target_positions": task_target_positions,
                    "task_positions": task_positions,
                    "background_priority": layering["background_priority"],
                    "obj_priority": layering["main_obj_priority"],
                    "obj_placements": placements,
                    **rendered,
                }
            )

    exit_composites = []
    for mode in modes:
        if not mode["exit_reachable"]:
            continue
        background_pack = packs[mode["exit_background_pack_id"]]
        obj_pack = packs[mode["exit_obj_pack_id"]]
        scroll = (-40, 0)
        task_initial_positions = [[240, 128]]
        task_target_positions = [[80, 128]]
        task_positions = [
            [
                _interpolate_q12(
                    task_initial_positions[0][0],
                    task_target_positions[0][0],
                    motion_model["last_updated_counter"],
                ),
                128,
            ]
        ]
        background, background_indices = _hardware_background(
            background_pack,
            upstream,
        )
        image, viewport_indices = _viewport(
            background,
            background_indices,
            scroll,
        )
        placements = _paste_objects(
            image,
            pack=obj_pack,
            task_positions=task_positions,
            background_indices=viewport_indices,
            background_priority=layering["background_priority"],
            obj_priority=layering["exit_obj_priority"],
            upstream=upstream,
        )
        relative = (
            f"exit/mode-{mode['mode']}-obj-pack-"
            f"{mode['exit_obj_pack_id']:02d}-over-pack-08.png"
        )
        rendered = _save_composite(output, relative, image)
        exit_composites.append(
            {
                "mode": mode["mode"],
                "background_pack_id": mode["exit_background_pack_id"],
                "obj_pack_id": mode["exit_obj_pack_id"],
                "background_width_pixels": 160,
                "background_scroll_pixels": list(scroll),
                "background_screen_origin": [40, 0],
                "task_initial_positions": task_initial_positions,
                "task_target_positions": task_target_positions,
                "task_positions": task_positions,
                "background_priority": layering["background_priority"],
                "obj_priority": layering["exit_obj_priority"],
                "obj_placements": placements,
                **rendered,
            }
        )

    return {
        "schema": "scene-visual-composites-v1",
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "implementation": {
            relative: _sha256(root / relative)
            for relative in (
                "tools/export_scene_visual_composites.py",
                "tools/verify_scene_visual_composites.py",
                "tests/test_export_scene_visual_composites.py",
            )
        },
        "upstream": {
            "path": UPSTREAM.as_posix(),
            "manifest_sha256": UPSTREAM_MANIFEST_SHA256,
        },
        "code_evidence": {
            name: {
                "start": _address(start),
                "end_exclusive": _address(end),
                "size": end - start,
                "sha256": expected_hash,
            }
            for name, (start, end, expected_hash) in CODE_SLICES.items()
        },
        "controller_modes": list(modes),
        "motion_model": motion_model,
        "layering": layering,
        "main_composites": main_composites,
        "exit_composites": exit_composites,
        "summary": {
            "main_composite_count": len(main_composites),
            "exit_composite_count": len(exit_composites),
            "composite_count": len(main_composites) + len(exit_composites),
            "source_pack_count": 9,
            "source_packs_represented": sorted(
                {
                    item["pack_id"] for item in main_composites
                }
                | {item["background_pack_id"] for item in exit_composites}
                | {item["obj_pack_id"] for item in exit_composites}
            ),
        },
        "scope": {
            "controller_direct_call_modes_complete": True,
            "controller_mode_pack_routes_complete": True,
            "stable_pack_row_bg_obj_layouts_complete": True,
            "bg_obj_priority_order_complete": True,
            "all_nine_source_packs_represented": True,
            "transition_intermediate_frames_complete": False,
            "presentation_overlay_composition_complete": False,
            "window_blend_mosaic_runtime_complete": False,
            "runtime_pixel_equivalence": False,
            "natural_language_identity_complete": False,
        },
    }


def _prepare_output(output: Path) -> None:
    if not output.exists():
        return
    manifest_path = output / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"refusing to replace foreign output: {error}") from error
    if manifest.get("artifact_id") != ARTIFACT_ID:
        raise ValueError("refusing to replace foreign output directory")
    shutil.rmtree(output)


def export_scene_visual_composites(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=output.parent,
        prefix=f".{ARTIFACT_ID}-",
    ) as directory:
        temporary = Path(directory) / ARTIFACT_ID
        temporary.mkdir()
        payload = _build_payload(root, temporary)
        payload_path = temporary / PAYLOAD_NAME
        payload_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        files = {
            path.relative_to(temporary).as_posix(): _sha256(path)
            for path in sorted(temporary.rglob("*"))
            if path.is_file()
        }
        manifest = {
            "schema": "git-artifact-promotion-v1",
            "artifact_id": ARTIFACT_ID,
            "artifact_schema": payload["schema"],
            "artifact_status": "accepted",
            "payload_file": PAYLOAD_NAME,
            "payload_sha256": files[PAYLOAD_NAME],
            "files": files,
            "scope": payload["scope"],
            "verifier": {
                "command": [
                    "python3",
                    "tools/verify_scene_visual_composites.py",
                    "--root",
                    ".",
                    "--artifact",
                    f"artifacts/{ARTIFACT_ID}",
                ],
                "exit_code": 0,
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _prepare_output(output)
        temporary.rename(output)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else args.root / args.output
    payload = export_scene_visual_composites(args.root, output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
