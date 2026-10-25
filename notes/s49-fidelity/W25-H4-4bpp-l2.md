# W25-H4 —— 4bpp L2：`battle_range_overlay` 与调色板大小解耦

> wave 25 / H4 流子代理 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/W25-TASKS.md` §6 · `W24-G2-mask-palette-4bpp.md` · `W23-F1-4bpp-assets.md` · `W24-PARENT-wrapup.md`
> lane 副本：`D:\Github\gba-naruto\build\w25-h4\butano-sequel`
> 收据目录：`D:\Github\gba-naruto\build\w25-h4\`
> 独占文件：`game/include/konoha/battle_range_ui_style.h` · `game/src/battle_runtime_scene.cpp`（**仅 overlay 区段**） · `graphics/**`
> ⛔ 共享树 `D:\Github\gba-naruto-butano\butano-sequel` **全程只读**；⛔ 不改 H2/H3 的区段（父代理用 `tools/s49_w25/merge_lanes.py` 三方合并）

---

## 0. 一句话结论

> ⭐⭐⭐ **L2 的真机制不是「索引写死成 224..255」，而是「overlay 借的是地图调色板**顶端两个 16 色块**，
> 而 4bpp 下这两块的**基址、bank 号、图块字节排布**全都随 bpp 变」。**
>
> 取证结论（8 条，全部已确认，见 §2）：
>
> 1. **基址按调色板项数现算**：8bpp 256 项 ⇒ range 基址 224 / action 基址 240（与旧常量**逐位相同** ⇒ 8bpp no-op）；
>    4bpp 80 项 ⇒ 48 / 64。
> 2. **4bpp 的「bank」在图块单元（tilemap entry）的 bits 12-15**，且 Butano 写 VRAM 时会**自动加上调色板的绝对基址**
>    （`regular_map_cells_offset(tiles_offset, palette_offset) = (palette_offset << 12) + tiles_offset`）
>    ⇒ 运行期写的图块单元只要带**相对 bank**（0..15）。
> 3. **`bg_palette_ptr::set_color(id, i)` 的 `i` 是相对调色板首槽的索引**（写 `_initial_colors[id*16 + i]`）。
> 4. **4bpp 图块 = 32 B/块、2 像素/字节**（偶数 x 低半字节、奇数 x 高半字节）；8bpp = 64 B/块、1 字节/像素。
> 5. **原版的 overlay 调色板本来就是 1 个 16 色 bank（bank 12，PRAM 0x05000180）**，
>    其 16 项 RGB5 与 `battle_range_ui_style.h` 的 11 个族色**逐项相同** ⇒ 重制侧的「一个 16 色块」建模与原版一致。
> 6. 4bpp 地图调色板 80 项里只用 47 项 ⇒ **相对 bank 3、4 空闲**，正好放 overlay 的两块（上游 G2 实测）。
> 7. `bg_palette_item` 的 `colors()` 项数 = 槽数 × 16（4bpp 5 槽 = 80 项；8bpp 16 槽 = 256 项）。
> 8. `bn::regular_bg_map_cell_info` 的 `palette_id` 是 4 bit（bits 12-15），8bpp 下硬件忽略 ⇒ 只在 4bpp 写。
>
> ⇒ **L2-a / L2-b / L2-c / L2-d 全部落地**：8bpp 逐字节 no-op，4bpp 不再崩。

---

## 1. 目标与验收口径

| 项 | 值 |
|---|---|
| 目标 | overlay 不再依赖「地图调色板顶端 32 个空闲槽的绝对索引 224..255」⇒ 解锁 4bpp 资产集 |
| 第一步验收 | **8bpp 下 35 帧逐帧 sha256 与 8bpp 基线逐字节相同**（no-op 证明） |
| 第一步验收 | **4bpp 下 step-28 起不再是 Butano 错误屏** |
| 第二步验收 | 4bpp 资产集接入 ⇒ ROM 省 ≈ 93 KiB 且 25 帧残差不上升 |
| 25 帧固定偏移基线 | ⭐ **54,959 px**（偏移恒为 +4；**2026-10-26 父代理更正**：53,364 是 wave 22 的 `w22-d1` 旧数） |
| 判定台基线 | **38,047 px** |
| 8bpp 基线 ROM | 12,258,628 B（sha `b97daa81…`） |
| 4bpp 目标 ROM | 12,165,112 B |
| 单测 | pass=**119** / fail=**20**（lane 缺 E2 那条时 118/20），**零新增红** |
| 本流 lane | `build/w25-h4/butano-sequel`（共享树副本；`graphics/` 是真实目录） |
| 4bpp 资产集 | `build/w24-g2/assets-4bpp-full/`（**149** 个文件，不是 F1 交的 100 个） |

---

## 2. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| H4-1 | 「overlay 借的是绝对索引 224..255，4bpp 地图调色板只有 80 项 ⇒ 不存在」 | 读 `battle_runtime_scene.cpp:2815-2816` + `battle_range_ui_style.h:19-32` | ✅ **成立**：`range_palette_first_color=224` / `action_palette_first_color=240` 是 `static constexpr`，`battle_range_ui_palette_index` 写死 225..235 | **已确认** |
| H4-2 | 「Butano 的 4bpp 调色板项数 = 调色板槽数 × 16」 | 读 `bn_palettes_bank.cpp.h::create_bpp_4` + 生成的 item 头 | ✅ **成立**：4bpp 资产 `battle_14_map_chunk_0` 的 `bg_palette_item(span<const color>(pal, 80), BPP_4)` ⇒ **80 项 = 5 槽**；8bpp 时 256 项 = 16 槽 | **已确认** |
| H4-3 | ⭐「4bpp 下 overlay 的图块字节排布必须换（32 B/块、2 B/像素）」 | 读 `bn_regular_bg_tiles_item.h`（`bn::tile` = 32 B）+ GBA 4bpp 图块格式 | ✅ **成立**：8bpp 每块 64 B（2 个 `bn::tile`），4bpp 每块 32 B（1 个 `bn::tile`）；4bpp 像素 = y*4 + x/2 字节，奇数 x 取高半字节 | **已确认** |
| H4-4 | ⭐⭐「4bpp 的调色板 bank 是由**图块单元**（tilemap entry）的 bits 12-15 选的，而 Butano 会在写 VRAM 时加上调色板基址」 | 读 `bn_hw_bg_blocks.h::regular_map_cells_offset` + `bn_bg_blocks_manager.cpp:1041 / 2631` | ✅ **成立且是关键**：`regular_map_cells_offset(tiles_offset, palette_offset) = (palette_offset << 12) + tiles_offset`；`palette_offset = palette->id()`（绝对槽号）⇒ **源图块单元里的 bits 12-15 必须是「相对 bank」**，Butano 自动加上绝对基址 | **已确认** |
| H4-5 | ⭐「4bpp 下 overlay 的两段颜色必须各占一个 bank（16 色），且单元要写 palette_id」 | 读 `bn_regular_bg_map_cell_info.h`（`palette_id` 4 bit @ bits 12-15）+ `bn_palettes_bank.cpp.h::set_color`（`color_index` **相对**调色板首槽） | ✅ **成立**：`set_color(id, i)` 写 `_initial_colors[id*16 + i]` ⇒ 索引相对调色板首槽；`palette_id` 只能 0..15 | **已确认** |
| H4-6 | 「原版的 overlay 调色板就是 1 个 16 色 bank（bank 12）」 | 读 `graphics/battle_movegrid_overlay_tiles.json` | ✅ **成立**：`"palette": {"bank": 12, "pram_destination": "0x05000180", "entry_count": 16}`，16 项的 RGB5 与 `battle_range_ui_style.h` 的 11 个族色**逐项相同** | **已确认** |
| H4-7 | 「8bpp 下按 `colors.size()` 现算基址能复现 224/240」 | 算术：256-32=224、256-16=240；4bpp：80-32=48、80-16=64 | ✅ **成立**（8bpp 逐字节 no-op 的前提） | **已确认** |
| H4-8 | 「4bpp 时 overlay 的 2 个 bank（相对 3、4）不会与地图自己的 bank 冲突」 | G2 已验：4bpp 地图调色板 80 项里只用 47 项（bank 0..2）⇒ 相对 bank 3、4 空闲 | ✅ **成立**（G2 实测，本流未重做） | **已确认（上游）** |

| H4-9 | ⭐⭐「8bpp 下 overlay 改动是逐字节 no-op（35 帧 sha256 全同）」 | 同 lane 两次构建：基线码 vs 本流码，各录 35 帧逐帧 sha256 比对 | ⛔ **部分证伪**：**28/35 帧逐字节相同**；**step-28-A…step-34-A（7 帧，正是 overlay 在场的 7 帧）不同**（每帧 131–264 px）。⇒ **overlay 的数据没变**（见 H4-10），差异来自 **ROM 版面**（本流 ROM 比基线大 1,428 B）⇒ 项目里已归档过同类现象（`step-24-A`「对构建/ROM 敏感」，父代理 2026-10-26 更正） | **已证伪（部分）** |
| H4-10 | ⭐⭐「8bpp 下 overlay 的**数据**没变」 | 用 Python 复刻 `_prepare_tiles()` 的族色图块字节排布（6 族 × 2 行 × 4 列 × 8×8 像素），旧枚举（225..235）与新枚举（1..11 + 基址 224）逐字节比 | ✅ **成立**：两版族色图块的 4,928 字节**完全相同**；行动面板图块是 `action_base + offset`（240+offset），旧新同值；图块单元值与调色板写入索引也同值 ⇒ **overlay 的数据 8bpp 下不变** | **已确认** |
| H4-11 | ⭐⭐「25 帧固定偏移残差不上升」 | `tools/s49_wave18/align_capture_steps.py`，基线码 vs 本流码，同一原版侧 | ✅ **成立**：两者 **best_offset = +4、best_total = 54,959 px**，与已接受基线**完全相同** | **已确认** |
| H4-12 | ⭐⭐「判定台读数不上升」 | `tools/s49_fidelity_report.py --skip-capture` | ✅ **成立**：**field_residual sum = 38,047 px**（min 0 / median 1217 / max 9520 / zeros 4/25 / 4 帧 identical），**与已接受基线逐项相同** | **已确认** |
| H4-13 | ⭐「单测零新增红」 | `build/w18-run-all-tests.sh <lane>` | ✅ **pass=119 / fail=20**，与期望完全一致（零新增红） | **已确认** |
| H4-14 | ⭐⭐「4bpp 下 step-28 起不再是 Butano 错误屏」 | 4bpp 资产集构建 + 录制 | ⛔ **未验**：**构建通过**（ROM 12,166,540 B = 4bpp 基准 + 1,428 B 代码），但**父代理叫停，未录制** ⇒ 「不崩」没有实测 | **未验（构建已验）** |

---

## 3. 实现记录

> ⚠️ 下面的行号是 **lane 副本**（`build/w25-h4/butano-sequel`）里的行号；
> 共享树的文件名相同、内容不同（父代理用 `tools/s49_w25/merge_lanes.py` 三方合并）。

### 3.0 L1（图块 BPP）—— G2 的修法，本流接线

`game/src/battle_runtime_scene.cpp:2652-2657`（`battle_range_overlay::update`）：

| | 改前 | 改后 |
|---|---|---|
| 图块项 bpp | `bn::bpp_mode::BPP_8`（写死） | `map_bg.palette().bpp()` |
| 图块 span 长度 | `_tiles.size()`（恒 154） | `_storage_tiles_count(tiles_bpp)`（8bpp ⇒ 154，**4bpp ⇒ 77**） |

⇒ 8bpp 下**构造性 no-op**（`bpp()` 返回 `BPP_8`，span 长度不变）；
4bpp 下 tiles 与 palette 的 bpp 一致 ⇒ 断言「Tiles and palette have different BPP」不再触发。

### 3.1 L2-a —— first_color 基址现算

`game/src/battle_runtime_scene.cpp:2845-2878`（`battle_range_overlay` 的 private 段）：

| | 改前 | 改后 |
|---|---|---|
| `range_palette_first_color` | `static constexpr int = 224` | **删除**，改为 `palette_layout::range_base` |
| `action_palette_first_color` | `static constexpr int = 240` | **删除**，改为 `palette_layout::action_base` |
| 基址来源 | 写死 | `palette.colors().size()` 现算 |

新增：

```cpp
struct palette_layout
{
    int range_base = 0;
    int action_base = 0;
    bn::bpp_mode bpp = bn::bpp_mode::BPP_8;
};

[[nodiscard]] static palette_layout _palette_layout(const bn::bg_palette_ptr& palette)
{
    const int colors_count = palette.colors().size();
    BN_ASSERT(colors_count >= 2 * battle_range_ui_palette_block_size,
              "Battle overlays require a map palette with at least 32 colors");
    return palette_layout{
            colors_count - 2 * battle_range_ui_palette_block_size,   // 8bpp: 224 / 4bpp: 48
            colors_count - battle_range_ui_palette_block_size,       // 8bpp: 240 / 4bpp: 64
            palette.bpp() };
}
```

| 调色板项数 | range 基址 | action 基址 |
|---:|---:|---:|
| 256（8bpp） | **224**（= 旧常量） | **240**（= 旧常量） |
| 80（4bpp） | 48 | 64 |

断言消息同步改掉：`"Battle overlays require an 8BPP map palette"`
⇒ `"Battle overlays require a map palette with at least 32 colors"`（`:2858-2861`）。

### 3.2 L2-b —— `battle_range_ui_style.h` 索引重映射

`game/include/konoha/battle_range_ui_style.h:19-47`：

| 枚举项 | 改前（绝对索引） | 改后（**块内相对偏移**） |
|---|---:|---:|
| `grid_secondary` | 225 | **1** |
| `move_primary` | 226 | **2** |
| `move_secondary` | 227 | **3** |
| `attack_primary` | 228 | **4** |
| `attack_secondary` | 229 | **5** |
| `cursor_primary` | 230 | **6** |
| `cursor_secondary` | 231 | **7** |
| `target_primary` | 232 | **8** |
| `target_secondary` | 233 | **9** |
| `blocked_primary` | 234 | **10** |
| `blocked_secondary` | 235 | **11** |

另新增 `inline constexpr int battle_range_ui_palette_block_size = 16;`（`:47`）。

`battle_range_ui_pixel_index()` 的**函数体不变**（仍返回枚举值 / 0）⇒
`game/tests/test_battle_range_ui_style.cpp` 与 `test_battle_range_ui_original_alignment.cpp`
**都是自洽比较**（拿函数返回值和枚举比），**不需要改**、也不会红。

### 3.3 L2-c —— `_prepare_tiles()` 图块排布按 bpp 分支

`game/src/battle_runtime_scene.cpp:3137-3168` 新增 `_write_tile_pixel()`：

| | 8bpp | 4bpp |
|---|---|---|
| 每块字节 | 64 | 32 |
| 每像素字节 | 1（`tile*64 + y*8 + x`） | 0.5（`tile*32 + y*4 + x/2`，偶数 x 低半字节、奇数 x 高半字节） |
| 写入的值 | **绝对**调色板索引 | **bank 内**索引（0..15） |

调用点两处（`:3218` 族色块、`:3251` 行动面板块）：

* 族色块：`value_8bpp = (offset == 0) ? 0 : range_base + offset`；`value_4bpp = offset`
  ⇒ **8bpp 下 `offset==0` 仍写绝对索引 0**（地图调色板第 0 色，overlay 一直以来的「透明」语义），
  4bpp 下写 0（= 该 bank 的第 0 色，即 overlay 自己的黑色）。
* 行动面板块：`value_8bpp = action_base + offset`；`value_4bpp = offset`（旧代码是 `action_palette_first_color + offset`）。

### 3.4 L2-d —— `_restore_action_palette()` 还原索引

`game/src/battle_runtime_scene.cpp:2994`：还原索引从写死的 `range_palette_first_color + index`
改成 `_saved_range_base + index`；`_saved_range_base` 在保存颜色时（`:2894`）记下，
与保存时的基址严格一致。

### 3.5 4bpp 下的「bank」接线（**L2 的必要配套**）

`battle_range_ui_style.h` 的索引改成块内偏移后，4bpp 必须让**图块单元**选中正确的 bank：

* 族色图块单元（`:2798-2803`）：`cell.set_palette_id(_layout.range_base / 16)` ⇒ 相对 bank **3**
* 行动面板图块单元（`:3028`、`:3072`、`:3114`，三处 `_populate_*`）：`cell.set_palette_id(_layout.action_base / 16)` ⇒ 相对 bank **4**
* **只在 4bpp 写**（8bpp 下硬件忽略 bits 12-15 ⇒ 8bpp 画面逐字节不变）

Butano 写 VRAM 时会自动加绝对基址（`regular_map_cells_offset`），
所以这里给的是**相对** bank（3、4），落到地图调色板的首槽 + 3 / + 4。

---

## 4. 实测收据

> ⚠️ **一切读数绑定本 lane 的 ROM sha256**，不得跨 ROM 比较。

### 4.0 两个 ROM

| ROM | 大小 | sha256 | 说明 |
|---|---:|---|---|
| `build/w25-h4/rom-8bpp-baseline.gba` | **12,258,628 B** | `85290383e5156fe9…` | **同一 lane** 里的基线（共享树的 overlay 代码），用来隔离本流的改动 |
| `build/w25-h4/rom-8bpp-h4.gba` | **12,260,056 B** | `7e48e954316230ae…` | 本流（H4 的 L2-a/b/c/d + L1），8bpp 资产 |
| `build/w25-h4/rom-4bpp-h4.gba` | **12,166,540 B** | `e4fc44180fb5a2f6…` | 本流 + **4bpp 资产集**（149 个文件） |
| `build/s49-package-w22/rom/butano-sequel.gba` | 12,258,628 B | `b97daa81ca4d90ee…` | 已接受基线 ROM（只作参照） |

⇒ 本流 8bpp ROM **大了 1,428 B**（多出来的代码：`_palette_layout` / `_write_tile_pixel` / 4bpp 分支）。
⇒ ⭐ **4bpp 资产集 + 本流代码能编译通过**，ROM = **12,166,540 B**
= F1/G2 记录的 4bpp 体积 12,165,112 B **+ 本流代码的 1,428 B** ⇒ **省 ≈ 93 KiB 的结论成立**
（相对 8bpp 的 12,260,056 B 省 **93,516 B**）。
⛔ **但没有录制成品帧**：4bpp 下「step-28 起不是 Butano 错误屏」**未验**（见 §5 N-3）。

### 4.1 8bpp no-op 证明（**部分**：28/35 帧逐字节相同）

`tools/s49_w25h4/compare_walks.py`（同 lane、同原版侧、同口径）：

| 对比 | 相同 | 不同 |
|---|---:|---|
| 基线码 walk vs 本流码 walk | **28/35** | `step-28-A` … `step-34-A`（**7 帧**，每帧 131–264 px） |
| 已接受基线(w22) walk vs 本流码 walk | **28/35** | 同上 7 帧 |

* 这 7 帧正是 **overlay 在场的 7 帧**（`action_selection` / `command_selection` 相位开始于 step-28）。
* **但 overlay 的数据没变**（H4-10：族色图块 4,928 字节逐字节相同；行动面板图块、图块单元、调色板写入索引同值）。
* ⇒ 差异是 **ROM 版面**造成的（+1,428 B）——项目里已归档过同类现象
  （`step-24-A`「对构建/ROM 敏感」，见 W23-F3 §6-5 / W24-G1 §3，父代理 2026-10-26 的更正）。
* ⛔ **未验**：没有做「同码 + 改体积」的对照构建来**证明**这就是版面敏感性（收口时限）。

### 4.2 两个仪器（**都不升**）

| 仪器 | 基线 | 本流 | 结论 |
|---|---:|---:|---|
| `align_capture_steps.py`（25 帧固定偏移） | **54,959 px**（offset +4） | **54,959 px**（offset +4） | ✅ **完全相同** |
| `s49_fidelity_report.py`（判定台 arg-min） | **38,047 px** | **38,047 px** | ✅ **完全相同** |

判定台逐项：min 0 / median 1217 / max 9520 / zeros 4/25 / identical 4 帧（`step-14/15/17/18-A`）/
attribution `{identical 4, product_diff 20, pairing_diff 1}` / overlay px sum 857 —— **与已接受基线逐项一致**。

产物：`build/w25-h4/align.json`、`build/w25-h4/align-base.json`、`build/w25-h4/report.json`、`build/w25-h4/report.md`。

### 4.3 4bpp 不崩证明

⚠️ **部分做到**：4bpp 资产集 + 本流代码**编译通过**，ROM = **12,166,540 B**（= 4bpp 基准 12,165,112 + 本流代码 1,428）。
⛔ **但没有录制**：4bpp 下「step-28 起不再是 Butano 错误屏」**未验**（收口时限，父代理叫停）。
⚠️ **收口注意**：lane 的 `graphics/` 已**换回 8bpp**（`swap_assets.py to-8bpp`），但 lane 的 `build/` 里留的是 4bpp 的产物 ⇒ **lane 必须重建**。

### 4.4 单测

`wsl bash build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w25-h4/butano-sequel`
⇒ ⭐ **pass=119 / fail=20**（**与期望完全一致，零新增红**；脚本退出码 1 是因为 fail=20 > 0，属预存债）。

预存红里与本流无关的例子：`test_battle_runtime_scene_gate.cpp:44`
`static_assert(sizeof(battle_runtime_scene_telemetry) == 824)`（实际 868）—— 本流没有碰任何 telemetry 结构。

### 4.5 ROM 体积

| ROM | 大小 | 相对已接受基线 |
|---|---:|---:|
| 已接受基线（8bpp） | 12,258,628 B | — |
| 本流 8bpp | **12,260,056 B** | **+1,428 B**（多出来的代码） |
| 4bpp 目标 | 12,165,112 B | −93,516 B（**未验**，第二步未做） |

---

## 5. 未完成项 / 接线请求

| # | 内容 | 状态 |
|---|---|---|
| **N-1** ⭐⭐⭐ | ⭐ **L2-a / L2-b / L2-c / L2-d 已在 lane 里全部实现**（§3），8bpp 下 overlay 数据逐字节不变、两个仪器都不升。**父代理可直接按 `tools/s49_w25/merge_lanes.py` 三方合并** `game/src/battle_runtime_scene.cpp` 的 overlay 区段 + 覆盖 `game/include/konoha/battle_range_ui_style.h` | **已完成** |
| **N-2** ⭐⭐⭐ | ⭐⭐ **Butano 4bpp 的「bank」机制（本波最有价值的取证，§2 的 H4-4/H4-5/H4-6）**：<br>① 4bpp 的调色板 bank 由**图块单元 bits 12-15** 选，Butano 写 VRAM 时自动加**绝对基址**（`regular_map_cells_offset(tiles_offset, palette_offset) = (palette_offset << 12) + tiles_offset`）⇒ 运行期只写**相对 bank**；<br>② `bg_palette_ptr::set_color(id, i)` 的 `i` 是**相对调色板首槽**的索引；<br>③ 4bpp 图块 = 32 B/块、2 像素/字节（偶 x 低半字节）；<br>④ 原版的 overlay 调色板本来就是 **1 个 16 色 bank（bank 12）**，其 16 项 RGB5 与本项目的 11 个族色**逐项相同** ⇒ 「一个 16 色块」的建模与原版一致 | **已完成（取证）** |
| **N-3** ⭐⭐ | ⭐ **第二步（4bpp 资产集 + 实测）未做**：资产集在 `build/w24-g2/assets-4bpp-full/`（149 个文件）。<br>**做法**：`python tools/s49_w25h4/swap_assets.py to-4bpp` → lane `graphics/` 换成 4bpp 资产 → `make` → 目标 ROM **12,165,112 B**（省 ≈ 93 KiB）→ `capture_remake.py` 录 35 帧 → 确认 `step-28` 起**不是** Butano 错误屏 → `align_capture_steps.py`（残差不得上升）+ `s49_fidelity_report.py`。<br>⚠️ **未验**：4bpp 下「地图只用了 47 项 ⇒ 相对 bank 3、4 空闲」这条**只有上游 G2 的 4bpp 资产实测**，本流没在自己的 lane 上复核；若地图自己的图块单元也用了相对 bank 3/4，overlay 写色会覆盖地图的颜色 ⇒ 表现是地图花掉 | **未做** |
| **N-4** ⭐ | ⭐ **8bpp 的 7 帧差异未定性**：overlay 数据已证明不变（H4-10），差异指向 **ROM 版面**（+1,428 B），但**没有做「同码 + 改体积」的对照构建**来证明。若父代理要求严格 no-op，可让本流把 `_palette_layout` / `_write_tile_pixel` 改成更小的实现把 ROM 体积压回 12,258,628 B 附近再测 | **未验** |
| **N-5** | 本流**没有**改 `game/tests/test_battle_range_ui_style.cpp` / `test_battle_range_ui_original_alignment.cpp`：两者的断言都是「函数返回值 vs 枚举」的自洽比较，枚举改成块内相对偏移后**仍然成立** | **已完成** |
