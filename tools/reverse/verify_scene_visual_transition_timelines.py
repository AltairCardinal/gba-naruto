#!/usr/bin/env python3
"""Independently verify scene controller phases and task motion witnesses."""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
import zipfile

from PIL import Image, ImageChops


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.verify_scene_visual_composites import (
    CODE_SLICES,
    ROM_SHA256,
    UPSTREAM,
    UPSTREAM_MANIFEST_SHA256,
    _background,
    _derive_controller_model,
    _derive_layering_model,
    _interpolate_q12,
    _viewport,
    verify_scene_visual_composites,
)


ROM_BASE = 0x08000000
ARTIFACT_ID = "scene-visual-transition-timelines-v1"
PAYLOAD_NAME = "scene-visual-transition-timelines.json"
ARCHIVE_NAME = "frames.zip"
COMPOSITE_PATH = Path("artifacts/scene-visual-composites-v1")
COMPOSITE_MANIFEST_SHA256 = (
    "bfa901135f416e48ee5e646d88c1b6669ab8c36d4817b24f2e3664cf00be0da2"
)
IMPLEMENTATION_PATHS = (
    "tools/export_scene_visual_transition_timelines.py",
    "tools/verify_scene_visual_transition_timelines.py",
    "tests/test_export_scene_visual_transition_timelines.py",
    "tools/export_scene_visual_composites.py",
    "tools/verify_scene_visual_composites.py",
)
JUMP_TABLE_BASE = 0x0808C2FC
JUMP_TABLE_HANDLERS = (
    0x0808C350,
    0x0808C38E,
    0x0808C3CC,
    0x0808C3DE,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C404,
    0x0808C438,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C49C,
    0x0808C494,
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _u16(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    return int.from_bytes(rom[offset : offset + 2], "little")


def _u32(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    return int.from_bytes(rom[offset : offset + 4], "little")


def _expect_halfwords(rom: bytes, expected: dict[int, int]) -> None:
    for address, halfword in expected.items():
        if _u16(rom, address) != halfword:
            raise ValueError(f"controller halfword mismatch at 0x{address:08X}")


def _decode_thumb_bl(rom: bytes, address: int) -> int | None:
    first = _u16(rom, address)
    second = _u16(rom, address + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    high = first & 0x07FF
    if high & 0x0400:
        high -= 0x0800
    displacement = (high << 12) | ((second & 0x07FF) << 1)
    return (address + 4 + displacement) & 0xFFFFFFFF


def _derive_phase_model(rom: bytes) -> dict[str, Any]:
    if _u32(rom, 0x0808C2F8) != JUMP_TABLE_BASE:
        raise ValueError("controller jump table pointer mismatch")
    handlers = tuple(
        _u32(rom, JUMP_TABLE_BASE + state * 4)
        for state in range(21)
    )
    if handlers != JUMP_TABLE_HANDLERS:
        raise ValueError("controller jump table handlers mismatch")
    _expect_halfwords(
        rom,
        {
            0x0808C38A: 0x0044,  # r4 = width_tiles << 1
            0x0808C38C: 0x2701,  # state = 1
            0x0808C224: 0x4680,
            0x0808C226: 0x4240,
            0x0808C22A: 0x4308,
            0x0808C22C: 0x17C6,
            0x0808C22E: 0x2004,
            0x0808C230: 0x4006,  # initial pack = mode ? 4 : 0
            0x0808C232: 0x2008,
            0x0808C234: 0x2900,
            0x0808C238: 0x2004,  # exclusive end = mode ? 8 : 4
            0x0808C23A: 0x4682,
            0x0808C3B4: 0x6005,  # store horizontal scroll
            0x0808C3B6: 0x3C01,  # remaining--
            0x0808C3B8: 0x2C00,
            0x0808C3C4: 0x2702,  # state = 2 after spawn
            0x0808C3CC: 0x3401,  # hold counter++
            0x0808C3CE: 0x2C3F,  # wait through 63
            0x0808C3D2: 0x2703,
            0x0808C3E2: 0x2802,  # external global == 2
            0x0808C3EA: 0x1C70,
            0x0808C3F2: 0x4556,
            0x0808C3F6: 0x270A,
            0x0808C3F8: 0x4640,
            0x0808C3FA: 0x2800,
            0x0808C3FE: 0xE04C,  # zero mode exits before state 10
            0x0808C420: 0x270B,  # state = 11
            0x0808C442: 0x6048,  # store vertical scroll
            0x0808C444: 0x3504,  # logical pixel counter += 4
            0x0808C446: 0x2D00,
            0x0808C44A: 0x2714,  # state = 20 after spawn
            0x0808C480: 0x6384,  # state20 counter starts at 0
            0x0808C494: 0x3401,
            0x0808C496: 0x2CD3,  # wait through 211
            0x0808C49A: 0x27FF,
        },
    )
    if _decode_thumb_bl(rom, 0x0808C3C0) != 0x0808C0B4:
        raise ValueError("main spawner call mismatch")
    stable = _derive_controller_model(rom)
    if stable["mode_one_initial_scroll"] != -240:
        raise ValueError("mode-one initial scroll mismatch")
    if stable["exit_scroll"] != [-40, 0]:
        raise ValueError("exit stable scroll mismatch")
    return {
        "jump_table_base": f"0x{JUMP_TABLE_BASE:08X}",
        "jump_table_handlers": [
            {"state": state, "handler": f"0x{handler:08X}"}
            for state, handler in enumerate(handlers)
        ],
        "main_background": {
            "state_0_handler": "0x0808C350",
            "state_1_handler": "0x0808C38E",
            "state_0_falls_through_to_state_1": True,
            "callback_count": "background_width_pixels / 4",
            "spawner_call": "0x0808C3C0 -> 0x0808C0B4",
            "spawner_timing": "after the final scroll write and countdown decrement",
        },
        "mode_routes": [
            {
                "mode": 0,
                "main_pack_ids": list(range(4)),
                "exit_reachable": False,
            },
            {
                "mode": 1,
                "main_pack_ids": list(range(4, 8)),
                "exit_reachable": True,
                "exit_background_pack_id": 8,
                "exit_obj_pack_id": 8,
            },
        ],
        "state_2_hold": {
            "handler": "0x0808C3CC",
            "initial_counter": 0,
            "callback_count": 64,
            "transition_counter": 64,
            "next_state": 3,
        },
        "state_3_wait": {
            "handler": "0x0808C3DE",
            "condition": "external_global_equals_2",
            "finite_callback_count": None,
        },
        "exit_background": {
            "state_10_handler": "0x0808C404",
            "state_11_handler": "0x0808C438",
            "state_10_initial_scroll": [-40, -240],
            "state_11_callback_count": 60,
            "spawner_timing": "after state_11 reaches vertical scroll zero",
        },
        "state_20_hold": {
            "handler": "0x0808C494",
            "initial_counter": 0,
            "callback_count": 212,
            "exit_counter": 212,
            "next_state": 255,
        },
    }


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _single_object(
    image: Image.Image,
    *,
    pack: dict[str, Any],
    task_index: int,
    position: list[int],
    background_indices: Image.Image,
    background_priority: int,
    obj_priority: int,
    upstream: Path,
) -> dict[str, Any]:
    frame = pack["obj"]["frames"][task_index]
    png_path = upstream / frame["png"]["file"]
    if _sha256(png_path) != frame["png"]["sha256"]:
        raise ValueError("upstream task PNG hash mismatch")
    bounds = frame["png"]["local_bounds"]
    origin = [
        position[0] + bounds["min_x"],
        position[1] + bounds["min_y"],
    ]
    layer = Image.new("RGBA", image.size)
    layer.alpha_composite(Image.open(png_path).convert("RGBA"), tuple(origin))
    source_alpha = layer.getchannel("A")
    source_count = sum(value != 0 for value in source_alpha.tobytes())
    occluded_count = 0
    if obj_priority > background_priority:
        bg_transparent = background_indices.point(
            lambda value: 255 if value == 0 else 0
        )
        visible_alpha = ImageChops.multiply(source_alpha, bg_transparent)
        visible_count = sum(value != 0 for value in visible_alpha.tobytes())
        occluded_count = source_count - visible_count
        layer.putalpha(visible_alpha)
    image.alpha_composite(layer)
    return {
        "task_index": task_index,
        "frame_id": frame["frame_id"],
        "palette_bank": frame["palette_bank"],
        "task_position": position,
        "local_bounds": bounds,
        "image_origin": origin,
        "source_nontransparent_pixel_count": source_count,
        "occluded_by_background_pixel_count": occluded_count,
    }


def _verify_archive_record(
    bundle: zipfile.ZipFile,
    *,
    frame_file: str,
    image: Image.Image,
    fields: dict[str, Any],
    errors: list[str],
    expected_names: list[str],
) -> dict[str, Any]:
    expected_names.append(frame_file)
    png = _png_bytes(image)
    try:
        info = bundle.getinfo(frame_file)
        actual = bundle.read(frame_file)
        if info.date_time != (1980, 1, 1, 0, 0, 0):
            errors.append(f"archive timestamp mismatch: {frame_file}")
        if info.compress_type != zipfile.ZIP_STORED:
            errors.append(f"archive compression mismatch: {frame_file}")
        if info.create_system != 3:
            errors.append(f"archive create_system mismatch: {frame_file}")
        if info.external_attr != 0o100644 << 16:
            errors.append(f"archive external_attr mismatch: {frame_file}")
        if info.internal_attr != 0:
            errors.append(f"archive internal_attr mismatch: {frame_file}")
        if info.extra:
            errors.append(f"archive extra metadata mismatch: {frame_file}")
        if info.comment:
            errors.append(f"archive entry comment mismatch: {frame_file}")
        if actual != png:
            errors.append(f"frame PNG mismatch: {frame_file}")
    except KeyError:
        errors.append(f"missing frame: {frame_file}")
    return {
        **fields,
        "frame_file": frame_file,
        "pixel_sha256": _sha256_bytes(image.tobytes()),
        "png_sha256": _sha256_bytes(png),
    }


def _spawned_main_tasks(
    controller: dict[str, Any],
    mode: int,
    pack: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "task_index": index,
            "counter": index,
            "position": [
                controller["main_initial_x_by_mode"][mode][index],
                controller["main_initial_y"][index],
            ],
        }
        for index in range(pack["spawn_count"])
    ]


def _expected_background_tracks(
    bundle: zipfile.ZipFile,
    *,
    controller: dict[str, Any],
    packs: list[dict[str, Any]],
    backgrounds: dict[int, tuple[Image.Image, Image.Image]],
    errors: list[str],
    expected_names: list[str],
) -> list[dict[str, Any]]:
    tracks = []
    for mode, pack_ids in ((0, range(4)), (1, range(4, 8))):
        for pack_id in pack_ids:
            pack = packs[pack_id]
            width = pack["background"]["width_tiles"] * 8
            callback_count = pack["background"]["width_tiles"] * 2
            initial_scroll = width if mode == 0 else controller[
                "mode_one_initial_scroll"
            ]
            step = -4 if mode == 0 else 4
            track_id = f"controller/main/mode-{mode}-pack-{pack_id:02d}"
            background, indices = backgrounds[pack_id]
            states = []
            for write_index in range(callback_count + 1):
                scroll = [initial_scroll + write_index * step, 0]
                image, _ = _viewport(background, indices, tuple(scroll))
                final = write_index == callback_count
                states.append(
                    _verify_archive_record(
                        bundle,
                        frame_file=(
                            f"{track_id}/write-{write_index:03d}.png"
                        ),
                        image=image,
                        fields={
                            "write_index": write_index,
                            "controller_dispatch_number": max(1, write_index),
                            "write_order_in_dispatch": (
                                1 if write_index == 1 else 0
                            ),
                            "handler": (
                                "state_0_initial_scroll_write"
                                if write_index == 0
                                else (
                                    "state_0_fallthrough_state_1"
                                    if write_index == 1
                                    else "state_1"
                                )
                            ),
                            "background_scroll": scroll,
                            "background_screen_origin": [-scroll[0], 0],
                            "remaining_scroll_callbacks": (
                                callback_count - write_index
                            ),
                            "spawner_called": final,
                            "spawned_tasks": (
                                _spawned_main_tasks(controller, mode, pack)
                                if final
                                else []
                            ),
                            "obj_placements": [],
                            "render_scope": "controller_background_only",
                        },
                        errors=errors,
                        expected_names=expected_names,
                    )
                )
            tracks.append(
                {
                    "track_id": track_id,
                    "kind": "main_background",
                    "mode": mode,
                    "pack_id": pack_id,
                    "background_width_pixels": width,
                    "controller_dispatch_count": callback_count,
                    "state_count": len(states),
                    "states": states,
                }
            )

    for mode, obj_pack_id in ((1, 8),):
        track_id = (
            f"controller/exit/mode-{mode}-obj-pack-"
            f"{obj_pack_id:02d}-over-pack-08"
        )
        background, indices = backgrounds[8]
        states = []
        for callback_index in range(61):
            scroll = [-40, -240 + callback_index * 4]
            image, _ = _viewport(background, indices, tuple(scroll))
            final = callback_index == 60
            states.append(
                _verify_archive_record(
                    bundle,
                    frame_file=f"{track_id}/callback-{callback_index:03d}.png",
                    image=image,
                    fields={
                        "callback_index": callback_index,
                        "controller_callback_number": callback_index + 1,
                        "handler": "state_10" if callback_index == 0 else "state_11",
                        "background_scroll": scroll,
                        "background_screen_origin": [-scroll[0], -scroll[1]],
                        "remaining_scroll_callbacks": 60 - callback_index,
                        "spawner_called": final,
                        "spawned_tasks": (
                            [
                                {
                                    "task_index": 0,
                                    "counter": 0,
                                    "position": controller["exit_initial"],
                                }
                            ]
                            if final
                            else []
                        ),
                        "obj_placements": [],
                        "render_scope": "controller_background_only",
                    },
                    errors=errors,
                    expected_names=expected_names,
                )
            )
        tracks.append(
            {
                "track_id": track_id,
                "kind": "exit_background",
                "mode": mode,
                "background_pack_id": 8,
                "obj_pack_id": obj_pack_id,
                "state_count": len(states),
                "states": states,
            }
        )
    return tracks


def _expected_task_track(
    bundle: zipfile.ZipFile,
    *,
    controller: dict[str, Any],
    layering: dict[str, Any],
    track_id: str,
    kind: str,
    mode: int,
    pack: dict[str, Any],
    pack_id: int,
    task_index: int,
    initial_counter: int,
    initial: list[int],
    target: list[int],
    background: Image.Image,
    background_indices: Image.Image,
    scroll: list[int],
    upstream: Path,
    errors: list[str],
    expected_names: list[str],
) -> dict[str, Any]:
    states = []
    position = list(initial)
    for state_index, counter in enumerate(range(initial_counter, 33)):
        callback_executed = state_index != 0
        position_written = callback_executed and counter <= controller[
            "last_updated_counter"
        ]
        if position_written:
            axis = 0 if kind == "exit_task" else 1
            position[axis] = _interpolate_q12(
                initial[axis],
                target[axis],
                counter,
                controller["counter_shift"],
            )
        image, viewport_indices = _viewport(
            background,
            background_indices,
            tuple(scroll),
        )
        placement = _single_object(
            image,
            pack=pack,
            task_index=task_index,
            position=list(position),
            background_indices=viewport_indices,
            background_priority=layering["background_priority"],
            obj_priority=(
                layering["exit_obj_priority"]
                if kind == "exit_task"
                else layering["main_obj_priority"]
            ),
            upstream=upstream,
        )
        states.append(
            _verify_archive_record(
                bundle,
                frame_file=f"{track_id}/callback-{state_index:03d}.png",
                image=image,
                fields={
                    "state_index": state_index,
                    "counter": counter,
                    "callback_executed": callback_executed,
                    "position_written": position_written,
                    "first_stable_callback": counter == 32,
                    "position": list(position),
                    "obj_placement": placement,
                    "background_scroll_context": scroll,
                    "render_scope": (
                        "single_task_over_stable_background_spatial_witness"
                    ),
                },
                errors=errors,
                expected_names=expected_names,
            )
        )
    return {
        "track_id": track_id,
        "kind": kind,
        "mode": mode,
        "pack_id": pack_id,
        "task_index": task_index,
        "initial_counter": initial_counter,
        "initial_position": initial,
        "target_parameter": target,
        "last_position_write_counter": 31,
        "first_stable_callback_counter": 32,
        "state_count": len(states),
        "states": states,
    }


def _expected_task_tracks(
    bundle: zipfile.ZipFile,
    *,
    controller: dict[str, Any],
    layering: dict[str, Any],
    packs: list[dict[str, Any]],
    backgrounds: dict[int, tuple[Image.Image, Image.Image]],
    upstream: Path,
    errors: list[str],
    expected_names: list[str],
) -> list[dict[str, Any]]:
    tracks = []
    for mode, pack_ids in ((0, range(4)), (1, range(4, 8))):
        xs = controller["main_initial_x_by_mode"][mode]
        for pack_id in pack_ids:
            pack = packs[pack_id]
            width = pack["background"]["width_tiles"] * 8
            scroll = (
                [0, 0]
                if mode == 0
                else [
                    controller["mode_one_initial_scroll"]
                    + pack["background"]["width_tiles"] * 2 * 4,
                    0,
                ]
            )
            for task_index in range(pack["spawn_count"]):
                initial = [
                    xs[task_index],
                    controller["main_initial_y"][task_index],
                ]
                target = [
                    xs[task_index],
                    controller["main_target_y"][task_index],
                ]
                track_id = (
                    f"task/main/mode-{mode}-pack-{pack_id:02d}"
                    f"-task-{task_index}"
                )
                tracks.append(
                    _expected_task_track(
                        bundle,
                        controller=controller,
                        layering=layering,
                        track_id=track_id,
                        kind="main_task",
                        mode=mode,
                        pack=pack,
                        pack_id=pack_id,
                        task_index=task_index,
                        initial_counter=task_index,
                        initial=initial,
                        target=target,
                        background=backgrounds[pack_id][0],
                        background_indices=backgrounds[pack_id][1],
                        scroll=scroll,
                        upstream=upstream,
                        errors=errors,
                        expected_names=expected_names,
                    )
                )
    for mode, obj_pack_id in ((1, 8),):
        track_id = f"task/exit/mode-{mode}-obj-pack-{obj_pack_id:02d}"
        tracks.append(
            _expected_task_track(
                bundle,
                controller=controller,
                layering=layering,
                track_id=track_id,
                kind="exit_task",
                mode=mode,
                pack=packs[obj_pack_id],
                pack_id=obj_pack_id,
                task_index=0,
                initial_counter=0,
                initial=controller["exit_initial"],
                target=controller["exit_target"],
                background=backgrounds[8][0],
                background_indices=backgrounds[8][1],
                scroll=controller["exit_scroll"],
                upstream=upstream,
                errors=errors,
                expected_names=expected_names,
            )
        )
    return tracks


def _summary(
    controller_tracks: list[dict[str, Any]],
    task_tracks: list[dict[str, Any]],
) -> dict[str, Any]:
    main_background = [
        track for track in controller_tracks if track["kind"] == "main_background"
    ]
    exit_background = [
        track for track in controller_tracks if track["kind"] == "exit_background"
    ]
    main_tasks = [track for track in task_tracks if track["kind"] == "main_task"]
    exit_tasks = [track for track in task_tracks if track["kind"] == "exit_task"]
    return {
        "main_background_track_count": len(main_background),
        "exit_background_track_count": len(exit_background),
        "main_background_scroll_write_count": sum(
            track["state_count"] for track in main_background
        ),
        "exit_background_scroll_write_count": sum(
            track["state_count"] for track in exit_background
        ),
        "background_scroll_write_count": sum(
            track["state_count"] for track in controller_tracks
        ),
        "main_task_track_count": len(main_tasks),
        "exit_task_track_count": len(exit_tasks),
        "task_callback_witness_state_count": sum(
            track["state_count"] for track in task_tracks
        ),
        "archive_entry_count": (
            sum(track["state_count"] for track in controller_tracks)
            + sum(track["state_count"] for track in task_tracks)
        ),
        "source_pack_count": 9,
    }


def verify_scene_visual_transition_timelines(
    root: Path,
    artifact: Path,
) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.resolve()
    errors: list[str] = []
    expected_summary: dict[str, Any] = {}
    try:
        manifest = _json(artifact / "manifest.json")
        payload = _json(artifact / PAYLOAD_NAME)
        if manifest.get("schema") != "git-artifact-promotion-v1":
            errors.append("promotion manifest schema mismatch")
        if manifest.get("artifact_id") != ARTIFACT_ID:
            errors.append("artifact id mismatch")
        if manifest.get("artifact_status") != "accepted":
            errors.append("artifact is not accepted")
        if manifest.get("artifact_schema") != "scene-visual-transition-phases-v1":
            errors.append("artifact schema mismatch")

        actual_files = {
            path.relative_to(artifact).as_posix(): path
            for path in artifact.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != set(actual_files):
            errors.append("artifact file inventory mismatch")
            files = {}
        for relative, digest in files.items():
            if relative in actual_files and _sha256(actual_files[relative]) != digest:
                errors.append(f"artifact hash mismatch: {relative}")
        payload_hash = _sha256(artifact / PAYLOAD_NAME)
        if manifest.get("payload_sha256") != payload_hash:
            errors.append("payload hash mismatch")

        rom = (root / "rom/base.gba").read_bytes()
        if _sha256_bytes(rom) != ROM_SHA256:
            errors.append("base ROM SHA-256 mismatch")
        for name, (start, end, digest) in CODE_SLICES.items():
            if _sha256_bytes(rom[start - ROM_BASE : end - ROM_BASE]) != digest:
                errors.append(f"{name} code slice mismatch")

        upstream = root / UPSTREAM
        if _sha256(upstream / "manifest.json") != UPSTREAM_MANIFEST_SHA256:
            errors.append("upstream scene pack manifest mismatch")
        source = _json(upstream / "manifest.json")
        packs = source["packs"]
        if [pack["pack_id"] for pack in packs] != list(range(9)):
            errors.append("upstream pack denominator mismatch")
        if _sha256(root / COMPOSITE_PATH / "manifest.json") != (
            COMPOSITE_MANIFEST_SHA256
        ):
            errors.append("stable composite manifest mismatch")

        phase_model = _derive_phase_model(rom)
        controller = _derive_controller_model(rom)
        layering = _derive_layering_model(rom)
        backgrounds = {
            pack["pack_id"]: _background(pack, upstream)
            for pack in packs
        }
        archive_path = artifact / ARCHIVE_NAME
        expected_names: list[str] = []
        with zipfile.ZipFile(archive_path) as bundle:
            if bundle.comment:
                errors.append("archive comment mismatch")
            expected_controller = _expected_background_tracks(
                bundle,
                controller=controller,
                packs=packs,
                backgrounds=backgrounds,
                errors=errors,
                expected_names=expected_names,
            )
            expected_tasks = _expected_task_tracks(
                bundle,
                controller=controller,
                layering=layering,
                packs=packs,
                backgrounds=backgrounds,
                upstream=upstream,
                errors=errors,
                expected_names=expected_names,
            )
            if bundle.namelist() != expected_names:
                errors.append("archive entry inventory or order mismatch")

        if payload.get("background_scroll_tracks") != expected_controller:
            errors.append("controller background records mismatch")
        if payload.get("task_callback_tracks") != expected_tasks:
            errors.append("task callback records mismatch")

        expected_summary = _summary(expected_controller, expected_tasks)
        if expected_summary != {
            "main_background_track_count": 8,
            "exit_background_track_count": 1,
            "main_background_scroll_write_count": 342,
            "exit_background_scroll_write_count": 61,
            "background_scroll_write_count": 403,
            "main_task_track_count": 15,
            "exit_task_track_count": 1,
            "task_callback_witness_state_count": 521,
            "archive_entry_count": 924,
            "source_pack_count": 9,
        }:
            errors.append("independent denominator mismatch")
        if payload.get("summary") != expected_summary:
            errors.append("summary mismatch")

        expected_scope = {
            "background_pre_spawn_order_complete": True,
            "finite_task_position_writes_complete": True,
            "state_2_and_state_20_counter_bounds_complete": True,
            "stable_endpoint_spatial_context_reconciled": True,
            "full_controller_timeline_complete": False,
            "state_3_external_wait_timing_complete": False,
            "cross_task_scheduler_order_complete": False,
            "presentation_overlay_composition_complete": False,
            "vblank_or_wall_frame_timing_complete": False,
            "window_blend_mosaic_runtime_complete": False,
            "runtime_pixel_equivalence": False,
            "natural_language_identity_complete": False,
        }
        expected_timing = {
            "controller_background_records": (
                "callback return boundaries, rendered without OBJ"
            ),
            "main_first_record": (
                "state 0 initialization and its same-invocation state 1 scroll"
            ),
            "spawn_event": "recorded after the final background scroll write",
            "task_records": (
                "independent callback-local spatial witnesses over stable background"
            ),
            "task_last_position_write_counter": 31,
            "task_first_stable_callback_counter": 32,
            "counter_step_q12": 128,
            "fraction_bits": 12,
            "division": "signed_truncate_toward_zero",
            "not_a_wall_frame_timeline": True,
        }
        expected_code = {
            name: {
                "start": f"0x{start:08X}",
                "end_exclusive": f"0x{end:08X}",
                "size": end - start,
                "sha256": digest,
            }
            for name, (start, end, digest) in CODE_SLICES.items()
        }
        expected_implementation = {
            relative: _sha256(root / relative)
            for relative in IMPLEMENTATION_PATHS
        }
        expected_upstream = {
            "scene_visual_packs": {
                "path": UPSTREAM.as_posix(),
                "manifest_sha256": UPSTREAM_MANIFEST_SHA256,
            },
            "stable_composites": {
                "path": COMPOSITE_PATH.as_posix(),
                "manifest_sha256": COMPOSITE_MANIFEST_SHA256,
            },
        }
        expected_archive = {
            "file": ARCHIVE_NAME,
            "entry_count": expected_summary["archive_entry_count"],
            "sha256": _sha256(archive_path),
            "zip_method": "stored_png",
            "entry_timestamp": "1980-01-01T00:00:00",
            "create_system": 3,
            "external_attr": "0o100644<<16",
            "archive_comment": "",
        }
        for field, expected in (
            ("schema", "scene-visual-transition-phases-v1"),
            ("artifact_id", ARTIFACT_ID),
            ("rom", {"path": "rom/base.gba", "sha256": ROM_SHA256}),
            ("upstream", expected_upstream),
            ("implementation", expected_implementation),
            ("code_evidence", expected_code),
            ("controller_model", phase_model),
            ("timing_model", expected_timing),
            ("frame_archive", expected_archive),
            ("scope", expected_scope),
        ):
            if payload.get(field) != expected:
                errors.append(f"{field} mismatch")
        if manifest.get("scope") != expected_scope:
            errors.append("promotion scope mismatch")

        stable = verify_scene_visual_composites(root, root / COMPOSITE_PATH)
        if not stable["verified"]:
            errors.append("upstream stable composite verifier failed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "verified": not errors,
        "errors": errors,
        "archive_entry_count": expected_summary.get("archive_entry_count", 0),
        "background_scroll_write_count": expected_summary.get(
            "background_scroll_write_count",
            0,
        ),
        "task_callback_witness_state_count": expected_summary.get(
            "task_callback_witness_state_count",
            0,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    artifact = (
        args.artifact
        if args.artifact.is_absolute()
        else args.root / args.artifact
    )
    report = verify_scene_visual_transition_timelines(args.root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
