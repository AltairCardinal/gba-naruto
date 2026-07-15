# Task 4.5 Step 1 实施报告

状态：`DONE_WITH_CONCERNS`

提交：`3a1c788` (`feat(re): guard macOS Intel runtime probes`)

本次只执行 brief 的 Step 1。没有执行或勾选 Step 2，没有修改 plan、OpenSpec
tasks、`.comet` progress，也没有清理或提交 `build/` 和外部缓存。

## 变更文件

- `tools/project_resource_guard.py`
- `tests/test_project_resource_guard.py`
- `tests/test_run_guarded.py`
- `tools/README.md`
- `notes/macos-intel-runtime-preflight-20260715.md`

## TDD RED

为避免回滚共享工作树，使用临时目录中的 `git archive HEAD` 作为生产代码，
只覆盖当前新增测试模块，然后运行：

```bash
python3 -m unittest \
  tests.test_project_resource_guard.ProjectResourceGuardTests.test_darwin_available_memory_counts_free_inactive_and_speculative_pages \
  tests.test_project_resource_guard.ProjectResourceGuardTests.test_darwin_rss_sums_only_rooted_descendants_from_ps_snapshot \
  tests.test_run_guarded.RunGuardedCliAndPosixTests.test_darwin_cli_launches_and_monitors_an_owned_child \
  -v
```

结果：按预期失败（退出 1）。三个缺口分别为：

- `RuntimeError: physical memory reader is unsupported on darwin`；
- `FileNotFoundError: /proc`；
- 真实 Darwin CLI 返回 125（protection-failure），而测试期望 0；该旧 CLI RED
  先在 Darwin admission 因 unsupported 失败，未到达 RSS wiring。上述 RSS 单元
  RED 才独立证明 `/proc` 缺口。

## GREEN 与最终验证

```bash
python3 -m unittest \
  tests.test_project_resource_guard.ProjectResourceGuardTests.test_darwin_available_memory_counts_free_inactive_and_speculative_pages \
  tests.test_project_resource_guard.ProjectResourceGuardTests.test_darwin_rss_sums_only_rooted_descendants_from_ps_snapshot \
  tests.test_run_guarded.RunGuardedCliAndPosixTests.test_darwin_cli_launches_and_monitors_an_owned_child \
  -v
```

结果：`Ran 3 tests`，全部通过。

```bash
python3 -m unittest tests.test_project_resource_guard tests.test_run_guarded -v
```

结果：`Ran 38 tests`，0 failures/errors；1 个 Windows Job Object 专用用例按平台跳过。

真实 `tools/run_guarded.py` smoke 使用临时 summary/lock，启动一个休眠 0.25 秒的
Python owned child。最终验证结果：exit 0、reason `completed`、backend
`posix-process-group`、degraded `false`、峰值 RSS `8.56640625 MiB`；child/PGID
`34397` 的 exact `ps` 查询无残留。此前带 marker 的 smoke 也返回 0、成功写入
marker、峰值 RSS `9.23828125 MiB`，PGID 无残留。

`git diff --check` 和 `git diff --cached --check` 均退出 0。仓库没有配置 ruff、
Black 或其他 Python formatter；现有 unittest 与 diff whitespace check 是本改动可用的
格式/行为验证。

## mGBA 0.10.5 证据

- 官方源码：`https://github.com/mgba-emu/mgba.git`，tag `0.10.5`。
- commit：`26b7884bc25a5933960f3cdcd98bac1ae14d42e2`。
- 源码缓存：`/Users/altair/.cache/codex-tools/mgba/0.10.5-src`，调查后
  `git status --short` 为空，未修改外部源码。
- 构建缓存：`/Users/altair/.cache/codex-tools/mgba/0.10.5-build-qt`。
- binary：`/Users/altair/.cache/codex-tools/mgba/0.10.5-build-qt/qt/mGBA.app/Contents/MacOS/mGBA`。
- version：`mGBA 0.10.5 (26b7884bc25a5933960f3cdcd98bac1ae14d42e2)`。
- file：`Mach-O 64-bit executable x86_64`。
- SHA-256：`30b2ed9065123405463ab6e372cf43e1e6febfaa9598d77cc8684cde61cdaae2`。
- help：正常输出 generic/graphics/frontend options；无 `--script`。

非提交的 guard summaries：

| 阶段 | 结果 | 峰值 owned-tree RSS | 最终 PGID |
|---|---:|---:|---|
| clone | completed/0 | 50.0078125 MiB | clean |
| configure（无 policy override） | child-exit/1 | 1.31640625 MiB | clean |
| configure（加 `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`） | completed/0 | 64.58203125 MiB | clean |
| build (`--parallel 2`) | completed/0 | 553.62109375 MiB | clean |

