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
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/import_battle_config.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
             "case": "encounter-zones"},
        ],
        "unresolved": [
            {"type": "evidence",
             "text": "metatile 缓冲的 2048 上限是由两侧原生结构"
                     "（`0x0201BE2C+0x1000` 与 `0x02021E2C`）夹出来的边界，"
                     "而不是一条明确的分配语句"},
        ],
        "corrections": [
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
        ],
        "unresolved": [
            {"type": "capability", "text": "完整乐曲 m4a→PCM 端到端合成未实现"},
            {"type": "capability", "text": "CGB PSG 声道无法导出"},
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
        "unresolved": [
            {"type": "evidence",
             "text": "`0x0202680C` 已收窄为「每场战斗计数/标志块的首字节」，"
                     "仅在结算时被读（类型 2/4/9 的闸门 + `0x08077BB6` 的兜底），"
                     "但原生代码没有写过偏移 0，是否真的在计回合仍未证明"},
        ],
        "corrections": [
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
        ],
        "writeback": [{"kind": "tool", "path": "tools/build_db_patches.py"}],
        "unresolved": [
            {"type": "capability", "text": "表情 80×80 素材的导入/写回未做"},
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
        "unresolved": [
            {"type": "evidence",
             "text": "剧情底图的 8bpp 条目用哪一路硬件 BG、是否开 256 色模式"
                     "（`BGxCNT` bit8）仍需一次 IO 寄存器抓取；"
                     "已确认的是 4bpp 与 8bpp **互斥**而不是叠加"},
        ],
        "corrections": [
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
            {"kind": "render", "tool": "tools/mgba_probe/render_screen.py",
             "artifact": "notes/evidence/story-scene-l3.png"},
        ],
        "writeback": [
            {"kind": "tool", "path": "tools/import_story_script.py"},
            {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
             "case": "story-vm-roots"},
        ],
        "unresolved": [
            {"type": "field",
             "text": "44 条指令里 38 条已由原生代码证明、6 条仍为推定；未解的是那 6 条子指令的字段名",
             "writeback_safe": True,
             "note": "notes/story-vm-opcodes-20261020.md",
             "need": ["inferred", "proved", "44"]},
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
        ],
        "writeback": [{"kind": "tool", "path": "tools/text_codec.py"}],
        "unresolved": [
            {"type": "ambiguity",
             "text": "8 个字符各有两个码位（基础 GB2312 序 + 扩展块）。规范码已定为"
                     "**基础 GB2312 序里的那个**（8/8 复核通过），但其中 5 个在"
                     "游戏自己的文本里两种拼写都出现过，"
                     "因此「字符 → 码位」单值映射在字节级无法唯一还原；"
                     "字节级精确的路径是 token 流（`tools/text_codec.py::encode_tokens`）"},
        ],
        "corrections": [
            "反向映射已从「取最小码位」改为**规范码**：基础 GB2312 序里的那个码"
            "（扩展块里的同字是冗余拼写，不规范）。"
            "证据与 5 条可证伪检验见 `notes/evidence/font-reverse-mapping-20261020.md`",
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
        ],
        "unresolved": [],
        "corrections": [
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
        "writeback": [{"kind": "tool", "path": "tools/import_dialogue.py"}],
        "unresolved": [
            {"type": "capability",
             "text": "`sequel/editor.db` 被 gitignore，纯净检出下编辑器→构建 override 链空转"
                     "（链本身的键集连接已修好；剩的是「数据库本体不入版本库」这个仓库策略问题）"},
        ],
        "corrections": [
            "`tools/find_sjis_blocks.py` 与 `tools/decode_dialogue_record.py` "
            "**已改用** `tools/text_codec.py`，不再依赖旧手工表 "
            "`sequel/content/text/sjis-to-tile-mapping.json`",
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
        ],
        "unresolved": [
            {"type": "evidence",
             "text": "`story_progress` / `story_branch` / `story_config` 三个字段"
                     "仍无运行时读数"},
        ],
        "corrections": [
            "运行时读数已闭环：`scene_id`（`0x020311EA`）在开场剧情里是 "
            "**54 → 50 → 40**，`battle_stage`（`0x02026805`）= 40、"
            "`battle_sub`（`0x02026806`）= 0、队伍槽 1（`0x02022EF0`）= "
            "角色 1（漩涡鸣人）等级 1",
            "旧推断「`0x020311EA` 是场景号」**已被运行时读数证实**",
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
        ],
        "unresolved": [
            {"type": "ambiguity",
             "text": "四个块分别对应哪四张原版战斗地图，尚未逐一对照"},
        ],
        "value": 3, "effort": 3,
    },
    # ---- banks that are aliases or contradicted ---------------------------
    "audio": {
        "title": "音频 bank（0x53F138，身份冲突）",
        "rom": 0x53F138,
        "bank": "audio",
        "probes": [
            {"kind": "tool", "path": "tools/consumer_locate.py"},
            {"kind": "note", "path": "notes/legacy-table-base-correction-20261020.md"},
        ],
        "unresolved": ["与 palettes 同称 0x53F138；实测该处是 motion/callback/sprite 对象，与音频无关",
                       "真正的 sound-ID 表在 0x465B70（见 sound-id-table 行）"],
        "value": 3, "effort": 2,
    },
    "palettes": {
        "title": "调色板 bank（0x53F138，身份冲突）",
        "rom": 0x53F138,
        "bank": "palettes",
        "probes": [
            {"kind": "tool", "path": "tools/consumer_locate.py"},
            {"kind": "note", "path": "notes/legacy-table-base-correction-20261020.md"},
        ],
        "unresolved": ["与 audio 同称 0x53F138，身份未拆清"],
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
        "unresolved": ["0x08079668 已证实是文本/消息脚本解释器，不是 Sappy 音频分发器",
                       "bank 里的 command_handlers / event_audio_mapping 结论作废"],
        "value": 3, "effort": 2,
    },
    "sprite-animations": {
        "title": "精灵动画 bank（0x53F200，与真表 0x596CCC 不同）",
        "rom": 0x53F200,
        "bank": "sprite-animations",
        "probes": [
            {"kind": "tool", "path": "tools/consumer_locate.py"},
            {"kind": "note", "path": "notes/legacy-table-base-correction-20261020.md"},
        ],
        "unresolved": ["真正的精灵动作表是 0x596CCC（见 sprite-action-table 行）",
                       "本 bank 的 0x53F200 身份未裁决"],
        "value": 2, "effort": 3,
    },
}

# Structures that only exist as a legacy bank: no proof probe is declared, so
# the audit reports them as `none` rather than inheriting the bank's own
# `static_verified` label.
LEGACY_BANK_ONLY = {
    "battle-encounters": [{"type": "relation",
                           "text": "与 0x5461C4 编成表的关系未裁决"}],
    "battle-handlers": [{"type": "relation", "text": "消费者未定位"}],
    "character-stats": [{"type": "relation",
                         "text": "与 0x54241C 角色模板的关系未裁决"}],
    "character-stats-b": [{"type": "relation",
                           "text": "与 0x54241C 角色模板的关系未裁决"}],
    "cutscene-scripts": [],
    "data-table-a": [{"type": "relation", "text": "表内容未定性"}],
    "data-table-b": [{"type": "relation", "text": "表内容未定性"}],
    "fonts": [{"type": "relation",
               "text": "0x53E5B4 字宽表与 0x53D644 字形段表的关系未裁决"}],
    "function-pointers": [{"type": "relation", "text": "消费者未定位"}],
    "levels": [{"type": "relation",
                "text": "与 0x545068 逐角色技能表的关系未裁决"}],
    "map-events": [{"type": "relation", "text": "消费者未定位"}],
    "map-sprites": [
        {"type": "field",
         "text": "描述符记录内部字段名未定。已收窄：记录**变长自描述**"
                 "（实测 12 或 28 字节交替），不是旧笔记说的「11 个字」；"
                 "每条以一个 u32 ROM 指针开头，末尾带下一条记录的地址",
         "writeback_safe": True,
         "note": "notes/evidence/units-offset-table-20261020.md",
         "need": ["0x53F140", "0x0812F5B0", "变长自描述"]},
    ],
    "menu-ui": [{"type": "relation", "text": "消费者未定位"}],
    "resource-pointers": [],
    "save-state": [],
    "story": [{"type": "relation",
               "text": "旧剧情表 0x53636C 与剧情 VM 根表不是同一张"}],
    "story-b": [{"type": "relation", "text": "旧剧情表，身份未裁决"}],
    "story-c": [{"type": "relation", "text": "旧剧情表，身份未裁决"}],
    "story-d": [{"type": "relation", "text": "旧剧情表，身份未裁决"}],
    "story-e": [{"type": "relation", "text": "旧剧情表，身份未裁决"}],
    "tile-assets": [{"type": "relation",
                     "text": "与 0x5A3218 的地块规则关系未裁决"}],
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
        return {"tables": {}, "alias_conflicts": [], "conflicts": {}}
    tables = {name: {"address": addr, "verified": verified, "note": note}
              for name, (addr, verified, note) in table_registry.TABLES.items()}
    conflicts = [c for c in table_registry.verify_table_bases()["alias_conflicts"]]
    return {"tables": tables, "alias_conflicts": conflicts,
            "conflicts": getattr(table_registry, "CONFLICTS", {}) or {}}


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
                if conflict.get("canonical_address") is None:
                    continue
                banks = conflict.get("banks") or []
                if row["key"] in banks:
                    disposition = str(
                        (conflict.get("dispositions") or {}).get(row["key"], ""))
                    canonical = conflict.get("canonical_address")
                    if canonical != row["rom_value"]:
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

        if row["level"] in ("L1", "L2"):
            add("L3", GAP_TEXT["L3"][0], GAP_TEXT["L3"][1],
                max(row["value"], 2), row["effort"] + 1, False)
        if row["level"] in ("L1", "L2", "L3"):
            add("L2", GAP_TEXT["L2"][0], GAP_TEXT["L2"][1],
                max(row["value"] - 1, 1), row["effort"] + 1, False)
    gaps.sort(key=lambda g: (not g["blocking"], -g["score"], -g["value"],
                              g["structure"], g["kind"]))
    return gaps


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
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
    }

    rows: list[dict[str, Any]] = []
    for key, spec in SPECS.items():
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
                ]
                spec["writeback"] = [
                    {"kind": "tool", "path": "tools/import_audio_song.py"},
                    {"kind": "writeback", "path": WRITEBACK_SELFCHECK,
                     "case": case},
                ]
                spec["unresolved"] = [
                    {"type": "ambiguity",
                     "text": "轨数据的块级格式（m4a 的 block 表）未逐字段拆解"},
                ]
                spec["corrections"] = [
                    f"旧基址 0x{base + 4:06X} 晚了 4 字节 —— 它锚在 "
                    f"`voicegroup_ptr` 字段（+0x04）而不是表头起点。"
                    f"本结构**不是**剧情表，而是 sound id {sound_id} 的 "
                    f"**m4a SongHeader**（由 sound-ID 表 `0x465B70` 的第 "
                    f"{sound_id} 行指向）",
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
        if name in LEGACY_WRITEBACK:
            spec["writeback"] = [{
                "kind": "writeback",
                "path": WRITEBACK_SELFCHECK,
                "case": LEGACY_WRITEBACK[name],
            }]
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
