# U1 —— 接线总装（wave 10 关键路径）

> 2026-10-24 · wave 10 · 流 U1
> 上游：`notes/s49-fidelity/WAVE10-TASKS.md` §1（流 U1）、
> `V3-dialogue-title.md`（对话 + 标题）、`V2-camera-anchor.md`（覆盖层锚点）、
> `W2-starfield-vram.md` + `V1-star37-wiring.md`（星光圈）
> 仪器（本流新建，都在 `build/s49-u1/`，产物不进 git）：
> `compare_levels.py`（37 级可见像素对拍）、`overlay_diff.py`（逐格差异归因）
> ⛔ 逆向线 `D:\Shell\Github\gba-naruto-reverse` **全程只读**；⛔ **未提交 git**

---

## 0. 一句话结论

> **六条接线全部落地，判定台残差从 109,597 降到 100,210（−8.6 %）、全 0 帧从 2 升到 5、
> 黑场 37 级逐级可见像素与原版全部对上（0 不匹配）。**
> 关键发现：**V1 的「残差回归 159,310」不是生长阶段的问题，而是星光圈用屏幕绝对坐标调
> Butano 的 `create_sprite()`（屏幕中心相对）⇒ 遮罩整体偏出 (120,80)、黑场从来没黑过。**
> 修掉坐标 + 打开 37 级的生长 + 把黑场两个引线对齐原版，残差反而比 HEAD 基线低 9,387 px。

---

## 1. 改了哪些文件

### 1.1 重制线（`D:\Shell\Github\gba-naruto-butano\butano-sequel\`）

| 文件 | 改动 | 行 |
|---|---|---|
| `game\src\battle_runtime_scene.cpp` | **改**（6 处接线，见 §3） | 见下 |
| `game\include\konoha\battle_black_field_star_mask.h` | **改**：⭐ 遮罩的屏幕中心偏移修正（+2 常量、2 处 `create_sprite`） | 68–71 / 118–135 / 145–156 |
| `graphics\battle_opening_title_kai.{bmp,json}` | **换**：V3 修好的素材（相位打包顺序 + 切块上界） | — |
| `graphics\battle_opening_title_shi_top.{bmp,json}` | **换** | — |
| `graphics\battle_opening_title_shi_right.{bmp,json}` | **换**（旧件全透明） | — |
| `graphics\battle_opening_title_shi_bottom.{bmp,json}` | **换**（旧件全透明） | — |
| `graphics\battle_opening_title_shi_corner.{bmp,json}` | **换**（两相位都全透明，内容相同） | — |

> `battle_black_field_star_mask.h` 属于 U1 独占（wave 10 任务书 §2.2 用的是
> **通配** `battle_black_field*.h`），且该文件是 wave 8 的 W2 产物、现无其它流持有。

### 1.2 主仓（`D:\Github\gba-naruto\`）

