#!/usr/bin/env python3
"""Extract character sprite sheets from table at 0x596D5C.

Dumps all 35 playable/NPC/enemy characters as PNG sprite sheets and previews.

Usage:
    python tools/extract_sprites.py [rom_path] [--out-dir build/sprites]
"""
from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

ROM_BASE = 0x08000000
TILE_TABLE_OFFSET = 0x596D5C
TILE_TABLE_ENTRY_SIZE = 16
TILE_TABLE_COUNT = 312

CHARACTER_NAMES = [
    ("漩涡鸣人", "Naruto Uzumaki"),
    ("宇智波佐助", "Sasuke Uchiha"),
    ("春野樱", "Sakura Haruno"),
    ("山中井野", "Ino Yamanaka"),
    ("奈良鹿丸", "Shikamaru Nara"),
    ("秋道丁次", "Choji Akimichi"),
    ("旗木卡卡西", "Kakashi Hatake"),
    ("犬冢牙与赤丸", "Kiba Inuzuka & Akamaru"),
    ("油女志乃", "Shino Aburame"),
    ("日向雏田", "Hinata Hyuga"),
    ("日向宁次", "Neji Hyuga"),
    ("李洛克", "Rock Lee"),
    ("天天", "Tenten"),
    ("我爱罗", "Gaara"),
    ("勘九郎", "Kankuro"),
    ("手鞠", "Temari"),
    ("音忍托斯", "Dosu Kinuta"),
    ("音忍萨克", "Zaku Abumi"),
    ("音忍琴", "Kin Tsuchi"),
    ("桃地再不斩", "Zabuza Momochi"),
    ("白", "Haku"),
    ("雨忍·影分身", "Rain Ninja A"),
    ("雨忍·刺客", "Rain Ninja B"),
    ("雨忍·头领", "Rain Ninja C"),
    ("鬼兄弟·业头", "Gozu (Demon Brother)"),
    ("鬼兄弟·冥头", "Meizu (Demon Brother)"),
    ("叛忍浪人", "Rogue Bandit"),
    ("敌方上忍头目", "Enemy Leader"),
    ("大蛇丸", "Orochimaru"),
    ("木叶丸", "Konohamaru"),
    ("手打 (一乐大叔)", "Teuchi (Ramen Guy)"),
    ("木叶暗部", "Leaf ANBU"),
    ("敌方潜伏密探", "Covert Scout"),
    ("伏击暗杀者", "Ambush Assassin"),
    ("傀儡·乌鸦", "Puppet Karasu"),
]


def parse_palette(rom: bytes, offset: int) -> list[tuple[int, int, int, int]]:
    colors = []
    for i in range(16):
        bgr = struct.unpack_from("<H", rom, offset + i * 2)[0]
        r = ((bgr & 0x1F) << 3) | ((bgr & 0x1F) >> 2)
        g = (((bgr >> 5) & 0x1F) << 3) | (((bgr >> 5) & 0x1F) >> 2)
        b = (((bgr >> 10) & 0x1F) << 3) | (((bgr >> 10) & 0x1F) >> 2)
        # color 0 is transparent in GBA sprites
        a = 0 if i == 0 else 255
        colors.append((r, g, b, a))
    return colors


def decode_tile(tile_bytes: bytes) -> list[list[int]]:
    rows = []
    for y in range(8):
        row = []
        for x_pair in range(4):
            b = tile_bytes[y * 4 + x_pair] if y * 4 + x_pair < len(tile_bytes) else 0
            row.extend([b & 0x0F, (b >> 4) & 0x0F])
        rows.append(row)
    return rows


def save_png(filename: Path | str, img_data: list[tuple[int, int, int, int]], width: int, height: int) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter None
        for x in range(width):
            raw.extend(img_data[y * width + x])
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(bytes(raw)))
    iend = chunk(b"IEND", b"")
    with open(filename, "wb") as f:
        f.write(header + ihdr + idat + iend)


