#!/usr/bin/env python3
"""Independently verify group 3/18 controlled direct-spawn runtime evidence."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import struct
import tarfile
import tempfile
from typing import Any

try:
    from tools.inspect_mgba_savestate import load_gba_state
    from tools.verify_battle_effect_controlled_runtime import (
        verify_artifact as verify_parent_controlled,
    )
    from tools.verify_battle_effect_group15_allocator_side_runtime import (
        verify_artifact as verify_parent_group15,
    )
except ModuleNotFoundError:
    from inspect_mgba_savestate import load_gba_state
    from verify_battle_effect_controlled_runtime import (
        verify_artifact as verify_parent_controlled,
    )
    from verify_battle_effect_group15_allocator_side_runtime import (
        verify_artifact as verify_parent_group15,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "battle-effect-direct-spawn-runtime-v1"
PHASES = ("renderer-post", "submit-post", "ack-post")
PHASE_ADDRESSES = (0x08063328, 0x08061126, 0x080612AA)
PHASE_PENDING = (0, 1, 0)
EXPECTED_BINARY_SHA256 = "c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8"
EXPECTED_MGBA_SOURCE_COMMIT = "d8bad14b4540f9114246c0281d74985cf81adc68"
NEGATIVE_RUN_INVENTORY_SHA256 = "904626b6907619ea312def094058a1a3342a1c30060cf642523270e7ffc0528f"
NEGATIVE_RUN_METADATA_SHA256 = "52b3d84668453bc30e89b4d9c3ba97296d3ac0e0c1882e3074c746e09c5e3a6a"
BASE_ROM = "rom/base.gba"
INPUT_STATE = "artifacts/runtime-checkpoints/scenario-50-battle-15-escort-12hp-player-turn.ss9"
SEQUENCE_CATALOG = "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
ANIMATION_CATALOG = "artifacts/battle-effect-sprite-animations-v1/manifest.json"
RESOURCE_CATALOG = "artifacts/battle-effect-resource-pairs-v1/manifest.json"
PARENT_CONTROLLED_ROOT = "artifacts/battle-effect-controlled-runtime-v1"
PARENT_GROUP15_ROOT = "artifacts/battle-effect-group15-allocator-side-runtime-v1"
TOOLCHAIN_PROFILE = "artifacts/rom-expansion-profile-v1/profile.json"
CAPTURE_SCRIPT = "tools/mgba_battle_effect_phase_capture.lua"
SOURCE_PATHS = {
    "base_rom": BASE_ROM,
    "input_state": INPUT_STATE,
    "sequence_catalog": SEQUENCE_CATALOG,
    "animation_catalog": ANIMATION_CATALOG,
    "resource_catalog": RESOURCE_CATALOG,
    "parent_controlled_manifest": f"{PARENT_CONTROLLED_ROOT}/manifest.json",
    "parent_group15_manifest": f"{PARENT_GROUP15_ROOT}/manifest.json",
    "toolchain_profile": TOOLCHAIN_PROFILE,
    "capture_script": CAPTURE_SCRIPT,
    "group3_graphics": "artifacts/battle-effect-resource-pairs-v1/group-03-graphics-4bpp.bin",
    "group3_palette": "artifacts/battle-effect-resource-pairs-v1/group-03-palette-bgr555.bin",
    "group18_graphics": "artifacts/battle-effect-resource-pairs-v1/group-18-graphics-4bpp.bin",
    "group18_palette": "artifacts/battle-effect-resource-pairs-v1/group-18-palette-bgr555.bin",
}
TRUSTED_SOURCE_SHA256 = {
    "base_rom": "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
    "input_state": "7d6796a767d574f5f7a91935c3c1e65ce44edbc51aa5a6b587784d4730bbe94f",
    "sequence_catalog": "ec8f41571bb132577ecb7bc57f946a85f219b4c05f3697c89b75be73385b0c73",
    "animation_catalog": "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848",
    "resource_catalog": "716ac580326077127797c634d1f19bbc0aadcfd4db9c577730728b112f002963",
    "parent_controlled_manifest": "ad1baabd5a972e1ef342b80a060084fb450e781b011128c4f7ccd89b5e10825b",
    "parent_group15_manifest": "c890b1bc395ea038fd439f3249686d429bdc75ef2c39c77483856c591763d289",
    "toolchain_profile": "e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287",
    "capture_script": "013b5eda11c067401873e39c068269462ed132cbd968c337c062ef45a00422e5",
    "group3_graphics": "eb9589427babaaa4d746b365cf1ea3083a5accd5cc408d53ac9c83131fb82475",
    "group3_palette": "c0e21753834c2ca38588891ecf78596fa7234012bb0c1a3f69ceb2ccc7619f95",
    "group18_graphics": "9162bda2e90536bbe5982e94b4d4de9b18111538b548137ca057701d36b7bc55",
    "group18_palette": "d53a7a56bded0b6727002a3fb4ad69454dccee15e8f849ad3a16c3b5639244c1",
}
REPOSITORY_FILES = (
    "tools/build_controlled_battle_effect_direct_spawn_probe.py",
    "tools/run_battle_effect_direct_spawn_batch.py",
    "tools/export_battle_effect_direct_spawn_runtime.py",
    "tools/verify_battle_effect_direct_spawn_runtime.py",
    "tools/verify_battle_effect_controlled_runtime.py",
    "tools/verify_battle_effect_group15_allocator_side_runtime.py",
    "tools/run_macos_mgba_battle_effect_phase_capture.py",
    "tools/run_macos_mgba_input_sequence.py",
    "tools/run_macos_mgba_replay.py",
    "tools/run_macos_mgba_single_input.py",
    "tools/mgba_battle_effect_phase_capture.lua",
    "tools/macos_mgba_runtime_residue.py",
    "tools/run_guarded.py",
    "tools/mgba_runtime_safety.py",
    "tools/project_resource_guard.py",
    "tools/inspect_mgba_savestate.py",
    "tools/build_save_state_runtime_probe.py",
    "tools/thumb_branch.py",
    "tests/test_build_controlled_battle_effect_direct_spawn_probe.py",
    "tests/test_run_battle_effect_direct_spawn_batch.py",
    "tests/test_export_battle_effect_direct_spawn_runtime.py",
    "tests/test_verify_battle_effect_direct_spawn_runtime.py",
)
TASK_BASE = 0x03003BB8
TASK_SIZE = 0x3C
TASK_COUNT = 128
ACTIVE_COUNT = 0x03005BB8
ACTIVE_POINTERS = 0x030059B8
SHADOW_OAM = 0x0300027C
HARDWARE_OAM = 0x07000000
PENDING = 0x0300067C
OBJ_VRAM = 0x06010000
OBJ_PRAM = 0x05000200
SCRATCH = 0x0203FF40
ROM_BASE = 0x08000000
HOOK = 0x08061F76
SOUND_MAIN = 0x0809AAB4
RESET = 0x0807FDCC
SELECTOR = 0x0807FE2C
SPAWN_NO_SIDE = 0x080800A4
SPAWN_SIDE = 0x08080108
STUB = 0x0809E800
STUB_SIZE = 64
NEGATIVE_CASE_ID = "group-03-sequence-03-direct-spawn"


CASE_ROWS = (
    {
        "case_id": "group-03-sequence-03-side-0-direct-spawn",
        "group_id": 3,
        "sequence_id": 3,
        "side": 0,
        "spawn_function": SPAWN_SIDE,
        "spawn_x": 104,
        "spawn_y": 80,
        "tile_start": 0x100,
        "tile_end": 0x39F,
        "palette_start": 4,
        "palette_end": 14,
    },
    {
        "case_id": "group-03-sequence-03-side-1-direct-spawn",
        "group_id": 3,
        "sequence_id": 3,
        "side": 1,
        "spawn_function": SPAWN_SIDE,
        "spawn_x": 104,
        "spawn_y": 80,
        "tile_start": 0x100,
        "tile_end": 0x39F,
        "palette_start": 4,
        "palette_end": 14,
    },
    {
        "case_id": "group-18-sequence-07-direct-spawn",
        "group_id": 18,
        "sequence_id": 7,
        "side": None,
        "spawn_function": SPAWN_NO_SIDE,
        "spawn_x": 120,
        "spawn_y": 80,
        "tile_start": 0x300,
        "tile_end": 0x37F,
        "palette_start": 12,
        "palette_end": 14,
    },
    {
        "case_id": "group-18-sequence-18-direct-spawn",
        "group_id": 18,
        "sequence_id": 18,
        "side": None,
        "spawn_function": SPAWN_NO_SIDE,
        "spawn_x": 120,
        "spawn_y": 80,
        "tile_start": 0x300,
        "tile_end": 0x37F,
        "palette_start": 12,
        "palette_end": 14,
    },
)


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_file(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid archived {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"archived {label} must be an object")
    return value


def _canonical_tar(payloads: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(payloads.items()):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o644
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(raw))
    return stream.getvalue()


def read_safe_tar(path: Path) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    with tarfile.open(path, "r:") as archive:
        for member in archive.getmembers():
            pure = PurePosixPath(member.name)
            if (
                not member.name
                or pure.is_absolute()
                or ".." in pure.parts
                or member.name in payloads
                or not member.isfile()
                or member.linkname
                or member.pax_headers
                or member.mode != 0o644
                or member.mtime != 0
                or member.uid != 0
                or member.gid != 0
                or member.uname
                or member.gname
            ):
                raise ValueError("raw archive path, type or metadata is unsafe")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError("raw archive member cannot be read")
            payloads[member.name] = extracted.read()
    if path.read_bytes() != _canonical_tar(payloads):
        raise ValueError("raw archive is not canonical USTAR")
    return payloads


def _expected_members() -> set[str]:
    members = set()
    for case in CASE_ROWS:
        base = f"source/{case['case_id']}"
        members.add(f"{base}/batch-audit.json")
        for name in ("profile.json", "guard-summary.json", "guard-summary.json.done.json", "output/audit.json"):
            members.add(f"{base}/{name}")
        for phase in PHASES:
            members.add(f"{base}/output/{phase}/capture-phase.json")
            members.add(f"{base}/output/{phase}/capture.ss9")
    for name in (
        "profile.json",
        "guard-summary.json",
        "guard-summary.json.done.json",
        "output/audit.json",
        "output/timeout.ss9",
        "run-inventory.json",
        "run-metadata.json",
    ):
        members.add(f"source/narrow-window-negative/{name}")
    return members


def _encode_bl(callsite: int, target: int) -> bytes:
    displacement = target - (callsite + 4)
    if displacement & 1 or not -(1 << 22) <= displacement < (1 << 22):
        raise ValueError("invalid Thumb BL")
    encoded = displacement & 0x7FFFFF
    return struct.pack("<HH", 0xF000 | ((encoded >> 12) & 0x7FF), 0xF800 | ((encoded >> 1) & 0x7FF))


def _decode_bl(raw: bytes, address: int) -> int | None:
    offset = address - ROM_BASE
    first, second = struct.unpack_from("<HH", raw, offset)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return address + 4 + displacement


def _mov_shift(value: int, register: int) -> tuple[int, int]:
    for shift in range(8):
        if value % (1 << shift) == 0 and value >> shift <= 0xFF:
            return 0x2000 | (register << 8) | (value >> shift), (shift << 6) | (register << 3) | register
    raise ValueError("allocator value is not compact")


def build_expected_probe(base: bytes, case: dict[str, Any]) -> bytes:
    code = bytearray(struct.pack("<H", 0xB510))
    code.extend(_encode_bl(STUB + len(code), SOUND_MAIN))
    literal_load_offset = len(code)
    code.extend(b"\x00\x00")
    code.extend(struct.pack("<HHH", 0x6820, 0x2800, 0))
    done_branch_offset = 12
    code.extend(struct.pack("<HH", 0x2001, 0x6020))
    start_mov, start_shift = _mov_shift(case["tile_start"], 0)
    end_mov, end_shift = _mov_shift(case["tile_end"] + 1, 1)
    code.extend(struct.pack("<7H", start_mov, start_shift, end_mov, end_shift, 0x3901, 0x2200 | case["palette_start"], 0x2300 | case["palette_end"]))
    code.extend(_encode_bl(STUB + len(code), RESET))
    code.extend(struct.pack("<H", 0x2000 | case["sequence_id"]))
    code.extend(_encode_bl(STUB + len(code), SELECTOR))
    code.extend(struct.pack("<H", 0x6060))
    if case["spawn_function"] == SPAWN_SIDE:
        args = (0x2100 | case["side"], 0x2200 | case["spawn_x"], 0x2300 | case["spawn_y"])
    else:
        args = (0x2100 | case["spawn_x"], 0x2200 | case["spawn_y"], 0x46C0)
    code.extend(struct.pack("<3H", *args))
    code.extend(_encode_bl(STUB + len(code), case["spawn_function"]))
    done_offset = len(code)
    code.extend(struct.pack("<HHH", 0xBC10, 0xBC01, 0x4700))
    while len(code) % 4:
        code.extend(struct.pack("<H", 0x46C0))
    literal_offset = len(code)
    code.extend(struct.pack("<I", SCRATCH))
    code.extend(bytes(STUB_SIZE - len(code)))
    pc_base = (STUB + literal_load_offset + 4) & ~3
    struct.pack_into("<H", code, literal_load_offset, 0x4C00 | ((STUB + literal_offset - pc_base) // 4))
    displacement = done_offset - (done_branch_offset + 4)
    struct.pack_into("<H", code, done_branch_offset, 0xD100 | ((displacement // 2) & 0xFF))
    output = bytearray(base)
    output[HOOK - ROM_BASE:HOOK - ROM_BASE + 4] = _encode_bl(HOOK, STUB)
    output[STUB - ROM_BASE:STUB - ROM_BASE + STUB_SIZE] = code
    return bytes(output)


def _verify_static_contract(base: bytes) -> None:
    # group 3 selects sequences 5 then 3 and spawns for sides 0 and 1.
    if _decode_bl(base, 0x0807F20E) != SELECTOR or _decode_bl(base, 0x0807F21C) != SELECTOR:
        raise ValueError("group 3 natural selector contract mismatch")
    if struct.unpack_from("<H", base, 0x0807F20C - ROM_BASE)[0] != 0x2005 or struct.unpack_from("<H", base, 0x0807F21A - ROM_BASE)[0] != 0x2003:
        raise ValueError("group 3 natural sequence immediates mismatch")
    if _decode_bl(base, 0x0807F274) != SPAWN_SIDE:
        raise ValueError("group 3 natural spawn call mismatch")
    for address in range(0x0807F208, 0x0807F284, 2):
        if _decode_bl(base, address) == RESET:
            raise ValueError("group 3 direct function unexpectedly resets allocator")
    # Three nearby battle-effect subsystem reset sites use the 0x100..0x39F/4..14 window.
    for callsite, literal_address in ((0x0807F5D0, 0x0807F690), (0x0807F8EC, 0x0807FA28), (0x0807FD14, 0x0807FD7C)):
        if _decode_bl(base, callsite) != RESET or struct.unpack_from("<I", base, literal_address - ROM_BASE)[0] != 0x39F:
            raise ValueError("wide battle-effect allocator evidence mismatch")
    # group 18 sequence 7 and sequence 18 paths use the narrow natural reset.
    for reset_call, selector_call, sequence, spawn_call in (
        (0x08081BD4, 0x08081BDA, 7, 0x08081BF4),
        (0x0806C5B4, 0x0806C5BA, 18, 0x0806C5D8),
    ):
        if _decode_bl(base, reset_call) != RESET or _decode_bl(base, selector_call) != SELECTOR or _decode_bl(base, spawn_call) != SPAWN_NO_SIDE:
            raise ValueError("group 18 natural direct-entry call chain mismatch")
        if struct.unpack_from("<H", base, selector_call - ROM_BASE - 2)[0] != 0x2000 | sequence:
            raise ValueError("group 18 natural sequence immediate mismatch")


def _state(raw: bytes, temporary: Path, name: str) -> Any:
    path = temporary / name
    path.write_bytes(raw)
    return load_gba_state(path)


def _target_tasks(state: Any, definition: int, animation: int) -> list[dict[str, Any]]:
    rows = []
    for slot in range(TASK_COUNT):
        raw = state.read_memory(TASK_BASE + slot * TASK_SIZE, TASK_SIZE)
        flags = struct.unpack_from("<I", raw)[0]
        if flags & 1 and struct.unpack_from("<II", raw, 0x1C) == (definition, animation):
            rows.append({
                "slot": slot,
                "flags": f"0x{flags:08X}",
                "anchor_x": struct.unpack_from("<h", raw, 4)[0],
                "anchor_y": struct.unpack_from("<h", raw, 6)[0],
                "tile_base": struct.unpack_from("<H", raw, 0x10)[0],
                "palette_bank": raw[0x12],
                "definition_pointer": f"0x{definition:08X}",
                "animation_pointer": f"0x{animation:08X}",
            })
    return rows


def _active_slots(state: Any) -> list[int]:
    count = state.read_memory(ACTIVE_COUNT, 1)[0]
    pointers = struct.unpack(f"<{count}I", state.read_memory(ACTIVE_POINTERS, count * 4))
    slots = []
    for pointer in pointers:
        delta = pointer - TASK_BASE
        if delta < 0 or delta % TASK_SIZE or delta // TASK_SIZE >= TASK_COUNT:
            raise ValueError("active task pointer mismatch")
        slots.append(delta // TASK_SIZE)
    return slots


def _source_records(evidence: dict[str, Any]) -> None:
    if set(evidence.get("sources", {})) != set(SOURCE_PATHS):
        raise ValueError("source record denominator mismatch")
    for name, relative in SOURCE_PATHS.items():
        path = ROOT / relative
        record = evidence["sources"][name]
        actual = _sha256(path)
        if actual != TRUSTED_SOURCE_SHA256[name]:
            raise ValueError(f"trusted source hash mismatch: {name}")
        if record != {"path": relative, "sha256": actual, "size": path.stat().st_size}:
            raise ValueError(f"source record mismatch: {name}")


def _verify_negative_run_inventory(
    payloads: dict[str, bytes], narrow_rom_sha: str
) -> None:
    prefix = "source/narrow-window-negative"
    inventory_raw = payloads[f"{prefix}/run-inventory.json"]
    metadata_raw = payloads[f"{prefix}/run-metadata.json"]
    if (
        _sha256_bytes(inventory_raw) != NEGATIVE_RUN_INVENTORY_SHA256
        or _sha256_bytes(metadata_raw) != NEGATIVE_RUN_METADATA_SHA256
    ):
        raise ValueError("narrow-window negative run ledger hash mismatch")
    inventory = _json_bytes(inventory_raw, "negative run inventory")
    metadata = _json_bytes(metadata_raw, "negative run metadata")
    files = inventory.get("files")
    if (
        inventory.get("schema") != "experiment-inventory-v1"
        or inventory.get("file_count") != 15
        or not isinstance(files, dict)
        or len(files) != 15
        or inventory.get("byte_count")
        != sum(row.get("size", -1) for row in files.values() if isinstance(row, dict))
        or metadata.get("schema") != "experiment-workspace-v1"
        or metadata.get("task") != "battle-effect-direct-spawn"
        or metadata.get("run_id") != "20260801-02"
        or metadata.get("status") != "completed"
        or metadata.get("inventory")
        != {
            "file_count": inventory["file_count"],
            "byte_count": inventory["byte_count"],
            "sha256": NEGATIVE_RUN_INVENTORY_SHA256,
        }
    ):
        raise ValueError("narrow-window negative run ledger mismatch")
    original_prefix = f"output/{NEGATIVE_CASE_ID}"
    selected = {
        f"{prefix}/profile.json": f"{original_prefix}/profile.json",
        f"{prefix}/guard-summary.json": f"{original_prefix}/guard-summary.json",
        f"{prefix}/guard-summary.json.done.json": f"{original_prefix}/guard-summary.json.done.json",
        f"{prefix}/output/audit.json": f"{original_prefix}/output/audit.json",
        f"{prefix}/output/timeout.ss9": f"{original_prefix}/output/timeout.ss9",
    }
    for member, original in selected.items():
        raw = payloads[member]
        if files.get(original) != {
            "sha256": _sha256_bytes(raw),
            "size": len(raw),
        }:
            raise ValueError("narrow-window negative run member ledger mismatch")
    for name in ("probe.gba", "staged.gba"):
        if files.get(f"{original_prefix}/{name}") != {
            "sha256": narrow_rom_sha,
            "size": (ROOT / BASE_ROM).stat().st_size,
        }:
            raise ValueError("narrow-window negative staged ROM ledger mismatch")


def _path_has_suffix(value: Any, relative: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    normalized = value.replace("\\", "/")
    return normalized == relative or normalized.endswith(f"/{relative}")


def _verify_case(
    payloads: dict[str, bytes],
    recorded: dict[str, Any],
    case: dict[str, Any],
    animation_group: dict[str, Any],
    resource_entry: dict[str, Any],
    temporary: Path,
) -> dict[str, Any]:
    case_id = case["case_id"]
    prefix = f"source/{case_id}"
    profile = _json_bytes(payloads[f"{prefix}/profile.json"], f"{case_id} profile")
    audit = _json_bytes(payloads[f"{prefix}/output/audit.json"], f"{case_id} audit")
    guard = _json_bytes(payloads[f"{prefix}/guard-summary.json"], f"{case_id} guard")
    done = _json_bytes(payloads[f"{prefix}/guard-summary.json.done.json"], f"{case_id} done")
    batch = _json_bytes(payloads[f"{prefix}/batch-audit.json"], f"{case_id} batch")
    expected_rom = build_expected_probe((ROOT / BASE_ROM).read_bytes(), case)
    rom_sha = _sha256_bytes(expected_rom)
    expected_allocator = {
        "function": "0x0807FDCC",
        "tile_start": f"0x{case['tile_start']:04X}",
        "tile_end": f"0x{case['tile_end']:04X}",
        "palette_start": case["palette_start"],
        "palette_end": case["palette_end"],
    }
    expected_spawn = {
        "selector": "0x0807FE2C",
        "function": f"0x{case['spawn_function']:08X}",
        "side": case["side"],
        "x": case["spawn_x"],
        "y": case["spawn_y"],
    }
    profile_raw = payloads[f"{prefix}/profile.json"]
    audit_raw = payloads[f"{prefix}/output/audit.json"]
    guard_raw = payloads[f"{prefix}/guard-summary.json"]
    profile_sha = _sha256_bytes(profile_raw)
    audit_sha = _sha256_bytes(audit_raw)
    guard_sha = _sha256_bytes(guard_raw)
    batch_rows = batch.get("cases")
    expected_batch_row = {
        "case_id": case_id,
        "group_id": case["group_id"],
        "sequence_id": case["sequence_id"],
        "rom_sha256": rom_sha,
        "profile_sha256": profile_sha,
        "audit_sha256": audit_sha,
        "guard_summary_sha256": guard_sha,
    }
    toolchain = audit.get("toolchain")
    guard_command = guard.get("command")
    expected_staged_suffix = f"output/{case_id}/staged.gba"
    expected_profile_suffix = f"output/{case_id}/profile.json"
    if (
        batch.get("schema") != "battle-effect-direct-spawn-batch-audit-v1"
        or set(batch) != {
            "schema",
            "input_state",
            "input_state_sha256",
            "binary_sha256",
            "toolchain_profile",
            "toolchain_profile_sha256",
            "cases",
        }
        or batch.get("input_state") != INPUT_STATE
        or batch.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
        or batch.get("binary_sha256") != EXPECTED_BINARY_SHA256
        or batch.get("toolchain_profile") != TOOLCHAIN_PROFILE
        or batch.get("toolchain_profile_sha256") != TRUSTED_SOURCE_SHA256["toolchain_profile"]
        or not isinstance(batch_rows, list)
        or batch_rows != [expected_batch_row]
        or profile.get("schema") != "battle-effect-phase-capture-profile-v1"
        or profile.get("execution_mode") != "controlled-direct-spawn"
        or profile.get("group_id") != case["group_id"]
        or profile.get("sequence_id") != case["sequence_id"]
        or profile.get("side") != case["side"]
        or profile.get("input_mode") != "zero-input-active-state"
        or profile.get("input_state") != INPUT_STATE
        or profile.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
        or profile.get("source_runtime_evidence") != SEQUENCE_CATALOG
        or profile.get("source_runtime_evidence_sha256") != TRUSTED_SOURCE_SHA256["sequence_catalog"]
        or profile.get("timeout_frames") != 60
        or profile.get("allocator_reset") != expected_allocator
        or profile.get("spawn") != expected_spawn
        or profile.get("source_rom_sha256") != rom_sha
        or audit.get("schema") != "mgba-battle-effect-phase-capture-v1"
        or audit.get("outcome") != "three-phase-captured"
        or audit.get("group_id") != case["group_id"]
        or audit.get("input_mode") != "zero-input-active-state"
        or audit.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
        or not _path_has_suffix(audit.get("input_state"), INPUT_STATE)
        or audit.get("inputs") != []
        or audit.get("automatic_inputs") != []
        or audit.get("recovery_inputs") != []
        or audit.get("capture_frames") != 0
        or audit.get("timeout_frames") != 60
        or audit.get("rom_sha256") != rom_sha
        or audit.get("staged_rom_sha256") != rom_sha
        or not _path_has_suffix(audit.get("staged_rom"), expected_staged_suffix)
        or audit.get("binary_sha256") != EXPECTED_BINARY_SHA256
        or audit.get("profile_sha256") != profile_sha
        or not _path_has_suffix(audit.get("profile"), expected_profile_suffix)
        or audit.get("guard_summary_sha256") != guard_sha
        or audit.get("phase_script_sha256") != TRUSTED_SOURCE_SHA256["capture_script"]
        or not _path_has_suffix(audit.get("phase_script"), CAPTURE_SCRIPT)
        or toolchain != {
            "kind": "current-desktop-runtime-profile",
            "path": audit.get("toolchain", {}).get("path") if isinstance(audit.get("toolchain"), dict) else None,
            "sha256": TRUSTED_SOURCE_SHA256["toolchain_profile"],
            "source_commit": EXPECTED_MGBA_SOURCE_COMMIT,
            "patch_sha256": None,
        }
        or not _path_has_suffix(toolchain.get("path") if isinstance(toolchain, dict) else None, TOOLCHAIN_PROFILE)
        or guard.get("reason") != "completed"
        or guard.get("exit_code") != 0
        or guard.get("degraded") is not False
        or guard.get("completion_trigger") != "success-marker"
        or not isinstance(guard_command, list)
        or len(guard_command) != 4
        or Path(guard_command[0]).name != "mGBA"
        or guard_command[1] != "--script"
        or not _path_has_suffix(guard_command[2], CAPTURE_SCRIPT)
        or not _path_has_suffix(guard_command[3], expected_staged_suffix)
        or done.get("status") != "three-phase-captured"
        or done.get("phase_count") != 3
        or done.get("run_id") != audit.get("run_id")
    ):
        raise ValueError(f"runtime audit provenance mismatch: {case_id}")
    residue = audit.get("runtime_residue", {})
    if residue.get("pgid_clean") is not True or residue.get("mgba_listener_clean") is not True:
        raise ValueError(f"runtime residue mismatch: {case_id}")
    definition = int(animation_group["definition_pointer_table"], 16)
    animation = int(animation_group["animation_pointer_table"], 16)
    graphics_name = "group3_graphics" if case["group_id"] == 3 else "group18_graphics"
    palette_name = "group3_palette" if case["group_id"] == 3 else "group18_palette"
    graphics = (ROOT / SOURCE_PATHS[graphics_name]).read_bytes()
    palette = (ROOT / SOURCE_PATHS[palette_name]).read_bytes()
    phases = []
    states = []
    palette_observations = []
    previous_cycle = -1
    for index, phase in enumerate(PHASES):
        state_raw = payloads[f"{prefix}/output/{phase}/capture.ss9"]
        state = _state(state_raw, temporary, f"{case_id}-{phase}.ss9")
        meta = _json_bytes(payloads[f"{prefix}/output/{phase}/capture-phase.json"], f"{case_id} {phase}")
        address = state.registers[15] - 2
        cycle = int(meta["cycle"])
        targets = _target_tasks(state, definition, animation)
        if (
            address != PHASE_ADDRESSES[index]
            or int(meta["address"], 16) != address
            or state.read_memory(PENDING, 1)[0] != PHASE_PENDING[index]
            or cycle <= previous_cycle
            or state.read_memory(SCRATCH, 4) != b"\x01\x00\x00\x00"
            or state.read_memory(SCRATCH + 4, 1)[0] == 0xFF
            or len(targets) != 1
            or targets[0]["slot"] not in _active_slots(state)
        ):
            raise ValueError(f"runtime phase mismatch: {case_id}/{phase}")
        previous_cycle = cycle
        task = targets[0]
        if state.read_memory(OBJ_VRAM + task["tile_base"] * 32, len(graphics)) != graphics:
            raise ValueError(f"runtime graphics mismatch: {case_id}/{phase}")
        runtime_palette = state.read_memory(
            OBJ_PRAM + task["palette_bank"] * 32, len(palette)
        )
        palette_mismatches = [
            offset
            for offset, pair in enumerate(zip(runtime_palette, palette, strict=True))
            if pair[0] != pair[1]
        ]
        if case["group_id"] == 3:
            if palette_mismatches != [30, 31] or runtime_palette[:30] != palette[:30]:
                raise ValueError(f"runtime palette prefix mismatch: {case_id}/{phase}")
        elif palette_mismatches:
            raise ValueError(f"runtime palette mismatch: {case_id}/{phase}")
        palette_observations.append({
            "matched_prefix_bytes": 30 if case["group_id"] == 3 else 32,
            "mismatch_offsets": palette_mismatches,
            "runtime_tail_hex": runtime_palette[30:].hex(),
            "source_tail_hex": palette[30:].hex(),
        })
        states.append(state)
        phases.append({
            "name": phase,
            "address": f"0x{address:08X}",
            "cycle": str(cycle),
            "pending": PHASE_PENDING[index],
            "selector_result": state.read_memory(SCRATCH + 4, 1)[0],
            "target_task": task,
            "savestate_sha256": _sha256_bytes(state_raw),
        })
    renderer_shadow = states[0].read_memory(SHADOW_OAM, 0x400)
    renderer_hardware = states[0].read_memory(HARDWARE_OAM, 0x400)
    if (
        renderer_shadow == renderer_hardware
        or states[1].read_memory(HARDWARE_OAM, 0x400) != renderer_hardware
        or states[2].read_memory(HARDWARE_OAM, 0x400) != renderer_shadow
    ):
        raise ValueError(f"OAM transaction mismatch: {case_id}")
    expected_record = {
        "case_id": case_id,
        "group_id": case["group_id"],
        "sequence_id": case["sequence_id"],
        "side": case["side"],
        "allocator_reset": expected_allocator,
        "spawn": expected_spawn,
        "rom_sha256": rom_sha,
        "profile_sha256": _sha256_bytes(payloads[f"{prefix}/profile.json"]),
        "audit_sha256": _sha256_bytes(payloads[f"{prefix}/output/audit.json"]),
        "guard_summary_sha256": _sha256_bytes(payloads[f"{prefix}/guard-summary.json"]),
        "peak_tree_rss_mib_sample": guard.get("peak_tree_rss_mib"),
        "rss_sample_valid_for_statistics": bool((guard.get("peak_tree_rss_mib") or 0) >= 10),
        "phases": phases,
        "oam_transaction": {
            "renderer_shadow_differs_from_old_hardware": True,
            "submit_hardware_unchanged": True,
            "ack_hardware_equals_renderer_shadow": True,
        },
        "resource": {
            "graphics_sha256": resource_entry["graphics"]["decompressed_sha256"],
            "graphics_size": len(graphics),
            "palette_sha256": resource_entry["palette"]["decompressed_sha256"],
            "palette_size": len(palette),
            "runtime_palette_observations": palette_observations,
        },
        "probe_contract": {
            "allocator_tile_start": case["tile_start"],
            "allocator_tile_end": case["tile_end"],
            "allocator_palette_start": case["palette_start"],
            "allocator_palette_end": case["palette_end"],
            "spawn_x": case["spawn_x"],
            "spawn_y": case["spawn_y"],
        },
    }
    if recorded != expected_record:
        raise ValueError(f"recorded case differs from raw evidence: {case_id}")
    return expected_record


def _verify_or_raise(artifact: Path) -> dict[str, Any]:
    manifest = _json_file(artifact / "manifest.json", "manifest")
    evidence = _json_file(artifact / "evidence.json", "evidence")
    if manifest.get("schema") != "git-artifact-promotion-v1" or manifest.get("artifact_schema") != SCHEMA:
        raise ValueError("manifest schema mismatch")
    if evidence.get("schema") != SCHEMA:
        raise ValueError("evidence schema mismatch")
    expected_files = {"evidence.json", "raw-batch.tar"}
    if set(manifest.get("files", {})) != expected_files:
        raise ValueError("artifact file denominator mismatch")
    for name in expected_files:
        if manifest["files"][name] != _sha256(artifact / name):
            raise ValueError(f"artifact file hash mismatch: {name}")
    if set(manifest.get("repository_files", {})) != set(REPOSITORY_FILES):
        raise ValueError("repository dependency denominator mismatch")
    for name in REPOSITORY_FILES:
        if manifest["repository_files"][name] != _sha256(ROOT / name):
            raise ValueError(f"repository dependency hash mismatch: {name}")
    _source_records(evidence)
    toolchain_profile = _json_file(ROOT / TOOLCHAIN_PROFILE, "toolchain profile")
    toolchain_hardware = toolchain_profile.get("hardware_evidence")
    if (
        toolchain_profile.get("schema") != "rom-expansion-profile-v1"
        or not isinstance(toolchain_hardware, dict)
        or toolchain_hardware.get("mgba_source_commit") != EXPECTED_MGBA_SOURCE_COMMIT
        or toolchain_hardware.get("mgba_binary_sha256") != EXPECTED_BINARY_SHA256
    ):
        raise ValueError("toolchain profile identity mismatch")
    parent_controlled = verify_parent_controlled(ROOT / PARENT_CONTROLLED_ROOT)
    parent_group15 = verify_parent_group15(ROOT / PARENT_GROUP15_ROOT)
    if not parent_controlled.get("verified") or not parent_group15.get("verified"):
        raise ValueError("verified parent battle-effect evidence is missing")
    parent_controlled_evidence = _json_file(
        ROOT / PARENT_CONTROLLED_ROOT / "evidence.json",
        "parent controlled evidence",
    )
    if parent_controlled_evidence.get("coverage", {}).get(
        "controlled_or_observed_group_ids"
    ) != [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17]:
        raise ValueError("parent controlled coverage mismatch")
    _verify_static_contract((ROOT / BASE_ROM).read_bytes())
    archive = artifact / "raw-batch.tar"
    payloads = read_safe_tar(archive)
    if set(payloads) != _expected_members() or len(payloads) != 51:
        raise ValueError("raw archive member denominator mismatch")
    archive_record = evidence.get("archive", {})
    expected_ledger = {name: {"sha256": _sha256_bytes(raw), "size": len(raw)} for name, raw in payloads.items()}
    if archive_record != {
        "path": "raw-batch.tar",
        "sha256": _sha256(archive),
        "size": archive.stat().st_size,
        "member_count": 51,
        "members": expected_ledger,
    }:
        raise ValueError("raw archive ledger mismatch")
    animations = _json_file(ROOT / ANIMATION_CATALOG, "animation catalog")
    resources = _json_file(ROOT / RESOURCE_CATALOG, "resource catalog")
    animation_groups = {row["group_id"]: row for row in animations["groups"]}
    resource_entries = {row["group_id"]: row for row in resources["entries"]}
    if resource_entries[3]["graphics"]["tile_count"] != 304 or resource_entries[18]["graphics"]["tile_count"] != 112:
        raise ValueError("resource tile count mismatch")
    recorded_cases = evidence.get("cases")
    if not isinstance(recorded_cases, list) or len(recorded_cases) != 4:
        raise ValueError("direct case denominator mismatch")
    with tempfile.TemporaryDirectory() as temporary_name:
        temporary = Path(temporary_name)
        cases = [
            _verify_case(payloads, recorded, case, animation_groups[case["group_id"]], resource_entries[case["group_id"]], temporary)
            for recorded, case in zip(recorded_cases, CASE_ROWS, strict=True)
        ]
        negative_state = _state(
            payloads["source/narrow-window-negative/output/timeout.ss9"],
            temporary,
            "narrow-window-negative.ss9",
        )
        input_state = load_gba_state(ROOT / INPUT_STATE)
    narrow_profile = _json_bytes(payloads["source/narrow-window-negative/profile.json"], "negative profile")
    narrow_audit = _json_bytes(payloads["source/narrow-window-negative/output/audit.json"], "negative audit")
    narrow_guard = _json_bytes(payloads["source/narrow-window-negative/guard-summary.json"], "negative guard")
    narrow_done = _json_bytes(payloads["source/narrow-window-negative/guard-summary.json.done.json"], "negative done")
    narrow_case = dict(CASE_ROWS[0])
    narrow_case.update({"spawn_x": 120, "tile_start": 0x300, "tile_end": 0x37F, "palette_start": 12})
    narrow_rom_sha = _sha256_bytes(build_expected_probe((ROOT / BASE_ROM).read_bytes(), narrow_case))
    _verify_negative_run_inventory(payloads, narrow_rom_sha)
    narrow_selector = negative_state.read_memory(SCRATCH + 4, 1)[0]
    narrow_command = narrow_guard.get("command")
    narrow_staged_suffix = f"output/{NEGATIVE_CASE_ID}/staged.gba"
    narrow_animation = animation_groups[3]
    if (
        narrow_profile.get("schema") != "battle-effect-phase-capture-profile-v1"
        or set(narrow_profile) != {
            "allocator_reset", "boundary", "execution_mode", "group_id",
            "input_mode", "input_state", "input_state_sha256", "profile_id",
            "schema", "sequence_id", "source_rom_sha256",
            "source_runtime_evidence", "source_runtime_evidence_sha256",
            "spawn", "timeout_frames",
        }
        or narrow_profile.get("execution_mode") != "controlled-direct-spawn"
        or narrow_profile.get("group_id") != 3
        or narrow_profile.get("sequence_id") != 3
        or narrow_profile.get("input_mode") != "zero-input-active-state"
        or narrow_profile.get("input_state") != INPUT_STATE
        or narrow_profile.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
        or narrow_profile.get("source_runtime_evidence") != SEQUENCE_CATALOG
        or narrow_profile.get("source_runtime_evidence_sha256") != TRUSTED_SOURCE_SHA256["sequence_catalog"]
        or narrow_profile.get("timeout_frames") != 60
        or narrow_profile.get("allocator_reset") != {"function": "0x0807FDCC", "tile_start": "0x0300", "tile_end": "0x037F", "palette_start": 12, "palette_end": 14}
        or narrow_profile.get("spawn") != {"selector": "0x0807FE2C", "function": "0x08080108", "side": 0, "x": 120, "y": 80}
        or narrow_profile.get("source_rom_sha256") != narrow_rom_sha
        or narrow_audit.get("schema") != "mgba-battle-effect-phase-capture-v1"
        or set(narrow_audit) != {
            "schema", "run_id", "outcome", "group_id", "definition_pointer",
            "animation_pointer", "frame", "capture_frames", "timeout_frames",
            "input_state", "input_state_sha256", "rom_sha256", "input_mode",
            "inputs", "automatic_inputs", "recovery_inputs", "renderer_hit_count",
            "submission_watch_hit_count", "ack_hit_count", "phases",
        }
        or narrow_audit.get("group_id") != 3
        or narrow_audit.get("definition_pointer") != narrow_animation["definition_pointer_table"]
        or narrow_audit.get("animation_pointer") != narrow_animation["animation_pointer_table"]
        or narrow_audit.get("input_mode") != "zero-input-active-state"
        or narrow_audit.get("input_state_sha256") != TRUSTED_SOURCE_SHA256["input_state"]
        or not _path_has_suffix(narrow_audit.get("input_state"), INPUT_STATE)
        or narrow_audit.get("inputs") != []
        or narrow_audit.get("automatic_inputs") != []
        or narrow_audit.get("recovery_inputs") != []
        or narrow_audit.get("capture_frames") != 0
        or narrow_audit.get("timeout_frames") != 60
        or narrow_audit.get("rom_sha256") != narrow_rom_sha
        or narrow_audit.get("outcome") != "capture-incomplete"
        or narrow_audit.get("phases") != []
        or narrow_guard.get("reason") != "completed"
        or set(narrow_guard) != {
            "reason", "exit_code", "child_pid", "peak_tree_rss_mib",
            "protection_backend", "degraded", "command", "cwd", "started_at",
            "finished_at", "completion_trigger",
        }
        or narrow_guard.get("exit_code") != 0
        or narrow_guard.get("degraded") is not False
        or narrow_guard.get("completion_trigger") != "success-marker"
        or not isinstance(narrow_command, list)
        or len(narrow_command) != 4
        or Path(narrow_command[0]).name != "mGBA"
        or narrow_command[1] != "--script"
        or not _path_has_suffix(narrow_command[2], CAPTURE_SCRIPT)
        or not _path_has_suffix(narrow_command[3], narrow_staged_suffix)
        or _sha256(Path(narrow_command[0]).resolve(strict=True)) != EXPECTED_BINARY_SHA256
        or set(narrow_done) != {"run_id", "status", "phase_count"}
        or narrow_done.get("status") != "capture-incomplete"
        or narrow_done.get("phase_count") != 0
        or narrow_done.get("run_id") != narrow_audit.get("run_id")
        or negative_state.read_memory(SCRATCH, 4) != b"\x01\x00\x00\x00"
        or narrow_selector != 0xFF
    ):
        raise ValueError("narrow-window negative provenance mismatch")
    allocator_ab = evidence.get("group3_allocator_ab")
    expected_allocator_ab = {
        "narrow_window": {"tile_start": 0x300, "tile_end": 0x37F},
        "narrow_selector_result": 0xFF,
        "wide_window": {"tile_start": 0x100, "tile_end": 0x39F},
        "wide_selector_results": [0, 0],
        "resource_tile_count": 304,
        "causal_boundary": (
            "The failed selector is upstream of spawn coordinates; the narrow 128-tile "
            "window cannot contain the 304-tile group 3 payload. The wide window is a "
            "controlled capacity reconstruction, not a proven direct natural caller reset."
        ),
    }
    if allocator_ab != expected_allocator_ab:
        raise ValueError("group 3 allocator A/B boundary mismatch")
    pointers = [input_state.read_u32(0x02026CA4), input_state.read_u32(0x02026CA8)]
    owner_bytes = [input_state.read_memory(pointer + 2, 1)[0] for pointer in pointers]
    side_observation = evidence.get("group3_side_observation")
    expected_side_observation = {
        "sides": [0, 1],
        "requested_x": 104,
        "target_anchors": [[136, 80], [136, 80]],
        "target_flags": [cases[0]["phases"][0]["target_task"]["flags"], cases[1]["phases"][0]["target_task"]["flags"]],
        "mirror_branch_proven": False,
        "reason": (
            "The accepted checkpoint has owner byte+2 values 1/0 for side 0/1, "
            "so both calls take the mirrored-x branch and both anchors are 136,80."
        ),
    }
    if owner_bytes != [1, 0] or side_observation != expected_side_observation or expected_side_observation["target_flags"][0] == expected_side_observation["target_flags"][1]:
        raise ValueError("group 3 side/mirror boundary mismatch")
    expected_coverage = {
        "direct_case_count": 4,
        "direct_case_success_count": 4,
        "new_controlled_group_ids": [3, 18],
        "controlled_or_observed_group_ids": list(range(1, 19)),
        "controlled_or_observed": {"numerator": 18, "denominator": 18},
        "production_natural_pixel_ab": {"numerator": 4, "denominator": 18},
        "observed_frame_phase": {"numerator": 5, "denominator": 18},
        "natural_entry_complete": False,
        "full_animation_complete": False,
        "real_hardware_complete": False,
    }
    if evidence.get("coverage") != expected_coverage:
        raise ValueError("coverage boundary mismatch")
    valid = [row["case_id"] for row in cases if row["rss_sample_valid_for_statistics"]]
    undersampled = [row["case_id"] for row in cases if not row["rss_sample_valid_for_statistics"]]
    if evidence.get("memory_sampling") != {
        "valid_case_ids": valid,
        "undersampled_case_ids": undersampled,
        "interpretation": "Guard enforcement remained active; sub-10 MiB peak samples are timing misses and are excluded from statistics.",
    }:
        raise ValueError("memory sampling boundary mismatch")
    return {
        "verified": True,
        "errors": [],
        "direct_case_count": 4,
        "controlled_or_observed_groups": 18,
        "narrow_group3_selector": narrow_selector,
        "wide_group3_selectors": [cases[0]["phases"][0]["selector_result"], cases[1]["phases"][0]["selector_result"]],
        "group3_mirror_branch_proven": False,
    }


def verify_artifact(artifact: Path) -> dict[str, Any]:
    try:
        return _verify_or_raise(Path(artifact).resolve(strict=True))
    except Exception as error:
        return {
            "verified": False,
            "errors": [str(error)],
            "direct_case_count": 0,
            "controlled_or_observed_groups": 0,
            "narrow_group3_selector": None,
            "wide_group3_selectors": [],
            "group3_mirror_branch_proven": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    result = verify_artifact(args.artifact)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
