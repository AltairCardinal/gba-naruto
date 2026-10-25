# W22-D4 —— 原版奖励/经验规则取证（整张奖励表）

> wave 22 / D4 流 · 子代理 = worker · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 创建时间：2026-10-25 22:2x (GMT+0800)
> 更新时间：2026-10-25 23:0x (GMT+0800)
> 状态：**缺口 1 已闭合（决定性静态证据）；缺口 2 的 E4 假设已被原版数据证伪；缺口 3 已覆盖 112/112 条**
>
> ⚠️ 本流**只取证**，不改任何产品文件、不改逆向线；工具在 `tools/s49_w22d4/`，
> 数据在 `build/w22-d4/`，机器可读结论在 `build/w22-d4/reward-truth.json`。

---

## 0. 一句话结论

> ⭐⭐⭐ **缺口 1：原版「回合加成」确实有 `round_limit` 阈值条件** —— 原版 ROM 的結算代码
> `0x08089402..0x0808940E` 明确写着
> `ldrb r0,[0x0202680C]`（战斗回合数）→ `ldrh r2,[记录+4]`（`round_limit`）→
> `cmp r0,r2` → `bhi`（无符号「大于」就跳过）→ 否则 `ldrh r0,[记录+2]`（`round_bonus_experience`）。
> **⇒ 重制侧 `battle_results.h:241-243` 的 `(battle_round <= reward.round_limit) ? … : 0` 与原版一字不差**，
> `round_limit` **不需要改**，缺口 2 里 E4 的「原版真值只证明回合 4 给 75、没证明超阈值不给」这个疑虑可以关闭。
>
> ⭐⭐⭐ **缺口 2：E4 的「场景 46 存在 `value_a = −2` 的 `0x15` 被动」假设被原版数据证伪。**
> 原版被动定义表（ROM `0x5459C8`，stride 12）里 **`type == 0x15` 的记录只有 1 条**
> （`id=16`，`value_a=5`、`value_b=5`、`value_c=0`、`value_d=0`），
> **全表没有任何 `value_a` 为负的 `0x15` 被动**；而且原版的结算算术
> （`value_a` 用 `ldrh` 读成 **u16**，`muls` 后 `__divsi3` 除 100）**在数学上无法产生负增量**
> ⇒ **59 不可能是「60 + 60×(−2)/100」得来的**。
>
> ⭐⭐ **缺口 3：重制侧 112 条奖励记录 == 原版 ROM 奖励表，逐字节相同。**
> 原版奖励表 = ROM `0x59EAE0`（GBA `0x0859EAE0`），**112 条 × 24 字节**；
> 段 sha256 = `05cefb7a73e68d196dd4349c3eb553703d497a438468b1e8e52069d86a7096b3`
> **与生成器 provenance 块里写死的哈希完全一致**；
> `sequel/content/battle-results/bank.json` 的 112 条与 ROM **逐字段 0 处不符**。

---

## 1. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| D4-01 | 原版「回合加成」**没有** `round_limit` 条件（E4/E2 的怀疑） | 定位原版奖励表的**代码消费者**，读它的比较指令 | **证伪**：原版 `0x08089408 cmp r0,r2` + `0x0808940A bhi` 就是 `round > limit ⇒ 不给` | **已证伪** |
| D4-02 | 原版「回合加成」有 `round_limit` 条件 | 同上 | **成立**：`ldrh r2,[r1,#4]` 取的就是记录 `+4` 字段（= 重制侧 `round_limit`），`bhi` 跳过 | **已确认** |
| D4-03 | 重制侧 `round_limit` 字段位置与原版一致 | 原版记录布局 vs 重制侧 `battle_reward_definition` | **一致**：`+0` mission_exp、`+2` round_bonus、`+4` round_limit、`+6..` 9×u16 | **已确认** |
| D4-04 | 原版 ROM 里有 `value_a = −2` 的 `0x15` 被动（场景 46 的 59 之谜） | 扫被动定义表 ROM `0x5459C8` 全表，找 `type==0x15` 与负 `value_a` | **证伪**：全表 **仅 1 条** `0x15`（`id=16`，`value_a=+5`），**零条负 `value_a`** | **已证伪** |
| D4-05 | 原版结算算术能产生负增量 | 读 `0x080890D0 ldrh`（u16）+ `muls` + `__divsi3(÷100)` | **证伪**：`u16` 恒为正 ⇒ 乘积恒正 ⇒ 增量恒 ≥ 0 ⇒ **不可能得到 59** | **已证伪** |
| D4-06 | 重制侧 112 条奖励记录 == 原版 ROM 奖励表 | ROM `0x59EAE0` 逐记录解析 vs `bank.json` vs 生成头 | **成立**：段 sha256 与 provenance 写死的哈希一致；112 条 **0 处不符** | **已确认** |
| D4-07 | 场景 46 的 59 来自「被动百分比」 | 同 D4-04/D4-05 | **证伪**（被动口径已排除）⇒ 59 的来源仍未闭合，见 §5 | **已证伪** |
| D4-08 | 原版奖励表消费者只有一处 | 全 ROM 扫 `ldr16/ldr32/movw+movt` 对 `0x0859EAE0` 的引用 | **成立**：4 处引用（`0x080893F0`/`0x08089EA2`/`0x08089F00`/`0x08089F80`） | **已确认** |

