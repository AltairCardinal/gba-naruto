# macOS mGBA GDB Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 macOS Intel 上以严格、可测试的 TCP owner gate 复用现有 mGBA GDB 探针，并用一次 guarded smoke 证明 `0x08095F12` 可精确停止。

**Architecture:** `mgba_gdb_probe.py` 保留现有 RSP 与 Windows owner 查询；Darwin 新增直接调用 `/usr/sbin/lsof` 的结构化字段解析和精确 endpoint 筛选。实际 mGBA 仍由 `run_guarded.py` 的 heavy lock/process group/RSS 门禁拥有，GDB 不负责输入。

**Tech Stack:** Python 3 `unittest`、mGBA 0.10.5 Qt GDB RSP、Darwin `/usr/sbin/lsof -FpnT`、项目 `run_guarded.py`。

## Global Constraints

- 所有实现严格执行 RED → GREEN → REFACTOR；没有先失败的测试不得修改 production code。
- Windows `GetExtendedTcpTable` 行为和现有测试保持不变。
- Darwin owner 证据必须来自精确 endpoint，不接受仅按端口或进程名猜测。
- `lsof` 缺失、超时、异常/畸形输出、owner 为空/多义/不等于 child PID全部 fail closed。
- mGBA smoke 必须经过 shared heavy lock、owned process group、RSS ceiling；只允许一次，不 retry、不输入。
- 不修改用户既有 `AGENTS.md`、`docs/sequel-roadmap.md`，不 push。

---

### Task 1: Darwin TCP owner adapter

**Files:**
- Modify: `tools/mgba_gdb_probe.py`
- Modify: `tests/test_mgba_gdb_probe.py`
- Modify: `tools/README.md`

**Interfaces:**
- Consumes: existing `listener_owner_pids(host, port)` and `connection_owner_pids(server_local, server_remote)` callers.
- Produces: the same return types on Darwin (`set[int]` and `list[int]`) without changing `run_probe()` or the evidence schema.

- [ ] **Step 1: Write failing parser/filter tests**

Add tests with an `lsof -FpnT` fixture containing two PIDs, a LISTEN record, the target ESTABLISHED direction, its client-side reverse direction, and unrelated ports. Require a focused parser to return records with exact PID/state/local/remote endpoints; require listener and connection filters to select only the server owner. Add malformed PID, missing endpoint/state, subprocess timeout/failure, and ambiguous-owner cases.

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_mgba_gdb_probe`

Expected: FAIL because the Darwin lsof record/parser/query functions do not exist and current owner helpers raise the Windows-only error.

- [ ] **Step 3: Implement the minimal Darwin adapter**

Add one immutable record type with `pid`, `state`, `local`, and optional `remote`. Parse only these field records:

```text
p4242
n127.0.0.1:2345
TST=LISTEN
n127.0.0.1:2345->127.0.0.1:54000
TST=ESTABLISHED
```

Run `/usr/sbin/lsof` with an argv list (no shell), `-nP -FpnT -iTCP:<port>`, captured text and a finite timeout. Validate decimal PID, numeric IPv4 endpoint/port, known LISTEN/ESTABLISHED state, and complete records. On `os.name == "nt"`, retain existing table code; on Darwin/POSIX, dispatch to the lsof implementation. Return all exact owners so the existing caller continues to reject zero, multiple, or mismatched PID.

- [ ] **Step 4: Add real Darwin integration coverage**

Under `@unittest.skipUnless(sys.platform == "darwin", ...)`, create a loopback listener owned by the current Python PID and assert the real listener query returns that PID. Create one accepted loopback connection and assert the exact server-local/client-peer query returns the current PID. Close all sockets in `finally`.

- [ ] **Step 5: Run GREEN and related verification**

Run:

```sh
python3 -m unittest tests.test_mgba_gdb_probe
python3 -m unittest tests.test_mgba_gdb_probe tests.test_project_resource_guard tests.test_run_guarded
python3 -m py_compile tools/mgba_gdb_probe.py
git diff --check
```

Expected: all pass; Windows-only tests remain skipped only on non-Windows; Darwin integration tests pass on this host.

- [ ] **Step 6: Commit and review**

Commit only the three scoped files with message `fix(re): verify mGBA GDB owners on macOS`. Generate a review package from the recorded base and require fresh reviewer verdicts `Spec PASS` and `Quality APPROVED` before runtime.

---

### Task 2: One guarded breakpoint smoke and retire the invalid Lua path

**Files:**
- Delete after successful smoke: `tools/mgba_breakpoint_frame_trace.lua`
- Delete after successful smoke: `tests/test_mgba_breakpoint_frame_trace.py`
- Modify: `tools/README.md`
- Modify: `openspec/changes/close-scenario-41-battle-runtime/.comet/subagent-progress.md`

**Interfaces:**
- Consumes: approved Task 1 adapter, observer ROM SHA `2992a8434da391d6191ddf71119c9409dcf3ca5223010d5f9d405e0b35a96dd8`, state SHA `cdb9ed6489a745ab602a0914afee3251c78e21f57751c207e53e3aa5d20a60e2`.
- Produces: a compact GDB smoke report proving or rejecting exact stop `0x08095F12`; no reusable output state.

- [ ] **Step 1: Preflight**

Require `rom/base.sav` absent, no mGBA/QEMU/GDB listener residue, available memory at least 4096 MiB, fixed binary/manifest/ROM/state hashes, and a fresh output directory. Record the existing crash baseline.

- [ ] **Step 2: Run exactly one guarded probe**

Use `tools/run_guarded.py` with the shared heavy lock, RSS ceiling 1536 MiB, wall/idle bounds, and `tools/mgba_gdb_probe.py` against the exact macOS mGBA binary. Load the fixed observer ROM and state, set breakpoint `0x08095F12`, and read only the task context and observer scratch needed to confirm the stop. Do not send input and do not retry.

- [ ] **Step 3: Validate the result**

Require output `outcome=verified`, listener/connection owner PID equal the owned child, ROM fingerprint match, actual PC accepted by Thumb stop semantics, guard/residue/base.sav/crash clean, and RSS below 1536 MiB. If any gate fails, preserve `not-proven`, stop, and do not delete the Lua files.

- [ ] **Step 4: Retire the invalid Lua breakpoint path only after smoke passes**

Delete the Lua trace and its behavior tests; remove the README section that presents it as usable. Replace it with a short failure-history note stating that the Qt-only 0.10.5 backport loads scripts after the one-shot start callback and lacks breakpoint script exports, so precise native addresses use the strict GDB probe. Run the related GDB/replay/resource tests and `git diff --check`.

- [ ] **Step 5: Commit and review**

Create one focused commit for the retirement/documentation and persist only compact smoke evidence. A fresh reviewer must approve scope, provenance, owner/stop gates, resource cleanup, and the conclusion boundary before Task 5B Step 1 continues.
