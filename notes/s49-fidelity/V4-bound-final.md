# V4 —— 可证像素下界为**最终 ROM** 终算 + 「重制缺一个相位」的具体定位

> 2026-10-24 · wave 16 · 流 V4 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 任务书：`notes/s49-fidelity/WAVE16-TASKS.md` §0.3 / §4
> 上游：`notes/s49-fidelity/Z3-bound-and-phase.md`（算法 / 工具 / 16,389 的来源）、
> `notes/s49-fidelity/X2-pairing.md`（配对流与「可证像素下界」的证明方式）
> 仪器：`tools/s49_z3_bound/`（**Z3 已交付，本流沿用；本流新增 `v4phase.py`**）
> 产物：`build/s49-v4/`（不进仓）
> ⛔ **未改**重制线任何文件（`D:\Shell\gba-naruto-butano` **只读使用**）；
> ⛔ **未改** `tools/s49_package/`（V3 独占）；⛔ 逆向线全程只读；⛔ **未提交 git**。

---

## 0. 一句话结论

> ⭐ **任务 A**：为**最终 ROM `fb9d2dbd…`** 重算的可证像素下界 = **16,350**
> （25 拍 ×「原版全部帧 × 重制全部帧」逐对取最小战场区残差再求和；
> 与 X2r 的 `pair.beat_floor` **交叉核对 `agrees=True`**，不等就拒绝出数）。
>
> | 对照 | 值 | 相对新值 |
> |---|---:|---:|
> | **新下界（ROM `fb9d2dbd…`）** | **16,350** | — |
> | Z3 的 16,389（ROM `2c2b48d9…`） | 16,389 | **−39（−0.24 %）** |
> | X2 的 23,753（ROM `fec749d8…`） | 23,753 | **−7,403（−31.2 %）** |
>
> ⭐ **同一份代码**在 Z3 的录制上重算 = **16,389**、在 wave-5 的录制上重算 = **23,753**
> ⇒ **三个数的差全部来自 ROM，不是算法漂移**（控制实验，见 §4 V6/V7）。
> ⇒ **残差归零在当前 ROM 上仍不可达**（下界 16,350 > 0）。
> ⇒ ⭐ **三段夹逼**（口径见 §2.2 的警告）：
>
> ```
> 16,350   ≤   最优残差   ≤   18,861
> (下界 B1)                (内容锚同刻配对 B2，可达；同刻 21/25)
> ```
>
> ⭐ **任务 B**：那 **50 格 = 「产品缺一段演出」**，**不是「walk 没走到」** ——
> 三条**可判定**的证据：
>
> 1. **重制侧的产品规则让「青 + 橙」在结构上不可能同现**
>    （`battle_range_ui_style.h::battle_range_ui_cell_kind`：
>    `move` 只在 `in_move_range && move_phase`，`attack_range` 只在 `in_attack_range && !move_phase`）
>    ⇒ **任何走位都取不到**；783 帧实测 `青∧橙` 共现 **0** 次、`黄∧青` 共现 **0** 次。
> 2. **重制侧已经走到了同一段**（结算段，semantic beat 24–30，**157 帧、192 个点亮格、
>    光标 + 橙都在**）⇒ **不是 walk 没走到**。
> 3. **原版那一帧是「相位残留」**（证据一致地指向，严格证明需要原版逐帧的缓冲写入序列
>    ⇒ 见 §6 风险 4）：原版的**活相位**里青（移动可达集）与橙（攻击范围）从不同时出现
>    （原版自己的移动相位帧 = solid 83 / edge 63 / hatch 46，**零黄、零绿、零橙**）；
>    原版在**结算段**把上一相位的青留在覆盖层缓冲里没清 ⇒ 才出现「青 + 橙 + 尾部黄光标」同框
>    （旁证：`field` 帧的受阻格 **83** 与移动相位帧的 **83** 完全相同）。
>
> ⇒ **缺的正是「相位切换时不清覆盖层缓冲」这段演出**（产品侧），
> 而**不是**「再走几步就能走到」的走位问题。
>
> ⭐ **顺带修正 wave-13 的「50 格」口径**：那 50 格是**跨时刻**比出来的
> （重制侧当时最好的匹配帧是**移动相位**的纯青帧 `step-26-A`）。
> **同刻**（原版结算段 ↔ 重制侧结算段）比出来是 **56 格（连尾部共 67 格）**，
> 而且差别族名也不同：**原版画「移动可达集（青 `hatch`）」、重制画「合法目标（绿 `hatch_shift`）」**。

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_z3_bound\v4phase.py` | **新建** | 「缺一个相位」定位仪：两侧逐帧时间线 + 相位族集合 + 相机 + 相位共存统计 + **同刻逐格对照** |
| `D:\Github\gba-naruto\notes\s49-fidelity\V4-bound-final.md` | **新建** | 本文件 |
| `D:\Github\gba-naruto\tools\s49_z3_bound\z3record.py` | **沿用**（未改） | 密集 walk 录制器（行安全客户端 + 钉 ROM） |
| `D:\Github\gba-naruto\tools\s49_z3_bound\z3bound.py` | **沿用**（未改） | 可证像素下界（arg-min 审计 + `pair.beat_floor` 交叉核对 + ROM sha） |
| `D:\Github\gba-naruto\tools\s49_z3_bound\z3phase.py` | **沿用**（未改） | Z3 的 130 格相位归因（被 `v4phase.py` **只读 import**） |

**只读复用的东西**：`tools/s49_pairing/`（`walkspec` / `savestate` / `anchors` / `pair` / `pairing_report`）、
`tools/s49_fidelity_report/`（`overlay` / `pixels`）、`tools/s49_overlay_align/compare_overlay_families.py`
（共享覆盖层仪器）、`tools/s49_rule_probe/overlay_ground_truth.py`（族名语义）、`tools/s49_battle_balance/w1_probe.py`
（行安全探针客户端）、`tools/mgba_probe/build.py`（用 `KONOHA_PROBE_OUT` 编到**私有目录**）。

---

## 2. 任务 A —— 最终 ROM 的可证像素下界

### 2.1 口径（**与 Z3 / X2r 完全相同，算法未重写**）

> 每一拍内，取**原版的全部帧**（该拍 23 帧 = 22 个内层采样 + 1 个拍尾）
> × **重制的全部帧**（783 帧，按战场区像素去重后 **383** 张），
> 逐对算战场区残差（`diff_mask`，区域 `(0,0,240,128)`）取最小；**25 拍求和**。

`z3bound.py` 自带三层保险：

1. **arg-min 审计**：每一拍记下「取到最小值的原版帧 + 重制帧」（见 §2.3）；
2. **交叉核对**：本工具自己的实现必须与 X2r 的 `pair.beat_floor` **逐值相等**，
   不等就 `raise SystemExit`（**拒绝出数**）⇒ 实测 `agrees=True`；
3. **钉 ROM + sha**：收据里写两侧 ROM 的 sha256 与全部帧的 sha256；
   收据**不含墙钟时间** ⇒ 两次跑可以逐字节比较。

### 2.2 ⭐ 新下界 + 与旧值的对照

| 项 | 旧（wave 6 / X2） | 中（wave 14 / Z3） | **新（wave 16 / V4）** |
|---|---:|---:|---:|
| **可证像素下界（25 拍求和）** | **23,753**（ROM `fec749d8…`）/ 23,697（`c1f44b3b…`） | **16,389**（ROM `2c2b48d9…`） | **16,350**（ROM **`fb9d2dbd…`**） |
| 规范帧残差之和（canonical） | 111,587 | 90,993 | **91,201** |
| 重制帧去重后（战场区） | 350 | 387 | **383** |
| 原版 ROM | `1198ece7…` | `1198ece7…` | `1198ece7…`（未变） |
| 重制 ROM | `fec749d8…` / `c1f44b3b…` | `2c2b48d9…` | **`fb9d2dbd…`** |
| `pair.beat_floor` 交叉核对 | — | `agrees=True` | **`agrees=True`** |
| **B2 · 内容锚同刻配对的可达残差** | 28,899 | 18,886 | **18,861**（同刻 **21 / 25**） |
| 内容锚配对差下界 | 6 帧 | 4 帧 | **4 帧** |
| ⭐ **三段夹逼** | 23,753 ≤ opt ≤ 28,899 | 16,389 ≤ opt ≤ 18,886 | **16,350 ≤ opt ≤ 18,861** |

> ⚠️ **口径提醒（必须写进 1:1 报告）**：**16,350 是「针对当前这两段录制」的下界**
> （原版 `1198ece7…` + 重制 `fb9d2dbd…`，密集 walk，stride 4），
> **不是**判定台读数（判定台是**不带时刻约束**的 arg-min，量级差 3.9 倍，**两个口径不许混用**）。
>
> ⭐ **产品改动后必须重算**：本流给了**一条命令**的重跑路径（§7）。
> 当前盘上的 ROM 就是 `fb9d2dbd…`（mtime 2026-10-24 19:18:31，V1/V2 尚未出新构建），
> **V1/V2 落地后重录重制侧即可**（原版侧不用重录，见 §2.5）。

### 2.3 ⭐ 逐拍分解（新下界 16,350）

| 拍 | 规范帧 | 该拍下界 | 取到最小值的原版帧 | 取到最小值的重制帧 | 规范帧残差 |
|---:|---|---:|---|---|---:|
| 0 | `step-0000-base.png` | 1,431 | `step-0000-base.png` | `step-0507-in.png` | 1,431 |
| 1 | `step-0023-beat.png` | 1,014 | `step-0011-in.png` | `step-0102-in.png` | 1,213 |
| 2 | `step-0046-beat.png` | 1,090 | `step-0031-in.png` | `step-0126-in.png` | 1,395 |
| 3 | `step-0069-beat.png` | 1,115 | `step-0067-in.png` | `step-0519-in.png` | 1,243 |
| 4 | `step-0092-beat.png` | 1,199 | `step-0092-beat.png` | `step-0347-in.png` | 1,199 |
| 5 | `step-0115-beat.png` | 1,590 | `step-0109-in.png` | `step-0188-in.png` | 1,828 |
| 6 | `step-0138-beat.png` | 1,005 | `step-0132-in.png` | `step-0212-in.png` | 1,200 |
| 7 | `step-0161-beat.png` | 1,674 | `step-0150-in.png` | `step-0235-in.png` | 1,814 |
| 8 | `step-0184-beat.png` | 1,002 | `step-0184-beat.png` | `step-0261-in.png` | 1,002 |
| 9 | `step-0207-beat.png` | 305 | `step-0207-beat.png` | `step-0277-in.png` | 305 |
| 10 | `step-0230-beat.png` | 182 | `step-0208-in.png` | `step-0290-in.png` | 278 |
| 11 | `step-0253-beat.png` | 5 | `step-0252-in.png` | `step-0323-in.png` | 236 |
| 12 | `step-0276-beat.png` | 0 | `step-0254-in.png` | `step-0070-in.png` | 0 |
| 13 | `step-0299-beat.png` | 0 | `step-0285-in.png` | `step-0361-in.png` | 0 |
| 14 | `step-0322-beat.png` | 0 | `step-0300-in.png` | `step-0377-in.png` | 0 |
| 15 | `step-0345-beat.png` | 0 | `step-0323-in.png` | `step-0393-in.png` | 0 |
| 16 | `step-0368-beat.png` | 0 | `step-0360-in.png` | `step-0431-in.png` | 0 |
| 17 | `step-0391-beat.png` | 0 | `step-0369-in.png` | `step-0439-in.png` | 0 |
| 18 | `step-0414-beat.png` | 0 | `step-0392-in.png` | `step-0448-in.png` | 0 |
| 19 | `step-0437-beat.png` | 64 | `step-0415-in.png` | `step-0325-in.png` | 24,460 |
| 20 | `step-0460-beat.png` | 742 | `step-0448-in.png` | `step-0462-in.png` | 4,158 |
| 21 | `step-0483-beat.png` | 1,254 | `step-0480-in.png` | `step-0510-in.png` | 27,322 |
| 22 | `step-0506-beat.png` | 1,236 | `step-0485-in.png` | `step-0519-in.png` | 20,627 |
| 23 | `step-0529-beat.png` | 1,310 | `step-0528-in.png` | `step-0528-in.png` | 1,358 |
| 24 | `step-0552-beat.png` | 132 | `step-0550-in.png` | `step-0546-in.png` | 132 |
| | **合计** | **16,350** | | | **91,201** |

**下界的构成**（与 Z3 的 16,389 结构相同）：

| 段 | 拍 | 合计 | 占比 |
|---|---|---:|---:|
| 战斗段前 9 拍 | 0–8 | **11,120** | 68.0 % |
| 标题 / 淡出段 | 9–11 | **492** | 3.0 % |
| 对话段 | 12–18 | **0**（7 拍全 0） | 0 % |
| 结算段 | 19–24 | **4,738** | 29.0 % |
| **合计** | 25 | **16,350** | 100 % |

⇒ **对话段与淡出段已经彻底对齐**（7 拍 = 0）；剩下的全是**战斗段与结算段的产品差**。

### 2.4 ⭐ 新下界的证明方式（可核验）

> **命题**：在「同语义 walk」下，任何配对方式在 battle-14 这 25 拍上的
> 战场区残差总和 **≥ 16,350**。
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
> 5. 25 拍求和 ⇒ **总残差 ≥ Σ_b min** = **16,350**。
>
> **可核验性**（全部在本流跑过，见 §4）：
> * `z3bound.py` 的收据里写死了算法、战场区、25 拍、**arg-min 帧名**、
>   两侧 ROM 的 sha256、全部帧的 sha256；
> * 收据里 `cross_check.inherited_floor_sum` 是**用 X2r 的 `pair.beat_floor`
>   独立算出来的同一个数**（实测 `agrees=True`）⇒ 算法没被改写；
> * ⭐ **控制实验**：**同一份代码**在 Z3 的录制上重算 = **16,389**、
>   在 wave-5 的录制上重算 = **23,753** ⇒ **新旧值的差来自 ROM，不来自算法**；
> * 同一份录制**独立录两次** ⇒ 帧指纹与下界收据**逐字节相同**（sha256 `7871453668…`）。

### 2.5 录制口径与可复现性

| 项 | 值 |
|---|---|
| 探针 | **私有** `build/mgba-probe-v4/mgba-probe.exe`（1,372,672 B；`$env:KONOHA_PROBE_OUT=…` 现编；**共享的 `build/mgba-probe/mgba-probe.exe` 未动**，mtime 仍是 2026-10-23 23:21:42） |
| 客户端 | `tools/s49_battle_balance/w1_probe.py`（**单后台读线程 + 队列**，避开共享 `probe_client.py` 的「每行一个读线程」死锁） |
| 原版 ROM | `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`（`D:\Shell\Github\gba-naruto-butano\rom\base.gba`，**未变**） |
| 重制 ROM | `fb9d2dbd8e35b8101b96f6df133b03073a144e8f84ae124fbc1812d47fd93384`（**先钉成字节副本再录**，收据里写 sha） |
| 录到的帧 | 原版 **553**（1 base + 24 拍 × 23）/ 重制 **783**（1 base + 34 拍 × 23） |
| 录制耗时 | 跑 A：原版 11.4 s / 重制 12.6 s；跑 B：原版 7.5 s / 重制 9.5 s |
| 孤儿探针 | 两次录制后各查一次 `Win32_Process`：**0 个** `mgba-probe.exe` |
| 帧指纹（原版） | `ffa679a0e4ff021eba607a9879f09c6f7d46ac2f01f979b7224541bb87cbe1d8` |
| 帧指纹（重制） | `b91900e76c8dfc118637d810dde72ef1f5968d8f85f2057d0494fb8693076c87` |

> ⭐ **原版侧不用重录**这条结论**又被坐实了一次**：本次新录的 553 帧与 Z3 的、
> 与 wave-5 的 `walk5` **逐字节相同**（同一个指纹 `ffa679a0…`）。
> ⇒ 重制侧换了 ROM，原版侧一个字节都没变。
>
> ⚠️ 重制侧指纹与 Z3 的 `72b285fe…` **不同** —— 这是**预期**的（ROM 变了）。

---

## 3. 任务 B —— 「重制缺一个相位」的具体定位

### 3.1 问题（Z3 留下的）

Z3 判定：`field` 的 **50 格 = 重制侧缺一个相位**（原版那一帧是**稳定态**，
原版密集 walk 里**连续 67 帧**保持；重制侧 **0 / 783** 帧同现），
但**「具体是哪个相位、怎么走位才走到」没有判**。

### 3.2 判据（**可判定**，不是断言）

`v4phase.py`（本流新增）做四件事，全部可复查：

1. **逐帧时间线**：对两侧每一帧读出
   **相位族集合**（`z3phase.py` 的地图空间解码器，与 wave-13 包同一口径）、
   族直方图、相机（`bg_vofs` / `bg_hofs`）、场景类、acting 指针；
2. **相位共存统计**：任意两个族是否**同框**（这是「某个组合可不可达」的直接度量）；
3. **最大连续段**：原版的相位出现在**哪一段**；
4. **同刻逐格对照**：原版 `field` 帧 vs 重制侧**每一帧**（783 帧里 180 帧有覆盖层），
   给出逐格族名对与残差，并**按相位族集合分组**取每组的最好一帧。

### 3.3 ⭐ 原版侧：这个相位在哪一段（实测）

**原版密集 walk 553 帧的相位族集合清单**（`build/s49-v4/phase-v4.json`）：

| 相位族集合 | 帧数 | 拍 | 场景 |
|---|---:|---|---|
| （无覆盖层） | 436 | b3–b22 | dialogue / fade / map |
| `{hatch_shift}`（**绿** = 合法目标） | 50 | b0（base）+ b1–b3 | map（**战斗段**，acting 0–3） |
| **`{band, hatch, line_alt}`（黄 + 青 + 橙）** | **67** | **b22–b24** | **map（结算段）** |

**那 67 帧的窗口**：

```
first_index 486  last_index 552   （67 个采样点 × stride 4 = 268 个真实帧 ≈ 4.5 s）
相机 BG0/BG1 VOFS : 152 → 166 → 177 → 182 → 184 → 200 → 216 → 232 → 240  （连续滚动）
场景           : 全部 map
每帧族直方图   : 完全相同（band 1 / edge 90 / hatch 12 / line_alt 6 / solid 83 = 192 点亮格）
```

⇒ ⭐ **相位位置定死了**：这个相位在原版的**结算段**（对话段之后的最后 3 拍），
相机正在**连续滚动**回地图，**覆盖层内容一字不变地挂了 4.5 秒**。

### 3.4 ⭐ 重制侧：同刻画的是什么（实测）

**重制密集 walk 783 帧的相位族集合清单**：

| 相位族集合 | 帧数 | 拍（semantic） | 场景 |
|---|---:|---|---|
| （无覆盖层） | 603 | −3 – 24（不含 21） | dialogue / fade / map |
| `{hatch}`（**青** = 移动可达集） | 23 | **21** | map（**移动相位**） |
| `{band, hatch_shift, line_alt}`（**黄 + 绿 + 橙**） | **157** | **24–30** | map（**结算段**） |

**共存统计（这是「可不可达」的直接度量）**：

| 同框组合 | 原版 553 帧 | **重制 783 帧** |
|---|---:|---:|
| `hatch` ∧ `line_alt`（**青 + 橙**） | **67** | **0** |
| `band` ∧ `hatch`（黄 + 青） | 67 | **0** |
| `band` ∧ `line_alt`（黄 + 橙） | 67 | **157** |
| `hatch` ∧ `hatch_shift`（青 + 绿） | 0 | **0** |

⇒ 重制侧**能**画「黄 + 橙」（157 帧），**从不**画「青 + 橙」。

### 3.5 ⭐ 归因：**产品缺一段演出**，不是 walk 没走到

**证据 ①（产品规则 ⇒ 结构上不可达）** —— 重制线**只读**源码
`butano-sequel/game/include/konoha/battle_range_ui_style.h:208-236`：

```cpp
battle_range_ui_cell_kind(bool move_phase, bool cursor_cell,
                          bool in_move_range, bool in_attack_range,
                          bool legal_target, bool blocked)
{
    if(cursor_cell   && ! move_phase) { return cursor;        }   // 黄
    if(legal_target  && ! move_phase) { return target;        }   // 绿
    if(in_attack_range && ! move_phase) { return attack_range; }  // 橙
    if(in_move_range &&  move_phase)  { return move;          }   // 青
    return blocked ? blocked : grid;
}
```

* `move`（青）要求 `move_phase` **为真**，`attack_range`（橙）要求 `move_phase` **为假**
  ⇒ **青与橙在同一个格里、同一帧里，逻辑上互斥**；
* `move_phase` 的来源是 `battle_runtime_scene.cpp`：
  `const bool move = (state.phase == battle_scene_phase::move_selection);`
  ⇒ **单一相位** ⇒ **任何走位都不可能让青与橙同框**；
* 渲染器每帧**整块重算重写** 16×12 的覆盖层缓冲（`battle_runtime_scene.cpp:2267-2343`）
  ⇒ **不留上一相位的残迹**；
* **实测吻合**：783 帧里 `青 ∧ 橙` 共现 **0** 次。

**证据 ②（重制侧已经走到同一段）** —— 重制侧的**结算段**（semantic beat 24–30）
画了 **157 帧、192 个点亮格**的覆盖层，**光标（黄）与橙都在**
（相位集合 `{band, hatch_shift, line_alt}`），相机 `BG2VOFS = 240`。
⇒ **段是走到了的**；差的是**第三族**：原版画**移动可达集（青）**，重制画**合法目标（绿）**。

**证据 ③（原版那一帧是「相位残留」）** ——

* 原版自己的**活**相位里，青与橙**从不同时出现**：
  * 原版的**移动相位**帧（`movegrid` 真值）= solid 83 / edge 63 / **hatch 46**，**零黄、零绿、零橙**；
  * 原版的**目标相位**帧（密集 walk b1–b3）= **只有绿** `{hatch_shift}`，也没有橙；
* 原版的 `field` 帧却同时有 **青 12 + 橙 6 + 黄 1**；
* 而且 `field` 帧的**受阻格数 = 83**，与移动相位帧的 **83 完全相同**
  ⇒ 这不是巧合：**`field` 帧画的就是那块「移动相位的缓冲」，上面又叠了目标相位的橙
  和尾部那个黄光标格** —— 原版**相位切换时不清覆盖层缓冲**。

⇒ **三条证据合起来只指向一个结论**：

> ⭐ **那 50 格是「产品缺一段演出」** ——
> 原版在结算段把**战斗相位残留的青格**留在覆盖层缓冲里，和目标相位的橙、尾部黄光标同框；
> 重制侧是「单一相位 + 每帧整块重画」，**结构上画不出这个组合**。
> **不是 walk 没走到**（重制侧已经走到了结算段，157 帧、192 格、光标 + 橙都在）。
>
> **要闭合它，重制侧需要的是产品改动**（属 V2 / 重制线，本流**未改**）：
> ① 相位切换时**不清**上一相位的可达集格（保留缓冲残迹），**或**
> ② 结算段按**移动相位**的族名画那一组格。
> 改 `battle_range_ui_style.h` 的**优先级**（比如允许 `move` 与 `attack_range` 同框）
> **不能**解决 —— 因为问题不在优先级，在**缓冲被整块重画**。

### 3.6 ⭐ 顺带修正 wave-13 的「50 格」口径

wave-13 包的 `cell-classification.json` 里，`field` 时刻的**最佳匹配重制帧 = `step-26-A`**，
其相位族集合 = **`{hatch}`（纯青）** —— 那是重制侧的**移动相位**帧，
**不是**结算段帧 ⇒ **那 50 格是跨时刻比出来的**。

本流的 `v4phase.py` 对重制侧**全部 180 帧**（有覆盖层的那些）逐帧对照原版 `field` 帧：

| 对照对象 | 相位族集合 | 帧数 | 最好残差 | 最好帧 | 非尾部格数 |
|---|---|---:|---:|---|---:|
| **跨时刻**（wave-13 用的） | `{hatch}`（移动相位） | 23 | **61** | `step-0553-in.png`（semantic 21） | **50** |
| **同刻**（结算段） | `{band, hatch_shift, line_alt}` | 157 | **67** | `step-0626-in.png`（semantic 24） | **56** |

* 跨时刻那一行的 **61 = 50（walk 相位）+ 11（尾部残留）**，
  且逐格族名对与 wave-13 报告**逐项相同**
  （`edge→hatch` 38 / `hatch→edge` 6 / `line_alt→edge` 2 / `line_alt→hatch` 2 /
  `line_alt→solid` 2 / 尾部 `edge→solid` 8 / `hatch→solid` 2 / `band→solid` 1）
  ⇒ **本流独立复现了 wave-13 的那个数**；
* 同刻那一行 = **67 = 56 + 11**，逐格族名对是
  `edge→hatch_shift` 36 / `hatch→edge` 6 / `hatch→hatch_shift` 4 / `solid→hatch_shift` 4 /
  `edge→band` 2 / `hatch→solid` 2 / `line_alt→edge` 2 / `line_alt→hatch_shift` 2 /
  尾部 `edge→solid` 8 / `band→solid` 1；
* 两侧都是 **192 / 192 点亮格、0 格缺失、0 格多画** ⇒ 差别**只在族名**。

⇒ **给父代理的一句话**：报告里「walk 相位 50 格（`field`）」应当改成
**「同刻口径 56 格（连尾部 67 格）：原版结算段画『移动可达集（青）』、重制画『合法目标（绿）』；
组合『青 + 橙』在重制侧结构上不可达 ⇒ 产品缺一段演出，不是 walk 没走到」**。
（⛔ **改口径是 V3 / Z4 的活**（`tools/s49_package/classify_overlay_cells.py` 与报告生成器），
本流**未改**任何分类文件。）

---

## 4. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| V1 | `$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-v4'; python tools/mgba_probe/build.py` | 私有探针 | exit 0；`built …\mgba-probe-v4\mgba-probe.exe (1372672 bytes)`；**共享 `build/mgba-probe/` 未动**（mtime 仍 2026-10-23 23:21:42） |
| V2 | `python tools/s49_z3_bound/z3record.py --side both --out build/s49-v4/walk --exe build/mgba-probe-v4/mgba-probe.exe` | 录到密集 walk（**当前 ROM，钉住**） | 原版 **553**（11.4 s，指纹 `ffa679a0…`）/ 重制 **783**（12.6 s，指纹 `b91900e7…`）；重制 ROM sha `fb9d2dbd…`（**钉住的字节副本**） |
| V3 | `python tools/s49_z3_bound/z3record.py --side both --out build/s49-v4/walk-b --remake-rom build/s49-v4/walk/pinned/remake.gba --original-rom build/s49-v4/walk/pinned/original.gba` | 第二次独立录制（同一钉住 ROM） | 原版 **553** / 重制 **783**，**指纹逐字节相同** |
| V4 | `python tools/s49_z3_bound/z3bound.py --walk build/s49-v4/walk --walk-id rom-fb9d2dbd-dense-walk --out build/s49-v4/bound-A.json` | **新下界** + 交叉核对 | **floor_sum = 16,350**；canonical **91,201**；383 distinct；**`pair.beat_floor` 交叉核对 `agrees=True`**；106 s |
| V5 | 同上，`--walk build/s49-v4/walk-b --out build/s49-v4/bound-B.json` | 两次跑逐字节一致 | **16,350 / `agrees=True`**；`bound-A.json` 与 `bound-B.json` sha256 **同为 `7871453668723df1c59f6859c257593edb7a7f3fdc2871cdcaebea917e410bc0`** |
| V6 | `python tools/s49_z3_bound/z3bound.py --walk build/s49-z3-bound/walk --out build/s49-v4/bound-control-z3walk.json` | **控制实验**：同一份代码在 Z3 的录制上 | **16,389** / canonical **90,993** / 387 distinct / `agrees=True` ⇒ **逐值复现 Z3** ⇒ 16,389 → 16,350 的差**来自 ROM** |
| V7 | `python tools/s49_z3_bound/z3bound.py --walk build/s49-pairing/walk5 --out build/s49-v4/bound-control-walk5.json` | **控制实验**：同一份代码在 wave-5 的录制上 | **23,753** / canonical **111,587** / 350 distinct / `agrees=True` ⇒ **逐值复现 X2** ⇒ 23,753 → 16,350 的差**来自 ROM** |
| V8 | `python tools/s49_pairing/pairing_report.py --walk build/s49-v4/walk --out build/s49-v4/pairing --no-floor` | 内容锚配对（B2 可达上界） | 同刻 **21 / 25**（84 %）；`residual_at_match_sum` = **18,861**；配对差下界 **4 帧** ⇒ **16,350 ≤ opt ≤ 18,861**（**只读调用**配对流的仪器） |
| V9 | `python tools/s49_z3_bound/v4phase.py --walk build/s49-v4/walk --out build/s49-v4/phase-v4.json` | **50 格相位归因** | 原版 1 段（frames 486–552，67 采样点，b22–b24，相机 152→240）；重制 **0** 段；`青∧橙` 重制 **0** / 原版 **67**；同刻对照 67 格 / 跨时刻对照 61 格（= 50 + 11） |
| V10 | 同上，`--out build/s49-v4/phase-v4-b.json` | 两次跑逐字节一致 | sha256 **同为** `4f882b68bd7f00beea4cdb9b0130db66d597ae6c60bf013b70bb3066ab8fcae9` |
| V11 | 孤儿进程复查 `Win32_Process` | 无残留 | 两次录制后各查一次：**0 个** `mgba-probe.exe` |
| V12 | **独立复现 wave-13 的「50 格」** | 同口径复现 | 本流同刻/跨时刻两套对照的**跨时刻**那一行 **61 格、逐格族名对与 wave-13 逐项相同** |
| V13 | 编码自检 | 新文件 LF、无 BOM | 见 §8 |
| V14 | `git status --short` | 未提交、不碰别人的文件 | 只新增 `tools/s49_z3_bound/v4phase.py` 与本笔记（`tools/s49_z3_bound/`、`notes/s49-fidelity/` 整目录本来就是未跟踪）；**未提交 git** |

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| V4-1 | Z3 的 16,389 可以沿用到当前 ROM | 比 ROM sha + 重录 | **不行**：Z3 测于 `2c2b48d9…`，当前盘上是 `fb9d2dbd…` ⇒ **重算** | **已证伪** |
| V4-2 | 新下界与 16,389 的差来自**算法漂移**而不是 ROM | **同一份代码**在 Z3 的录制上重算 | **16,389**（逐值复现，含 canonical 90,993 / 387 distinct）⇒ 差来自 ROM | **已证伪（差来自 ROM）** |
| V4-3 | 新下界与 23,753 的差来自算法漂移 | **同一份代码**在 wave-5 的录制上重算 | **23,753**（逐值复现）⇒ 差来自 ROM | **已证伪（差来自 ROM）** |
| V4-4 | 当前 ROM 的可证下界 = 16,350 | 25 拍 × 全帧逐对取最小求和 + 与 `pair.beat_floor` 交叉核对 | **16,350**；`cross_check.inherited_floor_sum = 16350`，`agrees=True` | **已确认** |
| V4-4b | 新下界与 B2（内容锚同刻配对 18,861）不矛盾 | 两者的口径差异（前者放宽到全帧配对，后者是同一时刻的配对） | **16,350 ≤ 最优 ≤ 18,861**，区间宽 2,511 ⇒ 真值被夹住 | **已确认** |
| V4-5 | 原版侧不用重录（ROM 未变） | 实录并逐字节比指纹 | 新录 553 帧与 Z3 的、`walk5` 的**逐字节相同**（同一指纹 `ffa679a0…`）⇒ 复用被再次坐实 | **已确认** |
| V4-6 | 「青 + 橙同现」是 **walk** 能取到的 | ① 读重制侧规则源码；② 在 783 帧上统计同框 | 规则里 `move` 与 `attack_range` 的 `move_phase` 条件**互斥**；渲染器每帧整块重画；实测 `青∧橙` = **0/783** ⇒ **结构上不可达** | **已证伪（不是 walk 问题）** |
| V4-7 | 「重制缺一个相位」= 重制**没走到**那一段 | 在重制侧密集 walk 上找原版相位的对应段 | 重制**走到了**结算段（semantic 24–30，157 帧、192 点亮格、光标 + 橙都在）⇒ **段是走到的**，差的是族名 | **已证伪** |
| V4-8 | 原版那一帧是某个**活相位** | 比原版自己的活相位帧 | 活相位里青与橙从不同时出现（移动相位零橙零黄零绿；目标相位只有绿）⇒ `field` 帧的青+橙同框是**缓冲残迹**；且 `field` 的受阻格 **83** = 移动相位的 **83** | **已证伪（是相位残留）** |
| V4-9 | wave-13 的「50 格」是**同刻**比出来的 | 读 `cell-classification.json` 的最佳匹配帧 | 最佳匹配帧 = `step-26-A`（**移动相位**的纯青帧）⇒ **跨时刻**；同刻口径是 **56 格（连尾部 67）** | **已证伪（是跨时刻）** |
| V4-10 | 本流能独立复现 wave-13 的那个数 | 同口径逐格对照 | 跨时刻对照 = **61 格**（= 50 + 11），逐格族名对与 wave-13 **逐项相同** | **已确认** |
| V4-11 | 两次跑逐字节一致 | 独立录制 + 独立计算，比 sha256 | 帧指纹、下界收据、相位收据**三者都逐字节相同** | **已确认** |
| V4-12 | recorder 会吃 7–8 GB 并泄漏 | 实测两次全量录制 + 孤儿进程复查 | 两段录制各 7.5–12.6 s，孤儿探针 **0 个** ⇒ 本机未复现；仍**全程串行**，没有与 V1 同时开全量录制 | **已确认（未复现）** |
| V4-13 | 当前盘上的 ROM 就是任务书说的「最终 ROM」 | 比 sha + mtime + 看 V1/V2 独占文件的 mtime | 盘上是 `fb9d2dbd…`（mtime 19:18:31，= W1 的构建）；**V2 的独占文件自 19:17 起未被改写** ⇒ V2 尚未出新构建。**若 V1/V2 随后重建，必须重跑 §7 的三条命令** | **已确认（截至交回时）** |

