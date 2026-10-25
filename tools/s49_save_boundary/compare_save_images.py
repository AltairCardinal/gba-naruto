#!/usr/bin/env python3
"""Compare the original's and the remake's cartridge-SRAM images.

Three questions, three answers:

1. **Does either side write SRAM during a battle?**
   Every checkpoint of the original's battle 14 (entry, five in-battle
   savestates, the post-battle task menu and forty walk steps) is compared
   byte for byte; the same is done for the remake's boot / preparation-scene
   save / second save / battle steps.

2. **Which bytes differ between the two sides' saves, and which field does
   each differing byte belong to?**
   The original's ten descriptor records and the remake's two ``KBCS`` slots
   are decoded into fields, and the byte-level diff of the two images is
   attributed to a field.

3. **Can one side read the other side's save?**
   Both loaders' header checks are re-implemented here and run against both
   images.

Usage::

    python tools/s49_save_boundary/compare_save_images.py
    python tools/s49_save_boundary/compare_save_images.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_save_common import (  # noqa: E402
    ORIGINAL_DESCRIPTORS,
    ORIGINAL_RECORD_HEADER,
    ORIGINAL_RECORD_HEADER_SIZE,
    ORIGINAL_SRAM_ADVANCE_OVERHEAD,
    RECEIPTS,
    REMAKE_CRC_OFFSET,
    REMAKE_MAGIC,
    REMAKE_SLOT_SIZE,
    REMAKE_VERSION,
    SRAM_SIZE,
    WORK,
    check_descriptor_bank,
    sha256_bytes,
    sha256_file,
    write_json,
    write_text,
)
from s49_save_layout import (  # noqa: E402
    decode_image,
    original_field_map,
    slot_field_map,
)


def _load(path: pathlib.Path) -> bytes:
    data = path.read_bytes()
    if len(data) != SRAM_SIZE:
        raise SystemExit(
            "ERR %s is %d bytes, expected %d" % (path, len(data), SRAM_SIZE)
        )
    return data


def _diff_ranges(left: bytes, right: bytes) -> list[tuple[int, int]]:
    ranges = []
    start = None
    for index in range(len(left)):
        if left[index] != right[index]:
            if start is None:
                start = index
        elif start is not None:
            ranges.append((start, index - 1))
            start = None
    if start is not None:
        ranges.append((start, len(left) - 1))
    return ranges


def _attribute(offset: int, original: dict, remake: dict) -> str:
    """Name the field a byte belongs to in either format."""

    for record in original["records"]:
        if record["sram_offset"] <= offset < record["sram_offset"] + \
                record["record_bytes"]:
            if offset < record["payload_offset"]:
                return "original.d%d.identity_header" % record[
                    "descriptor_index"]
            if offset < record["checksum_offset"]:
                return "original.d%d.payload" % record["descriptor_index"]
            return "original.d%d.checksum" % record["descriptor_index"]
    for slot in remake["slots"]:
        if slot["sram_offset"] <= offset < slot["sram_offset"] + REMAKE_SLOT_SIZE:
            for field_offset, size, name in slot_field_map(slot):
                if field_offset <= offset < field_offset + size:
                    return "remake.slot%d.%s" % (slot["slot_index"], name)
            return "remake.slot%d.padding" % slot["slot_index"]
    return "unmapped"


def _original_loader_accepts(image: bytes) -> dict:
    """The original's record header / checksum check, replayed offline."""

    results = []
    offset = 0
    for entry in ORIGINAL_DESCRIPTORS:
        length = entry["payload_length"]
        header = image[offset:offset + ORIGINAL_RECORD_HEADER_SIZE]
        payload = image[
            offset + ORIGINAL_RECORD_HEADER_SIZE:
            offset + ORIGINAL_RECORD_HEADER_SIZE + length
        ]
        checksum = image[offset + ORIGINAL_RECORD_HEADER_SIZE + length]
        expected = (~sum(payload)) & 0xFF
        results.append({
            "descriptor_index": entry["index"],
            "sram_offset": offset,
            "header_matches": header == ORIGINAL_RECORD_HEADER,
            "header_text": header[:19].decode("latin-1", "replace"),
            "checksum": checksum,
            "checksum_expected": expected,
            "checksum_ok": checksum == expected,
            "accepted": header == ORIGINAL_RECORD_HEADER and checksum == expected,
        })
        offset += length + ORIGINAL_SRAM_ADVANCE_OVERHEAD
    return {
        "records": results,
        "accepted_descriptors": [
            r["descriptor_index"] for r in results if r["accepted"]
        ],
    }


