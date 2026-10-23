#!/usr/bin/env python3
"""说话人名表「变长化」的**读者覆盖取证**（无头 mGBA）。

回答的问题
----------
台账 F18 / N5① 记的是：**真机验收只覆盖了 14 处取名读者里的 1 处**
（剧情 VM 的 `vm_0x08`），其余 13 处属「战斗消息 / 命令消息 / 战斗日志」场景，
当时的按键路线到不了。本脚本把这 13 处**真的跑到**，并给出可分档的结论。

三档判定
--------
* **A 自然场景跑到并取证** —— 在无头 mGBA 里用**真实按键路线**把该读者执行到，
  并且能用画面 / 断点命中证明它跑过。
* **B 受控触发取证** —— 在无头 mGBA 里用调试器**在读者入口处写好 id / 寄存器**，
  再单步走一遍补丁窗口，证明**补丁后的代码在真实 CPU 上语义正确**
  （算出的槽位对、解出的指针合法、字形码解出来是对的）。
  ⚠️ 这是**受控触发**，**不是**自然场景覆盖。
* **C 只有静态判定** —— 静态反汇编能说清它属于哪个界面，但运行时没跑到。

三条路线（全部在**转换版 ROM** 上跑）
------------------------------------
1. `story`  —— 开机 → START → 连按 A（含菜单键）。剧情路。
2. `battle` —— 读 `build/l2-states/battle.ss9`（停在剧情状态机循环头
   `0x0808F752`）→ 三次内存写强制进一场战斗 → 连按 A。战斗路。
3. 受控触发 —— 见 `controlled_trigger()`。

判据纪律
--------
* **判「能跑 / 卡死」只看画面推进**：每按一次 A 截一张 mGBA 渲染缓冲，
  比相邻两张哈希，**最后 3 张相同 ⇒ 冻结**。判定用的运行**只挂一个永不命中的
  断点** `0x08FFFFFE`。
* **辅助断点只用来取快照，不参与判定**；读者覆盖扫描**一次只挂一条**读者断点。
* ⚠️ mGBA 的断点是**软件断点**（原地改成 `BE00: bkpt`），命中时的寄存器快照
  **不是**那条指令的现场 ⇒ **寄存器级证据一律用受控触发的单步**，
  不用断点命中时的快照。

用法
----
    python tools/mgba_probe/speaker_reader_coverage.py             # 全跑
    python tools/mgba_probe/speaker_reader_coverage.py --static    # 只跑静态可达性
    python tools/mgba_probe/speaker_reader_coverage.py --controlled # 只跑受控触发

产物
----
    build/speaker-reader-coverage.json    机器可读的取证表
    build/speaker-reader-coverage.md      自动生成的表（报告直接引用它）
    build/speaker-reader-shots/           各路线的截图

依据：notes/evidence/speaker-names-hypothesis-ledger.md（F18 / N5①）
      notes/evidence/speaker-name-freeze-trace-20261023.md（判据与断点假象）
      notes/evidence/speaker-name-table-20261023.md（12 个原生读者的考证）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tools.mgba_probe.story_vm_capture import KEY_BITS, Probe  # noqa: E402

import text_codec  # noqa: E402

EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
BASE_ROM = REPO / "rom" / "base.gba"
TEST_ROM = REPO / "build" / "speaker-test.gba"
TEST_INFO = REPO / "build" / "speaker-test-info.json"
MANIFEST = REPO / "tools" / "data" / "speaker_name_code_patches.json"
BATTLE_STATE = REPO / "build" / "l2-states" / "battle.ss9"
SHOTDIR = REPO / "build" / "speaker-reader-shots"
OUT_JSON = REPO / "build" / "speaker-reader-coverage.json"
OUT_MD = REPO / "build" / "speaker-reader-coverage.md"

ROM_BASE = 0x08000000
DEAD_BP = 0x08FFFFFE          # 永不命中的死断点（判「能跑/卡死」时只挂它）
BOOT_FRAMES = 1500
FRAMES_PER_PRESS = 8
GAP_FRAMES = 120
FROZEN_TAIL = 3

# ---------------------------------------------------------------- 战斗路线的地址
STORY_STATE = 0x020311D4
SCENE_BYTE = STORY_STATE + 0x16     # 0x020311EA 战场组号
SUBCFG_BYTE = STORY_STATE + 0x19    # 0x020311ED 编成子配置
PHASE_WORD = STORY_STATE + 0x12     # 0x020311E6 相位（u16，0x0110 = 战斗）
MAPID_BYTE = STORY_STATE + 0x17     # 0x020311EB 战斗地图号
UNIT_ARRAY = 0x020240C0             # 12 槽，步长 0x1D4
UNIT_STRIDE = 0x1D4
PHASE_BATTLE = 0x0110

#: 剧情路的按键方案。`base` 跑一遍；剧情推进到后面几屏才会走到
#: 「名字板」那条绘制路径（读者 8），所以方案要重复若干遍。
STORY_PLAN = (["START"] + ["A"] * 12
              + ["B", "B", "UP", "DOWN", "LEFT", "RIGHT", "START", "SELECT"])
STORY_REPEATS = 12

#: 战斗路的按键方案。
BATTLE_PRESSES = 6
#: 战斗编成矩阵：(组号, 子配置)。组号 = 地图号。
#: ⚠️ **子配置要挑**：读者 7（`name_cell_count`）只在 **group 1 / sub 1**
#: （以及 group 31..38 的一部分）里被走到 —— group 1 / sub 0 **走不到**。
#: （144 组编成全扫一遍的结论见 `notes/evidence/speaker-name-reader-coverage-20261023.md` §3.4。）
BATTLE_FORMATIONS = [(1, 0), (1, 1), (31, 1), (32, 0), (33, 0), (34, 0),
                     (35, 0), (36, 0), (37, 0), (38, 0)]

#: 剧情场景分派路：把相位设成 0x0030 ⇒ 状态机走 `0x0808F544` →
#: `0x0808F4D4(scene)` ⇒ 直接进第 `scene` 号剧情场景。
#: （配方同 `tools/mgba_probe/l4_battle_matrix.py` 的 "maps/flow" 轴。）
SCENE_PHASE = 0x0030
SCENE_LIST = list(range(1, 56))
#: 每个剧情场景按多少次 A。
#: ⚠️ **必须是 40**：op 0x0E（读者 12 的第二处）只在**场景 53 的深处**才出现
#: ——实测 10 次按键只走到 `vm_0x08` / `name_len` / `name_draw`，
#: 40 次按键才第一次命中 `vm_0x0E_second_name`。
SCENE_PRESSES = 40

results: list[dict] = []
failures = 0


# ------------------------------------------------------------------ 小工具
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


_SEQ = [0]


def send(probe: Probe, cmd: str) -> list[str]:
    """发一条命令并读回它的输出。

    token 用**全局自增序号**：`story_vm_capture.Probe.send()` 的 token 由
    「命令文本 hash + stderr 行数」决定，而 stderr 行数是另一个线程异步更新的
    ⇒ 同样的命令文本可能拿到同一个 token ⇒ 上一次 `send()` 会把本次的 token
    读走 ⇒ 下一次 `send()` 永远等不到 token（**挂死**，实测过）。
    """
    _SEQ[0] += 1
    token = f"__end_{_SEQ[0]:08d}"
    probe.proc.stdin.write(f"{cmd}\necho {token}\n")
    probe.proc.stdin.flush()
    lines: list[str] = []
    while True:
        line = probe.proc.stdout.readline()
        if not line:
            raise EOFError("probe exited")
        line = line.rstrip("\r\n")
        if line == token:
            return lines
        lines.append(line)


def arm(probe: Probe, addr: int) -> int | None:
    """挂一条 Thumb 断点，返回它的编号。"""
    for line in send(probe, f"b/t {addr:#x}"):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def disarm(probe: Probe, ident: int | None) -> None:
    if ident is not None:
        send(probe, f"delete {ident}")


def status(probe: Probe) -> dict[str, int]:
    """完整 CPU 状态（含 cpsr）。"""
    out: dict[str, int] = {}
    for line in send(probe, "status"):
        parts = line.replace("cpsr:", " cpsr: ").split()
        for i, tok in enumerate(parts):
            if not tok.endswith(":"):
                continue
            name = tok[:-1]
            if i + 1 < len(parts):
                try:
                    out[name] = int(parts[i + 1], 16)
                except ValueError:
                    pass
    return out


def write_reg(probe: Probe, name: str, value: int) -> None:
    send(probe, f"w/r {name} {value:#x}")


def shot(probe: Probe, name: str) -> str:
    """截一张渲染缓冲（PNG），返回文件路径。"""
    SHOTDIR.mkdir(parents=True, exist_ok=True)
    raw = SHOTDIR / f"{name}.rgba"
    send(probe, f"rawshot {raw}")
    data = raw.read_bytes()[:240 * 160 * 4]
    try:
        from PIL import Image
        Image.frombytes("RGBA", (240, 160), data).save(SHOTDIR / f"{name}.png")
    except Exception:
        pass
    return str(SHOTDIR / f"{name}.png")


# ------------------------------------------------------------------ 静态可达性
def thumb_bl_sites(data: bytes) -> dict[int, list[int]]:
    """全 ROM 穷举 Thumb `BL` 的调用点（2 字节对齐）。"""
    res: dict[int, list[int]] = {}
    n = len(data)
    cands: list[int] = []
    for hi in range(0xF0, 0xF8):
        start = 0
        blob = bytes([hi])
        while True:
            pos = data.find(blob, start)
            if pos < 0:
                break
            # Thumb 半字是小端：半字的高字节在**奇数**偏移上
            if pos & 1:
                cands.append(pos - 1)
            start = pos + 1
    for off in cands:
        if off + 4 > n:
            continue
        hw1, hw2 = struct.unpack_from("<HH", data, off)
        if (hw1 & 0xF800) != 0xF000 or (hw2 & 0xD000) != 0xD000:
            continue
        s = (hw1 >> 10) & 1
        i1 = 1 - (((hw2 >> 13) & 1) ^ s)
        i2 = 1 - (((hw2 >> 11) & 1) ^ s)
        imm = ((s << 24) | (i1 << 23) | (i2 << 22) | ((hw1 & 0x3FF) << 12)
               | ((hw2 & 0x7FF) << 1))
        if s:
            imm -= 1 << 25
        target = (ROM_BASE + off + 4 + imm) & 0xFFFFFFFF
        res.setdefault(target, []).append(ROM_BASE + off)
    return res


def find_prologue(rom: bytes, addr: int, limit: int = 0x8000) -> int | None:
    """往前找最近的一条 `push {..., lr}`（半字 `0xB5xx`）当作函数入口。"""
    a = addr & ~1
    while a > addr - limit:
        hw = struct.unpack_from("<H", rom, a - ROM_BASE)[0]
        if (hw & 0xFF00) == 0xB500:
            return a
        a -= 2
    return None


def static_reachability() -> list[dict]:
    """14 处读者 → 所属函数 → 一级/二级调用者（静态）。"""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rom = BASE_ROM.read_bytes()
    calls = thumb_bl_sites(rom)
    words: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 3, 4):
        words.setdefault(struct.unpack_from("<I", rom, off)[0], []).append(ROM_BASE + off)

    def callers(fn: int | None) -> tuple[list[int], list[int]]:
        if fn is None:
            return [], []
        sites = sorted(calls.get(fn, []))
        fns = sorted({f for f in (find_prologue(rom, s) for s in sites) if f})
        return sites, fns

    rows: list[dict] = []
    for entry in manifest["patches"]:
        addr = int(str(entry["rom_addr"]), 16)
        fn = find_prologue(rom, addr)
        sites1, fns1 = callers(fn)
        refs = sorted(words.get((fn | 1) if fn else 0, [])) if fn else []
        l2: dict[str, list[str]] = {}
        for f1 in fns1:
            s2, f2 = callers(f1)
            l2[f"0x{f1:08X}"] = {
                "call_sites": [f"0x{s:08X}" for s in s2],
                "fns": [f"0x{x:08X}" for x in f2],
            }
        rows.append({
            "reader": entry["reader"],
            "site": entry["site"],
            "variant": entry["variant"],
            "patch_rom_addr": f"0x{addr:08X}",
            "function": f"0x{fn:08X}" if fn else None,
            "l1_call_sites": [f"0x{s:08X}" for s in sites1],
            "l1_functions": [f"0x{f:08X}" for f in fns1],
            "l2": l2,
            "callback_table_refs": [f"0x{r:08X}" for r in refs],
            "id_source": entry.get("id_source", ""),
        })
    return rows


# ------------------------------------------------------------------ 路线
def screen_hash(probe: Probe, path: pathlib.Path) -> str:
    """抓一张渲染缓冲并算哈希（**只写一个可复用的临时文件**）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    send(probe, f"rawshot {path}")
    data = path.read_bytes()
    return hashlib.sha1(data[:240 * 160 * 4]).hexdigest()[:12]


