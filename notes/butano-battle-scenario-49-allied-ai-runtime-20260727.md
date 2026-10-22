# Butano scenario 49 / Battle 14 任务友军与完整回合纵切（2026-07-27）

## 结论

scenario 49 / battle 14 已从“同阵营单位都由玩家操作”的通用假设扩展为真实任务战：

```text
generation 8 campaign SAV
  → generated battle 14 / 15×19 map / 9 units
  → Team 7 玩家回合
  → character 30 同阵营任务 AI 回合
  → character 55 敌方 AI 回合
  → resolver / condition / result / progression
  → scenario 50
```

本里程碑没有用截图决定坐标、HP、伤害、胜负或经验。宿主集成测试和完整 mGBA 路线都只
使用公开 controller 输入或合法 GBA 按键；Lua 只读 telemetry，不写内存。最终 mGBA
从 generation 8 SAV 冷启动，完成战斗、结算、成长、generation 9 SRAM 写后读验证并进入
scenario 50。

## 原版证据与边界

原版真值来自 `notes/scenario-49-battle-14-runtime-20260720.md`：

- battle 14 地图为 15×19；
- Team 7 为 Naruto LV5/HP138、Sasuke LV4/HP104、Sakura LV5/HP110；
- unit 4 为同阵营 character 30 / LV3 / HP40；
- unit 5–9 为 character 55 / LV5 / HP25；
- 原始存档中 unit 4 的 side 为 player，但 action/config 字段表明它不是普通玩家单位；
- 敌方 config 4 的关注目标是 character 30；
- unit 4 从入口 `(8,7)` 移动到原版 turn-4 样本的 `(12,3)`；
- 胜利要求消灭五敌，任务角色死亡会在 Team 7 尚存时触发败北；
- reward row 39 为 mission 125、round bonus 75、limit 8。

`(12,3)` 只被视为“原版可观察路径锚点”，不是已经证明的 ROM 脚本地址或完整 AI
算法。battle 15 同样把 character 30 归入任务 AI，但没有证据支持沿用 battle 14
锚点，因此不注入猜测坐标。

## 架构改动

### 数据驱动控制权

`battle_mission_rules` 新增任务控制策略。关卡只声明哪些角色由任务 AI 控制，以及是否有
可观察位置目标；loader 仍负责从 generated formation 构造单位。character 30 保留
formation 自带的 config 2 / LV3 / HP40，不会退回通用角色配置的 LV1 / HP10。

控制权现在明确分为：

- `player`：可由光标选择并接收玩家命令；
- `ai`：由共享 AI planner 执行，包括 player side 的任务友军和 enemy side；
- `scripted`：保留给真正的脚本单位，不再拿来代替自主任务角色。

### 回合调度

controller 只把 `battle_control::player` 单位加入玩家选择环。三名玩家角色行动完毕后，
先执行 player side 的任务 AI，再进入 enemy side AI。任务 AI 仍调用共享
`plan_ai_turn`、pathfinder、动作 resolver、表现 FIFO 和 condition evaluator，没有
battle-14 专用第二套 FSM。

AI objective 的位置权重被放入公共候选评分，而不是 controller 直接写坐标。这样后续
护送、撤离、守点任务可以复用同一任务控制策略；没有可靠目标证据的关卡可只声明 AI
控制而不声明位置。

## TDD 纵切

红绿重构覆盖了以下失败：

1. battle 14 任务规则最初没有控制权字段；
2. 把 character 30 误判为 scripted 后，原始 savestate 的 side/action 字段复核要求改为
   自主 AI；
3. loader 识别任务 AI 后仍错误加载通用角色配置，HP 从 40 退成 10；
4. 三名玩家行动完毕会直接进入敌方回合，遗漏同阵营任务 AI；
5. controller snapshot 一度从 1120 增至 1160 bytes，触发 ARM 预算门；移除重复 view
   字段后恢复预算。
6. mGBA 最初只能看到选择角色和坐标，无法区分宿主与 ARM 路线差异；在既有 telemetry
   ABI 尾部追加 12 个单位的 HP、查克拉、阵营、控制权、资源预览和 condition outcome，
   旧偏移保持不变，总大小为 824 bytes；
7. `preserve_empty_unit_slots` 构造 reserve 单位时未做值初始化，宿主偶然得到零值而 ARM
   可能保留旧栈内容；先以 inactive slot 10–12 红测复现，再改为
   `battle_unit_instance reserve{}`；
8. 完整 mGBA 结算最初把鸣人升级后余量误算为 60。generation 9 槽的有效 CRC 证明实际
   为 LV6/EXP0/TP5：LV5 阈值是 `250 + 15×4 = 310`，入口 EXP85 加本路线 225 正好清零。

完整 scenario 49 集成测试验证两条独立路径：

- 失败路径：Team 7 全部待机，character 30 自主移动、受伤、到达 `(12,3)`，随后死亡；
  Team 7 仍存活但 condition 返回 loss；
- 胜利路径：只使用公开移动、命令、查克拉补充、动作 5、佐助动作 16、目标、防御和回合
  tick；character 30 自主行动且受伤但存活，五敌在第 8 回合限制内全部由 resolver
  击倒，condition 返回 win。