成功配置的关键值：Release、Qt ON、SDL OFF、`ENABLE_SCRIPTING=ON`、Lua 5.5.0；
构建完成全部 367 个 Ninja edges。四个 owned child PID 对应的 exact PGID 查询均
无残留。

## mGBA CLI 根因与顾虑

复现：`mGBA --script /tmp/nonexistent-task45.lua` 稳定退出 1，并打印
`mGBA: unrecognized option '--script'`。根因调查确认：

- `ENABLE_SCRIPTING` 构建 scripting library/Lua；
- Qt CMake 条件编译 `ScriptingController`/`ScriptingView`，`Window.cpp` 将其接到
  GUI Tools 菜单；
- 0.10.5 的 `src/feature/commandline.c` 未注册 `script`；
- Qt `ConfigController.cpp` 的 subparser 只注册 graphics、`ecard`、`mb`。

因此 `ENABLE_SCRIPTING=ON` 仅证明 scripting library/Qt GUI 能力，不证明 CLI
脚本加载能力。按 brief 没有修改外部 mGBA 源码。后续运行时迁移不能假设
`mGBA --script`，必须选择并单独验证 GDB 等既有接口，或另行评估版本/前端。

另一个非阻塞顾虑是官方 0.10.5 在 AppleClang 16 下会产生 deployment
availability、sign/qualifier、unused 和 linker warnings；构建成功，但若要发布二进制
仍应单独审计。

## 自审与用户可见验收

### 【功能特性】
- macOS Intel 资源守卫：从现有 `run_guarded.py` 入口启动命令时，用户可获得
  Darwin admission、owned-tree RSS 峰值、reason/backend/degraded summary；空数据或
  系统命令失败按 protection-failure fail closed。
- 精确所有权：macOS 继续使用 POSIX process group，完成或失败后只清理本次 owned
  group，不按进程名影响其他同名进程。

### 【BUG 修复】
- Darwin admission：修复前直接报 unsupported、命令返回 125 → 修复后读取
  `vm_stat` 并可启动合格命令。
- Darwin RSS：修复前访问不存在的 `/proc` → 修复后通过 `ps` 监控 owned process
  group。

### 【验收清单】
- [x] 运行 focused Darwin 3 tests → 3/3 通过。
- [x] 运行两模块完整 guard suite → 38 tests，只有 Windows-only 1 skip。
- [x] 运行真实 guarded child → completed/0、summary 有正峰值 RSS、owned PGID 无残留。
- [x] 查看 mGBA version/file/SHA/help → 版本、commit、x86_64、哈希匹配；help 无
  `--script`。
- [x] 检查 clone/config/build guard summaries → 峰值 RSS 已记录、owned PGID 全 clean。
- [x] 检查提交范围 → 仅 5 个允许文件；Step 2/OpenSpec/plan/progress/build 未提交。

功能边界：本次只建立 macOS 资源守卫和 mGBA 迁移前置证据，不实现 Scenario 4.1
战斗运行时，不提供 mGBA CLI scripting，也不更改外部 mGBA。

---

# Task 4.5 review fix round 1/2

状态：`DONE_WITH_CONCERNS`

范围：只修复 review `4c446bc..3a1c788` 指出的 Darwin owned-PGID RSS、fail-closed、
真实 CLI 稳定性与证据缺口；未修改 plan、OpenSpec tasks 或 `.comet` progress，
也未提交忽略的 `build/` 证据。

## 根因与 TDD RED

Darwin 清理和存活判断使用 POSIX process group，但 RSS 读取使用 PPID 链。owned
root 退出后，grandchild 被 reparent，仍属于 owned PGID，却从 PPID rooted tree
消失，因而可绕过 `max_tree_rss_mib`。同一解析器对空、全畸形或没有 owned group
的 `ps` 输出返回 0，也会把监控失效误当成零 RSS。

先新增测试并运行：

```bash
python3 -m unittest \
  tests.test_project_resource_guard.ProjectResourceGuardTests.test_darwin_rss_sums_only_owned_process_group_from_ps_snapshot \
  tests.test_project_resource_guard.ProjectResourceGuardTests.test_darwin_rss_keeps_counting_owned_group_after_root_exits \
  tests.test_project_resource_guard.ProjectResourceGuardTests.test_darwin_rss_fails_closed_for_unusable_ps_snapshots \
  tests.test_run_guarded.RunGuardedCliAndPosixTests.test_darwin_cli_launches_and_monitors_an_owned_child \
  tests.test_run_guarded.RunGuardedCliAndPosixTests.test_darwin_root_exit_grandchild_in_owned_group_hits_memory_limit \
  -v
```