---

## 6. 卡在哪 / 剩余风险（**不粉饰**）

1. ⛔ **下界 16,350 只对当前这两段录制成立**（原版 `1198ece7…` + 重制 `fb9d2dbd…`，
   stride 4）。**V1 / V2 一旦重建 ROM，这个数就过期** ⇒ 必须重跑 §7 的三条命令
   （约 3 分钟：录制 25 s + 下界 210 s + 相位 15 s）。
2. ⚠️ **V1 尚未交付**（`notes/s49-fidelity/V1-real-victory.md` 不存在）⇒
   任务 B 的「用 V1 的闭环走位定位那个相位」**没有走 V1 的闭环**，
   改用**原版/重制两侧的密集 walk 时间线 + 内容锚（相机 / 场景 / acting 指针）**
   定位。**结论不依赖 V1**：判定用的都是 Z3 已经坐实过的数据口径
   （同一个覆盖层解码器、同一个原版真值捕获）。
   ⛔ **但 V1 的闭环一旦把战斗真正打完**，重制侧会走到**本流 783 帧之外**的状态
   （比如真正的「目标选择」相位、真正的胜负结算）⇒ **那时的覆盖层相位表可能变**，
   §3.4 的清单应当重跑一次（`v4phase.py` 一条命令）。
3. ⚠️ **两侧的拍数不等**（对话段后原版 6 屏 / 重制 3 屏，结算段拍数也不同），
   所以「semantic beat」只是**近似对齐**；本流的同刻判定**不靠拍号**，
   靠的是「同一段（结算段）+ 同样的 192 点亮格 + 光标 + 橙都在」这三个**可观测**事实。
