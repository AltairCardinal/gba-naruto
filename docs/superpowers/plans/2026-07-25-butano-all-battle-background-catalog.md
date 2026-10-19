# Butano 全战斗背景目录实施计划

**Goal:** 从 ROM 批量生成 47 场/49 块战斗背景和唯一 C++ 查询表，删除通用 renderer 的
逐关背景硬编码。

**Architecture:** 复用 per-map chunk generator 生成总 JSON catalog 与
`generated_battle_background_content.h`；通用场景按 battle ID 同时查询逻辑内容与视觉内容，
验证格数到像素尺寸映射后交给现有 stream。

**Tech Stack:** Python/Pillow、生成 C++、Butano regular BG、宿主/source tests、
Docker ARM、静音 mGBA。

## 约束

- 严格 RED → GREEN → REFACTOR。
- 全部像素/palette/hash 来自对应 ROM row。
- wrapper 不再列具体 BG item、尺寸或 origin。
- 空 variant 不伪造成可玩关卡。
- 不自动提交、暂存或推送。

### Task 1：全量生成器与目录

**Files:**
- Modify: `tools/generate_butano_battle_runtime_assets.py`
- Modify: `tests/test_generate_butano_battle_runtime_assets.py`
- Create: 47 份 map manifest、49 组 BMP/JSON、总 catalog
- Create: `butano-sequel/game/include/konoha/generated_battle_background_content.h`

- [x] 写 47 entry、49 chunk、battle 0/11 origin、尺寸/hash/C++ header 的失败测试。
- [x] 确认 RED 来自缺少批量生成 API。
- [x] 实现确定性批量生成和 C++ item 表。
- [x] 生成生产产物并确认重复生成稳定、测试 GREEN。

### Task 2：renderer 内容查询

**Files:**
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `tests/test_butano_build.py`

- [x] 先写 wiring RED：wrapper 禁止具体 BG item，必须查询 generated background entry。
- [x] 运行时复制基础 config，再从 battle ID 注入背景目录。
- [x] 验证 background/scenario battle ID 与格数→像素尺寸映射。
- [x] battle 9/11/43 wrapper 仅保留 ID、variant、title 和流程 flags。

### Task 3：资源与运行时验收

**Files:**
- Modify: 架构文档、领域记录、路线图、工具说明

- [x] 运行全部宿主 C++、Python 生成/wiring/research tests。
- [x] 受守卫 ARM 构建，记录 49 BG converter、ROM 大小、section 和 hash。
- [x] 静音 mGBA 回归 battle 11 `0→1→0`、battle 9、43、41。
- [x] 保存证据，`git diff --check`，复核 active Goal 与下一缺口。

## 完成证据

- 生成器 RED：缺少 `generate_all_map_chunks()`；GREEN：
  `build/resource-guard/butano-all-backgrounds-generator-green-20260725-66.json`。
- 生产生成：
  `build/resource-guard/butano-all-backgrounds-generate-production-20260725-67.json`，
  总目录为 `butano-sequel/graphics/battle_background_catalog.json`。
- ARM 首次 RED：
  `build/resource-guard/butano-all-backgrounds-arm-build-20260725-68.json`，准确暴露
  background content 与 stream 同名；GREEN：
  `build/resource-guard/butano-all-backgrounds-arm-build-20260725-69.json`。
- 64 个宿主 C++ 程序：
  `build/resource-guard/butano-all-backgrounds-host-all-20260725-74.json`。
- 106 项相关 Python 测试（1 skip）：
  `build/resource-guard/butano-all-backgrounds-python-focused-final-20260725-78.json`。
- 静音 mGBA：
  `artifacts/butano-all-backgrounds-b11-20260725-52/`、
  `artifacts/butano-all-backgrounds-b09-20260725-53/`、
  `artifacts/butano-all-backgrounds-s43-20260725-54/`、
  `artifacts/butano-all-backgrounds-s41-20260725-55/`。
- 最终 ROM 为 6,921,928 字节，SHA-256
  `f5c79ffe8616bbeaea87ba36519abf8f9dcfff84fef5ca398daf62b7e9b127cc`；
  ELF SHA-256
  `cef0f451d03e80b05ab53021ab4948e767bd4c02f4aa250e2e60124c53710ee1`。

全库 Python discovery 共运行 1,012 项，得到 1 个既有语义文案失败、3 个因历史 PNG/ss9
原始证据未保留而报错、18 个跳过；完整归因日志为
`build/test-results/butano-all-backgrounds-python-all-20260725-76.log`。这些失败不经过
本次生成器、目录、renderer 或 mGBA 路线，不能替代上述相关测试集的 GREEN，也不得被删除
或伪装为通过。
