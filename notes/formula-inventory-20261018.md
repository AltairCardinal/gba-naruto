# 逆向成果公式与参与属性总清单（2026-10-18）

**ROM:** `火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba`
**SHA-1:** `26f60795fa5e63b4f0264b84e453beffd56b9f7d`（`docs/structure-field-semantics.md:3-4`）
**SHA-256:** `1198ece7…59d05b`（战斗域函数绑定引用）

**本文性质：** 只读汇总。把散落在 `notes/`、`docs/` 中的、已被 ROM 证据闭合的公式与参与计算的属性字段集中成一张可检索清单。**不新增任何结论**；所有「闭合状态」措辞照抄原文，未升级也未降级。

**四域覆盖：** 战斗数值 / 音频引擎 / 图形动画 / 关卡地图剧情。
**排除：** 已被证伪的旧解释、宿主（Butano）侧工程常量（单列于第 9 节）、未闭合候选。

---

## 0. 符号约定

- `unit` = 战斗单位结构，基址 `0x020240C0 + slot*0x1D4`（`notes/battle-level-stat-runtime-20260726.md:40`）
- `file` = ROM 文件偏移；`0x08xxxxxx` = 运行地址
- `trunc0` = 向零截断；`>>` = 逻辑右移；`trunc()` = 向下取整
- `Q8.8` = 8.8 定点

---

## 1. 战斗数值域

### 1.1 等级 / 成长 / 属性上限

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| 等级属性成长 | `value(level) = base + growth × (level-1) / 100`，整数向下取整 | 成长表 `0x545068` 63×`0x10`；`+0x00→模板+0x0E`（体力上限）、`+0x02→+0x08`（查克拉）、`+0x04→+0x02`（攻）、`+0x06→+0x03`（防）、`+0x08→+0x04`（敏）、`+0x0A→+0x05`（移动）、`+0x0C→+0x06`（忍具容量）；`+0x0E` 未被读取 | `notes/battle-level-stat-runtime-20260726.md:41-42`；`notes/character-growth-runtime-chain-20260711.md:64-79` | 已闭合；消费函数 `0x0806D964` |
| 成长阶段基础钳制 | HP≤999；攻/防/敏≤99；移动≤5；查克拉/忍具容量≤9 | `unit+0x0E`、`+0x02`、`+0x03`、`+0x04`、`+0x05`、`+0x08` | `notes/battle-level-stat-runtime-20260726.md:41-44` | 已闭合；原文：「这里的 `9` 是纯等级成长阶段的基础钳制，不是持久被动后的最终上限」 |
| 持久被动属性双 pass | 先跑 targets `2/6/8/11` 的百分比提升与结印成本降低（`0x0806DAE6..0x0806DC19`），再跑 `1/3/4/5/7/9/10` 固定加值（`0x0806DC1A..0x0806DD95`）；最终钳制 target1/2 HP 999、3 查克拉 9、4 攻 99、5/6 防 99、7/8 敏 99、9 移动 9、10 忍具容量 99、11 结印降幅最小 1 | 被动槽 `unit+0x50+4i`（ID）、`unit+0x51+4i`（等级）；表 `0x085459C8` 45×12B；jump table `0x0806DC7C` | `notes/battle-persistent-passive-stat-runtime-20260727.md:33-47`；`notes/battle-persistent-passive-stat-bindings-20260727.json` | 已闭合；`target 2/6/8` 在第二张 jump table 中显式 no-op |
| 被动逐级取值（统一） | `base_a + per_level_a × (stored_level - 1)`，同时返回两个独立成长分量 | 槽 ID / 槽等级同上 | `notes/battle-persistent-passive-stat-runtime-20260727.md:26-31` | 已闭合；ID 0、level 0、level `0xFF` 不查询；同 type 只返回首个活动槽 |
| 被动动作修正双 pass | 先全 24 槽百分比 pass（`0x0806D6C0..0x0806D75D`），再全 24 槽固定 pass（`0x0806D75E..0x0806D84F`）；target 14/16 百分比增 potency≤99，13/15/17 固定增≤99，18（effect `0x1A`）固定增 u8 无 99 上限，19 固定增成功率 | 动作描述 header `0x0102/0x0101/0x0105`、effect；jump table `0x0806D7B8`；调用点 `0x0806D906`（主动技）/`0x0806D954`（忍具） | `notes/battle-passive-action-modifier-runtime-20260727.md:36-49` | 已闭合；targets 14/16 在固定 jump table 中显式 no-op |
| 地形类别逐路径预算 | 访问类别 `1/3/7` 的格子递减该类别局部剩余量，不足即拒绝该候选路径；递归按值保存剩余量，兄弟路径复用父层 | target `0x1A/0x1B/0x1C` → 类别 `1/7/3`；`0x08069DB8`、`0x08069D1C`；基值 2、每级 +1 | `notes/battle-terrain-passive-runtime-20260726.md:29-36` | 已闭合为「单条候选路径可穿越多少格该类地形」；原文：「不是战斗内会被用掉的资源」 |
| 忍具装备数量 | 循环上界取容量值，在 `+0xB1+i` 找首个空槽写入，只把 `+0xB0` 加一；不读逐件重量 | `unit+0xB0`、`unit+0xB1..+0xB9`、容量 `+0x06`；`0x08090004..0x08090049` | `notes/battle-persistent-passive-stat-runtime-20260727.md:48-52` | 已闭合为「可装备数量」；target 10 的 99 只是算术分支上限 |
| 经验阈值 | `required(level) = base_threshold + per_level_increment × (level-1)`；反复扣除升级，最大等级 50，余 EXP 钳制 999 | 表 file `0x59F560` 63×4；消费函数 `0x0808983C`；鸣人 15/250、佐助 15/180、小樱 15/150 | `notes/battle-result-progression-runtime-20260725.md:76-94` | 已闭合 |
| 战后奖励 | `total = mission_experience + round_bonus_experience`；`current_round <= round_limit` 才取得回合奖励 | 场景→奖励映射 file `0x348DAC` 48×u8；奖励表 `0x59EAE0` 112×`0x18`，`record+0..+5` | `notes/battle-result-progression-runtime-20260725.md:61-72` | 已闭合；`+0x06..+0x17` 九个 postbattle u16「在消费者语义闭合前不命名」 |
| 战败经验转移 | 目标被击败时把其 `+0xCE` 加给归属单位 | formation `+0x0C` → `unit+0xCE`（`0x0806AD92`）；转移点 `0x0806B224/0x0806B29E/0x0806B2EC` | `notes/battle-result-progression-runtime-20260725.md:38-59` | 已闭合（转移方向）；召唤/关联单位特殊归属分支未闭合 |
| 战后七项成长差 | `0x08089AE0` 分别构造旧/新等级模板后显示差值 | 模板 `+0x0E/+0x08/+0x02/+0x03/+0x04/+0x05/+0x06` | `notes/battle-result-progression-runtime-20260725.md:96-104` | 已闭合（代码与屏幕标签双证） |

### 1.2 伤害 / 命中 / 会心

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| 逐层伤害候选 | `scaled = trunc(attack × attack_percent / 100)`；`raw = trunc(power × scaled / 10)`；防御倍率 `100 - 5 × isqrt(defense)`；全程整数顺序向下取整 | 攻击者 attack、目标 defense；模板 `+4` power、attack_percent | `notes/battle-damage-hit-bindings-20260723.json:17-20`；`notes/battle-system-restoration-evidence-20260723.md:612-614` | 已闭合（builder `0x080754A8`）；状态/朝向/地形特例未闭合 |
| 四候选预存 | 事件预存普通计防御 / 150% 会心计防御 / 普通无视防御 / 150% 会心无视防御 | `event+0x18`、`+0x1A`、`+0x1C`、`+0x1E`；自然样本 `[9,13,11,16]` | `notes/battle-system-restoration-evidence-20260723.md:615-617` | 已闭合（候选产生）；结算侧选择依赖逐 hit flag |
| 逐 hit 成功率 | `success_rate = min(99, template_rate + trunc((source_agility - target_agility) / 2))`；`rng_percent = (rng_value × 100) >> 15`；命中条件 `rng_percent < success_rate`（严格小于） | 模板成功率 `+6`；源/目标 agility `unit+0x04` | `notes/battle-damage-hit-bindings-20260723.json:2-7`；`notes/battle-system-restoration-evidence-20260723.md:618-623` | 已闭合（逐 hit 生成器 `0x08076034`） |
| 会心概率门 | 命中后查被动 `0x0C`：`critical_rate = min(100, passive_value + 10)`，独立比 `(rng×100)>>15`，成功则 hit flag 写 2 | 被动槽 `unit+0x50+4i`、`+0x51+4i` | `notes/battle-system-restoration-evidence-20260723.md:635-637` | 已闭合；未装备该被动时不消耗附加 RNG |
| 无视防御概率门 | 查被动 `0x19`：无视率 = `passive_value`，再次独立抽 RNG，成功则 `flag |= 4`；RNG 顺序＝命中→会心→无视防御 | 同上 | `notes/battle-system-restoration-evidence-20260723.md:637-639` | 已闭合；「激活被动会改变后续 RNG 流」 |
| 有效命中分派门 | 扫描当前 event 全部 hit 结果，仅当至少一项有效才置 effective 标志；无有效 hit 直接跳过 effect handler | event hit 标志数组；effect `0x0E/0x0F/0x21/0x3F` | `notes/battle-damage-hit-bindings-20260723.json:22-29` | 已闭合；仅约束 opponent 目标策略的 status/reaction family |
| 反应优先级与多段截断 | blocker 顺序 `3F→3E→3D→0F→11→15`；reaction 顺序 `04→0A→09→10→16→19`；reaction 只对非零命中生效；写轮眼 `0x10` 把 `event+0x12` 截到「当前索引 + 1」，该 hit 被替换，后续 hit 不执行 | `event+0x12`（待逐个判定的 hit 数）；反应码 `unit+0xD4`、`unit+0xD5` | `notes/battle-system-restoration-evidence-20260723.md:660-668` | 部分闭合：当前只闭合写轮眼 `0x10` 与火弹 `0x19` |
| 火弹反击 | `0x19` 分支（`0x08076A30`）递归反转 source/target 并再调共享 resolver；观察：佐助 HP `134→134`，攻击者 `17→3` | `unit+0xB0`、`unit+0xB1`、`unit+0xD4=0x19`、`unit+0xD5=0xAE` | `notes/battle-system-restoration-evidence-20260723.md:669-677` | 已闭合（火弹单条） |

