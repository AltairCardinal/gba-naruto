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

## 第 7 回合正面占位路线

- 第 6 回合 Naruto 普攻把 `(3,5)` 敌人 `110 -> 87`，Sasuke 普攻把 `(5,7)`
  首敌 `17 -> 3`；敌方阶段后护送对象 `40 -> 28`、Naruto `79 -> 28`，自然进入
  第 7 回合。若第 7 回合让 Naruto 原地普攻、Sasuke 攻击 `(4,6)`，两次攻击均被
  替身规避，护送对象随后 `28 -> 4`，该分支只保留为负证据。
- 改进路线让 Naruto 使用瞬身术从 `(4,5)` 进入卷轴正前方 `(2,4)`。`(2,5)` 是
  非法落点，游戏会显示“请选择有效的目标”；这是技能目标约束，不是 mGBA 卡死。
  Sasuke 随后对 `(4,6)` 敌人使用 98% 忍者组合拳；攻击仍被替身规避，但敌人位移到
  `(5,7)`，清开中路。敌方阶段 Naruto 承伤 `28 -> 17`、Sasuke `110 -> 98`，护送
  对象保持 `28/40`，显著优于原地对攻路线。
- 第 8 回合正式恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round8-objective28-frontblock.ss9`，
  SHA-256 `ef761db1ff4ba3d985150d9ec7d1e75d49e35717d3fe76acaf995ea1673922b8`。
  80 帧零输入验证 run `9c6a95a139075f4f84351f03c159eac7` 成功，峰值
  52.1328125 MiB，`zero_input_verified=true`、`pgid_clean=true`。
- 第 8 回合开始时 Naruto `(2,4)`、17 HP、3 查克拉，Sasuke `(5,6)`、98 HP、
  1 查克拉；护送对象 `(1,4)`、28 HP。3 HP 首敌位于 `(1,5)`，87 HP 敌人位于
  `(3,4)`，其余三敌位于 `(2,6)`、`(3,6)`、`(5,5)`。下一闭环应优先清除 3 HP
  首敌，并维持 `(2,4)`/`(3,4)` 一线的正面占位。

## 第 8 回合休息承伤路线

- Naruto 当前的可用技能列表在 98% 忍者组合拳处结束，90% 十字手里剑已被列表过滤；
  重复单输入仍不改变选择，因此不是输入丢失。现有静态证据尚不能区分忍具库存、技能
  资格或单位状态条件，不能把原因写成“查克拉必须大于 3”。选择“休息”后 Naruto HP
  `17 -> 47`、查克拉保持 3，证明休息恢复的是 30 HP，而且不会改变该列表过滤状态。
- Naruto 原地休息、Sasuke 普攻 `(5,5)` 敌人 `110 -> 96` 后，敌方阶段护送对象
  `28 -> 16`、Naruto `47 -> 19`，双方仍未触发胜负。3 HP 首敌保持 `(1,5)`；其余
  敌人移动到 `(1,6)`、`(2,3)`、`(3,4)`、`(3,5)`。
- 普通组合拳不能攻击 Naruto `(2,4)` 对角的 `(1,5)` 敌人：目标选择器可以选中该敌，
  但确认时明确提示不在攻击范围。该敌只能由远程技能或后续近身单位处理。
- 单位结构 `+0xC4/+0xC5` 在正常移动后保留回合起点；实际落点写入
  `+0xC7/+0xC8`。此前只读取前者会把 Sasuke 从 `(5,6)` 到 `(4,6)` 的正常移动误判
  为“未移动”；后续运行时坐标判定必须同时记录两组字段，并以 `+0xC7/+0xC8` 作为
  已提交移动后的当前位置。
- 第 9 回合正式恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round9-objective16-restline.ss9`，
  SHA-256 `bc7de1c43e1a552937fcc01c8034e1e3e67fe47b4a128b82ab7ec56fac4f00b0`。
  80 帧零输入验证 run `29f97cfa6b79552bb636d26cbf75b247` 成功，峰值
  51.98046875 MiB，`zero_input_verified=true`、`pgid_clean=true`。

## 第 8 回合提前推进路线

- 在 Naruto 休息后，不再让 Sasuke 原地攻击 `(5,5)` 敌人，而是正常左移到
  `(4,6)`。移动后菜单只剩“术・忍具 / 行动结束”，默认停在顶部“术・忍具”；直接
  `A` 打开技能列表，按 `Up` 才会切换到底部“行动结束”。此前把顶部项误写成默认
  “行动结束”，已由第 10 回合的可重复输入链纠正。
- 提前移动改变了敌方目标选择：敌方阶段护送对象保持 `16/40`，Naruto
  `47 -> 25`、Sasuke `98 -> 81`，并自然进入第 9 回合。相比旧休息路线同期 Sasuke
  仍在 `(5,6)`，该路线把主力提前一格且没有额外损失护送对象 HP，因此取代旧快照
  作为后续求胜主线；旧快照仍保留为对照证据。
