# W22-D6 —— 黑场 B2/B3/B4 的 4bpp 化改造（实测 + 取舍结论）

> wave 22 / D6 流子代理 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/W21-C3-blackfade.md`（C3 的下界论证 + 接线请求 R-C3-2）
> · `notes/s49-fidelity/W20-EXEC-BRIEF.md` · `notes/s49-fidelity/W21-PARENT-wrapup.md` §4
> 独占文件：`tools/s49_w22d6/` · `build/w22-d6/` · 本笔记
> ⛔ **不改任何产品代码**；⛔ **不改共享树**；逆向线**只读**；不提交 git

---

## 0. 一句话结论（**最终**）

> ⭐⭐⭐ **R-C3-2 可行、而且零失真 —— 建议接线。**
>
> ① **原版这两张背景所在的战场画面本来就是 4bpp**（`DISPCNT = 0x1940` ⇒ Mode 1；
> 逐 8×8 块实测：草地地图 **100% 单调色板组**；四个 `BGxCNT` 的 **bit14（色深位）全部为 0**）。
> ⇒ **重制侧写死的 `bpp_8` 不是从原版测出来的**（`generate_butano_battle_runtime_assets.py:194` 是硬编码）
> ⇒ **改成 4bpp 是「向原版看齐」，不是引入失真**。
>
> ② ⭐⭐ **4bpp 化零失真，且两个全屏 BG 可以同时在场**：
> 用 **Butano 自己的 `bpp_4_auto` 量化器**跑这两张资产 ⇒ **像素 0 变化**，
> 调色板组数 = **地图 5 组 + 对白背景 2 组（+ 准备背景 1 组）= 8 组 ≤ PRAM 的 16 组**
> ⇒ **两个全屏 BG 可同时在场 ⇒ 交接可以做到 0 帧空屏**（对齐原版）。
>
> ③ ⚠️ **可执行的前提是「先去掉 BMP 调色板里的重复项」**：
> 当前两张 BMP 的调色板有**重复颜色**（256 项里只有 73 / 31 项真被用到），
> Butano 的量化器会直接抛 `ValueError: There's two used identical colors in: 1 and 33`。
> ⇒ **必须先做一次无损的调色板去重**，再把 sidecar 的 `bpp_mode` 改成 `bpp_4_auto`。
>
> ④ ⛔ **本流没有跑改后的 A/B 录制**（黑场帧数 + 25 帧判定台 total）——
> 原因：lane 副本的 `graphics/` **是指向共享树的符号链接**（无权改），
> 且两个长录制要占全局锁。**⇒ 接线前需要补这一跑。**

> 📌 **本流自己的一处更正（重要）**：本笔记的**初版结论是错的**——
> 我先前用「全局 16 色量化」和**自己写的粗糙贪心**得出「地图会变色 25.5%」「单张 4bpp 装不下（需 21 组）」。
> 两个口径都错了：4bpp 是**逐 tile** 的（不是全局 16 色），
> 而 Butano 的真实算法（first-fit + 合并 pass）**只需 5 组**。
> ⇒ §3.3 / §4 已按实测重写。

---

## 1. 判定口径

