# W1：把断在工作树里的 26 族接线补回来（2026-10-22）

日期：2026-10-22
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
逆向树 `/Users/altair/github/gba-naruto-reverse`，commit `821d0937e058245aa7e6d29f23f96c7fc78e7375`
配套：`docs/butano-wiring-roadmap.md`（W1）、`notes/butano-wiring-coverage-20261022.md`（分母来源）、
`notes/butano-usable-backlog-20261022.md`（存量分诊）

## 0. 结论

**26 族本地产物已全部补回，且每一族都与逆向树逐字节相同。**
闸门 `measure_butano_wiring_coverage.py` 的 `local-derivation-missing` 计数 **= 0**。

| 模式 | 族数 | 含义 |
| --- | ---: | --- |
| `rederived` | **16** | 复刻侧自己的 producer 复现了逆向树的字节（**含解码器**）——强结论 |
| `imported` | **9** | 复刻侧无 producer 能复现该族（抓取／verifier 证据／schema 已迭代），按 reverse commit + 逐文件摘要从逆向树导入——弱结论，**不是本地派生** |
| `already-identical` | **1** | 还原前该族目录已存在且逐字节一致（`character-fbff-runtime-v1`），来源沿用既有记录 |
| `diverged` | **0** | 无分叉 |

⇒ **没有任何一族被「就近取一个」糊弄过去**：同 schema 却产出不同字节一律判 `diverged` 并失败关闭，
本轮 **0 例**。

## 1. 为什么要做这一步

2026-10-19 的 artifacts 清理带走了 8,124 个被跟踪文件（见
`notes/s49-fidelity-handover-20261019.md` §1）。受影响的不是「没人接的族」，而是
**复刻构建链已经在指、但本地产物没了**的族：

```json
"checkpoint": "artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9"
```

——`sequel/content/battle_controller_states.json` 等 7 个内容库文件都这么写。
**线断在工作树里，不在设计里。** 这正是 W1 被排在最前面的原因：补回 26 族的成本
比新接 26 个族便宜一个数量级。

## 2. 口径（全脚本实测，无人工名单）

```
候选族     : 接线收据里 state == "local-derivation-missing" 的族       → 26
逆向孪生   : <reverse>/artifacts/<family>/ 存在                        → 26/26
producer   : tools/**/export_*.py 中「字面量提到该族」或
             「--output-dir 默认值解析到该族」的脚本                   → 自动发现
逐字节判定 : 目录树摘要（相对路径 + 每文件 SHA-256 的滚动摘要）
             + manifest SHA-256（两侧都有时）
```

### 2.1 producer 是怎么找到的（一个实际的坑）

多数 producer 不把族名写成字面量，而是写成模块常量：

```python
SCHEMA = "bg-resource-canvases-v1"
parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "artifacts" / SCHEMA)
```

纯字面量扫描看不到 `bg-resource-canvases-v1`，于是这两族会被误判成
「无 producer ⇒ 只能导入」。改用 **AST 解析 `--output-dir` 默认值 + 解析模块级常量**
之后，`bg-resource-canvases-v1` 与 `bg-scene-selection-v1` 从「导入」升级为「复现」。

⇒ **教训**：发现 producer 不能只扫字面量。族名藏在常量后面时，
**「没找到」会被误当成「不存在」**，而且是静默的——它只让一个本该更强的结论变弱。

### 2.2 producer 之间有依赖，必须按拓扑序还原

`export_world_map_backgrounds.py` 要读 `artifacts/dialogue-font-v2/manifest.json`，
`export_story_scene_timelines.py` 要读 `artifacts/story-scene-layer-bindings-v1/manifest.json`。
**先跑依赖方会 FileNotFoundError**，看起来像「工具坏了」，实际是工作树缺料。

⇒ 工具按需递归补齐前置产物（前置族自己也走「先复现、复现不了再导入」）。

## 3. 三种模式的判据

| 情况 | 判定 | 处置 |
| --- | --- | --- |
| producer 产出与逆向树**逐字节相同** | `rederived` | 采纳，作为本地产物 |
| producer 产出**不同 schema**（版本迭代） | 导入 | 导入逆向树原版，理由里写明「producer 声称的 schema 与逆向树不同」 |
| producer 产出**同 schema 但字节不同** | `diverged` | **硬失败**，不落地任何本地产物，退出码非 0 |

第三行是路线图「分叉必须报错，不许『就近取一个』」的机器化。

