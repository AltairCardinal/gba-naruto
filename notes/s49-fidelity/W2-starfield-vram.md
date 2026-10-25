# W2 —— 星光圈 VRAM 硬约束求解

> 2026-10-24 · wave 8 · 流 W2 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/Z2-title-art-starfield.md`（几何 + 素材 + 已证伪路线）、
> `notes/s49-fidelity/WAVE8-TASKS.md` §0.3 / §2
> 工具（新）：`tools/s49_starfield/analyze_vram_options.py`、
> `tools/s49_starfield/measure_scene_vram.py`、
> `tools/s49_starfield/make_star_mask_dedup_assets.py`、
> `tools/s49_starfield/verify_shipped_art.py`
> ⛔ **未改** `game/src/battle_runtime_scene.cpp` / `battle_scene_controller.h` /
> `battle_black_field.h` / `battle_black_field_timing.h` / `battle_opening_title.h`
> （W1 独占）；逆向线全程只读；**未提交 git**

---

## 0. 一句话结论

> **约束解开了，而且没有牺牲一个像素**：把遮罩从「40 块 32×32 网格」
> 改成「**32×32 均匀块共享 1 套图块 + 16×16 边界单元各持 1 套图块**」，
> 一帧的 OBJ 图块从 **640 → 168**、精灵从 40 → **≤84**、
> **换级峰值 308 块**（实测预算：战斗画面 **404 块空闲**、**86 个空 OAM 槽**）
> ⇒ **第二个黑场装得下**，且遮罩**逐像素等于原版**（25 级全部 0 像素差）。
> 接口：`konoha/battle_black_field_star_mask.h`（可直接 include），
> 接线点清单见 §6。

---

## 1. 预算：先把「有多少」量出来（实测，不是估算）

Z2 报的「战斗画面最紧 336 块空闲」来自**旧构建 + 稀疏采样**。
本流重新量了一遍（`tools/s49_starfield/measure_scene_vram.py`）：

| 量 | 实测 | 口径 |
|---|---:|---|
| **OBJ 图块空闲（全程最紧）** | **404** | Butano 分配器自己的 `free_tiles_count`（不是区域高水位） |
| OBJ 图块空闲（黑场淡出/淡入期间） | **422** | 同上，帧 2070…2102 |
| **场景占用的 OAM 精灵** | **42** | OAM 128 槽逐帧统计 |
| **空 OAM 槽** | **86** | 128 − 42 |
| 黑场淡出/淡入的帧区间 | 2070…2081 / 2082…2093 / 2094…2102 | 背景调色板逐帧求和（黑场就是一次调色板淡出） |

采样：2496 帧，每帧一次 `framedump`（调色板 0x200 B + 分配器计数器 2 B + OAM 0x400 B）。

> ⚠️ **修正上游的一个探测口径错误**：OAM **不在** `0x06000000`，
> 那儿是背景字符区；**OAM 在 `0x07000000`**。
> Z2 的 `probe_original_mask.py` 用 `OAM = 0x06000000`，
> 读到的其实是 VRAM（本流实测：2496 帧的" OAM "dump **逐字节相同**），
> 所以「原版有 80 个 disabled 的 8×8 精灵」这条结论**不成立**，本流不引用它。

⇒ **预算 = 404 块 OBJ 图块 + 86 个 OAM 槽**（第二个黑场发生处仍有 422 块 / 86 槽）。

---

## 2. 方案评估（每个方案都有实测数字）

判定口径：
* **tiles** = 一帧同时在 VRAM 里的 OBJ 图块数；
* **sprites** = 一帧同时占用的 OAM 槽数（上限 128）；
* **transPeak** = **换一级时**同时在 VRAM 里的图块数
  （Butano 的 `release()` 只把图块集标成 TO_REMOVE，**要下一次 `core::update()` 才真正归还**，
  所以换级那一瞬必须同时装下旧级和新级的图块集 —— 这是本流最关键的一条约束）。

| 方案 | tiles | sprites | transPeak | ≤404 块 | ≤86 槽 | 判定 |
|---|---:|---:|---:|---|---|---|
| `grid32`（Z2 的 40 块 32×32，不去重） | **640** | 40 | — | ✘ | ✔ | **装不下** |
| `grid32` + 去重 | 304 | 40 | **528** | ✔ | ✔ | ✘ **换级峰值超** |
| `grid16`（15×10 个 16×16，去重） | 152 | **150** | 292 | ✔ | ✘ | ✘ 精灵超 |
| `grid8`（30×20 个 8×8，去重） | 67 | **600** | 120 | ✔ | ✘ | ✘ 精灵超 |
| `hybrid8`（均匀块 32×32 + 边界 8×8） | 83 | **228** | 136 | ✔ | ✘ | ✘ 精灵超 |
| **`hybrid16`（均匀块 32×32 + 边界 16×16）** | **168** | **84** | **308** | ✔ | ✔ | **✅ 可行** |
| `hybrid16` + 32×32 回退（换级峰值换精灵数） | 248 | 51 | 452 | ✔ | ✔ | ✘ 峰值超 |
| `hierarchy`（32→16→8 全切） | 87 | **230** | 140 | ✔ | ✘ | ✘ 精灵超 |
| `bg_mask`（BG 遮罩，见 §7） | 67 | 0 | 120 | ✔ | ✔ | 可行但接线代价高 |

数据来源：`build/s49-starfield/vram-options.json`
（工具 `tools/s49_starfield/analyze_vram_options.py`，逐帧重建原版遮罩后精确计算）。

### 2.1 ⭐ 为什么 `hybrid16` 是唯一解

1. **图块数由「遮住的面积」决定 ⇒ 必然下界 ~600 块/帧**：
   OBJ 的图块是 8×8，一帧遮罩要盖 ~30000…38000 px ⇒ ~470…600 块。
   ⇒ **纯 OBJ 路线里唯一能省的就是「共享图块」**。
2. **能共享的只有「整块相同」**：GBA 要求一个精灵的 16 块（32×32）**在 VRAM 里连续**，
   所以只有**整个块像素相同**才能共用一套图块。
   - 均匀黑块 ⇒ 全屏共用 **1 套**（16 块）⇒ 代价与个数无关；
   - 边界块 ⇒ 每块各不相同 ⇒ 一套 16 块。
3. **边界越细，精灵越多**：8×8 切分 ⇒ 边界单元 ~85 个 ⇒ 全场 **228 个精灵**（超 OAM 的 128）；
   16×16 切分 ⇒ 边界单元 ~55 个 ⇒ **84 个精灵**（86 个空槽，刚好）。
4. **换级峰值**：星光圈每级旋转 ~16.9°，所以 32×32 的边界块**逐级全换**（并集 528 块 ⇒ 超）；
   16×16 的单元**逐级大量复用**（并集 308 块 ⇒ 可）。

⇒ **结论：均匀黑用 32×32 共享，边界用 16×16 独立。**

---

## 3. 推荐方案（`hybrid16`）详解

### 3.1 切分规则

```
屏幕 240×160
├─ 32×32 块（8 列 × 5 行 = 40 块）
│   ├─ 全黑（星光圈边界不经过）  → 1 个 32×32 精灵，**全屏共用 1 套图块（16 块）**
│   └─ 被边界穿过              → 切成 4 个 16×16 单元
│        ├─ 全黑                → 1 个 16×16 精灵，**全屏共用 1 套图块（4 块）**
│        ├─ 全透明（洞里）      → 不画
│        └─ 半黑半透明          → 1 个 16×16 精灵，**自己一套图块（4 块）**，
│                                  单元里的像素**逐像素照抄原版**
```

**每个单元都用它自己的像素画出来 ⇒ 遮罩逐像素等于原版**（不是近似）。

### 3.2 实测数字（逐级，来自生成的表 `build/s49-starfield/star-mask-dedup.json`）

| 级 | 可见 px（原版） | 32×32 块 | 16×16 单元 | 精灵 | **在 VRAM 的图块** | 图块集数 |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 7925 | 23 | 55 | 78 | **168** | 39 |
| 1 | 6561 | 24 | 54 | 78 | 160 | 37 |
| 2 | 4677 | 28 | 43 | 71 | 144 | 33 |
| … | | | | | | |
| 11 | 17 | 39 | 4 | 43 | 28 | 4 |
| 12 | 0（全黑） | 40 | 0 | 40 | 16 | 1 |
| 24 | 7200 | 23 | 61 | **84** | **168** | 39 |

* **每帧图块 ≤ 168**（预算 404 ⇒ 余 236）
* **每帧精灵 ≤ 84**（空槽 86 ⇒ 余 2，⚠️ 见 §8 风险 1）
* **换级峰值 308 块**（预算 404 ⇒ 余 96）

### 3.3 与 Z2 的素材对比

| | Z2 的 `battle_black_field_star_mask` | 本流 |
|---|---:|---:|
| 每帧 OBJ 图块 | 640 | **168** |
| 每帧精灵 | 40 | ≤84 |
| 换级峰值 | （Z2 未测） | **308** |
| ROM 图块 | 16 000（512 KB） | **1 632（52 KB）**：16×16 item 1 504 块（371 个单元 + 5 个补齐帧）+ 32×32 item 128 块 |
| 遮罩像素 | 与原版逐像素相同 | **与原版逐像素相同** |

---

## 4. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `game/include/konoha/battle_black_field_star.h` | **改** | 几何 + 新布局的常量/计数（无引擎依赖，可上主机单测） |
| `game/include/konoha/battle_black_field_star_table.h` | **新（生成）** | 摆放表：每一级画哪些块/单元、在哪、用第几帧 |
| `game/include/konoha/battle_black_field_star_mask.h` | **新** | ⭐ **可直接 include 的接口**（`battle_black_field_star_mask` 类） |
| `graphics/battle_black_field_star_mask16.{bmp,json}` | **新** | 371 个不同的 16×16 单元（4bpp，16×16 sprite item） |
| `graphics/battle_black_field_star_block32.{bmp,json}` | **新** | 1 个全黑 32×32 块（4bpp，32×32 sprite item） |
| `tools/s49_starfield/analyze_vram_options.py` | **新** | 7 种布局的图块/精灵/换级峰值实测对比 |
| `tools/s49_starfield/measure_scene_vram.py` | **新** | 逐帧测 OBJ 空闲图块 / OAM 精灵数 / 黑场区间 |
| `tools/s49_starfield/make_star_mask_dedup_assets.py` | **新** | 生成去重素材 + 摆放表 + 双重回读校验 |
| `tools/s49_starfield/verify_shipped_art.py` | **新** | 把 GRIT 产出的图块数据从构建产物里读回来逐帧对拍 |
| `notes/s49-fidelity/W2-starfield-vram.md` | **新** | 本报告 |

> ⚠️ **老的 `battle_black_field_star_mask.bmp`（512 KB）保留未动**：
> 它是 Z2 的「未链接」素材，新的方案用的是**两个新 item**，
> 这样 W1 若已经按 Z2 的清单写了 include，也不会被本流打断。
> 老 item 不被 include ⇒ 不进 ROM ⇒ 不占 VRAM。

---

## 5. 接口（交 W1 接线）

```cpp
#include "konoha/battle_black_field_star_mask.h"

