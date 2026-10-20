# S49 逆向侧未闭合项分诊（2026-10-20）

## 0. 范围、来源与只读声明

- 本文件只做**分诊**：对 4 个未闭合项分别写清「已确立 / 缺什么 / 最便宜的下一步 / 未确立」。不新增逆向结论。
- 逆向树只读：`/Users/altair/github/gba-naruto-reverse`，HEAD `f054f4c1e240c87583f1059b64eb1fc199aada07`。**本轮未写入逆向树任何文件**。
- ROM：`/Users/altair/github/gba-naruto/rom/base.gba`，SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- 解释器：`/usr/local/bin/python3`（3.14.3）。
- 本轮**未运行 mGBA**、未跑任何会写盘的逆向/复刻工具、未改动任何既有文件；只新增本文件。
- 「已确立」= 有文件路径或 ROM 地址可指；「未确立」一律写 `unknown`，不写「大概 / 看起来像」。

---

## 1. 原版 step-16 预览屏

### 已确立

1. **step-16 不是一张独立的「战前预览屏」**：它与 step-19 是**同一张移动范围（可达格）覆盖屏**的第二次出现，唯一差别是相机。
   - 收据：`artifacts/s49-original-movegrid-mechanism-v1/mechanism.json`（SHA-256 `83d22b5f6489a65dfa3ab29932dd2403da817f0f61ddb97d38a27188851c78ef`）→ `grid16_second_instance` = `{"bg0_hoffs": 152, "bg0_voffs": 40, "dispcnt": "0x1D40", "screenshot_delta_versus_field": 36323}`，note 原文：「A second instance of the move-range screen (walk step-16, camera panned to 152/40) repeats the same pattern」。
   - 帧级收据：`artifacts/s49-original-grid16-frame-v1/`（schema `konoha.mgba-frame-palette-sequence.v1`），`input_state` = `artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-16-A.ss9`，`input_state_sha256` `08cda9f3fbce3fc0505b77b2afcf965f37ac6b62bfad05d430670e113805e2a8`，`settle_frames=2`，`captured_frames=6`，落 PRAM 1024 B / VRAM 98304 B / IO 96 B。
   - 对照：step-19 同类收据 `artifacts/s49-original-movegrid-v1/manifest.json`，`input_state` = `walk-original-a24/step-19-A.ss9`。
2. **这一屏的控制器语义在逆向树已有名字**：38 态分母里 **0x3110 = `player_move_selection`**，entry `0x08073BA8`，`semantic_status = static_plus_checkpoint_runtime`。
   - 来源：逆向树 `notes/battle-controller-states-20260723.json`（SHA-256 `e0157597e6d7fddb94d036ddfa7a0d2e74fa232450ad08534cd868d6c6fe1336`），并经逆向树 `artifacts/rom-battle-controller-cfg-v1/rom-battle-controller-cfg.json`（SHA-256 `c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a`）的 38 条 `roots` 复核：`0x3110 → 0x08073BA8`。
   - 运行期绑定：主树 `notes/battle-controller-checkpoint-bindings-20260723.json`（SHA-256 `b12acafd034a842cbe135eb8c057305fba082466ffa4d80a21669f0274e98646`）中 `artifacts/runtime-checkpoints/scenario-41-player-turn.ss9`（`checkpoint_sha256` `ba411edee4ccf73c1b5a8392735d23dbbef6f8edce5240aef7acdcd76c436171`）的 frame = `{"callsite": "0x08073C88", "decoded_target": "0x0806F718", "entry": "0x08073BA8"}`。
   - 本轮复算（按 38 态分母）：`walk-original-a24/step-19-A.ss9` → `0x3110`（`validated_controller_ancestor`，frame `resume_pc=0x08073C8C`，callsite `0x08073C88` → `0x0806F718`）。**step-19 = 0x3110 成立。**
3. **覆盖层的图块与调色板在主树已被导出并与运行期内存交叉核对**（本轮新发现，纠正「还缺导出」的印象）：
   - `artifacts/s49-original-movegrid-overlay-v1/manifest.json`（SHA-256 `da42e2228a49e7dd81d64688641842ac7c4125fa14a20273d96021ad724f82db`），导出器 `tools/butano/export_s49_movegrid_overlay.py`（SHA-256 `7b9b398f81aeeb5bb3b55e1080a9502dcab7fe4eb86fb5211536c2da2c9f1d76`）。
   - `scope.established` 原文：「The 32-tile payload at ROM 0x080B9E94 is the BG2 tile set resident at VRAM 0x06002000 in the captured frames.」「The 32-byte payload at ROM 0x080B9F5C is palette bank 12, resident at PRAM 0x05000180 in the captured frames.」「The tile graphics and the palette are byte-identical across every captured frame of all four receipts; only the BG2 tilemap changes between states.」
   - 交叉核对锚点：LZ77 `0x080B9E94`（压缩 198 B，sha `b4e197b9…` → 解压 1024 B，sha `0f86c8032129ef1b92fb1464c516a03b1c0ca71672ac5de4d37e8b302cf6ce40`）、LZ77 `0x080B9F5C`（压缩 36 B → 解压 32 B，sha `d198ec85eff147b157978bb44d1948db5b9893edb5f8f63d4d9b96b5ca7e7e84`）；对运行期 dump 核对 `tiles_match_vram_window: true`（VRAM `0x2000..0x2400`）、`palette_match_pram_bank12: true`（PRAM `0x0180..0x01A0`），`bg2_tilemap_changed_cells_vs_baseline: 212`。
   - `artifacts/s49-original-movegrid-tilemap-v1/manifest.json`（SHA-256 `79968873f7fb98f9e408355fc7063836e87876926b0a50bd1072cab01bd84085`）已导出 **5 个** BG2 tilemap 收据，其中 `grid16-frame-v1`（`receipts.grid16-frame-v1.overlay = true`）就是 step-16 那一帧。
