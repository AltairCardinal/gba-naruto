# 木叶战记续作 Roadmap

## 目标

把当前仓库从"已建立续作工作区和逆向基础"推进到"可以持续生产续作内容并稳定回写 ROM"的状态。

**执行策略：~~先完成逆向工程，再建网页编辑器。~~**

> **2026-10-20 — 该执行策略已被证伪并推翻。**
> 与第三方剧情编辑器包的对比复盘（`notes/why-external-editor-shipped-20261020.md`）显示：
> 对方在**未完成全量逆向**的前提下，用"复制原生条目 + 只改已知字段 + hook 原生函数"
> 的写回模型，产出了可用的编辑器与 26 场可玩 DEMO；而本项目走了 3.5 个月、
> 105 次提交、32 个结构全量静态入库，最终**可玩新内容为 0**。
>
> 改用：
> 1. **写回模型**：复制原生条目 + 覆盖式改写，未知字段 raw 兜底、不再要求命名
> 2. **验收标准**：按需动态证据（仅对本次改动涉及的结构），不再全量门禁
> 3. **工程形态**：单文件夹离线 ROM 编辑器，暂停 Web 服务/认证/多用户方向
> 4. **逆向定位**：作为功能产出的副产品，按需推进，不作为开工前置条件

> **2026-10-20 — 平台约束（macOS → Windows 迁移后）**
> 新机接入与验真记录见 `notes/windows-migration-20261020.md`。要点：
> - 两条工作线（`codex/reverse-engineering` / `codex/butano-foundation-research`）
>   已落地为独立工作树，工作区字节与 git blob 逐字节一致，交接文档钉死的
>   账本/审计器/spec 三个 SHA-256 本机复算吻合。
> - **本机 `core.autocrlf` 必须保持 `false`**：仓库用文件 SHA-256 当证据身份，
>   换行符一改全部钉死失效，且 `git status` 不会报脏。
> - **重活仍需 POSIX 宿主或等价改造**：账本重建 / formal / D0 采集链上的工具
>   用了 `os.O_DIRECTORY` / `dir_fd` 等 POSIX 原语（`tools/` 下 47 个文件），
>   其中 D0 契约钉死的两个模块不能直接改。mGBA 运行时链在本机需按 Qt +
>   `d8bad14b` 重建才能做 D0 采集。
> - 结论：**续作编辑器的开发不受此阻塞；逆向重活需要单独决策。**

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
- 真实角色定义表已定位：`0x54241C`，63×`0xB4`；formation character ID 经
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
| 战斗配置表 | ⚠️ 需修正 | ROM 表(0x53D910, 0x53F298) + WRAM 地址均已确认，但**条目 32 字节字段顺序已判定为错**，按 P0-Step 3.5 统一 |
| 章节流程入口 | ❌ 未定位 | 需 runtime 调试 |
| 剧情脚本 VM | ✅ 已实现 | 自研解码器，55 场景 0 问题；6184 行可读对白，见 P0-Step 3.5b |
| 战斗胜负判定条件表 | ✅ 已定位 | `0x594758`，7 种原版类型语义已证实，见 `notes/battle-tables.md` |
| 任务文字三表 | ✅ 已定位 | `0x348DAC` + `0x59AA5C`/`0x59D214`/`0x59E920`，138 条目已解出 |
| 游戏文本编码 | ✅ 已更正 | **自定义双字节字形码，不是 Shift-JIS**；见 `notes/font-encoding.md` |
| 文本写回路径 | 🔴 待修 | 仍按 cp932 编码中文，会写坏 ROM，工具清单见 font-encoding §7 |
| 资源提取（图片/音频） | ⚠️ 部分 | tileset 地址已知，提取未完成 |

### 🟡 续作内容创作（逆向完成后）
- episode-01 剧情源稿细化
- 多章节内容模板

### 🟢 网页编辑器（❌ 方向已修正 2026-10-20）

