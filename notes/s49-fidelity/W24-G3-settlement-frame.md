# W24-G3 —— 結算屏最后 514 px：边框装饰 + 合計行双色红

> 流：**wave 24 / G3** · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/W23-F4-settlement-zero.md`（514 px 的分解）· `W19-B-settlement-tail.md`（結算屏资产来历）
> lane 副本：`D:\Github\gba-naruto\build\w23-f2\butano-sequel`（动手前已核对：与共享树
> `battle_result_content.h` / `battle_ui_model.h` / `battle_presentation_content.h` /
> `battle_runtime_scene.cpp` 与 `graphics/battle_result_font.bmp` /
> `graphics/battle_ui_result_total_palette.bmp` / `graphics/battle_ui_result_plate.bmp`
> **sha 全部一致**）
> 独占：`battle_result_content.h` · `battle_ui_model.h` · `battle_presentation_content.h` · `graphics/` 結算屏资产
> ⛔ `battle_runtime_scene.cpp` / `battle_presentation_script.h` = G1 流独占
> 工具：`tools/s49_w24g3/` · 收据：`build/w24-g3/`

---

## 0. 一句话结论

> ⭐⭐⭐ **結算屏整屏残差 514 px → 0 px（实测，F4 同前提真实链；改后图与原版真值图 sha256 相同）**。
> 其余 7 屏仍是逐字节 0 px；**25 帧 total = 54 959 px、判定台 = 38 047 px，两口径都正好等于当前基线（零回归）**；
> 单测 **pass=119 / fail=20**（与基线相同）；ROM **12 258 372 B（−256 B）**。
>
> ⭐ **514 px 全部定位完毕，而且全部是「资产层」的错，`battle_runtime_scene.cpp` 一行都不用改**：
>
> * **边框 354 px（上边框 223 + 框线 131）** ⇒ `graphics/battle_ui_result_plate.bmp`（結算屏的 BG 层）
>   **少了原版的花纹上边框、且右边框线只有 1 px 宽** ⇒ 把原版真值帧的像素**抄回该资产**即可。
> * **合計行 160 px** ⇒ `graphics/battle_result_font.bmp`（結算字体的数字图块）**把原版字块的
>   「双色」压成了单色**（深红 203 px），而原版是「浅红 160 + 深红 43」。
>   ⭐ **规则已被钉死并逐字验证**：*一个笔画像素是深红 ⟺ 它左边紧邻的像素也是笔画像素*
>   （即**每条横笔的最左一像素是浅红，其余是深红**）。
>   浅红 `(231,99,66)` **根本不在** `battle_ui_result_total_palette.bmp` 的调色板表里 ⇒
>   重制侧**没有色可用**，只能整行画深红。
>   ⭐ **机制 = (ii)：一个图块 + 两个调色板槽位**（证据见 §2.2，
>   最硬的一条是**同仓的姊妹字体 `battle_result_compact_font.bmp` 本来就是 idx2 + idx5 的双色字体**）。
>
> ⇒ **不需要任何 `.cpp` 接线** ⇒ **本流不产生接线请求**（只需拷 3 个资产，见 §6.5）。

---

## 1. ⭐ 514 px 的成分（本流独立复核，**不是**照抄 F4）

仪器：`tools/s49_w24g3/analyse_settlement.py` → `build/w24-g3/settlement-analysis.json`

| 部位 | px | 原版 | 重制 | 归属 |
|---|---:|---|---|---|
| **上边框装饰**（行 106–108） | **223** | `(99,189,115)`×130 + `(99,115,90)`×93 | 纯色 `(107,156,90)` | `battle_ui_result_plate.bmp` |
| **合計行**（行 139–149） | **160** | 浅红 160 + 深红 43 | 深红 203 | `battle_result_font.bmp` + `battle_ui_result_total_palette.bmp` |
| **框线 / 角** | **131** | 右边框线 **3 px 宽** | 只有 1 px | `battle_ui_result_plate.bmp` |
| 合计 | **514** | | | |

逐色对（`tools/s49_w24g3/dump_diff.py`）：

| 原版 → 重制 | px | 行 |
|---|---:|---|
| `(231,99,66)` → `(231,24,0)` | 160 | 139–149（合計字） |
| `(99,189,115)` → `(107,156,90)` | 130 | 106–108（上边框花纹） |
| `(99,115,90)` → `(107,156,90)` | 93 | 106–107（上边框花纹） |
| `(99,189,115)` → `(231,247,214)` | 54 | 111–152（右边框线） |
| `(231,214,99)` → `(231,247,214)` | 42 | 111–152（右边框线） |
| `(107,156,90)` → `(231,247,214)` | 30 | 113–150（右边框线） |
| `(99,189,115)` → `(231,214,99)` | 2 | 110–153 |
| `(107,156,90)` → `(231,214,99)` | 2 | 110–153 |
| `(107,156,90)` → `(99,189,115)` | 1 | 109 |

---

## 2. ⭐⭐ 合計行「双色红」的机制

### 2.1 决定性事实：**字形完全相同，只是「着色」不同**

`build/w24-g3/settlement-analysis.json`：

| 判据 | 值 |
|---|---:|
| 原版红色像素总数（浅+深） | 203 |
| 重制红色像素总数 | 203 |
| **两者的红色像素集合（对称差）** | **0** ⇒ 字形逐像素相同 |
| 原版描边 `(231,173,140)` / 重制描边 | 141 / 141，**对称差 0** ⇒ 描边也相同 |
| 原版浅红 / 深红 | 160 / 43 |
| 重制浅红 / 深红 | 0 / 203 |

⇒ **不是字形差、不是数值差、不是描边差**：只是**同一个字块被画成了两种红**。

### 2.2 ⭐ 机制判定：**(ii) 一个图块、两个调色板槽位**（不是两个精灵）

证据链：

1. **原版的「双色」是字块自身的属性，不是位置/时间的属性。**
   把真值帧的 9 个数字实例逐个与字库单元配对
   （`tools/s49_w24g3/patch_settlement_assets.py` ⇒ `build/w24-g3/patch-report.json`）：

   | 字符 | 字块 | 实例数 | 浅红 px / 深红 px | 各实例的「浅红像素集合」 |
   |---|---|---:|---:|---|
   | `0` | cell 15 | **5** | 20 / 4 | **5 个实例逐个相同** |
   | `3` | cell 18 | **2** | 17 / 5 | **相同** |
   | `5` | cell 20 | 1 | 13 / 7 | — |
   | `2` | cell 17 | 1 | 13 / 6 | — |

   ⇒ 同一个字块的 7 个实例给出**逐像素相同**的浅/深分布
   ⇒ **双色是「图块级」的**，不是「这一帧凑巧这样」。

2. **着色规则已被钉死**（对 4 个字块全部成立）：
   **一个笔画像素是深红 `(231,24,0)` ⟺ 它左边紧邻的像素也是笔画像素；
   否则是浅红 `(231,99,66)`。**
   换句话说：**每条横笔的最左一像素是浅红，其余是深红**。
   （例：`0` 的字块第 3 行 = `..###...` ⇒ 浅、深、深；第 6 行 = `.#o..#o.` ⇒ 两个孤立笔画都是浅红。）

