# Z2 —— 「開始」标题屏素材 + 四角星光圈（图形侧）

> 2026-10-24 · wave 7 · 流 Z2 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/WAVE7-TASKS.md` §0/§2、`Y2-opening-title-blackfade.md`、
> `W3-original-truth.md`（黑场真值表）
> 工具（新）：`tools/s49_opening_title/make_title_assets.py`、
> `tools/s49_opening_title/measure_vram_headroom.py`、
> `tools/s49_starfield/{analyze_star_iris,star_geometry,make_star_mask_assets,probe_original_mask,align_replay}.py`
> ⛔ **未改** `game/src/battle_runtime_scene.cpp` / `battle_scene_controller.h`（Z1 独占）
> ⛔ **未改** `battle_presentation_*.h`（Z3 独占）；逆向线全程只读；**未提交 git**

---

## 0. 一句话结论

> **任务 A 达成**：标题美术已经转成 5 个 Butano sprite item 放进 `graphics/`，
> **VRAM 余量实测 = 部署画面 662 块空闲 OBJ 图块，标题只要 208 块 ⇒ 装得下**；
> 投影残差 **5,869 / 4,699 → 264 / 341**（Y2 原始美术是 264 / 333，
> 差的 8 px 是重制侧自己的小鸟动画）。
> **任务 B 达成「素材 + 曲线」**：⭐ **原版的黑场被证明是一个「旋转的四角星光圈」，
> 不是亮度渐变** —— 它的 12 级淡出 / 18 帧全黑 / 12 级淡入共 66 帧，
> 逐帧的**可见像素数**已经量出来并做成了 Butano 素材，
> **生成的位图回读校验：66/66 帧逐帧相等**（`shipped_bitmap_round_trip_ok = true`）。
> **但有一个硬约束没解开**：一帧星光圈遮罩要 **640 块 OBJ 图块（20 KB）**，
> 部署画面空闲 662 块（**装得下**），战斗画面最紧时只剩 **336 块（装不下**），
> ⇒ 第二个黑场事件必须先腾出图块，或者改用「旋转 + 缩放」的近似模型。

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `butano-sequel/graphics/battle_opening_title_kai.{bmp,json}` | **新** | 「開」64x64，2 个相位 |
| `butano-sequel/graphics/battle_opening_title_shi_top.{bmp,json}` | **新** | 「始」上 64x64，2 个相位 |
| `butano-sequel/graphics/battle_opening_title_shi_right.{bmp,json}` | **新** | 「始」右 32x64，2 个相位 |
| `butano-sequel/graphics/battle_opening_title_shi_bottom.{bmp,json}` | **新** | 「始」下 64x32，2 个相位 |
| `butano-sequel/graphics/battle_opening_title_shi_corner.{bmp,json}` | **新** | 「始」右下 32x32，2 个相位 |
| `butano-sequel/graphics/battle_black_field_star_mask.{bmp,json}` | **新** | ⭐ 四角星光圈遮罩，25 级 × 40 块 = 1000 帧，4bpp |
| `butano-sequel/game/include/konoha/battle_black_field_star.h` | **新** | 星光圈的几何规格（无引擎依赖，可上主机单测） |
| `butano-sequel/game/include/konoha/battle_black_field_timing.h` | **改** | 加 `star_mask_level()`（纯逻辑） |
| `butano-sequel/game/include/konoha/battle_opening_title.h` | **改** | 写清 sprite item 的名字 / 格子 / 偏移 / 图块数 |
| `tools/s49_opening_title/make_title_assets.py` | **新** | 标题 PNG → Butano sprite item + 投影残差 |
| `tools/s49_opening_title/measure_vram_headroom.py` | **新** | **VRAM 余量实测**（读 Butano 分配器自己的计数器） |
| `tools/s49_starfield/analyze_star_iris.py` | **新** | 星光圈逐帧几何 + 均值曲线 |
| `tools/s49_starfield/star_geometry.py` | **新** | 星光圈的四角 / 四腰极值 |
| `tools/s49_starfield/make_star_mask_assets.py` | **新** | 星光圈 → Butano sprite item + **逐帧曲线对照** |
| `tools/s49_starfield/probe_original_mask.py` | **新** | 探针实验：原版黑场那一帧的 GPU 状态（DISPCNT / BGCNT / OAM） |
| `tools/s49_starfield/align_replay.py` | **新** | 把探针回放与项目自己的帧捕获对齐 |
| `notes/s49-fidelity/Z2-title-art-starfield.md` | **新** | 本报告 |

---

## 2. 任务 A：「開始」标题屏素材

### 2.1 原版真值（沿用 Y2 的抽取）

| 项 | 真值 | 来源 |
|---|---|---|
| 绘制方式 | **OBJ sprite**（BG 寄存器跨拍全同） | Y2 |
| 「開」 | 屏幕框 (41, 49)，美术 **59x62** | `build/s49-opening-title/projection.json` |
| 「始」 | 屏幕框 (135, 42)，美术 **70x70** | 同上 |
| 调色板 | 4 个不透明灰阶，RGB5 **4 / 13 / 22 / 31** | Y2 |

> ⚠️ **修正一条上游数字**：Y2 报告写「始」是 **63x70**；
> 实测 `projection.json` 的 `glyph_boxes` 是 `[135, 42, 205, 112]` ⇒ **70x70**。
> 美术文件 `tools/s49_opening_title/shi.png` 的墨迹包围盒也是 `(0,0,70,70)`。
> 这不是小事：70 > 64 ⇒ **不能只拆成两块**，
> 右边那 6 列也要单独一块（见 §2.3）。

### 2.2 ⭐ 美术清洗（Y2 的原始美术有污染像素）

`shi.png` 里有 **1 个** 非灰阶像素 `(148,148,33)`，
`shi-phase1.png` 里有 **21 个**（草地绿 / 黄绿 + 8 个 `(247,255,222)`）。
它们**不可能**属于标题：原版标题只有 4 个不透明色（Y2 实测），
所以这些像素是差分掩码把**会动的小鸟**捞进来的。

处理规则：**不是 4 个灰阶的不透明像素 ⇒ 变透明**（不是变灰）。
理由：原版那一帧这些位置就是**草地的颜色**（小鸟移开了），
所以重制侧同一位置应该透出**重制侧自己的**草地。

⇒ **投影残差（用发的美术重算）**：

| 量 | Y2 原始美术 | 本流发出的美术 | 差 |
|---|---:|---:|---|
| 原版标题拍 vs 重制侧同相位画面 | 5,869 | 5,869 | — |
| **投影 phase 0** | **264** | **264** | 0 |
| **投影 phase 1** | **333** | **341** | **+8** |

那 8 px 的来历：phase 1 里 8 个 `(247,255,222)`（近白）被清成透明后，
透出的是重制侧自己的画面，而原版那里是草绿 ⇒ **差 8 px 是重制侧的小鸟动画，
不是标题的错**（Y2 原始美术之所以是 333，是因为它把原版的草地像素原样搬了过来，
那是错的）。

### 2.3 ⭐ 拆块方案（「始」70x70 ⇒ 4 块）

GBA OBJ 的合法尺寸只有 `8x8 16x16 32x32 64x64 16x8 32x8 32x16 8x16 8x32 16x32 32x64`。
**`16x64` 与 `16x32` 不合法**（第一次构建就被 `grit` 拒了：
`Invalid sprite size: (: 16x64)`）⇒ 窄边那一片只能用 32 宽。

| sprite item | 格子 | 覆盖 | 图块 |
|---|---|---|---:|
| `battle_opening_title_kai` | 64x64 | 「開」59x62，行 0..61 / 列 0..58 | 64 |
| `battle_opening_title_shi_top` | 64x64 | 「始」行 0..63 / 列 0..63 | 64 |
| `battle_opening_title_shi_right` | 32x64 | 「始」行 0..63 / 列 64..95 | 32 |
| `battle_opening_title_shi_bottom` | 64x32 | 「始」行 64..95 / 列 0..63 | 32 |
| `battle_opening_title_shi_corner` | 32x32 | 「始」行 64..95 / 列 64..95 | 16 |
| **合计（一个相位）** | | | **208 图块 = 6,656 B** |

每个 item 的位图里横排 2 帧（相位 0 / 相位 1），
`json` 必须是 `{"type":"sprite","width":W,"height":H}`：
⚠️ **多帧 item 必须显式写 `width`**，否则 Butano 会把整个位图宽度当成
item 宽度，构建直接报 `Invalid sprite width: 128`（第一次构建就踩到了）。

### 2.4 ⭐ VRAM 余量实测（验收口径）

**测法**：Butano 的精灵图块分配器是**稀疏**的（最适应配，会把分配摊在整个区域上），
所以**高水位不是空闲空间**（实测高水位 = 1023/1024，但实际只用了 481 块）。
真正能回答问题的是**分配器自己的计数器**
`bn::sprite_tiles::available_tiles_count()`：

```powershell
# 计数器在 EWRAM 里的位置来自链接后的 ELF，不是猜的：
#   arm-none-eabi-nm -C butano-sequel.elf | grep sprite_tiles_manager
#       -> 02029a38 b bn::sprite_tiles_manager::(anonymous namespace)::data_buffer
#   arm-none-eabi-objdump -d butano-sequel.elf   （_allocate_impl 的字面量池）
#       -> free_tiles_count 的成员偏移 = 5740
```

`python tools/s49_opening_title/measure_vram_headroom.py` 实测（重制侧开场，
键序 `Down,Down` + `A*22`，240 帧空转）：

| 帧 | 相位 | **已用 / 1024 块 OBJ 图块** | **空闲** |
|---:|---|---:|---:|
| 334 | 准备场景 | 481 | 543 |
| 428 | 准备场景 | 481 | 543 |
| 522 | 部署画面 | 314 | **710** |
| 616 … 1462 | 部署画面 → 战斗 | 354–362 | **662–670** |
| **1650 / 1838** | **战斗（最紧）** | **688** | **336** |
| 2026 | 战斗 | 634 | 390 |
| 2214 / 2402 | 战斗 | 556–580 | 444–468 |

⇒ **结论**：OBJ 图块区共 **1024 块（32 KB）**；
**标题要 208 块** ⇒
* **部署画面（标题出现的地方）空闲 662–710 块 ⇒ 装得下，还剩 454–502 块** ✔
* 全程最紧时（战斗画面）空闲 336 块 ⇒ **标题不能在那时还占着**（它不在那时显示，OK）

同时 BG 图块区（`0x06000000-0x0600FFFF`）实测高水位 **40,144 / 65,536 B**，
空余 **25,392 B** ⇒ 本流的新素材只占 OBJ 区，不碰 BG 区。

> ⚠️ **素材现在是「已转换、未链接」的状态**：
> Butano 的图形工具已经把 7 个位图转成了 `build/bn_sprite_items_*.h`
> （构建日志：`graphics size: 512032 bytes` 等），
> 但**只要还没有代码 include 那些头，位图数据就不会进 ROM**
> （`arm-none-eabi-nm` 里查不到 `battle_opening_title_kai_bn_gfxTiles`）。
> ⇒ **ROM 现在没有变大**是正常的；等 Z1 接线点 1 加上 include + 绘制后才会链进去。
> 同理，**VRAM 的占用也只在精灵被创建时才会发生**。

### 2.5 生成的调色板（已从构建产物里读回验证）

`build/battle_opening_title_kai_bn_gfx.s` 的 `Pal:` 段：

```
.hword 0x7C1F,0x1084,0x35AD,0x5AD6,0x7FFF,0x0000,...
```

| 索引 | 16 位值 | RGB5 | 8 位展开 | 期望 |
|---:|---|---:|---:|---|
| 0 | 0x7C1F | (31, 0, 31) | 洋红 | 透明 |
| 1 | 0x1084 | (4, 4, 4) | 33 | 灰阶 1 ✔ |
| 2 | 0x35AD | (13, 13, 13) | 107 | 灰阶 2 ✔ |
| 3 | 0x5AD6 | (22, 22, 22) | 181 | 灰阶 3 ✔ |
| 4 | 0x7FFF | (31, 31, 31) | 255 | 灰阶 4 ✔ |

⇒ **和原版的 4 个灰阶逐位相同**（RGB5 4/13/22/31）✔

---

## 3. 任务 B：四角星光圈（真 1:1 的关键）

### 3.1 ⭐ 真相：原版的黑场是**旋转的四角星光圈**

Y2 说「淡出/淡入是四角星光圈的收缩/扩张」但没量化。本流把它量化了：

| 量 | 实测 |
|---|---|
| 遮罩中心 | **(120, 81)**（12 级全部一样） |
| 淡出 | **12 级 × 2 GBA 帧** = 帧 1013…1036 |
| 全黑 | 帧 1037…1054（18 帧） |
| 淡入 | **12 级 × 2 GBA 帧** = 帧 1055…1078 |
| 每级的「四角」角度 | 62°, 79°, 95°, 113°, 130°, 146°, 164°, 180°, 194°, 215°, 229°, 247°（**每级 ≈ +16.9°**，模 90°） |
| 每级的四角半径 | 88.25 → 79.75 → 67.75 → 58.75 → 46.00 → 37.75 → 29.50 → 25.50 → 17.00 → 12.75 → 8.25 → 3.75 |
| 腰半径 / 四角半径 | ≈ **0.36**（各级不变 ⇒ 12 级是**同一个形状的缩放 + 旋转**） |
| 面积 ∝ 半径² | 成立（误差 ≤ 5 %，小半径时是像素量化） |

⇒ **原版的星光圈 = 一个固定的四角星形状，按级缩放 + 按级旋转**。

### 3.2 ⭐ 遮罩素材（Butano sprite item）

`tools/s49_starfield/make_star_mask_assets.py` 从原版帧里量出每一级的遮罩
（判定：纯黑**且**与屏幕边缘连通的那片是遮罩，剩下的就是星光圈的洞），
再切成 **32x32 的 OBJ 精灵网格**（GBA 精灵最大 64x64，遮罩要盖满 240x160）：

* 网格 **8 列 × 5 行 = 40 块**（第 8 列越过屏幕右缘 16 px，被裁掉）
* 级数 **25** = 12 淡出 + **1 全黑** + 12 淡入
* 位图 `256 x 4000`（1000 帧），4bpp，**一个 Butano item**：
  `battle_black_field_star_mask`，`{"type":"sprite","width":32,"height":32}`
* **图块账**：每级 40 块 × 16 图块 = **640 块（20,480 B）**；
  25 级全进 ROM = **16,000 块 = 512,032 B**（构建实测 `graphics size: 512032 bytes`）

> ⚠️ Butano 的 item 是「一帧 = 连续的一段图块」，
> 所以位图里**帧的排布必须与 GRIT 的 map 顺序一致**
> （map f 在 map 网格的 `(f % 8, f / 8)` 处）。
> 第一次写成了「按像素顺序平铺」，回读校验立刻报 24/24 级不匹配
> （7390 vs 7925 px）⇒ 修正后 **24/24 级全对**。

### 3.3 ⭐ 逐帧曲线对照（判据）

一帧的**均值 = 可见面积 × 洞里画面的亮度** ⇒
**只要遮罩留下的可见像素数与原版逐帧相同，均值曲线就一致**。

`build/s49-starfield/star-mask-assets.json` 里有 **66 行**（淡出 24 + 全黑 18 + 淡入 24）：

| phase | level | frame | 原版均值(红) | 原版可见 px | 遮罩可见 px | 一致 |
|---|---:|---:|---:|---:|---:|---|
| fade_out | 0 | 1013 | 33.320 | 7925 | 7925 | OK |
| fade_out | 0 | 1014 | 33.320 | 7925 | 7925 | OK |
| fade_out | 1 | 1015 | 27.751 | 6561 | 6561 | OK |
| … | | | | | | |
| fade_out | 11 | 1036 | 0.050 | 17 | 17 | OK |
| black | 12 | 1037…1054 | 0.000 | 0 | 0 | OK |
| fade_in | 13 | 1055 | 0.092 | 21 | 21 | OK |
| … | | | | | | |
| fade_in | 24 | 1078 | 31.050 | 7200 | 7200 | OK |

完整表：`build/s49-starfield/curve-table.md`（66 行）。

**判决**：
* `visible_pixels_identical_on_every_frame = true`
* `shipped_bitmap_round_trip_ok = true`
  （这是**非平凡**的校验：**把发出的 .bmp 读回来**重新量可见像素，
  24 级全部与原版相等 —— 证明位图编码、帧排布、裁剪都没丢东西）

### 3.4 ⚠️ VRAM：星光圈装得下吗（**没解开的硬约束**）

| 相位 | 空闲 OBJ 图块 | 星光圈要 | 结论 |
|---|---:|---:|---|
| 部署画面（第一个黑场） | 662–710 | 640 | ✅ **装得下**（余 22–70 块，很紧） |
| 战斗画面（第二个黑场） | **336** | 640 | ❌ **装不下** |

⇒ 两个出路（**都要 Z1 决定**，我不动 `.cpp`）：
1. **黑场期间释放场景精灵**：黑场画面本来就被遮罩盖住，
   场景的精灵在遮罩期间是看不见的 ⇒ 可以在遮罩期间销毁/重建。
   （实测：战斗画面用了 688 块，遮罩只要 640 ⇒ 必须先释放 ≥ 304 块。）
2. **改用「旋转 + 缩放」近似**：4 枚带仿射矩阵的精灵（VRAM 只要 4×64 = 256 块），
   但那样**遮罩的外边界会跟着缩放往里缩**，盖不满屏幕 ⇒ 需要额外的「静态黑底」精灵，
   而静态黑底又会盖住洞 ⇒ **这条路在纯精灵模型里走不通**
   （原因写在 §6 的假设台账 Z2-11）。

---

## 4. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| Z2-V1 | `python tools/s49_opening_title/make_title_assets.py --graphics …` | 生成 5 个 sprite item | 5 个 item，**208 图块/相位**，投影残差 **264 / 341** |
| Z2-V2 | 构建产物 `build/battle_opening_title_kai_bn_gfx.s` 的 `Pal:` | 4 个灰阶逐位相同 | `0x1084/0x35AD/0x5AD6/0x7FFF` ⇒ RGB5 **4/13/22/31** ✔ |
| Z2-V3 | `python tools/s49_opening_title/measure_vram_headroom.py` | 空闲 OBJ 图块 | 部署画面 **662–710 空闲**；全程最紧 **336**（战斗画面） |
| Z2-V4 | `python tools/s49_starfield/analyze_star_iris.py` | 12 级 × 2 帧 + 均值 | 帧 1013…1036 各 2 帧，中心恒为 (120, 81) |
| Z2-V5 | `python tools/s49_starfield/star_geometry.py` | 四角 / 四腰极值 | 四角半径 88.25…3.75，腰/角 ≈ 0.36，旋转 ≈ +16.9°/级 |
| Z2-V6 | `python tools/s49_starfield/make_star_mask_assets.py` | 遮罩素材 + 曲线 | **66/66 帧可见像素相等**；`shipped_bitmap_round_trip_ok = true` |
| Z2-V7 | WSL `make -j4`（显式 `LIBBUTANOABS`）+ `make -B -j4` 全量重建 | 构建通过 | **ROM fixed!**（exit 0）；图形转换通过（`grit` 接受全部 7 个位图），星光圈 item 头 `graphics count = 1000`、`tiles = 16000`、`BPP_4` ✔ |
| Z2-V8 | `bash build/w1-run-all-tests.sh` | 失败集合与 HEAD 基线逐名相同 | 见 §4.1 |
| Z2-V9 | 孤儿进程检查 | 0 个 | `Win32_Process` → `mgba-probe.exe` **count=0** |
| Z2-V10 | 编码自检 | 新文件 LF、无 BOM | 12 个新文件 + 3 个改文件全部 `BOM=False CRLF=0`（见 §10） |
| Z2-V11 | `git status --short`（重制线） | 只碰本流独占区 | 只有上面列出的 16 个文件；`battle_runtime_scene.cpp` / `battle_scene_controller.h` / `battle_presentation_*.h` 未出现在本流的改动里 |

### 4.1 单测棘轮

见 §8（由本流的最后一次运行给出）。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Z2-1 | 「開始」美术可以直接放进 `graphics/` | 放进 + 构建 + 跑 ROM | 构建通过；VRAM 部署画面 662 块空闲 ≫ 208 块 | **已确认** |
| Z2-2 | Y2 的 `kai/shi` PNG 是干净的 | 数颜色 | ⛔ `shi.png` 有 1 个、`shi-phase1.png` 有 21 个非灰阶像素（小鸟污染） | **已证伪（已清洗）** |
| Z2-3 | 污染像素应该变灰（保住字形） | 两种清洗各跑一次投影 | 变灰 ⇒ 残差 354；变透明 ⇒ **341** ⇒ 变透明 | **已证伪** |
| Z2-4 | Y2 报告的「始」是 63x70 | 读 `projection.json` + 美术包围盒 | 实际 **70x70** ⇒ 要 4 块而不是 2 块 | **已证伪（已修正）** |
| Z2-5 | 多帧 sprite item 只要写 `height` | 构建 | 报 `Invalid sprite width: 128` ⇒ **必须显式写 `width`** | **已证伪（已修）** |
| Z2-6 | 窄边那一片可以用 16x64 | 构建 | `grit` 拒：`Invalid sprite size: 16x64` ⇒ 只能用 32 宽 | **已证伪（已改）** |
| Z2-7 | VRAM 空闲 = 区域高水位 | 探针量区域 | 高水位 1023/1024 但实际只用 481 块 ⇒ 分配器是稀疏的，高水位**不是**空闲 | **已证伪（改读分配器计数器）** |
| Z2-8 | 标题的 208 块在**所有**相位都装得下 | 分配器计数器全程采样 | 部署画面 662 块空闲 ✔；战斗画面最紧 336 块 ⇒ 标题不在那时显示，OK | **已确认** |
| Z2-9 | 原版黑场是亮度渐变 | 看原版帧 | ⛔ 是**旋转的四角星光圈**：洞里亮度不变，均值下降只因可见面积缩小 | **已证伪（Y2 的结论，本流量化）** |
| Z2-10 | 星光圈 12 级是同一个形状的缩放 | 面积 ∝ 半径² | 成立（误差 ≤ 5 %，小半径是像素量化）；腰/角半径比恒 ≈ 0.36 | **已确认** |
| Z2-11 | 星光圈可以用「旋转 + 缩放」的少量精灵实现 | 几何推演 | ⛔ **不行**：遮罩的外边界（屏幕边缘）不随缩放变化，
而洞随缩放变 ⇒ 缩放后盖不满屏幕；要盖满就得有静态黑底，静态黑底又盖住洞 | **已证伪（所以走逐级素材路线）** |
| Z2-12 | 逐级素材一帧要多少 VRAM | 图块账 | **640 块/级**（40 块 × 16）；战斗画面只剩 336 ⇒ 第二个黑场装不下 | **已确认（未解决 ⇒ §7 风险 1）** |
| Z2-13 | 原版是用 OAM 精灵画遮罩 | 探针读原版那一帧的 DISPCNT/BGCNT/OAM | DISPCNT = 0x1940（**读数与画面对不上**）、OAM 里 80 个 8x8 精灵处于 **disabled** 位 ⇒ **本流没能定位原版的画法** | **未验（不影响本流交付）** |

---

## 6. 接线点清单（交给 Z1 / 父代理）

> 行号基于 2026-10-24 的 `battle_runtime_scene.cpp`（Z1 在并行改，请按符号名定位）。
> ⛔ 本流**一行都没改** `.cpp`。

### 接线点 1 —— 标题的 sprite item（任务 A）

* 新增素材（已在 `graphics/`）：
  `battle_opening_title_kai` / `_shi_top` / `_shi_right` / `_shi_bottom` / `_shi_corner`
  （每个 2 帧 = 相位 0/1）
* 需要的 include：
  `#include "bn_sprite_items_battle_opening_title_kai.h"` 等 5 个
