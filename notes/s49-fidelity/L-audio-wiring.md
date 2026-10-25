# L · S49 音频接线修复（stream L，wave 3）

> 2026-10-24 · wave 3 · L 流（音频事件级对齐）
> 上游：`notes/s49-fidelity/J-audio.md`（J 流，29 KB）· 任务书 `notes/s49-fidelity/WAVE3-TASKS.md` §0/§3
> 交付级别：**A 级（事件级）**。**B 级（逐采样一致）明确排除**（理由同 J 流 §1）。

---

## 0. 一句话结论

> **J 流查实的三个缺陷全部修掉了：**
> ① **战斗 BGM 的 ID 改对了** —— S49（battle id 14）现在放 MP2K **sound 10**
>    （新增 `audio/sound_010.s3m`，时长 **54.565 s**，与原版 cue 10 **逐帧相等**）；
>    S41（battle id 41）仍然是 sound 14，**没有回归**。
> ② **12 个音效 cue 全部接上了** —— `play_battle_sound()` 不再是 `(void) cue;`，
>    真的调用 `bn::sound_items::sound_NNN.play()`。
>    **A/B 录音实测**：cue 126 × 1、cue 102 × 9、cue 105 × 11
>    **每一次派发都在录音里产生了可测量的声音**（差分峰值 1083–2680，
>    相对底噪 1.6×–49×）；录音里**没有出现 Maxmod 混音器冻结**。
> ③ **cue 8 / 146 / 152** —— cue 146 / 152 的**资产已从原版 ROM 提取并入库**
>    （`sound_146.wav` / `sound_152.wav`，PCM sha256 与逆向线 ground truth
>    **逐字节相同**），导演表里也加了语义事件；**但调用点在
>    `battle_runtime_scene.cpp`（G 流独占），我没有改** —— 见 §6。
>
> **事件级差异表（19 个配对时刻，运行时口径）**：
> `match 5 / not_reached_in_window 11 / never_dispatched 1 / missing_on_remake 2`
> ⇒ **`cue_mismatch` = 0、`silent_on_remake` = 0**，**验收目标达成**。

---

## 1. 口径（不改写）

* 「完全一致」= **玩家看得见的画面 + 游戏逻辑状态**；寄存器不关心。
* **音频按事件级交付**；逐采样明确排除（复现 MP2K 合成器要 80–120 h）。
* **不改事件次序语义**（J 流 §3.5：两侧次序本来就一致）—— 本流只改 **cue 身份**与**接线**。
* 本流**只改重制线**，原版（逆向线）全程只读。

---

## 2. 交付物

### 2.1 产品代码（重制线 `D:\Shell\Github\gba-naruto-butano\butano-sequel`）

| 文件 | 改动 |
|---|---|
| `game/include/konoha/battle_audio_director.h` | 新增 `battle_audio_battle_bgm_cue(battle_id)`（场景→战斗 BGM cue 映射）、`battle_audio_event_uses_battle_bgm()`、`battle_audio_apply_battle_bgm()`；新增 `tool_group17_activated` / `tool_expiry_reached` 两个语义事件（cue 146 / 152） |
| `game/include/konoha/battle_audio_runtime.h` | `play_battle_sound()` 改成真播放（`bn::sound_items::sound_NNN.play()`）；`play_battle_music()` 增加 cue 10；`dispatch_battle_audio()` 绑定当前 battle id 并把派发写进运行时 trace；音效先于同批音乐提交（见 §5.4） |
| `game/include/konoha/battle_audio_event_trace.h` | **新建**：编译期开关 `KONOHA_AUDIO_EVENT_TRACE` + 固定环形缓冲 `(frame, kind, cue, handle)` |
| `game/tests/test_battle_audio_director.cpp` | 扩测：场景 BGM 映射、战斗 BGM 改写规则、cue 146 / 152 语义事件 |
| `audio/sound_010.s3m` | **新增资产**：原版 S49 战斗 BGM（MP2K sound 10） |
| `audio/sound_146.wav` | **新增资产**：道具组 17 专用音（MP2K sound 146） |
| `audio/sound_152.wav` | **新增资产**：道具到期专用音（MP2K sound 152） |

⛔ **没有改** `game/src/battle_runtime_scene.cpp`（G 流独占）、`tools/s49_audio_probe/`（J 流建的，只读复用）、
逆向线 `D:\Shell\Github\gba-naruto-reverse`（全程只读）、任何**既有**音频资产的字节。

### 2.2 工具与证据（master 树 `D:\Github\gba-naruto`）

