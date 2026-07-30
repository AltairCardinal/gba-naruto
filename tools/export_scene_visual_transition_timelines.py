#!/usr/bin/env python3
"""Export controller-local scene background phases and task motion witnesses."""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
import zipfile

from PIL import Image, ImageChops


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.export_scene_visual_composites import (
    CODE_SLICES,
    ROM_SHA256,
    _hardware_background,
    _interpolate_q12,
    _validate_inputs,
    _viewport,
)


ROM_BASE = 0x08000000
ARTIFACT_ID = "scene-visual-transition-timelines-v1"
PAYLOAD_NAME = "scene-visual-transition-timelines.json"
ARCHIVE_NAME = "frames.zip"
UPSTREAM_PACK_MANIFEST_SHA256 = (
    "4bb40dff9ac2e5641b5e13f46b1dc90bdaa28b9b5615deab7e2a914ae002d5f4"
)
UPSTREAM_COMPOSITE_MANIFEST = Path(
    "artifacts/scene-visual-composites-v1/manifest.json"
)
UPSTREAM_COMPOSITE_MANIFEST_SHA256 = (
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


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _write_zip_entry(bundle: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.internal_attr = 0
    info.flag_bits = 0
    info.extra = b""
    info.comment = b""
    bundle.writestr(info, data)


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
    bounds = frame["png"]["local_bounds"]
    origin = [
        position[0] + bounds["min_x"],
        position[1] + bounds["min_y"],
    ]
    layer = Image.new("RGBA", image.size)
    layer.alpha_composite(
        Image.open(upstream / frame["png"]["file"]).convert("RGBA"),
        tuple(origin),
    )
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


def _archive_record(
    bundle: zipfile.ZipFile,
    *,
    frame_file: str,
    image: Image.Image,
    fields: dict[str, Any],
) -> dict[str, Any]:
    png = _png_bytes(image)
    _write_zip_entry(bundle, frame_file, png)
    return {
        **fields,
        "frame_file": frame_file,
        "pixel_sha256": _sha256_bytes(image.tobytes()),
        "png_sha256": _sha256_bytes(png),
    }


def _spawned_main_tasks(mode: dict[str, Any], pack: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "task_index": index,
            "counter": index,
            "position": [
                mode["main_task_x"][index],
                (-160, 240)[index],
            ],
        }
        for index in range(pack["spawn_count"])
    ]


def _controller_model(rom: bytes) -> dict[str, Any]:
    handlers = [
        int.from_bytes(
            rom[
                address - ROM_BASE : address - ROM_BASE + 4
            ],
            "little",
        )
        for address in range(JUMP_TABLE_BASE, JUMP_TABLE_BASE + 21 * 4, 4)
    ]
    if tuple(handlers) != JUMP_TABLE_HANDLERS:
        raise ValueError("scene controller jump table mismatch")
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


def _background_tracks(
    bundle: zipfile.ZipFile,
    *,
    modes: tuple[dict[str, Any], ...],
    packs: list[dict[str, Any]],
    backgrounds: dict[int, tuple[Image.Image, Image.Image]],
) -> list[dict[str, Any]]:
    tracks = []
    for mode in modes:
        for pack_id in mode["main_pack_ids"]:
            pack = packs[pack_id]
            width = pack["background"]["width_tiles"] * 8
            callback_count = width // 4
            initial_scroll = width if mode["mode"] == 0 else -240
            step = -4 if mode["mode"] == 0 else 4
            track_id = f"controller/main/mode-{mode['mode']}-pack-{pack_id:02d}"
            background, indices = backgrounds[pack_id]
            states = []
            for write_index in range(callback_count + 1):
                scroll = [initial_scroll + write_index * step, 0]
                image, _ = _viewport(background, indices, tuple(scroll))
                final = write_index == callback_count
                states.append(
                    _archive_record(
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
                                _spawned_main_tasks(mode, pack) if final else []
                            ),
                            "obj_placements": [],
                            "render_scope": "controller_background_only",
                        },
                    )
                )
            tracks.append(
                {
                    "track_id": track_id,
                    "kind": "main_background",
                    "mode": mode["mode"],
                    "pack_id": pack_id,
                    "background_width_pixels": width,
                    "controller_dispatch_count": callback_count,
                    "state_count": len(states),
                    "states": states,
                }
            )

    for mode in modes:
        if not mode["exit_reachable"]:
            continue
        obj_pack_id = mode["exit_obj_pack_id"]
        track_id = (
            f"controller/exit/mode-{mode['mode']}-obj-pack-"
            f"{obj_pack_id:02d}-over-pack-08"
        )
        background, indices = backgrounds[8]
        states = []
        for callback_index in range(61):
            scroll = [-40, -240 + callback_index * 4]
            image, _ = _viewport(background, indices, tuple(scroll))
            final = callback_index == 60
            states.append(
                _archive_record(
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
                                    "position": [240, 128],
                                }
                            ]
                            if final
                            else []
                        ),
                        "obj_placements": [],
                        "render_scope": "controller_background_only",
                    },
                )
            )
        tracks.append(
            {
                "track_id": track_id,
                "kind": "exit_background",
                "mode": mode["mode"],
                "background_pack_id": 8,
                "obj_pack_id": obj_pack_id,
                "state_count": len(states),
                "states": states,
            }
        )
    return tracks