| 项 | 口径 |
|---|---|
| 原版真值 | `rom/base.gba`，sha256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b` |
| 原版 GPU 抓取 | `D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-field-frame-v1`（`pram-00.bin` / `vram-00.bin` / `io-00.bin` / `frame-00.png`） |
| 位深判定方法 | ① 原版帧寄存器解码；② 逐 8×8 块把 PNG 像素回查 PRAM 调色板组（`tools/s49_w22d6/probe_bg_bpp.py`）—— 与逆向线的 `bits_per_pixel` 普查互相独立 |
| 4bpp 可行性判据 | **Butano 自己的** `BMP.quantize()`（`third_party/butano/butano/tools/bmp.py:107`），不重新实现（`tools/s49_w22d6/probe_butano_bpp4_auto.py`） |
| 重制侧资产 | `D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics\`（⚠️ **lane 副本里 `graphics/` 是指向共享树的符号链接** ⇒ 本流**没有**改任何资产） |

---

## 2. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **D6-1** | 「原版这两张全屏 BG 在 ROM 里本来就是 8bpp ⇒ 不该改」 | 原版战场帧 `DISPCNT`/`BGxCNT` 解码 + 逐 8×8 块回查 PRAM 组 + 逆向线逐层 `bits_per_pixel` | ⛔ **证伪**：`DISPCNT = 0x1940` ⇒ **Mode 1**；`BG0CNT/BG1CNT/BG2CNT/BG3CNT` 的 **bit14（色深位）全部 = 0 ⇒ 4bpp**；草地地图 **339/480 块单组**，跨组块与精灵位置逐一对应；逆向线 79 个描述符 / 300 层 = **4bpp 225 层、8bpp 75 层**，战斗描述符层位深 **[4,4,8,4]** | **已证伪** |
| **D6-2** | 「重制侧的 `bpp_8` 是从原版 ROM 测出来的」 | 读重制线生成器源码 | ⛔ **证伪**：`tools/generate_butano_battle_runtime_assets.py:194` 硬编码 `"bpp_mode": "bpp_8", "colors_count": 256` ⇒ **8bpp 是自选，不是原版事实** | **已证伪** |
| **D6-3** | 「把这两张图量化到 16 色会有可接受的失真」 | 全局 16 色中位切分量化 | ⛔ **证伪**（**但口径本身是错的**，见 D6-7）：地图 **25.513%** 像素变色 ⇒ 全局 16 色**不可接受** | **已证伪（口径错误）** |
| **D6-4** | 「地图是 tile 化的，所以 4bpp 化可以零失真」 | 逐 8×8 块统计不同颜色数 | ✅ **成立**：地图 4096 块、**超 16 色的块 = 0**、单块最多 **14** 色；对白背景 1024 块同样 **0 / 14** | **已确认** |
| **D6-5** | 「零失真的 4bpp 塞不进 PRAM 的 16 个调色板组」 | ⚠️ 初版用**自写贪心**得 21 组 ⇒ 判为证伪 | ⛔ **被推翻**：Butano 的真实算法（`bmp.py:107` first-fit + 合并 pass）**只需 5 组**（地图）/ **2 组**（对白背景）⇒ **7 ≤ 16，装得下** | **已推翻（见 D6-8）** |
| **D6-6** | 「黑场 2 帧/次是 GBA 的原理性下界」 | 原版战场帧 DISPCNT + 逆向线「battle 描述符 = 4 层并存」 | ⛔ **证伪**：原版同一帧里 **A/B/C/D 四层 BG 同时在场** ⇒ GBA 允许**多张 BG 并存**。⇒ 2 帧下界是**「换整屏 BG」这个重制架构**的下界，**不是 GBA 的下界** | **已证伪** |
| **D6-7** | 「4bpp = 全图 16 色」 | 读 Butano `bmp.py:107` 的 `quantize()` | ⛔ **证伪**：Butano 的 4bpp 量化器是**逐 tile（8×8）**的 —— 每块的颜色集必须落在**一个 16 色组**里；块数不限、组数 ≤ 16。⇒ **判据是「每个 tile ≤ 15 色」（>15 直接抛错），不是「全图 ≤ 16 色」** | **已证伪** |
| **D6-8** | ⭐「这两张资产能被 Butano 的 `bpp_4_auto` 无损转换，且组数 ≤ 16」 | 直接调用 `BMP.quantize()`，再逐像素比对 RGB | ✅ **成立**：地图 **5 组 / 0 像素变化**（262,144 px 全同）；对白背景 **2 组 / 0 像素变化**（65,536 px 全同）；准备背景 **1 组 / 0 变化** ⇒ **合计 8 组 ≤ 16** | **已确认** |
| **D6-9** | 「当前 BMP 能直接喂给 `bpp_4_auto`」 | 直接调用 `BMP.quantize()` | ⛔ **证伪**：两张 BMP 的调色板**有重复颜色** ⇒ 量化器抛 `ValueError: There's two used identical colors in: 1 and 33`（地图）/ `1 and 22`（对白背景）⇒ **必须先做无损去重** | **已证伪** |
| **D6-10** | 「去重是无损的」 | 去重后逐像素 RGB 比对 | ✅ **成立**：地图 256→47 项、**0 像素变化**；对白背景 256→29 项、**0 像素变化** | **已确认** |