4. ⚠️ **原版的「相位残留」是推断，不是逐帧证明**：证据是
   （a）原版活相位里青与橙从不同框、（b）`field` 帧的受阻格数 **83** 与移动相位的 **83** 相同、
   （c）`field` 帧 6/6 逐格全等（Z3 已确认的稳定态）。
   **严格证明需要原版逐帧的缓冲写入序列**（逆向线范围，本流只读、且未做）。
   ⇒ 报告里应写「**证据一致地指向相位残留**」，不要写成「已证明」。
5. ⚠️ **「50 格 → 56 格」的口径修正没有落到分类文件里**：
   `tools/s49_package/classify_overlay_cells.py` 与报告生成器是 **V3 / Z4 的文件**，
   本流**未改** ⇒ 报告里现在还是旧口径。
6. ⛔ **没有做的事**：改重制侧任何一行（V2 的活）；把重制侧的覆盖层改成保留相位残迹；
   复现原版的 `grid16` 撕裂残影（Z3 已判定**不该**复现）；
   判定 `movegrid` 那 2 格产品差（Z3 已归为「单位站位不同」，本流未复核）。
7. ⚠️ **判定台读数与本流的下界不是同一口径**：判定台是**不带时刻约束**的 arg-min
   （35 帧基线走），本流的下界是 **25 拍 × 全帧**的放宽 ⇒ **不许**把 16,350 说成
   「判定台的下界」。

