# Butano 单一战斗领域规则源实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax
> for tracking.

**Goal:** 删除生产运行时并存的旧 `ability_resolver`、`apply_effect_chain` 和
`substitution_ready` 规则源，使角色动作、AI 预览、实际结算、benchmark 与后续关卡都只依赖
`ActionDefinition + BattleSession + battle_action_resolver`。

**Architecture:** 随机数生成器从旧 ability 头独立到无业务含义的 `battle_random.h`；
生产消费者继续使用现有内容驱动 resolver。旧规则 API 不保留兼容实现，benchmark 改为调用
真实领域事务，防止另一套简化公式继续存在。Python 架构测试负责阻止旧符号重新进入生产树，
C++ 行为测试负责证明迁移没有减少原子提交、伤害、召唤和替身覆盖。

**Tech Stack:** C++20、固定容量 Butano/GBA 数据结构、Python `unittest`、devkitARM、
mGBA 0.10.5。

## Global Constraints

- 不改变 `ActionDefinition` 生成内容、ROM 已绑定公式或现有运行时输入流程。
- 所有行为变化必须执行 RED → GREEN → REFACTOR。
- `BattleSession` 是唯一可变战斗聚合；表现层和 benchmark 不持有独立 HP/状态规则。
- 保留用户已有未提交改动，不执行自动 commit、stage、push。
- mGBA、ARM 重构建通过 `tools/run_guarded.py` 使用 heavy lock。

---

### Task 1: 锁定生产运行时的单一规则源

**Files:**
- Create: `tests/test_butano_single_battle_domain.py`

**Interfaces:**
- Consumes: `butano-sequel/game/include/konoha/**/*.h`,
  `butano-sequel/game/src/**/*.cpp`
- Produces: 架构门禁，禁止旧 resolver、旧替身布尔和旧 effect chain 回流

- [x] **Step 1: 写失败测试**

```python
class ButanoSingleBattleDomainTest(unittest.TestCase):
    def test_production_tree_has_one_action_resolver(self):
        self.assertFalse((INCLUDE / "battle_abilities.h").exists())
        self.assertFalse((INCLUDE / "battle_effects.h").exists())
        source = "\n".join(path.read_text() for path in production_files())
        for forbidden in (
            "ability_resolver",
            "ability_definition<",
            "apply_effect_chain",
            "substitution_ready",
        ):
            self.assertNotIn(forbidden, source)
        self.assertEqual(source.count("class deterministic_rng"), 1)
```

- [x] **Step 2: 运行红测**

Run:

```bash
python3 -m unittest -v tests.test_butano_single_battle_domain
```

Expected: FAIL，明确指出旧头文件或旧符号仍存在，而不是导入/路径错误。

### Task 2: 独立随机数并迁移生产消费者

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_random.h`
- Modify: `butano-sequel/game/include/konoha/battle_action_system.h`
- Modify: `butano-sequel/game/include/konoha/battle_ai.h`
- Modify: `butano-sequel/game/include/konoha/battle_ai_candidate_score.h`
- Modify: `butano-sequel/game/include/konoha/battle_ai_utility.h`
- Modify: `butano-sequel/game/include/konoha/battle_scene_presentation.h`
- Modify: `butano-sequel/game/include/konoha/battle_session.h`
- Modify: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Delete: `butano-sequel/game/include/konoha/battle_abilities.h`
- Delete: `butano-sequel/game/include/konoha/battle_effects.h`

**Interfaces:**
- Produces:

```cpp
class deterministic_rng
{
public:
    explicit constexpr deterministic_rng(std::uint32_t seed);
    [[nodiscard]] int next_percent();
    [[nodiscard]] int next_u15();
};
```

- [x] **Step 1: 创建无业务规则的 RNG 头并替换 include**
- [x] **Step 2: 删除 `battle_ai::plan(ability_definition*)` 旧重载**
- [x] **Step 3: 删除 `BattleUnitInstance::substitution_ready`、旧 friend 与
  `battle_action_resolver` 中的布尔降级分支**
- [x] **Step 4: 删除未使用的 scenario 旧 effect include 和两个旧规则头**
- [x] **Step 5: 运行架构测试，预期 GREEN**

### Task 3: 把测试与 benchmark 迁移到真实领域事务

**Files:**
- Move: `butano-sequel/game/tests/test_battle_abilities.cpp` →
  `butano-sequel/game/tests/test_battle_domain_single_source.cpp`
- Modify: `butano-sequel/game/tests/test_battle_ai.cpp`
- Modify: `butano-sequel/game/tests/test_production_primitives.cpp`
- Move: `butano-sequel/benchmark/include/konoha_bench/battle_effects.h` →
  `butano-sequel/benchmark/include/konoha_bench/battle_domain.h`
- Modify: `butano-sequel/benchmark/src/self_test.cpp`
- Move: `butano-sequel/benchmark/tests/test_battle_effects.cpp` →
  `butano-sequel/benchmark/tests/test_battle_domain.cpp`

**Interfaces:**
- Consumes: `battle_session`, `action_definition`, `battle_action_resolver`
- Produces: benchmark 直接验证真实成本、伤害与原子失败，不实现自己的公式

- [x] **Step 1: 将旧 AI 单动作测试改为 `action_definition` 入口**
- [x] **Step 2: 将旧 ability 测试改为真实 session 的多 hit 和失败零写，并复用既有召唤测试**
- [x] **Step 3: 将 production primitives 与 benchmark 的 effect 测试改为共享 resolver**
- [x] **Step 4: 运行迁移后的 C++ 测试**

Run:

```bash
python3 tools/butano/run_cpp_benchmark_tests.py \
  --root butano-sequel/game \
  test_battle_domain_single_source test_battle_ai test_production_primitives
python3 tools/butano/run_cpp_benchmark_tests.py \
  test_battle_domain
```

Expected: 所有程序 exit 0，且源码扫描不再出现旧 API。

### Task 4: 持久文档与全链验收

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/sequel-roadmap.md`

- [x] **Step 1: 记录旧双规则源被移除、benchmark 改用真实领域事务**
- [x] **Step 2: 运行 `git diff --check`、全量宿主 C++ 与定向 Python**
- [x] **Step 3: 运行 devkitARM 构建**
- [x] **Step 4: 运行 battle 9、battle 32、scenario 41 静音 mGBA 路线**
- [x] **Step 5: 保存唯一 run ID、摘要、ROM/ELF 哈希和已知失败边界**