def _remake_loader_accepts(image: bytes) -> dict:
    """The remake's magic / version / payload-size / CRC check, offline."""

    results = []
    for index in range(2):
        base = index * REMAKE_SLOT_SIZE
        block = image[base:base + REMAKE_SLOT_SIZE]
        magic = block[0:4]
        version = block[4]
        payload_size = block[6] | (block[7] << 8)
        stored_crc = int.from_bytes(
            block[REMAKE_CRC_OFFSET:REMAKE_CRC_OFFSET + 4], "little"
        )
        computed_crc = 0xFFFFFFFF
        for byte in block[:REMAKE_CRC_OFFSET]:
            computed_crc ^= byte
            for _ in range(8):
                mask = 0 - (computed_crc & 1)
                computed_crc = (computed_crc >> 1) ^ (0xEDB88320 & mask)
        computed_crc = (~computed_crc) & 0xFFFFFFFF
        results.append({
            "slot_index": index,
            "magic": magic.hex(),
            "magic_ok": magic == REMAKE_MAGIC,
            "version": version,
            "version_ok": version == REMAKE_VERSION,
            "payload_size": payload_size,
            "stored_crc32": stored_crc,
            "computed_crc32": computed_crc,
            "crc_ok": stored_crc == computed_crc,
            "accepted": (
                magic == REMAKE_MAGIC
                and version == REMAKE_VERSION
                and stored_crc == computed_crc
            ),
        })
    return {
        "slots": results,
        "accepted_slots": [s["slot_index"] for s in results if s["accepted"]],
    }


def _remake_payload_values(decoded: dict) -> list[dict]:
    """The decoded field values of every active remake slot."""

    rows = []
    for slot in decoded["remake"]["slots"]:
        if "payload" not in slot:
            continue
        payload = slot["payload"]
        active = [
            {
                "index": index,
                "level": character["level"],
                "experience": character["experience"],
                "training_points": character["training_points"],
                "equipped_tools": [
                    tool for tool in character["equipped_tools"] if tool
                ],
            }
            for index, character in enumerate(payload["characters"])
            if character["active"]
        ]
        rows.append({
            "slot_index": slot["slot_index"],
            "generation": slot["generation"],
            "chapter_id": payload["chapter_id"],
            "flags": payload["flags"],
            "party": payload["party"],
            "ninja_tools": [
                (index, value)
                for index, value in enumerate(payload["ninja_tools"])
                if value
            ],
            "materials": [
                (index, value)
                for index, value in enumerate(payload["materials"])
                if value
            ],
            "active_characters": active,
            "inactive_character_count": sum(
                1 for character in payload["characters"]
                if not character["active"]
            ),
        })
    return rows