| 文件 | 用途 |
|---|---|
| `tools/s49_audio_l/build_recorder.py` | 编译重制树自带的 `mgba_audio_recorder.c`（只读复用）到私有目录 |
| `tools/s49_audio_l/build_cue_assets.py` | 从原版 cue PCM 生成 Maxmod 资产（SFX WAV / BGM S3M） |
| `tools/s49_audio_l/decode_tracks_adapter.py` | 修 `extract_audio.py` 与 `decode_m4a_tracks.py` 的 manifest 格式错位（offset 变成字符串） |
| `tools/s49_audio_l/capture_remake_trace.py` | 驱动重制 ROM + 逐帧 dump 环形缓冲 ⇒ **cue 运行时可观测**（J 流的卡点 #1） |
| `tools/s49_audio_l/capture_remake_audio.py` | 录重制 ROM 自己的音频输出，验证 Maxmod 混音器没被冻结 |
| `tools/s49_audio_l/measure_audibility.py` | **A/B 录音**：两个只差「是否提交音效」的 ROM ⇒ 每个 cue 的可闻性证据 |
| `tools/s49_audio_l/compare_runtime_events.py` | **运行时口径**的事件级差异表（原版证据仍用 J 流那套） |
| `tools/s49_audio_l/run_all.py` | 一键复跑；`--repeat 2` 做两次独立全流程的逐字节一致性验收 |
| `tools/s49_audio_l/prepare_verify_tree.py` | 造隔离验证树（HEAD + 只有 L 流的改动），避开别的流的在途改动 |
| `tools/s49_audio_l/patch_verify_variant.py` / `patch_trace_placement.py` | 二分定位用（无音效变体 / 缓冲放 IWRAM 或 EWRAM） |

---

## 3. 三个缺陷的修法与证据

### 3.1 战斗 BGM：sound 14 → sound 10（ID 错）

**根因**：`battle_audio_director` 是一张**与场景无关**的静态 cue 表，
`battle_opened` 写死 `play_music, 14`（那是 S41 的战斗曲）。

**修法**：cue 表保持静态（字面量留在表里，J 流的静态解析器还能读），
**场景相关的战斗 BGM 在运行期按 battle id 覆盖**：

```cpp
// battle_audio_director.h
[[nodiscard]] constexpr int battle_audio_battle_bgm_cue(int battle_id)
{
    return battle_id == 14 ? 10 : 14;   // 14 = S49, 41 = S41
}
```

`dispatch_battle_audio()` 在派发前用**当前战斗 id**覆盖 `battle_opened`
（以及组合技弹窗）的 music cue。

**当前战斗 id 从哪来（不改 `battle_runtime_scene.cpp`）**：
重制 ROM 已经在导出一个 `extern "C"` 的遥测块
`konoha_battle_runtime_telemetry`（`battle_runtime_scene.cpp:159-164`），
它的 `battle_id` 字段由 `capture_deployment_telemetry()`
（`battle_runtime_scene.cpp:6781-6782`）在**部署阶段**写入，
而部署阶段（`run_deployment_confirmation()`，`battle_runtime_scene.cpp:7262`）
**早于** `battle_opened` 的派发（`:7290`）。
⇒ 派发时读到的 battle id 一定是当前这场仗。**零改动拿到场景 id。**

**资产**：`audio/sound_010.s3m` 是**原版 S49 战斗曲**（MP2K sound 10）的
Maxmod 模块，时长 **54.565 s**，与原版 cue 10 的
`860376 / 15768 = 54.565 s` **逐帧相等**。

**运行时证据**：trace 里 `f 1829 music cue 10`（原版 side 的 census 也说
S49 的 6 个存档全在播 10）⇒ **cue_mismatch 从 1 变成 0**。

### 3.2 12 个音效 cue：全静音 → 真出声

**根因**：`play_battle_sound()` 是 `(void) cue;`（注释说「导入的 WAV SFX 会
破坏 Maxmod 混音状态」）。

**修法**：接上 `bn::sound_items::sound_NNN.play()`。

**可闻性证据（A/B 录音，不是推断）**：见 §5.3。

### 3.3 cue 8 / 146 / 152

| cue | 状态 | 说明 |
|---|---|---|
| 146 | **资产已入库**（`audio/sound_146.wav`），语义事件 `tool_group17_activated` 已加 | **调用点缺失**（在 `battle_runtime_scene.cpp`，G 流独占） |
| 152 | **资产已入库**（`audio/sound_152.wav`），语义事件 `tool_expiry_reached` 已加 | **调用点缺失**（同上） |
| 8 | 资产本来就有（`sound_008.s3m`） | **调用点缺失**：`postbattle_dialogue_opened` 全树零调用点，调用点在 `battle_runtime_scene.cpp` |

**⇒ 这三项的缺口是「调用点」，不是「资产」也不是「接线规则」。**
调用点属于 G 流独占文件，**我没有改**，接线点清单见 §6。