胜利路线实际击倒分配为 Naruto 3、Sasuke 1、Sakura 1，因此 live settlement 是：

- Naruto：LV6 / EXP125 / TP5；
- Sasuke：LV5 / EXP175 / TP4；
- Sakura：LV6 / EXP155 / TP5。

测试另以原版记录的击倒经验分配核对 reward row 39，可得到 Naruto LV6/EXP75、
Sasuke LV6/EXP35、Sakura LV6/EXP105。两组结果不同是合法路线的击倒归属不同，不是固定
结果表或结算分叉；mission/bonus 规则和共享 progression 相同。

### mGBA 合法输入纵切

ARM 上的敌方同分候选和实际站位演化与宿主路线不同，不能把宿主第 8 回合坐标序列写死。
最终驱动读取真实地图、单位槽和资源状态，使用共享规则保护任务友军；敌人降至两个后才
释放护卫位追击。它在第 9 回合合法获胜，因此 reward row 39 的 8 回合 bonus 门正确返回
0，而不是为了匹配宿主路线伪造 75。

最终 `artifacts/butano-battle-scenario-49-allied-ai-complete-20260728-15/` 记录：

- 317 个唯一领域转换；
- 影分身占用 unit 10，拥有 HP、查克拉、阵营、位置和行动回合；
- character 30 受伤后存活，胜利帧 HP36、位置 `(12,3)`；
- unit 5–9 全部由 resolver 置为 inactive，`condition_outcome=1`；
- 鸣人结果行为 mission 125 / battle 100 / round bonus 0 / total 225；
- 最终 SRAM 为 generation 9 / scenario 50 / verified，CRC 有效；
- Naruto LV6/EXP0/TP5、Sasuke LV5/EXP150/TP4、Sakura LV6/EXP80/TP5；
- controller/player error 均为 0。

曾尝试在自动路线创建第二个影分身以强迫第 8 回合结束；真实运行证明它改变敌方寻路后会
让任务友军在第 5 回合死亡。该方案被撤销，失败证据保留在
`artifacts/butano-battle-scenario-49-allied-ai-complete-20260728-12/`。这也说明通过标准
是领域胜负和任务语义，而不是让自动化凑出预设回合数。

## 构建与运行证据

- 全量宿主：通过；
  `build/resource-guard/butano-s49-victory-full-host-20260728-01.json`，峰值
  155.4453125 MiB。
- ARM 构建：通过；
  `build/resource-guard/butano-s49-victory-arm-build-20260728-01.json`，峰值
  75.15234375 MiB。
- ROM 入口：
  `artifacts/butano-battle-scenario-49-allied-ai-entry-20260727-01/`。
- 完整 mGBA：
  `build/resource-guard/butano-s49-victory-mgba-20260728-15.json`，由 success marker
  正常结束，峰值 125.03515625 MiB；运行目录为
  `artifacts/butano-battle-scenario-49-allied-ai-complete-20260728-15/`。
- Lua/协议/路由/telemetry：32 项 Python 测试、Lua 语法、5 个 JSON manifest 和
  `git diff --check` 通过。
- machine-readable manifest：
  `notes/evidence/butano-scenario-49-allied-ai-runtime-20260727.json`。

mGBA 从 scenario 47 完成后生成的 generation 8 SAV 冷启动，入口遥测为：

- scenario 49 / battle 14；
- round 1 / unit selection；
- 9 个活动单位；
- selected character 1；
- `load_generation=8`、`load_used_default=0`；
- controller/player error 均为 0。

当前 ROM/ELF SHA-256：

- ROM：
  `de8144edf14d139aaa638b2fe79fec6497f4f09fae3e85f704fd655f0102a083`
- ELF：
  `5cff87b36b7806fb1b23bea53dbbb18655a740690fa3021642a8ce3287934c6f`
- 输入 SAV：
  `3f473ececd31485800c1d907ca7a9b97350fc74f354ffb5a9032ce349a9dbc88`
- 输出 SAV：
  `2a8b55da3e0d1e5b8831ef95aab50f6bda5376ceac2aa442cafd848e254d9037`
- mGBA 驱动：
  `74ed74927efd81b10f50751da0a294caa2e11721fa7f8d0638da82c596cc60dd`

本次 ELF 的 telemetry 地址为 campaign `0x020081B0`、battle `0x02022768`。

## 未完成边界

- 完整 mGBA 已签发 generation 8 → battle 14 胜利 → generation 9 → scenario 50；
  scenario 49 不再是待签发边界。
- 早期合法按键探索和被否定的双分身路线仍作为负证据保留，不作为通过证据。
- battle 14 的任务 AI 路径目前只绑定一个可观察锚点；原版完整威胁规避、目标切换和动作
  选择仍需更多逐帧样本。
- 运行显式 `mute=1`、`audioSync=0`，不能签发音频撕裂已修复。
- scenario 48 剧情、scenario 50+ 完整纵切、逐角色 sprite、逐技能精确 OAM/音效仍未
  完成，因此完整战斗 Goal 保持 active。