---

## 7. 复跑命令

```powershell
cd D:\Github\gba-naruto

# 0) 私有探针（**不要**覆盖共享的 build/mgba-probe/）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-v4'
python tools/mgba_probe/build.py

# 1) 密集 walk（先钉 ROM 再录；**串行**，不要与其它流同时开全量录制）
python tools/s49_z3_bound/z3record.py --side both --out build/s49-v4/walk `
    --exe build/mgba-probe-v4/mgba-probe.exe

# 2) 可证像素下界（自带与 pair.beat_floor 的交叉核对；不等就拒绝出数）
python tools/s49_z3_bound/z3bound.py --walk build/s49-v4/walk `
    --walk-id rom-fb9d2dbd-dense-walk `
    --label "final ROM fb9d2dbd (V4 dense walk)" `
    --out build/s49-v4/bound-A.json

# 3) 「缺一个相位」定位（逐帧时间线 + 共存统计 + 同刻逐格对照）
python tools/s49_z3_bound/v4phase.py --walk build/s49-v4/walk `
    --walk-id rom-fb9d2dbd-dense-walk `
    --out build/s49-v4/phase-v4.json

# 4) 内容锚配对（B2 可达上界；**只读调用**配对流的仪器）
python tools/s49_pairing/pairing_report.py --walk build/s49-v4/walk `
    --out build/s49-v4/pairing --no-floor

