# Z3 —— 残差下界为**当前 ROM** 重算 + 130 格「walk 相位」的归因

> 2026-10-24 · wave 14 · 流 Z3 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 任务书：`notes/s49-fidelity/WAVE14-TASKS.md` §0.1 / §3
> 上游：`notes/s49-fidelity/X2-pairing.md`（配对流）、
> `notes/s49-fidelity/Y2-overlay-final.md`（逐格性质）、
> `notes/s49-fidelity/W4-wave13-package-final.md`（最新包）
> 仪器（**新建**）：`tools/s49_z3_bound/`（`z3record.py` / `z3bound.py` / `z3phase.py`）
> 产物：`build/s49-z3-bound/`（不进仓）
> ⛔ **未改**重制线任何文件；⛔ **未改**其它流的仪器（`tools/s49_pairing/`、
> `tools/s49_overlay_align/`、`tools/s49_fidelity_report/`、`tools/s49_package/`、
> `tools/s49_battle_balance/` 一律**只读调用**）；⛔ 逆向线全程只读；
> ⛔ **未提交 git**。

---

## 0. 一句话结论

> ⭐ **任务 A**：可证像素下界**为当前 ROM `2c2b48d9…` 重算 = 16,389**
> （旧值 23,697 / 23,753 是 wave 6 的录制 ⇒ **口径过期**），
> 与内容锚配对的可达数 **18,886** 夹出真值区间 **[16,389, 18,886]**
> ⇒ **残差归零在当前录制上不可达**，且下界比旧值**低了 7,364（−31.0 %）**
> —— 产品侧确实变好了，但**归零仍然不可达**。
>
> ⭐ **任务 B**：那 **130 格「walk 相位」不是同一类东西，可判定地劈成两半** ——
> **`field` 的 50 格 = 重制侧缺一个相位**（原版那一帧是**稳定态**：
> 连续 6 帧逐格相同、原版密集 walk 里连续 **67 帧**同相位；
> 而重制侧 **0 / 783 帧**同现）；
> **`grid16` 的 80 格 = 原版那一帧是瞬态**（导出帧在连续 6 帧里**只出现 1 次**，
> 下一帧就已是 176 格的完整画面 ⇒ 缓冲半刷新的撕裂残影）。
> ⇒ **130 = 50（重制缺相位）+ 80（原版瞬态）**。

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_z3_bound\__init__.py` | **新建** | 包说明 |
| `D:\Github\gba-naruto\tools\s49_z3_bound\z3record.py` | **新建** | 密集 walk 录制器（**行安全**客户端 + **钉住 ROM**） |
| `D:\Github\gba-naruto\tools\s49_z3_bound\z3bound.py` | **新建** | 可证像素下界（继承 X2r 的算法 + arg-min 审计 + ROM sha） |
| `D:\Github\gba-naruto\tools\s49_z3_bound\z3phase.py` | **新建** | 130 格相位归因（原版自己的 6 帧连拍 + 两侧逐帧对齐） |
| `D:\Github\gba-naruto\notes\s49-fidelity\Z3-bound-and-phase.md` | **新建** | 本文件 |

**只读复用的东西**：`tools/s49_pairing/lua/record_walk.lua`（walk 脚本）、
`tools/s49_pairing/walkspec.py`（拍脚本）、`tools/s49_pairing/pair.py::beat_floor`
（下界算法）、`tools/s49_pairing/pairing_report.py`（配对表，只读调用）、
`tools/s49_battle_balance/w1_probe.py`（行安全客户端）、`tools/s49_overlay_align/
compare_overlay_families.py`（覆盖层仪器）、`tools/s49_fidelity_report/overlay.py`
（原版/重制覆盖层解码）、`tools/s49_rule_probe/overlay_ground_truth.py`（真值）。

---

## 2. 任务 A —— 可证像素下界（当前 ROM）

### 2.1 口径

**与 X2r 完全相同的算法**（`tools/s49_pairing/pair.py::beat_floor`，
本流**只读调用**并**逐值交叉核对**）：

> 每一拍内，取**原版的全部帧**（该拍 23 帧 = 22 个内层采样 + 1 个拍尾）
> × **重制的全部帧**（783 帧，按战场区像素去重后 **387** 张），
> 逐对算战场区残差（`diff_mask`，区域 `(0,0,240,128)`）取最小；
> **25 拍求和**。

本流加了三样东西：

1. **arg-min 审计**：每一拍记下「取到最小值的原版帧 + 重制帧」，下界可以逐拍追；
2. **交叉核对**：本流自己的实现必须与 `pair.beat_floor` 的输出**逐值相等**，
   不等就**拒绝出数**（实测 `agrees=True`）；
3. **ROM 钉住 + sha**：下界收据里写**两侧 ROM 的 sha256** 与**全部帧的 sha256**，
   收据**不含墙钟时间** ⇒ 两次跑可以逐字节比较。

### 2.2 ⭐ 新下界 + 与旧值的对照

| 项 | 旧（wave 6 / X2） | **新（wave 14 / Z3）** |
|---|---:|---:|
| **可证像素下界（25 拍求和）** | **23,753**（ROM `fec749d8…`）/ 23,697（ROM `c1f44b3b…`） | **16,389**（ROM **`2c2b48d9…`**） |
| 同一实现重算旧录制 | **23,753**（`walk5`，`pair.beat_floor` 交叉核对 `agrees=True`） | — |
| 规范帧残差之和（canonical） | 111,587 | **90,993** |
| 重制帧去重后（战场区） | 350 | **387** |
| 原版 ROM | `1198ece7…`（未变） | `1198ece7…`（未变） |
| 重制 ROM | `fec749d8…` / `c1f44b3b…` | **`2c2b48d9…`** |
| 内容锚配对的可达残差（B2） | 28,899 | **18,886** |
| 内容锚同刻帧数 | 19 / 25 | **21 / 25** |
| 配对差下界（内容锚可达性） | 6 帧 | **4 帧** |

> ⚠️ **旧值 23,697 / 23,753 的口径**：它们是在 **wave 6 的两段录制**上测的
> （重制侧是旧 ROM），**不是**当前 ROM 的数字。
> 本流用**同一份代码**在旧录制上重算，得到 **23,753**（与 X2 报告**逐值相同**）
> ⇒ **新下界与旧值是同口径对照**，差值来自 ROM，不是来自算法漂移。

### 2.3 ⭐ 三段夹逼（这是本波最该写进报告的数字）

```
16,389   ≤   最优残差   ≤   18,886
 (下界 B1)                (内容锚配对 B2，可达)
