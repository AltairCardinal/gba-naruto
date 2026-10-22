# Codex re-entry audit（2026-07-12）

## 接管范围

- Draft PR：`#1 Reverse-engineering runtime chains, safe tooling, and replayable handoff`
- base：`master`
- head：`task/units-character-definitions`
- 接管时 head：`c1a3680 Package replayable runtime handoff`
- PR 状态：OPEN、Draft、merge state CLEAN

本地先执行 `git fetch origin --prune`，再切换并跟踪
`origin/task/units-character-definitions`。原工作区六个未跟踪本地文件均保留，未覆盖、
未提交。

## 已阅读的权威材料

1. `artifacts/runtime-checkpoints/README.md`
2. `notes/alternate-chapter-runtime-probe-20260712.md`
3. `notes/current-re-progress-20260711.md`
4. `docs/sequel-roadmap.md`
5. `docs/reverse-engineering-handoff-20260711.md`

新材料证明此前 units/maps/save/audio/primary chapter 等路线已经显著推进。旧
`goal-100pct-re.md` 中 2026-06-26 的“结构/生成器数量 + 17 项测试”清单不再能证明
完成，但“100% 完成逆向工程”总目标仍未达成，不能废弃。

## 环境与诊断 ROM 复现

```text
npm install --prefix play/_scripts
added 23 packages; 0 vulnerabilities
```

诊断 ROM 重建：

```text
python3 tools/build_alternate_chapter_runtime_probe.py \
  rom/base.gba /tmp/alternate-chapter-runtime.gba
SHA-256 c98e2d2c02e4e0235e14e584a5a423a20a079db897b85fa09adea7ef0a93e6a4
```

与交接预期完全一致。

## Checkpoint replay smoke

使用：

- Chromium `/usr/bin/chromium`
- `PROBE_INPUT_MODE=keyboard`
- `alternate-mission-selection.ss9`
- zero navigation input / one settle poll

结果：

- checkpoint SHA-256：
  `492ae012702be7488984640da968f3343670f152d189fa3628fee24b056a0308`；
- screenshot SHA-256：
  `43d9a45a0d4930947b70148ed9099028fad37651824b1fb627ec656c5fb9be60`；
- result JSON SHA-256：
  `6f605babd18ae8ef17045d096b66d9310fb743099a70d0fa110d66a167a2e577`；
- screenshot 为可辨认的“木叶里 / 对战”任务选择页；
- probe 按设计返回 `not-found / settle-exhausted`；
- chapter opcode hook hit count 0；
- battle ID 0；map runtime 与 unit runtime 均为空。

视觉分类器把该任务 UI 标成 `battle-map`，但严格内存门禁拒绝到达，因此不构成
story-b 或战斗到达证据。smoke test 通过交接定义。

## 测试基线与本地 DB 差异

首次运行时 Python 116/116、Node 27/27 通过，但 automated checks 为 23/25。
根因是本地保留的、被 `.gitignore` 排除的旧 `sequel/editor.db` 使用旧 schema：

- `rom_battle_config` 缺少当前分支要求的 `byte_00`；
- 旧 disproved mirror 表仍保留历史行。

该状态不属于 Git 分支内容。为复现 clean-clone 基线，旧数据库被完整移动到：

```text
/tmp/gba-naruto-editor-pre-handoff-20260712.db
```

随后由当前代码生成新库。最终验证：

```text
Python unittest: 116/116
Node probe tests: 27/27
Automated checks: 25/25
Bank audit: 32/32
Evidence: runtime 7 / code 3 / static 17 / disproved 5
git diff --check: pass
```

## Goal 决议

1. 保留总目标：100% 完成逆向工程。
2. 废弃旧执行计划：不再以 bank/generator 数量或旧 17 项测试作为完成证明。
3. 当前 P0：闭合 alternate chapter table `0x60D54`；scenario 39 目标脚本
   `0x08031281`。
4. `story-b` 只有同时满足 hook hit、alternate table pointer、script 内 opcode 和
   非零结果状态/明确终止语义后才能升级 runtime。
5. Draft PR #1 保持 Draft，不转 Ready、不合并；后续继续提交到同一分支。
