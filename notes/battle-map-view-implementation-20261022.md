# 战场地图视图 —— 落地记录（2026-10-22）

> 规格：`notes/specs/battle-map-editor.md`（主代理定稿，693 行）。
> 事实依据：`notes/evidence/battle-map-render-facts-20261022.md`。
> 本文只记**落地结果**、**实测数字**与**需要别人配合的事**，设计不重复。

## 落地了什么

| 文件 | 状态 | 负责 |
|---|---|---|
| `rom-editor/js/maprender.js` | 新建 | 纯函数模块（**无 DOM**）：解码、像素合成、坐标换算、LZ77 解压、从 ROM 现解 |
| `rom-editor/js/modules/battle-map.js` | 新建 | 地图视图：版面 / 画布 / 标记 / 右侧面板 / 拖动 / 缩放 / 平移 / 兜底 |
| `rom-editor/css/battle-map.css` | 新建 | 本视图样式（`index.html` 里主代理已链好） |
| `rom-editor/tools/verify_battle_map.mjs` | 新建 | 无头验收（规格 §8 的 V1–V12 + 入口与文字 13 组） |
| `rom-editor/js/modules/battle.js` | 改 | 域首页「打开战场地图」按钮；关卡视图顶部「战场地图 →」按钮；阵营/改动计数挪到 common.js |
| `rom-editor/js/modules/common.js` | 改 | 新增 `BATTLE_LAYOUT` / `stageChangeCount` / `sideCell` / `mapAssetNotice` |
| `notes/battle-map-view-implementation-20261022.md` | 新建 | 本文 |

`routing.js`（`#battle/map/<关卡>/<变体>`）、`app.js`（面包屑）、
`index.html`（样式表）主代理已经提交（commit `595ae39c`），本轮没有再动。

## 交互一览（规格 §3.3 / §3.4）

| 操作 | 行为 | 落在哪 |
|---|---|---|
| 滚轮 | 整数档 1× / 2× / 3× / 4×（`passive: false`，否则页面会跟着滚） | `canvas.addEventListener('wheel', …, {passive:false})` |
| 双击画布 | 在「适应窗口」与「100%」之间切换 | `canvas` 的 `dblclick` |
| 适应窗口 / 100% / − / ＋ | 工具条四个按钮 | `.map-toolbar` |
| 按住空格拖拽 / 中键拖拽 | 平移（改 `scrollLeft/scrollTop`） | `.map-scroll` 的 `mousedown` + window 的 `mousemove/mouseup` |
| 拖动标记 | 物件 / 角色跟着指针吸附到格；松手才写回 | 标记的 `mousedown` → window 的 `mousemove/mouseup` |
| 点格子 | 选中该格，状态行给出坐标 / 通行值 / 格上的东西 | `canvas` 的 `click` |

- 画布是 1:1 画的，**缩放交给 CSS**（`.map-stage` 的 `transform: scale(z)`），
  所以换缩放档不用重画像素；命中测试用 `cellFromClientPoint`，它按
  `rect.width ÷ (cellW × 32)` 除掉显示缩放。
- 悬停 / 选中的格是两个覆盖在画布上的小框（`.map-cell-hover` /
  `.map-cell-selected`），不重画整幅图。
- 「改过的」标记以 **pack** 为准（`pack.changedStructureRecords`），
  视图不维护第二份改动状态（规格 §4.8）。

## 纯函数契约（规格 §5）

`maprender.js` 不 import 任何 DOM 相关的东西，所以无头脚本能直接 import 它做断言：

- `cellFromPixel(px, py, cellW, cellH)` / `pixelFromCell(x, y)` / `cellRect(x, y)`
- `cellFromClientPoint(clientX, clientY, rect, cellW, cellH)` —— **除以显示缩放**
  （`rect.width ÷ (cellW × 32)`），越界返回 null
- `decodeMapAsset(bytes, index)` —— 素材二进制 → `{cellW, cellH, gfx, palette, layer0,
  layer1, metatiles, terrain}`
- `renderMapImage(asset, opts)` —— 返回 `{width, height, pixels}`，`pixels` 是
  `Uint8ClampedArray(width × height × 4)` 的 **RGBA**（**不碰 canvas**）
- `assetPixelColor(asset, px, py)` —— 某个地图像素的 `[r, g, b, a]`
- `terrainAt(asset, x, y)` —— 某一格的通行值（只读）
- `decodeMapAssetFromRom(rom, stage)` —— 规格 §6.4 留的同构入口，**本轮真的实现了**
  （带一个 JS 版 LZ77 解压器），已证明与素材包逐字节一致
- `backgroundIds(pack)` / `renderBackgroundImage(rom, id)` —— 剧情底图

## 合成算法（照规格 §2.4 / §5，一个字没改）

```
每个像素 (px, py)：
  格行 = py >> 4，格列 = px >> 5，格内第几个组合图块 = (px >> 4) & 1
  meta = u16(layer0, (格行 × 格宽 × 2 + 格列 × 2 + 格内) × 2)
  entry = u16(metatiles, meta × 8 + (((py >> 3) & 1) × 2 + ((px >> 3) & 1)) × 2)
  图块内像素：col = px & 7，row = py & 7
  翻转：entry bit10 → col = 7 − col，bit11 → row = 7 − row
  像素值 = 4bpp 的一半字节（低半字节是左像素）；0 = 透明
  颜色号 = 像素值 + (entry >>> 12) × 16；颜色 = palette[颜色号 × 2] 的 BGR555
图层 1 只在自身非透明处覆盖图层 0
```

