# 原版战后经验规则（2026-10-20）

## 一句话结论

原版**不是**给全队同一个经验数，而是每人三项相加：

```text
gain(member) = mission_experience(记录+0, 全员相同)
             + round_bonus_experience(记录+2, 全员相同, 仅当 current_round <= round_limit(记录+4))
             + carried_experience(member)   (该角色击败/关联到的单位携带经验之和)
```

再按 `required(level) = base_threshold + per_level_increment × (level-1)` 反复扣除升级。
本轮用**三个互不相同的战斗**（battle 14 / 教程 scenario 41 / 五猫 scenario 46）逐个复算，
原版战后等级、剩余经验、体力与修炼点**全部逐位对上**。
战前经验不在任何奖励表里，它是角色模板的持久字段（原版 battle 14 为 **160 / 100 / 190**）。

## 1. 问题

原版按什么规则决定「每个队员战后各得多少经验」「每人战前已经有多少经验」？重制目前给全队同一个数
（`mission_experience 125 + round_bonus 75 = 200`，见 `butano-sequel/game/include/konoha/generated_battle_result_content.h`），
因此复现不了原版逐人结果（鸣人 `EXP 100/325`、佐助连升两级）。

## 2. 方法（全部只读；未启动模拟器）

```sh
cd /Users/altair/github/gba-naruto-reverse
/usr/local/bin/python3 tools/disasm_thumb.py rom/base.gba 0x0808983C --before 0 --size 0x60
/usr/local/bin/python3 tools/disasm_thumb.py rom/base.gba 0x080893E4 --before 0 --size 0x70
/usr/local/bin/python3 tools/disasm_thumb.py rom/base.gba 0x0806AD80 --before 0 --size 0x30  # 0x0806B210 同样
```

存档快照按逆向树 `tools/inspect_mgba_savestate.py` 的 `gbAs` chunk 布局**只读**解析
（EWRAM base `0x02000000`，快照内偏移 `0x21000`，长度 `0x40000`）：

- 模板池 `0x02022E34 + slot*0xBC`：经验 `+0x10` u16、等级 `+0x01`、上限HP `+0x0E`、修炼点 `+0xBA`
- 战斗单位池 `0x020240C0 + slot*0x1D4`：当前HP `+0x0C`、上限HP `+0x0E`、携带经验 `+0xCE`
- 外层状态 `0x020311D4`（`+0x16` 战斗/场景号，`+0x19` 变体尾数），当前回合 u8 @ `0x0202680C`

快照（均在 `artifacts/runtime-checkpoints/`）：`scenario-49-battle-14-entry.ss9`
（`a3628723ac595f41…`，战前）、`…-turn4-two-kills.ss9`（`e8b2a5ee0cc4dfbc…`，中途）、
`…-postbattle-task-menu.ss9`（`8dfca22976fdb741…`，战后）、
`scenario-41-level-up-1.ss9`、`scenario-46-victory-reward.ss9`。