* 画法（**精灵以格子中心定位**，所以位置要加半格）：
  * 「開」：美术在 (41,49) 59x62，格子 64x64 ⇒ 精灵中心 = (41+32, 49+32) = **(73, 81)**
  * 「始」四块：
    | 块 | 格子 | 美术左上角 | 精灵中心 |
    |---|---|---|---|
    | top | 64x64 | (135, 42) | (167, 74) |
    | right | 32x64 | (199, 42) | (215, 74) |
    | bottom | 64x32 | (135, 106) | (167, 122) |
    | corner | 32x32 | (199, 106) | (215, 122) |
  * 相位切换：`create_sprite(x, y, phase)`（phase = 0/1）；
    或建好精灵后用 `set_tiles(bn::sprite_items::X.tiles_item(), phase)`。
* **相位机在 `battle_opening_title.h`**：`begin()` / `advance()` / `phase()` /
  `visible()` / `finish()` 已在（Y2 写的）。

### 接线点 2 —— 跳过 READY 四行（**必做**，Y2 的原话）

* 位置：`battle_runtime_scene.cpp` 的 `render_deployment_text()`
* 做法：标题显示期间**不画** `… DEPLOY` / `START` / `READY` / `A:OK B:BACK`
  （原版那个位置**没有文字**；投影正是靠抹掉这 631 px 才从 5,869 降到 264 的）