> 关键边界：界面显示的「6×3」不是最终伤害，不能把模板攻击力直接乘 hit 数后扣 HP（`notes/battle-system-restoration-evidence-20260723.md:626-627`）。

### 1.3 资源命令

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| 查克拉补充 | 每 1 点查克拉消耗 `unit+0x0A`（结印）作为 HP 成本，且仅当 `current_hp > cost` 才可继续，故提交后 HP ≥ 1；数量受 `unit+0x08` 上限约束 | `unit+0x07` 当前查克拉、`+0x08` 上限、`+0x0A` 结印、`+0x0C` 当前 HP | `notes/battle-system-restoration-evidence-20260723.md:505-509` | 已闭合（基础命令规则）；只闭合无额外修正分支 |
| 休息 | `heal = min(trunc(max_hp / 5), max_hp - current_hp)`；佐助 LV3 `89→24→41`；鸣人 LV6 `152→17→47` | `unit+0x0E` 最大 HP、`unit+0x0C` 当前 HP | `notes/battle-system-restoration-evidence-20260723.md:510-514` | 已闭合；被动/状态/脚本覆盖分支不能用本式推断 |
| 忍具战斗内消费 | 提交确认清空首个装备槽 `unit+0xB1` | `unit+0xB0`、`unit+0xB1` | `notes/battle-system-restoration-evidence-20260723.md:488-492` | 部分闭合：只证明事务方向与提交边界；`unit+0xB0` 完整布局未闭合 |

### 1.4 状态修正与生命周期

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| 属性状态族有序重算 | 暂存当前 character ID → 写回原始 ID `unit+0xBC` → 调基础属性 loader → 恢复 → 按活动状态槽 0→15 顺序读 code 与记录 `+6` 的 u16 potency；**百分比每步以前一步当前值为基数**做整数除法（同属性状态不可先求和） | 状态记录 `unit+0xD4` 起步长 8；potency 记录 `+6`；偏移 attack 2/defense 3/agility 4/movement 5/current_hp 12/max_hp 14；reducer `0x0806D1EC` | `notes/battle-status-attribute-modifier-bindings-20260723.json:385-411`；`notes/battle-system-restoration-evidence-20260723.md:930-939` | 已闭合（reducer 公式、上下限、producer、复合效果、持续时间、side-end 顺序全部 closed） |
| 各状态加减操作 | `0x12/0x1E` 攻+%（cap 99）、`0x1F` 攻−%（floor 0）、`0x20/0x21` 防 ±%、`0x22/0x23` 敏 ±%、`0x24` 移动绝对+（cap 9）、`0x25` 移动绝对−（floor 0）、`0x1B` 最大 HP+%（cap 999） | 同上 | `notes/battle-status-attribute-modifier-bindings-20260723.json:88-139` | 已闭合 |
| 复合效果 `0x26` | 以同一 target/potency/duration/source 依次建立四条独立状态 `0x1E→0x20→0x22→0x1B`（不存 code `0x26`）；HP 规则：新最大 HP 更高则当前 HP += 正差值，否则仅在超出新上限时钳制 | 忍具 91–93（potency 10/30/50）；branch `0x08077590`；`unit+0x0E`、`unit+0x0C` | `notes/battle-status-attribute-modifier-bindings-20260723.json:69-82` | 已闭合 |
| side-end 顺序 | `0x0807367C` tick → `0x08073680` removed-event → `0x08073684` 由 `0x0806D440` 重算单位 1–12；正 duration 到零走完整移除路径，duration 0 不递减且必须保留 | `unit+0xD4`（code）、`unit+0xD6`（duration）、已移除事件区 `unit+0x154..+0x1D4` | `notes/battle-system-restoration-evidence-20260723.md:690-693` | 已闭合 |
| 状态 `0x13` hit count 修正 | builder 在 effect type `0x14` 分支查 source 状态 `0x13`，读记录 `+6` 低字节加到共享 accumulator；`event+0x12 = 模板 hit count + accumulator`；resolver 先结算再以 mode 1 移除 `0x13` | `unit+0xD4` 槽位、记录 `+6`、`event+0x12` | `notes/battle-system-restoration-evidence-20260723.md:843-849` | 已闭合；`+6` 高字节与其他 hit-count modifier 未闭合 |
| 状态 `0x13` 阶段资格 | 读记录 `+6` 完整 u16：第一门仅状态不存在时可选；第二～五门要求阶段恰为 `1/2/3/4`（原因码 `10..17`）；表莲华要求存在且阶段≤2（18/19）；里莲华要求存在且阶段>2（20） | 模板 `+2=0x13`、`+4`=阶段 1–5、`+9`=duration 0、`+0x0A`=资源值 10/20/30/40/50 | `notes/battle-system-restoration-evidence-20260723.md:867-886` | 已闭合（架构）；原因码 9–20 的可见文案未闭合 |
| 状态 `0x05` 身份覆盖 | effect low6 `0x05` + duration 3 → upsert 存 6 ticks；helper 只覆盖 source 的 character ID = target 的 character ID（refresh mode 8），不复制单位记录；恢复从 `unit+0xBC`（mode 0），`unit+0xCA` 非零时原始 ID 8/15 → `0x39/0x3A` | `unit+0xBC`、`unit+0xCA`、记录 `+4` | `notes/battle-system-restoration-evidence-20260723.md:900-914` | 已闭合；可见显示名未闭合 |
| 状态 `0x0E` 联动递归 | action type ≠ `0x1F` 时查主目标 `0x0E`，按槽索引 ×8 读记录 `+4` 的联动单位槽，`0x08076B6C` 递归调同一 resolver（末位参数 `[0,0,0,1]` 为 guard）；返回后再读主目标 HP → 先递归、后主目标 | `unit+0xD4` 槽位、记录 `+4` | `notes/battle-system-restoration-evidence-20260723.md:754-761` | 已闭合（中性操作语义）；「不能据此命名成替身、分身羁绊或援护」 |
| 状态 `0x0D` 参与者消费 | event type low6 ∈ `0x04/0x09/0x0A/0x10/0x16/0x19` 时整块跳过；否则按 source、target 顺序查 `0x0D`，存在即 status remove mode 0 消费；target 命中时 `unit+0xC0 &= 0xFFFFFEFF` | `unit+0xC0`（bit `0x00000100`） | `notes/battle-system-restoration-evidence-20260723.md:774-781` | 已闭合；该 bit 业务名未闭合 |
| effect 高位 follow-up | 门条件 `sp+0x18 != 0 && (event+0x0E & 0x0700) == 0x0200`；bit `0x80` → code `0x3F`、一回合、`value_u16=0` + reaction state `0x30`；bit `0x40` → `0x1F/0x21/0x23` 各固定 10、三回合 | `event+0x0E`、event potency、source unit | `notes/battle-effect-flag-followups-20260726.md:23-35` | 已闭合；miss 不建状态、容量不足整体回滚 |
| 主动/忍具状态生产参数 | 动作 14/25/29 → `0x1E` 25/15/25、0 ticks；31 → `0x21` 10、3→6 ticks；37/38 → `0x12` 20、4→8 ticks；忍具 55–93 各档 8 ticks（移动 1/2/3，攻防敏 10/30/50 或 25/50/75，`0x26` 为 10/30/50） | 主动表 `0x08545458` 87×16B、忍具表 `0x08545BE4` 94×16B；模板 `+2` code、`+4` potency、`+9` duration | `notes/battle-status-action-compliance-20260726.md:18-51` | 已闭合（33 个生产定义的数值语义） |

