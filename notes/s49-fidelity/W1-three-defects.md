# W1 —— 修 3 个新查实的产品缺陷（wave 15）

> 工具：`tools/s49_battle_balance/w1_palette_probe.py`（**新增**：调色板 bank 台账探针）、
> `tools/s49_battle_balance/w1_palette_state.py`（**新增**：Butano 调色板 bank 解码）、
> `tools/s49_battle_balance/w1_utf8_scan.py`（**新增**：UTF-8 合法性扫描）
> 产物：`build/w1/`（`palette-{a..i}/` + `rom-w1a.gba` / `rom-w1b.gba` + `judgment-{base,w1}.json`）
> 2026-10-24 · 流 W1（wave 15）。**所有数字都是本机实测。**
> 重制线改了 3 个文件（见 §1）；逆向线 **零改动**；**未提交 git**。

---

## 0. 一句话结论

**三个缺陷都修好了，但「打完仗」这一条只做到一半。**

* **D1（OBJ 调色板 cohort 耗尽）修好了**：根因**不是**「16 个 bank 不够用」
  （实测峰值 14/16），而是**静态的 dimmed 调色板**在「调色板几乎占满时」被创建
  ⇒ 落在 bank 的**低位**（index 3）⇒ Butano 的 `create_bpp_8` 只把 bank **前端**给 BPP8 调色板
  ⇒ 肖像的 128 色 BPP8 调色板再也拿不到 8 个 bank ⇒ `BPP8 palette create failed. Colors count: 128`
  ⇒ **ROM 停机**。把 dimmed 调色板跟 map cohort 一起释放之后，**战斗不再停机**：
  闭环驱动器打到了**第 3 回合**（修前第 2 回合的对白就是停机点）。
* **D2（战后对白 / 任务菜单没有 UI 层）修好了**：新增两个相位专属的 UI 层；
  两屏**都有实际画面**（战后对白 7 页：说话人 + 台词；任务菜单：世界地图 + 信息框）。
* **D3（战后对白文本非法 UTF-8）修好了**：根因**不是**编码错，而是**折行器按字节而不是按字符拷贝**，
  把三字节的中文切成了半个字符 ⇒ `Invalid UTF-8 character` ⇒ ROM 停机。
  修好后**结算链一路走到 `complete`**（战后对白 → 任务菜单 → 画面交给战役）。
* ⛔ **但「由真实战斗产生的 `outcome=1`」没有拿到**：闭环战斗驱动器卡在**目标选择**
  （仪器侧：不知道行动的目标策略），整场仗**没有打完** ⇒ 结算链收据里的 `outcome=1`
  仍然是 poke 进控制器的（Z1 的老办法）。**见 §9。**
* **判定台残差没有变大**（同口径、同帧集：总和 **109,569** / 中位 **1,372** / 全 0 帧 **4**，
  与基线 ROM **逐项相同**；本流 ROM sha `fb9d2dbd…`）。

---

## 1. 改动文件清单

### 1.1 重制线（`D:\Shell\Github\gba-naruto-butano\butano-sequel`）

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `…\game\include\konoha\battle_ui_model.h` | **修改** | ⭐ **D2**：新增 `battle_ui_layer::post_battle_dialogue` / `task_menu` 两个层，并在 `make_battle_ui_model()` 里把这两个相位映射到自己的层（原来落到 `default:` ⇒ `hidden`）。 |
| `…\game\src\battle_runtime_scene.cpp` | **修改** | ⭐ **D1**：dimmed 调色板改成可释放的存储；新增 `release_map_sprite_palettes()`，在 map cohort 释放时把 **dimmed 调色板**和**单位的运行时轮廓调色板**一起还给 Butano。<br>⭐ **D3**：`_add_dialogue_text()` 的折行器改成**按字符**拷贝（新增 `battle_settlement_utf8_character_size()`）。<br>**D2 的配套**：UI 渲染器与 `render_battle_ui_text()` 对这两个新层提前返回（战斗 UI 不画在这两屏上）。 |
| `…\game\include\konoha\battle_presentation_content.h` | **未改** | 战后对白的文本内容是合法 UTF-8（`w1_utf8_scan.py` 扫过），**不需要改内容**。 |
| `…\game\include\konoha\battle_result_content.h` | **未改** | 同上（W3 也独占这个文件，本流不碰）。 |

