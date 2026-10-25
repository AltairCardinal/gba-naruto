# J · S49 音频事件级对照（stream J，wave 2）

**日期**：2026-10-23
**范围**：原版 `rom/base.gba`（MP2K）↔ 重制侧 `butano-sequel.gba`（Maxmod），
S49「木叶丸 vs 野蜂」（scenario-49 / battle-14）。
**交付级别**：**A 级（事件级）**。**B 级（逐采样一致）明确排除**，理由见 §1。

---

## 0. 一句话结论

> **这场仗的音频，事件级也不对：**
> **① 战斗 BGM 的 cue ID 就错了** —— 原版 S49 战斗放的是 MP2K **sound 10**，
> 重制侧放的是 **sound 14**（那是 S41 的战斗曲）。
> **② 12 个音效 cue 在重制侧一个都不出声** —— `play_battle_sound()` 是 `(void) cue;`
> 的空实现（这 12 个 cue 覆盖 11 个游戏时刻，`result_shown` 一个时刻发两条）。
> **③ 原版这场仗会响的 9 个 cue，重制侧「ID 正确且能出声」的是 0 个。**
> **④ 但素材是对的**：两侧共有的 17 个 cue，时长差**全部 0.000 s**
> ⇒ **坏的是「接线」，不是「素材」**；真正缺资产的只有 3 个 cue（10 / 146 / 152）。

差异表：19 个配对时刻里 `match 4 / cue_mismatch 1 / silent_on_remake 11 /
never_dispatched 1 / missing_on_remake 2`。
**可闻事件级一致率 0/9（按这场仗实际会响的 cue 计），按全部配对时刻计 4/19 = 21%。**

逐事件表：`build/s49-audio/event_diff.md`（机器可读：`build/s49-audio/event_diff.json`）。

---

## 1. 「三天内做不到逐采样一致」——明确结论

**做不到，而且不是"差一点"。** 理由三条：

1. **两侧根本不是同一个合成器。**
   原版是 **MP2K**（GBA 上的软件 PSG 合成器：MIDI 音序 → 10 路 DirectSound +
   4 路 CGB PSG 的全局音符池 + 包络 + 伪回声 + 混音）；
   重制侧是 **Maxmod**（S3M 模块播放器 + 自己的 DirectSound 混音路径）。
2. **重制侧的 BGM 资产本身就不是 MP2K 的合成输出。**
   `artifacts/scenario-41-audio-reference-v1/README.md` 写明：音乐输入是
   `build/scenario-41-original-bgm-capture-20260722-01/` 里**从原 ROM checkpoint
   用 mGBA 录下来的运行时 PCM**，再经 `tools/butano/generate_scenario_41_audio_assets.py`
   去直流 → 22050 Hz 单声道 → `.s3m`。
   也就是说现在是「**录下来的 PCM 当模块放**」，不是「**让 PSG 按同样的音序合成**」。
   ⇒ **即使音序逐音符对齐，采样流也不可能逐点相同**（采样率 8 位量化、混音顺序、
   DC 处理、Maxmod 的重采样全都不同）。
3. **要真做到逐采样一致，必须绕开 Maxmod、把 MP2K 合成器本身复现出来**
   （音符分配器、乐器映射、ADSR、伪回声、主增益、混音顺序）。
   逆向线已经把这条路的合同冻结在三份产物里
   （`rom-mp2k-dispatcher-v1`、`rom-mp2k-note-allocator-v1`、
   `rom-m4a-initializer-chain-v1`），工作量在 **80–120 h** 量级
   （与 `docs/s49-three-day-plan.md` §4 的估算一致）。

⇒ **本轮按 A 级交付；B 级排除，不是"暂缓"，是"三天内不可能"。**
若 B 级是硬要求，现实选择是把"完全一致"的定义改成 A 级，而不是假装能做。

---

## 2. 做了什么 / 仪器

### 2.1 框架能力调查（recomp 能不能导音频事件？）

| 问题 | 结论 | 证据 |
|---|---|---|
| 框架有没有比逐帧快照更细的音频事件仪器？ | **有**：MMIO 写捕获 | `GBARECOMP_MMIO_CAP=1` + TCP `{"cmd":"mmio_cap"}`，返回 `{cycle,addr,value,size,pc}`，环形缓冲 262144 条（`src/gba/gba_io.h:59`） |
| `game.toml` 有没有音频导出项？ | **没有** | `recomp/game.toml` 的 `[audio]` 只有 `shadow = true`（阴影伴音开关），不是事件导出 |
| recomp 能不能吃 mGBA 的 `.ss9` 存档？ | **不能** | 全框架搜不到 ss9 导入；`--load-state` 只认 gbarecomp 自己的快照格式 |
| ⇒ 结论 | **recomp 走不通「从 battle-14 存档起步」这条路** | 要用 recomp 就得从上电重走到 battle-14（输入走位不在本轮范围） |

