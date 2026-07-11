# 木叶战记续作 Roadmap

## 目标

把当前仓库从"已建立续作工作区和逆向基础"推进到"可以持续生产续作内容并稳定回写 ROM"的状态。

**执行策略：先完成逆向工程，再建网页编辑器。**

---

## 现状总览

### ✅ 已打通
- 对白 → ROM 写入闭环（dialogue patch pipeline）
- 5 段对话已验证写入 ROM
- 构建流水线支持 5 种 patch 类型（bytes/dialogue/pointer_redirect/map/battle_config）
- mGBA headless 调试环境稳定（`tools/mgba-headless-snapshot.py`）
- mGBA PC/读取探针已加入：断点真实命中后可在同一上下文抓取 ROM 与 WRAM；
  复位 PC smoke test 已通过，地图 loader `0x08068FF0` 仍需可复现导航/有效状态
  才能将 maps 提升为动态验证
- 网页 WASM 首战导航与编成探针已可复现：单位槽 1 坐标 `(4,4)` 唯一对应
  positions group 40 / variant 0 / record 0（ROM `0x588CA8`），positions 已完成
  runtime 验证
- WASM 探针现会记录 `0x02026804` 的 8 字节控制区及 `0x02026805` 标识；一次
  相同按键计数重放未进入战斗，证明下一步需改为画面/内存状态驱动导航，maps
  暂不升级验证等级
- 独立重放再次得到 slot 1 `(4,4)`，且 `0x02026805 = 40` 与 positions group 40
  一致；maps 第 40 行为 `0x53DE10`（36×44），但尚缺字段消费因果证据，仍保持
  code 验证
- units 旧结论已撤销：`0x0806E654` 实为读取单位 x/y，`0x53F298` 唯一消费者
  将其作为 u16 偏移查找；legacy units 回写已安全禁用，真实角色记录映射待定位
- 真实角色定义表已定位并迁移到 units bank：`0x54241C`，63×`0xB4`；
  `tools/extract_character_definitions.py` 可重复提取；formation character ID 经
  `0x02022E34` 模板池复制到 `0x1D4` 战斗槽，待成功探针样本闭合动态证据
- maps width/height 消费链已定位到 `0x0201BE28..2B`；首战第 40 行预期
  `[36,44,9,22]`，探针已加入读取，待稳定状态导航取得结果
- chapters、skills、story beats、audio 四类无 ROM 身份的 legacy 危险回写已禁用，
  只输出 unmapped 诊断；lossless `rom_*` mirror 继续作为安全写回入口
- Phase 1/2/6 框架级完成

### 🔴 核心瓶颈（P0 — 逆向工程阶段）

| 目标 | 状态 | 备注 |
|------|------|------|
| tilemap 布局数据 | ✅ 已定位 | 32x32 grid at 0x14D000+ |
| 战斗配置表 | ✅ 已定位 | ROM 表(0x53D910, 0x53F298) + WRAM 地址均已确认，patch 生成可用 |
| 章节流程入口 | ❌ 未定位 | 需 runtime 调试 |
| 资源提取（图片/音频） | ⚠️ 部分 | tileset 地址已知，提取未完成 |

### 🟡 续作内容创作（逆向完成后）
- episode-01 剧情源稿细化
- 多章节内容模板

### 🟢 网页编辑器（逆向工程 100% 完成后启动）
- 技术方案：FastAPI 后端 + Vue 前端，部署于本服务器（14.103.49.74）
- 功能：地图编辑器、角色编辑器、技能编辑器、剧情编辑器、道具编辑器等
- 架构：多用户 WebSocket 协作编辑，ROM 在服务端操作

---

## 逆向工程路线图

### P0-Step 1｜稳定 mGBA 调试环境
**状态：✅ 已完成**

- `tools/mgba-headless-snapshot.py`：snapshot / watch / diff 三种模式可用
- `docs/next-action-plan.md`：方案 A 执行结果已记录
- 验证：watchpoint 命中 PC=0x08060FD2，cycle=182801696

---

### P0-Step 2｜定位 tilemap 布局数据（Phase 4 收尾）

**状态：✅ 已完成**

