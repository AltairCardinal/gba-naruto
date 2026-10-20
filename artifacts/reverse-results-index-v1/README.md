# 逆向成果索引（自动生成）

本文件由 `tools/build_reverse_results_index.py` 生成，不要手工编辑；手工维护的是 `docs/reverse-results-index/ledger.json`。

- 索引 schema：`konoha.reverse-results-index.v1`
- 逆向工作树：`/Users/altair/github/gba-naruto-reverse`
- 逆向 commit：`f054f4c1e240c87583f1059b64eb1fc199aada07`
- 逆向工作树是否有未提交改动：False
- 条目总数：2204

## 分类统计

| 分类 | 条目数 |
| --- | --- |
| audio | 5 |
| battle | 13 |
| code | 1440 |
| map | 33 |
| other | 240 |
| overview | 3 |
| presentation | 29 |
| residual | 23 |
| rom | 252 |
| runtime | 13 |
| scenario | 23 |
| visual | 130 |

## 复刻台账（本次重建用到的东西从哪来）

| 项 | 类别 | 状态 | 来源 | 审计 |
| --- | --- | --- | --- | --- |
| S49 战场底图（map 14，30×19 格，480×304） | map | reused | `artifacts/map-canvases-v1/canvases/map-14-primary.png` | source found |
| S49 战斗入口存档（原版录制的起点） | runtime | reused | `artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9` | source found |
| 命令菜单字形（移動/木・忍具/查克拉/休息/行動結束） | presentation | reconstructed | `artifacts/s49-original-ui-reference-v1/screens/command-menu-0.png` | source found |
| 动作菜单字形（瞬身术/影分身术/忍者组合拳/十字手里剑） | presentation | reconstructed | `artifacts/s49-ledger-evidence-v1/action-menu-glyphs.json` | source found |
| 回合横幅面板与两行文字（回合 1 / 玩家 的行动） | presentation | reconstructed | `artifacts/s49-original-ui-reference-v1/screens/turn-banner-0.png` | source found |
| 非行动单位灰阶调色板（OBJ PRAM bank 3，16 项） | visual | reconstructed | `artifacts/s49-original-gpu-20261020-v2/dimmed-palette-receipt.json` | source found |
| 「SELECT詳細」提示语（详细两字） | presentation | reconstructed | `artifacts/s49-ledger-evidence-v1/select-prompt.json` | source found |
| 移动范围网格的染色规则（可达/消耗/不可达） | battle | reconstructed | `artifacts/s49-ledger-evidence-v1/move-grid-colors.json` | source found |
| AI 纯移动之后的朝向规则 | battle | reconstructed | `notes/s49-fidelity-handover-20261019.md` | source found |
| 镜头偏移 (240,24) 与场景格→地图格 +10 列 | map | derived | `artifacts/map-canvases-v1/manifest.json` | source found |
| 单位待机动画的帧序与相位 | visual | reconstructed | `artifacts/s49-ledger-evidence-v1/idle-sequence.json` | source found |
| 状态栏「結束 / 待機」的状态切换时机 | battle | reconstructed | `artifacts/s49-ledger-evidence-v1/standby-state.json` | source found |
| 逆向成果族判定：ROM 启动期 ARM/Thumb 互操作闭包 | rom | not-applicable | `artifacts/rom-boot-interwork-continuation-v1/manifest.json` | source found |
| 逆向成果族判定：全 ROM 控制流图根种子集 | rom | not-applicable | `artifacts/rom-cfg-seeds-v1/manifest.json` | source found |
| 逆向成果族判定：章节脚本未绑定尾巴（slot 45/46） | rom | not-applicable | `artifacts/rom-chapter-script-unbound-tail-v1/manifest.json` | source found |
| 逆向成果族判定：2026-09-01 字节覆盖基线的四包重放输入 | rom | not-applicable | `artifacts/rom-fast-audit-four-packet-baseline-v1/manifest.json` | source found |
| 逆向成果族判定：精灵组件源（12 个组件表 + 4 条动画时间线） | rom | not-applicable | `artifacts/rom-sprite-component-source-v1/manifest.json` | source found |
| 单位视觉表里的损坏终止符 0xFBFF | visual | reconstructed | `artifacts/s49-ledger-evidence-v1/action-menu-glyphs.json` | source found |
| S49（battle 14）的九槽名册：角色、坐标、等级、体力与携带经验 | battle | reused | `artifacts/character-runtime-unit-oam-bindings-v1/bindings.json` | source found |
| S49 战后的等级/经验结算（阈值表、成长表、按人分配的经验） | battle | reused | `notes/s49-post-battle-exp-rule-20261020.md` | source found |
| S49 移动网格覆盖层：BG2 层 + ROM 的两份 LZ77 资源（图块/调色板） | battle | reused | `notes/s49-dispcnt-bit10-layer-20261020.md` | source found |
| 被选中单位的 visual slot/帧：两侧都是 slot 0，差在 idle 相位一步（8 帧）——**常量偏移方案已被实测推翻** | visual | reused | `notes/s49-selected-unit-slot-frame-20261020.md` | source found |
| 移动网格覆盖层的 ROM 资源：32 个 4bpp 图块 + 调色板 bank 12（已导出并与同帧 VRAM/PRAM 逐字节对账） | visual | derived | `notes/s49-movegrid-overlay-assets-20261020.md` | source found |
| 覆盖层 BG2 tilemap 的实际内容：212 格 = 53 个 16×16 像素格，屏幕上是菱形/透镜 | visual | derived | `notes/s49-movegrid-overlay-tilemap-20261020.md` | source found |
| P2：10 条逆向笔记从 needs_guard 转成行为门禁（含 10 条显式拒绝） | other | reused | `notes/s49-needs-guard-gates-20261020.md` | source found |
| 原版 idle 相位可测量化：渲染帧 → 导出帧号的精确反查 + 跨录像的游戏内时刻配对 | visual | reused | `notes/s49-selected-unit-idle-phase-20261020.md` | source found |
| 原版「每帧重绘」的机制：不是新帧，是单位 OBJ 调色板 index 15 被逐帧改写（32 帧三角波） | visual | reused | `notes/s49-field-frame-order-20261020.md` | source found |
| 覆盖层 4bpp 图块 + bank 12 调色板已入库重制侧资产管线（Butano 图形工具实测处理成功） | visual | reused | `notes/s49-movegrid-overlay-asset-import-20261020.md` | source found |
| 覆盖层重制侧实施规格：接线已存在（专属 BG 层），缺图块/粒度/混合/规则四样 | visual | derived | `notes/s49-movegrid-overlay-implementation-spec-20261020.md` | source found |
| 原版战后状态页（人物信息页）已录到并核验：三人 EXP/体力/查克拉 与逆向树记录逐项吻合 | visual | reused | `notes/s49-original-victory-20261020.md` | source found |
| 覆盖层选块规则闭合：高亮族只取决于「列奇偶」（0 冲突）；常驻网格族仍未闭合 | visual | derived | `notes/s49-movegrid-overlay-rule-20261020.md` | source found |
| 原版覆盖层**确实在做 alpha 混合**（BLDCNT=0x1744、EVA=EVB=15/16）——旧读数来自 IO 偏移错误 | visual | reused | `notes/s49-movegrid-blend-correction-20261021.md` | source found |
| 同帧收据**完全自洽**：从 dump 重建 = PNG 38,400/38,400 逐像素一致（推翻「PNG 与 dump 不自洽」） | other | reused | `docs/konoha-senki/01-battle-s49.md` | source found |
| 覆盖层「只换原版高亮图块」被实测否证：缺的是族 0 的常驻网格网（已回滚） | visual | reused | `notes/s49-movegrid-overlay-swap-experiment-20261021.md` | source found |
| 原版覆盖层 = 每张地图烘焙好的一张静态布局图（BG2 tilemap，16 种签名，212 格会变） | visual | reused | `notes/s49-battlefield-overlay-baked-20261021.md` | source found |

台账无问题：每条都给出了状态与可核验的来源指针，没有条目留在 `missing`。

## 成果条目

### audio（5）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `audio` | artifact | `artifacts/audio` | — | 0 | 0 |
| `audio-cue-semantics-20260713` | note | `notes/audio-cue-semantics-20260713.md` | — | 0 | 0 |
| `audio-engine-runtime-chain-20260712` | note | `notes/audio-engine-runtime-chain-20260712.md` | — | 0 | 0 |
| `audio-palette-identity-correction-20260711` | note | `notes/audio-palette-identity-correction-20260711.md` | — | 0 | 0 |
| `audio-tie-lifecycle-20260713` | note | `notes/audio-tie-lifecycle-20260713.md` | — | 0 | 0 |

### battle（13）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `battle-encounters-story-visual-pixel-ab-v1` | artifact | `artifacts/battle-encounters-story-visual-pixel-ab-v1` | files, implementation, verifier | 0 | 0 |
| `battle-presentation-glyphs-v1` | artifact | `artifacts/battle-presentation-glyphs-v1` | atlas, consumer, rom, runtime_palette, scope, summary, tables | 0 | 7 |
| `battle-status-bars-v1` | artifact | `artifacts/battle-status-bars-v1` | files, producer, source, verifier | 0 | 0 |
| `battle-action-detail-renderer-20260713` | note | `notes/battle-action-detail-renderer-20260713.md` | — | 0 | 0 |
| `battle-config-format` | note | `notes/battle-config-format.md` | — | 0 | 0 |
| `battle-config-unsafe-template-fix-20260710` | note | `notes/battle-config-unsafe-template-fix-20260710.md` | — | 0 | 0 |
| `battle-encounters-story-visual-player-visible-20260809` | note | `notes/battle-encounters-story-visual-player-visible-20260809.md` | — | 0 | 0 |
| `battle-presentation-glyphs-export-20260729` | note | `notes/battle-presentation-glyphs-export-20260729.md` | — | 0 | 0 |
| `battle-scenario-config` | note | `notes/battle-scenario-config.md` | — | 0 | 0 |
| `battle-start-control-flow-20260713` | note | `notes/battle-start-control-flow-20260713.md` | — | 0 | 0 |
| `battle-status-bars-export-20260730` | note | `notes/battle-status-bars-export-20260730.md` | — | 0 | 0 |
| `battle-system-restoration-evidence-20260723` | note | `notes/battle-system-restoration-evidence-20260723.md` | — | 0 | 0 |
| `battlefield-object-effect-chain-20260802` | note | `notes/battlefield-object-effect-chain-20260802.md` | — | 0 | 0 |