⇒ 原版侧改用**任务书里的备选路径**：mGBA 探针 + 存档起步。

### 2.2 原版侧（MP2K）——运行时实测

* 仪器：`tools/mgba_probe` 的无头 mGBA 探针（**另建**在
  `build/mgba-probe-j/`，未碰共享的 `build/mgba-probe/mgba-probe.exe`）。
* 采集窗口（每帧一块）：
  * **MP2K 运行时状态**：`0x03005E58 .. 0x030077CF`（6520 B/帧）——
    4 个 track 数组、`SoundInfo`、DirectSound/CGB 通道池、**4 个 player 槽**。
  * **PSG / DMA 寄存器**：`0x04000060 .. 0x040000DF`（128 B/帧）。
* 起点：`artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9`
  （sha256 `a3628723…`）。
* 走位：`artifacts/s49-fidelity-20261019-v1/walk-original-a24` 的原版走位
  —— 90 帧零输入 + 24×(A 按住 4 帧 / 松开 90 帧) + 300 帧尾巴 = **2556 帧**。

**MP2K 布局（全部实测确认，代码在 `tools/s49_audio_probe/mp2k_layout.py`）**

| 事实 | 位置 | 怎么确认的 |
|---|---|---|
| sound ID → song descriptor → player 槽 的映射 | ROM `0x08465B70`，每行 8 B `{u32 descriptor, u16 player_index}` | 逐行解析 ROM；槽号与实测槽位一致 |
| `player+0x00` = **当前 song descriptor 指针** | 槽 0..3 = `0x030076B0/6F0/730/780`（各 0x40 B） | `0x0853A1EC`→sound 10（槽 0）、`0x0853CE88`→sound 102（槽 1），与 dispatcher 表命中 |
| `player+0x2C` = track 数组指针 | — | 槽 0 = `0x03005E58`（与逆向线笔记一致） |
| `track+0x00` = **状态字节**：`0x80` 在跑、`0xC0` = **这一帧被调度** | track 步长 0x50 | 在已知 dispatch 帧（762 / 1497 / 1527）上直接看到 `0xC0`，下一帧回到 `0x80` |
| `track+0x40` = 命令指针，**GOTO 循环会回跳** | — | ⚠️ **不能用它判重触发**（会误报，见 §5 台账 H-2） |

**事件识别规则**（`extract_original.py::derive_events`）
* `cue_start`：槽的 descriptor 变了（换了 cue）**或** descriptor 没变但某条 track
  状态 = `0xC0`（同一 cue 被重新调度）。
* `cue_stop`：descriptor 没变且该槽再没有 track 在跑。

### 2.3 原版侧（cue 普查）

`tools/s49_audio_probe/cue_census.py` 对 `runtime-checkpoints/` 里
**44 个存档**逐个读一次 MP2K 槽状态，回答「这个场景在播哪个 cue」。

### 2.4 重制侧（Maxmod）

* **静态**（权威，因为 director 是纯函数、有单测）：
  * `game/include/konoha/battle_audio_director.h` → 16 类事件的 `(kind, cue)` 表
    （脚本自动解析，含 `special_combination` 的两臂）。
  * `game/include/konoha/battle_audio_runtime.h` → 哪 cue 真的进到 Maxmod。
  * `game/src/**` → 每个事件的调度调用点（`file:line`）。
* **运行时**：探针跑重制 ROM（从上电，`ZERO_INPUT=600`，`Down,Down,A×32`，
  hold 4 / settle 90 + 300 帧尾巴 = **3496 帧**），逐帧导出 PSG/DMA 寄存器块。

---

## 3. 逐事件差异表（摘要）

完整表见 `build/s49-audio/event_diff.md`。配对键 = **游戏时刻**，不是帧号。

