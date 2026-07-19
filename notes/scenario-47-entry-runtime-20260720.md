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
