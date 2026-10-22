# 原版战场覆盖层（BG2）的**屏幕地面真相** + 残差归因（逐像素）

日期：2026-10-21（第 26 轮）
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
逆向树 `/Users/altair/github/gba-naruto-reverse` **只读**
Python 一律 `/usr/local/bin/python3`（3.14.3）。**本轮未运行 mGBA 跑原版**（只跑了一次重制侧 GPU 转储）。

## 0. 本轮做了什么（以及为什么）

第 25 轮结束时，master 合并已落地，但合并窗口期并行写入的 **在飞覆盖层实现（实测 13,338 像素，比基线 2,917 更差）**
被保全快照提交进树里 ⇒ 工作树停在**比基线更差**的状态。

本轮按顺序做了三件事：

1. **回滚在飞实现**，把工作树恢复到 2,917 基线：
   ```bash
   git restore --source=68ab647a --staged --worktree -- \
       butano-sequel/game/include/konoha/battle_range_ui_style.h \
       butano-sequel/game/src/battle_runtime_scene.cpp
   git rm tests/test_s49_overlay_implementation.py
   bash tools/butano/build.sh
   ```
   ⇒ ROM 回到 `02bf3573118f4b43d58189db6816a5d0d2d47190f23e0f1d3c6abd5dbb217803`
   （与 2,917 基线**逐字节相同**）。
   保留了 `tools/generate_butano_battlefield_overlay.py` 与它生成的
   `generated_battle_battlefield_overlay_content.h`（两者都对着已签 manifest 失败关闭，是可复用资产），
   只删掉了断言一个**并不存在**的实现的 WIP 测试。
2. **补上 provenance 审计缺口**：新生成器没有声明 `GENERATED_PRODUCTS`，
   审计把它报成「生成器未登记 ⇒ 产物无法核对」。
   补声明后审计 `exit 0 / problems: none`。
3. **把覆盖层的「屏幕地面真相」算出来并钉死**（本文件），并且**把 2,917 残差逐族归因**。

## 1. 机制（已闭合，本轮再次独立验证）

| 事实 | 证据 |
| --- | --- |
| 原版 BG2 = 4bpp、16 色调色板 **bank 12** | `artifacts/s49-original-movegrid-tilemap-v1/bg2-palette.bin`（32 B = 16 色）；tilemap 全部项 bank=12、无 hflip/vflip |
| BG2 tilemap = 32×32 项 × 16 bit 小端 | `artifacts/s49-original-battlefield-overlay-v1/bg2-tilemap-*.bin`（2048 B） |
| BG2 图块 = 32 块（256..287），4bpp，**每字节 2 像素、低半字节为左** | `bg2-tiles-4bpp.bin`（1024 B = 32×32 B）；实测解出 6 个图族 |
| 滚动 `hoff=240 / voff=24` ⇒ 可见窗口 30×20 图块 = **整屏 240×160** | `visible-cells.json` |
| 查表：屏幕格 (sx,sy) → tilemap 格 `(((sx+240)//8)%32, ((sy+24)//8)%32)` | 同上 |
| 混合：**alpha，EVA=EVB=10/16** ⇒ 结果 = `(BG2 + BG1) × 10/16` | 见 §2 的代数反解 |
| 调色板项 0 = `0x0000` ⇒ 该像素**透明** | `bg2-palette.bin` 首项为 0 |

**独立验证（本轮亲自做，不采信任何代理自述）**：
原版 `walk-original-a24/step-19-A.png` 在覆盖层青像素（调色板 2 = RGB (24,205,255)）处，
实测屏上色为 (123,236,190)。按 `(BG2+BG1)×10/16` 反解底图色：

```
bg1.r = 123×16/10 − 24 = 173    bg1.g = 236×16/10 − 205 = 173    bg1.b = 190×16/10 − 255 = 49
⇒ 底图 = (173,173,49)
```

而 step-16/step-17（覆盖层未开）同一区域实测底色**正是 (173,173,49)** ⇒
**混合公式、滚动、调色板三项同时坐实**。

## 1.5 ⚠️ 第 26 轮更正：**GBA 4bpp 的半字节顺序写反了**

仓库里（`notes/s49-movegrid-overlay-rule-20261020.md`、`docs/konoha-senki/01-battle-s49.md` 4.3.97.3、
`notes/s49-movegrid-overlay-assets-20261020.md`）一直写着「**高半字节 = 左像素**」——
**这是错的**。正确的是「**低半字节 = 左像素、高半字节 = 右像素**」。

### 怎么证出来的（不靠文档，靠原版像素）

原版 movegrid 帧在受阻区里，同一个 8 px 图块内相邻两像素：

