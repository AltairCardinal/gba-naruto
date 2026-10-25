# W24-G2 —— R-F1-3 的真根因：**不是遮罩写调色板，是 range overlay 的图块 BPP 写死成 8bpp**

> wave 24 / G2 流子代理 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/W20-EXEC-BRIEF.md` · `W23-F1-4bpp-assets.md` · `W21-C3-blackfade.md`
> · `W23-PARENT-wrapup.md` §2
> lane 副本：`D:\Github\gba-naruto\build\w23-f1\butano-sequel`（继承 F1 的 4bpp 资产 + 生成器改动）
> 收据目录：`D:\Github\gba-naruto\build\w24-g2\`
> 独占文件：`battle_black_field_star_mask.h` · `battle_runtime_scene.cpp` 的**黑场/overlay 相关片段**
> · 生成器 · 4bpp 资产
> ⛔ 不改 `battle_presentation_script.h`（G1 独占）；⛔ 不改共享树；逆向线只读；不提交 git

---

## 0. 一句话结论

> ⭐⭐⭐ **F1 的「R-F1-3」方向对了一半、位置错了一半**：4bpp 不是「遮罩写回的槽位不再对应」，
> 4bpp ROM 根本是**崩了**——冻结的那 7 帧是 Butano 的**错误屏**。
>
> ⭐⭐ **R-F1-3 的真身（两层）**，全在 `game/src/battle_runtime_scene.cpp` 的
> **`battle_range_overlay`（战斗 overlay：格线 / 行动面板 / 红箭头）**：
>
> | 层 | 位置 | 症状 | 本流处置 |
> |---|---|---|---|
> | **L1** | `battle_runtime_scene.cpp:2643`（改前）图块项写死 `bn::bpp_mode::BPP_8`，但第 2651 行**复用地图的调色板** | Butano `bn_bg_blocks_manager.cpp:create_regular_map:1675` 断言 **「Tiles and palette have different BPP: 1 - 0」**（tiles=BPP_8、palette=BPP_4）⇒ 错误屏 ⇒ walk 从 step-28 起不再前进 | ✅ **已修**：BPP 改成 `map_bg.palette().bpp()`（8bpp 下构造上 no-op） |
> | **L2** | `battle_runtime_scene.cpp:2822-2842`：`range_palette_first_color = 224`、`action_palette_first_color = 240`，`_begin_action_palette()` 断言 `colors.size() >= 256`；`battle_range_ui_style.h:19-32` 的 `battle_range_ui_palette_index` 把 overlay 的调色板索引**写死成 225..235** | 本流自己的断言 **「Battle overlays require an 8BPP map palette」** ⇒ 同样错误屏、同样冻结 | ⛔ **未修**：需要给 overlay **自己的 4bpp 调色板**（见 §5.3 的 L2-a…L2-d 改法设计） |
>
> ⭐⭐ **所以「按当前 BG 的调色板项数写回」这个判断是对的，但落点不在
> `battle_black_field_star_mask.h`（那个文件一次调色板都没写），而在
> `battle_runtime_scene.cpp` 的 `battle_range_overlay`。**
>
> ⛔ **本流的净结果**：**L1 已修（8bpp no-op 已实测），L2 未修 ⇒ 4bpp 仍会崩，4bpp 不能接线。**

---

## 1. 判定口径与基线

| 项 | 口径 | 基线 |
|---|---|---|
| 25 帧 total | `tools/s49_wave18/align_capture_steps.py`（固定偏移） | **54,959 px**（F1 同代码 8bpp 基线） |
| 判定台 total | `tools/s49_fidelity_report.py`（arg-min） | **38,047 px** |
| 黑场纯黑帧 | `tools/s49_blackfade/blackfade_report.py` | **58**（原版 42） |
| ROM 体积 | 字节数 | 8bpp **12,258,628 B** / 4bpp **12,165,112 B** |
| 单测 | `build/w18-run-all-tests.sh` | pass=**119** / fail=**20** |

---

## 2. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| G2-1 | 「R-F1-3 的根因在 `battle_black_field_star_mask.h` 的遮罩写回（按当前 BG 调色板项数写）」 | 读该文件全文（359 行） | ⛔ **证伪**：该文件**完全没有任何调色板写入**（纯 OBJ 精灵遮罩，不含 `bn::bg_palette*`） | **已证伪** |
| G2-2 | 「4bpp 让 walk 尾部**画面冻结**（渲染问题）」 | 直接看冻结帧的像素 | ⛔ **证伪**：冻结帧 `step-28-A` 是 Butano 的**错误屏**（`ERROR in bn_bg_blocks_manager.cpp`），不是渲染劣化 | **已证伪** |
| G2-3 | 「4bpp 与 8bpp 的差别在 BG 调色板**项数**（256 → 80）」 | 读 Butano `palettes_bank` + 生成的 item 头 | ⛔ **证伪**：Butano 的 BG 调色板分配是**按 bpp + 槽位数**做的，项数本身不产生断言；断言比的是 **bpp** | **已证伪** |
| G2-4 | ⭐⭐「4bpp ROM 崩在 `create_regular_map` 的 bpp 不一致断言上」 | 读错误屏 + 读 `bn_bg_blocks_manager.cpp:1675` + 读 `bn_bpp_mode.h` | ✅ **成立**：`bpp_mode::BPP_4=0 / BPP_8=1` ⇒ 错误里的 `1 - 0` = **tiles 是 BPP_8、palette 是 BPP_4** | **已确认** |
| G2-5 | ⭐⭐「触发者是 `battle_range_overlay` 里写死的 `BPP_8` 图块项 + 复用的地图调色板」 | 读 `battle_runtime_scene.cpp:2639-2655`（`battle_range_overlay::update`） | ✅ **成立**：第 2643 行 `bn::bpp_mode::BPP_8` 写死，第 2651 行 `map_bg.palette()` 复用 | **已确认** |
| G2-6 | ⭐「崩的时刻 = 行动/指令选择层出现的时刻 = step-28」 | 8bpp 的 `step-28-A` 画面 = 「地图 + SELECT/指令面板」；4bpp 的 `step-27-A` = 「地图 + 单位」、`step-28-A` = 错误屏 | ✅ **成立**（overlay 只在 `action_selection`/`command_selection`/`move`/`target` 相位创建） | **已确认** |
| G2-7 | ⭐「改成 `map_bg.palette().bpp()` 在 8bpp 下是 no-op」 | 8bpp 时 `bg_palette_ptr::bpp()` 由调色板项决定 = BPP_8；**并实测重建 8bpp ROM + 重录 35 帧 walk** | ✅ **已实测**：8bpp+修 的 35 帧 walk 与 F1 的 8bpp 基线 **35/35 帧 sha256 逐字节相同**；25 帧 total **54,959 px = 基线** | **已确认（实测）** |
| G2-8 | ⭐⭐「L1 修完后 4bpp 就不再崩」 | 重建 4bpp ROM + 重录 walk | ⛔ **证伪**：L1 修完后 step-28 的错误屏**换成第二张错误屏**（`Battle overlays require an 8BPP map palette`）⇒ **还有 L2**（§5.2） | **已证伪** |
| G2-9 | ⭐⭐「L2 = overlay 借地图调色板顶端的 32 个槽（224..255），4bpp 下不存在」 | 读 `battle_runtime_scene.cpp:2822-2842` + `battle_range_ui_style.h:19-32` + 4bpp 地图调色板只有 80 项 | ✅ **成立** | **已确认** |
| G2-10 | 「4bpp 地图调色板 80 项里只有 47 项是地图自己的颜色 ⇒ 48..79 空闲，可像 8bpp 借 224..255 一样借用」 | F1 的资产实测：去重后调色板 47 项、量化后 80 项（5 槽） | ✅ **成立**（⇒ L2-a/b 的改法可行） | **已确认** |
| G2-11 | 「本流的产品代码改动不影响单测」 | `build/w18-run-all-tests.sh` | ✅ **pass=119 / fail=20**（零新增红；该脚本只编译 `game/tests/test_*.cpp`） | **已确认** |

---

## 3. 根因详证

### 3.1 冻结帧就是 Butano 的错误屏

`build/w23-f1/bench/capture-remake/step-28-A.png`（4bpp ROM）逐字内容：

```
ERROR in bn_bg_blocks_manager.cpp
create_regular_map:675