本轮真实命中第二行的一例：

```
tile-assets-bg-v1   本地 producer 产出 schema tile-assets-bg-export-v2
                    逆向树该族 schema  tile-assets-bg-export-v1
```

⇒ 复刻侧的 `export_tile_asset_bg_layers.py` 已经迭代到 v2，**没有**能产出 v1 的工具。
该族按导入处理，并在收据里写明 schema 差异，而不是悄悄用 v2 的字节冒充 v1。

## 4. 两处判定被收紧（不是新功能，是旧判定不够严）

### 4.1 接线审计器从「只比 manifest」改成「比整棵目录树」

原判定只比 `manifest.json` 的 SHA-256。**manifest 只证明描述一致，不证明载荷一致**：
一份保持 manifest、换掉数据文件的本地产物会被判成「一致」。
现在改为**目录树摘要**（相对路径 + 每文件 SHA-256），manifest 哈希单独记在证据里。
另外，4 个抓取族（`e2e`、`runtime-checkpoints`、`world-map-gpu-captures`、
`scenario-41-audio-reference-v1`）**两侧都没有 manifest**，原判定永远给不出「一致」——
现在由树摘要裁决。

### 4.2 差异清单必须排除「逆向成果的本地副本」

还原后，`artifacts/runtime-checkpoints/` 里有一份 JSON 提到了
`rom-expansion-profile-v1`，把它从 `doc` 抬成了 `local_artifact`。
**副本内部的引用不是消费**——副本本身就是逆向成果。
这与 `artifacts/butano-reverse-m3-import-v1/` 被排除是同一条理由。

⇒ 差异清单新增一条**按内容判定**的排除规则：本地 `artifacts/<family>/` 的目录树摘要
**等于**逆向树同族摘要时，该目录整体不参与扫描。本轮命中 30 个目录。
规则是量出来的，不是手维护的名单；本地副本一旦与逆向树分叉，它立刻重新参与扫描。

⇒ 同时把新收据 `artifacts/butano-local-derivations-v1/` 加进静态排除表
（它逐族点名全体，是**总体枚举**，不是消费）。这是本仓库第 4 次踩自指坑。

## 5. 读数变化（全部来自当轮收据）

| 测量 | 还原前 | 还原后 |
| --- | ---: | ---: |
| 接线九态：`local-derivation-missing` | **26** | **0** ✅ |
| 接线九态：`local-rederived-identical` | 0 | **26** |
| 差异清单 `local_artifact` | 3 | **0**（副本内的引用不再计入） |
| 差异清单 `build` | 373 | **375**（两篇 2026-10-21 合并进来的 note 首次被计入，与本次还原无关） |
| 差异清单 `doc` | 512 | 513 |

### 5.1 全量套件：37 条由红转绿，0 条由本轮引入

`build/full-suite-w1b.log`：**Ran 2234，failures=31 / errors=92 / skipped=27 /
expected failures=5**（基线 `build/full-suite-r29.log` 为 2139/23/115/27/5，
去重后问题数 **138 → 123**）。

**转绿的 37 条全部是「需要本地产物才能跑」的 exporter 测试**：
`test_export_scene_visual_packs`、`test_export_world_map_runtime`、
`test_export_battle_effect_affine_runtime`、`test_export_story_scene_timelines`、
`test_export_tile_asset_bg_layers`、`test_butano_scenario_41_assets`、
`test_butano_scenario_41_gpu`、`test_butano_scenario_41_render` 等——
它们在还原前因 `artifacts/<family>/` 缺失而 `setUpClass` 失败。

⇒ **这是「线断在工作树里」的实证**：不是设计问题，是文件不在。

**与本轮无关的 21 条**（并行会话的未验收 WIP 所致，见 §7.1）：20 条是内容库
90 条版本与 `tests/test_text_and_visual_table_identity.py` 期望的 79 条冲突，
1 条是 `test_shipped_artifact_matches_a_fresh_build`（notes 索引漂移，
仓库已知：必须重建索引而非放宽门禁）。另有 1 条
`test_ask_antigravity_gemini` 是一次**真实模型调用**，天然不稳定。

## 6. 复现