| 屏幕像素 | 原版实测色 | 反解出的覆盖层色 | 对应图块字节 |
| --- | --- | --- | --- |
| x=46 | (154,154,76) | (74,74,74) = 调色板 10（'a'） | 第 4 字节 = `0xBA` |
| x=47 | (128,128,51) | (32,32,32) = 调色板 11（'b'） | 第 4 字节 = `0xBA` |

第 4 字节覆盖 x=6 与 x=7；`0xBA` 的**高半字节是 'b'、低半字节是 'a'**。
x=46（局部 x=6）显 'a' ⇒ **低半字节在左**；x=47（局部 x=7）显 'b' ⇒ 高半字节在右。✔

### 两条独立佐证

1. **几何**：受阻族的 1 px 边线必须落在 16×16 逻辑格的**右边缘**（局部 x=7），
   「低=左」正好把边线放在 x=7，「高=左」会把它放在 x=6（格子内部），不合几何。
2. **仓库自己的收据**：`tools/butano/render_scenario_41_gpu.py` 一直用的是
   `packed >> (4 if local_x & 1 else 0)`，即**低=左** —— 它能「从 dump 重建 = 38,400/38,400 逐像素一致」，
   而写反的 `export_s49_movegrid_tilemap.py` 一直没能通过同等级的验收。

### 已做的更正

- `tools/butano/export_s49_movegrid_tilemap.py::tile_pixels` 已改为「低=左」并**重导出**产物
  （旧的 `bg2-tiles-render.png` / `bg2-cells.png` / `bg2-layer.png` 是**左右镜像**的，PNG 肉眼看不出错）；
- `tools/butano/export_s49_overlay_screentruth.py` 同步改正；
- 三处文档/笔记里的规则已更正，`AGENTS.md` 登记表补了这条硬规则。

## 2. 屏幕地面真相（产物）
导出器 `tools/butano/export_s49_overlay_screentruth.py`（确定性、可重复、`--check` 可验）
→ `artifacts/s49-original-overlay-screentruth-v1/`：

| 文件 | 内容 |
| --- | --- |
| `overlay-movegrid-screen.png` | 覆盖层在**屏幕坐标**下的渲染（240×160 RGBA，透明=不画） |
| `overlay-field-screen.png` | 同上，field 帧 |
| `screen-truth.json` | 族分布图、足迹统计、field↔movegrid 差异、**残差归因** |
| `manifest.json` | 每个输入/输出的 sha256 |

关键数字：

- movegrid 帧覆盖层**刷了 28,482 像素**，包围盒 **(0,0)–(239,159) = 整屏**，占 600 个可见格中的 **531** 格；
- field↔movegrid 的差异 = **212 个 tilemap 项** = 屏幕上 **212 个 8×8 格**（bbox x 0..207、y 24..135）；
- 可见窗口的 30×20 **族分布图**（`.`=空 `#`=网格网 `M`=移动透镜 `A`=攻击/光标 `C`=光标 `T`=目标 `B`=受阻）：

```
     000000000011111111112222222222
     012345678901234567890123456789
r 0  BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB
r 1  BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB
r 2  BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB
r 3  .#BBBB...#...#MMMM...#BBBBBBBB
r 4  ##BBBB########MMMM####BBBBBBBB
r 5  .#BBBB...#MMMMMMMMMMMM...#BBBB
r 6  ##BBBB####MMMMMMMMMMMM####BBBB
r 7  .#...#MMMMMMMMMMMMMMMMMMMMBBBB
r 8  ######MMMMMMMMMMMMMMMMMMMMBBBB
r 9  .#MMMMMMMMMMMMMMMMMMMMMMMMBBBB
r10  ##MMMMMMMMMMMMMMMMMMMMMMMMBBBB
r11  .#...#MMMMMMMMMMMMBBBBMMMMBBBB
r12  ######MMMMMMMMMMMMBBBBMMMMBBBB
r13  .#...#BBBBMMMMMMMMMMMM...#BBBB
r14  ######BBBBMMMMMMMMMMMM####BBBB
r15  .#...#BBBB...#MMMM...#...#BBBB
r16  ######BBBB####MMMM########BBBB
r17  .#BBBBBBBBBBBB...#BBBBBBBBBBBB
r18  ##BBBBBBBBBBBB####BBBBBBBBBBBB
r19  .#...#...#...#...#...#...#BBBB
```

读法：**偶数逻辑列用「无框」变体、奇数列用「带框」变体**（这与第 23 轮的结论一致），
`B`（受阻区）是**烘焙布局的一部分**，覆盖上 HUD 带、左右边界和若干条竖带。

## 3. **2,917 残差的逐族归因**（本轮最关键的新结论）

对照原版 `walk-original-a24/step-19-A.png` vs 重制 `s49-remake-expfix-20261020-v1/step-20-A.png`，
战场区 (0,0,240,128) 逐像素不等 = **2,917**（与基线一致），按**原版该像素所属的图族**拆开：