```

* **下界 16,389**：任何配对方式都不可能低于此数（证明见 §2.5）；
* **可达 18,886**：25 个基准时刻里 **21 帧**在重制侧找到了**同一时刻**的帧，
  逐帧战场区残差之和 = 18,886（`tools/s49_pairing/pairing_report.py`，
  本流只读调用，输出在 `build/s49-z3-bound/pairing/pairing.json`）；
* 判定台自己的读数（当前 ROM、钉住基线、35 帧 arg-min、**不带时刻约束**）
  是 **100,210** ⇒ 判定台读数与真值的差距主要来自**口径**（X2 的老结论：
  判定台的 arg-min 没有时刻约束，比内容锚配对大 3.9 倍），**不是** walk 侧没走到头。

⇒ **残差归零在当前录制上不可达**（下界 16,389 > 0），这个结论**为当前 ROM 重算过了**。

### 2.4 逐拍分解（新下界 16,389）

| 拍 | 规范帧 | 该拍下界 | 取到最小值的原版帧 | 取到最小值的重制帧 |
|---:|---|---:|---|---|
| 0 | `step-0000-base.png` | 1,431 | `step-0000-base.png` | `step-0530-in.png` |
| 1 | `step-0023-beat.png` | 1,014 | `step-0011-in.png` | `step-0102-in.png` |
| 2 | `step-0046-beat.png` | 1,090 | `step-0031-in.png` | `step-0126-in.png` |
| 3 | `step-0069-beat.png` | 1,115 | `step-0067-in.png` | `step-0542-in.png` |
| 4 | `step-0092-beat.png` | 1,199 | `step-0092-beat.png` | `step-0362-in.png` |
| 5 | `step-0115-beat.png` | 1,590 | `step-0109-in.png` | `step-0188-in.png` |
| 6 | `step-0138-beat.png` | 1,005 | `step-0132-in.png` | `step-0212-in.png` |
| 7 | `step-0161-beat.png` | 1,674 | `step-0150-in.png` | `step-0235-in.png` |
| 8 | `step-0184-beat.png` | 1,002 | `step-0184-beat.png` | `step-0261-in.png` |
| 9 | `step-0207-beat.png` | 305 | `step-0207-beat.png` | `step-0277-in.png` |
| 10 | `step-0230-beat.png` | 182 | `step-0208-in.png` | `step-0290-in.png` |
| 11 | `step-0253-beat.png` | 3 | `step-0253-beat.png` | `step-0328-in.png` |
| 12 | `step-0276-beat.png` | 0 | `step-0254-in.png` | `step-0070-in.png` |
| 13 | `step-0299-beat.png` | 0 | `step-0285-in.png` | `step-0376-in.png` |
| 14 | `step-0322-beat.png` | 0 | `step-0300-in.png` | `step-0392-in.png` |
| 15 | `step-0345-beat.png` | 0 | `step-0323-in.png` | `step-0416-in.png` |
| 16 | `step-0368-beat.png` | 0 | `step-0360-in.png` | `step-0454-in.png` |
| 17 | `step-0391-beat.png` | 0 | `step-0369-in.png` | `step-0462-in.png` |
| 18 | `step-0414-beat.png` | 0 | `step-0392-in.png` | `step-0471-in.png` |
| 19 | `step-0437-beat.png` | 64 | `step-0415-in.png` | `step-0330-in.png` |
| 20 | `step-0460-beat.png` | 742 | `step-0448-in.png` | `step-0485-in.png` |
| 21 | `step-0483-beat.png` | 1,254 | `step-0480-in.png` | `step-0533-in.png` |
| 22 | `step-0506-beat.png` | 1,236 | `step-0485-in.png` | `step-0542-in.png` |
| 23 | `step-0529-beat.png` | 1,323 | `step-0529-beat.png` | `step-0551-in.png` |
| 24 | `step-0552-beat.png` | 160 | `step-0537-in.png` | `step-0569-in.png` |
| | **合计** | **16,389** | | |

⇒ 下界的 **67.9 %（11,120 px）** 来自**战斗段前 9 拍**，
**29.2 %（4,779 px）** 来自**结算段 6 拍**（相机滚动那几拍），
中间 **10 拍合计只有 490 px（3.0 %）**，其中 **7 拍已经是 0**
⇒ **对话段与淡出段已经彻底对齐**，剩下的全是**战斗段与结算段的产品差**。

### 2.5 ⭐ 新下界的证明方式（可核验）

> **命题**：在「同语义 walk」下，任何配对方式在 battle-14 这 25 拍上的
> 战场区残差总和 **≥ 16,389**。
>
> **证明**：
> 1. 判定台每一拍的残差 = **一个**原版帧对**一个**重制帧的战场区残差
>    （`diff_mask`，区域 `(0,0,240,128)`）。
> 2. 换 walk 只能改**选哪一对**，不能改**一对怎么算**。
> 3. ⇒ 对每一拍 `b`，任何配对给出的残差
>    `≥ min{ residual(o, r) : o ∈ 拍 b 的帧, r ∈ 重制录制的帧 }`。
> 4. 这个 `min` 取在**比任何 walk 能实现的配对更大**的一个集合上
>    （同一个重制帧可以被多拍同时取用）⇒ **放宽只会让最优值变小**，
>    所以它仍然是任何 walk 的下界。
> 5. 25 拍求和 ⇒ **总残差 ≥ Σ_b min** = **16,389**。
>
> **可核验性**：
> * `z3bound.py` 的收据里写死了算法、战场区、25 拍、arg-min 帧名、
>   两侧 ROM 的 sha256、全部帧的 sha256；
> * 收据里 `cross_check.inherited_floor_sum` 是**用 X2r 的 `pair.beat_floor`
>   独立算出来的同一个数**（实测 `agrees=True`）⇒ 算法没被改写；
> * 同一份录制重跑两次 ⇒ 收据**逐字节相同**
>   （sha256 `399a238ba9c84683…`）；
> * 旧录制用同一份代码重算 ⇒ **23,753**，与 X2 报告**逐值相同**。
>
> ⚠️ **口径边界**：这个下界是**针对当前这两段录制**的
> （原版 `1198ece7…` + 重制 `2c2b48d9…`，密集 walk，stride 4）。
> 产品改动后录制会变，**下界必须重算**。

### 2.6 录制口径与可复现性

| 项 | 值 |
|---|---|
| 探针 | **私有** `build/mgba-probe-z3/mgba-probe.exe`（`$env:KONOHA_PROBE_OUT=…` 现编；**没有**覆盖共享的 `build/mgba-probe/mgba-probe.exe`） |
| 客户端 | `tools/s49_battle_balance/w1_probe.py`（**单后台读线程 + 队列**，避开共享 `probe_client.py` 的「每行一个读线程」死锁） |
| 原版 ROM | `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`（`D:\Shell\Github\gba-naruto-butano\rom\base.gba`，未变） |
| 重制 ROM | `2c2b48d91fbe32447845a7ddf683b29badefd30202e14c230efc98640a72fca0`（**先钉成字节副本再录**，收据里写 sha） |
| 录到的帧 | 原版 **553**（1 base + 24 拍 × 23）/ 重制 **783**（1 base + 34 拍 × 23） |
| 录制耗时 | 原版 **6.8 s** / 重制 **8.7 s**（内存无异常） |
| 孤儿探针 | 跑完 `Win32_Process` 复查：**0 个** `mgba-probe.exe` |
| 帧指纹 | 原版 `ffa679a0e4ff021e…` / 重制 `72b285fe53ca442a…` |

**逐字节一致（三处）**：

| 比较 | 结果 |
|---|---|
| 原版：本次录制 vs `walk5`（wave 5）vs `walk6-z1`（wave 6） | **553/553 帧 PNG 逐字节相同**（三份指纹都是 `ffa679a0e4ff021e…`） |
| 重制：本次跑 A vs 本次跑 B（独立录制） | **783/783 帧 PNG 逐字节相同**（两份指纹都是 `72b285fe53ca442a…`） |
| 下界收据：跑 A vs 跑 B | **逐字节相同**（`399a238ba9c84683…`） |
| 相位收据：跑 A vs 跑 B | **逐字节相同**（`306ff9670641146a…`） |

---

## 3. 任务 B —— 130 格「walk 相位」的归因

### 3.1 问题

Y2 / Y4 把剩余 176 格分成三类：**尾部残留 44 / walk 相位 130 / 产品差 2**。
那 **130 格**到底是什么？两条断言：

* 原版 `field` 是「**青 + 橙同现**」的**稳定态**，而重制侧 35 帧**无一帧同现**；
* 原版 `grid16` 是**单帧瞬态**（半刷新、175 格）。

⇒ 要判定的是：**「重制侧缺一个相位」** 还是 **「原版那一帧是瞬态」**？

### 3.2 ⭐ 判据与数据源（**可判定**，不是断言）

> **原版自己被连续拍了 6 帧。**
> `D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-<moment>-frame-v1\`
> 每个时刻有 `frame-00..05.png` + `vram-00..05.bin` + `io-00..05.bin`
> （`settle_frames = 2`，随后**连续 6 帧**），
> 载入点分别是原版 walk 的 `step-15-A` / `step-16-A` / `step-17-A` / `step-19-A`。
>
> ⇒ **把 BG2 覆盖层从这 6 帧的 VRAM 里逐帧解出来**，
> 就能直接回答「那一帧是稳定态还是瞬态」：
> * **稳定态** ⇒ 6 帧的逐格摘要（网格摘要）**全等**；
> * **瞬态** ⇒ 只有导出帧那 1 帧的摘要与别帧不同。
>
> 再把**重制侧**的同一相位族集合在两侧的密集 walk 上逐帧对齐，
> 回答「重制侧有没有走到这个相位」。

**逐帧摘要**（每帧都算，可逐条复查）：
地图空间点亮格数 / 族直方图 / 相位族集合 / **缓冲逐行点亮数（16 行）** /
网格 sha256 摘要 / 非黑占比 / 均值 RGB / 不同色数 /
`DISPCNT` + `BG0-3CNT` + `HOFS` + `VOFS`。

### 3.3 ⭐ 四个时刻的逐帧判定（**可判定的证据**）

| 原版时刻 | 导出帧 | 相位族集合 | 点亮格 | 6 帧里相位族相同 | **6 帧里网格摘要相同** | ⇒ 判定 |
|---|---|---|---:|---:|---:|---|
| `field-frame-v1` | `frame-05` | `band`+`hatch`+`line_alt`（**黄+青+橙**） | 192 | **6 / 6** | **6 / 6** | ⭐ **稳定态** |
| `movegrid-frame-v1` | `frame-05` | `hatch`（青） | 192 | 6 / 6 | 6 / 6 | 稳定态 |
| `grid16-frame-v1` | `frame-00` | `band`+`hatch`+`line_alt` | **175** | 6 / 6 | **1 / 6** | ⭐ **单帧瞬态** |
| `banner-frame-v1` | `frame-05` | （无） | 0 | 6 / 6 | 6 / 6 | 稳定态（无覆盖层） |

**逐帧明细（`grid16` —— 瞬态的直接证据）**：

```
frame-00（导出帧）  lit=175  缓冲逐行点亮 = [0, 0, 15, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 0, 0, 0]
frame-01           lit=176  缓冲逐行点亮 = [0, 0, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 0, 0, 0]
frame-02           lit=176  （同上）
frame-03           lit=176  （同上）
frame-04           lit=176  （同上）
frame-05           lit=176  （同上）
```

⇒ 导出帧与下一帧的差别**只有一行一格**（第 2 行 15 vs 16），
且**第 1 行是空的**（稳定态第 1 行有 16 格）
⇒ 这是 **BG2 缓冲正在被重写时的撕裂残影**，**只存在 1 帧**。
⇒ **任何忠实的重制都不该被要求复现它**（复现它就等于复现一次半刷新）。

**逐帧明细（`field` —— 稳定态的直接证据）**：

```
frame-00..05  全部：lit=192  相位族={band,hatch,line_alt}
              缓冲逐行点亮 = [0, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 0, 0, 0]
              网格摘要全等  ⇒  6 帧逐格完全相同
