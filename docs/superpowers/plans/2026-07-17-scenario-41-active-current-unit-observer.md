---
change: close-scenario-41-battle-runtime
design-doc: docs/superpowers/specs/2026-07-17-scenario-41-active-current-unit-observer-design.md
base-ref: be92eb8
---

# Scenario 41 活动 Current-Unit Observer 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 Scenario 41 player-control 证据的实际 current-unit hook 与参数语义，并用受保护运行证明 fresh ordered 单位事件。

**Architecture:** 保留 PCO1/PCU1，新增独立 PCA1 observer 于 `0x08073BAC`。Evaluator 将 PCO1 解释为 selector 协议，把 fresh current-unit 的 `argument0` 解释为 unit slot，并通过 `0x020240C0 + slot * 0x1D4` 绑定到提供 character/affiliation 的同一 WRAM unit record；source hook/event 继续区分两条 current-unit 路径。

**Tech Stack:** Python `unittest`、Thumb BL/observer wrapper、Node `node:test`、macOS mGBA guarded replay。

## Global Constraints

- 所有功能修改执行 TDD RED → GREEN → 重构；没有失败测试不得写生产代码。
- PCO1 `(9,0,1)` 是 selector accept-mask/mode/flags，不是 slot/affiliation。
- `0x08069DB8` 只消费 `r0` 的 unit slot：先截断为 u8，再以 `0x1D4` 为 stride 从 `0x020240C0` 定位 unit record；`r1/r2` 在 callee 内被覆盖，不得作为单位属性。
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

- [x] **Step 1: 写 RED 测试**

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

- [x] **Step 2: 运行 RED**

Run: `node --test play/_scripts/scenario-41-runtime-evidence.test.js`

Expected: FAIL，现有 evaluator 仍错误比较 PCO1 slot/affiliation，且不识别 event3/source。

- [x] **Step 3: 最小 GREEN 实现**

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

- [x] **Step 4: 运行 GREEN 与回归**

Run: `node --test play/_scripts/scenario-41-runtime-evidence.test.js`

Expected: 全部 PASS，包括 uint32 wrap、stale/reversed、输入审计与新增 source/协议测试。

- [x] **Step 5: 提交**

```bash
git add play/_scripts/scenario-41-runtime-evidence.js play/_scripts/scenario-41-runtime-evidence.test.js
git commit -m "fix(re): bind player control evidence to active unit source"
```

---

### Task 2B: TDD 纠正 current-unit slot ABI

运行时 PCA1 `arg0=1` 与 base ROM 数据流共同证实，先前把 `r0` 解释为 character id 的设计错误；
该结果取代 Task 2 中对应的参数语义，但不取代 PCO1 protocol、source/event、fresh/order 或显式输入门禁。

**Files:**
- Modify: `play/_scripts/scenario-41-runtime-evidence.test.js`
- Modify: `play/_scripts/scenario-41-runtime-evidence.js`
- Modify: `docs/superpowers/specs/2026-07-17-scenario-41-active-current-unit-observer-design.md`

**Interfaces:**
- Consumes: fresh PCU1/PCA1 `argument0`、WRAM diagnostic 的 slot/character/affiliation。
- Produces: slot-aware `controlledUnitConsistent`；character/affiliation 仍必须来自该 slot 映射的同一 WRAM record。

- [x] **Step 1: 写并确认 RED**

把 valid sample 的 current `argument0` 改为 `controlledSlot`。新增拒绝测试证明 current slot 不一致会
fail closed，同时 character/affiliation 缺失或越界仍被拒绝；保留 current `r1/r2` 被忽略、PCO1
`(9,0,1)` 和 source/event 的全部既有测试。先运行 focused Node suite，并确认旧实现因仍比较
`controlledCharacterId` 而出现预期语义失败。

- [x] **Step 2: 最小 GREEN 与设计纠错**

将一致性门改为：

```javascript
const controlledUnitConsistent = input.controlledUnitFromWram === true
  && controlledDiagnosticValid
  && current.argument0 === input.controlledSlot;
```

同步设计文档：`0x08073BAA` 从 `0x0202680C+3` 读取 slot；`0x08069DB8` 以
`0x020240C0 + slot * 0x1D4` 定位 WRAM record；character id 按项目既有 runtime unit
解析约定取该 record `+0`，不是 call argument。canonical slot 1 的 `record+0=1`，而
`record+3=13` 是另一字段，不得解释为角色 ID。明确 `r1/r2` 是无关入口寄存器值，wrapper
完整保存/恢复 `r0-r4`。

- [x] **Step 3: GREEN、回归与聚焦提交**

运行 focused Node suite、observer/builder Python suites、`git diff --check`。只提交上述三个文件，
不得修改 runtime 产物、plan/OpenSpec checkbox 或用户文件；提交信息：
`fix(re): bind current unit slot to WRAM record`。

