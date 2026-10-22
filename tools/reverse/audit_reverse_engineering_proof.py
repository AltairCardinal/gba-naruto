#!/usr/bin/env python3
"""Audit the evidence required for an absolute reverse-engineering claim.

The auditor is deliberately fail-closed: labels and zero exit codes are not
proof.  A complete claim needs a caller-supplied root digest, the fixed bank
inventory, typed coverage denominators, structured verifier contracts, and an
actual verifier run.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit_rom_byte_coverage import MINIMUM_PYTHON
from tools.audit_rom_byte_coverage import _require_supported_python
from tools.audit_rom_byte_coverage import audit_manifest as audit_rom_manifest
from tools.verify_similar_table_candidates import (
    verify_repository_manifests as verify_similar_table_manifest,
)


SCHEMA = "reverse-engineering-proof-v1"
EXPECTED_BANKS = (
    "audio",
    "battle-config",
    "battle-encounters",
    "battle-handlers",
    "character-stats",
    "character-stats-b",
    "cutscene-scripts",
    "data-table-a",
    "data-table-b",
    "encounter-zones",
    "fonts",
    "function-pointers",
    "items",
    "levels",
    "map-events",
    "map-sprites",
    "maps",
    "menu-ui",
    "palettes",
    "positions",
    "resource-pointers",
    "sappy-engine",
    "save-state",
    "skills",
    "sprite-animations",
    "story",
    "story-b",
    "story-c",
    "story-d",
    "story-e",
    "tile-assets",
    "units",
)
EXPECTED_BANK_FILE_SHA256 = {
    "audio": "9c29808c854c9aa119b6ac2121754dd4c72dadb23e1a3c70264a087d38967f18",
    "battle-config": "ab5b49f47d86084517b926da79c1a6b7c0c62bdf51f6ea3813bfd3d809b2d702",
    "battle-encounters": "9c3d2860f06a0c994c9fdac5211a114322303943552299f1b545ac8dd982986d",
    "battle-handlers": "1d3b1ed2da0b7581f09cc7fbf40db5169f7e6c3659bf47def544a9d6ef4886bd",
    "character-stats": "a20233c665268fe85b48fc344db86c65735ca72d5c4529c006d2d5de79793256",
    "character-stats-b": "9655ae046ead20234259aa342c01e393604d95120febce8acafa454c72c44184",
    "cutscene-scripts": "791f8173103259290c57b29908e010362c29de9caaa3c983e1e7b0336cb406a4",
    "data-table-a": "319cfe202e5e630ec69fb2ec0f207a1cd80076efb8ad1a813a20ef0a90e6537d",
    "data-table-b": "5b8bf5e464c52dac97cd5522c079dea6e31527beb51ed4c0f8b07f934e2a7059",
    "encounter-zones": "656e77b14b8faf5dd0d5665836965d05272b6f7752ad50e6bb9944e9e6671bc1",
    "fonts": "206cdb5470c09505195eeff6b6c4d288fa2442f4ca772913d0fb47a3dcad38d4",
    "function-pointers": "88a227b94198761bf47c925c5ea6527ceabbd17d8601eea5c9986c97ee6304b2",
    "items": "8dd9458f2c15ac6db09fd534970bbccc0d01500744e65d84561d2b89c718fca1",
    "levels": "d64d69d5c85f4beb4719434a4c4bd97067a015462aec0df2f23bbca25ff471fd",
    "map-events": "aaf2c3244502fbf062d8d43721f7e1f6ef83b244aa32cbf3aff4d5e709a99365",
    "map-sprites": "52fae253049983323951b5c29b21e6960c6975c0348238947a8ec38efe474064",
    "maps": "a8e224f9ac3c243707e33706ef2cf2042cb2a13cd8607207622f55cc78d0f367",
    "menu-ui": "8e9cf0a4289ff2701ad9643181532a6e8283177875b38d34d6eced5948a6cfe7",
    "palettes": "c4f8ea7de0e5e09c88c4be8897514160a4269627801195b125887213b397066f",
    "positions": "1e9d2822e486c6e79c9ad4f1545915fa378505dd1b58e840f939fd1032fd55e9",
    "resource-pointers": "0d595c1dfeb9b71a25007e5aef11232553b3aecc9bc29321e185346dbfe5aa2d",
    "sappy-engine": "d71d8aff52746a61d59139d6ca4ccf3a9dd354b84ef90159276ca541cf82eb40",
    "save-state": "93552dd5222089538fb5d6b251cca97ecbc037b4b5acdb05ad108588fa0b1bce",
    "skills": "84b452026bda87d99601bfc7ff914be1cb6b42fc286038b0cc96394ad8f4b9f6",
    "sprite-animations": "5148a8a367861e011ec59d75ee8cbf19feb25b2ea511fa56bde390d5f1cee4ee",
    "story": "3b1467d057b8196e376b0cba6a7abb195940afe7956fa7f482c2470ef5079b17",
    "story-b": "654db6c57ae8dac8c87462ee2e9c9350cee90a572a7755406359f68e3c9afa8e",
    "story-c": "e0f22540e759975a557182612f764fde415490eaec1d9d9f0585e5a411d087c4",
    "story-d": "e3aa6bf2b1ae6c7a109a3082c0d0a53055f459aedfd1b9ab9dc2e293f3b17474",
    "story-e": "c9d4bdb125965e372f0069a981c758e036ffd7c039a57e7c5ca3ea571c1c4608",
    "tile-assets": "9ef92f5c358f114a660eeea42ab5358f37435047d7bb91708c3a80274d5df218",
    "units": "7d54332bbd3b75dd4f5eea7a10cdde355dfacffa8958393c11aa5370296a5db6",
}
EXPECTED_DISPROVED_CANDIDATE_RANGES = {
    "battle-handlers": (5498584, 5498640),
    "character-stats-b": (5526016, 5526304),
    "encounter-zones": (5495056, 5496560),
    "fonts": (5498292, 5498548),
    "items": (5529856, 5530048),
    "resource-pointers": (5861132, 5861212),
    "sprite-animations": (5501440, 5501592),
    "story-c": (5476336, 5476340),
    "story-d": (5483384, 5483388),
    "story-e": (5489600, 5489604),
}
GATE_CASES = {
    "rom_byte_coverage": ("all-rom-bytes-semantically-classified",),
    "resource_roundtrip": (
        "graphics",
        "audio",
        "text",
        "maps",
        "levels",
        "story",
        "characters",
    ),
    "editor_roundtrip": (
        "map-editor",
        "level-editor",
        "story-editor",
        "character-editor",
    ),
    "logic_modification": ("menu-logic", "battle-logic"),
    "clean_rebuild": (
        "clean-checkout",
        "pinned-toolchain",
        "deterministic-rom",
    ),
    "emulator_regression": (
        "base-rom-regression-matrix",
        "rebuilt-rom-regression-matrix",
    ),
    "physical_hardware": ("original-gba-release-smoke",),
}
REQUIRED_GATES = tuple(GATE_CASES)
# The reproducible full-ROM coverage verifier is the longest single step of the
# audit.  Receipt-backed history on the desktop runtime: 1,901.8 s (2026-09-05,
# notes/evidence/rom-post-story-four-packet-tier2-20260905/coverage-guard.json)
# and 1,819.5 s (2026-09-30,
# notes/evidence/rom-small-cfg-batch-canonical-20260930-v1/coverage-guard.json).
# That cost was dominated by ``atomize_claims`` being called 39 times with an
# O(segments x claims) scan (60.50 s per full-ledger call).  Since 2026-10-20
# that scan is a sweep (0.09 s per call, byte-identical output; see
# tests/test_audit_rom_byte_coverage_atomize_sweep.py), so the coverage step is
# expected back in the low hundreds of seconds.  Keep a bounded margin while
# the outer resource guard enforces the whole audit's memory, idle and
# wall-clock limits.
VERIFIER_TIMEOUT_SECONDS = 1_800
VERIFIER_PATH_OPTIONS = {
    "--artifact",
    "--artifact-dir",
    "--binary",
    "--evidence",
    "--input",
    "--manifest",
    "--rom",
    "--rom-path",
    "--root",
}


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _repo_file(
    root: Path,
    value: object,
    label: str,
    blockers: list[str],
    *,
    parent: Path | None = None,
) -> Path | None:
    if not isinstance(value, str) or not value:
        blockers.append(f"{label} path is missing")
        return None
    relative = Path(value)
    if relative.is_absolute():
        blockers.append(f"{label} path must be repository-relative")
        return None
    if ".." in relative.parts:
        blockers.append(f"{label} path contains parent traversal: {value}")
        return None
    candidate = root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        blockers.append(f"{label} path is not a file: {value}")
        return None
    allowed_parent = parent.resolve(strict=True) if parent else root
    if not _inside(resolved, allowed_parent):
        blockers.append(f"{label} path escapes repository: {value}")
        return None
    if resolved != candidate.absolute():
        blockers.append(f"{label} path must not use symlinks: {value}")
        return None
    if not resolved.is_file():
        blockers.append(f"{label} path is not a file: {value}")
        return None
    return resolved


def _evidence_list(value: object) -> list[dict[str, str]] | None:
    if not isinstance(value, list):
        return None
    evidence: list[dict[str, str]] = []
    for item in value:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not item["path"]
            or not _is_sha256(item.get("sha256"))
        ):
            return None
        evidence.append({"path": item["path"], "sha256": item["sha256"]})
    return evidence


def _contract(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("format") != "json":
        return None
    assertions = value.get("assertions")
    if not isinstance(assertions, dict) or not assertions:
        return None
    if not isinstance(assertions.get("/schema"), str):
        return None
    has_explicit_success = (
        assertions.get("/verified") is True
        or assertions.get("/errors") == []
    )
    if not has_explicit_success:
        return None
    if not all(isinstance(pointer, str) and pointer.startswith("/") for pointer in assertions):
        return None
    return {"format": "json", "assertions": assertions}


def _verifier_list(value: object) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    verifiers: list[dict[str, Any]] = []
    for item in value:
        command = item.get("command") if isinstance(item, dict) else None
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(part, str) and part for part in command)
            or not _is_sha256(item.get("script_sha256"))
        ):
            return None
        verifiers.append(
            {
                "command": command,
                "script_sha256": item["script_sha256"],
                "contract": item.get("contract"),
            }
        )
    return verifiers


def _valid_contracts(proof: dict[str, Any]) -> list[dict[str, Any]]:
    verifiers = _verifier_list(proof.get("verifiers")) or []
    return [
        contract
        for verifier in verifiers
        if (contract := _contract(verifier.get("contract"))) is not None
    ]


def _evidence_hashes(proof: dict[str, Any]) -> dict[str, str]:
    return {
        item["path"]: item["sha256"]
        for item in (_evidence_list(proof.get("evidence")) or [])
    }


def _check_verifier_path_argument(
    root: Path, label: str, value: str, blockers: list[str]
) -> bool:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        blockers.append(
            f"{label}: verifier path argument escapes repository: {value}"
        )
        return False
    candidate = root / path
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        blockers.append(f"{label}: verifier path argument does not exist: {value}")
        return False
    if not _inside(resolved, root) or resolved != candidate.absolute():
        blockers.append(
            f"{label}: verifier path argument escapes repository or uses a symlink: {value}"
        )
        return False
    return True


def _check_verifier_arguments(
    root: Path, label: str, arguments: list[str], blockers: list[str]
) -> bool:
    valid = True
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if "=" in argument and argument.startswith("--"):
            option, value = argument.split("=", 1)
            if Path(value).is_absolute() or ".." in Path(value).parts:
                blockers.append(
                    f"{label}: verifier path argument escapes repository: {value}"
                )
                valid = False
            elif option in VERIFIER_PATH_OPTIONS:
                valid = (
                    _check_verifier_path_argument(root, label, value, blockers)
                    and valid
                )
        elif argument in VERIFIER_PATH_OPTIONS:
            if index + 1 >= len(arguments):
                blockers.append(f"{label}: verifier path option has no value: {argument}")
                valid = False
            else:
                index += 1
                valid = (
                    _check_verifier_path_argument(
                        root, label, arguments[index], blockers
                    )
                    and valid
                )
        elif Path(argument).is_absolute() or ".." in Path(argument).parts:
            blockers.append(
                f"{label}: verifier path argument escapes repository: {argument}"
            )
            valid = False
        elif not argument.startswith("-") and "/" in argument:
            valid = (
                _check_verifier_path_argument(root, label, argument, blockers)
                and valid
            )
        index += 1
    return valid


def _json_pointer(value: object, pointer: str) -> object:
    current = value
    for raw_part in pointer.split("/")[1:]:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise KeyError(pointer)
    return current


def _check_bindings(
    root: Path,
    label: str,
    proof: dict[str, Any],
    blockers: list[str],
    commands: list[tuple[str, list[str], dict[str, Any]]],
) -> dict[str, Any]:
    evidence = _evidence_list(proof.get("evidence"))
    evidence_valid = bool(evidence)
    if not evidence:
        blockers.append(f"{label}: missing hash-bound evidence")
    else:
        for binding in evidence:
            relative = binding["path"]
            path = _repo_file(root, relative, f"{label}: evidence", blockers)
            if path is None:
                evidence_valid = False
            elif _sha256_file(path) != binding["sha256"]:
                evidence_valid = False
                blockers.append(f"{label}: evidence SHA-256 mismatch: {relative}")

    verifiers = _verifier_list(proof.get("verifiers"))
    hash_bound_count = 0
    contracted_count = 0
    if not verifiers:
        blockers.append(f"{label}: missing hash-bound verifier commands")
    else:
        tools_root = (root / "tools").resolve(strict=True)
        for verifier in verifiers:
            command = verifier["command"]
            if len(command) < 2 or command[0] != "python3":
                blockers.append(f"{label}: verifier must use python3 plus a script")
                continue
            if command[1:3] == ["-I", "-S"]:
                if len(command) < 4:
                    blockers.append(
                        f"{label}: isolated verifier must use python3 -I -S plus a script"
                    )
                    continue
                script_index = 3
            elif command[1].startswith("-"):
                blockers.append(
                    f"{label}: verifier uses unsupported python flags: {command[1]}"
                )
                continue
            else:
                script_index = 1
            script_relative = command[script_index]
            script = _repo_file(
                root,
                script_relative,
                f"{label}: verifier script",
                blockers,
                parent=tools_root,
            )
            if script is None:
                continue
            if _sha256_file(script) != verifier["script_sha256"]:
                blockers.append(
                    f"{label}: verifier script SHA-256 mismatch: {script_relative}"
                )
                continue
            hash_bound_count += 1
            if not _check_verifier_arguments(
                root, label, command[script_index + 1 :], blockers
            ):
                continue
            contract = _contract(verifier.get("contract"))
            if contract is None:
                blockers.append(
                    f"{label}: verifier lacks a structured JSON result contract: {script_relative}"
                )
                continue
            commands.append((label, [sys.executable, *command[1:]], contract))
            contracted_count += 1

    limitations = proof.get("limitations")
    if not isinstance(limitations, list):
        blockers.append(f"{label}: limitations must be an array")
    elif limitations:
        blockers.append(f"{label}: unresolved limitations remain ({len(limitations)})")
    return {
        "evidence_valid": evidence_valid,
        "hash_bound_verifier_count": hash_bound_count,
        "contracted_verifier_count": contracted_count,
        "limitations_count": len(limitations) if isinstance(limitations, list) else None,
    }


def _schema_field_ids(bank: dict[str, Any], slug: str, blockers: list[str]) -> list[str]:
    entry_size = bank.get("entry_size")
    entry_format = bank.get("entry_format")
    fields = entry_format.get("fields") if isinstance(entry_format, dict) else None
    if not isinstance(entry_size, int) or entry_size <= 0 or not isinstance(fields, list):
        blockers.append(f"{slug}: bank has no valid entry_size/entry_format denominator")
        return []
    names: list[str] = []
    for field in fields:
        if not isinstance(field, dict) or not isinstance(field.get("name"), str):
            blockers.append(f"{slug}: entry_format contains an invalid field")
            continue
        name = field["name"]
        names.append(name)
        offset, size = field.get("offset"), field.get("size")
        if offset is not None or size is not None:
            if (
                not isinstance(offset, int)
                or not isinstance(size, int)
                or offset < 0
                or size <= 0
                or offset + size > entry_size
            ):
                blockers.append(f"{slug}: field {name!r} is outside its entry layout")
    if len(names) != len(set(names)):
        blockers.append(f"{slug}: entry_format field IDs are not unique")
    return names


def _check_bank(
    root: Path,
    slug: str,
    bank_path: Path,
    proof: object,
    rom: bytes | None,
    blockers: list[str],
    commands: list[tuple[str, list[str], dict[str, Any]]],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "bank": slug,
        "proof_bound": isinstance(proof, dict),
        "complete": False,
    }
    before = len(blockers)
    bound_bank_path = _repo_file(
        root,
        bank_path.relative_to(root).as_posix(),
        f"{slug}: fixed bank file",
        blockers,
    )
    if bound_bank_path is None:
        blockers.append(f"{slug}: fixed bank file is missing")
        result["blockers"] = blockers[before:]
        return result
    bank_path = bound_bank_path
    actual_bank_sha = _sha256_file(bank_path)
    if actual_bank_sha != EXPECTED_BANK_FILE_SHA256.get(slug):
        blockers.append(f"{slug}: fixed bank denominator changed")
    bank = _read_object(bank_path, f"bank {slug}")
    classification = bank.get("verification")
    result["classification"] = classification
    if classification not in {"runtime_verified", "disproved"}:
        blockers.append(
            f"{slug}: classification is {classification!r}, expected runtime_verified or disproved"
        )
    if not isinstance(proof, dict):
        blockers.append(f"{slug}: missing proof object")
        result["blockers"] = blockers[before:]
        return result

    expected_bank_sha = proof.get("bank_sha256")
    if not _is_sha256(expected_bank_sha) or actual_bank_sha != expected_bank_sha:
        blockers.append(f"{slug}: bank file is not bound by its exact SHA-256")
    result.update(_check_bindings(root, slug, proof, blockers, commands))
    if proof.get("catalog_classification") != classification:
        blockers.append(
            f"{slug}: proof classification {proof.get('catalog_classification')!r} "
            f"does not match bank {classification!r}"
        )

    entries = bank.get("entries")
    if not isinstance(entries, list):
        blockers.append(f"{slug}: entries must be an array")
        entries = []
    if bank.get("entry_count") != len(entries):
        blockers.append(f"{slug}: entry_count does not match entries length")
    coverage = proof.get("coverage")
    if not isinstance(coverage, dict):
        blockers.append(f"{slug}: missing proof coverage")
        coverage = {}
    result["coverage_status"] = coverage.get("status")
    result["declared_records_total"] = coverage.get("records_total")
    result["declared_records_covered"] = coverage.get("records_covered")
    declared_total = coverage.get("records_total")
    declared_covered = coverage.get("records_covered")
    if declared_total != len(entries):
        blockers.append(
            f"{slug}: declared record denominator {declared_total!r} does not "
            f"match bank entry count {len(entries)!r}"
        )
    if (
        not isinstance(declared_covered, int)
        or declared_covered < 0
        or not isinstance(declared_total, int)
        or declared_covered > declared_total
    ):
        blockers.append(f"{slug}: declared covered-record count is invalid")

    if classification == "disproved":
        if coverage.get("status") != "disproved":
            blockers.append(f"{slug}: disproved bank coverage status must be disproved")
        if entries:
            blockers.append(f"{slug}: disproved bank must have no entries")
        candidate_range = proof.get("candidate_range")
        valid_range = (
            isinstance(candidate_range, list)
            and len(candidate_range) == 2
            and all(isinstance(value, int) for value in candidate_range)
            and candidate_range[0] >= 0
            and candidate_range[0] < candidate_range[1]
            and rom is not None
            and candidate_range[1] <= len(rom)
        )
        if not valid_range:
            blockers.append(f"{slug}: disproved proof needs an in-ROM candidate range")
        elif (
            not _is_sha256(proof.get("candidate_sha256"))
            or hashlib.sha256(rom[candidate_range[0] : candidate_range[1]]).hexdigest()
            != proof["candidate_sha256"]
        ):
            blockers.append(f"{slug}: candidate ROM bytes are not SHA-256 bound")
        expected_candidate_range = EXPECTED_DISPROVED_CANDIDATE_RANGES.get(slug)
        if expected_candidate_range is None or tuple(candidate_range or ()) != expected_candidate_range:
            blockers.append(f"{slug}: fixed disproved candidate range changed")
        if not isinstance(proof.get("rejection_reason"), str) or not proof[
            "rejection_reason"
        ].strip():
            blockers.append(f"{slug}: disproved proof needs a rejection reason")
        if proof.get("rejection_scope") != "independent_physical_bank_candidate":
            blockers.append(
                f"{slug}: disproved proof must target the fixed independent physical bank scope"
            )
        candidate_contract_bound = any(
            contract["assertions"].get("/candidate_range") == candidate_range
            and contract["assertions"].get("/candidate_sha256")
            == proof.get("candidate_sha256")
            and contract["assertions"].get("/rejected") is True
            and contract["assertions"].get("/rejection_scope")
            == "independent_physical_bank_candidate"
            and contract["assertions"].get(
                "/alternative_logical_consumers_exhaustively_excluded"
            )
            is False
            and contract["assertions"].get("/bank_sha256") == actual_bank_sha
            and contract["assertions"].get("/evidence_sha256")
            == _evidence_hashes(proof)
            for contract in _valid_contracts(proof)
        )
        if not candidate_contract_bound:
            blockers.append(
                f"{slug}: no verifier contract binds the rejected candidate bytes"
            )
    else:
        expected_record_ids = [str(index) for index in range(len(entries))]
        expected_field_ids = _schema_field_ids(bank, slug, blockers)
        if not entries:
            blockers.append(f"{slug}: runtime bank cannot have an empty record denominator")
        if coverage.get("status") != "exhaustive":
            blockers.append(
                f"{slug}: coverage status={coverage.get('status')!r}, expected 'exhaustive'"
            )
        if (
            coverage.get("record_ids_total") != expected_record_ids
            or coverage.get("record_ids_covered") != expected_record_ids
        ):
            blockers.append(f"{slug}: record coverage is not exhaustively ID-bound")
        if not expected_field_ids or coverage.get("field_ids_total") != expected_field_ids:
            blockers.append(f"{slug}: field denominator does not match entry_format")
        if coverage.get("field_ids_covered") != expected_field_ids:
            blockers.append(f"{slug}: field coverage is not exhaustive")
        exhaustive_contract_bound = any(
            contract["assertions"].get("/record_ids_covered")
            == expected_record_ids
            and contract["assertions"].get("/field_ids_covered")
            == expected_field_ids
            and contract["assertions"].get("/bank_sha256") == actual_bank_sha
            and contract["assertions"].get("/evidence_sha256")
            == _evidence_hashes(proof)
            for contract in _valid_contracts(proof)
        )
        if not exhaustive_contract_bound:
            blockers.append(
                f"{slug}: no verifier contract binds the exhaustive record, field, bank and evidence IDs"
            )

    result["blockers"] = blockers[before:]
    result["complete"] = len(blockers) == before
    return result


def _load_bank_proofs(
    root: Path, spec: dict[str, Any], blockers: list[str]
) -> dict[str, Any]:
    binding = spec.get("bank_proofs")
    if not isinstance(binding, dict):
        blockers.append("bank proof catalog binding is missing")
        return {}
    relative = binding.get("path")
    expected_sha = binding.get("sha256")
    if not _is_sha256(expected_sha):
        blockers.append("bank proof catalog binding is invalid")
        return {}
    path = _repo_file(root, relative, "bank proof catalog", blockers)
    if path is None:
        return {}
    if _sha256_file(path) != expected_sha:
        blockers.append(f"bank proof catalog SHA-256 mismatch: {relative}")
    try:
        payload = _read_object(path, "bank proof catalog")
    except ValueError as error:
        blockers.append(str(error))
        return {}
    if payload.get("schema") != "bank-proofs-v1":
        blockers.append("bank proof catalog schema must be bank-proofs-v1")
    banks = payload.get("banks")
    if not isinstance(banks, dict):
        blockers.append("bank proof catalog banks must be an object")
        return {}
    return banks


def _check_gate_coverage(
    name: str, gate: dict[str, Any], blockers: list[str]
) -> dict[str, Any]:
    expected = list(GATE_CASES[name])
    coverage = gate.get("coverage")
    if not isinstance(coverage, dict):
        blockers.append(f"gate {name}: typed coverage denominator is missing")
        return {"case_ids_total": expected, "case_ids_covered": []}
    total = coverage.get("case_ids_total")
    covered = coverage.get("case_ids_covered")
    if total != expected:
        blockers.append(f"gate {name}: case denominator does not match policy")
    if covered != expected:
        blockers.append(f"gate {name}: case coverage is not exhaustive")
    pointer = f"/gate_cases/{name}"
    evidence_pointer = f"/gate_evidence/{name}"
    if not any(
        contract["assertions"].get(pointer) == expected
        and contract["assertions"].get(evidence_pointer) == _evidence_hashes(gate)
        for contract in _valid_contracts(gate)
    ):
        blockers.append(
            f"gate {name}: no verifier contract binds the fixed case and evidence IDs"
        )
    return {"case_ids_total": total, "case_ids_covered": covered}


def _check_rom_gate(
    root: Path, gate: dict[str, Any], blockers: list[str]
) -> dict[str, Any]:
    evidence = _evidence_list(gate.get("evidence")) or []
    binding = next(
        (item for item in evidence if item["path"] == "sequel/rom-byte-coverage.json"),
        None,
    )
    if binding is None:
        blockers.append("gate rom_byte_coverage: canonical coverage manifest is missing")
        return {"verified": False, "semantic_classification_complete": False}
    path = _repo_file(
        root,
        binding["path"],
        "gate rom_byte_coverage: canonical manifest",
        blockers,
    )
    if path is None:
        return {"verified": False, "semantic_classification_complete": False}
    try:
        report = audit_rom_manifest(root, _read_object(path, "ROM coverage manifest"))
    except ValueError as error:
        blockers.append(f"gate rom_byte_coverage: {error}")
        return {"verified": False, "semantic_classification_complete": False}
    report_errors = report.get("errors")
    if isinstance(report_errors, list):
        for error in report_errors:
            blockers.append(
                f"gate rom_byte_coverage: coverage audit error: {error}"
            )
    if not report.get("verified"):
        blockers.append("gate rom_byte_coverage: coverage manifest is not reproducible")
    if not report.get("state_inventory_complete"):
        blockers.append("gate rom_byte_coverage: byte-state inventory is incomplete")
    if not report.get("semantic_classification_complete"):
        blockers.append("gate rom_byte_coverage: semantic classification is incomplete")
    return report


def _check_similar_table_candidates(
    root: Path, gate: dict[str, Any], blockers: list[str]
) -> dict[str, Any]:
    evidence = _evidence_list(gate.get("evidence")) or []
    canonical_path = "sequel/similar-table-candidates-v1.json"
    adjudication_path = "sequel/similar-table-adjudications-v1.json"
    binding = next(
        (item for item in evidence if item["path"] == canonical_path),
        None,
    )
    if binding is None:
        blockers.append(
            "gate rom_byte_coverage: canonical pointer-table candidate manifest is missing"
        )
        return {"verified": False, "candidate_count": 0, "open_candidate_count": 0}
    adjudication_binding = next(
        (item for item in evidence if item["path"] == adjudication_path),
        None,
    )
    if adjudication_binding is None:
        blockers.append(
            "gate rom_byte_coverage: canonical pointer-table adjudication manifest is missing"
        )
        return {"verified": False, "candidate_count": 0, "open_candidate_count": 0}
    path = _repo_file(
        root,
        binding["path"],
        "gate rom_byte_coverage: pointer-table candidate manifest",
        blockers,
    )
    if path is None:
        return {"verified": False, "candidate_count": 0, "open_candidate_count": 0}
    adjudication_file = _repo_file(
        root,
        adjudication_binding["path"],
        "gate rom_byte_coverage: pointer-table adjudication manifest",
        blockers,
    )
    if adjudication_file is None:
        return {"verified": False, "candidate_count": 0, "open_candidate_count": 0}
    try:
        report = verify_similar_table_manifest(
            root,
            _read_object(path, "pointer-table candidate manifest"),
            _read_object(
                adjudication_file, "pointer-table candidate adjudication manifest"
            ),
        )
    except ValueError as error:
        blockers.append(f"gate rom_byte_coverage: {error}")
        return {"verified": False, "candidate_count": 0, "open_candidate_count": 0}
    if not report.get("verified"):
        blockers.append(
            "gate rom_byte_coverage: pointer-table candidate manifest is not reproducible"
        )
    open_count = report.get("open_candidate_count")
    if not isinstance(open_count, int) or open_count != 0:
        blockers.append(
            f"gate rom_byte_coverage: {open_count!r} pointer-table candidates remain open"
        )
    return report


def _verifier_job_count(requested: int) -> int:
    """Bound verifier concurrency by the memory the host actually has free.

    The verifier replay is CPU bound and each worker holds a native trace
    replay in memory.  Running many of them at once on a host that is already
    swapping makes every verifier slower, so the pool shrinks when the
    available memory is low.  One job is always safe.
    """

    jobs = max(1, int(requested))
    try:
        from tools.project_resource_guard import available_physical_memory_mib

        available = float(available_physical_memory_mib().available_physical_mib)
    except Exception:  # pragma: no cover - the guard is optional here
        return jobs
    if available < 2048:
        return 1
    if available < 4096:
        return min(jobs, 2)
    return min(jobs, 4)


def _execute_groups(
    root: Path,
    groups: list[dict[str, Any]],
    rom_coverage_report: dict[str, Any] | None,
    jobs: int,
) -> list[tuple[int, dict[str, Any], list[str], dict[str, Any]]]:
    """Execute the verifier groups and return them in their original order.

    The verifier replay dominates this audit's wall clock: 107 independent
    subprocess verifications used to run one after another.  They do not
    depend on each other, so they run in a bounded thread pool.  The coverage
    verifier is reused in-process and is not a subprocess, so it stays on the
    calling thread.

    The returned list is sorted by the original group index, so the report
    order - and therefore the report digest - does not depend on which
    verifier happened to finish first.
    """

    prepared: list[tuple[int, dict[str, Any], list[str], dict[str, Any]]] = []
    pending: list[tuple[int, dict[str, Any], list[str]]] = []
    for index, group in enumerate(groups):
        local: list[str] = []
        if _is_rom_coverage_command(group["command"]) and rom_coverage_report is not None:
            execution = _reuse_rom_coverage_contract(
                group["labels"][0],
                group["command"],
                group["contract"],
                rom_coverage_report,
                local,
            )
            prepared.append((index, group, local, execution))
        else:
            pending.append((index, group, local))
    if pending:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {
                pool.submit(
                    _execute_contract,
                    root,
                    group["labels"][0],
                    group["command"],
                    group["contract"],
                    local,
                ): (index, group, local)
                for index, group, local in pending
            }
            for future in concurrent.futures.as_completed(futures):
                index, group, local = futures[future]
                prepared.append((index, group, local, future.result()))
    prepared.sort(key=lambda item: item[0])
    return prepared


def _execute_contract(
    root: Path,
    label: str,
    command: list[str],
    contract: dict[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONHASHSEED": "0",
        "LANG": "C",
        "LC_ALL": "C",
    }
    isolated_python = (
        bool(command)
        and Path(command[0]).name.lower().startswith("python")
        and "-I" in command[1:]
    )
    if not isolated_python:
        environment["PYTHONPATH"] = str(root)
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=VERIFIER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        blockers.append(f"{label}: verifier timed out after {VERIFIER_TIMEOUT_SECONDS}s")
        return {"label": label, "command": command, "exit_code": None, "contract_ok": False}
    result = {
        "label": label,
        "command": command,
        "exit_code": completed.returncode,
        "contract_ok": False,
    }
    if completed.returncode != 0:
        blockers.append(
            f"{label}: verifier failed with exit {completed.returncode}: {' '.join(command)}"
        )
        return result
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        blockers.append(f"{label}: verifier stdout is not one JSON object")
        return result
    mismatches = []
    for pointer, expected in contract["assertions"].items():
        try:
            actual = _json_pointer(payload, pointer)
        except KeyError:
            mismatches.append(f"{pointer}=<missing>")
            continue
        if actual != expected:
            mismatches.append(f"{pointer}={actual!r}, expected {expected!r}")
    if mismatches:
        blockers.append(f"{label}: verifier contract mismatch: {'; '.join(mismatches)}")
    else:
        result["contract_ok"] = True
    return result


def _reuse_rom_coverage_contract(
    label: str,
    command: list[str],
    contract: dict[str, Any],
    payload: dict[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    """Validate the coverage CLI contract against the identical in-process audit."""

    result = {
        "label": label,
        "command": command,
        "exit_code": 0,
        "contract_ok": False,
        "execution": "reused-in-process",
    }
    mismatches = []
    for pointer, expected in contract["assertions"].items():
        try:
            actual = _json_pointer(payload, pointer)
        except KeyError:
            mismatches.append(f"{pointer}=<missing>")
            continue
        if actual != expected:
            mismatches.append(f"{pointer}={actual!r}, expected {expected!r}")
    if mismatches:
        blockers.append(f"{label}: verifier contract mismatch: {'; '.join(mismatches)}")
    else:
        result["contract_ok"] = True
    return result


def _is_rom_coverage_command(command: list[str]) -> bool:
    return (
        len(command) == 4
        and Path(command[0]).name.lower().startswith("python")
        and command[1:] == [
            "tools/audit_rom_byte_coverage.py",
            "--root",
            ".",
        ]
    )


def audit_proof(
    root: Path,
    spec_path: Path,
    *,
    execute_verifiers: bool = False,
    trusted_spec_sha256: str | None = None,
    verifier_jobs: int = 4,
) -> dict[str, Any]:
    _require_supported_python()
    root = Path(root).resolve(strict=True)
    requested_spec = Path(spec_path)
    if requested_spec.is_absolute():
        try:
            requested_spec = requested_spec.resolve(strict=True).relative_to(root)
        except (OSError, ValueError) as error:
            raise ValueError("proof spec path escapes repository") from error
    spec_file = _repo_file(root, requested_spec.as_posix(), "proof spec", [])
    if spec_file is None:
        raise ValueError("proof spec path is invalid")
    spec = _read_object(spec_file, "reverse-engineering proof spec")
    blockers: list[str] = []
    commands: list[tuple[str, list[str], dict[str, Any]]] = []

    if spec.get("schema") != SCHEMA:
        blockers.append(f"spec schema is {spec.get('schema')!r}, expected {SCHEMA}")
    claim_status = spec.get("claim_status")
    if claim_status not in {"complete", "incomplete"}:
        blockers.append("claim_status must be complete or incomplete")
    spec_sha256 = _sha256_file(spec_file)
    trust_anchor_verified = False
    if trusted_spec_sha256 is not None:
        if not _is_sha256(trusted_spec_sha256):
            blockers.append("trusted spec SHA-256 is invalid")
        elif trusted_spec_sha256 != spec_sha256:
            blockers.append("trusted spec SHA-256 mismatch")
        else:
            trust_anchor_verified = True
    elif claim_status == "complete":
        blockers.append("complete claim requires an external trusted spec SHA-256")

    base = spec.get("base_rom")
    rom: bytes | None = None
    if not isinstance(base, dict):
        blockers.append("base_rom identity is missing")
    else:
        path = _repo_file(root, base.get("path"), "base_rom", blockers)
        if path is not None:
            rom = path.read_bytes()
            if len(rom) != base.get("size"):
                blockers.append("base_rom size mismatch")
            if hashlib.sha256(rom).hexdigest() != base.get("sha256"):
                blockers.append("base_rom SHA-256 mismatch")

    discovered = tuple(
        path.parent.name
        for path in sorted((root / "sequel/content").glob("*/bank.json"))
    )
    if discovered != EXPECTED_BANKS:
        blockers.append(
            "fixed bank inventory mismatch: "
            f"expected {len(EXPECTED_BANKS)}, discovered {len(discovered)}"
        )
    bank_proofs = _load_bank_proofs(root, spec, blockers)
    if set(bank_proofs) != set(EXPECTED_BANKS):
        blockers.append("bank proof catalog does not match the fixed 32-bank inventory")
    bank_results = [
        _check_bank(
            root,
            slug,
            root / "sequel/content" / slug / "bank.json",
            bank_proofs.get(slug),
            rom,
            blockers,
            commands,
        )
        for slug in EXPECTED_BANKS
    ]

    declared_runtime_record_coverage = {
        "records_total": sum(
            item["declared_records_total"]
            for item in bank_results
            if item.get("classification") == "runtime_verified"
            and isinstance(item.get("declared_records_total"), int)
        ),
        "records_covered": sum(
            item["declared_records_covered"]
            for item in bank_results
            if item.get("classification") == "runtime_verified"
            and isinstance(item.get("declared_records_covered"), int)
        ),
    }

    gates = spec.get("gates")
    gate_results: dict[str, dict[str, Any]] = {}
    if not isinstance(gates, dict):
        blockers.append("proof gates are missing")
        gates = {}
    if set(gates) != set(REQUIRED_GATES):
        blockers.append("gate set does not match the fixed proof policy")
    rom_coverage_report: dict[str, Any] | None = None
    for name in REQUIRED_GATES:
        gate = gates.get(name)
        before = len(blockers)
        details: dict[str, Any] = {}
        if not isinstance(gate, dict):
            blockers.append(f"gate {name}: missing gate object")
        else:
            status = gate.get("status")
            if status != "verified":
                blockers.append(f"gate {name}: status is {status}, expected verified")
            details["coverage"] = _check_gate_coverage(name, gate, blockers)
            details.update(
                _check_bindings(root, f"gate {name}", gate, blockers, commands)
            )
            if name == "rom_byte_coverage":
                details["rom_coverage_audit"] = _check_rom_gate(root, gate, blockers)
                rom_coverage_report = details["rom_coverage_audit"]
                details["similar_table_candidate_audit"] = (
                    _check_similar_table_candidates(root, gate, blockers)
                )
        gate_results[name] = {
            **details,
            "complete": len(blockers) == before,
            "blockers": blockers[before:],
        }

    if claim_status == "complete" and not execute_verifiers:
        blockers.append("complete claim requires verifier execution")
    verifier_results: list[dict[str, Any]] = []
    if execute_verifiers:
        grouped_commands: dict[
            tuple[str, ...], dict[str, Any]
        ] = {}
        for label, command, contract in commands:
            key = tuple(command) + (json.dumps(contract, sort_keys=True),)
            group = grouped_commands.setdefault(
                key,
                {"labels": [], "command": command, "contract": contract},
            )
            if label not in group["labels"]:
                group["labels"].append(label)

        bank_results_by_label = {item["bank"]: item for item in bank_results}
        gate_results_by_label = {
            f"gate {name}": item for name, item in gate_results.items()
        }

        def _record_execution(group, execution, execution_blockers):
            labels = group["labels"]
            execution["labels"] = labels
            verifier_results.append(execution)
            if execution["contract_ok"]:
                return

            failure = "; ".join(execution_blockers) or "unknown verifier failure"
            for label in labels:
                blocker = (
                    f"{label}: verifier execution did not satisfy its contract: "
                    f"{failure}"
                )
                blockers.append(blocker)
                subject = bank_results_by_label.get(label)
                if subject is None:
                    subject = gate_results_by_label.get(label)
                if subject is not None:
                    subject["blockers"].append(blocker)
                    subject["complete"] = False

        # The verifier replay dominates this audit's wall clock: 107 independent
        # subprocess verifications were executed one after another.  They do not
        # depend on each other, so they run in a bounded thread pool.  The
        # results are re-sorted by their original group index, so the report
        # order (and therefore the report digest) is unchanged.
        groups = list(grouped_commands.values())
        prepared = _execute_groups(
            root, groups, rom_coverage_report, _verifier_job_count(verifier_jobs)
        )
        for _index, group, execution_blockers, execution in prepared:
            _record_execution(group, execution, execution_blockers)

    if claim_status != "complete":
        blockers.append(f"claim_status is {claim_status}, expected complete")
    return {
        "schema": "reverse-engineering-proof-audit-v2",
        "claim_status": claim_status,
        "complete": not blockers,
        "trust_anchor": {
            "spec_sha256": spec_sha256,
            "externally_supplied": trusted_spec_sha256 is not None,
            "verified": trust_anchor_verified,
        },
        "bank_count": len(bank_results),
        "banks_complete": sum(item["complete"] for item in bank_results),
        "banks_proof_bound": sum(item["proof_bound"] for item in bank_results),
        "banks_with_valid_evidence": sum(
            item.get("evidence_valid") is True for item in bank_results
        ),
        "banks_with_hash_bound_offline_verifier": sum(
            item.get("hash_bound_verifier_count", 0) > 0 for item in bank_results
        ),
        "banks_with_contracted_verifier": sum(
            item.get("contracted_verifier_count", 0) > 0 for item in bank_results
        ),
        "declared_runtime_record_coverage": declared_runtime_record_coverage,
        "bank_results": bank_results,
        "gate_results": gate_results,
        "verifiers_executed": verifier_results,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("sequel/reverse-engineering-proof.json"),
    )
    parser.add_argument("--execute-verifiers", action="store_true")
    parser.add_argument(
        "--verifier-jobs",
        type=int,
        default=4,
        help=(
            "how many verifier subprocesses may run at once; the effective "
            "count is additionally bounded by the host's available memory"
        ),
    )
    parser.add_argument("--trusted-spec-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    try:
        result = audit_proof(
            args.root,
            args.spec,
            execute_verifiers=args.execute_verifiers,
            trusted_spec_sha256=args.trusted_spec_sha256,
            verifier_jobs=args.verifier_jobs,
        )
    except ValueError as error:
        result = {
            "schema": "reverse-engineering-proof-audit-v2",
            "complete": False,
            "blockers": [str(error)],
        }
    except RuntimeError as error:
        # An unsupported interpreter is an environment problem, not missing
        # evidence.  Report it as a refusal instead of a blocker so the two
        # never get confused.
        print(
            json.dumps(
                {
                    "schema": "reverse-engineering-proof-audit-v2",
                    "complete": False,
                    "refused": str(error),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output
        if not output.is_absolute():
            output = Path(args.root) / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.get("complete") or args.allow_incomplete else 1


if __name__ == "__main__":
    raise SystemExit(main())