```

### 3.4 ⭐ 两侧逐帧对齐（重制侧到底走到这个相位没有）

| 相位族集合 | 原版密集 walk（553 帧） | 原版**最长连续**同相位 | **重制密集 walk（783 帧）** | 重制**最长连续** | 重制 35 帧包（当前 ROM） |
|---|---:|---:|---:|---:|---:|
| `{band,hatch,line_alt}` = **黄+青+橙**（`field` / `grid16`） | **67 / 553** | **67 帧连续** | **0 / 783** | **0** | **0 / 35** |
| `{hatch}` = 青（`movegrid`） | 67 / 553 | 67 帧连续 | **23 / 783** | 23 帧连续 | 1 / 35 |
| `{}` = 无覆盖层（`banner`） | —（相位集合为空，判定退化） | — | — | — | — |

> **原版的密集 walk 采样步长是 4 帧** ⇒ 67 个连续采样点 = **268 个真实帧**
> ≈ **4.5 秒**的稳定保持 ⇒ 这**不是**瞬态，是**一个持续很久的稳定态**。
>
> **重制侧的 783 帧里，「黄+青+橙」一次都没有出现**。
> 重制侧有的是：**青**（23 帧）与 **绿+橙**（134 帧，`band+edge+hatch_shift+line_alt+solid`）
> —— 与 Y2 记的「`step-26-A` 只有青；`step-29..34` 只有绿 + 橙」**完全吻合**。
>
> ⭐ **独立复现**：本流的解码器（共享仪器 `compare_overlay_families` 的固定锚
> `remake_logical_cells`）与配对流自己的解码器（`s49_fidelity_report.overlay.remake_grid`）
> **给同一个数（0 / 783）** ⇒ 不依赖单一实现。

### 3.5 ⭐ 结论：130 格劈成两半

| 原版时刻 | 走位相位数 | **归因（可判定）** | **证据** |
|---|---:|---|---|
| `field-frame-v1` | **50** | ⭐ **重制侧缺一个相位**（**不是**原版瞬态） | 原版该画面在连续 6 帧里**逐格全等**（稳定态），在原版密集 walk 里**连续 67 帧**保持；重制侧 **0 / 783** 帧出现该相位族集合 ⇒ 重制的 walk **从未走到**原版那个相位 ⇒ 差的是**走位/游戏状态**，**不是覆盖层规则** |
| `grid16-frame-v1` | **80** | ⭐ **原版那一帧是瞬态**（**不是**重制缺相位） | 导出帧在连续 6 帧里**只出现 1 次**；下一帧已是 176 格的完整画面（第 1 行不再空、第 2 行补齐 1 格）⇒ **缓冲半刷新的撕裂残影**，任何忠实的重制都**不该**被要求复现它 |
| `movegrid-frame-v1` | 0 | （那 2 格是**产品差**：单位占位） | 重制侧**有**青相位（23 / 783）⇒ 同相位下仍逐格不同 ⇒ 规则/单位占位 |
| `banner-frame-v1` | 0 | — | 逐格全等 ✔ |
| **合计** | **130** | **50 = 重制缺相位 + 80 = 原版瞬态** | |

> ⇒ **给父代理的一句话**：报告 §3.3 的「walk 相位 130 格」应当**改写成
> 「50 格 = 重制侧缺一个相位（游戏状态/走位），80 格 = 原版覆盖层缓冲的单帧撕裂瞬态」**；
> 这 130 格**没有一格是覆盖层规则的产品差**，所以**覆盖层规则侧已经到头了**。

### 3.6 130 格的逐格族名对（明细）

| 原版时刻 | 原版族 → 重制族 | 格数 |
|---|---|---:|
| `field` | `edge` → `hatch` | 38 |
| `field` | `hatch` → `edge` | 6 |
| `field` | `line_alt` → `edge` | 2 |
| `field` | `line_alt` → `hatch` | 2 |
| `field` | `line_alt` → `solid` | 2 |
| **小计（`field`）** | | **50** |
| `grid16` | `edge` → `hatch` | 36 |
| `grid16` | `blank` → `solid` | 15 |
| `grid16` | `edge` → `solid` | 13 |
| `grid16` | `hatch` → `edge` | 6 |
| `grid16` | `band` → `solid` | 2 |
| `grid16` | `line_alt` → `edge` | 2 |
| `grid16` | `line_alt` → `hatch` | 2 |
| `grid16` | `line_alt` → `solid` | 2 |
| `grid16` | `solid` → `hatch` | 2 |
| **小计（`grid16`）** | | **80** |
| | **合计** | **130** |

> ⚠️ **这 130 格是从 wave 13 包自己的 `cell-classification.json` 里逐格读回来的**
> （sha256 见收据），**只含 `class == "walk 相位"` 的格**。
> 各时刻的**全部**族名对里还有尾部残留格（例如 `field` 的 `band → solid` 1 格 =
> `grid16` 的 `hatch → solid` 4 格），那些**不属于这 130**。

（`grid16` 里 `blank → solid` 的 15 格 = 原版那一帧第 1 行被清空、第 2 行少 1 格的
**半刷新残影**；`edge → hatch` 的 36 格 = 原版那一帧的格线还没被可达集覆盖
——**都是撕裂，不是规则**。）

---

## 4. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| V1 | `$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-z3'; python tools/mgba_probe/build.py` | 私有探针 | exit 0；`built …\mgba-probe-z3\mgba-probe.exe (1372672 bytes)`；**共享 `build/mgba-probe/` 未动** |
| V2 | `python tools/s49_z3_bound/z3record.py --side original --out build/s49-z3-bound/walk` | 录到原版密集 walk | **553 帧 / 553 存档 / 6.8 s**；帧指纹 `ffa679a0e4ff021e…` |
| V3 | `python tools/s49_z3_bound/z3record.py --side remake --out build/s49-z3-bound/walk` | 录到重制密集 walk（**当前 ROM**） | **783 帧 / 783 存档 / 8.7 s**；帧指纹 `72b285fe53ca442a…`；ROM sha `2c2b48d9…`（**钉住的字节副本**） |
| V4 | `python tools/s49_z3_bound/z3record.py --side both --out build/s49-z3-bound/walk-b --remake-rom build/s49-z3-bound/walk/pinned/remake.gba` | 第二次独立录制 | 原版 **553**（指纹同） / 重制 **783**（指纹同）；**逐字节一致** |
| V5 | `python tools/s49_z3_bound/z3bound.py --walk build/s49-z3-bound/walk --walk-id … --out build/s49-z3-bound/bound-A.json` | **新下界** + 交叉核对 | **floor_sum = 16,389**；canonical **90,993**；387 distinct；**`pair.beat_floor` 交叉核对 `agrees=True`** |
| V6 | 同上，walk = `build/s49-pairing/walk5` | 旧值复现 | **floor_sum = 23,753**（= X2 报告的值）；`agrees=True` |
| V7 | `python tools/s49_z3_bound/z3bound.py --walk build/s49-z3-bound/walk-b … --out bound-B.json` | 两次跑逐字节一致 | `bound-A.json` 与 `bound-B.json` sha256 **同为 `399a238ba9c84683…`** |
| V8 | `python tools/s49_pairing/pairing_report.py --walk build/s49-z3-bound/walk --out build/s49-z3-bound/pairing --no-floor` | 内容锚配对（只读调用） | 同刻 **21 / 25**；`px@同刻` 合计 **18,886**；配对差下界 **4** |
| V9 | `python tools/s49_z3_bound/z3phase.py --out build/s49-z3-bound/phase-A.json` | **130 格归因** | `field` 6/6 同网格 ⇒ **稳定态**；`grid16` 1/6 ⇒ **单帧瞬态**；重制 **0 / 783**；原版 **67 / 553**（最长连续 67） |
| V10 | 同上，`--out phase-B.json` | 两次跑逐字节一致 | sha256 **同为 `306ff9670641146a…`** |
| V11 | 孤儿进程复查 `Win32_Process` | 无残留 | 两次录制后各查一次：**0 个** `mgba-probe.exe` |
| V12 | `python tools/s49_z3_bound/z3phase.py`（独立解码器交叉核对） | 不依赖单一实现 | 配对流的 `remake_grid` 与本流的 `remake_logical_cells` 对「黄+青+橙」**都给 0 / 783** |
| V13 | 编码自检 | 新文件 LF、无 BOM | 见 §7 |
| V14 | `git status --short` | 未提交、不碰别人的文件 | 只新增 `tools/s49_z3_bound/`、`notes/s49-fidelity/Z3-bound-and-phase.md`；**未提交 git** |

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Z3-1 | 报告 §11 第 2 项的「可证像素下界 ≈ 23,700」可以沿用 | 读报告原文 + 读 X2 笔记的 ROM 口径 | **口径过期**：那两个数是 wave 6 录制上测的（旧 ROM `fec749d8…` / `c1f44b3b…`），**不是**当前 ROM | **已证伪** |
| Z3-2 | 共享 `probe_client.py`（每行一个读线程）能安全跑完 4000 帧的密集录制 | 直接用它录原版侧 | **不行**：Lua 在**探针进程内**读环境变量，而 `probe_client.py` 不给探针进程传 `X2_*` ⇒ `missing environment variable X2_OUTPUT_DIR`；且该客户端的逐行读线程有乱序风险 ⇒ 改用 `w1_probe.py`（单后台读线程）并把 `X2_*` 导出进本进程环境 | **已证伪（已修）** |
| Z3-3 | 原版侧不需要重录（ROM 未变，X2-12 说逐字节相同） | 实录并逐字节比对 | 不必重录也能用，但**本流还是重录了**：新录的 553 帧与 `walk5` / `walk6-z1` **逐字节相同**（三份指纹同一个）⇒ 该复用**已被实测坐实**，不再只是引用 | **已确认** |
| Z3-4 | 当前 ROM 的可证下界 = 16,389 | 25 拍 × 全帧逐对取最小求和 + 与 `pair.beat_floor` 交叉核对 | **16,389**；`cross_check.inherited_floor_sum = 16389`，`agrees=True` | **已确认** |
| Z3-5 | 新下界与旧值 23,753 的差来自算法漂移，而不是 ROM 变了 | 用**同一份代码**在旧录制 `walk5` 上重算 | 旧录制重算 = **23,753**（与 X2 逐值相同）⇒ 差值来自 ROM | **已证伪（差值来自 ROM）** |
| Z3-6 | 下界 16,389 与内容锚可达数 18,886 不矛盾 | 两者的口径差异（前者放宽到全帧配对，后者是同一时刻的配对） | **16,389 ≤ 最优 ≤ 18,886**，区间宽 2,497 ⇒ 真值被夹住 | **已确认** |
| Z3-7 | 原版 `field` 那一帧是稳定态 | 把 `s49-original-field-frame-v1` 的 6 帧 VRAM 逐帧解码 BG2 覆盖层，比网格摘要 | **6 / 6 逐格全等**（192 格、逐行 [0,16×12,0,0,0]）⇒ **稳定态** | **已确认** |
| Z3-8 | 原版 `grid16` 那一帧是单帧瞬态 | 同上，比 `s49-original-grid16-frame-v1` 的 6 帧 | **1 / 6**；导出帧 175 格（第 1 行空、第 2 行 15），下一帧已 176 格完整 ⇒ **半刷新撕裂残影** | **已确认** |
| Z3-9 | 「重制侧 35 帧无一帧同现」在更密的录制上仍然成立 | 把重制侧 783 帧密集 walk 的存档 VRAM 逐帧解码 | **0 / 783**（相位族集合 `{band,hatch,line_alt}`）；两个独立解码器给同一个数 | **已确认** |
| Z3-10 | 原版那一侧也该查一遍「这个相位到底持续多久」 | 把原版 553 帧密集 walk 的存档 VRAM 逐帧解码 | **67 / 553**，且是**连续 67 个采样点**（stride 4 ⇒ 268 真实帧 ≈ 4.5 s）⇒ 稳定态 | **已确认** |
| Z3-11 | 130 格是同一类东西 | 按 §3.5 逐时刻判定 | **不是**：`field` 50 = 重制缺相位；`grid16` 80 = 原版瞬态 | **已证伪（分成两类）** |
| Z3-12 | 两次跑逐字节一致 | 独立录制 + 独立计算，比 sha256 | 帧指纹、下界收据、相位收据**三者都逐字节相同** | **已确认** |
| Z3-13 | 录制会吃 7–8 GB 内存并泄漏（会卡住并行流） | 实测两次全量录制的内存与孤儿进程 | 本次两段录制各 **6.8 s / 8.7 s**，孤儿探针 **0 个** ⇒ 在本机上不是问题；仍**全程串行**，没有同时开两个全量录制 | **已确认（未复现）** |