---

### Task 2D: TDD 补齐原生帧时序输入审计

本任务是已批准 player-control evidence 能力中的小型验收场景补齐，不新增 capability，
不改变 observer ABI。现有 evaluator 只接受浏览器 `holdMs`，不能用近似毫秒值替代原生 mGBA
audit 中精确的 `down_frame/up_frame/hold_frames/capture_frame`。

**Files:**
- Modify: `play/_scripts/scenario-41-runtime-evidence.test.js`
- Modify: `play/_scripts/scenario-41-runtime-evidence.js`
- Modify: `docs/superpowers/specs/2026-07-17-scenario-41-active-current-unit-observer-design.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/specs/scenario-41-battle-runtime/spec.md`

- [x] **Step 1: RED — 定义互斥 timing union 与多事件链**

保留 legacy frozen plan item 的 `holdMs`。新增 native frozen plan item：`downFrame > 0`、
`upFrame > downFrame`、`holdFrames === upFrame - downFrame`、`captureFrame > upFrame`。
单项必须恰好属于 legacy 或 native 一种；同一 plan 不允许混合 timing mode。新增三段显式 A 的
native valid sample，并覆盖缺字段、非整数、顺序错误、hold 不一致、legacy/native 混用、event 与
plan mode/字段不一致、额外/缺失/乱序事件的 fail-closed 测试。先运行 focused Node suite，确认旧
实现因缺少 `holdMs` 而 RED。

- [x] **Step 2: GREEN — 最小向后兼容实现**

只扩展 `expectedInputPlanValid()` 与 `inputMatchesPlan()`；legacy `holdMs` 行为与既有失败原因保持
不变。native event 仍必须 `classification=explicit` 且 down/up complete。不得把每个独立 guarded
run 的局部 `captureFrame=80` 错误要求为跨事件递增，也不得接受近似/派生 `holdMs`。

- [x] **Step 3: 文档、回归与聚焦提交**

同步 Design Doc 与 delta spec；运行 focused Node、相关 observer Python suites 和
`git diff --check`。只提交四个允许文件，提交信息：
`fix(re): audit native frame-timed input plans`。

---

### Task 2E: 项目级自动技术决策策略

用户已明确要求：当前 Goal 范围内可逆、向后兼容且不扩张 capability 的技术细节由执行者负责，
不再制造用户确认点。该授权不覆盖归档、push/发布、破坏性或不可逆操作、新 capability、超过
50% 的范围扩张以及 Comet 其他真正硬决策点。

**Files:**
- Modify: `.comet/policy.yaml`
- Modify: `tools/check_comet_project_policy.py`
- Modify: `tests/test_check_comet_project_policy.py`

- [x] **Step 1: RED — 策略 schema 与机器报告**

先写失败测试，要求 exact policy schema 声明自动决策范围和必须询问范围；audit JSON 必须显式
输出两类清单，保存报告验证也必须拒绝缺失或被扩大授权的报告。

- [x] **Step 2: GREEN — 最小策略实现**

扩展严格 parser 期望 schema 与 audit/verify-report，不修改 Comet 插件代码。自动范围只包含
`in-scope-reversible-technical` 和 `backward-compatible-internal`；必须确认范围固定为
`archive/push/publish/destructive/irreversible/new-capability/scope-growth-over-50-percent`。

- [x] **Step 3: 回归与聚焦提交**

运行 policy focused tests、真实仓库 policy audit 和 `git diff --check`。不得修改当前用户已有的
`AGENTS.md` 或 `docs/sequel-roadmap.md`，提交信息：
`fix(comet): enforce automatic in-scope technical decisions`。

---

### Task 2F: 让严格 GDB probe 加载固定输入脚本

Task 4.2 需要在未打 observer 的基础 ROM 上由 GDB 独立命中原始 direct call。现有
`mgba_gdb_probe.py` 只能零输入启动，无法从已接纳的 A 前快照自然推进到目标地址。只增加受限的
重复 `--script PATH` 能力，不开放任意 mGBA 参数或 shell 命令。

**Files:**
- Modify: `tools/mgba_gdb_probe.py`
- Modify: `tests/test_mgba_gdb_probe.py`

- [x] **Step 1: RED — 固定脚本命令与 provenance**

先写失败测试，要求 parser 接受重复 `--script`；`build_mgba_command()` 按给定顺序将每个
`--script PATH` 放在 savestate/ROM 之前；无脚本时命令保持完全兼容。initial/result evidence 必须
记录每个脚本的 path/SHA-256/size，CLI 必须在启动前拒绝缺失或非普通脚本文件。

- [x] **Step 2: GREEN — 最小受限实现**