def _task_states(
    bundle: zipfile.ZipFile,
    *,
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
    background_priority: int,
    obj_priority: int,
    upstream: Path,
) -> dict[str, Any]:
    states = []
    position = list(initial)
    for state_index, counter in enumerate(range(initial_counter, 33)):
        callback_executed = state_index != 0
        position_written = callback_executed and counter <= 31
        if position_written:
            axis = 0 if kind == "exit_task" else 1
            position[axis] = _interpolate_q12(
                initial[axis],
                target[axis],
                counter,
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
            background_priority=background_priority,
            obj_priority=obj_priority,
            upstream=upstream,
        )
        states.append(
            _archive_record(
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
            )
        )
    result = {
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
    return result


def _task_tracks(
    bundle: zipfile.ZipFile,
    *,
    modes: tuple[dict[str, Any], ...],
    packs: list[dict[str, Any]],
    backgrounds: dict[int, tuple[Image.Image, Image.Image]],
    upstream: Path,
) -> list[dict[str, Any]]:
    tracks = []
    for mode in modes:
        for pack_id in mode["main_pack_ids"]:
            pack = packs[pack_id]
            width = pack["background"]["width_tiles"] * 8
            scroll = [0, 0] if mode["mode"] == 0 else [width - 240, 0]
            for task_index in range(pack["spawn_count"]):
                initial = [
                    mode["main_task_x"][task_index],
                    (-160, 240)[task_index],
                ]
                target = [
                    mode["main_task_x"][task_index],
                    (16, 64)[task_index],
                ]
                track_id = (
                    f"task/main/mode-{mode['mode']}-pack-{pack_id:02d}"
                    f"-task-{task_index}"
                )
                tracks.append(
                    _task_states(
                        bundle,
                        track_id=track_id,
                        kind="main_task",
                        mode=mode["mode"],
                        pack=pack,
                        pack_id=pack_id,
                        task_index=task_index,
                        initial_counter=task_index,
                        initial=initial,
                        target=target,
                        background=backgrounds[pack_id][0],
                        background_indices=backgrounds[pack_id][1],
                        scroll=scroll,
                        background_priority=2,
                        obj_priority=2,
                        upstream=upstream,
                    )
                )

    for mode in modes:
        if not mode["exit_reachable"]:
            continue
        obj_pack_id = mode["exit_obj_pack_id"]
        track_id = f"task/exit/mode-{mode['mode']}-obj-pack-{obj_pack_id:02d}"
        tracks.append(
            _task_states(
                bundle,
                track_id=track_id,
                kind="exit_task",
                mode=mode["mode"],
                pack=packs[obj_pack_id],
                pack_id=obj_pack_id,
                task_index=0,
                initial_counter=0,
                initial=[240, 128],
                target=[80, 128],
                background=backgrounds[8][0],
                background_indices=backgrounds[8][1],
                scroll=[-40, 0],
                background_priority=2,
                obj_priority=3,
                upstream=upstream,
            )
        )
    return tracks


def _build_payload(root: Path, output: Path) -> dict[str, Any]:
    rom, upstream, source = _validate_inputs(root)
    if _sha256(root / UPSTREAM_COMPOSITE_MANIFEST) != (
        UPSTREAM_COMPOSITE_MANIFEST_SHA256
    ):
        raise ValueError("scene visual composite manifest SHA-256 mismatch")
    modes = (
        {
            "mode": 0,
            "main_pack_ids": list(range(4)),
            "main_task_x": [192, 160],
            "exit_reachable": False,
            "exit_obj_pack_id": None,
        },
        {
            "mode": 1,
            "main_pack_ids": list(range(4, 8)),
            "main_task_x": [48, 16],
            "exit_reachable": True,
            "exit_obj_pack_id": 8,
        },
    )
    packs = source["packs"]
    backgrounds = {
        pack["pack_id"]: _hardware_background(pack, upstream)
        for pack in packs
    }
    archive_path = output / ARCHIVE_NAME
    with zipfile.ZipFile(archive_path, "w") as bundle:
        bundle.comment = b""
        controller_tracks = _background_tracks(
            bundle,
            modes=modes,
            packs=packs,
            backgrounds=backgrounds,
        )
        task_tracks = _task_tracks(
            bundle,
            modes=modes,
            packs=packs,
            backgrounds=backgrounds,
            upstream=upstream,
        )
    main_background = [
        track for track in controller_tracks if track["kind"] == "main_background"
    ]
    exit_background = [
        track for track in controller_tracks if track["kind"] == "exit_background"
    ]
    main_tasks = [track for track in task_tracks if track["kind"] == "main_task"]
    exit_tasks = [track for track in task_tracks if track["kind"] == "exit_task"]
    summary = {
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
    if summary != {
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
        raise ValueError("scene transition phase denominator mismatch")
    scope = {
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
    return {
        "schema": "scene-visual-transition-phases-v1",
        "artifact_id": ARTIFACT_ID,
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "upstream": {
            "scene_visual_packs": {
                "path": "artifacts/scene-visual-packs-v1",
                "manifest_sha256": UPSTREAM_PACK_MANIFEST_SHA256,
            },
            "stable_composites": {
                "path": "artifacts/scene-visual-composites-v1",
                "manifest_sha256": UPSTREAM_COMPOSITE_MANIFEST_SHA256,
            },
        },
        "implementation": {
            relative: _sha256(root / relative)
            for relative in IMPLEMENTATION_PATHS
        },
        "code_evidence": {
            name: {
                "start": f"0x{start:08X}",
                "end_exclusive": f"0x{end:08X}",
                "size": end - start,
                "sha256": digest,
            }
            for name, (start, end, digest) in CODE_SLICES.items()
        },
        "controller_model": _controller_model(rom),
        "timing_model": {
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
        },
        "frame_archive": {
            "file": ARCHIVE_NAME,
            "entry_count": summary["archive_entry_count"],
            "sha256": _sha256(archive_path),
            "zip_method": "stored_png",
            "entry_timestamp": "1980-01-01T00:00:00",
            "create_system": 3,
            "external_attr": "0o100644<<16",
            "archive_comment": "",
        },
        "background_scroll_tracks": controller_tracks,
        "task_callback_tracks": task_tracks,
        "summary": summary,
        "scope": scope,
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


def export_scene_visual_transition_timelines(
    root: Path,
    output: Path,
) -> dict[str, Any]:
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
                    "tools/verify_scene_visual_transition_timelines.py",
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
    payload = export_scene_visual_transition_timelines(args.root, output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
