#!/usr/bin/env python3
"""Dump the Konoha Senki story script as readable text.

Builds on tools/decode_story_script.py: walks every scene's bytecode and
renders the dialogue with speaker attribution, so the game's Chinese text can
be read and diffed without a running emulator.

Speaker tracking follows the script semantics:
    op 0x02  set dialogue box   [flag, character_id, expression]
    op 0x08  set portrait image [portrait_id]
    op 0x03  narration          clears the box
    op 0x01 / 0x20 / 0x32 / 0x05  text run (0x05 is a choice-menu label)

Usage:
    python tools/dump_story_text.py --scene 1
    python tools/dump_story_text.py --all --out build/story_text.txt
    python tools/dump_story_text.py --all --json build/story_text.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import konoha_font as kf  # noqa: E402
import decode_story_script as ds  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]


def speaker_name(cid: int, names: dict[int, str]) -> str:
    if cid in names:
        return names[cid]
    if 1 <= cid < len(kf.NAMES):
        return kf.NAMES[cid]
    return f"角色{cid}"


def clean(text: str) -> str:
    """Trim the trailing full-width padding the game uses for box layout."""
    return "\n".join(line.rstrip("　") for line in text.split("\n")).rstrip("　")


def dump_scene(rom: bytes, mapping: dict[int, str], names: dict[int, str], scene: int) -> list[dict]:
    roots = ds.scene_roots(rom, scene)
    merged: dict[int, ds.Node] = {}
    for root in roots.values():
        nodes, _ = ds.walk(rom, [root], mapping)
        merged.update(nodes)

    rows: list[dict] = []
    speaker = 0
    expression = 0
    portrait = 0
    for n in sorted(merged.values(), key=lambda n: n.offset):
        if n.op == 0x02 and len(n.raw) >= 4:
            speaker = n.raw[2]
            expression = n.raw[3]
        elif n.op == 0x08 and len(n.raw) >= 2:
            portrait = n.raw[1]
        elif n.op == 0x03:
            speaker = 0
        if n.text is None:
            continue
        text = clean(n.text)
        if not text.strip():
            continue
        kind = {0x01: "say", 0x20: "say", 0x32: "say", 0x05: "menu"}.get(n.op, "text")
        rows.append({
            "scene": scene,
            "rom_address": f"0x{n.offset + 0x08000000:08X}",
            "kind": kind,
            "speaker_id": speaker,
            "speaker": speaker_name(speaker, names) if (speaker and kind != "menu") else "",
            "expression": expression if speaker else 0,
            "portrait": portrait,
            "text": text,
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", help="write a readable text report here")
    ap.add_argument("--json", help="write a JSON report here")
    ap.add_argument("rom", nargs="?")
    args = ap.parse_args()

    rom_path = pathlib.Path(args.rom) if args.rom else next(REPO.glob("*.gba"))
    rom = rom_path.read_bytes()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    mapping, _ = kf.build_mapping(rom)
    names = kf.read_character_names(rom, mapping)
    print(f"character names decoded from the ROM name table: {len(names)}", file=sys.stderr)

    scenes = range(1, ds.STORY_SCENES + 1) if args.all else [args.scene]
    all_rows: list[dict] = []
    for scene in scenes:
        rows = dump_scene(rom, mapping, names, scene)
        all_rows.extend(rows)
        if args.scene and not args.all:
            print(f"=== scene {scene} ===")
            for r in rows:
                who = f"{r['speaker']}:" if r["speaker"] else ("[选项]" if r["kind"] == "menu" else "旁白:")
                print(f"  {r['rom_address']}  {who} {r['text']}")

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        cur = None
        for r in all_rows:
            if r["scene"] != cur:
                cur = r["scene"]
                lines.append(f"\n===== scene {cur} =====")
            who = f"{r['speaker']}" if r["speaker"] else ("选项" if r["kind"] == "menu" else "旁白")
            lines.append(f"  {r['rom_address']}  {who}：{r['text']}")
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {out} ({len(all_rows)} lines)", file=sys.stderr)

    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)

    if not args.out and not args.json and args.all:
        for r in all_rows[:40]:
            who = f"{r['speaker']}：" if r["speaker"] else "旁白："
            print(f"  scene{r['scene']:3d} {who}{r['text']}")
        print(f"\n{len(all_rows)} lines total", file=sys.stderr)


if __name__ == "__main__":
    main()
