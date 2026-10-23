#!/usr/bin/env python3
"""逐指令级定位：剧情 VM 到底死在哪一条指令。

问题
----
「说话人名表变长化」转换后的 ROM（`build/sp-bisect-all.gba`）会卡死。
本轮已经定位到：**CPU 死在 op 0x08 handler 补丁末尾的填充指令 `nop`（`0xBF00`）上**
—— `0xBF00` 在 ARMv4T（GBA 的 ARM7TDMI）上是**未定义指令**，不是 NOP。
详见 `notes/evidence/speaker-name-freeze-trace-20261023.md`。

本工具回答 5 个问题：

1. **CPU 死在哪一条**（逐条断点的命中情况 + 冻结现场的单步解剖 + PC 直方图）。
2. 停住时 r0..r15 / sp / lr / **CPSR**（含 Thumb 位 T 与模式位）各是多少。
3. **`sp` 什么时候变成 0**、**`lr` 是哪来的**。
4. **r1 的解引用链**（`--deref`）：一条指令被执行多遍时，每遍 r1 变成什么。
5. **改法验证**（`--fix-nop`）：把 14 处补丁末尾的 `0xBF00` 换成 ARMv4T 合法的
   `0x46C0`（`mov r8, r8`），跑 A/B 对照。

方法纪律
--------
* **一次只下一条断点**（外加一个永远不会命中的 `0x08FFFFFE`）。
  多个断点会互相污染。
* **判定「能跑 / 卡死」只看画面推进**（每按一次 A 截一张 mGBA 渲染缓冲，
  比相邻两张的哈希；最后 3 张相同 ⇒ 卡死）。断点只用来取寄存器快照，**不参与判定**。
* **mGBA 的断点是「软件断点」**：它把目标指令原地改成 `BE00: bkpt`，
  命中后恢复原指令再执行一遍。
  ⇒ 命中后如果立刻把断点重新挂回同一地址，那条指令会被**反复执行**，
  r1 会凭空多解几层 —— 这是**观测假象**，不是游戏在解引用。
  本工具命中后用 `next` 单步**恰好一条**指令再重新挂断点，并记录每一步的指令文本。

用法
----
    python tools/mgba_probe/speaker_freeze_trace.py                    # 默认 6 条指令 + 干净基线
    python tools/mgba_probe/speaker_freeze_trace.py --addr 0x08097A12  # 只查一条
    python tools/mgba_probe/speaker_freeze_trace.py --clean-only       # 只跑干净基线
    python tools/mgba_probe/speaker_freeze_trace.py --autopsy          # 冻结现场单步解剖
    python tools/mgba_probe/speaker_freeze_trace.py --fix-nop          # 改 nop 的 A/B 验证
    python tools/mgba_probe/speaker_freeze_trace.py --deref 6 --cpsr   # 解引用链 + CPSR

产物
----
    build/trace_freeze_report.json   机器可读的逐次结果
    build/trace_freeze_report.md     自动生成的表（报告直接引用它）
    build/trace_fixnop.gba           --fix-nop 生成的对照 ROM

依据：notes/evidence/speaker-name-patch-bisect-20261023.md
      notes/evidence/speaker-name-freeze-trace-20261023.md
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import pathlib
import re
import struct
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from tools.mgba_probe.story_vm_capture import KEY_BITS, Probe  # noqa: E402

PROBE_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
DEFAULT_ROM = REPO / "build" / "sp-bisect-all.gba"
BASE_ROM = REPO / "rom" / "base.gba"
PATCH_MANIFEST = REPO / "tools" / "data" / "speaker_name_code_patches.json"

ROM_BASE = 0x08000000

# 补丁窗口（转换版）：
#   0x08097A0C  lsls r1, r0, #2
#   0x08097A0E  ldr  r4, [pc, #0x30]      ; 字面量槽 0x08097A40 = 0x085A57C4
#   0x08097A10  adds r1, r1, r4
#   0x08097A12  ldr  r1, [r1]
#   0x08097A14  nop          <-- 0xBF00：ARMv4T 上是「未定义指令」（GBA 会炸）
#   0x08097A16  adds r0, r6, #0
#   0x08097A18  bl   0x0806626C           ; 文本渲染器
WINDOW = [0x08097A0C, 0x08097A0E, 0x08097A10, 0x08097A12, 0x08097A14, 0x08097A16]
RENDERER = 0x0806626C

# 挂一个永远不会命中的断点，**逼 `frames` 走 mGBA 的调试器路径**：
# 快速路径(core->runFrame)在游戏「等输入」时会永远不返回（连原版 ROM 也一样），
# 那是宿主的问题，不是游戏卡死。
DEAD_BP = 0x08FFFFFE

BOOT_FRAMES = 1500
FRAMES_PER_PRESS = 30
GAP_FRAMES = 6
PRESSES = 14          # START + 连按 A 多少次
FROZEN_TAIL = 3       # 最后几张图一样 ⇒ 冻结
HIT_CAP = 32          # 单个窗口内最多处理多少次命中（防死循环）
TRACE_HITS = 3        # 前 N 次命中额外问一次「当前指令是啥」（每次都要问太慢）
LOOP_HITS = 3         # 同一个断点在一个窗口里连中这么多次 ⇒ 死循环，收工

HIT_RE = re.compile(r"Hit breakpoint\s+(\d+)\s+at\s+(0x[0-9A-Fa-f]+)")
# mGBA 自己会报告「非法指令」：
#   Hit illegal opcode at 0x08097A14: 0x0000BF00
# 死循环里这条消息会出现**几十万次**（每一次异常入口都会报一次）——
# 它既是**根因的直接证据**，也是「已经死锁」的可靠信号。
ILL_RE = re.compile(r"Hit illegal opcode at\s+(0x[0-9A-Fa-f]+):\s*(0x[0-9A-Fa-f]+)")
STATUS_RE = re.compile(r"(r\d+|cpsr|sp|lr)\s*:\s*([0-9A-Fa-f]+)")

# ARM 处理器模式（ARMv4T）
ARM_MODES = {
    0x10: "User", 0x11: "FIQ", 0x12: "IRQ", 0x13: "Supervisor",
    0x17: "Abort", 0x1B: "Undefined", 0x1F: "System",
}

# 报告里要展示的寄存器
SHOW_REGS = ["r0", "r1", "r2", "r3", "r4", "r6", "r7", "r12", "r13", "r14", "r15"]


# --------------------------------------------------------------------- 小工具
_SEND_SEQ = itertools.count(1)


def send(probe: Probe, command: str) -> list[str]:
    """发一条命令并读回它的输出（**token 保证唯一**，输出**限量保留**）。

    ⚠️ 不要直接用 `story_vm_capture.Probe.send()`：
    1. 它的 token 由「命令文本的 hash + stderr 行数」决定，而 stderr 行数是**由另一个线程
       异步更新**的 ⇒ **同样的命令文本可能拿到同一个 token** ⇒ 上一次 `send()` 会把本次的
       token 读走 ⇒ 下一次 `send()` 永远等不到 token（**挂死**，实测过）。
    2. 它**每读一行就开一个线程**；而死循环里一次 `frames` 会产生 **19 万行**
       （mGBA 每次非法指令都报一行）⇒ 19 万个线程 ⇒ CPU 打满、内存爆掉。

    这里：token 用全局自增序号；读 stdout **直接 readline**（不建线程）；
    只保留前 50 行 + 前 20 行含 `Hit ` 的行。
    """
    token = f"__end_{next(_SEND_SEQ):08d}"
    probe.proc.stdin.write(f"{command}\necho {token}\n")
    probe.proc.stdin.flush()
    lines: list[str] = []
    hits: list[str] = []
    deadline = time.monotonic() + 600
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("probe timed out")
        line = probe.proc.stdout.readline()
        if not line:
            raise EOFError("probe exited")
        line = line.rstrip("\r\n")
        if line == token:
            return lines + hits
        if len(lines) < 50:
            lines.append(line)
        if "Hit " in line and len(hits) < 20:
            hits.append(line)


def arm(probe: Probe, address: int, thumb: bool = True) -> int | None:
    """挂一个断点，返回它的编号。

    `b/t` = 按 Thumb 断点挂。mGBA 的断点是**软件断点**：它把目标指令原地
    改成 `BE00: bkpt`，命中后再恢复原指令执行一遍（见文件头的「方法纪律」）。
    """
    cmd = f"b/t {address:#x}" if thumb else f"b/a {address:#x}"
    for line in send(probe, cmd):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def disarm(probe: Probe, ident: int | None) -> None:
    if ident is not None:
        send(probe, f"delete {ident}")


def hits_in(out: list[str]) -> list[int]:
    """从命令输出里解析出命中的断点地址。"""
    return [int(m.group(2), 16) for m in (HIT_RE.search(l) for l in out) if m]


def status_full(probe: Probe) -> dict[str, int]:
    """读完整 CPU 状态，**包含 CPSR**（`story_vm_capture.Probe.registers()` 会丢掉 cpsr）。"""
    out: dict[str, int] = {}
    for line in send(probe, "status"):
        for m in STATUS_RE.finditer(line):
            out[m.group(1)] = int(m.group(2), 16)
    return out


def decode_cpsr(cpsr: int | None) -> str:
    """把 CPSR 解成 'Thumb/System, I=0' 这样的一行。"""
    if cpsr is None:
        return "—"
    thumb = (cpsr >> 5) & 1
    mode = cpsr & 0x1F
    return (f"{'Thumb' if thumb else 'ARM  '}/{ARM_MODES.get(mode, f'0x{mode:02X}')}"
            f" I={(cpsr >> 7) & 1} F={(cpsr >> 6) & 1}")


def current_instruction(rom: pathlib.Path, pc: int, thumb: bool) -> str:
    """当前要执行的是哪条指令？

    **不**用 mGBA 的 `trace` 命令：它会追一整帧的指令（死循环时输出巨大、极慢）。
    这里直接读 ROM 文件、用 capstone 解码 —— mGBA 的 Thumb PC = 下一条指令地址
    ⇒ 当前指令在 pc-2；ARM PC = 当前指令 + 8 ⇒ 当前指令在 pc-8。
    """
    addr = (pc - 2) if thumb else (pc - 8)
    off = addr - ROM_BASE
    try:
        with rom.open("rb") as fh:
            fh.seek(off)
            raw = fh.read(8)
    except OSError:
        return ""
    if len(raw) < 4:
        return ""
    try:
        import capstone
        mode = capstone.CS_MODE_THUMB if thumb else capstone.CS_MODE_ARM
        md = capstone.Cs(capstone.CS_ARCH_ARM, mode)
        for ins in md.disasm(raw, addr, count=1):
            return f"{ins.bytes.hex()}: {ins.mnemonic} {ins.op_str}"
    except Exception:
        pass
    return raw[:2].hex()


def deadlocked(regs: dict[str, int]) -> bool:
    """CPU 是不是已经掉进 BIOS 的 **未定义指令 / 数据中止** 处理程序？

    剧情 VM 一旦踩到未定义指令（ARMv4T 上 `0xBF00` 就是未定义指令！），
    mGBA 的 BIOS 异常处理程序会**回到出错的那条指令** ⇒ 无限循环
    ⇒ PC 永远待在 BIOS 的异常处理区（mode = 0x1B Undefined / 0x17 Abort）。
    这种状态下**再按 A 只会白等**（死循环里每一帧都要跑满宿主的 2M 步上限，
    一帧 ≈ 19 秒）。

    ⚠️ 只认 0x1B / 0x17：**普通的 IRQ 处理程序（mode = 0x12）也住在 BIOS 区**，
    不能算死锁。
    """
    pc = regs.get("r15", 0)
    cpsr = regs.get("cpsr", 0)
    mode = cpsr & 0x1F
    return pc < 0x00010000 and mode in (0x17, 0x1B)


def fmt(regs: dict[str, int]) -> dict[str, str]:
    return {k: f"0x{v:08X}" for k, v in sorted(regs.items())}


def read_u32(probe: Probe, address: int) -> int | None:
    raw = probe.read_bytes(address, 4)
    if len(raw) != 4:
        return None
    return struct.unpack("<I", raw)[0]


def deref_chain(probe: Probe, value: int, depth: int) -> list[dict]:
    """沿着一个指针值往下解引用，返回每一跳的链。

    用于分辨「游戏真的多解了一层」与「调试器把同一条 ldr 执行了多遍」：
    后者的每一跳都停在**同一条指令**上，而前者的链会走出那条指令。
    """
    chain = []
    cur = value
    for level in range(depth):
        nxt = read_u32(probe, cur)
        chain.append({"level": level, "addr": f"0x{cur:08X}", "value": f"0x{nxt:08X}"
                      if nxt is not None else None})
        if nxt is None:
            break
        cur = nxt
    return chain


# --------------------------------------------------------------------- 一次运行
def run_case(rom: pathlib.Path, bp_addr: int | None, presses: int = PRESSES,
             label: str = "", want_cpsr: bool = False, deref: int = 0) -> dict:
    """跑一遍「START + 连按 A」。

    `bp_addr` = 要挂的那**一条**断点（None = 只挂永远不会命中的死断点 = 干净基线）。

    返回：每一步的屏幕哈希 + CPU 状态（pc/sp/lr/cpsr）、命中次数、
    命中时的寄存器快照与解引用链。
    """
    raw = REPO / "build" / "trace_freeze.rgba"
    raw.parent.mkdir(parents=True, exist_ok=True)
    state: dict = {"addr": bp_addr, "id": None, "stalled": False, "step": "boot"}
    timeline: list[dict] = []
    snaps: list[dict] = []

    probe = Probe(PROBE_EXE, rom)
    try:
        send(probe, f"frames {BOOT_FRAMES} 0x000")
        arm(probe, DEAD_BP)
        if bp_addr is not None:
            state["id"] = arm(probe, bp_addr)

        def capture() -> str:
            send(probe, f"rawshot {raw}")
            data = raw.read_bytes()
            return hashlib.sha1(data[:240 * 160 * 4]).hexdigest()[:12]

        def snapshot(step: str) -> dict[str, int]:
            regs = status_full(probe)
            cpsr = regs.get("cpsr")
            timeline.append({
                "step": step,
                "screen": capture(),
                "pc": f"0x{regs.get('r15', 0):08X}",
                "sp": f"0x{regs.get('r13', 0):08X}",
                "lr": f"0x{regs.get('r14', 0):08X}",
                "cpsr": f"0x{cpsr:08X}" if cpsr is not None else None,
                "state": decode_cpsr(cpsr),
                "r0": f"0x{regs.get('r0', 0):08X}",
                "r4": f"0x{regs.get('r4', 0):08X}",
                "r7": f"0x{regs.get('r7', 0):08X}",
                "regs": fmt(regs),
            })
            return regs

        def advance(cmd: str) -> None:
            """发一条运行命令；若测试断点命中，记录寄存器，单步一条，再挂回去。

            mGBA 的断点是软件断点：命中后那条指令会被**再执行一遍**。
            若立刻把断点挂回同一地址并继续，那条指令会被反复执行
            （r1 一层层多解）—— 那是**观测假象**。
            这里改成：命中后先 `next` 恰好一步（恢复并执行原指令），
            再把断点挂回去，这样每次命中对应**一次真实执行**。

            另外：**同一个断点在一个窗口里连中多次 = 游戏卡在死循环里**
            （BIOS 异常处理程序会回到出错的那条指令）。
            这时立刻收工 —— 死循环里每发一次 frames 都要跑满宿主的 2M 步上限（一帧 ≈ 19 秒）。
            """
            hits_here = 0
            for _ in range(HIT_CAP):
                out = send(probe, cmd)
                ill = ILL_RE.search("\n".join(out))
                hit = hits_in(out)
                for addr in hit:
                    if bp_addr is None or addr != bp_addr:
                        continue
                    hits_here += 1
                    if hits_here > LOOP_HITS:
                        state["deadlocked"] = True
                        state["stopped_early"] = True
                        return
                    regs = status_full(probe)
                    cpsr = regs.get("cpsr")
                    thumb = bool(cpsr is not None and (cpsr >> 5) & 1)
                    insn = ""
                    if len(snaps) < TRACE_HITS:
                        insn = current_instruction(rom, regs.get("r15", 0), thumb)
                    snap = {
                        "step": state["step"],
                        "regs": fmt(regs),
                        "cpsr": f"0x{cpsr:08X}" if cpsr is not None else None,
                        "state": decode_cpsr(cpsr),
                        "instruction": insn,
                        "selected": {k: f"0x{regs.get(k, 0):08X}" for k in SHOW_REGS},
                    }
                    if deref and len(snaps) < TRACE_HITS:
                        snap["deref_chain"] = deref_chain(probe, regs.get("r1", 0), deref)
                    snaps.append(snap)
                if ill:
                    # 「非法指令」= 死循环的根因，也是最可靠的死锁信号
                    # （死循环里每发一次 frames 会产生 19 万行这种消息！）
                    state["illegal_opcode"] = {"addr": ill.group(1),
                                              "word": ill.group(2)}
                    state["deadlocked"] = True
                    state["stopped_early"] = True
                    return
                if not hit:
                    # 死循环里 CPU 待在 BIOS 的异常处理程序中 ⇒ 再等也只是白等
                    # （每发一次 frames 要 27 秒）。
                    if deadlocked(status_full(probe)):
                        state["deadlocked"] = True
                        state["stopped_early"] = True
                    return
                # CPU 已经掉进 BIOS 的未定义指令处理程序 ⇒ 死循环
                # ⇒ 再发 frames 大命令只是白等（一帧 ≈ 19 秒），立刻收工。
                if bp_addr is not None and deadlocked(regs):
                    state["deadlocked"] = True
                    state["stopped_early"] = True
                    return
                # 单步恰好一条指令，再把断点挂回去
                send(probe, "next")
                if bp_addr is not None:
                    disarm(probe, state["id"])
                    state["id"] = arm(probe, bp_addr)
            state["stalled"] = True

        snapshot("boot")
        for i in range(presses + 1):
            key = "START" if i == 0 else "A"
            state["step"] = key if i == 0 else f"A{i}"
            advance(f"frames {FRAMES_PER_PRESS} 0x{KEY_BITS[key]:03X}")
            advance(f"frames {GAP_FRAMES} 0x000")
            # ⚠️ 这里**不要**再发 mGBA 的 `frame` 命令：死循环里「一帧」永远跑不完，
            # `frame` 会一直转（实测每个按键要 18 秒）。`frames` 命令结束时已经
            # 松开按键（`host_main.c::_cmdFrames` 会 `setKeys(core, 0)`），
            # 下一次按 A 照样是干净的按键边沿。
            last_regs = snapshot(state["step"])
            # **一冻结就停**：死循环里每一帧都要跑满宿主的 2M 步上限
            # （一帧 ≈ 19 秒），继续按 A 只是白等 —— 判定只需要知道「冻住了」。
            if len(timeline) >= FROZEN_TAIL:
                tail = [t["screen"] for t in timeline[-FROZEN_TAIL:]]
                if len(set(tail)) == 1:
                    state["stopped_early"] = True
                    break
            if deadlocked(last_regs):
                state["stopped_early"] = True
                state["deadlocked"] = True
                break
            if state.get("deadlocked"):
                break
    finally:
        probe.close()

    screens = [t["screen"] for t in timeline]
    changes = sum(1 for i in range(1, len(screens)) if screens[i] != screens[i - 1])
    # 冻结点 = 最后一段「一直不变」的起点
    frozen_at = None
    for i in range(len(screens) - 1, 0, -1):
        if screens[i] == screens[i - 1]:
            frozen_at = i - 1
        else:
            break
    tail = screens[-FROZEN_TAIL:]
    if state.get("deadlocked"):
        # CPU 已经掉进 BIOS 异常向量 ⇒ 死循环 ⇒ 画面不会再变
        verdict = "卡死"
        if frozen_at is None:
            frozen_at = max(0, len(screens) - 1)
    else:
        verdict = "卡死" if len(set(tail)) == 1 else "能跑"

    return {
        "label": label,
        "rom": str(rom.relative_to(REPO)),
        "breakpoint": f"0x{bp_addr:08X}" if bp_addr is not None else None,
        "hits": len(snaps),
        "stalled": state["stalled"],
        "verdict": verdict,
        "changes": changes,
        "frozen_at": frozen_at,
        "stopped_early": bool(state.get("stopped_early")),
        "illegal_opcode": state.get("illegal_opcode"),
        "timeline": timeline,
        "snapshots": snaps,
        "screen_hashes": screens,
    }


# --------------------------------------------------------------------- 冻结现场解剖
def autopsy(rom: pathlib.Path, presses: int = PRESSES, steps: int = 400,
            want_insn: bool = True) -> dict:
    """冻结现场：单步若干步，统计 PC 直方图 ⇒ CPU 死在哪条指令、死循环长什么样。

    不挂任何断点（除了那个永不命中的死断点），所以看到的就是真实死循环。
    """
    probe = Probe(PROBE_EXE, rom)
    try:
        send(probe, f"frames {BOOT_FRAMES} 0x000")
        arm(probe, DEAD_BP)
        send(probe, f"frames {FRAMES_PER_PRESS} 0x{KEY_BITS['START']:03X}")
        send(probe, f"frames {GAP_FRAMES} 0x000")
        shots: list[str] = []
        for _ in range(presses):
            send(probe, f"frames {FRAMES_PER_PRESS} 0x{KEY_BITS['A']:03X}")
            send(probe, f"frames {GAP_FRAMES} 0x000")
            raw = REPO / "build" / "trace_freeze.rgba"
            send(probe, f"rawshot {raw}")
            shots.append(hashlib.sha1(raw.read_bytes()[:240 * 160 * 4]).hexdigest()[:12])
            # 冻住就别再按 A 了（死循环里一帧要跑满宿主的 2M 步上限）
            if len(shots) >= FROZEN_TAIL and len(set(shots[-FROZEN_TAIL:])) == 1:
                break

        regs = status_full(probe)
        hist: collections.Counter = collections.Counter()
        seq: list[dict] = []
        for _ in range(steps):
            cpsr = regs.get("cpsr", 0)
            thumb = (cpsr >> 5) & 1
            pc = regs.get("r15", 0)
            # 死循环会重复同一串指令 ⇒ 只问前 40 步的指令文本就够看循环结构
            insn = current_instruction(rom, pc, thumb) if (want_insn and len(seq) < 40) else ""
            hist[(f"0x{pc:08X}", decode_cpsr(cpsr))] += 1
            seq.append({"pc": f"0x{pc:08X}", "state": decode_cpsr(cpsr),
                        "sp": f"0x{regs.get('r13', 0):08X}",
                        "lr": f"0x{regs.get('r14', 0):08X}", "instruction": insn})
            send(probe, "next")
            regs = status_full(probe)
        frozen = {
            "pc": f"0x{regs.get('r15', 0):08X}",
            "cpsr": f"0x{regs.get('cpsr', 0):08X}",
            "state": decode_cpsr(regs.get("cpsr")),
            "sp": f"0x{regs.get('r13', 0):08X}",
            "lr": f"0x{regs.get('r14', 0):08X}",
            "regs": fmt(regs),
        }
    finally:
        probe.close()
    return {
        "rom": str(rom.relative_to(REPO)),
        "steps": steps,
        "final": frozen,
        "histogram": [{"pc": pc, "state": state, "count": n}
                      for (pc, state), n in hist.most_common()],
        "sequence": seq[:40],
    }


# --------------------------------------------------------------------- nop 修法验证
NOP_FILLER = bytes.fromhex("c046")      # 0x46C0 = mov r8, r8（ARMv4T 合法、不写标志）


def build_fixed_rom(src: pathlib.Path, dst: pathlib.Path) -> list[dict]:
    """把 14 处补丁末尾的 `0xBF00` 换成 0x46C0，生成对照 ROM。"""
    data = bytearray(src.read_bytes())
    manifest = json.loads(PATCH_MANIFEST.read_text(encoding="utf-8"))
    done = []
    for p in manifest["patches"]:
        off = int(p["rom_addr"], 16) - ROM_BASE        # ROM 地址 -> 文件偏移
        after = bytes.fromhex(p["after_hex"])
        nops = [i for i in range(0, len(after) - 1, 2) if after[i:i + 2] == b"\x00\xbf"]
        for i in nops:
            data[off + i:off + i + 2] = NOP_FILLER
        done.append({"site": p["site"], "addr": p["rom_addr"],
                     "nop_offsets": nops, "patched": len(nops)})
    dst.write_bytes(bytes(data))
    return done


# --------------------------------------------------------------------- 出表
def render_md(cases: list[dict], baseline: dict | None, control: dict | None,
               aut: dict | None, fixcmp: list[dict] | None) -> str:
    lines = ["# 说话人名表转换版：剧情 VM 逐指令断点结果", "",
             f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", "",
             "判定口径：**最后 3 张画面完全相同 = 卡死**（按键不再有反应）；否则 = 能跑。",
             "断点只用于取寄存器快照，**不参与判定**。", ""]
    if baseline:
        lines += [f"* 干净基线（只挂永不命中的 `0x08FFFFFE`）：**{baseline['verdict']}** —— "
                  f"变化 {baseline['changes']} 步，冻结于第 {baseline['frozen_at']} 步", ""]
    if control:
        lines += [f"* 阳性对照（原版 ROM）：**{control['verdict']}** —— "
                  f"变化 {control['changes']} 步，冻结于第 {control['frozen_at']} 步", ""]
    lines += ["| 断点地址 | 命中次数 | 判定 | 变化步数 | 冻结步 | 首次命中时 pc / sp / lr | CPSR | 当前指令 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for c in cases:
        if c["snapshots"]:
            s = c["snapshots"][0]["selected"]
            reg = f"pc={s['r15']} sp={s['r13']} lr={s['r14']}"
            cpsr = c["snapshots"][0].get("state", "—")
            insn = c["snapshots"][0].get("instruction", "") or "—"
        else:
            reg, cpsr, insn = "—", "—", "—"
        lines.append(f"| `{c['breakpoint']}` | {c['hits']} | {c['verdict']} | "
                     f"{c['changes']} | {c['frozen_at']} | {reg} | {cpsr} | `{insn}` |")
    lines.append("")

    ill = [(c["breakpoint"], c.get("illegal_opcode")) for c in cases
           if c.get("illegal_opcode")]
    if ill:
        lines += ["## ⚠️ mGBA 报告的「非法指令」（根因）", "",
                  "| 断点 | 非法指令地址 | 指令字 |", "|---|---|---|"]
        for bp, io in ill:
            lines.append(f"| `{bp}` | `{io['addr']}` | `{io['word']}` |")
        lines += ["", "> `0xBF00` 在 ARMv4T（GBA 的 ARM7TDMI）上是**未定义指令**，不是 NOP。", ""]

    if aut:
        lines += ["## 冻结现场解剖（单步 + PC 直方图）", "",
                  f"* 冻结时：`pc={aut['final']['pc']}` `cpsr={aut['final']['cpsr']}` "
                  f"（{aut['final']['state']}） `sp={aut['final']['sp']}` `lr={aut['final']['lr']}`",
                  f"* 单步 {aut['steps']} 步的 PC 直方图：", ""]
        lines += ["| 次数 | PC | 处理器状态 |", "|---|---|---|"]
        for h in aut["histogram"]:
            lines.append(f"| {h['count']} | `{h['pc']}` | {h['state']} |")
        lines += ["", "单步序列（前 40 步）：", "",
                  "| # | PC | 状态 | sp | lr | 指令 |", "|---|---|---|---|---|---|"]
        for i, s in enumerate(aut["sequence"]):
            lines.append(f"| {i} | `{s['pc']}` | {s['state']} | `{s['sp']}` | "
                         f"`{s['lr']}` | `{s['instruction']}` |")
        lines.append("")

    if fixcmp:
        lines += ["## 修法 A/B 对照（把 14 处补丁末尾的 `0xBF00` 换成 `0x46C0`）", "",
                  "| ROM | 判定 | 变化步数 | 冻结步 | 画面哈希 |", "|---|---|---|---|---|"]
        for row in fixcmp:
            lines.append(f"| `{row['rom']}` | **{row['verdict']}** | {row['changes']} | "
                         f"{row['frozen_at']} | {' '.join(row['hashes'])} |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=pathlib.Path, default=DEFAULT_ROM)
    ap.add_argument("--base-rom", type=pathlib.Path, default=BASE_ROM)
    ap.add_argument("--addr", action="append", type=lambda v: int(v, 0), default=[],
                    help="要挂断点的地址；可重复（每次运行只挂一条）。"
                         "默认 = 补丁窗口的 6 条指令")
    ap.add_argument("--presses", type=int, default=PRESSES)
    ap.add_argument("--clean-only", action="store_true", help="只跑干净基线")
    ap.add_argument("--skip-clean", action="store_true", help="不跑干净基线")
    ap.add_argument("--cpsr", action="store_true", help="每次命中/快照都读 CPSR")
    ap.add_argument("--deref", type=int, default=0, metavar="N",
                    help="命中时沿着 r1 输出 N 跳解引用链")
    ap.add_argument("--autopsy", action="store_true",
                    help="冻结现场单步解剖（死循环的 PC 直方图）")
    ap.add_argument("--autopsy-steps", type=int, default=400)
    ap.add_argument("--fix-nop", action="store_true",
                    help="生成把 14 处补丁末尾 nop 换成 0x46C0 的 ROM 并做 A/B 对照")
    ap.add_argument("--fix-nop-out", type=pathlib.Path,
                    default=REPO / "build" / "trace_fixnop.gba")
    ap.add_argument("--out-json", default="build/trace_freeze_report.json")
    ap.add_argument("--out-md", default="build/trace_freeze_report.md")
    # 先把 stdout 切到 UTF-8：**必须在 argparse 之前**，
    # 否则 `--help` 打印中文/符号时会被 GBK 控制台编码卡死。
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = ap.parse_args()

    addrs = args.addr or WINDOW

    baseline = None
    control = None
    if not args.skip_clean:
        print("run: 干净基线（只挂永不命中的死断点）", flush=True)
        baseline = run_case(args.rom, None, presses=args.presses,
                            label="干净基线：只挂 0x08FFFFFE")
        print(f"  -> {baseline['verdict']} 变化 {baseline['changes']} 步 "
              f"冻结 {baseline['frozen_at']}", flush=True)
        print("run: 阳性对照（原版 ROM，干净基线）", flush=True)
        control = run_case(args.base_rom, None, presses=args.presses,
                           label="阳性对照：原版 ROM")
        print(f"  -> {control['verdict']} 变化 {control['changes']} 步 "
              f"冻结 {control['frozen_at']}", flush=True)

    cases: list[dict] = []
    if not args.clean_only:
        for a in addrs:
            print(f"run: 断点 0x{a:08X}", flush=True)
            c = run_case(args.rom, a, presses=args.presses,
                         label=f"断点 0x{a:08X}", want_cpsr=args.cpsr, deref=args.deref)
            cases.append(c)
            first = c["snapshots"][0] if c["snapshots"] else {}
            sel = first.get("selected", {})
            print(f"  -> 命中 {c['hits']} 次 | {c['verdict']} 变化 {c['changes']} 步 "
                  f"冻结 {c['frozen_at']} | 首次: pc={sel.get('r15')} "
                  f"sp={sel.get('r13')} lr={sel.get('r14')} r0={sel.get('r0')} "
                  f"r1={sel.get('r1')} | {first.get('state', '')} | "
                  f"{first.get('instruction', '')}", flush=True)

    aut = None
    if args.autopsy:
        print("run: 冻结现场解剖（单步）", flush=True)
        aut = autopsy(args.rom, presses=args.presses, steps=args.autopsy_steps)
        print(f"  -> 冻结时 pc={aut['final']['pc']} cpsr={aut['final']['cpsr']} "
              f"({aut['final']['state']}) sp={aut['final']['sp']} lr={aut['final']['lr']}",
              flush=True)
        for h in aut["histogram"][:8]:
            print(f"     {h['count']:5d} x {h['pc']}  {h['state']}", flush=True)

    fixcmp = None
    if args.fix_nop:
        print("run: 修法 A/B（把 14 处补丁末尾的 nop 换成 mov r8, r8）", flush=True)
        done = build_fixed_rom(args.rom, args.fix_nop_out)
        print(f"  改了 {sum(d['patched'] for d in done)} 处 -> {args.fix_nop_out}", flush=True)
        fixcmp = []
        for rom in (args.rom, args.fix_nop_out):
            c = run_case(rom, None, presses=args.presses, label=rom.name)
            fixcmp.append({"rom": rom.name, "verdict": c["verdict"],
                           "changes": c["changes"], "frozen_at": c["frozen_at"],
                           "hashes": c["screen_hashes"]})
            print(f"  -> {rom.name}: {c['verdict']} 变化 {c['changes']} 步 "
                  f"冻结 {c['frozen_at']}", flush=True)

    out = {
        "rom": str(args.rom.relative_to(REPO)),
        "baseline": baseline,
        "control_base_rom": control,
        "cases": cases,
        "autopsy": aut,
        "fix_nop_ab": fixcmp,
    }
    out_json = REPO / args.out_json
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    out_md = REPO / args.out_md
    out_md.write_text(render_md(cases, baseline, control, aut, fixcmp),
                      encoding="utf-8", newline="\n")
    print(f"\nwrote {args.out_json}")
    print(f"wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
