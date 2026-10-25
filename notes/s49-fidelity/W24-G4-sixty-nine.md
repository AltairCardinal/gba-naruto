# W24-G4 —— 逆向取证：场景 46 的「59」之谜 + 两个遗留开放项

> wave 24 / G4 流 · 子代理 = worker · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 创建时间：2026-10-25 23:45 (GMT+0800)
> 更新时间：2026-10-26 00:50 (GMT+0800)
> 状态：**任务 1 = 大幅收窄（找到全部读写点，证伪 3 条机制，来源仍未闭合）；
> 任务 2 = 已产出更正建议；任务 3 = 已复核 + 已产出安全删除脚本**
>
> ⚠️ 本流**只取证**：不改任何产品文件、不改逆向线（`D:\Shell\gba-naruto-reverse`、
> `D:\Shell\Github\gba-naruto-butano` 全程只读）。工具在 `tools/s49_w24g4/`，
> 数据在 `build/w24-g4/`。

---

## 0. 一句话结论

> ⭐⭐⭐ **「59」的来源仍未闭合，但搜索空间从「整个原版结算系统」缩到了「2 个数」**：
> 原版 `carried_experience`（战闘分）的**全部 13 个写入点已被枚举**，
> **其中没有任何一处做减法、没有一处按 `unit_parameter` 缩放、没有一处做取整/截断**；
> ⇒ **59 只能来自「结算时 Σ carried_experience 本来就是 59」**（而不是 60 被减了 1）。
>
> ⭐⭐⭐ **D4 留下的关键线索「结算按 `+0x0E`（unit_parameter）缩放」已被证伪**：
> `+0x0E` 在原版里是**状态特效 id**（消费点 `0x0806C71A` 与 `0xFF` 比较），
> **与经验无关**；且转移是**纯 u16 加法**。
>
> ⭐⭐ **任务 2**：逆向线 `mgba_battle_campaign_route.lua` 里场景 46 的
> `expected_battle_experience = 60` **与原版实测 59 不符**，
> `expected_total_experience = 185` **也与实测 184 不符** ⇒ **两处都要改成 59 / 184**。
>
> ⭐⭐ **任务 3**：33 个 stem / 66 个文件仍零引用，**链接器实测 ROM 占用 264,768 B**
> （两个 map 一致）；已产出「先验证 → 备份 → 删 → 可回滚」脚本（**已 dry-run 通过**）。

---

## 1. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| G4-01 | 「59」来自 `unit_parameter(+0x0E)` 的缩放/取模 | 定位原版转移代码并逐位读 | **证伪**：转移是 `recipient->carried += source->carried`（纯 u16 加法，3 处副本）；`+0x0E` 的消费点是状态特效 id | **已证伪** |
| G4-02 | 「59」来自被动百分比 | D4 已证伪（`ldrh` 恒正，`__divsi3` 恒非负） | 沿用 D4 | **已证伪** |
| G4-03 | 「59」来自某处写 `unit+0xCE` 的减法 | **枚举全 ROM 对 `unit+0xCE` 的全部写入点** | **证伪**：共 **13 处**写入（2 处种子、8 处写 0、3 处转移加、1 处条件 `+=25`），**无一处减法** | **已证伪** |
| G4-04 | 「59」来自种子值的取整/截断 | 读种子写入点 `0x0806AD98` | **证伪**：`ldrh r0,[r5,#0xC]` → `strh r0,[unit+0xCE]`，**逐字节原样拷贝**，无算术 | **已证伪** |
| G4-05 | 「59」来自 seed 本身不是 30 | 直接读 ROM 阵型矩阵 group 9 全 3 变体 | **部分排除**：v0 = 30×5（5 个敌人 slot 3..7）、v1 = 全空、v2 = 50×5 ⇒ **没有任何变体给 29** | **已证伪**（作为唯一来源） |
| G4-06 | 场景 46 的 Lua 期望值应改 | 读 `mgba_battle_campaign_route.lua` + 原版截图 | **成立**：截图实测 `59/59/30`、合計 `184/184/155`；Lua 写 `60` / `185` ⇒ **两处都要改** | **已确认** |
| G4-07 | 33 个零引用旧对白资产仍零引用 | 全树 1256 个候选文本文件重扫 | **成立**：**33 stem / 66 文件**零引用；7 个 `page_1..7` 仍被 `game/src/battle_runtime_scene.cpp` 引用 | **已确认** |
| G4-08 | 旧对白资产 ROM 实占 264,768 B | 两个链接器 map（w20-e4 基线 + w23-f1 最新）交叉复核 | **成立**：两份 map 都给 **264,768 B**（33/33 全部被链接） | **已确认** |
| G4-09 | 「59」= Σ carried 在结算时已等于 59（而非 60 被减 1） | 由 G4-01/03/04 联合推出 | **成立（推理）**：写侧无减法 ⇒ 只可能是读侧的和本身就是 59 | **已确认**（推理） |