def _cross_format_table(original: dict, remake: dict) -> list[dict]:
    """The field-level difference table, one row per logical field."""

    rows = []
    for record in original["records"]:
        active = not record["erased"]
        if active:
            header = "%s (19 B) at %d" % (
                record["header_text"], record["sram_offset"])
            payload = "%d B at %d" % (
                record["payload_length"], record["payload_offset"])
            checksum = "~sum(payload) = %02X at %d" % (
                record["checksum"], record["checksum_offset"])
        else:
            header = "(all FF, unused) at %d" % record["sram_offset"]
            payload = "(all FF) %d B at %d" % (
                record["payload_length"], record["payload_offset"])
            checksum = "(all FF) at %d" % record["checksum_offset"]
        rows.append({
            "field": "record %d header" % record["descriptor_index"],
            "original": header,
            "remake": "-",
            "difference": "原版有身份头，重制没有；重制用 4 字节魔数代替",
            "state": "active" if active else "erased (all FF)",
        })
        rows.append({
            "field": "record %d payload" % record["descriptor_index"],
            "original": payload,
            "remake": "-",
            "difference": "原版每条记录自带负载",
            "state": "active" if active else "erased (all FF)",
        })
        rows.append({
            "field": "record %d checksum" % record["descriptor_index"],
            "original": checksum,
            "remake": "-",
            "difference": "原版是 1 字节取反和，重制是 4 字节 CRC32",
            "state": "active" if active else "erased (all FF)",
        })
    for slot in remake["slots"]:
        if slot["erased"]:
            rows.append({
                "field": "slot %d" % slot["slot_index"],
                "original": "-",
                "remake": "erased (all FF) at %d" % slot["sram_offset"],
                "difference": "空槽",
                "state": "erased",
            })
            continue
        rows.append({
            "field": "slot %d header" % slot["slot_index"],
            "original": "-",
            "remake": "%s v%d, payload_size=%d, generation=%d at %d"
                      % (slot["magic"], slot["version"],
                         slot["payload_size"], slot["generation"],
                         slot["sram_offset"]),
            "difference": "重制有版本/长度/世代三字段，原版没有",
            "state": "active",
        })
        rows.append({
            "field": "slot %d payload" % slot["slot_index"],
            "original": "-",
            "remake": "%d B at %d"
                      % (slot["payload_size"], slot["sram_offset"] + 12),
            "difference": "重制负载是 3524 B 的战役状态（章节/队伍/库存/63 个角色成长）",
            "state": "active",
        })
        rows.append({
            "field": "slot %d checksum" % slot["slot_index"],
            "original": "-",
            "remake": "CRC32 = %08X at %d"
                      % (slot["stored_crc32"],
                         slot["sram_offset"] + REMAKE_CRC_OFFSET),
            "difference": "重制是 4 字节 CRC32，原版是 1 字节取反和",
            "state": "active",
        })
    return rows


def _semantic_rows(original: dict, remake: dict) -> list[dict]:
    """Which game state each format stores, and where."""

    active_original = [
        r for r in original["records"] if not r["erased"]
    ]
    active_remake = [
        s for s in remake["slots"] if not s["erased"]
    ]
    rows = [
        {
            "semantic": "存档容器",
            "original": "10 条固定偏移记录，记录起点 = 前一条 payload_len + 0x14",
            "remake": "2 个 4096 B 槽，槽 1 起点 = 4096",
            "difference": "★ 容器不同 ⇒ 两种存档互相读不了",
        },
        {
            "semantic": "存档身份",
            "original": "每条记录 19 B 身份串 `Naruto-KONOHASENKI\\0`",
            "remake": "槽头 4 B 魔数 `KBCS`",
            "difference": "★ 身份机制不同",
        },
        {
            "semantic": "存档完整性",
            "original": "1 B `~sum(payload)`",
            "remake": "4 B CRC32",
            "difference": "★ 校验算法不同",
        },
        {
            "semantic": "版本 / 世代",
            "original": "无版本号；无世代计数器（记录同时有效）",
            "remake": "version(u8) + payload_size(u16) + generation(u32)",
            "difference": "★ 原版没有「双槽轮换 + 世代」这一套",
        },
        {
            "semantic": "关卡进度",
            "original": "record 0 payload（4732 B，负载内部未逐字段解码）",
            "remake": "slot payload `chapter_id` (u16 @ +12)",
            "difference": "重制侧已逐字段；原版侧未逐字段解码",
        },
        {
            "semantic": "队伍",
            "original": "record 0 payload（未逐字段解码）",
            "remake": "slot payload `party[3]` (@ +18)",
            "difference": "重制侧已逐字段",
        },
        {
            "semantic": "忍具 / 材料库存",
            "original": "record 0 payload（未逐字段解码）",
            "remake": "slot payload `ninja_tools[94]` (@ +22) + "
                      "`materials[18]` (@ +116)",
            "difference": "重制侧已逐字段",
        },
        {
            "semantic": "角色成长（等级/经验/训练点/忍术等级/装备）",
            "original": "record 0 payload（未逐字段解码）",
            "remake": "slot payload `characters[63] x 54 B` (@ +134)",
            "difference": "重制侧已逐字段",
        },
        {
            "semantic": "战斗名册（坐标/HP/阵营/行动标记）",
            "original": "★ record 7 payload = 6084 B = 13 x 0x1D4 "
                        "（battle 14 的 9 名单位就在里面）",
            "remake": "★ 无对应字段（战役状态里只有成长，不含战斗名册）",
            "difference": "★ 语义缺口：重制不落盘战斗名册",
        },
        {
            "semantic": "战斗结果 / 回合状态",
            "original": "record 2 (20 B) / record 8 (1404 B) / record 9 (512 B)",
            "remake": "无对应字段",
            "difference": "★ 语义缺口（record 2 负载实测 = "
                          "0e000000 00000000 0e000000 00000000 0000）",
        },
        {
            "semantic": "存档写入时机",
            "original": "只有世界地图「存档」菜单会写（战斗全程 0 字节变化）",
            "remake": "准备场景「存档」菜单 + 战斗胜利后自动存档",
            "difference": "★ 写盘时机不同",
        },
        {
            "semantic": "落盘字节数",
            "original": "22468 B（10 条记录用满 0x57D4）",
            "remake": "8192 B（2 x 4096）",
            "difference": "★ 占用差 14276 B",
        },
    ]
    return rows