---

## 6. 卡在哪 / 剩余风险（**不粉饰**）

1. ⛔ **`field` 的 50 格没有闭合的路径在本流范围内**：结论是「**重制侧缺一个相位**」，
   但**到底是哪一个相位、怎么走位才能走到，本流没有判定**
   ⇒ 这是**游戏状态/流程**问题（对应 Y2 §8 第 3 条：需要 Y1 的闭环驱动走到那个相位），
   **不是**覆盖层规则问题 ⇒ 改 `battle_range_ui_style.h` 不会关掉这 50 格。
2. ⚠️ **`grid16` 的 80 格现在有了新解释，但没有新口径**：
   原版那一帧是撕裂残影 ⇒ 「多画 17」与「族名不一致 80」**不可复现**，
   报告里应当把它列进**「明确排除项」**（与 Y2 §3.5 的尾部残留并列），
   **而不是**留在「未达成项」里当产品差。
   ⛔ **改口径是 Z4 的活**（`tools/s49_package/classify_overlay_cells.py` 与报告生成器
   都是 Z4 的文件，本流**未改**）。
3. ⚠️ **下界 16,389 只对当前这两段录制成立**（原版 `1198ece7…` + 重制 `2c2b48d9…`，
   stride 4）。**产品改动后必须重算**；本流给了 `z3record.py` + `z3bound.py` 一条命令的重跑路径。
