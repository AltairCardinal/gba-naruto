#!/usr/bin/env python3
"""Generate composable battle UI frame slices and resource bars.

The palette and two-stage green frame treatment are sampled from the original
battle HUD evidence.  No text, number, or battle state is baked into panel
assets: the runtime composes the slices dynamically, while selection cursors
remain independent movable OBJ assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from PIL import Image

try:
    from tools.butano.indexed_bmp import write_4bpp_bmp
except ModuleNotFoundError:
    from indexed_bmp import write_4bpp_bmp


PANEL_WIDTH = 64
PANEL_HEIGHT = 32
PANEL_FRAME_COUNT = 7
STATUS_PANEL_WIDTH = 64
STATUS_PANEL_HEIGHT = 32
STATUS_PANEL_FRAME_COUNT = 4
STATUS_END_SIZE = 16
BAR_WIDTH = 64
BAR_HEIGHT = 32
BAR_FRAME_COUNT = 4
BAR_VISIBLE_TOP = 12
BAR_VISIBLE_HEIGHT = 8
DIALOG_PANEL_WIDTH = 32
DIALOG_PANEL_HEIGHT = 64
DIALOG_PANEL_FRAME_COUNT = 3
LARGE_DIALOG_PANEL_WIDTH = 64
LARGE_DIALOG_PANEL_HEIGHT = 64
LARGE_DIALOG_PANEL_FRAME_COUNT = 4
MESSAGE_PANEL_WIDTH = 64
MESSAGE_PANEL_HEIGHT = 64
MESSAGE_PANEL_FRAME_COUNT = 4
MESSAGE_BLACK_BAR_WIDTH = 64
MESSAGE_BLACK_BAR_HEIGHT = 32
DIALOGUE_SPEAKER_LABEL_WIDTH = 32
DIALOGUE_SPEAKER_LABEL_HEIGHT = 16
DIALOGUE_SPEAKER_LABEL_FRAME_COUNT = 2
PREPARATION_DIALOG_PANEL_WIDTH = 32
PREPARATION_DIALOG_PANEL_HEIGHT = 64
PREPARATION_DIALOG_PANEL_FRAME_COUNT = 3
PREPARATION_MENU_PANEL_SIZE = 64
PREPARATION_MENU_PANEL_FRAME_COUNT = 4
PREPARATION_CURSOR_SIZE = 8
COMMAND_CURSOR_WIDTH = 8
COMMAND_CURSOR_HEIGHT = 16
RANGE_TILE_SIZE = 8
RANGE_TILE_COUNT = 4
PREPARATION_BACKGROUND_SIZE = 256
RESULT_BACKGROUND_SIZE = 256
ROOT = Path(__file__).resolve().parents[2]
STATUS_PANEL_EVIDENCE = (
    ROOT / "references" / "battle-scenario-49-ui"
)
STATUS_END_SOURCE = (
    ROOT
    / "artifacts"
    / "runtime-checkpoints"
    / "scenario-49-battle-14-entry.ss9"
)
PREPARATION_OVERVIEW_SOURCE = (
    ROOT
    / "artifacts"
    / "runtime-checkpoints"
    / "scenario-49-battle-14-postbattle-task-menu.ss9"
)
PREPARATION_MENU_SOURCE = (
    ROOT
    / "artifacts"
    / "runtime-checkpoints"
    / "scenario-49-post-training-task-menu.ss9"
)
PREPARATION_ROOT_SOURCE = (
    ROOT
    / "artifacts"
    / "scenario-49-battle-14-postbattle-root-menu-v1"
    / "after-a.png"
)
PREPARATION_BEE_ROOT_SOURCE = (
    ROOT
    / "artifacts"
    / "original-s49-task-menu-sequence-20260730-106"
    / "frame-00.png"
)
PREPARATION_CONFIRMATION_SOURCE = (
    ROOT
    / "artifacts"
    / "original-s49-task-start-20260730-107"
    / "step-03-A.png"
)
MESSAGE_PANEL_SOURCE = (
    ROOT
    / "artifacts"
    / "original-s49-selector1-page1-gpu-20260730-115"
    / "frame.png"
)
MESSAGE_PANEL_SOURCE_SHA256 = (
    "c59febc100dd3129f06b6219b4927cd6"
    "aefdf2b0fced2db9a708311ca37c8f99"
)
DIALOGUE_BACKGROUND_EVIDENCE = (
    ROOT
    / "artifacts"
    / "original-s49-selector1-page1-gpu-20260730-115"
)
DIALOGUE_BACKGROUND_EVIDENCE_SHA256 = {
    "io.bin": (
        "5eba7919a19323c68a51c055c4cfd1a4e"
        "43bc211c537a55af175f6e66733fb6b"
    ),
    "pram.bin": (
        "3bcb1fb61bdfa083365488ca4a1bf04b"
        "92680caab876dda57fda41201a60e295"
    ),
    "vram.bin": (
        "20e735583456f64442b8e5283fd8c6ff"
        "20669ec9b0d7fcf2ca417e9c878412b9"
    ),
}
DIALOGUE_SPEAKER_LABEL_SOURCES = (
    (
        ROOT
        / "artifacts"
        / "original-s49-facing-sequence-tail-20260730-114"
        / "step-08-A.png",
        "29e29c9e24ffcf67d33630b08e83af8e"
        "a28568a84305d9c600bb8781ac9ed92a",
    ),
    (
        MESSAGE_PANEL_SOURCE,
        MESSAGE_PANEL_SOURCE_SHA256,
    ),
)
RESULT_EVIDENCE = (
    ROOT
    / "artifacts"
    / "original-s49-result-gpu-20260730-323"
)
LEVEL_UP_EVIDENCE = {
    1: (
        ROOT
        / "artifacts"
        / "original-s49-levelup-gpu-20260730-349"
    ),
    2: (
        ROOT
        / "artifacts"
        / "original-s49-levelup-sasuke-gpu-20260730-351"
    ),
    3: (
        ROOT
        / "artifacts"
        / "original-s49-levelup-sakura-gpu-20260730-352"
    ),
}
LEVEL_UP_REFERENCE_FRAMES = {
    (1, 0): (
        ROOT
        / "artifacts"
        / "original-s49-result-advance-20260730-326"
        / "step-01-A.png"
    ),
    (1, 1): (
        ROOT
        / "artifacts"
        / "original-s49-levelup-advance-20260730-345"
        / "step-01-A.png"
    ),
    (2, 0): (
        ROOT
        / "artifacts"
        / "original-s49-levelup-sequence-20260730-346"
        / "step-01-A.png"
    ),
    (2, 1): (
        ROOT
        / "artifacts"
        / "original-s49-levelup-sequence-20260730-346"
        / "step-02-A.png"
    ),
    (3, 0): (
        ROOT
        / "artifacts"
        / "original-s49-levelup-sequence-20260730-346"
        / "step-03-A.png"
    ),
    (3, 1): (
        ROOT
        / "artifacts"
        / "original-s49-levelup-sequence-20260730-346"
        / "step-04-A.png"
    ),
}
LEVEL_UP_PANEL_SIZE = 256
LEVEL_UP_TITLE_WIDTH = 128
LEVEL_UP_TITLE_HEIGHT = 16
LEVEL_UP_VALUE_WIDTH = 32
LEVEL_UP_VALUE_HEIGHT = 16
LEVEL_UP_PORTRAIT_COMPONENTS = (
    (6, 64, 64, 16, 40),
    (3, 16, 32, 80, 40),
    (2, 16, 32, 80, 72),
    (5, 32, 16, 16, 104),
    (4, 32, 16, 48, 104),
    (1, 16, 16, 80, 104),
)
TRAINING_EVIDENCE = (
    ROOT
    / "artifacts"
    / "original-s49-training-gpu-20260730-350"
)
TRAINING_REFERENCE_FRAMES = tuple(
    ROOT
    / "artifacts"
    / "original-s49-postlevel-sequence-20260730-347"
    / f"step-{step:02d}-A.png"
    for step in range(1, 7)
)
TRAINING_PAGE_COUNT = len(TRAINING_REFERENCE_FRAMES)
ACTION_MENU_SOURCE = (
    ROOT
    / "artifacts"
    / "scenario-49-battle-14-original-ui-boundaries-v1"
    / "turn4-action-a-01"
    / "step-01-A.ss9"
)
ACTION_MENU_GPU_DIR = (
    ROOT
    / "artifacts"
    / "scenario-49-battle-14-original-ui-boundaries-v1"
    / "turn4-skill-menu"
)
ACTION_ICON_SIZE = 16
ACTION_ICON_FRAME_COUNT = 6
ACTION_CURSOR_WIDTH = 8
ACTION_CURSOR_HEIGHT = 16
ACTION_START_HINT_WIDTH = 32
ACTION_START_HINT_HEIGHT = 16
ACTION_BACK_HINT_WIDTH = 16
ACTION_BACK_HINT_HEIGHT = 16
ACTION_ACTOR_STATS_WIDTH = 32
ACTION_ACTOR_STATS_HEIGHT = 16
ACTION_ICON_SOURCE_ORIGINS = (
    (80, 40),   # 忍
    (80, 72),   # 体
    (80, 88),   # 具
    (96, 40),   # 移
    (96, 56),   # 效
    (96, 72),   # 攻
)
ACTION_ICON_PALETTE = (
    (231, 247, 214),
    (66, 74, 82),
    (156, 165, 140),
    (206, 222, 198),
    (255, 181, 148),
    (24, 24, 24),
    (255, 255, 255),
    (123, 123, 123),
    (255, 107, 41),
    (148, 74, 41),
    (255, 222, 0),
    (165, 132, 0),
    (231, 247, 231),
    (132, 148, 115),
    (49, 41, 41),
    (0, 255, 0),
)
COMMAND_CURSOR_GPU_DIR = (
    ROOT
    / "artifacts"
    / "scenario-49-battle-14-original-ui-boundaries-v1"
    / "turn4-command-menu"
)
TARGET_CONFIRMATION_GPU_DIR = (
    ROOT
    / "artifacts"
    / "scenario-49-battle-14-original-ui-boundaries-v1"
    / "turn4-target-confirmation"
)
CONFIRMATION_CURSOR_WIDTH = 8
CONFIRMATION_CURSOR_HEIGHT = 16

# Transparent, parchment, original HUD greens, ink, highlights, HP and chakra.
PALETTE = (
    (0, 0, 0),
    (231, 247, 214),
    (57, 66, 57),
    (99, 189, 115),
    (107, 156, 90),
    (173, 181, 156),
    (231, 214, 99),
    (255, 231, 165),
    (74, 156, 115),
    (82, 255, 148),
    (132, 107, 0),
    (255, 173, 0),
    (99, 115, 90),
    (198, 255, 206),
    (33, 33, 33),
    (115, 123, 107),
)
MESSAGE_PANEL_PALETTE = tuple(
    (189, 173, 57)
    if index == 7
    else (132, 222, 148)
    if index == 8
    else (0, 0, 0)
    if index == 15
    else color
    for index, color in enumerate(PALETTE)
)
DIALOGUE_TEXT_PALETTE = tuple(
    (57, 66, 57)
    if index == 15
    else (173, 181, 156)
    if index == 5
    else (115, 123, 107)
    if index == 10
    else color
    for index, color in enumerate(PALETTE)
)
# The dialogue speaker label is drawn from the shared preparation font atlas, so
# its palette must speak that atlas's indices: foreground is baked as 2, shadow
# as 5 and midtone as 15.  Mapping 14 and 6 instead left the label grey, which
# is why 佐助 rendered with the right glyphs but the wrong colour.  This mirrors
# TEXT_ACCENT_PALETTE, which is used with the same atlas by the status bar.
DIALOGUE_SPEAKER_PALETTE = tuple(
    (115, 33, 255)
    if index == 2
    else (189, 173, 222)
    if index == 5
    else (148, 99, 239)
    if index == 15
    else color
    for index, color in enumerate(PALETTE)
)
DIALOGUE_SPEAKER_LABEL_PALETTE = (
    (0, 0, 0),
    (115, 33, 255),
    (189, 173, 222),
) + PALETTE[3:]
TEXT_ACCENT_PALETTE = tuple(
    (115, 33, 255)
    if index == 2
    else (189, 173, 222)
    if index == 5
    else (148, 99, 239)
    if index == 15
    else color
    for index, color in enumerate(PALETTE)
)
TEXT_WARNING_PALETTE = (
    PALETTE[:2]
    + ((231, 24, 0),)
    + PALETTE[3:5]
    + ((231, 173, 140),)
    + PALETTE[6:]
)
PREPARATION_TEXT_PALETTE = tuple(
    (115, 123, 107) if index == 15 else color
    for index, color in enumerate(PALETTE)
)
PREPARATION_ACCENT_PALETTE = tuple(
    (148, 99, 239) if index == 15 else color
    for index, color in enumerate(TEXT_ACCENT_PALETTE)
)
PREPARATION_CURSOR_PALETTE = (
    (0, 0, 0),
    (181, 189, 165),
    (247, 255, 222),
    (115, 123, 107),
    (57, 57, 57),
) + PALETTE[5:]
MAP_HINT_PALETTE = tuple(
    (255, 255, 255)
    if index in (2, 14)
    else (33, 33, 33)
    if index in (5, 12)
    else color
    for index, color in enumerate(PALETTE)
)
RESULT_TOTAL_PALETTE = tuple(
    (231, 24, 0)
    if index in (2, 14)
    else (231, 173, 140)
    if index in (5, 12)
    else color
    for index, color in enumerate(PALETTE)
)
BAR_PALETTE = (
    PALETTE[:3]
    + ((0, 82, 0),)
    + ((66, 41, 0),)
    + PALETTE[5:14]
    + (
        (156, 107, 0),
        (198, 173, 0),
    )
)


def _panel_frame(
    *,
    left: bool,
    right: bool,
    top: bool,
    bottom: bool,
) -> list[int]:
    pixels = [1] * (PANEL_WIDTH * PANEL_HEIGHT)

    def set_pixel(x: int, y: int, color: int) -> None:
        pixels[y * PANEL_WIDTH + x] = color

    # Sparse, deterministic parchment grain keeps the panels visually related
    # to the extracted source UI while remaining state-free and tileable.
    for y in range(7 if top else 1, 25 if bottom else 31):
        for x in range(4, PANEL_WIDTH - 4):
            if (x * 5 + y * 11) % 83 == 0:
                set_pixel(x, y, 5)
            elif (x * 13 + y * 3) % 127 == 0:
                set_pixel(x, y, 13)

    woven_rows = (
        (4,) * 8,
        (3,) * 8,
        (4, 4, 4, 12, 12, 12, 3, 3),
        (3, 3, 3, 4, 4, 4, 12, 12),
        (4, 4, 4, 3, 3, 4, 4, 4),
        (3,) * 8,
        (6,) * 8,
    )
    if top:
        for y, motif in enumerate(woven_rows):
            for x in range(PANEL_WIDTH):
                set_pixel(x, y, motif[x % 8])
    if bottom:
        for offset, motif in enumerate(reversed(woven_rows)):
            y = PANEL_HEIGHT - len(woven_rows) + offset
            for x in range(PANEL_WIDTH):
                set_pixel(x, y, motif[x % 8])

    side_pattern = (4, 3, 12, 3, 4, 3)
    first_content_row = 7 if top else 0
    last_content_row = 25 if bottom else PANEL_HEIGHT
    if left:
        for y in range(first_content_row, last_content_row):
            for x, color in enumerate(side_pattern):
                set_pixel(x, y, color)
    if right:
        for y in range(first_content_row, last_content_row):
            for offset, color in enumerate(side_pattern):
                set_pixel(PANEL_WIDTH - 1 - offset, y, color)
    return pixels


def _menu_panel_frame(
    *,
    top: bool,
    bottom: bool,
    content_top: int = 0,
    content_bottom: int = PANEL_HEIGHT - 1,
) -> list[int]:
    """Build the original 52px-wide command-menu frame.

    The transparent horizontal margins place the visible frame at x=8..55.
    Optional vertical margins let the runtime compose the original 48px
    two-command menu without scaling or baking any command state.
    """

    content_left = 8
    content_right = 55
    pixels = [0] * (PANEL_WIDTH * PANEL_HEIGHT)

    def set_pixel(x: int, y: int, color: int) -> None:
        pixels[y * PANEL_WIDTH + x] = color

    for y in range(content_top, content_bottom + 1):
        for x in range(content_left, content_right + 1):
            set_pixel(x, y, 1)

    if top:
        for x in range(content_left, content_right + 1):
            set_pixel(x, content_top, 2)
            set_pixel(x, content_top + 1, 3)
            set_pixel(x, content_top + 2, 4)
    if bottom:
        for x in range(content_left, content_right + 1):
            set_pixel(x, content_bottom, 2)
            set_pixel(x, content_bottom - 1, 3)
            set_pixel(x, content_bottom - 2, 4)

    for y in range(content_top, content_bottom + 1):
        set_pixel(content_left, y, 2)
        set_pixel(content_left + 1, y, 3)
        set_pixel(content_left + 2, y, 4)
        set_pixel(content_right, y, 2)
        set_pixel(content_right - 1, y, 3)
        set_pixel(content_right - 2, y, 4)

    grain_top = content_top + (4 if top else 1)
    grain_bottom = content_bottom - (3 if bottom else 0)
    for y in range(grain_top, grain_bottom):
        for x in range(content_left + 4, content_right - 3):
            if (x * 5 + y * 11) % 47 == 0:
                set_pixel(x, y, 5)
            elif (x * 13 + y * 3) % 71 == 0:
                set_pixel(x, y, 13)

    if top:
        set_pixel(content_left, content_top, 0)
        set_pixel(content_right, content_top, 0)
    if bottom:
        set_pixel(content_left, content_bottom, 0)
        set_pixel(content_right, content_bottom, 0)
    return pixels


def _gba_color(value: int) -> tuple[int, int, int]:
    return tuple(
        (channel << 3) | (channel >> 2)
        for channel in (
            value & 31,
            (value >> 5) & 31,
            (value >> 10) & 31,
        )
    )


def _result_palette(bank: int) -> tuple[tuple[int, int, int], ...]:
    pram = (RESULT_EVIDENCE / "pram.bin").read_bytes()
    return tuple(
        _gba_color(
            struct.unpack_from(
                "<H", pram, (bank * 16 + index) * 2
            )[0]
        )
        for index in range(16)
    )


def _result_layer_pixels(
    background: int,
    *,
    strip_runtime_fields: bool,
) -> list[int]:
    """Reconstruct one original result BG as a centered 256x256 canvas."""

    io = (RESULT_EVIDENCE / "io.bin").read_bytes()
    vram = (RESULT_EVIDENCE / "vram.bin").read_bytes()
    control = struct.unpack_from(
        "<H", io, 0x08 + background * 2
    )[0]
    character_base = ((control >> 2) & 3) * 0x4000
    screen_base = ((control >> 8) & 31) * 0x800
    horizontal = (
        struct.unpack_from(
            "<H", io, 0x10 + background * 4
        )[0]
        & 0x1FF
    )
    vertical = (
        struct.unpack_from(
            "<H", io, 0x12 + background * 4
        )[0]
        & 0x1FF
    )
    canvas = [0] * (RESULT_BACKGROUND_SIZE ** 2)
    dynamic_tiles = set()
    if strip_runtime_fields:
        # Header names and all four score columns are runtime state.  The
        # fixed "经验值" and score labels stay in the state-free panel.
        for row in (1, 2):
            for left in (12, 19, 26):
                dynamic_tiles.update(
                    (row * 32 + left, row * 32 + left + 1)
                )
        for row in range(14, 19):
            for left in (12, 19, 26):
                dynamic_tiles.update(
                    row * 32 + left + offset
                    for offset in range(3)
                )

    for screen_y in range(160):
        for screen_x in range(240):
            x = (screen_x + horizontal) & 0xFF
            y = (screen_y + vertical) & 0xFF
            map_index = (y // 8) * 32 + x // 8
            entry = struct.unpack_from(
                "<H", vram, screen_base + map_index * 2
            )[0]
            if map_index in dynamic_tiles:
                entry = (entry & 0xF000) | 0x01C1
            local_x = x & 7
            local_y = y & 7
            if entry & (1 << 10):
                local_x = 7 - local_x
            if entry & (1 << 11):
                local_y = 7 - local_y
            tile_offset = (
                character_base
                + (entry & 0x3FF) * 32
                + local_y * 4
                + local_x // 2
            )
            packed = vram[tile_offset]
            color = (
                packed >> 4
                if local_x & 1
                else packed & 0x0F
            )
            canvas[
                (screen_y + 48) * RESULT_BACKGROUND_SIZE
                + screen_x
                + 8
            ] = color
    return canvas


def _result_background_pixels() -> list[int]:
    """Return the exact state-free original BG0 gray result stage."""

    return _result_layer_pixels(
        0, strip_runtime_fields=False)


def _result_panel_pixels() -> list[int]:
    """Return exact BG3 panels with names and values removed."""

    return _result_layer_pixels(
        3, strip_runtime_fields=True)


def _result_participant_oam(
    oam_index: int,
) -> tuple[int, int, int]:
    oam = (RESULT_EVIDENCE / "oam.bin").read_bytes()
    offset = oam_index * 8
    if offset < 0 or offset + 6 > len(oam):
        raise ValueError(f"invalid result OAM index: {oam_index}")
    return struct.unpack_from("<HHH", oam, offset)


def _result_participant_pixels(oam_index: int) -> list[int]:
    """Decode one exact 32x64 result pose from the original OBJ tiles."""

    attr0, attr1, attr2 = _result_participant_oam(oam_index)
    io = (RESULT_EVIDENCE / "io.bin").read_bytes()
    display_control = struct.unpack_from("<H", io, 0)[0]
    if not display_control & (1 << 6):
        raise ValueError("result OBJ evidence is not using 1D mapping")
    if attr0 & (1 << 8) or attr0 & (1 << 13):
        raise ValueError("result participant must be non-affine 4bpp OBJ")
    shape = (attr0 >> 14) & 3
    size = (attr1 >> 14) & 3
    if (shape, size) != (2, 3):
        raise ValueError(
            "result participant must be a 32x64 tall OBJ")

    vram = (RESULT_EVIDENCE / "vram.bin").read_bytes()
    base_tile = attr2 & 0x3FF
    pixels = [0] * (32 * 64)
    for tile_y in range(8):
        for tile_x in range(4):
            tile_index = base_tile + tile_y * 4 + tile_x
            tile_offset = 0x10000 + tile_index * 32
            tile = _decode_4bpp_tile(
                vram[tile_offset:tile_offset + 32])
            for local_y in range(8):
                destination = (
                    (tile_y * 8 + local_y) * 32 +
                    tile_x * 8
                )
                source = local_y * 8
                pixels[destination:destination + 8] = (
                    tile[source:source + 8]
                )
    return pixels


def _result_participant_palette(
    oam_index: int,
) -> tuple[tuple[int, int, int], ...]:
    """Return the exact OBJ palette bank selected by a result pose."""

    _, _, attr2 = _result_participant_oam(oam_index)
    palette_bank = (attr2 >> 12) & 0x0F
    pram = (RESULT_EVIDENCE / "pram.bin").read_bytes()
    palette_offset = 0x200 + palette_bank * 32
    return tuple(
        _gba_color(
            struct.unpack_from(
                "<H", pram, palette_offset + index * 2
            )[0]
        )
        for index in range(16)
    )


def _level_up_bg_palette() -> tuple[tuple[int, int, int], ...]:
    pram = (LEVEL_UP_EVIDENCE[1] / "pram.bin").read_bytes()
    return tuple(
        _gba_color(
            struct.unpack_from(
                "<H", pram, (14 * 16 + index) * 2
            )[0]
        )
        for index in range(16)
    )


def _level_up_bg_pixel_index(
    io: bytes,
    vram: bytes,
    background: int,
    screen_x: int,
    screen_y: int,
) -> int | None:
    control = struct.unpack_from(
        "<H", io, 0x08 + background * 2
    )[0]
    x = (
        screen_x
        + (
            struct.unpack_from(
                "<H", io, 0x10 + background * 4
            )[0]
            & 0x1FF
        )
    ) & 0xFF
    y = (
        screen_y
        + (
            struct.unpack_from(
                "<H", io, 0x12 + background * 4
            )[0]
            & 0x1FF
        )
    ) & 0xFF
    character_base = ((control >> 2) & 3) * 0x4000
    screen_base = ((control >> 8) & 31) * 0x800
    map_index = (y // 8) * 32 + x // 8
    entry = struct.unpack_from(
        "<H", vram, screen_base + map_index * 2
    )[0]
    local_x = x & 7
    local_y = y & 7
    if entry & (1 << 10):
        local_x = 7 - local_x
    if entry & (1 << 11):
        local_y = 7 - local_y
    tile_offset = (
        character_base
        + (entry & 0x3FF) * 32
        + local_y * 4
        + local_x // 2
    )
    packed = vram[tile_offset]
    color = (
        packed >> 4
        if local_x & 1
        else packed & 0x0F
    )
    if color == 0:
        return None
    return (entry >> 12) * 16 + color


def _level_up_shell_screen_indices() -> list[int]:
    """Flatten the original BG0/BG3 shell after removing live fields."""

    evidence = LEVEL_UP_EVIDENCE[1]
    io = (evidence / "io.bin").read_bytes()
    vram = bytearray((evidence / "vram.bin").read_bytes())
    pram = (evidence / "pram.bin").read_bytes()
    bg3_control = struct.unpack_from("<H", io, 0x0E)[0]
    bg3_screen_base = ((bg3_control >> 8) & 31) * 0x800
    dynamic_tiles = {
        *(row * 32 + column
          for row in (1, 2)
          for column in range(1, 14)),
        *(row * 32 + column
          for row in range(5, 19)
          for column in range(22, 25)),
    }
    for map_index in dynamic_tiles:
        entry_offset = bg3_screen_base + map_index * 2
        entry = struct.unpack_from("<H", vram, entry_offset)[0]
        struct.pack_into(
            "<H",
            vram,
            entry_offset,
            (entry & 0xF000) | 449,
        )

    palette = _level_up_bg_palette()
    palette_lookup = {
        color: index
        for index, color in reversed(tuple(enumerate(palette)))
        if index != 0
    }
    screen = []
    for screen_y in range(160):
        for screen_x in range(240):
            palette_index = _level_up_bg_pixel_index(
                io, vram, 3, screen_x, screen_y
            )
            if palette_index is None:
                palette_index = _level_up_bg_pixel_index(
                    io, vram, 0, screen_x, screen_y
                )
            if palette_index is None:
                gba_color = struct.unpack_from("<H", pram, 0)[0]
            else:
                gba_color = struct.unpack_from(
                    "<H", pram, palette_index * 2
                )[0]
            rgb = _gba_color(gba_color)
            if rgb not in palette_lookup:
                raise ValueError(
                    "level-up shell color is outside BG3 palette: "
                    f"{rgb}"
                )
            screen.append(palette_lookup[rgb])
    return screen


def _level_up_panel_pixels() -> list[int]:
    screen = _level_up_shell_screen_indices()
    canvas = [1] * (LEVEL_UP_PANEL_SIZE ** 2)
    for screen_y in range(160):
        source = screen_y * 240
        destination = (
            (screen_y + 48) * LEVEL_UP_PANEL_SIZE + 8
        )
        canvas[destination:destination + 240] = (
            screen[source:source + 240]
        )
    return canvas


def _level_up_transparent_component(
    reference_path: Path,
    left: int,
    top: int,
    width: int,
    height: int,
) -> list[int]:
    palette = _level_up_bg_palette()
    palette_lookup = {
        color: index
        for index, color in reversed(tuple(enumerate(palette)))
        if index != 0
    }
    shell = _level_up_shell_screen_indices()
    with Image.open(reference_path) as source:
        source = source.convert("RGB")
        result = []
        for local_y in range(height):
            for local_x in range(width):
                screen_x = left + local_x
                screen_y = top + local_y
                rgb = source.getpixel((screen_x, screen_y))
                shell_index = shell[
                    screen_y * 240 + screen_x
                ]
                if rgb == palette[shell_index]:
                    result.append(0)
                else:
                    if rgb not in palette_lookup:
                        raise ValueError(
                            "level-up text color is outside BG3 "
                            f"palette: {rgb}"
                        )
                    result.append(palette_lookup[rgb])
    return result


def _level_up_title_pixels(
    character_id: int,
    detail_page: int,
) -> list[int]:
    reference = LEVEL_UP_REFERENCE_FRAMES[
        (character_id, detail_page)
    ]
    return _level_up_transparent_component(
        reference,
        0,
        8,
        LEVEL_UP_TITLE_WIDTH,
        LEVEL_UP_TITLE_HEIGHT,
    )


def _level_up_value_pixels(value: int) -> list[int]:
    sources = {
        0: (LEVEL_UP_REFERENCE_FRAMES[(1, 0)], 1),
        1: (LEVEL_UP_REFERENCE_FRAMES[(1, 0)], 2),
        14: (LEVEL_UP_REFERENCE_FRAMES[(1, 0)], 0),
        15: (LEVEL_UP_REFERENCE_FRAMES[(2, 0)], 0),
    }
    reference, row = sources[value]
    return _level_up_transparent_component(
        reference,
        168,
        40 + row * 16,
        LEVEL_UP_VALUE_WIDTH,
        LEVEL_UP_VALUE_HEIGHT,
    )


def _level_up_raw_portrait_component_pixels(
    character_id: int,
    component_index: int,
) -> list[int]:
    evidence = LEVEL_UP_EVIDENCE[character_id]
    oam = (evidence / "oam.bin").read_bytes()
    vram = (evidence / "vram.bin").read_bytes()
    _, width, height, expected_x, expected_y = (
        LEVEL_UP_PORTRAIT_COMPONENTS[component_index]
    )
    dimensions = {
        0: ((8, 8), (16, 16), (32, 32), (64, 64)),
        1: ((16, 8), (32, 8), (32, 16), (64, 32)),
        2: ((8, 16), (8, 32), (16, 32), (32, 64)),
    }
    attributes = None
    for oam_index in range(128):
        candidate = struct.unpack_from(
            "<HHH", oam, oam_index * 8
        )
        attr0, attr1, _ = candidate
        if not attr0 & (1 << 13):
            continue
        shape = (attr0 >> 14) & 3
        if shape == 3:
            continue
        size = (attr1 >> 14) & 3
        if (
            dimensions[shape][size] == (width, height)
            and (attr1 & 0x1FF) == expected_x
            and (attr0 & 0xFF) == expected_y
        ):
            attributes = candidate
            break
    if attributes is None:
        raise ValueError("missing level-up portrait component")
    attr0, attr1, attr2 = attributes
    if not attr0 & (1 << 13):
        raise ValueError("level-up portrait must be an 8bpp OBJ")
    base_tile = attr2 & 0x3FF
    pixels = [0] * (width * height)
    for tile_y in range(height // 8):
        for tile_x in range(width // 8):
            tile_unit = (
                base_tile
                + (tile_y * (width // 8) + tile_x) * 2
            )
            tile_offset = 0x10000 + tile_unit * 32
            tile = vram[tile_offset:tile_offset + 64]
            for local_y in range(8):
                destination = (
                    (tile_y * 8 + local_y) * width
                    + tile_x * 8
                )
                source = local_y * 8
                pixels[destination:destination + 8] = (
                    tile[source:source + 8]
                )
    return pixels


def _level_up_portrait_palette(
) -> tuple[tuple[int, int, int], ...]:
    """Return one shared 8bpp palette for the six final portrait slices.

    The original composes each portrait from OBJ tiles plus a WIN0-filtered
    backing.  Butano does not expose that exact per-window blend cheaply, so
    the generated portrait OBJ slices preserve the final pixels inside the
    original six OBJ rectangles.  This still keeps the portrait independent
    from the panel, title, values, and eye indicator.
    """

    colors = [(0, 0, 0)]
    seen: set[tuple[int, int, int]] = set()
    for character_id in (1, 2, 3):
        reference = Image.open(
            LEVEL_UP_REFERENCE_FRAMES[(character_id, 0)]
        ).convert("RGB")
        for _, width, height, left, top in LEVEL_UP_PORTRAIT_COMPONENTS:
            for rgb in reference.crop(
                (left, top, left + width, top + height)
            ).getdata():
                if rgb not in seen:
                    seen.add(rgb)
                    colors.append(rgb)
    if len(colors) > 256:
        raise ValueError("merged level-up portrait palette overflow")
    return tuple(colors)


def _level_up_portrait_component_pixels(
    character_id: int,
    component_index: int,
) -> list[int]:
    _, width, height, left, top = (
        LEVEL_UP_PORTRAIT_COMPONENTS[component_index]
    )
    reference = Image.open(
        LEVEL_UP_REFERENCE_FRAMES[(character_id, 0)]
    ).convert("RGB")
    merged = _level_up_portrait_palette()
    merged_lookup = {
        color: index for index, color in enumerate(merged)
    }
    crop = reference.crop(
        (left, top, left + width, top + height)
    )
    return [merged_lookup[rgb] for rgb in crop.getdata()]


def _level_up_sprite_palette(
) -> tuple[tuple[int, int, int], ...]:
    """Merge every level-up OBJ color into one hardware-safe palette."""

    colors = [(0, 0, 0)]
    seen: set[tuple[int, int, int]] = set()
    for palette, start in (
        (_level_up_portrait_palette(), 1),
        (_level_up_bg_palette(), 1),
        (_level_up_eye_palette(), 1),
    ):
        for color in palette[start:]:
            if color not in seen:
                seen.add(color)
                colors.append(color)
    if len(colors) > 256:
        raise ValueError("merged level-up OBJ palette overflow")
    return tuple(colors)


def _level_up_shared_palette_pixels(
    pixels: list[int],
    source_palette: tuple[tuple[int, int, int], ...],
) -> list[int]:
    merged = _level_up_sprite_palette()
    lookup = {
        color: index for index, color in enumerate(merged)
    }
    return [
        0 if index == 0 else lookup[source_palette[index]]
        for index in pixels
    ]


def _level_up_eye_pixels() -> list[int]:
    evidence = LEVEL_UP_EVIDENCE[1]
    oam = (evidence / "oam.bin").read_bytes()
    vram = (evidence / "vram.bin").read_bytes()
    attr0 = attr1 = attr2 = 0
    for oam_index in range(128):
        candidate = struct.unpack_from(
            "<HHH", oam, oam_index * 8
        )
        if (
            (candidate[1] & 0x1FF) == 216
            and (candidate[0] & 0xFF) == 8
            and ((candidate[0] >> 14) & 3) == 0
            and ((candidate[1] >> 14) & 3) == 1
        ):
            attr0, attr1, attr2 = candidate
            break
    else:
        raise ValueError("missing level-up eye OBJ")
    pixels = [0] * (16 * 16)
    base_tile = attr2 & 0x3FF
    for tile_y in range(2):
        for tile_x in range(2):
            tile_offset = (
                0x10000
                + (base_tile + tile_y * 2 + tile_x) * 32
            )
            tile = _decode_4bpp_tile(
                vram[tile_offset:tile_offset + 32]
            )
            for local_y in range(8):
                destination = (
                    (tile_y * 8 + local_y) * 16
                    + tile_x * 8
                )
                source = local_y * 8
                pixels[destination:destination + 8] = (
                    tile[source:source + 8]
                )
    return pixels


def _level_up_eye_palette(
) -> tuple[tuple[int, int, int], ...]:
    evidence = LEVEL_UP_EVIDENCE[1]
    pram = (evidence / "pram.bin").read_bytes()
    return tuple(
        _gba_color(
            struct.unpack_from(
                "<H", pram, 0x200 + (15 * 16 + index) * 2
            )[0]
        )
        for index in range(16)
    )


def _paste_indexed_component(
    destination: Image.Image,
    pixels: list[int],
    palette: tuple[tuple[int, int, int], ...],
    width: int,
    height: int,
    left: int,
    top: int,
) -> None:
    target = destination.load()
    for local_y in range(height):
        for local_x in range(width):
            index = pixels[local_y * width + local_x]
            if index:
                target[left + local_x, top + local_y] = (
                    palette[index]
                )


def recompose_level_up_frame(
    character_id: int,
    detail_page: int,
) -> Image.Image:
    palette = _level_up_bg_palette()
    shell = _level_up_shell_screen_indices()
    image = Image.new("RGB", (240, 160))
    image.putdata([palette[index] for index in shell])
    _paste_indexed_component(
        image,
        _level_up_title_pixels(character_id, detail_page),
        palette,
        LEVEL_UP_TITLE_WIDTH,
        LEVEL_UP_TITLE_HEIGHT,
        0,
        8,
    )
    growth = (
        (14, 0, 1, 1, 1, 0, 0)
        if character_id == 1
        else (15, 0, 1, 1, 1, 0, 0)
    )
    for row, value in enumerate(growth):
        _paste_indexed_component(
            image,
            _level_up_value_pixels(value),
            palette,
            LEVEL_UP_VALUE_WIDTH,
            LEVEL_UP_VALUE_HEIGHT,
            168,
            40 + row * 16,
        )
    portrait_palette = _level_up_portrait_palette()
    for component_index, (
            _,
            width,
            height,
            left,
            top,
    ) in enumerate(LEVEL_UP_PORTRAIT_COMPONENTS):
        _paste_indexed_component(
            image,
            _level_up_portrait_component_pixels(
                character_id, component_index
            ),
            portrait_palette,
            width,
            height,
            left,
            top,
        )
    _paste_indexed_component(
        image,
        _level_up_eye_pixels(),
        _level_up_eye_palette(),
        16,
        16,
        216,
        8,
    )
    return image


def _training_shell_screen_indices() -> list[int]:
    """Render the original training BG3 without its dynamic BG0 text."""

    io = (TRAINING_EVIDENCE / "io.bin").read_bytes()
    vram = bytearray(
        (TRAINING_EVIDENCE / "vram.bin").read_bytes()
    )
    pram = (TRAINING_EVIDENCE / "pram.bin").read_bytes()
    bg3_control = struct.unpack_from("<H", io, 0x0E)[0]
    bg3_screen_base = ((bg3_control >> 8) & 31) * 0x800
    for row in (1, 2, 3, 4):
        for column in range(1, 29):
            entry_offset = (
                bg3_screen_base + (row * 32 + column) * 2
            )
            entry = struct.unpack_from(
                "<H", vram, entry_offset
            )[0]
            struct.pack_into(
                "<H",
                vram,
                entry_offset,
                (entry & 0xF000) | 449,
            )
    palette = _level_up_bg_palette()
    palette_lookup = {
        color: index
        for index, color in reversed(tuple(enumerate(palette)))
        if index != 0
    }
    screen = []
    for screen_y in range(160):
        for screen_x in range(240):
            palette_index = _level_up_bg_pixel_index(
                io, vram, 3, screen_x, screen_y
            )
            if palette_index is None:
                palette_index = _level_up_bg_pixel_index(
                    io, vram, 0, screen_x, screen_y
                )
            if palette_index is None:
                gba_color = struct.unpack_from("<H", pram, 0)[0]
            else:
                gba_color = struct.unpack_from(
                    "<H", pram, palette_index * 2
                )[0]
            rgb = _gba_color(gba_color)
            if rgb not in palette_lookup:
                raise ValueError(
                    "training shell color is outside BG3 palette: "
                    f"{rgb}"
                )
            screen.append(palette_lookup[rgb])
    return screen


def _training_panel_pixels() -> list[int]:
    screen = _training_shell_screen_indices()
    source_palette = _level_up_bg_palette()
    palette_lookup = {
        color: index
        for index, color in enumerate(_training_palette())
    }
    canvas = [1] * (256 * 256)
    for screen_y in range(160):
        destination = (screen_y + 48) * 256 + 8
        canvas[destination:destination + 240] = [
            palette_lookup[
                source_palette[
                    screen[screen_y * 240 + screen_x]
                ]
            ]
            for screen_x in range(240)
        ]
    return canvas


def _training_eye_position(page: int) -> tuple[int, int]:
    if page < 0 or page >= TRAINING_PAGE_COUNT:
        raise ValueError("invalid training summary page")
    return (216, 24) if page % 2 == 0 else (216, 136)


def _training_palette(
) -> tuple[tuple[int, int, int], ...]:
    colors = [(0, 0, 0)]
    seen: set[tuple[int, int, int]] = set()
    for page, reference_path in enumerate(
            TRAINING_REFERENCE_FRAMES):
        eye_left, eye_top = _training_eye_position(page)
        with Image.open(reference_path) as source:
            source = source.convert("RGB")
            for screen_y in range(160):
                for screen_x in range(240):
                    if (
                        eye_left <= screen_x < eye_left + 16
                        and eye_top <= screen_y < eye_top + 16
                    ):
                        continue
                    color = source.getpixel(
                        (screen_x, screen_y)
                    )
                    if color not in seen:
                        seen.add(color)
                        colors.append(color)
    if len(colors) > 16:
        raise ValueError("training UI palette overflow")
    colors.extend([(0, 0, 0)] * (16 - len(colors)))
    return tuple(colors)


def _training_text_pixels(page: int) -> list[int]:
    if page < 0 or page >= TRAINING_PAGE_COUNT:
        raise ValueError("invalid training summary page")
    shell_palette = _level_up_bg_palette()
    palette = _training_palette()
    palette_lookup = {
        color: index
        for index, color in reversed(tuple(enumerate(palette)))
        if index != 0
    }
    shell = _training_shell_screen_indices()
    canvas = [0] * (256 * 256)
    eye_left, eye_top = _training_eye_position(page)
    with Image.open(
        TRAINING_REFERENCE_FRAMES[page]
    ) as source:
        source = source.convert("RGB")
        for screen_y in range(160):
            for screen_x in range(240):
                if (
                    eye_left <= screen_x < eye_left + 16
                    and eye_top <= screen_y < eye_top + 16
                ):
                    continue
                rgb = source.getpixel((screen_x, screen_y))
                shell_index = shell[
                    screen_y * 240 + screen_x
                ]
                if rgb == shell_palette[shell_index]:
                    continue
                if rgb not in palette_lookup:
                    raise ValueError(
                        "training text color is outside BG3 "
                        f"palette: {rgb}"
                    )
                canvas[
                    (screen_y + 48) * 256 + screen_x + 8
                ] = palette_lookup[rgb]
    return canvas


def recompose_training_frame(page: int) -> Image.Image:
    source_palette = _level_up_bg_palette()
    palette = _training_palette()
    shell = _training_shell_screen_indices()
    text = _training_text_pixels(page)
    image = Image.new("RGB", (240, 160))
    image.putdata([
        source_palette[index] for index in shell
    ])
    target = image.load()
    for screen_y in range(160):
        for screen_x in range(240):
            index = text[
                (screen_y + 48) * 256 + screen_x + 8
            ]
            if index:
                target[screen_x, screen_y] = palette[index]
    eye_left, eye_top = _training_eye_position(page)
    _paste_indexed_component(
        image,
        _level_up_eye_pixels(),
        _level_up_eye_palette(),
        16,
        16,
        eye_left,
        eye_top,
    )
    return image


def _write_8bpp_bmp(
    path: Path,
    width: int,
    height: int,
    pixels: list[int],
    palette: tuple[tuple[int, int, int], ...],
) -> None:
    if len(pixels) != width * height:
        raise ValueError("invalid 8bpp bitmap pixel count")
    image = Image.new("P", (width, height))
    image.putdata(pixels)
    flattened = [
        channel
        for color in palette
        for channel in color
    ]
    flattened.extend([0] * (768 - len(flattened)))
    image.putpalette(flattened)
    image.save(path)


def _panel_pixels() -> list[int]:
    frames = (
        # Full-width panels: left edge (h-flipped for right) and middle.
        _panel_frame(left=True, right=False, top=True, bottom=True),
        _panel_frame(left=False, right=False, top=True, bottom=True),
        # Vertical menu: top (v-flipped for bottom) and middle.
        _menu_panel_frame(top=True, bottom=False),
        _menu_panel_frame(top=False, bottom=False),
        # Borderless fill for composing large panels without internal seams.
        _panel_frame(
            left=False,
            right=False,
            top=False,
            bottom=False,
        ),
        # A two-command menu is 48px high in the original.  Transparent
        # half-tile margins keep both pieces legal 64x32 OBJ frames.
        _menu_panel_frame(
            top=True,
            bottom=False,
            content_top=8,
        ),
        _menu_panel_frame(
            top=False,
            bottom=True,
            content_bottom=23,
        ),
    )
    return [pixel for frame in frames for pixel in frame]


def _decode_4bpp_tile(encoded: bytes) -> list[int]:
    if len(encoded) != 32:
        raise ValueError("a 4bpp tile must contain exactly 32 bytes")
    pixels: list[int] = []
    for packed in encoded:
        pixels.extend((packed & 0x0F, packed >> 4))
    return pixels


def _status_panel_palette() -> tuple[tuple[int, int, int], ...]:
    encoded = (
        STATUS_PANEL_EVIDENCE
        / "hud-shell-bg-palette.bin"
    ).read_bytes()
    if len(encoded) != 32:
        raise ValueError(
            "the status-panel palette must contain 16 GBA colors"
        )
    colors = []
    for offset in range(0, len(encoded), 2):
        color = int.from_bytes(encoded[offset:offset + 2], "little")
        red = color & 31
        green = (color >> 5) & 31
        blue = (color >> 10) & 31
        colors.append(
            (
                (red << 3) | (red >> 2),
                (green << 3) | (green >> 2),
                (blue << 3) | (blue >> 2),
            )
        )
    return tuple(colors)


def _status_panel_pixels() -> list[int]:
    """Build the exact state-free 240x32 original BG3 status shell.

    Tiles 449..457 are the original panel's interior, corners and borders.
    Dynamic glyph and bar tiles are deliberately excluded: the runtime
    continues to render identity, phase, stats and resources from live state.
    Four legal 64x32 OBJ frames cover the 240-pixel viewport; the final
    frame's off-screen 16 pixels stay transparent.
    """

    encoded = (
        STATUS_PANEL_EVIDENCE
        / "hud-shell-bg-tiles.bin"
    ).read_bytes()
    if len(encoded) != 9 * 32:
        raise ValueError(
            "the status-panel evidence must contain tiles 449..457"
        )
    tiles = [
        _decode_4bpp_tile(encoded[index * 32:(index + 1) * 32])
        for index in range(9)
    ]
    tile_roles = (
        (1,) + (5,) * 28 + (2,),
        (7,) + (0,) * 28 + (8,),
        (7,) + (0,) * 28 + (8,),
        (3,) + (6,) * 28 + (4,),
    )
    shell = [0] * (256 * STATUS_PANEL_HEIGHT)
    for tile_y, row in enumerate(tile_roles):
        for tile_x, tile_index in enumerate(row):
            tile = tiles[tile_index]
            for local_y in range(8):
                target = (
                    (tile_y * 8 + local_y) * 256
                    + tile_x * 8
                )
                source = local_y * 8
                shell[target:target + 8] = tile[source:source + 8]

    frames: list[int] = []
    for frame in range(STATUS_PANEL_FRAME_COUNT):
        left = frame * STATUS_PANEL_WIDTH
        for y in range(STATUS_PANEL_HEIGHT):
            row = y * 256 + left
            frames.extend(
                shell[row:row + STATUS_PANEL_WIDTH]
            )
    return frames


def _status_end_pixels() -> list[int]:
    """Extract the original 16x16 red phase label as a transparent OBJ."""

    palette_indices = {
        color: index
        for index, color in enumerate(TEXT_WARNING_PALETTE)
    }
    with Image.open(STATUS_END_SOURCE) as source_image:
        source = source_image.convert("RGB").crop(
            (104, 136, 120, 152)
        )
    pixels = []
    for color in source.get_flattened_data():
        if color == PALETTE[1]:
            pixels.append(0)
            continue
        try:
            pixels.append(palette_indices[color])
        except KeyError as error:
            raise ValueError(
                f"unexpected status-end color {color}"
            ) from error
    return pixels


def _bar_frame(
    shoulder_color: int,
    middle_color: int,
    highlight_color: int,
    side_inner_color: int | None = None,
) -> list[int]:
    pixels = [0] * (BAR_WIDTH * BAR_HEIGHT)
    content_left = 16
    content_right = 55
    content_top = BAR_VISIBLE_TOP
    content_bottom = BAR_VISIBLE_TOP + BAR_VISIBLE_HEIGHT - 1

    def set_pixel(x: int, y: int, color: int) -> None:
        pixels[y * BAR_WIDTH + x] = color

    # These eight rows are transcribed from the scenario-41 status HUD.
    # Slots 14 and 15 are bar-local intermediate golds; the panel keeps its
    # own palette, so no state text or panel color is coupled to this ramp.
    set_pixel(content_left, content_top, 10)
    set_pixel(content_left + 1, content_top, 15)
    for x in range(content_left + 2, content_right):
        set_pixel(x, content_top, 6)
    set_pixel(content_right, content_top, 15)

    inner_rows = (
        shoulder_color,
        middle_color,
        highlight_color,
        highlight_color,
        middle_color,
        shoulder_color,
    )
    side_shoulder = (
        shoulder_color
        if side_inner_color is None
        else side_inner_color
    )
    side_middle = (
        middle_color
        if side_inner_color is None
        else side_inner_color
    )
    side_rows = (
        (15, 10, 15, 6),
        (10, side_shoulder, side_shoulder, 6),
        (10, side_middle, side_middle, 6),
        (10, side_middle, side_middle, 6),
        (10, side_shoulder, side_shoulder, 6),
        (15, 10, 15, 6),
    )
    for offset, (inner, sides) in enumerate(
        zip(inner_rows, side_rows),
        start=1,
    ):
        y = content_top + offset
        set_pixel(content_left, y, sides[0])
        set_pixel(content_left + 1, y, sides[1])
        for x in range(content_left + 2, content_right - 1):
            set_pixel(x, y, inner)
        set_pixel(content_right - 1, y, sides[2])
        set_pixel(content_right, y, sides[3])

    for x in range(content_left, content_right - 1):
        set_pixel(x, content_bottom, 10)
    set_pixel(content_right - 1, content_bottom, 15)
    set_pixel(content_right, content_bottom, 10)
    return pixels


def _bar_pixels() -> list[int]:
    frames = (
        _bar_frame(5, 5, 1),
        _bar_frame(8, 9, 13),
        _bar_frame(14, 11, 7),
        _bar_frame(3, 3, 3, side_inner_color=4),
    )
    return [pixel for frame in frames for pixel in frame]


def _dialog_panel_pixels() -> list[int]:
    """Extract the exact state-free 80x64 original confirmation shell."""

    vram = (TARGET_CONFIRMATION_GPU_DIR / "vram.bin").read_bytes()
    if len(vram) != 0x18000:
        raise ValueError(
            "scenario 49 target-confirmation VRAM is incomplete"
        )

    # BG3 uses charblock 3 and screenblock 3.  The signed state stores
    # dynamic glyphs in other tiles, while these nine tiles are only the
    # reusable shell and parchment fill.
    tile_layout = (
        (
            (0x1C2,) + (0x1C6,) * 8 + (0x1C3,),
        )
        + (
            ((0x1C8,) + (0x1C1,) * 8 + (0x1C9,)),
        )
        * 6
        + (
            (0x1C4,) + (0x1C7,) * 8 + (0x1C5,),
        )
    )
    screen_entries = (
        (
            (0xE1C2,) + (0xE1C6,) * 8 + (0xE1C3,),
        )
        + (
            ((0xE1C8,) + (0xE1C1,) * 8 + (0xE1C9,)),
        )
        * 6
        + (
            (0xE1C4,) + (0xE1C7,) * 8 + (0xE1C5,),
        )
    )
    screenblock_offset = 3 * 0x800
    for row, expected_row in enumerate(screen_entries):
        for column, expected in enumerate(expected_row):
            if row not in (0, 7) and column not in (0, 9):
                continue
            actual = struct.unpack_from(
                "<H",
                vram,
                screenblock_offset
                + ((row + 3) * 32 + column + 10) * 2,
            )[0]
            if actual != expected:
                raise ValueError(
                    "scenario 49 target-confirmation BG3 shell "
                    "tilemap no longer matches the signed state"
                )

    source_to_runtime_index = {
        1: 1,
        3: 3,
        4: 4,
        5: 12,
        6: 6,
    }
    charblock_offset = 3 * 0x4000
    tiles: dict[int, list[int]] = {}
    for tile_index in range(0x1C1, 0x1CA):
        tile_offset = charblock_offset + tile_index * 32
        decoded = _decode_4bpp_tile(
            vram[tile_offset:tile_offset + 32]
        )
        try:
            tiles[tile_index] = [
                source_to_runtime_index[pixel]
                for pixel in decoded
            ]
        except KeyError as error:
            raise ValueError(
                "scenario 49 target-confirmation shell "
                f"uses unexpected palette index {error.args[0]}"
            ) from error

    panel: list[int] = []
    for tile_row in tile_layout:
        for pixel_y in range(8):
            for tile_index in tile_row:
                panel.extend(
                    tiles[tile_index][
                        pixel_y * 8:pixel_y * 8 + 8
                    ]
                )

    frames: list[int] = []
    for source_x, destination_x, width in (
        (0, 8, 24),
        (24, 0, 32),
        (56, 0, 24),
    ):
        frame = [0] * (
            DIALOG_PANEL_WIDTH * DIALOG_PANEL_HEIGHT
        )
        for y in range(DIALOG_PANEL_HEIGHT):
            source_offset = y * 80 + source_x
            destination_offset = (
                y * DIALOG_PANEL_WIDTH + destination_x
            )
            frame[
                destination_offset:
                destination_offset + width
            ] = panel[
                source_offset:source_offset + width
            ]
        frames.extend(frame)
    return frames


def _large_dialog_panel_frame(
    *,
    left: bool,
    right: bool,
    top: bool,
    bottom: bool,
) -> list[int]:
    """Build one quadrant of the original 112x80 defense dialog.

    Two 56x40 visible quadrants per row are centered in legal 64x64 OBJ
    frames.  Transparent margins remove both horizontal overlap and the
    unused lower 24 rows without baking any dialog text or selection state.
    """

    width = LARGE_DIALOG_PANEL_WIDTH
    height = LARGE_DIALOG_PANEL_HEIGHT
    content_left = 4
    content_right = 59
    content_top = 0
    content_bottom = 39
    pixels = [0] * (width * height)

    def set_pixel(x: int, y: int, color: int) -> None:
        pixels[y * width + x] = color

    for y in range(content_top, content_bottom + 1):
        for x in range(content_left, content_right + 1):
            set_pixel(x, y, 1)
    if top:
        for x in range(content_left, content_right + 1):
            set_pixel(x, content_top, 2)
            set_pixel(x, content_top + 1, 3)
            set_pixel(x, content_top + 2, 4)
    if bottom:
        for x in range(content_left, content_right + 1):
            set_pixel(x, content_bottom, 2)
            set_pixel(x, content_bottom - 1, 3)
            set_pixel(x, content_bottom - 2, 4)
    if left:
        for y in range(content_top, content_bottom + 1):
            set_pixel(content_left, y, 2)
            set_pixel(content_left + 1, y, 3)
            set_pixel(content_left + 2, y, 4)
    if right:
        for y in range(content_top, content_bottom + 1):
            set_pixel(content_right, y, 2)
            set_pixel(content_right - 1, y, 3)
            set_pixel(content_right - 2, y, 4)

    grain_top = content_top + (4 if top else 1)
    grain_bottom = content_bottom - (3 if bottom else 0)
    for y in range(grain_top, grain_bottom):
        for x in range(
            content_left + (4 if left else 0),
            content_right - (3 if right else 0),
        ):
            if (x * 5 + y * 11) % 47 == 0:
                set_pixel(x, y, 5)
            elif (x * 13 + y * 3) % 71 == 0:
                set_pixel(x, y, 13)
    if left and top:
        set_pixel(content_left, content_top, 0)
    if right and top:
        set_pixel(content_right, content_top, 0)
    if left and bottom:
        set_pixel(content_left, content_bottom, 0)
    if right and bottom:
        set_pixel(content_right, content_bottom, 0)
    return pixels


def _large_dialog_panel_pixels() -> list[int]:
    frames = (
        _large_dialog_panel_frame(
            left=True,
            right=False,
            top=True,
            bottom=False,
        ),
        _large_dialog_panel_frame(
            left=False,
            right=True,
            top=True,
            bottom=False,
        ),
        _large_dialog_panel_frame(
            left=True,
            right=False,
            top=False,
            bottom=True,
        ),
        _large_dialog_panel_frame(
            left=False,
            right=True,
            top=False,
            bottom=True,
        ),
    )
    return [pixel for frame in frames for pixel in frame]


def _message_panel_pixels() -> list[int]:
    """Extract the original state-free 240x64 dialogue window as OBJ slices."""

    source_bytes = MESSAGE_PANEL_SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != (
        MESSAGE_PANEL_SOURCE_SHA256
    ):
        raise ValueError("battle dialogue panel evidence hash mismatch")
    source = Image.open(MESSAGE_PANEL_SOURCE).convert("RGB")
    panel = source.crop((0, 96, 240, 160))
    # The signed BG window owns this whole interior.  Remove the speaker,
    # body text and continue icon while retaining every original border pixel.
    panel.paste(PALETTE[1], (8, 7, 232, 57))

    color_indices = {
        color: index
        for index, color in enumerate(MESSAGE_PANEL_PALETTE)
        if index != 0
    }
    color_indices[(0, 0, 0)] = 15
    frames: list[int] = []
    for frame_index in range(MESSAGE_PANEL_FRAME_COUNT):
        frame = [0] * (MESSAGE_PANEL_WIDTH * MESSAGE_PANEL_HEIGHT)
        for y in range(MESSAGE_PANEL_HEIGHT):
            for chunk_x in range(60):
                color = panel.getpixel((frame_index * 60 + chunk_x, y))
                if color not in color_indices:
                    raise ValueError(
                        f"unsupported battle dialogue panel color {color}"
                    )
                frame[y * MESSAGE_PANEL_WIDTH + chunk_x + 2] = (
                    color_indices[color]
                )
        frames.extend(frame)
    return frames


def _dialogue_background_image() -> Image.Image:
    """Reconstruct selector 1 BG0 exactly from the original GPU dump."""

    evidence: dict[str, bytes] = {}
    expected_sizes = {
        "io.bin": 0x400,
        "pram.bin": 0x400,
        "vram.bin": 0x18000,
    }
    for name, expected_hash in (
        DIALOGUE_BACKGROUND_EVIDENCE_SHA256.items()
    ):
        data = (DIALOGUE_BACKGROUND_EVIDENCE / name).read_bytes()
        if len(data) != expected_sizes[name]:
            raise ValueError(
                f"battle dialogue {name} evidence size mismatch"
            )
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise ValueError(
                f"battle dialogue {name} evidence hash mismatch"
            )
        evidence[name] = data

    io = evidence["io.bin"]
    pram = evidence["pram.bin"]
    vram = evidence["vram.bin"]
    control = struct.unpack_from("<H", io, 0x08)[0]
    if control & (1 << 7):
        raise ValueError("battle dialogue BG0 must be 4bpp")
    if ((control >> 14) & 3) != 0:
        raise ValueError("battle dialogue BG0 must be 256x256")

    character_base = ((control >> 2) & 3) * 0x4000
    screen_base = ((control >> 8) & 31) * 0x800
    horizontal = struct.unpack_from("<H", io, 0x10)[0] & 511
    vertical = struct.unpack_from("<H", io, 0x12)[0] & 511
    palette: list[int] = []
    for offset in range(0, 512, 2):
        value = struct.unpack_from("<H", pram, offset)[0]
        for channel in (
            value & 31,
            (value >> 5) & 31,
            (value >> 10) & 31,
        ):
            palette.append((channel << 3) | (channel >> 2))

    image = Image.new("P", (256, 256), 0)
    image.putpalette(palette)

    for screen_y in range(160):
        for screen_x in range(240):
            x = (screen_x + horizontal) & 255
            y = (screen_y + vertical) & 255
            entry = struct.unpack_from(
                "<H",
                vram,
                screen_base + ((y // 8) * 32 + x // 8) * 2,
            )[0]
            local_x = x & 7
            local_y = y & 7
            if entry & (1 << 10):
                local_x = 7 - local_x
            if entry & (1 << 11):
                local_y = 7 - local_y
            packed = vram[
                character_base
                + (entry & 0x3FF) * 32
                + local_y * 4
                + local_x // 2
            ]
            color = (
                packed >> 4 if local_x & 1 else packed & 0x0F
            )
            palette_index = (
                0 if color == 0
                else ((entry >> 12) & 15) * 16 + color
            )
            image.putpixel(
                (8 + screen_x, 48 + screen_y),
                palette_index,
            )
    return image


def _message_black_bar_pixels() -> list[int]:
    pixels = [0] * (
        MESSAGE_BLACK_BAR_WIDTH * MESSAGE_BLACK_BAR_HEIGHT
    )
    for y in range(12, 20):
        for x in range(2, 62):
            pixels[y * MESSAGE_BLACK_BAR_WIDTH + x] = 15
    return pixels


def _dialogue_speaker_label_pixels() -> list[int]:
    color_indices = {
        (231, 247, 214): 0,
        (115, 33, 255): 1,
        (189, 173, 222): 2,
    }
    pixels: list[int] = []
    for source_path, expected_hash in DIALOGUE_SPEAKER_LABEL_SOURCES:
        source_bytes = source_path.read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != expected_hash:
            raise ValueError(
                "battle dialogue speaker evidence hash mismatch"
            )
        label = Image.open(source_path).convert("RGB").crop(
            (16, 104, 48, 120)
        )
        for color in label.get_flattened_data():
            if color not in color_indices:
                raise ValueError(
                    f"unsupported battle dialogue speaker color {color}"
                )
            pixels.append(color_indices[color])
    return pixels


def _preparation_dialog_panel_frame(
    *,
    left: bool,
    right: bool,
) -> list[int]:
    width = PREPARATION_DIALOG_PANEL_WIDTH
    height = PREPARATION_DIALOG_PANEL_HEIGHT
    content_top = 8
    content_bottom = 55
    pixels = [0] * (width * height)
    source_left = 40 if left else 168 if right else 72
    palette_indices = {
        color: index for index, color in enumerate(PALETTE)
    }
    with Image.open(PREPARATION_CONFIRMATION_SOURCE) as source_image:
        source = source_image.convert("RGB")
        for y in range(content_top, content_bottom + 1):
            screen_y = 56 + y
            for x in range(width):
                sample_y = screen_y
                screen_x = source_left + x
                if (
                    48 <= screen_x < 192
                    and 72 <= screen_y < 104
                ):
                    # Prompt and choices are dynamic OBJ text.  The original
                    # dialog interior beneath them is the plain task-panel
                    # fill color, so keep the shell state-free.
                    pixels[y * width + x] = 1
                else:
                    rgb = source.getpixel(
                        (screen_x, sample_y)
                    )
                    pixels[y * width + x] = palette_indices[rgb]
    return pixels


def _preparation_dialog_panel_pixels() -> list[int]:
    frames = (
        _preparation_dialog_panel_frame(left=True, right=False),
        _preparation_dialog_panel_frame(left=False, right=False),
        _preparation_dialog_panel_frame(left=False, right=True),
    )
    return [pixel for frame in frames for pixel in frame]


def _range_tile(color: int, *, target: bool = False) -> list[int]:
    pixels = [0] * (RANGE_TILE_SIZE * RANGE_TILE_SIZE)
    for y in range(RANGE_TILE_SIZE):
        for x in range(RANGE_TILE_SIZE):
            border = x in (0, RANGE_TILE_SIZE - 1) or y in (
                0, RANGE_TILE_SIZE - 1)
            pattern = (x + y) % (2 if target else 4) == 0
            if border or pattern:
                pixels[y * RANGE_TILE_SIZE + x] = color
    return pixels


def _range_pixels() -> list[int]:
    frames = (
        [0] * (RANGE_TILE_SIZE * RANGE_TILE_SIZE),
        _range_tile(8),
        _range_tile(11),
        _range_tile(6, target=True),
    )
    return [pixel for frame in frames for pixel in frame]


def _preparation_background_pixels(
    *,
    confirmation: bool = False,
    overview: bool = False,
) -> list[int]:
    size = PREPARATION_BACKGROUND_SIZE
    pixels = [1] * (size * size)

    def set_pixel(x: int, y: int, color: int) -> None:
        pixels[y * size + x] = color

    def draw_approximate_panel(
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> None:
        right = left + width - 1
        bottom = top + height - 1
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                edge_distance = min(
                    x - left,
                    right - x,
                    y - top,
                    bottom - y,
                )
                if edge_distance == 0:
                    color = 2
                elif edge_distance == 1:
                    color = 3
                elif edge_distance == 2:
                    color = 4
                elif (x * 5 + y * 11) % 47 == 0:
                    color = 5
                elif (x * 13 + y * 3) % 71 == 0:
                    color = 13
                else:
                    color = 1
                set_pixel(x, y, color)

    palette_indices = {
        color: index for index, color in enumerate(PALETTE)
    }

    def draw_original_panel_border(
        source: Image.Image,
        source_left: int,
        source_top: int,
        width: int,
        height: int,
        destination_left: int,
        destination_top: int,
        *,
        clear_root_cursor: bool = False,
    ) -> None:
        """Copy only the original eight-pixel frame, never its text/state."""

        for y in range(height):
            for x in range(width):
                destination_x = destination_left + x
                destination_y = destination_top + y
                if (
                    x < 8
                    or x >= width - 8
                    or y < 8
                    or y >= height - 8
                ):
                    source_x = source_left + x
                    source_y = source_top + y
                    rgb = source.getpixel((source_x, source_y))
                    if (
                        clear_root_cursor
                        and 72 <= source_x < 80
                        and 60 <= source_y < 68
                        and rgb not in palette_indices
                    ):
                        # The reference checkpoint contains the selected
                        # option cursor.  Restore the same repeating vertical
                        # frame segment from the next option row so this OBJ
                        # remains state-free; the cursor is rendered by its
                        # own movable sprite.
                        rgb = source.getpixel(
                            (source_x, source_y + 16)
                        )
                    color = palette_indices.get(rgb)
                    if color is None:
                        color = min(
                            range(len(PALETTE)),
                            key=lambda index: sum(
                                (
                                    rgb[channel]
                                    - PALETTE[index][channel]
                                )
                                ** 2
                                for channel in range(3)
                            ),
                        )
                else:
                    color = 1
                set_pixel(destination_x, destination_y, color)

    # A 256x256 regular background is centered by Butano.  The visible
    # 240x160 viewport therefore begins at (8, 48).
    with Image.open(PREPARATION_OVERVIEW_SOURCE) as source_image:
        source = source_image.convert("RGB")
        draw_original_panel_border(
            source, 0, 0, 240, 32, 8, 48
        )
        draw_original_panel_border(
            source, 0, 32, 240, 128, 8, 80
        )
    if not overview:
        with Image.open(PREPARATION_MENU_SOURCE) as source_image:
            source = source_image.convert("RGB")
            draw_original_panel_border(
                source,
                72,
                48,
                96,
                80,
                80,
                96,
                clear_root_cursor=True,
            )
    if confirmation:
        draw_approximate_panel(48, 112, 160, 48)
    return pixels


def _preparation_menu_panel_pixels() -> list[int]:
    """Pack the state-free 96x80 original menu into four legal 64x64 OBJs."""

    background = _preparation_background_pixels()
    background_size = PREPARATION_BACKGROUND_SIZE
    frame_size = PREPARATION_MENU_PANEL_SIZE
    result: list[int] = []
    slices = (
        (80, 96, 16, 24),
        (128, 96, 0, 24),
        (80, 136, 16, 0),
        (128, 136, 0, 0),
    )
    for source_left, source_top, destination_left, destination_top in slices:
        frame = [0] * (frame_size * frame_size)
        for y in range(40):
            for x in range(48):
                frame[
                    (destination_top + y) * frame_size
                    + destination_left
                    + x
                ] = background[
                    (source_top + y) * background_size
                    + source_left
                    + x
                ]
        result.extend(frame)
    return result


def _preparation_cursor_pixels() -> list[int]:
    """Extract the scenario-49 dark-phase cursor as a movable 8x8 OBJ."""

    palette_indices: dict[tuple[int, int, int], int] = {}
    for index, color in enumerate(PREPARATION_CURSOR_PALETTE):
        palette_indices.setdefault(color, index)
    pixels: list[int] = []
    with Image.open(PREPARATION_BEE_ROOT_SOURCE) as source_image:
        source = source_image.convert("RGB")
        for y in range(60, 68):
            for x in range(72, 80):
                rgb = source.getpixel((x, y))
                cursor_free_rgb = source.getpixel((x, y + 16))
                pixels.append(
                    palette_indices[rgb]
                    if rgb != cursor_free_rgb
                    else 0
                )
    return pixels


def _gba_color(value: int) -> tuple[int, int, int]:
    def expand(component: int) -> int:
        return (component << 3) | (component >> 2)

    return (
        expand(value & 0x1F),
        expand((value >> 5) & 0x1F),
        expand((value >> 10) & 0x1F),
    )


def _command_cursor_pixels() -> list[int]:
    """Extract the original command cursor from its OBJ tiles."""

    oam = (COMMAND_CURSOR_GPU_DIR / "oam.bin").read_bytes()
    attribute_0, attribute_1, attribute_2 = struct.unpack_from(
        "<HHH", oam
    )
    if (
        attribute_0 != 0x8030
        or attribute_1 != 0x0008
        or attribute_2 != 0xF3F4
    ):
        raise ValueError(
            "scenario 49 command cursor OAM no longer matches "
            "the signed 8x16 OBJ at screen position (8, 48)"
        )

    tile_index = attribute_2 & 0x03FF
    vram = (COMMAND_CURSOR_GPU_DIR / "vram.bin").read_bytes()
    tile_offset = 0x10000 + tile_index * 32
    tile_bytes = vram[
        tile_offset:
        tile_offset + COMMAND_CURSOR_HEIGHT // 8 * 32
    ]
    if len(tile_bytes) != 64:
        raise ValueError("scenario 49 command cursor OBJ tiles are missing")

    pixels: list[int] = []
    for tile_row in range(COMMAND_CURSOR_HEIGHT // 8):
        for y in range(8):
            row_offset = tile_row * 32 + y * 4
            for packed in tile_bytes[row_offset:row_offset + 4]:
                pixels.append(packed & 0x0F)
                pixels.append(packed >> 4)
    return pixels


def _command_cursor_palette() -> tuple[tuple[int, int, int], ...]:
    """Read the cursor's original OBJ palette bank from signed GPU data."""

    oam = (COMMAND_CURSOR_GPU_DIR / "oam.bin").read_bytes()
    attribute_2 = struct.unpack_from("<H", oam, 4)[0]
    palette_bank = attribute_2 >> 12
    pram = (COMMAND_CURSOR_GPU_DIR / "pram.bin").read_bytes()
    palette_offset = 0x200 + palette_bank * 32
    colors = [(0, 0, 0)]
    for index in range(1, 16):
        value = struct.unpack_from(
            "<H",
            pram,
            palette_offset + index * 2,
        )[0]
        colors.append(_gba_color(value))
    return tuple(colors)


