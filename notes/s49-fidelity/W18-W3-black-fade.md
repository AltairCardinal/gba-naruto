# W18-W3 —— 黑场（黑屏淡入淡出）从 6 个收敛到 2 个（wave 18 · 流 W3）

> **本路最终 ROM sha256 = `bf13fa849875af940ff4f97c1a4131d64fed160ea57b8314f54272a4788d7c72`**
> （副本内 `build/w18-w3/butano-sequel/butano-sequel.gba`，12115700 B；
> 基线未改代码时的 ROM = `7c31b4e28052d2130abf2b885ce2b8a6b7ddac93e43204f25a386067fe10797f`）
> ⇒ **本笔记的所有数字只绑定这两个 sha**（本机构建非字节可复现，跨 ROM 不可比）。

> 2026-10-25 · wave 18 · 流 W3（`mvs_c223c7033d55435b8951b53137e222ca`）· 父代理
> `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/WAVE18-TASKS.md` §3 · `notes/s49-fidelity/U1-d4-fix.md` §5.2 ·
> `notes/s49-fidelity/V2-pixel-fixes.md` §2.2/§4 ·
> `notes/s49-fidelity/Z2-blackfield-final.md` §1/§3
> 隔离副本：`D:\Github\gba-naruto\build\w18-w3\butano-sequel`（**只在这里改、只在这里构建**）
> ⛔ **未改** `game/src/battle_runtime_scene.cpp`（W4 独占）、`game/include/konoha/battle_result_content.h`、
> `battle_presentation_content.h`、`battle_ui_model.h`（W4 独占）、
> `game/include/konoha/battle_range_ui_style.h` / `game/tests/test_battle_range_ui_style.cpp`
> （父代理自办回退项，**未触碰**）；⛔ 未访问逆向线；⛔ **未提交 git**。

---

## 0. 一句话结论

> ⭐ **B1（开机 8 帧纯黑）已修：8 帧 → 2 帧，且整条 walk 的帧号一个都没动**（事件 2…6 的帧号与改前
> 逐个相同）。剩下的 2 帧是 **butano 的开机时序**造成的（`bn::core::init()` 的那次 update 把 GBA 的
> 强制空白清掉了，而本路的背景在它之后才建）⇒ 实测过「直接写 DISPCNT 强制空白位」的方案，
> **不成立**（butano 每次 update 都重写 DISPCNT）⇒ 已回退，留在 §6.1。
> ⛔ **B2 / B3 / B4 三个硬切的根因全部定位到 `game/src/battle_runtime_scene.cpp`**
> （分别是 `:8152`、`:5066-5067`、`:6497-6514` + `battle_visual_resource_coordinator.h`）
> ⇒ **按文件归属我不能改**，已写成**可执行的越界请求**（§6）。
> ⚠️ **B2 有硬约束**：GBA 的 BG 图块区只有 64 KB，而准备场景背景是 32 KB（4bpp 256×256）、
> 部署场景地图是 64 KB（8bpp）⇒ **两者无法共存** ⇒ 「释放 + 提交」与「新图提交」**不可能在同一次
> update 里完成** ⇒ 该缝隙**不是纯代码顺序问题**，见 §6.2 的 VRAM 算术。
> ⚠️ 另外两个**真黑场事件**的帧数也对不上原版（事件 3 淡入 28≠24、事件 6 淡出/淡入 28≠24），
> 根因见 §6.4/§6.5。
> ⚠️ 顺带发现：重制侧开机有 **26 帧纯白**（原版只有 2 帧）⇒ 比那 2 帧黑更大的观感差，根因在 butano。

---

## 1. 真值复述

| | 原版 | 重制侧（wave 17 实测） |
|---|---|---|
| 黑场事件数 | **2** | **6** |
| 事件 1 | 24 / 18 / 24（淡出/持黑/淡入） | 24 / 18 / **26** |
| 事件 2 | 24 / 24 / 24 | **28** / 24 / **28** |
| 持黑 18 | — | ✅ **已闭合**（与原版同形） |
| 其余 4 个 | — | ⛔ **纯黑硬切未收**（没有淡出/淡入渐变） |

原版侧真值（只读复用本仓已钉的捕获）：

| 真值 | 来源 | 数字 |
|---|---|---|
| 原版 2 个黑场事件 | `build/s49-blackfade/original-entry-v2/`（`blackfade_report.py`） | 24/18/24（1013–1078）与 24/24/24（1653–1724）；全黑帧 sha `47fbde60…` |
| **原版开机** | `build/s49-z2/original-boot/` | 95 帧；**帧 1–2 白**，**帧 3 起出画面**（mean 48.26→13.95→27.01→40.94→… 逐步变亮），**全程没有一帧纯黑**（blackpct ≤ 4.6 %） |

⇒ **原版的开机是「淡入且从不纯黑」**：强制空白（forced blank）在画面准备好之前一直开着。
重制侧原来是「白 26 帧 → **纯黑 8 帧** → 画面」。

---

## 2. 改动文件清单

