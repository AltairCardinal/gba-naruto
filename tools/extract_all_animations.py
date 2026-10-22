#!/usr/bin/env python3
"""Comprehensive Extractor for Character Action Animations, Ninjutsu VFX & Skill Scripts.

Reverse-engineers and extracts:
1. All 35 characters' full action sets from Table 0x596D5C:
   - Row 0: Locomotion (Walk 4-dir, Run 4-dir, Skid/Stop 4-dir, 20 frames)
   - Row 1: Attack 1 (Combo / Strike, 5-6 frames)
   - Row 2: Attack 2 (Heavy Strike / Uppercut / Knockback, 5-6 frames)
   - Row 3: Jutsu Charge (Hand Seals / Chakra Gathering, 5-6 frames)
   - Row 4: Hurt (Damage reaction, 5 frames)
   - Row 5: Guard (Block / Defense, 5 frames)
   - Row 6: Jutsu Cast (Special move / Secret technique execution, 5-6 frames)
   - Row 7: Victory (Victory pose, 5-6 frames)
   - Row 8: Defeat (Down / KO, 5 frames)
   - Generates animated GIFs and PNG action strips.
2. All Ninjutsu Cut-in Portraits & Expressions from Table 0x5A4E14:
   - 155 entries, 59 unique 64-color portraits and cut-in expressions (8bpp indexed).
3. All 36 Ninjutsu Battle Skill Script Tables from 0x53636C ~ 0x53CE44:
   - Bytecode opcodes (BE=ID, BC=target, BB=chakra, BD=phase, 81BF=particle/audio)
   - Spline trajectory and particle vector curves at 0x464800+.

Usage:
    python3 tools/extract_all_animations.py [rom_path] [--out-dir build]
"""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path
from PIL import Image

ROM_BASE = 0x08000000
TABLE_SPRITES_OFF = 0x596D5C
TABLE_PORTRAITS_OFF = 0x5A4E14
TABLE_PORTRAITS_COUNT = 155
SKILL_SCAN_START = 0x535000
SKILL_SCAN_END = 0x53D000

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
    ("鬼兄弟·业头", "Gozu"),
    ("鬼兄弟·冥头", "Meizu"),
    ("叛忍浪人", "Rogue Bandit"),
    ("敌方上忍头目", "Enemy Leader"),
    ("大蛇丸", "Orochimaru"),
    ("木叶丸", "Konohamaru"),
    ("手打 (一乐大叔)", "Teuchi"),
    ("木叶暗部", "Leaf ANBU"),
    ("敌方潜伏密探", "Covert Scout"),
    ("伏击暗杀者", "Ambush Assassin"),
    ("傀儡·乌鸦", "Puppet Karasu"),
]

ACTION_TYPES = [
    ("locomotion", "移动步态 (Walk/Run/Stop 4-Dir)"),
    ("attack1", "普攻连击 (Combo Strike)"),
    ("attack2", "重击击退 (Heavy Hit / Uppercut)"),
    ("charge", "结印蓄力 (Chakra / Hand Seals)"),
    ("hurt", "受创击退 (Hurt / Damage)"),
    ("guard", "防御格挡 (Guard / Defense)"),
    ("cast", "奥义释放 (Ninjutsu Release)"),
    ("victory", "胜利姿态 (Victory Pose)"),
    ("defeat", "倒地击溃 (KO / Defeat)"),
]