> 原计划："逆向工程 100% 完成后启动"。该前提已被证伪 —— 见
> `notes/why-external-editor-shipped-20261020.md`。
> 新方向：**单文件夹离线 ROM 编辑器**（原生条目复制 + 覆盖式改写），
> 暂停 FastAPI + Vue + 登录/多用户/WebSocket 平台路线。
>
> 若未来确需多人协作，以下既有方案可复用：
> - 技术方案：FastAPI 后端 + Vue 前端，部署于本服务器（14.103.49.74）
> - 功能：地图编辑器、角色编辑器、技能编辑器、剧情编辑器、道具编辑器等
> - 架构：多用户 WebSocket 协作编辑，ROM 在服务端操作

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
- ⚠️ **2026-10-20 修正**：`0x596D5C` 不是"图块描述符表"，而是**精灵动作表**
  `0x596CCC + id*144 + action*16` 的 id=1 行（`0x596CCC + 144 = 0x596D5C`），
  每行 4 个指针 = `(frames, animations, gfx, palette)`。我们原记录的
  "col0 嵌套描述符 / col3 调色板"实际就是这 4 个指针。详见
  `notes/external-konoha-workshop-gap-20261020.md` §2.2
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
- ✅ 真实角色定义表：`0x0854241C` / file `0x54241C`，63×`0xB4`；待建立提取器并迁移 units bank
- ✅ 战斗场景配置表：`0x0853D910` / file `0x53D910`，8 个有效条目 × 32 字节
  - ⚠️ **2026-10-20 修正**：条目格式为
    `+0 u16 原始宽 / +2 u16 原始高 / +4 tile gfx / +8 palette / +C 图层0 tilemap /
    +10 图层1 tilemap / +14 metatiles / +18 terrain / +1C 剧情底图ID`
    （宽/4、高/2 得图块网格）。terrain 解压长度 = 宽×高×2 已实测精确吻合。
    此前 `notes/battle-config-format.md` 与 `notes/chapter-flow-format.md` 的字段顺序
    互相矛盾且均与实测不符，需按 §2.1 统一
  - ptr1（+12/+10 图层 tilemap）：12 字节头 + 原始 tile 数据（u16/tile）
  - ptr2（+8 palette）：LZ77 压缩数据（解压后 384 字节）
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

### P0-Step 3.5｜吸收第三方剧情编辑器的逆向成果（2026-10-20）

**状态：🔴 刚发现，未开始实施**

**背景**：在 `D:\Downloads\火影忍者_木叶\木叶工房_剧情编辑器与后续DEMO_v0.4.4_无ROM`
发现一套第三方"剧情编辑器 + 剧情脚本编译器"。其基线 ROM 与本仓库 ROM
**SHA-256 完全一致**（`1198ece7…`），因此其全部地址/偏移/指令编号**可直接复用**。

**已在本仓库 ROM 上实测复核通过的关键结论**（复现：`tools/probe_external_re_claims.py`）：

| 结论 | 状态 |
|---|---|
| 地图表 `0x53D910` 32 字节字段顺序（+0 宽/+2 高/+4 gfx/+8 palette/+C/+10 图层/+14 metatiles/+18 terrain/+1C 底图ID） | ✅ 实测（terrain 解压 = 宽×高×2 精确吻合） |
| `0x596CCC` = 精灵动作表（id*144 + action*16 → frames/anim/gfx/pal） | ✅ 实测 |
| 头像表 `0x5A4DEC`（id*40+expr*8）+ 拼块表 `0x4643C0`（20 字节/块） | ✅ 实测 |
| 剧情脚本根表 `0x60C74`/`0x60D54`/`0x60E34`/`0x60EF0` + 指令表（0x01/0x02/0x03/0x07/0x15/0x1A/0x1B/0x22/0x32/0x34/0x36…） | ✅ 实测（原版脚本字节核对） |
| 任务文字索引表 `0x348DAC`（u8×48，每场景 3 条）+ 三张文本表 `0x59AA5C`/`0x59D214`/`0x59E920` | ✅ 实测 |
| 战斗条件表 `0x594758`（stage*0xCC + sub*0x44，2 组 × 4 条 × 8 字节） | ⚠️ 结构可用，类型 0..9 逐条语义待我们确认 |
| 战斗单位槽 stride 468（`0x020240C0`）、队员池 stride 188（`0x02022E34`） | ✅ 与既有结论一致 |

