#!/usr/bin/env python3
"""「说话人名表串池对齐」实验：名字字符串在串池里的**对齐**是不是卡死的病灶？

上一轮已排除的东西（见 notes/evidence/speaker-name-relocation-experiment-20261023.md）
------------------------------------------------------------------------------------
* 指针表放**哪**无关（V1 搬到 `0x085B56E0` 仍卡，且与不搬家的版本**逐帧相同**）；
* 名字的**内容/长度**无关（V4 等长照样卡，冻结画面哈希都一样）；
* 14 处补丁的**字节/语义**没错（两版读的是同一个字面量槽 `0x08097A40`）；
* 没有第 13 个读者（全 ROM 扫 u32，`0x085A57C4` 的引用恰好 12 个字面量）。

本轮的核心假设
--------------
**串池里的名字字符串没有对齐。**
原版内联槽每条 **12 字节**（`12 % 4 == 0`）⇒ 每条名字都落在 4 字节对齐的地址上。
产品代码把 64 条名字**紧挨着**写进串池，每条 = `2×字数 + 1`（含 NUL）⇒
**长度是奇数** ⇒ 从第 2 条起有一半名字起始地址是**奇数**。
⇒ 若游戏有任何一处用 16 位读（`ldrh`）去取名字/字形码，奇地址上的半字读会被 GBA
**旋转**（字节交换）⇒ 取到错的字形码 / 死循环。

本轮的变体矩阵
--------------
| 变体 | 只改一件事 | 想回答什么 |
|---|---|---|
| **P0** | = V1（基线，已知卡死） | 对照 |
| **P1** | 串池里每条名字**补齐到 2 字节对齐** | 对齐是病灶吗？ |
| **P2** | 串池里每条名字**补齐到 4 字节对齐** | 同上（更强的对齐） |
| **P3** | **指针表指向「原版内联槽」**（`基址 + id*12`），**完全不写串池** | 病灶是「名字被搬进池子」这件事？指针表本身无害？ |
| **P4** | = P3，但名字**确实改长**（id 1 → 「鸣人测试」，仍住原位内联槽） | 长度/内容开始起作用了吗？ |

判定口径（**与前两轮完全一致**）
--------------------------------
每按一次 A 截一张 mGBA 渲染缓冲（`rawshot`），比相邻两张的哈希；
**最后 3 张完全相同 ⇒ 卡死**，否则 ⇒ 画面还在推进 ⇒ 能跑。
判定用的运行**只挂一个永不命中的断点** `0x08FFFFFE`。

用法
----
    python tools/mgba_probe/speaker_align_probe.py            # 跑 P0..P4
    python tools/mgba_probe/speaker_align_probe.py --only p1   # 只跑一个（可重复）
    python tools/mgba_probe/speaker_align_probe.py --bisect-readers --only v0
        # 追加「按读者二分」：在 P3 的**正确取名**配置上，一次只改**一个**读者
        # （它自己的基址字面量 + 它自己的补丁），看是哪一个读者把游戏弄坏。
        # ⇒ 本轮实测：12 个读者里只有 **读者 12（剧情 VM 的 op 0x08 / op 0x0E）** 会卡。
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

from tools.mgba_probe.speaker_bisect import PRESSES, judge, run_probe  # noqa: E402
from tools.mgba_probe.speaker_relocate_probe import (  # noqa: E402
    EXPECTED_LITERALS, NEW_BASE_FILE, NEW_BASE_ROM, OLD_BASE_FILE, OLD_BASE_ROM,
    POOL_FILE, apply_code_patches, load_patch_hexes, patch_literals,
)

ROM_BASE = 0x08000000
BASE_ROM = REPO / "rom" / "base.gba"

TARGET_ID = 1                # 「鸣人」
NAME_TEXT = "鸣人测试"       # 让 id 1 变长 ⇒ 触发「内联槽 → 指针表」转换
INLINE_STRIDE = 12           # 原版内联槽步长
INLINE_COUNT = 63            # 原版内联槽条数（id 0..62；id 63 已经是「说话人全名表」）
INLINE_REGION = (OLD_BASE_FILE, OLD_BASE_FILE + INLINE_COUNT * INLINE_STRIDE)  # 0x5A57C4..0x5A5AB8

# --------------------------------------------------------------------- 造 ROM
# Node 侧的构建脚本（**不写回 pack.json**：基址只在内存里改）。
# 14 处指令补丁**留空**，由 Python 侧按 `speaker_name_code_patches.json` 逐字节打
# —— 这样「开关补丁」与「改字面量」两件事互不干扰（沿用上一轮的做法）。
MJS_SOURCE = r"""
// 由 tools/mgba_probe/speaker_align_probe.py 自动生成（每次运行重写）。
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
const outPath = arg('--out', 'build/align_base.gba');
const base = Number(arg('--base', '0'));
const targetId = Number(arg('--id', '1'));
const newText = arg('--text', '');