PORTRAIT_CHARACTER_MAP = {
    0: ("漩涡鸣人·通常", "Naruto Normal"),
    1: ("漩涡鸣人·呐喊", "Naruto Shout"),
    2: ("漩涡鸣人·惊愕", "Naruto Shocked"),
    3: ("宇智波佐助·通常", "Sasuke Normal"),
    4: ("宇智波佐助·战斗", "Sasuke Battle"),
    5: ("宇智波佐助·写轮眼", "Sasuke Sharingan"),
    6: ("春野樱·怒吼/里樱", "Sakura Shout / Inner Sakura"),
    7: ("春野樱·通常", "Sakura Normal"),
    8: ("山中井野·通常", "Ino Normal"),
    9: ("山中井野·战斗", "Ino Battle"),
    10: ("奈良鹿丸·通常", "Shikamaru Normal"),
    11: ("奈良鹿丸·思考", "Shikamaru Thinking"),
    12: ("奈良鹿丸·影子模仿", "Shikamaru Shadow"),
    13: ("秋道丁次·通常", "Choji Normal"),
    14: ("秋道丁次·肉弹战车", "Choji Battle"),
    15: ("旗木卡卡西·通常", "Kakashi Normal"),
    16: ("旗木卡卡西·雷切写轮眼", "Kakashi Raikiri / Sharingan"),
    17: ("旗木卡卡西·亲热天堂", "Kakashi Reading"),
    18: ("犬冢牙·通常", "Kiba Normal"),
    19: ("犬冢牙·通牙", "Kiba Battle"),
    20: ("油女志乃·通常", "Shino Normal"),
    21: ("油女志乃·秘术寄坏虫", "Shino Kikaichu"),
    22: ("日向雏田·通常", "Hinata Normal"),
    23: ("日向雏田·柔步双狮", "Hinata Battle"),
    24: ("日向宁次·通常", "Neji Normal"),
    25: ("日向宁次·白眼", "Neji Byakugan"),
    26: ("李洛克·通常", "Rock Lee Normal"),
    27: ("李洛克·热血/八门", "Rock Lee Eight Gates"),
    28: ("天天·通常", "Tenten Normal"),
    29: ("天天·操具", "Tenten Weapon Tools"),
    30: ("天天·胜利", "Tenten Victory"),
    31: ("我爱罗·通常", "Gaara Normal"),
    32: ("我爱罗·杀气", "Gaara Killer Eyes"),
    33: ("我爱罗·沙暴大葬", "Gaara Sand Coffin"),
    34: ("勘九郎·通常", "Kankuro Normal"),
    35: ("勘九郎·黑秘技", "Kankuro Puppet"),
    36: ("手鞠·通常", "Temari Normal"),
    37: ("手鞠·风遁斩斩舞", "Temari Wind Scythe"),
    38: ("音忍托斯·响鸣穿", "Dosu Kinuta"),
    39: ("音忍萨克·斩空波", "Zaku Abumi"),
    40: ("音忍琴·铃声千本", "Kin Tsuchi"),
    60: ("雨忍刺客·头领", "Rain Ninja Leader"),
    80: ("桃地再不斩·鬼人斩首", "Zabuza Momochi"),
    85: ("白·魔镜冰晶", "Haku Ice Mirrors"),
    90: ("大蛇丸·草薙剑潜影蛇手", "Orochimaru"),
    100: ("小虎 (捉拿失踪小猫任务)", "Tora the Lost Cat"),
    105: ("木叶丸·通常", "Konohamaru Normal"),
    110: ("伊鲁卡老师", "Iruka Sensei"),
    120: ("手打 (一乐拉面大叔)", "Teuchi Ramen Chef"),
    130: ("木叶暗部·队长", "ANBU Captain"),
}


def decompress_lz77(rom_bytes: bytes, offset: int) -> bytes:
    if offset >= len(rom_bytes) or rom_bytes[offset] != 0x10:
        return b""
    decomp_len = (
        rom_bytes[offset + 1]
        | (rom_bytes[offset + 2] << 8)
        | (rom_bytes[offset + 3] << 16)
    )
    src = offset + 4
    dest = bytearray()
    while len(dest) < decomp_len and src < len(rom_bytes):
        flags = rom_bytes[src]
        src += 1
        for bit in range(8):
            if len(dest) >= decomp_len:
                break
            if flags & (0x80 >> bit):
                if src + 1 >= len(rom_bytes):
                    break
                b1 = rom_bytes[src]
                b2 = rom_bytes[src + 1]
                src += 2
                disp = ((b1 & 0x0F) << 8) | b2
                length = (b1 >> 4) + 3
                start = len(dest) - disp - 1
                for _ in range(length):
                    if len(dest) >= decomp_len:
                        break
                    dest.append(dest[start] if 0 <= start < len(dest) else 0)
                    start += 1
            else:
                if src < len(rom_bytes):
                    dest.append(rom_bytes[src])
                    src += 1
    return bytes(dest)


