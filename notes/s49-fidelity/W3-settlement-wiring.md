# 流 W3 —— 结算链接线 + 字体扩字 + 结算屏美术 VRAM 量化

> 2026-10-24 · 流 W3（wave 11）
> 工具：本流新建 `tools/s49_w3_settlement/w3_*.py`（2 个）
> 重制线 `D:\Shell\Github\gba-naruto-butano` —— 只改了 W3 的独占文件 + 两个生成源
> 逆向线 `D:\Shell\Github\gba-naruto-reverse` —— **全程只读**
> **未提交 git**

---

## 0. 一句话结论

**结算链的 7 段在产品代码里走通了**（`battle_scene_phase` 加了
`post_battle_dialogue` / `task_menu` 两段，生成的绑定表同步到 26 行）；
**對白屏与任務菜單屏有实际画面**（原版的任务菜单美术本来就在仓里、
**运行时从来没引用过**，现在接上了；對白屏用重制侧自己的对话框 + 新建的
16×16 结算字体画字）；
**結算屏资产级差 px = 1,968（V4 口径，≤ 2,000 ✓）**；
**判定台残差 = 100,210 / 中位 1,323 / 全 0 帧 5 —— 与基线逐项相同**；
⭐ **U3 说的「三张 8bpp 层 = 192 KB > 96 KB VRAM」这个硬约束不成立** ——
Butano/grit **只导出非空图块**，三层实际只占 **10.7 KB**，
**不需要量化、也不需要分层上传**；
⭐ 但 **1:1 抓取层不是可复用的底板**（它是**场景 41 结算屏的整屏截图**，
自带那一局的数字、头像和人名）⇒ 本流做了一张**洗掉动态内容**的底板
（`battle_ui_result_plate`），实测 **1,968 px**，仍 ≤ 2,000；
⭐⭐ 本流还**抓到并修掉了一个真回归**：给 `battle_scene_snapshot` 加字段会
把场景函数的栈帧顶爆（ROM 跑出 `Illegal opcode: 0000bb10`、判定台抓帧直接失败）
⇒ 改成**尺寸中性**的实现（快照尺寸实测回到 **1672 = 与 HEAD 基线逐字节相同**）。

---

## 1. 改动文件清单

### 1.1 重制线（`D:\Shell\Github\gba-naruto-butano`）

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `…\butano-sequel\game\include\konoha\battle_result_content.h` | **改** | ① `battle_settlement_dialogue_line` 加 `speaker_name`（逐字转写的说话人名字）；② 7 页對白补上名字 |
| `…\butano-sequel\game\include\konoha\battle_scene_controller.h` | **改** | ① `battle_scene_phase` 加 `post_battle_dialogue` / `task_menu`（枚举尾部追加，22 个旧相的序数不变）；② `static_assert(battle_scene_phase_count == 26)`；③ 新增 `battle_scene_phase_settlement_stage()`（相位 → 结算链段）；④ `battle_scene_snapshot` 加 `settlement_stage` / `settlement_page`；⑤ `_advance_level_up()` 改写成按 `battle_result_level_up_pages()` 的**扁平子页**推进；⑥ 新增 `_begin_post_battle_dialogue()` / `_advance_post_battle_dialogue()` / `_advance_task_menu()`；⑦ `_advance_training_summary()` 结束后**不再直接 `complete`**，改进 `post_battle_dialogue`；⑧ `confirm()` 分派加两个新相 |
| `…\butano-sequel\game\include\konoha\battle_original_states.h` | **改（生成）** | `tools/butano/generate_battle_original_states.py` 重新生成：24 行 → **26 行**，新增两行 `remake_only` |
| `…\sequel\content\battle_controller_states.json` | **改** | `remake_phase_count` 24 → 26；`remake_only_phases` 加两个；`mapping` 加两行（状态码留空、注明原版 38 态里没有闭合对应态） |
| `…\butano-sequel\game\src\battle_runtime_scene.cpp` | **改** | ① 新增 `battle_settlement_screen_runtime_renderer`（任務菜單屏 + 戰後對白屏）；② 结算屏底板换成 `battle_ui_result_plate`；③ `_add_level_up_ui()` 改用 `battle_result_level_up_pages()`；④ `battle_phase_uses_full_screen_result()` 加两个相；⑤ 相位名加两条；⑥ 增删相应的 include 与调用点 |
| `…\butano-sequel\graphics\battle_ui_result_plate.bmp` / `.json` | **新增** | ⭐ 结算屏 1:1 底板（洗掉抓取层自带的动态内容后合并成**一层**） |
| `…\butano-sequel\graphics\battle_settlement_font.bmp` / `.json` | **新增** | ⭐ 结算链专用 16×16 精灵字体（94 ASCII + 90 汉字） |
| `…\butano-sequel\game\include\konoha\battle_settlement_sprite_font.h` | **新增（生成）** | 结算字体的 Butano 精灵字体头 |
| `…\butano-sequel\game\include\konoha\battle_settlement_font_content.h` | **新增（生成）** | 同一份生成器产出的**不依赖 Butano** 的字符清单（主机单测要用） |
| `…\butano-sequel\game\tests\test_battle_settlement_wiring.cpp` | **新增** | 新单测：7 段链 / 相位→段映射 / 段内页数 / 字体覆盖 / 6 个升級子页 |
| `…\tools\butano\generate_battle_settlement_font.py` | **新增** | 结算字体的生成器（可 `--check` 自检） |