---

## 2. 取证日志 —— 任务 1：「59」之谜

### 2.1 ⭐⭐⭐ 原版战斗单位记录的**真实布局**（此前无人钉死）

| 项 | 值 | 证据 |
|---|---|---|
| 单位数组基址 | **EWRAM `0x020240C0`** | 结算代码 `0x0808907E ldr r6,[pc]`（= `0x020240C0`） |
| 记录步长 | **`0x1D4`（468 字节）** | `0x08089086 movs r7,#0xea; lsls r7,#1` ⇒ `0x1D4` |
| 结算扫描的槽位 | **0..12（13 个）** | `0x080890B8 cmp r3,#0xc; bls` |
| 第 14 个槽位 | `0x02025884`（= 基址 + 13×`0x1D4`） | `0x0806AD7E ldr r1,[pc]`（= `0x02025884`），**不在结算扫描范围** |
| `unit+0x00` | character id（u8） | `0x08089092 ldrb r0,[r2]; cmp r0,r5` |
| `unit+0xC0` | u32 flags（bit0 = affiliation） | 初始化 `0x0806AAD4 str r0,[r2]`（= `affiliation | aux | 0x10`） |
| **`unit+0xCE`** | **carried_experience（u16）** | 结算读 `0x080890AA ldrh r0,[r0]` |
| `unit+0xD0` | u32（同值的另一份副本） | `0x0806AB26 adds r0,#2; str r5,[r0]` |
| `unit+0xCD` | **状态特效 id（u8）**，来自阵型 `+0x0E` | 消费点 `0x0806C71A ldrb r0,[r0]; cmp r0,#0xff` |
| `unit+0x10` | u16，**只加进「合計」行** | `0x08089446 ldrh r6,[r6,#0x10]` |

> ⭐⭐ **D4 搜 `strh/ldrh [rm,#0xCE]` 得 0 处的原因找到了**：
> 原版**不用 `strh [rm,#0xCE]` 的写法**，而是用**两条独立的 `adds`** 拼地址：
> `adds r0, r2, #0` → `adds r0, #0xCE` → `strh/ldrh r0,[r0]`。
> ⇒ 本流改用「全 ROM 扫 `+0xCE` 立即数」+「扫 `strh [rm,#imm]` 立即数」两路，
> 命中 **13 处写入点**。

### 2.2 ⭐⭐⭐ 种子写入点（原版权威）

```
; 0x0806ACAC（把阵型记录搬进战斗单位的那一步）
0x0806AD92: ldrh     r0, [r5, #0xc]      ; ⭐ r5 = 阵型记录；r0 = 阵型+0x0C = 战闘分种子
0x0806AD94: adds     r1, r2, #0           ; r1 = &unit[slot]
0x0806AD96: adds     r1, #0xce
0x0806AD98: strh     r0, [r1]             ; ⭐ unit+0xCE = 种子（逐字节原样拷贝，无算术）
```