* 需要一个「标题正在显示」的开关（`battle_opening_title::visible()` 已经有了）

### 接线点 3 —— `deployment.complete()` 分支改成「画标题 → 等 A → 走黑场」

* 位置：`battle_runtime_scene.cpp` 的 `deployment.complete()` 分支
* 做法：
  1. `title.begin()`；
  2. 每帧 `title.advance()`，并按 `title.phase()` 换相位；
  3. 玩家按 A ⇒ `title.finish()`，然后走 `battle_black_field` 的黑场。

### 接线点 4 —— 黑场改成星光圈（任务 B，**本流只提供素材 + 级别表**）

* 新增 include：
  `#include "bn_sprite_items_battle_black_field_star_mask.h"`
* 级别表在 `battle_black_field_star.h`
  （`level_count = 25`、`black_level = 12`、`blocks = 40`、`cell = 32`、
  `graphics_index(level, block)`、`block_x(block)`、`block_y(block)`、
  `visible_pixels[25]`）
* 状态机在 `battle_black_field_timing.h`：`star_mask_level()`
  （淡出 ⇒ 0..11，全黑 ⇒ 12，淡入 ⇒ 13..24，空闲 ⇒ -1）
* 画法：40 枚 32x32 精灵，每帧按 `graphics_index(level, block)` 换图块：
  * `block_x(block) = (block % 8) * 32`，`block_y(block) = (block / 8) * 32`
  * 精灵位置 = 格子中心 = `(block_x + 16, block_y + 16)`
  * 优先级要高于地图与 HUD（`set_bg_priority(0)`）
