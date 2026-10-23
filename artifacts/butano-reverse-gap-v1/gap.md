# Butano 侧对逆向成果的差异清单（自动生成）

本文件由 `tools/measure_butano_reverse_gap.py` 生成，不要手工编辑。

输出：`gap.json`（机读）、`gap.md`（本文件）。

- 索引：`artifacts/reverse-results-index-v1/index.json`
- 索引 SHA-256：`48117e653c72263ed23475251b9408fc23aac32550b370d29e3bb940e8dee475`
- 逆向 commit：`821d0937e058245aa7e6d29f23f96c7fc78e7375`（工作树 dirty=False）
- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 测量单位：reverse result entry (artifact family / note / doc)
- 扫描文件数：4573
- 排除前缀：`artifacts/reverse-results-index-v1`, `tools/build_reverse_results_index.py`, `artifacts/butano-reverse-gap-v1`, `artifacts/reverse-notes-index-v1`, `artifacts/butano-reverse-m3-import-v1`, `docs/butano-reverse-gap-roadmap.md`, `notes/full-customization-and-fidelity-theory-20261020.md`, `docs/reverse-results-index/notes-index.md`, `artifacts/s49-original-battle14-roster-v1`, `artifacts/s49-result-settlement-v1`, `artifacts/s49-original-movegrid-frame-v1`, `artifacts/s49-original-banner-frame-v1`, `artifacts/s49-original-movegrid-mechanism-v1`, `artifacts/butano-usable-backlog-v1`, `artifacts/butano-wiring-coverage-v1`, `artifacts/butano-local-derivations-v1`

## 状态定义

| 状态 | 含义 |
| --- | --- |
| `build` | remake 构建链（`butano-sequel/`、`tools/`）引用——**唯一算消费** |
| `local_artifact` | 只有本树 `artifacts/` 引用——本树有，但没从逆向成果引入 |
| `test` | 只有 `tests/` 引用——有契约，无生产使用 |
| `doc` | 只有 `docs/`/`notes/` 提及——提及，不是使用 |
| `none` | 全树无引用——**真正的差异项** |

## 总览

| 指标 | 值 |
| --- | ---: |
| 条目总数 | 2207 |
| 成果类（artifact/note/doc） | 765 |
| 成果类无引用（`none`） | 224 |
| 成果族（artifact family） | 264 |
| 成果族 `build` 占比 | 164 / 264 = 62.1% |
| 台账 `missing` 条目 | 0 |

| 状态 | 条目数 |
| --- | ---: |
| `build` | 445 |
| `doc` | 335 |
| `local_artifact` | 125 |
| `none` | 1073 |
| `test` | 229 |

## 按类别 × 状态

| 类别 | `build` | `doc` | `local_artifact` | `none` | `test` | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| audio | 0 | 1 | 3 | 0 | 1 | 5 |
| battle | 6 | 0 | 4 | 2 | 1 | 13 |
| code | 252 | 131 | 0 | 849 | 210 | 1442 |
| map | 15 | 0 | 8 | 10 | 0 | 33 |
| other | 27 | 85 | 73 | 42 | 14 | 241 |
| overview | 2 | 0 | 0 | 1 | 0 | 3 |
| presentation | 14 | 0 | 8 | 7 | 0 | 29 |
| residual | 13 | 1 | 0 | 9 | 0 | 23 |
| rom | 35 | 108 | 0 | 108 | 1 | 252 |
| runtime | 6 | 0 | 2 | 5 | 0 | 13 |
| scenario | 8 | 1 | 13 | 0 | 1 | 23 |
| visual | 67 | 8 | 14 | 40 | 1 | 130 |

## 真正未被触及的成果（`none`）

