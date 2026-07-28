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