* ⚠️ **VRAM**：一帧要 640 块（20 KB）。部署画面空闲 662 块（够），
  **战斗画面最紧时只有 336 块 ⇒ 第二个黑场事件必须先释放场景精灵**（见 §3.4）

### 接线点 5 —— 黑场时序常量（Y2 的，未做）

* `battle_runtime_scene.cpp:189` `battle_black_field_event1_hold_frames` 10 → **7**
* `battle_runtime_scene.cpp:190` `battle_black_field_event2_hold_frames` 24 → **12**
* `battle_runtime_scene.cpp:7935-7943` 战斗场景的淡入块上移到场景第一次
  `bn::core::update()` 之前（消掉 1521…1522 那 2 帧亮缝）

---

## 7. 卡在哪 / 剩余风险

1. **⭐ 星光圈的 VRAM（未解决）**：一帧 640 块，战斗画面只剩 336 块。
   ⇒ 第二个黑场事件要么先释放场景精灵，要么改模型。
   本流**没有**动 `.cpp`，所以这条只能由 Z1/父代理决断。
2. **⭐ 原版的画法没定位**：探针读到的 DISPCNT = 0x1940
   （mode 0、无 BG、无 OBJ）与「画面明明有地图和精灵」矛盾；
   同一时刻 OAM 里 80 个 8x8 精灵都带 **disabled** 位。
   ⇒ **要么探针的寄存器读取口径有偏差，要么原版那一帧的状态与我想的不同**。
   这不影响本流的交付（原版的行为已经量出来了），
   但它挡住了「照抄原版实现」这条路。
