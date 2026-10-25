# F 流 · 覆盖层规则判定 —— 原版 BG2 覆盖层的「点亮规则」

> 2026-10-23 · stream F（wave 2 关键路径）
> 独占产出：本文件 + `tools/s49_rule_probe/`；临时产物在 `build/s49-rule/`。
> **未改动**重制线、逆向线、master 仓其他任何文件。
>
> ⚠️ **2026-10-24 订正（wave 3 的 G 流证伪了本报告 §8 的两条施工前提）**：
> ① **「一格 = 16×16 px」不是游戏格** —— 16×16 是**本报告的分析单位**（逻辑格），
>    **原版的战斗格 = 32×16 px**（三条独立证据：格线间距实测竖 32 px / 横 16 px、
>    `movegrid` 青区按 32 px 合并后 = **曼哈顿半径 3 菱形**、ROM 碰撞网格 `width_tiles>>2`）。
>    ⇒ **1 战斗列 = 2 逻辑列，1 战斗行 = 1 逻辑行**。
>    ⇒ 照 §8.2 把 `tiles_per_cell_x` 4→2 **会把 32 px 格线画成 16 px（错的）**。
>    G 流已按正确口径实现：`notes/s49-fidelity/G-overlay-alignment.md`。
> ② **「多画 310–420 格 / 缺 96–129 格」这个口径本身是错的** ——
>    那是拿**原版的地图空间缓冲**去减**重制侧的屏幕空间图层**。
>    两侧都换算到 16×16 逻辑格后重算，`movegrid` 实为**多画 42 格 / 缺 24 格**。
> ③ **§7.2 的「坐标对应未建立」已关闭**：原版覆盖层是一张 **256×256 px 的地图空间缓冲**，
>    滚动量就是相机（`bg_hoffs=240, bg_voffs=24`）；
>    battle-14 = 逆向线 map id 14（15×19 战斗格，可走 147 / 不可走 138），
>    坐标 `(bx,by)` = 碰撞网格列行、**无偏移**（`notes/s49-fidelity/M-original-victory-truth.md`）。
> ④ **§1 的族优先级仍待定论**：G 流对拍出现 **30 处「原版青 `hatch` / 重制绿 `hatch_shift`」**
>    ⇒ 书面顺序 `target > move` **与实机相反**（G-H15，未验）。
>
> **本报告的规则本体（六族语义、图砖像素、调色板恒等、判定优先级框架）仍然成立**；
> 被推翻的是 §8 的两条施工前提与 §7 的坐标卡点。

---

## 0. 一句话结论

**原版覆盖层点亮的格是「可达范围高亮」，不是「不可达范围压暗」。**

六族语义（由原版自己的图砖像素 + bank-12 调色板 + 重制侧 `battle_range_ui_style.h`
的角色名三方对齐**逐项**确定）：

| 族 | 图砖 | 原版画的东西 | 调色板（bank 12） | 语义角色 | 重制侧同义 tile kind |
|---|---|---|---|---|---|
| `blank` | 256,257 | 全透明（索引 0） | 0 (0,0,0) | 战场之外 / 不画 | — |
| `edge` | 258–261 | **1 px 细格线**（石板蓝） | 1 (66,107,140) | 可走但**未被高亮**的格 → 只画格线 | `grid` |
| `hatch` | 262–265 | **实心亮青** | 2/3 (24,206,255)/(8,107,173) | **移动（可达）范围** | `move` |
| `line_alt` | 266–269 | **实心橙** | 4/5 (255,57,0)/(165,41,0) | **攻击范围 / 移动落点** | `attack_range` |
| `band` | 270–273 | **实心黄** | 6/7 (255,189,0)/(148,107,0) | **光标格** | `cursor` |
| `hatch_shift` | 274–277 | 实心绿 | 8/9 (173,255,0)/(82,132,0) | **合法目标**（这四个时刻**没被用过**） | `target` |
| `solid` | 278–281 | **50% 灰网点** | 10/11 (74,74,74)/(33,33,33) | **受阻格**（不可进入 / 被单位占住） | `blocked` |

