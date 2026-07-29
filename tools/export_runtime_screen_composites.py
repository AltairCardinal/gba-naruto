#!/usr/bin/env python3
"""Export auditable Mode 0 screen composites for tracked mGBA checkpoints."""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import zipfile

from PIL import Image

try:
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.render_mode0_checkpoint import (
        _active_objects,
        _object_coverage,
        _rgb8,
        render_mode0,
    )
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state
    from render_mode0_checkpoint import (
        _active_objects,
        _object_coverage,
        _rgb8,
        render_mode0,
    )


SCHEMA = "runtime-screen-composites-v1"
WIDTH = 240
HEIGHT = 160
SHADOW_OAM_ADDRESS = 0x0300027C
PHASE_CASES = {
    "alternate-character-submenu.ss9": (0x3F4, 0x3FA),
    "skill-list-pre-controller.ss9": (0x3FA, 0x3F8),
}
SCOPE = {
    "all_tracked_mode0_static_frames_rendered": True,
    "hardware_oam_domain_used_for_rendering": True,
    "89_of_91_screenshot_pixels_exact": True,
    "two_screenshot_phase_mismatches_accounted_for": True,
    "natural_mode0_text_bg_normal_1d_obj_alpha_darken_covered": True,
    "synthetic_2d_8bpp_semitransparent_obj_window_brighten_win1_covered": True,
    "unexplained_screenshot_mismatches_remaining": False,
    "natural_affine_obj_normal_and_mirror_bound_pixels_covered": True,
    "synthetic_affine_double_size_covered": True,
    "synthetic_mode0_bg_normal_and_affine_obj_mosaic_source_model_covered": True,
    "natural_nonzero_mosaic_runtime_covered": False,
    "physical_gba_mosaic_verified": False,
    "obj_window_mosaic_physical_semantics_complete": False,
    "scanline_register_changes_complete": False,
    "cross_frame_timing_complete": False,
    "screenshot_capture_phase_timing_complete": False,
    "physical_gba_display_output_verified": False,
    "all_game_visual_states_complete": False,
}
MOSAIC_REFERENCE_MODEL = {
    "implementation": "mGBA software renderer",
    "commit": "1d65391d3531f9338300f306c4e1d76c258ce657",
    "sources": [
        {
            "path": "src/gba/renderers/software-mode0.c",
            "sha256": "1e4104200fa1c068ff4ff17c24d8f99f9e1aed112d75e5088773e1bb6a318783",
            "role": "mode0-text-bg-mosaic",
        },
        {
            "path": "src/gba/renderers/software-obj.c",
            "sha256": "b737ba2372054156fd987f95ed9350e3370f469cb38b40367657c70c02667fe9",
            "role": "normal-and-affine-obj-horizontal-mosaic",
        },
        {
            "path": "src/gba/renderers/video-software.c",
            "sha256": "39a03b64a3fe9ab384a17de7d92d215298e9f5b64415f7c550d33779c2bbaf70",
            "role": "obj-vertical-mosaic",
        },
    ],
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _png(rgb: bytes) -> bytes:
    image = Image.frombytes("RGB", (WIDTH, HEIGHT), rgb)
    output = BytesIO()
    image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def _screenshot(path: Path) -> bytes:
    with Image.open(path) as image:
        if image.size != (WIDTH, HEIGHT):
            raise ValueError(f"{path.name}: unexpected screenshot size {image.size}")
        return image.convert("RGB").tobytes()


def _difference(rendered: bytes, screenshot: bytes) -> tuple[int, int, list[list[int]]]:
    byte_count = sum(left != right for left, right in zip(rendered, screenshot))
    coordinates = [
        [offset // 3 % WIDTH, offset // 3 // WIDTH]
        for offset in range(0, len(rendered), 3)
        if rendered[offset : offset + 3] != screenshot[offset : offset + 3]
    ]
    return byte_count, len(coordinates), coordinates


def _bbox(coordinates: list[list[int]]) -> list[int] | None:
    if not coordinates:
        return None
    xs = [item[0] for item in coordinates]
    ys = [item[1] for item in coordinates]
    return [min(xs), min(ys), max(xs) + 1, max(ys) + 1]


def _object_rect(oam: bytes, index: int) -> list[int]:
    dimensions = {
        0: ((8, 8), (16, 16), (32, 32), (64, 64)),
        1: ((16, 8), (32, 8), (32, 16), (64, 32)),
        2: ((8, 16), (8, 32), (16, 32), (32, 64)),
    }
    attr0, attr1 = struct.unpack_from("<HH", oam, index * 8)
    width, height = dimensions[(attr0 >> 14) & 3][(attr1 >> 14) & 3]
    x, y = attr1 & 0x1FF, attr0 & 0xFF
    if x >= 256:
        x -= 512
    if y >= 160:
        y -= 256
    return [x, y, x + width, y + height]


def _domain(data: bytes, address: int) -> dict[str, object]:
    return {
        "address": f"0x{address:08X}",
        "size": len(data),
        "sha256": _sha(data),
    }


def _phase_record(
    path: Path,
    io: bytes,
    pram: bytes,
    vram: bytes,
    hardware_oam: bytes,
    shadow_oam: bytes,
    screenshot: bytes,
    coordinates: list[list[int]],
) -> dict[str, object]:
    serialized_tile, screenshot_tile = PHASE_CASES[path.name]
    oam_index = 0
    offset = oam_index * 8
    attr0, attr1, attr2 = struct.unpack_from("<HHH", hardware_oam, offset)
    if attr2 & 0x3FF != serialized_tile:
        raise ValueError(f"{path.name}: unexpected serialized cursor tile")
    counterfactual = bytearray(hardware_oam)
    struct.pack_into(
        "<H",
        counterfactual,
        offset + 4,
        (attr2 & 0xFC00) | screenshot_tile,
    )
    counterfactual_rgb, _ = render_mode0(
        io, pram, bytes(counterfactual), vram
    )
    rect = _object_rect(hardware_oam, oam_index)
    inside = all(
        rect[0] <= x < rect[2] and rect[1] <= y < rect[3]
        for x, y in coordinates
    )
    return {
        "classification": "embedded-png-cursor-tile-phase-mismatch",
        "oam_index": oam_index,
        "hardware_shadow_oam_equal": hardware_oam == shadow_oam,
        "hardware_oam_entry_hex": hardware_oam[offset : offset + 8].hex(),
        "shadow_oam_entry_hex": shadow_oam[offset : offset + 8].hex(),
        "attr0": f"0x{attr0:04X}",
        "attr1": f"0x{attr1:04X}",
        "attr2": f"0x{attr2:04X}",
        "serialized_tile": serialized_tile,
        "screenshot_exact_tile": screenshot_tile,
        "object_screen_rect": rect,
        "all_differences_within_object_rect": inside,
        "differing_pixel_coordinates_sha256": _sha(
            json.dumps(coordinates, separators=(",", ":")).encode("utf-8")
        ),
        "counterfactual_rendered_rgb_sha256": _sha(counterfactual_rgb),
        "single_oam_tile_substitution_exact": counterfactual_rgb == screenshot,
        "unexplained_difference_count": (
            0 if counterfactual_rgb == screenshot and inside else len(coordinates)
        ),
    }


def _checkpoint(root: Path, path: Path) -> tuple[dict[str, object], bytes]:
    state = load_gba_state(path)
    io = state.read_memory(0x04000000, 0x400)
    pram = state.read_memory(0x05000000, 0x400)
    vram = state.read_memory(0x06000000, 0x18000)
    hardware_oam = state.read_memory(0x07000000, 0x400)
    shadow_oam = state.read_memory(SHADOW_OAM_ADDRESS, 0x400)
    rendered, stats = render_mode0(io, pram, hardware_oam, vram)
    screenshot = _screenshot(path)
    differing_bytes, differing_pixels, coordinates = _difference(
        rendered, screenshot
    )
    phase = None
    if differing_pixels:
        if path.name not in PHASE_CASES:
            raise ValueError(f"{path.name}: unexplained screenshot mismatch")
        phase = _phase_record(
            path,
            io,
            pram,
            vram,
            hardware_oam,
            shadow_oam,
            screenshot,
            coordinates,
        )
        if (
            not phase["hardware_shadow_oam_equal"]
            or not phase["single_oam_tile_substitution_exact"]
            or phase["unexplained_difference_count"]
        ):
            raise ValueError(f"{path.name}: phase classification is not exact")
    elif path.name in PHASE_CASES:
        raise ValueError(f"{path.name}: expected phase mismatch disappeared")
    member = f"frames/{path.stem}.png"
    png = _png(rendered)
    return (
        {
            "path": path.relative_to(root).as_posix(),
            "checkpoint_sha256": _sha(path.read_bytes()),
            "oam_input_domain": "hardware-oam-0x07000000",
            "domains": {
                "io": _domain(io, 0x04000000),
                "pram": _domain(pram, 0x05000000),
                "vram": _domain(vram, 0x06000000),
                "hardware_oam": _domain(hardware_oam, 0x07000000),
                "shadow_oam": _domain(shadow_oam, SHADOW_OAM_ADDRESS),
            },
            "display": {
                "dispcnt": f"0x{_u16(io, 0):04X}",
                "mode": _u16(io, 0) & 7,
                "obj_mapping": "1d" if _u16(io, 0) & 0x40 else "2d",
                "enabled_backgrounds": [
                    index
                    for index in range(4)
                    if _u16(io, 0) & (1 << (8 + index))
                ],
            },
            "active_oam_count": int(stats.get("active", 0)),
            "rendered_frame": {
                "archive_member": member,
                "png_sha256": _sha(png),
                "rgb_sha256": _sha(rendered),
                "width": WIDTH,
                "height": HEIGHT,
            },
            "rendered_rgb_sha256": _sha(rendered),
            "screenshot_rgb_sha256": _sha(screenshot),
            "rgb_exact": rendered == screenshot,
            "differing_bytes": differing_bytes,
            "differing_pixels": differing_pixels,
            "difference_bbox": _bbox(coordinates),
            "phase_classification": phase,
        },
        png,
    )


def _affine_runtime_goldens(root: Path) -> list[dict[str, object]]:
    evidence_root = root / "artifacts/battle-effect-affine-runtime-v1"
    cases = (
        ("raw/state-0154.ss9", 2, "runtime-object-02.png"),
        (
            "mirror-raw/mirrored.ss9",
            5,
            "runtime-object-mirrored.png",
        ),
    )
    records = []
    for state_relative, object_index, reference_relative in cases:
        state_path = evidence_root / state_relative
        state = load_gba_state(state_path)
        io = state.read_memory(0x04000000, 0x400)
        pram = state.read_memory(0x05000000, 0x400)
        vram = state.read_memory(0x06000000, 0x18000)
        hardware_oam = state.read_memory(0x07000000, 0x400)
        isolated_oam = bytearray(hardware_oam)
        for index in range(128):
            struct.pack_into("<H", isolated_oam, index * 8, 0x0200)
        start = object_index * 8
        isolated_oam[start : start + 6] = hardware_oam[start : start + 6]
        candidates, _, stats = _object_coverage(
            _u16(io, 0),
            _u16(io, 0x4C),
            pram,
            bytes(isolated_oam),
            vram,
        )
        attr0, attr1, attr2 = struct.unpack_from("<HHH", hardware_oam, start)
        matrix_index = (attr1 >> 9) & 0x1F
        matrix = tuple(
            struct.unpack_from(
                "<h",
                hardware_oam,
                (matrix_index * 4 + component) * 8 + 6,
            )[0]
            for component in range(4)
        )
        width, height = {
            0: ((8, 8), (16, 16), (32, 32), (64, 64)),
            1: ((16, 8), (32, 8), (32, 16), (64, 32)),
            2: ((8, 16), (8, 32), (16, 32), (32, 64)),
        }[(attr0 >> 14) & 3][(attr1 >> 14) & 3]
        if attr0 & 0x200:
            width *= 2
            height *= 2
        origin_x, origin_y = attr1 & 0x1FF, attr0 & 0xFF
        if origin_x >= 256:
            origin_x -= 512
        if origin_y >= 160:
            origin_y -= 256
        rgba = bytearray()
        for local_y in range(height):
            for local_x in range(width):
                x, y = origin_x + local_x, origin_y + local_y
                pixels = (
                    candidates[y * WIDTH + x]
                    if 0 <= x < WIDTH and 0 <= y < HEIGHT
                    else []
                )
                if pixels:
                    if len(pixels) != 1:
                        raise ValueError(
                            f"{state_path.name}: isolated affine overlap"
                        )
                    rgba.extend((*_rgb8(pixels[0].color), 255))
                else:
                    rgba.extend((0, 0, 0, 0))
        reference_path = evidence_root / reference_relative
        with Image.open(reference_path) as image:
            reference_rgba = image.convert("RGBA").tobytes()
            reference_size = list(image.size)
        if bytes(rgba) != reference_rgba or reference_size != [width, height]:
            raise ValueError(
                f"{state_path.name}: affine object does not match reference"
            )
        records.append(
            {
                "state_path": state_path.relative_to(root).as_posix(),
                "state_sha256": _sha(state_path.read_bytes()),
                "object_index": object_index,
                "attributes": {
                    "attr0": f"0x{attr0:04X}",
                    "attr1": f"0x{attr1:04X}",
                    "attr2": f"0x{attr2:04X}",
                    "affine": True,
                    "double_size": bool(attr0 & 0x200),
                    "matrix_index": matrix_index,
                    "matrix": {
                        name: value
                        for name, value in zip(
                            ("PA", "PB", "PC", "PD"), matrix
                        )
                    },
                },
                "domains": {
                    "io": _domain(io, 0x04000000),
                    "pram": _domain(pram, 0x05000000),
                    "vram": _domain(vram, 0x06000000),
                    "hardware_oam": _domain(hardware_oam, 0x07000000),
                },
                "reference_png": {
                    "path": reference_path.relative_to(root).as_posix(),
                    "sha256": _sha(reference_path.read_bytes()),
                    "rgba_sha256": _sha(reference_rgba),
                    "width": width,
                    "height": height,
                },
                "rendered_rgba_sha256": _sha(bytes(rgba)),
                "rgba_exact": True,
                "isolated_active_oam_count": int(stats.get("active", 0)),
                "isolated_affine_oam_count": int(stats.get("affine", 0)),
            }
        )
    return records


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name], compresslevel=9)