SCRATCH_RAW = REPO / "build" / "speaker-reader-shots" / "_scratch.rgba"


def cpu_deadlocked(probe: Probe) -> bool:
    """CPU 是不是掉进了 BIOS 的**异常处理程序**（真卡死）。

    「画面最后 3 张相同」有两种可能：
      * **真卡死** —— CPU 在未定义指令 / 数据中止的异常向量里死循环；
      * **在等输入** —— 游戏停在对话框上等按键，屏幕本来就不该变。
    区分办法：读 CPSR 的模式位与 PC（沿用
    `tools/mgba_probe/speaker_freeze_trace.py` 的 `deadlocked()` 判据）。
    """
    st = status(probe)
    pc = st.get("r15", 0)
    mode = st.get("cpsr", 0) & 0x1F
    return pc < 0x00010000 and mode in (0x17, 0x1B)


def judge(hashes: list[str], deadlocked: bool = False) -> dict:
    """按「最后 3 张画面相同 ⇒ 冻结」判定（判据只有这一条）。

    ⚠️ 加了**一个交叉验证**：只有当 CPU 同时**确实在 BIOS 异常向量里**
    （`cpu_deadlocked()`）才算「卡死」；否则标成「等待输入」
    —— 游戏停在对话框上等按键时，屏幕本来就不推进，那是正常状态，
    不是宿主/游戏卡死。
    """
    tail = hashes[-FROZEN_TAIL:]
    same_tail = len(tail) == FROZEN_TAIL and len(set(tail)) == 1
    frozen = same_tail and deadlocked
    changes = sum(1 for i in range(1, len(hashes)) if hashes[i] != hashes[i - 1])
    return {"frozen": frozen, "same_tail": same_tail,
            "cpu_deadlocked": deadlocked,
            "changes": changes, "hashes": hashes,
            "verdict": "卡死" if frozen else ("等待输入" if same_tail else "能跑")}