3. ⭐⭐ **它不可能是「两个精灵错位叠画」**：
   若浅红是同一字块平移 ±1 px 的第二份拷贝，则可见的深红集合必须是
   「字块 ∩ 平移后字块」或「平移后字块 ∖ 字块」这类**整段**集合；
   而实测的深红集合是「**每条横笔除最左一像素以外的那一段**」
   （`0` 的上横笔 = 中间 2 px，**右侧那 1 px 仍是浅红**）
   ⇒ 平移拷贝会产生不出这个分布。
   ⇒ **原版的一个数字图块里就带着两种色调索引** ⇒ 属于 (ii)。

4. **重制侧为什么画不出来**：`graphics/battle_ui_result_total_palette.bmp`
   是**调色板表**（像素是恒等 0..15），其 16 项里
   `idx2 = (231,24,0)`（深红）、`idx5 = (231,173,140)`（描边），
   **`(231,99,66)`（浅红）根本不在表里** ⇒ 重制侧**没有这个颜色可用**，
   于是把字块里所有笔画都画成 idx2 的深红。

5. ⭐⭐⭐ **同仓的「姊妹字体」给出决定性类比（机制 = (ii) 的硬证据）**：
   本仓的 **`battle_result_compact_font.bmp`（結算屏的「經驗值 / 戰鬥分 / 回合分」三行用的字体）
   本身就是「一个图块、两个调色板槽位」的双色字体**：

   ```
   cell 15 ('0')                     用到的索引：{0 透明, 2 深灰, 5 浅灰}
      00000000
      02222500        ← idx2 = (57,66,57) 深灰   idx5 = (173,181,156) 浅灰
      22502250
      22502250
      22502250
      22502250
      22502250
      02222500
      00000000
   ```

   ⇒ **同一个仓库、同一种资产、同一个索引对（2 + 5）**：
   姊妹字体**天生就是双色**（而且重制侧那三行现在就是 **0 px**），
   而結算行用的 `battle_result_font.bmp` **同样的字块被压成了单色**。
   ⇒ ⭐ **結算行字块丢掉的那个「第二色调」，与姊妹字体的第二色调是同一种机制**
   ⇒ **机制 = (ii)：一个图块 + 两个调色板槽位**，**不是**两个精灵/两个图块。