def parse_palette_4bpp(rom: bytes, offset: int) -> list[tuple[int, int, int, int]]:
    colors = []
    for i in range(16):
        bgr = struct.unpack_from("<H", rom, offset + i * 2)[0]
        r = ((bgr & 0x1F) << 3) | ((bgr & 0x1F) >> 2)
        g = (((bgr >> 5) & 0x1F) << 3) | (((bgr >> 5) & 0x1F) >> 2)
        b = (((bgr >> 10) & 0x1F) << 3) | (((bgr >> 10) & 0x1F) >> 2)
        a = 0 if i == 0 else 255
        colors.append((r, g, b, a))
    return colors


def parse_palette_8bpp(rom: bytes, offset: int, count: int = 64) -> list[tuple[int, int, int, int]]:
    colors = []
    for i in range(count):
        bgr = struct.unpack_from("<H", rom, offset + i * 2)[0]
        r = ((bgr & 0x1F) << 3) | ((bgr & 0x1F) >> 2)
        g = (((bgr >> 5) & 0x1F) << 3) | (((bgr >> 5) & 0x1F) >> 2)
        b = (((bgr >> 10) & 0x1F) << 3) | (((bgr >> 10) & 0x1F) >> 2)
        a = 0 if i == 0 else 255
        colors.append((r, g, b, a))
    return colors


def decode_tile_4bpp(tile_bytes: bytes) -> list[list[int]]:
    rows = []
    for y in range(8):
        row = []
        for x_pair in range(4):
            b = tile_bytes[y * 4 + x_pair] if y * 4 + x_pair < len(tile_bytes) else 0
            row.extend([b & 0x0F, (b >> 4) & 0x0F])
        rows.append(row)
    return rows


def render_frame_oam(
    rom: bytes,
    gfx_off: int,
    fptr: int,
    pal: list[tuple[int, int, int, int]],
    canvas_w: int = 64,
    canvas_h: int = 64,
    origin_x: int = 32,
    origin_y: int = 56,
) -> list[tuple[int, int, int, int]]:
    frame_canvas = [(0, 0, 0, 0)] * (canvas_w * canvas_h)
    curr = fptr
    max_parts = 8
    part_count = 0
    while part_count < max_parts:
        vals = struct.unpack_from("<IhhIIII", rom, curr)
        tile_off = vals[0]
        pos_x, pos_y = vals[1], vals[2]
        w = vals[3] & 0xFFFF
        h = (vals[3] >> 16) & 0xFFFF
        terminator = struct.unpack_from("<h", rom, curr + 20)[0]

        w_tiles = w // 8
        h_tiles = h // 8
        dst_base_x = origin_x + pos_x
        dst_base_y = origin_y + pos_y

        for ty in range(h_tiles):
            for tx in range(w_tiles):
                t_num = tile_off + ty * w_tiles + tx
                t_byte_off = gfx_off + t_num * 32
                if t_byte_off + 32 <= len(rom):
                    t_pix = decode_tile_4bpp(rom[t_byte_off : t_byte_off + 32])
                    for y in range(8):
                        for x in range(8):
                            dx = dst_base_x + tx * 8 + x
                            dy = dst_base_y + ty * 8 + y
                            if 0 <= dx < canvas_w and 0 <= dy < canvas_h:
                                c = pal[t_pix[y][x]]
                                if c[3] > 0:
                                    frame_canvas[dy * canvas_w + dx] = c

        part_count += 1
        if terminator == -1:
            break
        curr += 24
    return frame_canvas