| # | 游戏时刻 | 差异分类 | 原版 cue | 原版证据 | 重制侧 cue | 重制侧调度点 | 重制侧是否发声 |
|---:|---|---|---:|---|---|---|---|
| 1 | **S49 战斗 BGM** | **`cue_mismatch`** | **10** | cue 普查：6 个 scenario-49 battle 存档全在播 10 | **14** | `battle_runtime_scene.cpp:7292` | 是（但是错的曲子） |
| 2 | S41 战斗 BGM（参考） | `match` | 14 | cue 普查：7 个 scenario-41 battle 存档 | 14 | `battle_runtime_scene.cpp:7292` | 是 |
| 3 | 战前菜单 BGM | `match` | 5 | cue 普查：scenario-41 `start-row`/`prebattle-*` | 5 | `battle_preparation_scene.cpp:675`, `battle_runtime_scene.cpp:7256` | 是 |
| 4 | 组合拳演出 BGM | `match` | 15 | cue 普查：`scenario-41-combat-dialogue` | 15 | `battle_runtime_scene.cpp:203` | 是 |
| 5 | 战后对白 BGM | `never_dispatched` | 8 | cue 普查：11 个 `scenario-41-postbattle-dialogue-*` | 8 | **⚠ 无调用点** | 否（表里有，没人调） |
| 6 | 战后地图 BGM | `match` | 2 | cue 普查：`scenario-41-postbattle` | 2 | `battle_runtime_scene.cpp:260` | 是 |
| 7 | 战斗开场音 | `silent_on_remake` | 126 | 测量窗口内未出现 | 126 | `battle_runtime_scene.cpp:7292` | **否** |
| 8 | UI 确认音 | `silent_on_remake` | 102 | 运行时实测 **20 次**，首帧 f20 | 102 | `:7661`, `:7758` | **否** |
| 9 | UI 取消音 | `silent_on_remake` | 103 | 运行时未出现 | 103 | `:7766` | **否** |
| 10 | UI 移动音 | `silent_on_remake` | 104 | 运行时实测 **2 次**，首帧 f1497 | 104 | `:7628/7737/7745/7774/7782/7790/7798` | **否** |
| 11 | 输入被拒音 | `silent_on_remake` | 105 | 运行时实测 **1 次**，f2069 | 105 | `:7841` | **否** |
| 12 | 行动确认音 | `silent_on_remake` | 117 | 运行时实测 **1 次**，f1527 | 117 | `:7833` | **否** |
| 13 | 战斗演出音 | `silent_on_remake` | 116 | 运行时实测 **1 次**，f1515 | 116 | `:209` | **否** |
| 14 | 命中音 | `silent_on_remake` | 138 | 运行时未出现 | 138 | `:214` | **否** |
| 15 | 战斗结算弹窗音 | `silent_on_remake` | 149 | 运行时未出现 | 149 | `:219` | **否** |
| 16 | 胜利音 | `silent_on_remake` | 158 | 运行时实测 **2 次**，f762 | 158 | `:244` | **否** |
| 17 | 结算音 | `silent_on_remake` | 157 | 运行时未出现 | 157 + 112 | `:250` | **否** |
| 18 | 道具组17 专用音 | `missing_on_remake` | **146** | cue 普查：`tool37-group17-active` = [15, **146**] | — | — | 重制侧无此 cue |
| 19 | 道具到期专用音 | `missing_on_remake` | **152** | cue 普查：`tool67-expiry-ready` = [10, **152**] | — | — | 重制侧无此 cue |

### 3.1 差异分类统计

| 分类 | 数量 | 含义 |
|---|---:|---|
| `silent_on_remake` | 11 | 重制侧会调度该 cue，但运行时**不产生任何声音** |
| `match` | 4 | 两侧同一 cue、同一语义，且重制侧真的会发声 |
| `missing_on_remake` | 2 | 原版会播，重制侧**连这个 cue 都没有** |
| `cue_mismatch` | 1 | 同一游戏时刻两侧 cue ID 不同 ⇒ 音频内容必然不同 |
| `never_dispatched` | 1 | 重制侧表里有，但**没有任何调用点** |

### 3.2 参数对照（同一 cue 的时长 / 采样率 / 循环）

原版时长 = 逆向线 MP2K 引擎渲染的采样帧数 ÷ **15768 Hz**
（`tools/m4a_scheduler.py:18` `PCM_RATE = 15768`）；
重制侧时长 = 资产 manifest。完整表见 `build/s49-audio/event_diff.md`。