6. ⭐⭐ **原版真值帧上的旁证**：原版的**另外两行数字（經驗值 / 戰鬥分 / 回合分）也是双色的**
   （深灰 `(57,66,57)` ×469 + 浅灰 `(173,181,156)` ×187），
   像素级形状与合計行同构（每条横笔都有一格是第二种色调）：

   ```
   ..DDDL....DDDDL....DDDDL      ← 合计行是「浅红在最左」，
   ...DDL...DDL.DDL...DDL..         这一组是「浅灰在最右」（不同字形、不同倒角方向）
   ...DDL...DDL.DDL..DDL...
   ...DDL......DDL...DDDDL.
   ```

   ⇒ 原版**同屏两种字体、两种配色对，都是「字块自带第二色调」**。

7. ⭐ **未能做的取证**：**原版的 PRAM/VRAM 级取证**（把合計行的像素按 PRAM 槽位/VRAM 地址分类）
   本波**没做**：`build/s49-victory-capture/w4/settlementA/play.json` 里**没有 VRAM/PRAM 转储**，
   要拿到就得重放原版整场战斗到結算屏（29 700 帧的捕获级成本）。
   ⇒ 上述 (ii) 判定是**渲染层 + 几何层 + 同仓姊妹字体类比**的证据链，
   **不是**「读原版 VRAM 找到那两个图块」的直接证据。**这是本流的已知缺口。**

### 2.3 ⭐ 附带发现：**原版的合計行是「滚动累加」动画**

`build/s49-victory-capture/w4/settlementA/frames/`（29 700 帧）扫描行 139–149：

| 帧 | 浅红 | 深红 |
|---|---:|---:|
| 1–718 | 0 | 0（还没进結算行） |
| 719 | 99 | 15 |
| 763 | 159 | 27 |
| 831 | 117 | 42 |
| 1059 | **160** | **43** ← 终态 |
| 1059–1576 | 160 | 43（**恒定 ≈ 518 帧**） |
| 1577 起 | 0 | 0（离开結算行） |

⇒ 原版把三个合計数**从 0 滚到 300/350/200**；
**真值帧 `02-settlement-exp-power-turns.png` 取的是终态**（浅 160 / 深 43）。
⇒ ⛔ **重制侧没有这个累加动画**（数字一次出现）——这是**另一个开放项**，不影响本波的静态对拍。

---

## 3. 资产与代码定位（父代理要的「514 px 分别对应哪个资产/哪段代码」）