| 文件 | 性质 | 说明 |
|---|---|---|
| `notes\s49-fidelity\V1-star37-wiring.md` | **新** | ⭐ 补交 wave 9 流 V1 的报告（接线点逐条 + 台账 + 前后对比表） |
| `notes\s49-fidelity\U1-wiring.md` | **新** | 本文件 |
| `build\s49-u1\compare_levels.py` | **新（仪器）** | 37 级可见像素对拍（判定黑场真值） |
| `build\s49-u1\overlay_diff.py` | **新（仪器）** | 逐格覆盖层差异归因（定位剩余的 24/24/56） |
| `build\s49-u1\{bench,remake-entry,vram-after,r9,package,smoke.json}\` | **产物** | 私有输出路径，不进 git |

---

## 2. 接线点逐条状态

| # | 接线点（§1.2） | 状态 | 落点 / 证据 |
|---|---|---|---|
| **①** | ⭐⭐ **对话字形渲染移出输入门控** | **已接** | `battle_runtime_scene.cpp:8905–8922`：`render_script_glyphs()` 从 8726 的 `if(handled \|\| …)` 门控块里搬到门控块**之外**，每场景帧执行；用 V3 的 `battle_presentation_glyph_render_state`（`:7788`）判「这一帧要不要重画」。另加 `script_glyphs_released`（`:7793`）：遮罩/呈现抢走精灵或视觉资源换代释放了字形精灵时，强制下一帧重画（否则同一行回来时不会重画）。 |
| **②** | ⭐⭐ **标题 5 个坐标改成 Butano 中心相对** | **已接** | `:7246–7268`：改用 V3 放在 `battle_opening_title.h` 的 `battle_opening_title::placements[0..4]` = `(-47,1) (47,-6) (95,-6) (47,42) (95,42)`。`set_phase()` 未动。 |
| **③** | ⭐ **换掉 5 个标题素材** | **已接** | 从 `build/s49-v3/title-assets/` 拷 5 个 BMP + 5 个 JSON 到 `graphics/`。落地前 `python tools/s49_v3_dialogue/check_title_asset_pixels.py --staged build/s49-v3/title-assets` ⇒ **10 格全 0 差异**；落地后对 `graphics/` 再跑一次仍是 **10 格全 0 差异**。 |
| **④** | ⭐ **覆盖层锚点接线（V2）** | **已接** | `:2265/2266/2279/2283`：`map_px_y = battle_map_overlay_map_y(layer_px_y)`、`cell_y = battle_map_overlay_cell_y(layer_px_y)`、`map_px_x = battle_map_overlay_map_x(layer_px_x)`、`cell_x = battle_map_overlay_cell_x(layer_px_x)`。`tile_x/tile_y` 仍由 `map_px - cell*size` 推；`_bg->set_position(-window_x,-window_y)` **未动**；宽度钳位未放宽（`cell_x ∈ {0, 8..14}`）。旧的相机派生窗口与 `ceil_div` lambda 一并删掉。 |
| **⑤** | ⭐ **星光圈 37 级接线（V1）** | **已接（并修了 V1 的两个缺陷）** | include 已在（`:120`）；场景成员两处（部署场景 + 战斗场景）；每级 `set_level()`、黑场结束 `clear()` 都在。⭐ **修 V1 的缺陷 A**：遮罩的 `create_sprite()` 原来用屏幕绝对坐标 ⇒ 整体偏 (120,80) ⇒ 黑场不黑；现减屏幕中心（`battle_black_field_star_mask.h`）。⭐ **修 V1 的缺陷 B**：37 级的**生长 12 级**（原版帧 1079–1102）从「默认关」改成**打开**（`:247` `battle_black_field_event1_growth = true`）。⭐ 调色板淡出**保持关**（`battle_black_field.h::apply()` 已是空函数，V1 做对了）。素材已进 ROM（`nm \| grep star_mask` ⇒ `battle_black_field_star_mask16_bn_gfxTiles` / `_block32_bn_gfxTiles` 都在）。 |
| **⑤′** | ⭐ **V1 的时间轴回归先定位再打开** | **已定位 + 已打开 + 残差不回归** | 回归的真因是**遮罩坐标系**（不是生长）：遮罩出屏 ⇒ 黑场不黑 ⇒ 判定台两个黑场帧差 25k px 量级。修坐标后残差 159,697 → 114,304；再打开生长 → 104,784；再把黑场两个引线对齐原版 → **100,210**（比 HEAD 基线 109,597 低 9,387）。 |
| **⑥** | 对话框斜切展开（可选） | **未做（建议单独排一轮）** | 模型齐（`battle_presentation_box_opening`），但运行时怎么把黑色碎片画到对话框之上没有先例；V3 明确建议不要和标题补丁混做。本流没碰。 |

---

## 3. `battle_runtime_scene.cpp` 的 6 处改动（逐处）

1. **`:2265/2266/2279/2283` —— 覆盖层内容锚到地图空间**（接线点 ④）
2. **`:7246–7268` —— 标题的 5 个放置改成 `battle_opening_title::placements`**（接线点 ②）
3. **`:7788` —— 新成员 `battle_presentation_glyph_render_state script_glyph_render_state;`**
4. **`:7793` —— 新成员 `bool script_glyphs_released = true;`**
5. **`:8623` —— 视觉资源换代释放了字形精灵时置 `script_glyphs_released = true`**
6. **`:8905–8922` —— 字形渲染搬出输入门控**（接线点 ①）
7. **`:247` —— 生长 12 级打开**（接线点 ⑤）
8. **`:234/235` —— 黑场两个引线（见 §4 的校准）**

---

## 4. 怎么把黑场对齐回原版（**引线是唯一的相位旋钮**）

判定台的帧是**按键节拍**，所以黑场落在节拍网格的哪一格，决定了残差。
引线（`battle_black_field_event{1,2}_lead_frames`）就是黑场相对网格的相位：

| 事件 | 常量 | 改动的依据 | 残差变化 | 全 0 帧 |
|---|---:|---|---:|---:|
| 事件 1（标题 → 对白） | 36 → **38** | 原版 step 11 落在淡出的 **level 8**（305 亮 px），重制侧落在 **level 9**（173 亮 px）⇒ 早一级 ⇒ 引线加 2 场景帧。**2 场景帧 = 2 级 = 1 个打字机字形间隔**（原版每 4 GBA 帧露一个字），所以它同时决定了对话的字形相位。 | −104 | **3 → 5** |
| 事件 2（对白 → 回合 1） | 24 → **19** | 原版 step 18 落在**全黑持黑段的最后一帧**（0 亮 px），重制侧落在淡出的 **level 7**（681 亮 px）⇒ 晚 5 级 ⇒ 引线减 5 场景帧。 | **−4,470** | 3 |

两个引线都改完之后，对话屏的 5 帧（步骤 12/13/14/15/17）**残差全为 0**。

---

## 5. 跑了哪些验证（命令 + 关键数字）

| # | 验证 | 命令 | 结果 |
|---|---|---|---|
| V1 | **构建** | `wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=… && make -j4"` | **exit 0，`ROM fixed!`**；告警全是既有的（`battle_range_ui_style.h` 的 switch-default、`append_combatant_hp` 未使用、`battle_scene_controller.h:948/961` 的 null-dereference、`battle_turn_flow.h` 的 stack-usage）—— **没有一条是本流引入的** |
| V2 | **ROM 4096 帧冒烟** | `python tools/s49_package/smoke_rom.py --rom …\butano-sequel.gba --out build/s49-u1/smoke.json --probe build/mgba-probe-y3/mgba-probe.exe` | **`OK: the ROM ran and the Chinese title screen rendered`**；`problems: 0`；标题 6 个墨迹连通域 / 2 241 墨迹像素 |
| V3 | **R×9 不崩** | `probe_client.py` + `tools/s49_pairing/lua/record_walk.lua`，键序 `Down,Down,A,A,R×9` | **exit 0、0 条崩溃标记**、done marker 写出、13 帧采完 |
| V4 | ⭐ **判定台（重录）** | `python tools/s49_fidelity_report.py --out build/s49-u1/bench/report.json --work-dir build/s49-u1/bench --skip-capture`（原版侧复用同一份捕获） | **field residual sum = 100 210**（基线 109 597 ⇒ **−9 387** ✔）；**full residual sum = 197 875**（基线 209 745 ⇒ **−11 870**）；**全 0 帧 = 5 / 25**（基线 2 ⇒ 验收要 ≥ 4 ✔）；归因 `identical 5 / product_diff 17 / pairing_diff 3`；子类 `black_transition 0 / static_frame 0 / moment_mismatch 3`；confidence `high 17 / medium 7 / low 1`。**对话的 5 屏（步骤 12/13/14/15/17）的 full residual 也是 0** ⇒ 不只是战场区，**连对话框里的文字都逐像素等于原版**（基线是 1265 / 1365 / 781 / 635 / 1449）。 |
| V5 | ⭐ **黑场真值（37 级）** | `python build/s49-u1/compare_levels.py`（新仪器；原版 `build/s49-blackfade/original-entry-v2/frames` vs 重制侧 `build/s49-u1/remake-entry/frames`） | **37 级全部对上，mismatches = 0**；逐级可见像素差 ≤ 104 px（差值来自重制侧战场内容与原版不同，level 4–11 / 13–21 差 0）；淡出 12 + 全黑 1 + 淡入 12 + **生长 12** 全在 |
| V6 | **黑场真值（判决工具口径）** | `python tools/s49_blackfade/blackfade_report.py --frames build/s49-u1/remake-entry/frames --out build/s49-u1/blackfade-remake.json` | 事件 3 = 淡出 / 全黑 / 淡入三段齐全；全黑帧 sha256 = `47fbde60…`（与原版**逐字节相同**） |
| V7 | ⭐ **标题** | `python tools/s49_v3_dialogue/verify_title_placement.py --staged …\graphics` | **residual_fixed = 264（相位 0）/ 341（相位 1）** ⇒ **完全复现 Y2 的真值 264 / 341**；合成标题墨迹框 (41,49)-(197,111)，与原版标题框一致；旧坐标是 5 238 / 4 094 |
| V8 | **标题素材逐像素** | `python tools/s49_v3_dialogue/check_title_asset_pixels.py --staged build/s49-v3/title-assets`（落地前）与 `--staged …\graphics`（落地后） | **10 个（件 × 相位）格子 `differing_pixels` 全 0** |
| V9 | ⭐ **逐格族名对拍（锚点版仪器）** | `python tools/s49_v2_anchor/compare_at_anchor.py --vram-dir build/s49-u1/vram-after` | **field: 同亮 168 / 原版缺 24 / 多画 24 / 族名不一致 56**（V2 基线 **81 / 111 / 36 / 26** ⇒ **同亮 +87、原版缺 −87**）；movegrid 168/24/24/50；grid16 153/22/39/70；banner 0/0/192/0。**目标 192/0/0/0 未达成**，剩余差异已归因（§6） |
| V10 | ⭐ **单测棘轮** | HEAD 基线 `wsl … build/run-baseline-tests.sh` / 工作区 `wsl … build/w1-run-all-tests.sh` | 基线 **pass=101 fail=20**；工作区 **pass=115 fail=20**；**失败集合逐名相同**（20 个名字全部列出并 diff）⇒ **new red = 0 ✔** |
| V11 | **密集 walk 重录** | `python tools/s49_pairing/record.py --side remake --out build/s49-pairing/walk-u1 --stride 4 --beats 30` | **783 帧 + 783 个 savestate**（与基线同帧数） |
| V12 | ⭐ **12 步流水线** | `python tools/s49_package/run_pipeline.py --out build/s49-u1/package`（**私有输出路径**，避免撞 U4） | **`ok: true`，12 步全绿**：build ✔ / unit-tests ✔（HEAD 101+20 vs 工作区 115+20，棘轮过）/ smoke ✔ / headless ✔ / judgment ✔（field 100 210、zeros 5）/ overlay ✔（棘轮过）/ idle-frames ✔ / outline-wave ✔（200/200）/ blackfade ✔ / audio ✔ / save-boundary ✔ / package ✔（69 个文件）。收据：`build/s49-u1/package/receipt.json` |
| V13 | **孤儿进程** | `Get-CimInstance Win32_Process -Filter "Name='mgba-probe.exe'"` | 本流用 `build/mgba-probe-y3`（只读调用，**没有覆盖共享的 `build/mgba-probe/mgba-probe.exe`**）；残留的 1 个 `mgba-probe-u2` 进程属于 **U2 流**，未动 |