### 1.2 本仓库（`D:\Github\gba-naruto`）

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `notes\s49-fidelity\W1-three-defects.md` | **新增** | 本文件。 |
| `tools\s49_battle_balance\w1_palette_probe.py` | **新增** | ⭐ **调色板 bank 台账探针**：跑路线 + 每 60 帧 dump 一次 Butano 的 sprite/BG 调色板 bank 并解码。 |
| `tools\s49_battle_balance\w1_palette_state.py` | **新增** | Butano `bn::palettes_bank` 的内存布局解码器（布局用 ELF 的 DWARF 核对过：`palette` 28 字节，`usages` @0，`slots_count` @22，`bpp_8` @25；`palettes_bank` 1704 字节）。 |
| `tools\s49_battle_balance\w1_utf8_scan.py` | **新增** | 扫描 C/C++ 源文件里的字符串字面量是不是合法 UTF-8。 |
| `tools\s49_battle_balance\y1_play.py` | **修改** | ⚠️ **仪器**：路线驱动器对「过期路线步」和「ROM 多跑出来的对白」变得宽容（见 §4.4），并支持**路线循环**（路线比战斗短）。 |
| `build\w1\*` | **产物** | ROM 副本、调色板台账、判定台收据。 |

### 1.3 没有改的

* `battle_black_field*.h` / `graphics\`（W3 独占）**一个字节没动**；
* `tools\s49_package\`（W2/W4 独占）**一个字节没动**；
* 逆向线 `D:\Shell\Github\gba-naruto-reverse` **未访问**；
* 共享的 `build/mgba-probe/mgba-probe.exe` **未动**（私有探针建在 `build/mgba-probe-w1/`）。

---

## 2. D1：OBJ 调色板 cohort 耗尽（ROM 停机）

### 2.1 现象（复现）

`build/w1/rom-w1a.gba`（本流第一次构建，sha `5d2d49b4…`）上跑 `routeY.json`：

```
step 57 (A, phase 18): the dialogue never advanced
final phase: script_blocked (round 2)
画面：ERROR in bn_palettes_bank.cpp.h / create_bpp_8:265
      BPP8 palette create failed. Colors count: 128
      There are no more available colors.
```

⇒ 第 2 回合的对白处 ROM 停机，**战斗永远打不完**。

### 2.2 ⭐ 根因（实测，不是推测）

**Butano 的分配规则**（`third_party/butano/butano/src/bn_palettes_bank.cpp.h`）：

* 硬件只有 **16 个** sprite 调色板 bank（`bn_hw_palettes.h`：`count() == 16`，
  每个 bank 16 色 ⇒ 共 256 色）；
* **BPP4 调色板从 bank 的**高端**往下分配**（`create_bpp_4()` 从 `count()-1` 往下扫）；
* **BPP8 调色板只能住 bank 的前端**（`create_bpp_8()`）：
  `required_slots_count <= _first_bpp_4_palette_index()` —— 只要**低位**有一个活着的
  BPP4 调色板，BPP8 就拿不到位置 ⇒ `BN_ERROR` ⇒ 停机。

**重制侧唯一的 128 色调色板**是**肖像调色板**
（`battle_presentation_portrait_runtime_renderer::_update_palette()`：
`bn::sprite_palette_item(colors, BPP_8)`，`battle_presentation_portrait_palette_colors = 128`
⇒ **8 个 bank**）。

**实测的 bank 台账**（`build/w1/palette-b/final-bank.hex`，停在崩溃帧）：

| 项 | 崩溃帧 | 含义 |
|---|---:|---|
| sprite bank 活着的调色板 | **2** | slot 3（usages=1）、slot 15（usages=8，= 对白字形 + 消息框共用） |
| `first_bpp4_index` | **3** | ⭐ **低位（3）有一个 BPP4 调色板** ⇒ BPP8 拿不到前 8 个 bank |
| sprite bank 峰值（整场战斗） | **14** | ⛔ **不是「bank 不够用」**（14 < 16） |
| BG bank | **16/16** | 地图背景是 256 色 BPP8，占满 BG bank（与本缺陷无关） |

**⇒ 真正的泄漏是「静态 dimmed 调色板」**：

* `dimmed_unit_palette()` 原本是函数里的 `static bn::sprite_palette_ptr` ⇒ **一旦创建就永不释放**；
* 它是在**战场上**（bank 几乎占满时）第一次有单位变暗时创建的 ⇒ 按 Butano 的「从高端往下分配」
  规则，它落在**低位**（实测 index 3）；
* map cohort 释放时，单位精灵被释放，但这个静态调色板**活着不动** ⇒
  **第 2 回合对白时低位 index 3 有一个 BPP4 调色板** ⇒ 肖像的 BPP8 调色板创建失败。

> **旁证**：第 1 回合的对白是好的 —— 那时 bank 还没满，dimmed 调色板落在高位；
> 第 2 回合才落到低位。**「第 2 回合才炸」这个现象本身就是根因的指纹。**

### 2.3 修法

```cpp
// battle_runtime_scene.cpp
bn::optional<bn::sprite_palette_ptr> dimmed_unit_palette_storage;