| 缺陷 | 资产 / 代码 | 说明 |
|---|---|---|
| 上边框花纹 + 右边框线（354 px） | **`graphics/battle_ui_result_plate.bmp`**（256×256 8bpp，24 色） | 結算屏的 BG 层，代码里由 `battle_runtime_scene.cpp:1916 _add_result_background()` 用 `create_bg(8, 48)` 建 ⇒ **屏幕 (x,y) = 资产 (x+16, y)**。资产的调色板里**已经有** `(99,189,115)`（idx2）与 `(99,115,90)`（idx3）⇒ **只差像素，不需要加色** |
| 合計行双色（160 px） | **`graphics/battle_result_font.bmp`**（8×7920 字库，495 个 8×16 单元）+ **`graphics/battle_ui_result_total_palette.bmp`** | 数字字块用 idx2（笔画）与 idx5（描边）；**浅红缺色** |
| 合計行的绘制代码 | `battle_runtime_scene.cpp:4830-4846`（`result_text_generator.set_palette_item(battle_ui_result_total_palette)` + `generate(participant_value_x[index], 64, ...)`） | ⛔ G1 流独占，**但本波不需要改它**：调色板与字库改完，这段代码原样就画出双色 |

**字库定位方法（可复现）**：Butano 的 sprite font 把 ASCII 放在最前，
`graphics_index = char - '!'`（`third_party/butano/butano/src/bn_sprite_text_generator.cpp:977`）
⇒ `'0'`=**15**、`'2'`=**17**、`'3'`=**18**、`'5'`=**20**；
每个字块 = 字库图里第 N 个 8×16 单元（`bn_sprite_font.h:40 minimum_graphics = 94`）。

---

## 4. ⭐ 改法与「模拟残差 = 0 px」

工具：`tools/s49_w24g3/patch_settlement_assets.py`
（先 `--dry-run` 看模拟残差，确认后再落盘）

### 4.1 改了 3 个资产（**只在 lane 副本里**）

| 资产 | 改法 | 改后 sha256（前 16） |
|---|---|---|
| `graphics/battle_result_font.bmp` | 4 个数字字块里 **63 个**笔画像素由 idx2 改成 **idx1**（= 浅红） | `68f7273072f901e4` |
| `graphics/battle_ui_result_total_palette.bmp` | **调色板表**第 1 项 `(231,247,214)` → **`(231,99,66)`** | `3321c0509b2ba6db` |
| `graphics/battle_ui_result_plate.bmp` | 抄回原版真值帧的 **354 个像素**（花纹上边框 + 3 px 右边框线） | `1966940217d15893` |

**为什么挑 idx1**：`battle_result_font` 与 `battle_preparation_font` 两个字库用到的索引是
`{2, 5, 12, 14, 15}` ⇒ **idx1 在两个字库里都没被用过** ⇒ 改它不会波及
`battle_preparation_scene.cpp:189` 那段同样用 `battle_ui_result_total_palette` 的「傀儡人偶/蜜蜂」。

### 4.2 ⭐ 模拟残差（**改 ROM 前就能验**）

工具自带模拟：把补丁后的 plate + 改色后的数字叠回重制帧，与原版真值逐像素比：

| 口径 | 改前 | **改后（模拟）** |
|---|---:|---:|
| 結算屏整屏 | **514 px** | ⭐ **0 px** |

收据：`build/w24-g3/patch-report.json`（`simulated_diff_px = 0`）·
`build/w24-g3/settlement-simulated.png` · `settlement-truth.png`

---

## 4b. ⭐⚠️ 事故记录：lane 的 `graphics/` 是**指向共享树的符号链接**

> **动手前必须核对 lane 的 `graphics` 是不是符号链接。**
> 父代理给的 lane `build/w23-f2/butano-sequel` 里：
>
> ```
> audio     d----l -> D:\Shell\Github\gba-naruto-butano\butano-sequel\audio
> graphics  d----l -> D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics
> ```
>
> ⇒ **在 lane 里改 `graphics/*.bmp` 就是直接改共享树**（本流踩了：3 个资产被写进共享树）。
> 该 lane 还**缺 `src/` 与 `benchmark/`**（`main.cpp` 依赖 `konoha_bench/self_test.h`）⇒ **它根本编不出 ROM**。
>
> **处置**：① 用 `build/w19-b` 的同名资产把共享树的 3 个文件**按字节还原**
> （sha 回到 `669AF1EB3FAB` / `3516D0FB755B` / `F14C3897BBCC`，`git status` 也回到原状）；
> ② 改用**自建 lane** `build/w24-g3/butano-sequel`
> （`tools/s49_w24g3/setup_lane.py`：`Makefile` + `src/` + `game/` + `benchmark/` + **`graphics/` 真实副本**）。
>
> ⇒ **给下一波的硬规则**：**要改资产 ⇒ `graphics/` 必须是真实目录，不是符号链接。**
> （`tools/s49_w20/capture_lock.py` 的同源规矩：**共享树只读**。）