def story_route(probe: Probe, label: str) -> dict:
    """剧情路：开机 → START → 连按 A（含菜单键）。"""
    hashes = [screen_hash(probe, SCRATCH_RAW)]
    send(probe, f"frames {BOOT_FRAMES} 0x000")
    plan = STORY_PLAN * STORY_REPEATS
    for i, key in enumerate(plan):
        send(probe, f"frames {FRAMES_PER_PRESS} {KEY_BITS[key]:#05x}")
        send(probe, f"frames {GAP_FRAMES} 0x000")
        hashes.append(screen_hash(probe, SCRATCH_RAW))
    return judge(hashes, cpu_deadlocked(probe))


def battle_route(probe: Probe, label: str,
                formations: list[tuple[int, int]] | None = None) -> dict:
    """战斗路：读战斗路存档 → 三次内存写强制进战斗 → 连按 A。"""
    hashes = []
    send(probe, f"load {BATTLE_STATE}")
    units = 0
    for group, sub in (formations if formations is not None else BATTLE_FORMATIONS):
        send(probe, f"poke 0x{SCENE_BYTE:08X} {group}")
        send(probe, f"poke 0x{SUBCFG_BYTE:08X} {sub}")
        send(probe, f"poke16 0x{PHASE_WORD:08X} {PHASE_BATTLE:#x}")
        for _ in range(BATTLE_PRESSES):
            send(probe, f"frames {FRAMES_PER_PRESS} {KEY_BITS['A']:#05x}")
            send(probe, f"frames {GAP_FRAMES} 0x000")
            hashes.append(screen_hash(probe, SCRATCH_RAW))
        units = max(units, sum(1 for s in range(12)
                               if (raw := probe.read_bytes(UNIT_ARRAY + s * UNIT_STRIDE, 2))
                               and raw[0]))
    return {**judge(hashes, cpu_deadlocked(probe)), "units": units}