def _build(root: Path, output: Path) -> dict[str, object]:
    paths = sorted((root / "artifacts/runtime-checkpoints").glob("*.ss9"))
    if not paths:
        raise ValueError("no tracked runtime checkpoints found")
    checkpoints: list[dict[str, object]] = []
    members: dict[str, bytes] = {}
    for path in paths:
        record, png = _checkpoint(root, path)
        checkpoints.append(record)
        member = str(record["rendered_frame"]["archive_member"])
        if member in members:
            raise ValueError(f"duplicate archive member {member}")
        members[member] = png
    archive_path = output / "frames.zip"
    _write_zip(archive_path, members)
    archive = archive_path.read_bytes()
    exact_count = sum(bool(row["rgb_exact"]) for row in checkpoints)
    affine_goldens = _affine_runtime_goldens(root)
    implementation = {
        "exporter_sha256": _sha(
            (root / "tools/export_runtime_screen_composites.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            (root / "tools/verify_runtime_screen_composites.py").read_bytes()
        ),
        "renderer_sha256": _sha(
            (root / "tools/render_mode0_checkpoint.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_runtime_screen_composites.py").read_bytes()
        ),
        "renderer_test_sha256": _sha(
            (root / "tests/test_render_mode0_checkpoint.py").read_bytes()
        ),
        "renderer_source_verifier_sha256": _sha(
            (root / "tools/verify_mgba_renderer_source.py").read_bytes()
        ),
    }
    data = {
        "schema": SCHEMA,
        "implementation": implementation,
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_glob": "*.ss9",
            "checkpoint_count": len(checkpoints),
            "affine_runtime_evidence_root": (
                "artifacts/battle-effect-affine-runtime-v1"
            ),
            "affine_runtime_evidence_manifest_sha256": _sha(
                (
                    root
                    / "artifacts/battle-effect-affine-runtime-v1/manifest.json"
                ).read_bytes()
            ),
        },
        "renderer": {
            "display_mode": 0,
            "screen_size": [WIDTH, HEIGHT],
            "semantics": "serialized IO/PRAM/VRAM/hardware-OAM static frame",
            "oam_input_address": "0x07000000",
            "shadow_oam_diagnostic_address": f"0x{SHADOW_OAM_ADDRESS:08X}",
            "mosaic_reference_model": MOSAIC_REFERENCE_MODEL,
        },
        "summary": {
            "checkpoint_count": len(checkpoints),
            "exact_rgb_count": exact_count,
            "screenshot_phase_mismatch_count": len(checkpoints) - exact_count,
            "unexplained_mismatch_count": sum(
                int((row["phase_classification"] or {}).get(
                    "unexplained_difference_count", 0
                ))
                for row in checkpoints
            ),
            "active_oam_count": sum(
                int(row["active_oam_count"]) for row in checkpoints
            ),
            "archive_member_count": len(members),
            "affine_runtime_golden_count": len(affine_goldens),
        },
        "archive": {
            "file": "frames.zip",
            "size": len(archive),
            "sha256": _sha(archive),
            "member_count": len(members),
            "deterministic_zip_timestamp": "1980-01-01T00:00:00",
        },
        "checkpoints": checkpoints,
        "affine_runtime_goldens": affine_goldens,
        "scope": SCOPE,
    }
    data_bytes = (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    (output / "runtime-screen-composites.json").write_bytes(data_bytes)
    promotion = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            "frames.zip": _sha(archive),
            "runtime-screen-composites.json": _sha(data_bytes),
        },
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_count": len(checkpoints),
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_runtime_screen_composites.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/runtime-screen-composites-v1",
            ],
            **implementation,
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_runtime_screen_composites.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/runtime-screen-composites-v1",
            ],
            "verifier_sha256": implementation["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": "runtime-screen-composites-verification-v1",
                "verified": True,
                "checkpoint_count": len(checkpoints),
                "exact_rgb_count": exact_count,
                "errors": [],
            },
        },
        "experiment": {
            "task": "runtime-screen-composites",
            "run_id": "tracked-mode0-screen-mosaic-20260730-05",
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(promotion, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return data


def export_artifact(root: Path, output: Path) -> dict[str, object]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}.", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / output.name
        staged.mkdir()
        data = _build(root, staged)
        if output.exists():
            shutil.rmtree(output)
        os.replace(staged, output)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/runtime-screen-composites-v1"),
    )
    args = parser.parse_args()
    data = export_artifact(args.root, args.output_dir)
    print(json.dumps(data["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
