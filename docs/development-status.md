# 当前开发状态

## 已具备

- 基础 ROM 已识别并校验
- 无头 `mGBA` 自动导航和截图流程可复跑
- OCR 时间线可自动生成
- 对白渲染链路已有明确结论：
  - 场景使用 `BG3`
  - `WRAM 0x00A900-0x00AA4A` 是最强对白 tilemap 工作缓冲候选
  - `VRAM 0x1800+` 是对应的 `BG3` screen block 区域
  - `VRAM 0x2000+` 更像字形 tile 上传区
- 对白写入路径已有稳定命中：
  - `WRAM` 写入者 `0x08066D74`
  - `VRAM glyph` 写入者 `0x08065F50`
  - `VRAM tilemap` 更像 DMA/system copy 到 `0x06001B00+`
- 已有首批函数级分析：
  - `0x08066D70` 是 `WRAM` tilemap 半字写入指令
  - `0x08065F4C` 是 `VRAM glyph` 半字写入指令
  - `0x08065EB8` 很像字形展开函数
  - `0x08065F84` / `0x080894DE` 是更值得继续追的上层调用点
  - `0x08096168` / `0x08096238` 已收敛为 RAM 记录准备层
  - `0x080968A0` 已成为开场对白路径上的运行时命中上层入口
- 续作内容工作区已建立
- ROM 构建入口已建立并验证可生成开发 ROM
- 高层 `dialogue` 导入补丁已接入构建流水线并验证可生成开发 ROM
- 地图/战斗配置已接入统一内容校验接口：
  - `tools/import_map.py`
  - `tools/import_battle_config.py`

## 章节流程（2026-03-31 新增）

- **章节状态结构体**：WRAM `0x020311D4`，offset +0x16 = 章节 slot ID
- **改变加载章节**：写 WRAM `0x020311EA`
- **章节配置表**：ROM `0x0853D910`，8 条目 × 32 字节
- **条目公式**：`0x0853D910 + 4 + chapter_id * 32`
- **初始化链**：`0x0808F618` → `0x08068DE4` → `0x080732B4` → `0x08068FF0`
- **重要修正**：配置表条目大小为 32 字节（非 16），`import_battle_config.py` 已更新 ✅

## P0 逆向工程阶段 — 全部完成（2026-04-01）

所有 7 个 P0 逆向工程步骤均已完成。详见 `docs/sequel-roadmap.md`。

### 新增完成（2026-04-01）

**P0-Step 5：资源提取**
- `tools/extract_tileset.py` — 8 个战斗地图 tileset → PNG 图集（LZ77 + BGR555 调色板）
  - 关键修正：battle config 字段顺序（tile_gfx_ptr 在 +0x00，dims 在 +0x1C，非之前文档所述）
  - palette_ptr (fields[4]) = 实际颜色；palette2_ptr (fields[5]) = 全 0x8000 属性数据
- `tools/extract_audio.py` — 扫描 DirectSound PCM 样本，找到 10 个（含 3 个 BGM），导出 WAV
- `notes/resource-locations.md` — 完整资源地址文档

**P0-Step 6：可变长对话**
- `tools/import_dialogue_var.py` — 字段名已与 `build_mod.py` 对齐，free_space 地址修正
- `tools/build_mod.py` — 新增 `dialogue_var` patch 类型
- `notes/free-space.md` — ROM 0x5DFBEC–0x5FFFFF 128 KB 空闲区域文档

**P0-Step 7：自动化测试**
- `tools/automated_test.py` — 17/17 测试全部通过（build/manifest/patches/encoding 4 个套件）

## 现在可以开展的工作

P0 逆向全部完成，下一阶段为**内容生产**：

1. 扩写 `sequel/content/story/episode-01.json`（剧情框架 → 完整场景）
2. 补齐 `sequel/content/text/episode-01-dialogue.md`（对话内容）
3. 建立 episode-02 等多章节内容模板
4. 启动网页编辑器开发（FastAPI + Vue，服务器 14.103.49.74）