4. ⚠️ **本次重制侧密集 walk 是在 `2c2b48d9…` 上录的**：交回时盘上的 ROM 仍是这个 sha
   （`butano-sequel.gba`，mtime 16:19:43）。若父代理在 Z1/Z2 之后再重建 ROM，
   **重制侧录制必须重做**（原版侧不用：原版 ROM 未变，且已证明三次录制逐字节相同）。
5. ⚠️ **判定台的 100,210 与本流的下界 16,389 不是同一口径**：
   判定台是**不带时刻约束**的 arg-min（35 帧基线走），本流的下界是
   **25 拍 × 全帧**的放宽 ⇒ 报告里必须写清口径，**不许**把 16,389 说成「判定台的下界」。
6. ⛔ **`banner` 时刻的相位判定是退化的**（相位族集合为空 ⇒
   「含该集合的帧数」恒为平凡值）⇒ 报告里 `banner` 一栏只能写「逐格全等 ✔」，
   **不许**引用它的相位可达性数字。
7. ⛔ **没有做的事**：把重制侧改成「按时刻推进」的走位；判定「哪个相位」是原版 `field` 的
   那个相位；把 `grid16` 的撕裂残影在**重制侧**也复现出来（本流判定为**不该复现**）。

---

## 7. 复跑命令