### 1.5 AI 数值

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| 格（站位）评分 | 面向相同 `+50`；无威胁 `+200`（不消费 RNG）；有威胁但当前面向方向无来源 `+100`；受威胁分支再加 `(rng × 50) >> 15` | `unit+0xC4/+0xC5`；地图宽 `u8(0x0201BE2A)`；候选场 `0x02002880`；`0x08085160` | `notes/battle-system-restoration-evidence-20260723.md:323-327` | 已闭合（局部形状）；视线、碰撞过滤未闭合 |
| 严格择优 | 仅当 `candidate_score > best_score` 才复制 20 字节候选并更新 best；等分保留先枚举项 | `0x080855A2`/`0x080855A8` | `notes/battle-system-restoration-evidence-20260723.md:317-318` | 已闭合 |
| 动态威胁/候选场 | 只为 damage family `0x01/0x14/0x15` 写威胁 bit `0x01`，再 OR 来源方向 bit `0x10/0x20/0x40/0x80`；非零区 = 曼哈顿半径 4（movement 3 + hostile range 1） | 场 `0x02002880`（198B）、地图宽高 `0x0201BE2A/+1B`、有效格 `0x0202CA27` | `notes/battle-ai-candidate-field-runtime-20260725.json:71-91` | 已闭合（field 身份、5 bit 含义、范围、scenario-41 并集） |
| 目标索引七槽 | 扫单位槽 1→12，按 `unit+0xCC` 分同/异阵营各 7 槽（当前 HP 比例、最大 HP、攻、防、敏、移动、地图距离）；每项仅在指标严格更小时替换 | `unit+0xCC`、`unit+0xCA`、单位池 `0x020240C0`；`0x0808400C..0x08084266` | `notes/battle-system-restoration-evidence-20260723.md:393-397` | 已闭合；「不能压缩成最近敌人或单个 target_id」 |
| 目标槽权重 | 异阵营 `[1700,800,800,1300,1000,800,3600]`；同阵营 `[4200,2000,1000,1000,1000,800,0]`；同目标命中多项可叠加 | `notes/battle-ai-utility-policy-bindings-20260723.json` | `notes/battle-system-restoration-evidence-20260723.md:398-401` | 已闭合；「这不是互斥枚举」 |
| 伤害效用组件 | 按目标聚合 `signed(event+0x18) × event[0x12]`，再以目标当前 HP 截顶；伤害/最大成功率/覆盖目标数/最大地图距离权重 `6000/900/3000/100`，按目标 HP、100、有效异阵营单位数、行动者最大动作距离归一化；各组件做**整数平均**而非原始分相加 | `event+0x18`、`event[0x12]`、目标当前 HP、有效异阵营单位数、行动者最大动作距离 | `notes/battle-system-restoration-evidence-20260723.md:402-406` | 已闭合（「已闭合的局部评分形状」范围内） |
| 行动效用最终扰动 | 普通评分最后只加 `(rng × 10) >> 15`（0–9） | `0x08085132..0x08085136` | `notes/battle-system-restoration-evidence-20260723.md:411-413` | 已闭合；「与格评分的 0–49 扰动是两项不同机制，不能混为一项」 |
| 候选类型写入 | `0x0202D262[candidate_index]`：1=移动、2=提炼查克拉、3=休息、4=已选动作；索引取 `u8(0x0202D261)-1`；类型 2/3 用配置 `+0x24`，其他无动作候选用 `+0x28` | `0x0202D262`、`0x0202D261`、`0x080829CC` | `notes/battle-ai-action-component-runtime-20260727.md:6-17` | 已闭合（纠正 Butano 旧 `ai_role` 映射） |
| 动作组件计数 | kind 1 → 配置 `+0x18` + 一个聚合伤害组件（count 合计 +2）；kind 4 → `+0x20`（+1）；kind 5 → `+0x1C` + 按 effect low3 选 `[+0x84,+0x74,+0x78,+0x7C,+0x80,+0x74,0,0]`（+2）；其他已选 kind → 零值组件（+1）；未选动作 → `+0x24`/`+0x28`（+1） | 运行时动作描述表 `0x02030D29`（步长 16）：`+0` runtime kind、`+1..+2` 半字中 `0x0700` = effect low3 | `notes/battle-ai-action-component-runtime-20260727.md:40-57` | 已闭合；kind 1 的四个加权子项先求和再作为**一个**聚合组件加入平均 |
| actor 惩罚（除法前） | actor event/status `0x12/0x12` 或 `0x0D/0x0D` 首次匹配时，从分子减一次 `weight[0x84] + weight[0x1C]` 后退出；惩罚发生在整数除法之前，不增加 component count | 配置 `weight[0x84]/[0x1C]`、actor 状态 | `notes/battle-ai-action-component-runtime-20260727.md:56-57` | 已闭合 |
| event `0x11` 条件减分 | 若 `cur_hp > trunc(max_hp/2) && cur_chakra > trunc(max_chakra/2)` → 直接减 `weight[0x84]+weight[0x1C]`；否则以 `unit+0xC5 × u8(0x0201BE2A) + unit+0xC4` 索引候选场，bit 0 为 1 也减；两分支只减一次 | `unit+0x0C/+0x0E`、`+0x07/+0x08`、`+0xC4/+0xC5`、`0x02002880` | `notes/battle-ai-action-component-runtime-20260727.md:61-69` | 已闭合（逐指令绑定） |
| effect `0x07` 安全落点奖励 | 四条 scenario rule 槽均未处理 kind 1–5、selected action index ≠ `0xFF`、首条 queued event low6 = `0x07`、且 `event+0x15` 选出坐标不在 threat bit `0x01` 内时，分子固定 `+8000`，分母不变 | `event+0x15`、`event+2/+3`、`unit+0xC4/+0xC5`、`0x02002880` | `notes/battle-ai-action-component-runtime-20260727.md:78-88` | 已闭合；「只检查第一条 event，不能泛化为所有召唤事件」 |
| scenario rule 分量计数 | 每个被识别 kind 即使条件未命中、值为 0 也增加 count：kind 1 → `+2`；kind 2 → `+1`；kind 3/4/5 各 `+1`；最终以总 count 做一次整数除法 | 配置 `0x0853F348` 8×`0xA8`，尾部 4 个步长 8 的规则槽；`unit+0xCD` 选行 | `notes/battle-ai-action-component-runtime-20260727.md:94-104` | 已闭合；五种 custom rule 的可见名称未闭合 |
| 行动者 HP/查克拉投影 | 先加 `weight[0x00] + weight[0x0C]`，然后 HP 与查克拉**各只选一个互斥分支**：candidate 严格大于 baseline 时按增量/最大值用 `0x04` 或 `0x08`；否则按 candidate/baseline 保留比例用 `0x10` 或 `0x14`；两分支合计只把 count 增加 2 | actor `unit+0x07/+0x08/+0x0C/+0x0E`；scorer `0x080843DC..0x0808444E` | `notes/battle-ai-config-and-projection-runtime-20260727.md:12-18` | 已闭合（纠正 Butano 旧「四项同时平均」偏差） |
| AI 配置选择 | `unit+0xCD` 直接选 `0x0853F348` 的一条 `0xA8` 配置；阵型 `unit_parameter` 是持久来源；config 0 全零，1–7 的 `0x00..0x87` 相同，差异在 `0x88..0xA7` 四个 typed rule 槽 | `unit+0xCD`、`unit_parameter`、表 `0x0853F348..0x0853F888` | `notes/battle-ai-config-and-projection-runtime-20260727.md:26-41` | 已闭合 |
| 地图拓扑距离 | 读 `0x02026805` battle ID，以 `0x0853F888 + battle_id × 8 × 16` 选八条记录：kind 0 曼哈顿段结束；1/2 纵横屏障 breakpoint；3 map 5 固定补偿；4 map 23 15×17 signed distance lookup；5 map 24 13×17 双入口 lookup；6 map 17/37 固定补偿 | `0x02026805`、`0x0853F888` | `notes/battle-ai-action-component-runtime-20260727.md:137-148` | 已闭合为 battle-ID 驱动的拓扑距离；「不是通用寻路」 |
| AI 状态策略矩阵 | event low6 ∈ `0x3F/0x0F/0x0E` 或带 raw bit `0x80` 时，target 任有 `0x3F/0x3E/0x3D/0x0F/0x11` 即跳过该 event 分值；带 bit `0x40` 时 target 任有 `0x1F/0x21/0x23` 跳过；`0x1E/0x20/0x22/0x24` 各查同族，`0x26` 依次受 `0x1E/0x20/0x22/0x1B` 约束 | scorer `0x08084274..0x08085154` 内 15 个状态查询点 | `notes/battle-system-restoration-evidence-20260723.md:822-830` | 已闭合（三层状态感知评分）；各 code 可见名未闭合 |

---

## 2. 音频引擎域（m4a / DirectSound / CGB PSG）

### 2.1 ROM 侧：音高与 mixer phase

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| MIDI key→freq 查表 | `p0 = freq[scale[key]&15] >> (scale[key]>>4)`；`p1` 同式用 `key+1` | 表 `0x084645C4`（180B scale）、`0x08464678`（12×u32） | `notes/directsound-pitch-step-20260713.md:5-14`；`tools/m4a_pitch_step.py:8-32` | 已闭合 |
| key 插值 + step | `interp = p0 + high32((p1-p0)&0xffffffff, fine<<24)`；`step = high32(wave.frequency_raw, interp)`；`key>178 → key=178, fine=255` | `wave.frequency_raw`（Q10 Hz，`0x46606C = 0x00DAC000`）；`MidiKeyToFreq 0x0809A998` | 同上 `:15-24` | 已闭合 |
| track note-on 音高组合 | `(tune + bend*bendr)<<2 + keyShift<<8`，高位=signed key delta、低 8 位=fine；负 key 在 `0x0809A8A4` 钳 0 | KEYSH(signed s8)、BEND/TUNE（中心 `0x40`）、BENDR（默认 2）；`TrkVolPitSet 0x0809B3E0` | `notes/directsound-pitch-step-20260713.md:46-50` | 已闭合 |
| MODT=0 pitch LFO | `lfo_phase=(phase+LFOS)&0xFF`；`0x40<=phase<=0xBF → triangle=0x80-phase` 否则 signed8；`mod=(MOD*triangle)>>6` | LFOS、LFODL、MOD depth、MODT | `notes/directsound-pitch-step-20260713.md:55-59` | 已闭合 |
| mixer phase 推进（23 bit） | `total=phase+divFreq*step`；`phase=total&0x7FFFFF`，`advance=total>>23` | `SoundInfo.divFreq=532`、channel `+0x20` step、mode `0x0095FA00` | `notes/directsound-pitch-step-20260713.md:29-38` | 已闭合 |

