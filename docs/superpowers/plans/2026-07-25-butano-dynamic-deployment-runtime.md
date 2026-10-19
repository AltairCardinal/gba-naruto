# Butano 动态部署运行时实施计划

**Goal:** 删除可见场景的 fixed-roster-only 门禁，把章节提供的部署队伍贯穿部署预览和最终
session，同时保持所有固定编队路线。

## Task 1：公开请求契约

- [x] 先写 source wiring RED，要求 request 持有 `battle_scenario_load_policy`。
- [x] 在 `battle_runtime_scene.h` 定义 request 与通用入口。
- [x] renderer 只接受非空 content，并把 request policy 同时交给 preview/load。

## Task 2：动态集成夹具

- [x] 添加明确命名的 battle 32 deployment fixture，不冒充正式章节。
- [x] 将其追加到既有开发链末尾，不改变未按 SELECT 的现有路线。
- [x] 编写状态驱动 mGBA 路线，验证 6 个活动单位与 round 2。

## Task 3：回归与持久记录

- [x] 运行宿主 C++、相关 Python、ARM 构建。
- [x] 回归 battle 9/11/43 与 scenario 41。
- [x] 更新架构、领域记录、路线图和工具说明。
- [x] `git diff --check`，复核 active Goal；不提交、不暂存、不推送。

## 完成证据

- wiring RED：
  `build/resource-guard/butano-dynamic-deployment-wiring-red-20260725-79.json`；
- 最终 ARM：
  `build/resource-guard/butano-dynamic-deployment-arm-build-20260725-82.json`；
- 65 个宿主 C++：
  `build/resource-guard/butano-dynamic-deployment-host-all-final-20260725-90.json`；
- 109 项相关 Python（1 skip）：
  `build/resource-guard/butano-dynamic-deployment-python-focused-final-20260725-92.json`；
- 动态 battle 32：
  `artifacts/butano-dynamic-deployment-b32-20260725-57/`，部署
  `[1,2,3,35,35,35]`、6 个活动单位、第 1392 帧 round 2；
- 固定路线：
  `artifacts/butano-dynamic-deployment-regression-b11-20260725-58/`、
  `artifacts/butano-dynamic-deployment-regression-b09-20260725-59/`、
  `artifacts/butano-dynamic-deployment-regression-s43-20260725-60/`、
  `artifacts/butano-dynamic-deployment-regression-s41-20260725-61/`。

首个动态 mGBA 运行
`artifacts/butano-dynamic-deployment-b32-20260725-56/` 在第三名 AI 前停住：第二名 AI
把空格移动术目标选在 ROM 全封闭格 `(12,13)`，导致下一次 occupancy 重建失败。该运行已被
`...-57/` 取代，不用于验收。修复后 AI 规划和玩家空格目标都拒绝 cost 0、全封闭或已占用格。

最终 ROM 为 6,923,076 字节，SHA-256
`209c095031df613576a2c066f71b32ead5e60be72513ec6ea8b158ad0bcfefea`；
ELF SHA-256
`2258f62beb36c1d4b84c85d01388a8092a967e04d3266caf54f343e757cc8065`。