**本仓库完全没有、而对方已实现的三块（P0 缺口）**：
1. **剧情脚本 VM 图解码器**（`E.graph`：带 op/length/targets/text/offset 的节点图）
   → 没有它就没有剧情编辑器
2. **战斗胜负判定条件表读写**（`0x594758`）
3. **任务文字三表 + 索引算法**

**方法论解锁点**：对方用 **mGBA 0.11 C API**（`tools/gba_probe.c`）在 C 层驱动模拟器，
**可以注入按键**。我们长期卡住的 "mGBA headless 无法注入按键" 属工具层限制，可绕过。

**必须先裁决的冲突（C1~C4）**：
- C1 地图表字段顺序错（`notes/battle-config-format.md` + `notes/chapter-flow-format.md` 互相矛盾）
- C2 `0x596D5C` 被误认作图块描述符表（`notes/map-format.md`）
- C3 `0x599634` 被误认作 Sappy 音频索引表，实测是**忍具名称文本指针表**
  （`notes/dynamic-verification-audit.md`、`notes/patch-generator-audit.md`、
  `docs/structure-field-semantics.md` #22 均需复核）
- C4 `notes/battle-config-format.md` 的单位结构 236 字节已过期（应为 468）

**交付物**：
- ✅ `notes/external-konoha-workshop-gap-20261020.md` — 完整差集清单与验证记录
- ✅ `tools/probe_external_re_claims.py` — 可复现探针（本仓库自写）
- ✅ `third_party/konoha-workshop/` — 第三方自编代码已 vendored（155 文件，1.28 MB，
  MIT 授权部分；原作音乐/字形位图/参考美术/BPS 补丁已按许可排除）。
  **定位为只读逆向知识库**，改动请在本仓库另起实现，详见其 README
- ✅ **成果已吸收为自有实现**（见下方"已吸收"小节）
- ⬜ 剧情脚本 VM 解码器（`tools/decode_story_script.py` + `notes/story-script-vm.md`）
- ⬜ `notes/battle-condition-table.md` — 条件表结构与类型语义
- ⬜ `notes/mission-text-tables.md` — 任务文字三表

### P0-Step 3.5b｜已吸收：字形码 + 剧情 VM + 战斗表（2026-10-20）

**状态：✅ 核心三项已完成并静态验证**

第三方包带来的最大收获不是那几个地址，而是它的**字形码映射**。
用它做指纹校验后确认了一个颠覆性结论：

> **游戏文本是自定义双字节字形码，不是 Shift-JIS。**
> 本仓库此前把全部游戏文本当 cp932 处理，产出的都是乱码。

| 吸收项 | 本仓库实现 | 结果 | 笔记 |
|---|---|---|---|
| 字形码映射 + FNV-1a 指纹校验 + 编码器 | `tools/konoha_font.py` | 26/26 段指纹匹配；4261 码位 0 未解析 | `notes/font-encoding.md` |
| 往返验证 + 旧手工映射表判定 | `tools/font_roundtrip.py` | 真实文本 `encode(decode(x))==x` 字节级一致 | 同上 |
| 剧情脚本 VM 解码器 | `tools/decode_story_script.py` | 55 场景 × 4 根表，**0 问题** | `notes/story-script-vm.md` |
| 可读剧本导出 | `tools/dump_story_text.py` | **6184 行可读中文对白** | 同上 |
| 战斗条件表 / 任务文字三表 / 角色槽 | `tools/extract_battle_tables.py` | 86 条件条目 / 138 任务条目 / 85 角色条目 | `notes/battle-tables.md` |

**关键收获**：
- 62 个角色名全部从 ROM 姓名表解出（含"岸本齐史"彩蛋）
- 战斗条件 7 种原版类型语义由原版说明文字直接证实
  （type 10 是第三方新增扩展，**不是原版能力**）
- 任务标题/说明/提示三表此前完全无人解出

**遗留最高优先级风险**：写回路径仍按 cp932 编码中文，会写坏 ROM。
受影响工具清单见 `notes/font-encoding.md` §7。

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
