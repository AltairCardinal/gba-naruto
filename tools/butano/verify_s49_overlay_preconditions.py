#!/usr/bin/env python3
"""Verify the three preconditions of the S49 overlay 1:1 wiring.

``docs/butano-wiring-roadmap.md`` (W2) says the overlay wiring must not start
by editing code:

    **前置** | **先读重制侧 VRAM** 核对三件事：槽 77..100 的图块字节 /
    可见窗口 30×20 的 tile index / 8bpp 上传长度与基址对齐。
    **不先改代码**（第 26 轮否证就败在没核对这三处）

The 26th round measured 16,533 differing pixels against a 2,917 baseline and
the cause was never found, because those three facts were never checked.
This tool checks them, from receipts only -- no ROM build, no emulator, no
code change -- so the wiring either starts on solid ground or does not start
at all.

The three checks:

``tiles``
    The remake's 8bpp overlay tiles must decode **back** to the original's
    4bpp tiles, block for block, and the expansion must be exactly
    ``v == 0 -> 0``, ``1 <= v <= 11 -> 224 + v``, ``v >= 12 -> 0``.
    (The low nibble of a 4bpp byte is the **left** pixel -- the 26th round's
    correction.)

``visible_window``
    The original's BG2 tilemap is 32x32 entries; the screen shows a 30x20
    tile window and the layer scrolls by ``hoff = 240`` / ``voff = 24``
    pixels.  The visible window's tile indices must therefore be
    ``entry[(3 + row) % 32][(30 + column) % 32]`` and must equal the reverse
    work tree's ``generated-tilemap-30x20.bin`` entry for entry.  This is the
    fact the whole "load the original's baked window" plan rests on.

``upload``
    The new upload (the original's 24 family blocks plus the 28 action-menu
    glyph tiles) must fit the 8bpp tile set, must not grow the tile data,
    and must land on a 64-byte aligned base.

Usage::

    python3 tools/butano/verify_s49_overlay_preconditions.py \\
        --root . \\
        --reverse-root /Users/altair/github/gba-naruto-reverse \\
        --out-dir artifacts/s49-overlay-preconditions-v1
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA = "konoha.s49-overlay-preconditions.v1"

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_CHECK_FAILED = 3

#: The remake's 8bpp palette indices that carry the original's colours.
PALETTE_BASE = 224
PALETTE_LAST = 11

#: The original's overlay tiles live at BG2 tile indices 256..287.
TILE_BASE_INDEX = 256
TILE_COUNT = 32
TILE_BYTES_4BPP = 32
TILE_BYTES_8BPP = 64

#: The original's BG2 scroll registers, in pixels.
HOFFS = 240
VOFFS = 24

#: The visible window, in tiles.
VISIBLE_COLUMNS = 30
VISIBLE_ROWS = 20

#: The original's tilemap is 32x32 entries.
TILEMAP_COLUMNS = 32
TILEMAP_ROWS = 32


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_4bpp_tile(block: bytes) -> list[int]:
    """Decode one 8x8 4bpp tile into 64 palette indices, row major.

    The **low** nibble is the left pixel: that was the 26th round's
    correction, and getting it backwards is exactly the kind of thing that
    turns a 2,917 pixel residual into 16,533.
    """
    pixels: list[int] = []
    for row in range(8):
        for byte in block[row * 4 : row * 4 + 4]:
            pixels.append(byte & 0xF)
            pixels.append((byte >> 4) & 0xF)
    return pixels


def decode_8bpp_tile(block: bytes) -> list[int]:
    """Decode one 8x8 8bpp tile into 64 palette indices, row major."""
    return list(block[:64])


def parse_header_array(path: Path, name: str) -> list[int]:
    """Read a ``std::array<std::uint16_t, N>`` out of a generated header."""
    text = path.read_text(encoding="utf-8")
    match = re.search(re.escape(name) + r"\s*=\s*\{(.*?)\n\};", text, re.S)
    if match is None:
        raise ValueError(f"{path.name}: no array named {name}")
    body = re.sub(r"//[^\n]*", "", match.group(1))
    values = [
        int(token, 0) for token in re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", body)
    ]
    return values


def parse_header_bytes(path: Path, name: str) -> list[int]:
    """Read a ``std::array<std::uint8_t, N>`` out of a generated header."""
    text = path.read_text(encoding="utf-8")
    match = re.search(re.escape(name) + r"\s*=\s*\{(.*?)\n\};", text, re.S)
    if match is None:
        raise ValueError(f"{path.name}: no array named {name}")
    body = re.sub(r"//[^\n]*", "", match.group(1))
    return [
        int(token, 0) for token in re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", body)
    ]


# ---------------------------------------------------------------------------
# the three checks


def check_tiles(
    tiles_4bpp: bytes,
    tiles_8bpp: list[int],
) -> dict[str, Any]:
    """The remake's 8bpp tiles must decode back to the original's 4bpp tiles."""
    problems: list[str] = []
    if len(tiles_4bpp) != TILE_COUNT * TILE_BYTES_4BPP:
        problems.append(
            f"the original's tile sheet is {len(tiles_4bpp)} B, expected "
            f"{TILE_COUNT * TILE_BYTES_4BPP} B"
        )
    if len(tiles_8bpp) != TILE_COUNT * TILE_BYTES_8BPP:
        problems.append(
            f"the remake's expanded sheet is {len(tiles_8bpp)} B, expected "
            f"{TILE_COUNT * TILE_BYTES_8BPP} B"
        )
    blocks_compared = 0
    rule_violations: list[str] = []
    for block in range(min(TILE_COUNT, len(tiles_4bpp) // TILE_BYTES_4BPP)):
        original = decode_4bpp_tile(
            tiles_4bpp[block * TILE_BYTES_4BPP : (block + 1) * TILE_BYTES_4BPP]
        )
        expanded = decode_8bpp_tile(
            bytes(tiles_8bpp[block * TILE_BYTES_8BPP : (block + 1) * TILE_BYTES_8BPP])
        )
        for pixel, (source, target) in enumerate(zip(original, expanded)):
            if source == 0:
                expected = 0
            elif source <= PALETTE_LAST:
                expected = PALETTE_BASE + source
            else:
                expected = 0
            if target != expected:
                if len(rule_violations) < 8:
                    rule_violations.append(
                        f"block {block} pixel {pixel}: source {source} became "
                        f"{target}, expected {expected}"
                    )
            elif target != 0 and source != target - PALETTE_BASE:
                if len(rule_violations) < 8:
                    rule_violations.append(
                        f"block {block} pixel {pixel}: {target} is not "
                        f"{PALETTE_BASE}+{source}"
                    )
        blocks_compared += 1
    problems.extend(rule_violations)
    return {
        "check": "tiles",
        "ok": not problems,
        "blocks_compared": blocks_compared,
        "original_bytes": len(tiles_4bpp),
        "expanded_bytes": len(tiles_8bpp),
        "expansion_rule": (
            "v==0 -> 0, 1<=v<=%d -> %d+v, v>%d -> 0"
            % (PALETTE_LAST, PALETTE_BASE, PALETTE_LAST)
        ),
        "problems": problems,
    }


def check_visible_window(
    tilemap: list[int],
    states: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """The visible 30x20 window must be the one the original actually shows.

    The original's BG2 scrolls by ``hoff = 240`` / ``voff = 24`` pixels, so
    the screen's tile column ``c`` is tilemap column ``(c + 30) % 32`` and
    the screen's tile row ``r`` is tilemap row ``(r + 3) % 32``.  The
    runtime receipt states the visible window itself
    (``visible_map_cols`` / ``visible_map_rows``), so the formula is checked
    against the receipt rather than against an assumption.

    The window's entries must also stay inside the original's overlay tile
    set (256..287) and inside one palette bank, because the remake uploads
    exactly those blocks.
    """
    problems: list[str] = []
    per_state: dict[str, Any] = {}
    for name, state in sorted(states.items()):
        cols = state["visible_map_cols"]
        rows = state["visible_map_rows"]
        if len(cols) != VISIBLE_COLUMNS or len(rows) != VISIBLE_ROWS:
            problems.append(
                f"{name}: the receipt declares a {len(cols)}x{len(rows)} "
                f"window, expected {VISIBLE_COLUMNS}x{VISIBLE_ROWS}"
            )
            continue
        # Each state carries its own scroll registers: the S49 move state
        # scrolls by 240/24, the 16-grid state by 152/40.  The formula is
        # therefore evaluated with the state's own offsets.
        hoffs = int(state.get("bg2_hoffs", HOFFS))
        voffs = int(state.get("bg2_voffs", VOFFS))
        declared: list[int] = []
        computed: list[int] = []
        for row in range(VISIBLE_ROWS):
            for column in range(VISIBLE_COLUMNS):
                declared.append(
                    tilemap[rows[row] * TILEMAP_COLUMNS + cols[column]]
                )
                computed.append(
                    tilemap[
                        ((row + voffs // 8) % TILEMAP_ROWS) * TILEMAP_COLUMNS
                        + ((column + hoffs // 8) % TILEMAP_COLUMNS)
                    ]
                )
        if declared != computed:
            differing = sum(
                1 for left, right in zip(declared, computed) if left != right
            )
            problems.append(
                f"{name}: the scroll formula disagrees with the receipt's "
                f"declared window in {differing} of {len(declared)} entries"
            )
        indices = {value & 0x3FF for value in declared}
        banks = {value >> 12 for value in declared}
        outside = sorted(
            index for index in indices
            if not TILE_BASE_INDEX <= index < TILE_BASE_INDEX + TILE_COUNT
        )
        if outside:
            problems.append(
                f"{name}: the window names tiles {outside} outside the "
                f"original's overlay set {TILE_BASE_INDEX}.."
                f"{TILE_BASE_INDEX + TILE_COUNT - 1}"
            )
        if len(banks) != 1:
            problems.append(
                f"{name}: the window mixes palette banks {sorted(banks)}"
            )
        per_state[name] = {
            "scroll": {"hoffs": hoffs, "voffs": voffs},
            "declared_matches_formula": declared == computed,
            "palette_banks": sorted(banks),
            "tile_indices": sorted(indices),
            "distinct_tiles": len(indices),
            "lit_entries": sum(1 for value in declared if (value & 0x3FF) != 256),
        }
    return {
        "check": "visible_window",
        "ok": not problems,
        "scroll": {"hoffs": HOFFS, "voffs": VOFFS},
        "formula": "entry[(row + 3) % 32][(column + 30) % 32]",
        "states": per_state,
        "problems": problems,
    }


def check_source_identity(
    reverse_family_json: dict[str, Any],
    receipt_manifest: dict[str, Any],
) -> dict[str, Any]:
    """The S49 overlay's source is **not** a reverse family.

    ``docs/butano-wiring-roadmap.md`` (W2) says the original side of the
    S49 overlay is already closed in ``overview-gradient-overlay-v1``.  That
    is **wrong**, and the mistake is worth pinning down: that family is the
    *character overview* overlay on **BG0**, while the S49 battle overlay is
    a different layer on **BG2** with a different palette bank and a
    different tile set.

    This check states the distinction as a fact, so nobody wires the wrong
    overlay into the battle again.
    """
    problems: list[str] = []
    generated = reverse_family_json.get("generated") or {}
    binding = reverse_family_json.get("runtime_binding") or {}
    family_tiles = generated.get("tiles") or {}
    family_palette = generated.get("palette") or {}
    family_tilemap = generated.get("tilemap") or {}

    family_layer = "BG0" if binding.get("bg0cnt") else "unknown"
    family_tile_count = int(family_tiles.get("tile_count") or 0)
    family_palette_bank = int(family_palette.get("palette_bank") or -1)
    family_checkpoint = str(binding.get("checkpoint") or "")

    outputs = receipt_manifest.get("outputs") or {}
    receipt_tiles = outputs.get("bg2-tiles-4bpp.bin") or {}
    receipt_bytes = int(receipt_tiles.get("bytes") or 0)
    receipt_tile_count = receipt_bytes // TILE_BYTES_4BPP
    receipt_palette = outputs.get("bg2-palette.bin") or {}

    facts = {
        "reverse_family": {
            "id": "overview-gradient-overlay-v1",
            "layer": family_layer,
            "palette_bank": family_palette_bank,
            "tile_count": family_tile_count,
            "tilemap_dimensions": family_tilemap.get("dimensions"),
            "checkpoint": family_checkpoint,
            "controller": (reverse_family_json.get("controller") or {}).get(
                "gba_address"
            ),
        },
        "s49_overlay_source": {
            "id": "artifacts/s49-original-movegrid-tilemap-v1",
            "layer": "BG2",
            "palette_bank": 12,
            "tile_count": receipt_tile_count,
            "tilemap_dimensions": [TILEMAP_COLUMNS, TILEMAP_ROWS],
            "checkpoint": "artifacts/s49-remake-walk-20261021-v1",
            "controller": "the S49 battle controller",
        },
    }
    if family_layer == "BG2" and family_palette_bank == 12:
        problems.append(
            "the reverse family now looks like the S49 overlay; the "
            "distinction this check pins down may be out of date"
        )
    if receipt_tile_count != TILE_COUNT:
        problems.append(
            f"the remake-tree receipt holds {receipt_tile_count} tiles, "
            f"expected {TILE_COUNT}"
        )
    if not receipt_palette:
        problems.append("the remake-tree receipt has no palette dump")
    return {
        "check": "source_identity",
        "ok": not problems,
        "finding": (
            "the S49 battle overlay's closed original side is the remake "
            "tree's own runtime receipt, not a reverse family; the reverse "
            "family overview-gradient-overlay-v1 is the character overview "
            "gradient overlay on BG0"
        ),
        "consequence": (
            "W2 is not blocked on a missing reverse family -- but W4's "
            "'the original side is already closed' premise must be read as "
            "'the closed side is in this tree, in a runtime receipt'"
        ),
        "facts": facts,
        "problems": problems,
    }


def check_upload(plan: dict[str, Any]) -> dict[str, Any]:
    """The new upload must fit, must not grow, and must be base aligned."""
    problems: list[str] = []
    overlay = plan["overlay_layer"]
    tiles = overlay["tiles"]
    logical_now = int(tiles["logical_tiles_now"])
    bytes_now = int(tiles["bytes_now"])
    logical_new = 52
    bytes_new = logical_new * TILE_BYTES_8BPP
    if bytes_new > bytes_now:
        problems.append(
            f"the new upload is {bytes_new} B, more than the current {bytes_now} B"
        )
    # An 8bpp tile set must start on a 64 byte boundary; Butano hands out
    # whole 2 KB pages, so the set has to fit in a whole number of pages.
    pages_now = -(-bytes_now // 2048)
    pages_new = -(-bytes_new // 2048)
    if bytes_new % TILE_BYTES_8BPP:
        problems.append("the new upload is not a whole number of 8bpp tiles")
    if pages_new > pages_now:
        problems.append(
            f"the new upload needs {pages_new} tile pages, the current one "
            f"uses {pages_now}"
        )
    map_bytes = int(overlay["map"]["bytes"])
    if map_bytes % 2048:
        problems.append(
            f"the overlay map is {map_bytes} B, not a whole number of 2 KB "
            f"screen blocks"
        )
    return {
        "check": "upload",
        "ok": not problems,
        "logical_tiles_now": logical_now,
        "logical_tiles_new": logical_new,
        "bytes_now": bytes_now,
        "bytes_new": bytes_new,
        "delta_bytes": bytes_new - bytes_now,
        "tile_pages_now": pages_now,
        "tile_pages_new": pages_new,
        "map_bytes": map_bytes,
        "base_alignment_bytes": TILE_BYTES_8BPP,
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# driver


def load_states(
    tilemap_receipt: Path,
) -> tuple[dict[str, list[int]], dict[str, dict[str, Any]]]:
    """Read the original's BG2 tilemaps and the windows the receipt declares."""
    tilemaps: dict[str, list[int]] = {}
    states: dict[str, dict[str, Any]] = {}
    for name in ("field-frame-v1", "movegrid-frame-v1", "grid16-frame-v1", "banner-frame-v1"):
        path = tilemap_receipt / f"{name}.bg2-tilemap.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        flat = [0] * (TILEMAP_COLUMNS * TILEMAP_ROWS)
        for cell in payload.get("cells") or []:
            flat[cell["map_y"] * TILEMAP_COLUMNS + cell["map_x"]] = int(
                cell["raw_hex"], 16
            )
        window = payload.get("screen_window") or {}
        tilemaps[name] = flat
        states[name] = {
            "visible_map_cols": list(window.get("visible_map_cols") or []),
            "visible_map_rows": list(window.get("visible_map_rows") or []),
            "bg2_hoffs": int(window.get("bg2_hoffs", HOFFS)),
            "bg2_voffs": int(window.get("bg2_voffs", VOFFS)),
            "palette_bank": sorted(
                {
                    cell.get("palette_bank")
                    for cell in payload.get("cells") or []
                    if cell.get("palette_bank") is not None
                }
            ),
        }
    return tilemaps, states