全部改动**只在隔离副本** `build/w18-w3/butano-sequel/` 内；共享树
`D:\Shell\Github\gba-naruto-butano\butano-sequel` **一个字节没动**。

| 文件（副本内相对路径） | 改动摘要 | sha256 |
|---|---|---|
| `game/include/konoha/battle_black_field.h` | ①补齐自包含 include（`bn_bg_palettes.h`/`bn_optional.h`/`bn_regular_bg_ptr.h`/`bn_sprite_palettes.h`）——该头之前**依赖调用方的 include 顺序**，被 `battle_preparation_scene.cpp` 直接 include 时编译不过；②新增 `konoha::battle_screen_handover_background`：一个跨场景交接的「背景槽」（`slot()` + `frame_drawn()`），让开机路径先把背景画出来、准备场景再接手同一张背景。**黑场时序本身一字未动**。 | `d1160e2129167813c97888fd930c14e31cb0eb96bbb3146c0d42370b06c9c1f9` |
| `src/main.cpp` | 开机路径：`bn::core::init()` 之后**立刻**创建准备场景的背景并跑一次 `bn::core::update()`，把它放进交接槽 ⇒ **画面在游戏画的第一个帧就在屏上**，开机不再有 8 帧纯黑。 | `7e6af6cac87ccb0b6332f014376765c8420430a01ef5d650fb51e35bd976df9b` |
| `game/src/battle_preparation_scene.cpp` | ①从交接槽**接手**开机画好的背景（不再分配第二张：GBA 的 BG 图块区 64 KB 装不下两张 32 KB 的准备背景），接手后显式 `reset()` 槽位；②若接手的是开机帧，**跳过本场景第一次 `bn::core::update()`**（开机那次 update 就是本场景的第一帧）⇒ **整条 walk 的帧号一个都不移**。 | `f593e3efc89048cf6e267fbe5976329f021a4e019b85fa6cadfce55c94df0c70` |

### 2.1 最终 sha256（收尾时重算）

| 文件 | sha256 |
|---|---|
| `game/include/konoha/battle_black_field.h` | `d1160e2129167813c97888fd930c14e31cb0eb96bbb3146c0d42370b06c9c1f9` |
| `src/main.cpp` | `7e6af6cac87ccb0b6332f014376765c8420430a01ef5d650fb51e35bd976df9b` |
| `game/src/battle_preparation_scene.cpp` | `f593e3efc89048cf6e267fbe5976329f021a4e019b85fa6cadfce55c94df0c70` |
| **ROM（本路最终版）** | **`bf13fa849875af940ff4f97c1a4131d64fed160ea57b8314f54272a4788d7c72`**（12115700 B） |

* 新增文件：**无**。改动文件全部 LF、无 BOM（`crlf=0`）。
* 单元测试文件：**未改**（`game/tests/test_battle_black_field.cpp` 只 include
  `battle_black_field_timing.h`，**不含**我改的 `battle_black_field.h` ⇒ 不受影响）。
* 共享树对应文件的 diff：`battle_black_field.h` +49 行、`src/main.cpp` +26 行、
  `battle_preparation_scene.cpp` +48/−8 行（`git diff --no-index`，无删除性改动）。

---

## 3. 黑场事件清单（改前 / 改后对照）

仪器：`tools/s49_blackfade/blackfade_report.py`（**只读调用**，未改）
捕获：`tools/s49_package/capture_blackfade.py`（**只读调用**，未改）
ROM：见下表。

> ⚠️ **仪器坑**：`tools/s49_blackfade/blackfade_capture.py` **当前是坏的** ——
> 它读 `args.release_frames`，而自己的 parser 从没定义过这个参数 ⇒ 一上来就
> `AttributeError`，什么都没抓到。`tools/s49_package/capture_blackfade.py` 的文件头
> 明确写了「它就是为了替代那个坏工具而存在的」，两者驱动**同一个**
> `tools/s49_blackfade/capture_frames.lua`、**同一套 `MGBA_W3_*` 环境变量契约**、
> **同一份 receipt 形状**。本波全程用后者（**未修改任何工具**）。

| # | 帧号（改前 = 改后，**完全一致**） | 淡出 | 持黑 | 淡入 | 总帧 | 渐变？ | 判定 |
|---|---|---:|---:|---:|---:|---|---|
| **改前** 1 | 27–34 | 0 | **8** | 0 | 8 | ❌ 硬切 | ⛔ 多出来 |
| **改后** 1 | **27–28** | 0 | **2** | 0 | 2 | ❌ 仍硬切 | ⛔ 残留 2 帧（见 §6.1） |
| 2 | 527–532 | 0 | 6 | 0 | 6 | ❌ 硬切 | ⛔ 未动（根因在 W4 文件，§6.2） |
| 3 | 1549–1618 | 24 | 18 | **28** | 70 | ✅ | ⚠️ 淡入 28 ≠ 原版 24（§6.4） |
| 4 | 1659–1660 | 0 | 2 | 0 | 2 | ❌ 硬切 | ⛔ 未动（根因在 W4 文件，§6.3） |
| 5 | 2123–2130 | 0 | 8 | 0 | 8 | ❌ 硬切 | ⛔ 未动（根因在 W4 文件，§6.3） |
| 6 | 2171–2250 | **28** | 24 | **28** | 80 | ✅ | ⚠️ 淡出/淡入 28 ≠ 原版 24（§6.5） |

