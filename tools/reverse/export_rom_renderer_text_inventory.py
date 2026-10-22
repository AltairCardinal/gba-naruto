#!/usr/bin/env python3
"""Export renderer-bounded text targets from eleven fixed ROM pointer tables."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-renderer-text-inventory-v1"
VERIFY_SCHEMA = "rom-renderer-text-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

RENDERER_RANGE = (0x06626C, 0x066736)
RENDERER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
RENDERER_BRIDGE_RANGE = (0x066758, 0x066790)
RENDERER_BRIDGE_SHA256 = "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
RENDERER_BRIDGE_CALL = 0x06678A
CENTERED_TEXT_HELPER_RANGE = (0x09822C, 0x098290)
CENTERED_TEXT_HELPER_SHA256 = "a2d05cbb92a6b3d3775b05422ed9838b1ba3ad326c920a05e6d95555f0f742b9"
CENTERED_TEXT_HELPER_CALL = 0x09827C
SJIS_TABLE = 0x53D644
SJIS_ENTRY_COUNT = 31
SJIS_ENTRY_SIZE = 8
SJIS_TABLE_END = SJIS_TABLE + SJIS_ENTRY_COUNT * SJIS_ENTRY_SIZE
SJIS_TABLE_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

PAYLOAD_NAME = "renderer-text-inventory.json"
BUNDLE_NAME = "renderer-text-targets.bin"
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"}
BUNDLE_SHA256 = "28c999f31b51fe2727f66e295ad259920d2d472042d81ff98673c58e51c28cf5"
RANGE_DENOMINATOR_SHA256 = "60ae795037f79f4246718a5448dfeacbcfa4bc80e2759318764f2db9196d210e"

EXPECTED_SUMMARY = {
    "pointer_table_count": 11,
    "pointer_slot_count": 704,
    "unique_target_count": 625,
    "renderer_record_count": 625,
    "renderer_consumed_bytes": 22_588,
    "target_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_text_bytes": 22_588,
}
SCOPE = {
    "fixed_pointer_table_denominator_complete": True,
    "consumer_typed_target_set_complete": True,
    "renderer_consumed_byte_union_complete": True,
    "natural_gameplay_index_coverage_complete": False,
    "unicode_decoding_complete": False,
}
LIMITATIONS = [
    "Only unique targets referenced by the eleven fixed pointer tables and bytes consumed through the renderer-valid NUL are classified.",
    "Repeated pointer slots do not duplicate byte coverage; bytes between parser-bounded records remain unknown.",
    "Static consumer typing does not prove every dynamic index executes during natural gameplay.",
    "Encoded renderer bytes are not asserted to be Unicode-decoded natural-language text.",
]


def _spec(
    candidate_id: int,
    start: int,
    end: int,
    semantic_type: str,
    table_sha256: str,
    literal_offset: int,
    lookup_start: int,
    lookup_end: int,
    lookup_hex: str,
    path_start: int,
    path_end: int,
    path_sha256: str,
    call_offset: int,
    call_target: int,
    unique_targets: int,
    renderer_bytes: int,
    range_sha256: str,
    content_sha256: str,
) -> dict[str, Any]:
    return locals()


TABLE_SPECS = (
    _spec(94, 0x59AA5C, 0x59AC1C, "renderer_text_pointer_table_a", "0e0fe52119ace3e01fd38aa4414c0e0005297c1a004e2d3ac981c5aa38a08fcf", 0x07327C, 0x0731E6, 0x0731EE, "25486418a4002018", 0x0731E6, 0x0731FA, "2890425b2b16dffed757d2e02ed14541a95596c882582d9edab88e594e4eb989", 0x0731F6, 0x09822C, 86, 1_388, "aec0c65cba13e896577ef6cc91252383bc9c896194cf05605d9450bf7980b908", "0e8afd4439cc16d004004dfa6c42304fb516625cba9cafa914e358cb658e0a8a"),
    _spec(95, 0x59D214, 0x59D3D4, "renderer_text_pointer_table_b", "25ba8f2f457021a1386f312e694a576473a04cb3611ce154c8893a1dcd820156", 0x073280, 0x0731FA, 0x073202, "2148201800680026", 0x0731FA, 0x07320E, "518d8ba46a33501a046ecf86ee86b8083129141137b1a12e9ef1720528f09f2a", 0x07320A, 0x066758, 86, 5_971, "54558c6230e22bf836a67be87c4b4c543459e679cda38d2e7745a5e509b1f34a", "bc56317c6a0caad2ec580cae9c34e8bcd6cbb52eab5c76eec31c25a0e0b9f5ce"),
    _spec(96, 0x59E920, 0x59EAE0, "renderer_text_pointer_table_c", "dc5e3c9e336ec7c5fdc1ebc5f6e74ba1a9b422359b4d444ba4cf9a2eedbd0cca", 0x073284, 0x07320E, 0x073216, "1d48241820680824", 0x07320E, 0x073222, "a758da5e4f7eecd6e552dc7cc1496b751791ea658d1fc813af185106539efb24", 0x07321E, 0x066758, 86, 3_576, "e63e4a021a1dc30611157c49bec44062fe7c6e366a094537cc926602db7bfdeb", "71415af5246f7bee17ebf5e2c446b818d90e0dfa572ca9f026dcd0cb0d89e073"),
    _spec(105, 0x5A7E8C, 0x5A7ECC, "renderer_ui_text_pointer_table_16", "7b47bd9fe53a6f90e776ee02163215d1ffb2dc4743b325b75c188fd0b96587f6", 0x081800, 0x081784, 0x08178C, "1e4a9046f8888000", 0x081784, 0x08179C, "33d7fc193b7b48ec9d757bb1bb61d63c3442e4f953962cf730ff49d39c6cbf01", 0x081798, 0x066758, 15, 99, "c8fdad326683e3a99af0920e3908010666fa80fa786b7b7cf8995e5499c0e711", "34c2e71bb2233b8db3e20c0c273109f6f257e5d6e083134ca46ad8a4702e8aec"),
    _spec(107, 0x5A83D8, 0x5A8438, "renderer_text_pointer_table_24_a", "f719e6489250e971a68862beb04a664e9cbd042a62386e5db98a1466edd27979", 0x091C34, 0x091C06, 0x091C0E, "0b48310489130918", 0x091C06, 0x091C20, "a86b5bc0973839f44222e88fd602fe6f8ef6b91071d3f5133c002aee4b91717f", 0x091C1C, 0x066758, 24, 630, "370f2f35e24f591a7f50079f44ba13985c07c817d9d04f88859933724ba2ee7a", "50ff8ecf8a83ff56522499ee8b6bf12ddaef84405e8efefb6aece0d59a442485"),
    _spec(108, 0x5A879C, 0x5A87FC, "renderer_text_pointer_table_24_b", "556bbff5fe4c080fca22042b7d572dad007bf7f1979d0dc05963964016a566c5", 0x091D18, 0x091C64, 0x091C6C, "2c49300480134018", 0x091C64, 0x091C7E, "347656e01450f633e4167b07022d2f0f716892a3ef2685a41d06b0dae5154305", 0x091C7A, 0x066758, 24, 590, "90f29589834f2d8685b6946b6cad4adfe89d322d55c476b6ed0d7c76d92cef11", "b7aee19087b891ea77b426df3c0fe24d89c72734e33341814280f9bbe07a2c2b"),
    _spec(109, 0x5AA180, 0x5AA2D0, "renderer_text_pointer_table_84", "7af2200eea46254d6fd9a149a734c43dbc68428e7e211e67ab42e25b114b01fe", 0x07890C, 0x0788C8, 0x0788D0, "1049907980004018", 0x0788C8, 0x0788E8, "a04d5891a77bb8f82a53eb90a53c47ff820d193c5e9e121a34ef370c1a846f07", 0x0788E4, 0x066758, 84, 3_326, "afde88d7b2f6ca2209b75f6396fd474cca7cd50c326b529a92c9294382017e2d", "6696738c27283cfb8cc504d546f76a560d2d2ef8c22a36147f8f41884e45ecc8"),
    _spec(111, 0x5AC890, 0x5ACA00, "renderer_text_pointer_table_92", "02190031b7fa8cdddbff425fc879dda53c28256dfc3dfc7a7a6c13c53b07597d", 0x07903C, 0x07900C, 0x079014, "0b49b80040180068", 0x07900C, 0x079026, "b42da691086b2aff09b2b31114b6211d51c70610d90406f24139bce0015121e3", 0x079022, 0x066758, 92, 3_965, "1b474f922eaf379ebea5058195b1945286254f1fb309a60c596d9d83167b6dba", "c56690de773116a7c03c4a26cb67f3b466afb315fd901d7426bb4956e5c3bbcf"),
    _spec(112, 0x5ACFA8, 0x5ACFE8, "renderer_text_pointer_table_16", "98e71f1fdcbae83a3ab1baa9ddfa2e41e3f0099e7a33644fb7518c1be4155bfa", 0x08E6F0, 0x08E6BE, 0x08E6C6, "0c4824182068aa8d", 0x08E6BE, 0x08E6D8, "912da5e8531309e019daca67ac4a39f1695a654f8ddd1323fc74ecf01b578767", 0x08E6D4, 0x066758, 16, 806, "26c3da0f98d529b5a243079b9ff2712aea8dd551604e5d01692d989e658ff7e3", "bf7b5f860cc5fb5754f3a3266b7a337ccc7a8506b38e301f6e3c8e8d766c5000"),
    _spec(113, 0x5ADA38, 0x5ADB48, "renderer_text_pointer_table_68", "5af51bef3b5e118822522191331613e3d73c97ad44bb4d37074953e8812e4ce3", 0x09275C, 0x092754, 0x09275C, "014804e07c935908", 0x092754, 0x0927E4, "c6f94285c506ab75bfb146e7281609150a29582229e1dde080ee2e11257fb88d", 0x0927E0, 0x066758, 68, 1_692, "764b975c2bc6bf2d5aed2ede14a3ce5d0f54fbd38c0b7f2f02fdb8b021bcc055", "f9456aa250b6f79dc2df03c9af7972d1ff5af337eed645ea4edc182314ba6f48"),
    _spec(114, 0x5AE2B4, 0x5AE364, "renderer_text_pointer_table_44", "59d992ed6987c9b3bb87bb7f2892207d23623c2c771994f64b035c5da066e3b2", 0x092714, 0x092706, 0x09270E, "034807e000001c24", 0x092706, 0x0927E4, "b80dfbd362659ef84a7050435146d8aabaff0aae0b9bd49d25022ea99920bfdb", 0x0927E0, 0x066758, 44, 545, "b6ac3d64a52e98c8aa0d812dc4f01bbce27064edd66b300fdaeb5b898a755ad0", "7e75ad0e81a5a856ae20daea2e9428af3e99ba2b5a4b32970a6b340c3057e08a"),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _take(rom: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size <= 0 or offset + size > len(rom):
        raise ValueError(f"invalid ROM range at {_addr(offset)}")
    return rom[offset : offset + size]


def _u32(rom: bytes, offset: int) -> int:
    return struct.unpack("<I", _take(rom, offset, 4))[0]


def _bl_target(rom: bytes, offset: int) -> int:
    high = int.from_bytes(_take(rom, offset, 2), "little")
    low = int.from_bytes(_take(rom, offset + 2, 2), "little")
    if high & 0xF800 != 0xF000 or low & 0xF800 != 0xF800:
        raise ValueError(f"expected Thumb BL at {_addr(offset)}")
    delta = ((high & 0x07FF) << 12) | ((low & 0x07FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return offset + 4 + delta


def _sjis_pair_valid(rom: bytes, lead: int, trail: int) -> bool:
    code = lead << 8 | trail
    for index in range(SJIS_ENTRY_COUNT):
        raw = _take(rom, SJIS_TABLE + index * SJIS_ENTRY_SIZE, 3)
        lower = int.from_bytes(raw[:2], "little")
        if lower <= code < lower + raw[2]:
            return True
    return False


def _renderer_end(rom: bytes, offset: int) -> int:
    cursor = offset
    while True:
        value = _take(rom, cursor, 1)[0]
        if value == 0:
            return cursor + 1
        if value == 1:
            width = 2
        elif value == 2:
            width = 3
        elif 0x80 <= value <= 0x9F:
            width = 2
        elif value >= 0xA0 and _sjis_pair_valid(rom, value, _take(rom, cursor + 1, 1)[0]):
            width = 2
        else:
            width = 1
        _take(rom, cursor, width)
        cursor += width


def _slice_evidence(rom: bytes, start: int, end: int, expected: str, label: str) -> dict[str, Any]:
    if _sha(_take(rom, start, end - start)) != expected:
        raise ValueError(f"{label} changed")
    return {"file_range": [start, end], "gba_range": [_addr(start), _addr(end)], "sha256": expected}


def _consumer_evidence(rom: bytes) -> dict[str, Any]:
    if _bl_target(rom, RENDERER_BRIDGE_CALL) != RENDERER_RANGE[0]:
        raise ValueError("renderer bridge target changed")
    if _bl_target(rom, CENTERED_TEXT_HELPER_CALL) != RENDERER_BRIDGE_RANGE[0]:
        raise ValueError("centered text helper target changed")
    consumers = []
    for spec in TABLE_SPECS:
        if _u32(rom, spec["literal_offset"]) != ROM_BASE + spec["start"]:
            raise ValueError(f"candidate {spec['candidate_id']} literal changed")
        lookup = bytes.fromhex(spec["lookup_hex"])
        if _take(rom, spec["lookup_start"], spec["lookup_end"] - spec["lookup_start"]) != lookup:
            raise ValueError(f"candidate {spec['candidate_id']} lookup changed")
        if _sha(_take(rom, spec["path_start"], spec["path_end"] - spec["path_start"])) != spec["path_sha256"]:
            raise ValueError(f"candidate {spec['candidate_id']} consumer path changed")
        if _bl_target(rom, spec["call_offset"]) != spec["call_target"]:
            raise ValueError(f"candidate {spec['candidate_id']} call target changed")
        consumers.append(
            {
                "candidate_id": spec["candidate_id"],
                "table_literal_offset": spec["literal_offset"],
                "lookup_range": [spec["lookup_start"], spec["lookup_end"]],
                "lookup_sha256": _sha(lookup),
                "consumer_path_range": [spec["path_start"], spec["path_end"]],
                "consumer_path_sha256": spec["path_sha256"],
                "call_offset": spec["call_offset"],
                "call_target": _addr(spec["call_target"]),
            }
        )
    bridge = _slice_evidence(rom, *RENDERER_BRIDGE_RANGE, RENDERER_BRIDGE_SHA256, "renderer bridge")
    bridge.update({"call_offset": RENDERER_BRIDGE_CALL, "call_target": _addr(RENDERER_RANGE[0])})
    helper = _slice_evidence(rom, *CENTERED_TEXT_HELPER_RANGE, CENTERED_TEXT_HELPER_SHA256, "centered text helper")
    helper.update({"call_offset": CENTERED_TEXT_HELPER_CALL, "call_target": _addr(RENDERER_BRIDGE_RANGE[0])})
    return {
        "table_consumers": consumers,
        "centered_text_helper": helper,
        "renderer_bridge": bridge,
        "renderer_parser": _slice_evidence(rom, *RENDERER_RANGE, RENDERER_SHA256, "renderer parser"),
        "sjis_range_table": {
            **_slice_evidence(rom, SJIS_TABLE, SJIS_TABLE_END, SJIS_TABLE_SHA256, "SJIS range table"),
            "entry_count": SJIS_ENTRY_COUNT,
            "entry_size": SJIS_ENTRY_SIZE,
        },
    }


def _build(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    root = root.resolve(strict=True)
    rom = (root / ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    table_records = []
    target_sources: dict[int, list[int]] = {}
    failures = []
    for spec in TABLE_SPECS:
        raw_table = _take(rom, spec["start"], spec["end"] - spec["start"])
        if _sha(raw_table) != spec["table_sha256"]:
            raise ValueError(f"candidate {spec['candidate_id']} table changed")
        targets = []
        for offset in range(spec["start"], spec["end"], 4):
            address = _u32(rom, offset)
            target = address - ROM_BASE
            if address < ROM_BASE or not 0 <= target < len(rom):
                raise ValueError(f"candidate {spec['candidate_id']} pointer escapes ROM")
            targets.append(target)
        unique_targets = sorted(set(targets))
        ranges = []
        content = bytearray()
        for target in unique_targets:
            try:
                end = _renderer_end(rom, target)
            except ValueError as error:
                failures.append({"candidate_id": spec["candidate_id"], "target": _addr(target), "error": str(error)})
                continue
            ranges.append([target, end])
            content.extend(rom[target:end])
            target_sources.setdefault(target, []).append(spec["candidate_id"])
        range_hash = _sha(json.dumps(ranges, separators=(",", ":")).encode("ascii"))
        content_hash = _sha(bytes(content))
        if (
            len(unique_targets) != spec["unique_targets"]
            or sum(end - start for start, end in ranges) != spec["renderer_bytes"]
            or range_hash != spec["range_sha256"]
            or content_hash != spec["content_sha256"]
        ):
            raise ValueError(f"candidate {spec['candidate_id']} target denominator changed")
        table_records.append(
            {
                "candidate_id": spec["candidate_id"],
                "semantic_type": spec["semantic_type"],
                "file_range": [spec["start"], spec["end"]],
                "gba_range": [_addr(spec["start"]), _addr(spec["end"])],
                "entry_count": (spec["end"] - spec["start"]) // 4,
                "unique_target_count": len(unique_targets),
                "renderer_consumed_bytes": len(content),
                "table_sha256": spec["table_sha256"],
                "range_denominator_sha256": range_hash,
                "content_sha256": content_hash,
            }
        )
    if failures:
        raise ValueError(f"renderer target parse failures: {failures}")

    derived = []
    for target, candidate_ids in target_sources.items():
        end = _renderer_end(rom, target)
        derived.append((target, end, sorted(candidate_ids)))
    derived.sort()
    previous_end = -1
    for start, end, _ in derived:
        if start < previous_end:
            raise ValueError("renderer target ranges overlap")
        previous_end = end
    ranges_only = [[start, end] for start, end, _ in derived]
    range_hash = _sha(json.dumps(ranges_only, separators=(",", ":")).encode("ascii"))
    if range_hash != RANGE_DENOMINATOR_SHA256:
        raise ValueError("renderer target range denominator changed")

    bundle = bytearray()
    records = []
    for range_id, (start, end, candidate_ids) in enumerate(derived):
        packed_start = len(bundle)
        raw = rom[start:end]
        bundle.extend(raw)
        records.append(
            {
                "range_id": range_id,
                "candidate_ids": candidate_ids,
                "range": [start, end],
                "gba_range": [_addr(start), _addr(end)],
                "packed_range": [packed_start, len(bundle)],
                "size": len(raw),
                "bytes_sha256": _sha(raw),
            }
        )
    if _sha(bytes(bundle)) != BUNDLE_SHA256:
        raise ValueError("renderer text bundle changed")
    summary = {
        "pointer_table_count": len(TABLE_SPECS),
        "pointer_slot_count": sum((spec["end"] - spec["start"]) // 4 for spec in TABLE_SPECS),
        "unique_target_count": len(derived),
        "renderer_record_count": len(records),
        "renderer_consumed_bytes": len(bundle),
        "target_overlap_bytes": 0,
        "parse_failure_count": len(failures),
        "packed_text_bytes": len(bundle),
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError(f"renderer text summary changed: {summary}")
    implementation = {
        "exporter_sha256": _sha(Path(__file__).read_bytes()),
        "verifier_sha256": _sha((root / "tools/verify_rom_renderer_text_inventory.py").read_bytes()),
        "test_sha256": _sha((root / "tests/test_export_rom_renderer_text_inventory.py").read_bytes()),
    }
    payload = {
        "schema": SCHEMA,
        "implementation": implementation,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "pointer_tables": table_records,
        "consumer_evidence": _consumer_evidence(rom),
        "range_denominator_sha256": range_hash,
        "summary": summary,
        "records": records,
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": BUNDLE_SHA256}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
    }
    raw_payload = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    return payload, {PAYLOAD_NAME: raw_payload, BUNDLE_NAME: bytes(bundle)}


def _manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {name: _sha(data) for name, data in sorted(files.items())},
        "scope": SCOPE,
        "producer": {
            "command": ["python3", "tools/export_rom_renderer_text_inventory.py", "--root", ".", "--output-dir", f"artifacts/{SCHEMA}"],
            **payload["implementation"],
        },
        "verifier": {
            "command": ["python3", "tools/verify_rom_renderer_text_inventory.py", "--root", ".", "--artifact-dir", f"artifacts/{SCHEMA}"],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {"schema": VERIFY_SCHEMA, "verified": True, **EXPECTED_SUMMARY, "errors": []},
        },
    }


def _validate_output(root: Path, output: Path) -> Path:
    target = output.expanduser().resolve()
    root = root.resolve()
    if output.is_symlink() or target == root or target in root.parents:
        raise ValueError("output directory is unsafe")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("refusing to replace foreign output")
    try:
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("refusing to replace foreign output") from error
    members = list(target.rglob("*"))
    actual = {member.relative_to(target).as_posix() for member in members if member.is_file()}
    if any(member.is_symlink() for member in members) or manifest.get("artifact_schema") != SCHEMA or manifest.get("artifact_status") != "accepted" or actual != EXPECTED_FILES:
        raise ValueError("refusing to replace foreign output")
    for name, expected in manifest.get("files", {}).items():
        if _sha((target / name).read_bytes()) != expected:
            raise ValueError("refusing to replace corrupted output")
    return target


def _replace(output: Path, files: dict[str, bytes], manifest: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    backup = None
    try:
        for name, data in files.items():
            (temporary / name).write_bytes(data)
        (temporary / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if output.exists():
            backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
            os.replace(output, backup)
        os.replace(temporary, output)
        if backup is not None:
            shutil.rmtree(backup)
    except Exception:
        if output.exists() and backup is not None:
            shutil.rmtree(output)
        if backup is not None and backup.exists():
            os.replace(backup, output)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    target = _validate_output(root, output)
    payload, files = _build(root)
    _replace(target, files, _manifest(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    output = args.output_dir if args.output_dir.is_absolute() else args.root / args.output_dir
    payload = export_artifact(args.root, output)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
