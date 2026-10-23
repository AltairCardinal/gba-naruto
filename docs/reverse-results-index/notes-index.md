# 逆向 notes 分类索引（自动生成）

本文件由 `tools/build_reverse_notes_index.py` 生成，不要手工编辑。

每条逆向 note 落在且只落在五个桶之一：

| 桶 | 含义 | 条数 | 占比 |
| --- | --- | ---: | ---: |
| `implemented_in_code` | 本树构建链已引用，附消费文件与行号 | 29 | 6.7% |
| `not_applicable` | 与本复刻无关，附理由 | 43 | 9.9% |
| `missing_evidence` | 证据未闭合，回逆向侧补齐 | 19 | 4.4% |
| `needs_guard` | 已给出原版结论，尚未转成门禁——M1/M2 的原料 | 332 | 76.1% |
| `needs_human_review` | 自动判读不了，附原因 | 13 | 3.0% |

- 合计：**436** 个 note 文件
- 其中不重复的 note id：398（证据包内嵌的快照与顶层同名，计数以文件为单位）
- 逆向 commit：`821d0937e058245aa7e6d29f23f96c7fc78e7375`
- 扫描文件数：4863

- `needs_guard` 里有 **18** 条已经在 `tests/` 被引用过，**314** 条连测试都没有引用 ⇒ P2 的真实分母是后者。⚠️ **上界不是真值**：`tests/` 里的引用可能是**文档类测试**而不是行为门禁，所以「已被引用」只能当作「可能已有门禁」的上界，逐条判定仍需人看。

## 索引前的引用状态

本索引把每条 note 都写进了本树，因此差异测量里这些 note 的状态会从 `none` 变成 `doc`/`local_artifact`。**那不是消费。** 下面是写入本索引之前它们在本树的真实状态（`build` 才是「被消费」）。

| 索引前状态 | 条数 |
| --- | ---: |
| `build` | 29 |
| `local_artifact` | 125 |
| `test` | 10 |
| `doc` | 62 |
| `none` | 210 |

## 按类别 × 桶

| 类别 | `implemented_in_code` | `not_applicable` | `missing_evidence` | `needs_guard` | `needs_human_review` | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| audio | 0 | 0 | 0 | 4 | 0 | 4 |
| battle | 3 | 0 | 0 | 7 | 0 | 10 |
| map | 0 | 0 | 0 | 18 | 0 | 18 |
| other | 18 | 29 | 4 | 106 | 13 | 170 |
| overview | 0 | 0 | 0 | 1 | 0 | 1 |
| presentation | 0 | 0 | 0 | 15 | 0 | 15 |
| residual | 0 | 0 | 0 | 10 | 0 | 10 |
| rom | 1 | 14 | 15 | 93 | 0 | 123 |
| runtime | 1 | 0 | 0 | 7 | 0 | 8 |
| scenario | 3 | 0 | 0 | 14 | 0 | 17 |
| visual | 3 | 0 | 0 | 57 | 0 | 60 |

## `implemented_in_code`（29）

| note | 类别 | 消费指针 | 引用强度 |
| --- | --- | --- | --- |
| `notes/addresses.md` | other | `sequel/content/battle-config/ninja-tool-identities.json:3`、`sequel/content/battle-handlers/bank.json:66`、`sequel/content/data-table-b/bank.json:62` | code |
| `notes/battle-config-format.md` | battle | `tools/export_content_pack.py:1374`、`tools/import_battle_config.py:23`、`tools/import_battle_config.py:68` | code |
| `notes/battle-config-unsafe-template-fix-20260710.md` | battle | `tools/completion_audit.py:1007` | code |
| `notes/battle-system-restoration-evidence-20260723.md` | battle | `sequel/content/battle_controller_states.json:431`、`sequel/content/battle_controller_states.json:1413`、`sequel/content/battle_controller_transitions.json:627` | code |
| `notes/character-definition-source-20260711.md` | visual | `sequel/content/units/bank.json:19984`、`sequel/content/units/bank.json:20004`、`sequel/content/units/bank.json:20006` | code |
| `notes/character-runtime-unit-oam-bindings-20260730.md` | visual | `tools/butano/measure_s49_rule_ai_facing.py:26` | code |
| `notes/character-stats-addresses.md` | visual | `tools/export_content_pack.py:676`、`tools/export_content_pack.py:992`、`tools/export_content_pack.py:1025` | code |
| `notes/dialogue-format.md` | other | `tools/export_content_pack.py:428`、`tools/konoha_font.py:7` | code |
| `notes/dialogue-render-analysis.md` | other | `tools/analyze_dialogue_render.py:29` | code |
| `notes/dialogue-watch-record-bank.md` | other | `tools/mgba_trace_dialogue_writes.lua:48` | code |
| `notes/dialogue-watch-sb-struct.md` | other | `tools/mgba_trace_dialogue_writes.lua:40` | code |
| `notes/dialogue-watch-vram-glyph.md` | other | `tools/mgba_trace_dialogue_writes.lua:32` | code |
| `notes/dialogue-watch-vram-tilemap.md` | other | `tools/mgba_trace_dialogue_writes.lua:24` | code |
| `notes/dialogue-watch-wram.md` | other | `tools/README.md:866`、`tools/README.md:868`、`tools/mgba_trace_dialogue_writes.lua:16` | code |
| `notes/free-space.md` | other | `tools/import_chapter_scripts.py:50`、`tools/import_chapter_scripts.py:52`、`tools/import_dialogue_var.py:71` | code |
| `notes/macos-intel-runtime-preflight-20260715.md` | other | `tools/README.md:978` | markdown-mention |
| `notes/ninja-tool-addresses.md` | other | `sequel/content/battle-config/ninja-tool-identities.json:3` | code |
| `notes/positions-rom-source-20260710.md` | other | `tools/extract_positions.py:4`、`tools/extract_positions.py:266` | code |
| `notes/re-completion-audit.md` | other | `tools/audit_re_completion.py:292`、`tools/audit_re_completion.py:293`、`tools/completion_audit.py:6` | code |
| `notes/resource-locations.md` | other | `tools/README.md:305`、`tools/completion_audit.py:143`、`tools/completion_audit.py:144` | code |
| `notes/rom-gpu-copy-queue-inventory-20260730.md` | rom | `tools/export_rom_pram_halfword_writes.py:9` | code |
| `notes/runtime-verification-gates-20260710.md` | runtime | `tools/completion_audit.py:16`、`tools/l2_runtime_capture.py:6`、`tools/mgba_probe/l3_evidence_sweep.py:6` | code |
| `notes/scenario-45-safe-resume-20260719.md` | scenario | `sequel/content/battle_controller_transitions.json:437`、`sequel/content/battle_controller_transitions.json:439`、`sequel/content/battle_controller_transitions.json:465` | code |
| `notes/scenario-49-battle-14-runtime-20260720.md` | scenario | `butano-sequel/benchmark/tests/test_battle_result_settlement.cpp:5`、`tools/butano/verify_s49_battle_roster.py:103`、`tools/butano/verify_s49_battle_roster.py:113` | code |
| `notes/scenario-50-battle-15-runtime-20260720.md` | scenario | `tools/analyze_battle_resource_command_rules.py:235` | code |
| `notes/similar-tables.md` | other | `tools/README.md:819` | markdown-mention |
| `notes/u32-pointer-real-writeback-20260710.md` | other | `tools/table_registry.py:10` | code |
| `notes/units-unsafe-table-fix-20260711.md` | other | `tools/export_content_pack.py:424` | code |
| `notes/wasm-formation-probe-result-20260710.md` | other | `tools/completion_audit.py:729` | code |

## `not_applicable`（43）