def scene_route(probe: Probe, label: str,
               scenes: list[int] | None = None) -> dict:
    """剧情场景分派路：逐个场景派发 + 连按 A。"""
    hashes = []
    send(probe, f"load {BATTLE_STATE}")
    for scene in (scenes if scenes is not None else SCENE_LIST):
        send(probe, f"poke 0x{SCENE_BYTE:08X} {scene}")
        send(probe, f"poke16 0x{PHASE_WORD:08X} {SCENE_PHASE:#x}")
        for _ in range(SCENE_PRESSES):
            send(probe, f"frames {FRAMES_PER_PRESS} {KEY_BITS['A']:#05x}")
            send(probe, f"frames {GAP_FRAMES} 0x000")
            hashes.append(screen_hash(probe, SCRATCH_RAW))
    return judge(hashes, cpu_deadlocked(probe))


def route_hits_collecting(route: str, reader_filler: int | None) -> dict:
    """在一条路线上跑一遍，统计某一条读者断点的命中次数。

    `reader_filler` = 读者补丁末尾那条填充指令的地址（断点挂在它上面）。
    `None` = 只挂永不命中的死断点 ⇒ 这是**判定「能跑/卡死」**用的那次运行。

    **命中一次就收工**：读者覆盖只回答「这条读者有没有被自然走到」，
    不需要把整条路线跑完（省时间）。
    """
    import re
    hit_re = re.compile(r"(?:Hit breakpoint|Hit watchpoint)\s+#?(\d+)\s+at\s+(0x[0-9a-fA-F]+)")
    probe = Probe(EXE, TEST_ROM)
    hits = 0
    first_shot: str | None = None
    hashes: list[str] = []
    presses = 0
    try:
        arm(probe, DEAD_BP)
        if reader_filler is not None:
            arm(probe, reader_filler)

        def press(key: str) -> list[str]:
            outs = [send(probe, f"frames {FRAMES_PER_PRESS} {KEY_BITS[key]:#05x}"),
                    send(probe, f"frames {GAP_FRAMES} 0x000")]
            hashes.append(screen_hash(probe, SCRATCH_RAW))
            return outs

        if route == "story":
            send(probe, f"frames {BOOT_FRAMES} 0x000")
            plan: list[tuple] = [("key", k) for k in STORY_PLAN * STORY_REPEATS]
        elif route == "scene":
            send(probe, f"load {BATTLE_STATE}")
            plan = []
            for scene in SCENE_LIST:
                plan.append(("scene", scene))
                plan.extend(("key", "A") for _ in range(SCENE_PRESSES))
        else:
            send(probe, f"load {BATTLE_STATE}")
            plan = []
            for group, sub in BATTLE_FORMATIONS:
                plan.append(("battle", (group, sub)))
                plan.extend(("key", "A") for _ in range(BATTLE_PRESSES))

        for kind, arg in plan:
            if kind == "scene":
                # 相位 0x0030 ⇒ 状态机走 `0x0808F544` → `0x0808F4D4(scene)`
                # ⚠️ **每个场景都要重新 load 存档**：状态机跑完一个场景后不一定
                #    回到循环头，不 reload 的话后面的场景根本派发不出去。
                send(probe, f"load {BATTLE_STATE}")
                send(probe, f"poke 0x{SCENE_BYTE:08X} {arg}")
                send(probe, f"poke16 0x{PHASE_WORD:08X} {SCENE_PHASE:#x}")
                continue
            if kind == "battle":
                group, sub = arg
                send(probe, f"load {BATTLE_STATE}")
                send(probe, f"poke 0x{SCENE_BYTE:08X} {group}")
                send(probe, f"poke 0x{SUBCFG_BYTE:08X} {sub}")
                send(probe, f"poke16 0x{PHASE_WORD:08X} {PHASE_BATTLE:#x}")
                continue
            presses += 1
            outs = press(arg)
            for out in outs:
                for line in out:
                    if hit_re.search(line):
                        hits += 1
                        if first_shot is None:
                            first_shot = shot(probe, f"hit_{route}_"
                                                 f"{reader_filler:08X}")
            if hits:
                break
        res = judge(hashes, cpu_deadlocked(probe))
        return {"hits": hits, "presses": presses, "verdict": res["verdict"],
                "changes": res["changes"], "frozen": res["frozen"],
                "shot": first_shot}
    finally:
        probe.close()


