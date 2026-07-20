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

## 第 6 回合失败谓词复核

- ROM 中 `0x0807305C` 调用 `0x080777FC(0)`，并在 `0x08073068` 把返回值写入
  `0x02026807`。battle 15 的条件记录位于 `0x0859534C`；返回 `1` 是胜利组，返回
  `2` 是失败组。第 6 回合分支自然写入 `2`，不是 mGBA 或脚本伪造结果。
- 第 6 回合快照中木叶丸/卷轴代理槽仍显示 5 HP，但其特殊状态始终不能单靠 HP
  判断目标安全；失败转场后该槽的 character ID 从 30 清为 0。敌人停在
  `(3,4)/(4,5)` 并不构成安全硬阻断，旧快照只能作为负证据，后续不得再从它继续求胜。
- 这排除了“单纯拖到第 6 回合即可”的假设。有效路线必须在更早回合形成多人火力，
  并在目标脚本清除代理槽前击倒进入卷轴路线的敌人。

## 提前集结路线

- 从第 1 回合改动后排决策：Sasuke 从 `(2,12)` 正常移动到 `(2,10)`，再瞬身到
  `(2,8)`；Sakura 从 `(3,15)` 正常移动到 `(3,12)`，再瞬身到 `(3,10)`。
  第 1 次敌方阶段后两人均保持满血，木叶丸保持 40/40 HP。
- 第 2 回合先让 Sasuke 瞬身到 `(3,6)`，Naruto 沿已验证路线移动到 `(2,6)` 后
  瞬身到 `(4,5)`，Sakura 再瞬身到 `(4,8)`。第 3 回合开始时敌 5 位于 `(4,6)`，
  被 Naruto `(4,5)` 与 Sasuke `(3,6)` 夹住，Sakura 已进入支援距离；三名玩家单位
  HP 为 `134/134/86`，木叶丸仍为 40/40 HP。
- 正式恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round3-frontline-assembled.ss9`，
  SHA-256 `9ce9973360b8636952b0cbd44b44104b1a8ded15f52a07c11e284157831b420e`。
  600 帧零输入验证 run `247c49536dc85a82fe8da0141138f047` 成功，峰值
  51.85546875 MiB，`zero_input_verified=true`、`pgid_clean=true`。
- 该回合首个 97% 联携攻击仍未命中，证明此前的坏 RNG 不只影响 98%/90% 技能，
  且 100% 影分身不会推进命中 RNG。该未命中分支只保留在 `build/`；下一闭环应从
  正式恢复点用可验证的 RNG 消耗动作或 100% 伤害手段开始，不接受重复同一攻击。

## 资源安全

- 本轮所有 mGBA 输入和零输入等待均经资源守卫与 heavy lock 串行运行。
- 成功 run 的 owned-tree RSS 稳定在约 52 MiB，`pgid_clean=true` 且监听检查干净；
  没有新增 mGBA 崩溃、残留进程或内存异常。

## 保留行动资源后的命中路线

- 旧“提前集结路线”在第 2 回合为 Sasuke、Sakura 重复消耗瞬身，既浪费查克拉也提前
  结束行动。新路线保留 Sakura 的正常移动，并避免 Sasuke 的无效瞬身；第 3 回合形成
  连续命中：Naruto 普通攻击 `110 -> 94`、Sakura 普通攻击 `94 -> 84`、Sasuke
  联携普通攻击 `84 -> 49`。这证明此前画面上的部分“未命中”实际伴随替身/回避位移，
  不能只归因于一个尚未定位的战斗 RNG 状态。
- 第 4 回合 Naruto 再将同一敌人 `49 -> 33`。随后通过逐回合贴身牵制，路线首次安全
  跨过旧第 6 回合失败边界，并自然进入第 8 回合；Sakura 此时为 1 HP、已不能行动，
  但 Naruto/Sasuke 仍分别有 73/83 HP，护送对象为 14 HP。
- 第 8 回合正式恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round8-bait-success.ss9`，SHA-256
  `23d03e0c6f591beeea3fda0d0e8e2911891394ea1ed5fbbca24d80371978a2a6`。80 帧零输入
  验证 run `88265b294e214300236228b37fab773e` 成功，峰值 51.87890625 MiB，
  `zero_input_verified=true`、`pgid_clean=true`。

## 第 8/9 回合失败边界

- 第 8 回合 Naruto 移至 `(2,4)`，普通攻击把目标旁的敌人 `110 -> 94`；Sasuke
  瞬身到 `(3,5)`。敌方仍能从另一侧攻击护送对象，使其 `14 -> 2 HP`。这排除了
  “只在正面堆两名玩家即可完全吸收仇恨”的假设。
- 第 9 回合 Naruto 再把该敌人 `94 -> 78`，Sasuke 把另一名敌人 `33 -> 19`；敌方
  行动后护送对象的状态由 `0x90` 变为 `0x190` 并触发倒地对白。失败发生时 Naruto、
  Sasuke 仍存活，说明瓶颈是前期总输出与双侧攻击位控制，不是玩家队伍生存。
- 下一有效闭环应从第 3 回合或更早的已验证快照重排火力：优先保留 Sakura 行动能力，
  集中击倒首名 110 HP 敌人，并确保在护送对象降到 14 HP 前处理第二个相邻攻击位。
  第 8 回合快照适合复核目标 AI/失败谓词，不再作为求胜主路线反复试错。

## 第 4 回合远程压血路线

- 第 3 回合的既有最优组合仍是 Naruto 普攻 16、Sakura 普攻 10、Sasuke 联携 35，
  合计 61。Naruto 先用组合拳会令 Sasuke 的联携退化为 14；先用十字手里剑则因消耗
  3 查克拉产生同样退化，因此两者都不能替换该组合。
- 第 4 回合改为让 Naruto 留在 `(4,5)` 远程使用十字手里剑，首敌 `49 -> 31`；随后
  Sasuke 进入 `(5,5)` 普攻 `31 -> 17`。Sakura 因移动范围/地形无法到达 `(6,6)`，
  改为攻击相邻的第二敌。敌方阶段首敌移动到 `(5,7)` 攻击 Sakura，护送对象保持
  `40/40 HP`。
- 第 5 回合 Sasuke 对 17 HP 首敌的 99% 补刀触发替身，敌人位移但没有受伤；Sakura
  虽仍有 6 HP，状态 `0x110`，已被跳过。到第 6 回合护送对象仍为 40 HP，首敌仍为
  17 HP，显著优于旧第 6 回合的 5 HP/失败边界。
- 新的第 6 回合恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round6-objective40-enemy17.ss9`，
  SHA-256 `082522726e1d8a2c154a8feff66b95240fe53fd4c54f32bc553a4e5e3c4abc62`。
  80 帧零输入验证 run `c98f24b1e0714a63cdb6e67936b56c34` 成功，峰值
  51.95703125 MiB，`zero_input_verified=true`、`pgid_clean=true`。
- 下一动作应先处理护送对象旁 `(3,5)` 的 110 HP 敌人，同时让 Sasuke 从 `(5,6)`
  继续追击 `(5,7)` 的 17 HP 首敌；不再回滚到第 8 回合濒死分支。