| 原版图族 | 残差像素 | 受影响格数 |
| --- | ---: | ---: |
| **blocked**（278..281，受阻区暗化） | **2,317** | 42 |
| **move_lens**（262..265，移动透镜） | **600** | 31 |
| 其余全部族 | 0 | 0 |

⇒ 残差**只来自两处**，与颜色、混合、粒度以外的任何东西无关。

### 3.1 blocked 的 2,317 像素 = **重制根本没画那一层**

取原版覆盖层受阻色 = 调色板 10 = RGB (74,74,74)。原版在屏幕 (16,24) 实测 (128,164,76)，
按 10/16 反解底图 = **(131,188,48)**；重制同一点实测 = **(132,189,49)** ⇒
**底图逐像素一致，差别 100% 来自重制少画了覆盖层的受阻暗化**。
42 个受影响格里有 18 格是整块 64 像素全差（tile 278↔278、280↔280 这类「原版画了、重制没画」）。

### 3.2 move_lens 的 600 像素 = **粒度不同**

- 原版的逻辑格是 **16×16 px**（2×2 个 8×8 图块），描边（调色板 3 = (8,106,172)）画在每个逻辑格的右边与下边；
- 重制的格点是 **32×16 px**（`cell_width=32, cell_height=16`，`battle_range_ui_tiles_per_cell_x/y=4/2`），
  描边只画在 32×16 块的右边与下边 ⇒ **每隔一条线就少画一次**。

颜色侧**不用动**：重制的 `move_primary RGB5(3,25,31)` = (24,205,255) = 原版调色板 2；
`move_secondary RGB5(1,13,21)` = (8,106,172) = 原版 3；
`grid_secondary RGB5(8,13,17)` = (65,106,139) = 原版 1；
`blocked_primary/secondary RGB5(9,9,9)/(4,4,4)` = (74,74,74)/(32,32,32) = 原版 10/11。
⇒ **重制的调色板已经与原版逐号同色**，残差纯粹是「画哪格」和「格多粗」。

## 4. 落地时的结构性事实（给下一轮施工用）

- 重制覆盖层 BG（`battle_range_overlay`，`battle_runtime_scene.cpp` 1996 起）：
  **32×32 图块、8bpp、整屏 (0,0)、优先级 2、混合 10/16** ⇒ 结构上与原版 BG2 **同构**，
  差别只有「滚动」与「内容」；
- 重制 BG2 的硬件参数（自 `artifacts/s49-remake-gpu-20261021-v2/io.bin` 实读）：
  `BGCNT2=0x138A`（优先级 2、8bpp、字符基址块 1 ⇒ `0x06010000`、screen base 19 ⇒ `0x06013000`），
  `BGCNT3=0xCC83`（地图层，优先级 3，screen base 12 ⇒ `0x0600C000`）。
  ⇒ 若要把原版 tilemap「原样搬进重制」，需要的换算是
  **重制 map 格 (c,r) ← 原版 tilemap 格 ((c+30)%32, (r+3)%32)**。
- 重制的格子族→图块预算：grid 1..8 / move 9..16 / attack 17..24 / 动作 25..52 / cursor 53..60 /
  target 61..68 / blocked 69..76，逻辑图块 77 个（8bpp 占 154 个存储图块）。
  原版 32 块里的 256/257（空）与 282..287（全透明）不需要单独占位。

## 5. 仍未闭合 / 下一步

| 项 | 状态 |
| --- | --- |
| blocked 区域该由哪条规则产生 | **未闭合**：原版是烘焙布局的一部分（`B` 区含 HUD 带、边界、若干竖带），重制的 `blocked_overlay_rows` 语义不同 ⇒ 需先把原版 `B` 区还原成规则或按布局取用 |
| 16×16 粒度 | **未落地**：重制一格 32×16 px，原版一格 16×16 px；重制现有规则是按格点算的，要拆成两个逻辑格需要状态侧提供 16×16 分辨率 |
| 描边色三角波 | **部分闭合**：`global` 在 IWRAM `0x03000078`（ROM 字面量 `0x0806A7D4` 自证），`global & 0x10` 选上升/下降半支 ⇒ **64 步周期**（旧笔记写的「32 帧」不完整）。初值与「哪一处自增点在 S49 跑」仍 unknown，详见 `notes/s49-outline-triangle-counter-20261021.md` |
| 屏①结算 / 屏②升级 | **未录到**（`round_limit=8`；木叶丸第 5 回合后仅 4 HP） |

## 6. 复现命令

```bash
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
/usr/local/bin/python3 tools/butano/export_s49_overlay_screentruth.py
/usr/local/bin/python3 tools/butano/export_s49_overlay_screentruth.py --check
/usr/local/bin/python3 -m unittest tests.test_s49_overlay_screentruth -v
```