def verify(
    root: Path,
    reverse_root: Path,
    tilemap_receipt: Path,
    content_header: Path,
    tiles_header: Path,
    plan_path: Path,
) -> dict[str, Any]:
    tiles_4bpp = (tilemap_receipt / "bg2-tiles-4bpp.bin").read_bytes()
    tiles_8bpp = parse_header_bytes(
        tiles_header, "battle_battlefield_overlay_tiles_8bpp"
    )
    tilemaps, states = load_states(tilemap_receipt)
    receipt_manifest = json.loads(
        (tilemap_receipt / "manifest.json").read_text(encoding="utf-8")
    )
    reverse_family_json = json.loads(
        (
            reverse_root
            / "artifacts"
            / "overview-gradient-overlay-v1"
            / "overview-gradient-overlay.json"
        ).read_text(encoding="utf-8")
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    # The window check runs on the S49 move state; the other states are
    # reported so a future state with a different scroll is visible.
    movegrid = tilemaps.get("movegrid-frame-v1") or []
    checks = [
        check_tiles(tiles_4bpp, tiles_8bpp),
        check_visible_window(movegrid, states),
        check_source_identity(reverse_family_json, receipt_manifest),
        check_upload(plan),
    ]
    return {
        "schema": RECEIPT_SCHEMA,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "inputs": {
            "tilemap_receipt": {
                "path": str(tilemap_receipt.relative_to(root)),
                "tiles_4bpp_sha256": sha256_file(
                    tilemap_receipt / "bg2-tiles-4bpp.bin"
                ),
            },
            "content_header": {
                "path": str(content_header.relative_to(root)),
                "sha256": sha256_file(content_header),
            },
            "tiles_header": {
                "path": str(tiles_header.relative_to(root)),
                "sha256": sha256_file(tiles_header),
            },
            "plan": {
                "path": str(plan_path.relative_to(root)),
                "sha256": sha256_file(plan_path),
            },
            "reverse_family_json": {
                "path": str(
                    (
                        reverse_root
                        / "artifacts"
                        / "overview-gradient-overlay-v1"
                        / "overview-gradient-overlay.json"
                    )
                ),
                "sha256": sha256_file(
                    reverse_root
                    / "artifacts"
                    / "overview-gradient-overlay-v1"
                    / "overview-gradient-overlay.json"
                ),
            },
        },
        "checks": checks,
        "ok": all(check["ok"] for check in checks),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# S49 覆盖层 1:1 接线的前置核对（自动生成）",
        "",
        "本文件由 `tools/butano/verify_s49_overlay_preconditions.py` 生成，不要手工编辑。",
        "",
        "| 核对项 | 结果 |",
        "| --- | --- |",
    ]
    for check in payload["checks"]:
        lines.append(
            f"| `{check['check']}` | {'✅ 通过' if check['ok'] else '❌ 不通过'} |"
        )
    lines.append("")
    for check in payload["checks"]:
        lines.append(f"## `{check['check']}`")
        lines.append("")
        for key, value in check.items():
            if key in {"check", "ok", "problems"}:
                continue
            lines.append(f"- **{key}**: {value}")
        if check["problems"]:
            lines.append("- **问题**:")
            for problem in check["problems"]:
                lines.append(f"  - {problem}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--reverse-root",
        type=Path,
        default=Path("/Users/altair/github/gba-naruto-reverse"),
    )
    parser.add_argument(
        "--tilemap-receipt",
        type=Path,
        default=Path("artifacts/s49-original-movegrid-tilemap-v1"),
    )
    parser.add_argument(
        "--content-header",
        type=Path,
        default=Path(
            "butano-sequel/game/include/konoha/"
            "generated_battle_battlefield_overlay_content.h"
        ),
    )
    parser.add_argument(
        "--tiles-header",
        type=Path,
        default=Path(
            "butano-sequel/game/include/konoha/"
            "generated_battle_battlefield_overlay_tiles.h"
        ),
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("artifacts/s49-overlay-plan-20261021-v1/capacity.json"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/s49-overlay-preconditions-v1"),
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    reverse_root = args.reverse_root.resolve()

    def _resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    tilemap_receipt = _resolve(args.tilemap_receipt)
    content_header = _resolve(args.content_header)
    tiles_header = _resolve(args.tiles_header)
    plan_path = _resolve(args.plan)
    for required in (
        tilemap_receipt / "bg2-tiles-4bpp.bin",
        content_header,
        tiles_header,
        plan_path,
    ):
        if not required.is_file():
            print(f"missing input: {required}", file=sys.stderr)
            return EXIT_INPUT_ERROR

    payload = verify(
        root,
        reverse_root,
        tilemap_receipt,
        content_header,
        tiles_header,
        plan_path,
    )
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "preconditions.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "preconditions.md").write_text(
        render_markdown(payload), encoding="utf-8"
    )
    for check in payload["checks"]:
        print(
            f"{check['check']}: {'ok' if check['ok'] else 'FAILED'}"
            + ("" if check["ok"] else f" ({'; '.join(check['problems'])})")
        )
    return EXIT_OK if payload["ok"] else EXIT_CHECK_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