* 第二份拷贝（**配对单位**，`flags & 0xE == 6` 时）：`0x0806ADB0..0x0806ADB4`，同样取阵型 `+0x0C`。
* ⇒ **种子 = 阵型记录 `+0x0C`**，**没有缩放、没有取整、没有 −1**（**G4-04 证伪**）。

### 2.3 ⭐⭐⭐ 击倒转移点（原版权威）

```
; 0x0806B1A8（transfer 函数；r8 = 受害者槽位, sl = 受益者槽位）
0x0806B1D0: adds     r7, r0, r2           ; r7 = &unit[受益者]
0x0806B1D8: mov      sb, r0              ; sb = &unit[受害者]
...
0x0806B222: adds     r1, r7, #0
0x0806B224: adds     r1, #0xce
0x0806B226: mov      r0, sb
0x0806B228: adds     r0, #0xce
0x0806B22A: ldrh     r0, [r0]             ; r0 = 受害者 carried
0x0806B22C: ldrh     r4, [r1]             ; r4 = 受益者 carried
0x0806B22E: adds     r0, r0, r4
0x0806B230: strh     r0, [r1]             ; ⭐ 受益者 carried += 受害者 carried（纯 u16 加法）
```

* 同函数内另有 **2 份等价副本**：`0x0806B29C..0x0806B2AA`、`0x0806B2EC..0x0806B2F8`。
* 前置条件：`受害者.flags & 0xE ∈ {2,4,6}` ⇒ 不转移；`受益者.flags & 1` ⇒ 不转移。
* ⭐ **受害者的 `carried_experience` 转移后不清零**，但结算会跳过 `flags & 1` 的单位
  （敌人 affiliation=1 ⇒ bit0=1）⇒ 敌人不会进和。
* ⇒ **G4-01 证伪**：转移**不按 `unit_parameter` 缩放**，也**不产生任何 −1**。

### 2.4 ⭐⭐⭐ 结算函数（读侧）

```
; 0x08089064  settle_battle_exp(char_id) -> u16
0x0808907E: ldr      r6, [pc, #0x70]    ; =0x020240C0
0x0808908E: muls     r1, r3, r1        ; i * 0x1D4
0x08089090: adds     r2, r1, r6        ; &unit[i]
0x08089092: ldrb     r0, [r2]          ; char_id
0x08089094: cmp      r0, r5
0x08089096: bne      skip
0x0808909C: ldr      r0, [r0]          ; unit->flags@0xC0
0x080890A0: ands     r0, r1            ; & 1
0x080890A4: bne      skip              ; 敌人跳过
0x080890AA: ldrh     r0, [r0]          ; carried_experience
0x080890AC: adds     r0, r4, r0
0x080890B0: lsrs     r4, r0, #0x10     ; r4 = (r4 + carried) & 0xFFFF
...
0x080890C2: bl       #0x806dda4        ; 被动查询(类型 0x15)
0x080890D0: ldrh     r0, [sp]          ; value_a (u16)
0x080890D2: muls     r0, r4, r0
0x080890D6: bl       #0x809c14c        ; __divsi3 (÷100, 有符号)
0x080890DA: adds     r0, r4, r0
0x080890DE: lsrs     r4, r0, #0x10
```

* **公式**：`戰鬥分 = Σ(同 character_id 且非敌人的单位 carried) + (Σ × value_a) / 100`（u16 截断）。
* 调用点 `0x08089432`：
  * `0x08089442 strh r0,[sb+4+2*i]` ⇒ **屏幕「戰鬥分」行 = `settle_battle_exp` 的原值**；
  * `0x08089446 ldrh r6,[r6,#0x10]` ⇒ **「合計」行额外加上 `unit->u16@0x10`**；
  * `0x0808944C..0x08089456` ⇒ `合計 = (mission + round_bonus + 戰鬥分 + unit->u16@0x10) & 0xFFFF`。

### 2.5 ⭐⭐⭐ `unit+0xCE` 的**全部 13 个写入点**（G4-03 的核心证据）