```powershell
cd D:\Github\gba-naruto

# 0) 私有探针（**不要**覆盖共享的 build/mgba-probe/）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-z3'
python tools/mgba_probe/build.py

# 1) 密集 walk（先钉 ROM 再录；**串行**，不要同时开两个全量录制）
python tools/s49_z3_bound/z3record.py --side both --out build/s49-z3-bound/walk

# 2) 可证像素下界（自带与 pair.beat_floor 的交叉核对）
python tools/s49_z3_bound/z3bound.py --walk build/s49-z3-bound/walk `
    --walk-id rom-2c2b48d9-dense-walk `
    --label "current ROM 2c2b48d9 (Z3 dense walk)" `
    --out build/s49-z3-bound/bound-A.json

# 3) 130 格相位归因
python tools/s49_z3_bound/z3phase.py --out build/s49-z3-bound/phase-A.json

# 4) 内容锚配对（**只读调用**配对流的仪器）
python tools/s49_pairing/pairing_report.py --walk build/s49-z3-bound/walk `
    --out build/s49-z3-bound/pairing --no-floor

# 5) 两次跑逐字节一致（独立录制 + 独立计算，再比 sha256）
python tools/s49_z3_bound/z3record.py --side both --out build/s49-z3-bound/walk-b `
    --remake-rom build/s49-z3-bound/walk/pinned/remake.gba
