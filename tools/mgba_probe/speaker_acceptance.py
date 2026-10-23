#!/usr/bin/env python3
"""说话人名表「变长化」转换的**真机验收**（无头 mGBA）。

用法：
    python tools/mgba_probe/speaker_acceptance.py

做四件事，每一件都是**动态证据**（不是静态推断）：

  A1 **用产品代码造一份「说话人名改长」的 ROM** ——
     `node tools/build_speaker_test_rom.mjs`（把 id 1「鸣人」改成「鸣人测试」）。
     这一步会触发**说话人名表**的结构转换（定长内联槽 → 指针表 + 变长串池），
     并改掉 ROM 里的 12 个取名读者（14 处代码补丁）。
     顺带核对：**产物 ROM 里那 14 处的字节 == 清单里的 `after_hex`**。

  A2 **阳性对照**：原版 `rom/base.gba` 用**同一套按键方案**必须**能跑**（不冻结）。
     没有这一条，「转换版能跑」就没有意义 —— 可能这套按键方案本身就没在推进画面。

  A3 **转换版必须能跑**（不冻结）⇒ 打印一句话结论。

  A4 **辅助快照**（**不参与判定**）：在转换版上把断点挂在「被补丁过的取名读者」
     的填充指令上，确认它**真的被执行到**、而且是在 **Thumb 状态**下执行的。

判据（**只看画面是否推进**）
----------------------------
  * 每按一次 A 截一张 mGBA 渲染缓冲（`rawshot`），比相邻两张的哈希；
  * **最后 3 张相同 ⇒ 卡死**；否则 ⇒ 能跑。
  * 判定用的运行**只挂一个永远不会命中的断点** `0x08FFFFFE` ——
    快速路径（`core->runFrame`）在游戏「等输入」时会永不返回，
    那是**宿主**的问题，不是游戏卡死。
  * ⚠️ **不要**用「断点 `0x08097A1C` 命不命中」当判据 ——
    那是 mGBA 调试器「断点命中后重执行该指令」造成的**假象**，
    **原版 ROM 上同样不命中**（notes/evidence/speaker-name-freeze-trace-20261023.md §1）。

依据：notes/evidence/speaker-name-freeze-trace-20261023.md
      notes/evidence/speaker-name-fix-20261023.md
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

# 判定用的运行机制（开机帧数、按键方案、永不命中的死断点、快照）与
# `speaker_freeze_trace.py` 共用同一份实现 —— 判据只有一处。
from tools.mgba_probe.speaker_freeze_trace import (  # noqa: E402
    DEAD_BP,
    PRESSES,
    run_case,
)

EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
BASE_ROM = REPO / "rom" / "base.gba"
TEST_ROM = REPO / "build" / "speaker-test.gba"
TEST_INFO = REPO / "build" / "speaker-test-info.json"
MANIFEST = REPO / "tools" / "data" / "speaker_name_code_patches.json"

#: 补丁末尾的填充指令（约定值）。
SAFE_FILLER = "c046"     # 0x46C0 = Thumb `mov r8, r8`：合法、不写标志、不改寄存器、2 字节
BANNED_FILLER = "00bf"   # 0xBF00 —— ARMv4T 上是**未定义指令** ⇒ 无限异常循环 ⇒ 卡死

#: 辅助断点：被补丁过的取名读者（剧情 VM op 0x08 handler）的**填充指令**那一格。
#: 补丁窗口 0x08097A0C 起 10 字节 ⇒ 最后一条（填充）在 0x08097A14。
AUX_BP = 0x08097A14

#: 14 处取名读者的**填充指令**地址（= 补丁起点 + 补丁长度 - 2）。
#: 断点挂在这里 ⇒ 只要这段代码被执行到就会命中 ⇒ 用来回答
#: 「这一处读者**有没有**被走到过」。
#:
#: ⚠️ 这只是**辅助信息**：mGBA 的断点是软件断点（原地改成 `BE00: bkpt`），
#: 命中时的寄存器快照**不是**那条指令的现场；命中次数也只是**下界**
#: （一次挂多条断点会互相污染 ⇒ 所以覆盖扫描**一次只挂一条**）。
#: 它**不参与**「能跑 / 卡死」的判定。
READER_FILLERS: dict[str, int] = {
    "battle_msg_name": 0x0807908E,          # 读者 1  战斗消息
    "cmd_msg_name": 0x080811D4,             # 读者 2  命令消息
    "cmd_msg_name_copy": 0x08081240,        # 读者 3  命令消息（拷贝）
    "battle_log_name": 0x0808604A,          # 读者 4  战斗日志
    "battle_log_name_2": 0x08088816,        # 读者 5  战斗日志（2）
    "cmd_msg_name_copy_2": 0x08088DB4,      # 读者 6  命令消息（拷贝 2）
    "name_cell_count": 0x08089364,          # 读者 7  名字格数
    "name_len": 0x0808D29C,                 # 读者 8  名字长度
    "name_draw": 0x0808D2BC,                # 读者 8  名字绘制
    "cmd_msg_name_copy_3": 0x08090154,      # 读者 9  命令消息（拷贝 3）
    "battle_msg_name_2": 0x08095516,        # 读者 10 战斗消息（2）
    "cmd_msg_name_append": 0x08095CF8,      # 读者 11 命令消息（追加）
    "vm_0x08": 0x08097A14,                  # 读者 12 剧情 VM op 0x08
    "vm_0x0E_second_name": 0x08097A30,      # 读者 12 剧情 VM op 0x0E（第二个名字）
}

#: 覆盖扫描用的剧情路线：开机 1500 帧 + START + 连按 A ×14（= A2/A3 那条）。
#: 用它是因为这条路线**已经被 A2/A3 验过**，不依赖任何额外的 build 产物。
COVERAGE_PRESSES = PRESSES
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


def judge(case: dict) -> dict:
    """按「最后 3 张画面相同 ⇒ 卡死」判定，并给出**卡在哪一步**。

    判据只有两条：
      1. 最后 3 张画面哈希完全相同 ⇒ 画面不再推进 ⇒ 卡死；
      2. mGBA 报了「非法指令」/ 工具判成「卡死」⇒ CPU 掉进了 BIOS 异常向量
         （`0xBF00` 的死循环就是这条路）。
    """
    hashes = list(case.get("screen_hashes") or [])
    tail = hashes[-3:]
    same_tail = len(tail) == 3 and len(set(tail)) == 1
    illegal = case.get("illegal_opcode")
    frozen = same_tail or bool(illegal) or case.get("verdict") == "卡死"
    where = case.get("frozen_at")
    if frozen:
        if illegal:
            where_text = (f"mGBA 报非法指令 {illegal.get('addr')}（{illegal.get('word')}）")
        elif where is not None:
            where_text = f"第 {where + 1} 步开始画面不再变化（哈希 {tail[0]}）"
        else:
            where_text = "画面冻结"
    else:
        where_text = f"画面变化 {case.get('changes')} 步，全程未冻结"
    return {
        "frozen": frozen,
        "changes": case.get("changes"),
        "frozen_at": where,
        "same_tail": same_tail,
        "illegal_opcode": illegal,
        "where": where_text,
        "hashes": hashes,
    }


def build_test_rom() -> dict:
    """用**产品代码**造一份「说话人名改长」的 ROM。"""
    cmd = ["node", str(REPO / "tools" / "build_speaker_test_rom.mjs")]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout + r.stderr, file=sys.stderr)
        raise SystemExit(2)
    info = json.loads(TEST_INFO.read_text(encoding="utf-8"))
    return info


def patch_sites(rom: bytes) -> list[tuple[int, str, str]]:
    """(文件偏移, before_hex, after_hex) × 14，取自清单。"""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = []
    for entry in data["patches"]:
        out.append((int(str(entry["rom_offset"]), 0),
                    str(entry["before_hex"]).lower(),
                    str(entry["after_hex"]).lower()))
    return out


def reader_coverage() -> dict:
    """逐处读者覆盖：**一次只挂一条断点**跑一遍剧情路线，统计每处的命中次数。

    ⚠️ 这是**辅助信息**，**不参与**「能跑 / 卡死」的判定：
      * mGBA 的断点是软件断点 ⇒ 命中次数是**下界**（多挂断点会互相污染）；
      * 命中时的寄存器快照**不是**那条指令的现场（同 §A4）。

    走的是 `speaker_freeze_trace.run_case` 那条**已经被验过**的路
    （开机 1500 帧 + START + 连按 A ×14），所以不需要额外的存档状态。
    """
    out: dict[str, dict] = {}
    for site, addr in READER_FILLERS.items():
        case = run_case(TEST_ROM, addr, presses=COVERAGE_PRESSES, label=f"覆盖：{site}")
        out[site] = {
            "filler": f"0x{addr:08X}",
            "hits": len(case.get("snapshots") or []),
            "verdict": case.get("verdict"),
        }
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not EXE.exists():
        print(f"ERR {EXE} missing; run: python tools/mgba_probe/build.py", file=sys.stderr)
        return 2

    head("A0) 前置条件：补丁末尾的填充指令是安全的那一条")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    patches = manifest["patches"]
    banned = [p["site"] for p in patches
              if str(p["after_hex"]).lower().endswith(BANNED_FILLER)]
    check(f"{len(patches)} 处补丁末尾没有 0xBF00（ARMv4T 未定义指令 ⇒ 卡死）",
          not banned, "、".join(banned))
    safe = [p["site"] for p in patches
            if not str(p["after_hex"]).lower().endswith(SAFE_FILLER)]
    check(f"{len(patches)} 处补丁末尾都是 0x46C0（mov r8, r8）", not safe, "、".join(safe))
    check("判定用的死断点存在（0x08FFFFFE，永不命中）", DEAD_BP == 0x08FFFFFE, hex(DEAD_BP))

    head("A1) 用产品代码造一份「说话人名改长」的 ROM")
    info = build_test_rom()
    check("转换版 ROM 已生成", TEST_ROM.exists(), str(TEST_ROM.relative_to(REPO)))
    check("改的是 id 1（鸣人）", info.get("id") == 1, str(info.get("id")))
    check("名字确实变长了", str(info.get("new_text", "")).endswith("测试"),
          f"{info.get('original')} → {info.get('new_text')}")
    check("构建报告里有 1 条转换记录",
          len(info.get("conversions") or []) == 1,
          json.dumps(info.get("conversions") or [], ensure_ascii=False))
    rom = TEST_ROM.read_bytes()
    check("产物 ROM 大小与原版一样", len(rom) == BASE_ROM.stat().st_size,
          f"{len(rom)} 字节")
    sites = patch_sites(rom)
    mismatch = [off for off, before, after in sites
                if rom[off:off + len(after) // 2].hex() != after]
    check(f"产物 ROM 里 {len(sites)} 处补丁逐字节等于清单的 after_hex",
          not mismatch,
          "、".join(f"0x{o:X}" for o in mismatch[:4]))

    head("A2) 阳性对照：原版 ROM 用同一套按键方案必须能跑")
    control = judge(run_case(BASE_ROM, None, presses=PRESSES, label="原版 ROM"))
    check("原版 ROM：不冻结", not control["frozen"], control["where"])
    check("原版 ROM：画面确实在推进", (control["changes"] or 0) >= 3,
          f"变化 {control['changes']} 步")

    head("A3) 转换版必须能跑（不冻结）")
    converted = judge(run_case(TEST_ROM, None, presses=PRESSES, label="转换版 ROM"))
    check("转换版：不冻结", not converted["frozen"], converted["where"])
    check("转换版：画面确实在推进", (converted["changes"] or 0) >= 3,
          f"变化 {converted['changes']} 步")
    if not converted["frozen"]:
        print(f"  结论：转换版能跑 —— 画面推进 {converted['changes']} 步"
              f"（{PRESSES} 次按键全程不冻结）")

    head("A4) 辅助快照（**不参与判定**）：被补丁过的取名读者真的被执行到")
    aux = run_case(TEST_ROM, AUX_BP, presses=PRESSES, label="辅助：填充指令断点")
    snaps = aux.get("snapshots") or []
    check("辅助断点命中过（补丁过的读者不是死代码）", len(snaps) >= 1,
          f"命中 {len(snaps)} 次")
    # ⚠️ **命中瞬间的寄存器快照不能当判据**：mGBA 的断点是**软件断点**
    #   （把目标指令原地改成 `BE00: bkpt`）⇒ Thumb 的 BKPT 走的是未定义指令异常
    #   ⇒ CPU 进 BIOS 异常向量（ARM 状态）⇒ 调试器报出「命中」之后 **CPU 继续跑完
    #   这一帧**才被宿主切帧停住 ⇒ 快照里的 PC/寄存器**不是那条指令的现场**
    #   （实测：首个快照的 pc = 0x0806112A，在剧情 VM 里，不在 0x08097A14）。
    #   这是**观测假象**，依据：notes/evidence/speaker-name-freeze-trace-20261023.md §3.1/§3.2。
    #   ⇒ 这里只把快照当**信息**打印，**不参与判定**。
    if snaps:
        first = snaps[0]
        sel = first.get("selected", {})
        print(f"  · 首个命中快照（观测假象，仅供参考）："
              f"pc={sel.get('r15')} state={first.get('state')}"
              f" r1={sel.get('r1')} lr={sel.get('r14')}")

    head("A5) 读者覆盖（**辅助信息，不参与判定**）：14 处读者各自被走到过没有")
    coverage = reader_coverage()
    reached = {s: r for s, r in coverage.items() if r["hits"] > 0}
    missed = [s for s, r in coverage.items() if r["hits"] == 0]
    for site, rec in coverage.items():
        mark = f"命中 ×{rec['hits']}" if rec["hits"] else "未命中"
        print(f"    {site:24s} filler={rec['filler']}  {mark}")
    check("覆盖扫描跑起来了（剧情 VM 读者 vm_0x08 被执行到 ⇒ 覆盖机制有效）",
          coverage.get("vm_0x08", {}).get("hits", 0) >= 1,
          f"vm_0x08 命中 {coverage.get('vm_0x08', {}).get('hits', 0)} 次")
    check("至少 1 处读者被剧情路线执行到", len(reached) >= 1,
          f"{len(reached)}/14：" + "、".join(reached))
    print(f"  · 未被剧情路线执行到的 {len(missed)} 处：{'、'.join(missed) if missed else '（无）'}")
    print("    ⇒ 这些读者只在**战斗 / 命令 / 日志 / 名字格**场景里才会走到，"
          "本轮的真机路线没有覆盖到（详见 notes/evidence/speaker-name-fix-20261023.md §5(f)）。")

    head("结论")
    ok = failures == 0
    print("  说话人名变长化真机验收：" + ("全部通过" if ok else f"{failures} 项失败"))
    out_path = REPO / "build" / "speaker-acceptance.json"
    out_path.write_text(json.dumps({
        "ok": ok,
        "failures": failures,
        "presses": PRESSES,
        "control": control,
        "converted": converted,
        "aux_hits": len(snaps),
        "reader_coverage": coverage,
        "results": results,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"  已写出 {out_path.relative_to(REPO)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