konoha::battle_black_field_star_mask star_mask;   // 场景成员

// 每次黑场换一级时：
star_mask.set_level(battle_black_field_timing::star_mask_level());
// 黑场结束时：
star_mask.clear();
```

* `set_level(level)`：`level` ∈ [0,24]；**负数或越界 = 隐藏**。
* 内部：`clear()` 先销毁旧精灵（Butano 立刻归还 OAM 槽），
  再按摆放表建新精灵并 `set_tiles(create_tiles(art))`
  （**同一 art 的多个精灵共用同一套图块** —— Butano 的分配器按图块数据指针查表）。
* 精灵参数：`bg_priority = 0`（压在场景精灵之上）、`z_order = 1000`（场景自己最高用到 20）。
* 精灵**以中心定位**：32×32 块中心 = `(x+16, y+16)`，16×16 单元中心 = `(x+8, y+8)`。

---

## 6. 接线点清单（给 W1）

1. **include**：`#include "konoha/battle_black_field_star_mask.h"`
   （它自己会 include 两个 sprite item 头，**不需要**再单独 include）。
2. **加成员**：在战斗场景里加 `konoha::battle_black_field_star_mask star_mask;`。
3. **换级**：黑场每推进一级（`battle_black_field_timing::star_mask_level()` 变化时）
   调 `star_mask.set_level(level)`。
   ⚠️ **必须在场景精灵画完之后调**，否则遮罩会被场景精灵压住。