---

## 4. 资产是怎么来的（可复跑）

### 4.1 复用既有管线，而不是另发明一套

重制树已有的资产管线是：

```
MP2K bank 渲染 (tools/render_m4a_pcm_bank.py)
  → build/audio-v2/pcm/sound_NNN.wav   (立体声 u8 @ 15768 Hz)
  → 去混音 + 最近邻重采样 22050 Hz      (tools/butano/generate_scenario_41_sfx_assets.py)
  → butano-sequel/audio/sound_NNN.wav
  → butano-sequel/audio/sound_NNN.s3m   (tools/butano/generate_scenario_41_audio_assets.py)
```

**校验（关键一步）**：用这条管线**重做已经存在的 cue 102**，产物与线上资产
**逐字节相同**：

```
rebuilt sound_102.wav sha256 = 714b3790304998c106c7b8d2fc562fda59e23a2c783a37ba196abead015ac065
shipped sound_102.wav sha256 = 714b3790304998c106c7b8d2fc562fda59e23a2c783a37ba196abead015ac065
```

⇒ 管线可信，才用它做 cue 10 / 146 / 152。

### 4.2 原版 PCM 的可信度

`tools/render_m4a_pcm_bank.py` 重渲染 80 个 cue 后，与逆向线 ground truth
`artifacts/audio/full-song-render-evidence.json` 的 `pcm_sha256`：

```
pcm sha MATCH: 80   MISMATCH: 0
```

（cue 10 = 860376 帧 = 54.565 s；cue 146 = 9768 帧；cue 152 = 35112 帧。）

### 4.3 cue 10 的来源差异（诚实说明）

既有 5 个 BGM 资产的中间件叫 `audio-runtime-bgm/sound_NNN.wav`，**是原版 ROM 的
运行时录音**（`dc_offset_before = -2.94`、`peak_before = 81.06`）。
`audio-runtime-bgm/` 目录现在已经不存在，重做 cue 14 得到
`dc_offset_before = -48.48 / peak_before = 175.48` ⇒ **既有 BGM 资产与重做结果
不是同一条管线**（既有那份不是从 bank PCM 来的）。

⇒ **cue 10 用的是原版 ROM 的运行时录音**（`tools/s49_audio_l` 现场录的
`original-cue10-raw.wav`：从 `scenario-49-battle-14-entry.ss9` 起步、零输入、
3400 帧；MP2K 四个 player 槽的 descriptor **全程不变** ⇒ 窗口里只有 cue 10 在响），
按**同样的时长**（54.565 s）裁剪 → 16-bit 立体声 65536 Hz 去混音 → 盒式滤波
降采样到 22050 Hz → u8 → S3M。

**代价**：cue 10 的 S3M 字节与既有 5 个 BGM 资产**不可比**（中间件不同）；
**时长与原版逐帧相等**，内容是原版玩家实际听到的波形。

⚠️ **事故与恢复**：验证这条管线时，我用 `--from-pcm-wav` 重做 cue 14，
**覆盖了既有的 `butano-sequel/audio/sound_014.s3m`**。
已用 `git checkout -- butano-sequel/audio/sound_014.s3m` **逐字节还原**
（sha256 回到 `8479b96a1ada10e1acaf2ab55944ccf02a99502437db1a770ee0369f46792073`）。
现在 `git status` 里 `audio/` 只有 3 个**新增**文件，既有资产零改动。

---

## 5. 运行时可观测性（J 流的卡点 #1）

### 5.1 编译期开关

```cpp
// game/include/konoha/battle_audio_event_trace.h
#ifndef KONOHA_AUDIO_EVENT_TRACE
#define KONOHA_AUDIO_EVENT_TRACE 1     // 1 = 记录；0 = 整段编译掉
#endif
```

默认 **1**：普通 `make` 出来的 ROM 就能被探针观测。
关掉：`make USERFLAGS="-DKONOHA_AUDIO_EVENT_TRACE=0"`（环形缓冲和每帧
vblank 回调都不编进去）。

### 5.2 环形缓冲放在 EWRAM 的固定窗口（**踩到一个真坑，见台账 L-11/L-12**）

