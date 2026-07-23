# Codex Agent Timing Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实测当前 Codex 单代理完成五类 GBA 游戏基础内核和一次 Butano ROM 集成的墙钟时间，并据此重算全部基础系统工期。

**Architecture:** 五个逻辑内核以无堆、无异常、固定容量的 C++23 header-only 组件存在于隔离 benchmark 目录；宿主机 C++ 测试快速验证规则，Butano 自检入口验证交叉编译 wiring。Python 计时器用不可覆盖 JSON 事件记录每个红绿周期，最终报告用显式工作单元和系数外推。

**Tech Stack:** Python 3 `unittest`、Apple Clang C++23、Butano 21.7.1、固定 digest 的 devkitARM Docker、Make。

## Global Constraints

- 仅使用当前 Codex 主代理内联执行，不调用子代理或其他模型。
- 不计逆向补证、内容生产、旧存档兼容和人工等待。
- 每项先红后绿再重构；B6 必须真实构建 GBA ROM。
- 原始计时事件写入 `build/butano-agent-benchmark-20260721-01/`，不得覆盖。
- benchmark 代码不是正式游戏功能，不得在报告中宣称纵切片完成。
- 不自动 commit、push 或合并。

---

### Task 1: 不可覆盖的计时与 C++ 测试 harness

**Files:**
- Create: `tools/butano/benchmark_clock.py`
- Create: `tools/butano/run_cpp_benchmark_tests.py`
- Create: `tests/test_butano_benchmark_harness.py`

**Interfaces:**
- Produces: `benchmark_clock.py RUN_DIR start|event|finish TASK_ID ...`；每个 task 输出 `<TASK_ID>.json`。
- Produces: `run_cpp_benchmark_tests.py [test-name ...]`，逐个以 `clang++ -std=c++23` 编译并运行 `butano-sequel/benchmark/tests/test_*.cpp`。

- [ ] **Step 1: 写失败测试**：断言 start 创建 running manifest、重复 start/finish 失败、event 追加命令结果、finish 产生正时长且保留事件；断言空测试目录由 C++ runner 失败关闭。
- [ ] **Step 2: 运行红测**：`python3 -m unittest tests.test_butano_benchmark_harness -v`，预期因脚本不存在失败。
- [ ] **Step 3: 最小实现**：使用 `datetime.now(timezone.utc)`、`time.time_ns()` 和排他创建 `open(path, "x")`；更新通过同目录临时文件和 `os.replace`，但拒绝 finished manifest。
- [ ] **Step 4: 运行绿测与重构**：同一命令必须通过；运行 `python3 -m py_compile` 和 `git diff --check`。

### Task 2: B1 回合与行动状态机

**Files:**
- Create: `butano-sequel/benchmark/include/konoha_bench/action_state_machine.h`
- Create: `butano-sequel/benchmark/tests/test_action_state_machine.cpp`

**Interfaces:**
- Produces: `enum class action_phase`、`enum class action_input`、`struct action_result`、`class action_state_machine`，公开 `step(action_input)`、`phase()`、`committed()`。

- [ ] **Step 1: `benchmark_clock ... start B1`，写失败 C++ 测试**：覆盖 select→preview→menu→target→commit、preview/target/menu cancel、非法输入不变、commit 后 cancel 拒绝、end-turn。
- [ ] **Step 2: 运行红测并记录事件**：`python3 tools/butano/run_cpp_benchmark_tests.py test_action_state_machine`，预期缺 header 编译失败。
- [ ] **Step 3: 最小状态机**：显式 switch 转移；cancel 只退到定义的上一状态；返回 `{accepted, from, to}`。
- [ ] **Step 4: 运行绿测、整理命名并复验**，然后 `benchmark_clock ... finish B1`。

### Task 3: B2 地图、占位与确定性寻路

**Files:**
- Create: `butano-sequel/benchmark/include/konoha_bench/grid_pathfinder.h`
- Create: `butano-sequel/benchmark/tests/test_grid_pathfinder.cpp`

**Interfaces:**
- Produces: `point`、`grid_map<Width, Height>`、`path_result<Capacity>`、`find_path(map, start, goal, budget)`；0 成本表示阻挡，占位格不可进入，起点例外。

- [ ] **Step 1: 启动 B2 并写失败测试**：直线、绕障碍、高成本规避、预算不足、目标占位、不可达、固定 tie-break 和容量溢出。
- [ ] **Step 2: 运行红测并记录**：预期缺 header。
- [ ] **Step 3: 最小实现**：固定数组 Dijkstra，邻居顺序上、左、右、下，距离相同不重写 parent，结果重建时检查容量。
- [ ] **Step 4: 绿测、重构、复验并结束 B2**。

### Task 4: B3 事务式技能效果链

**Files:**
- Create: `butano-sequel/benchmark/include/konoha_bench/battle_effects.h`
- Create: `butano-sequel/benchmark/tests/test_battle_effects.cpp`

**Interfaces:**
- Produces: `unit_state`、`effect_kind`、`effect`、`effect_chain_result`、`apply_effect_chain(source, target, effects)`；失败时 source/target 字节等价回滚。

