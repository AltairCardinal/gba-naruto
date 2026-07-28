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

## 复核命令

```sh
du -sh build
du -shA build
find build -type f | wc -l
rg -l --glob '!build/**' 'build/' notes docs tools tests artifacts
```