---

## 3. 关键实测

### 3.1 ⭐ 原版战场帧的位深（**本流最重要的一问**）

**原版战场帧的 IO 寄存器**（`s49-original-field-frame-v1/io-00.bin`，6 帧全部相同）：

```
DISPCNT = 0x1940  ⇒  Mode = (0x1940 >> 12) & 7 = 1   (Mode 1)
```

| 寄存器 | 原值 | priority | char_base | **bit14（色深位）** |
|---|---|---:|---|---|
| `BG0CNT` | `0x0000` | 0 | 0x00000 | **0 ⇒ 4bpp** |
| `BG1CNT` | `0x0009` | 1 | 0x00000 | **0 ⇒ 4bpp** |
| `BG2CNT` | `0x00A0` | 0 | 0x00000 | **0 ⇒ 4bpp** |
| `BG3CNT` | `0x0007` | 3 | 0x04000 | **0 ⇒ 4bpp** |

**逐 8×8 块回查 PRAM 调色板组**（仪器：`tools/s49_w22d6/probe_bg_bpp.py`）：
4bpp 的每个 8×8 块只能来自**一个** 16 色组；8bpp 的块可横跨任意多组。

```
y000 222222222222222222222222..22..      ← 顶部 HUD 条（另一层 BG）
y008 ........................3.2432      ← 草地：全部 "."（单组）
y016 ........................323222
y024 ..2222.........33.............
y032 ..22.2.......34453............
y040 ..22.2.......34544.....23.....
y048 ..2222....33...662....3323....
y056 ..........456.3424....3222....
y064 ..........378.3335....2224....
y072 ..........436753242...........
y080 ..........665732352...........
y088 ..........46562..22222........
y096 ..........562.....2222........
y104 ......2222....................
y112 ......22.2....................
y120 ......22.2....................
y128 222222222222222222222222222222   ← 底部 HUD 条（另一层 BG）
```

* 图块总数 **480**、**单组 339**、跨组 141、**未映射像素 0**（PRAM↔PNG 配色映射完备）。
* 「跨组」的块**与精灵位置逐一对应**（两个角色在第 10–18 列；石头、灌木在第 22–27 列）⇒ **精灵叠在地图上**。
* ⇒ ⭐⭐ **草地地图区域 100% 是 4bpp**（每块只用 1 个 16 色调色板组）。

**交叉验证（逆向线自己的普查，与本流独立）**：
`artifacts/tile-assets-bg-v2/manifest.json`（79 个描述符 / 300 层）：**4bpp 225 层、8bpp 75 层**；
战斗描述符的层位深 = **[4, 4, 8, 4]**（A/B/D = 4bpp，C = 8bpp）。
`artifacts/bg-resource-canvases-v1/manifest.json`：12 个有效 BG 资源 = **7 个 4bpp + 5 个 8bpp**，运行期实际用到
`[1,2,3,4,5,6,7,9,10,12]`（**两种位深都在用**）。

**对白画面**：逆向线 `notes/dialogue-render-analysis.md` 记录对白帧
`DISPCNT = 0x1940`、`BG0CNT = 0x0087`、`BG3CNT = 0x0300`
⇒ **BG0/BG3 的 bit14 也都是 0** ⇒ **4bpp**；且对白帧的 **DISPCNT 与战场帧完全相同（Mode 1）**
⇒ 同一套 BG 硬件配置 ⇒ 与战场帧的逐块实测互相印证。
⇒ ⭐ **原版没有「一张独立的对白背景 BG」**：对白是**叠在原封不动的战场图层之上**的。

> ⚠️ 口径：对白画面的位深**不是**逐块实测（没有配套 PRAM/VRAM dump，见 §6 N-2），
> 而是由「同一 DISPCNT ⇒ 同一 Mode 1」+「BGxCNT bit14 = 0」**推得**。

### 3.2 重制侧的 8bpp 是硬编码的（**不是原版事实**）