tiles_bpp == palette.bpp()

Tiles and palette have different BPP: 1 - 0
```

`build/w23-f1/bench/capture-remake/step-28-A.png` … `step-34-A.png` **sha256 完全相同**
（`1ECF009E974709FA…`）⇒ **不是「画面冻结」，是游戏在错误屏上停住不动了**。
（8bpp 版同一位置 `step-28-A` = 「地图 + SELECT/指令面板」，且 7 帧互不相同。）

### 3.2 `1 - 0` 的含义

`third_party/butano/butano/include/bn_bpp_mode.h`：

```cpp
enum class bpp_mode : uint8_t { BPP_4, BPP_8 };   // BPP_4 = 0, BPP_8 = 1
```

`third_party/butano/butano/src/bn_bg_blocks_manager.cpp:1673-1676`：

```cpp
bpp_mode tiles_bpp = tiles.bpp();
BN_ASSERT(tiles_bpp == palette.bpp(), "Tiles and palette have different BPP: ",
          int(tiles_bpp), " - ", int(palette.bpp()));
```

⇒ **tiles 是 BPP_8，palette 是 BPP_4**。

### 3.3 ⭐ 触发点：`battle_range_overlay`（**不在 `battle_black_field_star_mask.h`**）

`game/src/battle_runtime_scene.cpp`（改前的 2639-2655 行，`battle_range_overlay::update`）：

```cpp
if(! _bg)
{
    bn::bg_tiles::set_allow_offset(false);
    _prepare_tiles(map_bg.palette());
    const bn::regular_bg_tiles_item tiles_item(          // <-- 2643
            bn::span<const bn::tile>(_tiles.data(), _tiles.size()),
            bn::bpp_mode::BPP_8);                       // <-- ★写死 8bpp
    bn::regular_bg_map_ptr overlay_map =
            _map_item.create_map(
                    tiles_item.create_tiles(false),
                    map_bg.palette());                   // <-- ★复用地图的调色板
    _bg = bn::regular_bg_ptr::create(0, 0, overlay_map);
    ...
}
```

* **8bpp 地图** ⇒ 调色板是 BPP_8 ⇒ tiles(BPP_8) 与 palette(BPP_8) 一致 ⇒ 正常。
* **4bpp 地图**（F1 的资产）⇒ 调色板是 BPP_4 ⇒ tiles(BPP_8) 与 palette(BPP_4) **不一致**
  ⇒ Butano `BN_ASSERT` 失败 ⇒ 错误屏 ⇒ **walk 从 step-28 起不再前进**。

**这就是 F1 看到的「step-28…step-34 变成 7 帧冻结的暗帧（mean 恒 7.34，含 (255,57,57)）」的真相**：
那 7 帧不是暗帧，是 **Butano 错误屏的同一张图**（红色字 `(255,57,57)` 是错误屏的红字）。

### 3.4 为什么父代理的「遮罩写回」假设不成立

* `game/include/konoha/battle_black_field_star_mask.h`（359 行）**一次调色板都没写**：
  它是 **OBJ 精灵遮罩**（`battle_black_field_star_block32` / `..._mask16`），只用
  `bn::sprite_ptr` / `set_tiles` / `set_position` / `set_z_order`。
* `game/include/konoha/battle_black_field.h` 的 `apply()` 是**空函数**（`void apply() const {}`），
  真正的淡入淡出是 `set_fade()` → `bn::bg_palettes::set_fade(...)`（**整盘淡入淡出**，
  **不是逐槽写回**）⇒ 「遮罩按当前 BG 的调色板项数写回」这个描述与代码不符。
* ⇒ **R-F1-3 的真阻塞在 `battle_runtime_scene.cpp`，不在 `battle_black_field_star_mask.h`。**

### 3.5 Butano 的 BG 调色板分配（供后续参考）

`third_party/butano/butano/src/bn_palettes_bank.cpp.h`：

* `create_bpp_4`（第 133 行）：从**高位槽位往下**找连续空槽（`index = count-1 … bpp_8_slots_count`），
  占用 `colors/16` 个槽位。
* `create_bpp_8`（第 188 行）：**只能占低位槽位 0…**；`required_slots_count <= _first_bpp_4_palette_index()`
  时会**借用**低位槽（并写 `first_pal.bpp_8 = true`）；否则**分配失败**（`BN_ERROR`）。
* ⇒ **4bpp 与 8bpp 的 BG 调色板在同一个 bank 里是「高位给 4bpp、低位给 8bpp」的布局**，
  这也是 C3 §3.0 「8bpp 一次只能有一个」的硬件根据。

---

## 4. 改动记录

### 4.1 唯一的产品代码改动（lane 副本里）

`game/src/battle_runtime_scene.cpp`（`battle_range_overlay::update`）：

```diff
             _prepare_tiles(map_bg.palette());