def _confirmation_cursor_pixels() -> list[int]:
    """Extract the original target-confirmation cursor OBJ."""

    oam = (TARGET_CONFIRMATION_GPU_DIR / "oam.bin").read_bytes()
    attribute_0, attribute_1, attribute_2 = struct.unpack_from(
        "<HHH", oam
    )
    if (
        attribute_0 != 0x8030
        or attribute_1 != 0x0068
        or attribute_2 != 0xF3F6
    ):
        raise ValueError(
            "scenario 49 confirmation cursor OAM no longer matches "
            "the signed 8x16 OBJ at screen position (104, 48)"
        )

    tile_index = attribute_2 & 0x03FF
    vram = (TARGET_CONFIRMATION_GPU_DIR / "vram.bin").read_bytes()
    tile_offset = 0x10000 + tile_index * 32
    tile_bytes = vram[
        tile_offset:
        tile_offset + CONFIRMATION_CURSOR_HEIGHT // 8 * 32
    ]
    if len(tile_bytes) != 64:
        raise ValueError(
            "scenario 49 confirmation cursor OBJ tiles are missing"
        )

    pixels: list[int] = []
    for tile_row in range(CONFIRMATION_CURSOR_HEIGHT // 8):
        for y in range(8):
            row_offset = tile_row * 32 + y * 4
            for packed in tile_bytes[row_offset:row_offset + 4]:
                pixels.append(packed & 0x0F)
                pixels.append(packed >> 4)
    return pixels


def _confirmation_cursor_palette() -> tuple[
    tuple[int, int, int], ...
]:
    """Read the confirmation cursor's signed OBJ palette bank."""

    oam = (TARGET_CONFIRMATION_GPU_DIR / "oam.bin").read_bytes()
    attribute_2 = struct.unpack_from("<H", oam, 4)[0]
    palette_bank = attribute_2 >> 12
    pram = (TARGET_CONFIRMATION_GPU_DIR / "pram.bin").read_bytes()
    palette_offset = 0x200 + palette_bank * 32
    colors = [(0, 0, 0)]
    for index in range(1, 16):
        value = struct.unpack_from(
            "<H",
            pram,
            palette_offset + index * 2,
        )[0]
        colors.append(_gba_color(value))
    return tuple(colors)


def _obj_4bpp_pixels(
    vram: bytes,
    tile_index: int,
    width: int,
    height: int,
) -> list[int]:
    """Decode one-dimensional 4bpp OBJ tiles into row-major pixels."""

    tile_columns = width // 8
    tile_rows = height // 8
    pixels = [0] * (width * height)
    for tile_y in range(tile_rows):
        for tile_x in range(tile_columns):
            source_tile = (
                tile_index + tile_y * tile_columns + tile_x
            )
            tile_offset = 0x10000 + source_tile * 32
            tile = vram[tile_offset:tile_offset + 32]
            if len(tile) != 32:
                raise ValueError(
                    f"OBJ tile {source_tile} is missing"
                )
            for y in range(8):
                destination = (
                    (tile_y * 8 + y) * width + tile_x * 8
                )
                for packed_index, packed in enumerate(
                    tile[y * 4:y * 4 + 4]
                ):
                    pixels[destination + packed_index * 2] = (
                        packed & 0x0F
                    )
                    pixels[
                        destination + packed_index * 2 + 1
                    ] = packed >> 4
    return pixels


def _action_control_palette() -> tuple[
    tuple[int, int, int], ...
]:
    """Read palette bank 15 used by the signed action-menu controls."""

    pram = (ACTION_MENU_GPU_DIR / "pram.bin").read_bytes()
    palette_offset = 0x200 + 15 * 32
    colors = [(0, 0, 0)]
    for index in range(1, 16):
        value = struct.unpack_from(
            "<H",
            pram,
            palette_offset + index * 2,
        )[0]
        colors.append(_gba_color(value))
    return tuple(colors)


def _action_cursor_pixels() -> list[int]:
    """Extract the action-row cursor from signed OAM entry 0."""

    oam = (ACTION_MENU_GPU_DIR / "oam.bin").read_bytes()
    attributes = struct.unpack_from("<HHH", oam, 0)
    if attributes != (0x8028, 0x0000, 0xF3F8):
        raise ValueError(
            "scenario 49 action cursor no longer matches "
            "the signed 8x16 OBJ at screen position (0, 40)"
        )
    vram = (ACTION_MENU_GPU_DIR / "vram.bin").read_bytes()
    return _obj_4bpp_pixels(
        vram,
        attributes[2] & 0x03FF,
        ACTION_CURSOR_WIDTH,
        ACTION_CURSOR_HEIGHT,
    )


def _action_start_hint_pixels() -> list[int]:
    """Compose the signed START hint OAM entries into one 32x16 OBJ."""

    oam = (ACTION_MENU_GPU_DIR / "oam.bin").read_bytes()
    right_attributes = struct.unpack_from("<HHH", oam, 2 * 8)
    left_attributes = struct.unpack_from("<HHH", oam, 3 * 8)
    if (
        right_attributes != (0x8078, 0x00A8, 0xF3D8)
        or left_attributes != (0x0078, 0x4098, 0xF3DA)
    ):
        raise ValueError(
            "scenario 49 START hint no longer matches signed "
            "OAM entries 2 and 3"
        )
    vram = (ACTION_MENU_GPU_DIR / "vram.bin").read_bytes()
    left = _obj_4bpp_pixels(
        vram,
        left_attributes[2] & 0x03FF,
        16,
        16,
    )
    right = _obj_4bpp_pixels(
        vram,
        right_attributes[2] & 0x03FF,
        8,
        16,
    )
    pixels = [0] * (
        ACTION_START_HINT_WIDTH * ACTION_START_HINT_HEIGHT
    )
    for y in range(ACTION_START_HINT_HEIGHT):
        destination = y * ACTION_START_HINT_WIDTH
        pixels[destination:destination + 16] = (
            left[y * 16:y * 16 + 16]
        )
        pixels[destination + 16:destination + 24] = (
            right[y * 8:y * 8 + 8]
        )
    return pixels


def _action_back_hint_pixels() -> list[int]:
    """Extract the signed B-button hint from OAM entry 1."""

    oam = (ACTION_MENU_GPU_DIR / "oam.bin").read_bytes()
    attributes = struct.unpack_from("<HHH", oam, 1 * 8)
    if attributes != (0x0088, 0x40C8, 0xF3D4):
        raise ValueError(
            "scenario 49 B hint no longer matches the signed "
            "16x16 OBJ at screen position (200, 136)"
        )
    vram = (ACTION_MENU_GPU_DIR / "vram.bin").read_bytes()
    return _obj_4bpp_pixels(
        vram,
        attributes[2] & 0x03FF,
        ACTION_BACK_HINT_WIDTH,
        ACTION_BACK_HINT_HEIGHT,
    )


def _action_actor_stats_pixels() -> list[int]:
    """Extract the fixed compact 体力/查克拉 labels as one UI element."""

    source_path = ACTION_MENU_GPU_DIR / "frame.png"
    palette_indices = {
        (231, 247, 214): 0,
        (57, 66, 57): 2,
        (173, 181, 156): 5,
    }
    pixels = [0] * (
        ACTION_ACTOR_STATS_WIDTH * ACTION_ACTOR_STATS_HEIGHT
    )
    with Image.open(source_path) as source_image:
        source = source_image.convert("RGB")
        for y in range(ACTION_ACTOR_STATS_HEIGHT):
            for x in range(24):
                color = source.getpixel((80 + x, 8 + y))
                try:
                    pixels[
                        y * ACTION_ACTOR_STATS_WIDTH + x
                    ] = palette_indices[color]
                except KeyError as error:
                    raise ValueError(
                        "action actor-stat source uses an "
                        f"unexpected color {color}"
                    ) from error
    return pixels


def _action_background_pixels() -> list[int]:
    frame_size = 64

    def frame(
        row: int,
        *,
        separator: bool,
    ) -> list[int]:
        # The last screen row is visible only through y=159.  Its lower
        # half stays transparent so the 64x64 sprite can legally represent
        # the original 48px description/help panel without covering the map.
        opaque_height = 32 if row == 2 else 64
        pixels = [0] * (frame_size * frame_size)

        def set_pixel(x: int, y: int, color: int) -> None:
            pixels[y * frame_size + x] = color

        for y in range(opaque_height):
            for x in range(frame_size):
                if (x * 5 + (y + row * 64) * 11) % 47 == 0:
                    color = 5
                elif (x * 13 + (y + row * 64) * 3) % 71 == 0:
                    color = 13
                else:
                    color = 1
                set_pixel(x, y, color)

        # Original action browser horizontal structure:
        # y=28 splits actor status from the action list,
        # y=112 starts the description/help panel,
        # y=159 closes the visible panel.
        borders = {
            0: (28,),
            1: (48,),
            2: (31,),
        }[row]
        for border_y in borders:
            for x in range(frame_size):
                set_pixel(x, border_y, 2)
                if border_y + 1 < opaque_height:
                    set_pixel(x, border_y + 1, 3)
                if border_y + 2 < opaque_height:
                    set_pixel(x, border_y + 2, 4)

        # The right-side statistics panel begins at screen x=152.  It falls
        # at local x=24 in column two.  Only this frame differs from the
        # common row frame and can therefore be reused by all other columns.
        if separator and row < 2:
            separator_height = 48 if row == 1 else opaque_height
            for y in range(separator_height):
                set_pixel(24, y, 2)
                set_pixel(25, y, 3)
                set_pixel(26, y, 4)
        return pixels

    result: list[int] = []
    for row in range(3):
        result.extend(frame(row, separator=False))
        result.extend(frame(row, separator=True))
    return result


def _action_icon_pixels() -> list[int]:
    """Pack six original category/effect glyphs into 16px sprite frames."""

    palette_indices = {
        color: index
        for index, color in enumerate(ACTION_ICON_PALETTE)
    }
    pixels: list[int] = []
    with Image.open(ACTION_MENU_SOURCE) as source_image:
        source = source_image.convert("RGB")
        for source_left, source_top in ACTION_ICON_SOURCE_ORIGINS:
            for y in range(ACTION_ICON_SIZE):
                for x in range(ACTION_ICON_SIZE):
                    color = source.getpixel(
                        (source_left + x, source_top + y)
                    )
                    if color not in palette_indices:
                        raise ValueError(
                            "action icon source uses an unexpected "
                            f"color {color} at "
                            f"({source_left + x}, {source_top + y})"
                        )
                    pixels.append(palette_indices[color])
    return pixels


def generate_outputs(output_directory: Path | str) -> dict[str, Path]:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    for stale_name in (
        "battle_ui_dialogue_upper_forest_wide.bmp",
        "battle_ui_dialogue_upper_forest_wide.json",
        "battle_ui_dialogue_upper_forest_narrow.bmp",
        "battle_ui_dialogue_upper_forest_narrow.json",
        "battle_ui_dialogue_upper_grass_wide.bmp",
        "battle_ui_dialogue_upper_grass_wide.json",
        "battle_ui_dialogue_upper_grass_tail.bmp",
        "battle_ui_dialogue_upper_grass_tail.json",
    ):
        (output_directory / stale_name).unlink(missing_ok=True)
    outputs = {
        "panel_bitmap": output_directory / "battle_ui_panel.bmp",
        "panel_metadata": output_directory / "battle_ui_panel.json",
        "status_panel_bitmap": (
            output_directory / "battle_ui_status_panel.bmp"
        ),
        "status_panel_metadata": (
            output_directory / "battle_ui_status_panel.json"
        ),
        "status_end_bitmap": (
            output_directory / "battle_ui_status_end.bmp"
        ),
        "status_end_metadata": (
            output_directory / "battle_ui_status_end.json"
        ),
        "bar_bitmap": output_directory / "battle_ui_bar.bmp",
        "bar_metadata": output_directory / "battle_ui_bar.json",
        "dialog_panel_bitmap": (
            output_directory / "battle_ui_dialog_panel.bmp"
        ),
        "dialog_panel_metadata": (
            output_directory / "battle_ui_dialog_panel.json"
        ),
        "large_dialog_panel_bitmap": (
            output_directory / "battle_ui_large_dialog_panel.bmp"
        ),
        "large_dialog_panel_metadata": (
            output_directory / "battle_ui_large_dialog_panel.json"
        ),
        "message_panel_bitmap": (
            output_directory / "battle_ui_message_panel.bmp"
        ),
        "message_panel_metadata": (
            output_directory / "battle_ui_message_panel.json"
        ),
        "dialogue_background_bitmap": (
            output_directory
            / "battle_ui_dialogue_background.bmp"
        ),
        "dialogue_background_metadata": (
            output_directory
            / "battle_ui_dialogue_background.json"
        ),
        "message_black_bar_bitmap": (
            output_directory / "battle_ui_message_black_bar.bmp"
        ),
        "message_black_bar_metadata": (
            output_directory / "battle_ui_message_black_bar.json"
        ),
        "dialogue_text_palette_bitmap": (
            output_directory
            / "battle_ui_dialogue_text_palette.bmp"
        ),
        "dialogue_text_palette_metadata": (
            output_directory
            / "battle_ui_dialogue_text_palette.json"
        ),
        "dialogue_speaker_palette_bitmap": (
            output_directory
            / "battle_ui_dialogue_speaker_palette.bmp"
        ),
        "dialogue_speaker_palette_metadata": (
            output_directory
            / "battle_ui_dialogue_speaker_palette.json"
        ),
        "dialogue_speaker_label_bitmap": (
            output_directory
            / "battle_ui_dialogue_speaker_label.bmp"
        ),
        "dialogue_speaker_label_metadata": (
            output_directory
            / "battle_ui_dialogue_speaker_label.json"
        ),
        "text_accent_palette_bitmap": (
            output_directory
            / "battle_ui_text_accent_palette.bmp"
        ),
        "text_accent_palette_metadata": (
            output_directory
            / "battle_ui_text_accent_palette.json"
        ),
        "text_warning_palette_bitmap": (
            output_directory
            / "battle_ui_text_warning_palette.bmp"
        ),
        "text_warning_palette_metadata": (
            output_directory
            / "battle_ui_text_warning_palette.json"
        ),
        "preparation_text_palette_bitmap": (
            output_directory
            / "battle_ui_preparation_text_palette.bmp"
        ),
        "preparation_text_palette_metadata": (
            output_directory
            / "battle_ui_preparation_text_palette.json"
        ),
        "preparation_accent_palette_bitmap": (
            output_directory
            / "battle_ui_preparation_accent_palette.bmp"
        ),
        "preparation_accent_palette_metadata": (
            output_directory
            / "battle_ui_preparation_accent_palette.json"
        ),
        "preparation_menu_panel_bitmap": (
            output_directory
            / "battle_ui_preparation_menu_panel.bmp"
        ),
        "preparation_menu_panel_metadata": (
            output_directory
            / "battle_ui_preparation_menu_panel.json"
        ),
        "preparation_cursor_bitmap": (
            output_directory
            / "battle_ui_preparation_cursor.bmp"
        ),
        "preparation_cursor_metadata": (
            output_directory
            / "battle_ui_preparation_cursor.json"
        ),
        "command_cursor_bitmap": (
            output_directory / "battle_ui_command_cursor.bmp"
        ),
        "command_cursor_metadata": (
            output_directory / "battle_ui_command_cursor.json"
        ),
        "confirmation_cursor_bitmap": (
            output_directory
            / "battle_ui_confirmation_cursor.bmp"
        ),
        "confirmation_cursor_metadata": (
            output_directory
            / "battle_ui_confirmation_cursor.json"
        ),
        "map_hint_palette_bitmap": (
            output_directory
            / "battle_ui_map_hint_palette.bmp"
        ),
        "map_hint_palette_metadata": (
            output_directory
            / "battle_ui_map_hint_palette.json"
        ),
        "result_background_bitmap": (
            output_directory
            / "battle_ui_result_background.bmp"
        ),
        "result_background_metadata": (
            output_directory
            / "battle_ui_result_background.json"
        ),
        "result_panel_bitmap": (
            output_directory
            / "battle_ui_result_panel.bmp"
        ),
        "result_panel_metadata": (
            output_directory
            / "battle_ui_result_panel.json"
        ),
        "result_naruto_bitmap": (
            output_directory / "battle_ui_result_naruto.bmp"
        ),
        "result_naruto_metadata": (
            output_directory / "battle_ui_result_naruto.json"
        ),
        "result_sasuke_bitmap": (
            output_directory / "battle_ui_result_sasuke.bmp"
        ),
        "result_sasuke_metadata": (
            output_directory / "battle_ui_result_sasuke.json"
        ),
        "result_sakura_bitmap": (
            output_directory / "battle_ui_result_sakura.bmp"
        ),
        "result_sakura_metadata": (
            output_directory / "battle_ui_result_sakura.json"
        ),
        "result_total_palette_bitmap": (
            output_directory
            / "battle_ui_result_total_palette.bmp"
        ),
        "result_total_palette_metadata": (
            output_directory
            / "battle_ui_result_total_palette.json"
        ),
        "level_up_panel_bitmap": (
            output_directory / "battle_ui_level_up_panel.bmp"
        ),
        "level_up_panel_metadata": (
            output_directory / "battle_ui_level_up_panel.json"
        ),
        "level_up_title_bitmap": (
            output_directory / "battle_ui_level_up_title.bmp"
        ),
        "level_up_title_metadata": (
            output_directory / "battle_ui_level_up_title.json"
        ),
        "level_up_value_bitmap": (
            output_directory / "battle_ui_level_up_value.bmp"
        ),
        "level_up_value_metadata": (
            output_directory / "battle_ui_level_up_value.json"
        ),
        "level_up_portrait_64x64_bitmap": (
            output_directory
            / "battle_ui_level_up_portrait_64x64.bmp"
        ),
        "level_up_portrait_64x64_metadata": (
            output_directory
            / "battle_ui_level_up_portrait_64x64.json"
        ),
        "level_up_portrait_16x32_bitmap": (
            output_directory
            / "battle_ui_level_up_portrait_16x32.bmp"
        ),
        "level_up_portrait_16x32_metadata": (
            output_directory
            / "battle_ui_level_up_portrait_16x32.json"
        ),
        "level_up_portrait_32x16_bitmap": (
            output_directory
            / "battle_ui_level_up_portrait_32x16.bmp"
        ),
        "level_up_portrait_32x16_metadata": (
            output_directory
            / "battle_ui_level_up_portrait_32x16.json"
        ),
        "level_up_portrait_16x16_bitmap": (
            output_directory
            / "battle_ui_level_up_portrait_16x16.bmp"
        ),
        "level_up_portrait_16x16_metadata": (
            output_directory
            / "battle_ui_level_up_portrait_16x16.json"
        ),
        "level_up_eye_bitmap": (
            output_directory / "battle_ui_level_up_eye.bmp"
        ),
        "level_up_eye_metadata": (
            output_directory / "battle_ui_level_up_eye.json"
        ),
        "training_panel_bitmap": (
            output_directory / "battle_ui_training_panel.bmp"
        ),
        "training_panel_metadata": (
            output_directory / "battle_ui_training_panel.json"
        ),
        "preparation_dialog_panel_bitmap": (
            output_directory
            / "battle_ui_preparation_dialog_panel.bmp"
        ),
        "preparation_dialog_panel_metadata": (
            output_directory
            / "battle_ui_preparation_dialog_panel.json"
        ),
        "range_tiles_bitmap": (
            output_directory / "battle_range_overlay_tiles.bmp"
        ),
        "range_tiles_metadata": (
            output_directory / "battle_range_overlay_tiles.json"
        ),
        "range_palette_bitmap": (
            output_directory / "battle_range_overlay_palette.bmp"
        ),
        "range_palette_metadata": (
            output_directory / "battle_range_overlay_palette.json"
        ),
        "preparation_background_bitmap": (
            output_directory / "battle_preparation_background.bmp"
        ),
        "preparation_background_metadata": (
            output_directory / "battle_preparation_background.json"
        ),
        "preparation_overview_background_bitmap": (
            output_directory
            / "battle_preparation_overview_background.bmp"
        ),
        "preparation_overview_background_metadata": (
            output_directory
            / "battle_preparation_overview_background.json"
        ),
        "preparation_confirmation_background_bitmap": (
            output_directory
            / "battle_preparation_confirmation_background.bmp"
        ),
        "preparation_confirmation_background_metadata": (
            output_directory
            / "battle_preparation_confirmation_background.json"
        ),
        "action_background_bitmap": (
            output_directory / "battle_ui_action_background.bmp"
        ),
        "action_background_metadata": (
            output_directory / "battle_ui_action_background.json"
        ),
        "action_icon_bitmap": (
            output_directory / "battle_ui_action_icon.bmp"
        ),
        "action_icon_metadata": (
            output_directory / "battle_ui_action_icon.json"
        ),
        "action_cursor_bitmap": (
            output_directory / "battle_ui_action_cursor.bmp"
        ),
        "action_cursor_metadata": (
            output_directory / "battle_ui_action_cursor.json"
        ),
        "action_start_hint_bitmap": (
            output_directory / "battle_ui_action_start_hint.bmp"
        ),
        "action_start_hint_metadata": (
            output_directory / "battle_ui_action_start_hint.json"
        ),
        "action_back_hint_bitmap": (
            output_directory / "battle_ui_action_back_hint.bmp"
        ),
        "action_back_hint_metadata": (
            output_directory / "battle_ui_action_back_hint.json"
        ),
        "action_actor_stats_bitmap": (
            output_directory / "battle_ui_action_actor_stats.bmp"
        ),
        "action_actor_stats_metadata": (
            output_directory / "battle_ui_action_actor_stats.json"
        ),
    }
    for page in range(TRAINING_PAGE_COUNT):
        outputs[f"training_text_{page}_bitmap"] = (
            output_directory
            / f"battle_ui_training_text_{page}.bmp"
        )
        outputs[f"training_text_{page}_metadata"] = (
            output_directory
            / f"battle_ui_training_text_{page}.json"
        )
    write_4bpp_bmp(
        outputs["panel_bitmap"],
        PANEL_WIDTH,
        PANEL_HEIGHT * PANEL_FRAME_COUNT,
        _panel_pixels(),
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["status_panel_bitmap"],
        STATUS_PANEL_WIDTH,
        STATUS_PANEL_HEIGHT * STATUS_PANEL_FRAME_COUNT,
        _status_panel_pixels(),
        _status_panel_palette(),
    )
    write_4bpp_bmp(
        outputs["status_end_bitmap"],
        STATUS_END_SIZE,
        STATUS_END_SIZE,
        _status_end_pixels(),
        TEXT_WARNING_PALETTE,
    )
    write_4bpp_bmp(
        outputs["bar_bitmap"],
        BAR_WIDTH,
        BAR_HEIGHT * BAR_FRAME_COUNT,
        _bar_pixels(),
        BAR_PALETTE,
    )
    write_4bpp_bmp(
        outputs["dialog_panel_bitmap"],
        DIALOG_PANEL_WIDTH,
        DIALOG_PANEL_HEIGHT * DIALOG_PANEL_FRAME_COUNT,
        _dialog_panel_pixels(),
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["large_dialog_panel_bitmap"],
        LARGE_DIALOG_PANEL_WIDTH,
        LARGE_DIALOG_PANEL_HEIGHT * LARGE_DIALOG_PANEL_FRAME_COUNT,
        _large_dialog_panel_pixels(),
        PALETTE,
    )
    _dialogue_background_image().save(
        outputs["dialogue_background_bitmap"]
    )
    write_4bpp_bmp(
        outputs["message_panel_bitmap"],
        MESSAGE_PANEL_WIDTH,
        MESSAGE_PANEL_HEIGHT * MESSAGE_PANEL_FRAME_COUNT,
        _message_panel_pixels(),
        MESSAGE_PANEL_PALETTE,
    )
    write_4bpp_bmp(
        outputs["message_black_bar_bitmap"],
        MESSAGE_BLACK_BAR_WIDTH,
        MESSAGE_BLACK_BAR_HEIGHT,
        _message_black_bar_pixels(),
        MESSAGE_PANEL_PALETTE,
    )
    write_4bpp_bmp(
        outputs["dialogue_text_palette_bitmap"],
        8,
        8,
        [
            index % len(DIALOGUE_TEXT_PALETTE)
            for index in range(64)
        ],
        DIALOGUE_TEXT_PALETTE,
    )
    write_4bpp_bmp(
        outputs["dialogue_speaker_palette_bitmap"],
        8,
        8,
        [
            index % len(DIALOGUE_SPEAKER_PALETTE)
            for index in range(64)
        ],
        DIALOGUE_SPEAKER_PALETTE,
    )
    write_4bpp_bmp(
        outputs["dialogue_speaker_label_bitmap"],
        DIALOGUE_SPEAKER_LABEL_WIDTH,
        (
            DIALOGUE_SPEAKER_LABEL_HEIGHT *
            DIALOGUE_SPEAKER_LABEL_FRAME_COUNT
        ),
        _dialogue_speaker_label_pixels(),
        DIALOGUE_SPEAKER_LABEL_PALETTE,
    )
    write_4bpp_bmp(
        outputs["text_accent_palette_bitmap"],
        8,
        8,
        [index % len(TEXT_ACCENT_PALETTE) for index in range(64)],
        TEXT_ACCENT_PALETTE,
    )
    write_4bpp_bmp(
        outputs["text_warning_palette_bitmap"],
        8,
        8,
        [
            index % len(TEXT_WARNING_PALETTE)
            for index in range(64)
        ],
        TEXT_WARNING_PALETTE,
    )
    write_4bpp_bmp(
        outputs["preparation_text_palette_bitmap"],
        8,
        8,
        [
            index % len(PREPARATION_TEXT_PALETTE)
            for index in range(64)
        ],
        PREPARATION_TEXT_PALETTE,
    )
    write_4bpp_bmp(
        outputs["preparation_accent_palette_bitmap"],
        8,
        8,
        [
            index % len(PREPARATION_ACCENT_PALETTE)
            for index in range(64)
        ],
        PREPARATION_ACCENT_PALETTE,
    )
    write_4bpp_bmp(
        outputs["preparation_menu_panel_bitmap"],
        PREPARATION_MENU_PANEL_SIZE,
        PREPARATION_MENU_PANEL_SIZE
        * PREPARATION_MENU_PANEL_FRAME_COUNT,
        _preparation_menu_panel_pixels(),
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["preparation_cursor_bitmap"],
        PREPARATION_CURSOR_SIZE,
        PREPARATION_CURSOR_SIZE,
        _preparation_cursor_pixels(),
        PREPARATION_CURSOR_PALETTE,
    )
    write_4bpp_bmp(
        outputs["command_cursor_bitmap"],
        COMMAND_CURSOR_WIDTH,
        COMMAND_CURSOR_HEIGHT,
        _command_cursor_pixels(),
        _command_cursor_palette(),
    )
    write_4bpp_bmp(
        outputs["confirmation_cursor_bitmap"],
        CONFIRMATION_CURSOR_WIDTH,
        CONFIRMATION_CURSOR_HEIGHT,
        _confirmation_cursor_pixels(),
        _confirmation_cursor_palette(),
    )
    write_4bpp_bmp(
        outputs["map_hint_palette_bitmap"],
        8,
        8,
        [index % len(MAP_HINT_PALETTE) for index in range(64)],
        MAP_HINT_PALETTE,
    )
    write_4bpp_bmp(
        outputs["result_background_bitmap"],
        RESULT_BACKGROUND_SIZE,
        RESULT_BACKGROUND_SIZE,
        _result_background_pixels(),
        _result_palette(13),
    )
    write_4bpp_bmp(
        outputs["result_panel_bitmap"],
        RESULT_BACKGROUND_SIZE,
        RESULT_BACKGROUND_SIZE,
        _result_panel_pixels(),
        _result_palette(14),
    )
    for key, oam_index in (
        ("result_naruto", 2),
        ("result_sasuke", 1),
        ("result_sakura", 0),
    ):
        write_4bpp_bmp(
            outputs[f"{key}_bitmap"],
            32,
            64,
            _result_participant_pixels(oam_index),
            _result_participant_palette(oam_index),
        )
    write_4bpp_bmp(
        outputs["result_total_palette_bitmap"],
        8,
        8,
        [
            index % len(RESULT_TOTAL_PALETTE)
            for index in range(64)
        ],
        RESULT_TOTAL_PALETTE,
    )
    write_4bpp_bmp(
        outputs["level_up_panel_bitmap"],
        256,
        256,
        _level_up_panel_pixels(),
        _level_up_bg_palette(),
    )
    title_frames: list[list[int]] = []
    for character_id in (1, 2, 3):
        for detail_page in (0, 1):
            title = _level_up_title_pixels(
                character_id, detail_page
            )
            for half in (0, 1):
                frame = [
                    title[row * LEVEL_UP_TITLE_WIDTH + half * 64 + column]
                    for row in range(LEVEL_UP_TITLE_HEIGHT)
                    for column in range(64)
                ]
                frame.extend(
                    [0] * (64 * (64 - LEVEL_UP_TITLE_HEIGHT))
                )
                title_frames.append(frame)
    level_up_sprite_palette = _level_up_sprite_palette()
    _write_8bpp_bmp(
        outputs["level_up_title_bitmap"],
        64,
        64 * len(title_frames),
        _level_up_shared_palette_pixels(
            [
                pixel
                for frame in title_frames
                for pixel in frame
            ],
            _level_up_bg_palette(),
        ),
        level_up_sprite_palette,
    )
    _write_8bpp_bmp(
        outputs["level_up_value_bitmap"],
        LEVEL_UP_VALUE_WIDTH,
        LEVEL_UP_VALUE_HEIGHT * 4,
        _level_up_shared_palette_pixels(
            [
                pixel
                for value in (0, 1, 14, 15)
                for pixel in _level_up_value_pixels(value)
            ],
            _level_up_bg_palette(),
        ),
        level_up_sprite_palette,
    )
    portrait_palette = _level_up_portrait_palette()
    for key, width, height, component_indexes in (
        ("level_up_portrait_64x64", 64, 64, (0,)),
        ("level_up_portrait_16x32", 16, 32, (1, 2)),
        ("level_up_portrait_32x16", 32, 16, (3, 4)),
        ("level_up_portrait_16x16", 16, 16, (5,)),
    ):
        _write_8bpp_bmp(
            outputs[f"{key}_bitmap"],
            width,
            height * 3 * len(component_indexes),
            _level_up_shared_palette_pixels(
                [
                    pixel
                    for character_id in (1, 2, 3)
                    for component_index in component_indexes
                    for pixel in _level_up_portrait_component_pixels(
                        character_id, component_index
                    )
                ],
                portrait_palette,
            ),
            level_up_sprite_palette,
        )
    _write_8bpp_bmp(
        outputs["level_up_eye_bitmap"],
        16,
        16,
        _level_up_shared_palette_pixels(
            _level_up_eye_pixels(),
            _level_up_eye_palette(),
        ),
        level_up_sprite_palette,
    )
    write_4bpp_bmp(
        outputs["training_panel_bitmap"],
        256,
        256,
        _training_panel_pixels(),
        _training_palette(),
    )
    for page in range(TRAINING_PAGE_COUNT):
        write_4bpp_bmp(
            outputs[f"training_text_{page}_bitmap"],
            256,
            256,
            _training_text_pixels(page),
            _training_palette(),
        )
    write_4bpp_bmp(
        outputs["preparation_dialog_panel_bitmap"],
        PREPARATION_DIALOG_PANEL_WIDTH,
        PREPARATION_DIALOG_PANEL_HEIGHT
        * PREPARATION_DIALOG_PANEL_FRAME_COUNT,
        _preparation_dialog_panel_pixels(),
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["range_tiles_bitmap"],
        RANGE_TILE_SIZE,
        RANGE_TILE_SIZE * RANGE_TILE_COUNT,
        _range_pixels(),
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["range_palette_bitmap"],
        8,
        8,
        [index % len(PALETTE) for index in range(64)],
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["preparation_background_bitmap"],
        PREPARATION_BACKGROUND_SIZE,
        PREPARATION_BACKGROUND_SIZE,
        _preparation_background_pixels(),
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["preparation_overview_background_bitmap"],
        PREPARATION_BACKGROUND_SIZE,
        PREPARATION_BACKGROUND_SIZE,
        _preparation_background_pixels(overview=True),
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["preparation_confirmation_background_bitmap"],
        PREPARATION_BACKGROUND_SIZE,
        PREPARATION_BACKGROUND_SIZE,
        _preparation_background_pixels(confirmation=True),
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["action_background_bitmap"],
        64,
        64 * 6,
        _action_background_pixels(),
        PALETTE,
    )
    write_4bpp_bmp(
        outputs["action_icon_bitmap"],
        ACTION_ICON_SIZE,
        ACTION_ICON_SIZE * ACTION_ICON_FRAME_COUNT,
        _action_icon_pixels(),
        ACTION_ICON_PALETTE,
    )
    write_4bpp_bmp(
        outputs["action_cursor_bitmap"],
        ACTION_CURSOR_WIDTH,
        ACTION_CURSOR_HEIGHT,
        _action_cursor_pixels(),
        _action_control_palette(),
    )
    write_4bpp_bmp(
        outputs["action_start_hint_bitmap"],
        ACTION_START_HINT_WIDTH,
        ACTION_START_HINT_HEIGHT,
        _action_start_hint_pixels(),
        _action_control_palette(),
    )
    write_4bpp_bmp(
        outputs["action_back_hint_bitmap"],
        ACTION_BACK_HINT_WIDTH,
        ACTION_BACK_HINT_HEIGHT,
        _action_back_hint_pixels(),
        _action_control_palette(),
    )
    write_4bpp_bmp(
        outputs["action_actor_stats_bitmap"],
        ACTION_ACTOR_STATS_WIDTH,
        ACTION_ACTOR_STATS_HEIGHT,
        _action_actor_stats_pixels(),
        PALETTE,
    )
    outputs["panel_metadata"].write_text(
        json.dumps(
            {"type": "sprite", "height": PANEL_HEIGHT},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["status_panel_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": STATUS_PANEL_HEIGHT,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["status_end_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": STATUS_END_SIZE,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["bar_metadata"].write_text(
        json.dumps(
            {"type": "sprite", "height": BAR_HEIGHT},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["dialog_panel_metadata"].write_text(
        json.dumps(
            {"type": "sprite", "height": DIALOG_PANEL_HEIGHT},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["large_dialog_panel_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": LARGE_DIALOG_PANEL_HEIGHT,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["message_panel_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": MESSAGE_PANEL_HEIGHT,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["dialogue_background_metadata"].write_text(
        json.dumps(
            {
                "type": "regular_bg",
                "bpp_mode": "bpp_8",
                "colors_count": 256,
                "compression": "auto_no_huffman",
                "active_size": [240, 160],
                "source": (
                    "original-s49-selector1-page1-gpu-"
                    "20260730-115"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["message_black_bar_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": MESSAGE_BLACK_BAR_HEIGHT,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for metadata in (
        outputs["dialogue_text_palette_metadata"],
        outputs["dialogue_speaker_palette_metadata"],
    ):
        metadata.write_text(
            json.dumps(
                {"type": "sprite_palette"},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    outputs["dialogue_speaker_label_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": DIALOGUE_SPEAKER_LABEL_HEIGHT,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["text_accent_palette_metadata"].write_text(
        json.dumps(
            {"type": "sprite_palette"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["text_warning_palette_metadata"].write_text(
        json.dumps(
            {"type": "sprite_palette"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["preparation_text_palette_metadata"].write_text(
        json.dumps(
            {"type": "sprite_palette"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["preparation_accent_palette_metadata"].write_text(
        json.dumps(
            {"type": "sprite_palette"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["preparation_menu_panel_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": PREPARATION_MENU_PANEL_SIZE,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["preparation_cursor_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": PREPARATION_CURSOR_SIZE,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["command_cursor_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": COMMAND_CURSOR_HEIGHT,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["confirmation_cursor_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": CONFIRMATION_CURSOR_HEIGHT,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["map_hint_palette_metadata"].write_text(
        json.dumps(
            {"type": "sprite_palette"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["result_background_metadata"].write_text(
        json.dumps(
            {"type": "regular_bg"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["result_panel_metadata"].write_text(
        json.dumps(
            {"type": "regular_bg"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "result_naruto",
        "result_sasuke",
        "result_sakura",
    ):
        outputs[f"{key}_metadata"].write_text(
            json.dumps(
                {"type": "sprite", "height": 64},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    outputs["result_total_palette_metadata"].write_text(
        json.dumps(
            {"type": "sprite_palette"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["level_up_panel_metadata"].write_text(
        json.dumps(
            {"type": "regular_bg"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for key, height in (
        ("level_up_title", 64),
        ("level_up_value", LEVEL_UP_VALUE_HEIGHT),
        ("level_up_eye", 16),
    ):
        outputs[f"{key}_metadata"].write_text(
            json.dumps(
                {
                    "type": "sprite",
                    "height": height,
                    "bpp_mode": "bpp_8",
                    "colors_count": 256,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    for key, height in (
        ("level_up_portrait_64x64", 64),
        ("level_up_portrait_16x32", 32),
        ("level_up_portrait_32x16", 16),
        ("level_up_portrait_16x16", 16),
    ):
        outputs[f"{key}_metadata"].write_text(
            json.dumps(
                {
                    "type": "sprite",
                    "height": height,
                    "bpp_mode": "bpp_8",
                    "colors_count": 256,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    for key in (
        "training_panel",
        *(f"training_text_{page}"
          for page in range(TRAINING_PAGE_COUNT)),
    ):
        outputs[f"{key}_metadata"].write_text(
            json.dumps(
                {"type": "regular_bg"},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    outputs["preparation_dialog_panel_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": PREPARATION_DIALOG_PANEL_HEIGHT,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["range_tiles_metadata"].write_text(
        json.dumps(
            {
                "type": "regular_bg_tiles",
                "bpp_mode": "bpp_4",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["range_palette_metadata"].write_text(
        json.dumps(
            {
                "type": "bg_palette",
                "bpp_mode": "bpp_4",
                "colors_count": 16,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["preparation_background_metadata"].write_text(
        json.dumps(
            {"type": "regular_bg"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["preparation_overview_background_metadata"].write_text(
        json.dumps(
            {"type": "regular_bg"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["preparation_confirmation_background_metadata"].write_text(
        json.dumps(
            {"type": "regular_bg"},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["action_background_metadata"].write_text(
        json.dumps(
            {"type": "sprite", "height": 64},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["action_icon_metadata"].write_text(
        json.dumps(
            {"type": "sprite", "height": ACTION_ICON_SIZE},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for metadata_key in (
        "action_cursor_metadata",
        "action_start_hint_metadata",
        "action_back_hint_metadata",
        "action_actor_stats_metadata",
    ):
        outputs[metadata_key].write_text(
            json.dumps(
                {"type": "sprite", "height": 16},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("butano-sequel/graphics"),
    )
    args = parser.parse_args()
    generate_outputs(args.output_directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
