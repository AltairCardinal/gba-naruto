# 卷轴防卫战（battle 15）运行时记录（2026-07-20）

## 入口与目标

- 从 `artifacts/runtime-checkpoints/scenario-49-battle-14-postbattle-task-menu.ss9`
  选择任务出发，战斗控制区确认实际 battle ID 为 15 (`0x0F`)。
- 开场对白由木叶丸明确要求保护卷轴，画面右上宝箱是目标。失败条件不是木叶丸 HP
  归零：多条失败分支在木叶丸仍有 `12/40`、`19/40`、`5/40` HP 时已经显示
  “失败”并进入 Game Over。
- 正式入口恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-entry.ss9`，SHA-256
  `9e74b086029b0873dfae1c6237e1ebf5fbccc4a01b493cdff35981b0bb6c2cc8`。
  600 帧零输入验证 run `11462ee28020230f68235d2f2bd4113b` 成功，峰值
  owned-tree RSS 51.96875 MiB，`zero_input_verified=true`、`pgid_clean=true`。

## 单位状态与危险边界

- 玩家 Naruto/Sasuke/Sakura 均为 LV6，入口 HP 为 `152/134/125`；木叶丸为
  character 30、LV3、HP 40。五名敌人均为 character 35、LV5、HP 110。
- 第 3 回合的正式恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-escort-12hp-player-turn.ss9`，
  SHA-256 `7d6796a767d574f5f7a91935c3c1e65ce44edbc51aa5a6b587784d4730bbe94f`。
  600 帧零输入验证 run `afbd48ab7818a88c9e370f1233f1a98b` 成功，峰值
  51.9140625 MiB，`zero_input_verified=true`、`pgid_clean=true`。
- 该恢复点已经晚于安全决策边界：5 号敌人在 `(3,3)`，其下一次自动阶段能触发卷轴
  失守。后续路线应从更早的 `enemy2-wait` 分支继续；当时木叶丸仍为 40 HP，5 号敌人
  在 `(3,5)`。

## 已排除路线

1. 在晚期恢复点让 Naruto 移到 `(3,4)` 并攻击 5 号敌人：预览 27，但本次 RNG 未命中，
   敌人仍为 110 HP；自动阶段后直接失败。
2. 在同一晚期恢复点于 `(4,4)` 生成影分身：分身 152 HP 且改变了部分敌方寻路，木叶丸
   仍为 12 HP，但 5 号敌人进入目标判定范围后仍失败。
3. 提前一回合在 `(2,4)` 生成影分身：木叶丸同期提高到 19 HP，分身仍为 152 HP，
   但 5 号敌人移动到 `(4,4)` 后仍触发失败。
4. 提前一回合让 Naruto 移到 `(3,6)`，普通攻击把 5 号敌人 `110 -> 94` 并贴身拦截：
   AI 仍越过 Naruto 到 `(3,3)`，木叶丸降到 5 HP，路线仍已进入失败边界。

这些结果证明承伤、仇恨和单纯占位都不是充分条件；必须在 5 号敌人进入卷轴判定区前
击倒它，或找到能硬性阻断其目标移动的地形/状态。下一闭环应回到更早回合集中 Naruto、
Sasuke 的高伤害技能处理 5 号敌人，不再重复晚期救援实验。

## 已验证的提前拦截路线

- 第 2 回合 Naruto 从 `(2,9)` 正常移动到 `(2,6)` 后，不再直接结束行动，而是继续使用
  瞬身术到 `(4,5)`。随后 5 号敌人从 `(6,5)` 改为移动到 `(4,6)` 并攻击 Naruto，
  Naruto `152 -> 140 HP`，木叶丸保持 `40/40 HP`；这首次改变了敌人的卷轴路径。
- 下一玩家回合的第一个命中随机数异常地同时使 98% 普通攻击和 90% 十字手里剑未命中。
  改用 100% 成功的影分身术，在 `(5,5)` 生成 140 HP 分身并消耗该行动周期。下一敌方
  阶段后 5 号敌人退到 `(4,8)`，另一敌人在 `(4,6)` 与前线交战，木叶丸仍为 19 HP；
  随后自然进入第 4 回合，没有触发旧路线的失败判定。
- 第 3 回合安全恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-safe-intercept-turn3.ss9`，SHA-256
  `2d872689345ade80d0027dfa7bbb58adfc28cfe3028f6b13856d43c8dc7a6ba8`。600 帧零输入
  run `81c22bfbab91bd081a66af7513d26fde` 成功，峰值 51.95703125 MiB，
  `zero_input_verified=true`、`pgid_clean=true`。
- 已跨过失守判定的第 4 回合恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round4-scroll-safe.ss9`，SHA-256
  `3ee17bef07d87173eee28a079511538c7a3eb0e2b7df3015cba787b383418cfa`。600 帧零输入
  run `81c3b777dd3d527600f63c199c81b564` 成功，峰值 51.94921875 MiB，
  `zero_input_verified=true`、`pgid_clean=true`。
- 第 5 回合若让分身留在 `(4,6)` 攻击，5 号敌人会从 `(3,6)` 进入 `(4,4)` 并立即
  触发失败；即使敌人已受伤到 94 HP 也不会改变判定。正确路线是让分身瞬身到 `(4,4)`
  直接占据失守格。敌方随后只能停在 `(3,4)`/`(4,5)`，分身剩余 111 HP，木叶丸保持
  5 HP，并自然进入第 6 回合。
- 第 6 回合硬阻断恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round6-hardblock.ss9`，SHA-256
  `10c1eac73a03e74182ed4f7c558410e8bb91794b8939080ceaf0e45c516e9390`。600 帧零输入
  run `d9711b258e5ce26a3f2045fb311cc19b` 成功，峰值 51.84375 MiB，
  `zero_input_verified=true`、`pgid_clean=true`。

## 资源安全

- 本轮所有 mGBA 输入和零输入等待均经资源守卫与 heavy lock 串行运行。
- 成功 run 的 owned-tree RSS 稳定在约 52 MiB，`pgid_clean=true` 且监听检查干净；
  没有新增 mGBA 崩溃、残留进程或内存异常。
