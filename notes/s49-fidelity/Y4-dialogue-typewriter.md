# Y4 —— 对话打字机 + 缺一屏对话（G3 / G4）

> 2026-10-24 · Y4 流（wave 6）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/WAVE6-TASKS.md` §0 / §5、`notes/s49-fidelity/X2-pairing.md`
> 仪器（只读复用）：`tools/s49_pairing/`（密集 walk + 内容锚）、
> `tools/s49_fidelity_report.py`（判定台）
> 独占文件：`battle_presentation_text_layout.h` / `battle_presentation_script.h` /
> `battle_presentation_content.h` + 新单元测试
> ⛔ **未改动** `battle_runtime_scene.cpp`（Y1 独占）、`battle_scene_controller.h`、
> `battle_black_field.h` / `battle_presentation.h` / `generated_battle_presentation_content.h`（Y2 独占）；
> ⛔ 逆向线全程只读；⛔ **未提交 git**。

---

## 0. 一句话结论

> **原版是逐字显现（1 字 / 4 帧），重制侧是整段一次出现 —— 打字机已在 Y4 的三个独占头里实现并单测通过；
> 缺的那一屏（step-12，9,907 px）经逐像素证明**不是内容缺，是时序缺**：原版那一屏是
> 「对话框已打开、字还没开始打」的**空对话框**（签名 0.805），重制侧因为整段一次出现，
> 从来没有过这个时刻；把打字机接上后，重制侧的空对话框将与原版的 step-12 **逐字节相同**
> （残差 9,907 → 0，签名 0.805 ⇒ 配对表里 step-12 拿到同刻帧）。**
> **接线点共 5 处（3 处在 `battle_runtime_scene.cpp`、1 处在 `battle_scene_controller.h`、
> 1 处在 `battle_runtime_scene.cpp` 的按键分支），已生成可直接 `git apply` 的补丁。**

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `butano-sequel/game/include/konoha/battle_presentation_text_layout.h` | **改** | +`count_glyphs()`、+`byte_prefix_length()`（打字机要数「画出来的字」和「前缀字节数」） |
| `butano-sequel/game/include/konoha/battle_presentation_content.h` | **改** | +两个实测常量（字间隔 4 帧、起手延迟 52 帧） |
| `butano-sequel/game/include/konoha/battle_presentation_script.h` | **改** | 打字机本体：`visible_glyph_count` / `typewriter_active` / `portraits_revealed` + `advance_typewriter()` |
| `butano-sequel/game/tests/test_battle_presentation_typewriter.cpp` | **新** | 打字机单测（layout 辅助函数 + 逐字节奏 + 起手延迟 + 头像时机） |
| `notes/s49-fidelity/Y4-dialogue-typewriter-wiring.patch` | **新** | **5 处接线点的 unified diff**（`git apply --check` 已过，exit 0） |
| `notes/s49-fidelity/Y4-dialogue-typewriter.md` | **新** | 本报告 |

---

## 2. ⭐ 关键事实（全部实测，证据可复跑）

### 2.1 原版确实是逐字显现：**1 字 / 4 帧**

原版密集 walk（`build/s49-pairing/walk5/dense-original`，553 帧，**每 4 GBA 帧采样 1 张**）。
把每帧的「对白文字带」（第 121–134 行）的墨迹列数打出来：

```
原版 line1: 0285→0299  ink 6,13,20,27,27,34,41,48,55,57,64,71,78,85,91   (末列 30→142)
原版 line2: 0323→0332  ink 6,13,16,19,26,33,40,42,49,56                  (末列 30→102)
原版 line3: 0360→0377  ink 6,9,12,19,26,33,40,47,47,56,63,70,77,84,91,98,105,106 (末列 30→161)
```

* 每一步 **+7~8 列 = 1 个字**（CJK 等宽 8 px），**每采样步 1 个字** ⇒ **1 字 / 4 GBA 帧**；
* 三行合计 **41 个打字采样步**（15 + 10 + 18）；
* 打字机不是「淡入」：原版行 125 的像素在 0285 就是终值 `(57,66,57)`（**一次跳到位**），
  0284（打字前）该行全是底色 `(231,247,214)`。

⇒ **打字机速度 = 1 字 / 4 帧**（写进 `battle_presentation_typewriter_glyph_interval`）。

### 2.2 重制侧确实是整段一次出现

```
重制 0325-0329  ink 0,0,0,0,0     （还在白闪过渡里）
重制 0330-0331  ink 4,4           （只有框线，暗阈值下无字）
重制 0332       ink 91            ← 一帧之内整行字全在
重制 0346       ink 56            ← 换行，也是一帧
重制 0369       ink 106           ← 再换行，还是一帧
```

重制行 125 的像素是**渐变**的：`0328 (165,165,165)` → `0330 (115,115,115)` →
`0331 (99,107,99)` → `0332 (90,99,90)` → `0333 (57,66,57)`。
⇒ 重制侧做的是**整屏调色板渐变（白闪）**，字是**一次出现**的，**没有打字机**。

⇒ **G3 成立**：原版 133 帧 / 60 个签名（3 位小数 56）vs 重制 59 帧 / 3 个签名。

### 2.3 ⭐ 缺的那一屏是**时序缺**，不是内容缺

| | 原版 | 重制侧 |
|---|---|---|
| 对白屏数 | 3 行 | 3 行 |
| 整行完成时的像素 | — | **与原版逐字节相同**（见下） |
| 原版 step-12（capture 0276）是什么 | **对话框已开、无字、无头像** | 重制侧**没有这个时刻** |

**内容完整的硬证据**：重制侧 `step-0333-in.png`（第 1 行整行完成）
与原版 `step-0312-in.png`（第 1 行整行完成）
**在整屏 240×160 上差 0 px**（战场区也是 0 px）。

⇒ **3 行对白一句不缺**，缺的是**空对话框那一拍**。

原版 0276 的对话签名 `0.805`（`build/s49-pairing/x2/pairing5/anchors-original.json`）
落在 capture **0272–0283** 这 12 张上：**框已开满、字一个字都还没有**。
重制侧从来没有这一拍（框和整行字同帧出现）⇒ **配对表里 step-12 没有同刻帧**。

### 2.4 ⭐ 接上打字机后 step-12 的残差**必然**降到 0（已逐像素证明）

原版 0276（空框）与原版 0312（整行字）**只在三处不同**：

```
不同的行：8–86（头像）  105–135（说话人标签 + 正文）  139–147（右下角螺旋图标）
框、森林背景、边框：完全相同
```

而重制侧 0333 ≡ 原版 0312（整屏 0 px 差）。
⇒ ⇒ **重制侧「空框 + 无头像 + 无字」的一帧 = 原版 0276，逐字节相同**
⇒ **残差 9,907 → 0**，**对话签名 = 0.805**（与原版同键 ⇒ 内容锚配对表里 step-12 拿到同刻帧）。

（已复核：原版 0276 的 `bright_share` = 0.805，重制侧 0333 = 0.6892。）

### 2.5 原版头像与「等待图标」的时机（决定接线点怎么写）

| 帧 | 头像 | 右下角螺旋图标 |
|---|---|---|
| 0276（原版 step-12，空框） | **无** | **无** |
| 0284（打字前一帧） | **有**（鸣人 + 小樱） | 无 |
| 0292（打字中） | 有 | **无** |
| 0300–0311（整行刚完成） | 有 | **无** |
| 0312–0322（整行完成 48 帧后） | 有 | **有** |
| 0323（下一行开始打字） | 有 | **无** |

⇒ **头像跟着第一个字一起进画面**（⇒ 接线点 D）；
⇒ **螺旋图标是「这行已经可以按 A 了」的标记，打字中不画**（⇒ 接线点 A1）。
图标在屏幕第 139–147 行，**在判定台战场区（0–127 行）之外** ⇒ 不影响残差，但**影响对话签名**
（0.6919 ↔ 0.6892）⇒ 打字中的帧必须**不画图标**，否则签名对不上原版。

---

## 3. 前后对比

| 指标 | 现状（重制侧） | 接线后（预测） | 原版 |
|---|---:|---:|---:|
| 对白帧数 | 59 | ≈ 59 + 41~48 | 133 |
| **对白不同签名数** | **3** | **≈ 48–55** | **56**（60 @4 位小数） |
| 逐字显现 | ❌ 整段一次 | ✅ 1 字 / 4 帧 | ✅ 1 字 / 4 帧 |
| 「空对话框」这一拍 | ❌ 不存在 | ✅ 52 帧（签名 0.805） | ✅ 52 帧（0.805） |
| step-12 同刻配对 | ❌ 无 | ✅ 有 | — |
| **step-12 残差** | **9,907** | **≈ 0**（逐字节同 ⇒ 必然 0） | — |
| step-13 / step-16（打字相位差） | 28 / 344 | ≈ 0（打字相位会对上） | — |
| 头像出现的时刻 | 随框一起 | 随第一个字 | 随第一个字 |

**预测口径**：打字机每行产生「1 个空框签名 + N 个逐字签名 + 1~2 个整行签名」；
battle_id 14 的 11 个 case 的逐字步数实测为 **18–60 步/case**（selector 1 = 17+12+19 = 48 步），
原版同场景实测 41 步 ⇒ **重制侧接线后的签名数与原版同量级**。

---

## 4. 实现说明（Y4 独占文件内）

### 4.1 `battle_presentation_text_layout.h`

* `count_glyphs(text, length, &count)`（static）：数**画出来的字**。
  全角空格 `0x8140` 占格但**不画**，所以**不算一个字**（原版对白的尾部全是这种填充空格）。
* `byte_prefix_length(text, length, glyph_limit)`（static）：前 `glyph_limit` 个字对应的**字节前缀长度**。
  前缀从第 0 字节起 ⇒ **每个字的格子位置与整行完全一致**（逐字显现不会让任何一个字挪位）。

### 4.2 `battle_presentation_content.h`

```cpp
inline constexpr std::uint8_t battle_presentation_typewriter_glyph_interval = 4;   // 1 字 / 4 帧
inline constexpr std::uint8_t battle_presentation_typewriter_start_delay   = 52;  // 空对话框 52 帧
```
（两个数都来自 §2.1 / §2.3 的实测，注释里写了出处。）

### 4.3 `battle_presentation_script.h`

快照新增 3 个字段：

```cpp
std::uint8_t visible_glyph_count = 0;   // 已显出的字数
bool typewriter_active = false;         // 这行还在打字
bool portraits_revealed = false;        // 头像是否已经进画面
```

* `_arm_typewriter(text_offset, text_length)`：数出这一行的字数；
  **本 case 的第一行**先等 `start_delay`（52 帧 ⇒ 空对话框），**后面的行**一帧就换（与原版一致）；
  字数为 0 时直接放行头像。
* `advance_typewriter()`：**每帧调一次**；每 `glyph_interval` 帧多显一个字；
  显出第一个字时把 `portraits_revealed` 置真 ⇒ **头像跟着第一个字进画面**。
* `snapshot()` 的语义**没变**（仍是 const 引用返回）；
  `text_length` **仍是整行长度**、**phase 仍是 `wait_for_input`** ——
  这是被现有的绿测 `test_battle_presentation_script` 钉死的
  （它断言 `begin()` 后 `phase == wait_for_input` 且 `text_length == 36`），
  所以**打字机不能靠改这两个字段实现**，必须由运行侧限制绘制 ⇒ 接线点 A3。

---

## 5. 接线点清单（**交给父代理**，已生成可直接应用的补丁）

补丁：`notes/s49-fidelity/Y4-dialogue-typewriter-wiring.patch`
（`git -C D:\Shell\Github\gba-naruto-butano apply --check …` → **exit 0**）

### A. `butano-sequel/game/src/battle_runtime_scene.cpp` :: `render_script_glyphs()`（约 4406 行）

| # | 位置 | 改法 | 为什么 |
|---|---|---|---|
| **A1** | 螺旋图标创建处（约 4441） | 整块包进 `if(! state.script.typewriter_active) { … }` | 原版打字中**不画**图标（§2.5）；图标在战场区外，但会改对话签名 |
| **A2** | 说话人标签处（约 4451 / 4465） | 两个分支各加 `state.script.visible_glyph_count > 0 &&` | 原版标签跟第一个字一起出现 |
| **A3** | 字形循环（约 4480） | `index < layout.glyph_count() && index < state.script.visible_glyph_count` | **只画已显出的字**（打字机本体） |

### B. `battle_runtime_scene.cpp` :: 主循环按键分支（约 8006）

```cpp
if(! state.script.typewriter_active &&
        ! script_confirmation_latched &&
        bn::keypad::a_held())
