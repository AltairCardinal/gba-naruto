# 场景 45 安全恢复记录（2026-07-19）

## 最终结论

场景 `0x2D` 已在 immutable base ROM 上自然完成，并返回木叶世界地图。正式恢复点为
`artifacts/runtime-checkpoints/scenario-45-postbattle-world-map.ss9`，SHA-256 是
`61623b3ceeb9112326ed878099537ae40fd384877908850f6c60024c3e131923`。
标准零输入复放 run `ddd75bba563f2a286e85dbc3e03bcae0` 成功，task 2 resume 为
`0x08067D02`，RGB hash 为
`67adb3c5f6e21ea6e5488de965a6e57a50dce53a9f290c28697f73c4f2b16a7c`。

决定性胜利链为：卡卡西单位记录仍保存 3/100 HP，小樱位于相邻格 `(6,9)`，
近战预览伤害 5、命中率 96%；自然结算后立即出现“卡卡西老师被打倒了”与胜利页。
这再次证明击倒由战斗脚本/状态迁移决定，不能用 `HP==0` 作为唯一门槛。

## 安全基线

- 恢复前 macOS 中已有 25 份 `mGBA-*.ips`；本轮所有固定 runner 完成后仍为 25，没有新增崩溃报告。
- 峰值 owned-tree RSS 约 51.9–52.7 MiB；每个 audit 均记录 `pgid_clean=true`，含监听字段的 audit
  均记录 `mgba_listener_clean=true`，旧零输入 audit 的字段缺口在文末单独披露。
- `tools/run_guarded.py` 已接入危险 Lua 扫描与 crash-report latch；临时脚本中的 `os.exit` 会在 mGBA 启动前失败关闭。
- 每个 mGBA 进程都由固定 runner 独立获取 heavy lock、执行资源守卫并产出独立 audit；
  相邻的低风险单输入可以串行合并为一个 shell 闭环，但前一个 runner 必须成功退出后才能启动下一个，
  不允许并发 mGBA 或绕过守卫。

## 已推进结果

输入基线：

- `build/scenario-45-round2-naruto-melee-20260719/pulse-11.ss9`
- SHA-256：`82bed2b973c1aa4a062b6176831ca13c384ed7907e2c097b8e2aa47b5434ff12`

安全重放与鸣人攻击：

1. `zero-80.ss9` 证明原快照零输入稳定。
2. A 确认近战后，卡卡西从 100/100 降至 87/100，鸣人保持 109/109；本次自然近战伤害为 13。
3. 完成朝向与默认“不使用防御”确认，切换到小樱。
4. 小樱本回合已无法移动/攻击，安全结束其行动并完成朝向/防御确认，切换到佐助。

佐助状态：

- `build/scenario-45-safe-resume-20260719/sasuke-tech-back.ss9`：佐助行动菜单，SHA-256 `0051cd623c72d24b1ac31997c7f23db8d3d6c9e81b1c5439dda63bcfc1fbd25a`。
- 火遁术参数：伤害 15×1、距离 2、范围 1、命中率 95%、查克拉消耗 2。
- 火遁未进入目标执行，原因是佐助与卡卡西当前距离约 3；已取消选择并返回行动菜单。
- `build/scenario-45-safe-resume-20260719/sasuke-move-open-short.ss9`：佐助移动网格，SHA-256 `ce14199070eb2ac84f42c3a318ba05fb0ec6b4c1d1e926c52fcacf57d80bd2b0`。

## 输入时序结论

- 菜单→子界面使用 8 帧 A 会跨状态重复消费；1 帧 A（frame 5→6）只打开移动网格。
- 行动菜单刚恢复时，frame 5→13 的方向脉冲可能落入输入锁；frame 40→48 可稳定改变菜单行。
- 移动网格中 1/8 帧方向输入只改变面对/指向，不能保证走格；不能把“状态哈希变化”误判为有效移动。
- 岩石右侧黄色格不可达；从当前网格应复用历史 `scenario-45-sasuke-advance-end-20260719` 的长按走格模式，先到青色目的格，再用 1 帧 A 打开确认。

## 当时下一步（已被后续结果取代）

1. 从 `sasuke-move-open-short.ss9` 进行一个变量的长按 Up 校准，目标是实际进入岩石上方青色格；失败即回到同一快照，不沿错误分支累积。
2. 靠近到火遁距离 2 后选择火遁，完成目标与命中结算。
3. 每次有效攻击后建立零输入稳定快照，记录卡卡西 HP；重复自然回合直到场景胜利并固化场景 45 持久证据。

## 安全整改后续推进（13:28–13:36）

- 首次真实运行被 Lua 门禁安全拒绝，原因是错误字符串中的普通单词 `load` 被当作动态加载调用；mGBA 未启动。策略现先剥离 Lua 字符串与注释再检查代码，并新增固定单输入 runner 的预检回归。
- 后续所有真实运行均为 `completed/0`，峰值 owned-tree RSS 为 51.9–52.4 MiB，PGID 与监听残留检查全通过；crash report 始终为 25，latch 未出现，持久 baseline 已建立。
- 移动网格的正确语义已确认：方向输入选择橙色目的格，A 才执行整段移动；不是按住方向直接走格。`Up` 选中原地，`Down → Right → Right` 是绕过岩石的本轮可达终点，第三次 Right 会越界切换到敌方单位查看。
- 已从第二次 Right 的目的格确认移动。新恢复点为 `build/scenario-45-safe-resume-20260719/sasuke-move-drr-confirm.ss9`，SHA-256 `6aa4fcad670ddf377699888374994888782f99c4ab09b392d4b3dec6e6cfb772`；佐助已移动到卡卡西近旁并返回行动菜单。
- 从该行动菜单执行 `Down → A` 会打开“结束行动？”确认框，并非忍术菜单；`sasuke-postmove-tech-open.ss9` 只作为错误分支证据。下一次应从 `sasuke-move-drr-confirm.ss9` 校准其他菜单方向，不从确认框继续。