```python
# D:\Shell\Github\gba-naruto-butano\tools\generate_butano_battle_runtime_assets.py:190-199
_write_json(
    chunk_path.with_suffix(".json"),
    {
        "type": "regular_bg",
        "bpp_mode": "bpp_8",          # ← 硬编码
        "colors_count": 256,          # ← 硬编码
        ...
        "source": f"rom/base.gba:map-row-{battle_id}",
    },
)
```

Butano 生成的 item 头（`build/w20-e3/butano-sequel/build/bn_regular_bg_items_battle_14_map_chunk_0.h`）：

```cpp
battle_14_map_chunk_0_bn_gfxTiles[718],                              // 718 块 × 64 B = 44,952 B
bg_palette_item(span<const color>(...Pal, 256), bpp_mode::BPP_8, ...) // 256 色 = 16 个调色板组
```

⇒ 重制侧：**718 块 8bpp + 16 组调色板**。
⇒ C3 的下界论证（两个 8bpp 全屏 BG 要 32 组 > 16 组）**在「重制现状」下完全成立**。

### 3.3 ⭐ 4bpp 化的代价：**零失真**，而且**两个 BG 装得下**

#### 3.3.1 判据修正：4bpp 是**逐 tile**的，不是全局 16 色

Butano 的 4bpp 量化器（`third_party/butano/butano/tools/bmp.py:107` `BMP.quantize()`）：

* 逐个 8×8 tile 收集**非 0** 的调色板索引集合；
* **单块超过 15 色直接抛错**（`There's a tile with more than 15 colors`）⇒ **判据是「每块 ≤ 15 色」**；
* 每块落进**一个 16 色调色板组**（first-fit + 一次合并 pass，`-mRtp` 的 `p` = palette reduction）；
* **组数 ≤ 16**（= PRAM 的全部）。

⇒ **不是**「全图 ≤ 16 色」。本流初版用「全局 16 色量化」判可行性的口径是错的。

#### 3.3.2 实测：Butano 的真实量化器 ⇒ **像素 0 变化**

仪器：`tools/s49_w22d6/probe_butano_bpp4_auto.py`（**直接调用 Butano 自己的 `BMP.quantize()`**，不重新实现）；
收据 `build/w22-d6/bpp4-auto-dedup-result.json`。

| 资产 | 量化后组数 | **调色板组数（槽位）** | 比对像素 | **像素变化** | 失真 |
|---|---:|---:|---:|---:|---|
| `battle_14_map_chunk_0` | 80 色 | **5** | 262,144 | **0** | **无** |
| `battle_ui_dialogue_background` | 32 色 | **2** | 65,536 | **0** | **无** |
| `battle_preparation_background` | 16 色 | **1** | 65,536 | **0** | **无** |

⇒ ⭐⭐ **地图 5 组 + 对白背景 2 组 + 准备背景 1 组 = 8 组 ≤ 16**
⇒ **三个全屏 BG 可以同时在场** ⇒ **交接的 0 帧空屏在调色板层面是可达的**（对齐原版）。

#### 3.3.3 ⚠️ 前置条件：BMP 调色板**去重**（无损）

Butano 的量化器要求调色板里**没有两个相同的颜色**。当前两张 BMP 都是 256 项调色板但**只有 73 / 31 项真被用到**：

```
battle_14_map_chunk_0        → ValueError: There's two used identical colors in: 1 and 33
battle_ui_dialogue_background → ValueError: There's two used identical colors in: 1 and 22
```

仪器：`tools/s49_w22d6/dedupe_bmp_palette.py`；收据 `build/w22-d6/palette-dedupe.json`。

| 资产 | 调色板项数（前 → 后） | 删掉 | **RGB 像素变化** |
|---|---:|---:|---:|
| `battle_14_map_chunk_0` | 256 → **47** | 209 | **0 / 262,144** |
| `battle_ui_dialogue_background` | 256 → **29** | 227 | **0 / 65,536** |

⇒ **去重是纯无损的**（索引 0 保留为透明槽）。

#### 3.3.4 附：每 16-tile 组的颜色数（父代理指定的判据）