3. **原版「始」的相位 1 美术偏小**：`shi-phase1.png` 的墨迹只有 62x63，
   而相位 0 是 70x70。差分掩码在这一相位捞到的笔画更少 ⇒
   **相位 1 的美术可能缺了一圈描边**（投影残差 +8 px 也指向这里）。
   要修得**逐帧重抓原版**（`tools/s49_package/capture_blackfade.py` 的 Lua，
   `MGBA_W3_CAPTURE=all`）。
4. **残差不是 0**：投影值 264 / 341 里的 ~300 px 是**重制侧战场自身**的差
   （小鸟动画帧 + 其它），不是标题造成的 ⇒ 「0 附近」要在小鸟逐帧对齐后才可达。
5. **星光圈的 25 级是逐像素烘焙的**：原版若是「同一个形状缩放 + 旋转」，
   重制侧可以用更省的模型（见台账 Z2-11 的结论），但纯精灵模型下走不通；
   如果换成 **mode 1 的仿射 BG**（调色板 0 号色透明），
   遮罩外边界与洞就能分开处理 —— **这是本流没有探索的方向**。

---

## 8. 单测棘轮

**HEAD 基线**（`bash build/run-baseline-tests.sh`，`git archive HEAD` 快照）：

```
FAIL(run) test_battle_all_scenario_runtime      FAIL(run) test_battle_campaign_route
FAIL(compile) test_battle_campaign_save          FAIL(run) test_battle_campaign_scenario_42
FAIL(run) test_battle_campaign_scenario_43       FAIL(run) test_battle_campaign_scenario_44
FAIL(run) test_battle_campaign_scenario_45       FAIL(run) test_battle_campaign_scenario_46
FAIL(run) test_battle_campaign_scenario_47       FAIL(run) test_battle_campaign_scenario_49
FAIL(run) test_battle_dynamic_deployment_turn    FAIL(run) test_battle_material_pickups
FAIL(run) test_battle_presentation_controller    FAIL(compile) test_battle_runtime_scene_gate
FAIL(run) test_battle_s49_input_flow             FAIL(run) test_battle_s49_opening
FAIL(run) test_battle_scene_character_actions    FAIL(run) test_battle_scene_controller
FAIL(run) test_battle_scene_multi_unit           FAIL(run) test_battle_scene_results
```

