#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.lib import load_json
from tools import text_codec


def find_free_space(data: bytes, size: int, start: int = 0) -> int:
    """Find a zero-filled region of at least `size` bytes."""
    needed = size
    run_start = -1
    for i in range(start, len(data)):
        if data[i] == 0:
            if run_start < 0:
                run_start = i
            if i - run_start + 1 >= needed:
                return run_start
        else:
            run_start = -1
    raise ValueError(f"no free space of {size} bytes found after offset 0x{start:X}")


def build_pointer_redirect(
    table_offset: int, old_text_offset: int, new_text_offset: int
) -> dict:
    """Build a pointer_redirect patch for a dialogue pointer table entry."""
    old_ptr = ROM_BASE + old_text_offset
    new_ptr = ROM_BASE + new_text_offset
    return {
        "type": "pointer_redirect",
        "pointer_table_offset": table_offset,
        "expected_pointer_hex": struct.pack("<I", old_ptr).hex(),
        "new_pointer_hex": struct.pack("<I", new_ptr).hex(),
    }


ROM_BASE = 0x08000000
FREE_SPACE_START = 0x5DFBEC  # first 0xFF-filled byte after all game data (128 KB free)
FREE_SPACE_END   = 0x5FFFFF  # last byte of ROM


def find_ff_run(data: bytes, size: int, start: int, limit: int) -> int:
    """Find an **4-byte aligned** offset inside a 0xFF run of at least `size` bytes.

    为什么必须扫 0xFF 而不是「从 FREE_SPACE_START 顺序往后写」：

    编辑器（`rom-editor/js/rom.js::allocate`）也往这一段空闲区里写东西 ——
    变长的文本表正文、**搬迁过去的剧情剧本**。两个分配器**互不知情**，
    顺序写的那一个会直接踩到另一个已经写进去的内容。

    改成**两边都只写 0xFF 区**之后，冲突在结构上消失：
    谁先写谁把那段变成非 0xFF，另一个自动避开它。
    （前提是后跑的那个跑在前一个的**输出**上 —— 这是正常的串行流程。）

    `size` 是**对齐之后**仍然需要的字节数。
    """
    n = min(len(data), limit)
    i = max(0, start)
    while i < n:
        if data[i] == 0xFF:
            j = i
            while j < n and data[j] == 0xFF:
                j += 1
            aligned = (i + 3) & ~3
            if j - aligned >= size:
                return aligned
            i = j
        else:
            i += 1
    raise ValueError(
        f"no 0xFF run of {size} bytes found in [0x{start:X}, 0x{limit:X}]"
    )


def load_rom_bytes(rom_path: Path | None) -> bytes:
    """The ROM the free-space scan has to look at."""
    if rom_path is not None:
        path = Path(rom_path)
        if not path.is_absolute():
            path = ROOT / path
        if path.exists():
            return path.read_bytes()
    from tools import text_codec

    return text_codec.resolve_rom(None).read_bytes()


