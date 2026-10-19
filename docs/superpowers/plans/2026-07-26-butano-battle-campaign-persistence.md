# Butano Battle Campaign Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 63 名角色的战斗成长状态从三条临时场景记录提升为可跨冷启动恢复的版本化 SRAM 档案。

**Architecture:** 新增纯领域 `battle_campaign_state`、纯字节 `battle_campaign_save_codec` 和仅 ARM 使用的 SRAM adapter。`run_battle_scene` 只负责三人小队投影及按角色 ID 合并，controller、resolver 和 renderer 不依赖 SRAM。

**Tech Stack:** C++20、Butano `bn::sram`、宿主 assert 测试、Python 接线测试、devkitARM、mGBA Lua。

## Global Constraints

- 所有生产行为必须先有失败测试并观察正确 RED。
- 不把 `BattleSession`、场景 snapshot、RNG 或表现状态写入存档。
- 两个 4096 字节槽必须带版本、generation、CRC32 和领域校验。
- SRAM/codec 工作区不得进入 GBA IWRAM 栈。
- 不修改或覆盖 `rom/base.sav`；mGBA 只使用隔离 staged ROM/SAV。
- 不自动提交、暂存或推送。

---

### Task 1: 63 角色 campaign 领域模型

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_campaign.h`
- Test: `butano-sequel/game/tests/test_battle_campaign.cpp`

**Interfaces:**
- Produces: `battle_campaign_state`, `initialize_battle_campaign`, `project_battle_party`, `merge_battle_party_progression`.
- Consumes: `character_progression_record`, `generated_unit_definitions`.

- [x] **Step 1: 写失败测试**

测试建立 Naruto/Sasuke/Sakura 三人档案，投影到三条场景 progression；修改 Naruto
等级、经验、修炼点和技能状态后按角色 ID 合并，断言其余 62 条记录零变化。重复角色、
未激活角色和不存在角色必须拒绝且输出零写。

- [x] **Step 2: 运行 RED**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_campaign`

Expected: FAIL，因为 `konoha/battle_campaign.h` 不存在。

- [x] **Step 3: 实现最小领域模型**

使用 63 条固定记录和三人 ID，不复制技能规则；激活角色时调用既有
`initialize_character_action_progression`。

- [x] **Step 4: 运行 GREEN 并重构**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_campaign`

Expected: PASS。

### Task 2: 显式、双槽可恢复的存档 codec

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_campaign_save.h`
- Test: `butano-sequel/game/tests/test_battle_campaign_save.cpp`

**Interfaces:**
- Produces: `battle_campaign_save_slot`, `encode_battle_campaign_slot`, `decode_battle_campaign_slot`, `load_latest_battle_campaign_slot`, `next_battle_campaign_slot`.
- Consumes: `battle_campaign_state`.

- [x] **Step 1: 写失败测试**

覆盖确定性编码、63 角色 round-trip、magic/version/size/CRC 错误、非法 level/技能/
忍具/party，两个有效 generation 选择、单槽损坏回退和双槽损坏默认值。

- [x] **Step 2: 运行 RED**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_campaign_save`

Expected: FAIL，因为 codec 头不存在。

- [x] **Step 3: 实现 4096 字节协议**

逐字段 little-endian 编码；CRC 复用 benchmark codec 已验证的多项式，但不依赖 benchmark
namespace 或 raw struct layout。

- [x] **Step 4: 运行 GREEN 并重构**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_campaign_save`

Expected: PASS。

### Task 3: 场景投影、结果合并与 SRAM adapter

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_campaign_sram.h`
- Create: `butano-sequel/game/src/battle_campaign_sram.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/src/main.cpp`
- Test: `butano-sequel/game/tests/test_battle_scene_results.cpp`
- Test: `tests/test_butano_single_battle_domain.py`

**Interfaces:**
- `battle_runtime_scene_request::campaign` is optional; legacy fixture callers keep their existing three-record input.
- `load_battle_campaign_from_sram` and `save_battle_campaign_to_sram` are the only cartridge I/O boundary.

- [x] **Step 1: 写 controller/campaign 失败集成测试**

从 campaign 投影 Naruto，执行 battle 41 结果和主技能修炼，再把 controller roster 合并，
断言 campaign 得到 LV2、EXP25、TP0 和 action 8 LV1。取消前的 campaign 保持逐字节相等。

- [x] **Step 2: 写 Python 失败接线测试**

断言 `run_battle_scene` 同时执行 party projection 与 merge，`main` 使用 EWRAM campaign/
save workspace 并在状态改变时保存。

- [x] **Step 3: 运行 RED**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_scene_results`

