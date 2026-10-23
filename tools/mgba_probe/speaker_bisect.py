#!/usr/bin/env python3
"""补丁级二分：14 处「说话人名表」读者补丁，逐处开关，看哪一处把剧情 VM 卡死。

判定口径（一次跑就得是/否，落在可观测的量上）
------------------------------------------------
**主判据 = 画面还推不推进。**
每按一次 A 就截一张图（mGBA 自己的渲染缓冲，`rawshot`），比相邻两张的哈希：

  * 最后 3 张图**完全相同** ⇒ 按键不再有反应 ⇒ **卡死**
  * 否则 ⇒ 画面还在推进 ⇒ **能跑**

为什么不用「断点 0x08097A1C 命不中」当判据
------------------------------------------
两条实测证据（详见 notes/evidence/speaker-name-patch-bisect-20261023.md §1）：

1. **mGBA 的调试器在断点命中后会把那条指令「再执行一次」才继续**，
   而且会在同一条指令上反复重入。实测：断点挂在 `0x08097A12`（`ldr r1,[r1]`）上时，
   连续三次命中的 r1 分别是「解引用前 / 解引用后 / 解引用两次」。
   ⇒ 判定用的运行里**绝不能挂会破坏上下文的断点**，尤其不能挂
   `0x0806626C`（渲染器入口第一条是 `push {r4,r5,r6,r7,lr}`，多执行一次栈就漂移）。
   ⇒ 也因此，`0x08097A16` 与 `0x08097A1C` 不能同时挂 ——
   **同时挂时 `0x08097A1C` 连原版 ROM 都不命中**，上一轮据此得出的
   「渲染器拿着坏指针进了循环」是**调试器假象**。
2. **`0x08097A1C` 只在剧本正好执行到 op 0x08 时才命中**，而剧本位置会随
   「名字变长了 / 对白行数变了」而漂移。
   而且在转换版 ROM 里，**名字渲染那一次调用根本没有发生**
   （渲染器入口只有 3 次命中，全是对白正文；没有第 4 次名字渲染）。

所以这里保留三个断点当**辅助观测**（`--aux-bp` 才挂），但判定用画面推进。

判定用画面推进还有一个好处：它对「这一处补丁有没有生效」是**敏感**的 ——
名字从「鸣人」变成「鸣人测试」后，名字框那一行的像素就会变。

本轮结论（2026-10-23）
----------------------
* 单独开 #13（读者 12 / `vm_0x08` @ `0x08097A0C`）≡ 全部 14 处一起开；
  全开去掉 #13 ≡ 一处都不开。其余 13 处**单独开 / 去掉都没有任何可观测差别**。
* 但**只转换数据侧（0 处代码补丁）也照样卡死** ⇒ 病灶在数据侧，不在补丁里。
* 等长改名（不触发转换）时 14 处补丁全开 ⇒ 完全正常。

用法
----
    python tools/mgba_probe/speaker_bisect.py --mode base            # 阳性对照（原版 ROM）
    python tools/mgba_probe/speaker_bisect.py --mode single          # 逐处单独开（14 次）
    python tools/mgba_probe/speaker_bisect.py --mode leave-one-out   # 逐处单独关（13/14 次）
    python tools/mgba_probe/speaker_bisect.py --mode all             # 全开 + 只改数据

产物
----
    build/speaker-bisect.json   机器可读的逐次结果
    build/speaker-bisect.md     14 行核心表（报告直接引用它）

依据：notes/evidence/speaker-name-code-patches-20261023.md
      notes/evidence/speaker-names-hypothesis-ledger.md（U5）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from tools.mgba_probe.story_vm_capture import KEY_BITS, Probe  # noqa: E402

PATCHES_JSON = REPO / "tools" / "data" / "speaker_name_code_patches.json"
BUILD_JS = REPO / "tools" / "build_speaker_probe_rom.mjs"
PROBE_EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
BASE_ROM = REPO / "rom" / "base.gba"

# --- 辅助观测用的三个断点（判定不靠它们，见文件头） -------------------------
BP_VM_ENTRY = 0x08097A16   # op 0x08：名字指针算好、准备调渲染器
BP_VM_RETURN = 0x08097A1C  # op 0x08：渲染器返回之后
BP_RENDERER = 0x0806626C   # 文本渲染器入口（任意调用方）

# 挂一个永远不会命中的断点，**逼 `frames` 走调试器路径**：
# 快速路径(core->runFrame)在游戏「等输入」时会永远不返回 —— 连**原版 ROM** 也一样，
# 那是宿主的问题，不是游戏卡死。调试器路径有帧步数上限，能扛住。
DEAD_BP = 0x08FFFFFE

BOOT_FRAMES = 1500
FRAMES_PER_PRESS = 30
GAP_FRAMES = 6
PRESSES = 14          # 连按 A 多少次
FROZEN_TAIL = 3       # 最后几张图一样 ⇒ 冻结

HIT_RE = re.compile(r"Hit breakpoint\s+(\d+)\s+at\s+(0x[0-9A-Fa-f]+)")

TABLE_BASE = 0x085A57C4
NAME_REGION_LO = 0x08500000
NAME_REGION_HI = 0x08600000


# --------------------------------------------------------------------- 清单
def load_patches() -> list[dict]:
    """14 处补丁的清单（带 1..14 的序号）。"""
    data = json.loads(PATCHES_JSON.read_text(encoding="utf-8"))
    out = []
    for i, p in enumerate(data["patches"], start=1):
        out.append({
            "no": i,
            "reader": p["reader"],
            "site": p["site"],
            "variant": p["variant"],
            "rom_addr": p["rom_addr"],
            "rom_offset": p["rom_offset"],
            "offset_int": int(p["rom_offset"], 16),
        })
    return out


# --------------------------------------------------------------------- 造 ROM
def build_rom(sites: list[int] | None, out_rel: str, data_only: bool = False) -> pathlib.Path:
    """造一个 ROM。

    * ``sites`` = None → 14 处补丁一处都不开（只转换数据侧）。
    * ``sites`` = [...] → 只开列出的那几处。

    数据侧（指针表 + 变长串池）**总是**转换：否则测的不是「说话人名表变长化」。
    """
    cmd = ["node", str(BUILD_JS), "--out", out_rel]
    if data_only or not sites:
        cmd.append("--data-only")
    else:
        cmd += ["--sites", ",".join(f"0x{s:x}" for s in sites)]
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(f"构建失败 {out_rel}:\n{res.stdout}\n{res.stderr}")
    return REPO / out_rel


# --------------------------------------------------------------------- 探针
def arm(probe: Probe, address: int) -> int | None:
    for line in probe.send(f"b {address:#x}"):
        if "breakpoint #" in line:
            return int(line.split("#")[1].split()[0])
    return None


def _classify_pointer(value: int) -> str:
    """把一个指针分成几类，给「是池里的合法地址还是垃圾值」用。"""
    if TABLE_BASE <= value < TABLE_BASE + 256:
        return "指针表槽地址"
    if NAME_REGION_LO <= value < NAME_REGION_HI:
        return "名字区（串池/旧内联槽）"
    if 0x08000000 <= value < 0x09000000:
        return "ROM 内（剧本/代码区）"
    if 0x02000000 <= value < 0x04000000:
        return "RAM"
    return "表外/垃圾"


def _raw_to_png(raw_path: pathlib.Path, png_path: pathlib.Path) -> None:
    from PIL import Image
    data = raw_path.read_bytes()
    if len(data) >= 240 * 160 * 4:
        Image.frombytes("RGBA", (240, 160), data[:240 * 160 * 4]).convert("RGB").save(png_path)


def run_probe(rom: pathlib.Path, presses: int = PRESSES, aux_bp: bool = False) -> dict:
    """跑一遍「START + 连按 A」，每按一次截一张图。

    ⚠️ mGBA 的调试器在断点命中后**会把那条指令再执行一次**才继续
    （实测：断点下在 `ldr r1,[r1]` 上时，命中后 r1 会变成「解引用一次」的值，
    再命中一次就变成「解引用两次」的值）。
    所以**判定用的运行里绝不能下会破坏上下文的断点** ——
    尤其不能下在渲染器入口 `0x0806626C`（那里是 `push {r4,r5,r6,r7,lr}`，
    被多执行一次就会让栈漂移，把游戏弄出一个假的卡死）。
    默认只挂一个**永远不会命中**的断点，用来把 `frames` 逼到调试器路径
    （快速路径在游戏「等输入」时会永远不返回，连原版 ROM 也一样）。

    返回：每一步的屏幕哈希、变化次数、冻结点、断点计数、最后一次的截图。
    """
    counts = {bp: 0 for bp in (BP_VM_ENTRY, BP_VM_RETURN, BP_RENDERER)}
    first: dict[int, dict] = {}
    seq: list[dict] = []
    raw = REPO / "build" / "_speaker-bisect.rgba"
    raw.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    probe = Probe(PROBE_EXE, rom)
    try:
        probe.send(f"frames {BOOT_FRAMES} 0x000")
        if aux_bp:
            for bp in (BP_VM_ENTRY, BP_VM_RETURN, BP_RENDERER):
                arm(probe, bp)
        arm(probe, DEAD_BP)

        def capture(step: str) -> str:
            probe.send(f"rawshot {raw}")
            data = raw.read_bytes()
            return hashlib.sha1(data[:240 * 160 * 4]).hexdigest()[:12]

        seq.append({"step": "boot", "screen": capture("boot")})
        for key in ["START"] + ["A"] * presses:
            for window in (f"frames {FRAMES_PER_PRESS} 0x{KEY_BITS[key]:03X}",
                           f"frames {GAP_FRAMES} 0x000"):
                out = probe.send(window)
                hit = None
                for line in out:
                    m = HIT_RE.search(line)
                    if m:
                        hit = int(m.group(2), 16)
                        break
                if hit is None:
                    continue
                counts[hit] = counts.get(hit, 0) + 1
                if hit not in first:
                    regs = probe.registers()
                    entry = {k: f"0x{v:08X}" for k, v in sorted(regs.items())}
                    r1 = regs.get("r1", 0)
                    entry["r1_kind"] = _classify_pointer(r1)
                    entry["r1_bytes"] = probe.read_bytes(r1, 16).hex(" ")
                    first[hit] = entry
                probe.send(f"frames {GAP_FRAMES} 0x000")
                probe.send("frame")
            seq.append({"step": key, "screen": capture(key)})
        probe.send(f"rawshot {raw}")
    finally:
        probe.close()

    last_png = REPO / "build" / f"speaker-bisect-last-{rom.stem}.png"
    _raw_to_png(raw, last_png)
    hashes = [s["screen"] for s in seq]
    changes = sum(1 for i in range(1, len(hashes)) if hashes[i] != hashes[i - 1])
    frozen_at = None
    for i in range(len(hashes) - FROZEN_TAIL, 0, -1):
        if len(set(hashes[i - 1:])) == 1:
            frozen_at = i - 1
        else:
            break
    return {
        "sequence": seq,
        "changes": changes,
        "frozen_at": frozen_at,
        "counts": {f"0x{a:08X}": n for a, n in counts.items()},
        "first": {f"0x{a:08X}": v for a, v in first.items()},
        "seconds": round(time.monotonic() - t0, 2),
        "last_png": str(last_png.relative_to(REPO)),
    }


def judge(result: dict) -> tuple[str, str]:
    """判定：最后 FROZEN_TAIL 张图一样 ⇒ 卡死。"""
    seq = result["sequence"]
    tail = [s["screen"] for s in seq[-FROZEN_TAIL:]]
    steps = [s["step"] for s in seq]
    if len(set(tail)) == 1:
        at = result["frozen_at"]
        where = f"（冻结在第 {at} 步：{steps[at]}）" if at is not None else ""
        return "卡死", f"最后 {FROZEN_TAIL} 张画面完全相同{where}"
    return "能跑", f"画面在 {result['changes']} 步里持续变化，最后 {FROZEN_TAIL} 张各不相同"


# --------------------------------------------------------------------- 主流程
def run_case(label: str, sites: list[int] | None, out_rel: str,
             data_only: bool = False, presses: int = PRESSES,
             aux_bp: bool = False) -> dict:
    rom = build_rom(sites, out_rel, data_only=data_only)
    result = run_probe(rom, presses=presses, aux_bp=aux_bp)
    verdict, why = judge(result)
    return {
        "label": label,
        "sites": ["0x%06x" % s for s in (sites or [])],
        "rom": str(rom.relative_to(REPO)),
        "verdict": verdict,
        "why": why,
        "changes": result["changes"],
        "frozen_at": result["frozen_at"],
        "counts": result["counts"],
        "first": result["first"],
        "sequence": result["sequence"],
        "seconds": result["seconds"],
        "last_png": result["last_png"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", action="append", default=[],
                    choices=["base", "single", "leave-one-out", "all"],
                    help="要跑哪几组；可重复")
    ap.add_argument("--presses", type=int, default=PRESSES)
    ap.add_argument("--aux-bp", action="store_true",
                    help="额外挂三个辅助断点（会破坏上下文，只用于取 r1 观测，"
                         "**不要**用它做判定）")
    ap.add_argument("--out-json", default="build/speaker-bisect.json")
    ap.add_argument("--out-md", default="build/speaker-bisect.md")
    args = ap.parse_args()

    modes = args.mode or ["base", "all", "single", "leave-one-out"]
    patches = load_patches()
    all_sites = [p["offset_int"] for p in patches]
    cases: list[dict] = []

    if "base" in modes:
        t0 = time.monotonic()
        result = run_probe(BASE_ROM, presses=args.presses, aux_bp=args.aux_bp)
        verdict, why = judge(result)
        cases.append({
            "label": "阳性对照：原版 ROM（未转换）",
            "sites": [],
            "rom": str(BASE_ROM.relative_to(REPO)),
            "verdict": verdict, "why": why,
            "changes": result["changes"], "frozen_at": result["frozen_at"],
            "counts": result["counts"], "first": result["first"],
            "sequence": result["sequence"],
            "seconds": round(time.monotonic() - t0, 2),
            "last_png": result["last_png"],
        })

    if "all" in modes:
        cases.append(run_case("全部 14 处一起开（数据侧也转换）", all_sites,
                              "build/sp-bisect-all.gba", presses=args.presses,
                              aux_bp=args.aux_bp))
        cases.append(run_case("只转换数据侧、14 处补丁一处都不开", None,
                              "build/sp-bisect-dataonly.gba", data_only=True,
                              presses=args.presses, aux_bp=args.aux_bp))

    if "single" in modes:
        for p in patches:
            cases.append(run_case(
                f"单独开 #{p['no']}（读者 {p['reader']} / {p['site']}）",
                [p["offset_int"]], f"build/sp-bisect-single-{p['no']:02d}.gba",
                presses=args.presses, aux_bp=args.aux_bp))

    if "leave-one-out" in modes:
        for p in patches:
            rest = [s for s in all_sites if s != p["offset_int"]]
            cases.append(run_case(
                f"全开但去掉 #{p['no']}（读者 {p['reader']} / {p['site']}）",
                rest, f"build/sp-bisect-loo-{p['no']:02d}.gba",
                presses=args.presses, aux_bp=args.aux_bp))

    out_json = REPO / args.out_json
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")

    single = {c["label"].split("#")[1].split("（")[0]: c
              for c in cases if c["label"].startswith("单独开 #")}
    loo = {c["label"].split("#")[1].split("（")[0]: c
           for c in cases if c["label"].startswith("全开但去掉 #")}
    all_case = next((c for c in cases if c["label"].startswith("全部 14 处")), None)
    base_case = next((c for c in cases if c["label"].startswith("阳性对照")), None)
    data_case = next((c for c in cases if c["label"].startswith("只转换数据侧")), None)

    lines = ["# 说话人名表 14 处补丁逐处开关结果", "",
             f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", "",
             "判定口径：**最后 3 张画面完全相同 = 卡死**（按键不再有反应）；否则 = 能跑。",
             "「与其它一起开」= 14 处全开、**单独去掉这一处**（leave-one-out）。", ""]
    for tag, case in (("阳性对照（原版 ROM）", base_case),
                      ("只改数据侧、0 处代码补丁", data_case),
                      ("全部 14 处一起开", all_case)):
        if case:
            lines.append(f"* {tag}：**{case['verdict']}** —— {case['why']}"
                         f"（变化 {case['changes']} 步）")
    lines += ["", "## 逐处结果", "",
              "基线：**只改数据侧（0 处代码补丁）** = 冻结在第 N 步；"
              "**全部 14 处一起开** = 冻结在第 M 步。",
              "单独开的结果若与「只改数据侧」基线一致 ⇒ 这一处补丁对本场景**没有可观测影响**；",
              "「与其它一起开」= 14 处全开、**单独去掉这一处**（leave-one-out）。", "",
              "| # | 补丁位置（ROM 地址 / site） | reader | 单独开 | 与其它一起开 | 判定 | 备注 |",
              "|---|---|---|---|---|---|---|"]
    base_freeze = data_case["frozen_at"] if data_case else None
    for p in patches:
        key = str(p["no"])
        s, l = single.get(key), loo.get(key)
        bad = (s and s["verdict"] == "卡死") or (l and l["verdict"] == "卡死")
        good = (s and s["verdict"] == "能跑") or (l and l["verdict"] == "能跑")
        note = []
        if s:
            note.append(f"单开冻结于第 {s['frozen_at']} 步" if s["frozen_at"] is not None
                        else "单开不冻结")
        if l:
            note.append(f"去掉后冻结于第 {l['frozen_at']} 步" if l["frozen_at"] is not None
                        else "去掉后不冻结")
        # 唯一「有可观测影响」的那一处：单独开的结果与「只改数据侧」基线不同
        standout = (s is not None and base_freeze is not None
                    and s["frozen_at"] != base_freeze)
        verdict = "卡死" if bad else ("能跑" if good else "没测")
        if standout:
            verdict = "卡死 ★有影响"
            note.append("**单独开就与基线不同 ⇒ 这一处是唯一有可观测影响的补丁**")
        lines.append(
            f"| {p['no']} | `{p['rom_addr']}` / {p['site']} | {p['reader']} | "
            f"{s['verdict'] if s else '没测'} | {l['verdict'] if l else '没测'} | "
            f"{verdict} | {'；'.join(note) or '—'} |")
    lines.append("")
    out_md = REPO / args.out_md
    out_md.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for c in cases:
        print(f"{c['verdict']:<4} {c['label']}  变化 {c['changes']:>2} 步  "
              f"冻结 {c['frozen_at']}  [{c['seconds']}s]  {c['counts']}")
    print(f"\nwrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
