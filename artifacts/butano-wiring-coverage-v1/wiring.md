# 接线覆盖矩阵（自动生成）

本文件由 `tools/measure_butano_wiring_coverage.py` 生成，不要手工编辑。

**接线点 = （逆向族, 复刻产物）二元组。** 两端都要枚举，缺一端就查不全。

## 口径

- **wired**：a declared product binds the family
- **gated**：a test file names the product -- an UPPER BOUND, not a verdict
- **shelf**：accepted, carries a payload, bound to no product
- **not_importable**：no importable payload: control-flow / coverage analysis
- **wired_mentioned**：the build chain names the family but NO product declares it -- the gap tool's lower bound, not a proven lineage
- **imported**：the family is pinned by manifest SHA-256 in a ROM importer and its files are copied into this tree -- a declared wire through the importer's own carrier
- **verified_against**：the family is only read as evidence by a verifier; the remake does not consume its payload
- **local_derivation**：a remake-side tool uses the family name as a schema tag and writes this tree's own artifacts/<family>/ -- the state says whether that copy is present and whether it still matches the reverse tree's original
- **no_material**：neither declared, nor mentioned by the build chain, nor carrying importable payload
- **sink_declared**：product is in a generator's GENERATED_PRODUCTS and carries a declaration
- **sink_undeclared**：remake source or data that no generator claims and that carries no declaration

## source 侧（逆向族）

| 状态 | 族数 |
| --- | ---: |
| `imported-and-gated` | 54 |
| `local-derivation-missing` | 26 |
| `no-material` | 37 |
| `not-importable` | 51 |
| `on-shelf` | 71 |
| `unclassified` | 12 |
| `verified-against` | 1 |
| `wired-and-gated` | 12 |

## sink 侧（复刻产物）

| 状态 | 产物数 |
| --- | ---: |
| `declared`（绑定了族） | 24 |
| `declared-not-applicable`（声明了「不消费逆向结果」+ 理由） | 14 |

### 未登记的 sink 面（**没有接线声明**的部分）

| 面 | 数量 | 有载体吗 |
| --- | ---: | --- |
| 生成器产物（generated header） | 27 | ✅ 已登记 |
| 手写头（`konoha/*.h`，非 generated） | 110 | ❌ 无载体 |
| 内容库（`sequel/content/*/bank.json`） | 34 | ❌ 无载体 |
| 图形资产（`butano-sequel/graphics/`） | 1819 | ❌ 无载体 |
| 运行时源码（`game/src/*.cpp`） | 4 | ❌ 无载体 |
| 门禁（`tests/test_*.py`） | 373 | — |

## 未接线的族（on-shelf，按类别）

| 类别 | 族数 | 族 |
| --- | ---: | --- |
| battle | 1 | `battle-status-bars-v1` |
| map | 3 | `map41-visual-resource-matrix-v1`, `scene-visual-composites-v1`, `scene-visual-transition-timelines-v1` |
| other | 4 | `initializer-resource-pack-v1`, `levels-status-per-level-ab-v1`, `lz77-palette-runtime-v1`, `sappy-engine-master-enable-ab-v1` |
| overview | 1 | `overview-gradient-overlay-v1` |
| presentation | 3 | `cutscene-obj-id1-primary-ptr-ab-v1`, `portrait-palette-producers-v1`, `story-visual-resource-sources-v1` |
| residual | 8 | `residual-text-bg-tilemap-resource-ownership-v1`, `residual-wram-crop-tilemap-runtime-v1`, `residual-wram-tilemap-abi-v1`, `residual-wram-tilemap-resource-ownership-v1`, `residual-wram-tilemap-runtime-v1`, `residual-wram-tilemap-runtime-v2`, `residual-wram-transformed-tilemap-runtime-v1`, `residual-wram-visual-metadata-abi-v2` |
| rom | 29 | `rom-alternate-dialogue-table-v1`, `rom-animation-descriptor-pool-v2`, `rom-battle-sound-selector-v1`, `rom-boot-copy-sources-v1`, `rom-bounded-index-u16-pair-table-v1`, `rom-cfg-proven-roots-v14`, `rom-cutscene-obj-source-ranges-v1`, `rom-dialogue-text-inventory-v1`, `rom-direct-cpuset-gpu-inventory-v1`, `rom-direct-dma-gpu-inventory-v1`, `rom-directsound-pitch-lookup-v1`, `rom-display-text-delta-v1` … |
| runtime | 4 | `runtime-bg-composites-v1`, `runtime-font-tile-provenance-v1`, `runtime-layer-static-provenance-v1`, `runtime-screen-composites-v1` |
| visual | 18 | `battle-effect-frame-phase-group1-v1`, `battle-effect-frame-phase-group14-v1`, `battle-effect-frame-phase-group16-natural-v1`, `battle-effect-frame-phase-group17-natural-v1`, `battle-effect-frame-phase-group18-natural-sequence-v1`, `battle-effect-frame-phase-group2-v1`, `battle-effect-frame-phase-group3-natural-v1`, `battle-effect-frame-phase-group4-natural-v1`, `battle-effect-frame-phase-group5-v1`, `battle-effect-frame-phase-v1`, `battle-effect-group12-ai-observer-v1`, `battle-effect-group13-natural-runtime-v1` … |

## 已接线但无门禁的族

共 **0** 族（线在，但没有测试提到它的产物）：


## 边界声明

- 「有门禁」是**上界**：测试提到产物路径可能是文档类测试，不等于行为门禁。
- sink 侧的未登记面**只是盘点**，不是缺陷判定——手写头与内容库本来就不消费逆向族 payload。
- 本工具不判定「该接哪个族」：那是按子系统的设计决定，不是脚本能读出来的事实。