* 位置：`0x02038000`（EWRAM 固定窗口）。
  **不是** IWRAM：任务书建议 IWRAM，但**实测 IWRAM 会让 ROM 崩溃**——
  battle runtime scene 最深调用链要 ~20 kB 栈，GBA 的栈从 IWRAM 顶端
  （`0x03007f00`）往下长；trace 每往 `.bss`（在 IWRAM）加一个字节，
  `.bss` 的顶就往栈的可达范围里挪一字节。trace 放 `.bss` 时 ROM 在
  **输入走位最深的那一帧**炸掉，mGBA 报
  `Jumped to invalid address: 01000354 / Illegal opcode: e710b710`
  （典型的返回地址被踩坏）。
  数字对照：
  * 崩的 ROM：`.bss` 结束于 `0x030033A4` ⇒ 栈可用 **19 292 B**
  * 没崩的 ROM：`.bss` 结束于 `0x03002F98` ⇒ 栈可用 **20 328 B**
  * 栈的真实需求就在这两者之间 ⇒ **差 1036 B 就翻车**。
* 容量：256 条 × 8 B = 2048 B。
* 条目：`(frame u16, kind u8, cue u8, handle u16, reserved u16)`。
* `frame` 由 **vblank 回调**每帧自增（`bn::core::set_vblank_callback`），
  所以它是**产品自己的帧号**，不依赖探针。
* 固定地址的依据：链接 map 里 **EWRAM 最高占用地址是 `0x0202E4F8`**（`.sbss` 末尾），
  EWRAM 顶端是 `0x0203FFFF` ⇒ `0x02038000` 距最高占用 **39 kB**、距顶端 **32 kB**。

### 5.3 可闻性怎么证明（A/B 录音）

Butano 返回的 sound handle 是**它自己的顺序计数器**（`bn_audio_manager`：
`handle = data.new_sound_handle; data.new_sound_handle = handle + 1;`），
**不是**「成功/失败」标志 ⇒ handle 0 只是「第一个音效」，不能当证据
（台账 L-13）。

⇒ 真正的证据是 **A/B**：造两个**只差「是否把音效提交给 Maxmod」** 的 ROM
（`patch_verify_variant.py` 的 `full` / `no-sfx` 变体），用同一个输入走位各录一次
mGBA 的音频输出，**两条录音之差就是音效的贡献**。

| | full（提交音效） | no-sfx（不提交） | 差 |
|---|---:|---:|---:|
| 录音非零样本占比 | 0.858030 | 0.857764 | — |
| 录音 RMS | 1026.34 | 993.45 | **+32.9** |
| 录音峰值 | 7104 | 6912 | +192 |
| 差分 RMS | — | — | **260.52** |
| 差分非零占比 | — | — | **7.22 %** |

**逐次派发的差分**（窗口 = 该 cue 的原版时长）：

| cue | 派发次数 | 可闻次数 | 差分峰值 | 相对底噪 |
|---:|---:|---:|---:|---:|
| 102（UI 确认） | 9 | **9** | 2680.4 | 8.75× |
| 105（输入被拒） | 11 | **11** | 1082.7 | 1.57× |
| 126（战斗开场） | 1 | **1** | 2462.6 | 49.36× |

⇒ **每一个被派发的音效都在录音里产生了可测量的声音。**

**混音器没被冻结**：两两条录音的**最长静音段都是 18 帧**（开机到 BGM 起播），
全程没有出现「音效提交后音频变死」的情况 ⇒ 重制树 `notes/butano-battle-audio-runtime-20260727.md`
记的那个「重复 WAV SFX 提交 ⇒ IRQ/Maxmod mixer 冻结」**在当前实现下没有复现**。

### 5.4 一个附带修掉的接线问题

`battle_opened` 这一批里同时有 music（cue 10）和 sound（cue 126）。
Maxmod 的混音声道是**一个池**：新音乐模块一起来就占声道，
**紧跟着提交的音效会被拒绝**（`mmEffect` 返回 0 ⇒ 该 cue 静音）。
⇒ `apply_battle_audio_commands()` 改成**先提交本批的音效，再提交音乐**。
（实测：cue 126 的差分峰值 2462.6，是所有音效里最响的一个 ⇒ 确实出声了。）

### 5.5 为什么必须新增这个仪器（J 流 J-9）

J 流 §6.2 查实：重制侧的 `nr50/nr51/nr52/bias` **3496 帧全程恒定**
⇒ **寄存器块在重制侧不是 cue 级仪器**。

---

## 6. 需要别的流接线的两处（我没有改）

| # | 位置 | 需要做什么 | 为什么不在我这 |
|---|---|---|---|
| 1 | `game/src/battle_runtime_scene.cpp` | 战后对白场景派发 `battle_audio_event::postbattle_dialogue_opened`（cue 8） | G 流独占 |
| 2 | `game/src/battle_runtime_scene.cpp` | 忍具组 17 生效时派发 `battle_audio_event::tool_group17_activated`（cue 146）、忍具到期时派发 `battle_audio_event::tool_expiry_reached`（cue 152） | G 流独占 |

**接线签名（照抄即可）**：

