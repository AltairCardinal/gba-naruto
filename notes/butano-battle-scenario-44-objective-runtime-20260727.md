# Butano 第 44 战两阶段目标运行证据（2026-07-27）

## 结论

第 44 战已经由正式战斗领域自然完成，不再把地图截图或一次按键确认当作战斗：

```text
Team 7 玩家回合 / Kakashi AI 回合
  → 共享移动、动作 5、伤害与击倒
  → 敌方清空但战斗继续
  → 玩家移动到 (4,3)
  → 面向下结束行动
  → 固定对象槽 1: type 3 在事务副本中清空
  → 生成条件 object_slot_inactive(0) 判胜
  → 三人结果 / 成长 / campaign merge
  → SRAM generation 4
  → scenario 45 冷启动
```

原版行为依据仍是
`notes/scenario-44-progression-runtime-20260718.md` 和
`artifacts/runtime-checkpoints/scenario-44-progression-evidence.json`：
卡卡西被击倒只是第一阶段；只有 `(4,3)` 面向下能取得 `(4,4)` 的铃铛，`(3,4)`、
`(4,4)` 和错误朝向不能完成。

## 根因与修复边界

生成条件已经正确表达“对象槽 1 无效时胜利”，但旧加载器没有创建对象槽 1，因此开战时
条件从领域角度已经为真，第一次行动边界就会误胜。这不是模拟器问题，也不是渲染黑屏，
而是场景目标没有进入 session。

修复复用以下既有链路：

- `battlefield_object_table` 新增显式槽位放置，固定目标能与生成条件引用同一槽；
- `battle_mission_rules` 只提供数据：对象记录、交互点、朝向、交互阵营和敌方清空前置；
- `battle_encounter_runtime` 加载时原子初始化对象；
- 所有玩家行动完成边界（含资源命令与朝向/防御）都在事务副本中解析目标交互，再由原
  条件解释器判胜；
- controller、turn flow 和 condition interpreter 内没有 battle 44 分支。

`battle_objectives.h` 的通用谓词引擎没有并入这条路径，因为生成条件表已经是关卡胜负的
权威真值；并行维护第二套胜负引擎会重新制造不一致。

## 成长语义

原版自然结果是三名队员各 125 EXP：

- Naruto：LV3 / EXP125 / TP2；
- Sasuke：LV2 / EXP45 / TP1；
- Sakura：LV1 / EXP125 / TP0。

这要求 Sasuke 在首次加入场景 44 时携带 100 EXP，Sakura 为 0。campaign party policy
已按该前置初始化。卡卡西记录中的 100 EXP 在这场训练任务不进入结果，因此 mission rules
使用通用结果策略关闭 battle EXP；它不修改敌方定义，也不影响场景 41–43 的击倒经验。

## TDD 与宿主证据

- 红：`test_battle_campaign_scenario_44.cpp` 首先证明加载后对象数为 0，而规格要求槽 1
  type 3 `(4,4)`；
- 红：`test_battle_results.cpp` 首先证明结果系统没有按任务关闭 battle EXP 的入口；
- 绿：对象初始化、精确交互和结果策略进入共享运行时；
- 重构：独立 `battle_mission_objective` 领域组件，关卡规则仅保留数据。

`butano-sequel/game/tests/test_battle_campaign_scenario_44.cpp` 只调用 controller 公共操作，
自然执行三名玩家、卡卡西 AI、移动、动作、击倒、目标交互、结果、升级、训练取消、
campaign merge 和 44→45 路由。它不写 HP、单位坐标、对象槽、胜负或 campaign 内存。

全量 `butano-sequel/game/tests` 为 102/102 通过，资源记录：

- `build/resource-guard/20260727-battle-campaign-s44-full-host-03.json`

首次全量运行
`build/resource-guard/20260727-battle-campaign-s44-full-host.json` 仅因编译器 60 秒无输出被
资源守卫判定 idle timeout；没有测试失败，后续用 300 秒编译空闲窗口完成，前一记录保留。

## mGBA 完整胜利与保存

证据目录：

- `artifacts/butano-battle-campaign-route-s44-complete-20260727-01/`
- `artifacts/butano-battle-campaign-route-s44-complete-20260727-02/`
- `build/resource-guard/20260727-battle-campaign-route-s44-complete-02.json`

`-01` 首次成功产物随后被覆盖资源命令边界的最终重构取代；以下签发数据取自 `-02`。

`audit.json`：

- frame 5793，battle 44，round 12，phase complete；
- active units 3，说明卡卡西已不活动而 Team 7 存活；
- `objective_verified=1`，`battlefield_object_count=0`；
- 最终游标和行动单位都在 `(4,3)`，移动目标距离为 0；
- mission/battle/round bonus/total EXP 为 `125/0/0/125`；
- scenario 45，save generation 4 / verified 1；
- Naruto LV3 / EXP125 / TP2；
- controller/player error 均为 0。

ROM/SAV/ELF SHA-256：

- ROM：`f76c36ba28728e8fe05071e0812b315492d735d2022377a1a4fc09c64b6abab5`
- SAV：`579f159d0e9091924a394090ac96155c2c06a869beecce4db08aa2aa75bb1ae7`
- ELF：`9179dab6d7066759706256fda3902aab1e0986f50627baed72600492266e9683`

Lua 只读取 telemetry 并发送 GBA 按键，没有 `emu:write`。

## Scenario 45 冷启动

第二个独立 mGBA 进程复制 generation 4 SAV 后启动：

- `artifacts/butano-battle-campaign-route-s45-cold-20260727-02/audit.json`
- scenario 45 / battle 45 / round 1 / unit selection；
- active units 4，selected character Naruto；
- load generation 4，`load_used_default=0`；
- controller/player error 均为 0；
- `battle-entry.png` 为可见 Team 7 与敌方战场，不是黑帧。

资源记录：

- `build/resource-guard/20260727-battle-campaign-route-s45-cold-02.json`
- `build/resource-guard/20260727-battle-campaign-s44-arm-build-02.json`

## 未完成边界

本轮签发的是可复用的“固定场景对象 + 精确行动交互 + 生成条件判胜”架构和第 44 战完整
纵切。它不自动证明其他关卡的对象类型、坐标、前置或奖励策略；后续关卡仍需逐项依据原
ROM、录像和攻略取证。逐技能专属表现、SFX、scenario 50 后章节和全部 47 场自然路线仍
未闭合，完整战斗 Goal 保持 active。
