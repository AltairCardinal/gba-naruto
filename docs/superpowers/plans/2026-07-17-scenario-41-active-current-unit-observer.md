---
change: close-scenario-41-battle-runtime
design-doc: docs/superpowers/specs/2026-07-17-scenario-41-active-current-unit-observer-design.md
base-ref: be92eb8
---

# Scenario 41 活动 Current-Unit Observer 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 Scenario 41 player-control 证据的实际 current-unit hook 与参数语义，并用受保护运行证明 fresh ordered 单位事件。

**Architecture:** 保留 PCO1/PCU1，新增独立 PCA1 observer 于 `0x08073BAC`。Evaluator 将 PCO1 解释为 selector 协议，只用 fresh current-unit 的 `argument0` 绑定 WRAM unit diagnostic 的 character id，并以 source hook/event 区分两条 current-unit 路径。

**Tech Stack:** Python `unittest`、Thumb BL/observer wrapper、Node `node:test`、macOS mGBA guarded replay。

## Global Constraints

- 所有功能修改执行 TDD RED → GREEN → 重构；没有失败测试不得写生产代码。
- PCO1 `(9,0,1)` 是 selector accept-mask/mode/flags，不是 slot/affiliation。
- `0x08069DB8` 只消费 `r0` character id；`r1/r2` 不得作为单位属性。
- 新 site 固定为 hook `0x08073BAC`、original `0x08069DB8`、stub `0x0809E900`、scratch `0x0203F0A0`、magic `PCA1`、event `3`。
- 保留现有 `0x080739D8` PCU1/event2；不得替换或弱化原路径覆盖。
- mGBA 必须走 heavy lock/resource guard；每轮 fresh output；不创建 `rom/base.sav`；不追加盲输入。
- 只创建聚焦本地 commit；禁止 push；不提交 raw `build/` 产物。

---

### Task 1: TDD 增加 PCA1 checked observer

**Files:**
- Modify: `tests/test_build_player_control_runtime_probe.py`
- Modify: `tools/build_player_control_runtime_probe.py`

**Interfaces:**
- Consumes: `ObserverSite`、`patch_observer()`、共享 counter `0x0203F040`。
- Produces: `ACTIVE_CURRENT_UNIT_SITE` 与三个 site 的 `OBSERVER_SITES`。

- [x] **Step 1: 写 RED 测试**

在测试中导入并断言以下精确常量，同时扩展 confined-diff 与 fail-closed 测试：

```python
ACTIVE_CURRENT_UNIT_HOOK = 0x08073BAC
ACTIVE_CURRENT_UNIT_ORIGINAL = 0x08069DB8
ACTIVE_CURRENT_UNIT_STUB = 0x0809E900
ACTIVE_CURRENT_UNIT_SCRATCH = 0x0203F0A0
ACTIVE_CURRENT_UNIT_MAGIC = int.from_bytes(b"PCA1", "little")
ACTIVE_CURRENT_UNIT_EVENT = 3
```

测试必须证明 base call 是 `BL 0x08069DB8`、probe call 是 `BL 0x0809E900`，stub 含 scratch/magic/original literal；第三 hook/cave 之外不得新增 changed range；破坏第三 call 或 cave 时分别报 `active-current-unit call-site` / `active-current-unit stub region`。

- [x] **Step 2: 运行 RED**

Run: `python3 -m unittest tests.test_build_player_control_runtime_probe -v`

Expected: FAIL，原因是上述常量/site 尚不存在或第三 call 未 patch。

- [x] **Step 3: 最小 GREEN 实现**

在 builder 中新增精确常量和 site：

```python
ACTIVE_CURRENT_UNIT_SITE = ObserverSite(
    "active-current-unit",
    ACTIVE_CURRENT_UNIT_HOOK,
    ACTIVE_CURRENT_UNIT_ORIGINAL,
    ACTIVE_CURRENT_UNIT_STUB,
    ACTIVE_CURRENT_UNIT_SCRATCH,
    ACTIVE_CURRENT_UNIT_MAGIC,
    ACTIVE_CURRENT_UNIT_EVENT,
)
OBSERVER_SITES = (PLAYER_CONTROL_SITE, CURRENT_UNIT_SITE, ACTIVE_CURRENT_UNIT_SITE)
```

复用既有 loop、overlap guard 和透明 wrapper，不新建第二套 patcher。

- [x] **Step 4: 运行 GREEN 与回归**

Run: `python3 -m unittest tests.test_build_player_control_runtime_probe tests.test_published_call_observer -v`

Expected: 全部 PASS；第三 wrapper machine ABI 与前两处一致。

- [x] **Step 5: 提交**

```bash
git add tests/test_build_player_control_runtime_probe.py tools/build_player_control_runtime_probe.py
git commit -m "fix(re): observe active scenario 41 current unit call"
```

---

### Task 2: TDD 修正 player-control evaluator 语义

**Files:**
- Modify: `play/_scripts/scenario-41-runtime-evidence.test.js`
- Modify: `play/_scripts/scenario-41-runtime-evidence.js`

**Interfaces:**
- Consumes: decoded PCO1 与 PCU1/PCA1 record、WRAM unit diagnostic。
- Produces: `evaluatePlayerControlEvidence(input)` 的 source-aware verified/reason/checks。

- [ ] **Step 1: 写 RED 测试**

把 valid sample 改为：