4. **收尾**：黑场结束（`star_mask_level()` 变回 −1）时调 `star_mask.clear()`。
5. **与调色板淡出的关系**：原版的黑场是「洞」而不是「变暗」，
   所以**星光圈开着的时候不要再叠调色板淡出**（否则洞里也会变暗），
   二选一：要么星光圈，要么 `battle_black_field` 的 alpha 淡出。
   本流**没有**动 `battle_black_field.h`（W1 独占），这条由 W1 决断。
6. **ROM 里必须能看到素材**：素材是「已转换、**未链接**」——
   只要 include 了 `battle_black_field_star_mask.h` 就会进 ROM；
   用 `arm-none-eabi-nm butano-sequel.elf | grep star_mask16` 自查。
7. ⚠️ **OAM 余量只有 2 个槽**（84 + 42 = 126 / 128）。
   若场景精灵数再涨，可让 W1 在黑场期间**隐藏**几个不入洞的 UI 精灵
   （`set_visible(false)` 不还图块，但还 OAM 槽）。

---

## 7. 替代路线：BG 遮罩（更省，但接线代价高）

如果哪天 OBJ 精灵数不够用，**BG 遮罩**是更宽裕的路线：

| 项 | `hybrid16`（推荐） | BG 遮罩 |
|---|---:|---:|
| OBJ 图块 | 168（峰值 308） | **0** |
| OBJ 精灵 | ≤84 | **0** |
| BG 图块 | 0 | ~67/级（8×8 粒度） |
| 遮罩像素 | 与原版逐像素相同 | 与原版逐像素相同（BG 原生 8×8 粒度） |
| 接线代价 | 低：只要 include + 两次调用 | **高**：需要一个空闲 BG 层、地图 BG 降优先级、场景精灵改 `bg_priority`、**每级重传 BG 图块与 BG 地图** |