### 4b.3 ⚠️ 第三个坑：**BG 层的「屏幕 ↔ 资产」偏移是 (0,0)，不是 (+16, 0)**

`battle_ui_result_plate` 由 `create_bg(8, 48)` 建（W19-B §3.1 的结论是
「`(8,48)` ⇒ 屏幕显示资产 **行 0–159 / 列 0–239**」）⇒ **屏幕 (x,y) = 资产 (x,y)**。

本流一开始按「GBA 藏起 256 宽 BG 的最左 16 像素」误推出 **(x+16, y)**，
补丁因此写到了资产的错误位置：**模拟残差 0 px，但真机只降到 163 px**
（上边框的花纹被平移了 +16 ⇒ 反而画到了别处）。

⭐ **仪器教训**：**任何「往 BG 层资产里抄像素」的补丁，都要先用暴力对齐把
「屏幕 ↔ 资产」的偏移量实测出来**（本流的 brute force：
`for dy in -40..40, for dx in -40..40` ⇒ **匹配率 (0,0)=90.2 %，次优仅 80.4 %**）
⇒ 别从注释里推偏移。
（本流的 `tools/s49_w24g3/patch_settlement_assets.py` 里的
`PLATE_DX` 常量现在就写着这个实测结论与实测方法。）



### 4b.2 ⚠️ 第二个坑：**PIL 存不回 4bpp BMP**

`battle_ui_result_total_palette.bmp` 原本是 **4bpp**（16 色表，150 B）。
用 PIL `save()` 存回去会**静默变成 8bpp**（182 B）⇒ **butano 的 loader 拒收 ⇒ 资产阶段构建失败**。
⇒ 调色板表必须**按字节改**（`tools/s49_w24g3/patch_palette_entry.py`：
BMP 的色表是 DIB 头后紧跟的 BGRA 四元组数组）。
（`battle_result_font.bmp` 与 `battle_ui_result_plate.bmp` 本来就是 8bpp，PIL 存回去不变。）

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| G3-1 | 514 px 全在「上边框 + 合計行 + 框线」三处 | 逐色对 + 逐行分布 | 223 + 160 + 131 = 514 ✅ | **已确认** |
| G3-2 | 合計行的差是**字形差** | 红色像素集合对称差 | **0** ⇒ 字形逐像素相同 ⇒ **证伪** | **已证伪** |
| G3-3 | 合計行的差是**描边差** | 描边像素集合对称差 | **0** ⇒ **证伪** | **已证伪** |
| G3-4 | 合計行的差是**数值差** | 数字格已是 0 px（F4） | 数值相同 ⇒ **证伪** | **已证伪** |
| G3-5 | 「双色」是**字块属性**（机制 (ii)） | 9 个实例逐个与字块配对，比对浅红像素集合 | 同字符的 7 个实例**逐像素相同** ⇒ **成立** | **已确认** |
| G3-6 | 「双色」是**两个精灵错位叠画** | 平移拷贝能产生的集合形状 | 产生的深红集合形状与实测**不符**（横笔右端仍应是浅红） ⇒ **证伪** | **已证伪** |
| G3-7 | 浅红缺色是重制侧画不出的根因 | `battle_ui_result_total_palette` 的 16 项 | 表里**没有** `(231,99,66)` ⇒ **成立** | **已确认** |
| G3-8 | 上边框花纹只需**改像素**、不用加色 | plate 的调色板表 | `(99,189,115)`=idx2、`(99,115,90)`=idx3 **都在** ⇒ **成立** | **已确认** |
| G3-9 | 原版的合計行是**静态**的 | 扫描 29 700 帧 | 终态恒定 518 帧，但**之前有累加动画** ⇒ 「终态静态」成立 | **部分确认** |
| G3-10 | 改完 3 个资产就能把整屏残差清零 | 补丁自带的逐像素模拟 | **0 px** | **已确认（模拟）** |
| G3-11 | 真机跑出来也是 0 px | F4 同前提链 + 逐屏对拍 | **結算屏 0 px、8 屏全 0 px、改后图 sha256 == 真值图** | **已确认** |
| G3-12 | 「双色」是 **(ii) 一个图块两个槽位** | ① 9 个实例逐像素一致 ② 平移拷贝产生不出该形状 ③ **同仓姊妹字体 `battle_result_compact_font` 本来就是 idx2+idx5 双色**（且那三行 0 px） | 三条都成立 | **已确认** |
| G3-13 | 「屏幕 ↔ BG 资产」的偏移是 (0,0) | 暴力对齐 `dx,dy ∈ ±40` | **(0,0) 匹配率 90.2 %**，次优仅 80.4 % ⇒ 证实；我一开始用的 (+16,0) 是错的 | **已确认（并已纠错）** |
| G3-14 | 判定台 / 25 帧不上升 | 两个口径各跑一次 | **38 047 / 54 959**，都正好等于当前基线 | **已确认** |
| G3-15 | 单测零新增红 | `build/w18-run-all-tests.sh` | **pass=119 / fail=20**（与基线逐项相同） | **已确认** |

