#!/usr/bin/env python3
"""Generate the original duel backdrop from ROM tile components."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import bgr555_to_rgb, lz77_decompress


DUEL_BACKGROUND_TILES_ADDRESS = 0x08329C34
DUEL_BACKGROUND_PALETTE_ADDRESS = 0x0832A854
DUEL_BACKGROUND_TILEMAP_ADDRESS = 0x0832A8F8
DUEL_BACKGROUND_TILES_OFFSET = 0x329C34
DUEL_BACKGROUND_PALETTE_OFFSET = 0x32A854
DUEL_BACKGROUND_TILEMAP_OFFSET = 0x32A8F8
OUTPUT_STEM = "battle_duel_forest"
OUTPUT_SIZE = 256
SCREEN_BLOCK_TILE_COLUMNS = 32
SCREEN_BLOCK_TILE_ROWS = 32
DUEL_HUD_EVIDENCE = (
    REPO_ROOT
    / "artifacts"
    / "original-s49-enemy-duel-gpu-20260730-190"
)
DUEL_HUD_EVIDENCE_SHA256 = {
    "io.bin":
        "bd341fe4ab656ae5efe75ca79fcaa88fac1b21d4adef7040bfff740a70e1a651",
    "pram.bin":
        "871ca742605c8962eb7a58a230ae8610275dc9582b1967d74ed0c1e9840379ee",
    "vram.bin":
        "42537d6c7d0c5858e099b0823aee94ba88105bd438ef9b106021d37dc128b4fc",
}
DUEL_HUD_BG_INDEX = 3
DUEL_HUD_SHELL_FIRST_TILE = 0x1C0
DUEL_HUD_SHELL_LAST_TILE = 0x1C9
DUEL_HUD_BLANK_TILE = 0x1C1
DUEL_HUD_TITLE_TILE_ROWS = range(0, 4)
DUEL_HUD_STATUS_TILE_ROWS = range(14, 20)
DUEL_HUD_PALETTE_BANK = 14


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_palette(raw: bytes) -> list[tuple[int, int, int]]:
    colors = [
        bgr555_to_rgb(struct.unpack_from("<H", raw, offset)[0])
        for offset in range(0, len(raw), 2)
    ]
    # The runtime changes backdrop color zero to black after loading this
    # palette.  Preserve that independently observed presentation behavior.
    colors[0] = (0, 0, 0)
    colors.extend([(0, 0, 0)] * (256 - len(colors)))
    return colors[:256]


def _tile_pixel(
    tiles: bytes,
    entry: int,
    local_x: int,
    local_y: int,
) -> int:
    if entry & (1 << 10):
        local_x = 7 - local_x
    if entry & (1 << 11):
        local_y = 7 - local_y
    tile_index = entry & 0x3FF
    tile_offset = tile_index * 32 + local_y * 4 + local_x // 2
    if tile_offset >= len(tiles):
        raise ValueError(
            f"tilemap references tile {tile_index}, outside "
            f"{len(tiles) // 32} decoded tiles"
        )
    packed = tiles[tile_offset]
    color = (packed >> (4 if local_x & 1 else 0)) & 0x0F
    return color + ((entry >> 12) & 0x0F) * 16


def render_text_background(
    tiles: bytes,
    palette: bytes,
    tilemap: bytes,
) -> Image.Image:
    """Render one GBA text-background screen block as indexed pixels."""
    if len(tilemap) % 2:
        raise ValueError("text background tilemap must contain 16-bit entries")
    entries = [
        struct.unpack_from("<H", tilemap, offset)[0]
        for offset in range(0, len(tilemap), 2)
    ]
    screen_entries = SCREEN_BLOCK_TILE_COLUMNS * SCREEN_BLOCK_TILE_ROWS
    if len(entries) > screen_entries:
        raise ValueError("tilemap exceeds one 32x32 text screen block")
    entries.extend([0] * (screen_entries - len(entries)))

    pixels = bytearray(OUTPUT_SIZE * OUTPUT_SIZE)
    for y in range(OUTPUT_SIZE):
        tile_y, local_y = divmod(y, 8)
        for x in range(OUTPUT_SIZE):
            tile_x, local_x = divmod(x, 8)
            entry = entries[
                tile_y * SCREEN_BLOCK_TILE_COLUMNS + tile_x
            ]
            pixels[y * OUTPUT_SIZE + x] = _tile_pixel(
                tiles,
                entry,
                local_x,
                local_y,
            )

    image = Image.frombytes(
        "P",
        (OUTPUT_SIZE, OUTPUT_SIZE),
        bytes(pixels),
    )
    image.putpalette(
        [
            component
            for color in _decode_palette(palette)
            for component in color
        ]
    )
    return image


def extract_duel_background(rom: bytes) -> dict[str, Any]:
    tiles = lz77_decompress(rom, DUEL_BACKGROUND_TILES_OFFSET)
    palette = lz77_decompress(rom, DUEL_BACKGROUND_PALETTE_OFFSET)
    tilemap = lz77_decompress(rom, DUEL_BACKGROUND_TILEMAP_OFFSET)
    return {
        "tiles": tiles,
        "palette": palette,
        "tilemap": tilemap,
        "image": render_text_background(tiles, palette, tilemap),
    }


def _read_hash_bound_gpu_evidence(
    evidence_dir: Path,
) -> tuple[dict[str, bytes], dict[str, str]]:
    raw: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for name, expected_sha256 in DUEL_HUD_EVIDENCE_SHA256.items():
        payload = (evidence_dir / name).read_bytes()
        digest = _sha256(payload)
        if digest != expected_sha256:
            raise ValueError(
                f"duel HUD evidence hash mismatch for {name}: {digest}"
            )
        raw[name] = payload
        hashes[name] = digest
    if len(raw["io.bin"]) != 0x400:
        raise ValueError("duel HUD IO evidence must contain 0x400 bytes")
    if len(raw["pram.bin"]) != 0x400:
        raise ValueError("duel HUD palette evidence must contain 0x400 bytes")
    if len(raw["vram.bin"]) != 0x18000:
        raise ValueError("duel HUD VRAM evidence must contain 0x18000 bytes")
    return raw, hashes


def _decode_4bpp_tile_pixel(
    vram: bytes,
    tile_index: int,
    local_x: int,
    local_y: int,
    *,
    horizontal_flip: bool = False,
    vertical_flip: bool = False,
) -> int:
    if horizontal_flip:
        local_x = 7 - local_x
    if vertical_flip:
        local_y = 7 - local_y
    offset = tile_index * 32 + local_y * 4 + local_x // 2
    packed = vram[offset]
    return (packed >> (4 if local_x & 1 else 0)) & 0x0F


def _duel_hud_palette(pram: bytes) -> list[int]:
    start = DUEL_HUD_PALETTE_BANK * 16 * 2
    palette = [
        component
        for offset in range(start, start + 32, 2)
        for component in bgr555_to_rgb(
            struct.unpack_from("<H", pram, offset)[0]
        )
    ]
    palette.extend([0] * (256 * 3 - len(palette)))
    return palette


def _duel_hud_screen(
    io: bytes,
    pram: bytes,
    vram: bytes,
) -> tuple[Image.Image, int]:
    control = struct.unpack_from(
        "<H",
        io,
        0x08 + DUEL_HUD_BG_INDEX * 2,
    )[0]
    if control != 0x0300:
        raise ValueError(
            f"unexpected original duel HUD BG3 control: 0x{control:04X}"
        )
    screen_base = ((control >> 8) & 0x1F) * 0x800
    character_base = ((control >> 2) & 3) * 0x4000
    if character_base != 0:
        raise ValueError("duel HUD shell expects BG3 character base zero")

    pixels = bytearray(OUTPUT_SIZE * 160)
    cleared_dynamic_cells = 0
    shell_rows = set(DUEL_HUD_TITLE_TILE_ROWS)
    shell_rows.update(DUEL_HUD_STATUS_TILE_ROWS)
    for tile_y in shell_rows:
        for tile_x in range(SCREEN_BLOCK_TILE_COLUMNS):
            entry_offset = (
                screen_base +
                (tile_y * SCREEN_BLOCK_TILE_COLUMNS + tile_x) * 2
            )
            entry = struct.unpack_from("<H", vram, entry_offset)[0]
            tile_index = entry & 0x3FF
            palette_bank = (entry >> 12) & 0x0F
            if (
                tile_index < DUEL_HUD_SHELL_FIRST_TILE or
                tile_index > DUEL_HUD_SHELL_LAST_TILE
            ):
                tile_index = DUEL_HUD_BLANK_TILE
                palette_bank = DUEL_HUD_PALETTE_BANK
                entry = tile_index | (palette_bank << 12)
                cleared_dynamic_cells += 1
            if palette_bank != DUEL_HUD_PALETTE_BANK:
                raise ValueError(
                    "state-free duel HUD shell uses an unexpected "
                    f"palette bank {palette_bank}"
                )
            for local_y in range(8):
                screen_y = tile_y * 8 + local_y
                for local_x in range(8):
                    screen_x = tile_x * 8 + local_x
                    pixels[screen_y * OUTPUT_SIZE + screen_x] = (
                        _decode_4bpp_tile_pixel(
                            vram,
                            tile_index,
                            local_x,
                            local_y,
                            horizontal_flip=bool(entry & (1 << 10)),
                            vertical_flip=bool(entry & (1 << 11)),
                        )
                    )

    image = Image.frombytes(
        "P",
        (OUTPUT_SIZE, 160),
        bytes(pixels),
    )
    image.putpalette(_duel_hud_palette(pram))
    return image, cleared_dynamic_cells


def _horizontal_sprite_sheet(
    screen: Image.Image,
    *,
    source_top: int,
    source_height: int,
    frame_height: int,
) -> Image.Image:
    frame_count = 4
    sheet = Image.new(
        "P",
        (64, frame_height * frame_count),
        color=0,
    )
    sheet.putpalette(screen.getpalette())
    destination_top = frame_height - source_height
    for frame in range(frame_count):
        left = frame * 64
        region = screen.crop(
            (
                left,
                source_top,
                left + 64,
                source_top + source_height,
            )
        )
        sheet.paste(
            region,
            (0, frame * frame_height + destination_top),
        )
    return sheet


def extract_duel_hud_shell(
    evidence_dir: Path = DUEL_HUD_EVIDENCE,
) -> dict[str, Any]:
    """Extract only the original BG3 panel shells, without live state.

    Original character names, action title, HP/CK values and bars occupy
    dynamic BG3 cells.  They are replaced with the original interior tile,
    leaving only panel structure for the runtime to populate from combat
    state.
    """

    raw, hashes = _read_hash_bound_gpu_evidence(evidence_dir)
    screen, cleared_dynamic_cells = _duel_hud_screen(
        raw["io.bin"],
        raw["pram.bin"],
        raw["vram.bin"],
    )
    background = Image.new(
        "P",
        (OUTPUT_SIZE, OUTPUT_SIZE),
        color=0,
    )
    background.putpalette(screen.getpalette())
    background.paste(screen, (0, 0))
    return {
        "background_image": background,
        "source_sha256": hashes,
        "palette_bank": DUEL_HUD_PALETTE_BANK,
        "cleared_dynamic_cells": cleared_dynamic_cells,
    }


def generate(
    rom_path: Path,
    output_dir: Path,
    *,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    rom = rom_path.read_bytes()
    extracted = extract_duel_background(rom)
    hud_shell = extract_duel_hud_shell()
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / f"{OUTPUT_STEM}.bmp"
    metadata_path = output_dir / f"{OUTPUT_STEM}.json"
    extracted["image"].save(image_path)
    hud_shell_path = output_dir / "battle_duel_hud_shell.bmp"
    hud_shell_metadata_path = (
        output_dir / "battle_duel_hud_shell.json"
    )
    hud_shell["background_image"].save(hud_shell_path)
    hud_shell_metadata_path.write_text(
        json.dumps(
            {
                "type": "regular_bg",
                "bpp_mode": "bpp_4",
                "colors_count": 16,
                "compression": "auto_no_huffman",
                "active_size": [240, 160],
                "source": "original_s49_bg3_state_free_shell",
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    for stale_name in (
        "battle_duel_title_panel.bmp",
        "battle_duel_title_panel.json",
        "battle_duel_status_panels.bmp",
        "battle_duel_status_panels.json",
    ):
        (output_dir / stale_name).unlink(missing_ok=True)

    source_components = [
        {
            "role": "bg_tiles",
            "address": f"0x{DUEL_BACKGROUND_TILES_ADDRESS:08X}",
            "decompressed_sha256": _sha256(extracted["tiles"]),
        },
        {
            "role": "bg_palette",
            "address": f"0x{DUEL_BACKGROUND_PALETTE_ADDRESS:08X}",
            "decompressed_sha256": _sha256(extracted["palette"]),
        },
        {
            "role": "bg_tilemap",
            "address": f"0x{DUEL_BACKGROUND_TILEMAP_ADDRESS:08X}",
            "decompressed_sha256": _sha256(extracted["tilemap"]),
        },
    ]
    metadata = {
        "type": "regular_bg",
        "bpp_mode": "bpp_4",
        "colors_count": 32,
        "compression": "auto_no_huffman",
        "source": source_components,
        "active_size": [240, 160],
        "component_pipeline": (
            "ROM LZ77 components -> GBA text BG decode -> Butano regular BG"
        ),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema": "original-action-duel-components-v1",
        "rom_sha256": _sha256(rom),
        "asset": image_path.name,
        "asset_sha256": _sha256(image_path.read_bytes()),
        "source_components": source_components,
        "runtime_evidence": {
            "tiles_destination": "0x06004000",
            "palette_destination": "0x05000000",
            "tilemap_destination": "0x06000000",
            "frame_loaded": [51, 52],
        },
        "hud_shell": {
            "source": "original-s49-enemy-duel-bg3",
            "source_sha256": hud_shell["source_sha256"],
            "palette_bank": hud_shell["palette_bank"],
            "cleared_dynamic_cells":
                hud_shell["cleared_dynamic_cells"],
            "asset": hud_shell_path.name,
        },
    }
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    print(
        json.dumps(
            generate(
                args.rom,
                args.output_dir,
                manifest_path=args.manifest,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