**关键性质**：改后的事件 **2/3/4/5/6 的帧号与改前逐个相同** ⇒
**B1 的修复没有让整条 walk 移一帧**（这是 `frame_drawn()` + 「跳过本场景第一次 update」的目的）。

### 3.1 改前 / 改后的开机段（逐帧 mean）

| 帧 | 改前 | 改后 |
|---|---|---|
| 1–26 | 255.00（纯白，强制空白） | 255.00（纯白，强制空白） |
| **27** | **0.00（纯黑）** | **0.00（纯黑）** |
| **28** | **0.00（纯黑）** | **0.00（纯黑）** |
| 29 | 0.00（纯黑） | **206.23（准备场景背景，5 色）** |
| 30–34 | 0.00（纯黑） | 206.23 |
| 35 | 182.68（准备场景 + 菜单） | 182.68 |

⇒ 开机纯黑 **8 帧 → 2 帧（−75 %）**；剩下的 2 帧是「强制空白已经关掉、但画面还没提交」的那一帧
（§6.1 给了修法，但修法需要动 butano 或写裸寄存器，**本波没做**）。

---

## 4. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **W3-1** | 开机那 8 帧纯黑 = `bn::core::init()` 之后、准备场景第一次 update 之前**什么都没画** | 逐帧 mean（`build/w18-w3/blackfade-base/blackfade.json`） | ⭐ **成立**：帧 1–26 纯白（GBA 强制空白）、帧 27–34 纯黑、帧 35 才是准备场景（mean 182.68 / 15 色） | **已确认** |
| **W3-2** | ⭐ 把准备场景的背景提前画出来 ⇒ 开机纯黑消失，**且 walk 的帧号不变** | 改 3 个文件 → 重建 → 重录 → 重跑判定台 | ⭐ **成立**：纯黑 8 → 2 帧；事件 2…6 的帧号与改前**逐个相同** | **已确认（已修）** |
| **W3-3** | 事件 2（527–532）的 6 帧纯黑 = 准备场景返回时背景被销毁 + 战斗场景 `:8152` 的 update 把它提交掉 | 读帧上下文（525–526 = mean 206.23 的准备场景、533+ = mean 138.61 的部署画面）+ 读代码 | ⭐ **成立**：`:8152` 的 `bn::core::update()` 是准备场景返回后的**第一次** update ⇒ 它提交了背景的释放 ⇒ 屏上只剩黑色背景板，直到部署场景的 `map`（7804–7811 建、第一次 update 提交） | **已确认** |
| **W3-4** | ⭐ 事件 2 可以靠「准备背景与部署地图在同一次 update 里交接」消掉 | VRAM 算术 | ⛔ **不成立**：GBA 的 BG 图块区只有 **64 KB**；准备背景 = 256×256 4bpp = **32 KB**，部署地图 = 256×256 **8bpp** = **64 KB** ⇒ 32+64 = 96 KB > 64 KB ⇒ **两者无法共存** ⇒ 释放必须先被提交、地图才能分配 ⇒ 「释放的提交」与「地图的提交」**不可能在同一次 update** ⇒ **至少 1 帧黑是结构性的** | **已证伪** |
| **W3-5** | 事件 4（1659–1660）的 2 帧纯黑 = 地图 → 对白背景的 8bpp 交接（释放 + 提交后再分配） | 读 `battle_dialogue_background_runtime_renderer::update()` | ⭐ **成立**：`:5066-5067` 就是 `map.reset(); bn::core::update();` ⇒ 这一 update 提交了地图的释放 ⇒ 屏上只剩背景板（黑），下一帧对白背景才提交 | **已确认** |
| **W3-6** | 事件 5（2123–2130）的 8 帧纯黑 = 对白 → 地图的视觉资源 cohort 切换 | 读 `apply_visual_resource_transition()` + `battle_visual_resource_coordinator.h` | ⭐ **成立**：`transition_to(map)` ⇒ `release_script=true` ⇒ `:6499-6502` 释放对白背景/对话框/立绘 ⇒ `:6513` 的 `bn::core::update()` 提交 ⇒ 地图（64 KB）重新分配 + 上屏要 8 帧 ⇒ 8 帧纯黑 | **已确认** |
| **W3-7** | 事件 3 的淡入 28 帧（原版 24）是因为**生长段**的洞里没有对白背景 | 帧上下文（1619–1658 mean≈130、1659–1660 纯黑、1661 起 mean 134） | ⭐ **成立**：生长段的洞里显示的是**地图**（对白背景此刻还没建），洞很小 ⇒ mean < 40 ⇒ 被判定台算进「淡入」段（多 4 帧） | **已确认** |
| **W3-8** | 事件 6 的淡出 28 帧（原版 24）= 前 2 级各多 2 帧（冷启动） | Z2 的逐级帧数结论（`Z2-blackfield-final.md` Z2-10） | ⭐ **成立**（Z2 已实测：前 2 级各 4 帧、其余 10 级各 2 帧）⇒ 多 4 帧 | **已确认（引 Z2）** |
| **W3-9** | 准备场景返回时把背景放进交接槽（而不是销毁）就能消掉事件 2 | VRAM 算术 | ⛔ **不成立**（同 W3-4）：地图的 64 KB 必须等背景的 32 KB 被**提交释放**之后才能分配 ⇒ 交接槽只能把黑帧从「6 帧」压到「地图上屏所需的最少帧数」，压不到 0 | **已证伪** |
| **W3-10** | 改后黑场事件数 | 重跑判定台 | **6 → 6（事件 1 由 8 帧缩到 2 帧，其余 5 个事件逐帧不变）** ⇒ 「收敛到 2 个」**未达成**（3 个硬切的根因在 W4 独占文件里） | **已确认（未达成）** |
| **W3-11** | ⭐ 开机那 2 帧纯黑 = GBA 的**强制空白**在画面准备好之前就被清掉了 ⇒ 把强制空白撑到背景提交之后即可消掉 | 在 `src/main.cpp` 里直接写 DISPCNT bit 15（强制空白）⇒ 重建 + 重录 + 重跑判定台 | ⛔ **不成立**：重录后**事件 1 仍是 2f（27–28）**（逐帧 mean 与不写强制空白时**完全一样**）⇒ butano 的 display manager 在**每一次** core update 的 update 阶段（`bn_core.cpp:225` 的 `display_manager::update()` → `hw::display::set_display()`）就重写 DISPCNT ⇒ **强制空白撑不过一次 update** ⇒ 实验**回退**（回退后的事件 4 也从 1661–1662 回到 1659–1660） | **已证伪** |
| **W3-12** | 黑场事件的**帧号**对二进制排布敏感 | 同一份源码逻辑的两个 ROM（中间版 vs 最终版）对比 | ⭐ **成立**：中间版的事件 4 在 1659–1660、强制空白实验版在 1661–1660（+2 帧）⇒ **跨 ROM 只可比「每段帧数」，不可比「绝对帧号」**（与任务书 §0.4 的告诫一致） | **已确认** |