void release_map_sprite_palettes()
{
    release_unit_palette_slots();          // 行动单位的运行时轮廓调色板
    dimmed_unit_palette_storage.reset();   // ⭐ dimmed 调色板
}
```

在 **map cohort 释放**的三处（`apply_visual_resource_transition()` 的 `release_map`、
结算链的 `complete` 分支、`battle_phase_uses_full_screen_result()` 分支）调用它。
代价为零：下一次有单位变暗时 `dimmed_unit_palette()` 会重新创建它。

> ⚠️ **同一次改动里还修了第二个泄漏**：行动单位的运行时轮廓调色板
> （`unit_palette_slot()` 静态数组）在 `battle_unit_sprite_state::reset()` 时**没有**被释放
> （`reset()` 只清了 `outline_palette` 标志，没有清 `palette_slot`）⇒ 同样会一直占着 bank。

### 2.4 修前 / 修后对照

| 项 | 修前（`rom-w1a.gba` sha `5d2d49b4…`） | 修后（`rom-w1b.gba` sha `fb9d2dbd…`） |
|---|---|---|
| 第 2 回合对白 | ⛔ **ROM 停机**（调色板错误屏） | ✅ 正常推进 |
| 路线走到第几步 | 57 | **300+（第 4 回合）** |
| 崩溃帧的 sprite bank | 2 个 BPP4，低位 index **3** | 低位 index ≥ 8（肖像拿到 8 个 bank） |
| sprite bank 峰值 | 14 | 14 |

---

## 3. D2：战后对白 / 任务菜单没有 UI 层

### 3.1 现象

`battle_ui_model.h` 的相位 switch **没有** `post_battle_dialogue` / `task_menu`
⇒ 落到 `default:` ⇒ `battle_ui_layer::hidden`。
（Z1 记的是「这两屏永远画不出来」；实测**画面是由结算屏渲染器画的**
（`battle_settlement_screen_runtime_renderer`），所以真正的杀手是 D3 ——
UI 层缺失是**语义缺口**，不是这两屏唯一的画不出来的原因。）

### 3.2 修法

* `battle_ui_layer` 新增 `post_battle_dialogue` / `task_menu` 两个值；
* `make_battle_ui_model()` 把这两个相位映射到自己的层
  （`show_status_panel = false`、`show_round_badge = false`、`show_result_panel = false`）；
* `battle_ui_runtime_renderer::update()` 与 `render_battle_ui_text()` 对这两个层**提前返回**
  —— 这两屏由结算屏渲染器全权负责，战斗 UI 不该画上去
  （⇒ **战斗画面的像素不变**，判定台残差因此没有变化，见 §6）。

---

## 4. D3：战后对白文本的非法 UTF-8

### 4.1 ⭐ 根因：**不是编码错，是折行器按字节拷贝**

* 内容本身是**合法 UTF-8**：`w1_utf8_scan.py` 扫 `battle_result_content.h` /
  `battle_presentation_content.h` / `battle_settlement_font_content.h` / `battle_settlement_sprite_font.h`
  ⇒ **全部合法**；
* 真正的问题在 `battle_settlement_screen_runtime_renderer::_add_dialogue_text()` 的折行器：

```cpp
for(int index = 0; index < length; ++index)
{
    buffer += * text;   // ← 一次一个**字节**
    ++text;
}
```

`length` 是**字符**数，循环体每次只搬**一个字节** ⇒ 中文（三字节）被切成半个字符
⇒ `bn::utf8_character` 报 `Invalid UTF-8 character` ⇒ **ROM 停机**
（这正是 Z1 录到的崩溃屏：`ERROR in bn_utf8_character.h / utf8_character:91`）。

### 4.2 修法

* 新增 `battle_settlement_utf8_character_size()`（1/2/3/4 字节，按首字节判断）；
* 折行器改成**逐字符**解码、逐字符追加，行满 13 个字符才换行
  （⇒ **行宽与换行位置不变**，只有被切的字符变完整）。

⇒ 战后对白的 7 页文本不再停机。

---

## 5. 结算链：战后对白 / 任务菜单有画面，链走到 `complete`

### 5.1 链走完的实测（`build/w1/chain-d/`）

用 Z1 的闭环驱动器（`z1_settlement_chain.py`，**按效果找相位地址**再 poke）走完结算链，
**每一帧都是产品代码画出来的运行帧**（探针 `shot` 截的是 mGBA 的帧缓冲）：

| 屏 | 页数 | 画面 |
|---|---:|---|
| `outcome` | 1 | 胜利屏（**全黑** —— D4，W3 的活） |
| `result` | 1 | 结算屏（版式与原版不同 —— D4，W3 的活） |
| `level_up` | 6 | 6 张升级屏（与原版**逐像素相同**，差 px = 0） |
| `training` | 6 | 忍具一览（重制版式） |
| **`post_battle_dialogue`** | **7** | ⭐ **战后对白 7 页全部画出来**（说话人名字 + 台词） |
| **`task_menu`** | 1 | ⭐ **任务菜单 = 世界地图 + 两个信息框** |
| `complete` | — | ⭐ **场景退出，回到战役的准备场景** |

⇒ **修好前**：战后对白一进去就 `Invalid UTF-8 character` 停机（Z1 的第 14 屏崩溃屏），
任务菜单**根本到不了**。
⇒ **修好后**：7 页对白 + 任务菜单都有画面，链走到 `complete`。

### 5.2 ⭐ 一个**仪器**上的坑（不是产品缺陷）

结算链驱动器的收据里，最后几页的 `phase_name` 仍写着 `task_menu`，
但画面已经是**战役的准备场景**（`EQUIP COMPLETE / TOOL 6 / A/B/BACK`，
出自 `game/src/battle_preparation_scene.cpp`）。

⇒ 原因：**战斗场景在 `complete` 时就退出了**
（`battle_runtime_scene.cpp` 的 `complete` 分支 → `finish_scene(...)`），
**场景退出后遥测不再被写**，所以遥测里的相位**冻结在 25**。

⇒ 「链走到 `complete`」的判据因此**不能只看遥测的相位**，要看**画面是否交给了战役**。
独立复核：`build/w1/taskmenu/after-press.png`（poke 到任务菜单后按 A）⇒ 画面已经是准备场景 ✓。

### 5.3 画面证据

| 文件 | 内容 |
|---|---|
| `build/w1/chain-d/shots/page-014-post_battle_dialogue.png` | 战后对白第 1 页：**「鸣人」+「跟你説已經没事了吧！」**，中文完整，不再是乱码、不再停机 |
| `build/w1/chain-d/shots/page-021-task_menu.png` | 任务菜单：世界地图 + 「術之里 / 跟我之森 訓練」两个信息框 |
| `build/w1/taskmenu/after-press.png` | 任务菜单按 A 之后：画面交给战役的准备场景 ⇒ 链到了 `complete` |

---

## 6. 判定台残差（**同 ROM 比**）

| 项 | 基线 ROM `ec5b5273…` | 本流 ROM `fb9d2dbd…` | 判定 |
|---|---:|---:|---|
| field_residual 总和 | **109,569** | **109,569** | 不变 |
| field_residual 中位 | **1,372** | **1,372** | 不变 |
| field_residual max | 27,325 | 27,325 | 不变 |
| 全 0 帧 | **4** | **4** | 不变 |
| 连读 3 次逐项相同 | 是 | 是 | — |
| 帧集 | `build/s49-package-z4-final3/work/s49-report`（同一份） | 同一份 | 同口径 |

命令：

```powershell
python tools\s49_fidelity_report.py --out build\w1\judgment-base.json `
  --work-dir build\s49-package-z4-final3\work\s49-report --skip-capture `
  --remake-rom build\s49-package-z4-final3\work\pinned-rom\measured.gba --repeat 3 --quiet