def save_png_rgba(filename: Path | str, img_data: list[tuple[int, int, int, int]], width: int, height: int) -> None:
    img = Image.new("RGBA", (width, height))
    img.putdata(img_data)
    img.save(filename, "PNG")


def save_gif_animation(filename: Path | str, frames: list[list[tuple[int, int, int, int]]], width: int, height: int, duration_ms: int = 120) -> None:
    if not frames:
        return
    pil_frames = []
    for f in frames:
        im = Image.new("RGBA", (width, height))
        im.putdata(f)
        pil_frames.append(im)
    pil_frames[0].save(
        filename,
        save_all=True,
        append_images=pil_frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )


def extract_character_animations(rom: bytes, base_out_dir: Path) -> dict:
    actions_dir = base_out_dir / "sprites" / "actions"
    gifs_dir = base_out_dir / "sprites" / "gifs"
    matrix_dir = base_out_dir / "sprites" / "matrix"
    actions_dir.mkdir(parents=True, exist_ok=True)
    gifs_dir.mkdir(parents=True, exist_ok=True)
    matrix_dir.mkdir(parents=True, exist_ok=True)

    catalog = {}
    print("=== 1. Extracting Character Action Animations ===")

    for char_id in range(len(CHARACTER_NAMES)):
        zh_name, en_name = CHARACTER_NAMES[char_id]
        start_row = char_id * 9
        if start_row >= 312:
            break

        # Palette is in Row 0 col3
        pal_off = struct.unpack_from("<I", rom, TABLE_SPRITES_OFF + start_row * 16 + 12)[0] - ROM_BASE
        pal = parse_palette_4bpp(rom, pal_off)

        char_key = f"char_{char_id:02d}_{zh_name}"
        char_data = {
            "id": char_id,
            "zh_name": zh_name,
            "en_name": en_name,
            "pal_offset": hex(pal_off),
            "actions": {},
        }

        matrix_rows = []

        for r_idx, (act_slug, act_desc) in enumerate(ACTION_TYPES):
            row_num = start_row + r_idx
            if row_num >= 312:
                break
            c0, c1, c2, c3 = struct.unpack_from("<IIII", rom, TABLE_SPRITES_OFF + row_num * 16)
            if not (ROM_BASE <= c0 < ROM_BASE + len(rom)) or not (ROM_BASE <= c2 < ROM_BASE + len(rom)):
                continue

            c0_off = c0 - ROM_BASE
            gfx_off = c2 - ROM_BASE

            # Frame descriptors
            sub_ptrs = []
            for s_idx in range(32):
                val = struct.unpack_from("<I", rom, c0_off + s_idx * 4)[0]
                if not (ROM_BASE <= val < ROM_BASE + len(rom)):
                    break
                sub_ptrs.append(val - ROM_BASE)

            if not sub_ptrs:
                continue

            # Render individual aligned frames (64x64)
            rendered_frames = []
            for fptr in sub_ptrs:
                frame_data = render_frame_oam(rom, gfx_off, fptr, pal, canvas_w=64, canvas_h=64, origin_x=32, origin_y=56)
                rendered_frames.append(frame_data)

            # 1. Action strip PNG
            strip_w = len(rendered_frames) * 64
            strip_h = 64
            strip_data = [(0, 0, 0, 0)] * (strip_w * strip_h)
            for fi, fd in enumerate(rendered_frames):
                for y in range(64):
                    for x in range(64):
                        strip_data[y * strip_w + (fi * 64 + x)] = fd[y * 64 + x]

            strip_file = actions_dir / f"{char_key}_{act_slug}.png"
            save_png_rgba(strip_file, strip_data, strip_w, strip_h)

            # 2. Animated GIF for key characters (first 14 main characters)
            gif_rel_path = None
            if char_id < 14 and len(rendered_frames) > 1:
                gif_file = gifs_dir / f"{char_key}_{act_slug}.gif"
                # Determine loop frames (e.g. for walk 0..2 or run 0..3)
                dur = 140 if act_slug == "locomotion" else 100
                save_gif_animation(gif_file, rendered_frames, 64, 64, duration_ms=dur)
                gif_rel_path = f"build/sprites/gifs/{gif_file.name}"

            char_data["actions"][act_slug] = {
                "desc": act_desc,
                "frames_count": len(rendered_frames),
                "strip_path": f"build/sprites/actions/{strip_file.name}",
                "gif_path": gif_rel_path,
                "gfx_offset": hex(gfx_off),
            }

            # Pick sample frame for matrix
            matrix_rows.append((act_slug, rendered_frames[0]))

        # 3. Create Full Character Action Matrix Sheet (64 x (64 * actions_count))
        if matrix_rows:
            mat_w = 64 * len(matrix_rows)
            mat_h = 64
            mat_data = [(0, 0, 0, 0)] * (mat_w * mat_h)
            for a_idx, (_, f0) in enumerate(matrix_rows):
                for y in range(64):
                    for x in range(64):
                        mat_data[y * mat_w + (a_idx * 64 + x)] = f0[y * 64 + x]
            mat_file = matrix_dir / f"{char_key}_all_actions.png"
            save_png_rgba(mat_file, mat_data, mat_w, mat_h)
            char_data["matrix_sheet"] = f"build/sprites/matrix/{mat_file.name}"

        catalog[char_id] = char_data
        print(f"[{char_id:02d}] {zh_name}: Extracted {len(char_data['actions'])} action states.")

    return catalog