**工作区**（`bash build/w1-run-all-tests.sh`，本流最终状态）：
**`w1-all-tests: pass=109 fail=20`**，失败名单与上面 **逐名相同** ⇒
**new red = 0** ✔ **棘轮是绿的。**

⚠️ **本流一度把棘轮弄红了，已修**：我把 `battle_opening_title::glyphs[1].width`
从 Y2 写的 63 改成实测的 70（见 §2.1 / 台账 Z2-4），
`test_battle_opening_title`（Y2 新加的、**不在 HEAD 基线里**）因此失败
⇒ 那是**一项新增红**。修法：**把那个单测的断言同步成实测值 70**，
并把头文件里的 `right` 从 198 改成 205（135 + 70 = 205）。
该测试文件是 **untracked**（Y2 加的），**不在本流的独占清单里**，
但它断言的正是本流改的头文件常量，不同步就会把棘轮弄红 ⇒ 改动已在此说明。

---

## 9. 复跑命令

```powershell
# 0) 私有探针（不要覆盖共享的 build/mgba-probe/mgba-probe.exe）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-z2'
python tools/mgba_probe/build.py

# 1) 标题素材 + 投影残差
python tools/s49_opening_title/make_title_assets.py \
    --graphics "D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics" \
    --out build/s49-opening-title/title-assets.json

# 2) VRAM 余量实测
python tools/s49_opening_title/measure_vram_headroom.py \
    --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
    --out build/s49-opening-title/vram-headroom.json

# 3) 星光圈几何 + 素材 + 逐帧曲线
python tools/s49_starfield/analyze_star_iris.py \
    --frames build/s49-blackfade/original-entry-v2/frames \
    --out build/s49-starfield/original-fadeout.json \
    --markdown build/s49-starfield/original-fadeout.md \
    --first 1012 --last 1038
python tools/s49_starfield/star_geometry.py \
    --frames build/s49-blackfade/original-entry-v2/frames \
    --first 1013 --last 1036 --out build/s49-starfield/geometry-fadeout.json
python tools/s49_starfield/make_star_mask_assets.py \
    --frames build/s49-blackfade/original-entry-v2/frames \
    --graphics "D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics" \
    --out build/s49-starfield/star-mask-assets.json

# 4) 构建（必须显式导出 LIBBUTANOABS）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 5) 单测棘轮
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh
```

