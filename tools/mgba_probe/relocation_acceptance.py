#!/usr/bin/env python3
"""剧情剧本搬迁的**真机验收**（无头 mGBA）。

用法：
    python tools/mgba_probe/relocation_acceptance.py

做四件事，每一件都是**动态证据**（不是静态推断）：

  L1 **游戏跟着改过的根表指针走** ——
     在剧情 VM 入口 `0x080977B8` 断住，读 r0：
     原版 ROM 的 r0 = 原地址，搬迁后的 ROM 的 r0 = **搬迁后的新地址**。
  L2 **跑中的剧本里就是新正文** ——
     在「显示文本」handler `0x080978DC` 断住，读跑着的指令流字节，
     解码成文字：被改的那一句必须是**变长之后**的内容。
  L3 **脚本继续往下跑** —— 改过的那句之后，后面的几句照样出现
     （⇒ 分支目标重基对了，没有跑飞）。
  L4 **画面只在对白那一行变** —— 两个 ROM 各截一张图，逐像素比：
     差异必须**只在正文行**，背景/立绘/名牌/框一个像素都不许动。

依据：notes/evidence/story-relocation-live-20261023.md
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.mgba_probe.story_vm_capture import Probe, KEY_BITS  # noqa: E402

DEFAULT_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
ROM_BASE = 0x08000000
VM_ENTRY = 0x080977B8
TEXT_HANDLER = 0x080978DC

PLAN = ["START"] + ["A"] * 13
BOOT_FRAMES = 1500
FRAMES_PER_STEP = 90

results: list[dict] = []
failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    if not ok:
        failures += 1
    row = {"check": name, "ok": bool(ok), "detail": detail}
    results.append(row)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def head(text: str) -> None:
    results.append({"section": text})
    print(text)


def run_capture(rom: pathlib.Path, breakpoint: int, script_bytes: int = 8) -> list[dict]:
    """Run story_vm_capture's probe against `rom` and return the hits."""
    cmd = [
        sys.executable, str(HERE / "story_vm_capture.py"), str(rom),
        "--breakpoint", hex(breakpoint),
        "--boot-frames", str(BOOT_FRAMES),
        "--plan", ",".join(PLAN),
        "--frames-per-step", str(FRAMES_PER_STEP),
        "--max-steps", "30",
        "--script-bytes", str(script_bytes),
        "--json", str(REPO / "build" / f"reloc-accept-{breakpoint:08X}-"
                                    f"{rom.stem}.json"),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads((REPO / "build" / f"reloc-accept-{breakpoint:08X}-"
                         f"{rom.stem}.json").read_text(encoding="utf-8"))
    return data.get("hits", [])


def decode_codes(raw_hex: str, skip_opcode: bool = True) -> list[int]:
    """Decode the running script bytes into font codes.

    The capture starts at the **opcode** byte, so the text body starts one
    byte later — skip it or the first character is lost.
    """
    data = bytes.fromhex(raw_hex.replace(" ", ""))
    if skip_opcode and data:
        data = data[1:]
    out = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0:
            break
        if b in (1, 2):
            width = 2 if b == 1 else 3
            i += width
            continue
        if 0x80 <= b <= 0x9F and i + 1 < len(data):
            out.append((b << 8) | data[i + 1])
            i += 2
            continue
        out.append(b)
        i += 1
    return out


def to_text(codes: list[int]) -> str:
    from tools import text_codec

    mapping, _ = text_codec.load_mapping(None)
    out = []
    for code in codes:
        if code in mapping:
            out.append(mapping[code])
        elif 32 <= code < 127:
            out.append(chr(code))
        else:
            out.append(f"{{{code:04X}}}")
    return "".join(out)


def render(rom: pathlib.Path, out_png: pathlib.Path, presses: list[str]) -> None:
    cmd = [
        sys.executable, str(HERE / "render_screen.py"), str(out_png),
        "--live", "--rom", str(rom),
    ]
    for key in presses:
        cmd += ["--press", key]
    subprocess.run(cmd, check=True, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


def main() -> int:
    if not DEFAULT_EXE.exists():
        print(f"ERR {DEFAULT_EXE} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2

    head("0) 造一个「对白变长」的 ROM")
    build = subprocess.run(
        ["node", str(REPO / "tools" / "build_reloc_test_rom.mjs")],
        cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if build.returncode != 0:
        print(build.stdout + build.stderr, file=sys.stderr)
        return 2
    info = json.loads((REPO / "build" / "reloc-test-info.json").read_text(encoding="utf-8"))
    moved = info["moved_scripts"][0]
    new_root = moved["roots"][0]["to"]
    old_root = moved["roots"][0]["from"]
    check("变长的对白触发了剧本搬迁", bool(moved), f"→ 0x{new_root:08X}")
    check("搬迁后的地址落在空闲区里", new_root >= 0x5DFBEC,
          f"0x{new_root:08X}")

    base_rom = REPO / "rom" / "base.gba"
    test_rom = REPO / "build" / "reloc-test.gba"

    head("L1) 游戏跟着改过的根表指针走")
    base_hits = run_capture(base_rom, VM_ENTRY)
    test_hits = run_capture(test_rom, VM_ENTRY)
    base_r0 = base_hits[0]["registers"]["r0"] if base_hits else None
    test_r0 = test_hits[0]["registers"]["r0"] if test_hits else None
    # 根表里存的是 **ROM 地址**；构建报告里的是**文件偏移**。
    check("原版 ROM：VM 入口拿到的是原地址",
          base_r0 == f"0x{old_root + ROM_BASE:08X}", str(base_r0))
    check("搬迁后的 ROM：VM 入口拿到的是**新地址**",
          test_r0 == f"0x{new_root + ROM_BASE:08X}", str(test_r0))

    head("L2) 跑中的剧本里就是变长后的新正文")
    text_hits = run_capture(test_rom, TEXT_HANDLER, script_bytes=120)
    check("在「显示文本」handler 上抓到了若干次命中", len(text_hits) >= 4,
          f"{len(text_hits)} 次")
    edited = None
    for hit in text_hits:
        addr = int(hit["script_address"], 16)
        if addr == new_root + (info.get("edited_offset", 0) or 0):
            edited = hit
    if edited is None:
        # 兜底：找跑到的正文里含有新文字尾巴的那一次。
        for hit in text_hits:
            text = to_text(decode_codes(hit["script_bytes"]))
            if info["new_text"][-4:] in text:
                edited = hit
                break
    check("抓到了被改的那一句", edited is not None,
          edited["script_address"] if edited else "没抓到")
    if edited is not None:
        text = to_text(decode_codes(edited["script_bytes"]))
        check("跑中的正文里出现了变长后新增的字",
              info["new_text"][-4:] in text, text[:60])
        check("跑中的正文仍在搬迁后的地址上",
              int(edited["script_address"], 16) >= 0x5DFBEC,
              edited["script_address"])

    head("L3) 改过的那句之后，脚本继续往下跑")
    tail = info["new_text"][-4:]
    texts = [to_text(decode_codes(h["script_bytes"])) for h in text_hits]
    edited_at = next((i for i, t in enumerate(texts) if tail in t), None)
    after = texts[edited_at + 1:] if edited_at is not None else []
    check("后面还有几句对白（分支重基对了，没有跑飞）", len(after) >= 2,
          " / ".join(t[:12] for t in after[:3]))

    head("L4) 画面只在对白那一行变")
    base_png = REPO / "build" / "reloc-accept-base.png"
    test_png = REPO / "build" / "reloc-accept-test.png"
    # 停在**被改的那一句**上（L3 证据的导航：START + A×4）。
    at_edited_line = ["START"] + ["A"] * 4
    render(base_rom, base_png, at_edited_line)
    render(test_rom, test_png, at_edited_line)
    try:
        from PIL import Image
    except ImportError:
        print("ERR 需要 Pillow 才能比像素（pip install pillow）", file=sys.stderr)
        return 2
    a = Image.open(base_png).convert("RGBA").load()
    b = Image.open(test_png).convert("RGBA").load()
    width, height = Image.open(base_png).size
    diff = 0
    rows = set()
    for y in range(height):
        for x in range(width):
            if a[x, y] != b[x, y]:
                diff += 1
                rows.add(y)
    check("两个画面尺寸一样", (width, height) == Image.open(test_png).size,
          f"{width}x{height}")
    check("画面确实变了（不是一模一样）", diff > 0, f"{diff} 个像素不同")
    check("差异**只在正文行**（背景/立绘/名牌/框一个像素都没动）",
          rows and all(112 <= y <= 152 for y in rows),
          f"差异行 {sorted(rows)[:4]}…{sorted(rows)[-2:] if rows else []}")
    check("差异比例很小（不是整屏重绘）", diff < width * height * 0.05,
          f"{diff}/{width * height} = {100.0 * diff / (width * height):.2f}%")

    head("结论")
    ok = failures == 0
    print("  真机验收：" + ("全部通过" if ok else f"{failures} 项失败"))
    out = REPO / "build" / "relocation-acceptance.json"
    out.write_text(json.dumps({"ok": ok, "failures": failures,
                               "results": results}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"  已写出 {out.relative_to(REPO)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
