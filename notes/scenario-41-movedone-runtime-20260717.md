# Scenario 41 首次 MOVEDONE 朝向提示持久化（2026-07-17）

## 方法与谱系

- 从已接受的 `scenario-41-player-turn` 出发，持久谱系只记录显式输入 `A -> Up -> A -> A`；已丢弃的 L 诊断与无效果 Up 诊断不属于谱系。
- 唯一 corrected A run ID 为 `d10c70cfe08e17f1b86f3f8c99ce9485`。其 baseline counter/MOD1/MOD2 全零，final counter 为 1，MOD1 在 `0x0807443C` 发布 fresh primary record，`0x08074918` 对应 MOD2 保持全零。
- MOD1 绑定 slot 1、record `0x02024294`、character 1、affiliation 0、坐标 `(4,10)`；hook-time C0 为 `0x00000100`，最终 unit C0 为 `0x00000110`，task 2 resume 为 `0x080745A4`。
- base-ROM control run `e918e8f9f5f02b1f2e4db2291800a1ea` 的业务状态与画面和 observer exact，归一化 RGB SHA-256 为 `54f5409df260ee24f35a4940069f32d4bb77b56e42acce566343b8814a73564f`；EWRAM 差异只在 observer scratch。

## 稳定性与 checkpoint

- unchanged cycle analyzer 得到最小周期 288，匹配帧 `[0, 288, 576]`。
- 两次串行 288 帧零输入 replay 均为 completed/0、success-marker、non-degraded，且 inputs/pre-scripts 为空。
- 只机械复制 p1 为 canonical checkpoint：`artifacts/runtime-checkpoints/scenario-41-first-movedone-facing.ss9`，SHA-256 `1bc95c63cb11d469e4b2e80e8bae5a937f04ad40e18d7a15706fc261cb9ffb94`。p2 仅作复核，未持久化为 checkpoint。

## 冻结 evaluator 结果与边界

- 对 exact-A native frame plan（down 5、up 13、hold 8、capture 128）冻结后调用既有 `evaluateMovedoneEvidence`，结果为 `verified=false`、`diagnosticVerified=false`、`reason=coordinates-unchanged`。
- 该 fail-closed 结果符合事实：坐标从 `(4,10)` 到 `(4,10)` 未变化。fresh publication 不得改称 verified MOVEDONE 或 turn completion。
- 本 checkpoint 只证明稳定的朝向选择提示，以及 observer 观察到 fresh primary publication；不证明回合完成，不接受 MOVEDONE，不证明胜利或 postbattle。