# 5) 两次跑逐字节一致（独立录制 + 独立计算，再比 sha256）
python tools/s49_z3_bound/z3record.py --side both --out build/s49-v4/walk-b `
    --exe build/mgba-probe-v4/mgba-probe.exe `
    --remake-rom build/s49-v4/walk/pinned/remake.gba `
    --original-rom build/s49-v4/walk/pinned/original.gba
python tools/s49_z3_bound/z3bound.py --walk build/s49-v4/walk-b `
    --walk-id rom-fb9d2dbd-dense-walk `
    --label "final ROM fb9d2dbd (V4 dense walk)" `
    --out build/s49-v4/bound-B.json
python tools/s49_z3_bound/v4phase.py --walk build/s49-v4/walk-b `
    --walk-id rom-fb9d2dbd-dense-walk `
    --out build/s49-v4/phase-v4-b.json
Get-FileHash build/s49-v4/bound-A.json,build/s49-v4/bound-B.json `
    -Algorithm SHA256
Get-FileHash build/s49-v4/phase-v4.json,build/s49-v4/phase-v4-b.json `
    -Algorithm SHA256

# 6) 控制实验（同一份代码在旧录制上重算 ⇒ 应得 16,389 / 23,753）
python tools/s49_z3_bound/z3bound.py --walk build/s49-z3-bound/walk `
    --out build/s49-v4/bound-control-z3walk.json
python tools/s49_z3_bound/z3bound.py --walk build/s49-pairing/walk5 `
    --out build/s49-v4/bound-control-walk5.json