| # | 地址 | 写入内容 | 性质 |
|---:|---|---|---|
| 1 | `0x0806AD98` | `阵型+0x0C` | **种子**（原样拷贝） |
| 2 | `0x0806ADB4` | `阵型+0x0C` | 配对单位的种子 |
| 3 | `0x0806AB24` | `0` | 建单位时清零 |
| 4 | `0x0806AE4A` | `0` | 清零 |
| 5 | `0x0806AE64` | `0` | 清零 |
| 6 | `0x0806AF94` | `0` | 清零 |
| 7 | `0x0806AFA4` | `0` | 清零 |
| 8 | `0x0806B0E0` | `0` | 清零 |
| 9 | `0x0806B0E6` | `0` | 清零 |
| 10 | `0x0806B230` | `+= 受害者 carried` | **转移** |
| 11 | `0x0806B2AA` | `+= 受害者 carried` | **转移**（副本） |
| 12 | `0x0806B2F8` | `+= 受害者 carried` | **转移**（副本） |
| 13 | `0x08081A0E` | `+= 25` | 条件：章节号 `byte[0x020311D4+0x16]`；场景 46 **不满足**（否则会看到 +25） |

⇒ **全 ROM 里没有任何一处对 `carried_experience` 做减法。**（G4-03 成立）

### 2.6 ⭐⭐ 原版阵型矩阵 group 9 / group 14 实测字节（自算，独立复核 E4）

`ROM 0x5461C4 + group*0x1AAC + variant*0x08E4 + 4 + slot*0xB8`

**group 9（= 场景 46 / battle 9）variant 0**：

| slot | selector | aff | x | y | facing | aux | **+0x0C 种子** | **+0x0E** | **+0x0F** |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 0 | 11 | 15 | 0 | 0 | 0 | 511 | 1 |
| 1 | 2 | 0 | 9 | 15 | 0 | 0 | 0 | 511 | 1 |
| 2 | 3 | 0 | 13 | 15 | 0 | 0 | 0 | 511 | 1 |
| **3** | **41** | **1** | 1 | 5 | 1 | 0 | **30** | **258** | **1** |
| **4** | **41** | **1** | 6 | 4 | 1 | 0 | **30** | **258** | **1** |
| **5** | **41** | **1** | 7 | 9 | 2 | 0 | **30** | **258** | **1** |
| **6** | **41** | **1** | 11 | 5 | 3 | 0 | **30** | **258** | **1** |
| **7** | **41** | **1** | 7 | 22 | 3 | 0 | **30** | **258** | **1** |
| 8..11 | 0 | 0 | — | — | — | — | 0 | 0 | 0 |

* ⭐ **敌人是 slot 3..7（5 个），不是 E4 笔记里的 slot 4..8**（E4 的表对 group 14 成立，对 group 9 差一格）。
* ⭐ **`+0x0E` 是 u16 `258 = 0x0102`**：低字节 `0x02` = unit_parameter，高字节 `0x01` = level。
  ⇒ **D4 记的「group 9 的 `+0x0E`=2、group 14 的 =4」其实是「状态特效 id」**
  （消费点 `0x0806C71A` 与 `0xFF` 比较 ⇒ `0xFF` 表示「无特效」），
  **与战闘分/经验完全无关** ⇒ **D4 的「结算按 `+0x0E` 缩放」线索作废**。
* variant 1 = 全空；variant 2 敌人种子 = 50×5 ⇒ **没有任何变体能给出 29**。

### 2.7 ⭐ 缩小后的范围（负结论也是结论）

**59 = 60 − 1 的「−1」不可能出现在写侧**（§2.5 已穷举），
⇒ **只可能是「结算时 Σ carried 本身就是 59」**。剩下的可能性只有 3 个：

