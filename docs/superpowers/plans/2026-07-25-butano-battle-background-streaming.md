# Butano 战斗背景分块流送实施计划

**Goal:** 用 ROM row 11 的 544×480 战场实现可复用的 512px 重叠分块生成和双向背景流送，
证明大地图不需要复制战斗 FSM 或复用错误背景。

**Architecture:** Python 生成器产出固定 512×512 分块与 manifest；无 Butano 依赖的
`battle_background_stream` 只根据 map-space camera center 选择分块；通用 renderer 用
`regular_bg_ptr::set_item()` 释放旧 BG 后切换资源，并按 origin 对齐世界坐标。

**Tech Stack:** Python/Pillow、C++20 固定数组、Butano regular BG、宿主测试、Docker ARM、
静音 mGBA、资源守卫。

## 约束

- 严格 RED → GREEN → REFACTOR。
- 分块像素和 palette 只来自对应 ROM row。
- 不创建 battle 11 专用领域 FSM，不同时常驻两份大 BG。
- 不用截图、缩放或其他关卡背景遮掩 512px 边界。
- 不自动提交、暂存或推送。

### Task 1：分块资源生成

**Files:**
- Modify: `tools/generate_butano_battle_runtime_assets.py`
- Modify: `tests/test_generate_butano_battle_runtime_assets.py`
- Create: `butano-sequel/graphics/battle_11_map_chunk_0.bmp/.json`
- Create: `butano-sequel/graphics/battle_11_map_chunk_1.bmp/.json`
- Create: `butano-sequel/graphics/battle_11_map_chunks.json`

- [x] 写 battle 11 两块、origin、重叠像素和 manifest 的失败测试。
- [x] 确认 RED 来自现有生成器拒绝超过 512px。
- [x] 实现通用 origin 规划与分块生成，保持单块 API 兼容。
- [x] 生成生产资产并确认测试 GREEN。

### Task 2：流送状态机

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_background_stream.h`
- Create: `butano-sequel/game/tests/test_battle_background_stream.cpp`

- [x] 先写 prepare、`0→1→0`、hysteresis、非法缺口的失败测试。
- [x] 确认 RED 来自缺少状态机。
- [x] 实现固定容量、无堆分配的相机分块选择器。
- [x] 运行定向及全部宿主 C++ 测试。

### Task 3：通用 renderer 与 battle 11

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/game/src/scenario_43_scene.cpp`
- Modify: `tests/test_butano_build.py`

- [x] 先写 wiring RED：多分块配置、`set_item()`、battle 11 入口和 chunk telemetry。
- [x] 把部署与战斗 camera 都接到同一背景流送 helper。
- [x] 新增 `run_battle_11_scene()`，battle 9 SELECT 串入；领域仍使用共享 controller。
- [x] 确认 Python wiring GREEN。

### Task 4：ROM 运行验收

**Files:**
- Create: `tools/butano/mgba_battle_11_background_stream.lua`
- Create: 对应 Python 脚本测试
- Modify: 架构文档、领域记录、路线图和工具说明

- [x] 用遥测驱动 battle 11 部署和 cursor，捕获 chunk `0→1→0`，不按固定帧盲发输入。
- [x] 受守卫 ARM 构建，核对资源、ROM 与 section。
- [x] 静音 mGBA 跑 battle 11，并回归 battle 9、43、41。
- [x] 保存唯一 manifest/audit/截图/哈希，`git diff --check`，复核 active Goal。