**现状：**
- Tile 描述表 `0x596D5C` 已完整分析（312行×16字节，每行含 tile data/attribute/layout/palette 4 个指针）
- tilemap 布局数据（2D 瓦片 ID 网格）已定位！

**发现：**
- 多个 tilemap 数据区位于 ROM: 0x14D000, 0x195000, 0x1CB000 等
- 格式：2字节/条目，32×32 网格 (1024条目，2048字节)
- 编码：低10位为 tile ID (0-311)， bits 10-15 为 flip/调色板属性

**方法：**
1. 用静态分析扫描 ROM 寻找 tile ID 有效范围内的 2D 网格模式
2. 通过对比验证找到多个有效的 tilemap 数据区

**交付物：**
- `notes/map-format.md`（完整版）✓
- `notes/map-addresses.md`（完整版）✓
- `tools/import_map.py`（完整 patch 生成逻辑）✓

---

### P0-Step 3｜定位战斗配置与角色定义

**状态：⚠️ 部分完成**（positions 已运行时验证；maps 与角色定义仍待动态闭环）

**已确认 ROM 数据表：**
- ❌ 旧 `0x0853F298` 单位 ID 映射结论已撤销；唯一消费者把它作为 u16
  对象/渲染偏移查找，legacy 回写已禁用
- ✅ 真实角色定义表：`0x0854241C` / file `0x54241C`，63×`0xB4`；
  `tools/extract_character_definitions.py` 已建立，`sequel/content/units/bank.json`
  已迁移；仍待 runtime 样本把战斗槽 character ID 闭合回该 ROM 记录
- ✅ 战斗场景配置表：`0x0853D910` / file `0x53D910`，8 个有效条目 × 16 字节
  - 条目格式：u16 tiles_x, u16 tiles_y, u32 ptr1, u32 ptr2, u16 flag, u16 extra
  - ptr1：12 字节头 + 原始 tile 数据（u16/tile）
  - ptr2：LZ77 压缩数据（解压后 384 字节，调色板/属性数据）
- ✅ 状态机函数指针表：`0x0853F1C0` / file `0x53F1C0`，u32[60]，指向 0x0812Fxxx
- ✅ WRAM 分配表：`0x0853D848` / file `0x53D848`

**已确认 WRAM 战斗数据地址：**
| WRAM 地址 | 大小 | 说明 |
|---|---|---|
| `0x0201BE28` | 4 字节 | map width/height 及 `>>2/>>1` 派生尺寸 |
| `0x02021E2C` | 网格相关 | 单位坐标查找表基址 |
| `0x020240C0` | `0x17C4` 总区间；`0x1D4*N` | 主战斗数据/单位数组物理基址（单位 stride 468 字节） |
| `0x02024294` | `0x1D4` | 第一个可分配/常用单位槽（slot 1） |
| `0x02022E34` | 24×`0xBC` | 角色模板池；模板 `+0` 为 character ID |
| `0x02026804` | 8 字节 | 战斗控制标志 |

**交付物：**
- ✅ `notes/battle-config-format.md` — 完整版（ROM 表、WRAM 布局、LZ77 格式、代码引用）
- ✅ `notes/unit-skill-addresses.md` — 完整版（单位 ID 表、场景配置、状态机函数）
- ✅ `notes/unit-id-mapping-analysis.md` — 完整版
- ✅ `notes/battle-scenario-config.md` — 完整版（8 个场景条目解析）
- ✅ `tools/import_battle_config.py` — 可生成 ROM patches + WRAM cheat patches
- ✅ `tools/extract_positions.py` — 从 ROM `0x5461C4` 编成矩阵可复现提取 48×3×12 条记录；记录 `+2/+3` 已静态确认为初始 x/y
- ✅ positions ROM→WRAM 静态链路：`0x0806E41E/0x0806E71E → 0x0806AC70 → 0x0806AA64`；单位 stride 已纠正为 `0x1D4`
- ✅ positions 编辑/回写链：通用 ROM mirror 导入 `rom_positions` 1728 行并保留完整 `0xB8` 原始记录；构建器验证 index、ROM offset 与长度后写回真实矩阵
- ⚠️ 旧 `unit_positions` CRUD 仅是运行时编辑概念，没有一行一 ROM 地址证据，不计入真实回写完成度
- ✅ runtime WRAM dump 已通过网页 WASM 探针取得并与 ROM 编成记录唯一关联；CLI
  headless 仍无按键注入与 PC/LR 联合采集能力