### 1.2 本仓（`D:\Github\gba-naruto`）

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_w3_settlement\w3_build_result_plate.py` | **新增** | 从 1:1 抓取层洗出可复用底板，并按 **index 0 = 透明** 的 alpha 规则量差 |
| `D:\Github\gba-naruto\tools\s49_w3_settlement\w3_settlement_measure.py` | **新增** | 量**运行时实际用的**底板栈（alpha 合成 + V4 口径 + 真值口径） |
| `D:\Github\gba-naruto\notes\s49-fidelity\W3-settlement-wiring.md` | **新增** | 本报告 |

**没有**改 `battle_range_ui_style.h` / `battle_map_content.h` / `grid_pathfinder.h`（W2 独占），
**没有**改 `battle_ui_model.h`（新相在运行时里单独走 `battle_settlement_screen_runtime_renderer`，
`make_battle_ui_model` 的 `default:` 分支本来就落到 `hidden`），
逆向线**一个字节都没写**。

---

## 2. ⭐ 任务 C：结算屏美术（VRAM 硬约束的答案）

### 2.1 U3 的「192 KB > 96 KB」不成立 —— Butano 只导出**非空图块**

U3 的估算是「256×256 8bpp = 每层 64 KB，三层 192 KB」。
但 Butano 走的是 grit，**grit 只导出图块数据里非空的那些 8×8 图块**，
空图块在 map 里指同一个 tile。实测（`build/bn_regular_bg_items_*.h`）：

| 层 | 非空图块 | 图块字节 | map 字节 | 调色板 | 合计 |
|---|---:|---:|---:|---:|---:|
| `scenario_41_result_bottom` | 78 | 2,496 | 2,048 | 512 | **5,056** |
| `scenario_41_result_middle` | 70 | 2,240 | 2,048 | 512 | **4,800** |
| `scenario_41_result_top` | **2** | 64 | 2,048 | 512 | **2,624** |
| **合计** | 150 | **4,800** | 6,144 | 1,536 | **12,480** |

⭐ 而且 **`scenario_41_result_top` 整张是透明的**
（65,536 个像素全是 index 0、只有 1 种颜色）⇒ **三层里只有两层是有效的**。

⇒ **结论：不需要 4bpp 量化，也不需要分层按需上传。**
三层的图块 + map 合计 **≈ 12.5 KB**，离 96 KB 的 VRAM 差两个数量级。

### 2.2 ⭐ 但 1:1 抓取层**不是可复用的底板**

`scenario_41_result_*` 是**场景 41 结算屏的整屏抓取**（alpha 合成后与
`ref-scenario-41-result/screen.png` **逐像素全等，0 差 px**），所以它自带：

* **场景 41 那一局的数字**（100 / 50 / 150，正文右边那一列）；
* **场景 41 那一个角色的头像**（鸣人）；
* **场景 41 那一个人的名字标签**（「鸣人」在第一个名字框里）。

⇒ 直接拿它当 S49（3 个人）的底板 ⇒ **数字会变成场景 41 的死值**，
而且运行时会把 S49 的数字再画一遍 ⇒ **叠字**。

逐行 diff（`tools/s49_w3_settlement/w3_build_result_plate.py` 打的行剖面）
把动态区定位得很准：

| 区域 | 屏幕范围 | 内容 |
|---|---|---|
| 名字行 | y 9..23, x 152..223 | 场景 41 只有「鸣人」，S49 还有「佐助」「小樱」 |
| 头像行 | y 49..100, x 84..224 | 场景 41 只有鸣人的头像，S49 有三个 |
| 数字块 | y 113..149, x 97..230 | 场景 41 只有一列数字，S49 有三列 + 合计 |

### 2.3 洗出可复用底板 ⇒ **1,968 px ≤ 2,000 ✓**

`w3_build_result_plate.py` 把动态区（头像行 + 数字块）用**该行自己的背景色**
填掉，再把三层合并成**一层** 8bpp 底板 `battle_ui_result_plate`。

**实测（alpha 合成，index 0 = 透明）：**

| 栈 | V4 口径 | 真值口径 | 差 bbox |
|---|---:|---:|---|
| 场景 41 抓取层（`scenario_41_result_bottom+middle+top`） | **1,636** | 3,769 | (84, 9, 231, 150) |
| **运行时底板 `battle_ui_result_plate`** | **1,968** | 4,562 | (85, 9, 236, 154) |

⇒ 两个数都 **≤ 2,000** ✓。
（差值的来源很直白：底板洗掉了动态内容，所以剩下的差就是**真值自己的动态内容**
——S49 的三个头像、三列数字和两个人名 —— 一共 4,562 px。
V4 口径每 3 个像素采 1 个，所以报 1,968。）

⚠️ **口径提醒**：沿用 U3 的口径 —— **必须按 alpha 合成**。
opaque paste 口径下抓取层是 12,798 → 12,800（**更差**）。

### 2.4 运行时底板的 VRAM

| 资源 | 图块 | map | 调色板 | 合计 |
|---|---:|---:|---:|---:|
| `battle_ui_result_plate` | 2,496 | 2,048 | 64 | **4,608** |

（结算屏与結算屏互斥驻留；对白屏那一侧见 §4.4。）

### 2.5 升级屏 / 训练页：**不换**，并说明原因

* **升级屏**：`scenario_41_level_up_1_*` 是**整屏烘焙截图** —— 抬头
  「漩涡鸣人的LV升到6级了」、**头像**、**7 行成长值**全在图层里。
  ⇒ 拿它当底板 ⇒ 抬头/头像/数值全是场景 41 的死值。
  ⇒ **升级屏保持 `battle_ui_level_up_panel`**；
  但**子页结构**（3 人 × 2 页 = 6 页）已经按原版接进产品代码（§3.3）。
* **训练页**：仓里**没有** `scenario_41_training_*`（U3-9 已证）⇒ 保持现状。

---

## 3. 任务 A：结算链的 3 条接线点

### 3.1 接线点 1：`battle_scene_controller.h` 的两段新相

* 枚举**尾部追加** `post_battle_dialogue` / `task_menu` ⇒ 22 个旧相的序数不变
  （`battle_scene_phase_origins` 是**按序数索引**的生成表，追加不会挪动旧行）。
* ⚠️ **`battle_scene_phase_origins` 是 24 行生成表，`static_assert == 24` 会失配**
  —— 处理方式（不是手改生成文件）：
  1. `battle_scene_controller.h` 的枚举加两个值；
  2. `sequel/content/battle_controller_states.json` 的 `mapping` 加两行
     （`status: remake_only`、状态码留空、note 写清为什么对不上原版 38 态），
     `remake_only_phases` 加两个，`remake_phase_count` 24 → 26；
  3. **重新运行生成器** `tools/butano/generate_battle_original_states.py`
     ⇒ `battle_original_states.h` 变成 26 行；
  4. `static_assert(battle_scene_phase_count == 26)`。
* `tests/test_battle_scene_phase_mapping.py` 6/6 通过（它会跑
  `生成器 --check`，所以生成物不会漂）。

### 3.2 接线点 1（续）：链的迁移

```
outcome → result → level_up → training → post_battle_dialogue → task_menu → complete
```

* `_settle_result()`：有人升级 ⇒ `level_up`；否则 ⇒ `training` 或
  **`post_battle_dialogue`**（原来直接 `complete`）。
* `_advance_training_summary()`：训练小结走完 ⇒ **`post_battle_dialogue`**（原来 `complete`）。
* `_advance_post_battle_dialogue()`：**7 页**，按 A 逐页推进，走完 ⇒ `task_menu`。
* `_advance_task_menu()`：按 A ⇒ `complete`。
* 段内页数记在新增的 `snapshot.settlement_page` 里；
  `snapshot.settlement_stage` 是**相位 → 段**的映射（`battle_scene_phase_settlement_stage()`）。

### 3.3 接线点 3：`battle_result_level_up_pages()` 接入

* **控制器**：`_advance_level_up()` 改成按 `battle_result_level_up_pages(_result)`
  的**扁平子页**推进（`settlement_page` 0..N-1），
  并用 `_sync_level_up_page()` 把两个旧字段（`result_participant_index` /
  `level_up_detail_page`）同步回去，让表现层不用自己走页表。
  ⇒ 「只有升级了的人才出现、每人 2 页」的语义**没有变**，
  只是页号从「人 + 页」两维变成一维。
* **运行时**：`_add_level_up_ui()` 改成用同一张页表取当前页
  （谁、第 1 页还是第 2 页、7 行成长值）。

### 3.4 接线点 2：`battle_runtime_scene.cpp` 画對白屏与任務菜單屏

新增 `battle_settlement_screen_runtime_renderer`：

| 段 | 画面 |
|---|---|
| **任務菜單** | 原版的**术之里世界地图**底板（`scenario_41_postbattle_bg`，优先级 2）+ 面板层（`scenario_41_postbattle_ui`，优先级 1） |
| **戰後對白** | 同一套底板 + **重制侧自己的对话框**（4 个 `battle_ui_message_panel` 拼成整宽）+ **说话人名字** + **台词**（结算字体，16×16，按 13 字/行折行） |

⭐ **`scenario_41_postbattle_bg` / `scenario_41_postbattle_ui` 早就���仓里，
但运行时从来没有引用过** —— 这就是「内容齐了但画不出来」的那一段。
（`scenario_41_postbattle_dialogue_1..11_*` 那 11 张**不能**用：
它们是场景 41 对白屏的整屏抓取，**台词是烘焙进去的**。）

#### ⭐ 说话人名字**不能靠 character_id 反查**

U3 转写的第 7 页说话人是**卡卡西**，但重制侧的 `character_id 4` 是
**山中井野**（`generated_battle_identity_content.h` 的第 5 行）。
⇒ 名字必须**跟着转写文本走**：本流给 `battle_settlement_dialogue_line`
加了 `speaker_name` 字段（逐字转写的名字），
运行时画的是它，**不是** `battle_character_short_label(character_id)`。
（单测里也钉住了这一条：`battle_settlement_s49_dialogue[6].speaker_name == "卡卡西"`。）

### 3.5 ⭐ 结算链 7 段的状态机单测

`butano-sequel/game/tests/test_battle_settlement_wiring.cpp`：

* 7 段枚举 / 顺序表 / 缺的那两段；
* **相位 → 段**的映射（22 个相位的 6 个结算相逐个断言）；
* 段内页数：升級屏 6 页、戰後對白 7 页、任務菜單 1 页；
* 用产品自己的 `battle_settlement_chain` + 产品自己的页数**走完 7 段**，
  断言按 A 的总按键数 = **1 + 1 + 6 + 1 + 7 + 1 = 17**；
* 结算字体覆盖**产品内容里的每一个字**（7 句對白 + 6 条升級抬头 + 5 个说话人）；
* `battle_result_level_up_pages()` 的 6 个子页顺序与成长值。

### 3.6 ⭐⭐ 本流踩到并修掉的一个真回归：**快照不能变大**

**现象**：第一次带本流改动的 ROM（sha `af0352d0…`）在判定台的**重制侧抓帧**里
于 **step 24 之后画面冻结**（step-24/25/26 三帧的 sha 完全相同），
探针报 **`[mgba] Illegal opcode: 0000bb10`** ⇒ CPU 跑到了非法指令 ⇒ 崩了。
（同一份代码在 wave 10 的基线 ROM `9ff98640…` 上抓满 35 帧、无 stderr。）

**根因**：本流给 `battle_scene_snapshot` 加了 **两个**字段
（`settlement_stage` + `settlement_page`）⇒ 结构体 **1672 → 1676 字节**。
而这个快照是**按值**在场景函数里到处复制的，它的尺寸有**项目自己的门限**：

```
butano-sequel/game/tests/test_battle_runtime_scene_gate.cpp:
    static_assert(sizeof(battle_scene_snapshot<12>) <= 1120);   // 实测 1672