仪器：`tools/s49_w22d6/probe_palette_banks.py`；收据 `build/w22-d6/palette-bank-census.json`。
（**注意**：这个「固定分组」口径只反映**分组是否越界**，不等于 Butano 的组分配算法。）

| 资产 | 每 1 块 | 每 4 块 | 每 8 块 | 每 16 块 | 每 32 块 |
|---|---|---|---|---|---|
| `battle_14_map_chunk_0` | 最多 14 色 / **0 越界** | 最多 **16** 色 / **0 越界** | 最多 25 色 / **38 越界** | 最多 36 色 / **40 越界** | 最多 36 色 / **36 越界** |
| `battle_ui_dialogue_background` | 最多 14 色 / **0 越界** | 最多 16 色 / **0 越界** | 最多 16 色 / **0 越界** | 最多 **16** 色 / **0 越界** | 最多 16 色 / **0 越界** |
| `battle_preparation_background` | 最多 6 色 / 0 越界 | 6 / 0 | 6 / 0 | 6 / 0 | 6 / 0 |

⇒ **对白背景在任何分组粒度下都无越界**；
⇒ **地图在「每 4 块一组」下无越界，但「每 16 块一组」有 40/256 组越界（最多 36 色）**
⇒ 但这**不构成障碍**：Butano 的真实算法是**逐块自由分配组**（不是固定分组），实测只要 **5 组**（§3.3.2）。

### 3.4 原版是怎么做到 0 黑帧的（背景知识，用于风险评估）

原版战场 = **4 张同时在场的 BG 图层**（逆向线 `tile-assets-bg-v2` 的 `layers`）：

| 层 | 位深 | 块数 | 覆盖 | 作用 |
|---|---:|---:|---|---|
| A | **4bpp** | 232 | 30×14 @ (0,0) | HUD / 场景层 |
| B | **4bpp** | 128 | 32×14 @ (0,0) | HUD / 场景层 |
| C | **8bpp** | 163–258 | 30×10 | 战场细节层 |
| D | **4bpp** | 544 | 27×18 @ (3,2) | **地图本体** |

⇒ 原版**从不在交接处「换一整张 BG」**：地图层一直在场，对白是**额外的层**。
⇒ ⭐ **C3 的「2 帧/次硬下界」是「重制当前架构（单张全屏 BG + 整张替换）」的下界，不是 GBA 的原理性下界。**
⇒ ⚠️ **但把重制改成「两张 4bpp BG 并存」也只是逼近原版**（原版是 4 层 + 对白叠层）。
⇒ **风险登记**：本方案解决的是「**调色板 16 槽**」这个瓶颈（16 槽 ⇒ 8 槽），
**不解决**「交接时仍要释放 + 重建 BG」带来的**图块搬迁延迟**
（C3 实测：来方 BG 的图块重定位延迟 = B2 +4 帧、B4 +6 帧）。
⇒ **预期**：B3（2 帧）与 B2/B4 的**下界 2 帧**可望消到 **0 帧**，
但 B2/B4 的**重定位余量（B2 +4、B4 +6）可能仍然存在** ⇒ **实测前不能承诺 0 帧。**

---

## 4. 对 C3 / R-C3-2 的取舍结论

### 4.1 R-C3-2：**✅ 采纳（有条件）**

| 检验点 | 结论 |
|---|---|
| 「原版本来就是 8bpp ⇒ 改了会引入失真」 | ⛔ **前提不成立**：原版战场就是 4bpp；重制的 8bpp 是自选硬编码 |
| 「改 4bpp 会不会引入颜色失真」 | ✅ **不会**：Butano 自己的量化器 ⇒ **像素 0 变化**（§3.3.2） |
| 「两个全屏 BG 能不能同时在场」 | ✅ **能**：5 + 2（+1）= **8 组 ≤ 16**（§3.3.2） |
| 「有什么前置条件」 | ⚠️ **必须先做 BMP 调色板去重**（§3.3.3），否则 Butano 直接抛错 |
| 残余风险 | ⚠️ 图块重定位延迟仍在（B2 +4、B4 +6）⇒ **实测前不能承诺 0 帧**（§3.4） |

### 4.2 ⭐⭐ 可执行方案（接线用）