---

## 5. 跑过的命令与数字

| # | 命令 | 结果 |
|---|---|---|
| 1 | `wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/w18-w3/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"`（**基线**，未改代码） | `ROM fixed!`；**ROM sha256 = `7c31b4e28052d2130abf2b885ce2b8a6b7ddac93e43204f25a386067fe10797f`**（12115700 B）；无新增告警 |
| 2 | `python tools/s49_package/capture_blackfade.py --rom build/w18-w3/butano-sequel/butano-sequel.gba --out build/w18-w3/blackfade-base --keys "Down,Down,A*21" --zero-frames 240 --frames 2575 --probe build/w18-w3/mgba-probe/mgba-probe.exe` | 2402 帧（`frames_run` 2575）；收据 `rom_sha256` = 基线 sha |
| 3 | `python tools/s49_blackfade/blackfade_report.py --frames build/w18-w3/blackfade-base/frames --out build/w18-w3/blackfade-base/blackfade.json --markdown …/blackfade.md` | **2402 帧 / 6 个事件**；事件 1 = 8f（27–34）、事件 2 = 6f（527–532）、事件 3 = 24/18/28（1549–1618）、事件 4 = 2f（1659–1660）、事件 5 = 8f（2123–2130）、事件 6 = 28/24/28（2171–2250） |
| 4 | 同上（**改后**，中间版） | `ROM fixed!`；ROM sha256 = `786ad2379f5dede76850952363de598d86f6b7f8f83d531227d48a51e0e5950f` |
| 5 | 捕获 + 判定台（改后，中间版） | **2402 帧 / 6 个事件**；**事件 1 = 2f（27–28）**；事件 2…6 的帧号与基线**逐个相同** |
| 5b | **强制空白实验**（见 W3-11）：在开机路径直接写 DISPCNT bit 15 | `ROM fixed!`；ROM sha256 = `68dcb6f701ff7d9863f9d64780a48989c0c12764d8eec35737821c1fbb6c5bfb`；重录后**事件 1 仍是 2f（27–28）**（强制空白**没起作用**），而且**事件 4 从 1659–1660 变成 1661–1662（+2 帧）** ⇒ 二进制排布变了 ⇒ **实验回退** |
| 5c | **最终版**（回退强制空白实验后的源码） | `ROM fixed!`；**ROM sha256 = `bf13fa849875af940ff4f97c1a4131d64fed160ea57b8314f54272a4788d7c72`** |
| 6 | 捕获 + 判定台（**最终版**） | **2402 帧 / 6 个事件**；事件 1 = **2f（27–28）**、事件 2 = 6f（527–532）、事件 3 = 24/18/28（1549–1618）、事件 4 = 2f（1659–1660）、事件 5 = 8f（2123–2130）、事件 6 = 28/24/28（2171–2250）⇒ **除事件 1 外，其余 5 个事件的帧号与基线逐个相同** |
| 6 | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w18-w3/butano-sequel` | 见 §7 |
| 7 | `Get-Process -Name 'mgba-probe' -ErrorAction SilentlyContinue` | 长录制前后各查一次：**孤儿探针 0 个**；全程只有本路 1 路长录制 |

> ⚠️ **本机构建不是字节可复现的** ⇒ 上面所有数字**只绑定本路自己的 ROM sha**，
> 与共享树/其它 lane 的数字**不可比**。
> ⚠️ 探针 exe 是 `build/mgba-probe/mgba-probe.exe` 的**副本**（`build/w18-w3/mgba-probe/`，
> sha `c4a34cd4…`），**共享的那个没动**。

---

## 6. 越界请求（都要改 W4 独占文件 `game/src/battle_runtime_scene.cpp`）

> **给父代理的一页速览**
>
> | 硬切 | 帧号 | 根因行号（W4 的文件） | 一句话修法 |
> |---|---|---|---|
> | **B2** 准备→战斗 6 帧纯黑 | 527–532 | `battle_runtime_scene.cpp:8152` 的 `bn::core::update()` | 把这次 update 挪到部署场景的 `map` 建好之后 ⇒ 黑帧从 6 帧降到 1–2 帧（**到 0 帧被 64 KB BG 图块区卡死**，§6.2） |
> | **B3** 生长段结束→对白 2 帧纯黑 | 1659–1660 | `battle_runtime_scene.cpp:5066-5067` 的 `map.reset(); bn::core::update();` | 把地图→对白背景的交换挪进**入场过渡的黑场持黑段**（遮罩全黑时）⇒ 事件消失，**并顺带把事件 3 的淡入从 28 压回 24** |
> | **B4** 对白段内部 8 帧纯黑 | 2123–2130 | `battle_runtime_scene.cpp:6497-6514` + `battle_visual_resource_coordinator.h:119-131` | 把对白→地图的交换推迟到**事件 2 淡出段的最后几级**（洞只剩 ≤305 px）⇒ 事件消失 |
> | 事件 3 淡入 28≠24 | — | 同 B3 | 同 B3 |
> | 事件 6 淡出/淡入 28≠24 | — | `battle_black_field_star_mask.h`（**归属待定**，§8） | 遮罩冷启动的前 2 级各多 2 帧 ⇒ 遮罩侧的事，与时序常量无关 |

### 6.1 （B1 残留）开机的 2 帧纯黑 —— 根因在 butano 的开机时序，**本路改不掉**

* **现象**：帧 27–28 纯黑，帧 29 才是准备场景背景（改前是帧 27–34 共 8 帧）。
* **根因（实测定位）**：`bn::core::init()`（`third_party/butano/butano/src/bn_core.cpp:424`）
  结尾会跑**一次** `update()` ⇒ 这一 update 提交了 DISPCNT ⇒ **GBA 的强制空白
  (DISPCNT bit 15) 被清掉** ⇒ 从帧 27 起屏上只剩背景板（黑）；而本路的开机背景是在
  `core::init()` **之后**才建的，最早只能到帧 29 才上屏。
* **原版的做法**：原版开机**帧 3 就出画面且从不纯黑** ⇒ 它的强制空白一直开到画面准备好为止。
* **为什么本路改不掉（实测，W3-11）**：试过在开机路径直接写 DISPCNT 的强制空白位
  ⇒ 重录后**事件 1 仍是 2f（27–28）**，逐帧 mean 与不写时**完全一样** ⇒
  butano 的 display manager 在**每一次** core update 的 update 阶段
  （`bn_core.cpp:225` → `display_manager::update()` → `hw::display::set_display()`）
  就重写 DISPCNT ⇒ **强制空白撑不过一次 update** ⇒ 该实验已**回退**。
* **建议修法（都需要改 butano / 换产品方案，不在本路文件里）**：
  1. **（butano 侧）**让 `bn::core::init()` 的那次 update **不要**清掉强制空白
     （或把它推迟到第一次有画面要提交时）⇒ 开机的白屏直接接到画面上 ⇒ **0 帧黑**。
  2. **（产品侧，推荐）**开机做一张**自己的启动画面**（哪怕只是一张纯色/标题图），
     在第一次 update 里提交 ⇒ 强制空白期间屏上就已经是「有内容的画面」，
     与原版「帧 3 出标题画面」的观感一致 ⇒ **顺带**把重制侧 26 帧的白屏
     （原版只有 2 帧）这个更大的观感差一起收掉。
  3. **（可接受现状）**接受 2 帧：判定台把它算成 1 个 2 帧的黑场事件；
     比原来的 8 帧少 4 倍，且全程 walk 帧号零漂移。
* ⚠️ **附带发现（给父代理）**：重制侧开机是 **26 帧纯白**（原版只有 **2 帧**），
  根因在 `bn::core::init()` 之前（BIOS + butano 初始化）⇒ **本路改不掉**
  （butano 是共享树，只读）。这是比那 2 帧黑**更大的**开机观感差。

### 6.2 （B2）准备场景 → 战斗的 6 帧纯黑（527–532）——**结构性，不是顺序问题**

* **根因（硬证据）**：
  1. `battle_preparation_scene.cpp` 在 `phase == ready` 时 `text_sprites.clear();
     panel_sprites.clear(); bn::core::update();`（帧 525–526 = 裸背景，mean 206.23），
     然后 `return` ⇒ 局部的 `bn::optional<bn::regular_bg_ptr> scene_background` 被析构；
  2. `battle_runtime_scene.cpp:8152` 的 `bn::core::update()` 是**准备场景返回之后的第一次
     update** ⇒ 它提交了背景的释放 ⇒ 屏上只剩黑色背景板；
  3. 部署场景的 `map` 在 `:7804-7811` 建，要到它自己的第一次 update（`:7946`）才提交 ⇒
     中间 6 帧（部署场景的建场景 + 64 KB 地图图块上传 + 精灵分配）全是黑。
* **为什么不能简单地把两次提交并成一次**：GBA 的 BG 图块区 = **64 KB**；
  准备场景背景 = 256×256 **4bpp** = **32 KB**；部署场景地图 = 256×256 **8bpp** = **64 KB**；
  32 + 64 = 96 KB > 64 KB ⇒ **两者不可能共存** ⇒ Butano 必须先把旧背景的图块**在一次 update
  里归还给分配器**，才能分配新地图 ⇒ 「释放的提交」与「地图的提交」**不可能在同一次 update**。
  ⇒ **至少 1 帧黑是结构性的**；实测 6 帧是因为部署场景的建场工作全在这段窗口里。
* **建议修法（都在 W4 的文件里）**：
  1. **（推荐，能压到 1–2 帧）**把 `:8152` 那次 `bn::core::update()` **挪到部署场景的
     `map` 建好之后**（或删掉，让部署场景的第一次 update 同时提交「背景释放 + 地图上屏」），
     这样黑帧 = 地图图块上传所需的最少帧数，而不是 6 帧。
     ⚠️ 注意 `:8152` 的注释说明它存在是为了「让 Butano 回收上一局释放的图块」⇒ 挪位置时要确认
     部署场景的精灵/图块分配不会因此 VRAM 不足（部署屏实测有 662 块空闲 OBJ 图块）。
  2. **（要压到 0 帧，需要产品决策）**让准备场景的背景**在部署场景第一次 update 的同一次
     update 里被释放**（本波已经加了 `konoha::battle_screen_handover_background` 这个交接槽，
     正好可以传过去）—— 但这仍然解决不了上面的 VRAM 约束：**地图的 64 KB 必须等背景的
     32 KB 归还之后才能分配** ⇒ 要 0 帧，只能
     (a) 把部署地图改成 4bpp（保真度变更，`graphics/` 既不是 W4 的也不是本路的），或
     (b) 让准备场景的背景**一开始就不是 regular BG**（同样要改 graphics/）。
  3. **（取证用）**原版在「准备 → 部署」这一段**没有可比对的数据**：原版的黑场真值
     （`build/s49-blackfade/original-entry-v2/`）是从 battle-14 入口存档起录的，
     **不含进场转场** ⇒ 这一段**原版到底有没有黑帧，本波无法判定**。

### 6.3 （B3 / B4）两个对白相关的硬切 —— 都在 `battle_runtime_scene.cpp`

| 硬切 | 帧号 | 代码位置（硬证据） | 机制 |
|---|---|---|---|
| **B3** 生长段结束 → 对白 **2 帧纯黑** | 1659–1660 | **`battle_runtime_scene.cpp:5063-5072`**（`battle_dialogue_background_runtime_renderer::update`）：`map.reset();` 紧跟 **`bn::core::update();`** | 对白背景是 8bpp、地图也是 8bpp ⇒ 地图必须先释放并**提交**，对白背景才能分配 ⇒ 那次 update 提交释放的瞬间屏上只剩背景板（黑）⇒ 1–2 帧纯黑 |
| **B4** 对白段内部 **8 帧纯黑** | 2123–2130 | **`battle_runtime_scene.cpp:6497-6514`**（`apply_visual_resource_transition`）+ **`game/include/konoha/battle_visual_resource_coordinator.h:119-131`** | `transition_to(map)` ⇒ `release_script=true` ⇒ `:6499-6502` 释放对白背景/对话框/立绘 ⇒ `:6513` 的 `bn::core::update()` 提交 ⇒ 地图（64 KB）重新分配 + 上屏要 8 帧 ⇒ 8 帧纯黑 |

* **建议修法（B3 + B4 同一个思路）：把 BG cohort 的交换挪进星光圈遮罩盖住屏幕的那一段。**
  * **B3**：把 `map → 对白背景` 的交换从「淡入/生长之后」（`:8475`）**挪到入场过渡的黑场持黑段**
    （`battle_runtime_scene.cpp:8319` 的 fade-in 块**之前**，也就是遮罩还是全黑洞的时候）。
    交换的那 1–2 帧本来就落在 18 帧持黑里 ⇒ 事件数与 24/18/24 结构**都不变**；
    而且淡入与生长阶段洞里会**直接是对白背景**（原版的生长段就是对话框的斜切展开）⇒
    **顺带把事件 3 的淡入从 28 帧压回 24 帧**（§6.4），并可能修掉 Z2 §5 记的「级 29–36 可见像素差 −139…−477」。
  * **B4**：把 `对白 → 地图` 的交换从「对白结束的那一刻」**推迟到事件 2 的淡出段的最后几级**
    （星光圈洞已经缩到 305/173/77/17 可见像素）⇒ 交换帧落在黑场事件内部 ⇒ **不再产生独立事件**，
    可见像素误差 ≤ 数百 px。
* ⚠️ 两处都需要 W4 动 `battle_runtime_scene.cpp`；**本路没有动它**。

### 6.4 事件 3 的淡入 28 帧（原版 24）

* **根因**：生长段（12 级 × 2 帧）的洞里显示的是**地图**，不是对白背景 ⇒ 洞很小 ⇒ mean < 40 ⇒
  判定台把生长段最前面的 4 帧算进「淡入」段（24 → 28）。
* **修法**：与 §6.3 的 B3 同源 —— 交换挪进持黑段后，洞里直接是对白背景 ⇒ 淡入回到 **24**。

### 6.5 事件 6 的淡出/淡入 28 帧（原版 24）

* **根因（Z2 已实测）**：淡出的**前 2 级各占 4 帧**（冷启动：VRAM/图块集第一次分配），其余 10 级各 2 帧
  ⇒ 淡出 24 + 4 = 28；淡入同理。
* **归属**：遮罩的图块分配在 `game/include/konoha/battle_black_field_star_mask.h`
  （**既不是本路、也不是 W4 的独占文件** —— 见 §8「需要父代理指定归属」），
  淡出的级推进在 `battle_black_field_timing.h`（**本路的**）但级数是对的（`frames_per_level = 1`），
  ⇒ **多出来的 4 帧是遮罩的性能问题，不是时序常量问题** ⇒ 本路改时序常量没有意义。

---

## 7. 验收逐条结论

| # | 项 | 结论 |
|---|---|---|
| **W3-1** | 黑场事件清单 | ✅ **实测清单见 §3**（事件数 / 帧号 / 每段帧数 / 是否渐变，与原版逐项对齐表）。<br>本路最终 ROM `bf13fa84…`：**6 个事件**（事件 1 = 2f 27–28、事件 2 = 6f 527–532、事件 3 = 24/18/28 1549–1618、事件 4 = 2f 1659–1660、事件 5 = 8f 2123–2130、事件 6 = 28/24/28 2171–2250）。<br>⚠️ **事件数 6 → 6 未达成**（事件 1 由 8 帧缩到 2 帧）；事件 3/6 的帧数差见 §6.4/§6.5 |
| **W3-2** | B1 / B2 修好并复测 | **B1：✅ 已修并复测**（8 帧 → 2 帧，**walk 帧号零漂移**；残留 2 帧的根因在 butano，§6.1，含一次**已证伪**的强制空白实验）。**B2：⛔ 未修** —— 根因在 `battle_runtime_scene.cpp:8152`（W4 独占），且受 GBA 64 KB BG 图块区的硬约束（§6.2）⇒ 已写越界请求 |
| **W3-3** | B3 / B4 定位 + 可执行修法 | ✅ **定位到确切代码位置**（B3 = `battle_runtime_scene.cpp:5066-5067`；B4 = `:6497-6514` + `battle_visual_resource_coordinator.h:119-131`），并给出**可执行的修法**（把 cohort 交换挪进遮罩盖住屏幕的时段）；因涉及他人独占文件 ⇒ **已写越界请求**（§6.3） |
| **W3-4** | 仪器 | ✅ `tools/s49_blackfade/`（`blackfade_report.py`）**只读调用**；捕获用 `tools/s49_package/capture_blackfade.py`（**只读**，因为 `tools/s49_blackfade/blackfade_capture.py` 自身有 `release_frames` 的 AttributeError 缺陷）。**未新建仪器目录**、**未改任何工具**。探针 exe 用自己的副本 `build/w18-w3/mgba-probe/mgba-probe.exe`（共享的没动） |
| **W3-5** | 单测 | 见 §7.1 |

### 7.1 单测棘轮

`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w18-w3/butano-sequel`

| | pass | fail |
|---|---:|---:|
| HEAD 基线（`build/run-baseline-tests.sh`） | 101 | **20** |
| **本路副本（改后）** | **117** | **21** |

失败名单（21 项）：

```
test_battle_all_scenario_runtime        test_battle_campaign_route
test_battle_campaign_save                test_battle_campaign_scenario_42
test_battle_campaign_scenario_43         test_battle_campaign_scenario_44
test_battle_campaign_scenario_45         test_battle_campaign_scenario_46
test_battle_campaign_scenario_47         test_battle_campaign_scenario_49
test_battle_dynamic_deployment_turn      test_battle_material_pickups
test_battle_presentation_controller      test_battle_range_ui_phase_truth_table  ★
test_battle_runtime_scene_gate           test_battle_s49_input_flow
test_battle_s49_opening                  test_battle_scene_character_actions
test_battle_scene_controller             test_battle_scene_multi_unit
test_battle_scene_results
```

★ = **比 20 项基线多出来的那一项 —— 不是本流引入的**，证据三条：

1. 它**只 `#include "konoha/battle_range_ui_style.h"`**（+ `<cassert>` / `<cstdint>`）
   ⇒ **本流改的 3 个文件（`battle_black_field.h` / `src/main.cpp` / `battle_preparation_scene.cpp`）
   根本不在它的编译单元里**，更没有链接 `battle_runtime_scene.cpp` ⇒ 本流不可能影响它；
