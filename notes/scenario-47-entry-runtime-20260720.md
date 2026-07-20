# 场景 46 后下一主线与 battle 13 入口（2026-07-20）

## 当前边界

- 从 `artifacts/runtime-checkpoints/scenario-46-postbattle-world-map.ss9` 恢复后，世界地图标题为
  “木叶之里”。选择主菜单默认“移动”，再确认地点列表默认项，进入卡卡西在室内说明下一任务的
  对白。
- “场景 47”仍只作为连续工作编号。继续自然推进森林对白，在任务目标页从
  “队伍·装备 / 查看地图 / 行动任务 / 保存”总菜单选择“行动任务”并确认后，已经进入真实战斗。
- 战斗入口状态的 `0x02026804..0x0202680B = 00 0d 00 00 00 00 00 00`，所以这段主线的
  **实际 battle ID 为 13 (`0x0D`)**，不能把连续工作编号 47 当成 ROM battle ID。
- 玩家单位槽 1..3 分别为 Naruto（character 1，LV4，HP 123）、Sasuke（character 2，
  LV3，HP 89）、Sakura（character 3，LV4，HP 95）；敌方槽 4..8 均为 character 33，
  LV3，HP 80。玩家初始坐标为 `(6,3)/(4,3)/(8,3)`，敌方初始坐标为
  `(1,10)/(3,14)/(6,16)/(9,14)/(11,10)`。
- 正式恢复点为 `artifacts/runtime-checkpoints/scenario-47-intro-kakashi.ss9`，SHA-256
  `73d56ff495f80a583bd179d3f8def8bc34693c3e0e2e3241fb281885d89f0cf7`。80 帧零输入恢复 run
  `6317d082a3713058bce3652e8e4e15c9` 成功，峰值 owned-tree RSS 51.859375 MiB，
  `pgid_clean=true`。
- 战斗入口正式恢复点为 `artifacts/runtime-checkpoints/scenario-47-battle-13-entry.ss9`，
  SHA-256 `af1c2f79643bbe45bf4f179ea36e4b951bdaa4de70d54aa754c11085c30f8e03`。
  600 帧零输入恢复 run `5b9997aa600ce3c4215906ba739e957f` 成功，
  `zero_input_verified=true`、`pgid_clean=true`，峰值 owned-tree RSS 52.1875 MiB。
- 后续从该对白快照继续，不重放场景 46 战斗与结算；自然完成任务并累计等级，直到 Naruto
  达到 LV8 或首次出现 secondary level 激活，再恢复 `levels` consumer 观测。战斗入口已经
  固化后，后续优先从 battle 13 快照恢复，不再重放 60 页对白与任务前菜单。

## 资源状态

- 本段 mGBA 全部经 heavy guard 串行执行，启动前后无 mGBA 残留。
- 建立快照时系统可用内存为 66%；此前整段场景 46 与入口运行期间 crash report 保持 25。
- battle 13 入口零输入验证后 crash report 仍为 25，没有新增崩溃记录。

## battle 13 第四回合恢复点

- 部署阶段必须依次确认 3 名玩家与 5 名敌方的 8 条 active formation 记录；第八次确认后显示
  “开始”，再完成战前对白才进入玩家控制。任务“相关条件”页明确要求打败 5 名不明忍者，
  与敌方槽 4..8 一致。
- 第一回合将 Naruto 从 `(6,3)` 推进到 `(6,6)`；Sasuke 直达 `(4,6)` 会撞岩石，最终经
  `(5,3)` 到 `(5,5)`；Sakura 的 `(8,6)` 同样是岩石，最终停在 `(8,5)`。被拒绝的候选
  没有串入有效状态。
- 第二回合 Naruto 移动到 `(7,8)`。本关行动菜单第三项是“查克拉”，不是普通攻击；攻击必须
  从“术·忍具”选择带“攻”标记的技能。第三回合使用距离 1、攻击力 10×1、命中 98% 的
  攻击术命中槽 8，使其 HP `80 -> 66`；攻击预览给出的实际伤害为 14。