### 2.2 ROM 侧：音量/声像两级增益链

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| track 级 R/L 增益 | `base=(VOL*volX)>>5`；MODT=1 时 `base=(base*(modM+128))>>7`；`pan=clamp(2*signedPAN+panX+(modM if MODT==2),-128,127)`；`trackR=((base*(pan+128))>>8)&0xff`；`trackL=((base*(127-pan))>>8)&0xff` | VOL cmd `0xBE`→track `+0x12`；PAN cmd `0xBF`→signed `+0x14`；默认 volX=64、panX=0 | `notes/directsound-volume-pan-20260713.md:19-28` | 已闭合；第一级是 STRB，极端值低 8 位回绕，**不得饱和** |
| channel pre-envelope 增益 | `chanR=min(255, velocity*(tonePan+128)*trackR>>14)`；`chanL=min(255, velocity*(127-tonePan)*trackL>>14)` | note velocity、drum `pan_sweep` bit7 时 `tonePan=(raw-0xC0)*2`；`ChnVolSetAsm 0x0809A6D8`→channel `+2/+3` | `notes/directsound-volume-pan-20260713.md:26-32` | 已闭合（16169/16169） |

### 2.3 ROM 侧：ADSR / release / pseudo echo

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| 包络相位机 | attack `ev+=A, ev>=255→钳255进 decay`；decay `ev=ev*D>>8, ev<=S→钳S进 sustain`；release `ev=ev*R>>8, ev<=echoVolume→echo 或零阈立即停`；echo 进入阈值的当前 tick 有输出，之后 echoLength 倒计时，`pre<=1` 停止 | tone `+8..+B` ADSR 四元组 → channel `+4..+7`；状态位 `0x80 new / 0x40 release / 0x10 loop / 0x04 echo` | `notes/directsound-envelope-20260713.md:9-16`；`tools/m4a_envelope.py:74-134` | 已闭合；每次 SoundMain mixer invocation 推进一次，**非** MP2K wait tick |
| masterEnv 与最终增益 | `masterEnv=(masterVolume+1)*ev>>4`；`mixR/L=preEnvelopeR/L*masterEnv>>8` | pre-envelope `channel+2/+3`、masterVolume | `notes/directsound-envelope-20260713.md:17-18` | 已闭合 |

### 2.4 ROM 侧：SoundMain 取样 / loop / 混音 / reverb

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| forward-linear 插值与推进 | `increment=u32(divFreq*step)`；`sample=s0+((phase*(s1-s0))>>23)`；`phase,advance=(phase+increment)&0x7FFFFF,(phase+increment)>>23` | wave header（type/status、freq、loop start、sample count）；hot loop `0x0809A0E8..0x0809A180` | `notes/directsound-mixer-runtime-chain-20260713.md:28-38` | 已闭合；末样本处引擎仍预读下一 ROM 字节作插值 guard |
| 左右路 modulo-256 混合 | `rightContribution=(sample*gainRight)>>8`；`right=s8((right+contrib)&0xFF)`，left 同 | mixer gain `channel+0x0A/+0x0B` | `notes/directsound-mixer-runtime-chain-20260713.md:5-9` | 已闭合——ROM **不做饱和**，`clamp(-128,127)` 渲染器可观测地错 |
| reverb seed | `sum = cur.right/left + prev.right/left`；`x=(sum*reverb)>>9`；`x&0x80` 时先 `x+1` 再把同一低字节写入两个 plane；reverb=0 清当前 plane | reverb 字段（SongHeader byte 3；80 首中 58 用 0、22 用 128）；6×264=0x630 环形 | `notes/directsound-mixer-runtime-chain-20260713.md:45-49` | 已闭合（约 t−6 / t−5，非单缓冲延迟） |

### 2.5 ROM 侧：tempo accumulator / buffer 节拍

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| tempo 累加与 tick 触发 | `tempoC += tempoI`；`while tempoC>=150: 执行一个完整 track tick; tempoC-=150`；`tempoD=raw*2`，`tempoI=(tempoD*tempoU)>>8`（默认 `tempoU=0x100`） | TEMPO cmd `0x0809A2E8`、`SampleFreqSet 0x0809AF34` | `notes/m4a-soundmain-scheduler-20260713.md:18-30` | 已闭合（raw 75 → 每次 SoundMain 一 tick；`tempoI=300` → 两 tick） |
| 采样率/divFreq | 264 samples/VBlank，整数 WAV 率 15768 Hz，`divFreq=532`；每声道面 `0x630=1584` 字节 = 6×264 chunk，顺序 0..5,0 | DMA1/DMA2 `0x040000A0/0x040000A4`；FIFO `0x04000080/0x04000084` | `notes/m4a-soundmain-scheduler-20260713.md:47-49` | 已闭合 |

### 2.6 ROM 侧：CGB channel-4（PSG/noise）

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| key→NR43 查表 | `key<=20 → index 0`，否则 `index=min(key-21,59)`；60 字节表 @ file `0x46475C` | `MidiKeyToCgbFreq 0x0809B494` → NR43 | `notes/psg-noise-runtime-chain-20260713.md:14-16` | 已闭合 |
| NR43 时钟解码 | `clock = 262144/(divisor*2^shift)`，`shift=(NR43>>4)&0xF`，`divisor_code=NR43&7`，code 0 视为 0.5 | NR43 | `notes/psg-noise-runtime-chain-20260713.md:18-19` | 已闭合（`0x14` = 32768 Hz） |
| 15/7-bit LFSR | `feedback=(lfsr&1)^((lfsr>>1)&1)`；`r=(lfsr>>1)|(feedback<<14)`；width 置位时同时写 bit6；`&0x7FFF` | NR43 width 位、channel-4 status | `notes/psg-noise-runtime-chain-20260713.md:20-21` | 已闭合 |
| `CgbModVol` 音量目标与 NR51 | `right>=left 且 right//2>=left → pan=0x0F`；`left>right 且 left//2>=right → 0xF0`；否则 `0xFF`；`goal=(right+left)//16`；`not(mode&1) 且 separated → goal=min(15,goal)`；`sustainGoal=(goal*sustain+15)>>4`；`pan & 0x88` | NR51、NR42（`(vol&0xF)<<4|0x08`）；`CgbModVol 0x0809B58C` | `notes/psg-noise-runtime-chain-20260713.md:22-26` | 已闭合 |
| CGB 通道分配与寄存器写 | envelope + NR41/NR42/NR43/NR44/NR51 写序列 | `CgbSound 0x0809B5F4..0x0809BA3C` | 同上 `:23-26` | 已闭合；本 ROM 唯一 PSG tone 为 sound ID 144 的 11 note |

### 2.7 宿主/离线渲染侧（**非 ROM 公式**）

| 项 | 内容 | 证据 |
|---|---|---|
| ROM 侧声学初始化写入 | `NR50 = 0x77`；`SOUNDCNT_H = 0xA90E`；写点 `0x0809AD2A`、`0x0809AE7A` | `notes/m4a-full-song-render-20260713.md:29-30`（写值属 ROM 代码；寄存器语义据 GBATEK + mGBA `_sample`） |
| 硬件混音尺度（宿主模型） | DirectSound signed byte 内部左移 2；PSG 经 SOUNDCNT_H volume shift 相加；最终 10-bit bias clamp | `notes/m4a-full-song-render-20260713.md:30-33` |
| PSG→DirectSound byte 平面 | channel-4 的 0..15 volume 映射为 `noise_bit * volume * 4`，与 DirectSound 相加后钳到 −128..127；相位累加器把 32768 Hz LFSR 迁到 15768 Hz PCM 轴 | `notes/m4a-full-song-render-20260713.md:34-37`（部分闭合，宿主对齐模型） |
| RIFF 8-bit 输出转换 | 每个 signed byte `XOR 0x80`，再左右声道交织 | `notes/directsound-mixer-runtime-chain-20260713.md:48-49` |

**本域未闭合边界：** 结构化 MIDI 仍是试听产物，**不能宣称整曲 bit-accurate 输出**；PSG/noise 尚不宣称最终可听渲染；80 个 cue 的玩家可见语义命名未完成（`notes/m4a-full-song-render-20260713.md:63-65`）。

---

## 3. 图形 / 动画 / 渲染域

