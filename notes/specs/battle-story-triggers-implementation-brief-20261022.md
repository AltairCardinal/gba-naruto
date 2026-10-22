# 第十一轮施工说明：战斗编辑界面里的「剧情触发列表」

> 用户需求：
> 「战斗编辑的剧情触发需要关联上剧情，让玩家可以不跳转而在战斗编辑界面
> 直接查看剧情触发列表、编辑每个剧情。」
>
> 本轮**三步走**（用户明确要求）：
> ① 独立子代理做设计 → ② 独立子代理审核 → ③ 实现。

## 产物

| 阶段 | 产物 | 状态 |
|---|---|---|
| 设计 | `notes/specs/battle-story-triggers-20261022.md`（670 行） | ✅ |
| 独立证据 | `notes/evidence/battle-story-trigger-structure-20261022.md` | ✅（主代理与设计子代理各做一遍，互为对照） |
| 审核 | `notes/reviews/battle-story-triggers-review-20261022.md` | ⏳ |
| 实现 | 见下 | ⏳ |

## 设计阶段的关键结论（已被两方独立证实）

- **触发块可认**：`logic`（战场事件逻辑）= 一串「条件 → `0x33` 压事件 id」；
  `events`（战场事件表）= 开头一条连续的 `0x32` 事件链。
- **链是 1 基的**：`0x08097D1A: subs r0,#1`（半字 `0x3801`）→
  `0x08097D1C: cmp r0,r4`（半字 `0x42A0`），链游标 `r4` 从 0 起
  ⇒ **压入 V 选中链上第 V 段**。
- **数量对账**：触发块 407 = 能选到段的 400 + 选不上的 7（场景 32..38 各多压一个 0）。
- **0x34 的 b 比的是回合计数**：`0x0808A198` 读的字面量在 `0x0808A1A0` = `0x0202680C`，
  而 `0x0202680C` = 回合计数是仓库**已定案**的
  （`notes/battle-tables.md` §「2026-10-21 追加：`0x0202680C` **就是回合计数**」）。
- **剧情与变体无关**：剧情按场景索引，同一关的三个变体共用同一份剧情。

## 实现阶段的落点（设计稿 §3）

| 文件 | 改什么 |
|---|---|
| `rom-editor/js/storyvm.js` | `KNOWN_OPERANDS` 补 0x34–0x39 的 u8 字段；`OPERAND_LABELS` 补中文标签；新增比较器名 |
| `rom-editor/js/battletriggers.js`（新） | 触发块模型 + 人话摘要（纯计算，无 DOM） |
| `rom-editor/js/modules/battle-sections.js` | `renderScriptsTab` 重写：根指针表 → 触发块列表 → before/after 指针与操作数表；降级；文案去字面 `**` |
| `rom-editor/js/modules/battle-map.js` | 卡片 hint 文案；`scriptsChanged()` 角标统计触发块里的改动 |
| `rom-editor/css/battle-map.css` | 触发块列表样式 |
| `tools/import_story_script.py` | `KNOWN_OPERANDS` 同步（两边是镜像表） |
| `rom-editor/tools/verify_battle_story_triggers.mjs`（新） | 验收断言（设计稿 §4 的 V1–V12） |
| `notes/story-vm-opcodes-20261020.md` | 补三条新结论（1 基映射 / 0x34 读的两个字节 / 0x35 的 a 恒为 0） |
| `docs/sequel-roadmap.md` | 加一条进度 |

## 写回约束（不可协商）

- **对白等长**：正文内联在指令后面，分支目标是绝对地址 ⇒ 改长改短会移位。
  复用 `rom-editor/js/scripttext.js::commitSegment`（超长当场拒收并回滚），**不重写**。
- **补丁叠加显示**：脚本正文不在任何结构表/文本表的写回范围内，改动只以补丁存在
  ⇒ 界面要用 `scripttext.js::currentBytes` 把补丁叠上去看。
- **写回通路只有三条**：`pack.setText` / `pack.setScriptOperand` / `pack.setBytesAt`，
  **不新开**。
- **u32 跳转目标这一轮不给输入框**（设计稿 D5）：它是地址不是参数，
  可能指到非指令边界且不报错，0x32 的载荷一动就要重划块边界。
  界面**只读显示**目标地址。
- **没证明的语义不许编**：0x35 的三个参数、0x36 的 b、`0x0202680E` 的业务名 ——
  照实显示原始数字 + 一句「仓库还没定名」。

## 降级

`ctx.rom` 为空时（没载入原版 ROM）：触发块列表换成一句说明，
但**根指针表与可改操作数表照常显示**（它们来自内容包，不需要 ROM），
卡片不能因此空掉或报错。

## 两个实测坑（实现前必读）

### 坑 1：场景 32..38 的 logic 与 events **是同一段字节**

实测（`tools/probe_battle_story_overlap.mjs` → `build/battle-story-overlap.txt`）：

| 场景 | logic 根 | events 根 | 差 | scanScript(logic) | scanScript(events) | logic 开头 |
|---|---|---|---:|---:|---:|---|
| 32..38 | 0x805A90C 等 | logic 根 + 8 | 8 | **17** 条 | 13 条 | **4 个 0x33 连着** |
| 40 / 5 | 各自独立 | — | — | 41 / 39 条 | 86 / 39 条 | 条件 + 0x33 |

两个后果：

1. **`scanScript(logicRoot)` 会把 events 的内容一起吸进来**（场景 32..38：
   logic 17 条 = 4 个压值 + 3 个链项 + 10 条文本/其它）。
   ⇒ **不能**把 logic 扫出来的指令统统当「条件」，
   必须按 opcode 分：`0x33` = 压值（触发块的结尾）、`0x32` = 链项、
   **其余**（0x34/0x35/0x36/0x37/0x38/0x39）才是条件。
2. **场景 32..38 的触发条件是「无条件」** —— 那 4 个 `0x33` 前面一条条件都没有。
   界面上这一组的条件摘要要写「无条件」，不能显示成空。

### 坑 2：0x0202680E 的**值**在 0/1 之间交替（不是 0x0E/0x0F）

`notes/evidence/callback-dispatch-tables-20261021.md:278` 写的是
`ctrl[10]（0/1 交替）`；`notes/evidence/open-structures-status-20261022.md:309` 写的是
`ctrl[2]`（0x0202680E）**每回合 ^= 1**。
设计稿 §1.9 把**地址末字节 0x0E** 当成了**观测值 0x0E/0x0F**，
据此得出的「与观测对不上 ⇒ 触发机制是死的」那个推论**不成立**
（观测值 0/1 与 c ∈ {0,1} 恰好对得上）。
⇒ 界面可以照实写「每回合翻转一次的字节（仓库叫 `ctrl[2]`，没有业务名）」，
但**不能**说它是「相位」或「回合奇偶」—— 那是推测。
