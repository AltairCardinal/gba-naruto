# 未被使用但可直接用于复刻的逆向成果（自动生成）

本文件由 `tools/measure_butano_usable_backlog.py` 生成，不要手工编辑。

上一份差异清单（`artifacts/butano-reverse-gap-v1/gap.md`）回答的是「有没有被引用」；
本文件回答的是「**能不能直接用**」。两者的分母相同，口径不同。

## 输入

- 索引：`artifacts/reverse-results-index-v1/index.json`（SHA-256 `48117e653c72263e…`）
- 差异清单：`artifacts/butano-reverse-gap-v1/gap.json`（SHA-256 `d06641655dd0e492…`）
- 逆向 commit：`821d0937e058245aa7e6d29f23f96c7fc78e7375`（工作树 dirty=False）
- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`

## 过滤链与判定口径

- **population**：`index entries with kind == artifact`
- **accepted**：`manifest artifact_status == "accepted"`
- **has_payload**：`at least one non-empty file that is not manifest.json/inputs.json and not a .gz receipt`
- **consumed**：`gap receipt status == build and the build hits are not verifier-only references`
- **shelf**：`accepted and has_payload and not consumed`
- **tier_asset**：`payload has a file with suffix in .4bpp, .8bpp, .bgr555, .lz77, .png, .s3m, .wav`
- **tier_table**：`JSON top-level keys hit the table vocabulary and no structural marker`
- **tier_analysis**：`no table marker, and at least one structural or coverage marker`
- **tier_unclassified**：`both a table marker and a structural marker, or no marker at all`

## 总览

| 指标 | 值 |
| --- | ---: |
| 成果族总数 | 264 |
| 其中 `accepted` | 201 |
| 其中已被构建链消费 | 162 |
| `accepted` 且带 payload | 192 |
| **未被使用的货架（shelf）** | **65** |
| 货架 payload 总量 | 27,702,166 字节 |
| 货架里 scope **全部闭合**的族 | 1 |
| 货架里 scope 仍有未闭合声明的族 | 38 |
| 货架里 manifest 没写 scope 的族 | 26 |
| 台账 `missing` | 0 |

### 货架分层

| 层 | 含义 | 族数 |
| --- | --- | ---: |
| `analysis-only`（仅判读） | payload 是控制流／覆盖分母／审计证据——约束行为，但不能导入 | 51 |
| `asset-direct`（资产直取） | payload 是 remake 资产管线能直接读的字节（像素／图块／调色板／LZ77／音频） | 1 |
| `table-direct`（一次生成器） | payload 是内容表，接入只需一个生成器 | 1 |
| `unclassified`（待判定） | 两类词表都命中或都没命中，不强行归类 | 12 |

## notes 侧（复用 notes 索引的既有分桶）

- 索引：`artifacts/reverse-notes-index-v1/notes-index.json`
- note 文件总数：436
  - `implemented_in_code`：29
  - `missing_evidence`：19
  - `needs_guard`：332
  - `needs_human_review`：13
  - `not_applicable`：43
- `needs_guard` 里**连测试都没引用**的：313

## 货架明细

### `asset-direct`（资产直取）— 1 族

| 族 | 类别 | payload | 字节 | 判定证据 | scope |
| --- | --- | --- | ---: | --- | --- |
| `overview-gradient-overlay-v1` | overview | `generated-palette.bgr555.bin`, `generated-tilemap-30x20.bin`, `generated-tiles.4bpp.bin`, `overview-gradient-overlay.json` | 26,201 | .png | manifest 无 scope |

### `table-direct`（一次生成器）— 1 族

| 族 | 类别 | payload | 字节 | 判定证据 | scope |
| --- | --- | --- | ---: | --- | --- |
| `character-runtime-unit-oam-bindings-v1` | visual | `bindings.json` | 469,272 | table: checkpoints | manifest 无 scope |

### `unclassified`（待判定）— 12 族

| 族 | 类别 | payload | 字节 | 判定证据 | scope |
| --- | --- | --- | ---: | --- | --- |
| `rom-cfg-proven-roots-v15` | rom | `rom-cfg-proven-roots-v15.json` | 57,245 | table: targets；structural: rejected_targets, source_membership | scope 未闭合: al |
| `rom-cfg-proven-roots-v16-consumed-literals-v1` | rom | `rom-cfg-proven-roots-v16-consumed-literals.json` | 65,851 | table: bindings；structural: target_words | scope 未闭合: ca |
| `rom-cgb-helper-bounded-cfg-v1` | rom | `rom-cgb-helper-bounded-cfg.bin`, `rom-cgb-helper-bounded-cfg.json` | 42,334 | table: initializer_binding；structural: cfg, roots | manifest 无 scope |
| `rom-cgbsound-bounded-cfg-v1` | rom | `rom-cgbsound-bounded-cfg.bin`, `rom-cgbsound-bounded-cfg.json` | 179,635 | table: initializer_binding；structural: cfg | manifest 无 scope |
| `rom-dialogue-padding-inventory-v1` | rom | `dialogue-padding-inventory.json`, `dialogue-padding-zero.bin` | 804,757 | table: ；structural:  | scope 未闭合: ru |
| `rom-mp2k-dispatcher-v1` | rom | `candidate/rom-mp2k-dispatcher.bin`, `candidate/rom-mp2k-dispatcher.json`, `rom-mp2k-dispatcher.bin`, `rom-mp2k-dispatcher.json` | 411,032 | table: initializer_binding；structural: cfg, code_ranges, literal_binding_vector, literal_binding_vector_sha256, literal_ranges, packed_binary, packed_layout, roots, unclassified_unknown_ranges | scope 未闭合: al |
| `rom-small-cfg-dependency-batch-v1` | rom | `rom-small-cfg-dependency-batch.json` | 203,761 | table: ；structural:  | manifest 无 scope |
| `rom-sprite-component-source-v1` | rom | `rom-sprite-component-source.bin`, `rom-sprite-component-source.json` | 45,928 | table: consumer；structural: packed_bytes, packed_bytes_sha256 | scope 未闭合: co |
| `rom-text-bg-task-closure-v1` | rom | `rom-text-bg-task-closure.json` | 20,175 | table: ；structural:  | manifest 无 scope |
| `rom-unbound-lz77-inventory-v1` | rom | `inventory.json`, `payloads.bin`, `streams.lz77.bin` | 70,309 | table: records, selection_rule；structural: bundles | scope 未闭合: al |
| `battle-effect-group15-natural-runtime-v1` | visual | `evidence.json`, `raw-runtime.tar` | 1,189,632 | table: ；structural:  | manifest 无 scope |
| `battle-effect-observed-frame-phases-v1` | visual | `coverage.json` | 10,327 | table: ；structural:  | manifest 无 scope |

### `analysis-only`（仅判读）— 51 族

| 族 | 类别 | payload | 字节 | 判定证据 | scope |
| --- | --- | --- | ---: | --- | --- |
| `rom-battle-controller-consumed-literals-v1` | rom | `rom-battle-controller-consumed-literals.json` | 56,966 | structural: source_to_target, target_words, v3_packet_target_overlap_word_count；coverage: coverage_baseline, coverage_projection, literal_denominator, non_claims | scope 未闭合: cf |
| `rom-battle-distance-dispatcher-cfg-v1` | rom | `rom-battle-distance-dispatcher-cfg.json` | 10,498 | structural: target_closure | manifest 无 scope |
| `rom-battle-status-bar-caller-slice-v1` | rom | `rom-battle-status-bar-caller-slice.json` | 14,507 | structural: packed_bytes, packed_bytes_sha256；coverage: coverage, range_denominator_sha256 | manifest 无 scope |
| `rom-boot-interwork-continuation-v1` | rom | `rom-boot-interwork-continuation.json` | 105,718 | structural: ；coverage: coverage_baseline, coverage_projection | scope 未闭合: bu |
| `rom-boot-register-init-dependency-cfg-v1` | rom | `rom-boot-register-init-dependency-cfg-v1.json` | 31,413 | structural: root, target_local_denominator；coverage: coverage_projection, precoverage, producer_denominator | scope 未闭合: ab |
| `rom-boot-state-dispatcher-cfg-v1` | rom | `rom-boot-state-dispatcher-cfg.json` | 21,757 | structural: target_closure；coverage: producer_denominator | manifest 无 scope |
| `rom-boot-thumb-handoff-cfg-v1` | rom | `rom-boot-thumb-handoff-cfg.bin`, `rom-boot-thumb-handoff-cfg.json` | 748,503 | structural: blocks, code_ranges, edges, external_edges, frontiers, instructions, literal_ranges, raw_indirect_pc_sites；coverage: coverage_baseline, coverage_claims, literal_bindings, promotion_ranges | scope 未闭合: al |
| `rom-cfg-proven-roots-batch-consumed-literals-v1` | rom | `rom-cfg-proven-roots-batch-consumed-literals.json` | 172,757 | structural: source_to_target, target_words, v3_packet_target_overlap_word_count；coverage: coverage_baseline, coverage_projection, non_claims | scope 未闭合: cf |
| `rom-cfg-proven-roots-v10` | rom | `rom-cfg-proven-roots-v10.json` | 220,851 | structural: ；coverage: coverage_baseline | scope 未闭合: ad |
| `rom-cfg-proven-roots-v11` | rom | `rom-cfg-proven-roots-v11.json` | 456,466 | structural: ；coverage: coverage_baseline, producer_denominator | scope 未闭合: ex |
| `rom-cfg-proven-roots-v12` | rom | `rom-cfg-proven-roots-v12.json` | 327,605 | structural: ；coverage: coverage_baseline, producer_denominator | scope 未闭合: ca |
| `rom-cfg-proven-roots-v13` | rom | `rom-cfg-proven-roots-v13.json` | 312,804 | structural: ；coverage: coverage_baseline, producer_denominator | scope 未闭合: ca |
| `rom-cfg-proven-roots-v16` | rom | `rom-cfg-proven-roots-v16.json` | 19,750 | structural: accepted_producers, roots；coverage: coverage_baseline | scope 全闭合 |
| `rom-cfg-proven-roots-v17` | rom | `rom-cfg-proven-roots-v17.json` | 13,478 | structural: root, target_local_denominator；coverage: coverage_projection, precoverage | scope 未闭合: ad |
| `rom-cfg-proven-roots-v18` | rom | `rom-cfg-proven-roots-v18.json` | 10,940 | structural: accepted_producers, roots, target_local_denominator；coverage: coverage_projection, precoverage | scope 未闭合: al |
| `rom-cfg-proven-roots-v19` | rom | `rom-cfg-proven-roots-v19.json` | 9,633 | structural: accepted_producers, root, target_local_denominator；coverage: coverage_projection, precoverage | scope 未闭合: al |
| `rom-cfg-proven-roots-v20` | rom | `rom-cfg-proven-roots-v20.json` | 20,820 | structural: accepted_producers, rejected_producers, root, target_local_denominator；coverage: coverage_projection, precoverage, producer_denominator | scope 未闭合: ab |
| `rom-cfg-proven-roots-v21` | rom | `rom-cfg-proven-roots-v21.json` | 12,782 | structural: accepted_producers, rejected_producers, root, target_local_denominator；coverage: coverage_projection, precoverage, producer_denominator | manifest 无 scope |
| `rom-cfg-proven-roots-v9` | rom | `rom-cfg-proven-roots-v9.json` | 99,730 | structural: roots；coverage: coverage_baseline, producer_denominator | scope 未闭合: gl |
| `rom-cfg-v1-consumed-literals-v1` | rom | `rom-cfg-v1-consumed-literals.json` | 137,316 | structural: source_to_target, target_words；coverage: coverage_baseline, coverage_projection, literal_denominator, non_claims | scope 未闭合: cf |
| `rom-cfg-v2-consumed-literals-v1` | rom | `rom-cfg-v2-consumed-literals.json` | 666,483 | structural: source_to_target, target_words；coverage: coverage_baseline, coverage_projection, literal_denominator, non_claims | scope 未闭合: cf |
| `rom-cfg-v2-shadowed-consumed-literals-v1` | rom | `rom-cfg-v2-shadowed-consumed-literals.json` | 35,476 | structural: source_to_target, target_words, v3_packet_target_overlap_word_count；coverage: coverage_baseline, coverage_projection, literal_denominator, non_claims | scope 未闭合: cf |
| `rom-cfg-v3-consumed-literals-v1` | rom | `rom-cfg-v3-consumed-literals.json` | 116,592 | structural: source_to_target, target_words；coverage: coverage_baseline, coverage_projection, literal_denominator, non_claims | scope 未闭合: cf |
| `rom-cfg-v6-consumed-literals-v1` | rom | `rom-cfg-v6-consumed-literals.json` | 270,829 | structural: source_to_target, target_words；coverage: coverage_baseline, coverage_projection, literal_denominator, non_claims | scope 未闭合: cf |
| `rom-chapter-selector-code-slice-v1` | rom | `rom-chapter-selector-code-slice.json` | 5,785 | structural: packed_bytes, packed_bytes_sha256；coverage: coverage, range_denominator_sha256 | manifest 无 scope |
| `rom-event-handler-cfg-v1` | rom | `rom-event-handler-cfg.json` | 34,133 | structural: cfg；coverage: coverage_baseline, producer_denominator | scope 未闭合: al |
| `rom-legacy-acceptance-20260905-v1` | rom | `catalog.json` | 434,402 | structural: roots | scope 未闭合: ca |
| `rom-m4a-initializer-chain-v1` | rom | `candidate/rom-m4a-initializer-chain.bin`, `candidate/rom-m4a-initializer-chain.json`, `rom-m4a-initializer-chain.bin`, `rom-m4a-initializer-chain.json` | 429,116 | structural: cfg, code_ranges, literal_binding_vector, literal_binding_vector_sha256, literal_ranges, packed_binary, packed_layout, roots, unclassified_unknown_ranges；coverage: coverage_baseline, coverage_baseline_source, coverage_claims, coverage_projection | scope 未闭合: al |
| `rom-mp2k-note-allocator-v1` | rom | `candidate/rom-mp2k-note-allocator.bin`, `candidate/rom-mp2k-note-allocator.json`, `rom-mp2k-note-allocator.bin`, `rom-mp2k-note-allocator.json` | 763,478 | structural: cfg, code_ranges, literal_binding_vector, literal_binding_vector_sha256, literal_ranges, packed_binary, packed_layout, roots, unclassified_unknown_ranges；coverage: coverage_baseline, coverage_baseline_source, coverage_claims, coverage_projection | scope 未闭合: al |
| `rom-mplaymain-scheduler-v1` | rom | `rom-mplaymain-scheduler.bin`, `rom-mplaymain-scheduler.json` | 336,741 | structural: blocks, candidate_windows, code_ranges, edges, external_edges, frontiers, instructions, literal_ranges, packed_binary, packed_layout, raw_indirect_pc_sites, roots, unclassified_unknown_ranges；coverage: coverage_baseline, coverage_claims, literal_bindings, producer_denominator | scope 未闭合: al |
| `rom-parser-bound-zero-padding-v1` | rom | `parser-bound-zero-padding.bin`, `rom-parser-bound-zero-padding.json` | 236,847 | structural: ；coverage: classified_ranges | scope 未闭合: al |
| `rom-prebattle-menu-controller-cfg-v1` | rom | `rom-prebattle-menu-controller-cfg.json` | 18,044 | structural: target_local_denominator；coverage: coverage_baseline, producer_denominator | manifest 无 scope |
| `rom-profile-selector-code-slices-v1` | rom | `rom-profile-selector-code-slices.json` | 7,706 | structural: packed_bytes, packed_bytes_sha256；coverage: coverage, range_denominator_sha256 | manifest 无 scope |
| `rom-referenced-text-slot-padding-v1` | rom | `referenced-text-slot-padding.bin`, `referenced-text-slot-padding.json` | 98,185 | structural: ；coverage: classified_ranges | scope 未闭合: ed |
| `rom-scene-source-closures-v1` | rom | `rom-scene-source-closures.json` | 104,695 | structural: ；coverage: coverage_baseline | manifest 无 scope |
| `rom-scene-visual-source-ranges-v1` | rom | `rom-scene-visual-source-ranges.bin`, `rom-scene-visual-source-ranges.json` | 69,328 | structural: ；coverage: coverage_baseline, source_denominator | scope 未闭合: al |
| `rom-selector-code-windows-v1` | rom | `rom-selector-code-windows-promotion.bin`, `rom-selector-code-windows.bin`, `rom-selector-code-windows.json` | 49,653 | structural: bundles；coverage: coverage, promotion_ranges | scope 未闭合: al |
| `rom-soundmain-relocated-cfg-v1` | rom | `rom-soundmain-relocated-cfg.bin`, `rom-soundmain-relocated-cfg.json` | 353,858 | structural: cfg, packed_binary, packed_layout；coverage: coverage_baseline, coverage_claims, producer_denominator, promotion_ranges | scope 未闭合: al |
| `rom-sprite-loader-tail-v1` | rom | `rom-sprite-loader-tail.json` | 5,675 | structural: packed_bytes, packed_bytes_sha256；coverage: coverage, range_denominator_sha256 | manifest 无 scope |
| `rom-story-callback-dependency-closures-v1` | rom | `rom-story-callback-dependency-closures.json` | 31,998 | structural: target_closure；coverage: coverage_baseline, producer_denominator | manifest 无 scope |
| `rom-story-next-dependency-cfg-v1` | rom | `rom-story-next-dependency-cfg-v1.json` | 32,054 | structural: accepted_producers, rejected_producers, root, target_local_denominator；coverage: coverage_projection, precoverage, producer_denominator | scope 未闭合: ab |
| `rom-story-selector-dependency-cfg-v1` | rom | `rom-story-selector-dependency-cfg-v1.json` | 10,027 | structural: accepted_producers, rejected_producers, root, target_local_denominator；coverage: coverage_projection, precoverage, producer_denominator | scope 未闭合: ad |
| `rom-story-state-callback-cfg-v1` | rom | `rom-story-state-callback-cfg.json` | 16,837 | structural: root, target_local_denominator；coverage: coverage_baseline, coverage_projection, producer_denominator | manifest 无 scope |
| `rom-story-state-entry-c4cc-v1` | rom | `rom-story-state-entry-c4cc.json` | 5,351 | structural: ；coverage: coverage_baseline, coverage_projection, producer_denominator | manifest 无 scope |
| `rom-task-callback-078e38-closure-v1` | rom | `rom-task-callback-078e38-closure-v1.json` | 19,489 | structural: ；coverage: precoverage | manifest 无 scope |
| `rom-task-scheduler-core-v1` | rom | `rom-task-scheduler-core.bin`, `rom-task-scheduler-core.json` | 226,748 | structural: blocks, candidate_windows, code_ranges, edges, external_edges, frontiers, instructions, literal_ranges, packed_binary, packed_layout, raw_indirect_pc_sites, roots, unclassified_unknown_ranges；coverage: coverage_baseline, coverage_claims, literal_bindings, producer_denominator | scope 未闭合: al |
| `rom-text-bg-loop-continuation-v1` | rom | `rom-text-bg-loop-continuation.json` | 6,593 | structural: source_membership；coverage: coverage_baseline, producer_denominator | manifest 无 scope |
| `rom-v17-v18-helper-cfg-v1` | rom | `rom-v17-v18-helper-cfg.json` | 31,523 | structural: target_closure；coverage: producer_denominator | manifest 无 scope |
| `battle-effect-controlled-runtime-v1` | visual | `evidence.json`, `raw-batch.tar` | 13,451,375 | structural: ；coverage: coverage | manifest 无 scope |
| `battle-effect-direct-spawn-runtime-v1` | visual | `evidence.json`, `raw-batch.tar` | 1,363,015 | structural: ；coverage: coverage | manifest 无 scope |
| `battle-effect-group15-allocator-side-runtime-v1` | visual | `evidence.json`, `raw-batch.tar` | 2,069,377 | structural: ；coverage: coverage | manifest 无 scope |

## 边界声明

- 分层是**词表探针**的结果，不是逐族人工判定；每个族的判定证据都写在明细表里，可逐行复核。
- `analysis-only` 的族**不是无用**：它们约束 remake 的行为（哪些字节被消费、
  哪些分母成立），但它们不是可导入的素材。
- 本清单不把「已被引用」当「已使用」：`build` 才是消费，文档提及不是。

