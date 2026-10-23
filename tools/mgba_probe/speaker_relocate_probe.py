#!/usr/bin/env python3
"""「指针表搬家」实验：卡死是不是因为那 256 字节指针表占用了旧内联名字表那片地址？

核心问题
--------
上一轮（notes/evidence/speaker-name-patch-bisect-20261023.md）已经证明：
只转换数据侧（写 256 字节指针表 + 串池）、**一处代码补丁都不开**，游戏照样卡死；
再二分数据侧 ⇒ 串池无害，**`0x085A57C4` 处那 256 字节指针表**才是要害。

本轮把指针表**搬到空闲区**，并把 12 个取名读者加载基址的**字面量**改成新基址，
用同一条判据（画面还推不推进）跑一遍：

| 变体 | 指针表位置 | 12 处字面量 | 14 处指令补丁 | 想回答什么 |
|---|---|---|---|---|
| V0 | —（原版 ROM） | — | — | 阳性对照：必须**能跑** |
| V1 | **新基址** | → 新基址 | **全开** | **主问题**：还卡不卡？ |
| V2 | **新基址** | 不动 | 0 处 | 对照：旧读者仍按 `旧基址+id*12` 读**没被动过**的旧内联表 ⇒ 期望**能跑** |
| V3 | **新基址** | → 新基址 | 0 处 | 附带：字面量改了但读者没打补丁 ⇒ 读的是新基址+id*12 的垃圾 |

判据（**与上一轮完全一致**，直接复用 `speaker_bisect.py` 的跑 ROM / 截屏 / 判定代码）
------------------------------------------------------------------------------
每按一次 A 截一张 mGBA 的渲染缓冲（`rawshot`），比相邻两张的哈希：
最后 3 张完全相同 ⇒ 卡死；否则 ⇒ 画面还在推进 ⇒ 能跑。
判定用的运行**只挂一个永远不会命中的断点** `0x08FFFFFE`
（快速路径 `core->runFrame()` 在等输入时会永远不返回，那是宿主的问题）。

新基址
------
`0x085B56E0`（文件偏移 `0x5B56E0`）。理由见 `verify_region()` 的检查结果：
* 原版 ROM 里 `0x5B56E0..0x5B5FFF`（**2,336 字节**）全是 `0xFF`；
* 它是两块压缩图形数据之间的**对齐填充**（前一块以 `00 14` 结束，后一块从 `0x5B6000` 开始）；
* 内容包**没有声称占用**它，ROM 里**没有任何指针**指进它；
* **不在** `0x5DFBEC..0x600000` 那段共享空闲区里 ⇒ 不和串池、剧本搬迁抢地方。

用法
----
    python tools/mgba_probe/speaker_relocate_probe.py                 # 跑 V0/V1/V2/V3
    python tools/mgba_probe/speaker_relocate_probe.py --only v1        # 只跑一个
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from tools.mgba_probe.speaker_bisect import (  # noqa: E402
    PRESSES, judge, run_probe,
)

PATCHES_JSON = REPO / "tools" / "data" / "speaker_name_code_patches.json"
BASE_ROM = REPO / "rom" / "base.gba"

ROM_BASE = 0x08000000
OLD_BASE_FILE = 0x5A57C4
OLD_BASE_ROM = ROM_BASE + OLD_BASE_FILE
NEW_BASE_FILE = 0x5B56E0
NEW_BASE_ROM = ROM_BASE + NEW_BASE_FILE
POOL_FILE = 0x5DFBEC               # 串池起点（编辑器 allocate() 选的那块）
POOL_LEN = 340                    # 上一轮实测：64 条名字共 340 字节
NAME_TEXT = "鸣人测试"             # 让 id 1 的名字变长 ⇒ 触发「内联槽 → 指针表」转换

# 12 个取名读者加载基址的字面量（ROM 地址；文件偏移 = 减 ROM_BASE）
EXPECTED_LITERALS = [
    0x08079108, 0x08081224, 0x08081254, 0x080860C0, 0x08088884, 0x08088E4C,
    0x08089538, 0x0808D338, 0x08090168, 0x08095598, 0x08095DF0, 0x08097A40,
]

# --------------------------------------------------------------------- 造 ROM
# Node 侧的构建脚本（**不写回 pack.json**：基址只在内存里改）。
# 指令补丁**不**在这里打 —— 由 Python 侧按 `speaker_name_code_patches.json` 逐字节打，
# 这样「开关 14 处补丁」和「改 12 处字面量」两件事互不干扰。
MJS_SOURCE = r"""
// 由 tools/mgba_probe/speaker_relocate_probe.py 自动生成（每次运行重写）。
// 只做一件事：在**内存里**把说话人名表转换的基址改掉，然后调 buildRom。
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..');