* **层级可行性（已推演，未实测）**：GBA 的绘制顺序是
  `OBJ(pri0) > BG3..BG0(pri0) > OBJ(pri1) > …`，
  ⇒ **遮罩 BG 必须比场景精灵的 `bg_priority` 数字大**才能盖住它们；
  场景精灵多数是 `bg_priority 0` ⇒ 遮罩 BG 放 **priority 1**、
  地图 BG 放 **priority 0** 即可（遮罩在地图前面、也在场景精灵前面）。
* **BG 地图必须逐级改**（洞的位置变了）⇒ 每级重传 600 个 map cell + ~67 套图块。
* **BG 路线没有精灵压力**，所以它是「OBJ 精灵不够时」的备选，
  不是现在的首选 —— 现在的首选已经装得下。

---

## 8. 卡在哪 / 剩余风险

1. ⚠️ **OAM 余量只有 2 个槽**（遮罩 84 + 场景 42 = 126 / 128）。
   实测的场景 42 个精灵是**当前构建**的数字；W1 接线时若场景多了 UI 精灵就要先隐藏几个。
2. ⚠️ **素材还没进 ROM**（没人 include 它）⇒ 本流**没有在真机上画过这个遮罩**。
   证据链到「图块数据」为止：位图 → GRIT → 图块数据（逐帧对拍通过，见 §9），
   再往上是 Butano 的标准路径（`create_sprite` → `create_tiles` → 分配器按指针查表共享）。
3. **黑场是「洞」还是「变暗」**：原版是洞；重制侧现在还有调色板淡出那条路。
   两者同时开会让洞里也变暗 ⇒ **必须二选一**（W1 决断，本流未动 `battle_black_field.h`）。
4. **黑场期间洞里的画面**：洞里露的是场景本身（地图 BG + 场景精灵）。
   本流**没有**释放/隐藏任何场景精灵（没必要：遮罩精灵压在上面）。