| note | 类别 | 理由 | 判据 |
| --- | --- | --- | --- |
| `notes/butano-agent-timing-benchmark-20260721.md` | other | 主题是逆向工程自身的工程过程（子代理/基准/工作树/工具链/提交门禁），不是关于原版 ROM 的结论，与本复刻无关。 | Codex、benchmark、run_guarded、子代理、计时基准 |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/AGENTS.md` | other | 证据包内嵌的逆向树自身文件快照（AGENTS.md），不是新的 ROM 结论。 | notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/AGENTS.md |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | other | 证据包内嵌的逆向树自身文件快照（remaining-reverse-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | other | 证据包内嵌的逆向树自身文件快照（reverse-engineering-handoff-current-20260905.md），不是新的 ROM 结论。 | notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md` | other | 证据包内嵌的逆向树自身文件快照（reverse-engineering-proof-policy.md），不是新的 ROM 结论。 | notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/sequel-roadmap.md` | other | 证据包内嵌的逆向树自身文件快照（sequel-roadmap.md），不是新的 ROM 结论。 | notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/sequel-roadmap.md |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-bank-proof-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-battle-effect-fixed-roundtrip-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-battle-effect-fixed-roundtrip-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-battle-effect-fixed-roundtrip-20261001.md |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-partial-bank-joint-matrix-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-partial-bank-joint-matrix-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-partial-bank-joint-matrix-20261001.md |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-release-gate-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-release-gate-work-plan-20261001.md |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/AGENTS.md` | other | 证据包内嵌的逆向树自身文件快照（AGENTS.md），不是新的 ROM 结论。 | notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/AGENTS.md |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | other | 证据包内嵌的逆向树自身文件快照（remaining-reverse-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | other | 证据包内嵌的逆向树自身文件快照（reverse-engineering-handoff-current-20260905.md），不是新的 ROM 结论。 | notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/sequel-roadmap.md` | other | 证据包内嵌的逆向树自身文件快照（sequel-roadmap.md），不是新的 ROM 结论。 | notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/sequel-roadmap.md |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-bank-runtime-replay-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-bank-runtime-replay-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-bank-runtime-replay-20261001.md |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-cutscene-secondary-ptr-ab-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-cutscene-secondary-ptr-ab-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-cutscene-secondary-ptr-ab-20261001.md |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/AGENTS.md` | other | 证据包内嵌的逆向树自身文件快照（AGENTS.md），不是新的 ROM 结论。 | notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/AGENTS.md |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | other | 证据包内嵌的逆向树自身文件快照（remaining-reverse-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | other | 证据包内嵌的逆向树自身文件快照（reverse-engineering-handoff-current-20260905.md），不是新的 ROM 结论。 | notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md` | other | 证据包内嵌的逆向树自身文件快照（reverse-engineering-proof-policy.md），不是新的 ROM 结论。 | notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/sequel-roadmap.md` | other | 证据包内嵌的逆向树自身文件快照（sequel-roadmap.md），不是新的 ROM 结论。 | notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/sequel-roadmap.md |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-bank-proof-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-data-table-b-partial-bank-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-data-table-b-partial-bank-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-data-table-b-partial-bank-20261001.md |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/AGENTS.md` | other | 证据包内嵌的逆向树自身文件快照（AGENTS.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/AGENTS.md |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | other | 证据包内嵌的逆向树自身文件快照（remaining-reverse-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/remaining-reverse-work-plan-20261001.md |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | other | 证据包内嵌的逆向树自身文件快照（reverse-engineering-handoff-current-20260905.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/sequel-roadmap.md` | other | 证据包内嵌的逆向树自身文件快照（sequel-roadmap.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/sequel-roadmap.md |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-map-resource-fixed-roundtrip-20261002.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-map-resource-fixed-roundtrip-20261002.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-map-resource-fixed-roundtrip-20261002.md |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-release-gate-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/AGENTS.md` | other | 证据包内嵌的逆向树自身文件快照（AGENTS.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/AGENTS.md |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | other | 证据包内嵌的逆向树自身文件快照（remaining-reverse-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/remaining-reverse-work-plan-20261001.md |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | other | 证据包内嵌的逆向树自身文件快照（reverse-engineering-handoff-current-20260905.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/sequel-roadmap.md` | other | 证据包内嵌的逆向树自身文件快照（sequel-roadmap.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/sequel-roadmap.md |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/notes/rom-map-resource-relocation-roundtrip-20261002.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-map-resource-relocation-roundtrip-20261002.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/notes/rom-map-resource-relocation-roundtrip-20261002.md |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-release-gate-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/AGENTS.md` | other | 证据包内嵌的逆向树自身文件快照（AGENTS.md），不是新的 ROM 结论。 | notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/AGENTS.md |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | other | 证据包内嵌的逆向树自身文件快照（remaining-reverse-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | other | 证据包内嵌的逆向树自身文件快照（reverse-engineering-handoff-current-20260905.md），不是新的 ROM 结论。 | notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md` | other | 证据包内嵌的逆向树自身文件快照（reverse-engineering-proof-policy.md），不是新的 ROM 结论。 | notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/sequel-roadmap.md` | other | 证据包内嵌的逆向树自身文件快照（sequel-roadmap.md），不是新的 ROM 结论。 | notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/sequel-roadmap.md |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-bank-proof-work-plan-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-map-sprites-partial-bank-20261001.md` | rom | 证据包内嵌的逆向树自身文件快照（rom-map-sprites-partial-bank-20261001.md），不是新的 ROM 结论。 | notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-map-sprites-partial-bank-20261001.md |
| `notes/staged-artifact-policy-20260905.md` | other | 主题是逆向工程自身的工程过程（子代理/基准/工作树/工具链/提交门禁），不是关于原版 ROM 的结论，与本复刻无关。 | githooks、pre-commit、工作树、提交门禁、暂存、检查器 |

## `missing_evidence`（19）

