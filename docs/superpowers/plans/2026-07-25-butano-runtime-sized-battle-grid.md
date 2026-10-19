# Butano 运行时尺寸战斗网格实施计划

**Goal:** 用单一 23×32 固定容量控制器安全装载全部 47 张原作逻辑地图，消除按地图尺寸
复制控制器与回合流程的架构瓶颈。

**Architecture:** `grid_map` 的模板宽高改为存储容量，对象保存运行时活动宽高；
map loader 以定义宽度读取内容、以容量宽度存储。所有移动边界统一经过 `contains()`。
可见场景只持有一个共享容量控制器。视觉地图资源和大地图流送不在本里程碑冒充完成。

**Tech Stack:** C++20 固定数组、Butano/ARM GBA、宿主 `g++`、Python wiring 测试、
静音 mGBA、资源守卫。

## 约束

- 严格 RED → GREEN → REFACTOR。
- 不使用堆分配，不把大 workspace 放回 IWRAM 栈。
- 不复制 22 套模板实例，不为无视觉资源的关卡复用错误背景。
- 复用现有 map loader、controller、scenario loader、content catalog 和 mGBA 遥测。
- 不自动提交、暂存或推送。

### Task 1：活动边界与通用地图装载

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_runtime_grid.h`
- Modify: `butano-sequel/game/include/konoha/grid_pathfinder.h`
- Modify: `butano-sequel/game/include/konoha/battle_map_loader.h`
- Create: `butano-sequel/game/tests/test_battle_runtime_grid.cpp`

- [x] 写失败测试：23×32 容量装载 9×22 与 16×32 地图，padding 不可访问，非法尺寸事务失败，
  寻路不能越过活动边界。
- [x] 确认 RED 来自缺少活动尺寸能力/共享容量定义。
- [x] 最小实现运行时活动边界和容量型 materializer。
- [x] 确认 GREEN，并回归既有 grid/map loader 测试。

### Task 2：全目录控制器证明

**Files:**
- Modify: `butano-sequel/game/tests/test_battle_runtime_grid.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_scene_controller.h`
- Modify: host test build wiring

- [x] 测试迭代 47 张地图与全部非空 variant；动态占位提供显式角色绑定。
- [x] 修复 cursor、AI 搜索边界等仍绕过 `contains()` 的编译期边界。
- [x] 证明同一 `battle_runtime_controller` 可重复装载全部可玩/部署 variant。
- [x] 运行全部宿主测试，保留测试数量与资源守卫证据。

### Task 3：可见运行时迁移

**Files:**
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `tests/test_butano_build.py`

- [x] 先写失败 wiring 测试：禁止 `run_visible_battle_scene<...>` 和尺寸专用 controller。
- [x] 把 battle 9、battle 43 迁移到同一个 EWRAM `battle_runtime_controller`。
- [x] 保留各自 ROM 背景、像素相机边界、部署与遥测行为。
- [x] 确认 wiring 与相关 Python 测试通过。

### Task 4：ARM 与运行时回归

**Files:**
- Modify: 架构文档、领域记录、路线图和工具说明

- [x] 受守卫 ARM 构建，核对 ROM、IWRAM/EWRAM section 和 warning/error。
- [x] 静音 mGBA 重跑 battle 9、battle 43、scenario 41，核对部署、round 2、活动单位和画面。
- [x] 保存唯一证据目录、manifest、ROM/ELF 哈希和失败实验。
- [x] `git diff --check`，复核 Goal 仍为 active，并记录下一里程碑为视觉地图流送。