5. 「只画变化的边缘」「分帧」两条路都被实测否掉了：
   * 「只画边缘」不成立 —— 遮罩要盖的是**洞外**的整块面积，
     洞外的部分每一级都不同（星光圈在转），省不掉；
   * 「分帧」不成立 —— 遮罩在**转**，两帧拼不出一个洞。

---

## 9. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| W2-V1 | `python tools/s49_starfield/analyze_vram_options.py --frames build/s49-blackfade/original-entry-v2/frames --out build/s49-starfield/vram-options.json` | 7 种布局的图块/精灵/峰值 | `hybrid16` **168 块 / 84 精灵 / 峰值 308**；其余布局各有明确的不合格项（表 §2） |
| W2-V2 | `python tools/s49_starfield/measure_scene_vram.py --rom … --out build/s49-starfield/scene-vram.json` | 逐帧量预算 | **404 块空闲（全程最紧）/ 422 块（黑场期间）/ 42 场景精灵 / 86 空 OAM 槽**；黑场帧 2070…2102 |
| W2-V3 | `python tools/s49_starfield/make_star_mask_dedup_assets.py …` | 生成素材 + 表 + 回读校验 | 371 单元 + 1 块；`shipped_bitmap_round_trip_ok = true`（25 级可见像素与原版相等）、`header_round_trip_ok = true`（**从生成的 C++ 表回读**重建遮罩，**0 像素差**） |
| W2-V4 | `python tools/s49_starfield/verify_shipped_art.py --build …/build --graphics …` | GRIT 产出的图块数据逐帧对拍 | `mask16` 376 帧、`block32` 8 帧，**mismatched frames = 0**；metatile 顺序 = **row_major** |
| W2-V5 | WSL `make -j4`（显式 `LIBBUTANOABS`） | 构建通过 | **ROM fixed!**（exit 0）；生成 `bn_sprite_items_battle_black_field_star_mask16.h`（376 帧 / 1504 块 / **2×2 metatile**）与 `_block32.h`（8 帧 / 128 块 / 4×4 metatile） |
| W2-V6 | `arm-none-eabi-g++ -c` 单独编译接口头 | 接口能编过 | **COMPILE_OK**（`build/w2-check/star_mask_compile_test.cpp`） |
| W2-V7 | `bash build/run-baseline-tests.sh` | HEAD 基线 | **pass=101 fail=20**，失败名单见 §9.1（与 Z2 的 20 项**逐名相同**） |
| W2-V8 | `bash build/w1-run-all-tests.sh` | 棘轮 | 见 §9.1 |
| W2-V9 | 孤儿进程检查 | 0 个 | `Win32_Process` → `mgba-probe.exe` **count=0** |
| W2-V10 | 编码自检 | 新文件 LF、无 BOM | 见 §11 |

### 9.1 单测棘轮

**HEAD 基线**（`build/run-baseline-tests.sh`，`git archive HEAD` 快照）：
**pass=101 fail=20**，失败名单：

```
test_battle_all_scenario_runtime      test_battle_campaign_route
test_battle_campaign_save              test_battle_campaign_scenario_42
test_battle_campaign_scenario_43       test_battle_campaign_scenario_44
test_battle_campaign_scenario_45       test_battle_campaign_scenario_46
test_battle_campaign_scenario_47       test_battle_campaign_scenario_49
test_battle_dynamic_deployment_turn    test_battle_material_pickups
test_battle_presentation_controller    test_battle_runtime_scene_gate
test_battle_s49_input_flow             test_battle_s49_opening
test_battle_scene_character_actions    test_battle_scene_controller
test_battle_scene_multi_unit           test_battle_scene_results
```

**工作区**（`build/w1-run-all-tests.sh`）：
**`w1-all-tests: pass=111 fail=20 status=1`**，失败名单与上面 **逐名相同**
（脚本化 diff：`Compare-Object` ⇒ **完全一致，new red = 0**）：

