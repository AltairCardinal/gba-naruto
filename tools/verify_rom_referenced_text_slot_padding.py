#!/usr/bin/env python3
"""Independently verify fixed referenced-text post-NUL zero padding."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "rom-referenced-text-slot-padding-v1"
VERIFY_SCHEMA = "rom-referenced-text-slot-padding-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SELECTOR_MANIFEST = Path("artifacts/rom-selector-text-bindings-v1/manifest.json")
SELECTOR_MANIFEST_SHA256 = (
    "05cd987a60990ca6b2d3ee187eae963fd6ac8728ef9b42b92d6b37b5dc4bc031"
)
SELECTOR_PAYLOAD = Path(
    "artifacts/rom-selector-text-bindings-v1/selector-text-bindings.json"
)
SELECTOR_PAYLOAD_SHA256 = (
    "8737d04de14949cbbbb9215c892a7776476c4230eb1e2b0c2abbbbe4440ce2eb"
)
SELECTOR_VERIFIER = Path("tools/verify_rom_selector_text_bindings.py")
SELECTOR_VERIFIER_SHA256 = (
    "a68a0d1e036be241bbac84538d5a082c7e76e2c6331ffa1d12cd384dc79e2f18"
)
CHAPTER_MANIFEST = Path("artifacts/rom-chapter-script-inventory-v1/manifest.json")
CHAPTER_MANIFEST_SHA256 = (
    "ad77f775f927b89e4a499ddff82e077c38b2767cd86348b65053cb8ca4136f0e"
)
CHAPTER_PAYLOAD = Path(
    "artifacts/rom-chapter-script-inventory-v1/chapter-script-inventory.json"
)
CHAPTER_PAYLOAD_SHA256 = (
    "813cd10394e5fac239aefd6043437796b1a63f95d8d068d714871b8dd3edcabc"
)
CHAPTER_VERIFIER = Path("tools/verify_rom_chapter_script_inventory.py")
CHAPTER_VERIFIER_SHA256 = (
    "b9bf0203bddd8ca85981bd7957d95171c11187a117447bc5a0e92e384777911c"
)

DIRECT_BASE = 0x5A5AB8
DIRECT_STRIDE = 19
DIRECT_SLOT_IDS = (
    1, 2, 3, 7, 44, 43, 4, 5, 6, 45, 8, 9, 10, 46, 11, 12, 13, 47,
    48, 30, 51, 52, 14, 15, 16, 17, 18, 19, 22, 23, 24, 29, 61, 20,
    21, 31, 49, 56, 50, 25, 26, 27, 28, 53, 54, 62,
)
CONFIGURED_BASE = 0x5A5F65
CONFIGURED_STRIDE = 18
CONFIGURED_SLOT_IDS = tuple(range(1, 32)) + (39, 46, 50, 51, 52, 53, 54)
SPEAKER_BASE = 0x5A57C4
SPEAKER_STRIDE = 12
SPEAKER_IDS = tuple(range(1, 32)) + (35, 36, 37, 41) + tuple(range(43, 55)) + (56, 61)

GROUP_CONTRACTS = {
    "selector_direct": {
        "range_count": 46,
        "padding_bytes": 550,
        "range_denominator_sha256": (
            "647695b786a07f4c226bbad80246b0101d503eeb11912d71da500593812bb023"
        ),
        "packed_sha256": (
            "25778f162c4243167f8eaa876f1b0619e67afc158de7805600471a563ec5e8b7"
        ),
    },
    "selector_configured": {
        "range_count": 38,
        "padding_bytes": 368,
        "range_denominator_sha256": (
            "326f4c14065664e689b9c8245a931beb0a647241874a78953dfbc7dfcc2dddf3"
        ),
        "packed_sha256": (
            "71818ecc26433c32172dd9a3544657971c7078daa2257da7c3c303e08693cb23"
        ),
    },
    "chapter_speaker": {
        "range_count": 49,
        "padding_bytes": 337,
        "range_denominator_sha256": (
            "c2bdff7dad49f5446929b17b0a7fe6d5cd5a2a696c2ab091c5cebcd546912f16"
        ),
        "packed_sha256": (
            "3ad337042948f15072caf3da89730e6cc6d42657af2b2291806c4fd45ee1aae6"
        ),
    },
}
RANGE_DENOMINATOR_SHA256 = (
    "0d565762f2bdfd18a6aa1f8c8cd25da5347da5184fe1c78e37de9c6334259b5a"
)
BUNDLE_SHA256 = "920b0cbd31dee627e4e6f4cd4d7805da10ec58ec47d4be3cb4a2dfc98a3b442b"
PAYLOAD_NAME = "referenced-text-slot-padding.json"
BUNDLE_NAME = "referenced-text-slot-padding.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
IMPLEMENTATION_PATHS = {
    "exporter": Path("tools/export_rom_referenced_text_slot_padding.py"),
    "verifier": Path("tools/verify_rom_referenced_text_slot_padding.py"),
    "test": Path("tests/test_export_rom_referenced_text_slot_padding.py"),
}
SCOPE = {
    "referenced_record_denominators_complete": True,
    "all_suffix_bytes_zero": True,
    "unreferenced_slots_classified": False,
    "nul_or_prefix_bytes_classified_here": False,
    "natural_gameplay_all_records_proven": False,
    "editing_safety_proven": False,
    "zero_padding_safe_allocatable": False,
}
LIMITATIONS = [
    "Only fixed slots referenced by the two accepted source artifacts are included.",
    "The first consumer-valid NUL and all prefix bytes remain owned by the source text claims.",
    "Zero padding is structural evidence, not editable or safely allocatable free space.",
    "Natural gameplay reachability, Unicode semantics, and writeback safety are not claimed.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _vector_hash(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":")).encode())


def _safe_file(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _read_bound(root: Path, relative: Path, expected_sha: str) -> bytes:
    raw = _safe_file(root, relative).read_bytes()
    if _sha(raw) != expected_sha:
        raise ValueError(f"bound source identity changed: {relative}")
    return raw


def _read_json_bound(root: Path, relative: Path, expected_sha: str) -> dict[str, Any]:
    value = json.loads(_read_bound(root, relative, expected_sha))
    if not isinstance(value, dict):
        raise ValueError(f"bound JSON is not an object: {relative}")
    return value


def _load_sources(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    selector_manifest = _read_json_bound(
        root, SELECTOR_MANIFEST, SELECTOR_MANIFEST_SHA256
    )
    selector = _read_json_bound(root, SELECTOR_PAYLOAD, SELECTOR_PAYLOAD_SHA256)
    _read_bound(root, SELECTOR_VERIFIER, SELECTOR_VERIFIER_SHA256)
    if (
        selector_manifest.get("artifact_schema") != "rom-selector-text-bindings-v1"
        or selector_manifest.get("files", {}).get(SELECTOR_PAYLOAD.name)
        != SELECTOR_PAYLOAD_SHA256
        or selector.get("schema") != "rom-selector-text-bindings-v1"
    ):
        raise ValueError("selector source contract changed")

    chapter_manifest = _read_json_bound(root, CHAPTER_MANIFEST, CHAPTER_MANIFEST_SHA256)
    chapter = _read_json_bound(root, CHAPTER_PAYLOAD, CHAPTER_PAYLOAD_SHA256)
    _read_bound(root, CHAPTER_VERIFIER, CHAPTER_VERIFIER_SHA256)
    if (
        chapter_manifest.get("artifact_schema") != "rom-chapter-script-inventory-v1"
        or chapter_manifest.get("files", {}).get(CHAPTER_PAYLOAD.name)
        != CHAPTER_PAYLOAD_SHA256
        or chapter.get("schema") != "rom-chapter-script-inventory-v1"
    ):
        raise ValueError("chapter source contract changed")

    evidence = {
        "selector": {
            "manifest": {"path": SELECTOR_MANIFEST.as_posix(), "sha256": SELECTOR_MANIFEST_SHA256},
            "payload": {"path": SELECTOR_PAYLOAD.as_posix(), "sha256": SELECTOR_PAYLOAD_SHA256},
            "verifier": {"path": SELECTOR_VERIFIER.as_posix(), "sha256": SELECTOR_VERIFIER_SHA256},
        },
        "chapter": {
            "manifest": {"path": CHAPTER_MANIFEST.as_posix(), "sha256": CHAPTER_MANIFEST_SHA256},
            "payload": {"path": CHAPTER_PAYLOAD.as_posix(), "sha256": CHAPTER_PAYLOAD_SHA256},
            "verifier": {"path": CHAPTER_VERIFIER.as_posix(), "sha256": CHAPTER_VERIFIER_SHA256},
        },
    }
    return selector, chapter, evidence


def _nul_end(rom: bytes, start: int, end: int) -> int:
    if not (0 <= start < end <= len(rom)):
        raise ValueError("text slot range is outside the ROM")
    try:
        return start + rom[start:end].index(0) + 1
    except ValueError as error:
        raise ValueError("referenced text slot has no NUL terminator") from error


def _make_record(
    rom: bytes,
    *,
    source_kind: str,
    source_record_id: str,
    source_selector: str,
    consumed: list[int],
    physical: list[int],
    slot_id: int | None = None,
    label_id: int | None = None,
) -> dict[str, Any]:
    start, consumed_end = consumed
    physical_start, physical_end = physical
    if start != physical_start or consumed_end != _nul_end(rom, physical_start, physical_end):
        raise ValueError(f"consumer NUL boundary changed: {source_record_id}")
    if consumed_end >= physical_end:
        raise ValueError(f"referenced slot has no post-NUL suffix: {source_record_id}")
    raw = rom[consumed_end:physical_end]
    if any(raw):
        raise ValueError(f"zero padding changed: {source_record_id}")
    result: dict[str, Any] = {
        "range_id": f"{source_kind}-{source_record_id}",
        "source_kind": source_kind,
        "source_record_id": source_record_id,
        "source_selector": source_selector,
        "source_consumed_range": list(consumed),
        "source_physical_range": list(physical),
        "range": [consumed_end, physical_end],
        "size": len(raw),
        "bytes_sha256": _sha(raw),
        "all_zero": True,
        "safe_allocatable_space_claimed": False,
    }
    if slot_id is not None:
        result["slot_id"] = slot_id
    if label_id is not None:
        result["label_id"] = label_id
    return result


def _summary(records: list[dict[str, Any]], rom: bytes) -> dict[str, Any]:
    ranges = [record["range"] for record in records]
    raw = b"".join(rom[start:end] for start, end in ranges)
    return {
        "range_count": len(records),
        "padding_bytes": len(raw),
        "range_denominator_sha256": _vector_hash(ranges),
        "packed_sha256": _sha(raw),
    }


def derive_records(
    rom: bytes,
    selector: dict[str, Any],
    chapter: dict[str, Any],
) -> tuple[list[dict[str, Any]], bytes, dict[str, dict[str, Any]]]:
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size changed")
    if selector.get("schema") != "rom-selector-text-bindings-v1":
        raise ValueError("selector payload schema changed")
    if chapter.get("schema") != "rom-chapter-script-inventory-v1":
        raise ValueError("chapter payload schema changed")

    source_direct = selector.get("direct_text_candidates", {}).get("records")
    if not isinstance(source_direct, list) or tuple(
        item.get("slot_id") for item in source_direct
    ) != DIRECT_SLOT_IDS:
        raise ValueError("selector direct denominator changed")
    direct = []
    for index, slot_id in enumerate(DIRECT_SLOT_IDS):
        source = source_direct[index]
        physical = [
            DIRECT_BASE + slot_id * DIRECT_STRIDE,
            DIRECT_BASE + (slot_id + 1) * DIRECT_STRIDE,
        ]
        consumed = source.get("consumed_range")
        record = _make_record(
            rom,
            source_kind="selector_direct",
            source_record_id=source.get("record_id", "invalid-direct-record"),
            source_selector=f"/direct_text_candidates/records/{index}",
            consumed=source.get("consumed_range", []),
            physical=physical,
            slot_id=slot_id,
        )
        if (
            source.get("source_id") != index
            or source.get("record_id") != f"direct-source-{index:02d}-slot-{slot_id:02d}"
            or source.get("physical_range") != physical
            or not isinstance(consumed, list)
            or consumed[0] != physical[0]
            or _sha(rom[physical[0]:physical[1]]) != source.get("physical_sha256")
            or _sha(rom[consumed[0]:consumed[1]]) != source.get("consumed_sha256")
        ):
            raise ValueError("selector direct source record changed")
        direct.append(record)

    source_configured = selector.get("configured_text_table", {}).get(
        "referenced_records"
    )
    if not isinstance(source_configured, list) or tuple(
        item.get("slot_id") for item in source_configured
    ) != CONFIGURED_SLOT_IDS:
        raise ValueError("selector configured denominator changed")
    configured = []
    for index, slot_id in enumerate(CONFIGURED_SLOT_IDS):
        source = source_configured[index]
        physical = [
            CONFIGURED_BASE + slot_id * CONFIGURED_STRIDE,
            CONFIGURED_BASE + (slot_id + 1) * CONFIGURED_STRIDE,
        ]
        consumed = source.get("consumed_range")
        record = _make_record(
            rom,
            source_kind="selector_configured",
            source_record_id=source.get("record_id", "invalid-configured-record"),
            source_selector=f"/configured_text_table/referenced_records/{index}",
            consumed=source.get("consumed_range", []),
            physical=physical,
            slot_id=slot_id,
        )
        if (
            source.get("record_id") != f"configured-slot-{slot_id:02d}"
            or source.get("physical_range") != physical
            or not isinstance(consumed, list)
            or consumed[0] != physical[0]
            or _sha(rom[physical[0]:physical[1]]) != source.get("physical_sha256")
            or _sha(rom[consumed[0]:consumed[1]]) != source.get("consumed_sha256")
        ):
            raise ValueError("selector configured source record changed")
        configured.append(record)

    source_speaker = (
        chapter.get("referenced_resources", {})
        .get("speaker_labels", {})
        .get("records")
    )
    if not isinstance(source_speaker, list) or tuple(
        item.get("label_id") for item in source_speaker
    ) != SPEAKER_IDS:
        raise ValueError("chapter speaker denominator changed")
    speaker = []
    for index, label_id in enumerate(SPEAKER_IDS):
        source = source_speaker[index]
        physical = [
            SPEAKER_BASE + label_id * SPEAKER_STRIDE,
            SPEAKER_BASE + (label_id + 1) * SPEAKER_STRIDE,
        ]
        renderer = source.get("renderer_range")
        if (
            source.get("slot_range") != physical
            or not isinstance(renderer, list)
            or renderer[0] != physical[0]
            or source.get("size") != renderer[1] - renderer[0]
            or _sha(rom[renderer[0]:renderer[1]]) != source.get("bytes_sha256")
        ):
            raise ValueError("chapter speaker source record changed")
        speaker.append(
            _make_record(
                rom,
                source_kind="chapter_speaker",
                source_record_id=f"speaker-label-{label_id:02d}",
                source_selector=f"/referenced_resources/speaker_labels/records/{index}",
                consumed=renderer,
                physical=physical,
                label_id=label_id,
            )
        )

    grouped = {
        "selector_direct": direct,
        "selector_configured": configured,
        "chapter_speaker": speaker,
    }
    summaries = {name: _summary(items, rom) for name, items in grouped.items()}
    if summaries != GROUP_CONTRACTS:
        raise ValueError(f"padding group denominator changed: {summaries}")
    records = sorted(
        (item for items in grouped.values() for item in items),
        key=lambda item: (item["range"][0], item["range"][1], item["range_id"]),
    )
    bundle = bytearray()
    previous_end = -1
    for record in records:
        start, end = record["range"]
        if start < previous_end:
            raise ValueError("padding ranges overlap")
        previous_end = end
        cursor = len(bundle)
        bundle.extend(rom[start:end])
        record["packed_range"] = [cursor, len(bundle)]
    if _vector_hash([item["range"] for item in records]) != RANGE_DENOMINATOR_SHA256:
        raise ValueError("combined padding range denominator changed")
    if _sha(bytes(bundle)) != BUNDLE_SHA256 or any(bundle):
        raise ValueError("combined zero padding bundle changed")
    return records, bytes(bundle), summaries


def _implementation(root: Path) -> dict[str, dict[str, str]]:
    return {
        key: {"path": relative.as_posix(), "sha256": _sha(_safe_file(root, relative).read_bytes())}
        for key, relative in IMPLEMENTATION_PATHS.items()
    }


def rebuild_payload(root: Path) -> tuple[dict[str, Any], bytes]:
    root = root.resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("fixed ROM identity changed")
    selector, chapter, sources = _load_sources(root)
    records, bundle, summaries = derive_records(rom, selector, chapter)
    summary = {
        "padding_range_count": 133,
        "padding_bytes": 1_255,
        "zero_byte_count": 1_255,
        "packed_bytes": 1_255,
        "range_overlap_bytes": 0,
        "range_denominator_sha256": RANGE_DENOMINATOR_SHA256,
        "bundle_sha256": BUNDLE_SHA256,
    }
    if len(records) != 133 or len(bundle) != 1_255:
        raise ValueError("padding summary changed")
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "sources": sources,
        "group_summaries": summaries,
        "classified_ranges": records,
        "summary": summary,
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": BUNDLE_SHA256}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": _implementation(root),
    }
    return payload, bundle


def _success_report(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "artifact_schema": SCHEMA,
        "verified": True,
        "padding_range_count": 133,
        "padding_bytes": 1_255,
        "zero_byte_count": 1_255,
        "packed_bytes": 1_255,
        "range_overlap_bytes": 0,
        "bundle_sha256": BUNDLE_SHA256,
        "group_summaries": payload["group_summaries"],
        "errors": [],
    }


def _expected_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {name: _sha(raw) for name, raw in sorted(files.items())},
        "scope": SCOPE,
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_referenced_text_slot_padding.py",
                "--root",
                ".",
                "--output-dir",
                f"artifacts/{SCHEMA}",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_referenced_text_slot_padding.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier"]["sha256"],
            "exit_code": 0,
            "report": _success_report(payload),
        },
    }


def _artifact_file(artifact: Path, name: str) -> Path:
    path = artifact / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"artifact member is missing or unsafe: {name}")
    return path


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact path uses a symlink")
        if not cursor.exists():
            break
    return requested


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    try:
        root = root.resolve(strict=True)
        requested = artifact_dir.expanduser()
        if not requested.is_absolute():
            requested = root / requested
        requested = _reject_symlink_components(requested)
        artifact = requested.resolve(strict=True)
        if not artifact.is_dir():
            raise ValueError("artifact path is not a directory")
        members = list(artifact.iterdir())
        if (
            {item.name for item in members} != EXPECTED_FILES
            or any(item.is_symlink() or not item.is_file() for item in members)
        ):
            raise ValueError("artifact file denominator changed")

        expected_payload, expected_bundle = rebuild_payload(root)
        expected_payload_raw = _canonical_json(expected_payload)
        expected_files = {
            PAYLOAD_NAME: expected_payload_raw,
            BUNDLE_NAME: expected_bundle,
        }
        actual_payload_raw = _artifact_file(artifact, PAYLOAD_NAME).read_bytes()
        actual_bundle = _artifact_file(artifact, BUNDLE_NAME).read_bytes()
        if actual_payload_raw != expected_payload_raw:
            raise ValueError("artifact payload differs from independent reconstruction")
        if actual_bundle != expected_bundle:
            raise ValueError("artifact bundle differs from independent reconstruction")
        actual_manifest = json.loads(
            _artifact_file(artifact, "manifest.json").read_text(encoding="utf-8")
        )
        if actual_manifest != _expected_manifest(expected_payload, expected_files):
            raise ValueError("artifact manifest differs from independent reconstruction")
        return _success_report(expected_payload)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {
            "schema": VERIFY_SCHEMA,
            "artifact_schema": SCHEMA,
            "verified": False,
            "errors": [str(error)],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("verified") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
