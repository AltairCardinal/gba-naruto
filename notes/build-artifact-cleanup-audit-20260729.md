# `build/` 产物清理审计（2026-07-29）

## 结论

- 审计时顶层 `build/` 实占约 `1.7 GiB`，apparent size 约 `1.6 GiB`；当前目录本身并非
  `24 GiB`。旧数字不能作为本次删除依据。
- `build/` 中的大部分空间是 ROM、`.ss9`、SAV、GPU/OAM/VRAM dump、录像和运行守卫，
  不是普通编译缓存。
- 本轮只删除了能够由源码和测试命令完全重建、且没有仓库引用的宿主测试二进制：
  - `build/host-tests/`
  - `build/test_battle_ai-current.dSYM/`
- 删除前两项共占 `9,812 KiB`；删除后 `build/` 为 `1,736,948 KiB`，共有
  `20,371` 个文件。

## 判定标准

只有同时满足以下条件的内容才能直接清理：

1. 不被 `notes/`、`docs/`、`tools/`、`tests/` 或 `artifacts/` 引用；
2. 不含唯一 ROM、快照、输入日志、运行时 dump、录像或 guard 证据；
3. 能由仓库内已有命令确定性重建；
4. 不属于当天仍在进行的 Butano 工作；
5. 清理时没有进程持有相关文件。

“没有直接文本引用”不能单独证明可删除；未引用的实验原件可能只是尚未完成成果转化。

## 当前必须保留

- `build/resource-guard/`：被大量文档直接引用，并在本次审计当天仍有 Butano 任务写入。
- `build/audio-v2/`、`build/audio/`：现有音频测试和工具直接读取。
- `build/signed-tooling/`：构建和验证链路直接依赖。
- `build/original-fire-presentation-trace-20260726-{98,99}/`：现有生成器和测试直接读取。
- 被笔记直接引用的视频、快照、运行目录：在关键帧、manifest 和复现入口迁入
  `artifacts/` 且对应笔记提交前，仍是证据链的一部分。
- `build/mgba-upstream-patch/`：是异常/未完成的嵌套 Git 工作树，不能按缓存删除。

## 后续可清理候选

以下目录体积较大，但目前仍包含尚未固化到 `artifacts/` 的原始证据，不能直接删除：

- `build/butano-battle-video-analysis-20260725-ai-defense/`
- `build/battle-presentation-original-probes-20260727-01/`
- `build/battle-reaction-family-runtime-20260725-02/`
- `build/butano-combat-presentation-runtime-*`
- `build/butano-action05-*-runtime-*`

处理顺序应为：提取最终关键帧/manifest/输入与哈希 → 写入并验证 `artifacts/` →
更新持久笔记中的证据路径 → 提交成果 → 再删除原始临时目录。

## 成果转化复核

第二轮按“现有成果能否独立复核结论”逐项检查了最大的非活动目录。仅有笔记、哈希或
生成命令，不等于原始输入已经转化完成：如果媒体、trace、输出快照或内存 dump 仍只存在
于 `build/`，删除后就无法独立复核视觉或运行时结论。

| 分类 | 体积 | 当前状态 | 清理结论 |
|---|---:|---|---|
| 已删宿主测试缓存 | `9,812 KiB` | 源码和测试命令可确定性重建，无仓库引用 | 已清理 |
| 录像、联系表、ROM trace 与输出快照 | `619,680 KiB` | 已有笔记或结构化 JSON，但原始输入/输出仍仅在 `build/` | 先迁入持久 artifact 并验证，再清理 |
| `battle-presentation-original-probes-20260727-01/` | `128,436 KiB` | 4,868 个 GPU/OAM/PRAM/VRAM dump、PNG 与快照尚无领域成果映射 | 必须保留 |
| `audio-v2/` 与 `audio/` | 约 `33 MiB` | 测试、工具及编辑器规格直接读取 | 必须保留 |

因此第二轮没有追加删除项，立即可安全回收量为 `0`。约 `605.2 MiB` 的候选不是缓存；
只有在原始媒体/trace 或足够独立复核的派生工件、manifest、输入哈希和验证命令迁入
`artifacts/`，相关笔记改为持久路径并提交后，才达到删除条件。不能为了回收空间而让
现有证据路径断链。