```
FAIL(compile) test_battle_campaign_save          FAIL(compile) test_battle_runtime_scene_gate
FAIL(run) test_battle_all_scenario_runtime        FAIL(run) test_battle_campaign_route
FAIL(run) test_battle_campaign_scenario_42         FAIL(run) test_battle_campaign_scenario_43
FAIL(run) test_battle_campaign_scenario_44         FAIL(run) test_battle_campaign_scenario_45
FAIL(run) test_battle_campaign_scenario_46         FAIL(run) test_battle_campaign_scenario_47
FAIL(run) test_battle_campaign_scenario_49         FAIL(run) test_battle_dynamic_deployment_turn
FAIL(run) test_battle_material_pickups             FAIL(run) test_battle_presentation_controller
FAIL(run) test_battle_s49_input_flow               FAIL(run) test_battle_s49_opening
FAIL(run) test_battle_scene_character_actions      FAIL(run) test_battle_scene_controller
FAIL(run) test_battle_scene_multi_unit             FAIL(run) test_battle_scene_results
```

⇒ **棘轮是绿的（new red = 0）**：本流没有新增测试文件，也没有改动任何既有测试的断言，
只改了一个头文件（`battle_black_field_star.h`）的内容。

---

## 10. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W2-1 | VRAM 空闲 = 区域高水位 | 探针量区域 | ⛔ 高水位 1023/1024 但只用 ~620 ⇒ 必须读分配器计数器 | **已证伪（沿用 Z2，W2-V2 复核）** |
| W2-2 | 1bpp 素材能省图块 | 读 Butano 源码 | ⛔ `bn::tile` 恒为 32 B（4bpp），`sprite_tiles_manager` 按**图块个数**分配 ⇒ 1bpp 不省 | **已证伪** |
| W2-3 | 640 块装不下 | 分配器计数器 | ⛔ 空闲 404 < 640 ⇒ Z2 的第二个黑场确实装不下 | **已确认** |
| W2-4 | 换级时新旧图块集**不必**同时在 VRAM | 读 Butano 源码 | ⛔ `release()` 只标 TO_REMOVE，**下一次 `core::update()` 才归还** ⇒ 换级那一瞬是**并集** | **已确认**（本流最关键的一条约束） |
| W2-5 | 32×32 网格去重后能装下 | 逐级算并集 | ⚠️ 稳态 304 块 ✔ 但**并集 528 块** > 404 ⇒ 不可用 | **已证伪** |
| W2-6 | 16×16 边界 + 32×32 均匀块可装下 | 逐级算 + 生成后回读 | ✔ **168 块 / 84 精灵 / 并集 308 块**，且 25 级**逐像素**等于原版 | **已确认** |
| W2-7 | 精确的 8×8 洞能用 OBJ 画 | 逐级算 | ⛔ 边界单元太多 ⇒ **228 个精灵** > 128 ⇒ 纯 OBJ 画不出精确的洞 | **已证伪**（⇒ 要更粗的边界或走 BG） |
| W2-8 | 场景最多用多少 OAM 槽 | 逐帧读 OAM | 场景最多 **42** 个精灵 ⇒ **86 个空槽** | **已确认** |
| W2-9 | OAM 在 0x06000000 | 逐帧 dump 比对 | ⛔ OAM 在 **0x07000000**；0x06000000 是背景字符区（2496 帧 dump 逐字节相同） | **已证伪（上游探测口径已修正）** |
| W2-10 | GBA 4bpp 左像素在高半字节 | 逐帧对拍 GRIT 输出 | ⛔ **左像素在低半字节**（位图相反）⇒ 反了就整列错位 | **已证伪（验证工具已修正）** |
| W2-11 | 摆放表可以按「每级紧凑排列」索引 | 生成后从 C++ 表回读重建遮罩 | ⛔ 表是**按级定长**的 ⇒ 必须按 `max_blocks`/`max_cells` **补齐**，否则第 2 级起全错位 | **已证伪（本流发现并修掉的真 bug）** |
| W2-12 | 素材只要转换过就进 ROM | `nm` 查符号 | ⛔ 没 include 就被链接器丢掉（`nm` 查不到 `star_mask16_bn_gfxTiles`） | **已确认**（W1 接线点 6） |
| W2-13 | BG 遮罩更省 | 层级推演 | 数字上更省（0 精灵 / 67 块），但要 BG 层 + 优先级 + 逐级重传 ⇒ 本流不选 | **未验（备选，见 §7）** |
| W2-14 | 洞里可以只画「变化的边缘」 | 几何推演 | ⛔ 要盖的是**洞外**整片面积，而洞每级在转 ⇒ 盖不到 | **已证伪** |
| W2-15 | 遮罩可以分两帧画完 | 几何推演 | ⛔ 两帧之间洞在转 ⇒ 拼不出一个洞；会闪 | **已证伪** |