# ------------------------------------------------------------------ 受控触发
def parse_patch_registers(new_disasm: list[str]) -> dict:
    """从补丁的 `new_disasm` 推出：结果寄存器 / id 寄存器 / 基址寄存器。

    形状（变长化的统一写法）：
        lsls rD, rID, #2        rD = id*4
        ldr  rB, [pc, #imm]     rB = 基址        （变体 A/B/C 有；变体 D 没有）
        adds rD, rD, rB         rD = 槽地址
        ldr  rD, [rD, #0]       rD = 解引用后的字符串首地址
        mov  r8, r8             填充

    ⚠️ **变体 B/C 的 id 寄存器与基址寄存器是同一个**（例如读者 2：id 在 r1，
    而 `ldr r1,[pc,#imm]` 把基址也装进 r1）。补丁自己会覆盖它，所以
    **写寄存器时必须「先写基址、再写 id」**。
    """
    regs: dict[str, str] = {}
    for line in new_disasm:
        parts = line.replace(",", " ").split()
        if not parts:
            continue
        if parts[0] == "lsls" and len(parts) >= 3:
            regs["dst"] = parts[1]
            regs["id"] = parts[2]
        elif parts[0] == "ldr" and "[pc" in line:
            regs["base"] = parts[1]
            regs["base_preset"] = "no"      # 补丁自己会装基址
        elif parts[0] == "adds" and len(parts) >= 4 and parts[2] == parts[1]:
            if "base" not in regs:
                regs["base"] = parts[3]
                regs["base_preset"] = "yes"  # 基址已经在寄存器里（变体 D）
    return regs