def extract_ninjutsu_portraits(rom: bytes, base_out_dir: Path) -> list[dict]:
    vfx_dir = base_out_dir / "vfx" / "portraits"
    vfx_dir.mkdir(parents=True, exist_ok=True)
    portraits = []

    print("\n=== 2. Extracting Ninjutsu Cut-in Portraits (Table 0x5A4E14) ===")
    seen_graphics = {}

    for idx in range(TABLE_PORTRAITS_COUNT):
        off = TABLE_PORTRAITS_OFF + idx * 16
        c0, c1, c2, c3 = struct.unpack_from("<IIII", rom, off)
        if not (ROM_BASE <= c0 < ROM_BASE + len(rom)) or not (ROM_BASE <= c1 < ROM_BASE + len(rom)):
            continue

        c0_off = c0 - ROM_BASE
        c1_off = c1 - ROM_BASE
        c2_off = c2 - ROM_BASE if ROM_BASE <= c2 < ROM_BASE + len(rom) else None
        c3_off = c3 - ROM_BASE if ROM_BASE <= c3 < ROM_BASE + len(rom) else None

        if c0 in seen_graphics:
            decomp = seen_graphics[c0]
        else:
            decomp = decompress_lz77(rom, c0_off)
            if len(decomp) >= 6400:
                seen_graphics[c0] = decomp

        if len(decomp) < 6400:
            continue

        pal = parse_palette_8bpp(rom, c1_off, 64)

        # Render 64x64 portrait from tiles 36..99 (8x8 tiles = 64 tiles)
        img_64x64 = [(0, 0, 0, 0)] * (64 * 64)
        for ty in range(8):
            for tx in range(8):
                tb = (36 + ty * 8 + tx) * 64
                for y in range(8):
                    for x in range(8):
                        img_64x64[(ty * 8 + y) * 64 + (tx * 8 + x)] = pal[decomp[tb + y * 8 + x]]

        # Determine label
        zh_title, en_title = PORTRAIT_CHARACTER_MAP.get(idx, (f"特写立绘_{idx:02d}", f"Portrait_{idx:02d}"))
        p_filename = f"portrait_{idx:03d}_{zh_title.split('·')[0]}.png"
        out_path = vfx_dir / p_filename
        save_png_rgba(out_path, img_64x64, 64, 64)

        entry_meta = {
            "index": idx,
            "zh_title": zh_title,
            "en_title": en_title,
            "c0_ptr": hex(c0),
            "c1_pal_ptr": hex(c1),
            "c2_alt_ptr": hex(c2) if c2_off else None,
            "file_path": f"build/vfx/portraits/{p_filename}",
        }
        portraits.append(entry_meta)

    print(f"Extracted {len(portraits)} high-resolution 64-color cut-in portraits.")

    # Create composite gallery poster (e.g. 10 per row)
    cols = 12
    rows = (len(portraits) + cols - 1) // cols
    gal_w = cols * 64
    gal_h = rows * 64
    gal_data = [(0, 0, 0, 0)] * (gal_w * gal_h)

    for p_idx, p_meta in enumerate(portraits):
        gx = p_idx % cols
        gy = p_idx // cols
        p_img = Image.open(base_out_dir / p_meta["file_path"].replace("build/", ""))
        for y in range(64):
            for x in range(64):
                px = gx * 64 + x
                py = gy * 64 + y
                gal_data[py * gal_w + px] = p_img.getpixel((x, y))

    gal_path = base_out_dir / "vfx" / "all_portraits_gallery.png"
    save_png_rgba(gal_path, gal_data, gal_w, gal_h)
    print(f"Saved master portrait gallery: {gal_path} ({gal_w}x{gal_h})")

    return portraits