### code（1440）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `__init__` | tool | `tools/_vendor/capstone/__init__.py` | — | 0 | 0 |
| `arm` | tool | `tools/_vendor/capstone/arm.py` | — | 0 | 0 |
| `arm64` | tool | `tools/_vendor/capstone/arm64.py` | — | 0 | 0 |
| `arm64_const` | tool | `tools/_vendor/capstone/arm64_const.py` | — | 0 | 0 |
| `arm_const` | tool | `tools/_vendor/capstone/arm_const.py` | — | 0 | 0 |
| `bpf` | tool | `tools/_vendor/capstone/bpf.py` | — | 0 | 0 |
| `bpf_const` | tool | `tools/_vendor/capstone/bpf_const.py` | — | 0 | 0 |
| `evm` | tool | `tools/_vendor/capstone/evm.py` | — | 0 | 0 |
| `evm_const` | tool | `tools/_vendor/capstone/evm_const.py` | — | 0 | 0 |
| `m680x` | tool | `tools/_vendor/capstone/m680x.py` | — | 0 | 0 |
| `m680x_const` | tool | `tools/_vendor/capstone/m680x_const.py` | — | 0 | 0 |
| `m68k` | tool | `tools/_vendor/capstone/m68k.py` | — | 0 | 0 |
| `m68k_const` | tool | `tools/_vendor/capstone/m68k_const.py` | — | 0 | 0 |
| `mips` | tool | `tools/_vendor/capstone/mips.py` | — | 0 | 0 |
| `mips_const` | tool | `tools/_vendor/capstone/mips_const.py` | — | 0 | 0 |
| `mos65xx` | tool | `tools/_vendor/capstone/mos65xx.py` | — | 0 | 0 |
| `mos65xx_const` | tool | `tools/_vendor/capstone/mos65xx_const.py` | — | 0 | 0 |
| `ppc` | tool | `tools/_vendor/capstone/ppc.py` | — | 0 | 0 |
| `ppc_const` | tool | `tools/_vendor/capstone/ppc_const.py` | — | 0 | 0 |
| `riscv` | tool | `tools/_vendor/capstone/riscv.py` | — | 0 | 0 |
| `riscv_const` | tool | `tools/_vendor/capstone/riscv_const.py` | — | 0 | 0 |
| `sh` | tool | `tools/_vendor/capstone/sh.py` | — | 0 | 0 |
| `sh_const` | tool | `tools/_vendor/capstone/sh_const.py` | — | 0 | 0 |
| `sparc` | tool | `tools/_vendor/capstone/sparc.py` | — | 0 | 0 |
| `sparc_const` | tool | `tools/_vendor/capstone/sparc_const.py` | — | 0 | 0 |
| `systemz` | tool | `tools/_vendor/capstone/systemz.py` | — | 0 | 0 |
| `sysz_const` | tool | `tools/_vendor/capstone/sysz_const.py` | — | 0 | 0 |
| `tms320c64x` | tool | `tools/_vendor/capstone/tms320c64x.py` | — | 0 | 0 |
| `tms320c64x_const` | tool | `tools/_vendor/capstone/tms320c64x_const.py` | — | 0 | 0 |
| `tricore` | tool | `tools/_vendor/capstone/tricore.py` | — | 0 | 0 |
| `tricore_const` | tool | `tools/_vendor/capstone/tricore_const.py` | — | 0 | 0 |
| `wasm` | tool | `tools/_vendor/capstone/wasm.py` | — | 0 | 0 |
| `wasm_const` | tool | `tools/_vendor/capstone/wasm_const.py` | — | 0 | 0 |
| `x86` | tool | `tools/_vendor/capstone/x86.py` | — | 0 | 0 |
| `x86_const` | tool | `tools/_vendor/capstone/x86_const.py` | — | 0 | 0 |
| `xcore` | tool | `tools/_vendor/capstone/xcore.py` | — | 0 | 0 |
| `xcore_const` | tool | `tools/_vendor/capstone/xcore_const.py` | — | 0 | 0 |
| `accept_prebattle_candidate` | tool | `tools/accept_prebattle_candidate.py` | — | 0 | 0 |
| `analyze_battle_action_template_semantics` | tool | `tools/analyze_battle_action_template_semantics.py` | — | 0 | 0 |
| `analyze_battle_action_transactions` | tool | `tools/analyze_battle_action_transactions.py` | — | 0 | 0 |
| `analyze_battle_ai_status_policy` | tool | `tools/analyze_battle_ai_status_policy.py` | — | 0 | 0 |
| `analyze_battle_ai_utility_policy` | tool | `tools/analyze_battle_ai_utility_policy.py` | — | 0 | 0 |
| `analyze_battle_condition_interpreter` | tool | `tools/analyze_battle_condition_interpreter.py` | — | 0 | 0 |
| `analyze_battle_controller_checkpoints` | tool | `tools/analyze_battle_controller_checkpoints.py` | — | 0 | 0 |
| `analyze_battle_damage_hit_formula` | tool | `tools/analyze_battle_damage_hit_formula.py` | — | 0 | 0 |
| `analyze_battle_defense_preparation` | tool | `tools/analyze_battle_defense_preparation.py` | — | 0 | 0 |
| `analyze_battle_defense_reaction` | tool | `tools/analyze_battle_defense_reaction.py` | — | 0 | 0 |
| `analyze_battle_effect_formation_routes` | tool | `tools/analyze_battle_effect_formation_routes.py` | — | 0 | 0 |
| `analyze_battle_effect_hardcoded_selector_producers` | tool | `tools/analyze_battle_effect_hardcoded_selector_producers.py` | — | 0 | 0 |
| `analyze_battle_effect_resolution` | tool | `tools/analyze_battle_effect_resolution.py` | — | 0 | 0 |
| `analyze_battle_hit_modifiers` | tool | `tools/analyze_battle_hit_modifiers.py` | — | 0 | 0 |
| `analyze_battle_objective_transitions` | tool | `tools/analyze_battle_objective_transitions.py` | — | 0 | 0 |
| `analyze_battle_reaction_matrix` | tool | `tools/analyze_battle_reaction_matrix.py` | — | 0 | 0 |
| `analyze_battle_reaction_priority` | tool | `tools/analyze_battle_reaction_priority.py` | — | 0 | 0 |
| `analyze_battle_resource_transactions` | tool | `tools/analyze_battle_resource_transactions.py` | — | 0 | 0 |
| `analyze_battle_status_attribute_modifiers` | tool | `tools/analyze_battle_status_attribute_modifiers.py` | — | 0 | 0 |
| `analyze_battle_status_consumers` | tool | `tools/analyze_battle_status_consumers.py` | — | 0 | 0 |
| `analyze_battle_status_expiry` | tool | `tools/analyze_battle_status_expiry.py` | — | 0 | 0 |
| `analyze_battle_status_hit_count_modifier` | tool | `tools/analyze_battle_status_hit_count_modifier.py` | — | 0 | 0 |
| `analyze_battle_status_linked_resolution` | tool | `tools/analyze_battle_status_linked_resolution.py` | — | 0 | 0 |
| `analyze_battle_status_participant_consumption` | tool | `tools/analyze_battle_status_participant_consumption.py` | — | 0 | 0 |
| `analyze_battle_status_stage_policy` | tool | `tools/analyze_battle_status_stage_policy.py` | — | 0 | 0 |
| `analyze_battle_status_storage` | tool | `tools/analyze_battle_status_storage.py` | — | 0 | 0 |
| `analyze_battle_status_transformation` | tool | `tools/analyze_battle_status_transformation.py` | — | 0 | 0 |
| `analyze_battle_unit_eligibility` | tool | `tools/analyze_battle_unit_eligibility.py` | — | 0 | 0 |
| `analyze_battle_unit_selection` | tool | `tools/analyze_battle_unit_selection.py` | — | 0 | 0 |
| `analyze_battlefield_object_effect_chain` | tool | `tools/analyze_battlefield_object_effect_chain.py` | — | 0 | 0 |
| `analyze_battlefield_object_producers` | tool | `tools/analyze_battlefield_object_producers.py` | — | 0 | 0 |
| `analyze_dialogue_render` | tool | `tools/analyze_dialogue_render.py` | — | 0 | 0 |
| `analyze_mgba_zero_input_cycle` | tool | `tools/analyze_mgba_zero_input_cycle.py` | — | 0 | 0 |
| `analyze_reverse_engineering_gaps` | tool | `tools/analyze_reverse_engineering_gaps.py` | — | 0 | 0 |
| `analyze_rom_ai_entry_domains` | tool | `tools/analyze_rom_ai_entry_domains.py` | — | 0 | 0 |
| `analyze_rom_renderer_excluded_roots` | tool | `tools/analyze_rom_renderer_excluded_roots.py` | — | 0 | 0 |
| `analyze_rom_renderer_handler_graphs` | tool | `tools/analyze_rom_renderer_handler_graphs.py` | — | 0 | 0 |
| `analyze_rom_unknown_clusters` | tool | `tools/analyze_rom_unknown_clusters.py` | — | 0 | 0 |
| `analyze_table` | tool | `tools/analyze_table.py` | — | 0 | 0 |
| `analyze_tile_table` | tool | `tools/analyze_tile_table.py` | — | 0 | 0 |
| `audit_battle_effect_fixed_roundtrip` | tool | `tools/audit_battle_effect_fixed_roundtrip.py` | — | 0 | 0 |
| `audit_map_resource_fixed_roundtrip` | tool | `tools/audit_map_resource_fixed_roundtrip.py` | — | 0 | 0 |
| `audit_map_resource_relocation_roundtrip` | tool | `tools/audit_map_resource_relocation_roundtrip.py` | — | 0 | 0 |
| `audit_re_completion` | tool | `tools/audit_re_completion.py` | — | 0 | 0 |
| `audit_reverse_engineering_proof` | tool | `tools/audit_reverse_engineering_proof.py` | — | 0 | 0 |
| `audit_rom_byte_coverage` | tool | `tools/audit_rom_byte_coverage.py` | — | 0 | 0 |
| `automated_test` | tool | `tools/automated_test.py` | — | 0 | 0 |
| `batch_test_dispatcher_triggers` | tool | `tools/batch_test_dispatcher_triggers.py` | — | 0 | 0 |
| `build_action_submit_runtime_probe` | tool | `tools/build_action_submit_runtime_probe.py` | — | 0 | 0 |
| `build_adjacent_tutorial_runtime_probe` | tool | `tools/build_adjacent_tutorial_runtime_probe.py` | — | 0 | 0 |
| `build_alternate_chapter_runtime_probe` | tool | `tools/build_alternate_chapter_runtime_probe.py` | — | 0 | 0 |
| `build_audio_runtime_probe` | tool | `tools/build_audio_runtime_probe.py` | — | 0 | 0 |
| `build_battle_catalog_runtime_probe` | tool | `tools/build_battle_catalog_runtime_probe.py` | — | 0 | 0 |
| `build_battle_effect_group5_pixel_ab` | tool | `tools/build_battle_effect_group5_pixel_ab.py` | — | 0 | 0 |
| `build_battle_effect_pixel_ab` | tool | `tools/build_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `build_battle_effect_runtime_probe` | tool | `tools/build_battle_effect_runtime_probe.py` | — | 0 | 0 |
| `build_battle_encounters_story_visual_pixel_ab` | tool | `tools/build_battle_encounters_story_visual_pixel_ab.py` | — | 0 | 0 |
| `build_battle_message_runtime_probe` | tool | `tools/build_battle_message_runtime_probe.py` | — | 0 | 0 |
| `build_battle_message_runtime_probe_slots` | tool | `tools/build_battle_message_runtime_probe_slots.py` | — | 0 | 0 |
| `build_battle_start_runtime_probe` | tool | `tools/build_battle_start_runtime_probe.py` | — | 0 | 0 |
| `build_chapter_battle_route_probe` | tool | `tools/build_chapter_battle_route_probe.py` | — | 0 | 0 |
| `build_chapter_script_probe` | tool | `tools/build_chapter_script_probe.py` | — | 0 | 0 |
| `build_chapter_semantic_probe` | tool | `tools/build_chapter_semantic_probe.py` | — | 0 | 0 |
| `build_character_battle_graphics_pixel_ab` | tool | `tools/build_character_battle_graphics_pixel_ab.py` | — | 0 | 0 |
| `build_character_battle_visual_resource_matrix` | tool | `tools/build_character_battle_visual_resource_matrix.py` | — | 0 | 0 |
| `build_character_fbff_control_rom` | tool | `tools/build_character_fbff_control_rom.py` | — | 0 | 0 |
| `build_character_growth_probe` | tool | `tools/build_character_growth_probe.py` | — | 0 | 0 |
| `build_controlled_audio_runtime_probe` | tool | `tools/build_controlled_audio_runtime_probe.py` | — | 0 | 0 |
| `build_controlled_battle_effect_allocator_reset_probe` | tool | `tools/build_controlled_battle_effect_allocator_reset_probe.py` | — | 0 | 0 |
| `build_controlled_battle_effect_direct_spawn_probe` | tool | `tools/build_controlled_battle_effect_direct_spawn_probe.py` | — | 0 | 0 |
| `build_controlled_battle_effect_pixel_ab` | tool | `tools/build_controlled_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `build_controlled_battle_effect_sequence_probe` | tool | `tools/build_controlled_battle_effect_sequence_probe.py` | — | 0 | 0 |
| `build_controller_path_runtime_probe` | tool | `tools/build_controller_path_runtime_probe.py` | — | 0 | 0 |
| `build_cross_player_cgb_probe` | tool | `tools/build_cross_player_cgb_probe.py` | — | 0 | 0 |
| `build_cutscene_obj_id1_pixel_ab` | tool | `tools/build_cutscene_obj_id1_pixel_ab.py` | — | 0 | 0 |
| `build_cutscene_obj_primary_ptr_ab` | tool | `tools/build_cutscene_obj_primary_ptr_ab.py` | — | 0 | 0 |
| `build_cutscene_obj_secondary_ptr_ab` | tool | `tools/build_cutscene_obj_secondary_ptr_ab.py` | — | 0 | 0 |
| `build_db_patches` | tool | `tools/build_db_patches.py` | — | 0 | 0 |
| `build_delayed_audio_retrigger_probe` | tool | `tools/build_delayed_audio_retrigger_probe.py` | — | 0 | 0 |
| `build_forced_save_case_probe` | tool | `tools/build_forced_save_case_probe.py` | — | 0 | 0 |
| `build_function_pointer_runtime_probe` | tool | `tools/build_function_pointer_runtime_probe.py` | — | 0 | 0 |
| `build_levels_runtime_probe` | tool | `tools/build_levels_runtime_probe.py` | — | 0 | 0 |
| `build_macos_mgba` | tool | `tools/build_macos_mgba.py` | — | 0 | 0 |
| `build_map41_primary_layout_pixel_ab` | tool | `tools/build_map41_primary_layout_pixel_ab.py` | — | 0 | 0 |
| `build_map41_visual_resource_matrix` | tool | `tools/build_map41_visual_resource_matrix.py` | — | 0 | 0 |
| `build_map_events_e4_handler_pixel_ab` | tool | `tools/build_map_events_e4_handler_pixel_ab.py` | — | 0 | 0 |
| `build_map_sprites_definition_pixel_ab` | tool | `tools/build_map_sprites_definition_pixel_ab.py` | — | 0 | 0 |
| `build_menu_portrait_pixel_ab` | tool | `tools/build_menu_portrait_pixel_ab.py` | — | 0 | 0 |
| `build_menu_portrait_pointer_ab` | tool | `tools/build_menu_portrait_pointer_ab.py` | — | 0 | 0 |
| `build_mod` | tool | `tools/build_mod.py` | — | 0 | 0 |
| `build_motion_effect_parameter_pixel_ab` | tool | `tools/build_motion_effect_parameter_pixel_ab.py` | — | 0 | 0 |
| `build_natural_delayed_battle_effect_pixel_ab` | tool | `tools/build_natural_delayed_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `build_natural_load_runtime_probe` | tool | `tools/build_natural_load_runtime_probe.py` | — | 0 | 0 |
| `build_natural_save_runtime_probe` | tool | `tools/build_natural_save_runtime_probe.py` | — | 0 | 0 |
| `build_numeric_writer_trace_probe` | tool | `tools/build_numeric_writer_trace_probe.py` | — | 0 | 0 |
| `build_player_control_runtime_probe` | tool | `tools/build_player_control_runtime_probe.py` | — | 0 | 0 |
| `build_postbattle_natural_save_probe` | tool | `tools/build_postbattle_natural_save_probe.py` | — | 0 | 0 |
| `build_postbattle_save_probe` | tool | `tools/build_postbattle_save_probe.py` | — | 0 | 0 |
| `build_profile_text_runtime_probe` | tool | `tools/build_profile_text_runtime_probe.py` | — | 0 | 0 |
| `build_relocated_chapter_runtime_probe` | tool | `tools/build_relocated_chapter_runtime_probe.py` | — | 0 | 0 |
| `build_residual_wram_tilemap_pixel_ab` | tool | `tools/build_residual_wram_tilemap_pixel_ab.py` | — | 0 | 0 |
| `build_resource_pointer_runtime_probe` | tool | `tools/build_resource_pointer_runtime_probe.py` | — | 0 | 0 |
| `build_rom_expansion_probe` | tool | `tools/build_rom_expansion_probe.py` | — | 0 | 0 |
| `build_sappy_engine_master_enable_ab` | tool | `tools/build_sappy_engine_master_enable_ab.py` | — | 0 | 0 |
| `build_save_group_runtime_probe` | tool | `tools/build_save_group_runtime_probe.py` | — | 0 | 0 |
| `build_save_state_runtime_probe` | tool | `tools/build_save_state_runtime_probe.py` | — | 0 | 0 |
| `build_skill_detail_runtime_probe` | tool | `tools/build_skill_detail_runtime_probe.py` | — | 0 | 0 |
| `build_skill_relation_runtime_probe` | tool | `tools/build_skill_relation_runtime_probe.py` | — | 0 | 0 |
| `build_skill_runtime_probe` | tool | `tools/build_skill_runtime_probe.py` | — | 0 | 0 |
| `build_text_writer_trace_probe` | tool | `tools/build_text_writer_trace_probe.py` | — | 0 | 0 |
| `build_tile_asset_descriptor_pixel_ab` | tool | `tools/build_tile_asset_descriptor_pixel_ab.py` | — | 0 | 0 |
| `build_tilemap_writer_trace_probe` | tool | `tools/build_tilemap_writer_trace_probe.py` | — | 0 | 0 |
| `build_training_levels_runtime_probe` | tool | `tools/build_training_levels_runtime_probe.py` | — | 0 | 0 |
| `build_world_map_page0_pixel_ab` | tool | `tools/build_world_map_page0_pixel_ab.py` | — | 0 | 0 |
| `analyze_scenario_41_gpu` | tool | `tools/butano/analyze_scenario_41_gpu.py` | — | 0 | 0 |
| `benchmark_clock` | tool | `tools/butano/benchmark_clock.py` | — | 0 | 0 |
| `export_scenario_41_attack_animation` | tool | `tools/butano/export_scenario_41_attack_animation.py` | — | 0 | 0 |
| `export_scenario_41_attack_gpu_bases` | tool | `tools/butano/export_scenario_41_attack_gpu_bases.py` | — | 0 | 0 |
| `export_scenario_41_combat_reference` | tool | `tools/butano/export_scenario_41_combat_reference.py` | — | 0 | 0 |
| `export_scenario_41_extended_reference` | tool | `tools/butano/export_scenario_41_extended_reference.py` | — | 0 | 0 |
| `export_scenario_41_prebattle_reference` | tool | `tools/butano/export_scenario_41_prebattle_reference.py` | — | 0 | 0 |
| `export_scenario_41_reference` | tool | `tools/butano/export_scenario_41_reference.py` | — | 0 | 0 |
| `generate_scenario_41_assets` | tool | `tools/butano/generate_scenario_41_assets.py` | — | 0 | 0 |
| `generate_scenario_41_attack_animation_assets` | tool | `tools/butano/generate_scenario_41_attack_animation_assets.py` | — | 0 | 0 |
| `generate_scenario_41_audio_assets` | tool | `tools/butano/generate_scenario_41_audio_assets.py` | — | 0 | 0 |
| `generate_scenario_41_prebattle_assets` | tool | `tools/butano/generate_scenario_41_prebattle_assets.py` | — | 0 | 0 |
| `generate_scenario_41_sfx_assets` | tool | `tools/butano/generate_scenario_41_sfx_assets.py` | — | 0 | 0 |
| `render_scenario_41_gpu` | tool | `tools/butano/render_scenario_41_gpu.py` | — | 0 | 0 |
| `run_cpp_benchmark_tests` | tool | `tools/butano/run_cpp_benchmark_tests.py` | — | 0 | 0 |
| `verify_scenario_41_audio_states` | tool | `tools/butano/verify_scenario_41_audio_states.py` | — | 0 | 0 |
| `verify_setup` | tool | `tools/butano/verify_setup.py` | — | 0 | 0 |
| `chapter_script_analyzer` | tool | `tools/chapter_script_analyzer.py` | — | 0 | 0 |
| `chapter_script_codec` | tool | `tools/chapter_script_codec.py` | — | 0 | 0 |
| `check_comet_project_policy` | tool | `tools/check_comet_project_policy.py` | — | 0 | 0 |
| `check_staged_artifact_policy` | tool | `tools/check_staged_artifact_policy.py` | — | 0 | 0 |
| `compare_mgba_audio_capture` | tool | `tools/compare_mgba_audio_capture.py` | — | 0 | 0 |
| `compare_mgba_cgb_capture` | tool | `tools/compare_mgba_cgb_capture.py` | — | 0 | 0 |
| `compare_mgba_cross_player_cgb_capture` | tool | `tools/compare_mgba_cross_player_cgb_capture.py` | — | 0 | 0 |
| `compare_mgba_linked_audio_capture` | tool | `tools/compare_mgba_linked_audio_capture.py` | — | 0 | 0 |
| `compare_mgba_retrigger_capture` | tool | `tools/compare_mgba_retrigger_capture.py` | — | 0 | 0 |
| `compare_wram_regions` | tool | `tools/compare_wram_regions.py` | — | 0 | 0 |
| `decode_controller_path_runtime_probe` | tool | `tools/decode_controller_path_runtime_probe.py` | — | 0 | 0 |
| `decode_dialogue_record` | tool | `tools/decode_dialogue_record.py` | — | 0 | 0 |
| `decode_m4a_tracks` | tool | `tools/decode_m4a_tracks.py` | — | 0 | 0 |
| `diff_memory_regions` | tool | `tools/diff_memory_regions.py` | — | 0 | 0 |
| `disasm_thumb` | tool | `tools/disasm_thumb.py` | — | 0 | 0 |
| `disassemble_battle_effect_dispatchers` | tool | `tools/disassemble_battle_effect_dispatchers.py` | — | 0 | 0 |
| `experiment_workspace` | tool | `tools/experiment_workspace.py` | — | 0 | 0 |
| `export_battle_effect_affine_runtime` | tool | `tools/export_battle_effect_affine_runtime.py` | — | 0 | 0 |
| `export_battle_effect_controlled_runtime` | tool | `tools/export_battle_effect_controlled_runtime.py` | — | 0 | 0 |
| `export_battle_effect_direct_spawn_runtime` | tool | `tools/export_battle_effect_direct_spawn_runtime.py` | — | 0 | 0 |
| `export_battle_effect_frame_phase` | tool | `tools/export_battle_effect_frame_phase.py` | — | 0 | 0 |
| `export_battle_effect_group15_allocator_side_runtime` | tool | `tools/export_battle_effect_group15_allocator_side_runtime.py` | — | 0 | 0 |
| `export_battle_effect_group15_natural_runtime` | tool | `tools/export_battle_effect_group15_natural_runtime.py` | — | 0 | 0 |
| `export_battle_effect_group5_pixel_ab_evidence` | tool | `tools/export_battle_effect_group5_pixel_ab_evidence.py` | — | 0 | 0 |
| `export_battle_effect_observed_frame_phases` | tool | `tools/export_battle_effect_observed_frame_phases.py` | — | 0 | 0 |
| `export_battle_effect_pixel_ab_evidence` | tool | `tools/export_battle_effect_pixel_ab_evidence.py` | — | 0 | 0 |
| `export_battle_effect_resource_pairs` | tool | `tools/export_battle_effect_resource_pairs.py` | — | 0 | 0 |
| `export_battle_effect_resource_relocation_audit` | tool | `tools/export_battle_effect_resource_relocation_audit.py` | — | 0 | 0 |
| `export_battle_effect_resource_writeback_audit` | tool | `tools/export_battle_effect_resource_writeback_audit.py` | — | 0 | 0 |
| `export_battle_effect_runtime_oam_bindings` | tool | `tools/export_battle_effect_runtime_oam_bindings.py` | — | 0 | 0 |
| `export_battle_effect_runtime_oam_task_bindings` | tool | `tools/export_battle_effect_runtime_oam_task_bindings.py` | — | 0 | 0 |
| `export_battle_effect_sequence_bindings` | tool | `tools/export_battle_effect_sequence_bindings.py` | — | 0 | 0 |
| `export_battle_effect_sprite_animations` | tool | `tools/export_battle_effect_sprite_animations.py` | — | 0 | 0 |
| `export_battle_encounters_story_visual_pixel_ab` | tool | `tools/export_battle_encounters_story_visual_pixel_ab.py` | — | 0 | 0 |
| `export_battle_presentation_glyphs` | tool | `tools/export_battle_presentation_glyphs.py` | — | 0 | 0 |
| `export_battle_status_bars` | tool | `tools/export_battle_status_bars.py` | — | 0 | 0 |
| `export_battle_visual_catalog` | tool | `tools/export_battle_visual_catalog.py` | — | 0 | 0 |
| `export_battle_visual_runtime_timelines` | tool | `tools/export_battle_visual_runtime_timelines.py` | — | 0 | 0 |
| `export_bg_resource_canvases` | tool | `tools/export_bg_resource_canvases.py` | — | 0 | 0 |
| `export_bg_resource_relocation_audit` | tool | `tools/export_bg_resource_relocation_audit.py` | — | 0 | 0 |
| `export_bg_resource_writeback_audit` | tool | `tools/export_bg_resource_writeback_audit.py` | — | 0 | 0 |
| `export_bg_scene_selection` | tool | `tools/export_bg_scene_selection.py` | — | 0 | 0 |
| `export_character_battle_bundle_relocation_audit` | tool | `tools/export_character_battle_bundle_relocation_audit.py` | — | 0 | 0 |
| `export_character_battle_graphics_pixel_ab_evidence` | tool | `tools/export_character_battle_graphics_pixel_ab_evidence.py` | — | 0 | 0 |
| `export_character_battle_graphics_writeback_audit` | tool | `tools/export_character_battle_graphics_writeback_audit.py` | — | 0 | 0 |
| `export_character_battle_palette_writeback_audit` | tool | `tools/export_character_battle_palette_writeback_audit.py` | — | 0 | 0 |
| `export_character_battle_structure_writeback_audit` | tool | `tools/export_character_battle_structure_writeback_audit.py` | — | 0 | 0 |
| `export_character_battle_visual_resource_matrix_evidence` | tool | `tools/export_character_battle_visual_resource_matrix_evidence.py` | — | 0 | 0 |
| `export_character_battle_visuals` | tool | `tools/export_character_battle_visuals.py` | — | 0 | 0 |
| `export_character_runtime_oam_bindings` | tool | `tools/export_character_runtime_oam_bindings.py` | — | 0 | 0 |
| `export_character_runtime_oam_task_bindings` | tool | `tools/export_character_runtime_oam_task_bindings.py` | — | 0 | 0 |
| `export_character_runtime_unit_oam_bindings` | tool | `tools/export_character_runtime_unit_oam_bindings.py` | — | 0 | 0 |
| `export_controlled_battle_effect_pixel_ab` | tool | `tools/export_controlled_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `export_cutscene_obj_assets` | tool | `tools/export_cutscene_obj_assets.py` | — | 0 | 0 |
| `export_cutscene_obj_bundle_relocation_audit` | tool | `tools/export_cutscene_obj_bundle_relocation_audit.py` | — | 0 | 0 |
| `export_cutscene_obj_id1_pixel_ab_evidence` | tool | `tools/export_cutscene_obj_id1_pixel_ab_evidence.py` | — | 0 | 0 |
| `export_cutscene_obj_primary_ptr_ab` | tool | `tools/export_cutscene_obj_primary_ptr_ab.py` | — | 0 | 0 |
| `export_cutscene_obj_secondary_ptr_ab` | tool | `tools/export_cutscene_obj_secondary_ptr_ab.py` | — | 0 | 0 |
| `export_data_table_b_message0_pointer_ab` | tool | `tools/export_data_table_b_message0_pointer_ab.py` | — | 0 | 0 |
| `export_dialogue_font_atlases` | tool | `tools/export_dialogue_font_atlases.py` | — | 0 | 0 |
| `export_direct_image_palette_relocation_audit` | tool | `tools/export_direct_image_palette_relocation_audit.py` | — | 0 | 0 |
| `export_generic_sprite_bundle_relocation_audit` | tool | `tools/export_generic_sprite_bundle_relocation_audit.py` | — | 0 | 0 |
| `export_initializer_resource_pack` | tool | `tools/export_initializer_resource_pack.py` | — | 0 | 0 |
| `export_levels_status_per_level_ab` | tool | `tools/export_levels_status_per_level_ab.py` | — | 0 | 0 |
| `export_map41_primary_layout_pixel_ab_evidence` | tool | `tools/export_map41_primary_layout_pixel_ab_evidence.py` | — | 0 | 0 |
| `export_map41_visual_resource_matrix_evidence` | tool | `tools/export_map41_visual_resource_matrix_evidence.py` | — | 0 | 0 |
| `export_map_canvases` | tool | `tools/export_map_canvases.py` | — | 0 | 0 |
| `export_map_events_e4_handler_pixel_ab` | tool | `tools/export_map_events_e4_handler_pixel_ab.py` | — | 0 | 0 |
| `export_map_resource_relocation_audit` | tool | `tools/export_map_resource_relocation_audit.py` | — | 0 | 0 |
| `export_map_resource_writeback_audit` | tool | `tools/export_map_resource_writeback_audit.py` | — | 0 | 0 |
| `export_map_sprites_definition_pixel_ab` | tool | `tools/export_map_sprites_definition_pixel_ab.py` | — | 0 | 0 |
| `export_menu_portrait_pixel_ab_evidence` | tool | `tools/export_menu_portrait_pixel_ab_evidence.py` | — | 0 | 0 |
| `export_menu_portrait_pointer_ab` | tool | `tools/export_menu_portrait_pointer_ab.py` | — | 0 | 0 |
| `export_menu_portrait_relocation_audit` | tool | `tools/export_menu_portrait_relocation_audit.py` | — | 0 | 0 |
| `export_menu_portrait_writeback_audit` | tool | `tools/export_menu_portrait_writeback_audit.py` | — | 0 | 0 |
| `export_menu_portraits` | tool | `tools/export_menu_portraits.py` | — | 0 | 0 |
| `export_motion_effect_parameter_pixel_ab` | tool | `tools/export_motion_effect_parameter_pixel_ab.py` | — | 0 | 0 |
| `export_natural_delayed_battle_effect_pixel_ab` | tool | `tools/export_natural_delayed_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `export_overview_gradient_overlay` | tool | `tools/export_overview_gradient_overlay.py` | — | 0 | 0 |
| `export_portrait_palette_producers` | tool | `tools/export_portrait_palette_producers.py` | — | 0 | 0 |
| `export_residual_lz77_graphics_relocation_audit` | tool | `tools/export_residual_lz77_graphics_relocation_audit.py` | — | 0 | 0 |
| `export_residual_text_bg_tilemap_relocation_audit` | tool | `tools/export_residual_text_bg_tilemap_relocation_audit.py` | — | 0 | 0 |
| `export_residual_text_bg_tilemap_resource_ownership` | tool | `tools/export_residual_text_bg_tilemap_resource_ownership.py` | — | 0 | 0 |
| `export_residual_wram_crop_tilemap_runtime_evidence` | tool | `tools/export_residual_wram_crop_tilemap_runtime_evidence.py` | — | 0 | 0 |
| `export_residual_wram_derived_tilemap_relocation_audit` | tool | `tools/export_residual_wram_derived_tilemap_relocation_audit.py` | — | 0 | 0 |
| `export_residual_wram_tilemap_abi` | tool | `tools/export_residual_wram_tilemap_abi.py` | — | 0 | 0 |
| `export_residual_wram_tilemap_pixel_ab_evidence` | tool | `tools/export_residual_wram_tilemap_pixel_ab_evidence.py` | — | 0 | 0 |
| `export_residual_wram_tilemap_relocation_audit` | tool | `tools/export_residual_wram_tilemap_relocation_audit.py` | — | 0 | 0 |
| `export_residual_wram_tilemap_resource_ownership` | tool | `tools/export_residual_wram_tilemap_resource_ownership.py` | — | 0 | 0 |
| `export_residual_wram_tilemap_runtime_evidence` | tool | `tools/export_residual_wram_tilemap_runtime_evidence.py` | — | 0 | 0 |
| `export_residual_wram_tilemap_runtime_v2` | tool | `tools/export_residual_wram_tilemap_runtime_v2.py` | — | 0 | 0 |
| `export_residual_wram_transformed_tilemap_runtime_evidence` | tool | `tools/export_residual_wram_transformed_tilemap_runtime_evidence.py` | — | 0 | 0 |
| `export_residual_wram_visual_metadata_abi` | tool | `tools/export_residual_wram_visual_metadata_abi.py` | — | 0 | 0 |
| `export_rom_alternate_dialogue_table` | tool | `tools/export_rom_alternate_dialogue_table.py` | — | 0 | 0 |
| `export_rom_animation_descriptor_pool_v2` | tool | `tools/export_rom_animation_descriptor_pool_v2.py` | — | 0 | 0 |
| `export_rom_battle_condition_records` | tool | `tools/export_rom_battle_condition_records.py` | — | 0 | 0 |
| `export_rom_battle_condition_result_text` | tool | `tools/export_rom_battle_condition_result_text.py` | — | 0 | 0 |
| `export_rom_battle_controller_cfg` | tool | `tools/export_rom_battle_controller_cfg.py` | — | 0 | 0 |
| `export_rom_battle_controller_consumed_literals` | tool | `tools/export_rom_battle_controller_consumed_literals.py` | — | 0 | 0 |
| `export_rom_battle_distance_dispatcher_cfg` | tool | `tools/export_rom_battle_distance_dispatcher_cfg.py` | — | 0 | 0 |
| `export_rom_battle_message_text_inventory` | tool | `tools/export_rom_battle_message_text_inventory.py` | — | 0 | 0 |
| `export_rom_battle_sound_selector` | tool | `tools/export_rom_battle_sound_selector.py` | — | 0 | 0 |
| `export_rom_battle_status_bar_caller_slice` | tool | `tools/export_rom_battle_status_bar_caller_slice.py` | — | 0 | 0 |
| `export_rom_boot_copy_sources` | tool | `tools/export_rom_boot_copy_sources.py` | — | 0 | 0 |
| `export_rom_boot_framebuffers` | tool | `tools/export_rom_boot_framebuffers.py` | — | 0 | 0 |
| `export_rom_boot_interwork` | tool | `tools/export_rom_boot_interwork.py` | — | 0 | 0 |
| `export_rom_boot_interwork_continuation` | tool | `tools/export_rom_boot_interwork_continuation.py` | — | 0 | 0 |
| `export_rom_boot_register_init_dependency_cfg` | tool | `tools/export_rom_boot_register_init_dependency_cfg.py` | — | 0 | 0 |
| `export_rom_boot_state_dispatcher_cfg` | tool | `tools/export_rom_boot_state_dispatcher_cfg.py` | — | 0 | 0 |
| `export_rom_boot_thumb_handoff_cfg` | tool | `tools/export_rom_boot_thumb_handoff_cfg.py` | — | 0 | 0 |
| `export_rom_bounded_index_u16_pair_table` | tool | `tools/export_rom_bounded_index_u16_pair_table.py` | — | 0 | 0 |
| `export_rom_cfg_inventory` | tool | `tools/export_rom_cfg_inventory.py` | — | 0 | 0 |
| `export_rom_cfg_inventory_v3` | tool | `tools/export_rom_cfg_inventory_v3.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots` | tool | `tools/export_rom_cfg_proven_roots.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_batch_consumed_literals` | tool | `tools/export_rom_cfg_proven_roots_batch_consumed_literals.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v10` | tool | `tools/export_rom_cfg_proven_roots_v10.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v11` | tool | `tools/export_rom_cfg_proven_roots_v11.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v12` | tool | `tools/export_rom_cfg_proven_roots_v12.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v13` | tool | `tools/export_rom_cfg_proven_roots_v13.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v14` | tool | `tools/export_rom_cfg_proven_roots_v14.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v15` | tool | `tools/export_rom_cfg_proven_roots_v15.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v16` | tool | `tools/export_rom_cfg_proven_roots_v16.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v16_consumed_literals` | tool | `tools/export_rom_cfg_proven_roots_v16_consumed_literals.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v17` | tool | `tools/export_rom_cfg_proven_roots_v17.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v18` | tool | `tools/export_rom_cfg_proven_roots_v18.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v19` | tool | `tools/export_rom_cfg_proven_roots_v19.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v2` | tool | `tools/export_rom_cfg_proven_roots_v2.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v20` | tool | `tools/export_rom_cfg_proven_roots_v20.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v21` | tool | `tools/export_rom_cfg_proven_roots_v21.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v3` | tool | `tools/export_rom_cfg_proven_roots_v3.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v4` | tool | `tools/export_rom_cfg_proven_roots_v4.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v5` | tool | `tools/export_rom_cfg_proven_roots_v5.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v6` | tool | `tools/export_rom_cfg_proven_roots_v6.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v7` | tool | `tools/export_rom_cfg_proven_roots_v7.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v8` | tool | `tools/export_rom_cfg_proven_roots_v8.py` | — | 0 | 0 |
| `export_rom_cfg_proven_roots_v9` | tool | `tools/export_rom_cfg_proven_roots_v9.py` | — | 0 | 0 |
| `export_rom_cfg_seeds` | tool | `tools/export_rom_cfg_seeds.py` | — | 0 | 0 |
| `export_rom_cfg_v1_consumed_literals` | tool | `tools/export_rom_cfg_v1_consumed_literals.py` | — | 0 | 0 |
| `export_rom_cfg_v2_consumed_literals` | tool | `tools/export_rom_cfg_v2_consumed_literals.py` | — | 0 | 0 |
| `export_rom_cfg_v2_shadowed_consumed_literals` | tool | `tools/export_rom_cfg_v2_shadowed_consumed_literals.py` | — | 0 | 0 |
| `export_rom_cfg_v3_consumed_literals` | tool | `tools/export_rom_cfg_v3_consumed_literals.py` | — | 0 | 0 |
| `export_rom_cfg_v6_consumed_literals` | tool | `tools/export_rom_cfg_v6_consumed_literals.py` | — | 0 | 0 |
| `export_rom_cgb_helper_bounded_cfg` | tool | `tools/export_rom_cgb_helper_bounded_cfg.py` | — | 0 | 0 |
| `export_rom_cgbsound_bounded_cfg` | tool | `tools/export_rom_cgbsound_bounded_cfg.py` | — | 0 | 0 |
| `export_rom_chapter_script_consumer_roots` | tool | `tools/export_rom_chapter_script_consumer_roots.py` | — | 0 | 0 |
| `export_rom_chapter_script_inventory` | tool | `tools/export_rom_chapter_script_inventory.py` | — | 0 | 0 |
| `export_rom_chapter_selector_code_slice` | tool | `tools/export_rom_chapter_selector_code_slice.py` | — | 0 | 0 |
| `export_rom_cutscene_obj_source_ranges` | tool | `tools/export_rom_cutscene_obj_source_ranges.py` | — | 0 | 0 |
| `export_rom_dialogue_padding_inventory` | tool | `tools/export_rom_dialogue_padding_inventory.py` | — | 0 | 0 |
| `export_rom_dialogue_text_inventory` | tool | `tools/export_rom_dialogue_text_inventory.py` | — | 0 | 0 |
| `export_rom_direct_cpuset_gpu_inventory` | tool | `tools/export_rom_direct_cpuset_gpu_inventory.py` | — | 0 | 0 |
| `export_rom_direct_dma_gpu_inventory` | tool | `tools/export_rom_direct_dma_gpu_inventory.py` | — | 0 | 0 |
| `export_rom_directsound_pitch_lookup` | tool | `tools/export_rom_directsound_pitch_lookup.py` | — | 0 | 0 |
| `export_rom_display_text_delta` | tool | `tools/export_rom_display_text_delta.py` | — | 0 | 0 |
| `export_rom_event_handler_cfg` | tool | `tools/export_rom_event_handler_cfg.py` | — | 0 | 0 |
| `export_rom_fixed_animation_descriptor_groups` | tool | `tools/export_rom_fixed_animation_descriptor_groups.py` | — | 0 | 0 |
| `export_rom_fixed_consumer_text_inventory` | tool | `tools/export_rom_fixed_consumer_text_inventory.py` | — | 0 | 0 |
| `export_rom_fixed_index_u8_tail` | tool | `tools/export_rom_fixed_index_u8_tail.py` | — | 0 | 0 |
| `export_rom_fixed_pair_tables` | tool | `tools/export_rom_fixed_pair_tables.py` | — | 0 | 0 |
| `export_rom_fixed_renderer_script_records` | tool | `tools/export_rom_fixed_renderer_script_records.py` | — | 0 | 0 |
| `export_rom_gpu_copy_queue_inventory` | tool | `tools/export_rom_gpu_copy_queue_inventory.py` | — | 0 | 0 |
| `export_rom_low_script_delta` | tool | `tools/export_rom_low_script_delta.py` | — | 0 | 0 |
| `export_rom_m4a_byte_inventory` | tool | `tools/export_rom_m4a_byte_inventory.py` | — | 0 | 0 |
| `export_rom_m4a_initializer_chain` | tool | `tools/export_rom_m4a_initializer_chain.py` | — | 0 | 0 |
| `export_rom_menu_portrait_palette_inventory` | tool | `tools/export_rom_menu_portrait_palette_inventory.py` | — | 0 | 0 |
| `export_rom_mp2k_dispatcher` | tool | `tools/export_rom_mp2k_dispatcher.py` | — | 0 | 0 |
| `export_rom_mp2k_note_allocator` | tool | `tools/export_rom_mp2k_note_allocator.py` | — | 0 | 0 |
| `export_rom_mplaymain_scheduler` | tool | `tools/export_rom_mplaymain_scheduler.py` | — | 0 | 0 |
| `export_rom_parser_bound_zero_padding` | tool | `tools/export_rom_parser_bound_zero_padding.py` | — | 0 | 0 |
| `export_rom_pointer_lz77_graphics` | tool | `tools/export_rom_pointer_lz77_graphics.py` | — | 0 | 0 |
| `export_rom_pointer_lz77_inventory` | tool | `tools/export_rom_pointer_lz77_inventory.py` | — | 0 | 0 |
| `export_rom_positions_aux_dispatch` | tool | `tools/export_rom_positions_aux_dispatch.py` | — | 0 | 0 |
| `export_rom_post_story_dependency_precoverage` | tool | `tools/export_rom_post_story_dependency_precoverage.py` | — | 0 | 0 |
| `export_rom_prebattle_menu_controller_cfg` | tool | `tools/export_rom_prebattle_menu_controller_cfg.py` | — | 0 | 0 |
| `export_rom_profile_selector_code_slices` | tool | `tools/export_rom_profile_selector_code_slices.py` | — | 0 | 0 |
| `export_rom_profile_text_inventory` | tool | `tools/export_rom_profile_text_inventory.py` | — | 0 | 0 |
| `export_rom_psg_frequency_lookup` | tool | `tools/export_rom_psg_frequency_lookup.py` | — | 0 | 0 |
| `export_rom_referenced_text_slot_padding` | tool | `tools/export_rom_referenced_text_slot_padding.py` | — | 0 | 0 |
| `export_rom_renderer_records_delta` | tool | `tools/export_rom_renderer_records_delta.py` | — | 0 | 0 |
| `export_rom_renderer_script_pointer_pool_records` | tool | `tools/export_rom_renderer_script_pointer_pool_records.py` | — | 0 | 0 |
| `export_rom_renderer_text_inventory` | tool | `tools/export_rom_renderer_text_inventory.py` | — | 0 | 0 |
| `export_rom_scene_source_closures` | tool | `tools/export_rom_scene_source_closures.py` | — | 0 | 0 |
| `export_rom_scene_source_four_packet_precoverage` | tool | `tools/export_rom_scene_source_four_packet_precoverage.py` | — | 0 | 0 |
| `export_rom_scene_visual_source_ranges` | tool | `tools/export_rom_scene_visual_source_ranges.py` | — | 0 | 0 |
| `export_rom_selector_code_windows` | tool | `tools/export_rom_selector_code_windows.py` | — | 0 | 0 |
| `export_rom_selector_direct_source_records` | tool | `tools/export_rom_selector_direct_source_records.py` | — | 0 | 0 |
| `export_rom_selector_text_bindings` | tool | `tools/export_rom_selector_text_bindings.py` | — | 0 | 0 |
| `export_rom_small_cfg_dependency_batch` | tool | `tools/export_rom_small_cfg_dependency_batch.py` | — | 0 | 0 |
| `export_rom_soundmain_relocated_cfg` | tool | `tools/export_rom_soundmain_relocated_cfg.py` | — | 0 | 0 |
| `export_rom_sprite_component_source` | tool | `tools/export_rom_sprite_component_source.py` | — | 0 | 0 |
| `export_rom_sprite_loader_tail` | tool | `tools/export_rom_sprite_loader_tail.py` | — | 0 | 0 |
| `export_rom_staged_gpu_copy_inventory` | tool | `tools/export_rom_staged_gpu_copy_inventory.py` | — | 0 | 0 |
| `export_rom_story_callback_dependency_closures` | tool | `tools/export_rom_story_callback_dependency_closures.py` | — | 0 | 0 |
| `export_rom_story_callback_dependency_precoverage` | tool | `tools/export_rom_story_callback_dependency_precoverage.py` | — | 0 | 0 |
| `export_rom_story_next_dependency_cfg` | tool | `tools/export_rom_story_next_dependency_cfg.py` | — | 0 | 0 |
| `export_rom_story_selector_dependency_cfg` | tool | `tools/export_rom_story_selector_dependency_cfg.py` | — | 0 | 0 |
| `export_rom_story_state_callback_cfg` | tool | `tools/export_rom_story_state_callback_cfg.py` | — | 0 | 0 |
| `export_rom_story_state_entry_c4cc` | tool | `tools/export_rom_story_state_entry_c4cc.py` | — | 0 | 0 |
| `export_rom_task_callback_078e38_closure` | tool | `tools/export_rom_task_callback_078e38_closure.py` | — | 0 | 0 |
| `export_rom_task_scheduler_core` | tool | `tools/export_rom_task_scheduler_core.py` | — | 0 | 0 |
| `export_rom_text_bg_loop_continuation` | tool | `tools/export_rom_text_bg_loop_continuation.py` | — | 0 | 0 |
| `export_rom_text_bg_task_closure` | tool | `tools/export_rom_text_bg_task_closure.py` | — | 0 | 0 |
| `export_rom_training_text_script_inventory` | tool | `tools/export_rom_training_text_script_inventory.py` | — | 0 | 0 |
| `export_rom_u8_indexed_u16_pair_lookup` | tool | `tools/export_rom_u8_indexed_u16_pair_lookup.py` | — | 0 | 0 |
| `export_rom_u8_indexed_u8_triplet_lookup` | tool | `tools/export_rom_u8_indexed_u8_triplet_lookup.py` | — | 0 | 0 |
| `export_rom_unbound_chapter_script_tail` | tool | `tools/export_rom_unbound_chapter_script_tail.py` | — | 0 | 0 |
| `export_rom_unbound_lz77_inventory` | tool | `tools/export_rom_unbound_lz77_inventory.py` | — | 0 | 0 |
| `export_rom_v17_v18_helper_cfg` | tool | `tools/export_rom_v17_v18_helper_cfg.py` | — | 0 | 0 |
| `export_rom_value_range_text_inventory` | tool | `tools/export_rom_value_range_text_inventory.py` | — | 0 | 0 |
| `export_runtime_bg_composites` | tool | `tools/export_runtime_bg_composites.py` | — | 0 | 0 |
| `export_runtime_font_tile_provenance` | tool | `tools/export_runtime_font_tile_provenance.py` | — | 0 | 0 |
| `export_runtime_layer_static_provenance` | tool | `tools/export_runtime_layer_static_provenance.py` | — | 0 | 0 |
| `export_runtime_screen_composites` | tool | `tools/export_runtime_screen_composites.py` | — | 0 | 0 |
| `export_sappy_engine_master_enable_ab` | tool | `tools/export_sappy_engine_master_enable_ab.py` | — | 0 | 0 |
| `export_scene_visual_composites` | tool | `tools/export_scene_visual_composites.py` | — | 0 | 0 |
| `export_scene_visual_packs` | tool | `tools/export_scene_visual_packs.py` | — | 0 | 0 |
| `export_scene_visual_transition_timelines` | tool | `tools/export_scene_visual_transition_timelines.py` | — | 0 | 0 |
| `export_sprite_definition_animations` | tool | `tools/export_sprite_definition_animations.py` | — | 0 | 0 |
| `export_sprite_definition_runtime_chain` | tool | `tools/export_sprite_definition_runtime_chain.py` | — | 0 | 0 |
| `export_story_scene_layer_bindings` | tool | `tools/export_story_scene_layer_bindings.py` | — | 0 | 0 |
| `export_story_scene_timelines` | tool | `tools/export_story_scene_timelines.py` | — | 0 | 0 |
| `export_story_visual_layers` | tool | `tools/export_story_visual_layers.py` | — | 0 | 0 |
| `export_story_visual_resource_relocation_audit` | tool | `tools/export_story_visual_resource_relocation_audit.py` | — | 0 | 0 |
| `export_story_visual_resource_sources` | tool | `tools/export_story_visual_resource_sources.py` | — | 0 | 0 |
| `export_tile_asset_bg_layers` | tool | `tools/export_tile_asset_bg_layers.py` | — | 0 | 0 |
| `export_tile_asset_descriptor_pixel_ab` | tool | `tools/export_tile_asset_descriptor_pixel_ab.py` | — | 0 | 0 |
| `export_tile_asset_resource_relocation_audit` | tool | `tools/export_tile_asset_resource_relocation_audit.py` | — | 0 | 0 |
| `export_world_map_background_relocation_audit` | tool | `tools/export_world_map_background_relocation_audit.py` | — | 0 | 0 |
| `export_world_map_backgrounds` | tool | `tools/export_world_map_backgrounds.py` | — | 0 | 0 |
| `export_world_map_page0_pixel_ab_evidence` | tool | `tools/export_world_map_page0_pixel_ab_evidence.py` | — | 0 | 0 |
| `export_world_map_runtime` | tool | `tools/export_world_map_runtime.py` | — | 0 | 0 |
| `extract_all_structures` | tool | `tools/extract_all_structures.py` | — | 0 | 0 |
| `extract_audio` | tool | `tools/extract_audio.py` | — | 0 | 0 |
| `extract_audio_assets` | tool | `tools/extract_audio_assets.py` | — | 0 | 0 |
| `extract_audio_command_table` | tool | `tools/extract_audio_command_table.py` | — | 0 | 0 |
| `extract_audio_cue_calls` | tool | `tools/extract_audio_cue_calls.py` | — | 0 | 0 |
| `extract_audio_engine` | tool | `tools/extract_audio_engine.py` | — | 0 | 0 |
| `extract_audio_resource_sets` | tool | `tools/extract_audio_resource_sets.py` | — | 0 | 0 |
| `extract_battle_ai_planner` | tool | `tools/extract_battle_ai_planner.py` | — | 0 | 0 |
| `extract_battle_content_catalog` | tool | `tools/extract_battle_content_catalog.py` | — | 0 | 0 |
| `extract_battle_controller_states` | tool | `tools/extract_battle_controller_states.py` | — | 0 | 0 |
| `extract_battle_effect_templates` | tool | `tools/extract_battle_effect_templates.py` | — | 0 | 0 |
| `extract_chapter_flow_tables` | tool | `tools/extract_chapter_flow_tables.py` | — | 0 | 0 |
| `extract_character_definitions` | tool | `tools/extract_character_definitions.py` | — | 0 | 0 |
| `extract_character_growth` | tool | `tools/extract_character_growth.py` | — | 0 | 0 |
| `extract_dialogue_full` | tool | `tools/extract_dialogue_full.py` | — | 0 | 0 |
| `extract_graphics_resource_sets` | tool | `tools/extract_graphics_resource_sets.py` | — | 0 | 0 |
| `extract_positions` | tool | `tools/extract_positions.py` | — | 0 | 0 |
| `extract_save_descriptors` | tool | `tools/extract_save_descriptors.py` | — | 0 | 0 |
| `extract_skill_templates` | tool | `tools/extract_skill_templates.py` | — | 0 | 0 |
| `extract_text_block` | tool | `tools/extract_text_block.py` | — | 0 | 0 |
| `extract_tileset` | tool | `tools/extract_tileset.py` | — | 0 | 0 |
| `find_battlefield_object_effect_seeds` | tool | `tools/find_battlefield_object_effect_seeds.py` | — | 0 | 0 |
| `find_pointer_refs` | tool | `tools/find_pointer_refs.py` | — | 0 | 0 |
| `find_resource_tables` | tool | `tools/find_resource_tables.py` | — | 0 | 0 |
| `find_similar_tables` | tool | `tools/find_similar_tables.py` | — | 0 | 0 |
| `find_sjis_blocks` | tool | `tools/find_sjis_blocks.py` | — | 0 | 0 |
| `find_thumb_calls` | tool | `tools/find_thumb_calls.py` | — | 0 | 0 |
| `fixed_resource_roundtrip` | tool | `tools/fixed_resource_roundtrip.py` | — | 0 | 0 |
| `gba_image_export` | tool | `tools/gba_image_export.py` | — | 0 | 0 |
| `generate_butano_battle_action_content` | tool | `tools/generate_butano_battle_action_content.py` | — | 0 | 0 |
| `generate_butano_battle_runtime_assets` | tool | `tools/generate_butano_battle_runtime_assets.py` | — | 0 | 0 |
| `generate_butano_battle_unit_content` | tool | `tools/generate_butano_battle_unit_content.py` | — | 0 | 0 |
| `image_resource_regions` | tool | `tools/image_resource_regions.py` | — | 0 | 0 |
| `import_battle_config` | tool | `tools/import_battle_config.py` | — | 0 | 0 |
| `import_battle_effect_resource_relocations` | tool | `tools/import_battle_effect_resource_relocations.py` | — | 0 | 0 |
| `import_battle_effect_resources` | tool | `tools/import_battle_effect_resources.py` | — | 0 | 0 |
| `import_bg_resource_relocations` | tool | `tools/import_bg_resource_relocations.py` | — | 0 | 0 |
| `import_bg_resources` | tool | `tools/import_bg_resources.py` | — | 0 | 0 |
| `import_chapter_scripts` | tool | `tools/import_chapter_scripts.py` | — | 0 | 0 |
| `import_character_battle_bundles` | tool | `tools/import_character_battle_bundles.py` | — | 0 | 0 |
| `import_character_battle_graphics` | tool | `tools/import_character_battle_graphics.py` | — | 0 | 0 |
| `import_character_battle_palettes` | tool | `tools/import_character_battle_palettes.py` | — | 0 | 0 |
| `import_character_battle_structures` | tool | `tools/import_character_battle_structures.py` | — | 0 | 0 |
| `import_cutscene_obj_bundle_relocations` | tool | `tools/import_cutscene_obj_bundle_relocations.py` | — | 0 | 0 |
| `import_dialogue` | tool | `tools/import_dialogue.py` | — | 0 | 0 |
| `import_dialogue_var` | tool | `tools/import_dialogue_var.py` | — | 0 | 0 |
| `import_direct_image_palette_relocations` | tool | `tools/import_direct_image_palette_relocations.py` | — | 0 | 0 |
| `import_generic_sprite_bundle_relocations` | tool | `tools/import_generic_sprite_bundle_relocations.py` | — | 0 | 0 |
| `import_map` | tool | `tools/import_map.py` | — | 0 | 0 |
| `import_map_resource_relocations` | tool | `tools/import_map_resource_relocations.py` | — | 0 | 0 |
| `import_map_resources` | tool | `tools/import_map_resources.py` | — | 0 | 0 |
| `import_menu_portrait_relocations` | tool | `tools/import_menu_portrait_relocations.py` | — | 0 | 0 |
| `import_menu_portraits` | tool | `tools/import_menu_portraits.py` | — | 0 | 0 |
| `import_residual_lz77_graphics_relocations` | tool | `tools/import_residual_lz77_graphics_relocations.py` | — | 0 | 0 |
| `import_residual_text_bg_tilemap_relocations` | tool | `tools/import_residual_text_bg_tilemap_relocations.py` | — | 0 | 0 |
| `import_residual_wram_derived_tilemap_relocations` | tool | `tools/import_residual_wram_derived_tilemap_relocations.py` | — | 0 | 0 |
| `import_residual_wram_tilemap_relocations` | tool | `tools/import_residual_wram_tilemap_relocations.py` | — | 0 | 0 |
| `import_rom_to_editor` | tool | `tools/import_rom_to_editor.py` | — | 0 | 0 |
| `import_story_visual_resource_relocations` | tool | `tools/import_story_visual_resource_relocations.py` | — | 0 | 0 |
| `import_tile_asset_resources` | tool | `tools/import_tile_asset_resources.py` | — | 0 | 0 |
| `import_world_map_background_relocations` | tool | `tools/import_world_map_background_relocations.py` | — | 0 | 0 |
| `inspect_block` | tool | `tools/inspect_block.py` | — | 0 | 0 |
| `inspect_mgba_savestate` | tool | `tools/inspect_mgba_savestate.py` | — | 0 | 0 |
| `inspect_wram_region` | tool | `tools/inspect_wram_region.py` | — | 0 | 0 |
| `legacy_artifact_acceptance_contract` | tool | `tools/legacy_artifact_acceptance_contract.py` | — | 0 | 0 |
| `__init__` | tool | `tools/lib/__init__.py` | — | 0 | 0 |
| `gba_utils` | tool | `tools/lib/gba_utils.py` | — | 0 | 0 |
| `image_utils` | tool | `tools/lib/image_utils.py` | — | 0 | 0 |
| `lldb_trace_dialogue_callers` | tool | `tools/lldb_trace_dialogue_callers.py` | — | 0 | 0 |
| `m4a_channels` | tool | `tools/m4a_channels.py` | — | 0 | 0 |
| `m4a_command_vm` | tool | `tools/m4a_command_vm.py` | — | 0 | 0 |
| `m4a_envelope` | tool | `tools/m4a_envelope.py` | — | 0 | 0 |
| `m4a_pcm` | tool | `tools/m4a_pcm.py` | — | 0 | 0 |
| `m4a_pitch_step` | tool | `tools/m4a_pitch_step.py` | — | 0 | 0 |
| `m4a_psg` | tool | `tools/m4a_psg.py` | — | 0 | 0 |
| `m4a_runtime_channels` | tool | `tools/m4a_runtime_channels.py` | — | 0 | 0 |
| `m4a_scheduler` | tool | `tools/m4a_scheduler.py` | — | 0 | 0 |
| `m4a_song_engine` | tool | `tools/m4a_song_engine.py` | — | 0 | 0 |
| `m4a_track_state` | tool | `tools/m4a_track_state.py` | — | 0 | 0 |
| `macos_mgba_runtime_residue` | tool | `tools/macos_mgba_runtime_residue.py` | — | 0 | 0 |
| `macos_mgba_toolchain_profile` | tool | `tools/macos_mgba_toolchain_profile.py` | — | 0 | 0 |
| `map_m4a_instruments` | tool | `tools/map_m4a_instruments.py` | — | 0 | 0 |
| `measure_reverse_throughput` | tool | `tools/measure_reverse_throughput.py` | — | 0 | 0 |
| `mgba-headless-snapshot` | tool | `tools/mgba-headless-snapshot.py` | — | 0 | 0 |
| `mgba_gdb_probe` | tool | `tools/mgba_gdb_probe.py` | — | 0 | 0 |
| `mgba_runtime_safety` | tool | `tools/mgba_runtime_safety.py` | — | 0 | 0 |
| `ocr_report` | tool | `tools/ocr_report.py` | — | 0 | 0 |
| `ocr_screenshot` | tool | `tools/ocr_screenshot.py` | — | 0 | 0 |
| `patch_mgba_savestate_memory` | tool | `tools/patch_mgba_savestate_memory.py` | — | 0 | 0 |
| `patch_safety` | tool | `tools/patch_safety.py` | — | 0 | 0 |
| `patch_sjis` | tool | `tools/patch_sjis.py` | — | 0 | 0 |
| `populate_bank_json` | tool | `tools/populate_bank_json.py` | — | 0 | 0 |
| `prepare_rom_verifier_contracts` | tool | `tools/prepare_rom_verifier_contracts.py` | — | 0 | 0 |
| `profile_coverage_build` | tool | `tools/profile_coverage_build.py` | — | 0 | 0 |
| `profile_table_blocks` | tool | `tools/profile_table_blocks.py` | — | 0 | 0 |
| `project_resource_guard` | tool | `tools/project_resource_guard.py` | — | 0 | 0 |
| `project_status` | tool | `tools/project_status.py` | — | 0 | 0 |
| `published_call_observer` | tool | `tools/published_call_observer.py` | — | 0 | 0 |
| `quarantine_legacy_artifacts` | tool | `tools/quarantine_legacy_artifacts.py` | — | 0 | 0 |
| `rebuild_battle_effect_frame_phase_artifacts` | tool | `tools/rebuild_battle_effect_frame_phase_artifacts.py` | — | 0 | 0 |
| `rebuild_battle_effect_pixel_ab_artifacts` | tool | `tools/rebuild_battle_effect_pixel_ab_artifacts.py` | — | 0 | 0 |
| `rebuild_image_relocation_artifacts` | tool | `tools/rebuild_image_relocation_artifacts.py` | — | 0 | 0 |
| `rebuild_legacy_artifact_acceptance` | tool | `tools/rebuild_legacy_artifact_acceptance.py` | — | 0 | 0 |
| `render_m4a_midi` | tool | `tools/render_m4a_midi.py` | — | 0 | 0 |
| `render_m4a_pcm_bank` | tool | `tools/render_m4a_pcm_bank.py` | — | 0 | 0 |
| `render_mode0_checkpoint` | tool | `tools/render_mode0_checkpoint.py` | — | 0 | 0 |
| `resource_relocation_build_cli` | tool | `tools/resource_relocation_build_cli.py` | — | 0 | 0 |
| `revoke_false_story_banks` | tool | `tools/revoke_false_story_banks.py` | — | 0 | 0 |
| `rom_boot_interwork_continuation_contract` | tool | `tools/rom_boot_interwork_continuation_contract.py` | — | 0 | 0 |
| `rom_boot_register_init_dependency_cfg_contract` | tool | `tools/rom_boot_register_init_dependency_cfg_contract.py` | — | 0 | 0 |
| `rom_cfg_proven_roots_v14_contract` | tool | `tools/rom_cfg_proven_roots_v14_contract.py` | — | 0 | 0 |
| `rom_cfg_proven_roots_v15_contract` | tool | `tools/rom_cfg_proven_roots_v15_contract.py` | — | 0 | 0 |
| `rom_cfg_proven_roots_v16_contract` | tool | `tools/rom_cfg_proven_roots_v16_contract.py` | — | 0 | 0 |
| `rom_cfg_proven_roots_v17_contract` | tool | `tools/rom_cfg_proven_roots_v17_contract.py` | — | 0 | 0 |
| `rom_cfg_proven_roots_v18_contract` | tool | `tools/rom_cfg_proven_roots_v18_contract.py` | — | 0 | 0 |
| `rom_cfg_proven_roots_v19_contract` | tool | `tools/rom_cfg_proven_roots_v19_contract.py` | — | 0 | 0 |
| `rom_cfg_proven_roots_v20_contract` | tool | `tools/rom_cfg_proven_roots_v20_contract.py` | — | 0 | 0 |
| `rom_cfg_proven_roots_v21_contract` | tool | `tools/rom_cfg_proven_roots_v21_contract.py` | — | 0 | 0 |
| `rom_display_text_parameter_flow` | tool | `tools/rom_display_text_parameter_flow.py` | — | 0 | 0 |
| `rom_event_handler_cfg_contract` | tool | `tools/rom_event_handler_cfg_contract.py` | — | 0 | 0 |
| `rom_fixed_index_u8_tail_contract` | tool | `tools/rom_fixed_index_u8_tail_contract.py` | — | 0 | 0 |
| `rom_fixed_pair_tables_contract` | tool | `tools/rom_fixed_pair_tables_contract.py` | — | 0 | 0 |
| `rom_layout` | tool | `tools/rom_layout.py` | — | 0 | 0 |
| `rom_prebattle_menu_controller_cfg_contract` | tool | `tools/rom_prebattle_menu_controller_cfg_contract.py` | — | 0 | 0 |
| `rom_scene_source_closures_contract` | tool | `tools/rom_scene_source_closures_contract.py` | — | 0 | 0 |
| `rom_small_cfg_callback_gaps_independent_verifier` | tool | `tools/rom_small_cfg_callback_gaps_independent_verifier.py` | — | 0 | 0 |
| `rom_small_cfg_callback_gaps_producer` | tool | `tools/rom_small_cfg_callback_gaps_producer.py` | — | 0 | 0 |
| `rom_small_cfg_dependency_packets` | tool | `tools/rom_small_cfg_dependency_packets.py` | — | 0 | 0 |
| `rom_small_cfg_dispatch_decode` | tool | `tools/rom_small_cfg_dispatch_decode.py` | — | 0 | 0 |
| `rom_small_cfg_dispatcher_independent_verifier` | tool | `tools/rom_small_cfg_dispatcher_independent_verifier.py` | — | 0 | 0 |
| `rom_small_cfg_dispatcher_producer` | tool | `tools/rom_small_cfg_dispatcher_producer.py` | — | 0 | 0 |
| `rom_small_cfg_event_gaps_independent_verifier` | tool | `tools/rom_small_cfg_event_gaps_independent_verifier.py` | — | 0 | 0 |
| `rom_small_cfg_event_gaps_producer` | tool | `tools/rom_small_cfg_event_gaps_producer.py` | — | 0 | 0 |
| `rom_small_cfg_wrappers_independent_verifier` | tool | `tools/rom_small_cfg_wrappers_independent_verifier.py` | — | 0 | 0 |
| `rom_small_cfg_wrappers_producer` | tool | `tools/rom_small_cfg_wrappers_producer.py` | — | 0 | 0 |
| `rom_sprite_component_source_contract` | tool | `tools/rom_sprite_component_source_contract.py` | — | 0 | 0 |
| `rom_story_callback_dependency_closures_contract` | tool | `tools/rom_story_callback_dependency_closures_contract.py` | — | 0 | 0 |
| `rom_story_next_dependency_cfg_contract` | tool | `tools/rom_story_next_dependency_cfg_contract.py` | — | 0 | 0 |
| `rom_story_selector_dependency_cfg_contract` | tool | `tools/rom_story_selector_dependency_cfg_contract.py` | — | 0 | 0 |
| `rom_task_callback_078e38_contract` | tool | `tools/rom_task_callback_078e38_contract.py` | — | 0 | 0 |
| `rom_v17_v18_helper_cfg_contract` | tool | `tools/rom_v17_v18_helper_cfg_contract.py` | — | 0 | 0 |
| `run_battle_effect_allocator_reset_batch` | tool | `tools/run_battle_effect_allocator_reset_batch.py` | — | 0 | 0 |
| `run_battle_effect_controlled_sequence_batch` | tool | `tools/run_battle_effect_controlled_sequence_batch.py` | — | 0 | 0 |
| `run_battle_effect_direct_spawn_batch` | tool | `tools/run_battle_effect_direct_spawn_batch.py` | — | 0 | 0 |
| `run_battle_effect_phase_batch` | tool | `tools/run_battle_effect_phase_batch.py` | — | 0 | 0 |
| `run_controlled_battle_effect_pixel_ab` | tool | `tools/run_controlled_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `run_guarded` | tool | `tools/run_guarded.py` | — | 0 | 0 |
| `run_macos_mgba_battle_ai_action_observer` | tool | `tools/run_macos_mgba_battle_ai_action_observer.py` | — | 0 | 0 |
| `run_macos_mgba_battle_effect_phase_capture` | tool | `tools/run_macos_mgba_battle_effect_phase_capture.py` | — | 0 | 0 |
| `run_macos_mgba_controlled_battle_effect_capture` | tool | `tools/run_macos_mgba_controlled_battle_effect_capture.py` | — | 0 | 0 |
| `run_macos_mgba_group15_natural_branch_trace` | tool | `tools/run_macos_mgba_group15_natural_branch_trace.py` | — | 0 | 0 |
| `run_macos_mgba_input_sequence` | tool | `tools/run_macos_mgba_input_sequence.py` | — | 0 | 0 |
| `run_macos_mgba_replay` | tool | `tools/run_macos_mgba_replay.py` | — | 0 | 0 |
| `run_macos_mgba_replay_current` | tool | `tools/run_macos_mgba_replay_current.py` | — | 0 | 0 |
| `run_macos_mgba_single_input` | tool | `tools/run_macos_mgba_single_input.py` | — | 0 | 0 |
| `run_macos_mgba_single_input_current` | tool | `tools/run_macos_mgba_single_input_current.py` | — | 0 | 0 |
| `run_motion_effect_parameter_pixel_ab` | tool | `tools/run_motion_effect_parameter_pixel_ab.py` | — | 0 | 0 |
| `run_natural_delayed_battle_effect_pixel_ab` | tool | `tools/run_natural_delayed_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `run_offline_e2e` | tool | `tools/run_offline_e2e.py` | — | 0 | 0 |
| `runtime_checkpoint_ledger` | tool | `tools/runtime_checkpoint_ledger.py` | — | 0 | 0 |
| `scan_rom` | tool | `tools/scan_rom.py` | — | 0 | 0 |
| `summarize_watch_hits` | tool | `tools/summarize_watch_hits.py` | — | 0 | 0 |
| `thumb_branch` | tool | `tools/thumb_branch.py` | — | 0 | 0 |
| `translate_sjis_to_chinese` | tool | `tools/translate_sjis_to_chinese.py` | — | 0 | 0 |
| `verification_cache` | tool | `tools/verification_cache.py` | — | 0 | 0 |
| `verify_battle_config_records` | tool | `tools/verify_battle_config_records.py` | — | 0 | 0 |
| `verify_battle_effect_affine_runtime` | tool | `tools/verify_battle_effect_affine_runtime.py` | — | 0 | 0 |
| `verify_battle_effect_controlled_runtime` | tool | `tools/verify_battle_effect_controlled_runtime.py` | — | 0 | 0 |
| `verify_battle_effect_direct_spawn_runtime` | tool | `tools/verify_battle_effect_direct_spawn_runtime.py` | — | 0 | 0 |
| `verify_battle_effect_formation_routes` | tool | `tools/verify_battle_effect_formation_routes.py` | — | 0 | 0 |
| `verify_battle_effect_frame_phase` | tool | `tools/verify_battle_effect_frame_phase.py` | — | 0 | 0 |
| `verify_battle_effect_group15_allocator_side_runtime` | tool | `tools/verify_battle_effect_group15_allocator_side_runtime.py` | — | 0 | 0 |
| `verify_battle_effect_group15_natural_runtime` | tool | `tools/verify_battle_effect_group15_natural_runtime.py` | — | 0 | 0 |
| `verify_battle_effect_group5_pixel_ab_evidence` | tool | `tools/verify_battle_effect_group5_pixel_ab_evidence.py` | — | 0 | 0 |
| `verify_battle_effect_natural_checkpoint` | tool | `tools/verify_battle_effect_natural_checkpoint.py` | — | 0 | 0 |
| `verify_battle_effect_observed_frame_phases` | tool | `tools/verify_battle_effect_observed_frame_phases.py` | — | 0 | 0 |
| `verify_battle_effect_pixel_ab_evidence` | tool | `tools/verify_battle_effect_pixel_ab_evidence.py` | — | 0 | 0 |
| `verify_battle_effect_resource_pairs` | tool | `tools/verify_battle_effect_resource_pairs.py` | — | 0 | 0 |
| `verify_battle_effect_resource_relocation_audit` | tool | `tools/verify_battle_effect_resource_relocation_audit.py` | — | 0 | 0 |
| `verify_battle_effect_resource_writeback_audit` | tool | `tools/verify_battle_effect_resource_writeback_audit.py` | — | 0 | 0 |
| `verify_battle_effect_runtime_oam_bindings` | tool | `tools/verify_battle_effect_runtime_oam_bindings.py` | — | 0 | 0 |
| `verify_battle_effect_runtime_oam_task_bindings` | tool | `tools/verify_battle_effect_runtime_oam_task_bindings.py` | — | 0 | 0 |
| `verify_battle_effect_sequence_bindings` | tool | `tools/verify_battle_effect_sequence_bindings.py` | — | 0 | 0 |
| `verify_battle_effect_sprite_animations` | tool | `tools/verify_battle_effect_sprite_animations.py` | — | 0 | 0 |
| `verify_battle_encounters_story_visual_pixel_ab` | tool | `tools/verify_battle_encounters_story_visual_pixel_ab.py` | — | 0 | 0 |
| `verify_battle_presentation_glyphs` | tool | `tools/verify_battle_presentation_glyphs.py` | — | 0 | 0 |
| `verify_battle_presentation_rom_ranges` | tool | `tools/verify_battle_presentation_rom_ranges.py` | — | 0 | 0 |
| `verify_battle_presentation_text_padding` | tool | `tools/verify_battle_presentation_text_padding.py` | — | 0 | 0 |
| `verify_battle_status_bars` | tool | `tools/verify_battle_status_bars.py` | — | 0 | 0 |
| `verify_battle_visual_catalog` | tool | `tools/verify_battle_visual_catalog.py` | — | 0 | 0 |
| `verify_battle_visual_runtime_timelines` | tool | `tools/verify_battle_visual_runtime_timelines.py` | — | 0 | 0 |
| `verify_battlefield_object_effect_chain` | tool | `tools/verify_battlefield_object_effect_chain.py` | — | 0 | 0 |
| `verify_battlefield_object_producers` | tool | `tools/verify_battlefield_object_producers.py` | — | 0 | 0 |
| `verify_bg_resource_canvases` | tool | `tools/verify_bg_resource_canvases.py` | — | 0 | 0 |
| `verify_bg_resource_relocation_audit` | tool | `tools/verify_bg_resource_relocation_audit.py` | — | 0 | 0 |
| `verify_bg_resource_writeback_audit` | tool | `tools/verify_bg_resource_writeback_audit.py` | — | 0 | 0 |
| `verify_bg_scene_selection` | tool | `tools/verify_bg_scene_selection.py` | — | 0 | 0 |
| `verify_character_battle_bundle_relocation_audit` | tool | `tools/verify_character_battle_bundle_relocation_audit.py` | — | 0 | 0 |
| `verify_character_battle_graphics_pixel_ab_evidence` | tool | `tools/verify_character_battle_graphics_pixel_ab_evidence.py` | — | 0 | 0 |
| `verify_character_battle_graphics_writeback_audit` | tool | `tools/verify_character_battle_graphics_writeback_audit.py` | — | 0 | 0 |
| `verify_character_battle_palette_writeback_audit` | tool | `tools/verify_character_battle_palette_writeback_audit.py` | — | 0 | 0 |
| `verify_character_battle_structure_writeback_audit` | tool | `tools/verify_character_battle_structure_writeback_audit.py` | — | 0 | 0 |
| `verify_character_battle_visual_resource_matrix_evidence` | tool | `tools/verify_character_battle_visual_resource_matrix_evidence.py` | — | 0 | 0 |
| `verify_character_battle_visuals` | tool | `tools/verify_character_battle_visuals.py` | — | 0 | 0 |
| `verify_character_fbff_runtime` | tool | `tools/verify_character_fbff_runtime.py` | — | 0 | 0 |
| `verify_character_runtime_oam_bindings` | tool | `tools/verify_character_runtime_oam_bindings.py` | — | 0 | 0 |
| `verify_character_runtime_oam_task_bindings` | tool | `tools/verify_character_runtime_oam_task_bindings.py` | — | 0 | 0 |
| `verify_character_runtime_unit_oam_bindings` | tool | `tools/verify_character_runtime_unit_oam_bindings.py` | — | 0 | 0 |
| `verify_character_stats_records` | tool | `tools/verify_character_stats_records.py` | — | 0 | 0 |
| `verify_controlled_battle_effect_pixel_ab` | tool | `tools/verify_controlled_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `verify_cutscene_obj_bundle_relocation_audit` | tool | `tools/verify_cutscene_obj_bundle_relocation_audit.py` | — | 0 | 0 |
| `verify_cutscene_obj_export` | tool | `tools/verify_cutscene_obj_export.py` | — | 0 | 0 |
| `verify_cutscene_obj_id1_pixel_ab_evidence` | tool | `tools/verify_cutscene_obj_id1_pixel_ab_evidence.py` | — | 0 | 0 |
| `verify_cutscene_obj_primary_ptr_ab` | tool | `tools/verify_cutscene_obj_primary_ptr_ab.py` | — | 0 | 0 |
| `verify_cutscene_obj_secondary_ptr_ab` | tool | `tools/verify_cutscene_obj_secondary_ptr_ab.py` | — | 0 | 0 |
| `verify_data_table_b_message0_pointer_ab` | tool | `tools/verify_data_table_b_message0_pointer_ab.py` | — | 0 | 0 |
| `verify_data_table_b_partial_bank` | tool | `tools/verify_data_table_b_partial_bank.py` | — | 0 | 0 |
| `verify_dialogue_font_atlases` | tool | `tools/verify_dialogue_font_atlases.py` | — | 0 | 0 |
| `verify_dialogue_font_source_padding` | tool | `tools/verify_dialogue_font_source_padding.py` | — | 0 | 0 |
| `verify_direct_image_palette_relocation_audit` | tool | `tools/verify_direct_image_palette_relocation_audit.py` | — | 0 | 0 |
| `verify_disproved_bank_candidates` | tool | `tools/verify_disproved_bank_candidates.py` | — | 0 | 0 |
| `verify_generic_sprite_bundle_relocation_audit` | tool | `tools/verify_generic_sprite_bundle_relocation_audit.py` | — | 0 | 0 |
| `verify_initializer_resource_pack` | tool | `tools/verify_initializer_resource_pack.py` | — | 0 | 0 |
| `verify_legacy_artifact_acceptance` | tool | `tools/verify_legacy_artifact_acceptance.py` | — | 0 | 0 |
| `verify_levels_status_per_level_ab` | tool | `tools/verify_levels_status_per_level_ab.py` | — | 0 | 0 |
| `verify_lz77_palette_runtime` | tool | `tools/verify_lz77_palette_runtime.py` | — | 0 | 0 |
| `verify_map41_primary_layout_pixel_ab_evidence` | tool | `tools/verify_map41_primary_layout_pixel_ab_evidence.py` | — | 0 | 0 |
| `verify_map41_visual_resource_matrix_evidence` | tool | `tools/verify_map41_visual_resource_matrix_evidence.py` | — | 0 | 0 |
| `verify_map_canvases` | tool | `tools/verify_map_canvases.py` | — | 0 | 0 |
| `verify_map_events_e4_handler_pixel_ab` | tool | `tools/verify_map_events_e4_handler_pixel_ab.py` | — | 0 | 0 |
| `verify_map_resource_buffers` | tool | `tools/verify_map_resource_buffers.py` | — | 0 | 0 |
| `verify_map_resource_relocation_audit` | tool | `tools/verify_map_resource_relocation_audit.py` | — | 0 | 0 |
| `verify_map_resource_writeback_audit` | tool | `tools/verify_map_resource_writeback_audit.py` | — | 0 | 0 |
| `verify_map_sprites_definition_pixel_ab` | tool | `tools/verify_map_sprites_definition_pixel_ab.py` | — | 0 | 0 |
| `verify_map_sprites_partial_bank` | tool | `tools/verify_map_sprites_partial_bank.py` | — | 0 | 0 |
| `verify_maps_partial_bank` | tool | `tools/verify_maps_partial_bank.py` | — | 0 | 0 |
| `verify_menu_portrait_pixel_ab_evidence` | tool | `tools/verify_menu_portrait_pixel_ab_evidence.py` | — | 0 | 0 |
| `verify_menu_portrait_pointer_ab` | tool | `tools/verify_menu_portrait_pointer_ab.py` | — | 0 | 0 |
| `verify_menu_portrait_relocation_audit` | tool | `tools/verify_menu_portrait_relocation_audit.py` | — | 0 | 0 |
| `verify_menu_portrait_writeback_audit` | tool | `tools/verify_menu_portrait_writeback_audit.py` | — | 0 | 0 |
| `verify_mgba_renderer_source` | tool | `tools/verify_mgba_renderer_source.py` | — | 0 | 0 |
| `verify_motion_effect_parameter_pixel_ab` | tool | `tools/verify_motion_effect_parameter_pixel_ab.py` | — | 0 | 0 |
| `verify_natural_delayed_battle_effect_pixel_ab` | tool | `tools/verify_natural_delayed_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `verify_overview_gradient_overlay` | tool | `tools/verify_overview_gradient_overlay.py` | — | 0 | 0 |
| `verify_portrait_palette_producers` | tool | `tools/verify_portrait_palette_producers.py` | — | 0 | 0 |
| `verify_residual_lz77_graphics_relocation_audit` | tool | `tools/verify_residual_lz77_graphics_relocation_audit.py` | — | 0 | 0 |
| `verify_residual_text_bg_tilemap_relocation_audit` | tool | `tools/verify_residual_text_bg_tilemap_relocation_audit.py` | — | 0 | 0 |
| `verify_residual_text_bg_tilemap_resource_ownership` | tool | `tools/verify_residual_text_bg_tilemap_resource_ownership.py` | — | 0 | 0 |
| `verify_residual_wram_crop_tilemap_runtime_evidence` | tool | `tools/verify_residual_wram_crop_tilemap_runtime_evidence.py` | — | 0 | 0 |
| `verify_residual_wram_derived_tilemap_relocation_audit` | tool | `tools/verify_residual_wram_derived_tilemap_relocation_audit.py` | — | 0 | 0 |
| `verify_residual_wram_tilemap_abi` | tool | `tools/verify_residual_wram_tilemap_abi.py` | — | 0 | 0 |
| `verify_residual_wram_tilemap_pixel_ab_evidence` | tool | `tools/verify_residual_wram_tilemap_pixel_ab_evidence.py` | — | 0 | 0 |
| `verify_residual_wram_tilemap_relocation_audit` | tool | `tools/verify_residual_wram_tilemap_relocation_audit.py` | — | 0 | 0 |
| `verify_residual_wram_tilemap_resource_ownership` | tool | `tools/verify_residual_wram_tilemap_resource_ownership.py` | — | 0 | 0 |
| `verify_residual_wram_tilemap_runtime_evidence` | tool | `tools/verify_residual_wram_tilemap_runtime_evidence.py` | — | 0 | 0 |
| `verify_residual_wram_tilemap_runtime_v2` | tool | `tools/verify_residual_wram_tilemap_runtime_v2.py` | — | 0 | 0 |
| `verify_residual_wram_transformed_tilemap_runtime_evidence` | tool | `tools/verify_residual_wram_transformed_tilemap_runtime_evidence.py` | — | 0 | 0 |
| `verify_residual_wram_visual_metadata_abi` | tool | `tools/verify_residual_wram_visual_metadata_abi.py` | — | 0 | 0 |
| `verify_rom_alternate_dialogue_table` | tool | `tools/verify_rom_alternate_dialogue_table.py` | — | 0 | 0 |
| `verify_rom_animation_descriptor_pool_v2` | tool | `tools/verify_rom_animation_descriptor_pool_v2.py` | — | 0 | 0 |
| `verify_rom_artifact_bound_alignment_gaps` | tool | `tools/verify_rom_artifact_bound_alignment_gaps.py` | — | 0 | 0 |
| `verify_rom_battle_condition_records` | tool | `tools/verify_rom_battle_condition_records.py` | — | 0 | 0 |
| `verify_rom_battle_condition_result_text` | tool | `tools/verify_rom_battle_condition_result_text.py` | — | 0 | 0 |
| `verify_rom_battle_controller_cfg` | tool | `tools/verify_rom_battle_controller_cfg.py` | — | 0 | 0 |
| `verify_rom_battle_controller_consumed_literals` | tool | `tools/verify_rom_battle_controller_consumed_literals.py` | — | 0 | 0 |
| `verify_rom_battle_distance_dispatcher_cfg` | tool | `tools/verify_rom_battle_distance_dispatcher_cfg.py` | — | 0 | 0 |
| `verify_rom_battle_message_text_inventory` | tool | `tools/verify_rom_battle_message_text_inventory.py` | — | 0 | 0 |
| `verify_rom_battle_sound_selector` | tool | `tools/verify_rom_battle_sound_selector.py` | — | 0 | 0 |
| `verify_rom_battle_status_bar_caller_slice` | tool | `tools/verify_rom_battle_status_bar_caller_slice.py` | — | 0 | 0 |
| `verify_rom_boot_copy_sources` | tool | `tools/verify_rom_boot_copy_sources.py` | — | 0 | 0 |
| `verify_rom_boot_framebuffers` | tool | `tools/verify_rom_boot_framebuffers.py` | — | 0 | 0 |
| `verify_rom_boot_interwork` | tool | `tools/verify_rom_boot_interwork.py` | — | 0 | 0 |
| `verify_rom_boot_interwork_continuation` | tool | `tools/verify_rom_boot_interwork_continuation.py` | — | 0 | 0 |
| `verify_rom_boot_register_init_dependency_cfg` | tool | `tools/verify_rom_boot_register_init_dependency_cfg.py` | — | 0 | 0 |
| `verify_rom_boot_state_dispatcher_cfg` | tool | `tools/verify_rom_boot_state_dispatcher_cfg.py` | — | 0 | 0 |
| `verify_rom_boot_thumb_code_literal_alignment_gaps` | tool | `tools/verify_rom_boot_thumb_code_literal_alignment_gaps.py` | — | 0 | 0 |
| `verify_rom_boot_thumb_handoff_cfg` | tool | `tools/verify_rom_boot_thumb_handoff_cfg.py` | — | 0 | 0 |
| `verify_rom_bounded_index_u16_pair_table` | tool | `tools/verify_rom_bounded_index_u16_pair_table.py` | — | 0 | 0 |
| `verify_rom_cfg_inventory` | tool | `tools/verify_rom_cfg_inventory.py` | — | 0 | 0 |
| `verify_rom_cfg_inventory_v3` | tool | `tools/verify_rom_cfg_inventory_v3.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots` | tool | `tools/verify_rom_cfg_proven_roots.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_batch_consumed_literals` | tool | `tools/verify_rom_cfg_proven_roots_batch_consumed_literals.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v10` | tool | `tools/verify_rom_cfg_proven_roots_v10.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v11` | tool | `tools/verify_rom_cfg_proven_roots_v11.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v12` | tool | `tools/verify_rom_cfg_proven_roots_v12.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v12_bundle` | tool | `tools/verify_rom_cfg_proven_roots_v12_bundle.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v13` | tool | `tools/verify_rom_cfg_proven_roots_v13.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v13_bundle` | tool | `tools/verify_rom_cfg_proven_roots_v13_bundle.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v14` | tool | `tools/verify_rom_cfg_proven_roots_v14.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v14_bundle` | tool | `tools/verify_rom_cfg_proven_roots_v14_bundle.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v15` | tool | `tools/verify_rom_cfg_proven_roots_v15.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v15_bundle` | tool | `tools/verify_rom_cfg_proven_roots_v15_bundle.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v16` | tool | `tools/verify_rom_cfg_proven_roots_v16.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v16_consumed_literals` | tool | `tools/verify_rom_cfg_proven_roots_v16_consumed_literals.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v17` | tool | `tools/verify_rom_cfg_proven_roots_v17.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v18` | tool | `tools/verify_rom_cfg_proven_roots_v18.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v19` | tool | `tools/verify_rom_cfg_proven_roots_v19.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v2` | tool | `tools/verify_rom_cfg_proven_roots_v2.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v20` | tool | `tools/verify_rom_cfg_proven_roots_v20.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v21` | tool | `tools/verify_rom_cfg_proven_roots_v21.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v3` | tool | `tools/verify_rom_cfg_proven_roots_v3.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v4` | tool | `tools/verify_rom_cfg_proven_roots_v4.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v5` | tool | `tools/verify_rom_cfg_proven_roots_v5.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v6` | tool | `tools/verify_rom_cfg_proven_roots_v6.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v7` | tool | `tools/verify_rom_cfg_proven_roots_v7.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v8` | tool | `tools/verify_rom_cfg_proven_roots_v8.py` | — | 0 | 0 |
| `verify_rom_cfg_proven_roots_v9` | tool | `tools/verify_rom_cfg_proven_roots_v9.py` | — | 0 | 0 |
| `verify_rom_cfg_seeds` | tool | `tools/verify_rom_cfg_seeds.py` | — | 0 | 0 |
| `verify_rom_cfg_v1_consumed_literals` | tool | `tools/verify_rom_cfg_v1_consumed_literals.py` | — | 0 | 0 |
| `verify_rom_cfg_v2_consumed_literals` | tool | `tools/verify_rom_cfg_v2_consumed_literals.py` | — | 0 | 0 |
| `verify_rom_cfg_v2_shadowed_consumed_literals` | tool | `tools/verify_rom_cfg_v2_shadowed_consumed_literals.py` | — | 0 | 0 |
| `verify_rom_cfg_v3_consumed_literals` | tool | `tools/verify_rom_cfg_v3_consumed_literals.py` | — | 0 | 0 |
| `verify_rom_cfg_v6_consumed_literals` | tool | `tools/verify_rom_cfg_v6_consumed_literals.py` | — | 0 | 0 |
| `verify_rom_cgb_bounded_cfg_bundle` | tool | `tools/verify_rom_cgb_bounded_cfg_bundle.py` | — | 0 | 0 |
| `verify_rom_cgb_helper_bounded_cfg` | tool | `tools/verify_rom_cgb_helper_bounded_cfg.py` | — | 0 | 0 |
| `verify_rom_cgbsound_bounded_cfg` | tool | `tools/verify_rom_cgbsound_bounded_cfg.py` | — | 0 | 0 |
| `verify_rom_chapter_script_consumer_roots` | tool | `tools/verify_rom_chapter_script_consumer_roots.py` | — | 0 | 0 |
| `verify_rom_chapter_script_inventory` | tool | `tools/verify_rom_chapter_script_inventory.py` | — | 0 | 0 |
| `verify_rom_chapter_selector_code_slice` | tool | `tools/verify_rom_chapter_selector_code_slice.py` | — | 0 | 0 |
| `verify_rom_cutscene_obj_palette_definition_alignment_gaps` | tool | `tools/verify_rom_cutscene_obj_palette_definition_alignment_gaps.py` | — | 0 | 0 |
| `verify_rom_cutscene_obj_source_ranges` | tool | `tools/verify_rom_cutscene_obj_source_ranges.py` | — | 0 | 0 |
| `verify_rom_dialogue_padding_inventory` | tool | `tools/verify_rom_dialogue_padding_inventory.py` | — | 0 | 0 |
| `verify_rom_dialogue_text_inventory` | tool | `tools/verify_rom_dialogue_text_inventory.py` | — | 0 | 0 |
| `verify_rom_direct_cpuset_gpu_inventory` | tool | `tools/verify_rom_direct_cpuset_gpu_inventory.py` | — | 0 | 0 |
| `verify_rom_direct_dma_gpu_inventory` | tool | `tools/verify_rom_direct_dma_gpu_inventory.py` | — | 0 | 0 |
| `verify_rom_directsound_pitch_lookup` | tool | `tools/verify_rom_directsound_pitch_lookup.py` | — | 0 | 0 |
| `verify_rom_directsound_pitch_lookup_bundle` | tool | `tools/verify_rom_directsound_pitch_lookup_bundle.py` | — | 0 | 0 |
| `verify_rom_display_text_delta` | tool | `tools/verify_rom_display_text_delta.py` | — | 0 | 0 |
| `verify_rom_event_handler_cfg` | tool | `tools/verify_rom_event_handler_cfg.py` | — | 0 | 0 |
| `verify_rom_expansion_profile` | tool | `tools/verify_rom_expansion_profile.py` | — | 0 | 0 |
| `verify_rom_fast_audit_four_packet_coverage` | tool | `tools/verify_rom_fast_audit_four_packet_coverage.py` | — | 0 | 0 |
| `verify_rom_fixed_animation_descriptor_groups` | tool | `tools/verify_rom_fixed_animation_descriptor_groups.py` | — | 0 | 0 |
| `verify_rom_fixed_consumer_text_inventory` | tool | `tools/verify_rom_fixed_consumer_text_inventory.py` | — | 0 | 0 |
| `verify_rom_fixed_consumer_text_padding` | tool | `tools/verify_rom_fixed_consumer_text_padding.py` | — | 0 | 0 |
| `verify_rom_fixed_index_u8_tail` | tool | `tools/verify_rom_fixed_index_u8_tail.py` | — | 0 | 0 |
| `verify_rom_fixed_pair_tables` | tool | `tools/verify_rom_fixed_pair_tables.py` | — | 0 | 0 |
| `verify_rom_fixed_renderer_script_records` | tool | `tools/verify_rom_fixed_renderer_script_records.py` | — | 0 | 0 |
| `verify_rom_gpu_copy_queue_inventory` | tool | `tools/verify_rom_gpu_copy_queue_inventory.py` | — | 0 | 0 |
| `verify_rom_low_script_delta` | tool | `tools/verify_rom_low_script_delta.py` | — | 0 | 0 |
| `verify_rom_lz77_alignment_padding` | tool | `tools/verify_rom_lz77_alignment_padding.py` | — | 0 | 0 |
| `verify_rom_m4a_byte_inventory` | tool | `tools/verify_rom_m4a_byte_inventory.py` | — | 0 | 0 |
| `verify_rom_m4a_initializer_chain` | tool | `tools/verify_rom_m4a_initializer_chain.py` | — | 0 | 0 |
| `verify_rom_menu_portrait_lz77_palette_alignment_gaps` | tool | `tools/verify_rom_menu_portrait_lz77_palette_alignment_gaps.py` | — | 0 | 0 |
| `verify_rom_menu_portrait_palette_inventory` | tool | `tools/verify_rom_menu_portrait_palette_inventory.py` | — | 0 | 0 |
| `verify_rom_mp2k_dispatcher` | tool | `tools/verify_rom_mp2k_dispatcher.py` | — | 0 | 0 |
| `verify_rom_mp2k_note_allocator` | tool | `tools/verify_rom_mp2k_note_allocator.py` | — | 0 | 0 |
| `verify_rom_mplaymain_scheduler` | tool | `tools/verify_rom_mplaymain_scheduler.py` | — | 0 | 0 |
| `verify_rom_mplaymain_scheduler_bundle` | tool | `tools/verify_rom_mplaymain_scheduler_bundle.py` | — | 0 | 0 |
| `verify_rom_parser_bound_zero_padding` | tool | `tools/verify_rom_parser_bound_zero_padding.py` | — | 0 | 0 |
| `verify_rom_pointer_lz77_graphics` | tool | `tools/verify_rom_pointer_lz77_graphics.py` | — | 0 | 0 |
| `verify_rom_pointer_lz77_inventory` | tool | `tools/verify_rom_pointer_lz77_inventory.py` | — | 0 | 0 |
| `verify_rom_positions_aux_dispatch` | tool | `tools/verify_rom_positions_aux_dispatch.py` | — | 0 | 0 |
| `verify_rom_prebattle_menu_controller_cfg` | tool | `tools/verify_rom_prebattle_menu_controller_cfg.py` | — | 0 | 0 |
| `verify_rom_profile_selector_code_slices` | tool | `tools/verify_rom_profile_selector_code_slices.py` | — | 0 | 0 |
| `verify_rom_profile_text_inventory` | tool | `tools/verify_rom_profile_text_inventory.py` | — | 0 | 0 |
| `verify_rom_psg_frequency_lookup` | tool | `tools/verify_rom_psg_frequency_lookup.py` | — | 0 | 0 |
| `verify_rom_psg_frequency_lookup_bundle` | tool | `tools/verify_rom_psg_frequency_lookup_bundle.py` | — | 0 | 0 |
| `verify_rom_referenced_text_slot_padding` | tool | `tools/verify_rom_referenced_text_slot_padding.py` | — | 0 | 0 |
| `verify_rom_renderer_records_delta` | tool | `tools/verify_rom_renderer_records_delta.py` | — | 0 | 0 |
| `verify_rom_renderer_script_pointer_pool_records` | tool | `tools/verify_rom_renderer_script_pointer_pool_records.py` | — | 0 | 0 |
| `verify_rom_renderer_text_inventory` | tool | `tools/verify_rom_renderer_text_inventory.py` | — | 0 | 0 |
| `verify_rom_renderer_text_padding` | tool | `tools/verify_rom_renderer_text_padding.py` | — | 0 | 0 |
| `verify_rom_scene_source_closures` | tool | `tools/verify_rom_scene_source_closures.py` | — | 0 | 0 |
| `verify_rom_scene_visual_source_ranges` | tool | `tools/verify_rom_scene_visual_source_ranges.py` | — | 0 | 0 |
| `verify_rom_scheduler_callback_lifecycle_gate` | tool | `tools/verify_rom_scheduler_callback_lifecycle_gate.py` | — | 0 | 0 |
| `verify_rom_selector_code_windows` | tool | `tools/verify_rom_selector_code_windows.py` | — | 0 | 0 |
| `verify_rom_selector_direct_source_records` | tool | `tools/verify_rom_selector_direct_source_records.py` | — | 0 | 0 |
| `verify_rom_selector_text_bindings` | tool | `tools/verify_rom_selector_text_bindings.py` | — | 0 | 0 |
| `verify_rom_small_cfg_dependency_batch` | tool | `tools/verify_rom_small_cfg_dependency_batch.py` | — | 0 | 0 |
| `verify_rom_soundmain_relocated_alignment_gaps` | tool | `tools/verify_rom_soundmain_relocated_alignment_gaps.py` | — | 0 | 0 |
| `verify_rom_soundmain_relocated_cfg` | tool | `tools/verify_rom_soundmain_relocated_cfg.py` | — | 0 | 0 |
| `verify_rom_soundmain_relocated_cfg_bundle` | tool | `tools/verify_rom_soundmain_relocated_cfg_bundle.py` | — | 0 | 0 |
| `verify_rom_sprite_component_source` | tool | `tools/verify_rom_sprite_component_source.py` | — | 0 | 0 |
| `verify_rom_sprite_loader_tail` | tool | `tools/verify_rom_sprite_loader_tail.py` | — | 0 | 0 |
| `verify_rom_staged_gpu_copy_inventory` | tool | `tools/verify_rom_staged_gpu_copy_inventory.py` | — | 0 | 0 |
| `verify_rom_story_callback_dependency_closures` | tool | `tools/verify_rom_story_callback_dependency_closures.py` | — | 0 | 0 |
| `verify_rom_story_next_dependency_cfg` | tool | `tools/verify_rom_story_next_dependency_cfg.py` | — | 0 | 0 |
| `verify_rom_story_selector_dependency_cfg` | tool | `tools/verify_rom_story_selector_dependency_cfg.py` | — | 0 | 0 |
| `verify_rom_story_state_callback_cfg` | tool | `tools/verify_rom_story_state_callback_cfg.py` | — | 0 | 0 |
| `verify_rom_story_state_entry_c4cc` | tool | `tools/verify_rom_story_state_entry_c4cc.py` | — | 0 | 0 |
| `verify_rom_task_callback_078e38_closure` | tool | `tools/verify_rom_task_callback_078e38_closure.py` | — | 0 | 0 |
| `verify_rom_task_scheduler_core` | tool | `tools/verify_rom_task_scheduler_core.py` | — | 0 | 0 |
| `verify_rom_task_scheduler_core_bundle` | tool | `tools/verify_rom_task_scheduler_core_bundle.py` | — | 0 | 0 |
| `verify_rom_text_bg_loop_continuation` | tool | `tools/verify_rom_text_bg_loop_continuation.py` | — | 0 | 0 |
| `verify_rom_text_bg_task_closure` | tool | `tools/verify_rom_text_bg_task_closure.py` | — | 0 | 0 |
| `verify_rom_tile_bg_lz77_palette_alignment_gaps` | tool | `tools/verify_rom_tile_bg_lz77_palette_alignment_gaps.py` | — | 0 | 0 |
| `verify_rom_training_text_script_inventory` | tool | `tools/verify_rom_training_text_script_inventory.py` | — | 0 | 0 |
| `verify_rom_u8_indexed_u16_pair_lookup` | tool | `tools/verify_rom_u8_indexed_u16_pair_lookup.py` | — | 0 | 0 |
| `verify_rom_u8_indexed_u8_triplet_lookup` | tool | `tools/verify_rom_u8_indexed_u8_triplet_lookup.py` | — | 0 | 0 |
| `verify_rom_u8_indexed_u8_triplet_lookup_bundle` | tool | `tools/verify_rom_u8_indexed_u8_triplet_lookup_bundle.py` | — | 0 | 0 |
| `verify_rom_unbound_chapter_script_tail` | tool | `tools/verify_rom_unbound_chapter_script_tail.py` | — | 0 | 0 |
| `verify_rom_unbound_lz77_inventory` | tool | `tools/verify_rom_unbound_lz77_inventory.py` | — | 0 | 0 |
| `verify_rom_v17_v18_helper_cfg` | tool | `tools/verify_rom_v17_v18_helper_cfg.py` | — | 0 | 0 |
| `verify_rom_value_range_text_inventory` | tool | `tools/verify_rom_value_range_text_inventory.py` | — | 0 | 0 |
| `verify_runtime_bg_composites` | tool | `tools/verify_runtime_bg_composites.py` | — | 0 | 0 |
| `verify_runtime_checkpoint_containers` | tool | `tools/verify_runtime_checkpoint_containers.py` | — | 0 | 0 |
| `verify_runtime_font_tile_provenance` | tool | `tools/verify_runtime_font_tile_provenance.py` | — | 0 | 0 |
| `verify_runtime_layer_static_provenance` | tool | `tools/verify_runtime_layer_static_provenance.py` | — | 0 | 0 |
| `verify_runtime_screen_composites` | tool | `tools/verify_runtime_screen_composites.py` | — | 0 | 0 |
| `verify_sappy_engine_master_enable_ab` | tool | `tools/verify_sappy_engine_master_enable_ab.py` | — | 0 | 0 |
| `verify_save_state_records` | tool | `tools/verify_save_state_records.py` | — | 0 | 0 |
| `verify_scene_visual_composites` | tool | `tools/verify_scene_visual_composites.py` | — | 0 | 0 |
| `verify_scene_visual_packs` | tool | `tools/verify_scene_visual_packs.py` | — | 0 | 0 |
| `verify_scene_visual_transition_timelines` | tool | `tools/verify_scene_visual_transition_timelines.py` | — | 0 | 0 |
| `verify_similar_table_candidates` | tool | `tools/verify_similar_table_candidates.py` | — | 0 | 0 |
| `verify_sprite_definition_animations` | tool | `tools/verify_sprite_definition_animations.py` | — | 0 | 0 |
| `verify_sprite_definition_runtime_chain` | tool | `tools/verify_sprite_definition_runtime_chain.py` | — | 0 | 0 |
| `verify_story_scene_layer_bindings` | tool | `tools/verify_story_scene_layer_bindings.py` | — | 0 | 0 |
| `verify_story_scene_timelines` | tool | `tools/verify_story_scene_timelines.py` | — | 0 | 0 |
| `verify_story_visual_layer_export` | tool | `tools/verify_story_visual_layer_export.py` | — | 0 | 0 |
| `verify_story_visual_resource_relocation_audit` | tool | `tools/verify_story_visual_resource_relocation_audit.py` | — | 0 | 0 |
| `verify_tile_asset_bg_export` | tool | `tools/verify_tile_asset_bg_export.py` | — | 0 | 0 |
| `verify_tile_asset_descriptor_pixel_ab` | tool | `tools/verify_tile_asset_descriptor_pixel_ab.py` | — | 0 | 0 |
| `verify_tile_asset_resource_relocation_audit` | tool | `tools/verify_tile_asset_resource_relocation_audit.py` | — | 0 | 0 |
| `verify_world_map_background_relocation_audit` | tool | `tools/verify_world_map_background_relocation_audit.py` | — | 0 | 0 |
| `verify_world_map_backgrounds` | tool | `tools/verify_world_map_backgrounds.py` | — | 0 | 0 |
| `verify_world_map_page0_pixel_ab_evidence` | tool | `tools/verify_world_map_page0_pixel_ab_evidence.py` | — | 0 | 0 |
| `verify_world_map_runtime` | tool | `tools/verify_world_map_runtime.py` | — | 0 | 0 |
| `test_accept_prebattle_candidate` | test | `tests/test_accept_prebattle_candidate.py` | — | 0 | 0 |
| `test_analyze_battle_action_template_semantics` | test | `tests/test_analyze_battle_action_template_semantics.py` | — | 0 | 0 |
| `test_analyze_battle_action_transactions` | test | `tests/test_analyze_battle_action_transactions.py` | — | 0 | 0 |
| `test_analyze_battle_ai_status_policy` | test | `tests/test_analyze_battle_ai_status_policy.py` | — | 0 | 0 |
| `test_analyze_battle_ai_utility_policy` | test | `tests/test_analyze_battle_ai_utility_policy.py` | — | 0 | 0 |
| `test_analyze_battle_condition_interpreter` | test | `tests/test_analyze_battle_condition_interpreter.py` | — | 0 | 0 |
| `test_analyze_battle_controller_checkpoints` | test | `tests/test_analyze_battle_controller_checkpoints.py` | — | 0 | 0 |
| `test_analyze_battle_damage_hit_formula` | test | `tests/test_analyze_battle_damage_hit_formula.py` | — | 0 | 0 |
| `test_analyze_battle_defense_preparation` | test | `tests/test_analyze_battle_defense_preparation.py` | — | 0 | 0 |
| `test_analyze_battle_defense_reaction` | test | `tests/test_analyze_battle_defense_reaction.py` | — | 0 | 0 |
| `test_analyze_battle_effect_formation_routes` | test | `tests/test_analyze_battle_effect_formation_routes.py` | — | 0 | 0 |
| `test_analyze_battle_effect_hardcoded_selector_producers` | test | `tests/test_analyze_battle_effect_hardcoded_selector_producers.py` | — | 0 | 0 |
| `test_analyze_battle_effect_resolution` | test | `tests/test_analyze_battle_effect_resolution.py` | — | 0 | 0 |
| `test_analyze_battle_hit_modifiers` | test | `tests/test_analyze_battle_hit_modifiers.py` | — | 0 | 0 |
| `test_analyze_battle_objective_transitions` | test | `tests/test_analyze_battle_objective_transitions.py` | — | 0 | 0 |
| `test_analyze_battle_reaction_matrix` | test | `tests/test_analyze_battle_reaction_matrix.py` | — | 0 | 0 |
| `test_analyze_battle_reaction_priority` | test | `tests/test_analyze_battle_reaction_priority.py` | — | 0 | 0 |
| `test_analyze_battle_resource_transactions` | test | `tests/test_analyze_battle_resource_transactions.py` | — | 0 | 0 |
| `test_analyze_battle_status_attribute_modifiers` | test | `tests/test_analyze_battle_status_attribute_modifiers.py` | — | 0 | 0 |
| `test_analyze_battle_status_consumers` | test | `tests/test_analyze_battle_status_consumers.py` | — | 0 | 0 |
| `test_analyze_battle_status_expiry` | test | `tests/test_analyze_battle_status_expiry.py` | — | 0 | 0 |
| `test_analyze_battle_status_hit_count_modifier` | test | `tests/test_analyze_battle_status_hit_count_modifier.py` | — | 0 | 0 |
| `test_analyze_battle_status_linked_resolution` | test | `tests/test_analyze_battle_status_linked_resolution.py` | — | 0 | 0 |
| `test_analyze_battle_status_participant_consumption` | test | `tests/test_analyze_battle_status_participant_consumption.py` | — | 0 | 0 |
| `test_analyze_battle_status_stage_policy` | test | `tests/test_analyze_battle_status_stage_policy.py` | — | 0 | 0 |
| `test_analyze_battle_status_storage` | test | `tests/test_analyze_battle_status_storage.py` | — | 0 | 0 |
| `test_analyze_battle_status_transformation` | test | `tests/test_analyze_battle_status_transformation.py` | — | 0 | 0 |
| `test_analyze_battle_unit_eligibility` | test | `tests/test_analyze_battle_unit_eligibility.py` | — | 0 | 0 |
| `test_analyze_battle_unit_selection` | test | `tests/test_analyze_battle_unit_selection.py` | — | 0 | 0 |
| `test_analyze_battlefield_object_effect_chain` | test | `tests/test_analyze_battlefield_object_effect_chain.py` | — | 0 | 0 |
| `test_analyze_battlefield_object_producers` | test | `tests/test_analyze_battlefield_object_producers.py` | — | 0 | 0 |
| `test_analyze_mgba_zero_input_cycle` | test | `tests/test_analyze_mgba_zero_input_cycle.py` | — | 0 | 0 |
| `test_analyze_rom_ai_entry_domains` | test | `tests/test_analyze_rom_ai_entry_domains.py` | — | 0 | 0 |
| `test_analyze_rom_renderer_excluded_roots` | test | `tests/test_analyze_rom_renderer_excluded_roots.py` | — | 0 | 0 |
| `test_analyze_rom_renderer_handler_graphs` | test | `tests/test_analyze_rom_renderer_handler_graphs.py` | — | 0 | 0 |
| `test_analyze_rom_unknown_clusters` | test | `tests/test_analyze_rom_unknown_clusters.py` | — | 0 | 0 |
| `test_audio_sound_id_writeback` | test | `tests/test_audio_sound_id_writeback.py` | — | 0 | 0 |
| `test_audit_reverse_engineering_coverage_count_liveness` | test | `tests/test_audit_reverse_engineering_coverage_count_liveness.py` | — | 0 | 0 |
| `test_audit_reverse_engineering_parallel_verifiers` | test | `tests/test_audit_reverse_engineering_parallel_verifiers.py` | — | 0 | 0 |
| `test_audit_reverse_engineering_proof` | test | `tests/test_audit_reverse_engineering_proof.py` | — | 0 | 0 |
| `test_audit_rom_byte_coverage` | test | `tests/test_audit_rom_byte_coverage.py` | — | 0 | 0 |
| `test_audit_rom_byte_coverage_atomize_sweep` | test | `tests/test_audit_rom_byte_coverage_atomize_sweep.py` | — | 0 | 0 |
| `test_automated_test_output_isolation` | test | `tests/test_automated_test_output_isolation.py` | — | 0 | 0 |
| `test_battle_effect_fixed_roundtrip` | test | `tests/test_battle_effect_fixed_roundtrip.py` | — | 0 | 0 |
| `test_battle_effect_resource_relocation_audit` | test | `tests/test_battle_effect_resource_relocation_audit.py` | — | 0 | 0 |
| `test_battle_encounter_identity` | test | `tests/test_battle_encounter_identity.py` | — | 0 | 0 |
| `test_battle_encounters_story_visual_pixel_ab_artifact` | test | `tests/test_battle_encounters_story_visual_pixel_ab_artifact.py` | — | 0 | 0 |
| `test_battle_handler_identity` | test | `tests/test_battle_handler_identity.py` | — | 0 | 0 |
| `test_battle_status_bars_roadmap` | test | `tests/test_battle_status_bars_roadmap.py` | — | 0 | 0 |
| `test_bg_resource_relocation_audit` | test | `tests/test_bg_resource_relocation_audit.py` | — | 0 | 0 |
| `test_build_action_submit_runtime_probe` | test | `tests/test_build_action_submit_runtime_probe.py` | — | 0 | 0 |
| `test_build_adjacent_tutorial_runtime_probe` | test | `tests/test_build_adjacent_tutorial_runtime_probe.py` | — | 0 | 0 |
| `test_build_alternate_chapter_runtime_probe` | test | `tests/test_build_alternate_chapter_runtime_probe.py` | — | 0 | 0 |
| `test_build_audio_runtime_probe` | test | `tests/test_build_audio_runtime_probe.py` | — | 0 | 0 |
| `test_build_battle_catalog_runtime_probe` | test | `tests/test_build_battle_catalog_runtime_probe.py` | — | 0 | 0 |
| `test_build_battle_effect_group5_pixel_ab` | test | `tests/test_build_battle_effect_group5_pixel_ab.py` | — | 0 | 0 |
| `test_build_battle_effect_pixel_ab` | test | `tests/test_build_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `test_build_battle_effect_runtime_probe` | test | `tests/test_build_battle_effect_runtime_probe.py` | — | 0 | 0 |
| `test_build_battle_encounters_story_visual_pixel_ab` | test | `tests/test_build_battle_encounters_story_visual_pixel_ab.py` | — | 0 | 0 |
| `test_build_battle_message_runtime_probe` | test | `tests/test_build_battle_message_runtime_probe.py` | — | 0 | 0 |
| `test_build_battle_message_runtime_probe_slots` | test | `tests/test_build_battle_message_runtime_probe_slots.py` | — | 0 | 0 |
| `test_build_battle_start_runtime_probe` | test | `tests/test_build_battle_start_runtime_probe.py` | — | 0 | 0 |
| `test_build_chapter_battle_route_probe` | test | `tests/test_build_chapter_battle_route_probe.py` | — | 0 | 0 |
| `test_build_chapter_script_probe` | test | `tests/test_build_chapter_script_probe.py` | — | 0 | 0 |
| `test_build_chapter_semantic_probe` | test | `tests/test_build_chapter_semantic_probe.py` | — | 0 | 0 |
| `test_build_character_battle_graphics_pixel_ab` | test | `tests/test_build_character_battle_graphics_pixel_ab.py` | — | 0 | 0 |
| `test_build_character_battle_visual_resource_matrix` | test | `tests/test_build_character_battle_visual_resource_matrix.py` | — | 0 | 0 |
| `test_build_character_fbff_control_rom` | test | `tests/test_build_character_fbff_control_rom.py` | — | 0 | 0 |
| `test_build_character_growth_probe` | test | `tests/test_build_character_growth_probe.py` | — | 0 | 0 |
| `test_build_controlled_audio_runtime_probe` | test | `tests/test_build_controlled_audio_runtime_probe.py` | — | 0 | 0 |
| `test_build_controlled_battle_effect_allocator_reset_probe` | test | `tests/test_build_controlled_battle_effect_allocator_reset_probe.py` | — | 0 | 0 |
| `test_build_controlled_battle_effect_direct_spawn_probe` | test | `tests/test_build_controlled_battle_effect_direct_spawn_probe.py` | — | 0 | 0 |
| `test_build_controlled_battle_effect_pixel_ab` | test | `tests/test_build_controlled_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `test_build_controlled_battle_effect_sequence_probe` | test | `tests/test_build_controlled_battle_effect_sequence_probe.py` | — | 0 | 0 |
| `test_build_controller_path_runtime_probe` | test | `tests/test_build_controller_path_runtime_probe.py` | — | 0 | 0 |
| `test_build_cross_player_cgb_probe` | test | `tests/test_build_cross_player_cgb_probe.py` | — | 0 | 0 |
| `test_build_cutscene_obj_id1_pixel_ab` | test | `tests/test_build_cutscene_obj_id1_pixel_ab.py` | — | 0 | 0 |
| `test_build_cutscene_obj_primary_ptr_ab` | test | `tests/test_build_cutscene_obj_primary_ptr_ab.py` | — | 0 | 0 |
| `test_build_cutscene_obj_secondary_ptr_ab` | test | `tests/test_build_cutscene_obj_secondary_ptr_ab.py` | — | 0 | 0 |
| `test_build_delayed_audio_retrigger_probe` | test | `tests/test_build_delayed_audio_retrigger_probe.py` | — | 0 | 0 |
| `test_build_forced_save_case_probe` | test | `tests/test_build_forced_save_case_probe.py` | — | 0 | 0 |
| `test_build_function_pointer_runtime_probe` | test | `tests/test_build_function_pointer_runtime_probe.py` | — | 0 | 0 |
| `test_build_levels_runtime_probe` | test | `tests/test_build_levels_runtime_probe.py` | — | 0 | 0 |
| `test_build_macos_mgba` | test | `tests/test_build_macos_mgba.py` | — | 0 | 0 |
| `test_build_map41_primary_layout_pixel_ab` | test | `tests/test_build_map41_primary_layout_pixel_ab.py` | — | 0 | 0 |
| `test_build_map41_visual_resource_matrix` | test | `tests/test_build_map41_visual_resource_matrix.py` | — | 0 | 0 |
| `test_build_map_events_e4_handler_pixel_ab` | test | `tests/test_build_map_events_e4_handler_pixel_ab.py` | — | 0 | 0 |
| `test_build_map_sprites_definition_pixel_ab` | test | `tests/test_build_map_sprites_definition_pixel_ab.py` | — | 0 | 0 |
| `test_build_menu_portrait_pixel_ab` | test | `tests/test_build_menu_portrait_pixel_ab.py` | — | 0 | 0 |
| `test_build_menu_portrait_pointer_ab` | test | `tests/test_build_menu_portrait_pointer_ab.py` | — | 0 | 0 |
| `test_build_motion_effect_parameter_pixel_ab` | test | `tests/test_build_motion_effect_parameter_pixel_ab.py` | — | 0 | 0 |
| `test_build_natural_delayed_battle_effect_pixel_ab` | test | `tests/test_build_natural_delayed_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `test_build_natural_load_runtime_probe` | test | `tests/test_build_natural_load_runtime_probe.py` | — | 0 | 0 |
| `test_build_natural_save_runtime_probe` | test | `tests/test_build_natural_save_runtime_probe.py` | — | 0 | 0 |
| `test_build_numeric_writer_trace_probe` | test | `tests/test_build_numeric_writer_trace_probe.py` | — | 0 | 0 |
| `test_build_player_control_runtime_probe` | test | `tests/test_build_player_control_runtime_probe.py` | — | 0 | 0 |
| `test_build_postbattle_natural_save_probe` | test | `tests/test_build_postbattle_natural_save_probe.py` | — | 0 | 0 |
| `test_build_postbattle_save_probe` | test | `tests/test_build_postbattle_save_probe.py` | — | 0 | 0 |
| `test_build_profile_text_runtime_probe` | test | `tests/test_build_profile_text_runtime_probe.py` | — | 0 | 0 |
| `test_build_relocated_chapter_runtime_probe` | test | `tests/test_build_relocated_chapter_runtime_probe.py` | — | 0 | 0 |
| `test_build_residual_wram_tilemap_pixel_ab` | test | `tests/test_build_residual_wram_tilemap_pixel_ab.py` | — | 0 | 0 |
| `test_build_resource_pointer_runtime_probe` | test | `tests/test_build_resource_pointer_runtime_probe.py` | — | 0 | 0 |
| `test_build_rom_expansion_probe` | test | `tests/test_build_rom_expansion_probe.py` | — | 0 | 0 |
| `test_build_sappy_engine_master_enable_ab` | test | `tests/test_build_sappy_engine_master_enable_ab.py` | — | 0 | 0 |
| `test_build_save_group_runtime_probe` | test | `tests/test_build_save_group_runtime_probe.py` | — | 0 | 0 |
| `test_build_save_state_runtime_probe` | test | `tests/test_build_save_state_runtime_probe.py` | — | 0 | 0 |
| `test_build_skill_detail_runtime_probe` | test | `tests/test_build_skill_detail_runtime_probe.py` | — | 0 | 0 |
| `test_build_skill_relation_runtime_probe` | test | `tests/test_build_skill_relation_runtime_probe.py` | — | 0 | 0 |
| `test_build_skill_runtime_probe` | test | `tests/test_build_skill_runtime_probe.py` | — | 0 | 0 |
| `test_build_text_writer_trace_probe` | test | `tests/test_build_text_writer_trace_probe.py` | — | 0 | 0 |
| `test_build_tile_asset_descriptor_pixel_ab` | test | `tests/test_build_tile_asset_descriptor_pixel_ab.py` | — | 0 | 0 |
| `test_build_tilemap_writer_trace_probe` | test | `tests/test_build_tilemap_writer_trace_probe.py` | — | 0 | 0 |
| `test_build_training_levels_runtime_probe` | test | `tests/test_build_training_levels_runtime_probe.py` | — | 0 | 0 |
| `test_build_world_map_page0_pixel_ab` | test | `tests/test_build_world_map_page0_pixel_ab.py` | — | 0 | 0 |
| `test_butano_benchmark_harness` | test | `tests/test_butano_benchmark_harness.py` | — | 0 | 0 |
| `test_butano_build` | test | `tests/test_butano_build.py` | — | 0 | 0 |
| `test_butano_mgba_audio_recorder` | test | `tests/test_butano_mgba_audio_recorder.py` | — | 0 | 0 |
| `test_butano_research_docs` | test | `tests/test_butano_research_docs.py` | — | 0 | 0 |
| `test_butano_scenario_41_assets` | test | `tests/test_butano_scenario_41_assets.py` | — | 0 | 0 |
| `test_butano_scenario_41_attack_animation` | test | `tests/test_butano_scenario_41_attack_animation.py` | — | 0 | 0 |
| `test_butano_scenario_41_attack_assets` | test | `tests/test_butano_scenario_41_attack_assets.py` | — | 0 | 0 |
| `test_butano_scenario_41_attack_gpu_bases` | test | `tests/test_butano_scenario_41_attack_gpu_bases.py` | — | 0 | 0 |
| `test_butano_scenario_41_audio` | test | `tests/test_butano_scenario_41_audio.py` | — | 0 | 0 |
| `test_butano_scenario_41_combat_reference` | test | `tests/test_butano_scenario_41_combat_reference.py` | — | 0 | 0 |
| `test_butano_scenario_41_extended_reference` | test | `tests/test_butano_scenario_41_extended_reference.py` | — | 0 | 0 |
| `test_butano_scenario_41_gpu` | test | `tests/test_butano_scenario_41_gpu.py` | — | 0 | 0 |
| `test_butano_scenario_41_prebattle_assets` | test | `tests/test_butano_scenario_41_prebattle_assets.py` | — | 0 | 0 |
| `test_butano_scenario_41_prebattle_reference` | test | `tests/test_butano_scenario_41_prebattle_reference.py` | — | 0 | 0 |
| `test_butano_scenario_41_reference` | test | `tests/test_butano_scenario_41_reference.py` | — | 0 | 0 |
| `test_butano_scenario_41_render` | test | `tests/test_butano_scenario_41_render.py` | — | 0 | 0 |
| `test_butano_scenario_41_runtime_script` | test | `tests/test_butano_scenario_41_runtime_script.py` | — | 0 | 0 |
| `test_butano_setup` | test | `tests/test_butano_setup.py` | — | 0 | 0 |
| `test_chapter_flow_writeback` | test | `tests/test_chapter_flow_writeback.py` | — | 0 | 0 |
| `test_chapter_script_analyzer` | test | `tests/test_chapter_script_analyzer.py` | — | 0 | 0 |
| `test_chapter_script_codec` | test | `tests/test_chapter_script_codec.py` | — | 0 | 0 |
| `test_character_battle_bundle_relocation_audit` | test | `tests/test_character_battle_bundle_relocation_audit.py` | — | 0 | 0 |
| `test_character_battle_graphics_pixel_ab_evidence` | test | `tests/test_character_battle_graphics_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_character_battle_visual_resource_matrix_evidence` | test | `tests/test_character_battle_visual_resource_matrix_evidence.py` | — | 0 | 0 |
| `test_character_definition_writeback` | test | `tests/test_character_definition_writeback.py` | — | 0 | 0 |
| `test_character_overview_field_semantics` | test | `tests/test_character_overview_field_semantics.py` | — | 0 | 0 |
| `test_check_comet_project_policy` | test | `tests/test_check_comet_project_policy.py` | — | 0 | 0 |
| `test_check_staged_artifact_policy` | test | `tests/test_check_staged_artifact_policy.py` | — | 0 | 0 |
| `test_compare_mgba_audio_capture` | test | `tests/test_compare_mgba_audio_capture.py` | — | 0 | 0 |
| `test_compare_mgba_cgb_capture` | test | `tests/test_compare_mgba_cgb_capture.py` | — | 0 | 0 |
| `test_compare_mgba_cross_player_cgb_capture` | test | `tests/test_compare_mgba_cross_player_cgb_capture.py` | — | 0 | 0 |
| `test_compare_mgba_linked_audio_capture` | test | `tests/test_compare_mgba_linked_audio_capture.py` | — | 0 | 0 |
| `test_compare_mgba_retrigger_capture` | test | `tests/test_compare_mgba_retrigger_capture.py` | — | 0 | 0 |
| `test_coverage_evidence_selector_repairs` | test | `tests/test_coverage_evidence_selector_repairs.py` | — | 0 | 0 |
| `test_cutscene_obj_bundle_relocation_audit` | test | `tests/test_cutscene_obj_bundle_relocation_audit.py` | — | 0 | 0 |
| `test_cutscene_obj_primary_ptr_ab_artifact` | test | `tests/test_cutscene_obj_primary_ptr_ab_artifact.py` | — | 0 | 0 |
| `test_cutscene_obj_secondary_ptr_ab` | test | `tests/test_cutscene_obj_secondary_ptr_ab.py` | — | 0 | 0 |
| `test_cutscene_obj_secondary_ptr_publication` | test | `tests/test_cutscene_obj_secondary_ptr_publication.py` | — | 0 | 0 |
| `test_cutscene_visual_resources` | test | `tests/test_cutscene_visual_resources.py` | — | 0 | 0 |
| `test_data_table_b_message0_pointer_ab_artifact` | test | `tests/test_data_table_b_message0_pointer_ab_artifact.py` | — | 0 | 0 |
| `test_data_table_b_partial_bank` | test | `tests/test_data_table_b_partial_bank.py` | — | 0 | 0 |
| `test_decode_controller_path_runtime_probe` | test | `tests/test_decode_controller_path_runtime_probe.py` | — | 0 | 0 |
| `test_decode_dialogue_record` | test | `tests/test_decode_dialogue_record.py` | — | 0 | 0 |
| `test_decode_m4a_tracks` | test | `tests/test_decode_m4a_tracks.py` | — | 0 | 0 |
| `test_direct_image_palette_relocation_audit` | test | `tests/test_direct_image_palette_relocation_audit.py` | — | 0 | 0 |
| `test_disasm_thumb` | test | `tests/test_disasm_thumb.py` | — | 0 | 0 |
| `test_disassemble_battle_effect_dispatchers` | test | `tests/test_disassemble_battle_effect_dispatchers.py` | — | 0 | 0 |
| `test_editor_build_integration` | test | `tests/test_editor_build_integration.py` | — | 0 | 0 |
| `test_encounter_zone_identity` | test | `tests/test_encounter_zone_identity.py` | — | 0 | 0 |
| `test_experiment_workspace` | test | `tests/test_experiment_workspace.py` | — | 0 | 0 |
| `test_export_battle_effect_affine_runtime` | test | `tests/test_export_battle_effect_affine_runtime.py` | — | 0 | 0 |
| `test_export_battle_effect_controlled_runtime` | test | `tests/test_export_battle_effect_controlled_runtime.py` | — | 0 | 0 |
| `test_export_battle_effect_direct_spawn_runtime` | test | `tests/test_export_battle_effect_direct_spawn_runtime.py` | — | 0 | 0 |
| `test_export_battle_effect_frame_phase` | test | `tests/test_export_battle_effect_frame_phase.py` | — | 0 | 0 |
| `test_export_battle_effect_group15_allocator_side_runtime` | test | `tests/test_export_battle_effect_group15_allocator_side_runtime.py` | — | 0 | 0 |
| `test_export_battle_effect_group15_natural_runtime` | test | `tests/test_export_battle_effect_group15_natural_runtime.py` | — | 0 | 0 |
| `test_export_battle_effect_group5_pixel_ab_evidence` | test | `tests/test_export_battle_effect_group5_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_export_battle_effect_observed_frame_phases` | test | `tests/test_export_battle_effect_observed_frame_phases.py` | — | 0 | 0 |
| `test_export_battle_effect_pixel_ab_evidence` | test | `tests/test_export_battle_effect_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_export_battle_effect_resource_pairs` | test | `tests/test_export_battle_effect_resource_pairs.py` | — | 0 | 0 |
| `test_export_battle_effect_runtime_oam_bindings` | test | `tests/test_export_battle_effect_runtime_oam_bindings.py` | — | 0 | 0 |
| `test_export_battle_effect_runtime_oam_task_bindings` | test | `tests/test_export_battle_effect_runtime_oam_task_bindings.py` | — | 0 | 0 |
| `test_export_battle_effect_sequence_bindings` | test | `tests/test_export_battle_effect_sequence_bindings.py` | — | 0 | 0 |
| `test_export_battle_effect_sprite_animations` | test | `tests/test_export_battle_effect_sprite_animations.py` | — | 0 | 0 |
| `test_export_battle_presentation_glyphs` | test | `tests/test_export_battle_presentation_glyphs.py` | — | 0 | 0 |
| `test_export_battle_status_bars` | test | `tests/test_export_battle_status_bars.py` | — | 0 | 0 |
| `test_export_battle_visual_catalog` | test | `tests/test_export_battle_visual_catalog.py` | — | 0 | 0 |
| `test_export_battle_visual_runtime_timelines` | test | `tests/test_export_battle_visual_runtime_timelines.py` | — | 0 | 0 |
| `test_export_bg_resource_canvases` | test | `tests/test_export_bg_resource_canvases.py` | — | 0 | 0 |
| `test_export_bg_scene_selection` | test | `tests/test_export_bg_scene_selection.py` | — | 0 | 0 |
| `test_export_character_battle_visuals` | test | `tests/test_export_character_battle_visuals.py` | — | 0 | 0 |
| `test_export_character_runtime_oam_bindings` | test | `tests/test_export_character_runtime_oam_bindings.py` | — | 0 | 0 |
| `test_export_character_runtime_oam_task_bindings` | test | `tests/test_export_character_runtime_oam_task_bindings.py` | — | 0 | 0 |
| `test_export_character_runtime_unit_oam_bindings` | test | `tests/test_export_character_runtime_unit_oam_bindings.py` | — | 0 | 0 |
| `test_export_controlled_battle_effect_pixel_ab` | test | `tests/test_export_controlled_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `test_export_cutscene_obj_assets` | test | `tests/test_export_cutscene_obj_assets.py` | — | 0 | 0 |
| `test_export_cutscene_obj_id1_pixel_ab_evidence` | test | `tests/test_export_cutscene_obj_id1_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_export_dialogue_font_atlases` | test | `tests/test_export_dialogue_font_atlases.py` | — | 0 | 0 |
| `test_export_initializer_resource_pack` | test | `tests/test_export_initializer_resource_pack.py` | — | 0 | 0 |
| `test_export_map_canvases` | test | `tests/test_export_map_canvases.py` | — | 0 | 0 |
| `test_export_menu_portrait_pixel_ab_evidence` | test | `tests/test_export_menu_portrait_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_export_menu_portraits` | test | `tests/test_export_menu_portraits.py` | — | 0 | 0 |
| `test_export_motion_effect_parameter_pixel_ab` | test | `tests/test_export_motion_effect_parameter_pixel_ab.py` | — | 0 | 0 |
| `test_export_natural_delayed_battle_effect_pixel_ab` | test | `tests/test_export_natural_delayed_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `test_export_overview_gradient_overlay` | test | `tests/test_export_overview_gradient_overlay.py` | — | 0 | 0 |
| `test_export_portrait_palette_producers` | test | `tests/test_export_portrait_palette_producers.py` | — | 0 | 0 |
| `test_export_residual_text_bg_tilemap_resource_ownership` | test | `tests/test_export_residual_text_bg_tilemap_resource_ownership.py` | — | 0 | 0 |
| `test_export_residual_wram_tilemap_abi` | test | `tests/test_export_residual_wram_tilemap_abi.py` | — | 0 | 0 |
| `test_export_residual_wram_tilemap_resource_ownership` | test | `tests/test_export_residual_wram_tilemap_resource_ownership.py` | — | 0 | 0 |
| `test_export_residual_wram_visual_metadata_abi` | test | `tests/test_export_residual_wram_visual_metadata_abi.py` | — | 0 | 0 |
| `test_export_rom_alternate_dialogue_table` | test | `tests/test_export_rom_alternate_dialogue_table.py` | — | 0 | 0 |
| `test_export_rom_animation_descriptor_pool_v2` | test | `tests/test_export_rom_animation_descriptor_pool_v2.py` | — | 0 | 0 |
| `test_export_rom_battle_condition_records` | test | `tests/test_export_rom_battle_condition_records.py` | — | 0 | 0 |
| `test_export_rom_battle_condition_result_text` | test | `tests/test_export_rom_battle_condition_result_text.py` | — | 0 | 0 |
| `test_export_rom_battle_controller_cfg` | test | `tests/test_export_rom_battle_controller_cfg.py` | — | 0 | 0 |
| `test_export_rom_battle_controller_consumed_literals` | test | `tests/test_export_rom_battle_controller_consumed_literals.py` | — | 0 | 0 |
| `test_export_rom_battle_distance_dispatcher_cfg` | test | `tests/test_export_rom_battle_distance_dispatcher_cfg.py` | — | 0 | 0 |
| `test_export_rom_battle_message_text_inventory` | test | `tests/test_export_rom_battle_message_text_inventory.py` | — | 0 | 0 |
| `test_export_rom_battle_sound_selector` | test | `tests/test_export_rom_battle_sound_selector.py` | — | 0 | 0 |
| `test_export_rom_battle_status_bar_caller_slice` | test | `tests/test_export_rom_battle_status_bar_caller_slice.py` | — | 0 | 0 |
| `test_export_rom_boot_copy_sources` | test | `tests/test_export_rom_boot_copy_sources.py` | — | 0 | 0 |
| `test_export_rom_boot_framebuffers` | test | `tests/test_export_rom_boot_framebuffers.py` | — | 0 | 0 |
| `test_export_rom_boot_interwork` | test | `tests/test_export_rom_boot_interwork.py` | — | 0 | 0 |
| `test_export_rom_boot_interwork_continuation` | test | `tests/test_export_rom_boot_interwork_continuation.py` | — | 0 | 0 |
| `test_export_rom_boot_register_init_dependency_cfg` | test | `tests/test_export_rom_boot_register_init_dependency_cfg.py` | — | 0 | 0 |
| `test_export_rom_boot_state_dispatcher_cfg` | test | `tests/test_export_rom_boot_state_dispatcher_cfg.py` | — | 0 | 0 |
| `test_export_rom_boot_thumb_handoff_cfg` | test | `tests/test_export_rom_boot_thumb_handoff_cfg.py` | — | 0 | 0 |
| `test_export_rom_bounded_index_u16_pair_table` | test | `tests/test_export_rom_bounded_index_u16_pair_table.py` | — | 0 | 0 |
| `test_export_rom_cfg_inventory` | test | `tests/test_export_rom_cfg_inventory.py` | — | 0 | 0 |
| `test_export_rom_cfg_inventory_v3` | test | `tests/test_export_rom_cfg_inventory_v3.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots` | test | `tests/test_export_rom_cfg_proven_roots.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_batch_consumed_literals` | test | `tests/test_export_rom_cfg_proven_roots_batch_consumed_literals.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v10` | test | `tests/test_export_rom_cfg_proven_roots_v10.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v11` | test | `tests/test_export_rom_cfg_proven_roots_v11.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v12` | test | `tests/test_export_rom_cfg_proven_roots_v12.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v13` | test | `tests/test_export_rom_cfg_proven_roots_v13.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v14` | test | `tests/test_export_rom_cfg_proven_roots_v14.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v15` | test | `tests/test_export_rom_cfg_proven_roots_v15.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v16` | test | `tests/test_export_rom_cfg_proven_roots_v16.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v16_consumed_literals` | test | `tests/test_export_rom_cfg_proven_roots_v16_consumed_literals.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v17` | test | `tests/test_export_rom_cfg_proven_roots_v17.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v18` | test | `tests/test_export_rom_cfg_proven_roots_v18.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v19` | test | `tests/test_export_rom_cfg_proven_roots_v19.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v2` | test | `tests/test_export_rom_cfg_proven_roots_v2.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v20` | test | `tests/test_export_rom_cfg_proven_roots_v20.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v21` | test | `tests/test_export_rom_cfg_proven_roots_v21.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v3` | test | `tests/test_export_rom_cfg_proven_roots_v3.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v4` | test | `tests/test_export_rom_cfg_proven_roots_v4.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v5` | test | `tests/test_export_rom_cfg_proven_roots_v5.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v6` | test | `tests/test_export_rom_cfg_proven_roots_v6.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v7` | test | `tests/test_export_rom_cfg_proven_roots_v7.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v8` | test | `tests/test_export_rom_cfg_proven_roots_v8.py` | — | 0 | 0 |
| `test_export_rom_cfg_proven_roots_v9` | test | `tests/test_export_rom_cfg_proven_roots_v9.py` | — | 0 | 0 |
| `test_export_rom_cfg_seeds` | test | `tests/test_export_rom_cfg_seeds.py` | — | 0 | 0 |
| `test_export_rom_cfg_v1_consumed_literals` | test | `tests/test_export_rom_cfg_v1_consumed_literals.py` | — | 0 | 0 |
| `test_export_rom_cfg_v2_consumed_literals` | test | `tests/test_export_rom_cfg_v2_consumed_literals.py` | — | 0 | 0 |
| `test_export_rom_cfg_v2_shadowed_consumed_literals` | test | `tests/test_export_rom_cfg_v2_shadowed_consumed_literals.py` | — | 0 | 0 |
| `test_export_rom_cfg_v3_consumed_literals` | test | `tests/test_export_rom_cfg_v3_consumed_literals.py` | — | 0 | 0 |
| `test_export_rom_cfg_v6_consumed_literals` | test | `tests/test_export_rom_cfg_v6_consumed_literals.py` | — | 0 | 0 |
| `test_export_rom_cgb_helper_bounded_cfg` | test | `tests/test_export_rom_cgb_helper_bounded_cfg.py` | — | 0 | 0 |
| `test_export_rom_cgbsound_bounded_cfg` | test | `tests/test_export_rom_cgbsound_bounded_cfg.py` | — | 0 | 0 |
| `test_export_rom_chapter_script_consumer_roots` | test | `tests/test_export_rom_chapter_script_consumer_roots.py` | — | 0 | 0 |
| `test_export_rom_chapter_script_inventory` | test | `tests/test_export_rom_chapter_script_inventory.py` | — | 0 | 0 |
| `test_export_rom_chapter_selector_code_slice` | test | `tests/test_export_rom_chapter_selector_code_slice.py` | — | 0 | 0 |
| `test_export_rom_cutscene_obj_source_ranges` | test | `tests/test_export_rom_cutscene_obj_source_ranges.py` | — | 0 | 0 |
| `test_export_rom_dialogue_padding_inventory` | test | `tests/test_export_rom_dialogue_padding_inventory.py` | — | 0 | 0 |
| `test_export_rom_dialogue_text_inventory` | test | `tests/test_export_rom_dialogue_text_inventory.py` | — | 0 | 0 |
| `test_export_rom_direct_cpuset_gpu_inventory` | test | `tests/test_export_rom_direct_cpuset_gpu_inventory.py` | — | 0 | 0 |
| `test_export_rom_direct_dma_gpu_inventory` | test | `tests/test_export_rom_direct_dma_gpu_inventory.py` | — | 0 | 0 |
| `test_export_rom_directsound_pitch_lookup` | test | `tests/test_export_rom_directsound_pitch_lookup.py` | — | 0 | 0 |
| `test_export_rom_event_handler_cfg` | test | `tests/test_export_rom_event_handler_cfg.py` | — | 0 | 0 |
| `test_export_rom_fixed_animation_descriptor_groups` | test | `tests/test_export_rom_fixed_animation_descriptor_groups.py` | — | 0 | 0 |
| `test_export_rom_fixed_consumer_text_inventory` | test | `tests/test_export_rom_fixed_consumer_text_inventory.py` | — | 0 | 0 |
| `test_export_rom_fixed_index_u8_tail` | test | `tests/test_export_rom_fixed_index_u8_tail.py` | — | 0 | 0 |
| `test_export_rom_fixed_pair_tables` | test | `tests/test_export_rom_fixed_pair_tables.py` | — | 0 | 0 |
| `test_export_rom_fixed_renderer_script_records` | test | `tests/test_export_rom_fixed_renderer_script_records.py` | — | 0 | 0 |
| `test_export_rom_gpu_copy_queue_inventory` | test | `tests/test_export_rom_gpu_copy_queue_inventory.py` | — | 0 | 0 |
| `test_export_rom_m4a_initializer_chain` | test | `tests/test_export_rom_m4a_initializer_chain.py` | — | 0 | 0 |
| `test_export_rom_menu_portrait_palette_inventory` | test | `tests/test_export_rom_menu_portrait_palette_inventory.py` | — | 0 | 0 |
| `test_export_rom_mp2k_dispatcher` | test | `tests/test_export_rom_mp2k_dispatcher.py` | — | 0 | 0 |
| `test_export_rom_mp2k_note_allocator` | test | `tests/test_export_rom_mp2k_note_allocator.py` | — | 0 | 0 |
| `test_export_rom_mplaymain_scheduler` | test | `tests/test_export_rom_mplaymain_scheduler.py` | — | 0 | 0 |
| `test_export_rom_parser_bound_zero_padding` | test | `tests/test_export_rom_parser_bound_zero_padding.py` | — | 0 | 0 |
| `test_export_rom_pointer_lz77_graphics` | test | `tests/test_export_rom_pointer_lz77_graphics.py` | — | 0 | 0 |
| `test_export_rom_pointer_lz77_inventory` | test | `tests/test_export_rom_pointer_lz77_inventory.py` | — | 0 | 0 |
| `test_export_rom_positions_aux_dispatch` | test | `tests/test_export_rom_positions_aux_dispatch.py` | — | 0 | 0 |
| `test_export_rom_post_story_dependency_precoverage` | test | `tests/test_export_rom_post_story_dependency_precoverage.py` | — | 0 | 0 |
| `test_export_rom_prebattle_menu_controller_cfg` | test | `tests/test_export_rom_prebattle_menu_controller_cfg.py` | — | 0 | 0 |
| `test_export_rom_profile_selector_code_slices` | test | `tests/test_export_rom_profile_selector_code_slices.py` | — | 0 | 0 |
| `test_export_rom_profile_text_inventory` | test | `tests/test_export_rom_profile_text_inventory.py` | — | 0 | 0 |
| `test_export_rom_psg_frequency_lookup` | test | `tests/test_export_rom_psg_frequency_lookup.py` | — | 0 | 0 |
| `test_export_rom_referenced_text_slot_padding` | test | `tests/test_export_rom_referenced_text_slot_padding.py` | — | 0 | 0 |
| `test_export_rom_renderer_script_pointer_pool_records` | test | `tests/test_export_rom_renderer_script_pointer_pool_records.py` | — | 0 | 0 |
| `test_export_rom_renderer_text_inventory` | test | `tests/test_export_rom_renderer_text_inventory.py` | — | 0 | 0 |
| `test_export_rom_scene_source_closures` | test | `tests/test_export_rom_scene_source_closures.py` | — | 0 | 0 |
| `test_export_rom_scene_source_four_packet_precoverage` | test | `tests/test_export_rom_scene_source_four_packet_precoverage.py` | — | 0 | 0 |
| `test_export_rom_scene_visual_source_ranges` | test | `tests/test_export_rom_scene_visual_source_ranges.py` | — | 0 | 0 |
| `test_export_rom_selector_code_windows` | test | `tests/test_export_rom_selector_code_windows.py` | — | 0 | 0 |
| `test_export_rom_selector_direct_source_records` | test | `tests/test_export_rom_selector_direct_source_records.py` | — | 0 | 0 |
| `test_export_rom_selector_text_bindings` | test | `tests/test_export_rom_selector_text_bindings.py` | — | 0 | 0 |
| `test_export_rom_soundmain_relocated_cfg` | test | `tests/test_export_rom_soundmain_relocated_cfg.py` | — | 0 | 0 |
| `test_export_rom_sprite_component_source` | test | `tests/test_export_rom_sprite_component_source.py` | — | 0 | 0 |
| `test_export_rom_sprite_loader_tail` | test | `tests/test_export_rom_sprite_loader_tail.py` | — | 0 | 0 |
| `test_export_rom_staged_gpu_copy_inventory` | test | `tests/test_export_rom_staged_gpu_copy_inventory.py` | — | 0 | 0 |
| `test_export_rom_story_callback_dependency_closures` | test | `tests/test_export_rom_story_callback_dependency_closures.py` | — | 0 | 0 |
| `test_export_rom_story_callback_dependency_precoverage` | test | `tests/test_export_rom_story_callback_dependency_precoverage.py` | — | 0 | 0 |
| `test_export_rom_story_next_dependency_cfg` | test | `tests/test_export_rom_story_next_dependency_cfg.py` | — | 0 | 0 |
| `test_export_rom_story_selector_dependency_cfg` | test | `tests/test_export_rom_story_selector_dependency_cfg.py` | — | 0 | 0 |
| `test_export_rom_story_state_callback_cfg` | test | `tests/test_export_rom_story_state_callback_cfg.py` | — | 0 | 0 |
| `test_export_rom_story_state_entry_c4cc` | test | `tests/test_export_rom_story_state_entry_c4cc.py` | — | 0 | 0 |
| `test_export_rom_task_callback_078e38_closure` | test | `tests/test_export_rom_task_callback_078e38_closure.py` | — | 0 | 0 |
| `test_export_rom_task_scheduler_core` | test | `tests/test_export_rom_task_scheduler_core.py` | — | 0 | 0 |
| `test_export_rom_text_bg_loop_continuation` | test | `tests/test_export_rom_text_bg_loop_continuation.py` | — | 0 | 0 |
| `test_export_rom_text_bg_task_closure` | test | `tests/test_export_rom_text_bg_task_closure.py` | — | 0 | 0 |
| `test_export_rom_training_text_script_inventory` | test | `tests/test_export_rom_training_text_script_inventory.py` | — | 0 | 0 |
| `test_export_rom_u8_indexed_u16_pair_lookup` | test | `tests/test_export_rom_u8_indexed_u16_pair_lookup.py` | — | 0 | 0 |
| `test_export_rom_u8_indexed_u8_triplet_lookup` | test | `tests/test_export_rom_u8_indexed_u8_triplet_lookup.py` | — | 0 | 0 |
| `test_export_rom_unbound_chapter_script_tail` | test | `tests/test_export_rom_unbound_chapter_script_tail.py` | — | 0 | 0 |
| `test_export_rom_v17_v18_helper_cfg` | test | `tests/test_export_rom_v17_v18_helper_cfg.py` | — | 0 | 0 |
| `test_export_rom_value_range_text_inventory` | test | `tests/test_export_rom_value_range_text_inventory.py` | — | 0 | 0 |
| `test_export_runtime_bg_composites` | test | `tests/test_export_runtime_bg_composites.py` | — | 0 | 0 |
| `test_export_runtime_font_tile_provenance` | test | `tests/test_export_runtime_font_tile_provenance.py` | — | 0 | 0 |
| `test_export_runtime_layer_static_provenance` | test | `tests/test_export_runtime_layer_static_provenance.py` | — | 0 | 0 |
| `test_export_runtime_screen_composites` | test | `tests/test_export_runtime_screen_composites.py` | — | 0 | 0 |
| `test_export_scene_visual_composites` | test | `tests/test_export_scene_visual_composites.py` | — | 0 | 0 |
| `test_export_scene_visual_packs` | test | `tests/test_export_scene_visual_packs.py` | — | 0 | 0 |
| `test_export_scene_visual_transition_timelines` | test | `tests/test_export_scene_visual_transition_timelines.py` | — | 0 | 0 |
| `test_export_sprite_definition_animations` | test | `tests/test_export_sprite_definition_animations.py` | — | 0 | 0 |
| `test_export_sprite_definition_runtime_chain` | test | `tests/test_export_sprite_definition_runtime_chain.py` | — | 0 | 0 |
| `test_export_story_scene_layer_bindings` | test | `tests/test_export_story_scene_layer_bindings.py` | — | 0 | 0 |
| `test_export_story_scene_timelines` | test | `tests/test_export_story_scene_timelines.py` | — | 0 | 0 |
| `test_export_story_visual_layers` | test | `tests/test_export_story_visual_layers.py` | — | 0 | 0 |
| `test_export_story_visual_resource_sources` | test | `tests/test_export_story_visual_resource_sources.py` | — | 0 | 0 |
| `test_export_tile_asset_bg_layers` | test | `tests/test_export_tile_asset_bg_layers.py` | — | 0 | 0 |
| `test_export_world_map_backgrounds` | test | `tests/test_export_world_map_backgrounds.py` | — | 0 | 0 |
| `test_export_world_map_page0_pixel_ab_evidence` | test | `tests/test_export_world_map_page0_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_export_world_map_runtime` | test | `tests/test_export_world_map_runtime.py` | — | 0 | 0 |
| `test_extract_audio_assets` | test | `tests/test_extract_audio_assets.py` | — | 0 | 0 |
| `test_extract_audio_command_table` | test | `tests/test_extract_audio_command_table.py` | — | 0 | 0 |
| `test_extract_audio_cue_calls` | test | `tests/test_extract_audio_cue_calls.py` | — | 0 | 0 |
| `test_extract_audio_engine` | test | `tests/test_extract_audio_engine.py` | — | 0 | 0 |
| `test_extract_audio_resource_sets` | test | `tests/test_extract_audio_resource_sets.py` | — | 0 | 0 |
| `test_extract_battle_ai_planner` | test | `tests/test_extract_battle_ai_planner.py` | — | 0 | 0 |
| `test_extract_battle_content_catalog` | test | `tests/test_extract_battle_content_catalog.py` | — | 0 | 0 |
| `test_extract_battle_controller_states` | test | `tests/test_extract_battle_controller_states.py` | — | 0 | 0 |
| `test_extract_battle_effect_templates` | test | `tests/test_extract_battle_effect_templates.py` | — | 0 | 0 |
| `test_extract_chapter_flow_tables` | test | `tests/test_extract_chapter_flow_tables.py` | — | 0 | 0 |
| `test_extract_character_definitions` | test | `tests/test_extract_character_definitions.py` | — | 0 | 0 |
| `test_extract_character_growth` | test | `tests/test_extract_character_growth.py` | — | 0 | 0 |
| `test_extract_graphics_resource_sets` | test | `tests/test_extract_graphics_resource_sets.py` | — | 0 | 0 |
| `test_extract_positions` | test | `tests/test_extract_positions.py` | — | 0 | 0 |
| `test_extract_save_descriptors` | test | `tests/test_extract_save_descriptors.py` | — | 0 | 0 |
| `test_extract_skill_templates` | test | `tests/test_extract_skill_templates.py` | — | 0 | 0 |
| `test_extract_tileset` | test | `tests/test_extract_tileset.py` | — | 0 | 0 |
| `test_find_battlefield_object_effect_seeds` | test | `tests/test_find_battlefield_object_effect_seeds.py` | — | 0 | 0 |
| `test_find_pointer_refs` | test | `tests/test_find_pointer_refs.py` | — | 0 | 0 |
| `test_find_similar_tables` | test | `tests/test_find_similar_tables.py` | — | 0 | 0 |
| `test_find_thumb_calls` | test | `tests/test_find_thumb_calls.py` | — | 0 | 0 |
| `test_function_pointer_consumer` | test | `tests/test_function_pointer_consumer.py` | — | 0 | 0 |
| `test_gba_image_export` | test | `tests/test_gba_image_export.py` | — | 0 | 0 |
| `test_generate_butano_battle_action_content` | test | `tests/test_generate_butano_battle_action_content.py` | — | 0 | 0 |
| `test_generate_butano_battle_runtime_assets` | test | `tests/test_generate_butano_battle_runtime_assets.py` | — | 0 | 0 |
| `test_generate_butano_battle_unit_content` | test | `tests/test_generate_butano_battle_unit_content.py` | — | 0 | 0 |
| `test_generic_sprite_bundle_relocation_audit` | test | `tests/test_generic_sprite_bundle_relocation_audit.py` | — | 0 | 0 |
| `test_image_resource_regions` | test | `tests/test_image_resource_regions.py` | — | 0 | 0 |
| `test_import_battle_effect_resource_relocations` | test | `tests/test_import_battle_effect_resource_relocations.py` | — | 0 | 0 |
| `test_import_battle_effect_resources` | test | `tests/test_import_battle_effect_resources.py` | — | 0 | 0 |
| `test_import_bg_resource_relocations` | test | `tests/test_import_bg_resource_relocations.py` | — | 0 | 0 |
| `test_import_bg_resources` | test | `tests/test_import_bg_resources.py` | — | 0 | 0 |
| `test_import_chapter_scripts` | test | `tests/test_import_chapter_scripts.py` | — | 0 | 0 |
| `test_import_character_battle_bundles` | test | `tests/test_import_character_battle_bundles.py` | — | 0 | 0 |
| `test_import_character_battle_graphics` | test | `tests/test_import_character_battle_graphics.py` | — | 0 | 0 |
| `test_import_character_battle_palettes` | test | `tests/test_import_character_battle_palettes.py` | — | 0 | 0 |
| `test_import_character_battle_structures` | test | `tests/test_import_character_battle_structures.py` | — | 0 | 0 |
| `test_import_cutscene_obj_bundle_relocations` | test | `tests/test_import_cutscene_obj_bundle_relocations.py` | — | 0 | 0 |
| `test_import_dialogue_var` | test | `tests/test_import_dialogue_var.py` | — | 0 | 0 |
| `test_import_direct_image_palette_relocations` | test | `tests/test_import_direct_image_palette_relocations.py` | — | 0 | 0 |
| `test_import_generic_sprite_bundle_relocations` | test | `tests/test_import_generic_sprite_bundle_relocations.py` | — | 0 | 0 |
| `test_import_map_resource_relocations` | test | `tests/test_import_map_resource_relocations.py` | — | 0 | 0 |
| `test_import_map_resources` | test | `tests/test_import_map_resources.py` | — | 0 | 0 |
| `test_import_menu_portrait_relocations` | test | `tests/test_import_menu_portrait_relocations.py` | — | 0 | 0 |
| `test_import_menu_portraits` | test | `tests/test_import_menu_portraits.py` | — | 0 | 0 |
| `test_import_residual_lz77_graphics_relocations` | test | `tests/test_import_residual_lz77_graphics_relocations.py` | — | 0 | 0 |
| `test_import_residual_text_bg_tilemap_relocations` | test | `tests/test_import_residual_text_bg_tilemap_relocations.py` | — | 0 | 0 |
| `test_import_residual_wram_derived_tilemap_relocations` | test | `tests/test_import_residual_wram_derived_tilemap_relocations.py` | — | 0 | 0 |
| `test_import_residual_wram_tilemap_relocations` | test | `tests/test_import_residual_wram_tilemap_relocations.py` | — | 0 | 0 |
| `test_import_story_visual_resource_relocations` | test | `tests/test_import_story_visual_resource_relocations.py` | — | 0 | 0 |
| `test_import_tile_asset_resources` | test | `tests/test_import_tile_asset_resources.py` | — | 0 | 0 |
| `test_import_world_map_background_relocations` | test | `tests/test_import_world_map_background_relocations.py` | — | 0 | 0 |
| `test_inspect_mgba_savestate` | test | `tests/test_inspect_mgba_savestate.py` | — | 0 | 0 |
| `test_isolated_build_paths` | test | `tests/test_isolated_build_paths.py` | — | 0 | 0 |
| `test_levels_status_per_level_ab_artifact` | test | `tests/test_levels_status_per_level_ab_artifact.py` | — | 0 | 0 |
| `test_m4a_channels` | test | `tests/test_m4a_channels.py` | — | 0 | 0 |
| `test_m4a_command_vm` | test | `tests/test_m4a_command_vm.py` | — | 0 | 0 |
| `test_m4a_envelope` | test | `tests/test_m4a_envelope.py` | — | 0 | 0 |
| `test_m4a_pcm` | test | `tests/test_m4a_pcm.py` | — | 0 | 0 |
| `test_m4a_pitch_step` | test | `tests/test_m4a_pitch_step.py` | — | 0 | 0 |
| `test_m4a_psg` | test | `tests/test_m4a_psg.py` | — | 0 | 0 |
| `test_m4a_runtime_channels` | test | `tests/test_m4a_runtime_channels.py` | — | 0 | 0 |
| `test_m4a_scheduler` | test | `tests/test_m4a_scheduler.py` | — | 0 | 0 |
| `test_m4a_song_engine` | test | `tests/test_m4a_song_engine.py` | — | 0 | 0 |
| `test_m4a_track_state` | test | `tests/test_m4a_track_state.py` | — | 0 | 0 |
| `test_macos_mgba_runtime_residue` | test | `tests/test_macos_mgba_runtime_residue.py` | — | 0 | 0 |
| `test_map41_primary_layout_pixel_ab_evidence` | test | `tests/test_map41_primary_layout_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_map41_visual_resource_matrix_evidence` | test | `tests/test_map41_visual_resource_matrix_evidence.py` | — | 0 | 0 |
| `test_map_event_identity` | test | `tests/test_map_event_identity.py` | — | 0 | 0 |
| `test_map_events_e4_handler_pixel_ab_artifact` | test | `tests/test_map_events_e4_handler_pixel_ab_artifact.py` | — | 0 | 0 |
| `test_map_header_writeback` | test | `tests/test_map_header_writeback.py` | — | 0 | 0 |
| `test_map_m4a_instruments` | test | `tests/test_map_m4a_instruments.py` | — | 0 | 0 |
| `test_map_resource_fixed_roundtrip` | test | `tests/test_map_resource_fixed_roundtrip.py` | — | 0 | 0 |
| `test_map_resource_relocation_audit` | test | `tests/test_map_resource_relocation_audit.py` | — | 0 | 0 |
| `test_map_resource_relocation_roundtrip` | test | `tests/test_map_resource_relocation_roundtrip.py` | — | 0 | 0 |
| `test_map_sprites_definition_pixel_ab_artifact` | test | `tests/test_map_sprites_definition_pixel_ab_artifact.py` | — | 0 | 0 |
| `test_map_sprites_partial_bank` | test | `tests/test_map_sprites_partial_bank.py` | — | 0 | 0 |
| `test_maps_partial_bank` | test | `tests/test_maps_partial_bank.py` | — | 0 | 0 |
| `test_measure_reverse_throughput` | test | `tests/test_measure_reverse_throughput.py` | — | 0 | 0 |
| `test_menu_portrait_pointer_ab` | test | `tests/test_menu_portrait_pointer_ab.py` | — | 0 | 0 |
| `test_menu_portrait_pointer_publication` | test | `tests/test_menu_portrait_pointer_publication.py` | — | 0 | 0 |
| `test_menu_portrait_relocation_audit` | test | `tests/test_menu_portrait_relocation_audit.py` | — | 0 | 0 |
| `test_mgba_affine_mirror_probe_script` | test | `tests/test_mgba_affine_mirror_probe_script.py` | — | 0 | 0 |
| `test_mgba_battle_ai_action_observer_script` | test | `tests/test_mgba_battle_ai_action_observer_script.py` | — | 0 | 0 |
| `test_mgba_battle_effect_dispatcher_tracer` | test | `tests/test_mgba_battle_effect_dispatcher_tracer.py` | — | 0 | 0 |
| `test_mgba_battle_effect_phase_capture_script` | test | `tests/test_mgba_battle_effect_phase_capture_script.py` | — | 0 | 0 |
| `test_mgba_battle_encounters_story_visual_trace_script` | test | `tests/test_mgba_battle_encounters_story_visual_trace_script.py` | — | 0 | 0 |
| `test_mgba_character_fbff_probe_script` | test | `tests/test_mgba_character_fbff_probe_script.py` | — | 0 | 0 |
| `test_mgba_controlled_battle_effect_capture_script` | test | `tests/test_mgba_controlled_battle_effect_capture_script.py` | — | 0 | 0 |
| `test_mgba_gdb_probe` | test | `tests/test_mgba_gdb_probe.py` | — | 0 | 0 |
| `test_mgba_group15_natural_branch_trace_script` | test | `tests/test_mgba_group15_natural_branch_trace_script.py` | — | 0 | 0 |
| `test_mgba_headless_probe` | test | `tests/test_mgba_headless_probe.py` | — | 0 | 0 |
| `test_mgba_lz77_palette_probe_script` | test | `tests/test_mgba_lz77_palette_probe_script.py` | — | 0 | 0 |
| `test_mgba_map_events_e4_trace_script` | test | `tests/test_mgba_map_events_e4_trace_script.py` | — | 0 | 0 |
| `test_mgba_map_sprites_trace_script` | test | `tests/test_mgba_map_sprites_trace_script.py` | — | 0 | 0 |
| `test_mgba_palette_producer_probe_script` | test | `tests/test_mgba_palette_producer_probe_script.py` | — | 0 | 0 |
| `test_mgba_rom_expansion_restore_script` | test | `tests/test_mgba_rom_expansion_restore_script.py` | — | 0 | 0 |
| `test_mgba_runtime_safety` | test | `tests/test_mgba_runtime_safety.py` | — | 0 | 0 |
| `test_mgba_sappy_engine_master_enable_trace_script` | test | `tests/test_mgba_sappy_engine_master_enable_trace_script.py` | — | 0 | 0 |
| `test_mgba_tile_asset_initializer_trace_script` | test | `tests/test_mgba_tile_asset_initializer_trace_script.py` | — | 0 | 0 |
| `test_mgba_wram_crop_tilemap_probe_script` | test | `tests/test_mgba_wram_crop_tilemap_probe_script.py` | — | 0 | 0 |
| `test_mgba_wram_tilemap_probe_script` | test | `tests/test_mgba_wram_tilemap_probe_script.py` | — | 0 | 0 |
| `test_mgba_wram_tilemap_sequence_probe_script` | test | `tests/test_mgba_wram_tilemap_sequence_probe_script.py` | — | 0 | 0 |
| `test_mgba_wram_tilemap_single_input_probe_script` | test | `tests/test_mgba_wram_tilemap_single_input_probe_script.py` | — | 0 | 0 |
| `test_ocr_screenshot` | test | `tests/test_ocr_screenshot.py` | — | 0 | 0 |
| `test_overlapping_visual_table_identity` | test | `tests/test_overlapping_visual_table_identity.py` | — | 0 | 0 |
| `test_patch_mgba_savestate_memory` | test | `tests/test_patch_mgba_savestate_memory.py` | — | 0 | 0 |
| `test_patch_safety` | test | `tests/test_patch_safety.py` | — | 0 | 0 |
| `test_populate_units_bank` | test | `tests/test_populate_units_bank.py` | — | 0 | 0 |
| `test_positions_integration` | test | `tests/test_positions_integration.py` | — | 0 | 0 |
| `test_prepare_rom_verifier_contracts` | test | `tests/test_prepare_rom_verifier_contracts.py` | — | 0 | 0 |
| `test_project_resource_guard` | test | `tests/test_project_resource_guard.py` | — | 0 | 0 |
| `test_published_call_observer` | test | `tests/test_published_call_observer.py` | — | 0 | 0 |
| `test_python_version_gate` | test | `tests/test_python_version_gate.py` | — | 0 | 0 |
| `test_quarantine_legacy_artifacts` | test | `tests/test_quarantine_legacy_artifacts.py` | — | 0 | 0 |
| `test_re_completion_audit` | test | `tests/test_re_completion_audit.py` | — | 0 | 0 |
| `test_rebuild_battle_effect_frame_phase_artifacts` | test | `tests/test_rebuild_battle_effect_frame_phase_artifacts.py` | — | 0 | 0 |
| `test_rebuild_battle_effect_pixel_ab_artifacts` | test | `tests/test_rebuild_battle_effect_pixel_ab_artifacts.py` | — | 0 | 0 |
| `test_rebuild_image_relocation_artifacts` | test | `tests/test_rebuild_image_relocation_artifacts.py` | — | 0 | 0 |
| `test_rebuild_legacy_artifact_acceptance` | test | `tests/test_rebuild_legacy_artifact_acceptance.py` | — | 0 | 0 |
| `test_remaining_static_identity` | test | `tests/test_remaining_static_identity.py` | — | 0 | 0 |
| `test_render_m4a_midi` | test | `tests/test_render_m4a_midi.py` | — | 0 | 0 |
| `test_render_m4a_pcm_bank` | test | `tests/test_render_m4a_pcm_bank.py` | — | 0 | 0 |
| `test_render_mode0_checkpoint` | test | `tests/test_render_mode0_checkpoint.py` | — | 0 | 0 |
| `test_residual_lz77_graphics_relocation_audit` | test | `tests/test_residual_lz77_graphics_relocation_audit.py` | — | 0 | 0 |
| `test_residual_text_bg_tilemap_relocation_audit` | test | `tests/test_residual_text_bg_tilemap_relocation_audit.py` | — | 0 | 0 |
| `test_residual_wram_crop_tilemap_runtime_evidence` | test | `tests/test_residual_wram_crop_tilemap_runtime_evidence.py` | — | 0 | 0 |
| `test_residual_wram_derived_tilemap_relocation_audit` | test | `tests/test_residual_wram_derived_tilemap_relocation_audit.py` | — | 0 | 0 |
| `test_residual_wram_tilemap_pixel_ab_evidence` | test | `tests/test_residual_wram_tilemap_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_residual_wram_tilemap_relocation_audit` | test | `tests/test_residual_wram_tilemap_relocation_audit.py` | — | 0 | 0 |
| `test_residual_wram_tilemap_runtime_evidence` | test | `tests/test_residual_wram_tilemap_runtime_evidence.py` | — | 0 | 0 |
| `test_residual_wram_tilemap_runtime_v2` | test | `tests/test_residual_wram_tilemap_runtime_v2.py` | — | 0 | 0 |
| `test_residual_wram_transformed_tilemap_runtime_evidence` | test | `tests/test_residual_wram_transformed_tilemap_runtime_evidence.py` | — | 0 | 0 |
| `test_rom_cfg_proven_roots_v21_coverage` | test | `tests/test_rom_cfg_proven_roots_v21_coverage.py` | — | 0 | 0 |
| `test_rom_display_text_delta` | test | `tests/test_rom_display_text_delta.py` | — | 0 | 0 |
| `test_rom_display_text_parameter_flow` | test | `tests/test_rom_display_text_parameter_flow.py` | — | 0 | 0 |
| `test_rom_layout` | test | `tests/test_rom_layout.py` | — | 0 | 0 |
| `test_rom_low_script_delta` | test | `tests/test_rom_low_script_delta.py` | — | 0 | 0 |
| `test_rom_m4a_byte_inventory` | test | `tests/test_rom_m4a_byte_inventory.py` | — | 0 | 0 |
| `test_rom_renderer_records_delta` | test | `tests/test_rom_renderer_records_delta.py` | — | 0 | 0 |
| `test_rom_renderer_script_pointer_pool_canonical` | test | `tests/test_rom_renderer_script_pointer_pool_canonical.py` | — | 0 | 0 |
| `test_rom_small_cfg_batch_canonical` | test | `tests/test_rom_small_cfg_batch_canonical.py` | — | 0 | 0 |
| `test_rom_small_cfg_batch_coverage` | test | `tests/test_rom_small_cfg_batch_coverage.py` | — | 0 | 0 |
| `test_rom_small_cfg_batch_publication` | test | `tests/test_rom_small_cfg_batch_publication.py` | — | 0 | 0 |
| `test_rom_small_cfg_callback_gaps_independent_verifier` | test | `tests/test_rom_small_cfg_callback_gaps_independent_verifier.py` | — | 0 | 0 |
| `test_rom_small_cfg_callback_gaps_parent_boundary_gates` | test | `tests/test_rom_small_cfg_callback_gaps_parent_boundary_gates.py` | — | 0 | 0 |
| `test_rom_small_cfg_callback_gaps_producer` | test | `tests/test_rom_small_cfg_callback_gaps_producer.py` | — | 0 | 0 |
| `test_rom_small_cfg_dependency_packets` | test | `tests/test_rom_small_cfg_dependency_packets.py` | — | 0 | 0 |
| `test_rom_small_cfg_dispatcher_dispatch_decode` | test | `tests/test_rom_small_cfg_dispatcher_dispatch_decode.py` | — | 0 | 0 |
| `test_rom_small_cfg_dispatcher_parent_packet` | test | `tests/test_rom_small_cfg_dispatcher_parent_packet.py` | — | 0 | 0 |
| `test_rom_small_cfg_event_gaps_packet` | test | `tests/test_rom_small_cfg_event_gaps_packet.py` | — | 0 | 0 |
| `test_rom_small_cfg_wrappers_independent_verifier` | test | `tests/test_rom_small_cfg_wrappers_independent_verifier.py` | — | 0 | 0 |
| `test_rom_small_cfg_wrappers_parent_decoder` | test | `tests/test_rom_small_cfg_wrappers_parent_decoder.py` | — | 0 | 0 |
| `test_rom_small_cfg_wrappers_producer` | test | `tests/test_rom_small_cfg_wrappers_producer.py` | — | 0 | 0 |
| `test_rom_unbound_lz77_inventory` | test | `tests/test_rom_unbound_lz77_inventory.py` | — | 0 | 0 |
| `test_run_battle_effect_allocator_reset_batch` | test | `tests/test_run_battle_effect_allocator_reset_batch.py` | — | 0 | 0 |
| `test_run_battle_effect_controlled_sequence_batch` | test | `tests/test_run_battle_effect_controlled_sequence_batch.py` | — | 0 | 0 |
| `test_run_battle_effect_direct_spawn_batch` | test | `tests/test_run_battle_effect_direct_spawn_batch.py` | — | 0 | 0 |
| `test_run_battle_effect_phase_batch` | test | `tests/test_run_battle_effect_phase_batch.py` | — | 0 | 0 |
| `test_run_controlled_battle_effect_pixel_ab` | test | `tests/test_run_controlled_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `test_run_guarded` | test | `tests/test_run_guarded.py` | — | 0 | 0 |
| `test_run_macos_mgba_battle_ai_action_observer` | test | `tests/test_run_macos_mgba_battle_ai_action_observer.py` | — | 0 | 0 |
| `test_run_macos_mgba_battle_effect_phase_capture` | test | `tests/test_run_macos_mgba_battle_effect_phase_capture.py` | — | 0 | 0 |
| `test_run_macos_mgba_controlled_battle_effect_capture` | test | `tests/test_run_macos_mgba_controlled_battle_effect_capture.py` | — | 0 | 0 |
| `test_run_macos_mgba_group15_natural_branch_trace` | test | `tests/test_run_macos_mgba_group15_natural_branch_trace.py` | — | 0 | 0 |
| `test_run_macos_mgba_input_sequence` | test | `tests/test_run_macos_mgba_input_sequence.py` | — | 0 | 0 |
| `test_run_macos_mgba_replay` | test | `tests/test_run_macos_mgba_replay.py` | — | 0 | 0 |
| `test_run_macos_mgba_replay_current` | test | `tests/test_run_macos_mgba_replay_current.py` | — | 0 | 0 |
| `test_run_macos_mgba_single_input` | test | `tests/test_run_macos_mgba_single_input.py` | — | 0 | 0 |
| `test_run_macos_mgba_single_input_current` | test | `tests/test_run_macos_mgba_single_input_current.py` | — | 0 | 0 |
| `test_run_motion_effect_parameter_pixel_ab` | test | `tests/test_run_motion_effect_parameter_pixel_ab.py` | — | 0 | 0 |
| `test_run_natural_delayed_battle_effect_pixel_ab` | test | `tests/test_run_natural_delayed_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `test_run_offline_e2e` | test | `tests/test_run_offline_e2e.py` | — | 0 | 0 |
| `test_runtime_checkpoint_ledger` | test | `tests/test_runtime_checkpoint_ledger.py` | — | 0 | 0 |
| `test_sappy_engine_master_enable_ab_artifact` | test | `tests/test_sappy_engine_master_enable_ab_artifact.py` | — | 0 | 0 |
| `test_scenario41_completion_persistence` | test | `tests/test_scenario41_completion_persistence.py` | — | 0 | 0 |
| `test_scenario41_controller_checkpoint_persistence` | test | `tests/test_scenario41_controller_checkpoint_persistence.py` | — | 0 | 0 |
| `test_scenario41_first_movedone_facing_persistence` | test | `tests/test_scenario41_first_movedone_facing_persistence.py` | — | 0 | 0 |
| `test_scenario41_first_turn_technique_menu_persistence` | test | `tests/test_scenario41_first_turn_technique_menu_persistence.py` | — | 0 | 0 |
| `test_scenario41_turn1_complete_persistence` | test | `tests/test_scenario41_turn1_complete_persistence.py` | — | 0 | 0 |
| `test_scenario42_progression_persistence` | test | `tests/test_scenario42_progression_persistence.py` | — | 0 | 0 |
| `test_scenario43_progression_persistence` | test | `tests/test_scenario43_progression_persistence.py` | — | 0 | 0 |
| `test_scenario44_progression_persistence` | test | `tests/test_scenario44_progression_persistence.py` | — | 0 | 0 |
| `test_scenario47_tool67_equipment_persistence` | test | `tests/test_scenario47_tool67_equipment_persistence.py` | — | 0 | 0 |
| `test_scenario49_battle14_tool67_entry_persistence` | test | `tests/test_scenario49_battle14_tool67_entry_persistence.py` | — | 0 | 0 |
| `test_scenario49_tool37_confirmation_persistence` | test | `tests/test_scenario49_tool37_confirmation_persistence.py` | — | 0 | 0 |
| `test_scenario49_tool37_group17_persistence` | test | `tests/test_scenario49_tool37_group17_persistence.py` | — | 0 | 0 |
| `test_scenario49_tool67_active_object_persistence` | test | `tests/test_scenario49_tool67_active_object_persistence.py` | — | 0 | 0 |
| `test_scenario49_tool67_confirmation_persistence` | test | `tests/test_scenario49_tool67_confirmation_persistence.py` | — | 0 | 0 |
| `test_scenario49_tool67_expiry_ready_persistence` | test | `tests/test_scenario49_tool67_expiry_ready_persistence.py` | — | 0 | 0 |
| `test_skill_relationship_semantics` | test | `tests/test_skill_relationship_semantics.py` | — | 0 | 0 |
| `test_staged_legacy_artifact_acceptance` | test | `tests/test_staged_legacy_artifact_acceptance.py` | — | 0 | 0 |
| `test_story_visual_resource_relocation_audit` | test | `tests/test_story_visual_resource_relocation_audit.py` | — | 0 | 0 |
| `test_text_and_visual_table_identity` | test | `tests/test_text_and_visual_table_identity.py` | — | 0 | 0 |
| `test_thumb_branch` | test | `tests/test_thumb_branch.py` | — | 0 | 0 |
| `test_tile_asset_descriptor_pixel_ab_artifact` | test | `tests/test_tile_asset_descriptor_pixel_ab_artifact.py` | — | 0 | 0 |
| `test_tile_asset_resource_relocation_audit` | test | `tests/test_tile_asset_resource_relocation_audit.py` | — | 0 | 0 |
| `test_u32_pointer_patches` | test | `tests/test_u32_pointer_patches.py` | — | 0 | 0 |
| `test_unsafe_legacy_patches` | test | `tests/test_unsafe_legacy_patches.py` | — | 0 | 0 |
| `test_unsafe_unit_patch` | test | `tests/test_unsafe_unit_patch.py` | — | 0 | 0 |
| `test_verification_cache` | test | `tests/test_verification_cache.py` | — | 0 | 0 |
| `test_verify_battle_config_records` | test | `tests/test_verify_battle_config_records.py` | — | 0 | 0 |
| `test_verify_battle_effect_controlled_runtime` | test | `tests/test_verify_battle_effect_controlled_runtime.py` | — | 0 | 0 |
| `test_verify_battle_effect_direct_spawn_runtime` | test | `tests/test_verify_battle_effect_direct_spawn_runtime.py` | — | 0 | 0 |
| `test_verify_battle_effect_formation_routes` | test | `tests/test_verify_battle_effect_formation_routes.py` | — | 0 | 0 |
| `test_verify_battle_effect_frame_phase` | test | `tests/test_verify_battle_effect_frame_phase.py` | — | 0 | 0 |
| `test_verify_battle_effect_group15_allocator_side_runtime` | test | `tests/test_verify_battle_effect_group15_allocator_side_runtime.py` | — | 0 | 0 |
| `test_verify_battle_effect_group15_natural_runtime` | test | `tests/test_verify_battle_effect_group15_natural_runtime.py` | — | 0 | 0 |
| `test_verify_battle_effect_group5_pixel_ab_evidence` | test | `tests/test_verify_battle_effect_group5_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_verify_battle_effect_natural_checkpoint` | test | `tests/test_verify_battle_effect_natural_checkpoint.py` | — | 0 | 0 |
| `test_verify_battle_effect_observed_frame_phases` | test | `tests/test_verify_battle_effect_observed_frame_phases.py` | — | 0 | 0 |
| `test_verify_battle_effect_pixel_ab_evidence` | test | `tests/test_verify_battle_effect_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_verify_battle_effect_runtime_oam_bindings` | test | `tests/test_verify_battle_effect_runtime_oam_bindings.py` | — | 0 | 0 |
| `test_verify_battle_effect_runtime_oam_task_bindings` | test | `tests/test_verify_battle_effect_runtime_oam_task_bindings.py` | — | 0 | 0 |
| `test_verify_battle_presentation_rom_ranges` | test | `tests/test_verify_battle_presentation_rom_ranges.py` | — | 0 | 0 |
| `test_verify_battle_presentation_text_padding` | test | `tests/test_verify_battle_presentation_text_padding.py` | — | 0 | 0 |
| `test_verify_battlefield_object_effect_chain` | test | `tests/test_verify_battlefield_object_effect_chain.py` | — | 0 | 0 |
| `test_verify_battlefield_object_producers` | test | `tests/test_verify_battlefield_object_producers.py` | — | 0 | 0 |
| `test_verify_character_fbff_runtime` | test | `tests/test_verify_character_fbff_runtime.py` | — | 0 | 0 |
| `test_verify_character_stats_records` | test | `tests/test_verify_character_stats_records.py` | — | 0 | 0 |
| `test_verify_controlled_battle_effect_pixel_ab` | test | `tests/test_verify_controlled_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `test_verify_cutscene_obj_id1_pixel_ab_evidence` | test | `tests/test_verify_cutscene_obj_id1_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_verify_dialogue_font_source_padding` | test | `tests/test_verify_dialogue_font_source_padding.py` | — | 0 | 0 |
| `test_verify_disproved_bank_candidates` | test | `tests/test_verify_disproved_bank_candidates.py` | — | 0 | 0 |
| `test_verify_legacy_artifact_acceptance` | test | `tests/test_verify_legacy_artifact_acceptance.py` | — | 0 | 0 |
| `test_verify_lz77_palette_runtime` | test | `tests/test_verify_lz77_palette_runtime.py` | — | 0 | 0 |
| `test_verify_map_resource_buffers` | test | `tests/test_verify_map_resource_buffers.py` | — | 0 | 0 |
| `test_verify_menu_portrait_pixel_ab_evidence` | test | `tests/test_verify_menu_portrait_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_verify_motion_effect_parameter_pixel_ab` | test | `tests/test_verify_motion_effect_parameter_pixel_ab.py` | — | 0 | 0 |
| `test_verify_natural_delayed_battle_effect_pixel_ab` | test | `tests/test_verify_natural_delayed_battle_effect_pixel_ab.py` | — | 0 | 0 |
| `test_verify_rom_artifact_bound_alignment_gaps` | test | `tests/test_verify_rom_artifact_bound_alignment_gaps.py` | — | 0 | 0 |
| `test_verify_rom_battle_controller_cfg` | test | `tests/test_verify_rom_battle_controller_cfg.py` | — | 0 | 0 |
| `test_verify_rom_battle_controller_consumed_literals` | test | `tests/test_verify_rom_battle_controller_consumed_literals.py` | — | 0 | 0 |
| `test_verify_rom_battle_status_bar_caller_slice` | test | `tests/test_verify_rom_battle_status_bar_caller_slice.py` | — | 0 | 0 |
| `test_verify_rom_boot_interwork_continuation` | test | `tests/test_verify_rom_boot_interwork_continuation.py` | — | 0 | 0 |
| `test_verify_rom_boot_thumb_code_literal_alignment_gaps` | test | `tests/test_verify_rom_boot_thumb_code_literal_alignment_gaps.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_batch_consumed_literals` | test | `tests/test_verify_rom_cfg_proven_roots_batch_consumed_literals.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v12` | test | `tests/test_verify_rom_cfg_proven_roots_v12.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v12_bundle` | test | `tests/test_verify_rom_cfg_proven_roots_v12_bundle.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v13` | test | `tests/test_verify_rom_cfg_proven_roots_v13.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v13_bundle` | test | `tests/test_verify_rom_cfg_proven_roots_v13_bundle.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v14` | test | `tests/test_verify_rom_cfg_proven_roots_v14.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v14_bundle` | test | `tests/test_verify_rom_cfg_proven_roots_v14_bundle.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v15` | test | `tests/test_verify_rom_cfg_proven_roots_v15.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v15_bundle` | test | `tests/test_verify_rom_cfg_proven_roots_v15_bundle.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v16` | test | `tests/test_verify_rom_cfg_proven_roots_v16.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v16_consumed_literals` | test | `tests/test_verify_rom_cfg_proven_roots_v16_consumed_literals.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v17` | test | `tests/test_verify_rom_cfg_proven_roots_v17.py` | — | 0 | 0 |
| `test_verify_rom_cfg_proven_roots_v18` | test | `tests/test_verify_rom_cfg_proven_roots_v18.py` | — | 0 | 0 |
| `test_verify_rom_cfg_v1_consumed_literals` | test | `tests/test_verify_rom_cfg_v1_consumed_literals.py` | — | 0 | 0 |
| `test_verify_rom_cfg_v2_consumed_literals` | test | `tests/test_verify_rom_cfg_v2_consumed_literals.py` | — | 0 | 0 |
| `test_verify_rom_cfg_v2_shadowed_consumed_literals` | test | `tests/test_verify_rom_cfg_v2_shadowed_consumed_literals.py` | — | 0 | 0 |
| `test_verify_rom_cfg_v3_consumed_literals` | test | `tests/test_verify_rom_cfg_v3_consumed_literals.py` | — | 0 | 0 |
| `test_verify_rom_cfg_v6_consumed_literals` | test | `tests/test_verify_rom_cfg_v6_consumed_literals.py` | — | 0 | 0 |
| `test_verify_rom_cgb_bounded_cfg_bundle` | test | `tests/test_verify_rom_cgb_bounded_cfg_bundle.py` | — | 0 | 0 |
| `test_verify_rom_cgb_helper_bounded_cfg` | test | `tests/test_verify_rom_cgb_helper_bounded_cfg.py` | — | 0 | 0 |
| `test_verify_rom_cgbsound_bounded_cfg` | test | `tests/test_verify_rom_cgbsound_bounded_cfg.py` | — | 0 | 0 |
| `test_verify_rom_chapter_selector_code_slice` | test | `tests/test_verify_rom_chapter_selector_code_slice.py` | — | 0 | 0 |
| `test_verify_rom_cutscene_obj_palette_definition_alignment_gaps` | test | `tests/test_verify_rom_cutscene_obj_palette_definition_alignment_gaps.py` | — | 0 | 0 |
| `test_verify_rom_directsound_pitch_lookup` | test | `tests/test_verify_rom_directsound_pitch_lookup.py` | — | 0 | 0 |
| `test_verify_rom_directsound_pitch_lookup_bundle` | test | `tests/test_verify_rom_directsound_pitch_lookup_bundle.py` | — | 0 | 0 |
| `test_verify_rom_event_handler_cfg` | test | `tests/test_verify_rom_event_handler_cfg.py` | — | 0 | 0 |
| `test_verify_rom_expansion_profile` | test | `tests/test_verify_rom_expansion_profile.py` | — | 0 | 0 |
| `test_verify_rom_fast_audit_four_packet_coverage` | test | `tests/test_verify_rom_fast_audit_four_packet_coverage.py` | — | 0 | 0 |
| `test_verify_rom_fixed_consumer_text_padding` | test | `tests/test_verify_rom_fixed_consumer_text_padding.py` | — | 0 | 0 |
| `test_verify_rom_lz77_alignment_padding` | test | `tests/test_verify_rom_lz77_alignment_padding.py` | — | 0 | 0 |
| `test_verify_rom_m4a_initializer_chain` | test | `tests/test_verify_rom_m4a_initializer_chain.py` | — | 0 | 0 |
| `test_verify_rom_menu_portrait_lz77_palette_alignment_gaps` | test | `tests/test_verify_rom_menu_portrait_lz77_palette_alignment_gaps.py` | — | 0 | 0 |
| `test_verify_rom_mp2k_dispatcher` | test | `tests/test_verify_rom_mp2k_dispatcher.py` | — | 0 | 0 |
| `test_verify_rom_mp2k_note_allocator` | test | `tests/test_verify_rom_mp2k_note_allocator.py` | — | 0 | 0 |
| `test_verify_rom_mplaymain_scheduler_bundle` | test | `tests/test_verify_rom_mplaymain_scheduler_bundle.py` | — | 0 | 0 |
| `test_verify_rom_profile_selector_code_slices` | test | `tests/test_verify_rom_profile_selector_code_slices.py` | — | 0 | 0 |
| `test_verify_rom_psg_frequency_lookup` | test | `tests/test_verify_rom_psg_frequency_lookup.py` | — | 0 | 0 |
| `test_verify_rom_psg_frequency_lookup_bundle` | test | `tests/test_verify_rom_psg_frequency_lookup_bundle.py` | — | 0 | 0 |
| `test_verify_rom_renderer_text_padding` | test | `tests/test_verify_rom_renderer_text_padding.py` | — | 0 | 0 |
| `test_verify_rom_scheduler_callback_lifecycle_gate` | test | `tests/test_verify_rom_scheduler_callback_lifecycle_gate.py` | — | 0 | 0 |
| `test_verify_rom_soundmain_relocated_alignment_gaps` | test | `tests/test_verify_rom_soundmain_relocated_alignment_gaps.py` | — | 0 | 0 |
| `test_verify_rom_soundmain_relocated_cfg` | test | `tests/test_verify_rom_soundmain_relocated_cfg.py` | — | 0 | 0 |
| `test_verify_rom_soundmain_relocated_cfg_bundle` | test | `tests/test_verify_rom_soundmain_relocated_cfg_bundle.py` | — | 0 | 0 |
| `test_verify_rom_sprite_component_source` | test | `tests/test_verify_rom_sprite_component_source.py` | — | 0 | 0 |
| `test_verify_rom_sprite_loader_tail` | test | `tests/test_verify_rom_sprite_loader_tail.py` | — | 0 | 0 |
| `test_verify_rom_task_scheduler_core_bundle` | test | `tests/test_verify_rom_task_scheduler_core_bundle.py` | — | 0 | 0 |
| `test_verify_rom_tile_bg_lz77_palette_alignment_gaps` | test | `tests/test_verify_rom_tile_bg_lz77_palette_alignment_gaps.py` | — | 0 | 0 |
| `test_verify_rom_u8_indexed_u8_triplet_lookup` | test | `tests/test_verify_rom_u8_indexed_u8_triplet_lookup.py` | — | 0 | 0 |
| `test_verify_rom_u8_indexed_u8_triplet_lookup_bundle` | test | `tests/test_verify_rom_u8_indexed_u8_triplet_lookup_bundle.py` | — | 0 | 0 |
| `test_verify_runtime_checkpoint_containers` | test | `tests/test_verify_runtime_checkpoint_containers.py` | — | 0 | 0 |
| `test_verify_save_state_records` | test | `tests/test_verify_save_state_records.py` | — | 0 | 0 |
| `test_verify_similar_table_candidates` | test | `tests/test_verify_similar_table_candidates.py` | — | 0 | 0 |
| `test_verify_world_map_page0_pixel_ab_evidence` | test | `tests/test_verify_world_map_page0_pixel_ab_evidence.py` | — | 0 | 0 |
| `test_vram_lz77_encoder_safety` | test | `tests/test_vram_lz77_encoder_safety.py` | — | 0 | 0 |
| `test_vram_safe_fixed_slot_audits` | test | `tests/test_vram_safe_fixed_slot_audits.py` | — | 0 | 0 |
| `test_world_map_background_relocation_audit` | test | `tests/test_world_map_background_relocation_audit.py` | — | 0 | 0 |

### map（33）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `map-canvases-v1` | artifact | `artifacts/map-canvases-v1` | consumer_contract, map_header_table, rom, scope, unique_resource_counts | 0 | 0 |
| `map-events-e4-handler-pixel-ab-v1` | artifact | `artifacts/map-events-e4-handler-pixel-ab-v1` | files, implementation, scope, verifier | 0 | 0 |
| `map-resource-relocation-v1` | artifact | `artifacts/map-resource-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `map-resource-writeback-v1` | artifact | `artifacts/map-resource-writeback-v1` | files, scope, verifier | 0 | 0 |
| `map-sprites-definition-id1-pixel-ab-v1` | artifact | `artifacts/map-sprites-definition-id1-pixel-ab-v1` | files, implementation, scope, verifier | 0 | 0 |
| `map41-primary-layout-pixel-ab-v1` | artifact | `artifacts/map41-primary-layout-pixel-ab-v1` | files, implementation_sha256, parent, scope, verifier | 0 | 0 |
| `map41-visual-resource-matrix-v1` | artifact | `artifacts/map41-visual-resource-matrix-v1` | files, implementation_sha256, parent, scope, verifier | 0 | 0 |
| `scene-visual-composites-v1` | artifact | `artifacts/scene-visual-composites-v1` | files, scope, verifier | 0 | 0 |
| `scene-visual-packs-v1` | artifact | `artifacts/scene-visual-packs-v1` | consumer_evidence, obj_animation_runtime, obj_selection_chain, rom, scope, source_table, summary | 0 | 0 |
| `scene-visual-transition-timelines-v1` | artifact | `artifacts/scene-visual-transition-timelines-v1` | files, scope, verifier | 0 | 0 |
| `world-map-background-relocation-v1` | artifact | `artifacts/world-map-background-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `world-map-backgrounds-v1` | artifact | `artifacts/world-map-backgrounds-v1` | consumer_evidence, rom, scope, source_tables, summary | 0 | 0 |
| `world-map-gpu-captures` | artifact | `artifacts/world-map-gpu-captures` | — | 0 | 0 |
| `world-map-page0-pixel-ab-v1` | artifact | `artifacts/world-map-page0-pixel-ab-v1` | files, implementation_sha256, parent, raw_files, scope, verifier | 0 | 0 |
| `world-map-runtime-v1` | artifact | `artifacts/world-map-runtime-v1` | capture, page_zero_background, page_zero_label, registers, rom, scope, selection_cursor, static_dependency | 0 | 0 |
| `map-addresses` | note | `notes/map-addresses.md` | — | 0 | 0 |
| `map-canvases-export-20260729` | note | `notes/map-canvases-export-20260729.md` | — | 0 | 0 |
| `map-events-e4-player-visible-20260809` | note | `notes/map-events-e4-player-visible-20260809.md` | — | 0 | 0 |
| `map-format` | note | `notes/map-format.md` | — | 0 | 0 |
| `map-position-pc-probe-20260710` | note | `notes/map-position-pc-probe-20260710.md` | — | 0 | 0 |
| `map-resource-relocation-20260731` | note | `notes/map-resource-relocation-20260731.md` | — | 0 | 0 |
| `map-resource-writeback-20260730` | note | `notes/map-resource-writeback-20260730.md` | — | 0 | 0 |
| `map-sprites-definition-player-visible-20260809` | note | `notes/map-sprites-definition-player-visible-20260809.md` | — | 0 | 0 |
| `map41-primary-layout-pixel-ab-20260801` | note | `notes/map41-primary-layout-pixel-ab-20260801.md` | — | 0 | 0 |
| `map41-visual-resource-matrix-20260801` | note | `notes/map41-visual-resource-matrix-20260801.md` | — | 0 | 0 |
| `maps-runtime-fields-20260711` | note | `notes/maps-runtime-fields-20260711.md` | — | 0 | 0 |
| `scene-visual-composites-export-20260730` | note | `notes/scene-visual-composites-export-20260730.md` | — | 0 | 0 |
| `scene-visual-pack-export-20260729` | note | `notes/scene-visual-pack-export-20260729.md` | — | 0 | 0 |
| `scene-visual-transition-timelines-20260730` | note | `notes/scene-visual-transition-timelines-20260730.md` | — | 0 | 0 |
| `world-map-background-export-20260729` | note | `notes/world-map-background-export-20260729.md` | — | 0 | 0 |
| `world-map-background-relocation-20260731` | note | `notes/world-map-background-relocation-20260731.md` | — | 0 | 0 |
| `world-map-page0-pixel-ab-20260801` | note | `notes/world-map-page0-pixel-ab-20260801.md` | — | 0 | 0 |
| `world-map-runtime-composition-20260729` | note | `notes/world-map-runtime-composition-20260729.md` | — | 0 | 0 |

### other（240）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `data-table-b-message0-pointer-pixel-ab-v1` | artifact | `artifacts/data-table-b-message0-pointer-pixel-ab-v1` | files, implementation, verifier | 0 | 0 |
| `dialogue-font-v2` | artifact | `artifacts/dialogue-font-v2` | byte_table, chapter_intro_mapping, consumer_chain, datasets, localized_mapping_evidence, rom, runtime_expansion, scope, sjis_table, source_format, storage_relationships, visualization_palette | 1 | 0 |
| `direct-image-palette-relocation-v1` | artifact | `artifacts/direct-image-palette-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `generic-sprite-bundle-relocation-v1` | artifact | `artifacts/generic-sprite-bundle-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `initializer-resource-pack-v1` | artifact | `artifacts/initializer-resource-pack-v1` | experiment, files, producer, source, verifier | 0 | 0 |
| `levels-status-per-level-ab-v1` | artifact | `artifacts/levels-status-per-level-ab-v1` | files, implementation, verifier | 0 | 0 |
| `lz77-palette-runtime-v1` | artifact | `artifacts/lz77-palette-runtime-v1` | files, scope, verifier | 0 | 0 |
| `motion-effect-parameter-pixel-ab-v1` | artifact | `artifacts/motion-effect-parameter-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `sappy-engine-master-enable-ab-v1` | artifact | `artifacts/sappy-engine-master-enable-ab-v1` | files, implementation, verifier | 0 | 0 |
| `addresses` | note | `notes/addresses.md` | — | 0 | 0 |
| `alternate-chapter-runtime-probe-20260712` | note | `notes/alternate-chapter-runtime-probe-20260712.md` | — | 0 | 0 |
| `auditor-module-failures-20261020` | note | `notes/auditor-module-failures-20261020.md` | — | 0 | 0 |
| `auto-exit-prevention-mgba-compile-20260806` | note | `notes/auto-exit-prevention-mgba-compile-20260806.md` | — | 0 | 0 |
| `bank-player-visible-closure-plan-20260806` | note | `notes/bank-player-visible-closure-plan-20260806.md` | — | 0 | 0 |
| `build-api-ownership-20260713` | note | `notes/build-api-ownership-20260713.md` | — | 0 | 0 |
| `build-artifact-cleanup-audit-20260729` | note | `notes/build-artifact-cleanup-audit-20260729.md` | — | 0 | 0 |
| `butano-agent-timing-benchmark-20260721` | note | `notes/butano-agent-timing-benchmark-20260721.md` | — | 0 | 0 |
| `butano-battle-architecture-implementation-20260722` | note | `notes/butano-battle-architecture-implementation-20260722.md` | — | 0 | 0 |
| `butano-battle-domain-rewrite-20260723` | note | `notes/butano-battle-domain-rewrite-20260723.md` | — | 0 | 0 |
| `butano-battle-flow-video-review-20260722` | note | `notes/butano-battle-flow-video-review-20260722.md` | — | 0 | 0 |
| `butano-battle-video-frame-analysis-20260722` | note | `notes/butano-battle-video-frame-analysis-20260722.md` | — | 0 | 0 |
| `butano-deployment-runtime-20260721` | note | `notes/butano-deployment-runtime-20260721.md` | — | 0 | 0 |
| `butano-scenario-41-one-to-one-runtime-20260722` | note | `notes/butano-scenario-41-one-to-one-runtime-20260722.md` | — | 0 | 0 |
| `butano-scenario-41-runtime-20260721` | note | `notes/butano-scenario-41-runtime-20260721.md` | — | 0 | 0 |
| `chapter-entry-points` | note | `notes/chapter-entry-points.md` | — | 0 | 0 |
| `chapter-flow-format` | note | `notes/chapter-flow-format.md` | — | 0 | 0 |
| `chapter-flow-runtime-chain-20260712` | note | `notes/chapter-flow-runtime-chain-20260712.md` | — | 0 | 0 |
| `chapter-script-observed-subset-20260713` | note | `notes/chapter-script-observed-subset-20260713.md` | — | 0 | 0 |
| `chapter-script-production-writeback-20260713` | note | `notes/chapter-script-production-writeback-20260713.md` | — | 0 | 0 |
| `codex-reentry-audit-20260712` | note | `notes/codex-reentry-audit-20260712.md` | — | 0 | 0 |
| `current-re-progress-20260711` | note | `notes/current-re-progress-20260711.md` | — | 0 | 0 |
| `d0-bank-exhaustion-gate-20261020` | note | `notes/d0-bank-exhaustion-gate-20261020.md` | — | 0 | 0 |
| `debugging-record` | note | `notes/debugging-record.md` | — | 0 | 0 |
| `dialogue-caller-runtime` | note | `notes/dialogue-caller-runtime.md` | — | 0 | 0 |
| `dialogue-font-atlas-export-20260729` | note | `notes/dialogue-font-atlas-export-20260729.md` | — | 0 | 0 |
| `dialogue-font-table-discovery-20260703` | note | `notes/dialogue-font-table-discovery-20260703.md` | — | 0 | 0 |
| `dialogue-format` | note | `notes/dialogue-format.md` | — | 0 | 0 |
| `dialogue-function-analysis` | note | `notes/dialogue-function-analysis.md` | — | 0 | 0 |
| `dialogue-mapping-blocker-20260702` | note | `notes/dialogue-mapping-blocker-20260702.md` | — | 0 | 0 |
| `dialogue-mapping-decoder-20260702` | note | `notes/dialogue-mapping-decoder-20260702.md` | — | 0 | 0 |
| `dialogue-mapping-progress-20260702` | note | `notes/dialogue-mapping-progress-20260702.md` | — | 0 | 0 |
| `dialogue-memory-analysis` | note | `notes/dialogue-memory-analysis.md` | — | 0 | 0 |
| `dialogue-ram-structures` | note | `notes/dialogue-ram-structures.md` | — | 0 | 0 |
| `dialogue-render-analysis` | note | `notes/dialogue-render-analysis.md` | — | 0 | 0 |
| `dialogue-watch-record-bank` | note | `notes/dialogue-watch-record-bank.md` | — | 0 | 0 |
| `dialogue-watch-sb-struct` | note | `notes/dialogue-watch-sb-struct.md` | — | 0 | 0 |
| `dialogue-watch-vram-glyph` | note | `notes/dialogue-watch-vram-glyph.md` | — | 0 | 0 |
| `dialogue-watch-vram-tilemap` | note | `notes/dialogue-watch-vram-tilemap.md` | — | 0 | 0 |
| `dialogue-watch-wram` | note | `notes/dialogue-watch-wram.md` | — | 0 | 0 |
| `dialogue-write-path` | note | `notes/dialogue-write-path.md` | — | 0 | 0 |
| `dialogue-writer-addresses` | note | `notes/dialogue-writer-addresses.md` | — | 0 | 0 |
| `diff-dialogue-2160-2340-vram` | note | `notes/diff-dialogue-2160-2340-vram.md` | — | 0 | 0 |
| `diff-dialogue-2160-2340-wram` | note | `notes/diff-dialogue-2160-2340-wram.md` | — | 0 | 0 |
| `diff-dialogue-2340-2520-vram` | note | `notes/diff-dialogue-2340-2520-vram.md` | — | 0 | 0 |
| `diff-dialogue-2340-2520-wram` | note | `notes/diff-dialogue-2340-2520-wram.md` | — | 0 | 0 |
| `direct-image-palette-relocation-20260731` | note | `notes/direct-image-palette-relocation-20260731.md` | — | 0 | 0 |
| `directsound-envelope-20260713` | note | `notes/directsound-envelope-20260713.md` | — | 0 | 0 |
| `directsound-mixer-runtime-chain-20260713` | note | `notes/directsound-mixer-runtime-chain-20260713.md` | — | 0 | 0 |
| `directsound-pitch-step-20260713` | note | `notes/directsound-pitch-step-20260713.md` | — | 0 | 0 |
| `directsound-volume-pan-20260713` | note | `notes/directsound-volume-pan-20260713.md` | — | 0 | 0 |
| `dynamic-verification-audit` | note | `notes/dynamic-verification-audit.md` | — | 0 | 0 |
| `editor-isolated-writeback-smoke-20260713` | note | `notes/editor-isolated-writeback-smoke-20260713.md` | — | 0 | 0 |
| `README` | note | `notes/evidence/reverse-proof-update-20261019-v1/first-run-venv-interpreter/README.md` | — | 0 | 0 |
| `三包接入施工单-raw` | note | `notes/evidence/reverse-proof-update-20261020-v2/三包接入施工单-raw.md` | — | 0 | 0 |
| `throughput` | note | `notes/evidence/reverse-throughput-20261019-v1/throughput.md` | — | 0 | 0 |
| `plan` | note | `notes/evidence/reverse-work-plan-20261001-v1/plan.md` | — | 0 | 0 |
| `README` | note | `notes/evidence/rom-animation-pool-lifecycle-20261001-v1/README.md` | — | 0 | 0 |
| `AGENTS` | note | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/AGENTS.md` | — | 0 | 0 |
| `remaining-reverse-work-plan-20261001` | note | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | — | 0 | 0 |
| `reverse-engineering-handoff-current-20260905` | note | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | — | 0 | 0 |
| `reverse-engineering-proof-policy` | note | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md` | — | 0 | 0 |
| `sequel-roadmap` | note | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/sequel-roadmap.md` | — | 0 | 0 |
| `AGENTS` | note | `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/AGENTS.md` | — | 0 | 0 |
| `remaining-reverse-work-plan-20261001` | note | `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | — | 0 | 0 |
| `reverse-engineering-handoff-current-20260905` | note | `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | — | 0 | 0 |
| `sequel-roadmap` | note | `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/sequel-roadmap.md` | — | 0 | 0 |
| `note` | note | `notes/evidence/rom-cutscene-secondary-ptr-shared-lock-20261001-v1/contract-tier1-20261001-v1/note.md` | — | 0 | 0 |
| `AGENTS` | note | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/AGENTS.md` | — | 0 | 0 |
| `remaining-reverse-work-plan-20261001` | note | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | — | 0 | 0 |
| `reverse-engineering-handoff-current-20260905` | note | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | — | 0 | 0 |
| `reverse-engineering-proof-policy` | note | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md` | — | 0 | 0 |
| `sequel-roadmap` | note | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/sequel-roadmap.md` | — | 0 | 0 |
| `AGENTS` | note | `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/AGENTS.md` | — | 0 | 0 |
| `remaining-reverse-work-plan-20261001` | note | `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | — | 0 | 0 |
| `reverse-engineering-handoff-current-20260905` | note | `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | — | 0 | 0 |
| `sequel-roadmap` | note | `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/sequel-roadmap.md` | — | 0 | 0 |
| `AGENTS` | note | `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/AGENTS.md` | — | 0 | 0 |
| `remaining-reverse-work-plan-20261001` | note | `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | — | 0 | 0 |
| `reverse-engineering-handoff-current-20260905` | note | `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | — | 0 | 0 |
| `sequel-roadmap` | note | `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/sequel-roadmap.md` | — | 0 | 0 |
| `AGENTS` | note | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/AGENTS.md` | — | 0 | 0 |
| `remaining-reverse-work-plan-20261001` | note | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | — | 0 | 0 |
| `reverse-engineering-handoff-current-20260905` | note | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | — | 0 | 0 |
| `reverse-engineering-proof-policy` | note | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md` | — | 0 | 0 |
| `sequel-roadmap` | note | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/sequel-roadmap.md` | — | 0 | 0 |
| `note` | note | `notes/evidence/rom-menu-gfx-pointer-ab-20261001-v1/contract-20261001-v1/note.md` | — | 0 | 0 |
| `exporter-root-deletion-incident-20260809` | note | `notes/exporter-root-deletion-incident-20260809.md` | — | 0 | 0 |
| `first-battle-savestate-checkpoints-20260712` | note | `notes/first-battle-savestate-checkpoints-20260712.md` | — | 0 | 0 |
| `four-decisions-20261020` | note | `notes/four-decisions-20261020.md` | — | 0 | 0 |
| `free-space` | note | `notes/free-space.md` | — | 0 | 0 |
| `function-pointer-runtime-probe-20260713` | note | `notes/function-pointer-runtime-probe-20260713.md` | — | 0 | 0 |
| `generic-sprite-bundle-relocation-20260731` | note | `notes/generic-sprite-bundle-relocation-20260731.md` | — | 0 | 0 |
| `group12-natural-entry-ai-observer-20260806` | note | `notes/group12-natural-entry-ai-observer-20260806.md` | — | 0 | 0 |
| `handover-20261020-reverse-tree` | note | `notes/handover-20261020-reverse-tree.md` | — | 0 | 0 |
| `headless-workflow` | note | `notes/headless-workflow.md` | — | 0 | 0 |
| `initializer-resource-pack-export-20260730` | note | `notes/initializer-resource-pack-export-20260730.md` | — | 0 | 0 |
| `legacy-artifact-acceptance-20260905` | note | `notes/legacy-artifact-acceptance-20260905.md` | — | 0 | 0 |
| `legacy-generator-safety-20260711` | note | `notes/legacy-generator-safety-20260711.md` | — | 0 | 0 |
| `levels-runtime-probe-20260713` | note | `notes/levels-runtime-probe-20260713.md` | — | 0 | 0 |
| `line-a-progress-20261019` | note | `notes/line-a-progress-20261019.md` | — | 0 | 0 |
| `live-ledger-identity-repair-20261020` | note | `notes/live-ledger-identity-repair-20261020.md` | — | 0 | 0 |
| `local-mgba-build` | note | `notes/local-mgba-build.md` | — | 0 | 0 |
| `m4a-channel-allocation-20260713` | note | `notes/m4a-channel-allocation-20260713.md` | — | 0 | 0 |
| `m4a-command-vm-20260713` | note | `notes/m4a-command-vm-20260713.md` | — | 0 | 0 |
| `m4a-emulator-differential-20260713` | note | `notes/m4a-emulator-differential-20260713.md` | — | 0 | 0 |
| `m4a-full-song-render-20260713` | note | `notes/m4a-full-song-render-20260713.md` | — | 0 | 0 |
| `m4a-player-slot-control-flow-20260713` | note | `notes/m4a-player-slot-control-flow-20260713.md` | — | 0 | 0 |
| `m4a-player-slot-runtime-differential-20260713` | note | `notes/m4a-player-slot-runtime-differential-20260713.md` | — | 0 | 0 |
| `m4a-runtime-channel-wiring-20260713` | note | `notes/m4a-runtime-channel-wiring-20260713.md` | — | 0 | 0 |
| `m4a-soundmain-scheduler-20260713` | note | `notes/m4a-soundmain-scheduler-20260713.md` | — | 0 | 0 |
| `m4a-track-register-state-20260713` | note | `notes/m4a-track-register-state-20260713.md` | — | 0 | 0 |
| `macos-intel-runtime-preflight-20260715` | note | `notes/macos-intel-runtime-preflight-20260715.md` | — | 0 | 0 |
| `memory-incident-root-cause-20260714` | note | `notes/memory-incident-root-cause-20260714.md` | — | 0 | 0 |
| `mgba-threaded-fastforward-fix` | note | `notes/mgba-threaded-fastforward-fix.md` | — | 0 | 0 |
| `motion-effect-parameter-player-visible-20260809` | note | `notes/motion-effect-parameter-player-visible-20260809.md` | — | 0 | 0 |
| `natural-skill-detail-runtime-20260713` | note | `notes/natural-skill-detail-runtime-20260713.md` | — | 0 | 0 |
| `next-steps` | note | `notes/next-steps.md` | — | 0 | 0 |
| `ninja-tool-addresses` | note | `notes/ninja-tool-addresses.md` | — | 0 | 0 |
| `ocr-dialogue-report` | note | `notes/ocr-dialogue-report.md` | — | 0 | 0 |
| `ocr-longwalk-report` | note | `notes/ocr-longwalk-report.md` | — | 0 | 0 |
| `ocr-newgame-report` | note | `notes/ocr-newgame-report.md` | — | 0 | 0 |
| `offline-e2e-smoke-20260713` | note | `notes/offline-e2e-smoke-20260713.md` | — | 0 | 0 |
| `overlapping-visual-tables-audit-20260712` | note | `notes/overlapping-visual-tables-audit-20260712.md` | — | 0 | 0 |
| `palettes-bank-player-visible-attempt-20260806` | note | `notes/palettes-bank-player-visible-attempt-20260806.md` | — | 0 | 0 |
| `partial-item-inventory` | note | `notes/partial-item-inventory.md` | — | 0 | 0 |
| `partial-random-encounter` | note | `notes/partial-random-encounter.md` | — | 0 | 0 |
| `patch-generator-audit` | note | `notes/patch-generator-audit.md` | — | 0 | 0 |
| `positions-rom-source-20260710` | note | `notes/positions-rom-source-20260710.md` | — | 0 | 0 |
| `profile-text-runtime-probe-20260713` | note | `notes/profile-text-runtime-probe-20260713.md` | — | 0 | 0 |
| `psg-noise-runtime-chain-20260713` | note | `notes/psg-noise-runtime-chain-20260713.md` | — | 0 | 0 |
| `re-completion-audit` | note | `notes/re-completion-audit.md` | — | 0 | 0 |
| `remaining-runtime-bank-probes-20260713` | note | `notes/remaining-runtime-bank-probes-20260713.md` | — | 0 | 0 |
| `resource-locations` | note | `notes/resource-locations.md` | — | 0 | 0 |
| `resource-pointer-alias-correction-20260730` | note | `notes/resource-pointer-alias-correction-20260730.md` | — | 0 | 0 |
| `resource-table-596F98` | note | `notes/resource-table-596F98.md` | — | 0 | 0 |
| `reverse-engineering-current-gaps-20260806` | note | `notes/reverse-engineering-current-gaps-20260806.md` | — | 0 | 0 |
| `reverse-engineering-progress-snapshot-20260802` | note | `notes/reverse-engineering-progress-snapshot-20260802.md` | — | 0 | 0 |
| `reverse-method-review-20261002` | note | `notes/reverse-method-review-20261002.md` | — | 0 | 0 |
| `sappy-engine-master-enable-runtime-20260809` | note | `notes/sappy-engine-master-enable-runtime-20260809.md` | — | 0 | 0 |
| `save-descriptor-layout-correction-20260712` | note | `notes/save-descriptor-layout-correction-20260712.md` | — | 0 | 0 |
| `save-state-wasm-probe-20260711` | note | `notes/save-state-wasm-probe-20260711.md` | — | 0 | 0 |
| `scan-summary` | note | `notes/scan-summary.md` | — | 0 | 0 |
| `similar-tables` | note | `notes/similar-tables.md` | — | 0 | 0 |
| `skill-template-consumer-semantics-20260713` | note | `notes/skill-template-consumer-semantics-20260713.md` | — | 0 | 0 |
| `skill-template-identity-20260711` | note | `notes/skill-template-identity-20260711.md` | — | 0 | 0 |
| `skill-template-ui-probe-20260712` | note | `notes/skill-template-ui-probe-20260712.md` | — | 0 | 0 |
| `staged-artifact-policy-20260905` | note | `notes/staged-artifact-policy-20260905.md` | — | 0 | 0 |
| `static-bank-identity-corrections-20260713` | note | `notes/static-bank-identity-corrections-20260713.md` | — | 0 | 0 |
| `strict-battle-arrival-gate-20260712` | note | `notes/strict-battle-arrival-gate-20260712.md` | — | 0 | 0 |
| `text-and-battle-visual-consumers-20260713` | note | `notes/text-and-battle-visual-consumers-20260713.md` | — | 0 | 0 |
| `text-regions` | note | `notes/text-regions.md` | — | 0 | 0 |
| `tier2-threshold-policy-source-20261020` | note | `notes/tier2-threshold-policy-source-20261020.md` | — | 0 | 0 |
| `tutorial-victory-save-load-runtime-20260712` | note | `notes/tutorial-victory-save-load-runtime-20260712.md` | — | 0 | 0 |
| `u32-pointer-real-writeback-20260710` | note | `notes/u32-pointer-real-writeback-20260710.md` | — | 0 | 0 |
| `unit-id-mapping-analysis` | note | `notes/unit-id-mapping-analysis.md` | — | 0 | 0 |
| `unit-skill-addresses` | note | `notes/unit-skill-addresses.md` | — | 0 | 0 |
| `units-unsafe-table-fix-20260711` | note | `notes/units-unsafe-table-fix-20260711.md` | — | 0 | 0 |
| `unknown-bgm-sfx` | note | `notes/unknown-bgm-sfx.md` | — | 0 | 0 |
| `unknown-item-inventory` | note | `notes/unknown-item-inventory.md` | — | 0 | 0 |
| `unknown-random-encounter` | note | `notes/unknown-random-encounter.md` | — | 0 | 0 |
| `unknown-save-state` | note | `notes/unknown-save-state.md` | — | 0 | 0 |
| `unresolved-lz77-palette-survey-20260730` | note | `notes/unresolved-lz77-palette-survey-20260730.md` | — | 0 | 0 |
| `variable-dialogue-relocation-20260712` | note | `notes/variable-dialogue-relocation-20260712.md` | — | 0 | 0 |
| `vram-safe-lz77-runtime-20260801` | note | `notes/vram-safe-lz77-runtime-20260801.md` | — | 0 | 0 |
| `wasm-formation-navigation-probe-20260710` | note | `notes/wasm-formation-navigation-probe-20260710.md` | — | 0 | 0 |
| `wasm-formation-probe-result-20260710` | note | `notes/wasm-formation-probe-result-20260710.md` | — | 0 | 0 |
| `wasm-runtime-api-audit-20260710` | note | `notes/wasm-runtime-api-audit-20260710.md` | — | 0 | 0 |
| `writeback-experiment-00076D` | note | `notes/writeback-experiment-00076D.md` | — | 0 | 0 |
| `build-pipeline` | doc | `docs/build-pipeline.md` | — | 0 | 0 |
| `butano-konoha-systems-cost` | doc | `docs/butano-konoha-systems-cost.md` | — | 0 | 0 |
| `butano-local-reference` | doc | `docs/butano-local-reference.md` | — | 0 | 0 |
| `butano-scenario-41-battle` | doc | `docs/butano-scenario-41-battle.md` | — | 0 | 0 |
| `codex-goal-comet-governance` | doc | `docs/codex-goal-comet-governance.md` | — | 0 | 0 |
| `codex-mgba-cost-time-audit-20260716` | doc | `docs/codex-mgba-cost-time-audit-20260716.md` | — | 0 | 0 |
| `commit-convention` | doc | `docs/commit-convention.md` | — | 0 | 0 |
| `content-pipeline` | doc | `docs/content-pipeline.md` | — | 0 | 0 |
| `development-status` | doc | `docs/development-status.md` | — | 0 | 0 |
| `editor-emulator-link` | doc | `docs/editor-emulator-link.md` | — | 0 | 0 |
| `experiment-artifact-lifecycle` | doc | `docs/experiment-artifact-lifecycle.md` | — | 0 | 0 |
| `final-completion-report` | doc | `docs/final-completion-report.md` | — | 0 | 0 |
| `legacy-artifact-acceptance-contract-v1` | doc | `docs/legacy-artifact-acceptance-contract-v1.md` | — | 0 | 0 |
| `next-action-plan` | doc | `docs/next-action-plan.md` | — | 0 | 0 |
| `phase3-final-status` | doc | `docs/phase3-final-status.md` | — | 0 | 0 |
| `remaining-reverse-work-plan-20261001` | doc | `docs/remaining-reverse-work-plan-20261001.md` | — | 0 | 0 |
| `reverse-engineering-handoff-20260711` | doc | `docs/reverse-engineering-handoff-20260711.md` | — | 0 | 0 |
| `reverse-engineering-handoff-20260806` | doc | `docs/reverse-engineering-handoff-20260806.md` | — | 0 | 0 |
| `reverse-engineering-handoff-20260807` | doc | `docs/reverse-engineering-handoff-20260807.md` | — | 0 | 0 |
| `reverse-engineering-handoff-20260812` | doc | `docs/reverse-engineering-handoff-20260812.md` | — | 0 | 0 |
| `reverse-engineering-handoff-current-20260905` | doc | `docs/reverse-engineering-handoff-current-20260905.md` | — | 0 | 0 |
| `reverse-engineering-macos-intel-handoff-20260715` | doc | `docs/reverse-engineering-macos-intel-handoff-20260715.md` | — | 0 | 0 |
| `reverse-engineering-midterm-report-20260823` | doc | `docs/reverse-engineering-midterm-report-20260823.md` | — | 0 | 0 |
| `reverse-engineering-proof-policy` | doc | `docs/reverse-engineering-proof-policy.md` | — | 0 | 0 |
| `reverse-engineering-roadmap` | doc | `docs/reverse-engineering-roadmap.md` | — | 0 | 0 |
| `sequel-authoring-workspace` | doc | `docs/sequel-authoring-workspace.md` | — | 0 | 0 |
| `sequel-roadmap` | doc | `docs/sequel-roadmap.md` | — | 0 | 0 |
| `structure-field-semantics` | doc | `docs/structure-field-semantics.md` | — | 0 | 0 |
| `2026-07-14-reverse-engineering-resource-safety` | doc | `docs/superpowers/plans/2026-07-14-reverse-engineering-resource-safety.md` | — | 0 | 0 |
| `2026-07-15-scenario-41-battle-runtime` | doc | `docs/superpowers/plans/2026-07-15-scenario-41-battle-runtime.md` | — | 0 | 0 |
| `2026-07-15-scenario-41-controller-path-probe` | doc | `docs/superpowers/plans/2026-07-15-scenario-41-controller-path-probe.md` | — | 0 | 0 |
| `2026-07-15-scenario-41-lineup-to-controller` | doc | `docs/superpowers/plans/2026-07-15-scenario-41-lineup-to-controller.md` | — | 0 | 0 |
| `2026-07-16-project-completion-policy-alignment` | doc | `docs/superpowers/plans/2026-07-16-project-completion-policy-alignment.md` | — | 0 | 0 |
| `2026-07-16-project-policy-audit-repair` | doc | `docs/superpowers/plans/2026-07-16-project-policy-audit-repair.md` | — | 0 | 0 |
| `2026-07-17-macos-mgba-gdb-ownership` | doc | `docs/superpowers/plans/2026-07-17-macos-mgba-gdb-ownership.md` | — | 0 | 0 |
| `2026-07-17-mgba-safe-script-termination` | doc | `docs/superpowers/plans/2026-07-17-mgba-safe-script-termination.md` | — | 0 | 0 |
| `2026-07-17-scenario-41-active-current-unit-observer` | doc | `docs/superpowers/plans/2026-07-17-scenario-41-active-current-unit-observer.md` | — | 0 | 0 |
| `2026-07-18-direct-reverse-engineering-critical-path` | doc | `docs/superpowers/plans/2026-07-18-direct-reverse-engineering-critical-path.md` | — | 0 | 0 |
| `2026-07-19-mgba-runtime-safety` | doc | `docs/superpowers/plans/2026-07-19-mgba-runtime-safety.md` | — | 0 | 0 |
| `2026-07-21-butano-foundation-research` | doc | `docs/superpowers/plans/2026-07-21-butano-foundation-research.md` | — | 0 | 0 |
| `2026-07-21-butano-scenario-41-battle` | doc | `docs/superpowers/plans/2026-07-21-butano-scenario-41-battle.md` | — | 0 | 0 |
| `2026-07-21-codex-agent-timing-benchmark` | doc | `docs/superpowers/plans/2026-07-21-codex-agent-timing-benchmark.md` | — | 0 | 0 |
| `2026-07-22-butano-battle-system-implementation` | doc | `docs/superpowers/plans/2026-07-22-butano-battle-system-implementation.md` | — | 0 | 0 |
| `2026-07-22-butano-scenario-41-reference-capture` | doc | `docs/superpowers/plans/2026-07-22-butano-scenario-41-reference-capture.md` | — | 0 | 0 |
| `2026-07-23-battle-controller-checkpoint-binding` | doc | `docs/superpowers/plans/2026-07-23-battle-controller-checkpoint-binding.md` | — | 0 | 0 |
| `2026-07-14-reverse-engineering-resource-safety-design` | doc | `docs/superpowers/specs/2026-07-14-reverse-engineering-resource-safety-design.md` | — | 0 | 0 |
| `2026-07-15-scenario-41-battle-runtime-design` | doc | `docs/superpowers/specs/2026-07-15-scenario-41-battle-runtime-design.md` | — | 0 | 0 |
| `2026-07-15-scenario-41-controller-path-probe-design` | doc | `docs/superpowers/specs/2026-07-15-scenario-41-controller-path-probe-design.md` | — | 0 | 0 |
| `2026-07-15-scenario-41-prebattle-to-controller-design` | doc | `docs/superpowers/specs/2026-07-15-scenario-41-prebattle-to-controller-design.md` | — | 0 | 0 |
| `2026-07-16-project-completion-policy-alignment-design` | doc | `docs/superpowers/specs/2026-07-16-project-completion-policy-alignment-design.md` | — | 0 | 0 |
| `2026-07-16-scenario-41-animated-snapshot-stability-design` | doc | `docs/superpowers/specs/2026-07-16-scenario-41-animated-snapshot-stability-design.md` | — | 0 | 0 |
| `2026-07-17-macos-mgba-gdb-ownership-design` | doc | `docs/superpowers/specs/2026-07-17-macos-mgba-gdb-ownership-design.md` | — | 0 | 0 |
| `2026-07-17-mgba-safe-script-termination-design` | doc | `docs/superpowers/specs/2026-07-17-mgba-safe-script-termination-design.md` | — | 0 | 0 |
| `2026-07-17-scenario-41-active-current-unit-observer-design` | doc | `docs/superpowers/specs/2026-07-17-scenario-41-active-current-unit-observer-design.md` | — | 0 | 0 |
| `2026-07-19-mgba-runtime-safety-design` | doc | `docs/superpowers/specs/2026-07-19-mgba-runtime-safety-design.md` | — | 0 | 0 |
| `2026-07-21-butano-foundation-research-design` | doc | `docs/superpowers/specs/2026-07-21-butano-foundation-research-design.md` | — | 0 | 0 |
| `2026-07-21-butano-scenario-41-battle-design` | doc | `docs/superpowers/specs/2026-07-21-butano-scenario-41-battle-design.md` | — | 0 | 0 |
| `2026-07-21-codex-agent-timing-benchmark-design` | doc | `docs/superpowers/specs/2026-07-21-codex-agent-timing-benchmark-design.md` | — | 0 | 0 |
| `2026-07-22-butano-battle-system-architecture-design` | doc | `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md` | — | 0 | 0 |
| `2026-07-22-butano-scenario-41-one-to-one-design` | doc | `docs/superpowers/specs/2026-07-22-butano-scenario-41-one-to-one-design.md` | — | 0 | 0 |
| `testing-checklist` | doc | `docs/testing-checklist.md` | — | 0 | 0 |
| `web-editor-spec` | doc | `docs/web-editor-spec.md` | — | 0 | 0 |

### overview（3）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `e2e` | artifact | `artifacts/e2e` | — | 0 | 0 |
| `overview-gradient-overlay-v1` | artifact | `artifacts/overview-gradient-overlay-v1` | files, producer, source, verifier | 0 | 0 |
| `overview-gradient-overlay-export-20260730` | note | `notes/overview-gradient-overlay-export-20260730.md` | — | 0 | 0 |

### presentation（29）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `cutscene-obj-bundle-relocation-v1` | artifact | `artifacts/cutscene-obj-bundle-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `cutscene-obj-id1-pixel-ab-v1` | artifact | `artifacts/cutscene-obj-id1-pixel-ab-v1` | files, implementation_sha256, parent, raw_files, scope, verifier | 0 | 0 |
| `cutscene-obj-id1-primary-ptr-ab-v1` | artifact | `artifacts/cutscene-obj-id1-primary-ptr-ab-v1` | files, implementation, verifier | 0 | 0 |
| `cutscene-obj-v1` | artifact | `artifacts/cutscene-obj-v1` | animation_runtime, consumer, consumer_evidence, resource_table, rom, scope, sprite_table | 0 | 0 |
| `menu-portrait-pixel-ab-v1` | artifact | `artifacts/menu-portrait-pixel-ab-v1` | files, implementation_sha256, parent, raw_files, scope, verifier | 0 | 0 |
| `menu-portrait-relocation-v1` | artifact | `artifacts/menu-portrait-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `menu-portrait-writeback-v1` | artifact | `artifacts/menu-portrait-writeback-v1` | files, scope, verifier | 0 | 0 |
| `menu-portraits-v1` | artifact | `artifacts/menu-portraits-v1` | canvas, rom, source_table | 0 | 0 |
| `portrait-palette-producers-v1` | artifact | `artifacts/portrait-palette-producers-v1` | files, producer, scope, source, verifier | 0 | 0 |
| `story-scene-layer-bindings-v1` | artifact | `artifacts/story-scene-layer-bindings-v1` | rom, scope, selection, source_artifacts, timing | 0 | 0 |
| `story-scene-timelines-v1` | artifact | `artifacts/story-scene-timelines-v1` | controller_timing, rom, scope, source_artifacts | 0 | 0 |
| `story-visual-layers-v1` | artifact | `artifacts/story-visual-layers-v1` | linked_visual_descriptor_bank, rom, runtime_layout, source_table | 0 | 0 |
| `story-visual-resource-relocation-v1` | artifact | `artifacts/story-visual-resource-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `story-visual-resource-sources-v1` | artifact | `artifacts/story-visual-resource-sources-v1` | files, scope, summary, verifier | 0 | 0 |
| `cutscene-obj-bundle-relocation-20260731` | note | `notes/cutscene-obj-bundle-relocation-20260731.md` | — | 0 | 0 |
| `cutscene-obj-export-20260729` | note | `notes/cutscene-obj-export-20260729.md` | — | 0 | 0 |
| `cutscene-visual-resource-consumer-20260712` | note | `notes/cutscene-visual-resource-consumer-20260712.md` | — | 0 | 0 |
| `cutscene-visual-resource-player-visible-20260809` | note | `notes/cutscene-visual-resource-player-visible-20260809.md` | — | 0 | 0 |
| `menu-portrait-export-20260729` | note | `notes/menu-portrait-export-20260729.md` | — | 0 | 0 |
| `menu-portrait-pixel-ab-20260801` | note | `notes/menu-portrait-pixel-ab-20260801.md` | — | 0 | 0 |
| `menu-portrait-relocation-20260731` | note | `notes/menu-portrait-relocation-20260731.md` | — | 0 | 0 |
| `menu-portrait-writeback-20260730` | note | `notes/menu-portrait-writeback-20260730.md` | — | 0 | 0 |
| `portrait-palette-producers-20260730` | note | `notes/portrait-palette-producers-20260730.md` | — | 0 | 0 |
| `story-bank-identity-correction-20260712` | note | `notes/story-bank-identity-correction-20260712.md` | — | 0 | 0 |
| `story-scene-layer-bindings-20260729` | note | `notes/story-scene-layer-bindings-20260729.md` | — | 0 | 0 |
| `story-scene-timelines-export-20260729` | note | `notes/story-scene-timelines-export-20260729.md` | — | 0 | 0 |
| `story-visual-descriptor-consumer-20260712` | note | `notes/story-visual-descriptor-consumer-20260712.md` | — | 0 | 0 |
| `story-visual-layer-export-20260729` | note | `notes/story-visual-layer-export-20260729.md` | — | 0 | 0 |
| `story-visual-resource-relocation-20260731` | note | `notes/story-visual-resource-relocation-20260731.md` | — | 0 | 0 |