```bash
# 还原（幂等；第二次运行保持 provenance 里的模式不变）
/usr/local/bin/python3 tools/restore_butano_local_derivations.py \
    --root . \
    --reverse-root /Users/altair/github/gba-naruto-reverse \
    --wiring artifacts/butano-wiring-coverage-v1/wiring.json \
    --out-dir artifacts/butano-local-derivations-v1

# 独立复核（不 import 还原工具，自己重算摘要与判定）
/usr/local/bin/python3 tools/verify_butano_local_derivations.py \
    --root . \
    --reverse-root /Users/altair/github/gba-naruto-reverse \
    --receipt artifacts/butano-local-derivations-v1/local.json \
    --wiring artifacts/butano-wiring-coverage-v1/wiring.json

# 闸门
/usr/local/bin/python3 tools/measure_butano_wiring_coverage.py \
    --root . \
    --backlog artifacts/butano-usable-backlog-v1/backlog.json \
    --gap artifacts/butano-reverse-gap-v1/gap.json \
    --index artifacts/reverse-results-index-v1/index.json \
    --reverse-root /Users/altair/github/gba-naruto-reverse \
    --out-dir artifacts/butano-wiring-coverage-v1
```

收据：`artifacts/butano-local-derivations-v1/{local.json,local.md,provenance.json}`
门禁：`tests/test_restore_butano_local_derivations.py`（13 项）+ 接线/差异清单既有门禁

### 6.1 `provenance.json` 为什么单独存一份

还原是幂等的：第二次运行时本地产物已经逐字节一致，工具会把模式退化成
「already-identical」——**强结论（复现）会被洗成弱结论（本来就在）**。
`provenance.json` 记住每族「当初是怎么来的」，第二次运行时按摘要校验后原样保留。
⇒ **测量工具的幂等性不能以丢失来源信息为代价。**

## 7. 边界声明

- **`rederived` 只覆盖 16 族**。另外 9 族是导入，**不能声称复刻侧能自己产出它们**。
- 导入族按 reverse commit `821d0937…` + 逐文件 SHA-256 钉死；逆向树一变摘要就变。
- 本轮**没有**把任何族接进复刻构建链的**声明**载体——W1 补的是「本地产物」，
  接线声明载体是 W3 的事。
- 差异清单的 `build` 375 与还原前的 373 之差来自 2026-10-21 合并进来的两篇 note，
  **不是**本次还原带来的。
- 本地产物共 6,206 个文件、约 40 MB，已入库（与 `artifacts/butano-reverse-m3-import-v1/` 同惯例）。

### 7.1 ⚠️ 共享工作树的并行写入（本轮实际发生）

本轮工作期间，**另一个会话在同一工作树里提交了 WIP 快照**
（`b35351db wip(main-tree): round-25 战场 overlay 第二轮在飞工作保全快照`，08:54:03），
**把本轮已还原的 `artifacts/` 一并快照进去了**。核查结论：

- 本轮的工具与收据**未被覆盖**（`git status` 与内容比对确认）；
- 全量套件里 19 条「转红」的用例**与本次还原无关**：
  对方会话把 `sequel/content/*/bank.json` 改成了 90 条版本
  （`tests/test_text_and_visual_table_identity.py` 仍期望 79 条），
  而该快照自述「**本轮未对该批内容做全量构建/测试验收**」；
- 反而有 **35 条用例由红转绿**，全部是**需要本地产物才能跑**的 exporter 测试
  （`test_export_scene_visual_packs`、`test_export_world_map_runtime`、
  `test_butano_scenario_41_assets` 等）——**这正是「线断在工作树里」的实证**。

> **教训**：共享工作树里做还原时，**必须用文件级快照证明「不是我改的」**。
> 判据是**内容与 mtime 双证**（本轮实测：完整重跑还原器后，
> 内容库的 sha 与 mtime **都没变** ⇒ 还原器不写内容库）。
> 只看 `git status` 不够——并发提交会把别人的改动和自己的改动混在一起。

## 8. 相关

- `docs/butano-wiring-roadmap.md`（W0–W5 执行路线图；W1 已闭合）
- `notes/butano-wiring-carriers-20261022.md`（W3 动作 1：审计器覆盖两套载体）
- `notes/butano-wiring-coverage-20261022.md`（接线点枚举 + 两套载体的教训）
- `notes/butano-usable-backlog-20261022.md`（存量分诊 + 词表探针的三处错分）
- `notes/s49-fidelity-handover-20261019.md` §1（2026-10-19 清理带走 8,124 个被跟踪文件）
- `tools/restore_butano_local_derivations.py`、`tools/verify_butano_local_derivations.py`、
  `tools/measure_butano_wiring_coverage.py`、`tools/measure_butano_reverse_gap.py`
