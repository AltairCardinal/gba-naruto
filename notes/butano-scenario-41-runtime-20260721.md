# Butano Scenario 41 运行证据（2026-07-21）

> **已取代：** 本文记录的是旧“功能等价”占位纵切片。原作 1:1 稳定边界、正确的木叶丸身份、`100/50/0=150` 结算和后续实机证据以 `notes/butano-scenario-41-one-to-one-runtime-20260722.md` 为准。

## 固定输入

- 原 ROM：`rom/base.gba`，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- 复刻目标：battle/scenario 41，9×22 grid，Naruto `(4,10)`，Iruka `(4,4)`。
- Butano：21.7.1，提交 `112a1827c9c6d9e6041a7e93e66f04c4561a6415`。
- 工具链：`devkitpro/devkitarm@sha256:116afba8df8453961de2936ffab20dd441edf4d682856c1ec8b0e53d7ed0bbf5`。

## 已完成证据

- 领域层：`test_production_primitives`、initial、movement、turns、victory、presenter
  六个宿主 C++ 测试均通过 `-std=c++23 -Wall -Wextra -Werror -pedantic`。
- 兼容层：既有 action state、pathfinder、battle effects、chapter VM、save codec
  五个 benchmark 测试保持通过。
- 资产：256×512/4bpp map 和 16×48/4bpp units 由确定性生成器产生；两次临时目录
  输出 SHA-256 完全一致。
- 首次场景编译：`build/resource-guard/butano-s41-build-20260721-01.json`，
  `completed/0`，non-degraded，峰值 77.859375 MiB。
- presenter 重构后的集成编译：
  `build/resource-guard/butano-s41-build-20260721-02.json`，`completed/0`，
  non-degraded，峰值 128.6640625 MiB。
- 移动范围性能修复后的干净构建：先运行
  `build/resource-guard/butano-s41-clean-20260721-04.json`，再运行
  `build/resource-guard/butano-s41-build-20260721-04.json`；均为 `completed/0`、
  non-degraded，构建峰值 133.7578125 MiB。干净构建与修复后增量构建的 ROM 哈希
  均为 `c55a440da95401f1ec965dfb73c4293b5d0a9724eb8c686be3369434e50232fd`。

## 运行验收状态

冷启动 mGBA 输入与画面验收已完成。最终 run ID 为
`butano-s41-runtime-20260721-02`，证据目录是同名的
`build/butano-s41-runtime-20260721-02/`。输入由
`tools/butano/mgba_scenario_41_acceptance.lua` 在 930 个模拟帧内显式注入，共 17 次：
关闭开场、选择鸣人、向上移动三格、WAIT、两个 START 等待回合、第四回合选择 COMBO、
选择相邻伊鲁卡、进入结果页并重新开始。

- ROM SHA-256：`c55a440da95401f1ec965dfb73c4293b5d0a9724eb8c686be3369434e50232fd`。
- mGBA：0.10.5 + Qt script backport；二进制 SHA-256
  `af6ab51a2ff63d6067908938aa74181fe2bbad0c441e231f3c4dbc80e7d6fe5d`；来源和
  backport 提交固定在 `build/mgba-0.10.5-script-backport-manifest.json`。
- `guard.json`：`reason=completed`、`exit_code=0`、`degraded=false`、
  `completion_trigger=success-marker`、峰值 `95.6875 MiB`；完成后未留下该 mGBA
  进程。
- `audit.json` 固定 run ID、ROM 哈希、17 次按键、六张主验收截图和
  `final.ss9`；done marker 在所有证据写完后才创建。
- `intro.png` 显示目标；`turn-2.png` / `turn-4.png` 显示回合推进；
  `victory.png` 显示 `VICTORY`；`result.png` 显示 `EXP +110` 与
  `TRAINING +1`；`restart.png` 回到与初始一致的目标页。关键三张截图哈希分别为：
  `victory.png` `6bd07621cd0a5710920548aac16bfe559a737da0619a442d0ad47b2b4767f364`，
  `result.png` `38689416bfbf80c947434f9f632072f9a0be9f211a72f4beeac2450d41147fe5`，
  `restart.png` `138945a4b8b7ae926f916fc253969276a7977cb0ce52de8416b02203e83faec0`。

## 运行时问题与修复

首次 run `butano-s41-runtime-20260721-01` 暴露出移动选择卡顿：显示层在 9×22 地图上
逐格执行 198 次寻路，渲染期间后续自动按键已按下又释放，最终未能进入胜利页。该失败
证据保留，不能视为验收成功。修复先由 `reachable_points()` 的失败宿主测试约束，再把
候选缩到移动力 3 的至多 24 个格子，并让场景直接消费该集合；源码 wiring 测试同时禁止
恢复 198 格全图循环。修复后的同一输入序列完整到达胜利、结算和重开，确认 bug 已修复。

## 边界

本次证据证明当前 ROM 的一条完整胜利路线可从冷启动完成，不证明战前编队、多技能、
失败结算、旧存档、战后世界地图或其他章节已经实现。画面采用辨识度近似资源，不是原作
逐像素复刻。