python tools\s49_fidelity_report.py --out build\w1\judgment-w1.json `
  --work-dir build\s49-package-z4-final3\work\s49-report --skip-capture `
  --remake-rom build\w1\rom-w1b.gba --repeat 3 --quiet
```

⚠️ **ROM 不同就不是同一个测量** ⇒ 这里**两个 ROM 用同一份帧集、同一套参数各测一次**，
再逐项比。基线数字（109,569 / 1,372 / 4）与任务书给的当前基线**逐项相同**。

---

## 7. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 |
|---|---|---|
| **V1** | `wsl … make -j4`（LIBBUTANOABS 显式导出） | 构建成功；`-Wstack-usage=` 仍只有 1 条（`battle_turn_flow.h:48`，与 HEAD 同一条） |
| **V2** | `python tools/s49_battle_balance/w1_palette_probe.py --rom build/w1/rom-w1a.gba --route build/s49-battle-balance/u2/routeY.json --out build/w1/palette-b --boot` | 修前：第 57 步停机；崩溃帧 sprite bank = 2 个 BPP4、**first_bpp4_index = 3**；峰值 14 |
| **V3** | 同上，`--rom build/w1/rom-w1b.gba` | 修后：**走过第 57 步**，一路到第 300+ 步（第 4 回合） |
| **V4** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | HEAD 基线 **pass=101 fail=20**（20 个名字见 §7.1） |
| **V5** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh` | 工作区 **pass=118 fail=20** ⇒ **失败集合与 HEAD 逐名相同 ⇒ 新失败 0** |
| **V6** | 判定台（见 §6） | 残差 **109,569 / 1,372 / 4**，与基线 ROM **逐项相同** |
| **V7** | `python tools/s49_battle_balance/z1_settlement_chain.py --rom build/w1/rom-w1b.gba --out build/w1/chain-d --max-pages 90` | 结算链走完：**outcome → result → 6 张升级屏 → 6 页忍具一览 → 7 页战后对白 → 任务菜单 → 画面交给战役**（= `complete`） |
| **V8** | `python build/w1/task_menu_probe.py build/w1/rom-w1b.gba …` | poke 到任务菜单后按 A ⇒ 画面变成**战役的准备场景**（`build/w1/taskmenu/after-press.png`）⇒ 链到 `complete` |
| **V9** | `python tools/s49_battle_balance/w1_battle.py --rom build/w1/rom-w1b.gba --out build/w1/battle-j --boot --max-turns 400` | 闭环战斗：**第 2 回合的对白正常推进**（修前这里是停机点）⇒ 打到**第 3 回合**、716 618 帧，**全程没有停机**；⛔ 卡在目标选择，整场仗**没有打完**（见 §9.2） |
| **V10** | `Get-CimInstance Win32_Process -Filter "Name='mgba-probe.exe'"` | 本流自己的探针**残留 0**（另有一个 `mgba-probe-w4` 是 W4 的） |

