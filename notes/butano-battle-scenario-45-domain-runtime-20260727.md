# Butano scenario 45 共享战斗领域纵切证据（2026-07-27）

## 结论

scenario 45 已在宿主集成测试中由同一套生产领域管线完整执行，不是截图、预录帧或
关卡专用选项状态机：

```text
generated encounter / campaign
  → battle_scene_controller
  → player selection / movement / action draft
  → preview / confirm / battle_action_resolver
  → enemy AI / round scheduler / presentation selector
  → generated condition interpreter
  → result / growth / campaign merge / 45→46 route
```

纵切只通过 controller 的公开语义输入推进，没有写 HP、坐标、胜负、结果或 campaign
内存。鸣人、佐助、小樱均来自 campaign progression，卡卡西来自 generated encounter。

## 原版内容与奖励归属

生成数据给出 9×22 地图、玩家角色 1/2/3、敌方角色 7、敌方清空胜利、玩家清空失败；
卡卡西等级 3，携带 100 battle EXP，动作目录为 5/3/2/31，并携带忍具 40。scenario
result 108 给每名参战者 150 mission EXP，5 回合内另有 25 bonus。

原版存档模板池位于 `0x02022E34 + slot*0xBC`，等级字段为 `+0x01`，经验字段为
`+0x10`。不可变 checkpoint 的角色状态为：

- scenario 44：鸣人 LV3/125、佐助 LV2/45、小樱 LV1/125；
- scenario 45：鸣人 LV3/275、佐助 LV3/0、小樱 LV3/60。

小樱升级阈值依次为 150、165，因此只有
`125 + 150 mission + 100 Kakashi - 150 - 165 = 60` 能解释原档。结论是：三人各得
150 mission EXP，卡卡西的 100 battle EXP 只归实际击倒者小樱。共享 resolver 已在
击倒事务中把目标 `carried_experience` 转给 actor；scenario 45 必须使用默认结果策略，
不能复制 scenario 44 训练任务的禁用 battle EXP 特例。

## 宿主完整纵切

`butano-sequel/game/tests/test_battle_campaign_scenario_45.cpp` 构造真实的第 44 战后档案，
为鸣人装备忍具 1，并验证：

- 鸣人目录含动作 2/5/7 和忍具 1；佐助含 2/5/16；小樱含 1/2/5；
- 鸣人使用十字手里剑后装备槽和库存同步消费；
- 佐助移动后仍能使用动作 16，组合选择取消到单独施术后消耗 2 查克拉；
- round scheduler、卡卡西 AI 和第 1/2/3 回合玩家表现选择器均走共享链；
- 小樱完成最后击倒并独得 100 battle EXP；
- 为避开 5 回合奖励，结果为三人 mission 150、bonus 0；小樱 total 250，其余 total 150；
- 最终鸣人 LV3/275/TP2、佐助 LV3/0/TP2、小樱 LV3/60/TP2；
- 忍具 1 已消费，campaign 从 scenario 45 原子推进到 46。

全量宿主验证由
`build/resource-guard/20260727-battle-campaign-s45-full-host-01.json` 记录：
103/103 个 game C++ 测试通过，退出码 0，峰值 RSS 155.0078125 MiB。

## mGBA 根因与完整运行时闭环

基于已验证 generation 4 SRAM 的前三次 guarded mGBA 运行均自然到达 scenario 45
结果页，最后进度一致：frame 5339、round 11、phase 14（RESULT）、scenario/battle 45，
controller/player error 均为 0。运行分别记录在：

- `artifacts/butano-battle-campaign-route-s45-complete-20260727-01/`
- `artifacts/butano-battle-campaign-route-s45-complete-20260727-02/`
- `artifacts/butano-battle-campaign-route-s45-complete-20260727-03/`

对应守卫峰值为 141.6758、152.7617、140.4102 MiB。随后诊断运行
`artifacts/butano-battle-campaign-route-s45-complete-20260727-04/progress.json`
在断言前记录到实际首名参与者结果为 `150 mission / 100 battle / 0 bonus / 250 total`。
根因不是 mGBA 内存泄漏，而是通用路线让鸣人完成最后击倒，却仍断言原版小樱击倒路线中
鸣人的 `0 battle / 150 total`；Lua 断言退出后 mGBA 继续空转，最终才触发内存守卫。

驱动已改为通过真实战前配装 UI 卸下旧忍具并装备忍具 1，然后按角色、动作 ID 和动作
来源依次验证十字手里剑、佐助动作 16 的单独施术分支，并在回合奖励窗口后只允许小樱
完成最后击倒。成功证据：

- `artifacts/butano-battle-campaign-route-s45-complete-20260727-05/audit.json`
- frame 5402 / round 11 / phase complete；
- `cross_shuriken_verified=1`、`sasuke_fire_verified=1`、
  `sakura_finisher_verified=1`；
- 首名参与者鸣人为 `150 + 0 + 0 = 150`，最终 LV3/EXP275/TP2；
- 忍具 1 的装备槽与库存均为 0；
- scenario 46，SRAM generation 6 / verified 1；
- controller/player error 均为 0；
- guard 正常由 success marker 完成，峰值 RSS 120.3046875 MiB；
- ROM SHA-256：
  `f76c36ba28728e8fe05071e0812b315492d735d2022377a1a4fc09c64b6abab5`；
- SAV SHA-256：
  `ff9f84eb441ec5c8015d634e113ce3b321cff6f675c9dcb702857a8fbd00ea27`。

第二个独立 mGBA 进程复制该 SAV 后冷启动：

- `artifacts/butano-battle-campaign-route-s46-cold-20260727-01/audit.json`
- scenario 46 / battle 9 / round 1 / phase unit selection；
- active units 8，load generation 6，`load_used_default=0`；
- controller/player error 均为 0，`battle-entry.png` 为可见战场。

这签发 scenario 45 的 ROM 战斗、保存与 scenario 46 入口，不自动签发 scenario 46 的
完整胜利或完整 Goal。