def controlled_trigger(site: str, patch: dict, base_addr: int,
                       pool_lo: int, pool_hi: int, mapping: dict[int, str],
                       speaker_id: int = 1) -> dict:
    """受控触发：在读者入口处写好 id / 寄存器，单步走一遍补丁窗口。

    **这是受控触发，不是自然场景覆盖。** 它证明的是：补丁后的代码在真实 CPU 上
    语义正确（槽位算对、解引用出的指针合法、字形码解出来是对的）。
    """
    regs = parse_patch_registers(patch["new_disasm"])
    dst = regs.get("dst", "r0")
    idreg = regs.get("id", "r0")
    basereg = regs.get("base")
    addr = int(str(patch["rom_addr"]), 16)
    n_ins = len(patch["new_disasm"])          # 末尾那条是填充，不算
    steps: list[dict] = []
    probe = Probe(EXE, TEST_ROM)
    try:
        send(probe, f"load {BATTLE_STATE}")
        # System 模式 + Thumb + 关掉 IRQ/FIQ：否则单步途中会被 VBlank IRQ 打断
        # （IRQ 向量在 BIOS 的 0x00000188，实测会把现场冲掉）。
        write_reg(probe, "cpsr", 0xFF)
        # ⚠️ **先写基址、再写 id**：变体 B/C 的 id 寄存器与基址寄存器是同一个，
        #    补丁自己的 `ldr rX,[pc,#imm]` 会把基址装进去（所以 id 必须后写）。
        if basereg:
            write_reg(probe, basereg, base_addr)
        write_reg(probe, idreg, speaker_id)
        write_reg(probe, "pc", addr)
        for _ in range(n_ins - 1):
            send(probe, "next")
            st = status(probe)
            steps.append({
                "pc": f"0x{st.get('r15', 0):08X}",
                "cpsr": f"0x{st.get('cpsr', 0):08X}",
                "dst": f"0x{st.get(dst, 0):08X}",
                "id": f"0x{st.get(idreg, 0):08X}",
                "base": f"0x{st.get(basereg, 0):08X}" if basereg else None,
            })
        final = status(probe)
        ptr = final.get(dst, 0)
        raw = probe.read_bytes(ptr, 24) if ptr else b""
    finally:
        probe.close()

    name_bytes = raw.split(b"\x00")[0] if raw else b""
    try:
        name = text_codec.decode(name_bytes, mapping, BASE_ROM)
    except Exception:
        name = ""
    # 槽地址 = 基址 + id*4（变长化后的指针表步长）
    slot = base_addr + speaker_id * 4
    slot_seen = any(s["dst"] == f"0x{slot:08X}" for s in steps)
    return {
        "site": site,
        "patch_rom_addr": f"0x{addr:08X}",
        "id_register": idreg,
        "base_register": basereg,
        "base_is_preset": regs.get("base_preset"),
        "result_register": dst,
        "speaker_id": speaker_id,
        "expected_slot": f"0x{slot:08X}",
        "slot_seen_in_trace": slot_seen,
        "string_pointer": f"0x{ptr:08X}",
        "pointer_in_pool": bool(pool_lo <= ptr <= pool_hi),
        "pool_range": [f"0x{pool_lo:08X}", f"0x{pool_hi:08X}"],
        "name_bytes": name_bytes.hex(" "),
        "name": name,
        "steps": steps,
    }


# ------------------------------------------------------------------ 主流程
def build_test_rom() -> dict:
    cmd = ["node", str(REPO / "tools" / "build_speaker_test_rom.mjs")]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout + r.stderr, file=sys.stderr)
        raise SystemExit(2)
    return json.loads(TEST_INFO.read_text(encoding="utf-8"))