---

### P0-Step 4｜定位章节流程入口（Phase 3 收尾）

**状态：⚠️ 部分完成 - 静态分析完成，runtime 验证受限于环境**

**已完成：**
- 静态分析：遍历 38 个 late-ROM 表候选，全部为视觉/资源描述表
- 代码引用分析：定位到 9 处对战斗配置表（0x0853D910, 0x0853F298）的引用
- 章节 ID 序列搜索：在 0xBD713, 0xC1717 等处发现 u16(1,2,3...) 模式，但未找到明确配置表

**Runtime 验证尝试：**
- 尝试 1：加载 savestate - 失败（所有 save 文件为 0xFF，未初始化）
- 尝试 2：设断点 0x080894DE - 未命中（游戏卡在 UI 循环 0x085CCDxx）
- 尝试 3：设断点 0x0806E654 - 未命中（无用户输入无法到达战斗）
- 尝试 4：frame advance + breakpoint - 停留在 video/UI 子系统，无法进入主游戏逻辑

**环境限制：**
- mgba-sdl 0.10.1 缺少 `--script` 参数支持
- CLI 调试器无法注入按键输入
- 无有效 savestate 文件

**交付物：**
- `notes/chapter-entry-points.md` - 运行时验证尝试记录 + 静态分析
- `notes/chapter-flow-format.md` - 格式分析（待 runtime 验证）

---

### P0-Step 5｜资源提取链路（图片/音频）

**现状：**
- tileset 地址已知（`0x596D5C` 的 tile data 指针），提取脚本未完成

**方法：**
1. 从 `0x596D5C` 提取 tileset 指针，用 Python 导出为 PNG
2. 搜索音频数据段（MIDI-like 结构 或 PCM 段）
3. 编写 `tools/extract_tileset.py` 和 `tools/extract_audio.py`

**交付物：**
- `tools/extract_tileset.py`
- `tools/extract_audio.py`
- `notes/resource-locations.md`

---

### P0-Step 6｜可变长对话（Phase 2 收尾）

**现状：**
- 同长替换可行，变长 redirect 需要已验证的空闲 ROM 区域

**方法：**
1. 用 mGBA 在游戏运行时检测 ROM 空闲区域（写入后读回为 0xFF 且不被读的地址）
2. 验证后实现 pointer_redirect 策略

**交付物：**
- 空闲 ROM 区域验证文档
- `import_dialogue_var.py`（变长 redirect patch 生成）

---

### P0-Step 7｜全面测试闭环

**现状：**
- `docs/testing-checklist.md` 已建立
- mGBA + OCR 验证流程未完成

**方法：**
1. 搭建自动化验证：`build_mod.py` → mGBA 加载 → OCR 比对 → 报告
2. 每完成一个格式的 patch 生成，都要跑一遍 checklist

**交付物：**
- `tools/automated-test.py`（mGBA + OCR 验证）
- 所有格式的验证报告

---

## 当前推荐顺序

### 2026-07-10 Positions 与构建安全更新

- positions 真实 ROM 来源已更正为 `0x5461C4` 编成矩阵，记录 `+2/+3`
  为初始 x/y；旧 `0x53D914` 结论已撤销。
- 新增可重复提取器 `tools/extract_positions.py`，共提取 `48×3×12=1728`
  条完整 `0xB8` 记录，并通过 `rom_positions` 无损回写。
- 单位物理数组基址是 WRAM `0x020240C0`，stride `0x1D4`；
  `0x02024294` 是 slot 1。
- 补丁冲突门禁发现旧 battle-config 模板会覆盖 `0x547934+`；
  已停止将未映射的 `scenario_id` 当 ROM 索引。