- [ ] **Step 1: 启动 B3 并写失败测试**：伤害下限、治疗上限、查克拉消费、状态、位移、效果顺序、非法目标、资源不足和中途失败回滚。
- [ ] **Step 2: 红测并记录**：预期缺 header。
- [ ] **Step 3: 最小实现**：先复制 source/target 到临时值，全部效果验证和应用成功后一次提交；数值使用显式饱和。
- [ ] **Step 4: 绿测、重构、复验并结束 B3**。

### Task 5: B4 有 step budget 的章节 VM

**Files:**
- Create: `butano-sequel/benchmark/include/konoha_bench/chapter_vm.h`
- Create: `butano-sequel/benchmark/tests/test_chapter_vm.cpp`

**Interfaces:**
- Produces: `chapter_opcode`、`chapter_event`、`vm_status`、`chapter_vm<ProgramCapacity, EventCapacity>`；`run(step_budget)` 在 emit/wait/start-battle/end/error 时返回。

- [ ] **Step 1: 启动 B4 并写失败测试**：对白事件、flag、条件分支、等待恢复、启动战斗、正常结束、非法 opcode、越界跳转、缺 end 和预算耗尽。
- [ ] **Step 2: 红测并记录**：预期缺 header。
- [ ] **Step 3: 最小实现**：字节 PC、固定 flag bitset、固定事件数组，所有 operand 读取前做边界检查，budget 为零返回 error。
- [ ] **Step 4: 绿测、重构、复验并结束 B4**。

### Task 6: B5 版本化双槽存档 codec

**Files:**
- Create: `butano-sequel/benchmark/include/konoha_bench/save_codec.h`
- Create: `butano-sequel/benchmark/tests/test_save_codec.cpp`

**Interfaces:**
- Produces: `save_payload`、`save_slot`、`decode_result`、`encode_slot(payload, generation)`、`decode_slot(bytes)`、`load_newest(slot_a, slot_b)`；格式含 magic/version/generation/payload/CRC32。

- [ ] **Step 1: 启动 B5 并写失败测试**：确定性往返、默认新档、截断、magic/version/CRC 错误、generation 选择、写坏新槽仍读取旧槽。
- [ ] **Step 2: 红测并记录**：预期缺 header。
- [ ] **Step 3: 最小实现**：显式 little-endian 编解码，CRC32 固定多项式，decode 不 reinterpret_cast，双槽只选择完整有效且 generation 更新的槽。
- [ ] **Step 4: 绿测、重构、复验并结束 B5**。

### Task 7: B6 Butano 自检 ROM 集成

**Files:**
- Create: `butano-sequel/benchmark/include/konoha_bench/self_test.h`
- Create: `butano-sequel/benchmark/src/self_test.cpp`
- Modify: `butano-sequel/Makefile`
- Modify: `butano-sequel/src/main.cpp`
- Modify: `tests/test_butano_build.py`

**Interfaces:**
- Produces: `self_test_result run_self_tests()`，包含五位 pass mask 和 `all_passed()`。
- Consumes: B1–B5 公共头文件。

- [ ] **Step 1: 启动 B6 并先扩展集成测试**：要求 Makefile 编译 benchmark source/include，main 调用 `run_self_tests`，干净 ROM 构建成功，ELF 符号表包含 `konoha_bench::run_self_tests()`。
- [ ] **Step 2: 运行红测并记录**：`RUN_BUTANO_INTEGRATION=1 python3 -m unittest tests.test_butano_build -v`，预期 wiring 断言失败。
- [ ] **Step 3: 实现自检与可见结果**：自检分别执行五个最小确定性用例；ROM 显示 `B1 STATE PASS` 至 `B5 SAVE PASS` 和 `ALL PASS`/`SELF TEST FAILED`。
- [ ] **Step 4: 固定 Docker 镜像干净构建，绿测、复验并结束 B6**。

### Task 8: 样本外推与持久报告

**Files:**
- Create: `notes/butano-agent-timing-benchmark-20260721.md`
- Modify: `docs/butano-konoha-systems-cost.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `tests/test_butano_research_docs.py`

**Interfaces:**
- Consumes: B1–B6 JSON 的 start/end/duration/events 和源码/构建统计。
- Produces: 13 系统 Codex 墙钟小时表、总区间、8/16/24 小时日历换算和误差说明。

- [ ] **Step 1: 先修改文档测试为红**：要求旧人周结论标记“已取代”，报告包含 `Codex 连续墙钟小时`、六项实测、外推公式、8/16/24 小时日历和“不计逆向补证”。
- [ ] **Step 2: 读取不可变 JSON 并计算**：逐项把系统拆成内核单元、wiring、集成和回归次数；按规格中的三档系数计算，所有小计可手工复算。
- [ ] **Step 3: 写报告和路线图追加**：明确样本边界、失败/返工和 mGBA 自动化限制，不把 benchmark 宣称为正式功能。
- [ ] **Step 4: 运行文档测试和范围验证**：相关单元测试、C++ 全部测试、干净 ROM 集成、setup verifier、`git diff --check`；披露范围外既有失败。