---

## 10. 边界声明

* 逆向线 `D:\Shell\Github\gba-naruto-reverse` **全程只读**（本流甚至没有打开它）。
* **未改** `game/src/battle_runtime_scene.cpp`、`battle_scene_controller.h`
  （Z1 独占）与 `battle_presentation_*.h`（Z3 独占）。
* 重制线的改动**只有**：
  * `graphics/` 下 **12 个新文件**（5 个标题 item + 1 个星光圈 item，各 bmp + json）：
    `battle_opening_title_kai` / `_shi_top` / `_shi_right` / `_shi_bottom` /
    `_shi_corner` / `battle_black_field_star_mask`；
  * `game/include/konoha/battle_black_field_star.h`（**新**）；
  * `game/include/konoha/battle_black_field_timing.h`（**改**：加 `star_mask_level()`）；
  * `game/include/konoha/battle_opening_title.h`（**改**：写清 sprite item 规格，
    「始」宽 63 → **70**（实测），`right` 198 → **205**）；
  * `game/tests/test_battle_opening_title.cpp`（**改**：断言 63 → 70，
    见 §8 的说明；这是 Y2 加的 untracked 文件，不同步就会让棘轮变红）。
* **未提交 git**；新文件一律 **LF、无 BOM**（12 个新文件 + 3 个改文件全部自检通过）。