### residual（23）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `residual-lz77-graphics-relocation-v1` | artifact | `artifacts/residual-lz77-graphics-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `residual-text-bg-tilemap-relocation-v1` | artifact | `artifacts/residual-text-bg-tilemap-relocation-v1` | files, implementation, scope, summary, verifier | 0 | 0 |
| `residual-text-bg-tilemap-resource-ownership-v1` | artifact | `artifacts/residual-text-bg-tilemap-resource-ownership-v1` | files, implementation, scope, summary, verifier | 0 | 0 |
| `residual-wram-crop-tilemap-runtime-v1` | artifact | `artifacts/residual-wram-crop-tilemap-runtime-v1` | files, implementation, scope, verifier | 0 | 0 |
| `residual-wram-derived-tilemap-relocation-v1` | artifact | `artifacts/residual-wram-derived-tilemap-relocation-v1` | files, implementation, scope, summary, verifier | 0 | 0 |
| `residual-wram-tilemap-abi-v1` | artifact | `artifacts/residual-wram-tilemap-abi-v1` | files, implementation, scope, summary, verifier | 0 | 0 |
| `residual-wram-tilemap-pixel-ab-v1` | artifact | `artifacts/residual-wram-tilemap-pixel-ab-v1` | files, implementation_sha256, parent, scope, verifier | 0 | 0 |
| `residual-wram-tilemap-relocation-v1` | artifact | `artifacts/residual-wram-tilemap-relocation-v1` | files, implementation, scope, summary, verifier | 0 | 0 |
| `residual-wram-tilemap-resource-ownership-v1` | artifact | `artifacts/residual-wram-tilemap-resource-ownership-v1` | files, implementation, scope, summary, verifier | 0 | 0 |
| `residual-wram-tilemap-runtime-v1` | artifact | `artifacts/residual-wram-tilemap-runtime-v1` | files, implementation, scope, verifier | 0 | 0 |
| `residual-wram-tilemap-runtime-v2` | artifact | `artifacts/residual-wram-tilemap-runtime-v2` | files, implementation, scope, verifier | 0 | 0 |
| `residual-wram-transformed-tilemap-runtime-v1` | artifact | `artifacts/residual-wram-transformed-tilemap-runtime-v1` | files, implementation, scope, verifier | 0 | 0 |
| `residual-wram-visual-metadata-abi-v2` | artifact | `artifacts/residual-wram-visual-metadata-abi-v2` | files, implementation, scope, summary, verifier | 0 | 0 |
| `residual-lz77-graphics-relocation-20260731` | note | `notes/residual-lz77-graphics-relocation-20260731.md` | — | 0 | 0 |
| `residual-text-bg-tilemap-relocation-20260731` | note | `notes/residual-text-bg-tilemap-relocation-20260731.md` | — | 0 | 0 |
| `residual-text-bg-tilemap-resource-ownership-20260731` | note | `notes/residual-text-bg-tilemap-resource-ownership-20260731.md` | — | 0 | 0 |
| `residual-wram-derived-tilemap-relocation-20260731` | note | `notes/residual-wram-derived-tilemap-relocation-20260731.md` | — | 0 | 0 |
| `residual-wram-tilemap-abi-20260731` | note | `notes/residual-wram-tilemap-abi-20260731.md` | — | 0 | 0 |
| `residual-wram-tilemap-pixel-ab-20260801` | note | `notes/residual-wram-tilemap-pixel-ab-20260801.md` | — | 0 | 0 |
| `residual-wram-tilemap-relocation-20260731` | note | `notes/residual-wram-tilemap-relocation-20260731.md` | — | 0 | 0 |
| `residual-wram-tilemap-resource-ownership-20260731` | note | `notes/residual-wram-tilemap-resource-ownership-20260731.md` | — | 0 | 0 |
| `residual-wram-tilemap-runtime-reachability-20260731` | note | `notes/residual-wram-tilemap-runtime-reachability-20260731.md` | — | 0 | 0 |
| `residual-wram-transformed-tilemap-runtime-20260801` | note | `notes/residual-wram-transformed-tilemap-runtime-20260801.md` | — | 0 | 0 |