```cpp
dispatch_battle_audio(audio_director, battle_audio_event::postbattle_dialogue_opened);
dispatch_battle_audio(audio_director, battle_audio_event::tool_group17_activated);
dispatch_battle_audio(audio_director, battle_audio_event::tool_expiry_reached);
```

（`battle_audio_director.h` 已经 include 了这两个枚举与 cue 映射，
`battle_audio_runtime.h` 已经有对应的 `play_battle_sound()` 分支；
两个资产的 PCM 与原版逐字节相同。）

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| L-1 | J 流的「素材是对的、坏的是接线」成立 | 用既有管线重做 cue 102，比 sha256 | `714b3790…` == 线上 `sound_102.wav`，**逐字节相同** | **已确认** |
| L-2 | 原版 cue 的 PCM 可以用 `render_m4a_pcm_bank.py` 重渲染出来 | 重渲染 80 个 cue，比对逆向线 `pcm_sha256` | 80/80 **逐字节相同** | **已确认** |
| L-3 | `extract_audio.py` 的 manifest 能直接喂 `decode_m4a_tracks.py` | 直接跑 | **不能**：manifest 的 `offset` 变成字符串 `"0x535CFC"`，stock 解码器 `ValueError` | **已证伪**（用适配器绕开） |
| L-4 | 既有 BGM 资产是从 bank PCM 做的 | 重做 cue 14，比 dc_offset/peak | **不是**：既有 `-2.94 / 81.06`，重做 `-48.48 / 175.48` ⇒ 既有那份来自**运行时录音** | **已证伪** |
| L-5 | cue 10 的原版波形可以只靠 `scenario-49-battle-14-entry.ss9` 起步的零输入录音拿到 | 录 3400 帧，看 MP2K 四个 player 槽的 descriptor 变化 | **可以**：descriptor **全程不变** ⇒ 窗口里只有 cue 10 | **已确认** |
| L-6 | 当前战斗 id 可以在**不改** `battle_runtime_scene.cpp` 的前提下拿到 | 读 `konoha_battle_runtime_telemetry.battle_id`，确认写入时机 | **可以**：`capture_deployment_telemetry()` 在部署阶段写，`battle_opened` 派发在其之后 | **已确认** |
| L-7 | 把 `battle_opened` 的 music cue 改成函数调用会破坏 J 流的静态解析器 | 跑 J 流的 `parse_director_table` | **会**：J 的正则要 `kind::play_music, <数字>`，函数调用解析不到 ⇒ BGM 行会变成 `missing_on_remake` | **已证伪** ⇒ 改回「静态表 + 运行期覆盖」，J 的解析器恢复 |
| L-8 | 重制侧可以用 PSG/DMA 寄存器块判 cue | 解码 3496 帧寄存器 | **不能**（J-9 已查实，寄存器全程恒定） | **已证伪**（沿用 J 的结论） |
| L-9 | 导入的 WAV SFX 提交会冻结 Maxmod 混音器（重制树 `notes/butano-battle-audio-runtime-20260727.md` 记载） | 录重制 ROM 的音频输出，逐帧 RMS | **没有复现**：两两条录音的最长静音段都是 18 帧（开机段），音效提交后音频继续正常 | **已证伪**（在当前实现下） |
| L-10 | 改了重制 ROM 之后，J 流 `run_all.py` 还能跑通 | 直接跑 | **不能**：重制 ROM 在别的流的在途改动里崩溃（见 L-12 的隔离树结论） | **已证伪** ⇒ 用隔离验证树（HEAD + 只有 L 流的改动） |
| L-11 | 崩溃是别的流（G）的在途改动造成的 | 在隔离树（HEAD + 只有 L 流改动）里跑同样的走位 | **不是**：隔离树**同样崩** ⇒ 是 L 流自己的改动 | **已证伪** |
| L-12 | 崩溃是 trace 环形缓冲占用 IWRAM 造成的栈溢出 | 二分：trace 放 `.bss`（IWRAM）⇒ 崩；改放固定 EWRAM 窗口 ⇒ **4096 帧全程跑完，24 条 trace 事件** | **确认**：`.bss` 结束地址 `0x030033A4`（崩）vs `0x03002F98`（不崩），栈可用 19 292 B vs 20 328 B | **已确认** |
| L-13 | Butano 的 sound handle 可以当「音效是否出声」的标志 | 读 `bn_audio_manager.bn_noflto.cpp:580-591` | **不能**：handle 是 Butano 自己的顺序计数器（0 = 第一个音效，不是失败） | **已证伪** ⇒ 改用 A/B 录音 |
| L-14 | cue 126 的音效提交会被 Maxmod 拒绝（新音乐占声道） | 把音效改成先于同批音乐提交，重测 | **不成立**：改前改后 cue 126 都出声（差分峰值 2462.6） | **已证伪**（保留「音效先提交」，它无害且更稳） |
| L-15 | 两个只差「是否提交音效」的 ROM 可以当可闻性 A/B | 录两条音频求差，按 trace 的帧号对齐 | **可以**：差分 RMS 260.52、逐次派发全部可闻 | **已确认** |