## 复核命令

```sh
du -sh build
du -shA build
find build -type f | wc -l
rg -l --glob '!build/**' 'build/' notes docs tools tests artifacts
```

## 第三轮清理：按成果转化状态复核

本轮重新按“是否已经形成持久成果”核对：

- 已提交的六组静态图形成果均已进入 `artifacts/`，具备 ROM 哈希、导出器和测试；
  这些任务没有在 `build/` 留下显著重复副本。
- 最大的约 `605.2 MiB` 仍是外部录像、原 ROM trace、快照、GPU/OAM/PRAM/VRAM
  dump。相关笔记仍直接引用其中的原始输入，且尚无等价的持久 artifact，因此继续保留。
- `build/tiles/` 与 `build/tiles-v2/` 只是 tileset atlas；47 张完整地图层/画布尚未完成
  解码，不能把它们误判为已经转化完成。
- `build/audio-v2/`、`build/audio/`、`build/resource-guard/`、`build/signed-tooling/`
  仍被工具、测试或当前流程直接读取，继续保留。

确认没有进程持有文件、没有仓库引用后，清理了八个可由源码和测试命令重建的旧宿主
构建目录、十七个宿主测试可执行文件和一个对象文件，共 `48,856,483` 字节
（`46.59 MiB`）。清理后：

- `build/` 为 `1,688,692 KiB`；
- 文件数为 `20,054`；
- 所有目标路径均已确认不存在。

这些内容只是已经由源码、测试和后续验收结果取代的构建缓存，不承担 ROM 原始证据、
可复用快照或运行时 dump 的职责。本轮未删除任何录像、音频、ROM、savestate、trace、
guard、持久 artifact 或并行 Butano 任务的当日产物。

## 第四轮清理：完整地图成果落库后

完整地图成果 `artifacts/map-canvases-v1/` 已提交，包含 47 张地图的 61 张主/备选
索引画布、展开后的 tilemap、去重原始资源、ROM/表哈希及独立 verifier。复核时：

- `tests/test_extract_tileset.py` 的 6 项测试通过；
- `tools/verify_map_canvases.py` 独立验证 `47/47` 地图、`61/61` 画布；
- 逐地图对比旧 manifest 与新 manifest，47 组 tile graphics 的 ROM offset、解压大小和
  SHA-256 全部一致；
- `build/tiles/` 与 `build/tiles-v2/` 没有进程占用，只含可由已提交脚本重建的旧
  tileset atlas，已被完整地图成果取代；
- 全量哈希对比发现 `build/` 内另有 1,012 个文件、约 `31.03 MiB` 与已跟踪
  artifacts 内容相同，但它们只覆盖所属 trace 的一小部分。为避免破坏原始帧序列和
  实验上下文，本轮不做碎片式删除。

因此仅删除 `build/tiles/` 与 `build/tiles-v2/`，回收 `776 KiB`。录像、音频、
ROM、快照、trace、GPU/OAM/PRAM/VRAM dump、guard、工具链及并行 Butano 当日产物
继续保留；它们尚未被完整、可独立复核的持久成果覆盖。清理完成时 `build/` 为
`1,688,000 KiB`；并行任务仍可能继续向其中写入新结果。

## 第五轮清理：全仓库嵌套构建目录复核

本轮同时检查顶层和嵌套 `build/`，确认先前所称的 `24 GiB` 已不在当前工作树中：

- 顶层 `build/` 清理前为 `1,688,108 KiB`；
- `butano-sequel/build/` 为 `61,660 KiB`，属于当天仍在运行的并行 Butano 工作；
- `third_party/butano/examples/{audio,sprites}/build/` 合计 `34,556 KiB`，只含
  497 个可由各自 Makefile 重建的 `.o/.d/.s/.h` 等示例编译中间文件；
- 其余嵌套构建目录均不足 `18 MiB`。

两个 Butano 示例构建目录未被 Git 跟踪、被子模块 `.gitignore` 明确忽略、没有仓库
引用且没有进程占用，因此已删除。另从 `build/test-results/` 删除 4 个无仓库引用、
可由宿主测试源码重建的旧调试可执行文件；其文本日志继续保留。两类合计回收
`35,976 KiB`（约 `35.13 MiB`），其中顶层 `build/` 回收 `1,420 KiB`。