const rom = new Uint8Array(readFileSync(join(repoRoot, 'rom', 'base.gba')));
const pack = ContentPack.fromJSON(
  JSON.parse(readFileSync(join(repoRoot, 'rom-editor', 'content', 'pack.json'), 'utf8')));
pack.patches = [];

// ★ 本实验的唯一改动：把「内联槽 → 指针表」的基址换成新基址（**只在内存里**）。
pack.conversions.speaker_names.base = base;
// 14 处指令补丁留空：Python 侧按 tools/data/speaker_name_code_patches.json 逐字节打。
pack.conversions.speaker_names.code_patches = [];

const table = pack.textTable('speaker_names');
const record = table.records.find((r) => r.id === targetId);
if (!record) throw new Error(`speaker_names 里没有 id ${targetId}`);
pack.setText(table, record, newText || `${record.text}测试`);

const { bytes, report } = buildRom(pack, rom);
if (report.errors.length) {
  console.error('构建失败：');
  for (const e of report.errors) console.error('  ' + e);
  process.exit(1);
}
writeFileSync(join(repoRoot, outPath), Buffer.from(bytes));
console.log(`已写出 ${outPath}（基址 0x${base.toString(16)}）`);
"""


def build_product_rom() -> pathlib.Path:
    """用**产品代码**造出「指针表在新基址 + 名字在串池」的 ROM（指令补丁留给 Python）。

    `pack.json` **一个字都不改**（基址只在内存里改），与上一轮的做法一致。
    """
    mjs = REPO / "build" / "align_build.mjs"
    mjs.parent.mkdir(parents=True, exist_ok=True)
    mjs.write_text(MJS_SOURCE, encoding="utf-8", newline="\n")
    out_rel = "build/align_base.gba"
    cmd = ["node", str(mjs), "--out", out_rel, "--base", str(NEW_BASE_FILE),
           "--id", str(TARGET_ID), "--text", NAME_TEXT]
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"构建失败 {out_rel}:\n{res.stdout}\n{res.stderr}")
    return REPO / out_rel


# ------------------------------------------------------------- 串池 / 指针表
def read_pool_records(data: bytes | bytearray) -> list[bytes]:
    """从串池里读出 64 条记录的正文（不含结尾的 NUL）。

    串池里每条 = 正文 + 1 个 `0x00`；正文是双字节字形码（lead 0x80..0x9F），
    **正文里不会有 0x00** ⇒ 按「遇 0x00 停」解析是安全的。
    """
    out: list[bytes] = []
    cur = POOL_FILE
    for _ in range(64):
        end = data.index(0, cur)
        out.append(bytes(data[cur:end]))
        cur = end + 1
    return out


def pool_record_offsets(data: bytes | bytearray) -> list[int]:
    """串池里 64 条记录各自的文件偏移。"""
    out: list[int] = []
    cur = POOL_FILE
    for _ in range(64):
        out.append(cur)
        cur = data.index(0, cur) + 1
    return out


def relayout_pool_aligned(data: bytearray, align: int) -> dict:
    """把串池按 `align` 字节对齐重排，并**同步改写 64 个指针**。

    每条记录 = 正文 + `0x00`，再补 `0x00` 到 `align` 的倍数。
    """
    records = read_pool_records(data)
    offsets: list[int] = []
    cur = POOL_FILE
    for content in records:
        offsets.append(cur)
        size = len(content) + 1
        padded = (size + align - 1) // align * align
        data[cur:cur + len(content)] = content
        data[cur + len(content)] = 0
        for k in range(size, padded):
            data[cur + k] = 0
        cur += padded
    for i, off in enumerate(offsets):
        struct.pack_into("<I", data, NEW_BASE_FILE + 4 * i, ROM_BASE + off)
    return {
        "align": align,
        "pool_end": cur,
        "pool_size": cur - POOL_FILE,
        "record_offsets": offsets,
        "odd_starts": sum(1 for o in offsets if o % 2 == 1),
        "misaligned_starts": sum(1 for o in offsets if o % align != 0),
    }


def write_inline_pointer_table(data: bytearray) -> None:
    """指针表的 64 个指针改成「原版内联槽地址」= `基址 + id*12`。"""
    for i in range(64):
        struct.pack_into("<I", data, NEW_BASE_FILE + 4 * i, OLD_BASE_ROM + i * INLINE_STRIDE)


def restore_region_from_base(data: bytearray, start: int, length: int) -> None:
    """把一段恢复成**原版 ROM** 的字节。"""
    base = BASE_ROM.read_bytes()
    data[start:start + length] = base[start:start + length]


def set_inline_name(data: bytearray, slot_id: int, content: bytes) -> dict:
    """把 id `slot_id` 的名字**写回原版内联槽**（正文 + NUL + 0 填充到 12 字节）。"""
    off = OLD_BASE_FILE + slot_id * INLINE_STRIDE
    if len(content) + 1 > INLINE_STRIDE:
        raise RuntimeError(f"名字太长，塞不进 {INLINE_STRIDE} 字节的内联槽：{content!r}")
    data[off:off + INLINE_STRIDE] = b"\x00" * INLINE_STRIDE
    data[off:off + len(content)] = content
    data[off + len(content)] = 0
    return {"slot_offset": off, "content": content.hex(" ")}


def reader_groups() -> list[dict]:
    """按**读者**把 14 处补丁分组（读者 8 和 12 各有 2 处，共用同一个字面量）。

    每一组 = 一个读者 = 一个基址字面量（改它就会同时影响该读者的所有取名点）。
    """
    groups: dict[int, dict] = {}
    for p in load_patch_hexes():
        g = groups.setdefault(p["reader"], {"reader": p["reader"], "sites": [],
                                            "literal": p["literal_rom_addr"]})
        g["sites"].append(p)
    out = []
    for r in sorted(groups):
        g = groups[r]
        out.append({
            "reader": r,
            "sites": [p["site"] for p in g["sites"]],
            "literal": int(g["literal"], 16),
            "patches": g["sites"],
        })
    return out


# --------------------------------------------------------------------- 自检
def verify_rom(path: pathlib.Path, kind: str, pool_info: dict | None,
               inline_content: bytes | None = None) -> dict:
    """核对造出来的 ROM 是不是「说的那样」—— 结论必须建立在核对过的字节上。"""
    data = path.read_bytes()
    base = BASE_ROM.read_bytes()
    out: dict = {"path": str(path.relative_to(REPO)), "checks": [], "ok": True}

    def check(name: str, cond: bool, detail: str = "") -> None:
        out["checks"].append({"name": name, "ok": bool(cond), "detail": detail})
        if not cond:
            out["ok"] = False

    # 1) 12 处基址字面量 = 新基址
    lits = {f"0x{a:08X}": f"0x{struct.unpack_from('<I', data, a - ROM_BASE)[0]:08X}"
            for a in EXPECTED_LITERALS}
    check("12 处基址字面量 = 新基址",
          all(v == f"0x{NEW_BASE_ROM:08X}" for v in lits.values()), str(lits))

    # 2) 14 处指令补丁全开
    patches = load_patch_hexes()
    bad = []
    for p in patches:
        off = int(p["rom_offset"], 16)
        want = bytes.fromhex(p["after_hex"])
        if bytes(data[off:off + len(want)]) != want:
            bad.append(p["rom_addr"])
    check("14 处指令补丁 = after_hex", not bad,
          "全部匹配" if not bad else f"不匹配：{bad}")

    # 3) 指针表 64 个指针的落点
    pt = [struct.unpack_from("<I", data, NEW_BASE_FILE + 4 * i)[0] for i in range(64)]
    if kind in ("p3", "p4"):
        want = [OLD_BASE_ROM + i * INLINE_STRIDE for i in range(64)]
        check("指针表 64 项 = 原版内联槽（基址+id*12）", pt == want,
              f"entry0=0x{pt[0]:08X} entry1=0x{pt[1]:08X} entry63=0x{pt[63]:08X}")
    else:
        pool_lo = ROM_BASE + POOL_FILE
        pool_hi = pool_lo + (pool_info["pool_size"] if pool_info else 0x1000)
        in_pool = all(pool_lo <= v < pool_hi for v in pt)
        check("指针表 64 项都指向串池", in_pool,
              f"entry0=0x{pt[0]:08X} entry1=0x{pt[1]:08X} entry44=0x{pt[44]:08X}")

    # 4) 旧内联名字表逐字节保持原版（P4 改了 slot 1，单独说明）
    lo, hi = INLINE_REGION
    old = bytes(data[lo:hi])
    orig = bytes(base[lo:hi])
    if kind == "p4":
        # slot 1 被改写成新名字（正文 + NUL + 0 填充），**其余**槽逐字节与原版相同
        want_slot = inline_content + b"\x00" * (INLINE_STRIDE - len(inline_content))
        got_slot = bytes(data[lo + INLINE_STRIDE: lo + INLINE_STRIDE * 2])
        rest_same = (bytes(data[lo:lo + INLINE_STRIDE]) == bytes(orig[:INLINE_STRIDE])
                     and bytes(data[lo + INLINE_STRIDE * 2:hi]) == bytes(orig[INLINE_STRIDE * 2:]))
        check("旧内联表：只有 slot 1 被改写，内容 = 新名字正文 + NUL + 填充",
              got_slot == want_slot and rest_same,
              f"slot1 = {got_slot.hex(' ')}（期望 {want_slot.hex(' ')}）；"
              f"其余 {INLINE_COUNT - 1} 个槽与原版相同 = {rest_same}")
    else:
        check("旧内联名字表 0x5A57C4..0x5A5AB7 逐字节与原版相同", old == orig,
              "逐字节相同" if old == orig else "已被改写")

    # 5) 串池：位置、内容、与指针表不重叠
    if kind in ("p3", "p4"):
        allff = all(b == 0xFF for b in data[POOL_FILE:POOL_FILE + 0x400])
        check("串池区 0x5DFBEC 起 1024 字节全 0xFF（没写串池）", allff,
              data[POOL_FILE:POOL_FILE + 8].hex(" "))
    else:
        pool_size = pool_info["pool_size"] if pool_info else 340
        free_ok = all(b == 0xFF for b in base[POOL_FILE:POOL_FILE + pool_size])
        check("串池那段在原版 ROM 里全是 0xFF（是空闲区）", free_ok,
              f"0x{POOL_FILE:06X}..0x{POOL_FILE + pool_size - 1:06X}")
        if pool_info:
            mis = pool_info["misaligned_starts"]
            check(f"串池 64 条记录起始地址都对齐到 {pool_info['align']} 字节",
                  mis == 0,
                  f"未对齐 {mis} 条；奇地址 {pool_info['odd_starts']} 条")

    overlap = not (NEW_BASE_FILE + 256 <= POOL_FILE
                   or POOL_FILE + 0x400 <= NEW_BASE_FILE)
    check("指针表与串池不重叠", not overlap,
          f"指针表 0x{NEW_BASE_FILE:06X}..0x{NEW_BASE_FILE + 255:06X} / "
          f"串池 0x{POOL_FILE:06X} 起")

    # 6) 新基址那 256 字节在**原版 ROM** 里是不是全 0xFF
    ff = all(b == 0xFF for b in base[NEW_BASE_FILE:NEW_BASE_FILE + 256])
    check("新基址那 256 字节在原版 ROM 里全是 0xFF", ff,
          f"0x{NEW_BASE_FILE:06X}..0x{NEW_BASE_FILE + 255:06X}")

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


# --------------------------------------------------------------------- 变体
LABELS = {
    "v0": "V0 阳性对照：原版 ROM（未做任何改动）",
    "p0": "P0 基线：= V1（指针表在新基址 + 名字在串池 + 12 处字面量改新基址 + 14 处补丁全开）",
    "p1": "P1 串池每条名字补齐到 **2 字节对齐**（其余同 P0）",
    "p2": "P2 串池每条名字补齐到 **4 字节对齐**（其余同 P0）",
    "p3": "P3 指针表指向**原版内联槽**（基址+id*12），**完全不写串池**（其余同 P0）",
    "p4": "P4 = P3，但 id 1 的名字**确实改长**为「鸣人测试」（仍住原位内联槽）",
}


def make_variant(kind: str, product: pathlib.Path) -> tuple[pathlib.Path, dict]:
    """造一个变体的 ROM。"""
    if kind == "v0":
        return BASE_ROM, {"kind": kind, "note": "原版 ROM，未做任何改动"}
    data = bytearray(product.read_bytes())
    how: dict = {"kind": kind}
    # 所有变体共有：12 处字面量改新基址 + 14 处指令补丁全开
    how["literal_changes"] = patch_literals(data, NEW_BASE_ROM)
    how["code_patches_applied"] = apply_code_patches(data, load_patch_hexes())

    pool_info = None
    if kind in ("p1", "p2"):
        align = 2 if kind == "p1" else 4
        pool_info = relayout_pool_aligned(data, align)
        how["pool"] = {k: v for k, v in pool_info.items() if k != "record_offsets"}
    elif kind in ("p3", "p4"):
        # 名字**留在原位**：指针表指向原版内联槽，串池不写，旧内联表保持原版。
        # ⚠️ 顺序要紧：先取「产品代码写进串池的那份字形码」（P4 要用），
        #    再把串池恢复成 0xFF，再把旧内联表恢复成原版，**最后**才写 P4 的新名字。
        content = read_pool_records(data)[TARGET_ID] if kind == "p4" else None
        write_inline_pointer_table(data)
        restore_region_from_base(data, POOL_FILE, 0x400)
        restore_region_from_base(data, INLINE_REGION[0], INLINE_REGION[1] - INLINE_REGION[0])
        how["pointer_table"] = "64 项 = 0x085A57C4 + id*12（原版内联槽）"
        how["pool"] = "未写（0x5DFBEC 起恢复成 0xFF）"
        if kind == "p4":
            how["inline_name"] = set_inline_name(data, TARGET_ID, content)
    out = REPO / f"build/align_{kind}.gba"
    out.write_bytes(bytes(data))
    return out, {"pool_info": pool_info, **how}


def make_reader_bisect_rom(product: pathlib.Path, group: dict) -> pathlib.Path:
    """造一个「只改一个读者」的 ROM（P3 的正确取名配置）。

    * 指针表放新基址，64 项指向**原版内联槽**（数据全对）；
    * 串池不写、旧内联表保持原版；
    * **只**把这个读者的基址字面量改成新基址（其它读者仍按旧基址+id*12 读旧内联槽）；
    * **只**打这个读者的补丁。
    """
    data = bytearray(product.read_bytes())
    for p in group["patches"]:
        off = int(p["rom_offset"], 16)
        before = bytes.fromhex(p["before_hex"])
        after = bytes.fromhex(p["after_hex"])
        if bytes(data[off:off + len(before)]) != before:
            raise RuntimeError(f"补丁 {p['rom_addr']} 的原始字节不匹配")
        data[off:off + len(after)] = after
    struct.pack_into("<I", data, group["literal"] - ROM_BASE, NEW_BASE_ROM)
    write_inline_pointer_table(data)
    restore_region_from_base(data, POOL_FILE, 0x400)
    restore_region_from_base(data, INLINE_REGION[0], INLINE_REGION[1] - INLINE_REGION[0])
    out = REPO / f"build/align_bisect_r{group['reader']:02d}.gba"
    out.write_bytes(bytes(data))
    return out


# --------------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", action="append", default=[],
                    choices=sorted(LABELS), help="只跑某几个变体；可重复")
    ap.add_argument("--presses", type=int, default=PRESSES)
    ap.add_argument("--out-json", default="build/align_speaker_probe.json")
    ap.add_argument("--out-md", default="build/align_speaker_probe.md")
    ap.add_argument("--bisect-readers", action="store_true",
                    help="追加「按读者二分」：在 P3 的正确取名配置上，"
                         "每次只改**一个**读者的字面量+补丁，看是哪一个读者把游戏弄坏")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    kinds = args.only or sorted(LABELS)
    product = build_product_rom()

    # 合并到既有 JSON（按变体名覆盖），这样可以一个变体一个变体地跑。
    out_json = REPO / args.out_json
    out_json.parent.mkdir(parents=True, exist_ok=True)
    store: dict = {"cases": {}}
    if out_json.exists():
        try:
            store = json.loads(out_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            store = {"cases": {}}
    store.setdefault("cases", {})

    for kind in kinds:
        rom, how = make_variant(kind, product)
        pool_info = how.get("pool_info")
        inline_content = (bytes.fromhex(how["inline_name"]["content"])
                          if kind == "p4" else None)
        if kind == "v0":
            check = {"path": str(rom.relative_to(REPO)), "checks": [], "ok": True,
                     "diff_ranges": []}
        else:
            check = verify_rom(rom, kind, pool_info, inline_content)
        t0 = time.monotonic()
        result = run_probe(rom, presses=args.presses)
        verdict, why = judge(result)
        seq = result["sequence"]
        hashes = [s["screen"] for s in seq]
        frozen_at = result["frozen_at"]
        case = {
            "variant": kind,
            "label": LABELS[kind],
            "rom": str(rom.relative_to(REPO)),
            "verdict": verdict,
            "why": why,
            "changes": result["changes"],
            "frozen_at": frozen_at,
            "frozen_screen": hashes[frozen_at] if frozen_at is not None else None,
            "sequence": seq,
            "seconds": round(time.monotonic() - t0, 2),
            "build": {k: v for k, v in how.items() if k != "pool_info"},
            "verify": check,
        }
        store["cases"][kind] = case
        out_json.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")

        print(f"{verdict:<4} {LABELS[kind]}")
        print(f"      ROM {rom.relative_to(REPO)}  变化 {result['changes']} 步  "
              f"冻结 {frozen_at}  冻结画面哈希 {case['frozen_screen']}  "
              f"[{case['seconds']}s]")
        print(f"      自检：{'全部通过' if check['ok'] else '★有不通过项'}")
        for c in check["checks"]:
            if not c["ok"]:
                print(f"        ✗ {c['name']}：{c['detail']}")
        print("      哈希序列：" + " ".join(hashes))
        sys.stdout.flush()

    # --- 追加：按读者二分（P3 的正确取名配置，每次只改一个读者） -------------
    bisect: list[dict] = []
    if args.bisect_readers:
        for group in reader_groups():
            rom = make_reader_bisect_rom(product, group)
            t0 = time.monotonic()
            result = run_probe(rom, presses=args.presses)
            verdict, why = judge(result)
            hashes = [s["screen"] for s in result["sequence"]]
            frozen_at = result["frozen_at"]
            bisect.append({
                "reader": group["reader"],
                "sites": group["sites"],
                "literal": f"0x{group['literal']:08X}",
                "rom": str(rom.relative_to(REPO)),
                "verdict": verdict,
                "changes": result["changes"],
                "frozen_at": frozen_at,
                "frozen_screen": hashes[frozen_at] if frozen_at is not None else None,
                "sequence": result["sequence"],
            })
            print(f"{verdict:<4} 读者 {group['reader']:>2} / {', '.join(group['sites'])}"
                  f"  字面量 0x{group['literal']:08X}  变化 {result['changes']} 步  "
                  f"冻结 {frozen_at}  冻结画面哈希 "
                  f"{hashes[frozen_at] if frozen_at is not None else None}"
                  f"  [{round(time.monotonic() - t0, 2)}s]")
            sys.stdout.flush()
        store["reader_bisect"] = bisect
        out_json.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")

    # 写一份人读的表（全部变体都有结果时）
    order = [k for k in sorted(LABELS) if k in store["cases"]]
    lines = ["# 串池对齐实验：P0..P4 判定", "",
             f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", "",
             f"新基址（指针表）：`0x{NEW_BASE_ROM:08X}`（文件偏移 `0x{NEW_BASE_FILE:06X}`）",
             f"旧内联表：`0x{OLD_BASE_ROM:08X}`（文件偏移 `0x{OLD_BASE_FILE:06X}`，每条 12 字节）",
             f"串池：`0x{ROM_BASE + POOL_FILE:08X}`（文件偏移 `0x{POOL_FILE:06X}`）", "",
             "判定口径：**最后 3 张画面完全相同 = 卡死**；否则 = 能跑。", "",
             "| 变体 | ROM | 判定 | 变化步数 | 冻结步 | 冻结画面哈希 |",
             "|---|---|---|---|---|---|"]
    for k in order:
        c = store["cases"][k]
        lines.append(f"| {k.upper()} | `{c['rom']}` | **{c['verdict']}** | "
                     f"{c['changes']} | {c['frozen_at']} | `{c['frozen_screen']}` |")
    lines.append("")
    for k in order:
        c = store["cases"][k]
        lines.append(f"## {c['label']}")
        lines.append("")
        lines.append(f"* ROM：`{c['rom']}`")
        lines.append(f"* 判定：**{c['verdict']}** —— {c['why']}")
        lines.append(f"* 冻结画面哈希：`{c['frozen_screen']}`")
        lines.append("* 屏幕哈希序列：")
        lines.append("")
        lines.append("```")
        lines.append("  ".join(f"{s['step']}:{s['screen']}" for s in c["sequence"]))
        lines.append("```")
        lines.append("")
        lines.append(f"* 与原版 ROM 的差异区间：{', '.join(c['verify']['diff_ranges'])}")
        lines.append("")
    # 逐帧比对
    lines.append("## 逐帧比对")
    lines.append("")
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            ha = [s["screen"] for s in store["cases"][a]["sequence"]]
            hb = [s["screen"] for s in store["cases"][b]["sequence"]]
            lines.append(f"* {a.upper()} vs {b.upper()}：逐帧完全相同 = **{ha == hb}**")
    lines.append("")
    (REPO / args.out_md).write_text("\n".join(lines), encoding="utf-8", newline="\n")

    print(f"\nwrote {out_json}")
    print(f"wrote {REPO / args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