Run: `python3 -m unittest -q tests.test_butano_single_battle_domain`

Expected: 新断言失败，因为场景和 SRAM 尚未接线。

- [x] **Step 4: 实现最小接线**

场景入口从 campaign 建立三条 progression；所有 controller 存在后的退出路径先导出最终
roster，再由 `run_battle_scene` 合并。ARM adapter 使用两个静态 EWRAM slot，保存后读回
验证。`main` 只在档案变化时写 SRAM。

- [x] **Step 5: 运行 GREEN 并重构**

重复定向 C++/Python 测试，确认旧 fixture 调用仍保持兼容。

### Task 4: ARM 与冷启动 mGBA 验收

**Files:**
- Modify: `tools/butano/mgba_battle_41_shared_runtime.lua`
- Create: `tools/butano/mgba_battle_campaign_load.lua`
- Test: `tests/test_butano_battle_campaign_runtime_script.py`
- Modify: `tools/README.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/sequel-roadmap.md`

**Interfaces:**
- 第一次运行在隔离 `staged.gba` 旁生成 `staged.sav`。
- 第二次运行复用同一 staged ROM/SAV，不能读取或写入 `rom/base.sav`。

- [x] **Step 1: 写 Lua 契约失败测试**

要求两个脚本读取 exact ELF 符号地址，第一轮证明保存 generation 和 Naruto LV2/action8，
第二轮证明冷启动恢复相同值。

- [x] **Step 2: 运行宿主全量和相关 Python**

Expected: 全部已有与新增测试通过。

- [x] **Step 3: 运行受守卫 ARM 构建**

检查 map/ELF：两个槽和 campaign state 位于 EWRAM，SP 不接近 Maxmod 区域。

- [x] **Step 4: 运行两段受守卫 mGBA**

第一段完成 battle 41、训练并退出；第二段用同一 `.sav` 冷启动。两份 audit 必须绑定
ROM/ELF/SAV 哈希、generation、角色状态、错误码和最终 SP。

- [x] **Step 5: 更新持久文档**

记录协议、用户入口、恢复/损坏行为、哈希和未完成边界；路线图不得把自动档误报为完整章节。

### Task 5: 九格装备消费回写

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_campaign.h`
- Modify: `butano-sequel/game/include/konoha/battle_campaign_scene_progression.h`
- Modify: `butano-sequel/game/include/konoha/battle_scene_controller.h`
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_campaign_sram.h`
- Modify: `butano-sequel/game/src/battle_campaign_sram.cpp`
- Test: `butano-sequel/game/tests/test_battle_campaign.cpp`
- Test: `butano-sequel/game/tests/test_battle_scene_results.cpp`
- Test: `tests/test_butano_battle_campaign_runtime_script.py`

**Interfaces:**
- campaign 长期拥有每角色九个已装备忍具 ID；
- session 只持有战斗内副本，成功 resolver 清空对应槽；
- scene progression 在退出边界一次提交成长与装备，SRAM adapter 仍是唯一 cartridge I/O。

- [x] **Step 1: 写 controller/scene 失败集成测试**

真实 battle 41 controller 使用忍具 37 后导出 `67/11/0`；未部署队员装备必须保留。

- [x] **Step 2: 观察 RED**

先观察缺少 `equipped_tools_roster()` / `equipped_tools()` 的编译失败，再观察未部署队员
装备被清空，以及非法忍具 94 缺少原子拒绝。

- [x] **Step 3: 实现最小所有权链**

按 `original_character_id` 绑定玩家单位；从入场九格建立导出草稿，只覆盖真实部署单位；
campaign 在候选副本上同时校验成长与装备，全部合法才提交。

- [x] **Step 4: 宿主、ARM 与保存进程 GREEN**

聚焦领域/集成测试、Lua 契约和零缓存 devkitARM 构建通过；隔离 mGBA 从正式目录消费忍具
37，完成结果/训练并写出 generation 1。

- [x] **Step 5: 新进程零输入恢复**

完全关闭保存进程后复用隔离 ROM/SAV，frame 1 读取 generation 1、default 0 和
`67/11/0`。证据记录在
`notes/battle-campaign-tool-writeback-runtime-20260726.md`。