```

---

## 8. 确认

* **新文件全部 LF、无 BOM**（`tools/s49_z3_bound/v4phase.py` 与本笔记；见 §9 的自检命令）。
* **未提交 git**。
* **未改重制线任何文件**（`D:\Shell\Github\gba-naruto-butano` **只读使用**；
  录制的重制 ROM 是它的**字节副本**；§3.5 引用的源码只是**读**）。
* **未改逆向线任何文件**（`D:\Shell\gba-naruto-reverse` 未触碰）。
* **未改其它流的仪器**：`tools/s49_pairing/`、`tools/s49_overlay_align/`、
  `tools/s49_fidelity_report/`、`tools/s49_rule_probe/`、`tools/s49_battle_balance/`、
  `tools/s49_package/` 一律**只读调用**；
  唯一的例外是 `tools/mgba_probe/build.py` 用 `KONOHA_PROBE_OUT` 编到了**私有目录**，
  **没有**动共享的 `build/mgba-probe/`。
* **没有伪造任何帧**：所有数字来自盘上的收据 / 证据文件。
* **并发约束遵守**：两段全量录制**串行**跑；跑完复查 `Win32_Process`：**0 个孤儿探针**。

---

## 9. 编码自检（LF、无 BOM）

```powershell
cd D:\Github\gba-naruto
$files = @(
  'tools/s49_z3_bound/v4phase.py',
  'notes/s49-fidelity/V4-bound-final.md')
foreach ($f in $files) {
  $bytes = [System.IO.File]::ReadAllBytes($f)
  $bom   = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
  $crlf  = ([regex]::Matches([System.Text.Encoding]::UTF8.GetString($bytes), "`r`n")).Count
  "{0,-44} BOM={1} CRLF={2} bytes={3}" -f $f, $bom, $crlf, $bytes.Length
}
```
