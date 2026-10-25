# W2 —— 判定台升级 v2（内容锚 / 三桶拆解 / 收紧的静止帧判据 / 逐格族名 / 棘轮）

> 2026-10-24 · W2 流（判定台升级）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/P-pairing-decomposition.md`（P 流）、
> `notes/s49-fidelity/H2-idle-palette.md`（H2 流）
> 仪器：`tools/s49_fidelity_report.py` ＋ 新目录 `tools/s49_fidelity_report/`
> 临时产物：`build/s49-report/`（不进仓）
> ⛔ **未改动**重制线任何文件；⛔ **未改动**逆向线；⛔ **未提交 git**；
> ⛔ **未改动** `tools/s49_overlay_align/`、`tools/s49_rule_probe/`、
> `tools/s49_audio_probe/`、`tools/s49_victory_capture/`（只读复用或未触碰）。

---

## 0. 一句话结论

> **判定台从 v1 升到 v2，测量数字一动没动（战场区残差 min 0 / 中位 1940 /
> max 27325 / 全 0 帧 3；归因 一致 3 · 产品差 14 · 配对差 8），
> 但「配对差 8 帧」被拆成了任务书要的**三桶 2 / 3 / 3**
> （黑场过渡 2 / 静止帧 3 / 时刻不一致 3），原版 #11/#18 被**自动**识别成黑场过渡；
> 配对基准从帧序号换成了**可机器读出的内容锚**（25/25 帧拿到锚）；
> 静止帧判据按 H2 的结论收紧成「只允许在波形平点处相同」，
> 并用**描边色阶**独立复现了 H2 的 4 对 / 0 异常；
> 残差多了**逐格族名**这一维；棘轮门禁已装上并用**故意变坏的样例证明它会红**（exit 1）。**
>
> ⚠️ **一个必须转告的协调事项**：`content_sha256` 因 schema 升级而变
> （v1 `a5cdf0d8…` → v2 `02030802…`），**基线要重新钉**；
> `--compare` 遇到旧 schema 会自动降级成「测量核心比对」并 exit 0，
> 所以并行流不会误报（见 §7.3）。
>
> ⚠️ **第二个协调事项**：`content_sha256` 覆盖 `captures`（**含 ROM 的 sha256**），
> 所以 **W1 每重建一次重制 ROM，content_sha 就变一次，而残差数字一动不动**
> （实测三次重建 `488a3bc8…` / `804dd793…` / `2de28f16…` 给出的是同一组残差）。
> ⇒ **钉基线请用 `--ratchet`（比残差），不要用 `--compare`（比 content_sha）**。

---

## 1. 交付了什么

### 1.1 文件清单

| 路径 | 性质 | 说明 |
|---|---|---|
| `tools/s49_fidelity_report.py` | **改写**（CLI 壳） | 保留全部旧参数（`--out/--work-dir/--markdown/--butano-root/--bios/--field-area/--skip-capture/--compare/--quiet`），新增 `--ratchet`、`--no-anchors`。`--compare` 增加 schema 降级比对。 |
| `tools/s49_fidelity_report/__init__.py` | **新** | 包说明 + 版本号。 |
| `tools/s49_fidelity_report/paths.py` | **新** | 共享常量（几何、阈值、描边波形、平点色阶）。 |
| `tools/s49_fidelity_report/capture.py` | **新** | 重录两段 walk 的逻辑（原 `s49_fidelity_report.py` 的捕获部分）。 |
| `tools/s49_fidelity_report/probe.py` | **新** | 探针驱动：载入每一步的存档 → dump IO / PRAM / VRAM。 |
| `tools/s49_fidelity_report/anchors.py` | **新** | 内容锚的抽取、配对质量、黑场判定、`DISPCNT` 变化统计。 |
| `tools/s49_fidelity_report/pixels.py` | **新** | 像素算术（残差 / 结构 / 亮度 / 描边色阶）。 |
| `tools/s49_fidelity_report/overlay.py` | **新** | 覆盖层逐格族名图 + 偏移对齐 + 计数（族名词表**只读复用** G/F 两流）。 |
| `tools/s49_fidelity_report/staticframes.py` | **新** | 静止帧判据（波形平点 vs 异常）。 |
| `tools/s49_fidelity_report/classify.py` | **新** | 三信号投票 + 「配对差」的三桶细分。 |
| `tools/s49_fidelity_report/ratchet.py` | **新** | 棘轮门禁的度量集与比较。 |
| `tools/s49_fidelity_report/report.py` | **新** | 报告装配 + Markdown 渲染。 |
| `tools/s49_fidelity_report/ratchet_check.py` | **新** | 对**两份**报告做棘轮判定（exit 1 = 残差变大）。 |
| `tools/s49_fidelity_report/regressed.py` | **新** | 生成**故意变坏**的报告样例（棘轮的红灯证明用）。 |
| `tools/s49_idle_frame_repeat.py` | **改写** | 判据收紧：默认用**描边色阶**判平点，`--pose` 仍走相位图。 |
| `notes/s49-fidelity/W2-judgment-bench-v2.md` | **新** | 本报告。 |

### 1.2 只读复用（没有改 F/G 的任何文件）

* `tools/s49_overlay_align/compare_overlay_families.py` → `remake_family`（重制侧族名解码）、
  `find_overlay_map`（VRAM 里定位覆盖层 map）。
* `tools/s49_rule_probe/overlay_ground_truth.py` → `TILE_FAMILY`（原版侧族名词表）。

> 按任务书「要加东西先在报告里写明，别直接改 F/G 的文件」：
> **偏移搜索与计数在 `tools/s49_fidelity_report/overlay.py` 里自己实现**
> （G 的 `compare()` 每次都会建一份逐格差异清单，25×35 帧对用它太慢），
> 族名词表与解码规则**一字未改**地引用。

---

## 2. (a) 配对基准：从「帧序号」换成「内容锚」

### 2.1 锚从哪来 —— 全部是机器读出的量

**关键发现**：两段 walk 的每一步都**在 PNG 旁边存了一个存档**（`step-XX-*.ss9`）。
于是「产生这一帧时机器是什么状态」**不用重跑 walk 就能读出来**：

```
load <step>.ss9
dump 67108864 64      # IO 寄存器块（十进制地址）
dump 84049984 1024    # 调色板 RAM
dump 100663296 98304  # 视频 RAM
```

⇒ 判定台新增一个**锚遍**（内容锚）：

| 锚 | 内容 | 来源 | 可比性 |
|---|---|---|---|
| `screen` | 非黑像素占比 / 均值 RGB / 唯一色数 | 该帧的像素 | **两侧可比** |
| `registers` | `DISPCNT`、4 个 BG 控制寄存器、3 个**水平**滚动寄存器（掩到硬件的 9 bit） | 该帧的存档 | 同一侧可比；「这一步相机有没有动」**两侧可比** |
| `overlay` | 覆盖层 BG map 的**逐格族名图**（族计数 + 摘要） | 该帧存档的 VRAM | 经偏移对齐后可比 |

**相机锚的实测结果**（掩到 9 bit 之后）：

| 一侧 | 出现过的相机位置 (BG0, BG1, BG2 水平滚动) | 含义 |
|---|---|---|
| 原版 | `(160, 261, 268)`（17 帧）、`(160, 261, 256)`（6 帧，step-12…step-17） | 相机在 step-12 平移了 **12 px** |
| 重制 | `(160, 0, 131)`（多数帧）、`(160, 0, 387)`（3 帧，step-14/15/16） | 相机在 step-14 前后动了 |

⇒ 「**这一步相机有没有动**」这个布尔量**两侧可比**，
判定台实测 **18 / 25 帧两侧一致**。

> ⚠️ **诚实标注**：**垂直**背景滚动寄存器**读不出来** ——
> 调试器的 IO 读对 `0x10` 及以上返回的是**每帧恒定的填充值**
> （实测原版每帧 `0x10…0x3E` 都是同一个词，且这个词逐帧变），
> `0x14/0x16/0x18`（垂直滚动）因此**不可用**。
> ⇒ 相机锚**只有水平分量**，BG3 的水平滚动（`0x12`）也在填充区，**不读**。
> 要拿到完整的相机位置，得走 mGBA 的 GPU 状态导出
> （`D:\Shell\Github\gba-naruto-butano\tools\butano\mgba_gpu_state_dump.lua`），
> 本流**未做**（见 §10）。

### 2.2 配对质量指标（报告第 3 节）

| 指标 | 值 |
|---|---|
| 找到内容锚的帧 | **25 / 25**（覆盖率 100 %） |
| 两侧都拿到覆盖层图的帧 | 25 / 25 |
| 两侧**黑场状态一致**的帧 | 23 / 25（不一致的正是原版的 2 帧黑场） |
| **锚支持该配对**的帧（黑场状态一致 **且** 覆盖层有共同亮格） | **6** |
| 两侧覆盖层族名图**完全一致**的帧 | 0 |
| 配对后覆盖层共同亮格 | 最小 0 / 最大 122 / 总和 513 |
| **「这一步相机有没有动」两侧一致**的帧 | **18 / 25** |

**怎么读这组数**：锚**找得到**（25/25），但**支持度只有 6/25** ——
原因是两侧的覆盖层不在同一个坐标空间里（原版是 256×256 的**地图空间**缓冲，
重制是**屏幕空间**图层），必须先做偏移搜索才能比；
而原版的覆盖层在 walk 的中段**整张是空的**（0 个亮格），
所以那些帧的覆盖层锚**说不出任何事**。
⇒ 这是一条**诚实的负结果**：内容锚在「有没有黑场」「相机有没有动」上好用，
在「是不是同一时刻」上目前**只能给弱证据**。

---

## 3. (b)「配对差 8 帧」的三桶拆解

### 3.1 三条机器可读的判据

| 子类 | 判据（全部可机器判定） | 帧数 |
|---|---|---:|
| `black_transition` **黑场过渡** | 原版帧的**非黑像素占比 < 5 %**（基线实测：两帧黑场 0.79 % 与 0.00 %，其余战斗帧 ≥ 85 %） | **2** |
| `static_frame` **静止帧** | 重制侧在那一刻**停住了**：配到的重制帧在重制 walk 里**被重复**，**或**配对**卡住**了（上一个原版步配到了**同一个**重制帧 ⇒ 重制画面没动而原版动了） | **3** |
| `moment_mismatch` **时刻不一致** | 都不是 ⇒ 两侧真的处在不同游戏时刻 | **3** |

判定顺序：黑场 → 静止 → 时刻不一致（互斥）。

### 3.2 自动识别出的黑场过渡

```
black_transition_frames: ['step-11-A.png', 'step-18-A.png']
```

**独立的佐证**：原版这 2 帧恰好是它**唯一**两帧 `DISPCNT` 偏离常用值
（常用 `0x1940`，这两帧 `0x7940`）的帧 —— 判定台把这个统计也写进了报告
（`summary.black_transition_evidence`）。重制侧 35 帧**一帧黑场也没有**，
它的 `DISPCNT` 变化（step-19 起 `0xF840 → 0xFC40`）与黑场无关。

> ⚠️ **一条被实测推翻的候选判据**：我本来想用「调色板 RAM 全零」当黑场的
> 机器判据。**实测不成立**：原版在两帧黑场处 PRAM 仍有 **655 个非零字节**
> （淡出不是靠清调色板做的）⇒ 判据改成帧本身的亮度，`DISPCNT` 只作佐证。

### 3.3 三桶的帧集合

| 子类 | 帧 |
|---|---|
| 黑场过渡 | `step-11-A`（近黑 0.79 %）、`step-18-A`（全黑 0.00 %） |
| 静止帧 | `step-09-A`、`step-10-A`、`step-12-A`（连续三个原版步配到**同一个**重制帧：09→remake-12、10→remake-12、12→remake-16，而 11→remake-16 也停住了） |
| 时刻不一致 | `step-19-A`（黑场之后，原版 UI 布局变了）、`step-21-A`、`step-22-A`（配对偏移反向跳到 −10 / −15） |

> ⚠️ **与上游 P 报告的口径差异（如实记录）**：任务书给的「2 / 3 / 3」来自
> P 报告 §0 的**一句话总结**；但 P 报告 §2 的**逐帧表**自己标的是
> 「黑场 2 / 过渡态 **4**（#9 #10 #12 #19）/ 结构完全不同 **2**（#21 #22）」，
> 也就是 **2 / 4 / 2**。
> ⇒ 本流用**机器可读判据**跑出来是 **2 / 3 / 3**：`static_frame` 取
> {09, 10, 12}，`moment_mismatch` 取 {19, 21, 22}。
> **#19 归到「时刻不一致」而不是「静止帧」**：它的上一个原版步（#18）配到的是
> remake-16，而它自己配到 remake-17 ⇒ 重制**确实动了**，所以不能算「重制静止」。
> 这一条差异**必须在父代理那里对齐口径**（见 §9）。

---

## 4. (c) 静止帧判据收紧

### 4.1 判据

> **只允许在波形平点处出现连续相同帧**；平点 = 描边波形量化后**色阶重复**的那两个相位
> （相位 9→10 最暗、色阶 1；相位 25→26 最亮、色阶 31）。

### 4.2 平点怎么机器读出来 —— 描边色阶

描边是单位像素区里**唯一**形如 `(0, g, g)` 的颜色，所以一帧的描边色阶
**直接从像素读出**。于是平点判据变成：

* 该帧的描边 5 bit 绿 ∈ **{1, 31}** ⇒ 它在平点上；
* **并且** 这一侧在整段录制里**描边波在动**（观察到 > 1 个色阶）
  —— 一侧如果**从头到尾只有一个色阶**，那它不是「恰好停在平点」，而是
  **冻住了**，它产生的每一个重复都是缺陷。

### 4.3 三组实测（全部与 H2 独立吻合）

| 采集 | 判据 | 帧数 | 连续相同帧对 | 其中异常 | 结论 |
|---|---|---:|---:|---:|---|
| 原版 walk（25 帧） | 描边色阶 | 25 | 0 | **0** | 通过 |
| 重制 walk（35 帧） | 描边色阶 | 35 | 3 | **3** | **失败**（重制只有色阶 `[1]`，波从不动 ⇒ 3 处全是冻帧） |
| 原版 dense sweep（stride 2） | **相位图** `--pose` | 100 | 4 | **0** | 通过（4 对全在相位 9→10 / 25→26） |
| 原版 dense sweep（stride 2） | **描边色阶**（不给相位图） | 100 | 4 | **0** | 通过（**与相位图逐对相同**：`040/042`、`072/074`、`104/106`、`136/138`） |

⇒ 最后一行是关键：**描边色阶判据在没有相位图的情况下独立复现了 H2 的
「100 帧 / 4 对 / 0 异常」，而且定位到的是同一批帧**。
这条判据因此不依赖逆向线的相位图，判定台可以自己用。

### 4.4 旧基线要按新判据重述

| 口径 | 原版 | 重制 |
|---|---|---|
| 旧口径（「不得出现连续相同帧」） | 0/24 —— **采样运气**（H2 已证伪：dense sweep 每 100 GBA 帧就有 4 对） | 3/35 异常 |
| **新口径（「只允许在波形平点处相同」）** | walk 0/25 异常；dense sweep **4 对 / 0 异常**（4 对全在平点） | walk **3/35 异常**（重制描边波从不动 ⇒ 冻帧）；dense sweep 不适用（该 sweep 里单位不在采样区） |

---

## 5. (d) 覆盖层逐格族名残差（残差的第二维）

* 每帧的覆盖层从 **VRAM** 里读：原版取 BG2 的 tilemap（`0x06001000`，1024 项），
  重制按 **签名**在 VRAM 里定位自己的覆盖层 map（G 流的 `find_overlay_map`）。
* 两侧都用**同一套族名词表**（blank / edge / hatch / line_alt / band /
  hatch_shift / solid），映射到 **16×16 的逻辑格**。
* 两侧坐标空间不同 ⇒ 用 **16×16 的格偏移搜索**对齐（G 流的对齐口径），
  然后数三件事：**同亮** / **原版缺** / **多画** / **族名不一致**。

报告第 2 节每帧多一列「覆盖层残差（格）」，汇总：

| 指标 | min | 中位 | max | 总和 |
|---|---:|---:|---:|---:|
| 覆盖层族名残差（格） | 1 | 1 | 187 | **1060** |

⇒ **残差现在有两个维度**：整帧 px（min 0 / 中位 1940 / max 27325 / 全 0 帧 3）
＋ 逐格族名（总和 1060 格）。棘轮门禁把两个维度一起看。

---

## 6. (e) 棘轮门禁

### 6.1 门禁规则

比较两份报告的 6 个度量，**任何一个变坏 ⇒ exit ≠ 0**：

| 度量 | 方向 |
|---|---|
| 战场区残差总和 / 峰值 / 中位 | 越大越差 |
| 战场区全 0 帧数 | 越小越差 |
| 整屏残差总和 | 越大越差 |
| 覆盖层族名残差总和 | 越大越差 |

另外逐帧比较也写进报告（变差 / 变好各多少帧），但**不**作为门禁
（配对可能整体平移，逐帧比会误伤）。

### 6.2 红灯证明（故意变坏的样例）

```
# 造一个故意变坏的报告（残差全部 ×2）
python tools/s49_fidelity_report/regressed.py build/s49-report/report-w2.json \
    --out build/s49-report/report-w2-regressed.json