### rom（252）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `rom-alternate-dialogue-table-v1` | artifact | `artifacts/rom-alternate-dialogue-table-v1` | files, historical_coverage_reference, producer | 0 | 0 |
| `rom-animation-descriptor-pool-v2` | artifact | `artifacts/rom-animation-descriptor-pool-v2` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-battle-condition-records-v1` | artifact | `artifacts/rom-battle-condition-records-v1` | files, implementation, producer, rom, scope, verifier | 0 | 0 |
| `rom-battle-condition-result-text-v1` | artifact | `artifacts/rom-battle-condition-result-text-v1` | files, implementation | 0 | 0 |
| `rom-battle-controller-cfg-v1` | artifact | `artifacts/rom-battle-controller-cfg-v1` | controller, dispatch_summary, extension_summary, files, implementation, rom | 0 | 0 |
| `rom-battle-controller-consumed-literals-v1` | artifact | `artifacts/rom-battle-controller-consumed-literals-v1` | coverage_baseline, coverage_projection, files, literal_denominator, overlap_baseline, promotion, rom, scope, source_artifact, source_denominator, summary, verifier | 0 | 0 |
| `rom-battle-distance-dispatcher-cfg-v1` | artifact | `artifacts/rom-battle-distance-dispatcher-cfg-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-battle-message-text-inventory-v1` | artifact | `artifacts/rom-battle-message-text-inventory-v1` | files, producer, scope, verification | 0 | 0 |
| `rom-battle-sound-selector-v1` | artifact | `artifacts/rom-battle-sound-selector-v1` | files, implementation, producer, rom, scope, verifier | 0 | 0 |
| `rom-battle-status-bar-caller-slice-v1` | artifact | `artifacts/rom-battle-status-bar-caller-slice-v1` | coverage, files, producer, source, verification | 0 | 0 |
| `rom-boot-copy-sources-v1` | artifact | `artifacts/rom-boot-copy-sources-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-boot-framebuffers-v1` | artifact | `artifacts/rom-boot-framebuffers-v1` | boot_chain, implementation, padding, rom, scope, startup_chain, summary | 0 | 0 |
| `rom-boot-interwork-continuation-precoverage-v1` | artifact | `artifacts/rom-boot-interwork-continuation-precoverage-v1` | files | 0 | 0 |
| `rom-boot-interwork-continuation-v1` | artifact | `artifacts/rom-boot-interwork-continuation-v1` | coverage_baseline, coverage_denominator, current_unknown_owner, decoder, files, implementation, official_boot_interwork_artifact, producer, promotion, rom, scope, summary, verification | 0 | 0 |
| `rom-boot-interwork-v1` | artifact | `artifacts/rom-boot-interwork-v1` | files, producer, rom, scope, summary, verification | 0 | 0 |
| `rom-boot-register-init-dependency-cfg-v1` | artifact | `artifacts/rom-boot-register-init-dependency-cfg-v1` | cfg_inventory, coverage_projection, files, implementation, precoverage, producer, producer_owner, promotion, rom, scope, verifier | 0 | 0 |
| `rom-boot-state-dispatcher-cfg-v1` | artifact | `artifacts/rom-boot-state-dispatcher-cfg-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-boot-thumb-handoff-cfg-v1` | artifact | `artifacts/rom-boot-thumb-handoff-cfg-v1` | coverage_baseline, files, handoff, implementation, producer, promotion, rom, scope, summary, verification, verifier | 0 | 0 |
| `rom-bounded-index-u16-pair-table-v1` | artifact | `artifacts/rom-bounded-index-u16-pair-table-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-cfg-inventory-v2` | artifact | `artifacts/rom-cfg-inventory-v2` | decoder, files, implementation, limits, rom, scope, seed_artifact, summary | 0 | 0 |
| `rom-cfg-inventory-v3` | artifact | `artifacts/rom-cfg-inventory-v3` | base_cfg, combined_summary, decoder, extension_policy, extension_summary, files, implementation, limits, rom, scope, static_dispatch_summary | 0 | 0 |
| `rom-cfg-proven-roots-batch-consumed-literals-v1` | artifact | `artifacts/rom-cfg-proven-roots-batch-consumed-literals-v1` | coverage_baseline, coverage_projection, denominator, files, promotion, rom, scope, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v1` | artifact | `artifacts/rom-cfg-proven-roots-v1` | cross_edge_summary, decoder, extension_summary, files, frozen_baseline, implementation, limits, producer_summary, rom, scope | 0 | 0 |
| `rom-cfg-proven-roots-v10` | artifact | `artifacts/rom-cfg-proven-roots-v10` | coverage_baseline, files, implementation, producer, promotion, rom, scope, source, target, upstream, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v11` | artifact | `artifacts/rom-cfg-proven-roots-v11` | coverage_baseline, files, implementation, producer, producer_denominator, promotion, rom, scope, source, target, upstream, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v12` | artifact | `artifacts/rom-cfg-proven-roots-v12` | coverage_baseline, files, implementation, producer, producer_denominator, promotion, rom, scope, source, target, upstream, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v13` | artifact | `artifacts/rom-cfg-proven-roots-v13` | coverage_baseline, files, implementation, producer, producer_denominator, promotion, rom, scope, source, target, upstream, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v14` | artifact | `artifacts/rom-cfg-proven-roots-v14` | coverage_baseline, files, implementation, producer, promotion, rom, scope, upstream, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v15` | artifact | `artifacts/rom-cfg-proven-roots-v15` | excluded_source_candidate, files, implementation, producer, promotion, rom, scope, upstream, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v16` | artifact | `artifacts/rom-cfg-proven-roots-v16` | coverage_baseline, files, implementation, producer, rom, scope, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v16-consumed-literals-v1` | artifact | `artifacts/rom-cfg-proven-roots-v16-consumed-literals-v1` | coverage_baseline, coverage_projection, files, implementation, literal_denominator, promotion, rom, scope, source_artifact, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v17` | artifact | `artifacts/rom-cfg-proven-roots-v17` | coverage_projection, files, implementation, precoverage, producer, promotion, rom, scope, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v17-precoverage-v1` | artifact | `artifacts/rom-cfg-proven-roots-v17-precoverage-v1` | files, scope | 0 | 0 |
| `rom-cfg-proven-roots-v18` | artifact | `artifacts/rom-cfg-proven-roots-v18` | coverage_projection, files, implementation, precoverage, producer, promotion, rom, scope, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v18-precoverage-v1` | artifact | `artifacts/rom-cfg-proven-roots-v18-precoverage-v1` | files | 0 | 0 |
| `rom-cfg-proven-roots-v19` | artifact | `artifacts/rom-cfg-proven-roots-v19` | coverage_projection, dependency_dag, files, implementation, precoverage, producer, promotion, rom, scope, upstream_continuation_artifact, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v2` | artifact | `artifacts/rom-cfg-proven-roots-v2` | cross_edge_summary, decoder, extension_summary, files, frozen_baseline, implementation, limits, producer_summary, rom, scope | 0 | 0 |
| `rom-cfg-proven-roots-v20` | artifact | `artifacts/rom-cfg-proven-roots-v20` | coverage_projection, files, implementation, precoverage, producer, promotion, rom, scope, story_overlay, upstream_continuation_artifact, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v21` | artifact | `artifacts/rom-cfg-proven-roots-v21` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-cfg-proven-roots-v3` | artifact | `artifacts/rom-cfg-proven-roots-v3` | extension_summary, files, producer_summary, rom | 0 | 0 |
| `rom-cfg-proven-roots-v4` | artifact | `artifacts/rom-cfg-proven-roots-v4` | extension_summary, files, producer_summary, rom | 0 | 0 |
| `rom-cfg-proven-roots-v5` | artifact | `artifacts/rom-cfg-proven-roots-v5` | extension_summary, files, producer_summary, rom | 0 | 0 |
| `rom-cfg-proven-roots-v6` | artifact | `artifacts/rom-cfg-proven-roots-v6` | extension_summary, files, producer_summary, rom | 0 | 0 |
| `rom-cfg-proven-roots-v7` | artifact | `artifacts/rom-cfg-proven-roots-v7` | dispatcher_summary, extension_summary, files, rom | 0 | 0 |
| `rom-cfg-proven-roots-v8` | artifact | `artifacts/rom-cfg-proven-roots-v8` | extension_summary, files, frozen_baseline, implementation, producer_summary, promotion, rom, scope, source | 0 | 0 |
| `rom-cfg-proven-roots-v9` | artifact | `artifacts/rom-cfg-proven-roots-v9` | coverage_baseline, extension_summary, files, frozen_baseline, implementation, producer, producer_summary, promotion, rom, scope, source, verifier | 0 | 0 |
| `rom-cfg-seeds-v1` | artifact | `artifacts/rom-cfg-seeds-v1` | files, implementation, rom, scope, summary | 0 | 0 |
| `rom-cfg-v1-consumed-literals-v1` | artifact | `artifacts/rom-cfg-v1-consumed-literals-v1` | coverage_baseline, coverage_projection, files, literal_denominator, promotion, rom, scope, source_artifact, summary, verifier | 0 | 0 |
| `rom-cfg-v2-consumed-literals-v1` | artifact | `artifacts/rom-cfg-v2-consumed-literals-v1` | coverage_baseline, coverage_projection, files, literal_denominator, promotion, rom, scope, source_artifact, summary, verifier | 0 | 0 |
| `rom-cfg-v2-shadowed-consumed-literals-v1` | artifact | `artifacts/rom-cfg-v2-shadowed-consumed-literals-v1` | coverage_baseline, coverage_projection, files, literal_denominator, prior_packets, promotion, rom, scope, source_artifact, source_denominator, summary, v3_shadow_evidence, verifier | 0 | 0 |
| `rom-cfg-v3-consumed-literals-v1` | artifact | `artifacts/rom-cfg-v3-consumed-literals-v1` | coverage_baseline, coverage_projection, files, literal_denominator, promotion, rom, scope, source_artifact, summary, verifier | 0 | 0 |
| `rom-cfg-v6-consumed-literals-v1` | artifact | `artifacts/rom-cfg-v6-consumed-literals-v1` | coverage_baseline, coverage_projection, files, literal_denominator, promotion, rom, scope, source_artifact, summary, verifier | 0 | 0 |
| `rom-cgb-audio-precoverage-v1` | artifact | `artifacts/rom-cgb-audio-precoverage-v1` | coverage, recovery | 0 | 0 |
| `rom-cgb-helper-bounded-cfg-v1` | artifact | `artifacts/rom-cgb-helper-bounded-cfg-v1` | acceptance, files, verification, verifier | 0 | 0 |
| `rom-cgbsound-bounded-cfg-v1` | artifact | `artifacts/rom-cgbsound-bounded-cfg-v1` | acceptance, files, verification, verifier | 0 | 0 |
| `rom-chapter-script-consumer-roots-v1` | artifact | `artifacts/rom-chapter-script-consumer-roots-v1` | files, implementation, promotion | 0 | 0 |
| `rom-chapter-script-inventory-v1` | artifact | `artifacts/rom-chapter-script-inventory-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-chapter-script-unbound-tail-v1` | artifact | `artifacts/rom-chapter-script-unbound-tail-v1` | files, implementation, promotion | 0 | 0 |
| `rom-chapter-selector-code-slice-v1` | artifact | `artifacts/rom-chapter-selector-code-slice-v1` | coverage, files, producer, source, verification | 0 | 0 |
| `rom-cutscene-obj-source-ranges-v1` | artifact | `artifacts/rom-cutscene-obj-source-ranges-v1` | files, producer, rom, scope, source_identity, verifier | 0 | 0 |
| `rom-dialogue-padding-inventory-v1` | artifact | `artifacts/rom-dialogue-padding-inventory-v1` | files, implementation, rom, scope, source_artifact, summary, verifier | 0 | 0 |
| `rom-dialogue-text-inventory-v1` | artifact | `artifacts/rom-dialogue-text-inventory-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-direct-cpuset-gpu-inventory-v1` | artifact | `artifacts/rom-direct-cpuset-gpu-inventory-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-direct-dma-gpu-inventory-v1` | artifact | `artifacts/rom-direct-dma-gpu-inventory-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-directsound-pitch-lookup-v1` | artifact | `artifacts/rom-directsound-pitch-lookup-v1` | coverage_baseline, coverage_projection, files, implementation, producer, promotion, rom, scope, verification, verifier | 0 | 0 |
| `rom-display-text-delta-v1` | artifact | `artifacts/rom-display-text-delta-v1` | files, verifier | 0 | 0 |
| `rom-event-handler-cfg-v1` | artifact | `artifacts/rom-event-handler-cfg-v1` | cfg, coverage_baseline, files, implementation, producer, producer_denominator, promotion, rom, scope, verifier | 0 | 0 |
| `rom-expansion-profile-v1` | artifact | `artifacts/rom-expansion-profile-v1` | files, scope, summary, verifier | 0 | 0 |
| `rom-fast-audit-four-packet-baseline-v1` | artifact | `artifacts/rom-fast-audit-four-packet-baseline-v1` | files, scope | 0 | 0 |
| `rom-fixed-animation-descriptor-groups-v1` | artifact | `artifacts/rom-fixed-animation-descriptor-groups-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-fixed-consumer-text-inventory-v1` | artifact | `artifacts/rom-fixed-consumer-text-inventory-v1` | files, producer, scope, verification | 0 | 0 |
| `rom-fixed-index-u8-tail-v1` | artifact | `artifacts/rom-fixed-index-u8-tail-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-fixed-pair-tables-v1` | artifact | `artifacts/rom-fixed-pair-tables-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-fixed-renderer-script-records-v1` | artifact | `artifacts/rom-fixed-renderer-script-records-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-gpu-copy-queue-inventory-v1` | artifact | `artifacts/rom-gpu-copy-queue-inventory-v1` | files, producer, scope, source, verifier | 0 | 0 |
| `rom-legacy-acceptance-20260905-v1` | artifact | `artifacts/rom-legacy-acceptance-20260905-v1` | files, producer, scope, summary, verifier | 0 | 0 |
| `rom-low-script-delta-v1` | artifact | `artifacts/rom-low-script-delta-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-m4a-byte-inventory-v1` | artifact | `artifacts/rom-m4a-byte-inventory-v1` | base_rom, dense_audio_window, producer, semantic_class_bytes, semantic_class_counts, summary | 0 | 0 |
| `rom-m4a-initializer-chain-precoverage-v1` | artifact | `artifacts/rom-m4a-initializer-chain-precoverage-v1` | coverage, recovery | 0 | 0 |
| `rom-m4a-initializer-chain-v1` | artifact | `artifacts/rom-m4a-initializer-chain-v1` | acceptance, coverage_baseline, coverage_baseline_source, coverage_projection, files, gap_exclusion, implementation, producer, producer_denominator, promotion, rom, scope, semantic_contract, summary, upstream_receipts, verification, verifier | 0 | 0 |
| `rom-menu-portrait-palette-inventory-v1` | artifact | `artifacts/rom-menu-portrait-palette-inventory-v1` | files, producer, scope, source, verifier | 0 | 0 |
| `rom-mp2k-dispatcher-precoverage-v1` | artifact | `artifacts/rom-mp2k-dispatcher-precoverage-v1` | coverage, recovery | 0 | 0 |
| `rom-mp2k-dispatcher-v1` | artifact | `artifacts/rom-mp2k-dispatcher-v1` | acceptance, coverage_baseline, coverage_baseline_source, coverage_projection, dispatcher, files, implementation, initializer_binding, producer, producer_denominator, promotion, provenance, rom, scope, semantic_contract, summary, upstream_receipts, verification, verifier | 0 | 0 |
| `rom-mp2k-note-allocator-precoverage-v1` | artifact | `artifacts/rom-mp2k-note-allocator-precoverage-v1` | coverage, recovery | 0 | 0 |
| `rom-mp2k-note-allocator-v1` | artifact | `artifacts/rom-mp2k-note-allocator-v1` | acceptance, coverage_baseline, coverage_baseline_source, coverage_projection, entry_pointer, files, implementation, producer, producer_denominator, promotion, rom, scope, semantic_contract, summary, upstream_receipts, verification, verifier | 0 | 0 |
| `rom-mplaymain-scheduler-v1` | artifact | `artifacts/rom-mplaymain-scheduler-v1` | coverage_baseline, entry_proof, files, implementation, producer, promotion, provenance_inputs, rom, scope, summary, verification, verifier | 0 | 0 |
| `rom-parser-bound-zero-padding-v1` | artifact | `artifacts/rom-parser-bound-zero-padding-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-pointer-lz77-graphics-v1` | artifact | `artifacts/rom-pointer-lz77-graphics-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-pointer-lz77-inventory-v1` | artifact | `artifacts/rom-pointer-lz77-inventory-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-positions-aux-dispatch-v1` | artifact | `artifacts/rom-positions-aux-dispatch-v1` | denominator, files, payload, producer, rom, summary, verification | 0 | 0 |
| `rom-post-story-dependency-precoverage-v1` | artifact | `artifacts/rom-post-story-dependency-precoverage-v1` | files, implementation, source | 0 | 0 |
| `rom-prebattle-menu-controller-cfg-v1` | artifact | `artifacts/rom-prebattle-menu-controller-cfg-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-profile-selector-code-slices-v1` | artifact | `artifacts/rom-profile-selector-code-slices-v1` | coverage, files, producer, source, verification | 0 | 0 |
| `rom-profile-text-inventory-v1` | artifact | `artifacts/rom-profile-text-inventory-v1` | files, verification | 0 | 0 |
| `rom-psg-frequency-lookup-v1` | artifact | `artifacts/rom-psg-frequency-lookup-v1` | coverage_baseline, coverage_projection, files, implementation, producer, promotion, rom, scope, verification, verifier | 0 | 0 |
| `rom-referenced-text-slot-padding-v1` | artifact | `artifacts/rom-referenced-text-slot-padding-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-renderer-records-delta-v1` | artifact | `artifacts/rom-renderer-records-delta-v1` | files, verifier | 0 | 0 |
| `rom-renderer-script-pointer-pool-records-v1` | artifact | `artifacts/rom-renderer-script-pointer-pool-records-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-renderer-text-inventory-v1` | artifact | `artifacts/rom-renderer-text-inventory-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-scene-source-closures-v1` | artifact | `artifacts/rom-scene-source-closures-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-scene-source-four-packet-precoverage-v1` | artifact | `artifacts/rom-scene-source-four-packet-precoverage-v1` | files, implementation, producer, recovery | 0 | 0 |
| `rom-scene-visual-source-ranges-v1` | artifact | `artifacts/rom-scene-visual-source-ranges-v1` | coverage_baseline, files, producer, rom, scope, source_identity, verifier | 0 | 0 |
| `rom-selector-code-windows-v1` | artifact | `artifacts/rom-selector-code-windows-v1` | coverage, files, producer, rom, scope, upstream, verification | 0 | 0 |
| `rom-selector-direct-source-records-v1` | artifact | `artifacts/rom-selector-direct-source-records-v1` | files, producer, rom, scope, upstream, verification | 0 | 0 |
| `rom-selector-text-bindings-v1` | artifact | `artifacts/rom-selector-text-bindings-v1` | files, producer, scope, verification | 0 | 0 |
| `rom-small-cfg-dependency-batch-v1` | artifact | `artifacts/rom-small-cfg-dependency-batch-v1` | files, verifier | 0 | 0 |
| `rom-soundmain-relocated-cfg-v1` | artifact | `artifacts/rom-soundmain-relocated-cfg-v1` | acceptance, copy_operation, coverage_baseline, files, implementation, producer, producer_denominator, promotion, rom, scope, source, summary, verification, verifier | 0 | 0 |
| `rom-sprite-component-source-v1` | artifact | `artifacts/rom-sprite-component-source-v1` | coverage_baseline, files, producer, rom, scope, verification | 0 | 0 |
| `rom-sprite-loader-tail-v1` | artifact | `artifacts/rom-sprite-loader-tail-v1` | coverage, files, producer, source, verification | 0 | 0 |
| `rom-staged-gpu-copy-inventory-v1` | artifact | `artifacts/rom-staged-gpu-copy-inventory-v1` | files, producer, scope, source, verifier | 0 | 0 |
| `rom-story-callback-dependency-closures-precoverage-v1` | artifact | `artifacts/rom-story-callback-dependency-closures-precoverage-v1` | files, implementation, source | 0 | 0 |
| `rom-story-callback-dependency-closures-v1` | artifact | `artifacts/rom-story-callback-dependency-closures-v1` | files, implementation, summary | 0 | 0 |
| `rom-story-next-dependency-cfg-v1` | artifact | `artifacts/rom-story-next-dependency-cfg-v1` | cfg_inventory, coverage_projection, files, implementation, precoverage, producer, promotion, rom, scope, story_overlay, v20_overlay, verifier | 0 | 0 |
| `rom-story-selector-dependency-cfg-v1` | artifact | `artifacts/rom-story-selector-dependency-cfg-v1` | coverage_projection, files, implementation, precoverage, producer, promotion, rom, scope, story_dependency, verifier | 0 | 0 |
| `rom-story-state-callback-cfg-v1` | artifact | `artifacts/rom-story-state-callback-cfg-v1` | files, promotion, verifier_report | 0 | 0 |
| `rom-story-state-entry-c4cc-v1` | artifact | `artifacts/rom-story-state-entry-c4cc-v1` | files, promotion, verifier_report | 0 | 0 |
| `rom-task-callback-078e38-closure-v1` | artifact | `artifacts/rom-task-callback-078e38-closure-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-task-scheduler-core-v1` | artifact | `artifacts/rom-task-scheduler-core-v1` | coverage_baseline, entry_proof, files, implementation, producer, promotion, provenance_inputs, rom, scope, summary, verification, verifier | 0 | 0 |
| `rom-text-bg-loop-continuation-v1` | artifact | `artifacts/rom-text-bg-loop-continuation-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-text-bg-task-closure-v1` | artifact | `artifacts/rom-text-bg-task-closure-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-training-text-script-inventory-v1` | artifact | `artifacts/rom-training-text-script-inventory-v1` | files, producer, scope, verification | 0 | 0 |
| `rom-u8-indexed-u16-pair-lookup-v1` | artifact | `artifacts/rom-u8-indexed-u16-pair-lookup-v1` | coverage_baseline, files, implementation, non_claims, producer, rom, scope, verification, verifier | 0 | 0 |
| `rom-u8-indexed-u8-triplet-lookup-v1` | artifact | `artifacts/rom-u8-indexed-u8-triplet-lookup-v1` | coverage_baseline, coverage_projection, files, implementation, non_claims, promotion, rom, scope, verification, verifier | 0 | 0 |
| `rom-unbound-lz77-inventory-v1` | artifact | `artifacts/rom-unbound-lz77-inventory-v1` | files, producer, scope, verifier | 0 | 0 |
| `rom-v17-v18-helper-cfg-v1` | artifact | `artifacts/rom-v17-v18-helper-cfg-v1` | files, implementation, producer, summary, verifier | 0 | 0 |
| `rom-value-range-text-inventory-v1` | artifact | `artifacts/rom-value-range-text-inventory-v1` | files, producer, scope, verification | 0 | 0 |
| `rom-bank-proof-work-plan-20261001` | note | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` | — | 0 | 0 |
| `rom-battle-effect-fixed-roundtrip-20261001` | note | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-battle-effect-fixed-roundtrip-20261001.md` | — | 0 | 0 |
| `rom-partial-bank-joint-matrix-20261001` | note | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-partial-bank-joint-matrix-20261001.md` | — | 0 | 0 |
| `rom-release-gate-work-plan-20261001` | note | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` | — | 0 | 0 |
| `rom-bank-runtime-replay-20261001` | note | `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-bank-runtime-replay-20261001.md` | — | 0 | 0 |
| `rom-cutscene-secondary-ptr-ab-20261001` | note | `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-cutscene-secondary-ptr-ab-20261001.md` | — | 0 | 0 |
| `rom-bank-proof-work-plan-20261001` | note | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` | — | 0 | 0 |
| `rom-data-table-b-partial-bank-20261001` | note | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-data-table-b-partial-bank-20261001.md` | — | 0 | 0 |
| `rom-map-resource-fixed-roundtrip-20261002` | note | `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-map-resource-fixed-roundtrip-20261002.md` | — | 0 | 0 |
| `rom-release-gate-work-plan-20261001` | note | `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` | — | 0 | 0 |
| `rom-map-resource-relocation-roundtrip-20261002` | note | `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/notes/rom-map-resource-relocation-roundtrip-20261002.md` | — | 0 | 0 |
| `rom-release-gate-work-plan-20261001` | note | `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` | — | 0 | 0 |
| `rom-bank-proof-work-plan-20261001` | note | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` | — | 0 | 0 |
| `rom-map-sprites-partial-bank-20261001` | note | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-map-sprites-partial-bank-20261001.md` | — | 0 | 0 |
| `rom-ai-config-writer-preflight-20260930` | note | `notes/rom-ai-config-writer-preflight-20260930.md` | — | 0 | 0 |
| `rom-ai-entry-local-domains-20260930` | note | `notes/rom-ai-entry-local-domains-20260930.md` | — | 0 | 0 |
| `rom-ai-extra-pool-lifecycle-preflight-20260930` | note | `notes/rom-ai-extra-pool-lifecycle-preflight-20260930.md` | — | 0 | 0 |
| `rom-ai-producer-and-pool-alias-20260930` | note | `notes/rom-ai-producer-and-pool-alias-20260930.md` | — | 0 | 0 |
| `rom-ai-renderer-script-dependencies-20260930` | note | `notes/rom-ai-renderer-script-dependencies-20260930.md` | — | 0 | 0 |
| `rom-alternate-dialogue-table-20260902` | note | `notes/rom-alternate-dialogue-table-20260902.md` | — | 0 | 0 |
| `rom-animation-base-pairs-preflight-20261001` | note | `notes/rom-animation-base-pairs-preflight-20261001.md` | — | 0 | 0 |
| `rom-animation-callee-effects-20261001` | note | `notes/rom-animation-callee-effects-20261001.md` | — | 0 | 0 |
| `rom-animation-caller-predecessor-20261001` | note | `notes/rom-animation-caller-predecessor-20261001.md` | — | 0 | 0 |
| `rom-animation-critical-writers-20261001` | note | `notes/rom-animation-critical-writers-20261001.md` | — | 0 | 0 |
| `rom-animation-full-renderer-20261001` | note | `notes/rom-animation-full-renderer-20261001.md` | — | 0 | 0 |
| `rom-animation-interprocedural-identities-20261001` | note | `notes/rom-animation-interprocedural-identities-20261001.md` | — | 0 | 0 |
| `rom-animation-irq-arm-native-20261001` | note | `notes/rom-animation-irq-arm-native-20261001.md` | — | 0 | 0 |
| `rom-animation-object-lifecycle-20261001` | note | `notes/rom-animation-object-lifecycle-20261001.md` | — | 0 | 0 |
| `rom-animation-object-native-20261001` | note | `notes/rom-animation-object-native-20261001.md` | — | 0 | 0 |
| `rom-animation-pool-caller-screen-20261001` | note | `notes/rom-animation-pool-caller-screen-20261001.md` | — | 0 | 0 |
| `rom-animation-pool-lifecycle-20261001` | note | `notes/rom-animation-pool-lifecycle-20261001.md` | — | 0 | 0 |
| `rom-animation-save-source-20261001` | note | `notes/rom-animation-save-source-20261001.md` | — | 0 | 0 |
| `rom-animation-upstream-closure-20261001` | note | `notes/rom-animation-upstream-closure-20261001.md` | — | 0 | 0 |
| `rom-animation-writer-domain-20261001` | note | `notes/rom-animation-writer-domain-20261001.md` | — | 0 | 0 |
| `rom-bank-proof-work-plan-20261001` | note | `notes/rom-bank-proof-work-plan-20261001.md` | — | 0 | 0 |
| `rom-bank-runtime-replay-20261001` | note | `notes/rom-bank-runtime-replay-20261001.md` | — | 0 | 0 |
| `rom-battle-condition-result-text-20260902` | note | `notes/rom-battle-condition-result-text-20260902.md` | — | 0 | 0 |
| `rom-battle-distance-dispatcher-cfg-20260902` | note | `notes/rom-battle-distance-dispatcher-cfg-20260902.md` | — | 0 | 0 |
| `rom-battle-effect-fixed-roundtrip-20261001` | note | `notes/rom-battle-effect-fixed-roundtrip-20261001.md` | — | 0 | 0 |
| `rom-battle-message-text-inventory-20260811` | note | `notes/rom-battle-message-text-inventory-20260811.md` | — | 0 | 0 |
| `rom-boot-interwork-20260811` | note | `notes/rom-boot-interwork-20260811.md` | — | 0 | 0 |
| `rom-boot-register-init-dependency-cfg-20260905` | note | `notes/rom-boot-register-init-dependency-cfg-20260905.md` | — | 0 | 0 |
| `rom-bounded-index-u16-pair-table-20260904` | note | `notes/rom-bounded-index-u16-pair-table-20260904.md` | — | 0 | 0 |
| `rom-cfg-proven-roots-20260811` | note | `notes/rom-cfg-proven-roots-20260811.md` | — | 0 | 0 |
| `rom-cfg-proven-roots-v13-20260830` | note | `notes/rom-cfg-proven-roots-v13-20260830.md` | — | 0 | 0 |
| `rom-cfg-proven-roots-v14-20260830` | note | `notes/rom-cfg-proven-roots-v14-20260830.md` | — | 0 | 0 |
| `rom-cfg-proven-roots-v15-20260830` | note | `notes/rom-cfg-proven-roots-v15-20260830.md` | — | 0 | 0 |
| `rom-cfg-proven-roots-v2-20260812` | note | `notes/rom-cfg-proven-roots-v2-20260812.md` | — | 0 | 0 |
| `rom-cfg-proven-roots-v20-20260905` | note | `notes/rom-cfg-proven-roots-v20-20260905.md` | — | 0 | 0 |
| `rom-cfg-proven-roots-v21-20260905` | note | `notes/rom-cfg-proven-roots-v21-20260905.md` | — | 0 | 0 |
| `rom-cfg-proven-roots-v3-v4-20260813` | note | `notes/rom-cfg-proven-roots-v3-v4-20260813.md` | — | 0 | 0 |
| `rom-chapter-script-consumer-roots-20260902` | note | `notes/rom-chapter-script-consumer-roots-20260902.md` | — | 0 | 0 |
| `rom-chapter-script-inventory-20260809` | note | `notes/rom-chapter-script-inventory-20260809.md` | — | 0 | 0 |
| `rom-coroutine-record-lifecycle-preflight-20261001` | note | `notes/rom-coroutine-record-lifecycle-preflight-20261001.md` | — | 0 | 0 |
| `rom-cutscene-secondary-ptr-ab-20261001` | note | `notes/rom-cutscene-secondary-ptr-ab-20261001.md` | — | 0 | 0 |
| `rom-cutscene-secondary-ptr-contract-20261001` | note | `notes/rom-cutscene-secondary-ptr-contract-20261001.md` | — | 0 | 0 |
| `rom-data-table-b-partial-bank-20261001` | note | `notes/rom-data-table-b-partial-bank-20261001.md` | — | 0 | 0 |
| `rom-direct-cpuset-inventory-survey-20260730` | note | `notes/rom-direct-cpuset-inventory-survey-20260730.md` | — | 0 | 0 |
| `rom-direct-dma-inventory-survey-20260730` | note | `notes/rom-direct-dma-inventory-survey-20260730.md` | — | 0 | 0 |
| `rom-display-text-delta-tier1-20261001` | note | `notes/rom-display-text-delta-tier1-20261001.md` | — | 0 | 0 |
| `rom-display-text-parameter-flow-tdd-20261001` | note | `notes/rom-display-text-parameter-flow-tdd-20261001.md` | — | 0 | 0 |
| `rom-evidence-selector-repair-20260905` | note | `notes/rom-evidence-selector-repair-20260905.md` | — | 0 | 0 |
| `rom-expansion-character-bundle-relocation-20260731` | note | `notes/rom-expansion-character-bundle-relocation-20260731.md` | — | 0 | 0 |
| `rom-finite-lookup-scope-review-20260905` | note | `notes/rom-finite-lookup-scope-review-20260905.md` | — | 0 | 0 |
| `rom-fixed-animation-descriptor-groups-20260902` | note | `notes/rom-fixed-animation-descriptor-groups-20260902.md` | — | 0 | 0 |
| `rom-fixed-consumer-text-inventory-20260811` | note | `notes/rom-fixed-consumer-text-inventory-20260811.md` | — | 0 | 0 |
| `rom-fixed-index-u8-tail-20260905` | note | `notes/rom-fixed-index-u8-tail-20260905.md` | — | 0 | 0 |
| `rom-fixed-pair-tables-20260904` | note | `notes/rom-fixed-pair-tables-20260904.md` | — | 0 | 0 |
| `rom-fixed-text-route-preflight-20261001` | note | `notes/rom-fixed-text-route-preflight-20261001.md` | — | 0 | 0 |
| `rom-gpu-copy-queue-inventory-20260730` | note | `notes/rom-gpu-copy-queue-inventory-20260730.md` | — | 0 | 0 |
| `rom-large-unknown-anchor-screen-20261001` | note | `notes/rom-large-unknown-anchor-screen-20261001.md` | — | 0 | 0 |
| `rom-later-cfg-renderer-consumers-preflight-20261001` | note | `notes/rom-later-cfg-renderer-consumers-preflight-20261001.md` | — | 0 | 0 |
| `rom-low-script-delta-tier1-20261001` | note | `notes/rom-low-script-delta-tier1-20261001.md` | — | 0 | 0 |
| `rom-low-script-fixed-consumers-preflight-20261001` | note | `notes/rom-low-script-fixed-consumers-preflight-20261001.md` | — | 0 | 0 |
| `rom-m4a-initializer-chain-20260829` | note | `notes/rom-m4a-initializer-chain-20260829.md` | — | 0 | 0 |
| `rom-map-resource-fixed-roundtrip-20261002` | note | `notes/rom-map-resource-fixed-roundtrip-20261002.md` | — | 0 | 0 |
| `rom-map-resource-relocation-roundtrip-20261002` | note | `notes/rom-map-resource-relocation-roundtrip-20261002.md` | — | 0 | 0 |
| `rom-map-sprites-partial-bank-20261001` | note | `notes/rom-map-sprites-partial-bank-20261001.md` | — | 0 | 0 |
| `rom-menu-gfx-pointer-ab-20261001` | note | `notes/rom-menu-gfx-pointer-ab-20261001.md` | — | 0 | 0 |
| `rom-menu-portrait-palette-inventory-20260820` | note | `notes/rom-menu-portrait-palette-inventory-20260820.md` | — | 0 | 0 |
| `rom-mp2k-dispatcher-20260829` | note | `notes/rom-mp2k-dispatcher-20260829.md` | — | 0 | 0 |
| `rom-mp2k-note-allocator-20260829` | note | `notes/rom-mp2k-note-allocator-20260829.md` | — | 0 | 0 |
| `rom-mplaymain-scheduler-20260828` | note | `notes/rom-mplaymain-scheduler-20260828.md` | — | 0 | 0 |
| `rom-open-root-and-large-candidate-review-20260905` | note | `notes/rom-open-root-and-large-candidate-review-20260905.md` | — | 0 | 0 |
| `rom-partial-bank-joint-matrix-20261001` | note | `notes/rom-partial-bank-joint-matrix-20261001.md` | — | 0 | 0 |
| `rom-pointer-lz77-graphics-preview-20260730` | note | `notes/rom-pointer-lz77-graphics-preview-20260730.md` | — | 0 | 0 |
| `rom-pointer-lz77-inventory-export-20260730` | note | `notes/rom-pointer-lz77-inventory-export-20260730.md` | — | 0 | 0 |
| `rom-prebattle-menu-controller-cfg-20260905` | note | `notes/rom-prebattle-menu-controller-cfg-20260905.md` | — | 0 | 0 |
| `rom-ram-protocol-tag-preflight-20261001` | note | `notes/rom-ram-protocol-tag-preflight-20261001.md` | — | 0 | 0 |
| `rom-referenced-text-slot-padding-20260820` | note | `notes/rom-referenced-text-slot-padding-20260820.md` | — | 0 | 0 |
| `rom-release-gate-work-plan-20261001` | note | `notes/rom-release-gate-work-plan-20261001.md` | — | 0 | 0 |
| `rom-renderer-batch-plan-20261001` | note | `notes/rom-renderer-batch-plan-20261001.md` | — | 0 | 0 |
| `rom-renderer-excluded-roots-preflight-20260930` | note | `notes/rom-renderer-excluded-roots-preflight-20260930.md` | — | 0 | 0 |
| `rom-renderer-flow-cost-20261001` | note | `notes/rom-renderer-flow-cost-20261001.md` | — | 0 | 0 |
| `rom-renderer-handler-context-preflight-20260930` | note | `notes/rom-renderer-handler-context-preflight-20260930.md` | — | 0 | 0 |
| `rom-renderer-records-delta-tier1-20261001` | note | `notes/rom-renderer-records-delta-tier1-20261001.md` | — | 0 | 0 |
| `rom-renderer-source-plan-20261001` | note | `notes/rom-renderer-source-plan-20261001.md` | — | 0 | 0 |
| `rom-renderer-source-replay-20261001` | note | `notes/rom-renderer-source-replay-20261001.md` | — | 0 | 0 |
| `rom-renderer-text-inventory-20260809` | note | `notes/rom-renderer-text-inventory-20260809.md` | — | 0 | 0 |
| `rom-scene-source-closures-20260905` | note | `notes/rom-scene-source-closures-20260905.md` | — | 0 | 0 |
| `rom-scene-visual-source-ranges-20260820` | note | `notes/rom-scene-visual-source-ranges-20260820.md` | — | 0 | 0 |
| `rom-selector-code-windows-20260820` | note | `notes/rom-selector-code-windows-20260820.md` | — | 0 | 0 |
| `rom-selector-direct-source-records-20260820` | note | `notes/rom-selector-direct-source-records-20260820.md` | — | 0 | 0 |
| `rom-selector-text-bindings-20260811` | note | `notes/rom-selector-text-bindings-20260811.md` | — | 0 | 0 |
| `rom-small-cfg-dependency-batch-20260905` | note | `notes/rom-small-cfg-dependency-batch-20260905.md` | — | 0 | 0 |
| `rom-small-cfg-dependency-tier2-20260930` | note | `notes/rom-small-cfg-dependency-tier2-20260930.md` | — | 0 | 0 |
| `rom-soundmain-relocated-cfg-20260828` | note | `notes/rom-soundmain-relocated-cfg-20260828.md` | — | 0 | 0 |
| `rom-staged-gpu-copy-inventory-20260730` | note | `notes/rom-staged-gpu-copy-inventory-20260730.md` | — | 0 | 0 |
| `rom-story-callback-dependency-closures-20260905` | note | `notes/rom-story-callback-dependency-closures-20260905.md` | — | 0 | 0 |
| `rom-story-next-dependency-cfg-20260905` | note | `notes/rom-story-next-dependency-cfg-20260905.md` | — | 0 | 0 |
| `rom-story-selector-dependency-cfg-20260905` | note | `notes/rom-story-selector-dependency-cfg-20260905.md` | — | 0 | 0 |
| `rom-strided-prefix-local-read-domain-20260905` | note | `notes/rom-strided-prefix-local-read-domain-20260905.md` | — | 0 | 0 |
| `rom-task-callback-078e38-closure-20260905` | note | `notes/rom-task-callback-078e38-closure-20260905.md` | — | 0 | 0 |
| `rom-task-callback-alignment-gap-candidate-20260905` | note | `notes/rom-task-callback-alignment-gap-candidate-20260905.md` | — | 0 | 0 |
| `rom-training-text-script-inventory-20260811` | note | `notes/rom-training-text-script-inventory-20260811.md` | — | 0 | 0 |
| `rom-u8-indexed-u16-pair-lookup-20260827` | note | `notes/rom-u8-indexed-u16-pair-lookup-20260827.md` | — | 0 | 0 |
| `rom-unknown-candidate-59eae0-negative-evidence-20260827` | note | `notes/rom-unknown-candidate-59eae0-negative-evidence-20260827.md` | — | 0 | 0 |
| `rom-unknown-cluster-refresh-20260901` | note | `notes/rom-unknown-cluster-refresh-20260901.md` | — | 0 | 0 |
| `rom-unknown-cluster-refresh-20260902` | note | `notes/rom-unknown-cluster-refresh-20260902.md` | — | 0 | 0 |
| `rom-unknown-cluster-refresh-20260905` | note | `notes/rom-unknown-cluster-refresh-20260905.md` | — | 0 | 0 |
| `rom-v17-v18-helper-cfg-20260904` | note | `notes/rom-v17-v18-helper-cfg-20260904.md` | — | 0 | 0 |
| `rom-value-range-text-inventory-20260811` | note | `notes/rom-value-range-text-inventory-20260811.md` | — | 0 | 0 |
| `rom-verifier-runtime-inputs-20260905` | note | `notes/rom-verifier-runtime-inputs-20260905.md` | — | 0 | 0 |
| `rom-reverse-engineering-results` | doc | `docs/rom-reverse-engineering-results.md` | — | 0 | 0 |
| `rom-sequel-plan` | doc | `docs/rom-sequel-plan.md` | — | 0 | 0 |
| `rom-verifier-checkout-setup` | doc | `docs/rom-verifier-checkout-setup.md` | — | 0 | 0 |

### runtime（13）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `runtime-bg-composites-v1` | artifact | `artifacts/runtime-bg-composites-v1` | experiment, files, producer, source, verifier | 0 | 0 |
| `runtime-checkpoints` | artifact | `artifacts/runtime-checkpoints` | — | 0 | 0 |
| `runtime-font-tile-provenance-v1` | artifact | `artifacts/runtime-font-tile-provenance-v1` | experiment, files, producer, source, verifier | 0 | 0 |
| `runtime-layer-static-provenance-v1` | artifact | `artifacts/runtime-layer-static-provenance-v1` | experiment, files, producer, source, verifier | 0 | 0 |
| `runtime-screen-composites-v1` | artifact | `artifacts/runtime-screen-composites-v1` | experiment, files, producer, source, verifier | 0 | 0 |
| `runtime-bg-composites-20260730` | note | `notes/runtime-bg-composites-20260730.md` | — | 0 | 0 |
| `runtime-checkpoints-data-integrity-issue-20260806` | note | `notes/runtime-checkpoints-data-integrity-issue-20260806.md` | — | 0 | 0 |
| `runtime-font-tile-provenance-20260730` | note | `notes/runtime-font-tile-provenance-20260730.md` | — | 0 | 0 |
| `runtime-handler-pair-consumer-20260712` | note | `notes/runtime-handler-pair-consumer-20260712.md` | — | 0 | 0 |
| `runtime-layer-static-provenance-20260730` | note | `notes/runtime-layer-static-provenance-20260730.md` | — | 0 | 0 |
| `runtime-mode0-screen-compositor-20260730` | note | `notes/runtime-mode0-screen-compositor-20260730.md` | — | 0 | 0 |
| `runtime-state-entry-audit-20260710` | note | `notes/runtime-state-entry-audit-20260710.md` | — | 0 | 0 |
| `runtime-verification-gates-20260710` | note | `notes/runtime-verification-gates-20260710.md` | — | 0 | 0 |

### scenario（23）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `scenario-41-attack-animation-v1` | artifact | `artifacts/scenario-41-attack-animation-v1` | frames | 0 | 0 |
| `scenario-41-audio-reference-v1` | artifact | `artifacts/scenario-41-audio-reference-v1` | — | 0 | 0 |
| `scenario-41-combat-reference-v1` | artifact | `artifacts/scenario-41-combat-reference-v1` | boundaries | 0 | 0 |
| `scenario-41-extended-reference-v1` | artifact | `artifacts/scenario-41-extended-reference-v1` | boundaries | 0 | 0 |
| `scenario-41-prebattle-reference-v1` | artifact | `artifacts/scenario-41-prebattle-reference-v1` | boundaries | 0 | 0 |
| `scenario-41-reference-v1` | artifact | `artifacts/scenario-41-reference-v1` | boundaries | 0 | 0 |
| `scenario-41-battle-entry-runtime-20260713` | note | `notes/scenario-41-battle-entry-runtime-20260713.md` | — | 0 | 0 |
| `scenario-41-completion-runtime-20260718` | note | `notes/scenario-41-completion-runtime-20260718.md` | — | 0 | 0 |
| `scenario-41-controller-path-runtime-20260715` | note | `notes/scenario-41-controller-path-runtime-20260715.md` | — | 0 | 0 |
| `scenario-41-movedone-runtime-20260717` | note | `notes/scenario-41-movedone-runtime-20260717.md` | — | 0 | 0 |
| `scenario-41-player-control-runtime-20260715` | note | `notes/scenario-41-player-control-runtime-20260715.md` | — | 0 | 0 |
| `scenario-41-prebattle-menu-macos-20260715` | note | `notes/scenario-41-prebattle-menu-macos-20260715.md` | — | 0 | 0 |
| `scenario-41-prebattle-to-controller-macos-20260715` | note | `notes/scenario-41-prebattle-to-controller-macos-20260715.md` | — | 0 | 0 |
| `scenario-41-savestate-context-reanalysis-20260715` | note | `notes/scenario-41-savestate-context-reanalysis-20260715.md` | — | 0 | 0 |
| `scenario-42-progression-runtime-20260718` | note | `notes/scenario-42-progression-runtime-20260718.md` | — | 0 | 0 |
| `scenario-43-progression-runtime-20260718` | note | `notes/scenario-43-progression-runtime-20260718.md` | — | 0 | 0 |
| `scenario-44-progression-runtime-20260718` | note | `notes/scenario-44-progression-runtime-20260718.md` | — | 0 | 0 |
| `scenario-45-safe-resume-20260719` | note | `notes/scenario-45-safe-resume-20260719.md` | — | 0 | 0 |
| `scenario-46-entry-runtime-20260719` | note | `notes/scenario-46-entry-runtime-20260719.md` | — | 0 | 0 |
| `scenario-47-entry-runtime-20260720` | note | `notes/scenario-47-entry-runtime-20260720.md` | — | 0 | 0 |
| `scenario-48-academy-runtime-20260720` | note | `notes/scenario-48-academy-runtime-20260720.md` | — | 0 | 0 |
| `scenario-49-battle-14-runtime-20260720` | note | `notes/scenario-49-battle-14-runtime-20260720.md` | — | 0 | 0 |
| `scenario-50-battle-15-runtime-20260720` | note | `notes/scenario-50-battle-15-runtime-20260720.md` | — | 0 | 0 |

### visual（130）

| id | 类型 | 路径 | 提供的结论 | 公式数 | 地址数 |
| --- | --- | --- | --- | --- | --- |
| `battle-effect-affine-runtime-v1` | artifact | `artifacts/battle-effect-affine-runtime-v1` | capture, display, mirror_capture, object, resource_binding, scope, sequence_coverage | 0 | 0 |
| `battle-effect-controlled-runtime-v1` | artifact | `artifacts/battle-effect-controlled-runtime-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-direct-spawn-runtime-v1` | artifact | `artifacts/battle-effect-direct-spawn-runtime-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-frame-phase-group1-v1` | artifact | `artifacts/battle-effect-frame-phase-group1-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-frame-phase-group14-v1` | artifact | `artifacts/battle-effect-frame-phase-group14-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-frame-phase-group16-natural-v1` | artifact | `artifacts/battle-effect-frame-phase-group16-natural-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-frame-phase-group17-natural-v1` | artifact | `artifacts/battle-effect-frame-phase-group17-natural-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-frame-phase-group18-natural-sequence-v1` | artifact | `artifacts/battle-effect-frame-phase-group18-natural-sequence-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-frame-phase-group2-v1` | artifact | `artifacts/battle-effect-frame-phase-group2-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-frame-phase-group3-natural-v1` | artifact | `artifacts/battle-effect-frame-phase-group3-natural-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-frame-phase-group4-natural-v1` | artifact | `artifacts/battle-effect-frame-phase-group4-natural-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-frame-phase-group5-v1` | artifact | `artifacts/battle-effect-frame-phase-group5-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-frame-phase-v1` | artifact | `artifacts/battle-effect-frame-phase-v1` | animations, breakpoint_pc_semantics, dump_semantics, files, input_state, profile, repository_files, source_runtime_provenance, toolchain, verifier | 0 | 0 |
| `battle-effect-group03-controlled-pixel-ab-v1` | artifact | `artifacts/battle-effect-group03-controlled-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group03-natural-pixel-ab-v1` | artifact | `artifacts/battle-effect-group03-natural-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group06-controlled-pixel-ab-v1` | artifact | `artifacts/battle-effect-group06-controlled-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group07-controlled-pixel-ab-v1` | artifact | `artifacts/battle-effect-group07-controlled-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group08-controlled-pixel-ab-v1` | artifact | `artifacts/battle-effect-group08-controlled-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group09-controlled-pixel-ab-v1` | artifact | `artifacts/battle-effect-group09-controlled-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group1-pixel-ab-v1` | artifact | `artifacts/battle-effect-group1-pixel-ab-v1` | files, generated_with_implementation_sha256, parent, raw_files, scope, verified_with_implementation_sha256, verifier | 0 | 0 |
| `battle-effect-group10-controlled-pixel-ab-v1` | artifact | `artifacts/battle-effect-group10-controlled-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group11-pixel-ab-v1` | artifact | `artifacts/battle-effect-group11-pixel-ab-v1` | files, generated_with_implementation_sha256, parent, raw_files, scope, verified_with_implementation_sha256, verifier | 0 | 0 |
| `battle-effect-group12-ai-observer-v1` | artifact | `artifacts/battle-effect-group12-ai-observer-v1` | files, inputs, mgba_build, result, verifier | 0 | 0 |
| `battle-effect-group12-controlled-pixel-ab-v1` | artifact | `artifacts/battle-effect-group12-controlled-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group13-natural-runtime-v1` | artifact | `artifacts/battle-effect-group13-natural-runtime-v1` | files, verifier | 0 | 0 |
| `battle-effect-group13-pixel-ab-v1` | artifact | `artifacts/battle-effect-group13-pixel-ab-v1` | files, generated_with_implementation_sha256, parent, raw_files, scope, verified_with_implementation_sha256, verifier | 0 | 0 |
| `battle-effect-group14-pixel-ab-v1` | artifact | `artifacts/battle-effect-group14-pixel-ab-v1` | files, generated_with_implementation_sha256, parent, raw_files, scope, verified_with_implementation_sha256, verifier | 0 | 0 |
| `battle-effect-group15-allocator-side-runtime-v1` | artifact | `artifacts/battle-effect-group15-allocator-side-runtime-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group15-natural-runtime-v1` | artifact | `artifacts/battle-effect-group15-natural-runtime-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group15-pixel-ab-v1` | artifact | `artifacts/battle-effect-group15-pixel-ab-v1` | files, generated_with_implementation_sha256, parent, raw_files, scope, verified_with_implementation_sha256, verifier | 0 | 0 |
| `battle-effect-group16-pixel-ab-v1` | artifact | `artifacts/battle-effect-group16-pixel-ab-v1` | files, generated_with_implementation_sha256, parent, raw_files, scope, verified_with_implementation_sha256, verifier | 0 | 0 |
| `battle-effect-group17-pixel-ab-v1` | artifact | `artifacts/battle-effect-group17-pixel-ab-v1` | files, generated_with_implementation_sha256, parent, raw_files, scope, verified_with_implementation_sha256, verifier | 0 | 0 |
| `battle-effect-group18-controlled-pixel-ab-v1` | artifact | `artifacts/battle-effect-group18-controlled-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group18-natural-checkpoint-v1` | artifact | `artifacts/battle-effect-group18-natural-checkpoint-v1` | delayed_object, expiry_route, files, input_state, runtime_phase, scope, source_states, static_producers, verifier | 0 | 0 |
| `battle-effect-group18-natural-pixel-ab-v1` | artifact | `artifacts/battle-effect-group18-natural-pixel-ab-v1` | files, repository_files, verifier | 0 | 0 |
| `battle-effect-group2-pixel-ab-v1` | artifact | `artifacts/battle-effect-group2-pixel-ab-v1` | files, generated_with_implementation_sha256, parent, raw_files, scope, verified_with_implementation_sha256, verifier | 0 | 0 |
| `battle-effect-group4-pixel-ab-v1` | artifact | `artifacts/battle-effect-group4-pixel-ab-v1` | files, generated_with_implementation_sha256, parent, raw_files, scope, verified_with_implementation_sha256, verifier | 0 | 0 |
| `battle-effect-group5-pixel-ab-v1` | artifact | `artifacts/battle-effect-group5-pixel-ab-v1` | files, implementation_sha256, parent, raw_files, scope, verifier | 0 | 0 |
| `battle-effect-observed-frame-phases-v1` | artifact | `artifacts/battle-effect-observed-frame-phases-v1` | files, producer, verifier | 0 | 0 |
| `battle-effect-resource-pairs-v1` | artifact | `artifacts/battle-effect-resource-pairs-v1` | resource_pair_table, rom, scope | 0 | 0 |
| `battle-effect-resource-relocation-v1` | artifact | `artifacts/battle-effect-resource-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `battle-effect-resource-writeback-v1` | artifact | `artifacts/battle-effect-resource-writeback-v1` | files, scope, verifier | 0 | 0 |
| `battle-effect-runtime-oam-bindings-v1` | artifact | `artifacts/battle-effect-runtime-oam-bindings-v1` | files, producer, source, summary, verifier | 0 | 0 |
| `battle-effect-runtime-oam-task-bindings-v1` | artifact | `artifacts/battle-effect-runtime-oam-task-bindings-v1` | files, producer, source, summary, verifier | 0 | 0 |
| `battle-effect-sequence-bindings-v1` | artifact | `artifacts/battle-effect-sequence-bindings-v1` | active_action_join_evidence, active_action_slice, active_action_template_table, boundary_evidence, ninja_tool_join_evidence, ninja_tool_selector_slice, ninja_tool_template_table, rom, runtime_state_sequence_table, scope, sequence_descriptor_table | 0 | 0 |
| `battle-effect-sprite-animations-v1` | artifact | `artifacts/battle-effect-sprite-animations-v1` | affine_matrix_model, animation_schema, child_task_origin_model, component_schema, dynamic_obj_vram_model, inputs, motion_spawn_table, oam_attribute_model, parent_release_scheduler_boundary, pre_oam_coordinate_transform_model, resource_pointer_table, rom, runtime_golden_duration_cross_checks, scope, sprite_pair_table | 0 | 0 |
| `battle-visual-catalog-v1` | artifact | `artifacts/battle-visual-catalog-v1` | rom, scope, selection_chain, source_artifacts, summary | 1 | 3 |
| `battle-visual-runtime-timelines-v1` | artifact | `artifacts/battle-visual-runtime-timelines-v1` | rom, scope, source_artifact, summary | 0 | 0 |
| `bg-resource-canvases-v1` | artifact | `artifacts/bg-resource-canvases-v1` | consumer, rom, scope, summary, table | 0 | 0 |
| `bg-resource-relocation-v1` | artifact | `artifacts/bg-resource-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `bg-resource-writeback-v1` | artifact | `artifacts/bg-resource-writeback-v1` | files, scope, verifier | 0 | 0 |
| `bg-scene-selection-v1` | artifact | `artifacts/bg-scene-selection-v1` | catalogs, evidence, rom, scope, summary, upstream | 0 | 0 |
| `character-battle-bundle-relocation-v1` | artifact | `artifacts/character-battle-bundle-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `character-battle-graphics-pixel-ab-v1` | artifact | `artifacts/character-battle-graphics-pixel-ab-v1` | files, implementation_sha256, parent, scope, verifier | 0 | 0 |
| `character-battle-graphics-writeback-v1` | artifact | `artifacts/character-battle-graphics-writeback-v1` | files, scope, summary, verifier | 0 | 0 |
| `character-battle-palette-writeback-v1` | artifact | `artifacts/character-battle-palette-writeback-v1` | files, scope, summary, verifier | 0 | 0 |
| `character-battle-structure-writeback-v1` | artifact | `artifacts/character-battle-structure-writeback-v1` | files, scope, summary, verifier | 0 | 0 |
| `character-battle-visual-resource-matrix-v1` | artifact | `artifacts/character-battle-visual-resource-matrix-v1` | files, implementation_sha256, parent, scope, verifier | 0 | 0 |
| `character-battle-visuals-v1` | artifact | `artifacts/character-battle-visuals-v1` | consumer, rom, scope, summary, table | 0 | 0 |
| `character-fbff-runtime-v1` | artifact | `artifacts/character-fbff-runtime-v1` | base_rom, base_run, conclusion, control_rom, control_run, probe_input, probe_script, renderer | 0 | 0 |
| `character-runtime-oam-bindings-v1` | artifact | `artifacts/character-runtime-oam-bindings-v1` | files, source, summary, verifier | 0 | 0 |
| `character-runtime-oam-task-bindings-v1` | artifact | `artifacts/character-runtime-oam-task-bindings-v1` | experiment, files, producer, source, verifier | 0 | 0 |
| `character-runtime-unit-oam-bindings-v1` | artifact | `artifacts/character-runtime-unit-oam-bindings-v1` | experiment, files, producer, source, verifier | 0 | 0 |
| `sprite-definition-animations-v1` | artifact | `artifacts/sprite-definition-animations-v1` | consumer, pair_table, rom, scope, source_artifact | 0 | 0 |
| `sprite-definition-assets-v2` | artifact | `artifacts/sprite-definition-assets-v2` | component_schema, pair_table, rom, runtime_chain, scope, sprite_pack_atlas, static_resources, tile_coverage, tile_offset_table | 0 | 0 |
| `sprite-definition-runtime-v1` | artifact | `artifacts/sprite-definition-runtime-v1` | component_schema, pair_table, rom, runtime_chain, scope, tile_offset_table | 0 | 0 |
| `tile-asset-descriptor2-pixel-ab-v1` | artifact | `artifacts/tile-asset-descriptor2-pixel-ab-v1` | files, implementation, scope, verifier | 0 | 0 |
| `tile-asset-resource-relocation-v1` | artifact | `artifacts/tile-asset-resource-relocation-v1` | files, scope, summary, verifier | 0 | 0 |
| `tile-assets-bg-v1` | artifact | `artifacts/tile-assets-bg-v1` | complete_layer_counts, rom, scope, source_table | 0 | 0 |
| `tile-assets-bg-v2` | artifact | `artifacts/tile-assets-bg-v2` | complete_layer_counts, rom, scope, source_table, supersedes | 0 | 0 |
| `battle-effect-controlled-phase-extension-20260809` | note | `notes/battle-effect-controlled-phase-extension-20260809.md` | — | 0 | 0 |
| `battle-effect-controlled-runtime-20260801` | note | `notes/battle-effect-controlled-runtime-20260801.md` | — | 0 | 0 |
| `battle-effect-direct-spawn-runtime-20260802` | note | `notes/battle-effect-direct-spawn-runtime-20260802.md` | — | 0 | 0 |
| `battle-effect-frame-phase-20260801` | note | `notes/battle-effect-frame-phase-20260801.md` | — | 0 | 0 |
| `battle-effect-group1-pixel-ab-20260801` | note | `notes/battle-effect-group1-pixel-ab-20260801.md` | — | 0 | 0 |
| `battle-effect-group11-pixel-ab-20260801` | note | `notes/battle-effect-group11-pixel-ab-20260801.md` | — | 0 | 0 |
| `battle-effect-group12-group13-route-audit-20260802` | note | `notes/battle-effect-group12-group13-route-audit-20260802.md` | — | 0 | 0 |
| `battle-effect-group13-pixel-ab-20260802` | note | `notes/battle-effect-group13-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group14-pixel-ab-20260801` | note | `notes/battle-effect-group14-pixel-ab-20260801.md` | — | 0 | 0 |
| `battle-effect-group15-allocator-side-runtime-20260801` | note | `notes/battle-effect-group15-allocator-side-runtime-20260801.md` | — | 0 | 0 |
| `battle-effect-group15-natural-runtime-20260802` | note | `notes/battle-effect-group15-natural-runtime-20260802.md` | — | 0 | 0 |
| `battle-effect-group15-pixel-ab-20260802` | note | `notes/battle-effect-group15-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group16-natural-pixel-ab-20260802` | note | `notes/battle-effect-group16-natural-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group17-natural-pixel-ab-20260802` | note | `notes/battle-effect-group17-natural-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group18-controlled-pixel-ab-20260802` | note | `notes/battle-effect-group18-controlled-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group18-natural-pixel-ab-20260802` | note | `notes/battle-effect-group18-natural-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group2-pixel-ab-20260802` | note | `notes/battle-effect-group2-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group2-route-stop-20260802` | note | `notes/battle-effect-group2-route-stop-20260802.md` | — | 0 | 0 |
| `battle-effect-group3-controlled-pixel-ab-20260802` | note | `notes/battle-effect-group3-controlled-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group3-natural-expiry-phase-20260802` | note | `notes/battle-effect-group3-natural-expiry-phase-20260802.md` | — | 0 | 0 |
| `battle-effect-group3-natural-pixel-ab-20260802` | note | `notes/battle-effect-group3-natural-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group4-natural-pixel-ab-20260802` | note | `notes/battle-effect-group4-natural-pixel-ab-20260802.md` | — | 0 | 0 |
| `battle-effect-group5-pixel-ab-20260801` | note | `notes/battle-effect-group5-pixel-ab-20260801.md` | — | 0 | 0 |
| `battle-effect-group6-controlled-pixel-ab-20260809` | note | `notes/battle-effect-group6-controlled-pixel-ab-20260809.md` | — | 0 | 0 |
| `battle-effect-group6-entry-audit-20260806` | note | `notes/battle-effect-group6-entry-audit-20260806.md` | — | 0 | 0 |
| `battle-effect-groups7-12-controlled-pixel-ab-20260809` | note | `notes/battle-effect-groups7-12-controlled-pixel-ab-20260809.md` | — | 0 | 0 |
| `battle-effect-hardcoded-selector-producers-20260802` | note | `notes/battle-effect-hardcoded-selector-producers-20260802.md` | — | 0 | 0 |
| `battle-effect-observed-frame-phases-20260801` | note | `notes/battle-effect-observed-frame-phases-20260801.md` | — | 0 | 0 |
| `battle-effect-resource-pairs-export-20260729` | note | `notes/battle-effect-resource-pairs-export-20260729.md` | — | 0 | 0 |
| `battle-effect-resource-relocation-20260731` | note | `notes/battle-effect-resource-relocation-20260731.md` | — | 0 | 0 |
| `battle-effect-resource-writeback-20260731` | note | `notes/battle-effect-resource-writeback-20260731.md` | — | 0 | 0 |
| `battle-effect-runtime-oam-bindings-20260801` | note | `notes/battle-effect-runtime-oam-bindings-20260801.md` | — | 0 | 0 |
| `battle-effect-runtime-oam-task-bindings-20260801` | note | `notes/battle-effect-runtime-oam-task-bindings-20260801.md` | — | 0 | 0 |
| `battle-effect-sequence-bindings-export-20260729` | note | `notes/battle-effect-sequence-bindings-export-20260729.md` | — | 0 | 0 |
| `battle-effect-sprite-animations-export-20260729` | note | `notes/battle-effect-sprite-animations-export-20260729.md` | — | 0 | 0 |
| `battle-effect-template-consumer-20260711` | note | `notes/battle-effect-template-consumer-20260711.md` | — | 0 | 0 |
| `battle-visual-catalog-export-20260729` | note | `notes/battle-visual-catalog-export-20260729.md` | — | 0 | 0 |
| `battle-visual-runtime-timelines-export-20260729` | note | `notes/battle-visual-runtime-timelines-export-20260729.md` | — | 0 | 0 |
| `bg-resource-canvases-export-20260729` | note | `notes/bg-resource-canvases-export-20260729.md` | — | 0 | 0 |
| `bg-resource-relocation-20260731` | note | `notes/bg-resource-relocation-20260731.md` | — | 0 | 0 |
| `bg-resource-writeback-20260731` | note | `notes/bg-resource-writeback-20260731.md` | — | 0 | 0 |
| `bg-scene-selection-export-20260729` | note | `notes/bg-scene-selection-export-20260729.md` | — | 0 | 0 |
| `character-battle-graphics-pixel-ab-20260801` | note | `notes/character-battle-graphics-pixel-ab-20260801.md` | — | 0 | 0 |
| `character-battle-graphics-writeback-20260731` | note | `notes/character-battle-graphics-writeback-20260731.md` | — | 0 | 0 |
| `character-battle-palette-writeback-20260731` | note | `notes/character-battle-palette-writeback-20260731.md` | — | 0 | 0 |
| `character-battle-structure-writeback-20260731` | note | `notes/character-battle-structure-writeback-20260731.md` | — | 0 | 0 |
| `character-battle-visual-resource-matrix-20260801` | note | `notes/character-battle-visual-resource-matrix-20260801.md` | — | 0 | 0 |
| `character-battle-visuals-export-20260729` | note | `notes/character-battle-visuals-export-20260729.md` | — | 0 | 0 |
| `character-definition-source-20260711` | note | `notes/character-definition-source-20260711.md` | — | 0 | 0 |
| `character-growth-runtime-chain-20260711` | note | `notes/character-growth-runtime-chain-20260711.md` | — | 0 | 0 |
| `character-runtime-oam-bindings-20260730` | note | `notes/character-runtime-oam-bindings-20260730.md` | — | 0 | 0 |
| `character-runtime-oam-task-bindings-20260730` | note | `notes/character-runtime-oam-task-bindings-20260730.md` | — | 0 | 0 |
| `character-runtime-unit-oam-bindings-20260730` | note | `notes/character-runtime-unit-oam-bindings-20260730.md` | — | 0 | 0 |
| `character-stats-addresses` | note | `notes/character-stats-addresses.md` | — | 0 | 0 |
| `sprite-definition-animations-export-20260729` | note | `notes/sprite-definition-animations-export-20260729.md` | — | 0 | 0 |
| `sprite-definition-runtime-chain-20260729` | note | `notes/sprite-definition-runtime-chain-20260729.md` | — | 0 | 0 |
| `tile-asset-resource-relocation-20260731` | note | `notes/tile-asset-resource-relocation-20260731.md` | — | 0 | 0 |
| `tile-assets-bg-export-20260729` | note | `notes/tile-assets-bg-export-20260729.md` | — | 0 | 0 |
| `tile-assets-descriptor-player-visible-20260809` | note | `notes/tile-assets-descriptor-player-visible-20260809.md` | — | 0 | 0 |
| `tileset-extraction-correction-20260712` | note | `notes/tileset-extraction-correction-20260712.md` | — | 0 | 0 |