---

## 6. 覆盖层：剩下的 24 / 24 / 56 是什么（已归因）

`build/s49-u1/overlay_diff.py` 逐格打印（仪器：`tools/s49_v2_anchor/compare_at_anchor.py`）：

* **原版缺 24 / 多画 24 ⇒ 是同一批 24 个地图位置**（map px x = 256 与 272，行 1..12）：
  原版记在逻辑列 **30/31**，重制侧记在逻辑列 **0/1**。
  根因是**仪器两侧的逻辑列索引空间不一致**：
  原版侧 `original_map_cells()` 用 `map_lx = (anchor_x + lx*16)//16`（**不回绕** 480），
  重制侧 `remake_logical_cells()` 用 `((col*8 + anchor_x) % 480)//16`（**回绕**）。
  ⇒ **内容覆盖其实已经一致**；这 24/24 是仪器口径问题（属 U4 的仪器活）。
* **族名不一致 56**：原版 `hatch` / `line_alt` vs 重制侧 `edge` / `hatch_shift`
  ⇒ 是**贴图族样式**的差异（`battle_range_ui_style.h` 的族定义），不是覆盖范围的差异。

⇒ **接线侧该做的已经做完**（内容锚点 + 绘制范围 1..12 + 受阻集）；
剩下的 192/0/0/0 需要 **U4 把仪器两侧的列索引统一** + **族样式对齐**。

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| U1-1 | 对话一个字都没画 = 字形渲染被关在输入门控里 | 把 `render_script_glyphs()` 搬出门控块 | 判定台步骤 13/14/15/17 的残差 674/702/417/756 → **0/0/0/0** | **已确认（修复生效）** |
| U1-2 | 标题画不出来 = 坐标体系错 | 换 `battle_opening_title::placements` | 步骤 09 的残差 5 733 → **759**，步骤 10 的 4 523 → **2 761**；`verify_title_placement` 残差 264 / 341 | **已确认（修复生效）** |
| U1-3 | 标题的 3 件素材全透明 + 相位打包错 ⇒ 换素材 | `check_title_asset_pixels.py` | 10 格全 0 差异（落地前后各一次） | **已确认** |
| U1-4 | 覆盖层的内容映射要用地图空间锚点 256 | 接 V2 的 API 后跑锚点版仪器 | 同亮 81 → **168**，原版缺 111 → **24** | **已确认（部分达成）** |
| U1-5 | ⭐ **V1 的残差回归是「生长移位时间轴」造成的** | 先只修遮罩坐标、生长仍关 | 修坐标后 159 697 → **114 304**（生长还没开就已经降了 45k）⇒ 回归的主因**不是**生长 | **已证伪（真因见 U1-6）** |
| U1-6 | ⭐ **遮罩用屏幕绝对坐标调 `create_sprite()` ⇒ 遮罩出屏、黑场不黑** | 读 Butano 的 `create_sprite` 语义 + 看黑场帧的像素 | 黑场帧里只有右下角黑；遮罩整体偏 (120,80) | **已确认（根因）** |
| U1-7 | 修掉遮罩坐标后 37 级逐级可见像素与原版一致 | `compare_levels.py` | **37 级 0 不匹配**（最大差 104 px，来自战场内容） | **已确认** |
| U1-8 | 生长 12 级打开后残差不回归 | 判定台复跑 | 114 304 → **104 784** | **已确认（该开）** |
| U1-9 | 黑场两个引线是黑场相对按键网格的相位旋钮 | 各改一档复跑判定台 | 事件 2：24→19 ⇒ **−4 470**；事件 1：36→38 ⇒ 全 0 帧 **3→5** | **已确认** |
| U1-10 | 事件 2 的引线改 19 后残差还在 173 px 差 | 逐帧亮像素读数 | 原版 step 18 = **0 亮 px**（全黑持黑最后一帧），重制侧 = **173 亮 px**（level 9）⇒ 还差 3 级 | **已确认（未闭合，见 §8）** |
| U1-11 | 覆盖层剩下的 24/24 是内容覆盖的差异 | `overlay_diff.py` 逐格打印 | 是**同一批 24 个地图位置**、两侧列索引空间不同 ⇒ 仪器口径问题 | **已确认（不是接线侧）** |
| U1-12 | 单测没有新增红项 | HEAD 基线 vs 工作区 | 20 → 20，**逐名相同** | **已确认** |

