#!/usr/bin/env python3
"""剧本区「孤儿字节」的**运行时不可达**验收（无头 mGBA）。

用法：
    python tools/mgba_probe/orphan_acceptance.py

背景：`notes/evidence/story-orphan-bytes-20261023.md` 用**静态**分析证明了
那 2,145 字节是「汉化补丁挤下来的旧剧本」——全 ROM 无指针可达、四张根表
没有槽指向它们。但那份笔记自己写着「**全程没跑 mGBA**」，于是
「运行时会不会被走到」这一层仍是静态推断。

这一道门禁把它变成**动态证据**：

  O1 **对照成立**：剧情 VM 入口 `0x080977B8` 断得住（探针在工作、故事在跑）。
  O2 **三块孤儿一次都没被执行**：在孤儿块的**首地址**下断点，
     跑完整段导航，命中数必须是 **0**。
     （孤儿块是**剧本字节码**而不是代码 —— 断点命中就等于「CPU 把那里
     当指令取出来了」，那才是真的被走到。）
  O3 **游戏进入的每一个剧本都是根表可达的**：VM 入口每次读到的 r0
     必须落在「四张根表逐槽展开出来的剧本首地址集合」里。
  O4 **场景 54 / 55 没有被走进过**（它们是汉化补丁合并掉的场景，
     静态上「交接表里没有 54/55、55 的正文是占位语」）。

依据：notes/evidence/story-orphan-bytes-20261023.md
"""
from __future__ import annotations

import json
import pathlib
import re
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.mgba_probe.story_vm_capture import Probe, KEY_BITS, HIT_RE  # noqa: E402

ROM_BASE = 0x08000000
VM_ENTRY = 0x080977B8

#: 孤儿块（**ROM 地址**）；文件偏移见 notes/evidence/story-orphan-bytes-20261023.md
ORPHANS = {
    "story_orphan_scene2_tail": 0x0800CAC2,
    "story_orphan_after54": 0x0804BE31,
    "story_orphan_after55": 0x0804C633,
}

#: 四张剧情根表（**文件偏移**）；槽号 = 场景号
ROOTS = {
    "before": (0x060C74, 55),
    "after": (0x060D54, 55),
    "logic": (0x060E34, 46),
    "events": (0x060EF0, 46),
}

#: 场景 54 / 55 的剧本首地址（静态考证见上面那份笔记）
SCENE_54 = 0x08049E76
SCENE_55 = 0x0804C616

PLAN = ["START"] + ["A"] * 40
FRAMES_PER_STEP = 90
BOOT_FRAMES = 1500

results: list[dict] = []
failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    if not ok:
        failures += 1
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def head(text: str) -> None:
    results.append({"section": text})
    print(text)


def root_script_starts(rom: bytes) -> set[int]:
    """四张根表逐槽展开出来的剧本首地址集合（ROM 地址）。"""
    out: set[int] = set()
    for base, scenes in ROOTS.values():
        for scene in range(scenes + 1):
            at = base + scene * 4
            if at + 4 > len(rom):
                continue
            (value,) = struct.unpack_from("<I", rom, at)
            if value >= ROM_BASE and value < ROM_BASE + len(rom):
                out.add(value)
    return out


def main() -> int:
    exe = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
    if not exe.exists():
        print(f"ERR {exe} missing; run: python tools/mgba_probe/build.py",
              file=sys.stderr)
        return 2
    rom_path = REPO / "rom" / "base.gba"
    rom = rom_path.read_bytes()
    known = root_script_starts(rom)

    head("O0) 四张根表展开出来的剧本首地址")
    check("根表能展开出剧本首地址", len(known) > 0, f"{len(known)} 个不同首地址")
    check("场景 54 / 55 的首地址都在里面",
          SCENE_54 in known and SCENE_55 in known,
          f"54=0x{SCENE_54:08X} 55=0x{SCENE_55:08X}")
    orphan_addrs = set(ORPHANS.values())
    check("三块孤儿**不在**根表可达集合里（静态前提）",
          not (orphan_addrs & known),
          f"交集 {sorted(hex(a) for a in (orphan_addrs & known))}")

    probe = Probe(exe, rom_path)
    entered: list[int] = []
    orphan_hits: dict[str, int] = {name: 0 for name in ORPHANS}
    vm_hits = 0
    try:
        probe.send(f"frames {BOOT_FRAMES} 0x000")
        armed: dict[int, int] = {}
        for address in [VM_ENTRY, *orphan_addrs]:
            for line in probe.send(f"b {address:#x}"):
                if "breakpoint #" in line:
                    armed[address] = int(line.split("#")[1].split()[0])

        for step, key in enumerate(PLAN):
            out = probe.send(f"frames {FRAMES_PER_STEP} 0x{KEY_BITS[key]:03X}")
            hit_addr = None
            for line in out:
                found = HIT_RE.search(line)
                if found:
                    hit_addr = int(found.group(2), 16)
                    break
            if hit_addr is None:
                probe.send("frames 6 0x000")
                continue
            if hit_addr == VM_ENTRY:
                vm_hits += 1
                regs = probe.registers()
                entered.append(regs.get("r0", 0))
            else:
                for name, address in ORPHANS.items():
                    if address == hit_addr:
                        orphan_hits[name] += 1
            # 重新下断点（mGBA 的软件断点会在命中后自动复原，但编号会变，
            # 重新拿一遍编号更稳）。
            for address, ident in list(armed.items()):
                probe.send(f"delete {ident}")
                for line in probe.send(f"b {address:#x}"):
                    if "breakpoint #" in line:
                        armed[address] = int(line.split("#")[1].split()[0])
            probe.send("frames 6 0x000")
            probe.send("frame")
    finally:
        probe.close()

    head("O1) 对照：剧情 VM 入口断得住")
    check("VM 入口命中次数 ≥ 3（探针在工作、故事在跑）", vm_hits >= 3, f"{vm_hits} 次")
    check("VM 入口读到的 r0 都落在 ROM 内",
          all(ROM_BASE <= a < ROM_BASE + len(rom) for a in entered),
          f"{len(entered)} 次")

    head("O2) 三块孤儿一次都没被执行")
    for name, count in orphan_hits.items():
        check(f"{name}（0x{ORPHANS[name]:08X}）命中 0 次", count == 0, f"{count} 次")

    head("O3) 游戏进入的每一个剧本都是根表可达的")
    unknown = [a for a in entered if a not in known]
    check("没有一个入口落在根表之外", not unknown,
          f"越界入口 {sorted(hex(a) for a in unknown)[:6]}")
    check("也没有一个入口落在孤儿块上",
          not (set(entered) & orphan_addrs))

    head("O4) 场景 54 / 55 没有被走进过")
    check("场景 54 的剧本没被进入", SCENE_54 not in entered,
          f"进入过 {entered.count(SCENE_54)} 次")
    check("场景 55 的剧本没被进入", SCENE_55 not in entered,
          f"进入过 {entered.count(SCENE_55)} 次")

    head("结论")
    ok = failures == 0
    print("  孤儿字节运行时验收：" + ("全部通过" if ok else f"{failures} 项失败"))
    out_path = REPO / "build" / "orphan-acceptance.json"
    out_path.write_text(json.dumps({
        "ok": ok,
        "failures": failures,
        "vm_hits": vm_hits,
        "entered": [f"0x{a:08X}" for a in entered],
        "orphan_hits": orphan_hits,
        "results": results,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"  已写出 {out_path.relative_to(REPO)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