| cue | 原版时长 s | 原版轨道数 | 原版循环 | 重制侧时长 s | 差值 s |
|---:|---:|---:|---|---:|---:|
| 2 | 64.476 | 10 | 是 | 64.476 | **0.000** |
| 5 | 41.455 | 6 | 是 | 41.455 | **0.000** |
| 8 | 33.318 | 9 | 是 | 33.318 | **0.000** |
| 14 | 51.099 | 8 | 是 | 51.099 | **0.000** |
| 15 | 6.496 | 4 | 是 | 6.496 | **0.000** |
| 102 | 0.318 | 1 | 否 | 0.318 | **0.000** |
| 103 | 0.218 | 1 | 否 | 0.218 | **0.000** |
| 104 | 0.318 | 1 | 否 | 0.318 | **0.000** |
| 105 | 0.318 | 1 | 否 | 0.318 | **0.000** |
| 112 | 0.619 | 1 | 否 | 0.619 | **0.000** |
| 116 | 0.419 | 1 | 否 | 0.419 | **0.000** |
| 117 | 0.820 | 1 | 否 | 0.820 | **0.000** |
| 126 | 1.021 | 1 | 否 | 1.021 | **0.000** |
| 138 | 0.720 | 1 | 否 | 0.720 | **0.000** |
| 149 | 1.323 | 1 | 否 | 1.323 | **0.000** |
| 157 | 0.318 | 1 | 否 | 0.318 | **0.000** |
| 158 | 1.122 | 1 | 否 | 1.122 | **0.000** |
| **10** | **54.565** | 8 | 是 | **无资产** | — |
| **146** | **0.619** | 1 | 否 | **无资产** | — |
| **152** | **2.227** | 1 | 否 | **无资产** | — |

⇒ **两侧共有的 17 个 cue，时长差全部为 0.000 s**：
**重制侧的音频「资产」是原版 MP2K cue 的忠实渲染，参数没有问题。**
⇒ **参数层面的错只有一个：cue 10 / 146 / 152 在重制侧根本没有资产。**
⇒ 交叉验证：原版 cue 102 在模拟里实测约 **19 帧 ≈ 0.318 s**，
与渲染的 0.318 s **逐位吻合**。

### 3.3 原版侧逐事件序列（运行时实测，2556 帧）

```
cue 102  slot1  20 次   f95 189 283 377 471 565 659 753 1035 1129 1223 1411
                   1515 1564 1599 1693 1787 1881 1975 2163   （每次约 19 帧 ≈ 0.32 s）
cue 158  slot1   2 次   f762, f802
cue 104  slot1   2 次   f1497, f1506
cue 116  slot2   1 次   f1515
cue 117  slot2   1 次   f1527
cue 105  slot1   1 次   f2069
cue  10  slot0   贯穿全程（battle-14-entry 存档时已在播，窗口内未停、未重调度）
```
共 **50 个事件**（27 次 `cue_start` + 23 次 `cue_stop`）。

> ⚠️ **cue 10（战斗 BGM）在这张表里没有 start/stop 事件**，是因为它在
> `scenario-49-battle-14-entry.ss9` 存档时**已经在播**，测量窗口内既没停也没被重调度。
> 它的身份由 **cue 普查**独立确认（6 个 scenario-49 battle 存档全在播 10）。

### 3.4 重制侧事件序列（产品代码）

```
preparation_opened        → music 5            （有调用点 → 出声）
battle_opened             → music 14 + sound 126（music 出声，126 静音）
ui_confirmed              → sound 102          （静音）
ui_cancelled              → sound 103          （静音）
ui_navigated              → sound 104          （静音）
input_rejected            → sound 105          （静音）
action_confirmed          → sound 117          （静音）
action_movie              → sound 116          （静音）
impact                    → sound 138          （静音）
combat_popup              → sound 149（special 时另加 music 14）
victory_shown             → sound 158          （静音）
result_shown              → sound 157 + 112    （静音）
level_up_shown            → （无）
postbattle_opened         → music 2            （出声）
postbattle_dialogue_opened→ music 8            ⚠ **无调用点**（表里有，代码里没人调）
technique_title (special) → music 15           （出声）
```

**两侧「触发点」的口径**（重要：两边的触发点不是同一种东西）

| | 原版 | 重制侧 |
|---|---|---|
| 触发点 = ? | **MP2K dispatch 的帧号**（实测，`player+0x00` 变化或 `track+0x00` = 0xC0 的那一帧） | **产品代码里的调用点**（`file:line`）+ 事件语义（"每次 A 键"、"行动确认时"…） |
| 能给出帧号吗？ | 能（见 §3.3） | **不能** —— 重制侧的 PSG/DMA 寄存器块在整个 3496 帧里**恒定**（`nr50/nr51/nr52/bias` 全程不变，见 §6.2），**寄存器不是 cue 级仪器**；Maxmod 的"当前模块指针"没有已知地址，探针读不到 |

