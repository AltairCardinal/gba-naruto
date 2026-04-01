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
- Phase 1/2/6 框架级完成

### 🔴 核心瓶颈（P0 — 逆向工程阶段）

| 目标 | 状态 | 备注 |
|------|------|------|
| tilemap 布局数据 | ✅ 已定位 | 32x32 grid at 0x14D000+ |
| 战斗配置表 | ✅ 已定位 | ROM 表(0x53D910, 0x53F298) + WRAM 地址均已确认，patch 生成可用 |
| 章节流程入口 | ✅ 已定位 | 静态分析完成，WRAM 0x020311EA 写入控制章节 ID |
| 可变长对话 | ✅ 已完成 | 128 KB 空闲区域 0x5DFBEC, pointer_redirect pipeline 可用 |
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

### P0-Step 3｜定位战斗配置表（Phase 5 收尾）

**状态：✅ 已完成**（ROM 数据表已定位，patch 生成可用，runtime 验证受限于 headless 环境）

**已确认 ROM 数据表：**
- ✅ 单位 ID 映射表：`0x0853F298` / file `0x53F298`，u16[64]，映射 slot → character ID
- ✅ 战斗场景配置表：`0x0853D910` / file `0x53D910`，8 个有效条目 × **32 字节**（2026-03-31 修正）
  - 访问公式：`entry_ptr = 0x0853D910 + 4 + chapter_id * 32`
  - 条目格式：u32 dim(h|w), u32 tile_gfx_ptr, u32 tilemap_ptr, u32 tilemap_alt_ptr, u32 extra_ptr, u32 palette_ptr, u32 palette2_ptr, u32 flags
- ✅ 状态机函数指针表：`0x0853F1C0` / file `0x53F1C0`，u32[60]，指向 0x0812Fxxx
- ✅ WRAM 分配表：`0x0853D848` / file `0x53D848`

**已确认 WRAM 战斗数据地址：**
| WRAM 地址 | 大小 | 说明 |
|---|---|---|
| `0x0201BE2A` | 可变 | 单位计数 + team 计数 |
| `0x02021E2C` | 234*N | 单位查找表基址 |
| `0x02024294` | 234*25 | 单位数组 |
| `0x020240C0` | 0x17C4 | 主战斗数据 |
| `0x02022E30` | 0x127C | 战斗状态 |
| `0x02026804` | 8 字节 | 战斗控制标志 |

**交付物：**
- ✅ `notes/battle-config-format.md` — 完整版（ROM 表、WRAM 布局、LZ77 格式、代码引用）
- ✅ `notes/unit-skill-addresses.md` — 完整版（单位 ID 表、场景配置、状态机函数）
- ✅ `notes/unit-id-mapping-analysis.md` — 完整版
- ✅ `notes/battle-scenario-config.md` — 完整版（8 个场景条目解析）
- ✅ `tools/import_battle_config.py` — 可生成 ROM patches + WRAM cheat patches
- ⚠️ runtime WRAM dump 受限于 headless 环境（无 key input 注入），已记录在案

---

### P0-Step 4｜定位章节流程入口（Phase 3 收尾）

**状态：✅ 已完成**（静态分析法，2026-03-31）

**发现：**
- 章节状态结构体：WRAM `0x020311D4`，+0x16 存章节/战斗 slot ID
- 要改变加载的章节：写 `0x020311EA`（= base + 0x16）
- 章节配置表：ROM `0x0853D910`，8 条目 × **32 字节**（之前误判为 16 字节，已修正）
- 条目访问公式：`entry_ptr = 0x0853D910 + 4 + chapter_id * 32`
- 初始化调用链：`0x0808F618` → `0x08068DE4` → `0x080732B4` → `0x08068FF0`（地图加载器）
- 地图加载器 `0x08068FF0` 读取 tile graphics / tilemap / palette，通过 DMA 写入 VRAM

**关键修正：**
- ROM 条目大小 = **32 字节**，非 16 字节，影响 `import_battle_config.py` 中的 patch 计算
- `0x0201BE2A/B` 是 tile display slot，非 unit count（功能重新解释）

**交付物：**
- ✅ `notes/chapter-flow-format.md`（完整版）
- ✅ `notes/chapter-entry-points.md`（完整版）
- ✅ `notes/battle-config-format.md`（已修正条目大小）
- ✅ `tools/import_battle_config.py` — 已更新为 32 字节条目格式

---

### P0-Step 5｜资源提取链路（图片/音频）

**状态：✅ 已完成**（2026-04-01）

**已完成：**
- ✅ `tools/extract_tileset.py` — 读取战斗配置表 8 条目，LZ77 解压 tile_gfx + palette，导出 PNG 图集
  - 输出：`build/tiles/battle_tileset_00.png` … `battle_tileset_07.png`
  - 格式：8×8 4bpp tiles，32 列图集，×2 缩放，BGR555 调色板（bit15 mask 修正）
  - 调色板来源：fields[4] (palette_ptr) - LZ77 压缩 BG 调色板（16 sub-palettes × 16 色）
  - 验证：entry 0 = 672 tiles，97% 非零像素，PNG 21 KB，颜色正确（地形棕绿色）
- ✅ `tools/analyze_tile_table.py` — 分析 0x596D5C 描述符表的多级指针链，用于 sprite 格式研究
- ✅ `notes/resource-locations.md` — 已记录关键资源地址

**交付物：**
- ✅ `tools/extract_tileset.py` — 战斗地图图集 PNG 导出（8 场景 × LZ77 tile_gfx + palette）
- ✅ `tools/extract_audio.py` — 扫描 DirectSound PCM 样本，导出 WAV 文件
- ✅ `tools/analyze_tile_table.py` — 0x596D5C 多级指针链分析工具
- ✅ `notes/resource-locations.md` — 完整资源地址文档

**关键发现：**
- fields[4] (palette_ptr) = 实际 BG 调色板（LZ77 压缩，BGR555，bit15=透明标志需 mask）
- fields[5] (palette2_ptr) = 全 0x8000，为属性/透明度数据，非颜色调色板
- 32 字节条目实际字段顺序（修正文档）：tile_gfx_ptr, tilemap_ptr, tilemap_alt_ptr, extra_ptr, palette_ptr, palette2_ptr, flags, packed_dims

---

### P0-Step 6｜可变长对话（Phase 2 收尾）

**状态：✅ 已完成**（2026-03-31）

**发现：**
- ROM 末尾 0x5DFBEC–0x5FFFFF 为 ~128 KB 的 0xFF 填充空闲区域
- 同长替换与变长 redirect 均已实现

**交付物：**
- ✅ `notes/free-space.md` — 空闲 ROM 区域验证文档（起始地址、大小、填充值）
- ✅ `tools/import_dialogue_var.py` — 变长 redirect patch 生成（字段名与 build_mod.py 对齐）
- ✅ `tools/build_mod.py` — 新增 `dialogue_var` patch 类型支持

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

```
P0-Step 1（mGBA调试） ✅
       ↓
P0-Step 2（tilemap） ✅
       ↓
P0-Step 3（战斗配置） ✅（ROM 表已定位，条目格式已修正为 32 字节）
P0-Step 4（章节流程） ✅（章节流程入口已定位，WRAM/ROM 地址均已确认）
P0-Step 5（资源提取） ✅（tileset PNG + audio WAV 均已完成）
P0-Step 6（变长对话） ✅（128 KB 空闲区域确认，pipeline 完整）
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