## 火遁命中与回合对白（13:40–13:55）

- 同类场景 41 证据证明移动后默认行动菜单已停在忍术项；从 `sasuke-move-drr-confirm.ss9` 直接 A 成功打开忍术列表，不需要 Down。
- 火遁完整自然输入链为：行动菜单 A → 火遁 A → “继续使用该攻击？”A → 列表 A → 目标网格 Right → 敌方预览 A → “可以吗？”A。`Up` 只移动到无敌人的相邻格；在斜视战场中屏幕右上方敌人对应控制器 Right。
- 敌方预览显示卡卡西 HP 87、预计伤害 49、命中 99%；火遁演出后经零输入 600 帧自然到达朝向提示，完成朝向和默认不防御后，卡卡西 HP 为 38，满足 `87 - 49 = 38`。这闭合了移动、技能选择、目标坐标、伤害预览和实际 HP 消费链。
- 决定性结算快照为 `build/scenario-45-safe-resume-20260719/sasuke-fire-defense-no.ss9`，SHA-256 `5f6947cc1b42f556730c96fc5d6ba0ee096dfddd7f2f26ce3820cb7ea317c9c1`；对应画面直接显示卡卡西 HP 38。
- 结算后零输入进入 Naruto 与 Kakashi 的回合对白。已自然推进 9 个 A 边界，当前恢复点为 `build/scenario-45-safe-resume-20260719/post-sasuke-dialogue-a9.ss9`，SHA-256 `a65f6900fea29d653244aad5c1cc58bed8de4a800952bc9e7593a807022e880b`；仍处于对白，尚未声称下一回合或胜利。
- 本段所有 mGBA run 均为非降级 `completed/0`，峰值 owned-tree RSS 51.8–52.3 MiB，`pgid_clean=true`、`mgba_listener_clean=true`。后续直接从 A9 继续对白，不重放移动或火遁链。

## 回合 3–6 与自然胜利

- 佐助第一次火遁把卡卡西从 87 HP 降至 38 HP；同回合资源消费后再次选择火遁会明确提示
  “查克拉不足”，证明查克拉消费进入实际技能门禁。
- 佐助随后使用零查克拉近战，预览伤害 11、命中率 98%，但自然结算后卡卡西仍为 38 HP，
  形成一次可审计的 RNG 未命中样本。
- 鸣人的远程忍具预览为攻击 6×3、距离 3、命中率 90%，自然命中后卡卡西从 38 HP
  降至 13 HP；下一回合再次选择同一忍具会提示库存不足，证明忍具按库存消费且不会每回合刷新。
- 小樱两次零查克拉近战分别把卡卡西从 13 HP 降至 8 HP、再从 8 HP 降至 3 HP。
  离线读取 `0x020240C0 + slot*0x1D4` 记录确认 Naruto/Sasuke/Sakura/Kakashi 坐标分别为
  `(5,9)/(4,10)/(6,9)/(6,8)`，最终应从小樱目标网格输入 `Up`，而非错误分支的 `Left`。
- 决胜预览快照为 `round6-sakura-correct-preview.ss9`，SHA-256
  `c382a80f0466ff38ae555e87c91d5cb0b8c5c2ee37d5628ef3dcd12d90591871`；结算后
  `victory-dialogue-a2.ss9` 显示胜利，SHA-256
  `ceb2d02dc49ab88ea610096b1e98c6b116af1cb1a33e2fb2597b05a9b3a73aa0`。

## 奖励与安全边界

- 结果页给 Naruto、Sasuke、Sakura 各 150 EXP；战后模板记录为 Naruto LV3/EXP275、
  Sasuke LV3/EXP0、Sakura LV3/EXP60，佐助和小樱均出现升至 LV3 的成长页，随后出现技能解锁序列。
- 场景目录共 289 份含 RSS 的守卫 audit，全部 `success=true`、`pgid_clean=true`；其中 271 份
  内嵌监听检查且全部 `mgba_listener_clean=true`，18 份旧零输入 audit 未写该字段，不能把字段缺失
  解释为独立通过。最终 `lsof` 检查无 mGBA 监听。最高 owned-tree RSS 52.74609375 MiB，
  正式世界地图零输入复放为 52.6640625 MiB，均远低于 140 MiB 上限。
- macOS `mGBA-*.ips` 数量保持 25，未新增崩溃报告，未生成
  `build/resource-guard/mgba-crash-latch.json`，结束后无 mGBA 进程残留。
- 正式机器可读证据为
  `artifacts/runtime-checkpoints/scenario-45-progression-evidence.json`；本结论只覆盖场景 45，
  不声称后续任务已完成。