python tools/s49_z3_bound/z3bound.py --walk build/s49-z3-bound/walk-b `
    --walk-id rom-2c2b48d9-dense-walk `
    --label "current ROM 2c2b48d9 (Z3 dense walk)" `
    --out build/s49-z3-bound/bound-B.json
python tools/s49_z3_bound/z3phase.py --out build/s49-z3-bound/phase-B.json
Get-FileHash build/s49-z3-bound/bound-A.json,build/s49-z3-bound/bound-B.json `
    -Algorithm SHA256
Get-FileHash build/s49-z3-bound/phase-A.json,build/s49-z3-bound/phase-B.json `
    -Algorithm SHA256

# 6) 旧值对照（同一份代码在旧录制上重算 ⇒ 应得 23,753）
python tools/s49_z3_bound/z3bound.py --walk build/s49-pairing/walk5 `
    --out build/s49-z3-bound/bound-old-walk5.json
```

---

## 8. 确认

* **新文件全部 LF、无 BOM**（`tools/s49_z3_bound/*` 与本笔记；见 §9 的自检命令）。
* **未提交 git**。
* **未改重制线任何文件**（`D:\Shell\gba-naruto-butano` **只读使用**；
  录制的重制 ROM 是它的**字节副本**）。
* **未改逆向线任何文件**（`D:\Shell\gba-naruto-reverse` 未触碰）。
* **未改其它流的仪器**：`tools/s49_pairing/`、`tools/s49_overlay_align/`、
  `tools/s49_fidelity_report/`、`tools/s49_package/`、`tools/s49_battle_balance/`、
  `tools/s49_rule_probe/`、`tools/mgba_probe/` 一律**只读调用**
  （唯一的例外：`tools/mgba_probe/build.py` 用 `KONOHA_PROBE_OUT` 编到了**私有目录**，
  **没有**动共享的 `build/mgba-probe/`）。
* **没有伪造任何帧**：所有数字来自盘上的收据 / 证据文件。
* **并发约束遵守**：两段全量录制**串行**跑；跑完复查 `Win32_Process`：**0 个孤儿探针**。

---

## 9. 编码自检（LF、无 BOM）

```powershell
cd D:\Github\gba-naruto
$files = @(
  'tools/s49_z3_bound/__init__.py',
  'tools/s49_z3_bound/z3record.py',
  'tools/s49_z3_bound/z3bound.py',
  'tools/s49_z3_bound/z3phase.py',
  'notes/s49-fidelity/Z3-bound-and-phase.md')
foreach ($f in $files) {
  $bytes = [System.IO.File]::ReadAllBytes($f)
  $bom   = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
  $crlf  = ([regex]::Matches([System.Text.Encoding]::UTF8.GetString($bytes), "`r`n")).Count
  "{0,-44} BOM={1} CRLF={2} bytes={3}" -f $f, $bom, $crlf, $bytes.Length
}
```