| id | kind | category | 逆向路径 |
| --- | --- | --- | --- |
| `rom-boot-interwork-continuation-precoverage-v1` | artifact | rom | `artifacts/rom-boot-interwork-continuation-precoverage-v1` |
| `rom-cfg-proven-roots-v17-precoverage-v1` | artifact | rom | `artifacts/rom-cfg-proven-roots-v17-precoverage-v1` |
| `rom-cfg-proven-roots-v18-precoverage-v1` | artifact | rom | `artifacts/rom-cfg-proven-roots-v18-precoverage-v1` |
| `rom-cgb-audio-precoverage-v1` | artifact | rom | `artifacts/rom-cgb-audio-precoverage-v1` |
| `rom-m4a-initializer-chain-precoverage-v1` | artifact | rom | `artifacts/rom-m4a-initializer-chain-precoverage-v1` |
| `rom-mp2k-dispatcher-precoverage-v1` | artifact | rom | `artifacts/rom-mp2k-dispatcher-precoverage-v1` |
| `rom-mp2k-note-allocator-precoverage-v1` | artifact | rom | `artifacts/rom-mp2k-note-allocator-precoverage-v1` |
| `rom-post-story-dependency-precoverage-v1` | artifact | rom | `artifacts/rom-post-story-dependency-precoverage-v1` |
| `rom-scene-source-four-packet-precoverage-v1` | artifact | rom | `artifacts/rom-scene-source-four-packet-precoverage-v1` |
| `rom-story-callback-dependency-closures-precoverage-v1` | artifact | rom | `artifacts/rom-story-callback-dependency-closures-precoverage-v1` |
| `reverse-engineering-handoff-20260806` | doc | other | `docs/reverse-engineering-handoff-20260806.md` |
| `reverse-engineering-handoff-20260807` | doc | other | `docs/reverse-engineering-handoff-20260807.md` |
| `reverse-engineering-handoff-20260812` | doc | other | `docs/reverse-engineering-handoff-20260812.md` |
| `reverse-engineering-midterm-report-20260823` | doc | other | `docs/reverse-engineering-midterm-report-20260823.md` |
| `battle-encounters-story-visual-player-visible-20260809` | note | battle | `notes/battle-encounters-story-visual-player-visible-20260809.md` |
| `battlefield-object-effect-chain-20260802` | note | battle | `notes/battlefield-object-effect-chain-20260802.md` |
| `map-events-e4-player-visible-20260809` | note | map | `notes/map-events-e4-player-visible-20260809.md` |
| `map-resource-relocation-20260731` | note | map | `notes/map-resource-relocation-20260731.md` |
| `map-resource-writeback-20260730` | note | map | `notes/map-resource-writeback-20260730.md` |
| `map-sprites-definition-player-visible-20260809` | note | map | `notes/map-sprites-definition-player-visible-20260809.md` |
| `map41-primary-layout-pixel-ab-20260801` | note | map | `notes/map41-primary-layout-pixel-ab-20260801.md` |
| `map41-visual-resource-matrix-20260801` | note | map | `notes/map41-visual-resource-matrix-20260801.md` |
| `scene-visual-composites-export-20260730` | note | map | `notes/scene-visual-composites-export-20260730.md` |
| `scene-visual-transition-timelines-20260730` | note | map | `notes/scene-visual-transition-timelines-20260730.md` |
| `world-map-background-relocation-20260731` | note | map | `notes/world-map-background-relocation-20260731.md` |
| `world-map-page0-pixel-ab-20260801` | note | map | `notes/world-map-page0-pixel-ab-20260801.md` |
| `AGENTS` | note | other | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/AGENTS.md` |
| `AGENTS` | note | other | `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/AGENTS.md` |
| `AGENTS` | note | other | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/AGENTS.md` |
| `AGENTS` | note | other | `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/AGENTS.md` |
| `AGENTS` | note | other | `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/AGENTS.md` |
| `AGENTS` | note | other | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/AGENTS.md` |
| `README` | note | other | `notes/evidence/reverse-proof-update-20261019-v1/first-run-venv-interpreter/README.md` |
| `README` | note | other | `notes/evidence/rom-animation-pool-lifecycle-20261001-v1/README.md` |
| `auditor-module-failures-20261020` | note | other | `notes/auditor-module-failures-20261020.md` |
| `auto-exit-prevention-mgba-compile-20260806` | note | other | `notes/auto-exit-prevention-mgba-compile-20260806.md` |
| `bank-player-visible-closure-plan-20260806` | note | other | `notes/bank-player-visible-closure-plan-20260806.md` |
| `d0-bank-exhaustion-gate-20261020` | note | other | `notes/d0-bank-exhaustion-gate-20261020.md` |
| `direct-image-palette-relocation-20260731` | note | other | `notes/direct-image-palette-relocation-20260731.md` |
| `exporter-root-deletion-incident-20260809` | note | other | `notes/exporter-root-deletion-incident-20260809.md` |
| `four-decisions-20261020` | note | other | `notes/four-decisions-20261020.md` |
| `generic-sprite-bundle-relocation-20260731` | note | other | `notes/generic-sprite-bundle-relocation-20260731.md` |
| `group12-natural-entry-ai-observer-20260806` | note | other | `notes/group12-natural-entry-ai-observer-20260806.md` |
| `initializer-resource-pack-export-20260730` | note | other | `notes/initializer-resource-pack-export-20260730.md` |
| `legacy-artifact-acceptance-20260905` | note | other | `notes/legacy-artifact-acceptance-20260905.md` |
| `line-a-progress-20261019` | note | other | `notes/line-a-progress-20261019.md` |
| `live-ledger-identity-repair-20261020` | note | other | `notes/live-ledger-identity-repair-20261020.md` |
| `motion-effect-parameter-player-visible-20260809` | note | other | `notes/motion-effect-parameter-player-visible-20260809.md` |
| `note` | note | other | `notes/evidence/rom-cutscene-secondary-ptr-shared-lock-20261001-v1/contract-tier1-20261001-v1/note.md` |
| `note` | note | other | `notes/evidence/rom-menu-gfx-pointer-ab-20261001-v1/contract-20261001-v1/note.md` |
| `palettes-bank-player-visible-attempt-20260806` | note | other | `notes/palettes-bank-player-visible-attempt-20260806.md` |
| `plan` | note | other | `notes/evidence/reverse-work-plan-20261001-v1/plan.md` |
| `resource-pointer-alias-correction-20260730` | note | other | `notes/resource-pointer-alias-correction-20260730.md` |
| `reverse-engineering-current-gaps-20260806` | note | other | `notes/reverse-engineering-current-gaps-20260806.md` |
| `reverse-engineering-progress-snapshot-20260802` | note | other | `notes/reverse-engineering-progress-snapshot-20260802.md` |
| `reverse-method-review-20261002` | note | other | `notes/reverse-method-review-20261002.md` |
| `sappy-engine-master-enable-runtime-20260809` | note | other | `notes/sappy-engine-master-enable-runtime-20260809.md` |
| `staged-artifact-policy-20260905` | note | other | `notes/staged-artifact-policy-20260905.md` |
| `throughput` | note | other | `notes/evidence/reverse-throughput-20261019-v1/throughput.md` |
| `tier2-threshold-policy-source-20261020` | note | other | `notes/tier2-threshold-policy-source-20261020.md` |
| `unresolved-lz77-palette-survey-20260730` | note | other | `notes/unresolved-lz77-palette-survey-20260730.md` |
| `vram-safe-lz77-runtime-20260801` | note | other | `notes/vram-safe-lz77-runtime-20260801.md` |
| `windows-porting-20261020` | note | other | `notes/windows-porting-20261020.md` |
| `三包接入施工单-raw` | note | other | `notes/evidence/reverse-proof-update-20261020-v2/三包接入施工单-raw.md` |
| `overview-gradient-overlay-export-20260730` | note | overview | `notes/overview-gradient-overlay-export-20260730.md` |
| `cutscene-obj-bundle-relocation-20260731` | note | presentation | `notes/cutscene-obj-bundle-relocation-20260731.md` |
| `cutscene-visual-resource-player-visible-20260809` | note | presentation | `notes/cutscene-visual-resource-player-visible-20260809.md` |
| `menu-portrait-pixel-ab-20260801` | note | presentation | `notes/menu-portrait-pixel-ab-20260801.md` |
| `menu-portrait-relocation-20260731` | note | presentation | `notes/menu-portrait-relocation-20260731.md` |
| `menu-portrait-writeback-20260730` | note | presentation | `notes/menu-portrait-writeback-20260730.md` |
| `portrait-palette-producers-20260730` | note | presentation | `notes/portrait-palette-producers-20260730.md` |
| `story-visual-resource-relocation-20260731` | note | presentation | `notes/story-visual-resource-relocation-20260731.md` |
| `residual-lz77-graphics-relocation-20260731` | note | residual | `notes/residual-lz77-graphics-relocation-20260731.md` |
| `residual-text-bg-tilemap-relocation-20260731` | note | residual | `notes/residual-text-bg-tilemap-relocation-20260731.md` |
| `residual-text-bg-tilemap-resource-ownership-20260731` | note | residual | `notes/residual-text-bg-tilemap-resource-ownership-20260731.md` |
| `residual-wram-derived-tilemap-relocation-20260731` | note | residual | `notes/residual-wram-derived-tilemap-relocation-20260731.md` |
| `residual-wram-tilemap-abi-20260731` | note | residual | `notes/residual-wram-tilemap-abi-20260731.md` |
| `residual-wram-tilemap-relocation-20260731` | note | residual | `notes/residual-wram-tilemap-relocation-20260731.md` |
| `residual-wram-tilemap-resource-ownership-20260731` | note | residual | `notes/residual-wram-tilemap-resource-ownership-20260731.md` |
| `residual-wram-tilemap-runtime-reachability-20260731` | note | residual | `notes/residual-wram-tilemap-runtime-reachability-20260731.md` |
| `residual-wram-transformed-tilemap-runtime-20260801` | note | residual | `notes/residual-wram-transformed-tilemap-runtime-20260801.md` |
| `rom-ai-extra-pool-lifecycle-preflight-20260930` | note | rom | `notes/rom-ai-extra-pool-lifecycle-preflight-20260930.md` |
| `rom-alternate-dialogue-table-20260902` | note | rom | `notes/rom-alternate-dialogue-table-20260902.md` |
| `rom-animation-base-pairs-preflight-20261001` | note | rom | `notes/rom-animation-base-pairs-preflight-20261001.md` |
| `rom-animation-callee-effects-20261001` | note | rom | `notes/rom-animation-callee-effects-20261001.md` |
| `rom-animation-caller-predecessor-20261001` | note | rom | `notes/rom-animation-caller-predecessor-20261001.md` |
| `rom-animation-critical-writers-20261001` | note | rom | `notes/rom-animation-critical-writers-20261001.md` |
| `rom-animation-full-renderer-20261001` | note | rom | `notes/rom-animation-full-renderer-20261001.md` |
| `rom-animation-interprocedural-identities-20261001` | note | rom | `notes/rom-animation-interprocedural-identities-20261001.md` |
| `rom-animation-irq-arm-native-20261001` | note | rom | `notes/rom-animation-irq-arm-native-20261001.md` |
| `rom-animation-object-lifecycle-20261001` | note | rom | `notes/rom-animation-object-lifecycle-20261001.md` |
| `rom-animation-object-native-20261001` | note | rom | `notes/rom-animation-object-native-20261001.md` |
| `rom-animation-pool-caller-screen-20261001` | note | rom | `notes/rom-animation-pool-caller-screen-20261001.md` |
| `rom-animation-pool-lifecycle-20261001` | note | rom | `notes/rom-animation-pool-lifecycle-20261001.md` |
| `rom-animation-save-source-20261001` | note | rom | `notes/rom-animation-save-source-20261001.md` |
| `rom-animation-upstream-closure-20261001` | note | rom | `notes/rom-animation-upstream-closure-20261001.md` |
| `rom-animation-writer-domain-20261001` | note | rom | `notes/rom-animation-writer-domain-20261001.md` |
| `rom-bank-proof-work-plan-20261001` | note | rom | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` |
| `rom-bank-proof-work-plan-20261001` | note | rom | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` |
| `rom-bank-proof-work-plan-20261001` | note | rom | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-bank-proof-work-plan-20261001.md` |
| `rom-bank-proof-work-plan-20261001` | note | rom | `notes/rom-bank-proof-work-plan-20261001.md` |
| `rom-bank-runtime-replay-20261001` | note | rom | `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-bank-runtime-replay-20261001.md` |
| `rom-bank-runtime-replay-20261001` | note | rom | `notes/rom-bank-runtime-replay-20261001.md` |
| `rom-battle-condition-result-text-20260902` | note | rom | `notes/rom-battle-condition-result-text-20260902.md` |
| `rom-battle-distance-dispatcher-cfg-20260902` | note | rom | `notes/rom-battle-distance-dispatcher-cfg-20260902.md` |
| `rom-battle-effect-fixed-roundtrip-20261001` | note | rom | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-battle-effect-fixed-roundtrip-20261001.md` |
| `rom-battle-effect-fixed-roundtrip-20261001` | note | rom | `notes/rom-battle-effect-fixed-roundtrip-20261001.md` |
| `rom-boot-interwork-20260811` | note | rom | `notes/rom-boot-interwork-20260811.md` |
| `rom-boot-register-init-dependency-cfg-20260905` | note | rom | `notes/rom-boot-register-init-dependency-cfg-20260905.md` |
| `rom-bounded-index-u16-pair-table-20260904` | note | rom | `notes/rom-bounded-index-u16-pair-table-20260904.md` |
| `rom-cfg-proven-roots-20260811` | note | rom | `notes/rom-cfg-proven-roots-20260811.md` |
| `rom-cfg-proven-roots-v13-20260830` | note | rom | `notes/rom-cfg-proven-roots-v13-20260830.md` |
| `rom-cfg-proven-roots-v14-20260830` | note | rom | `notes/rom-cfg-proven-roots-v14-20260830.md` |
| `rom-cfg-proven-roots-v15-20260830` | note | rom | `notes/rom-cfg-proven-roots-v15-20260830.md` |
| `rom-cfg-proven-roots-v2-20260812` | note | rom | `notes/rom-cfg-proven-roots-v2-20260812.md` |
| `rom-cfg-proven-roots-v20-20260905` | note | rom | `notes/rom-cfg-proven-roots-v20-20260905.md` |
| `rom-chapter-script-consumer-roots-20260902` | note | rom | `notes/rom-chapter-script-consumer-roots-20260902.md` |
| `rom-chapter-script-inventory-20260809` | note | rom | `notes/rom-chapter-script-inventory-20260809.md` |
| `rom-coroutine-record-lifecycle-preflight-20261001` | note | rom | `notes/rom-coroutine-record-lifecycle-preflight-20261001.md` |
| `rom-cutscene-secondary-ptr-ab-20261001` | note | rom | `notes/evidence/rom-cutscene-secondary-ptr-ab-20261001-v1/implementation/notes/rom-cutscene-secondary-ptr-ab-20261001.md` |
| `rom-cutscene-secondary-ptr-ab-20261001` | note | rom | `notes/rom-cutscene-secondary-ptr-ab-20261001.md` |
| `rom-cutscene-secondary-ptr-contract-20261001` | note | rom | `notes/rom-cutscene-secondary-ptr-contract-20261001.md` |
| `rom-data-table-b-partial-bank-20261001` | note | rom | `notes/evidence/rom-data-table-b-partial-bank-20261001-v1/implementation/notes/rom-data-table-b-partial-bank-20261001.md` |
| `rom-data-table-b-partial-bank-20261001` | note | rom | `notes/rom-data-table-b-partial-bank-20261001.md` |
| `rom-direct-cpuset-inventory-survey-20260730` | note | rom | `notes/rom-direct-cpuset-inventory-survey-20260730.md` |
| `rom-direct-dma-inventory-survey-20260730` | note | rom | `notes/rom-direct-dma-inventory-survey-20260730.md` |
| `rom-display-text-delta-tier1-20261001` | note | rom | `notes/rom-display-text-delta-tier1-20261001.md` |
| `rom-display-text-parameter-flow-tdd-20261001` | note | rom | `notes/rom-display-text-parameter-flow-tdd-20261001.md` |
| `rom-expansion-character-bundle-relocation-20260731` | note | rom | `notes/rom-expansion-character-bundle-relocation-20260731.md` |
| `rom-fixed-animation-descriptor-groups-20260902` | note | rom | `notes/rom-fixed-animation-descriptor-groups-20260902.md` |
| `rom-fixed-consumer-text-inventory-20260811` | note | rom | `notes/rom-fixed-consumer-text-inventory-20260811.md` |
| `rom-fixed-index-u8-tail-20260905` | note | rom | `notes/rom-fixed-index-u8-tail-20260905.md` |
| `rom-fixed-pair-tables-20260904` | note | rom | `notes/rom-fixed-pair-tables-20260904.md` |
| `rom-fixed-text-route-preflight-20261001` | note | rom | `notes/rom-fixed-text-route-preflight-20261001.md` |
| `rom-large-unknown-anchor-screen-20261001` | note | rom | `notes/rom-large-unknown-anchor-screen-20261001.md` |
| `rom-later-cfg-renderer-consumers-preflight-20261001` | note | rom | `notes/rom-later-cfg-renderer-consumers-preflight-20261001.md` |
| `rom-low-script-delta-tier1-20261001` | note | rom | `notes/rom-low-script-delta-tier1-20261001.md` |
| `rom-low-script-fixed-consumers-preflight-20261001` | note | rom | `notes/rom-low-script-fixed-consumers-preflight-20261001.md` |
| `rom-m4a-initializer-chain-20260829` | note | rom | `notes/rom-m4a-initializer-chain-20260829.md` |
| `rom-map-resource-fixed-roundtrip-20261002` | note | rom | `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-map-resource-fixed-roundtrip-20261002.md` |
| `rom-map-resource-fixed-roundtrip-20261002` | note | rom | `notes/rom-map-resource-fixed-roundtrip-20261002.md` |
| `rom-map-sprites-partial-bank-20261001` | note | rom | `notes/evidence/rom-map-sprites-partial-bank-20261001-v1/implementation/notes/rom-map-sprites-partial-bank-20261001.md` |
| `rom-map-sprites-partial-bank-20261001` | note | rom | `notes/rom-map-sprites-partial-bank-20261001.md` |
| `rom-menu-gfx-pointer-ab-20261001` | note | rom | `notes/rom-menu-gfx-pointer-ab-20261001.md` |
| `rom-menu-portrait-palette-inventory-20260820` | note | rom | `notes/rom-menu-portrait-palette-inventory-20260820.md` |
| `rom-mp2k-dispatcher-20260829` | note | rom | `notes/rom-mp2k-dispatcher-20260829.md` |
| `rom-pointer-lz77-inventory-export-20260730` | note | rom | `notes/rom-pointer-lz77-inventory-export-20260730.md` |
| `rom-prebattle-menu-controller-cfg-20260905` | note | rom | `notes/rom-prebattle-menu-controller-cfg-20260905.md` |
| `rom-ram-protocol-tag-preflight-20261001` | note | rom | `notes/rom-ram-protocol-tag-preflight-20261001.md` |
| `rom-referenced-text-slot-padding-20260820` | note | rom | `notes/rom-referenced-text-slot-padding-20260820.md` |
| `rom-release-gate-work-plan-20261001` | note | rom | `notes/evidence/rom-battle-effect-fixed-roundtrip-20261001-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` |
| `rom-release-gate-work-plan-20261001` | note | rom | `notes/evidence/rom-map-resource-fixed-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` |
| `rom-release-gate-work-plan-20261001` | note | rom | `notes/evidence/rom-map-resource-relocation-roundtrip-20261002-v1/implementation/notes/rom-release-gate-work-plan-20261001.md` |
| `rom-release-gate-work-plan-20261001` | note | rom | `notes/rom-release-gate-work-plan-20261001.md` |
| `rom-renderer-batch-plan-20261001` | note | rom | `notes/rom-renderer-batch-plan-20261001.md` |
| `rom-renderer-excluded-roots-preflight-20260930` | note | rom | `notes/rom-renderer-excluded-roots-preflight-20260930.md` |
| `rom-renderer-flow-cost-20261001` | note | rom | `notes/rom-renderer-flow-cost-20261001.md` |
| `rom-renderer-handler-context-preflight-20260930` | note | rom | `notes/rom-renderer-handler-context-preflight-20260930.md` |
| `rom-renderer-records-delta-tier1-20261001` | note | rom | `notes/rom-renderer-records-delta-tier1-20261001.md` |
| `rom-renderer-source-plan-20261001` | note | rom | `notes/rom-renderer-source-plan-20261001.md` |
| `rom-renderer-source-replay-20261001` | note | rom | `notes/rom-renderer-source-replay-20261001.md` |
| `rom-renderer-text-inventory-20260809` | note | rom | `notes/rom-renderer-text-inventory-20260809.md` |
| `rom-scene-source-closures-20260905` | note | rom | `notes/rom-scene-source-closures-20260905.md` |
| `rom-scene-visual-source-ranges-20260820` | note | rom | `notes/rom-scene-visual-source-ranges-20260820.md` |
| `rom-selector-code-windows-20260820` | note | rom | `notes/rom-selector-code-windows-20260820.md` |
| `rom-selector-direct-source-records-20260820` | note | rom | `notes/rom-selector-direct-source-records-20260820.md` |
| `rom-selector-text-bindings-20260811` | note | rom | `notes/rom-selector-text-bindings-20260811.md` |
| `rom-soundmain-relocated-cfg-20260828` | note | rom | `notes/rom-soundmain-relocated-cfg-20260828.md` |
| `rom-staged-gpu-copy-inventory-20260730` | note | rom | `notes/rom-staged-gpu-copy-inventory-20260730.md` |
| `rom-story-callback-dependency-closures-20260905` | note | rom | `notes/rom-story-callback-dependency-closures-20260905.md` |
| `rom-story-next-dependency-cfg-20260905` | note | rom | `notes/rom-story-next-dependency-cfg-20260905.md` |
| `rom-story-selector-dependency-cfg-20260905` | note | rom | `notes/rom-story-selector-dependency-cfg-20260905.md` |
| `rom-task-callback-078e38-closure-20260905` | note | rom | `notes/rom-task-callback-078e38-closure-20260905.md` |
| `rom-task-callback-alignment-gap-candidate-20260905` | note | rom | `notes/rom-task-callback-alignment-gap-candidate-20260905.md` |
| `rom-training-text-script-inventory-20260811` | note | rom | `notes/rom-training-text-script-inventory-20260811.md` |
| `rom-unknown-cluster-refresh-20260901` | note | rom | `notes/rom-unknown-cluster-refresh-20260901.md` |
| `rom-unknown-cluster-refresh-20260905` | note | rom | `notes/rom-unknown-cluster-refresh-20260905.md` |
| `rom-v17-v18-helper-cfg-20260904` | note | rom | `notes/rom-v17-v18-helper-cfg-20260904.md` |
| `rom-value-range-text-inventory-20260811` | note | rom | `notes/rom-value-range-text-inventory-20260811.md` |
| `runtime-bg-composites-20260730` | note | runtime | `notes/runtime-bg-composites-20260730.md` |
| `runtime-checkpoints-data-integrity-issue-20260806` | note | runtime | `notes/runtime-checkpoints-data-integrity-issue-20260806.md` |
| `runtime-font-tile-provenance-20260730` | note | runtime | `notes/runtime-font-tile-provenance-20260730.md` |
| `runtime-layer-static-provenance-20260730` | note | runtime | `notes/runtime-layer-static-provenance-20260730.md` |
| `runtime-mode0-screen-compositor-20260730` | note | runtime | `notes/runtime-mode0-screen-compositor-20260730.md` |
| `battle-effect-controlled-phase-extension-20260809` | note | visual | `notes/battle-effect-controlled-phase-extension-20260809.md` |
| `battle-effect-direct-spawn-runtime-20260802` | note | visual | `notes/battle-effect-direct-spawn-runtime-20260802.md` |
| `battle-effect-frame-phase-20260801` | note | visual | `notes/battle-effect-frame-phase-20260801.md` |
| `battle-effect-group1-pixel-ab-20260801` | note | visual | `notes/battle-effect-group1-pixel-ab-20260801.md` |
| `battle-effect-group11-pixel-ab-20260801` | note | visual | `notes/battle-effect-group11-pixel-ab-20260801.md` |
| `battle-effect-group12-group13-route-audit-20260802` | note | visual | `notes/battle-effect-group12-group13-route-audit-20260802.md` |
| `battle-effect-group13-pixel-ab-20260802` | note | visual | `notes/battle-effect-group13-pixel-ab-20260802.md` |
| `battle-effect-group14-pixel-ab-20260801` | note | visual | `notes/battle-effect-group14-pixel-ab-20260801.md` |
| `battle-effect-group15-allocator-side-runtime-20260801` | note | visual | `notes/battle-effect-group15-allocator-side-runtime-20260801.md` |
| `battle-effect-group15-natural-runtime-20260802` | note | visual | `notes/battle-effect-group15-natural-runtime-20260802.md` |
| `battle-effect-group15-pixel-ab-20260802` | note | visual | `notes/battle-effect-group15-pixel-ab-20260802.md` |
| `battle-effect-group16-natural-pixel-ab-20260802` | note | visual | `notes/battle-effect-group16-natural-pixel-ab-20260802.md` |
| `battle-effect-group17-natural-pixel-ab-20260802` | note | visual | `notes/battle-effect-group17-natural-pixel-ab-20260802.md` |
| `battle-effect-group18-controlled-pixel-ab-20260802` | note | visual | `notes/battle-effect-group18-controlled-pixel-ab-20260802.md` |
| `battle-effect-group18-natural-pixel-ab-20260802` | note | visual | `notes/battle-effect-group18-natural-pixel-ab-20260802.md` |
| `battle-effect-group2-pixel-ab-20260802` | note | visual | `notes/battle-effect-group2-pixel-ab-20260802.md` |
| `battle-effect-group2-route-stop-20260802` | note | visual | `notes/battle-effect-group2-route-stop-20260802.md` |
| `battle-effect-group3-controlled-pixel-ab-20260802` | note | visual | `notes/battle-effect-group3-controlled-pixel-ab-20260802.md` |
| `battle-effect-group3-natural-expiry-phase-20260802` | note | visual | `notes/battle-effect-group3-natural-expiry-phase-20260802.md` |
| `battle-effect-group3-natural-pixel-ab-20260802` | note | visual | `notes/battle-effect-group3-natural-pixel-ab-20260802.md` |
| `battle-effect-group4-natural-pixel-ab-20260802` | note | visual | `notes/battle-effect-group4-natural-pixel-ab-20260802.md` |
| `battle-effect-group5-pixel-ab-20260801` | note | visual | `notes/battle-effect-group5-pixel-ab-20260801.md` |
| `battle-effect-group6-controlled-pixel-ab-20260809` | note | visual | `notes/battle-effect-group6-controlled-pixel-ab-20260809.md` |
| `battle-effect-group6-entry-audit-20260806` | note | visual | `notes/battle-effect-group6-entry-audit-20260806.md` |
| `battle-effect-groups7-12-controlled-pixel-ab-20260809` | note | visual | `notes/battle-effect-groups7-12-controlled-pixel-ab-20260809.md` |
| `battle-effect-hardcoded-selector-producers-20260802` | note | visual | `notes/battle-effect-hardcoded-selector-producers-20260802.md` |
| `battle-effect-observed-frame-phases-20260801` | note | visual | `notes/battle-effect-observed-frame-phases-20260801.md` |
| `battle-effect-resource-relocation-20260731` | note | visual | `notes/battle-effect-resource-relocation-20260731.md` |
| `battle-effect-resource-writeback-20260731` | note | visual | `notes/battle-effect-resource-writeback-20260731.md` |
| `battle-effect-runtime-oam-bindings-20260801` | note | visual | `notes/battle-effect-runtime-oam-bindings-20260801.md` |
| `battle-effect-runtime-oam-task-bindings-20260801` | note | visual | `notes/battle-effect-runtime-oam-task-bindings-20260801.md` |
| `bg-resource-relocation-20260731` | note | visual | `notes/bg-resource-relocation-20260731.md` |
| `bg-resource-writeback-20260731` | note | visual | `notes/bg-resource-writeback-20260731.md` |
| `character-battle-graphics-pixel-ab-20260801` | note | visual | `notes/character-battle-graphics-pixel-ab-20260801.md` |
| `character-battle-graphics-writeback-20260731` | note | visual | `notes/character-battle-graphics-writeback-20260731.md` |
| `character-battle-structure-writeback-20260731` | note | visual | `notes/character-battle-structure-writeback-20260731.md` |
| `character-runtime-oam-bindings-20260730` | note | visual | `notes/character-runtime-oam-bindings-20260730.md` |
| `character-runtime-oam-task-bindings-20260730` | note | visual | `notes/character-runtime-oam-task-bindings-20260730.md` |
| `tile-asset-resource-relocation-20260731` | note | visual | `notes/tile-asset-resource-relocation-20260731.md` |
| `tile-assets-descriptor-player-visible-20260809` | note | visual | `notes/tile-assets-descriptor-player-visible-20260809.md` |

## 台账 `missing` 条目

（无）

## 全部条目

| id | kind | category | 状态 | 台账 | 命中数 |
| --- | --- | --- | --- | --- | ---: |
| `accept_prebattle_candidate` | tool | code | `build` | — | 5 |
| `addresses` | note | other | `build` | — | 115 |
| `analyze_battle_action_template_semantics` | tool | code | `build` | — | 7 |
| `analyze_battle_action_transactions` | tool | code | `build` | — | 4 |
| `analyze_battle_ai_status_policy` | tool | code | `build` | — | 4 |
| `analyze_battle_ai_utility_policy` | tool | code | `build` | — | 6 |
| `analyze_battle_condition_interpreter` | tool | code | `build` | — | 4 |
| `analyze_battle_controller_checkpoints` | tool | code | `build` | — | 16 |
| `analyze_battle_damage_hit_formula` | tool | code | `build` | — | 5 |
| `analyze_battle_defense_preparation` | tool | code | `build` | — | 4 |
| `analyze_battle_defense_reaction` | tool | code | `build` | — | 4 |
| `analyze_battle_effect_resolution` | tool | code | `build` | — | 4 |
| `analyze_battle_hit_modifiers` | tool | code | `build` | — | 3 |
| `analyze_battle_objective_transitions` | tool | code | `build` | — | 4 |
| `analyze_battle_reaction_matrix` | tool | code | `build` | — | 4 |
| `analyze_battle_reaction_priority` | tool | code | `build` | — | 4 |
| `analyze_battle_resource_transactions` | tool | code | `build` | — | 4 |
| `analyze_battle_status_attribute_modifiers` | tool | code | `build` | — | 4 |
| `analyze_battle_status_consumers` | tool | code | `build` | — | 4 |
| `analyze_battle_status_expiry` | tool | code | `build` | — | 5 |
| `analyze_battle_status_hit_count_modifier` | tool | code | `build` | — | 4 |
| `analyze_battle_status_linked_resolution` | tool | code | `build` | — | 4 |
| `analyze_battle_status_participant_consumption` | tool | code | `build` | — | 4 |
| `analyze_battle_status_stage_policy` | tool | code | `build` | — | 4 |
| `analyze_battle_status_storage` | tool | code | `build` | — | 4 |
| `analyze_battle_status_transformation` | tool | code | `build` | — | 4 |
| `analyze_battle_unit_eligibility` | tool | code | `build` | — | 4 |
| `analyze_battle_unit_selection` | tool | code | `build` | — | 4 |
| `analyze_dialogue_render` | tool | code | `build` | — | 3 |
| `analyze_mgba_zero_input_cycle` | tool | code | `build` | — | 4 |
| `analyze_scenario_41_gpu` | tool | code | `build` | — | 6 |
| `analyze_table` | tool | code | `build` | — | 5 |
| `analyze_tile_table` | tool | code | `build` | — | 2 |
| `arm64_const` | tool | code | `build` | — | 2 |
| `arm_const` | tool | code | `build` | — | 3 |
| `audit_re_completion` | tool | code | `build` | — | 9 |
| `automated_test` | tool | code | `build` | — | 38 |
| `battle-config-format` | note | battle | `build` | — | 19 |
| `battle-config-unsafe-template-fix-20260710` | note | battle | `build` | — | 8 |
| `battle-effect-affine-runtime-v1` | artifact | visual | `build` | — | 11 |
| `battle-effect-frame-phase-group1-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-frame-phase-group14-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-frame-phase-group16-natural-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-frame-phase-group17-natural-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-frame-phase-group18-natural-sequence-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-frame-phase-group2-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-frame-phase-group3-natural-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-frame-phase-group4-natural-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-frame-phase-group5-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-frame-phase-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group03-controlled-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group03-natural-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group06-controlled-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group07-controlled-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group08-controlled-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group09-controlled-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group1-pixel-ab-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-group10-controlled-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group11-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group12-ai-observer-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group12-controlled-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group13-natural-runtime-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-group13-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group14-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group15-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group16-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group17-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group18-controlled-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group18-natural-checkpoint-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group18-natural-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group2-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group4-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-group5-pixel-ab-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-resource-pairs-v1` | artifact | visual | `build` | — | 28 |
| `battle-effect-resource-relocation-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-resource-writeback-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-runtime-oam-bindings-v1` | artifact | visual | `build` | — | 3 |
| `battle-effect-runtime-oam-task-bindings-v1` | artifact | visual | `build` | — | 2 |
| `battle-effect-sequence-bindings-v1` | artifact | visual | `build` | — | 16 |
| `battle-effect-sprite-animations-v1` | artifact | visual | `build` | — | 12 |
| `battle-encounters-story-visual-pixel-ab-v1` | artifact | battle | `build` | — | 2 |
| `battle-presentation-glyphs-v1` | artifact | battle | `build` | — | 13 |
| `battle-status-bars-v1` | artifact | battle | `build` | — | 6 |
| `battle-system-restoration-evidence-20260723` | note | battle | `build` | — | 11 |
| `battle-visual-catalog-v1` | artifact | visual | `build` | — | 12 |
| `battle-visual-runtime-timelines-v1` | artifact | visual | `build` | — | 9 |
| `benchmark_clock` | tool | code | `build` | — | 3 |
| `bg-resource-canvases-v1` | artifact | visual | `build` | — | 13 |
| `bg-resource-relocation-v1` | artifact | visual | `build` | — | 2 |
| `bg-resource-writeback-v1` | artifact | visual | `build` | — | 2 |
| `bg-scene-selection-v1` | artifact | visual | `build` | — | 10 |
| `bpf_const` | tool | code | `build` | — | 2 |
| `build_action_submit_runtime_probe` | tool | code | `build` | — | 3 |
| `build_adjacent_tutorial_runtime_probe` | tool | code | `build` | — | 3 |
| `build_alternate_chapter_runtime_probe` | tool | code | `build` | — | 9 |
| `build_audio_runtime_probe` | tool | code | `build` | — | 3 |
| `build_battle_catalog_runtime_probe` | tool | code | `build` | — | 2 |
| `build_battle_effect_runtime_probe` | tool | code | `build` | — | 3 |
| `build_battle_message_runtime_probe` | tool | code | `build` | — | 5 |
| `build_battle_start_runtime_probe` | tool | code | `build` | — | 4 |
| `build_chapter_script_probe` | tool | code | `build` | — | 18 |
| `build_chapter_semantic_probe` | tool | code | `build` | — | 3 |
| `build_character_fbff_control_rom` | tool | code | `build` | — | 2 |
| `build_character_growth_probe` | tool | code | `build` | — | 4 |
| `build_controlled_audio_runtime_probe` | tool | code | `build` | — | 11 |
| `build_controller_path_runtime_probe` | tool | code | `build` | — | 5 |
| `build_cross_player_cgb_probe` | tool | code | `build` | — | 6 |
| `build_db_patches` | tool | code | `build` | — | 40 |
| `build_delayed_audio_retrigger_probe` | tool | code | `build` | — | 6 |
| `build_forced_save_case_probe` | tool | code | `build` | — | 3 |
| `build_function_pointer_runtime_probe` | tool | code | `build` | — | 3 |
| `build_levels_runtime_probe` | tool | code | `build` | — | 3 |
| `build_macos_mgba` | tool | code | `build` | — | 12 |
| `build_mod` | tool | code | `build` | — | 42 |
| `build_natural_load_runtime_probe` | tool | code | `build` | — | 3 |
| `build_natural_save_runtime_probe` | tool | code | `build` | — | 4 |
| `build_numeric_writer_trace_probe` | tool | code | `build` | — | 3 |
| `build_player_control_runtime_probe` | tool | code | `build` | — | 4 |
| `build_postbattle_natural_save_probe` | tool | code | `build` | — | 4 |
| `build_postbattle_save_probe` | tool | code | `build` | — | 4 |
| `build_profile_text_runtime_probe` | tool | code | `build` | — | 3 |
| `build_relocated_chapter_runtime_probe` | tool | code | `build` | — | 4 |
| `build_resource_pointer_runtime_probe` | tool | code | `build` | — | 4 |
| `build_save_group_runtime_probe` | tool | code | `build` | — | 3 |
| `build_save_state_runtime_probe` | tool | code | `build` | — | 33 |
| `build_skill_detail_runtime_probe` | tool | code | `build` | — | 3 |
| `build_skill_relation_runtime_probe` | tool | code | `build` | — | 5 |
| `build_skill_runtime_probe` | tool | code | `build` | — | 3 |
| `build_text_writer_trace_probe` | tool | code | `build` | — | 3 |
| `build_tilemap_writer_trace_probe` | tool | code | `build` | — | 3 |
| `build_training_levels_runtime_probe` | tool | code | `build` | — | 2 |
| `chapter_script_analyzer` | tool | code | `build` | — | 5 |
| `chapter_script_codec` | tool | code | `build` | — | 9 |
| `character-battle-bundle-relocation-v1` | artifact | visual | `build` | — | 2 |
| `character-battle-graphics-pixel-ab-v1` | artifact | visual | `build` | — | 2 |
| `character-battle-graphics-writeback-v1` | artifact | visual | `build` | — | 2 |
| `character-battle-palette-writeback-v1` | artifact | visual | `build` | — | 2 |
| `character-battle-structure-writeback-v1` | artifact | visual | `build` | — | 2 |
| `character-battle-visual-resource-matrix-v1` | artifact | visual | `build` | — | 3 |
| `character-battle-visuals-v1` | artifact | visual | `build` | — | 19 |
| `character-definition-source-20260711` | note | visual | `build` | — | 11 |
| `character-fbff-runtime-v1` | artifact | visual | `build` | — | 11 |
| `character-runtime-oam-bindings-v1` | artifact | visual | `build` | — | 3 |
| `character-runtime-oam-task-bindings-v1` | artifact | visual | `build` | — | 2 |
| `character-runtime-unit-oam-bindings-20260730` | note | visual | `build` | — | 2 |
| `character-runtime-unit-oam-bindings-v1` | artifact | visual | `build` | reused | 7 |
| `character-stats-addresses` | note | visual | `build` | — | 8 |
| `check_comet_project_policy` | tool | code | `build` | — | 6 |
| `compare_mgba_audio_capture` | tool | code | `build` | — | 8 |
| `compare_mgba_cgb_capture` | tool | code | `build` | — | 5 |
| `compare_mgba_cross_player_cgb_capture` | tool | code | `build` | — | 4 |
| `compare_mgba_linked_audio_capture` | tool | code | `build` | — | 6 |
| `compare_mgba_retrigger_capture` | tool | code | `build` | — | 4 |
| `compare_wram_regions` | tool | code | `build` | — | 2 |
| `cutscene-obj-bundle-relocation-v1` | artifact | presentation | `build` | — | 2 |
| `cutscene-obj-id1-pixel-ab-v1` | artifact | presentation | `build` | — | 2 |
| `cutscene-obj-id1-primary-ptr-ab-v1` | artifact | presentation | `build` | — | 6 |
| `cutscene-obj-v1` | artifact | presentation | `build` | — | 4 |
| `data-table-b-message0-pointer-pixel-ab-v1` | artifact | other | `build` | — | 3 |
| `decode_controller_path_runtime_probe` | tool | code | `build` | — | 3 |
| `decode_dialogue_record` | tool | code | `build` | — | 12 |
| `decode_m4a_tracks` | tool | code | `build` | — | 7 |
| `dialogue-font-v2` | artifact | other | `build` | — | 21 |
| `dialogue-format` | note | other | `build` | — | 6 |
| `dialogue-render-analysis` | note | other | `build` | — | 4 |
| `dialogue-watch-record-bank` | note | other | `build` | — | 4 |
| `dialogue-watch-sb-struct` | note | other | `build` | — | 4 |
| `dialogue-watch-vram-glyph` | note | other | `build` | — | 5 |
| `dialogue-watch-vram-tilemap` | note | other | `build` | — | 5 |
| `dialogue-watch-wram` | note | other | `build` | — | 7 |
| `diff_memory_regions` | tool | code | `build` | — | 1 |
| `direct-image-palette-relocation-v1` | artifact | other | `build` | — | 2 |
| `disasm_thumb` | tool | code | `build` | — | 27 |
| `e2e` | artifact | overview | `build` | — | 5 |
| `evm_const` | tool | code | `build` | — | 2 |
| `export_battle_effect_affine_runtime` | tool | code | `build` | — | 4 |
| `export_battle_effect_resource_pairs` | tool | code | `build` | — | 3 |
| `export_battle_effect_sequence_bindings` | tool | code | `build` | — | 3 |
| `export_battle_effect_sprite_animations` | tool | code | `build` | — | 3 |
| `export_battle_presentation_glyphs` | tool | code | `build` | — | 4 |
| `export_battle_visual_catalog` | tool | code | `build` | — | 3 |
| `export_battle_visual_runtime_timelines` | tool | code | `build` | — | 3 |
| `export_bg_resource_canvases` | tool | code | `build` | — | 3 |
| `export_bg_scene_selection` | tool | code | `build` | — | 3 |
| `export_character_battle_visuals` | tool | code | `build` | — | 4 |
| `export_cutscene_obj_assets` | tool | code | `build` | — | 3 |
| `export_dialogue_font_atlases` | tool | code | `build` | — | 3 |
| `export_map_canvases` | tool | code | `build` | — | 3 |
| `export_menu_portraits` | tool | code | `build` | — | 3 |
| `export_rom_pointer_lz77_inventory` | tool | code | `build` | — | 3 |
| `export_scenario_41_attack_animation` | tool | code | `build` | — | 2 |
| `export_scenario_41_attack_gpu_bases` | tool | code | `build` | — | 2 |
| `export_scenario_41_combat_reference` | tool | code | `build` | — | 2 |
| `export_scenario_41_extended_reference` | tool | code | `build` | — | 2 |
| `export_scenario_41_prebattle_reference` | tool | code | `build` | — | 2 |
| `export_scenario_41_reference` | tool | code | `build` | — | 7 |
| `export_scene_visual_packs` | tool | code | `build` | — | 4 |
| `export_sprite_definition_animations` | tool | code | `build` | — | 3 |
| `export_sprite_definition_runtime_chain` | tool | code | `build` | — | 3 |
| `export_story_scene_layer_bindings` | tool | code | `build` | — | 3 |
| `export_story_scene_timelines` | tool | code | `build` | — | 7 |
| `export_story_visual_layers` | tool | code | `build` | — | 5 |
| `export_tile_asset_bg_layers` | tool | code | `build` | — | 8 |
| `export_world_map_backgrounds` | tool | code | `build` | — | 4 |
| `export_world_map_runtime` | tool | code | `build` | — | 3 |
| `extract_all_structures` | tool | code | `build` | — | 20 |
| `extract_audio` | tool | code | `build` | — | 16 |
| `extract_audio_assets` | tool | code | `build` | — | 7 |
| `extract_audio_command_table` | tool | code | `build` | — | 3 |
| `extract_audio_cue_calls` | tool | code | `build` | — | 6 |
| `extract_audio_engine` | tool | code | `build` | — | 3 |
| `extract_audio_resource_sets` | tool | code | `build` | — | 8 |
| `extract_battle_ai_planner` | tool | code | `build` | — | 5 |
| `extract_battle_content_catalog` | tool | code | `build` | — | 4 |
| `extract_battle_controller_states` | tool | code | `build` | — | 7 |
| `extract_battle_effect_templates` | tool | code | `build` | — | 3 |
| `extract_chapter_flow_tables` | tool | code | `build` | — | 3 |
| `extract_character_definitions` | tool | code | `build` | — | 12 |
| `extract_character_growth` | tool | code | `build` | — | 5 |
| `extract_dialogue_full` | tool | code | `build` | — | 7 |
| `extract_graphics_resource_sets` | tool | code | `build` | — | 2 |
| `extract_positions` | tool | code | `build` | — | 14 |
| `extract_save_descriptors` | tool | code | `build` | — | 4 |
| `extract_skill_templates` | tool | code | `build` | — | 6 |
| `extract_text_block` | tool | code | `build` | — | 6 |
| `extract_tileset` | tool | code | `build` | — | 47 |
| `find_pointer_refs` | tool | code | `build` | — | 6 |
| `find_resource_tables` | tool | code | `build` | — | 2 |
| `find_similar_tables` | tool | code | `build` | — | 3 |
| `find_sjis_blocks` | tool | code | `build` | — | 10 |
| `find_thumb_calls` | tool | code | `build` | — | 15 |
| `free-space` | note | other | `build` | — | 12 |
| `gba_image_export` | tool | code | `build` | — | 18 |
| `gba_utils` | tool | code | `build` | — | 2 |
| `generate_butano_battle_action_content` | tool | code | `build` | — | 11 |
| `generate_butano_battle_runtime_assets` | tool | code | `build` | — | 15 |
| `generate_butano_battle_unit_content` | tool | code | `build` | — | 11 |
| `generate_scenario_41_assets` | tool | code | `build` | — | 14 |
| `generate_scenario_41_attack_animation_assets` | tool | code | `build` | — | 2 |
| `generate_scenario_41_audio_assets` | tool | code | `build` | — | 2 |
| `generate_scenario_41_prebattle_assets` | tool | code | `build` | — | 2 |
| `generate_scenario_41_sfx_assets` | tool | code | `build` | — | 2 |
| `generic-sprite-bundle-relocation-v1` | artifact | other | `build` | — | 2 |
| `image_utils` | tool | code | `build` | — | 2 |
| `import_battle_config` | tool | code | `build` | — | 24 |
| `import_chapter_scripts` | tool | code | `build` | — | 7 |
| `import_dialogue` | tool | code | `build` | — | 17 |
| `import_dialogue_var` | tool | code | `build` | — | 14 |
| `import_map` | tool | code | `build` | — | 8 |
| `import_rom_to_editor` | tool | code | `build` | — | 6 |
| `initializer-resource-pack-v1` | artifact | other | `build` | — | 2 |
| `inspect_block` | tool | code | `build` | — | 3 |
| `inspect_mgba_savestate` | tool | code | `build` | — | 53 |
| `inspect_wram_region` | tool | code | `build` | — | 2 |
| `levels-status-per-level-ab-v1` | artifact | other | `build` | — | 6 |
| `lldb_trace_dialogue_callers` | tool | code | `build` | — | 5 |
| `lz77-palette-runtime-v1` | artifact | other | `build` | — | 3 |
| `m4a_channels` | tool | code | `build` | — | 4 |
| `m4a_command_vm` | tool | code | `build` | — | 8 |
| `m4a_envelope` | tool | code | `build` | — | 6 |
| `m4a_pitch_step` | tool | code | `build` | — | 6 |
| `m4a_runtime_channels` | tool | code | `build` | — | 4 |
| `m4a_scheduler` | tool | code | `build` | — | 13 |
| `m4a_song_engine` | tool | code | `build` | — | 11 |
| `m4a_track_state` | tool | code | `build` | — | 6 |
| `m680x_const` | tool | code | `build` | — | 2 |
| `m68k_const` | tool | code | `build` | — | 2 |
| `macos-intel-runtime-preflight-20260715` | note | other | `build` | — | 3 |
| `macos_mgba_runtime_residue` | tool | code | `build` | — | 6 |
| `map-canvases-v1` | artifact | map | `build` | reused | 21 |
| `map-events-e4-handler-pixel-ab-v1` | artifact | map | `build` | — | 3 |
| `map-resource-relocation-v1` | artifact | map | `build` | — | 2 |
| `map-resource-writeback-v1` | artifact | map | `build` | — | 2 |
| `map-sprites-definition-id1-pixel-ab-v1` | artifact | map | `build` | — | 2 |
| `map41-primary-layout-pixel-ab-v1` | artifact | map | `build` | — | 2 |
| `map41-visual-resource-matrix-v1` | artifact | map | `build` | — | 4 |
| `map_m4a_instruments` | tool | code | `build` | — | 7 |
| `menu-portrait-pixel-ab-v1` | artifact | presentation | `build` | — | 2 |
| `menu-portrait-relocation-v1` | artifact | presentation | `build` | — | 2 |
| `menu-portrait-writeback-v1` | artifact | presentation | `build` | — | 2 |
| `menu-portraits-v1` | artifact | presentation | `build` | — | 15 |
| `mgba-headless-snapshot` | tool | code | `build` | — | 15 |
| `mgba_gdb_probe` | tool | code | `build` | — | 19 |
| `mgba_runtime_safety` | tool | code | `build` | — | 7 |
| `mips_const` | tool | code | `build` | — | 2 |
| `mos65xx_const` | tool | code | `build` | — | 2 |
| `motion-effect-parameter-pixel-ab-v1` | artifact | other | `build` | — | 3 |
| `ninja-tool-addresses` | note | other | `build` | — | 4 |
| `ocr_report` | tool | code | `build` | — | 5 |
| `ocr_screenshot` | tool | code | `build` | — | 8 |
| `overview-gradient-overlay-v1` | artifact | overview | `build` | — | 10 |
| `patch_mgba_savestate_memory` | tool | code | `build` | — | 3 |
| `patch_safety` | tool | code | `build` | — | 6 |
| `patch_sjis` | tool | code | `build` | — | 7 |
| `populate_bank_json` | tool | code | `build` | — | 17 |
| `portrait-palette-producers-v1` | artifact | presentation | `build` | — | 5 |
| `positions-rom-source-20260710` | note | other | `build` | — | 9 |
| `ppc_const` | tool | code | `build` | — | 2 |
| `profile_table_blocks` | tool | code | `build` | — | 4 |
| `project_resource_guard` | tool | code | `build` | — | 10 |
| `project_status` | tool | code | `build` | — | 1 |
| `published_call_observer` | tool | code | `build` | — | 12 |
| `re-completion-audit` | note | other | `build` | — | 11 |
| `render_m4a_midi` | tool | code | `build` | — | 7 |
| `render_m4a_pcm_bank` | tool | code | `build` | — | 3 |
| `render_scenario_41_gpu` | tool | code | `build` | — | 16 |
| `residual-lz77-graphics-relocation-v1` | artifact | residual | `build` | — | 3 |
| `residual-text-bg-tilemap-relocation-v1` | artifact | residual | `build` | — | 2 |
| `residual-text-bg-tilemap-resource-ownership-v1` | artifact | residual | `build` | — | 2 |
| `residual-wram-crop-tilemap-runtime-v1` | artifact | residual | `build` | — | 2 |
| `residual-wram-derived-tilemap-relocation-v1` | artifact | residual | `build` | — | 2 |
| `residual-wram-tilemap-abi-v1` | artifact | residual | `build` | — | 2 |
| `residual-wram-tilemap-pixel-ab-v1` | artifact | residual | `build` | — | 3 |
| `residual-wram-tilemap-relocation-v1` | artifact | residual | `build` | — | 2 |
| `residual-wram-tilemap-resource-ownership-v1` | artifact | residual | `build` | — | 2 |
| `residual-wram-tilemap-runtime-v1` | artifact | residual | `build` | — | 2 |
| `residual-wram-tilemap-runtime-v2` | artifact | residual | `build` | — | 3 |
| `residual-wram-transformed-tilemap-runtime-v1` | artifact | residual | `build` | — | 2 |
| `residual-wram-visual-metadata-abi-v2` | artifact | residual | `build` | — | 3 |
| `resource-locations` | note | other | `build` | — | 18 |
| `revoke_false_story_banks` | tool | code | `build` | — | 3 |
| `riscv_const` | tool | code | `build` | — | 2 |
| `rom-alternate-dialogue-table-v1` | artifact | rom | `build` | — | 5 |
| `rom-animation-descriptor-pool-v2` | artifact | rom | `build` | — | 3 |
| `rom-battle-condition-records-v1` | artifact | rom | `build` | — | 6 |
| `rom-battle-controller-cfg-v1` | artifact | rom | `build` | — | 12 |
| `rom-battle-sound-selector-v1` | artifact | rom | `build` | — | 6 |
| `rom-boot-copy-sources-v1` | artifact | rom | `build` | — | 3 |
| `rom-bounded-index-u16-pair-table-v1` | artifact | rom | `build` | — | 3 |
| `rom-cfg-proven-roots-v14` | artifact | rom | `build` | — | 4 |
| `rom-chapter-script-inventory-v1` | artifact | rom | `build` | — | 5 |
| `rom-cutscene-obj-source-ranges-v1` | artifact | rom | `build` | — | 4 |
| `rom-dialogue-text-inventory-v1` | artifact | rom | `build` | — | 5 |
| `rom-direct-cpuset-gpu-inventory-v1` | artifact | rom | `build` | — | 3 |
| `rom-direct-dma-gpu-inventory-v1` | artifact | rom | `build` | — | 2 |
| `rom-directsound-pitch-lookup-v1` | artifact | rom | `build` | — | 8 |
| `rom-display-text-delta-v1` | artifact | rom | `build` | — | 6 |
| `rom-expansion-profile-v1` | artifact | rom | `build` | — | 3 |
| `rom-fixed-animation-descriptor-groups-v1` | artifact | rom | `build` | — | 4 |
| `rom-fixed-consumer-text-inventory-v1` | artifact | rom | `build` | — | 7 |
| `rom-fixed-index-u8-tail-v1` | artifact | rom | `build` | — | 4 |
| `rom-fixed-pair-tables-v1` | artifact | rom | `build` | — | 3 |
| `rom-fixed-renderer-script-records-v1` | artifact | rom | `build` | — | 8 |
| `rom-gpu-copy-queue-inventory-20260730` | note | rom | `build` | — | 3 |
| `rom-gpu-copy-queue-inventory-v1` | artifact | rom | `build` | — | 3 |
| `rom-low-script-delta-v1` | artifact | rom | `build` | — | 3 |
| `rom-menu-portrait-palette-inventory-v1` | artifact | rom | `build` | — | 6 |
| `rom-pointer-lz77-graphics-v1` | artifact | rom | `build` | — | 6 |
| `rom-pointer-lz77-inventory-v1` | artifact | rom | `build` | — | 12 |
| `rom-psg-frequency-lookup-v1` | artifact | rom | `build` | — | 8 |
| `rom-renderer-records-delta-v1` | artifact | rom | `build` | — | 4 |
| `rom-renderer-script-pointer-pool-records-v1` | artifact | rom | `build` | — | 4 |
| `rom-renderer-text-inventory-v1` | artifact | rom | `build` | — | 5 |
| `rom-selector-direct-source-records-v1` | artifact | rom | `build` | — | 3 |
| `rom-staged-gpu-copy-inventory-v1` | artifact | rom | `build` | — | 2 |
| `rom-u8-indexed-u16-pair-lookup-v1` | artifact | rom | `build` | — | 5 |
| `rom-u8-indexed-u8-triplet-lookup-v1` | artifact | rom | `build` | — | 6 |
| `run_cpp_benchmark_tests` | tool | code | `build` | — | 19 |
| `run_guarded` | tool | code | `build` | — | 289 |
| `run_macos_mgba_replay` | tool | code | `build` | — | 12 |
| `run_macos_mgba_single_input` | tool | code | `build` | — | 8 |
| `run_offline_e2e` | tool | code | `build` | — | 5 |
| `runtime-bg-composites-v1` | artifact | runtime | `build` | — | 4 |
| `runtime-checkpoints` | artifact | runtime | `build` | reused | 132 |
| `runtime-font-tile-provenance-v1` | artifact | runtime | `build` | — | 2 |
| `runtime-layer-static-provenance-v1` | artifact | runtime | `build` | — | 2 |
| `runtime-screen-composites-v1` | artifact | runtime | `build` | — | 4 |
| `runtime-verification-gates-20260710` | note | runtime | `build` | — | 29 |
| `runtime_checkpoint_ledger` | tool | code | `build` | — | 7 |
| `sappy-engine-master-enable-ab-v1` | artifact | other | `build` | — | 6 |
| `scan_rom` | tool | code | `build` | — | 3 |
| `scenario-41-audio-reference-v1` | artifact | scenario | `build` | — | 7 |
| `scenario-41-combat-reference-v1` | artifact | scenario | `build` | — | 5 |
| `scenario-41-extended-reference-v1` | artifact | scenario | `build` | — | 3 |
| `scenario-41-prebattle-reference-v1` | artifact | scenario | `build` | — | 8 |
| `scenario-41-reference-v1` | artifact | scenario | `build` | — | 7 |
| `scenario-45-safe-resume-20260719` | note | scenario | `build` | — | 5 |
| `scenario-49-battle-14-runtime-20260720` | note | scenario | `build` | — | 12 |
| `scenario-50-battle-15-runtime-20260720` | note | scenario | `build` | — | 3 |
| `scene-visual-composites-v1` | artifact | map | `build` | — | 5 |
| `scene-visual-packs-v1` | artifact | map | `build` | — | 7 |
| `scene-visual-transition-timelines-v1` | artifact | map | `build` | — | 3 |
| `sh_const` | tool | code | `build` | — | 2 |
| `similar-tables` | note | other | `build` | — | 5 |
| `sparc_const` | tool | code | `build` | — | 2 |
| `sprite-definition-animations-v1` | artifact | visual | `build` | — | 6 |
| `sprite-definition-assets-v2` | artifact | visual | `build` | — | 10 |
| `story-scene-layer-bindings-v1` | artifact | presentation | `build` | — | 9 |
| `story-scene-timelines-v1` | artifact | presentation | `build` | — | 8 |
| `story-visual-layers-v1` | artifact | presentation | `build` | — | 11 |
| `story-visual-resource-relocation-v1` | artifact | presentation | `build` | — | 2 |
| `story-visual-resource-sources-v1` | artifact | presentation | `build` | — | 2 |
| `summarize_watch_hits` | tool | code | `build` | — | 2 |
| `sysz_const` | tool | code | `build` | — | 2 |
| `test_export_rom_battle_controller_cfg` | test | code | `build` | — | 4 |
| `test_extract_tileset` | test | code | `build` | — | 5 |
| `thumb_branch` | tool | code | `build` | — | 55 |
| `tile-asset-descriptor2-pixel-ab-v1` | artifact | visual | `build` | — | 3 |
| `tile-asset-resource-relocation-v1` | artifact | visual | `build` | — | 2 |
| `tile-assets-bg-v1` | artifact | visual | `build` | — | 8 |
| `tile-assets-bg-v2` | artifact | visual | `build` | — | 18 |
| `tms320c64x` | tool | code | `build` | — | 4 |
| `tms320c64x_const` | tool | code | `build` | — | 2 |
| `translate_sjis_to_chinese` | tool | code | `build` | — | 4 |
| `tricore_const` | tool | code | `build` | — | 2 |
| `u32-pointer-real-writeback-20260710` | note | other | `build` | — | 4 |
| `units-unsafe-table-fix-20260711` | note | other | `build` | — | 7 |
| `verify_battle_config_records` | tool | code | `build` | — | 4 |
| `verify_battle_effect_affine_runtime` | tool | code | `build` | — | 3 |
| `verify_battle_effect_resource_pairs` | tool | code | `build` | — | 3 |
| `verify_battle_effect_sequence_bindings` | tool | code | `build` | — | 4 |
| `verify_battle_effect_sprite_animations` | tool | code | `build` | — | 4 |
| `verify_battle_presentation_glyphs` | tool | code | `build` | — | 5 |
| `verify_battle_visual_catalog` | tool | code | `build` | — | 3 |
| `verify_battle_visual_runtime_timelines` | tool | code | `build` | — | 4 |
| `verify_bg_resource_canvases` | tool | code | `build` | — | 4 |
| `verify_bg_scene_selection` | tool | code | `build` | — | 3 |
| `verify_character_battle_visuals` | tool | code | `build` | — | 5 |
| `verify_character_fbff_runtime` | tool | code | `build` | — | 3 |
| `verify_character_stats_records` | tool | code | `build` | — | 4 |
| `verify_cutscene_obj_export` | tool | code | `build` | — | 4 |
| `verify_dialogue_font_atlases` | tool | code | `build` | — | 4 |
| `verify_map_canvases` | tool | code | `build` | — | 4 |
| `verify_map_resource_buffers` | tool | code | `build` | — | 3 |
| `verify_save_state_records` | tool | code | `build` | — | 5 |
| `verify_scenario_41_audio_states` | tool | code | `build` | — | 2 |
| `verify_scene_visual_packs` | tool | code | `build` | — | 3 |
| `verify_setup` | tool | code | `build` | — | 7 |
| `verify_sprite_definition_animations` | tool | code | `build` | — | 3 |
| `verify_sprite_definition_runtime_chain` | tool | code | `build` | — | 4 |
| `verify_story_scene_layer_bindings` | tool | code | `build` | — | 3 |
| `verify_story_scene_timelines` | tool | code | `build` | — | 4 |
| `verify_story_visual_layer_export` | tool | code | `build` | — | 3 |
| `verify_tile_asset_bg_export` | tool | code | `build` | — | 4 |
| `verify_world_map_backgrounds` | tool | code | `build` | — | 3 |
| `verify_world_map_runtime` | tool | code | `build` | — | 4 |
| `wasm-formation-probe-result-20260710` | note | other | `build` | — | 10 |
| `wasm_const` | tool | code | `build` | — | 2 |
| `world-map-background-relocation-v1` | artifact | map | `build` | — | 2 |
| `world-map-backgrounds-v1` | artifact | map | `build` | — | 8 |
| `world-map-gpu-captures` | artifact | map | `build` | — | 6 |
| `world-map-page0-pixel-ab-v1` | artifact | map | `build` | — | 2 |
| `world-map-runtime-v1` | artifact | map | `build` | — | 5 |
| `x86_const` | tool | code | `build` | — | 2 |
| `xcore_const` | tool | code | `build` | — | 2 |
| `alternate-chapter-runtime-probe-20260712` | note | other | `local_artifact` | — | 4 |
| `audio-cue-semantics-20260713` | note | audio | `local_artifact` | — | 5 |
| `audio-engine-runtime-chain-20260712` | note | audio | `local_artifact` | — | 6 |
| `audio-palette-identity-correction-20260711` | note | audio | `local_artifact` | — | 4 |
| `battle-action-detail-renderer-20260713` | note | battle | `local_artifact` | — | 7 |
| `battle-effect-resource-pairs-export-20260729` | note | visual | `local_artifact` | — | 4 |
| `battle-effect-sequence-bindings-export-20260729` | note | visual | `local_artifact` | — | 3 |
| `battle-effect-sprite-animations-export-20260729` | note | visual | `local_artifact` | — | 5 |
| `battle-effect-template-consumer-20260711` | note | visual | `local_artifact` | — | 4 |
| `battle-presentation-glyphs-export-20260729` | note | battle | `local_artifact` | — | 8 |
| `battle-scenario-config` | note | battle | `local_artifact` | — | 10 |
| `battle-start-control-flow-20260713` | note | battle | `local_artifact` | — | 9 |
| `battle-visual-catalog-export-20260729` | note | visual | `local_artifact` | — | 7 |
| `battle-visual-runtime-timelines-export-20260729` | note | visual | `local_artifact` | — | 7 |
| `bg-resource-canvases-export-20260729` | note | visual | `local_artifact` | — | 4 |
| `bg-scene-selection-export-20260729` | note | visual | `local_artifact` | — | 6 |
| `butano-scenario-41-one-to-one-runtime-20260722` | note | other | `local_artifact` | — | 8 |
| `chapter-entry-points` | note | other | `local_artifact` | — | 4 |
| `chapter-flow-format` | note | other | `local_artifact` | — | 8 |
| `chapter-flow-runtime-chain-20260712` | note | other | `local_artifact` | — | 6 |
| `chapter-script-observed-subset-20260713` | note | other | `local_artifact` | — | 3 |
| `chapter-script-production-writeback-20260713` | note | other | `local_artifact` | — | 3 |
| `character-battle-visuals-export-20260729` | note | visual | `local_artifact` | — | 10 |
| `character-growth-runtime-chain-20260711` | note | visual | `local_artifact` | — | 11 |
| `codex-reentry-audit-20260712` | note | other | `local_artifact` | — | 3 |
| `current-re-progress-20260711` | note | other | `local_artifact` | — | 5 |
| `cutscene-obj-export-20260729` | note | presentation | `local_artifact` | — | 3 |
| `cutscene-visual-resource-consumer-20260712` | note | presentation | `local_artifact` | — | 5 |
| `debugging-record` | note | other | `local_artifact` | — | 3 |
| `dialogue-caller-runtime` | note | other | `local_artifact` | — | 7 |
| `dialogue-font-atlas-export-20260729` | note | other | `local_artifact` | — | 3 |
| `dialogue-font-table-discovery-20260703` | note | other | `local_artifact` | — | 2 |
| `dialogue-function-analysis` | note | other | `local_artifact` | — | 6 |
| `dialogue-mapping-blocker-20260702` | note | other | `local_artifact` | — | 4 |
| `dialogue-mapping-decoder-20260702` | note | other | `local_artifact` | — | 3 |
| `dialogue-mapping-progress-20260702` | note | other | `local_artifact` | — | 3 |
| `dialogue-memory-analysis` | note | other | `local_artifact` | — | 4 |
| `dialogue-ram-structures` | note | other | `local_artifact` | — | 4 |
| `dialogue-write-path` | note | other | `local_artifact` | — | 5 |
| `dialogue-writer-addresses` | note | other | `local_artifact` | — | 4 |
| `diff-dialogue-2160-2340-vram` | note | other | `local_artifact` | — | 3 |
| `diff-dialogue-2160-2340-wram` | note | other | `local_artifact` | — | 3 |
| `diff-dialogue-2340-2520-vram` | note | other | `local_artifact` | — | 3 |
| `diff-dialogue-2340-2520-wram` | note | other | `local_artifact` | — | 3 |
| `directsound-envelope-20260713` | note | other | `local_artifact` | — | 5 |
| `directsound-mixer-runtime-chain-20260713` | note | other | `local_artifact` | — | 6 |
| `directsound-pitch-step-20260713` | note | other | `local_artifact` | — | 5 |
| `directsound-volume-pan-20260713` | note | other | `local_artifact` | — | 5 |
| `dynamic-verification-audit` | note | other | `local_artifact` | — | 11 |
| `editor-isolated-writeback-smoke-20260713` | note | other | `local_artifact` | — | 4 |
| `first-battle-savestate-checkpoints-20260712` | note | other | `local_artifact` | — | 8 |
| `function-pointer-runtime-probe-20260713` | note | other | `local_artifact` | — | 3 |
| `headless-workflow` | note | other | `local_artifact` | — | 4 |
| `levels-runtime-probe-20260713` | note | other | `local_artifact` | — | 8 |
| `m4a-channel-allocation-20260713` | note | other | `local_artifact` | — | 3 |
| `m4a-emulator-differential-20260713` | note | other | `local_artifact` | — | 5 |
| `m4a-full-song-render-20260713` | note | other | `local_artifact` | — | 5 |
| `m4a-player-slot-control-flow-20260713` | note | other | `local_artifact` | — | 3 |
| `m4a-player-slot-runtime-differential-20260713` | note | other | `local_artifact` | — | 8 |
| `m4a-runtime-channel-wiring-20260713` | note | other | `local_artifact` | — | 4 |
| `m4a-soundmain-scheduler-20260713` | note | other | `local_artifact` | — | 6 |
| `map-addresses` | note | map | `local_artifact` | — | 5 |
| `map-canvases-export-20260729` | note | map | `local_artifact` | — | 3 |
| `map-format` | note | map | `local_artifact` | — | 9 |
| `map-position-pc-probe-20260710` | note | map | `local_artifact` | — | 3 |
| `maps-runtime-fields-20260711` | note | map | `local_artifact` | — | 7 |
| `memory-incident-root-cause-20260714` | note | other | `local_artifact` | — | 4 |
| `menu-portrait-export-20260729` | note | presentation | `local_artifact` | — | 4 |
| `natural-skill-detail-runtime-20260713` | note | other | `local_artifact` | — | 5 |
| `offline-e2e-smoke-20260713` | note | other | `local_artifact` | — | 2 |
| `overlapping-visual-tables-audit-20260712` | note | other | `local_artifact` | — | 3 |
| `partial-item-inventory` | note | other | `local_artifact` | — | 5 |
| `partial-random-encounter` | note | other | `local_artifact` | — | 5 |
| `patch-generator-audit` | note | other | `local_artifact` | — | 7 |
| `profile-text-runtime-probe-20260713` | note | other | `local_artifact` | — | 3 |
| `psg-noise-runtime-chain-20260713` | note | other | `local_artifact` | — | 5 |
| `resource-table-596F98` | note | other | `local_artifact` | — | 2 |
| `runtime-handler-pair-consumer-20260712` | note | runtime | `local_artifact` | — | 3 |
| `runtime-state-entry-audit-20260710` | note | runtime | `local_artifact` | — | 4 |
| `save-descriptor-layout-correction-20260712` | note | other | `local_artifact` | — | 4 |
| `save-state-wasm-probe-20260711` | note | other | `local_artifact` | — | 4 |
| `scan-summary` | note | other | `local_artifact` | — | 2 |
| `scenario-41-battle-entry-runtime-20260713` | note | scenario | `local_artifact` | — | 6 |
| `scenario-41-completion-runtime-20260718` | note | scenario | `local_artifact` | — | 7 |
| `scenario-41-controller-path-runtime-20260715` | note | scenario | `local_artifact` | — | 4 |
| `scenario-41-movedone-runtime-20260717` | note | scenario | `local_artifact` | — | 8 |
| `scenario-41-player-control-runtime-20260715` | note | scenario | `local_artifact` | — | 6 |
| `scenario-41-prebattle-menu-macos-20260715` | note | scenario | `local_artifact` | — | 3 |
| `scenario-41-prebattle-to-controller-macos-20260715` | note | scenario | `local_artifact` | — | 3 |
| `scenario-41-savestate-context-reanalysis-20260715` | note | scenario | `local_artifact` | — | 4 |
| `scenario-42-progression-runtime-20260718` | note | scenario | `local_artifact` | — | 4 |
| `scenario-43-progression-runtime-20260718` | note | scenario | `local_artifact` | — | 4 |
| `scenario-44-progression-runtime-20260718` | note | scenario | `local_artifact` | — | 6 |
| `scenario-46-entry-runtime-20260719` | note | scenario | `local_artifact` | — | 4 |
| `scenario-47-entry-runtime-20260720` | note | scenario | `local_artifact` | — | 3 |
| `scene-visual-pack-export-20260729` | note | map | `local_artifact` | — | 4 |
| `skill-template-consumer-semantics-20260713` | note | other | `local_artifact` | — | 3 |
| `skill-template-identity-20260711` | note | other | `local_artifact` | — | 3 |
| `skill-template-ui-probe-20260712` | note | other | `local_artifact` | — | 3 |
| `sprite-definition-animations-export-20260729` | note | visual | `local_artifact` | — | 5 |
| `sprite-definition-runtime-chain-20260729` | note | visual | `local_artifact` | — | 6 |
| `static-bank-identity-corrections-20260713` | note | other | `local_artifact` | — | 3 |
| `story-bank-identity-correction-20260712` | note | presentation | `local_artifact` | — | 3 |
| `story-scene-layer-bindings-20260729` | note | presentation | `local_artifact` | — | 4 |
| `story-scene-timelines-export-20260729` | note | presentation | `local_artifact` | — | 5 |
| `story-visual-descriptor-consumer-20260712` | note | presentation | `local_artifact` | — | 3 |
| `story-visual-layer-export-20260729` | note | presentation | `local_artifact` | — | 3 |
| `strict-battle-arrival-gate-20260712` | note | other | `local_artifact` | — | 3 |
| `text-and-battle-visual-consumers-20260713` | note | other | `local_artifact` | — | 6 |
| `text-regions` | note | other | `local_artifact` | — | 5 |
| `tile-assets-bg-export-20260729` | note | visual | `local_artifact` | — | 3 |
| `tileset-extraction-correction-20260712` | note | visual | `local_artifact` | — | 3 |
| `tutorial-victory-save-load-runtime-20260712` | note | other | `local_artifact` | — | 7 |
| `unit-id-mapping-analysis` | note | other | `local_artifact` | — | 4 |
| `unit-skill-addresses` | note | other | `local_artifact` | — | 8 |
| `unknown-bgm-sfx` | note | other | `local_artifact` | — | 7 |
| `unknown-item-inventory` | note | other | `local_artifact` | — | 4 |
| `unknown-random-encounter` | note | other | `local_artifact` | — | 4 |
| `unknown-save-state` | note | other | `local_artifact` | — | 5 |
| `variable-dialogue-relocation-20260712` | note | other | `local_artifact` | — | 2 |
| `wasm-formation-navigation-probe-20260710` | note | other | `local_artifact` | — | 3 |
| `wasm-runtime-api-audit-20260710` | note | other | `local_artifact` | — | 3 |
| `world-map-background-export-20260729` | note | map | `local_artifact` | — | 4 |
| `world-map-runtime-composition-20260729` | note | map | `local_artifact` | — | 4 |
| `writeback-experiment-00076D` | note | other | `local_artifact` | — | 2 |
| `2026-07-22-butano-battle-system-architecture-design` | doc | other | `test` | — | 22 |
| `2026-07-22-butano-battle-system-implementation` | doc | other | `test` | — | 3 |
| `audio` | artifact | audio | `test` | — | 16 |
| `battle-status-bars-export-20260730` | note | battle | `test` | — | 4 |
| `butano-battle-domain-rewrite-20260723` | note | other | `test` | — | 20 |
| `butano-konoha-systems-cost` | doc | other | `test` | — | 9 |
| `butano-local-reference` | doc | other | `test` | — | 6 |
| `butano-scenario-41-battle` | doc | other | `test` | — | 7 |
| `butano-scenario-41-runtime-20260721` | note | other | `test` | — | 5 |
| `character-battle-visual-resource-matrix-20260801` | note | visual | `test` | — | 3 |
| `rom-cfg-inventory-v3` | artifact | rom | `test` | — | 4 |
| `scenario-41-attack-animation-v1` | artifact | scenario | `test` | — | 2 |
| `sequel-roadmap` | doc | other | `test` | — | 78 |
| `sequel-roadmap` | note | other | `test` | — | 78 |
| `sequel-roadmap` | note | other | `test` | — | 78 |
| `sequel-roadmap` | note | other | `test` | — | 78 |
| `sequel-roadmap` | note | other | `test` | — | 78 |
| `sequel-roadmap` | note | other | `test` | — | 78 |
| `sequel-roadmap` | note | other | `test` | — | 78 |
| `test_accept_prebattle_candidate` | test | code | `test` | — | 2 |
| `test_analyze_battle_action_template_semantics` | test | code | `test` | — | 1 |
| `test_analyze_battle_action_transactions` | test | code | `test` | — | 1 |
| `test_analyze_battle_ai_status_policy` | test | code | `test` | — | 1 |
| `test_analyze_battle_ai_utility_policy` | test | code | `test` | — | 1 |
| `test_analyze_battle_condition_interpreter` | test | code | `test` | — | 1 |
| `test_analyze_battle_controller_checkpoints` | test | code | `test` | — | 2 |
| `test_analyze_battle_damage_hit_formula` | test | code | `test` | — | 1 |
| `test_analyze_battle_defense_preparation` | test | code | `test` | — | 1 |
| `test_analyze_battle_defense_reaction` | test | code | `test` | — | 1 |
| `test_analyze_battle_effect_resolution` | test | code | `test` | — | 1 |
| `test_analyze_battle_hit_modifiers` | test | code | `test` | — | 1 |
| `test_analyze_battle_objective_transitions` | test | code | `test` | — | 1 |
| `test_analyze_battle_reaction_matrix` | test | code | `test` | — | 1 |
| `test_analyze_battle_reaction_priority` | test | code | `test` | — | 1 |
| `test_analyze_battle_resource_transactions` | test | code | `test` | — | 1 |
| `test_analyze_battle_status_attribute_modifiers` | test | code | `test` | — | 1 |
| `test_analyze_battle_status_consumers` | test | code | `test` | — | 1 |
| `test_analyze_battle_status_expiry` | test | code | `test` | — | 1 |
| `test_analyze_battle_status_hit_count_modifier` | test | code | `test` | — | 1 |
| `test_analyze_battle_status_linked_resolution` | test | code | `test` | — | 1 |
| `test_analyze_battle_status_participant_consumption` | test | code | `test` | — | 1 |
| `test_analyze_battle_status_stage_policy` | test | code | `test` | — | 1 |
| `test_analyze_battle_status_storage` | test | code | `test` | — | 1 |
| `test_analyze_battle_status_transformation` | test | code | `test` | — | 1 |
| `test_analyze_battle_unit_eligibility` | test | code | `test` | — | 1 |
| `test_analyze_battle_unit_selection` | test | code | `test` | — | 1 |
| `test_analyze_mgba_zero_input_cycle` | test | code | `test` | — | 2 |
| `test_audio_sound_id_writeback` | test | code | `test` | — | 2 |
| `test_automated_test_output_isolation` | test | code | `test` | — | 2 |
| `test_battle_encounter_identity` | test | code | `test` | — | 3 |
| `test_battle_handler_identity` | test | code | `test` | — | 3 |
| `test_build_action_submit_runtime_probe` | test | code | `test` | — | 2 |
| `test_build_adjacent_tutorial_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_alternate_chapter_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_audio_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_battle_catalog_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_battle_effect_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_battle_message_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_battle_start_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_chapter_script_probe` | test | code | `test` | — | 1 |
| `test_build_chapter_semantic_probe` | test | code | `test` | — | 1 |
| `test_build_character_fbff_control_rom` | test | code | `test` | — | 2 |
| `test_build_character_growth_probe` | test | code | `test` | — | 2 |
| `test_build_controlled_audio_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_controller_path_runtime_probe` | test | code | `test` | — | 2 |
| `test_build_cross_player_cgb_probe` | test | code | `test` | — | 1 |
| `test_build_delayed_audio_retrigger_probe` | test | code | `test` | — | 1 |
| `test_build_forced_save_case_probe` | test | code | `test` | — | 1 |
| `test_build_function_pointer_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_levels_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_macos_mgba` | test | code | `test` | — | 2 |
| `test_build_natural_load_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_natural_save_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_numeric_writer_trace_probe` | test | code | `test` | — | 4 |
| `test_build_player_control_runtime_probe` | test | code | `test` | — | 3 |
| `test_build_postbattle_natural_save_probe` | test | code | `test` | — | 1 |
| `test_build_postbattle_save_probe` | test | code | `test` | — | 1 |
| `test_build_profile_text_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_relocated_chapter_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_resource_pointer_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_save_group_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_save_state_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_skill_detail_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_skill_relation_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_skill_runtime_probe` | test | code | `test` | — | 1 |
| `test_build_text_writer_trace_probe` | test | code | `test` | — | 3 |
| `test_build_tilemap_writer_trace_probe` | test | code | `test` | — | 4 |
| `test_build_training_levels_runtime_probe` | test | code | `test` | — | 1 |
| `test_butano_benchmark_harness` | test | code | `test` | — | 3 |
| `test_butano_build` | test | code | `test` | — | 20 |
| `test_butano_mgba_audio_recorder` | test | code | `test` | — | 1 |
| `test_butano_research_docs` | test | code | `test` | — | 8 |
| `test_butano_scenario_41_assets` | test | code | `test` | — | 5 |
| `test_butano_scenario_41_attack_animation` | test | code | `test` | — | 1 |
| `test_butano_scenario_41_attack_assets` | test | code | `test` | — | 1 |
| `test_butano_scenario_41_attack_gpu_bases` | test | code | `test` | — | 1 |
| `test_butano_scenario_41_audio` | test | code | `test` | — | 3 |
| `test_butano_scenario_41_combat_reference` | test | code | `test` | — | 1 |
| `test_butano_scenario_41_extended_reference` | test | code | `test` | — | 1 |
| `test_butano_scenario_41_gpu` | test | code | `test` | — | 3 |
| `test_butano_scenario_41_prebattle_assets` | test | code | `test` | — | 1 |
| `test_butano_scenario_41_prebattle_reference` | test | code | `test` | — | 1 |
| `test_butano_scenario_41_reference` | test | code | `test` | — | 2 |
| `test_butano_scenario_41_render` | test | code | `test` | — | 2 |
| `test_butano_scenario_41_runtime_script` | test | code | `test` | — | 3 |
| `test_butano_setup` | test | code | `test` | — | 3 |
| `test_chapter_flow_writeback` | test | code | `test` | — | 1 |
| `test_chapter_script_analyzer` | test | code | `test` | — | 1 |
| `test_chapter_script_codec` | test | code | `test` | — | 1 |
| `test_character_definition_writeback` | test | code | `test` | — | 3 |
| `test_character_overview_field_semantics` | test | code | `test` | — | 1 |
| `test_check_comet_project_policy` | test | code | `test` | — | 5 |
| `test_compare_mgba_audio_capture` | test | code | `test` | — | 1 |
| `test_compare_mgba_cgb_capture` | test | code | `test` | — | 1 |
| `test_compare_mgba_cross_player_cgb_capture` | test | code | `test` | — | 1 |
| `test_compare_mgba_linked_audio_capture` | test | code | `test` | — | 1 |
| `test_compare_mgba_retrigger_capture` | test | code | `test` | — | 1 |
| `test_cutscene_visual_resources` | test | code | `test` | — | 1 |
| `test_decode_controller_path_runtime_probe` | test | code | `test` | — | 2 |
| `test_decode_dialogue_record` | test | code | `test` | — | 3 |
| `test_decode_m4a_tracks` | test | code | `test` | — | 1 |
| `test_disasm_thumb` | test | code | `test` | — | 2 |
| `test_editor_build_integration` | test | code | `test` | — | 4 |
| `test_encounter_zone_identity` | test | code | `test` | — | 1 |
| `test_export_battle_effect_affine_runtime` | test | code | `test` | — | 2 |
| `test_export_battle_effect_resource_pairs` | test | code | `test` | — | 2 |
| `test_export_battle_effect_sequence_bindings` | test | code | `test` | — | 2 |
| `test_export_battle_effect_sprite_animations` | test | code | `test` | — | 2 |
| `test_export_battle_presentation_glyphs` | test | code | `test` | — | 3 |
| `test_export_battle_visual_catalog` | test | code | `test` | — | 2 |
| `test_export_battle_visual_runtime_timelines` | test | code | `test` | — | 2 |
| `test_export_bg_resource_canvases` | test | code | `test` | — | 2 |
| `test_export_bg_scene_selection` | test | code | `test` | — | 2 |
| `test_export_character_battle_visuals` | test | code | `test` | — | 3 |
| `test_export_cutscene_obj_assets` | test | code | `test` | — | 2 |
| `test_export_dialogue_font_atlases` | test | code | `test` | — | 2 |
| `test_export_map_canvases` | test | code | `test` | — | 2 |
| `test_export_menu_portraits` | test | code | `test` | — | 3 |
| `test_export_scene_visual_packs` | test | code | `test` | — | 3 |
| `test_export_sprite_definition_animations` | test | code | `test` | — | 2 |
| `test_export_sprite_definition_runtime_chain` | test | code | `test` | — | 3 |
| `test_export_story_scene_layer_bindings` | test | code | `test` | — | 4 |
| `test_export_story_scene_timelines` | test | code | `test` | — | 3 |
| `test_export_story_visual_layers` | test | code | `test` | — | 4 |
| `test_export_tile_asset_bg_layers` | test | code | `test` | — | 6 |
| `test_export_world_map_backgrounds` | test | code | `test` | — | 2 |
| `test_export_world_map_runtime` | test | code | `test` | — | 3 |
| `test_extract_audio_assets` | test | code | `test` | — | 1 |
| `test_extract_audio_command_table` | test | code | `test` | — | 1 |
| `test_extract_audio_cue_calls` | test | code | `test` | — | 4 |
| `test_extract_audio_engine` | test | code | `test` | — | 1 |
| `test_extract_audio_resource_sets` | test | code | `test` | — | 1 |
| `test_extract_battle_ai_planner` | test | code | `test` | — | 1 |
| `test_extract_battle_content_catalog` | test | code | `test` | — | 1 |
| `test_extract_battle_controller_states` | test | code | `test` | — | 2 |
| `test_extract_battle_effect_templates` | test | code | `test` | — | 1 |
| `test_extract_chapter_flow_tables` | test | code | `test` | — | 1 |
| `test_extract_character_definitions` | test | code | `test` | — | 3 |
| `test_extract_character_growth` | test | code | `test` | — | 2 |
| `test_extract_graphics_resource_sets` | test | code | `test` | — | 1 |
| `test_extract_positions` | test | code | `test` | — | 3 |
| `test_extract_save_descriptors` | test | code | `test` | — | 1 |
| `test_extract_skill_templates` | test | code | `test` | — | 2 |
| `test_find_pointer_refs` | test | code | `test` | — | 1 |
| `test_find_thumb_calls` | test | code | `test` | — | 3 |
| `test_function_pointer_consumer` | test | code | `test` | — | 2 |
| `test_gba_image_export` | test | code | `test` | — | 3 |
| `test_generate_butano_battle_action_content` | test | code | `test` | — | 2 |
| `test_generate_butano_battle_runtime_assets` | test | code | `test` | — | 5 |
| `test_generate_butano_battle_unit_content` | test | code | `test` | — | 2 |
| `test_import_chapter_scripts` | test | code | `test` | — | 1 |
| `test_import_dialogue_var` | test | code | `test` | — | 4 |
| `test_inspect_mgba_savestate` | test | code | `test` | — | 4 |
| `test_isolated_build_paths` | test | code | `test` | — | 1 |
| `test_m4a_channels` | test | code | `test` | — | 1 |
| `test_m4a_command_vm` | test | code | `test` | — | 1 |
| `test_m4a_envelope` | test | code | `test` | — | 1 |
| `test_m4a_pcm` | test | code | `test` | — | 2 |
| `test_m4a_pitch_step` | test | code | `test` | — | 1 |
| `test_m4a_psg` | test | code | `test` | — | 1 |
| `test_m4a_runtime_channels` | test | code | `test` | — | 1 |
| `test_m4a_scheduler` | test | code | `test` | — | 1 |
| `test_m4a_song_engine` | test | code | `test` | — | 1 |
| `test_m4a_track_state` | test | code | `test` | — | 1 |
| `test_macos_mgba_runtime_residue` | test | code | `test` | — | 2 |
| `test_map_event_identity` | test | code | `test` | — | 1 |
| `test_map_header_writeback` | test | code | `test` | — | 2 |
| `test_map_m4a_instruments` | test | code | `test` | — | 1 |
| `test_mgba_affine_mirror_probe_script` | test | code | `test` | — | 1 |
| `test_mgba_character_fbff_probe_script` | test | code | `test` | — | 2 |
| `test_mgba_gdb_probe` | test | code | `test` | — | 4 |
| `test_mgba_headless_probe` | test | code | `test` | — | 2 |
| `test_mgba_runtime_safety` | test | code | `test` | — | 2 |
| `test_ocr_screenshot` | test | code | `test` | — | 1 |
| `test_overlapping_visual_table_identity` | test | code | `test` | — | 2 |
| `test_patch_mgba_savestate_memory` | test | code | `test` | — | 1 |
| `test_patch_safety` | test | code | `test` | — | 1 |
| `test_populate_units_bank` | test | code | `test` | — | 2 |
| `test_positions_integration` | test | code | `test` | — | 5 |
| `test_project_resource_guard` | test | code | `test` | — | 6 |
| `test_published_call_observer` | test | code | `test` | — | 4 |
| `test_re_completion_audit` | test | code | `test` | — | 1 |
| `test_remaining_static_identity` | test | code | `test` | — | 2 |
| `test_render_m4a_midi` | test | code | `test` | — | 2 |
| `test_render_m4a_pcm_bank` | test | code | `test` | — | 1 |
| `test_run_guarded` | test | code | `test` | — | 6 |
| `test_run_macos_mgba_replay` | test | code | `test` | — | 3 |
| `test_run_macos_mgba_single_input` | test | code | `test` | — | 3 |
| `test_run_offline_e2e` | test | code | `test` | — | 1 |
| `test_runtime_checkpoint_ledger` | test | code | `test` | — | 4 |
| `test_scenario41_completion_persistence` | test | code | `test` | — | 2 |
| `test_scenario41_controller_checkpoint_persistence` | test | code | `test` | — | 1 |
| `test_scenario41_first_movedone_facing_persistence` | test | code | `test` | — | 1 |
| `test_scenario41_first_turn_technique_menu_persistence` | test | code | `test` | — | 1 |
| `test_scenario41_turn1_complete_persistence` | test | code | `test` | — | 2 |
| `test_scenario42_progression_persistence` | test | code | `test` | — | 1 |
| `test_scenario43_progression_persistence` | test | code | `test` | — | 1 |
| `test_scenario44_progression_persistence` | test | code | `test` | — | 1 |
| `test_skill_relationship_semantics` | test | code | `test` | — | 1 |
| `test_text_and_visual_table_identity` | test | code | `test` | — | 5 |
| `test_thumb_branch` | test | code | `test` | — | 3 |
| `test_u32_pointer_patches` | test | code | `test` | — | 9 |
| `test_unsafe_legacy_patches` | test | code | `test` | — | 4 |
| `test_unsafe_unit_patch` | test | code | `test` | — | 3 |
| `test_verify_battle_config_records` | test | code | `test` | — | 1 |
| `test_verify_character_fbff_runtime` | test | code | `test` | — | 2 |
| `test_verify_character_stats_records` | test | code | `test` | — | 1 |
| `test_verify_map_resource_buffers` | test | code | `test` | — | 1 |
| `test_verify_save_state_records` | test | code | `test` | — | 1 |
| `2026-07-14-reverse-engineering-resource-safety` | doc | other | `doc` | — | 1 |
| `2026-07-14-reverse-engineering-resource-safety-design` | doc | other | `doc` | — | 1 |
| `2026-07-15-scenario-41-battle-runtime` | doc | other | `doc` | — | 3 |
| `2026-07-15-scenario-41-battle-runtime-design` | doc | other | `doc` | — | 4 |
| `2026-07-15-scenario-41-controller-path-probe` | doc | other | `doc` | — | 1 |
| `2026-07-15-scenario-41-controller-path-probe-design` | doc | other | `doc` | — | 1 |
| `2026-07-15-scenario-41-lineup-to-controller` | doc | other | `doc` | — | 1 |
| `2026-07-15-scenario-41-prebattle-to-controller-design` | doc | other | `doc` | — | 2 |
| `2026-07-16-project-completion-policy-alignment` | doc | other | `doc` | — | 1 |
| `2026-07-16-project-completion-policy-alignment-design` | doc | other | `doc` | — | 2 |
| `2026-07-16-project-policy-audit-repair` | doc | other | `doc` | — | 2 |
| `2026-07-16-scenario-41-animated-snapshot-stability-design` | doc | other | `doc` | — | 3 |
| `2026-07-17-macos-mgba-gdb-ownership` | doc | other | `doc` | — | 2 |
| `2026-07-17-macos-mgba-gdb-ownership-design` | doc | other | `doc` | — | 1 |
| `2026-07-17-mgba-safe-script-termination` | doc | other | `doc` | — | 1 |
| `2026-07-17-mgba-safe-script-termination-design` | doc | other | `doc` | — | 1 |
| `2026-07-17-scenario-41-active-current-unit-observer` | doc | other | `doc` | — | 1 |
| `2026-07-17-scenario-41-active-current-unit-observer-design` | doc | other | `doc` | — | 2 |
| `2026-07-18-direct-reverse-engineering-critical-path` | doc | other | `doc` | — | 1 |
| `2026-07-19-mgba-runtime-safety` | doc | other | `doc` | — | 1 |
| `2026-07-19-mgba-runtime-safety-design` | doc | other | `doc` | — | 1 |
| `2026-07-21-butano-foundation-research` | doc | other | `doc` | — | 1 |
| `2026-07-21-butano-foundation-research-design` | doc | other | `doc` | — | 1 |
| `2026-07-21-butano-scenario-41-battle` | doc | other | `doc` | — | 1 |
| `2026-07-21-butano-scenario-41-battle-design` | doc | other | `doc` | — | 1 |
| `2026-07-21-codex-agent-timing-benchmark` | doc | other | `doc` | — | 1 |
| `2026-07-21-codex-agent-timing-benchmark-design` | doc | other | `doc` | — | 1 |
| `2026-07-22-butano-scenario-41-one-to-one-design` | doc | other | `doc` | — | 2 |
| `2026-07-22-butano-scenario-41-reference-capture` | doc | other | `doc` | — | 1 |
| `2026-07-23-battle-controller-checkpoint-binding` | doc | other | `doc` | — | 1 |
| `analyze_rom_ai_entry_domains` | tool | code | `doc` | — | 2 |
| `analyze_rom_unknown_clusters` | tool | code | `doc` | — | 17 |
| `audio-tie-lifecycle-20260713` | note | audio | `doc` | — | 2 |
| `audit_reverse_engineering_proof` | tool | code | `doc` | — | 1 |
| `audit_rom_byte_coverage` | tool | code | `doc` | — | 3 |
| `battle-effect-controlled-runtime-20260801` | note | visual | `doc` | — | 1 |
| `battle-effect-controlled-runtime-v1` | artifact | visual | `doc` | — | 2 |
| `battle-effect-direct-spawn-runtime-v1` | artifact | visual | `doc` | — | 2 |
| `battle-effect-group15-allocator-side-runtime-v1` | artifact | visual | `doc` | — | 2 |
| `battle-effect-group15-natural-runtime-v1` | artifact | visual | `doc` | — | 1 |
| `battle-effect-observed-frame-phases-v1` | artifact | visual | `doc` | — | 1 |
| `build-api-ownership-20260713` | note | other | `doc` | — | 1 |
| `build-artifact-cleanup-audit-20260729` | note | other | `doc` | — | 1 |
| `build-pipeline` | doc | other | `doc` | — | 3 |
| `butano-agent-timing-benchmark-20260721` | note | other | `doc` | — | 5 |
| `butano-battle-architecture-implementation-20260722` | note | other | `doc` | — | 2 |
| `butano-battle-flow-video-review-20260722` | note | other | `doc` | — | 4 |
| `butano-battle-video-frame-analysis-20260722` | note | other | `doc` | — | 5 |
| `butano-deployment-runtime-20260721` | note | other | `doc` | — | 1 |
| `character-battle-palette-writeback-20260731` | note | visual | `doc` | — | 1 |
| `codex-goal-comet-governance` | doc | other | `doc` | — | 2 |
| `codex-mgba-cost-time-audit-20260716` | doc | other | `doc` | — | 2 |
| `commit-convention` | doc | other | `doc` | — | 1 |
| `content-pipeline` | doc | other | `doc` | — | 4 |
| `development-status` | doc | other | `doc` | — | 2 |
| `editor-emulator-link` | doc | other | `doc` | — | 2 |
| `experiment-artifact-lifecycle` | doc | other | `doc` | — | 1 |
| `experiment_workspace` | tool | code | `doc` | — | 3 |
| `export_residual_wram_tilemap_resource_ownership` | tool | code | `doc` | — | 1 |
| `export_rom_cfg_inventory` | tool | code | `doc` | — | 1 |
| `export_rom_fixed_renderer_script_records` | tool | code | `doc` | — | 1 |
| `export_rom_gpu_copy_queue_inventory` | tool | code | `doc` | — | 2 |
| `export_rom_small_cfg_dependency_batch` | tool | code | `doc` | — | 1 |
| `export_rom_training_text_script_inventory` | tool | code | `doc` | — | 1 |
| `final-completion-report` | doc | other | `doc` | — | 4 |
| `handover-20261020-reverse-tree` | note | other | `doc` | — | 1 |
| `legacy-artifact-acceptance-contract-v1` | doc | other | `doc` | — | 2 |
| `legacy-generator-safety-20260711` | note | other | `doc` | — | 3 |
| `local-mgba-build` | note | other | `doc` | — | 2 |
| `m4a-command-vm-20260713` | note | other | `doc` | — | 3 |
| `m4a-track-register-state-20260713` | note | other | `doc` | — | 2 |
| `macos_mgba_toolchain_profile` | tool | code | `doc` | — | 1 |
| `measure_reverse_throughput` | tool | code | `doc` | — | 1 |
| `mgba-threaded-fastforward-fix` | note | other | `doc` | — | 1 |
| `next-action-plan` | doc | other | `doc` | — | 2 |
| `next-steps` | note | other | `doc` | — | 1 |
| `ocr-dialogue-report` | note | other | `doc` | — | 1 |
| `ocr-longwalk-report` | note | other | `doc` | — | 2 |
| `ocr-newgame-report` | note | other | `doc` | — | 3 |
| `phase3-final-status` | doc | other | `doc` | — | 3 |
| `prepare_rom_verifier_contracts` | tool | code | `doc` | — | 2 |
| `prepare_rom_verifier_contracts_win` | tool | code | `doc` | — | 1 |
| `remaining-reverse-work-plan-20261001` | doc | other | `doc` | — | 1 |
| `remaining-reverse-work-plan-20261001` | note | other | `doc` | — | 1 |
| `remaining-reverse-work-plan-20261001` | note | other | `doc` | — | 1 |
| `remaining-reverse-work-plan-20261001` | note | other | `doc` | — | 1 |
| `remaining-reverse-work-plan-20261001` | note | other | `doc` | — | 1 |
| `remaining-reverse-work-plan-20261001` | note | other | `doc` | — | 1 |
| `remaining-reverse-work-plan-20261001` | note | other | `doc` | — | 1 |
| `remaining-runtime-bank-probes-20260713` | note | other | `doc` | — | 3 |
| `residual-wram-tilemap-pixel-ab-20260801` | note | residual | `doc` | — | 1 |
| `reverse-engineering-handoff-20260711` | doc | other | `doc` | — | 9 |
| `reverse-engineering-handoff-current-20260905` | doc | other | `doc` | — | 3 |
| `reverse-engineering-handoff-current-20260905` | note | other | `doc` | — | 3 |
| `reverse-engineering-handoff-current-20260905` | note | other | `doc` | — | 3 |
| `reverse-engineering-handoff-current-20260905` | note | other | `doc` | — | 3 |
| `reverse-engineering-handoff-current-20260905` | note | other | `doc` | — | 3 |
| `reverse-engineering-handoff-current-20260905` | note | other | `doc` | — | 3 |
| `reverse-engineering-handoff-current-20260905` | note | other | `doc` | — | 3 |
| `reverse-engineering-macos-intel-handoff-20260715` | doc | other | `doc` | — | 4 |
| `reverse-engineering-proof-policy` | doc | other | `doc` | — | 1 |
| `reverse-engineering-proof-policy` | note | other | `doc` | — | 1 |
| `reverse-engineering-proof-policy` | note | other | `doc` | — | 1 |
| `reverse-engineering-proof-policy` | note | other | `doc` | — | 1 |
| `reverse-engineering-roadmap` | doc | other | `doc` | — | 2 |
| `rom-ai-config-writer-preflight-20260930` | note | rom | `doc` | — | 6 |
| `rom-ai-entry-local-domains-20260930` | note | rom | `doc` | — | 5 |
| `rom-ai-producer-and-pool-alias-20260930` | note | rom | `doc` | — | 5 |
| `rom-ai-renderer-script-dependencies-20260930` | note | rom | `doc` | — | 2 |
| `rom-battle-condition-result-text-v1` | artifact | rom | `doc` | — | 1 |
| `rom-battle-controller-consumed-literals-v1` | artifact | rom | `doc` | — | 2 |
| `rom-battle-distance-dispatcher-cfg-v1` | artifact | rom | `doc` | — | 1 |
| `rom-battle-message-text-inventory-20260811` | note | rom | `doc` | — | 1 |
| `rom-battle-message-text-inventory-v1` | artifact | rom | `doc` | — | 2 |
| `rom-battle-status-bar-caller-slice-v1` | artifact | rom | `doc` | — | 1 |
| `rom-boot-framebuffers-v1` | artifact | rom | `doc` | — | 1 |
| `rom-boot-interwork-continuation-v1` | artifact | rom | `doc` | not-applicable | 1 |
| `rom-boot-interwork-v1` | artifact | rom | `doc` | — | 1 |
| `rom-boot-register-init-dependency-cfg-v1` | artifact | rom | `doc` | — | 1 |
| `rom-boot-state-dispatcher-cfg-v1` | artifact | rom | `doc` | — | 3 |
| `rom-boot-thumb-handoff-cfg-v1` | artifact | rom | `doc` | — | 3 |
| `rom-cfg-inventory-v2` | artifact | rom | `doc` | — | 3 |
| `rom-cfg-proven-roots-batch-consumed-literals-v1` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-proven-roots-v1` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v10` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-proven-roots-v11` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-proven-roots-v12` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-proven-roots-v13` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-proven-roots-v15` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-proven-roots-v16` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v16-consumed-literals-v1` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v17` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v18` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v19` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v2` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v20` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v21` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v21-20260905` | note | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v3` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v3-v4-20260813` | note | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v4` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v5` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v6` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v7` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v8` | artifact | rom | `doc` | — | 1 |
| `rom-cfg-proven-roots-v9` | artifact | rom | `doc` | — | 3 |
| `rom-cfg-seeds-v1` | artifact | rom | `doc` | not-applicable | 1 |
| `rom-cfg-v1-consumed-literals-v1` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-v2-consumed-literals-v1` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-v2-shadowed-consumed-literals-v1` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-v3-consumed-literals-v1` | artifact | rom | `doc` | — | 2 |
| `rom-cfg-v6-consumed-literals-v1` | artifact | rom | `doc` | — | 2 |
| `rom-cgb-helper-bounded-cfg-v1` | artifact | rom | `doc` | — | 3 |
| `rom-cgbsound-bounded-cfg-v1` | artifact | rom | `doc` | — | 3 |
| `rom-chapter-script-consumer-roots-v1` | artifact | rom | `doc` | — | 1 |
| `rom-chapter-script-unbound-tail-v1` | artifact | rom | `doc` | not-applicable | 2 |
| `rom-chapter-selector-code-slice-v1` | artifact | rom | `doc` | — | 1 |
| `rom-dialogue-padding-inventory-v1` | artifact | rom | `doc` | — | 2 |
| `rom-event-handler-cfg-v1` | artifact | rom | `doc` | — | 2 |
| `rom-evidence-selector-repair-20260905` | note | rom | `doc` | — | 3 |
| `rom-fast-audit-four-packet-baseline-v1` | artifact | rom | `doc` | not-applicable | 2 |
| `rom-finite-lookup-scope-review-20260905` | note | rom | `doc` | — | 3 |
| `rom-legacy-acceptance-20260905-v1` | artifact | rom | `doc` | — | 2 |
| `rom-m4a-byte-inventory-v1` | artifact | rom | `doc` | — | 1 |
| `rom-m4a-initializer-chain-v1` | artifact | rom | `doc` | — | 3 |
| `rom-map-resource-relocation-roundtrip-20261002` | note | rom | `doc` | — | 1 |
| `rom-map-resource-relocation-roundtrip-20261002` | note | rom | `doc` | — | 1 |
| `rom-mp2k-dispatcher-v1` | artifact | rom | `doc` | — | 3 |
| `rom-mp2k-note-allocator-20260829` | note | rom | `doc` | — | 1 |
| `rom-mp2k-note-allocator-v1` | artifact | rom | `doc` | — | 4 |
| `rom-mplaymain-scheduler-20260828` | note | rom | `doc` | — | 1 |
| `rom-mplaymain-scheduler-v1` | artifact | rom | `doc` | — | 4 |
| `rom-open-root-and-large-candidate-review-20260905` | note | rom | `doc` | — | 3 |
| `rom-parser-bound-zero-padding-v1` | artifact | rom | `doc` | — | 3 |
| `rom-partial-bank-joint-matrix-20261001` | note | rom | `doc` | — | 1 |
| `rom-partial-bank-joint-matrix-20261001` | note | rom | `doc` | — | 1 |
| `rom-pointer-lz77-graphics-preview-20260730` | note | rom | `doc` | — | 1 |
| `rom-positions-aux-dispatch-v1` | artifact | rom | `doc` | — | 2 |
| `rom-prebattle-menu-controller-cfg-v1` | artifact | rom | `doc` | — | 1 |
| `rom-profile-selector-code-slices-v1` | artifact | rom | `doc` | — | 1 |
| `rom-profile-text-inventory-v1` | artifact | rom | `doc` | — | 1 |
| `rom-referenced-text-slot-padding-v1` | artifact | rom | `doc` | — | 2 |
| `rom-reverse-engineering-results` | doc | rom | `doc` | — | 6 |
| `rom-scene-source-closures-v1` | artifact | rom | `doc` | — | 1 |
| `rom-scene-visual-source-ranges-v1` | artifact | rom | `doc` | — | 3 |
| `rom-selector-code-windows-v1` | artifact | rom | `doc` | — | 3 |
| `rom-selector-text-bindings-v1` | artifact | rom | `doc` | — | 1 |
| `rom-sequel-plan` | doc | rom | `doc` | — | 1 |
| `rom-small-cfg-dependency-batch-20260905` | note | rom | `doc` | — | 4 |
| `rom-small-cfg-dependency-batch-v1` | artifact | rom | `doc` | — | 3 |
| `rom-small-cfg-dependency-tier2-20260930` | note | rom | `doc` | — | 3 |
| `rom-soundmain-relocated-cfg-v1` | artifact | rom | `doc` | — | 4 |
| `rom-sprite-component-source-v1` | artifact | rom | `doc` | not-applicable | 2 |
| `rom-sprite-loader-tail-v1` | artifact | rom | `doc` | — | 1 |
| `rom-story-callback-dependency-closures-v1` | artifact | rom | `doc` | — | 1 |
| `rom-story-next-dependency-cfg-v1` | artifact | rom | `doc` | — | 1 |
| `rom-story-selector-dependency-cfg-v1` | artifact | rom | `doc` | — | 2 |
| `rom-story-state-callback-cfg-v1` | artifact | rom | `doc` | — | 3 |
| `rom-story-state-entry-c4cc-v1` | artifact | rom | `doc` | — | 2 |
| `rom-strided-prefix-local-read-domain-20260905` | note | rom | `doc` | — | 4 |
| `rom-task-callback-078e38-closure-v1` | artifact | rom | `doc` | — | 2 |
| `rom-task-scheduler-core-v1` | artifact | rom | `doc` | — | 3 |
| `rom-text-bg-loop-continuation-v1` | artifact | rom | `doc` | — | 1 |
| `rom-text-bg-task-closure-v1` | artifact | rom | `doc` | — | 2 |
| `rom-training-text-script-inventory-v1` | artifact | rom | `doc` | — | 2 |
| `rom-u8-indexed-u16-pair-lookup-20260827` | note | rom | `doc` | — | 1 |
| `rom-unbound-lz77-inventory-v1` | artifact | rom | `doc` | — | 2 |
| `rom-unknown-candidate-59eae0-negative-evidence-20260827` | note | rom | `doc` | — | 2 |
| `rom-unknown-cluster-refresh-20260902` | note | rom | `doc` | — | 2 |
| `rom-v17-v18-helper-cfg-v1` | artifact | rom | `doc` | — | 1 |
| `rom-value-range-text-inventory-v1` | artifact | rom | `doc` | — | 1 |
| `rom-verifier-checkout-setup` | doc | rom | `doc` | — | 2 |
| `rom-verifier-runtime-inputs-20260905` | note | rom | `doc` | — | 1 |
| `rom_small_cfg_callback_gaps_independent_verifier` | tool | code | `doc` | — | 1 |
| `rom_small_cfg_dependency_packets` | tool | code | `doc` | — | 1 |
| `scenario-48-academy-runtime-20260720` | note | scenario | `doc` | — | 1 |
| `sequel-authoring-workspace` | doc | other | `doc` | — | 1 |
| `sprite-definition-runtime-v1` | artifact | visual | `doc` | — | 1 |
| `structure-field-semantics` | doc | other | `doc` | — | 11 |
| `test_analyze_rom_ai_entry_domains` | test | code | `doc` | — | 1 |
| `test_analyze_rom_unknown_clusters` | test | code | `doc` | — | 3 |
| `test_audit_reverse_engineering_coverage_count_liveness` | test | code | `doc` | — | 2 |
| `test_build_battle_message_runtime_probe_slots` | test | code | `doc` | — | 1 |
| `test_data_table_b_partial_bank` | test | code | `doc` | — | 1 |
| `test_prepare_rom_verifier_contracts` | test | code | `doc` | — | 1 |
| `test_prepare_rom_verifier_contracts_win` | test | code | `doc` | — | 1 |
| `testing-checklist` | doc | other | `doc` | — | 3 |
| `verify_battle_effect_resource_writeback_audit` | tool | code | `doc` | — | 2 |
| `verify_battle_encounters_story_visual_pixel_ab` | tool | code | `doc` | — | 2 |
| `verify_battle_presentation_rom_ranges` | tool | code | `doc` | — | 1 |
| `verify_battle_presentation_text_padding` | tool | code | `doc` | — | 1 |
| `verify_bg_resource_writeback_audit` | tool | code | `doc` | — | 2 |
| `verify_character_battle_graphics_writeback_audit` | tool | code | `doc` | — | 2 |
| `verify_character_battle_palette_writeback_audit` | tool | code | `doc` | — | 2 |
| `verify_character_battle_structure_writeback_audit` | tool | code | `doc` | — | 2 |
| `verify_cutscene_obj_primary_ptr_ab` | tool | code | `doc` | — | 2 |
| `verify_data_table_b_message0_pointer_ab` | tool | code | `doc` | — | 1 |
| `verify_data_table_b_partial_bank` | tool | code | `doc` | — | 1 |
| `verify_dialogue_font_source_padding` | tool | code | `doc` | — | 1 |
| `verify_disproved_bank_candidates` | tool | code | `doc` | — | 1 |
| `verify_map41_primary_layout_pixel_ab_evidence` | tool | code | `doc` | — | 2 |
| `verify_map_events_e4_handler_pixel_ab` | tool | code | `doc` | — | 2 |
| `verify_map_resource_writeback_audit` | tool | code | `doc` | — | 2 |
| `verify_map_sprites_definition_pixel_ab` | tool | code | `doc` | — | 2 |
| `verify_menu_portrait_pixel_ab_evidence` | tool | code | `doc` | — | 2 |
| `verify_menu_portrait_writeback_audit` | tool | code | `doc` | — | 2 |
| `verify_motion_effect_parameter_pixel_ab` | tool | code | `doc` | — | 2 |
| `verify_overview_gradient_overlay` | tool | code | `doc` | — | 1 |
| `verify_portrait_palette_producers` | tool | code | `doc` | — | 1 |
| `verify_residual_wram_visual_metadata_abi` | tool | code | `doc` | — | 1 |
| `verify_rom_artifact_bound_alignment_gaps` | tool | code | `doc` | — | 1 |
| `verify_rom_battle_condition_records` | tool | code | `doc` | — | 1 |
| `verify_rom_battle_controller_cfg` | tool | code | `doc` | — | 1 |
| `verify_rom_battle_controller_consumed_literals` | tool | code | `doc` | — | 1 |
| `verify_rom_battle_message_text_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_battle_sound_selector` | tool | code | `doc` | — | 1 |
| `verify_rom_battle_status_bar_caller_slice` | tool | code | `doc` | — | 1 |
| `verify_rom_boot_framebuffers` | tool | code | `doc` | — | 1 |
| `verify_rom_boot_interwork` | tool | code | `doc` | — | 1 |
| `verify_rom_boot_thumb_code_literal_alignment_gaps` | tool | code | `doc` | — | 1 |
| `verify_rom_boot_thumb_handoff_cfg` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_inventory` | tool | code | `doc` | — | 3 |
| `verify_rom_cfg_inventory_v3` | tool | code | `doc` | — | 3 |
| `verify_rom_cfg_proven_roots` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_batch_consumed_literals` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v10` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v11` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v12_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v13_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v14_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v15_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v2` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v3` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v4` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v5` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v6` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v7` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v8` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_proven_roots_v9` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_v1_consumed_literals` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_v2_consumed_literals` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_v2_shadowed_consumed_literals` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_v3_consumed_literals` | tool | code | `doc` | — | 1 |
| `verify_rom_cfg_v6_consumed_literals` | tool | code | `doc` | — | 1 |
| `verify_rom_cgb_bounded_cfg_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_cgbsound_bounded_cfg` | tool | code | `doc` | — | 1 |
| `verify_rom_chapter_script_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_chapter_selector_code_slice` | tool | code | `doc` | — | 1 |
| `verify_rom_cutscene_obj_palette_definition_alignment_gaps` | tool | code | `doc` | — | 1 |
| `verify_rom_cutscene_obj_source_ranges` | tool | code | `doc` | — | 1 |
| `verify_rom_dialogue_padding_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_dialogue_text_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_direct_cpuset_gpu_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_directsound_pitch_lookup_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_fixed_consumer_text_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_fixed_consumer_text_padding` | tool | code | `doc` | — | 1 |
| `verify_rom_fixed_renderer_script_records` | tool | code | `doc` | — | 3 |
| `verify_rom_gpu_copy_queue_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_lz77_alignment_padding` | tool | code | `doc` | — | 1 |
| `verify_rom_m4a_byte_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_m4a_initializer_chain` | tool | code | `doc` | — | 1 |
| `verify_rom_menu_portrait_lz77_palette_alignment_gaps` | tool | code | `doc` | — | 1 |
| `verify_rom_menu_portrait_palette_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_mp2k_dispatcher` | tool | code | `doc` | — | 1 |
| `verify_rom_mp2k_note_allocator` | tool | code | `doc` | — | 1 |
| `verify_rom_mplaymain_scheduler_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_parser_bound_zero_padding` | tool | code | `doc` | — | 1 |
| `verify_rom_pointer_lz77_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_positions_aux_dispatch` | tool | code | `doc` | — | 1 |
| `verify_rom_profile_selector_code_slices` | tool | code | `doc` | — | 1 |
| `verify_rom_profile_text_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_psg_frequency_lookup_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_referenced_text_slot_padding` | tool | code | `doc` | — | 1 |
| `verify_rom_renderer_text_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_renderer_text_padding` | tool | code | `doc` | — | 1 |
| `verify_rom_scene_visual_source_ranges` | tool | code | `doc` | — | 1 |
| `verify_rom_scheduler_callback_lifecycle_gate` | tool | code | `doc` | — | 4 |
| `verify_rom_selector_code_windows` | tool | code | `doc` | — | 1 |
| `verify_rom_selector_direct_source_records` | tool | code | `doc` | — | 1 |
| `verify_rom_selector_text_bindings` | tool | code | `doc` | — | 1 |
| `verify_rom_small_cfg_dependency_batch` | tool | code | `doc` | — | 3 |
| `verify_rom_soundmain_relocated_alignment_gaps` | tool | code | `doc` | — | 1 |
| `verify_rom_soundmain_relocated_cfg_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_sprite_loader_tail` | tool | code | `doc` | — | 1 |
| `verify_rom_task_scheduler_core_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_tile_bg_lz77_palette_alignment_gaps` | tool | code | `doc` | — | 1 |
| `verify_rom_training_text_script_inventory` | tool | code | `doc` | — | 2 |
| `verify_rom_u8_indexed_u16_pair_lookup` | tool | code | `doc` | — | 1 |
| `verify_rom_u8_indexed_u8_triplet_lookup_bundle` | tool | code | `doc` | — | 1 |
| `verify_rom_unbound_lz77_inventory` | tool | code | `doc` | — | 1 |
| `verify_rom_value_range_text_inventory` | tool | code | `doc` | — | 1 |
| `verify_scene_visual_composites` | tool | code | `doc` | — | 1 |
| `verify_similar_table_candidates` | tool | code | `doc` | — | 1 |
| `verify_tile_asset_descriptor_pixel_ab` | tool | code | `doc` | — | 2 |
| `web-editor-spec` | doc | other | `doc` | — | 3 |
| `AGENTS` | note | other | `none` | — | 0 |
| `AGENTS` | note | other | `none` | — | 0 |
| `AGENTS` | note | other | `none` | — | 0 |
| `AGENTS` | note | other | `none` | — | 0 |
| `AGENTS` | note | other | `none` | — | 0 |
| `AGENTS` | note | other | `none` | — | 0 |
| `README` | note | other | `none` | — | 0 |
| `README` | note | other | `none` | — | 0 |
| `__init__` | tool | code | `none` | — | 0 |
| `__init__` | tool | code | `none` | — | 0 |
| `analyze_battle_effect_formation_routes` | tool | code | `none` | — | 0 |
| `analyze_battle_effect_hardcoded_selector_producers` | tool | code | `none` | — | 0 |
| `analyze_battlefield_object_effect_chain` | tool | code | `none` | — | 0 |
| `analyze_battlefield_object_producers` | tool | code | `none` | — | 0 |
| `analyze_reverse_engineering_gaps` | tool | code | `none` | — | 0 |
| `analyze_rom_renderer_excluded_roots` | tool | code | `none` | — | 0 |
| `analyze_rom_renderer_handler_graphs` | tool | code | `none` | — | 0 |
| `arm` | tool | code | `none` | — | 0 |
| `arm64` | tool | code | `none` | — | 0 |
| `audit_battle_effect_fixed_roundtrip` | tool | code | `none` | — | 0 |
| `audit_map_resource_fixed_roundtrip` | tool | code | `none` | — | 0 |
| `audit_map_resource_relocation_roundtrip` | tool | code | `none` | — | 0 |
| `auditor-module-failures-20261020` | note | other | `none` | — | 0 |
| `auto-exit-prevention-mgba-compile-20260806` | note | other | `none` | — | 0 |
| `bank-player-visible-closure-plan-20260806` | note | other | `none` | — | 0 |
| `batch_test_dispatcher_triggers` | tool | code | `none` | — | 0 |
| `battle-effect-controlled-phase-extension-20260809` | note | visual | `none` | — | 0 |
| `battle-effect-direct-spawn-runtime-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-frame-phase-20260801` | note | visual | `none` | — | 0 |
| `battle-effect-group1-pixel-ab-20260801` | note | visual | `none` | — | 0 |
| `battle-effect-group11-pixel-ab-20260801` | note | visual | `none` | — | 0 |
| `battle-effect-group12-group13-route-audit-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group13-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group14-pixel-ab-20260801` | note | visual | `none` | — | 0 |
| `battle-effect-group15-allocator-side-runtime-20260801` | note | visual | `none` | — | 0 |
| `battle-effect-group15-natural-runtime-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group15-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group16-natural-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group17-natural-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group18-controlled-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group18-natural-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group2-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group2-route-stop-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group3-controlled-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group3-natural-expiry-phase-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group3-natural-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group4-natural-pixel-ab-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-group5-pixel-ab-20260801` | note | visual | `none` | — | 0 |
| `battle-effect-group6-controlled-pixel-ab-20260809` | note | visual | `none` | — | 0 |
| `battle-effect-group6-entry-audit-20260806` | note | visual | `none` | — | 0 |
| `battle-effect-groups7-12-controlled-pixel-ab-20260809` | note | visual | `none` | — | 0 |
| `battle-effect-hardcoded-selector-producers-20260802` | note | visual | `none` | — | 0 |
| `battle-effect-observed-frame-phases-20260801` | note | visual | `none` | — | 0 |
| `battle-effect-resource-relocation-20260731` | note | visual | `none` | — | 0 |
| `battle-effect-resource-writeback-20260731` | note | visual | `none` | — | 0 |
| `battle-effect-runtime-oam-bindings-20260801` | note | visual | `none` | — | 0 |
| `battle-effect-runtime-oam-task-bindings-20260801` | note | visual | `none` | — | 0 |
| `battle-encounters-story-visual-player-visible-20260809` | note | battle | `none` | — | 0 |
| `battlefield-object-effect-chain-20260802` | note | battle | `none` | — | 0 |
| `bg-resource-relocation-20260731` | note | visual | `none` | — | 0 |
| `bg-resource-writeback-20260731` | note | visual | `none` | — | 0 |
| `bpf` | tool | code | `none` | — | 0 |
| `build_battle_effect_group5_pixel_ab` | tool | code | `none` | — | 0 |
| `build_battle_effect_pixel_ab` | tool | code | `none` | — | 0 |
| `build_battle_encounters_story_visual_pixel_ab` | tool | code | `none` | — | 0 |
| `build_battle_message_runtime_probe_slots` | tool | code | `none` | — | 0 |
| `build_chapter_battle_route_probe` | tool | code | `none` | — | 0 |
| `build_character_battle_graphics_pixel_ab` | tool | code | `none` | — | 0 |
| `build_character_battle_visual_resource_matrix` | tool | code | `none` | — | 0 |
| `build_controlled_battle_effect_allocator_reset_probe` | tool | code | `none` | — | 0 |
| `build_controlled_battle_effect_direct_spawn_probe` | tool | code | `none` | — | 0 |
| `build_controlled_battle_effect_pixel_ab` | tool | code | `none` | — | 0 |
| `build_controlled_battle_effect_sequence_probe` | tool | code | `none` | — | 0 |
| `build_cutscene_obj_id1_pixel_ab` | tool | code | `none` | — | 0 |
| `build_cutscene_obj_primary_ptr_ab` | tool | code | `none` | — | 0 |
| `build_cutscene_obj_secondary_ptr_ab` | tool | code | `none` | — | 0 |
| `build_map41_primary_layout_pixel_ab` | tool | code | `none` | — | 0 |
| `build_map41_visual_resource_matrix` | tool | code | `none` | — | 0 |
| `build_map_events_e4_handler_pixel_ab` | tool | code | `none` | — | 0 |
| `build_map_sprites_definition_pixel_ab` | tool | code | `none` | — | 0 |
| `build_menu_portrait_pixel_ab` | tool | code | `none` | — | 0 |
| `build_menu_portrait_pointer_ab` | tool | code | `none` | — | 0 |
| `build_motion_effect_parameter_pixel_ab` | tool | code | `none` | — | 0 |
| `build_natural_delayed_battle_effect_pixel_ab` | tool | code | `none` | — | 0 |
| `build_residual_wram_tilemap_pixel_ab` | tool | code | `none` | — | 0 |
| `build_rom_expansion_probe` | tool | code | `none` | — | 0 |
| `build_sappy_engine_master_enable_ab` | tool | code | `none` | — | 0 |
| `build_tile_asset_descriptor_pixel_ab` | tool | code | `none` | — | 0 |
| `build_world_map_page0_pixel_ab` | tool | code | `none` | — | 0 |
| `character-battle-graphics-pixel-ab-20260801` | note | visual | `none` | — | 0 |
| `character-battle-graphics-writeback-20260731` | note | visual | `none` | — | 0 |
| `character-battle-structure-writeback-20260731` | note | visual | `none` | — | 0 |
| `character-runtime-oam-bindings-20260730` | note | visual | `none` | — | 0 |
| `character-runtime-oam-task-bindings-20260730` | note | visual | `none` | — | 0 |
| `check_staged_artifact_policy` | tool | code | `none` | — | 0 |
| `cutscene-obj-bundle-relocation-20260731` | note | presentation | `none` | — | 0 |
| `cutscene-visual-resource-player-visible-20260809` | note | presentation | `none` | — | 0 |
| `d0-bank-exhaustion-gate-20261020` | note | other | `none` | — | 0 |
| `direct-image-palette-relocation-20260731` | note | other | `none` | — | 0 |
| `disassemble_battle_effect_dispatchers` | tool | code | `none` | — | 0 |
| `evm` | tool | code | `none` | — | 0 |
| `export_battle_effect_controlled_runtime` | tool | code | `none` | — | 0 |
| `export_battle_effect_direct_spawn_runtime` | tool | code | `none` | — | 0 |
| `export_battle_effect_frame_phase` | tool | code | `none` | — | 0 |
| `export_battle_effect_group15_allocator_side_runtime` | tool | code | `none` | — | 0 |
| `export_battle_effect_group15_natural_runtime` | tool | code | `none` | — | 0 |
| `export_battle_effect_group5_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `export_battle_effect_observed_frame_phases` | tool | code | `none` | — | 0 |
| `export_battle_effect_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `export_battle_effect_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `export_battle_effect_resource_writeback_audit` | tool | code | `none` | — | 0 |
| `export_battle_effect_runtime_oam_bindings` | tool | code | `none` | — | 0 |
| `export_battle_effect_runtime_oam_task_bindings` | tool | code | `none` | — | 0 |
| `export_battle_encounters_story_visual_pixel_ab` | tool | code | `none` | — | 0 |
| `export_battle_status_bars` | tool | code | `none` | — | 0 |
| `export_bg_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `export_bg_resource_writeback_audit` | tool | code | `none` | — | 0 |
| `export_character_battle_bundle_relocation_audit` | tool | code | `none` | — | 0 |
| `export_character_battle_graphics_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `export_character_battle_graphics_writeback_audit` | tool | code | `none` | — | 0 |
| `export_character_battle_palette_writeback_audit` | tool | code | `none` | — | 0 |
| `export_character_battle_structure_writeback_audit` | tool | code | `none` | — | 0 |
| `export_character_battle_visual_resource_matrix_evidence` | tool | code | `none` | — | 0 |
| `export_character_runtime_oam_bindings` | tool | code | `none` | — | 0 |
| `export_character_runtime_oam_task_bindings` | tool | code | `none` | — | 0 |
| `export_character_runtime_unit_oam_bindings` | tool | code | `none` | — | 0 |
| `export_controlled_battle_effect_pixel_ab` | tool | code | `none` | — | 0 |
| `export_cutscene_obj_bundle_relocation_audit` | tool | code | `none` | — | 0 |
| `export_cutscene_obj_id1_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `export_cutscene_obj_primary_ptr_ab` | tool | code | `none` | — | 0 |
| `export_cutscene_obj_secondary_ptr_ab` | tool | code | `none` | — | 0 |
| `export_data_table_b_message0_pointer_ab` | tool | code | `none` | — | 0 |
| `export_direct_image_palette_relocation_audit` | tool | code | `none` | — | 0 |
| `export_generic_sprite_bundle_relocation_audit` | tool | code | `none` | — | 0 |
| `export_initializer_resource_pack` | tool | code | `none` | — | 0 |
| `export_levels_status_per_level_ab` | tool | code | `none` | — | 0 |
| `export_map41_primary_layout_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `export_map41_visual_resource_matrix_evidence` | tool | code | `none` | — | 0 |
| `export_map_events_e4_handler_pixel_ab` | tool | code | `none` | — | 0 |
| `export_map_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `export_map_resource_writeback_audit` | tool | code | `none` | — | 0 |
| `export_map_sprites_definition_pixel_ab` | tool | code | `none` | — | 0 |
| `export_menu_portrait_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `export_menu_portrait_pointer_ab` | tool | code | `none` | — | 0 |
| `export_menu_portrait_relocation_audit` | tool | code | `none` | — | 0 |
| `export_menu_portrait_writeback_audit` | tool | code | `none` | — | 0 |
| `export_motion_effect_parameter_pixel_ab` | tool | code | `none` | — | 0 |
| `export_natural_delayed_battle_effect_pixel_ab` | tool | code | `none` | — | 0 |
| `export_overview_gradient_overlay` | tool | code | `none` | — | 0 |
| `export_portrait_palette_producers` | tool | code | `none` | — | 0 |
| `export_residual_lz77_graphics_relocation_audit` | tool | code | `none` | — | 0 |
| `export_residual_text_bg_tilemap_relocation_audit` | tool | code | `none` | — | 0 |
| `export_residual_text_bg_tilemap_resource_ownership` | tool | code | `none` | — | 0 |
| `export_residual_wram_crop_tilemap_runtime_evidence` | tool | code | `none` | — | 0 |
| `export_residual_wram_derived_tilemap_relocation_audit` | tool | code | `none` | — | 0 |
| `export_residual_wram_tilemap_abi` | tool | code | `none` | — | 0 |
| `export_residual_wram_tilemap_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `export_residual_wram_tilemap_relocation_audit` | tool | code | `none` | — | 0 |
| `export_residual_wram_tilemap_runtime_evidence` | tool | code | `none` | — | 0 |
| `export_residual_wram_tilemap_runtime_v2` | tool | code | `none` | — | 0 |
| `export_residual_wram_transformed_tilemap_runtime_evidence` | tool | code | `none` | — | 0 |
| `export_residual_wram_visual_metadata_abi` | tool | code | `none` | — | 0 |
| `export_rom_alternate_dialogue_table` | tool | code | `none` | — | 0 |
| `export_rom_animation_descriptor_pool_v2` | tool | code | `none` | — | 0 |
| `export_rom_battle_condition_records` | tool | code | `none` | — | 0 |
| `export_rom_battle_condition_result_text` | tool | code | `none` | — | 0 |
| `export_rom_battle_controller_cfg` | tool | code | `none` | — | 0 |
| `export_rom_battle_controller_consumed_literals` | tool | code | `none` | — | 0 |
| `export_rom_battle_distance_dispatcher_cfg` | tool | code | `none` | — | 0 |
| `export_rom_battle_message_text_inventory` | tool | code | `none` | — | 0 |
| `export_rom_battle_sound_selector` | tool | code | `none` | — | 0 |
| `export_rom_battle_status_bar_caller_slice` | tool | code | `none` | — | 0 |
| `export_rom_boot_copy_sources` | tool | code | `none` | — | 0 |
| `export_rom_boot_framebuffers` | tool | code | `none` | — | 0 |
| `export_rom_boot_interwork` | tool | code | `none` | — | 0 |
| `export_rom_boot_interwork_continuation` | tool | code | `none` | — | 0 |
| `export_rom_boot_register_init_dependency_cfg` | tool | code | `none` | — | 0 |
| `export_rom_boot_state_dispatcher_cfg` | tool | code | `none` | — | 0 |
| `export_rom_boot_thumb_handoff_cfg` | tool | code | `none` | — | 0 |
| `export_rom_bounded_index_u16_pair_table` | tool | code | `none` | — | 0 |
| `export_rom_cfg_inventory_v3` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_batch_consumed_literals` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v10` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v11` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v12` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v13` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v14` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v15` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v16` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v16_consumed_literals` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v17` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v18` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v19` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v2` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v20` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v21` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v3` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v4` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v5` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v6` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v7` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v8` | tool | code | `none` | — | 0 |
| `export_rom_cfg_proven_roots_v9` | tool | code | `none` | — | 0 |
| `export_rom_cfg_seeds` | tool | code | `none` | — | 0 |
| `export_rom_cfg_v1_consumed_literals` | tool | code | `none` | — | 0 |
| `export_rom_cfg_v2_consumed_literals` | tool | code | `none` | — | 0 |
| `export_rom_cfg_v2_shadowed_consumed_literals` | tool | code | `none` | — | 0 |
| `export_rom_cfg_v3_consumed_literals` | tool | code | `none` | — | 0 |
| `export_rom_cfg_v6_consumed_literals` | tool | code | `none` | — | 0 |
| `export_rom_cgb_helper_bounded_cfg` | tool | code | `none` | — | 0 |
| `export_rom_cgbsound_bounded_cfg` | tool | code | `none` | — | 0 |
| `export_rom_chapter_script_consumer_roots` | tool | code | `none` | — | 0 |
| `export_rom_chapter_script_inventory` | tool | code | `none` | — | 0 |
| `export_rom_chapter_selector_code_slice` | tool | code | `none` | — | 0 |
| `export_rom_cutscene_obj_source_ranges` | tool | code | `none` | — | 0 |
| `export_rom_dialogue_padding_inventory` | tool | code | `none` | — | 0 |
| `export_rom_dialogue_text_inventory` | tool | code | `none` | — | 0 |
| `export_rom_direct_cpuset_gpu_inventory` | tool | code | `none` | — | 0 |
| `export_rom_direct_dma_gpu_inventory` | tool | code | `none` | — | 0 |
| `export_rom_directsound_pitch_lookup` | tool | code | `none` | — | 0 |
| `export_rom_display_text_delta` | tool | code | `none` | — | 0 |
| `export_rom_event_handler_cfg` | tool | code | `none` | — | 0 |
| `export_rom_fixed_animation_descriptor_groups` | tool | code | `none` | — | 0 |
| `export_rom_fixed_consumer_text_inventory` | tool | code | `none` | — | 0 |
| `export_rom_fixed_index_u8_tail` | tool | code | `none` | — | 0 |
| `export_rom_fixed_pair_tables` | tool | code | `none` | — | 0 |
| `export_rom_low_script_delta` | tool | code | `none` | — | 0 |
| `export_rom_m4a_byte_inventory` | tool | code | `none` | — | 0 |
| `export_rom_m4a_initializer_chain` | tool | code | `none` | — | 0 |
| `export_rom_menu_portrait_palette_inventory` | tool | code | `none` | — | 0 |
| `export_rom_mp2k_dispatcher` | tool | code | `none` | — | 0 |
| `export_rom_mp2k_note_allocator` | tool | code | `none` | — | 0 |
| `export_rom_mplaymain_scheduler` | tool | code | `none` | — | 0 |
| `export_rom_parser_bound_zero_padding` | tool | code | `none` | — | 0 |
| `export_rom_pointer_lz77_graphics` | tool | code | `none` | — | 0 |
| `export_rom_positions_aux_dispatch` | tool | code | `none` | — | 0 |
| `export_rom_post_story_dependency_precoverage` | tool | code | `none` | — | 0 |
| `export_rom_prebattle_menu_controller_cfg` | tool | code | `none` | — | 0 |
| `export_rom_profile_selector_code_slices` | tool | code | `none` | — | 0 |
| `export_rom_profile_text_inventory` | tool | code | `none` | — | 0 |
| `export_rom_psg_frequency_lookup` | tool | code | `none` | — | 0 |
| `export_rom_referenced_text_slot_padding` | tool | code | `none` | — | 0 |
| `export_rom_renderer_records_delta` | tool | code | `none` | — | 0 |
| `export_rom_renderer_script_pointer_pool_records` | tool | code | `none` | — | 0 |
| `export_rom_renderer_text_inventory` | tool | code | `none` | — | 0 |
| `export_rom_scene_source_closures` | tool | code | `none` | — | 0 |
| `export_rom_scene_source_four_packet_precoverage` | tool | code | `none` | — | 0 |
| `export_rom_scene_visual_source_ranges` | tool | code | `none` | — | 0 |
| `export_rom_selector_code_windows` | tool | code | `none` | — | 0 |
| `export_rom_selector_direct_source_records` | tool | code | `none` | — | 0 |
| `export_rom_selector_text_bindings` | tool | code | `none` | — | 0 |
| `export_rom_soundmain_relocated_cfg` | tool | code | `none` | — | 0 |
| `export_rom_sprite_component_source` | tool | code | `none` | — | 0 |
| `export_rom_sprite_loader_tail` | tool | code | `none` | — | 0 |
| `export_rom_staged_gpu_copy_inventory` | tool | code | `none` | — | 0 |
| `export_rom_story_callback_dependency_closures` | tool | code | `none` | — | 0 |
| `export_rom_story_callback_dependency_precoverage` | tool | code | `none` | — | 0 |
| `export_rom_story_next_dependency_cfg` | tool | code | `none` | — | 0 |
| `export_rom_story_selector_dependency_cfg` | tool | code | `none` | — | 0 |
| `export_rom_story_state_callback_cfg` | tool | code | `none` | — | 0 |
| `export_rom_story_state_entry_c4cc` | tool | code | `none` | — | 0 |
| `export_rom_task_callback_078e38_closure` | tool | code | `none` | — | 0 |
| `export_rom_task_scheduler_core` | tool | code | `none` | — | 0 |
| `export_rom_text_bg_loop_continuation` | tool | code | `none` | — | 0 |
| `export_rom_text_bg_task_closure` | tool | code | `none` | — | 0 |
| `export_rom_u8_indexed_u16_pair_lookup` | tool | code | `none` | — | 0 |
| `export_rom_u8_indexed_u8_triplet_lookup` | tool | code | `none` | — | 0 |
| `export_rom_unbound_chapter_script_tail` | tool | code | `none` | — | 0 |
| `export_rom_unbound_lz77_inventory` | tool | code | `none` | — | 0 |
| `export_rom_v17_v18_helper_cfg` | tool | code | `none` | — | 0 |
| `export_rom_value_range_text_inventory` | tool | code | `none` | — | 0 |
| `export_runtime_bg_composites` | tool | code | `none` | — | 0 |
| `export_runtime_font_tile_provenance` | tool | code | `none` | — | 0 |
| `export_runtime_layer_static_provenance` | tool | code | `none` | — | 0 |
| `export_runtime_screen_composites` | tool | code | `none` | — | 0 |
| `export_sappy_engine_master_enable_ab` | tool | code | `none` | — | 0 |
| `export_scene_visual_composites` | tool | code | `none` | — | 0 |
| `export_scene_visual_transition_timelines` | tool | code | `none` | — | 0 |
| `export_story_visual_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `export_story_visual_resource_sources` | tool | code | `none` | — | 0 |
| `export_tile_asset_descriptor_pixel_ab` | tool | code | `none` | — | 0 |
| `export_tile_asset_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `export_world_map_background_relocation_audit` | tool | code | `none` | — | 0 |
| `export_world_map_page0_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `exporter-root-deletion-incident-20260809` | note | other | `none` | — | 0 |
| `find_battlefield_object_effect_seeds` | tool | code | `none` | — | 0 |
| `fixed_resource_roundtrip` | tool | code | `none` | — | 0 |
| `four-decisions-20261020` | note | other | `none` | — | 0 |
| `generic-sprite-bundle-relocation-20260731` | note | other | `none` | — | 0 |
| `group12-natural-entry-ai-observer-20260806` | note | other | `none` | — | 0 |
| `image_resource_regions` | tool | code | `none` | — | 0 |
| `import_battle_effect_resource_relocations` | tool | code | `none` | — | 0 |
| `import_battle_effect_resources` | tool | code | `none` | — | 0 |
| `import_bg_resource_relocations` | tool | code | `none` | — | 0 |
| `import_bg_resources` | tool | code | `none` | — | 0 |
| `import_character_battle_bundles` | tool | code | `none` | — | 0 |
| `import_character_battle_graphics` | tool | code | `none` | — | 0 |
| `import_character_battle_palettes` | tool | code | `none` | — | 0 |
| `import_character_battle_structures` | tool | code | `none` | — | 0 |
| `import_cutscene_obj_bundle_relocations` | tool | code | `none` | — | 0 |
| `import_direct_image_palette_relocations` | tool | code | `none` | — | 0 |
| `import_generic_sprite_bundle_relocations` | tool | code | `none` | — | 0 |
| `import_map_resource_relocations` | tool | code | `none` | — | 0 |
| `import_map_resources` | tool | code | `none` | — | 0 |
| `import_menu_portrait_relocations` | tool | code | `none` | — | 0 |
| `import_menu_portraits` | tool | code | `none` | — | 0 |
| `import_residual_lz77_graphics_relocations` | tool | code | `none` | — | 0 |
| `import_residual_text_bg_tilemap_relocations` | tool | code | `none` | — | 0 |
| `import_residual_wram_derived_tilemap_relocations` | tool | code | `none` | — | 0 |
| `import_residual_wram_tilemap_relocations` | tool | code | `none` | — | 0 |
| `import_story_visual_resource_relocations` | tool | code | `none` | — | 0 |
| `import_tile_asset_resources` | tool | code | `none` | — | 0 |
| `import_world_map_background_relocations` | tool | code | `none` | — | 0 |
| `initializer-resource-pack-export-20260730` | note | other | `none` | — | 0 |
| `legacy-artifact-acceptance-20260905` | note | other | `none` | — | 0 |
| `legacy_artifact_acceptance_contract` | tool | code | `none` | — | 0 |
| `line-a-progress-20261019` | note | other | `none` | — | 0 |
| `live-ledger-identity-repair-20261020` | note | other | `none` | — | 0 |
| `m4a_pcm` | tool | code | `none` | — | 0 |
| `m4a_psg` | tool | code | `none` | — | 0 |
| `m680x` | tool | code | `none` | — | 0 |
| `m68k` | tool | code | `none` | — | 0 |
| `map-events-e4-player-visible-20260809` | note | map | `none` | — | 0 |
| `map-resource-relocation-20260731` | note | map | `none` | — | 0 |
| `map-resource-writeback-20260730` | note | map | `none` | — | 0 |
| `map-sprites-definition-player-visible-20260809` | note | map | `none` | — | 0 |
| `map41-primary-layout-pixel-ab-20260801` | note | map | `none` | — | 0 |
| `map41-visual-resource-matrix-20260801` | note | map | `none` | — | 0 |
| `menu-portrait-pixel-ab-20260801` | note | presentation | `none` | — | 0 |
| `menu-portrait-relocation-20260731` | note | presentation | `none` | — | 0 |
| `menu-portrait-writeback-20260730` | note | presentation | `none` | — | 0 |
| `mips` | tool | code | `none` | — | 0 |
| `mos65xx` | tool | code | `none` | — | 0 |
| `motion-effect-parameter-player-visible-20260809` | note | other | `none` | — | 0 |
| `note` | note | other | `none` | — | 0 |
| `note` | note | other | `none` | — | 0 |
| `overview-gradient-overlay-export-20260730` | note | overview | `none` | — | 0 |
| `palettes-bank-player-visible-attempt-20260806` | note | other | `none` | — | 0 |
| `plan` | note | other | `none` | — | 0 |
| `portrait-palette-producers-20260730` | note | presentation | `none` | — | 0 |
| `ppc` | tool | code | `none` | — | 0 |
| `profile_coverage_build` | tool | code | `none` | — | 0 |
| `quarantine_legacy_artifacts` | tool | code | `none` | — | 0 |
| `rebuild_battle_effect_frame_phase_artifacts` | tool | code | `none` | — | 0 |
| `rebuild_battle_effect_pixel_ab_artifacts` | tool | code | `none` | — | 0 |
| `rebuild_image_relocation_artifacts` | tool | code | `none` | — | 0 |
| `rebuild_legacy_artifact_acceptance` | tool | code | `none` | — | 0 |
| `render_mode0_checkpoint` | tool | code | `none` | — | 0 |
| `residual-lz77-graphics-relocation-20260731` | note | residual | `none` | — | 0 |
| `residual-text-bg-tilemap-relocation-20260731` | note | residual | `none` | — | 0 |
| `residual-text-bg-tilemap-resource-ownership-20260731` | note | residual | `none` | — | 0 |
| `residual-wram-derived-tilemap-relocation-20260731` | note | residual | `none` | — | 0 |
| `residual-wram-tilemap-abi-20260731` | note | residual | `none` | — | 0 |
| `residual-wram-tilemap-relocation-20260731` | note | residual | `none` | — | 0 |
| `residual-wram-tilemap-resource-ownership-20260731` | note | residual | `none` | — | 0 |
| `residual-wram-tilemap-runtime-reachability-20260731` | note | residual | `none` | — | 0 |
| `residual-wram-transformed-tilemap-runtime-20260801` | note | residual | `none` | — | 0 |
| `resource-pointer-alias-correction-20260730` | note | other | `none` | — | 0 |
| `resource_relocation_build_cli` | tool | code | `none` | — | 0 |
| `reverse-engineering-current-gaps-20260806` | note | other | `none` | — | 0 |
| `reverse-engineering-handoff-20260806` | doc | other | `none` | — | 0 |
| `reverse-engineering-handoff-20260807` | doc | other | `none` | — | 0 |
| `reverse-engineering-handoff-20260812` | doc | other | `none` | — | 0 |
| `reverse-engineering-midterm-report-20260823` | doc | other | `none` | — | 0 |
| `reverse-engineering-progress-snapshot-20260802` | note | other | `none` | — | 0 |
| `reverse-method-review-20261002` | note | other | `none` | — | 0 |
| `riscv` | tool | code | `none` | — | 0 |
| `rom-ai-extra-pool-lifecycle-preflight-20260930` | note | rom | `none` | — | 0 |
| `rom-alternate-dialogue-table-20260902` | note | rom | `none` | — | 0 |
| `rom-animation-base-pairs-preflight-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-callee-effects-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-caller-predecessor-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-critical-writers-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-full-renderer-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-interprocedural-identities-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-irq-arm-native-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-object-lifecycle-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-object-native-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-pool-caller-screen-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-pool-lifecycle-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-save-source-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-upstream-closure-20261001` | note | rom | `none` | — | 0 |
| `rom-animation-writer-domain-20261001` | note | rom | `none` | — | 0 |
| `rom-bank-proof-work-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-bank-proof-work-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-bank-proof-work-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-bank-proof-work-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-bank-runtime-replay-20261001` | note | rom | `none` | — | 0 |
| `rom-bank-runtime-replay-20261001` | note | rom | `none` | — | 0 |
| `rom-battle-condition-result-text-20260902` | note | rom | `none` | — | 0 |
| `rom-battle-distance-dispatcher-cfg-20260902` | note | rom | `none` | — | 0 |
| `rom-battle-effect-fixed-roundtrip-20261001` | note | rom | `none` | — | 0 |
| `rom-battle-effect-fixed-roundtrip-20261001` | note | rom | `none` | — | 0 |
| `rom-boot-interwork-20260811` | note | rom | `none` | — | 0 |
| `rom-boot-interwork-continuation-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-boot-register-init-dependency-cfg-20260905` | note | rom | `none` | — | 0 |
| `rom-bounded-index-u16-pair-table-20260904` | note | rom | `none` | — | 0 |
| `rom-cfg-proven-roots-20260811` | note | rom | `none` | — | 0 |
| `rom-cfg-proven-roots-v13-20260830` | note | rom | `none` | — | 0 |
| `rom-cfg-proven-roots-v14-20260830` | note | rom | `none` | — | 0 |
| `rom-cfg-proven-roots-v15-20260830` | note | rom | `none` | — | 0 |
| `rom-cfg-proven-roots-v17-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-cfg-proven-roots-v18-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-cfg-proven-roots-v2-20260812` | note | rom | `none` | — | 0 |
| `rom-cfg-proven-roots-v20-20260905` | note | rom | `none` | — | 0 |
| `rom-cgb-audio-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-chapter-script-consumer-roots-20260902` | note | rom | `none` | — | 0 |
| `rom-chapter-script-inventory-20260809` | note | rom | `none` | — | 0 |
| `rom-coroutine-record-lifecycle-preflight-20261001` | note | rom | `none` | — | 0 |
| `rom-cutscene-secondary-ptr-ab-20261001` | note | rom | `none` | — | 0 |
| `rom-cutscene-secondary-ptr-ab-20261001` | note | rom | `none` | — | 0 |
| `rom-cutscene-secondary-ptr-contract-20261001` | note | rom | `none` | — | 0 |
| `rom-data-table-b-partial-bank-20261001` | note | rom | `none` | — | 0 |
| `rom-data-table-b-partial-bank-20261001` | note | rom | `none` | — | 0 |
| `rom-direct-cpuset-inventory-survey-20260730` | note | rom | `none` | — | 0 |
| `rom-direct-dma-inventory-survey-20260730` | note | rom | `none` | — | 0 |
| `rom-display-text-delta-tier1-20261001` | note | rom | `none` | — | 0 |
| `rom-display-text-parameter-flow-tdd-20261001` | note | rom | `none` | — | 0 |
| `rom-expansion-character-bundle-relocation-20260731` | note | rom | `none` | — | 0 |
| `rom-fixed-animation-descriptor-groups-20260902` | note | rom | `none` | — | 0 |
| `rom-fixed-consumer-text-inventory-20260811` | note | rom | `none` | — | 0 |
| `rom-fixed-index-u8-tail-20260905` | note | rom | `none` | — | 0 |
| `rom-fixed-pair-tables-20260904` | note | rom | `none` | — | 0 |
| `rom-fixed-text-route-preflight-20261001` | note | rom | `none` | — | 0 |
| `rom-large-unknown-anchor-screen-20261001` | note | rom | `none` | — | 0 |
| `rom-later-cfg-renderer-consumers-preflight-20261001` | note | rom | `none` | — | 0 |
| `rom-low-script-delta-tier1-20261001` | note | rom | `none` | — | 0 |
| `rom-low-script-fixed-consumers-preflight-20261001` | note | rom | `none` | — | 0 |
| `rom-m4a-initializer-chain-20260829` | note | rom | `none` | — | 0 |
| `rom-m4a-initializer-chain-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-map-resource-fixed-roundtrip-20261002` | note | rom | `none` | — | 0 |
| `rom-map-resource-fixed-roundtrip-20261002` | note | rom | `none` | — | 0 |
| `rom-map-sprites-partial-bank-20261001` | note | rom | `none` | — | 0 |
| `rom-map-sprites-partial-bank-20261001` | note | rom | `none` | — | 0 |
| `rom-menu-gfx-pointer-ab-20261001` | note | rom | `none` | — | 0 |
| `rom-menu-portrait-palette-inventory-20260820` | note | rom | `none` | — | 0 |
| `rom-mp2k-dispatcher-20260829` | note | rom | `none` | — | 0 |
| `rom-mp2k-dispatcher-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-mp2k-note-allocator-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-pointer-lz77-inventory-export-20260730` | note | rom | `none` | — | 0 |
| `rom-post-story-dependency-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-prebattle-menu-controller-cfg-20260905` | note | rom | `none` | — | 0 |
| `rom-ram-protocol-tag-preflight-20261001` | note | rom | `none` | — | 0 |
| `rom-referenced-text-slot-padding-20260820` | note | rom | `none` | — | 0 |
| `rom-release-gate-work-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-release-gate-work-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-release-gate-work-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-release-gate-work-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-renderer-batch-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-renderer-excluded-roots-preflight-20260930` | note | rom | `none` | — | 0 |
| `rom-renderer-flow-cost-20261001` | note | rom | `none` | — | 0 |
| `rom-renderer-handler-context-preflight-20260930` | note | rom | `none` | — | 0 |
| `rom-renderer-records-delta-tier1-20261001` | note | rom | `none` | — | 0 |
| `rom-renderer-source-plan-20261001` | note | rom | `none` | — | 0 |
| `rom-renderer-source-replay-20261001` | note | rom | `none` | — | 0 |
| `rom-renderer-text-inventory-20260809` | note | rom | `none` | — | 0 |
| `rom-scene-source-closures-20260905` | note | rom | `none` | — | 0 |
| `rom-scene-source-four-packet-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-scene-visual-source-ranges-20260820` | note | rom | `none` | — | 0 |
| `rom-selector-code-windows-20260820` | note | rom | `none` | — | 0 |
| `rom-selector-direct-source-records-20260820` | note | rom | `none` | — | 0 |
| `rom-selector-text-bindings-20260811` | note | rom | `none` | — | 0 |
| `rom-soundmain-relocated-cfg-20260828` | note | rom | `none` | — | 0 |
| `rom-staged-gpu-copy-inventory-20260730` | note | rom | `none` | — | 0 |
| `rom-story-callback-dependency-closures-20260905` | note | rom | `none` | — | 0 |
| `rom-story-callback-dependency-closures-precoverage-v1` | artifact | rom | `none` | — | 0 |
| `rom-story-next-dependency-cfg-20260905` | note | rom | `none` | — | 0 |
| `rom-story-selector-dependency-cfg-20260905` | note | rom | `none` | — | 0 |
| `rom-task-callback-078e38-closure-20260905` | note | rom | `none` | — | 0 |
| `rom-task-callback-alignment-gap-candidate-20260905` | note | rom | `none` | — | 0 |
| `rom-training-text-script-inventory-20260811` | note | rom | `none` | — | 0 |
| `rom-unknown-cluster-refresh-20260901` | note | rom | `none` | — | 0 |
| `rom-unknown-cluster-refresh-20260905` | note | rom | `none` | — | 0 |
| `rom-v17-v18-helper-cfg-20260904` | note | rom | `none` | — | 0 |
| `rom-value-range-text-inventory-20260811` | note | rom | `none` | — | 0 |
| `rom_boot_interwork_continuation_contract` | tool | code | `none` | — | 0 |
| `rom_boot_register_init_dependency_cfg_contract` | tool | code | `none` | — | 0 |
| `rom_cfg_proven_roots_v14_contract` | tool | code | `none` | — | 0 |
| `rom_cfg_proven_roots_v15_contract` | tool | code | `none` | — | 0 |
| `rom_cfg_proven_roots_v16_contract` | tool | code | `none` | — | 0 |
| `rom_cfg_proven_roots_v17_contract` | tool | code | `none` | — | 0 |
| `rom_cfg_proven_roots_v18_contract` | tool | code | `none` | — | 0 |
| `rom_cfg_proven_roots_v19_contract` | tool | code | `none` | — | 0 |
| `rom_cfg_proven_roots_v20_contract` | tool | code | `none` | — | 0 |
| `rom_cfg_proven_roots_v21_contract` | tool | code | `none` | — | 0 |
| `rom_display_text_parameter_flow` | tool | code | `none` | — | 0 |
| `rom_event_handler_cfg_contract` | tool | code | `none` | — | 0 |
| `rom_fixed_index_u8_tail_contract` | tool | code | `none` | — | 0 |
| `rom_fixed_pair_tables_contract` | tool | code | `none` | — | 0 |
| `rom_layout` | tool | code | `none` | — | 0 |
| `rom_prebattle_menu_controller_cfg_contract` | tool | code | `none` | — | 0 |
| `rom_scene_source_closures_contract` | tool | code | `none` | — | 0 |
| `rom_small_cfg_callback_gaps_producer` | tool | code | `none` | — | 0 |
| `rom_small_cfg_dispatch_decode` | tool | code | `none` | — | 0 |
| `rom_small_cfg_dispatcher_independent_verifier` | tool | code | `none` | — | 0 |
| `rom_small_cfg_dispatcher_producer` | tool | code | `none` | — | 0 |
| `rom_small_cfg_event_gaps_independent_verifier` | tool | code | `none` | — | 0 |
| `rom_small_cfg_event_gaps_producer` | tool | code | `none` | — | 0 |
| `rom_small_cfg_wrappers_independent_verifier` | tool | code | `none` | — | 0 |
| `rom_small_cfg_wrappers_producer` | tool | code | `none` | — | 0 |
| `rom_sprite_component_source_contract` | tool | code | `none` | — | 0 |
| `rom_story_callback_dependency_closures_contract` | tool | code | `none` | — | 0 |
| `rom_story_next_dependency_cfg_contract` | tool | code | `none` | — | 0 |
| `rom_story_selector_dependency_cfg_contract` | tool | code | `none` | — | 0 |
| `rom_task_callback_078e38_contract` | tool | code | `none` | — | 0 |
| `rom_v17_v18_helper_cfg_contract` | tool | code | `none` | — | 0 |
| `run_battle_effect_allocator_reset_batch` | tool | code | `none` | — | 0 |
| `run_battle_effect_controlled_sequence_batch` | tool | code | `none` | — | 0 |
| `run_battle_effect_direct_spawn_batch` | tool | code | `none` | — | 0 |
| `run_battle_effect_phase_batch` | tool | code | `none` | — | 0 |
| `run_controlled_battle_effect_pixel_ab` | tool | code | `none` | — | 0 |
| `run_macos_mgba_battle_ai_action_observer` | tool | code | `none` | — | 0 |
| `run_macos_mgba_battle_effect_phase_capture` | tool | code | `none` | — | 0 |
| `run_macos_mgba_controlled_battle_effect_capture` | tool | code | `none` | — | 0 |
| `run_macos_mgba_group15_natural_branch_trace` | tool | code | `none` | — | 0 |
| `run_macos_mgba_input_sequence` | tool | code | `none` | — | 0 |
| `run_macos_mgba_replay_current` | tool | code | `none` | — | 0 |
| `run_macos_mgba_single_input_current` | tool | code | `none` | — | 0 |
| `run_motion_effect_parameter_pixel_ab` | tool | code | `none` | — | 0 |
| `run_natural_delayed_battle_effect_pixel_ab` | tool | code | `none` | — | 0 |
| `runtime-bg-composites-20260730` | note | runtime | `none` | — | 0 |
| `runtime-checkpoints-data-integrity-issue-20260806` | note | runtime | `none` | — | 0 |
| `runtime-font-tile-provenance-20260730` | note | runtime | `none` | — | 0 |
| `runtime-layer-static-provenance-20260730` | note | runtime | `none` | — | 0 |
| `runtime-mode0-screen-compositor-20260730` | note | runtime | `none` | — | 0 |
| `sappy-engine-master-enable-runtime-20260809` | note | other | `none` | — | 0 |
| `scene-visual-composites-export-20260730` | note | map | `none` | — | 0 |
| `scene-visual-transition-timelines-20260730` | note | map | `none` | — | 0 |
| `sh` | tool | code | `none` | — | 0 |
| `sparc` | tool | code | `none` | — | 0 |
| `staged-artifact-policy-20260905` | note | other | `none` | — | 0 |
| `story-visual-resource-relocation-20260731` | note | presentation | `none` | — | 0 |
| `systemz` | tool | code | `none` | — | 0 |
| `test_analyze_battle_effect_formation_routes` | test | code | `none` | — | 0 |
| `test_analyze_battle_effect_hardcoded_selector_producers` | test | code | `none` | — | 0 |
| `test_analyze_battlefield_object_effect_chain` | test | code | `none` | — | 0 |
| `test_analyze_battlefield_object_producers` | test | code | `none` | — | 0 |
| `test_analyze_rom_renderer_excluded_roots` | test | code | `none` | — | 0 |
| `test_analyze_rom_renderer_handler_graphs` | test | code | `none` | — | 0 |
| `test_audit_reverse_engineering_parallel_verifiers` | test | code | `none` | — | 0 |
| `test_audit_reverse_engineering_proof` | test | code | `none` | — | 0 |
| `test_audit_rom_byte_coverage` | test | code | `none` | — | 0 |
| `test_audit_rom_byte_coverage_atomize_sweep` | test | code | `none` | — | 0 |
| `test_battle_effect_fixed_roundtrip` | test | code | `none` | — | 0 |
| `test_battle_effect_resource_relocation_audit` | test | code | `none` | — | 0 |
| `test_battle_encounters_story_visual_pixel_ab_artifact` | test | code | `none` | — | 0 |
| `test_battle_status_bars_roadmap` | test | code | `none` | — | 0 |
| `test_bg_resource_relocation_audit` | test | code | `none` | — | 0 |
| `test_build_battle_effect_group5_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_battle_effect_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_battle_encounters_story_visual_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_chapter_battle_route_probe` | test | code | `none` | — | 0 |
| `test_build_character_battle_graphics_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_character_battle_visual_resource_matrix` | test | code | `none` | — | 0 |
| `test_build_controlled_battle_effect_allocator_reset_probe` | test | code | `none` | — | 0 |
| `test_build_controlled_battle_effect_direct_spawn_probe` | test | code | `none` | — | 0 |
| `test_build_controlled_battle_effect_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_controlled_battle_effect_sequence_probe` | test | code | `none` | — | 0 |
| `test_build_cutscene_obj_id1_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_cutscene_obj_primary_ptr_ab` | test | code | `none` | — | 0 |
| `test_build_cutscene_obj_secondary_ptr_ab` | test | code | `none` | — | 0 |
| `test_build_map41_primary_layout_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_map41_visual_resource_matrix` | test | code | `none` | — | 0 |
| `test_build_map_events_e4_handler_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_map_sprites_definition_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_menu_portrait_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_menu_portrait_pointer_ab` | test | code | `none` | — | 0 |
| `test_build_motion_effect_parameter_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_natural_delayed_battle_effect_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_residual_wram_tilemap_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_rom_expansion_probe` | test | code | `none` | — | 0 |
| `test_build_sappy_engine_master_enable_ab` | test | code | `none` | — | 0 |
| `test_build_tile_asset_descriptor_pixel_ab` | test | code | `none` | — | 0 |
| `test_build_world_map_page0_pixel_ab` | test | code | `none` | — | 0 |
| `test_character_battle_bundle_relocation_audit` | test | code | `none` | — | 0 |
| `test_character_battle_graphics_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_character_battle_visual_resource_matrix_evidence` | test | code | `none` | — | 0 |
| `test_check_staged_artifact_policy` | test | code | `none` | — | 0 |
| `test_coverage_evidence_selector_repairs` | test | code | `none` | — | 0 |
| `test_cutscene_obj_bundle_relocation_audit` | test | code | `none` | — | 0 |
| `test_cutscene_obj_primary_ptr_ab_artifact` | test | code | `none` | — | 0 |
| `test_cutscene_obj_secondary_ptr_ab` | test | code | `none` | — | 0 |
| `test_cutscene_obj_secondary_ptr_publication` | test | code | `none` | — | 0 |
| `test_data_table_b_message0_pointer_ab_artifact` | test | code | `none` | — | 0 |
| `test_direct_image_palette_relocation_audit` | test | code | `none` | — | 0 |
| `test_disassemble_battle_effect_dispatchers` | test | code | `none` | — | 0 |
| `test_experiment_workspace` | test | code | `none` | — | 0 |
| `test_export_battle_effect_controlled_runtime` | test | code | `none` | — | 0 |
| `test_export_battle_effect_direct_spawn_runtime` | test | code | `none` | — | 0 |
| `test_export_battle_effect_frame_phase` | test | code | `none` | — | 0 |
| `test_export_battle_effect_group15_allocator_side_runtime` | test | code | `none` | — | 0 |
| `test_export_battle_effect_group15_natural_runtime` | test | code | `none` | — | 0 |
| `test_export_battle_effect_group5_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_export_battle_effect_observed_frame_phases` | test | code | `none` | — | 0 |
| `test_export_battle_effect_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_export_battle_effect_runtime_oam_bindings` | test | code | `none` | — | 0 |
| `test_export_battle_effect_runtime_oam_task_bindings` | test | code | `none` | — | 0 |
| `test_export_battle_status_bars` | test | code | `none` | — | 0 |
| `test_export_character_runtime_oam_bindings` | test | code | `none` | — | 0 |
| `test_export_character_runtime_oam_task_bindings` | test | code | `none` | — | 0 |
| `test_export_character_runtime_unit_oam_bindings` | test | code | `none` | — | 0 |
| `test_export_controlled_battle_effect_pixel_ab` | test | code | `none` | — | 0 |
| `test_export_cutscene_obj_id1_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_export_initializer_resource_pack` | test | code | `none` | — | 0 |
| `test_export_menu_portrait_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_export_motion_effect_parameter_pixel_ab` | test | code | `none` | — | 0 |
| `test_export_natural_delayed_battle_effect_pixel_ab` | test | code | `none` | — | 0 |
| `test_export_overview_gradient_overlay` | test | code | `none` | — | 0 |
| `test_export_portrait_palette_producers` | test | code | `none` | — | 0 |
| `test_export_residual_text_bg_tilemap_resource_ownership` | test | code | `none` | — | 0 |
| `test_export_residual_wram_tilemap_abi` | test | code | `none` | — | 0 |
| `test_export_residual_wram_tilemap_resource_ownership` | test | code | `none` | — | 0 |
| `test_export_residual_wram_visual_metadata_abi` | test | code | `none` | — | 0 |
| `test_export_rom_alternate_dialogue_table` | test | code | `none` | — | 0 |
| `test_export_rom_animation_descriptor_pool_v2` | test | code | `none` | — | 0 |
| `test_export_rom_battle_condition_records` | test | code | `none` | — | 0 |
| `test_export_rom_battle_condition_result_text` | test | code | `none` | — | 0 |
| `test_export_rom_battle_controller_consumed_literals` | test | code | `none` | — | 0 |
| `test_export_rom_battle_distance_dispatcher_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_battle_message_text_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_battle_sound_selector` | test | code | `none` | — | 0 |
| `test_export_rom_battle_status_bar_caller_slice` | test | code | `none` | — | 0 |
| `test_export_rom_boot_copy_sources` | test | code | `none` | — | 0 |
| `test_export_rom_boot_framebuffers` | test | code | `none` | — | 0 |
| `test_export_rom_boot_interwork` | test | code | `none` | — | 0 |
| `test_export_rom_boot_interwork_continuation` | test | code | `none` | — | 0 |
| `test_export_rom_boot_register_init_dependency_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_boot_state_dispatcher_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_boot_thumb_handoff_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_bounded_index_u16_pair_table` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_inventory_v3` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_batch_consumed_literals` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v10` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v11` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v12` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v13` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v14` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v15` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v16` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v16_consumed_literals` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v17` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v18` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v19` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v2` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v20` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v21` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v3` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v4` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v5` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v6` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v7` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v8` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_proven_roots_v9` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_seeds` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_v1_consumed_literals` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_v2_consumed_literals` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_v2_shadowed_consumed_literals` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_v3_consumed_literals` | test | code | `none` | — | 0 |
| `test_export_rom_cfg_v6_consumed_literals` | test | code | `none` | — | 0 |
| `test_export_rom_cgb_helper_bounded_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_cgbsound_bounded_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_chapter_script_consumer_roots` | test | code | `none` | — | 0 |
| `test_export_rom_chapter_script_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_chapter_selector_code_slice` | test | code | `none` | — | 0 |
| `test_export_rom_cutscene_obj_source_ranges` | test | code | `none` | — | 0 |
| `test_export_rom_dialogue_padding_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_dialogue_text_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_direct_cpuset_gpu_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_direct_dma_gpu_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_directsound_pitch_lookup` | test | code | `none` | — | 0 |
| `test_export_rom_event_handler_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_fixed_animation_descriptor_groups` | test | code | `none` | — | 0 |
| `test_export_rom_fixed_consumer_text_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_fixed_index_u8_tail` | test | code | `none` | — | 0 |
| `test_export_rom_fixed_pair_tables` | test | code | `none` | — | 0 |
| `test_export_rom_fixed_renderer_script_records` | test | code | `none` | — | 0 |
| `test_export_rom_gpu_copy_queue_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_m4a_initializer_chain` | test | code | `none` | — | 0 |
| `test_export_rom_menu_portrait_palette_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_mp2k_dispatcher` | test | code | `none` | — | 0 |
| `test_export_rom_mp2k_note_allocator` | test | code | `none` | — | 0 |
| `test_export_rom_mplaymain_scheduler` | test | code | `none` | — | 0 |
| `test_export_rom_parser_bound_zero_padding` | test | code | `none` | — | 0 |
| `test_export_rom_pointer_lz77_graphics` | test | code | `none` | — | 0 |
| `test_export_rom_pointer_lz77_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_positions_aux_dispatch` | test | code | `none` | — | 0 |
| `test_export_rom_post_story_dependency_precoverage` | test | code | `none` | — | 0 |
| `test_export_rom_prebattle_menu_controller_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_profile_selector_code_slices` | test | code | `none` | — | 0 |
| `test_export_rom_profile_text_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_psg_frequency_lookup` | test | code | `none` | — | 0 |
| `test_export_rom_referenced_text_slot_padding` | test | code | `none` | — | 0 |
| `test_export_rom_renderer_script_pointer_pool_records` | test | code | `none` | — | 0 |
| `test_export_rom_renderer_text_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_scene_source_closures` | test | code | `none` | — | 0 |
| `test_export_rom_scene_source_four_packet_precoverage` | test | code | `none` | — | 0 |
| `test_export_rom_scene_visual_source_ranges` | test | code | `none` | — | 0 |
| `test_export_rom_selector_code_windows` | test | code | `none` | — | 0 |
| `test_export_rom_selector_direct_source_records` | test | code | `none` | — | 0 |
| `test_export_rom_selector_text_bindings` | test | code | `none` | — | 0 |
| `test_export_rom_soundmain_relocated_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_sprite_component_source` | test | code | `none` | — | 0 |
| `test_export_rom_sprite_loader_tail` | test | code | `none` | — | 0 |
| `test_export_rom_staged_gpu_copy_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_story_callback_dependency_closures` | test | code | `none` | — | 0 |
| `test_export_rom_story_callback_dependency_precoverage` | test | code | `none` | — | 0 |
| `test_export_rom_story_next_dependency_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_story_selector_dependency_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_story_state_callback_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_story_state_entry_c4cc` | test | code | `none` | — | 0 |
| `test_export_rom_task_callback_078e38_closure` | test | code | `none` | — | 0 |
| `test_export_rom_task_scheduler_core` | test | code | `none` | — | 0 |
| `test_export_rom_text_bg_loop_continuation` | test | code | `none` | — | 0 |
| `test_export_rom_text_bg_task_closure` | test | code | `none` | — | 0 |
| `test_export_rom_training_text_script_inventory` | test | code | `none` | — | 0 |
| `test_export_rom_u8_indexed_u16_pair_lookup` | test | code | `none` | — | 0 |
| `test_export_rom_u8_indexed_u8_triplet_lookup` | test | code | `none` | — | 0 |
| `test_export_rom_unbound_chapter_script_tail` | test | code | `none` | — | 0 |
| `test_export_rom_v17_v18_helper_cfg` | test | code | `none` | — | 0 |
| `test_export_rom_value_range_text_inventory` | test | code | `none` | — | 0 |
| `test_export_runtime_bg_composites` | test | code | `none` | — | 0 |
| `test_export_runtime_font_tile_provenance` | test | code | `none` | — | 0 |
| `test_export_runtime_layer_static_provenance` | test | code | `none` | — | 0 |
| `test_export_runtime_screen_composites` | test | code | `none` | — | 0 |
| `test_export_scene_visual_composites` | test | code | `none` | — | 0 |
| `test_export_scene_visual_transition_timelines` | test | code | `none` | — | 0 |
| `test_export_story_visual_resource_sources` | test | code | `none` | — | 0 |
| `test_export_world_map_page0_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_find_battlefield_object_effect_seeds` | test | code | `none` | — | 0 |
| `test_find_similar_tables` | test | code | `none` | — | 0 |
| `test_generic_sprite_bundle_relocation_audit` | test | code | `none` | — | 0 |
| `test_image_resource_regions` | test | code | `none` | — | 0 |
| `test_import_battle_effect_resource_relocations` | test | code | `none` | — | 0 |
| `test_import_battle_effect_resources` | test | code | `none` | — | 0 |
| `test_import_bg_resource_relocations` | test | code | `none` | — | 0 |
| `test_import_bg_resources` | test | code | `none` | — | 0 |
| `test_import_character_battle_bundles` | test | code | `none` | — | 0 |
| `test_import_character_battle_graphics` | test | code | `none` | — | 0 |
| `test_import_character_battle_palettes` | test | code | `none` | — | 0 |
| `test_import_character_battle_structures` | test | code | `none` | — | 0 |
| `test_import_cutscene_obj_bundle_relocations` | test | code | `none` | — | 0 |
| `test_import_direct_image_palette_relocations` | test | code | `none` | — | 0 |
| `test_import_generic_sprite_bundle_relocations` | test | code | `none` | — | 0 |
| `test_import_map_resource_relocations` | test | code | `none` | — | 0 |
| `test_import_map_resources` | test | code | `none` | — | 0 |
| `test_import_menu_portrait_relocations` | test | code | `none` | — | 0 |
| `test_import_menu_portraits` | test | code | `none` | — | 0 |
| `test_import_residual_lz77_graphics_relocations` | test | code | `none` | — | 0 |
| `test_import_residual_text_bg_tilemap_relocations` | test | code | `none` | — | 0 |
| `test_import_residual_wram_derived_tilemap_relocations` | test | code | `none` | — | 0 |
| `test_import_residual_wram_tilemap_relocations` | test | code | `none` | — | 0 |
| `test_import_story_visual_resource_relocations` | test | code | `none` | — | 0 |
| `test_import_tile_asset_resources` | test | code | `none` | — | 0 |
| `test_import_world_map_background_relocations` | test | code | `none` | — | 0 |
| `test_levels_status_per_level_ab_artifact` | test | code | `none` | — | 0 |
| `test_map41_primary_layout_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_map41_visual_resource_matrix_evidence` | test | code | `none` | — | 0 |
| `test_map_events_e4_handler_pixel_ab_artifact` | test | code | `none` | — | 0 |
| `test_map_resource_fixed_roundtrip` | test | code | `none` | — | 0 |
| `test_map_resource_relocation_audit` | test | code | `none` | — | 0 |
| `test_map_resource_relocation_roundtrip` | test | code | `none` | — | 0 |
| `test_map_sprites_definition_pixel_ab_artifact` | test | code | `none` | — | 0 |
| `test_map_sprites_partial_bank` | test | code | `none` | — | 0 |
| `test_maps_partial_bank` | test | code | `none` | — | 0 |
| `test_measure_reverse_throughput` | test | code | `none` | — | 0 |
| `test_menu_portrait_pointer_ab` | test | code | `none` | — | 0 |
| `test_menu_portrait_pointer_publication` | test | code | `none` | — | 0 |
| `test_menu_portrait_relocation_audit` | test | code | `none` | — | 0 |
| `test_mgba_battle_ai_action_observer_script` | test | code | `none` | — | 0 |
| `test_mgba_battle_effect_dispatcher_tracer` | test | code | `none` | — | 0 |
| `test_mgba_battle_effect_phase_capture_script` | test | code | `none` | — | 0 |
| `test_mgba_battle_encounters_story_visual_trace_script` | test | code | `none` | — | 0 |
| `test_mgba_controlled_battle_effect_capture_script` | test | code | `none` | — | 0 |
| `test_mgba_group15_natural_branch_trace_script` | test | code | `none` | — | 0 |
| `test_mgba_lz77_palette_probe_script` | test | code | `none` | — | 0 |
| `test_mgba_map_events_e4_trace_script` | test | code | `none` | — | 0 |
| `test_mgba_map_sprites_trace_script` | test | code | `none` | — | 0 |
| `test_mgba_palette_producer_probe_script` | test | code | `none` | — | 0 |
| `test_mgba_rom_expansion_restore_script` | test | code | `none` | — | 0 |
| `test_mgba_sappy_engine_master_enable_trace_script` | test | code | `none` | — | 0 |
| `test_mgba_tile_asset_initializer_trace_script` | test | code | `none` | — | 0 |
| `test_mgba_wram_crop_tilemap_probe_script` | test | code | `none` | — | 0 |
| `test_mgba_wram_tilemap_probe_script` | test | code | `none` | — | 0 |
| `test_mgba_wram_tilemap_sequence_probe_script` | test | code | `none` | — | 0 |
| `test_mgba_wram_tilemap_single_input_probe_script` | test | code | `none` | — | 0 |
| `test_python_version_gate` | test | code | `none` | — | 0 |
| `test_quarantine_legacy_artifacts` | test | code | `none` | — | 0 |
| `test_rebuild_battle_effect_frame_phase_artifacts` | test | code | `none` | — | 0 |
| `test_rebuild_battle_effect_pixel_ab_artifacts` | test | code | `none` | — | 0 |
| `test_rebuild_image_relocation_artifacts` | test | code | `none` | — | 0 |
| `test_rebuild_legacy_artifact_acceptance` | test | code | `none` | — | 0 |
| `test_render_mode0_checkpoint` | test | code | `none` | — | 0 |
| `test_residual_lz77_graphics_relocation_audit` | test | code | `none` | — | 0 |
| `test_residual_text_bg_tilemap_relocation_audit` | test | code | `none` | — | 0 |
| `test_residual_wram_crop_tilemap_runtime_evidence` | test | code | `none` | — | 0 |
| `test_residual_wram_derived_tilemap_relocation_audit` | test | code | `none` | — | 0 |
| `test_residual_wram_tilemap_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_residual_wram_tilemap_relocation_audit` | test | code | `none` | — | 0 |
| `test_residual_wram_tilemap_runtime_evidence` | test | code | `none` | — | 0 |
| `test_residual_wram_tilemap_runtime_v2` | test | code | `none` | — | 0 |
| `test_residual_wram_transformed_tilemap_runtime_evidence` | test | code | `none` | — | 0 |
| `test_rom_cfg_proven_roots_v21_coverage` | test | code | `none` | — | 0 |
| `test_rom_display_text_delta` | test | code | `none` | — | 0 |
| `test_rom_display_text_parameter_flow` | test | code | `none` | — | 0 |
| `test_rom_layout` | test | code | `none` | — | 0 |
| `test_rom_low_script_delta` | test | code | `none` | — | 0 |
| `test_rom_m4a_byte_inventory` | test | code | `none` | — | 0 |
| `test_rom_renderer_records_delta` | test | code | `none` | — | 0 |
| `test_rom_renderer_script_pointer_pool_canonical` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_batch_canonical` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_batch_coverage` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_batch_publication` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_callback_gaps_independent_verifier` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_callback_gaps_parent_boundary_gates` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_callback_gaps_producer` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_dependency_packets` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_dispatcher_dispatch_decode` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_dispatcher_parent_packet` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_event_gaps_packet` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_wrappers_independent_verifier` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_wrappers_parent_decoder` | test | code | `none` | — | 0 |
| `test_rom_small_cfg_wrappers_producer` | test | code | `none` | — | 0 |
| `test_rom_unbound_lz77_inventory` | test | code | `none` | — | 0 |
| `test_run_battle_effect_allocator_reset_batch` | test | code | `none` | — | 0 |
| `test_run_battle_effect_controlled_sequence_batch` | test | code | `none` | — | 0 |
| `test_run_battle_effect_direct_spawn_batch` | test | code | `none` | — | 0 |
| `test_run_battle_effect_phase_batch` | test | code | `none` | — | 0 |
| `test_run_controlled_battle_effect_pixel_ab` | test | code | `none` | — | 0 |
| `test_run_macos_mgba_battle_ai_action_observer` | test | code | `none` | — | 0 |
| `test_run_macos_mgba_battle_effect_phase_capture` | test | code | `none` | — | 0 |
| `test_run_macos_mgba_controlled_battle_effect_capture` | test | code | `none` | — | 0 |
| `test_run_macos_mgba_group15_natural_branch_trace` | test | code | `none` | — | 0 |
| `test_run_macos_mgba_input_sequence` | test | code | `none` | — | 0 |
| `test_run_macos_mgba_replay_current` | test | code | `none` | — | 0 |
| `test_run_macos_mgba_single_input_current` | test | code | `none` | — | 0 |
| `test_run_motion_effect_parameter_pixel_ab` | test | code | `none` | — | 0 |
| `test_run_natural_delayed_battle_effect_pixel_ab` | test | code | `none` | — | 0 |
| `test_sappy_engine_master_enable_ab_artifact` | test | code | `none` | — | 0 |
| `test_scenario47_tool67_equipment_persistence` | test | code | `none` | — | 0 |
| `test_scenario49_battle14_tool67_entry_persistence` | test | code | `none` | — | 0 |
| `test_scenario49_tool37_confirmation_persistence` | test | code | `none` | — | 0 |
| `test_scenario49_tool37_group17_persistence` | test | code | `none` | — | 0 |
| `test_scenario49_tool67_active_object_persistence` | test | code | `none` | — | 0 |
| `test_scenario49_tool67_confirmation_persistence` | test | code | `none` | — | 0 |
| `test_scenario49_tool67_expiry_ready_persistence` | test | code | `none` | — | 0 |
| `test_staged_legacy_artifact_acceptance` | test | code | `none` | — | 0 |
| `test_story_visual_resource_relocation_audit` | test | code | `none` | — | 0 |
| `test_tile_asset_descriptor_pixel_ab_artifact` | test | code | `none` | — | 0 |
| `test_tile_asset_resource_relocation_audit` | test | code | `none` | — | 0 |
| `test_verification_cache` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_controlled_runtime` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_direct_spawn_runtime` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_formation_routes` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_frame_phase` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_group15_allocator_side_runtime` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_group15_natural_runtime` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_group5_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_natural_checkpoint` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_observed_frame_phases` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_runtime_oam_bindings` | test | code | `none` | — | 0 |
| `test_verify_battle_effect_runtime_oam_task_bindings` | test | code | `none` | — | 0 |
| `test_verify_battle_presentation_rom_ranges` | test | code | `none` | — | 0 |
| `test_verify_battle_presentation_text_padding` | test | code | `none` | — | 0 |
| `test_verify_battlefield_object_effect_chain` | test | code | `none` | — | 0 |
| `test_verify_battlefield_object_producers` | test | code | `none` | — | 0 |
| `test_verify_controlled_battle_effect_pixel_ab` | test | code | `none` | — | 0 |
| `test_verify_cutscene_obj_id1_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_verify_dialogue_font_source_padding` | test | code | `none` | — | 0 |
| `test_verify_disproved_bank_candidates` | test | code | `none` | — | 0 |
| `test_verify_legacy_artifact_acceptance` | test | code | `none` | — | 0 |
| `test_verify_lz77_palette_runtime` | test | code | `none` | — | 0 |
| `test_verify_menu_portrait_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_verify_motion_effect_parameter_pixel_ab` | test | code | `none` | — | 0 |
| `test_verify_natural_delayed_battle_effect_pixel_ab` | test | code | `none` | — | 0 |
| `test_verify_rom_artifact_bound_alignment_gaps` | test | code | `none` | — | 0 |
| `test_verify_rom_battle_controller_cfg` | test | code | `none` | — | 0 |
| `test_verify_rom_battle_controller_consumed_literals` | test | code | `none` | — | 0 |
| `test_verify_rom_battle_status_bar_caller_slice` | test | code | `none` | — | 0 |
| `test_verify_rom_boot_interwork_continuation` | test | code | `none` | — | 0 |
| `test_verify_rom_boot_thumb_code_literal_alignment_gaps` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_batch_consumed_literals` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v12` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v12_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v13` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v13_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v14` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v14_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v15` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v15_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v16` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v16_consumed_literals` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v17` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_proven_roots_v18` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_v1_consumed_literals` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_v2_consumed_literals` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_v2_shadowed_consumed_literals` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_v3_consumed_literals` | test | code | `none` | — | 0 |
| `test_verify_rom_cfg_v6_consumed_literals` | test | code | `none` | — | 0 |
| `test_verify_rom_cgb_bounded_cfg_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_cgb_helper_bounded_cfg` | test | code | `none` | — | 0 |
| `test_verify_rom_cgbsound_bounded_cfg` | test | code | `none` | — | 0 |
| `test_verify_rom_chapter_selector_code_slice` | test | code | `none` | — | 0 |
| `test_verify_rom_cutscene_obj_palette_definition_alignment_gaps` | test | code | `none` | — | 0 |
| `test_verify_rom_directsound_pitch_lookup` | test | code | `none` | — | 0 |
| `test_verify_rom_directsound_pitch_lookup_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_event_handler_cfg` | test | code | `none` | — | 0 |
| `test_verify_rom_expansion_profile` | test | code | `none` | — | 0 |
| `test_verify_rom_fast_audit_four_packet_coverage` | test | code | `none` | — | 0 |
| `test_verify_rom_fixed_consumer_text_padding` | test | code | `none` | — | 0 |
| `test_verify_rom_lz77_alignment_padding` | test | code | `none` | — | 0 |
| `test_verify_rom_m4a_initializer_chain` | test | code | `none` | — | 0 |
| `test_verify_rom_menu_portrait_lz77_palette_alignment_gaps` | test | code | `none` | — | 0 |
| `test_verify_rom_mp2k_dispatcher` | test | code | `none` | — | 0 |
| `test_verify_rom_mp2k_note_allocator` | test | code | `none` | — | 0 |
| `test_verify_rom_mplaymain_scheduler_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_profile_selector_code_slices` | test | code | `none` | — | 0 |
| `test_verify_rom_psg_frequency_lookup` | test | code | `none` | — | 0 |
| `test_verify_rom_psg_frequency_lookup_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_renderer_text_padding` | test | code | `none` | — | 0 |
| `test_verify_rom_scheduler_callback_lifecycle_gate` | test | code | `none` | — | 0 |
| `test_verify_rom_soundmain_relocated_alignment_gaps` | test | code | `none` | — | 0 |
| `test_verify_rom_soundmain_relocated_cfg` | test | code | `none` | — | 0 |
| `test_verify_rom_soundmain_relocated_cfg_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_sprite_component_source` | test | code | `none` | — | 0 |
| `test_verify_rom_sprite_loader_tail` | test | code | `none` | — | 0 |
| `test_verify_rom_task_scheduler_core_bundle` | test | code | `none` | — | 0 |
| `test_verify_rom_tile_bg_lz77_palette_alignment_gaps` | test | code | `none` | — | 0 |
| `test_verify_rom_u8_indexed_u8_triplet_lookup` | test | code | `none` | — | 0 |
| `test_verify_rom_u8_indexed_u8_triplet_lookup_bundle` | test | code | `none` | — | 0 |
| `test_verify_runtime_checkpoint_containers` | test | code | `none` | — | 0 |
| `test_verify_similar_table_candidates` | test | code | `none` | — | 0 |
| `test_verify_world_map_page0_pixel_ab_evidence` | test | code | `none` | — | 0 |
| `test_vram_lz77_encoder_safety` | test | code | `none` | — | 0 |
| `test_vram_safe_fixed_slot_audits` | test | code | `none` | — | 0 |
| `test_world_map_background_relocation_audit` | test | code | `none` | — | 0 |
| `throughput` | note | other | `none` | — | 0 |
| `tier2-threshold-policy-source-20261020` | note | other | `none` | — | 0 |
| `tile-asset-resource-relocation-20260731` | note | visual | `none` | — | 0 |
| `tile-assets-descriptor-player-visible-20260809` | note | visual | `none` | — | 0 |
| `tricore` | tool | code | `none` | — | 0 |
| `unresolved-lz77-palette-survey-20260730` | note | other | `none` | — | 0 |
| `verification_cache` | tool | code | `none` | — | 0 |
| `verify_battle_effect_controlled_runtime` | tool | code | `none` | — | 0 |
| `verify_battle_effect_direct_spawn_runtime` | tool | code | `none` | — | 0 |
| `verify_battle_effect_formation_routes` | tool | code | `none` | — | 0 |
| `verify_battle_effect_frame_phase` | tool | code | `none` | — | 0 |
| `verify_battle_effect_group15_allocator_side_runtime` | tool | code | `none` | — | 0 |
| `verify_battle_effect_group15_natural_runtime` | tool | code | `none` | — | 0 |
| `verify_battle_effect_group5_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `verify_battle_effect_natural_checkpoint` | tool | code | `none` | — | 0 |
| `verify_battle_effect_observed_frame_phases` | tool | code | `none` | — | 0 |
| `verify_battle_effect_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `verify_battle_effect_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_battle_effect_runtime_oam_bindings` | tool | code | `none` | — | 0 |
| `verify_battle_effect_runtime_oam_task_bindings` | tool | code | `none` | — | 0 |
| `verify_battle_status_bars` | tool | code | `none` | — | 0 |
| `verify_battlefield_object_effect_chain` | tool | code | `none` | — | 0 |
| `verify_battlefield_object_producers` | tool | code | `none` | — | 0 |
| `verify_bg_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_character_battle_bundle_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_character_battle_graphics_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `verify_character_battle_visual_resource_matrix_evidence` | tool | code | `none` | — | 0 |
| `verify_character_runtime_oam_bindings` | tool | code | `none` | — | 0 |
| `verify_character_runtime_oam_task_bindings` | tool | code | `none` | — | 0 |
| `verify_character_runtime_unit_oam_bindings` | tool | code | `none` | — | 0 |
| `verify_controlled_battle_effect_pixel_ab` | tool | code | `none` | — | 0 |
| `verify_cutscene_obj_bundle_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_cutscene_obj_id1_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `verify_cutscene_obj_secondary_ptr_ab` | tool | code | `none` | — | 0 |
| `verify_direct_image_palette_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_generic_sprite_bundle_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_initializer_resource_pack` | tool | code | `none` | — | 0 |
| `verify_legacy_artifact_acceptance` | tool | code | `none` | — | 0 |
| `verify_levels_status_per_level_ab` | tool | code | `none` | — | 0 |
| `verify_lz77_palette_runtime` | tool | code | `none` | — | 0 |
| `verify_map41_visual_resource_matrix_evidence` | tool | code | `none` | — | 0 |
| `verify_map_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_map_sprites_partial_bank` | tool | code | `none` | — | 0 |
| `verify_maps_partial_bank` | tool | code | `none` | — | 0 |
| `verify_menu_portrait_pointer_ab` | tool | code | `none` | — | 0 |
| `verify_menu_portrait_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_mgba_renderer_source` | tool | code | `none` | — | 0 |
| `verify_natural_delayed_battle_effect_pixel_ab` | tool | code | `none` | — | 0 |
| `verify_residual_lz77_graphics_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_residual_text_bg_tilemap_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_residual_text_bg_tilemap_resource_ownership` | tool | code | `none` | — | 0 |
| `verify_residual_wram_crop_tilemap_runtime_evidence` | tool | code | `none` | — | 0 |
| `verify_residual_wram_derived_tilemap_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_residual_wram_tilemap_abi` | tool | code | `none` | — | 0 |
| `verify_residual_wram_tilemap_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `verify_residual_wram_tilemap_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_residual_wram_tilemap_resource_ownership` | tool | code | `none` | — | 0 |
| `verify_residual_wram_tilemap_runtime_evidence` | tool | code | `none` | — | 0 |
| `verify_residual_wram_tilemap_runtime_v2` | tool | code | `none` | — | 0 |
| `verify_residual_wram_transformed_tilemap_runtime_evidence` | tool | code | `none` | — | 0 |
| `verify_rom_alternate_dialogue_table` | tool | code | `none` | — | 0 |
| `verify_rom_animation_descriptor_pool_v2` | tool | code | `none` | — | 0 |
| `verify_rom_battle_condition_result_text` | tool | code | `none` | — | 0 |
| `verify_rom_battle_distance_dispatcher_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_boot_copy_sources` | tool | code | `none` | — | 0 |
| `verify_rom_boot_interwork_continuation` | tool | code | `none` | — | 0 |
| `verify_rom_boot_register_init_dependency_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_boot_state_dispatcher_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_bounded_index_u16_pair_table` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v12` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v13` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v14` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v15` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v16` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v16_consumed_literals` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v17` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v18` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v19` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v20` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_proven_roots_v21` | tool | code | `none` | — | 0 |
| `verify_rom_cfg_seeds` | tool | code | `none` | — | 0 |
| `verify_rom_cgb_helper_bounded_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_chapter_script_consumer_roots` | tool | code | `none` | — | 0 |
| `verify_rom_direct_dma_gpu_inventory` | tool | code | `none` | — | 0 |
| `verify_rom_directsound_pitch_lookup` | tool | code | `none` | — | 0 |
| `verify_rom_display_text_delta` | tool | code | `none` | — | 0 |
| `verify_rom_event_handler_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_expansion_profile` | tool | code | `none` | — | 0 |
| `verify_rom_fast_audit_four_packet_coverage` | tool | code | `none` | — | 0 |
| `verify_rom_fixed_animation_descriptor_groups` | tool | code | `none` | — | 0 |
| `verify_rom_fixed_index_u8_tail` | tool | code | `none` | — | 0 |
| `verify_rom_fixed_pair_tables` | tool | code | `none` | — | 0 |
| `verify_rom_low_script_delta` | tool | code | `none` | — | 0 |
| `verify_rom_mplaymain_scheduler` | tool | code | `none` | — | 0 |
| `verify_rom_pointer_lz77_graphics` | tool | code | `none` | — | 0 |
| `verify_rom_prebattle_menu_controller_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_psg_frequency_lookup` | tool | code | `none` | — | 0 |
| `verify_rom_renderer_records_delta` | tool | code | `none` | — | 0 |
| `verify_rom_renderer_script_pointer_pool_records` | tool | code | `none` | — | 0 |
| `verify_rom_scene_source_closures` | tool | code | `none` | — | 0 |
| `verify_rom_soundmain_relocated_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_sprite_component_source` | tool | code | `none` | — | 0 |
| `verify_rom_staged_gpu_copy_inventory` | tool | code | `none` | — | 0 |
| `verify_rom_story_callback_dependency_closures` | tool | code | `none` | — | 0 |
| `verify_rom_story_next_dependency_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_story_selector_dependency_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_story_state_callback_cfg` | tool | code | `none` | — | 0 |
| `verify_rom_story_state_entry_c4cc` | tool | code | `none` | — | 0 |
| `verify_rom_task_callback_078e38_closure` | tool | code | `none` | — | 0 |
| `verify_rom_task_scheduler_core` | tool | code | `none` | — | 0 |
| `verify_rom_text_bg_loop_continuation` | tool | code | `none` | — | 0 |
| `verify_rom_text_bg_task_closure` | tool | code | `none` | — | 0 |
| `verify_rom_u8_indexed_u8_triplet_lookup` | tool | code | `none` | — | 0 |
| `verify_rom_unbound_chapter_script_tail` | tool | code | `none` | — | 0 |
| `verify_rom_v17_v18_helper_cfg` | tool | code | `none` | — | 0 |
| `verify_runtime_bg_composites` | tool | code | `none` | — | 0 |
| `verify_runtime_checkpoint_containers` | tool | code | `none` | — | 0 |
| `verify_runtime_font_tile_provenance` | tool | code | `none` | — | 0 |
| `verify_runtime_layer_static_provenance` | tool | code | `none` | — | 0 |
| `verify_runtime_screen_composites` | tool | code | `none` | — | 0 |
| `verify_sappy_engine_master_enable_ab` | tool | code | `none` | — | 0 |
| `verify_scene_visual_transition_timelines` | tool | code | `none` | — | 0 |
| `verify_story_visual_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_tile_asset_resource_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_world_map_background_relocation_audit` | tool | code | `none` | — | 0 |
| `verify_world_map_page0_pixel_ab_evidence` | tool | code | `none` | — | 0 |
| `vram-safe-lz77-runtime-20260801` | note | other | `none` | — | 0 |
| `wasm` | tool | code | `none` | — | 0 |
| `windows-porting-20261020` | note | other | `none` | — | 0 |
| `world-map-background-relocation-20260731` | note | map | `none` | — | 0 |
| `world-map-page0-pixel-ab-20260801` | note | map | `none` | — | 0 |
| `x86` | tool | code | `none` | — | 0 |
| `xcore` | tool | code | `none` | — | 0 |
| `三包接入施工单-raw` | note | other | `none` | — | 0 |