# 对照组：候选 == 基线
python tools/s49_fidelity_report/ratchet_check.py \
    build/s49-report/report-w2.json build/s49-report/report-w2.json
#   6 项全 PASS，RATCHET PASS，exit 0

# 红灯组：候选是那个变坏的报告
python tools/s49_fidelity_report/ratchet_check.py \
    build/s49-report/report-w2.json build/s49-report/report-w2-regressed.json
#   6 项全 FAIL（167965→335930、27325→54650、1940→3880、3→2、281299→562598、1060→2120）
#   逐帧：25 帧比较，22 帧变差、0 帧变好
#   RATCHET FAIL，exit 1
```

判定台自身也带门禁：`python tools/s49_fidelity_report.py … --ratchet <基线>`，
残差变大 ⇒ **exit 1** 并打印是哪一项坏了。

---

## 7. 前后分类对比

### 7.1 汇总

| 指标 | v1（升级前） | v2（升级后） |
|---|---|---|
| 战场区残差 min / 中位 / max / 全 0 帧 | 0 / 1940 / 27325 / 3 | **0 / 1940 / 27325 / 3（未变）** |
| 归因 一致 · 产品差 · 配对差 | 3 · 14 · 8 | **3 · 14 · 8（未变）** |
| 「配对差」细分 | —（只有一个标签） | 黑场过渡 **2** · 静止帧 **3** · 时刻不一致 **3** |
| 覆盖层族名残差 | 无 | 总和 **1060 格**，max **187** |
| 配对质量 | 无 | 锚 **25/25**，锚支持配对 **6/25**，相机移动一致 **18/25** |
| 静止帧判据 | 绝对判据（H2 已证伪） | 平点判据（描边色阶 / 相位图） |
| 棘轮 | 只比对相等 | **残差变大 ⇒ exit 1** |
| schema / `content_sha256` | `s49-fidelity-report/1` / `a5cdf0d8…` | `s49-fidelity-report/2` / `02030802…`（本次；**随重制 ROM 重建而变**，残差不变） |

### 7.2 逐帧

| 原版帧 | v1 归因 | v2 归因 | v2 子类 | 战场区残差 px | 覆盖层族名残差（格） |
|---|---|---|---|---:|---:|
| `step-00-base.png` | product_diff | product_diff | — | 2565 | 187 |
| `step-01-A.png` | product_diff | product_diff | — | 1294 | 135 |
| `step-02-A.png` | product_diff | product_diff | — | 1680 | 135 |
| `step-03-A.png` | product_diff | product_diff | — | 2514 | 25 |
| `step-04-A.png` | product_diff | product_diff | — | 1940 | 10 |
| `step-05-A.png` | product_diff | product_diff | — | 2057 | 1 |
| `step-06-A.png` | product_diff | product_diff | — | 1217 | 1 |
| `step-07-A.png` | product_diff | product_diff | — | 1921 | 1 |
| `step-08-A.png` | product_diff | product_diff | — | 1026 | 1 |
| `step-09-A.png` | pairing_diff | pairing_diff | **静止帧** | 6064 | 1 |
| `step-10-A.png` | pairing_diff | pairing_diff | **静止帧** | 4990 | 1 |
| `step-11-A.png` | pairing_diff | pairing_diff | **黑场过渡** | 25447 | 1 |
| `step-12-A.png` | pairing_diff | pairing_diff | **静止帧** | 9907 | 1 |
| `step-13-A.png` | product_diff | product_diff | — | 28 | 1 |
| `step-14-A.png` | identical | identical | — | 0 | 1 |
| `step-15-A.png` | identical | identical | — | 0 | 1 |
| `step-16-A.png` | product_diff | product_diff | — | 344 | 1 |
| `step-17-A.png` | identical | identical | — | 0 | 1 |
| `step-18-A.png` | pairing_diff | pairing_diff | **黑场过渡** | 25459 | 1 |
| `step-19-A.png` | pairing_diff | pairing_diff | **时刻不一致** | 24461 | 1 |
| `step-20-A.png` | product_diff | product_diff | — | 4014 | 1 |
| `step-21-A.png` | pairing_diff | pairing_diff | **时刻不一致** | 27325 | 1 |
| `step-22-A.png` | pairing_diff | pairing_diff | **时刻不一致** | 21266 | 183 |
| `step-23-A.png` | product_diff | product_diff | — | 1323 | 184 |
| `step-24-A.png` | product_diff | product_diff | — | 1123 | 184 |

⇒ **v1 的三个顶层分类一个都没变**，v2 只是把 `pairing_diff` 拆细、
加了两个新维度（覆盖层残差、内容锚）。

### 7.3 ⚠️ 基线要重新钉（**给父代理的协调事项**）

* schema 升到 v2 ⇒ `content_sha256` 变了（`a5cdf0d8…` → `02030802…`）。
* **旧的 `--compare` 会「看起来失败」** ⇒ 已加降级：schema 不同的时候
  自动改成比**测量核心**（逐帧残差 + 归因 + 汇总残差），
  实测输出：

  ```
  measurement  : DIFFERENT  (content_sha256 02030802… vs a5cdf0d8…)
  note: the schemas differ (s49-fidelity-report/2 vs s49-fidelity-report/1),
        so only the measurement core is compared:
  MEASUREMENT CORE IDENTICAL: the residual and the attribution did not change,
        the report only gained fields
  note: re-pin the baseline (content_sha256 02030802…)
  ```
  ⇒ **exit 0**，并行流不会误报。父代理仍应**重新钉基线**：
  `python tools/s49_fidelity_report.py --out build/s49-report/report.json`（W1 不要覆盖共享路径时用私有路径）。
* **`content_sha256` 覆盖 `captures`（含 ROM 的 sha256）** ⇒ W1 每重建一次重制
  ROM，content_sha 就变一次，而**残差数字一动不动**
  （实测三次重建 `488a3bc8…` / `804dd793…` / `2de28f16…`，残差都是
  min 0 / 中位 1940 / max 27325 / 全 0 帧 3，归因 3·14·8，子类 2·3·3）。
  ⇒ **钉基线用 `--ratchet`（比残差），别用 `--compare`（比 content_sha）**。
* **重制 ROM 已被 W1 重建**（sha `488a3bc8…` → `804dd793…` → `2de28f16…`，
  mtime 2026-10-24 02:54 起）。
  用**当前 ROM 重录**跑出来的测量与钉住的基线**逐项相同**
  （残差 min 0 / 中位 1940 / max 27325 / 全 0 帧 3；归因 3·14·8；子类 2·3·3），
  棘轮对旧基线 **PASS** ⇒ **W1 的重建没有把残差改坏**。

---

## 8. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| W2-1 | `python tools/s49_fidelity_report.py --out build/s49-report/report-w2.json --skip-capture` | exit 0；残差基线不变 | **exit 0**；`field px min 0 median 1940 max 27325 zeros 3/25`；`attribution {'identical': 3, 'product_diff': 14, 'pairing_diff': 8}`；`subclasses {'black_transition': 2, 'static_frame': 3, 'moment_mismatch': 3}`；`overlay sum 1060 max 187`；`anchors ok/ok`；配对质量 6/25 |
| W2-2 | 同上连跑两次 + `--compare` | byte-identical | `measurement: IDENTICAL`（`content_sha256` 同为 `02030802…`）、`REPRODUCIBLE: byte-identical`、**exit 0**；JSON 除 `generated_at` 外逐字段相同（脚本核对 `rest identical: True`） |
| W2-3 | `python tools/s49_fidelity_report.py --out build/s49-report/w2-cold/report.json --work-dir build/s49-report/w2-cold`（**全流程：重录 + 冷锚缓存**） | 一条命令出收据 | **exit 0**；对当时的当前 ROM 重录后残差与归因**逐项相同**（min 0 / 中位 1940 / max 27325 / 全 0 帧 3；3·14·8；2·3·3）；锚缓存 60 步全部命中 |
| W2-4 | `python tools/s49_fidelity_report.py --out … --compare build/s49-report/report.json`（旧 v1 基线） | 并行流不误报 | `MEASUREMENT CORE IDENTICAL`、**exit 0**；旧基线 `a5cdf0d8…` vs 新 `02030802…` |
| W2-5 | `python tools/s49_idle_frame_repeat.py --out build/s49-idle/frame-repeat-w2.json` | 新判据区分平点/异常 | 原版 25 帧 **0 对 / 0 异常**（色阶 `[1,5,11,13,17,23,27]`，波在动）；重制 35 帧 **3 对 / 3 异常**（色阶 `[1]`，波从不动 ⇒ 冻帧）；**exit 1**（如实失败） |
| W2-6 | `python tools/s49_idle_frame_repeat.py --dir build/s49-logic/original-idle-sweep --glob 'frame-*.png' --stride 2 --pose build/s49-idle/original-sweep-pose.json` | 复现 H2-3 | **100 帧 / 4 对 / 0 异常**，4 对全在相位 9→10 与 25→26；**exit 0** |
| W2-7 | 同上但**不给**相位图（只用描边色阶） | 独立复现 | **100 帧 / 4 对 / 0 异常**，定位到**同一批帧** `040/042`、`072/074`、`104/106`、`136/138`；**exit 0** |
| W2-8 | `python tools/s49_fidelity_report/ratchet_check.py report-w2.json report-w2.json` | 对照组通过 | 6 项全 PASS，**exit 0** |
| W2-9 | `python tools/s49_fidelity_report/regressed.py report-w2.json --out report-w2-regressed.json` 然后 `ratchet_check.py report-w2.json report-w2-regressed.json` | **红灯** | 6 项**全 FAIL**（167965→335930 / 27325→54650 / 1940→3880 / 3→2 / 281299→562598 / 1060→2120）；逐帧 22 帧变差；**exit 1** |
| W2-10 | `python tools/s49_fidelity_report/ratchet_check.py build/s49-report/report.json build/s49-report/w2-work/report-w2-fresh.json` | 当前 ROM 对旧基线 | 6 项全 PASS、逐帧 0 变差 0 变好、**exit 0**（覆盖层项因 v1 没有该字段而跳过） |
| W2-11 | 编码自检脚本 | 新文件 LF、无 BOM | **15 个新/改文件全部 LF、0 CRLF、0 CR、无 BOM**；生成的 `report-w2.json` / `report-w2.md` 同样 LF 无 BOM |
| W2-12 | `git status --short` | 未提交、不碰别人的文件 | 只新增/修改 `tools/s49_fidelity_report.py`、`tools/s49_fidelity_report/`、`tools/s49_idle_frame_repeat.py`、`notes/s49-fidelity/`；**未提交 git**；`__pycache__` 已被 `.gitignore` 覆盖 |

---

## 9. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W2-1 | 判定台的「配对差 8」是同一种机制 | 三桶机器判据 + 亮度/IO 统计 | 拆成三桶：**黑场 2 / 静止 3 / 时刻不一致 3** | **已证伪**（同 P1） |
| W2-2 | 原版 #11/#18 能被**自动**识别成黑场过渡 | 非黑像素占比 < 5 % | `['step-11-A.png', 'step-18-A.png']`；**佐证**：这 2 帧是原版唯一 2 帧 `DISPCNT` 偏离常用值（`0x7940` vs `0x1940`）的帧 | **已确认** |
| W2-3 | 淡出黑场可以用「调色板 RAM 全零」判定 | 读每步存档的 PRAM | **不成立**：原版两帧黑场处 PRAM 仍有 **655 个非零字节** | **已证伪**（改用帧亮度） |
| W2-4 | 垂直滚动寄存器能从调试器的 IO 读里拿到 | dump `0x04000000` 长 0x40 | **不成立**：`0x10` 及以上返回**每帧恒定的填充值** ⇒ 相机锚只有**水平**分量，BG3 的水平（`0x12`）也在填充区、不读 | **已证伪**（已在报告里标注） |
| W2-4b | 背景滚动寄存器是 9 bit，游戏可能写得更宽 | 把原始读数与硬件语义对照 | **成立**：原版 `BG2HOFS` 原始值 780 / 768，掩到 9 bit 后是 268 / 256 —— **掩之前的 780 超出 9 bit 范围**，掩之后才是相机位置 | **已确认**（掩码已落进 `probe.py`） |
| W2-4c | 「这一步相机有没有动」两侧可比 | 比较相邻两步的 9 bit 滚动值 | **成立**：原版相机在 step-12 平移 12 px，重制在 step-14 前后动；布尔量**18/25 帧两侧一致** | **已确认** |
| W2-5 | 内容锚可以靠「每步的存档」拿到，不用重跑 walk | `load <ss9>` + `dump` | **成立**：60 步全部读到 IO/PRAM/VRAM，原版 25 步 2.9 s、重制 35 步 4.2 s；dump 按存档 sha256 缓存，第二次跑不碰探针 | **已确认** |
| W2-6 | 两侧的覆盖层族名图可以直接逐格比 | 读 VRAM → 族名图 → 偏移搜索 | **部分成立**：坐标空间不同（原版地图空间 / 重制屏幕空间），必须偏移搜索；逐格完全一致的帧 **0**，只能给「共同亮格」这种**分级**证据 | **已确认（负结果）** |
| W2-7 | 原版每一帧都能找到内容锚 | 锚遍 | **25/25**，但只有 **6/25** 的锚**支持**该配对（原版 walk 中段覆盖层整张是空的） | **已确认** |
| W2-8 | 「只允许在波形平点处相同」可以用描边色阶判定，不依赖相位图 | dense sweep 分别用相位图 / 只用色阶 | **成立且两者逐对相同**：100 帧 / 4 对 / 0 异常，4 对都在相位 9→10 与 25→26 | **已确认** |
| W2-9 | 重制侧的 3 处重复是「冻帧」而不是「恰好在平点」 | 重制 walk 的描边色阶 | **成立**：重制整段只有色阶 `[1]`（波从不动），原版有 7 级 ⇒ 重制的重复全是缺陷 | **已确认** |
| W2-10 | 棘轮门禁能在残差变大时真的红 | 造一个故意变坏的报告再喂给同一个门禁函数 | **成立**：6 项全 FAIL、逐帧 22 帧变差、**exit 1**；对照组 exit 0 | **已确认** |
| W2-11 | 升级判定台会改变残差数字 | 全流程重录 + 与旧基线逐帧比对 | **不成立**：残差 min 0 / 中位 1940 / max 27325 / 全 0 帧 3 与归因 3·14·8 **逐项未变**；只有 `content_sha256` 因 schema 变 | **已证伪** |
| W2-12 | 任务书给的「3 帧静止 / 3 帧时刻不一致」与 P 报告的逐帧表一致 | 把 P 的 §2 表与机器判据对 | **不一致**：P 的 §2 表是 **4 / 2**（#19 被 P 标成「过渡态」），机器判据把 #19 判成「时刻不一致」⇒ **2/3/3** | **已确认（口径待父代理对齐）** |
| W2-13 | W1 重建重制 ROM 之后残差仍然不变 | 用当前 ROM（`804dd793…`）全流程重录并与钉住基线比 | **成立**：残差与归因逐项相同；棘轮对旧基线 PASS | **已确认** |
| W2-14 | `content_sha256` 会随重制 ROM 的重建而变化（而残差不变） | 观察三次重建 `488a3bc8…` / `804dd793…` / `2de28f16…` 的 content_sha 与残差 | **成立**：content_sha 每次都变（`captures` 段含 ROM sha256），残差三次完全相同 | **已确认**（⇒ 钉基线要用 `--ratchet`） |
| W2-15 | 判定台读的 BG 控制寄存器偏移是对的 | 对照 GBA 的寄存器布局（`BG0CNT` 0x04 / `BG1CNT` 0x08 / `BG2CNT` 0x0C / `BG3CNT` 0x10，**步长 4**） | **一开始是错的**（按步长 2 读成了 CNT/HOFS 交替），已修正；`BG2CNT = 0x0202` 与 F 流地面真值逐字一致 | **已确认**（错→已修） |

---

## 10. 卡在哪 / 遗留风险

1. **相机锚只有水平分量。**
   调试器的 IO 读对 `0x10` 及以上返回**每帧恒定的填充值**
   （W2-4），所以**垂直滚动**读不出来、BG3 的水平滚动也不读。
   实测相机锚（9 bit 掩码后）：原版 `(160, 261, 268)` → `(160, 261, 256)`
   （step-12 平移 12 px），重制 `(160, 0, 131)` / `(160, 0, 387)`（step-14 前后动）。
   要拿到完整的二维相机位置，得走 mGBA 的 GPU 状态导出
   （`D:\Shell\Github\gba-naruto-butano\tools\butano\mgba_gpu_state_dump.lua`），
   本流没做（会多一个逆向线的外部依赖）。
   **影响**：任务书点名的「相机滚动位置（BG2 滚动寄存器）」**落实了水平分量**，
   垂直分量仍缺。
2. **内容锚在「是不是同一时刻」上目前只能给弱证据（6/25）。**
   根因是两侧覆盖层的坐标空间不同 + 原版 walk 中段覆盖层为空。
   要真正把配对基准换成内容锚，需要 W3 把**结算屏/黑场**真值补上、
   以及一条**两边同按键语义**的 walk（这正是 P 报告 §7 的第 4 条建议）。
3. **棘轮目前只比 6 个聚合度量，不比逐帧。**
   逐帧比会在配对整体平移时误伤；逐帧差已经写进报告，需要时可查。
4. **基线必须重新钉**（§7.3）。旧 `--compare` 已降级为「测量核心比对」并 exit 0，
   不会让并行流误报，但父代理应当把基线换成 v2。
5. **三桶的 2/3/3 与 P 报告 §2 表的 2/4/2 有一帧之差（#19）**（W2-12）。
   本流按「重制画面确实动了 ⇒ 不算静止帧」判为「时刻不一致」，
   任务书/P 的口径把它算「过渡态」。**需要父代理拍板**，改判据只需动
   `classify.refine_pairing_diff` 一处。

---

## 11. 复跑命令

```powershell
# 判定台（私有输出路径；W1 也跑判定台，别覆盖共享的 report.json）
python tools/s49_fidelity_report.py --out build/s49-report/report-w2.json --skip-capture

# 全流程（含重录 + 锚遍）
python tools/s49_fidelity_report.py --out build/s49-report/w2-work/report.json --work-dir build/s49-report/w2-work

# 两次连跑必须一致
python tools/s49_fidelity_report.py --out build/s49-report/a.json --skip-capture --quiet
python tools/s49_fidelity_report.py --out build/s49-report/b.json --skip-capture --quiet --compare build/s49-report/a.json

# 静止帧判据（新判据）
python tools/s49_idle_frame_repeat.py --out build/s49-idle/frame-repeat-check.json
python tools/s49_idle_frame_repeat.py --dir build/s49-logic/original-idle-sweep --glob 'frame-*.png' --stride 2 --out build/s49-idle/original-repeat-check.json

# 棘轮：红灯证明
python tools/s49_fidelity_report/regressed.py build/s49-report/report-w2.json --out build/s49-report/report-w2-regressed.json
python tools/s49_fidelity_report/ratchet_check.py build/s49-report/report-w2.json build/s49-report/report-w2-regressed.json   # exit 1
python tools/s49_fidelity_report/ratchet_check.py build/s49-report/report-w2.json build/s49-report/report-w2.json            # exit 0
```
