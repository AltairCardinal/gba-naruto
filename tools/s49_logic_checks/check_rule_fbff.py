#!/usr/bin/env python3
"""``0xFBFF`` is a corrupt terminator, not a new format.

The original ROM carries exactly one corrupted component terminator.  At
``0x0825A8E4`` the trailer of character 26, visual slot 2, frame 2 reads
``0xFBFF`` where every other frame reads ``0xFFFF``.  The signed value of
``0xFBFF`` is -1025, so the common renderer -- which only accepts -1 as the
end of a component list -- does **not** stop there.  It steps on by one
20 byte component at a time and reads the data behind the frame as if it
were more components.  The reverse side closed this as a **corrupt
terminator**, not as a new format:

* the base run reads ``0x0825A8E4 = 0xFBFF`` then ``0x0825A8F8 = 0x00FF``,
  ``0x0825A90C = 0x0100`` and ``0x0825A920 = 0xA8D0`` -- four reads, one
  component apart, so the renderer overran the frame;
* the one byte control ROM (``0x0825A8E5``: ``0xFB`` -> ``0xFF``) reads
  ``0x0825A8E4 = 0xFFFF`` (-1) and stops immediately, producing exactly one
  legal object.

This tool verifies the ROM side from the local ``rom/base.gba`` (byte,
renderer instruction windows, and the patched control ROM's hash) and reads
the runtime traces from the reverse work tree.  It also reports what the
remake's generated catalog does with the same frame.

Usage::

    python tools/s49_logic_checks/check_rule_fbff.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from s49_logic_common import (  # noqa: E402
    EXIT_INPUT_ERROR,
    FAIL,
    ORIGINAL_ROM,
    PASS,
    REMAKE_ROOT,
    UNDECIDED,
    Check,
    CheckInputError,
    read_json,
    sha256_bytes,
    sha256_file,
)

#: The reverse work tree.  It holds the signed runtime traces of the
#: one byte A/B on the ROM.
REVERSE_ROOT = Path(r"D:\Shell\Github\gba-naruto-reverse")

ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

#: The file offset of the corrupted trailer (GBA address 0x0825A8E4).
TRAILER_OFFSET = 0x25A8E4
TRAILER_BYTES = "fffb0000"

#: The one byte repair the reverse side signed.
REPAIR_OFFSET = 0x25A8E5
REPAIR_BEFORE = 0xFB
REPAIR_AFTER = 0xFF
CONTROL_ROM_SHA256 = (
    "3f55e607829db4497a1f49200514777c89df01f3624fd849005b96247502507a"
)

#: The renderer's instruction windows, hashed by the reverse side's signed
#: manifest.
RENDERER_WINDOWS = (
    ("0x080629FC", "0x08062A0A", "1eec74c4d5fbbe612ea235443537b5f670eb656f460b623059ad4bdb6adda3fa"),
    ("0x080631F6", "0x08063214", "139cfdb1b42f080558791e74aab2d726cfb36e703555991b437065e744b32af7"),
)

FBFF_ARTIFACT = "artifacts/character-fbff-runtime-v1"

#: The ROM derived visual catalog the remake ships.
CATALOG = "butano-sequel/graphics/battle_unit_visual_catalog.json"

FBFF_CHARACTER_ID = 26
FBFF_VISUAL_SLOT = 2
FBFF_FRAME_INDEX = 2

TERMINATOR_FIELDS = ("frame_trailer_raw_hex", "renderer_terminator")


def measure_rom(root: Path) -> dict[str, Any]:
    path = root / "rom" / "base.gba"
    if not path.is_file():
        raise CheckInputError(f"missing the ROM under study: {path}")
    data = path.read_bytes()
    digest = sha256_bytes(data)
    if digest != ROM_SHA256:
        raise CheckInputError(f"{path} hashes to {digest}, not {ROM_SHA256}")

    trailer = data[TRAILER_OFFSET: TRAILER_OFFSET + 4]
    if trailer.hex() != TRAILER_BYTES:
        raise CheckInputError(
            f"the trailer at {TRAILER_OFFSET:#x} is {trailer.hex()}, "
            f"not {TRAILER_BYTES}"
        )
    patched = bytearray(data)
    if patched[REPAIR_OFFSET] != REPAIR_BEFORE:
        raise CheckInputError(
            f"the byte at {REPAIR_OFFSET:#x} is "
            f"{patched[REPAIR_OFFSET]:#04x}, not {REPAIR_BEFORE:#04x}"
        )
    patched[REPAIR_OFFSET] = REPAIR_AFTER
    control_digest = sha256_bytes(bytes(patched))

    windows = []
    for start, end, expected in RENDERER_WINDOWS:
        begin = int(start, 16) - 0x08000000
        finish = int(end, 16) - 0x08000000
        actual = sha256_bytes(data[begin:finish])
        if actual != expected:
            raise CheckInputError(
                f"the renderer window {start}..{end} hashes to {actual}, "
                f"not {expected}"
            )
        windows.append({"start": start, "end": end, "sha256": actual})

    return {
        "rom": "rom/base.gba",
        "rom_sha256": digest,
        "trailer_gba_address": f"0x{0x08000000 + TRAILER_OFFSET:08X}",
        "trailer_bytes": trailer.hex(),
        "trailer_signed_value": int.from_bytes(
            trailer[:2], "little", signed=True
        ),
        "repair": {
            "file_offset": REPAIR_OFFSET,
            "gba_address": f"0x{0x08000000 + REPAIR_OFFSET:08X}",
            "before": REPAIR_BEFORE,
            "after": REPAIR_AFTER,
            "changed_byte_count": 1,
        },
        "control_rom_sha256": control_digest,
        "control_rom_sha256_expected": CONTROL_ROM_SHA256,
        "renderer_windows": windows,
    }


def measure_reverse_tree(reverse_root: Path) -> dict[str, Any]:
    manifest_path = reverse_root / FBFF_ARTIFACT / "manifest.json"
    if not manifest_path.is_file():
        return {
            "available": False,
            "reason": f"the reverse work tree has no {FBFF_ARTIFACT}/manifest.json",
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    traces = {}
    for side in ("base", "control"):
        trace_path = reverse_root / FBFF_ARTIFACT / side / "renderer-loop.json"
        if not trace_path.is_file():
            raise CheckInputError(f"missing the runtime trace: {trace_path}")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        traces[side] = {
            "path": str(trace_path.relative_to(reverse_root)),
            "sha256": sha256_file(trace_path),
            "hits": [
                {
                    "pointer": hit["pointer"],
                    "raw_u16": hit["raw_u16"],
                    "signed_value": hit["signed_value"],
                }
                for hit in trace["hits"]
            ],
        }
    return {
        "available": True,
        "manifest_path": str(manifest_path.relative_to(reverse_root)),
        "manifest_sha256": sha256_file(manifest_path),
        "schema": manifest.get("schema"),
        "base_rom_sha256": manifest.get("base_rom", {}).get("sha256"),
        "control_rom_sha256": manifest.get("control_rom", {}).get("sha256"),
        "conclusion": manifest.get("conclusion", {}),
        "traces": traces,
    }


def measure_catalog(root: Path) -> dict[str, Any]:
    path = root / CATALOG
    payload = read_json(path)
    for entry in payload.get("entries", []):
        if entry.get("character_id") != FBFF_CHARACTER_ID:
            continue
        visuals = entry.get("visuals", [])
        if FBFF_VISUAL_SLOT >= len(visuals):
            continue
        visual = visuals[FBFF_VISUAL_SLOT]
        for frame in visual.get("frames", []):
            if frame.get("frame_index") != FBFF_FRAME_INDEX:
                continue
            components = frame.get("components", [])
            trailer_value = (
                components[-1].get("next_tile_index") if components else None
            )
            return {
                "catalog": CATALOG,
                "character_id": FBFF_CHARACTER_ID,
                "visual_slot": FBFF_VISUAL_SLOT,
                "semantic": visual.get("semantic"),
                "frame_index": FBFF_FRAME_INDEX,
                "frame_pointer_hex": frame.get("frame_pointer_hex"),
                "component_count": frame.get("component_count"),
                "trailer_value": trailer_value,
                "trailer_hex": (
                    f"{trailer_value:04x}" if trailer_value is not None else None
                ),
                "recorded_fields": {
                    field: frame.get(field) for field in TERMINATOR_FIELDS
                },
                "records_the_defect": all(
                    field in frame for field in TERMINATOR_FIELDS
                ),
            }
    raise CheckInputError(
        f"{path} has no character {FBFF_CHARACTER_ID} slot "
        f"{FBFF_VISUAL_SLOT} frame {FBFF_FRAME_INDEX}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remake-root", default=str(REMAKE_ROOT))
    parser.add_argument("--reverse-root", default=str(REVERSE_ROOT))
    args = parser.parse_args(argv)
    root = Path(args.remake_root).resolve()
    reverse_root = Path(args.reverse_root).resolve()

    check = Check(
        name="rule-fbff",
        title="0xFBFF 损坏终止符的缺陷语义",
        source="tools/s49_logic_checks/check_rule_fbff.py",
    )

    rom = measure_rom(root)
    check.add(
        "rom-trailer",
        PASS if rom["trailer_signed_value"] == -1025 else FAIL,
        "读 ROM 0x0825A8E4 处的终止符字节与它的有符号值",
        original="fffb0000，有符号值 -1025（不是 -1 ⇒ 渲染器不会在这里停）",
        remake=f"{rom['trailer_bytes']}，有符号值 {rom['trailer_signed_value']}",
        delta="—" if rom["trailer_signed_value"] == -1025 else "终止符被改过了",
    )
    check.add(
        "rom-renderer-windows",
        PASS if len(rom["renderer_windows"]) == 2 else FAIL,
        "把渲染器的那两段指令窗口重新算哈希，和逆向侧签名的清单比对",
        original="两段窗口的 sha256 与逆向侧签名一致",
        remake="；".join(
            f"{w['start']}..{w['end']}={w['sha256'][:12]}…"
            for w in rom["renderer_windows"]
        ),
        delta="—",
    )
    check.add(
        "rom-control-rom",
        PASS if rom["control_rom_sha256"] == CONTROL_ROM_SHA256 else FAIL,
        "把终止符高字节 0xFB 改成 0xFF，算出对照 ROM 的 sha256",
        original=f"对照 ROM sha256 {CONTROL_ROM_SHA256[:16]}…（逆向侧签名）",
        remake=f"对照 ROM sha256 {rom['control_rom_sha256'][:16]}…",
        delta="—" if rom["control_rom_sha256"] == CONTROL_ROM_SHA256 else "不同",
    )

    reverse = measure_reverse_tree(reverse_root)
    if not reverse.get("available"):
        check.add(
            "runtime-overrun", UNDECIDED,
            "逆向线的运行时轨迹在本机不存在",
            missing=reverse.get("reason", ""),
        )
    else:
        conclusion = reverse["conclusion"]
        base_hits = reverse["traces"]["base"]["hits"]
        control_hits = reverse["traces"]["control"]["hits"]
        pointers = [int(hit["pointer"], 16) for hit in base_hits]
        steps = {
            pointers[index + 1] - pointers[index]
            for index in range(len(pointers) - 1)
        }
        check.add(
            "runtime-overrun",
            PASS if (len(base_hits) == 4 and steps == {20}) else FAIL,
            "读逆向侧签名的基线运行时轨迹：渲染器读到损坏终止符之后，"
            "应当继续每 20 字节一个部件地越界读下去",
            original=f"基线读了 {len(base_hits)} 个指针，步长 {sorted(steps)}；"
                     f"语义 {conclusion.get('runtime_semantics')}",
            remake=f"轨迹 {reverse['traces']['base']['path']}",
            delta="—" if len(base_hits) == 4 and steps == {20} else "轨迹与签名不符",
        )
        check.add(
            "runtime-control-stops",
            PASS if control_hits and all(
                hit["pointer"] == "0x0825A8E4"
                and hit["raw_u16"] == "0xFFFF"
                and hit["signed_value"] == -1
                for hit in control_hits
            ) else FAIL,
            "读对照 ROM 的运行时轨迹：在修好的终止符处应当立刻停下",
            original="对照轨迹只读到 0x0825A8E4 = 0xFFFF（-1）就停",
            remake=f"对照轨迹 {reverse['traces']['control']['path']}，"
                   f"{len(control_hits)} 个命中",
            delta="—" if control_hits else "对照轨迹没有命中",
        )

    catalog = measure_catalog(root)
    check.add(
        "catalog-records-defect",
        PASS if catalog["records_the_defect"] else FAIL,
        "重制侧生成的视觉目录里，有没有把损坏终止符记下来"
        "（原样字节 + 渲染器不认这个终止符）",
        original="逆向侧的导出器会记 frame_trailer_raw_hex 与 renderer_terminator",
        remake=f"记录到的字段 {catalog['recorded_fields']}；"
               f"终止符值 {catalog['trailer_hex']}",
        delta="已记录" if catalog["records_the_defect"] else "缺陷被吞掉了",
    )
    check.add(
        "catalog-keeps-corrupt-value",
        PASS if catalog["trailer_hex"] == "fbff" else FAIL,
        "重制侧目录里这一帧的终止符值必须仍是损坏的那个 0xFBFF，"
        "不能被悄悄修好",
        original="0xFBFF（损坏值，渲染器越界是原版画面的一部分）",
        remake=catalog["trailer_hex"],
        delta="—" if catalog["trailer_hex"] == "fbff" else "值不同",
    )

    path = check.write()
    print(check.render())
    print(f"\nreceipt: {path}")
    return check.exit_code()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckInputError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(EXIT_INPUT_ERROR)