⇒ **不可达但可走的格根本没有被"压暗"**：它们只拿到 1 px 的格线（`edge`），
像素上等于透明。被"压暗"的是 **受阻格**（`solid`，灰色网点）—— 这是**地形属性**，
不是"可达性"的反面。

---

## 1. 可执行判据

对 16×16 px 的**逻辑格**（= 2×2 个 8×8 tilemap 项；整张覆盖层是 16×16 格 = 256×256 px
的 BG2 背景区），原版给每格只画一个族，优先级自高而低：

```
cursor (band)  >  target (hatch_shift)  >  attack_range (line_alt)
              >  move_range (hatch)     >  blocked (solid)
              >  walkable (edge)         >  outside (blank)
```

调用者要提供的状态就是五个格集合（= "单位格坐标 + 地形属性"经游戏自己的
寻路/距离场解析后的结果）：

```python
OverlayState(
    extent       = 战场范围（格线画到哪）,
    blocked      = 受阻格（地形不可进入 / 被别的单位占住）,
    move_range   = 当前单位的可达集合,
    attack_range = 当前单位的攻击范围 / 移动落点,
    cursor       = 光标格,
)
```

实现在 `tools/s49_rule_probe/overlay_rule.py`（`OverlayState` / `cell_family` /
`predict`），语义表与调色板恒等检查也在同一文件。

---

## 2. 四个时刻逐格全等的证据

`python tools/s49_rule_probe/verify_moments.py --out build/s49-rule/verify-moments.json`
（exit 0，`RESULT: PASS`）：

```
=== A. reproduction: the original's own BG2 tilemap, byte for byte ===
  field-frame-v1       126 frame(s) reproduce the exported tilemap   first=a-1567.bin
  movegrid-frame-v1    283 frame(s) reproduce the exported tilemap   first=a-1694.bin
  grid16-frame-v1        1 frame(s) reproduce the exported tilemap   first=a-1505.bin
  banner-frame-v1     1107 frame(s) reproduce the exported tilemap   first=a-0380.bin
  all four reproduced: True

=== B. rule prediction vs the original, per logical 16x16 cell ===
  field-frame-v1     original lit  192  predicted  192  overlap  192  original-only   0  remake-only   0  family mismatches   0  => EXACT
  movegrid-frame-v1  original lit  192  predicted  192  overlap  192  original-only   0  remake-only   0  family mismatches   0  => EXACT
  grid16-frame-v1    original lit  175  predicted  175  overlap  175  original-only   0  remake-only   0  family mismatches   0  => EXACT
  banner-frame-v1    original lit    0  predicted    0  overlap    0  original-only   0  remake-only   0  family mismatches   0  => EXACT
  all four exact: True

=== B2. held-out base layer (field's extent+blocked -> movegrid) ===
  base layer shared by field and movegrid: True
  field-frame-v1     original lit  192  predicted  192  original-only   0  remake-only   0  => EXACT
  movegrid-frame-v1  original lit  192  predicted  192  original-only   0  remake-only   0  => EXACT
  all exact: True

=== C. role / palette identity ===
  band        role cursor           opaque palette [6, 7] (allowed [6, 7]) ok
  blank       role grid (nothing)   opaque palette [] (allowed [0]) ok
  edge        role grid             opaque palette [1] (allowed [1]) ok
  hatch       role move             opaque palette [2, 3] (allowed [2, 3]) ok
  hatch_shift role target           opaque palette [8, 9] (allowed [8, 9]) ok
  line_alt    role attack_range     opaque palette [4, 5] (allowed [4, 5]) ok
  solid       role blocked          opaque palette [10, 11] (allowed [10, 11]) ok
  palette identity (bank 12 == remake slots 225..235): True
  roles ok: True

=== D. cursor cross-check (OAM -> logical cell) ===
  field-frame-v1     scroll=(240,24) band cells=[(15, 6)] confirmed=True
      ground_truth_oam         sprites= 32 on a band cell=0
      local_reproduction_oam   sprites= 32 on a band cell=1  e.g. slot12 tile24 cell(15, 6)
  ...
RESULT: PASS
```