def import_dialogue_variable(
    bank_path: Path,
    content_path: Path,
    free_space_start: int = FREE_SPACE_START,
    rom_path: Path | None = None,
) -> list[dict]:
    """Generate patches for variable-length dialogue entries.

    For each dialogue content entry:
    1. Encode text in the target encoding ("font" = the game's own font codes)
    2. If length matches existing slot, generate a bytes patch (in-place)
    3. If length differs, generate:
       - a bytes patch to write new text into free space
       - a pointer_redirect patch to update the pointer table

    空闲区的落点**扫 0xFF 段**（`find_ff_run`）—— 见那里的说明：
    编辑器也往这一段写，两边都只写 0xFF ⇒ 互不踩踏。
    """
    bank = load_json(bank_path)
    content = load_json(content_path)
    bank_map = {entry["id"]: entry for entry in bank["entries"]}

    patches = []
    text_cursor = free_space_start
    mapping: dict[int, str] | None = None
    rom_bytes = b""

    for entry in content["entries"]:
        entry_id = entry["id"]
        if entry_id not in bank_map:
            raise ValueError(f"dialogue entry {entry_id} missing from bank")

        bank_entry = bank_map[entry_id]
        encoding = bank_entry.get("encoding", text_codec.FONT_ENCODING)
        if encoding == text_codec.FONT_ENCODING and mapping is None:
            mapping, _ = text_codec.load_mapping(rom_path)
        text = entry["text"]
        encoded = text_codec.encode(text, encoding, mapping)
        max_bytes = int(bank_entry["max_bytes"])

        text_offset = int(bank_entry["offset"])
        table_offset = int(bank_entry.get("table_offset", 0))
        old_text_offset = int(bank_entry.get("text_rom_offset", text_offset))

        if len(encoded) <= max_bytes:
            # Same-length or shorter: patch in place
            # Pad with null if shorter
            padded = encoded + b"\x00" * (max_bytes - len(encoded))
            patches.append(
                {
                    "id": f"dialogue.{entry_id}",
                    "type": "bytes",
                    "offset": text_offset,
                    "before_hex": bank_entry["expected_hex"],
                    "after_hex": padded.hex(),
                    "encoding": encoding,
                    "text": text,
                    "max_bytes": max_bytes,
                    "source_entry": entry_id,
                    "method": "in_place",
                }
            )
        else:
            # Longer than existing slot: write to free space + redirect pointer
            if not table_offset:
                raise ValueError(
                    f"dialogue entry {entry_id} needs variable-length import "
                    f"but has no table_offset in bank"
                )

            after_bytes = encoded + b"\x00"

            # 落点：扫 0xFF 段（4 字节对齐），**跳过别人已经写进去的东西**。
            if not rom_bytes:
                rom_bytes = load_rom_bytes(rom_path)
            text_cursor = find_ff_run(
                rom_bytes, len(after_bytes), text_cursor, FREE_SPACE_END + 1
            )
            # 落点自己占掉的那几个字节不再是 0xFF 了 —— 后面的条目要避开它。
            rom_bytes = (
                rom_bytes[:text_cursor]
                + b"\x00" * len(after_bytes)
                + rom_bytes[text_cursor + len(after_bytes):]
            )

            patches.append(
                {
                    "id": f"dialogue.{entry_id}.write_text",
                    "type": "bytes",
                    "offset": text_cursor,
                    "before_hex": "ff" * len(after_bytes),  # free space is 0xFF-filled
                    "after_hex": after_bytes.hex(),
                    "encoding": encoding,
                    "text": text,
                    "source_entry": entry_id,
                    "method": "free_space_write",
                }
            )

            old_ptr = ROM_BASE + old_text_offset
            new_ptr = ROM_BASE + text_cursor
            patches.append(
                {
                    "id": f"dialogue.{entry_id}.redirect_ptr",
                    "type": "pointer_redirect",
                    "pointer_table_offset": table_offset,
                    "expected_pointer_hex": struct.pack("<I", old_ptr).hex(),
                    "new_pointer_hex": struct.pack("<I", new_ptr).hex(),
                    "source_entry": entry_id,
                }
            )

            text_cursor += len(after_bytes)  # 这一段已经不是 0xFF 了

    return patches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert high-level dialogue content into ROM patch entries (supports variable length)."
    )
    parser.add_argument("--bank", default="sequel/content/text/dialogue-bank.json")
    parser.add_argument(
        "--content", default="sequel/content/text/dialogue-patches.json"
    )
    parser.add_argument(
        "--free-space-start",
        default=hex(FREE_SPACE_START),
        help="Start offset for free space in ROM (hex)",
    )
    parser.add_argument("--output", help="Optional output JSON path")
    parser.add_argument(
        "--rom",
        default=None,
        help="ROM used for the font code table (default rom/base.gba)",
    )
    args = parser.parse_args()

    free_start = int(args.free_space_start, 0)
    patches = import_dialogue_variable(
        ROOT / args.bank, ROOT / args.content, free_start, args.rom
    )
    text = json.dumps({"patches": patches}, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        from tools.lib.io import write_text as write_text_lf
        write_text_lf(ROOT / args.output, text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