---

## 11. 复跑命令

```powershell
# 1) 布局对比（7 种方案）
python tools/s49_starfield/analyze_vram_options.py \
    --frames build/s49-blackfade/original-entry-v2/frames \
    --out build/s49-starfield/vram-options.json \
    --markdown build/s49-starfield/vram-options.md

# 2) 逐帧预算（OBJ 空闲图块 / OAM 精灵 / 黑场区间）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-w2'
python tools/mgba_probe/build.py
python tools/s49_starfield/measure_scene_vram.py \
    --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
    --out build/s49-starfield/scene-vram.json

# 3) 生成去重素材 + 摆放表（带回读校验）
python tools/s49_starfield/make_star_mask_dedup_assets.py \
    --frames build/s49-blackfade/original-entry-v2/frames \
    --graphics "D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics" \
    --header "D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_black_field_star_table.h" \
    --out build/s49-starfield/star-mask-dedup.json

# 4) GRIT 产出的图块数据对拍
python tools/s49_starfield/verify_shipped_art.py \
    --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
    --elf "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.elf" \
    --build "D:\Shell\Github\gba-naruto-butano\butano-sequel\build" \
    --graphics "D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics" \
    --out build/s49-starfield/shipped-art-check.json

# 5) 构建（必须显式导出 LIBBUTANOABS）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 6) 单测棘轮
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh
```

---

## 12. 边界声明

* 逆向线 `D:\Shell\Github\gba-naruto-reverse` **全程只读**（本流没有打开它）。
* **未改** `game/src/battle_runtime_scene.cpp`、`battle_scene_controller.h`、
  `battle_black_field.h`、`battle_black_field_timing.h`、`battle_opening_title.h`
  （W1 独占），**一行都没动**。
* 重制线的改动**只有**：
  * `game/include/konoha/battle_black_field_star.h`（**改**：新布局的常量/计数）；
  * `game/include/konoha/battle_black_field_star_table.h`（**新，生成**）；
  * `game/include/konoha/battle_black_field_star_mask.h`（**新**：接口）；
  * `graphics/battle_black_field_star_mask16.{bmp,json}`、
    `graphics/battle_black_field_star_block32.{bmp,json}`（**新**）。
* **未提交 git**；新文件一律 **LF、无 BOM**（见 §13）。
* 本流**没有新增单元测试文件**（新增测试文件是 W3 的独占范围），
  也没有改动任何既有测试的断言 ⇒ 棘轮只可能变绿，不会变红。

---

## 13. 编码自检

新文件与改过的文件全部 **LF、无 BOM**（脚本逐个读字节核对）：

| 文件 | BOM | CRLF |
|---|---|---:|
| `notes/s49-fidelity/W2-starfield-vram.md` | False | 0 |
| `tools/s49_starfield/analyze_vram_options.py` | False | 0 |
| `tools/s49_starfield/measure_scene_vram.py` | False | 0 |
| `tools/s49_starfield/make_star_mask_dedup_assets.py` | False | 0 |
| `tools/s49_starfield/verify_shipped_art.py` | False | 0 |
| `game/include/konoha/battle_black_field_star.h` | False | 0 |
| `game/include/konoha/battle_black_field_star_table.h` | False | 0 |
| `game/include/konoha/battle_black_field_star_mask.h` | False | 0 |
| `graphics/battle_black_field_star_mask16.json` | False | 0 |
| `graphics/battle_black_field_star_block32.json` | False | 0 |

（`.bmp` 是二进制，不适用。）

**孤儿进程**：`Win32_Process` → `mgba-probe.exe` **count = 0** ✔
（探针建在私有目录 `build/mgba-probe-w2/`，没有覆盖共享的 `build/mgba-probe/`）。