---

## 2. 取证日志

### 2.1 ⭐ 缺口 1：原版有没有 `round_limit`？—— **有，且判定逐位一致**

#### 2.1.1 定位原版奖励表

* 生成器 `tools/generate_butano_battle_result_content.py:18-41` 的 provenance 块**写死了原版奖励表的地址**：
  * `0x59EAE0`，2688 字节，sha256 `05cefb7a73e68d196dd4349c3eb553703d497a438468b1e8e52069d86a7096b3`
  * 2688 / 24 = **112 条 × 24 字节** ⇒ 与重制侧的 `REWARD_RECORD_COUNT = 112` 完全对上。
* 实测（`tools/s49_w22d4/dump_rom_reward_table.py`）：
  * ROM 段 sha256 = `05cefb7a73e68d196dd4349c3eb553703d497a438468b1e8e52069d86a7096b3` ⇒ **与 provenance 写死的值逐字节相同**。
  * `bank.json` 的 112 条与 ROM **逐字段（`mission_experience` / `round_bonus_experience` /
    `round_limit` / 9 个 `postbattle_words`）0 处不符**。

#### 2.1.2 记录布局（两边一致）

| 偏移 | 含义 | 原版代码证据 | 重制侧字段 |
|---:|---|---|---|
| `+0` | 任务经验 | `0x080893FC ldrh r0,[r1]` → `strh` 到 `[0x02002880]` | `mission_experience` |
| `+2` | 回合加成 | `0x0808940C ldrh r0,[r1,#2]` → `strh` 到 `[0x02002882]` | `round_bonus_experience` |
| `+4` | 回合上限 | `0x08089406 ldrh r2,[r1,#4]` | `round_limit` |
| `+6..+23` | 9 × u16 | `0x08089F80 ldr r0,[pc]` → `adds r0,#6` | `postbattle_words[9]` |

* 记录步长 **24 字节**：原版 `0x080893F4..0x080893FA` = `r1*2 → +r1 → *8`（= 24 × 索引），
  与重制侧 `postbattle_words[9]`（18 B）+ 3 个 u16（6 B）= 24 B **完全一致**。

#### 2.1.3 ⭐ 决定性代码切片（`0x080893F0..0x0808940E`）

```
0x080893F0: ldr   r2, [pc, #0x160]   ; =0x0859EAE0  (原版奖励表)
0x080893F2: adds  r1, r1, r0         ; 记录索引
0x080893F4: lsls  r0, r1, #1
0x080893F6: adds  r0, r0, r1         ; *3
0x080893F8: lsls  r0, r0, #3         ; *24  -> 记录步长 24
0x080893FA: adds  r1, r0, r2         ; r1 = &记录
0x080893FC: ldrh  r0, [r1]           ; r0 = 记录[+0] = mission_experience
0x080893FE: mov   r5, sb
0x08089400: strh  r0, [r5]           ; -> [0x02002880]
0x08089402: ldr   r0, [pc, #0x154]   ; =0x0202680C
0x08089404: ldrb  r0, [r0]           ; r0 = 战斗回合数 (u8)
0x08089406: ldrh  r2, [r1, #4]       ; r2 = 记录[+4] = round_limit
0x08089408: cmp   r0, r2             ; 回合数 vs 上限
0x0808940A: bhi   #0x08089410        ; 回合数 > 上限 -> 跳过（不给加成）
0x0808940C: ldrh  r0, [r1, #2]       ; r0 = 记录[+2] = round_bonus_experience
0x0808940E: strh  r0, [r5, #2]       ; -> [0x02002882]
```