```javascript
final: {
  player: call(1, 1, { argument0: 9, argument1: 0, argument2: 1, eventCode: 1 }),
  current: call(1, 2, { argument0: 0x31, eventCode: 3 }),
},
currentSourceHook: '0x08073BAC',
controlledSlot: 1,
controlledCharacterId: 0x31,
controlledAffiliation: 0,
controlledUnitFromWram: true,
```

新增拒绝测试：PCO1 protocol 任一字段错误；event2/source 不是 `0x080739D8`；event3/source 不是 `0x08073BAC`；`current.argument0` 与 character id 不同；缺少 WRAM 来源；以及把 PCO1 argument0 当 slot 的旧 sample。

- [ ] **Step 2: 运行 RED**

Run: `node --test play/_scripts/scenario-41-runtime-evidence.test.js`

Expected: FAIL，现有 evaluator 仍错误比较 PCO1 slot/affiliation，且不识别 event3/source。

- [ ] **Step 3: 最小 GREEN 实现**

加入 source/event 映射并替换旧一致性检查：

```javascript
const CURRENT_UNIT_SOURCES = new Map([
  [2, '0x080739D8'],
  [3, '0x08073BAC'],
]);

const selectorProtocolValid = player.argument0 === 9
  && player.argument1 === 0
  && player.argument2 === 1;
const currentSourceValid = CURRENT_UNIT_SOURCES.get(current.eventCode)
  === input.currentSourceHook;
const controlledUnitConsistent = input.controlledUnitFromWram === true
  && controlledDiagnosticValid
  && current.argument0 === input.controlledCharacterId;
```

保留 fresh、sequence order、battle/map/screen、显式输入计划等现有门禁。不要读取 current `argument1/argument2` 作为单位属性。

- [ ] **Step 4: 运行 GREEN 与回归**

Run: `node --test play/_scripts/scenario-41-runtime-evidence.test.js`

Expected: 全部 PASS，包括 uint32 wrap、stale/reversed、输入审计与新增 source/协议测试。

- [ ] **Step 5: 提交**

```bash
git add play/_scripts/scenario-41-runtime-evidence.js play/_scripts/scenario-41-runtime-evidence.test.js
git commit -m "fix(re): bind player control evidence to active unit source"
```

---

### Task 3: 重建 probe 并完成受保护 runtime 复验

**Files:**
- Modify: `docs/superpowers/specs/2026-07-15-scenario-41-battle-runtime-design.md`
- Modify: `docs/superpowers/plans/2026-07-15-scenario-41-battle-runtime.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/tasks.md`（仅验收后勾选）
- Create after acceptance: compact evidence/checkpoint/note files required by OpenSpec 4.1。

**Interfaces:**
- Consumes: Task 1 ROM builder、Task 2 evaluator、accepted controller checkpoint 和已审计短输入链。
- Produces: 四 record baseline、PCO1→PCU1/PCA1 fresh order、unit-object identity binding、可供 OpenSpec 4.2 使用的 player-control checkpoint。

- [ ] **Step 1: 构建并审计 ROM**

Run:

```bash
python3 tools/build_player_control_runtime_probe.py rom/base.gba build/scenario-41-active-current/player-observer.gba
python3 -m unittest tests.test_build_player_control_runtime_probe tests.test_published_call_observer -v
node --test play/_scripts/scenario-41-runtime-evidence.test.js
```

Expected: tests PASS；ROM confined diff 仅三个 checked hooks 与三个 caves；baseline counter、PCO1、PCU1、PCA1 全零。

- [ ] **Step 2: 先做诊断复验**

从旧 PCO1-positive state 只允许在报告明确记录“跨 probe 仅新增未执行 PCA1 patch”的情况下做一次诊断；先零输入验证 task/object/画面，再按静态唯一输入继续。诊断只用于确认 `0x08073BAC` 活性，不得作为最终 canonical evidence。

Expected: PCA1 fresh 时记录 source `0x08073BAC`、event3、sequence 严格晚于 PCO1，且 `argument0` 等于 unit-object character id；未命中则停止并做 GDB 只读 breakpoint，不追加盲输入。

- [ ] **Step 3: 从 canonical checkpoint 重放最终证据**

使用新 ROM 从 `artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9` 重放已审计的零输入/单 A 链；每个可消费边界均先零输入或周期验收。最终 evidence 必须来自同一新 ROM、全零 baseline、fresh PCO1→PCU1/PCA1 顺序和 WRAM unit diagnostic。

- [ ] **Step 4: 验收、持久化与回归**

运行 evaluator、相关 Python/Node tests、`git diff --check`、资源/残留检查。只有 evaluator verified、基础 ROM 对照行为一致且独立 GDB/相邻 PC 复核通过后，才持久化 player-control checkpoint 并勾选 Task 5B Step 1/OpenSpec 4.1；否则保持未完成。

- [ ] **Step 5: 提交**

仅提交 compact evidence、checkpoint、稳定文档和任务勾选，不提交 raw build：

```bash
git add artifacts/runtime-checkpoints/scenario-41-player-turn.ss9 \
  artifacts/runtime-checkpoints/scenario-41-player-control-evidence.json \
  artifacts/runtime-checkpoints/scenario-41-checkpoints.json \
  artifacts/runtime-checkpoints/README.md \
  notes/scenario-41-player-control-runtime-20260715.md \
  docs/superpowers/specs/2026-07-15-scenario-41-battle-runtime-design.md \
  docs/superpowers/plans/2026-07-15-scenario-41-battle-runtime.md \
  openspec/changes/close-scenario-41-battle-runtime/tasks.md
git commit -m "evidence(re): verify scenario 41 active player unit control"
```