清理期间并行 Butano 任务正通过资源守卫运行 mGBA；本轮没有删除或修改
`butano-sequel/build/`、`build/resource-guard/`、`build/signed-tooling/` 或该任务的
任何 artifact。此前列出的录像、原始 ROM trace、快照和内存 dump 仍未被完整持久成果
覆盖，继续保留。

## 第六轮清理：按成果转化状态终检

本轮再次以“是否已有可独立复核的持久成果”为唯一清理依据：

- 顶层 `build/` 清理前为 `1,686,712 KiB`，已不含先前所称的 `24 GiB` 临时产物；
- 近期完成的角色战斗视觉和场景背景资源已提交到 `artifacts/`，但没有在 `build/`
  留下可整目录删除的大体积重复副本；
- 当前最大的录像、ROM trace、快照、GPU/OAM/PRAM/VRAM dump 仍被笔记引用，或其
  原始输入与实验上下文尚未完整迁入持久 artifact，不能因已有局部结论而删除；
- `build/audio-v2/`、`build/audio/`、`build/resource-guard/`、
  `build/signed-tooling/` 和 `build/mgba-upstream-patch/` 仍分别承担工具输入、
  运行守卫、签名工具链或未完成工作树职责；
- 当日新增的 `build/butano-battle-ui-flow-depth-host-20260729-01/` 及
  `butano-sequel/build/` 属于并行 Butano 工作，本轮未触碰。

确认没有仓库引用和进程占用后，删除了 `build/test-results/` 中 4 个遗留 `.dSYM`
调试符号包。它们对应的调试可执行文件已在前轮清理，符号包可由现有源码和测试重新
生成，不承担 ROM、快照或运行时证据职责。本轮实际回收 `2,260 KiB`；清理后顶层
`build/` 为 `1,684,452 KiB`，且其中不再存在 `.dSYM`。

## 第七轮清理：全量哈希成果核对

本轮对 `build/` 与已跟踪 `artifacts/` 做全量 SHA-256 对照，并按顶层目录统计完整
覆盖率。核对结果：

- `build/battle-continuation-source-20260725-01/` 仅含一个 `base.gba`，SHA-256 为
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；该内容已由
  `artifacts/type2-original-probe-20260726-04/staged.gba` 等多个已跟踪工件完整承接，
  `build/` 之外的仓库文件没有引用，因此删除整个目录。
- 删除一个无引用的 0 字节日志和三个无引用空目录；它们不承载结果或证据。
- `build/naruto-sequel-dev.sav` 虽与持久 artifact 内容相同，但仍被两份笔记直接引用，
  仅占 32 KiB，因此保留，避免制造文档断链。
- 大体积目录只有部分文件与 artifact 重复。例如
  `battle-presentation-original-probes-20260727-01/` 的 4,868 个文件中仅 640 个重复；
  原始帧序列、dump 和实验上下文没有被完整覆盖，因此不做碎片式删除。

本轮从 `1,684,484 KiB` 清理至 `1,678,344 KiB`，回收 `6,140 KiB`，文件数降至
`20,039`。清理后检测到并行 Butano 任务正在通过 `run_guarded.py` 驱动 mGBA；本轮
没有触碰其 `artifacts/butano-battle-s49-fidelity-20260729-19/`、
`build/resource-guard/`、`build/signed-tooling/` 或 `butano-sequel/build/`。

## 第八轮清理：成果承接与可重建性终审

本轮再次核对 Goal、Git 状态、仓库引用、目录内容和活跃进程，只清理满足“结论已经进入
持久代码/测试/笔记，原目录不再承载唯一证据，且可从既有来源重建”的项目：

- 删除 `build/maxmod-upstream-20260727-01/`。它是约 `1.2 MiB` 的临时 partial clone，
  工作树源码已经全部缺失，只剩可从公开上游 commit
  `97c4e3267afc08f6f8a2da1ef7238d5b0bfdef0d` 重新取得的 Git 对象缓存；仓库没有引用
  该路径。
- 删除 `build/maxmod-header-diagnostic-20260727-01/`。其中只有旧的
  `soundbank.bin`/`soundbank.h` 诊断输出，约 `4.4 MiB`；Maxmod 接线、故障根因和
  音频边界已经进入 `butano-sequel/`、对应测试及持久笔记，这两个文件可由现有音频
  资产和构建链重新生成，仓库没有引用该路径。