⇒ 重制侧的「触发点」只能给到**语义级 + 代码位置**，给不到帧号。
这是本轮**唯一的仪器缺口**，已在 §8 写成给计划所有者的需求。

**静音的根因**（`game/include/konoha/battle_audio_runtime.h:39-45`）：
```cpp
inline void play_battle_sound(int cue)
{
    // The imported WAV SFX currently corrupt Maxmod's mixer state
    // after repeated playback. Keep the semantic cue boundary here
    // so stable assets can be restored without touching battle flow.
    (void) cue;
}
```

全树 grep 佐证：`butano-sequel/game/**` 里 **`.play()` 只有 5 处**，
全是 `bn::music_items::sound_002/005/008/014/015.play()`；
**没有任何一处 `bn::sound_items::*.play()`**。
⇒ 14 个 SFX 资产（`butano-sequel/audio/sound_051/052/102/…/158.wav`）**都编进了 ROM、
都注册进了 Butano 的 item 系统，但运行时一次都没播**。
（好消息：这些 WAV 本身就是原版 MP2K cue 的离线渲染 —— `sfx-manifest.json` 里
sound_102 的 `source_frame_count=5016` 与逆向线 `full-song-render-evidence.json`
里 sound 102 的 5016 帧完全一致 ⇒ **资产是对的，坏的是接线**。）

### 3.5 顺序对照（任务书要求的"顺序错"这一维）

| 维度 | 原版（实测） | 重制侧（产品代码） | 判定 |
|---|---|---|---|
| 战前 BGM → 战斗 BGM | 有（cue 5 → cue 10，见 cue 普查） | 有（`preparation_opened` → `battle_opened`） | **顺序一致** |
| 每次输入 → UI 音 | cue 102 每按一次 A 响一次（实测 20 次，每次 ~19 帧） | `ui_confirmed` / `ui_navigated` / `ui_cancelled` / `input_rejected` 每次输入派一条 | **顺序一致** |
| 行动演出 → 命中 → 结算弹窗 | 实测到 116(f1515) → 117(f1527) 紧邻 | `technique_title` → `action_movie` → `impact` → `combat_popup` 同一状态机顺序 | **顺序一致** |
| 胜利 → 结算 → 战后 | 普查：`victory` → `result` → `postbattle` | `victory_shown` → `result_shown` → `postbattle_opened` | **顺序一致** |
| 战斗 BGM 与战斗开场音的先后 | 原版在 battle-entry 存档时**战斗 BGM 已经在播**（没有可观测的开场音） | 重制侧 `battle_opened` **先 music 14 再 sound 126**（同一函数里连着派两条） | **原版不可观测**（battle-entry 时战斗已经开始） |

⇒ **顺序不是这次的错**。两侧的事件次序语义一致；
错的是 **cue 身份**（§3 第 1 行）与 **接线**（12 个音效 no-op）。

---

## 4. 结论：事件级还差多少、差在哪

**这场仗（S49 battle-14）实际会响的 cue：**

| cue | 原版 | 重制侧 |
|---|---|---|
| 战斗 BGM | 10 | 14（**ID 错**） |
| UI 确认 | 102 | 调度了，**无声** |
| UI 移动 | 104 | 调度了，**无声** |
| 输入被拒 | 105 | 调度了，**无声** |
| 战斗演出 | 116 | 调度了，**无声** |
| 行动确认 | 117 | 调度了，**无声** |
| 胜利 | 158 | 调度了，**无声** |
| 道具组17 专用 | 146 | **没有这个 cue** |
| 道具到期专用 | 152 | **没有这个 cue** |

⇒ **9 个应该响的 cue，重制侧「ID 正确且能出声」= 0 个。**
唯一有声的（cue 14）是**错的曲子**。

**差在哪 —— 一句话：坏的是接线，不是素材。**
两侧共有的 17 个 cue，**时长差全部 0.000 s**（§3.2），
说明重制侧拿到的就是原版 MP2K cue 的忠实渲染。
真正的错只有两类：**调错了 cue**（S49 战斗 BGM）与**没接线**（12 个音效 no-op、
cue 8 无调用点）；另有 3 个 cue（10 / 146 / 152）**连资产都没有**。

