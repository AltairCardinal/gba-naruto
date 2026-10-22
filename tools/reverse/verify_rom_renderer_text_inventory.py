#!/usr/bin/env python3
"""Independently verify the fixed-ROM renderer text target inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-renderer-text-inventory-v1"
VERIFY_SCHEMA = "rom-renderer-text-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "renderer-text-inventory.json"
BUNDLE_NAME = "renderer-text-targets.bin"
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, "manifest.json"}
BUNDLE_SHA256 = "28c999f31b51fe2727f66e295ad259920d2d472042d81ff98673c58e51c28cf5"
RANGE_DENOMINATOR_SHA256 = "60ae795037f79f4246718a5448dfeacbcfa4bc80e2759318764f2db9196d210e"

PARSER_RANGE = (0x06626C, 0x066736)
PARSER_HASH = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
BRIDGE_RANGE = (0x066758, 0x066790)
BRIDGE_HASH = "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
BRIDGE_CALL = 0x06678A
CENTER_HELPER_RANGE = (0x09822C, 0x098290)
CENTER_HELPER_HASH = "a2d05cbb92a6b3d3775b05422ed9838b1ba3ad326c920a05e6d95555f0f742b9"
CENTER_HELPER_CALL = 0x09827C
SJIS_TABLE = 0x53D644
SJIS_COUNT = 31
SJIS_SIZE = 8
SJIS_END = SJIS_TABLE + SJIS_COUNT * SJIS_SIZE
SJIS_HASH = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

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


def _contract(
    candidate_id: int,
    start: int,
    end: int,
    semantic_type: str,
    table_hash: str,
    literal: int,
    lookup_start: int,
    lookup_hex: str,
    path_start: int,
    path_end: int,
    path_hash: str,
    call: int,
    call_target: int,
    target_count: int,
    byte_count: int,
    ranges_hash: str,
    content_hash: str,
) -> dict[str, Any]:
    return locals()


TABLES = (
    _contract(94, 0x59AA5C, 0x59AC1C, "renderer_text_pointer_table_a", "0e0fe52119ace3e01fd38aa4414c0e0005297c1a004e2d3ac981c5aa38a08fcf", 0x07327C, 0x0731E6, "25486418a4002018", 0x0731E6, 0x0731FA, "2890425b2b16dffed757d2e02ed14541a95596c882582d9edab88e594e4eb989", 0x0731F6, 0x09822C, 86, 1_388, "aec0c65cba13e896577ef6cc91252383bc9c896194cf05605d9450bf7980b908", "0e8afd4439cc16d004004dfa6c42304fb516625cba9cafa914e358cb658e0a8a"),
    _contract(95, 0x59D214, 0x59D3D4, "renderer_text_pointer_table_b", "25ba8f2f457021a1386f312e694a576473a04cb3611ce154c8893a1dcd820156", 0x073280, 0x0731FA, "2148201800680026", 0x0731FA, 0x07320E, "518d8ba46a33501a046ecf86ee86b8083129141137b1a12e9ef1720528f09f2a", 0x07320A, 0x066758, 86, 5_971, "54558c6230e22bf836a67be87c4b4c543459e679cda38d2e7745a5e509b1f34a", "bc56317c6a0caad2ec580cae9c34e8bcd6cbb52eab5c76eec31c25a0e0b9f5ce"),
    _contract(96, 0x59E920, 0x59EAE0, "renderer_text_pointer_table_c", "dc5e3c9e336ec7c5fdc1ebc5f6e74ba1a9b422359b4d444ba4cf9a2eedbd0cca", 0x073284, 0x07320E, "1d48241820680824", 0x07320E, 0x073222, "a758da5e4f7eecd6e552dc7cc1496b751791ea658d1fc813af185106539efb24", 0x07321E, 0x066758, 86, 3_576, "e63e4a021a1dc30611157c49bec44062fe7c6e366a094537cc926602db7bfdeb", "71415af5246f7bee17ebf5e2c446b818d90e0dfa572ca9f026dcd0cb0d89e073"),
    _contract(105, 0x5A7E8C, 0x5A7ECC, "renderer_ui_text_pointer_table_16", "7b47bd9fe53a6f90e776ee02163215d1ffb2dc4743b325b75c188fd0b96587f6", 0x081800, 0x081784, "1e4a9046f8888000", 0x081784, 0x08179C, "33d7fc193b7b48ec9d757bb1bb61d63c3442e4f953962cf730ff49d39c6cbf01", 0x081798, 0x066758, 15, 99, "c8fdad326683e3a99af0920e3908010666fa80fa786b7b7cf8995e5499c0e711", "34c2e71bb2233b8db3e20c0c273109f6f257e5d6e083134ca46ad8a4702e8aec"),
    _contract(107, 0x5A83D8, 0x5A8438, "renderer_text_pointer_table_24_a", "f719e6489250e971a68862beb04a664e9cbd042a62386e5db98a1466edd27979", 0x091C34, 0x091C06, "0b48310489130918", 0x091C06, 0x091C20, "a86b5bc0973839f44222e88fd602fe6f8ef6b91071d3f5133c002aee4b91717f", 0x091C1C, 0x066758, 24, 630, "370f2f35e24f591a7f50079f44ba13985c07c817d9d04f88859933724ba2ee7a", "50ff8ecf8a83ff56522499ee8b6bf12ddaef84405e8efefb6aece0d59a442485"),
    _contract(108, 0x5A879C, 0x5A87FC, "renderer_text_pointer_table_24_b", "556bbff5fe4c080fca22042b7d572dad007bf7f1979d0dc05963964016a566c5", 0x091D18, 0x091C64, "2c49300480134018", 0x091C64, 0x091C7E, "347656e01450f633e4167b07022d2f0f716892a3ef2685a41d06b0dae5154305", 0x091C7A, 0x066758, 24, 590, "90f29589834f2d8685b6946b6cad4adfe89d322d55c476b6ed0d7c76d92cef11", "b7aee19087b891ea77b426df3c0fe24d89c72734e33341814280f9bbe07a2c2b"),
    _contract(109, 0x5AA180, 0x5AA2D0, "renderer_text_pointer_table_84", "7af2200eea46254d6fd9a149a734c43dbc68428e7e211e67ab42e25b114b01fe", 0x07890C, 0x0788C8, "1049907980004018", 0x0788C8, 0x0788E8, "a04d5891a77bb8f82a53eb90a53c47ff820d193c5e9e121a34ef370c1a846f07", 0x0788E4, 0x066758, 84, 3_326, "afde88d7b2f6ca2209b75f6396fd474cca7cd50c326b529a92c9294382017e2d", "6696738c27283cfb8cc504d546f76a560d2d2ef8c22a36147f8f41884e45ecc8"),
    _contract(111, 0x5AC890, 0x5ACA00, "renderer_text_pointer_table_92", "02190031b7fa8cdddbff425fc879dda53c28256dfc3dfc7a7a6c13c53b07597d", 0x07903C, 0x07900C, "0b49b80040180068", 0x07900C, 0x079026, "b42da691086b2aff09b2b31114b6211d51c70610d90406f24139bce0015121e3", 0x079022, 0x066758, 92, 3_965, "1b474f922eaf379ebea5058195b1945286254f1fb309a60c596d9d83167b6dba", "c56690de773116a7c03c4a26cb67f3b466afb315fd901d7426bb4956e5c3bbcf"),
    _contract(112, 0x5ACFA8, 0x5ACFE8, "renderer_text_pointer_table_16", "98e71f1fdcbae83a3ab1baa9ddfa2e41e3f0099e7a33644fb7518c1be4155bfa", 0x08E6F0, 0x08E6BE, "0c4824182068aa8d", 0x08E6BE, 0x08E6D8, "912da5e8531309e019daca67ac4a39f1695a654f8ddd1323fc74ecf01b578767", 0x08E6D4, 0x066758, 16, 806, "26c3da0f98d529b5a243079b9ff2712aea8dd551604e5d01692d989e658ff7e3", "bf7b5f860cc5fb5754f3a3266b7a337ccc7a8506b38e301f6e3c8e8d766c5000"),
    _contract(113, 0x5ADA38, 0x5ADB48, "renderer_text_pointer_table_68", "5af51bef3b5e118822522191331613e3d73c97ad44bb4d37074953e8812e4ce3", 0x09275C, 0x092754, "014804e07c935908", 0x092754, 0x0927E4, "c6f94285c506ab75bfb146e7281609150a29582229e1dde080ee2e11257fb88d", 0x0927E0, 0x066758, 68, 1_692, "764b975c2bc6bf2d5aed2ede14a3ce5d0f54fbd38c0b7f2f02fdb8b021bcc055", "f9456aa250b6f79dc2df03c9af7972d1ff5af337eed645ea4edc182314ba6f48"),
    _contract(114, 0x5AE2B4, 0x5AE364, "renderer_text_pointer_table_44", "59d992ed6987c9b3bb87bb7f2892207d23623c2c771994f64b035c5da066e3b2", 0x092714, 0x092706, "034807e000001c24", 0x092706, 0x0927E4, "b80dfbd362659ef84a7050435146d8aabaff0aae0b9bd49d25022ea99920bfdb", 0x0927E0, 0x066758, 44, 545, "b6ac3d64a52e98c8aa0d812dc4f01bbce27064edd66b300fdaeb5b898a755ad0", "7e75ad0e81a5a856ae20daea2e9428af3e99ba2b5a4b32970a6b340c3057e08a"),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _take(rom: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size <= 0 or offset + size > len(rom):
        raise ValueError(f"invalid ROM range at {_addr(offset)}")
    return rom[offset : offset + size]


def _word(rom: bytes, offset: int) -> int:
    return struct.unpack("<I", _take(rom, offset, 4))[0]


def _thumb_bl(rom: bytes, offset: int) -> int:
    first = int.from_bytes(_take(rom, offset, 2), "little")
    second = int.from_bytes(_take(rom, offset + 2, 2), "little")
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError(f"missing Thumb BL at {_addr(offset)}")
    delta = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return offset + 4 + delta


def _valid_sjis(rom: bytes, first: int, second: int) -> bool:
    code = first << 8 | second
    for index in range(SJIS_COUNT):
        raw = _take(rom, SJIS_TABLE + index * SJIS_SIZE, 3)
        lower = int.from_bytes(raw[:2], "little")
        if lower <= code < lower + raw[2]:
            return True
    return False


def _text_end(rom: bytes, offset: int) -> int:
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
        elif value >= 0xA0 and _valid_sjis(rom, value, _take(rom, cursor + 1, 1)[0]):
            width = 2
        else:
            width = 1
        _take(rom, cursor, width)
        cursor += width


def _evidence(rom: bytes, start: int, end: int, expected: str, label: str) -> dict[str, Any]:
    if _sha(_take(rom, start, end - start)) != expected:
        raise ValueError(f"{label} hash differs")
    return {"file_range": [start, end], "gba_range": [_addr(start), _addr(end)], "sha256": expected}


def _consumer_contract(rom: bytes) -> dict[str, Any]:
    if _thumb_bl(rom, BRIDGE_CALL) != PARSER_RANGE[0]:
        raise ValueError("renderer bridge call differs")
    if _thumb_bl(rom, CENTER_HELPER_CALL) != BRIDGE_RANGE[0]:
        raise ValueError("center helper call differs")
    consumers = []
    for table in TABLES:
        lookup = bytes.fromhex(table["lookup_hex"])
        lookup_end = table["lookup_start"] + len(lookup)
        if _word(rom, table["literal"]) != ROM_BASE + table["start"]:
            raise ValueError(f"candidate {table['candidate_id']} literal differs")
        if _take(rom, table["lookup_start"], len(lookup)) != lookup:
            raise ValueError(f"candidate {table['candidate_id']} lookup differs")
        if _sha(_take(rom, table["path_start"], table["path_end"] - table["path_start"])) != table["path_hash"]:
            raise ValueError(f"candidate {table['candidate_id']} path differs")
        if _thumb_bl(rom, table["call"]) != table["call_target"]:
            raise ValueError(f"candidate {table['candidate_id']} call differs")
        consumers.append(
            {
                "candidate_id": table["candidate_id"],
                "table_literal_offset": table["literal"],
                "lookup_range": [table["lookup_start"], lookup_end],
                "lookup_sha256": _sha(lookup),
                "consumer_path_range": [table["path_start"], table["path_end"]],
                "consumer_path_sha256": table["path_hash"],
                "call_offset": table["call"],
                "call_target": _addr(table["call_target"]),
            }
        )
    bridge = _evidence(rom, *BRIDGE_RANGE, BRIDGE_HASH, "renderer bridge")
    bridge.update({"call_offset": BRIDGE_CALL, "call_target": _addr(PARSER_RANGE[0])})
    helper = _evidence(rom, *CENTER_HELPER_RANGE, CENTER_HELPER_HASH, "center helper")
    helper.update({"call_offset": CENTER_HELPER_CALL, "call_target": _addr(BRIDGE_RANGE[0])})
    return {
        "table_consumers": consumers,
        "centered_text_helper": helper,
        "renderer_bridge": bridge,
        "renderer_parser": _evidence(rom, *PARSER_RANGE, PARSER_HASH, "renderer parser"),
        "sjis_range_table": {
            **_evidence(rom, SJIS_TABLE, SJIS_END, SJIS_HASH, "SJIS table"),
            "entry_count": SJIS_COUNT,
            "entry_size": SJIS_SIZE,
        },
    }


def _derive(rom: bytes) -> tuple[dict[str, Any], bytes]:
    tables = []
    target_sources: dict[int, list[int]] = {}
    failures = []
    for contract in TABLES:
        table_raw = _take(rom, contract["start"], contract["end"] - contract["start"])
        if _sha(table_raw) != contract["table_hash"]:
            raise ValueError(f"candidate {contract['candidate_id']} table differs")
        targets = []
        for offset in range(contract["start"], contract["end"], 4):
            address = _word(rom, offset)
            target = address - ROM_BASE
            if address < ROM_BASE or not 0 <= target < len(rom):
                raise ValueError(f"candidate {contract['candidate_id']} pointer escapes ROM")
            targets.append(target)
        unique = sorted(set(targets))
        ranges = []
        content = bytearray()
        for target in unique:
            try:
                end = _text_end(rom, target)
            except ValueError as error:
                failures.append(str(error))
                continue
            ranges.append([target, end])
            content.extend(rom[target:end])
            target_sources.setdefault(target, []).append(contract["candidate_id"])
        ranges_hash = _sha(json.dumps(ranges, separators=(",", ":")).encode("ascii"))
        content_hash = _sha(bytes(content))
        if len(unique) != contract["target_count"] or len(content) != contract["byte_count"] or ranges_hash != contract["ranges_hash"] or content_hash != contract["content_hash"]:
            raise ValueError(f"candidate {contract['candidate_id']} denominator differs")
        tables.append(
            {
                "candidate_id": contract["candidate_id"],
                "semantic_type": contract["semantic_type"],
                "file_range": [contract["start"], contract["end"]],
                "gba_range": [_addr(contract["start"]), _addr(contract["end"])],
                "entry_count": (contract["end"] - contract["start"]) // 4,
                "unique_target_count": len(unique),
                "renderer_consumed_bytes": len(content),
                "table_sha256": contract["table_hash"],
                "range_denominator_sha256": ranges_hash,
                "content_sha256": content_hash,
            }
        )
    if failures:
        raise ValueError(f"renderer parse failures: {failures}")
    targets = []
    for start, candidate_ids in target_sources.items():
        targets.append((start, _text_end(rom, start), sorted(candidate_ids)))
    targets.sort()
    previous_end = -1
    for start, end, _ in targets:
        if start < previous_end:
            raise ValueError("renderer targets overlap")
        previous_end = end
    range_hash = _sha(json.dumps([[start, end] for start, end, _ in targets], separators=(",", ":")).encode("ascii"))
    if range_hash != RANGE_DENOMINATOR_SHA256:
        raise ValueError("global target range denominator differs")
    bundle = bytearray()
    records = []
    for range_id, (start, end, candidate_ids) in enumerate(targets):
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
        raise ValueError("packed renderer text differs")
    summary = {
        "pointer_table_count": len(TABLES),
        "pointer_slot_count": sum((item["end"] - item["start"]) // 4 for item in TABLES),
        "unique_target_count": len(targets),
        "renderer_record_count": len(records),
        "renderer_consumed_bytes": len(bundle),
        "target_overlap_bytes": 0,
        "parse_failure_count": len(failures),
        "packed_text_bytes": len(bundle),
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError(f"summary differs: {summary}")
    return {
        "pointer_tables": tables,
        "consumer_evidence": _consumer_contract(rom),
        "range_denominator_sha256": range_hash,
        "summary": summary,
        "records": records,
    }, bytes(bundle)


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha((root / "tools/export_rom_renderer_text_inventory.py").read_bytes()),
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "test_sha256": _sha((root / "tests/test_export_rom_renderer_text_inventory.py").read_bytes()),
    }


def _manifest(implementation: dict[str, str], payload_raw: bytes, bundle: bytes) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {BUNDLE_NAME: _sha(bundle), PAYLOAD_NAME: _sha(payload_raw)},
        "scope": SCOPE,
        "producer": {
            "command": ["python3", "tools/export_rom_renderer_text_inventory.py", "--root", ".", "--output-dir", f"artifacts/{SCHEMA}"],
            **implementation,
        },
        "verifier": {
            "command": ["python3", "tools/verify_rom_renderer_text_inventory.py", "--root", ".", "--artifact-dir", f"artifacts/{SCHEMA}"],
            "verifier_sha256": implementation["verifier_sha256"],
            "exit_code": 0,
            "report": {"schema": VERIFY_SCHEMA, "verified": True, **EXPECTED_SUMMARY, "errors": []},
        },
    }


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    summary = {key: 0 for key in EXPECTED_SUMMARY}
    try:
        root = root.resolve(strict=True)
        artifact = artifact.resolve(strict=True)
        if not artifact.is_dir() or artifact.is_symlink():
            raise ValueError("artifact is not a safe directory")
        members = list(artifact.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("artifact contains a symbolic link")
        actual_files = {member.relative_to(artifact).as_posix() for member in members if member.is_file()}
        if actual_files != EXPECTED_FILES:
            raise ValueError("artifact file set differs")
        rom = (root / ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity differs")
        expected, expected_bundle = _derive(rom)
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_raw)
        canonical = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        if payload_raw != canonical:
            raise ValueError("inventory JSON is not canonical")
        bundle = (artifact / BUNDLE_NAME).read_bytes()
        if bundle != expected_bundle or _sha(bundle) != BUNDLE_SHA256:
            raise ValueError("renderer text bundle differs from ROM")
        implementation = _implementation(root)
        expected_payload = {
            "schema": SCHEMA,
            "implementation": implementation,
            "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
            **expected,
            "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": BUNDLE_SHA256}},
            "scope": SCOPE,
            "limitations": LIMITATIONS,
        }
        if payload != expected_payload:
            raise ValueError("inventory claims differ from independent ROM derivation")
        summary = expected["summary"]
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        if manifest != _manifest(implementation, payload_raw, bundle):
            raise ValueError("promotion manifest bindings differ")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {"schema": VERIFY_SCHEMA, "verified": not errors, **summary, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