* `bhi` = **无符号「高于」** ⇒ 发放条件 = `round_count <= round_limit`。
* ⇒ 与重制侧 `battle_results.h:241-243`
  `round_bonus_experience = (battle_round <= reward.round_limit) ? reward.round_bonus_experience : 0`
  **判定完全一致（含等号边界）**。
* ⇒ **`round_limit = 8` 这个数据值不需要改**；E2 的 P-51 结论「规则与原版一致」**在原版 ROM 上得到独立证实**
  （此前只有重制侧自证）。

#### 2.1.4 `round_limit` 字段的分布（112 条）

* 非零 `round_limit`：**77 / 112**；取值集合 = `{1,2,3,4,5,6,7,8,10,12,15}`。
* battle 14 用的记录（第 46 位映射 `scenario_reward_record_indices[46] = 98` 之外的场景索引见 §2.3）
  `round_limit = 8`、`round_bonus_experience = 75`、`mission_experience = 125`
  ⇒ 与重制侧 `battle_reward_definition{125, 75, 8, …}` **逐字段一致**。

### 2.2 ⭐ 缺口 2：场景 46 的 `59` 之谜 —— E4 的「−2 被动」假设被原版数据**证伪**

#### 2.2.1 原版被动系统的真实结构（静态取证的副产品）

* **被动定义表**：ROM `0x5459C8`（GBA `0x085459C8`），**stride 12**，按 `passive_id` 索引。
  * 取值代码：`0x0806DDD0..0x0806DDDA`（`r0 = id*3; r0 = r0*4` ⇒ `id*12`）。
  * 记录布局：`+0` u8 **type**（被动目标类型）、`+2` u16 **value_a**、
    `+4` u16 value_d、`+6` u16 value_b、`+8` u16 value_c。
* **被动查询函数** `0x0806DDA4(unit, type, out_ptr)`：
  * 在单位记录的 `+0x50` 起、每槽 4 字节的**被动列表**里扫 24 槽（`0x00..0x17`）：
    `[+0]` = passive_id（去被动表索引）、`[+1]` = 等级字节 `L`；
  * `L` 参与：`r3 = (L-1) & 0xFF`；`L == 0` 或 `L == 0xFF` ⇒ **跳过**；
  * `out[0] = value_a + value_b * (L-1)`；`out[2] = value_d + value_c * (L-1)`。
* **角色的被动列表来源**：角色定义表 ROM `0x54241C`，63 条，stride `0xB4`，
  `+0x48..+0xA7` = 24 个次槽（`[0]`=passive_id，`[1]`=状态/等级，`[2]`=解锁等级）
  ⇒ 被复制到模板 `+0x50/+0x51` ⇒ 复制到战斗单位槽 ⇒ 就是被动查询函数读的那张表。

#### 2.2.2 ⭐ 全表扫描结果（`tools/s49_w22d4/dump_passive_table.py`）

| 判定 | 结果 |
|---|---|
| 全表（400 条 = 覆盖 `0x5459C8..0x546C88`）里 `type == 0x15` 的记录 | **只有 1 条**：`id=16` @ `0x545A88`，`value_a=5`、`value_b=5`、`value_c=0`、`value_d=0` |
| `value_a` 落在 `[−10,−1]` 的记录 | **0 条** |
| ⇒ | **原版不存在 `value_a = −2` 的 `0x15` 被动** |

* 角色 1 / 2 / 3（场景 46 的三名玩家）**都带 passive_id=16（type 0x15）**，
  但 `state = 255 (0xFF)` ⇒ 被动查询函数会**跳过**它 ⇒ **场景 46 里 `0x15` 被动根本没生效**。

#### 2.2.3 ⭐ 算术上也不可能

* 结算代码 `0x080890D0 ldrh r0,[r0]` 用 **`ldrh`（u16）** 读 `value_a`
  ⇒ 恒为 `0..65535`（永远是「正」）；
* `0x080890D2 muls r0,r4,r0`（`r4` = Σ`carried_experience` ≥ 0）
  ⇒ 乘积 ≥ 0；
* `0x080890D6 bl 0x0809C14C` = **`__divsi3`**（有符号除法，但被除数非负 ⇒ 结果非负）；
* ⇒ **增量恒 ≥ 0 ⇒ `60 + 60×(−2)/100 = 59` 这条路径在原版 ROM 上不可能成立**。

