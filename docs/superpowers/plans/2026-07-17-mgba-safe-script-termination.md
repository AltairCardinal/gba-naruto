# mGBA Qt 脚本安全终止 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 mGBA Qt replay 在 CPU 线程执行 `os.exit` 引发的非确定 `SIGABRT`，同时保留 guard `completed/0`、固定脚本和 owned-tree 证据门禁。

**Architecture:** `run_guarded` 增加默认关闭的 fresh success-marker 终止条件；固定 Lua 在所有产物落盘后写 marker 并停止副作用。runner 验证 marker payload 和全部既有产物，guard 只清理本次 owned process group。

**Tech Stack:** Python 3 `unittest`、mGBA 0.10.5 Lua、POSIX process group/Windows Job Object、项目 `run_guarded.py`。

## Global Constraints

- 默认 guard 行为必须完全兼容；只有显式 `--success-marker` 才启用新终止条件。
- marker 必须在启动前不存在，运行后是 fresh regular non-symlink 文件；内容绑定 run ID 与 capture frame。
- Lua 不得调用 `os.exit`，marker 写出后不得再发送输入、覆盖产物或重复写 marker。
- 任何 marker/产物/provenance/残留不一致仍 fail closed；不得接受旧 `child-exit/-6` state。
- 所有真实 mGBA 验证继续使用同一 heavy lock、可用内存门和 owned-tree RSS 上限。

---

### Task 1: Resource guard success-marker terminal condition

**Files:**
- Modify: `tools/project_resource_guard.py`
- Modify: `tools/run_guarded.py`
- Test: `tests/test_project_resource_guard.py`
- Test: `tests/test_run_guarded.py`

**Interfaces:**
- Consumes: 现有 `run_guarded(command, ..., summary_path, config, ...) -> GuardResult`。
- Produces: 可选 `success_marker: str | Path | None = None`；CLI `--success-marker PATH`；成功摘要保持 `reason="completed"`、`exit_code=0`，并增加 metadata `completion_trigger="success-marker"`。

- [ ] **Step 1: 写 RED 单元与 CLI 集成测试**

测试必须覆盖：marker 启动前已存在时不启动 child；运行中 marker 出现会终止且只终止 owned tree、返回 `completed/0`；marker 缺失仍走原 timeout；默认无 marker 的现有成功/失败语义不变；CLI 摘要包含 trigger。

- [ ] **Step 2: 运行 RED 并确认因接口缺失失败**

Run: `python3 -m unittest tests.test_project_resource_guard tests.test_run_guarded -v`

Expected: 新测试因 `run_guarded(..., success_marker=...)`/`--success-marker` 尚不存在而 FAIL/ERROR，既有测试保持通过。

- [ ] **Step 3: 实现最小 guard 行为**

在 `_monitor_started_process` 每轮先读取 child exit；child 仍存活且 marker 成为 fresh regular non-symlink 时，调用现有 `_stop_with_result(..., "completed", 0, ...)`。不得新增按进程名扫描；metadata 仅在 marker 实际触发时写入。

- [ ] **Step 4: 运行 GREEN 与回归**

Run: `python3 -m unittest tests.test_project_resource_guard tests.test_run_guarded -v`

Expected: PASS，且现有 lock/memory/timeout/protection-failure 测试无退化。

- [ ] **Step 5: 创建聚焦本地 commit**

```bash
git add tools/project_resource_guard.py tools/run_guarded.py tests/test_project_resource_guard.py tests/test_run_guarded.py
git commit -m "fix(tools): let guard own scripted completion"
```

### Task 2: Fixed replay marker contract and failed-B revalidation

**Files:**
- Modify: `tools/mgba_checkpoint_replay.lua`
- Modify: `tools/mgba_single_input_replay.lua`
- Modify: `tools/run_macos_mgba_replay.py`
- Modify: `tools/run_macos_mgba_single_input.py`
- Modify: `tools/README.md`
- Test: `tests/test_run_macos_mgba_replay.py`
- Test: `tests/test_run_macos_mgba_single_input.py`

**Interfaces:**
- Consumes: Task 1 的 `--success-marker` 和摘要 trigger。
- Produces: env `MGBA_REPLAY_DONE_MARKER`；payload `{"run_id":"<32 hex>","capture_frame":N,"status":"capture-complete"}`；runner 对 marker、audit/sentinel、state/PNG、hash/residue 的联合验收。

- [ ] **Step 1: 写 RED runner/Lua 契约测试**

静态契约要求两个固定 Lua 不含 `os.exit`，要求 done-marker env，并在 audit/sentinel 后最后写 marker；runner 必须传 `--success-marker`、验证 payload、拒绝 missing/wrong marker 和缺少 trigger 的 guard summary。更新固定 Lua SHA 的测试期望只能在 GREEN 阶段完成。

- [ ] **Step 2: 运行 RED 并确认正确失败**

Run: `python3 -m unittest tests.test_run_macos_mgba_replay tests.test_run_macos_mgba_single_input -v`

Expected: 新测试因现有 Lua 仍含 `os.exit` 且 runner 无 marker 契约而 FAIL；不是路径或 fixture 错误。

- [ ] **Step 3: 实现最小 Lua/runner 变更**

runner 为每次 fresh 输出生成 `<guard-summary>.done.json`，把绝对路径传给 Lua 与 guard；Lua 使用既有 `write_file` 在全部 capture 文件关闭后写 marker并设置 `capture_complete=true`，后续 frame callback立即返回。更新两个 runner 内固定 SHA；不修改输入时序、截图/state 顺序或 provenance 字段。

- [ ] **Step 4: 运行 GREEN、guard 回归和静态检查**

Run: `python3 -m unittest tests.test_run_macos_mgba_replay tests.test_run_macos_mgba_single_input tests.test_project_resource_guard tests.test_run_guarded -v`

Run: `python3 -m py_compile tools/project_resource_guard.py tools/run_guarded.py tools/run_macos_mgba_replay.py tools/run_macos_mgba_single_input.py`

Run: `git diff --check`

Expected: 全部 PASS。

- [ ] **Step 5: 真实重放同一 inner B 并验收根因已消失**

从 accepted final-A zero state `1c4b1796...f571` 在 fresh 目录执行唯一 B `5/13/80`。要求：guard `completed/0` 且 trigger=`success-marker`；没有新增 mGBA crash report；audit/sentinel/marker 完整；RSS `<1536 MiB`；PGID/listener/source `base.sav` clean。旧 `325dd862...00e0` state 保持 rejected。

- [ ] **Step 6: 更新 README 并创建聚焦本地 commit**

README 说明 Qt CPU-thread `os.exit` 禁令、marker 只是清理信号而非证据、失败边界与旧崩溃产物不可消费。

```bash
git add tools/mgba_checkpoint_replay.lua tools/mgba_single_input_replay.lua tools/run_macos_mgba_replay.py tools/run_macos_mgba_single_input.py tools/README.md tests/test_run_macos_mgba_replay.py tests/test_run_macos_mgba_single_input.py
git commit -m "fix(tools): terminate mGBA replay through guard"
```