**逐格全等的口径**：B 段按 16×16 逻辑格（不是 8×8 tilemap 项）比，
`original-only = 0`、`remake-only = 0`、**族名逐格 0 处不一致**。
B2 是**留出检验**：把 `field` 时刻的"战场范围 + 受阻格"整体搬到 `movegrid` 时刻
（只换该时刻自己的高亮集合），预测仍然逐格全等 ⇒ **基层是跨时刻稳定的量**，
变的只有高亮层。

### 2.1 四个时刻是**本机可逐字节复现**的（这是最强的门禁）

原始导出（macOS 收据）里没有 savestate，但原版 walk 的输入序列是固定的
（`mgba_original_s49_ui_boundaries.lua`：90 帧空输入 + 24×(A 按住 4 帧 + 90 帧 settle)）。
用探针从 `scenario-49-battle-14-entry.ss9` 重放，逐帧导出 BG2 的 tilemap
（VRAM `0x06001000`，2048 B），**四个时刻的 tilemap 全部逐字节命中**
（sha256 与导出的地面真相相同）。命中帧：

| 时刻 | walk 索引 | 全局帧 | 命中帧数 |
|---|---|---|---:|
| banner | `a-0380` | 471 | 1107 |
| grid16 | `a-1505` | 1596 | **1**（瞬态！） |
| field | `a-1567` | 1658 | 126 |
| movegrid | `a-1694` | 1785 | 283 |

⇒ **G 流可以直接用这四条 sha256 当门禁期望值**，不必依赖 macOS 收据。
⚠️ `grid16` 只存在 **1 帧**，按内容定位（sha256），**不要按帧序号**。

---

## 3. 规则是怎么定下来的（关键证据）

### 3.1 三方恒等：原版 bank 12 == 重制侧 225–235

wave 1 已经确认"重制侧调色板索引 225–235 与原版 16 色覆盖层调色板逐项 RGB5 相同"。
本流把它**反向用起来**：原版 bank 12 的索引 `i` 对应重制侧槽位 `224+i`
（索引 0 是透明的"什么都不画"，所以重制的 225 == bank12 的 1）。
重制侧 `battle_range_ui_style.h` 里每个槽位都有角色名，于是：

```
bank12  1 (66,107,140)  == 225 grid_secondary   -> edge   = 格线
bank12  2 (24,206,255)  == 226 move_primary      -> hatch  = 移动范围
bank12  3 (8,107,173)   == 227 move_secondary    -> hatch  = 移动范围（边线）
bank12  4 (255,57,0)    == 228 attack_primary    -> line_alt = 攻击范围
bank12  5 (165,41,0)    == 229 attack_secondary  -> line_alt = 攻击范围（边线）
bank12  6 (255,189,0)   == 230 cursor_primary    -> band   = 光标
bank12  7 (148,107,0)   == 231 cursor_secondary  -> band   = 光标（边线）
bank12  8 (173,255,0)   == 232 target_primary    -> hatch_shift = 合法目标
bank12  9 (82,132,0)    == 233 target_secondary  -> hatch_shift = 合法目标（边线）
bank12 10 (74,74,74)    == 234 blocked_primary   -> solid  = 受阻
bank12 11 (33,33,33)    == 235 blocked_secondary -> solid  = 受阻（边线）
```

**11/11 逐项相同**（`verify_moments.py` 的 C 段自动复算）。
再把 32 块图砖的像素解出来对照。**关键坑**：图砖在 VRAM 里是 **32 字节步长**
（tile 256 在 VRAM `0x2000`，`0x2000/32 = 256` ✓ 与 `base_tile_index` 自洽），
按 4bpp 解读；`bg2-tiles-4bpp.bin` 是 **32 块 × 32 B**，不是 64 块 × 16 B。
按 16 B 步长读会得到"edge 族全是空白"，与导出的 `.bg2-layer.png` 里明显的
细蓝格线矛盾 ⇒ 32 B 步长是对的。