**Step 1 —— 资产去重（无损）**
对 `graphics/battle_14_map_chunk_0.bmp` 与 `graphics/battle_ui_dialogue_background.bmp`
做一次**调色板去重**（256 → 47 / 29 项，**RGB 像素 0 变化**）。
⇒ 工具已就绪：`tools/s49_w22d6/dedupe_bmp_palette.py`
⇒ ⚠️ **更稳妥的做法是在生成器里做**（否则下次跑生成器会把去重冲掉）：
* 地图：`D:\Shell\Github\gba-naruto-butano\tools\generate_butano_battle_runtime_assets.py`（写 `.bmp` + sidecar 的地方，:185-216）
* 对白背景：`D:\Shell\Github\gba-naruto-butano\tools\butano\generate_battle_ui_assets.py`（:104-132 定义来源，:3445 写 sidecar）

**Step 2 —— sidecar 改位深**

```jsonc
// graphics/battle_14_map_chunk_0.json
{
  "type": "regular_bg",
  "bpp_mode": "bpp_4_auto",     // ← 原 "bpp_8"
  "colors_count": 80,           // ← 4bpp 下由 Butano 自己算；建议删掉这一项
  "compression": "auto_no_huffman",
  "source": "rom/base.gba:map-row-14",
  ...
}
```

* ⭐ **`bpp_4_auto` 是 Butano 自带的模式**（`butano_graphics_tool.py:688-693`）：
  它会先调 `BMP.quantize()`（**逐 tile、无损**），再走 GRIT `-gB4`（`:902-905`）+ `-mRtp`（palette reduction，`:907-908`）。
* ⚠️ **`bpp_4_auto` 不能与 `palette_item`（外部调色板）同时用**（`:689-690` 会抛错）。
* ⚠️ `bpp_4_auto` 要求源 BMP 的调色板**满 256 项**（`bmp.py:114-116`）⇒ Step 1 的去重要**保留 256 项槽位**（只用前 47 / 29 项）。

**Step 3 —— 调色板怎么进 ROM（父代理点名要查的那一步）**

Butano 的管线是：**sidecar → `butano_graphics_tool.py` → GRIT → `bn_regular_bg_items_<name>.h`**

* GRIT 产出 `bn_gfx`（tiles + `Pal[]` + map）；
* Butano 把 `Pal` 写成 `bn::color` 数组：`bg_palette_item(span<const color>(..._bn_gfxPal, <colors_count>), bpp_mode::BPP_4, compression_type::RUN_LENGTH)`；
* **`colors_count` 由 `parse_colors_count()`（`butano_graphics_tool.py:19-33`）从 sidecar 取，并向上取整到 16 的倍数**
  ⇒ **组数 = `colors_count / 16`**，必须 ≤ 16；
* 改完后的期望产物（对照现在的 8bpp 版本）：

```cpp
// 期望（4bpp）
battle_14_map_chunk_0_bn_gfxTiles[?],                                  // 4bpp：32 B/块
bg_palette_item(span<const color>(battle_14_map_chunk_0_bn_gfxPal, 80), bpp_mode::BPP_4, ...)
```

**Step 4 —— 接线后必须跑的验证（父代理的验收口径）**
1. `python tools/s49_package/capture_blackfade.py --rom <新ROM> --out build/w22-d6/blackfade-after`
   （**用全局锁** `python tools/s49_w20/capture_lock.py --run --label D6 -- <命令>`）
   ⇒ **判据**：纯黑帧分组由 `6 / 18 / 2 / 8 / 24` 变成多少？B2 的 6 / B3 的 2 / B4 的 8 是否降到 0。
2. **25 帧判定台**：`python tools/s49_wave18/align_capture_steps.py`，基线 `build/w20-e3/align-e3.json`
   （`best_offset = 4`、total **148,914 px**）⇒ **total 不得上升**。
   ⭐ **预期**：4bpp 化**不改变任何像素** ⇒ 画面应当**逐帧完全一致** ⇒ total 应**持平**；
   若 total 上升 ⇒ 说明 4bpp 转换引入了失真 ⇒ **不接线**。