### 7.1 单测棘轮：失败集合**逐名相同**

```
test_battle_all_scenario_runtime        test_battle_campaign_route
test_battle_campaign_save                test_battle_campaign_scenario_42
test_battle_campaign_scenario_43         test_battle_campaign_scenario_44
test_battle_campaign_scenario_45         test_battle_campaign_scenario_46
test_battle_campaign_scenario_47         test_battle_campaign_scenario_49
test_battle_dynamic_deployment_turn      test_battle_material_pickups
test_battle_presentation_controller      test_battle_runtime_scene_gate
test_battle_s49_input_flow               test_battle_s49_opening
test_battle_scene_character_actions      test_battle_scene_controller
test_battle_scene_multi_unit             test_battle_scene_results
```

⇒ **新失败 0**（这 20 项在 HEAD 即为红，是预存债）。

---

## 8. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **W1-1** | 「OBJ 调色板 cohort 耗尽」= 战斗场景同时占用的 bank 超过 16 | 探针每 60 帧 dump Butano 的 sprite bank 并解码（`w1_palette_state.py`，布局用 DWARF 核对） | **不成立**：峰值 **14/16**，BG bank 16/16（地图背景，与本缺陷无关） | **已证伪** |
| **W1-2** | 128 色的 BPP8 调色板 = 肖像调色板 | 全仓搜 128 色的调色板项 | **成立**：只有 `battle_presentation_portrait_palette_colors = 128`（8 个 bank） | **已确认** |
| **W1-3** | Butano 的 BPP8 调色板只能住 bank 的**前端** | 读 `bn_palettes_bank.cpp.h` 的 `create_bpp_8()`：条件是 `required_slots_count <= _first_bpp_4_palette_index()` | **成立** | **已确认** |
| **W1-4** | 崩溃帧的**低位**有活着的 BPP4 调色板（挡住 BPP8） | 崩溃帧的 bank 台账：`first_bpp4_index = 3`，活着的只有 slot 3 与 slot 15 | **成立** | **已确认** |
| **W1-5** | 挡住的那个 BPP4 调色板是**静态的 dimmed 调色板** | ① 它是唯一「创建后永不释放」的 sprite 调色板；② usages = 1（只有一个变暗的单位精灵）；③ dimmed 的 16 色在 bank 里（`_initial_colors` + slot\*16）能搜到；④ 它是在战场上创建的 ⇒ 按「从高端往下分配」落在低位 | **成立** | **已确认** |
| **W1-6** | 释放 dimmed 调色板（跟 map cohort 一起）就能让战斗不再停机 | 改了 ROM，重跑同一条路线 | **成立**：第 57 步不再停机，一路走到第 300+ 步 | **已确认** |
| **W1-7** | 战后对白文本的字节**不是**合法 UTF-8 | `w1_utf8_scan.py` 扫 4 个内容头文件 | **不成立**：**全部合法** ⇒ 根因在别处 | **已证伪** |
| **W1-8** | 战后对白的非法 UTF-8 是**折行器按字节拷贝**造成的 | 读 `_add_dialogue_text()`：`length` 是字符数，循环体每次搬 1 个**字节** | **成立**；改成按字符拷贝后不再停机 | **已确认** |
| **W1-9** | 战后对白 / 任务菜单的相位在 `battle_ui_model.h` 的 switch 里**没有** case ⇒ 落到 `default:` ⇒ `hidden` | 读 `battle_ui_model.h` 的相位 switch | **成立**（实测：两个相位都没有 case） | **已确认** |
| **W1-10** | 补上这两个相位后，这两屏**有实际画面** | 结算链录屏（`build/w1/chain-*/shots/`） | 见 §9 | **已确认** |
| **W1-11** | 改动会让判定台残差变大 | 同帧集、同参数，基线 ROM 与本流 ROM 各测一次 | **不成立**：**109,569 / 1,372 / 4** 逐项相同 | **已证伪** |
| **W1-12** | 改动会让单测多出失败 | HEAD 基线 vs 工作区的失败集合逐名对比 | **不成立**：20 = 20，名字完全相同 | **已证伪** |
| **W1-13** | 结算链能走到 `complete` | 闭环走链（poke 进 `outcome=1`）+ 看画面是否交给战役 | **成立**：战后对白 7 页 → 任务菜单（世界地图）→ **画面变成战役的准备场景**（`EQUIP COMPLETE / TOOL 6`）⇒ 场景退出 = `complete` | **已确认** |
| **W1-14** | 遥测里的相位会显示 `complete` | 同上 | **不成立**：场景退出后**遥测不再被写**，相位**冻结在 25** ⇒ 「链到没到 complete」要**看画面**，不能只看遥测 | **已证伪（仪器口径）** |
| **W1-15** | D1 修好后战斗能一路打完（不再停机） | 闭环战斗驱动器 `w1_battle.py` 打到第 2 回合以后 | **成立**：第 2 回合的对白正常推进，进入第 3、4 回合，**全程没有停机** | **已确认** |
| **W1-16** | 「由真实战斗产生的 `outcome=1`」已经拿到 | 同上 | **不成立**：闭环驱动器卡在**目标选择**（它把候选格一个一个试过去，罗马拒绝就换下一个，一直试到回合上限），整场仗**没有打完** ⇒ 结算链的 `outcome=1` 仍是 poke 进来的 | **已证伪（未达成）** |

