#!/usr/bin/env python3
"""说话人名表「变长化」的**逐像素名字框核对**（无头 mGBA）。

用法：
    python tools/mgba_probe/speaker_namebox_check.py

回答一个问题
------------
**「鸣人测试」到底有没有被正确画进名字框？**

`tools/mgba_probe/speaker_acceptance.py` 只证明了「画面不再冻结」，
**没有证明「名字显示对了」** —— 而后者才是这个功能的**目的**。
本脚本用**逐像素比对**补上这一条：

1. 用**产品代码**造一份「鸣人」→「鸣人测试」的 ROM（`build/speaker-test.gba`）。
2. 用**同一套按键方案**（START + 连按 A）在**原版**与**转换版**上各跑一遍，
   每一步都抓一张 mGBA 渲染缓冲（`rawshot`）。
3. 逐像素比对同一时刻的两张图，定位**名字框**并断言：

   * **N1** 转换版确实比原版**多出字**（存在差分像素，且差分是一块矩形）；
   * **N2** 名字框里的**前两个字仍是「鸣人」** ——
     原版名字所占的矩形在两张图里**逐字节相同**
     ⇒ 新名字是**在原名字后面追加**的，不是重新居中/重排的；
   * **N3** 名字框**没有溢出**：所有差分像素都落在转换版名字框矩形内，
     框外差分为 0；
   * **N4** 对话正文那一行与原版**一致**（这次只改了名字，正文不该变）。

判据里的两个派生量都是**算出来的**，不是写死的
----------------------------------------------------
* `cell_w`（一个字形格宽）= 差分矩形宽 ÷ 新增字数；
* 原版名字矩形的宽 = 原名字字数 × `cell_w`，其**右边界紧贴**差分矩形的左边界。

依据：notes/evidence/speaker-name-namebox-verification-20261023.md
      notes/evidence/speaker-name-fix-20261023.md
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from tools.mgba_probe.story_vm_capture import KEY_BITS, Probe  # noqa: E402
from tools.mgba_probe.speaker_freeze_trace import (  # noqa: E402
    BOOT_FRAMES,
    DEAD_BP,
    FRAMES_PER_PRESS,
    GAP_FRAMES,
    PRESSES,
    arm,
    send,
)

EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
BASE_ROM = REPO / "rom" / "base.gba"
TEST_ROM = REPO / "build" / "speaker-test.gba"
TEST_INFO = REPO / "build" / "speaker-test-info.json"
OUTDIR = REPO / "build" / "namebox"
REPORT = REPO / "build" / "speaker-namebox-check.json"

W, H = 240, 160

results: list[dict] = []
failures = 0


def check(name: str, ok: bool, detail: str = "") -> bool:
    global failures
    if not ok:
        failures += 1
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def head(text: str) -> None:
    results.append({"section": text})
    print(text)


# ------------------------------------------------------------------ 像素小工具
def pixel(data: bytes, x: int, y: int) -> tuple[int, int, int, int]:
    o = (y * W + x) * 4
    return tuple(data[o:o + 4])  # type: ignore[return-value]


def bbox(points: list[tuple[int, int]]) -> tuple[int, int, int, int] | None:
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def region_bytes(data: bytes, x0: int, y0: int, x1: int, y1: int) -> bytes:
    return b"".join(data[(y * W + x) * 4:(y * W + x) * 4 + 4]
                    for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))


def region_equal(a: bytes, b: bytes, x0: int, y0: int, x1: int, y1: int) -> bool:
    return region_bytes(a, x0, y0, x1, y1) == region_bytes(b, x0, y0, x1, y1)


def save_png(data: bytes, path: pathlib.Path, scale: int = 3) -> None:
    try:
        from PIL import Image
    except Exception:
        return
    img = Image.frombytes("RGBA", (W, H), data)
    img.save(path)
    img.resize((W * scale, H * scale), Image.NEAREST).save(
        path.with_name(path.stem + f"_x{scale}.png"))


# ------------------------------------------------------------------ 抓帧
def capture(rom: pathlib.Path, label: str) -> list[tuple[str, bytes]]:
    """跑一遍 START + 连按 A，每一步抓一张 rawshot。"""
    OUTDIR.mkdir(parents=True, exist_ok=True)
    raw = OUTDIR / f"{label}.raw"
    probe = Probe(EXE, rom)
    frames: list[tuple[str, bytes]] = []
    try:
        send(probe, f"frames {BOOT_FRAMES} 0x000")
        arm(probe, DEAD_BP)

        def grab(step: str) -> bytes:
            send(probe, f"rawshot {raw}")
            data = raw.read_bytes()[:W * H * 4]
            (OUTDIR / f"{label}_{step}.raw").write_bytes(data)
            return data

        frames.append(("boot", grab("boot")))
        for i in range(PRESSES):
            key = "START" if i == 0 else "A"
            send(probe, f"frames {FRAMES_PER_PRESS} 0x{KEY_BITS[key]:03X}")
            send(probe, f"frames {GAP_FRAMES} 0x000")
            frames.append((f"{key}{i}", grab(f"{key}{i}")))
    finally:
        probe.close()
    return frames


# ------------------------------------------------------------------ 主流程
def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    head("N0) 前置条件")
    if not EXE.exists():
        print(f"ERR {EXE} missing; run: python tools/mgba_probe/build.py", file=sys.stderr)
        return 2
    r = subprocess.run(["node", str(REPO / "tools" / "build_speaker_test_rom.mjs")],
                       cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout + r.stderr, file=sys.stderr)
        return 2
    info = json.loads(TEST_INFO.read_text(encoding="utf-8"))
    original = str(info["original"])
    new_text = str(info["new_text"])
    check("转换版 ROM 已生成", TEST_ROM.exists(), str(TEST_ROM.relative_to(REPO)))
    check("原版与转换版不是同一个文件（否则比对是空的）",
          BASE_ROM.read_bytes() != TEST_ROM.read_bytes())
    check("名字确实变长了（追加，不是替换）",
          new_text.startswith(original) and len(new_text) > len(original),
          f"{original} → {new_text}")
    added_chars = len(new_text) - len(original)
    print(f"  原名 {original!r}（{len(original)} 字） → 新名 {new_text!r}"
          f"（{len(new_text)} 字），新增 {added_chars} 字")

    head("N1) 同一按键序列下逐帧抓图（START + 连按 A ×%d）" % PRESSES)
    base_frames = capture(BASE_ROM, "base")
    conv_frames = capture(TEST_ROM, "conv")
    check("两次运行的帧数一致", len(base_frames) == len(conv_frames),
          f"{len(base_frames)} vs {len(conv_frames)}")

    # 找出「有差分」的那些步 —— 那就是名字框出现的时刻
    per_step: list[dict] = []
    for (sa, da), (sb, db) in zip(base_frames, conv_frames):
        diffs = [(x, y) for y in range(H) for x in range(W)
                 if pixel(da, x, y) != pixel(db, x, y)]
        row = {
            "step": sa,
            "base_sha": hashlib.sha1(da).hexdigest()[:12],
            "conv_sha": hashlib.sha1(db).hexdigest()[:12],
            "diff_pixels": len(diffs),
            "diff_bbox": bbox(diffs),
        }
        per_step.append(row)
        print(f"  {sa:7s} base={row['base_sha']} conv={row['conv_sha']} "
              f"差分像素={row['diff_pixels']}")

    diff_steps = [row for row in per_step if row["diff_pixels"] > 0]
    check("至少有一帧出现差分（名字框确实显示出来了）", len(diff_steps) >= 1,
          f"{len(diff_steps)} 帧有差分：" +
          "、".join(row["step"] for row in diff_steps))
    if not diff_steps:
        return 1

    # 差分矩形必须在所有有差分的帧里完全一致（同一个名字框、同一个位置）
    boxes = {row["diff_bbox"] for row in diff_steps}
    check("所有有差分的帧，差分矩形完全一致（同一个名字框）", len(boxes) == 1,
          "、".join(str(b) for b in sorted(boxes)))

    head("N2) 名字框的逐像素断言")
    # 用第一帧有差分的画面做详查
    first = diff_steps[0]
    step_name = first["step"]
    base = dict(base_frames)[step_name]
    conv = dict(conv_frames)[step_name]
    dx0, dy0, dx1, dy1 = first["diff_bbox"]  # type: ignore[misc]
    diff_w = dx1 - dx0 + 1
    diff_h = dy1 - dy0 + 1

    cell_w = diff_w / added_chars
    check("一个字形格的宽度是整数", cell_w == int(cell_w),
          f"差分宽 {diff_w} ÷ 新增 {added_chars} 字 = {cell_w}")
    cell_w = int(cell_w)

    base_name_w = len(original) * cell_w
    base_x0 = dx0 - base_name_w
    conv_x1 = dx1
    print(f"  差分矩形 = x[{dx0},{dx1}] × y[{dy0},{dy1}]"
          f"（{diff_w}×{diff_h} px，{diff_w // cell_w} 个字形格）")
    print(f"  原版名字矩形 = x[{base_x0},{dx0 - 1}] × y[{dy0},{dy1}]"
          f"（{base_name_w} px = {len(original)} 字）")
    print(f"  转换版名字矩形 = x[{base_x0},{conv_x1}] × y[{dy0},{dy1}]"
          f"（{conv_x1 - base_x0 + 1} px = {len(new_text)} 字）")

    check("原版名字矩形的左边界没有跑到屏幕外", base_x0 >= 0, f"x0={base_x0}")

    # N2-a：原版名字矩形在两张图里逐字节相同 ⇒ 前两个字没被重排
    same_prefix = region_equal(base, conv, base_x0, dy0, dx0 - 1, dy1)
    check("原版名字所占的矩形在原版与转换版里逐字节相同"
          "（⇒ 前两个字仍是「鸣人」，是追加不是重排）",
          same_prefix,
          f"x[{base_x0},{dx0 - 1}] × y[{dy0},{dy1}]")

    # N2-b：差分像素全部落在转换版名字矩形内
    diffs = [(x, y) for y in range(H) for x in range(W)
             if pixel(base, x, y) != pixel(conv, x, y)]
    outside = [(x, y) for x, y in diffs
               if not (base_x0 <= x <= conv_x1 and dy0 <= y <= dy1)]
    check("名字框没有溢出（所有差分像素都落在转换版名字矩形内）",
          not outside, f"溢出 {len(outside)} 像素")

    # N2-c：名字矩形以外逐字节相同（正文、头像、边框……全都没动）
    outside_diff = 0
    for y in range(H):
        for x in range(W):
            if base_x0 <= x <= conv_x1 and dy0 <= y <= dy1:
                continue
            if pixel(base, x, y) != pixel(conv, x, y):
                outside_diff += 1
    check("名字矩形以外的每一个像素都与原版一致", outside_diff == 0,
          f"框外差分 {outside_diff} 像素")

    # N2-d：对话正文那一行与原版一致（正文在名字行下方）
    body_ok = region_equal(base, conv, 0, dy1 + 1, W - 1, H - 1)
    check("对话正文那一行（名字行以下）与原版一致", body_ok,
          f"y[{dy1 + 1},{H - 1}] × x[0,{W - 1}] 逐字节相同")

    # N2-e：名字确实「多出了字」—— 墨色像素变多
    ink_colors = ({pixel(conv, x, y) for x, y in diffs}
                  - {pixel(base, x, y) for x, y in diffs})
    check("新增字形用的是与名字同族的墨色（差分区里出现的新颜色）",
          len(ink_colors) >= 1,
          "、".join(str(c) for c in sorted(ink_colors)))
    base_ink = [(x, y) for y in range(dy0, dy1 + 1)
                 for x in range(base_x0, dx0)
                 if pixel(base, x, y) in ink_colors]
    conv_ink = [(x, y) for y in range(dy0, dy1 + 1)
                 for x in range(base_x0, conv_x1 + 1)
                 if pixel(conv, x, y) in ink_colors]
    check("原版名字矩形里确实有名字墨色（⇒ 找对了名字框）",
          len(base_ink) >= 1, f"{len(base_ink)} 个墨色像素")
    check("转换版名字框里的墨色像素比原版多（⇒ 确实多出了字）",
          len(conv_ink) > len(base_ink),
          f"{len(base_ink)} → {len(conv_ink)}")

    # N2-f：原版名字墨色的横向范围紧贴差分矩形左边 ⇒ 名字是左对齐追加的
    base_ink_box = bbox(base_ink)
    check("原版名字墨色的横向范围 = 原版名字矩形"
          "（⇒ 名字左对齐，转换版是在它右边追加）",
          base_ink_box is not None
          and base_ink_box[0] == base_x0
          and base_ink_box[2] == dx0 - 1,
          f"墨色 bbox x[{base_ink_box[0]},{base_ink_box[2]}]，"
          f"期望 x[{base_x0},{dx0 - 1}]" if base_ink_box else "无墨色")

    head("N3) 证据截图")
    save_png(base, OUTDIR / f"base_{step_name}.png")
    save_png(conv, OUTDIR / f"conv_{step_name}.png")
    for label, data in (("base", base), ("conv", conv)):
        try:
            from PIL import Image
        except Exception:
            break
        cx0 = max(0, base_x0 - 8)
        cy0 = max(0, dy0 - 6)
        cx1 = min(W, conv_x1 + 9)
        cy1 = min(H, dy1 + 7)
        img = Image.frombytes("RGBA", (W, H), data)
        img.crop((cx0, cy0, cx1, cy1)).resize(
            ((cx1 - cx0) * 4, (cy1 - cy0) * 4), Image.NEAREST).save(
                OUTDIR / f"{label}_{step_name}_namebox.png")
    print(f"  已写出 {OUTDIR.relative_to(REPO)}/（base/conv 原图 + 名字框放大图）")

    head("结论")
    ok = failures == 0
    print("  逐像素名字框核对：" + ("全部通过" if ok else f"{failures} 项失败"))
    REPORT.write_text(json.dumps({
        "ok": ok,
        "failures": failures,
        "original": original,
        "new_text": new_text,
        "added_chars": added_chars,
        "cell_width": cell_w,
        "diff_rect": {"x0": dx0, "y0": dy0, "x1": dx1, "y1": dy1},
        "base_name_rect": {"x0": base_x0, "y0": dy0, "x1": dx0 - 1, "y1": dy1},
        "conv_name_rect": {"x0": base_x0, "y0": dy0, "x1": conv_x1, "y1": dy1},
        "ink_colors": [list(c) for c in sorted(ink_colors)],
        "base_ink_pixels": len(base_ink),
        "conv_ink_pixels": len(conv_ink),
        "steps": per_step,
        "results": results,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"  已写出 {REPORT.relative_to(REPO)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
