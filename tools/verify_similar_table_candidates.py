#!/usr/bin/env python3
"""Rebuild the full-ROM pointer scan and independently verify adjudications."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "similar-table-candidates-v1"
ADJUDICATION_SCHEMA = "similar-table-adjudications-v1"
VERIFICATION_SCHEMA = "similar-table-candidates-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCANNER_PATH = Path("tools/find_similar_tables.py")
VERIFIER_PATH = Path("tools/verify_similar_table_candidates.py")
SCAN_MANIFEST_PATH = Path("sequel/similar-table-candidates-v1.json")
ADJUDICATION_PATH = Path("sequel/similar-table-adjudications-v1.json")
ROM_BASE = 0x08000000
ROW_SIZE = 0x10
MIN_ROWS = 4

CONSUMER_BOUND_OPEN_TABLES = (
    (92, 0x599F5C, 0x599FF4, "value_range_renderer_text_pointer_table_38", "70e722a0521ed49bf2ac43cbbee960295332d4b857115b595163da29f7731110", 0x0874B4, 0x087484, 0x08748C, "0b4880464d460135", "38 contiguous value ranges cover 0x0000..0x017B; runtime input upper bound is not proven"),
    (94, 0x59AA5C, 0x59AC1C, "unclassified_text_resource_pointer_table_a", "0e0fe52119ace3e01fd38aa4414c0e0005297c1a004e2d3ac981c5aa38a08fcf", 0x07327C, 0x0731E6, 0x0731EE, "25486418a4002018"),
    (95, 0x59D214, 0x59D3D4, "unclassified_text_resource_pointer_table_b", "25ba8f2f457021a1386f312e694a576473a04cb3611ce154c8893a1dcd820156", 0x073280, 0x0731FA, 0x073202, "2148201800680026"),
    (96, 0x59E920, 0x59EAE0, "unclassified_text_resource_pointer_table_c", "dc5e3c9e336ec7c5fdc1ebc5f6e74ba1a9b422359b4d444ba4cf9a2eedbd0cca", 0x073284, 0x07320E, 0x073216, "1d48241820680824"),
    (105, 0x5A7E8C, 0x5A7ECC, "unclassified_ui_text_pointer_table_16", "7b47bd9fe53a6f90e776ee02163215d1ffb2dc4743b325b75c188fd0b96587f6", 0x081800, 0x081784, 0x08178C, "1e4a9046f8888000"),
    (106, 0x5A7FCC, 0x5A802C, "unclassified_ui_resource_pointer_table_24", "c71cd2217162483632be4b5b8a104f9c6378be0b3d1d24437e196277347862cc", 0x08E6EC, 0x08E6A4, 0x08E6AC, "1148b40020180068"),
    (107, 0x5A83D8, 0x5A8438, "unclassified_text_pointer_table_24_a", "f719e6489250e971a68862beb04a664e9cbd042a62386e5db98a1466edd27979", 0x091C34, 0x091C06, 0x091C0E, "0b48310489130918"),
    (108, 0x5A879C, 0x5A87FC, "unclassified_text_pointer_table_24_b", "556bbff5fe4c080fca22042b7d572dad007bf7f1979d0dc05963964016a566c5", 0x091D18, 0x091C64, 0x091C6C, "2c49300480134018"),
    (109, 0x5AA180, 0x5AA2D0, "unclassified_text_pointer_table_84", "7af2200eea46254d6fd9a149a734c43dbc68428e7e211e67ab42e25b114b01fe", 0x07890C, 0x0788C8, 0x0788D0, "1049907980004018"),
    (111, 0x5AC890, 0x5ACA00, "unclassified_text_pointer_table_92", "02190031b7fa8cdddbff425fc879dda53c28256dfc3dfc7a7a6c13c53b07597d", 0x07903C, 0x07900C, 0x079014, "0b49b80040180068"),
    (112, 0x5ACFA8, 0x5ACFE8, "unclassified_text_pointer_table_16", "98e71f1fdcbae83a3ab1baa9ddfa2e41e3f0099e7a33644fb7518c1be4155bfa", 0x08E6F0, 0x08E6BE, 0x08E6C6, "0c4824182068aa8d"),
    (113, 0x5ADA38, 0x5ADB48, "unclassified_text_pointer_table_68", "5af51bef3b5e118822522191331613e3d73c97ad44bb4d37074953e8812e4ce3", 0x09275C, 0x092754, 0x09275C, "014804e07c935908"),
    (114, 0x5AE2B4, 0x5AE364, "unclassified_text_pointer_table_44", "59d992ed6987c9b3bb87bb7f2892207d23623c2c771994f64b035c5da066e3b2", 0x092714, 0x092706, 0x09270E, "034807e000001c24"),
)

CONSUMER_BOUND_ALIAS_TABLES = (
    (
        3,
        0x060E34,
        0x060EF0,
        "unclassified_runtime_state_pointer_table_47",
        "d0abb00332b73cd36637dbfcf5a7811622438f9c6382dc8c8ff45b00455d00ae",
        0x08A578,
        0x08A55C,
        0x08A564,
        "0648a10009180868",
        "47-entry structural domain 0..46; runtime maximum is not statically bounded",
    ),
    (
        4,
        0x060EF0,
        0x060FA4,
        "positions_formation_pointer_table_45",
        "d5f04183747f3a68bc9c6e087c89b18a4b71e7a12cf85f6eec589050338594ed",
        0x08A5E4,
        0x08A5CE,
        0x08A5D6,
        "0549a00040180568",
        "positions headers enumerate indices {0,6,8,10,11,12,14}",
    ),
    (
        93,
        0x59A104,
        0x59A1B8,
        "training_slot_pointer_table_45",
        "98b063cc49b8ab7b036b612bd81fb3f564187b54fd963e36c9cdc78909d9876b",
        0x093308,
        0x0932DA,
        0x0932E4,
        "0b49a079800040180068",
        "training slot IDs enumerate the complete index domain 0..44",
    ),
)

INLINE_JUMP_TABLES = (
    (5, 0x064CA0, 0x064CA4, 0x064CE0, "68377623da41fc9aa102c72fa0c877481c0f0471700702336d241688072b2677", "95e80bfdd6dbb99169cfa839cd07d6e9b50074d181bb2d3b3a5adefd76bed328", 0x064CA0, 0x064C92, 0x064C9A, "0349401800688746"),
    (6, 0x06BB28, 0x06BB2C, 0x06BB78, "d5babdb91e01bd35c860dcec33d8c8cd2565a4d2ccd8e3e46b0fe1febeeee28c", "ac31daa0e7d1921c4e614e431bc9dc8c5bd2bee4e5e7aab8c378fe1588100a8b", 0x06BB28, 0x06BB1E, 0x06BB26, "0249401800688746"),
    (7, 0x06BBC0, 0x06BBC8, 0x06BC20, "cf33d063274d581a4e8254c1e033b4381289c827548309f35930a892ab4cc35a", "f2c9a79de874a42ded43bb09b49294ff847f451da7a76d847b83a6e96b89fc3e", 0x06BBC4, 0x06BBB6, 0x06BBBE, "0349401800688746"),
    (8, 0x06C474, 0x06C478, 0x06C564, "41cb264d9021184bad0bf697e0c7fe63b8013493bb65ddab09e3774e1c94b8cd", "a6378714306823e16a833250a54dd4493799e4fa3adf595c8c70600f14f1c55a", 0x06C474, 0x06C468, 0x06C470, "0249401800688746"),
    (9, 0x06D238, 0x06D23C, 0x06D288, "1f22195cf1ba4c69a3cb7a6d3d9c05a3190e12ddfeee9c30670293771a811bcd", "ccfcfe37ffa8ea4aa7f81baa077eb6424706c43235cc4e493346a9a7e4e1cf4b", 0x06D238, 0x06D22E, 0x06D236, "0249401800688746"),
    (10, 0x06EEE4, 0x06EEE8, 0x06EFC4, "82b47bb2fde3baa3ff4e2d04a9dc5391bcf79d0fece99ce76913b66044fd7742", "71a6532c1dee9bcc514d6ae7820c1ba18585d9dd5c6e058cf26ddcf30a1a2825", 0x06EEE4, 0x06EEDA, 0x06EEE2, "0249401800688746"),
    (12, 0x0709A0, 0x0709A4, 0x070A30, "97caea1ad41050561752ce17d02b675fa12bac36706a38c47985a147c9225e19", "e1caafa44b90aba4972dcdd14db24169b2529b1a61548616e74a91e864105d7f", 0x0709A0, 0x070986, 0x07098E, "0649401800688746"),
    (13, 0x071D60, 0x071D64, 0x071DF0, "876b0a9a9b704d58cbce33242cca8261cc639dfb50062cb05e9128cdbd723bb3", "0583e747630c14e2de72582fdad75dbd082e93a7124aaedfa52ea184754d10ba", 0x071D60, 0x071D42, 0x071D4A, "0749401800688746"),
    (15, 0x07B964, 0x07B968, 0x07B9B4, "1f48f7e44ae8ecff54a8d8dc959a5925e995c9e25703d6e252afd3499eef2a23", "6c168e8dbd51ffa8f46f498a4bf93744e7de107b699ccc14be96a8df6125c415", 0x07B964, 0x07B94E, 0x07B956, "0549401800688746"),
    (16, 0x07CAB8, 0x07CABC, 0x07CBB8, "080b2e942d0ce4542318bcec37fe1f7d0df9277e6f55758c2654be185c8bf844", "50f7453fdd7b2458b169706cc50b0ae3602eb4ae7271e36a840f9e14a61c788a", 0x07CAB8, 0x07CA9A, 0x07CAA2, "0749401800688746"),
    (17, 0x07DCD8, 0x07DCDC, 0x07DD28, "67b4994111ffae0c9a12576fdb7ae9f97cab53645be895077c655636c852bce0", "f4719e40bb86451f12ed89f905d6735ec9cae7579abb8ad426778c9d76280cdb", 0x07DCD8, 0x07DCCA, 0x07DCD2, "0349401800688746"),
    (18, 0x07DD60, 0x07DD64, 0x07DDC0, "253fa0080366b109106d7e27ff3a5096a0b7a27ea3c8dacc0559a182df0d7794", "a28413c80887bf7ab097713dde07763e2df352dca32306dfeff3b8cc97c9b187", 0x07DD60, 0x07DD54, 0x07DD5C, "0249401800688746"),
    (19, 0x086430, 0x086434, 0x0864B0, "b1740e6c09e412acead065be049159981800d852484d774eebc66d0b26f36693", "033d26c46530fa8ccd58ea300e7304454b9dbafad3fb35510097f204c8b8ca69", 0x086430, 0x08640E, 0x086416, "0849401800688746"),
    (20, 0x088B3C, 0x088B40, 0x088BBC, "abc181de9ff4d0c009034c3f913598061fe156ca21e662864bdeb13f3b1d0937", "ad8d8be21e468532cc5ccb1a6298dadf87e6e3d3f3e5251394ea7e0893e3c242", 0x088B3C, 0x088B1C, 0x088B24, "0749401800688746"),
    (22, 0x092854, 0x092864, 0x0928F4, "be2ee29092bdabb638e89c71188895b4a3f3384f373e602cd517ee02f9fc48f6", "39c306f9b712169cf51cce8225c6d94ed121c0db3353f78f05e6d8717e203d0b", 0x092860, 0x09284A, 0x092852, "0549401800688746"),
    (24, 0x096340, 0x096344, 0x096480, "199fb3e8a976e9a405c18da20331fc91ec99a5792c92b5b336853d5e9a26bf7c", "d1d0e546e0efa1c403720241192ce5d0eadeba10ee18d8e99274e9e7ac31f117", 0x096340, 0x096336, 0x09633E, "0249401800688746"),
    (26, 0x098840, 0x098848, 0x0988C0, "d473e8212be65f54f056e5d31dfe5451faf9d11f495d13a697d3c482eeb8628c", "406f019152b639c3f7c7e64267845509eaecabe497d6e2e97ee60fc4498a207d", 0x098844, 0x098832, 0x09883A, "0449401800688746"),
    (27, 0x09BCE4, 0x09BCE8, 0x09BD24, "8c44065055357bd89ab6ee75a2a65d71b8d1846fb0786e25314c7eefad47be68", "2ca84a8244941c3ae1a67347f26fc0d4711ba13565fff4d9e5b391ebf1f08027", 0x09BCE4, 0x09BCDA, 0x09BCE2, "0249401800688746"),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _decode_thumb_bl(data: bytes, offset: int) -> int:
    high = _u16(data, offset)
    low = _u16(data, offset + 2)
    if high >> 11 != 0x1E or low >> 11 != 0x1F:
        raise ValueError("Thumb BL encoding changed")
    displacement = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if displacement >= 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def _row_kind(rom: bytes, offset: int) -> str:
    values = [_u32(rom, offset + index * 4) for index in range(4)]
    if all(value == 0 for value in values):
        return "zero"
    pointers = [ROM_BASE <= value < ROM_BASE + len(rom) for value in values]
    if all(pointers):
        return "all_ptrs"
    if any(pointers):
        return "mixed"
    return "other"


def _scan(rom: bytes) -> list[dict[str, int | str]]:
    candidates: list[dict[str, int | str]] = []
    offset = 0
    while offset + ROW_SIZE <= len(rom):
        if _row_kind(rom, offset) != "all_ptrs":
            offset += 4
            continue
        start = offset
        nonzero_rows = 0
        zero_rows = 0
        reused_first_col = 0
        previous_first: int | None = None
        while offset + ROW_SIZE <= len(rom):
            kind = _row_kind(rom, offset)
            if kind not in {"all_ptrs", "zero"}:
                break
            if kind == "zero":
                zero_rows += 1
            else:
                first = _u32(rom, offset)
                if first == previous_first:
                    reused_first_col += 1
                previous_first = first
                nonzero_rows += 1
            offset += ROW_SIZE
        if nonzero_rows >= MIN_ROWS:
            candidates.append(
                {
                    "start": start,
                    "end": offset,
                    "nonzero_rows": nonzero_rows,
                    "zero_gap_rows": zero_rows,
                    "reused_first_col_pairs": reused_first_col,
                    "status": "open",
                }
            )
    return candidates


def build_manifest(root: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    rom = (root / ROM_PATH).read_bytes()
    actual_sha = _sha256(rom)
    if actual_sha != ROM_SHA256:
        raise ValueError(f"base ROM SHA-256 changed: {actual_sha}")
    scanner = root / SCANNER_PATH
    candidates = _scan(rom)
    if len(candidates) != 114:
        raise ValueError(f"strict pointer-table candidate count changed: {len(candidates)}")
    return {
        "schema": SCHEMA,
        "base_rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": actual_sha,
        },
        "producer": {
            "path": SCANNER_PATH.as_posix(),
            "sha256": _sha256(scanner.read_bytes()),
        },
        "parameters": {
            "start": 0,
            "end": len(rom),
            "row_size": ROW_SIZE,
            "min_nonzero_rows": MIN_ROWS,
        },
        "candidate_count": len(candidates),
        "open_candidate_count": len(candidates),
        "candidates": candidates,
        "limitations": [
            "The scan is heuristic and does not enumerate non-pointer or differently shaped structures.",
            "Every candidate remains open until a hash-bound accepted, alias_of, or rejected adjudication is added.",
        ],
    }


def verify_manifest(root: Path, manifest: object) -> dict[str, Any]:
    errors: list[str] = []
    try:
        expected = build_manifest(root)
    except (OSError, ValueError) as error:
        return {
            "schema": VERIFICATION_SCHEMA,
            "verified": False,
            "candidate_count": 0,
            "open_candidate_count": 0,
            "errors": [str(error)],
        }
    if manifest != expected:
        errors.append("manifest differs from strict full-ROM scan")
    return {
        "schema": VERIFICATION_SCHEMA,
        "verified": not errors,
        "candidate_count": expected["candidate_count"],
        "open_candidate_count": expected["open_candidate_count"],
        "errors": errors,
    }


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _load_evidence(root: Path, relative: str) -> tuple[dict[str, Any], str]:
    path = root / relative
    resolved = path.resolve(strict=True)
    if not _inside(resolved, root) or resolved != path.absolute() or not resolved.is_file():
        raise ValueError(f"invalid evidence path: {relative}")
    data = resolved.read_bytes()
    try:
        manifest = json.loads(data)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON evidence {relative}: {error}") from error
    if not isinstance(manifest, dict):
        raise ValueError(f"evidence is not an object: {relative}")
    return manifest, _sha256(data)


def _load_source_evidence(root: Path, relative: str) -> tuple[bytes, str]:
    path = root / relative
    resolved = path.resolve(strict=True)
    if not _inside(resolved, root) or resolved != path.absolute() or not resolved.is_file():
        raise ValueError(f"invalid source evidence path: {relative}")
    data = resolved.read_bytes()
    return data, _sha256(data)


def _require_rom_identity(manifest: dict[str, Any], relative: str) -> None:
    rom = manifest.get("rom")
    if not isinstance(rom, dict) or rom.get("sha256") != ROM_SHA256:
        raise ValueError(f"evidence ROM identity changed: {relative}")


def _canonical_table(
    *,
    rom: bytes,
    start: int,
    end: int,
    semantic_type: str,
    evidence_path: str,
    evidence_sha256: str,
    selector: str,
    priority: int = 50,
) -> dict[str, Any]:
    if not (0 <= start < end <= len(rom)):
        raise ValueError(f"canonical range is outside ROM: {semantic_type}")
    return {
        "semantic_type": semantic_type,
        "range": [start, end],
        "sha256": _sha256(rom[start:end]),
        "evidence": {
            "path": evidence_path,
            "sha256": evidence_sha256,
            "selector": selector,
        },
        "priority": priority,
    }


def _require_rom_slice(
    rom: bytes, start: int, end: int, expected_hex: str, label: str
) -> None:
    if rom[start:end].hex() != expected_hex:
        raise ValueError(f"consumer instruction window changed: {label}")


def _require_pointer_table(
    rom: bytes,
    *,
    start: int,
    end: int,
    expected_sha256: str,
    expected_entries: int,
    expected_zero_entries: int = 0,
    label: str,
) -> None:
    source = rom[start:end]
    if (
        len(source) != expected_entries * 4
        or _sha256(source) != expected_sha256
    ):
        raise ValueError(f"canonical table bytes changed: {label}")
    values = [_u32(rom, offset) for offset in range(start, end, 4)]
    zero_entries = sum(value == 0 for value in values)
    mapped_entries = sum(
        ROM_BASE <= value < ROM_BASE + len(rom) for value in values
    )
    if (
        zero_entries != expected_zero_entries
        or mapped_entries + zero_entries != expected_entries
    ):
        raise ValueError(f"canonical pointer domain changed: {label}")


def _consumer_tables(root: Path, rom: bytes) -> list[dict[str, Any]]:
    """Reconstruct tables whose exact boundaries are proven by consumers."""

    tables: list[dict[str, Any]] = []

    status_path = "notes/battle-status-stage-policy-bindings-20260723.json"
    status, status_sha = _load_evidence(root, status_path)
    if (
        status.get("action_jump_table") != "0x0806FF30"
        or status.get("action_jump_table_sha256")
        != "70e8f03efa99fa88b91aa2bbb6963555c617688855d6414d597aa1cf10e7db1d"
    ):
        raise ValueError("battle-status action jump-table evidence changed")
    _require_rom_slice(
        rom,
        0x06FF10,
        0x06FF24,
        "007d04382d2800d9c0e180000349401800688746",
        "battle-status action dispatch",
    )
    if _u32(rom, 0x06FF2C) != ROM_BASE + 0x06FF30:
        raise ValueError("battle-status action table literal changed")
    _require_pointer_table(
        rom,
        start=0x06FF30,
        end=0x06FFE8,
        expected_sha256=(
            "70e8f03efa99fa88b91aa2bbb6963555c617688855d6414d597aa1cf10e7db1d"
        ),
        expected_entries=46,
        label="battle-status action jump table",
    )
    for start, end, semantic_type, selector in (
        (
            0x06FF2C,
            0x06FF30,
            "battle_status_action_jump_table_literal",
            "/action_jump_table",
        ),
        (
            0x06FF30,
            0x06FFE8,
            "battle_status_action_jump_table",
            "/action_jump_table_sha256",
        ),
    ):
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type=semantic_type,
                evidence_path=status_path,
                evidence_sha256=status_sha,
                selector=selector,
                priority=60,
            )
        )

    effect_path = "notes/battle-action-template-semantics-bindings-20260723.json"
    effect, effect_sha = _load_evidence(root, effect_path)
    resolver = effect.get("evidence", {}).get("resolver_dispatch")
    if (
        effect.get("rom_sha256") != ROM_SHA256
        or not isinstance(resolver, dict)
        or resolver.get("start") != "0x08076F24"
        or resolver.get("end") != "0x08077040"
        or resolver.get("sha256")
        != "e45b03dec38fddb123ab43af2b47a08e7d67e49435cabe64f59dc28d453fbbd4"
    ):
        raise ValueError("battle-effect resolver evidence changed")
    _require_rom_slice(
        rom,
        0x076F24,
        0x076F40,
        "f1893f20084001380a1c3e2800d98ce3800002494018006887460000",
        "battle-effect subtype dispatch",
    )
    if _u32(rom, 0x076F40) != ROM_BASE + 0x076F44:
        raise ValueError("battle-effect subtype table literal changed")
    _require_pointer_table(
        rom,
        start=0x076F44,
        end=0x077040,
        expected_sha256=(
            "bb2f646887a005da8a0430da93bf5ea2268aa42ebc0200f92183f26957623958"
        ),
        expected_entries=63,
        label="battle-effect subtype dispatch table",
    )
    for start, end, semantic_type, selector in (
        (
            0x076F40,
            0x076F44,
            "battle_effect_subtype_dispatch_table_literal",
            "/evidence/resolver_dispatch",
        ),
        (
            0x076F44,
            0x077040,
            "battle_effect_subtype_dispatch_table",
            "/evidence/resolver_dispatch",
        ),
    ):
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type=semantic_type,
                evidence_path=effect_path,
                evidence_sha256=effect_sha,
                selector=selector,
                priority=60,
            )
        )

    scene_path = (
        "artifacts/scene-visual-transition-timelines-v1/"
        "scene-visual-transition-timelines.json"
    )
    scene, scene_sha = _load_evidence(root, scene_path)
    _require_rom_identity(scene, scene_path)
    controller = scene.get("controller_model")
    handlers = controller.get("jump_table_handlers") if isinstance(controller, dict) else None
    if (
        not isinstance(controller, dict)
        or controller.get("jump_table_base") != "0x0808C2FC"
        or not isinstance(handlers, list)
        or len(handlers) != 21
    ):
        raise ValueError("scene-controller jump-table evidence changed")
    _require_rom_slice(
        rom,
        0x08C2E8,
        0x08C2F8,
        "142f00d9d6e0b8000149401800688746",
        "scene-controller dispatch",
    )
    if _u32(rom, 0x08C2F8) != ROM_BASE + 0x08C2FC:
        raise ValueError("scene-controller table literal changed")
    expected_scene_handlers = [int(item["handler"], 16) for item in handlers]
    actual_scene_handlers = [
        _u32(rom, offset) for offset in range(0x08C2FC, 0x08C350, 4)
    ]
    if actual_scene_handlers != expected_scene_handlers:
        raise ValueError("scene-controller handler list changed")
    _require_pointer_table(
        rom,
        start=0x08C2FC,
        end=0x08C350,
        expected_sha256=(
            "5c208504bc18c720d7cbae57394572582a05298ee8485875be52c39d3abb2c39"
        ),
        expected_entries=21,
        label="scene-controller jump table",
    )
    for start, end, semantic_type, selector in (
        (
            0x08C2F8,
            0x08C2FC,
            "scene_controller_jump_table_literal",
            "/controller_model/jump_table_base",
        ),
        (
            0x08C2FC,
            0x08C350,
            "scene_controller_jump_table",
            "/controller_model/jump_table_handlers",
        ),
    ):
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type=semantic_type,
                evidence_path=scene_path,
                evidence_sha256=scene_sha,
                selector=selector,
                priority=60,
            )
        )

    story_path = "sequel/content/story/bank.json"
    story, story_sha = _load_evidence(root, story_path)
    consumer = story.get("consumer")
    if (
        not isinstance(consumer, dict)
        or consumer.get("opcode_dispatch") != "0x080977D8"
        or consumer.get("end_handler") != "0x08097916"
        or consumer.get("render_text_handler") != "0x080978DC"
    ):
        raise ValueError("story opcode consumer evidence changed")
    _require_rom_slice(
        rom,
        0x0977D8,
        0x0977F0,
        "3878392800d925e3800003494018006887460000505e0003",
        "story opcode dispatch",
    )
    if _u32(rom, 0x0977F0) != ROM_BASE + 0x0977F4:
        raise ValueError("story opcode table literal changed")
    _require_pointer_table(
        rom,
        start=0x0977F4,
        end=0x0978DC,
        expected_sha256=(
            "a3d2eb7489c851b040b87afeb6c2a020e15e5b6d9086c57f036be4893b12792d"
        ),
        expected_entries=58,
        label="story opcode dispatch table",
    )
    for start, end, semantic_type, selector in (
        (
            0x0977F0,
            0x0977F4,
            "story_opcode_dispatch_table_literal",
            "/consumer/opcode_dispatch",
        ),
        (
            0x0977F4,
            0x0978DC,
            "story_opcode_dispatch_table",
            "/consumer",
        ),
    ):
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type=semantic_type,
                evidence_path=story_path,
                evidence_sha256=story_sha,
                selector=selector,
                priority=60,
            )
        )

    pitch_path = "artifacts/audio/pitch-step-evidence.json"
    pitch, pitch_sha = _load_evidence(root, pitch_path)
    if (
        pitch.get("scale_table", {}).get("offset") != "0x4645C4"
        or pitch.get("scale_table", {}).get("size") != 180
        or not isinstance(pitch.get("command_handlers"), dict)
        or len(pitch["command_handlers"]) != 8
    ):
        raise ValueError("M4A command-table boundary evidence changed")
    _require_rom_slice(
        rom,
        0x09A234,
        0x09A24C,
        "137801b4500e05d10348824201d3900b00d0002301bc7047",
        "M4A command-table boundary consumer",
    )
    if _u32(rom, 0x09A24C) != ROM_BASE + 0x464534:
        raise ValueError("M4A command-table literal changed")
    _require_pointer_table(
        rom,
        start=0x464534,
        end=0x4645C4,
        expected_sha256=(
            "f18662620047b0851ca5ae6d181ac3810a115870add27bb5119d0612b5f6c6a6"
        ),
        expected_entries=36,
        label="M4A track-command dispatch table",
    )
    tables.append(
        _canonical_table(
            rom=rom,
            start=0x464534,
            end=0x4645C4,
            semantic_type="m4a_track_command_dispatch_table",
            evidence_path=pitch_path,
            evidence_sha256=pitch_sha,
            selector="/command_handlers",
            priority=60,
        )
    )

    message_path = "tools/extract_audio_command_table.py"
    message_source, message_sha = _load_source_evidence(root, message_path)
    for marker in (b"TABLE_OFFSET = 0x599634", b"ENTRY_COUNT = 100"):
        if marker not in message_source:
            raise ValueError("message-command source evidence changed")
    _require_rom_slice(
        rom,
        0x07966C,
        0x079680,
        "0006020ee32a47d8802010400006010e002931d1",
        "message-command upper-bound dispatch",
    )
    _require_rom_slice(
        rom,
        0x0796E4,
        0x0796F4,
        "06498120404210408000401800680021",
        "message-command table indexing",
    )
    if _u32(rom, 0x079700) != ROM_BASE + 0x599634:
        raise ValueError("message-command table literal changed")
    _require_pointer_table(
        rom,
        start=0x599634,
        end=0x5997C4,
        expected_sha256=(
            "cedf35c21b949aeacd8accf29a96856ed1595d3434f2b46bd2c893049fc6410f"
        ),
        expected_entries=100,
        expected_zero_entries=1,
        label="message-command pointer table",
    )
    tables.append(
        _canonical_table(
            rom=rom,
            start=0x599634,
            end=0x5997C4,
            semantic_type="message_command_pointer_table",
            evidence_path=message_path,
            evidence_sha256=message_sha,
            selector="TABLE_OFFSET/ENTRY_COUNT/build_bank",
            priority=60,
        )
    )

    detail_path = "tools/build_skill_detail_runtime_probe.py"
    detail_source, detail_sha = _load_source_evidence(root, detail_path)
    for marker in (b"ACTION_COUNT = 87", b"LOW_DETAIL_NAME_TABLE = 0x085A6D04"):
        if marker not in detail_source:
            raise ValueError("low-detail action source evidence changed")
    _require_rom_slice(
        rom,
        0x071176,
        0x071182,
        "124928788000401800681c9b",
        "low-detail action-name indexing",
    )
    if _u32(rom, 0x0711C0) != ROM_BASE + 0x5A6D04:
        raise ValueError("low-detail action-name table literal changed")
    _require_pointer_table(
        rom,
        start=0x5A6D04,
        end=0x5A6E60,
        expected_sha256=(
            "a9bd263418cf363d7ff4280490576c650a236b6ffe01497a01a79b2edc24e091"
        ),
        expected_entries=87,
        label="low-detail action-name pointer table",
    )
    tables.append(
        _canonical_table(
            rom=rom,
            start=0x5A6D04,
            end=0x5A6E60,
            semantic_type="low_detail_action_name_pointer_table",
            evidence_path=detail_path,
            evidence_sha256=detail_sha,
            selector="LOW_DETAIL_NAME_TABLE/ACTION_COUNT/build_probe",
            priority=60,
        )
    )

    passive_path = "tools/build_battle_catalog_runtime_probe.py"
    passive_source, passive_sha = _load_source_evidence(root, passive_path)
    for marker in (b"PASSIVE_TEXT_TABLES = (0x085A7060", b"PASSIVE_TEXT_COUNT = 45"):
        if marker not in passive_source:
            raise ValueError("passive auxiliary text source evidence changed")
    for start, expected in (
        (0x079698, "0248006e0091002129e00000"),
        (0x0796A8, "0248406e0091002121e00000"),
        (0x0796B8, "0248806e0091002119e00000"),
        (0x0796C8, "02488c3000680091002110e0"),
    ):
        _require_rom_slice(
            rom, start, start + 12, expected, "passive auxiliary text consumer"
        )
    for literal in (0x0796A4, 0x0796B4, 0x0796C4, 0x0796D4):
        if _u32(rom, literal) != ROM_BASE + 0x5A7060:
            raise ValueError("passive auxiliary text table literal changed")
    _require_pointer_table(
        rom,
        start=0x5A7060,
        end=0x5A7114,
        expected_sha256=(
            "1231c8f3ac946f9138d1becab3a330aed1421bedc698c746471e7b4157206b71"
        ),
        expected_entries=45,
        label="passive auxiliary text pointer table",
    )
    tables.append(
        _canonical_table(
            rom=rom,
            start=0x5A7060,
            end=0x5A7114,
            semantic_type="passive_auxiliary_text_pointer_table",
            evidence_path=passive_path,
            evidence_sha256=passive_sha,
            selector="PASSIVE_TEXT_TABLES/PASSIVE_TEXT_COUNT/build_probe",
            priority=60,
        )
    )
    return tables


def _character_tables(root: Path, rom: bytes) -> list[dict[str, Any]]:
    relative = "artifacts/character-battle-visuals-v1/manifest.json"
    manifest, evidence_sha = _load_evidence(root, relative)
    _require_rom_identity(manifest, relative)
    tables: list[dict[str, Any]] = []
    resources = manifest.get("resources")
    if not isinstance(resources, list) or len(resources) != 250:
        raise ValueError("character visual resource denominator changed")
    artifact_root = (root / relative).parent
    for index, resource in enumerate(resources):
        table = resource.get("frame_pointer_table") if isinstance(resource, dict) else None
        if not isinstance(table, dict):
            raise ValueError(f"character resource {index} frame table is missing")
        try:
            start = int(table["gba_pointer"], 16) - ROM_BASE
            size = int(table["size"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"character resource {index} frame table is invalid") from error
        end = start + size
        source = rom[start:end]
        if table.get("sha256") != _sha256(source):
            raise ValueError(f"character resource {index} frame table ROM hash changed")
        file_value = table.get("file")
        if not isinstance(file_value, str) or not file_value:
            raise ValueError(f"character resource {index} frame table file is missing")
        file_path = artifact_root / file_value
        resolved = file_path.resolve(strict=True)
        if (
            not _inside(resolved, artifact_root)
            or resolved != file_path.absolute()
            or resolved.read_bytes() != source
        ):
            raise ValueError(f"character resource {index} extracted frame table changed")
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type="character_battle_frame_pointer_table",
                evidence_path=relative,
                evidence_sha256=evidence_sha,
                selector=f"/resources/{index}/frame_pointer_table",
                priority=100,
            )
        )
    table = manifest.get("table")
    if not isinstance(table, dict):
        raise ValueError("character descriptor table is missing")
    start = table.get("file_offset")
    count = table.get("entry_count")
    size = table.get("entry_size")
    if not all(isinstance(value, int) for value in (start, count, size)):
        raise ValueError("character descriptor table denominator is invalid")
    end = start + count * size
    if count != 558 or size != 16 or table.get("sha256") != _sha256(rom[start:end]):
        raise ValueError("character descriptor table bytes changed")
    tables.append(
        _canonical_table(
            rom=rom,
            start=start,
            end=end,
            semantic_type="character_battle_descriptor_table",
            evidence_path=relative,
            evidence_sha256=evidence_sha,
            selector="/table",
            priority=100,
        )
    )
    return tables


BANK_EVIDENCE = {
    "sequel/content/story/bank.json": "chapter_flow_primary_pointer_table",
    "sequel/content/story-b/bank.json": "chapter_flow_alternate_pointer_table",
    "sequel/content/map-events/bank.json": "map_event_handler_pair_table",
    "sequel/content/data-table-a/bank.json": "profile_text_pointer_table",
    "sequel/content/data-table-b/bank.json": "battle_message_pointer_table",
    "sequel/content/menu-ui/bank.json": "menu_portrait_variant_table",
    "sequel/content/cutscene-scripts/bank.json": (
        "cutscene_visual_resource_pointer_pair_table"
    ),
    "sequel/content/map-sprites/bank.json": (
        "map_sprite_definition_animation_pointer_pair_table"
    ),
}


def _bank_tables(root: Path, rom: bytes) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for relative, semantic_type in BANK_EVIDENCE.items():
        manifest, evidence_sha = _load_evidence(root, relative)
        start = manifest.get("table_offset")
        count = manifest.get("entry_count")
        size = manifest.get("entry_size")
        entries = manifest.get("entries")
        fields = manifest.get("entry_format", {}).get("fields")
        if (
            not all(isinstance(value, int) for value in (start, count, size))
            or not isinstance(entries, list)
            or len(entries) != count
            or not isinstance(fields, list)
        ):
            raise ValueError(f"bank denominator is invalid: {relative}")
        rebuilt = bytearray()
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or entry.get("_raw_offset") != start + index * size:
                raise ValueError(f"bank row offset changed: {relative}#{index}")
            row = bytearray(size)
            covered = set()
            for field in fields:
                if not isinstance(field, dict):
                    raise ValueError(f"bank field schema changed: {relative}")
                offset = field.get("offset")
                field_size = field.get("size")
                name = field.get("name")
                value = entry.get(name) if isinstance(name, str) else None
                if (
                    not isinstance(offset, int)
                    or not isinstance(field_size, int)
                    or not isinstance(value, int)
                    or offset < 0
                    or field_size <= 0
                    or offset + field_size > size
                ):
                    raise ValueError(f"bank field value changed: {relative}#{index}")
                row[offset : offset + field_size] = value.to_bytes(field_size, "little")
                covered.update(range(offset, offset + field_size))
            if covered != set(range(size)):
                raise ValueError(f"bank row schema does not cover all bytes: {relative}")
            rebuilt.extend(row)
        end = start + count * size
        if bytes(rebuilt) != rom[start:end]:
            raise ValueError(f"bank rows do not reproduce ROM bytes: {relative}")
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type=semantic_type,
                evidence_path=relative,
                evidence_sha256=evidence_sha,
                selector="/",
                priority=40,
            )
        )
    return tables


def _battle_effect_tables(root: Path, rom: bytes) -> list[dict[str, Any]]:
    relative = "artifacts/battle-effect-sprite-animations-v1/manifest.json"
    manifest, evidence_sha = _load_evidence(root, relative)
    _require_rom_identity(manifest, relative)
    tables: list[dict[str, Any]] = []
    groups = manifest.get("groups")
    if not isinstance(groups, list) or len(groups) != 18:
        raise ValueError("battle-effect group denominator changed")
    for index, group in enumerate(groups):
        frames = group.get("frames") if isinstance(group, dict) else None
        if (
            not isinstance(frames, list)
            or group.get("frame_count") != len(frames)
            or not isinstance(group.get("definition_pointer_table"), str)
        ):
            raise ValueError(f"battle-effect group {index + 1} frame denominator changed")
        start = int(group["definition_pointer_table"], 16) - ROM_BASE
        rebuilt = b"".join(
            int(frame["component_list_pointer"], 16).to_bytes(4, "little")
            for frame in frames
        )
        end = start + len(rebuilt)
        if rom[start:end] != rebuilt:
            raise ValueError(f"battle-effect group {index + 1} frame pointers changed")
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type="battle_effect_frame_pointer_table",
                evidence_path=relative,
                evidence_sha256=evidence_sha,
                selector=f"/groups/{index}/definition_pointer_table",
                priority=80,
            )
        )
    for key, semantic_type in (
        ("resource_pointer_table", "battle_effect_resource_pointer_table"),
        ("sprite_pair_table", "battle_effect_sprite_pair_table"),
    ):
        table = manifest.get(key)
        if not isinstance(table, dict):
            raise ValueError(f"battle-effect {key} is missing")
        start = table.get("file_offset")
        count = table.get("entry_count")
        size = table.get("entry_size")
        if not all(isinstance(value, int) for value in (start, count, size)):
            raise ValueError(f"battle-effect {key} denominator changed")
        end = start + count * size
        if table.get("sha256") != _sha256(rom[start:end]):
            raise ValueError(f"battle-effect {key} bytes changed")
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type=semantic_type,
                evidence_path=relative,
                evidence_sha256=evidence_sha,
                selector=f"/{key}",
                priority=80,
            )
        )
    return tables


def _menu_portrait_table(root: Path, rom: bytes) -> list[dict[str, Any]]:
    relative = "artifacts/menu-portraits-v1/manifest.json"
    manifest, evidence_sha = _load_evidence(root, relative)
    _require_rom_identity(manifest, relative)
    table = manifest.get("source_table")
    if not isinstance(table, dict):
        raise ValueError("menu portrait source table is missing")
    start = table.get("file_offset")
    count = table.get("entry_count")
    size = table.get("entry_size")
    if not all(isinstance(value, int) for value in (start, count, size)):
        raise ValueError("menu portrait source denominator changed")
    end = start + count * size
    if table.get("sha256") != _sha256(rom[start:end]):
        raise ValueError("menu portrait source bytes changed")
    return [
        _canonical_table(
            rom=rom,
            start=start,
            end=end,
            semantic_type="menu_portrait_source_table",
            evidence_path=relative,
            evidence_sha256=evidence_sha,
            selector="/source_table",
            priority=90,
        )
    ]


CATALOG_TABLES = (
    ("unit_name_pointer_table", "units", "name", "unit_name_table"),
    ("active_action_name_pointer_table", "active_actions", "name", "active_name_table"),
    (
        "active_action_description_pointer_table",
        "active_actions",
        "description",
        "active_description_table",
    ),
    ("passive_name_pointer_table", "passives", "name", "passive_name_table"),
    (
        "passive_description_pointer_table",
        "passives",
        "description",
        "passive_description_table",
    ),
    ("ninja_tool_name_pointer_table", "ninja_tools", "name", "ninja_tool_name_table"),
    (
        "ninja_tool_description_pointer_table",
        "ninja_tools",
        "description",
        "ninja_tool_description_table",
    ),
)


def _catalog_tables(root: Path, rom: bytes) -> list[dict[str, Any]]:
    relative = "notes/battle-content-catalog-20260723.json"
    manifest, evidence_sha = _load_evidence(root, relative)
    _require_rom_identity(manifest, relative)
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("battle content provenance is missing")
    tables: list[dict[str, Any]] = []
    for semantic_type, section, field, provenance_key in CATALOG_TABLES:
        entries = manifest.get(section)
        address = provenance.get(provenance_key)
        if not isinstance(entries, list) or not isinstance(address, str):
            raise ValueError(f"battle content table is missing: {semantic_type}")
        start = int(address, 16) - ROM_BASE
        rebuilt = bytearray()
        for index, entry in enumerate(entries):
            pointer = entry.get(field) if isinstance(entry, dict) else None
            expected_address = ROM_BASE + start + index * 4
            if (
                not isinstance(pointer, dict)
                or int(pointer.get("pointer_entry_address", "-1"), 16)
                != expected_address
            ):
                raise ValueError(f"battle content row address changed: {semantic_type}#{index}")
            value = pointer.get("pointer")
            if value is None:
                integer = 0
            elif isinstance(value, str):
                integer = int(value, 16)
            else:
                raise ValueError(f"battle content pointer changed: {semantic_type}#{index}")
            rebuilt.extend(integer.to_bytes(4, "little"))
        end = start + len(rebuilt)
        if bytes(rebuilt) != rom[start:end]:
            raise ValueError(f"battle content table does not reproduce ROM: {semantic_type}")
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type=semantic_type,
                evidence_path=relative,
                evidence_sha256=evidence_sha,
                selector=f"/{section}",
                priority=70,
            )
        )
    return tables


def _presentation_tables(root: Path, rom: bytes) -> list[dict[str, Any]]:
    relative = "artifacts/battle-presentation-glyphs-v1/manifest.json"
    manifest, evidence_sha = _load_evidence(root, relative)
    rom_identity = manifest.get("rom")
    if not isinstance(rom_identity, dict) or rom_identity.get("sha256") != ROM_SHA256:
        raise ValueError("battle presentation ROM identity changed")
    source_tables = manifest.get("tables")
    if not isinstance(source_tables, dict):
        raise ValueError("battle presentation tables are missing")
    tables: list[dict[str, Any]] = []
    for name, table in source_tables.items():
        if not isinstance(table, dict):
            raise ValueError(f"battle presentation table changed: {name}")
        start = table.get("file_offset")
        end_address = table.get("gba_end")
        if not isinstance(start, int) or not isinstance(end_address, str):
            raise ValueError(f"battle presentation range changed: {name}")
        end = int(end_address, 16) - ROM_BASE
        if table.get("sha256") != _sha256(rom[start:end]):
            raise ValueError(f"battle presentation bytes changed: {name}")
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type=f"battle_presentation_{name}_table",
                evidence_path=relative,
                evidence_sha256=evidence_sha,
                selector=f"/tables/{name}",
                priority=80,
            )
        )
    return tables


def _remaining_candidate_tables(rom: bytes) -> list[dict[str, Any]]:
    """Validate consumer-bound tables and scanner-inline Thumb jump tables."""

    tables: list[dict[str, Any]] = []

    def add_consumer_bound_table(
        record: tuple[Any, ...],
        *,
        expected_zero_entries: int,
        require_unique_literal: bool,
    ) -> None:
        (
            candidate_id,
            start,
            end,
            semantic_type,
            expected_sha256,
            literal_offset,
            window_start,
            window_end,
            window_hex,
            *index_evidence,
        ) = record
        _require_rom_slice(
            rom,
            window_start,
            window_end,
            window_hex,
            f"candidate {candidate_id} table consumer",
        )
        if _u32(rom, literal_offset) != ROM_BASE + start:
            raise ValueError(f"candidate {candidate_id} table-base literal changed")
        if require_unique_literal and rom.count(
            (ROM_BASE + start).to_bytes(4, "little")
        ) != 1:
            raise ValueError(
                f"candidate {candidate_id} table-base literal uniqueness changed"
            )
        _require_pointer_table(
            rom,
            start=start,
            end=end,
            expected_sha256=expected_sha256,
            expected_entries=(end - start) // 4,
            expected_zero_entries=expected_zero_entries,
            label=f"candidate {candidate_id} consumer-bound table",
        )
        table = _canonical_table(
            rom=rom,
            start=start,
            end=end,
            semantic_type=semantic_type,
            evidence_path=ROM_PATH.as_posix(),
            evidence_sha256=ROM_SHA256,
            selector=(
                f"consumer literal 0x{ROM_BASE + literal_offset:08X}; "
                f"instruction window 0x{ROM_BASE + window_start:08X}.."
                f"0x{ROM_BASE + window_end:08X}"
                + (f"; index evidence: {index_evidence[0]}" if index_evidence else "")
            ),
            priority=75,
        )
        table["candidate_id"] = candidate_id
        table["consumer_bound"] = True
        tables.append(table)

    for record in CONSUMER_BOUND_OPEN_TABLES:
        add_consumer_bound_table(
            record,
            expected_zero_entries=0,
            require_unique_literal=False,
        )
    for record in CONSUMER_BOUND_ALIAS_TABLES:
        add_consumer_bound_table(
            record,
            expected_zero_entries=1,
            require_unique_literal=True,
        )

    range_map_start = 0x542204
    range_map_end = 0x54229C
    if (
        _sha256(rom[range_map_start:range_map_end])
        != "d5fc38cb718478c33f58d2175f2b6d35d360e08c83dfcde2a082a3f5852e39c9"
    ):
        raise ValueError("candidate 92 value-range map changed")
    pairs = [
        (_u16(rom, offset), _u16(rom, offset + 2))
        for offset in range(range_map_start, range_map_end, 4)
    ]
    if (
        len(pairs) != 38
        or pairs[0][0] != 0
        or pairs[-1][1] != 0x017B
        or any(lower > upper for lower, upper in pairs)
        or any(left[1] + 1 != right[0] for left, right in zip(pairs, pairs[1:]))
        or _u32(rom, 0x874B8) != 0x02003AD0
        or _u32(rom, 0x874BC) != ROM_BASE + range_map_start
        or _sha256(rom[0x87484:0x874DC])
        != "f03357dd32d0f91c901aa6eae88a34ef733a6a233b1ca28732d27d09b45588c8"
        or _decode_thumb_bl(rom, 0x874DC) != 0x66758
        or _sha256(rom[0x66758:0x66790])
        != "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
        or _decode_thumb_bl(rom, 0x6678A) != 0x6626C
        or _sha256(rom[0x6671C:0x6672A])
        != "25ce574d8e9b4f7158d414ee3ed4c527c07805c68e32e8fcaa9fd008a0c28991"
    ):
        raise ValueError("candidate 92 value-range renderer consumer changed")

    for (
        candidate_id,
        start,
        split,
        end,
        prefix_sha256,
        table_sha256,
        base_literal_offset,
        window_start,
        window_end,
        window_hex,
    ) in INLINE_JUMP_TABLES:
        _require_rom_slice(
            rom,
            window_start,
            window_end,
            window_hex,
            f"candidate {candidate_id} inline jump-table consumer",
        )
        if _u32(rom, base_literal_offset) != ROM_BASE + split:
            raise ValueError(
                f"candidate {candidate_id} inline jump-table base changed"
            )
        if _sha256(rom[start:split]) != prefix_sha256:
            raise ValueError(f"candidate {candidate_id} literal prefix changed")
        _require_pointer_table(
            rom,
            start=split,
            end=end,
            expected_sha256=table_sha256,
            expected_entries=(end - split) // 4,
            label=f"candidate {candidate_id} PC-relative jump table",
        )
        selector = (
            f"PC-relative base literal 0x{ROM_BASE + base_literal_offset:08X}; "
            f"instruction window 0x{ROM_BASE + window_start:08X}.."
            f"0x{ROM_BASE + window_end:08X}"
        )
        tables.extend(
            (
                _canonical_table(
                    rom=rom,
                    start=start,
                    end=split,
                    semantic_type="thumb_dispatch_literal_pool",
                    evidence_path=ROM_PATH.as_posix(),
                    evidence_sha256=ROM_SHA256,
                    selector=selector,
                    priority=75,
                ),
                _canonical_table(
                    rom=rom,
                    start=split,
                    end=end,
                    semantic_type="thumb_pc_relative_jump_table",
                    evidence_path=ROM_PATH.as_posix(),
                    evidence_sha256=ROM_SHA256,
                    selector=selector,
                    priority=75,
                ),
            )
        )

    for start, end, semantic_type, expected_sha256, expected_entries in (
        (
            0x53DF04,
            0x53DF70,
            "unbound_thumb_code_pointer_pool",
            "bcdf9c72e447e025af41a942be262878fd1abd25a2138e5bf06700a136c4504d",
            27,
        ),
        (
            0x53F138,
            0x53F140,
            "map_sprite_callback_pointer_pair",
            "e6db594ec553b63dab55e665c16a5370b156c1ecda9aa712ad63256368789eeb",
            2,
        ),
    ):
        _require_pointer_table(
            rom,
            start=start,
            end=end,
            expected_sha256=expected_sha256,
            expected_entries=expected_entries,
            label=semantic_type,
        )
        tables.append(
            _canonical_table(
                rom=rom,
                start=start,
                end=end,
                semantic_type=semantic_type,
                evidence_path=ROM_PATH.as_posix(),
                evidence_sha256=ROM_SHA256,
                selector="structural pointer domain and adjacent canonical boundary",
                priority=70,
            )
        )
    return tables


def _literal_pool_rejection(
    candidate_id: int, candidate: dict[str, Any], rom: bytes
) -> dict[str, Any] | None:
    if candidate_id != 23:
        return None
    start, end = candidate["start"], candidate["end"]
    if [start, end] != [0x093C38, 0x093C78]:
        raise ValueError("candidate 23 range changed")
    expected_sha256 = (
        "50fd28fd7de3943216662df93b22c645abd3379e16f3b17e3adb232e6b4ee96e"
    )
    if _sha256(rom[start:end]) != expected_sha256:
        raise ValueError("candidate 23 literal-pool bytes changed")
    references: list[tuple[int, int]] = []
    for offset in range(0x093900, start, 2):
        instruction = int.from_bytes(rom[offset : offset + 2], "little")
        if instruction & 0xF800 != 0x4800:
            continue
        literal = ((ROM_BASE + offset + 4) & ~3) + (instruction & 0xFF) * 4
        literal_offset = literal - ROM_BASE
        if start <= literal_offset < end:
            references.append((offset, literal_offset))
    if len(references) != 17 or len({target for _, target in references}) != 16:
        raise ValueError("candidate 23 PC-relative literal references changed")
    return {
        **_decision_base(candidate_id, candidate, rom),
        "status": "rejected",
        "relation": "thumb_literal_pool_not_indexed_table",
        "literal_pool_range": [start, end],
        "literal_pool_sha256": expected_sha256,
        "pc_relative_ldr_reference_count": len(references),
        "distinct_literal_word_count": len({target for _, target in references}),
        "evidence": {
            "path": ROM_PATH.as_posix(),
            "sha256": ROM_SHA256,
            "selector": "17 independent Thumb LDR literals target all 16 words",
        },
    }


def _canonical_tables(root: Path, rom: bytes) -> list[dict[str, Any]]:
    tables = [
        *_character_tables(root, rom),
        *_bank_tables(root, rom),
        *_battle_effect_tables(root, rom),
        *_menu_portrait_table(root, rom),
        *_catalog_tables(root, rom),
        *_presentation_tables(root, rom),
        *_consumer_tables(root, rom),
        *_remaining_candidate_tables(rom),
    ]
    return sorted(
        tables,
        key=lambda item: (
            item["range"][0],
            item["range"][1],
            -item["priority"],
            item["semantic_type"],
        ),
    )


def _table_binding(table: dict[str, Any]) -> dict[str, Any]:
    return {
        "semantic_type": table["semantic_type"],
        "canonical_range": table["range"],
        "canonical_sha256": table["sha256"],
        "evidence": table["evidence"],
    }


def _decision_base(candidate_id: int, candidate: dict[str, Any], rom: bytes) -> dict[str, Any]:
    start = candidate["start"]
    end = candidate["end"]
    return {
        "candidate_id": candidate_id,
        "candidate_range": [start, end],
        "candidate_sha256": _sha256(rom[start:end]),
        "scan_fingerprint": {
            "nonzero_rows": candidate["nonzero_rows"],
            "zero_gap_rows": candidate["zero_gap_rows"],
            "reused_first_col_pairs": candidate["reused_first_col_pairs"],
        },
    }


def _best_parent(parents: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        parents,
        key=lambda item: (
            -item["priority"],
            item["range"][1] - item["range"][0],
            item["semantic_type"],
        ),
    )[0]


def _crossing_partitions(
    start: int, end: int, tables: list[dict[str, Any]], rom: bytes
) -> list[dict[str, Any]] | None:
    by_range: dict[tuple[int, int], dict[str, Any]] = {}
    for table in tables:
        table_start, table_end = table["range"]
        if table_start < end and start < table_end:
            key = (table_start, table_end)
            existing = by_range.get(key)
            if existing is None or table["priority"] > existing["priority"]:
                by_range[key] = table
    overlapping = sorted(by_range.values(), key=lambda item: item["range"])
    cursor = start
    partitions: list[dict[str, Any]] = []
    while cursor < end:
        choices = [
            table
            for table in overlapping
            if table["range"][0] <= cursor < table["range"][1]
        ]
        if not choices:
            return None
        table = sorted(
            choices,
            key=lambda item: (-item["range"][1], -item["priority"], item["semantic_type"]),
        )[0]
        part_end = min(end, table["range"][1])
        partition = {
            "range": [cursor, part_end],
            "sha256": _sha256(rom[cursor:part_end]),
            **_table_binding(table),
        }
        partitions.append(partition)
        cursor = part_end
    if len(partitions) < 2 or len({item["semantic_type"] for item in partitions}) < 2:
        return None
    return partitions


def build_adjudication_manifest(
    root: Path, scan_manifest: dict[str, Any]
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    strict_scan = build_manifest(root)
    if scan_manifest != strict_scan:
        raise ValueError("cannot adjudicate a non-canonical candidate scan")
    rom = (root / ROM_PATH).read_bytes()
    tables = _canonical_tables(root, rom)
    decisions: list[dict[str, Any]] = []
    descriptor = next(
        table
        for table in tables
        if table["semantic_type"] == "character_battle_descriptor_table"
    )
    for candidate_id, candidate in enumerate(strict_scan["candidates"], 1):
        start = candidate["start"]
        end = candidate["end"]
        base = _decision_base(candidate_id, candidate, rom)
        literal_pool_rejection = _literal_pool_rejection(
            candidate_id, candidate, rom
        )
        if literal_pool_rejection is not None:
            decisions.append(literal_pool_rejection)
            continue
        consumer_bound_tables = [
            table
            for table in tables
            if table.get("consumer_bound")
            and table.get("candidate_id") == candidate_id
            and table["range"] == [start, end]
        ]
        if consumer_bound_tables:
            decisions.append(
                {
                    **base,
                    "status": "accepted",
                    "relation": "exact_consumer_bound_table",
                    **_table_binding(_best_parent(consumer_bound_tables)),
                }
            )
            continue
        exact_tables = [
            table
            for table in tables
            if table["semantic_type"]
            in {
                "character_battle_frame_pointer_table",
                "m4a_track_command_dispatch_table",
            }
            and table["range"] == [start, end]
        ]
        if exact_tables:
            decisions.append(
                {
                    **base,
                    "status": "accepted",
                    "relation": "exact_canonical_table",
                    **_table_binding(_best_parent(exact_tables)),
                }
            )
            continue
        descriptor_start, descriptor_end = descriptor["range"]
        if (
            start == descriptor_start
            and end == descriptor_end + ROW_SIZE
            and rom[descriptor_end:end] == bytes(ROW_SIZE)
        ):
            decisions.append(
                {
                    **base,
                    "status": "accepted",
                    "relation": "canonical_table_plus_zero_terminator",
                    **_table_binding(descriptor),
                    "terminal_zero_range": [descriptor_end, end],
                    "terminal_zero_hex": rom[descriptor_end:end].hex(),
                    "terminal_zero_sha256": _sha256(rom[descriptor_end:end]),
                }
            )
            continue
        parents = [
            table
            for table in tables
            if table["range"][0] <= start
            and end <= table["range"][1]
            and table["range"] != [start, end]
        ]
        if parents:
            decisions.append(
                {
                    **base,
                    "status": "alias_of",
                    "relation": "strict_subrange",
                    **_table_binding(_best_parent(parents)),
                }
            )
            continue
        partitions = _crossing_partitions(start, end, tables, rom)
        if partitions is not None:
            decisions.append(
                {
                    **base,
                    "status": "rejected",
                    "relation": "crosses_canonical_table_boundary",
                    "partitions": partitions,
                }
            )
    decision_counts = {
        status: sum(item["status"] == status for item in decisions)
        for status in ("accepted", "alias_of", "rejected")
    }
    if decision_counts != {"accepted": 60, "alias_of": 26, "rejected": 28}:
        raise ValueError(f"evidence-derived decision denominator changed: {decision_counts}")
    scan_path = root / SCAN_MANIFEST_PATH
    return {
        "schema": ADJUDICATION_SCHEMA,
        "base_rom": strict_scan["base_rom"],
        "base_scan": {
            "path": SCAN_MANIFEST_PATH.as_posix(),
            "sha256": _sha256(scan_path.read_bytes()),
            "schema": SCHEMA,
            "candidate_count": strict_scan["candidate_count"],
        },
        "producer": {
            "path": VERIFIER_PATH.as_posix(),
            "sha256": _sha256((root / VERIFIER_PATH).read_bytes()),
        },
        "adjudication_count": len(decisions),
        "decision_counts": decision_counts,
        "open_candidate_count": strict_scan["candidate_count"] - len(decisions),
        "adjudications": decisions,
        "limitations": [
            "Only candidates derivable from current hash-bound canonical tables are adjudicated.",
            "Missing candidate IDs remain open; absence is never interpreted as rejection.",
            "An alias_of decision classifies a strict scanner subrange and does not create a second table.",
            "A rejected decision rejects the scanner's aggregate extent, not the canonical tables partitioning its bytes.",
            "Candidate 3's 47-entry structural domain is consumer-bound, but its runtime index maximum has not been observed dynamically.",
            "Candidate 92 is a strict scanner subrange of a 38-entry value-range renderer-text table; the runtime source at 0x02003AD0 is not statically bounded to 0x0000..0x017B.",
        ],
    }


def verify_repository_manifests(
    root: Path, scan_manifest: object, adjudication_manifest: object
) -> dict[str, Any]:
    errors: list[str] = []
    scan_report = verify_manifest(root, scan_manifest)
    if not scan_report["verified"]:
        errors.extend(scan_report["errors"])
    try:
        strict_scan = build_manifest(root)
        expected = build_adjudication_manifest(root, strict_scan)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {
            "schema": VERIFICATION_SCHEMA,
            "verified": False,
            "candidate_count": 0,
            "adjudicated_candidate_count": 0,
            "open_candidate_count": 0,
            "decision_counts": {"accepted": 0, "alias_of": 0, "rejected": 0},
            "errors": [*errors, str(error)],
        }
    if adjudication_manifest != expected:
        errors.append(
            "adjudication manifest differs from independently rebuilt evidence"
        )
    return {
        "schema": VERIFICATION_SCHEMA,
        "verified": not errors,
        "candidate_count": expected["base_scan"]["candidate_count"],
        "adjudicated_candidate_count": expected["adjudication_count"],
        "open_candidate_count": expected["open_candidate_count"],
        "decision_counts": expected["decision_counts"],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=SCAN_MANIFEST_PATH)
    parser.add_argument("--adjudications", type=Path, default=ADJUDICATION_PATH)
    parser.add_argument(
        "--regenerate-scan",
        action="store_true",
        help="Rewrite the full-ROM scan manifest from the fixed scanner denominator.",
    )
    parser.add_argument(
        "--regenerate-adjudications",
        action="store_true",
        help="Rewrite the adjudication overlay from current canonical evidence.",
    )
    args = parser.parse_args()
    scan_path = args.manifest if args.manifest.is_absolute() else args.root / args.manifest
    adjudication_path = (
        args.adjudications
        if args.adjudications.is_absolute()
        else args.root / args.adjudications
    )
    try:
        if args.regenerate_scan:
            strict_scan = build_manifest(args.root)
            scan_path.parent.mkdir(parents=True, exist_ok=True)
            scan_path.write_text(
                json.dumps(strict_scan, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        scan_manifest = json.loads(scan_path.read_text(encoding="utf-8"))
        if args.regenerate_adjudications:
            expected = build_adjudication_manifest(args.root, scan_manifest)
            adjudication_path.parent.mkdir(parents=True, exist_ok=True)
            adjudication_path.write_text(
                json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        adjudication_manifest = json.loads(adjudication_path.read_text(encoding="utf-8"))
        report = verify_repository_manifests(
            args.root, scan_manifest, adjudication_manifest
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        report = {
            "schema": VERIFICATION_SCHEMA,
            "verified": False,
            "candidate_count": 0,
            "adjudicated_candidate_count": 0,
            "open_candidate_count": 0,
            "decision_counts": {"accepted": 0, "alias_of": 0, "rejected": 0},
            "errors": [str(error)],
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
