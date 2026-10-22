# 未被使用但可直接用于复刻的逆向成果（自动生成）

本文件由 `tools/measure_butano_usable_backlog.py` 生成，不要手工编辑。

上一份差异清单（`artifacts/butano-reverse-gap-v1/gap.md`）回答的是「有没有被引用」；
本文件回答的是「**能不能直接用**」。两者的分母相同，口径不同。

## 输入

- 索引：`artifacts/reverse-results-index-v1/index.json`（SHA-256 `a38f7f2e81e31d66…`）
- 差异清单：`artifacts/butano-reverse-gap-v1/gap.json`（SHA-256 `7bc86fbada4146c9…`）
- 逆向 commit：`821d0937e058245aa7e6d29f23f96c7fc78e7375`（工作树 dirty=False）
- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`

## 过滤链与判定口径

- **population**：`index entries with kind == artifact`
- **accepted**：`manifest artifact_status == "accepted"`
- **has_payload**：`at least one non-empty file that is not manifest.json/inputs.json and not a .gz receipt`
- **consumed**：`gap receipt status == build`
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
| 其中已被构建链消费 | 96 |
| `accepted` 且带 payload | 192 |
| **未被使用的货架（shelf）** | **131** |
| 货架 payload 总量 | 69,094,936 字节 |
| 货架里 scope **全部闭合**的族 | 3 |
| 货架里 scope 仍有未闭合声明的族 | 69 |
| 货架里 manifest 没写 scope 的族 | 59 |
| 台账 `missing` | 0 |

### 货架分层

| 层 | 含义 | 族数 |
| --- | --- | ---: |
| `analysis-only`（仅判读） | payload 是控制流／覆盖分母／审计证据——约束行为，但不能导入 | 51 |
| `asset-direct`（资产直取） | payload 是 remake 资产管线能直接读的字节（像素／图块／调色板／LZ77／音频） | 27 |
| `table-direct`（一次生成器） | payload 是内容表，接入只需一个生成器 | 41 |
| `unclassified`（待判定） | 两类词表都命中或都没命中，不强行归类 | 12 |

## notes 侧（复用 notes 索引的既有分桶）

- 索引：`artifacts/reverse-notes-index-v1/notes-index.json`
- note 文件总数：436
  - `implemented_in_code`：28
  - `missing_evidence`：19
  - `needs_guard`：333
  - `needs_human_review`：13
  - `not_applicable`：43
- `needs_guard` 里**连测试都没引用**的：314

## 货架明细

### `asset-direct`（资产直取）— 27 族

| 族 | 类别 | payload | 字节 | 判定证据 | scope |
| --- | --- | --- | ---: | --- | --- |
| `battle-status-bars-v1` | battle | `battle-status-bars.json`, `battle-status-bars.png`, `generated-family.4bpp.bin`, `runtime-palette-bank13.bgr555.bin` | 159,706 | .png | manifest 无 scope |
| `map41-visual-resource-matrix-v1` | map | `baseline/audit.json`, `baseline/frame80.png`, `baseline/frame80.ss9`, `baseline/guard.json` | 687,545 | .png | scope 未闭合: al |
| `scene-visual-composites-v1` | map | `exit/mode-1-obj-pack-08-over-pack-08.png`, `main/mode-0-pack-00.png`, `main/mode-0-pack-01.png`, `main/mode-0-pack-02.png` | 166,835 | .png | scope 未闭合: na |
| `initializer-resource-pack-v1` | other | `bg-graphics-atlas.png`, `bg-graphics.bin`, `bg-graphics.lz77.bin`, `bg-palette.bin` | 1,157,583 | .png | manifest 无 scope |
| `lz77-palette-runtime-v1` | other | `evidence.json`, `inputs/profile-title-menu.png`, `inputs/profile-title-menu.ss9`, `inputs/scenario-41-target-select-tutorial-dismissed.png` | 673,139 | .png | scope 未闭合: ge |
| `overview-gradient-overlay-v1` | overview | `generated-palette.bgr555.bin`, `generated-tilemap-30x20.bin`, `generated-tiles.4bpp.bin`, `overview-gradient-overlay.json` | 26,201 | .png | manifest 无 scope |
| `portrait-palette-producers-v1` | presentation | `portrait-palette-producers.json`, `raw/control/audit.json`, `raw/control/guard.json`, `raw/control/scratch.bin` | 324,088 | .png | scope 未闭合: al |
| `residual-wram-crop-tilemap-runtime-v1` | residual | `audit.json`, `crop-consumer.ss9`, `crop-load.ss9`, `done.json` | 274,856 | .png | scope 未闭合: ex |
| `residual-wram-tilemap-runtime-v1` | residual | `audit.json`, `final-queue.bin`, `final.png`, `final.ss9` | 253,008 | .png | scope 未闭合: ex |
| `residual-wram-tilemap-runtime-v2` | residual | `bridge-audit.json`, `bridge-done.json`, `bridge-guard.json`, `final-queue.bin` | 268,562 | .png | scope 未闭合: ex |
| `residual-wram-transformed-tilemap-runtime-v1` | residual | `entry/choice-screen-entry.ss9`, `entry/choice-state3.ss9`, `entry/state3-audit.json`, `entry/state3-done.marker` | 1,802,294 | .png | scope 未闭合: fi |
| `rom-expansion-profile-v1` | rom | `boot-frame-60.png`, `boot-frame-60.ss9`, `build-manifest.json`, `guard-summary.json` | 33,737 | .png | scope 全闭合 |
| `rom-pointer-lz77-graphics-v1` | rom | `graphics-catalog.json`, `previews/080b9e94-080b9f5c-bank-00.png`, `previews/0812c8b0-08457ea8-bank-00.png`, `previews/0812d134-08457ea8-bank-00.png` | 81,066 | .png | scope 未闭合: al |
| `battle-effect-frame-phase-group1-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 733,930 | .png | manifest 无 scope |
| `battle-effect-frame-phase-group14-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 617,081 | .png | manifest 无 scope |
| `battle-effect-frame-phase-group16-natural-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 622,356 | .png | manifest 无 scope |
| `battle-effect-frame-phase-group17-natural-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 621,642 | .png | manifest 无 scope |
| `battle-effect-frame-phase-group18-natural-sequence-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 703,391 | .png | manifest 无 scope |
| `battle-effect-frame-phase-group2-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 629,081 | .png | manifest 无 scope |
| `battle-effect-frame-phase-group3-natural-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 609,254 | .png | manifest 无 scope |
| `battle-effect-frame-phase-group4-natural-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 617,500 | .png | manifest 无 scope |
| `battle-effect-frame-phase-group5-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 599,576 | .png | manifest 无 scope |
| `battle-effect-frame-phase-v1` | visual | `guard-summary.json`, `raw/ack-post/capture-active-count.bin`, `raw/ack-post/capture-active-pointers.bin`, `raw/ack-post/capture-hardware-oam.bin` | 617,477 | .png | manifest 无 scope |
| `battle-effect-group12-ai-observer-v1` | visual | `audit.json`, `guard-summary.json`, `guard-summary.json.done.json`, `selection.png` | 53,686 | .png | manifest 无 scope |
| `battle-effect-group13-natural-runtime-v1` | visual | `evidence.json`, `raw/observer-audit.json`, `raw/observer-done.json`, `raw/observer-guard.json` | 58,186 | .png | manifest 无 scope |
| `battle-effect-group18-natural-checkpoint-v1` | visual | `raw/expiry-ready-check.json`, `raw/expiry-ready.png`, `raw/expiry-ready.ss9`, `raw/expiry-route-audit.json` | 531,920 | .png | scope 未闭合: mo |
| `character-battle-visual-resource-matrix-v1` | visual | `baseline/audit.json`, `baseline/bundle.bin`, `baseline/frame80.png`, `baseline/frame80.ss9` | 528,206 | .png | scope 未闭合: al |

