# Butano Battle Presentation Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从原 ROM 提取并验证全 47 场战斗表现脚本控制图，再把已闭合命令接入通用 Butano 战斗 controller。

**Architecture:** 先建立哈希绑定的只读 selector-builder/presentation-case 内容目录，再实现固定容量的脚本运行时。脚本只发布表现命令和强类型章节事件，不能直接修改 `battle_session`。

**Tech Stack:** Python 3 标准库、JSON、C++23、Butano 21.7.1、宿主测试、Docker ARM 构建、mGBA Lua。

## Global Constraints

- 所有行为变化必须按红、绿、重构顺序实施。
- 不复用整屏截图作为交互实现。
- 不新增 `battle_id == 41` 的流程分支。
- 未闭合 opcode 和条件语义必须失败关闭。
- 不自动提交、暂存或推送。

---

### Task 1: 哈希绑定的战斗脚本控制图

**Files:**
- Create: `tools/analyze_battle_presentation_scripts.py`
- Create: `tests/test_analyze_battle_presentation_scripts.py`
- Create: `sequel/content/battle-presentation-scripts/bank.json`

**Interfaces:**
- Produces: `build_battle_presentation_manifest(rom_path) -> dict`
- Produces: per-battle `selector_builder`, `reachable_selector_sequences`, `presentation_cases`

- [x] **Step 1: 写失败测试**

测试两张 47 项表、entry 0/1–46、控制 opcode 集、battle 41 根地址、可达 selector 序列和两个 presentation case roots。

- [x] **Step 2: 验证红灯**

Run: `python3 -m unittest tests.test_analyze_battle_presentation_scripts -v`

Expected: FAIL，原因是分析模块尚不存在。

- [x] **Step 3: 实现最小分析器**

实现 ROM/函数/表哈希门禁、u32 指针校验、`0x00/0x07/0x32..0x39` 控制图解析、
selector 路径枚举和 presentation case 解析。

- [x] **Step 4: 验证绿灯并生成 bank**

Run: `python3 -m unittest tests.test_analyze_battle_presentation_scripts -v`

Run: `python3 tools/analyze_battle_presentation_scripts.py rom/base.gba --output sequel/content/battle-presentation-scripts/bank.json`

Expected: PASS；bank 生成确定性一致。

### Task 2: 闭合实际表现 payload 指令

**Files:**
- Modify: `tools/analyze_battle_presentation_scripts.py`
- Modify: `tests/test_analyze_battle_presentation_scripts.py`
- Modify: `sequel/content/battle-presentation-scripts/bank.json`
- Create: `notes/battle-presentation-script-bindings-20260725.json`

**Interfaces:**
- Produces: typed command records with raw operands, branch/fallthrough, evidence and source address.

- [x] **Step 1: 按解释器 handler 为实际 opcode 写失败测试**
- [x] **Step 2: 验证每个失败来自缺失的长度或语义**
- [x] **Step 3: 逐个实现已闭合 handler，未知 handler 保留 raw 并拒绝可玩生成**
- [x] **Step 4: 对 battle 41 和另一场 battle 生成完整可达命令图**
- [x] **Step 5: 运行分析器、确定性和损坏输入测试**

### Task 3: 固定容量 Butano 内容生成

**Files:**
- Create: `tools/generate_butano_battle_presentation_content.py`
- Create: `tests/test_generate_butano_battle_presentation_content.py`
- Create: `butano-sequel/game/include/konoha/battle_presentation_content.h`
- Create: `butano-sequel/game/include/konoha/generated_battle_presentation_content.h`

**Interfaces:**
- Produces: `battle_presentation_definition_for(battle_id, variant)`

- [x] **Step 1: 写非法地址、未知 opcode、容量溢出的失败测试**
- [x] **Step 2: 验证红灯**
- [x] **Step 3: 生成固定容量定义与编译期目录校验**
- [x] **Step 4: 验证生成器确定性和宿主 C++ 内容查询**

### Task 4: 通用脚本执行器与 controller 阻塞

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_presentation_script.h`
- Create: `butano-sequel/game/tests/test_battle_presentation_script.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_scene_controller.h`
- Modify: `butano-sequel/game/tests/test_battle_scene_controller.cpp`

**Interfaces:**
- Produces: `battle_presentation_script_snapshot`
- Consumes: `battle_presentation_definition`
- Publishes: typed presentation commands only

- [x] **Step 1: 写脚本阻塞、单页推进、完成恢复、重复确认幂等测试**
- [x] **Step 2: 验证红灯**
- [x] **Step 3: 实现固定容量 cursor/private-variable 状态**
- [x] **Step 4: 接入 controller start/round/side trigger**
- [x] **Step 5: 重构并重跑领域与 controller 测试**

### Task 5: 可见表现、跨关卡和运行时验收

**Files:**
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Create: `butano-sequel/game/include/konoha/battle_presentation_portrait_renderer.h`
- Create: `butano-sequel/game/tests/test_battle_presentation_portrait_renderer.cpp`
- Create: `tools/generate_butano_battle_portrait_content.py`
- Create: `tests/test_generate_butano_battle_portrait_content.py`
- Create/Modify: battle 41/43 mGBA Lua and Python wiring tests
- Modify: `docs/sequel-roadmap.md`
- Modify: `tools/README.md`

**Interfaces:**
- Consumes: controller script snapshot
- Produces: visible dialogue/portrait/cue rendering and telemetry

- [x] **Step 1: 写能暴露按键穿透、空黑屏和错 battle 内容的失败测试**
- [x] **Step 2: 验证红灯**
- [x] **Step 3: 实现结构化窗口/头像/文本 renderer**
- [x] **Step 4: battle 41 与第二场 battle 共用同一 runtime 验收**
- [x] **Step 5: 运行宿主 C++、Python、ARM、mGBA、`git diff --check`**
- [x] **Step 6: 记录运行 ID、ROM/ELF 哈希、输入与 telemetry manifest**