- 敌方连续推进并攻击后，第四回合玩家控制时 Naruto/Sasuke/Sakura HP 分别为 `96/89/95`，
  坐标为 `(7,8)/(5,5)/(8,5)`；敌方槽 4..8 坐标为
  `(7,9)/(5,8)/(6,10)/(9,7)/(8,8)`，HP 为 `80/80/80/80/66`。
- 正式恢复点为 `artifacts/runtime-checkpoints/scenario-47-battle-13-turn4-player.ss9`，
  SHA-256 `5815e69ad0ed435f51610b95e85f375325491bafbf16fed6a8facf15429e0d4b`。
  600 帧零输入恢复 run `8952f3b4fafb31e26aca5f0a8bce3dd7` 成功，
  `zero_input_verified=true`、`pgid_clean=true`，峰值 owned-tree RSS 51.9375 MiB。
- 后续直接从第四回合快照继续：敌人已围拢，优先让三名玩家使用攻击术集中消耗同一目标，
  不再重复部署、接敌或远程技能方向试探。

## battle 13 首敌击倒恢复点

- Naruto 的行动菜单第三项实际是“查克拉”，本关攻击从“术·忍具”中的“攻”技能发起。
  距离 1、攻击力 10×1、命中 98% 的技能连续造成 14、21、14 点伤害；第四项攻击力
  6×3、命中 90% 的多段技能再造成 24 点伤害。第七回合最后一次邻接攻击触发剧情对白，
  对白结束后槽 8 character ID 清零，确认首名敌人自然击倒。
- Sakura 从 `(8,5)` 直达 `(8,7)` 被游戏拒绝，改走 `(9,6)` 有效；随后两次攻击槽 7，
  使其 HP `80 -> 72 -> 64`。Sasuke 在 `(5,5)` 使用距离 1 攻击槽 6，使其 HP
  `80 -> 69 -> 58`。Sasuke 默认火遁标示距离 2，不能用于邻接目标。
- 当前玩家 HP 为 Naruto/Sasuke/Sakura `14/59/70`。正式恢复点停在 Sasuke 攻击完成后的
  朝向选择、尚未进入下一敌方阶段：
  `artifacts/runtime-checkpoints/scenario-47-battle-13-turn7-first-kill.ss9`，SHA-256
  `d4429e4993bb96a5c638266a06456dd9f2a29e400e35d4938eeca3040774736a`。
  600 帧零输入恢复 run `79a81a85b274ffd3e54f9ac3acd0f047` 成功，
  `zero_input_verified=true`、`pgid_clean=true`，峰值 owned-tree RSS 52.05859375 MiB。
- 下一步先选择 Sasuke 朝向；Naruto 只有 14 HP，不能直接重复无防御过回合。应测试防御或
  分身吸收火力，并让 Sakura/Sasuke 优先击倒相邻目标，避免 Naruto 在下一敌方阶段阵亡。

## battle 13 第五回合撤退恢复点

- 首敌击倒路线证明原地持续输出会让 Naruto 承受每回合约 18 点的集中伤害；第八回合后即使
  只等待一个回合也会触发 Naruto 倒地剧情，Sasuke/Sakura 无法独立把该路线推进到胜利。
- 从正式第四回合快照重新开始后，Naruto 不攻击，先向北撤到 `(7,3)`；Sakura 和 Sasuke
  分别按已验证路线移动到 `(9,6)`、`(5,7)`。方向键必须复用原始帧时序：Sakura 的单格
  `Right/Down` 使用 1 帧按压，Sasuke 的两格 `Down` 使用 12 帧按压；统一长按会越过目标。
- 第五回合玩家控制时 Naruto/Sasuke/Sakura HP 为 `96/79/85`，说明 Naruto 相比旧路线同期
  `73` HP 完全避开了集中攻击。敌方槽 4..8 位于 `(7,7)/(5,8)/(7,8)/(9,7)/(7,6)`，
  HP 仍为 `80/80/80/80/66`；后续由两名队友攻击相邻目标，Naruto 继续保持距离。