| # | 候选 | 现状 | 判别方法（下一步最小动作） |
|---:|---|---|---|
| **C-1** | **运行时用的阵型记录 ≠ ROM 里的那份**（例如实际 variant 不是 0，或 EWRAM 里的记录被改写） | ROM 里 group 9 三变体分别给 30×5 / 空 / 50×5，**都不给 29** | 跑原版 ROM，在战斗开始后 dump EWRAM `0x02022E34` 附近与 `unit+0xCE`，看 5 个敌人的真实 carried |
| **C-2** | **有一次击杀记到了别的 character id / 或有单位被结算跳过** | 未验证 | 同上 dump 结算瞬间的 13 个单位槽（char_id @+0x00、flags @+0xC0、carried @+0xCE） |
| **C-3** | **被动项非零且基础和是 58**（58 + (58×2)/100 = 59；第三人 30 + 0 = 30） | D4 已证：全表唯一的 `0x15` 被动 `value_a = +5`（非 2），且角色 1/2/3 带它时 state = `0xFF` ⇒ 跳过 | 读 `0x0806DDA4` 的返回值语义（`cmp r0,#0xff`）与角色 1/2/3 的被动槽 `L` |

⭐ **最省事的一步**：**在原版 ROM 上做一次「结算瞬间 EWRAM dump」**（`unit` 数组基址
`0x020240C0`、步长 `0x1D4`、13 个槽，各读 `+0x00` / `+0xC0` / `+0xCE`）
⇒ 一次就能同时判别 C-1 / C-2 / C-3。

---

## 3. 任务 2 —— 逆向线 `expected_battle_experience` 更正建议

> **建议文件**：`build/w24-g4/scenario-46-expectation-correction.md`（**父代理转交**）
> ⚠️ 逆向线**只读**，本流**没有改**任何一行。

### 3.1 事实

| 项 | 原版实测（`build/w20-e4/s46-settlement-numbers.png`，本流独立读图确认） | Lua 现状 |
|---|---|---|
| 經驗值行 | `125 / 125 / 125` | `expected_mission_experience = 125` ✔ |
| **戰鬥分行** | **`59 / 59 / 30`** | **`expected_battle_experience = 60` ✘** |
| 回合數行 | `0 / 0 / 0` | `expected_round_bonus_experience = 0` ✔ |
| **合計行** | **`184 / 184 / 155`** | **`expected_total_experience = 185` ✘** |

* `mgba_battle_campaign_route.lua:85-93`（`expected_battle_experience`）与 `:98-106`（`expected_total_experience`）。
* ⭐ **`expected_total_experience` 也要改**：它 = `mission + battle + round`，
  场景 46 的口径是**第一位玩家**（对照场景 49：`100/150/0` → `125+100+0 = 225` = Lua 写的 225）。
  ⇒ 场景 46 应为 `125 + 59 + 0 = **184**`。
* ⚠️ 这两个期望值是**对原版 ROM 输出的断言**（`assert(battle.result_battle_experience == expected_battle_experience)`，
  见 `:1561-1564` / `:1873-1876` / `:2676-2679` / `:3045-3048` / `:3097-3100`）
  ⇒ **现状下场景 46 的完成路径会在断言处失败**（除非走了 `MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_BATTLE_EXPERIENCE` 环境变量覆盖）。

### 3.2 建议的改法

```lua
local expected_battle_experience = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUSE_EXPECTED_BATTLE_EXPERIENCE",   -- ← 原文件里就是 ROUTE
	...
		(scenario_46_completion and 59 or        -- ← 60 → 59
```

```lua
local expected_total_experience = optional_number(
	"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_TOTAL_EXPERIENCE",
	...
			(scenario_46_completion and 184 or    -- ← 185 → 184
```

* ⚠️ **建议同时加注释**，把「来源未闭合」这件事写进代码，否则以后没人知道 59 是怎么来的：

```lua
-- 场景 46（battle 9）的「戰鬥分」= 59，原版結算屏实测 59/59/30、合計 184/184/155
-- （截圖 build/w20-e4/s46-settlement-numbers.png）。
-- ⚠️ 59 的**来源尚未闭合**：原版「戰鬥分种子」= 阵型记录 +0x0C（group 9 v0 = 30×5，合计 150），
--    转移是纯 u16 加法、写侧无减法（D4 已证伪「负增量被动」；G4 已证伪「按 +0x0E 缩放」）。
--    ⇒ 差额 2 分的来源仍待查，见 notes/s49-fidelity/W24-G4-sixty-nine.md §2.7。
```