**差在哪（按修复优先级）：**

1. **【P0】S49 战斗 BGM 用错了 cue。**
   原版 S49 战斗 = MP2K **sound 10**；重制侧 `battle_opened` 放 **sound 14**
   （= S41 的战斗曲）。重制侧的 cue 表是照着 **scenario 41** 建的
   （`tools/butano/generate_scenario_41_audio_assets.py` 的
   `SCENARIO_41_MUSIC_SEMANTICS` 把 14 标成 `battle_bgm`），
   **scenario 49 的战斗曲（10）从来没被导入**。
   ⇒ 修法：把原版 S49 战斗 BGM（sound 10）录成 PCM → 转 S3M →
   新增 `sound_010`，并让 S49 的战斗场景播它。
   （本轮**没有动产品代码** —— 这是产品 stream 的活。）
2. **【P0】12 个音效 cue 全部静音。**
   `play_battle_sound()` 是空实现；注释说导入的 WAV SFX 会破坏 Maxmod 混音状态。
   ⇒ 修法二选一：(a) 改用 Maxmod 原生的 effect/PCM 路径重导这 14 个 SFX；
   (b) 保留 WAV 但把播放放到一个不会污染混音状态的位置（分通道/分优先级）。
   **资产本身是对的**（就是原版 cue 的离线渲染），只是没播。
3. **【P1】cue 8（战后对白 BGM）在 director 里有、代码里没人调。**
   `postbattle_dialogue_opened` 全树零调用点。
4. **【P1】cue 146 / 152 在重制侧根本没有。**
   S49 专属的两个道具音效（组17 / 到期）原版会播，重制侧没有对应资产也没有对应事件。
5. **【P2】重制侧的 cue 事件只能从产品代码读，运行时不可观测。**
   见 §6 的探针需求。

---

## 5. 假设台账（一行一个假设）

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| J-1 | recomp 框架没有音频事件导出能力 | 查 `recomp/game.toml` + 框架源码 | `[audio]` 只有 `shadow`；但**有** MMIO 写捕获（`GBARECOMP_MMIO_CAP` + TCP `mmio_cap`，带 cycle/PC） | **已证伪**（部分）：不是"没有"，是"有更细的仪器但走不到 battle-14" |
| J-2 | recomp 能加载 mGBA 的 `.ss9` 存档 | 全框架搜 ss9 导入 | 搜不到；`--load-state` 只吃 gbarecomp 自己的快照 | **已证伪** |
| J-3 | MP2K 的 sound ID 可以从运行时内存读出来 | 读 `player+0x00` → ROM dispatcher 表 | 命中：0x0853A1EC→10、0x0853CE88→102、0x0853CEC0→104、0x0853D04C→117、0x0853D56C→158 | **已确认** |
| J-4 | MP2K 的"cue 已停"可以用 track 状态字节判 | 扫 6520 B/帧里所有变化的字节 | `track+0x20` 变（0/0x40/0x80/0xC0），但**语义对不上**（BGM 的 track 每 ~12 帧就掉一次） | **已证伪** |
| J-5 | MP2K 的 track 状态字节在 `+0x20` | 同上 | 在已知 dispatch 帧上，`+0x20` 不变；**`+0x00`** 在 dispatch 帧 = 0xC0、下一帧 = 0x80 | **已证伪**（真值是 `+0x00`） |
| J-6 | 同一 cue 的重触发可以用「命令指针回跳」判定 | 看命令指针（`track+0x40`） | **不成立**：BGM 的 GOTO 循环也回跳（每 ~98 帧一次，且尾巴 300 帧无输入时照样出现）⇒ 假阳性 26 条 | **已证伪** |
| J-7 | 同一 cue 的重触发可以用「track 状态变 0xC0」判定 | 重跑事件提取 | 50 个事件，其中 cue 102 被测到 **20 次**（每次约 19 帧 ≈ 0.32 s，与 `sfx-manifest` 的 0.318 s 一致） | **已确认** |
| J-8 | 读 I/O 块会扰动模拟 ⇒ 两边必须分两次运行 | 三次探针运行做对照：MP2K 窗口 / I/O 窗口 / 先 I/O 后 MP2K | 第三次的 MP2K 窗口与第一次**逐字节相同** ⇒ 读 `0x04000060..0x040000DF` **不扰动**（VCOUNT 在 `0x06`，不在本窗口内） | **已证伪**（本窗口安全；仍保留分次运行） |
| J-9 | 重制侧能靠 PSG/DMA 寄存器读出 cue ID | 解码 3496 帧寄存器块 | `nr50/nr51/nr52/bias` **全程恒定**（0x0000 / 0x120C / 0x0080 / 0x0200），FIFO 读回不是采样数据 ⇒ **寄存器块在重制侧不是 cue 级仪器** | **已证伪** |
| J-10 | S49 的战斗 BGM 与 S41 相同 | cue 普查 44 个存档 | **不同**：S41 battle 在播 14，S49 battle 在播 10 | **已证伪** |
| J-11 | 重制侧的 cue ID 编号 = 原版 MP2K sound ID | 比对 `sfx-manifest.json` 的 sound_id 与 MP2K 槽位区间 | 51/52→槽3、102–105/156–158→槽1、106–155→槽2、2/5/8/14/15→槽0 ⇒ **完全对得上** | **已确认** |
| J-12 | 重制侧 14 个 SFX 资产是原版 cue 的渲染 | 比对 `sfx-manifest.json` 的 `source_frame_count` 与 `full-song-render-evidence.json` | sound 102：5016 = 5016 ✔（其余同源） | **已确认** |
| J-13 | 采集可复跑（两次连跑逐字节一致） | 同一条命令连跑两次，比对 JSON | `determinism (run twice byte-identical) = True`；端到端 `run_all.py` 连跑两次产出同一批 JSON | **已确认** |