| note | 类别 | 缺什么 | 理由 |
| --- | --- | --- | --- |
| `notes/evidence/reverse-work-plan-20261001-v1/plan.md` | other | 当前canonical：6,203,825已分类、87,631未知字节，1,763个未知段；SHA为；`b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`。；17个至少1KiB的段合计42,880B，占未知区约48.9%。其余44,751B分散在1,746段。 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/next-steps.md` | other | 1. A confirmed text pointer path from visible in-game UI/script to ROM offsets.；2. A confirmed chapter or event-script table.；3. A confirmed battle/unit/map configuration table. | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/remaining-runtime-bank-probes-20260713.md` | other | 1. 寻找自然产生 `0x80|skill_id` 的非教程战斗或组合候选 UI，并以；`0x08070906` 专属探针捕获真实 skill ID；；2. 从 actionable checkpoint 完成一次有效攻击，继续观察 battle-message 与 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/reverse-engineering-current-gaps-20260806.md` | other | 2026-08-11 已新增固定 boot interwork ARM 根闭包：唯一 Thumb BL→`BX pc`→ARM B；producer 静态绑定到 `0x0800024C`，独立 worklist 闭合 92 条 ARM 指令、8 个 block、；10 条 edge、0 个 frontier 及 9 个 literal，精确减少 unknown 414 字节。该成果不 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-ai-config-writer-preflight-20260930.md` | rom | 旧AI候选记录只突出source record+0E复制。不能把它当完整writer分母；至少还要处理；固定ROM base5411E4、0xAC stride的`+2`读链，以及上游RAM lookup/call/生命周期。；5411E4位于大unknown簇`53F89C..541368`内部，因此“大簇完全没有消费者锚点”的 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-ai-extra-pool-lifecycle-preflight-20260930.md` | rom | 本条自身声明结果尚未成立 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-animation-base-pairs-preflight-20261001.md` | rom | 1. 新池已有116个LDR形态。批量从固定来源CFG重枚举到626B4的真正r0/r1参数流，；固定全部候选、排除项与ROM target-limited caller分母；不能只硬编码这两个成功样例。；2. 冻结group、stack arguments和初始化的slot域。07105A令r2=0，071056/071058把8写 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-animation-interprocedural-identities-20261001.md` | rom | 尚未闭合；未晋升 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-bank-proof-work-plan-20261001.md` | rom | 1. **先做证据合同迁移包。** 以map-sprites旧样本为首个canary，新增wrapper/typed结果；时先写RED：缺field/record ID、错误bank SHA、archive变化、错路径及普通verified=true；都必须拒绝。GREEN只能声明record1/definition_ptr；只有证明覆盖整个固定分母才能 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-coroutine-record-lifecycle-preflight-20261001.md` | rom | 既有独立producer扫描重建：61D10只有616C0一个BL；61D7C有8个BL；61D8C有2个BL；（61D84、7C61C）；61E00有12个BL。没有重复新建全ROM扫描器。；新增目标7C5E8有5个BL形态：7BA0E、7BE36、7F0D6、7F10C、7F2B6。 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-fixed-text-route-preflight-20261001.md` | rom | 首BL目标 | site数 | 假设消费字节 | 验收前仍需补足 |；: | ---: | --- |；66758 / r0 | 13 | 346 | 来源raw verifier、完整消费者分母及独立参数流；桥接范围SHA匹配已有合同 | | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-later-cfg-renderer-consumers-preflight-20261001.md` | rom | 尚未闭合 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-low-script-fixed-consumers-preflight-20261001.md` | rom | 主枚举经heavy guard成功、exit0、非降级，约11.4s，观测峰值168MiB。；独立sidecar逐site重算PC-relative literal、exporter参数流和training语法，与verifier结果一致；；重算immutable unknown交集为12B。helpers原封不动，输入源码哈希另存。 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-open-root-and-large-candidate-review-20260905.md` | rom | Sol medium 从现有0902/0905 unknown-cluster记录只找到一个具有正向消费锚点、；预计超过1KiB的后续研究方向：AI配置表`[53F348,53F86C)`，旧估算unknown交集1316B。；`tools/analyze_battle_ai_utility_policy.py:27`固定基址与8×0xA8布局，126起有逐记录读取； | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-ram-protocol-tag-preflight-20261001.md` | rom | 优先冻结60条显示文本的来源/桥接合同，复用现有双parser与delta adapter，不另建解析器。；RAM标签只有在完成caller参数、所有相关RAM writer、stage/readiness及错误路径闭包后才准入。；若无法冻结这些状态，保留候选并搁置，不通过反复扩小窗口替代证明。 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-release-gate-work-plan-20261001.md` | rom | 1. **资源round-trip（固定7case）**：先修复上述失效证据和typed合同，再补audio/text/；maps/levels/story/characters对应的完整提取→修改→编码→回写→重读矩阵。六组图像族；通过不能直接把graphics整个case标covered，更不能代表另外六case。 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-renderer-excluded-roots-preflight-20260930.md` | rom | RED：新增测试先因缺少分析模块失败，原始red.log保留。GREEN：6/6通过，覆盖零值；操作数不能提前终止、截断/越界/未支持opcode/缺终止失败关闭、嵌套文本终止符、真实ROM；与CLI重放。整理后py_compile与限定路径diff检查通过。真实消费者重建包含独立旧CFG | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-renderer-handler-context-preflight-20260930.md` | rom | 未晋升 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |
| `notes/rom-task-callback-alignment-gap-candidate-20260905.md` | rom | 仅候选 | 本条自述为开放工作项（预检/计划/缺口清单，或明写结论未成立），证据尚未闭合，需回到逆向侧补齐。 |

## `needs_guard`（332）

| note | 类别 | 可转门禁的材料 | 理由 |
| --- | --- | --- | --- |
| `notes/alternate-chapter-runtime-probe-20260712.md` | other | data_contract | 已给出原版行为的可核验结论（14 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/audio-cue-semantics-20260713.md` | audio | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（163 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/audio-engine-runtime-chain-20260712.md` | audio | tick_cadence、data_contract | 已给出原版行为的可核验结论（32 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/audio-palette-identity-correction-20260711.md` | audio | data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/audio-tie-lifecycle-20260713.md` | audio | guard_condition、tick_cadence | 已给出原版行为的可核验结论（），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/auditor-module-failures-20261020.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（39 处 ROM 地址、26 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/auto-exit-prevention-mgba-compile-20260806.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/bank-player-visible-closure-plan-20260806.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址、5 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-action-detail-renderer-20260713.md` | battle | guard_condition、data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-controlled-phase-extension-20260809.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（3 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-controlled-runtime-20260801.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（1 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-direct-spawn-runtime-20260802.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-frame-phase-20260801.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（11 处 ROM 地址、1 个逆向成果族、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group1-pixel-ab-20260801.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（16 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group11-pixel-ab-20260801.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（7 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group12-group13-route-audit-20260802.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group13-pixel-ab-20260802.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（6 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group14-pixel-ab-20260801.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（7 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group15-allocator-side-runtime-20260801.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（6 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group15-natural-runtime-20260802.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（15 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group15-pixel-ab-20260802.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（5 处 ROM 地址、1 个逆向成果族、4 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group16-natural-pixel-ab-20260802.md` | visual | tick_cadence、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group17-natural-pixel-ab-20260802.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group18-controlled-pixel-ab-20260802.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（7 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group18-natural-pixel-ab-20260802.md` | visual | tick_cadence、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group2-pixel-ab-20260802.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（6 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group2-route-stop-20260802.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group3-controlled-pixel-ab-20260802.md` | visual | guard_condition、data_contract | 已给出原版行为的可核验结论（17 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group3-natural-expiry-phase-20260802.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（9 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group3-natural-pixel-ab-20260802.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（9 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group4-natural-pixel-ab-20260802.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（7 处 ROM 地址、4 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group5-pixel-ab-20260801.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group6-controlled-pixel-ab-20260809.md` | visual | tick_cadence、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-group6-entry-audit-20260806.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（114 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-groups7-12-controlled-pixel-ab-20260809.md` | visual | tick_cadence、data_contract | 已给出原版行为的可核验结论（6 处 ROM 地址、7 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-hardcoded-selector-producers-20260802.md` | visual | guard_condition、data_contract | 已给出原版行为的可核验结论（14 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-observed-frame-phases-20260801.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（3 处 ROM 地址、7 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-resource-pairs-export-20260729.md` | visual | tick_cadence、data_contract | 已给出原版行为的可核验结论（39 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-resource-relocation-20260731.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（7 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-resource-writeback-20260731.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（4 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-runtime-oam-bindings-20260801.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-runtime-oam-task-bindings-20260801.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（6 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-sequence-bindings-export-20260729.md` | visual | tick_cadence、data_contract | 已给出原版行为的可核验结论（59 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-sprite-animations-export-20260729.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（69 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-effect-template-consumer-20260711.md` | visual | data_contract | 已给出原版行为的可核验结论（11 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-encounters-story-visual-player-visible-20260809.md` | battle | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（26 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-presentation-glyphs-export-20260729.md` | battle | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（40 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-scenario-config.md` | battle | tick_cadence、data_contract | 已给出原版行为的可核验结论（70 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-start-control-flow-20260713.md` | battle | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（155 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-status-bars-export-20260730.md` | battle | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（24 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-visual-catalog-export-20260729.md` | visual | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battle-visual-runtime-timelines-export-20260729.md` | visual | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（7 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/battlefield-object-effect-chain-20260802.md` | battle | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（31 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/bg-resource-canvases-export-20260729.md` | visual | data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/bg-resource-relocation-20260731.md` | visual | guard_condition、data_contract | 已给出原版行为的可核验结论（5 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/bg-resource-writeback-20260731.md` | visual | guard_condition、data_contract | 已给出原版行为的可核验结论（1 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/bg-scene-selection-export-20260729.md` | visual | defect_semantics、data_contract | 已给出原版行为的可核验结论（34 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/build-api-ownership-20260713.md` | other | tick_cadence | 已给出原版行为的可核验结论（），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/build-artifact-cleanup-audit-20260729.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（8 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/butano-scenario-41-one-to-one-runtime-20260722.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、6 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/butano-scenario-41-runtime-20260721.md` | other | guard_condition、defect_semantics、tick_cadence | 已给出原版行为的可核验结论（），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/chapter-entry-points.md` | other | defect_semantics、data_contract | 已给出原版行为的可核验结论（28 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/chapter-flow-format.md` | other | data_contract | 已给出原版行为的可核验结论（48 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/chapter-flow-runtime-chain-20260712.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（44 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/chapter-script-observed-subset-20260713.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（44 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/chapter-script-production-writeback-20260713.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（17 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/character-battle-graphics-pixel-ab-20260801.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/character-battle-graphics-writeback-20260731.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/character-battle-palette-writeback-20260731.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（1 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/character-battle-structure-writeback-20260731.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/character-battle-visual-resource-matrix-20260801.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/character-battle-visuals-export-20260729.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（26 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/character-growth-runtime-chain-20260711.md` | visual | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（47 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/character-runtime-oam-bindings-20260730.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/character-runtime-oam-task-bindings-20260730.md` | visual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（64 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/codex-reentry-audit-20260712.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/current-re-progress-20260711.md` | other | guard_condition、data_contract | 已给出原版行为的可核验结论（24 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/cutscene-obj-bundle-relocation-20260731.md` | presentation | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/cutscene-obj-export-20260729.md` | presentation | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（35 处 ROM 地址、1 个逆向成果族、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/cutscene-visual-resource-consumer-20260712.md` | presentation | data_contract | 已给出原版行为的可核验结论（21 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/cutscene-visual-resource-player-visible-20260809.md` | presentation | guard_condition、data_contract | 已给出原版行为的可核验结论（17 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/d0-bank-exhaustion-gate-20261020.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址、9 个逆向成果族、6 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/debugging-record.md` | other | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（47 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-caller-runtime.md` | other | tick_cadence | 已给出原版行为的可核验结论（54 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-font-atlas-export-20260729.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（50 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-font-table-discovery-20260703.md` | other | data_contract | 已给出原版行为的可核验结论（65 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-function-analysis.md` | other | tick_cadence、data_contract | 已给出原版行为的可核验结论（80 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-mapping-blocker-20260702.md` | other | defect_semantics、data_contract | 已给出原版行为的可核验结论（23 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-mapping-decoder-20260702.md` | other | guard_condition、data_contract | 已给出原版行为的可核验结论（19 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-mapping-progress-20260702.md` | other | data_contract | 已给出原版行为的可核验结论（33 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-memory-analysis.md` | other | defect_semantics | 已给出原版行为的可核验结论（42 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-ram-structures.md` | other | tick_cadence、data_contract | 已给出原版行为的可核验结论（23 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-write-path.md` | other | tick_cadence | 已给出原版行为的可核验结论（32 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dialogue-writer-addresses.md` | other | data_contract | 已给出原版行为的可核验结论（21 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/diff-dialogue-2160-2340-vram.md` | other | — | 已给出原版行为的可核验结论（8 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/diff-dialogue-2160-2340-wram.md` | other | — | 已给出原版行为的可核验结论（5 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/diff-dialogue-2340-2520-vram.md` | other | — | 已给出原版行为的可核验结论（7 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/diff-dialogue-2340-2520-wram.md` | other | — | 已给出原版行为的可核验结论（6 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/direct-image-palette-relocation-20260731.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/directsound-envelope-20260713.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/directsound-mixer-runtime-chain-20260713.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（11 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/directsound-pitch-step-20260713.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（17 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/directsound-volume-pan-20260713.md` | other | data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/dynamic-verification-audit.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（112 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/editor-isolated-writeback-smoke-20260713.md` | other | guard_condition、data_contract | 已给出原版行为的可核验结论（1 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/evidence/reverse-proof-update-20261019-v1/first-run-venv-interpreter/README.md` | other | guard_condition、data_contract | 已给出原版行为的可核验结论（1 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/evidence/reverse-proof-update-20261020-v2/三包接入施工单-raw.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（28 处 ROM 地址、17 个逆向成果族、4 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/evidence/rom-animation-pool-lifecycle-20261001-v1/README.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/evidence/rom-cutscene-secondary-ptr-shared-lock-20261001-v1/contract-tier1-20261001-v1/note.md` | other | guard_condition、data_contract | 已给出原版行为的可核验结论（15 处 ROM 地址、1 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/evidence/rom-menu-gfx-pointer-ab-20261001-v1/contract-20261001-v1/note.md` | other | guard_condition、data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/exporter-root-deletion-incident-20260809.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（1 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/first-battle-savestate-checkpoints-20260712.md` | other | tick_cadence | 已给出原版行为的可核验结论（10 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/four-decisions-20261020.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（9 处 ROM 地址、5 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/function-pointer-runtime-probe-20260713.md` | other | defect_semantics、data_contract | 已给出原版行为的可核验结论（16 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/generic-sprite-bundle-relocation-20260731.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（4 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/group12-natural-entry-ai-observer-20260806.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（12 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/handover-20261020-reverse-tree.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（5 处 ROM 地址、1 个逆向成果族、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/headless-workflow.md` | other | tick_cadence | 已给出原版行为的可核验结论（24 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/initializer-resource-pack-export-20260730.md` | other | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/legacy-artifact-acceptance-20260905.md` | other | guard_condition、defect_semantics | 已给出原版行为的可核验结论（3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/levels-runtime-probe-20260713.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（44 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/line-a-progress-20261019.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（85 处 ROM 地址、20 个逆向成果族、9 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/live-ledger-identity-repair-20261020.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（6 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/m4a-channel-allocation-20260713.md` | other | — | 已给出原版行为的可核验结论（14 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/m4a-command-vm-20260713.md` | other | tick_cadence、data_contract | 已给出原版行为的可核验结论（1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/m4a-emulator-differential-20260713.md` | other | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（15 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/m4a-full-song-render-20260713.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（3 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/m4a-player-slot-control-flow-20260713.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（71 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/m4a-player-slot-runtime-differential-20260713.md` | other | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/m4a-runtime-channel-wiring-20260713.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/m4a-soundmain-scheduler-20260713.md` | other | tick_cadence | 已给出原版行为的可核验结论（12 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/m4a-track-register-state-20260713.md` | other | tick_cadence | 已给出原版行为的可核验结论（1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map-addresses.md` | map | data_contract | 已给出原版行为的可核验结论（36 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map-canvases-export-20260729.md` | map | guard_condition、data_contract | 已给出原版行为的可核验结论（3 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map-events-e4-player-visible-20260809.md` | map | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map-format.md` | map | data_contract | 已给出原版行为的可核验结论（37 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map-position-pc-probe-20260710.md` | map | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（18 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map-resource-relocation-20260731.md` | map | guard_condition、data_contract | 已给出原版行为的可核验结论（27 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map-resource-writeback-20260730.md` | map | guard_condition、data_contract | 已给出原版行为的可核验结论（1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map-sprites-definition-player-visible-20260809.md` | map | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map41-primary-layout-pixel-ab-20260801.md` | map | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/map41-visual-resource-matrix-20260801.md` | map | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（16 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/maps-runtime-fields-20260711.md` | map | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（26 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/memory-incident-root-cause-20260714.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（5 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/menu-portrait-export-20260729.md` | presentation | data_contract | 已给出原版行为的可核验结论（12 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/menu-portrait-pixel-ab-20260801.md` | presentation | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（11 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/menu-portrait-relocation-20260731.md` | presentation | guard_condition、data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/menu-portrait-writeback-20260730.md` | presentation | guard_condition、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/motion-effect-parameter-player-visible-20260809.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（7 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/natural-skill-detail-runtime-20260713.md` | other | data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/offline-e2e-smoke-20260713.md` | other | data_contract | 已给出原版行为的可核验结论（1 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/overlapping-visual-tables-audit-20260712.md` | other | — | 已给出原版行为的可核验结论（20 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/overview-gradient-overlay-export-20260730.md` | overview | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（23 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/palettes-bank-player-visible-attempt-20260806.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（4 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/partial-item-inventory.md` | other | — | 已给出原版行为的可核验结论（11 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/partial-random-encounter.md` | other | data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/patch-generator-audit.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（72 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/portrait-palette-producers-20260730.md` | presentation | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（50 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/profile-text-runtime-probe-20260713.md` | other | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（17 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/psg-noise-runtime-chain-20260713.md` | other | tick_cadence | 已给出原版行为的可核验结论（6 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-lz77-graphics-relocation-20260731.md` | residual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（5 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-text-bg-tilemap-relocation-20260731.md` | residual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（16 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-text-bg-tilemap-resource-ownership-20260731.md` | residual | tick_cadence、data_contract | 已给出原版行为的可核验结论（22 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-wram-derived-tilemap-relocation-20260731.md` | residual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（37 处 ROM 地址、1 个逆向成果族、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-wram-tilemap-abi-20260731.md` | residual | tick_cadence、data_contract | 已给出原版行为的可核验结论（14 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-wram-tilemap-pixel-ab-20260801.md` | residual | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（16 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-wram-tilemap-relocation-20260731.md` | residual | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（12 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-wram-tilemap-resource-ownership-20260731.md` | residual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（18 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-wram-tilemap-runtime-reachability-20260731.md` | residual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（21 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/residual-wram-transformed-tilemap-runtime-20260801.md` | residual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（14 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/resource-pointer-alias-correction-20260730.md` | other | defect_semantics、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/resource-table-596F98.md` | other | data_contract | 已给出原版行为的可核验结论（38 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/reverse-method-review-20261002.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（12 处 ROM 地址、5 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-ai-entry-local-domains-20260930.md` | rom | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（5 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-ai-producer-and-pool-alias-20260930.md` | rom | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-ai-renderer-script-dependencies-20260930.md` | rom | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（4 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-alternate-dialogue-table-20260902.md` | rom | data_contract | 已给出原版行为的可核验结论（18 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-callee-effects-20261001.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-caller-predecessor-20261001.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-critical-writers-20261001.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-full-renderer-20261001.md` | rom | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-irq-arm-native-20261001.md` | rom | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-object-lifecycle-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-object-native-20261001.md` | rom | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-pool-caller-screen-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-pool-lifecycle-20261001.md` | rom | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（4 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-save-source-20261001.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-upstream-closure-20261001.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-animation-writer-domain-20261001.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（4 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-bank-runtime-replay-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-battle-condition-result-text-20260902.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-battle-distance-dispatcher-cfg-20260902.md` | rom | guard_condition | 已给出原版行为的可核验结论（16 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-battle-effect-fixed-roundtrip-20261001.md` | rom | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、4 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-battle-message-text-inventory-20260811.md` | rom | data_contract | 已给出原版行为的可核验结论（17 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-boot-interwork-20260811.md` | rom | — | 已给出原版行为的可核验结论（21 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-boot-register-init-dependency-cfg-20260905.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-bounded-index-u16-pair-table-20260904.md` | rom | data_contract | 已给出原版行为的可核验结论（16 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cfg-proven-roots-20260811.md` | rom | guard_condition | 已给出原版行为的可核验结论（6 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cfg-proven-roots-v13-20260830.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cfg-proven-roots-v14-20260830.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（24 处 ROM 地址、1 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cfg-proven-roots-v15-20260830.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cfg-proven-roots-v2-20260812.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cfg-proven-roots-v20-20260905.md` | rom | guard_condition | 已给出原版行为的可核验结论（10 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cfg-proven-roots-v21-20260905.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（5 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cfg-proven-roots-v3-v4-20260813.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（29 处 ROM 地址、5 个逆向成果族、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-chapter-script-consumer-roots-20260902.md` | rom | — | 已给出原版行为的可核验结论（23 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-chapter-script-inventory-20260809.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（26 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cutscene-secondary-ptr-ab-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（11 处 ROM 地址、3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-cutscene-secondary-ptr-contract-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（15 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-data-table-b-partial-bank-20261001.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（6 处 ROM 地址、3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-direct-cpuset-inventory-survey-20260730.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址、5 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-direct-dma-inventory-survey-20260730.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（21 处 ROM 地址、4 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-display-text-delta-tier1-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（3 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-display-text-parameter-flow-tdd-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（4 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-evidence-selector-repair-20260905.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-expansion-character-bundle-relocation-20260731.md` | rom | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（26 处 ROM 地址、5 个逆向成果族、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-finite-lookup-scope-review-20260905.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（18 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-fixed-animation-descriptor-groups-20260902.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（11 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-fixed-consumer-text-inventory-20260811.md` | rom | defect_semantics、data_contract | 已给出原版行为的可核验结论（42 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-fixed-index-u8-tail-20260905.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（15 处 ROM 地址、5 个逆向成果族、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-fixed-pair-tables-20260904.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-large-unknown-anchor-screen-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-low-script-delta-tier1-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（4 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-m4a-initializer-chain-20260829.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（31 处 ROM 地址、4 个逆向成果族、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-map-resource-fixed-roundtrip-20261002.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-map-resource-relocation-roundtrip-20261002.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-map-sprites-partial-bank-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-menu-gfx-pointer-ab-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-menu-portrait-palette-inventory-20260820.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（4 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-mp2k-dispatcher-20260829.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（40 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-mp2k-note-allocator-20260829.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（28 处 ROM 地址、3 个逆向成果族、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-mplaymain-scheduler-20260828.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（26 处 ROM 地址、4 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-partial-bank-joint-matrix-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-pointer-lz77-graphics-preview-20260730.md` | rom | tick_cadence、data_contract | 已给出原版行为的可核验结论（45 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-pointer-lz77-inventory-export-20260730.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-prebattle-menu-controller-cfg-20260905.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（14 处 ROM 地址、4 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-referenced-text-slot-padding-20260820.md` | rom | guard_condition、defect_semantics | 已给出原版行为的可核验结论（4 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-renderer-batch-plan-20261001.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-renderer-flow-cost-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-renderer-records-delta-tier1-20261001.md` | rom | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（4 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-renderer-source-plan-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-renderer-source-replay-20261001.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-renderer-text-inventory-20260809.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（7 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-scene-source-closures-20260905.md` | rom | guard_condition | 已给出原版行为的可核验结论（4 处 ROM 地址、6 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-scene-visual-source-ranges-20260820.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（4 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-selector-code-windows-20260820.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（20 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-selector-direct-source-records-20260820.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、4 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-selector-text-bindings-20260811.md` | rom | data_contract | 已给出原版行为的可核验结论（23 处 ROM 地址、7 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-small-cfg-dependency-batch-20260905.md` | rom | guard_condition、defect_semantics | 已给出原版行为的可核验结论（10 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-small-cfg-dependency-tier2-20260930.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（6 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-soundmain-relocated-cfg-20260828.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（29 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-staged-gpu-copy-inventory-20260730.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（24 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-story-callback-dependency-closures-20260905.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、4 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-story-next-dependency-cfg-20260905.md` | rom | guard_condition | 已给出原版行为的可核验结论（21 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-story-selector-dependency-cfg-20260905.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、4 个逆向成果族、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-strided-prefix-local-read-domain-20260905.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（16 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-task-callback-078e38-closure-20260905.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-training-text-script-inventory-20260811.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-u8-indexed-u16-pair-lookup-20260827.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（27 处 ROM 地址、3 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-unknown-candidate-59eae0-negative-evidence-20260827.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（66 处 ROM 地址、2 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-unknown-cluster-refresh-20260901.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（48 处 ROM 地址、6 个逆向成果族、4 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-unknown-cluster-refresh-20260902.md` | rom | guard_condition、data_contract | 已给出原版行为的可核验结论（158 处 ROM 地址、7 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-unknown-cluster-refresh-20260905.md` | rom | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（40 处 ROM 地址、3 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-v17-v18-helper-cfg-20260904.md` | rom | — | 已给出原版行为的可核验结论（14 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-value-range-text-inventory-20260811.md` | rom | data_contract | 已给出原版行为的可核验结论（24 处 ROM 地址、2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/rom-verifier-runtime-inputs-20260905.md` | rom | data_contract | 已给出原版行为的可核验结论（4 个逆向成果族），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/runtime-bg-composites-20260730.md` | runtime | defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/runtime-checkpoints-data-integrity-issue-20260806.md` | runtime | guard_condition、defect_semantics、tick_cadence | 已给出原版行为的可核验结论（3 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/runtime-font-tile-provenance-20260730.md` | runtime | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（5 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/runtime-handler-pair-consumer-20260712.md` | runtime | data_contract | 已给出原版行为的可核验结论（15 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/runtime-layer-static-provenance-20260730.md` | runtime | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/runtime-mode0-screen-compositor-20260730.md` | runtime | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（3 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/runtime-state-entry-audit-20260710.md` | runtime | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（14 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/sappy-engine-master-enable-runtime-20260809.md` | other | guard_condition、data_contract | 已给出原版行为的可核验结论（13 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/save-descriptor-layout-correction-20260712.md` | other | tick_cadence、data_contract | 已给出原版行为的可核验结论（28 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/save-state-wasm-probe-20260711.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（20 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scan-summary.md` | other | data_contract | 已给出原版行为的可核验结论（56 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-41-battle-entry-runtime-20260713.md` | scenario | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（32 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-41-completion-runtime-20260718.md` | scenario | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（9 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-41-controller-path-runtime-20260715.md` | scenario | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（18 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-41-movedone-runtime-20260717.md` | scenario | guard_condition、defect_semantics、tick_cadence | 已给出原版行为的可核验结论（9 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-41-player-control-runtime-20260715.md` | scenario | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（22 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-41-prebattle-menu-macos-20260715.md` | scenario | guard_condition、data_contract | 已给出原版行为的可核验结论（18 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-41-prebattle-to-controller-macos-20260715.md` | scenario | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（37 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-41-savestate-context-reanalysis-20260715.md` | scenario | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（70 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-42-progression-runtime-20260718.md` | scenario | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（6 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-43-progression-runtime-20260718.md` | scenario | guard_condition、defect_semantics、tick_cadence | 已给出原版行为的可核验结论（1 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-44-progression-runtime-20260718.md` | scenario | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（1 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-46-entry-runtime-20260719.md` | scenario | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-47-entry-runtime-20260720.md` | scenario | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scenario-48-academy-runtime-20260720.md` | scenario | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scene-visual-composites-export-20260730.md` | map | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（22 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scene-visual-pack-export-20260729.md` | map | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（53 处 ROM 地址、1 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/scene-visual-transition-timelines-20260730.md` | map | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（11 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/skill-template-consumer-semantics-20260713.md` | other | tick_cadence、data_contract | 已给出原版行为的可核验结论（23 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/skill-template-identity-20260711.md` | other | data_contract | 已给出原版行为的可核验结论（12 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/skill-template-ui-probe-20260712.md` | other | data_contract | 已给出原版行为的可核验结论（32 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/sprite-definition-animations-export-20260729.md` | visual | tick_cadence、data_contract | 已给出原版行为的可核验结论（9 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/sprite-definition-runtime-chain-20260729.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（41 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/static-bank-identity-corrections-20260713.md` | other | data_contract | 已给出原版行为的可核验结论（15 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/story-bank-identity-correction-20260712.md` | presentation | data_contract | 已给出原版行为的可核验结论（21 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/story-scene-layer-bindings-20260729.md` | presentation | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（25 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/story-scene-timelines-export-20260729.md` | presentation | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（15 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/story-visual-descriptor-consumer-20260712.md` | presentation | data_contract | 已给出原版行为的可核验结论（18 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/story-visual-layer-export-20260729.md` | presentation | data_contract | 已给出原版行为的可核验结论（26 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/story-visual-resource-relocation-20260731.md` | presentation | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（9 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/strict-battle-arrival-gate-20260712.md` | other | — | 已给出原版行为的可核验结论（2 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/text-and-battle-visual-consumers-20260713.md` | other | data_contract | 已给出原版行为的可核验结论（36 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/text-regions.md` | other | data_contract | 已给出原版行为的可核验结论（12 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/tier2-threshold-policy-source-20261020.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（6 处 ROM 地址、9 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/tile-asset-resource-relocation-20260731.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（4 处 ROM 地址、1 个逆向成果族、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/tile-assets-bg-export-20260729.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/tile-assets-descriptor-player-visible-20260809.md` | visual | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（9 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/tileset-extraction-correction-20260712.md` | visual | guard_condition | 已给出原版行为的可核验结论（9 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/tutorial-victory-save-load-runtime-20260712.md` | other | data_contract | 已给出原版行为的可核验结论（9 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/unit-id-mapping-analysis.md` | other | data_contract | 已给出原版行为的可核验结论（22 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/unit-skill-addresses.md` | other | data_contract | 已给出原版行为的可核验结论（20 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/unknown-bgm-sfx.md` | other | data_contract | 已给出原版行为的可核验结论（5 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/unknown-item-inventory.md` | other | — | 已给出原版行为的可核验结论（18 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/unknown-random-encounter.md` | other | data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/unknown-save-state.md` | other | — | 已给出原版行为的可核验结论（11 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/unresolved-lz77-palette-survey-20260730.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（49 处 ROM 地址、1 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/variable-dialogue-relocation-20260712.md` | other | guard_condition、data_contract | 已给出原版行为的可核验结论（16 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/vram-safe-lz77-runtime-20260801.md` | other | guard_condition、defect_semantics、data_contract | 已给出原版行为的可核验结论（2 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/wasm-formation-navigation-probe-20260710.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（12 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/wasm-runtime-api-audit-20260710.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/windows-porting-20261020.md` | other | guard_condition、data_contract | 已给出原版行为的可核验结论（2 个逆向成果族、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/world-map-background-export-20260729.md` | map | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（37 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/world-map-background-relocation-20260731.md` | map | guard_condition、defect_semantics、tick_cadence、data_contract | 已给出原版行为的可核验结论（17 处 ROM 地址、1 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/world-map-page0-pixel-ab-20260801.md` | map | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（10 处 ROM 地址、2 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/world-map-runtime-composition-20260729.md` | map | guard_condition、tick_cadence、data_contract | 已给出原版行为的可核验结论（8 处 ROM 地址、3 个产物目录），本树尚未把它变成门禁，是 M1/M2 的原料。 |
| `notes/writeback-experiment-00076D.md` | other | data_contract | 已给出原版行为的可核验结论（3 处 ROM 地址），本树尚未把它变成门禁，是 M1/M2 的原料。 |