2. **实测**：用**共享树**（父代理已回退 `battle_range_ui_style.h`）的头文件编译并运行
   `test_battle_range_ui_phase_truth_table.cpp` ⇒ **通过**
   （`g++ -std=c++23 -I <shared>/game/include … && ./truth_shared` ⇒ `TRUTH_TABLE_PASSES_ON_SHARED_TREE`）；
   本路副本是 wave 18 开火时的快照，仍带着**已被父代理回退**的那版覆盖层规则 ⇒ 它红；
3. `battle_range_ui_style.h` 在共享树与本路副本之间确实不同
   （`git diff --no-index`：5 insertions / 17 deletions）⇒ 差异就是父代理回退的那一处。

⇒ **本流零新增单测失败**；共享树回退后的口径应为 **pass=118 / fail=20**（与 20 项基线逐名相同）。

⭐ **收尾复跑**：在**最终源码**（强制空白实验回退后）上重跑同一脚本 ⇒ **pass=117 / fail=21**，
失败名单与上表**逐名相同** ⇒ 结论对最终源码成立。

---

## 8. 需要父代理裁决的两件事

1. **`game/include/konoha/battle_black_field_star_mask.h` 的归属**（§6.5）：事件 6 淡出多出的 4 帧
   是遮罩的「冷启动」开销，这个文件**既不在本路独占清单、也不在 W4 独占清单**里
   ⇒ 需要指定归属（`battle_black_field_star.h` 是本路的，但遮罩的实现不在）。