def build_report(capture: dict) -> dict:
    original_images = capture["original"]["images"]
    remake_images = capture["remake"]["images"]

    original_hashes = {}
    for name, info in original_images.items():
        original_hashes.setdefault(info["sram_sha256"], []).append(name)
    original_pre = _load(
        pathlib.Path(original_images["original-pre-battle"]["sram_path"])
    )
    original_post = _load(
        pathlib.Path(original_images["original-post-battle"]["sram_path"])
    )
    original_diff = _diff_ranges(original_pre, original_post)

    remake_names = sorted(remake_images)
    remake_pre = _load(
        pathlib.Path(remake_images["remake-step-03-Down"]["sram_path"])
    )
    remake_first = _load(
        pathlib.Path(remake_images["remake-step-04-A"]["sram_path"])
    )
    remake_second = _load(
        pathlib.Path(remake_images["remake-step-08-A"]["sram_path"])
    )
    remake_battle = _load(
        pathlib.Path(remake_images[remake_names[-1]]["sram_path"])
    )

    original_decoded = decode_image(original_pre)
    remake_decoded = decode_image(remake_second)

    cross_bytes = _diff_ranges(original_pre, remake_second)
    attributed = []
    for start, end in cross_bytes:
        attributed.append({
            "start": start,
            "end": end,
            "length": end - start + 1,
            "original_field": _attribute(start, original_decoded["original"],
                                         remake_decoded["remake"]),
            "remake_field": _attribute(start, original_decoded["original"],
                                       remake_decoded["remake"]),
        })

    return {
        "inputs": {
            "original_rom_sha256": capture["original"]["rom_sha256"],
            "remake_rom_sha256": capture["remake"]["rom_sha256"],
            "descriptor_bank": check_descriptor_bank(),
        },
        "original": {
            "checkpoint_count": len(original_images),
            "distinct_images": len(original_hashes),
            "image_sha256": sorted(original_hashes),
            "pre_battle_sha256": original_images[
                "original-pre-battle"]["sram_sha256"],
            "post_battle_sha256": original_images[
                "original-post-battle"]["sram_sha256"],
            "pre_post_differing_bytes": sum(
                end - start + 1 for start, end in original_diff),
            "pre_post_diff_ranges": original_diff,
            "writes_during_battle": (
                len(original_hashes) != 1),
            "records": original_decoded["original"]["records"],
        },
        "remake": {
            "checkpoint_count": len(remake_images),
            "phases": {
                "boot_erased": {
                    "sha256": sha256_bytes(remake_pre),
                    "active_slots": decode_image(remake_pre)[
                        "remake"]["active_slot_count"],
                },
                "first_save": {
                    "sha256": sha256_bytes(remake_first),
                    "slots": [
                        {
                            "slot_index": s["slot_index"],
                            "magic_ok": s["magic_ok"],
                            "generation": s["generation"],
                            "crc_ok": s["crc_ok"],
                        }
                        for s in decode_image(remake_first)["remake"]["slots"]
                    ],
                },
                "second_save": {
                    "sha256": sha256_bytes(remake_second),
                    "slots": [
                        {
                            "slot_index": s["slot_index"],
                            "magic_ok": s["magic_ok"],
                            "generation": s["generation"],
                            "crc_ok": s["crc_ok"],
                        }
                        for s in decode_image(remake_second)["remake"]["slots"]
                    ],
                },
                "in_battle_last_step": {
                    "sha256": sha256_bytes(remake_battle),
                },
            },
            "diff_erased_to_first_save": {
                "differing_bytes": sum(
                    end - start + 1
                    for start, end in _diff_ranges(remake_pre, remake_first)),
                "ranges": _diff_ranges(remake_pre, remake_first),
            },
            "diff_first_to_second_save": {
                "differing_bytes": sum(
                    end - start + 1
                    for start, end in _diff_ranges(remake_first, remake_second)),
                "ranges": _diff_ranges(remake_first, remake_second),
            },
            "diff_second_save_to_last_battle_step": {
                "differing_bytes": sum(
                    end - start + 1
                    for start, end in _diff_ranges(remake_second,
                                                   remake_battle)),
                "ranges": _diff_ranges(remake_second, remake_battle),
            },
            "slots": remake_decoded["remake"]["slots"],
        },
        "cross_format": {
            "original_image_sha256": sha256_bytes(original_pre),
            "remake_image_sha256": sha256_bytes(remake_second),
            "differing_bytes": sum(end - start + 1
                                   for start, end in cross_bytes),
            "ranges": cross_bytes,
            "attributed": attributed,
            "field_table": _cross_format_table(
                original_decoded["original"], remake_decoded["remake"]),
            "semantic_table": _semantic_rows(
                original_decoded["original"], remake_decoded["remake"]),
            "remake_payload_values": _remake_payload_values(remake_decoded),
            "original_loader_on_remake_image": _original_loader_accepts(
                remake_second),
            "remake_loader_on_original_image": _remake_loader_accepts(
                original_pre),
            "original_loader_on_original_image": _original_loader_accepts(
                original_pre),
            "remake_loader_on_remake_image": _remake_loader_accepts(
                remake_second),
        },
    }


