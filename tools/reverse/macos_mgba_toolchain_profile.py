#!/usr/bin/env python3
"""Validate the accepted current-desktop mGBA runtime profile."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from tools.run_macos_mgba_replay import ReplayError, validate_expected_hash
except ModuleNotFoundError:
    from run_macos_mgba_replay import ReplayError, validate_expected_hash


CURRENT_TOOLCHAIN_PROFILE_SHA256 = (
    "e21d375914dda3c20b05ccec45c39406db310609e69ee19d04dfa342f4b70287"
)
CURRENT_MGBA_SOURCE_COMMIT = "d8bad14b4540f9114246c0281d74985cf81adc68"


def _object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReplayError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ReplayError(f"{label} must be a JSON object")
    return value


def validate_current_toolchain_profile(
    profile_path: Path, binary: Path, expected_binary_sha256: str
) -> dict[str, Any]:
    """Validate the current desktop mGBA against its accepted runtime evidence."""
    profile = _object(profile_path, "mGBA runtime profile")
    if profile.get("schema") != "rom-expansion-profile-v1":
        raise ReplayError("mGBA runtime profile schema mismatch")
    if profile.get("identity") != "agb_standard_16mib_sequel_rom_profile":
        raise ReplayError("mGBA runtime profile identity mismatch")
    hardware = profile.get("hardware_evidence")
    if not isinstance(hardware, dict):
        raise ReplayError("mGBA runtime profile hardware evidence is missing")
    if hardware.get("mgba_source_commit") != CURRENT_MGBA_SOURCE_COMMIT:
        raise ReplayError("mGBA runtime profile source commit mismatch")
    if hardware.get("mgba_binary_sha256") != expected_binary_sha256:
        raise ReplayError("mGBA runtime profile binary hash mismatch")
    validate_expected_hash(binary, expected_binary_sha256, "mGBA binary")
    runtime = profile.get("runtime_probe")
    if not isinstance(runtime, dict):
        raise ReplayError("mGBA runtime profile probe evidence is missing")
    expected_runtime = {
        "guard_reason": "completed",
        "guard_completion_trigger": "success-marker",
        "guard_exit_code": 0,
        "guard_degraded": False,
        "new_mgba_crash_report": False,
        "owned_process_residue": False,
    }
    for field, expected in expected_runtime.items():
        if runtime.get(field) != expected:
            raise ReplayError(f"mGBA runtime profile {field} mismatch")
    return profile