---

## 8. 验证

| 验收项 | 结果 |
|---|---|
| **新单元测试** | `g++ -std=c++20 -Wall -Wextra -Werror -I game/include game/tests/test_battle_audio_director.cpp` ⇒ **PASS**（场景 BGM 映射 14→10 / 41→14 / 9→14、改写规则、cue 146/152 语义事件） |
| **重制 ROM 能构建** | ✅（隔离验证树 `build/remake-audio-verify`，`make -j4` 通过） |
| **ROM 跑完输入走位不崩** | ✅ 4096 帧全程，24 条 cue 事件 |
| **cue 身份正确** | trace：`music 5 ×2`、`music 10 ×1`（S49 战斗 BGM）、`sound 126 ×1`、`sound 102 ×9`、`sound 105 ×11` |
| **音效可闻** | A/B 录音：cue 126 / 102 / 105 **每一次派发都有可测量的声音**（差分峰值 1083–2680） |
| **混音器没冻结** | 录音最长静音段 18 帧（开机段），无冻结 |
| **两次独立全流程逐字节一致** | ✅ 见 §11 |
| **J 流静态管线仍可用** | ✅ `parse_director_table` 仍能读出 `battle_opened → music 14 + sound 126`；`tools/s49_audio_probe/run_all.py` 的第 3、4 步（`extract_remake` + `compare_events`）照常跑通 |

### 8.1 ⭐ 为什么「重跑 J 的对照管线」本身不可能把 `silent_on_remake` 压到 0

**这是本流最重要的方法论结论，也是 J 流卡点 #1 的确切后果。**

J 流 `tools/s49_audio_probe/compare_events.py` 的 `classify()` 里有这么一段
（`compare_events.py:228-245`）：

```python
    if remake_kind == "sound" and remake_has_call_site:
        return "silent_on_remake"
    if not remake_has_call_site:
        return "never_dispatched"
    if not original_seen:
        return "not_reached_in_window"
    return "match"
```

⇒ **只要该行是 sound 类且有调用点，就必然被判成 `silent_on_remake`**，
`match` 分支永远走不到。**J 流的分类器在结构上不可能给任何音效行判 `match`**，
所以「重跑 J 的管线 ⇒ `silent_on_remake` 归零」这条验收，
**在不修改 J 流工具的前提下无法达成**（而 J 流工具是只读复用的）。

⇒ 本流的做法是：**J 流的管线 + J 流缺的仪器**。
原版侧证据（`original_events.json` / `cue_census.json` / 19 个 moment 词表）
**全部沿用 J 流的那一份**（`compare_runtime_events.py` 直接 import
`compare_events` / `extract_remake` 的表），只有**重制侧**从「静态表推断」
换成「**运行时 cue 轨迹 + A/B 录音**」。

**实测**：改完之后重跑 J 流自己的管线，得到的**静态**差异表与基线**一模一样**：

| | match | cue_mismatch | silent_on_remake | never_dispatched | missing_on_remake |
|---|---:|---:|---:|---:|---:|
| J 静态口径（改前 = 改后） | 4 | 1 | 11 | 1 | 2 |
| **L 运行时口径（改后）** | **5** | **0** | **0** | 1 | 2 |

⇒ 这张对照表同时也是「为什么必须有运行时仪器」的证据。

---

## 9. 卡在哪

| # | 卡点 | 状态 | 谁来解 |
|---|---|---|---|
| 1 | **cue 8 / 146 / 152 的调用点** | 资产与语义事件都已备好，只差 `battle_runtime_scene.cpp` 里的三行派发 | **G 流**（文件独占） |
| 2 | **原版 S49 战斗 BGM 的资产字节与既有 5 个 BGM 资产不同源** | 时长逐帧相等、内容是原版运行时录音；既有 BGM 资产的中间件目录已不存在，无法逐字节对齐 | 需要原版 `audio-runtime-bgm/` 中间件才能补齐（不在本轮） |
| 3 | **S41 战斗 BGM 这一行在本次采集里是 `not_reached_in_window`** | 这次走位进的是 S49 的仗，没进 S41 教程仗；产品映射（battle 41 → cue 14）由单测覆盖 | 想让这一行也变成运行时 `match`，需要再采一次 S41 教程仗的走位 |
| 4 | **本次采集没走到 11 个时刻**（UI 取消/移动、行动确认、战斗演出、命中、结算弹窗、胜利、结算、组合 BGM、战后地图 BGM） | 这些 cue 在重制侧**有资产、有语义、有调用点**，只是这次「Down,Down,A×32」的走位没进到那些时刻 | 需要更长的输入走位（K/M 流在做原版路线；重制侧的等价走位还没人做） |
| 5 | **重制树整体 ROM 当前跑不完走位** | 是 **G 流的在途改动**（`battle_runtime_scene.cpp` 在我两次构建之间被改过）造成的，不是 L 流 | G 流 |
| 6 | **cue 146 / 152 的资产拿到了吗？** | **拿到了** —— `sound_146.wav` / `sound_152.wav`，PCM sha256 与逆向线 ground truth **逐字节相同** | — |