仅增加 `Path` 类型的重复 `--script` 和脚本 file evidence；不得增加任意 argv、shell、端口或环境
注入接口。运行环境继续只继承父进程，本轮固定 input Lua 所需变量由受守卫的父命令显式提供。

- [x] **Step 3: 回归、审查与聚焦提交**

运行 `tests.test_mgba_gdb_probe`、相关 guard 测试和 `git diff --check`；聚焦提交后由 fresh thorough
reviewer 检查命令顺序、provenance、缺文件 fail-closed 与默认兼容性。提交信息：
`feat(re): load audited scripts in gdb probe`。

---

### Task 2G: TDD 扩展玩家控制 checkpoint 证据组合

现有 ledger 将 `player-control` 写死为 selector `0x08073946` 与旧 PCU call-site
`0x080739D8` 的单一组合；canonical runtime 已独立证明实际行动菜单路径使用新的 PCA direct call
`0x08073BAC`。这是向后兼容的内部验证 schema 扩展，不改变 checkpoint JSON 版本或字段。

**Files:**
- Modify: `tools/runtime_checkpoint_ledger.py`
- Modify: `tests/test_runtime_checkpoint_ledger.py`

- [ ] **Step 1: RED — 定义 selector + current-unit 二选一组合**

先写失败测试，要求 `player-control` 接受 `0x08073946 + 0x080739D8`（legacy PCU）或
`0x08073946 + 0x08073BAC`（canonical PCA）。分别拒绝只有 selector、只有任一 current-unit、
缺 selector、无关地址，以及把两个 current-unit 地址误当作无需 selector 的组合。运行 focused suite，
确认旧实现只在 PCA 正例上因正确原因失败。

- [ ] **Step 2: GREEN — 最小向后兼容 evidence alternatives**

把内部 evidence requirement 表达为可满足的 hook 组合；其他 `movedone/victory/postbattle` 语义保持
完全不变。保持 `schema_version: 1`、JSON 字段和既有错误边界，不放宽非 canonical 地址或未知 evidence。

- [ ] **Step 3: 回归、审查与聚焦提交**

运行 `tests.test_runtime_checkpoint_ledger`、真实 ledger validator 和 `git diff --check`。只提交上述两个
文件；由 fresh thorough reviewer 核验 legacy compatibility、PCA 正例与 selector fail-closed。提交信息：
`fix(re): accept active-current checkpoint evidence`。

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

- [x] **Step 1: 构建并审计 ROM**

Run:

```bash
python3 tools/build_player_control_runtime_probe.py rom/base.gba build/scenario-41-active-current/player-observer.gba
python3 -m unittest tests.test_build_player_control_runtime_probe tests.test_published_call_observer -v
node --test play/_scripts/scenario-41-runtime-evidence.test.js
```

Expected: tests PASS；ROM confined diff 仅三个 checked hooks 与三个 caves；baseline counter、PCO1、PCU1、PCA1 全零。

- [x] **Step 2: 先做诊断复验**

从旧 PCO1-positive state 只允许在报告明确记录“跨 probe 仅新增未执行 PCA1 patch”的情况下做一次诊断；先零输入验证 task/object/画面，再按静态唯一输入继续。诊断只用于确认 `0x08073BAC` 活性，不得作为最终 canonical evidence。

Expected: PCA1 fresh 时记录 source `0x08073BAC`、event3、sequence 严格晚于 PCO1，且 `argument0` 等于 unit slot；该 slot 必须通过 `0x020240C0 + slot * 0x1D4` 映射到独立 WRAM diagnostic 读取的同一 unit record。未命中则停止并做 GDB 只读 breakpoint，不追加盲输入。

- [x] **Step 3: 从 canonical checkpoint 重放最终证据**

使用新 ROM 从 `artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9` 重放已审计的零输入/单 A 链；每个可消费边界均先零输入或周期验收。最终 evidence 必须来自同一新 ROM、全零 baseline、fresh PCO1→PCU1/PCA1 顺序和 WRAM unit diagnostic。

Action-menu 动画的既有 600 帧诊断在原输入相对帧 `9/137/265` 得到首个精确三重哈希，给出
`anchor=9, p=128` 候选。必须先从原 action state 新建一次严格 zero-input frame-9 candidate，要求
其 RGB 与既有 frame 9 exact；随后从该 candidate 重新运行固定 600 帧 sampler，并由未修改的
analyzer 在新 candidate 自身的 `[0,p,2p]` 上重新选周期。只有 analyzer 选择 `p=128` 且两段
独立 128-frame replay 的 RGB、task、unit、observer 与资源门全部通过，第一段 p 输出才可供一次
fresh A 正证据运行。任何一步失败即停止，不使用原 diagnostic A 输出。

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