RED 退出 1，正确失败摘要：实现实际调用 `pid=,ppid=,rss=` 而非期望的
`pid=,pgid=,rss=`；空、全畸形、owned PGID 缺失三类输出均未抛异常；真实 root
退出后 48 MiB grandchild 在 32 MiB 上限下最终为 `wall-timeout`/124，而非
`memory-limit`/125。真实 Darwin 回收期间还暴露 `killpg(..., 0)` 短暂 EPERM；为此
追加 `test_posix_wait_retries_transient_permission_while_group_is_being_reaped`，旧实现
以 `PermissionError` 正确 RED。

## GREEN、重构与完整回归

最小实现改为从单次 `ps -axo pid=,pgid=,rss=` 快照累加 PGID 等于 owned root PID
的所有行；即使 root 行已消失也继续计入 group member。没有任何 owned PGID 行时
抛 `RuntimeError` fail closed。POSIX wait 对 Darwin 回收窗口中的 EPERM 保持有界
重试，直到 group 消失或超时。GREEN 后将 Darwin helper 重命名为
`_darwin_process_group_rss_mib`，明确所有权语义。

focused 命令（上述五项加 EPERM 用例）结果：`Ran 6 tests`，全部通过。

```bash
python3 -m unittest tests.test_project_resource_guard tests.test_run_guarded -v
```

结果：`Ran 42 tests`，0 failures/errors；1 个 Windows Job Object 专用用例按平台
跳过。真实 root-exit guard 另行保存 summary：root PID/PGID `45851` 退出后，
grandchild PID `45853` 分配 48 MiB；结果 `memory-limit`/125、峰值 owned-PGID RSS
`57.23828125 MiB`、backend `posix-process-group`、degraded `false`，最终 exact PGID
查询为空。

## guarded mGBA CLI 证据

三项能力检查均通过修复后的 `tools/run_guarded.py` 和共享 heavy lock 运行，summary
保存在忽略的 `build/resource-guard/`，未加入提交：

| 命令 | reason/exit | 峰值 RSS | child/PGID | 最终 PGID |
|---|---|---:|---:|---|
| `mGBA --version` | completed/0 | 4.03125 MiB | 44642 | clean |
| `mGBA --help` | completed/0 | 0.16796875 MiB | 45016 | clean |
| `mGBA --script /tmp/nonexistent-task45.lua` | child-exit/1 | 0.171875 MiB | 45390 | clean |

三项均为 `posix-process-group`、`degraded: false`。`--script` 的 child-exit/1 是上游
0.10.5 CLI 不识别该选项的预期能力边界，不是 guard failure。

## 自审与用户可见验收

### 【功能特性】
- macOS Intel 资源守卫：用户从 `tools/run_guarded.py` 启动 heavy command 时，root
  提前退出也会继续监控同一 owned PGID，summary 展示完整 group 的峰值 RSS。
- mGBA 能力证据：用户可在迁移前置 note 中查看三项实际 heavy-guard 结果；CLI
  scripting 边界明确为不支持。

### 【BUG 修复】
- root-exit RSS 绕过：修复前 reparented grandchild 不再计入、最终 wall timeout →
  修复后仍按 owned PGID 计入，超过上限立即 memory-limit/125 并清理 group。
- 无效 `ps` 静默返回 0：修复前空/畸形/无 owned PGID 被视为零 RSS → 修复后抛错
  并走 protection-failure fail closed。
- Darwin CLI 测试竞态：修复前 helper 可能在首次 RSS sample 前退出 → 修复后至少
  存活 0.3 秒（6 个 0.05 秒采样周期），并显式验收最终 PGID clean。

### 【验收清单】
- [x] 运行 focused 6 tests → 6/6 通过。
- [x] 运行完整两模块 guard suite → 42 tests，只有 Windows-only 1 skip。
- [x] 运行真实 root-exit/48 MiB grandchild/32 MiB limit → memory-limit/125、PGID clean。
- [x] 运行 guarded mGBA version/help/script → completed/0、completed/0、child-exit/1；
  三个 PGID 均 clean。
- [x] 运行 `git diff --check` → 退出 0；提交范围只包含六个允许文件，ignored
  `build/` 与用户已有 plan/OpenSpec/progress 改动不加入提交。

功能边界：本修复只保证 Darwin owned-PGID 资源监控与现有 mGBA CLI 能力证据，
不增加 mGBA `--script` 支持，不实现 Scenario 4.1 runtime，不修改外部 mGBA 源码。

非阻塞顾虑：官方 mGBA 0.10.5 的 AppleClang 16 构建 warnings 仍与原报告一致，
若发布二进制需单独审计。