3. **单测**：期望 `pass=119 / fail=20`。
4. **ROM 体积**：4bpp 图块 **32 B/块** vs 8bpp **64 B/块**
   ⇒ 地图 718 块：45,952 B → **22,976 B（省 22.0 KiB）**；调色板 256 色 → 80 色（省 352 B）。
   （GRIT 在 4bpp 下还会再做 tile 合并，实际省得更多。）

### 4.3 ⭐ 接线请求

| # | 归属 | 改成什么 | 为什么 |
|---|---|---|---|
| **R-D6-1** ⭐ | 资产层（**共享树**：`D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics\`）—— ⚠️ **lane 副本的 `graphics/` 是符号链接，本流无权改** | `battle_14_map_chunk_0` / `battle_ui_dialogue_background` 的 sidecar：`"bpp_mode": "bpp_8"` → **`"bpp_mode": "bpp_4_auto"`**，并**先做调色板去重** | §3.3.2 / §3.3.3：Butano 自己的量化器 ⇒ **像素 0 变化**；组数 **5 + 2 + 1 = 8 ≤ 16** ⇒ 两个全屏 BG 可同时在场 ⇒ 0 帧空屏可达 |
| **R-D6-2** | 生成器（共享树，**非本流独占**）：`tools/generate_butano_battle_runtime_assets.py`、`tools/butano/generate_battle_ui_assets.py` | 在写 `.bmp` 的地方**顺带去重调色板**（保持 256 项槽位、只用前 N 项） | 否则下一次跑生成器会把去重冲掉，`bpp_4_auto` 会抛 `two used identical colors` |
| **R-D6-3** | `notes/s49-fidelity/W21-C3-blackfade.md` §3.0 / §5.1 | 把「0 帧在当前资产布局下不可达」改成「**在『单张全屏 BG + 整张替换』且 8bpp 的架构下不可达；改成 4bpp 后调色板槽位够用（8 ≤ 16），但图块重定位延迟仍在 ⇒ 0 帧需实测确认**」 | §3.4 + §4.1 |
| **R-D6-4** | wave 22 / **D1**（`battle_runtime_scene.cpp` / `battle_visual_resource_coordinator.h`） | 若 4bpp 化后**仍有**黑场帧，则走「**交接时不要释放/重建整屏 BG**」的架构修法（保留地图 BG，对白画在第二张 BG/OBJ 上 —— 原版就是 4 层并存） | §3.4：原版 0 黑帧靠**图层并存**；4bpp 化只解决**调色板槽位**这一半 |

---

## 5. 收据 / 工具

| 项 | 路径 |
|---|---|
| ⭐ 原版战场帧位深收据 | `build/w22-d6/field-frame-bpp.json`（DISPCNT/BGxCNT 解码 + 480 块的调色板组统计） |
| ⭐ 4bpp 可转换性收据 | `build/w22-d6/bpp-convertibility.json`（超 16 色块统计 + 全局量化代价） |
| ⭐ **Butano 真实 4bpp 量化收据** | `build/w22-d6/bpp4-auto-dedup-result.json`（**组数 5 / 2 / 1，像素 0 变化**） |
| ⭐ 调色板去重收据 | `build/w22-d6/palette-dedupe.json` |
| 每 N-tile 组的颜色普查 | `build/w22-d6/palette-bank-census.json` |
| 仪器 1：原版帧位深探针 | `tools/s49_w22d6/probe_bg_bpp.py` |
| 仪器 2：4bpp 可转换性探针 | `tools/s49_w22d6/probe_bpp_convertibility.py` |
| 仪器 3：**Butano 真实 4bpp 量化器驱动** | `tools/s49_w22d6/probe_butano_bpp4_auto.py` |
| 仪器 4：调色板去重（无损） | `tools/s49_w22d6/dedupe_bmp_palette.py` |
| 仪器 5：每 N-tile 组普查 | `tools/s49_w22d6/probe_palette_banks.py` |
| 产出的 4bpp 就绪资产（**未进 ROM**） | `build/w22-d6/bpp4-auto/*.dedup.bmp` · `build/w22-d6/bpp4-auto/quantized/*.bn_quantized.bmp` |
| 原版 GPU 抓取（只读） | `D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-field-frame-v1` |
| 逆向线证据（只读） | `artifacts/tile-assets-bg-v2\manifest.json`（逐层 `bits_per_pixel`）· `bg-resource-canvases-v1\manifest.json`（7 个 4bpp + 5 个 8bpp）· `notes\dialogue-render-analysis.md`（对白帧寄存器） |

---

## 6. 未完成项（本流明确没做的事）

| # | 事 | 状态 | 原因 |
|---|---|---|---|
| **N-1** | ⭐ **改完 4bpp 后的黑场 A/B 实测**（B2/B3/B4 帧数 + 25 帧判定台 total + 单测 + ROM 体积） | ⛔ **未做** | ① **lane 副本的 `graphics/` 是指向共享树的符号链接** ⇒ 本流**无权**改资产（改动必须在共享树做，由父代理接线）；② 两个长录制要占全局锁，本流已超出时间预算。**⇒ 接线后必须补这一跑（§4.2 Step 4 给了全部命令与判据）** |
| **N-2** | 对白场景的原版 GPU 抓取（`pram/vram/io` 三件套） | ⛔ **未做** | 逆向线只有对白帧的**寄存器**记录，没有配套 PRAM/VRAM dump ⇒ 对白位深是**推得**（同一 DISPCNT + bit14=0），不是逐块实测 |
| **N-3** | 改 4bpp 后的**实际图块数 / ROM 体积** | ⚠️ **未实测** | 需要真的跑一次构建；§4.2 Step 4 给了估算法（地图 718 块：45,952 B → 22,976 B，省 22.0 KiB） |
| **N-4** | 4bpp 化后 **B2/B4 的图块重定位延迟是否还在** | ⛔ **未知** | C3 实测 B2 = 2 + 4、B4 = 2 + 6（余量 = 来方 BG 的图块重定位延迟）。4bpp 化把图块量**减半**（44.9 → 22.0 KiB）⇒ 重定位压力下降 ⇒ **余量可能缩小**，但**不保证归零** ⇒ 实测前不能承诺 0 帧 |

---

## 7. 一页速查（给父代理）

| 问题 | 答案 | 证据 |
|---|---|---|
| 原版战场背景位深？ | **4bpp** | DISPCNT 0x1940 ⇒ Mode 1；四个 BGxCNT 的 bit14 全 0；480 块里草地 **100% 单调色板组**，跨组块 = 精灵位置 |
| 原版对白背景位深？ | **4bpp**（原版**没有**独立的对白背景 BG，对白是叠层） | 对白帧 BG0CNT=0x0087 / BG3CNT=0x0300 ⇒ bit14=0，且 DISPCNT 与战场帧相同 |
| 原版 0 黑帧的机制？ | **多张 BG 图层并存**（A/B/C/D 四层，位深 [4,4,8,4]） | 逆向线 `tile-assets-bg-v2` 逐层 `bits_per_pixel` |
| 重制侧 8bpp 从哪来？ | **硬编码**，非原版实测 | `generate_butano_battle_runtime_assets.py:194` |
| 4bpp 化会失真吗？ | **不会** —— Butano 自己的量化器：**像素 0 变化** | `build/w22-d6/bpp4-auto-dedup-result.json` |
| 需要几个调色板组？ | **地图 5 + 对白背景 2 + 准备背景 1 = 8 ≤ 16** ⇒ 可同时在场 | 同上 |
| 前置条件？ | ⚠️ **必须先做 BMP 调色板去重**（否则 Butano 抛 `two used identical colors`） | `build/w22-d6/palette-dedupe.json` |
| sidecar 怎么改？ | `"bpp_mode": "bpp_8"` → **`"bpp_mode": "bpp_4_auto"`**（Butano 自带模式，逐 tile 量化 + GRIT `-gB4 -mRtp`） | `butano_graphics_tool.py:688-693, 902-908` |
| **该不该做 R-C3-2？** | **✅ 该做，但必须先补 A/B 录制**（黑场帧数 + 25 帧 total），且**不能承诺 0 帧**（图块重定位延迟仍在） | §4.1 / §4.2 / §6 N-4 |