const { ContentPack } = await import('../rom-editor/js/pack.js');
const { buildRom } = await import('../rom-editor/js/rom.js');

function arg(name, fallback) {
  const at = process.argv.indexOf(name);
  return at >= 0 ? process.argv[at + 1] : fallback;
}
const outPath = arg('--out', 'build/reloc_build.gba');
const base = Number(arg('--base', '0'));
const targetId = Number(arg('--id', '1'));
const newText = arg('--text', '');
// `--text-id N`：把 id N 的**原名**拿来用（用来做「等长但仍进池」的对照）
const textId = arg('--text-id', '');

const rom = new Uint8Array(readFileSync(join(repoRoot, 'rom', 'base.gba')));
const pack = ContentPack.fromJSON(
  JSON.parse(readFileSync(join(repoRoot, 'rom-editor', 'content', 'pack.json'), 'utf8')));
pack.patches = [];

// ★ 本实验的唯一改动：把「内联槽 → 指针表」的基址换成新基址（**只在内存里**）。
pack.conversions.speaker_names.base = base;
// 14 处指令补丁留空：Python 侧按 tools/data/speaker_name_code_patches.json 逐字节打，
// 这样「开关补丁」与「改字面量」两件事互不干扰。
pack.conversions.speaker_names.code_patches = [];

const table = pack.textTable('speaker_names');
const record = table.records.find((r) => r.id === targetId);
if (!record) throw new Error(`speaker_names 里没有 id ${targetId}`);
let text = newText;
if (textId !== '') {
  const other = table.records.find((r) => r.id === Number(textId));
  if (!other) throw new Error(`speaker_names 里没有 id ${textId}`);
  text = other.original_text || other.text;
}
pack.setText(table, record, text || `${record.text}测试`);

