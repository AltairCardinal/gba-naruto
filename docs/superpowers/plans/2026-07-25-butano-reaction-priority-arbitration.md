# Butano 反应优先级仲裁实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让共享 `battle_action_resolver` 按原 ROM 的固定顺序只选择一个来袭反应，并在未知高优先反应或结算失败时保持 session 与 RNG 零提交。

**Architecture:** 在现有 resolver 内增加只读反应仲裁器，按 `0x04 → 0x0A → 0x09 → 0x10 → 0x16 → 0x19` 查找目标状态。仲裁器只选择，不改 HP、状态或坐标；执行层继续复用写轮眼、替身和火弹 handler。尚未闭合的 `0x04/0x0A/0x09` 返回 `unsupported_effect`，不允许绕到后续已实现反应。

**Tech Stack:** C++20、现有 `BattleSession`/`battle_status_store`/`battle_action_resolver`、系统 Clang、devkitARM、mGBA。

## Global Constraints

- 只实现 `notes/battle-reaction-priority-bindings-20260723.json` 已绑定的选择顺序，不推测未知反应效果。
- 玩家、AI、benchmark 和关卡继续消费同一个 `battle_action_resolver`。
- 所有行为变化先见 RED；失败不得提交 session 或 RNG。
- 战场对象是否阻挡替身落点和 12 候选精确 RNG 权重仍保持未决，不在本计划中猜测。
- 不提交、不推送，不混入工作区其他已有改动。

---

### Task 1: 用领域测试固定唯一反应选择

**Files:**
- Modify: `butano-sequel/game/tests/test_battle_substitution_reaction.cpp`
- Modify: `butano-sequel/game/tests/test_battle_defense_counter.cpp`

**Interfaces:**
- Consumes: `battle_unit_instance::statuses`、`battle_action_resolver::resolve_draft`
- Produces: 多令牌时的唯一选择、低优先令牌保留与无合法替身落点不降级

- [x] **Step 1: 写多令牌优先级失败测试**

为同一目标同时写入 `0x10/0x16/0x19`，执行有效来袭；断言只触发 `0x10`，只消费
`0x10`，`0x16/0x19` 保留，目标不位移且攻击者不承受反击。

- [x] **Step 2: 写未知高优先反应失败测试**

为目标同时写入 `0x04` 与 `0x10`，执行来袭；断言返回
`action_error::unsupported_effect`，完整 session 不变，随后从同种子 RNG 读取的下一个值
与未执行对照相同。

- [x] **Step 3: 写替身无落点不降级失败测试**

让 `0x16` 与 `0x19` 共存并封闭全部替身候选；断言不触发火弹、不消费任一令牌，来袭走
现有普通伤害边界。

- [x] **Step 4: 运行聚焦测试确认 RED**

Run:

```bash
python3 tools/butano/run_cpp_benchmark_tests.py \
  --root butano-sequel/game \
  test_battle_substitution_reaction test_battle_defense_counter
```

Expected: 至少一个新断言因当前逐分支 fallthrough 或失败 RNG 已推进而失败。

### Task 2: 增加只读仲裁器并保持事务原子性

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_action_system.h`

**Interfaces:**
- Produces: `incoming_reaction_selection`、`_select_incoming_reaction(target)`
- Preserves: `_resolve_incoming_reaction(...)` 仍是唯一反应执行入口

- [x] **Step 1: 添加 ROM 顺序常量与只读选择结果**

选择器依次检查 `0x04, 0x0A, 0x09, 0x10, 0x16, 0x19`，返回第一个存在的 code/slot；
无匹配返回空选择。

- [x] **Step 2: 让执行层只处理已选反应**

`0x10/0x16/0x19` 复用现有实现；`0x04/0x0A/0x09` 设置
`action_error::unsupported_effect` 并停止当前动作。`0x16` 没有合法落点时停止继续查找，
但按现有中性边界让来袭正常结算并保留令牌。

- [x] **Step 3: 让公开 resolve 对 RNG 也使用副本**

`resolve_draft` 与 `resolve_area_draft` 在本地复制 RNG，只有结果成功时才同时提交 session
和 RNG；失败保持调用者 RNG 不变。

- [x] **Step 4: 运行聚焦测试确认 GREEN**

Run:

```bash
python3 tools/butano/run_cpp_benchmark_tests.py \
  --root butano-sequel/game \
  test_battle_substitution_reaction test_battle_defense_counter \
  test_battle_action_system test_battle_linked_resolution
```

Expected: 所有程序 exit 0。

### Task 3: 架构防回流、构建与运行时回归

**Files:**
- Modify: `tests/test_butano_single_battle_domain.py`
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/sequel-roadmap.md`

**Interfaces:**
- Produces: 生产树对完整反应顺序与单一执行入口的结构约束

- [x] **Step 1: 先写失败的 Python 架构测试**

断言生产实现包含完整 ROM 顺序，且多令牌选择通过唯一 `_select_incoming_reaction` 入口，
不再由三个互相 fallthrough 的状态查询决定优先级。

- [x] **Step 2: 运行架构测试确认 RED，再做最小结构调整使其 GREEN**

Run:

```bash
python3 -m unittest -v tests.test_butano_single_battle_domain
```

- [x] **Step 3: 运行全量宿主 C++、相关 Python 与 `git diff --check`**

- [x] **Step 4: 经 `tools/run_guarded.py` 完成 devkitARM 构建**

- [x] **Step 5: 经同一 heavy lock 回归 battle 9、battle 32、scenario 41**

- [x] **Step 6: 记录 RED/GREEN、run ID、ROM/ELF 哈希和未决边界**