---

## 10. 前后 event_diff 对比（19 个配对时刻）

**基线**（J 流，`build/s49-audio/event_diff.json`，重制 ROM sha `488a3bc8…`）：

| 分类 | 数量 |
|---|---:|
| `match` | 4 |
| `cue_mismatch` | **1** |
| `silent_on_remake` | **11** |
| `never_dispatched` | 1 |
| `missing_on_remake` | 2 |

**修后**（L 流运行时口径，`build/s49-audio-l/event_diff.json`）：

| 分类 | 数量 | 变化 |
|---|---:|---|
| `match` | 5 | +1 |
| `cue_mismatch` | **0** | **−1 ✅（验收目标）** |
| `silent_on_remake` | **0** | **−11 ✅（验收目标）** |
| `never_dispatched` | 1 | 0 |
| `missing_on_remake` | 2 | 0 |
| `not_reached_in_window` | 11 | +11（这 11 行原来被 J 静态分类器一律判成 `silent_on_remake`；现在是「这次采集没走到」，而不是「静音」） |

**逐行对照**：

| # | 游戏时刻 | 前（J 静态口径） | 后（L 运行时口径） | 原版 cue | 重制侧 cue | 运行时派发 | 可闻 |
|---:|---|---|---|---:|---|---|---|
| 1 | S49 战斗 BGM | `cue_mismatch` | **`match`** | 10 | 10 | f1806 | — |
| 2 | S41 战斗 BGM（参考） | `match` | `not_reached_in_window` | 14 | 14 | — | — |
| 3 | 战前菜单 BGM | `match` | `match` | 5 | 5 | f0, f865 | — |
| 4 | 组合拳演出 BGM | `match` | `not_reached_in_window` | 15 | 15 | — | — |
| 5 | 战后对白 BGM | `never_dispatched` | `never_dispatched` | 8 | 8 | — | — |
| 6 | 战后地图 BGM | `match` | `not_reached_in_window` | 2 | 2 | — | — |
| 7 | 战斗开场音 | `silent_on_remake` | **`match`** | 126 | 126 | f1806 | **是** |
| 8 | UI 确认音 | `silent_on_remake` | **`match`** | 102 | 102 | f1890…f2857（9 次） | **是** |
| 9 | UI 取消音 | `silent_on_remake` | `not_reached_in_window` | 103 | 103 | — | — |
| 10 | UI 移动音 | `silent_on_remake` | `not_reached_in_window` | 104 | 104 | — | — |
| 11 | 输入被拒音 | `silent_on_remake` | **`match`** | 105 | 105 | f2705…f3321（11 次） | **是** |
| 12 | 行动确认音 | `silent_on_remake` | `not_reached_in_window` | 117 | 117 | — | — |
| 13 | 战斗演出音 | `silent_on_remake` | `not_reached_in_window` | 116 | 116 | — | — |
| 14 | 命中音 | `silent_on_remake` | `not_reached_in_window` | 138 | 138 | — | — |
| 15 | 战斗结算弹窗音 | `silent_on_remake` | `not_reached_in_window` | 149 | 149 | — | — |
| 16 | 胜利音 | `silent_on_remake` | `not_reached_in_window` | 158 | 158 | — | — |
| 17 | 结算音 | `silent_on_remake` | `not_reached_in_window` | 157（+112） | 157（+112） | — | — |
| 18 | 道具组17 专用音 | `missing_on_remake` | `missing_on_remake` | 146 | — | — | — |
| 19 | 道具到期专用音 | `missing_on_remake` | `missing_on_remake` | 152 | — | — | — |

**口径说明**：J 流的静态分类器对「sound 类 + 有调用点」**一律**判 `silent_on_remake`
（它的 `classify()` 里 `remake_kind == "sound"` 分支先于其它判断），
所以它**永远不可能**给音效行判 `match`；L 流的分类器改成看**运行时轨迹**
（cue 有没有被真的派发）+ **A/B 录音**（派发有没有真的出声）。