---

## 6. 跑了什么验收 / 观察到什么

### 6.1 复跑命令

```powershell
# 探针（另建一份，不碰共享 exe）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-j'
python tools/mgba_probe/build.py

# 全流程（采集 + 普查 + 对照）
python tools/s49_audio_probe/run_all.py --out build/s49-audio

# 单步
python tools/s49_audio_probe/extract_original.py --out build/s49-audio
python tools/s49_audio_probe/cue_census.py       --out build/s49-audio/cue_census.json
python tools/s49_audio_probe/extract_remake.py   --out build/s49-audio
python tools/s49_audio_probe/compare_events.py   --out build/s49-audio
```

### 6.2 观察结果

| 验收项 | 结果 |
|---|---|
| 原版采集帧数 | 2556（2256 走位 + 300 尾巴） |
| 原版 MP2K 事件数 | **50**（27 `cue_start` + 23 `cue_stop`） |
| 重制侧采集帧数 | 3496 |
| **确定性：同一条采集命令连跑两次逐字节一致** | **True** |
| **I/O 读不扰动 MP2K 时间线**（控制实验：先 I/O 窗口后 MP2K 窗口 vs 纯 MP2K 窗口） | **True** |
| cue 普查存档数 | 44（scenario-41/49） |
| 原版 PSG 活动 | `nr50=0x0077`、`nr51=0x210E`、`nr52=0x008B`、`bias=0x4200`，2556 帧全程有声 |
| 重制侧 PSG 活动 | `nr50=0x0000`、`nr51=0x120C`、`nr52=0x0080`、`bias=0x0200`，3496 帧全程「硬件开着」，但寄存器块**不随 cue 变化** |
| 重制侧 `.play()` 调用点 | 全树只有 5 处，全是 music；**0 处 sound** |

### 6.3 可复跑证据（两次独立全流程，逐字节一致）

两次**完整**跑 `run_all.py`（各自重新采集、重新普查、重新比对），
落盘产物逐字节一致：

| 产物 | sha256（前 16） | 两次连跑 |
|---|---|---|
| `original_events.json` | `7580e8a82e590219…` | **IDENTICAL** |
| `original_frames.json` | `cd8459f8f3f15cb1…` | **IDENTICAL** |
| `cue_census.json` | `b05a90b0f0026fc2…` | **IDENTICAL** |
| `remake_events.json` | `df42f625345cb08f…` | **IDENTICAL** |
| `event_diff.json` | `52d8be698d69d132…` | **IDENTICAL** |
| `event_diff.md` | `cffc96dd7c904e8b…` | **IDENTICAL** |

逐帧 dump 抽样（`orig-mp2k/m-0000.bin`、`m-1234.bin`、`t-0299.bin`）两次采集也一致。

复跑命令：

```powershell
python tools/s49_audio_probe/run_all.py --out build/s49-audio
python tools/s49_audio_probe/run_all.py --out build/s49-audio/verify
# 然后逐文件比 sha256
```