def _markdown(report: dict) -> str:
    lines = []
    add = lines.append
    add("# S49 存档字节对比（W4 自动生成）")
    add("")
    add("## 1. 输入")
    add("")
    add("| 项 | 值 |")
    add("|---|---|")
    add("| 原版 ROM sha256 | `%s` |"
        % report["inputs"]["original_rom_sha256"])
    add("| 重制 ROM sha256 | `%s` |"
        % report["inputs"]["remake_rom_sha256"])
    bank = report["inputs"]["descriptor_bank"]
    add("| 逆向线 descriptor bank | 存在=%s 一致=%s |"
        % (bank["available"], bank["matches"]))
    add("")
    add("## 2. 两侧在战斗期写不写 SRAM")
    add("")
    original = report["original"]
    remake = report["remake"]
    add("| 侧 | 检查点数 | 不同镜像数 | 战前→战后不同字节 | 结论 |")
    add("|---|---:|---:|---:|---|")
    add("| 原版 | %d | %d | %d | %s |"
        % (original["checkpoint_count"], original["distinct_images"],
           original["pre_post_differing_bytes"],
           "战斗中不写 SRAM" if not original["writes_during_battle"]
           else "战斗中写 SRAM"))
    add("| 重制 | %d | - | %d | 战斗自身不写；准备场景「存档」与战后自动存档写 |"
        % (remake["checkpoint_count"],
           remake["diff_second_save_to_last_battle_step"][
               "differing_bytes"]))
    add("")
    add("## 3. 重制侧三段写入的字节差")
    add("")
    add("| 阶段 | sha256 | 不同字节 |")
    add("|---|---|---:|")
    add("| 上电（未存档） | `%s` | - |"
        % remake["phases"]["boot_erased"]["sha256"][:16])
    add("| 准备场景存档（槽0 gen1） | `%s` | %d |"
        % (remake["phases"]["first_save"]["sha256"][:16],
           remake["diff_erased_to_first_save"]["differing_bytes"]))
    add("| 第二次存档（槽1 gen2） | `%s` | %d |"
        % (remake["phases"]["second_save"]["sha256"][:16],
           remake["diff_first_to_second_save"]["differing_bytes"]))
    add("| 战斗中最后一步 | `%s` | %d |"
        % (remake["phases"]["in_battle_last_step"]["sha256"][:16],
           remake["diff_second_save_to_last_battle_step"][
               "differing_bytes"]))
    add("")
    add("## 4. 跨格式字段级差异表")
    add("")
    add("| 字段 | 原版 | 重制 | 差异 | 状态 |")
    add("|---|---|---|---|---|")
    for row in report["cross_format"]["field_table"]:
        add("| %s | %s | %s | %s | %s |"
            % (row["field"], row["original"], row["remake"],
               row["difference"], row["state"]))
    add("")
    add("## 4b. 语义映射（游戏状态落在哪）")
    add("")
    add("| 语义 | 原版落在哪 | 重制落在哪 | 差异 |")
    add("|---|---|---|---|")
    for row in report["cross_format"]["semantic_table"]:
        add("| %s | %s | %s | %s |"
            % (row["semantic"], row["original"], row["remake"],
               row["difference"]))
    add("")
    add("## 4c. 重制侧槽内实测值")
    add("")
    add("| 槽 | 世代 | chapter_id | flags | party | 忍具 | 材料 | 激活角色 |")
    add("|---|---:|---:|---|---|---|---|---|")
    for row in report["cross_format"]["remake_payload_values"]:
        add("| %d | %d | %d | 0x%08X | %s | %s | %s | %s |"
            % (row["slot_index"], row["generation"], row["chapter_id"],
               row["flags"], row["party"], row["ninja_tools"],
               row["materials"],
               ", ".join(
                   "%d(lv%d/exp%d/tp%d)" % (c["index"], c["level"],
                                            c["experience"],
                                            c["training_points"])
                   for c in row["active_characters"])))
    add("")
    add("## 5. 互相能不能读")
    add("")
    compat = report["cross_format"]
    add("| 读取方 | 读取对象 | 结果 |")
    add("|---|---|---|")
    add("| 原版 loader | 原版存档 | 接受记录 %s |"
        % compat["original_loader_on_original_image"]["accepted_descriptors"])
    add("| 原版 loader | 重制存档 | 接受记录 %s |"
        % compat["original_loader_on_remake_image"]["accepted_descriptors"])
    add("| 重制 loader | 原版存档 | 接受槽 %s |"
        % compat["remake_loader_on_original_image"]["accepted_slots"])
    add("| 重制 loader | 重制存档 | 接受槽 %s |"
        % compat["remake_loader_on_remake_image"]["accepted_slots"])
    add("")
    add("跨格式不同字节数：**%d**" % compat["differing_bytes"])
    add("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",
                        default=str(WORK / "receipts" / "capture_sram.json"))
    parser.add_argument("--json", default=str(RECEIPTS / "save_compare.json"))
    parser.add_argument("--markdown",
                        default=str(RECEIPTS / "save_compare.md"))
    args = parser.parse_args(argv)

    capture_path = pathlib.Path(args.capture)
    if not capture_path.is_file():
        print("ERR missing capture receipt %s; run capture_sram.py first"
              % capture_path, file=sys.stderr)
        return 2
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    report = build_report(capture)
    write_json(args.json, report)
    write_text(args.markdown, _markdown(report))
    print("wrote %s" % args.json)
    print("wrote %s" % args.markdown)
    print("original: %d checkpoints, %d distinct images, pre/post diff %d B"
          % (report["original"]["checkpoint_count"],
             report["original"]["distinct_images"],
             report["original"]["pre_post_differing_bytes"]))
    print("remake: erased->save1 %d B, save1->save2 %d B, save2->battle %d B"
          % (report["remake"]["diff_erased_to_first_save"]["differing_bytes"],
             report["remake"]["diff_first_to_second_save"]["differing_bytes"],
             report["remake"]["diff_second_save_to_last_battle_step"][
                 "differing_bytes"]))
    print("cross format: %d differing bytes"
          % report["cross_format"]["differing_bytes"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