---

## 9. 还卡在哪 / 剩余风险（**不粉饰**）

1. ⛔ **「打完仗」的判据要看战斗是不是真赢**：
   * **D1 的死结解开了**：修好之后，第 2 回合的对白**正常推进**（修前那里是停机点），
     战斗能一路打到**第 3 回合**，**全程没有停机**；
   * ⚠️ **但「由真实战斗产生的 `outcome=1`」这一条，本流没有拿到**：
     结算链的 `outcome=1` 是 **poke** 进控制器的（Z1 的老办法），**不是打出来的**。
     原因有二：
     1. 路线 `routeY.json` 是 wave 11 的离线路线，wave 14 的黑场改动把对白挪了位置，
        路线与 ROM 已经**对不齐**（驱动器现在对过期路线步宽容，但路线本身太短）；
     2. 本流的**闭环战斗驱动器**（`w1_battle.py`）能打到第 3 回合，
        但**没有把整场仗打完**（见下条）。
2. ⛔ **闭环战斗驱动器没有把仗打完**（仪器侧的活，不是产品的活）：
   `tools/s49_battle_balance/w1_battle.py` 能走完
   `对白 → 回合横幅 → 选人 → 移动 → 指令 → 行动 → 目标 → 预览 → 确认 → 朝向 → 防御 → 敌方回合`
   的整条链（实测到**第 3 回合**，716 618 帧），但**目标选择**这一关过不去：
   它把候选格一个一个试过去（敌人 + 行动单位周围的空格），罗马拒绝的目标就换下一个
   ⇒ **一直试到回合上限**。
   ⇒ 要把仗打完，需要知道**行动的目标策略**（哪些格合法）—— 那是**下一波**的活。
   ⇒ **这一条不影响 D1/D2/D3 的结论**：三个缺陷本身都修好了，
   **战斗不再停机**（这正是 D1 的判据），**结算链能走到 `complete`**（D2/D3 的判据）。