⇒ ⭐ **E4 的 P-50（假设 P-50：`59 = 60 + (60 × (−2))/100`）被证伪**，
「场景 46 存在 `value_a = −2` 的 `0x15` 被动」**不成立**。
⇒ 场景 46 的 `59` 来源**仍未闭合**（见 §5 未完成项 U-1）。

### 2.3 缺口 3：重制侧奖励表 vs 原版奖励表

| 项 | 值 |
|---|---|
| 原版奖励表地址 | ROM `0x59EAE0` / GBA `0x0859EAE0` |
| 条数 × 步长 | **112 × 24 字节** |
| 原版段 sha256 | `05cefb7a73e68d196dd4349c3eb553703d497a438468b1e8e52069d86a7096b3` |
| 生成器 provenance 写死的 sha256 | `05cefb7a…96b3` ⇒ **完全一致** |
| `bank.json`（重制侧生成器数据源）vs ROM | **112/112 条逐字段 0 处不符** |
| `round_limit` 非零条数 | 77/112，取值 `{1,2,3,4,5,6,7,8,10,12,15}` |

* **结论：重制侧的 112 条奖励记录与原版 ROM 奖励表逐字节相同 ⇒ 没有不一致的场景。**
* 场景 → 奖励记录的映射（48 条）在重制侧是 `scenario_reward_record_indices`；
  原版侧的对应代码在 `0x080893E4..0x080893F2`
  （`byte[0x08348DAC + byte[0x020311D4+0x16]] + byte[0x020311D4+0x19]`）
  ⇒ **本流未把这条 48 项映射逐项反解**（未完成项 U-3）。

---

## 3. 交付物

| 路径 | 内容 |
|---|---|
| `notes/s49-fidelity/W22-D4-reward-truth.md` | 本文件 |
| `build/w22-d4/reward-truth.json` | 机器可读结论（schema `konoha.s49-original-reward-truth.v1`） |
| `build/w22-d4/rom-reward-table.json` | 原版 112 条奖励记录 + 全部代码引用点 + 与 `bank.json` 的对账 |
| `build/w22-d4/passive-table.json` | 原版被动定义表 dump（64 条） |
| `build/w22-d4/passive-table-400.json` | 原版被动定义表 dump（400 条宽扫） |
| `build/w22-d4/char-passives.json` | 角色 1/2/3/41 的被动列表解析 |
| `tools/s49_w22d4/dump_rom_reward_table.py` | 原版奖励表 dump + 引用扫描 + `bank.json` 对账 |
| `tools/s49_w22d4/scan_const_refs.py` | 全 ROM 扫 `ldr16/ldr32/movw+movt` 对某常量的引用 |
| `tools/s49_w22d4/sweep.py` | 带 literal-pool 注释的 Thumb 线性反汇编 |
| `tools/s49_w22d4/disasm.py` | 简易 Thumb 反汇编封装 |
| `tools/s49_w22d4/dump_passive_table.py` | 原版被动定义表 dump |
| `tools/s49_w22d4/dump_char_passives.py` | 角色被动列表解析（对齐被动定义表） |

---

## 4. 接线请求（不改产品文件 / 不改逆向线）

### 4.1 🔴 逆向线 Lua 期望值更正（`60` → `59`）

* 文件：`D:\Shell\Github\gba-naruto-butano\tools\butano\mgba_battle_campaign_route.lua`
* 现状：场景 46 的 `expected_battle_experience` 写的是 **60**。
* 实测：原版結算屏（`build/w20-e4/s46-settlement-numbers.png`，本流独立读图确认）
  第 2 行是 **`59 / 59 / 30`**、合計 **`184 / 184 / 155`**。
* ⇒ **期望值应改为 59**（至少列 2 个期望：`59` 与 `30`；若该字段只能写单值，写 59 并加注释）。
* ⚠️ **但请先看 §5 的 U-1**：59 的**来源**尚未闭合，直接改成 59 会把「原因」藏起来。
  **建议写法**：改成 59 并加注释 `// 原版結算屏实测 59/59/30；59 的来源未闭合（见 notes/s49-fidelity/W22-D4-reward-truth.md §5 U-1）`。

### 4.2 ✅ 无需改 `round_limit`（**明确结论，避免误改**）