4. **覆盖层的 GPU 结构（主树实测）**：`notes/s49-dispcnt-bit10-layer-20261020.md:23-25` —— 变的是 **BG2**（图块 256–281、调色板 bank 12、字符区 `VRAM 0x06002000`），BG0（地图）调色板与图块逐字节相同 ⇒ 「给底色染色」被否证；ROM 资源：图块 LZ77 `0x080B9E94`（198 B → 1024 B = 32 个 4bpp 图块）→ `VRAM 0x06002000`，调色板 LZ77 `0x080B9F5C`（32 B）→ `PRAM 0x05000180`，装载代码 `0x080694C4`。
   - 逆向树侧只到「这是一对 LZ77 记录」：`reverse/notes/rom-pointer-lz77-graphics-preview-20260730.md:46` 列出 `0x080B9E94 → 0x080B9F5C`，并把这类归为「静态未绑定图形」——逆向树**没有**把它标注为移动范围覆盖层。
5. **屏幕顺序**：原版 a24 录制 14=战场+移动光标 / 15=回合横幅 / 16=移动范围网格 / 17=战场「SELECT人物」/ 18=命令菜单（`notes/s49-fidelity-handover-20261019.md:2569-2575`）；重制 17→21 = 战场→命令菜单→移动网格→行动结束→动作菜单（同文件 `:2577`）。
6. **两边不是同一场战斗**（同文件 `:2742-2768`）：原版 step-16 中间是木叶丸、右侧鸣人+选择框、左上/左下各 1 只蜜蜂（模板计数 42/42，重制 15/42），原版地图有水渠、重制没有。

### 缺什么

1. **step-16 这一实例的控制器态未闭合**：本轮复算 `walk-original-a24/step-16-A.ss9` 只得到 ancestor 判据下的 `0x8000`（frame `resume_pc=0x08074436`，callsite `0x08074432` → `0x0806ED68`），**不是** `0x3110`；`0x3110` 的绑定目前只有 scenario-41 的存档。
2. **覆盖层的语义仍未闭合**（主树导出器自己列在 `scope.not_established` 里，逐条照抄）：
   - 「Which tilemap cells the game lights up: the BG2 tilemap content is generated at runtime and no ROM record for it was found.」⇒ **生成 BG2 tilemap 的那条 ROM 记录至今没找到**；
   - 「Whether the overlay marks reachable or unreachable ground: the layer is identified, its meaning is not.」⇒ **这一层标的是可达还是不可达，仍未判定**；
   - 「Whether the layer is reached by natural execution: the receipts are a scripted walk, not a coverage proof.」；
   - 「Whether the 32 tiles are all used: the captured frames reference only part of the tile set.」；
   - 「The PNG screenshots of the receipts are not self-consistent with their own dumps, so no pixel-level claim about the rendered overlay is made here.」⇒ **收据里的 PNG 与自己的 dump 不自洽，不能对其渲染结果做像素级断言**。
3. **逆向树侧没有对应 artifact**：逆向树只有 `0x080B9E94 → 0x080B9F5C` 这对 LZ77 记录（`reverse/notes/rom-pointer-lz77-graphics-preview-20260730.md:46`），归类为「静态未绑定图形」，既没有「它是移动范围覆盖层」的结论，也没有 `0x080694C4` 装载点与 `VRAM 0x06002000` 目的地址的运行时绑定收据。
4. **「无状态栏」只有散文**：出现在 `notes/s49-fidelity-handover-20261019.md:3261` 与 `:3319`，无机器收据。
5. **覆盖层染色机制**（抖动遮罩 / alpha 混合）在逆向侧无对应 artifact。

### 最便宜的下一步