2. **B2 要不要做到 0 帧**（§6.2）：做到 0 帧需要动 `graphics/`（准备背景改成非 regular BG，
   或部署地图改 4bpp）—— 那是保真度决策，不是纯顺序问题。

---

## 9. 单测实测

见 §7.1：**本路副本 pass=117 / fail=21**；21 项 = 20 项已知基线 + 1 项**父代理已回退**的
覆盖层规则产物（已用共享树头文件实测该测试**通过**）⇒ **本流零回归**。

---

## 10. 剩余风险

1. ⛔ **「黑场事件 6 → 2」未达成**：B2/B3/B4 三处的根因都在 W4 的独占文件里。
2. ⚠️ **B1 的修复把开机的画面提前了 6 帧**（背景在帧 29 而不是帧 35 上屏）⇒
   **walk 的后半段帧号没动**（已逐个核对），但**开机段多出 7 帧「只有背景、没有菜单」的画面**
   （帧 29–35）⇒ 这 7 帧与原版的标题画面对不上（**原版开机根本没有准备场景**，
   它是标题画面 ⇒ 这一段本来就是 remake 自己的画面，本波未做标题屏）。
3. ⚠️ **本波没跑判定台残差**（`tools/s49_fidelity_report.py`）：任务书的 W3 验收项里没有它，
   且它要求「同一帧集 + 同一 ROM」⇒ 留给波末父代理统一跑（父代理自己的 §0.4 流程）。