---

## 8. 未达成 / 剩余风险（**不粉饰**）

1. **逐格族名对拍没有到 192 / 0 / 0 / 0**：现为 **168 / 24 / 24 / 56**。
   剩余的 24/24 是**仪器**两侧的逻辑列索引空间不一致（同一批 24 个地图位置），
   56 是**族样式**（`hatch`/`line_alt` vs `edge`/`hatch_shift`）的差异。
   ⇒ **接线侧已做完；剩下的是 U4 的仪器活 + 族样式的活。**
2. **事件 2 的黑场还差 3 级**（判定台步骤 18 的残差 173 px）：原版落在持黑段的最后一帧
   （0 亮 px），重制侧落在淡出的 level 9（173 亮 px）。
   再减 3 级要再动引线，但**动引线会改对话的字形相位**（事件 1 的引线就是靠这一点把
   全 0 帧从 3 抬到 5 的）⇒ **本流按「验收指标优先」停在这里**，没有继续试。
3. **判定台步骤 08 / 11 / 18 / 19 仍比基线差**（+138 / +51 / +173 / +0），
   其中步骤 19 是 `pairing_diff`（原版 24 460，重制侧同样 24 460 ⇒ 与基线相同）。
4. **对话框斜切展开（接线点 ⑥）未做**：模型齐、运行时没有先例，按 V3 的建议单独排一轮。
5. **相位 1 的标题只有两个采样点**：原版的逐帧录制没有做，`phase_frames = 23` 是按采样推的。
6. **本机构建非字节可复现**：随包带 ROM + 复现命令。
7. **12 步流水线已在私有路径跑完，12 步全绿**（`build/s49-u1/package/receipt.json`，`ok: true`）。
   ⚠️ U4 也在跑流水线；两边各自用输出路径，**没有撞**。