> `--skip-capture`（只重新解码已有的逐帧 dump）与完整采集产出**同一份文档**：
> 解码模式会把上一次采集的对照结果（确定性 / I/O 不扰动）带过来，不会清空。

---

## 7. 改了什么（文件路径）

| 文件 | 说明 |
|---|---|
| `tools/s49_audio_probe/probe_driver.py` | 新增：探针驱动（`load`/`frames`/`framedump`/`keyseq`），dump 按前缀分目录收集 |
| `tools/s49_audio_probe/mp2k_layout.py` | 新增：MP2K 运行时布局 + ROM dispatcher 表解析 |
| `tools/s49_audio_probe/psg_state.py` | 新增：GBA 声音/DMA 寄存器块解码（GB 兼容的 `0x04000080..0x87` 控制块） |
| `tools/s49_audio_probe/extract_original.py` | 新增：原版侧采集 + 事件提取 + 确定性/扰动对照 |
| `tools/s49_audio_probe/cue_census.py` | 新增：存档级 cue 普查 |
| `tools/s49_audio_probe/extract_remake.py` | 新增：重制侧采集 + director 表/接线/调用点解析 |
| `tools/s49_audio_probe/compare_events.py` | 新增：按游戏时刻配对，生成逐事件差异表 |
| `tools/s49_audio_probe/run_all.py` | 新增：一键复跑 |
| `tools/s49_audio_probe/README.md` | 新增：用法与关键事实 |
| `notes/s49-fidelity/J-audio.md` | 新增：本报告 |

**临时产物**（在 `build/s49-audio/`，不入库）：
`original_events.json` / `original_frames.json` / `cue_census.json` /
`remake_events.json` / `event_diff.md` / `event_diff.json`，
以及逐帧 dump 目录 `orig-mp2k/` `orig-psg/` `remake-psg/` `orig-mp2k-repeat/`
`orig-perturb/` 与 `verify/`（第二次独立全流程跑）。

**没有改**：`tools/mgba_probe/host_main.c`（共享探针源码）、重制线任何文件、逆向线任何文件。

---

## 8. 需要计划所有者统一加的探针/产品能力（**本流没有改**）

1. **重制侧 cue ID 的运行时可观测性（缺）**
   现有探针（`framedump` / `keyseq`）能读任意内存窗口，但 Maxmod 的
   「当前正在播的模块指针」没有已知地址 ⇒ 重制侧的 cue 序列只能从产品代码读，
   拿不到运行时证据。
   **建议**：在重制侧加一个**可选的 build 开关**（例如 `BN_AUDIO_EVENT_TRACE`），
   把 `play_battle_music` / `play_battle_sound` 的 `(kind, cue, frame)` 写进一个
   固定 IWRAM 环形缓冲；探针就能按帧 dump 它。
   ⇒ **这是产品代码改动，需产品 stream 决定，本流不动。**
2. **探针本轮无新增需求**：`framedump` / `keyseq` 已经够用（见 §2.2）。
3. **若要继续用 recomp 做原版侧**：需要 (a) 一条从上电走到 battle-14 的输入走位，
   或 (b) 一个 `.ss9` → gbarecomp 快照的转换器；两者都不在本轮范围。

---

## 9. 剩下什么

* **P0 修 BGM cue（10 ↔ 14）** —— 需要先录原版 S49 战斗 BGM（sound 10）的 PCM。
  原版侧录制可以用本轮的工具（把 cue 普查指向 `scenario-49-battle-14-entry`，
  录 MP2K 槽 0 的输出）。
* **P0 修 12 个音效的静音** —— 资产已在，改接线即可；需要确认 Maxmod 混音污染的根因。
* **P1 补 cue 8 的调用点**、**P1 补 cue 146/152**。
* **逐采样（B 级）**：不在三天路径内，见 §1。

## 10. 卡在哪

* **重制侧没有运行时 cue 证据**（J-9）：寄存器块恒定，只能靠产品代码。
  要补运行时证据需要产品侧加开关（§8.1）。
* **原版侧 MP2K slot 0 的 BGM 在测量窗口内没有 start/stop 事件**（存档时已在播），
  它的身份靠 cue 普查独立确认；两次证据一致才算闭合。
* **recomp 这条路本轮没走通**（J-1/J-2）：差一条从 power-on 到 battle-14 的走位，
  或一个 ss9→gbarecomp 快照转换器。