### 3.1 战斗特效 renderer（22 sequence）

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| child 原点 = 父偏移 + 对战侧镜像 | `x_off = s16(-x)`，并切 `0x8000` H-flip | motion 表 `render_attributes`；task `+0x04/+0x06` | `notes/battle-effect-sprite-animations-export-20260729.md:123-124` | 公式已闭合；父坐标为运行时输入 |
| 角色锚点跟随 | `origin(t)=actor_anchor(t)+delta`；`actor.x = Q8.8 截断` 或 `240-截断`（依 `orientation==side_id`），`y=Q8.8 截断` | task `+0x08/+0x0A` actor-follow delta | 同上 `:125-128` | 公式已闭合；delta/anchor 为运行时输入 |
| seq1 RNG 匀减速抛射 | `speed=max(0,speed-24)`；负 Q8.8 先 `+255` 再算术 `>>8` | task `+0x2C/+0x30` s32 Q8.8、`+0x34` angle、`+0x38` speed | 同上 `:119-121` | 公式已闭合；两次 RNG 结果未实例化 |
| attr 前偏移表选择 | `flags&0x1000` 门控；`sel=(flags&0x6000)>>13`；`x-=s32table[sel].x>>8`、`y-=…>>8` | `task.render_flags` bit 12/13/14；`0x03000054` 四组 `<s32 x,s32 y>` | 同上 `:143-150` | 公式已闭合；`0x03000054` 逐帧值未实例化 |
| 两阶段 Q8.8 scale/extent | 两侧 scale pair 均 `0x01000100` 走原尺寸快路；否则 `trunc0` 连乘 task×component，**以变换前 extent 封顶** | task scale pair、`component+0x0C/+0x0E`、`+0x08/+0x0A` | 同上 `:151-154` | 已闭合 |
| 四项可见性裁剪 gate | `x+scaled_w>0 ∧ y+scaled_h>0 ∧ x<240-trunc0((pre_w-scaled_w)/2) ∧ y<160-trunc0((pre_h-scaled_h)/2)` | 变换后 x/y、scaled extent | 同上 `:155-158` | 已闭合 |
| attr0.y / attr1.x 位宽 wrap | `attr0.y=u8(final_y)`、`attr1.x=u9(final_x)` | OAM attr0 bit0-7、attr1 bit0-8 | 同上 `:184-185` | 已闭合（仅最终坐标字段） |
| shape/size 12 编码 | 合法矩形 `8×8,8×16,8×32,16×8,16×16,16×32,32×8,32×16,32×32,32×64,64×32,64×64` | attr0 bits 8-9、attr1 bits 14-15 combined mask | 同上 `:186-189` | 已闭合；437 component 实际用 8 种 |
| 非 affine H/V 位 | `u2(component.tile_flags XOR ((task.render_flags&0x18000)>>15))` → attr1 bits 12-13 | `component+0x02`、`render_flags` bit15/16 | 同上 `:190-193` | 已闭合，受栈 mode bit0、`task+0x13`、scale pair、bit19 guard 约束 |
| 普通 attr2 合成 | `u16(tile_base+tile_index)`；`u4(palette_bank)<<12`；`(render_flags&0xC0)<<4` = priority bits10-11 | `task.tile_base`、`task.palette_bank`、`render_flags&0x00400000==0` | 同上 `:194-196` | 已闭合（限普通 battle-effect 路径） |
| affine matrix PA/PB/PC/PD | `phase=u8(comp.angle_offset+task.angle_offset)`；`S=sin_q8_8(phase)`、`C=sin_q8_8(phase+64)`；`Q(v,d)=trunc0((s32(v)<<16)/d)`；`PA=hs·Q(C,dX)`、`PB=vs·Q(S,dX)`、`PC=-hs·Q(S,dY)`、`PD=vs·Q(C,dY)`；`dX=task.sx×comp.sx` | `component+0x02/+0x03`、task scale/angle/side flip、`0x03000282+ord×32` 的 `+0/+8/+16/+24`；attr1 bits9-13=`u5(ord)`；bit19 启用 double-size | 同上 `:206-232` | 已闭合 |
| task angle 位置旋转 | `x=-trunc0(w/2)+trunc0((cx·cos-cy·sin)/256)`；`y=-trunc0(h/2)+trunc0((cx·sin+cy·cos)/256)`（先算中心并应用 task Q8.8 scale） | `task+0x13`；**不使用** `component+0x03` | 同上 `:239-250` | 已闭合 |
| affine 像素逆采样 | `rx=screen_x-TW/2`、`ry=screen_y-TH/2`；`source_x=(PA·rx+PB·ry+W·128)>>8`；`source_y=(PC·rx+PD·ry+H·128)>>8`；`TW=W<<double_size` | affine matrix；越界与 palette index 0 透明 | 同上 `:252-276`（mGBA source-model） | mGBA source-model 公式已闭合；**非**真机 pixel golden |
| OAM x/y 环绕与包围盒 | x 低 9 位先符号扩展，y 按 256 环绕；x 为变换包围盒左边缘 | attr1 x、attr0 y | 同上 `:321-322` | 源码审计闭合 |
| bit22 动态 OBJ VRAM 拷贝 | src=`task.tile_source_ptr + s16(comp.tile_index)×32`；dst=`0x06010000 + u16(tile_base+running_offset)×32`；size=`u16(trunc0(s16(w)×s16(h)/64)×32)`；`running_offset += trunc0(w×h/64)`；attr2=`u16(tile_base+off)|palette<<12|priority<<10`；门控 `bit23==0 ∧ (flags&0x01000008)!=0x01000008` | `render_flags` bit22/23、`+0x01000008`、`task.tile_base`、`tile_source_ptr` | 同上 `:325-337` | 通用公式已闭合；**对当前 22 条 sequence 不可达** |
| 拷贝队列消费 | 16 个 16-byte 槽 @`0x03005BBC`；status1 同步 `CpuSet` 搬 `u16(size)>>1` 个 halfword；满队列返回 0 但 renderer 忽略仍写 OAM | `0x080612BC..0x080614E4`；首 flush @`0x080613FC`，另分支 `0x080614C2` | 同上 `:339-354` | 机制已闭合；queue-full 运行时结果未签发 |

### 3.2 Sprite definition / animation

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| animation 内嵌记录 | `animation_table[0].u32 = definition_pointer + 4`；记录 `<s16 frame_index, s16 duration_ticks>`；选帧 `table + frame_cursor*4`；每 tick `timer++` 与 `+2` 比较；`frame_index=-1` 时按 `flags&0x30` 选停止/循环/callback | task timer、task flags | `notes/sprite-definition-animations-export-20260729.md:8-15` | 43/43 单帧已闭合；业务语义未证明 |
| component 步进与终止 | `component+0x00 == -1` 终止；每次前进 `0x14` | `component+0x00` | `notes/sprite-definition-runtime-chain-20260729.md:60-61` | 已闭合 |
| tile 覆盖计数 | `source_tile = tile_base_offset[id] + component.tile_offset`；`tile_count=(width/8)×(height/8)` | `component+0x00/+0x08/+0x0A`、ROM `0x53F298` | 同上 `:91-93` | 已闭合（43 tile-base + 45 component 覆盖 tile 0..48） |
| 运行时 OBJ 地址链 | `attr2.tile = u16[0x0202CA24] + tile_base_offset[id]`；`attr2.palette = u8[0x0202CA26]<<12`；OBJ tile bytes `=0x06010000 + attr2.tile×32`；palette bytes `=0x05000200 + bank×32` | `0x0202CA24`/`0x0202CA26`；writer `0x08063108` | 同上 `:106-126` | 地址公式已闭合；两个 RAM 槽为运行时输入 |

### 3.3 战斗视觉时间线（79 项）

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| state_id 派生（三处同源） | `state_id = input_id - 1`；descriptor `0x085A320C + state_id×0x44`；message `0x085A2B08 + state_id×4`；binding `0x085A2EF4 + state_id×10` | 状态字节 0 | `notes/battle-visual-catalog-export-20260729.md:6-12` | 已闭合 |
| 标准 consumer 时长与 OBJ 坐标 | 前置 8 帧 → binding 槽 6 帧节拍 → 保持 60 帧；`x = slot×24 - count×12 + 132`、`y=16`、palette bank 13；总长 `84 + 6×count` | binding 槽序号、`0xFF` 槽占时序 | `notes/battle-visual-runtime-timelines-export-20260729.md:24-36` | 已闭合（标准 consumer）；逐 tick scroll/blend/palette transform 未完成 |
| mode2/3 横向震荡 | tick32 端点 `origin_x=72`；奇数 tick `origin+q`、偶数 tick `origin-q-2` | easing 终点 | 同上 `:41-43` | 已闭合（限 tick 1..106） |
| mode3 D scroll 交替 | `+1,-2,+3,-4…`，tick106 累计 `−16 px` | D 层 scroll | 同上 `:54-55` | 已闭合 |
| C-over-B alpha 斜坡 | `k=trunc((tick-16)/4)`、`EVA=k`、`EVB=16-k`；tick80 达 `16/0`，tick81 清 `BLDCNT` | flag `0x0100`、`BLDALPHA/BLDCNT` | 同上 `:61-64` | 已闭合 |

### 3.4 剧情场景图层与时间线

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| story config 直接零基索引 | `config_id = u8(descriptor+0x0C)`；索引 `0x085A320C + config_id×0x44`；**不使用** `input_id-1` | `descriptor+0x0C` | `notes/story-scene-layer-bindings-20260729.md:5-14` | 已闭合（24 config 全落 0..78） |
| BG3CNT 两步写入 | helper `0x08065404` 先写 `0x0300`，剧情路径 `0x08087CEA` 覆盖 `0x030C`，`0x08087EAA` 启用；gfx `0x0600C000 + 0x140×32 = 0x0600E800`，tilemap `0x06001800` | BG3CNT charblock3/screenblock3/prio0 | `notes/story-visual-layer-export-20260729.md:36-49` | 已闭合（不可用中间值推翻） |
| C / D 层 tile base | `C.base = state[0x16] >> 1`；`D.base = u16(state[0x12] + state[0x16])` | `state[0x12]`、`state[0x16]` | `notes/story-scene-layer-bindings-20260729.md:37-40` | 公式已闭合；state 字为运行时 |
| flag `0x0200` 交换 priority | 有 flag：C/BG0=1、D/BG1=2；否则 C=2、D=1 | descriptor flag `0x0200` | 同上 `:26-27` | 已闭合（仅 config 61 置位） |
| D 层 enable 门 | flag `0x0400` 禁止装载 D；初始 enable 门 `flags&0x0900` | descriptor flag `0x0400/0x0900` | 同上 `:46-53` | 已闭合 |
| 剧情 controller 精确时序 | prelude 1..21 → linked 1..16（wall 22..37）→ linked 17..106（38..127）→ 灰度 128..143 → BG3 overlay 144..383 | linked tick、wall frame | `notes/story-scene-timelines-export-20260729.md:21-30` | 已闭合（离线确定性，非像素等价） |
| palette phase×2 亮度 | `phase` 截断 0..7，左移后以 `phase×2` 加到 B/G/R；tick106 每通道增量 14 | linked palette | 同上 `:38-40`（`0x08098AA0..0x08098AB8`） | 已闭合 |
| 公共 B 层运动 | B scroll 每 tick `+2 px` fixed；B palette 2..9 奇数 tick 轮换 | B scroll / palette | 同上 `:46-47` | 已闭合 |
| `d_bg_flicker` | task counter `mod 4`：余 2 启用 BG1、余 0 关闭 | counter mod4 | 同上 `:43` | 已闭合（仅 config16） |
| text-BG tilemap H/V 翻转 | tilemap entry bit10 = 水平、bit11 = 垂直 | BG tilemap entry | `notes/story-visual-layer-export-20260729.md:12` | 已闭合 |