### 3.3 ⚠️ 但**不要**改产品侧

* **重制侧 `battle_results.h:369-395` 的公式与原版逐位一致**（`Σ同角色 carried + (Σ×value_a)/100`），
  **不需要改**。
* **种子数据也不需要改**：`generated_battle_scenario_content.h` 里 battle 9 的 5 个敌人已经是 30（E4 §7.1 已证）。
* ⇒ **本开放项是「期望值抄错」而不是「产品算错」**：
  **在 59 的来源闭合之前，产品侧不应该为了迎合 59 去改公式或改数据**（那会把一个未理解的差 2 固化成代码）。

---

## 4. 任务 3 —— 33 张零引用旧对白资产的清理清单

### 4.1 复核结果（wave 20 / E4 之后产品代码变过 ⇒ 重扫）

| 项 | 值 |
|---|---|
| `graphics/scenario_41_postbattle_dialogue_*` 文件总数 | **80**（40 个 stem） |
| **仍被引用** | **7** 个 stem（`..._page_1` .. `..._page_7`）⇒ 全部命中 `game/src/battle_runtime_scene.cpp` |
| **零引用** | ⭐ **33** 个 stem = **66** 个文件（`.bmp` + `.json`） |
| 扫描的候选文本文件 | **1256** |

零引用的 33 个 stem（每个 1 个 `.bmp` + 1 个 `.json`）：

```
scenario_41_postbattle_dialogue_{1..11}_{top,middle,bottom}
```

（`scenario_41_postbattle_dialogue_1_top` … `scenario_41_postbattle_dialogue_11_bottom`）

### 4.2 ⭐ ROM 实占（**链接器 map 实测，不是估**）

| map | 33 个旧资产被链接数 | `.rodata`+`.data` 字节 |
|---|---:|---:|
| `build/w20-e4/butano-sequel/build/butano-sequel.map`（wave 20 基线） | **33 / 33** | **264,768** |
| `build/w23-f1/butano-sequel/build/butano-sequel.map`（最新） | **33 / 33** | **264,768** |

* 对照：7 个 `page_1..7` = **132,992 B**。
* ⚠️ 与 E4 的数字**完全一致** ⇒ **264,768 B 可回收**（≈ 258.6 KiB）。
* ⚠️ 这是**链接器 section 大小**，**未做「删完重建」的第二轮实测**（见 §6 U-2）。

### 4.3 交付的**安全删除脚本**

`tools/s49_w24g4/cleanup_unused_dialogue_assets.py`，四步顺序执行，任一步不过就停：

1. **VERIFY** —— 重新扫全树，确认 33 个 stem **仍然零引用**、且每个文件 sha256 与清单一致；
2. **BACKUP** —— 把 66 个文件逐字节复制到 `build/w24-g4/backup/`（保留相对路径）并写 `backup-ledger.json`；
3. **DELETE**（仅 `--apply`）—— 只删清单里的文件，且删除前再次校验 sha256、且校验路径确实在 `graphics/` 下；
4. **ROLLBACK**（`--rollback`）—— 按台账逐个恢复并复验 sha256。

* ✅ **已 dry-run 实跑通过**：`VERIFY OK: 66 files still match the manifest` → `BACKUP OK` → `DRY RUN`。
* ⚠️ **本流没有删任何文件**（共享树完好无损：80 个文件一个不少）。

```powershell
# dry run（默认）
python tools/s49_w24g4/cleanup_unused_dialogue_assets.py
# 真删
python tools/s49_w24g4/cleanup_unused_dialogue_assets.py --apply
# 回滚
python tools/s49_w24g4/cleanup_unused_dialogue_assets.py --rollback
```

---

## 5. 交付物