- 32/32 bank 已通过基准 ROM 字节一致性门禁；动态消费路径验证仍在进行。
- 新增只读 WASM 导航/WRAM 轮询探针 `play/_scripts/runtime-formation-probe.js`：
  可按 START → 新游戏 → 连续 A 计划导航，读取 `0x020240C0` 单位数组，并将
  `+0xC4/+0xC5` 坐标与 positions bank 匹配；已验证 core 就绪门禁与真实 WRAM
  读取。后续真实部署运行已进入首战，两次观察到 slot 1 `(4,4)` 并唯一匹配
  group 40 / variant 0 / record 0，因此 positions 已升级为 `runtime_verified`。
  当前导航继续扩展 battle-control、map runtime、画面分类和转场等待，用于闭合
  maps 与真实角色定义的运行时证据。

### 2026-07-10 Bank 元数据审计基线

- 新增 `tools/audit_re_completion.py`，可重复检查 32 个 `sequel/content/*/bank.json` 的表偏移、格式字段、条目、验证标签和 Markdown 文档覆盖。
- 审计产物为 `notes/re-completion-audit.json` 与 `notes/re-completion-audit.md`。
- 首次审计结果为 23/32；随后已纠正 7 个偏移错误并从校验过的基准 ROM 重新提取，同时补齐 3 个格式描述。当前元数据检查为 32/32，但这仍不代表动态语义或真实回写完成。
- 验证分布现为 30 个 `static_verified`、1 个 `code_verified`、1 个
  `runtime_verified`（positions）；仍不能作为“100% 完成”的单独证据。

### 2026-07-10 u32 指针表回写进展

- 新增带索引边界、48 Mbit ROM 地址范围、Thumb bit 和数据指针对齐检查的通用
  u32 指针表真实回写 helper，并补充 6 项单元测试。
- `map_events` 与 story B–E 当前可生成 88 个真实表补丁，不再写 audit 保留区。
- 安全检查发现 `rom_battle_handlers` 和 `rom_map_sprites` 共 61 行 DB 数据使用陈旧
  `_rom_offset`，现已拒绝回写；下一工作周期需从 `rom/base.gba` 重新导入并验证。
- `battle_encounters` 是混合值表；`cutscene_scripts` 的声明边界含越界值，两者仍需
  重新确认格式，未计为完成。详见 `notes/u32-pointer-real-writeback-20260710.md`。
- 第二批已把 data table A/B、function pointers、menu UI、resource pointers、
  sprite animations、tile assets 共 135 行转换为带严格校验的真实 ROM 回写；旧
  audit-only 不可达代码已删除。palette 因表冲突证据不足仍保持隔离。

```
P0-Step 1（mGBA调试） ✅
       ↓
P0-Step 2（tilemap） ✅
       ↓
P0-Step 3（战斗配置） ✅（ROM 表已定位，patch 生成可用）
P0-Step 4（章节流程）
P0-Step 5（资源提取）
P0-Step 6（变长对话）
P0-Step 7（测试闭环）
       ↓
100% 逆向覆盖
       ↓
网页编辑器开发
```

---

## 不该现在做的事

1. 不要现在开始写大量剧情 —— 格式还没定，内容随时可能废弃
2. 不要现在开始建网页编辑器 —— 等逆向覆盖到 80%+ 再动手
3. 不要把手工十六进制修改当正式开发流程 —— 一切要走 pipeline

---

## 网页编辑器架构（逆向完成后）

**技术方案：** FastAPI + Vue + SQLite

**服务器：** 14.103.49.74:443（Debian 12，2核/4GB）

**架构图：**
```
用户浏览器 (Vue)
    │ HTTPS
[FastAPI 服务]
    │
 ┌──┼──┐
 │     │
SQLite  ROM文件
(队列)  (本地)
 │
WebSocket
(协作编辑)
```

**功能模块（逆向完成后按序开发）：**

| 模块 | 说明 |
|------|------|
| 对话编辑器 | 文本表单，调用 import_dialogue.py |
| 地图编辑器 | Canvas 瓦片地图，调用 import_map.py |
| 角色编辑器 | 数值表单，调用 import_battle_config.py |
| 技能编辑器 | 效果链配置 |
| 道具编辑器 | 表格编辑 |
| 剧情编辑器 | 分支对话树 |
| 构建验证 | build_mod.py 输出可下载 patch ROM |

**优先级：** 对话 > 地图 > 角色 > 技能 > 道具 > 剧情
