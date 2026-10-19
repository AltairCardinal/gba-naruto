# Butano 战斗单位选择与地图深度修复（2026-07-29）

## 现象

人工验收 scenario 49 / battle 14 时出现两个可见问题：

1. 鸣人与木叶丸等纵向相邻单位发生图像重叠时，较靠下的单位没有稳定遮挡较靠上的
   单位；
2. 第二回合进入单位选择后，方向键可把光标移到空格，随后按 A 返回
   `CANNOT SELECT`。失败提示又固定停留 60 帧，即使后续输入成功也不立即消失，造成
   “不管点什么都失败”的观感。

## 运行日志归因

人工观察器产物
`artifacts/butano-battle-manual-observer-20260729-001141/manual-battle-trace.jsonl`
共有 1460 条有效记录。第二回合状态为 player side / `unit_selection`：

- 光标曾离开鸣人所在格并落到空格，A 返回 controller `invalid_input`；
- 顶层按 B 返回 `invalid_phase`；
- 光标回到鸣人格后，记录中两次成功从 phase 1 `unit_selection` 进入 phase 2
  `move_selection`。

因此这不是第二回合领域状态机锁死。根因是单位选择层仍暴露了自由地图游标，以及错误
提示生命周期与输入成功状态脱节。

## 修复设计

### 单位选择层

`unit_selection` 只负责选择本回合仍可行动的玩家控制单位：

- 方向键调用已有 `cycle_roster_unit` 链路，在合法单位之间循环；
- 游标始终同步到被选单位坐标；
- A 进入该单位的移动层；
- 顶层 B 为无副作用成功，不再制造 `CANNOT SELECT`；
- `target_selection` 继续保留自由地图游标，避免把选目标流程错误收窄为 roster。

该设计没有新增第二套单位查找或回合状态；它复用 controller 已有的
`cycle_unit`、runtime roster 过滤和 move flow。

### 错误提示生命周期

`battle_ui_rejection_latch` 统一管理失败反馈：

- 失败输入显示 60 帧；
- 无输入时正常倒计时；
- 任一后续成功输入立即清除；
- 仅重绘 UI，不改领域状态和遥测错误码。

### 地图单位深度

所有地图单位组件按当前可见地图 Y 计算 z-order：

```text
z_order = -visual_y
```

Butano 的较小 z-order 后绘制，因此地图位置越靠下，单位越靠前。深度使用
`battle_map_visual_position` 的结果，所以移动预览中的单位也随当前位置更新层级，而
不是只按行动前坐标排序。决斗演出保持独立的固定深度。

scenario 49 最多会同时显示基础单位和召唤单位；为容纳实际地图深度、游标和 HUD 的不同
排序层，`BN_CFG_SPRITES_MAX_SORT_LAYERS` 提升到 32。

## TDD 与验证

红测分别确认：

- 第二回合方向输入最初不会选中下一个合法单位；
- 顶层 B 最初返回失败；
- 地图深度投影函数最初不存在；
- 成功输入最初不会清除仍在显示的失败提示；
- runtime 最初没有把可见地图位置写入单位 sprite z-order；
- 人工观察器最初仍启动旧验收 ROM，而不是当前构建。

绿测与回归：

- 7 个相关 C++ 宿主测试以
  `clang++ -std=c++20 -Wall -Wextra -Werror` 编译执行通过；
  guard 为
  `artifacts/butano-battle-ui-flow-depth-20260729-01/host-tests-guard.json`；
- 36 项 UI wiring、遥测协议、Lua 路线和观察器 Python 测试通过；
- Lua 语法、POSIX shell 语法、直接/`sh` 两种观察器 `--check` 均通过；
- 固定 Docker/devkitARM 构建通过，guard 为
  `artifacts/butano-battle-ui-flow-depth-20260729-01/build-guard-02.json`；
- 当前 ROM 从 generation 8 的 scenario 49 存档开始，在真实 mGBA 中完成九回合、
  五名敌人结算、generation 9 verified save 并进入 scenario 50。第二回合依次出现
  `unit_selection → move_selection → command_selection`，最终 controller/player
  error 均为 0。运行目录：
  `artifacts/butano-battle-ui-flow-depth-runtime-20260729-01/`。

既有 `test_battle_campaign_scenario_49.cpp` 没有作为本次通过项：它的测试辅助函数
`set_cursor` 固定先横向再纵向走到目标，当前在 move selection 从 `(9,14)` 向
`(8,13)` 移动时先撞到不可进入格并触发断言。失败发生在测试路径生成器，不在本次修改的
unit selection 分支；同一 generated map 的 mGBA 路线使用合法逐格路径并完成整场。
该旧测试辅助器仍应另行改成根据地图生成路径，当前不得把它记为通过。

本次运行哈希：

- ROM：
  `b3e02cbba75ee3a66357be70fb0c06aeb98330fe4c2c54b5d013e21d7e0576fe`
- ELF：
  `31014feab37ab060cd1c0f3146ae2e0b16e0b0a48e6a7e3ea829c6e07382bd32`
- 输入 SAV：
  `3f473ececd31485800c1d907ca7a9b97350fc74f354ffb5a9032ce349a9dbc88`
- telemetry：battle `0x020227dc`，campaign `0x0200820c`

## 验收边界

- 自动路线证明当前 ROM 能稳定通过第二回合并完成整场战斗；
- 深度函数、移动预览 wiring 和排序层容量已有测试与 ARM 构建覆盖；
- 单位重叠的最终像素观感仍保留给人工验收，因为自动路线不应为了制造特定重叠而改写
  单位坐标；
- 本次真实 mGBA 路线显式静音，只签发 UI/流程，不签发音频。
