#!/usr/bin/env python3
"""Recompute the per-structure reverse-engineering completion table.

Why this exists
---------------
`notes/re-completion-audit.md` (2026-07-11) scored the 32 content banks as
"32/32 complete" while its own verification distribution was
`static_verified`=30 / `code_verified`=1 / `runtime_verified`=1, and it said so
itself: *"no runtime or write-back validation ... cannot prove runtime
semantics or actual write-back closure"*.  Since then (2026-10-20) a large
amount of genuinely new evidence landed (font-code write-back, the story VM,
the battle/mission/reward/portrait tables, the four-level evidence ladder),
and the old "32/32" number stopped meaning anything.

This script rebuilds the table from the repository's *current* state, using the
four-level ladder defined in `notes/runtime-verification-gates-20260710.md`:

    L1  tool / editor output passes
    L2  native decision point (breakpoint hits the consumer, registers or
        memory correspond to the field)
    L3  reproduced with normal key input in an emulator
    L4  full playthrough

How the levels are computed
----------------------------
Nothing is asserted from a hand-written per-structure verdict.  For every
audited structure the script:

  1. reads `sequel/content/*/bank.json` for the declared table offset and the
     legacy verification label;
  2. reads `tools/table_registry.py` for the authoritative address of every
     table (including which ones are *not* independently verified);
  3. imports `tools/synthetic_fixture.py` and enumerates the registered
     synthetic fixtures;
  4. greps `tools/`, `notes/` and `docs/` for the structure's address
     (matching both the file offset and the `0x08xxxxxx` ARM form);
  5. checks each *declared evidence probe* -- a file path plus the exact
     marker substrings that make it evidence (a disassembly line, a fixture
     name, a round-trip assertion, a render artifact) -- and records which
     probes passed and which did not.

The level is then a pure function of those probe results:

    L1 = (a format-proof probe passed) and (a tool that mentions the address
          exists) and (a note that mentions the address exists)
    L2 = an L2 dynamic-evidence probe passed
    L3 = an L3 dynamic-evidence probe passed
    L4 = an L4 dynamic-evidence probe passed

L2 and L3 are two independent collection routes (breakpoint pinning vs.
emulator key input), so L3 does not require L2.  A structure with no passing
proof is reported as `none`, not as `static_verified`: a bank merely being
extracted by a generic extractor is *not* proof of a format.

Because a probe is a checked pointer to evidence, deleting or weakening the
evidence lowers the level automatically.  That is the point: the table is a
verdict on the repository, not on this file.

Usage
-----
    python tools/completion_audit.py                     # summary + markdown
    python tools/completion_audit.py --json build/completion-audit.json
    python tools/completion_audit.py --markdown build/completion-audit.md
    python tools/completion_audit.py --check             # non-zero on drift
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

ARM_BASE = 0x08000000
HEX_RE = re.compile(r"0x([0-9A-Fa-f]+)")

LEVELS = ("L4", "L3", "L2", "L1", "none")
LEVEL_LABEL = {
    "L4": "L4 完整通关",
    "L3": "L3 模拟器按键",
    "L2": "L2 原生定点",
    "L1": "L1 工具产出",
    "none": "无证据",
}

# The fixture-coverage note is the committed record that a registered fixture
# was actually run green.  A fixture name must appear there as well as in the
# live registry for the fixture to count as evidence.
FIXTURE_COVERAGE_NOTE = "notes/fixture-coverage-20261020.md"

# Machine-checkable native-consumer evidence, produced by
# `tools/consumer_locate.py`.  Every structure whose base appears in this
# file automatically gets a `codecite` (positive) or `notatable`
# (negative: the ROM never names that address) probe.
CONSUMER_EVIDENCE = "notes/evidence/consumer-evidence.json"
BASE_ROM = "rom/base.gba"

# The write-back self-check.  `tools/writeback_paths.py` holds one case per
# structure; each case copies a native entry out of the ROM, applies an
# author change, reads it back and asserts (a) the read-back equals the
# author input and (b) no byte outside the declared "known field" set moved.
# The audit *executes* the case instead of grepping for the tool, so a
# write-back path only counts once it actually round-trips.
WRITEBACK_SELFCHECK = "tools/writeback_paths.py"

# L2 runtime evidence: a breakpoint hits the structure's native consumer and
# the registers/memory correspond to its fields.  Produced by
# `tools/l2_runtime_capture.py` (which re-runs the capture and exits non-zero
# when the correspondence is missing).
L2_EVIDENCE_NOTE = "notes/evidence/l2-runtime-evidence-20261021.md"

# L4 evidence: every battle configuration, every map, and a game-driven
# scene->scene transition were actually run in the emulator.
# `tools/mgba_probe/l4_battle_matrix.py` is the executable gate (it exits
# non-zero when an item is not reached).
L4_EVIDENCE_NOTE = "notes/evidence/l4-battle-matrix-20261021.md"

# ---------------------------------------------------------------------------
# Structure catalog.
#
# Each entry declares *where the evidence lives*, never the conclusion.  The
# conclusion (the level) is computed from the probe results.  `covers` lists
# the addresses a single fixture is allowed to cover for this structure.
#
# `value` / `effort` are the one place where a human judgement is declared
# rather than derived: they drive the gap ranking ("unlock value / cost").
# ---------------------------------------------------------------------------
SPECS: dict[str, dict[str, Any]] = {
    # ---- 2026-10-20 newly verified structures ----------------------------
    "maps": {
        "title": "战斗地图表（场景描述符）",
        "rom": 0x53D910,
        "bank": "maps",
        "probes": [
            {"kind": "tool", "path": "tools/extract_scene_tilesets.py"},
            {"kind": "note", "path": "notes/resource-locations.md"},
            {"kind": "code", "path": "notes/resource-locations.md",
             "need": ["0x08069046", "adds r0, r5, #4"]},
            {"kind": "render", "tool": "tools/extract_scene_tilesets.py",
             "artifact": "build/tiles/battle_00_map_layer0_0.png"},
            {"kind": "dynamic", "path": L2_EVIDENCE_NOTE,
             "level": "L2",
             "need": ["0x0808F4F6", "0x0853D910"],
             "address_required": False},
            {"kind": "tool", "path": "tools/l2_runtime_capture.py",
             "need": ["0x0808F4F6"], "address_required": False},
            {"kind": "dynamic", "path": L4_EVIDENCE_NOTE,
             "level": "L4",
             "need": ["47/47", "0x0853D910", "0x0808F752"],
             "address_required": False},
            {"kind": "tool", "path": "tools/mgba_probe/l4_battle_matrix.py",
             "need": ["0x0808F752"], "address_required": False},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/import_battle_config.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
             "case": "encounter-zones"},
        ],
        "unresolved": [],
        "corrections": [
            "metatile 缓冲的容量**不再是从两侧结构夹出来的**："
            "缓冲**基址 `0x0201DE2C`** 与**末端 `0x02021E2C`** 是 ROM 代码里"
            "**成对出现的两个字面量常量**（分别在 `0x08068F58` 与 `0x080690E8`，"
            "同一个字面量池），步长 **8 字节**（`0x08068F38 lsls r0,r0,#3`），"
            "因此容量 = `0x4000/8` = **2048 项**。"
            "**仍未证实**：引擎没有一条显式的「下标 < 2048」越界检查，"
            "「越界会被拒绝」这句话**无证据**",
            "metatile 缓冲真实容量已闭环：WRAM `0x0201DE2C`，每项 **8 字节**"
            "（`0x08068F38 lsls r0,r0,#3`），容量 **2048 项**"
            "（= 0x4000 字节），实际最多用到 770 项",
            "「没有图层 1」的判据已固化为 **`layer1_ptr == 0`（NULL）**："
            "`0x08069082 cmp r2,#0` / `0x08069084 beq 0x0806909E`，没有别的哨兵值；"
            "47 条里 14 条非空、33 条为 NULL（已复核：非空下标 "
            "0/7/8/9/10/11/12/21/22/23/31/32/34/35）",
            "地图描述符表有 **47** 条有效条目（0..46），不是 8 条",
        ],
        "value": 5, "effort": 2,
    },
    "sound-id-table": {
        "title": "音频 sound-ID 表",
        "rom": 0x465B70,
        "readonly": True,
        "probes": [
            {"kind": "tool", "path": "tools/extract_audio.py"},
            {"kind": "note", "path": "notes/resource-locations.md"},
            {"kind": "code", "path": "notes/resource-locations.md",
             "need": ["0x0809AAC2", "lsls r0, r0, #0x10"]},
            {"kind": "render", "tool": "tools/extract_audio.py",
             "artifact": "build/audio/manifest.json"},
            {"kind": "dynamic", "path": L2_EVIDENCE_NOTE,
             "level": "L2",
             "need": ["0x0809AAC6", "0x08465B70"],
             "address_required": False},
            {"kind": "tool", "path": "tools/l2_runtime_capture.py",
             "need": ["0x0809AAC6"], "address_required": False},
            {"kind": "tool", "path": "tools/audio_song_export.py",
             "need": ["0x0809B4FE"], "address_required": False},
        ],
        "unresolved": [],
        "corrections": [
            "**DirectSound 弯音（pitch bend）插值已实现**（2026-10-21）："
            "引擎的弯音链已按本 ROM 的代码逐条转写并用探针对拍："
            "BEND(0xC0) 写 `通道+0x0E = 操作数-0x40`（`0x0809A368`）、"
            "BENDR(0xC1) 写 `通道+0x0F = 量程`（`0x0809A37C`，复位默认 2，`0x0809A4D6`）；"
            "累加器 `0x0809B450`..`0x0809B486` 给出 "
            "`S = (tune + bend*range)*4 + (keyShift<<8)`、"
            "`通道+0x08 = (s8)(S>>8)`（半音偏移）、`通道+0x09 = (u8)S`（分数）；"
            "音高键 = 音符键 + 半音偏移（负则夹 0，`0x0809A8A2`），"
            "DirectSound 音高 = `((f(k) + ((f(k+1)-f(k))*fraction>>8)) * wave[4]) >> 32`"
            "（`0x0809A998`；`>>32` 来自 ARM 态助手 `0x08099D80`）。"
            "`tools/audio_song_export.py` 现在算的是**同一套整数**，"
            "并用 `tools/closure_pitch_check.py` 对拍引擎自己的读数："
            "**179 条引擎音高读数 0 处不符**（含弯音分数 128/160 与半音偏移 +4/−1）。"
            "五个原生曲子的 PSG 导出仍与 ROM 原始字节逐事件相符（616/534/746/612/498）",
            "**PSG 频率表只有 12 项有符号 16 位**（`ldrsh` @ `0x0809B4FE`），"
            "不是 16 项无符号 —— 旧工具读 16 个 u16，**读进了噪声表**；"
            "旧工具还有 `+0x800` 偏置、算术右移、噪声 key 重映射"
            "（`key<=20 ? 0 : min(key-21,59)`）与 `key-36` 先减后夹的顺序错误。"
            "现在五个已知 SongHeader 的 PSG 事件数"
            "（616/534/746/612/498）已与 ROM 原始字节逐条对上",
            "m4a 引擎语义（tempo `0x0809A2E8`、tick 栅格 `0x0809A474`/`0x0809A5C6`、"
            "命令表 `0x08464534`、音符频率 `0x0809A998`、PSG 频率 `0x0809B494`、"
            "循环 `0x0809A25C/27C/298/2AC`）已按**本 ROM 的代码**逐条反汇编证实",
            "**块级轨道重写已实现**（2026-10-21）：block 表就是 SongHeader 本身，"
            "`track_ptr[i]` 指向无头的命令流（FINE 结束）；"
            "`tools/m4a_block_table.py` 的 decode→encode 对 45 个原生 block "
            "**逐字节相同**，并支持就地重写 / 重建 / 停在自由区并改指针；"
            "`tools/import_audio_song.py --block trackN=json[,offset]` 已接上，"
            "写回自检新增 case `audio-block-1`（19/19 PASS）",
            "**running opcode 规则已修**：`0x0809A4F8 cmp r1,#0xbd` 表明"
            "**所有 `>= 0xBD` 的 opcode 都更新 running opcode**（不只是音符）；"
            "旧解码器只在音符时更新，把 MOD/EOT 的参数读成了 key=0 的假音符"
            "（101 字节 / 11 条轨道）。修完后两个独立解码器**零分歧**",
        ],
        "value": 4, "effort": 3,
    },
    "battle-rules": {
        "title": "战斗胜负条件表",
        "rom": 0x594758,
        "probes": [
            {"kind": "fixture", "name": "battle_rules", "covers": [0x594758]},
            {"kind": "tool", "path": "tools/extract_battle_tables.py"},
            {"kind": "note", "path": "notes/battle-tables.md"},
            {"kind": "dynamic", "path": "notes/evidence/battle-rules-l2-20261020.md",
             "level": "L2",
             "need": ["0x08077904", "0x08594830", "0x0202680C", "0x02026804"],
             "address_required": False},
            {"kind": "tool", "path": "tools/battle_rules_runtime.py",
             "need": ["0x08077904"], "address_required": False},
        ],
        "writeback": [{"kind": "tool", "path": "tools/build_db_patches.py"}],
        "unresolved": [],
        "corrections": [
            "`0x0202680C` **就是回合计数**（2026-10-21，旧的「不是回合计数」结论**作废**）："
            "它是战斗控制块 `0x02026804` 的 **+8** 字节，类型 2 的胜利条件正是"
            "「`0x0202680C` == `ctrl[6]`（回合上限，`0x0202680A`）」"
            "（`0x08077914`..`0x0807791A`；上限为 0 时该规则不生效）。"
            "运行时读数（`tools/closure_round_probe.py`，组 9 / 子 0）："
            "只按 A 时战斗停在界面、计数不动；**按 DOWN + A 真的把回合打完**时，"
            "计数从 **1 变 2**。"
            "旧审计「40 轮按键全程为 0」的那次读数是因为**战斗没推进过回合**",
            "类型 2 的判据已由原生代码证明为**回合上限到达**"
            "（`0x08077904` 比对 `ctrl[6]`=回合上限 与 `byte[0x0202680C]`），"
            "而且**从不读 `rule.a` / `rule.b`** —— "
            "旧笔记「与类型 3 成对出现、意图是类型 3 的反面」的说法**作废**："
            "它本来就不看 a/b，所以成对出现没有语义冲突",
            "类型 3 = 「指定角色已离场」（`rule.a`=阵营、`rule.b`=角色 id，"
            "判据在 `0x020240C0` 的 12 个单位槽）",
        ],
        "value": 5, "effort": 2,
    },
    "mission-text": {
        "title": "任务文字三表（标题/说明/提示）",
        "rom": 0x348DAC,
        "probes": [
            {"kind": "fixture", "name": "mission_text",
             "covers": [0x348DAC, 0x59AA5C, 0x59D214, 0x59E920]},
            {"kind": "tool", "path": "tools/extract_battle_tables.py"},
            {"kind": "note", "path": "notes/battle-tables.md"},
        ],
        "writeback": [{"kind": "tool", "path": "tools/build_db_patches.py"}],
        "unresolved": [],
        "value": 4, "effort": 2,
    },
    "reward-table": {
        "title": "战斗奖励表",
        "rom": 0x59EAE0,
        "probes": [
            {"kind": "fixture", "name": "reward_entry", "covers": [0x59EAE0]},
            {"kind": "tool", "path": "tools/reward_rules_semantics.py"},
            {"kind": "note", "path": "notes/reward-and-rules-semantics-20261020.md"},
            {"kind": "dynamic", "path": L2_EVIDENCE_NOTE,
             "level": "L2",
             "need": ["0x08089EA2", "0x0859EAE0"],
             "address_required": False},
            {"kind": "tool", "path": "tools/l2_runtime_capture.py",
             "need": ["0x08089EA2"], "address_required": False},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/build_db_patches.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK, "case": "reward-table"},
        ],
        "unresolved": [
            {"type": "field",
             "text": "记录尾部 +0x16 / +0x17 两个字节语义未定（112 条全为 0、"
                     "无消费者读取）；类别 3（技术）的取值域只能由代码给出上界，"
                     "因为本 ROM 的 112 条记录里没有一条用类别 3",
             "writeback_safe": True,
             "note": "notes/reward-and-rules-semantics-20261020.md",
             "need": ["0x59EAE0", "0x0859F5E0", "越界"]},
        ],
        "corrections": [
            "尾部低字节已定为**奖励类别标签**（0=忍具 / 1=强化素材 / 2=认识卡 / 3=技术），"
            "不是数量也不是档位",
            "条目步长已由消费者证明为 **24 字节** —— 旧笔记的 16 字节说法作废",
            "类别 → 名字表对应由 ROM 自带的 4 槽指针表 `0x0859F5E0` 证明"
            "（`0x0808A02A` 载入，用尾字节做下标），不再只靠四个 arm 各挂一张字面量",
            "328 个尾部槽位的 id **全部落在各自类别的名字表容量内**（0 越界）",
        ],
        "value": 4, "effort": 3,
    },
    "portrait-table": {
        "title": "头像表 + 拼块表",
        "rom": 0x5A4DEC,
        "probes": [
            {"kind": "fixture", "name": "portrait_table",
             "covers": [0x5A4DEC, 0x4643C0]},
            {"kind": "tool", "path": "tools/portrait_assets.py"},
            {"kind": "note", "path": "notes/runtime-and-object-tables-20261020.md"},
            {"kind": "dynamic", "path": L2_EVIDENCE_NOTE,
             "level": "L2",
             "need": ["0x08096158", "0x085A4DEC"],
             "address_required": False},
            {"kind": "tool", "path": "tools/l2_runtime_capture.py",
             "need": ["0x08096158"], "address_required": False},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/export_content_pack.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
             "case": "portrait-table"},
        ],
        "unresolved": [],
        "corrections": [
            "头像素材 = BIOS LZ77（`svc 0x11`）解压的 **6400 字节 8bpp 图形** "
            "+ **128 字节原始 BGR555 调色板**；每条表情的压缩预算 2320–4008 字节，"
            "310 条表情全部能用回引用 LZ77 **压得更小**（余量 11–51 字节）⇒ 写回可行",
            "旧的「80*80/2 = 6400 字节 4bpp」算法**作废**：6400 字节是 8bpp"
            "（100 张 64 字节图块）",
            "有效头像是 **62 个 id / 310 条表情**（行 63 的指针不在 ROM 内，是垃圾指针）",
            "2026-10-21：「参数 << 4」的语义**已由原生代码钉死**"
            "（`0x080961D6`..`0x080961F8`）："
            "它是 `if (byte != 0) byte = (byte + (param << 4)) & 0xFF`，"
            "只作用于解压后 6400 字节里的**前 6144 字节**。"
            "**同一个 `param` 决定调色板槽 `0x05000200 + param*32`**"
            "（整张 64 色调色板被 CpuSet 进去），"
            "所以这次改写是**调色板索引平移**"
            "（把实际使用的 16 色窗口重基到 0..15），"
            "**不是描边、也不是换色**。旧结论「换色/描边未证实」**作废**。"
            "**运行时读数已拿到**（`tools/closure_portrait_probe.py`，场景 1 与 5 各一次）："
            "在头像加载器的 VRAM 拷贝点 `0x08096202` 断下，"
            "**WRAM 暂存缓冲 `0x02002880` 的前 6144 字节**与"
            "「ROM LZ77 解压结果 + 单个 `param<<4` 平移」**逐字节相等（0 不符）**，"
            "其中 `param<<4 = 0x40`（param = 4）—— 差分直方图只有这一个值，"
            "作用在 4309 个**非零**字节上，**零字节一个都没动**。"
            "**比对目标必须是 WRAM 暂存缓冲**：VRAM `0x06011900` 装的是"
            "**6 块拼好的 80×80 成品**，布局与源图不同"
            "（旧工具拿它跟单块源图比，得出 4925 个不符 —— 那是**模型错了**，不是数据错）；"
            "另外暂存缓冲**尾部 256 字节不是 ROM 的尾部**（是这块共享缓冲的残留），"
            "所以「后 256 字节不动」应理解为「后 256 字节不属于图形」。",
            "2026-10-21：拼块表 `portrait_pieces`（`0x4643C0`）的**基址已闭合** —— "
            "旧说「`0x084643C0` 零字面量读者 ⇒ 拿不到基址」**作废**："
            "这张表的地址是指针，存放在静态描述符 `0x0846443C` 的**首字**，"
            "而该描述符地址被 **7 处原生代码**加载"
            "（`0x08077D12` / `0x08089B06` / `0x0808B356` / `0x08091036` / "
            "`0x08091680` / `0x08093846` / `0x08096618`，"
            "其中 `0x08096618` 在头像加载路径上）。"
            "运行时读数（`tools/closure_portrait_pieces.py`）："
            "描述符首字读出 **`0x084643C0`**，6×20 = 120 字节与 ROM **逐字节相等**。"
            "6 条记录字段 = 「起始 tile / 0 / x / y / w / h / 0x0100 / 0x0100 / "
            "0x20FF / 0」，**无重叠**拼出 80×80"
            "（256+512+512+512+512+4096 = 6400）。"
            "顺带钉死池结构：源 tile 100 张来自条目 u32[0] 的 LZ77 头像"
            "（解压正好 6400 字节），另外 **36 个空位**"
            "（4..7 / 16..23 / 32..39 / 48..55 / 64..71）"
            "是**表情差分**（条目 u32[1] 的原始图块数据）的落点",
        ],
        "value": 3, "effort": 3,
    },
    "story-background-table": {
        "title": "剧情底图表",
        "rom": 0x59903C,
        "probes": [
            {"kind": "fixture", "name": "background_table", "covers": [0x59903C]},
            {"kind": "tool", "path": "tools/extract_scene_tilesets.py"},
            {"kind": "note", "path": "notes/runtime-and-object-tables-20261020.md"},
        ],
        "writeback": [{"kind": "tool", "path": "tools/build_db_patches.py"}],
        "unresolved": [],
        "corrections": [
            "8bpp 底图条目用哪一路 BG、是否开 256 色模式**已闭环**（2026-10-21）："
            "底图加载器 `0x08088348` 的第二个参数就是 **BG 号**（`0x0808835C`），"
            "运行时遍历 **55 个剧情场景**读到**每一次都是 BG0**"
            "（`DISPCNT` bit 8，`0x080883EA` 写 `1 << (8+BG)`），"
            "**8bpp 底图走 BG0**。"
            "256 色模式确实开着，但**位号是 `BGxCNT` bit 7（0x80），不是 bit 8**"
            "（bit 8 是屏幕基址块的最低位）—— 写入点在 `0x0808840E`"
            "（`movs r0,#0x80` / `orrs r3,r0`），4bpp 分支（`0x0808840C beq`）"
            "不置这一位。"
            "运行时 IO 抓取：8bpp 场景（50 / 47）`BG0CNT = 0x0087`（bit7 = 1），"
            "4bpp 场景（40）`BG0CNT = 0x0007`（bit7 = 0），`DISPCNT = 0x1F40`。"
            "底图表 320 条里有 **192 条**是 8bpp（`条目+0x0C != 0`）",
            "8bpp 条目与 4bpp 条目**互斥**，不是图层：每条都是一整张 "
            "32×32 硬件 BG 地图（320 个真实条目 + 704 个填充条目 = 正好 2 KB 一屏；"
            "4bpp 填充 tile 0、8bpp 填充 tile 30），走同一个 loader、同一批 VRAM 槽、"
            "同一个调色板 bank",
            "旧结论「8bpp 条目的层叠关系未还原」**作废** —— 不存在层叠",
        ],
        "value": 3, "effort": 3,
    },
    "story-vm-roots": {
        "title": "剧情脚本 VM 四根表",
        "rom": 0x060C74,
        "probes": [
            {"kind": "fixture", "name": "story_before",
             "covers": [0x060C74, 0x060D54, 0x060E34, 0x060EF0]},
            {"kind": "tool", "path": "tools/decode_story_script.py"},
            {"kind": "note", "path": "notes/story-script-vm.md"},
            {"kind": "dynamic", "path": "notes/evidence/story-vm-l2-20261020.md",
             "level": "L2",
             "need": ["0x080977BA", "0x08049E76", "0x0808F546", "0x00000036",
                      "0x49E76", "0x020311D4"],
             "address_required": False},
            {"kind": "dynamic", "path": "notes/evidence/story-scene-l3-20261020.md",
             "level": "L3",
             "need": ["伊鲁卡", "是啊，是我这个班主任所承认的嘛", "0x08049E76",
                      "story-scene-l3.png"],
             "address_required": False},
            {"kind": "dynamic", "path": L4_EVIDENCE_NOTE,
             "level": "L4",
             "need": ["55/55", "0x0808F752"],
             "address_required": False},
            {"kind": "tool", "path": "tools/mgba_probe/l4_battle_matrix.py",
             "need": ["0x0808F752"], "address_required": False},
            {"kind": "render", "tool": "tools/mgba_probe/render_screen.py",
             "artifact": "notes/evidence/story-scene-l3.png"},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/import_story_script.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
             "case": "story-vm-roots"},
        ],
        "corrections": [
            "44 条指令里 **38 条已由原生代码证明、6 条仍为推定** —— 2026-10-21 已全部定案："
            "6 个 helper 逐条反汇编完，字段语义已定，全部升为 `proved`（44/44）",
            "**L4 的「全流程」轴已达成 55/55**：每一场都能被调度到，"
            "且游戏实际使用的脚本指针与根表条目逐位相等"
            "（见 `notes/evidence/l4-playthrough-20261021.md`）",
        ],
        "value": 5, "effort": 3,
    },
    "ninjutsu-names": {
        "title": "忍具名表",
        "rom": 0x599634,
        "readonly": True,
        "probes": [
            {"kind": "fixture", "name": "ninjutsu_names", "covers": [0x599634]},
            {"kind": "tool", "path": "tools/extract_rewards.py"},
            {"kind": "note", "path": "notes/resource-locations.md"},
            {"kind": "dynamic",
             "path": "notes/evidence/ninjutsu-names-vm-20261022.md",
             "level": "L3",
             "need": ["0x0809734C", "0x08599634", "0x08097352", "0x08599758"],
             "address_required": False},
            {"kind": "tool", "path": "tools/mgba_probe/open_readers_sweep.py",
             "need": ["0x0809734C", "0x08599634"],
             "address_required": False},
        ],
        "unresolved": [],
        "value": 2, "effort": 3,
    },
    "font-segments": {
        "title": "字形段表 / 文本编码",
        "rom": 0x53D644,
        "probes": [
            {"kind": "tool", "path": "tools/konoha_font.py"},
            {"kind": "roundtrip", "path": "tools/font_roundtrip.py",
             "need": ["bytes_equal"]},
            {"kind": "note", "path": "notes/font-encoding.md"},
            {"kind": "dynamic", "path": "notes/evidence/text-encoding-l3-20261020.md",
             "level": "L3",
             "need": ["0x8142", "0x0813E209", "story-scene-l3.png",
                      "是啊，是我这个班主任所承认的嘛"],
             "address_required": False},
            {"kind": "render", "tool": "tools/mgba_probe/screen_text.py",
             "artifact": "notes/evidence/story-scene-l3.png"},
            {"kind": "dynamic", "path": L2_EVIDENCE_NOTE,
             "level": "L2",
             "need": ["0x08065EE6", "0x0853D644"],
             "address_required": False},
            {"kind": "tool", "path": "tools/l2_runtime_capture.py",
             "need": ["0x08065EE6"], "address_required": False},
        ],
        "writeback": [{"kind": "tool", "path": "tools/text_codec.py"}],
        "unresolved": [],
        "corrections": [
            "反向映射已从「取最小码位」改为**规范码**：基础 GB2312 序里的那个码"
            "（扩展块里的同字是冗余拼写，不规范）。"
            "证据与 5 条可证伪检验见 `notes/evidence/font-reverse-mapping-20261020.md`",
            "**「8 个字符两个码位」在字节级不再是歧义**（2026-10-21）："
            "ROM 的 **9141 个真实文本块**逐个做「码级 token 流 → 字节」往返，"
            "**9141/9141 逐字节相同**（含全部 794 个含双码位字符的块）。"
            "唯一且字节精确的表示是**码级 token 流**；"
            "`tools/text_codec.py::encode_tokens` 直接写码、不走「字符 → 码位」"
            "反查表，所以对两种拼写都精确。"
            "「字符 → 码位」只是方便层，在这 8 个字符上**必然有损**，"
            "规范码是**约定**而不是唯一解",
        ],
        "value": 5, "effort": 1,
    },
    "sprite-action-table": {
        "title": "精灵动作表",
        "rom": 0x596CCC,
        "probes": [
            {"kind": "tool", "path": "tools/sprite_frames.py"},
            {"kind": "note", "path": "notes/sprite-frame-format-20261020.md"},
            {"kind": "code", "path": "notes/sprite-frame-format-20261020.md",
             "need": ["0x596CCC", "0xFFFF"]},
            {"kind": "dynamic", "path": L2_EVIDENCE_NOTE,
             "level": "L2",
             "need": ["0x0806B76C", "0x08596CCC"],
             "address_required": False},
            {"kind": "tool", "path": "tools/l2_runtime_capture.py",
             "need": ["0x0806B76C"], "address_required": False},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/import_sprite_action.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
             "case": "sprite-action-table"},
        ],
        "unresolved": [],
        "corrections": [
            "ROM `0x25A8E5` 的字节已定为 **`0xFF`**：它是 4 字节终止符 "
            "`ff ff 00 00` 里 u16 `tile` 的高字节。把这一字节改成 `0xFF` 后，"
            "全 ROM 的完整终止符数量恰好 +1（复核：5546 → 5547），"
            "且合法的最大 tile 下标只有 **768**（`0xFBFF`=64511 超出取值域 84 倍）",
            "「帧描述符上限 32 片」**不是 ROM 约束**：实测单帧最多 **5** 片"
            "（分布 1 片 2562 / 2 片 70 / 3 片 26 / 5 片 16），触到 32 的条目为 0",
        ],
        "value": 3, "effort": 3,
    },
    "mechanism-effects": {
        "title": "机关效果表 / 拾取分派表 / 建立期分支",
        "rom": 0x0808136C,
        "readonly": True,
        "probes": [
            {"kind": "tool", "path": "tools/mechanism_map.py"},
            {"kind": "note", "path": "notes/mechanisms-20261020.md"},
            {"kind": "code", "path": "notes/mechanisms-20261020.md",
             "need": ["0x0808136C", "0x080815E4", "0x0806E868"]},
            {"kind": "dynamic",
             "path": "notes/evidence/mechanism-effects-l3-20261022.md",
             "level": "L3",
             "need": ["0x08081350", "0x0808136C", "0x0807498C", "0x08081544"],
             "address_required": False},
            {"kind": "tool", "path": "build/probe_items2.py",
             "need": ["0x08081350", "0x0808136C"],
             "address_required": False},
        ],
        "unresolved": [],
        "corrections": [
            "**这张表不是数据表，是 13 项函数指针跳转表**（2026-10-22）："
            "`0x08081350: ldr r1,[pc,#0x14]` 装 `0x0808136C`、"
            "`0x08081352/54/56` 算 `&表[下标]` 并 `mov pc, r0` —— "
            "Thumb-2 switch 惯用法，下标 = 传入值 - 1，必须落在 0..12。"
            "旧注记把它当「13 项效果表」是错的",
            "target 9 **根本到不了效果表**：`0x08081984` 先把它截走，"
            "走「两个剧情 VM 脚本 + 计数器 + 单位 `+0xCE += 25`」的分支；"
            "表槽 `0x0808138C → 0x080814CC` 是死代码",
            "target 11 是**空操作**：`0x08081394 = 0x080814CC`，"
            "直接落到共享收尾（关窗 → 播 `config[0]` BGM → 等按键），"
            "而且原版 46 关里一次都没用过 target 11",
            "type 5/6/7 **不决定脚本**，脚本由 target 决定："
            "`0x080815E4[4]=[5]=[6]=0x08081984` 共用一个处理分支；"
            "type 只决定运行时对象类型（3/4/5-6 ⇒ 精灵 + 拾取音效）",
            "旧结论「13 项效果表中 target 9/11 语义未定」**作废**",
            "**运行时读数已取得（2026-10-22）**：路线是"
            "剧情战斗 `fn 0x080732B4` → `0x0807498C` → `fn 0x08081544`"
            "（第二个关卡对象处理器，按 `record+4` 做 7 路分派）→ "
            "`0x08081ADE` → `fn 0x080812DC` → 读 `0x0808136C`。"
            "判定点 `0x08081350` 命中，`r2 = 1` = 机制下标（= `record[+6]`）。"
            "见 `notes/evidence/mechanism-effects-l3-20261022.md`",
        ],
        "value": 3, "effort": 3,
    },
    "text-writeback": {
        "title": "对白文本写回（字形码）",
        "rom": 0x461CE8,
        "probes": [
            {"kind": "tool", "path": "tools/extract_dialogue_full.py"},
            {"kind": "roundtrip", "path": "tools/verify_text_writeback.py",
             "need": ["font"], "address_required": False},
            {"kind": "note", "path": "notes/text-writeback-migration-20261020.md"},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/import_dialogue.py"},
            {"kind": "tool", "path": "tools/build_editor_db.py"},
        ],
        "unresolved": [],
        "corrections": [
            "`tools/find_sjis_blocks.py` 与 `tools/decode_dialogue_record.py` "
            "**已改用** `tools/text_codec.py`，不再依赖旧手工表 "
            "`sequel/content/text/sjis-to-tile-mapping.json`",
            "**「`sequel/editor.db` 被 gitignore ⇒ 纯净检出下 override 链空转」"
            "已解决**：新增 `tools/build_editor_db.py`，从仓库内容（"
            "`sequel/content/*/bank.json`）**重建**数据库，并当场验证"
            "「编辑器 → 构建」链真的产出补丁（实测 applied 5533 / rejected 549）；"
            "`--check` 模式会逐个生成器报 applied/rejected，"
            "「全部被拒」就是基址或字段名过期的信号。"
            "见 `notes/evidence/editor-db-override-chain-20261021.md`",
        ],
        "value": 5, "effort": 1,
    },
    "character-template": {
        "title": "角色定义表",
        "rom": 0x54241C,
        "probes": [
            {"kind": "tool", "path": "tools/character_templates.py"},
            {"kind": "code", "path": "notes/character-template-format-20261020.md",
             "need": ["0x54241C + id*0xB4", "62 条（id 1..62）"]},
            {"kind": "note", "path": "notes/character-template-format-20261020.md"},
            {"kind": "dynamic", "path": L2_EVIDENCE_NOTE,
             "level": "L2",
             "need": ["0x0806D984", "0x0854241C"],
             "address_required": False},
            {"kind": "tool", "path": "tools/l2_runtime_capture.py",
             "need": ["0x0806D984"], "address_required": False},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/import_character_template.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
             "case": "character-template"},
        ],
        "unresolved": [
            {"type": "field",
             "text": "12 字节头的 +0x00 / +0x07、以及 0x545458 记录里的 "
                     "+0x00/+0x01 与 +0x03/+0x0A/+0x0B/+0x0D/+0x0F 语义未定；"
                     "条目字节 4（pad）未定",
             "writeback_safe": True,
             "note": "notes/character-template-format-20261020.md",
             "need": ["0x54241C", "0xB4", "0x545458", "16 字节"]},
        ],
        "corrections": [
            "`0x545458` 已确认为 **16 字节忍术记录表**（87 条，下标 = 忍术 id），"
            "不是 u32 指针表 —— 旧结论作废，写回路径见 "
            "`tools/import_character_template.py`",
            "`+0x0A` 已由原生代码证明是**体力基数**（`0x0806DA46`），"
            "不再存疑",
            "仓库内已有可复现提取器 `tools/character_templates.py` 与往返自检"
            "（`tools/writeback_paths.py::character-template`）",
        ],
        "value": 4, "effort": 3,
    },
    "runtime-state": {
        "title": "运行时状态（WRAM 字段）",
        "rom": None,
        "readonly": True,
        "probes": [
            {"kind": "tool", "path": "tools/runtime_state.py"},
            {"kind": "note", "path": "notes/runtime-and-object-tables-20261020.md"},
            {"kind": "code", "path": "notes/runtime-and-object-tables-20261020.md",
             "need": ["0x020311EA", "0x020240C0"], "address_required": False},
            {"kind": "dynamic", "path": "notes/evidence/runtime-state-l3-20261020.md",
             "level": "L3",
             "need": ["0x020311EA", "0x02026805", "0x02022EF0", "54"],
             "address_required": False},
            {"kind": "tool", "path": "tools/runtime_capture.py",
             "need": ["0x02026804", "0x0202680C"], "address_required": False},
            {"kind": "dynamic",
             "path": "notes/evidence/runtime-state-story-config-20261022.md",
             "level": "L3",
             "need": ["0x08097C40", "0x020311ED", "0x08097E00", "0x0808F942"],
             "address_required": False},
            {"kind": "tool", "path": "tools/mgba_probe/runtime_state_probe.py",
             "need": ["0x08097C40", "0x020311ED"],
             "address_required": False},
        ],
        "unresolved": [],
        "corrections": [
            "运行时读数已闭环：`scene_id`（`0x020311EA`）在开场剧情里是 "
            "**54 → 50 → 40**，`battle_stage`（`0x02026805`）= 40、"
            "`battle_sub`（`0x02026806`）= 0、队伍槽 1（`0x02022EF0`）= "
            "角色 1（漩涡鸣人）等级 1",
            "旧推断「`0x020311EA` 是场景号」**已被运行时读数证实**",
            "**`story_config[0]` 的非零读数已闭合（2026-10-22）**：旧归因"
            "「由调度器 `0x0808F5C8` 写入、`0x0808F5CC` 随即清零，所以任何快照"
            "都拍不到」**归因错误** —— 逐指令核对显示 `0x0808F5C8` **只**在"
            "「before」路径上执行，而那条路径的前提正是 `state[0x18] == 0`，"
            "所以调度器**恒写 0**；真正的写入者是剧情 VM 的 **opcode `0x1F`**"
            "（`0x08097C40: strb r0,[r1,#0x19]`，操作数 = 战斗 sub-config）。"
            "场景 **2/3/4/6/7** 的 before 脚本都用 `1F 01`，因此游戏自己会写 "
            "**1**。实测（`tools/mgba_probe/runtime_state_probe.py`，场景 2 + "
            "作答行 1）：`0x08097C40` 命中、`r0 = 1`、内存 `0x020311ED` = "
            "**`0x01`** ⇒ 非零读数成立。见 "
            "`notes/evidence/runtime-state-story-config-20261022.md`",
            "`story_progress` = `0x020311E4`（u16，VM 的「设进度」opcode 在 "
            "`0x08097BD4` 置成绝对值；调度器在 `0x0808F5E0` 跟 **360** 比较）；"
            "`story_branch` = `0x020311EC`（u8，调度器在 `0x0808F5A0` 读它来选"
            "「after」根表，`0x0808F5CC` 清零；**场景 31** 读出 **1**）；"
            "`story_config` = `0x020311ED..EF`",
        ],
        "value": 4, "effort": 2,
    },
    # ---- banks that carry real evidence ----------------------------------
    "positions": {
        "title": "战斗角色槽 / 编成表",
        "rom": 0x5461C4,
        "bank": "positions",
        "probes": [
            {"kind": "fixture", "name": "battle_actors", "covers": [0x5461C4]},
            {"kind": "tool", "path": "tools/extract_positions.py"},
            {"kind": "note", "path": "notes/battle-tables.md"},
            {"kind": "dynamic", "path": "notes/wasm-formation-probe-result-20260710.md",
             "level": "L3", "need": ["runtimePositions", "0x588CA8", "\"unique\": true"],
             "address_required": False},
            {"kind": "dynamic", "path": L4_EVIDENCE_NOTE,
             "level": "L4",
             "need": ["85/85", "0x085461C4", "0x020240C0"],
             "address_required": False},
            {"kind": "tool", "path": "tools/mgba_probe/l4_battle_matrix.py",
             "need": ["0x085461C4"], "address_required": False},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/build_db_patches.py",
             "need": ["rom_positions"]},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK, "case": "positions"},
        ],
        "unresolved": [
            {"type": "field",
             "text": "group/variant 等索引字段名仍是暂定名（槽内 +0x00/+0x01/+0x04/+0x0F 已证）",
             "writeback_safe": True,
             "note": "notes/addresses.md",
             "need": ["group", "variant", "0x5461C4"]},
        ],
        "corrections": [
            "索引字段名已由消费者代码定名：`group_id`→**battle_stage**（`ctrl[1]`，步长 `0x1AAC`）、"
            "`variant_id`→**battle_sub**（`ctrl[2]`，步长 `0x8E4`）、"
            "`record_id`→**actor_slot**（0..11，`0xB8`）、"
            "`selector`→**character_id**（`+0x00`）、`aux_u32`→**unit_flags**（`+0x08`，bit0 = 阵营）、"
            "`+0x02/+0x03`→**spawn_x/spawn_y**、`+0x04`→**facing**",
        ],
        "value": 5, "effort": 2,
    },
    "battle-config": {
        "title": "技能表（bank 名为 battle-config）",
        "rom": 0x545458,
        "bank": "battle-config",
        "probes": [
            {"kind": "fixture", "name": "skill_table", "covers": [0x545458]},
            {"kind": "tool", "path": "tools/character_templates.py"},
            {"kind": "note", "path": "notes/character-template-format-20261020.md"},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/import_character_template.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK, "case": "battle-config"},
        ],
        "corrections": [
            "`0x545458` 已确认为 16 字节记录表（87 条），不是 u32 指针表 —— "
            "旧结论作废，写回路径见 `tools/import_character_template.py`",
        ],
        "unresolved": [],
        "value": 3, "effort": 2,
    },
    "sprite-frame-descriptors": {
        "title": "精灵帧描述符表（0x53EE98，10 字节步长）",
        "rom": 0x53EE98,
        "readonly": True,
        "probes": [
            {"kind": "note", "path": "notes/evidence/units-offset-table-20261020.md"},
            {"kind": "tool", "path": "tools/frame_descriptors.py"},
            {"kind": "code", "path": "notes/evidence/units-offset-table-20261020.md",
             "need": ["0x53EE98", "10 字节", "0x080806BA", "0x0808077E", "0x0808082E"],
             "address_required": False},
            {"kind": "dynamic",
             "path": "notes/evidence/fonts-spriteframe-l3-20261022.md",
             "level": "L3",
             "need": ["0x080806BA", "0x0853EE98", "0x0853EEA2", "0x0853EED4"],
             "address_required": False},
            {"kind": "tool", "path": "tools/mgba_probe/unitslot_probe.py",
             "need": ["0x080806BA", "0x0853EE98"],
             "address_required": False},
        ],
        "unresolved": [
            {"type": "field",
             "text": "五个 u16 字段（+0 类别/链表结束、+2/+4 有符号量、+6 类别、"
                     "+8 结束标志）的业务名未定",
             "writeback_safe": True,
             "note": "notes/evidence/units-offset-table-20261020.md",
             "need": ["0x53EE98", "0x53EF2E"]},
        ],
        "corrections": [
            "这张表此前**完全没有被登记**：它在 ROM 里有 3 个原生读者"
            "（`0x080806BA` / `0x0808077E` / `0x0808082E`），"
            "步长 10 字节、15 条记录（`0x53EE98`..`0x53EF2E`）",
            "它之所以查不到，是因为 `notes/evidence/consumer-evidence.json` "
            "只存了 54 张表，而字面量索引有 18051 个值（1196 个是活的）—— "
            "邻域分析必须查全量索引",
            "暂列**只读参考**：五个字段的业务名都还没定，写它没有可写的已知字段",
            "**运行时读数已取得（2026-10-22）**：读者 `fn 0x08080670` 在"
            "`--force-dispatch` 路线上命中，判定点 `0x080806BC` 处 "
            "`r1 = 0x0853EE98`（表基址）、`r4 = 0x0853EEA2 / 0x0853EEB6 / "
            "0x0853EED4` = **基址 + 下标 × 10**，**步长 10 字节得到运行时证实**。"
            "见 `notes/evidence/fonts-spriteframe-l3-20261022.md`",
        ],
        "value": 3, "effort": 3,
    },
    "cutscene-scripts": {
        "title": "关卡数据块表（bank 名为 cutscene-scripts）",
        "rom": 0x53DF70,
        "bank": "cutscene-scripts",
        "probes": [
            {"kind": "tool", "path": "tools/cutscene_block.py"},
            {"kind": "note", "path": "notes/evidence/cutscene-block-format-20261020.md"},
            {"kind": "code", "path": "notes/evidence/cutscene-block-format-20261020.md",
             "need": ["0x08072F0C", "0x06016000", "0x05000380", "svc #0x12"],
             "address_required": False},
            {"kind": "dynamic", "path": L2_EVIDENCE_NOTE,
             "level": "L2",
             "need": ["0x08072F0C", "0x0853DF70"],
             "address_required": False},
            {"kind": "tool", "path": "tools/l2_runtime_capture.py",
             "need": ["0x08072F0C"], "address_required": False},
            {"kind": "dynamic",
             "path": "notes/evidence/cutscene-scripts-l3-20261022.md",
             "level": "L3",
             "need": ["0x08072F0E", "0x0853DF70", "0x0808F94A", "0x0118"],
             "address_required": False},
            {"kind": "tool", "path": "tools/mgba_probe/phase_sweep.py",
             "need": ["0x08072F0E", "0x0853DF70"],
             "address_required": False},
            {"kind": "note", "path": "notes/evidence/writeback-paths-20261020.md"},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/import_battle_config.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
             "case": "cutscene-scripts"},
        ],
        "corrections": [
            "`0x53DF70` **不是剧情 VM 脚本表**，而是**关卡数据块表**："
            "**4 项 × 8 字节**，每项一对指针（LZ77 4bpp 图块 → VRAM `0x06016000`、"
            "LZ77 16 色调色板 → 调色板 RAM `0x05000380`），"
            "由 BIOS `svc 0x12`（LZ77UnCompVram）解压 —— "
            "剧情 VM 从头到尾没碰过这些块",
            "旧结构库「16 项 × u32」**作废**：原生步长是 8 字节；"
            "旧的 16 槽模型允许下标越过表尾写进下一张表（`0x53DFB0`）",
            "**「这四块对应哪四张原版战斗地图」的前提已被证伪**（2026-10-21）："
            "四个块用 BIOS `svc 0x12` 解压出 **4096/4096/4096/2048 字节**"
            "（= 128/128/128/64 张 4bpp 图块），而 47 个战斗地图描述符的"
            "原图图块集只有 **156–276 字节（4–8 张图块）**；"
            "把每张地图的图块集逐张（32 字节）对上四个块的图块集合，"
            "**一张都匹配不上**。所以它们是**关卡/过场自己的 4bpp 图块集**，"
            "不是战斗地图的图块集",
            "**加载器已被自然触发（2026-10-22）** —— 旧注记「55 个剧情场景、"
            "开机流程、真实战斗里加载器一次都没命中，属于剧情/战斗之外的第四种模式，"
            "本轮探针能到达的范围内无法触发」**作废**："
            "**相位 `0x0118`**（`0x0808F94A`：置战斗标志 bit 1 → `bl 0x080732B4` "
            "跑剧情战斗 → 清标志）就能命中判定点 `0x08072F0E`，"
            "此时 **`r4 = 0x0853DF70`**、表首 32 字节被 dump 出"
            "（4 条 8 字节记录，word0 = ROM 源地址 `0x0812xxxx`）。"
            "同时更正：**表读取没有前提条件** —— `0x08072EEE` 处的 "
            "`cmp r2,#0 / beq 0x08072F0C` 只决定要不要顺手置标志，"
            "`beq` 直接跳到装载指令，两条路径都会读表。"
            "见 `notes/evidence/cutscene-scripts-l3-20261022.md`",
        ],
        "unresolved": [],
        "value": 3, "effort": 3,
    },
    # ---- banks that are aliases or contradicted ---------------------------
    "audio": {
        "title": "音频 bank（已退役：0x53F138 与音频无关）",
        "rom": 0x53F138,
        "bank": "audio",
        "probes": [
            {"kind": "tool", "path": "tools/consumer_locate.py"},
            {"kind": "note", "path": "notes/legacy-table-base-correction-20261020.md"},
        ],
        "corrections": [
            "**已退役**（`tools/table_registry.py::RETIRED`）："
            "`0x53F138` 处是 `0x53F140` 指针数组头部的 2 个代码指针"
            "（场景对象/motion/callback 描述符），与音频无关；"
            "本 bank 的 Sappy 叙事整体作废。真正的 sound-ID 表在 `0x465B70`"
            "（见 sound-id-table 行）",
        ],
        "retired": True,
        "unresolved": [],
        "value": 3, "effort": 2,
    },
    "palettes": {
        "title": "调色板 bank（已退役：是 map-sprites 的别名窗口）",
        "rom": 0x53F138,
        "bank": "palettes",
        "probes": [
            {"kind": "tool", "path": "tools/consumer_locate.py"},
            {"kind": "note", "path": "notes/legacy-table-base-correction-20261020.md"},
        ],
        "corrections": [
            "**已退役**（`tools/table_registry.py::RETIRED`）："
            "`0x53F138` 只是 `0x53F140` 起的 86 项 u32 指针数组"
            "头部 2 个代码指针的窗口；那里不是 RGB555 调色板。"
            "真正的调色板数据在 `0x05000380`（VRAM 调色板 RAM，"
            "由 `0x53DF70` 关卡数据块经 BIOS `svc 0x12` 解压写入）",
        ],
        "retired": True,
        "unresolved": [],
        "value": 2, "effort": 3,
    },
    "items": {
        "title": "道具/技能记录表（0x545BE4，与 skills 同址）",
        "rom": 0x545BE4,
        "bank": "items",
        "readonly": True,
        "probes": [
            {"kind": "tool", "path": "tools/legacy_rebase.py"},
            {"kind": "note",
             "path": "notes/evidence/legacy-rebase-nearby-20261020.md"},
            {"kind": "code",
             "path": "notes/evidence/legacy-rebase-nearby-20261020.md",
             "need": ["0x545BE4"], "address_required": False},
            {"kind": "dynamic",
             "path": "notes/evidence/items-skills-l3-20261022.md",
             "level": "L3",
             "need": ["0x0806D91A", "0x08545BE4", "0x08083812", "0x0202D4CD"],
             "address_required": False},
            {"kind": "tool", "path": "build/probe_items2.py",
             "need": ["0x0806D91A", "0x08545BE4"],
             "address_required": False},
        ],
        "unresolved": [
            {"type": "field",
             "text": "记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，"
                     "来源已作废）",
             "writeback_safe": True,
             "note": "notes/evidence/legacy-rebase-nearby-20261020.md",
             "need": ["0x545BE4"]},
        ],
        "corrections": [
            "旧基址 `0x546100` 是这张表的**第 81 条 + 12 字节**的错位窗口；"
            "真基址是 `0x545BE4`（16 字节/条，94 条，7 个原生读者），"
            "表尾正好接战斗编成矩阵 `0x5461C4`",
        ],
        "value": 2, "effort": 3,
    },
    "skills": {
        "title": "技能 bank（0x546100，与 items 同址）",
        "rom": 0x545BE4,
        "bank": "skills",
        "readonly": True,
        "probes": [
            {"kind": "tool", "path": "tools/legacy_rebase.py"},
            {"kind": "note",
             "path": "notes/evidence/legacy-rebase-nearby-20261020.md"},
            {"kind": "code",
             "path": "notes/evidence/legacy-rebase-nearby-20261020.md",
             "need": ["0x545BE4"], "address_required": False},
            {"kind": "dynamic",
             "path": "notes/evidence/items-skills-l3-20261022.md",
             "level": "L3",
             "need": ["0x0806D91A", "0x08545BE4", "0x08083812", "0x0202D4CD"],
             "address_required": False},
            {"kind": "tool", "path": "build/probe_items2.py",
             "need": ["0x0806D91A", "0x08545BE4"],
             "address_required": False},
        ],
        "unresolved": [
            {"type": "field",
             "text": "记录里各个 u16 字段的业务名未定（旧字段名来自错位窗口，"
                     "来源已作废）",
             "writeback_safe": True,
             "note": "notes/evidence/legacy-rebase-nearby-20261020.md",
             "need": ["0x545BE4"]},
        ],
        "corrections": [
            "旧基址 `0x546100` 是这张表的**第 81 条 + 12 字节**的错位窗口；"
            "真基址是 `0x545BE4`（16 字节/条，94 条，7 个原生读者）",
            "与 `items` 同址已裁决：同一张表，规范名 `skills`",
        ],
        "value": 2, "effort": 3,
    },
    "encounter-zones": {
        "title": "遭遇区 bank（0x53D910，与 maps 同址）",
        "rom": 0x53D910,
        "bank": "encounter-zones",
        "probes": [
            {"kind": "tool", "path": "tools/consumer_locate.py"},
            {"kind": "note", "path": "notes/legacy-table-base-correction-20261020.md"},
        ],
        "corrections": [
            "与 `maps` 同称 `0x53D910`：已裁决为**同一张表**的别名，规范名 `maps`",
            "旧结论「地图描述符从 `0x53D914` 起」**作废** —— 那是旧逻辑的错误基址；"
            "原生 loader `0x08069040` 直接以 `0x0853D910` 为基址、步长 32 字节，"
            "首条目就是 `0x53D910`（见 `notes/battle-config-unsafe-template-fix-20260710.md`）",
        ],
        "unresolved": [],
        "writeback": [
            {"kind": "tool", "path": "tools/import_battle_config.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
             "case": "encounter-zones"},
        ],
        "value": 2, "effort": 3,
    },
    "sappy-engine": {
        "title": "Sappy 引擎 bank（0x079668，已被证伪）",
        "rom": 0x079668,
        "bank": "sappy-engine",
        "probes": [
            {"kind": "tool", "path": "tools/consumer_locate.py"},
            {"kind": "note", "path": "notes/legacy-table-base-correction-20261020.md"},
        ],
        "corrections": [
            "**已退役**（`tools/table_registry.py::RETIRED`）："
            "0x08079668 已证实是文本/消息对象分派函数，不是 Sappy 音频分发器；"
            "bank 里的 command_handlers / event_audio_mapping 结论作废",
        ],
        "retired": True,
        "unresolved": [],
        "value": 3, "effort": 2,
    },
    "sprite-animations": {
        "title": "精灵动作表（0x596CCC，id*144 + action*16）",
        "rom": 0x596CCC,
        "bank": "sprite-animations",
        "probes": [
            {"kind": "tool", "path": "tools/consumer_locate.py"},
            {"kind": "note", "path": "notes/legacy-table-base-correction-20261020.md"},
        ],
        "corrections": [
            "旧基址 0x53F200 是 0x53F140 起的指针数组第 48 项起的 38 字节窗口，"
            "不是独立表；真实基址 0x596CCC 有 18 个原生读者，"
            "条目 = 4 个 u32 指针 (frames, animations, gfx, palette)",
            "本 bank 与 `sprite-action-table` 是同一张表；写回路径与判死检验"
            "统一走 `sprite-action-table`（见 tools/writeback_paths.py 的 "
            "`sprite-action-table` case），本行只作别名留档",
        ],
        "readonly": True,
        "unresolved": [],
        "value": 2, "effort": 3,
    },
}

# Structures that only exist as a legacy bank: no proof probe is declared, so
# the audit reports them as `none` rather than inheriting the bank's own
# `static_verified` label.
LEGACY_BANK_ONLY = {
    "battle-encounters": [{"type": "relation",
                           "text": "与 0x5461C4 编成表的关系未裁决"}],
    "character-stats": [{"type": "relation",
                         "text": "与 0x54241C 角色模板的关系未裁决"}],
    "character-stats-b": [{"type": "relation",
                           "text": "与 0x54241C 角色模板的关系未裁决"}],
    "cutscene-scripts": [],
    "levels": [{"type": "relation",
                "text": "与 0x545068 逐角色技能表的关系未裁决"}],
    "map-sprites": [
        {"type": "field",
         "text": "描述符记录内部字段名未定。已收窄：记录**变长自描述**"
                 "（实测 12 或 28 字节交替），不是旧笔记说的「11 个字」；"
                 "每条以一个 u32 ROM 指针开头，末尾带下一条记录的地址",
         "writeback_safe": True,
         "note": "notes/evidence/units-offset-table-20261020.md",
         "need": ["0x53F140", "0x0812F5B0", "变长自描述"]},
    ],
    "resource-pointers": [],
    "save-state": [],
    "story": [{"type": "relation",
               "text": "旧剧情表 0x53636C 与剧情 VM 根表不是同一张"}],
    "story-b": [{"type": "relation", "text": "旧剧情表，身份未裁决"}],
    "story-c": [{"type": "relation", "text": "旧剧情表，身份未裁决"}],
    "story-d": [{"type": "relation", "text": "旧剧情表，身份未裁决"}],
    "story-e": [{"type": "relation", "text": "旧剧情表，身份未裁决"}],
    "units": [],
}

# Facts that used to sit in the open-item list and have since been settled.
# They are kept so that a conclusion change stays on the record (AGENTS.md
# rule 5) instead of silently disappearing.
LEGACY_CORRECTIONS = {
    "map-sprites": [
        "权威基址 `0x53F140`（86 项 u32 指针表）；bank 里的 `0x53F1DC` 是它的第 39 项窗口",
    ],
    "resource-pointers": [
        "消费者已定位（`0x0807B220`，fn `0x0807AE04`）；该 bank 是精灵动作表 "
        "`0x596CCC` + `0x240` 的窗口，不是独立的资源指针表",
    ],
    "save-state": [
        "`0x53D848` 已证实是 **WRAM 分配表**（10 组 `{u32 wram_addr, u32 size}`，"
        "4 个原生读者 `0x0806869A / 0x08068954 / 0x08068CC0 / 0x08068D98`），"
        "**不是**存档描述符表 —— 存档数据在 SRAM，不在 ROM",
    ],
    "units": [
        "`0x53F298` **不是**「u16[64] 角色 ID 表」，而是 **43 项的 u16 重映射表**"
        "（{0..48} 去掉 {14,15,16,17,19,20} 的排列）；旧框架还横跨了"
        "`0x53F2EE`（16 项有符号增量表，读者 `0x08080AE0`）与 `0x53F318`（代码指针表）"
        "另外两张结构",
        "消费者的取值方式已由原生代码证明：表值 **加上 WRAM `0x0202CA24` 的 u16**"
        "（运行时值）后 **掩到 16 位** ⇒ 目标是 64 KB 窗口内的索引。"
        "2026-07-11 笔记提出的可证伪判据「是否加到某个基址上」**已证实**；"
        "因为基址是运行时量，写回仍须限制在原生出现过的取值内 —— "
        "见 `notes/evidence/units-offset-table-20261020.md`",
    ],
}

# Legacy banks that DO have an executable write-back path.  The key is the
# case name registered in `tools/writeback_paths.py`; the case's own base
# address is cross-checked against the bank's declared table offset, so a
# path can never be credited to the wrong table.
LEGACY_WRITEBACK = {
    "cutscene-scripts": "cutscene-scripts",
    "map-sprites": "map-sprites",
    "resource-pointers": "resource-pointers",
    "save-state": "save-state",
    "units": "units",
}

# A write-back case may target a *window* of the structure's table rather
# than its base.  The audit cross-checks the case address against the
# structure's base, so the window address has to be declared.
LEGACY_WRITEBACK_BASE = {
    # resource-pointers was re-pointed at the sprite-action table
    # (0x596CCC); its write-back case edits the +0x240 window.
    "resource-pointers": 0x596F0C,
}

# Legacy banks whose identity was re-established in 2026-10-21.  They get
# their own probes instead of the generic "zero reference" pair, because
# they are now known structures with native readers.
LEGACY_REIDENTIFIED = {
    "story": (0x536368, 1, "audio-song-1"),
    "story-b": (0x536BC4, 2, "audio-song-2"),
    "story-c": (0x538FEC, 8, "audio-song-8"),
    "story-d": (0x53AB74, 11, "audio-song-11"),
    "story-e": (0x53C3BC, 14, "audio-song-14"),
    "character-stats": (0x545068, None, None),
    "character-stats-b": (0x545068, None, None),
    "levels": (0x5459C8, None, None),
    "items": (0x545BE4, None, None),
    "skills": (0x545BE4, None, None),
    "battle-encounters": (0x54229C, None, None),
}

# Where the proof for each re-identified legacy bank is written down.
LEGACY_REIDENTIFIED_NOTE = {
    "battle-encounters": "notes/evidence/remaining-rebase-leads-20261021.md",
}

# 2026-10-21: the last nine legacy banks were re-pointed to the base a NATIVE
# READER actually loads.  They are read-only references (their record fields
# have no business names yet), so they get their own title, proof note and
# correction text instead of the generic "zero reference" pair.
#
#   bank -> (base, title, reader, corrections)
LEGACY_REBASE_NOTE = "notes/evidence/legacy-rebase-final-20261021.md"
LEGACY_REBASE = {
    "resource-pointers": (
        0x596CCC,
        "资源指针表（0x596CCC，与精灵动作表同址；旧基址 0x596F0C 是其 +0x240 窗口）",
        "0x0806B76C",
        "2026-10-22：旧基址 `0x596F0C` 是精灵动作表 `0x596CCC` 的第 36 项窗口"
        "（+0x240），**不是独立的资源指针表**；全 ROM 里 `0x596F0C` 只出现一次"
        "（池项 `0x0807B278`），由 `0x0807B220` 装载，而该指令在 "
        "`fn 0x0807AE04` 的 **case 7** 里 —— case 7 只能由 `arg1 = 7` 进入，"
        "两个 `arg1 = 7` 的调用点（`0x0807C3D6` / `0x0807C4D6`）都在 "
        "`fn 0x0807B8B8` 的循环里，该循环入口把 `r8` 硬编码成 2，"
        "`0x0807C4CC: cmp r0,#1` 永远失败 ⇒ **两处都是死代码**。"
        "运行时阴性对照（20 场剧情战斗）：同路线 items 读者命中 72 次，"
        "资源读者 0 次、`arg1=7` 调用点 0 次。"
        "⇒ 本 bank 按 `LEGACY_REBASE` 的先例重定基址到 `0x596CCC`"
        "（有活着的原生读者 `0x0806B76C` 真正装载的那个基址），"
        "与 `sprite-animations` / `sprite-action-table` 同址；"
        "旧结论「唯一原生读者是 `0x0807B220`」**作废**。"
        "详见 `notes/evidence/resource-pointers-deadcode-20261022.md`"),
    "battle-handlers": (
        0x53E698, "处理程序分派表（0x53E698，8 字节/条 x 256）", "0x0807F934",
        "旧基址 0x53E6D8 是本表第 8 条起、只读每条第一个 u32 的错位窗口；"
        "真实基址 0x53E698 有 2 个原生读者（决策点 0x0807F934 与 0x0807FD36），"
        "表尾正好接精灵帧描述符表 0x53EE98。"
        "2026-10-21 更正：消费者不是 fn 0x0807F414（它不读本表）；"
        "两个派发点都用 **同一个 u8 索引字节 0x02027350**，"
        "0x0807FD36 处是 'ldrb r0,[sb+0x770]' -> '*8' -> 'ldr' -> 'bl 0x0809C114'"),
    "map-events": (
        0x53E698, "处理程序分派表（同表，0x53E698 另一个窗口）", "0x0807F934",
        "旧基址 0x53EB08 = 0x53E698 + 142*8，是 8 字节记录按 4 字节步长读出来的窗口；"
        "map-events 与 battle-handlers 是同一张表"),
    "fonts": (
        0x53E596, "字宽表（0x53E596，1 字节/条 x 256，按字符码索引）",
        "0x0807F0FC",
        "旧基址 0x53E5B4 晚了 30 字节；唯一原生读者 0x0807F0FC 用 'ldrb' 取字符码后"
        "加到 0x0853E596 取宽度，所以表长是 256（与字符码一一对应）。"
        "2026-10-21 更正：旧笔记说「消费者是 fn 0x0807EE50」**不成立** —— "
        "fn 0x0807EE50 读的是另一张表 0x0853E328（字形度量，6 字节/字形）；"
        "0x0853E596 全 ROM 只有 1 处字面量引用（0x0807F114），消费者函数是 0x0807F064 起的那段。"
        "索引字节与 battle-handlers 共用：u8 @ 0x02027350"),
    "data-table-a": (
        0x5A143C, "数据指针表 A（0x5A143C，u32 ROM 指针 x 46）", "0x0808A6BA",
        "旧基址 0x5A14A4 = 0x5A143C + 26*4；46 项全部是 ROM 指针。"
        "2026-10-21 补充：本表有 **2 个**字面量读者 0x0808A704 与 0x0808B214，"
        "旧笔记只记了后者"),
    "data-table-b": (
        0x5A2034, "数据指针表 B（0x5A2034，u32 x 90）", "0x080985D8",
        "旧基址 0x5A2120 = 0x5A2034 + 59*4；90 项里 79 项是 ROM 指针"),
    "menu-ui": (
        0x5A4DEC, "头像指针表（0x5A4DEC，40 字节/条 x 63）", "0x08096158",
        "旧基址 0x5A5774 = 0x5A4DEC + 61*40，是头像表第 61..62 行的窗口，"
        "不是独立的菜单 UI 表；读者 0x08096158 按 id*40 + expr*8 索引"),
    "function-pointers": (
        0x53D5F0, "函数指针表（0x53D5F0，13 槽 u32）", "0x08061DD4",
        "旧基址 0x53D5F4 是槽 1；槽 0 与槽 12 是 FFFFFFFF 哨兵，槽 1..11 是 11 个"
        "代码指针（0x08061C8D 起每槽 +12 字节等距）"),
    "tile-assets": (
        0x5A320C, "图块/精灵资源记录表（0x5A320C，68 字节/条 x 79）", "0x0809881E",
        "旧基址 0x5A3218 是记录 0 的 +0x0C 指针块窗口（6 个 u32），不是表基址；"
        "记录数 79 由「指针块结构在 0x5A4708 处干净断裂」确定。"
        "2026-10-21 补充：本表有 **9 个**字面量读者"
        "（0x08087E30 / 0x0809851C / 0x08098840 / 0x08098AF0 / 0x08098DB0 / "
        "0x08098FC0 / 0x08099464 / 0x08099698 / 0x08099D10），旧笔记只记了 2 个"),
}

# 2026-10-21 (later): the callback-table dispatch points are located at
# instruction level (notes/evidence/callback-dispatch-tables-20261021.md).
#
# The first breakpoint census claimed that **none** of them fires on the
# battle / story / save routes, and concluded that the tables belong to a
# fourth "level / cutscene" mode.  That conclusion is **withdrawn**
# (notes/evidence/callback-dispatch-runtime-20261021.md): the census had a
# tool bug (the key release only ran when no breakpoint fired, so the game
# never saw a press edge and the battle intro never advanced), and the
# dispatch gate `fn 0x0806DF88` compares `unit[0xC0] & 1` against a side
# byte that is 0x0E/0x0F during a battle -- so it can never open by
# itself.  Five structures are now closed by that route (see
# CALLBACK_DISPATCH_L2); the ones listed here are the structures whose
# readers live in a *different* subsystem and still need their own route.
CALLBACK_DISPATCH_BLOCKED = {
    "resource-pointers", "items", "skills",
    "data-table-a", "tile-assets", "battle-encounters",
    "mechanism-effects", "mission-text", "text-writeback",
}

# The re-pointed banks that ALSO have L2 runtime evidence (a breakpoint hits
# the native consumer and the registers correspond to the fields).
LEGACY_REBASE_L2 = {
    "data-table-b": ("0x080985D8", "0x085A2034"),
    "function-pointers": ("0x08061DD4", "0x0853D5F0"),
    # 2026-10-22: the old base 0x08596F0C is a window of the sprite-action
    # table (0x08596CCC + 0x240) and its only native reference
    # (0x0807B220) sits in unreachable code -- see
    # notes/evidence/resource-pointers-deadcode-20261022.md
    "resource-pointers": ("0x0806B76C", "0x08596CCC"),
}

# 2026-10-22: the re-pointed banks that reached L3 through the **handler
# table** route.  `fn 0x0807F414` dispatches the 256 x 8 byte record table
# `0x0853E698` -- each record is `(handler_A, handler_B)` -- and the entry is
# selected by a u8 at `base + 0x770` (measured at runtime as `0x02027428`).
# 168 of the 256 records have `fn 0x0807F064` (the reader of the glyph width
# table `0x0853E596`) as their B slot.
LEGACY_REBASE_L3 = {
    "fonts": ("notes/evidence/fonts-spriteframe-l3-20261022.md",
              ["0x0807F108", "0x0853E596", "0x0853E635"],
              ("tools/mgba_probe/unitslot_probe.py",
               ["0x0807F108", "0x0853E596"])),
    "resource-pointers": (
        "notes/evidence/resource-pointers-deadcode-20261022.md",
        ["0x0807B220", "0x08596F0C", "0x0806B76C", "0x08596CCC"],
        ("build/probe_items2.py", ["0x0807B220", "0x08596F0C"])),
}

# The callback-table dispatch points, proven reachable on 2026-10-21.
# The gate is `fn 0x0806DF88` (called from the battle turn case at
# 0x080736DE): it only dispatches when a unit slot holds a real character
# and `unit[0xC0] & 1 == ctrl[10]`.  `ctrl[10]` is 0x0E/0x0F during a
# battle, so the comparison can never hold -- the gate was opened with a
# documented WRAM-only intervention (see the note).  The evidence is the
# game's own reader instructions executing and dumping the table bytes.
CALLBACK_DISPATCH_NOTE = "notes/evidence/callback-dispatch-runtime-20261021.md"
CALLBACK_DISPATCH_GATE = "tools/mgba_probe/unitslot_probe.py"

# structure -> (dispatch instruction, the table it reads)
CALLBACK_DISPATCH_L2 = {
    "battle-handlers": ("0x0807F414", "0x0853E698"),
    "map-events": ("0x0807AA8C", "0x0853E698"),
    "map-sprites": ("0x08080B12", "0x0853F140"),
    "units": ("0x08080B32", "0x0853F298"),
    "levels": ("0x0806DDD6", "0x085459C8"),
}

# ---------------------------------------------------------------------------
# Batch probes: runtime evidence that lives in one note per level.
#
# Adding a structure here is enough to wire the probe -- the note path and the
# evidence markers are data, not code.  The note must contain every marker in
# `need`, and the executable gate that produced it is listed in `tool`.
#
#   structure key -> (note path, [markers], gate tool)
# ---------------------------------------------------------------------------
L2_BATCH_PROBES: dict[str, tuple[str, list[str], str]] = {
    "character-stats": ("notes/evidence/l2-runtime-evidence-20261021.md",
                        ["0x0806D98C", "0x08545068"],
                        "tools/l2_runtime_capture.py"),
    "character-stats-b": ("notes/evidence/l2-runtime-evidence-20261021.md",
                          ["0x0806D98C", "0x08545068"],
                          "tools/l2_runtime_capture.py"),
    "levels": ("notes/evidence/l2-runtime-evidence-20261021.md",
               ["0x0806DB14", "0x085459C8"],
               "tools/l2_runtime_capture.py"),
    "encounter-zones": ("notes/evidence/l2-runtime-evidence-20261021.md",
                        ["0x08069040", "0x0853D910"],
                        "tools/l2_runtime_capture.py"),
    "positions": ("notes/evidence/l2-runtime-evidence-20261021.md",
                  ["0x0806E1F0", "0x085461C4"],
                  "tools/l2_runtime_capture.py"),
    "save-state": ("notes/evidence/l2-runtime-evidence-20261021.md",
                   ["0x0806869A", "0x0853D848"],
                   "tools/l2_runtime_capture.py"),
    "story-background-table": ("notes/evidence/l2-runtime-evidence-20261021.md",
                               ["0x08088372", "0x0859903C"],
                               "tools/l2_runtime_capture.py"),
    "sprite-action-table": ("notes/evidence/l2-runtime-evidence-20261021.md",
                            ["0x0806B76C", "0x08596CCC"],
                            "tools/l2_runtime_capture.py"),
    "sprite-animations": ("notes/evidence/l2-runtime-evidence-20261021.md",
                          ["0x0806B76C", "0x08596CCC"],
                          "tools/l2_runtime_capture.py"),
    # 2026-10-21 batch 4: the m4a SongHeaders are reached through the sound-id
    # table (they have no literal reader of their own), and two structures that
    # were stuck behind a wrong branch got a reachable consumer.
    "story-b": ("notes/evidence/l2-batch4-20261021.md",
                ["0x0809B242", "0x08536BC4"],
                ("tools/l2_runtime_capture.py", ["0x0809B242"])),
    "story-c": ("notes/evidence/l2-batch4-20261021.md",
                ["0x0809B242", "0x08538FEC"],
                ("tools/l2_runtime_capture.py", ["0x0809B242"])),
    "story-d": ("notes/evidence/l2-batch4-20261021.md",
                ["0x0809B282", "0x0853AB74"],
                ("tools/l2_runtime_capture.py", ["0x0809B282"])),
    "story-e": ("notes/evidence/l2-batch4-20261021.md",
                ["0x0809B25C", "0x0853C3BC"],
                ("tools/l2_runtime_capture.py", ["0x0809B25C"])),
    "mission-text": ("notes/evidence/l2-batch4-20261021.md",
                     ["0x080884F8", "0x08348DAC"],
                     "tools/l2_runtime_capture.py"),
    "tile-assets": ("notes/evidence/l2-batch4-20261021.md",
                    ["0x0809845C", "0x085A320C"],
                    "tools/l2_runtime_capture.py"),
}
L3_BATCH_PROBES: dict[str, tuple[str, list[str], str]] = {
    "character-template": ("notes/evidence/l3-evidence-20261021.md",
                           ["0x020240C0", "0x0854241C", "0xB4"],
                           "tools/mgba_probe/l3_evidence_sweep.py"),
    "encounter-zones": ("notes/evidence/l3-evidence-20261021.md",
                         ["0x0853D910", "0x020311EB", "0x06004000"],
                         "tools/mgba_probe/l3_evidence_sweep.py"),
    "battle-rules": ("notes/evidence/l3-evidence-20261021.md",
                     ["0x08594758", "0xCC", "0x44", "ctrl[6]"],
                     "tools/mgba_probe/l3_evidence_sweep.py"),
    "cutscene-scripts": ("notes/evidence/l3-evidence-20261021.md",
                         ["0x0853DF70", "0x06016000", "0x05000380"],
                         "tools/mgba_probe/l3_evidence_sweep.py"),
    "portrait-table": ("notes/evidence/l3-evidence-20261021.md",
                       ["0x085A4DEC", "0x06010000"],
                       "tools/mgba_probe/l3_evidence_sweep.py"),
    "menu-ui": ("notes/evidence/l3-evidence-20261021.md",
                ["0x085A4DEC", "0x06010000", "menu-ui"],
                "tools/mgba_probe/l3_evidence_sweep.py"),
    "save-state": ("notes/evidence/l3-evidence-20261021.md",
                   ["0x0853D848", "0x020240C0", "0x02026804"],
                   "tools/mgba_probe/l3_evidence_sweep.py"),
    "units": ("notes/evidence/l3-evidence-20261021.md",
              ["0x0853F298", "0x0202CA24"],
              "tools/mgba_probe/l3_evidence_sweep.py"),
    "story-background-table": ("notes/evidence/l3-evidence-20261021.md",
                               ["0x0859903C", "0x06004000"],
                               "tools/mgba_probe/l3_evidence_sweep.py"),
    # 2026-10-22: sound id 14 (the `story-e` song header 0x0853C3BC) is
    # requested by the chapter menu -- phase 0x0120 -> fn 0x0808A0F0 ->
    # fn 0x08089310 plays the jingle once the mission list runs past its
    # ninth entry.  The old note claimed the request lived in the map /
    # event scripts and was unreachable; that is falsified.
    "story-e": ("notes/evidence/story-e-l3-20261022.md",
                ["0x080894FC", "0x0853C3BC", "0x0809AAD6"],
                ("tools/mgba_probe/phase_sweep.py",
                 ["0x080894FC", "0x0809AAD6"])),
}

# The callback-table dispatch points are reached by the game's own reader
# code (2026-10-21).  The battle runs on normal A-key input; the gate was
# opened with the documented WRAM-only intervention described in the note.
# The note states the boundary explicitly: the tables are proven to be read
# by the ROM's own instructions, but a *natural* battle does not take that
# path.
for _key, (_site, _table) in CALLBACK_DISPATCH_L2.items():
    L2_BATCH_PROBES.setdefault(
        _key, (CALLBACK_DISPATCH_NOTE, [_site, _table],
               CALLBACK_DISPATCH_GATE))
    L3_BATCH_PROBES.setdefault(
        _key, (CALLBACK_DISPATCH_NOTE, [_site, _table],
               CALLBACK_DISPATCH_GATE))

# The mission panel (fn 0x080884DC) reads the mission index table on the
# chapter route; the game's own load instructions were observed and the
# table bytes were dumped at the hit.
L3_BATCH_PROBES.setdefault(
    "mission-text",
    ("notes/evidence/menu-answer-channel-20261021.md",
     ["0x08088500", "0x08348DAC"],
     "tools/mgba_probe/chapter_route.py"))

# The level mode (reached through the chapter hand-off) runs the three
# functions that read the character / formation / sprite-action tables, and
# it hits the *same* decision points the L2 evidence note uses.
LEVEL_MODE_NOTE = "notes/evidence/level-mode-l3-20261022.md"
LEVEL_MODE_GATE = "tools/mgba_probe/chapter_census.py"
LEVEL_MODE_PROBES = {
    "character-stats": ("0x0806D9D8", "0x08545068"),
    "character-stats-b": ("0x0806D9D8", "0x08545068"),
    "battle-config": ("0x0806E1FE", "0x085461C4"),
    "sprite-animations": ("0x0806B770", "0x08596CCC"),
    "sprite-action-table": ("0x0806B770", "0x08596CCC"),
}
for _key, (_site, _table) in LEVEL_MODE_PROBES.items():
    L3_BATCH_PROBES.setdefault(
        _key, (LEVEL_MODE_NOTE, [_site, _table], LEVEL_MODE_GATE))
    L2_BATCH_PROBES.setdefault(
        _key, (LEVEL_MODE_NOTE, [_site, _table], LEVEL_MODE_GATE))

# `tile-assets` is reached on the *story* route (map loading), with no memory
# intervention at all: the watch points had been sitting on the literal pool,
# which is why every earlier census reported 0 hits.
L3_BATCH_PROBES.setdefault(
    "tile-assets",
    ("notes/evidence/callback-dispatch-runtime-20261021.md",
     ["0x08099600", "0x085A320C"],
     "tools/mgba_probe/callback_census.py"))

# The battle BGM really starts, and the m4a play entry reads the SongHeader
# of sound id 1 (registry key `audio_song_1`, the `story` structure).  The
# old note claimed the engine never reads that header's fields -- it does.
# The story route plays sound id 8 and the battle route plays sound id 11,
# so the m4a play entry reads those SongHeaders' fields too.
M4A_NOTE = "notes/evidence/m4a-songheader-l3-20261022.md"
for _key, (_table) in (("story-b", "0x08536BC4"),
                       ("story-c", "0x08538FEC"),
                       ("story-d", "0x0853AB74")):
    L3_BATCH_PROBES.setdefault(
        _key, (M4A_NOTE, ["0x0809B282", _table],
               "tools/mgba_probe/callback_census.py"))

# The sound id table (0x08465B70) is read by the blip helper
# (fn 0x0809AAC0) on the story route, and the m4a play entry reads a
# SongHeader's fields when a song starts.
L3_BATCH_PROBES.setdefault(
    "story",
    (M4A_NOTE, ["0x0809B242", "0x08536368"],
     "tools/mgba_probe/callback_census.py"))

# The story route plays menu / scene sounds, and the blip helper reads the
# sound id table (0x08465B70) directly.
L3_BATCH_PROBES.setdefault(
    "sound-id-table",
    ("notes/evidence/m4a-songheader-l3-20261022.md",
     ["0x0809AACC", "0x08465B70"],
     "tools/mgba_probe/callback_census.py"))

# The dialogue pointer table (0x08461CE8) has no literal reader at all: its
# base is computed and loaded by fn 0x080914D8, which the state machine
# only calls from phase 0x0210.  Poking that phase makes the game read it.
TEXT_TABLE_NOTE = "notes/evidence/text-pointer-table-l3-20261022.md"
L3_BATCH_PROBES.setdefault(
    "text-writeback",
    (TEXT_TABLE_NOTE, ["0x080917B0", "0x08461CE8"],
     "tools/mgba_probe/text_table_probe.py"))
L2_BATCH_PROBES.setdefault(
    "text-writeback",
    (TEXT_TABLE_NOTE, ["0x080917B0", "0x08461CE8"],
     "tools/mgba_probe/text_table_probe.py"))

# The story state machine dispatches on `state[0x12]`, and each phase
# handler is a thin wrapper around one subsystem -- several still-unread
# tables are read from exactly such a handler.  Sweeping the 16 phases
# found two more (notes/evidence/phase-route-l3-20261022.md).
PHASE_ROUTE_NOTE = "notes/evidence/phase-route-l3-20261022.md"
PHASE_ROUTE_PROBES = {
    "data-table-a": ("0x0808A6BC", "0x085A143C"),
    "battle-encounters": ("0x08087D02", "0x0854229C"),
    "data-table-b": ("0x080985DA", "0x085A2034"),
    "function-pointers": ("0x08061DD6", "0x0853D5F0"),
    "reward-table": ("0x080893F2", "0x0859EAE0"),
}
for _key, (_site, _table) in PHASE_ROUTE_PROBES.items():
    L3_BATCH_PROBES.setdefault(
        _key, (PHASE_ROUTE_NOTE, [_site, _table],
               "tools/mgba_probe/phase_sweep.py"))
    L2_BATCH_PROBES.setdefault(
        _key, (PHASE_ROUTE_NOTE, [_site, _table],
               "tools/mgba_probe/phase_sweep.py"))

# The screenshot artifacts the L3 evidence note points at (they must be
# repository-tracked, so the audit's render probe accepts them).
L3_RENDER_ARTIFACTS = {
    "character-template": "notes/evidence/l3-intro.png",
    "encounter-zones": "notes/evidence/l3-intro.png",
    "battle-rules": "notes/evidence/l3-intro.png",
    "cutscene-scripts": "notes/evidence/l3-intro.png",
    "portrait-table": "notes/evidence/l3-intro.png",
    "menu-ui": "notes/evidence/l3-intro.png",
    "save-state": "notes/evidence/l3-intro.png",
    "units": "notes/evidence/l3-intro.png",
    "story-background-table": "notes/evidence/l3-story-scene54.png",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def read_text(rel: str) -> str:
    path = REPO / rel
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def hex_values(text: str) -> set[int]:
    return {int(m, 16) for m in HEX_RE.findall(text)}


def mentions_address(text: str, rom: int | None) -> bool:
    """True when `text` mentions the file offset or the ARM address."""
    if rom is None:
        return False
    wanted = {rom, rom + ARM_BASE}
    return bool(hex_values(text) & wanted)


def git_tracked(rel_path: str) -> bool:
    """True when the repo-relative path is tracked by git (durable evidence)."""
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "--error-unmatch", "--", rel_path],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def all_mentions() -> dict[int, list[str]]:
    """address -> repo-relative files that mention it (file offset or ARM form)."""
    out: dict[int, list[str]] = {}
    files = [p for p in (REPO / "tools").rglob("*.py") if p.is_file()]
    files += [p for p in (REPO / "notes").glob("*.md") if p.is_file()]
    files += [p for p in (REPO / "docs").glob("*.md") if p.is_file()]
    for path in files:
        text = read_text(str(path.relative_to(REPO)).replace("\\", "/"))
        for value in hex_values(text):
            out.setdefault(value, []).append(str(path.relative_to(REPO)).replace("\\", "/"))
    return out


def load_banks() -> dict[str, dict[str, Any]]:
    banks: dict[str, dict[str, Any]] = {}
    for path in sorted((REPO / "sequel" / "content").glob("*/bank.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        banks[path.parent.name] = data
    return banks


def load_registry() -> dict[str, Any]:
    try:
        from tools import table_registry  # type: ignore
    except Exception:
        return {"tables": {}, "alias_conflicts": [], "conflicts": {},
                "retired": {}}
    tables = {name: {"address": addr, "verified": verified, "note": note}
              for name, (addr, verified, note) in table_registry.TABLES.items()}
    conflicts = [c for c in table_registry.verify_table_bases()["alias_conflicts"]]
    return {"tables": tables, "alias_conflicts": conflicts,
            "conflicts": getattr(table_registry, "CONFLICTS", {}) or {},
            "retired": getattr(table_registry, "RETIRED", {}) or {}}


def load_fixtures() -> dict[str, dict[str, Any]]:
    """Registered synthetic fixtures + the module each one is defined in."""
    out: dict[str, dict[str, Any]] = {}
    try:
        from tools import synthetic_fixture  # type: ignore
    except Exception:
        return out
    for name, func in synthetic_fixture.FIXTURES.items():
        module = getattr(func, "__module__", "")
        module_file = None
        for candidate in ("tools/synthetic_fixture.py", "tools/fixtures_extended.py"):
            if module.replace("tools.", "") in candidate:
                module_file = candidate
                break
        out[name] = {
            "function": getattr(func, "__name__", name),
            "module": module,
            "module_file": module_file,
            "doc": (func.__doc__ or "").strip(),
        }
    return out


# ---------------------------------------------------------------------------
# Probe evaluation
# ---------------------------------------------------------------------------
def evaluate_probe(probe: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    kind = probe.get("kind")
    rom = ctx.get("rom")
    address_required = probe.get("address_required", True)
    result = {"kind": kind, "passed": False, "detail": "", "ref": probe.get("path")
              or probe.get("name") or probe.get("tool")}

    if kind == "fixture":
        name = probe["name"]
        fixtures = ctx["fixtures"]
        if name not in fixtures:
            result["detail"] = f"夹具 {name} 不在 FIXTURES 注册表"
            return result
        covers = probe.get("covers") or ([rom] if rom is not None else [])
        module_file = fixtures[name]["module_file"]
        module_text = read_text(module_file) if module_file else ""
        if not any(mentions_address(module_text, c) for c in covers if c is not None):
            result["detail"] = f"夹具 {name} 的模块未提及本结构地址"
            return result
        coverage = ctx["fixture_coverage_note"]
        if name not in coverage:
            result["detail"] = f"夹具 {name} 未出现在 {FIXTURE_COVERAGE_NOTE}"
            return result
        result["passed"] = True
        result["ref"] = f"{module_file}::{name}"
        result["detail"] = f"夹具 {name}（{module_file}，覆盖笔记已记录）"
        return result

    if kind == "tool":
        path = probe["path"]
        text = read_text(path)
        if not text:
            result["detail"] = f"{path} 不存在"
            return result
        need = probe.get("need", [])
        missing = [n for n in need if n not in text]
        if missing:
            result["detail"] = f"{path} 缺少标记 {missing}"
            return result
        if address_required and rom is not None and not mentions_address(text, rom):
            result["detail"] = f"{path} 未提及本结构地址"
            return result
        result["passed"] = True
        result["detail"] = f"{path} 存在且命中地址/标记"
        return result

    if kind == "note":
        path = probe["path"]
        text = read_text(path)
        if not text:
            result["detail"] = f"{path} 不存在"
            return result
        need = probe.get("need", [])
        missing = [n for n in need if n not in text]
        if missing:
            result["detail"] = f"{path} 缺少标记 {missing}"
            return result
        if address_required and rom is not None and not mentions_address(text, rom):
            result["detail"] = f"{path} 未提及本结构地址"
            return result
        result["passed"] = True
        result["detail"] = f"{path} 存在且命中地址/标记"
        return result

    if kind == "code":
        path = probe["path"]
        text = read_text(path)
        if not text:
            result["detail"] = f"{path} 不存在"
            return result
        need = probe.get("need", [])
        missing = [n for n in need if n not in text]
        if missing:
            result["detail"] = f"{path} 缺少证据片段 {missing}"
            return result
        result["passed"] = True
        result["detail"] = f"{path} 含原生代码证据"
        return result

    if kind == "roundtrip":
        path = probe["path"]
        text = read_text(path)
        if not text:
            result["detail"] = f"{path} 不存在"
            return result
        need = probe.get("need", [])
        missing = [n for n in need if n not in text]
        if missing:
            result["detail"] = f"{path} 缺少往返断言标记 {missing}"
            return result
        result["passed"] = True
        result["detail"] = f"{path} 含字节级往返断言"
        return result

    if kind == "render":
        tool = probe["tool"]
        artifact = probe["artifact"]
        tool_text = read_text(tool)
        if not tool_text:
            result["detail"] = f"{tool} 不存在"
            return result
        if rom is not None and not mentions_address(tool_text, rom):
            result["detail"] = f"{tool} 未提及本结构地址"
            return result
        if not any(marker in tool_text for marker in (".png", ".wav", ".mid", "wave", "Image")):
            result["detail"] = f"{tool} 没有媒体产出标记"
            return result
        art = REPO / artifact
        result["artifact"] = artifact
        result["artifact_present"] = art.is_file() and art.stat().st_size > 0
        result["artifact_tracked"] = git_tracked(artifact)
        result["passed"] = True
        result["detail"] = f"{tool} 产出 {artifact}（本地{'已生成' if result['artifact_present'] else '未生成'}，" \
                           f"{'已提交' if result['artifact_tracked'] else '未提交'}）"
        return result

    if kind == "dynamic":
        path = probe["path"]
        text = read_text(path)
        if not text:
            result["detail"] = f"{path} 不存在"
            return result
        need = probe.get("need", [])
        missing = [n for n in need if n not in text]
        if missing:
            result["detail"] = f"{path} 缺少证据片段 {missing}"
            return result
        result["passed"] = True
        result["level"] = probe.get("level")
        result["detail"] = f"{path}（{probe.get('level')} 动态证据）"
        return result

    if kind == "writeback":
        # Executable write-back proof.
        #
        # A write-back path only counts as usable when it can (1) read a
        # native entry, (2) apply an author change, and (3) read the result
        # back and get the author input again -- without disturbing the
        # bytes whose meaning is unknown.  `tools/writeback_paths.py`
        # implements exactly that, once per structure; this probe *runs* the
        # structure's case against a copy of the ROM instead of grepping for
        # the tool's existence.
        path = probe["path"]
        case_key = probe.get("case")
        text = read_text(path)
        if not text:
            result["detail"] = f"{path} 不存在"
            return result
        if not case_key:
            result["detail"] = f"{path} 的写回探针没有声明 case"
            return result
        if f'Case("{case_key}"' not in text:
            result["detail"] = f"{path} 里没有登记 case {case_key}"
            return result
        rom_bytes = ctx.get("rom_bytes")
        if not rom_bytes:
            result["detail"] = "ROM 不可读，无法执行写回自检"
            return result
        try:
            if str(REPO / "tools") not in sys.path:
                sys.path.insert(0, str(REPO / "tools"))
            import writeback_paths  # type: ignore
        except Exception as exc:
            result["detail"] = f"无法导入 {path}: {type(exc).__name__}: {exc}"
            return result
        case = next((c for c in writeback_paths.CASES if c.key == case_key), None)
        if case is None:
            result["detail"] = f"{path}:{case_key} 未登记"
            return result
        # The case must target this structure's own base address.  Without
        # this cross-check a write-back path could be credited to the wrong
        # table simply by naming the right key.
        want = probe.get("base", ctx.get("structure_rom"))
        if want is not None:
            try:
                case_rom = int(case.rom, 16)
            except (TypeError, ValueError):
                result["detail"] = f"{path}:{case_key} 的 rom 字段无法解析"
                return result
            if case_rom != want:
                result["detail"] = (f"{path}:{case_key} 针对的是 0x{case_rom:06X}，"
                                    f"与本结构基址 0x{want:06X} 不符")
                return result
        try:
            outcome = case.run(rom_bytes)
        except Exception as exc:
            result["detail"] = (f"{case_key} 写回自检抛异常: "
                                f"{type(exc).__name__}: {exc}")
            return result
        problems = outcome.get("problems") or []
        if problems:
            result["detail"] = f"{case_key} 写回自检失败: {problems}"
            return result
        result["passed"] = True
        result["ref"] = f"{path}::{case_key}"
        result["detail"] = (f"{case_key} 写回自检通过"
                            "（回读 == 作者输入，未知字节原样保留）")
        return result

    if kind == "codecite":
        # Machine-checkable "native code addressing" proof.
        #
        # Instead of grepping prose for an address, this probe reads the
        # consumer-evidence file produced by `tools/consumer_locate.py`,
        # verifies the ROM digest still matches, and checks that the
        # structure really is read by the game's own code.
        path = probe["path"]
        text = read_text(path)
        if not text:
            result["detail"] = f"{path} 不存在"
            return result
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            result["detail"] = f"{path} 不是合法 JSON: {exc}"
            return result
        expected_digest = ctx.get("rom_sha256")
        if expected_digest and data.get("rom_sha256") != expected_digest:
            result["detail"] = (f"{path} 的 ROM 指纹过期："
                                f"{data.get('rom_sha256')} != {expected_digest}")
            return result
        table = probe.get("table")
        entry = (data.get("tables") or {}).get(table)
        if entry is None:
            result["detail"] = f"{path} 里没有 {table}"
            return result
        consumers = entry.get("consumers") or []
        min_consumers = probe.get("min_consumers", 1)
        if len(consumers) < min_consumers:
            result["detail"] = (f"{path}:{table} 只有 {len(consumers)} 个原生消费者，"
                                f"少于 {min_consumers}")
            return result
        haystack: list[str] = []
        for consumer in consumers:
            haystack.append(str(consumer.get("reader") or ""))
            haystack.append(str(consumer.get("function") or ""))
            haystack.extend(consumer.get("evidence") or [])
            haystack.extend(consumer.get("disasm") or [])
        need = probe.get("need", [])
        missing = [n for n in need if not any(n in h for h in haystack)]
        if missing:
            result["detail"] = f"{path}:{table} 缺少证据片段 {missing}"
            return result
        result["passed"] = True
        result["ref"] = f"{path}::{table}"
        result["detail"] = (f"{path}:{table} 有 {len(consumers)} 个原生消费者"
                            + (f"，stride={consumers[0].get('stride')}"
                               if consumers[0].get("stride") else ""))
        return result

    if kind == "notatable":
        # Negative proof: the declared base is NOT a structure base because
        # the ROM never names that address (no literal load, no data
        # pointer).  This adjudicates the identity question, but it is NOT a
        # format proof -- it cannot raise the evidence level.
        path = probe["path"]
        text = read_text(path)
        if not text:
            result["detail"] = f"{path} 不存在"
            return result
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            result["detail"] = f"{path} 不是合法 JSON: {exc}"
            return result
        expected_digest = ctx.get("rom_sha256")
        if expected_digest and data.get("rom_sha256") != expected_digest:
            result["detail"] = (f"{path} 的 ROM 指纹过期："
                                f"{data.get('rom_sha256')} != {expected_digest}")
            return result
        table = probe.get("table")
        entry = (data.get("tables") or {}).get(table)
        if entry is None:
            result["detail"] = f"{path} 里没有 {table}"
            return result
        if entry.get("consumers"):
            result["detail"] = f"{path}:{table} 其实有 {len(entry['consumers'])} 个原生消费者"
            return result
        if entry.get("raw_occurrences"):
            result["detail"] = (f"{path}:{table} 在 ROM 里出现 "
                                f"{len(entry['raw_occurrences'])} 次，不是无效地址")
            return result
        result["passed"] = True
        result["ref"] = f"{path}::{table}"
        result["detail"] = f"{path}:{table} 在 ROM 里零引用，基址无效（已裁决）"
        return result

    result["detail"] = f"未知探针类型 {kind}"
    return result


def evaluate_structure(key: str, spec: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    spec_probes = list(spec.get("probes", []))
    # Implicit native-consumer probe: derived from the structure's own base
    # address, so it follows the evidence file instead of being hand-listed.
    rom_addr = spec.get("rom")
    if rom_addr is not None and ctx.get("consumer_tables") is not None:
        arm = rom_addr if rom_addr >= ARM_BASE else rom_addr + ARM_BASE
        entry = ctx["consumer_tables"].get(f"0x{arm:08X}")
        if entry is not None:
            table = f"0x{arm:08X}"
            if entry.get("consumers"):
                spec_probes.append({
                    "kind": "codecite",
                    "path": CONSUMER_EVIDENCE,
                    "table": table,
                    "min_consumers": 1,
                })
            elif not entry.get("raw_occurrences"):
                spec_probes.append({
                    "kind": "notatable",
                    "path": CONSUMER_EVIDENCE,
                    "table": table,
                })
    probes = [evaluate_probe(p, {**ctx, "rom": rom_addr}) for p in spec_probes]
    # Write-back probes are matched by their `need` markers: the generator
    # tools are deliberately generic (one patch generator serves many
    # tables), so demanding the address inside them is meaningless.  The
    # executable `writeback` kind gets the structure's own base instead, so
    # it can cross-check that the case really targets *this* table.
    writeback = [evaluate_probe(p, {**ctx, "rom": None, "structure_rom": rom_addr})
                 for p in spec.get("writeback", [])]
    passed = [p for p in probes if p["passed"]]
    kinds = {p["kind"] for p in passed}

    has_tool = "tool" in kinds
    has_note = "note" in kinds
    has_proof = bool(kinds & {"fixture", "render", "code", "roundtrip", "codecite"})
    has_dyn = {p["kind"] for p in passed} & {"dynamic"}
    # A structure whose declared base is proven to be unnamed in the ROM has
    # been *adjudicated*: the identity question is closed (the base is
    # wrong), even though no format proof exists yet.
    adjudicated = any(p["kind"] == "notatable" and p["passed"] for p in probes)

    levels: list[str] = []
    if has_proof and has_tool and has_note:
        levels.append("L1")
    for level in ("L2", "L3", "L4"):
        if any(p["kind"] == "dynamic" and p.get("level") == level for p in probes):
            levels.append(level)

    level = next((l for l in LEVELS if l in levels), "none")
    if level == "none" and not levels:
        level = "none"

    rom = spec.get("rom")
    tool_hits = [f for f in ctx["mentions"].get(rom, []) if f.startswith("tools/")] if rom else []
    note_hits = [f for f in ctx["mentions"].get(rom, []) if not f.startswith("tools/")] if rom else []

    return {
        "key": key,
        "title": spec.get("title", key),
        "rom": (f"0x{rom:08X}" if rom >= ARM_BASE else f"0x{rom:06X}")
        if rom is not None else None,
        "rom_value": rom,
        "bank": spec.get("bank"),
        "level": level,
        "levels_met": levels,
        "format_proven": has_proof,
        "adjudicated": adjudicated,
        "has_tool": has_tool,
        "has_note": has_note,
        "readonly": bool(spec.get("readonly")) or adjudicated,
        "retired": bool(spec.get("retired")),
        "readonly_reason": (
            "基址在 ROM 中零引用，已裁决为无效的只读参考"
            if adjudicated else
            ("结构被声明为只读参考" if spec.get("readonly") else None)
        ),
        "writeback_usable": any(p["passed"] for p in writeback),
        "writeback_executable": any(p["kind"] == "writeback" and p["passed"]
                                    for p in writeback),
        "probes": probes,
        "writeback_probes": writeback,
        "failed_probes": [p for p in probes if not p["passed"]],
        "auto_tools": sorted(tool_hits),
        "auto_notes": sorted(note_hits),
        "unresolved": spec.get("unresolved", []),
        "corrections": spec.get("corrections", []),
        "value": spec.get("value", 2),
        "effort": spec.get("effort", 3),
    }


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------
GAP_TEXT = {
    "format": ("格式未证明",
               "需要一条可复现的证明：合成夹具写入→生产读取器读回逐字节相等，"
               "或渲染可视证明，或字节级往返，或原生代码字面量池定址；"
               "并把该证明写进 notes/。"),
    "tool": ("无可复现工具",
             "需要提交一个能一条命令跑出该结构可检查结果的工具（夹具或提取器）。"),
    "doc": ("无笔记",
            "需要在 notes/ 记录地址、字段语义、证据文件与复现命令。"),
    "semantics": ("字段语义未解",
                  "需要对该结构的每个字段给出含义；未解字段要显式列出并标注，"
                  "且不得影响“复制原生条目 + 只改已知字段”的写回模型。"),
    "writeback": ("无可用写回路径",
                  "需要一条写回路径 + “回读渲染/解码结果 == 作者输入”的验收。"),
    "identity": ("身份冲突未裁决",
                 "需要定位该地址的真实消费者，判定它到底是哪张表，"
                 "并把它与同址的其它 bank 拆开。"),
    "rebase": ("基址无效，需重新定位",
               "该地址已被证明在 ROM 里零引用（不是任何结构的基址）。"
               "需要用原生消费者定位（tools/consumer_locate.py）找到真正"
               "拥有这张表的地址，再重新做格式证明。"),
    "L2": ("缺原生定点证据",
           "需要在消费者地址下断点，命中后同一上下文记录 PC/LR/寄存器，"
           "并证明至少一个字段与运行时值或可见行为对应。"),
    "L3": ("缺模拟器按键复现",
           "需要用 mGBA 探针注入正常按键走到该结构生效的场景，"
           "并保存运行时读数与结构字段的唯一对应。"),
    "L4": ("缺完整通关",
           "需要把 55 场景 × 3 配置全流程打通并逐场留证。"),
    # --- 未结项的细分类 -------------------------------------------------
    # The "字段语义未解" criterion has three conditions: every field has a
    # meaning (or is explicitly listed as unknown), the unknown ones are
    # listed, and they do not affect the write-back model.  An open item
    # that is NOT about an unknown field must not be filed under it, or the
    # report would confuse "we do not know what this byte means" with
    # "we have not exported this asset yet".
    "relation": ("与另一张表的关系未裁决",
                 "需要证明本表与所指的那张表是不是同一张东西，"
                 "或者明确它们各自负责什么。"),
    "evidence": ("缺运行时证据闭环",
                 "需要一次原生定点或模拟器复现，把这条静态推导"
                 "变成运行时读数。"),
    "capability": ("工具/导出能力缺失",
                   "需要一个能把这份内容完整导出或写回的命令。"),
    "integrity": ("素材完整性未核",
                  "需要逐条核实这份素材的实际取值范围/损坏点，"
                  "并修掉被证伪的那几处。"),
    "ambiguity": ("取值规则未唯一化",
                  "需要把这条查找/编码规则收敛成唯一且可机械执行的一条。"),
    "labelled": ("未知字段已显式标注",
                 "该结构的未知字段已经逐条列出，且写回路径的往返自检"
                 "证明这些字节不会被改动 —— 不影响“复制原生条目 + "
                 "只改已知字段”的写回模型。"),
}


UNRESOLVED_TYPES = ("field", "relation", "evidence", "capability",
                    "integrity", "ambiguity")


def classify_unresolved(item: Any) -> tuple[str, str, dict[str, Any]]:
    """Split one declared open item into (gap kind, text, extra).

    The audit used to file *every* open item under "字段语义未解".  That
    conflated four different questions:

      * a field of the ROM structure whose meaning is unknown  -> ``field``
      * the relation between this table and another one        -> ``relation``
      * a static deduction that has no runtime closure yet     -> ``evidence``
      * a missing tool / export / asset-import capability      -> ``capability``
        (also ``integrity`` for damaged assets and ``ambiguity``
        for a lookup rule that is not unique yet)

    Only the first one is a field-semantics gap in the sense of
    ``GAP_TEXT["semantics"]``.
    """
    if isinstance(item, str):
        return "field", item, {}
    if not isinstance(item, dict):
        return "field", str(item), {}
    kind = str(item.get("type", "field"))
    if kind not in UNRESOLVED_TYPES:
        kind = "field"
    text = str(item.get("text", ""))
    extra = {k: v for k, v in item.items() if k not in ("type", "text")}
    return kind, text, extra


def evidence_text(ctx: dict[str, Any], rom: int | None) -> str:
    """Every file in the repo that mentions this structure's address."""
    if rom is None:
        return ""
    key = f"evidence_text:{rom}"
    cached = ctx.get(key)
    if cached is not None:
        return cached
    parts = [read_text(f) for f in ctx["mentions"].get(rom, [])]
    text = "\n".join(parts)
    ctx[key] = text
    return text


