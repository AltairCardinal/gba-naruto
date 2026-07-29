#!/usr/bin/env python3
"""Verify the character FBFF/FFFF renderer A/B artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from PIL import Image


BASE_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
CONTROL_ROM_SHA256 = (
    "3f55e607829db4497a1f49200514777c89df01f3624fd849005b96247502507a"
)
SOURCE_STATE_SHA256 = (
    "60028c26e1a529c9542b1e9644dcd35d341cfcfe593cde1b3359c1e2817e3c93"
)
GENERATED_STATE_SHA256 = (
    "6430971b14eb084da468c8db9019ec6c9d5534d632b4f5effa616f25dfff7ce5"
)
PATCH_OFFSET = 0x25A8E5
TASK_SHA256 = (
    "c091d31ceea2a97cbcf2b6aa34049ca5612e6730903eaa11d3ff0d378736fc21"
)
BASE_TRACE = [
    ("0x0825A8E4", "0xFBFF", -1025),
    ("0x0825A8F8", "0x00FF", 255),
    ("0x0825A90C", "0x0100", 256),
    ("0x0825A920", "0xA8D0", -22320),
]
CONTROL_TRACE = [
    ("0x0825A8E4", "0xFFFF", -1),
    ("0x0825A8E4", "0xFFFF", -1),
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _trace_tuples(trace: dict[str, Any]) -> list[tuple[str, str, int]]:
    return [
        (item["pointer"], item["raw_u16"], item["signed_value"])
        for item in trace.get("hits", [])
    ]


def verify(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        manifest = _load_json(artifact_dir / "manifest.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {
            "schema": "character-fbff-runtime-verification-v1",
            "success": False,
            "errors": [f"manifest: {error}"],
            "base_outcome": None,
            "control_outcome": None,
        }

    _expect(
        manifest.get("schema") == "character-fbff-runtime-v1",
        "manifest schema mismatch",
        errors,
    )

    rom_path = root / "rom" / "base.gba"
    source_state_path = (
        root
        / "artifacts"
        / "battle-effect-affine-runtime-v1"
        / "raw"
        / "state-0154.ss9"
    )
    script_path = root / "tools" / "mgba_character_fbff_probe.lua"
    try:
        rom = rom_path.read_bytes()
        source_state = source_state_path.read_bytes()
        script = script_path.read_bytes()
    except OSError as error:
        errors.append(f"source input: {error}")
        rom = b""
        source_state = b""
        script = b""

    _expect(_sha256(rom) == BASE_ROM_SHA256, "base ROM hash mismatch", errors)
    _expect(
        _sha256(source_state) == SOURCE_STATE_SHA256,
        "source state hash mismatch",
        errors,
    )
    _expect(
        _sha256(script) == manifest.get("probe_script", {}).get("sha256"),
        "probe script hash mismatch",
        errors,
    )
    if len(rom) > PATCH_OFFSET + 2:
        _expect(
            rom[PATCH_OFFSET - 1 : PATCH_OFFSET + 3] == bytes.fromhex("fffb0000"),
            "base ROM FBFF source bytes mismatch",
            errors,
        )
        control = bytearray(rom)
        control[PATCH_OFFSET] = 0xFF
        _expect(
            _sha256(bytes(control)) == CONTROL_ROM_SHA256,
            "one-byte control ROM hash mismatch",
            errors,
        )
        _expect(
            _sha256(rom[0x629FC:0x62A0A])
            == "1eec74c4d5fbbe612ea235443537b5f670eb656f460b623059ad4bdb6adda3fa",
            "renderer initial comparison hash mismatch",
            errors,
        )
        _expect(
            _sha256(rom[0x631F6:0x63214])
            == "139cfdb1b42f080558791e74aab2d726cfb36e703555991b437065e744b32af7",
            "renderer loop comparison hash mismatch",
            errors,
        )

    _expect(
        manifest.get("base_rom", {}).get("sha256") == BASE_ROM_SHA256,
        "manifest base ROM hash mismatch",
        errors,
    )
    _expect(
        manifest.get("control_rom", {}).get("sha256") == CONTROL_ROM_SHA256,
        "manifest control ROM hash mismatch",
        errors,
    )
    _expect(
        manifest.get("probe_input", {}).get("source_state_sha256")
        == SOURCE_STATE_SHA256,
        "manifest source state hash mismatch",
        errors,
    )
    _expect(
        manifest.get("probe_input", {}).get("generated_state_sha256")
        == GENERATED_STATE_SHA256,
        "manifest generated state hash mismatch",
        errors,
    )

    expected_files = {
        **manifest.get("base_run", {}).get("files", {}),
        **manifest.get("control_run", {}).get("files", {}),
    }
    actual_files = {
        path.relative_to(artifact_dir).as_posix()
        for path in artifact_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    _expect(
        actual_files == set(expected_files),
        "artifact file inventory mismatch",
        errors,
    )
    for relative, expected_hash in sorted(expected_files.items()):
        path = artifact_dir / relative
        try:
            actual_hash = _sha256(path.read_bytes())
        except OSError as error:
            errors.append(f"{relative}: {error}")
            continue
        label = (
            "base renderer trace"
            if relative == "base/renderer-loop.json"
            else relative
        )
        _expect(actual_hash == expected_hash, f"{label} hash mismatch", errors)

    try:
        base_audit = _load_json(artifact_dir / "base" / "audit.json")
        base_trace = _load_json(artifact_dir / "base" / "renderer-loop.json")
        base_guard = _load_json(artifact_dir / "base" / "guard.json")
        control_audit = _load_json(artifact_dir / "control" / "audit.json")
        control_trace = _load_json(artifact_dir / "control" / "renderer-loop.json")
        control_guard = _load_json(artifact_dir / "control" / "guard.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"runtime JSON: {error}")
        base_audit = {}
        base_trace = {}
        base_guard = {}
        control_audit = {}
        control_trace = {}
        control_guard = {}

    _expect(base_audit.get("success") is True, "base audit is not successful", errors)
    _expect(
        base_audit.get("outcome") == "renderer_continues_past_fbff",
        "base outcome mismatch",
        errors,
    )
    _expect(
        base_audit.get("rom_sha256") == BASE_ROM_SHA256,
        "base audit ROM hash mismatch",
        errors,
    )
    _expect(
        base_audit.get("input_state_sha256") == GENERATED_STATE_SHA256,
        "base audit input hash mismatch",
        errors,
    )
    _expect(
        base_audit.get("addresses_advance_by_component") is True,
        "base renderer did not advance by 20-byte components",
        errors,
    )
    _expect(
        base_trace.get("renderer_loop_address") == "0x080631FE"
        and _trace_tuples(base_trace) == BASE_TRACE,
        "base renderer trace semantics mismatch",
        errors,
    )
    _expect(
        base_guard.get("reason") == "completed"
        and base_guard.get("exit_code") == 0
        and base_guard.get("degraded") is False
        and base_guard.get("completion_trigger") == "success-marker",
        "base guard result mismatch",
        errors,
    )
    _expect(
        str(base_guard.get("command", [""])[-1]).endswith("/rom/base.gba"),
        "base guard ROM command mismatch",
        errors,
    )

    _expect(
        control_audit.get("success") is True,
        "control audit is not successful",
        errors,
    )
    _expect(
        control_audit.get("outcome") == "renderer_stops_at_ffff",
        "control outcome mismatch",
        errors,
    )
    _expect(
        control_audit.get("rom_sha256") == CONTROL_ROM_SHA256,
        "control audit ROM hash mismatch",
        errors,
    )
    _expect(
        control_audit.get("input_state_sha256") == GENERATED_STATE_SHA256,
        "control audit input hash mismatch",
        errors,
    )
    _expect(
        control_audit.get("valid_component_count") == 1
        and control_audit.get("first_pseudo_component_count") == 0,
        "control OAM component counts mismatch",
        errors,
    )
    _expect(
        control_trace.get("renderer_loop_address") == "0x080631FE"
        and _trace_tuples(control_trace) == CONTROL_TRACE,
        "control renderer trace semantics mismatch",
        errors,
    )
    _expect(
        control_guard.get("reason") == "completed"
        and control_guard.get("exit_code") == 0
        and control_guard.get("degraded") is False
        and control_guard.get("completion_trigger") == "success-marker",
        "control guard result mismatch",
        errors,
    )
    _expect(
        str(control_guard.get("command", [""])[-1]).endswith("/control.gba"),
        "control guard ROM command mismatch",
        errors,
    )

    try:
        base_task_before = (artifact_dir / "base" / "task-before.bin").read_bytes()
        base_task_after = (artifact_dir / "base" / "task-after.bin").read_bytes()
        control_task_before = (
            artifact_dir / "control" / "task-before.bin"
        ).read_bytes()
        control_oam = (artifact_dir / "control" / "oam.bin").read_bytes()
        with Image.open(artifact_dir / "control" / "frame.png") as image:
            image.load()
            image_size = image.size
    except (OSError, ValueError) as error:
        errors.append(f"runtime binary: {error}")
        base_task_before = b""
        base_task_after = b""
        control_task_before = b""
        control_oam = b""
        image_size = None

    _expect(
        len(base_task_before) == 60
        and _sha256(base_task_before) == TASK_SHA256
        and base_task_before == base_task_after
        and base_task_before == control_task_before,
        "probe task A/B identity mismatch",
        errors,
    )
    if len(control_oam) == 0x400:
        attr0, attr1, attr2 = struct.unpack_from("<HHH", control_oam, 0)
        _expect(
            (attr0, attr1, attr2) == (0x8438, 0xC068, 0xE340),
            "control OAM entry 0 mismatch",
            errors,
        )
    else:
        errors.append("control OAM size mismatch")
    _expect(image_size == (240, 160), "control screenshot size mismatch", errors)

    conclusion = manifest.get("conclusion", {})
    _expect(
        conclusion.get("runtime_semantics") == "not_a_terminator_renderer_overrun"
        and conclusion.get("source_space_render_complete") is True
        and conclusion.get("repaired_component_count") == 1,
        "manifest FBFF conclusion mismatch",
        errors,
    )

    return {
        "schema": "character-fbff-runtime-verification-v1",
        "success": not errors,
        "errors": errors,
        "base_outcome": base_audit.get("outcome"),
        "control_outcome": control_audit.get("outcome"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/character-fbff-runtime-v1"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    artifact_dir = (
        args.artifact_dir
        if args.artifact_dir.is_absolute()
        else root / args.artifact_dir
    )
    report = verify(root, artifact_dir.resolve())
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