```
tile 256/257 (blank)     全 0（透明）
tile 258 (edge)          x=7 一列索引 1        -> 右侧竖线
tile 259 (edge)          y=7 一行索引 1        -> 底边横线
tile 260 (edge)          y=7 一行索引 1        -> 底边横线（与 259 像素相同）
tile 261 (edge)          x=7 一列 + y=7 一行    -> 竖线+横线（角）
tile 262-265 (hatch)     整块索引 2，末列 3    -> 移动范围（青）
tile 266-269 (line_alt)  整块索引 4，末列 5    -> 攻击范围（橙）
tile 270-273 (band)      整块索引 6，末列 7    -> 光标（黄）
tile 274-277 (hatch_shift) 整块索引 8，末列 9   -> 合法目标（绿，这四时刻未用）
tile 278-281 (solid)     索引 10/11 交替网点 + 底边索引 11 -> 受阻（灰网点）
```

**每个族画什么、画的是哪个调色板索引，全部是机器读出来的，不是猜的。**
（族名沿用导出器的词表；本流只补上了它们**各自是什么**。）

### 3.2 动态证据：青色区随光标移动而整体改写，灰区不动

`field → movegrid` 逐格差（16×16 逻辑格）**恰好 53 格**，而且每一处变化都符合
"旧高亮退回格线 + 新高亮盖上格线"：

| 变化 | 格数 | 含义 |
|---|---:|---|
| `edge → hatch` | 38 | 新的可达范围 |
| `hatch → edge` | 8 | 旧可达范围撤销 |
| `line_alt → hatch` | 4 | 旧落点变成新可达格 |
| `line_alt → edge` | 2 | 旧落点撤销 |
| `band → edge` | 1 | 旧光标撤销 |

**灰（`solid`）的集合在这两个时刻完全没动** ⇒ 灰是**地形/占位**属性，
不是"可达性"的反面。
⇒ 「可达范围高亮」成立；「不可达范围压暗」被证伪（若灰是压暗层，
它应当是可达集合的补集，会随光标一起变）。

### 3.3 光标身份独立确认（OAM，不是覆盖层）

用探针 `dump 117440512 1024`（**OAM；注意探针的 `dump` 地址按十进制解析**，
而 `framedump`/`keyseq` 吃 `0x` 字面量）读原版 OAM，把 OBJ 的屏幕坐标
加上该时刻的相机滚动（`bg2_hoffs=240, bg2_voffs=24`）换算成逻辑格：

* `field` 时刻：slot 12（tile 24，32×32）落在逻辑格 **(15, 6)**，
  而覆盖层唯一的 `band`（黄）格正是 **(15, 6)** ⇒ **黄格 = 光标格**。
* `grid16` 的光标精灵落在 (12,6)，而地面真相的黄格是
  {(12,7),(13,7),(14,6),(15,6)} —— 那是**相机平移途中的 1 帧瞬态**，
  精灵与地面真相可能差一帧（macOS 收据的 `oam-00.bin` 与 tilemap 导出也不是同一帧）。

---

## 4. 做了什么 / 改了哪些文件

| 文件 | 作用 |
|---|---|
| `tools/s49_rule_probe/overlay_ground_truth.py` | 地面真相加载器：1024 项 tilemap → 16×16 逻辑格；32 块图砖解码（32 B 步长 / 4bpp）；bank-12 调色板；族词表 |
| `tools/s49_rule_probe/overlay_rule.py` | **规则本体**：族↔角色表、优先级、`OverlayState` / `cell_family` / `predict`；bank-12 ↔ 225–235 恒等自检 |
| `tools/s49_rule_probe/capture_original.py` | 用探针重放原版 A×24 walk，**按内容**定位四个时刻并落 savestate；再导出 EWRAM/IWRAM/VRAM/OAM |
| `tools/s49_rule_probe/verify_moments.py` | **验收门禁**：A 复现 / B 逐格全等 / B2 留出基层 / C 角色恒等 / D 光标对拍；写 JSON 收据，失败即 exit≠0 |