| 路径 | 内容 |
|---|---|
| `notes/s49-fidelity/W24-G4-sixty-nine.md` | 本文件 |
| `build/w24-g4/scenario-46-expectation-correction.md` | **任务 2 的更正建议**（父代理转交逆向线） |
| `build/w24-g4/unused-dialogue-assets.json` | 33 个零引用 stem + 逐 stem 引用证据 |
| `build/w24-g4/dialogue-asset-cleanup-manifest.json` | 66 个待删文件的 size + sha256 |
| `build/w24-g4/dialogue-asset-rom-footprint.json` | 两份链接器 map 的 ROM 占用实测 |
| `build/w24-g4/ce-sites.json` | 全 ROM `+0xCE` 立即数站点 dump（含反汇编窗口） |
| `build/w24-g4/backup/` | 删除脚本生成的备份（66 文件 + 台账） |
| `tools/s49_w24g4/scan_ce_writes.py` | 「全 ROM 找 `+0xCE` 物化点 + 反汇编窗口」扫描器 |
| `tools/s49_w24g4/scan_unused_dialogue_assets.py` | 旧对白资产重扫 + 清单 + ROM 实占 |
| `tools/s49_w24g4/cleanup_unused_dialogue_assets.py` | 安全删除脚本（验证→备份→删→回滚） |

---

## 6. 未完成项

| # | 未完成项 | 现状 | 下一步（最小动作） |
|---|---|---|---|
| **U-1** ⭐⭐⭐ | **「59」的来源** | 写侧已穷举（13 个写入点，**无减法**）；转移是纯 u16 加法；种子是阵型 `+0x0C` 原样拷贝；D4 的「按 `+0x0E` 缩放」已证伪；范围缩到 3 个候选（C-1/C-2/C-3） | **在原版 ROM 上做一次「结算瞬间 EWRAM dump」**：读 `0x020240C0` 起 13 个槽的 `+0x00` / `+0xC0` / `+0xCE` ⇒ 一次判别全部候选 |
| **U-2** | 旧对白资产的「删完重建」第二轮实测 | 只做了链接器 map 实测（264,768 B） | 在 lane 里把 `graphics/` 换成真实目录后删掉 66 个文件重建，比对 ROM 大小；**注意 lane 的 `graphics/` 是共享树的符号链接，直接删会打到共享树** |
| **U-3** | 原版 `unit+0xCD`（状态特效 id）的完整语义 | 只证了「与经验无关」 | 读 `0x0806C71A` 上下文与 `0x0806D4A0` 的模板构造 |
| **U-4** | 原版被动查询 `0x0806DDA4` 的返回值语义 | 只证了 `cmp r0,#0xff` ⇒ 「找不到则跳过」 | 逐条读 `L`（等级字节）的来源，闭合 D4 的 U-4 |

---

## 7. 本波新增的仪器教训（建议并进 AGENTS.md）

> ⭐⭐ **搜「字段写入点」时，先确认字段偏移在**目标 ROM**里是几。**
> D4 拿**重制侧**的 `unit+0xCE` 去搜原版 ROM 的 `strh [rm,#0xCE]`，得 0 处，
> 于是判定「原版没有转移代码」—— 实际上原版**也是 `+0xCE`**，但
> **地址是用两条独立 `adds` 拼出来的**（`adds r0,r2,#0` + `adds r0,#0xCE`），
> 任何「`strh [rm,#imm]`」或「`adds rd,#imm` 紧跟 `strh`」的模式都匹配不到。
> ⇒ **可靠做法：扫「物化该立即数」的所有站点 + 逐个看反汇编窗口**，而不是猜指令模式。
>
> ⭐⭐ **「数值对不上」优先怀疑「口径」，其次才怀疑「算错」。**
> 场景 46 的 `59/59/30`（合计 148）与 5×30 = 150 差 2，
> 在把**写侧 13 个写入点全部读完**之前，任何「−1 来自某处」的猜测都是噪音。
> 本波证伪了 3 条机制（被动百分比 / `+0x0E` 缩放 / 写侧减法），
> 每一条都是**「读侧和本来就是 59」**这条结论的支柱。