def extract_character_sprites(rom_path: Path, out_dir: Path) -> None:
    rom = rom_path.read_bytes()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Scan 0x596D5C for unique sprite character groups
    groups = []
    seen_pals = set()
    for i in range(TILE_TABLE_COUNT):
        off = TILE_TABLE_OFFSET + i * TILE_TABLE_ENTRY_SIZE
        c0, c1, c2, c3 = struct.unpack_from("<IIII", rom, off)
        if c0 == 0 and c3 == 0:
            continue
        pal_off = c3 - ROM_BASE if ROM_BASE <= c3 < ROM_BASE + len(rom) else None
        gfx_off = c2 - ROM_BASE if ROM_BASE <= c2 < ROM_BASE + len(rom) else None
        c0_off = c0 - ROM_BASE if ROM_BASE <= c0 < ROM_BASE + len(rom) else None

        if pal_off and pal_off not in seen_pals:
            seen_pals.add(pal_off)
            groups.append((i, pal_off, gfx_off, c0_off))

    print(f"Discovered {len(groups)} character groups in descriptor table.")

    # 2. Extract each character
    all_standings = []
    for idx, (row, pal_off, gfx_off, c0_off) in enumerate(groups):
        zh_name, en_name = CHARACTER_NAMES[idx] if idx < len(CHARACTER_NAMES) else (f"角色{idx}", f"Char_{idx}")
        pal = parse_palette(rom, pal_off)

        # Parse sub-pointers from c0 (frames)
        sub_ptrs = []
        if c0_off is not None:
            for s_idx in range(16):
                val = struct.unpack_from("<I", rom, c0_off + s_idx * 4)[0]
                if not (ROM_BASE <= val < ROM_BASE + len(rom)):
                    break
                sub_ptrs.append(val - ROM_BASE)

        # Extract up to 4 animation frames (standing / walking loop)
        frames_to_extract = min(len(sub_ptrs), 4) if sub_ptrs else 1
        frame_w, frame_h = 32, 64  # Standard GBA sprite size for this game
        sheet_w = frame_w * max(frames_to_extract, 1)
        sheet_h = frame_h
        sheet = [(0, 0, 0, 0)] * (sheet_w * sheet_h)

        for f_idx in range(frames_to_extract):
            tile_offset = 0
            if f_idx < len(sub_ptrs):
                # read tile_offset from sub pointer structure
                tile_offset = struct.unpack_from("<I", rom, sub_ptrs[f_idx])[0]
            else:
                tile_offset = f_idx * 32

            # Render 4x8 tiles
            for ty in range(8):
                for tx in range(4):
                    t_num = tile_offset + ty * 4 + tx
                    t_byte_off = gfx_off + t_num * 32
                    if t_byte_off + 32 <= len(rom):
                        t_pixels = decode_tile(rom[t_byte_off : t_byte_off + 32])
                        for y in range(8):
                            for x in range(8):
                                px = f_idx * frame_w + tx * 8 + x
                                py = ty * 8 + y
                                sheet[py * sheet_w + px] = pal[t_pixels[y][x]]

        # Save individual character sprite sheet
        char_png = out_dir / f"char_{idx:02d}_{zh_name}.png"
        save_png(char_png, sheet, sheet_w, sheet_h)

        # Grab first frame for roster poster
        first_frame = [(0, 0, 0, 0)] * (frame_w * frame_h)
        for py in range(frame_h):
            for px in range(frame_w):
                first_frame[py * frame_w + px] = sheet[py * sheet_w + px]
        all_standings.append(first_frame)

        print(f"[{idx:02d}] {zh_name} ({en_name}): {frames_to_extract} frames -> {char_png.name}")

    # 3. Generate composite full roster poster
    roster_w = len(all_standings) * 32
    roster_h = 64
    roster_img = [(0, 0, 0, 0)] * (roster_w * roster_h)
    for c_idx, frame in enumerate(all_standings):
        for py in range(roster_h):
            for px in range(32):
                roster_img[py * roster_w + (c_idx * 32 + px)] = frame[py * 32 + px]

    roster_path = out_dir / "all_characters_roster.png"
    save_png(roster_path, roster_img, roster_w, roster_h)
    print(f"\nSaved master roster poster: {roster_path} ({roster_w}x{roster_h})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract character sprites from GBA ROM")
    parser.add_argument("rom", nargs="?", default="火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba", type=Path)
    parser.add_argument("--out-dir", default=Path("build/sprites"), type=Path)
    args = parser.parse_args()

    extract_character_sprites(args.rom, args.out_dir)


if __name__ == "__main__":
    main()