**踩过的坑**：图层是「格行 × (格列 × 2)」的矩阵，所以行下标要用**格行**（`py >> 4`），
不是像素行；写成像素行会把整张图错位（第一版就是这么错的，靠独立实现对照才发现）。

## 实测数字

- 1 格 = **32 × 16 像素**；第 40 关 = 9 × 22 格 = 288 × 352 像素。
- 46 张图（关卡 1..46）的格宽格高与 `map_table` 的 `raw_width >> 2` /
  `raw_height >> 1` **逐张相等**；`px_w === cell_w × 32`、`px_h === cell_h × 16`。
- 素材包（`content/maps/maps.bin.gz`，174,584 字节 gzip）与「从 ROM 现解」的结果
  **46/46 逐字节相同** ⇒ 导出器与渲染器没有各说各话。
- 渲染抽样（关卡 1 / 7 / 40 / 46，步长 3 像素，共 50,514 个取样点）与一份
  **独立实现**（照第三方 `features.js` 的算法重写，不共用 `maprender.js` 的代码）
  **0 处不同**。
- 底图可用的 id（从内容包推出来的，不写死）：**1–7、9–13** —— 判据是
  「三个指针都非零」且「第 4 个 u32 是色深标志（0 或 1）」；14..35 那一批的同一个
  位置是指针，是另一种 32 字节调色板形态。
- 剧情底图预览（4bpp，240 × 80）：从 ROM 现解，关卡 1 的底图 19,200 个像素全不透明，
  是一张平铺的剧情贴图；**8bpp 的底图（9..13）预览不了**（调色板只有 192 色，
  索引会越界），界面显示占位与说明。

## 写回

只走 `pack.setValue(structure, record, key, value)`，**没有新开通路**：

- 战场物件：`type` / `target` / `x` / `y`（16 槽）
- 角色出生点：`character_id` / `unit_flags`（阵营 = bit0）/ `x` / `y` / `facing` / `level`（12 槽）
- `map_table.background_id`（u8）

**整份 ROM 逐字节比对**（`buildRom` 的输出 vs `rom/base.gba`）：

- 改物件第 1 槽的 `x` → 整份 ROM **只有 1 个字节**不同（0x58954A = 7），
  同槽的 type / target / y 三个字节与原版逐字节相同。
- 改 `map_table[40].background_id` → 整份 ROM **只有 1 个字节**不同（0x53DE2C = 3），
  该记录其余 31 字节不变。

## 兜底（规格 §6.4）

素材文件缺失 / 拉取失败 / sha256 不符 ⇒ 地图视图**照常打开**：

- 画布区画**格线底图**（`.map-grid-fallback`，纯 CSS 网格，每 32×16 像素一格），
  行列号仍画在画布上；
- 顶部提示条：`未载入地图素材 —— 只显示格线与标记。` + 素材文件路径 + 「重新载入素材」按钮；
- **编辑功能一条不少**：战场物件仍是 16 行、角色出生点仍是 12 行。

## 需要主代理配合的改动

**已全部做完**：

- **`docs/sequel-roadmap.md`** 已补第八轮条目（按 AGENTS.md 的规则，路线图进度变化要同步）。
- `routing.js` 的 `#battle/map/<关卡>/<变体>` 解析与生成（commit `595ae39c`）。
- `app.js` 的面包屑：标签已改成规格 §3.1 的「第 N 关 · 战场地图」
  （变体在地图视图自己的工具条上）。
- `index.html` 的 `<link rel="stylesheet" href="css/battle-map.css">`。
- `pack.js` 的 `this.map_assets = data.map_assets || null;` —— 地图视图**优先**读
  `ctx.pack.map_assets`；没有这一行时它会自己去拉一次 `content/pack.min.json.gz`，
  功能一样，只是多下一次内容包。

**还剩一句提醒**：导出内容包时记得带上 `content/maps/maps.bin.gz`（§6.2 的已知代价）——
导出的 pack.json 里只有 `map_assets` 的**元数据**，没有那 170 KiB 的二进制。

## 明确没做（规格 §9）

- 不改地形 / 通行值（战斗加载器 `0x08068FF0` 根本不读 `+0x18`）；
- 不改图块 / 调色板 / 图层 / 组合图块（LZ77，改了要重压缩 + 改指针 + 找空闲区）；
- 不导入外部图片当地块；不扩图 / 改地图尺寸；
- 地图视图里不编辑战斗目标（条件参数里没有坐标），只给一个指向关卡视图的链接；
- 不在地图上画地形笔刷 / 复制底图图案；
- **换角色不自动拷角色模板**（那要改槽内 168 字节未解数据）—— 改成确认弹窗 + 说明；
- **一次拖动 = 两条撤销记录**（x 与 y 各一条）—— 状态行里写明「Ctrl+Z 撤销」；
  不改 `pack.js` 的公共撤销模型。

## 复现

```
node rom-editor/tools/verify_battle_map.mjs   # V1–V12（+ 入口与文字）
node rom-editor/tools/verify_syntax.mjs
node rom-editor/tools/verify_views.mjs
node rom-editor/tools/verify_sources.mjs
node rom-editor/tools/verify_labels.mjs
node rom-editor/tools/verify_pack.mjs
python -m unittest discover -s tests
```

验收脚本自带最小 DOM 桩，并把 `fetch` 桩住端上**真实的** `content/maps/maps.bin.gz` ——
所以 sha256 校验、gzip 解压、素材解码这一整条路都在跑，不是假的。