```

⇒ 快照本来就**已经超了项目自己的预算**（1672 > 1120），
再加 4 字节就把场景函数的栈帧顶爆了。

**修法（尺寸中性）**：
* **段**不占字段 —— 用自由函数 `battle_scene_phase_settlement_stage(phase)` 从相位推；
* **页**只用 **1 个字节**，而且**放在结构体原有的对齐空隙里**
  （`training_detail_page` 后面本来就有 1 个 padding 字节）
  ⇒ `sizeof(battle_scene_snapshot<12>)` **实测回到 1672 = 与 HEAD 基线逐字节相同**；
* 结算字体的 `bn::sprite_text_generator` 也从**栈上局部变量**改成
  `BN_DATA_EWRAM static` ⇒ 栈帧零增长。

⇒ **这条要写进路线图**：结算链的接线**不能再往
`battle_scene_snapshot` 里加字段**；要加就必须同时从别处**减**出同样的字节。


---

## 4. 任务 B：字体扩字

### 4.1 ⭐ 为什么两个既有字体都不行

| 字体 | 形态 | 缺什么 |
|---|---|---|
| `battle_result_font` | **8 px 宽**的精灵字体，汉字是**半高**渲染 | 结算链要用的字里缺 **38 个汉字 + 「…」**（`u3_font_gap.py` 报的 42 个里有 4 个是 ASCII，`5 6 L V` 本来就在 Butano 的 ASCII 块里） |
| presentation 字体 | 原版自己的 Shift-JIS 对白字体（862 码） | 缺 **44 码**（0x88C8=以、0x89C6=家、0x8A90=叶、0x8ADB=丸 …）—— **原版自己从没用过这些码**，所以**逆向线里根本没有这些字形**，扩不了 |

⇒ 只能**新造一个重制侧字体**（`battle_identity_font` 的 provenance 注释早就写明
这类字体是「remake side reconstruction, not a ROM byte derivative」）。

### 4.2 `battle_settlement_font`（新增）

* **格子 16×16**（和 `battle_identity_font` 同形）⇒ 汉字**看得清**
  （8 px 宽的版本只能糊成一团）。
* ASCII 块**逐字节**取自 Butano 自己的 `common_variable_16x16_font.bmp`。
* 90 个汉字用系统 CJK 字体（Windows `simsun.ttc`，macOS `PingFang.ttc`）渲染，
  **双色**：index 14 = 正文，index 12 = 1 px 投影（和其它重制字体同一套 index 约定）。
* ⭐ **正文色改成深棕（48,32,16）**、投影纯黑 —— 因为结算屏的字是画在
  **原版那种奶油色对话框**上的（其它重制字体是画在深色战斗地图上的）。
* 字符集 = 结算链自己的内容（7 句對白 + 6 条升級抬头 + 5 个说话人），
  由生成器**从 `battle_result_content.h` 里读出来** ⇒ 字体不会和内容脱节。

### 4.3 生成器与自检

`tools/butano/generate_battle_settlement_font.py` 产出三个文件：
图集、Butano 精灵字体头、**不依赖 Butano 的**字符清单头
（主机单测没有 Butano 的 include 路径，所以字符清单要单独出一份）。
`--check` 会验证三份产物都跟内容一致。

### 4.4 对白屏那一侧的 VRAM

| 资源 | 字节 |
|---|---:|
| `scenario_41_postbattle_bg` | 35,392 |
| `scenario_41_postbattle_ui` | 4,800 |
| `battle_settlement_font` | 23,584 |
| 对话框（4 × 64×64 4bpp 精灵） | ≈ 2,048 |
| **合计** | **≈ 65.8 KB** |

⇒ 对白屏那一侧也 **< 96 KB** ✓（战斗地图在结算相被释放，见
`battle_phase_uses_full_screen_result()`）。

---

## 5. 跑了哪些验证

| # | 命令 | 关键数字 |
|---|---|---|
| **V1** | `python tools/s49_u3_settlement/u3_s4_asset_swap.py --truth … --reference-root …` | 复现 wave 10 的数：结算屏现状 12,798 / **S4 候选 alpha 1,636**；升级屏 7,681 / S4 候选 608。⚠️ **V4 的「升级屏 / 训练页」真值配对是错的**（U3-3），本流不拿它当基准 |
| **V2** | `python tools/s49_u3_settlement/u3_font_gap.py` | `battle_result_font` 缺 **42 个字**（其中 4 个是 ASCII）；presentation 字体缺 **44 码** |
| **V3** | `python tools/s49_w3_settlement/w3_build_result_plate.py --write` | 抓取层 **1,636**；洗过的底板 **1,968**（V4 口径）⇒ **≤ 2,000 ✓** |
| **V4** | `python tools/s49_w3_settlement/w3_settlement_measure.py --out build/w3-probe/settlement-measure.json` | 运行时底板栈 **v4=1,968 / true=4,562** |
| **V5** | `python tools/butano/generate_battle_settlement_font.py` + `--check` | 90 个字符；三份产物自检通过 |
| **V6** | `wsl … /mnt/d/Shell/Github/gba-naruto-butano && python3 -m unittest tests.test_battle_scene_phase_mapping` | **6/6 通过**（含生成器 `--check`） |
| **V7** | `g++ -std=c++23 -Wall -Wextra -Werror -pedantic … test_battle_settlement_wiring.cpp && ./…` | **TEST PASS** |
| **V8** | `wsl … build/run-baseline-tests.sh` | **HEAD 基线：pass=101 fail=20**，失败名 20 个（已存档） |
| **V9** | `wsl … build/w1-run-all-tests.sh` | **工作区：pass=117 fail=20**，失败名 **与基线逐名相同** ⇒ **零回归** |
| **V10** | `wsl … make -j4`（导出 `LIBBUTANOABS`） | **ROM 构建通过**：`butano-sequel.gba` 12,090,464 字节（第一次 `objcopy: Invalid argument` 是已知的并发覆盖，按规程等 60 s 重试即过） |
| **V11** | `build/bn_regular_bg_items_*.h` / `bn_sprite_items_battle_settlement_font.h` | VRAM 实数：底板 4,608 / 任务菜单两层 40,192 / 字体 23,584 字节 |
| **V12** | `python tools/s49_fidelity_report.py --remake-rom build/w3-probe/w3.gba --repeat 1` | **判定台残差 100,210 / 中位 1,323 / 全 0 帧 5 / 归因 5·17·3**（与基线逐项相同），重制侧 **35 帧全抓到** ⇒ ROM 健康 |
| **V13** | `g++ … test_battle_settlement_wiring.cpp` | **TEST PASS**（改了快照字段之后重跑仍然过） |
| **V14** | `build/w3-probe/check_encoding.py` | 11 个改动/新增文件：**bom=False, crlf=0** 全部通过 |

### 5.1 单测棘轮

**HEAD 基线失败 20 项**（`run-baseline-tests.sh`，pass=101）：
`test_battle_all_scenario_runtime`、`test_battle_campaign_route`、
`test_battle_campaign_save`、`test_battle_campaign_scenario_42`…`_49`（8 项）、
`test_battle_dynamic_deployment_turn`、`test_battle_material_pickups`、
`test_battle_presentation_controller`、`test_battle_runtime_scene_gate`、
`test_battle_s49_input_flow`、`test_battle_s49_opening`、
`test_battle_scene_character_actions`、`test_battle_scene_controller`、
`test_battle_scene_multi_unit`、`test_battle_scene_results`。

**工作区失败 20 项，名字与基线逐名相同 ⇒ 零回归**（pass 101 → 117）。
⚠️ pass 的增量不是本流独占的：本流只加了 **1 个**新单测
（`test_battle_settlement_wiring.cpp`），其余是各流陆续加的。
⚠️ `test_battle_runtime_scene_gate` 的**编译失败是预存债**
（同一处 `static_assert(sizeof(battle_scene_snapshot<12>) <= 1120)`，实测 1672，
基线与工作区**同一处**）。
⭐ 本流**没有让快照变大**：段由相位推出、页只用 1 个字节且**塞进结构体原有的
对齐空隙** ⇒ `sizeof(battle_scene_snapshot<12>)` 实测 **1672 = 与 HEAD 基线
逐字节相同**（这正是 §3.6 那个崩溃的修法）。
⇒ 尺寸中性修法之后**又跑了一次全量单测**：仍是 **pass=117 / fail=20、
失败名逐名相同**。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W3-1 | 结算链的 7 段能在产品代码里走通 | 新单测走 `battle_settlement_chain` + 产品页数 | 7 段按序走完，按 A 共 17 次 | **已确认** |
| W3-2 | `battle_scene_phase_origins` 加两行后 `static_assert == 24` 会失配 | 读生成器（按序数索引）+ 改 JSON 后重生成 | 失配属实；同步 JSON + 重生成 ⇒ 26 行，`static_assert == 26` | **已确认** |
| W3-3 | 三张 8bpp 层 = 192 KB > 96 KB VRAM ⇒ 必须量化 | 读 Butano 生成的 `bn_regular_bg_items_*.h` | **前提错误**：grit 只导出非空图块；三层图块 4,800 B + map 6,144 B ≈ **12.5 KB** | **已证伪**（不需要量化） |
| W3-4 | `scenario_41_result_top` 是有效的第三层 | 逐像素统计 | **整张透明**（65,536 px 全 index 0，1 种颜色）⇒ 只有两层有效 | **已证伪** |
| W3-5 | 1:1 抓取层可以直接当 S49 的底板 | alpha 合成后逐行 diff 定位动态区 | **不行**：它是场景 41 整屏截图，自带那一局的数字/头像/人名 | **已证伪** |
| W3-6 | 洗掉动态内容后差 px 仍 ≤ 2,000 | `w3_build_result_plate.py` 实测 | **1,968 ≤ 2,000 ✓** | **已确认** |
| W3-7 | opaque paste 口径可用 | 同一栈两种合成规则各测一次 | opaque 下抓取层 12,798 → 12,800（更差） | **已证伪**（必须 alpha） |
| W3-8 | 升级屏的 1:1 层可以当底板 | 看合成图 | **不行**：抬头/头像/成长值全烘焙在图层里 | **已证伪** |
| W3-9 | 任务菜单屏没有现成美术 | 扫 `graphics/` | **有**：`scenario_41_postbattle_bg` + `…_ui`，但**运行时从未引用** | **已证伪**（缺的是接线不是美术） |
| W3-10 | 对白屏的 1:1 层可以复用 | 看合成图 | **不行**：场景 41 的台词是烘焙的 ⇒ 改用重制自己的对话框 + 自己的字体 | **已证伪** |
| W3-11 | 结算链的文字能用现有字体画 | `u3_font_gap.py` 对两个字体各查一次 | `battle_result_font` 缺 38 汉字 +「…」；presentation 缺 44 码且**原版从没用过 ⇒ 逆向线里没有字形** | **已证伪**（必须新造） |
| W3-12 | 16×16 的结算字体放得下 | 读 Butano 生成的精灵项头 | 184 格 × 4 图块 = 736 图块 = 23,584 字节；连对白屏全部资源 ≈ 65.8 KB < 96 KB | **已确认** |
| W3-13 | 控制器改写会让既有单测变红 | 基线 vs 工作区跑全量单测 | 20 vs 20，**逐名相同** | **已确认** |
| W3-14 | `battle_result_level_up_pages()` 接入后升級段语义不变 | 比对改前/改后的页数与旧字段 | 升级了 N 个人 ⇒ 2N 页；`result_participant_index` / `level_up_detail_page` 同步回旧值 | **已确认** |
| W3-15 | 给 `battle_scene_snapshot` 加两个字段是安全的 | 抓帧（判定台重制侧）看 ROM 是否还活着 | **不是**：ROM 在 step 24 后冻结，探针报 `Illegal opcode: 0000bb10` ⇒ 快照本来就超了项目门限（1672 > 1120），+4 字节顶爆栈帧 | **已证伪** |
| W3-16 | 段可以由相位推出、页只占 1 字节且塞进原有对齐空隙 ⇒ 尺寸中性 | 编译期量 `sizeof(battle_scene_snapshot<12>)` | **1672 = 与 HEAD 基线逐字节相同** | **已确认** |
| W3-17 | 對白第 7 页的说话人「卡卡西」能用 `character_id` 反查 | 读 `generated_battle_identity_content.h` | **不能**：重制侧的 `character_id 4` 是**山中井野** ⇒ 名字必须跟着转写文本走（`speaker_name` 字段） | **已证伪** |

---

## 7. 未达成 / 留给别人的

| 项 | 说明 |
|---|---|
| **升級屏美术没换 1:1 层** | `scenario_41_level_up_1_*` 是整屏烘焙截图（抬头/头像/成长值都在里面），换上去 S49 会显示场景 41 的死值。**子页结构（3 人 × 2 页 = 6 页）已经按原版接进产品代码**；美术要等原版 BG 层（不含 message 层）的干净抓取 |
| **訓練页没换** | 仓里没有 `scenario_41_training_*`（U3-9），且 V4 用的「訓練页真值」`07-ninja-tool-list.png` 其实是小樱升級第 2 页 ⇒ **那条真值配对本身是错的** |
| **對白屏 / 任務菜單屏的运行帧截图** | 本流只做到「产品代码里画得出来」+ 资产级测量。**逐帧对照留给 W1 的运行帧录制流**（W1 已经在录勝利/結算屏的运行帧；它要用的是 **U2 的那条获胜按键脚本** `build/s49-battle-balance/u2/route.json` —— 本流把结算链加长了两段，那条脚本的按键数**不够走到 `complete`**（旧的链 8 次 A，新链要 16 次），W1 复用它时要**补 8 次 A**） |
| **判定台的重制侧 ROM 路径** | 本流测残差时用的是**私有副本** `build/w3-probe/w3.gba`（sha `b6c2a05f…`），因为共享的 `butano-sequel/butano-sequel.gba` 被别的流的探针**内存映射锁住**，写不进去（`objcopy: Invalid argument` / `user-mapped section open`）。**修好后必须把共享 ROM 换回这个版本** —— 否则共享目录里留着一个会崩的 ROM |
| **判定台残差** | 见 §8 |

---

## 8. 判定台残差

**测量口径**：固定 walk（判定台自带的 S49 开机 + 34 次 A），
**固定 ROM sha**，同一台机器、同一份原版 ROM（sha `1198ece7…`）。

| | 基线（wave 10） | **W3 之后** |
|---|---:|---:|
| 判定台 ROM（重制侧） | `9ff9864047ece0fc…` | **`b6c2a05fa50e2861…`** |
| 残差**总和** | 100,210 | **100,210** |
| 残差**中位** | 1,323 | **1,323** |
| **全 0 帧** | 5 | **5** |
| 归因 | 一致 5 · 产品差 17 · 配对差 3 | **一致 5 · 产品差 17 · 配对差 3** |
| 覆盖层残差 | 857 / 17 帧 exact | **857 / 17 帧 exact** |
| 重制侧抓帧 | 35 帧，capture_ok | **35 帧，capture_ok** |

⇒ **残差与基线逐项相同 ⇒ 只许变小这条满足（没有变大）**。
（本流的改动只落在**结算链的后两段**和**结算屏底板**上，
判定台的 walk 走不到结算链 ⇒ 残差理应不变，实测正是逐项不变。）

⚠️ **这次测量还抓到了一个真回归（见 §3.6）**：第一次带本流改动的 ROM
（sha `af0352d0…`）在抓帧里**画面冻结、探针报 `Illegal opcode: 0000bb10`**
⇒ 判定台直接报 `capture 'remake' did not complete`。
根因是 `battle_scene_snapshot` 长了 4 字节 ⇒ 场景函数的栈帧顶爆。
**尺寸中性修法之后 ROM 恢复健康（35 帧全抓到），残差回到基线。**

---

## 9. 确认

* **新文件全部 LF、无 BOM**（2 个 `tools/s49_w3_settlement/*.py` + 1 个新单测
  + 2 个生成头 + 1 个生成器 + 本报告）；改动的 6 个头文件/源文件也扫过
  （`build/w3-probe/check_encoding.py`：11 个文件 **bom=False, crlf=0**）。
* **未提交 git**（重制线与本仓的工作区改动都留在工作区里）。
* **未改** `battle_range_ui_style.h` / `battle_map_content.h` / `grid_pathfinder.h`。
* **逆向线全程只读**。
* 私有探针：`build/mgba-probe-w3/mgba-probe.exe`（**没有**覆盖共享的
  `build/mgba-probe/mgba-probe.exe`）；收工时复查 `Win32_Process` 里的
  `mgba-probe.exe`，**本流没有留下孤儿进程**（剩下的两个是 W1 流的）。
* ⚠️ **共享 ROM 的状态**：判定台测的是私有副本
  `build/w3-probe/w3.gba`（sha `b6c2a05f…`）。
  共享的 `butano-sequel/butano-sequel.gba` 在本流测残差时被别的流的探针锁住
  （`user-mapped section open`），**里面一度还是那个会崩的 13:07 版本**。
  ⇒ 本流留了 `build/w3-probe/replace_shared_rom.ps1` 轮询复制，
  **锁一放就换好了**：共享 ROM 现在是 **sha `b6c2a05f…` / 12,090,380 字节**
  ⇒ **共享目录里已经是修好的版本**（父代理不用再动手）。
  ⇒ 但**别的流如果在此之前用旧 ROM 抓过帧，那些帧是崩版的**，重跑即可。
  ⇒ ⭐ **收工时观察到 W1 流的三个探针已经在用本流的私有副本
  `build/w3-probe/w3.gba` 抓帧** ⇒ W1 拿到的也是**修好的 ROM**。
  ⇒ 本流自己的探针（`build/mgba-probe-w3`）**残留 0 个**。