- **(a) 判这一屏是什么 —— 已有答案，只需把绑定落到 S49**：见第 3 节的 38 态库存重建命令，对 `walk-original-a24/step-16-A.ss9` 与 `walk-original-a24/step-19-A.ss9` 各跑一次；产出 `notes/battle-controller-checkpoint-bindings-38-20261020.json`。若 step-16 仍只得 ancestor，需要在 `0x08073C88`（0x3110 的调用点）再取一帧。
- **(b) 找「生成 BG2 tilemap 的那条 ROM 记录」（主树导出器自认没找到的那一条）**：这是本项真正的逆向缺口。检索面已由主树收据钉死：tilemap 在 `VRAM 0x06001000`（BG2 screen base block 2）、图块在 `VRAM 0x06002000`（tile 256..287）、调色板 bank 12 在 `PRAM 0x05000180`；且 `scope.established` 写明图块与调色板**逐帧不变、只有 tilemap 变** ⇒ 写这 1024 格的是**运行期代码**。逆向侧起点：`0x080694C4` 附近的装载代码（`notes/s49-dispcnt-bit10-layer-20261020.md:25`）与 BG2 tilemap 写入点；产出建议落逆向树 `artifacts/rom-move-range-overlay-tilemap-v1/`（写入须由逆向树属主执行，本轮只读未做）。
- **(b') 把主树已有的导出提升为逆向侧 artifact（零实验成本）**：`artifacts/s49-original-movegrid-overlay-v1/` 的图块/调色板字节与 `VRAM 0x06002000` / `PRAM 0x05000180` 的运行期核对结果可以直接搬进逆向树，逆向树现有 `rom-pointer-lz77-graphics-v1` 只差「这组 LZ77 就是移动范围覆盖层」这一条语义绑定。
- **(c) 若目标只是「重制没有这一屏」**：逆向侧已足够——它是 0x3110 移动选择屏的第二次出现（相机 152/40），缺的是重制侧实现，不是逆向判定。

### 未确立

- step-16 实例的控制器态 —— `unknown`（本轮只得到 ancestor `0x8000`）。
- 「无状态栏」的机器级证据 —— `unknown`。
- 覆盖层图块是否与地图图块是「同一资源的两份拷贝」 —— `unknown`（`notes/s49-fidelity-handover-20261019.md:3556` 已把它作为给逆向侧的问题提出，至今无结论）。
- 覆盖层标的是「可达」还是「不可达」 —— `unknown`（主树导出器 `scope.not_established` 明写「the layer is identified, its meaning is not」）。
- 收据 PNG 与 dump 不自洽的原因 ⇒ ⚠️ **第 20 轮更正**：**不存在**。用参考渲染器从同帧 dump 重建，移动网格帧/战场帧/横幅帧 **逐像素一致**（38,400/38,400）；当年的判断来自「朴素的调色板颜色集合检查」（看不见 alpha 混合色）＋ `BLDCNT` 读错。

---

## 2. 待机 31 姿态

### 已确立

1. **「31」不是 ROM 侧的姿态数**。逆向树 `artifacts/character-battle-visuals-v1/manifest.json`（SHA-256 `a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c`）里 field slot（`visual_slot 0`，`semantic = "field_idle_and_movement"`）62 个角色全部有动画；逐个统计：
   - 56/62：4 条 `duration_frames=32` 的动画，每条 4 个 keyframe、`hold_frames` 全为 8，合计 12 个不同 `frame_id`；
   - 2/62：8 条 32 帧动画、20 个 `frame_id`；1/62：8 条 32 帧动画、24 个；1/62：1 条 32 帧动画、3 个；2/62：无 32 帧动画。
   - **没有任何角色是 31**。
   - `character_id=1`（resource 0）实例：32 帧动画的 keyframe 序列为 `[0,1,2,1]` / `[3,4,5,4]` / `[6,7,8,7]` / `[9,10,11,10]`，hold 全 8 ⇒ **一个 32 帧周期只有 3 个不同姿态**（与 `notes/s49-fidelity-handover-20261019.md:3322` 的「32 帧 / 每姿态 hold 8 / 三姿态」一致）。
2. **「31」= 运行期「32 帧内互不相同的图像数」，已有专用测量器与门禁**（主树 `tools/butano/measure_s49_rule_idle_sequence.py`，SHA-256 `bc83fbb57f81c4802a132b79dd600ec28b36ff41ad8cf79ebb224d6b470b247c`，schema `konoha.s49-rule-idle-sequence.v1`；门禁 `tests/test_s49_rule_idle_sequence.py`）。本轮原样跑通，输出（仅 stdout，不写盘）：
   - `original.sweep` = `artifacts/s49-fidelity-20261019-v1/original-idle-sweep`，`first_frame_sha256` `7bb28820bd83fb89de189d1b0e36f76b54e349690383670dd42079c80d7a80da`，`frames_measured` 192，`changed_region_bbox` `(109,32,146,90)`；
   - `original.full_region`（region `(109,32,147,91)`）：**`distinct_images_in_32_frames` = 31**，`identical_neighbouring_frames_in_32` = 1，`changed_transitions` 183 / `total_transitions` 191；
   - `original.sprite_region`（region `(118,32,147,91)`）：**`distinct_images_in_32_frames` = 30**，同样 183/191 次变化；
   - `rom_model`：62 个角色有 field slot；`cycle_length_to_animations` = `{32: 249, 12: 213, 14: 212, 48: 4, 16: 12, 8: 1, 4: 4}`；**`cycle_length_to_max_distinct_frames` = `{32: 3, 12: 4, 14: 3, 48: 6, 16: 9, 8: 1, 4: 3}`**（32 帧周期最多 3 个不同帧）。ROM 侧模型取自 `butano-sequel/graphics/battle_unit_visual_catalog.json`（`table_offset_hex` `0x596D5C`，`source_rom_sha256` 与基准 ROM 一致）。
   - **「31 vs 30」之谜已解**：不是矛盾，是**取样区域不同** —— 31 = 全区域 `(109,32,147,91)`，30 = 精灵区 `(118,32,147,91)`。主树笔记 `notes/s49-fidelity-handover-20261019.md:3265`（31）与 `:3321`（30/32）指的是这两个不同区域。
   - 本轮独立复核（只读、像素级，主树 `artifacts/s49-fidelity-20261019-v1/original-longidle/`，1000 张 240×160 PNG）：32 帧窗口 `[0:32]`/`[64:96]` 得 31 个互不相同的图（整帧与单位裁切一致），窗口 `[128:160]`/`[256:288]`/`[512:544]` 得 30 个；逐帧 diff bbox 覆盖整个精灵（25×52 … 38×59），**不是**一个小标记在动 ⇒ 整个单位图像在逐帧变。与测量器结论一致。
3. **逆向树自己声明运行期未闭合**：
   - `artifacts/character-battle-visuals-v1/manifest.json` 的 `scope` = `{"static_source_space_frames": true, "animation_holds": true, "pointer_bounded_source_previews": false, "screen_space_position": false, "camera_and_priority": false, "runtime_slot_selection": false, "blend_and_palette_transform": false, "all_component_termination_semantics_complete": true}`。
   - `artifacts/character-runtime-unit-oam-bindings-v1/bindings.json`（SHA-256 `346310eecece5053f3b7a23f7620104f2980ecadb3e36d869768c78eb7aca0f3`）的 `scope` 含 `unit_animation_state_to_source_frame_complete: false`、`live_unit_oam_ownership_proven: false`、`unit_constructor_or_selector_trace_complete: false`、`all_live_units_visualized: false`。
4. **逆向树已证明的是「帧选择」通路，不是「时间线」**：`artifacts/character-battle-visual-resource-matrix-v1/manifest.json`（SHA-256 `41baf4a2f087723e1d51de2629e1065958bd1d7ddd655f3157dbb0de41966fdb`）的 `scope` = `{"resource_0_timeline_frame_selection_pixel_ab": true, "full_animation_timing_verified": false, "all_250_resources_runtime_verified": false, "camera_blend_transform_verified": false}`；其 `runtime-evidence.json` 的输入是 `artifacts/runtime-checkpoints/scenario-41-start-row.ss9`（选人起始行），**不是战场**。

### 缺什么

1. **缺运行期把单位动画状态推进到具体 frame 的那条路径**，且这件事**已被测量器自己写在结论里**：`tools/butano/measure_s49_rule_idle_sequence.py` 的 docstring 原文 —— 「the original's *per frame* redraw is not explained by the ROM's hold field, so the frame order (帧序) of the original's field animation is still open on the reverse side.」；`notes/s49-fidelity-handover-20261019.md:3323` 同义（「缺的是『哪条运行期路径逐帧推进单位视觉帧』」）。逆向树 `notes/` 里没有任何一条关于单位待机帧推进的记录。
2. **缺逐帧 OAM/VRAM 收据**：需要在 32 帧窗口内逐帧读该单位 OAM 条目的 tile index，再与 `character-battle-visuals-v1` 的 `resources[].frames[].components[]` tile 表比对，才能判定运行期用的是哪个 `frame_id`。
3. ~~**缺「31 vs 3」矛盾的解释**~~ ⇒ **第 15 轮已推翻本条推断**：实测（原版 96 帧窗口）显示
   运行期的**帧序就是 ROM 的 `resources[0].animations[3]`**（`0x08142AFC`
   `[(9,8),(10,8),(11,8),(10,8)]`，周期 32）⇒ 运行期显示的**就是** field slot 那套帧，
   「30 幅互不相同」来自**同一帧的描边调色板逐帧改写**（index 15，32 帧三角波），
   而**不是**新帧、也不是新 slot。详见 `notes/s49-field-frame-order-20261020.md`。
4. **「31」与重制侧模型的对齐**没有门禁结论：测量器只并列报告两侧（原版 30–31 幅 vs 重制 32 帧四步 4 姿态），没有给出「重制该改成什么」的可执行规格。

### 最便宜的下一步

- **复现既有测量（零成本，先把口径钉死）**：

```
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
/usr/local/bin/python3 tools/butano/measure_s49_rule_idle_sequence.py
```

  只输出 stdout，不写盘；门禁 `tests/test_s49_rule_idle_sequence.py` 守着它。
- **逐帧 OAM 收据（主线）**：复用主树既有探针 `tools/butano/mgba_gpu_state_dump.lua` + `tools/butano/capture_s49_gpu_state.py`，从 `artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9`（SHA-256 `a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1`）起零输入跑 32 帧，每帧落 OAM 1024 B，产物写 `artifacts/s49-original-unit-oam-timeline-v1/`；再用逆向树 manifest 的 `resources[].frames[].components[].tile` 做匹配表。**本轮 mGBA 被占用且受守卫，未执行。**
- **静态侧（可与上条并行）**：逆向树定位「谁递增单位的视觉帧计数器」——已知 `character-battle-visuals-v1` 的 `consumer.selector` 在 `0x0807AE04..0x0807B284`（sha `5a0d06474ee94f5d3fd68cfe6c90224ce5a4cc8ffbb8ceeb6c4529c67ecd1b0b`）、`sprite_task_allocator` 在 `0x080625A4..0x080626B0`（sha `e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54`）；从后者反查单位记录里的帧计数字段。
- **反向验证**：若逐帧 OAM 的 tile index 与 resource 0 的 20 帧组件表**一个都匹配不上** ⇒ 证明渲染的不是 field slot 资源，问题转为「slot 选择」；逆向树 `left_facing_empty_slot_fallback` 只覆盖 slot 5..8 → 1..4，未覆盖 slot 0。

### 未确立

- 运行期那 32 帧窗口里单位用的**具体 `frame_id` 序列** —— `unknown`。
- 「31 姿态」这个措辞本身 —— `unknown`：已确证的是「32 帧内互不相同的**图像**数 = 31（全区域）/ 30（精灵区）」，不等于「姿态」数；一个姿态可能对应多幅图，反之亦然。主树台账 `notes/butano-reverse-gap-verification-20261020.md:265` 写的「单位待机动画 31 姿态」把图像数说成了姿态数。
- 屏幕上那只是不是 `character_id=1`（Naruto） —— `unknown`（我仅用逆向树 `bindings.json` 里 `origin (120,80)` / `grid (4,10)` 作推断，未做逐帧 OAM 归属核对）。
- 逆向树是否已存在未以「frame counter / advance frame」措辞书写的待机推进记录 —— `unknown`（grep 仅命中音效调度 `m4a-soundmain-scheduler-20260713.md:14` 与特效帧计数 `battle-effect-controlled-runtime-20260801.md:31`）。

---

## 3. 12 个 unknown 态

### 已确立

1. **权威分母**：逆向树 `artifacts/rom-battle-controller-cfg-v1/manifest.json`（SHA-256 `282b4323bf965676a68b5326f2edbbdee35606b987412d351de137b82d50fe63`）/ payload `rom-battle-controller-cfg.json`（SHA-256 `c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a`），65,536 输入分母、38 个非 default 态、38 条 `roots`。12 个 unknown 态的入口与 `roots` **逐条核对一致**。
2. **闭合契约**：主树 `sequel/content/battle_controller_states.json` 每个 unknown 态的 `missing_evidence` 要求**两件**：① handler 级静态断言（说清 handler 读/写什么）；② **至少一个哈希绑定的运行期 checkpoint，其 controller frame 落在该态区间 [start,end) 内**。
3. **条件①的材料已齐**：主树 `notes/s49-unknown-state-handlers-20261020.md`（SHA-256 `cec65e6cb5eb71d628a0c3bd65a956062e8cc7473bc4ced0e61662e17de2f5f1`）对 12 态逐条给出入口、分派点、行为与决定性指令地址。
4. **条件②已有 2 态被既有主树存档满足**（本轮新算，见下表 `现有哈希绑定` 列）。
5. **现有绑定文件是 36 态口径**：`notes/battle-controller-checkpoint-bindings-20260723.json`（SHA-256 `b12acafd…`）基于 `notes/battle-controller-states-20260723.json`（36 态，SHA-256 `e0157597…`）。其中标为 `0x1220` 的那条 frame entry 是 `0x080736F8` = 38 态分母的 **0x1210**，与 38 态的 0x1220（entry `0x080737E6`）**不是**同一 handler；`notes/s49-unknown-state-handlers-20261020.md:103-105` 已记录这一命名撞车。
6. **区间内有无非出口 `bl`**（本轮用 `rom/base.gba` 原始半字独立扫描复核，与主树笔记一致）：`0x3100` / `0x8010` / `0xA000` 三个区间内**只有**公共出口 `bl 0x0807504E` ⇒ 被动 `.ss9` checkpoint 的「栈内返回点」判据**永远落不进来**，必须一次性断点/观测器；其余 9 态区间内有非出口 `bl` ⇒ 被动 checkpoint 可行。

### 逐态闭合条件（12 行，每行一个可判定的条件）

| 态 | 入口 | 区间 [start,end) | 现有哈希绑定 checkpoint | 可达 frame PC（区间内非出口 `bl` 的返回 PC） | 闭合条件 | 最便宜的下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| 0x0010 | `0x08073638` | `[0x08073638,0x0807364A)` | **有**：`artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-09-A.ss9`（sha `e193b4143270843ca1abf4f23759747701eaab85e419fc36d63965629a931583`），`validated_controller_ancestor`，frame `resume_pc=0x0807363E`（栈内返回字 `0x0807363F`，来自 callsite `0x0807363A` 的 `bl 0x08072EDC`，原始半字 `f7ff fc4f` 已复核） | `0x0807363E`（→`0x08072EDC`）、`0x08073642`（→`0x08073000`） | **已满足**：条件②有现成存档；补条件①（主树笔记的静态断言）即可 | 用第 3 节命令按 38 态重跑，把这条 observation 写进 `notes/battle-controller-checkpoint-observations-20261020.json`（`expected_controller_state: "0x0010"`） |
| 0x1000 | `0x0807364A` | `[0x0807364A,0x0807367C)` | 无 | `0x0807365E`（`bl 0x080753F8` @`0x0807365A`） | 一份 checkpoint，其 frame `resume_pc` ∈ 区间；等价于在 `0x080753F8`（本单位单位扫描）内取一帧 | 从 `artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9` 零输入推进到敌方/我方相位切换，在 `0x080753F8` 内取帧（同时记返回后的 `r4`，判掉未命中分支） |
| 0x1200 | `0x080736B0` | `[0x080736B0,0x080736F8)` | 无 | `0x080736C8`（`0x0807305C`）、`0x080736D2`（`0x08074FDA`）、`0x080736E2`（`0x0806DF88`）、`0x080736E8`（`0x08075350`） | 一份 checkpoint，其 frame `resume_pc` ∈ 区间；同一次采样读 `0x0202680E` 前后值 | 复用逆向树 `battle-status-expiry` 已有 side-end 单输入复放，在 `0x08075350` 内取帧（该 handler 最后一个调用） |
| 0x1220 | `0x080737E6` | `[0x080737E6,0x080738C0)` | **有**：`walk-original-a24/step-15-A.ss9`（sha `131b4265309441baa398416c35df258dcec91151e35c6a8bf9fa736fb94714aa`），`direct_controller_resume`，`resume_pc=0x08073884`；另有 `artifacts/s49-fidelity-20261019-v1/original-dialogue/step-15-A.ss9`（sha `c362b2652cda657498d0c082cd1d24e81270f1b13ef1def833c69e4f04b2a2a2`）同样 | `0x08073818`、`0x08073832`、`0x08073846`、`0x08073866`、`0x0807386A`、`0x08073884`、`0x08073896`、`0x080738A2`、`0x080738A6`、`0x080738B2` | **已满足**：条件②有两份现成存档；补条件①即可 | 同 0x0010：按 38 态重跑并把两条 observation 写进新的 observations 文件（`expected_controller_state: "0x1220"`） |
| 0x3100 | `0x08073B84` | `[0x08073B84,0x08073BA8)` | 无（区间内**只有**公共出口 `bl 0x0807504E`） | **无** | 一次性断点/观测器采样：`r1`（current unit pointer P）、`P+5`、`0x0202680E` | 在 `0x08073B84`（或分派点 `0x08073458`）下断点读上述三值；被动 `.ss9` 落不进来 |
| 0x3200 | `0x08073E14` | `[0x08073E14,0x08073EB0)` | 无 | `0x08073E26`、`0x08073E42`、`0x08073E48`（`0x08067158`）、`0x08073E9E`、`0x08073EA4` | 一份 checkpoint，其 frame `resume_pc` ∈ 区间；并读 `P+7/P+8/P+0xA/P+0xC` 与 `P+0x0E`(HP) 前后值 | 在 `0x08073E5C..0x08073E6A`（写 `P+7`/`P+0xC` 的两条指令）外侧取帧 |
| 0x3220 | `0x08074074` | `[0x08074074,0x080740D4)` | 无 | `0x0807407A`、`0x08074080`（`0x08067158`）、`0x080740A8`（`0x08070D84`） | 一份 checkpoint，其 frame `resume_pc` ∈ 区间；并读 `r1`(=delta)、`0x02026A41`(选中槽)、`0x02026A42+slot` 落值 | 在 `0x080740A4`（`bl 0x08070D84`）处取帧 |
| 0x8010 | `0x08074510` | `[0x08074510,0x08074550)` | 无（区间内**只有**公共出口 `bl 0x0807504E`） | **无** | 一次性断点采样：`P+0xCC`、`P+0xCD` 与分支后 `r6` | 在 `0x08074510` 下断点；被动 `.ss9` 落不进来 |
| 0xA000 | `0x0807484E` | `[0x0807484E,0x08074870)` | 无（区间内**只有**公共出口 `bl 0x0807504E`） | **无** | 一次性断点采样：被载入的 `r6` 与 `0x0202D24C..0x0202D25F` 20 字节 | 在 `0x08074862`（`adds r6,r7,#0`）下断点；被动 `.ss9` 落不进来 |
| 0xB000 | `0x08074870` | `[0x08074870,0x080748AC)` | 无 | `0x0807487E`（`0x08067158`）、`0x08074888`（`0x08085A40`）、`0x0807488C`（`0x08085A74`）、`0x08074896` | 一份 checkpoint，其 frame `resume_pc` ∈ 区间；并读 `0x02026A40` 的 20 字节与 `0x0200A880/0x0202A882` | 在 `0x08074884`（`bl 0x08085A40`）处取帧；ROM `0x0812F18C` 的 20 字节以 ASCII `DEFCOMMAND` 开头 |
| 0xC000 | `0x080748AC` | `[0x080748AC,0x08074918)` | 无 | `0x080748DE`（`0x08067158`）、`0x080748E8`（`0x08085B8C`）、`0x080748EC`（`0x08085BC0`）、`0x080748F6`、`0x08074900` | 一份 checkpoint，其 frame `resume_pc` ∈ 区间；并读 `0x02026804`、`0x02026A40` 的 20 字节与后继 `r6` | 在 `0x080748B0`（`cmp r0,#0`）处取帧 |
| 0xE000 | `0x08074988` | `[0x08074988,0x080749CC)` | 无 | `0x08074990`（`0x08081544`）、`0x080749AC`（`0x0806A854`）、`0x080749C2` | 一份 checkpoint，其 frame `resume_pc` ∈ 区间；并读 `0x0202680F`、`P+0xCC`、`0x02026A56`、`unit+0xC0` | 在 `0x0807498C`（`bl 0x08081544`）处取帧 |

> 「可达 frame PC」= 分析器会算出的 `resume_pc`（= callsite + 4；`raw_return_word` = callsite + 5，Thumb 位）。判定式：checkpoint 的栈内返回点落进 `[start,end)` ⇒ 该 checkpoint 满足条件②。

### 缺什么

1. **条件②对 10 态仍缺**：0x1000 / 0x1200 / 0x3100 / 0x3200 / 0x3220 / 0x8010 / 0xA000 / 0xB000 / 0xC000 / 0xE000。
2. **条件①尚未落进 `battle_controller_states.json`**：12 态的 `name_status` 仍是 `unknown`；`sequel/content/battle_controller_states.json` 的 `missing_evidence` 明写「Until both exist this state must stay unnamed」。
3. **绑定口径未升级到 38 态**：现有 `notes/battle-controller-checkpoint-bindings-20260723.json` 是 36 态口径；`notes/battle-controller-checkpoint-observations-20260723.json` 里 `scenario-41-turn-1-complete.ss9` 的 `expected_controller_state` 写的是 `0x1220`，在 38 态下应为 `0x1210`。
4. **18 条 observation 里有 4 条指向已不存在的文件**：`build/scenario-45-round1-enemy-phase-20260719/pulse-0{1,2}.ss9`、`build/scenario-50-battle-15-round2-resource-route-20260720/{k11-defense,e1-wait}/output.ss9`（本轮实测全部 MISS）；分析器对缺失文件是**失败关闭**（`tools/analyze_battle_controller_checkpoints.py:222-228`），不修这 4 条就整批跑不完。

### 最便宜的下一步

- **(1) 重建 38 态库存（必做前置）**：从逆向树 CFG payload 生成 `notes/battle-controller-states-38-20261020.json`（字段须含 `controller_entry` / `controller_end` / `controller_sha256` / `states[].entry`，sha 与 `c9bdc220590a851fa331960bcb32be90eb9ac7248a5cd3dabb9f8afa0b674bc1` 对应 controller 区间 `0x080732B4..0x0807509C`）。
- **(2) 修 4 条失效 observation**：把那 4 条 `build/` 路径从新 observations 文件里剔除（或从逆向树补回存档），否则失败关闭。
- **(3) 改 1 条旧标签**：`scenario-41-turn-1-complete.ss9` 的 `expected_controller_state` 改成 `0x1210`。
- **(4) 补 3 条新 observation**（本轮已算好期望值）：
  - `artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-09-A.ss9`（sha `e193b414…`）→ `expected_controller_state: "0x0010"`；
  - `artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-15-A.ss9`（sha `131b4265…`）→ `"0x1220"`；
  - `artifacts/s49-fidelity-20261019-v1/original-dialogue/step-15-A.ss9`（sha `c362b265…`）→ `"0x1220"`。
- **(5) 跑分析器**，产物 `notes/battle-controller-checkpoint-bindings-38-20261020.json`：

```
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
/usr/local/bin/python3 tools/analyze_battle_controller_checkpoints.py \
  --states   notes/battle-controller-states-38-20261020.json \
  --observations notes/battle-controller-checkpoint-observations-20261020.json \
  --output   notes/battle-controller-checkpoint-bindings-38-20261020.json
```

- **(6) 0x0010 与 0x1220 随即可从 `unknown` 升为 `named`**（条件①②都齐），并同步 `sequel/content/battle_controller_states.json` 的 `name` / `name_status` / `semantic_status` / `evidence`。
- **(7) 其余 10 态按上表「可达 frame PC」逐条取帧**：9 态用被动 checkpoint（在下表列出的 `bl` 目标函数内取帧即可让 frame 落进区间），3 态（0x3100 / 0x8010 / 0xA000）必须一次性断点。

### 未确立

- 0x0010 与 0x1220 的**语义名称** —— `unknown`（本轮只证明「存在落在区间内的哈希绑定 checkpoint」，命名仍是主树笔记的**提议名**，未经运行期语义闭合）。
- 0x1000 未命中分支的后继态（`r6=r4`） —— `unknown`。
- `unit+5`（0x3100 读的字节）与 `P+0xA`/`P+0xC`（0x3200）的字段角色 —— `unknown`（静态指令流推断，未运行期闭合）。
- 0xB000 与 0xC000 的**游戏语义差别** —— `unknown`（两者共用 `DEFCOMMAND` 源与 `0x02026A40` 目的，仅分支各多做一件事）。

---

## 4. 23 个 pixel-A/B 族缺 scenario-47/50/53 checkpoint

### 已确立

1. **「23」的准确出处**：主树 `artifacts/butano-reverse-m3-import-v1/pixel-ab/baselines.json`（SHA-256 `aa1a4606f4005252d9c83b5c12fbd06b690c25822245836f9b764e00c0e67a3e`），`family_count = 32`，其中 **`applicability = "no-local-anchor-in-this-tree"` 恰为 23 条**，`"local-anchor-found"` 为 9 条。23 条的 `local_anchors` 全为空数组。
2. **9 条「有本地锚」的族全部锚在 scenario-41**：`battle-effect-group1`/`group5`（`artifacts/runtime-checkpoints/scenario-41-attack-confirmation.ss9`）、`battle-encounters-story-visual`（`scenario-41-postbattle-dialogue-8.ss9`）、`character-battle-graphics` 与 `map41-primary-layout`（`scenario-41-start-row.ss9`）、`cutscene-obj-id1`（`scenario-41-combat-popup.ss9`）、`map-sprites-definition-id1`（`scenario-41-combat-dialogue.ss9`）、`menu-portrait`（`scenario-41-postbattle-dialogue-9.ss9`）、`world-map-page0`（`scenario-41-postbattle-dialogue-11.ss9`）。
   ⇒ **主树笔记 `notes/s49-fidelity-handover-20261019.md:3327` 的「缺 scenario-47/50/53 的 checkpoint」措辞不精确**：23 条里只有 **5 条**需要 scenario-47/50 存档，其余需要 scenario-49 / battle3 / battle8 / 家族私有存档。
3. **23 条的精确缺件清单**（`baselines.json` 的 `unavailable_local_inputs`，逐条原样）：

| 族 | 缺的本地产物 |
| --- | --- |
| `battle-effect-group03-controlled-pixel-ab-v1` | `sequel/content/battle-effect-controlled-pixel-ab/group-03-sequence-03-side-0-direct-spawn.json` |
| `battle-effect-group03-natural-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready{,-evidence}.{ss9,json}`、`sequel/content/battle-effect-natural-pixel-ab/group-03-tool67-expiry.json` |
| `battle-effect-group06-controlled-pixel-ab-v1` | `sequel/content/battle-effect-controlled-pixel-ab/group-06-sequence-08-controlled.json` |
| `battle-effect-group07-controlled-pixel-ab-v1` | `sequel/content/battle-effect-controlled-pixel-ab/group-07-sequence-09-controlled.json` |
| `battle-effect-group08-controlled-pixel-ab-v1` | `sequel/content/battle-effect-controlled-pixel-ab/group-08-sequence-10-controlled.json` |
| `battle-effect-group09-controlled-pixel-ab-v1` | `sequel/content/battle-effect-controlled-pixel-ab/group-09-sequence-11-controlled.json` |
| `battle-effect-group10-controlled-pixel-ab-v1` | `sequel/content/battle-effect-controlled-pixel-ab/group-10-sequence-12-controlled.json` |
| `battle-effect-group11-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-50-cross-shuriken-confirmation.ss9`、`sequel/content/battle-effect-pixel-ab/group-11-cross-shuriken.json` |
| `battle-effect-group12-controlled-pixel-ab-v1` | `sequel/content/battle-effect-controlled-pixel-ab/group-12-sequence-14-controlled.json` |
| `battle-effect-group13-pixel-ab-v1` | `artifacts/runtime-checkpoints/battle3-action61-ai-preconfirm.ss9`、`sequel/content/battle-effect-pixel-ab/group-13-action61-execution.json` |
| `battle-effect-group14-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-47-fire-action16-confirmation.ss9`、`sequel/content/battle-effect-pixel-ab/group-14-fire-action.json` |
| `battle-effect-group15-pixel-ab-v1` | `artifacts/runtime-checkpoints/battle8-action64-ai-preconfirm.ss9`、`sequel/content/battle-effect-pixel-ab/group-15-action64-water-dragon.json` |
| `battle-effect-group16-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-confirmation.ss9`、`sequel/content/battle-effect-pixel-ab/group-16-tool67-tag.json` |
| `battle-effect-group17-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-49-battle-14-tool37-confirmation.ss9`、`sequel/content/battle-effect-pixel-ab/group-17-tool37-smoke.json` |
| `battle-effect-group18-controlled-pixel-ab-v1` | `sequel/content/battle-effect-controlled-pixel-ab/group-18-sequence-07-direct-spawn.json` |
| `battle-effect-group18-natural-pixel-ab-v1` | `artifacts/battle-effect-group18-natural-checkpoint-v1/manifest.json`、`artifacts/battle-effect-group18-natural-checkpoint-v1/raw/object-created.ss9`、`sequel/content/battle-effect-natural-pixel-ab/group-18-tool67-zero-event-expiry.json` |
| `battle-effect-group2-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-50-action7-shadow-clone-confirmation.ss9`、`sequel/content/battle-effect-pixel-ab/group-02-action7-shadow-clone.json` |
| `battle-effect-group4-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-50-cross-shuriken-confirmation.ss9`、`sequel/content/battle-effect-pixel-ab/group-04-tool1-projectile.json` |
| `data-table-b-message0-pointer-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-50-action7-shadow-clone-confirmation.ss9`、`tools/mgba_input_sequence_replay.lua` |
| `map-events-e4-handler-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready.ss9` |
| `motion-effect-parameter-pixel-ab-v1` | `artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready{,-evidence}.{ss9,json}`、`sequel/content/motion-effect-parameter-pixel-ab/group-03-record-00-y-offset.json`、`sequel/content/palettes/bank.json` |
| `residual-wram-tilemap-pixel-ab-v1` | **空列表**（`unavailable_local_inputs: []`，即缺件未被记录） |
| `tile-asset-descriptor2-pixel-ab-v1` | `artifacts/residual-wram-tilemap-runtime-v2/scene-panel-setup.ss9`、`artifacts/runtime-checkpoints/scene-visual-controller-mode0-preselector.ss9` |

4. **这些缺件在逆向树里全部存在**（本轮只读核验，SHA-256 前 16 位）：`scenario-50-cross-shuriken-confirmation.ss9` `57d4929ef3c8b305`、`scenario-50-action7-shadow-clone-confirmation.ss9` `2b800fe160992396`、`scenario-47-fire-action16-confirmation.ss9` `50330328232cb626`、`scenario-49-battle-14-tool67-expiry-ready.ss9` `34eb56d34d876a27`、`scenario-49-battle-14-tool67-confirmation.ss9` `95cc6805139fa6ba`、`scenario-49-battle-14-tool37-confirmation.ss9` `af37457d4cd41e18`、`battle3-action61-ai-preconfirm.ss9` `6524764b33c41907`、`battle8-action64-ai-preconfirm.ss9` `c775d4b5ea952f95`；profile JSON 在逆向树 `sequel/content/battle-effect-pixel-ab/`（8 个）与 `sequel/content/battle-effect-controlled-pixel-ab/`（8 个）。

### 缺什么

1. **主树缺 23 族的本地锚（checkpoint + profile）**，`applicability` 仍是 `no-local-anchor-in-this-tree` ⇒ 这些族在主树里**只能当像素基线比对**，不能按「原输入复跑」重放。
2. `residual-wram-tilemap-pixel-ab-v1` 的 `unavailable_local_inputs` 是**空列表** —— 缺件未被登记，缺什么仍 `unknown`。
3. `motion-effect-parameter-pixel-ab-v1` 列的缺件 `sequel/content/palettes/bank.json` **本轮实测已存在于主树**（SHA-256 `683db11e4186ec145314ad4ae238c34f5b5d80fe66a5520a1cf4d77b5b6b5bf0`，8,375 B）⇒ 该条 `unavailable_local_inputs` 是**导入时的陈旧记录**，重跑导入器即可消掉。
4. `data-table-b-message0-pointer-pixel-ab-v1` 列的缺件 `tools/mgba_input_sequence_replay.lua` **本轮实测存在于逆向树**（`/Users/altair/github/gba-naruto-reverse/tools/mgba_input_sequence_replay.lua`）⇒ 属可拷贝件。

### 最便宜的下一步

1. **从逆向树只读拷贝**（逆向树为只读源，拷贝是读操作）：
   - 8 个 checkpoint → 主树 `artifacts/runtime-checkpoints/`（按上表族名对应）；
   - 16 个 profile JSON → 主树 `sequel/content/battle-effect-pixel-ab/`、`sequel/content/battle-effect-controlled-pixel-ab/`、`sequel/content/battle-effect-natural-pixel-ab/`、`sequel/content/motion-effect-parameter-pixel-ab/`（目标目录需新建）。
2. **重跑导入器并让它改判 `applicability`**：

```
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
/usr/local/bin/python3 tools/butano/import_rom_pixel_ab_baselines.py import \
  --reverse-root /Users/altair/github/gba-naruto-reverse \
  --out-dir artifacts/butano-reverse-m3-import-v1/pixel-ab
/usr/local/bin/python3 tools/butano/import_rom_pixel_ab_baselines.py verify \
  --reverse-root /Users/altair/github/gba-naruto-reverse \
  --out-dir artifacts/butano-reverse-m3-import-v1/pixel-ab
```

   产物：`artifacts/butano-reverse-m3-import-v1/pixel-ab/baselines.json`（`applicability` 应从 `no-local-anchor-in-this-tree` 变为 `local-anchor-found`）。
3. **先做零成本的部分**：8 个受控族（`group03/06/07/08/09/10/12/18-controlled`）只缺 profile JSON、不缺 checkpoint ⇒ 只拷 8 个 JSON 就能把 8 族从 23 里划掉。**这是本项最省的一刀。**
4. `residual-wram-tilemap-pixel-ab-v1`：先在逆向树 `notes/residual-wram-tilemap-pixel-ab-20260801.md` 里查它的输入清单（逆向树侧笔记存在），再决定补什么。

### 未确立

- `residual-wram-tilemap-pixel-ab-v1` 到底缺哪些输入 —— `unknown`（`unavailable_local_inputs` 为空）。
- `motion-effect-parameter-pixel-ab-v1` 的 `sequel/content/palettes/bank.json` 与逆向树版本是否**逐字节相同** —— `unknown`（本轮只核验了主树侧存在与哈希，未与逆向树侧比对）。
- 23 族里「自然场景 checkpoint」与「受控探针」是否都算「对照配方」 —— `unknown`（主树笔记未定义该词的确切判据）。

---

## 5. 汇总

| 项 | 状态 | 最便宜的下一步（一条） |
| --- | --- | --- |
| 1. 原版 step-16 预览屏 | **不是独立战前预览屏**，是 0x3110 移动选择屏的第二次出现（相机 152/40，`DISPCNT 0x1D40`）；图块/调色板主树已导出并与 VRAM/PRAM 核对，但**语义**（可达/不可达）与 step-16 的控制器态仍 `unknown` | 用 38 态库存对 `walk-original-a24/step-16-A.ss9` 跑绑定取 0x3110 内层帧；逆向侧找「生成 BG2 tilemap 的 ROM 记录」 |
| 2. 待机 31 姿态 | 「31」已被 `tools/butano/measure_s49_rule_idle_sequence.py` 钉死 = 32 帧内互不相同的**图像**数（全区域 31 / 精灵区 30），**不是** ROM 姿态数（32 帧周期最多 3 帧，`cycle_length_to_max_distinct_frames`）；逆向树自认 `runtime_slot_selection: false` | 32 帧逐帧 OAM 收据（`artifacts/s49-original-unit-oam-timeline-v1/`）＋ 匹配 `character-battle-visuals-v1` 的组件 tile 表，以解出原版的**帧序** |
| 3. 12 个 unknown 态 | **0x0010、0x1220 条件②已由现成主树存档满足**（本轮新算）；其余 10 态缺 checkpoint，其中 0x3100/0x8010/0xA000 被动 checkpoint 结构上落不进来 | 重建 38 态库存 → 修 4 条失效 observation → 改 1 条旧标签 → 加 3 条新 observation → 跑 `tools/analyze_battle_controller_checkpoints.py` |
| 4. 23 个 pixel-A/B 族 | 「23」= `baselines.json` 里 `applicability == "no-local-anchor-in-this-tree"` 的条数；缺件清单已逐条列全，且**全部存在于逆向树** | 先只拷 8 个受控族的 profile JSON（零 checkpoint 成本），再重跑 `import_rom_pixel_ab_baselines.py` |

**本轮新增的确证（此前无记录）**

- 0x0010 与 0x1220 已有哈希绑定的 38 态 checkpoint（`walk-original-a24/step-09-A.ss9` sha `e193b414…`；`walk-original-a24/step-15-A.ss9` sha `131b4265…`；`original-dialogue/step-15-A.ss9` sha `c362b265…`）。
- 12 个区间的**可达 frame PC** 全表（可判定的闭合条件）。
- 现有 18 条 observation 中有 4 条指向已删除的 `build/` 存档（分析器失败关闭）。
- 「31」= 30–31 幅互不相同的**精灵图**（逐像素复算），且变化覆盖整个精灵而非小标记。
- 逆向树 field slot 的静态结构：56/62 角色为「4 keyframe × hold 8 = 32 帧、3 姿态」。