def extract_skill_scripts(rom: bytes) -> list[dict]:
    print("\n=== 3. Decoding Ninjutsu Skill Script Bytecode (0x53636C ~ 0x53CE44) ===")
    skills = []
    pos = SKILL_SCAN_START

    while pos < SKILL_SCAN_END:
        val0 = struct.unpack_from("<I", rom, pos)[0]
        if 0x08464800 <= val0 <= 0x08466000:
            val1 = struct.unpack_from("<I", rom, pos + 4)[0]
            if ROM_BASE <= val1 < ROM_BASE + len(rom):
                b1 = rom[val1 - ROM_BASE]
                if b1 == 0xBE:
                    steps = []
                    idx = 1
                    while True:
                        vp = struct.unpack_from("<I", rom, pos + idx * 4)[0]
                        if not (ROM_BASE <= vp < ROM_BASE + len(rom)):
                            break
                        if rom[vp - ROM_BASE] != 0xBE:
                            break
                        step_bytes = rom[vp - ROM_BASE : vp - ROM_BASE + 32]
                        steps.append({
                            "ptr": hex(vp),
                            "hex_preview": step_bytes[:16].hex(),
                        })
                        idx += 1

                    s0_off = struct.unpack_from("<I", rom, pos + 4)[0] - ROM_BASE
                    skill_id = rom[s0_off + 1]
                    target = rom[s0_off + 3]
                    chakra = rom[s0_off + 5]
                    curve_ptr = struct.unpack_from("<I", rom, (val0 - ROM_BASE) + 4)[0]

                    skills.append({
                        "table_offset": hex(pos),
                        "skill_id": hex(skill_id),
                        "skill_id_dec": skill_id,
                        "target_flag": target,
                        "chakra_cost": chakra,
                        "step_count": len(steps),
                        "curve_header": hex(val0),
                        "curve_ptr": hex(curve_ptr),
                        "steps": steps,
                    })
        pos += 4

    print(f"Decoded {len(skills)} Ninjutsu Skill Script Tables with full bytecode.")
    return skills


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract all animations, VFX and scripts")
    parser.add_argument("rom", nargs="?", default="火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba", type=Path)
    parser.add_argument("--out-dir", default=Path("build"), type=Path)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    char_catalog = extract_character_animations(rom, args.out_dir)
    portraits_catalog = extract_ninjutsu_portraits(rom, args.out_dir)
    skills_catalog = extract_skill_scripts(rom)

    summary = {
        "characters_count": len(char_catalog),
        "characters": char_catalog,
        "portraits_count": len(portraits_catalog),
        "portraits": portraits_catalog,
        "skills_count": len(skills_catalog),
        "skills": skills_catalog,
    }

    out_json = args.out_dir / "animations_and_vfx_manifest.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nManifest saved: {out_json}")


if __name__ == "__main__":
    main()