- 正式恢复点为 `artifacts/runtime-checkpoints/scenario-47-battle-13-turn5-retreat.ss9`，SHA-256
  `529b3e0f64d5b9a161994765efa25f341f9d8d5b772d45f5f3cc8df9fadd6e55`。600 帧零输入恢复 run
  `4aa2c91a4f1f710a6896fd33ffbb0368` 成功，`zero_input_verified=true`、`pgid_clean=true`，
  峰值 owned-tree RSS 51.9609375 MiB。

## battle 13 第二敌击倒恢复点

- **该恢复点已被下文第 22 回合的休息轮换路线取代。** 本段快照停在延迟提示中，且 Sasuke
  已退场、Sakura 仅 19 HP；它只保留为失败路线证据，不再作为后续主线恢复点。
- 第五至第八回合让 Naruto 轮换承伤，并由 Sakura/Sasuke 攻击相邻目标。Sasuke 在 9 HP
  触发低体力剧情后退场；Sakura 保持 19 HP，Naruto 保持 60 HP。
- Naruto 从 `(9,4)` 移到 `(11,4)` 后攻击槽 8 `(11,5)`，使其 character ID `33 -> 0`，
  确认第二名敌人击倒。移动完成后的行动菜单游标停在“行动结束”；必须 `Down` 两次才到
  “术·忍具”，按一次会误选结束行动，按 `B` 则会取消刚完成的移动。
- 正式恢复点为 `artifacts/runtime-checkpoints/scenario-47-battle-13-turn9-second-kill.ss9`，
  SHA-256 `d7d480d22cc98bb4924d674a46a58fee6324e279060742309fcede91b1db75f9`。600 帧零输入恢复 run
  `680fb78679f53d71a8de55d665f70f3a` 成功，`zero_input_verified=true`、`pgid_clean=true`，
  峰值 owned-tree RSS 52.140625 MiB。后续从该点继续，剩余敌方槽 4..7 共 4 名。

## battle 13 第三敌击倒与第 22 回合恢复点

- 从第五回合撤退快照重新推进后，采用“低血量角色休息、健康角色攻击”的轮换路线。第 15
  回合 Sasuke 在敌方阶段自然退场，但 Naruto/Sakura 保持可持续恢复；第 16 至 20 回合由
  Naruto 连续休息、Sakura 每回合攻击近身目标，使 Naruto 的回合起始 HP 从 `16` 稳定增长到
  `32`，没有再进入阵亡阈值。
- 第 21 回合 Naruto 攻击槽 6，使其 HP `26 -> 5`；Sakura 随后完成击倒，槽 6 character ID
  `33 -> 0`。击倒动画会延迟“请选择人物面对的方向”和防御忍术提示，必须分别观察画面后再
  单发 `A`，不能把下一角色或敌方阶段输入提前串入。
- “进入术·忍具后按了几次 Down”不能单独证明技能序号：菜单会保留上次选择，并可能在边界
  停留或回绕。后续应同时核对技能面板的攻击力、命中率和目标格类型；本路线使用的是
  `10x1`、命中 `98%`、距离 1 的近身攻击。此前按 Down 次数推导“第四技能”的说法不再作为
  技能表证据。
- 第 22 回合玩家控制时 Naruto/Sakura HP 为 `23/95`，坐标为 `(9,4)/(10,5)`；Sasuke 已
  退场。剩余敌方槽 4、5 HP 为 `80/58`，坐标为 `(9,5)/(8,5)`；槽 6..8 character ID
  均为 0，确认已完成三次自然击倒。
- 正式恢复点为
  `artifacts/runtime-checkpoints/scenario-47-battle-13-turn22-third-kill-rest-route.ss9`，
  SHA-256 `be0ac5c920d4c5b6d8ad60300163ece179d05ecf10ae6af0fe6a2cf2b46e6cbe`。
  600 帧零输入恢复 run `71cb1555e5d27cfd43a955747b4bc7f9` 成功，
  `zero_input_verified=true`、`pgid_clean=true`，峰值 owned-tree RSS 51.85546875 MiB。
- 后续优先从该快照继续，不再恢复旧的第二击倒失败路线。先让 Naruto 休息并由 Sakura 集中
  攻击 HP 58 的槽 5；击倒后再处理槽 4。