---

## 9. 复跑命令

```powershell
# 1) 构建（必须显式导出 LIBBUTANOABS）
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel && \
  source /opt/devkitpro/devkitarm.sh && \
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"

# 2) 判定台（原版侧复用捕获，只重录重制侧）
python tools/s49_fidelity_report.py --out build/s49-u1/bench/report.json \
  --work-dir build/s49-u1/bench --skip-capture

# 3) 黑场 37 级真值
python tools/s49_package/capture_blackfade.py \
  --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
  --keys "Down,Down,A*21" --zero-frames 240 --frames 2552 \
  --out build/s49-u1/remake-entry
python build/s49-u1/compare_levels.py

# 4) 覆盖层逐格族名（锚点版仪器）
python tools/s49_w1/capture_remake_vram.py \
  --capture-dir build/s49-u1/bench/capture-remake --out-dir build/s49-u1/vram-after \
  --exe build/mgba-probe-y3/mgba-probe.exe
python tools/s49_v2_anchor/compare_at_anchor.py --vram-dir build/s49-u1/vram-after
python build/s49-u1/overlay_diff.py --vram build/s49-u1/vram-after/step-29-A.vram-0000.bin

# 5) 标题
python tools/s49_v3_dialogue/check_title_asset_pixels.py --staged build/s49-v3/title-assets
python tools/s49_v3_dialogue/verify_title_placement.py --staged "D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics"

# 6) 冒烟 / R×9 / 单测棘轮
python tools/s49_package/smoke_rom.py --rom "D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba" \
  --out build/s49-u1/smoke.json --probe build/mgba-probe-y3/mgba-probe.exe
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh
wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh

# 7) 12 步流水线（私有输出路径）
python tools/s49_package/run_pipeline.py --out build/s49-u1/package
```

---

## 10. 边界声明

* 逆向线 `D:\Shell\Github\gba-naruto-reverse` **全程只读**（本流没有打开它）。
* **未改** `battle_map_visual_projection.h` / `battle_scene_controller.h`（V2）、
  `battle_presentation_*.h` / `battle_opening_title.h`（V3）、
  `battle_result*.h` / `battle_runtime_result.h` / `generated_battle_result_content.h`（U3）。
* **未提交 git**；新文件一律 **LF、无 BOM**（§11 自检）。
* 本流**没有新增或修改任何单元测试文件** ⇒ 棘轮只可能变绿，不会变红（实测 new red = 0）。