## `needs_human_review`（13）

| note | 类别 | 可转门禁的材料 | 理由 |
| --- | --- | --- | --- |
| `notes/butano-battle-architecture-implementation-20260722.md` | other | guard_condition、tick_cadence、data_contract | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/butano-battle-domain-rewrite-20260723.md` | other | guard_condition、tick_cadence、data_contract | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/butano-battle-flow-video-review-20260722.md` | other | guard_condition、tick_cadence、data_contract | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/butano-battle-video-frame-analysis-20260722.md` | other | guard_condition、defect_semantics、tick_cadence、data_contract | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/butano-deployment-runtime-20260721.md` | other | guard_condition、defect_semantics | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/evidence/reverse-throughput-20261019-v1/throughput.md` | other | guard_condition | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/legacy-generator-safety-20260711.md` | other | data_contract | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/local-mgba-build.md` | other | guard_condition、defect_semantics | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/mgba-threaded-fastforward-fix.md` | other | defect_semantics、tick_cadence | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/ocr-dialogue-report.md` | other | — | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/ocr-longwalk-report.md` | other | — | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/ocr-newgame-report.md` | other | — | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |
| `notes/reverse-engineering-progress-snapshot-20260802.md` | other | guard_condition、tick_cadence、data_contract | 既没有构建链引用，也没有原版行为证据（无地址/成果族/产物引用），也不满足开放工作项或逆向工程自身流程的特征，自动判读不了。 |

## 全部条目

| note | 桶 | 索引前状态 | 类别 |
| --- | --- | --- | --- |
| `notes/addresses.md` | `implemented_in_code` | `build` | other |
| `notes/alternate-chapter-runtime-probe-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/audio-cue-semantics-20260713.md` | `needs_guard` | `local_artifact` | audio |
| `notes/audio-engine-runtime-chain-20260712.md` | `needs_guard` | `local_artifact` | audio |
| `notes/audio-palette-identity-correction-20260711.md` | `needs_guard` | `local_artifact` | audio |
| `notes/audio-tie-lifecycle-20260713.md` | `needs_guard` | `doc` | audio |
| `notes/auditor-module-failures-20261020.md` | `needs_guard` | `none` | other |
| `notes/auto-exit-prevention-mgba-compile-20260806.md` | `needs_guard` | `none` | other |
| `notes/bank-player-visible-closure-plan-20260806.md` | `needs_guard` | `none` | other |
| `notes/battle-action-detail-renderer-20260713.md` | `needs_guard` | `local_artifact` | battle |
| `notes/battle-config-format.md` | `implemented_in_code` | `build` | battle |
| `notes/battle-config-unsafe-template-fix-20260710.md` | `implemented_in_code` | `build` | battle |
| `notes/battle-effect-controlled-phase-extension-20260809.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-controlled-runtime-20260801.md` | `needs_guard` | `doc` | visual |
| `notes/battle-effect-direct-spawn-runtime-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-frame-phase-20260801.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group1-pixel-ab-20260801.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group11-pixel-ab-20260801.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group12-group13-route-audit-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group13-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group14-pixel-ab-20260801.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group15-allocator-side-runtime-20260801.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group15-natural-runtime-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group15-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group16-natural-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group17-natural-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group18-controlled-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group18-natural-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group2-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group2-route-stop-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group3-controlled-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group3-natural-expiry-phase-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group3-natural-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group4-natural-pixel-ab-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group5-pixel-ab-20260801.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group6-controlled-pixel-ab-20260809.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-group6-entry-audit-20260806.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-groups7-12-controlled-pixel-ab-20260809.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-hardcoded-selector-producers-20260802.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-observed-frame-phases-20260801.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-resource-pairs-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/battle-effect-resource-relocation-20260731.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-resource-writeback-20260731.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-runtime-oam-bindings-20260801.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-runtime-oam-task-bindings-20260801.md` | `needs_guard` | `none` | visual |
| `notes/battle-effect-sequence-bindings-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/battle-effect-sprite-animations-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/battle-effect-template-consumer-20260711.md` | `needs_guard` | `local_artifact` | visual |
| `notes/battle-encounters-story-visual-player-visible-20260809.md` | `needs_guard` | `none` | battle |
| `notes/battle-presentation-glyphs-export-20260729.md` | `needs_guard` | `local_artifact` | battle |
| `notes/battle-scenario-config.md` | `needs_guard` | `local_artifact` | battle |
| `notes/battle-start-control-flow-20260713.md` | `needs_guard` | `local_artifact` | battle |
| `notes/battle-status-bars-export-20260730.md` | `needs_guard` | `test` | battle |
| `notes/battle-system-restoration-evidence-20260723.md` | `implemented_in_code` | `build` | battle |
| `notes/battle-visual-catalog-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/battle-visual-runtime-timelines-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/battlefield-object-effect-chain-20260802.md` | `needs_guard` | `none` | battle |
| `notes/bg-resource-canvases-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/bg-resource-relocation-20260731.md` | `needs_guard` | `none` | visual |
| `notes/bg-resource-writeback-20260731.md` | `needs_guard` | `none` | visual |
| `notes/bg-scene-selection-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/build-api-ownership-20260713.md` | `needs_guard` | `doc` | other |
| `notes/build-artifact-cleanup-audit-20260729.md` | `needs_guard` | `doc` | other |
| `notes/butano-agent-timing-benchmark-20260721.md` | `not_applicable` | `doc` | other |
| `notes/butano-battle-architecture-implementation-20260722.md` | `needs_human_review` | `doc` | other |
| `notes/butano-battle-domain-rewrite-20260723.md` | `needs_human_review` | `test` | other |
| `notes/butano-battle-flow-video-review-20260722.md` | `needs_human_review` | `doc` | other |
| `notes/butano-battle-video-frame-analysis-20260722.md` | `needs_human_review` | `doc` | other |
| `notes/butano-deployment-runtime-20260721.md` | `needs_human_review` | `doc` | other |
| `notes/butano-scenario-41-one-to-one-runtime-20260722.md` | `needs_guard` | `local_artifact` | other |
| `notes/butano-scenario-41-runtime-20260721.md` | `needs_guard` | `test` | other |
| `notes/chapter-entry-points.md` | `needs_guard` | `local_artifact` | other |
| `notes/chapter-flow-format.md` | `needs_guard` | `local_artifact` | other |
| `notes/chapter-flow-runtime-chain-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/chapter-script-observed-subset-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/chapter-script-production-writeback-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/character-battle-graphics-pixel-ab-20260801.md` | `needs_guard` | `none` | visual |
| `notes/character-battle-graphics-writeback-20260731.md` | `needs_guard` | `none` | visual |
| `notes/character-battle-palette-writeback-20260731.md` | `needs_guard` | `doc` | visual |
| `notes/character-battle-structure-writeback-20260731.md` | `needs_guard` | `none` | visual |
| `notes/character-battle-visual-resource-matrix-20260801.md` | `needs_guard` | `test` | visual |
| `notes/character-battle-visuals-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/character-definition-source-20260711.md` | `implemented_in_code` | `build` | visual |
| `notes/character-growth-runtime-chain-20260711.md` | `needs_guard` | `local_artifact` | visual |
| `notes/character-runtime-oam-bindings-20260730.md` | `needs_guard` | `none` | visual |
| `notes/character-runtime-oam-task-bindings-20260730.md` | `needs_guard` | `none` | visual |
| `notes/character-runtime-unit-oam-bindings-20260730.md` | `implemented_in_code` | `build` | visual |
| `notes/character-stats-addresses.md` | `implemented_in_code` | `build` | visual |
| `notes/codex-reentry-audit-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/current-re-progress-20260711.md` | `needs_guard` | `local_artifact` | other |
| `notes/cutscene-obj-bundle-relocation-20260731.md` | `needs_guard` | `none` | presentation |
| `notes/cutscene-obj-export-20260729.md` | `needs_guard` | `local_artifact` | presentation |
| `notes/cutscene-visual-resource-consumer-20260712.md` | `needs_guard` | `local_artifact` | presentation |
| `notes/cutscene-visual-resource-player-visible-20260809.md` | `needs_guard` | `none` | presentation |
| `notes/d0-bank-exhaustion-gate-20261020.md` | `needs_guard` | `none` | other |
| `notes/debugging-record.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-caller-runtime.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-font-atlas-export-20260729.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-font-table-discovery-20260703.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-format.md` | `implemented_in_code` | `build` | other |
| `notes/dialogue-function-analysis.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-mapping-blocker-20260702.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-mapping-decoder-20260702.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-mapping-progress-20260702.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-memory-analysis.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-ram-structures.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-render-analysis.md` | `implemented_in_code` | `build` | other |
| `notes/dialogue-watch-record-bank.md` | `implemented_in_code` | `build` | other |
| `notes/dialogue-watch-sb-struct.md` | `implemented_in_code` | `build` | other |
| `notes/dialogue-watch-vram-glyph.md` | `implemented_in_code` | `build` | other |
| `notes/dialogue-watch-vram-tilemap.md` | `implemented_in_code` | `build` | other |
| `notes/dialogue-watch-wram.md` | `implemented_in_code` | `build` | other |
| `notes/dialogue-write-path.md` | `needs_guard` | `local_artifact` | other |
| `notes/dialogue-writer-addresses.md` | `needs_guard` | `local_artifact` | other |
| `notes/diff-dialogue-2160-2340-vram.md` | `needs_guard` | `local_artifact` | other |
| `notes/diff-dialogue-2160-2340-wram.md` | `needs_guard` | `local_artifact` | other |
| `notes/diff-dialogue-2340-2520-vram.md` | `needs_guard` | `local_artifact` | other |
| `notes/diff-dialogue-2340-2520-wram.md` | `needs_guard` | `local_artifact` | other |
| `notes/direct-image-palette-relocation-20260731.md` | `needs_guard` | `none` | other |
| `notes/directsound-envelope-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/directsound-mixer-runtime-chain-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/directsound-pitch-step-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/directsound-volume-pan-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/dynamic-verification-audit.md` | `needs_guard` | `local_artifact` | other |
| `notes/editor-isolated-writeback-smoke-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/evidence/reverse-proof-update-20261019-v1/first-run-venv-interpreter/README.md` | `needs_guard` | `none` | other |
| `notes/evidence/reverse-proof-update-20261020-v2/三包接入施工单-raw.md` | `needs_guard` | `none` | other |
| `notes/evidence/reverse-throughput-20261019-v1/throughput.md` | `needs_human_review` | `none` | other |
| `notes/evidence/reverse-work-plan-20261001-v1/plan.md` | `missing_evidence` | `none` | other |
| `notes/evidence/rom-animation-pool-lifecycle-20261001-v1/README.md` | `needs_guard` | `none` | other |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/AGENTS.md` | `not_applicable` | `none` | other |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/docs/sequel-roadmap.md` | `not_applicable` | `test` | other |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-battle-effect-fixed-roundtrip-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-partial-bank-joint-matrix-20261001.md` | `not_applicable` | `doc` | rom |
| `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/AGENTS.md` | `not_applicable` | `none` | other |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/docs/sequel-roadmap.md` | `not_applicable` | `test` | other |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-bank-runtime-replay-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-cutscene-secondary-ptr-ab-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-cutscene-secondary-ptr-shared-lock-20261001-v1/contract-tier1-20261001-v1/note.md` | `needs_guard` | `none` | other |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/AGENTS.md` | `not_applicable` | `none` | other |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/docs/sequel-roadmap.md` | `not_applicable` | `test` | other |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-data-table-b-partial-bank-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/AGENTS.md` | `not_applicable` | `none` | other |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/docs/sequel-roadmap.md` | `not_applicable` | `test` | other |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-map-resource-fixed-roundtrip-20261002.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/AGENTS.md` | `not_applicable` | `none` | other |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/docs/sequel-roadmap.md` | `not_applicable` | `test` | other |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/notes/rom-map-resource-relocation-roundtrip-20261002.md` | `not_applicable` | `doc` | rom |
| `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/AGENTS.md` | `not_applicable` | `none` | other |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/remaining-reverse-work-plan-20261001.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/reverse-engineering-handoff-current-20260905.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/reverse-engineering-proof-policy.md` | `not_applicable` | `doc` | other |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/docs/sequel-roadmap.md` | `not_applicable` | `test` | other |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-map-sprites-partial-bank-20261001.md` | `not_applicable` | `none` | rom |
| `notes/evidence/rom-menu-gfx-pointer-ab-20261001-v1/contract-20261001-v1/note.md` | `needs_guard` | `none` | other |
| `notes/exporter-root-deletion-incident-20260809.md` | `needs_guard` | `none` | other |
| `notes/first-battle-savestate-checkpoints-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/four-decisions-20261020.md` | `needs_guard` | `none` | other |
| `notes/free-space.md` | `implemented_in_code` | `build` | other |
| `notes/function-pointer-runtime-probe-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/generic-sprite-bundle-relocation-20260731.md` | `needs_guard` | `none` | other |
| `notes/group12-natural-entry-ai-observer-20260806.md` | `needs_guard` | `none` | other |
| `notes/handover-20261020-reverse-tree.md` | `needs_guard` | `doc` | other |
| `notes/headless-workflow.md` | `needs_guard` | `local_artifact` | other |
| `notes/initializer-resource-pack-export-20260730.md` | `needs_guard` | `none` | other |
| `notes/legacy-artifact-acceptance-20260905.md` | `needs_guard` | `none` | other |
| `notes/legacy-generator-safety-20260711.md` | `needs_human_review` | `doc` | other |
| `notes/levels-runtime-probe-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/line-a-progress-20261019.md` | `needs_guard` | `none` | other |
| `notes/live-ledger-identity-repair-20261020.md` | `needs_guard` | `none` | other |
| `notes/local-mgba-build.md` | `needs_human_review` | `doc` | other |
| `notes/m4a-channel-allocation-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/m4a-command-vm-20260713.md` | `needs_guard` | `doc` | other |
| `notes/m4a-emulator-differential-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/m4a-full-song-render-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/m4a-player-slot-control-flow-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/m4a-player-slot-runtime-differential-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/m4a-runtime-channel-wiring-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/m4a-soundmain-scheduler-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/m4a-track-register-state-20260713.md` | `needs_guard` | `doc` | other |
| `notes/macos-intel-runtime-preflight-20260715.md` | `implemented_in_code` | `build` | other |
| `notes/map-addresses.md` | `needs_guard` | `local_artifact` | map |
| `notes/map-canvases-export-20260729.md` | `needs_guard` | `local_artifact` | map |
| `notes/map-events-e4-player-visible-20260809.md` | `needs_guard` | `none` | map |
| `notes/map-format.md` | `needs_guard` | `local_artifact` | map |
| `notes/map-position-pc-probe-20260710.md` | `needs_guard` | `local_artifact` | map |
| `notes/map-resource-relocation-20260731.md` | `needs_guard` | `none` | map |
| `notes/map-resource-writeback-20260730.md` | `needs_guard` | `none` | map |
| `notes/map-sprites-definition-player-visible-20260809.md` | `needs_guard` | `none` | map |
| `notes/map41-primary-layout-pixel-ab-20260801.md` | `needs_guard` | `none` | map |
| `notes/map41-visual-resource-matrix-20260801.md` | `needs_guard` | `none` | map |
| `notes/maps-runtime-fields-20260711.md` | `needs_guard` | `local_artifact` | map |
| `notes/memory-incident-root-cause-20260714.md` | `needs_guard` | `local_artifact` | other |
| `notes/menu-portrait-export-20260729.md` | `needs_guard` | `local_artifact` | presentation |
| `notes/menu-portrait-pixel-ab-20260801.md` | `needs_guard` | `none` | presentation |
| `notes/menu-portrait-relocation-20260731.md` | `needs_guard` | `none` | presentation |
| `notes/menu-portrait-writeback-20260730.md` | `needs_guard` | `none` | presentation |
| `notes/mgba-threaded-fastforward-fix.md` | `needs_human_review` | `doc` | other |
| `notes/motion-effect-parameter-player-visible-20260809.md` | `needs_guard` | `none` | other |
| `notes/natural-skill-detail-runtime-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/next-steps.md` | `missing_evidence` | `doc` | other |
| `notes/ninja-tool-addresses.md` | `implemented_in_code` | `build` | other |
| `notes/ocr-dialogue-report.md` | `needs_human_review` | `doc` | other |
| `notes/ocr-longwalk-report.md` | `needs_human_review` | `doc` | other |
| `notes/ocr-newgame-report.md` | `needs_human_review` | `doc` | other |
| `notes/offline-e2e-smoke-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/overlapping-visual-tables-audit-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/overview-gradient-overlay-export-20260730.md` | `needs_guard` | `none` | overview |
| `notes/palettes-bank-player-visible-attempt-20260806.md` | `needs_guard` | `none` | other |
| `notes/partial-item-inventory.md` | `needs_guard` | `local_artifact` | other |
| `notes/partial-random-encounter.md` | `needs_guard` | `local_artifact` | other |
| `notes/patch-generator-audit.md` | `needs_guard` | `local_artifact` | other |
| `notes/portrait-palette-producers-20260730.md` | `needs_guard` | `none` | presentation |
| `notes/positions-rom-source-20260710.md` | `implemented_in_code` | `build` | other |
| `notes/profile-text-runtime-probe-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/psg-noise-runtime-chain-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/re-completion-audit.md` | `implemented_in_code` | `build` | other |
| `notes/remaining-runtime-bank-probes-20260713.md` | `missing_evidence` | `doc` | other |
| `notes/residual-lz77-graphics-relocation-20260731.md` | `needs_guard` | `none` | residual |
| `notes/residual-text-bg-tilemap-relocation-20260731.md` | `needs_guard` | `none` | residual |
| `notes/residual-text-bg-tilemap-resource-ownership-20260731.md` | `needs_guard` | `none` | residual |
| `notes/residual-wram-derived-tilemap-relocation-20260731.md` | `needs_guard` | `none` | residual |
| `notes/residual-wram-tilemap-abi-20260731.md` | `needs_guard` | `none` | residual |
| `notes/residual-wram-tilemap-pixel-ab-20260801.md` | `needs_guard` | `doc` | residual |
| `notes/residual-wram-tilemap-relocation-20260731.md` | `needs_guard` | `none` | residual |
| `notes/residual-wram-tilemap-resource-ownership-20260731.md` | `needs_guard` | `none` | residual |
| `notes/residual-wram-tilemap-runtime-reachability-20260731.md` | `needs_guard` | `none` | residual |
| `notes/residual-wram-transformed-tilemap-runtime-20260801.md` | `needs_guard` | `none` | residual |
| `notes/resource-locations.md` | `implemented_in_code` | `build` | other |
| `notes/resource-pointer-alias-correction-20260730.md` | `needs_guard` | `none` | other |
| `notes/resource-table-596F98.md` | `needs_guard` | `local_artifact` | other |
| `notes/reverse-engineering-current-gaps-20260806.md` | `missing_evidence` | `none` | other |
| `notes/reverse-engineering-progress-snapshot-20260802.md` | `needs_human_review` | `none` | other |
| `notes/reverse-method-review-20261002.md` | `needs_guard` | `none` | other |
| `notes/rom-ai-config-writer-preflight-20260930.md` | `missing_evidence` | `doc` | rom |
| `notes/rom-ai-entry-local-domains-20260930.md` | `needs_guard` | `doc` | rom |
| `notes/rom-ai-extra-pool-lifecycle-preflight-20260930.md` | `missing_evidence` | `none` | rom |
| `notes/rom-ai-producer-and-pool-alias-20260930.md` | `needs_guard` | `doc` | rom |
| `notes/rom-ai-renderer-script-dependencies-20260930.md` | `needs_guard` | `doc` | rom |
| `notes/rom-alternate-dialogue-table-20260902.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-base-pairs-preflight-20261001.md` | `missing_evidence` | `none` | rom |
| `notes/rom-animation-callee-effects-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-caller-predecessor-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-critical-writers-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-full-renderer-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-interprocedural-identities-20261001.md` | `missing_evidence` | `none` | rom |
| `notes/rom-animation-irq-arm-native-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-object-lifecycle-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-object-native-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-pool-caller-screen-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-pool-lifecycle-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-save-source-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-upstream-closure-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-animation-writer-domain-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-bank-proof-work-plan-20261001.md` | `missing_evidence` | `none` | rom |
| `notes/rom-bank-runtime-replay-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-battle-condition-result-text-20260902.md` | `needs_guard` | `none` | rom |
| `notes/rom-battle-distance-dispatcher-cfg-20260902.md` | `needs_guard` | `none` | rom |
| `notes/rom-battle-effect-fixed-roundtrip-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-battle-message-text-inventory-20260811.md` | `needs_guard` | `doc` | rom |
| `notes/rom-boot-interwork-20260811.md` | `needs_guard` | `none` | rom |
| `notes/rom-boot-register-init-dependency-cfg-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-bounded-index-u16-pair-table-20260904.md` | `needs_guard` | `none` | rom |
| `notes/rom-cfg-proven-roots-20260811.md` | `needs_guard` | `none` | rom |
| `notes/rom-cfg-proven-roots-v13-20260830.md` | `needs_guard` | `none` | rom |
| `notes/rom-cfg-proven-roots-v14-20260830.md` | `needs_guard` | `none` | rom |
| `notes/rom-cfg-proven-roots-v15-20260830.md` | `needs_guard` | `none` | rom |
| `notes/rom-cfg-proven-roots-v2-20260812.md` | `needs_guard` | `none` | rom |
| `notes/rom-cfg-proven-roots-v20-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-cfg-proven-roots-v21-20260905.md` | `needs_guard` | `doc` | rom |
| `notes/rom-cfg-proven-roots-v3-v4-20260813.md` | `needs_guard` | `doc` | rom |
| `notes/rom-chapter-script-consumer-roots-20260902.md` | `needs_guard` | `none` | rom |
| `notes/rom-chapter-script-inventory-20260809.md` | `needs_guard` | `none` | rom |
| `notes/rom-coroutine-record-lifecycle-preflight-20261001.md` | `missing_evidence` | `none` | rom |
| `notes/rom-cutscene-secondary-ptr-ab-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-cutscene-secondary-ptr-contract-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-data-table-b-partial-bank-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-direct-cpuset-inventory-survey-20260730.md` | `needs_guard` | `none` | rom |
| `notes/rom-direct-dma-inventory-survey-20260730.md` | `needs_guard` | `none` | rom |
| `notes/rom-display-text-delta-tier1-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-display-text-parameter-flow-tdd-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-evidence-selector-repair-20260905.md` | `needs_guard` | `doc` | rom |
| `notes/rom-expansion-character-bundle-relocation-20260731.md` | `needs_guard` | `none` | rom |
| `notes/rom-finite-lookup-scope-review-20260905.md` | `needs_guard` | `doc` | rom |
| `notes/rom-fixed-animation-descriptor-groups-20260902.md` | `needs_guard` | `none` | rom |
| `notes/rom-fixed-consumer-text-inventory-20260811.md` | `needs_guard` | `none` | rom |
| `notes/rom-fixed-index-u8-tail-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-fixed-pair-tables-20260904.md` | `needs_guard` | `none` | rom |
| `notes/rom-fixed-text-route-preflight-20261001.md` | `missing_evidence` | `none` | rom |
| `notes/rom-gpu-copy-queue-inventory-20260730.md` | `implemented_in_code` | `build` | rom |
| `notes/rom-large-unknown-anchor-screen-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-later-cfg-renderer-consumers-preflight-20261001.md` | `missing_evidence` | `none` | rom |
| `notes/rom-low-script-delta-tier1-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-low-script-fixed-consumers-preflight-20261001.md` | `missing_evidence` | `none` | rom |
| `notes/rom-m4a-initializer-chain-20260829.md` | `needs_guard` | `none` | rom |
| `notes/rom-map-resource-fixed-roundtrip-20261002.md` | `needs_guard` | `none` | rom |
| `notes/rom-map-resource-relocation-roundtrip-20261002.md` | `needs_guard` | `doc` | rom |
| `notes/rom-map-sprites-partial-bank-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-menu-gfx-pointer-ab-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-menu-portrait-palette-inventory-20260820.md` | `needs_guard` | `none` | rom |
| `notes/rom-mp2k-dispatcher-20260829.md` | `needs_guard` | `none` | rom |
| `notes/rom-mp2k-note-allocator-20260829.md` | `needs_guard` | `doc` | rom |
| `notes/rom-mplaymain-scheduler-20260828.md` | `needs_guard` | `doc` | rom |
| `notes/rom-open-root-and-large-candidate-review-20260905.md` | `missing_evidence` | `doc` | rom |
| `notes/rom-partial-bank-joint-matrix-20261001.md` | `needs_guard` | `doc` | rom |
| `notes/rom-pointer-lz77-graphics-preview-20260730.md` | `needs_guard` | `doc` | rom |
| `notes/rom-pointer-lz77-inventory-export-20260730.md` | `needs_guard` | `none` | rom |
| `notes/rom-prebattle-menu-controller-cfg-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-ram-protocol-tag-preflight-20261001.md` | `missing_evidence` | `none` | rom |
| `notes/rom-referenced-text-slot-padding-20260820.md` | `needs_guard` | `none` | rom |
| `notes/rom-release-gate-work-plan-20261001.md` | `missing_evidence` | `none` | rom |
| `notes/rom-renderer-batch-plan-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-renderer-excluded-roots-preflight-20260930.md` | `missing_evidence` | `none` | rom |
| `notes/rom-renderer-flow-cost-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-renderer-handler-context-preflight-20260930.md` | `missing_evidence` | `none` | rom |
| `notes/rom-renderer-records-delta-tier1-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-renderer-source-plan-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-renderer-source-replay-20261001.md` | `needs_guard` | `none` | rom |
| `notes/rom-renderer-text-inventory-20260809.md` | `needs_guard` | `none` | rom |
| `notes/rom-scene-source-closures-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-scene-visual-source-ranges-20260820.md` | `needs_guard` | `none` | rom |
| `notes/rom-selector-code-windows-20260820.md` | `needs_guard` | `none` | rom |
| `notes/rom-selector-direct-source-records-20260820.md` | `needs_guard` | `none` | rom |
| `notes/rom-selector-text-bindings-20260811.md` | `needs_guard` | `none` | rom |
| `notes/rom-small-cfg-dependency-batch-20260905.md` | `needs_guard` | `doc` | rom |
| `notes/rom-small-cfg-dependency-tier2-20260930.md` | `needs_guard` | `doc` | rom |
| `notes/rom-soundmain-relocated-cfg-20260828.md` | `needs_guard` | `none` | rom |
| `notes/rom-staged-gpu-copy-inventory-20260730.md` | `needs_guard` | `none` | rom |
| `notes/rom-story-callback-dependency-closures-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-story-next-dependency-cfg-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-story-selector-dependency-cfg-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-strided-prefix-local-read-domain-20260905.md` | `needs_guard` | `doc` | rom |
| `notes/rom-task-callback-078e38-closure-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-task-callback-alignment-gap-candidate-20260905.md` | `missing_evidence` | `none` | rom |
| `notes/rom-training-text-script-inventory-20260811.md` | `needs_guard` | `none` | rom |
| `notes/rom-u8-indexed-u16-pair-lookup-20260827.md` | `needs_guard` | `doc` | rom |
| `notes/rom-unknown-candidate-59eae0-negative-evidence-20260827.md` | `needs_guard` | `doc` | rom |
| `notes/rom-unknown-cluster-refresh-20260901.md` | `needs_guard` | `none` | rom |
| `notes/rom-unknown-cluster-refresh-20260902.md` | `needs_guard` | `doc` | rom |
| `notes/rom-unknown-cluster-refresh-20260905.md` | `needs_guard` | `none` | rom |
| `notes/rom-v17-v18-helper-cfg-20260904.md` | `needs_guard` | `none` | rom |
| `notes/rom-value-range-text-inventory-20260811.md` | `needs_guard` | `none` | rom |
| `notes/rom-verifier-runtime-inputs-20260905.md` | `needs_guard` | `doc` | rom |
| `notes/runtime-bg-composites-20260730.md` | `needs_guard` | `none` | runtime |
| `notes/runtime-checkpoints-data-integrity-issue-20260806.md` | `needs_guard` | `none` | runtime |
| `notes/runtime-font-tile-provenance-20260730.md` | `needs_guard` | `none` | runtime |
| `notes/runtime-handler-pair-consumer-20260712.md` | `needs_guard` | `local_artifact` | runtime |
| `notes/runtime-layer-static-provenance-20260730.md` | `needs_guard` | `none` | runtime |
| `notes/runtime-mode0-screen-compositor-20260730.md` | `needs_guard` | `none` | runtime |
| `notes/runtime-state-entry-audit-20260710.md` | `needs_guard` | `local_artifact` | runtime |
| `notes/runtime-verification-gates-20260710.md` | `implemented_in_code` | `build` | runtime |
| `notes/sappy-engine-master-enable-runtime-20260809.md` | `needs_guard` | `none` | other |
| `notes/save-descriptor-layout-correction-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/save-state-wasm-probe-20260711.md` | `needs_guard` | `local_artifact` | other |
| `notes/scan-summary.md` | `needs_guard` | `local_artifact` | other |
| `notes/scenario-41-battle-entry-runtime-20260713.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-41-completion-runtime-20260718.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-41-controller-path-runtime-20260715.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-41-movedone-runtime-20260717.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-41-player-control-runtime-20260715.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-41-prebattle-menu-macos-20260715.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-41-prebattle-to-controller-macos-20260715.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-41-savestate-context-reanalysis-20260715.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-42-progression-runtime-20260718.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-43-progression-runtime-20260718.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-44-progression-runtime-20260718.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-45-safe-resume-20260719.md` | `implemented_in_code` | `build` | scenario |
| `notes/scenario-46-entry-runtime-20260719.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-47-entry-runtime-20260720.md` | `needs_guard` | `local_artifact` | scenario |
| `notes/scenario-48-academy-runtime-20260720.md` | `needs_guard` | `doc` | scenario |
| `notes/scenario-49-battle-14-runtime-20260720.md` | `implemented_in_code` | `build` | scenario |
| `notes/scenario-50-battle-15-runtime-20260720.md` | `implemented_in_code` | `build` | scenario |
| `notes/scene-visual-composites-export-20260730.md` | `needs_guard` | `none` | map |
| `notes/scene-visual-pack-export-20260729.md` | `needs_guard` | `local_artifact` | map |
| `notes/scene-visual-transition-timelines-20260730.md` | `needs_guard` | `none` | map |
| `notes/similar-tables.md` | `implemented_in_code` | `build` | other |
| `notes/skill-template-consumer-semantics-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/skill-template-identity-20260711.md` | `needs_guard` | `local_artifact` | other |
| `notes/skill-template-ui-probe-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/sprite-definition-animations-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/sprite-definition-runtime-chain-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/staged-artifact-policy-20260905.md` | `not_applicable` | `none` | other |
| `notes/static-bank-identity-corrections-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/story-bank-identity-correction-20260712.md` | `needs_guard` | `local_artifact` | presentation |
| `notes/story-scene-layer-bindings-20260729.md` | `needs_guard` | `local_artifact` | presentation |
| `notes/story-scene-timelines-export-20260729.md` | `needs_guard` | `local_artifact` | presentation |
| `notes/story-visual-descriptor-consumer-20260712.md` | `needs_guard` | `local_artifact` | presentation |
| `notes/story-visual-layer-export-20260729.md` | `needs_guard` | `local_artifact` | presentation |
| `notes/story-visual-resource-relocation-20260731.md` | `needs_guard` | `none` | presentation |
| `notes/strict-battle-arrival-gate-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/text-and-battle-visual-consumers-20260713.md` | `needs_guard` | `local_artifact` | other |
| `notes/text-regions.md` | `needs_guard` | `local_artifact` | other |
| `notes/tier2-threshold-policy-source-20261020.md` | `needs_guard` | `none` | other |
| `notes/tile-asset-resource-relocation-20260731.md` | `needs_guard` | `none` | visual |
| `notes/tile-assets-bg-export-20260729.md` | `needs_guard` | `local_artifact` | visual |
| `notes/tile-assets-descriptor-player-visible-20260809.md` | `needs_guard` | `none` | visual |
| `notes/tileset-extraction-correction-20260712.md` | `needs_guard` | `local_artifact` | visual |
| `notes/tutorial-victory-save-load-runtime-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/u32-pointer-real-writeback-20260710.md` | `implemented_in_code` | `build` | other |
| `notes/unit-id-mapping-analysis.md` | `needs_guard` | `local_artifact` | other |
| `notes/unit-skill-addresses.md` | `needs_guard` | `local_artifact` | other |
| `notes/units-unsafe-table-fix-20260711.md` | `implemented_in_code` | `build` | other |
| `notes/unknown-bgm-sfx.md` | `needs_guard` | `local_artifact` | other |
| `notes/unknown-item-inventory.md` | `needs_guard` | `local_artifact` | other |
| `notes/unknown-random-encounter.md` | `needs_guard` | `local_artifact` | other |
| `notes/unknown-save-state.md` | `needs_guard` | `local_artifact` | other |
| `notes/unresolved-lz77-palette-survey-20260730.md` | `needs_guard` | `none` | other |
| `notes/variable-dialogue-relocation-20260712.md` | `needs_guard` | `local_artifact` | other |
| `notes/vram-safe-lz77-runtime-20260801.md` | `needs_guard` | `none` | other |
| `notes/wasm-formation-navigation-probe-20260710.md` | `needs_guard` | `local_artifact` | other |
| `notes/wasm-formation-probe-result-20260710.md` | `implemented_in_code` | `build` | other |
| `notes/wasm-runtime-api-audit-20260710.md` | `needs_guard` | `local_artifact` | other |
| `notes/windows-porting-20261020.md` | `needs_guard` | `none` | other |
| `notes/world-map-background-export-20260729.md` | `needs_guard` | `local_artifact` | map |
| `notes/world-map-background-relocation-20260731.md` | `needs_guard` | `none` | map |
| `notes/world-map-page0-pixel-ab-20260801.md` | `needs_guard` | `none` | map |
| `notes/world-map-runtime-composition-20260729.md` | `needs_guard` | `local_artifact` | map |
| `notes/writeback-experiment-00076D.md` | `needs_guard` | `local_artifact` | other |