def build_gaps(rows: list[dict[str, Any]], alias_map: dict[str, list[str]],
               ctx: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Turn per-structure probe results into a ranked action list.

    `blocking` marks the gaps that the "100% 完成" definition actually
    requires; the rest are hardening items (native pinning, full playthrough)
    that the repository has explicitly not claimed yet.
    """
    ctx = ctx or {}
    gaps: list[dict[str, Any]] = []
    for row in rows:
        key = row["key"]
        unresolved = row.get("unresolved", [])
        alias = alias_map.get(key, [])

        def add(kind: str, what: str, evidence: str, value: int, effort: int,
                blocking: bool) -> None:
            gaps.append({
                "structure": key,
                "title": row["title"],
                "rom": row["rom"],
                "level": row["level"],
                "kind": kind,
                "what": what,
                "evidence_needed": evidence,
                "value": value,
                "effort": effort,
                "blocking": blocking,
                "score": round(value / effort, 3),
            })

        if row.get("retired"):
            # The bank was retired from the content catalogue: its identity
            # died, the retirement is recorded in
            # `tools/table_registry.py::RETIRED`, and the bank owns no table.
            # There is nothing left to do for it, so it is not an open item.
            continue
        if row.get("adjudicated"):
            # The declared base was proven to be named nowhere in the ROM, so
            # the identity question is closed and the structure is explicitly
            # a read-only reference.  That satisfies P1 ("adjudicated") and
            # P3 ("explicitly read-only"), so it is NOT a blocking "format
            # unproven" gap any more - it is a "find the real base" item.
            #
            # When the registry already adjudicated this base, the item is
            # not "go and find it" but the concrete disposition it recorded
            # (falsified / deprecated-window / repointed / merge), so the
            # gap text says what to do instead of sending the reader off to
            # re-derive it.
            todo = "；".join(classify_unresolved(i)[1] for i in unresolved)
            disposition = ""
            canonical = None
            kind = "rebase"
            conflicts = ctx.get("conflicts") or {}
            for conflict in conflicts.values():
                if row.get("rom_value") is None:
                    continue
                banks = conflict.get("banks") or []
                if row["key"] in banks:
                    disposition = str(
                        (conflict.get("dispositions") or {}).get(row["key"], ""))
                    canonical = conflict.get("canonical_address")
                    # A falsified entry has NO canonical address -- it means
                    # "there is no table here", not "look somewhere else".
                    if canonical is not None and canonical != row["rom_value"]:
                        kind = "repoint"
                    break
            what = GAP_TEXT["rebase"][0]
            evidence = GAP_TEXT["rebase"][1]
            if disposition.startswith("falsified"):
                # The identity is dead: no table lives at that address, so
                # there is nothing to repoint to.  The action is to retire
                # the bank, not to hunt for a base.
                kind = "retire"
                what = "身份已作废，应退役该 bank"
                evidence = (
                    f"registry 已裁决：{disposition}。"
                    f"该地址不对应任何结构 —— 应当把这个 bank 从内容目录退役"
                    f"（或改名并指向真正对应的表），而不是再去找基址")
            elif kind == "repoint":
                what = "基址需改指到裁决后的真实基址"
                evidence = (
                    f"registry 已裁决：{disposition}。"
                    f"真实基址是 0x{canonical:06X} —— "
                    f"把本 bank 的 `table_offset` 指过去即可，"
                    f"不需要再找（见 tools/table_registry.py::CONFLICTS）")
            elif disposition:
                evidence = f"registry 已裁决：{disposition}。" + evidence
            add(kind, what,
                evidence + ("；本结构的具体待办：" + todo if todo else ""),
                max(row["value"] - 2, 1), row["effort"], False)
        elif row["level"] == "none":
            # Nothing about this structure is proven yet: roll the sub-gaps
            # (identity / semantics / write-back) into one actionable item
            # instead of emitting four near-identical rows.
            extra: list[str] = []
            if alias:
                extra.append(f"与 {', '.join(alias)} 同址，身份冲突未裁决")
            extra.extend(classify_unresolved(i)[1] for i in unresolved)
            if not row["writeback_usable"] and not row.get("readonly"):
                extra.append("没有写回路径")
            what = "格式未证明（无独立证据）"
            evidence = GAP_TEXT["format"][1]
            if extra:
                evidence += "；本结构的具体待办：" + "；".join(extra)
            add("format", what, evidence, max(row["value"], 2), row["effort"], True)
        else:
            if not row["format_proven"]:
                add("format", GAP_TEXT["format"][0], GAP_TEXT["format"][1],
                    max(row["value"], 2), row["effort"], True)
            elif not row["has_tool"]:
                add("tool", GAP_TEXT["tool"][0], GAP_TEXT["tool"][1],
                    row["value"], row["effort"], True)
            elif not row["has_note"]:
                add("doc", GAP_TEXT["doc"][0], GAP_TEXT["doc"][1], 2, 3, True)
            if alias:
                add("identity", GAP_TEXT["identity"][0] + f"（与 {', '.join(alias)} 同址）",
                    GAP_TEXT["identity"][1], max(row["value"], 3), row["effort"], True)
            for item in unresolved:
                kind, text, extra = classify_unresolved(item)
                if kind == "field":
                    # A field gap is satisfied when the unknown fields are
                    # explicitly listed *and* the write-back path provably
                    # leaves them alone.  The "provably" half is machine
                    # checked: the write-back self-check asserts that no byte
                    # outside the declared known-field set moved.
                    safe = bool(extra.get("writeback_safe"))
                    markers = extra.get("need") or []
                    note_file = extra.get("note")
                    haystack = (read_text(note_file) if note_file
                                else evidence_text(ctx, row.get("rom_value")))
                    missing = [m for m in markers if m not in haystack]
                    if (safe and not missing
                            and (row.get("writeback_executable")
                                 or row.get("readonly"))):
                        add("labelled", GAP_TEXT["labelled"][0] + "：" + text,
                            GAP_TEXT["labelled"][1], max(row["value"] - 1, 1),
                            max(row["effort"], 2), False)
                    else:
                        why = ""
                        if safe and missing:
                            why = ("；但下列标记尚未在证据文件中出现："
                                   + "、".join(missing))
                        elif safe and not row.get("writeback_executable") \
                                and not row.get("readonly"):
                            why = ("；且该结构还没有可执行的写回往返自检，"
                                   "无法证明未知字段不会被改动")
                        add("semantics",
                            GAP_TEXT["semantics"][0] + "：" + text + why,
                            GAP_TEXT["semantics"][1],
                            max(row["value"], 2), row["effort"], True)
                elif kind == "relation":
                    add("relation", GAP_TEXT["relation"][0] + "：" + text,
                        GAP_TEXT["relation"][1], max(row["value"], 2),
                        row["effort"], True)
                elif kind == "evidence":
                    add("evidence", GAP_TEXT["evidence"][0] + "：" + text,
                        GAP_TEXT["evidence"][1], max(row["value"] - 1, 1),
                        row["effort"] + 1, False)
                else:
                    add(kind, GAP_TEXT[kind][0] + "：" + text,
                        GAP_TEXT[kind][1], max(row["value"] - 2, 1),
                        max(row["effort"], 2), False)

            if not row["writeback_usable"] and not row.get("readonly"):
                add("writeback", GAP_TEXT["writeback"][0], GAP_TEXT["writeback"][1],
                    max(row["value"] - 1, 1), max(row["effort"], 2), True)

        # The gap list must say what is **missing**, not what could be
        # better: a structure that already reached L3 has L2 evidence too
        # (the levels are cumulative), so it gets no L2 row.
        met = set(row.get("levels_met") or [])
        l3_what, l3_evidence = GAP_TEXT["L3"]
        l2_what, l2_evidence = GAP_TEXT["L2"]
        if key in CALLBACK_DISPATCH_BLOCKED:
            # The dispatch points of the callback tables are known down to the
            # instruction, and the family around 0x0807F..0x08080 has been
            # shown to be reachable from a *story battle* (the earlier
            # "0 hits" census was a tool bug: the key release only ran when
            # no breakpoint fired, so the game never saw a press edge).  The
            # structures listed here are read from a *different* subsystem,
            # so they need their own route; saying "press a key" would still
            # be a guess, so the note says what is known.
            l3_evidence = (
                l3_evidence + "2026-10-21 复核（notes/evidence/"
                "callback-dispatch-runtime-20261021.md）：旧结论「回调派发点在 "
                "battle / save / sweep 三条路线 0 命中，所以这些表只属于关卡/"
                "过场模式」**作废** —— 那次普查有工装 bug（松手只在没命中断点时"
                "才执行，游戏收不到按下沿，战斗过场不推进）。同一族派发点"
                "（0x0807F414 / 0x0807FE62 / 0x08080B12 / 0x08080B32）已被证明"
                "在**剧情战斗**里可达，并拿到了运行时读数。本结构的读者在另一个"
                "子系统，需要各自的路线路径。")
            l2_evidence = (
                l2_evidence + "2026-10-21 复核：旧结论「消费者在 ROM 回调表后面，"
                "只能经派发进入」**部分作废** —— 派发本身已被证明可达"
                "（notes/evidence/callback-dispatch-runtime-20261021.md）；"
                "本结构尚未走到自己的那一条派发点。")
        if "L4" not in met and "L3" not in met:
            add("L3", l3_what, l3_evidence,
                max(row["value"], 2), row["effort"] + 1, False)
        if "L4" not in met and "L3" not in met and "L2" not in met:
            add("L2", l2_what, l2_evidence,
                max(row["value"] - 1, 1), row["effort"] + 1, False)
    gaps.sort(key=lambda g: (not g["blocking"], -g["score"], -g["value"],
                              g["structure"], g["kind"]))
    return gaps


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _apply_batch_probes(spec: dict[str, Any], key: str) -> None:
    """Attach the batch runtime-evidence probes for `key` to `spec`.

    The L2/L3 evidence lives in one note per level, so the probe is data:
    the note path, the markers that note must contain, and the executable gate
    that produced it.  Nothing here is structure-specific, so a new batch of
    evidence is wired by adding an entry, not by editing code.
    """
    for table, level in ((L2_BATCH_PROBES, "L2"), (L3_BATCH_PROBES, "L3")):
        entry = table.get(key)
        if not entry:
            continue
        note, markers, gate = entry
        # The gate may carry its own marker list: a structure whose base comes
        # from the registry (e.g. the m4a SongHeaders) has its base in the
        # *note* but not in the *tool* -- the tool reads the base from
        # `tools/table_registry.py`.  The tool marker is then the decision
        # point, which is what the tool really contains.
        tool_markers = markers
        if isinstance(gate, tuple):
            gate, tool_markers = gate
        probes = spec.setdefault("probes", [])
        if any(p.get("kind") == "dynamic" and p.get("path") == note
               and p.get("level") == level for p in probes):
            continue
        probes.append({
            "kind": "dynamic", "path": note, "level": level,
            "need": list(markers), "address_required": False,
        })
        if gate:
            probes.append({
                "kind": "tool", "path": gate,
                "need": list(tool_markers), "address_required": False,
            })
    artifact = L3_RENDER_ARTIFACTS.get(key)
    if artifact:
        probes.append({
            "kind": "render", "tool": "tools/mgba_probe/l3_evidence_sweep.py",
            "artifact": artifact,
        })


def build_report() -> dict[str, Any]:
    banks = load_banks()
    registry = load_registry()
    fixtures = load_fixtures()
    mentions = all_mentions()

    # Native-consumer evidence: the machine-checkable product of
    # `tools/consumer_locate.py`.  A stale digest is reported but does not
    # silently downgrade the audit -- it shows up in the report so the
    # reviewer can regenerate it.
    consumer_tables: dict[str, Any] | None = None
    consumer_status = "missing"
    rom_sha256 = None
    rom_bytes: bytes | None = None
    rom_path = REPO / BASE_ROM
    if rom_path.is_file():
        import hashlib
        rom_bytes = rom_path.read_bytes()
        rom_sha256 = hashlib.sha256(rom_bytes).hexdigest()
    evidence_text = read_text(CONSUMER_EVIDENCE)
    if evidence_text:
        try:
            evidence = json.loads(evidence_text)
        except json.JSONDecodeError:
            evidence = None
        if isinstance(evidence, dict) and evidence.get("tables"):
            consumer_tables = evidence["tables"]
            consumer_status = ("ok" if evidence.get("rom_sha256") == rom_sha256
                               else "stale")

    ctx = {
        "fixtures": fixtures,
        "fixture_coverage_note": read_text(FIXTURE_COVERAGE_NOTE),
        "mentions": mentions,
        "consumer_tables": consumer_tables,
        "rom_sha256": rom_sha256,
        "rom_bytes": rom_bytes,
        "conflicts": (registry.get("conflicts") or {}),
        "retired": (registry.get("retired") or {}),
    }

    rows: list[dict[str, Any]] = []
    for key, spec in SPECS.items():
        _apply_batch_probes(spec, key)
        rows.append(evaluate_structure(key, spec, ctx))

    # Legacy banks with no dedicated spec.
    for name in sorted(banks):
        if name in SPECS:
            continue
        declared = LEGACY_BANK_ONLY.get(name)
        spec = {
            "title": name,
            "rom": banks[name].get("table_offset"),
            "bank": name,
            "probes": [
                # The generic scanner is the tool that proves the base, and
                # the base-correction note is where the verdict is written.
                {"kind": "tool", "path": "tools/consumer_locate.py"},
                {"kind": "note", "path": "notes/legacy-table-base-correction-20261020.md"},
            ],
            "unresolved": (declared if isinstance(declared, list)
                           else ([declared] if declared else [])),
            "value": 2,
            "effort": 3,
        }
        if banks[name].get("retired") or name in (ctx.get("retired") or {}):
            spec["retired"] = True
            spec["unresolved"] = []
            reason = (ctx.get("retired") or {}).get(name, "")
            spec["corrections"] = [
                f"**已退役**（`tools/table_registry.py::RETIRED`）：{reason}"]
        if name in LEGACY_REIDENTIFIED:
            base, sound_id, case = LEGACY_REIDENTIFIED[name]
            if sound_id is not None:
                spec["title"] = f"m4a SongHeader（sound id {sound_id}）"
                spec["rom"] = base
                spec["probes"] = [
                    {"kind": "tool", "path": "tools/audio_song_headers.py"},
                    {"kind": "note",
                     "path": "notes/evidence/story-table-family-20261020.md"},
                    {"kind": "code",
                     "path": "notes/evidence/story-table-family-20261020.md",
                     "need": ["0x0809B242", "0x0809AAC8", f"0x{base:06X}"],
                     "address_required": False},
                    {"kind": "tool", "path": "tools/m4a_block_table.py",
                     "need": ["0x08464534"], "address_required": False},
                    {"kind": "note",
                     "path": "notes/evidence/m4a-block-table-20261021.md"},
                    {"kind": "code",
                     "path": "notes/evidence/m4a-block-table-20261021.md",
                     "need": ["0x08464534", "0x0809A4E8", "0x0809B25C"],
                     "address_required": False},
                ]
                spec["writeback"] = [
                    {"kind": "tool", "path": "tools/import_audio_song.py"},
                    {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
                     "case": case},
                ]
                spec["unresolved"] = []
                spec["corrections"] = [
                    f"旧基址 0x{base + 4:06X} 晚了 4 字节 —— 它锚在 "
                    f"`voicegroup_ptr` 字段（+0x04）而不是表头起点。"
                    f"本结构**不是**剧情表，而是 sound id {sound_id} 的 "
                    f"**m4a SongHeader**（由 sound-ID 表 `0x465B70` 的第 "
                    f"{sound_id} 行指向）",
                    "**轨数据的块级格式已逐字段拆解**（2026-10-21）："
                    "「block 表」就是 SongHeader 本身 —— "
                    "`+0x00` u8 轨道数、`+0x01` u8（本 ROM 全为 0 且引擎不读）、"
                    "`+0x02` u8 优先级、`+0x03` u8 标志（bit7 = 混响）、"
                    "`+0x04` u32 voicegroup 指针、"
                    "`+0x08` 起 `u32 track_ptr[轨道数]`；"
                    "每个 `track_ptr[i]` 指向一个**无头**的 block —— "
                    "扁平命令流，以 FINE（`0xB1`）结束、其后是 0x00 padding。"
                    "命令编码：`0x00-0x7F` 是**续写字节**（running opcode 的操作数）、"
                    "`0x80-0xB0` 是 WAIT、`0xB1-0xCE` 是命令表"
                    "（`0x08464534`，30 项，索引 `op-0xB1`）、"
                    "`0xCF-0xFF` 是 NOTE（0~3 个可选参数字节）。"
                    "**running opcode 规则**（`0x0809A4F8 cmp r1,#0xbd` / "
                    "`0x0809A4FC strb r1,[r5,#7]`）："
                    "**所有 `>= 0xBD` 的 opcode 都更新 running opcode**（不只是音符）。"
                    "循环：GOTO `0xB2`（4 字节**小端**目标）、PATT `0xB3`（栈深 3）、"
                    "PEND `0xB4`（空栈 = 继续）、REPT `0xB5`（`count` + 目标，count 0 = 无限）。"
                    "往返自检：5 首曲子 45 个 block（9952 字节 / 6333 条命令）"
                    "**45/45 逐字节相同**。"
                    "见 `notes/evidence/m4a-block-table-20261021.md`",
                ]
            else:
                note_path = LEGACY_REIDENTIFIED_NOTE.get(
                    name, "notes/evidence/legacy-rebase-nearby-20261020.md")
                spec["title"] = {
                    "character-stats": "逐角色属性表（0x545068，16 字节/条）",
                    "character-stats-b": "逐角色属性表（同表，0x545068 另一个错位窗口）",
                    "levels": "角色特性表（0x5459C8，12 字节/条）",
                    "items": "道具/技能记录表（0x545BE4，16 字节/条）",
                    "skills": "道具/技能记录表（同表，0x545BE4 另一个错位窗口）",
                    "battle-encounters": "战斗遭遇记录表（0x54229C，16 字节/条）",
                }[name]
                spec["rom"] = base
                # The record fields' business names are unknown, so there is
                # no *known* field a writer could change -- the structure is
                # a read-only reference until the fields are named.
                spec["readonly"] = True
                spec["probes"] = [
                    {"kind": "tool", "path": "tools/legacy_rebase.py"},
                    {"kind": "note", "path": note_path},
                    {"kind": "code", "path": note_path,
                     "need": [f"0x{base:06X}"], "address_required": False},
                ]
                spec["unresolved"] = [
                    {"type": "field",
                     "text": "记录里各个 u16 字段的业务名未定（旧字段名来自"
                             "错位窗口，来源已作废）",
                     "writeback_safe": True,
                     "note": note_path,
                     "need": [f"0x{base:06X}"]},
                ]
                spec["corrections"] = [
                    f"旧基址错位，已更正为 `0x{base:06X}`"
                    f"（详见 {note_path}）",
                ]
        if name in LEGACY_CORRECTIONS:
            spec["corrections"] = LEGACY_CORRECTIONS[name]
        if name in LEGACY_REBASE:
            base, title, reader, correction = LEGACY_REBASE[name]
            note_path = LEGACY_REBASE_NOTE
            if name in LEGACY_REBASE_L3:
                # the L3 note carries the full address / field / command
                # record for this re-pointing decision
                note_path = LEGACY_REBASE_L3[name][0]
            spec["title"] = title
            spec["rom"] = base
            # The record fields have no business names yet, so there is no
            # *known* field a writer could change: the structure stays a
            # read-only reference until the fields are named.
            spec["readonly"] = True
            spec["probes"] = [
                {"kind": "tool", "path": "tools/rebase_resolve.py"},
                {"kind": "note", "path": note_path},
                {"kind": "code", "path": note_path,
                 "need": [f"0x{base:06X}", reader], "address_required": False},
            ]
            spec["unresolved"] = [{
                "type": "field",
                "text": "记录里各字段的业务名未定（旧字段名来自错位窗口，来源已作废）",
                "writeback_safe": True,
                "note": note_path,
                "need": [f"0x{base:06X}"],
            }]
            spec["corrections"] = [correction]
            if name in LEGACY_WRITEBACK:
                # the write-back round-trip self-check still covers this
                # bank (the window it writes is inside the re-pointed
                # table), so the path stays usable
                probe = {
                    "kind": "writeback",
                    "path": WRITEBACK_SELFCHECK,
                    "case": LEGACY_WRITEBACK[name],
                }
                if name in LEGACY_WRITEBACK_BASE:
                    probe["base"] = LEGACY_WRITEBACK_BASE[name]
                spec["writeback"] = [probe]
            if name in LEGACY_REBASE_L2:
                consumer, arm = LEGACY_REBASE_L2[name]
                spec["probes"].append({
                    "kind": "dynamic", "path": L2_EVIDENCE_NOTE,
                    "level": "L2",
                    "need": [consumer, arm],
                    "address_required": False,
                })
                spec["probes"].append({
                    "kind": "tool", "path": "tools/l2_runtime_capture.py",
                    "need": [consumer], "address_required": False,
                })
            if name in LEGACY_REBASE_L3:
                note_path, markers, (gate, tool_markers) = LEGACY_REBASE_L3[name]
                spec["probes"].append({
                    "kind": "dynamic", "path": note_path,
                    "level": "L3",
                    "need": list(markers),
                    "address_required": False,
                })
                spec["probes"].append({
                    "kind": "tool", "path": gate,
                    "need": list(tool_markers), "address_required": False,
                })
        if name in LEGACY_WRITEBACK:
            probe = {
                "kind": "writeback",
                "path": WRITEBACK_SELFCHECK,
                "case": LEGACY_WRITEBACK[name],
            }
            if name in LEGACY_WRITEBACK_BASE:
                probe["base"] = LEGACY_WRITEBACK_BASE[name]
            spec["writeback"] = [probe]
        _apply_batch_probes(spec, name)
        rows.append(evaluate_structure(name, spec, ctx))

    rows.sort(key=lambda r: (LEVELS.index(r["level"]), r["title"]))

    # alias map: structures that share a ROM address.  A pair that the
    # registry has already adjudicated (`ALIASES` / `CONFLICTS`) is NOT an
    # open identity conflict any more, so it is not reported as one.
    adjudicated_aliases: set[str] = set()
    try:
        from tools import table_registry  # type: ignore
        adjudicated_aliases = set(getattr(table_registry, "ALIASES", {}) or {})
        # A collision that the registry adjudicates in `CONFLICTS` is just as
        # settled as one in `ALIASES` -- the verdict and the per-bank
        # disposition live there.
        for conflict in (getattr(table_registry, "CONFLICTS", {}) or {}).values():
            adjudicated_aliases.update(conflict.get("banks") or [])
    except Exception:
        adjudicated_aliases = set()
    alias_map: dict[str, list[str]] = {}
    by_address: dict[str, list[str]] = {}
    for row in rows:
        if row["rom"]:
            by_address.setdefault(row["rom"], []).append(row["key"])
    for address, keys in by_address.items():
        if len(keys) > 1:
            for key in keys:
                others = [k for k in keys if k != key]
                alias_map.setdefault(key, []).extend(others)
    alias_map = {k: sorted(set(v)) for k, v in alias_map.items()}
    for key in list(alias_map):
        # A pair is resolved as soon as the registry adjudicates *either*
        # side of it (the canonical owner or the deprecated alias).
        others = [o for o in alias_map[key]
                  if o not in adjudicated_aliases and key not in adjudicated_aliases]
        if others:
            alias_map[key] = others
        else:
            del alias_map[key]

    gaps = build_gaps(rows, alias_map, ctx)

    distribution: dict[str, int] = {level: 0 for level in LEVELS}
    for row in rows:
        distribution[row["level"]] += 1

    bank_distribution: dict[str, int] = {}
    for name, data in banks.items():
        label = data.get("verification") or "missing"
        bank_distribution[label] = bank_distribution.get(label, 0) + 1

    failed = [p for row in rows for p in row["failed_probes"]]

    uncommitted = []
    for row in rows:
        for probe in row["probes"]:
            if probe.get("artifact") and not probe.get("artifact_tracked"):
                uncommitted.append({
                    "structure": row["key"],
                    "artifact": probe["artifact"],
                    "present_locally": probe.get("artifact_present", False),
                })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": ("每结构的四级证据等级（L1 工具产出 / L2 原生定点 / L3 模拟器按键 / L4 完整通关），"
                  "由仓库内可核验的文件证据计算；不含对未提交产物的认定"),
        "banks_found": len(banks),
        "structures_audited": len(rows),
        "level_distribution": distribution,
        "bank_verification_distribution": bank_distribution,
        "format_proven_count": sum(1 for r in rows if r["format_proven"]),
        "writeback_usable_count": sum(1 for r in rows if r["writeback_usable"]),
        "fixture_count": len(fixtures),
        "registry_alias_conflicts": registry.get("alias_conflicts", []),
        "consumer_evidence": {
            "path": CONSUMER_EVIDENCE,
            "status": consumer_status,
            "rom_sha256": rom_sha256,
            "tables": len(consumer_tables) if consumer_tables else 0,
        },
        "adjudicated_count": sum(1 for r in rows if r.get("adjudicated")),
        "failed_probes": failed,
        "uncommitted_artifacts": uncommitted,
        "structures": rows,
        "gaps": gaps,
    }


def markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    dist = report["level_distribution"]
    lines.append("## 逐结构表")
    lines.append("")
    lines.append("| 结构 | ROM 范围 | 格式已证明 | 写回可用 | 等级 | 证据文件 | 剩余缺口 |")
    lines.append("|---|---|:---:|:---:|:---:|---|---|")
    for row in report["structures"]:
        proofs = [p for p in row["probes"] if p["kind"] in ("fixture", "render", "code",
                                                            "roundtrip", "codecite")
                  and p["passed"]]
        evidence = "；".join(p["ref"] for p in proofs) or "—"
        if row.get("adjudicated"):
            evidence += "；[基址已裁决：ROM 零引用]"
        gap = "；".join(classify_unresolved(i)[1] for i in row["unresolved"]) or "—"
        if row.get("corrections"):
            gap += "（已更正：" + "；".join(row["corrections"]) + "）"
        lines.append(
            f"| {row['title']} | `{row['rom'] or '—'}` | "
            f"{'✅' if row['format_proven'] else '❌'} | "
            f"{'✅' if row['writeback_usable'] else '❌'} | "
            f"**{row['level']}** | {evidence} | {gap} |")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    for level in LEVELS:
        lines.append(f"- {LEVEL_LABEL[level]}：`{dist[level]}`")
    lines.append(f"- 格式已证明：`{report['format_proven_count']}` / `{report['structures_audited']}`")
    lines.append(f"- 写回可用：`{report['writeback_usable_count']}` / `{report['structures_audited']}`")
    lines.append(f"- 基址已裁决（ROM 零引用，基址无效）：`{report['adjudicated_count']}`")
    evidence_info = report.get("consumer_evidence") or {}
    lines.append(f"- 原生消费者证据：`{evidence_info.get('path')}` "
                 f"（状态 `{evidence_info.get('status')}`，"
                 f"覆盖 {evidence_info.get('tables', 0)} 张表）")
    if report["uncommitted_artifacts"]:
        lines.append("")
        lines.append("> 下列渲染产物**未被 git 跟踪**，纯净检出下不存在；"
                     "本审计只把它们当作“可由已提交工具重新生成”的附带证据：")
        for item in report["uncommitted_artifacts"]:
            state = "本地已生成" if item["present_locally"] else "本地未生成"
            lines.append(f"> - `{item['artifact']}`（{item['structure']}，{state}，未提交）")
    lines.append("")
    lines.append("## 距离 100% 的缺口（按解锁价值/难度排序）")
    lines.append("")
    blocking = [g for g in report["gaps"] if g["blocking"]]
    hardening = [g for g in report["gaps"] if not g["blocking"]]
    lines.append(f"### 阻塞缺口（`{len(blocking)}` 条，必须清零才算 100%）")
    lines.append("")
    lines.append("| # | 结构 | 等级 | 缺口 | 需要的证据 | 价值 | 难度 |")
    lines.append("|---:|---|:---:|---|---|---:|---:|")
    for index, gap in enumerate(blocking, 1):
        lines.append(
            f"| {index} | {gap['title']} | {gap['level']} | {gap['what']} | "
            f"{gap['evidence_needed']} | {gap['value']} | {gap['effort']} |")
    lines.append("")
    lines.append(f"### 加固缺口（`{len(hardening)}` 条，不属于 100% 门槛，但会提高可信度）")
    lines.append("")
    lines.append("| # | 结构 | 等级 | 缺口 | 需要的证据 | 价值 | 难度 |")
    lines.append("|---:|---|:---:|---|---|---:|---:|")
    for index, gap in enumerate(hardening, 1):
        lines.append(
            f"| {index} | {gap['title']} | {gap['level']} | {gap['what']} | "
            f"{gap['evidence_needed']} | {gap['value']} | {gap['effort']} |")
    lines.append("")
    return "\n".join(lines)


BEGIN_MARKER = "<!-- BEGIN GENERATED: tables -->"
END_MARKER = "<!-- END GENERATED: tables -->"


def sync_note(path: pathlib.Path, body: str) -> bool:
    """Replace the generated block inside `path` with `body` (LF endings)."""
    from tools.lib.io import write_text as write_text_lf

    text = path.read_text(encoding="utf-8")
    if BEGIN_MARKER not in text or END_MARKER not in text:
        return False
    head, rest = text.split(BEGIN_MARKER, 1)
    _, tail = rest.split(END_MARKER, 1)
    write_text_lf(path, f"{head}{BEGIN_MARKER}\n{body}\n{END_MARKER}{tail}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", default="build/completion-audit.json")
    parser.add_argument("--markdown", default=None,
                        help="write the markdown table to this path")
    parser.add_argument("--note", default=None,
                        help="regenerate the generated block inside this note")
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero when any declared probe fails")
    args = parser.parse_args()

    report = build_report()
    body = markdown(report)

    if args.json:
        from tools.lib.io import write_text as write_text_lf
        path = REPO / args.json
        write_text_lf(path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.markdown:
        from tools.lib.io import write_text as write_text_lf
        write_text_lf(REPO / args.markdown, body + "\n")
    if args.note:
        note_path = REPO / args.note
        if not sync_note(note_path, body):
            print(f"note {args.note} has no generated block "
                  f"({BEGIN_MARKER} / {END_MARKER})", file=sys.stderr)
            return 2
        print(f"note regenerated: {args.note}")

    dist = report["level_distribution"]
    print(json.dumps({
        "structures_audited": report["structures_audited"],
        "level_distribution": dist,
        "format_proven": report["format_proven_count"],
        "writeback_usable": report["writeback_usable_count"],
        "failed_probes": len(report["failed_probes"]),
        "top_gaps": [{"structure": g["structure"], "kind": g["kind"], "score": g["score"]}
                     for g in report["gaps"][:5]],
    }, ensure_ascii=False, indent=2))

    if args.check and report["failed_probes"]:
        print("\nfailed probes:")
        for probe in report["failed_probes"]:
            print(f"  {probe['kind']} {probe['ref']}: {probe['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
