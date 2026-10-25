# W23-F1 —— 把两张全屏 BG 改 4bpp（wave 23 / F1 流）

> wave 23 / F1 流子代理 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/W20-EXEC-BRIEF.md` · `W22-D6-blackfade-4bpp.md`（全部前置推导）
> · `W22-PARENT-wrapup.md` §4 / §8 · `W21-C3-blackfade.md`（黑场下界）
> lane 副本：`D:\Github\gba-naruto\build\w23-f1\butano-sequel`（`graphics/` 是**真实目录**，可改资产）
> 独占文件：`graphics/battle_14_map_chunk_0.{bmp,json}` · `graphics/battle_ui_dialogue_background.{bmp,json}`
> · `graphics/battle_preparation_background.{bmp,json}` + 生成器 + 其数据源
> ⛔ 不改 `game/` 下的 C++（别的 lane）；⛔ 不改共享树（`D:\Shell\gba-naruto-butano\`）；逆向线只读；不提交 git

---

## 0. 一句话结论

> ⭐⭐ **4bpp 化本身完全成功、零失真、调色板槽位从 33 降到 8（≤ 16）、
> ROM 省 93,516 B（91.3 KiB）、黑场纯黑帧 58 → 56（B4 从 8 帧降到 6 帧）**
> —— **但同代码 A/B 证明：4bpp 让 35 帧步进的**尾部画面冻结**，
> 25 帧判定台 total 从 54,959 px 升到 82,831 px（+27,872 px）⇒ ⛔ **按门禁属于回归，不建议直接接线。**
>
> ⭐ **根因方向已锁定**：黑场遮罩（`battle_black_field_star_mask.h`）与 **BG 调色板布局**耦合
> —— 淡入淡出靠「把 BG 调色板项写成黑色再写回原值」实现，
> 而 4bpp 把地图的调色板从 256 项压到 **80 项** ⇒ 遮罩写回的槽位不再对应。
> ⇒ **资产层已经做完（可交付）；代码层还需要一波「让遮罩认新的调色板布局」的改动。**

---

## 1. 判定口径与基线

| 项 | 口径 |
|---|---|
| 原版黑场真值 | `build/s49-package-w22/evidence/blackfade/`（原版 **42** 纯黑帧，全在 2 个持黑段） |
| 重制侧改前基线 | `build/w21-c3/blackfade-base/blackfade.json`（**58** 纯黑帧；分组 6/18/2/8/24） |
| 25 帧判定台 | `tools/s49_wave18/align_capture_steps.py`；基线 `build/w22-d1/align-v4.json`（total **53,364 px**） |
| 单测 | 期望 pass=119 / fail=20 |

---

## 2. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **F1-1** | 改 4bpp 后纯黑帧下降 | 黑场 A/B 录制（同口径、同探针） | ✅ **58 → 56**（B4：8 → 6；B2 6 / B3 2 不变） | **已确认（只降 2 帧）** |
| **F1-2** | 4bpp 化零像素变化 | 逐像素 RGB 比对 + 35 帧步进逐帧 sha256 | ✅ 资产层 **0 变化**；步进 **step-03…step-27 逐字节相同**（25 帧） | **已确认（前半段）** |
| **F1-3** | ROM 体积下降 | 同代码 A/B 的两个 ROM 字节数 | ✅ **12,258,628 → 12,165,112（−93,516 B / −91.3 KiB）** | **已确认** |
| **F1-4** | 「去重逻辑写进生成器 ⇒ 重跑不会被冲掉」 | 重跑生成器 + 复读 sidecar | ✅ **成立**：49/49 块 `bpp_4_auto`、对白 `bpp_4_auto`/32 色 | **已确认** |
| **F1-5** | 「所有 47 张地图都能无损转 4bpp」 | Butano 自己的 `BMP.quantize()` 逐张跑 | ✅ **成立**：49/49 块全部通过（无一回落 8bpp） | **已确认** |
| **F1-6** | 「4bpp ⇒ 调色板 16 槽瓶颈解除 ⇒ 黑场帧会掉」 | ROM 内 item 头 + 黑场录制 | ⚠️ **一半成立**：槽位 33 → **8**（✅ 解除）；纯黑帧只掉 **2 帧**（B2/B3 一帧没掉） | **部分成立** |
| **F1-7** | ⭐⭐「4bpp 化不会让 25 帧判定台变差」 | **同代码 A/B**（同 lane、同代码、同构建环境，8bpp vs 4bpp 两个 ROM） | ⛔ **证伪**：total **54,959 → 82,831 px（+27,872）**；步进 step-28…34 从「有内容」变成 **7 帧冻结的暗帧** | **已证伪** |
| **F1-8** | 「25 帧上升是共享树代码漂移造成的，不是 4bpp」 | 同代码 A/B：判定台基线 53,364 vs 本流 8bpp 基线 54,959 | ⛔ **证伪**：代码漂移只贡献 **+1,595 px**，4bpp 贡献 **+27,872 px** | **已证伪** |

---

## 3. 改动记录（增量更新）

### 3.1 lane 脚手架（父代理给的 lane 副本缺件，已补）

| 项 | 处理 |
|---|---|
| `build/w23-f1/third_party` | **junction** → `D:\Shell\gba-naruto-butano\third_party`（符号链接需要管理员权限，改用 junction） |
| `build/w23-f1/rom` | junction → 共享树 `rom`（生成器要 `rom/base.gba`） |
| `build/w23-f1/artifacts` | junction → 共享树 `artifacts` |
| `build/w23-f1/butano-sequel/src`、`benchmark` | 从共享树**复制**（1 + 13 个文件）——lane 副本缺这两个目录，Makefile 的 `SOURCES`/`INCLUDES` 引用它们 |
| `build/w23-f1/tools/` | 共享树 `tools/` 的**影子副本**（620 个文件）⇒ 在副本上改生成器，**共享树零改动** |

> ⚠️ `D:\Github\gba-naruto` 本身是 `D:\Shell\gba-naruto` 的 **junction** ⇒ 生成器里
> `Path(__file__).resolve().parents[2]` 解析到真实路径，影子副本的 `ROOT` = `build/w23-f1` ✓

**lane 与共享树的一致性核对**（改动前）：`game/` **291 个文件逐一 sha256 相同**；
`graphics/` **1852 个文件逐一 sha256 相同** ⇒ 本流改动的**唯一**差异就是资产本身。

### 3.2 ⭐ 生成器改动（**去重逻辑写在生成器里 ⇒ 重跑不会被冲掉**）

**影子副本（父代理接线时把这 3 个文件的 diff 接回共享树）：**

| 文件 | 改动 |
|---|---|
| `tools/butano/indexed_bmp.py` | 新增 `dedupe_palette(image)`（**无损**去重：索引 0 保留为透明槽，其余按使用顺序压紧，RGB 0 变化）+ 新增 `bpp4_auto_palette_slots(bmp_path)`（**调用 Butano 自己的 `BMP.quantize()`**，返回需要的 16 色槽位数；量化器拒绝 ⇒ 返回 `None`） |
| `tools/generate_butano_battle_runtime_assets.py` | `generate_map_chunks()`：先 `dedupe_palette(chunk)` ⇒ 落盘到临时文件 ⇒ `bpp4_auto_palette_slots()` 判定 ⇒ **通过**则写 `bpp_4_auto` + `colors_count = 槽位×16`；**不通过**则**原样写回 8bpp 资产**（逐字节不变） |
| `tools/butano/generate_battle_ui_assets.py` | `_dialogue_background_image()` 的落盘点：先 `dedupe_palette()` 再存 ⇒ sidecar 写 `bpp_4_auto` + `colors_count = 槽位×16`（量化器拒绝 ⇒ 回落 `bpp_8`/256） |

> ⭐ **判定用的是 Butano 自己的量化器，不是重写的贪心**：
> `bpp_4_auto` 在构建时跑的就是 `third_party/butano/butano/tools/bmp.py:107` 的 `BMP.quantize()`，
> 生成器跑的是**同一个函数** ⇒ 生成器的决定 == 构建的决定。

### 3.3 资产实测（改后）

| 资产 | 调色板（去重前 → 后） | **RGB 像素变化** | Butano 量化器 | 调色板槽位 |
|---|---:|---:|---|---:|
| `battle_14_map_chunk_0` | 256 → 47 项 | **0 / 262,144** | 80 色 | **5** |
| `battle_ui_dialogue_background` | 256 → 29 项 | **0 / 65,536** | 32 色 | **2** |
| `battle_preparation_background` | 本来就是 4bpp（`write_4bpp_bmp` 写 16 色） | — | — | **1** |

⇒ **5 + 2 + 1 = 8 ≤ 16** ⇒ 两个全屏 BG 可以同时在场 ⇒ **黑场的「16 槽瓶颈」被解开**（与 D6 §3.3.2 的预测**逐项吻合**）。

**49 张地图块全部转成 4bpp**（49/49，无一回落 8bpp）：
`battle_00` 8 槽 / `battle_01` 4 槽 / `battle_02` 5 槽 / `battle_03` 3 槽 / `battle_04` 3 槽 / …

---

## 4. 未完成项 / 接线请求

### 4.1 接线请求

| # | 归属 | 改成什么 | 为什么 |
|---|---|---|---|
| **R-F1-1** ⭐ | 共享树生成器：`tools/butano/indexed_bmp.py` · `tools/generate_butano_battle_runtime_assets.py` · `tools/butano/generate_battle_ui_assets.py` | 接回本流的 3 个文件 diff（收据：`build/w23-f1/f1-generator-4bpp.patch`，7,510 B） | 否则下次跑生成器会把去重 + 4bpp 冲掉，`bpp_4_auto` 会抛 `two used identical colors` |
| **R-F1-2** ⭐ | 共享树资产 `butano-sequel/graphics/battle_*_map_chunk_*.{bmp,json}`（**49 块**）+ `battle_ui_dialogue_background.{bmp,json}` | 接回 lane 副本的资产（收据：`build/w23-f1/graphics-4bpp/`，**100 个文件**）；⚠️ `integrate.py` **不覆盖 `graphics/`** ⇒ 必须手动拷 | §3.3：Butano 自己的量化器 ⇒ 像素 0 变化；8 槽 ≤ 16 ⇒ 调色板不再是瓶颈；ROM 省 91.3 KiB |
| **R-F1-3** ⭐⭐ | **黑场遮罩（`game/include/konoha/battle_black_field_star_mask.h` + `battle_runtime_scene.cpp` 的淡入淡出路径）—— 非本流独占** | 让遮罩**按「当前 BG 自己的调色板项数」写回**，而不是假定 256 项 / 16 槽；或改成「淡入淡出只改自己那一张 BG 的调色板槽位」 | ⭐⭐ **这是 4bpp 接线的真正阻塞点**：4bpp 把地图调色板从 256 项压到 80 项，遮罩写回的槽位不再对应 ⇒ 35 帧步进尾部**冻结在暗帧** ⇒ 25 帧 total +27,872 px（§5.5） |
| **R-F1-4** | `notes/s49-fidelity/W21-C3-blackfade.md` §3.0 / §5.1（R-C3-2） | 把「0 帧在当前资产布局下不可达」改成「**8bpp 架构下不可达；4bpp 后调色板槽位够用（8 ≤ 16），但图块重定位延迟仍在，且**遮罩与调色板布局耦合 ⇒ 0 帧需先修遮罩再实测**」 | D6 §3.4 + 本流 §5.5 |
| **R-F1-5** | 父代理的出包流水线 | **不要**在 R-F1-3 修好之前把本流的资产接进共享树 | §5.5：同代码 A/B ⇒ 4bpp 造成 25 帧 total +27,872 px 回归 |

### 4.2 本流明确**没做**的事

| # | 事 | 状态 | 原因 |
|---|---|---|---|
| **N-1** | ⛔ **`tools/butano/generate_battle_ui_assets.py` 无法端到端重跑** | 缺 `references/battle-scenario-49-ui/hud-shell-bg-tiles.bin` 与 `artifacts/original-s49-selector1-page1-gpu-20260730-115/*`（**本机根本没有**，共享树里也没有 `references/` 目录） | 与本流改动**无关**的既有缺口。对白背景的**改动本身**是用生成器**同一份** `dedupe_palette()` + `bpp4_auto_palette_slots()` 做的（0 像素变化、2 槽） |
| **N-2** | ⚠️ **4bpp ⇒ 尾部冻结的机理未闭合** | 只锁定到「遮罩 ↔ BG 调色板布局」这一层，没有落到具体代码行 | 时间预算（父代理 23:50 收口，本流跑完已过 01:0x） |
| **N-3** | ⚠️ **只接了 battle 14 的地图 vs 49 张地图全转** | 本流把**全部 49 块**都转了 4bpp（更贴近原版：原版战场 BG 的 bit14 全 0） | 若父代理想缩小爆炸半径，可只保留 battle 14（把 sidecar 的 `bpp_mode` 改回 `bpp_8` 即可，其余不动） |

---

## 5. 实测收据

### 5.1 ⭐ ROM 体积 + ROM 内的位深（权威数字：Butano 生成的 item 头）

| 项 | 改前（8bpp，`build/w20-e3/butano-sequel/build/`） | **改后（4bpp，本流 lane）** |
|---|---|---|
| `battle_14_map_chunk_0` | `512x512@8` · 359 tiles（64 B/块 = 22,976 B）· palette **256** 色 = **16 槽** · total 14,720 B | ⭐ `512x512@4` · 359 tiles（32 B/块 = **11,488 B**）· palette **80** 色 = **5 槽** · total **12,268 B** |
| `battle_ui_dialogue_background` | 178 tiles @8 · palette 256 = **16 槽** | ⭐ 89 tiles @4 · palette **32** = **2 槽** · total 3,344 B |
| `battle_preparation_background` | `256x256@4` · palette 16 = 1 槽 | 不变（本来就是 4bpp） |
| **同时在场的调色板槽位** | 16 + 16 + 1 = **33 > 16** ⇒ ⛔ 放不下 | ⭐ **5 + 2 + 1 = 8 ≤ 16** ⇒ ✅ **两个全屏 BG 可同时在场** |
| **ROM 体积** | `build/s49-package-w22/rom/butano-sequel.gba` = **12,258,628 B** | ⭐ **12,165,112 B** ⇒ **省 93,516 B（91.3 KiB）** |

* 改后 ROM sha256 `558b83e38e2897bc1f70b9b23a025d7eef6e7a58e051ebf16bbba1bc718e133b`
* 改后 item 头（节选）：
  `regular_bg_tiles_item(span<const tile>(battle_14_map_chunk_0_bn_gfxTiles, 359), bpp_mode::BPP_4, ...)`
  `bg_palette_item(span<const color>(battle_14_map_chunk_0_bn_gfxPal, 80), bpp_mode::BPP_4, ...)`
* ⇒ **调色板 16 槽瓶颈已解除**（与 D6 §3.3.2 的 5+2+1=8 预测**逐项吻合**）。

### 5.2 ⭐⭐ 黑场 A/B 实测（改后）

收据：`build/w23-f1/blackfade-after/{capture.json,blackfade.json,blackfade.md,frames/}`
（探针 `build/mgba-probe-w23f1/mgba-probe.exe`，全局锁 `--label F1`，同口径参数：keys `Down,Down,A×21` / zero 240 / hold 4 / settle 90 / frames 2552 → 2402 帧）

| 事件 | 帧段（改前 → 改后） | 总帧 | 纯黑 | 淡出 | 淡入 | 原版应有 |
|---|---|---:|---:|---:|---:|---|
| 1 = **B2**（准备→部署） | 00527–00532（**不变**） | 6 | **6** | 0 | 0 | 0 |
| 2 | 01639–01708（不变） | 70 | 18 | 24 | 28 | 淡入 24 |
| 3 = **B3**（地图→对白） | 01749–01750（**不变**） | 2 | **2** | 0 | 0 | 0 |
| 4 = **B4**（对白→地图） | 02217–**02222**（改前 02217–**02224**） | **6**（改前 8） | ⭐ **6**（改前 8） | 0 | 0 | 0 |
| 5 | 02263–02342（改前 02265–02344） | 80 | 24 | 28 | 28 | 淡出/淡入 24 |

| 项 | 改前 | **改后** | 原版 |
|---|---:|---:|---:|
| **纯黑帧总数** | **58** | ⭐ **56** | **42** |
| 纯黑分组 | 6 / 18 / 2 / 8 / 24 | ⭐ **6 / 18 / 2 / 6 / 24** | 42（2 段：18 + 24） |
| 纯黑偏差 | +16 | ⭐ **+14** | 0 |

⇒ ⭐ **B4 从 8 帧降到 6 帧（−2）**；**B2（6）与 B3（2）一帧没降**。
⇒ **与 C3 的模型吻合**：交接代价 = 「释放 commit + 图块上传」2 帧硬下界 **+ 来方 BG 的图块重定位延迟**。
4bpp 把地图图块从 22,976 B 砍到 11,488 B ⇒ **搬迁压力下降 ⇒ B4 的 +6 余量降到 +4（实测 6 = 2 + 4）**；
但 B2 的 +4 余量（实测 6 = 2 + 4）**没有变化** ⇒ ⚠️ **4bpp 只解决「调色板 16 槽」这一半**：
**交接时地图 BG 仍然被 `map.reset()` 释放**（C3 §3.1 的代码路径）⇒ 屏幕上仍然有 1 帧空屏。
⇒ ⭐ **要真正做到 0 帧，还必须改代码：交接时不要释放/重建整屏 BG**（D6 的 R-D6-4 / C3 的 R-C3-3）。

### 5.3 生成器重跑的证明

| 项 | 结果 |
|---|---|
| 重跑 `tools/generate_butano_battle_runtime_assets.py --graphics <lane graphics>` | ✅ **退出码 0** |
| 重跑后 49 张地图块的 sidecar | ✅ **49/49 = `bpp_4_auto`**（无一回落 `bpp_8`） |
| 重跑后 `battle_14_map_chunk_0.json` | `bpp_4_auto` / `colors_count = 80`（= 5 槽 × 16） |
| 重跑后 `battle_ui_dialogue_background.json` | `bpp_4_auto` / `colors_count = 32`（= 2 槽 × 16） |
| 对白背景的 4bpp 判定 | ✅ **Butano 自己的 `BMP.quantize()` = 32 色 = 2 槽**，**RGB 像素变化 0 / 65,536** |
| ⛔ `tools/butano/generate_battle_ui_assets.py` **整体重跑** | ❌ **跑不起来**（见 §4.2 N-1：`references/battle-scenario-49-ui/*` 与 `artifacts/original-s49-selector1-page1-gpu-20260730-115/*` **本机不存在**，共享树里也没有 `references/` 目录）—— **与本流改动无关的既有缺口** |

### 5.4 ⭐⭐ 25 帧判定台（改后）：**total 上升 ⇒ 触发回归门禁**

收据：`build/w23-f1/align-f1.json`（工具 `tools/s49_wave18/align_capture_steps.py`，
original = `build/w23-f1/bench/capture-original`，remake = `build/w23-f1/bench/capture-remake`）

| 项 | 基线 `build/w22-d1/align-v4.json` | **改后 `build/w23-f1/align-f1.json`** | Δ |
|---|---:|---:|---:|
| **best_offset** | +4 | **+4** | 0 |
| **total field px** | **53,364** | ⭐ **82,831** | **+29,467（上升）** |
| 逐帧相同？ | — | ⭐ **24 / 25 帧的 field px 与基线逐项相同**（2565 / 1294 / 1680 / 2514 / 1940 / 2057 / 1217 / 1921 / 1026 / 759 / 278 / 1212 / 24101 / 195 / 0 / 0 / 43 / 0 / 0 / 106 / 3881 / 1535 / 2696 / 1161） | — |
| **唯一不同的帧** | `step-24-A` = **1,183 px** | ⭐ `step-24-A` = **30,650 px**（best offset 从 +4 变成 **+3**，该帧 6,443 px） | **+29,467** |

**重制侧 35 帧步进逐帧 sha256 对比**（改后 vs 基线 `build/w22-d1/capture-remake-v4`）：

| 步 | 结果 |
|---|---|
| step-03 … step-27 | ⭐ **25 帧逐字节相同**（sha256 全同）⇒ **4bpp 化对画面零变化**（这 25 帧覆盖了战斗段全部 25 个判定帧） |
| step-28 … step-34 | ⛔ **改后全是黑帧**（field mean = 7.34，基线是 139.8 / 142.1 / 142.3 / 142.6 / 140.6 / 140.6 / 169.4） |

⇒ ⚠️ **4bpp 把「对白→地图」交接（B4）缩短了 2 帧 ⇒ 整条时间线在步进里前移 ⇒
判定台的最后一帧（`step-24-A`）对不上（30,650 px ≈ 全屏不同）**。
⇒ ⛔ **按任务书的门禁「25 帧 total 不上升」，这一版属于回归**。

> ⚠️ **但这个结论还不能直接归罪给 4bpp**：判定台的基线 ROM（`align-v4` 用的是 w20-e1 lane 的
> ROM sha `40c41df9…`）**与本流 lane 的代码不是同一份**（共享树在 wave 22 之后又动过），
> ⇒ 必须做**同代码 A/B**（见 §5.5）才能把「4bpp 造成的」与「共享树代码漂移造成的」分开。

### 5.5 ⭐⭐⭐ 同代码 A/B（**决定性**）：回归是 **4bpp 造成的**，不是共享树代码漂移

**为什么必须做这一跑**：判定台的基线 `align-v4.json` 用的是 w20-e1 lane 的 ROM（sha `40c41df9…`），
**与本流 lane 的代码不是同一份** ⇒ 「25 帧上升」不能直接归罪给 4bpp。
⇒ 本流在**同一个 lane、同一份代码、同一套构建环境**下重建了一份 **8bpp 基线 ROM** 做对照。

| 项 | **8bpp 基线 ROM**（同代码） | **4bpp ROM** | Δ |
|---|---:|---:|---:|
| ROM 体积 | **12,258,628 B**（= `build/s49-package-w22/rom/butano-sequel.gba` 的**同一字节数** ⇒ 基线对齐 ✓） | ⭐ **12,165,112 B** | **−93,516 B（−91.3 KiB）** |
| ROM sha256 | `6edab8a47f103532ee6d63064127fead4592ba35cf646f4eaf9f74813ac74c7c` | `558b83e38e2897bc1f70b9b23a025d7eef6e7a58e051ebf16bbba1bc718e133b` | — |
| **25 帧 total**（同一 original 捕获，已核对 25/25 逐字节相同） | **54,959 px** | ⭐ **82,831 px** | **+27,872 px（上升）** |
| 其中 `step-24-A` | 2,778 px | ⭐ **30,650 px** | **+27,872** |
| 其余 24 帧 | 与 4bpp 版**逐项相同** | 同 | 0 |
| 35 帧步进 step-28 … step-34 | **有内容**（mean 139.8 / 142.1 / 142.3 / 142.6 / 140.6 / 140.6 / 169.4） | ⛔ **7 帧全黑**（mean 恒为 7.34，**逐字节相同** ⇒ 画面**冻结**） | ⛔ |

**两个基线的差**（把「代码漂移」和「4bpp」分开）：

| 对比 | total | `step-24-A` |
|---|---:|---:|
| 判定台基线 `align-v4.json`（w20-e1 lane ROM，`40c41df9…`） | 53,364 | 1,183 |
| **本流 8bpp 基线 ROM（同一份当前代码）** | **54,959** | **2,778** |
| **本流 4bpp ROM（同一份当前代码）** | **82,831** | **30,650** |

⇒ ⭐ **共享树代码漂移只贡献 +1,595 px（1,183 → 2,778）**；
⇒ ⭐⭐ **4bpp 化本身贡献 +27,872 px（2,778 → 30,650）** ⇒ **回归是 4bpp 造成的**。

**症状定位**：4bpp ROM 的 `step-28-A` **不是纯黑**（1,359 / 38,400 个非黑像素，
其中 `(255,57,57)` 的红色元素在 (3417, 3433, 3449, 3454, 3466 …)）⇒
**画面停在「深色背景 + 红色选择元素」上，且连续 7 步逐字节不变 ⇒ 画面冻结**。
（同一次构建的 8bpp 版在同一位置显示「地图 + SELECT 画面」。）

⇒ ⚠️ **机理未闭合**（时间预算内没做完）：**最可能是黑场遮罩与「BG 调色板布局」耦合**——
淡入淡出是把 BG 调色板项写成黑色再写回原值，**4bpp 把地图的调色板布局从 256 项压到 80 项**，
⇒ 遮罩写回的槽位与原来不是同一批 ⇒ 某些路径下屏幕停在暗态。
⇒ **这正是 D6 的 R-D6-4 / C3 的 R-C3-3 那一层**（黑场遮罩代码在 `battle_black_field_star_mask.h`，
**不是本流独占文件** ⇒ 只能写成接线请求）。

### 5.6 单测

`wsl bash build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w23-f1/butano-sequel`
⇒ ⭐ **pass=119 / fail=20**（与期望**完全一致**；20 项是预存债，**零新增红**）。
（单测只编译 `game/tests/test_*.cpp`，不编译 `battle_runtime_scene.cpp`，也不碰资产 ⇒ 本流改动不影响它们。）

---

## 6. 交付物清单

| 路径 | 内容 |
|---|---|
| `notes/s49-fidelity/W23-F1-4bpp-assets.md` | 本文件 |
| `build/w23-f1/tools/` | 生成器的**影子副本**（3 个文件已改；共享树零改动） |
| `build/w23-f1/f1-generator-4bpp.patch` | ⭐ **接回共享树的 3 文件 diff（7,510 B）** |
| `build/w23-f1/graphics-4bpp/` | ⭐ **改后的 100 个资产**（49 块地图 × 2 + 对白背景 × 2） |
| `build/w23-f1/rom-4bpp.gba` | 4bpp ROM（12,165,112 B，sha `558b83e3…`） |
| `build/w23-f1/rom-8bpp-baseline.gba` | ⭐ **同代码 8bpp 基线 ROM**（12,258,628 B，sha `6edab8a4…`）—— A/B 对照用 |
| `build/w23-f1/butano-sequel/` | lane 副本（当前状态 = **4bpp 资产 + 4bpp ROM**；`graphics/` 是真实目录） |
| `build/w23-f1/blackfade-after/` | ⭐ 改后黑场收据（`capture.json` / `blackfade.json` / `blackfade.md` / 2402 帧） |
| `build/w23-f1/align-f1.json` | ⭐ 改后 25 帧逐帧（total 82,831） |
| `build/w23-f1/bench-8bpp/` + `build/w23-f1/align-8bpp.json` | ⭐ **同代码 8bpp 基线的步进捕获与 25 帧结果（total 54,959）** |
| `build/w23-f1/report.json` / `report-8bpp.json` | 判定台报告（4bpp / 8bpp） |
| `build/mgba-probe-w23f1/mgba-probe.exe` | 本流私建探针（**没用** `build/mgba-probe-w4/`） |

**最终一致性复核**（交付时状态）：
lane 的 `graphics/` = 4bpp 资产 · lane 的 `build/bn_regular_bg_items_*.h` = `512x512@4` / `bg_palette_item(..., 80, bpp_mode::BPP_4, ...)` ·
lane 的 `butano-sequel.gba` = **12,165,112 B / sha `558b83e3…`**（重跑构建**逐字节复现**同一 sha）⇒ 三者一致 ✓

**两个可忽略的残留**（删除被安全策略拦下，留给父代理）：
`build/w23-f1/_tmp_quant_test.bmp`（Butano 量化器试跑产物）与 `build/w23-f1/gen-out-ui/`（UI 生成器**失败**时的半成品目录，**不要**接回共享树）。

**共享树零改动核对**：共享树 `butano-sequel/graphics` 仍是 1852 个文件；
`tools/generate_butano_battle_runtime_assets.py` 与 `tools/butano/indexed_bmp.py` 里**没有** `bpp_4_auto` / `dedupe_palette` ⇒ 未越界 ✓

---

## 7. 结论与给父代理的三个决定

1. ⭐ **资产层可以交付**（4bpp + 去重 + 生成器改动 + ROM 省 91.3 KiB + 黑场 −2 帧），
   **但接线前必须先修遮罩**（R-F1-3），否则 25 帧判定台 **+27,872 px**。
2. ⭐ **「4bpp 就能消掉黑场」这个预期要下调**：**调色板 16 槽瓶颈确实解开了（33 → 8）**，
   但黑场只从 58 帧降到 56 帧（B4 −2），**B2（6 帧）与 B3（2 帧）一帧没动**
   ⇒ 「交接时释放整张 BG」造成的空屏**不是调色板问题，是代码问题**。
3. ⭐ **下一轮的第一件事应该是 R-F1-3**（让 `battle_black_field_star_mask.h` 的淡入淡出
   按「当前 BG 自己的调色板项数」写回），**然后**再把 4bpp 资产接进去。
   ⇒ 本流已把**资产 + 生成器 + 全部收据**备好，父代理只需：
   * 接 3 个生成器文件（patch 现成）
   * 拷 100 个资产
   * 再派一路修遮罩 → 重新跑黑场 + 25 帧

> ⏰ 本流实际完成时间约 01:1x（父代理 23:50 收口后仍有产出，见本文件）。