ROM `rom/base.gba`，SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`（两棵树同一份）。

## 3. 逆向侧已闭合的部分（原文引用）

1. **战后经验规则逆向侧未闭合**。`notes/levels-runtime-probe-20260713.md:145`：
   > 「battle 并捕获战后 EXP/level/训练点；levels 严格保持 `code_verified`。」

2. `0x59F560` 逆向侧已按 **u8 索引 u16 对 lookup** 闭合（不是经验专用表），
   `notes/rom-u8-indexed-u16-pair-lookup-20260827.md:18-20`：
   > 「cell 编码：little-endian `u16 multiplier` + little-endian `u16 addend`；真实结果：`u16(multiplier_u16 * (count - 1) + addend_u16)`。」

3. `0x59EAE0` 逆向侧**拒绝**冻结成 112×24 表，
   `notes/rom-unknown-candidate-59eae0-negative-evidence-20260827.md:11-14`：
   > 「静态代码能证明两个消费者都计算：`index = byte[0x08348DAC + state[0x16]] + state[0x19]`；`record = 0x0859EAE0 + index * 24`」
   同文件给出反例 `(state[0x16], state[0x19]) = (31, 30)` ⇒ index 120 > 111，**表长未闭合**。

4. battle 14 战后事实（`notes/scenario-49-battle-14-runtime-20260720.md:41-44`）：
   > 「战后 Naruto `LV5 -> LV6`，体力 `+14`…；状态页显示 `EXP 100/325`、HP `152/152`。Sasuke 连升两级、`LV4 -> LV6`，体力合计 `+30` …」
   同文件 `:10-11` 给出入口等级/HP：`LV5/138`、`LV4/104`、`LV5/110`。

5. 角色模板 `+0x10` 是经验值（`notes/character-stats-addresses.md:45-46`）；
   LV1 页面显示 `100/250`（`notes/character-definition-source-20260711.md:125`）。

6. 结算页读数（`notes/scenario-46-entry-runtime-20260719.md:291-292`）：
   > 「胜利结算页显示三名角色本战经验均为 125，另列 59/59/30，合计显示 184/184/155。」

7. 重制树自己已记录**原版代码级**的同一规则（`notes/battle-result-progression-runtime-20260725.md:38-94`）：
   编队 `+0x0C` → 战斗单位 `+0xCE`、击败时转移给归属角色、
   `required(level) = base_threshold + per_level_increment * (level - 1)`、
   `current_round <= round_limit` 才取回合奖励。

## 4. 本轮新解码（ROM 偏移 + 字节 + 反汇编）

### 4.1 等级阈值：`0x59F560`，消费者 `0x0808983C`

cell 4 字节 = `(u16 per_level_increment, u16 base_threshold)`，按 `character_id` 直接索引：
鸣人1 `0x59F564` = `0f 00 fa 00`（15/250）；佐助2 `0x59F568` = `0f 00 b4 00`（15/180）；
小樱3 `0x59F56C` = `0f 00 96 00`（15/150）。反汇编逐条对上：

```text
0x08089868 ldr  r0,[pc,#0x6c]   ; r0 = 0x0859F560
0x0808986A lsls r1,r3,#2       ; cell = base + char_id*4
0x08089870 ldrh r3,[r2]        ; increment = cell[0]
0x08089872 subs r2,r4,#1       ; level-1
0x0808987A muls r0,r2,r0       ; increment*(level-1)
0x0808987C ldrh r1,[r1]        ; base = cell[1]（cell+2）
0x0808987E adds r0,r0,r1       ; required = increment*(level-1)+base
0x08089886 cmp  r5,r1 / blo    ; exp_left < required → 退出
0x080898A2 subs r0,r5,r1       ; exp_left -= required
0x08089896 adds r0,r2,#1       ; level++
0x080898B6 cmp  r4,#0x31 / bhi ; level > 49 → 退出（最大等级 50）
0x080898C6 strh r1,[r0]        ; 满级剩余经验 = 999
```

### 4.2 奖励记录与当前回合：`0x59EAE0`（stride 0x18），消费者 `0x080893E4`

```text
0x080893E4 ldr  r1,[pc,#0x164]  ; 0x08348DAC lookup（u8）
0x080893E6 ldr  r2,[pc,#0x168]  ; 0x020311D4 外层状态
0x080893E8 ldrb r0,[r2,#0x16]  ; 战斗/场景号；0x080893EC ldrb r1,[r0] → lookup[id]
0x080893EE ldrb r0,[r2,#0x19]  ; 变体尾数
0x080893F0 ldr  r2,[pc,#0x160]  ; 0x0859EAE0 记录基址
0x080893F2 adds r1,r1,r0       ; index = lookup[id] + tail
0x080893F4..FA                 ; index*24 → record
0x080893FC ldrh r0,[r1]        ; 记录+0 = mission_experience
0x08089402/04 ldrb r0,[0x0202680C] ; 当前回合（u8）
0x08089406 ldrh r2,[r1,#4]     ; 记录+4 = round_limit
0x08089408 cmp  r0,r2 / bhi    ; current_round > limit → 不取回合奖励
0x0808940C ldrh r0,[r1,#2]     ; 记录+2 = round_bonus_experience
```

本轮用到的记录（字节与重制侧解码值逐字节一致）：

| 记录 | 文件偏移 | 原始字节 | mission | bonus | limit |
| ---: | --- | --- | ---: | ---: | ---: |
| 24 | `0x59ED20` | `7d 00 4b 00 08 00 …` | 125 | 75 | 8 |
| 39 | `0x59EE88` | `7d 00 4b 00 08 00 00 01 00 25 00 49 01 …` | 125 | 75 | 8 |
| 104 | `0x59F4A0` | `64 00 19 00 03 00 00 00 …` | 100 | 25 | 3 |

lookup（`0x348DAC`，u8）：`lookup[9]=24`、`lookup[14]=39`、`lookup[41]=104`。
battle 14 入口快照 `state+0x16=14`、`state+0x19=0` ⇒ index 39 ⇒ 记录 39 = **125 / 75 / 8**
（与重制 `artifacts/s49-result-settlement-v1/settlement.json` 的 `"reward_record":39` 一致）。

### 4.3 携带经验：装载与转移

```text
0x0806AD92 ldrh r0,[r5,#0xc]   ; 编队记录 +0x0C
0x0806AD96/98 adds r1,#0xce ; strh r0,[r1]   ; → 战斗单位 +0xCE

0x0806B224 adds r1,#0xce       ; 归属方单位 +0xCE
0x0806B22A ldrh r0,[r0]        ; 被击败单位 +0xCE
0x0806B22C ldrh r4,[r1]        ; 归属方当前携带
0x0806B22E adds r0,r0,r4
0x0806B230 strh r0,[r1]        ; 归属方 += 被击败方
```

### 4.4 原版 battle 14 的战前/战后状态（从 .ss9 直接读出）

战前（`scenario-49-battle-14-entry.ss9`）：

| 槽 | 角色 | 等级 | **经验(+0x10)** | 上限HP | 修炼点 | 携带经验(+0xCE) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 鸣人 1 | 5 | **160** | 138 | 4 | 0 |
| 2 | 佐助 2 | 4 | **100** | 104 | 3 | 0 |
| 3 | 小樱 3 | 5 | **190** | 110 | 4 | 0 |
| 4 | 木叶丸 30 | 3 | 0 | 40 | — | 0 |
| 5–9 | 蜜蜂 55 ×5 | 5 | 0 | 25 | — | **50 each** |

战后（`scenario-49-battle-14-postbattle-task-menu.ss9`）：

| 槽 | 等级 | 经验 | 上限HP | 修炼点 | **携带经验** |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 鸣人 | **6** | **100** | 152 | 4→5 | **50**（击倒 1 个） |
| 2 佐助 | **6** | **35** | 134 | 3→5 | **200**（击倒 4 个） |
| 3 小樱 | **6** | **180** | 125 | 4→5 | **0** |
| 5–9 | id=0（已击倒） | — | — | — | 50 each |

回合计数 `0x0202680C` = 6（≤ limit 8 ⇒ 回合奖励生效）；中途快照 `…turn4-two-kills.ss9`
携带经验 50/50/0，与「佐助先手火遁击倒槽 9、鸣人普通攻击收掉槽 8」一致。

## 5. 规则（正式表述）

```text
record  = 0x0859EAE0 + (lookup[state+0x16] + state+0x19) * 24
          lookup = 0x08348DAC (u8), state = 0x020311D4
mission = record[+0]                                       ; 全员相同
bonus   = record[+2] if current_round <= record[+4] else 0  ; 全员相同
carried = 该角色战斗中累计的 unit+0xCE（击倒/关联转移而来）
gain    = mission + bonus + carried
required(L) = base_threshold(char) + per_level_increment(char) * (L - 1)
              char cell = 0x0859F560 + char_id*4（cell[0]=increment, cell[1]=base）
exp_total = exp_before + gain
while exp_total >= required(level): exp_total -= required(level); level += 1
（level > 49 停止，剩余经验写 999）
```

## 6. 算术复现（逐位对上）

**样本 A：battle 14**（记录 39 = 125/75/8，回合 6 ≤ 8 ⇒ bonus 75）

- 鸣人：160 + (125+75+50) = 410 = 310(升 LV6) + **100** ⇒ `EXP 100/325`
  （325 = 250+15×5 = 升 LV7 阈值）✓ 与逆向笔记原话一致
- 佐助：100 + (125+75+200) = 500 = 225(升 LV5) + 240(升 LV6) + **35** ⇒ **连升两级** ✓
- 小樱：190 + (125+75+0) = 390 = 210(升 LV6) + **180** ✓
- 体力 138→152 / 104→134 / 110→125、修炼点 4→5 / 3→5 / 4→5，与战后快照逐位一致 ✓

**样本 B：教程战 scenario 41**（记录 104 = 100/25/3，回合 4 > 3 ⇒ **无**回合奖励）

- 鸣人 LV1/100 + (100 + 0 + 携带 50) = 250 = required(LV1→2) = 250 ⇒ LV2 / 剩余 0，
  HP 94、修炼点 1 ✓ 与 `scenario-41-level-up-1.ss9` 一致，也与
  `notes/battle-result-progression-runtime-20260725.md` 的 `100+50+0=150` 一致

**样本 C：五猫任务 scenario 46**（记录 24 = 125/75/8，回合 47 > 8 ⇒ **无**回合奖励）

- 战前 LV3/275、LV3/0、LV3/60；携带 60/60/30
- 鸣人 275+185 = 460 ⇒ −280 = 180 ⇒ LV4（HP 109→123，+14）✓；佐助 0+185 = 185 < 210 ⇒ 仍 LV3 ✓
  （逆向笔记也只说鸣人、小樱升级）；小樱 60+155 = 215 ⇒ −180 = 35 ⇒ LV4（HP 80→95，+15）✓

**不符的读法**：`每击倒 1 个 +125` 会推出「佐助 150+200=350 < 465，升不了两级」；`统一 200`
也不成立（三人总经验必须分别是 410 / ≥465 / 210+r）。只有「任务 + 回合 + 按人携带经验」才对得上。

## 7. 未确立（残余未知）

1. **奖励表物理上界**：逆向树明确拒绝 112×24（index 可达 120+）；本轮只用消费者算术，
   不宣称表长或安全索引域闭合。
2. **尾数项 `state+0x19`** 三个样本均为 0（完整域未取样）；**mission 是否永远全员相同**
   只有 3 个战斗的 3/3 人相同的样本。
3. **归属分支**：逆向侧注明「召唤/关联单位特殊归属分支未闭合」；本轮只解码 `0x0806B224`
   一处转移，`0x0806B29E` / `0x0806B2EC` 的触发条件未逐条解码。
4. **被动 EXP 加成（type 0x15）** 未闭合；**满级 50 / 剩余 999** 只从代码读出，未运行验证。
5. **逆向笔记 ±1 转写**：scenario 46 结算页笔记写「59/59/30、184/184/155」，快照权威值是携带
   60/60/30 ⇒ 应为 185/185/155。两种读法都不改变升级结论，但**转写差异本身未解释**。
6. **战前经验来源**：角色模板持久字段（`+0x10`），不是阵型表 `battle_experience`
   （battle 14 入口两者都是 0，而经验是 160/100/190）。此前各战的经验累积链本轮未回溯。

## 8. 残余各自还缺哪一次测量

| 残余 | 需要的测量 |
| --- | --- |
| 奖励表边界 / 索引域 | 先闭合 `0x0808F654` 的 scheduler callback 生命周期 gate（逆向树已写明前置条件），再枚举 `(state+0x16, state+0x19)` 自然可达域 |
| mission 是否恒等 | 再取 2–3 个**奖励记录不同**的战斗，读结算页三列 + 战后模板 `0x02022E34+slot*0xBC+0x10` |
| 归属分支 | 同一战斗改用「召唤/关联单位」样本，比较击杀者与归属者的 `+0xCE` |
| 被动 EXP 加成 | 装备带 type 0x15 的被动后复测同一战斗，比较三人增益差 |
| ±1 转写 | 直接重读 scenario 46 结算页原始帧（本轮未重读截图） |

## 9. 对重制的含义（本轮只记录，未改任何代码/数据）

- 「统一 200」只在「无人携带经验且拿到回合奖励」时与原版一致；battle 14 原版是 **125+75+{50,200,0}**。
- 重制的战前经验默认 **85 / 150 / 115** 与原版 **160 / 100 / 190** 全部不符，而升级判定依赖它，
  所以「统一 200」在**输入端**就已错。
- 要复现原版需按人建模：mission（全队）+ round bonus（全队，带 `current_round <= limit` 条件）
  + 击败单位的携带经验（按归属角色累加）+ 查表升级；阵型表 `battle_experience` 是**携带经验**，
  与角色模板的持久经验是两个量。

## 10. 可复用任务模式（建议登记）

**模式**：固定存档快照的只读 EWRAM 读取 + ROM 表/消费者反汇编的规则复原
**方式**：可复现脚本（解析器 + 独立 verifier）；执行时 Luna schema 不可用，Terra 只读复核
**边界**：只解析 `.ss9` 的 `gbAs` chunk（EWRAM 偏移 0x21000 / 0x40000），**不启动模拟器**；
**不要**把 `state+0x16` 当经验或等级字段
**教训**：逆向侧未闭合「战后经验」时，先找**战斗前后的存档快照**，别继续猜公式

## 11. 本轮边界

- 只写了本文件；未改代码/数据/测试；未提交。逆向树 `/Users/altair/github/gba-naruto-reverse`
  全程只读，未运行 mGBA，未改动任何文件。
- 引用的重制树既有产物：`artifacts/s49-result-settlement-v1/settlement.json`、
  `artifacts/s49-original-battle14-roster-v1/roster.json`、`tools/extract_battle_result_content.py`、
  `docs/konoha-senki/01-battle-s49.md` §4.3.92。