### 3.5 场景 visual pack / cutscene OBJ 时序

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| duration=0 的 16-bit 回绕循环 | 每更新先 `timer++`；duration 0 时首相等发生在 timer 经 `65536` 次回绕到 0；`0xA1&0x30==0x20` → 清 cursor/timer 并循环 | task timer、flags `0xA0→0xA1` | `notes/scene-visual-pack-export-20260729.md:76-89` | 已闭合；**非「无限时长」**，manifest 保留精确回绕周期 |
| 场景 BG 画布常量 | `BG0CNT=0x4086` → 8bpp/charblock1/screenblock0/512×256；packed rectangle 固定 20 行高、18–23 tile 宽 | descriptor `+0x18/+0x19` | 同上 `:57-59` | 已闭合；`screen_space_composition_complete=false` |
| cutscene frame 数推导 | `frames = (animation_table_ptr - definition_table_ptr) / 12`（4B def ptr + 8B animation record） | 两张 ROM 表指针 | `notes/cutscene-obj-export-20260729.md:50-59` | 已闭合 |
| cutscene 单帧终止 | flags `0x08→0x09`；duration 1 首次更新到期、duration 0 第 `65536` 次回绕到期；`0x09&0x30==0` → 清活动位停止 | task flags、timer、frame_cursor | 同上 `:62-73` | 时序已闭合；`final_runtime_sequence=false` |

### 3.6 BG 资源选择与画布

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| battle header 背景选择 | `entry_id = u8[0x0853D910 + battle_id×0x20 + 0x1C]` | header `+0x1C` | `notes/bg-scene-selection-export-20260729.md:20-24` | 已闭合（47/47，ID 1–7） |
| wrapper 分段索引与安全域 | input 0–46 走 header 公式；50–54 走 `entry_id = input_id - 41`（→ID 9–13）；47–49 越表读出 96/36/214；完整安全域 `0..46 ∪ 50..54` | wrapper input | 同上 `:73-77` | 已闭合（含不安全边界） |
| BG loader 目标地址与填充 | gfx→`0x06000000 + charblock×0x4000`；palette→`0x05000000`；tilemap→`0x06000000 + screenblock×0x0800`；mode≠0 置 `BGxCNT` bit7；自 `+0x280` 续填 32×32，4bpp 填 `0x0000`、8bpp 填 `0x001E` | charblock、screenblock、color_mode_8bpp | `notes/bg-resource-canvases-export-20260729.md:32-50` | 已闭合；原始 tilemap 仅 256×80，填充行非 ROM 数据 |
| 世界地图背景/标签 | 记录选择 `u8[0x020311D4+0x14]`；gfx→`0x06004000`、160 色→`0x05000000`、map 经 `0x08063604` 展开到 `0x06000000`；`BG0CNT=0x0086`；30×20 map → 240×160；标签 `0x085A8038 + index×0x10` → `0x08066758` | `state+0x14`、标签 index | `notes/world-map-background-export-20260729.md:5-15` | 表与绑定已闭合；label palette/屏幕坐标未完成 |

### 3.7 字形展开与演出字形链

| 公式 | 表达式 | 参与属性 | 证据 | 状态 |
|---|---|---|---|---|
| 2bpp 位拆分 | `bits 1:0, 3:2, 5:4, 7:6`（低字节优先） | packed-2bpp 源记录 | `notes/dialogue-font-atlas-export-20260729.md:38` | 已闭合 |
| 4bpp 输出索引 | `output_index = source_2bpp + (((arg1 & 1) + 2) << 2)`；`0x080894DE` SJIS 传 `arg1=1` → 12–15，`0x080894A8` 单字节传 `arg1=0` → 8–11 | cache 调用 `arg1` | 同上 `:39-42` | 已闭合 |
| 字形几何 = 8×16 垂直 | half 0 写当前行、half 1 写下一行，水平前进一格 | tilemap 两行 entry | 同上 `:44-45` | 已闭合；源记录本身不定义左右/上下布局 |
| 演出 glyph 索引与解压槽 | message `u8(id)×4`；binding `message_id×10`（byte0=count）；glyph `id×4` 取 LZ77；`0xFF` 跳过；解压到 OBJ VRAM 目的槽固定 `+0x200` 递增 | `0x085A2B08`/`0x085A2EF4`/`0x085A2C44`、display_slot | `notes/battle-presentation-glyphs-export-20260729.md:19-29` | 已闭合（172 glyph / 每 chunk 512B = 16 tile 4bpp） |
| 演出 palette bank 链 | `state[0x0F]=13`；`0x05000200 + 13×32 = 0x050003A0` 复制 16 色；`0x08098F82` 以同值作 sprite palette bank；`0x08063108` 写 `task+0x12 << 12` → attr2 bits12–15 | `state[0x0F]`、task `+0x12` | 同上 `:37-46` | 已闭合 |

### 3.8 Butano S49 未证明的位移/相位公式（**不可当 ROM 公式**）

| 项 | 内容 | 证据 | 状态 |
|---|---|---|---|
| 多格到达锚点补间 | 两格右移到达 f22–28 的 `-8,-6,-4,-3,-2,-1,0 px` 锚点序列 | `notes/butano-s49-full-fidelity-20261013.md:62` | 原文「通用公式未证明」 |
| 单格移动帧预算 | 起步资源 12 帧、到达 14 帧；内置 `20/24 px` 位移 | 同上 | 单格经验值已录；通用公式未证明 |
| 待机/移动相位 | 菜单恢复后 idle 从 frame6 重新起算 8 帧 | 同上 | 「当前全局 scene_frame 尚未校准」 |
| 括角 4 帧循环周期 | 亮 d3×4、d2×5、d1×7、d0×15、d1×8、d2×5（无输入 256 帧唯一匹配 44 帧循环） | 同上 `:80` | 周期形状已实证；不证明输入初相位一致 |
| easing 切片锚点 | 切片 `0x080986E8..0x080986F8` | `notes/story-scene-timelines-export-20260729.md:56` | **仅定位切片，未签发插值表达式** |

---

## 4. 关卡 / 地图 / 剧情 / 经验域

### 4.1 编队 / 位置寻址

| 公式 | 表达式 | 参与字段 | 证据 | 状态 |
|---|---|---|---|---|
| 编队记录寻址（两级索引） | `record = 0x5461C4 + battle_id*0x1AAC + variant*0x08E4 + 4 + record_id*0xB8`；`3*0x08E4 == 0x1AAC` 定死 48×3×12=1728 条 | `battle_control@0x02026804 +1/+2`；record `+0` 过滤首字节、`+2`=x、`+3`=y、`+4`=parameter | `notes/positions-rom-source-20260710.md:11-29`；`notes/butano-battle-domain-rewrite-20260723.md:310-311` | 寻址已闭合；两索引维度的枚举语义尚未动态确认 |
| 编队记录 → WRAM 单位坐标 | `unit = 0x020240C0 + slot*0x1D4`；`record[+2]→unit+0xC7/+0xC4`、`record[+3]→+0xC8/+0xC5`、`record[+4]→+0xC9/+0xC6` | unit `+0xC4/+0xC5/+0xC7/+0xC8` | `notes/positions-rom-source-20260710.md:60-63` | 已闭合 |
| 编队记录内嵌运行时配置 | stride `0xB8`：`+0x0F` level、`+0x10` 15×{action,state,unlock_level,reserved}、`+0x4C` 24×{passive,state,unlock_level,reserved}、`+0xAC` 9×ninja_tool_id、`+0x0E` unit_parameter | 构造器 `0x0806ACAC..0x0806ADC4`；选择链 `0x0806E1C0..0x0806E332` | `notes/battle-formation-runtime-config-20260726.md:11-30` | 已闭合；`unit_parameter` 保持中性命名 |
| 编队携带经验 | `record+0x0C → unit+0xCE`（`0x0806AD92`） | formation `+0x0C`、unit `+0xCE` | `notes/battle-result-progression-runtime-20260725.md:38-59` | 已闭合 |

### 4.2 角色定义与解锁

| 公式 | 表达式 | 参与字段 | 证据 | 状态 |
|---|---|---|---|---|
| 成长记录寻址 | `0x545068 + character_id*0x10`（63×`0x10`）；ID57/58 改用 physical record 8/15 | character_id | `notes/character-growth-runtime-chain-20260711.md:9-13` | 已闭合（runtime_verified） |
| 角色定义记录寻址与模板链 | `0x54241C + character_id*0xB4`（63 条）；模板池 `0x02022E34 + slot*0xBC`；复制前 `0xBC` 字节到 `0x020240C0 + battle_slot*0x1D4` | def `+0` active_flag、`+1..+6/+8/+A` base、`+0x0C..+0x47` 15 主槽→模板 `+0x14`、`+0x48..+0xA7` 24 次槽→`+0x50`、`+0xA8..+0xB0` 9 候选经 `0x0808FA34` 过滤→`+0xB1` | `notes/character-definition-source-20260711.md:18-24` | 槽布局与过滤已闭合 |
| 技能解锁条件 | 槽 `state==0xFF` 且 `unlock_level≠0` 且 `≤角色等级` 时 runtime state 置零 | 主/副槽 `state`、`unlock_level` | 同上 `:113-117` | 已闭合（代码直证） |
| 旧「角色数据块」WRAM 基址 | `0x02022EF0 = 0x02022E34 + 1*0xBC`（即 template slot 1），非独立基址 | — | `notes/character-stats-addresses.md:4-21` | 旧表已撤销 |

### 4.3 地图

