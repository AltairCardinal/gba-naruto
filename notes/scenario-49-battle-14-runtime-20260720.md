# 演习场剧情与 battle 14 运行时记录（2026-07-20）

## 入口与任务边界

- 从 `artifacts/runtime-checkpoints/scenario-48-post-academy-world-map.ss9` 选择“演习场”，
  推进 60 页剧情后进入任务菜单。该菜单包含队伍状态、装备、查看地图、任务出发、术属性与
  好感等入口；选择“任务出发”并确认后进入部署阶段。
- 部署确认后的战斗控制区 `0x02026804..0x0202680B = 00 0e 00 00 00 00 00 00`，所以实际
  **battle ID 为 14 (`0x0E`)**。
- 玩家槽 1..3 为 Naruto/Sasuke/Sakura，入口等级和 HP 为 `LV5/138`、`LV4/104`、
  `LV5/110`。槽 4 是 character 30、HP 40 的护送单位；槽 5..9 是 character 55、
  LV5、HP 25 的五名敌人。
- 任务菜单正式恢复点为
  `artifacts/runtime-checkpoints/scenario-49-post-training-task-menu.ss9`，SHA-256
  `365e15623485785bd95e5509355ca466c77b0b3e8b7e132cb8f5f9a11b687c5b`。600 帧零输入
  run `55c0a1ed4f11d2c0e8b1920764dae467` 成功，峰值 owned-tree RSS 51.9375 MiB，
  `zero_input_verified=true`、`pgid_clean=true`。
- battle 14 入口正式恢复点为 `artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9`，
  SHA-256 `a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1`。600 帧零输入
  run `77dfdf3729aed54646bd6add9d36804e` 成功，峰值 51.9765625 MiB，
  `zero_input_verified=true`、`pgid_clean=true`。

## 可复现战斗路线

- 第一回合让 Naruto 前移到 `(8,6)`，Sakura 前移到 `(7,14)`，Sasuke 前移到 `(8,13)`；
  五名敌人随后主动接近。第二回合 Sasuke 从 `(8,12)` 使用火遁·豪火球术，预览伤害 60，
  自然击倒槽 9；Naruto 的普通攻击先把槽 8 从 25 HP 打到 9 HP，下一回合再完成击倒。
- 护送单位在第二次敌方阶段从 40 HP 降到 28 HP。随后 Naruto、Sasuke 向中部聚敌，
  依次清除槽 7 和槽 6。Naruto 的三段攻击曾显示 27 点预览，但实际只造成 18 点，槽 5
  `25 -> 7`；因此预览值不能当作击杀证据，必须复核槽位 HP 和 character ID。
- 最后一名 7 HP 敌人攻击护送单位，使其 `28 -> 16 HP`；下一玩家回合 Sasuke 移到
  `(10,4)`，普通攻击预览 13 并自然完成最后击杀。全程没有写内存或跳过战斗逻辑。
- 两次自然击倒后的第四回合恢复点为
  `artifacts/runtime-checkpoints/scenario-49-battle-14-turn4-two-kills.ss9`，SHA-256
  `e8b2a5ee0cc4dfbcf89086c8a5fd8fb2bc9e38b9a7bec83cfcb2e3e2a44de350`。600 帧零输入
  run `e8d33ea25d3b257239317303fba0caca` 成功，峰值 51.9375 MiB，
  `zero_input_verified=true`、`pgid_clean=true`。

## 结算与后续恢复点

- 战后 Naruto `LV5 -> LV6`，体力 `+14`，攻击、防御、敏捷、忍耐各 `+1`；状态页显示
  `EXP 100/325`、HP `152/152`。Sasuke 连升两级、`LV4 -> LV6`，体力合计 `+30`，四项
  战斗属性各合计 `+2`；Sakura `LV5 -> LV6`，体力 `+15`，四项战斗属性各 `+1`。下一战
  入口的三个玩家槽等级均为 6，与结算页相互印证。
- 战后返回同一任务菜单，而不是世界地图。正式恢复点为
  `artifacts/runtime-checkpoints/scenario-49-battle-14-postbattle-task-menu.ss9`，SHA-256
  `8dfca22976fdb741bf8d2521aab8f03e067781c9c2284d003f8bfe6893f76484`。600 帧零输入
  run `0f72e412b2dc5c17fc0e86e9bc251cd7` 成功，峰值 51.953125 MiB，
  `zero_input_verified=true`、`pgid_clean=true`。
- 当前 Naruto 为 LV6，尚未达到 levels 第一个 type-4 row 的 LV8 门槛。后续从战后任务
  菜单直接开始下一自然任务，不再重放演习场剧情或 battle 14。

## 资源守卫事实

- 所有 mGBA 运行均经 heavy lock 串行执行；成功 run 的 owned-tree RSS 稳定在约 52 MiB，
  且 `pgid_clean=true`。
- 第一次等待 1200 帧时把 idle timeout 设为 15 秒，早于约 20 秒的预期运行时间，守卫以
  `idle-timeout/124` 熔断并清理 owned process group；失败证据保留在
  `build/scenario-49-battle-14-route-20260720/enemy-phase-wait/guard.json`。后续独立 run 将
  idle timeout 调到 35 秒后成功。该事件不是 mGBA 崩溃或内存异常。