4. ⚠️ 准备场景**第一次**循环迭代被跳过了一次 update ⇒ 那 7 帧里按键状态是开机那次 update 的
   （陈旧 7 帧）。实测的按键序列（240 帧零输入 + Down/Down/A）完全落在开机窗口之外 ⇒ 对本波测量无影响。
5. ⚠️ `battle_screen_handover_background` 的槽位是**全局静态**（`battle_black_field.h` 里的
   inline 函数的函数内静态 ⇒ 跨 TU 唯一）⇒ 正常路径下开机路径填、准备场景取空 ⇒ 不泄漏；
   若 `flow.load()` 失败提前返回，槽位里会留下一张背景（下次进准备场景时会被接手，不会重复绘制）。
6. ⚠️ **父代理合并后 ROM sha 会变** ⇒ 本笔记的数字**不能直接套到合并后的 ROM** 上：
   实测证明**同一份逻辑的两个 ROM，事件 4 的帧号能差 2 帧**（W3-12）⇒
   **只有「每段的帧数」可比，「绝对帧号」不可比** ⇒ 波末必须**在合并后的 ROM 上重跑一次判定台**。
7. ⚠️ 开机段（帧 1–35）现在有 **26 帧纯白**（原版 2 帧）+ 2 帧纯黑 ⇒
   **开机的观感仍然与原版差很多**；本波只把「黑场事件」这一项收窄了 8→2 帧，
   **开机画面本身（原版的标题画面）本波没做**（要新美术 + 新场景，超出本波范围）。