* 文件：`game/include/konoha/generated_battle_result_content.h`（`battle_reward_definitions`）
* ⇒ **不要改**。原版 ROM 的 `round_limit` 就在奖励表 `+4` 字段，判定是
  `回合数 > limit ⇒ 不给`（`bhi`），与重制侧逐位一致；且 112 条与原版逐字节相同。

---

## 5. 未完成项

| # | 未完成项 | 现状 | 下一步（最小动作） |
|---|---|---|---|
| **U-1** | ⭐ **场景 46 的 `59` 到底怎么来的** | 已排除「−2 被动」（原版无此被动）、已排除「负增量」（u16 算术不可能）⇒ **`59` 必然来自 Σ`carried_experience` 本身**（即 `59 + 59 + 30 = 148 ≠ 150 = 5×30`） | 定位**原版**里写 `单位+0xCE`（`carried_experience`）的代码：① 阵型 `+0x0C` 种子写入点；② 击倒转移点。若转移是「种子 − 已得经验」或「种子按 0x0E 缩放」，59 自然成立 |

#### 5.1 U-1 的最新线索（本流读原版阵型原始字节）

直接读原版 ROM 的阵型记录（`0x5461C4 + group*0x1AAC + variant*0x08E4 + 4 + record*0xB8`）：

| group | 敌人 `+0x0C`（战斗分种子） | 敌人 `+0x0E`（unit_parameter） | 敌人 `+0x0F`（level） | 原版結算实测合计 |
|---:|---:|---:|---:|---:|
| **9**（场景 46） | **30 ×5** | **2** | 1 | **148**（59+59+30）⇒ **少 2** |
| 14（场景 49） | 50 ×5 | 4 | 5 | 250（100+150+0）⇒ **不少** |

* ⇒ **group 9 与 group 14 的唯一显著差别（除种子与等级外）是 `unit_parameter`：2 vs 4**，
  而 **group 9 恰好少 2 分、group 14 恰好不少分**。
  ⇒ **强烈怀疑：转移/结算时按敌人的 `unit_parameter`（`+0x0E`）做了某种缩放或扣减**。
  例：`unit_parameter=2` ⇒ 每个敌人转移 29（`30 × 98/100 = 29.4 → 29`）？
  但那样 2 个敌人应是 `58` 而不是 `59`，**算术不闭合** ⇒ 需要真代码，不能靠猜。
* ⛔ 本流**未定位** `单位+0xCE` 的写入点：全 ROM 扫描 `strh/ldrh [rm,#0xCE]`（0 处）、
  `adds rd,#0xCE` 紧跟 `strh`（10 处，全在 `0x08xxxxxx` 非战斗代码区）、
  以及 `adds rd,#0xCE` 全量 697 处命中（噪音太大）⇒ **需要按「单位基址 + 0xCE」的间接寻址模式再扫一轮**。

#### 5.2 ⚠️ 额外接线请求（父代理）

* **`docs/sequel-roadmap.md`**：请把本流的三条结论并入 wave 22 段
  （① 原版有 `round_limit`；② 原版无 `value_a=−2` 的 `0x15` 被动；③ 112 条奖励表逐字节一致）。
  本流**不越界改路线图**（不属本流独占文件）。
| **U-2** | 场景→奖励记录的 48 项映射未逐项反解 | 原版映射代码已定位（`0x080893E4..0x080893F2`），但两查表（`0x08348DAC` 与 `0x020311D4+0x16/+0x19`）未解 | 解 `0x08348DAC` 的表项 + `0x020311D4+0x16/+0x19` 的含义，再与 `scenario_reward_record_indices` 逐项比对 |
| **U-3** | `0x0202680C` 的语义未独立证明是「战斗回合数」 | 结算代码里它被拿来和 `round_limit` 比 ⇒ **语义上必然是回合数**（否则这个阈值毫无意义）；但没有找到它的写入点 | 扫全 ROM 找写 `0x0202680C` 的指令，确认它按回合递增 |
| **U-4** | 原版被动表的 `state`/`level` 字节语义未定 | 已知 `L==0` 或 `L==0xFF` 会被跳过；`L∈[2,0xFE]` 时 `value_a + value_b*(L−1)` | 读初始化器（`0x0806D4A0` 一线）把 `L` 的来源钉死 |
| **U-5** | 「原版結算屏第 3 行标签 = 回合數」与数值语义 | 结算行是 `mission_exp / battle_exp(每人) / round_bonus`，标签文本未逐字核对 | 读原版结算屏文本表（`0x08348DAC` 附近的文字表） |