| 公式 | 表达式 | 参与字段 | 证据 | 状态 |
|---|---|---|---|---|
| 地图头寻址 | `0x0853D910 + map_id*0x20`（47 条×32B） | map row `+0` width、`+2` height | `notes/maps-runtime-fields-20260711.md:5-16` | 已闭合（runtime_verified） |
| 逻辑格派生 | `width>>2 → 0x0201BE2A`，`height>>1 → 0x0201BE2B`；粗格数 `(width>>2)*(height>>1)`；layout 解压长 = 粗格数×4，collision = 粗格数×2 | width/height；消费者 `0x08068FB4`/`0x08068FF0`/`0x08069264` | 同上 `:5-13` | 已闭合（47/47 行长度成立） |
| 地图资源六指针 | `+4` tile gfx→`0x06000000+idx*0x4000`；`+8` palette→`0x05000000`；`+0C` primary layout→`0x0201BE2C`；`+10` alternate→`0x0201CE2C`；`+14` metatile attrs→`0x0201DE2C`；`+18` collision→`0x02021E2C` | map row `+4/+8/+0C/+10/+14/+18/+1C` | 同上 `:70-88` | 已闭合（逐字节运行时验证） |
| 元块展开 | 每粗格 u32 的低/高 u16 选左/右 2×2 metatile；每 metatile = 4 个标准 BG u16（TL/TR/BL/BR） | primary layout u32；metatile 定义 `0x14` 指针 8B/个 | `docs/structure-field-semantics.md:288-301` | 静态闭合；动态 occupancy overlay 超出静态导出 |
| 战场对象占位写入 | `0x08080FC8` 写 `(slot<<6)` 到 `0x02021E2C`；释放 `0x08081084` 以 `0xF83F` 清 `0x07C0` 位域 | 对象 slot、collision 元数据 | `notes/battlefield-object-runtime-20260726.md:55-56` | 已闭合（不是可见 OBJ sprite） |

### 4.4 剧情 / 章节

| 公式 | 表达式 | 参与字段 | 证据 | 状态 |
|---|---|---|---|---|
| 主线章节脚本 | `script = [0x60C74 + scenario_id*4]`（56 项 u32，entry 0 为 null）；`0x0808F544` 在章节状态 `+0x18==0` 时取用 | 章节状态 `+0x18` | `docs/structure-field-semantics.md:442-450` | 已闭合（scenario 39 运行时命中） |
| 备用章节脚本 | 同格式表 `0x60D54`，在 state `+0x18 != 0` 时选择 | 同上 | 同上 `:453-456` | 表身份 code_verified；live sample pending |
| 章节奖励记录映射 | `reward_record = file 0x348DAC[scenario_id]`（48×u8）；奖励表 `0x59EAE0` 112×`0x18` | mission_exp、round_bonus_exp、round_limit | `notes/battle-result-progression-runtime-20260725.md:63-74` | 前三 u16 已闭合；`+0x06..+0x17` 九个 u16 不命名 |
| 剧情视觉描述符 | 24×16B，`+0/+4/+8` 三个 LZ 指针、`+0x0C` 视觉/配置 ID | descriptor `+0x0C` | `docs/structure-field-semantics.md:45-51` | 已闭合；旧 `0x542384` 只是 descriptor 14 的 `+8` |
| 消息命令索引 | `code 0x80..0xE3 → 指针表 0x599634[code-0x80]`（100 项）；`0x64..0x67` 取调用方 state 的 4 个指针 | `message_ptr` | 同上 `:12-25` | 已闭合（旧「audio/sappy」解释已撤销） |

### 4.5 动作 / 忍具 / 立绘 / 效果表与存档

| 公式 | 表达式 | 参与字段 | 证据 | 状态 |
|---|---|---|---|---|
| 动作数值模板 | `src = 0x545458 + action_id*0x10`（87 项） | `+0` cost kind、`+1` 动画族、`+2` effect/flags、`+3` target policy、`+4` potency、`+5` hit count、`+6` 成功率、`+7/+8` 打包射程/形状、`+9` duration、`+A..+B` 资源成本 | `docs/structure-field-semantics.md:29-41` | 已闭合；`+0x0D` 未命名；type 7 不做成长调整 |
| 模板内等级成长目标 | 模板字节 `+0x0C` 选目标 `(+4..+9)`（type 1..6）；`u16 +0x0E` 为增量 ×(`level-1`) | 模板 `+0x0C`、`+0x0E` | 同上 `:39-41` | 已闭合（type 7 例外） |
| 忍具模板 | `0x545BE4 + ninja_tool_id*16`（94 项），拷贝 `+0..+9` | `+4` 攻击、`+5` hit count、`+6` 成功率、`+7` 距离/直线形状、`+8` 射程 | `docs/structure-field-semantics.md:417-431` | 已闭合；`+2/+3/+9` 未命名 |
| 立绘/变体矩阵 | `pair = 0x5A4DEC + record_id*40 + variant*8`（63×5）；variant 5 用 `0x5A4DE4` 特例对 | `graphics_ptr`、`palette_ptr` | 同上 `:345-349` | 已闭合 |
| 地图精灵 tile 基址 | `tile_base = u16[0x0202CA24] + u16[0x53F298 + id*2]`；OBJ tiles = `0x06010000 + tile_base*32`；`attr2.palette = u8[0x0202CA26]<<12`；组件 `+0x08/+0x0A` = 宽/高（8/16/32/64） | 43 项 tile-base 表、组件 `+0x00`(=-1 结束) | 同上 `:312-341` | 已闭合 |
| 效果序列选择 | 选择器 `0x53E596` 按整 u8 索引 256 项；低 7 位索引 94 个忍具模板；描述符 `0x53EF30` 覆盖 ID 0..21 | 事件 `+0x0C` 高位、runtime state `+0x770` | 同上 `:532-546` | 已闭合 |
| 战斗表现字形三段区 | `0x5A2B08..0x5A2C44` 79 消息指针；`0x5A2C44..0x5A2EF4` 172 LZ77 字形指针；`0x5A2EF4..0x5A320A` 79×10 绑定 | — | `notes/similar-tables.md:81-92` | 已闭合 |
| 存档记录寻址 | `next_SRAM_record = prev + payload_length + 0x14`；每记录 = 19 字节 identity header + payload + `~sum(payload)`；表 `0x53D848` u32[2]×10（7 唯一） | `ewram_addr`、`payload_length`；handler `0x08068684` | `docs/structure-field-semantics.md:401-414` | 已闭合（slot-1 存/冷恢复 runtime verified） |

---

## 5. 参与计算的高频属性字段索引

按访问频次合并，供下游生成器直接取用。

### 5.1 战斗单位 `unit`（基址 `0x020240C0 + slot*0x1D4`）

| 偏移 | 语义 | 参与哪些公式 |
|---|---|---|
| `+0x02` | 攻击 attack | 成长、伤害 scaled、会心/无视防御四候选 |
| `+0x03` | 防御 defense | `100 - 5×isqrt(defense)` |
| `+0x04` | 敏捷 agility | 成功率修正、格评分间接 |
| `+0x05` | 移动 movement | 威胁半径、状态 `0x24/0x25` |
| `+0x06` | 忍具容量 | 忍具装备数量 |
| `+0x07` | 当前查克拉 | 查克拉补充、AI 投影 |
| `+0x08` | 查克拉上限 | 查克拉补充上限、AI 投影 |
| `+0x0A` | 结印成本 | 查克拉补充的 HP 成本 |
| `+0x0C` | 当前 HP | 休息、复合 `0x26`、AI 投影 |
| `+0x0E` | 最大 HP | 休息 `max_hp/5`、AI 投影 |
| `+0x50+4i` / `+0x51+4i` | 被动槽 ID / 等级 | 被动属性、被动动作修正、会心 `0x0C`、无视防御 `0x19`、actor 惩罚 |
| `+0xB0` / `+0xB1..+0xB9` | 战斗内忍具数 / 九个 ID 槽 | 忍具消费、火弹反击 |
| `+0xBC` / `+0xCA` | 原始 / 当前 character ID | 属性重算、身份覆盖 `0x05` |
| `+0xC0` | 状态字（bit `0x00000100`） | 参与者消费 `0x0D` |
| `+0xC4` / `+0xC5` | 单位 x / y | 格评分、event `0x11` 减分、actor 跟随 |
| `+0xCC` | 阵营 | 目标七槽分组 |
| `+0xCD` | AI 配置行 | 配置选择、scenario rule 分量 |
| `+0xCE` | 携带经验 | 战败转移、经验阈值 |
| `+0xD4` / `+0xD6` | 状态 code / duration | 状态槽遍历、持续时间递减、反应码 |
| `+0x154..+0x1D4` | 已移除事件区 | side-end 顺序 |
| `+0x770` | runtime state（效果选择） | 效果序列选择 |

### 5.2 事件结构 `event`

| 偏移 | 语义 | 参与哪些公式 |
|---|---|---|
| `+0x12` | 待逐个判定的 hit 数 | 多段截断、`0x13` hit count 修正、伤害效用聚合 |
| `+0x18` / `+0x1A` / `+0x1C` / `+0x1E` | 四个伤害候选 | 结算器按逐 hit flag 选一个 |
| `+0x0E` | effect/flag 字 | effect 高位 follow-up 门 |
| `+0x15` | 落点坐标选择器 | effect `0x07` 安全奖励 |
| `+2` / `+3` | 坐标 | 格评分、effect `0x07` |

### 5.3 动作模板（`0x545458 + id*0x10`）

| 偏移 | 语义 |
|---|---|
| `+2` | effect code / flags |
| `+4` | potency（power） |
| `+5` | hit count |
| `+6` | 成功率（target 10 最终钳制 99） |
| `+7` / `+8` | 打包射程 / 形状 |
| `+9` | duration |
| `+0x0A` / `+0x0B` | 资源成本 |
| `+0x0C` | 等级成长目标（type 1..6 → `+4..+9`；type 7 无成长） |
| `+0x0D` | **未命名** |
| `+0x0E` | u16 成长增量 ×(`level-1`) |

### 5.4 AI 配置（`0x0853F348`，8×`0xA8`）