---

## 11. 两次独立全流程跑的逐字节一致性

```powershell
python tools/s49_audio_l/run_all.py --out build/s49-audio-l --repeat 2 `
    --rom  build/remake-audio-verify/butano-sequel/butano-sequel.gba `
    --elf  build/remake-audio-verify/butano-sequel/butano-sequel.elf `
    --original build/s49-audio
```

| 产物 | 第一次 sha256 | 第二次 sha256 | 结论 |
|---|---|---|---|
| `remake_trace.json` | `55b8e5beb390cbf3a3606e217af52a9809150d7ae760585fad29746042bed0ae` | 同左 | **IDENTICAL** |
| `remake_audio_analysis.json` | `a2a3a0a2575d4532b3b85eb8ad3f4b43d1132b9ac4d1634c18a02c7302c479d0` | 同左 | **IDENTICAL** |
| `event_diff.json` | `dbf757f0519ea351b57a1278421e0694cd1a4432aa8f8aaf9d3c5a5dd682639c` | 同左 | **IDENTICAL** |
| `event_diff.md` | `1537189f3e4c3ee378f2bbc5655941a463a1113474b7012a87557217a9217cdd` | 同左 | **IDENTICAL** |

```
determinism (run twice byte-identical) = True
```

> 第一次跑出来的 `remake_audio_analysis.json` 与第二次差一个字节：
> 差的是它记的**输入 WAV 路径**（两次跑写的目录不同）。
> 已把该字段改成只记文件名，重跑后逐字节一致。

---

## 12. 复现命令清单

```powershell
# 0) 工具链（私有探针目录，别覆盖共享的 build/mgba-probe）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-l'
python tools/mgba_probe/build.py            # 共享探针（J 流也用它）
python tools/s49_audio_l/build_recorder.py  # 音频录音器（重制树自带源）

# 1) 原版 PCM（逆向线 ground truth 对齐）
cd D:\Shell\Github\gba-naruto-butano
python tools/extract_audio.py rom/base.gba --extract --output-dir build/audio-v2
python <repo>/tools/s49_audio_l/decode_tracks_adapter.py
python tools/render_m4a_pcm_bank.py rom/base.gba --bank sequel/content/audio/bank.json `
       --decoded build/audio-v2/tracks-decoded.json --output-dir build/audio-v2/pcm `
       --evidence build/audio-v2/render-evidence.json --loop-invocations 7200 --max-one-shot-invocations 3600

# 2) 新资产（cue 10 / 146 / 152）
python tools/s49_audio_l/build_cue_assets.py --sound-id 146 --kind sfx `
       --from-pcm-wav D:\Shell\Github\gba-naruto-butano\build\audio-v2\pcm\sound_146.wav
python tools/s49_audio_l/build_cue_assets.py --sound-id 152 --kind sfx `
       --from-pcm-wav D:\Shell\Github\gba-naruto-butano\build\audio-v2\pcm\sound_152.wav
python tools/s49_audio_l/build_cue_assets.py --sound-id 10 --kind bgm `
       --from-wav D:\Github\gba-naruto\build\s49-audio-l\original-cue10-raw.wav

# 3) 隔离验证树 + 构建
python tools/s49_audio_l/prepare_verify_tree.py
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/remake-audio-verify/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 4) 运行时轨迹 + 录音 + A/B 可闻性 + 差异表 + 两次一致性
python tools/s49_audio_l/run_all.py --out build/s49-audio-l --repeat 2 --rom ... --elf ... --original build/s49-audio

# 5) 单元测试
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && \
  g++ -std=c++20 -Wall -Wextra -Werror -I game/include -o /tmp/t game/tests/test_battle_audio_director.cpp && /tmp/t"
```

---

## 13. 给父代理的三条提醒

1. **重制树整体 ROM 需要重新构建**：我最后一次改 `battle_audio_event_trace.h`
   （把环形缓冲从 IWRAM 挪到 EWRAM 固定窗口）是 02:14，G 在 02:10–02:12 的那次构建
   用的是**旧的 IWRAM 版本**⇒ 那个 ROM 在输入走位上会崩（见 §5.2）。
   **G 下一次构建会带上我的新头文件**，就没事了。
2. **重制树的整体 ROM 目前跑不完输入走位**，原因是 **G 流 `battle_runtime_scene.cpp`
   的在途改动**（`battle_runtime_scene.cpp` 在我两次构建之间被改过，
   1:53:22 与 2:10:27 两次）。我用隔离验证树（HEAD + 只有 L 流的改动）做的验收。
3. **cue 8 / 146 / 152 只差三行调用点**（§6），在 `battle_runtime_scene.cpp` 里。