- 改进后的第 9 回合恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round9-objective16-sasuke46.ss9`，
  SHA-256 `22c08cf668959e001f326eb5eb5d02b927ee09006e83e11248cc58a3ae935f24`。
  80 帧零输入验证 run `2ed60ed4719eada06eeefa0c3c0069ae` 成功，峰值
  51.953125 MiB，`zero_input_verified=true`、`pgid_clean=true`。

## 临时产物容量整改

- `build/` 一度达到 46 GiB，数据卷只余 81 MiB；根因是 5,166 份已结束运行遗留的
  `staged.gba/.sav` 隔离副本，合计约 30.43 GiB。它们不属于审计证据，且可由 runner
  重新生成。
- 清理仅删除 `build/**/staged.gba` 与 `build/**/staged.sav`，保留所有 audit、guard
  summary、`output.ss9`、PNG 和正式 checkpoint。清理后 `build/` 为 16 GiB、数据卷
  可用空间约 31 GiB；清理期间没有 mGBA 进程启动或残留。

## 第 10 至 11 回合首敌清除

- 改进后的第 9 回合路线中，Naruto 休息后为 63 HP；敌方阶段使护送对象降至
  `4/40 HP`，但仍未触发失败。第 10 回合起点已保存为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round10-objective4-sasuke26.ss9`，
  SHA-256 `b9a7ee664e157081be03b1fa28e3fe43ed0e93f5e87fe75ca878b8cbef4c4c4f`；
  80 帧零输入恢复验证 run `4193649db5eb8257892025ddefad739d` 成功，峰值
  52.01171875 MiB，`zero_input_verified=true`、`pgid_clean=true`。
- Sasuke 不能从 `(2,6)` 上移到 `(2,5)`，但可左移到 `(1,6)`；移动后的默认菜单项是
  “术・忍具”。向下两次选择 0 查克拉、99% 的忍者组合拳，向上选择 `(1,5)` 的
  3 HP 敌人，预览伤害为 14。结算后该槽 character ID 从 35 清零而 HP 字段保留 3，
  再次证明击倒必须以 character ID/状态转移确认，不能只检查 HP 是否归零。
- 敌方阶段后 Naruto `63 -> 41 HP`、Sasuke `70 -> 58 HP`，护送对象保持
  `4/40 HP`，其坐标从 `(1,4)` 更新为 `(1,5)`，并自然进入第 11 回合。剩余四敌为
  96、87、110、110 HP，战斗结果字节仍未置位。
- 第 11 回合正式恢复点为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round11-objective4-first-enemy-cleared.ss9`，
  SHA-256 `d34b5bde39f68148860a751c1eee3e67906b5f74351072d7cc31bf1fcf53d4f5`。
  从该正式文件执行 80 帧零输入恢复验证 run `49977bf48be8af5ae09bb1d08dee7272`
  成功，峰值 51.96484375 MiB，`zero_input_verified=true`、`pgid_clean=true`。

## 第 11 至 14 回合稳定削减循环

- 第 11 回合由 Sasuke 原地使用 99% 忍者组合拳，把侧翼敌人 `96 -> 82`；Naruto
  原地休息 `41 -> 71`。敌方阶段后护送对象仍为 4 HP，Naruto 49 HP、Sasuke
  47 HP，自然进入第 12 回合，证明“一个单位休息、另一个单位攻击”能在不丢失正面
  占位的情况下形成可持续循环。
- 第 12 回合起点保存为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round12-objective4-stable-loop.ss9`，
  SHA-256 `a1919e59dfbc8f0a1995f06269224059b500c8f3a89a7e5467acffba0b2ff91a`；
  80 帧零输入验证 run `0ba1d3f218a49d75fb26901a14bc3902` 成功，峰值
  52.04296875 MiB，`zero_input_verified=true`、`pgid_clean=true`。
- 第 12 回合重复 Naruto 休息、Sasuke 攻击，侧翼敌人 `82 -> 68`；第 13 回合改为
  Sasuke 休息、Naruto 攻击正面敌人 `87 -> 71`。两回合敌方阶段均只攻击玩家单位，
  护送对象保持 4 HP。第 14 回合 Naruto 46 HP、Sasuke 50 HP，两名已受伤敌人为
  68/71 HP，另两敌仍为 110/110 HP。
- 第 14 回合起点保存为
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round14-objective4-enemies68-71.ss9`，
  SHA-256 `9e22602e5e5391bb83ef661e56ec6c58599d6953b344b88b07902c8f6530682d`；
  80 帧零输入验证 run `3ba74ec41c33ccb430018f6476f67b4e` 成功，峰值
  52.0234375 MiB，`zero_input_verified=true`、`pgid_clean=true`。
- 第 14 回合开头的红色选择箭头曾短暂落在木叶丸/护送单位上，但 `A` 只把选择推进到
  Naruto，没有打开木叶丸行动菜单；该单位不能据此视为可控或可通过“休息”主动恢复。
