# Butano 完整战斗动作身份目录实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 87 个主动技能与 94 个忍具都拥有可追溯的运行时身份，并让攻击、防御选择器显示真实名称而不是 `TOOL #ID`。

**Architecture:** 继续复用 `battle_action_browser` 和 `battle_defense_browser` 的动作来源、ID 与槽位，不把显示名称写进领域规则。生成器从人工校对身份 overlay 与 ROM 绑定的 `battle-content-catalog` 生成固定 C++ 目录和 UTF-8 sprite font；renderer 只按动作来源查询对应目录。

**Tech Stack:** Python 3、Pillow、C++20 固定数组、Butano UTF-8 sprite font、devkitARM。

## Global Constraints

- 不按动作名称分派效果、成本、目标或 AI；名称只属于表现身份。
- 87 个主动技能继续使用现有 ROM 字节绑定 overlay。
- 94 个忍具必须保持连续 ID 0–93，并关联 `notes/battle-content-catalog-20260723.json` 的 ROM 名称记录。
- 只有自然运行中已辨认的忍具标为 exact；其余名称显示 `?`，不得把攻略关联冒充 ROM 精确校字。
- 所有行为变化执行 RED → GREEN → REFACTOR。
- 不提交、暂存或推送 Git。

---

### Task 1：完整忍具身份输入与生成器

**Files:**
- Create: `sequel/content/battle-config/ninja-tool-identities.json`
- Modify: `tools/generate_butano_battle_identity_content.py`
- Modify: `tests/test_generate_butano_battle_identity_content.py`

**Interfaces:**
- Consumes: 94 条连续忍具身份与 `notes/battle-content-catalog-20260723.json` 的 `ninja_tools[*].name.raw_hex`
- Produces: `content["tools"]`、`battle_ninja_tool_identities`、`battle_ninja_tool_identity(id)`

- [x] **Step 1: 写失败测试**

测试要求工具目录长度为 94、ID 连续，ID 1/2/17/73/93 分别显示十字手里剑、八方手里剑、风魔手里剑、兵粮丸、超万能丸；生成头文件包含 94 项数组和查询函数，字体覆盖全部工具名称。

- [x] **Step 2: 确认 RED**

Run:

```bash
python3 -m unittest tests.test_generate_butano_battle_identity_content
```

Expected: FAIL，`content["tools"]` 尚不存在。

- [x] **Step 3: 最小实现**

增加独立 `_load_ninja_tool_entries`：校验连续 ID、置信度、非空显示名，并逐项确认 ROM catalog 中存在非空名称字节；把 tools 纳入 UTF-8 字符集合、内容头和字体输出。

- [x] **Step 4: 确认 GREEN**

运行生成器更新四个受控输出，再重跑定向测试。

### Task 2：攻击与防御选择器统一身份投影

**Files:**
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/game/tests/test_battle_scene_character_actions.cpp`
- Modify: `tests/test_butano_build.py`

**Interfaces:**
- Consumes: `battle_action_source_kind` / `defense_action_kind`、动作 ID
- Produces: 主动技能与忍具统一显示名；`defense_selection` 显示当前准备动作

- [x] **Step 1: 写失败测试**

C++ 测试要求 `battle_ninja_tool_identity(1/93)` 返回真实名称；source wiring 测试要求 runtime 调用工具身份查询并在防御阶段读取 `selected_defense_kind/id`。

- [x] **Step 2: 确认 RED**

运行 C++ 定向测试与 Python wiring 测试，预期分别因缺失查询函数和 renderer 接线失败。

- [x] **Step 3: 最小实现**

将 `append_action_identity` 改为来源 + ID 接口；主动动作查询 active catalog，忍具查询 tool catalog。攻击菜单和防御菜单共用该接口，保留越界 ID 的明确 fallback。

- [x] **Step 4: 确认 GREEN 并重构**

重跑定向与全部宿主测试，确认领域 resolver、browser 和 session 无名称依赖。

### Task 3：ARM 与持久证据

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/sequel-roadmap.md`

**Interfaces:**
- Produces: 完整动作身份覆盖、置信度边界和验证记录

- [x] **Step 1: ARM 构建**

通过 `tools/run_guarded.py` 执行干净 devkitARM 构建，要求 exit 0 且无 warning/error。

- [x] **Step 2: 静音运行时验证**

从装备十字手里剑的角色进入动作列表，遥测仍以来源/ID/槽位解析，截图显示名称而非编号；自动模拟器保持静音。

- [x] **Step 3: 最终验证与文档**

运行生成器测试、相关 C++/Python 集成测试、`git diff --check`，记录 ROM 哈希及未完成的 AI 防御/资源策略、章节脚本和结果演出边界。
