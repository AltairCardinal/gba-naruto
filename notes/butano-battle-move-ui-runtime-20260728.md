# Butano 战斗移动预览运行时修复（2026-07-28）

## 用户可见故障

玩家选中单位进入 `MOVE` 后，方向键只移动光标，角色仍停在原格，界面也不显示目的地或
移动费用。只有进入后续行动并最终提交事务时，领域位置才变化，因此从玩家视角看
“移动没有用”。

## 根因

移动领域本身已有事务草稿：

- `battle_session::preview_move()` 保存 `preview_position`，不立即改写单位权威坐标；
- 选择朝向并完成行动时才提交草稿；
- 取消行动可回滚到原格。

缺失发生在场景 wiring：

1. `battle_scene_controller::move_cursor()` 只改 `_cursor`，没有在每次合法方向输入后调用
   `preview_move()`；
2. 地图单位 renderer 始终读取 `unit.position`，没有投影事务草稿；
3. `move_selection` 只有静态提示，没有显示当前目的地和路径费用。

此外，指令菜单的 `MOVE` 还有一个独立门槛错误：`reopen_move_selection()` 要求草稿先前
必须已经离开原格。因此玩家若先在原地确认，再从指令菜单选择 `MOVE`，菜单项会直接返回
`invalid_phase`。这解释了“行动菜单中的 MOVE 没有用”的精确操作路径。

## 架构修复

- 移动阶段每次方向输入先验证新的格点及路径；合法时同时推进光标和移动草稿，非法时
  保持当前合法预览。
- 新增 `battle_map_visual_position()`，只在当前玩家行动事务的可见阶段把所选单位投影
  到 `state.player.move_position`；其他单位和其他阶段继续使用权威坐标。
- UI 模型公开 `move_position` 与 `move_cost`，地图层显示
  `MOVE x,y Ccost` 以及 `A OK / B BACK`。
- `reopen_move_selection()` 只要求当前处于指令菜单和存在有效行动草稿，不再要求玩家
  之前已经移动；原地确认后选择 `MOVE` 也能正常重开。
- A 只确认移动选择并进入指令菜单；权威单位坐标仍在完整行动事务提交时更新。B 取消
  会回到原格，避免表现层提前污染领域状态。

因此 renderer 不拥有移动规则，controller 不直接改绘制坐标，领域事务仍是唯一真相。

## TDD 与集成验证

红测先固定以下行为：

- 合法方向输入会更新 `player.move_position` 和正路径费用；
- 原地确认后从指令菜单选择 `MOVE` 会重新进入移动阶段；
- 预览期间 `unit.position` 保持原值；
- visual projection 返回预览格；
- 回到原格时费用归零；
- UI 模型公开移动提示、目的地和费用；
- ROM 场景必须实际调用移动投影；
- mGBA 路线必须在角色离开原格后采集移动 UI。

绿测结果：

- `test_battle_scene_controller.cpp`
- `test_battle_player_action_flow.cpp`
- `test_battle_encounter_runtime.cpp`
- `test_battle_runtime_scene_gate.cpp`
- `test_battle_ui_model.cpp`
- 29 项相关 Python 契约测试
- `luac -p tools/butano/mgba_battle_campaign_route.lua`

devkitARM 构建证据：

- guard：`artifacts/butano-battle-ui-20260728-01/build-guard-24.json`
- 结果：exit 0，owned tree peak 92.046875 MiB

静音 mGBA 完整战斗证据：

- artifacts：`artifacts/butano-battle-ui-20260728-01/full-runtime-26/`
- 从 scenario 49 / battle 14 的 generation 8 存档开始；
- frame 295 的 `scenario_49-move-menu.json` 证明玩家先原地确认，再从指令菜单选择
  `MOVE`，ROM 实际返回 phase 2；
- 移动截图 `ui-phase-2.png` 只在预览坐标离开权威原格后采集；
- round 9 击败 5 名敌人，影分身、豪火球和友军 AI 均经过正式流程；
- 结算 `125 + 100 + 0 = 225`，save generation 9 verified；
- 最终进入 scenario 50，控制器与玩家错误均为 0；
- guard peak 132.6484375 MiB。

ROM/ELF SHA-256：

- ROM：`d50d06e81194328b803ca7b4f4a944fddfddb59263bb787cd394e8fe4de210c1`
- ELF：`fdd3ef50f7d3a7815709d11f8f4921c638cce6ff84a5e256c45674ee8d4a97f9`

`full-runtime-23` 已被取代：它实际推进到 round 9 并击败 4 名敌人，但旧验收机器人按
横轴优先直线移动，在 `(9,4)` 左侧墙格反复输入。`full-runtime-24` 改为依据同一张
generated map 用 BFS 发送逐格合法方向输入，随后由包含菜单 MOVE 实机探针的最终
`full-runtime-26` 取代；这些路线都没有写 RAM 或绕过 controller。

## 边界

本次签发 scenario 49 的玩家移动预览、取消/确认事务和完整胜利闭环。未新增移动范围
高亮、不可达格专用视觉样式或 scenario 50 之后的关卡内容；WAV 战斗音效仍不在验收范围。

> 2026-07-29 更新：其中“未新增移动范围高亮”已被通用范围/目标投影实现取代。新实现、
> 调色板资源约束和 scenario 41 实机证据见
> `notes/butano-battle-ui-state-projection-20260729.md`。
