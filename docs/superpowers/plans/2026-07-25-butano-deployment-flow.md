# Butano 通用部署确认流程实施计划

**Goal:** 按原作录屏恢复“逐个确认场上单位 → 显示开始 → 进入玩家回合”的部署阶段，并让固定编队与 `0xFA..0xFF` 动态占位编队共用同一领域流程。

**Architecture:** 新增不持有 Butano 对象的 `battle_deployment_flow`。它只读取
`battle_scenario_definition` 和 `battle_scenario_load_policy`，复用场景加载器的角色解析，
输出当前确认单位、格点、阵营和阶段；可见场景仅把 A/B 转为 confirm/cancel，完成后才加载
`battle_scene_controller`。部署不写 `BattleSession`，取消不会产生半套编队。

**Tech Stack:** C++20 固定数组、Butano/ARM GBA、宿主 `g++`、Python wiring 测试、静音 mGBA。

## 约束

- 遵循 RED → GREEN → REFACTOR。
- 不在表现层解析 selector，不复制 `0xFF - selector` 规则。
- 固定编队同样经过逐单位确认；动态占位必须有显式策略绑定。
- 无效 variant、未绑定角色或非法角色在控制器创建前失败。
- 不自动提交、暂存或推送。

### Task 1：共享角色解析与部署领域流程

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_scenario_loader.h`
- Create: `butano-sequel/game/include/konoha/battle_deployment_flow.h`
- Create: `butano-sequel/game/tests/test_battle_deployment_flow.cpp`

- [x] 写失败测试：battle 9 依次暴露 8 个单位，随后进入 start confirmation；B 可退回；battle 32 未绑定失败，绑定后解析六个占位角色。
- [x] 确认 RED：缺少 `battle_deployment_flow.h`。
- [x] 抽取加载器共享 selector 解析，并实现固定容量部署状态机。
- [x] 确认 GREEN，并回归场景加载器测试。

### Task 2：通用可见场景接线

**Files:**
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Modify: `tests/test_butano_build.py`

- [x] 写失败 wiring 测试：控制器 `start()` 前必须完成 deployment flow；禁止 scene 自行解析 selector。
- [x] 确认 RED。
- [x] 增加部署确认 UI、光标/相机跟随与遥测阶段；完成后才启动共享控制器。
- [x] 确认 GREEN。

### Task 3：运行时回归与持久证据

**Files:**
- Modify: `tools/butano/mgba_battle_09_character_actions.lua`
- Modify: `tools/butano/mgba_scenario_43_runtime.lua`
- Modify: 对应 Python 脚本测试
- Modify: 架构文档、领域记录、路线图和工具说明

- [x] 更新状态驱动脚本，逐个确认部署单位和“开始”，不按固定帧盲发输入。
- [x] 运行 61+ 宿主测试、Python 接线/脚本测试和 Docker ARM 构建。
- [x] 静音 mGBA 复跑 battle 9、scenario 43、scenario 41，保存唯一证据。
- [x] `git diff --check`，复核 active Goal 与剩余边界。