---

## 6. ⭐ A/B 实测

### 6.1 結算屏逐屏对拍（**F4 的同前提真实链**）

命令（**只读复用** F4 的驱动器与探针）：

```powershell
python tools/s49_w20/capture_lock.py --run --label G3 -- python tools/s49_w23f4/v1_battle_f4.py \
  --rom "D:\Github\gba-naruto\build\w24-g3\butano-sequel\butano-sequel.gba" \
  --out build/w24-g3/run --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w24g3/mgba-probe.exe
python tools/s49_victory_align/align_settlement.py \
  --truth build/s49-victory-capture/w4/settlement-truth \
  --remake build/w24-g3/run/shots --out build/w24-g3/align-settlement.json
```

**前提收据**（`build/w24-g3/run/battle.json`，**与 F4 完全同前提**）：

| 项 | 值 |
|---|---|
| `entry.poke` / `poke_commands` | **false / 0** |
| `errors` | **`[]`** |
| `from_real_battle` | **true** |
| 回合数 | **8** |
| 击杀归属 | **2 / 3 / 0** |
| 战闘分 / 回合分 | **100 / 150 / 0** / **75 / 75 / 75** |

**逐屏结果**（`build/w24-g3/align-settlement.json`）：

| 屏 | 改前（F4） | ⭐ **改后** |
|---|---:|---:|
| victory | 0 px | **0 px**（逐字节相同） |
| ⭐ **result（結算屏）** | **514 px** | ⭐⭐ **0 px**（`identical: true`） |
| level_up_1..6 | 0 px ×6 | **0 px ×6**（逐字节相同） |
| **8 屏合计** | 514 px | ⭐ **0 px** |

**收据图**（`build/w24-g3/`）：
`settlement-truth.png` · `settlement-before-514px.png` · `settlement-after-0px.png`
⇒ 改后图与真值图 **sha256 相同**（`e34e116c7ed3a55e…`）⇒ **整屏逐字节相同**。

### 6.2 单测

```
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh \
  /mnt/d/Github/gba-naruto/build/w24-g3/butano-sequel
```
⇒ **pass=119 / fail=20**（与基线**逐项相同** ⇒ 零新增红；脚本 `status=1` 是这 20 项预存债的固有返回码）。

### 6.3 ROM 体积

| ROM | 字节 |
|---|---:|
| 共享树基线 `butano-sequel.gba` | 12 258 628 |
| ⭐ **本流改后** | **12 258 372** |
| Δ | ⭐ **−256 B** |

### 6.4 ⭐ 两个口径都不许上升（AGENTS.md 第 15 条）

**判定台**（`tools/s49_fidelity_report.py`，arg-min 对齐）：

