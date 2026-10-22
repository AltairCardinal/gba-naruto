#!/usr/bin/env python3
"""Independently verify the controlled story visual descriptor pixel A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
from typing import Any, Sequence

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.inspect_mgba_savestate import load_gba_state
from tools.patch_mgba_savestate_memory import patch_savestate
from tools.render_mode0_checkpoint import render_checkpoint


BASE_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PARENT_PATH = Path(
    "artifacts/runtime-checkpoints/scenario-41-postbattle-dialogue-8.ss9"
)
PARENT_SHA256 = "62adcd52b577f73ca1ffd6d2d4ec3b9fafa2a2b130ac644a6834e2a56a50d4d8"
INPUT_SHA256 = "65cd8b010f9c21a6d5bc93fe8ed1b84fada025136936f6a42f0d540d0f7ab0a9"
CANONICAL_PATH = Path(
    "artifacts/runtime-checkpoints/scenario-53-story-slideshow-command-controlled.ss9"
)
BINARY_SHA256 = "ef2386a58364932504b082fb5097340268c2b5b7b202bbf8201b0ce69271d54b"
SCRIPT_RELATIVE = Path("tools/mgba_battle_encounters_story_visual_trace.lua")
SCRIPT_SHA256 = "078c19552036a1fea0fe33ec173ec823ba81995b05f8a4398378eb90580e49e0"
PATCH_OFFSET = 0x54229C
BEFORE_POINTER = 0x0812FF50
AFTER_POINTER = 0x081303E8
RAW_FILES = {
    "build/build-manifest.json",
    "input/controlled-story-opcode.ss9",
    "runs/baseline/audit.json",
    "runs/baseline/final.png",
    "runs/baseline/final.ss9",
    "runs/baseline/guard-summary.json",
    "runs/candidate/audit.json",
    "runs/candidate/final.png",
    "runs/candidate/final.ss9",
    "runs/candidate/guard-summary.json",
    "launch-identity.json",
}
IMPLEMENTATION_FILES = {
    "tools/build_battle_encounters_story_visual_pixel_ab.py",
    "tools/export_battle_encounters_story_visual_pixel_ab.py",
    "tools/verify_battle_encounters_story_visual_pixel_ab.py",
    "tools/mgba_battle_encounters_story_visual_trace.lua",
    "tools/inspect_mgba_savestate.py",
    "tools/render_mode0_checkpoint.py",
    "tools/patch_mgba_savestate_memory.py",
    "tests/test_build_battle_encounters_story_visual_pixel_ab.py",
    "tests/test_mgba_battle_encounters_story_visual_trace_script.py",
    "tests/test_battle_encounters_story_visual_pixel_ab_artifact.py",
}
EXPECTED_PIXELS = {
    "width": 240,
    "height": 160,
    "changed_pixel_count": 1603,
    "bbox_inclusive": [88, 48, 159, 108],
    "baseline_rgb_sha256": "3551e69b1b3eef6e7acfc179ba2556622608544f322e3999b25c66f9fd90a2ce",
    "candidate_rgb_sha256": "6b87ae09aadf58d8ccca94f78efa5dd9260c04b29f6f20a2a4fc29cd56bb444a",
}
EXPECTED_REGIONS = {
    "IO": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "e0f287b97d27486e6c7e4ba5aba72b3dd71395199ffbd1660e45449920eaa2c6", "e0f287b97d27486e6c7e4ba5aba72b3dd71395199ffbd1660e45449920eaa2c6", None),
    "PRAM": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "76b4e174e0730e8902fee39c1f720b2449055d745c721dbcd35d8804aa0e3f32", "76b4e174e0730e8902fee39c1f720b2449055d745c721dbcd35d8804aa0e3f32", None),
    "VRAM": (2348, "0a2034d58c9f7ebb9556ee5fdbd77cf28d4468c99408ecae333d494775ec56e8", "0e151558329d8483c1424966fc77fedc8b8dcb9ee50ba7991faae162fdf577d9", "bc22c6e21af8cf4fbe8138cc6a82a4da2531974a8bebf22a10a269fd55700de2", (0xE83E, 0xF5C2)),
    "OAM": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "2a25f06c35b6c2bb7327a651cc845e3fafc093881f3c13358a3cce44b66ba13d", "2a25f06c35b6c2bb7327a651cc845e3fafc093881f3c13358a3cce44b66ba13d", None),
    "IWRAM": (1, "df07d516b299fe1db9db5f6c94a2e36735d5ce4027aeb9f7c648878b8882cc1c", "9645dd5ebdf587bb924c59ff442af5007d20b945db8a50e87981e3c2dbf9ee1f", "377dffd9048a62246e7058934612bdf5b75e87b49c74fff8c3f5c05c9a6e2ae8", (0x7F9C, 0x7F9C)),
    "EWRAM": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "75c12071d842f55e8ae96b811cf6bed241fca8279113d53b9763a2e7244afe71", "75c12071d842f55e8ae96b811cf6bed241fca8279113d53b9763a2e7244afe71", None),
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _extract_raw(archive_path: Path, output: Path) -> None:
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        if {member.name for member in members} != RAW_FILES:
            raise ValueError("battle-encounters raw archive file set mismatch")
        for member in members:
            target = Path(member.name)
            if (
                not member.isfile()
                or target.is_absolute()
                or ".." in target.parts
                or member.uid != 0
                or member.gid != 0
                or member.mtime != 0
                or member.mode != 0o644
            ):
                raise ValueError("battle-encounters raw archive member mismatch")
        archive.extractall(output, filter="data")


def _lz77(rom: bytes, pointer: int) -> bytes:
    offset = pointer - 0x08000000
    if not 0 <= offset < len(rom) or rom[offset] != 0x10:
        raise ValueError("story visual LZ77 pointer mismatch")
    size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= size:
                break
            if flags & (1 << bit):
                pair = (rom[cursor] << 8) | rom[cursor + 1]
                cursor += 2
                length = (pair >> 12) + 3
                distance = (pair & 0x0FFF) + 1
                if distance > len(output):
                    raise ValueError("story visual LZ77 backreference mismatch")
                for _ in range(length):
                    output.append(output[-distance])
                    if len(output) >= size:
                        break
            else:
                output.append(rom[cursor])
                cursor += 1
    return bytes(output)


def _pixel_facts(left_path: Path, right_path: Path) -> dict[str, Any]:
    left_image = Image.open(left_path).convert("RGB")
    right_image = Image.open(right_path).convert("RGB")
    if left_image.size != (240, 160) or right_image.size != left_image.size:
        raise ValueError("battle-encounters PNG dimensions mismatch")
    left = left_image.tobytes()
    right = right_image.tobytes()
    bbox = ImageChops.difference(left_image, right_image).getbbox()
    return {
        "width": 240,
        "height": 160,
        "changed_pixel_count": sum(
            left[index : index + 3] != right[index : index + 3]
            for index in range(0, len(left), 3)
        ),
        "bbox_inclusive": None
        if bbox is None
        else [bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1],
        "baseline_rgb_sha256": _sha256(left),
        "candidate_rgb_sha256": _sha256(right),
    }


def _verify_regions(states: dict[str, Any]) -> dict[str, dict[str, Any]]:
    regions = (
        ("IO", 0x04000000, 0x400),
        ("PRAM", 0x05000000, 0x400),
        ("VRAM", 0x06000000, 0x18000),
        ("OAM", 0x07000000, 0x400),
        ("IWRAM", 0x03000000, 0x8000),
        ("EWRAM", 0x02000000, 0x40000),
    )
    result = {}
    for name, address, size in regions:
        left = states["baseline"].read_memory(address, size)
        right = states["candidate"].read_memory(address, size)
        indices = [
            index
            for index, pair in enumerate(zip(left, right, strict=True))
            if pair[0] != pair[1]
        ]
        actual = (
            len(indices),
            _sha256(b"".join(index.to_bytes(4, "little") for index in indices)),
            _sha256(left),
            _sha256(right),
            None if not indices else (indices[0], indices[-1]),
        )
        if actual != EXPECTED_REGIONS[name]:
            raise ValueError(f"battle-encounters {name} attribution mismatch")
        result[name] = {
            "count": actual[0],
            "index_sha256": actual[1],
            "baseline_sha256": actual[2],
            "candidate_sha256": actual[3],
        }
        if actual[4] is not None:
            result[name]["first_offset"] = actual[4][0]
            result[name]["last_offset"] = actual[4][1]
    return result


def _verify_audit(
    root: Path,
    raw: Path,
    build: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    audit = _read_json(raw / f"runs/{variant}/audit.json", f"{variant} audit")
    guard = _read_json(raw / f"runs/{variant}/guard-summary.json", f"{variant} guard")
    if (
        audit.get("schema") != "battle-encounters-story-visual-trace-v1"
        or audit.get("outcome") != "capture-complete"
        or audit.get("frame") != 205
        or audit.get("missing") != []
        or audit.get("input_state_sha256") != INPUT_SHA256
        or audit.get("script_sha256") != SCRIPT_SHA256
        or audit.get("rom_sha256") != build["variants"][variant]["rom_sha256"]
    ):
        raise ValueError(f"battle-encounters {variant} audit mismatch")
    events = audit.get("events")
    names = [row.get("name") for row in events] if isinstance(events, list) else []
    expected_names = [
        "chapter-opcode-14",
        "story-state-dispatch",
        "story-wrapper",
        "story-loader",
        "descriptor-0-select",
        "gfx-decompress",
        "palette-decompress",
        "tilemap-decompress",
        "overlay-first-vblank",
    ]
    if names != expected_names:
        raise ValueError(f"battle-encounters {variant} event chain mismatch")
    indexed = {row["name"]: row for row in events}
    expected_gfx = "0x0812FF50" if variant == "baseline" else "0x081303E8"
    if (
        indexed["chapter-opcode-14"].get("r7") != "0x08049E63"
        or indexed["story-state-dispatch"].get("story_state") != "0x8000"
        or indexed["story-wrapper"].get("lr") != "0x0808FA31"
        or indexed["story-loader"].get("lr") != "0x0808A6A3"
        or indexed["descriptor-0-select"].get("r0") != "0x0854229C"
        or indexed["gfx-decompress"].get("r0") != expected_gfx
        or indexed["gfx-decompress"].get("r1") != "0x0600E800"
        or indexed["palette-decompress"].get("r0") != "0x08130268"
        or indexed["palette-decompress"].get("r1") != "0x050001E0"
        or indexed["tilemap-decompress"].get("r0") != "0x08130290"
        or indexed["tilemap-decompress"].get("r1") != "0x06001800"
        or indexed["overlay-first-vblank"].get("frame") != 198
    ):
        raise ValueError(f"battle-encounters {variant} runtime event mismatch")
    command = guard.get("command")
    if (
        guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("completion_trigger") != "success-marker"
        or guard.get("degraded") is not False
        or not isinstance(guard.get("peak_tree_rss_mib"), (int, float))
        or guard["peak_tree_rss_mib"] > 512
        or not isinstance(command, list)
        or len(command) != 4
        or Path(command[0]).name != "mGBA"
        or command[1] != "--script"
        or Path(command[2]).name != SCRIPT_RELATIVE.name
        or not command[3].endswith(f"/build/{variant}/{variant}.gba")
    ):
        raise ValueError(f"battle-encounters {variant} guard mismatch")
    return {
        "rom_sha256": audit["rom_sha256"],
        "audit_sha256": _sha256_file(raw / f"runs/{variant}/audit.json"),
        "guard_sha256": _sha256_file(raw / f"runs/{variant}/guard-summary.json"),
        "state_sha256": _sha256_file(raw / f"runs/{variant}/final.ss9"),
        "png_sha256": _sha256_file(raw / f"runs/{variant}/final.png"),
        "peak_tree_rss_mib": guard["peak_tree_rss_mib"],
        "pgid_clean": True,
    }


def _verify_launch_identity(raw: Path) -> None:
    guards = {}
    for variant in ("baseline", "candidate"):
        path = raw / f"runs/{variant}/guard-summary.json"
        guard = _read_json(path, f"{variant} guard")
        command = guard.get("command")
        if not isinstance(command, list) or len(command) != 4:
            raise ValueError("battle-encounters launch identity command mismatch")
        guards[variant] = {
            "guard_sha256": _sha256_file(path),
            "binary_command_path_sha256": _sha256(command[0].encode("utf-8")),
            "script_command_path_sha256": _sha256(command[2].encode("utf-8")),
        }
    expected = {
        "schema": "battle-encounters-launch-identity-v1",
        "binary": {
            "basename": "mGBA",
            "sha256": BINARY_SHA256,
            "source_commit": "c16c3ff55585e71bee83c95539c2ecde15d728c8",
        },
        "script": {
            "repository_path": SCRIPT_RELATIVE.as_posix(),
            "sha256": SCRIPT_SHA256,
        },
        "guards": guards,
    }
    if _read_json(raw / "launch-identity.json", "launch identity") != expected:
        raise ValueError("battle-encounters launch identity mismatch")


def verify_artifact(
    root: Path,
    artifact: Path,
    binary_path: Path | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    artifact = Path(artifact).resolve(strict=True)
    if {path.name for path in artifact.iterdir() if path.is_file()} != {
        "baseline.png",
        "candidate.png",
        "evidence.json",
        "manifest.json",
        "raw.tar",
    }:
        raise ValueError("battle-encounters artifact file set mismatch")
    manifest = _read_json(artifact / "manifest.json", "manifest")
    evidence = _read_json(artifact / "evidence.json", "evidence")
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_schema")
        != "battle-encounters-story-visual-pixel-ab-artifact-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("verifier", {}).get("command")
        != [
            "python3",
            "tools/verify_battle_encounters_story_visual_pixel_ab.py",
            "--root",
            ".",
            "--artifact",
            "artifacts/battle-encounters-story-visual-pixel-ab-v1",
        ]
        or manifest.get("verifier", {}).get("exit_code") != 0
    ):
        raise ValueError("battle-encounters manifest contract mismatch")
    for name in ("baseline.png", "candidate.png", "evidence.json", "raw.tar"):
        if manifest.get("files", {}).get(name) != _sha256_file(artifact / name):
            raise ValueError(f"battle-encounters artifact hash mismatch: {name}")
    implementation = manifest.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != IMPLEMENTATION_FILES:
        raise ValueError("battle-encounters implementation file set mismatch")
    for name, expected in implementation.items():
        path = root / name
        if not path.is_file() or _sha256_file(path) != expected:
            raise ValueError(f"battle-encounters implementation hash mismatch: {name}")
    if (
        evidence.get("schema")
        != "battle-encounters-story-visual-pixel-ab-evidence-v1"
        or evidence.get("verified") is not True
        or evidence.get("actual_identity") != "24 story visual descriptors"
    ):
        raise ValueError("battle-encounters evidence contract mismatch")
    expected_emulator = {
        "source_commit": "c16c3ff55585e71bee83c95539c2ecde15d728c8",
        "binary_sha256": BINARY_SHA256,
        "launch_identity": "raw.tar:launch-identity.json",
        "script_path": SCRIPT_RELATIVE.as_posix(),
        "script_sha256": SCRIPT_SHA256,
    }
    if evidence.get("emulator") != expected_emulator:
        raise ValueError("battle-encounters emulator identity mismatch")
    edit = evidence.get("edit")
    if (
        not isinstance(edit, dict)
        or edit.get("record_id") != 0
        or edit.get("field") != "gfx_lz_ptr"
        or edit.get("rom_offset") != PATCH_OFFSET
        or edit.get("before_pointer") != "0x0812FF50"
        or edit.get("after_pointer") != "0x081303E8"
        or edit.get("changed_rom_offsets")
        != [PATCH_OFFSET, PATCH_OFFSET + 1, PATCH_OFFSET + 2]
    ):
        raise ValueError("battle-encounters edit contract mismatch")
    if (
        _sha256_file(root / SCRIPT_RELATIVE) != SCRIPT_SHA256
    ):
        raise ValueError("battle-encounters current runtime tool mismatch")
    if binary_path is not None:
        binary_path = Path(binary_path).resolve(strict=True)
        if not binary_path.is_file() or _sha256_file(binary_path) != BINARY_SHA256:
            raise ValueError("battle-encounters supplied emulator binary mismatch")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != BASE_SHA256:
        raise ValueError("battle-encounters base ROM mismatch")
    before = struct.pack("<I", BEFORE_POINTER)
    after = struct.pack("<I", AFTER_POINTER)
    if base[PATCH_OFFSET : PATCH_OFFSET + 4] != before:
        raise ValueError("battle-encounters source pointer mismatch")
    candidate_buffer = bytearray(base)
    candidate_buffer[PATCH_OFFSET : PATCH_OFFSET + 4] = after
    candidate = bytes(candidate_buffer)
    changed = [
        index
        for index, pair in enumerate(zip(base, candidate, strict=True))
        if pair[0] != pair[1]
    ]
    if changed != [PATCH_OFFSET, PATCH_OFFSET + 1, PATCH_OFFSET + 2]:
        raise ValueError("battle-encounters reconstructed ROM mismatch")

    parent = root / PARENT_PATH
    if _sha256_file(parent) != PARENT_SHA256:
        raise ValueError("battle-encounters parent checkpoint mismatch")
    reconstructed_fixture = patch_savestate(
        parent.read_bytes(),
        [(0x030011F0, struct.pack("<I", 0x08049E63))],
    )
    if _sha256(reconstructed_fixture) != INPUT_SHA256:
        raise ValueError("battle-encounters reconstructed fixture mismatch")
    canonical = root / CANONICAL_PATH
    if (
        _sha256_file(canonical) != INPUT_SHA256
        or canonical.read_bytes() != reconstructed_fixture
    ):
        raise ValueError("battle-encounters canonical checkpoint mismatch")

    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory) / "raw"
        raw.mkdir()
        _extract_raw(artifact / "raw.tar", raw)
        _verify_launch_identity(raw)
        fixture = raw / "input/controlled-story-opcode.ss9"
        if fixture.read_bytes() != reconstructed_fixture:
            raise ValueError("battle-encounters raw fixture mismatch")
        build = _read_json(raw / "build/build-manifest.json", "raw build")
        if (
            build.get("schema")
            != "battle-encounters-story-visual-pixel-ab-build-v1"
            or build.get("source_rom_sha256") != BASE_SHA256
            or build.get("input_state_sha256") != INPUT_SHA256
            or build.get("controlled_entry", {}).get("canonical_checkpoint")
            != CANONICAL_PATH.as_posix()
            or build.get("controlled_entry", {}).get("canonical_checkpoint_sha256")
            != INPUT_SHA256
            or build.get("edit") != edit
            or build.get("variants", {}).get("baseline", {}).get("rom_sha256")
            != BASE_SHA256
            or build.get("variants", {}).get("candidate", {}).get("rom_sha256")
            != _sha256(candidate)
        ):
            raise ValueError("battle-encounters raw build mismatch")
        states = {}
        runs = {}
        for variant in ("baseline", "candidate"):
            runs[variant] = _verify_audit(root, raw, build, variant)
            state_path = raw / f"runs/{variant}/final.ss9"
            png_path = raw / f"runs/{variant}/final.png"
            state = load_gba_state(state_path)
            with Image.open(png_path) as screenshot:
                screenshot_rgb = screenshot.convert("RGB").tobytes()
            if render_checkpoint(state_path)[0] != screenshot_rgb:
                raise ValueError(f"battle-encounters {variant} screenshot mismatch")
            if (artifact / f"{variant}.png").read_bytes() != png_path.read_bytes():
                raise ValueError(f"battle-encounters promoted {variant} PNG mismatch")
            states[variant] = state
        region_facts = _verify_regions(states)
        pixels = _pixel_facts(
            raw / "runs/baseline/final.png", raw / "runs/candidate/final.png"
        )
        if pixels != EXPECTED_PIXELS:
            raise ValueError("battle-encounters pixel contract mismatch")
        if evidence.get("pixels", {}).get("changed_pixel_count") != 1603:
            raise ValueError("battle-encounters evidence pixel mismatch")
        if evidence.get("memory_differences", {}).get("VRAM", {}).get("count") != 2348:
            raise ValueError("battle-encounters evidence memory mismatch")

        baseline_gfx = _lz77(base, BEFORE_POINTER)
        candidate_gfx = _lz77(base, AFTER_POINTER)
        palette = _lz77(base, 0x08130268)
        tilemap = _lz77(base, 0x08130290)
        if (
            len(baseline_gfx) != 1248
            or len(candidate_gfx) != 3552
            or states["baseline"].read_memory(0x0600E800, len(baseline_gfx))
            != baseline_gfx
            or states["candidate"].read_memory(0x0600E800, len(candidate_gfx))
            != candidate_gfx
            or palette != states["baseline"].read_memory(0x050001E0, 32)
            or palette != states["candidate"].read_memory(0x050001E0, 32)
            or tilemap != states["baseline"].read_memory(0x06001800, 2048)
            or tilemap != states["candidate"].read_memory(0x06001800, 2048)
        ):
            raise ValueError("battle-encounters runtime resource materialization mismatch")

        expected_evidence = {
            "schema": "battle-encounters-story-visual-pixel-ab-evidence-v1",
            "verified": True,
            "historical_slug": "battle-encounters",
            "actual_identity": "24 story visual descriptors",
            "controlled_entry": build["controlled_entry"],
            "input_state": {
                "path": "raw.tar:input/controlled-story-opcode.ss9",
                "sha256": INPUT_SHA256,
                "canonical_path": CANONICAL_PATH.as_posix(),
                "parent_path": PARENT_PATH.as_posix(),
                "parent_sha256": PARENT_SHA256,
                "state_difference_offsets": [106992, 106993, 106994],
            },
            "emulator": expected_emulator,
            "edit": build["edit"],
            "runs": runs,
            "memory_differences": region_facts,
            "pixels": pixels,
            "runtime_chain": [
                "0x08049E63: opcode 0x14 state 0x0168",
                "0x0808FA2C story-state dispatch",
                "0x0808A69C story wrapper",
                "0x08087C9C story loader",
                "0x0854229C descriptor 0",
                "0x0809C0E8 three LZ77 streams",
                "BG3 visible frame",
            ],
            "boundary": build["boundary"],
        }
        if evidence != expected_evidence:
            raise ValueError("battle-encounters evidence mismatch")

    return {
        "schema": "battle-encounters-story-visual-pixel-ab-verification-v1",
        "verified": True,
        "changed_pixel_count": EXPECTED_PIXELS["changed_pixel_count"],
        "bbox_inclusive": EXPECTED_PIXELS["bbox_inclusive"],
        "memory_differences": region_facts,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument(
        "--binary",
        type=Path,
        help="optional local mGBA binary; when supplied its SHA-256 is verified",
    )
    args = parser.parse_args(argv)
    result = verify_artifact(args.root, args.artifact, args.binary)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