- 删除三个无文件的空运行目录：
  `battle-substitution-position-watch-20260725-{01,02}/` 和
  `butano-ai-runtime-20260724-01/`。既有笔记引用这些名称只是为了明确记录保护失败或
  checkpoint 不适用，且已明确说明输出为空；保留空目录不会增加可复核证据。

删除后上述五个路径均不存在，顶层 `build/` 有 `19,871` 个文件。由于同仓库的并行
Butano 工作仍可能写入 `build/resource-guard/` 等目录，清理前后的顶层总量不能单独
用作本轮回收量；本轮目标目录本身约回收 `5.6 MiB`。

其余约 `1.6 GiB` 未继续删除：大体积录像、ROM trace、快照、GPU/OAM/PRAM/VRAM dump
仍未被完整、可独立验证的 `artifacts/` 承接；`audio-v2/`、`audio/`、
`resource-guard/`、`signed-tooling/` 仍被测试或工具直接使用；
`mgba-upstream-patch/` 仍是未完成的异常工作树；`butano-sequel/build/` 和当日产物
属于并行 Butano 工作。删除它们会造成证据断链、测试输入缺失或干扰并行任务。

## 第九轮清理：新增成果差量复核

本轮以第八轮之后新增并提交的成果为差量边界再次核对：

- 首次核对时顶层 `build/` 为 `1,678,868 KiB`，共有 `19,878` 个文件；并行任务随后
  继续写入守卫结果，因此该数字只作为审计起点。此前所称的 `24 GiB` 仍不在当前工作树中。
- 新增的 `tile-assets-bg-v2` 与 `story-scene-layer-bindings-v1` 直接生成到
  `artifacts/`，没有在 `build/` 留下可整目录删除的重复副本。
- 最大的录像、ROM trace、快照及 GPU/OAM/PRAM/VRAM dump 仍只有部分文件与持久
  artifact 重复；其余原始帧序列和实验上下文尚未被完整承接，继续保留。
- 零字节 trap 日志记录对应实验没有命中陷阱，属于阴性结果，不按普通空文件删除。
- 复核期间并行 Butano 任务正通过 `tools/run_guarded.py` 使用
  `build/signed-tooling/mGBA.app`，因此未触碰它的工具链、守卫、构建目录或运行产物。

本轮没有满足全部删除条件的新项目，实际删除量为 `0`。这不是清理遗漏：强行删除剩余
内容会造成证据链断裂、测试输入缺失，或干扰并行任务。后续应先把原始媒体/trace 的
关键输入、完整 manifest、哈希和独立验证入口迁入 `artifacts/`，再按顶层目录完整删除，
不做破坏实验上下文的碎片式去重。

## 第十轮清理：角色场景视觉成果后的差量核对

本轮在 `scene-visual-packs-v1` 提交后重新核对成果承接、仓库引用、目录时间和活跃进程：

- 顶层 `build/` 实占 `1,679,248 KiB`、共有 `19,892` 个文件；全仓库只有它和约
  `62 MiB` 的 `butano-sequel/build/` 两个有显著体积的构建目录，当前工作树中不存在
  `24 GiB` 的临时 `build/` 产物。
- `scene-visual-packs-v1` 由 ROM 直接导出到已跟踪 `artifacts/`，没有在 `build/`
  留下重复目录，因此该成果没有对应的新增清理对象。
- 第九轮之后新增的内容只有 `resource-guard/` 记录、场景 49 GPU dump 和三张对比图；
  它们属于当天并行 Butano 验证，尚未形成等价的已提交 artifact，不能删除。
- 其余约 `1.6 GiB` 的录像、trace、快照和内存转储仍未被完整成果承接；音频输入、
  签名 mGBA 工具链和守卫目录仍被测试或运行流程直接使用。

因此本轮实际删除量仍为 `0`。这是按成果转化状态得出的安全结果；此时继续删除只能
回收尚未固化的原始证据或影响并行任务。下一批应在相应录像/trace 建立完整 manifest、
输入哈希、关键输出和独立 verifier 并提交后，再按实验目录整批清理。