| 口径 | 基线（`build/s49-package-w22/work/s49-report/report.json`） | ⭐ **本流** |
|---|---:|---:|
| `field_residual.sum` | **38 047 px** | ⭐ **38 047 px**（**不升**） |
| `full_residual.sum` | 123 592 px | **123 592 px** |
| `overlay_residual.sum` | 857 px | **857 px** |
| attribution | 4 identical / 20 product_diff / 1 pairing_diff | **逐项相同** |

**25 帧固定偏移口径**（`tools/s49_wave18/align_capture_steps.py`，offset **+4**）：

| 口径 | 基线 | ⭐ **本流** |
|---|---:|---:|
| `best_total` | **54 959 px**（= F1 的「同代码 8bpp 基线」） | ⭐ **54 959 px**（**不升**） |

⚠️ **任务书里给的 `build/w22-d1/align-v4.json` = 53 364 px 是 wave 22 的旧数**；
与当前基线的 **+1 595 px** 差异**早已定位**到 `step-24-A` 一帧、**是共享树代码漂移**，
不是资产问题（W23-F3 §220、W23-F1 F1-8 都记着这条）。
⇒ **本流的正确判据是 54 959 ⇒ 实测正好 54 959 ⇒ 零回归。**
（两个口径**同时**不变 ⇒ 符合 AGENTS.md 第 15 条。）

### 6.5 ⭐ 资产清单（父代理接线时要拷回共享树的 3 个文件）

| 文件（相对 `butano-sequel/`） | 改法 | 改后 sha256（前 16） |
|---|---|---|
| `graphics/battle_result_font.bmp` | 4 个数字字块（cell 15/17/18/20）里 **63 个**笔画像素由 idx2 改成 **idx1** | `68f7273072f901e4` |
| `graphics/battle_ui_result_total_palette.bmp` | **调色板表**第 1 项 `(231,247,214)` → **`(231,99,66)`**（**必须按字节改**：PIL 会把 4bpp 存成 8bpp） | `3321c0509b2ba6db` |
| `graphics/battle_ui_result_plate.bmp` | 抄回原版真值帧的 **354 个像素**（花纹上边框 223 + 3 px 右边框线 131） | `1966940217d15893` |

⇒ ⭐ **不需要改任何 `.cpp` / `.h`** ⇒ **本流不产生接线请求**。
（接线时请注意：**先 `git checkout` 这三个文件到干净态再拷**，因为 `battle_ui_result_plate.bmp`
在共享树里是**未入库的新文件**（`git status` 显示 `??`）。）


---

## 7. 未完成项 / 开放项

1. ⏳ **重制侧没有原版的「合計数累加动画」**（原版 719→1059 帧从 0 滚到 300/350/200，终态恒定 518 帧）。
   本波只做**终态**的逐像素对齐；动画是**独立开放项**（要动 `battle_runtime_scene.cpp` ⇒ 属 G1 流）。
2. ⛔ **原版的 PRAM/VRAM 级机制取证未做**（(i)/(ii) 的判定是渲染层 + 几何层 + 同仓姊妹字体类比的证据链，
   **不是**「读原版 VRAM 找到那两个图块」的直接证据；原版的結算屏 VRAM/PRAM 没有现成转储，
   要重放整场战斗才能拿到）。**这是本流唯一的已知缺口。**
3. ✅ **本波不需要接线请求**：3 个资产改完，`battle_runtime_scene.cpp` 原样就画出正确画面。
4. ℹ️ `battle_ui_result_plate.bmp` 的改动是**逐像素抄原版**，与原版真值帧**绑定**；
   若将来原版結算屏的边框换画，要重新抄。
5. ℹ️ `battle_ui_result_total_palette.bmp` 的 **idx1 原本是奶油色 `(231,247,214)`**，
   本流把它改成了浅红 `(231,99,66)`。
   实测：idx1 **在 `battle_result_font` 与 `battle_preparation_font` 两个字库里都没被任何字块用过**
   ⇒ 不影响 `battle_preparation_scene.cpp:189` 那段同样用这张调色板的「傀儡人偶/蜜蜂」。
   （但如果以后有字块要用 idx1，须重新挑一个空槽。）
6. ⚠️ **本流曾误改共享树**（lane 的 `graphics/` 是符号链接）⇒ 已按字节还原，
   详见 §4b。**下一波要改资产 ⇒ 必须自建 lane 的真实 `graphics/` 目录。**