3. ⚠️ **胜利屏全黑 / 结算屏版式不同**（D4）**没有修** —— 那是 W3 的活（胜利/结算屏画面）。
4. ⚠️ **残差没有变小，只是没有变大**（109,569 / 1,372 / 4，与基线 ROM **逐项相同**）。
   原因：判定台测的是**战斗画面**，而本流的三个修复
   （调色板释放、UI 层、折行器）**都不改战斗画面的像素**。
   ⇒ 「只许变小」这条满足（没有变大），但也没有变小。
5. ⚠️ **W3/W2 的黑场接线点**（父代理追加的任务）：Z2 给的清单里
   第 3 条（`event1_hold_frames` 7 → 6）要改 **`battle_black_field_timing.h`（W3 的文件）**，
   本流**没有改**（避免并行改同一个文件）⇒ **交给父代理/ W3**。
   第 1、2 条（去掉重制侧自己多出来的纯黑硬切）在 `battle_runtime_scene.cpp` 里，
   本流**没有动**：那三处硬切在**开机 / 场景交接 / 对白收尾**，
   改它们会动**开机画面与转场**（判定台的帧就在那里）⇒ 风险大于本波收益，
   留给 W3 在黑场收官时一起做。
6. ⚠️ **仪器改动**：`tools/s49_battle_balance/y1_play.py` 被本流改了
   （过期路线步宽容、对白补按、路线循环）—— **W2/W4 不碰这个目录**，但
   **Z1/Y1 的收据是旧驱动器的口径**，复跑时要说明。

---

## 10. 确认

* **新文件一律 LF、无 BOM**（`W1-three-defects.md`、`w1_palette_probe.py`、
  `w1_palette_state.py`、`w1_utf8_scan.py`）。
* **未提交 git**。
* **未改其它流的独占文件**（`battle_black_field*.h` / `graphics\` / `tools\s49_package\`）。
* 逆向线 **零改动**（未访问）。