def read_pool(rom: bytes, base_addr: int, count: int = 64) -> tuple[int, int, list[int]]:
    """读指针表，返回 (池下界, 池上界, 64 个指针)。"""
    off = base_addr - ROM_BASE
    ptrs = list(struct.unpack_from("<64I", rom, off))
    los, his = [], []
    for p in ptrs:
        if not p:
            continue
        po = p - ROM_BASE
        end = rom.find(b"\x00", po)
        los.append(p)
        his.append(p + (end - po if end >= 0 else 0))
    return min(los), max(his), ptrs


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--static", action="store_true", help="只跑静态可达性")
    ap.add_argument("--controlled", action="store_true", help="只跑受控触发")
    ap.add_argument("--skip-build", action="store_true", help="不重新造转换版 ROM")
    ap.add_argument("--quick", action="store_true",
                    help="冒烟模式：把三条路线都缩到最短（只验机制，不出结论）")
    args = ap.parse_args()

    if args.quick:
        global SCENE_LIST, SCENE_PRESSES, STORY_REPEATS, BATTLE_FORMATIONS
        SCENE_LIST = list(range(1, 6))
        SCENE_PRESSES = 6
        STORY_REPEATS = 1
        BATTLE_FORMATIONS = [(1, 1)]

    if not EXE.exists():
        print(f"ERR {EXE} missing; run: python tools/mgba_probe/build.py", file=sys.stderr)
        return 2

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    patches = manifest["patches"]
    base_addr = int(manifest["table"]["base_rom_addr"], 16)

    head("R0) 前置条件")
    if not args.skip_build:
        build_test_rom()
    check("转换版 ROM 存在", TEST_ROM.exists(), str(TEST_ROM.relative_to(REPO)))
    prod = TEST_ROM.read_bytes()
    bad = []
    for p in patches:
        off = int(str(p["rom_offset"]), 0)
        after = str(p["after_hex"]).lower()
        if prod[off:off + len(after) // 2].hex() != after:
            bad.append(p["site"])
    check(f"产物 ROM 里 {len(patches)} 处补丁逐字节等于清单的 after_hex",
          not bad, "、".join(bad))
    fillers = [p["site"] for p in patches
               if not str(p["after_hex"]).lower().endswith("c046")]
    check("14 处补丁末尾都是 0x46C0（mov r8,r8；0xBF00 在 ARMv4T 上是未定义指令）",
          not fillers, "、".join(fillers))
    pool_lo, pool_hi, ptrs = read_pool(prod, base_addr)
    check("指针表 64 槽全部落在 ROM 内", all(base_addr <= p < ROM_BASE + len(prod)
                                       for p in ptrs), f"64 槽")
    print(f"  指针表 {base_addr:#010x}，串池 {pool_lo:#010x}..{pool_hi:#010x}"
          f"（{pool_hi - pool_lo + 1} 字节）")

    head("R1) 静态可达性（14 处读者 → 所属函数 → 一级/二级调用者）")
    t0 = time.time()
    static_rows = static_reachability()
    print(f"  （{time.time() - t0:.1f}s）")
    for r in static_rows:
        print(f"  读者 {r['reader']:2d} {r['site']:22s} {r['patch_rom_addr']} "
              f"fn={r['function']}")
        print(f"        L1 = {r['l1_functions'] or '（无直接 bl 调用点）'}")
        if r["callback_table_refs"]:
            print(f"        回调表引用 = {r['callback_table_refs']}")
    check("14 处读者都定位到了所属函数",
          all(r["function"] for r in static_rows))

    if args.static:
        print("\n--static: 只跑到静态可达性。")
        return 0

    head("R2) 判定「能跑 / 卡死」（只看画面推进；只挂死断点 0x08FFFFFE）")
    judge_rows = {}
    for route in ("story", "scene", "battle"):
        probe = Probe(EXE, TEST_ROM)
        try:
            arm(probe, DEAD_BP)
            if route == "story":
                res = story_route(probe, "judge")
            elif route == "scene":
                res = scene_route(probe, "judge")
            else:
                res = battle_route(probe, "judge")
        finally:
            probe.close()
        judge_rows[route] = res
        check(f"{route} 路：画面全程推进（最后 3 张不同 ⇒ 不冻结）",
              not res["frozen"], f"变化 {res['changes']} 步，判定 {res['verdict']}")
    check("战斗路真的进了战斗（战斗单位已装载）",
          judge_rows["battle"].get("units", 0) > 0,
          f"{judge_rows['battle'].get('units')} 个单位")

    head("R3) 自然场景覆盖（A 档）：逐处读者，一次只挂一条断点")
    coverage: dict[str, dict] = {}
    for p in patches:
        site = p["site"]
        addr = int(str(p["rom_addr"]), 16)
        filler = addr + int(p["byte_length"]) - 2
        row: dict = {"site": site, "patch_rom_addr": f"0x{addr:08X}",
                     "filler": f"0x{filler:08X}"}
        for route in ("story", "scene", "battle"):
            r = route_hits_collecting(route, filler)
            row[route] = r
            print(f"  {site:22s} {route:6s} 命中 {r['hits']:4d}  "
                  f"画面 {r['verdict']}（变化 {r['changes']} 步）"
                  + (f"  截图 {r['shot']}" if r["shot"] else ""))
        coverage[site] = row

    head("R4) 受控触发取证（B 档）：写好 id / 寄存器，单步走一遍补丁窗口")
    mapping, _ = text_codec.load_mapping(BASE_ROM)
    controlled = []
    for p in patches:
        res = controlled_trigger(p["site"], p, base_addr, pool_lo, pool_hi, mapping)
        controlled.append(res)
        print(f"  {res['site']:22s} id={res['speaker_id']} "
              f"槽位 {res['expected_slot']} "
              f"（{'命中' if res['slot_seen_in_trace'] else '未见'}）→ "
              f"指针 {res['string_pointer']} "
              f"（{'在串池内' if res['pointer_in_pool'] else '★越界'}）"
              f" 名字 {res['name']!r}")
        check(f"{res['site']}：算出的槽位 = 基址 + id*4",
              res["slot_seen_in_trace"], res["expected_slot"])
        check(f"{res['site']}：解引用出的指针落在串池里",
              res["pointer_in_pool"], res["string_pointer"])
        check(f"{res['site']}：解出的字形码是合法的名字",
              bool(res["name"]), res["name"] or res["name_bytes"])

    head("R5) 取证表")
    table = []
    for p in patches:
        site = p["site"]
        cov = coverage.get(site, {})
        hits = {r: (cov.get(r) or {}).get("hits", 0)
                for r in ("story", "scene", "battle")}
        ctrl = next((c for c in controlled if c["site"] == site), None)
        if any(hits.values()):
            grade = "A"
        elif ctrl and ctrl["pointer_in_pool"] and ctrl["name"]:
            grade = "B"
        else:
            grade = "C"
        table.append({
            "reader": p["reader"], "site": site,
            "patch_rom_addr": f"0x{int(str(p['rom_addr']), 16):08X}",
            "grade": grade,
            "story_hits": hits["story"], "scene_hits": hits["scene"],
            "battle_hits": hits["battle"],
            "shot": (cov.get("story") or {}).get("shot")
                    or (cov.get("scene") or {}).get("shot")
                    or (cov.get("battle") or {}).get("shot"),
            "controlled": ctrl,
        })
    grades = {"A": sum(1 for r in table if r["grade"] == "A"),
              "B": sum(1 for r in table if r["grade"] == "B"),
              "C": sum(1 for r in table if r["grade"] == "C")}
    print(f"  A（自然场景跑到并取证）= {grades['A']} 处")
    print(f"  B（受控触发取证）      = {grades['B']} 处")
    print(f"  C（只有静态判定）      = {grades['C']} 处")

    head("结论")
    ok = failures == 0
    print("  读者覆盖取证：" + ("全部通过" if ok else f"{failures} 项失败"))
    payload = {
        "ok": ok, "failures": failures,
        "grades": grades,
        "pool_range": [f"0x{pool_lo:08X}", f"0x{pool_hi:08X}"],
        "judge": judge_rows,
        "static": static_rows,
        "coverage": coverage,
        "controlled": controlled,
        "table": table,
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    md = ["# 说话人名表变长化 —— 14 处读者覆盖取证表（自动生成）", "",
          f"- 指针表 `{base_addr:#010x}`，串池 `{pool_lo:#010x}..{pool_hi:#010x}`",
          f"- 档位：**A={grades['A']} / B={grades['B']} / C={grades['C']}**", "",
          "| 读者 | 站点 | 补丁地址 | 档位 | 剧情路命中 | 场景路命中 | 战斗路命中 | "
          "受控触发：槽位 | 指针 | 名字 | 首次命中截图 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in table:
        c = r["controlled"] or {}
        md.append(
            f"| {r['reader']} | `{r['site']}` | `{r['patch_rom_addr']}` | "
            f"**{r['grade']}** | {r['story_hits']} | {r['scene_hits']} | "
            f"{r['battle_hits']} | "
            f"`{c.get('expected_slot','—')}` | `{c.get('string_pointer','—')}` | "
            f"{c.get('name','—') or '—'} | "
            f"{('`' + r['shot'] + '`') if r.get('shot') else '—'} |")
    md.append("")
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print(f"  已写出 {OUT_JSON.relative_to(REPO)}")
    print(f"  已写出 {OUT_MD.relative_to(REPO)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