const { bytes, report } = buildRom(pack, rom);
if (report.errors.length) {
  console.error('构建失败：');
  for (const e of report.errors) console.error('  ' + e);
  process.exit(1);
}
writeFileSync(join(repoRoot, outPath), Buffer.from(bytes));
console.log(`已写出 ${outPath}（基址 0x${base.toString(16)}）`);
"""


def _mjs_source() -> str:
    return MJS_SOURCE


def build_relocated_rom(out_rel: str, base_file: int = NEW_BASE_FILE,
                        text: str = NAME_TEXT, target_id: int = 1,
                        text_id: int | None = None) -> pathlib.Path:
    """造一个「指针表在 `base_file`」的 ROM（只做数据侧转换，指令补丁留给 Python）。"""
    mjs = REPO / "build" / "reloc_build.mjs"
    mjs.parent.mkdir(parents=True, exist_ok=True)
    mjs.write_text(_mjs_source(), encoding="utf-8", newline="\n")
    cmd = ["node", str(mjs), "--out", out_rel,
           "--base", str(base_file), "--id", str(target_id)]
    if text_id is not None:
        cmd += ["--text-id", str(text_id)]
    else:
        cmd += ["--text", text]
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"构建失败 {out_rel}:\n{res.stdout}\n{res.stderr}")
    return REPO / out_rel


# --------------------------------------------------------------- 后处理：字面量
def load_patch_hexes() -> list[dict]:
    """`speaker_name_code_patches.json` 的原始条目（**带** before_hex/after_hex）。

    `speaker_bisect.load_patches()` 只保留元信息，字节要自己读。
    """
    data = json.loads(PATCHES_JSON.read_text(encoding="utf-8"))
    return data["patches"]


def patch_literals(data: bytearray, new_base_rom: int | None) -> list[str]:
    """把 12 个基址字面量改成 `new_base_rom`（`None` = 不动）。"""
    notes: list[str] = []
    if new_base_rom is None:
        return notes
    for addr in EXPECTED_LITERALS:
        off = addr - ROM_BASE
        old = struct.unpack_from("<I", data, off)[0]
        if old != OLD_BASE_ROM:
            raise RuntimeError(
                f"字面量 0x{addr:08X} 的原值不是 0x{OLD_BASE_ROM:08X}"
                f"（是 0x{old:08X}）—— ROM 与预期不符")
        struct.pack_into("<I", data, off, new_base_rom)
        notes.append(f"0x{addr:08X}: 0x{OLD_BASE_ROM:08X} -> 0x{new_base_rom:08X}")
    return notes


def apply_code_patches(data: bytearray, patches: list[dict]) -> list[str]:
    """按 `speaker_name_code_patches.json` 逐字节打指令补丁（**长度不变**）。"""
    notes: list[str] = []
    for p in patches:
        off = int(p["rom_offset"], 16)
        before = bytes.fromhex(p["before_hex"])
        after = bytes.fromhex(p["after_hex"])
        if len(before) != len(after):
            raise RuntimeError(f"补丁 0x{p['rom_addr']} 长度变了")
        actual = bytes(data[off:off + len(before)])
        if actual != before:
            raise RuntimeError(
                f"补丁 0x{p['rom_addr']}（{p['site']}）的原始字节不匹配："
                f"期望 {before.hex(' ')}，实际 {actual.hex(' ')}")
        data[off:off + len(after)] = after
        notes.append(f"0x{p['rom_addr']} / {p['site']}（读者 {p['reader']}）")
    return notes


# ------------------------------------------------------------------- 自检
def verify_rom(path: pathlib.Path, *, expect_base_rom: int,
               expect_patches: bool, expect_literals: int | None,
               has_pointer_table: bool = True) -> dict:
    """核对造出来的 ROM 是不是「说的那样」—— 结论必须建立在核对过的字节上。"""
    data = path.read_bytes()
    base = BASE_ROM.read_bytes()
    out: dict = {"path": str(path.relative_to(REPO)), "checks": [], "ok": True}

    def check(name: str, cond: bool, detail: str = "") -> None:
        out["checks"].append({"name": name, "ok": bool(cond), "detail": detail})
        if not cond:
            out["ok"] = False

    # 1) 12 处字面量
    lits = {f"0x{a:08X}": f"0x{struct.unpack_from('<I', data, a - ROM_BASE)[0]:08X}"
            for a in EXPECTED_LITERALS}
    want = f"0x{expect_literals:08X}" if expect_literals is not None else None
    if want:
        check("12 处基址字面量", all(v == want for v in lits.values()),
              f"全部 = {want}" if all(v == want for v in lits.values()) else str(lits))
    else:
        check("12 处基址字面量保持原值",
              all(v == f"0x{OLD_BASE_ROM:08X}" for v in lits.values()), str(lits))

    # 2) 14 处指令补丁
    patches = load_patch_hexes()
    want_bytes = "after" if expect_patches else "before"
    bad = []
    for p in patches:
        off = int(p["rom_offset"], 16)
        want = bytes.fromhex(p[f"{want_bytes}_hex"])
        if bytes(data[off:off + len(want)]) != want:
            bad.append(p["rom_addr"])
    check(f"14 处指令补丁 = {want_bytes}_hex", not bad,
          "全部匹配" if not bad else f"不匹配：{bad}")

    # 3) 新基址处是 64 个指向串池的指针
    if has_pointer_table:
        pt = [struct.unpack_from("<I", data, expect_base_rom - ROM_BASE + 4 * i)[0]
              for i in range(64)]
        in_pool = all(POOL_FILE + ROM_BASE <= v < POOL_FILE + ROM_BASE + POOL_LEN + 0x100
                      for v in pt)
        check("新基址处 64 个指针都指向串池", in_pool,
              f"entry0=0x{pt[0]:08X} entry1=0x{pt[1]:08X} entry44=0x{pt[44]:08X}")

    # 4) 旧内联名字表那 256 字节是否原样保留
    old_intact = bytes(data[OLD_BASE_FILE:OLD_BASE_FILE + 256]) == \
        bytes(base[OLD_BASE_FILE:OLD_BASE_FILE + 256])
    check("旧内联名字表 0x5A57C4..0x5A58C3 原样保留", old_intact,
          "逐字节与原版相同" if old_intact else "已被改写")

    # 5) 串池在 0x5DFBEC，且不与指针表重叠
    if has_pointer_table:
        pool_ok = bytes(data[POOL_FILE:POOL_FILE + 4]) != b"\xff\xff\xff\xff"
        check("串池仍在 0x5DFBEC", pool_ok, data[POOL_FILE:POOL_FILE + 8].hex(" "))
        overlap = not (expect_base_rom - ROM_BASE + 256 <= POOL_FILE
                       or POOL_FILE + POOL_LEN <= expect_base_rom - ROM_BASE)
        check("指针表与串池不重叠", not overlap,
              f"指针表 0x{expect_base_rom - ROM_BASE:06X}.."
              f"0x{expect_base_rom - ROM_BASE + 255:06X} / 串池 0x{POOL_FILE:06X}.."
              f"0x{POOL_FILE + POOL_LEN - 1:06X}")

    # 6) 新基址那 256 字节在**原版 ROM** 里是不是全 0xFF
    ff = all(b == 0xFF for b in base[expect_base_rom - ROM_BASE:
                                    expect_base_rom - ROM_BASE + 256])
    check("新基址那 256 字节在原版 ROM 里全是 0xFF", ff,
          f"0x{expect_base_rom - ROM_BASE:06X}.."
          f"0x{expect_base_rom - ROM_BASE + 255:06X}")

    # 7) 与原版 ROM 的差异区间（给人看的）
    diff = [i for i in range(len(data)) if data[i] != base[i]]
    ranges: list[list[int]] = []
    for i in diff:
        if ranges and ranges[-1][1] == i:
            ranges[-1][1] = i + 1
        else:
            ranges.append([i, i + 1])
    out["diff_ranges"] = [f"0x{s:06X}..0x{e-1:06X} ({e - s}B)" for s, e in ranges]
    return out


def verify_region() -> dict:
    """新基址那块地址的安全性核对（写进报告的依据）。"""
    base = BASE_ROM.read_bytes()
    lo, hi = NEW_BASE_FILE, NEW_BASE_FILE + 256
    run_end = lo
    while run_end < len(base) and base[run_end] == 0xFF:
        run_end += 1
    run_start = lo
    while run_start > 0 and base[run_start - 1] == 0xFF:
        run_start -= 1
    # 指向这段的 u32（排除那 12 个已知字面量）
    ptrs = []
    for off in range(0, len(base) - 3):
        v = struct.unpack_from("<I", base, off)[0]
        if ROM_BASE + run_start <= v <= ROM_BASE + run_end - 1:
            ptrs.append((off, v))
    return {
        "run_file_start": f"0x{run_start:06X}",
        "run_file_end": f"0x{run_end - 1:06X}",
        "run_len": run_end - run_start,
        "chosen_file": f"0x{lo:06X}",
        "chosen_rom": f"0x{ROM_BASE + lo:08X}",
        "all_ff_in_base_rom": all(b == 0xFF for b in base[lo:hi]),
        "pointers_into_run": [(f"0x{o:06X}", f"0x{v:08X}") for o, v in ptrs],
        "bytes_before": base[lo - 16:lo].hex(" "),
        "bytes_after": base[run_end:run_end + 16].hex(" "),
    }


# --------------------------------------------------------------------- 主流程
def build_variant(kind: str) -> tuple[pathlib.Path, dict]:
    """造一个变体的 ROM。`kind` ∈ {v0, v1, v2, v3, v4}。"""
    if kind == "v0":
        return BASE_ROM, {"note": "原版 ROM，未做任何改动"}
    out_rel = f"build/reloc_{kind}.gba"
    # v4：名字**等长**（拿 id 2 的原名），但仍然触发转换 ⇒ 名字住在串池里、长度不变
    text_id = 2 if kind == "v4" else None
    rom = build_relocated_rom(out_rel, text_id=text_id)
    data = bytearray(rom.read_bytes())
    literals = patch_literals(data, NEW_BASE_ROM if kind in ("v1", "v3", "v4") else None)
    applied = (apply_code_patches(data, load_patch_hexes())
               if kind in ("v1", "v4") else [])
    rom.write_bytes(bytes(data))
    return rom, {"literal_changes": literals, "code_patches_applied": applied}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", action="append", default=[],
                    choices=["v0", "v1", "v2", "v3", "v4"], help="只跑某几个变体；可重复")
    ap.add_argument("--presses", type=int, default=PRESSES)
    ap.add_argument("--out-json", default="build/reloc_speaker_probe.json")
    ap.add_argument("--out-md", default="build/reloc_speaker_probe.md")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    kinds = args.only or ["v0", "v1", "v2", "v3", "v4"]
    region = verify_region()

    labels = {
        "v0": "V0 阳性对照：原版 ROM（未转换）",
        "v1": "V1 指针表搬家 + 12 处字面量改新基址 + 14 处补丁全开（主问题）",
        "v2": "V2 指针表搬家 + 字面量不动 + 0 处补丁（旧读者仍读没被动过的旧内联表）",
        "v3": "V3 指针表搬家 + 12 处字面量改新基址 + 0 处补丁（附带对照）",
        "v4": "V4 指针表搬家 + 14 处补丁全开 + 名字**等长**（附带对照：名字在池里但长度不变）",
    }

    cases: list[dict] = []
    for kind in kinds:
        rom, how = build_variant(kind)
        expect_literals = NEW_BASE_ROM if kind in ("v1", "v3", "v4") else None
        if kind == "v0":
            expect_literals = OLD_BASE_ROM
        check = verify_rom(rom, expect_base_rom=NEW_BASE_ROM,
                           expect_patches=(kind in ("v1", "v4")),
                           expect_literals=expect_literals,
                           has_pointer_table=(kind != "v0"))
        t0 = time.monotonic()
        result = run_probe(rom, presses=args.presses)
        verdict, why = judge(result)
        cases.append({
            "variant": kind,
            "label": labels[kind],
            "rom": str(rom.relative_to(REPO)),
            "verdict": verdict,
            "why": why,
            "changes": result["changes"],
            "frozen_at": result["frozen_at"],
            "sequence": result["sequence"],
            "seconds": round(time.monotonic() - t0, 2),
            "build": how,
            "verify": check,
        })
        print(f"{verdict:<4} {labels[kind]}")
        print(f"      ROM {rom.relative_to(REPO)}  变化 {result['changes']} 步  "
              f"冻结 {result['frozen_at']}  [{cases[-1]['seconds']}s]")
        print(f"      自检：{'全部通过' if check['ok'] else '★有不通过项'}")
        for c in check["checks"]:
            if not c["ok"]:
                print(f"        ✗ {c['name']}：{c['detail']}")
        sys.stdout.flush()

    out_json = REPO / args.out_json
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(
        {"region": region, "new_base_file": f"0x{NEW_BASE_FILE:06X}",
         "new_base_rom": f"0x{NEW_BASE_ROM:08X}",
         "old_base_rom": f"0x{OLD_BASE_ROM:08X}",
         "pool_file": f"0x{POOL_FILE:06X}",
         "cases": cases}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    lines = ["# 指针表搬家实验：V0/V1/V2/V3/V4 判定", "",
             f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", "",
             f"新基址：`0x{NEW_BASE_ROM:08X}`（文件偏移 `0x{NEW_BASE_FILE:06X}`）",
             f"旧基址：`0x{OLD_BASE_ROM:08X}`　串池：`0x{ROM_BASE + POOL_FILE:08X}`", "",
             "判定口径：**最后 3 张画面完全相同 = 卡死**；否则 = 能跑。", "",
             "| 变体 | ROM | 判定 | 变化步数 | 冻结步 |",
             "|---|---|---|---|---|"]
    for c in cases:
        lines.append(f"| {c['variant']} | `{c['rom']}` | **{c['verdict']}** | "
                     f"{c['changes']} | {c['frozen_at']} |")
    lines.append("")
    for c in cases:
        lines.append(f"## {c['label']}")
        lines.append("")
        lines.append(f"* ROM：`{c['rom']}`")
        lines.append(f"* 判定：**{c['verdict']}** —— {c['why']}")
        lines.append(f"* 屏幕哈希序列：")
        lines.append("")
        lines.append("```")
        lines.append("  ".join(f"{s['step']}:{s['screen']}" for s in c["sequence"]))
        lines.append("```")
        lines.append("")
        lines.append(f"* 与原版 ROM 的差异区间：{', '.join(c['verify']['diff_ranges'])}")
        lines.append("")
    (REPO / args.out_md).write_text("\n".join(lines), encoding="utf-8", newline="\n")

    print(f"\nwrote {out_json}")
    print(f"wrote {REPO / args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