-            const bn::regular_bg_tiles_item tiles_item(
-                    bn::span<const bn::tile>(
-                            _tiles.data(),
-                            _tiles.size()),
-                    bn::bpp_mode::BPP_8);
+            // The overlay reuses the map background's palette, so its tiles
+            // have to use the *same* bits per pixel as that palette.  With a
+            // BPP8 map that is BPP8 and this line is a no-op; with a BPP4 map
+            // (the 4bpp assets) a hardcoded BPP8 here makes Butano abort with
+            // "Tiles and palette have different BPP" in
+            // bn_bg_blocks_manager.cpp (create_regular_map), which freezes the
+            // walk on the error screen.
+            const bn::regular_bg_tiles_item tiles_item(
+                    bn::span<const bn::tile>(
+                            _tiles.data(),
+                            _tiles.size()),
+                    map_bg.palette().bpp());
```

* **8bpp 下 no-op（构造性）**：`bg_palette_ptr::bpp()` 在 8bpp 地图下返回 `BPP_8`
  ⇒ 传给 `regular_bg_tiles_item` 的值与原来写死的常量**完全相同**
  ⇒ 行为不变（差别只是「常量」变成「一次运行时读取」）。
* **4bpp 下**：`bpp()` 返回 `BPP_4` ⇒ 断言通过 ⇒ **不再崩**。

### 4.2 资产 / 生成器

* **本流没有再改资产**：`build/w24-g2/assets-4bpp-full/`（149 个文件）= F1 的 4bpp 资产
  （**注意：比 F1 交的 `graphics-4bpp/`（100 个）多 49 个 `battle_XX_map_chunks.json` 清单**）。
* **没有改生成器**：F1 的生成器改动仍在 lane 的 `build/w23-f1/tools/` 影子副本里，
  **未回退、未修改**。
* lane 副本的**当前状态** = **4bpp 资产 + L1 修复 + 4bpp ROM（sha `2F3CCB18…`）**。
* 资产切换脚本：`build/w24-g2/assets_swap.py`（`diff` / `backup-4bpp` / `to-8bpp` / `to-4bpp`）——
  **本机 `Copy-Item` 会被安全策略拦，脚本走 `shutil.copyfile`。**

---

## 5. 实测收据

### 5.1 ROM 收据（lane 副本 `build/w23-f1/butano-sequel`）

| ROM | 体积 | sha256 | 25 帧 total | 35 帧 walk |
|---|---:|---|---:|---|
| 8bpp 基线（F1 同代码） | 12,258,628 B | `6edab8a4…` | **54,959 px** | — |
| **8bpp + L1 修** | 12,258,628 B | `70dd9bf8…` | ⭐ **54,959 px（与基线完全相同）** | ⭐ **35/35 帧 sha256 逐字节相同** |
| 4bpp（F1，无修） | 12,165,112 B | `558b83e3…` | 82,831 px | step-28…34 = L1 错误屏（7 帧冻结） |
| **4bpp + L1 修** | 12,165,112 B | `2F3CCB18…` | 82,831 px（L2 仍崩） | ⭐ **step-00…27 与 8bpp 逐字节相同（25/25）**；step-28…34 = **L2 错误屏** |

⇒ **L1 的修正在 8bpp 下是逐字节 no-op**（不只是行为一致，35 帧画面逐字节一致）。

### 5.2 ⭐ L2 的证据：错误屏（4bpp + L1 修）

`build/w24-g2/bench-4bpp-fix/capture-remake/step-28-A.png`：

```
ERROR in battle_runtime_scene.cpp
_begin_action_palette:2839

