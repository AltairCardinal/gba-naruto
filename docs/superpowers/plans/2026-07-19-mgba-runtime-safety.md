# mGBA Runtime Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让统一资源守卫拒绝危险 mGBA Lua，并在新崩溃报告出现时熔断后续模拟。

**Architecture:** 新建独立的 mGBA 安全策略模块，`run_guarded.py` 只负责调用它并维持原有通用资源守卫语义。运行时状态写入 `build/resource-guard/`，不污染版本控制。

**Tech Stack:** Python 3 标准库、unittest、现有 `project_resource_guard`。

## Global Constraints

- 所有行为变化先红后绿。
- 不改动用户已有的 `AGENTS.md` 与路线图修改。
- 不使用 Comet，不自动 push。

---

### Task 1: mGBA 启动策略与熔断状态

**Files:**
- Create: `tools/mgba_runtime_safety.py`
- Test: `tests/test_mgba_runtime_safety.py`

**Interfaces:**
- Produces: `prepare_mgba_launch(command, crash_dir, latch_path) -> LaunchAudit | None`
- Produces: `finish_mgba_launch(audit, summary_path, exit_code) -> int`
- Produces: `clear_crash_latch(latch_path, crash_dir) -> None`

- [x] 写测试证明危险 `--script`、已有熔断和 marker 后新 `.ips` 当前未被阻止。
- [x] 运行 `python3 -m unittest tests.test_mgba_runtime_safety -v`，确认因接口缺失而失败。
- [x] 最小实现命令识别、实际 Lua 扫描、报告快照、熔断写入与显式清除。
- [x] 重跑测试并保持全绿。

### Task 2: 接入统一资源守卫并做真实回放

**Files:**
- Modify: `tools/run_guarded.py`
- Modify: `tests/test_run_guarded.py`
- Modify: `tools/README.md`

**Interfaces:**
- Consumes: Task 1 的 `prepare_mgba_launch` 与 `finish_mgba_launch`。
- Produces: 所有经 `run_guarded.py` 启动的 mGBA 都自动执行安全策略。

- [x] 写 CLI 集成测试：危险 Lua 不启动子进程；非 mGBA 命令行为不变；新 crash report 返回失败。
- [x] 运行相关测试确认红灯。
- [x] 在 `run_guarded.py` 启动前后接入策略，保持原参数兼容。
- [x] 运行 `python3 -m unittest tests.test_mgba_runtime_safety tests.test_run_guarded -v`。
- [x] 用固定单输入 runner 从场景 45 快照执行一次真实回放，确认无新崩溃报告、熔断未触发、PGID 无残留。

### Task 3: 审查加固

- [x] 构建 sentinel 改为由统一守卫直接启动 mGBA。
- [x] 预检、启动、成功 marker 清理和 crash-report 收尾置于同一 heavy lock 生命周期。
- [x] 持久化已确认报告基线，使迟到 `.ips` 在下一轮启动前触发熔断。
- [x] crash 目录扫描和安全状态写入失败时关闭失败。
- [x] 增加竞态、marker+crash、迟到报告、写失败和 Lua 别名调用回归测试。