临时产物（不进仓）：`build/s49-rule/`（walk 逐帧 dump、capture/*.ss9、*.ewram-0000.bin、
*.iwram-0000.bin、*.oam-0000.bin、`verify-moments.json`）。

## 5. 跑了哪些验收命令

```powershell
# 1) 私有探针（不要覆盖共享的 build/mgba-probe/mgba-probe.exe）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-f'
python tools/mgba_probe/build.py

# 2) 复现四个时刻 + 抓原版状态
python tools/s49_rule_probe/capture_original.py --out build/s49-rule/capture
#    -> field a-1567 / movegrid a-1694 / grid16 a-1505 / banner a-0380（sha256 命中）

# 3) 验收门禁（一条命令，exit 0 = PASS）
python tools/s49_rule_probe/verify_moments.py --out build/s49-rule/verify-moments.json

# 4) 单独看规则与调色板恒等
python tools/s49_rule_probe/overlay_rule.py
```

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| H1 | 覆盖层是「可达范围高亮」 | 族↔调色板↔重制侧角色名三方对齐 + 图砖像素 | hatch=青=move、solid=灰=blocked、line_alt=橙=attack、band=黄=cursor | **已确认** |
| H2 | 覆盖层是「不可达范围压暗」 | field→movegrid 逐格差分 | 青色区随光标整体改写、灰区不动；灰不可能是"可达性的补集" | **已证伪** |
| H3 | 覆盖层是每张地图烘焙好的静态布局图 | field vs grid16 逐格差 | 43 格不同（solid→edge 19、solid→blank 17、edge→solid 2、solid→band 3、solid→hatch 2） | **已证伪**（但 field↔movegrid 的基层相同 ⇒ 基层是逐帧重画、跨时刻可稳定） |
| H4 | 四个时刻能在本机逐字节复现 | 探针重放 A×24 walk + BG2 tilemap sha256 | 4/4 命中（126/283/1/1107 帧） | **已确认** |
| H5 | 覆盖层内容随相机平移（屏幕空间） | 32×32 tilemap 全位移搜索（1024 个位移） | 最佳位移 = (0,0)，860/1024 相同 ⇒ 内容锚在**地图空间** | **已证伪** |
| H6 | 覆盖层 tilemap 的 16×16 格 == 原版战斗格 | OAM 光标反推 vs roster 坐标 | 光标落在 (15,6)，roster 的 9 个单位坐标里没有它 | **未验** → ⭐ **2026-10-24 已解（G 流）**：16×16 是**逻辑格**，**战斗格 = 32×16 px**；**1 战斗列 = 2 逻辑列，1 战斗行 = 1 逻辑行** ⇒ 两者**不是**同一格 |
| H7 | 移动范围存在原版 EWRAM/IWRAM 的逐格数组里 | 4 种形状 × 2 区域 × 4 时刻穷举（按 hatch 集合 / 角色码网格两种判据） | 0 命中 | **已证伪**（该形态；原版多半是现算现写 VRAM） |
| H8 | 六族 == 重制侧 6 个 tile kind | bank 12 与 225..235 逐项 RGB5 | 11/11 逐项相同 | **已确认** |
| H9 | 重制侧 battle-14 地图的 blocked 集 == 原版覆盖层的 solid 集 | 16×16 全偏移相关 | 最佳重叠 49/83（纯真度 ~0.6） | **已证伪**（在当前坐标映射下）→ ⭐ **2026-10-24 需重算（G 流）**：当时的坐标映射**是错的**（把逻辑格当战斗格）；正确映射下 battle-14 = 逆向线 map id 14，**可走 147 / 不可走 138**（`M-original-victory-truth.md`） |
| H10 | 探针 `dump` 的地址参数按十进制解析 | `dump 04000000 8` 解出 0x003D0900 | 确认十进制；`framedump`/`keyseq` 则是 `0x` 字面量 | **已确认** |

---

## 7. 剩下什么 / 卡在哪

1. **（卡点）"单位格坐标 + 地形属性 → 移动/攻击范围"这一步还没在原版侧落地。**
   原版的可达集合**不在** EWRAM/IWRAM 里以逐格数组的形式存在（H7），
   而它算出来的形状**不是**朴素的菱形（BFS 步数）也不是欧氏圆：
   `movegrid` 的青区逐行宽度是 12 / 10 / 6 / 2（关于第 6 行对称），
   左右边界相对中心**不同步**（左边界每行 +2，右边界 −2），
   并且在 (8,7)、(9,7) 被占住的两格上被挖空。
   ⇒ 要么原版的距离函数在**带地形成本的地图**上算，要么战斗格与覆盖层逻辑格**不是同一格**。
   **下一步（建议给 G 流）**：用重制侧自己的 `grid_pathfinder.h` / `battle_map_movement.h`
   算一套范围，然后用本流给的 sha256 门禁去卡：
   `field ce5dd2917f062e5ef8f868898c8f3f7aa70e49cbd93cf50eaec274755efd487e`
   `movegrid 72dbe5858aa2fb5e8cf09208a61b26f788d8bd785a640035532f4396ed5ea230`
   `grid16 c1236fbbb8047a571f4685b252cc3e0721cab8e903698d535a61279b56a3fa3e`
   `banner 193aa2d94d7f3f161c06614a2e0a573820866b5b9874c441ee6314adda38ed18`
   （覆盖层的 2048 B tilemap 逐字节相等 ⇒ 逐格全等。）

2. **覆盖层逻辑格与重制侧战斗格的坐标对应关系未建立。**
   原版覆盖层是 16×16 逻辑格（256×256 px），重制侧 battle-14 地图是 **15×19** 格，
   两者对不上（H6/H9）。要么重制侧地图不是这场战斗用的那张，要么战斗格 ≠ 16 px。
   **卡点**：需要原版自己的地图数据（格数 + 地形类别 + 通行成本）。

3. **逐格"命中"的是"原版自己画的"，不是"从外部状态推出来的"。**
   B 段的状态是从该时刻自身的覆盖层反解出来的（自洽性检验）；
   B2 段是跨时刻留出（基层可搬运）；A 段是**逐字节**复现原版。
   真正"由（单位坐标 + 地形）预测出这四张图"的那一步，取决于 §7.1。

4. **`grid16` 是 1 帧瞬态**（相机平移途中），它的基层与 field/movegrid 不同
   （43 格）。要复现它必须逐帧对齐到那一帧。

5. **`docs/sequel-roadmap.md` 本轮未更新** —— 按本流的文件归属约定，
   路线图由主线/父代理统一更新。

---

## 8. 给 G 流的施工要点（可直接抄）

1. **族词表照抄原版**：`blank / edge / hatch / line_alt / band / solid`
   （原版还多一个 `hatch_shift`=绿色"合法目标"，这四个时刻没用过，但图砖在原版 tile 集里）。
2. ~~**一格 = 16×16 px**（2×2 图砖），不是 32×16。~~
   ⭐ **2026-10-24 订正（被 G 流证伪）**：16×16 px 是**分析单位（逻辑格）**，
   **原版的战斗格 = 32×16 px**；**1 战斗列 = 2 逻辑列，1 战斗行 = 1 逻辑行**。
   ⇒ **不要**把 `battle_range_ui_tiles_per_cell_x` 4→2（那会把 32 px 格线画成 16 px）。
   正确的施工见 `notes/s49-fidelity/G-overlay-alignment.md`。
3. **画法**：`edge` = 1 px 格线；`hatch`/`line_alt`/`band` = 实心填充（边界用次色）；
   `solid` = 50% 网点（不是实心）。
4. **调色板独立 bank 12**（不能与地图共用），11 个已占用槽位 = 重制侧 225–235。
5. **判定顺序**：`cursor > target > attack > move > blocked > walkable > nothing`。
   ⚠️ **2026-10-24**：`target > move` 这条**与实机相反**（G 流对拍出现 30 处
   「原版青 `hatch` / 重制绿 `hatch_shift`」）⇒ 优先级**待原版目标选择阶段实机帧定论**。
   ⇒ ~~「多画 310–420 格」的根因是重制侧把整张地图都铺了覆盖层~~
   ⭐ **该口径已被 G 流证伪**（拿地图空间缓冲去减屏幕空间图层）；
   换算到 16×16 逻辑格后实为**多画 42 格 / 缺 24 格**。
   「缺画」的根因仍成立：`edge`（格线）、`solid`（受阻）、`hatch`（可达）三类没按原版画/没画对。
6. **门禁**：用 §7.1 的四条 sha256 对 2048 B 的 BG2 tilemap 做逐字节比对；
   四个时刻在本机都可用 `capture_original.py` 重新抓出来。