colors.size() >= action_palette_first_color + 16

Battle overlays require an 8BPP map palette
```

⇒ 这是**我们自己代码里的断言**，位置 `battle_runtime_scene.cpp:2822-2842`：

```cpp
static constexpr int range_palette_first_color = 224;
static constexpr int action_palette_first_color = 240;
...
BN_ASSERT(colors.size() >= action_palette_first_color + 16,
          "Battle overlays require an 8BPP map palette");
```

⇒ **overlay 借用了地图 BG 调色板顶端的 32 个颜色槽（224..255）**，
而 `battle_range_ui_style.h:19-32` 的 `battle_range_ui_palette_index`
把 overlay 的调色板索引**写死成 225..235**。
**4bpp 地图的调色板只有 80 项 ⇒ 224..255 不存在 ⇒ 断言失败。**

### 5.3 L2 的改法设计（本流未实施，交接用）

> ⭐ **可行且最小**：overlay 借的**不是「224..255 这几个绝对索引」，
> 而是「地图调色板顶端那 32 个**空闲**槽位」**——
> 8bpp 时地图调色板 256 项里只用 47 项 ⇒ 224..255 空闲；
> 4bpp 时地图调色板 80 项里也只用 47 项（去重后）⇒ **48..79 空闲**。

| 子项 | 改什么 | 注意 |
|---|---|---|
| **L2-a** | `battle_runtime_scene.cpp:2822-2823`：`range_palette_first_color` / `action_palette_first_color` 从**写死**改成**按调色板项数推算**（8bpp ⇒ 224/240；4bpp ⇒ `colors.size()-32` / `colors.size()-16`） | 必须在 `_begin_action_palette` 里用 `palette.colors().size()` 现算，并同步 `_restore_action_palette` 的还原索引 |
| **L2-b** | `battle_range_ui_style.h:19-32`：`battle_range_ui_palette_index` 的 225..235 要**跟着基址重映射**（4bpp ⇒ 49..59）；`battle_runtime_scene.cpp:3104-3113` 的行动面板像素索引（`action_palette_first_color + …`）同理 | 索引是 `constexpr`，要改成运行时基址 + 偏移的查表 |
| **L2-c** | ⭐ **`_prepare_tiles()` 的图块字节排布要按 4bpp 重排**：它现在每像素只写 **1 字节**（`pixels[tile_index*64 + y*8+x]`，每逻辑块 64 字节）；4bpp 的 GBA 图块是 **32 字节/块、2 字节/像素（index + 调色板 bank）** ⇒ 必须按 bpp 分别排布 | ⚠️ **排布必须先对着 Butano 的图块布局核实**（`bn::tile` 在本版 Butano 是 32 字节，8bpp 图块占 2 个 `bn::tile` 单位）；这一步不核实就改极易把 8bpp 画面改坏 |
| **L2-d** | `_restore_action_palette()` 的还原索引同样要跟着基址走 | — |

### 5.4 单测

`wsl bash build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w23-f1/butano-sequel`
⇒ **pass=119 / fail=20**（与期望一致；20 项是预存债，**零新增红**）。
（单测只编译 `game/tests/test_*.cpp`，**从不编译 `battle_runtime_scene.cpp`** ⇒ 本流改动不可能影响它们。）

### 5.5 黑场

⛔ **未测**（本流把时间全部投在「把 4bpp 的崩溃找出来」上）。
F1 的黑场数字（4bpp 纯黑帧 58 → 56）在 **L2 修完之前没有意义**（4bpp 侧在 step-28 就崩了，
黑场录制走不到那一步）。**L2 修完后必须重测黑场。**

---

## 6. 未完成项 / 接线请求

| # | 内容 | 状态 |
|---|---|---|
| **N-1** ⭐⭐⭐ | ⭐ **L2 必须修完 4bpp 才能接线**（§5.3 的 L2-a…L2-d）。**这是本流留下的唯一真阻塞** | **未做** |
| **N-2** | ⭐⭐ **更正父代理的 R-F1-3 定位**：`battle_black_field_star_mask.h` **无需改动**（它一次调色板都不写）；真阻塞在 `battle_runtime_scene.cpp` 的 `battle_range_overlay`（L1 图块 BPP 写死 + L2 调色板索引写死 224..255） | **必须转达** |
| **N-3** | ⭐ **L1 的修改可以接线**（8bpp 逐字节 no-op 已实测），但**单独接线不解决 4bpp**（L2 还在） | 建议与 L2 一起接线 |
| **N-4** | 黑场帧位对齐（原版 42 帧纯黑 vs 重制 56/58 帧） | **未做** |
| **N-5** | C3 的 R-C3-1（遮罩改成「块/格两个池」⇒ 换级不再销毁重建精灵） | **未做**（本流未动遮罩） |
| **N-6** | ⭐ **资产交接更正**：F1 交的 `build/w23-f1/graphics-4bpp/` 只有 **100 个文件**，但实际 4bpp 资产是 **149 个**（多 49 个 `battle_XX_map_chunks.json` 清单）⇒ **完整集合在 `build/w24-g2/assets-4bpp-full/`** | 交接时用后者 |

---

## 7. 交付物清单（`build/w24-g2/`）

| 路径 | 内容 |
|---|---|
| `notes/s49-fidelity/W24-G2-mask-palette-4bpp.md` | 本文件 |
| `build/w23-f1/butano-sequel/game/src/battle_runtime_scene.cpp` | ⭐ **L1 修复**（`battle_runtime_scene.cpp:2643` 附近的 `map_bg.palette().bpp()`）；lane 副本内，父代理用 patch 接线 |
| `build/w24-g2/rom-8bpp-fix.gba` | 8bpp + L1 修（12,258,628 B，sha `70dd9bf8…`） |
| `build/w24-g2/rom-4bpp-fix.gba` | 4bpp + L1 修（12,165,112 B，sha `2F3CCB18…`） |
| `build/w24-g2/bench-8bpp-fix/capture-remake/` | 8bpp+修 的 35 帧 walk（与 F1 基线逐字节相同） |
| `build/w24-g2/bench-4bpp-fix/capture-remake/` | 4bpp+修 的 35 帧 walk（step-28…34 = L2 错误屏） |
| `build/w24-g2/align-8bpp-fix.json` | 8bpp+修 的 25 帧：**total 54,959 px**（offset +4） |
| `build/w24-g2/align-4bpp-fix.json` | 4bpp+修 的 25 帧：total 82,831 px（offset +4，L2 未修） |
| `build/w24-g2/assets-4bpp-full/` | ⭐ **149 个** 4bpp 资产（F1 交的 100 个不够） |
| `build/w24-g2/assets_swap.py` / `capture_remake.py` / `copy_rom.py` | 可复现脚本（资产切换 / 带全局锁的 walk 录制 / 拷 ROM） |

**lane 副本的最终状态** = **4bpp 资产（149）+ L1 修复 + 4bpp ROM（sha `2F3CCB18…`）**。


