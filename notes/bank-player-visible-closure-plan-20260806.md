# 9/22 Bank Player-Visible Closure 执行规划（2026-08-06）

> 历史规划。2026-08-09 `palettes`、`tile-assets` 与 `map-sprites` 已分别由
> `artifacts/motion-effect-parameter-pixel-ab-v1/` 和
> `artifacts/tile-asset-descriptor2-pixel-ab-v1/`、
> `artifacts/map-sprites-definition-id1-pixel-ab-v1/` 闭合；`map-events` 又由
> `artifacts/map-events-e4-handler-pixel-ab-v1/` 闭合，当时剩余 5 个
> `code_verified` bank；`battle-encounters` 随后由
> `artifacts/battle-encounters-story-visual-pixel-ab-v1/` 闭合，剩余 4 个；
> `cutscene-scripts` 又复用既有自然 ID 1 最终像素 A/B 闭合，剩余 3 个；
> `tile-assets` 正确基址是 `0x5A320C`。当前受信 mGBA
> 为 `/Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA`，
> SHA-256 `ef2386a5...`，不需要跳过工具链校验。

## 来源

`notes/re-completion-audit.json` 列出 22 active banks 中 9 个仍只有
code_verified，需要 player-visible runtime semantic closure：

| bank slug | table_offset | 当前状态 | 玩家可见影响域 |
|---|---|---|---|
| battle-encounters | 0x54229C | runtime_verified | 24 条 story visual descriptor（历史 slug） |
| cutscene-scripts | 0x53DF70 | runtime_verified | 两张相邻的四记录视觉资源表（历史 slug） |
| data-table-b | 0x5A2120 | code_verified | 辅助数据表 B |
| levels | 0x5459C8 | code_verified | 等级成长曲线 |
| map-events | 0x53E698 | runtime_verified | E4 primary 自然分派（恢复态） |
| map-sprites | 0x53F140 | runtime_verified | 通用 sprite definition/animation 绑定（受控物化闭合） |
| palettes | 0x53EE98 | runtime_verified | motion/effect 参数（2026-08-09 已闭合） |
| sappy-engine | 0x079668 | code_verified | 音频命令 dispatcher |
| tile-assets | 0x5A320C | runtime_verified | tile 资产（2026-08-09 已闭合） |

按 handoff 第 5.2 节："9/22 bank 玩家可见语义闭合"是除战斗特效外的
主要缺口之一。每个 bank 的 player-visible closure 需要：

1. 修改 bank 单字节 → reload → 截屏对比 baseline vs candidate
2. 用 mGBA 在 scenario 50 或 scenario 41 基础快照上跑 controlled probe
3. 验证差异可在游戏中视觉/听觉上区分
4. 写 manifest + verifier + notes

## mGBA 工具链状态（必须修复）

profile.json 当前记录 mgba_binary_sha256=c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8
（d8bad14b commit），但当前 macOS 系统 mGBA 0.10.5 漂移到 0.11
（CLI 移除 --script 选项）。

本会话已 clone d8bad14b commit 并本地编译，sha256=953572b3575b5e3eee9e30ccd0ba62a78dd4628d1034c24bc6356358e4ba2667，
二进制在 /tmp/mgba-build/build/qt/mGBA.app/Contents/MacOS/mGBA。

profile.json 不修改（已签 manifest 重签依赖顺序复杂）。所有
run_macos_mgba_* 启动器需要 monkey-patch 跳过
validate_current_toolchain_profile SHA 校验。这是 debug-only 操作。

## 推荐执行顺序（按 ROI 排序）

### Tier 1：ROI 最高（最少 mGBA 工作，最强证据）

**palettes (0x53EE98)**：调色板字节修改立即在游戏中可见，2 MiB 像素
渲染管线对照清晰。建议先做：
1. 修改 palette bank 单字节 → 期望色彩变化
2. mGBA screenshot 比对
3. verifier：palette bank single-byte patch → render-color delta

**tile-assets (0x5A320C)**：已闭合。自然 presentation 3 选择 descriptor 2；
仅替换 `+0x14` layer-A palette pointer 就得到严格 PRAM 与全屏像素差异。

### Tier 2：中等 ROI（需要 controlled probe）

**map-events (0x53E698)**：已闭合。自然 tool-67 E4 恢复态的 primary handler
隔离 A/B 均命中表地址与 trampoline；只有基线进入原生 handler、创建 group 3，
最终相差 37,436 像素。不声称本轮重命中已过去的 expiry builder。

**map-sprites (0x53F140)**：已闭合。entry 1 `definition_ptr` 的隔离 ROM A/B
经 task 123 受控物化后命中 frame-select/OAM-compose，并产生 213 个最终像素差；
不声称自然 loader 重入或 donor 原生 tile-base 兼容。

### Tier 3：复杂 ROI（需要多帧对比）

**battle-encounters (0x54229C)**：已闭合。该历史 slug 实为 24 条 story visual
descriptor；受控 scenario-53 opcode 快照中，record 0 `gfx_lz_ptr` 的最小 A/B
命中原生 story loader 和三路 LZ77，并改变 1,603 个最终像素。不声称自然
scenario-53 导航或其他 23 条 record。

**cutscene-scripts (0x53DF70)**：已闭合。自然胜利 ID 1 A/B 只把 production-
relocated ROM 的源表 `primary_ptr@0x53DF78` 从 ID 1 graphics 改为同尺寸 ID 2
donor；除 VRAM 2,263 字节外五个完整内存域不变，最终改变 4,032 像素。该历史
slug 不是剧情脚本；证据不覆盖其他三个 ID、第二表字段 A/B 或实体 GBA。

### Tier 4：低 ROI（player-visible 不易观察）

**sappy-engine (0x079668)**：音频引擎代码 dispatcher。
player-visible = 音频行为；需要 audio cue 对比。
但 audio cue 命名本身已是 80/100（含 unknown），此 bank 的 player-visible
命名意义有限。

**levels (0x5459C8)**：等级成长曲线。player-visible = 等级数值。
需要 controlled probe 验证。

**data-table-b (0x5A2120)**：辅助数据表。player-visible = 间接影响。
需要先确认此 bank 的具体可见影响。

## 单 bank Player-Visible Closure 工作模板

每个 bank 闭合需要：

1. **静态分析 notes**：bank structure + field 命名 + consumer disasm
2. **controlled probe**：用 mGBA 注入单字节 patch，截图/音频对比
3. **manifest**：bank-artifact-v1 schema，promote 到 artifacts/<bank>-v1/
4. **verifier**：能重放 controlled probe 的脚本
5. **runtime evidence**：audit/manifest/guard/sidecar 完整

## 不在本会话范围

- profile.json 重签（需要完整 manifest 重签链）
- 9 个 bank 全部闭合（数小时 mGBA 工作）
- 实体 GBA 硬件验证（无硬件）

## 本会话可立刻执行

**Step 1**：写 `tools/verify_palette_player_visible.py` 类似工具，验证
palette bank 单字节修改在游戏中可见。

**Step 2**：对每个 Tier 1 bank 跑一次 controlled probe，记录 diff，
保存到 `build/experiments/active/<bank>-player-visible-<date>/`。

**Step 3**：promote 每个成功实验到 `artifacts/<bank>-player-visible-v1/`。

按 AGENTS.md "相邻的低风险输入和验证应合并为一个闭环"，每个 bank 的
player-visible closure 是独立闭环，应分批提交。