| 偏移 | 语义 |
|---|---|
| `+0x00` / `+0x0C` | HP / 查克拉基础偏置权重 |
| `+0x04` / `+0x08` / `+0x10` / `+0x14` | HP/查克拉投影的互斥分支权重 |
| `+0x18` / `+0x1C` / `+0x20` | kind 1 / 5 / 4 组件权重 |
| `+0x24` / `+0x28` | 类型 2/3（提炼查克拉、休息）与其他无动作候选用权重 |
| `+0x74`..`+0x84` | effect low3 选择的 7 档权重 |
| `+0x88..+0xA7` | 4 个 typed rule 槽（步长 8：kind / parameter / weight） |
| 目标槽权重 | 异阵营 `[1700,800,800,1300,1000,800,3600]`；同阵营 `[4200,2000,1000,1000,1000,800,0]` |

### 5.5 OAM / `render_flags` 位域

| 位 | 参与哪些公式 |
|---|---|
| `0x1000` | attr 前偏移表选择门控 |
| `0x6000`（bit 13/14） | 偏移表 `sel=(flags&0x6000)>>13` |
| `0x18000`（bit 15/16） | 非 affine H/V flip 与 `component.tile_flags` XOR |
| `0xC0`（bit 6/7） | attr2 priority bits 10-11 |
| bit 19 | affine double-size |
| `0x00400000`（bit 22） | 动态 OBJ VRAM 拷贝分支（当前 22 sequence 不可达） |
| `0x01000008`（bit 24/3） | bit22 分支门控 `bit23==0 ∧ (flags&0x01000008)!=0x01000008` |
| 栈 mode bit0 | 非 affine flip 的额外约束 |
| `task+0x13` | task angle 位置旋转（非 affine flip 也受其约束） |

### 5.6 音频寄存器

| 寄存器 / 字段 | 参与哪些公式 |
|---|---|
| `SoundInfo.divFreq`（=532） | mixer phase 推进、forward-linear increment |
| channel `+0x20` step | 同上 |
| channel `+2` / `+3` | pre-envelope R/L 增益 |
| channel `+4..+7` | ADSR 相位机状态 |
| channel `+0x0A` / `+0x0B` | mixer L/R 增益 |
| track `+0x12` / signed `+0x14` | VOL / PAN 命令落点 |
| `wave.frequency_raw`（Q10 Hz） | key 插值 step |
| reverb（SongHeader byte 3） | reverb seed |
| **NR41/NR42/NR43/NR44/NR51** | PSG 通道分配、包络、时钟、pan 掩码 |
| **NR50 / SOUNDCNT_H** | 宿主混音尺度（`0x77` / `0xA90E`，属 ROM 侧写入） |
| DMA1/DMA2 `0x040000A0/A4`、FIFO `0x04000080/84` | 264 样本/VBlank 节拍 |

---

## 6. 明确未闭合 / 未签发的公式（勿当结论）

| 项 | 原文边界 | 证据 |
|---|---|---|
| AI 候选生成、评分、目标优先级与 RNG 公式（`0x080851F8` 内部） | 未闭合 | `notes/battle-system-restoration-evidence-20260723.md:305-306` |
| 状态增减益、朝向/地形特例、联携追加、治疗、非伤害效果 | 需分支级证据 | 同上 `:622-624` |
| 「第三 hit 必定 miss」 | 不能推成；只唯一确定结果组成，不确定顺序 | 同上 `:627-628` |
| 各状态 code 的可见名称 / 图标 / 专属动画 | 未闭合 | `notes/battle-status-action-compliance-20260726.md`、`notes/battle-effect-flag-followups-20260726.md` |
| 原因码 `9–20` 的可见文案 | 未闭合 | `notes/battle-system-restoration-evidence-20260723.md:885-886` |
| 被动 EXP 加成 type `0x15` | 未闭合 | `notes/battle-result-progression-runtime-20260725.md:142-143` |
| `0x59F560` 阈值表除三位主角外的 60 条映射 | 未知 | 同上 |
| easing 插值表达式（切片 `0x080986E8..0x080986F8`） | 仅定位切片，未签发 | `notes/story-scene-timelines-export-20260729.md:56` |
| 多 BG/OBJ 最终合成、window mask、shadow register VBlank 顺序 | `runtime_pixel_equivalence=false` | `notes/story-scene-timelines-export-20260729.md:65,67-69` |
| 世界地图 label palette / 屏幕坐标 / 最终合成 | 未完成 | `notes/world-map-background-export-20260729.md:89-95` |
| 结构化 MIDI → bit-accurate 整曲输出 | 不成立 | `notes/directsound-pitch-step-20260713.md:62-63` |
| PSG 最终可听渲染 | 不成立 | `notes/psg-noise-runtime-chain-20260713.md:46-48` |
| 80 个 cue 玩家可见语义命名 | 未完成 | `notes/m4a-full-song-render-20260713.md:63-65` |
| 补充查克拉 / 休息的完整公式分支（被动、状态、脚本覆盖） | 未伪造常量接入 | `notes/butano-battle-domain-rewrite-20260723.md:628` |
| 反应候选选择顺序 | 「中性策略，不记为 ROM 精确公式」 | 同上 `:442-447` |

---

## 7. 已被证伪 / 已被取代的旧解释（引用时须避用）

| 旧说法 | 纠正 | 证据 |
|---|---|---|
| `docs/rom-reverse-engineering-results.md:84-97` 等级成长表 `0x5459D4` 47×12 | 实际 `0x5459C8` / `0x085459C8` 45×12 | `docs/structure-field-semantics.md:258-263` |
| 同上 `:125-132` 经验曲线 `0x09C580` | 实际 `0x59F560` 63×4 阈值表 | `notes/battle-result-progression-runtime-20260725.md:76-94` |
| 同上 `:134-149` `0x545458` 是「32 entries battle configuration」 | 实际 87×16 主动技数值模板 | `docs/structure-field-semantics.md:29-41` |
| 同上 `:151-166` / `:222-237` 两张 Character Stat Table | 已被标为 disproved | `docs/structure-field-semantics.md:115-120` |
| 同上音频章节 `0x53F138`「88×Sappy 指针表」、`0x079668`「Sappy 命令处理器」 | `0x53F138` 实为 motion/effect 表；`0x08079668` 是消息表/分发器 | `notes/audio-palette-identity-correction-20260711.md:9-19` |
| `0x53D914`「positions / 8 场景」 | 已撤销，是 map row 0 的 `tile_gfx_ptr` | `notes/positions-rom-source-20260710.md:31-32` |
| `0x53D910`「Encounter Zones / zone_id+0x1C」 | 已证伪：`+0x1C` 就是 map `flags` | `docs/structure-field-semantics.md:177-184` |
| `0x545200`「Stats B」 | 已证伪物理别名 = `0x545068 + 25*0x10 + 8` | `docs/structure-field-semantics.md:115-120` |
| `notes/map-format.md`、`notes/map-addresses.md` tilemap 32×32 区 | Superseded，真实布局经 `0x53D910 +0x0C` 指针 | `notes/map-format.md:3-14` |
| `notes/battle-scenario-config.md` 16 字节 16 条视图 | 被 47×32B 头表取代（旧文档未标注作废） | vs `notes/maps-runtime-fields-20260711.md:5` |
| 旧立绘地址 `0x5A4E14`（155×16） | 改用 `0x5A4DEC` 311 变体 | `notes/results-viewer-audit-20261018.md` |

---

## 8. 闭合度速查

| 域 | 闭合公式数 | 未闭合/边界项 |
|---|---|---|
| 战斗数值 | 53 | 状态可见名、AI 候选生成、被动 EXP `0x15`、资源命令修正分支 |
| 音频引擎 | 19（ROM 侧 15 + 宿主侧 4） | 整曲 bit-accurate、PSG 可听渲染、cue 语义命名 |
| 图形动画 | 47 | easing 表达式、多 BG/OBJ 最终合成、世界地图 label 坐标 |
| 关卡地图剧情 | 26 | 编队索引枚举语义、9 个 postbattle u16、60 条经验阈值 |

---

## 9. 宿主（Butano）侧工程常量 —— **非 ROM 公式**

| 项 | 内容 | 证据 |
|---|---|---|
| 动作目录容量 | 24（15 主动术 + 9 忍具） | `notes/battle-formation-runtime-config-20260726.md:92-100` |
| 菜单 8 位 cost / 9 字节目录 / 384B flow / 1120B 快照 | 完整 ROM cost 最大 200 | 同上 |
| 编队配置优先级 | `progression > explicit policy > formation > character template` | `notes/battle-formation-runtime-config-20260726.md:19-20` |
| Campaign SRAM 协议 | 双 4096B 槽，`KBCS` magic/版本/长度/generation/CRC32，63 条逐字段 LE，**不与原作 SRAM 二进制兼容** | `notes/battle-campaign-persistence-runtime-20260726.md:26-38` |
| 反应候选选择顺序 | 中性策略，非 ROM 公式 | `notes/butano-battle-domain-rewrite-20260723.md:442-447` |

---

## 10. 复核方法

本文是**汇总**，不是新证据。任何一条的复核入口：

1. 按表中 `file:line` 读原文，确认措辞未被升级；
2. 涉及 JSON binding 的，跑对应 `tools/analyze_*.py` 与 `tests/test_*.py`；
3. 涉及音频的，`tools/m4a_pitch_step.py` / `m4a_envelope.py` / `m4a_psg.py` / `m4a_pcm.py` / `m4a_scheduler.py` 是固化实现，与 A–F 组公式逐条对应；
4. 重型运行（mGBA、Chromium）必须经 `tools/run_guarded.py`。

**本轮未运行任何 verifier 或测试**；「测试锁定」仅依据 notes 与 `tests/` 中存在的用例名。