### `table-direct`（一次生成器）— 41 族

| 族 | 类别 | payload | 字节 | 判定证据 | scope |
| --- | --- | --- | ---: | --- | --- |
| `scene-visual-transition-timelines-v1` | map | `frames.zip`, `scene-visual-transition-timelines.json` | 11,812,893 | table: background_scroll_tracks, controller_model | scope 未闭合: cr |
| `story-visual-resource-sources-v1` | presentation | `graphics/0b07fe8227f92a1ee99d0e2b5059265b18320ce5258b10cfb400faa176ea6347.4bpp.bin`, `graphics/0bbeb4fe314a823ef4b5b73a4ae8cff407689412d4d78d213d8a2fa7df0d057a.4bpp.bin`, `graphics/127b3b92ac19fb83b687249f348e0773f08bef3a54058df8b50b04de5b9c71d4.4bpp.bin`, `graphics/12e6ed9845dd95c282d57dd8cf53a42d355110bfb063dfd54c895797763de2ca.4bpp.bin` | 138,833 | table: resources, source_catalog | scope 全闭合 |
| `residual-text-bg-tilemap-resource-ownership-v1` | residual | `resource-ownership.json` | 5,365 | table: ownership_record | scope 未闭合: ex |
| `residual-wram-tilemap-abi-v1` | residual | `residual-wram-tilemap-abi.json`, `tilemaps.bin` | 7,018 | table: queue_contract, source_inventory, tilemaps | scope 未闭合: fi |
| `residual-wram-tilemap-resource-ownership-v1` | residual | `resource-ownership.json` | 20,525 | table: ownership_records | scope 未闭合: ex |
| `residual-wram-visual-metadata-abi-v2` | residual | `residual-wram-visual-metadata-abi.json`, `tilemap-sources.bin` | 18,240 | table: queue_contract, source_inventory, tilemap_sources | scope 未闭合: fi |
| `rom-alternate-dialogue-table-v1` | rom | `alternate-dialogue-table.json`, `alternate-dialogue-text.bin` | 99,750 | table: consumer, table, targets | manifest 无 scope |
| `rom-animation-descriptor-pool-v2` | rom | `rom-animation-descriptor-pool-v2.json` | 35,254 | table: consumer_contract | manifest 无 scope |
| `rom-battle-sound-selector-v1` | rom | `battle-sound-selector.bin`, `battle-sound-selector.json` | 38,941 | table: entries | scope 未闭合: co |
| `rom-boot-copy-sources-v1` | rom | `rom-boot-copy-sources.json` | 5,587 | table: copy_operation_union, copy_operations, local_dma_consumer | manifest 无 scope |
| `rom-bounded-index-u16-pair-table-v1` | rom | `rom-bounded-index-u16-pair-table.json` | 4,762 | table: consumer_contract, table | manifest 无 scope |
| `rom-cfg-proven-roots-v14` | rom | `rom-cfg-proven-roots-v14.json` | 73,816 | table: targets | scope 未闭合: ca |
| `rom-cutscene-obj-source-ranges-v1` | rom | `rom-cutscene-obj-source-ranges.bin`, `rom-cutscene-obj-source-ranges.json` | 41,363 | table: records, resources | scope 未闭合: al |
| `rom-dialogue-text-inventory-v1` | rom | `dialogue-text-inventory.json`, `direct-nul-targets.bin`, `pointer-table.bin` | 758,312 | table: consumer_evidence, table | scope 未闭合: al |
| `rom-direct-cpuset-gpu-inventory-v1` | rom | `new-raw-sources.bin`, `rom-direct-cpuset-gpu-inventory.json` | 43,211 | table: selection_rule, source_catalog | scope 未闭合: cr |
| `rom-direct-dma-gpu-inventory-v1` | rom | `rom-direct-dma-gpu-inventory.json` | 16,701 | table: constant_rom_gpu_transfers, selection_rule | scope 未闭合: cr |
| `rom-directsound-pitch-lookup-v1` | rom | `rom-directsound-pitch-lookup.bin`, `rom-directsound-pitch-lookup.json` | 8,035 | table: consumer, tables | scope 未闭合: al |
| `rom-display-text-delta-v1` | rom | `rom-display-text-delta.json` | 94,550 | table: consumers, records | manifest 无 scope |
| `rom-fixed-animation-descriptor-groups-v1` | rom | `rom-fixed-animation-descriptor-groups.json` | 9,341 | table: consumer_contract, tables | manifest 无 scope |
| `rom-fixed-index-u8-tail-v1` | rom | `rom-fixed-index-u8-tail.json` | 4,312 | table: consumer | manifest 无 scope |
| `rom-fixed-pair-tables-v1` | rom | `rom-fixed-pair-tables.json` | 10,639 | table: a_consumer, b_consumers, tables | manifest 无 scope |
| `rom-fixed-renderer-script-records-v1` | rom | `rom-fixed-renderer-script-records.json` | 32,401 | table: records | manifest 无 scope |
| `rom-gpu-copy-queue-inventory-v1` | rom | `rom-gpu-copy-queue-inventory.json` | 22,622 | table: selection_rule | scope 未闭合: al |
| `rom-low-script-delta-v1` | rom | `rom-low-script-delta.json` | 5,213 | table: consumers, records | manifest 无 scope |
| `rom-menu-portrait-palette-inventory-v1` | rom | `rom-menu-portrait-palette-inventory.json`, `rom-menu-portrait-palettes.bin` | 269,703 | table: logical_outputs, physical_palettes, queue, resource_provenance, writeback | scope 未闭合: ad |
| `rom-psg-frequency-lookup-v1` | rom | `rom-psg-frequency-lookup.bin`, `rom-psg-frequency-lookup.json` | 14,102 | table: consumer, table | scope 未闭合: al |
| `rom-renderer-records-delta-v1` | rom | `rom-renderer-records-delta.json` | 35,709 | table: consumers, records | manifest 无 scope |
| `rom-renderer-script-pointer-pool-records-v1` | rom | `rom-renderer-script-pointer-pool-records.json` | 12,030 | table: consumer_contract, records | manifest 无 scope |
| `rom-renderer-text-inventory-v1` | rom | `renderer-text-inventory.json`, `renderer-text-targets.bin` | 276,204 | table: consumer_evidence, pointer_tables, records | scope 未闭合: na |
| `rom-selector-direct-source-records-v1` | rom | `rom-selector-direct-source-records.bin`, `rom-selector-direct-source-records.json` | 37,999 | table: consumer_evidence | scope 未闭合: al |
| `rom-staged-gpu-copy-inventory-v1` | rom | `rom-staged-gpu-copy-inventory.json` | 8,160 | table: selection_rule | scope 未闭合: al |
| `rom-u8-indexed-u16-pair-lookup-v1` | rom | `rom-u8-indexed-u16-pair-lookup.bin`, `rom-u8-indexed-u16-pair-lookup.json` | 138,414 | table: consumers | scope 未闭合: al |
| `rom-u8-indexed-u8-triplet-lookup-v1` | rom | `rom-u8-indexed-u8-triplet-lookup.bin`, `rom-u8-indexed-u8-triplet-lookup.json` | 13,475 | table: consumer, table | scope 未闭合: bu |
| `runtime-bg-composites-v1` | runtime | `layers.zip`, `runtime-bg-composites.json` | 3,684,999 | table: checkpoints, states | manifest 无 scope |
| `runtime-font-tile-provenance-v1` | runtime | `runtime-font-tile-provenance.json` | 3,779,809 | table: classification_contract, layers | manifest 无 scope |
| `runtime-layer-static-provenance-v1` | runtime | `runtime-layer-static-provenance.json` | 1,573,057 | table: checkpoints, classification_contract, layers, source_registry | manifest 无 scope |
| `runtime-screen-composites-v1` | runtime | `frames.zip`, `runtime-screen-composites.json` | 1,999,346 | table: affine_runtime_goldens, checkpoints | manifest 无 scope |
| `battle-effect-runtime-oam-bindings-v1` | visual | `bindings.json` | 152,524 | table: binding_contract, supplemental_states | manifest 无 scope |
| `battle-effect-runtime-oam-task-bindings-v1` | visual | `bindings.json` | 252,937 | table: binding_contract, supplemental_states | manifest 无 scope |
| `character-runtime-oam-bindings-v1` | visual | `bindings.json` | 2,471,308 | table: binding_contract, checkpoints | manifest 无 scope |
| `character-runtime-oam-task-bindings-v1` | visual | `bindings.json` | 408,877 | table: checkpoints | manifest 无 scope |

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