```
⇒ 打字中按 A **不换行**（原版同样忽略），否则会把整行字截断、
让「整行完成」的那一帧永远不出现 ⇒ 判定台 #13/#14/#15/#17 的 0 残差会爆掉。

### C. `battle_runtime_scene.cpp` :: 主循环（`state = controller.snapshot();` 之前，约 8201）

```cpp
if(state.phase == battle_scene_phase::script_blocked &&
        state.script.phase ==
                battle_presentation_script_phase::wait_for_input &&
        state.script.typewriter_active)
{
    controller.advance_typewriter();
}
```

### D. `battle_runtime_scene.cpp` :: `update_script_portraits()`（约 5994）

```cpp
if(state.script.portraits_revealed) { renderer.update(state.script.portraits, scratch); }
else { renderer.reset(); }
```
⇒ 头像等第一个字（§2.5）⇒ **这一处是 step-12 残差 9,907 → 0 的关键**
（否则空框那帧仍带着两个头像，残差 ≈ 6,000 而不是 0）。

### E. `butano-sequel/game/include/konoha/battle_scene_controller.h`（**这个文件无人独占**）

```cpp
[[nodiscard]] bool advance_typewriter()
{
    if(_phase != battle_scene_phase::script_blocked) { return false; }
    return _script.advance_typewriter();
}
```
（控制器把逐帧推进转发给脚本；`battle_scene_controller.h` 不在 Y1/Y2/Y3 的独占清单里，
但也不在 Y4 的独占清单里 ⇒ **请父代理决定由谁改**，或由父代理直接改。）

---

## 6. 跑了哪些验证

| # | 验证 | 命令 | 结果 |
|---|---|---|---|
| Y4-V1 | 原版逐字节奏 | 读 `build/s49-pairing/walk5/dense-original` 553 帧的文字带墨迹列 | **1 字 / 4 帧**，三行 15/10/18 步 |
| Y4-V2 | 重制侧整段一次 | 同上，dense-remake | 0330/0331 无字、0332 整行 ⇒ 无打字机；调色板渐变而非打字 |
| Y4-V3 | 对话签名分布 | `build/s49-pairing/x2/pairing5/anchors-{original,remake}.json` | 原版 133 帧 / **60** 签名；重制 59 帧 / **3** 签名 |
| Y4-V4 | **内容不缺**（逐像素） | 原版 0312 vs 重制 0333，`diff_mask` 整屏 | **0 px**（整屏 240×160） |
| Y4-V5 | **空框预测**（逐像素） | 原版 0276 vs 原版 0312 的差异行 | 只差 **8–86（头像）/105–135（标签+字）/139–147（图标）** ⇒ 空框帧 ≡ 原版 0276 ⇒ 残差 **0**、签名 **0.805** |
| Y4-V6 | 签名值复核 | `_bright_share` | 原版 0276 = **0.805**；重制 0333 = 0.6892 |
| Y4-V7 | 头像/图标时机 | 原版 0276…0391 的图标区与头像区逐帧 | 见 §2.5 表 |
| Y4-V8 | **新单测** | `g++ -std=c++23 -Wall -Wextra -Werror -pedantic … test_battle_presentation_typewriter.cpp` | **PASS**（layout 辅助函数 + 逐字节奏 + 52 帧起手 + 换行零延迟） |
| Y4-V9 | 既有绿测不回归 | `test_battle_presentation_script` / `…_text_layout` | **PASS / PASS**（`text_length` 与 phase 语义未变） |
| Y4-V10 | **单测棘轮（工作区）** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh` | **pass=108 fail=20**，失败集合与 HEAD 基线 **逐名相同**（20/20） |
| Y4-V11 | **单测棘轮（HEAD 基线）** | `bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | **pass=101 fail=20**，同一份 20 项名单 |
| Y4-V12 | 4 项疑似新红的隔离实验 | 把 Y4 的三个头换成 HEAD 版本再编这 4 项 | 4 项**全部 PASS**（with-y4 / without-y4 一致）⇒ 那 4 项是**别的流在跑测试期间改了树**造成的，不是 Y4 |
| Y4-V13 | **GBA 构建** | `make -j4`（`LIBBUTANOABS` 已导出） | **exit 0**，`Linking ROM… / ROM fixed!`；我改的三个头**零 warning**；ROM sha `103A6944…` |
| Y4-V14 | **判定台（残差）** | `python tools/s49_fidelity_report.py --out build/s49-report/report-y4.json --work-dir build/s49-report/y4-work` | exit 0；**step-12 = 9,907（与基线一致 ⇒ Y4 未引入回归）**；step-13=28、step-16=344；总和 168,392、中位 1,940、归因 3·14·8 |
| Y4-V15 | 接线补丁可应用 | `git apply --check …Y4-dialogue-typewriter-wiring.patch` | **exit 0**（两个文件都干净） |
| Y4-V16 | 编码 | 5 个文件的 CRLF/BOM 统计 | 全部 **CRLF=0、无 BOM** |

⚠️ **Y4-V14 的口径说明**：判定台默认跑的是**粗 walk**（中位 1,940 / 3·14·8）；
任务书里的「中位 1,680 / 总和 117,832 / 归因 4·15·6」是 X2 的**密集 walk**口径
（`tools/s49_pairing/pairing_report.py`，783 帧重制侧）。
且本次录制用的 ROM sha 是 `a7d903d7…`，**不等于**我构建的 `103A6944…`
⇒ 录制期间**别的流又重建了 ROM** ⇒ 该数字**不能**当作 Y4 的效果，
只能当作「**Y4 未引入回归**」的证据（step-12 仍精确是 9,907）。
**Y4 的效果必须等接线后重跑密集 walk 才算数。**

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Y4-1 | 原版对话是逐字显现（不是别的机制） | 逐帧量对白文字带的墨迹列 | 每采样步 +1 字（8 px），三行 41 步 ⇒ 1 字 / 4 帧 | **已确认** |
| Y4-2 | 重制侧整段一次出现 | 同上（dense-remake） | 0332 一帧内 91 列全在；像素是调色板渐变 | **已确认** |
| Y4-3 | 对白签名差异（3 vs 60）由打字机造成 | 对话签名分布（X2 的 anchors） | 原版 133/60、重制 59/3 | **已确认** |
| Y4-4 | **缺的一屏是内容缺** | 逐像素比对整行完成帧 | 重制 0333 ≡ 原版 0312（整屏 0 px）⇒ **内容不缺** | **已证伪** |
| Y4-5 | 缺的一屏是**时序缺**（空对话框那一拍） | 原版 0276 与 0312 的差异行 | 只差头像/标签/正文/图标 ⇒ 0276 = 空框 ⇒ **时序缺** | **已确认** |
| Y4-6 | 接线后 step-12 残差必然 = 0 | 重制空框帧 ≡ 原版 0276（由 V4+V5 推出） | 重制 0333 ≡ 原版 0312，且 0276 只差头像/字/图标 ⇒ 重制空框 ≡ 0276 | **已确认**（推导） |
| Y4-7 | 打字机速度 = 1 字 / 4 帧 | 三行逐帧墨迹列 | 15/10/18 步对应 41 步 ⇒ 每步 4 GBA 帧 | **已确认** |
| Y4-8 | 空对话框持续 52 帧 | 原版 0272（框开满）→ 0285（第一个字） | 13 个采样步 × 4 帧 | **已确认** |
| Y4-9 | 头像跟第一个字出现 | 原版 0276/0284 的头像区 | 0276 无头像、0284 有 | **已确认** |
| Y4-10 | 打字中不画螺旋图标 | 原版 0285–0311 图标区墨迹 | 恒 17（无图标），0312 起 53 | **已确认** |
| Y4-11 | 打字机不能靠改 `phase` / `text_length` 实现 | 读绿测 `test_battle_presentation_script` | 绿测钉死 `phase == wait_for_input`、`text_length == 36` ⇒ 必须由运行侧限制绘制 | **已确认** |
| Y4-12 | 在 `snapshot()` 里遮蔽头像会打破既有绿测 | 同上（绿测断言 `portraits[0].visible`） | 会 ⇒ 改为**运行侧**遮蔽（接线点 D） | **已证伪（已改）** |
| Y4-13 | 打字中按 A 必须被忽略 | 原版 0360–0377 打字中、369 有按键 | 打字没有被截断 ⇒ 原版忽略该按键 | **已确认** |
| Y4-14 | 接线后签名数与原版同量级 | battle_id 14 的 11 个 case 逐字步数 18–60 | 与原版 41 步同量级 ⇒ 签名数 ≈ 48–55 vs 原版 56 | **已确认（估算）** |
| Y4-15 | Y4 的改动在接线前**行为中立** | 逐条审 + 判定台复跑 | 新字段无人读、`advance_typewriter()` 无调用者 ⇒ step-12 仍精确 9,907 | **已确认** |
| Y4-16 | 工作区比 HEAD 多出的 4 项失败是 Y4 引入的 | 把 Y4 三个头换回 HEAD 版本再编这 4 项 | with/without 都 PASS ⇒ **不是 Y4**（是别的流在跑测试期间改了树） | **已证伪** |
| Y4-17 | 对白行数（3 行）在接线后仍是 3 行 | 脚本数据：battle_id 14 的 case 只有 3 条 `render_text` | 是（接线只改**显现节奏**，不改脚本） | **已确认** |

---

## 8. 卡在哪 / 遗留风险

1. **⚠️ 本流不能独自完成验收**：打字机需要 5 处接线（§5），其中 4 处在
   `battle_runtime_scene.cpp`（**Y1 独占**）、1 处在 `battle_scene_controller.h`（无人独占）。
   **Y4 按独占规则没有改这两个文件** ⇒
   **「签名序列长度」「step-12 同刻配对且残差降到 0」这两条验收，必须在父代理接线后重跑才算数。**
   本流已把补丁准备好（`git apply --check` 通过）。
2. **接线后必须重跑密集 walk**：判定台的默认跑法是粗 walk；
   签名数与 step-12 的配对要看 `tools/s49_pairing/pairing_report.py`（783 帧重制侧）。
   ⚠️ X2 §9.7 已警告：**密集 walk 的重制侧与当前 ROM 绑定**，必须重录。
3. **原版的「对话框展开动画」（capture 0267–0271）仍然缺**：原版的框是**斜切展开**的，
   重制侧的框是**瞬间出现**（配白闪过渡）。这会让原版的 5 个「框展开」签名在重制侧没有对应
   （不在 25 帧判定台基准里，所以不影响残差，但影响配对表的「同刻」覆盖）。
   修它需要改对话框图块/渲染（`battle_runtime_scene.cpp` + `graphics/`）⇒ **不在 Y4 范围**。
4. **原版「换行后先等 56~92 帧再打下一行」没有复现**：实测原版第 2/3 行的第一个字
   分别在按键后 92 / 56 帧出现，而重制侧是**按键后 1 帧**换行（与原版「一帧换行」的
   画面表现一致，但时序不同）。本流按**画面**对齐（残差），没有按**时刻**对齐。
   ⇒ 若父代理要求时刻级对齐，需要原版脚本里的逐行等待参数（逆向线，本流只读未取）。
5. **打字机期间按 A 被忽略** ⇒ 若玩家的手速比打字快，对话会「多等一会儿」。
   这是原版的行为（实测），但**是行为变更**，出包前应确认产品侧接受。
6. **并发流污染测量**：本次录制用的 ROM sha（`a7d903d7…`）与我构建的（`103A6944…`）不同
   ⇒ 期间有别的流重建了 ROM；第一次跑单测时也出现 4 项额外失败（同样是并发改树）。
   ⇒ **判读数字前请先确认树是静止的**（我已用 Y4-V12 的隔离实验证明那 4 项不是 Y4 的）。

---

## 9. 复跑命令

```powershell
# Y4 单测
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano && g++ -std=c++23 -Wall -Wextra -Werror -pedantic -I butano-sequel/game/include butano-sequel/game/tests/test_battle_presentation_typewriter.cpp -o /tmp/y4_tw && /tmp/y4_tw"

# 单测棘轮（工作区 vs HEAD）
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh

# 接线（父代理）
git -C 'D:\Shell\Github\gba-naruto-butano' apply 'D:\Github\gba-naruto\notes\s49-fidelity\Y4-dialogue-typewriter-wiring.patch'

# 接线后重录 + 判定台 + 配对表（父代理）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"
python tools/s49_pairing/run_all.py --walk build/s49-pairing/walk5
python tools/s49_fidelity_report.py --out build/s49-pairing/x2/dense5/report.json --work-dir build/s49-pairing/x2/dense5 --skip-capture --ratchet build/s49-pairing/x2/base-cur/report.json
```

⚠️ **构建冲突**：并发构建会互相覆盖 ⇒ 同一时刻只允许一路做构建；
若报 `objcopy: Invalid argument` ⇒ 等 60 秒重试（最多 5 次）。