---

## 8. 复现

```powershell
# 0) 自建 lane（graphics 必须是真实目录，不是符号链接）
python tools/s49_w24g3/setup_lane.py --lane build/w24-g3/butano-sequel

# 1) 打补丁（--dry-run 先看模拟残差）
python tools/s49_w24g3/patch_settlement_assets.py \
  --lane build/w24-g3/butano-sequel --out build/w24-g3 --dry-run
python tools/s49_w24g3/patch_settlement_assets.py \
  --lane build/w24-g3/butano-sequel --out build/w24-g3

# 2) 构建
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/w24-g3/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 3) F4 同前提链（全局锁）
python tools/s49_w20/capture_lock.py --run --label G3 -- python tools/s49_w23f4/v1_battle_f4.py \
  --rom "D:\Github\gba-naruto\build\w24-g3\butano-sequel\butano-sequel.gba" \
  --out build/w24-g3/run --boot --max-turns 400 --use-tools \
  --exe build/mgba-probe-w24g3/mgba-probe.exe

# 4) 逐屏对拍
python tools/s49_victory_align/align_settlement.py \
  --truth build/s49-victory-capture/w4/settlement-truth \
  --remake build/w24-g3/run/shots --out build/w24-g3/align-settlement.json

# 5) 两个口径
python tools/s49_fidelity_report.py --out build/w24-g3/report.json \
  --work-dir build/w24-g3/work --butano-root build/w24-g3/butano-sequel \
  --compare build/s49-package-w22/work/s49-report/report.json
python tools/s49_wave18/align_capture_steps.py \
  --original build/s49-package-w18/work/s49-report/capture-original \
  --remake build/w24-g3/work/capture-remake --out build/w24-g3/align.json

# 6) 单测
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh \
  /mnt/d/Github/gba-naruto/build/w24-g3/butano-sequel
```

### 收据清单（`build/w24-g3/`）

| 收据 | 内容 |
|---|---|
| ⭐ `align-settlement.json` | **8 屏全 0 px**，結算屏 `identical: true` |
| ⭐ `run/battle.json` | 真实链收据：`poke=false`、`poke_commands=0`、`errors=[]`、`round=8`、`kills={1:2,2:3,3:0}`、`battle_score=[100,150,0]`、`round_score=[75,75,75]` |
| ⭐ `settlement-truth.png` / `settlement-before-514px.png` / `settlement-after-0px.png` | 改前/改后結算屏图（**改后与真值 sha256 相同**） |
| ⭐ `report.json` | 判定台：`field_residual.sum = 38 047`（= 基线） |
| ⭐ `align.json` | 25 帧固定偏移：`best_offset=4`、`best_total=54 959`（= 基线） |
| `patch-report.json` | 补丁报告：字块/槽位/354 px 明细 + 模拟残差 0 px |
| `settlement-analysis.json` / `settlement-diff-groups.json` / `font-cells.json` | 514 px 的分解、逐色对、字库单元 dump |
| `build.log` / `build2.log` / `chain.log` / `chain2.log` / `bench.log` | 构建 / 链 / 判定台日志 |

### 工具（`tools/s49_w24g3/`）

| 工具 | 作用 |
|---|---|
| `setup_lane.py` | 建**自包含** lane（`graphics/` 真实副本，不吃符号链接） |
| `analyse_settlement.py` | 514 px 的成分分解 + 合计行足迹/描边对称差 + plate 调色板核对 |
| `dump_diff.py` | 逐色对 + 逐行/逐列分布 + 每个数字的字形位图 |
| `dump_font_cells.py` | 字库单元 dump（ASCII 索引约定） |
| `patch_settlement_assets.py` | ⭐ 主补丁：字块改色 + 调色板加色 + plate 抄像素（自带模拟残差） |
| `patch_palette_entry.py` | **按字节**改 4bpp BMP 的调色板表项（PIL 存不回 4bpp） |
| `revert_settlement_assets.py` | 补丁回滚（本流误改共享树时用过；最终用 `build/w19-b` 的干净副本按字节还原） |
